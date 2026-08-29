"""Private dependency-driven execution coordinator for a PreCheck Run."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import subprocess
from typing import Protocol, TypeVar, cast

from mediasense.geo import AdaptiveReverseGeocoder

from ._accounting_types import AccountedItem
from ._compression_producer import (
    AdaptiveCompressionProducer,
    CompressionGroupOutcome,
    CompressionInput,
)
from ._compression_strategy import AdaptiveCompressionProfile
from ._work_types import WorkRecord, WorkStatus
from .accounting import AccountingStore
from .bundling import BundleCandidateOutcome, BundleCandidateProducer
from .embedding import EmbeddingProfile, EmbeddingProducer, ImageEmbeddingEncoder
from .geocode import (
    ReverseGeocodeBatchOutcome,
    ReverseGeocodeProducer,
    ReverseGeocodeProfile,
)
from .gpx import GPXMatchProducer, GPXOutcome
from .metadata import MetadataOutcome, MetadataProducer
from .rendition import (
    HIGH_RESOLUTION_RENDITION_PROFILE,
    ORDINARY_RENDITION_PROFILE,
    ImageRenditionProducer,
    RenditionOutcome,
)
from .resources import (
    BoundedWorkExecutor,
    ResourceAdmissionCancelled,
    ResourceBudget,
    ResourceClaim,
    ScheduledCall,
)
from .result import ResultStore
from .sensitivity import (
    SensitivityDetector,
    SensitivityOutcome,
    SensitivityProducer,
    SensitivityProfile,
)
from .video import (
    ContactSheetOutcome,
    ContactSheetProducer,
    VideoFrameOutcome,
    VideoFrameProducer,
    VideoKeyFrameCandidateProducer,
    VideoKeyFrameOutcome,
    VideoProbeOutcome,
    VideoProbeProducer,
    sample_video_times,
)


_T = TypeVar("_T")
_MEDIA_KINDS = {"image", "raw_image", "video"}
_STILL_KINDS = {"image", "raw_image"}


class _RunControl(Protocol):
    database_path: Path

    def current_state(self, run_ref: str) -> str: ...

    def sync_accounting(self, run_ref: str) -> dict[str, object]: ...

    def require_confirmation(
        self,
        run_ref: str,
        *,
        summary: str,
        quantity: int,
        unit: str,
        skip_allowed: bool,
        pending_fingerprint: str,
    ) -> dict[str, object]: ...

    def confirmation_decision(
        self, run_ref: str, *, pending_fingerprint: str
    ) -> str | None: ...

    def mark_blocked(
        self,
        run_ref: str,
        *,
        code: str,
        message: str,
        resume_when: str,
    ) -> dict[str, object]: ...

    def publish_result(self, run_ref: str, draft) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class PrecheckExecutionConfig:
    """Durable internal policy selecting which producer graph a Run demands."""

    metadata: bool = True
    gpx: bool = True
    image_renditions: bool = True
    video: bool = True
    bundles: bool = True
    compression_target: int | None = 200
    video_frame_limit: int = 3
    embedding_profile: EmbeddingProfile | None = None
    sensitivity_profile: SensitivityProfile | None = None
    reverse_geocode_profile: ReverseGeocodeProfile = field(
        default_factory=ReverseGeocodeProfile
    )
    resource_budget: ResourceBudget = field(
        default_factory=lambda: ResourceBudget(
            capacity=ResourceClaim(
                source_io_slots=2,
                workspace_io_slots=2,
                cpu_slots=2,
                process_slots=1,
                memory_bytes=512 * 1024 * 1024,
                temporary_bytes=1024 * 1024 * 1024,
                model_slots=1,
                exiftool_slots=1,
                decoder_slots=1,
                encoder_slots=1,
                network_slots=0,
            ),
            max_workers=2,
            max_pending=8,
        )
    )
    dataset_name: str | None = None

    def __post_init__(self) -> None:
        if self.gpx and not self.metadata:
            raise ValueError("GPX matching requires metadata")
        if self.video_frame_limit < 1:
            raise ValueError("video_frame_limit must be positive")
        if self.compression_target is not None and self.compression_target < 1:
            raise ValueError("compression_target must be positive")
        if (
            self.reverse_geocode_profile.enabled
            and self.resource_budget.capacity.network_slots < 1
        ):
            raise ValueError("enabled reverse geocoding requires one network slot")

    def value(self) -> dict[str, object]:
        return {
            "bundles": self.bundles,
            "compression_target": self.compression_target,
            "dataset_name": self.dataset_name,
            "embedding_profile": _embedding_profile_value(self.embedding_profile),
            "gpx": self.gpx,
            "image_renditions": self.image_renditions,
            "metadata": self.metadata,
            "resource_budget": {
                "capacity": asdict(self.resource_budget.capacity),
                "max_pending": self.resource_budget.max_pending,
                "max_workers": self.resource_budget.max_workers,
            },
            "reverse_geocode_profile": {
                "enabled": self.reverse_geocode_profile.enabled,
                "max_attempts": self.reverse_geocode_profile.max_attempts,
                "provider_profile": self.reverse_geocode_profile.provider_profile,
                "refresh_token": self.reverse_geocode_profile.refresh_token,
                "retry_delay_seconds": self.reverse_geocode_profile.retry_delay_seconds,
                "routing_policy": self.reverse_geocode_profile.routing_policy,
            },
            "sensitivity_profile": _sensitivity_profile_value(self.sensitivity_profile),
            "version": 1,
            "video": self.video,
            "video_frame_limit": self.video_frame_limit,
        }

    @classmethod
    def from_value(cls, value: Mapping[str, object]) -> PrecheckExecutionConfig:
        if value.get("version") != 1:
            raise ValueError("unsupported PreCheck execution configuration")
        budget_value = cast(Mapping[str, object], value["resource_budget"])
        capacity_value = cast(Mapping[str, object], budget_value["capacity"])
        geocode_value = cast(Mapping[str, object], value["reverse_geocode_profile"])
        return cls(
            metadata=bool(value["metadata"]),
            gpx=bool(value["gpx"]),
            image_renditions=bool(value["image_renditions"]),
            video=bool(value["video"]),
            bundles=bool(value["bundles"]),
            compression_target=(
                None
                if value["compression_target"] is None
                else int(value["compression_target"])
            ),
            video_frame_limit=int(value["video_frame_limit"]),
            embedding_profile=_embedding_profile_from_value(
                cast(Mapping[str, object] | None, value["embedding_profile"])
            ),
            sensitivity_profile=_sensitivity_profile_from_value(
                cast(Mapping[str, object] | None, value["sensitivity_profile"])
            ),
            reverse_geocode_profile=ReverseGeocodeProfile(
                enabled=bool(geocode_value["enabled"]),
                provider_profile=str(geocode_value["provider_profile"]),
                routing_policy=str(geocode_value["routing_policy"]),
                refresh_token=str(geocode_value["refresh_token"]),
                max_attempts=int(geocode_value["max_attempts"]),
                retry_delay_seconds=float(geocode_value["retry_delay_seconds"]),
            ),
            resource_budget=ResourceBudget(
                capacity=ResourceClaim(
                    **{key: int(item) for key, item in capacity_value.items()}
                ),
                max_workers=int(budget_value["max_workers"]),
                max_pending=int(budget_value["max_pending"]),
            ),
            dataset_name=(
                None if value["dataset_name"] is None else str(value["dataset_name"])
            ),
        )


@dataclass(slots=True)
class PrecheckExecutionDependencies:
    """Process-local adapters; credentials and model objects are never persisted."""

    metadata_runner: (
        Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None
    ) = None
    exiftool_version: str | None = None
    video_runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = (
        None
    )
    ffprobe_version: str | None = None
    ffmpeg_version: str | None = None
    embedding_encoder: ImageEmbeddingEncoder | None = None
    sensitivity_detector: SensitivityDetector | None = None
    geocoder: AdaptiveReverseGeocoder | None = None


class PrecheckOrchestrator:
    """Coordinate existing producers without becoming a second state authority."""

    def __init__(
        self,
        database_path: Path,
        run_control: _RunControl,
        dependencies: PrecheckExecutionDependencies | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.run_control = run_control
        self.dependencies = dependencies or PrecheckExecutionDependencies()

    def advance(
        self,
        run_ref: str,
        accounting_run_id: str,
        config: PrecheckExecutionConfig,
    ) -> dict[str, object]:
        if not self._running(run_ref):
            return self.run_control.sync_accounting(run_ref)
        accounting = AccountingStore(self.database_path)
        self._checkpoint(run_ref, "accounting")
        accounting.process_run(
            accounting_run_id,
            should_continue=lambda: self._running(run_ref),
        )
        status = self.run_control.sync_accounting(run_ref)
        if status["state"] != "running":
            return status
        items = accounting.get_run_items(accounting_run_id)
        media = tuple(
            item
            for item in items
            if item.scope == "source_media"
            and item.kind in _MEDIA_KINDS
            and item.source_revision is not None
        )
        gpx_paths = tuple(
            item.relative_path
            for item in items
            if item.kind == "gpx" and item.source_revision is not None
        )
        executor = BoundedWorkExecutor(config.resource_budget)

        metadata = self._metadata(run_ref, accounting_run_id, media, config, executor)
        if not self._finish_phase(run_ref, "metadata"):
            return self.run_control.sync_accounting(run_ref)
        renditions = self._renditions(
            run_ref, accounting_run_id, media, config, executor
        )
        if not self._finish_phase(run_ref, "renditions"):
            return self.run_control.sync_accounting(run_ref)
        probes, frames, sheets = self._video(
            run_ref, accounting_run_id, media, config, executor
        )
        if not self._finish_phase(run_ref, "video"):
            return self.run_control.sync_accounting(run_ref)
        gpx = self._gpx(
            run_ref,
            accounting_run_id,
            metadata,
            gpx_paths,
            config,
            executor,
        )
        if not self._finish_phase(run_ref, "gpx"):
            return self.run_control.sync_accounting(run_ref)
        embeddings, key_frames = self._embeddings(
            run_ref,
            accounting_run_id,
            renditions,
            frames,
            config,
            executor,
        )
        if not self._finish_phase(run_ref, "embeddings"):
            return self.run_control.sync_accounting(run_ref)
        sensitivity = self._sensitivity(
            run_ref,
            accounting_run_id,
            renditions,
            frames,
            config,
            executor,
        )
        if not self._finish_phase(run_ref, "sensitivity"):
            return self.run_control.sync_accounting(run_ref)
        bundles = self._bundles(accounting_run_id, metadata, config)
        if not self._finish_phase(run_ref, "bundles"):
            return self.run_control.sync_accounting(run_ref)
        compression, representative_paths = self._compression(
            accounting_run_id,
            renditions,
            frames,
            sheets,
            key_frames,
            metadata,
            gpx,
            embeddings,
            bundles,
            config,
        )
        if not self._finish_phase(run_ref, "compression"):
            return self.run_control.sync_accounting(run_ref)
        geocode = self._geocode(
            run_ref,
            accounting_run_id,
            representative_paths,
            metadata,
            gpx,
            config,
            executor,
        )
        if geocode.status == "confirmation_required":
            return self.run_control.sync_accounting(run_ref)
        if not self._finish_phase(run_ref, "external_evidence"):
            return self.run_control.sync_accounting(run_ref)

        draft = ResultStore(self.database_path).build_minimal(
            accounting_run_id,
            [outcome.work.work_id for outcome in renditions],
            compression_work_ids=[
                outcome.work.work_id
                for outcome in compression
                if outcome.work.status is WorkStatus.SUCCEEDED
            ],
            contact_sheet_work_ids=[outcome.work.work_id for outcome in sheets],
            gpx_work_ids=[outcome.work.work_id for outcome in gpx.values()],
            metadata_work_ids=[outcome.work.work_id for outcome in metadata.values()],
            reverse_geocode_work_by_source=geocode.work_by_source(),
            sensitivity_work_ids=[outcome.work.work_id for outcome in sensitivity],
            video_probe_work_ids=[outcome.work.work_id for outcome in probes.values()],
            video_frame_work_ids=[outcome.work.work_id for outcome in frames],
            video_key_frame_work_ids=[
                outcome.work.work_id for outcome in key_frames.values()
            ],
            dataset_name=config.dataset_name,
            external_policy_status=geocode.status,
        )
        self._checkpoint(run_ref, "sealing")
        return self.run_control.publish_result(run_ref, draft)

    def _metadata(
        self,
        run_ref: str,
        run_id: str,
        media: tuple[AccountedItem, ...],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> dict[Path, MetadataOutcome]:
        if not config.metadata:
            return {}
        kwargs: dict[str, object] = {}
        if self.dependencies.metadata_runner is not None:
            kwargs["command_runner"] = self.dependencies.metadata_runner
        if self.dependencies.exiftool_version is not None:
            kwargs["exiftool_version"] = self.dependencies.exiftool_version
        producer = MetadataProducer(self.database_path, **kwargs)
        outcomes = self._execute(
            run_ref,
            executor,
            (
                ScheduledCall(
                    f"metadata:{item.relative_path.as_posix()}",
                    ResourceClaim(
                        source_io_slots=1,
                        cpu_slots=1,
                        process_slots=1,
                        memory_bytes=16 * 1024 * 1024,
                        exiftool_slots=1,
                    ),
                    lambda item=item: producer.produce(run_id, item.relative_path),
                )
                for item in media
            ),
        )
        return {
            Path(key.removeprefix("metadata:")): item for key, item in outcomes.items()
        }

    def _renditions(
        self,
        run_ref: str,
        run_id: str,
        media: tuple[AccountedItem, ...],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> tuple[RenditionOutcome, ...]:
        if not config.image_renditions:
            return ()
        producer = ImageRenditionProducer(self.database_path)
        high_resolution = (
            config.embedding_profile is not None
            or config.sensitivity_profile is not None
        )
        calls = (
            ScheduledCall(
                f"rendition:{profile.name}:{item.relative_path.as_posix()}",
                ResourceClaim(
                    source_io_slots=1,
                    workspace_io_slots=1,
                    cpu_slots=1,
                    memory_bytes=128 * 1024 * 1024,
                    temporary_bytes=32 * 1024 * 1024,
                    decoder_slots=1,
                    encoder_slots=1,
                ),
                lambda item=item, profile=profile: producer.produce(
                    run_id, item.relative_path, profile=profile
                ),
            )
            for item in media
            if item.kind in _STILL_KINDS
            for profile in (
                (ORDINARY_RENDITION_PROFILE, HIGH_RESOLUTION_RENDITION_PROFILE)
                if high_resolution
                else (ORDINARY_RENDITION_PROFILE,)
            )
        )
        return tuple(self._execute(run_ref, executor, calls).values())

    def _video(
        self,
        run_ref: str,
        run_id: str,
        media: tuple[AccountedItem, ...],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> tuple[
        dict[Path, VideoProbeOutcome],
        tuple[VideoFrameOutcome, ...],
        tuple[ContactSheetOutcome, ...],
    ]:
        videos = tuple(item for item in media if item.kind == "video")
        if not config.video or not videos:
            return {}, (), ()
        probe_kwargs: dict[str, object] = {}
        frame_kwargs: dict[str, object] = {}
        if self.dependencies.video_runner is not None:
            probe_kwargs["command_runner"] = self.dependencies.video_runner
            frame_kwargs["command_runner"] = self.dependencies.video_runner
        if self.dependencies.ffprobe_version is not None:
            probe_kwargs["ffprobe_version"] = self.dependencies.ffprobe_version
        if self.dependencies.ffmpeg_version is not None:
            frame_kwargs["ffmpeg_version"] = self.dependencies.ffmpeg_version
        probe_producer = VideoProbeProducer(self.database_path, **probe_kwargs)
        probes = self._execute(
            run_ref,
            executor,
            (
                ScheduledCall(
                    f"video-probe:{item.relative_path.as_posix()}",
                    ResourceClaim(
                        source_io_slots=1,
                        cpu_slots=1,
                        process_slots=1,
                        memory_bytes=32 * 1024 * 1024,
                        decoder_slots=1,
                    ),
                    lambda item=item: probe_producer.produce(
                        run_id, item.relative_path
                    ),
                )
                for item in videos
            ),
        )
        probe_by_path = {
            Path(key.removeprefix("video-probe:")): outcome
            for key, outcome in probes.items()
        }
        frame_producer = VideoFrameProducer(self.database_path, **frame_kwargs)
        frame_calls = []
        for path, outcome in probe_by_path.items():
            if outcome.work.status is not WorkStatus.SUCCEEDED or outcome.probe is None:
                continue
            for sample_time in sample_video_times(
                outcome.probe.duration_seconds,
                max_frames=config.video_frame_limit,
            ):
                frame_calls.append(
                    ScheduledCall(
                        f"video-frame:{path.as_posix()}:{sample_time:.6f}",
                        ResourceClaim(
                            source_io_slots=1,
                            workspace_io_slots=1,
                            cpu_slots=1,
                            process_slots=1,
                            memory_bytes=128 * 1024 * 1024,
                            temporary_bytes=32 * 1024 * 1024,
                            decoder_slots=1,
                            encoder_slots=1,
                        ),
                        lambda path=path, outcome=outcome, sample_time=sample_time: (
                            frame_producer.produce(
                                run_id,
                                path,
                                outcome.work.work_id,
                                sample_time,
                            )
                        ),
                    )
                )
        frame_values = tuple(self._execute(run_ref, executor, frame_calls).values())
        frames_by_path: dict[Path, list[VideoFrameOutcome]] = {}
        for frame in frame_values:
            path = _work_subject(frame.work)
            frames_by_path.setdefault(path, []).append(frame)
        sheet_producer = ContactSheetProducer(self.database_path)
        sheet_calls = (
            ScheduledCall(
                f"contact-sheet:{path.as_posix()}",
                ResourceClaim(
                    source_io_slots=1,
                    workspace_io_slots=1,
                    cpu_slots=1,
                    memory_bytes=128 * 1024 * 1024,
                    temporary_bytes=64 * 1024 * 1024,
                    decoder_slots=1,
                    encoder_slots=1,
                ),
                lambda path=path, frames=tuple(frames): sheet_producer.produce(
                    run_id,
                    path,
                    [
                        frame.work.work_id
                        for frame in frames
                        if frame.work.status is WorkStatus.SUCCEEDED
                    ],
                ),
            )
            for path, frames in frames_by_path.items()
            if any(frame.work.status is WorkStatus.SUCCEEDED for frame in frames)
        )
        sheets = tuple(self._execute(run_ref, executor, sheet_calls).values())
        return probe_by_path, frame_values, sheets

    def _gpx(
        self,
        run_ref: str,
        run_id: str,
        metadata: Mapping[Path, MetadataOutcome],
        gpx_paths: tuple[Path, ...],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> dict[Path, GPXOutcome]:
        if not config.gpx or not gpx_paths:
            return {}
        producer = GPXMatchProducer(self.database_path)
        eligible = {
            path: outcome
            for path, outcome in metadata.items()
            if outcome.work.status is WorkStatus.SUCCEEDED
        }
        outcomes = self._execute(
            run_ref,
            executor,
            (
                ScheduledCall(
                    f"gpx:{path.as_posix()}",
                    ResourceClaim(source_io_slots=1, cpu_slots=1),
                    lambda path=path, outcome=outcome: producer.produce(
                        run_id, outcome.work.work_id, gpx_paths
                    ),
                )
                for path, outcome in eligible.items()
            ),
        )
        return {
            Path(key.removeprefix("gpx:")): value for key, value in outcomes.items()
        }

    def _embeddings(
        self,
        run_ref: str,
        run_id: str,
        renditions: tuple[RenditionOutcome, ...],
        frames: tuple[VideoFrameOutcome, ...],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> tuple[dict[str, WorkRecord], dict[Path, VideoKeyFrameOutcome]]:
        profile = config.embedding_profile
        if profile is None:
            return {}, {}
        encoder = self.dependencies.embedding_encoder
        if encoder is None:
            raise _BlockedExecution(
                "embedding_backend_unavailable",
                "The configured local embedding backend is unavailable.",
                "Configure the pinned local embedding backend and resume.",
            )
        visual = [
            outcome
            for outcome in (*renditions, *frames)
            if outcome.work.status is WorkStatus.SUCCEEDED
            and (
                outcome.work.spec.capability == "video-frame"
                or _rendition_profile(outcome.work) == "high_resolution"
            )
        ]
        producer = EmbeddingProducer(self.database_path, encoder)
        values = self._execute(
            run_ref,
            executor,
            (
                ScheduledCall(
                    f"embedding:{outcome.work.work_id}",
                    ResourceClaim(
                        source_io_slots=1,
                        workspace_io_slots=1,
                        cpu_slots=1,
                        memory_bytes=256 * 1024 * 1024,
                        temporary_bytes=32 * 1024 * 1024,
                        model_slots=1,
                    ),
                    lambda outcome=outcome: producer.produce(
                        run_id, outcome.work.work_id, profile=profile
                    ),
                )
                for outcome in visual
            ),
        )
        embeddings = {
            key.removeprefix("embedding:"): value.work
            for key, value in values.items()
            if value.work.status is WorkStatus.SUCCEEDED
        }
        frame_pairs: dict[Path, list[tuple[str, str]]] = {}
        for frame in frames:
            embedding = embeddings.get(frame.work.work_id)
            if embedding is not None:
                frame_pairs.setdefault(_work_subject(frame.work), []).append(
                    (frame.work.work_id, embedding.work_id)
                )
        key_producer = VideoKeyFrameCandidateProducer(self.database_path)
        key_frames = {
            path: key_producer.produce(run_id, path, pairs)
            for path, pairs in frame_pairs.items()
            if pairs
        }
        return embeddings, key_frames

    def _sensitivity(
        self,
        run_ref: str,
        run_id: str,
        renditions: tuple[RenditionOutcome, ...],
        frames: tuple[VideoFrameOutcome, ...],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> tuple[SensitivityOutcome, ...]:
        profile = config.sensitivity_profile
        if profile is None:
            return ()
        detector = self.dependencies.sensitivity_detector
        if detector is None:
            raise _BlockedExecution(
                "sensitivity_backend_unavailable",
                "The configured local sensitivity backend is unavailable.",
                "Configure the pinned local sensitivity backend and resume.",
            )
        visual = [
            outcome
            for outcome in (*renditions, *frames)
            if outcome.work.status is WorkStatus.SUCCEEDED
            and (
                outcome.work.spec.capability == "video-frame"
                or _rendition_profile(outcome.work) == "high_resolution"
            )
        ]
        producer = SensitivityProducer(self.database_path, detector)
        calls = (
            ScheduledCall(
                f"sensitivity:{outcome.work.work_id}",
                ResourceClaim(
                    source_io_slots=1,
                    cpu_slots=1,
                    memory_bytes=256 * 1024 * 1024,
                    model_slots=1,
                ),
                lambda outcome=outcome: producer.produce(
                    run_id,
                    _work_subject(outcome.work),
                    outcome.work.work_id,
                    profile=profile,
                ),
            )
            for outcome in visual
        )
        return tuple(self._execute(run_ref, executor, calls).values())

    def _bundles(
        self,
        run_id: str,
        metadata: Mapping[Path, MetadataOutcome],
        config: PrecheckExecutionConfig,
    ) -> tuple[BundleCandidateOutcome, ...]:
        if not config.bundles:
            return ()
        return BundleCandidateProducer(self.database_path).produce(
            run_id,
            [
                outcome.work.work_id
                for outcome in metadata.values()
                if outcome.work.status is WorkStatus.SUCCEEDED
            ],
        )

    def _compression(
        self,
        run_id: str,
        renditions: tuple[RenditionOutcome, ...],
        frames: tuple[VideoFrameOutcome, ...],
        sheets: tuple[ContactSheetOutcome, ...],
        key_frames: Mapping[Path, VideoKeyFrameOutcome],
        metadata: Mapping[Path, MetadataOutcome],
        gpx: Mapping[Path, GPXOutcome],
        embeddings: Mapping[str, WorkRecord],
        bundles: tuple[BundleCandidateOutcome, ...],
        config: PrecheckExecutionConfig,
    ) -> tuple[tuple[CompressionGroupOutcome, ...], tuple[Path, ...]]:
        visual_by_path: dict[Path, WorkRecord] = {}
        for outcome in renditions:
            if outcome.work.status is not WorkStatus.SUCCEEDED:
                continue
            path = _work_subject(outcome.work)
            profile = _rendition_profile(outcome.work)
            current = visual_by_path.get(path)
            if current is None or profile == "high_resolution":
                visual_by_path[path] = outcome.work
        successful_frames: dict[str, WorkRecord] = {
            outcome.work.work_id: outcome.work
            for outcome in frames
            if outcome.work.status is WorkStatus.SUCCEEDED
        }
        for path, outcome in key_frames.items():
            if outcome.selected_frame_work_id in successful_frames:
                visual_by_path[path] = successful_frames[
                    cast(str, outcome.selected_frame_work_id)
                ]
        for outcome in sheets:
            if outcome.work.status is WorkStatus.SUCCEEDED:
                path = _work_subject(outcome.work)
                visual_by_path.setdefault(path, outcome.work)

        inputs: list[CompressionInput] = []
        covered: set[Path] = set()
        for outcome in bundles:
            candidate = outcome.candidate
            if outcome.work.status is not WorkStatus.SUCCEEDED or candidate is None:
                continue
            visual = visual_by_path.get(candidate.representative_path)
            if visual is None:
                continue
            inputs.append(
                self._compression_input(
                    candidate.representative_path,
                    visual,
                    metadata,
                    gpx,
                    embeddings,
                    member_paths=candidate.members,
                    bundle_work_id=outcome.work.work_id,
                )
            )
            covered.update(candidate.members)
        for path, visual in visual_by_path.items():
            if path in covered:
                continue
            inputs.append(
                self._compression_input(path, visual, metadata, gpx, embeddings)
            )
        if config.compression_target is None or not inputs:
            return (), tuple(sorted(visual_by_path))
        outcomes = AdaptiveCompressionProducer(self.database_path).produce(
            run_id,
            inputs,
            profile=AdaptiveCompressionProfile(
                target_entries=config.compression_target
            ),
        )
        representatives = tuple(
            outcome.group.representative_path
            for outcome in outcomes
            if outcome.work.status is WorkStatus.SUCCEEDED and outcome.group is not None
        )
        return outcomes, representatives

    def _compression_input(
        self,
        path: Path,
        visual: WorkRecord,
        metadata: Mapping[Path, MetadataOutcome],
        gpx: Mapping[Path, GPXOutcome],
        embeddings: Mapping[str, WorkRecord],
        *,
        member_paths: tuple[Path, ...] = (),
        bundle_work_id: str | None = None,
    ) -> CompressionInput:
        metadata_work = metadata.get(path)
        gpx_work = gpx.get(path)
        embedding = embeddings.get(visual.work_id)
        return CompressionInput(
            relative_path=path,
            visual_work_id=visual.work_id,
            member_paths=member_paths,
            bundle_work_id=bundle_work_id,
            metadata_work_id=(
                metadata_work.work.work_id
                if metadata_work is not None
                and metadata_work.work.status is WorkStatus.SUCCEEDED
                else None
            ),
            gpx_work_id=(
                gpx_work.work.work_id
                if gpx_work is not None and gpx_work.work.status is WorkStatus.SUCCEEDED
                else None
            ),
            embedding_work_id=None if embedding is None else embedding.work_id,
        )

    def _geocode(
        self,
        run_ref: str,
        run_id: str,
        representative_paths: tuple[Path, ...],
        metadata: Mapping[Path, MetadataOutcome],
        gpx: Mapping[Path, GPXOutcome],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> ReverseGeocodeBatchOutcome:
        work_ids = []
        for path in representative_paths:
            for candidate in (metadata.get(path), gpx.get(path)):
                if (
                    candidate is not None
                    and candidate.work.status is WorkStatus.SUCCEEDED
                ):
                    work_ids.append(candidate.work.work_id)
        producer = ReverseGeocodeProducer(
            self.database_path,
            self.run_control,
            self.dependencies.geocoder,
        )
        outcome = self._execute(
            run_ref,
            executor,
            (
                ScheduledCall(
                    "reverse-geocode",
                    ResourceClaim(
                        cpu_slots=1,
                        network_slots=(
                            1 if config.reverse_geocode_profile.enabled else 0
                        ),
                    ),
                    lambda: producer.produce(
                        run_ref,
                        run_id,
                        work_ids,
                        profile=config.reverse_geocode_profile,
                    ),
                ),
            ),
        )
        return outcome["reverse-geocode"]

    def _execute(
        self,
        run_ref: str,
        executor: BoundedWorkExecutor,
        calls: Iterable[ScheduledCall[_T]],
    ) -> dict[str, _T]:
        def guarded(call: ScheduledCall[_T]) -> ScheduledCall[_T]:
            def invoke() -> _T:
                if not self._running(run_ref):
                    raise ResourceAdmissionCancelled(
                        "Run stopped before scheduled Work began"
                    )
                return call.function()

            return ScheduledCall(call.key, call.claim, invoke)

        outcomes = executor.run(guarded(call) for call in calls)
        values: dict[str, _T] = {}
        for outcome in outcomes:
            if outcome.error is None:
                values[outcome.key] = cast(_T, outcome.value)
            elif not isinstance(outcome.error, ResourceAdmissionCancelled):
                raise outcome.error
        return values

    def _running(self, run_ref: str) -> bool:
        return self.run_control.current_state(run_ref) == "running"

    def _checkpoint(self, run_ref: str, phase: str) -> None:
        store = getattr(self.run_control, "_store")
        store.set_execution_checkpoint(run_ref, phase)

    def _finish_phase(self, run_ref: str, phase: str) -> bool:
        self._checkpoint(run_ref, f"{phase}:complete")
        self._after_phase(run_ref, phase)
        return self._running(run_ref)

    def _after_phase(self, run_ref: str, phase: str) -> None:
        """Fault-injection seam after a durable orchestration boundary."""


class _BlockedExecution(RuntimeError):
    def __init__(self, code: str, message: str, resume_when: str) -> None:
        self.code = code
        self.message = message
        self.resume_when = resume_when
        super().__init__(message)


def _work_subject(work: WorkRecord) -> Path:
    output = work.output
    if isinstance(output, Mapping):
        subject = output.get("subject")
        if isinstance(subject, Mapping) and isinstance(
            subject.get("relative_path"), str
        ):
            return Path(subject["relative_path"])
    dependency = next(
        (
            item
            for item in work.spec.dependencies
            if item.kind.value == "parameter" and item.key == "subject_relative_path"
        ),
        None,
    )
    if dependency is not None:
        return Path(dependency.value)
    source_dependency = next(
        (
            item
            for item in work.spec.dependencies
            if item.kind.value in {"source_content", "source_revision"}
        ),
        None,
    )
    if source_dependency is not None:
        source_key = json.loads(source_dependency.key)
        if (
            isinstance(source_key, list)
            and len(source_key) == 2
            and isinstance(source_key[1], str)
        ):
            return Path(source_key[1])
    raise ValueError("Work has no Source Item subject")


def _rendition_profile(work: WorkRecord) -> str | None:
    output = work.output
    if isinstance(output, Mapping):
        value = output.get("value")
        if isinstance(value, Mapping):
            profile = value.get("profile")
            if isinstance(profile, Mapping) and isinstance(profile.get("name"), str):
                return str(profile["name"])
    dependency = next(
        (
            item
            for item in work.spec.dependencies
            if item.kind.value == "parameter"
            and item.key in {"rendition_profile", "profile_name"}
        ),
        None,
    )
    if dependency is None:
        return None
    try:
        value = json.loads(dependency.value)
    except json.JSONDecodeError:
        return dependency.value
    return None if not isinstance(value, Mapping) else str(value.get("name"))


def _embedding_profile_value(profile: EmbeddingProfile | None) -> object:
    if profile is None:
        return None
    return {
        "dimensions": profile.dimensions,
        "dtype": profile.dtype,
        "name": profile.name,
        "normalization": profile.normalization,
    }


def _embedding_profile_from_value(
    value: Mapping[str, object] | None,
) -> EmbeddingProfile | None:
    if value is None:
        return None
    return EmbeddingProfile(
        name=str(value["name"]),
        dimensions=int(value["dimensions"]),
        normalization=str(value["normalization"]),
        dtype=str(value["dtype"]),
    )


def _sensitivity_profile_value(profile: SensitivityProfile | None) -> object:
    if profile is None:
        return None
    return {
        "mild_ratio": profile.mild_ratio,
        "name": profile.name,
        "thresholds": [asdict(threshold) for threshold in profile.thresholds],
    }


def _sensitivity_profile_from_value(
    value: Mapping[str, object] | None,
) -> SensitivityProfile | None:
    if value is None:
        return None
    from .sensitivity import SensitivityThreshold

    thresholds = cast(Sequence[Mapping[str, object]], value["thresholds"])
    return SensitivityProfile(
        name=str(value["name"]),
        mild_ratio=float(value["mild_ratio"]),
        thresholds=tuple(
            SensitivityThreshold(
                label=str(threshold["label"]),
                threshold=float(threshold["threshold"]),
                description=str(threshold["description"]),
            )
            for threshold in thresholds
        ),
    )


__all__ = [
    "PrecheckExecutionConfig",
    "PrecheckExecutionDependencies",
    "PrecheckOrchestrator",
]
