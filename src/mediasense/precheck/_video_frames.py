"""Per-frame Work/Artifact outcomes over one shared local video decoder."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import timedelta
import math
from pathlib import Path

from PIL import Image

from ._artifact_types import InvalidArtifactDraft
from ._fingerprint import SourceChangedDuringRead
from ._sqlite_scope import connection_scope
from ._video_decoder import (
    PyAVVideoDecoder,
    VideoDecoder,
    VideoDecodeCancelled,
    VideoDecodeLimitExceeded,
)
from ._video_producers import _attached_work, _probe_from_output
from ._video_types import (
    VideoFrameOutcome,
    VideoFrameProfile,
    VideoProcessingError,
    frame_identity,
)
from ._work_types import (
    DependencyKind,
    LeaseLost,
    WorkDependency,
    WorkLease,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
    upstream_dependency,
)
from .artifact import ArtifactStore
from .source_validity import SourceContentProof, SourceValidityStore
from .work import WorkStore


@dataclass(frozen=True, slots=True)
class _PendingFrame:
    target: float
    record: WorkRecord
    lease: WorkLease


class VideoFrameProducer:
    def __init__(
        self,
        database_path: Path,
        *,
        decoder: VideoDecoder | None = None,
        threads: int = 1,
        should_continue: Callable[[], bool] | None = None,
    ) -> None:
        if threads < 1:
            raise ValueError("video decoder thread count must be positive")
        self.database_path = Path(database_path)
        self.validity = SourceValidityStore(self.database_path)
        self.work = WorkStore(self.database_path)
        self.artifacts = ArtifactStore(self.database_path)
        self.decoder = decoder or PyAVVideoDecoder()
        self.decoder_identity = self.decoder.identity
        self.threads = threads
        self.should_continue = should_continue or (lambda: True)

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        probe_work_id: str,
        sample_time_seconds: float,
        *,
        profile: VideoFrameProfile = VideoFrameProfile(),
        owner: str = "builtin-video-frame",
    ) -> VideoFrameOutcome:
        return self.produce_many(
            run_id,
            relative_path,
            probe_work_id,
            (sample_time_seconds,),
            profile=profile,
            owner=owner,
        )[0]

    def produce_many(
        self,
        run_id: str,
        relative_path: Path,
        probe_work_id: str,
        sample_times: Iterable[float],
        *,
        profile: VideoFrameProfile = VideoFrameProfile(),
        owner: str = "builtin-video-frame",
    ) -> tuple[VideoFrameOutcome, ...]:
        """Share decoding, retain every Work, and return distinct frames plus failures."""

        targets = tuple(sorted(set(float(value) for value in sample_times)))
        if not targets:
            return ()
        if any(not math.isfinite(value) or value < 0 for value in targets):
            raise ValueError("video frame sample time must be finite and nonnegative")
        with connection_scope(self.database_path):
            return self._produce_many(
                run_id, relative_path, probe_work_id, targets, profile, owner
            )

    def _produce_many(
        self, run_id, relative_path, probe_work_id, targets, profile, owner
    ):
        proof = self.validity.prove(run_id, relative_path)
        probe_work = _attached_work(self.work, run_id, probe_work_id, "video-probe")
        subject = next(
            d.value
            for d in probe_work.spec.dependencies
            if d.key == "subject_relative_path"
        )
        if subject != proof.relative_path.as_posix():
            raise ValueError("video probe belongs to another Source Item")
        probe = _probe_from_output(probe_work.output)
        if probe is None or targets[-1] > probe.duration_seconds + 0.000001:
            raise ValueError("video frame sample time is outside the probed duration")
        outcomes: dict[float, VideoFrameOutcome] = {}
        pending: list[_PendingFrame] = []
        for target in targets:
            spec = self._spec(proof, probe_work, target, profile)
            record = self.work.ensure_work(run_id, spec)
            if record.status is WorkStatus.SUCCEEDED:
                artifacts = self.artifacts.artifacts_for_work(record.work_id)
                if artifacts and artifacts[0].integrity.value == "available":
                    outcomes[target] = VideoFrameOutcome(record, artifacts[0], True)
                    continue
                record = self.work.ensure_work(run_id, spec)
            if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
                outcomes[target] = VideoFrameOutcome(record, None, False)
                continue
            leases = self.work.claim_ready_work(
                run_id,
                owner,
                lease_duration=timedelta(minutes=5),
                work_id=record.work_id,
            )
            if leases:
                pending.append(_PendingFrame(target, record, leases[0]))
            else:
                outcomes[target] = VideoFrameOutcome(
                    self.work.get_work(record.work_id), None, False
                )

        active = {item.target: item for item in pending}
        try:
            context = (
                self.decoder.open(
                    proof.source_path,
                    threads=self.threads,
                    should_continue=self.should_continue,
                )
                if pending
                else nullcontext()
            )
            with context as session:
                for item in pending:
                    if not self.should_continue():
                        raise VideoDecodeCancelled("video preparation was stopped")
                    draft = self.artifacts.create_draft(item.lease, suffix=".jpg")
                    try:
                        decoded = session.frame_at(
                            item.target, max_edge=profile.max_edge
                        )
                        with decoded.image as image:
                            image.save(
                                draft.path, format="JPEG", quality=profile.jpeg_quality
                            )
                        with Image.open(draft.path) as saved:
                            saved.load()
                            width, height = saved.size
                        self.validity.verify(run_id, proof)
                        value = {
                            "sample_time_seconds": item.target,
                            "width": width,
                            "height": height,
                            "profile": {
                                "max_edge": profile.max_edge,
                                "jpeg_quality": profile.jpeg_quality,
                            },
                            "producer": {
                                "identity": item.record.spec.producer_identity,
                                "decoder": self.decoder_identity,
                            },
                            "position_basis": {
                                "origin": "video_stream_start",
                                "selection": "at_or_before_target_tick_or_first",
                                "target_rounding": "nearest_stream_time_base_tick",
                                "method": "presentation_timestamp"
                                if decoded.decoded_time_seconds is not None
                                else "unknown",
                            },
                        }
                        if decoded.decoded_time_seconds is not None:
                            if (
                                not math.isfinite(decoded.decoded_time_seconds)
                                or decoded.decoded_time_seconds < 0
                            ):
                                raise VideoProcessingError(
                                    "decoder returned an invalid observed position"
                                )
                            value["decoded_time_seconds"] = decoded.decoded_time_seconds
                        if decoded.time_base_seconds is not None:
                            value["position_basis"]["time_base_seconds"] = (
                                decoded.time_base_seconds
                            )
                        finished, artifact = self.artifacts.publish(
                            item.lease,
                            draft,
                            suffix=".jpg",
                            media_type="image/jpeg",
                            role="video_frame",
                            output=value,
                        )
                        outcomes[item.target] = VideoFrameOutcome(
                            finished, artifact, False
                        )
                    except SourceChangedDuringRead:
                        raise
                    except (
                        InvalidArtifactDraft,
                        OSError,
                        VideoProcessingError,
                    ) as error:
                        outcomes[item.target] = self._fail(item, error)
                    finally:
                        draft.path.unlink(missing_ok=True)
                    active.pop(item.target)
        except SourceChangedDuringRead:
            # Every frame of this video depends on the old probe/source proof.
            self.work.invalidate_work(
                probe_work_id, "source changed during video frame decoding"
            )
            outcomes = {
                target: VideoFrameOutcome(
                    self.work.get_work(value.work.work_id), None, False
                )
                for target, value in outcomes.items()
            }
            outcomes.update(
                {
                    target: VideoFrameOutcome(
                        self.work.get_work(item.record.work_id), None, False
                    )
                    for target, item in active.items()
                }
            )
        except VideoDecodeCancelled as error:
            for item in active.values():
                self._fail(item, error, code="video_frame_cancelled", retryable=True)
            raise
        except (OSError, VideoProcessingError) as error:
            for item in active.values():
                outcomes[item.target] = self._fail(item, error)
        except BaseException as error:
            for item in active.values():
                self._fail(
                    item, error, code="video_frame_execution_failed", retryable=True
                )
            raise
        distinct: list[VideoFrameOutcome] = []
        seen = set()
        for target in targets:
            outcome = outcomes[target]
            identity = frame_identity(outcome.work)
            if outcome.work.status is WorkStatus.SUCCEEDED:
                if identity in seen:
                    continue
                seen.add(identity)
            distinct.append(outcome)
        return tuple(distinct)

    def _fail(self, item, error, *, code="video_frame_decode_failed", retryable=False):
        if isinstance(error, VideoDecodeLimitExceeded):
            code = "video_decode_limit_exceeded"
        try:
            failed = self.work.fail_work(
                item.lease,
                error_code=code,
                message=str(error) or type(error).__name__,
                retryable=retryable,
            )
        except LeaseLost:
            failed = self.work.get_work(item.record.work_id)
        return VideoFrameOutcome(failed, None, False)

    def _spec(
        self,
        proof: SourceContentProof,
        probe_work: WorkRecord,
        target: float,
        profile: VideoFrameProfile,
    ) -> WorkSpec:
        return WorkSpec(
            capability="video-frame",
            producer_identity="builtin-pts-video-frame-v2",
            dependencies=(
                source_revision_dependency(
                    proof.dataset_id, proof.relative_path, proof.source_revision
                ),
                proof.dependency(),
                upstream_dependency(probe_work),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "subject_relative_path",
                    proof.relative_path.as_posix(),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER, "sample_time_seconds", str(target)
                ),
                WorkDependency(
                    DependencyKind.PARAMETER, "max_edge", str(profile.max_edge)
                ),
                WorkDependency(
                    DependencyKind.PARAMETER, "jpeg_quality", str(profile.jpeg_quality)
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "frame_selection",
                    "presentation-at-or-before-nearest-tick-v1",
                ),
                WorkDependency(
                    DependencyKind.ENVIRONMENT, "video_decoder", self.decoder_identity
                ),
            ),
        )
