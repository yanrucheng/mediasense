"""Reproduce rejected FP16 policies and the accepted bounded autocast policy."""

from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "shared"))
from model_evaluation import check_runtime  # noqa: E402
from model_evaluation_dinov3 import image_pixels, load_processor, torch_vision  # noqa: E402
from model_evaluation_inputs import validate_inputs, write_json  # noqa: E402
from validate import compare  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PYTORCH_ENABLE_MPS_FALLBACK="0")
    config = json.loads(args.config.read_text())
    check_runtime(config)
    prepared = validate_inputs(config, args.inputs)
    metadata = json.loads((args.reference / "validation.json").read_text())
    if metadata["status"] != "passed" or metadata["input_fingerprint"] != prepared["input_fingerprint"]:
        raise ValueError("Require a passing reference for the same frozen inputs")
    by_id = {row["id"]: row for row in prepared["inputs"]}
    paths = []
    for sample in metadata["samples"]:
        row = by_id[sample["id"]]
        if row["image_sha256"] != sample["image_sha256"]:
            raise ValueError("Reference input bytes changed")
        paths.append(Path(row["image_path"]))
    args.output.mkdir(parents=True, exist_ok=False)
    import numpy as np
    import torch

    reference = np.load(args.reference / "features.npz")["cpu_fp32"]
    pixels = image_pixels(load_processor(config["model"]), paths)
    results = {}

    class FP32ReturnInput(torch.nn.Module):
        def __init__(self, attention):
            super().__init__()
            self.attention = attention

        def forward(self, x, rope=None, attn_mask=None):
            with torch.autocast("mps", enabled=False):
                return self.attention(x.float(), rope=rope, attn_mask=attn_mask).to(x.dtype)

    for mode in ("full_half", "standard_autocast", "half_residual_fp32_attention", "validated_autocast"):
        model = torch_vision(config["model"], {**config["runtime"], "precision": "float32"})
        if mode in {"full_half", "standard_autocast"}:
            for block in model.blocks:
                block.attn = block.attn.attention
        if mode == "full_half":
            periods = model.rope.periods.clone()
            model.half()
            model.rope.periods = periods
        elif mode == "half_residual_fp32_attention":
            for block in model.blocks:
                block.attn = FP32ReturnInput(block.attn.attention)
            for name, parameter in model.named_parameters():
                parameter.data = parameter.detach().to(torch.float32 if ".attn." in name else torch.float16)
        model.eval()
        first_bad = []

        def capture(name):
            def hook(module, inputs, output):
                if not first_bad and isinstance(output, torch.Tensor) and not bool(torch.isfinite(output).all()):
                    first_bad.append(name)
            return hook

        handles = [module.register_forward_hook(capture(name)) for name, module in model.named_modules() if name == "patch_embed" or (name.startswith("blocks.") and len(name.split(".")) <= 3)]
        autocast = mode in {"standard_autocast", "validated_autocast"}
        dtype = torch.float32 if autocast else torch.float16
        batches = []
        with torch.inference_mode(), torch.autocast("mps", dtype=torch.float16, enabled=autocast):
            for start in range(0, len(paths), 4):
                value = model.forward_features(pixels[start:start + 4].to("mps", dtype=dtype))[:, 0, :]
                batches.append(value.float().cpu().numpy())
        features = np.concatenate(batches)
        np.save(args.output / f"{mode}.npy", features)
        finite = bool(np.isfinite(features).all())
        results[mode] = {"all_finite": finite, "first_nonfinite_module": first_bad[0] if first_bad else None, "comparison": compare(reference, features, enforce=False) if finite else None}
        print(mode, json.dumps(results[mode]), flush=True)
        for handle in handles:
            handle.remove()
        del model, value
        gc.collect()
        torch.mps.empty_cache()
    write_json(args.output / "diagnosis.json", {"input_fingerprint": prepared["input_fingerprint"], "policies": results})


if __name__ == "__main__":
    main()
