"""Local content-sensitivity observations with explicit detector provenance."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta, datetime, timezone
import json
import math
from pathlib import Path
from typing import Protocol


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


from ._sensitivity_profiles import (
    SensitivityError,
    SensitivityBackendUnavailable,
    NamedSensitivityProfile,
    SensitivityInput,
    SensitivityPrediction,
)
from ._sensitivity_values import validate_named_value, validate_observation


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
    profile: NamedSensitivityProfile
    execution: dict | None

    @property
    def identity(self) -> str: ...

    @property
    def declaration(self) -> Mapping[str, object]: ...

    def analyze(
        self, inputs: Sequence[SensitivityInput]
    ) -> Sequence[SensitivityPrediction]: ...

    def close(self) -> None: ...


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
        self.admit_model = None

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        input_work_id: str,
        *,
        profile: NamedSensitivityProfile,
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
        profile: NamedSensitivityProfile,
        owner: str = "builtin-content-sensitivity",
    ) -> dict[str, SensitivityOutcome]:
        if not isinstance(profile, NamedSensitivityProfile):
            raise ValueError(
                "V1 sensitivity is read-only; new work requires a declared named-value profile"
            )
        if self.detector.profile.identity != profile.identity:
            raise SensitivityError(
                "Detector declaration does not match the frozen profile"
            )
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
            try:
                outcomes.update(self._produce_named(tuple(ready), profile))
            except Exception:
                # A dead execution owner must not leave claimed work pretending
                # to run, or turn a protocol defect into a bad-source observation.
                for item in ready:
                    if (
                        self.work.get_work(item.record.work_id).status
                        is WorkStatus.RUNNING
                    ):
                        self.work.invalidate_work(
                            item.record.work_id, "sensitivity_execution_failed"
                        )
                raise
        return outcomes

    def _prepare(
        self,
        run_id: str,
        relative_path: Path,
        input_work_id: str,
        *,
        profile: NamedSensitivityProfile,
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
        spec = WorkSpec(
            capability="content-sensitivity",
            producer_identity="builtin-local-content-sensitivity-v2",
            dependencies=(
                upstream_dependency(input_work),
                WorkDependency(
                    DependencyKind.MODEL, "detector_identity", self.detector.identity
                ),
                WorkDependency(
                    DependencyKind.PARAMETER, "profile_identity", profile.identity
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "subject_relative_path",
                    relative_path.as_posix(),
                ),
                WorkDependency(DependencyKind.PARAMETER, "profile_name", profile.name),
            ),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            observations = _observations(record.output)
            if isinstance(profile, NamedSensitivityProfile):
                if len(observations) != 1:
                    raise SensitivityError("Committed sensitivity output is incomplete")
                validate_observation(observations[0])
            return SensitivityOutcome(record, observations, True)
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

    def _produce_named(self, prepared, profile):
        from copy import deepcopy
        import time

        inputs = []
        for item in prepared:
            output = item.input_work.output
            # Dimensions are established by preparation, never from source metadata.
            dimensions = output["value"]
            if "width" not in dimensions:
                raise SensitivityError("Prepared visual Work has no dimension proof")
            inputs.append(
                SensitivityInput(
                    item.input_work_id,
                    item.input_artifact.path,
                    item.input_artifact.digest,
                    dimensions["width"],
                    dimensions["height"],
                )
            )
        expected_identity = self.detector.identity
        expected_profile_identity = profile.identity
        from uuid import uuid4

        batch_id = "sensitivity-batch:" + uuid4().hex
        load_seconds = None
        try:
            if self.admit_model is not None:
                self.admit_model()
            load = getattr(self.detector, "load", None)
            if callable(load):
                loaded = load()
                load_seconds = (
                    self.detector.execution.get("load_seconds")
                    if loaded is True
                    else 0.0
                    if loaded is False
                    else None
                )
            started = time.monotonic()
            predictions = tuple(self.detector.analyze(tuple(inputs)))
        except SensitivityBackendUnavailable:
            for item in prepared:
                self.work.invalidate_work(
                    item.record.work_id, "sensitivity_backend_unavailable"
                )
            raise
        elapsed = time.monotonic() - started
        observed = datetime.now(timezone.utc).isoformat()
        if (
            self.detector.identity != expected_identity
            or profile.identity != expected_profile_identity
        ):
            raise SensitivityError(
                "Adapter mutated its frozen semantic declaration during execution"
            )
        by_key = {p.key: p for p in predictions}
        if len(by_key) != len(predictions) or set(by_key) != {i.key for i in inputs}:
            raise SensitivityError(
                "Sensitivity batch has missing, duplicate or unassignable outputs"
            )
        # Validate the whole batch before committing any attributable success.
        for inp in inputs:
            prediction = by_key[inp.key]
            if prediction.sha256 != inp.sha256 or (
                (prediction.values is None) == (prediction.failure is None)
            ):
                raise SensitivityError(
                    "Sensitivity output identity or outcome is ambiguous"
                )
            if prediction.values is not None:
                if set(prediction.values) != set(
                    profile.definitions["declared_properties"]
                ):
                    raise SensitivityError("Adapter returned undeclared properties")
                validate_named_value(
                    {
                        "detector_identity": self.detector.identity,
                        "profile": profile.name,
                        **prediction.values,
                    },
                    profile.definitions,
                    profile.basis,
                    {"width": inp.width, "height": inp.height},
                )
        outcomes = {}
        actual = self.detector.execution or {}
        inference_count = getattr(self.detector, "batch_execution", {}).get(
            "inference_input_count"
        )
        if inference_count is not None and (
            type(inference_count) is not int or not 0 <= inference_count <= len(inputs)
        ):
            raise SensitivityError("Invalid actual inference batch size")
        execution = {
            "schema_version": 1,
            "batch": {
                "batch_id": batch_id,
                "accounting_run_id": prepared[0].lease.run_id,
                "observed_at": observed,
                "input_count": len(inputs),
                "inference_input_count": inference_count,
                "processing_wall_seconds": elapsed,
                "load_wall_seconds": load_seconds,
                "actual_device": actual.get("device"),
                "precision": actual.get("precision"),
                "measured_memory_bytes": actual.get("measured_memory_bytes"),
            },
        }
        for item in prepared:
            prediction = by_key[item.input_work_id]
            if prediction.failure is not None:
                outcomes[item.input_work_id] = self._fail_prepared(
                    item, SensitivityError(prediction.failure), execution
                )
                continue
            self.artifacts.require_available(item.input_artifact.artifact_id)
            observation = {
                "name": "content_sensitivity",
                "status": "available",
                "value": {
                    "detector_identity": self.detector.identity,
                    "profile": profile.name,
                    **prediction.values,
                },
                "basis": deepcopy(profile.basis),
                "provenance": {
                    "detector_identity": self.detector.identity,
                    "profile": profile.name,
                    "model_id": profile.model_id,
                    "revision": profile.revision,
                    "files_sha256": profile.files,
                    "producer": profile.adapter_revision,
                    "observed_at": observed,
                    "input_work_id": item.input_work_id,
                    "input_sha256": item.input_artifact.digest,
                    "relative_path": item.relative_path.as_posix(),
                    "definitions": deepcopy(profile.definitions),
                    "actual_execution": deepcopy(self.detector.execution),
                },
                "qualifications": [
                    {
                        "code": "model_observation_limits",
                        "effect": "limits_interpretation",
                        "message": "Model evidence applies only to this input; no calibration, complete detection, represented-member coverage or remote authorization is implied.",
                    }
                ],
            }
            completed = self.work.succeed_work(
                item.lease,
                {
                    "observations": [observation],
                    "subject": {"relative_path": item.relative_path.as_posix()},
                    "execution": deepcopy(execution),
                },
            )
            outcomes[item.input_work_id] = SensitivityOutcome(
                completed, (observation,), False
            )
        return outcomes

    def _fail_prepared(
        self,
        prepared: _PreparedSensitivity,
        error: BaseException,
        execution: dict,
    ) -> SensitivityOutcome:
        from copy import deepcopy

        profile = self.detector.profile
        observation = {
            "name": "content_sensitivity",
            "status": "failed",
            "basis": {"code": "sensitivity_detection_failed", "message": str(error)},
            "provenance": {
                "detector_identity": self.detector.identity,
                "profile": profile.name,
                "model_id": profile.model_id,
                "revision": profile.revision,
                "files_sha256": profile.files,
                "definitions": deepcopy(profile.definitions),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "producer": profile.adapter_revision,
                "input_work_id": prepared.input_work_id,
                "input_sha256": prepared.input_artifact.digest,
                "relative_path": prepared.relative_path.as_posix(),
                "actual_execution": deepcopy(self.detector.execution),
            },
            "qualifications": [
                {
                    "code": "sensitivity_unavailable",
                    "effect": "limits_interpretation",
                    "message": str(error) or type(error).__name__,
                }
            ],
        }
        try:
            failed = self.work.fail_work(
                prepared.lease,
                error_code="sensitivity_detection_failed",
                message=str(error) or type(error).__name__,
                retryable=False,
                output={
                    "observations": [observation],
                    "subject": {"relative_path": prepared.relative_path.as_posix()},
                    "execution": deepcopy(execution),
                },
            )
        except LeaseLost:
            failed = self.work.get_work(prepared.record.work_id)
        return SensitivityOutcome(failed, (observation,), False)


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


__all__ = [
    "Detection",
    "NSFW_BINARY_PROFILE_V1",
    "NUDENET_BODY_EXPOSURE_PROFILE_V1",
    "SensitivityBackendUnavailable",
    "SensitivityDetector",
    "SensitivityError",
    "SensitivityOutcome",
    "SensitivityProducer",
    "SensitivityProfile",
    "SensitivityScore",
    "SensitivityThreshold",
    "classify_detections",
]
