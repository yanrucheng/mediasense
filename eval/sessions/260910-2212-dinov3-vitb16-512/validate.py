"""Fixed real-input numerical checks for the selected DINOv3 implementation."""

from __future__ import annotations

import argparse
from copy import deepcopy
import gc
import importlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
from model_evaluation import check_runtime, timed_batch, validate_vector  # noqa: E402
from model_evaluation_inputs import validate_inputs, write_json  # noqa: E402

TOLERANCES = {
    "max_cosine_distance": 0.001,
    "max_pairwise_cosine_error": 0.002,
    "material_rank_margin": 0.005,
    "max_stored_unit_norm_error": 1e-6,
}


def normalized(raw):
    import numpy as np

    return np.asarray([validate_vector(row, 768) for row in raw], dtype=np.float64)


def compare(reference, candidate, *, enforce=True):
    import numpy as np

    reference, candidate = np.asarray(reference), np.asarray(candidate)
    if reference.shape != candidate.shape:
        raise ValueError("Reference/candidate row mapping or dimension differs")
    a, b = normalized(reference), normalized(candidate)
    # Non-BLAS reference avoids spurious Accelerate floating-point warnings;
    # the retained arithmetic check independently compares both implementations.
    aa = np.einsum("ik,jk->ij", a, a, optimize=False)
    bb = np.einsum("ik,jk->ij", b, b, optimize=False)
    if not np.isfinite(aa).all() or not np.isfinite(bb).all():
        raise ValueError("Nonfinite similarity matrix")
    pair_error = np.abs(aa - bb)
    upper = np.triu_indices(len(a), 1)
    pair_values = pair_error[upper]
    np.fill_diagonal(aa, -np.inf)
    np.fill_diagonal(bb, -np.inf)
    ranks_a, ranks_b = np.argsort(-aa, axis=1), np.argsort(-bb, axis=1)
    inversions = 0
    for row in range(len(a)):
        indices = np.flatnonzero(np.arange(len(a)) != row)
        for i, left in enumerate(indices):
            rest = indices[i + 1:]
            gap = aa[row, left] - aa[row, rest]
            inversions += int(np.sum((np.abs(gap) > TOLERANCES["material_rank_margin"]) & (gap * (bb[row, left] - bb[row, rest]) < 0)))
    result = {
        "rows": len(a), "dimensions": a.shape[1],
        "max_cosine_distance": float(np.max(np.maximum(0, 1 - np.sum(a * b, axis=1)))),
        "max_pairwise_cosine_error": float(np.max(pair_error)),
        "pairwise_pairs": len(pair_values),
        "pairwise_over_tolerance": int(np.sum(pair_values > TOLERANCES["max_pairwise_cosine_error"])),
        "max_normalized_element_error": float(np.max(np.abs(a - b))),
        "max_raw_relative_l2_error": float(np.max(np.linalg.norm(reference - candidate, axis=1) / np.linalg.norm(reference, axis=1))),
        "nearest_neighbor_agreement": int(np.sum(ranks_a[:, 0] == ranks_b[:, 0])),
        "changed_rank_positions": int(np.sum(ranks_a != ranks_b)),
        "inversions_with_reference_margin_over_0_005": inversions,
        "max_stored_unit_norm_error": float(np.max(np.abs(np.linalg.norm(b, axis=1) - 1))),
    }
    result["passed"] = all(result[key] <= limit for key, limit in TOLERANCES.items() if key != "material_rank_margin") and not inversions
    if enforce and not result["passed"]:
        raise ValueError(f"Predeclared numerical tolerance failed: {result}")
    return result


def exercise(config, paths, output, reference_checks=False):
    import numpy as np

    module, name = config["model"]["adapter"].split(":")
    adapter = getattr(importlib.import_module(module), name)(config["model"], config["runtime"])
    adapter.load()
    adapter.synchronize()
    execution_dtypes = {}
    handles = []
    if config["runtime"]["device"] != "coreml":
        def capture(name):
            def hook(module, args, value):
                execution_dtypes[name] = {"dtype": str(value.dtype), "device": value.device.type}
            return hook
        for name, module in adapter.encoder.named_modules():
            if name in {"patch_embed.proj", "blocks.0", "blocks.0.norm1", "blocks.0.attn.attention.qkv", "blocks.0.mlp.fc1", "blocks.0.mlp.fc2"}:
                handles.append(module.register_forward_hook(capture(name)))

    def encode(values, encoder_adapter=adapter):
        return np.asarray(timed_batch(encoder_adapter, values)[0])

    batch = np.concatenate([encode(paths[i:i + 4]) for i in range(0, len(paths), 4)])
    for handle in handles:
        handle.remove()
    singleton = np.concatenate([encode([path]) for path in paths])
    permutation = [7, 0, 5, 2, 6, 1, 4, 3]
    permuted = np.concatenate([encode([paths[i] for i in permutation[start:start + 4]]) for start in (0, 4)])
    tail = encode(paths[-2:])
    duplicate_ids = [2, 2, 5, 2]
    duplicate = encode([paths[i] for i in duplicate_ids])
    np.savez(output, batch=batch, singleton=singleton, permuted=permuted, tail=tail, duplicate=duplicate)
    checks = {
        "single_vs_batch4": compare(batch, singleton),
        "reordered": compare(batch[permutation], permuted),
        "final_batch2": compare(batch[-2:], tail),
        "duplicate_slots": compare(batch[duplicate_ids], duplicate),
        "description": adapter.description,
        "observed_execution_dtypes": execution_dtypes,
    }
    if reference_checks:
        import torch
        from PIL import Image
        from torchvision.transforms import v2
        from model_evaluation_dinov3 import image_pixels

        pixels = image_pixels(adapter.processor, paths[:4])
        meta_transform = v2.Compose([
            v2.ToImage(), v2.Resize((512, 512), antialias=True),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=(.485, .456, .406), std=(.229, .224, .225)),
        ])
        expected_pixels = []
        for path in paths[:4]:
            with Image.open(path) as image:
                with image.convert("RGB") as rgb:
                    expected_pixels.append(meta_transform(rgb))
        if not torch.equal(pixels, torch.stack(expected_pixels)):
            raise ValueError("Preprocessing differs from Meta README make_transform(512)")
        with torch.inference_mode():
            tokens = adapter.encoder.forward_features(pixels)
            direct = adapter.encoder(pixels)
        if tokens.shape != (4, 1029, 768):
            raise ValueError("Expected CLS + 4 register + 1024 patch tokens")
        if not np.array_equal(batch[:4], tokens[:, 0, :].numpy()) or not np.array_equal(batch[:4], direct.numpy()):
            raise ValueError("Adapter does not exactly match the selected timm CLS path")
        checks["reference_feature_semantics"] = {
            "meta_preprocessing_equal": True,
            "token_shape": list(tokens.shape),
            "direct_cls_and_token_pool_exact": True,
            "equal_to_patch_average": bool(np.array_equal(batch[:4], tokens[:, 5:, :].mean(1).numpy())),
            "meta_checkpoint_numerical_equivalence": "unverified; gated official checkpoint unavailable",
        }
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
    result = {"status": "incomplete", "input_fingerprint": prepared["input_fingerprint"], "samples": samples, "tolerances": TOLERANCES, "checks": {}}
    import numpy as np

    try:
        if args.phase == "torch":
            outputs = {}
            for label, device, precision in [("cpu_fp32", "cpu", "float32"), ("mps_fp32", "mps", "float32"), ("mps_fp16", "mps", "float16")]:
                variant = deepcopy(config)
                variant["runtime"].update(device=device, precision=precision)
                print(f"checking {label}", flush=True)
                outputs[label], result["checks"][label] = exercise(variant, paths, args.output / f"{label}-batches.npz", reference_checks=label == "cpu_fp32")
                np.savez(args.output / "features.npz", **outputs)
                if label != "cpu_fp32":
                    result["checks"][label + "_vs_cpu_fp32"] = compare(outputs["cpu_fp32"], outputs[label])
        else:
            if args.reference is None:
                raise ValueError("Core ML validation requires the retained CPU/MPS reference")
            reference_meta = json.loads((args.reference / "validation.json").read_text())
            if reference_meta["status"] != "passed" or reference_meta["samples"] != samples:
                raise ValueError("Reference samples or validation status differ")
            features, result["checks"]["coreml"] = exercise(config, paths, args.output / "batches.npz")
            np.savez(args.output / "features.npz", coreml=features)
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
    print(json.dumps({"status": result["status"], "checks": list(result["checks"])}, indent=2))


if __name__ == "__main__":
    main()
