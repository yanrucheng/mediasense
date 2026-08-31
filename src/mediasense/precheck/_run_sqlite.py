"""Private durable state adapter for the public PreCheck Run lifecycle."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
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
    def __init__(self, database_path: Path, *, sqlite_timeout: float = 30) -> None:
        if sqlite_timeout < 0:
            raise ValueError("sqlite_timeout cannot be negative")
        self.database_path = Path(database_path)
        self.sqlite_timeout = sqlite_timeout
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
        observed_at = _now()
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
                    (accounting_run_id, _now(), run_ref),
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
                    (encoded, _now(), run_ref),
                )
            return _record(self._require(connection, run_ref))

    def set_execution_checkpoint(self, run_ref: str, checkpoint: str) -> None:
        if not checkpoint.strip():
            raise ValueError("execution checkpoint must be non-empty")
        with self._transaction() as connection:
            record = _record(self._require(connection, run_ref))
            if record["state"] not in {"running", "paused", "blocked"}:
                raise RunStateConflict(record)
            connection.execute(
                """
                UPDATE precheck_runs
                SET execution_checkpoint = ?, updated_at = ?
                WHERE run_ref = ?
                """,
                (checkpoint, _now(), run_ref),
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
        decision: str | None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        with self._transaction() as connection:
            row = self._require(connection, run_ref)
            observed = _record(row)
            state = str(observed["state"])
            confirmation = observed["confirmation"]
            if state == "running":
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
                if decision not in {"proceed", "skip_optional_work"}:
                    raise RunDecisionError("unknown confirmation decision")
                if decision == "skip_optional_work" and not bool(
                    confirmation["skip_allowed"]
                ):
                    raise RunDecisionError(
                        "the pending optional work cannot be skipped"
                    )
                fingerprint = str(observed["confirmation_fingerprint"])
            else:
                if decision is not None:
                    raise RunDecisionError(
                        "resume decision is valid only for a confirmation pause"
                    )
                fingerprint = None
            current = self._update_state(
                connection,
                run_ref,
                "running",
                confirmation_fingerprint=fingerprint,
                confirmation_decision=decision,
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
                (_json(progress), _now(), run_ref),
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
                (_json(published_result), _now(), run_ref),
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
                _now(),
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
        "execution_checkpoint": row["execution_checkpoint"],
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


__all__ = [
    "RunBindingError",
    "RunDecisionError",
    "RunIdempotencyConflict",
    "RunStateConflict",
    "SQLiteRunStore",
]
