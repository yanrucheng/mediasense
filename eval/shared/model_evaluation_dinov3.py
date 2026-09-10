"""Evaluation-only DINOv3 CLS adapters; the shared runner owns L2/storage."""

from __future__ import annotations

import os
from pathlib import Path

from model_evaluation_inputs import digest, fingerprint


def load_processor(spec: dict):
    import torch
    from torchvision.transforms import InterpolationMode, v2

    profile = spec["preprocessing"]
    if (
        profile["image_size"] != 512
        or profile["interpolation"] != "bilinear"
        or profile["antialias"] is not True
        or profile["crop"] is not None
        or profile["mean"] != [0.485, 0.456, 0.406]
        or profile["std"] != [0.229, 0.224, 0.225]
    ):
        raise ValueError("This experiment requires the pinned Meta 512px transform")
    # Match Meta's README order: uint8 resize BEFORE rescaling to float32.
    return v2.Compose([
        v2.ToImage(),
        v2.Resize((512, 512), interpolation=InterpolationMode.BILINEAR, antialias=True),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=profile["mean"], std=profile["std"]),
    ])


def image_pixels(processor, paths: list[Path]):
    import torch
    from PIL import Image

    pixels = []
    for path in paths:
        with Image.open(path) as opened:
            with opened.convert("RGB") as rgb:
                pixels.append(processor(rgb))
    batch = torch.stack(pixels)
    if batch.shape != (len(paths), 3, 512, 512) or batch.dtype != torch.float32:
        raise ValueError("Unexpected DINOv3 processor output")
    return batch


def torch_vision(spec: dict, runtime: dict):
    import timm
    import torch
    from safetensors.torch import load_file

    root = Path(timm.__file__).parent
    for name, expected in spec["implementation_files_sha256"].items():
        if digest(root / name) != expected:
            raise ValueError(f"Pinned timm implementation changed: {name}")
    torch.set_num_threads(runtime["cpu_threads"])
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    device, precision = runtime["device"], runtime["precision"]
    if device not in {"cpu", "mps"} or precision not in {"float32", "float16"}:
        raise ValueError("Only CPU/MPS FP32/FP16 are supported by this experiment")
    if device == "mps":
        if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") != "0":
            raise ValueError("Disable MPS CPU fallback before importing torch")
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS unavailable; refusing CPU fallback")
    if spec["rope_precision"] != "float32":
        raise ValueError("Preserve the reference's FP32 RoPE periods and computation")
    encoder = timm.create_model(
        spec["architecture"], pretrained=False, num_classes=0,
        img_size=512, global_pool="token",
    )
    weights = load_file(str(Path(spec["snapshot_path"]) / "model.safetensors"))
    encoder.load_state_dict(weights, strict=True)
    del weights
    if (
        encoder.num_features != spec["dimensions"]
        or encoder.num_prefix_tokens != 5
        or not isinstance(encoder.norm, torch.nn.LayerNorm)
        or not isinstance(encoder.head, torch.nn.Identity)
        or not isinstance(encoder.fc_norm, torch.nn.Identity)
        or any(block.attn.q_bias is not None for block in encoder.blocks)
        or sum(p.numel() for p in encoder.parameters()) != spec["vision_parameters"]
    ):
        raise ValueError("DINOv3 architecture differs from the reviewed CLS model")
    if spec["attention_implementation"] != "sdpa-float32":
        raise ValueError("The verified reference requires FP32 SDPA attention")
    if not all(block.attn.fused_attn for block in encoder.blocks):
        raise ValueError("The effective attention implementation is not SDPA")
    # Half attention overflows; half residuals failed the numerical gate.
    # Keep original FP32 parameters and residuals. The adapter uses autocast
    # for eligible convolution/MLP ops; attention explicitly disables it.
    encoder.eval().requires_grad_(False).to(device=device)
    for parameter in encoder.parameters():
        if parameter.device.type != device or parameter.dtype != torch.float32:
            raise ValueError("Actual parameter device/precision differs from configuration")

    class Float32Attention(torch.nn.Module):
        def __init__(self, attention):
            super().__init__()
            self.attention = attention

        def forward(self, x, rope=None, attn_mask=None):
            with torch.autocast(device_type=x.device.type, enabled=False):
                return self.attention(x.float(), rope=rope, attn_mask=attn_mask)

    for block in encoder.blocks:
        block.attn = Float32Attention(block.attn)
    encoder.eval()
    if encoder.rope.periods.dtype != torch.float32 or encoder.rope.periods.device.type != device:
        raise ValueError("Incorrect RoPE device/precision")
    return encoder


class DinoV3TorchAdapter:
    def __init__(self, model: dict, runtime: dict):
        self.spec, self.runtime = model, runtime

    def load(self) -> None:
        import torch

        self.torch = torch
        self.encoder = torch_vision(self.spec, self.runtime)
        self.processor = load_processor(self.spec)
        self.description = {
            "identity": self.identity,
            "model_id": self.spec["model_id"],
            "revision": self.spec["revision"],
            "device": next(self.encoder.parameters()).device.type,
            "precision": "FP16 autocast convolution/MLP; FP32 parameters, attention, normalization, residuals and RoPE" if self.runtime["precision"] == "float16" else "float32",
            "autocast": self.runtime["precision"] == "float16",
            "vision_parameters": sum(p.numel() for p in self.encoder.parameters()),
            "feature_output": self.spec["feature_output"],
            "prefix_tokens": "CLS + 4 register tokens; only CLS is returned",
            "qkv_bias": False,
            "rope_periods_policy": self.spec["rope_periods_policy"],
            "rope_periods": self.encoder.rope.periods.cpu().tolist(),
            "attention_implementation": "timm EvaAttention in float32, including QKV, SDPA and output projection; attention autocast disabled",
            "parameter_counts_by_dtype": {
                str(dtype): sum(p.numel() for p in self.encoder.parameters() if p.dtype == dtype)
                for dtype in {p.dtype for p in self.encoder.parameters()}
            },
            "preprocessing": self.spec["preprocessing"],
            "output_normalization": "runner L2 normalization and float32-le storage",
            "mps_cpu_fallback": False,
            "cpu_threads": torch.get_num_threads(),
            "inter_op_threads": torch.get_num_interop_threads(),
            "positional_coordinate_creation": "timm creates coordinates on CPU then explicitly transfers to the model device; not operator fallback",
        }

    @property
    def identity(self) -> str:
        return "dinov3-cls:" + fingerprint({"model": self.spec, "runtime": self.runtime})

    def encode_images(self, paths: list[Path]):
        pixels = image_pixels(self.processor, paths).to(device=self.runtime["device"])
        with self.torch.inference_mode(), self.torch.autocast(
            device_type=self.runtime["device"], dtype=self.torch.float16,
            enabled=self.runtime["precision"] == "float16",
        ):
            features = self.encoder.forward_features(pixels)[:, 0, :]
        if features.device.type != self.runtime["device"]:
            raise RuntimeError("DINOv3 features were computed on an unexpected device")
        if features.shape != (len(paths), self.spec["dimensions"]):
            raise ValueError("Unexpected CLS feature shape")
        return features.float().cpu().tolist()

    def synchronize(self) -> None:
        if self.runtime["device"] == "mps":
            self.torch.mps.synchronize()


class DinoV3CoreMLAdapter:
    def __init__(self, model: dict, runtime: dict):
        self.spec, self.runtime = model, runtime

    def load(self) -> None:
        import coremltools as ct
        import torch

        torch.set_num_threads(self.runtime["cpu_threads"])
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        if self.runtime["batch_size"] not in self.spec["native_batch_sizes"]:
            raise ValueError("Configured batch size is outside the verified Core ML shapes")
        self.processor = load_processor(self.spec)
        self.encoder = ct.models.CompiledMLModel(
            str(Path(self.spec["snapshot_path"]) / "vision.mlmodelc"),
            compute_units=getattr(ct.ComputeUnit, self.runtime["compute_units"]),
        )
        self.description = {
            "identity": self.identity,
            "model_id": self.spec["model_id"],
            "revision": self.spec["revision"],
            "device": f"Core ML {self.runtime['compute_units']} (actual scheduling unmeasured)",
            "precision": self.spec["graph_precision"],
            "feature_output": self.spec["feature_output"],
            "source_checkpoint_sha256": self.spec["source_checkpoint_sha256"],
            "native_batch_sizes": self.spec["native_batch_sizes"],
            "multi_image_calls": "sequential single-image predictions" if self.spec["native_batch_sizes"] == [1] else "native batches",
            "padding": "none",
            "preprocessing": self.spec["preprocessing"],
            "torch_model_loaded": False,
            "output_normalization": "runner L2 normalization and float32-le storage",
            "memory_note": "RUSAGE_SELF excludes Core ML services; total unified/GPU memory unknown",
        }

    @property
    def identity(self) -> str:
        return "dinov3-coreml:" + fingerprint({"model": self.spec, "runtime": self.runtime})

    def encode_images(self, paths: list[Path]):
        pixels = image_pixels(self.processor, paths).numpy()
        sizes = self.spec["native_batch_sizes"]
        if sizes == [1]:
            batches = [pixels[i:i + 1] for i in range(len(paths))]
        elif len(paths) in sizes:
            batches = [pixels]
        else:
            raise ValueError("Unsupported native Core ML batch shape")
        rows = []
        for batch in batches:
            output = self.encoder.predict({"pixel_values": batch})["image_features"]
            if output.shape != (len(batch), self.spec["dimensions"]):
                raise ValueError("Unexpected Core ML CLS feature shape")
            rows.extend(output.astype("float32", copy=False).tolist())
        return rows

    def synchronize(self) -> None:
        # predict() is synchronous and returns materialized CPU arrays.
        pass
