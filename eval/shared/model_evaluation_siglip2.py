"""Evaluation-only SigLIP 2 image tower adapters; no product model replacement."""

from __future__ import annotations

import inspect
import os
from pathlib import Path

from model_evaluation_inputs import digest, fingerprint


def load_processor(spec: dict):
    from transformers import SiglipImageProcessor

    return SiglipImageProcessor.from_pretrained(
        spec["snapshot_path"], local_files_only=True
    )


def image_pixels(processor, paths: list[Path]):
    from PIL import Image

    images = []
    try:
        for path in paths:
            with Image.open(path) as opened:
                images.append(opened.convert("RGB"))
        return processor(images=images, return_tensors="np")["pixel_values"]
    finally:
        for image in images:
            image.close()


def torch_vision(spec: dict, runtime: dict):
    import torch
    from transformers import SiglipVisionModel

    source = Path(inspect.getfile(SiglipVisionModel))
    if digest(source) != spec["encoder_source_sha256"]:
        raise ValueError("Pinned Transformers SigLIP implementation changed")
    torch.set_num_threads(runtime["cpu_threads"])
    if torch.get_num_interop_threads() != 1:
        torch.set_num_interop_threads(1)
    if runtime["device"] not in {"cpu", "mps"}:
        raise ValueError("This evaluation supports only CPU reference or MPS")
    if runtime["precision"] not in {"float32", "float16"}:
        raise ValueError("This evaluation does not use quantized weights")
    if runtime["device"] == "mps":
        if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") != "0":
            raise ValueError("MPS CPU fallback must be disabled before importing torch")
        if not torch.backends.mps.is_available():
            raise RuntimeError("MPS is unavailable; refusing CPU fallback")
    dtype = getattr(torch, runtime["precision"])
    encoder, loading = SiglipVisionModel.from_pretrained(
        spec["snapshot_path"],
        local_files_only=True,
        dtype=dtype,
        attn_implementation=spec["attention_implementation"],
        output_loading_info=True,
    )
    if loading["missing_keys"] or loading["mismatched_keys"] or loading["error_msgs"]:
        raise ValueError(f"Incomplete image tower weights: {loading}")
    if any(
        not key.startswith(("text_model.", "logit_scale", "logit_bias"))
        for key in loading["unexpected_keys"]
    ):
        raise ValueError("Unexpected non-text checkpoint weights were ignored")
    encoder.eval().requires_grad_(False).to(runtime["device"])
    if not encoder.vision_model.use_head:
        raise ValueError("Official attention pooling head is required")
    if encoder.config.hidden_size != spec["dimensions"]:
        raise ValueError("Image feature dimensions do not match configuration")
    if any(
        parameter.device.type != runtime["device"] or parameter.dtype != dtype
        for parameter in encoder.parameters()
    ):
        raise ValueError("Actual image tower device/precision differs from configuration")
    return encoder, source, len(loading["unexpected_keys"])


class Siglip2TorchAdapter:
    def __init__(self, model: dict, runtime: dict):
        self.spec, self.runtime = model, runtime

    def load(self) -> None:
        import torch

        self.torch = torch
        self.encoder, source, excluded = torch_vision(self.spec, self.runtime)
        self.processor = load_processor(self.spec)
        self.description = {
            "identity": self.identity,
            "model_id": self.spec["model_id"],
            "revision": self.spec["revision"],
            "device": next(self.encoder.parameters()).device.type,
            "precision": str(next(self.encoder.parameters()).dtype).removeprefix("torch."),
            "autocast": False,
            "attention_implementation": self.encoder.config._attn_implementation,
            "encoder_source": str(source),
            "encoder_source_sha256": digest(source),
            "vision_parameters": sum(p.numel() for p in self.encoder.parameters()),
            "excluded_checkpoint_tensors": excluded,
            "text_tower_loaded": False,
            "feature_output": "SiglipVisionModel.pooler_output; official learned attention pooling + residual MLP, identical path to SiglipModel.get_image_features",
            "preprocessing": self.processor.to_dict(),
            "image_decode": "Pillow Image.open -> RGB; no EXIF transpose",
            "output_normalization": "runner L2 normalization and float32-le storage",
            "mps_available": torch.backends.mps.is_available(),
            "mps_cpu_fallback": False,
            "cpu_threads": torch.get_num_threads(),
            "inter_op_threads": torch.get_num_interop_threads(),
        }

    @property
    def identity(self) -> str:
        return "siglip2-image:" + fingerprint({"model": self.spec, "runtime": self.runtime})

    def encode_images(self, paths: list[Path]):
        pixels = self.torch.from_numpy(image_pixels(self.processor, paths)).to(
            device=self.runtime["device"], dtype=getattr(self.torch, self.runtime["precision"])
        )
        with self.torch.inference_mode():
            features = self.encoder(pixel_values=pixels).pooler_output
        if features.device.type != self.runtime["device"]:
            raise RuntimeError("Image features were computed on an unexpected device")
        return features.float().cpu().tolist()

    def synchronize(self) -> None:
        if self.runtime["device"] == "mps":
            self.torch.mps.synchronize()


class Siglip2CoreMLAdapter:
    def __init__(self, model: dict, runtime: dict):
        self.spec, self.runtime = model, runtime

    def load(self) -> None:
        import coremltools as ct

        if self.spec.get("prediction_batch_size") == 1 and self.runtime["batch_size"] != 1:
            raise ValueError("Validated Core ML profile requires runtime batch_size=1")
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
            "precision": "float16 graph; float32 input/output",
            "compute_units": self.runtime["compute_units"],
            "actual_compute_devices": "unknown; allowed units and compute plan are not execution tracing",
            "compiled_model": str(Path(self.spec["snapshot_path"]) / "vision.mlmodelc"),
            "source_checkpoint_sha256": self.spec["source_checkpoint_sha256"],
            "feature_output": "converted official SigLIP vision tower pooler_output",
            "text_tower_loaded": False,
            "torch_model_loaded": False,
            "preprocessing": self.processor.to_dict(),
            "image_decode": "Pillow Image.open -> RGB; no EXIF transpose",
            "output_normalization": "runner L2 normalization and float32-le storage",
            "batch_shapes": self.spec.get("batch_shapes", [1, 2, 4]),
            "prediction_batch_size": self.spec.get("prediction_batch_size", "native input batch"),
            "multi_image_calls": "sequential single-image predictions" if self.spec.get("prediction_batch_size") == 1 else "native batch",
            "padding": "Repeat final real input to fixed batch 4; discard padding outputs" if self.spec.get("batch_shapes") == [4] else "none",
            "memory_note": "RUSAGE_SELF excludes Core ML services and does not measure total unified memory",
        }

    @property
    def identity(self) -> str:
        return "siglip2-coreml:" + fingerprint({"model": self.spec, "runtime": self.runtime})

    def encode_images(self, paths: list[Path]):
        import numpy as np

        if len(paths) not in {1, 2, 4}:
            raise ValueError("Converted model supports only batches 1, 2 and 4")
        pixels = image_pixels(self.processor, paths).astype(np.float32, copy=False)
        if self.spec.get("prediction_batch_size") == 1:
            outputs = []
            for index in range(len(paths)):
                value = self.encoder.predict({"pixel_values": pixels[index:index + 1]})["image_features"]
                if value.shape != (1, self.spec["dimensions"]):
                    raise ValueError(f"Unexpected Core ML single-image feature shape: {value.shape}")
                outputs.append(value[0].astype(np.float32, copy=False).tolist())
            return outputs
        physical_rows = len(paths)
        if self.spec.get("batch_shapes") == [4] and len(paths) < 4:
            pixels = np.concatenate([pixels, np.repeat(pixels[-1:], 4 - len(paths), axis=0)])
            physical_rows = 4
        output = self.encoder.predict({"pixel_values": pixels})["image_features"]
        if output.shape != (physical_rows, self.spec["dimensions"]):
            raise ValueError(f"Unexpected Core ML image feature shape: {output.shape}")
        return output[:len(paths)].astype(np.float32, copy=False).tolist()

    def synchronize(self) -> None:
        # CompiledMLModel.predict is synchronous and returns materialized CPU arrays.
        pass
