"""Inspectable filename and temporal bundle candidates for adaptive compression."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
    upstream_dependency,
)
from .accounting import AccountingStore
from .discovery import SourceScope, association_key
from .work import WorkStore


_DEFAULT_REPRESENTATIVE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".heic",
    ".png",
    ".mov",
    ".mp4",
)


@dataclass(frozen=True, slots=True)
class BundleProfile:
    max_gap_seconds: float = 60.0
    representative_extensions: tuple[str, ...] = _DEFAULT_REPRESENTATIVE_EXTENSIONS

    def __post_init__(self) -> None:
        if self.max_gap_seconds < 0:
            raise ValueError("bundle time gap must be nonnegative")
        normalized = tuple(value.casefold() for value in self.representative_extensions)
        if not normalized or any(not value.startswith(".") for value in normalized):
            raise ValueError("representative extensions must be non-empty suffixes")
        if len(normalized) != len(set(normalized)):
            raise ValueError("representative extensions must be unique")
        object.__setattr__(self, "representative_extensions", normalized)


@dataclass(frozen=True, slots=True)
class BundleItem:
    relative_path: Path
    capture_time: datetime | None
    source_revision: int | None = None
    metadata_work_id: str | None = None

    def __post_init__(self) -> None:
        path = Path(self.relative_path)
        if path.is_absolute() or path == Path(".") or ".." in path.parts:
            raise ValueError("bundle item paths must stay relative")
        if self.capture_time is not None and (
            self.capture_time.tzinfo is None or self.capture_time.utcoffset() is None
        ):
            raise ValueError("bundle capture times must be timezone-aware")
        if self.source_revision is not None and self.source_revision < 1:
            raise ValueError("bundle source revision must be positive")
        object.__setattr__(self, "relative_path", path)


@dataclass(frozen=True, slots=True)
class BundleCandidate:
    candidate_id: str
    members: tuple[Path, ...]
    representative_path: Path
    boundary_paths: tuple[Path, ...]
    span_seconds: float | None
    qualifications: tuple[str, ...]
    basis: dict[str, object]


@dataclass(frozen=True, slots=True)
class BundleCandidateOutcome:
    work: WorkRecord
    candidate: BundleCandidate | None
    reused: bool


class BundleCandidateProducer:
    """Persist one bounded Work result per current filename/time candidate group."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.accounting = AccountingStore(self.database_path)
        self.work = WorkStore(self.database_path)

    def produce(
        self,
        run_id: str,
        metadata_work_ids: Iterable[str] = (),
        *,
        profile: BundleProfile = BundleProfile(),
        owner: str = "builtin-bundle-candidate",
    ) -> tuple[BundleCandidateOutcome, ...]:
        summary = self.accounting.get_run_summary(run_id)
        metadata = _metadata_by_path(self.work, run_id, metadata_work_ids)
        items = tuple(
            BundleItem(
                item.relative_path,
                _capture_time(metadata.get(item.relative_path)),
                source_revision=item.source_revision,
                metadata_work_id=(
                    None
                    if item.relative_path not in metadata
                    else metadata[item.relative_path].work_id
                ),
            )
            for item in self.accounting.get_run_items(run_id)
            if item.scope == SourceScope.SOURCE_MEDIA
            and item.source_revision is not None
        )
        candidates = build_bundle_candidates(items, profile)
        item_by_path = {item.relative_path: item for item in items}
        outcomes = []
        for candidate in candidates:
            dependencies: list[WorkDependency] = []
            metadata_ids: set[str] = set()
            for member_path in candidate.members:
                item = item_by_path[member_path]
                assert item.source_revision is not None
                dependencies.append(
                    source_revision_dependency(
                        summary.dataset_id, member_path, item.source_revision
                    )
                )
                if item.metadata_work_id is not None:
                    metadata_ids.add(item.metadata_work_id)
            dependencies.extend(
                upstream_dependency(self.work.get_work(work_id))
                for work_id in sorted(metadata_ids)
            )
            dependencies.extend(
                (
                    WorkDependency(
                        DependencyKind.PARAMETER,
                        "candidate_id",
                        candidate.candidate_id,
                    ),
                    WorkDependency(
                        DependencyKind.PARAMETER,
                        "max_gap_seconds",
                        format(profile.max_gap_seconds, ".17g"),
                    ),
                    WorkDependency(
                        DependencyKind.PARAMETER,
                        "representative_extensions",
                        json.dumps(profile.representative_extensions),
                    ),
                )
            )
            spec = WorkSpec(
                capability="bundle-candidate",
                producer_identity="builtin-filename-temporal-bundle-v1",
                dependencies=tuple(dependencies),
            )
            record = self.work.ensure_work(run_id, spec)
            if record.status is WorkStatus.SUCCEEDED:
                outcomes.append(BundleCandidateOutcome(record, candidate, True))
                continue
            if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
                outcomes.append(BundleCandidateOutcome(record, None, False))
                continue
            leases = self.work.claim_ready_work(
                run_id,
                owner,
                lease_duration=timedelta(minutes=2),
                work_id=record.work_id,
            )
            if not leases:
                outcomes.append(
                    BundleCandidateOutcome(
                        self.work.get_work(record.work_id), None, False
                    )
                )
                continue
            completed = self.work.succeed_work(
                leases[0],
                {
                    "candidate": {
                        "basis": candidate.basis,
                        "boundary_paths": [
                            path.as_posix() for path in candidate.boundary_paths
                        ],
                        "candidate_id": candidate.candidate_id,
                        "member_count": len(candidate.members),
                        "qualifications": list(candidate.qualifications),
                        "representative_path": candidate.representative_path.as_posix(),
                        "span_seconds": candidate.span_seconds,
                    }
                },
            )
            outcomes.append(BundleCandidateOutcome(completed, candidate, False))
        return tuple(outcomes)


def build_bundle_candidates(
    items: Iterable[BundleItem], profile: BundleProfile = BundleProfile()
) -> tuple[BundleCandidate, ...]:
    ordered_items = tuple(sorted(items, key=lambda item: item.relative_path.as_posix()))
    if len({item.relative_path for item in ordered_items}) != len(ordered_items):
        raise ValueError("bundle candidate input paths must be unique")
    if not ordered_items:
        return ()
    parent = list(range(len(ordered_items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    filename_groups: dict[Path, list[int]] = defaultdict(list)
    for index, item in enumerate(ordered_items):
        filename_groups[association_key(item.relative_path)].append(index)
    for indices in filename_groups.values():
        for index in indices[1:]:
            union(indices[0], index)

    components = _components(parent)
    timed_components: list[tuple[datetime, int]] = []
    for root, indices in components.items():
        selected_time = _component_time(ordered_items, indices, profile)
        if selected_time is not None:
            timed_components.append((selected_time, root))
    timed_components.sort(key=lambda value: (value[0], value[1]))
    for (previous_time, previous_root), (current_time, current_root) in zip(
        timed_components, timed_components[1:], strict=False
    ):
        gap = (current_time - previous_time).total_seconds()
        if gap <= profile.max_gap_seconds:
            union(previous_root, current_root)

    groups = []
    for indices in _components(parent).values():
        members = tuple(sorted(ordered_items[index].relative_path for index in indices))
        representative = _select_representative(members, profile)
        timed_members = sorted(
            (
                (ordered_items[index].capture_time, ordered_items[index].relative_path)
                for index in indices
                if ordered_items[index].capture_time is not None
            ),
            key=lambda value: (value[0], value[1].as_posix()),
        )
        span = (
            None
            if not timed_members
            else (timed_members[-1][0] - timed_members[0][0]).total_seconds()
        )
        boundaries = (
            (representative,)
            if not timed_members
            else tuple(dict.fromkeys((timed_members[0][1], timed_members[-1][1])))
        )
        qualifications = []
        if span is not None and span > profile.max_gap_seconds:
            qualifications.append("adjacent_chain_exceeds_gap")
        if not timed_members:
            qualifications.append("capture_time_unavailable")
        candidate_id = _candidate_id(members)
        groups.append(
            BundleCandidate(
                candidate_id=candidate_id,
                members=members,
                representative_path=representative,
                boundary_paths=boundaries,
                span_seconds=span,
                qualifications=tuple(qualifications),
                basis={
                    "filename_association": "same-directory-stem-appledouble-m01-m02-v1",
                    "representative_priority": list(profile.representative_extensions),
                    "temporal_adjacency_seconds": profile.max_gap_seconds,
                },
            )
        )
    return tuple(sorted(groups, key=lambda group: group.representative_path.as_posix()))


def _components(parent: list[int]) -> dict[int, list[int]]:
    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    groups: dict[int, list[int]] = defaultdict(list)
    for index in range(len(parent)):
        groups[find(index)].append(index)
    return groups


def _component_time(
    items: tuple[BundleItem, ...], indices: list[int], profile: BundleProfile
) -> datetime | None:
    representative = _select_representative(
        tuple(items[index].relative_path for index in indices), profile
    )
    representative_time = next(
        item.capture_time for item in items if item.relative_path == representative
    )
    if representative_time is not None:
        return representative_time
    available = sorted(
        item.capture_time
        for item in (items[index] for index in indices)
        if item.capture_time is not None
    )
    return None if not available else available[0]


def _select_representative(paths: tuple[Path, ...], profile: BundleProfile) -> Path:
    ordered = tuple(sorted(paths, key=lambda path: path.as_posix()))
    for extension in profile.representative_extensions:
        for path in ordered:
            if not path.name.startswith("._") and path.suffix.casefold() == extension:
                return path
    return next(
        (path for path in ordered if not path.name.startswith("._")), ordered[0]
    )


def _candidate_id(members: tuple[Path, ...]) -> str:
    encoded = json.dumps(
        [path.as_posix() for path in members],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "bundle-candidate:sha256:" + hashlib.sha256(encoded).hexdigest()


def _metadata_by_path(
    work: WorkStore,
    run_id: str,
    work_ids: Iterable[str],
) -> dict[Path, WorkRecord]:
    attached = {record.work_id: record for record in work.list_run_work(run_id)}
    selected: dict[Path, WorkRecord] = {}
    for work_id in dict.fromkeys(work_ids):
        record = attached.get(work_id)
        if record is None or record.spec.capability != "source-metadata":
            raise ValueError("metadata Work is not attached to this run")
        if record.status is not WorkStatus.SUCCEEDED:
            raise ValueError("metadata Work must succeed before bundling")
        subject = next(
            (
                dependency.value
                for dependency in record.spec.dependencies
                if dependency.kind is DependencyKind.PARAMETER
                and dependency.key == "subject_relative_path"
            ),
            None,
        )
        if subject is None:
            raise ValueError("metadata Work has no subject path")
        path = Path(subject)
        if path in selected:
            raise ValueError("multiple metadata Work Records for one source")
        selected[path] = record
    return selected


def _capture_time(record: WorkRecord | None) -> datetime | None:
    if record is None or not isinstance(record.output, Mapping):
        return None
    observations = record.output.get("observations")
    if not isinstance(observations, list):
        return None
    value = next(
        (
            item.get("value")
            for item in observations
            if isinstance(item, Mapping)
            and item.get("name") == "capture_time"
            and item.get("status") == "available"
        ),
        None,
    )
    if not isinstance(value, str):
        return None
    parsed = datetime.fromisoformat(value)
    return (
        parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None
    )


__all__ = [
    "BundleCandidate",
    "BundleCandidateOutcome",
    "BundleCandidateProducer",
    "BundleItem",
    "BundleProfile",
    "build_bundle_candidates",
]
