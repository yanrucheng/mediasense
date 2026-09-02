"""Private dependency-driven execution coordinator for a PreCheck Run."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
import hashlib
import heapq
from itertools import islice
import json
from pathlib import Path
import subprocess
from typing import Protocol, TypeVar, cast

from mediasense.capabilities.geo import ReverseGeocodeBatchEngine

from ._accounting_types import AccountedItem
from ._compression_producer import (
    AdaptiveCompressionProducer,
    CompressionGroupOutcome,
    CompressionInput,
)
from ._compression_strategy import AdaptiveCompressionProfile
from ._work_types import DependencyKind, WorkRecord, WorkStatus
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
    detect_source_storage,
    resolve_resource_budget,
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
from .work import WorkStore


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

    def scope_selection_submitted(self, run_ref: str) -> bool: ...

    def require_scope_selection(
        self, run_ref: str, accounting_run_id: str
    ) -> dict[str, object]: ...

    def mark_blocked(
        self,
        run_ref: str,
        *,
        code: str,
        message: str,
        resume_when: str,
    ) -> dict[str, object]: ...

    def record_phase(
        self,
        run_ref: str,
        phase: str,
        *,
        complete: bool = False,
        total: int | str | None = None,
    ) -> None: ...

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
    metadata_batch_size: int | None = None
    ffmpeg_threads: int | None = None
    model_batch_size: int | None = None
    directed_evidence_paths: tuple[Path, ...] = ()
    embedding_profile: EmbeddingProfile | None = None
    sensitivity_profile: SensitivityProfile | None = None
    reverse_geocode_profile: ReverseGeocodeProfile = field(
        default_factory=ReverseGeocodeProfile
    )
    source_storage_hint: str = "auto"
    source_storage_evidence: str = "unresolved"
    resource_budget: ResourceBudget | None = None
    dataset_name: str | None = None

    def __post_init__(self) -> None:
        if self.gpx and not self.metadata:
            raise ValueError("GPX matching requires metadata")
        if self.video_frame_limit < 1:
            raise ValueError("video_frame_limit must be positive")
        if self.metadata_batch_size is not None and self.metadata_batch_size < 1:
            raise ValueError("metadata_batch_size must be positive")
        if self.ffmpeg_threads is not None and self.ffmpeg_threads < 1:
            raise ValueError("ffmpeg_threads must be positive")
        if self.model_batch_size is not None and self.model_batch_size < 1:
            raise ValueError("model_batch_size must be positive")
        if self.source_storage_hint not in {"auto", "local", "remote", "unknown"}:
            raise ValueError(
                "source_storage_hint must be auto, local, remote, or unknown"
            )
        normalized_paths = tuple(Path(path) for path in self.directed_evidence_paths)
        if any(
            path.is_absolute() or path == Path(".") or ".." in path.parts
            for path in normalized_paths
        ):
            raise ValueError("directed evidence paths must stay source-root-relative")
        if len(set(normalized_paths)) != len(normalized_paths):
            raise ValueError("directed evidence paths must be unique")
        object.__setattr__(self, "directed_evidence_paths", normalized_paths)
        if self.compression_target is not None and self.compression_target < 1:
            raise ValueError("compression_target must be positive")
        if (
            self.resource_budget is not None
            and self.reverse_geocode_profile.enabled
            and self.resource_budget.capacity.network_slots < 1
        ):
            raise ValueError("enabled reverse geocoding requires one network slot")

    def value(self) -> dict[str, object]:
        if (
            self.resource_budget is None
            or self.metadata_batch_size is None
            or self.ffmpeg_threads is None
            or self.model_batch_size is None
            or self.source_storage_hint == "auto"
        ):
            return self.resolve_resources().value()
        assert self.resource_budget is not None
        return {
            "bundles": self.bundles,
            "compression_target": self.compression_target,
            "dataset_name": self.dataset_name,
            "directed_evidence_paths": [
                path.as_posix() for path in self.directed_evidence_paths
            ],
            "embedding_profile": _embedding_profile_value(self.embedding_profile),
            "ffmpeg_threads": self.ffmpeg_threads,
            "gpx": self.gpx,
            "image_renditions": self.image_renditions,
            "metadata": self.metadata,
            "metadata_batch_size": self.metadata_batch_size,
            "model_batch_size": self.model_batch_size,
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
            "source_storage": self.source_storage_hint,
            "source_storage_evidence": self.source_storage_evidence,
            "version": 4,
            "video": self.video,
            "video_frame_limit": self.video_frame_limit,
        }

    def resolve_resources(
        self,
        *,
        source_root: Path | None = None,
        source_storage: str | None = None,
        source_storage_evidence: str | None = None,
        logical_cpu_count: int | None = None,
        available_memory_bytes: int | None = None,
    ) -> PrecheckExecutionConfig:
        if (
            self.resource_budget is not None
            and self.metadata_batch_size is not None
            and self.ffmpeg_threads is not None
            and self.model_batch_size is not None
            and self.source_storage_hint != "auto"
        ):
            return self
        detected_storage = source_storage
        detected_evidence = source_storage_evidence
        if detected_storage is None:
            if source_root is None:
                detected_storage = "unknown"
                detected_evidence = "source_root_unavailable"
            else:
                detected_storage, detected_evidence = detect_source_storage(source_root)
        if detected_storage not in {"local", "remote", "unknown"}:
            raise ValueError(
                "detected source storage must be local, remote, or unknown"
            )
        storage = self.source_storage_hint
        evidence = detected_evidence or "storage_probe_unspecified"
        if storage == "auto":
            storage = detected_storage
        elif storage == "local" and detected_storage != "local":
            storage = detected_storage
            evidence = f"operator_local_not_verified:{evidence}"
        elif storage != detected_storage:
            evidence = f"operator_conservative_override:{storage}:{evidence}"
        budget = resolve_resource_budget(
            source_storage=storage,
            network_enabled=self.reverse_geocode_profile.enabled,
            ceiling=self.resource_budget,
            logical_cpu_count=logical_cpu_count,
            available_memory_bytes=available_memory_bytes,
        )
        metadata_batch_size = self.metadata_batch_size or min(
            200,
            max(16, (budget.capacity.memory_bytes - 16 * 1024 * 1024) // (512 * 1024)),
        )
        ffmpeg_threads = self.ffmpeg_threads or max(
            1,
            min(
                2,
                budget.capacity.cpu_slots // max(1, budget.capacity.process_slots),
            ),
        )
        model_batch_size = self.model_batch_size or max(
            1,
            min(16, budget.capacity.memory_bytes // (256 * 1024 * 1024)),
        )
        return replace(
            self,
            metadata_batch_size=metadata_batch_size,
            ffmpeg_threads=ffmpeg_threads,
            model_batch_size=model_batch_size,
            source_storage_hint=storage,
            source_storage_evidence=evidence,
            resource_budget=budget,
        )

    @classmethod
    def from_value(cls, value: Mapping[str, object]) -> PrecheckExecutionConfig:
        if value.get("version") != 4:
            raise ValueError("unsupported PreCheck execution configuration")
        budget_value = cast(Mapping[str, object], value["resource_budget"])
        capacity_value = cast(Mapping[str, object], budget_value["capacity"])
        geocode_value = cast(Mapping[str, object], value["reverse_geocode_profile"])
        return cls(
            metadata=bool(value["metadata"]),
            metadata_batch_size=int(value["metadata_batch_size"]),
            ffmpeg_threads=int(value["ffmpeg_threads"]),
            model_batch_size=int(value["model_batch_size"]),
            directed_evidence_paths=tuple(
                Path(str(path)) for path in value["directed_evidence_paths"]
            ),
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
            source_storage_hint=str(value["source_storage"]),
            source_storage_evidence=str(value["source_storage_evidence"]),
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
    geocoder: ReverseGeocodeBatchEngine | None = None


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
        attachment = accounting.get_source_attachment(accounting_run_id)
        config = config.resolve_resources(source_root=attachment.source_root)
        assert config.resource_budget is not None
        assert config.metadata_batch_size is not None
        assert config.ffmpeg_threads is not None
        assert config.model_batch_size is not None
        self._checkpoint(run_ref, "accounting", total="unknown")
        accounting.process_run(
            accounting_run_id,
            should_continue=lambda: self._running(run_ref),
            force_rescan=self.run_control.scope_selection_submitted(run_ref),
        )
        status = self.run_control.sync_accounting(run_ref)
        if status["state"] != "running":
            return status
        if not self._finish_phase(run_ref, "accounting"):
            return self.run_control.sync_accounting(run_ref)

        self._checkpoint(run_ref, "scope_review", total=1)
        status = self.run_control.require_scope_selection(run_ref, accounting_run_id)
        if status["state"] != "running":
            return status
        if not self._finish_phase(run_ref, "scope_review"):
            return self.run_control.sync_accounting(run_ref)

        def media_items() -> Iterator[AccountedItem]:
            return (
                item
                for item in accounting.iter_run_items(accounting_run_id)
                if item.scope == "source_media"
                and item.kind in _MEDIA_KINDS
                and item.source_revision is not None
            )

        media_count = accounting.count_run_items(
            accounting_run_id,
            scope="source_media",
            kinds=_MEDIA_KINDS,
            require_source_revision=True,
        )
        gpx_paths = tuple(
            item.relative_path
            for item in accounting.iter_run_items(accounting_run_id)
            if item.scope == "auxiliary"
            and item.kind == "gpx"
            and item.source_revision is not None
        )
        executor = BoundedWorkExecutor(config.resource_budget)

        self._checkpoint(
            run_ref,
            "metadata",
            total=media_count if config.metadata else 0,
        )
        self._metadata(run_ref, accounting_run_id, media_items(), config, executor)
        if not self._finish_phase(run_ref, "metadata"):
            return self.run_control.sync_accounting(run_ref)
        self._checkpoint(
            run_ref,
            "bundles",
            total="unknown" if config.bundles else 0,
        )
        bundle_outcomes = self._bundles(accounting_run_id, config)
        evidence_media, bundle_work_ids = _initial_evidence_media(
            media_items(), bundle_outcomes, config
        )
        if not self._finish_phase(run_ref, "bundles"):
            return self.run_control.sync_accounting(run_ref)
        evidence_paths = {item.relative_path for item in evidence_media}
        metadata = _selected_metadata(
            self.database_path, accounting_run_id, evidence_paths
        )
        demanded_metadata = metadata
        rendition_profiles = (
            2
            if config.embedding_profile is not None
            or config.sensitivity_profile is not None
            else 1
        )
        self._checkpoint(
            run_ref,
            "renditions",
            total=(
                sum(item.kind in _STILL_KINDS for item in evidence_media)
                * rendition_profiles
                if config.image_renditions
                else 0
            ),
        )
        renditions = self._renditions(
            run_ref, accounting_run_id, evidence_media, config, executor
        )
        if not self._finish_phase(run_ref, "renditions"):
            return self.run_control.sync_accounting(run_ref)
        self._checkpoint(
            run_ref,
            "video",
            total=(
                "unknown"
                if config.video and any(item.kind == "video" for item in evidence_media)
                else 0
            ),
        )
        probes, frames, sheets = self._video(
            run_ref, accounting_run_id, evidence_media, config, executor
        )
        if not self._finish_phase(run_ref, "video"):
            return self.run_control.sync_accounting(run_ref)
        self._checkpoint(
            run_ref,
            "gpx",
            total=(
                sum(
                    outcome.work.status is WorkStatus.SUCCEEDED
                    for outcome in metadata.values()
                )
                if config.gpx and gpx_paths
                else 0
            ),
        )
        gpx = self._gpx(
            run_ref,
            accounting_run_id,
            demanded_metadata,
            gpx_paths,
            config,
            executor,
        )
        if not self._finish_phase(run_ref, "gpx"):
            return self.run_control.sync_accounting(run_ref)
        self._checkpoint(
            run_ref,
            "embeddings",
            total="unknown" if config.embedding_profile is not None else 0,
        )
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
        self._checkpoint(
            run_ref,
            "sensitivity",
            total="unknown" if config.sensitivity_profile is not None else 0,
        )
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
        self._checkpoint(
            run_ref,
            "compression",
            total="unknown" if config.compression_target is not None else 0,
        )
        compression, representative_paths = self._compression(
            accounting_run_id,
            renditions,
            frames,
            sheets,
            key_frames,
            metadata,
            gpx,
            embeddings,
            bundle_work_ids,
            config,
        )
        if not self._finish_phase(run_ref, "compression"):
            return self.run_control.sync_accounting(run_ref)
        self._checkpoint(run_ref, "external_evidence", total="unknown")
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
            metadata_work_ids=(
                work_id
                for work_id in WorkStore(self.database_path).iter_run_work_ids(
                    accounting_run_id, capability="source-metadata"
                )
            ),
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
        self._checkpoint(run_ref, "publishing", total=1)
        return self.run_control.publish_result(run_ref, draft)

    def _metadata(
        self,
        run_ref: str,
        run_id: str,
        media: Iterable[AccountedItem],
        config: PrecheckExecutionConfig,
        executor: BoundedWorkExecutor,
    ) -> None:
        if not config.metadata:
            return
        kwargs: dict[str, object] = {}
        kwargs["should_continue"] = lambda: self._running(run_ref)
        if self.dependencies.metadata_runner is not None:
            kwargs["command_runner"] = self.dependencies.metadata_runner
        if self.dependencies.exiftool_version is not None:
            kwargs["exiftool_version"] = self.dependencies.exiftool_version
        producer = MetadataProducer(self.database_path, **kwargs)
        batches = _batched(media, config.metadata_batch_size)
        try:
            for _key, _batch_outcomes in self._execute(
                run_ref,
                executor,
                (
                    ScheduledCall(
                        f"metadata-batch:{index}",
                        ResourceClaim(
                            source_io_slots=1,
                            cpu_slots=1,
                            process_slots=1,
                            memory_bytes=min(
                                128 * 1024 * 1024,
                                16 * 1024 * 1024 + len(batch) * 512 * 1024,
                            ),
                            exiftool_slots=1,
                        ),
                        lambda batch=batch: producer.produce_many(
                            run_id,
                            (item.relative_path for item in batch),
                        ),
                    )
                    for index, batch in enumerate(batches)
                ),
            ):
                pass
        finally:
            producer.close()

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
        return tuple(value for _key, value in self._execute(run_ref, executor, calls))

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
        assert config.ffmpeg_threads is not None
        frame_kwargs["threads"] = config.ffmpeg_threads
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
            Path(key.removeprefix("video-probe:")): outcome for key, outcome in probes
        }
        frame_producer = VideoFrameProducer(self.database_path, **frame_kwargs)
        frame_calls = (
            ScheduledCall(
                f"video-frame:{path.as_posix()}:{sample_time:.6f}",
                ResourceClaim(
                    source_io_slots=1,
                    workspace_io_slots=1,
                    cpu_slots=config.ffmpeg_threads,
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
            for path, outcome in probe_by_path.items()
            if outcome.work.status is WorkStatus.SUCCEEDED and outcome.probe is not None
            for sample_time in sample_video_times(
                outcome.probe.duration_seconds,
                max_frames=config.video_frame_limit,
            )
        )
        frame_values = tuple(
            value for _key, value in self._execute(run_ref, executor, frame_calls)
        )
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
        sheets = tuple(
            value for _key, value in self._execute(run_ref, executor, sheet_calls)
        )
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
        return {Path(key.removeprefix("gpx:")): value for key, value in outcomes}

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
        visual = tuple(
            outcome
            for outcome in (*renditions, *frames)
            if outcome.work.status is WorkStatus.SUCCEEDED
            and (
                outcome.work.spec.capability == "video-frame"
                or _rendition_profile(outcome.work) == "high_resolution"
            )
        )
        producer = EmbeddingProducer(self.database_path, encoder)
        assert config.model_batch_size is not None
        batch_values = self._execute(
            run_ref,
            executor,
            (
                ScheduledCall(
                    f"embedding-batch:{index}",
                    ResourceClaim(
                        source_io_slots=1,
                        workspace_io_slots=1,
                        cpu_slots=1,
                        memory_bytes=min(
                            config.resource_budget.capacity.memory_bytes,
                            256 * 1024 * 1024 + len(batch) * 32 * 1024 * 1024,
                        ),
                        gpu_memory_bytes=(
                            config.resource_budget.capacity.gpu_memory_bytes
                        ),
                        temporary_bytes=32 * 1024 * 1024,
                        model_slots=1,
                    ),
                    lambda batch=batch: producer.produce_many(
                        run_id,
                        tuple(outcome.work.work_id for outcome in batch),
                        profile=profile,
                    ),
                )
                for index, batch in enumerate(_batched(visual, config.model_batch_size))
            ),
        )
        embeddings: dict[str, WorkRecord] = {}
        for _key, batch in batch_values:
            embeddings.update(
                {
                    input_work_id: outcome.work
                    for input_work_id, outcome in batch.items()
                    if outcome.work.status is WorkStatus.SUCCEEDED
                }
            )
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
        visual = tuple(
            outcome
            for outcome in (*renditions, *frames)
            if outcome.work.status is WorkStatus.SUCCEEDED
            and (
                outcome.work.spec.capability == "video-frame"
                or _rendition_profile(outcome.work) == "high_resolution"
            )
        )
        producer = SensitivityProducer(self.database_path, detector)
        assert config.model_batch_size is not None
        batch_values = self._execute(
            run_ref,
            executor,
            (
                ScheduledCall(
                    f"sensitivity-batch:{index}",
                    ResourceClaim(
                        source_io_slots=1,
                        cpu_slots=1,
                        memory_bytes=min(
                            config.resource_budget.capacity.memory_bytes,
                            256 * 1024 * 1024 + len(batch) * 32 * 1024 * 1024,
                        ),
                        gpu_memory_bytes=(
                            config.resource_budget.capacity.gpu_memory_bytes
                        ),
                        model_slots=1,
                    ),
                    lambda batch=batch: producer.produce_many(
                        run_id,
                        tuple(
                            (_work_subject(outcome.work), outcome.work.work_id)
                            for outcome in batch
                        ),
                        profile=profile,
                    ),
                )
                for index, batch in enumerate(_batched(visual, config.model_batch_size))
            ),
        )
        return tuple(
            outcome for _key, batch in batch_values for outcome in batch.values()
        )

    def _bundles(
        self,
        run_id: str,
        config: PrecheckExecutionConfig,
    ) -> Iterator[BundleCandidateOutcome]:
        if not config.bundles:
            return iter(())
        return BundleCandidateProducer(self.database_path).iter_produce(
            run_id,
            None,
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
        bundle_work_ids: tuple[str, ...],
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
        work_store = WorkStore(self.database_path)
        for bundle_work_id in bundle_work_ids:
            bundle_work = work_store.get_work(bundle_work_id)
            representative_path = _bundle_representative(bundle_work)
            member_paths = _bundle_member_paths(bundle_work)
            visual = visual_by_path.get(representative_path)
            if visual is None:
                continue
            inputs.append(
                self._compression_input(
                    representative_path,
                    visual,
                    metadata,
                    gpx,
                    embeddings,
                    member_paths=member_paths,
                    bundle_work_id=bundle_work_id,
                )
            )
            covered.update(path for path in member_paths if path in visual_by_path)
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
        outcomes = self._execute(
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
        _key, outcome = next(outcomes)
        return outcome

    def _execute(
        self,
        run_ref: str,
        executor: BoundedWorkExecutor,
        calls: Iterable[ScheduledCall[_T]],
    ) -> Iterator[tuple[str, _T]]:
        def guarded(call: ScheduledCall[_T]) -> ScheduledCall[_T]:
            def invoke() -> _T:
                if not self._running(run_ref):
                    raise ResourceAdmissionCancelled(
                        "Run stopped before scheduled Work began"
                    )
                return call.function()

            return ScheduledCall(call.key, call.claim, invoke)

        def guarded_calls() -> Iterator[ScheduledCall[_T]]:
            for call in calls:
                if not self._running(run_ref):
                    return
                yield guarded(call)

        for outcome in executor.iter_run(guarded_calls()):
            if outcome.error is None:
                yield outcome.key, cast(_T, outcome.value)
            elif not isinstance(outcome.error, ResourceAdmissionCancelled):
                raise outcome.error

    def _running(self, run_ref: str) -> bool:
        return self.run_control.current_state(run_ref) == "running"

    def _checkpoint(
        self, run_ref: str, phase: str, *, total: int | str | None = None
    ) -> None:
        self.run_control.record_phase(run_ref, phase, total=total)

    def _finish_phase(self, run_ref: str, phase: str) -> bool:
        self.run_control.record_phase(run_ref, phase, complete=True)
        self._after_phase(run_ref, phase)
        return self._running(run_ref)

    def _after_phase(self, run_ref: str, phase: str) -> None:
        """Fault-injection seam after a durable orchestration boundary."""


def _initial_evidence_media(
    media: Iterable[AccountedItem],
    bundles: Iterable[BundleCandidateOutcome],
    config: PrecheckExecutionConfig,
) -> tuple[tuple[AccountedItem, ...], tuple[str, ...]]:
    """Select the bounded initial visual frontier without reducing accounting."""

    requested = set(config.directed_evidence_paths)
    demanded = set(requested)
    evidence_limit = min(
        2_000,
        max(128, (config.compression_target or 200) * 4),
    )
    selected_heap: list[tuple[int, str, str, Path, tuple[Path, ...]]] = []
    saw_bundle = False
    for outcome in bundles:
        saw_bundle = True
        candidate = outcome.candidate
        if outcome.work.status is not WorkStatus.SUCCEEDED or candidate is None:
            raise _BlockedExecution(
                "bundle_frontier_incomplete",
                "Bundle candidate Work did not complete successfully.",
                "Resume the Run after retrying or resolving failed bundle Work.",
            )
        score = int(candidate.candidate_id.rsplit(":", 1)[-1], 16)
        entry = (
            -score,
            candidate.candidate_id,
            outcome.work.work_id,
            candidate.representative_path,
            candidate.boundary_paths,
        )
        if len(selected_heap) < evidence_limit:
            heapq.heappush(selected_heap, entry)
        elif score < -selected_heap[0][0]:
            heapq.heapreplace(selected_heap, entry)
    selected_entries = tuple(sorted(selected_heap, key=lambda entry: entry[1]))
    for _score, _candidate_id, _work_id, representative, boundaries in selected_entries:
        demanded.add(representative)
        demanded.update(boundaries)
    selected = []
    fallback_heap: list[tuple[int, str, AccountedItem]] = []
    seen_requested: set[Path] = set()
    for item in media:
        if item.relative_path in requested:
            seen_requested.add(item.relative_path)
        if saw_bundle and item.relative_path in demanded:
            selected.append(item)
        elif not saw_bundle and item.relative_path not in requested:
            path_value = item.relative_path.as_posix()
            score = int(hashlib.sha256(path_value.encode("utf-8")).hexdigest(), 16)
            entry = (-score, path_value, item)
            if len(fallback_heap) < evidence_limit:
                heapq.heappush(fallback_heap, entry)
            elif score < -fallback_heap[0][0]:
                heapq.heapreplace(fallback_heap, entry)
        elif item.relative_path in requested:
            selected.append(item)
    if not saw_bundle:
        selected.extend(entry[2] for entry in fallback_heap)
        selected.sort(key=lambda item: item.relative_path.as_posix())
    missing = requested - seen_requested
    if missing:
        paths = ", ".join(path.as_posix() for path in sorted(missing))
        raise _BlockedExecution(
            "directed_evidence_source_missing",
            f"Directed evidence paths are not eligible Source Items: {paths}",
            "Start a fresh Run with paths from the current Dataset accounting.",
        )
    return tuple(selected), tuple(entry[2] for entry in selected_entries)


def _bundle_representative(record: WorkRecord) -> Path:
    if not isinstance(record.output, Mapping):
        raise ValueError("bundle Work has no output")
    candidate = record.output.get("candidate")
    if not isinstance(candidate, Mapping):
        raise ValueError("bundle Work has no candidate output")
    value = candidate.get("representative_path")
    if not isinstance(value, str):
        raise ValueError("bundle Work has no representative path")
    return Path(value)


def _bundle_member_paths(record: WorkRecord) -> tuple[Path, ...]:
    members = []
    for dependency in record.spec.dependencies:
        if dependency.kind is not DependencyKind.SOURCE_REVISION:
            continue
        try:
            _dataset_id, relative_path = json.loads(dependency.key)
        except (TypeError, ValueError) as error:
            raise ValueError("bundle Work has an invalid source dependency") from error
        members.append(Path(str(relative_path)))
    return tuple(sorted(members))


def _selected_metadata(
    database_path: Path,
    run_id: str,
    selected_paths: Iterable[Path],
) -> dict[Path, MetadataOutcome]:
    requested = set(selected_paths)
    selected: dict[Path, MetadataOutcome] = {}
    if not requested:
        return selected
    work = WorkStore(database_path)
    for subject in sorted(requested):
        records = work.get_run_work_by_parameter(
            run_id,
            capability="source-metadata",
            key="subject_relative_path",
            value=subject.as_posix(),
        )
        if not records:
            continue
        if len(records) != 1:
            raise ValueError("multiple metadata Work Records for one source")
        record = records[0]
        observations: tuple[dict[str, object], ...] = ()
        if isinstance(record.output, Mapping):
            values = record.output.get("observations")
            if isinstance(values, list):
                observations = tuple(
                    cast(dict[str, object], value)
                    for value in values
                    if isinstance(value, dict)
                )
        selected[subject] = MetadataOutcome(record, observations, True)
    return selected


def _batched(items: Iterable[_T], size: int) -> Iterator[tuple[_T, ...]]:
    iterator = iter(items)
    while batch := tuple(islice(iterator, size)):
        yield batch


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
