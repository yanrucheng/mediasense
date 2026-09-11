"""Private SQLite state machine for reusable PreCheck work."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from ._accounting_types import WorkingRunStatus
from ._invalidation import invalidate_work_tree
from ._sqlite_scope import connect
from ._working_schema import SCHEMA_VERSION
from ._work_types import (
    AttemptOutcome,
    DependencyKind,
    InvalidWorkSpec,
    InvalidWorkTransition,
    LeaseLost,
    WorkAttempt,
    WorkDependency,
    WorkIdentityCollision,
    WorkLease,
    WorkRecord,
    WorkSpec,
    WorkStatus,
)


_MAX_INLINE_OUTPUT_BYTES = 64 * 1024


class SQLiteWorkStore:
    """Persist Work Record identity, dependencies, attempts, and leases.

    This store does not execute producers and does not publish Artifacts. Workers
    return state transitions through this coordinator after doing expensive work
    outside SQLite transactions.
    """

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self._verify_schema()

    def ensure_work(
        self,
        run_id: str,
        spec: WorkSpec,
        *,
        max_attempts: int = 3,
        now: datetime | None = None,
    ) -> WorkRecord:
        """Reuse one current semantic record or create and attach a new one."""

        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        observed_at = _utc(now)
        descriptor = _descriptor_json(spec)
        semantic_key = _semantic_key(descriptor)
        with self._transaction(immediate=True) as connection:
            run = self._require_run_ready(connection, run_id)
            self._validate_source_dependencies(
                connection,
                run_id,
                str(run["dataset_id"]),
                spec,
            )
            self._validate_upstream_dependencies(connection, spec)
            existing = connection.execute(
                """
                SELECT * FROM work_records
                WHERE semantic_key = ? AND status <> ? AND status <> ?
                """,
                (semantic_key, WorkStatus.INVALIDATED, WorkStatus.CANCELLED),
            ).fetchone()
            if existing is not None:
                if existing["descriptor_json"] != descriptor:
                    raise WorkIdentityCollision(
                        f"semantic key collision for {semantic_key}"
                    )
                if int(existing["max_attempts"]) != max_attempts:
                    raise InvalidWorkSpec(
                        "equivalent work already exists with a different retry policy"
                    )
                work_id = str(existing["work_id"])
            else:
                work_id = uuid4().hex
                status = self._initial_status(connection, spec)
                connection.execute(
                    """
                    INSERT INTO work_records (
                        work_id, semantic_key, descriptor_json, capability,
                        producer_identity, status, max_attempts, created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        work_id,
                        semantic_key,
                        descriptor,
                        spec.capability,
                        spec.producer_identity,
                        status,
                        max_attempts,
                        observed_at,
                        observed_at,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO work_dependencies (
                        work_id, dependency_kind, dependency_key,
                        dependency_value
                    ) VALUES (?, ?, ?, ?)
                    """,
                    (
                        (work_id, dependency.kind, dependency.key, dependency.value)
                        for dependency in spec.dependencies
                    ),
                )
            attached = connection.execute(
                """
                INSERT OR IGNORE INTO run_work_records (
                    run_id, work_id, requested_at
                ) VALUES (?, ?, ?)
                """,
                (run_id, work_id, observed_at),
            )
            if attached.rowcount:
                from ._run_sqlite import record_work_scope_change

                record_work_scope_change(
                    connection, run_id, spec.capability, observed_at
                )
            return self._get_work(connection, work_id)

    def claim_ready_work(
        self,
        run_id: str,
        owner: str,
        *,
        lease_duration: timedelta,
        limit: int = 1,
        work_id: str | None = None,
        now: datetime | None = None,
    ) -> tuple[WorkLease, ...]:
        """Atomically claim a bounded set of ready work for one run."""

        if not owner.strip():
            raise ValueError("lease owner must be non-empty")
        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        if limit < 1:
            raise ValueError("claim limit must be positive")
        claimed_at = _utc(now)
        expires_at = _iso(_as_datetime(claimed_at) + lease_duration)
        leases: list[WorkLease] = []
        with self._transaction(immediate=True) as connection:
            self._require_run_ready(connection, run_id)
            self._recover_expired(connection, claimed_at)
            self._promote_ready(connection, claimed_at)
            candidates = connection.execute(
                """
                SELECT work_records.work_id, work_records.attempt_count
                FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                  AND (
                    work_records.status = ?
                    OR (
                        work_records.status = ?
                        AND (work_records.retry_not_before IS NULL
                             OR work_records.retry_not_before <= ?)
                    )
                  )
                  AND (? IS NULL OR work_records.work_id = ?)
                ORDER BY work_records.created_at, work_records.work_id
                LIMIT ?
                """,
                (
                    run_id,
                    WorkStatus.READY,
                    WorkStatus.RETRYABLE_FAILURE,
                    claimed_at,
                    work_id,
                    work_id,
                    limit,
                ),
            ).fetchall()
            for row in candidates:
                work_id = str(row["work_id"])
                attempt_number = int(row["attempt_count"]) + 1
                token = uuid4().hex
                changed = connection.execute(
                    """
                    UPDATE work_records
                    SET status = ?, attempt_count = ?, lease_run_id = ?,
                        lease_owner = ?, lease_token = ?, lease_expires_at = ?,
                        retry_not_before = NULL, updated_at = ?
                    WHERE work_id = ? AND status IN (?, ?)
                    """,
                    (
                        WorkStatus.RUNNING,
                        attempt_number,
                        run_id,
                        owner.strip(),
                        token,
                        expires_at,
                        claimed_at,
                        work_id,
                        WorkStatus.READY,
                        WorkStatus.RETRYABLE_FAILURE,
                    ),
                ).rowcount
                if changed != 1:
                    continue
                connection.execute(
                    """
                    INSERT INTO work_attempts (
                        work_id, attempt_number, run_id, lease_owner,
                        lease_token, started_at, lease_expires_at, outcome
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        work_id,
                        attempt_number,
                        run_id,
                        owner.strip(),
                        token,
                        claimed_at,
                        expires_at,
                        AttemptOutcome.RUNNING,
                    ),
                )
                leases.append(
                    WorkLease(
                        work_id=work_id,
                        run_id=run_id,
                        owner=owner.strip(),
                        token=token,
                        attempt_number=attempt_number,
                        expires_at=_as_datetime(expires_at),
                    )
                )
        return tuple(leases)

    def renew_lease(
        self,
        lease: WorkLease,
        *,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> WorkLease:
        return self.renew_leases(
            (lease,), lease_duration=lease_duration, now=now
        )[0]

    def renew_leases(
        self,
        leases: Iterable[WorkLease],
        *,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> tuple[WorkLease, ...]:
        """Renew a bounded batch atomically; every owner and expiry must be valid."""

        if lease_duration <= timedelta(0):
            raise ValueError("lease_duration must be positive")
        entries = tuple(leases)
        if len(entries) > 1024:
            raise ValueError("lease renewal batch cannot exceed 1024 items")
        if len({lease.work_id for lease in entries}) != len(entries):
            raise ValueError("batch Work leases must be unique")
        if not entries:
            return ()
        observed_at = _utc(now)
        expires_at = _iso(_as_datetime(observed_at) + lease_duration)
        with self._transaction(immediate=True) as connection:
            self._recover_expired(connection, observed_at)
            for lease in entries:
                self._require_lease(connection, lease)
            connection.executemany(
                """
                UPDATE work_records
                SET lease_expires_at = ?, updated_at = ?
                WHERE work_id = ?
                """,
                ((expires_at, observed_at, lease.work_id) for lease in entries),
            )
            connection.executemany(
                """
                UPDATE work_attempts
                SET lease_expires_at = ?
                WHERE work_id = ? AND attempt_number = ?
                """,
                ((expires_at, lease.work_id, lease.attempt_number) for lease in entries),
            )
        return tuple(
            WorkLease(
                work_id=lease.work_id,
                run_id=lease.run_id,
                owner=lease.owner,
                token=lease.token,
                attempt_number=lease.attempt_number,
                expires_at=_as_datetime(expires_at),
            )
            for lease in entries
        )

    def save_checkpoint(
        self,
        lease: WorkLease,
        checkpoint: str,
        *,
        now: datetime | None = None,
    ) -> None:
        if not checkpoint:
            raise ValueError("checkpoint must be non-empty")
        observed_at = _utc(now)
        with self._transaction(immediate=True) as connection:
            self._recover_expired(connection, observed_at)
            self._require_lease(connection, lease)
            connection.execute(
                """
                UPDATE work_records
                SET checkpoint = ?, updated_at = ?
                WHERE work_id = ?
                """,
                (checkpoint, observed_at, lease.work_id),
            )
            connection.execute(
                """
                UPDATE work_attempts
                SET checkpoint = ?
                WHERE work_id = ? AND attempt_number = ?
                """,
                (checkpoint, lease.work_id, lease.attempt_number),
            )

    def succeed_work(
        self,
        lease: WorkLease,
        output: object,
        *,
        now: datetime | None = None,
    ) -> WorkRecord:
        """Atomically commit a small structured result and mark work successful."""

        observed_at = _utc(now)
        output_json = _output_json(output)
        output_digest = (
            "inline-json-sha256-v1:"
            + hashlib.sha256(output_json.encode("utf-8")).hexdigest()
        )
        with self._transaction(immediate=True) as connection:
            self._recover_expired(connection, observed_at)
            self._require_lease(connection, lease)
            connection.execute(
                """
                UPDATE work_attempts
                SET finished_at = ?, outcome = ?, retryable = 0
                WHERE work_id = ? AND attempt_number = ?
                """,
                (
                    observed_at,
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
                    observed_at,
                    observed_at,
                    lease.work_id,
                ),
            )
            self._promote_dependents(connection, lease.work_id, observed_at)
            return self._get_work(connection, lease.work_id)

    def succeed_work_many(
        self,
        values: Iterable[tuple[WorkLease, object]],
        *,
        now: datetime | None = None,
    ) -> tuple[WorkRecord, ...]:
        """Commit a related set of small outputs atomically after one batch effect."""

        entries = tuple(values)
        if not entries:
            return ()
        work_ids = tuple(lease.work_id for lease, _output in entries)
        if len(set(work_ids)) != len(work_ids):
            raise ValueError("batch Work leases must be unique")
        encoded = tuple(
            (
                lease,
                output_json,
                "inline-json-sha256-v1:"
                + hashlib.sha256(output_json.encode("utf-8")).hexdigest(),
            )
            for lease, output in entries
            for output_json in (_output_json(output),)
        )
        observed_at = _utc(now)
        with self._transaction(immediate=True) as connection:
            self._recover_expired(connection, observed_at)
            for lease, _output_json_value, _output_digest in encoded:
                self._require_lease(connection, lease)
            for lease, output_json, output_digest in encoded:
                connection.execute(
                    """
                    UPDATE work_attempts
                    SET finished_at = ?, outcome = ?, retryable = 0
                    WHERE work_id = ? AND attempt_number = ?
                    """,
                    (
                        observed_at,
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
                        observed_at,
                        observed_at,
                        lease.work_id,
                    ),
                )
            for lease, _output_json_value, _output_digest in encoded:
                self._promote_dependents(connection, lease.work_id, observed_at)
            return tuple(
                self._get_work(connection, lease.work_id)
                for lease, _output_json_value, _output_digest in encoded
            )

    def fail_work(
        self,
        lease: WorkLease,
        *,
        error_code: str,
        message: str,
        retryable: bool,
        retry_delay: timedelta = timedelta(0),
        now: datetime | None = None,
    ) -> WorkRecord:
        if not error_code.strip() or not message.strip():
            raise ValueError("failure code and message must be non-empty")
        if retry_delay < timedelta(0):
            raise ValueError("retry_delay cannot be negative")
        observed_at = _utc(now)
        with self._transaction(immediate=True) as connection:
            self._recover_expired(connection, observed_at)
            row = self._require_lease(connection, lease)
            can_retry = retryable and int(row["attempt_count"]) < int(
                row["max_attempts"]
            )
            status = (
                WorkStatus.RETRYABLE_FAILURE
                if can_retry
                else WorkStatus.TERMINAL_FAILURE
            )
            outcome = (
                AttemptOutcome.RETRYABLE_FAILURE
                if can_retry
                else AttemptOutcome.TERMINAL_FAILURE
            )
            retry_not_before = (
                _iso(_as_datetime(observed_at) + retry_delay) if can_retry else None
            )
            connection.execute(
                """
                UPDATE work_attempts
                SET finished_at = ?, outcome = ?, retryable = ?,
                    error_code = ?, error_message = ?
                WHERE work_id = ? AND attempt_number = ?
                """,
                (
                    observed_at,
                    outcome,
                    int(can_retry),
                    error_code.strip(),
                    message.strip(),
                    lease.work_id,
                    lease.attempt_number,
                ),
            )
            connection.execute(
                """
                UPDATE work_records
                SET status = ?, lease_run_id = NULL, lease_owner = NULL,
                    lease_token = NULL, lease_expires_at = NULL,
                    retry_not_before = ?, last_failure_code = ?,
                    last_failure_message = ?, updated_at = ?
                WHERE work_id = ?
                """,
                (
                    status,
                    retry_not_before,
                    error_code.strip(),
                    message.strip(),
                    observed_at,
                    lease.work_id,
                ),
            )
            if status is WorkStatus.TERMINAL_FAILURE:
                self._block_dependents(connection, lease.work_id, observed_at)
            return self._get_work(connection, lease.work_id)

    def recover_expired_leases(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[str, ...]:
        observed_at = _utc(now)
        with self._transaction(immediate=True) as connection:
            return tuple(self._recover_expired(connection, observed_at))

    def invalidate_work(
        self,
        work_id: str,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> tuple[str, ...]:
        """Invalidate work and its transitive dependents without deleting history."""

        if not reason.strip():
            raise ValueError("invalidation reason must be non-empty")
        observed_at = _utc(now)
        invalidated: list[str] = []
        with self._transaction(immediate=True) as connection:
            self._get_work(connection, work_id)
            invalidated.extend(
                invalidate_work_tree(
                    connection,
                    {work_id: reason.strip()},
                    observed_at=observed_at,
                )
            )
        return tuple(invalidated)

    def invalidate_for_rebuild(
        self,
        run_id: str,
        reason: str,
        *,
        work_ids: Iterable[str] = (),
        capabilities: Iterable[str] = (),
        source_paths: Iterable[Path] = (),
        now: datetime | None = None,
    ) -> tuple[str, ...]:
        """Invalidate an explicit selector intersection and its dependents."""

        if not reason.strip():
            raise ValueError("rebuild reason must be non-empty")
        selected_work_ids = {value.strip() for value in work_ids if value.strip()}
        selected_capabilities = {
            value.strip() for value in capabilities if value.strip()
        }
        selected_paths = {
            _validated_rebuild_path(value).as_posix() for value in source_paths
        }
        if not (selected_work_ids or selected_capabilities or selected_paths):
            raise ValueError("manual rebuild requires at least one selector")
        observed_at = _utc(now)
        with self._transaction(immediate=True) as connection:
            self._require_run(connection, run_id)
            rows = connection.execute(
                """
                SELECT work_records.work_id, work_records.capability,
                       work_records.status
                FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                ORDER BY work_records.created_at, work_records.work_id
                """,
                (run_id,),
            ).fetchall()
            attached_ids = {str(row["work_id"]) for row in rows}
            unknown_ids = selected_work_ids - attached_ids
            if unknown_ids:
                raise KeyError(
                    "manual rebuild Work is not attached to this run: "
                    + ", ".join(sorted(unknown_ids))
                )
            roots: dict[str, str] = {}
            for row in rows:
                work_id = str(row["work_id"])
                if selected_work_ids and work_id not in selected_work_ids:
                    continue
                if (
                    selected_capabilities
                    and str(row["capability"]) not in selected_capabilities
                ):
                    continue
                if selected_paths and not (
                    selected_paths & _work_source_paths(connection, work_id)
                ):
                    continue
                if WorkStatus(row["status"]) is WorkStatus.RUNNING:
                    raise InvalidWorkTransition(
                        f"cannot rebuild actively leased Work: {work_id}"
                    )
                roots[work_id] = f"manual rebuild: {reason.strip()}"
            if not roots:
                raise ValueError("manual rebuild selectors matched no Work")
            return invalidate_work_tree(
                connection,
                roots,
                observed_at=observed_at,
            )

    def get_work(self, work_id: str) -> WorkRecord:
        with self._connect() as connection:
            return self._get_work(connection, work_id)

    def get_run_work(self, run_id: str, work_id: str) -> WorkRecord:
        """Return one Work Record only when it is attached to the Run."""

        with self._connect() as connection:
            if (
                connection.execute(
                    """
                SELECT 1 FROM run_work_records
                WHERE run_id = ? AND work_id = ?
                """,
                    (run_id, work_id),
                ).fetchone()
                is None
            ):
                raise KeyError(f"Work Record is not attached to this run: {work_id}")
            return self._get_work(connection, work_id)

    def detach_run_work(
        self,
        run_id: str,
        work_ids: Iterable[str],
    ) -> tuple[str, ...]:
        """Detach superseded, inactive Work from one mutable Run without deleting it."""

        selected = tuple(dict.fromkeys(str(work_id) for work_id in work_ids))
        if not selected:
            return ()
        detached: list[str] = []
        with self._transaction(immediate=True) as connection:
            self._require_run(connection, run_id)
            for work_id in selected:
                row = connection.execute(
                    """
                    SELECT work_records.status, work_records.lease_run_id, work_records.capability
                    FROM run_work_records
                    JOIN work_records USING (work_id)
                    WHERE run_work_records.run_id = ?
                      AND run_work_records.work_id = ?
                    """,
                    (run_id, work_id),
                ).fetchone()
                if row is None:
                    continue
                if (
                    WorkStatus(row["status"]) is WorkStatus.RUNNING
                    and row["lease_run_id"] == run_id
                ):
                    raise InvalidWorkTransition(
                        f"cannot detach actively leased Work: {work_id}"
                    )
                connection.execute(
                    """
                    DELETE FROM run_work_records
                    WHERE run_id = ? AND work_id = ?
                    """,
                    (run_id, work_id),
                )
                from ._run_sqlite import record_work_scope_change

                record_work_scope_change(
                    connection, run_id, row["capability"], _utc(None)
                )
                detached.append(work_id)
        return tuple(detached)

    def get_attempts(self, work_id: str) -> tuple[WorkAttempt, ...]:
        with self._connect() as connection:
            self._get_work(connection, work_id)
            rows = connection.execute(
                """
                SELECT * FROM work_attempts
                WHERE work_id = ? ORDER BY attempt_number
                """,
                (work_id,),
            ).fetchall()
        return tuple(_attempt_from_row(row) for row in rows)

    def list_run_work(self, run_id: str) -> tuple[WorkRecord, ...]:
        with self._connect() as connection:
            self._require_run(connection, run_id)
            rows = connection.execute(
                """
                SELECT work_records.work_id
                FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                ORDER BY work_records.created_at, work_records.work_id
                """,
                (run_id,),
            ).fetchall()
            return tuple(
                self._get_work(connection, str(row["work_id"])) for row in rows
            )

    def iter_run_work(
        self,
        run_id: str,
        *,
        capability: str | None = None,
        status: WorkStatus | None = None,
        page_size: int = 1_000,
    ) -> Iterator[WorkRecord]:
        """Page attached Work without retaining the whole Run in memory."""

        if page_size < 1:
            raise ValueError("Work page size must be positive")
        after = ""
        first_page = True
        while True:
            clauses = ["run_work_records.run_id = ?", "work_records.work_id > ?"]
            parameters: list[object] = [run_id, after]
            if capability is not None:
                clauses.append("work_records.capability = ?")
                parameters.append(capability)
            if status is not None:
                clauses.append("work_records.status = ?")
                parameters.append(WorkStatus(status).value)
            parameters.append(page_size)
            with self._connect() as connection:
                if first_page:
                    self._require_run(connection, run_id)
                    first_page = False
                rows = connection.execute(
                    """
                    SELECT work_records.work_id
                    FROM run_work_records
                    JOIN work_records USING (work_id)
                    WHERE """
                    + " AND ".join(clauses)
                    + " ORDER BY work_records.work_id LIMIT ?",
                    parameters,
                ).fetchall()
                records = tuple(
                    self._get_work(connection, str(row["work_id"])) for row in rows
                )
            if not records:
                return
            yield from records
            after = records[-1].work_id

    def iter_run_work_ids(
        self,
        run_id: str,
        *,
        capability: str | None = None,
        status: WorkStatus | None = None,
        page_size: int = 1_000,
    ) -> Iterator[str]:
        """Page attached Work identities without decoding full Work records."""

        if page_size < 1:
            raise ValueError("Work page size must be positive")
        after = ""
        first_page = True
        while True:
            clauses = ["run_work_records.run_id = ?", "work_records.work_id > ?"]
            parameters: list[object] = [run_id, after]
            if capability is not None:
                clauses.append("work_records.capability = ?")
                parameters.append(capability)
            if status is not None:
                clauses.append("work_records.status = ?")
                parameters.append(WorkStatus(status).value)
            parameters.append(page_size)
            with self._connect() as connection:
                if first_page:
                    self._require_run(connection, run_id)
                    first_page = False
                rows = connection.execute(
                    """
                    SELECT work_records.work_id
                    FROM run_work_records
                    JOIN work_records USING (work_id)
                    WHERE """
                    + " AND ".join(clauses)
                    + " ORDER BY work_records.work_id LIMIT ?",
                    parameters,
                ).fetchall()
            if not rows:
                return
            work_ids = tuple(str(row["work_id"]) for row in rows)
            yield from work_ids
            after = work_ids[-1]

    def get_run_work_by_parameter(
        self,
        run_id: str,
        *,
        capability: str,
        key: str,
        value: str,
    ) -> tuple[WorkRecord, ...]:
        """Resolve a bounded subject-like selection through the dependency index."""

        if not capability.strip() or not key.strip() or not value.strip():
            raise ValueError("Work parameter lookup values must be non-empty")
        with self._connect() as connection:
            self._require_run(connection, run_id)
            rows = connection.execute(
                """
                SELECT work_records.work_id
                FROM work_dependencies
                JOIN work_records USING (work_id)
                JOIN run_work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                  AND work_records.capability = ?
                  AND work_dependencies.dependency_kind = ?
                  AND work_dependencies.dependency_key = ?
                  AND work_dependencies.dependency_value = ?
                ORDER BY work_records.created_at, work_records.work_id
                """,
                (run_id, capability, DependencyKind.PARAMETER, key, value),
            ).fetchall()
            return tuple(
                self._get_work(connection, str(row["work_id"])) for row in rows
            )

    def get_run_work_counts(self, run_id: str) -> dict[WorkStatus, int]:
        """Return bounded operational progress without loading every Work Record."""

        with self._connect() as connection:
            self._require_run(connection, run_id)
            rows = connection.execute(
                """
                SELECT work_records.status, COUNT(*) AS count
                FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                GROUP BY work_records.status
                """,
                (run_id,),
            ).fetchall()
        return {WorkStatus(row["status"]): int(row["count"]) for row in rows}

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
            except sqlite3.OperationalError as error:
                raise RuntimeError(
                    "initialize the PreCheck working store before creating WorkStore"
                ) from error
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported or uninitialized internal schema")

    def _initial_status(
        self,
        connection: sqlite3.Connection,
        spec: WorkSpec,
    ) -> WorkStatus:
        upstream = self._upstream_statuses(connection, spec.dependencies)
        if any(status in _UNUSABLE_UPSTREAM for status in upstream):
            return WorkStatus.BLOCKED
        if all(status is WorkStatus.SUCCEEDED for status in upstream):
            return WorkStatus.READY
        return WorkStatus.PENDING

    def _validate_upstream_dependencies(
        self,
        connection: sqlite3.Connection,
        spec: WorkSpec,
    ) -> None:
        for dependency in spec.dependencies:
            if dependency.kind is not DependencyKind.UPSTREAM_WORK:
                continue
            row = connection.execute(
                "SELECT semantic_key FROM work_records WHERE work_id = ?",
                (dependency.key,),
            ).fetchone()
            if row is None:
                raise InvalidWorkSpec(f"unknown upstream Work Record: {dependency.key}")
            if row["semantic_key"] != dependency.value:
                raise InvalidWorkSpec(
                    f"upstream semantic key mismatch: {dependency.key}"
                )

    def _validate_source_dependencies(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        dataset_id: str,
        spec: WorkSpec,
    ) -> None:
        for dependency in spec.dependencies:
            if dependency.kind not in {
                DependencyKind.SOURCE_REVISION,
                DependencyKind.SOURCE_CONTENT,
            }:
                continue
            try:
                source_dataset, relative_path = json.loads(dependency.key)
            except (TypeError, ValueError) as error:
                raise InvalidWorkSpec(
                    "invalid source revision dependency key"
                ) from error
            if source_dataset != dataset_id or not isinstance(relative_path, str):
                raise InvalidWorkSpec(
                    "source revision dependency is outside the Working Run Dataset"
                )
            row = connection.execute(
                """
                SELECT source_revision FROM run_items
                WHERE run_id = ? AND relative_path = ?
                """,
                (run_id, relative_path),
            ).fetchone()
            if row is None or row["source_revision"] is None:
                raise InvalidWorkSpec(
                    f"source dependency is not accounted by this run: {relative_path}"
                )
            if dependency.kind is DependencyKind.SOURCE_REVISION:
                if str(row["source_revision"]) != dependency.value:
                    raise InvalidWorkSpec(
                        f"source revision is not accounted by this run: {relative_path}"
                    )
                continue
            try:
                proof_value = json.loads(dependency.value)
                reuse_domain = str(proof_value["reuse_domain"])
            except (KeyError, TypeError, ValueError) as error:
                raise InvalidWorkSpec(
                    "invalid source content dependency value"
                ) from error
            proof = connection.execute(
                """
                SELECT source_revision, proof_value
                FROM source_content_proofs
                WHERE dataset_id = ? AND relative_path = ? AND reuse_domain = ?
                """,
                (dataset_id, relative_path, reuse_domain),
            ).fetchone()
            if (
                proof is None
                or int(proof["source_revision"]) != int(row["source_revision"])
                or str(proof["proof_value"]) != dependency.value
            ):
                raise InvalidWorkSpec(
                    f"exact source content is not proven for this run: {relative_path}"
                )

    def _upstream_statuses(
        self,
        connection: sqlite3.Connection,
        dependencies: tuple[WorkDependency, ...],
    ) -> tuple[WorkStatus, ...]:
        statuses: list[WorkStatus] = []
        for dependency in dependencies:
            if dependency.kind is not DependencyKind.UPSTREAM_WORK:
                continue
            row = connection.execute(
                "SELECT status FROM work_records WHERE work_id = ?",
                (dependency.key,),
            ).fetchone()
            if row is None:
                raise InvalidWorkSpec(f"unknown upstream Work Record: {dependency.key}")
            statuses.append(WorkStatus(row["status"]))
        return tuple(statuses)

    def _recover_expired(
        self,
        connection: sqlite3.Connection,
        observed_at: str,
    ) -> list[str]:
        rows = connection.execute(
            """
            SELECT * FROM work_records
            WHERE status = ? AND lease_expires_at <= ?
            ORDER BY lease_expires_at, work_id
            """,
            (WorkStatus.RUNNING, observed_at),
        ).fetchall()
        recovered: list[str] = []
        for row in rows:
            can_retry = int(row["attempt_count"]) < int(row["max_attempts"])
            status = (
                WorkStatus.RETRYABLE_FAILURE
                if can_retry
                else WorkStatus.TERMINAL_FAILURE
            )
            connection.execute(
                """
                UPDATE work_attempts
                SET finished_at = ?, outcome = ?, retryable = ?,
                    error_code = ?, error_message = ?
                WHERE work_id = ? AND attempt_number = ?
                """,
                (
                    observed_at,
                    AttemptOutcome.LEASE_EXPIRED,
                    int(can_retry),
                    "lease_expired",
                    "worker lease expired before completion",
                    row["work_id"],
                    row["attempt_count"],
                ),
            )
            connection.execute(
                """
                UPDATE work_records
                SET status = ?, lease_run_id = NULL, lease_owner = NULL,
                    lease_token = NULL, lease_expires_at = NULL,
                    retry_not_before = ?, last_failure_code = ?,
                    last_failure_message = ?, updated_at = ?
                WHERE work_id = ?
                """,
                (
                    status,
                    observed_at if can_retry else None,
                    "lease_expired",
                    "worker lease expired before completion",
                    observed_at,
                    row["work_id"],
                ),
            )
            if status is WorkStatus.TERMINAL_FAILURE:
                self._block_dependents(connection, str(row["work_id"]), observed_at)
            recovered.append(str(row["work_id"]))
        return recovered

    def _promote_ready(
        self,
        connection: sqlite3.Connection,
        observed_at: str,
    ) -> None:
        rows = connection.execute(
            "SELECT work_id FROM work_records WHERE status = ?",
            (WorkStatus.PENDING,),
        ).fetchall()
        for row in rows:
            work_id = str(row["work_id"])
            statuses = self._upstream_statuses_for_work(connection, work_id)
            if any(status in _UNUSABLE_UPSTREAM for status in statuses):
                status = WorkStatus.BLOCKED
            elif all(status is WorkStatus.SUCCEEDED for status in statuses):
                status = WorkStatus.READY
            else:
                continue
            connection.execute(
                "UPDATE work_records SET status = ?, updated_at = ? WHERE work_id = ?",
                (status, observed_at, work_id),
            )

    def _promote_dependents(
        self,
        connection: sqlite3.Connection,
        work_id: str,
        observed_at: str,
    ) -> None:
        for dependent in self._dependent_ids(connection, work_id):
            statuses = self._upstream_statuses_for_work(connection, dependent)
            if statuses and all(status is WorkStatus.SUCCEEDED for status in statuses):
                connection.execute(
                    """
                    UPDATE work_records SET status = ?, updated_at = ?
                    WHERE work_id = ? AND status = ?
                    """,
                    (WorkStatus.READY, observed_at, dependent, WorkStatus.PENDING),
                )

    def _block_dependents(
        self,
        connection: sqlite3.Connection,
        work_id: str,
        observed_at: str,
    ) -> None:
        queue = deque(self._dependent_ids(connection, work_id))
        seen: set[str] = set()
        while queue:
            dependent = queue.popleft()
            if dependent in seen:
                continue
            seen.add(dependent)
            connection.execute(
                """
                UPDATE work_records
                SET status = ?, last_failure_code = ?,
                    last_failure_message = ?, updated_at = ?
                WHERE work_id = ? AND status IN (?, ?)
                """,
                (
                    WorkStatus.BLOCKED,
                    "upstream_terminal_failure",
                    f"upstream work {work_id} cannot produce a usable result",
                    observed_at,
                    dependent,
                    WorkStatus.PENDING,
                    WorkStatus.READY,
                ),
            )
            queue.extend(self._dependent_ids(connection, dependent))

    def _dependent_ids(
        self,
        connection: sqlite3.Connection,
        work_id: str,
    ) -> tuple[str, ...]:
        rows = connection.execute(
            """
            SELECT work_id FROM work_dependencies
            WHERE dependency_kind = ? AND dependency_key = ?
            ORDER BY work_id
            """,
            (DependencyKind.UPSTREAM_WORK, work_id),
        ).fetchall()
        return tuple(str(row["work_id"]) for row in rows)

    def _upstream_statuses_for_work(
        self,
        connection: sqlite3.Connection,
        work_id: str,
    ) -> tuple[WorkStatus, ...]:
        rows = connection.execute(
            """
            SELECT upstream.status
            FROM work_dependencies AS dependency
            JOIN work_records AS upstream
              ON upstream.work_id = dependency.dependency_key
            WHERE dependency.work_id = ? AND dependency.dependency_kind = ?
            """,
            (work_id, DependencyKind.UPSTREAM_WORK),
        ).fetchall()
        return tuple(WorkStatus(row["status"]) for row in rows)

    def _require_lease(
        self,
        connection: sqlite3.Connection,
        lease: WorkLease,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM work_records WHERE work_id = ?", (lease.work_id,)
        ).fetchone()
        if (
            row is None
            or row["status"] != WorkStatus.RUNNING
            or row["lease_token"] != lease.token
            or row["lease_run_id"] != lease.run_id
            or row["lease_owner"] != lease.owner
            or int(row["attempt_count"]) != lease.attempt_number
        ):
            raise LeaseLost(
                f"lease is no longer active for Work Record {lease.work_id}"
            )
        return row

    def _get_work(
        self,
        connection: sqlite3.Connection,
        work_id: str,
    ) -> WorkRecord:
        row = connection.execute(
            "SELECT * FROM work_records WHERE work_id = ?", (work_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown Work Record: {work_id}")
        dependencies = tuple(
            WorkDependency(
                kind=dependency["dependency_kind"],
                key=str(dependency["dependency_key"]),
                value=str(dependency["dependency_value"]),
            )
            for dependency in connection.execute(
                """
                SELECT dependency_kind, dependency_key, dependency_value
                FROM work_dependencies WHERE work_id = ?
                ORDER BY dependency_kind, dependency_key
                """,
                (work_id,),
            )
        )
        return WorkRecord(
            work_id=work_id,
            semantic_key=str(row["semantic_key"]),
            spec=WorkSpec(
                capability=str(row["capability"]),
                producer_identity=str(row["producer_identity"]),
                dependencies=dependencies,
            ),
            status=WorkStatus(row["status"]),
            max_attempts=int(row["max_attempts"]),
            attempt_count=int(row["attempt_count"]),
            lease_run_id=row["lease_run_id"],
            lease_owner=row["lease_owner"],
            lease_expires_at=_optional_datetime(row["lease_expires_at"]),
            retry_not_before=_optional_datetime(row["retry_not_before"]),
            checkpoint=row["checkpoint"],
            last_failure_code=row["last_failure_code"],
            last_failure_message=row["last_failure_message"],
            invalidation_reason=row["invalidation_reason"],
            output=None
            if row["output_json"] is None
            else json.loads(row["output_json"]),
            output_digest=row["output_digest"],
        )

    def _require_run(self, connection: sqlite3.Connection, run_id: str) -> None:
        if (
            connection.execute(
                "SELECT 1 FROM working_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            is None
        ):
            raise KeyError(f"unknown Working Run: {run_id}")

    def _require_run_ready(
        self,
        connection: sqlite3.Connection,
        run_id: str,
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT dataset_id, status FROM working_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown Working Run: {run_id}")
        if WorkingRunStatus(row["status"]) not in {
            WorkingRunStatus.COMPLETED,
            WorkingRunStatus.COMPLETED_WITH_ISSUES,
        }:
            raise InvalidWorkTransition(
                f"Working Run {run_id} has not completed source accounting"
            )
        return row

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with connect(self.database_path) as connection:
            yield connection

    @contextmanager
    def _transaction(
        self,
        *,
        immediate: bool,
    ) -> Iterator[sqlite3.Connection]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()


_UNUSABLE_UPSTREAM = {
    WorkStatus.TERMINAL_FAILURE,
    WorkStatus.BLOCKED,
    WorkStatus.INVALIDATED,
    WorkStatus.CANCELLED,
}


def _validated_rebuild_path(value: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError("manual rebuild source paths must stay relative")
    return path


def _work_source_paths(connection: sqlite3.Connection, work_id: str) -> set[str]:
    rows = connection.execute(
        """
        SELECT dependency_kind, dependency_key, dependency_value
        FROM work_dependencies WHERE work_id = ?
        """,
        (work_id,),
    ).fetchall()
    paths: set[str] = set()
    for row in rows:
        kind = DependencyKind(row["dependency_kind"])
        if (
            kind is DependencyKind.PARAMETER
            and row["dependency_key"] == "subject_relative_path"
        ):
            paths.add(str(row["dependency_value"]))
        elif kind in {DependencyKind.SOURCE_REVISION, DependencyKind.SOURCE_CONTENT}:
            _dataset_id, relative_path = json.loads(str(row["dependency_key"]))
            paths.add(str(relative_path))
    return paths


def _descriptor_json(spec: WorkSpec) -> str:
    return json.dumps(
        {
            "capability": spec.capability,
            "producer_identity": spec.producer_identity,
            "dependencies": [
                {
                    "kind": dependency.kind,
                    "key": dependency.key,
                    "value": dependency.value,
                }
                for dependency in spec.dependencies
            ],
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _semantic_key(descriptor: str) -> str:
    return "work-sha256-v1:" + hashlib.sha256(descriptor.encode("utf-8")).hexdigest()


def _output_json(output: object) -> str:
    try:
        value = json.dumps(
            output,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as error:
        raise ValueError("inline Work output must be valid JSON") from error
    if len(value.encode("utf-8")) > _MAX_INLINE_OUTPUT_BYTES:
        raise ValueError("inline Work output exceeds the 64 KiB limit")
    return value


def _utc(value: datetime | None) -> str:
    observed = datetime.now(timezone.utc) if value is None else value
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return _iso(observed.astimezone(timezone.utc))


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _as_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _optional_datetime(value: str | None) -> datetime | None:
    return None if value is None else _as_datetime(value)


def _attempt_from_row(row: sqlite3.Row) -> WorkAttempt:
    return WorkAttempt(
        work_id=str(row["work_id"]),
        attempt_number=int(row["attempt_number"]),
        run_id=str(row["run_id"]),
        lease_owner=str(row["lease_owner"]),
        lease_token=str(row["lease_token"]),
        started_at=_as_datetime(str(row["started_at"])),
        lease_expires_at=_as_datetime(str(row["lease_expires_at"])),
        finished_at=_optional_datetime(row["finished_at"]),
        outcome=AttemptOutcome(row["outcome"]),
        retryable=None if row["retryable"] is None else bool(row["retryable"]),
        error_code=row["error_code"],
        error_message=row["error_message"],
        checkpoint=row["checkpoint"],
    )
