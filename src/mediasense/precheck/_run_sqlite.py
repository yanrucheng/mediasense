"""Private durable state adapter for the public PreCheck Run lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Iterator
from uuid import uuid4

from mediasense.dataset_reference import dataset_ref_from_id

from ._working_schema import SCHEMA_VERSION


class RunIdempotencyConflict(ValueError):
    """A request ID was reused with different start inputs."""


class RunDecisionError(ValueError):
    """A lifecycle decision does not match the current durable boundary."""


class RunBindingError(ValueError):
    """A public Run cannot be bound to the requested accounting Run."""


class RunStateConflict(RuntimeError):
    """A requested transition is incompatible with the current state."""

    def __init__(self, record: dict[str, object]) -> None:
        self.record = record
        super().__init__(f"invalid transition from {record['state']}")


class RunExecutionConflict(ValueError):
    """A Run was asked to continue under different execution semantics."""


class SQLiteRunStore:
    def __init__(
        self,
        database_path: Path,
        *,
        sqlite_timeout: float = 30,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if sqlite_timeout < 0:
            raise ValueError("sqlite_timeout cannot be negative")
        self.database_path = Path(database_path)
        self.sqlite_timeout = sqlite_timeout
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._verify_schema()

    def start(
        self,
        request: dict[str, object],
        *,
        dataset_ref: str,
        prior_result_ref: str | None,
    ) -> tuple[dict[str, object], bool]:
        request_json = _json(request)
        request_id = str(request["request_id"])
        observed_at = self.now()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM precheck_runs WHERE request_id = ?", (request_id,)
            ).fetchone()
            if existing is not None:
                if str(existing["request_json"]) != request_json:
                    raise RunIdempotencyConflict(request_id)
                return _record(existing), False
            run_ref = f"precheck-run:{uuid4().hex}"
            connection.execute(
                """
                INSERT INTO precheck_runs (
                    run_ref, request_id, request_json, dataset_ref,
                    prior_result_ref, state, progress_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?)
                """,
                (
                    run_ref,
                    request_id,
                    request_json,
                    dataset_ref,
                    prior_result_ref,
                    _json(_unknown_progress()),
                    observed_at,
                    observed_at,
                ),
            )
            row = connection.execute(
                "SELECT * FROM precheck_runs WHERE run_ref = ?", (run_ref,)
            ).fetchone()
        assert row is not None
        return _record(row), True

    def replay_start(self, request: dict[str, object]) -> dict[str, object] | None:
        """Return an existing identical start before revalidating its upstream."""

        request_id = str(request["request_id"])
        request_json = _json(request)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM precheck_runs WHERE request_id = ?", (request_id,)
            ).fetchone()
        if row is None:
            return None
        if str(row["request_json"]) != request_json:
            raise RunIdempotencyConflict(request_id)
        return _record(row)

    def dataset_exists(self, dataset_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
        return row is not None

    def bind_accounting_run(
        self, run_ref: str, accounting_run_id: str
    ) -> dict[str, object]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            record = _record(row)
            accounting = connection.execute(
                "SELECT dataset_id FROM working_runs WHERE run_id = ?",
                (accounting_run_id,),
            ).fetchone()
            if accounting is None:
                raise RunBindingError("accounting Run does not exist")
            dataset_ref = dataset_ref_from_id(accounting["dataset_id"])
            if dataset_ref != record["dataset_ref"]:
                raise RunBindingError("accounting Run belongs to a different Dataset")
            current = record["accounting_run_id"]
            if current is not None and current != accounting_run_id:
                raise RunBindingError(
                    "public Run is already bound to another accounting Run"
                )
            if current is None:
                if record["state"] not in {"running", "paused", "blocked"}:
                    raise RunStateConflict(record)
                connection.execute(
                    """
                    UPDATE precheck_runs
                    SET accounting_run_id = ?, updated_at = ?
                    WHERE run_ref = ?
                    """,
                    (accounting_run_id, self.now(), run_ref),
                )
            return _record(self._require(connection, run_ref))

    def configure_execution(
        self,
        run_ref: str,
        configuration: dict[str, object],
    ) -> dict[str, object]:
        encoded = _json(configuration)
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            record = _record(row)
            existing = record["execution_config"]
            if existing is not None and existing != configuration:
                raise RunExecutionConflict(
                    "Run execution configuration is already fixed"
                )
            if existing is None:
                if record["state"] not in {"running", "paused", "blocked"}:
                    raise RunStateConflict(record)
                connection.execute(
                    """
                    UPDATE precheck_runs
                    SET execution_config_json = ?, updated_at = ?
                    WHERE run_ref = ?
                    """,
                    (encoded, self.now(), run_ref),
                )
            return _record(self._require(connection, run_ref))

    def set_execution_checkpoint(
        self,
        run_ref: str,
        checkpoint: str,
        *,
        complete: bool = False,
        total: int | str | None = None,
    ) -> None:
        if not checkpoint.strip():
            raise ValueError("execution checkpoint must be non-empty")
        if (
            total != "unknown"
            and total is not None
            and (not isinstance(total, int) or isinstance(total, bool) or total < 0)
        ):
            raise ValueError(
                "execution checkpoint total must be nonnegative or unknown"
            )
        with self._transaction() as connection:
            record = _record(self._require(connection, run_ref))
            if record["state"] not in {"running", "paused", "blocked"}:
                raise RunStateConflict(record)
            observed_at = self.now()
            previous = record["execution_checkpoint"]
            assert isinstance(previous, dict)
            previous_phase = previous["phase"]
            if total is None:
                total = previous["total"] if previous_phase == checkpoint else "unknown"
            value = {
                "version": 1,
                "phase": checkpoint,
                "complete": complete,
                "total": total,
                "last_progress_at": (
                    previous["last_progress_at"]
                    if previous_phase == checkpoint
                    and previous["complete"] == complete
                    and previous["total"] == total
                    else observed_at
                ),
                "worker": previous["worker"],
            }
            self._write_execution_checkpoint(
                connection, run_ref, value, observed_at=observed_at
            )

    def claim_execution_worker(
        self,
        run_ref: str,
        worker_token: str,
        *,
        stale_after: timedelta,
    ) -> bool:
        """Claim one Run worker unless another current heartbeat still owns it."""

        if not worker_token.strip():
            raise ValueError("worker token must be non-empty")
        if stale_after <= timedelta(0):
            raise ValueError("worker stale interval must be positive")
        with self._transaction() as connection:
            record = _record(self._require(connection, run_ref))
            if record["state"] != "running":
                return False
            observed_at = self.now()
            checkpoint = record["execution_checkpoint"]
            assert isinstance(checkpoint, dict)
            worker = checkpoint["worker"]
            if isinstance(worker, dict) and worker.get("token") != worker_token:
                heartbeat_at = _as_datetime(str(worker["heartbeat_at"]))
                if _as_datetime(observed_at) - heartbeat_at <= stale_after:
                    return False
            checkpoint["worker"] = {
                "token": worker_token,
                "heartbeat_at": observed_at,
            }
            self._write_execution_checkpoint(
                connection, run_ref, checkpoint, observed_at=observed_at
            )
        return True

    def heartbeat_execution_worker(self, run_ref: str, worker_token: str) -> bool:
        """Refresh one owned worker heartbeat without claiming execution progress."""

        with self._transaction() as connection:
            record = _record(self._require(connection, run_ref))
            if record["state"] != "running":
                return False
            checkpoint = record["execution_checkpoint"]
            assert isinstance(checkpoint, dict)
            worker = checkpoint["worker"]
            if not isinstance(worker, dict) or worker.get("token") != worker_token:
                return False
            observed_at = self.now()
            worker["heartbeat_at"] = observed_at
            self._write_execution_checkpoint(
                connection, run_ref, checkpoint, observed_at=observed_at
            )
        return True

    def release_execution_worker(self, run_ref: str, worker_token: str) -> None:
        """Release only the caller's worker ownership, preserving Run progress."""

        with self._transaction() as connection:
            record = _record(self._require(connection, run_ref))
            checkpoint = record["execution_checkpoint"]
            assert isinstance(checkpoint, dict)
            worker = checkpoint["worker"]
            if not isinstance(worker, dict) or worker.get("token") != worker_token:
                return
            checkpoint["worker"] = None
            self._write_execution_checkpoint(
                connection, run_ref, checkpoint, observed_at=self.now()
            )

    def stop_unstarted_execution(
        self,
        run_ref: str,
        *,
        target_state: str,
        reason: dict[str, object],
        worker_token: str | None = None,
    ) -> dict[str, object]:
        """Atomically stop a Run before a claimed worker starts."""

        if target_state not in {"blocked", "failed"}:
            raise ValueError("unstarted execution may stop only as blocked or failed")

        with self._transaction() as connection:
            observed = _record(self._require(connection, run_ref))
            if observed["state"] == target_state:
                return observed
            if observed["state"] != "running":
                raise RunStateConflict(observed)
            checkpoint = observed["execution_checkpoint"]
            assert isinstance(checkpoint, dict)
            worker = checkpoint["worker"]
            if worker_token is None:
                if worker is not None:
                    raise RunExecutionConflict(
                        "unstarted execution already has a worker owner"
                    )
            elif not isinstance(worker, dict) or worker.get("token") != worker_token:
                raise RunExecutionConflict(
                    "unstarted execution is not owned by the expected worker"
                )
            observed_at = self.now()
            if worker is not None:
                checkpoint["worker"] = None
                self._write_execution_checkpoint(
                    connection,
                    run_ref,
                    checkpoint,
                    observed_at=observed_at,
                )
            accounting_run_id = observed["accounting_run_id"]
            if isinstance(accounting_run_id, str):
                connection.execute(
                    """
                    UPDATE working_runs
                    SET status = 'paused', blocked_reason = NULL, updated_at = ?
                    WHERE run_id = ? AND status = 'running'
                    """,
                    (observed_at, accounting_run_id),
                )
            return self._update_state(
                connection,
                run_ref,
                target_state,
                reason=reason,
            )

    def execution_facts(self, accounting_run_id: str | None) -> dict[str, object]:
        """Read bounded aggregate facts used by the public activity projection."""

        if accounting_run_id is None:
            return {"accounting": None, "work": ()}
        with self._connect() as connection:
            accounting = connection.execute(
                "SELECT status, updated_at FROM working_runs WHERE run_id = ?",
                (accounting_run_id,),
            ).fetchone()
            if accounting is None:
                raise RunBindingError("bound accounting Run does not exist")
            accounting_counts = connection.execute(
                """
                SELECT change_kind, COUNT(*) AS count
                FROM run_items WHERE run_id = ? GROUP BY change_kind
                """,
                (accounting_run_id,),
            ).fetchall()
            work_rows = connection.execute(
                """
                SELECT work_records.capability, work_records.status,
                       CASE WHEN EXISTS (
                           SELECT 1 FROM work_attempts
                           WHERE work_attempts.work_id = work_records.work_id
                             AND work_attempts.run_id = run_work_records.run_id
                       ) THEN 1 ELSE 0 END AS attempted_here,
                       COUNT(*) AS count,
                       MAX(CASE WHEN EXISTS (
                           SELECT 1 FROM work_attempts
                           WHERE work_attempts.work_id = work_records.work_id
                             AND work_attempts.run_id = run_work_records.run_id
                       ) THEN work_records.updated_at
                       ELSE run_work_records.requested_at END) AS last_progress_at
                FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                GROUP BY work_records.capability, work_records.status, attempted_here
                ORDER BY work_records.capability, work_records.status, attempted_here
                """,
                (accounting_run_id,),
            ).fetchall()
        return {
            "accounting": {
                "state": str(accounting["status"]),
                "last_progress_at": str(accounting["updated_at"]),
                "counts": {
                    str(row["change_kind"]): int(row["count"])
                    for row in accounting_counts
                },
            },
            "work": tuple(
                {
                    "capability": str(row["capability"]),
                    "status": str(row["status"]),
                    "attempted_here": bool(row["attempted_here"]),
                    "count": int(row["count"]),
                    "last_progress_at": str(row["last_progress_at"]),
                }
                for row in work_rows
            ),
        }

    def now(self) -> str:
        observed = self._clock()
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("Run clock must return a timezone-aware datetime")
        return observed.astimezone(timezone.utc).isoformat(timespec="microseconds")

    @staticmethod
    def _write_execution_checkpoint(
        connection: sqlite3.Connection,
        run_ref: str,
        checkpoint: dict[str, object],
        *,
        observed_at: str,
    ) -> None:
        connection.execute(
            """
            UPDATE precheck_runs
            SET execution_checkpoint = ?, updated_at = ?
            WHERE run_ref = ?
            """,
            (_json(checkpoint), observed_at, run_ref),
        )

    def unfinished_accounting_run(self, dataset_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id FROM working_runs
                WHERE dataset_id = ?
                  AND status IN ('running', 'paused', 'blocked')
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (dataset_id,),
            ).fetchone()
        return None if row is None else str(row["run_id"])

    def accounting_progress(
        self, run_ref: str
    ) -> tuple[dict[str, object], str, str | None]:
        with self._connect() as connection:
            run = self._require(connection, run_ref)
            accounting_run_id = run["accounting_run_id"]
            if accounting_run_id is None:
                raise RunBindingError("public Run has no accounting Run")
            accounting = connection.execute(
                "SELECT status, blocked_reason FROM working_runs WHERE run_id = ?",
                (accounting_run_id,),
            ).fetchone()
            if accounting is None:
                raise RunBindingError("bound accounting Run does not exist")
            rows = connection.execute(
                """
                SELECT condition, COUNT(*) AS count
                FROM run_items WHERE run_id = ? GROUP BY condition
                """,
                (accounting_run_id,),
            ).fetchall()
        counts = {str(row["condition"]): int(row["count"]) for row in rows}
        accounted = sum(counts.values())
        return (
            {
                "discovered": accounted,
                "accounted": accounted,
                "usable": counts.get("usable", 0),
                "exceptional": sum(
                    counts.get(condition, 0)
                    for condition in ("unsupported", "invalid", "error")
                ),
                "unresolved": counts.get("unresolved", 0),
            },
            str(accounting["status"]),
            accounting["blocked_reason"],
        )

    def get(self, run_ref: str) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM precheck_runs WHERE run_ref = ?", (run_ref,)
            ).fetchone()
        if row is None:
            raise KeyError(run_ref)
        return _record(row)

    def ensure_scope_review(
        self,
        run_ref: str,
        *,
        accounting_run_id: str,
        scan_generation: int,
        inventory_fingerprint: str,
        summary: Mapping[str, object],
    ) -> tuple[dict[str, object], dict[str, object] | None]:
        """Reuse, retain, or pause for one exact factual source inventory."""

        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            record = _record(row)
            latest = connection.execute(
                """
                SELECT * FROM precheck_scope_reviews
                WHERE run_ref = ? ORDER BY revision DESC LIMIT 1
                """,
                (run_ref,),
            ).fetchone()
            if (
                latest is not None
                and latest["inventory_fingerprint"] == inventory_fingerprint
                and latest["state"] in {"accepted", "reused"}
            ):
                return record, json.loads(str(latest["selection_json"]))
            if (
                latest is not None
                and latest["inventory_fingerprint"] == inventory_fingerprint
                and latest["state"] == "pending"
            ):
                return record, None
            if latest is not None and latest["state"] in {
                "pending",
                "accepted",
                "reused",
            }:
                connection.execute(
                    """
                    UPDATE precheck_scope_reviews SET state = 'stale'
                    WHERE run_ref = ? AND revision = ?
                    """,
                    (run_ref, latest["revision"]),
                )

            revision = 1 if latest is None else int(latest["revision"]) + 1
            reusable = connection.execute(
                """
                SELECT review.run_ref, review.selection_json
                FROM precheck_scope_reviews AS review
                JOIN precheck_runs AS prior ON prior.run_ref = review.run_ref
                WHERE prior.dataset_ref = ?
                  AND prior.state = 'completed'
                  AND review.inventory_fingerprint = ?
                  AND review.state IN ('accepted', 'reused')
                  AND review.selection_json IS NOT NULL
                  AND review.run_ref <> ?
                ORDER BY review.decided_at DESC, review.created_at DESC
                LIMIT 1
                """,
                (record["dataset_ref"], inventory_fingerprint, run_ref),
            ).fetchone()
            observed_at = self.now()
            if reusable is not None:
                selection_json = str(reusable["selection_json"])
                connection.execute(
                    """
                    INSERT INTO precheck_scope_reviews (
                        run_ref, revision, accounting_run_id, scan_generation,
                        inventory_fingerprint, summary_json, state,
                        selection_json, reused_from_run_ref, created_at, decided_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'reused', ?, ?, ?, ?)
                    """,
                    (
                        run_ref,
                        revision,
                        accounting_run_id,
                        scan_generation,
                        inventory_fingerprint,
                        _json(summary),
                        selection_json,
                        str(reusable["run_ref"]),
                        observed_at,
                        observed_at,
                    ),
                )
                return record, json.loads(selection_json)

            confirmation = {
                "kind": "source_scope",
                "summary": "Review the discovered source tree before expensive work.",
                "inventory_fingerprint": inventory_fingerprint,
                "scan_generation": scan_generation,
                "inventory": dict(summary),
            }
            connection.execute(
                """
                INSERT INTO precheck_scope_reviews (
                    run_ref, revision, accounting_run_id, scan_generation,
                    inventory_fingerprint, summary_json, state, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    run_ref,
                    revision,
                    accounting_run_id,
                    scan_generation,
                    inventory_fingerprint,
                    _json(summary),
                    observed_at,
                ),
            )
            current = self._update_state(
                connection,
                run_ref,
                "paused",
                reason={
                    "code": "scope_confirmation_required",
                    "message": "The discovered source tree requires a scope selection.",
                    "resume_when": (
                        "The caller supplies an include/exclude selection for "
                        "this exact inventory."
                    ),
                },
                confirmation=confirmation,
                confirmation_fingerprint=inventory_fingerprint,
            )
        return current, None

    def latest_scope_review(self, run_ref: str) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM precheck_scope_reviews
                WHERE run_ref = ? ORDER BY revision DESC LIMIT 1
                """,
                (run_ref,),
            ).fetchone()
        return None if row is None else _scope_review_record(row)

    def request_pause(
        self, run_ref: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if observed["state"] == "paused":
                return observed, observed
            if observed["state"] != "running":
                raise RunStateConflict(observed)
            current = self._update_state(
                connection,
                run_ref,
                "paused",
                reason={
                    "code": "user_requested",
                    "message": "The caller requested a durable pause.",
                    "resume_when": "The caller chooses to continue this Run.",
                },
            )
        return observed, current

    def request_resume(
        self,
        run_ref: str,
        *,
        decision: object,
    ) -> tuple[dict[str, object], dict[str, object]]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            state = str(observed["state"])
            confirmation = observed["confirmation"]
            if state == "running":
                if isinstance(decision, dict):
                    latest = connection.execute(
                        """
                        SELECT selection_json FROM precheck_scope_reviews
                        WHERE run_ref = ? AND state IN ('accepted', 'reused')
                        ORDER BY revision DESC LIMIT 1
                        """,
                        (run_ref,),
                    ).fetchone()
                    if (
                        latest is None
                        or json.loads(str(latest["selection_json"])) != decision
                    ):
                        raise RunDecisionError(
                            "this running Run has no matching scope decision"
                        )
                    return observed, observed
                previous_decision = observed["confirmation_decision"]
                if decision is not None and decision != previous_decision:
                    raise RunDecisionError(
                        "this running Run has no matching confirmation decision"
                    )
                return observed, observed
            if state not in {"paused", "blocked"}:
                raise RunStateConflict(observed)
            if confirmation is not None:
                if decision is None:
                    raise RunDecisionError(
                        "resume requires a decision for the pending confirmation"
                    )
                if not isinstance(confirmation, dict):
                    raise RunDecisionError("pending confirmation is invalid")
                if confirmation.get("kind") == "source_scope":
                    if not isinstance(decision, dict):
                        raise RunDecisionError(
                            "scope confirmation requires a source-scope decision"
                        )
                    fingerprint = str(observed["confirmation_fingerprint"])
                    if decision.get("inventory_fingerprint") != fingerprint:
                        raise RunDecisionError(
                            "source-scope decision names a stale inventory"
                        )
                    pending = connection.execute(
                        """
                        SELECT revision FROM precheck_scope_reviews
                        WHERE run_ref = ? AND inventory_fingerprint = ?
                          AND state = 'pending'
                        ORDER BY revision DESC LIMIT 1
                        """,
                        (run_ref, fingerprint),
                    ).fetchone()
                    if pending is None:
                        raise RunDecisionError("scope review is no longer pending")
                    connection.execute(
                        """
                        UPDATE precheck_scope_reviews
                        SET state = 'accepted', selection_json = ?, decided_at = ?
                        WHERE run_ref = ? AND revision = ?
                        """,
                        (_json(decision), self.now(), run_ref, pending["revision"]),
                    )
                    generic_decision = None
                else:
                    if not isinstance(decision, str) or decision not in {
                        "proceed",
                        "skip_optional_work",
                    }:
                        raise RunDecisionError("unknown confirmation decision")
                    if decision == "skip_optional_work" and not bool(
                        confirmation["skip_allowed"]
                    ):
                        raise RunDecisionError(
                            "the pending optional work cannot be skipped"
                        )
                    fingerprint = str(observed["confirmation_fingerprint"])
                    generic_decision = str(decision)
            else:
                if decision is not None:
                    raise RunDecisionError(
                        "resume decision is valid only for a confirmation pause"
                    )
                fingerprint = None
                generic_decision = None
            current = self._update_state(
                connection,
                run_ref,
                "running",
                confirmation_fingerprint=fingerprint,
                confirmation_decision=generic_decision,
            )
        return observed, current

    def request_cancel(
        self, run_ref: str
    ) -> tuple[dict[str, object], dict[str, object]]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if observed["state"] == "cancelled":
                return observed, observed
            if observed["state"] not in {"running", "paused", "blocked"}:
                raise RunStateConflict(observed)
            current = self._update_state(connection, run_ref, "cancelled")
        return observed, current

    def pause_for_confirmation(
        self,
        run_ref: str,
        *,
        confirmation: dict[str, object],
        fingerprint: str,
    ) -> tuple[dict[str, object], bool]:
        """Pause for an exact frozen work set unless it is already authorized."""

        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if (
                observed["state"] == "running"
                and observed["confirmation_fingerprint"] == fingerprint
                and observed["confirmation_decision"]
                in {"proceed", "skip_optional_work"}
            ):
                return observed, False
            if observed["state"] == "paused" and observed["confirmation"] is not None:
                if observed["confirmation_fingerprint"] != fingerprint:
                    raise RunStateConflict(observed)
                if _json(observed["confirmation"]) != _json(confirmation):
                    raise RunDecisionError(
                        "confirmation fingerprint identifies different work"
                    )
                return observed, True
            if observed["state"] not in {"running", "paused", "blocked"}:
                raise RunStateConflict(observed)
            current = self._update_state(
                connection,
                run_ref,
                "paused",
                reason={
                    "code": "confirmation_required",
                    "message": (
                        f"{confirmation['quantity']} {confirmation['unit']} "
                        "require confirmation."
                    ),
                    "resume_when": (
                        "The caller chooses proceed"
                        + (
                            " or skip_optional_work."
                            if confirmation["skip_allowed"]
                            else "."
                        )
                    ),
                },
                confirmation=confirmation,
                confirmation_fingerprint=fingerprint,
            )
        return current, True

    def mark_blocked(
        self, run_ref: str, reason: dict[str, object]
    ) -> dict[str, object]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if observed["state"] not in {"running", "blocked"}:
                raise RunStateConflict(observed)
            return self._update_state(connection, run_ref, "blocked", reason=reason)

    def mark_interrupted(
        self, run_ref: str, *, message: str | None = None
    ) -> dict[str, object]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if observed["state"] == "paused":
                return observed
            if observed["state"] != "running":
                raise RunStateConflict(observed)
            return self._update_state(
                connection,
                run_ref,
                "paused",
                reason={
                    "code": "process_interrupted",
                    "message": message
                    or "The worker stopped before this Run completed.",
                    "resume_when": "A worker is available to resume this Run.",
                },
            )

    def mark_failed(self, run_ref: str, reason: dict[str, object]) -> dict[str, object]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if observed["state"] == "failed":
                return observed
            if observed["state"] in {"completed", "cancelled"}:
                raise RunStateConflict(observed)
            return self._update_state(connection, run_ref, "failed", reason=reason)

    def set_progress(
        self, run_ref: str, progress: dict[str, object]
    ) -> dict[str, object]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if observed["state"] not in {"running", "paused", "blocked"}:
                raise RunStateConflict(observed)
            connection.execute(
                """
                UPDATE precheck_runs SET progress_json = ?, updated_at = ?
                WHERE run_ref = ?
                """,
                (_json(progress), self.now(), run_ref),
            )
            row = self._require(connection, run_ref)
        return _record(row)

    def set_completed(
        self, run_ref: str, published_result: dict[str, object]
    ) -> dict[str, object]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            if observed["state"] == "completed":
                if observed["published_result"] != published_result:
                    raise RunStateConflict(observed)
                return observed
            if observed["state"] != "running":
                raise RunStateConflict(observed)
            connection.execute(
                """
                UPDATE precheck_runs
                SET state = 'completed', published_result_json = ?,
                    reason_json = NULL, confirmation_json = NULL,
                    confirmation_fingerprint = NULL, updated_at = ?
                WHERE run_ref = ?
                """,
                (_json(published_result), self.now(), run_ref),
            )
            row = self._require(connection, run_ref)
        return _record(row)

    def _update_state(
        self,
        connection: sqlite3.Connection,
        run_ref: str,
        state: str,
        *,
        reason: dict[str, object] | None = None,
        confirmation: dict[str, object] | None = None,
        confirmation_fingerprint: str | None = None,
        confirmation_decision: str | None = None,
    ) -> dict[str, object]:
        connection.execute(
            """
            UPDATE precheck_runs
            SET state = ?, reason_json = ?, confirmation_json = ?,
                confirmation_fingerprint = ?, confirmation_decision = ?,
                updated_at = ?
            WHERE run_ref = ?
            """,
            (
                state,
                None if reason is None else _json(reason),
                None if confirmation is None else _json(confirmation),
                confirmation_fingerprint,
                confirmation_decision,
                self.now(),
                run_ref,
            ),
        )
        return _record(self._require(connection, run_ref))

    def _require(self, connection: sqlite3.Connection, run_ref: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM precheck_runs WHERE run_ref = ?", (run_ref,)
        ).fetchone()
        if row is None:
            raise KeyError(run_ref)
        return row

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
            except sqlite3.OperationalError as error:
                raise RuntimeError(
                    "initialize the PreCheck store before creating the Run Tool"
                ) from error
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported or uninitialized internal schema")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=self.sqlite_timeout)
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


def _record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "run_ref": str(row["run_ref"]),
        "request_id": str(row["request_id"]),
        "dataset_ref": str(row["dataset_ref"]),
        "prior_result_ref": row["prior_result_ref"],
        "state": str(row["state"]),
        "progress": json.loads(str(row["progress_json"])),
        "reason": _optional_json(row["reason_json"]),
        "confirmation": _optional_json(row["confirmation_json"]),
        "confirmation_fingerprint": row["confirmation_fingerprint"],
        "confirmation_decision": row["confirmation_decision"],
        "published_result": _optional_json(row["published_result_json"]),
        "accounting_run_id": row["accounting_run_id"],
        "execution_config": _optional_json(row["execution_config_json"]),
        "execution_checkpoint": _execution_checkpoint(
            row["execution_checkpoint"], fallback_at=str(row["created_at"])
        ),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def _scope_review_record(row: sqlite3.Row) -> dict[str, object]:
    return {
        "run_ref": str(row["run_ref"]),
        "revision": int(row["revision"]),
        "accounting_run_id": str(row["accounting_run_id"]),
        "scan_generation": int(row["scan_generation"]),
        "inventory_fingerprint": str(row["inventory_fingerprint"]),
        "summary": json.loads(str(row["summary_json"])),
        "state": str(row["state"]),
        "selection": _optional_json(row["selection_json"]),
        "reused_from_run_ref": row["reused_from_run_ref"],
        "created_at": str(row["created_at"]),
        "decided_at": row["decided_at"],
    }


def _optional_json(value: str | None) -> object | None:
    return None if value is None else json.loads(value)


def _unknown_progress() -> dict[str, str]:
    return {
        "discovered": "unknown",
        "accounted": "unknown",
        "usable": "unknown",
        "exceptional": "unknown",
        "unresolved": "unknown",
    }


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _execution_checkpoint(value: object, *, fallback_at: str) -> dict[str, object]:
    if isinstance(value, dict):
        decoded = value
    elif isinstance(value, str):
        try:
            candidate = json.loads(value)
        except json.JSONDecodeError:
            candidate = None
        if isinstance(candidate, dict):
            decoded = candidate
        else:
            complete = value.endswith(":complete")
            decoded = {
                "phase": value.removesuffix(":complete"),
                "complete": complete,
                "total": "unknown",
                "last_progress_at": "unknown",
                "worker": None,
            }
    else:
        decoded = {
            "phase": "unknown",
            "complete": False,
            "total": "unknown",
            "last_progress_at": fallback_at,
            "worker": None,
        }
    return {
        "version": 1,
        "phase": str(decoded.get("phase", "unknown")),
        "complete": bool(decoded.get("complete", False)),
        "total": decoded.get("total", "unknown"),
        "last_progress_at": str(decoded.get("last_progress_at", fallback_at)),
        "worker": decoded.get("worker"),
    }


def _as_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("persisted Run timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "RunBindingError",
    "RunDecisionError",
    "RunIdempotencyConflict",
    "RunStateConflict",
    "SQLiteRunStore",
]
