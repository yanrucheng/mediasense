"""Offline MobileCLIP2-S2 evaluation adapters; retain the trained image projection."""

from __future__ import annotations

import os
from pathlib import Path
import time

from model_evaluation_inputs import digest, fingerprint


def load_processor(spec):
    from open_clip.transform import PreprocessCfg, image_transform_v2

    p = spec["preprocessing"]
    if p != {"image_size": 256, "resize_mode": "shortest", "crop": "center", "interpolation": "bilinear", "antialias": True, "mean": [0.0] * 3, "std": [1.0] * 3, "image_decode": "Pillow RGB; no EXIF transpose"}:
        raise ValueError("Only the fixed MobileCLIP2-S2 inference recipe is supported")
    return image_transform_v2(PreprocessCfg(size=256, mean=tuple(p["mean"]), std=tuple(p["std"]), interpolation="bilinear", resize_mode="shortest"), is_train=False)


def image_pixels(processor, paths, timings=None):
    import torch
    from PIL import Image

    values = []
    for path in paths:
        start = time.perf_counter()
        with Image.open(path) as opened:
            with opened.convert("RGB") as rgb:
                decoded = time.perf_counter()
                values.append(processor(rgb))
                processed = time.perf_counter()
        if timings is not None:
            timings["read_rgb_decode"] += decoded - start
            timings["resize_normalize_stack"] += processed - decoded
    start = time.perf_counter()
    pixels = torch.stack(values)
    if timings is not None:
        timings["resize_normalize_stack"] += time.perf_counter() - start
    if pixels.shape != (len(paths), 3, 256, 256) or pixels.dtype != torch.float32:
        raise ValueError("Incorrect processed pixels")
    return pixels


def torch_vision(spec, runtime, *, reparameterize=True):
    import open_clip
    import timm
    import torch
    from open_clip.timm_model import TimmModel
    from timm.models.fastvit import checkpoint_filter_fn
    from timm.utils import reparameterize_model

    for package, root in (("open_clip", Path(open_clip.__file__).parent), ("timm", Path(timm.__file__).parent)):
        for name, sha in spec["implementation_files_sha256"][package].items():
            if digest(root / name) != sha:
                raise ValueError(f"Pinned {package} implementation changed: {name}")
    torch.set_num_threads(runtime["cpu_threads"])
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    device = runtime["device"]
    if device not in {"cpu", "mps"} or runtime["precision"] not in {"float32", "float16"}:
        raise ValueError("Unsupported device or precision")
    if device == "mps" and (os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") != "0" or not torch.backends.mps.is_available()):
        raise RuntimeError("MPS unavailable or CPU fallback enabled")
    encoder = TimmModel("fastvit_mci2", embed_dim=512, image_size=256, pool="avg", proj=None, pretrained=False)
    state = torch.load(Path(spec["snapshot_path"]) / "mobileclip2_s2.pt", map_location="cpu", weights_only=True)
    if not all(k.startswith(("image_encoder.model.", "text_encoder.")) or k == "logit_scale" for k in state):
        raise ValueError("Unexpected checkpoint tensor prefix")
    # This is the same upstream mapping used by OpenCLIP's load_checkpoint.
    weights = checkpoint_filter_fn(state, encoder.trunk)
    encoder.trunk.load_state_dict(weights, strict=True)
    del state, weights
    before = sum(p.numel() for p in encoder.parameters())
    if before != spec["parameters_before_fusion"] or encoder.trunk.head.fc.out_features != 512 or len(encoder.head) != 0:
        raise ValueError("Unexpected image tower or projection")
    encoder.eval().requires_grad_(False)
    if reparameterize:
        encoder = reparameterize_model(encoder)
        if sum(p.numel() for p in encoder.parameters()) != spec["vision_parameters"]:
            raise ValueError("Unexpected fused image parameter count")
    dtype = getattr(torch, runtime["precision"])
    encoder.to(device=device, dtype=dtype).eval().requires_grad_(False)
    if any(p.device.type != device or p.dtype != dtype for p in encoder.parameters()):
        raise ValueError("Actual parameter device/precision mismatch")
    return encoder


class MobileCLIP2TorchAdapter:
    def __init__(self, model, runtime):
        self.spec, self.runtime = model, runtime

    @property
    def identity(self):
        return "mobileclip2-image:" + fingerprint({"model": self.spec, "runtime": self.runtime})

    def load(self):
        import torch

        self.torch = torch
        self.encoder = torch_vision(self.spec, self.runtime)
        self.processor = load_processor(self.spec)
        self.description = {
            "identity": self.identity, "model_id": self.spec["model_id"], "revision": self.spec["revision"],
            "device": self.runtime["device"], "precision": self.runtime["precision"], "autocast": False,
            "vision_parameters": sum(p.numel() for p in self.encoder.parameters()),
            "parameters_before_fusion": self.spec["parameters_before_fusion"],
            "feature_output": self.spec["feature_output"], "preprocessing": self.spec["preprocessing"],
            "reparameterization": "timm reparameterize_model in CPU FP32, eval mode, before device/dtype conversion",
            "text_tower_loaded": False, "mps_cpu_fallback": False,
            "output_normalization": "runner L2, float32-le storage", "processor": str(self.processor),
        }

    def encode_images(self, paths):
        timings = {"read_rgb_decode": 0.0, "resize_normalize_stack": 0.0}
        pixels = image_pixels(self.processor, paths, timings)
        start = time.perf_counter()
        pixels = pixels.to(device=self.runtime["device"], dtype=getattr(self.torch, self.runtime["precision"]))
        with self.torch.inference_mode():
            features = self.encoder(pixels)
        if features.shape != (len(paths), 512) or features.device.type != self.runtime["device"]:
            raise ValueError("Incorrect output shape/device")
        rows = features.float().cpu().tolist()
        self.synchronize()
        timings["predict_transfer_sync"] = time.perf_counter() - start
        self.last_stage_seconds = timings
        return rows

    def synchronize(self):
        if self.runtime["device"] == "mps":
            self.torch.mps.synchronize()


class MobileCLIP2CoreMLAdapter:
    def __init__(self, model, runtime):
        self.spec, self.runtime = model, runtime

    @property
    def identity(self):
        return "mobileclip2-coreml:" + fingerprint({"model": self.spec, "runtime": self.runtime})

    def load(self):
        import coremltools as ct
        import torch

        torch.set_num_threads(self.runtime["cpu_threads"])
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        if self.runtime["batch_size"] != 1 or self.spec["native_batch_sizes"] != [1]:
            raise ValueError("Only fixed single-image Core ML is validated")
        self.processor = load_processor(self.spec)
        self.encoder = ct.models.CompiledMLModel(str(Path(self.spec["snapshot_path"]) / "vision.mlmodelc"), compute_units=getattr(ct.ComputeUnit, self.runtime["compute_units"]))
        self.description = {
            "identity": self.identity, "model_id": self.spec["model_id"], "revision": self.spec["revision"],
            "device": "Core ML ALL; actual dispatch unmeasured", "precision": self.spec["graph_precision"],
            "feature_output": self.spec["feature_output"], "preprocessing": self.spec["preprocessing"],
            "vision_parameters": self.spec["vision_parameters"], "torch_model_loaded": False,
            "native_batch_sizes": [1], "multi_image_calls": "sequential single-image predictions",
            "output_normalization": "runner L2, float32-le storage",
            "memory_note": "RSS excludes Core ML services; total unified/GPU memory unknown",
        }

    def encode_images(self, paths):
        timings = {"read_rgb_decode": 0.0, "resize_normalize_stack": 0.0}
        pixels = image_pixels(self.processor, paths, timings)
        start = time.perf_counter()
        pixels = pixels.numpy()
        rows = []
        for i in range(len(paths)):
            output = self.encoder.predict({"pixel_values": pixels[i:i + 1]})["image_features"]
            if output.shape != (1, 512):
                raise ValueError("Incorrect Core ML output shape")
            rows.extend(output.astype("float32", copy=False).tolist())
        timings["predict_transfer_sync"] = time.perf_counter() - start
        self.last_stage_seconds = timings
        return rows

    def synchronize(self):
        pass  # predict returns materialized CPU arrays synchronously
