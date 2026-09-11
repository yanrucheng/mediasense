"""Pinned DINOv3 384 CLS inference, promoted from the accepted Core ML experiment.

The bundled recipe is immutable evidence for this adapter revision. Weights are
prepared separately; neither loading nor diagnosis downloads or converts models.
"""

from __future__ import annotations

from collections.abc import Sequence
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import platform
import threading
from typing import Any

from .embedding import EmbeddingBackendUnavailable, InvalidEmbedding, _package_version


MODEL_ID = "timm/vit_base_patch16_dinov3.lvd1689m"
REVISION = "c6a5fb7d12bbd3cf3b0079253141c3332aaed7da"


def recipe() -> dict[str, Any]:
    return json.loads(files("mediasense._resources").joinpath("dinov3-384.json").read_text())


def default_model_path() -> Path:
    # This is a machine asset, never a Dataset-relative artifact or authority.
    return Path.home() / "Library/Caches/MediaSense/models" / f"dinov3-vitb16-384-{REVISION}"


def verify_model(path: Path) -> None:
    expected = recipe()["files_sha256"]
    try:
        actual = {
            p.relative_to(path).as_posix()
            for p in (path / "vision.mlmodelc").rglob("*") if p.is_file()
        }
        if actual != set(expected):
            raise EmbeddingBackendUnavailable("DINOv3 384 compiled model files are missing or unexpected; prepare the pinned local model")
        for name, digest in expected.items():
            with (path / name).open("rb") as stream:
                observed = hashlib.file_digest(stream, "sha256").hexdigest()
            if observed != digest:
                raise EmbeddingBackendUnavailable(f"DINOv3 384 model checksum mismatch: {name}")
    except OSError as error:
        raise EmbeddingBackendUnavailable("DINOv3 384 local model cannot be read") from error


def platform_issue() -> str | None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return "DINOv3 Core ML requires Apple Silicon macOS; Intel macOS and Windows are not validated or enabled; no backend fallback"
    if int(platform.mac_ver()[0].split(".")[0]) < 15:
        return "DINOv3 compiled graph requires macOS 15 or newer"
    return None


class DinoV3CoreMLEncoder:
    """Fixed native batch 1; caller batches are sequential single-image calls."""

    def __init__(self, *, model_path: Path | None = None) -> None:
        self.model_path = Path(model_path) if model_path is not None else default_model_path()
        self._model: Any = None
        self._processor: Any = None
        self._lock = threading.RLock()

    @property
    def identity(self) -> str:
        spec = recipe()
        versions = {name: _package_version(name) for name in spec["runtime_versions"]}
        # Missing prerequisites must be repairable by resume. Installed differing
        # versions stay distinct and are rejected by readiness, never reused.
        effective = {name: spec["runtime_versions"][name] if value == "unavailable" else value for name, value in versions.items()}
        payload = {"recipe": spec, "packages": effective,
                   "platform": [platform.system(), platform.machine(), platform.mac_ver()[0]]}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return f"dinov3-coreml-384:{MODEL_ID}@{REVISION};sha256={digest}"

    def diagnose(self) -> dict[str, object]:
        spec = recipe()
        issues = []
        if problem := platform_issue():
            issues.append(problem)
        for name, expected in spec["runtime_versions"].items():
            actual = _package_version(name)
            if actual != expected:
                issues.append(f"{name} requires {expected}; installed {actual}")
        try:
            verify_model(self.model_path)
        except EmbeddingBackendUnavailable as error:
            issues.append(str(error))
        return {"state": "unavailable" if issues else "prepared", "issues": issues,
                "encoder_identity": self.identity, "model_path": str(self.model_path),
                "execution": "not_checked", "backend": "coreml", "compute_units": "ALL",
                "hardware_dispatch": "unmeasured", "model_downloads": False,
                "fallback": False}

    def check_available(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            diagnosis = self.diagnose()
            if diagnosis["issues"]:
                raise EmbeddingBackendUnavailable("; ".join(diagnosis["issues"]))
            try:
                import coremltools as ct
                import torch
                from torchvision.transforms import InterpolationMode, v2
            except (ImportError, OSError) as error:
                raise EmbeddingBackendUnavailable("DINOv3 Core ML dependencies cannot be imported locally") from error
            torch.set_num_threads(2)
            if torch.get_num_interop_threads() != 1:
                try:
                    torch.set_num_interop_threads(1)
                except RuntimeError as error:
                    raise EmbeddingBackendUnavailable("DINOv3 requires one inter-op thread; restart this Host before inference") from error
            # Same uint8 resize BEFORE float32 rescale as the accepted experiment.
            self._processor = v2.Compose([
                v2.ToImage(),
                v2.Resize((384, 384), interpolation=InterpolationMode.BILINEAR, antialias=True),
                v2.ToDtype(torch.float32, scale=True),
                v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
            ])
            try:
                self._model = ct.models.CompiledMLModel(
                    str(self.model_path / "vision.mlmodelc"), compute_units=ct.ComputeUnit.ALL,
                )
            except (RuntimeError, OSError) as error:
                raise EmbeddingBackendUnavailable("The pinned DINOv3 Core ML graph cannot load on this Host; no fallback") from error

    def encode_image(self, image_path: Path) -> Sequence[float]:
        return self.encode_images((image_path,))[0]

    def encode_images(self, image_paths: Sequence[Path]) -> Sequence[Sequence[float]]:
        import numpy as np
        from PIL import Image

        self.check_available()
        rows = []
        with self._lock:
            for path in image_paths:
                with Image.open(path) as opened, opened.convert("RGB") as rgb:
                    pixels = self._processor(rgb).unsqueeze(0).numpy()
                # Unexpected prediction failures propagate; never become a wait
                # state or trigger a backend/model/network fallback.
                output = self._model.predict({"pixel_values": pixels})["image_features"]
                if output.shape != (1, 768) or not np.isfinite(output).all() or not np.any(output):
                    raise InvalidEmbedding("DINOv3 requires a finite nonzero 768-dimensional CLS row")
                rows.append(output.astype("float32", copy=False)[0].tolist())
        # EmbeddingProducer performs L2 normalization and float32-le publication.
        return rows
