"""Convert the pinned DINOv3 CLS graph with the validated precision boundary."""

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
from model_evaluation_dinov3 import image_pixels, load_processor, torch_vision  # noqa: E402
from model_evaluation_inputs import digest, validate_inputs, write_json  # noqa: E402
from validate import compare  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--batches", type=int, nargs="+", default=[1], choices=[1, 2, 4])
    parser.add_argument("--native-tensor-split", action="store_true", help="Reproduce Core ML Tools 9.0's unsupported tensor_split failure")
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TOKENIZERS_PARALLELISM="false")
    os.nice(max(0, config["runtime"]["nice"] - os.getpriority(os.PRIO_PROCESS, 0)))
    check_runtime(config)
    prepared = validate_inputs(config, args.inputs)
    reference = json.loads((args.reference / "validation.json").read_text())
    if reference["status"] != "passed" or reference["input_fingerprint"] != prepared["input_fingerprint"]:
        raise ValueError("A passing matching CPU/MPS reference is required")
    by_id = {row["id"]: row for row in prepared["inputs"]}
    samples = reference["samples"][:4]
    selected = [by_id[row["id"]] for row in samples]
    if any(row["image_sha256"] != sample["image_sha256"] for row, sample in zip(selected, samples, strict=True)):
        raise ValueError("Reference input bytes changed")
    args.output.mkdir(parents=True, exist_ok=False)
    args.evidence.mkdir(parents=True, exist_ok=False)
    batches = sorted(set(args.batches))
    precision = "FP16 convolution/MLP graph; FP32 attention, normalization, residuals and RoPE; FP32 I/O"
    result = {"status": "incomplete", "input_fingerprint": prepared["input_fingerprint"], "source_checkpoint_sha256": config["model"]["files_sha256"]["model.safetensors"], "precision": precision, "native_batch_sizes": batches, "timings": {}}
    try:
        import coremltools as ct
        import numpy as np
        import torch
        from coremltools.converters.mil.mil.scope import ScopeSource

        started = time.perf_counter()
        model = torch_vision(config["model"], {**config["runtime"], "device": "cpu", "precision": "float32"})
        pixels = image_pixels(load_processor(config["model"]), [Path(row["image_path"]) for row in selected])
        result["timings"]["source_load_and_example_seconds"] = time.perf_counter() - started

        class CLS(torch.nn.Module):
            def __init__(self, encoder):
                super().__init__()
                self.encoder = encoder

            def forward(self, pixel_values):
                return self.encoder.forward_features(pixel_values)[:, 0, :]

        wrapper = CLS(model).eval()
        started = time.perf_counter()
        print(f"tracing CLS graph for native batches {batches}", flush=True)
        import timm.models.eva as eva
        from timm.layers.pos_embed_sincos import rope_rotate_half, rot

        original_rope = eva.apply_rot_embed_cat

        def export_rope(x, embedding, half=False):
            # tensor_split(2) and chunk(2) are identical for the fixed, even
            # 128-wide sin/cos embedding. No RoPE values or math are changed.
            if embedding.shape[-1] != 128:
                raise ValueError("Export rewrite only covers DINOv3 B/16's 128-wide RoPE")
            sine, cosine = embedding.chunk(2, dim=-1)
            return x * cosine + (rope_rotate_half(x) if half else rot(x)) * sine

        try:
            if not args.native_tensor_split:
                eva.apply_rot_embed_cat = export_rope
            with torch.inference_mode():
                traced = torch.jit.trace(wrapper, pixels[:batches[0]], check_inputs=[(pixels[:batch],) for batch in batches] + [(pixels[-1:],)])
                traced_output = traced(pixels).numpy()
        finally:
            eva.apply_rot_embed_cat = original_rope
        result["export_compatibility"] = "native tensor_split" if args.native_tensor_split else "RoPE tensor_split(2,-1) replaced by chunk(2,-1) at fixed width 128; process-local tracing only"
        result["timings"]["trace_and_checks_seconds"] = time.perf_counter() - started
        with np.load(args.reference / "features.npz") as features:
            result["trace_vs_cpu_fp32"] = compare(features["cpu_fp32"][:4], traced_output)

        selection = Counter()

        def lower_to_fp16(operation):
            scope = "/".join(operation.scopes.get(ScopeSource.TORCHSCRIPT_MODULE_NAME, []))
            lower = "patch_embed" in scope or "mlp" in scope
            selection["fp16" if lower else "keep_fp32"] += 1
            return lower

        shapes = [(batch, 3, 512, 512) for batch in batches]
        shape = shapes[0] if len(shapes) == 1 else ct.EnumeratedShapes(shapes=shapes, default=shapes[0])
        print("converting: FP16 convolution/MLP, FP32 attention/residuals", flush=True)
        started = time.perf_counter()
        converted = ct.convert(
            traced, convert_to="mlprogram",
            inputs=[ct.TensorType(name="pixel_values", shape=shape, dtype=np.float32)],
            outputs=[ct.TensorType(name="image_features", dtype=np.float32)],
            compute_precision=ct.transform.FP16ComputePrecision(op_selector=lower_to_fp16),
            minimum_deployment_target=ct.target.macOS15, skip_model_load=True,
        )
        result["timings"]["conversion_seconds"] = time.perf_counter() - started
        if not selection["fp16"] or not selection["keep_fp32"]:
            raise ValueError("Precision selection did not establish both required scopes")
        result["precision_selection_counts"] = dict(selection)
        types, attention_types, ops = Counter(), Counter(), Counter()
        for function in converted._mil_program.functions.values():
            for operation in function.operations:
                if operation.op_type == "const":
                    continue
                ops[operation.op_type] += 1
                scope = "/".join(operation.scopes.get(ScopeSource.TORCHSCRIPT_MODULE_NAME, []))
                for value in operation.outputs:
                    dtype = value.dtype.__name__
                    if dtype in {"fp16", "fp32"}:
                        types[dtype] += 1
                        if "attn" in scope and operation.op_type in {"linear", "matmul", "softmax", "scaled_dot_product_attention"}:
                            attention_types[dtype] += 1
        if attention_types["fp16"] or not attention_types["fp32"]:
            raise ValueError(f"Attention precision boundary was not preserved: {attention_types}")
        result.update(nonconstant_float_output_types=dict(types), attention_compute_output_types=dict(attention_types), operation_counts=dict(ops))
        converted.short_description = "DINOv3 ViT-B/16 CLS at 512px; FP16 conv/MLP, FP32 attention/residuals"
        converted.user_defined_metadata["source_revision"] = config["model"]["revision"]
        converted.user_defined_metadata["source_checkpoint_sha256"] = result["source_checkpoint_sha256"]
        started = time.perf_counter()
        converted.save(str(args.output / "vision.mlpackage"))
        result["timings"]["save_seconds"] = time.perf_counter() - started
        shutil.copyfile(Path(config["model"]["snapshot_path"]) / "config.json", args.output / "source-config.json")
        started = time.perf_counter()
        print("compiling model package", flush=True)
        ct.models.utils.compile_model(str(args.output / "vision.mlpackage"), destination_path=str(args.output / "vision.mlmodelc"))
        result["timings"]["compile_seconds"] = time.perf_counter() - started
        result["files_sha256"] = {str(path.relative_to(args.output)): digest(path) for path in sorted(args.output.rglob("*")) if path.is_file()}
        candidate = deepcopy(config)
        candidate["model"].update(adapter="model_evaluation_dinov3:DinoV3CoreMLAdapter", snapshot_path=str(args.output.resolve()), files_sha256=result["files_sha256"], source_checkpoint_sha256=result["source_checkpoint_sha256"], native_batch_sizes=batches, graph_precision=precision)
        candidate["runtime"].update(device="coreml", compute_units="ALL", batch_size=batches[0], profile_note=precision + "; allowed compute units ALL, actual dispatch unmeasured; no padding")
        candidate["runtime"].pop("parameter_precision", None)
        write_json(args.evidence / "config-coreml.json", candidate)
        result["status"] = "converted_and_compiled; numerical validation pending"
    except BaseException as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["conversion_process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write_json(args.evidence / "conversion.json", result)
    print(json.dumps({"status": result["status"], "timings": result["timings"]}, indent=2))


if __name__ == "__main__":
    main()
