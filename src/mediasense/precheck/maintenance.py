"""Conservative workspace audit, quarantine, and reachability cleanup."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from ._artifact_types import ArtifactAudit
from ._result_types import ResultAudit
from ._working_schema import SCHEMA_VERSION
from .artifact import ArtifactStore
from .result import ResultStore


_COLLECTIBLE_WORK_STATES = {"invalidated", "cancelled"}
_ACTIVE_ACCOUNTING_STATES = {"running", "paused", "blocked"}
_ACTIVE_PUBLIC_STATES = {"running", "paused", "blocked"}


@dataclass(frozen=True, slots=True)
class GarbageCandidate:
    kind: str
    identifier: str
    path: Path | None
    size_bytes: int
    reason: str


@dataclass(frozen=True, slots=True)
class MaintenanceAudit:
    artifacts: ArtifactAudit
    results: ResultAudit
    candidates: tuple[GarbageCandidate, ...]
    reclaimable_bytes: int


@dataclass(frozen=True, slots=True)
class MaintenanceReceipt:
    removed_work_ids: tuple[str, ...]
    removed_artifact_ids: tuple[str, ...]
    quarantined_paths: tuple[Path, ...]
    reclaimed_bytes: int
    failures: tuple[str, ...]


class WorkspaceMaintenance:
    """Collect only expired, unreferenced workspace-owned state."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.workspace = self.database_path.parent.absolute()
        self.quarantine_root = self.workspace / "_quarantine"
        self.artifacts = ArtifactStore(self.database_path)
        self.results = ResultStore(self.database_path)
        self._verify_schema()

    def audit(
        self,
        *,
        grace_period: timedelta = timedelta(days=1),
        now: datetime | None = None,
    ) -> MaintenanceAudit:
        if grace_period < timedelta(0):
            raise ValueError("grace_period cannot be negative")
        observed_at = _utc(now)
        cutoff = observed_at - grace_period
        artifact_audit = self.artifacts.audit()
        result_audit = self.results.audit()
        with self._connect() as connection:
            work_ids = _collectible_work_ids(connection, cutoff)
            artifact_rows = _collectible_artifacts(connection, work_ids)
        candidates: list[GarbageCandidate] = [
            GarbageCandidate(
                "work",
                work_id,
                None,
                0,
                "invalidated_or_cancelled_and_unreferenced",
            )
            for work_id in sorted(work_ids)
        ]
        candidates.extend(
            GarbageCandidate(
                "artifact",
                str(row["artifact_id"]),
                self.workspace / str(row["relative_path"]),
                int(row["size_bytes"]),
                "owned_only_by_collectible_work",
            )
            for row in artifact_rows
        )
        untracked = (("artifact_orphan", path) for path in artifact_audit.orphan_paths)
        unpublished = (
            ("unpublished", path)
            for path in artifact_audit.unpublished_paths
            + result_audit.unpublished_paths
        )
        result_orphans = (("result_orphan", path) for path in result_audit.orphan_paths)
        for kind, path in (*untracked, *unpublished, *result_orphans):
            if not _older_than(path, cutoff):
                continue
            candidates.append(
                GarbageCandidate(
                    kind,
                    path.relative_to(self.workspace).as_posix(),
                    path,
                    _file_size(path),
                    "untracked_workspace_file_past_grace_period",
                )
            )
        candidates.sort(key=lambda item: (item.kind, item.identifier))
        return MaintenanceAudit(
            artifacts=artifact_audit,
            results=result_audit,
            candidates=tuple(candidates),
            reclaimable_bytes=sum(item.size_bytes for item in candidates),
        )

    def collect(
        self,
        *,
        grace_period: timedelta = timedelta(days=1),
        now: datetime | None = None,
    ) -> MaintenanceReceipt:
        """Recheck reachability, delete stale rows, and quarantine bytes."""

        observed_at = _utc(now)
        audit = self.audit(grace_period=grace_period, now=observed_at)
        planned_work = {
            item.identifier for item in audit.candidates if item.kind == "work"
        }
        planned_artifacts = {
            item.identifier for item in audit.candidates if item.kind == "artifact"
        }
        removed_work: tuple[str, ...] = ()
        removed_artifacts: tuple[str, ...] = ()
        artifact_paths: dict[str, Path] = {}
        with self._transaction() as connection:
            eligible_work = (
                _collectible_work_ids(connection, observed_at - grace_period)
                & planned_work
            )
            artifact_rows = _collectible_artifacts(connection, eligible_work)
            eligible_artifacts = {
                str(row["artifact_id"]): row
                for row in artifact_rows
                if str(row["artifact_id"]) in planned_artifacts
            }
            artifact_paths = {
                artifact_id: self.workspace / str(row["relative_path"])
                for artifact_id, row in eligible_artifacts.items()
            }
            if eligible_work:
                placeholders = ",".join("?" for _ in eligible_work)
                parameters = tuple(sorted(eligible_work))
                for table in (
                    "work_attempts",
                    "work_dependencies",
                    "run_work_records",
                    "work_artifacts",
                ):
                    connection.execute(
                        f"DELETE FROM {table} WHERE work_id IN ({placeholders})",  # noqa: S608
                        parameters,
                    )
                connection.execute(
                    f"DELETE FROM work_records WHERE work_id IN ({placeholders})",  # noqa: S608
                    parameters,
                )
                removed_work = parameters
            if eligible_artifacts:
                placeholders = ",".join("?" for _ in eligible_artifacts)
                parameters = tuple(sorted(eligible_artifacts))
                connection.execute(
                    f"DELETE FROM artifacts WHERE artifact_id IN ({placeholders})",  # noqa: S608
                    parameters,
                )
                removed_artifacts = parameters

        quarantine_candidates = [
            item.path
            for item in audit.candidates
            if item.path is not None
            and (item.kind != "artifact" or item.identifier in removed_artifacts)
        ]
        quarantined: list[Path] = []
        failures: list[str] = []
        reclaimed_bytes = 0
        for path in dict.fromkeys((*artifact_paths.values(), *quarantine_candidates)):
            if not path.exists() and not path.is_symlink():
                continue
            try:
                size = _file_size(path)
                quarantined.append(self._quarantine(path, observed_at))
                reclaimed_bytes += size
            except OSError as error:
                failures.append(f"{path}: {error}")
        return MaintenanceReceipt(
            removed_work_ids=removed_work,
            removed_artifact_ids=removed_artifacts,
            quarantined_paths=tuple(quarantined),
            reclaimed_bytes=reclaimed_bytes,
            failures=tuple(failures),
        )

    def restore_artifact(self, artifact_id: str) -> Path:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT relative_path, digest, size_bytes FROM artifacts WHERE artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown Artifact: {artifact_id}")
        return self._restore(
            Path(str(row["relative_path"])),
            str(row["digest"]),
            int(row["size_bytes"]),
        )

    def restore_result(self, result_ref: str) -> Path:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT relative_path, digest, size_bytes FROM sealed_results WHERE result_ref = ?",
                (result_ref,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown Result: {result_ref}")
        return self._restore(
            Path(str(row["relative_path"])),
            str(row["digest"]),
            int(row["size_bytes"]),
        )

    def _quarantine(self, path: Path, observed_at: datetime) -> Path:
        relative = path.absolute().relative_to(self.workspace)
        destination = (
            self.quarantine_root / observed_at.strftime("%Y%m%dT%H%M%S.%fZ") / relative
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            destination = destination.with_name(f"{destination.name}.{uuid4().hex}")
        os.replace(path, destination)
        return destination

    def _restore(self, relative_path: Path, digest: str, size_bytes: int) -> Path:
        destination = self.workspace / relative_path
        candidates = tuple(
            path
            for path in self.quarantine_root.glob(f"*/{relative_path.as_posix()}")
            if path.is_file()
        )
        source = next(
            (
                path
                for path in sorted(candidates, reverse=True)
                if _digest(path) == (digest, size_bytes)
            ),
            None,
        )
        if source is None:
            raise FileNotFoundError("no integrity-matching quarantined bytes exist")
        if destination.exists() or destination.is_symlink():
            self._quarantine(destination, _utc(None))
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(source, destination)
        destination.chmod(0o444)
        return destination

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT version FROM internal_schema WHERE singleton = 1"
            ).fetchone()
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported or uninitialized internal schema")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()


def _collectible_work_ids(connection: sqlite3.Connection, cutoff: datetime) -> set[str]:
    rows = connection.execute(
        """
        SELECT work_id FROM work_records
        WHERE status IN ('invalidated', 'cancelled') AND updated_at <= ?
          AND NOT EXISTS (
              SELECT 1 FROM result_work_records
              WHERE result_work_records.work_id = work_records.work_id
          )
          AND NOT EXISTS (
              SELECT 1 FROM run_work_records
              JOIN working_runs USING (run_id)
              WHERE run_work_records.work_id = work_records.work_id
                AND working_runs.status IN ('running', 'paused', 'blocked')
          )
          AND NOT EXISTS (
              SELECT 1 FROM run_work_records
              JOIN precheck_runs ON precheck_runs.accounting_run_id = run_work_records.run_id
              WHERE run_work_records.work_id = work_records.work_id
                AND precheck_runs.state IN ('running', 'paused', 'blocked')
          )
        """,
        (cutoff.isoformat(timespec="microseconds"),),
    ).fetchall()
    candidates = {str(row["work_id"]) for row in rows}
    dependencies = connection.execute(
        """
        SELECT dependency_key AS upstream_work_id, work_id AS dependent_work_id
        FROM work_dependencies
        WHERE dependency_kind = 'upstream_work'
        """
    ).fetchall()
    changed = True
    while changed:
        changed = False
        for row in dependencies:
            upstream = str(row["upstream_work_id"])
            dependent = str(row["dependent_work_id"])
            if upstream in candidates and dependent not in candidates:
                candidates.remove(upstream)
                changed = True
    return candidates


def _collectible_artifacts(
    connection: sqlite3.Connection, collectible_work_ids: set[str]
) -> tuple[sqlite3.Row, ...]:
    rows = connection.execute("SELECT * FROM artifacts ORDER BY artifact_id").fetchall()
    selected = []
    for row in rows:
        artifact_id = str(row["artifact_id"])
        if connection.execute(
            "SELECT 1 FROM result_artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone():
            continue
        owners = {
            str(owner["work_id"])
            for owner in connection.execute(
                "SELECT work_id FROM work_artifacts WHERE artifact_id = ?",
                (artifact_id,),
            )
        }
        if owners and owners <= collectible_work_ids:
            selected.append(row)
    return tuple(selected)


def _older_than(path: Path, cutoff: datetime) -> bool:
    try:
        modified = datetime.fromtimestamp(path.lstat().st_mtime, timezone.utc)
    except OSError:
        return False
    return modified <= cutoff


def _file_size(path: Path) -> int:
    try:
        return path.lstat().st_size
    except OSError:
        return 0


def _digest(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _utc(value: datetime | None) -> datetime:
    observed = value or datetime.now(timezone.utc)
    if observed.tzinfo is None:
        raise ValueError("maintenance time must be timezone-aware")
    return observed.astimezone(timezone.utc)


__all__ = [
    "GarbageCandidate",
    "MaintenanceAudit",
    "MaintenanceReceipt",
    "WorkspaceMaintenance",
]
