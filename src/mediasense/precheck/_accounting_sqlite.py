"""SQLite persistence adapter scoped to PreCheck discovery accounting."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import unicodedata

from mediasense.dataset_reference import dataset_ref_from_id

from ._working_schema import SCHEMA, SCHEMA_VERSION
from ._accounting_types import (
    AccountedItem,
    ChangeKind,
    RecordedIssue,
    RemovedSource,
    WorkingRunStatus,
    WorkingRunSummary,
)
from ._fingerprint import CandidateFingerprint, fingerprint_stat_identity
from ._invalidation import invalidate_source_dependencies
from .discovery import (
    DiscoveredSource,
    DiscoveryEvent,
    DiscoveryIssue,
    DiscoveryIssueCode,
    SourceCondition,
)
from .source_attachment import (
    FilesystemCapabilities,
    SourceAttachment,
    SourceAttachmentProbe,
    SourceRebinding,
)


DISCOVERY_PRODUCER = "builtin-source-classification-v1"


class SQLiteAccounting:
    """Private persistence operations for the Slice 1 accounting lifecycle."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            version = connection.execute(
                "SELECT version FROM internal_schema WHERE singleton = 1"
            ).fetchone()[0]
            if version not in {11, 12, 13, 14, SCHEMA_VERSION}:
                raise RuntimeError(f"unsupported internal schema version: {version}")
            columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(run_items)")
            }
            if "normalized_path" not in columns:
                if version == SCHEMA_VERSION:
                    raise RuntimeError(
                        "current internal schema is missing normalized_path"
                    )
                connection.execute(
                    "ALTER TABLE run_items "
                    "ADD COLUMN normalized_path TEXT NOT NULL DEFAULT ''"
                )
                rows = connection.execute(
                    "SELECT rowid, relative_path FROM run_items"
                ).fetchall()
                connection.executemany(
                    "UPDATE run_items SET normalized_path = ? WHERE rowid = ?",
                    (
                        (_normalized_path(str(row["relative_path"])), int(row["rowid"]))
                        for row in rows
                    ),
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS run_items_normalized_path "
                "ON run_items(run_id, normalized_path, last_seen_generation)"
            )
            run_columns = {
                str(row["name"])
                for row in connection.execute("PRAGMA table_info(precheck_runs)")
            }
            for column in ("execution_config_json", "execution_checkpoint"):
                if column not in run_columns:
                    if version == SCHEMA_VERSION:
                        raise RuntimeError(
                            f"current internal schema is missing {column}"
                        )
                    connection.execute(
                        f"ALTER TABLE precheck_runs ADD COLUMN {column} TEXT"
                    )
            if version in {11, 12, 13, 14}:
                connection.execute(
                    "UPDATE internal_schema SET version = ? WHERE singleton = 1",
                    (SCHEMA_VERSION,),
                )
                version = SCHEMA_VERSION

    def register_dataset(self, dataset_id: str) -> None:
        now = _now()
        # The first DatasetRuntime release accidentally stored the public
        # reference here. Affected rows have no normal downstream records because
        # PreCheck rejected start before creating them. Preserve any unexpected
        # referenced row, but remove the known orphan after registering its
        # canonical internal identity.
        legacy_dataset_id = dataset_ref_from_id(dataset_id)
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT dataset_id, created_at, updated_at "
                "FROM datasets WHERE dataset_id = ?",
                (dataset_id,),
            ).fetchone()
            legacy = connection.execute(
                "SELECT created_at, updated_at FROM datasets WHERE dataset_id = ?",
                (legacy_dataset_id,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO datasets (dataset_id, created_at, updated_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        dataset_id,
                        now if legacy is None else str(legacy["created_at"]),
                        now if legacy is None else str(legacy["updated_at"]),
                    ),
                )
            if legacy is not None:
                connection.execute(
                    """
                    DELETE FROM datasets
                    WHERE dataset_id = ?
                      AND NOT EXISTS (
                          SELECT 1 FROM working_runs WHERE dataset_id = ?
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM source_state WHERE dataset_id = ?
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM source_content_proofs WHERE dataset_id = ?
                      )
                      AND NOT EXISTS (
                          SELECT 1 FROM sealed_results WHERE dataset_id = ?
                      )
                    """,
                    (legacy_dataset_id,) * 5,
                )

    def dataset(self, dataset_id: str) -> sqlite3.Row:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT dataset_id FROM datasets WHERE dataset_id = ?",
                (dataset_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown dataset: {dataset_id}")
        return row

    def unfinished_run(self, dataset_id: str) -> str | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT run_id
                FROM working_runs
                WHERE dataset_id = ? AND status IN ('running', 'paused', 'blocked')
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (dataset_id,),
            ).fetchone()
        return None if row is None else str(row["run_id"])

    def latest_attachment(self, dataset_id: str) -> SourceAttachment | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM working_runs
                WHERE dataset_id = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (dataset_id,),
            ).fetchone()
        return None if row is None else _attachment_from_row(row)

    def create_run(
        self,
        run_id: str,
        dataset_id: str,
        attachment: SourceAttachment,
        *,
        previous_attachment: SourceAttachment | None = None,
        continuity: str | None = None,
    ) -> None:
        now = _now()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO working_runs (
                    run_id, dataset_id, source_root, expected_volume_identity,
                    expected_root_identity, identity_strength, reuse_domain,
                    filesystem_capabilities_json, binding_reason, status,
                    started_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    dataset_id,
                    str(attachment.source_root),
                    attachment.volume_identity,
                    attachment.root_identity,
                    attachment.identity_strength,
                    attachment.reuse_domain,
                    attachment.capabilities.to_json(),
                    attachment.binding_reason,
                    WorkingRunStatus.RUNNING,
                    now,
                    now,
                ),
            )
            if previous_attachment is not None:
                if continuity is None:
                    raise ValueError("continuity is required for a rebinding audit")
                connection.execute(
                    """
                    INSERT INTO run_source_rebindings (
                        run_id, sequence, previous_source_root,
                        previous_volume_identity, previous_root_identity,
                        source_root, volume_identity, root_identity,
                        identity_strength, reuse_domain, reason, continuity,
                        capabilities_json, observed_at
                    ) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        str(previous_attachment.source_root),
                        previous_attachment.volume_identity,
                        previous_attachment.root_identity,
                        str(attachment.source_root),
                        attachment.volume_identity,
                        attachment.root_identity,
                        attachment.identity_strength,
                        attachment.reuse_domain,
                        attachment.binding_reason,
                        continuity,
                        attachment.capabilities.to_json(),
                        now,
                    ),
                )

    def active_attachment(self, run_id: str) -> SourceAttachment:
        return _attachment_from_row(self.load_run(run_id))

    def rebind_run(
        self,
        run_id: str,
        attachment: SourceAttachmentProbe,
        *,
        reuse_domain: str,
        reason: str,
        continuity: str,
    ) -> None:
        now = _now()
        with self.connect() as connection:
            previous = connection.execute(
                "SELECT * FROM working_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if previous is None:
                raise KeyError(f"unknown working run: {run_id}")
            sequence = int(
                connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence), 0) + 1
                    FROM run_source_rebindings
                    WHERE run_id = ?
                    """,
                    (run_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO run_source_rebindings (
                    run_id, sequence, previous_source_root,
                    previous_volume_identity, previous_root_identity,
                    source_root, volume_identity, root_identity, identity_strength,
                    reuse_domain, reason, continuity, capabilities_json, observed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    sequence,
                    previous["source_root"],
                    previous["expected_volume_identity"],
                    previous["expected_root_identity"],
                    str(attachment.source_root),
                    attachment.volume_identity,
                    attachment.root_identity,
                    attachment.identity_strength,
                    reuse_domain,
                    reason,
                    continuity,
                    attachment.capabilities.to_json(),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE working_runs
                SET source_root = ?, expected_volume_identity = ?,
                    expected_root_identity = ?, identity_strength = ?,
                    reuse_domain = ?, filesystem_capabilities_json = ?,
                    binding_reason = ?, blocked_reason = NULL,
                    status = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (
                    str(attachment.source_root),
                    attachment.volume_identity,
                    attachment.root_identity,
                    attachment.identity_strength,
                    reuse_domain,
                    attachment.capabilities.to_json(),
                    reason,
                    WorkingRunStatus.PAUSED,
                    now,
                    run_id,
                ),
            )

    def get_rebindings(self, run_id: str) -> tuple[SourceRebinding, ...]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, previous_source_root, previous_volume_identity,
                       previous_root_identity, source_root, volume_identity,
                       root_identity, identity_strength, reason, continuity,
                       reuse_domain, capabilities_json
                FROM run_source_rebindings
                WHERE run_id = ?
                ORDER BY sequence
                """,
                (run_id,),
            ).fetchall()
        return tuple(
            SourceRebinding(
                sequence=int(row["sequence"]),
                previous_source_root=Path(row["previous_source_root"]),
                previous_volume_identity=row["previous_volume_identity"],
                previous_root_identity=row["previous_root_identity"],
                source_root=Path(row["source_root"]),
                volume_identity=row["volume_identity"],
                root_identity=row["root_identity"],
                identity_strength=str(row["identity_strength"]),
                reason=str(row["reason"]),
                continuity=str(row["continuity"]),
                reuse_domain=str(row["reuse_domain"]),
                capabilities=FilesystemCapabilities.from_json(
                    str(row["capabilities_json"])
                ),
            )
            for row in rows
        )

    def load_run(self, run_id: str) -> sqlite3.Row:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM working_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown working run: {run_id}")
        return row

    def prepare_run(self, run_id: str, attachment: SourceAttachmentProbe) -> int:
        now = _now()
        with self.connect() as connection:
            connection.execute(
                """
                DELETE FROM run_issues
                WHERE run_id = ? AND relative_path = '.' AND code = ?
                """,
                (run_id, DiscoveryIssueCode.ROOT_UNAVAILABLE),
            )
            connection.execute(
                """
                UPDATE working_runs
                SET expected_volume_identity = COALESCE(expected_volume_identity, ?),
                    expected_root_identity = COALESCE(expected_root_identity, ?),
                    identity_strength = ?, filesystem_capabilities_json = ?,
                    status = ?, blocked_reason = NULL,
                    scan_generation = scan_generation + 1,
                    checkpoint = NULL, updated_at = ?
                WHERE run_id = ?
                """,
                (
                    attachment.volume_identity,
                    attachment.root_identity,
                    attachment.identity_strength,
                    attachment.capabilities.to_json(),
                    WorkingRunStatus.RUNNING,
                    now,
                    run_id,
                ),
            )
            return int(
                connection.execute(
                    "SELECT scan_generation FROM working_runs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )

    def event_is_committed(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        scan_generation: int,
        event: DiscoveryEvent,
    ) -> bool:
        if isinstance(event, DiscoveryIssue):
            row = connection.execute(
                """
                SELECT message, blocked, basis_json, last_seen_generation
                FROM run_issues
                WHERE run_id = ? AND relative_path = ? AND code = ?
                """,
                (run_id, event.relative_path.as_posix(), event.code),
            ).fetchone()
            return (
                row is not None
                and row["last_seen_generation"] == scan_generation
                and (
                    row["message"],
                    bool(row["blocked"]),
                    tuple(json.loads(row["basis_json"])),
                )
                == (event.message, event.blocked, event.basis)
            )

        row = connection.execute(
            """
            SELECT size_bytes, mtime_ns, device_id, inode, mode, condition,
                   kind, scope, basis_json, producer_identity, last_seen_generation
            FROM run_items
            WHERE run_id = ? AND relative_path = ?
            """,
            (run_id, event.relative_path.as_posix()),
        ).fetchone()
        return (
            row is not None
            and row["last_seen_generation"] == scan_generation
            and (
                _row_observation(row) == _item_observation(event)
                and row["kind"] == event.kind
                and row["scope"] == event.scope
                and tuple(json.loads(row["basis_json"])) == event.basis
                and row["producer_identity"] == DISCOVERY_PRODUCER
            )
        )

    def commit_batch(
        self,
        run_id: str,
        scan_generation: int,
        events: Iterable[DiscoveryEvent],
        fingerprint: Callable[[DiscoveredSource], CandidateFingerprint],
    ) -> None:
        event_list = list(events)
        if not event_list:
            return
        with self.connect() as connection:
            run = connection.execute(
                "SELECT dataset_id, reuse_domain FROM working_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(f"unknown working run: {run_id}")
            dataset_id = str(run["dataset_id"])
            for event in event_list:
                if isinstance(event, DiscoveryIssue):
                    self._write_issue(connection, run_id, scan_generation, event)
                else:
                    self._write_item(
                        connection,
                        dataset_id,
                        run_id,
                        scan_generation,
                        str(run["reuse_domain"]),
                        event,
                        fingerprint,
                    )
            connection.execute(
                """
                UPDATE working_runs
                SET checkpoint = ?, committed_batches = committed_batches + 1,
                    updated_at = ?
                WHERE run_id = ?
                """,
                (_event_key(event_list[-1]), _now(), run_id),
            )

    def get_run_summary(self, run_id: str) -> WorkingRunSummary:
        with self.connect() as connection:
            run = connection.execute(
                "SELECT * FROM working_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise KeyError(f"unknown working run: {run_id}")
            counts = {
                row["change_kind"]: row["count"]
                for row in connection.execute(
                    """
                    SELECT change_kind, COUNT(*) AS count
                    FROM run_items
                    WHERE run_id = ?
                    GROUP BY change_kind
                    """,
                    (run_id,),
                )
            }
            issue_count = connection.execute(
                "SELECT COUNT(*) FROM run_issues WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            item_count = connection.execute(
                "SELECT COUNT(*) FROM run_items WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            removed_count = connection.execute(
                "SELECT COUNT(*) FROM run_removals WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
        return WorkingRunSummary(
            run_id=run_id,
            dataset_id=str(run["dataset_id"]),
            status=WorkingRunStatus(run["status"]),
            scan_generation=int(run["scan_generation"]),
            checkpoint=run["checkpoint"],
            committed_batches=int(run["committed_batches"]),
            item_count=int(item_count),
            new_count=int(counts.get(ChangeKind.NEW, 0)),
            changed_count=int(counts.get(ChangeKind.CHANGED, 0)),
            reused_count=int(counts.get(ChangeKind.REUSED, 0)),
            error_count=int(counts.get(ChangeKind.ERROR, 0)),
            removed_count=int(removed_count),
            issue_count=int(issue_count),
            blocked_reason=run["blocked_reason"],
        )

    def get_run_items(self, run_id: str) -> tuple[AccountedItem, ...]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT relative_path, kind, scope, condition, basis_json,
                       change_kind, source_revision
                FROM run_items
                WHERE run_id = ?
                ORDER BY relative_path
                """,
                (run_id,),
            ).fetchall()
        return tuple(
            AccountedItem(
                relative_path=Path(row["relative_path"]),
                kind=str(row["kind"]),
                scope=str(row["scope"]),
                condition=str(row["condition"]),
                basis=tuple(json.loads(row["basis_json"])),
                change_kind=ChangeKind(row["change_kind"]),
                source_revision=row["source_revision"],
            )
            for row in rows
        )

    def get_run_issues(self, run_id: str) -> tuple[RecordedIssue, ...]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT relative_path, code, message, blocked, basis_json
                FROM run_issues
                WHERE run_id = ?
                ORDER BY relative_path, code
                """,
                (run_id,),
            ).fetchall()
        return tuple(
            RecordedIssue(
                relative_path=Path(row["relative_path"]),
                code=DiscoveryIssueCode(row["code"]),
                message=str(row["message"]),
                blocked=bool(row["blocked"]),
                basis=tuple(json.loads(row["basis_json"])),
            )
            for row in rows
        )

    def get_run_removals(self, run_id: str) -> tuple[RemovedSource, ...]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT relative_path, previous_revision, basis_json
                FROM run_removals
                WHERE run_id = ?
                ORDER BY relative_path
                """,
                (run_id,),
            ).fetchall()
        return tuple(
            RemovedSource(
                relative_path=Path(row["relative_path"]),
                previous_revision=int(row["previous_revision"]),
                basis=tuple(json.loads(row["basis_json"])),
            )
            for row in rows
        )

    def finish_run(self, run_id: str, scan_generation: int) -> None:
        with self.connect() as connection:
            run = connection.execute(
                "SELECT dataset_id FROM working_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if run is None:
                raise KeyError(f"unknown working run: {run_id}")
            connection.execute(
                """
                DELETE FROM run_issues
                WHERE run_id = ? AND last_seen_generation <> ?
                """,
                (run_id, scan_generation),
            )
            issue_count = connection.execute(
                "SELECT COUNT(*) FROM run_issues WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            missing = connection.execute(
                """
                SELECT relative_path, revision
                    FROM source_state
                    WHERE dataset_id = ? AND present = 1
                      AND NOT EXISTS (
                          SELECT 1 FROM run_items
                          WHERE run_id = ?
                            AND run_items.relative_path = source_state.relative_path
                            AND last_seen_generation = ?
                      )
                ORDER BY relative_path
                """,
                (run["dataset_id"], run_id, scan_generation),
            ).fetchall()
            for row in missing:
                connection.execute(
                    """
                    INSERT INTO run_removals (
                            run_id, relative_path, previous_revision,
                            basis_json, detected_at, scan_generation
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        row["relative_path"],
                        row["revision"],
                        json.dumps(("absent_after_complete_reconciliation",)),
                        _now(),
                        scan_generation,
                    ),
                )
            connection.execute(
                """
                UPDATE source_state
                    SET present = 0, last_observed_run_id = ?
                    WHERE dataset_id = ? AND present = 1
                      AND NOT EXISTS (
                          SELECT 1 FROM run_items
                          WHERE run_id = ?
                            AND run_items.relative_path = source_state.relative_path
                            AND last_seen_generation = ?
                      )
                """,
                (run_id, run["dataset_id"], run_id, scan_generation),
            )
            affected_paths = {
                str(row["relative_path"])
                for row in connection.execute(
                    """
                    SELECT relative_path FROM run_items
                    WHERE run_id = ? AND last_seen_generation = ?
                      AND change_kind IN (?, ?)
                    UNION
                    SELECT relative_path FROM run_removals
                    WHERE run_id = ? AND scan_generation = ?
                    """,
                    (
                        run_id,
                        scan_generation,
                        ChangeKind.CHANGED,
                        ChangeKind.ERROR,
                        run_id,
                        scan_generation,
                    ),
                )
            }
            if affected_paths:
                invalidate_source_dependencies(
                    connection,
                    str(run["dataset_id"]),
                    affected_paths,
                    reason="source_accounting_changed",
                )
            connection.execute(
                """
                DELETE FROM run_items
                WHERE run_id = ? AND last_seen_generation <> ?
                """,
                (run_id, scan_generation),
            )
            status = (
                WorkingRunStatus.COMPLETED_WITH_ISSUES
                if issue_count
                else WorkingRunStatus.COMPLETED
            )
            connection.execute(
                """
                UPDATE working_runs
                SET status = ?, finished_at = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, _now(), _now(), run_id),
            )

    def block_run(
        self,
        run_id: str,
        source_root: Path,
        code: DiscoveryIssueCode,
    ) -> None:
        with self.connect() as connection:
            run = connection.execute(
                """
                SELECT scan_generation, dataset_id FROM working_runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
            if run is None:
                raise KeyError(f"unknown working run: {run_id}")
            scan_generation = int(run["scan_generation"])
            self._write_issue(
                connection,
                run_id,
                scan_generation,
                DiscoveryIssue(
                    relative_path=Path("."),
                    locator=source_root,
                    code=code,
                    message="source root is unavailable or is on an unexpected volume",
                    blocked=True,
                    basis=("source_root_probe",),
                ),
            )
            connection.execute(
                """
                UPDATE working_runs
                SET status = ?, blocked_reason = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (WorkingRunStatus.BLOCKED, code, _now(), run_id),
            )
            invalidate_source_dependencies(
                connection,
                str(run["dataset_id"]),
                None,
                reason="source_root_unavailable",
            )

    def set_status(
        self,
        run_id: str,
        status: WorkingRunStatus,
        *,
        blocked_reason: DiscoveryIssueCode | None = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE working_runs
                SET status = ?, blocked_reason = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (status, blocked_reason, _now(), run_id),
            )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _write_item(
        self,
        connection: sqlite3.Connection,
        dataset_id: str,
        run_id: str,
        scan_generation: int,
        reuse_domain: str,
        item: DiscoveredSource,
        fingerprint_candidate: Callable[[DiscoveredSource], CandidateFingerprint],
    ) -> None:
        previous = connection.execute(
            """
            SELECT * FROM source_state
            WHERE dataset_id = ? AND relative_path = ?
            """,
            (dataset_id, item.relative_path.as_posix()),
        ).fetchone()
        existing_run_item = connection.execute(
            """
            SELECT source_revision, change_kind
            FROM run_items
            WHERE run_id = ? AND relative_path = ?
            """,
            (run_id, item.relative_path.as_posix()),
        ).fetchone()
        condition = item.condition
        basis = item.basis
        fingerprint: CandidateFingerprint | None = None
        previously_present = previous is not None and bool(previous["present"])
        change_kind = ChangeKind.NEW if not previously_present else ChangeKind.CHANGED
        revision = 1 if previous is None else int(previous["revision"]) + 1

        try:
            fingerprint = fingerprint_candidate(item)
        except OSError as error:
            condition = SourceCondition.ERROR
            basis += ("fingerprint_failed",)
            change_kind = ChangeKind.ERROR
            revision = None
            self._write_issue(
                connection,
                run_id,
                scan_generation,
                DiscoveryIssue(
                    relative_path=item.relative_path,
                    locator=item.locator,
                    code=DiscoveryIssueCode.ENTRY_INSPECTION_FAILED,
                    message=str(error),
                    blocked=False,
                    basis=("fingerprint_failed",),
                ),
            )
        else:
            connection.execute(
                """
                DELETE FROM run_issues
                WHERE run_id = ? AND relative_path = ? AND code = ?
                """,
                (
                    run_id,
                    item.relative_path.as_posix(),
                    DiscoveryIssueCode.ENTRY_INSPECTION_FAILED,
                ),
            )
            if previously_present and _can_reuse_current_observation(
                previous,
                item,
                fingerprint,
                reuse_domain,
            ):
                if previous["last_observed_run_id"] == run_id and existing_run_item:
                    change_kind = ChangeKind(existing_run_item["change_kind"])
                    revision = existing_run_item["source_revision"]
                else:
                    change_kind = ChangeKind.REUSED
                    revision = int(previous["revision"])
            self._upsert_source_state(
                connection,
                dataset_id,
                run_id,
                item,
                condition,
                basis,
                revision,
                fingerprint,
                reuse_domain,
            )

        self._upsert_run_item(
            connection,
            run_id,
            scan_generation,
            item,
            condition,
            basis,
            revision,
            fingerprint,
            change_kind,
            reuse_domain,
        )

    def _upsert_source_state(
        self,
        connection: sqlite3.Connection,
        dataset_id: str,
        run_id: str,
        item: DiscoveredSource,
        condition: SourceCondition,
        basis: tuple[str, ...],
        revision: int,
        fingerprint: CandidateFingerprint,
        reuse_domain: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO source_state (
                dataset_id, relative_path, revision, kind, scope, condition,
                basis_json, size_bytes, mtime_ns, device_id, inode, mode,
                fingerprint_algorithm, fingerprint, producer_identity,
                reuse_domain, present,
                last_observed_run_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(dataset_id, relative_path) DO UPDATE SET
                revision = excluded.revision, kind = excluded.kind,
                scope = excluded.scope, condition = excluded.condition,
                basis_json = excluded.basis_json, size_bytes = excluded.size_bytes,
                mtime_ns = excluded.mtime_ns, device_id = excluded.device_id,
                inode = excluded.inode, mode = excluded.mode,
                fingerprint_algorithm = excluded.fingerprint_algorithm,
                fingerprint = excluded.fingerprint,
                producer_identity = excluded.producer_identity,
                reuse_domain = excluded.reuse_domain,
                present = excluded.present,
                last_observed_run_id = excluded.last_observed_run_id
            """,
            (
                dataset_id,
                item.relative_path.as_posix(),
                revision,
                item.kind,
                item.scope,
                condition,
                json.dumps(basis),
                fingerprint.size_bytes,
                fingerprint.mtime_ns,
                fingerprint.device_id,
                fingerprint.inode,
                fingerprint.mode,
                fingerprint.algorithm,
                fingerprint.value,
                DISCOVERY_PRODUCER,
                reuse_domain,
                1,
                run_id,
            ),
        )

    def _upsert_run_item(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        scan_generation: int,
        item: DiscoveredSource,
        condition: SourceCondition,
        basis: tuple[str, ...],
        revision: int | None,
        fingerprint: CandidateFingerprint | None,
        change_kind: ChangeKind,
        reuse_domain: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO run_items (
                run_id, relative_path, normalized_path, source_revision,
                kind, scope, condition,
                basis_json, size_bytes, mtime_ns, device_id, inode, mode,
                fingerprint_algorithm, fingerprint, producer_identity,
                reuse_domain, change_kind, last_seen_generation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, relative_path) DO UPDATE SET
                normalized_path = excluded.normalized_path,
                source_revision = excluded.source_revision, kind = excluded.kind,
                scope = excluded.scope, condition = excluded.condition,
                basis_json = excluded.basis_json, size_bytes = excluded.size_bytes,
                mtime_ns = excluded.mtime_ns, device_id = excluded.device_id,
                inode = excluded.inode, mode = excluded.mode,
                fingerprint_algorithm = excluded.fingerprint_algorithm,
                fingerprint = excluded.fingerprint,
                producer_identity = excluded.producer_identity,
                reuse_domain = excluded.reuse_domain,
                change_kind = excluded.change_kind,
                last_seen_generation = excluded.last_seen_generation
            """,
            (
                run_id,
                item.relative_path.as_posix(),
                _normalized_path(item.relative_path.as_posix()),
                revision,
                item.kind,
                item.scope,
                condition,
                json.dumps(basis),
                fingerprint.size_bytes if fingerprint else item.size_bytes,
                fingerprint.mtime_ns if fingerprint else item.mtime_ns,
                fingerprint.device_id if fingerprint else item.device_id,
                fingerprint.inode if fingerprint else item.inode,
                fingerprint.mode if fingerprint else item.mode,
                fingerprint.algorithm if fingerprint else None,
                fingerprint.value if fingerprint else None,
                DISCOVERY_PRODUCER,
                reuse_domain,
                change_kind,
                scan_generation,
            ),
        )
        self._record_normalized_path_collisions(
            connection,
            run_id,
            scan_generation,
            _normalized_path(item.relative_path.as_posix()),
        )

    def _record_normalized_path_collisions(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        scan_generation: int,
        normalized_path: str,
    ) -> None:
        paths = tuple(
            str(row["relative_path"])
            for row in connection.execute(
                """
                SELECT relative_path
                FROM run_items
                WHERE run_id = ? AND normalized_path = ?
                  AND last_seen_generation = ?
                ORDER BY relative_path
                """,
                (run_id, normalized_path, scan_generation),
            )
        )
        if len(paths) < 2:
            return
        for relative_path in paths:
            peers = tuple(path for path in paths if path != relative_path)
            self._write_issue(
                connection,
                run_id,
                scan_generation,
                DiscoveryIssue(
                    relative_path=Path(relative_path),
                    locator=Path(relative_path),
                    code=DiscoveryIssueCode.NORMALIZED_PATH_COLLISION,
                    message=(
                        "Distinct source paths share the same Unicode NFC form: "
                        + ", ".join(peers)
                    ),
                    blocked=False,
                    basis=("unicode_nfc_collision",),
                ),
            )

    def _write_issue(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        scan_generation: int,
        issue: DiscoveryIssue,
    ) -> None:
        connection.execute(
            """
            INSERT INTO run_issues (
                run_id, relative_path, code, message, blocked, basis_json,
                observed_at, last_seen_generation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, relative_path, code) DO UPDATE SET
                message = excluded.message, blocked = excluded.blocked,
                basis_json = excluded.basis_json, observed_at = excluded.observed_at,
                last_seen_generation = excluded.last_seen_generation
            """,
            (
                run_id,
                issue.relative_path.as_posix(),
                issue.code,
                issue.message,
                int(issue.blocked),
                json.dumps(issue.basis),
                _now(),
                scan_generation,
            ),
        )
        if issue.code is DiscoveryIssueCode.DIRECTORY_READ_FAILED and not issue.blocked:
            self._carry_forward_unreadable_subtree(
                connection,
                run_id,
                scan_generation,
                issue,
            )

    def _carry_forward_unreadable_subtree(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        scan_generation: int,
        issue: DiscoveryIssue,
    ) -> None:
        dataset = connection.execute(
            "SELECT dataset_id FROM working_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if dataset is None:
            raise KeyError(f"unknown working run: {run_id}")
        prefix = issue.relative_path.as_posix()
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = connection.execute(
            """
            SELECT * FROM source_state
            WHERE dataset_id = ? AND present = 1
              AND (relative_path = ? OR relative_path LIKE ? ESCAPE '\\')
            ORDER BY relative_path
            """,
            (dataset["dataset_id"], prefix, f"{escaped}/%"),
        ).fetchall()
        for row in rows:
            basis = tuple(json.loads(row["basis_json"])) + (
                "ancestor_directory_read_failed",
            )
            connection.execute(
                """
                INSERT INTO run_items (
                    run_id, relative_path, normalized_path, source_revision,
                    kind, scope, condition,
                    basis_json, size_bytes, mtime_ns, device_id, inode, mode,
                    fingerprint_algorithm, fingerprint, producer_identity,
                    reuse_domain, change_kind, last_seen_generation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, relative_path) DO UPDATE SET
                    normalized_path = excluded.normalized_path,
                    condition = excluded.condition, basis_json = excluded.basis_json,
                    change_kind = excluded.change_kind,
                    last_seen_generation = excluded.last_seen_generation
                """,
                (
                    run_id,
                    row["relative_path"],
                    _normalized_path(str(row["relative_path"])),
                    row["revision"],
                    row["kind"],
                    row["scope"],
                    SourceCondition.UNRESOLVED,
                    json.dumps(basis),
                    row["size_bytes"],
                    row["mtime_ns"],
                    row["device_id"],
                    row["inode"],
                    row["mode"],
                    row["fingerprint_algorithm"],
                    row["fingerprint"],
                    row["producer_identity"],
                    row["reuse_domain"],
                    ChangeKind.ERROR,
                    scan_generation,
                ),
            )
            self._record_normalized_path_collisions(
                connection,
                run_id,
                scan_generation,
                _normalized_path(str(row["relative_path"])),
            )


def _can_reuse_current_observation(
    previous: sqlite3.Row,
    item: DiscoveredSource,
    fingerprint: CandidateFingerprint,
    reuse_domain: str,
) -> bool:
    """Compare discovery observations; this cannot authorize Artifact reuse."""

    return (
        previous["fingerprint_algorithm"] == fingerprint.algorithm
        and previous["fingerprint"] == fingerprint.value
        and previous["reuse_domain"] == reuse_domain
        and _row_stat_identity(previous) == fingerprint_stat_identity(fingerprint)
        and previous["kind"] == item.kind
        and previous["scope"] == item.scope
        and previous["condition"] == item.condition
        and tuple(json.loads(previous["basis_json"])) == item.basis
    )


def _normalized_path(relative_path: str) -> str:
    """Return a comparison key without changing the authoritative spelling."""

    return unicodedata.normalize("NFC", relative_path)


def _item_observation(item: DiscoveredSource) -> tuple[object, ...]:
    return (
        item.size_bytes,
        item.mtime_ns,
        item.device_id,
        item.inode,
        item.mode,
        item.condition,
    )


def _row_observation(row: sqlite3.Row) -> tuple[object, ...]:
    return (
        row["size_bytes"],
        row["mtime_ns"],
        row["device_id"],
        row["inode"],
        row["mode"],
        row["condition"],
    )


def _row_stat_identity(row: sqlite3.Row) -> tuple[object, ...]:
    return (
        row["size_bytes"],
        row["mtime_ns"],
        row["device_id"],
        row["inode"],
        row["mode"],
    )


def _event_key(event: DiscoveryEvent) -> str:
    suffix = "issue" if isinstance(event, DiscoveryIssue) else "source"
    return f"{event.relative_path.as_posix()}\0{suffix}"


def _attachment_from_row(row: sqlite3.Row) -> SourceAttachment:
    return SourceAttachment(
        source_root=Path(row["source_root"]),
        volume_identity=row["expected_volume_identity"],
        root_identity=row["expected_root_identity"],
        identity_strength=str(row["identity_strength"]),
        reuse_domain=str(row["reuse_domain"]),
        binding_reason=str(row["binding_reason"]),
        capabilities=FilesystemCapabilities.from_json(
            str(row["filesystem_capabilities_json"])
        ),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
