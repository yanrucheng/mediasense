"""Fixed real-input checks of MobileCLIP2-S2 mapping, fusion and runtime precision."""
import argparse
from copy import deepcopy
import gc
import json
import os
from pathlib import Path
import sys

SESSION = Path(__file__).resolve().parent
sys.path.insert(0, str(SESSION.parents[1] / "shared"))
sys.path.insert(0, str(SESSION.parent / "260910-2212-dinov3-vitb16-512"))
from model_evaluation import check_runtime, timed_batch  # noqa: E402
from model_evaluation_inputs import fingerprint, validate_inputs, write_json  # noqa: E402
from model_evaluation_mobileclip2 import MobileCLIP2TorchAdapter, MobileCLIP2CoreMLAdapter, image_pixels, torch_vision  # noqa: E402
from validate import compare, TOLERANCES  # noqa: E402


def recipe(c):
    return fingerprint({k: c["model"][k] for k in ("model_id", "revision", "preprocessing", "feature_output", "implementation_files_sha256")})


def exercise(c, paths, destination, reference=False):
    import numpy as np
    import torch

    cls = MobileCLIP2CoreMLAdapter if c["runtime"]["device"] == "coreml" else MobileCLIP2TorchAdapter
    a = cls(c["model"], c["runtime"])
    a.load()
    def encode(p, adapter=a):
        return np.asarray(timed_batch(adapter, p)[0])
    batch = np.concatenate([encode(paths[i:i+4]) for i in (0, 4)])
    single = np.concatenate([encode([p]) for p in paths])
    order = [7, 0, 5, 2, 6, 1, 4, 3]
    reordered = np.concatenate([encode([paths[j] for j in order[i:i+4]]) for i in (0, 4)])
    tail, duplicate = encode(paths[-2:]), encode([paths[i] for i in (2, 2, 5, 2)])
    result = {"single_vs_batch": compare(batch, single), "reordered": compare(batch[order], reordered), "tail": compare(batch[-2:], tail), "duplicate": compare(batch[[2, 2, 5, 2]], duplicate), "description": a.description}
    np.savez(destination, batch=batch, single=single, reordered=reordered, tail=tail, duplicate=duplicate)
    if reference:
        import open_clip
        from PIL import Image
        from torchvision.transforms import Compose, Resize, CenterCrop, ToTensor, Normalize, InterpolationMode

        pixels = image_pixels(a.processor, paths[:4])
        independently = Compose([Resize(256, interpolation=InterpolationMode.BILINEAR, antialias=True), CenterCrop(256), ToTensor(), Normalize((0.,)*3, (1.,)*3)])
        expected = []
        for p in paths[:4]:
            with Image.open(p) as im:
                with im.convert("RGB") as rgb:
                    expected.append(independently(rgb))
        if not torch.equal(pixels, torch.stack(expected)):
            raise ValueError("Wrong MobileCLIP preprocessing")
        unfused = torch_vision(c["model"], c["runtime"], reparameterize=False)
        full = open_clip.create_model("MobileCLIP2-S2", pretrained=None, device="cpu").eval()
        open_clip.load_checkpoint(full, str(Path(c["model"]["snapshot_path"]) / "mobileclip2_s2.pt"), strict=True)
        with torch.inference_mode():
            raw = unfused(pixels).numpy()
            direct = full.encode_image(pixels, normalize=False).numpy()
        if not np.array_equal(raw, direct):
            raise ValueError("Vision-only adapter differs from full OpenCLIP encode_image")
        result["reference"] = {"preprocessing_exact": True, "full_openclip_unfused_exact": True, "fusion_vs_unfused": compare(raw, batch[:4]), "dimensions": 512, "parameters_before_fusion": sum(p.numel() for p in unfused.parameters()), "parameters_after_fusion": sum(p.numel() for p in a.encoder.parameters())}
        del full, unfused
    del a
    gc.collect()
    if c["runtime"]["device"] == "mps":
        torch.mps.empty_cache()
    return batch, result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("phase", choices=["torch", "coreml"])
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--reference", type=Path)
    args = p.parse_args()
    c = json.loads(args.config.read_text())
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", PYTORCH_ENABLE_MPS_FALLBACK="0")
    os.nice(max(0, c["runtime"]["nice"] - os.getpriority(os.PRIO_PROCESS, 0)))
    check_runtime(c)
    data = validate_inputs(c, args.inputs)
    selected = []
    for kind in ("image", "video"):
        rows = [r for r in data["inputs"] if r["state"] == "ready" and r["kind"] == kind]
        selected.extend(rows[i] for i in (0, len(rows)//3, 2*len(rows)//3, len(rows)-1))
    paths = [Path(r["image_path"]) for r in selected]
    samples = [{k:r[k] for k in ("id", "kind", "image_sha256")} for r in selected]
    args.output.mkdir(parents=True, exist_ok=False)
    result = {"status": "incomplete", "recipe": recipe(c), "input_fingerprint": data["input_fingerprint"], "samples": samples, "tolerances": TOLERANCES, "checks": {}}
    import numpy as np
    features = {}
    try:
        if args.phase == "torch":
            for name, device, precision in [("cpu_fp32", "cpu", "float32"), ("mps_fp32", "mps", "float32"), ("mps_fp16", "mps", "float16")]:
                print("checking", name, flush=True)
                variant = deepcopy(c)
                variant["runtime"].update(device=device, precision=precision)
                features[name], result["checks"][name] = exercise(variant, paths, args.output/f"{name}.npz", reference=name=="cpu_fp32")
                if name != "cpu_fp32":
                    result["checks"][name+"_vs_cpu"] = compare(features["cpu_fp32"], features[name])
        else:
            reference = json.loads((args.reference/"validation.json").read_text())
            if reference["status"] != "passed" or reference["recipe"] != recipe(c) or reference["samples"] != samples:
                raise ValueError("Mismatched reference")
            features["coreml"], result["checks"]["coreml"] = exercise(c, paths, args.output/"coreml.npz")
            with np.load(args.reference/"features.npz") as previous:
                for name in ("cpu_fp32", "mps_fp32" if c["runtime"]["precision"] == "float32" else "mps_fp16"):
                    result["checks"]["coreml_vs_"+name] = compare(previous[name], features["coreml"])
        validate_inputs(c, args.inputs)
        result["status"] = "passed"
    except BaseException as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        np.savez(args.output/"features.npz", **features)
        write_json(args.output/"validation.json", result)
    print(result["status"], flush=True)


if __name__ == "__main__":
    main()
