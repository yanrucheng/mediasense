"""Revision-bound ordinary-change observations for source-derived Work."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import stat
from typing import Iterator

from ._accounting_types import WorkingRunStatus
from ._fingerprint import SourceChangedDuringRead, stat_identity
from ._invalidation import invalidate_source_dependencies
from ._sqlite_scope import connect
from ._working_schema import SCHEMA_VERSION
from ._work_types import WorkDependency, source_content_dependency
from .discovery import SourceCondition


@dataclass(frozen=True, slots=True)
class SourceContentProof:
    dataset_id: str
    relative_path: Path
    source_revision: int
    reuse_domain: str
    algorithm: str
    digest: str
    size_bytes: int
    observed_at: datetime
    source_path: Path

    def dependency(self) -> WorkDependency:
        return source_content_dependency(
            self.dataset_id,
            self.relative_path,
            reuse_domain=self.reuse_domain,
            algorithm=self.algorithm,
            digest=self.digest,
            size_bytes=self.size_bytes,
        )


class SourceValidityStore:
    """Persist reusable source observations without creating source identity."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self._verify_schema()

    def prove(self, run_id: str, relative_path: Path) -> SourceContentProof:
        return self.prove_many(run_id, (relative_path,))[0]

    def prove_many(self, run_id: str, relative_paths) -> tuple[SourceContentProof, ...]:
        """Observe at most 128 occurrences, then commit their proofs together."""
        from itertools import islice

        paths = tuple(_validated_relative_path(p) for p in islice(relative_paths, 129))
        if len(paths) > 128:
            raise ValueError("source proof batch exceeds 128 occurrences")
        if not paths:
            return ()
        with self._connect() as connection:
            rows = self._source_rows(connection, run_id, paths)
        proofs = tuple(self._observe(rows.get(path.as_posix()), path) for path in paths)
        with self._transaction() as connection:
            current = self._source_rows(connection, run_id, paths)
            for path, proof in zip(paths, proofs, strict=True):
                row = current.get(path.as_posix())
                if row is None or dict(row) != dict(rows[path.as_posix()]):
                    raise SourceChangedDuringRead(
                        f"source accounting changed while proving: {path}"
                    )
                # Recheck this occurrence's stat at the commit boundary. A batch
                # must not stretch an earlier observation into authorization.
                self._observe(row, path)
                self._record_proof(connection, proof)
        return proofs

    def _source_rows(self, connection, run_id, paths):
        names = tuple(dict.fromkeys(path.as_posix() for path in paths))
        rows = connection.execute(
            f"""
            SELECT run_items.relative_path, working_runs.dataset_id,
                   working_runs.source_root, working_runs.reuse_domain,
                   working_runs.status, run_items.source_revision,
                   run_items.condition, run_items.size_bytes, run_items.mtime_ns,
                   run_items.device_id, run_items.inode, run_items.mode,
                   run_items.fingerprint_algorithm, run_items.fingerprint
            FROM working_runs JOIN run_items USING (run_id)
            WHERE working_runs.run_id = ?
              AND run_items.relative_path IN ({','.join('?' for _ in names)})
            """, (run_id, *names),
        ).fetchall()
        return {row["relative_path"]: row for row in rows}

    def _observe(self, row, relative):
        if row is None:
            raise KeyError(f"source is not accounted by Working Run: {relative}")
        if WorkingRunStatus(row["status"]) not in {
            WorkingRunStatus.COMPLETED,
            WorkingRunStatus.COMPLETED_WITH_ISSUES,
        }:
            raise ValueError("source accounting must be complete before observation")
        if row["source_revision"] is None:
            raise ValueError(f"source has no reusable revision: {relative}")
        if SourceCondition(row["condition"]) not in {
            SourceCondition.USABLE,
            SourceCondition.UNRESOLVED,
        }:
            raise ValueError(f"source is not usable: {relative}")

        source_root = Path(str(row["source_root"]))
        source_path = source_root / relative
        expected_identity = (
            int(row["size_bytes"]),
            int(row["mtime_ns"]),
            int(row["device_id"]),
            int(row["inode"]),
            int(row["mode"]),
        )
        observed = source_path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(observed.st_mode)
            or stat_identity(observed) != expected_identity
        ):
            raise SourceChangedDuringRead(
                f"source changed after accounting: {source_path}"
            )
        algorithm = row["fingerprint_algorithm"]
        digest = row["fingerprint"]
        if not isinstance(algorithm, str) or not algorithm:
            raise ValueError(f"source has no candidate fingerprint profile: {relative}")
        if not isinstance(digest, str) or not digest:
            raise ValueError(f"source has no candidate fingerprint value: {relative}")
        observed_at = datetime.now(timezone.utc)
        proof = SourceContentProof(
            dataset_id=str(row["dataset_id"]),
            relative_path=relative,
            source_revision=int(row["source_revision"]),
            reuse_domain=str(row["reuse_domain"]),
            algorithm=algorithm,
            digest=digest,
            size_bytes=observed.st_size,
            observed_at=observed_at,
            source_path=source_path,
        )
        return proof

    def verify(self, run_id: str, expected: SourceContentProof) -> SourceContentProof:
        observed = self.prove(run_id, expected.relative_path)
        if observed.dependency().value != expected.dependency().value:
            raise SourceChangedDuringRead(
                f"source changed during read: {expected.relative_path}"
            )
        return observed

    def _record_proof(self, connection, proof: SourceContentProof) -> None:
        dependency = proof.dependency()
        timestamp = proof.observed_at.isoformat(timespec="microseconds")
        previous = connection.execute(
            """
            SELECT proof_value FROM source_content_proofs
            WHERE dataset_id = ? AND relative_path = ? AND reuse_domain = ?
            """,
            (
                proof.dataset_id,
                proof.relative_path.as_posix(),
                proof.reuse_domain,
            ),
        ).fetchone()
        if previous is not None and previous["proof_value"] != dependency.value:
            invalidate_source_dependencies(
                connection,
                proof.dataset_id,
                {proof.relative_path.as_posix()},
                reason="exact_source_content_changed",
                observed_at=timestamp,
            )
        connection.execute(
            """
            INSERT INTO source_content_proofs (
                dataset_id, relative_path, reuse_domain, source_revision,
                algorithm, digest, size_bytes, proof_value, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (dataset_id, relative_path, reuse_domain) DO UPDATE SET
                source_revision = excluded.source_revision,
                algorithm = excluded.algorithm,
                digest = excluded.digest,
                size_bytes = excluded.size_bytes,
                proof_value = excluded.proof_value,
                observed_at = excluded.observed_at
            """,
            (
                proof.dataset_id,
                proof.relative_path.as_posix(),
                proof.reuse_domain,
                proof.source_revision,
                proof.algorithm,
                proof.digest,
                proof.size_bytes,
                dependency.value,
                timestamp,
            ),
        )

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
            except sqlite3.OperationalError as error:
                raise RuntimeError(
                    "initialize the PreCheck working store before source validation"
                ) from error
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported or uninitialized internal schema")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with connect(self.database_path) as connection:
            yield connection

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


def _validated_relative_path(value: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError("source path must stay relative to its root")
    return path


__all__ = ["SourceContentProof", "SourceValidityStore"]
