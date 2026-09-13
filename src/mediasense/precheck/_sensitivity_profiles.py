"""Pinned local recipes and image port declarations, readable without backends."""

from dataclasses import dataclass, asdict
from pathlib import Path
import hashlib
import json
import platform


class SensitivityError(RuntimeError):
    """A sensitivity protocol or execution failure, not a localized bad image."""


class SensitivityBackendUnavailable(SensitivityError):
    """A known missing local prerequisite that can be restored."""


@dataclass(frozen=True)
class SensitivityInput:
    key: str
    path: Path
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class SensitivityPrediction:
    key: str
    sha256: str
    values: dict | None = None
    failure: str | None = None


@dataclass(frozen=True)
class NamedSensitivityProfile:
    name: str
    model_id: str
    revision: str
    files: dict[str, str]
    definitions: dict
    basis: dict
    dependencies: dict[str, str]
    device: str
    precision: str
    batch_size: int
    memory_bytes: int
    cpu_threads: int = 2
    adapter_revision: str = "local-sensitivity-v2"

    @property
    def identity(self):
        # Required versions, not installed versions: exact caches remain readable
        # and reusable after optional dependencies are removed. Load checks them.
        semantic = self.value()
        for key in ("memory_bytes", "batch_size", "cpu_threads"):
            semantic.pop(key)
        semantic["platform"] = platform.platform()
        digest = hashlib.sha256(
            json.dumps(semantic, sort_keys=True).encode()
        ).hexdigest()
        return f"{self.model_id}@{self.revision};profile={self.name};recipe=sha256:{digest}"

    def value(self):
        return asdict(self)


LABELS_640 = [
    "FEMALE_GENITALIA_COVERED",
    "FACE_FEMALE",
    "BUTTOCKS_EXPOSED",
    "FEMALE_BREAST_EXPOSED",
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_BREAST_EXPOSED",
    "ANUS_EXPOSED",
    "FEET_EXPOSED",
    "BELLY_COVERED",
    "FEET_COVERED",
    "ARMPITS_COVERED",
    "ARMPITS_EXPOSED",
    "FACE_MALE",
    "BELLY_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_COVERED",
    "FEMALE_BREAST_COVERED",
    "BUTTOCKS_COVERED",
]
FREEPIK = NamedSensitivityProfile(
    name="freepik-ordinal448-mps-fp32-v1",
    model_id="Freepik/nsfw_image_detector",
    revision="15b85477e4fd2000db76ae9aae0f89a72f95e2e3",
    files={
        "config.json": "39f53e86cc4868e0e11396b523c906f376621f54c1025ffc9ee2ee840542a41b",
        "model.safetensors": "024a9d4818fae2656403bf626c9f8c9e7789c2da274749fbebb1060d8fdaa7ab",
    },
    definitions={
        "declared_properties": [
            "classification_distribution",
            "cumulative_probabilities",
        ],
        "taxonomy": "freepik-native-levels",
        "labels": ["neutral", "low", "medium", "high"],
        "meaning": "Native mutually exclusive ordinal class probabilities, not a nudity fact, accuracy or remote-processing permission.",
    },
    basis={
        "cumulative_probabilities": {
            "operation": "sum",
            "source_property": "classification_distribution",
            "events": {
                "at_least_low": ["low", "medium", "high"],
                "at_least_medium": ["medium", "high"],
                "high": ["high"],
            },
        },
        "preprocessing": "Official Timm 448 bicubic squash, native mean/std; Pillow RGB without additional EXIF transpose or ICC conversion",
    },
    dependencies={
        "torch": "2.7.0",
        "torchvision": "0.22.0",
        "transformers": "4.57.6",
        "timm": "1.0.20",
        "Pillow": "12.3.0",
        "numpy": "2.2.6",
        "safetensors": "0.8.0",
        "huggingface-hub": "0.36.2",
    },
    device="mps",
    precision="float32",
    batch_size=4,
    memory_bytes=7 * 1024**3,
)
NUDENET640 = NamedSensitivityProfile(
    name="nudenet640-native-cpu-fp32-v1",
    model_id="notAI-tech/NudeNet/640m",
    revision="nudenet-3.4.2/v3.4-weights",
    files={
        "640m.onnx": "04fe3d77980780c1f8297dc6d7f942fd5b3abe6942a188f742a85241e4f634eb"
    },
    definitions={
        "declared_properties": ["region_detections"],
        "taxonomy": "nudenet-3.4.2-native-body-labels",
        "labels": LABELS_640,
        "meaning": "Native body-region detection scores, not image sensitivity probabilities. Omitted labels do not establish real-world absence.",
    },
    basis={
        "postprocessing": {
            "candidate_confidence": 0.2,
            "nms_score_threshold": 0.25,
            "nms_iou": 0.45,
            "class_agnostic": True,
            "coordinate_projection": "native integer xywh -> [x,y,x+w,y+h]; no second clipping or NMS",
        },
        "preprocessing": "native OpenCV decode, COLOR_RGBA2BGR and swapRB=True; right/bottom black square padding, 640px, 1/255",
        "weight_source": "SimonJoz/nudenet mirror at 2b20805bd4ab2a9edbbb99fa862f68411c00286a; official bytes not independently obtained",
    },
    dependencies={
        "nudenet": "3.4.2",
        "onnxruntime": "1.22.1",
        "opencv-python-headless": "4.11.0.86",
        "numpy": "2.2.6",
    },
    device="cpu",
    precision="float32",
    batch_size=1,
    memory_bytes=512 * 1024**2,
)
PROFILES = {"freepik": FREEPIK, "nudenet640": NUDENET640}


def normalize_sensitivity(value):
    """Resolve complete per-model configuration without importing inference."""
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise ValueError("sensitivity must be a table")
    if set(value) & {"device", "nsfw_model_id", "nsfw_revision"}:
        raise ValueError(
            "Legacy sensitivity configuration requires explicit migration to sensitivity.models.freepik/nudenet640; Falconsai/320 are not automatically replaced"
        )
    if (
        set(value) - {"enabled", "models"}
        or type(value.get("enabled", False)) is not bool
    ):
        raise ValueError("Invalid sensitivity keys or enabled value")
    models = value.get("models", {})
    if not isinstance(models, dict) or set(models) - set(PROFILES):
        raise ValueError("Unknown sensitivity model or invalid models table")
    resolved = {}
    for name, profile in PROFILES.items():
        item = models.get(name, {})
        if not isinstance(item, dict) or set(item) - {
            "enabled",
            "profile",
            "model_path",
            "device",
            "precision",
            "batch_size",
        }:
            raise ValueError(f"Invalid sensitivity.models.{name} keys")
        enabled = item.get("enabled", False)
        if type(enabled) is not bool:
            raise ValueError(f"{name}.enabled must be boolean")
        expected = {
            "profile": profile.name,
            "device": profile.device,
            "precision": profile.precision,
            "batch_size": profile.batch_size,
        }
        for key, fixed in expected.items():
            if key in item and (
                type(item[key]) is not type(fixed) or item[key] != fixed
            ):
                raise ValueError(
                    f"{name}.{key} must be {fixed!r} for the released recipe"
                )
        path = item.get("model_path")
        if path is not None and (
            not isinstance(path, str) or not Path(path).is_absolute()
        ):
            raise ValueError(f"{name}.model_path must be an absolute local path")
        effective = value.get("enabled", False) and enabled
        if effective and path is None:
            raise ValueError(f"Enabled {name} requires model_path")
        resolved[name] = {"enabled": effective, **expected, "model_path": path}
    return {"enabled": value.get("enabled", False), "models": resolved}
