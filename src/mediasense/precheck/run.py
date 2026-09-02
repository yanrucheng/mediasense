"""Durable public control surface for one mutable PreCheck Run."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sqlite3
from threading import Event, Thread
from uuid import uuid4

from mediasense.dataset_reference import dataset_id_from_ref

from ._run_sqlite import (
    RunDecisionError,
    RunExecutionConflict,
    RunIdempotencyConflict,
    RunStateConflict,
    SQLiteRunStore,
)
from ._orchestrator import (
    PrecheckExecutionConfig,
    PrecheckExecutionDependencies,
    PrecheckOrchestrator,
    _BlockedExecution,
)
from .accounting import AccountingStore
from .read import PrecheckReadTool
from .result import ResultDraft, ResultSealError, ResultStore


_ACTIONS = {"start", "status", "pause", "resume", "cancel"}
_ALLOWED_ACTIONS = {
    "running": ["pause", "cancel"],
    "paused": ["resume", "cancel"],
    "blocked": ["resume", "cancel"],
    "completed": [],
    "cancelled": [],
    "failed": [],
}
_PROGRESS_KEYS = {
    "discovered",
    "accounted",
    "usable",
    "exceptional",
    "unresolved",
}
_EXCEPTIONAL_CONDITIONS = {"unsupported", "invalid", "error"}
_PHASE_NAMES = {
    "queued": "queued",
    "accounting": "source_accounting",
    "metadata": "metadata",
    "renditions": "renditions",
    "video": "video",
    "gpx": "gpx",
    "embeddings": "embeddings",
    "sensitivity": "sensitivity",
    "bundles": "bundling",
    "compression": "compression",
    "external_evidence": "external_evidence",
    "publishing": "publishing",
    "sealing": "publishing",
}
_PHASE_CAPABILITIES = {
    "metadata": {"source-metadata"},
    "renditions": {"image-rendition"},
    "video": {"video-probe", "video-frame", "video-contact-sheet"},
    "gpx": {"gpx-location-candidate"},
    "embeddings": {"image-embedding", "video-key-frame-candidate"},
    "sensitivity": {"content-sensitivity"},
    "bundling": {"bundle-candidate"},
    "compression": {"adaptive-compression-group"},
    "external_evidence": {"reverse-geocode-observation"},
}
_CAPABILITY_PHASE = {
    capability: phase
    for phase, capabilities in _PHASE_CAPABILITIES.items()
    for capability in capabilities
}
_WORK_FAILURE_STATES = {
    "retryable_failure",
    "terminal_failure",
    "blocked",
}
_ERROR_PHASE_LIMIT = 5


class PrecheckRunTool:
    """Implement ``mediasense.precheck.run`` without exposing private Work state."""

    name = "mediasense.precheck.run"

    def __init__(
        self,
        database_path: Path,
        *,
        sqlite_timeout: float = 30,
        execution_config: PrecheckExecutionConfig | None = None,
        execution_dependencies: PrecheckExecutionDependencies | None = None,
        clock: Callable[[], datetime] | None = None,
        heartbeat_interval_seconds: float = 30,
        worker_stale_seconds: float = 120,
        progress_stale_seconds: float = 300,
    ) -> None:
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat interval must be positive")
        if worker_stale_seconds <= heartbeat_interval_seconds:
            raise ValueError("worker stale interval must exceed heartbeat interval")
        if progress_stale_seconds <= 0:
            raise ValueError("progress stale interval must be positive")
        self.database_path = Path(database_path)
        self._store = SQLiteRunStore(
            self.database_path,
            sqlite_timeout=sqlite_timeout,
            clock=clock,
        )
        self._reader = PrecheckReadTool(self.database_path)
        self._execution_config = execution_config or PrecheckExecutionConfig()
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._worker_stale_after = timedelta(seconds=worker_stale_seconds)
        self._progress_stale_after = timedelta(seconds=progress_stale_seconds)
        self._orchestrator = PrecheckOrchestrator(
            self.database_path,
            self,
            execution_dependencies,
        )

    def run(self, request: dict[str, object]) -> dict[str, object]:
        """Apply one public lifecycle operation and return its contract envelope."""

        if not isinstance(request, dict):
            raise ValueError("Run request must be an object")
        action = request.get("action")
        if action not in _ACTIONS:
            raise ValueError("action must be start, status, pause, resume, or cancel")
        action = str(action)
        try:
            _validate_request(action, request)
        except ValueError as error:
            return _error(action, "invalid_request", str(error))

        try:
            if action == "start":
                return self._start(request)
            run_ref = str(request["run_ref"])
            if action == "status":
                return self._status(run_ref)
            return self._control(action, run_ref, request.get("decision"))
        except sqlite3.Error:
            return _error(
                action,
                "operation_failed",
                "Durable Run state is temporarily unavailable.",
                (
                    str(request["run_ref"])
                    if isinstance(request.get("run_ref"), str)
                    else None
                ),
            )

    def record_progress(
        self, run_ref: str, progress: Mapping[str, object]
    ) -> dict[str, object]:
        """Persist exact business counters while the Run is progressing."""

        normalized = dict(progress)
        _validate_progress(normalized)
        record = self._store.set_progress(run_ref, normalized)
        return self._status_record(record)

    def record_phase(
        self,
        run_ref: str,
        phase: str,
        *,
        complete: bool = False,
        total: int | str | None = None,
    ) -> None:
        """Persist one coarse execution boundary, never one write per source item."""

        if phase not in _PHASE_NAMES or phase == "queued":
            raise ValueError(f"unknown execution phase: {phase}")
        self._store.set_execution_checkpoint(
            run_ref,
            phase,
            complete=complete,
            total=total,
        )

    def bind_working_run(
        self, run_ref: str, accounting_run_id: str
    ) -> dict[str, object]:
        """Bind execution to the one accounting Run for the same Dataset."""

        if not accounting_run_id.strip():
            raise ValueError("accounting_run_id must be non-empty")
        self._store.bind_accounting_run(run_ref, accounting_run_id)
        return self.sync_accounting(run_ref)

    def sync_accounting(self, run_ref: str) -> dict[str, object]:
        """Project durable accounting facts into public business progress."""

        current = self._store.get(run_ref)
        if current["state"] in {"completed", "cancelled", "failed"}:
            return self._status_record(current)
        progress, accounting_state, blocked_reason = self._store.accounting_progress(
            run_ref
        )
        record = self._store.set_progress(run_ref, progress)
        if accounting_state == "blocked" and record["state"] == "running":
            record = self._store.mark_blocked(
                run_ref,
                _reason(
                    str(blocked_reason or "source_unavailable"),
                    "Source accounting is blocked.",
                    resume_when="The required source condition is available again.",
                ),
            )
        elif accounting_state == "paused" and record["state"] == "running":
            record = self._store.mark_interrupted(run_ref)
        return self._status_record(record)

    def require_confirmation(
        self,
        run_ref: str,
        *,
        summary: str,
        quantity: int,
        unit: str,
        skip_allowed: bool,
        pending_fingerprint: str,
    ) -> dict[str, object]:
        """Pause before one exact, frozen optional work set may cause effects."""

        if not summary.strip():
            raise ValueError("confirmation summary must be non-empty")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            raise ValueError("confirmation quantity must be a positive integer")
        if not unit.strip():
            raise ValueError("confirmation unit must be non-empty")
        if not isinstance(skip_allowed, bool):
            raise ValueError("confirmation skip_allowed must be boolean")
        if not pending_fingerprint.strip():
            raise ValueError("pending_fingerprint must be non-empty")
        confirmation = {
            "summary": summary,
            "quantity": quantity,
            "unit": unit,
            "skip_allowed": skip_allowed,
        }
        record, _paused = self._store.pause_for_confirmation(
            run_ref,
            confirmation=confirmation,
            fingerprint=pending_fingerprint,
        )
        return self._status_record(record)

    def confirmation_decision(
        self, run_ref: str, *, pending_fingerprint: str
    ) -> str | None:
        """Return authorization only when it names the same frozen work set."""

        record = self._store.get(run_ref)
        if record["confirmation_fingerprint"] != pending_fingerprint:
            return None
        decision = record["confirmation_decision"]
        return None if decision is None else str(decision)

    def current_state(self, run_ref: str) -> str:
        """Return the durable state used by cooperative workers."""

        return str(self._store.get(run_ref)["state"])

    def mark_blocked(
        self,
        run_ref: str,
        *,
        code: str,
        message: str,
        resume_when: str,
    ) -> dict[str, object]:
        reason = _reason(code, message, resume_when=resume_when)
        return self._status_record(self._store.mark_blocked(run_ref, reason))

    def mark_interrupted(
        self, run_ref: str, *, message: str | None = None
    ) -> dict[str, object]:
        return self._status_record(
            self._store.mark_interrupted(run_ref, message=message)
        )

    def advance(self, run_ref: str) -> dict[str, object]:
        """Continue one source-bound Run through its durable producer graph."""

        try:
            record = self._store.get(run_ref)
        except KeyError:
            return _error("status", "run_not_found", "Run does not exist", run_ref)
        if record["state"] != "running":
            return self._status_record(record)
        accounting_run_id = record["accounting_run_id"]
        if accounting_run_id is None:
            accounting_run_id = self._store.unfinished_accounting_run(
                dataset_id_from_ref(record["dataset_ref"])
            )
            if accounting_run_id is None:
                return self._status_record(record)
            self._store.bind_accounting_run(run_ref, accounting_run_id)
        configuration = record["execution_config"]
        if configuration is None:
            configuration = self._resolved_execution_config(
                str(accounting_run_id)
            ).value()
            self._store.configure_execution(run_ref, configuration)
        worker_token = uuid4().hex
        if not self._store.claim_execution_worker(
            run_ref,
            worker_token,
            stale_after=self._worker_stale_after,
        ):
            return self._status_record(self._store.get(run_ref))
        heartbeat_stop = Event()
        heartbeat = Thread(
            target=self._heartbeat_worker,
            args=(run_ref, worker_token, heartbeat_stop),
            name=f"mediasense-heartbeat-{run_ref}",
            daemon=True,
        )
        heartbeat.start()
        try:
            try:
                config = PrecheckExecutionConfig.from_value(configuration)
                result = self._orchestrator.advance(
                    run_ref, str(accounting_run_id), config
                )
            except _BlockedExecution as error:
                result = self.mark_blocked(
                    run_ref,
                    code=error.code,
                    message=error.message,
                    resume_when=error.resume_when,
                )
            except (RunExecutionConflict, ValueError, OSError):
                result = self.mark_blocked(
                    run_ref,
                    code="execution_prerequisite_unavailable",
                    message="A required local execution prerequisite is unavailable.",
                    resume_when=(
                        "Correct the execution prerequisite and resume this Run."
                    ),
                )
            except Exception:
                current = self._store.get(run_ref)
                if current["state"] != "running":
                    result = self._status_record(current)
                else:
                    result = self.mark_interrupted(
                        run_ref,
                        message="The execution worker stopped unexpectedly.",
                    )
            except BaseException:
                current = self._store.get(run_ref)
                if current["state"] == "running":
                    self.mark_interrupted(
                        run_ref,
                        message="The execution worker stopped unexpectedly.",
                    )
                raise
            if self._store.get(run_ref)["state"] == "running":
                return self.mark_interrupted(
                    run_ref,
                    message=(
                        "The execution worker ended before reaching an attention "
                        "or terminal state."
                    ),
                )
            return result
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
            try:
                self._store.release_execution_worker(run_ref, worker_token)
            except sqlite3.Error:
                pass

    def _heartbeat_worker(
        self,
        run_ref: str,
        worker_token: str,
        stop: Event,
    ) -> None:
        while not stop.wait(self._heartbeat_interval_seconds):
            try:
                if not self._store.heartbeat_execution_worker(run_ref, worker_token):
                    return
            except sqlite3.Error:
                continue

    def _prepare_execution(
        self, record: Mapping[str, object], *, dataset_id: str
    ) -> None:
        """Bind and configure a new Run without starting long-running work."""

        accounting_run_id = self._store.unfinished_accounting_run(dataset_id)
        if accounting_run_id is None:
            return
        run_ref = str(record["run_ref"])
        self._store.bind_accounting_run(run_ref, accounting_run_id)
        self._store.configure_execution(
            run_ref,
            self._resolved_execution_config(accounting_run_id).value(),
        )

    def _resolved_execution_config(
        self, accounting_run_id: str
    ) -> PrecheckExecutionConfig:
        attachment = AccountingStore(self.database_path).get_source_attachment(
            accounting_run_id
        )
        return self._execution_config.resolve_resources(
            source_root=attachment.source_root
        )

    def mark_failed(
        self, run_ref: str, *, code: str, message: str
    ) -> dict[str, object]:
        reason = _reason(code, message)
        return self._status_record(self._store.mark_failed(run_ref, reason))

    def complete_with_result(self, run_ref: str, result_ref: str) -> dict[str, object]:
        """Atomically bind completion only after the sealed Result verifies."""

        try:
            record = self._store.get(run_ref)
        except KeyError:
            return _error("status", "run_not_found", "Run does not exist", run_ref)
        verified = self._verified_result(result_ref)
        if isinstance(verified, str):
            failed = self._store.mark_failed(
                run_ref,
                _reason("result_untrusted", verified),
            )
            return self._status_record(failed)
        result_view, package = verified
        if result_view["dataset_ref"] != record["dataset_ref"]:
            failed = self._store.mark_failed(
                run_ref,
                _reason(
                    "result_dataset_mismatch",
                    "The sealed Result belongs to a different Dataset.",
                ),
            )
            return self._status_record(failed)
        progress = _completed_progress(record["progress"], package, result_ref)
        self._store.set_progress(run_ref, progress)
        published = {
            "result_ref": result_ref,
            "coverage": result_view["coverage"],
            "readiness": result_view["readiness"],
            "integrity": result_view["integrity"],
        }
        completed = self._store.set_completed(run_ref, published)
        return self._status_record(completed)

    def publish_result(self, run_ref: str, draft: ResultDraft) -> dict[str, object]:
        """Internal automatic seal path; it is deliberately not a public action."""

        try:
            record = self._store.get(run_ref)
        except KeyError:
            return _error("status", "run_not_found", "Run does not exist", run_ref)
        if record["state"] != "running":
            return _invalid_state("status", run_ref, record)
        if record["accounting_run_id"] != draft.run_id:
            return self.mark_failed(
                run_ref,
                code="result_run_mismatch",
                message="Result draft does not belong to this Run's accounting state.",
            )
        try:
            result_ref = (
                "precheck-result:" + hashlib.sha256(run_ref.encode("utf-8")).hexdigest()
            )
            sealed = ResultStore(self.database_path).seal(
                draft,
                result_ref=result_ref,
            )
        except ResultSealError as error:
            return self.mark_failed(
                run_ref,
                code="result_validation_failed",
                message=str(error) or "Result validation failed.",
            )
        except OSError:
            return self.mark_blocked(
                run_ref,
                code="workspace_write_failed",
                message="Result publication could not write the workspace.",
                resume_when="Workspace storage is writable with sufficient free space.",
            )
        return self.complete_with_result(run_ref, sealed.result_ref)

    def _start(self, request: dict[str, object]) -> dict[str, object]:
        try:
            replay = self._store.replay_start(request)
        except RunIdempotencyConflict:
            return _error(
                "start",
                "idempotency_conflict",
                "request_id was already used with different start inputs",
            )
        if replay is not None:
            return _start_response(replay)

        prior_result_ref = request.get("prior_result_ref")
        if prior_result_ref is None:
            dataset_ref = str(request["dataset_ref"])
            dataset_id = dataset_id_from_ref(dataset_ref)
            if not self._store.dataset_exists(dataset_id):
                return _error("start", "dataset_not_found", "Dataset does not exist")
        else:
            result_ref = str(prior_result_ref)
            verified = self._verified_result(result_ref)
            if isinstance(verified, str):
                code = (
                    "result_not_found"
                    if verified == "Result does not exist"
                    else "result_untrusted"
                )
                return _error("start", code, verified)
            result_view, _package = verified
            dataset_ref = str(result_view["dataset_ref"])
            dataset_id = dataset_id_from_ref(dataset_ref)
            if not self._store.dataset_exists(dataset_id):
                return _error(
                    "start",
                    "dataset_not_found",
                    "The prior Result's Dataset does not exist in this workspace",
                )
        try:
            record, _created = self._store.start(
                request,
                dataset_ref=dataset_ref,
                prior_result_ref=(
                    None if prior_result_ref is None else str(prior_result_ref)
                ),
            )
        except RunIdempotencyConflict:
            return _error(
                "start",
                "idempotency_conflict",
                "request_id was already used with different start inputs",
            )
        self._prepare_execution(record, dataset_id=dataset_id)
        return _start_response(record)

    def _status(self, run_ref: str) -> dict[str, object]:
        try:
            record = self._store.get(run_ref)
        except KeyError:
            return _error("status", "run_not_found", "Run does not exist", run_ref)
        if record["state"] != "completed" and record["accounting_run_id"] is not None:
            progress, _accounting_state, _blocked_reason = (
                self._store.accounting_progress(run_ref)
            )
            record = {**record, "progress": progress}
        if record["state"] == "completed":
            published = record["published_result"]
            if not isinstance(published, dict):
                return _error(
                    "status",
                    "operation_failed",
                    "Completed Run has no published Result record",
                    run_ref,
                )
            verified = self._verified_result(str(published["result_ref"]))
            if isinstance(verified, str):
                return _error("status", "result_untrusted", verified, run_ref)
            result_view, _package = verified
            current = {
                "result_ref": result_view["ref"],
                "coverage": result_view["coverage"],
                "readiness": result_view["readiness"],
                "integrity": result_view["integrity"],
            }
            if current != published:
                return _error(
                    "status",
                    "result_untrusted",
                    "Published Result projection no longer matches its sealed bytes",
                    run_ref,
                )
        return self._status_record(record)

    def _control(
        self, action: str, run_ref: str, decision: object
    ) -> dict[str, object]:
        normalized_decision = None if decision is None else str(decision)
        try:
            if action == "pause":
                observed, _current = self._store.request_pause(run_ref)
                target = "paused"
            elif action == "resume":
                observed, _current = self._store.request_resume(
                    run_ref, decision=normalized_decision
                )
                target = "running"
            else:
                observed, _current = self._store.request_cancel(run_ref)
                target = "cancelled"
        except KeyError:
            return _error(action, "run_not_found", "Run does not exist", run_ref)
        except RunDecisionError as error:
            return _error(action, "invalid_request", str(error), run_ref)
        except RunStateConflict as error:
            return _invalid_state(action, run_ref, error.record)
        response: dict[str, object] = {
            "outcome": "accepted",
            "action": action,
            "run_ref": run_ref,
            "observed_state": observed["state"],
            "target_state": target,
        }
        if action == "resume" and normalized_decision is not None:
            response["decision"] = normalized_decision
        return response

    def _verified_result(
        self, result_ref: str
    ) -> tuple[dict[str, object], dict[str, object]] | str:
        loaded = self._reader._load(result_ref)
        if isinstance(loaded, dict):
            error = loaded.get("error")
            if isinstance(error, dict) and error.get("code") == "result_not_found":
                return "Result does not exist"
            message = error.get("message") if isinstance(error, dict) else None
            return str(message or "sealed Result cannot be trusted")
        package, _digest = loaded
        if not isinstance(package, dict) or not isinstance(package.get("result"), dict):
            return "sealed Result has an invalid package shape"
        result_view = package["result"]
        required = {"ref", "dataset_ref", "coverage", "readiness", "integrity"}
        if not required <= set(result_view):
            return "sealed Result is missing required status fields"
        if result_view["ref"] != result_ref or result_view["integrity"] != "valid":
            return "sealed Result does not provide valid integrity"
        return result_view, package

    def _status_record(self, record: dict[str, object]) -> dict[str, object]:
        response: dict[str, object] = {
            "outcome": "ok",
            "action": "status",
            "run_ref": record["run_ref"],
            "dataset_ref": record["dataset_ref"],
            "state": record["state"],
            "progress": record["progress"],
            "activity": self._activity_record(record),
            "allowed_actions": list(_ALLOWED_ACTIONS[str(record["state"])]),
        }
        if record["prior_result_ref"] is not None:
            response["prior_result_ref"] = record["prior_result_ref"]
        if record["state"] in {"paused", "blocked", "failed"}:
            response["reason"] = record["reason"]
        if record["state"] == "paused" and record["confirmation"] is not None:
            response["confirmation"] = record["confirmation"]
        if record["state"] == "completed":
            response["published_result"] = record["published_result"]
        return response

    def _activity_record(self, record: dict[str, object]) -> dict[str, object]:
        checkpoint = record["execution_checkpoint"]
        assert isinstance(checkpoint, dict)
        internal_phase = str(checkpoint["phase"])
        phase = _PHASE_NAMES.get(internal_phase, "unknown")
        facts = self._store.execution_facts(
            None
            if record["accounting_run_id"] is None
            else str(record["accounting_run_id"])
        )
        work, work_last_progress_at = _phase_work_progress(
            internal_phase,
            complete=bool(checkpoint["complete"]),
            total_hint=checkpoint["total"],
            facts=facts,
            run_state=str(record["state"]),
        )
        last_progress_at = _latest_timestamp(
            str(checkpoint["last_progress_at"]), work_last_progress_at
        )
        if record["state"] == "completed":
            phase = "complete"
            last_progress_at = _latest_timestamp(
                last_progress_at, str(record["updated_at"])
            )
        activity_state = self._activity_state(
            record,
            last_progress_at=last_progress_at,
        )
        return {
            "state": activity_state,
            "phase": phase,
            "work": work,
            "last_progress_at": last_progress_at,
            "errors": _error_summary(facts),
        }

    def _activity_state(
        self,
        record: Mapping[str, object],
        *,
        last_progress_at: str,
    ) -> str:
        state = str(record["state"])
        if state in {"completed", "cancelled", "failed"}:
            return "finished"
        if state == "blocked":
            return "waiting"
        if state == "paused":
            reason = record.get("reason")
            if (
                isinstance(reason, dict)
                and reason.get("code") == "confirmation_required"
            ):
                return "waiting"
            return "paused"
        checkpoint = record["execution_checkpoint"]
        assert isinstance(checkpoint, dict)
        worker = checkpoint.get("worker")
        if not isinstance(worker, dict) or not isinstance(
            worker.get("heartbeat_at"), str
        ):
            return "queued"
        now = _as_datetime(self._store.now())
        if now - _as_datetime(str(worker["heartbeat_at"])) > self._worker_stale_after:
            return "suspected_stalled"
        if (
            last_progress_at != "unknown"
            and now - _as_datetime(last_progress_at) > self._progress_stale_after
        ):
            return "no_recent_progress"
        return "working"


def _phase_work_progress(
    phase: str,
    *,
    complete: bool,
    total_hint: object,
    facts: Mapping[str, object],
    run_state: str,
) -> tuple[dict[str, object], str | None]:
    if phase == "queued":
        return _work_counts(0, 0, 0, "unknown", "unknown"), None
    if phase == "accounting":
        accounting = facts.get("accounting")
        if not isinstance(accounting, dict):
            return _unknown_work_counts(), None
        counts = accounting.get("counts")
        if not isinstance(counts, dict):
            return _unknown_work_counts(), str(accounting["last_progress_at"])
        completed = int(counts.get("new", 0)) + int(counts.get("changed", 0))
        reused = int(counts.get("reused", 0))
        failed = int(counts.get("error", 0))
        observed = completed + reused + failed
        finished = complete or accounting.get("state") == "completed"
        return (
            _work_counts(
                completed,
                reused,
                failed,
                0 if finished else "unknown",
                observed if finished else "unknown",
            ),
            str(accounting["last_progress_at"]),
        )
    if phase == "publishing":
        completed = int(run_state == "completed")
        return _work_counts(completed, 0, 0, 1 - completed, 1), None

    capabilities = _PHASE_CAPABILITIES.get(_PHASE_NAMES.get(phase, "unknown"), set())
    rows = facts.get("work")
    if not isinstance(rows, tuple):
        return _unknown_work_counts(), None
    completed = reused = failed = 0
    observed = 0
    last_progress_at: str | None = None
    for row in rows:
        if not isinstance(row, dict) or row.get("capability") not in capabilities:
            continue
        count = int(row["count"])
        observed += count
        status = str(row["status"])
        if status == "succeeded":
            if row["attempted_here"]:
                completed += count
            else:
                reused += count
        elif status in _WORK_FAILURE_STATES:
            failed += count
        last_progress_at = _latest_timestamp(
            last_progress_at, str(row["last_progress_at"])
        )
    settled = completed + reused + failed
    if complete:
        total = max(observed, settled)
        remaining: int | str = max(total - settled, 0)
    elif isinstance(total_hint, int) and not isinstance(total_hint, bool):
        total = max(total_hint, observed, settled)
        remaining = max(total - settled, 0)
    else:
        total = "unknown"
        remaining = "unknown"
    return (
        _work_counts(completed, reused, failed, remaining, total),
        last_progress_at,
    )


def _error_summary(facts: Mapping[str, object]) -> dict[str, object]:
    rows = facts.get("work")
    counts: dict[str, int] = {}
    if isinstance(rows, tuple):
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("status") not in _WORK_FAILURE_STATES
            ):
                continue
            phase = _CAPABILITY_PHASE.get(str(row.get("capability")), "unknown")
            counts[phase] = counts.get(phase, 0) + int(row["count"])
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    shown = ordered[:_ERROR_PHASE_LIMIT]
    return {
        "total": sum(counts.values()),
        "by_phase": [{"phase": phase, "count": count} for phase, count in shown],
        "truncated": len(ordered) > len(shown),
    }


def _work_counts(
    completed: int | str,
    reused: int | str,
    failed: int | str,
    remaining: int | str,
    total: int | str,
) -> dict[str, object]:
    return {
        "completed": completed,
        "reused": reused,
        "failed": failed,
        "remaining": remaining,
        "total": total,
    }


def _unknown_work_counts() -> dict[str, object]:
    return _work_counts("unknown", "unknown", "unknown", "unknown", "unknown")


def _latest_timestamp(left: str | None, right: str | None) -> str:
    known = [value for value in (left, right) if value not in {None, "unknown"}]
    if not known:
        return "unknown"
    return max(known, key=_as_datetime)


def _as_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Run timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_request(action: str, request: dict[str, object]) -> None:
    allowed = {
        "start": {"action", "dataset_ref", "prior_result_ref", "request_id"},
        "status": {"action", "run_ref"},
        "pause": {"action", "run_ref"},
        "resume": {"action", "run_ref", "decision"},
        "cancel": {"action", "run_ref"},
    }[action]
    if unknown := set(request) - allowed:
        raise ValueError(f"unknown request fields: {sorted(unknown)}")
    if action == "start":
        _require_ref(request.get("request_id"), "request:", "request_id")
        upstream = [
            key for key in ("dataset_ref", "prior_result_ref") if key in request
        ]
        if len(upstream) != 1:
            raise ValueError("start requires exactly one upstream reference")
        field = upstream[0]
        if field == "dataset_ref":
            dataset_id_from_ref(request[field])
        else:
            _require_ref(request[field], "precheck-result:", field)
        return
    _require_ref(request.get("run_ref"), "precheck-run:", "run_ref")
    if action == "resume" and "decision" in request:
        if request["decision"] not in {"proceed", "skip_optional_work"}:
            raise ValueError("decision must be proceed or skip_optional_work")


def _require_ref(value: object, prefix: str, field: str) -> None:
    if (
        not isinstance(value, str)
        or not value.startswith(prefix)
        or len(value) == len(prefix)
        or any(character.isspace() for character in value)
    ):
        raise ValueError(f"{field} must be a valid {prefix[:-1]} reference")


def _validate_progress(progress: dict[str, object]) -> None:
    if set(progress) != _PROGRESS_KEYS:
        raise ValueError("progress must contain exactly the five public counters")
    for key, value in progress.items():
        if value == "unknown":
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"progress.{key} must be nonnegative or unknown")
    accounted = progress["accounted"]
    buckets = [progress[key] for key in ("usable", "exceptional", "unresolved")]
    known_buckets = [value for value in buckets if isinstance(value, int)]
    if isinstance(accounted, int):
        if sum(known_buckets) > accounted:
            raise ValueError("known condition buckets exceed accounted")
        if len(known_buckets) == 3 and sum(known_buckets) != accounted:
            raise ValueError("known condition buckets must close accounted")
    discovered = progress["discovered"]
    if (
        isinstance(discovered, int)
        and isinstance(accounted, int)
        and accounted > discovered
    ):
        raise ValueError("accounted cannot exceed discovered")


def _completed_progress(
    current: object,
    package: dict[str, object],
    result_ref: str,
) -> dict[str, object]:
    if not isinstance(current, dict):
        raise ValueError("Run progress is invalid")
    relationships = package.get("relationships")
    if not isinstance(relationships, list):
        raise ValueError("sealed Result relationships are invalid")
    accounts = [
        item
        for item in relationships
        if isinstance(item, dict)
        and item.get("origin") == result_ref
        and item.get("relation") == "accounts_for"
        and isinstance(item.get("member"), dict)
    ]
    conditions = [item["member"].get("condition") for item in accounts]
    allowed_conditions = {"usable", *_EXCEPTIONAL_CONDITIONS, "unresolved"}
    if any(condition not in allowed_conditions for condition in conditions):
        raise ValueError("sealed Result contains an invalid accounting condition")
    discovered = current.get("discovered", "unknown")
    progress = {
        "discovered": discovered,
        "accounted": len(accounts),
        "usable": conditions.count("usable"),
        "exceptional": sum(
            condition in _EXCEPTIONAL_CONDITIONS for condition in conditions
        ),
        "unresolved": conditions.count("unresolved"),
    }
    _validate_progress(progress)
    return progress


def _start_response(record: dict[str, object]) -> dict[str, object]:
    response: dict[str, object] = {
        "outcome": "ok",
        "action": "start",
        "run_ref": record["run_ref"],
        "dataset_ref": record["dataset_ref"],
        "state": "running",
    }
    if record["prior_result_ref"] is not None:
        response["prior_result_ref"] = record["prior_result_ref"]
    return response


def _reason(
    code: str, message: str, *, resume_when: str | None = None
) -> dict[str, object]:
    if not code or not message:
        raise ValueError("reason code and message must be non-empty")
    reason: dict[str, object] = {"code": code, "message": message}
    if resume_when is not None:
        if not resume_when:
            raise ValueError("resume_when must be non-empty")
        reason["resume_when"] = resume_when
    return reason


def _invalid_state(
    action: str, run_ref: str, record: dict[str, object]
) -> dict[str, object]:
    state = str(record["state"])
    return _error(
        action,
        "invalid_state",
        f"A {state} Run cannot {action}.",
        run_ref,
        current_state=state,
        allowed_actions=_ALLOWED_ACTIONS[state],
    )


def _error(
    action: str,
    code: str,
    message: str,
    run_ref: str | None = None,
    *,
    current_state: str | None = None,
    allowed_actions: list[str] | None = None,
) -> dict[str, object]:
    detail: dict[str, object] = {"code": code, "message": message}
    if current_state is not None:
        detail["current_state"] = current_state
    if allowed_actions is not None:
        detail["allowed_actions"] = list(allowed_actions)
    response: dict[str, object] = {
        "outcome": "error",
        "action": action,
        "error": detail,
    }
    if run_ref is not None:
        response["run_ref"] = run_ref
    return response


__all__ = ["PrecheckRunTool"]
