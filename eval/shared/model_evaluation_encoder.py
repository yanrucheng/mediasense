"""Evaluation-only lifecycle around the installed ImageEmbeddingEncoder port."""

from __future__ import annotations

import inspect
from pathlib import Path

from model_evaluation_inputs import digest


class ChineseCLIPAdapter:
    """Keep PyTorch objects and synchronization inside this adapter."""

    def __init__(self, model: dict, runtime: dict):
        self.spec = model
        self.runtime = runtime

    def load(self) -> None:
        import torch
        from mediasense.precheck.embedding import ChineseCLIPEncoder

        source = Path(inspect.getfile(ChineseCLIPEncoder))
        if digest(source) != self.spec["encoder_source_sha256"]:
            raise ValueError(
                "Installed image encoder changed; record and review the new adapter version"
            )
        torch.set_num_threads(self.runtime["cpu_threads"])
        torch.set_num_interop_threads(1)
        self.torch = torch
        self.encoder = ChineseCLIPEncoder(
            model_id=str(Path(self.spec["snapshot_path"]).resolve()),
            revision=self.spec["revision"],
            device=self.runtime["device"],
        )
        self.encoder.check_available()
        # Inspection belongs here, never in the framework-neutral runner.
        model, processor, _ = self.encoder._load()
        if {str(parameter.dtype) for parameter in model.parameters()} != {
            "torch.float32"
        }:
            raise ValueError("Baseline requires actual float32 model parameters")
        if model.config.projection_dim != self.spec["dimensions"]:
            raise ValueError(
                "Model projection dimension does not match the declared profile"
            )
        self.description = {
            "identity": self.encoder.identity,
            "model_id": self.spec["model_id"],
            "revision": self.spec["revision"],
            "encoder_source": str(source),
            "precision": "float32; no autocast; existing no_grad path",
            "preprocessing": processor.image_processor.to_dict(),
            "image_decode": "Pillow Image.open -> RGB; no EXIF transpose",
            "output_normalization": self.spec["normalization"],
            "mps_available": torch.backends.mps.is_available(),
            "cpu_threads": torch.get_num_threads(),
            "inter_op_threads": torch.get_num_interop_threads(),
        }
        self.synchronize()

    @property
    def identity(self) -> str:
        return self.encoder.identity

    def encode_images(self, paths: list[Path]):
        # The existing batch port promises one vector per path in input order.
        return self.encoder.encode_images(paths)

    def synchronize(self) -> None:
        if self.runtime["device"] == "mps":
            self.torch.mps.synchronize()
        elif self.runtime["device"] == "cuda":
            self.torch.cuda.synchronize()
