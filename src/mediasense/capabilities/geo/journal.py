"""Minimal durable journal for Geo Tool effect idempotency."""

from __future__ import annotations

import json
import hashlib
import fcntl
from contextlib import contextmanager
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 2


class GeoIdempotencyConflict(RuntimeError):
    """A request ID was reused with different effective input or authority."""


class GeoBudgetExhausted(RuntimeError):
    """No new effect fits in the persisted cumulative envelope."""


@dataclass(frozen=True, slots=True)
class GeoJournalEntry:
    request_id: str
    request_fingerprint: str
    authorization_binding: str
    state: str
    result: dict[str, Any]


class GeoOperationJournal:
    """Record admitted effects without becoming a geographic observation cache."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            journal_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'geo_operation_journal'"
            ).fetchone()
            schema_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' "
                "AND name = 'internal_schema'"
            ).fetchone()
            if schema_exists is not None:
                version = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
                if version is None or version[0] not in {1, _SCHEMA_VERSION}:
                    raise RuntimeError("unsupported Geo journal schema version")
            if journal_exists is not None and schema_exists is None:
                raise RuntimeError("unsupported unversioned Geo journal")
            connection.executescript(
                """
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS internal_schema (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    version INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO internal_schema (singleton, version)
                VALUES (1, 1);

                CREATE TABLE IF NOT EXISTS geo_operation_journal (
                    request_id TEXT PRIMARY KEY,
                    request_fingerprint TEXT NOT NULL,
                    authorization_binding TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('indeterminate', 'completed')),
                    result_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS geo_execution_cycles (
                    request_id TEXT PRIMARY KEY REFERENCES geo_operation_journal(request_id),
                    root_request_id TEXT NOT NULL,
                    prior_request_id TEXT UNIQUE,
                    request_json TEXT NOT NULL,
                    authority_json TEXT NOT NULL,
                    max_requests INTEGER NOT NULL CHECK(max_requests >= 0),
                    max_billable_units INTEGER,
                    baseline_requests INTEGER NOT NULL CHECK(baseline_requests >= 0),
                    baseline_billable_units INTEGER,
                    owner_pid INTEGER NOT NULL,
                    closed INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS geo_provider_executions (
                    request_id TEXT NOT NULL REFERENCES geo_execution_cycles(request_id),
                    sequence INTEGER NOT NULL,
                    reserved_requests INTEGER NOT NULL CHECK(reserved_requests >= 0),
                    reserved_billable_units INTEGER,
                    descriptor_json TEXT NOT NULL,
                    execution_json TEXT,
                    PRIMARY KEY(request_id, sequence)
                );
                CREATE TRIGGER IF NOT EXISTS geo_writer_insert_guard
                BEFORE INSERT ON geo_operation_journal BEGIN
                    SELECT CASE WHEN mediasense_geo_schema_version() != 2
                    THEN RAISE(ABORT, 'Geo writer schema mismatch') END;
                END;
                CREATE TRIGGER IF NOT EXISTS geo_writer_update_guard
                BEFORE UPDATE ON geo_operation_journal BEGIN
                    SELECT CASE WHEN mediasense_geo_schema_version() != 2
                    THEN RAISE(ABORT, 'Geo writer schema mismatch') END;
                END;
                UPDATE internal_schema SET version = 2 WHERE singleton = 1;
                COMMIT;
                """
            )
            version = connection.execute(
                "SELECT version FROM internal_schema WHERE singleton = 1"
            ).fetchone()
            if version is None or int(version["version"]) != _SCHEMA_VERSION:
                raise RuntimeError("unsupported Geo journal schema version")

    @contextmanager
    def ownership(self, request_id: str):
        """An OS lock proves execution ownership and is released on process death."""
        directory = self.database_path.parent / (self.database_path.name + ".owners")
        directory.mkdir(exist_ok=True)
        path = directory / hashlib.sha256(request_id.encode()).hexdigest()
        with path.open("a+b") as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def admit(
        self,
        *,
        request_id: str,
        request_fingerprint: str,
        authorization_binding: str,
        indeterminate_result: dict[str, Any],
        execution: dict[str, Any] | None = None,
    ) -> GeoJournalEntry | None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT request_id, request_fingerprint, authorization_binding,
                       state, result_json
                FROM geo_operation_journal
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
            if row is not None:
                entry = _entry(row)
                if (
                    entry.request_fingerprint != request_fingerprint
                    or entry.authorization_binding != authorization_binding
                ):
                    raise GeoIdempotencyConflict(
                        "request_id was already used with different input or authority"
                    )
                return entry
            if connection.execute(
                "SELECT 1 FROM geo_operation_journal WHERE authorization_binding = ? LIMIT 1",
                (authorization_binding,),
            ).fetchone():
                raise GeoIdempotencyConflict(
                    "This accepted authorization already belongs to a different request; changing request_id cannot allocate another budget"
                )
            if execution is not None and execution.get("prior_request_id"):
                prior_id = execution["prior_request_id"]
                prior = connection.execute(
                    "SELECT * FROM geo_execution_cycles WHERE request_id = ?",
                    (prior_id,),
                ).fetchone()
                if prior is None or not prior["closed"]:
                    raise GeoIdempotencyConflict(
                        "Prior Geo execution must be closed before recovery"
                    )
                if connection.execute(
                    "SELECT 1 FROM geo_execution_cycles WHERE prior_request_id = ?",
                    (prior_id,),
                ).fetchone():
                    raise GeoIdempotencyConflict(
                        "Prior Geo execution already has a recovery"
                    )
                if execution["root_request_id"] != prior["root_request_id"]:
                    raise GeoIdempotencyConflict(
                        "Recovery root does not match prior execution"
                    )
                if _json(execution["request"]) != prior["request_json"]:
                    raise GeoIdempotencyConflict(
                        "Recovery cannot change original query scope"
                    )
                root = connection.execute(
                    "SELECT * FROM geo_execution_cycles WHERE request_id = ?",
                    (prior["root_request_id"],),
                ).fetchone()
                if (
                    execution["max_requests"] != root["max_requests"]
                    or execution.get("max_billable_units") != root["max_billable_units"]
                ):
                    raise GeoIdempotencyConflict(
                        "Recovery cannot reset the cumulative ceiling"
                    )
            connection.execute(
                """
                INSERT INTO geo_operation_journal (
                    request_id, request_fingerprint, authorization_binding,
                    state, result_json
                ) VALUES (?, ?, ?, 'indeterminate', ?)
                """,
                (
                    request_id,
                    request_fingerprint,
                    authorization_binding,
                    _json(indeterminate_result),
                ),
            )
            if execution is not None:
                import os

                connection.execute(
                    """INSERT INTO geo_execution_cycles
                    (request_id, root_request_id, prior_request_id, request_json,
                     authority_json, max_requests, max_billable_units,
                     baseline_requests, baseline_billable_units, owner_pid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        request_id,
                        execution.get("root_request_id", request_id),
                        execution.get("prior_request_id"),
                        _json(execution["request"]),
                        _json(execution["authority"]),
                        execution["max_requests"],
                        execution.get("max_billable_units"),
                        execution.get("baseline_requests", 0),
                        execution.get("baseline_billable_units", 0),
                        os.getpid(),
                    ),
                )
        return None

    def complete(self, request_id: str, result: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            prior = connection.execute(
                "SELECT state, result_json FROM geo_operation_journal WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if prior and prior["state"] == "completed":
                if prior["result_json"] != _json(result):
                    raise GeoIdempotencyConflict("Completed Geo result is immutable")
                return
            updated = connection.execute(
                """
                UPDATE geo_operation_journal
                SET state = 'completed', result_json = ?
                WHERE request_id = ?
                """,
                (_json(result), request_id),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Geo operation was not admitted")
            connection.execute(
                "UPDATE geo_execution_cycles SET closed = 1 WHERE request_id = ?",
                (request_id,),
            )

    def reserve(
        self,
        request_id: str,
        *,
        descriptor: dict[str, Any],
        requests: int,
        billable_units: int | None,
    ) -> int:
        """Reserve before each external operation, including across recovery IDs."""
        if requests < 1 or (billable_units is not None and billable_units < 0):
            raise ValueError("invalid effect reservation")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cycle = connection.execute(
                "SELECT * FROM geo_execution_cycles WHERE request_id = ?", (request_id,)
            ).fetchone()
            if cycle is None or cycle["closed"]:
                raise RuntimeError("Geo execution cycle is not open")
            root = connection.execute(
                "SELECT * FROM geo_execution_cycles WHERE request_id = ?",
                (cycle["root_request_id"],),
            ).fetchone()
            if root is None:
                raise RuntimeError("Geo execution root is missing")
            usage = connection.execute(
                """SELECT COALESCE(SUM(e.reserved_requests), 0) AS requests,
                COALESCE(SUM(e.reserved_billable_units), 0) AS bills,
                SUM(e.reserved_billable_units IS NULL) AS unknown_bills
                FROM geo_provider_executions e JOIN geo_execution_cycles c
                ON c.request_id = e.request_id WHERE c.root_request_id = ?""",
                (cycle["root_request_id"],),
            ).fetchone()
            if (
                root["baseline_requests"] + usage["requests"] + requests
                > root["max_requests"]
            ):
                raise GeoBudgetExhausted("Cumulative Geo request ceiling exhausted.")
            ceiling = root["max_billable_units"]
            if ceiling is not None and (
                billable_units is None
                or root["baseline_billable_units"] is None
                or usage["unknown_bills"]
                or root["baseline_billable_units"] + usage["bills"] + billable_units
                > ceiling
            ):
                raise GeoBudgetExhausted("Cumulative Geo billable ceiling exhausted.")
            sequence = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 FROM geo_provider_executions WHERE request_id = ?",
                (request_id,),
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO geo_provider_executions VALUES (?, ?, ?, ?, ?, NULL)",
                (request_id, sequence, requests, billable_units, _json(descriptor)),
            )
            return int(sequence)

    def record_execution(
        self, request_id: str, sequence: int, execution: dict[str, Any]
    ) -> None:
        """Finalize a reservation; an interrupted call retains its full ceiling."""
        attempts = execution["attempts"]
        requests = sum(a["provider_requests"] for a in attempts)
        bills = (
            None
            if any(a["billable_units"] is None for a in attempts)
            else sum(a["billable_units"] for a in attempts)
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM geo_provider_executions WHERE request_id = ? AND sequence = ?",
                (request_id, sequence),
            ).fetchone()
            if row is None:
                raise RuntimeError("Geo execution was not reserved")
            if row["execution_json"] is not None:
                if row["execution_json"] != _json(execution):
                    raise GeoIdempotencyConflict(
                        "Recorded Geo execution cannot be overwritten"
                    )
                return
            if requests > row["reserved_requests"] or requests < 0:
                raise ValueError("Provider exceeded its reserved request ceiling")
            if row["reserved_billable_units"] is not None and (
                bills is None or bills > row["reserved_billable_units"]
            ):
                raise ValueError("Provider exceeded its reserved billable ceiling")
            connection.execute(
                """UPDATE geo_provider_executions SET reserved_requests = ?,
                reserved_billable_units = ?, execution_json = ?
                WHERE request_id = ? AND sequence = ?""",
                (requests, bills, _json(execution), request_id, sequence),
            )

    def executions(self, request_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM geo_provider_executions WHERE request_id = ? ORDER BY sequence",
                    (request_id,),
                )
            ]

    def cycle(self, request_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM geo_execution_cycles WHERE request_id = ?", (request_id,)
            ).fetchone()
            return None if row is None else dict(row)

    def precheck_execution(self, run_ref: str, subject_refs: set[str]):
        """Find an admitted stage batch even if its Work projection never committed."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM geo_execution_cycles WHERE prior_request_id IS NULL"
            ).fetchall()
        matches = []
        for row in rows:
            proof = json.loads(row["authority_json"]).get("precheck_confirmation") or {}
            if proof.get("run_ref") != run_ref:
                continue
            refs = {
                s["subject_ref"] for s in json.loads(row["request_json"])["subjects"]
            }
            if refs.intersection(subject_refs):
                matches.append(row["request_id"])
        if len(matches) > 1:
            raise GeoIdempotencyConflict(
                "Multiple admitted Geo scopes overlap unprojected Work"
            )
        return self.latest(matches[0]) if matches else None

    def latest(self, request_id: str) -> GeoJournalEntry | None:
        with self._connect() as connection:
            seen = set()
            while request_id not in seen:
                seen.add(request_id)
                row = connection.execute(
                    "SELECT request_id FROM geo_execution_cycles WHERE prior_request_id = ?",
                    (request_id,),
                ).fetchone()
                if row is None:
                    return self.get(request_id)
                request_id = row[0]
        raise RuntimeError("Cyclic Geo recovery journal")

    def adopt_legacy(
        self, request_id: str, request: dict, authority, *, confirmation_proof=None
    ) -> None:
        """Attach recoverable accounting only when the original authority is proven."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute(
                "SELECT 1 FROM geo_execution_cycles WHERE request_id = ?", (request_id,)
            ).fetchone():
                return
            row = connection.execute(
                "SELECT * FROM geo_operation_journal WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if (
                row is None
                or row["state"] != "completed"
                or row["authorization_binding"] != authority.binding()
            ):
                raise GeoIdempotencyConflict(
                    "Original Geo authority or completion is not proven"
                )
            result = json.loads(row["result_json"])
            effects = result["effects"]
            requests = effects["provider_requests"]
            if (
                not isinstance(requests, int)
                or requests > authority.envelope.max_provider_requests
            ):
                raise GeoIdempotencyConflict(
                    "Original Geo request consumption is unknown"
                )
            connection.execute(
                """INSERT INTO geo_execution_cycles
                (request_id, root_request_id, request_json, authority_json, max_requests,
                 max_billable_units, baseline_requests, baseline_billable_units, owner_pid, closed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 1)""",
                (
                    request_id,
                    request_id,
                    _json(request),
                    _json(
                        {
                            **authority.value(),
                            "precheck_confirmation": confirmation_proof,
                        }
                    ),
                    authority.envelope.max_provider_requests,
                    authority.envelope.max_billable_units,
                    requests,
                    effects["billable_units"],
                ),
            )

    def get(self, request_id: str) -> GeoJournalEntry | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT request_id, request_fingerprint, authorization_binding,
                       state, result_json
                FROM geo_operation_journal
                WHERE request_id = ?
                """,
                (request_id,),
            ).fetchone()
        return None if row is None else _entry(row)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.create_function(
            "mediasense_geo_schema_version", 0, lambda: _SCHEMA_VERSION
        )
        return connection


def _entry(row: sqlite3.Row) -> GeoJournalEntry:
    result = json.loads(str(row["result_json"]))
    if not isinstance(result, dict):
        raise TypeError("Geo journal result is not an object")
    return GeoJournalEntry(
        request_id=str(row["request_id"]),
        request_fingerprint=str(row["request_fingerprint"]),
        authorization_binding=str(row["authorization_binding"]),
        state=str(row["state"]),
        result=result,
    )


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
