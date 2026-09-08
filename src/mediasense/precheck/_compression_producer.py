"""Work-backed adapter for the pure adaptive-compression strategy."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
import json
from pathlib import Path

from ._artifact_types import ArtifactIntegrity
from ._compression_strategy import (
    AdaptiveCompressionProfile,
    CompressionGroup,
    CompressionPoint,
    _relative_path,
    build_adaptive_groups,
)
from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    upstream_dependency,
)
from .artifact import ArtifactStore
from .embedding import EmbeddingProfile, read_embedding
from .work import WorkStore


@dataclass(frozen=True, slots=True)
class CompressionInput:
    relative_path: Path
    visual_work_id: str
    member_paths: tuple[Path, ...] = ()
    bundle_work_id: str | None = None
    metadata_work_id: str | None = None
    gpx_work_id: str | None = None
    embedding_work_id: str | None = None

    def __post_init__(self) -> None:
        path = _relative_path(self.relative_path)
        members = self.member_paths or (path,)
        members = tuple(sorted({_relative_path(member) for member in members}))
        if path not in members:
            raise ValueError(
                "compression input members must include its representative"
            )
        if not self.visual_work_id.strip():
            raise ValueError("compression input requires visual Work")
        object.__setattr__(self, "relative_path", path)
        object.__setattr__(self, "member_paths", members)


@dataclass(frozen=True, slots=True)
class CompressionGroupOutcome:
    work: WorkRecord
    group: CompressionGroup | None
    reused: bool


class AdaptiveCompressionProducer:
    """Persist independently reusable group claims over explicit upstream Work."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.work = WorkStore(self.database_path)
        self.artifacts = ArtifactStore(self.database_path)

    def produce(
        self,
        run_id: str,
        inputs: Sequence[CompressionInput],
        *,
        profile: AdaptiveCompressionProfile,
        owner: str = "builtin-adaptive-compression",
    ) -> tuple[CompressionGroupOutcome, ...]:
        attached = {
            record.work_id: record for record in self.work.list_run_work(run_id)
        }
        prepared = tuple(self._prepare_input(run_id, item, attached) for item in inputs)
        points = tuple(item[0] for item in prepared)
        groups = build_adaptive_groups(points, profile)
        inputs_by_path = {item.relative_path: item for item in inputs}
        work_by_path = {point.relative_path: records for point, records in prepared}
        outcomes = []
        for group in groups:
            group_inputs = tuple(
                inputs_by_path[point.relative_path]
                for point in points
                if set(point.members) <= set(group.members)
            )
            upstream_records = {
                record.work_id: record
                for item in group_inputs
                for record in work_by_path[item.relative_path]
            }
            if any(
                item.bundle_work_id is not None
                and _mapping_value(
                    attached[item.bundle_work_id].output, "candidate"
                ).get("representative_path")
                != item.relative_path.as_posix()
                for item in group_inputs
            ):
                group = replace(
                    group,
                    qualifications=(
                        *group.qualifications,
                        "unavailable_bundle_representative_replaced",
                    ),
                )
            source_dependencies = {
                (dependency.kind, dependency.key): dependency
                for record in upstream_records.values()
                for dependency in record.spec.dependencies
                if dependency.kind
                in {DependencyKind.SOURCE_REVISION, DependencyKind.SOURCE_CONTENT}
                and _source_dependency_path(dependency) in group.members
            }
            dependencies = [
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "selection_basis",
                    json.dumps(group.basis, sort_keys=True),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "content_based_boundaries",
                    str(profile.content_based_boundaries),
                ),
                *source_dependencies.values(),
                *(upstream_dependency(record) for record in upstream_records.values()),
                WorkDependency(DependencyKind.PARAMETER, "group_id", group.group_id),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "target_entries",
                    str(profile.target_entries),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "temporal_scale_seconds",
                    format(profile.temporal_scale_seconds, ".17g"),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "spatial_scale_meters",
                    format(profile.spatial_scale_meters, ".17g"),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "content_distance_scale",
                    format(profile.content_distance_scale, ".17g"),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "representative_top_k",
                    format(profile.representative_top_k, ".17g"),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "exact_representative_limit",
                    str(profile.exact_representative_limit),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "representative_comparison_budget",
                    str(profile.representative_comparison_budget),
                ),
            ]
            if {path for item in group_inputs for path in item.member_paths} != set(
                group.members
            ):
                raise ValueError(
                    "compression group does not match declared memberships"
                )
            spec = WorkSpec(
                capability="adaptive-compression-group",
                producer_identity="builtin-adaptive-compression-v2",
                dependencies=tuple(dependencies),
            )
            record = self.work.ensure_work(run_id, spec)
            if record.status is WorkStatus.SUCCEEDED:
                outcomes.append(CompressionGroupOutcome(record, group, True))
                continue
            if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
                outcomes.append(CompressionGroupOutcome(record, None, False))
                continue
            leases = self.work.claim_ready_work(
                run_id,
                owner,
                lease_duration=timedelta(minutes=5),
                work_id=record.work_id,
            )
            if not leases:
                outcomes.append(
                    CompressionGroupOutcome(
                        self.work.get_work(record.work_id), None, False
                    )
                )
                continue
            completed = self.work.succeed_work(
                leases[0],
                {"group": _group_value(group), "profile": _profile_value(profile)},
            )
            outcomes.append(CompressionGroupOutcome(completed, group, False))
        return tuple(outcomes)

    def _prepare_input(
        self,
        run_id: str,
        item: CompressionInput,
        attached: Mapping[str, WorkRecord],
    ) -> tuple[CompressionPoint, tuple[WorkRecord, ...]]:
        visual = _attached_work(
            attached,
            item.visual_work_id,
            {"image-rendition", "video-contact-sheet", "video-frame"},
            "visual",
        )
        records = [visual]
        if item.bundle_work_id is not None:
            bundle = _attached_work(
                attached, item.bundle_work_id, {"bundle-candidate"}, "bundle"
            )
            records.append(bundle)
            _mapping_value(bundle.output, "candidate")
            # A bundle's preferred representative is a candidate, not a guarantee
            # of decodability. Any verified visual member can represent it.
            if _record_source_paths(bundle) != set(item.member_paths):
                raise ValueError("bundle Work membership does not match input")
        elif item.member_paths != (item.relative_path,):
            raise ValueError("multi-source compression input requires bundle Work")
        if item.relative_path not in _record_source_paths(visual):
            raise ValueError("visual Work belongs to a different Source Item")

        metadata = _optional_attached_work(
            attached, item.metadata_work_id, "source-metadata"
        )
        gpx = _optional_attached_work(
            attached, item.gpx_work_id, "gpx-location-candidate"
        )
        embedding = _optional_attached_work(
            attached, item.embedding_work_id, "image-embedding"
        )
        records.extend(
            record for record in (metadata, gpx, embedding) if record is not None
        )
        if metadata is not None and _record_subject(metadata) != item.relative_path:
            raise ValueError("metadata Work belongs to another Source Item")
        if gpx is not None and _record_subject(gpx) != item.relative_path:
            raise ValueError("GPX Work belongs to another Source Item")
        if embedding is not None and not any(
            dependency.kind is DependencyKind.UPSTREAM_WORK
            and dependency.key == visual.work_id
            for dependency in embedding.spec.dependencies
        ):
            raise ValueError("embedding Work does not depend on the visual input")

        capture_time = _capture_time(metadata)
        gps = _gps_value(metadata) or _gps_value(gpx)
        vector = None if embedding is None else self._embedding_value(embedding)
        return (
            CompressionPoint(
                relative_path=item.relative_path,
                capture_time=capture_time,
                gps=gps,
                embedding=vector,
                members=item.member_paths,
                weight=len(item.member_paths),
            ),
            tuple(records),
        )

    def _embedding_value(self, record: WorkRecord) -> tuple[float, ...]:
        value = _mapping_value(record.output, "value")
        profile = EmbeddingProfile(
            name=str(value["profile"]),
            dimensions=int(value["dimensions"]),
            normalization=str(value["normalization"]),
            dtype=str(value["dtype"]),
        )
        produced = self.artifacts.artifacts_for_work(record.work_id)
        if not produced or produced[0].integrity is not ArtifactIntegrity.AVAILABLE:
            raise ValueError("embedding Artifact must be available")
        artifact = self.artifacts.require_available(produced[0].artifact_id)
        return read_embedding(artifact, profile)


def _attached_work(
    attached: Mapping[str, WorkRecord],
    work_id: str,
    capabilities: set[str],
    label: str,
) -> WorkRecord:
    record = attached.get(work_id)
    if record is None or record.spec.capability not in capabilities:
        raise ValueError(f"{label} Work is not attached to this run")
    if record.status is not WorkStatus.SUCCEEDED:
        raise ValueError(f"{label} Work must succeed before compression")
    return record


def _optional_attached_work(
    attached: Mapping[str, WorkRecord],
    work_id: str | None,
    capability: str,
) -> WorkRecord | None:
    if work_id is None:
        return None
    return _attached_work(attached, work_id, {capability}, capability)


def _record_source_paths(record: WorkRecord) -> set[Path]:
    paths = set()
    for dependency in record.spec.dependencies:
        path = _source_dependency_path(dependency)
        if path is not None:
            paths.add(path)
    return paths


def _source_dependency_path(dependency: WorkDependency) -> Path | None:
    if dependency.kind not in {
        DependencyKind.SOURCE_REVISION,
        DependencyKind.SOURCE_CONTENT,
    }:
        return None
    try:
        _dataset_id, relative_path = json.loads(dependency.key)
    except (TypeError, ValueError) as error:
        raise ValueError("Work has an invalid source dependency") from error
    return _relative_path(Path(relative_path))


def _record_subject(record: WorkRecord) -> Path | None:
    value = next(
        (
            dependency.value
            for dependency in record.spec.dependencies
            if dependency.kind is DependencyKind.PARAMETER
            and dependency.key == "subject_relative_path"
        ),
        None,
    )
    return None if value is None else _relative_path(Path(value))


def _mapping_value(output: object | None, key: str) -> Mapping[str, object]:
    if not isinstance(output, Mapping) or not isinstance(output.get(key), Mapping):
        raise ValueError(f"Work output has no valid {key}")
    return output[key]


def _capture_time(record: WorkRecord | None) -> datetime | None:
    value = _observation_value(record, "capture_time")
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value)
    return (
        parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    )


def _gps_value(record: WorkRecord | None) -> tuple[float, float] | None:
    value = _observation_value(record, "gps_coordinates")
    if not isinstance(value, Mapping):
        return None
    latitude = value.get("latitude")
    longitude = value.get("longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(
        longitude, (int, float)
    ):
        return None
    return float(latitude), float(longitude)


def _observation_value(record: WorkRecord | None, name: str) -> object | None:
    if record is None or not isinstance(record.output, Mapping):
        return None
    observations = record.output.get("observations")
    if not isinstance(observations, list):
        return None
    return next(
        (
            item.get("value")
            for item in observations
            if isinstance(item, Mapping)
            and item.get("name") == name
            and item.get("status") == "available"
        ),
        None,
    )


def _group_value(group: CompressionGroup) -> dict[str, object]:
    return {
        "basis": group.basis,
        "boundary_paths": [path.as_posix() for path in group.boundary_paths],
        "conflict_paths": [path.as_posix() for path in group.conflict_paths],
        "group_id": group.group_id,
        "member_count": len(group.members),
        "outlier_paths": [path.as_posix() for path in group.outlier_paths],
        "qualifications": list(group.qualifications),
        "representative_path": group.representative_path.as_posix(),
    }


def _profile_value(profile: AdaptiveCompressionProfile) -> dict[str, object]:
    return {
        "content_based_boundaries": profile.content_based_boundaries,
        "content_distance_scale": profile.content_distance_scale,
        "exact_representative_limit": profile.exact_representative_limit,
        "representative_comparison_budget": (profile.representative_comparison_budget),
        "representative_top_k": profile.representative_top_k,
        "spatial_scale_meters": profile.spatial_scale_meters,
        "target_entries": profile.target_entries,
        "temporal_scale_seconds": profile.temporal_scale_seconds,
    }


__all__ = [
    "AdaptiveCompressionProducer",
    "CompressionGroupOutcome",
    "CompressionInput",
]
