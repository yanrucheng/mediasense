"""Resolve explicit local profiles without changing existing model selections."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mediasense.precheck.dinov3 import MODEL_ID, REVISION, DinoV3CoreMLEncoder, default_model_path
from mediasense.precheck.embedding import ChineseCLIPEncoder


def dinov3_profile(value: dict[str, Any]) -> dict[str, Any]:
    from .config import ConfigurationError

    defaults = dict(model_id=MODEL_ID, revision=REVISION, dimensions=768,
                    device="coreml", batch_size=1, image_size=384,
                    model_path=str(default_model_path()))
    for key, expected in defaults.items():
        if key in {"model_path"}:
            continue
        actual = value.get(key, expected)
        if actual != expected or type(actual) is not type(expected):
            raise ConfigurationError(f"DINOv3 embedding.{key} must be {expected!r}; other recipes/backends are not released")
    model_path = value.get("model_path", defaults["model_path"])
    if not isinstance(model_path, str) or not Path(model_path).is_absolute():
        raise ConfigurationError("embedding.model_path must be an absolute machine-local path")
    return {**defaults, "model_path": model_path}


def make_encoder(profile: dict[str, Any]):
    if profile["model_id"] == MODEL_ID:
        return DinoV3CoreMLEncoder(model_path=Path(profile["model_path"]))
    return ChineseCLIPEncoder(model_id=profile["model_id"], revision=profile["revision"], device=profile["device"])
