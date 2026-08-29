"""Reusable local image embeddings backed by immutable Artifacts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from importlib.metadata import PackageNotFoundError, version
import math
from pathlib import Path
import struct
from typing import Any, Protocol

from PIL import Image

from ._artifact_types import (
    ArtifactIntegrity,
    ArtifactRecord,
)
from ._work_types import (
    DependencyKind,
    LeaseLost,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    upstream_dependency,
)
from .artifact import ArtifactStore
from .work import WorkStore


class EmbeddingError(RuntimeError):
    """Base error for local embedding production or validation."""


class EmbeddingBackendUnavailable(EmbeddingError):
    """Raised when a configured local model cannot be loaded without network access."""


class InvalidEmbedding(EmbeddingError):
    """Raised when a backend returns an unusable vector."""


@dataclass(frozen=True, slots=True)
class EmbeddingProfile:
    """Semantic output properties; model identity belongs to the encoder."""

    name: str
    dimensions: int
    normalization: str = "model_native"
    dtype: str = "float32-le"

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("embedding profile name must be non-empty")
        if self.dimensions < 1:
            raise ValueError("embedding dimensions must be positive")
        if self.normalization not in {"model_native", "unit_length"}:
            raise ValueError("unsupported embedding normalization")
        if self.dtype != "float32-le":
            raise ValueError("only little-endian float32 embeddings are supported")


@dataclass(frozen=True, slots=True)
class EmbeddingOutcome:
    work: WorkRecord
    artifact: ArtifactRecord | None
    reused: bool


class ImageEmbeddingEncoder(Protocol):
    """Small adapter boundary for one locally available image model."""

    @property
    def identity(self) -> str: ...

    def encode_image(self, image_path: Path) -> Sequence[float]: ...


class ChineseCLIPEncoder:
    """AI Album-compatible ChineseCLIP inference with local-only model loading."""

    def __init__(
        self,
        *,
        revision: str,
        model_id: str = "OFA-Sys/chinese-clip-vit-huge-patch14",
        device: str = "cpu",
    ) -> None:
        if not model_id.strip() or not revision.strip() or not device.strip():
            raise ValueError("model id, pinned revision, and device must be non-empty")
        self.model_id = model_id
        self.revision = revision
        self.device = device
        self._model: Any | None = None
        self._processor: Any | None = None

    @property
    def identity(self) -> str:
        return (
            f"transformers-chinese-clip:{self.model_id}@{self.revision};"
            f"transformers={_package_version('transformers')};"
            f"torch={_package_version('torch')};device={self.device}"
        )

    def encode_image(self, image_path: Path) -> Sequence[float]:
        model, processor, torch = self._load()
        with Image.open(image_path) as opened:
            image = opened.convert("RGB")
        inputs = processor(images=image, return_tensors="pt")
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        with torch.no_grad():
            features = model.get_image_features(**inputs)
        return tuple(
            float(value) for value in features.detach().cpu().flatten().tolist()
        )

    def _load(self) -> tuple[Any, Any, Any]:
        if self._model is not None and self._processor is not None:
            import torch

            return self._model, self._processor, torch
        try:
            import torch
            from transformers import ChineseCLIPModel, ChineseCLIPProcessor
        except ImportError as error:
            raise EmbeddingBackendUnavailable(
                "ChineseCLIP requires the local-models optional dependencies"
            ) from error
        try:
            self._model = ChineseCLIPModel.from_pretrained(
                self.model_id,
                revision=self.revision,
                local_files_only=True,
            ).to(self.device)
            self._model.eval()
            self._processor = ChineseCLIPProcessor.from_pretrained(
                self.model_id,
                revision=self.revision,
                local_files_only=True,
            )
        except (OSError, ValueError) as error:
            raise EmbeddingBackendUnavailable(
                "the pinned ChineseCLIP model is not available locally"
            ) from error
        return self._model, self._processor, torch


class EmbeddingProducer:
    """Encode one existing rendition/frame Artifact into an immutable vector."""

    def __init__(self, database_path: Path, encoder: ImageEmbeddingEncoder) -> None:
        self.database_path = Path(database_path)
        self.encoder = encoder
        self.work = WorkStore(self.database_path)
        self.artifacts = ArtifactStore(self.database_path)

    def produce(
        self,
        run_id: str,
        input_work_id: str,
        *,
        profile: EmbeddingProfile,
        owner: str = "builtin-image-embedding",
    ) -> EmbeddingOutcome:
        input_work, input_artifact = _attached_visual_artifact(
            self.work, self.artifacts, run_id, input_work_id
        )
        spec = WorkSpec(
            capability="image-embedding",
            producer_identity="builtin-local-image-embedding-v1",
            dependencies=(
                *(
                    dependency
                    for dependency in input_work.spec.dependencies
                    if dependency.kind
                    in {DependencyKind.SOURCE_REVISION, DependencyKind.SOURCE_CONTENT}
                ),
                upstream_dependency(input_work),
                WorkDependency(
                    DependencyKind.MODEL, "encoder_identity", self.encoder.identity
                ),
                WorkDependency(DependencyKind.PARAMETER, "profile_name", profile.name),
                WorkDependency(
                    DependencyKind.PARAMETER, "dimensions", str(profile.dimensions)
                ),
                WorkDependency(DependencyKind.PARAMETER, "dtype", profile.dtype),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "normalization",
                    profile.normalization,
                ),
            ),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            produced = self.artifacts.artifacts_for_work(record.work_id)
            if produced and produced[0].integrity is ArtifactIntegrity.AVAILABLE:
                return EmbeddingOutcome(record, produced[0], True)
            record = self.work.ensure_work(run_id, spec)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return EmbeddingOutcome(record, None, False)
        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=30),
            work_id=record.work_id,
        )
        if not leases:
            return EmbeddingOutcome(self.work.get_work(record.work_id), None, False)
        lease = leases[0]
        draft = self.artifacts.create_draft(lease, suffix=".f32")
        try:
            vector = _validated_vector(
                self.encoder.encode_image(input_artifact.path), profile
            )
            draft.path.write_bytes(struct.pack(f"<{len(vector)}f", *vector))
            self.artifacts.require_available(input_artifact.artifact_id)
            completed, artifact = self.artifacts.publish(
                lease,
                draft,
                suffix=".f32",
                media_type="application/vnd.mediasense.embedding-f32le",
                role="embedding",
                output={
                    "dimensions": profile.dimensions,
                    "dtype": profile.dtype,
                    "encoder_identity": self.encoder.identity,
                    "input_work_id": input_work.work_id,
                    "normalization": profile.normalization,
                    "profile": profile.name,
                },
            )
            return EmbeddingOutcome(completed, artifact, False)
        except Exception as error:
            draft.path.unlink(missing_ok=True)
            try:
                failed = self.work.fail_work(
                    lease,
                    error_code="embedding_failed",
                    message=str(error) or type(error).__name__,
                    retryable=False,
                )
            except LeaseLost:
                failed = self.work.get_work(record.work_id)
            return EmbeddingOutcome(failed, None, False)


def read_embedding(
    artifact: ArtifactRecord, profile: EmbeddingProfile
) -> tuple[float, ...]:
    expected_size = profile.dimensions * 4
    payload = artifact.path.read_bytes()
    if len(payload) != expected_size:
        raise InvalidEmbedding(
            f"embedding byte size {len(payload)} does not match {expected_size}"
        )
    vector = struct.unpack(f"<{profile.dimensions}f", payload)
    return _validated_vector(vector, profile)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("cosine similarity requires equal non-empty vectors")
    dot = sum(float(x) * float(y) for x, y in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
    right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("cosine similarity is undefined for zero vectors")
    return dot / (left_norm * right_norm)


def _validated_vector(
    values: Sequence[float], profile: EmbeddingProfile
) -> tuple[float, ...]:
    vector = tuple(float(value) for value in values)
    if len(vector) != profile.dimensions:
        raise InvalidEmbedding(
            f"embedding dimensions {len(vector)} do not match {profile.dimensions}"
        )
    if not all(math.isfinite(value) for value in vector):
        raise InvalidEmbedding("embedding contains a non-finite value")
    if not any(value != 0 for value in vector):
        raise InvalidEmbedding("embedding must not be a zero vector")
    if profile.normalization == "unit_length":
        norm = math.sqrt(sum(value * value for value in vector))
        vector = tuple(value / norm for value in vector)
    return vector


def _attached_visual_artifact(
    work: WorkStore,
    artifacts: ArtifactStore,
    run_id: str,
    work_id: str,
) -> tuple[WorkRecord, ArtifactRecord]:
    record = next(
        (item for item in work.list_run_work(run_id) if item.work_id == work_id), None
    )
    if record is None or record.spec.capability not in {
        "image-rendition",
        "video-frame",
    }:
        raise ValueError("visual input Work is not attached to this run")
    if record.status is not WorkStatus.SUCCEEDED:
        raise ValueError("visual input Work must succeed first")
    produced = artifacts.artifacts_for_work(record.work_id)
    if not produced or produced[0].integrity is not ArtifactIntegrity.AVAILABLE:
        raise ValueError("visual input Artifact must be available")
    return record, artifacts.require_available(produced[0].artifact_id)


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unavailable"


__all__ = [
    "ChineseCLIPEncoder",
    "EmbeddingBackendUnavailable",
    "EmbeddingError",
    "EmbeddingOutcome",
    "EmbeddingProducer",
    "EmbeddingProfile",
    "ImageEmbeddingEncoder",
    "InvalidEmbedding",
    "cosine_similarity",
    "read_embedding",
]
