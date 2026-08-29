"""Private Artifact filesystem and SQLite publication adapter."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
from uuid import uuid4

from ._artifact_types import (
    ArtifactAudit,
    ArtifactDraft,
    ArtifactIntegrity,
    ArtifactIntegrityError,
    ArtifactRecord,
    InvalidArtifactDraft,
)
from ._fingerprint import SourceChangedDuringRead, stat_identity
from ._invalidation import invalidate_work_tree
from .source_validity import SourceValidityStore
from ._work_sqlite import SQLiteWorkStore, _as_datetime, _output_json, _utc
from ._work_types import (
    AttemptOutcome,
    DependencyKind,
    WorkLease,
    WorkRecord,
    WorkStatus,
)


_DIGEST_ALGORITHM = "sha256"
_ARTIFACT_ID_PREFIX = "artifact:sha256:"
_SAFE_SUFFIX = re.compile(r"\.[a-z0-9]{1,10}")


class SQLiteArtifactStore(SQLiteWorkStore):
    """Publish immutable bytes and bind them to successful Work atomically."""

    def __init__(self, database_path: Path) -> None:
        super().__init__(database_path)
        self.workspace = self.database_path.parent.absolute()
        self.artifact_root = self.workspace / "_artifacts"
        self.unpublished_root = self.artifact_root / "unpublished"
        self.published_root = self.artifact_root / "sha256"

    def create_draft(self, lease: WorkLease, *, suffix: str) -> ArtifactDraft:
        normalized_suffix = _validated_suffix(suffix)
        with self._transaction(immediate=True) as connection:
            self._recover_expired(connection, _utc(None))
            self._require_lease(connection, lease)
        self.unpublished_root.mkdir(parents=True, exist_ok=True)
        path = self.unpublished_root / (
            f"{lease.work_id}-{lease.token}-{uuid4().hex}{normalized_suffix}.part"
        )
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        return ArtifactDraft(
            work_id=lease.work_id,
            lease_token=lease.token,
            path=path,
        )

    def publish(
        self,
        lease: WorkLease,
        draft: ArtifactDraft,
        *,
        suffix: str,
        media_type: str,
        role: str,
        output: object | None = None,
        now: datetime | None = None,
    ) -> tuple[WorkRecord, ArtifactRecord]:
        if draft.work_id != lease.work_id or draft.lease_token != lease.token:
            raise InvalidArtifactDraft("draft does not belong to the active Work lease")
        if not media_type.strip() or not role.strip():
            raise ValueError("Artifact media_type and role must be non-empty")
        self._verify_exact_source_dependencies(lease)
        normalized_suffix = _validated_suffix(suffix)
        draft_path = draft.path.absolute()
        if draft_path.parent != self.unpublished_root.absolute():
            raise InvalidArtifactDraft("draft is outside the unpublished workspace")
        staging_path = self.unpublished_root / f"{uuid4().hex}.publishing"
        try:
            digest, size_bytes = _copy_stable_regular_file(draft_path, staging_path)
        except FileNotFoundError as error:
            raise InvalidArtifactDraft("draft bytes are missing") from error
        if size_bytes == 0:
            staging_path.unlink(missing_ok=True)
            raise InvalidArtifactDraft("empty Artifact drafts cannot be published")
        draft_path.unlink()
        artifact_id = f"{_ARTIFACT_ID_PREFIX}{digest}"
        final_dir = self.published_root / digest[:2]
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = final_dir / f"{digest}{normalized_suffix}"
        if final_path.exists():
            existing_digest, existing_size = _digest_file(final_path)
            if existing_digest == digest and existing_size == size_bytes:
                staging_path.unlink()
            else:
                os.replace(staging_path, final_path)
        else:
            os.replace(staging_path, final_path)
        final_path.chmod(0o444)
        _fsync_file_and_directory(final_path)
        self._after_file_published(final_path)
        final_digest, final_size = _digest_file(final_path)
        if final_digest != digest or final_size != size_bytes:
            raise ArtifactIntegrityError(
                "published Artifact bytes changed before Work binding"
            )

        timestamp = _utc(now)
        relative_path = final_path.relative_to(self.workspace).as_posix()
        artifact_output = {
            "artifacts": [{"artifact_ref": artifact_id, "role": role.strip()}],
            "value": output,
        }
        output_json = _output_json(artifact_output)
        output_digest = (
            "inline-json-sha256-v1:"
            + hashlib.sha256(output_json.encode("utf-8")).hexdigest()
        )
        with self._transaction(immediate=True) as connection:
            self._recover_expired(connection, timestamp)
            self._require_lease(connection, lease)
            existing = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            if existing is not None and (
                str(existing["digest_algorithm"]) != _DIGEST_ALGORITHM
                or str(existing["digest"]) != digest
                or int(existing["size_bytes"]) != size_bytes
                or str(existing["relative_path"]) != relative_path
            ):
                raise ArtifactIntegrityError(
                    f"Artifact identity collision: {artifact_id}"
                )
            connection.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, digest_algorithm, digest, size_bytes,
                    media_type, relative_path, integrity_status,
                    last_verified_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (artifact_id) DO UPDATE SET
                    integrity_status = excluded.integrity_status,
                    last_verified_at = excluded.last_verified_at
                """,
                (
                    artifact_id,
                    _DIGEST_ALGORITHM,
                    digest,
                    size_bytes,
                    media_type.strip(),
                    relative_path,
                    ArtifactIntegrity.AVAILABLE,
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                """
                INSERT INTO work_artifacts (work_id, role, position, artifact_id)
                VALUES (?, ?, 0, ?)
                """,
                (lease.work_id, role.strip(), artifact_id),
            )
            connection.execute(
                """
                UPDATE work_attempts
                SET finished_at = ?, outcome = ?, retryable = 0
                WHERE work_id = ? AND attempt_number = ?
                """,
                (
                    timestamp,
                    AttemptOutcome.SUCCEEDED,
                    lease.work_id,
                    lease.attempt_number,
                ),
            )
            connection.execute(
                """
                UPDATE work_records
                SET status = ?, lease_run_id = NULL, lease_owner = NULL,
                    lease_token = NULL, lease_expires_at = NULL,
                    retry_not_before = NULL, last_failure_code = NULL,
                    last_failure_message = NULL, output_json = ?,
                    output_digest = ?, succeeded_at = ?, updated_at = ?
                WHERE work_id = ?
                """,
                (
                    WorkStatus.SUCCEEDED,
                    output_json,
                    output_digest,
                    timestamp,
                    timestamp,
                    lease.work_id,
                ),
            )
            self._promote_dependents(connection, lease.work_id, timestamp)
            work = self._get_work(connection, lease.work_id)
            artifact = self._artifact_from_row(
                connection.execute(
                    "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
                ).fetchone()
            )
        return work, artifact

    def artifacts_for_work(
        self,
        work_id: str,
        *,
        verify: bool = True,
    ) -> tuple[ArtifactRecord, ...]:
        with self._connect() as connection:
            self._get_work(connection, work_id)
            rows = connection.execute(
                """
                SELECT artifacts.* FROM work_artifacts
                JOIN artifacts USING (artifact_id)
                WHERE work_artifacts.work_id = ?
                ORDER BY work_artifacts.role, work_artifacts.position
                """,
                (work_id,),
            ).fetchall()
        records = tuple(self._artifact_from_row(row) for row in rows)
        if verify:
            return tuple(self.verify(record.artifact_id) for record in records)
        return records

    def verify(self, artifact_id: str) -> ArtifactRecord:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown Artifact: {artifact_id}")
        path = self.workspace / str(row["relative_path"])
        integrity = ArtifactIntegrity.AVAILABLE
        try:
            digest, size_bytes = _digest_file(path)
        except (FileNotFoundError, OSError):
            integrity = ArtifactIntegrity.MISSING
        else:
            if digest != row["digest"] or size_bytes != int(row["size_bytes"]):
                integrity = ArtifactIntegrity.CORRUPT
        timestamp = _utc(None)
        with self._transaction(immediate=True) as connection:
            connection.execute(
                """
                UPDATE artifacts
                SET integrity_status = ?, last_verified_at = ?
                WHERE artifact_id = ?
                """,
                (integrity, timestamp, artifact_id),
            )
            if integrity is not ArtifactIntegrity.AVAILABLE:
                roots = {
                    str(work["work_id"]): f"artifact_{integrity}:{artifact_id}"
                    for work in connection.execute(
                        "SELECT work_id FROM work_artifacts WHERE artifact_id = ?",
                        (artifact_id,),
                    )
                }
                invalidate_work_tree(connection, roots, observed_at=timestamp)
            updated = connection.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
        return self._artifact_from_row(updated)

    def require_available(self, artifact_id: str) -> ArtifactRecord:
        artifact = self.verify(artifact_id)
        if artifact.integrity is not ArtifactIntegrity.AVAILABLE:
            raise ArtifactIntegrityError(
                f"Artifact {artifact_id} is {artifact.integrity}"
            )
        return artifact

    def audit(self) -> ArtifactAudit:
        with self._connect() as connection:
            artifact_ids = tuple(
                str(row["artifact_id"])
                for row in connection.execute(
                    "SELECT artifact_id FROM artifacts ORDER BY artifact_id"
                )
            )
            referenced_paths = {
                str(row["relative_path"])
                for row in connection.execute("SELECT relative_path FROM artifacts")
            }
        records = tuple(self.verify(artifact_id) for artifact_id in artifact_ids)
        published_paths = (
            tuple(path for path in self.published_root.rglob("*") if path.is_file())
            if self.published_root.exists()
            else ()
        )
        orphan_paths = tuple(
            sorted(
                path
                for path in published_paths
                if path.relative_to(self.workspace).as_posix() not in referenced_paths
            )
        )
        unpublished_paths = (
            tuple(
                sorted(
                    path for path in self.unpublished_root.iterdir() if path.is_file()
                )
            )
            if self.unpublished_root.exists()
            else ()
        )
        return ArtifactAudit(
            available=tuple(
                record.artifact_id
                for record in records
                if record.integrity is ArtifactIntegrity.AVAILABLE
            ),
            missing=tuple(
                record.artifact_id
                for record in records
                if record.integrity is ArtifactIntegrity.MISSING
            ),
            corrupt=tuple(
                record.artifact_id
                for record in records
                if record.integrity is ArtifactIntegrity.CORRUPT
            ),
            orphan_paths=orphan_paths,
            unpublished_paths=unpublished_paths,
        )

    def _artifact_from_row(self, row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=str(row["artifact_id"]),
            digest_algorithm=str(row["digest_algorithm"]),
            digest=str(row["digest"]),
            size_bytes=int(row["size_bytes"]),
            media_type=str(row["media_type"]),
            path=self.workspace / str(row["relative_path"]),
            integrity=ArtifactIntegrity(row["integrity_status"]),
            created_at=_as_datetime(str(row["created_at"])),
        )

    def _verify_exact_source_dependencies(self, lease: WorkLease) -> None:
        with self._connect() as connection:
            self._require_lease(connection, lease)
            dependencies = connection.execute(
                """
                SELECT dependency_key, dependency_value
                FROM work_dependencies
                WHERE work_id = ? AND dependency_kind = ?
                ORDER BY dependency_key
                """,
                (lease.work_id, DependencyKind.SOURCE_CONTENT),
            ).fetchall()
        if not dependencies:
            raise InvalidArtifactDraft(
                "Artifact-producing Work requires an exact source content dependency"
            )
        validity = SourceValidityStore(self.database_path)
        for dependency in dependencies:
            try:
                _dataset_id, relative_path = json.loads(dependency["dependency_key"])
            except (TypeError, ValueError) as error:
                raise InvalidArtifactDraft(
                    "Artifact Work has an invalid source content dependency"
                ) from error
            try:
                observed = validity.prove(
                    lease.run_id, Path(relative_path)
                ).dependency()
            except SourceChangedDuringRead as error:
                self.invalidate_work(
                    lease.work_id,
                    f"source changed before Artifact publication:{relative_path}",
                )
                raise InvalidArtifactDraft(str(error)) from error
            if observed.value != dependency["dependency_value"]:
                raise InvalidArtifactDraft(
                    f"source content changed before Artifact publication: {relative_path}"
                )

    def _after_file_published(self, path: Path) -> None:
        """Fault-injection seam after atomic bytes publication, before DB commit."""


def _validated_suffix(value: str) -> str:
    suffix = value.casefold()
    if _SAFE_SUFFIX.fullmatch(suffix) is None:
        raise ValueError("Artifact suffix must be a short lowercase file extension")
    return suffix


def _digest_file(path: Path) -> tuple[str, int]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError(f"Artifact is not a regular file: {path}")
        digest = hashlib.sha256()
        size_bytes = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size_bytes += len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if stat_identity(before) != stat_identity(after):
        raise OSError(f"Artifact changed while reading: {path}")
    return digest.hexdigest(), size_bytes


def _copy_stable_regular_file(
    source_path: Path, destination_path: Path
) -> tuple[str, int]:
    """Copy producer-owned bytes onto a publication-owned inode."""

    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    source = os.open(source_path, flags)
    try:
        before = os.fstat(source)
        if not stat.S_ISREG(before.st_mode):
            raise InvalidArtifactDraft("draft must be a regular non-symlink file")
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with destination_path.open("xb") as destination:
                while chunk := os.read(source, 1024 * 1024):
                    destination.write(chunk)
                    digest.update(chunk)
                    size_bytes += len(chunk)
                destination.flush()
                os.fsync(destination.fileno())
        except BaseException:
            destination_path.unlink(missing_ok=True)
            raise
        after = os.fstat(source)
        os.lseek(source, 0, os.SEEK_SET)
        confirmed = hashlib.sha256()
        confirmed_size = 0
        while chunk := os.read(source, 1024 * 1024):
            confirmed.update(chunk)
            confirmed_size += len(chunk)
        confirmed_stat = os.fstat(source)
    finally:
        os.close(source)
    if (
        stat_identity(before) != stat_identity(after)
        or stat_identity(after) != stat_identity(confirmed_stat)
        or confirmed.hexdigest() != digest.hexdigest()
        or confirmed_size != size_bytes
    ):
        destination_path.unlink(missing_ok=True)
        raise InvalidArtifactDraft("draft changed while being closed for publication")
    return digest.hexdigest(), size_bytes


def _fsync_file_and_directory(path: Path) -> None:
    with path.open("rb") as stream:
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
