"""Authorization, execution, recovery, and Receipt closure for Apply Runs."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import fcntl
from pathlib import Path
import sqlite3

from .filesystem import (
    EffectObservation,
    FilesystemBoundary,
    FilesystemEffectError,
    LocalFilesystem,
    MetadataDiscrepancy,
    canonical_identity,
    ensure_directories,
    planned_directories,
)
from .preparation import ApplyRunStore, ApplyPreparationError
from .receipt import ReceiptStore, content_identity


FaultHook = Callable[[str, str | None], None]


class ApplyExecutionError(RuntimeError):
    """Execution cannot safely continue under the current Run facts."""


class ApplyExecutor:
    """Execute prepared Runs while keeping all mutable truth in their store."""

    def __init__(
        self,
        run_store: ApplyRunStore,
        receipt_store: ReceiptStore,
        *,
        filesystem: FilesystemBoundary | None = None,
        fault_hook: FaultHook | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.run_store = run_store
        self.receipt_store = receipt_store
        self.filesystem = filesystem or LocalFilesystem()
        self.fault_hook = fault_hook or (lambda _point, _item: None)
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def execute(
        self,
        *,
        run_ref: str,
        prepared_revision: str,
        prepared_content_identity: str,
        request_id: str,
        authorization_binding: str,
    ) -> dict[str, object]:
        """Authorize exact prepared content and synchronously advance the Run."""

        response = self.authorize(
            run_ref=run_ref,
            prepared_revision=prepared_revision,
            prepared_content_identity=prepared_content_identity,
            request_id=request_id,
            authorization_binding=authorization_binding,
        )
        if response["observed_state"] == "closed":
            return self.run_store.status(run_ref)
        self.advance(run_ref)
        return self.run_store.status(run_ref)

    def authorize(
        self,
        *,
        run_ref: str,
        prepared_revision: str,
        prepared_content_identity: str,
        request_id: str,
        authorization_binding: str | None,
    ) -> dict[str, object]:
        """Persist exact Human authorization without claiming completion."""

        request_identity = canonical_identity(
            {
                "run_ref": run_ref,
                "prepared_revision": prepared_revision,
                "prepared_content_identity": prepared_content_identity,
            }
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._run(connection, run_ref)
            if existing["execute_request_id"] is not None:
                if (
                    existing["execute_request_id"] != request_id
                    or existing["execute_request_identity"] != request_identity
                ):
                    raise ApplyExecutionError("execute idempotency conflict")
                return {
                    "outcome": "accepted",
                    "action": "execute",
                    "run_ref": run_ref,
                    "observed_state": str(existing["state"]),
                    "target_state": "executing",
                }
            if authorization_binding is None:
                raise ApplyExecutionError("trusted Human confirmation is required")
            if existing["prepared_revision"] != prepared_revision:
                raise ApplyPreparationError("prepared revision mismatch")
            if existing["prepared_content_identity"] != prepared_content_identity:
                raise ApplyPreparationError("prepared content identity mismatch")
            if existing["state"] not in {"ready_for_authorization", "needs_attention"}:
                raise ApplyExecutionError("Run is not ready for authorization")
            if (
                existing["state"] == "needs_attention"
                and not connection.execute(
                    "SELECT 1 FROM metadata_discrepancies WHERE run_ref = ? "
                    "AND accepted_authorization_ref IS NULL LIMIT 1",
                    (run_ref,),
                ).fetchone()
            ):
                raise ApplyExecutionError(
                    "Run needs recovery rather than new authorization"
                )
            now = self._timestamp()
            authorization_ref = f"authorization:{request_id.split(':', 1)[-1]}"
            connection.execute(
                """
                UPDATE metadata_discrepancies
                SET accepted_authorization_ref = ?
                WHERE run_ref = ? AND accepted_authorization_ref IS NULL
                """,
                (authorization_ref, run_ref),
            )
            connection.execute(
                """
                UPDATE runs
                SET execute_request_id = ?, execute_request_identity = ?,
                    authorization_binding = ?,
                    authorized_prepared_content_identity = ?, authorized_at = ?,
                    started_at = COALESCE(started_at, ?), state = 'executing',
                    control_requested = NULL
                WHERE run_ref = ?
                """,
                (
                    request_id,
                    request_identity,
                    authorization_binding,
                    prepared_content_identity,
                    now,
                    now,
                    run_ref,
                ),
            )
            connection.commit()
        return {
            "outcome": "accepted",
            "action": "execute",
            "run_ref": run_ref,
            "observed_state": "ready_for_authorization",
            "target_state": "executing",
        }

    def resume(self, run_ref: str) -> dict[str, object]:
        """Accept a request to continue one paused or attention-required Run."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = self._run(connection, run_ref)
            if run["state"] == "closed":
                raise ApplyExecutionError("closed Run cannot resume")
            if run["state"] not in {
                "executing",
                "paused",
                "needs_attention",
                "verifying",
            }:
                raise ApplyExecutionError(f"Run cannot resume from {run['state']}")
            if connection.execute(
                "SELECT 1 FROM metadata_discrepancies WHERE run_ref = ? AND accepted_authorization_ref IS NULL LIMIT 1",
                (run_ref,),
            ).fetchone():
                raise ApplyExecutionError("resume cannot authorize a metadata loss")
            connection.execute(
                "DELETE FROM findings WHERE run_ref = ? AND code = 'executor_interrupted'",
                (run_ref,),
            )
            connection.execute(
                """
                UPDATE runs SET state = 'executing', control_requested = NULL,
                    resume_count = resume_count + 1
                WHERE run_ref = ?
                """,
                (run_ref,),
            )
            connection.execute(
                """
                UPDATE run_items SET execution_status = 'not_attempted'
                WHERE run_ref = ? AND (
                    execution_status = 'failed'
                    OR (execution_status = 'indeterminate' AND attempts = 0)
                )
                """,
                (run_ref,),
            )
            connection.commit()
        return self._control_response("resume", run_ref, str(run["state"]), "executing")

    def pause(self, run_ref: str) -> dict[str, object]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = self._run(connection, run_ref)
            if run["state"] == "paused":
                connection.commit()
                return self._control_response("pause", run_ref, "paused", "paused")
            if run["state"] != "executing":
                raise ApplyExecutionError(f"Run cannot pause from {run['state']}")
            connection.execute(
                "UPDATE runs SET control_requested = 'pause' WHERE run_ref = ?",
                (run_ref,),
            )
            connection.commit()
        return self._control_response("pause", run_ref, "executing", "paused")

    def cancel(self, run_ref: str) -> dict[str, object]:
        run = self.run_store.get_run(run_ref)
        if run.state in {"preparing", "ready_for_authorization", "blocked"}:
            self.run_store.cancel_before_execution(run_ref)
            return self._control_response("cancel", run_ref, run.state, "cancelled")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._run(connection, run_ref)
            if current["state"] == "closed":
                raise ApplyExecutionError("closed Run cannot cancel")
            if current["execute_request_id"] is None:
                raise ApplyExecutionError("Run has no accepted execution")
            connection.execute(
                """
                UPDATE runs SET control_requested = 'cancel', state = 'verifying',
                    closure = 'human_cancelled'
                WHERE run_ref = ?
                """,
                (run_ref,),
            )
            connection.commit()
        return self._control_response(
            "cancel", run_ref, str(current["state"]), "verifying"
        )

    @staticmethod
    def _control_response(
        action: str, run_ref: str, observed_state: str, target_state: str
    ) -> dict[str, object]:
        return {
            "outcome": "accepted",
            "action": action,
            "run_ref": run_ref,
            "observed_state": observed_state,
            "target_state": target_state,
        }

    def advance(self, run_ref: str) -> None:
        """Reconcile pending intent, issue safe effects, and close when complete."""

        with self._run_lock(run_ref):
            self._advance_locked(run_ref)

    def _advance_locked(self, run_ref: str) -> None:
        self._recover_publication(run_ref)
        current_state = self.run_store.get_run(run_ref).state
        if current_state == "closed":
            return
        if current_state in {"paused", "needs_attention"}:
            return
        if current_state not in {"executing", "verifying"}:
            raise ApplyExecutionError(f"Run cannot advance from {current_state}")
        self._reconcile_intents(run_ref)
        if self.run_store.get_run(run_ref).state == "needs_attention":
            return
        self._reconcile_directory_intents(run_ref)
        while True:
            run, item = self._next_item(run_ref)
            if run["control_requested"] == "pause":
                self._set_state(run_ref, "paused")
                return
            if run["control_requested"] == "cancel":
                self._set_state(run_ref, "verifying", closure="human_cancelled")
                self._close(run_ref, closure="human_cancelled")
                return
            if item is None:
                break
            self._execute_item(run, item)
            if self.run_store.get_run(run_ref).state == "needs_attention":
                return
            if self._has_pending_metadata_decision(run_ref):
                return
        with self._connect() as connection:
            unresolved = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM run_items
                    WHERE run_ref = ? AND planned_outcome = 'materialize'
                      AND execution_status <> 'completed_and_verified'
                    """,
                    (run_ref,),
                ).fetchone()[0]
            )
        if unresolved:
            self._set_state(run_ref, "needs_attention")
            return
        self._set_state(run_ref, "verifying")
        self._close(run_ref, closure="automatic")

    @contextmanager
    def _run_lock(self, run_ref: str):
        lock_root = self.run_store.database_path.parent / "locks"
        lock_root.mkdir(parents=True, exist_ok=True)
        token = canonical_identity(run_ref).removeprefix("sha256:")
        lock_path = lock_root / f"{token}.lock"
        with lock_path.open("a+b") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ApplyExecutionError(
                    "another executor is already advancing this Run"
                ) from error
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def mark_owner_interrupted(self, run_ref: str) -> None:
        """A Host with no local worker probes the cross-process owner lock.

        This only records an interruption; status never starts media effects.
        """
        if self.run_store.get_run(run_ref).state not in {"executing", "verifying"}:
            return
        try:
            with self._run_lock(run_ref):
                with self._connect() as connection:
                    connection.execute("BEGIN IMMEDIATE")
                    run = self._run(connection, run_ref)
                    if run["state"] not in {"executing", "verifying"}:
                        return
                    connection.execute(
                        "UPDATE runs SET state = 'needs_attention' WHERE run_ref = ?",
                        (run_ref,),
                    )
                    connection.execute(
                        "INSERT OR IGNORE INTO findings VALUES (?, 'executor_interrupted', '', ?)",
                        (
                            run_ref,
                            "No execution owner remains; resume to reconcile durable intent, or cancel.",
                        ),
                    )
                    connection.commit()
        except ApplyExecutionError as error:
            if str(error) != "another executor is already advancing this Run":
                raise

    def _has_pending_metadata_decision(self, run_ref: str) -> bool:
        with self._connect() as connection:
            return bool(
                connection.execute(
                    """
                    SELECT 1 FROM metadata_discrepancies
                    WHERE run_ref = ? AND accepted_authorization_ref IS NULL
                    LIMIT 1
                    """,
                    (run_ref,),
                ).fetchone()
            )

    def _next_item(self, run_ref: str) -> tuple[sqlite3.Row, sqlite3.Row | None]:
        with self._connect() as connection:
            run = self._run(connection, run_ref)
            row = connection.execute(
                """
                SELECT * FROM run_items
                WHERE run_ref = ? AND planned_outcome = 'materialize'
                  AND execution_status = 'not_attempted'
                ORDER BY ordinal LIMIT 1
                """,
                (run_ref,),
            ).fetchone()
        return run, row

    def _execute_item(self, run: sqlite3.Row, item: sqlite3.Row) -> None:
        run_ref = str(run["run_ref"])
        source_item_ref = str(item["source_item_ref"])
        source = Path(item["source_path"])
        target = Path(item["intended_target"])
        try:
            self._verify_run_bindings(run_ref)
            directory_root = (
                target.parent
                if run["direction"] == "rewind"
                else Path(run["destination_parent"])
            )
            self._ensure_directories_durable(run_ref, directory_root, target.parent)
            temporary = (
                Path(item["temporary_path"])
                if item["temporary_path"] is not None
                else None
            )
            if (
                temporary is None
                and run["execution_route"] == "verified_cross_filesystem_transfer"
            ):
                token = run_ref.split(":", 1)[-1]
                temporary = target.with_name(
                    f".{target.name}.mediasense-{token}.partial"
                )
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                changed = connection.execute(
                    """
                    UPDATE run_items
                    SET execution_status = 'intent', attempts = attempts + 1,
                        source_after = 'present', target_after = 'absent',
                        execution_reason_code = NULL,
                        execution_reason_message = NULL, temporary_path = ?
                    WHERE run_ref = ? AND source_item_ref = ?
                      AND execution_status = 'not_attempted'
                    """,
                    (
                        str(temporary) if temporary is not None else None,
                        run_ref,
                        source_item_ref,
                    ),
                )
                connection.commit()
                if changed.rowcount != 1:
                    return
            self.fault_hook("after_intent", source_item_ref)
            observation = self.filesystem.move(
                source=source,
                target=target,
                expected_digest=str(
                    item["transfer_digest"] or item["expected_verification"]
                ),
                expected_size=int(item["observed_size"]),
                route=str(run["execution_route"]),
                temporary_path=temporary,
                accepted_discrepancies=self._accepted_discrepancies(
                    run_ref, source_item_ref
                ),
                expected_source_stat=(
                    int(item["observed_device"]),
                    int(item["observed_inode"]),
                    int(item["observed_mtime_ns"]),
                    int(item["observed_ctime_ns"]),
                ),
            )
            self.fault_hook("after_effect_before_record", source_item_ref)
            if observation.status == "metadata_loss":
                self._record_metadata_loss(run, item, observation)
                return
            self._record_observation(run_ref, source_item_ref, observation)
        except FilesystemEffectError as error:
            self._record_effect_error(run_ref, source_item_ref, error)

    def _reconcile_intents(self, run_ref: str) -> None:
        with self._connect() as connection:
            run = self._run(connection, run_ref)
            intents = connection.execute(
                """
                SELECT * FROM run_items
                WHERE run_ref = ? AND execution_status = 'intent'
                ORDER BY ordinal
                """,
                (run_ref,),
            ).fetchall()
        for item in intents:
            source_item_ref = str(item["source_item_ref"])
            try:
                self._verify_run_bindings(run_ref)
                observation = self.filesystem.reconcile(
                    source=Path(item["source_path"]),
                    target=Path(item["intended_target"]),
                    expected_digest=str(
                        item["transfer_digest"] or item["expected_verification"]
                    ),
                    expected_size=int(item["observed_size"]),
                    route=str(run["execution_route"]),
                    temporary_path=(
                        Path(item["temporary_path"])
                        if item["temporary_path"] is not None
                        else None
                    ),
                    accepted_discrepancies=self._accepted_discrepancies(
                        run_ref, source_item_ref
                    ),
                    expected_source_stat=(
                        int(item["observed_device"]),
                        int(item["observed_inode"]),
                        int(item["observed_mtime_ns"]),
                        int(item["observed_ctime_ns"]),
                    ),
                )
                if observation.status == "completed":
                    observation = replace(
                        observation,
                        verification_basis=observation.verification_basis,
                    )
                    self._record_observation(
                        run_ref, source_item_ref, observation, recovered=True
                    )
                else:
                    with self._connect() as connection:
                        connection.execute(
                            """
                            UPDATE run_items SET execution_status = 'not_attempted',
                                recovery_fact = ?, postcondition_profile = NULL,
                                postcondition_result = NULL,
                                postcondition_basis = NULL,
                                execution_reason_code = NULL,
                                execution_reason_message = NULL
                            WHERE run_ref = ? AND source_item_ref = ?
                            """,
                            (
                                observation.verification_basis,
                                run_ref,
                                source_item_ref,
                            ),
                        )
                        connection.commit()
            except FilesystemEffectError as error:
                self._record_effect_error(run_ref, source_item_ref, error)

    def _record_observation(
        self,
        run_ref: str,
        source_item_ref: str,
        observation: EffectObservation,
        *,
        recovered: bool = False,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE run_items
                SET execution_status = 'completed_and_verified',
                    source_after = ?, target_after = ?,
                    postcondition_profile = ?, postcondition_result = 'verified',
                    postcondition_basis = ?, bytes_moved = ?, temporary_path = NULL,
                    recovery_fact = COALESCE(?, recovery_fact),
                    execution_reason_code = NULL,
                    execution_reason_message = NULL
                WHERE run_ref = ? AND source_item_ref = ?
                """,
                (
                    observation.source_after,
                    observation.target_after,
                    observation.verification_profile,
                    observation.verification_basis,
                    observation.bytes_moved,
                    "Recovered a completed effect from filesystem facts."
                    if recovered
                    else None,
                    run_ref,
                    source_item_ref,
                ),
            )
            connection.commit()

    def _record_effect_error(
        self, run_ref: str, source_item_ref: str, error: FilesystemEffectError
    ) -> None:
        status = "indeterminate" if error.global_risk else "failed"
        if error.code in {
            "source_missing",
            "source_unsafe_type",
            "source_stale",
            "source_size_mismatch",
            "source_digest_mismatch",
            "target_collision",
        }:
            status = "refused"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                """
                SELECT execution_status FROM run_items
                WHERE run_ref = ? AND source_item_ref = ?
                """,
                (run_ref, source_item_ref),
            ).fetchone()
            if (
                error.global_risk
                and current is not None
                and current["execution_status"] == "intent"
            ):
                status = "intent"
            connection.execute(
                """
                UPDATE run_items
                SET execution_status = ?, source_after = 'indeterminate',
                    target_after = 'indeterminate',
                    postcondition_profile = 'effect_boundary_verification',
                    postcondition_result = 'indeterminate',
                    postcondition_basis = ?, execution_reason_code = ?,
                    execution_reason_message = ?
                WHERE run_ref = ? AND source_item_ref = ?
                """,
                (status, str(error), error.code, str(error), run_ref, source_item_ref),
            )
            if error.global_risk:
                connection.execute(
                    "UPDATE runs SET state = 'needs_attention' WHERE run_ref = ?",
                    (run_ref,),
                )
            connection.commit()

    def _record_metadata_loss(
        self, run: sqlite3.Row, item: sqlite3.Row, observation: EffectObservation
    ) -> None:
        discrepancy_facts = [
            {
                "discrepancy_ref": (
                    f"metadata-discrepancy:"
                    f"{item['source_item_ref'].split(':', 1)[-1]}-{index}"
                ),
                "source_item_ref": str(item["source_item_ref"]),
                "attribute": value.attribute,
                "expected": value.expected,
                "observed": value.observed,
            }
            for index, value in enumerate(observation.discrepancies)
        ]
        discrepancy_identity = canonical_identity(discrepancy_facts)
        changed_identity = canonical_identity(
            {
                "prepared_content_identity": str(run["prepared_content_identity"]),
                "metadata_discrepancies": discrepancy_facts,
            }
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM metadata_discrepancies WHERE run_ref = ? AND source_item_ref = ?",
                (run["run_ref"], item["source_item_ref"]),
            )
            for value in discrepancy_facts:
                connection.execute(
                    """
                    INSERT INTO metadata_discrepancies (
                        run_ref, discrepancy_ref, source_item_ref, attribute,
                        expected_json, observed_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run["run_ref"],
                        value["discrepancy_ref"],
                        item["source_item_ref"],
                        value["attribute"],
                        json.dumps(value["expected"], sort_keys=True),
                        json.dumps(value["observed"], sort_keys=True),
                    ),
                )
            connection.execute(
                """
                UPDATE run_items SET execution_status = 'not_attempted',
                    temporary_path = ?, recovery_fact = ?,
                    execution_reason_code = 'metadata_preservation_loss_requires_authorization',
                    execution_reason_message = ?
                WHERE run_ref = ? AND source_item_ref = ?
                """,
                (
                    observation.temporary_path,
                    "Verified non-final copy awaits exact metadata-loss authorization.",
                    "Source deletion is blocked until the exact metadata loss is authorized.",
                    run["run_ref"],
                    item["source_item_ref"],
                ),
            )
            connection.execute(
                """
                UPDATE runs SET state = 'needs_attention',
                    prepared_revision = ?, prepared_content_identity = ?,
                    execute_request_id = NULL, execute_request_identity = NULL,
                    authorization_binding = NULL,
                    authorized_prepared_content_identity = NULL,
                    authorized_at = NULL
                WHERE run_ref = ?
                """,
                (
                    f"apply-revision:{discrepancy_identity.removeprefix('sha256:')[:24]}",
                    changed_identity,
                    run["run_ref"],
                ),
            )
            connection.commit()

    def _accepted_discrepancies(
        self, run_ref: str, source_item_ref: str
    ) -> tuple[MetadataDiscrepancy, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT attribute, expected_json, observed_json
                FROM metadata_discrepancies
                WHERE run_ref = ? AND source_item_ref = ?
                  AND accepted_authorization_ref IS NOT NULL
                ORDER BY discrepancy_ref
                """,
                (run_ref, source_item_ref),
            ).fetchall()
        return tuple(
            MetadataDiscrepancy(
                attribute=str(row["attribute"]),
                expected=json.loads(row["expected_json"]),
                observed=json.loads(row["observed_json"]),
            )
            for row in rows
        )

    def _verify_run_bindings(self, run_ref: str) -> None:
        with self._connect() as connection:
            run = self._run(connection, run_ref)
            roots = connection.execute(
                "SELECT * FROM source_roots WHERE run_ref = ?", (run_ref,)
            ).fetchall()
        if run["direction"] == "forward":
            destination = Path(run["destination_parent"])
            try:
                info = destination.stat(follow_symlinks=False)
            except OSError as error:
                raise FilesystemEffectError(
                    "destination_unavailable",
                    "destination parent is unavailable at the effect boundary",
                    global_risk=True,
                ) from error
            observed = (
                f"filesystem-object-v1:dev={info.st_dev}:ino={info.st_ino}:"
                f"path={destination}"
            )
            if observed != run["destination_observed_identity"]:
                raise FilesystemEffectError(
                    "destination_rebound",
                    "destination parent identity changed after preparation",
                    global_risk=True,
                )
        for root in roots:
            path = Path(root["current_root"])
            try:
                info = path.stat(follow_symlinks=False)
            except OSError as error:
                raise FilesystemEffectError(
                    "source_root_unavailable",
                    f"source root is unavailable: {root['source_root_ref']}",
                    global_risk=True,
                ) from error
            observed = (
                f"filesystem-object-v1:dev={info.st_dev}:ino={info.st_ino}:path={path}"
            )
            if observed != root["observed_identity"]:
                raise FilesystemEffectError(
                    "source_root_rebound",
                    f"source root identity changed: {root['source_root_ref']}",
                    global_risk=True,
                )

    def _record_created_directories(self, run_ref: str, paths: list[Path]) -> None:
        if not paths:
            return
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                """
                INSERT INTO created_directories (run_ref, path, status)
                VALUES (?, ?, 'created')
                ON CONFLICT(run_ref, path) DO UPDATE SET status = 'created'
                """,
                ((run_ref, str(path)) for path in paths),
            )
            connection.commit()

    def _ensure_directories_durable(
        self, run_ref: str, root: Path, parent: Path
    ) -> None:
        missing = planned_directories(root, parent)
        if not missing:
            return
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.executemany(
                """
                INSERT OR IGNORE INTO created_directories (run_ref, path, status)
                VALUES (?, ?, 'intent')
                """,
                ((run_ref, str(path)) for path in missing),
            )
            connection.commit()
        self.fault_hook("after_directory_intent", None)
        created = ensure_directories(root, parent)
        self.fault_hook("after_directory_effect_before_record", None)
        self._record_created_directories(run_ref, created)

    def _reconcile_directory_intents(self, run_ref: str) -> None:
        with self._connect() as connection:
            intents = connection.execute(
                """
                SELECT path FROM created_directories
                WHERE run_ref = ? AND status = 'intent' ORDER BY path
                """,
                (run_ref,),
            ).fetchall()
            for row in intents:
                path = Path(row["path"])
                status = (
                    "preexisting"
                    if path.is_dir() and not path.is_symlink()
                    else "intent"
                )
                connection.execute(
                    """
                    UPDATE created_directories SET status = ?
                    WHERE run_ref = ? AND path = ?
                    """,
                    (status, run_ref, str(path)),
                )
            connection.commit()

    def _set_state(
        self, run_ref: str, state: str, *, closure: str | None = None
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET state = ?, closure = COALESCE(?, closure) WHERE run_ref = ?",
                (state, closure, run_ref),
            )
            connection.commit()

    def _close(self, run_ref: str, *, closure: str) -> None:
        with self._connect() as connection:
            run = self._run(connection, run_ref)
            items = connection.execute(
                "SELECT * FROM run_items WHERE run_ref = ? ORDER BY ordinal",
                (run_ref,),
            ).fetchall()
            roots = connection.execute(
                "SELECT * FROM source_roots WHERE run_ref = ? ORDER BY source_root_ref",
                (run_ref,),
            ).fetchall()
            directories = connection.execute(
                """
                SELECT path FROM created_directories
                WHERE run_ref = ? AND status = 'created' ORDER BY path
                """,
                (run_ref,),
            ).fetchall()
            discrepancies = connection.execute(
                """
                SELECT * FROM metadata_discrepancies
                WHERE run_ref = ? ORDER BY discrepancy_ref
                """,
                (run_ref,),
            ).fetchall()
        receipt = self._build_receipt(
            run, items, roots, directories, discrepancies, closure=closure
        )
        package = self.receipt_store.prepare(receipt)
        receipt = package.document
        receipt_ref = str(receipt["sealed_content"]["receipt_ref"])
        identity = str(receipt["seal"]["content_identity"])
        final_path = self.receipt_store.artifact_path(receipt_ref) / "receipt.json"
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO receipt_publications (
                    run_ref, receipt_ref, content_identity, final_path,
                    document_json, state
                ) VALUES (?, ?, ?, ?, ?, 'reserved')
                """,
                (
                    run_ref,
                    receipt_ref,
                    identity,
                    str(final_path),
                    json.dumps(receipt, ensure_ascii=False, sort_keys=True),
                ),
            )
            connection.commit()
        path = self.receipt_store.publish(package)
        self.fault_hook("after_receipt_publish_before_close", None)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                UPDATE receipt_publications SET state = 'published'
                WHERE run_ref = ? AND content_identity = ?
                """,
                (run_ref, identity),
            )
            connection.execute(
                """
                UPDATE runs SET state = 'closed', closure = ?, ended_at = ?,
                    receipt_ref = ?, receipt_path = ?, receipt_content_identity = ?
                WHERE run_ref = ?
                """,
                (closure, self._timestamp(), receipt_ref, str(path), identity, run_ref),
            )
            connection.commit()

    def _recover_publication(self, run_ref: str) -> None:
        with self._connect() as connection:
            publication = connection.execute(
                "SELECT * FROM receipt_publications WHERE run_ref = ?", (run_ref,)
            ).fetchone()
        if publication is None:
            return
        receipt = json.loads(publication["document_json"])
        ledger = receipt["sealed_content"]["operation_ledger"]
        operations = None
        if ledger["kind"] == "immutable_segments":
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM run_items
                    WHERE run_ref = ? AND planned_outcome = 'materialize'
                    ORDER BY ordinal
                    """,
                    (run_ref,),
                ).fetchall()
            operations = [self._operation_receipt(row) for row in rows]
        package = self.receipt_store.prepare(receipt, operations=operations)
        path = self.receipt_store.publish(package)
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "UPDATE receipt_publications SET state = 'published' WHERE run_ref = ?",
                (run_ref,),
            )
            connection.execute(
                """
                UPDATE runs SET state = 'closed', receipt_ref = ?, receipt_path = ?,
                    receipt_content_identity = ?, ended_at = COALESCE(ended_at, ?)
                WHERE run_ref = ?
                """,
                (
                    publication["receipt_ref"],
                    str(path),
                    publication["content_identity"],
                    self._timestamp(),
                    run_ref,
                ),
            )
            connection.commit()

    def _build_receipt(
        self,
        run: sqlite3.Row,
        rows: list[sqlite3.Row],
        roots: list[sqlite3.Row],
        directories: list[sqlite3.Row],
        discrepancies: list[sqlite3.Row],
        *,
        closure: str,
    ) -> dict[str, object]:
        materialized = [row for row in rows if row["planned_outcome"] == "materialize"]
        operations = [self._operation_receipt(row) for row in materialized]
        counts = {
            name: sum(row["execution_status"] == name for row in materialized)
            for name in (
                "completed_and_verified",
                "failed",
                "refused",
                "not_attempted",
                "indeterminate",
            )
        }
        complete = counts["completed_and_verified"] == len(materialized)
        receipt_ref = str(
            run["receipt_ref"]
            or f"apply-receipt:{str(run['run_ref']).split(':', 1)[-1]}"
        )
        accepted = [
            str(row["discrepancy_ref"])
            for row in discrepancies
            if row["accepted_authorization_ref"] is not None
        ]
        discrepancy_values = [
            {
                "discrepancy_ref": str(row["discrepancy_ref"]),
                "source_item_ref": str(row["source_item_ref"]),
                "attribute": str(row["attribute"]),
                "expected": json.loads(row["expected_json"]),
                "observed": json.loads(row["observed_json"]),
            }
            for row in discrepancies
        ]
        authorizations = []
        if accepted:
            authorization_ref = str(
                next(
                    row["accepted_authorization_ref"]
                    for row in discrepancies
                    if row["accepted_authorization_ref"] is not None
                )
            )
            authorizations.append(
                {
                    "authorization_ref": authorization_ref,
                    "binding": str(run["authorization_binding"]),
                    "confirmed_prepared_content_identity": str(
                        run["authorized_prepared_content_identity"]
                    ),
                    "confirmed_discrepancy_set_identity": canonical_identity(
                        [
                            value
                            for value in discrepancy_values
                            if value["discrepancy_ref"] in accepted
                        ]
                    ),
                    "accepted_discrepancy_refs": accepted,
                    "confirmed_at": str(run["authorized_at"]),
                }
            )
        route = str(run["execution_route"])
        checked_attributes = (
            ["filesystem_identity_and_location"]
            if route == "same_filesystem_atomic_move"
            else ["mode", "uid", "gid", "mtime_ns", "birthtime_ns", "flags", "xattrs"]
        )
        sealed: dict[str, object] = {
            "contract": "mediasense.apply-receipt",
            "receipt_ref": receipt_ref,
            "run_ref": str(run["run_ref"]),
            "frozen_plan_ref": str(run["frozen_plan_ref"]),
            "frozen_plan_content_identity": str(run["frozen_plan_content_identity"]),
            "effect": "move_originals",
            "execution_binding": self._receipt_execution_binding(run, roots, rows),
            "prepared_content_identity": str(run["prepared_content_identity"]),
            "authorization": {
                "binding": str(run["authorization_binding"]),
                "confirmed_prepared_content_identity": str(
                    run["authorized_prepared_content_identity"]
                ),
                "confirmed_at": str(run["authorized_at"]),
            },
            "preflight": {
                "source_compatibility": "verified",
                "target_binding": "verified",
                "execution_route": route,
                "target_collisions": 0,
                "blockers": 0,
                "warnings": 1 if route == "same_filesystem_atomic_move" else 0,
            },
            "completion": "complete" if complete else "incomplete",
            "closure": closure,
            "accounting": {
                "plan_scope_items": len(rows),
                "materialization_operations": len(materialized),
                "retained_without_effect": sum(
                    row["planned_outcome"] == "retain" for row in rows
                ),
                "excluded_without_effect": sum(
                    row["planned_outcome"] == "exclude" for row in rows
                ),
                **counts,
            },
            "verification": {
                "planned_targets_present": counts["completed_and_verified"],
                "original_locations_absent": counts["completed_and_verified"],
                "unplanned_targets": 0,
                "unplanned_renames": 0,
                "unverified_items": len(materialized)
                - counts["completed_and_verified"],
            },
            "metadata_preservation": {
                "profile": (
                    "same_filesystem_rename_v1"
                    if route == "same_filesystem_atomic_move"
                    else "cross_filesystem_user_metadata_v1"
                ),
                "content_verification": {
                    "profile": (
                        "filesystem_identity_and_location"
                        if route == "same_filesystem_atomic_move"
                        else "byte_for_byte"
                    ),
                    "result": "verified" if complete else "indeterminate",
                },
                "checked_attributes": checked_attributes,
                "unpreserved_attributes": discrepancy_values,
                "accepted_discrepancy_refs": accepted,
                "discrepancy_authorizations": authorizations,
            },
            "operation_ledger": {"kind": "inline", "items": operations},
            "created_directories": [
                {
                    "path": str(row["path"]),
                    "effect": "created_by_run",
                    "rewind_rule": "remove_only_if_empty_and_unchanged",
                }
                for row in directories
            ],
            "recovery": {
                "resume_count": int(run["resume_count"]),
                "recovered_item_refs": [
                    str(row["source_item_ref"])
                    for row in materialized
                    if row["recovery_fact"] is not None
                ],
                "rewind_window_ends_at": (
                    self.clock() + timedelta(hours=1)
                ).isoformat(),
            },
            "resource_facts": {
                "bytes_moved": sum(
                    int(row["bytes_moved"] or 0) for row in materialized
                ),
                "started_at": str(run["started_at"]),
                "ended_at": self._timestamp(),
            },
        }
        return {
            "sealed_content": sealed,
            "seal": {
                "encoding_profile": "mediasense-json-sha256-v1",
                "content_identity": content_identity(sealed),
                "sealed_at": self._timestamp(),
            },
        }

    @staticmethod
    def _receipt_execution_binding(
        run: sqlite3.Row, roots: list[sqlite3.Row], rows: list[sqlite3.Row]
    ) -> dict[str, object]:
        if run["direction"] == "rewind":
            return {
                "kind": "rewind",
                "rewind_of_receipt_ref": str(run["rewind_of_receipt_ref"]),
                "restored_source_parents": sorted(
                    {
                        str(Path(row["intended_target"]).parent)
                        for row in rows
                        if row["planned_outcome"] == "materialize"
                    }
                ),
            }
        return {
            "kind": "forward",
            "source_roots": [
                {
                    "source_root_ref": str(root["source_root_ref"]),
                    "current_root": str(root["current_root"]),
                    "observed_identity": str(root["observed_identity"]),
                }
                for root in roots
            ],
            "destination": {
                "parent": str(run["destination_parent"]),
                "resolved_logical_root": str(
                    Path(run["destination_parent"]) / str(run["logical_root"])
                ),
                "observed_identity": str(run["destination_observed_identity"]),
            },
        }

    @staticmethod
    def _operation_receipt(row: sqlite3.Row) -> dict[str, object]:
        result = str(row["execution_status"])
        if row["planned_outcome"] != "materialize":
            raise AssertionError("non-materialized item cannot enter operation ledger")
        source_after = str(row["source_after"] or "present")
        target_after = str(row["target_after"] or "absent")
        verification_result = str(row["postcondition_result"] or "indeterminate")
        value: dict[str, object] = {
            "source_item_ref": str(row["source_item_ref"]),
            "source_before": str(row["source_path"]),
            "intended_target": str(row["intended_target"]),
            "source_verification": {
                "profile": str(row["verification_profile"]),
                "result": "matched",
                "expected_basis": {
                    "value": str(row["expected_verification"]),
                    "size_bytes": int(row["observed_size"]),
                },
                "observed_basis": {
                    "value": str(row["observed_verification"]),
                    "size_bytes": int(row["observed_size"]),
                },
            },
            "result": result,
            "attempts": int(row["attempts"]),
            "source_after": source_after,
            "target_after": target_after,
            "verification": {
                "profile": str(row["postcondition_profile"] or "not_attempted"),
                "result": verification_result,
                "basis": str(
                    row["postcondition_basis"] or "Operation was not attempted."
                ),
            },
        }
        if row["execution_reason_code"] is not None:
            value["reason"] = {
                "code": str(row["execution_reason_code"]),
                "message": str(row["execution_reason_message"]),
            }
        if row["recovery_fact"] is not None:
            value["recovery_fact"] = str(row["recovery_fact"])
        return value

    def _run(self, connection: sqlite3.Connection, run_ref: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM runs WHERE run_ref = ?", (run_ref,)
        ).fetchone()
        if row is None:
            raise KeyError(run_ref)
        return row

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.run_store.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _timestamp(self) -> str:
        return self.clock().isoformat()
