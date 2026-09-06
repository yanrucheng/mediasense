"""Minimal durable journal for Geo Tool effect idempotency."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 1


class GeoIdempotencyConflict(RuntimeError):
    """A request ID was reused with different effective input or authority."""


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
            if journal_exists is not None and schema_exists is None:
                raise RuntimeError("unsupported unversioned Geo journal")
            connection.executescript(
                """
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
                )
                """
            )
            version = connection.execute(
                "SELECT version FROM internal_schema WHERE singleton = 1"
            ).fetchone()
            if version is None or int(version["version"]) != _SCHEMA_VERSION:
                raise RuntimeError("unsupported Geo journal schema version")

    def admit(
        self,
        *,
        request_id: str,
        request_fingerprint: str,
        authorization_binding: str,
        indeterminate_result: dict[str, Any],
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
        return None

    def complete(self, request_id: str, result: dict[str, Any]) -> None:
        with self._connect() as connection:
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
