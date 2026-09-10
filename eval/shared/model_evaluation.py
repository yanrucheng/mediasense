"""One offline evaluation entry: prepare inputs, encode, then render fixed clusters."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import resource
import struct
import subprocess
import sys
import time

from model_evaluation_inputs import (
    digest,
    fixture_roots,
    fingerprint,
    outside,
    prepare_inputs,
    stage_fixture,
    validate_inputs,
    write_json,
)


def inference_fingerprint(config: dict) -> str:
    return fingerprint(
        {
            key: config[key]
            for key in (
                "fixture",
                "inputs",
                "expected_input_fingerprint",
                "model",
                "runtime",
            )
        }
    )


def validate_vector(raw, dimensions: int) -> tuple[float, ...]:
    values = tuple(float(value) for value in raw)
    if len(values) != dimensions or not all(map(math.isfinite, values)):
        raise ValueError("Encoder returned wrong dimensions or non-finite values")
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0 or not math.isfinite(norm):
        raise ValueError("Encoder returned a zero or invalid vector")
    # Classification uses the exact float32 bytes retained for later review.
    return struct.unpack(
        f"<{dimensions}f",
        struct.pack(f"<{dimensions}f", *(value / norm for value in values)),
    )


def timed_batch(
    adapter, paths: list[Path]
) -> tuple[tuple[tuple[float, ...], ...], float]:
    adapter.synchronize()
    started = time.perf_counter()
    rows = tuple(
        tuple(float(value) for value in row) for row in adapter.encode_images(paths)
    )
    adapter.synchronize()
    elapsed = time.perf_counter() - started
    if len(rows) != len(paths):
        raise ValueError(
            "Encoder output count differs from input; refusing ambiguous row assignment"
        )
    return rows, elapsed


def environment() -> dict:
    def command(*args):
        return subprocess.check_output(args, text=True).strip()

    result = {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "pid": os.getpid(),
        "nice": os.getpriority(os.PRIO_PROCESS, 0),
    }
    if sys.platform == "darwin":
        result.update(
            macos=command("sw_vers", "-productVersion"),
            build=command("sw_vers", "-buildVersion"),
            cpu=command("sysctl", "-n", "machdep.cpu.brand_string"),
            unified_memory_bytes=int(command("sysctl", "-n", "hw.memsize")),
        )
    return result


def code_version() -> dict:
    root = Path(__file__).resolve().parents[2]
    names = sorted(
        path.name for path in Path(__file__).parent.glob("model_evaluation*.py")
    ) + ["prepare_input.py"]
    return {
        "git_head": subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip(),
        "working_tree_dirty": bool(
            subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain"], text=True
            )
        ),
        "evaluation_files_sha256": {
            name: digest(Path(__file__).parent / name) for name in names
        },
    }


def check_runtime(config: dict) -> None:
    runtime = config["runtime"]
    if type(runtime["batch_size"]) is not int or runtime["batch_size"] < 1:
        raise ValueError("batch_size must be a positive integer")
    if type(runtime["cpu_threads"]) is not int or runtime["cpu_threads"] < 1:
        raise ValueError("cpu_threads must be a positive integer")
    if platform.python_version() != runtime["python_version"]:
        raise ValueError(f"Use the pinned interpreter: {runtime['python']}")
    for name, expected in runtime["packages"].items():
        if version(name) != expected:
            raise ValueError(
                f"Runtime changed: {name}; expected {expected}, found {version(name)}"
            )
    model = config["model"]
    if model["normalization"] != "unit_length" or model["vector_dtype"] != "float32-le":
        raise ValueError(
            "This recipe stores L2-normalized little-endian float32 vectors"
        )
    snapshot = Path(model["snapshot_path"])
    files = {
        str(path.relative_to(snapshot)): digest(path)
        for path in snapshot.rglob("*")
        if path.is_file() and path.name != ".DS_Store"
    }
    if files != model["files_sha256"]:
        raise ValueError(
            "Actual checkpoint/processor files differ from the pinned model manifest"
        )


def encode(config: dict, inputs_path: Path, output: Path) -> dict:
    output = outside(output, *fixture_roots(config))
    if output.exists():
        raise ValueError(
            "Use a new output directory; speed runs never reuse saved vectors"
        )
    check_runtime(config)
    prepared = validate_inputs(config, inputs_path)
    if config["inputs"].get("mode") == "mediasense_business":
        from model_evaluation_business import check_baseline

        check_baseline(config, prepared)
    output.mkdir(parents=True)
    write_json(output / "config.json", config)
    provenance = code_version()
    rows = [
        {
            "id": row["id"],
            "state": "not_encoded" if row["state"] == "ready" else "input_failed",
            **({"error": row["error"]} if "error" in row else {}),
        }
        for row in prepared["inputs"]
    ]
    ready = [
        (index, row)
        for index, row in enumerate(prepared["inputs"])
        if row["state"] == "ready"
    ]
    summary = {
        "status": "encoding_incomplete",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "inference_fingerprint": inference_fingerprint(config),
        "code": provenance,
        "environment": environment(),
        "inputs_manifest": str(inputs_path.resolve()),
        "input_fingerprint": prepared["input_fingerprint"],
        "source_fingerprint": prepared["source_fingerprint"],
        "model": config["model"],
        "runtime": config["runtime"],
        "counts": {
            "sources": prepared["source_count"],
            "expected_inputs": len(rows),
            "prepared": len(ready),
            "input_failures": len(rows) - len(ready),
        },
        "performance": {
            "model_load_seconds": None,
            "encoding_seconds": 0.0,
            "encoded_inputs": 0,
            "embedding_cache_hits": 0,
            "warmup_inputs": 0,
            "timing_scope": "Every batch includes file read, RGB decode, processor resize/normalize, inference, result materialization on CPU, and device synchronization. No warmup; first batch included. Excludes fixture verification, video extraction, L2 normalization, vector writes, clustering and preview.",
            "load_scope": "Adapter/framework import, model and processor loading, device transfer, readiness and synchronization; weight hashing is preflight, outside load timing.",
            "memory_scope": "Kernel RUSAGE_SELF high-water resident bytes for this encoding PID through completion, including imports, load and encoding; excludes all children and separate preparation/preview processes. Not total system or GPU allocation.",
            "memory_includes_children": False,
        },
    }
    performance = summary["performance"]
    completed = 0
    last_notice = time.monotonic()
    try:
        started = time.perf_counter()
        module, factory = config["model"]["adapter"].split(":")
        adapter = getattr(importlib.import_module(module), factory)(
            config["model"], config["runtime"]
        )
        adapter.load()
        adapter.synchronize()
        performance["model_load_seconds"] = time.perf_counter() - started
        summary["effective_encoder"] = adapter.description
        summary["embedding_identity"] = fingerprint(
            {
                "model": config["model"],
                "runtime": config["runtime"],
                "effective_encoder": adapter.description,
            }
        )
        print(
            f"model loaded in {performance['model_load_seconds']:.3f}s; encoding {len(ready)} inputs",
            flush=True,
        )
        batch_size = config["runtime"]["batch_size"]
        with (output / "vectors.f32").open("xb") as vectors:
            for start in range(0, len(ready), batch_size):
                batch = ready[start : start + batch_size]
                attempted_at = time.perf_counter()
                try:
                    raw, elapsed = timed_batch(
                        adapter, [Path(row["image_path"]) for _, row in batch]
                    )
                except BaseException:
                    performance["encoding_seconds"] += (
                        time.perf_counter() - attempted_at
                    )
                    raise
                performance["encoding_seconds"] += elapsed
                validated = [
                    validate_vector(values, config["model"]["dimensions"])
                    for values in raw
                ]
                for (index, _), vector in zip(batch, validated, strict=True):
                    vectors.write(struct.pack(f"<{len(vector)}f", *vector))
                    rows[index].update(state="encoded", vector_row=completed)
                    completed += 1
                if time.monotonic() - last_notice >= 15:
                    print(
                        f"encoded {completed}/{len(ready)}; {completed / performance['encoding_seconds']:.3f} inputs/s",
                        flush=True,
                    )
                    last_notice = time.monotonic()
        validate_inputs(config, inputs_path)
        if (
            provenance["evaluation_files_sha256"]
            != code_version()["evaluation_files_sha256"]
        ):
            raise ValueError("Evaluation execution code changed during the run")
        summary["status"] = "encoded"
    except BaseException as error:
        summary["status"] = (
            "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        )
        summary["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        performance["encoded_inputs"] = completed
        performance["inputs_per_second"] = (
            completed / performance["encoding_seconds"]
            if performance["encoding_seconds"] and summary["status"] == "encoded"
            else None
        )
        performance["peak_process_rss_bytes"] = resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
        summary["counts"]["encoded"] = completed
        summary["counts"]["not_encoded"] = sum(
            row["state"] == "not_encoded" for row in rows
        )
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(output / "rows.json", rows)
        summary["rows_sha256"] = digest(output / "rows.json")
        summary["vectors_sha256"] = (
            digest(output / "vectors.f32")
            if (output / "vectors.f32").exists()
            else None
        )
        write_json(output / "encoding.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("stage-fixture", "prepare", "encode", "preview", "run")
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--inputs", type=Path, help="Frozen prepared inputs.json (encode/run)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New directory; preview uses the retained encoding directory",
    )
    parser.add_argument(
        "--summary", type=Path, help="New compact summary file (preview/run)"
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    os.environ.update(
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        TOKENIZERS_PARALLELISM="false",
        OMP_NUM_THREADS=str(config["runtime"]["cpu_threads"]),
        OPENBLAS_NUM_THREADS=str(config["runtime"]["cpu_threads"]),
    )
    os.nice(max(0, config["runtime"]["nice"] - os.getpriority(os.PRIO_PROCESS, 0)))
    if args.action in {"encode", "run"} and args.inputs is None:
        parser.error("--inputs is required")
    if args.action in {"preview", "run"}:
        if args.summary is None or args.summary.exists():
            parser.error("--summary must name a new compact summary file")
        outside(args.summary, *fixture_roots(config))
        if config["classification"]["status"] != "confirmed":
            parser.error(
                "The exact Hierarchical method still requires Human confirmation; encode remains available"
            )
    if args.action == "stage-fixture":
        result = stage_fixture(config, args.output)
    elif args.action == "prepare":
        result = prepare_inputs(config, args.output)
    elif args.action in {"encode", "run"}:
        result = encode(config, args.inputs, args.output)
    else:
        result = None
    if args.action in {"preview", "run"}:
        if config["inputs"].get("mode") == "mediasense_business":
            from model_evaluation_business_preview import preview
        else:
            from model_evaluation_preview import preview

        result = preview(config, args.output, args.summary)
    if args.action in {"encode", "preview", "run"}:
        result = {
            "output": str(args.output.resolve()),
            "status": result["status"],
            "counts": result["counts"],
            "performance": result["performance"],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
