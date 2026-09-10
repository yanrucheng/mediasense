"""One FP16 image-tower conversion with batch 1/2/4; no model search."""

from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import resource
import shutil
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
from model_evaluation import check_runtime  # noqa: E402
from model_evaluation_inputs import digest, validate_inputs, write_json  # noqa: E402
from model_evaluation_siglip2 import image_pixels, load_processor, torch_vision  # noqa: E402
from validate import compare  # noqa: E402


def compute_plan(path):
    import coremltools as ct

    plan = ct.models.compute_plan.MLComputePlan.load_from_path(str(path), ct.ComputeUnit.ALL)
    preferred, supported, operations = Counter(), Counter(), Counter()

    def visit(block):
        for operation in block.operations:
            operations[operation.operator_name] += 1
            usage = plan.get_compute_device_usage_for_mlprogram_operation(operation)
            preferred[type(usage.preferred_compute_device).__name__ if usage else "unknown"] += 1
            if usage:
                supported.update(type(device).__name__ for device in usage.supported_compute_devices)
            for nested in operation.blocks:
                visit(nested)

    for function in plan.model_structure.program.functions.values():
        visit(function.block)
    return {"compute_units": "ALL", "preferred_device_operation_counts": dict(preferred), "supported_device_operation_counts": dict(supported), "operations": dict(operations), "actual_execution_trace": False, "limitation": "Static compute plan, not measured per-operation dispatch or elapsed time."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New model artifact directory")
    parser.add_argument("--evidence", type=Path, required=True, help="New diagnostic directory")
    parser.add_argument("--fixed-batch", action="store_true", help="Diagnostic reproduction of the failed static batch-4 attempt")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
    os.nice(max(0, config["runtime"]["nice"] - os.getpriority(os.PRIO_PROCESS, 0)))
    check_runtime(config)
    prepared = validate_inputs(config, args.inputs)
    reference = json.loads((args.reference / "validation.json").read_text())
    if reference["status"] != "passed" or reference["input_fingerprint"] != prepared["input_fingerprint"]:
        raise ValueError("A passing matching FP32/MPS reference is required")
    by_id = {row["id"]: row for row in prepared["inputs"]}
    selected = [by_id[row["id"]] for row in reference["samples"][:4]]
    if any(row["image_sha256"] != sample["image_sha256"] for row, sample in zip(selected, reference["samples"], strict=False)):
        raise ValueError("Reference input bytes changed")
    args.output.mkdir(parents=True, exist_ok=False)
    args.evidence.mkdir(parents=True, exist_ok=False)
    shapes = [4] if args.fixed_batch else [1, 2, 4]
    result = {"status": "incomplete", "input_fingerprint": prepared["input_fingerprint"], "source_checkpoint_sha256": config["model"]["files_sha256"]["model.safetensors"], "compute_precision": "FLOAT16", "input_output_dtype": "float32", "batch_shapes": shapes, "minimum_deployment_target": "macOS15", "timings": {}}
    try:
        import coremltools as ct
        import numpy as np
        import torch

        result.update(coremltools=ct.__version__, torch=torch.__version__)
        runtime = {**config["runtime"], "device": "cpu", "precision": "float32"}
        started = time.perf_counter()
        vision, _, _ = torch_vision(config["model"], runtime)
        processor = load_processor(config["model"])
        pixels = torch.from_numpy(image_pixels(processor, [Path(row["image_path"]) for row in selected]))
        result["timings"]["source_load_and_example_seconds"] = time.perf_counter() - started

        class ImageTower(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.vision = vision.vision_model

            def forward(self, pixel_values):
                return self.vision(pixel_values).pooler_output

        wrapper = ImageTower().eval()
        print("tracing official image tower, checking batches 1/2/4", flush=True)
        started = time.perf_counter()
        with torch.no_grad():
            traced = torch.jit.trace(wrapper, pixels, check_inputs=[(pixels[:1],), (pixels[:2],)])
            traced_output = traced(pixels).numpy()
        result["timings"]["trace_and_checks_seconds"] = time.perf_counter() - started
        with np.load(args.reference / "features.npz") as features:
            result["trace_vs_cpu_fp32"] = compare(features["cpu_fp32"][:4], traced_output)
        print("converting FP16 ML Program", flush=True)
        started = time.perf_counter()
        model = ct.convert(
            traced,
            convert_to="mlprogram",
            inputs=[ct.TensorType(name="pixel_values", shape=(4, 3, 512, 512) if args.fixed_batch else ct.EnumeratedShapes(shapes=[(1, 3, 512, 512), (2, 3, 512, 512), (4, 3, 512, 512)], default=(4, 3, 512, 512)), dtype=np.float32)],
            outputs=[ct.TensorType(name="image_features", dtype=np.float32)],
            compute_precision=ct.precision.FLOAT16,
            minimum_deployment_target=ct.target.macOS15,
            skip_model_load=True,
        )
        result["timings"]["conversion_seconds"] = time.perf_counter() - started
        floating = Counter()
        for function in model._mil_program.functions.values():
            for operation in function.operations:
                if operation.op_type != "const":
                    floating.update(value.dtype.__name__ for value in operation.outputs if value.dtype.__name__ in {"fp16", "fp32"})
        result["nonconstant_float_output_types"] = dict(floating)
        model.short_description = f"SigLIP 2 So400m-512 official vision pooler; FP16; batches {shapes}"
        model.user_defined_metadata["source_revision"] = config["model"]["revision"]
        model.user_defined_metadata["source_checkpoint_sha256"] = result["source_checkpoint_sha256"]
        started = time.perf_counter()
        model.save(str(args.output / "vision.mlpackage"))
        result["timings"]["save_seconds"] = time.perf_counter() - started
        for name in ("config.json", "preprocessor_config.json"):
            shutil.copyfile(Path(config["model"]["snapshot_path"]) / name, args.output / name)
        print("compiling model separately from evaluation load/encoding", flush=True)
        started = time.perf_counter()
        ct.models.utils.compile_model(str(args.output / "vision.mlpackage"), destination_path=str(args.output / "vision.mlmodelc"))
        result["timings"]["compile_seconds"] = time.perf_counter() - started
        result["compute_plan"] = compute_plan(args.output / "vision.mlmodelc")
        result["files_sha256"] = {str(path.relative_to(args.output)): digest(path) for path in sorted(args.output.rglob("*")) if path.is_file()}
        candidate = deepcopy(config)
        candidate["model"].update(adapter="model_evaluation_siglip2:Siglip2CoreMLAdapter", snapshot_path=str(args.output.resolve()), files_sha256=result["files_sha256"], source_checkpoint_sha256=result["source_checkpoint_sha256"], batch_shapes=shapes)
        candidate["runtime"].update(device="coreml", compute_units="ALL", profile_note="Core ML FP16 graph, float32 I/O; actual device scheduling unmeasured. " + ("Static batch 4; final batch 2 repeats its last real input, discarding 2 padding outputs (368 forward rows for 366 real inputs)." if args.fixed_batch else "Flexible batches 1/2/4, no padding."))
        if not args.fixed_batch:
            # The original flexible graph is correct only with native batch 1 on
            # this tested stack; never emit a default profile that uses batch 4.
            candidate["model"]["prediction_batch_size"] = 1
            candidate["runtime"].update(batch_size=1, profile_note="Core ML FP16; native single-image predictions only. Native batch 2/4 failed correctness. No padding; compute units ALL; actual scheduling unmeasured.")
        write_json(args.evidence / "config-coreml.json", candidate)
        result["status"] = "converted_and_compiled; numerical validation pending"
    except BaseException as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["conversion_process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write_json(args.evidence / "conversion.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
