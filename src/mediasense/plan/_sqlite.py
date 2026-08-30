"""Private SQLite persistence for Plan Working State."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Iterator


SCHEMA_VERSION = 2


class PlanStoreError(RuntimeError):
    pass


class WorkNotFound(PlanStoreError):
    pass


class WorkClosed(PlanStoreError):
    pass


class RevisionConflict(PlanStoreError):
    def __init__(self, current_revision: str) -> None:
        super().__init__("revision conflict")
        self.current_revision = current_revision


class IdempotencyConflict(PlanStoreError):
    pass


class SealConflict(PlanStoreError):
    pass


@dataclass(frozen=True, slots=True)
class WorkSnapshot:
    work_ref: str
    result_ref: str
    state: str
    revision: str
    organization_preferences: dict[str, Any]
    candidate: dict[str, Any] | None
    candidate_identity: str | None
    geo_observations: tuple[dict[str, Any], ...]
    plan_ref: str
    published_path: str | None


@dataclass(frozen=True, slots=True)
class SealReservation:
    request_id: str
    request_digest: str
    confirmation_digest: str
    work_ref: str
    revision: str
    candidate_identity: str
    plan_ref: str
    artifact_path: str
    frozen_plan: dict[str, Any]


class SQLitePlanStore:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def replay(self, request_id: str, request_digest: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT request_digest, response_json FROM plan_requests WHERE request_id = ?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        if row["request_digest"] != request_digest:
            raise IdempotencyConflict(request_id)
        return json.loads(row["response_json"])

    def cursor_signing_key(self) -> bytes:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT cursor_signing_key FROM plan_secrets WHERE singleton = 1"
            ).fetchone()
            if row is None:
                key = secrets.token_bytes(32)
                connection.execute(
                    "INSERT INTO plan_secrets(singleton, cursor_signing_key) VALUES (1, ?)",
                    (key,),
                )
                return key
            return bytes(row["cursor_signing_key"])

    def create(
        self,
        *,
        request_id: str,
        request_digest: str,
        work_ref: str,
        result_ref: str,
        revision: str,
        plan_ref: str,
        organization_preferences: dict[str, Any],
        response: dict[str, Any],
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            replay = self._replay(connection, request_id, request_digest)
            if replay is not None:
                return replay
            connection.execute(
                """
                INSERT INTO plan_works(
                    work_ref, result_ref, state, revision,
                    organization_preferences_json, plan_ref
                ) VALUES (?, ?, 'open', ?, ?, ?)
                """,
                (
                    work_ref,
                    result_ref,
                    revision,
                    _json(organization_preferences),
                    plan_ref,
                ),
            )
            self._record_request(
                connection, request_id, request_digest, "create", work_ref, response
            )
        return response

    def update(
        self,
        *,
        request_id: str,
        request_digest: str,
        work_ref: str,
        base_revision: str,
        revision: str,
        candidate: dict[str, Any],
        candidate_identity: str,
        organization_preferences: dict[str, Any] | None,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            replay = self._replay(connection, request_id, request_digest)
            if replay is not None:
                return replay
            row = self._row(connection, work_ref)
            if row["state"] != "open":
                raise WorkClosed(work_ref)
            reserved = connection.execute(
                "SELECT request_id FROM plan_seal_reservations WHERE work_ref = ?",
                (work_ref,),
            ).fetchone()
            if reserved is not None:
                raise SealConflict("a seal attempt is pending recovery")
            if row["revision"] != base_revision:
                raise RevisionConflict(row["revision"])
            preferences_json = (
                row["organization_preferences_json"]
                if organization_preferences is None
                else _json(organization_preferences)
            )
            connection.execute(
                """
                UPDATE plan_works
                SET revision = ?, organization_preferences_json = ?,
                    candidate_json = ?, candidate_identity = ?, updated_at = CURRENT_TIMESTAMP
                WHERE work_ref = ?
                """,
                (
                    revision,
                    preferences_json,
                    _json(candidate),
                    candidate_identity,
                    work_ref,
                ),
            )
            self._record_request(
                connection, request_id, request_digest, "update", work_ref, response
            )
        return response

    def snapshot(self, work_ref: str) -> WorkSnapshot:
        with self._connect() as connection:
            row = self._row(connection, work_ref)
        return _snapshot(row)

    def record_geo_observation(
        self,
        *,
        request_id: str,
        request_digest: str,
        work_ref: str,
        base_revision: str,
        revision: str,
        observation: dict[str, Any],
        response: dict[str, Any],
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            replay = self._replay(connection, request_id, request_digest)
            if replay is not None:
                return replay
            row = self._row(connection, work_ref)
            if row["state"] != "open":
                raise WorkClosed(work_ref)
            reserved = connection.execute(
                "SELECT request_id FROM plan_seal_reservations WHERE work_ref = ?",
                (work_ref,),
            ).fetchone()
            if reserved is not None:
                raise SealConflict("a seal attempt is pending recovery")
            if row["revision"] != base_revision:
                raise RevisionConflict(row["revision"])
            observations = json.loads(row["geo_observations_json"])
            if not isinstance(observations, list):
                raise RuntimeError("Plan Geo observations are invalid")
            observations.append(observation)
            connection.execute(
                """
                UPDATE plan_works
                SET revision = ?, geo_observations_json = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE work_ref = ?
                """,
                (revision, _json(observations), work_ref),
            )
            self._record_request(
                connection,
                request_id,
                request_digest,
                "enrich_geo",
                work_ref,
                response,
            )
        return response

    def reserve_seal(
        self,
        *,
        request_id: str,
        request_digest: str,
        confirmation_digest: str,
        work_ref: str,
        revision: str,
        candidate_identity: str,
        plan_ref: str,
        artifact_path: str,
        frozen_plan: dict[str, Any],
    ) -> SealReservation:
        with self._transaction() as connection:
            replay = self._replay(connection, request_id, request_digest)
            if replay is not None:
                raise SealConflict("seal is already complete")
            row = connection.execute(
                "SELECT * FROM plan_seal_reservations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is not None:
                reservation = _seal_reservation(row)
                if (
                    reservation.request_digest != request_digest
                    or reservation.confirmation_digest != confirmation_digest
                ):
                    raise IdempotencyConflict(request_id)
                return reservation

            work = self._row(connection, work_ref)
            if work["state"] != "open":
                raise WorkClosed(work_ref)
            if work["revision"] != revision:
                raise RevisionConflict(work["revision"])
            if work["candidate_identity"] != candidate_identity:
                raise SealConflict("candidate identity does not match the reservation")
            active = connection.execute(
                "SELECT request_id FROM plan_seal_reservations WHERE work_ref = ?",
                (work_ref,),
            ).fetchone()
            if active is not None:
                raise SealConflict("another seal attempt is already reserved")
            connection.execute(
                """
                INSERT INTO plan_seal_reservations(
                    request_id, request_digest, confirmation_digest, work_ref,
                    revision, candidate_identity, plan_ref, artifact_path,
                    frozen_plan_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    request_digest,
                    confirmation_digest,
                    work_ref,
                    revision,
                    candidate_identity,
                    plan_ref,
                    artifact_path,
                    _json(frozen_plan),
                ),
            )
            row = connection.execute(
                "SELECT * FROM plan_seal_reservations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            assert row is not None
            return _seal_reservation(row)

    def complete_seal(
        self,
        *,
        request_id: str,
        request_digest: str,
        confirmation_digest: str,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        with self._transaction() as connection:
            replay = self._replay(connection, request_id, request_digest)
            if replay is not None:
                return replay
            row = connection.execute(
                "SELECT * FROM plan_seal_reservations WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is None:
                raise SealConflict("seal reservation is missing")
            reservation = _seal_reservation(row)
            if (
                reservation.request_digest != request_digest
                or reservation.confirmation_digest != confirmation_digest
            ):
                raise IdempotencyConflict(request_id)
            work = self._row(connection, reservation.work_ref)
            if work["state"] != "open":
                raise WorkClosed(reservation.work_ref)
            if work["revision"] != reservation.revision:
                raise RevisionConflict(work["revision"])
            if work["candidate_identity"] != reservation.candidate_identity:
                raise SealConflict("candidate changed during seal")
            connection.execute(
                """
                UPDATE plan_works
                SET state = 'closed', published_path = ?,
                    closed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE work_ref = ?
                """,
                (reservation.artifact_path, reservation.work_ref),
            )
            self._record_request(
                connection,
                request_id,
                request_digest,
                "seal",
                reservation.work_ref,
                response,
            )
            connection.execute(
                "DELETE FROM plan_seal_reservations WHERE request_id = ?",
                (request_id,),
            )
        return response

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS internal_schema (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    version INTEGER NOT NULL
                );
                INSERT OR IGNORE INTO internal_schema(singleton, version) VALUES (1, 2);

                CREATE TABLE IF NOT EXISTS plan_works (
                    work_ref TEXT PRIMARY KEY,
                    result_ref TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('open', 'closed')),
                    revision TEXT NOT NULL,
                    organization_preferences_json TEXT NOT NULL,
                    candidate_json TEXT,
                    candidate_identity TEXT,
                    geo_observations_json TEXT NOT NULL DEFAULT '[]',
                    plan_ref TEXT NOT NULL UNIQUE,
                    published_path TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    closed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS plan_requests (
                    request_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    action TEXT NOT NULL,
                    work_ref TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS plan_secrets (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    cursor_signing_key BLOB NOT NULL
                );

                CREATE TABLE IF NOT EXISTS plan_seal_reservations (
                    request_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    confirmation_digest TEXT NOT NULL,
                    work_ref TEXT NOT NULL UNIQUE,
                    revision TEXT NOT NULL,
                    candidate_identity TEXT NOT NULL,
                    plan_ref TEXT NOT NULL UNIQUE,
                    artifact_path TEXT NOT NULL UNIQUE,
                    frozen_plan_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            version = connection.execute(
                "SELECT version FROM internal_schema WHERE singleton = 1"
            ).fetchone()[0]
            if version == 1:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(plan_works)"
                    ).fetchall()
                }
                if "geo_observations_json" not in columns:
                    connection.execute(
                        """
                        ALTER TABLE plan_works
                        ADD COLUMN geo_observations_json TEXT NOT NULL DEFAULT '[]'
                        """
                    )
                connection.execute(
                    "UPDATE internal_schema SET version = 2 WHERE singleton = 1"
                )
                version = 2
            if version != SCHEMA_VERSION:
                raise RuntimeError(f"unsupported Plan schema version: {version}")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _row(connection: sqlite3.Connection, work_ref: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM plan_works WHERE work_ref = ?", (work_ref,)
        ).fetchone()
        if row is None:
            raise WorkNotFound(work_ref)
        return row

    @staticmethod
    def _replay(
        connection: sqlite3.Connection, request_id: str, request_digest: str
    ) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT request_digest, response_json FROM plan_requests WHERE request_id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        if row["request_digest"] != request_digest:
            raise IdempotencyConflict(request_id)
        return json.loads(row["response_json"])

    @staticmethod
    def _record_request(
        connection: sqlite3.Connection,
        request_id: str,
        request_digest: str,
        action: str,
        work_ref: str,
        response: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO plan_requests(
                request_id, request_digest, action, work_ref, response_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (request_id, request_digest, action, work_ref, _json(response)),
        )


def _snapshot(row: sqlite3.Row) -> WorkSnapshot:
    return WorkSnapshot(
        work_ref=row["work_ref"],
        result_ref=row["result_ref"],
        state=row["state"],
        revision=row["revision"],
        organization_preferences=json.loads(row["organization_preferences_json"]),
        candidate=None
        if row["candidate_json"] is None
        else json.loads(row["candidate_json"]),
        candidate_identity=row["candidate_identity"],
        geo_observations=tuple(json.loads(row["geo_observations_json"])),
        plan_ref=row["plan_ref"],
        published_path=row["published_path"],
    )


def _seal_reservation(row: sqlite3.Row) -> SealReservation:
    return SealReservation(
        request_id=row["request_id"],
        request_digest=row["request_digest"],
        confirmation_digest=row["confirmation_digest"],
        work_ref=row["work_ref"],
        revision=row["revision"],
        candidate_identity=row["candidate_identity"],
        plan_ref=row["plan_ref"],
        artifact_path=row["artifact_path"],
        frozen_plan=json.loads(row["frozen_plan_json"]),
    )


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
