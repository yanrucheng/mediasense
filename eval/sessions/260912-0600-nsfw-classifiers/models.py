"""Session-local offline adapters; scores never choose a handling policy."""

from __future__ import annotations

import json
from pathlib import Path


def cumulative_levels(probabilities: dict[str, float]) -> dict[str, float]:
    """Freepik's mutually exclusive classes and cumulative events stay separate."""
    return {
        "at_least_low": sum(probabilities[k] for k in ("low", "medium", "high")),
        "at_least_medium": probabilities["medium"] + probabilities["high"],
        "high": probabilities["high"],
    }


class Classifier:
    def __init__(self, spec: dict, runtime: dict, device: str):
        import torch

        if device == "mps" and not torch.backends.mps.is_available():
            raise RuntimeError("Requested MPS is unavailable; no CPU fallback")
        torch.set_num_threads(runtime["cpu_threads"])
        torch.set_num_interop_threads(1)
        self.torch, self.device = torch, device
        self.spec = spec
        snapshot = Path(spec["snapshot"])
        config = json.loads((snapshot / "config.json").read_text())
        self.processor = None
        self.transform = None
        if spec["loader"] == "timm":
            import timm
            from safetensors.torch import load_file

            labels = config["label_names"]
            self.model = timm.create_model(
                config["architecture"], pretrained=False, num_classes=len(labels)
            )
            self.model.load_state_dict(load_file(str(snapshot / spec["weight_file"])), strict=True)
        else:
            from transformers import AutoModelForImageClassification

            self.model = AutoModelForImageClassification.from_pretrained(
                str(snapshot), local_files_only=True, torch_dtype=torch.float32,
                use_safetensors=spec["weight_file"].endswith(".safetensors"),
            )
            labels = [self.model.config.id2label[i] for i in range(len(spec["labels"]))]
        if labels != spec["labels"]:
            raise ValueError(f"Actual label order differs from pinned config: {labels}")
        if spec["loader"] in {"timm", "transformers_timm"}:
            from timm.data import create_transform, resolve_data_config

            data_config = resolve_data_config({}, pretrained_cfg=config["pretrained_cfg"])
            self.transform = create_transform(**data_config, is_training=False)
            preprocessing = {"data_config": data_config, "transform": repr(self.transform)}
        else:
            from transformers import AutoImageProcessor

            self.processor = AutoImageProcessor.from_pretrained(str(snapshot), local_files_only=True)
            preprocessing = self.processor.to_dict()
        self.model.to(device=device, dtype=torch.float32).eval()
        self.description = {
            "model_class": type(self.model).__name__,
            "parameters": sum(p.numel() for p in self.model.parameters()),
            "parameter_dtypes": sorted({str(p.dtype) for p in self.model.parameters()}),
            "labels": labels,
            "preprocessing": preprocessing,
            "device": device,
            "precision": "float32 weights, inputs, logits and softmax; no autocast",
            "cpu_threads": torch.get_num_threads(),
            "inter_op_threads": torch.get_num_interop_threads(),
        }
        self.synchronize()

    def synchronize(self):
        if self.device == "mps":
            self.torch.mps.synchronize()

    def predict(self, paths: list[Path]) -> list[dict]:
        from PIL import Image

        images = []
        try:
            for path in paths:
                with Image.open(path) as opened:
                    if opened.getexif().get(274, 1) != 1 or getattr(opened, "n_frames", 1) != 1:
                        raise ValueError("Use an oriented, single-frame prepared image")
                    images.append(opened.convert("RGB"))
            with self.torch.inference_mode():
                if self.processor is not None:
                    inputs = self.processor(images=images, return_tensors="pt").to(self.device)
                    logits = self.model(**inputs).logits.float()
                else:
                    inputs = self.torch.stack([self.transform(img) for img in images]).to(self.device)
                    outputs = self.model(inputs)
                    logits = (outputs.logits if hasattr(outputs, "logits") else outputs).float()
                probabilities = logits.softmax(dim=-1).cpu().tolist()
                raw_logits = logits.cpu().tolist()
            self.synchronize()
            result = []
            for raw, values in zip(raw_logits, probabilities, strict=True):
                scores = dict(zip(self.spec["labels"], values, strict=True))
                row = {"logits": raw, "probabilities": scores}
                if self.spec["loader"] == "transformers_timm":
                    row["cumulative_probabilities"] = cumulative_levels(scores)
                result.append(row)
            return result
        finally:
            for img in images:
                img.close()
