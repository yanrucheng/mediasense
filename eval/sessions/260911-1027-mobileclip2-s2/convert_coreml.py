"""Export the validated fused MobileCLIP2 image tower at fixed batch one."""
import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import resource
import sys
import time

SESSION = Path(__file__).resolve().parent
sys.path.insert(0, str(SESSION.parents[1] / "shared"))
from model_evaluation import check_runtime  # noqa: E402
from model_evaluation_inputs import digest, validate_inputs, write_json  # noqa: E402
from model_evaluation_mobileclip2 import torch_vision, image_pixels, load_processor  # noqa: E402
from validate_mobileclip2 import compare, recipe  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "inputs", "reference", "output", "evidence"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--precision", choices=["float16", "float32"], default="float16")
    args = p.parse_args()
    c = json.loads(args.config.read_text())
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
    os.nice(max(0, c["runtime"]["nice"]-os.getpriority(os.PRIO_PROCESS, 0)))
    check_runtime(c)
    data = validate_inputs(c, args.inputs)
    reference = json.loads((args.reference/"validation.json").read_text())
    if reference["status"] != "passed" or reference["recipe"] != recipe(c) or reference["input_fingerprint"] != data["input_fingerprint"]:
        raise ValueError("A matching passing CPU/MPS reference is required")
    args.output.mkdir(parents=True, exist_ok=False)
    args.evidence.mkdir(parents=True, exist_ok=False)
    result = {"status": "incomplete", "recipe": recipe(c), "timings": {}, "native_batch_sizes": [1], "source_checkpoint_sha256": c["model"]["files_sha256"]["mobileclip2_s2.pt"]}
    try:
        import coremltools as ct
        import numpy as np
        import torch

        start = time.perf_counter()
        model = torch_vision(c["model"], {**c["runtime"], "device": "cpu", "precision": "float32"})
        by_id = {r["id"]:r for r in data["inputs"]}
        pixels = image_pixels(load_processor(c["model"]), [Path(by_id[r["id"]]["image_path"]) for r in reference["samples"][:4]])
        result["timings"]["source_load_and_examples_seconds"] = time.perf_counter()-start
        start = time.perf_counter()
        with torch.inference_mode():
            traced = torch.jit.trace(model, pixels[:1], check_inputs=[(pixels[1:2],)])
            raw = torch.cat([traced(pixels[i:i+1]) for i in range(4)]).numpy()
        with np.load(args.reference/"features.npz") as features:
            result["trace_vs_cpu"] = compare(features["cpu_fp32"][:4], raw)
        result["timings"]["trace_and_checks_seconds"] = time.perf_counter()-start
        start = time.perf_counter()
        converted = ct.convert(traced, convert_to="mlprogram", inputs=[ct.TensorType(name="pixel_values", shape=(1,3,256,256), dtype=np.float32)], outputs=[ct.TensorType(name="image_features", dtype=np.float32)], compute_precision=getattr(ct.precision, args.precision.upper()), minimum_deployment_target=ct.target.macOS15, skip_model_load=True)
        result["timings"]["conversion_seconds"] = time.perf_counter()-start
        converted.short_description = "MobileCLIP2-S2 fused image tower, trained 512-d projection, fixed 256px batch one"
        converted.user_defined_metadata["source_checkpoint_sha256"] = result["source_checkpoint_sha256"]
        start = time.perf_counter()
        converted.save(str(args.output/"vision.mlpackage"))
        result["timings"]["save_seconds"] = time.perf_counter()-start
        start = time.perf_counter()
        ct.models.utils.compile_model(str(args.output/"vision.mlpackage"), destination_path=str(args.output/"vision.mlmodelc"))
        result["timings"]["compile_seconds"] = time.perf_counter()-start
        result["files_sha256"] = {str(p.relative_to(args.output)):digest(p) for p in args.output.rglob('*') if p.is_file()}
        candidate = deepcopy(c)
        graph_precision = f"{args.precision} graph, FP32 input/output, CPU FP32 source reparameterization"
        result["graph_precision"] = graph_precision
        candidate["model"].update(adapter="model_evaluation_mobileclip2:MobileCLIP2CoreMLAdapter", snapshot_path=str(args.output.resolve()), files_sha256=result["files_sha256"], source_checkpoint_sha256=result["source_checkpoint_sha256"], native_batch_sizes=[1], graph_precision=graph_precision)
        candidate["runtime"].update(device="coreml", batch_size=1, precision=args.precision, compute_units="ALL", profile_note=graph_precision + "; fixed batch1; ALL scheduling unmeasured")
        candidate["runtime"].pop("parameter_precision", None)
        write_json(args.evidence/"config-coreml.json", candidate)
        result["status"] = "converted_and_compiled; output validation pending"
    except BaseException as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["conversion_process_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write_json(args.evidence/"conversion.json", result)
    print(json.dumps({"status":result["status"], "timings":result["timings"]}, indent=2))


if __name__ == "__main__":
    main()
