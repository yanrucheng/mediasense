"""Embedding-based representative frame candidates for local videos."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
import json
from pathlib import Path

from ._artifact_types import ArtifactIntegrity
from ._video_producers import _attached_work
from ._video_types import VideoKeyFrameOutcome, VideoKeyFrameProfile
from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    upstream_dependency,
)
from .artifact import ArtifactStore
from .compression import select_embedding_representative
from .embedding import EmbeddingProfile, read_embedding
from .work import WorkStore


class VideoKeyFrameCandidateProducer:
    """Select a challengeable representative from explicit frame embeddings."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.work = WorkStore(self.database_path)
        self.artifacts = ArtifactStore(self.database_path)

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        frame_embedding_work_ids: Sequence[tuple[str, str]],
        *,
        profile: VideoKeyFrameProfile = VideoKeyFrameProfile(),
        owner: str = "builtin-video-key-frame",
    ) -> VideoKeyFrameOutcome:
        if not frame_embedding_work_ids:
            raise ValueError("video key-frame selection requires frame embeddings")
        frames = tuple(
            _attached_work(self.work, run_id, frame_id, "video-frame")
            for frame_id, _embedding_id in frame_embedding_work_ids
        )
        embeddings = tuple(
            _attached_work(self.work, run_id, embedding_id, "image-embedding")
            for _frame_id, embedding_id in frame_embedding_work_ids
        )
        for frame, embedding in zip(frames, embeddings, strict=True):
            if not any(
                dependency.kind is DependencyKind.UPSTREAM_WORK
                and dependency.key == frame.work_id
                for dependency in embedding.spec.dependencies
            ):
                raise ValueError("embedding Work does not match its video frame")
        subject = Path(relative_path)
        if any(_source_path(frame) != subject for frame in frames):
            raise ValueError("video frames belong to another Source Item")
        vectors = tuple(_embedding_vector(self.artifacts, work) for work in embeddings)
        selected_index = select_embedding_representative(vectors, top_k=profile.top_k)
        source_dependencies = {
            (dependency.kind, dependency.key): dependency
            for frame in frames
            for dependency in frame.spec.dependencies
            if dependency.kind
            in {DependencyKind.SOURCE_REVISION, DependencyKind.SOURCE_CONTENT}
        }
        frame_order = [frame.work_id for frame in frames]
        dependencies = (
            *source_dependencies.values(),
            *(upstream_dependency(frame) for frame in frames),
            *(upstream_dependency(embedding) for embedding in embeddings),
            WorkDependency(
                DependencyKind.PARAMETER,
                "subject_relative_path",
                subject.as_posix(),
            ),
            WorkDependency(
                DependencyKind.PARAMETER,
                "frame_order",
                json.dumps(frame_order, separators=(",", ":")),
            ),
            WorkDependency(
                DependencyKind.PARAMETER,
                "top_k",
                str(profile.top_k),
            ),
        )
        spec = WorkSpec(
            capability="video-key-frame-candidate",
            producer_identity="builtin-video-key-frame-cosine-v1",
            dependencies=dependencies,
        )
        record = self.work.ensure_work(run_id, spec)
        selected_id = frames[selected_index].work_id
        if record.status is WorkStatus.SUCCEEDED:
            return VideoKeyFrameOutcome(record, selected_id, True)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return VideoKeyFrameOutcome(record, None, False)
        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=5),
            work_id=record.work_id,
        )
        if not leases:
            return VideoKeyFrameOutcome(self.work.get_work(record.work_id), None, False)
        completed = self.work.succeed_work(
            leases[0],
            {
                "candidate": {
                    "frame_count": len(frames),
                    "selected_frame_work_id": selected_id,
                    "top_k": profile.top_k,
                },
                "subject": {"relative_path": subject.as_posix()},
            },
        )
        return VideoKeyFrameOutcome(completed, selected_id, False)


def _source_path(record: WorkRecord) -> Path:
    dependency = next(
        (
            item
            for item in record.spec.dependencies
            if item.kind is DependencyKind.SOURCE_REVISION
        ),
        None,
    )
    if dependency is None:
        raise ValueError("video Work has no source dependency")
    try:
        _dataset_id, relative_path = json.loads(dependency.key)
    except (TypeError, ValueError) as error:
        raise ValueError("video Work has an invalid source dependency") from error
    return Path(relative_path)


def _embedding_vector(
    artifacts: ArtifactStore, record: WorkRecord
) -> tuple[float, ...]:
    if not isinstance(record.output, Mapping) or not isinstance(
        record.output.get("value"), Mapping
    ):
        raise ValueError("embedding Work has an invalid output")
    value = record.output["value"]
    profile = EmbeddingProfile(
        name=str(value["profile"]),
        dimensions=int(value["dimensions"]),
        normalization=str(value["normalization"]),
        dtype=str(value["dtype"]),
    )
    produced = artifacts.artifacts_for_work(record.work_id)
    if not produced or produced[0].integrity is not ArtifactIntegrity.AVAILABLE:
        raise ValueError("embedding Artifact must be available")
    return read_embedding(artifacts.require_available(produced[0].artifact_id), profile)


__all__ = ["VideoKeyFrameCandidateProducer"]
