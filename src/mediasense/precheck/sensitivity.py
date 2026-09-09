"""Local content-sensitivity observations with explicit detector provenance."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version, distribution
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from ._artifact_types import ArtifactIntegrity, ArtifactRecord
from ._work_types import (
    DependencyKind,
    LeaseLost,
    WorkDependency,
    WorkLease,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    upstream_dependency,
)
from .artifact import ArtifactStore
from .work import WorkStore


class SensitivityError(RuntimeError):
    """Base error for local sensitivity analysis."""


class SensitivityBackendUnavailable(SensitivityError):
    """Raised when a configured detector is not locally available."""


@dataclass(frozen=True, slots=True)
class Detection:
    label: str
    score: float

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("detection label must be non-empty")
        if not math.isfinite(self.score) or not 0 <= self.score <= 1:
            raise ValueError("detection score must be between zero and one")


@dataclass(frozen=True, slots=True)
class SensitivityThreshold:
    label: str
    threshold: float
    description: str = ""

    def __post_init__(self) -> None:
        if not self.label.strip():
            raise ValueError("sensitivity threshold label must be non-empty")
        if not math.isfinite(self.threshold) or self.threshold < 0:
            raise ValueError("sensitivity threshold must be nonnegative")


@dataclass(frozen=True, slots=True)
class SensitivityProfile:
    name: str
    thresholds: tuple[SensitivityThreshold, ...]
    mild_ratio: float = 1 / 3

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("sensitivity profile name must be non-empty")
        if not self.thresholds:
            raise ValueError("sensitivity profile requires thresholds")
        labels = [threshold.label for threshold in self.thresholds]
        if len(labels) != len(set(labels)):
            raise ValueError("sensitivity threshold labels must be unique")
        if not math.isfinite(self.mild_ratio) or not 0 < self.mild_ratio <= 1:
            raise ValueError("sensitivity mild ratio must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class SensitivityScore:
    label: str
    score: float
    threshold: float
    mild_threshold: float
    sensitive: bool
    mild_sensitive: bool
    description: str


@dataclass(frozen=True, slots=True)
class SensitivityOutcome:
    work: WorkRecord
    observations: tuple[dict[str, object], ...]
    reused: bool


@dataclass(frozen=True, slots=True)
class _PreparedSensitivity:
    input_work_id: str
    relative_path: Path
    input_work: WorkRecord
    input_artifact: ArtifactRecord
    record: WorkRecord
    lease: WorkLease


class SensitivityDetector(Protocol):
    @property
    def identity(self) -> str: ...

    def detect(self, image_path: Path) -> Sequence[Detection]: ...


class NudeNetDetector:
    """NudeNet 3.x adapter; package and bundled weights must already be local."""

    def __init__(self, *, device: str = "cpu") -> None:
        self.device = device
        self._detector: Any | None = None
        self._identity: str | None = None

    @property
    def identity(self) -> str:
        if self._identity is not None:
            return self._identity
        try:
            weights = self._weights()
            with weights.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
        except (SensitivityBackendUnavailable, OSError):
            digest = "unavailable"
        identity = f"nudenet:NudeDetector@nudenet-{_package_version('nudenet')};weights=sha256:{digest};device={self.device};onnxruntime={_package_version('onnxruntime')}"
        if "unavailable" not in identity:
            self._identity = identity
        return identity

    @staticmethod
    def _weights() -> Path:
        try:
            path = Path(distribution("nudenet").locate_file("nudenet/320n.onnx"))
        except PackageNotFoundError as error:
            raise SensitivityBackendUnavailable(
                "NudeNet local package and bundled weights are unavailable"
            ) from error
        if not path.is_file():
            raise SensitivityBackendUnavailable(
                "NudeNet bundled weights are missing; automatic downloads are disabled"
            )
        return path

    def detect(self, image_path: Path) -> Sequence[Detection]:
        detector = self._load()
        raw = detector.detect(str(image_path))
        if not isinstance(raw, list):
            raise SensitivityError("NudeNet returned a non-list result")
        if any(
            not isinstance(item, Mapping) or "class" not in item or "score" not in item
            for item in raw
        ):
            raise SensitivityError("NudeNet returned a malformed detection")
        return tuple(
            Detection(label=str(item["class"]), score=float(item["score"]))
            for item in raw
        )

    def _load(self) -> Any:
        if self._detector is not None:
            return self._detector
        try:
            import onnxruntime

            onnxruntime.disable_telemetry_events()
            from nudenet import NudeDetector as Detector
        except ImportError as error:
            raise SensitivityBackendUnavailable(
                "NudeNet requires the local-models optional dependencies"
            ) from error
        weights = self._weights()
        provider = {"cpu": "CPUExecutionProvider", "cuda": "CUDAExecutionProvider"}.get(
            self.device
        )
        if provider is None or provider not in onnxruntime.get_available_providers():
            raise SensitivityBackendUnavailable(
                f"NudeNet does not support the requested {self.device} backend locally"
            )
        try:
            self._detector = Detector(model_path=str(weights), providers=[provider])
        except (OSError, ValueError, RuntimeError) as error:
            raise SensitivityBackendUnavailable(
                "NudeNet could not load its local weights/backend"
            ) from error
        return self._detector


class TransformersNSFWDetector:
    """Pinned Hugging Face image classifier loaded without network access."""

    def __init__(
        self,
        *,
        revision: str,
        model_id: str = "Falconsai/nsfw_image_detection",
        device: str = "cpu",
    ) -> None:
        if not model_id.strip() or not revision.strip():
            raise ValueError("model id and pinned revision must be non-empty")
        self.device = device
        self.model_id = model_id
        self.revision = revision
        self._classifier: Any | None = None

    @property
    def identity(self) -> str:
        return (
            f"transformers-image-classification:{self.model_id}@{self.revision};"
            f"transformers={_package_version('transformers')};"
            f"torch={_package_version('torch')};device={self.device}"
        )

    def detect(self, image_path: Path) -> Sequence[Detection]:
        return self.detect_many((image_path,))[0]

    def detect_many(self, image_paths: Sequence[Path]) -> Sequence[Sequence[Detection]]:
        classifier = self._load()
        images = []
        try:
            for image_path in image_paths:
                with Image.open(image_path) as opened:
                    images.append(opened.convert("RGB"))
            import torch

            model, processor = classifier
            inputs = processor(images=images, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                probabilities = model(**inputs).logits.softmax(dim=-1).cpu().tolist()
            return tuple(
                tuple(
                    Detection(
                        label=str(model.config.id2label[index]), score=float(score)
                    )
                    for index, score in enumerate(scores)
                )
                for scores in probabilities
            )
        finally:
            for image in images:
                image.close()

    def _load(self) -> Any:
        if self._classifier is not None:
            return self._classifier
        try:
            from transformers import AutoImageProcessor, AutoModelForImageClassification

            processor = AutoImageProcessor.from_pretrained(
                self.model_id, revision=self.revision, local_files_only=True
            )
            model = AutoModelForImageClassification.from_pretrained(
                self.model_id, revision=self.revision, local_files_only=True
            )
            model.to(self.device).eval()
        except (
            ImportError,
            OSError,
            ValueError,
            RuntimeError,
            AssertionError,
        ) as error:
            raise SensitivityBackendUnavailable(
                "The pinned NSFW model, processor, or requested local backend is unavailable; downloads are disabled"
            ) from error
        self._classifier = (model, processor)
        return self._classifier


NSFW_BINARY_PROFILE_V1 = SensitivityProfile(
    name="falconsai-nsfw-c90-thresholds-v1",
    thresholds=(
        SensitivityThreshold("nsfw", 0.02, "NSFW"),
        SensitivityThreshold("normal", 99.0, "normal"),
    ),
)


NUDENET_BODY_EXPOSURE_PROFILE_V1 = SensitivityProfile(
    name="nudenet-body-exposure-c90-thresholds-v1",
    thresholds=tuple(
        SensitivityThreshold(label, threshold, description)
        for label, description, threshold in (
            ("FEMALE_GENITALIA_COVERED", "covered female genitalia", 0.5),
            ("FACE_FEMALE", "female face", 99.0),
            ("BUTTOCKS_EXPOSED", "exposed buttocks", 0.5),
            ("FEMALE_BREAST_EXPOSED", "exposed female breast", 0.5),
            ("FEMALE_GENITALIA_EXPOSED", "exposed female genitalia", 0.4),
            ("MALE_BREAST_EXPOSED", "exposed male breast", 99.0),
            ("ANUS_EXPOSED", "exposed anus", 0.5),
            ("FEET_EXPOSED", "exposed feet", 99.0),
            ("BELLY_COVERED", "covered belly", 99.0),
            ("FEET_COVERED", "covered feet", 99.0),
            ("ARMPITS_COVERED", "covered armpits", 99.0),
            ("ARMPITS_EXPOSED", "exposed armpits", 99.0),
            ("FACE_MALE", "male face", 99.0),
            ("BELLY_EXPOSED", "exposed belly", 99.0),
            ("MALE_GENITALIA_EXPOSED", "exposed male genitalia", 0.6),
            ("ANUS_COVERED", "covered anus", 0.5),
            ("FEMALE_BREAST_COVERED", "covered female breast", 0.5),
            ("BUTTOCKS_COVERED", "covered buttocks", 0.5),
        )
    ),
)


class SensitivityProducer:
    """Turn one visual Artifact into one explicit local detector observation."""

    def __init__(self, database_path: Path, detector: SensitivityDetector) -> None:
        self.database_path = Path(database_path)
        self.detector = detector
        self.work = WorkStore(self.database_path)
        self.artifacts = ArtifactStore(self.database_path)

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        input_work_id: str,
        *,
        profile: SensitivityProfile,
        owner: str = "builtin-content-sensitivity",
    ) -> SensitivityOutcome:
        return self.produce_many(
            run_id,
            ((relative_path, input_work_id),),
            profile=profile,
            owner=owner,
        )[input_work_id]

    def produce_many(
        self,
        run_id: str,
        inputs: Sequence[tuple[Path, str]],
        *,
        profile: SensitivityProfile,
        owner: str = "builtin-content-sensitivity",
    ) -> dict[str, SensitivityOutcome]:
        normalized = tuple(
            (_validated_relative_path(path), work_id) for path, work_id in inputs
        )
        work_ids = tuple(work_id for _path, work_id in normalized)
        if len(set(work_ids)) != len(work_ids):
            raise ValueError("sensitivity batch inputs must be unique")
        outcomes: dict[str, SensitivityOutcome] = {}
        ready: list[_PreparedSensitivity] = []
        for relative_path, input_work_id in normalized:
            prepared = self._prepare(
                run_id,
                relative_path,
                input_work_id,
                profile=profile,
                owner=owner,
            )
            if isinstance(prepared, SensitivityOutcome):
                outcomes[input_work_id] = prepared
            else:
                ready.append(prepared)
        if ready:
            outcomes.update(self._produce_prepared(tuple(ready), profile))
        return outcomes

    def _prepare(
        self,
        run_id: str,
        relative_path: Path,
        input_work_id: str,
        *,
        profile: SensitivityProfile,
        owner: str,
    ) -> _PreparedSensitivity | SensitivityOutcome:
        relative_path = _validated_relative_path(relative_path)
        input_work, input_artifact = _attached_visual_artifact(
            self.work,
            self.artifacts,
            run_id,
            input_work_id,
            relative_path,
        )
        threshold_value = json.dumps(
            [
                {
                    "description": item.description,
                    "label": item.label,
                    "threshold": item.threshold,
                }
                for item in profile.thresholds
            ],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        spec = WorkSpec(
            capability="content-sensitivity",
            producer_identity="builtin-local-content-sensitivity-v1",
            dependencies=(
                upstream_dependency(input_work),
                WorkDependency(
                    DependencyKind.MODEL, "detector_identity", self.detector.identity
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "subject_relative_path",
                    relative_path.as_posix(),
                ),
                WorkDependency(DependencyKind.PARAMETER, "profile_name", profile.name),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "thresholds",
                    threshold_value,
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "mild_ratio",
                    format(profile.mild_ratio, ".17g"),
                ),
            ),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            return SensitivityOutcome(record, _observations(record.output), True)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return SensitivityOutcome(record, (), False)
        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=15),
            work_id=record.work_id,
        )
        if not leases:
            current = self.work.get_work(record.work_id)
            return SensitivityOutcome(current, _observations(current.output), False)
        return _PreparedSensitivity(
            input_work_id,
            relative_path,
            input_work,
            input_artifact,
            record,
            leases[0],
        )

    def _produce_prepared(
        self,
        prepared: tuple[_PreparedSensitivity, ...],
        profile: SensitivityProfile,
    ) -> dict[str, SensitivityOutcome]:
        try:
            detect_many = getattr(self.detector, "detect_many", None)
            if callable(detect_many):
                raw_detections = tuple(
                    detect_many(tuple(item.input_artifact.path for item in prepared))
                )
            else:
                raw_detections = tuple(
                    self.detector.detect(item.input_artifact.path) for item in prepared
                )
            if len(raw_detections) != len(prepared):
                raise SensitivityError(
                    "sensitivity batch output count does not match input"
                )
        except SensitivityBackendUnavailable:
            for item in prepared:
                self.work.invalidate_work(
                    item.record.work_id, "sensitivity_backend_unavailable"
                )
            raise
        except (SensitivityError, OSError, ValueError) as error:
            if len(prepared) > 1:
                midpoint = len(prepared) // 2
                return {
                    **self._produce_prepared(prepared[:midpoint], profile),
                    **self._produce_prepared(prepared[midpoint:], profile),
                }
            item = prepared[0]
            return {item.input_work_id: self._fail_prepared(item, error)}

        outcomes: dict[str, SensitivityOutcome] = {}
        for item, detections in zip(prepared, raw_detections, strict=True):
            outcomes[item.input_work_id] = self._complete_prepared(
                item, detections, profile
            )
        return outcomes

    def _complete_prepared(
        self,
        prepared: _PreparedSensitivity,
        detections: Sequence[Detection],
        profile: SensitivityProfile,
    ) -> SensitivityOutcome:
        try:
            scores = classify_detections(detections, profile)
            self.artifacts.require_available(prepared.input_artifact.artifact_id)
            observations = (
                {
                    "name": "content_sensitivity",
                    "status": "available",
                    "value": {
                        "detector_identity": self.detector.identity,
                        "labels": [_score_value(score) for score in scores],
                        "profile": profile.name,
                    },
                    "provenance": {
                        "detector_identity": self.detector.identity,
                        "input_work_id": prepared.input_work.work_id,
                        "profile": profile.name,
                        "relative_path": prepared.relative_path.as_posix(),
                    },
                },
            )
            completed = self.work.succeed_work(
                prepared.lease,
                {
                    "observations": list(observations),
                    "subject": {"relative_path": prepared.relative_path.as_posix()},
                },
            )
            return SensitivityOutcome(completed, observations, False)
        except (SensitivityError, OSError, ValueError) as error:
            return self._fail_prepared(prepared, error)

    def _fail_prepared(
        self,
        prepared: _PreparedSensitivity,
        error: BaseException,
    ) -> SensitivityOutcome:
        try:
            failed = self.work.fail_work(
                prepared.lease,
                error_code="sensitivity_detection_failed",
                message=str(error) or type(error).__name__,
                retryable=False,
            )
        except LeaseLost:
            failed = self.work.get_work(prepared.record.work_id)
        return SensitivityOutcome(failed, (), False)


def classify_detections(
    detections: Sequence[Detection], profile: SensitivityProfile
) -> tuple[SensitivityScore, ...]:
    thresholds = {item.label: item for item in profile.thresholds}
    maxima: dict[str, float] = {}
    for detection in detections:
        if detection.label not in thresholds:
            raise ValueError(f"unknown sensitivity label: {detection.label}")
        maxima[detection.label] = max(maxima.get(detection.label, 0.0), detection.score)
    classified = []
    for label in sorted(maxima):
        item = thresholds[label]
        mild_threshold = item.threshold * profile.mild_ratio
        score = maxima[label]
        classified.append(
            SensitivityScore(
                label=label,
                score=score,
                threshold=item.threshold,
                mild_threshold=mild_threshold,
                sensitive=score >= item.threshold,
                mild_sensitive=score >= mild_threshold,
                description=item.description,
            )
        )
    return tuple(classified)


def _score_value(score: SensitivityScore) -> dict[str, object]:
    return {
        "description": score.description,
        "label": score.label,
        "mild_sensitive": score.mild_sensitive,
        "mild_threshold": score.mild_threshold,
        "score": score.score,
        "sensitive": score.sensitive,
        "threshold": score.threshold,
    }


def _observations(output: object | None) -> tuple[dict[str, object], ...]:
    if not isinstance(output, Mapping) or not isinstance(
        output.get("observations"), list
    ):
        return ()
    return tuple(
        dict(item) for item in output["observations"] if isinstance(item, Mapping)
    )


def _attached_visual_artifact(
    work: WorkStore,
    artifacts: ArtifactStore,
    run_id: str,
    work_id: str,
    relative_path: Path,
) -> tuple[WorkRecord, ArtifactRecord]:
    try:
        record = work.get_run_work(run_id, work_id)
    except KeyError as error:
        raise ValueError("visual input Work is not attached to this run") from error
    if record.spec.capability not in {
        "image-rendition",
        "video-frame",
    }:
        raise ValueError("visual input Work is not attached to this run")
    if record.status is not WorkStatus.SUCCEEDED:
        raise ValueError("visual input Work must succeed first")
    source_paths = {
        str(json.loads(item.key)[1])
        for item in record.spec.dependencies
        if item.kind is DependencyKind.SOURCE_REVISION
    }
    if relative_path.as_posix() not in source_paths:
        raise ValueError("visual input Work belongs to a different Source Item")
    produced = artifacts.artifacts_for_work(record.work_id)
    if not produced or produced[0].integrity is not ArtifactIntegrity.AVAILABLE:
        raise ValueError("visual input Artifact must be available")
    return record, artifacts.require_available(produced[0].artifact_id)


def _validated_relative_path(path: Path) -> Path:
    path = Path(path)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError(
            "sensitivity subject path must stay relative to its source root"
        )
    return path


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unavailable"


__all__ = [
    "Detection",
    "NSFW_BINARY_PROFILE_V1",
    "NUDENET_BODY_EXPOSURE_PROFILE_V1",
    "NudeNetDetector",
    "SensitivityBackendUnavailable",
    "SensitivityDetector",
    "SensitivityError",
    "SensitivityOutcome",
    "SensitivityProducer",
    "SensitivityProfile",
    "SensitivityScore",
    "SensitivityThreshold",
    "TransformersNSFWDetector",
    "classify_detections",
]
