"""Small, fixed real-image checks; not a second business evaluation runner."""

from __future__ import annotations

import argparse
from copy import deepcopy
import gc
import importlib
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
from model_evaluation import check_runtime, timed_batch, validate_vector  # noqa: E402
from model_evaluation_inputs import validate_inputs, write_json  # noqa: E402


def normalized(raw):
    import numpy as np

    return np.asarray([validate_vector(row, 1152) for row in raw], dtype=np.float64)


def compare(reference, candidate):
    import numpy as np

    a, b = normalized(reference), normalized(candidate)
    aa, bb = a @ a.T, b @ b.T
    pair_error = float(np.max(np.abs(aa - bb)))
    np.fill_diagonal(aa, -np.inf)
    np.fill_diagonal(bb, -np.inf)
    ranks_a, ranks_b = np.argsort(-aa, axis=1), np.argsort(-bb, axis=1)
    inversions = 0
    for row in range(len(a)):
        indices = [i for i in range(len(a)) if i != row]
        for i, left in enumerate(indices):
            for right in indices[i + 1 :]:
                gap = aa[row, left] - aa[row, right]
                if abs(gap) > 0.005 and gap * (bb[row, left] - bb[row, right]) < 0:
                    inversions += 1
    result = {
        "rows": len(a),
        "dimensions": a.shape[1],
        "max_cosine_distance": float(np.max(np.maximum(0, 1 - np.sum(a * b, axis=1)))),
        "max_pairwise_cosine_error": pair_error,
        "max_normalized_element_error": float(np.max(np.abs(a - b))),
        "max_raw_relative_l2_error": float(np.max(np.linalg.norm(reference - candidate, axis=1) / np.linalg.norm(reference, axis=1))),
        "nearest_neighbor_agreement": int(np.sum(ranks_a[:, 0] == ranks_b[:, 0])),
        "changed_rank_positions": int(np.sum(ranks_a != ranks_b)),
        "inversions_with_reference_margin_over_0_005": inversions,
        "max_stored_unit_norm_error": float(np.max(np.abs(np.linalg.norm(b, axis=1) - 1))),
    }
    if result["max_cosine_distance"] > 0.001 or pair_error > 0.002:
        raise ValueError(f"Predeclared numerical tolerance failed: {result}")
    if inversions:
        raise ValueError(f"Material similarity-order inversion: {result}")
    return result


def exercise(config, paths, check_official=False, raw_output=None):
    import numpy as np

    module, name = config["model"]["adapter"].split(":")
    adapter = getattr(importlib.import_module(module), name)(config["model"], config["runtime"])
    started = time.perf_counter()
    adapter.load()
    adapter.synchronize()
    load_seconds = time.perf_counter() - started
    batches = [timed_batch(adapter, paths[start : start + 4]) for start in range(0, len(paths), 4)]
    batch = np.asarray([row for values, _ in batches for row in values])
    singleton = np.asarray([timed_batch(adapter, [path])[0][0] for path in paths])
    permutation = [7, 0, 5, 2, 6, 1, 4, 3]
    permuted = np.asarray([row for start in range(0, len(paths), 4) for row in timed_batch(adapter, [paths[i] for i in permutation[start : start + 4]])[0]])
    pair = np.asarray(timed_batch(adapter, paths[-2:])[0])
    if raw_output is not None:
        np.savez(raw_output, batch=batch, singleton=singleton, permuted=permuted, pair=pair)
    checks = {
        "single_vs_batch4": compare(batch, singleton),
        "permuted_vs_original": compare(batch[permutation], permuted),
        "final_batch2_vs_batch4": compare(batch[-2:], pair),
        "description": adapter.description,
        "probe_timing": {"load_seconds": load_seconds, "first_batch_seconds": batches[0][1], "scope": "Correctness probe only; separate from full business performance."},
    }
    if check_official:
        import torch
        from transformers import SiglipModel
        from model_evaluation_siglip2 import image_pixels

        # Invoke the actual official method with just its required vision submodule.
        # No text tower is instantiated or run.
        pixels = torch.from_numpy(image_pixels(adapter.processor, paths[:4]))
        with torch.inference_mode():
            official = SiglipModel.get_image_features(
                SimpleNamespace(vision_model=adapter.encoder.vision_model),
                pixel_values=pixels,
            ).numpy()
        checks["official_get_image_features"] = compare(batch[:4], official)
        if not np.array_equal(batch[:4], official):
            raise ValueError("CPU adapter does not exactly match official get_image_features")
    del adapter
    gc.collect()
    if config["runtime"]["device"] == "mps":
        import torch

        torch.mps.empty_cache()
    return batch, checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("torch", "coreml"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reference", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", PYTORCH_ENABLE_MPS_FALLBACK="0", TOKENIZERS_PARALLELISM="false")
    os.nice(max(0, config["runtime"]["nice"] - os.getpriority(os.PRIO_PROCESS, 0)))
    check_runtime(config)
    prepared = validate_inputs(config, args.inputs)
    selected = []
    for kind in ("image", "video"):
        rows = [row for row in prepared["inputs"] if row["state"] == "ready" and row["kind"] == kind]
        selected.extend(rows[i] for i in (0, len(rows) // 3, 2 * len(rows) // 3, len(rows) - 1))
    paths = [Path(row["image_path"]) for row in selected]
    samples = [{key: row[key] for key in ("id", "kind", "image_sha256")} for row in selected]
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"status": "incomplete", "input_fingerprint": prepared["input_fingerprint"], "samples": samples, "tolerances": {"max_cosine_distance": 0.001, "max_pairwise_cosine_error": 0.002, "material_rank_margin": 0.005}, "checks": {}}
    import numpy as np

    try:
        if args.phase == "torch":
            outputs = {}
            for label, device, precision in [("cpu_fp32", "cpu", "float32"), ("mps_fp32", "mps", "float32"), ("mps_fp16", "mps", "float16")]:
                variant = deepcopy(config)
                variant["runtime"].update(device=device, precision=precision)
                print(f"checking {label}", flush=True)
                outputs[label], result["checks"][label] = exercise(variant, paths, check_official=label == "cpu_fp32", raw_output=args.output / f"{label}-batches.npz")
                np.savez(args.output / "features.npz", **outputs)
                if label != "cpu_fp32":
                    result["checks"][label + "_vs_cpu_fp32"] = compare(outputs["cpu_fp32"], outputs[label])
                write_json(args.output / f"{label}.json", result["checks"][label])
        else:
            if args.reference is None:
                raise ValueError("Core ML checks require the retained torch reference")
            reference_meta = json.loads((args.reference / "validation.json").read_text())
            if reference_meta["status"] != "passed" or reference_meta["samples"] != samples:
                raise ValueError("Reference samples or validation status differ")
            features, result["checks"]["coreml_fp16"] = exercise(config, paths, raw_output=args.output / "batch-checks.npz")
            np.savez(args.output / "features.npz", coreml_fp16=features)
            with np.load(args.reference / "features.npz") as reference:
                for label in ("cpu_fp32", "mps_fp16"):
                    result["checks"]["coreml_vs_" + label] = compare(reference[label], features)
        validate_inputs(config, args.inputs)
        result["status"] = "passed"
    except BaseException as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        write_json(args.output / "validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
