"""Inspectable filename and temporal bundle candidates for adaptive compression."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from typing import Iterator

from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
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
    max_members: int = 1_000
    representative_extensions: tuple[str, ...] = _DEFAULT_REPRESENTATIVE_EXTENSIONS

    def __post_init__(self) -> None:
        if self.max_gap_seconds < 0:
            raise ValueError("bundle time gap must be nonnegative")
        if self.max_members < 1:
            raise ValueError("bundle max_members must be positive")
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
    metadata_semantic_key: str | None = None

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
        if (self.metadata_work_id is None) != (self.metadata_semantic_key is None):
            raise ValueError("bundle metadata identity must be complete")
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
        metadata_work_ids: Iterable[str] | None = None,
        *,
        profile: BundleProfile = BundleProfile(),
        owner: str = "builtin-bundle-candidate",
    ) -> Iterator[BundleCandidateOutcome]:
        return self.iter_produce(
            run_id,
            metadata_work_ids,
            profile=profile,
            owner=owner,
        )

    def iter_produce(
        self,
        run_id: str,
        metadata_work_ids: Iterable[str] | None = None,
        *,
        profile: BundleProfile = BundleProfile(),
        owner: str = "builtin-bundle-candidate",
    ) -> Iterator[BundleCandidateOutcome]:
        """Produce candidates from a disk-backed spool, one bounded group at a time."""

        summary = self.accounting.get_run_summary(run_id)
        for candidate, items in _iter_spooled_candidates(
            self.database_path,
            run_id,
            metadata_work_ids,
            profile,
        ):
            dependencies: list[WorkDependency] = []
            for item in items:
                assert item.source_revision is not None
                dependencies.append(
                    source_revision_dependency(
                        summary.dataset_id, item.relative_path, item.source_revision
                    )
                )
                if item.metadata_work_id is not None:
                    assert item.metadata_semantic_key is not None
                    dependencies.append(
                        WorkDependency(
                            DependencyKind.UPSTREAM_WORK,
                            item.metadata_work_id,
                            item.metadata_semantic_key,
                        )
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
                        "max_members",
                        str(profile.max_members),
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
                yield BundleCandidateOutcome(record, candidate, True)
                continue
            if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
                yield BundleCandidateOutcome(record, None, False)
                continue
            leases = self.work.claim_ready_work(
                run_id,
                owner,
                lease_duration=timedelta(minutes=2),
                work_id=record.work_id,
            )
            if not leases:
                yield BundleCandidateOutcome(
                    self.work.get_work(record.work_id), None, False
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
            yield BundleCandidateOutcome(completed, candidate, False)


def _iter_spooled_candidates(
    database_path: Path,
    run_id: str,
    metadata_work_ids: Iterable[str] | None,
    profile: BundleProfile,
) -> Iterator[tuple[BundleCandidate, tuple[BundleItem, ...]]]:
    """Externalize global ordering while keeping each in-memory group bounded."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix="mediasense-bundles-",
        suffix=".sqlite3",
        dir=database_path.parent,
        delete=False,
    )
    spool_path = Path(handle.name)
    handle.close()
    try:
        _build_bundle_spool(
            database_path,
            spool_path,
            run_id,
            metadata_work_ids,
            profile,
        )
        with sqlite3.connect(spool_path) as spool:
            spool.row_factory = sqlite3.Row
            for row in spool.execute(
                """
                SELECT component_id, limited
                FROM components
                WHERE capture_timestamp IS NULL
                ORDER BY component_id
                """
            ):
                yield _candidate_from_spool(
                    spool,
                    (int(row["component_id"]),),
                    profile,
                    member_limit_applied=bool(row["limited"]),
                )

            chain: list[int] = []
            chain_count = 0
            chain_limited = False
            previous_time: float | None = None
            for row in spool.execute(
                """
                SELECT component_id, capture_timestamp, member_count, limited
                FROM components
                WHERE capture_timestamp IS NOT NULL
                ORDER BY capture_timestamp, component_id
                """
            ):
                current_time = float(row["capture_timestamp"])
                member_count = int(row["member_count"])
                within_gap = (
                    previous_time is not None
                    and current_time - previous_time <= profile.max_gap_seconds
                )
                exceeds_limit = bool(chain) and (
                    chain_count + member_count > profile.max_members
                )
                if chain and (not within_gap or exceeds_limit):
                    if exceeds_limit and within_gap:
                        chain_limited = True
                    yield _candidate_from_spool(
                        spool,
                        tuple(chain),
                        profile,
                        member_limit_applied=chain_limited,
                    )
                    chain = []
                    chain_count = 0
                    chain_limited = exceeds_limit and within_gap
                chain.append(int(row["component_id"]))
                chain_count += member_count
                chain_limited = chain_limited or bool(row["limited"])
                previous_time = current_time
            if chain:
                yield _candidate_from_spool(
                    spool,
                    tuple(chain),
                    profile,
                    member_limit_applied=chain_limited,
                )
    finally:
        spool_path.unlink(missing_ok=True)


def _build_bundle_spool(
    database_path: Path,
    spool_path: Path,
    run_id: str,
    metadata_work_ids: Iterable[str] | None,
    profile: BundleProfile,
) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("ATTACH DATABASE ? AS bundle_spool", (str(spool_path),))
        connection.executescript(
            """
            CREATE TABLE bundle_spool.selected_metadata (
                work_id TEXT PRIMARY KEY
            );
            CREATE TABLE bundle_spool.metadata_by_path (
                relative_path TEXT PRIMARY KEY,
                work_id TEXT NOT NULL,
                semantic_key TEXT NOT NULL,
                output_json TEXT NOT NULL
            ) WITHOUT ROWID;
            CREATE TABLE bundle_spool.components (
                component_id INTEGER PRIMARY KEY,
                capture_timestamp REAL,
                member_count INTEGER NOT NULL,
                limited INTEGER NOT NULL
            );
            CREATE INDEX bundle_spool.components_time
                ON components(capture_timestamp, component_id);
            CREATE TABLE bundle_spool.members (
                component_id INTEGER NOT NULL,
                relative_path TEXT NOT NULL,
                capture_time TEXT,
                source_revision INTEGER NOT NULL,
                metadata_work_id TEXT,
                metadata_semantic_key TEXT,
                PRIMARY KEY (component_id, relative_path)
            );
            """
        )
        if metadata_work_ids is not None:
            connection.executemany(
                """
                INSERT OR IGNORE INTO bundle_spool.selected_metadata(work_id)
                VALUES (?)
                """,
                ((str(work_id),) for work_id in metadata_work_ids),
            )
            invalid = connection.execute(
                """
                SELECT selected_metadata.work_id
                FROM bundle_spool.selected_metadata AS selected_metadata
                LEFT JOIN run_work_records
                  ON run_work_records.run_id = ?
                 AND run_work_records.work_id = selected_metadata.work_id
                LEFT JOIN work_records
                  ON work_records.work_id = selected_metadata.work_id
                WHERE run_work_records.work_id IS NULL
                   OR work_records.capability <> 'source-metadata'
                   OR work_records.status <> 'succeeded'
                LIMIT 1
                """,
                (run_id,),
            ).fetchone()
            if invalid is not None:
                raise ValueError(
                    "metadata Work is not successful and attached to this run"
                )

        metadata_selection = (
            "JOIN bundle_spool.selected_metadata AS selected_metadata "
            "ON selected_metadata.work_id = work_records.work_id"
            if metadata_work_ids is not None
            else ""
        )
        connection.execute(
            f"""
            INSERT INTO bundle_spool.metadata_by_path(
                relative_path, work_id, semantic_key, output_json
            )
            SELECT subject_dependency.dependency_value,
                   work_records.work_id,
                   work_records.semantic_key,
                   work_records.output_json
            FROM work_records
            JOIN run_work_records
              ON run_work_records.work_id = work_records.work_id
             AND run_work_records.run_id = ?
            {metadata_selection}
            JOIN work_dependencies AS subject_dependency
              ON subject_dependency.work_id = work_records.work_id
             AND subject_dependency.dependency_kind = 'parameter'
             AND subject_dependency.dependency_key = 'subject_relative_path'
            WHERE work_records.capability = 'source-metadata'
              AND work_records.status = 'succeeded'
            """,
            (run_id,),
        )

        rows = connection.execute(
            """
            SELECT run_items.association_key,
                   run_items.relative_path,
                   run_items.source_revision,
                   metadata.work_id AS metadata_work_id,
                   metadata.semantic_key AS metadata_semantic_key,
                   metadata.output_json AS metadata_output_json
            FROM run_items
            LEFT JOIN bundle_spool.metadata_by_path AS metadata
              ON metadata.relative_path = run_items.relative_path
            WHERE run_items.run_id = ?
              AND run_items.scope = ?
              AND run_items.source_revision IS NOT NULL
            ORDER BY run_items.association_key, run_items.relative_path
            """,
            (run_id, SourceScope.SOURCE_MEDIA.value),
        )
        current_key: str | None = None
        chunk: list[BundleItem] = []
        group_split = False
        for row in rows:
            association = str(row["association_key"])
            if current_key is not None and association != current_key:
                _insert_spool_component(
                    connection, chunk, profile, limited=group_split
                )
                chunk = []
                group_split = False
            current_key = association
            if len(chunk) == profile.max_members:
                _insert_spool_component(connection, chunk, profile, limited=True)
                chunk = []
                group_split = True
            chunk.append(
                BundleItem(
                    Path(str(row["relative_path"])),
                    _capture_time_json(row["metadata_output_json"]),
                    source_revision=int(row["source_revision"]),
                    metadata_work_id=(
                        None
                        if row["metadata_work_id"] is None
                        else str(row["metadata_work_id"])
                    ),
                    metadata_semantic_key=(
                        None
                        if row["metadata_semantic_key"] is None
                        else str(row["metadata_semantic_key"])
                    ),
                )
            )
        if chunk:
            _insert_spool_component(connection, chunk, profile, limited=group_split)
        connection.commit()
        connection.execute("DETACH DATABASE bundle_spool")


def _insert_spool_component(
    connection: sqlite3.Connection,
    items: list[BundleItem],
    profile: BundleProfile,
    *,
    limited: bool,
) -> None:
    if not items:
        return
    values = tuple(items)
    capture_time = _component_time(values, list(range(len(values))), profile)
    inserted = connection.execute(
        """
        INSERT INTO bundle_spool.components(
            capture_timestamp, member_count, limited
        ) VALUES (?, ?, ?)
        """,
        (
            None if capture_time is None else capture_time.timestamp(),
            len(values),
            int(limited),
        ),
    )
    component_id = int(inserted.lastrowid)
    connection.executemany(
        """
        INSERT INTO bundle_spool.members(
            component_id, relative_path, capture_time,
            source_revision, metadata_work_id, metadata_semantic_key
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            (
                component_id,
                item.relative_path.as_posix(),
                None if item.capture_time is None else item.capture_time.isoformat(),
                item.source_revision,
                item.metadata_work_id,
                item.metadata_semantic_key,
            )
            for item in values
        ),
    )


def _candidate_from_spool(
    spool: sqlite3.Connection,
    component_ids: tuple[int, ...],
    profile: BundleProfile,
    *,
    member_limit_applied: bool,
) -> tuple[BundleCandidate, tuple[BundleItem, ...]]:
    placeholders = ",".join("?" for _component_id in component_ids)
    rows = spool.execute(
        f"""
        SELECT relative_path, capture_time, source_revision,
               metadata_work_id, metadata_semantic_key
        FROM members
        WHERE component_id IN ({placeholders})
        ORDER BY relative_path
        """,
        component_ids,
    ).fetchall()
    items = tuple(
        BundleItem(
            Path(str(row["relative_path"])),
            (
                None
                if row["capture_time"] is None
                else datetime.fromisoformat(str(row["capture_time"]))
            ),
            source_revision=int(row["source_revision"]),
            metadata_work_id=(
                None
                if row["metadata_work_id"] is None
                else str(row["metadata_work_id"])
            ),
            metadata_semantic_key=(
                None
                if row["metadata_semantic_key"] is None
                else str(row["metadata_semantic_key"])
            ),
        )
        for row in rows
    )
    candidate = _bundle_candidate_from_items(
        items,
        profile,
        member_limit_applied=member_limit_applied,
    )
    return candidate, items


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
    for component_indices in _components(parent).values():
        ordered_indices = sorted(
            component_indices,
            key=lambda index: (
                ordered_items[index].capture_time is None,
                ordered_items[index].capture_time
                or datetime.max.replace(tzinfo=timezone.utc),
                ordered_items[index].relative_path.as_posix(),
            ),
        )
        chunks = tuple(
            ordered_indices[offset : offset + profile.max_members]
            for offset in range(0, len(ordered_indices), profile.max_members)
        )
        for indices in chunks:
            groups.append(
                _bundle_candidate(
                    ordered_items,
                    indices,
                    profile,
                    member_limit_applied=len(chunks) > 1,
                )
            )
    return tuple(sorted(groups, key=lambda group: group.representative_path.as_posix()))


def _bundle_candidate(
    ordered_items: tuple[BundleItem, ...],
    indices: list[int],
    profile: BundleProfile,
    *,
    member_limit_applied: bool,
) -> BundleCandidate:
    return _bundle_candidate_from_items(
        tuple(ordered_items[index] for index in indices),
        profile,
        member_limit_applied=member_limit_applied,
    )


def _bundle_candidate_from_items(
    items: tuple[BundleItem, ...],
    profile: BundleProfile,
    *,
    member_limit_applied: bool,
) -> BundleCandidate:
    members = tuple(sorted(item.relative_path for item in items))
    representative = _select_representative(members, profile)
    timed_members = sorted(
        (
            (item.capture_time, item.relative_path)
            for item in items
            if item.capture_time is not None
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
    if member_limit_applied:
        qualifications.append("bundle_member_limit_applied")
    candidate_id = _candidate_id(members)
    return BundleCandidate(
        candidate_id=candidate_id,
        members=members,
        representative_path=representative,
        boundary_paths=boundaries,
        span_seconds=span,
        qualifications=tuple(qualifications),
        basis={
            "filename_association": "same-directory-stem-appledouble-m01-m02-v1",
            "max_members": profile.max_members,
            "representative_priority": list(profile.representative_extensions),
            "temporal_adjacency_seconds": profile.max_gap_seconds,
        },
    )


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
        items[index].capture_time
        for index in indices
        if items[index].relative_path == representative
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
    attached = {
        record.work_id: record
        for record in work.iter_run_work(run_id, capability="source-metadata")
    }
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
    return _capture_time_output(record.output)


def _capture_time_json(output_json: object) -> datetime | None:
    if not isinstance(output_json, str):
        return None
    try:
        output = json.loads(output_json)
    except json.JSONDecodeError:
        return None
    return _capture_time_output(output)


def _capture_time_output(output: object) -> datetime | None:
    if not isinstance(output, Mapping):
        return None
    observations = output.get("observations")
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
