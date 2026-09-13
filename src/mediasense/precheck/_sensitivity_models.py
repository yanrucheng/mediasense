"""Offline adapters for the two released sensitivity recipes."""

import gc
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import time

from PIL import Image, UnidentifiedImageError

from ._sensitivity_profiles import (
    PROFILES,
    NamedSensitivityProfile,
    SensitivityBackendUnavailable,
    SensitivityError,
    SensitivityPrediction,
)


def prerequisites(profile, model_path):
    """Check files and dependency metadata; never import or execute a model."""
    failures = []
    actual = {}
    for package, expected in profile.dependencies.items():
        try:
            actual[package] = version(package)
        except PackageNotFoundError:
            actual[package] = None
        if actual[package] != expected:
            failures.append(f"{package} requires {expected}, found {actual[package]}")
    path = Path(model_path) if model_path is not None else None
    files = {}
    for name, expected in profile.files.items():
        selected = (
            None if path is None else path / name if len(profile.files) > 1 else path
        )
        digest = None
        if selected is not None:
            try:
                with selected.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
            except (
                FileNotFoundError,
                NotADirectoryError,
                IsADirectoryError,
                PermissionError,
            ):
                pass
        files[name] = digest
        if digest != expected:
            failures.append(f"{name}: pinned local content unavailable")
    return {
        "state": "unavailable" if failures else "prepared",
        "failures": failures,
        "dependencies": actual,
        "files_sha256": files,
        "execution": "not_checked",
    }


class LocalSensitivityDetector:
    def __init__(self, profile: NamedSensitivityProfile, model_path: Path):
        self.profile = profile
        self.model_path = Path(model_path)
        self._model = None
        self._transform = None
        self.execution = None
        self.batch_execution = {}

    @property
    def identity(self):
        return self.profile.identity

    @property
    def declaration(self):
        return {**self.profile.value(), "input": "oriented_single_frame_prepared_image"}

    def load(self):
        if self._model is not None:
            return False
        started = time.monotonic()
        facts = prerequisites(self.profile, self.model_path)
        if facts["failures"]:
            raise SensitivityBackendUnavailable("; ".join(facts["failures"]))
        if self.profile.device == "mps":
            self._load_freepik()
        elif self.profile.device == "cpu":
            self._load_nudenet()
        else:
            raise SensitivityError("Unknown released adapter profile")
        self.execution.update(
            {
                "load_seconds": time.monotonic() - started,
                "dependencies": facts["dependencies"],
                "files_sha256": facts["files_sha256"],
                "measured_memory_bytes": None,
                "memory_estimate_bytes": self.profile.memory_bytes,
                "memory_estimate_scope": "admission estimate including residency and batch; not measured process peak",
            }
        )
        return True

    def _load_freepik(self):
        try:
            import torch
            from transformers import AutoModelForImageClassification
            from timm.data import create_transform, resolve_data_config
        except ModuleNotFoundError as error:
            if error.name not in {"torch", "transformers", "timm"}:
                raise
            raise SensitivityBackendUnavailable(
                "Freepik local inference libraries unavailable"
            ) from error
        if os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK", "0") != "0":
            raise SensitivityBackendUnavailable(
                "Freepik forbids PYTORCH_ENABLE_MPS_FALLBACK; start the Host with fallback disabled"
            )
        if not torch.backends.mps.is_available():
            raise SensitivityBackendUnavailable("Freepik requires MPS; no CPU fallback")
        torch.set_num_threads(self.profile.cpu_threads)
        if torch.get_num_interop_threads() != 1:
            torch.set_num_interop_threads(1)
        model = (
            AutoModelForImageClassification.from_pretrained(
                str(self.model_path),
                local_files_only=True,
                torch_dtype=torch.float32,
                use_safetensors=True,
            )
            .to(device="mps", dtype=torch.float32)
            .eval()
        )
        labels = [model.config.id2label[i] for i in range(4)]
        if labels != self.profile.definitions["labels"]:
            raise SensitivityError(
                "Loaded Freepik label order differs from declaration"
            )
        config = json.loads((self.model_path / "config.json").read_text())
        data = resolve_data_config({}, pretrained_cfg=config["pretrained_cfg"])
        self._transform = create_transform(**data, is_training=False)
        devices = {p.device.type for p in model.parameters()}
        precisions = {str(p.dtype) for p in model.parameters()}
        if devices != {"mps"} or precisions != {"torch.float32"}:
            raise SensitivityError(
                "Loaded Freepik device or precision contradicts recipe"
            )
        self._model = model
        torch.mps.synchronize()
        self.execution = {
            "device": "mps",
            "precision": "float32",
            "cpu_threads": torch.get_num_threads(),
            "inter_op_threads": torch.get_num_interop_threads(),
            "preprocessing": {"data_config": data, "transform": repr(self._transform)},
        }

    def _load_nudenet(self):
        try:
            import cv2
            import onnxruntime as ort
            from nudenet import NudeDetector
            import nudenet.nudenet as native
        except ModuleNotFoundError as error:
            if error.name not in {"cv2", "onnxruntime", "nudenet"}:
                raise
            raise SensitivityBackendUnavailable(
                "NudeNet local inference libraries unavailable"
            ) from error
        # Version alone cannot certify the native color/NMS implementation.
        digest = hashlib.sha256(Path(native.__file__).read_bytes()).hexdigest()
        if digest != "4ce2b9e18a698196afc7ec5bef66c2f2be14b85dc6c57041a4392fbb58c1952c":
            raise SensitivityBackendUnavailable(
                "NudeNet native implementation checksum mismatch"
            )
        ort.disable_telemetry_events()
        if "CPUExecutionProvider" not in ort.get_available_providers():
            raise SensitivityBackendUnavailable(
                "NudeNet CPUExecutionProvider unavailable"
            )
        options = ort.SessionOptions()
        options.intra_op_num_threads = self.profile.cpu_threads
        options.inter_op_num_threads = 1
        cv2.setNumThreads(self.profile.cpu_threads)
        session = ort.InferenceSession(
            str(self.model_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        if session.get_providers() != ["CPUExecutionProvider"]:
            raise SensitivityBackendUnavailable(
                "NudeNet actual provider must be CPU only"
            )
        # 3.4.2 constructor ignores providers. Supply only that narrow initialization;
        # detect still uses the unmodified, content-verified native implementation.
        model = object.__new__(NudeDetector)
        model.onnx_session = session
        model.input_width = model.input_height = 640
        model.input_name = session.get_inputs()[0].name
        if session.get_inputs()[0].type != "tensor(float)":
            raise SensitivityError("NudeNet input precision differs from FP32")
        self._model = model
        self.execution = {
            "device": "cpu",
            "precision": "float32",
            "actual_providers": session.get_providers(),
            "cpu_threads": self.profile.cpu_threads,
            "inter_op_threads": 1,
            "native_implementation_sha256": digest,
        }

    def analyze(self, inputs):
        if (
            len(inputs) > self.profile.batch_size
            or not inputs
            or len({x.key for x in inputs}) != len(inputs)
        ):
            raise SensitivityError("Invalid sensitivity batch envelope")
        self.load()
        self.batch_execution = {"inference_input_count": 0}
        results, valid, images = [], [], []
        try:
            for item in inputs:
                try:
                    with item.path.open("rb") as stream:
                        if (
                            hashlib.file_digest(stream, "sha256").hexdigest()
                            != item.sha256
                        ):
                            raise SensitivityError("Prepared input identity changed")
                    with Image.open(item.path) as opened:
                        if (
                            opened.size != (item.width, item.height)
                            or opened.getexif().get(274, 1) != 1
                            or getattr(opened, "n_frames", 1) != 1
                        ):
                            raise SensitivityError(
                                "Input dimensions/orientation/frame count contradict prepared identity"
                            )
                        images.append(opened.convert("RGB"))
                    valid.append(item)
                except (OSError, UnidentifiedImageError) as error:
                    results.append(
                        SensitivityPrediction(
                            item.key,
                            item.sha256,
                            failure=f"prepared_image_read_failed: {error}",
                        )
                    )
            if self.profile.device == "mps" and valid:
                import torch

                with torch.inference_mode():
                    tensor = torch.stack([self._transform(im) for im in images]).to(
                        "mps"
                    )
                    self.batch_execution["inference_input_count"] = len(valid)
                    logits = self._model(tensor).logits.float()
                    if logits.device.type != "mps":
                        raise SensitivityError("Freepik logits device differs from MPS")
                    probabilities = logits.softmax(dim=-1).cpu().tolist()
                torch.mps.synchronize()
                for item, scores in zip(valid, probabilities, strict=True):
                    dist = dict(
                        zip(self.profile.definitions["labels"], scores, strict=True)
                    )
                    events = self.profile.basis["cumulative_probabilities"]["events"]
                    results.append(
                        SensitivityPrediction(
                            item.key,
                            item.sha256,
                            {
                                "classification_distribution": {
                                    "taxonomy": self.profile.definitions["taxonomy"],
                                    "score_semantics": "categorical_probability",
                                    "probabilities": dist,
                                },
                                "cumulative_probabilities": {
                                    name: sum(dist[k] for k in keys)
                                    for name, keys in events.items()
                                },
                            },
                        )
                    )
            elif valid:
                for item in valid:
                    import cv2

                    if cv2.imread(str(item.path)) is None:
                        results.append(
                            SensitivityPrediction(
                                item.key,
                                item.sha256,
                                failure="native_image_decode_failed",
                            )
                        )
                        continue
                    self.batch_execution["inference_input_count"] += 1
                    raw = self._model.detect(str(item.path))
                    instances = []
                    for row in raw:
                        x, y, w, h = row["box"]
                        instances.append(
                            {
                                "label": row["class"],
                                "score": row["score"],
                                "box_xyxy": [x, y, x + w, y + h],
                            }
                        )
                    results.append(
                        SensitivityPrediction(
                            item.key,
                            item.sha256,
                            {
                                "region_detections": {
                                    "taxonomy": self.profile.definitions["taxonomy"],
                                    "score_semantics": "model_detection_score",
                                    "coordinate_system": "input_evidence_pixels_xyxy",
                                    "input_dimensions": {
                                        "width": item.width,
                                        "height": item.height,
                                    },
                                    "instances": instances,
                                }
                            },
                        )
                    )
            return tuple(results)
        finally:
            for im in images:
                im.close()

    def close(self):
        self._model = self._transform = None
        gc.collect()
        if self.profile.device == "mps" and self.execution is not None:
            import torch

            torch.mps.empty_cache()


def configured_detectors(configuration):
    return tuple(
        LocalSensitivityDetector(PROFILES[name], Path(item["model_path"]))
        for name, item in configuration["models"].items()
        if item["enabled"]
    )
