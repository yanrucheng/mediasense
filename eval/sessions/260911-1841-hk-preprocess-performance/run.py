"""Reproducible, local-only EXIF/video comparison on the owner-selected copy."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time


SESSION = Path(__file__).resolve().parent
CONFIG = json.loads((SESSION / "config.json").read_text())
OUTPUTS = SESSION / "outputs"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def source_state(root):
    rows = []
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            if (Path(folder) / name).is_symlink():
                raise ValueError("Source contains a symlink; review its boundary first")
        for name in files:
            path = Path(folder) / name
            before = path.stat()
            sha = digest(path)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (
                after.st_size,
                after.st_mtime_ns,
            ):
                raise ValueError(f"Source changed while hashing: {path}")
            rows.append(
                {
                    "path": str(path.relative_to(root)),
                    "bytes": after.st_size,
                    "mtime_ns": after.st_mtime_ns,
                    "sha256": sha,
                }
            )
    return sorted(rows, key=lambda row: row["path"])


def inventory():
    root = Path(CONFIG["source_root"])
    package = Path(CONFIG["package"])
    manifest = package / "manifests/media-manifest.jsonl"
    expected_manifest = (
        "f56caa6b1f1dd56e1b02850a5bfc17567d11f5617899db166eb8d670889d67fe"
    )
    if digest(package / "manifests/SHA256SUMS") != expected_manifest:
        raise ValueError("Versioned checksum manifest changed")
    verification = (OUTPUTS / "package-verification.log").read_text()
    if "all listed files match SHA-256" not in verification:
        raise ValueError("Run the package verifier before trusting the manifest")
    state = source_state(root)
    by_path = {row["path"]: row for row in state}
    rows = [json.loads(line) for line in manifest.read_text().splitlines()]
    for index, row in enumerate(rows):
        observed = by_path[row["path"]]
        if observed["sha256"] != row["derived_sha256"]:
            raise ValueError(f"Test copy differs from manifest: {row['path']}")
        row["index"] = index
        row["observed_bytes"] = observed["bytes"]
    write_json(OUTPUTS / "inputs.json", rows)
    write_json(OUTPUTS / "source-state-before.json", state)
    transforms = Counter(row["transform"] for row in rows)
    summary = {
        "source_root": str(root),
        "source_files": len(state),
        "source_bytes": sum(row["bytes"] for row in state),
        "manifest_media": len(rows),
        "media_bytes": sum(row["observed_bytes"] for row in rows),
        "media_types": dict(Counter(row["media_type"] for row in rows)),
        "transforms": dict(transforms),
        "all_test_media_match_versioned_sha256": True,
        "source_state_sha256": digest(OUTPUTS / "source-state-before.json"),
        "package_verifier": {
            "listed_sha256": "passed",
            "whole_package": "failed_size_limit"
            if "limit is 2000000000" in verification
            else "see_log",
        },
        "platform": platform.platform(),
        "tools": {},
    }
    for tool in ("exiftool", "ffmpeg", "ffprobe"):
        summary["tools"][tool] = subprocess.check_output(
            [tool, "-ver" if tool == "exiftool" else "-version"], text=True
        ).splitlines()[0]
    write_json(SESSION / "metrics/inventory.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def execute(case, mode, *, legacy=False, reuse=False, limit=None, workers=1):
    directory = OUTPUTS / case
    directory.mkdir(parents=True, exist_ok=True)
    suffix = "reuse" if reuse else "fresh"
    result = directory / f"{suffix}.json"
    if result.exists():
        raise FileExistsError(
            f"Refusing to overwrite a completed measurement: {result}"
        )
    python = CONFIG["legacy_python" if legacy else "current_python"]
    command = [
        python,
        str(SESSION / "worker.py"),
        "--mode",
        mode,
        "--case",
        case,
        "--workers",
        str(workers),
    ]
    if reuse:
        command.append("--reuse")
    if limit is not None:
        command.extend(("--limit", str(limit)))
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT"}
    }
    environment.update(
        PYTHONDONTWRITEBYTECODE="1",
        PYTHONUNBUFFERED="1",
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        TOKENIZERS_PARALLELISM="false",
    )
    start = time.perf_counter()
    with (directory / f"{suffix}.log").open("x") as log:
        completed = subprocess.run(
            command,
            env=environment,
            cwd=OUTPUTS,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=1800,
        )
    outer_seconds = time.perf_counter() - start
    if completed.returncode:
        raise RuntimeError(f"{case}/{suffix} failed; see its retained log")
    value = json.loads(result.read_text())
    value["outer_process_seconds"] = outer_seconds
    value["command"] = command
    write_json(result, value)
    print(
        json.dumps(
            {
                "case": case,
                "pass": suffix,
                "seconds": value["seconds"],
                "success": value.get("success"),
                "failures": value.get("failures"),
                "process_starts": value.get("process_starts"),
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def run_suite():
    # Kernel comparisons alternate order to expose order/system-cache effects.
    for repeat in range(CONFIG["kernel_repeats"]):
        variants = ["legacy", "current"]
        if repeat % 2:
            variants.reverse()
        for variant in variants:
            execute(
                f"exif-kernel-{variant}-{repeat + 1}",
                f"exif-{variant}",
                legacy=True,
            )
    execute("exif-legacy-sequential", "exif-legacy", legacy=True, workers=-1)
    execute("exif-legacy-with-invalid", "exif-legacy-all", legacy=True)
    execute("metadata-producer", "metadata-producer")
    execute("metadata-producer", "metadata-producer", reuse=True)
    execute("video-probes", "video-probes", workers=4)
    for repeat in range(CONFIG["kernel_repeats"]):
        variants = ["legacy", "current"]
        if repeat % 2:
            variants.reverse()
        for variant in variants:
            execute(
                f"video-common-{variant}-{repeat + 1}",
                f"video-common-{variant}",
                legacy=True,
            )
    execute("video-native-legacy", "video-native-legacy", legacy=True)
    execute("video-native-legacy", "video-native-legacy", legacy=True, reuse=True)
    execute("video-native-current", "video-native-current", workers=4)
    execute("video-native-current", "video-native-current", workers=4, reuse=True)


def summarize():
    values = []
    for path in sorted(OUTPUTS.glob("*/*.json")):
        if path.name not in {"fresh.json", "reuse.json"} or path.parent.name.startswith(
            "pilot"
        ):
            continue
        value = json.loads(path.read_text())
        value["record"] = str(path.relative_to(SESSION))
        value.pop("rows", None)
        value.pop("raw_values", None)
        values.append(value)
    groups = {}
    for family in (
        "exif-kernel-legacy",
        "exif-kernel-current",
        "video-common-legacy",
        "video-common-current",
    ):
        samples = [v["seconds"] for v in values if v["case"].startswith(family)]
        if samples:
            groups[family] = {
                "n": len(samples),
                "seconds": samples,
                "median_seconds": statistics.median(samples),
                "min_seconds": min(samples),
                "max_seconds": max(samples),
            }
    state = source_state(Path(CONFIG["source_root"]))
    write_json(OUTPUTS / "source-state-after.json", state)
    before = json.loads((OUTPUTS / "source-state-before.json").read_text())
    if state != before:
        raise ValueError("Source bytes, sizes, timestamps or paths changed")
    result = {"groups": groups, "measurements": values, "source_unchanged": True}
    write_json(SESSION / "metrics/combined.json", result)
    print(json.dumps({"groups": groups, "source_unchanged": True}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inventory", "run", "summarize", "case"))
    parser.add_argument("--case")
    parser.add_argument("--mode")
    parser.add_argument("--legacy", action="store_true")
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.action == "inventory":
        inventory()
    elif args.action == "run":
        run_suite()
    elif args.action == "summarize":
        summarize()
    else:
        execute(
            args.case,
            args.mode,
            legacy=args.legacy,
            reuse=args.reuse,
            limit=args.limit,
            workers=args.workers,
        )


if __name__ == "__main__":
    main()
