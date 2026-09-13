"""Durable public control surface for one mutable PreCheck Run."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
from threading import Event, Thread
from uuid import uuid4

from mediasense.dataset_reference import dataset_id_from_ref, dataset_ref_from_id

from ._run_sqlite import (
    RunAlreadyActive,
    RunBindingError,
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
from .read import PrecheckReadTool, _ReadFailure, _ResultGraph
from .result import ResultDraft, ResultSealError, ResultStore
from .scope_review import (
    ScopeSelectionError,
    build_scope_inventory,
    normalize_scope_path,
    selection_digest,
    validate_scope_selection,
)


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
    "accounting": "source_accounting",
    "scope_review": "scope_review",
    "metadata": "metadata",
    "renditions": "renditions",
    "video": "video",
    "gpx": "gpx",
    "embeddings": "embeddings",
    "sensitivity": "sensitivity",
    "bundles": "bundling",
    "compression": "compression",
    "external_evidence": "geo",
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
    "geo": {"reverse-geocode-observation"},
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
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PrecheckConfirmationContext:
    principal_ref: str
    confirmed_content_identity: str
    confirmed_at: datetime

    def value(self) -> dict[str, str]:
        return {
            "principal_ref": self.principal_ref,
            "confirmed_content_identity": self.confirmed_content_identity,
            "confirmed_at": self.confirmed_at.isoformat(),
        }


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
        reader: PrecheckReadTool | None = None,
    ) -> None:
        if heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat interval must be positive")
        if worker_stale_seconds <= heartbeat_interval_seconds:
            raise ValueError("worker stale interval must exceed heartbeat interval")
        if progress_stale_seconds <= 0:
            raise ValueError("progress stale interval must be positive")
        self.database_path = Path(database_path)
        if (
            reader is not None
            and reader.database_path.resolve() != self.database_path.resolve()
        ):
            raise ValueError("Run and Reader must use the same Dataset store")
        self._store = SQLiteRunStore(
            self.database_path,
            sqlite_timeout=sqlite_timeout,
            clock=clock,
        )
        self._reader = (
            reader if reader is not None else PrecheckReadTool(self.database_path)
        )
        self._execution_config = execution_config or PrecheckExecutionConfig()
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._worker_stale_after = timedelta(seconds=worker_stale_seconds)
        self._progress_stale_after = timedelta(seconds=progress_stale_seconds)
        self._orchestrator = PrecheckOrchestrator(
            self.database_path,
            self,
            execution_dependencies,
        )

    def run(
        self,
        request: dict[str, object],
        *,
        confirmation: PrecheckConfirmationContext | None = None,
    ) -> dict[str, object]:
        """Apply one public lifecycle operation and return its contract envelope."""

        from mediasense.runtime.resources import contract_validator

        if not contract_validator(self.name).is_valid(request):
            return _error("", "invalid_request", "Invalid flat PreCheck Run request.")
        try:
            action = str(request["action"])
            if action == "start":
                return self._start(request)
            run_ref = str(request["run_ref"])
            try:
                record = self._store.get(run_ref)
            except KeyError:
                return _error(action, "run_not_found", "Run does not exist.")
            if record["dataset_ref"] != request["dataset_ref"]:
                return _error(
                    action, "run_not_found", "Run does not exist in this Dataset."
                )
            if action == "status":
                return self._status(
                    run_ref,
                    scope_path=request.get("scope_path"),
                    scope_after=request.get("scope_after"),
                    include=request.get("include", []),
                    page=request.get("page"),
                )
            return self._control(
                action, run_ref, request.get("decision"), confirmation=confirmation
            )

        except sqlite3.OperationalError as error:
            if error.sqlite_errorcode not in {
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            }:
                raise
            return _error(
                str(request["action"]),
                "operation_failed",
                "Durable Run state is temporarily locked.",
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

        if phase not in _PHASE_NAMES:
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
        disclosure: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        """Pause before one exact, frozen work set may cause external effects."""

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
            "kind": "external_effect",
            "summary": summary,
            "quantity": quantity,
            "unit": unit,
            "skip_allowed": skip_allowed,
            "content_identity": "sha256:"
            + hashlib.sha256(
                json.dumps(
                    dict(disclosure or {}),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
        }
        if disclosure is not None:
            confirmation["disclosure"] = dict(disclosure)
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

    def confirmation_authority(
        self, run_ref: str, *, pending_fingerprint: str
    ) -> Mapping[str, object] | None:
        record = self._store.get(run_ref)
        if record["confirmation_fingerprint"] != pending_fingerprint:
            return None
        confirmation = record.get("confirmation")
        if not isinstance(confirmation, Mapping):
            return None
        authority = confirmation.get("accepted_authority")
        return authority if isinstance(authority, Mapping) else None

    def scope_selection_submitted(self, run_ref: str) -> bool:
        review = self._store.latest_scope_review(run_ref)
        return review is not None and review["state"] in {"accepted", "reused"}

    def require_scope_selection(
        self,
        run_ref: str,
        accounting_run_id: str,
    ) -> dict[str, object]:
        """Pause for or apply one exact factual source-scope selection."""

        accounting = AccountingStore(self.database_path)
        inventory = self._scope_inventory(accounting_run_id)
        fingerprint = str(inventory["inventory_fingerprint"])
        summary = accounting.get_run_summary(accounting_run_id)
        record, selection = self._store.ensure_scope_review(
            run_ref,
            accounting_run_id=accounting_run_id,
            scan_generation=summary.scan_generation,
            inventory_fingerprint=fingerprint,
            summary=inventory,
        )
        if selection is None:
            return self._status_record(record)
        normalized = validate_scope_selection(
            selection,
            inventory_fingerprint_value=fingerprint,
            existing_paths=(
                str(fact["relative_path"])
                for fact in accounting.iter_scope_inventory_facts(accounting_run_id)
            ),
        )
        accounting.apply_scope_selection(
            accounting_run_id,
            normalized,
            selection_digest=selection_digest(normalized),
        )
        return self._status_record(self._store.get(run_ref))

    def current_state(self, run_ref: str) -> str:
        """Return the durable state used by cooperative workers."""

        return self._store.current_state(run_ref)

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

        worker_token, status = self.claim_execution(run_ref)
        if worker_token is None:
            return status
        return self.advance_claimed(run_ref, worker_token)

    def claim_execution(self, run_ref: str) -> tuple[str | None, dict[str, object]]:
        """Claim execution before a Host reports that this Run is running."""

        try:
            record = self._store.get(run_ref)
        except KeyError:
            return None, _error(
                "status", "run_not_found", "Run does not exist", run_ref
            )
        if record["state"] != "running":
            return None, self._status_record(record)
        accounting_run_id = record["accounting_run_id"]
        if accounting_run_id is None:
            accounting_run_id = self._store.unfinished_accounting_run(
                dataset_id_from_ref(record["dataset_ref"])
            )
            if accounting_run_id is None:
                failed = self.mark_failed(
                    run_ref,
                    code="execution_not_prepared",
                    message=(
                        "The Run has no source-accounting work to execute. "
                        "Execution was not started."
                    ),
                )
                return None, failed
            self._store.bind_accounting_run(run_ref, accounting_run_id)
        configuration = record["execution_config"]
        if configuration is None:
            try:
                configuration = self._resolved_execution_config(
                    str(accounting_run_id)
                ).value()
                self._store.configure_execution(run_ref, configuration)
            except (RunExecutionConflict, ValueError, OSError):
                _LOGGER.exception(
                    "PreCheck execution initialization failed for %s", run_ref
                )
                failed = self.mark_failed(
                    run_ref,
                    code="execution_initialization_failed",
                    message=(
                        "The execution configuration could not be initialized. "
                        "Execution was not started."
                    ),
                )
                return None, failed
        worker_token = uuid4().hex
        if not self._store.claim_execution_worker(
            run_ref,
            worker_token,
            stale_after=self._worker_stale_after,
        ):
            return None, self._status_record(self._store.get(run_ref))
        return worker_token, self._status_record(self._store.get(run_ref))

    def advance_claimed(self, run_ref: str, worker_token: str) -> dict[str, object]:
        """Advance a Run whose worker lease was acquired before dispatch."""

        record = self._store.get(run_ref)
        if record["state"] != "running":
            return self._status_record(record)
        checkpoint = record["execution_checkpoint"]
        assert isinstance(checkpoint, dict)
        worker = checkpoint.get("worker")
        if not isinstance(worker, dict) or worker.get("token") != worker_token:
            return self._status_record(record)
        accounting_run_id = record["accounting_run_id"]
        configuration = self._store.execution_configuration(run_ref)
        if not isinstance(accounting_run_id, str) or not isinstance(
            configuration, dict
        ):
            return self.mark_failed(
                run_ref,
                code="execution_not_prepared",
                message=(
                    "The claimed worker has no complete execution preparation. "
                    "Execution was stopped."
                ),
            )
        heartbeat_stop = Event()
        heartbeat = Thread(
            target=self._heartbeat_worker,
            args=(run_ref, worker_token, heartbeat_stop),
            name=f"mediasense-heartbeat-{run_ref}",
            daemon=True,
        )
        heartbeat.start()
        from ._snapshot import SourceSnapshotChanged

        try:
            try:
                config = PrecheckExecutionConfig.from_value(configuration)
                result = self._orchestrator.advance(
                    run_ref, str(accounting_run_id), config
                )
            except SourceSnapshotChanged as error:
                result = self.mark_failed(run_ref, code="source_snapshot_changed", message=str(error))
            except _BlockedExecution as error:
                result = self.mark_blocked(
                    run_ref,
                    code=error.code,
                    message=error.message,
                    resume_when=error.resume_when,
                )
            except (RunExecutionConflict, ValueError, OSError):
                _LOGGER.exception("PreCheck execution failed for %s", run_ref)
                result = self.mark_failed(
                    run_ref,
                    code="execution_failed",
                    message="PreCheck execution failed before reaching a safe boundary.",
                )
            except Exception:
                _LOGGER.exception("PreCheck execution failed for %s", run_ref)
                self.mark_failed(
                    run_ref,
                    code="execution_worker_crashed",
                    message="Unexpected implementation failure; inspect the Host diagnostic before retrying.",
                )
                raise
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

    def prepare_execution(
        self,
        run_ref: str,
        *,
        dataset_id: str,
        source_root: Path | None = None,
        rebind_reason: str | None = None,
    ) -> None:
        """Prepare the exact bound accounting Run without starting long work.

        An unbound newly-created public Run may adopt the Dataset's unfinished
        accounting Run. Once bound, every resume stays on that same Run.
        """

        record = self._store.get(run_ref)
        expected_dataset_ref = dataset_ref_from_id(dataset_id)
        if record["dataset_ref"] != expected_dataset_ref:
            raise RunBindingError(
                "public Run belongs to a different Dataset than execution preparation"
            )
        accounting_run_id = record["accounting_run_id"]
        if not isinstance(accounting_run_id, str):
            accounting_run_id = self._store.unfinished_accounting_run(dataset_id)
            if accounting_run_id is None:
                return
        self._store.bind_accounting_run(run_ref, accounting_run_id)
        if source_root is not None:
            AccountingStore(self.database_path).resume_run_attachment(
                accounting_run_id,
                source_root,
                rebind_reason=rebind_reason,
            )
        if record["execution_config"] is None:
            self._store.configure_execution(
                run_ref,
                self._resolved_execution_config(accounting_run_id).value(),
            )
        checkpoint = self._store.get(run_ref)["execution_checkpoint"]
        assert isinstance(checkpoint, dict)
        if checkpoint["phase"] not in _PHASE_NAMES:
            self.record_phase(run_ref, "accounting")

    def _resolved_execution_config(
        self, accounting_run_id: str
    ) -> PrecheckExecutionConfig:
        attachment = AccountingStore(self.database_path).get_source_attachment(
            accounting_run_id
        )
        config = self._execution_config
        if config.sensitivity_profiles and not config.sensitivity_detector_identities:
            from dataclasses import replace

            config = replace(
                config,
                sensitivity_detector_identities=tuple(
                    d.identity
                    for d in self._orchestrator.dependencies.sensitivity_detectors
                ),
            )
        return config.resolve_resources(source_root=attachment.source_root)

    def mark_failed(
        self, run_ref: str, *, code: str, message: str
    ) -> dict[str, object]:
        reason = _reason(code, message)
        return self._status_record(self._store.mark_failed(run_ref, reason))

    def stop_unstarted_execution(
        self,
        run_ref: str,
        *,
        target_state: str,
        code: str,
        message: str,
        resume_when: str | None = None,
        worker_token: str | None = None,
    ) -> dict[str, object]:
        """Stop a public Run and pause accounting before execution starts."""

        return self._status_record(
            self._store.stop_unstarted_execution(
                run_ref,
                target_state=target_state,
                reason=_reason(code, message, resume_when=resume_when),
                worker_token=worker_token,
            )
        )

    def complete_with_result(self, run_ref: str, result_ref: str) -> dict[str, object]:
        """Atomically bind completion only after the sealed Result verifies."""

        try:
            record = self._store.get(run_ref)
        except KeyError:
            return _error("status", "run_not_found", "Run does not exist", run_ref)
        verified = self._verified_result(result_ref)
        if isinstance(verified, _ReadFailure):
            failed = self._store.mark_failed(
                run_ref,
                _reason("result_untrusted", str(verified)),
            )
            return self._status_record(failed)
        result_view, graph = verified
        if result_view["dataset_ref"] != record["dataset_ref"]:
            failed = self._store.mark_failed(
                run_ref,
                _reason(
                    "result_dataset_mismatch",
                    "The sealed Result belongs to a different Dataset.",
                ),
            )
            return self._status_record(failed)
        progress = _completed_progress(record["progress"], graph)
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
        except ValueError:
            return _error("start", "invalid_request", "Start inputs must be finite canonical JSON.")
        if replay is not None:
            return _start_response(replay)

        try:
            frozen_config = self.validated_start_configuration(request)
        except _ReadFailure as error:
            return _error("start", error.code, str(error))

        prior_result_ref = request.get("prior_result_ref")
        if prior_result_ref is None:
            dataset_ref = str(request["dataset_ref"])
            dataset_id = dataset_id_from_ref(dataset_ref)
            if not self._store.dataset_exists(dataset_id):
                return _error("start", "dataset_not_found", "Dataset does not exist")
        else:
            result_ref = str(prior_result_ref)
            verified = self._verified_result(result_ref)
            if isinstance(verified, _ReadFailure):
                return _error("start", verified.code, str(verified))
            result_view, _package = verified
            dataset_ref = str(result_view["dataset_ref"])
            if dataset_ref != request["dataset_ref"]:
                return _error(
                    "start",
                    "result_not_found",
                    "Prior Result does not exist in this Dataset.",
                )
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
                execution_config=frozen_config.value(),
            )
        except RunIdempotencyConflict:
            return _error(
                "start",
                "idempotency_conflict",
                "request_id was already used with different start inputs",
            )
        except RunAlreadyActive as error:
            return _error("start", "already_running", str(error), error.run_ref)
        try:
            self.prepare_execution(str(record["run_ref"]), dataset_id=dataset_id)
        except (RunBindingError, RunExecutionConflict, ValueError, OSError):
            _LOGGER.exception(
                "PreCheck start preparation failed for %s", record["run_ref"]
            )
            failed = self.stop_unstarted_execution(
                str(record["run_ref"]),
                target_state="failed",
                code="execution_initialization_failed",
                message="The Run could not prepare a source-bound execution.",
            )
            return _error(
                "start",
                "operation_failed",
                str(failed["reason"]["message"]),
                str(record["run_ref"]),
                current_state="failed",
                allowed_actions=[],
            )
        return _start_response(record)

    def validated_start_configuration(self, request):
        """Effect-free validation, also used before Host accounting admission."""
        from dataclasses import replace
        from ._preparation import freeze_preparation, resolved_preparation_recipes

        graph, digest = None, None
        if request.get("prior_result_ref") is not None:
            graph, digest = self._reader._load(request["prior_result_ref"])
            if graph.result["dataset_ref"] != request["dataset_ref"]:
                raise _ReadFailure("result_not_found", "Prior Result is not in this Dataset.")
        config = self._execution_config
        deps = self._orchestrator.dependencies
        if config.embedding_profile is not None and config.embedding_encoder_identity is None and deps.embedding_encoder is not None:
            config = replace(config, embedding_encoder_identity=deps.embedding_encoder.identity)
        if config.sensitivity_profiles and not config.sensitivity_detector_identities:
            config = replace(config, sensitivity_detector_identities=tuple(d.identity for d in deps.sensitivity_detectors))
        accounting_run = self._store.unfinished_accounting_run(dataset_id_from_ref(request["dataset_ref"]))
        root = None if accounting_run is None else AccountingStore(self.database_path).get_source_attachment(accounting_run).source_root
        config = config.resolve_resources(source_root=root)
        # Canonical preparation uses the same effective numeric/value types as
        # durable recovery, including profiles authored with integer literals.
        config = PrecheckExecutionConfig.from_value(config.value())
        preparation = freeze_preparation(request, config.value(), resolved_preparation_recipes(config, deps), graph, digest)
        return replace(config, preparation=preparation)

    def _status(
        self,
        run_ref: str,
        *,
        scope_path: object = None,
        scope_after: object = None,
        include: object = (),
        page: object = None,
    ) -> dict[str, object]:
        try:
            record = self._store.observe(run_ref)
        except KeyError:
            return _error("status", "run_not_found", "Run does not exist", run_ref)
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
            if isinstance(verified, _ReadFailure):
                return _error("status", verified.code, str(verified), run_ref)
            record["_verified_result"] = verified
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
        response = self._status_record(record, include=include, page=page)
        if scope_path is not None:
            confirmation = response.get("confirmation")
            if (
                not isinstance(confirmation, dict)
                or confirmation.get("kind") != "source_scope"
            ):
                return _error(
                    "status",
                    "invalid_request",
                    "scope_path is available only while source scope is pending",
                    run_ref,
                )
            accounting_run_id = record["accounting_run_id"]
            if not isinstance(accounting_run_id, str):
                return _error(
                    "status",
                    "operation_failed",
                    "Run has no bound source accounting state",
                    run_ref,
                )
            try:
                inventory = self._scope_inventory(
                    accounting_run_id,
                    scope_path=normalize_scope_path(scope_path, allow_root=True),
                    scope_after=(None if scope_after is None else str(scope_after)),
                )
            except ScopeSelectionError as error:
                return _error("status", "invalid_request", str(error), run_ref)
            confirmation = dict(confirmation)
            confirmation["inventory"] = {
                key: value
                for key, value in inventory.items()
                if key not in {"inventory_fingerprint", "scan_generation"}
            }
            response["confirmation"] = confirmation
        return response

    def _control(
        self,
        action: str,
        run_ref: str,
        decision: object,
        *,
        confirmation: PrecheckConfirmationContext | None,
    ) -> dict[str, object]:
        normalized_decision: object = decision
        try:
            if action == "pause":
                observed, _current = self._store.request_pause(run_ref)
            elif action == "resume":
                if isinstance(decision, dict):
                    record = self._store.get(run_ref)
                    confirmation = record["confirmation"]
                    accounting_run_id = record["accounting_run_id"]
                    if (
                        not isinstance(confirmation, dict)
                        or confirmation.get("kind") != "source_scope"
                        or not isinstance(accounting_run_id, str)
                    ):
                        raise RunDecisionError(
                            "source-scope decision requires a pending scope review"
                        )
                    normalized_decision = validate_scope_selection(
                        decision,
                        inventory_fingerprint_value=str(
                            confirmation["inventory_fingerprint"]
                        ),
                        existing_paths=(
                            str(fact["relative_path"])
                            for fact in AccountingStore(
                                self.database_path
                            ).iter_scope_inventory_facts(accounting_run_id)
                        ),
                    )
                elif decision is not None:
                    normalized_decision = str(decision)
                authority = None
                if normalized_decision == "proceed":
                    record = self._store.get(run_ref)
                    pending = record.get("confirmation")
                    identity = (
                        pending.get("content_identity")
                        if isinstance(pending, Mapping)
                        else None
                    )
                    if (
                        not isinstance(pending, Mapping)
                        or pending.get("kind") != "external_effect"
                        or confirmation is None
                        or confirmation.confirmed_content_identity != identity
                    ):
                        return _error(
                            action,
                            "confirmation_required"
                            if confirmation is None
                            else "confirmation_stale",
                            "Proceed requires trusted confirmation for the exact pending disclosure.",
                            run_ref,
                        )
                    authority = confirmation.value()
                observed, _current = self._store.request_resume(
                    run_ref, decision=normalized_decision, authority=authority
                )
            else:
                observed, _current = self._store.request_cancel(run_ref)
        except KeyError:
            return _error(action, "run_not_found", "Run does not exist", run_ref)
        except (RunDecisionError, ScopeSelectionError) as error:
            return _error(action, "invalid_request", str(error), run_ref)
        except RunStateConflict as error:
            return _invalid_state(action, run_ref, error.record)
        return {"state": _current["state"]}

    def _scope_inventory(
        self,
        accounting_run_id: str,
        *,
        scope_path: str = ".",
        scope_after: str | None = None,
    ) -> dict[str, object]:
        accounting = AccountingStore(self.database_path)
        summary = accounting.get_run_summary(accounting_run_id)
        issues = (
            {
                "relative_path": issue.relative_path.as_posix(),
                "code": str(issue.code),
                "blocked": issue.blocked,
                "basis": issue.basis,
            }
            for issue in accounting.get_run_issues(accounting_run_id)
        )
        return build_scope_inventory(
            accounting.iter_scope_inventory_facts(accounting_run_id),
            issues,
            scan_generation=summary.scan_generation,
            scope_path=scope_path,
            scope_after=scope_after,
            cursor_ref=accounting_run_id,
        )

    def _verified_result(
        self, result_ref: str
    ) -> tuple[dict[str, object], _ResultGraph] | _ReadFailure:
        try:
            graph, _digest = self._reader._load(result_ref)
        except _ReadFailure as error:
            return error
        result_view = graph.result
        required = {"ref", "dataset_ref", "coverage", "readiness", "integrity"}
        if not required <= set(result_view):
            return _ReadFailure(
                "result_untrusted", "sealed Result is missing required status fields"
            )
        if result_view["ref"] != result_ref or result_view["integrity"] != "valid":
            return _ReadFailure(
                "result_untrusted", "sealed Result does not provide valid integrity"
            )
        return result_view, graph

    def _status_record(
        self, record: dict[str, object], *, include: object = (), page: object = None
    ) -> dict[str, object]:
        activity = self._activity_record(record)
        state = str(record["state"])
        response: dict[str, object] = {"state": state}
        if _ALLOWED_ACTIONS[state]:
            response["allowed_actions"] = list(_ALLOWED_ACTIONS[state])
        if state == "running":
            work = activity["work"]
            counts = [work[key] for key in ("completed", "reused", "failed")]
            response["progress"] = {
                "phase": activity["phase"],
                "unit": _phase_unit(str(activity["phase"])),
                "processed": sum(counts)
                if all(isinstance(n, int) for n in counts)
                else None,
                "total": _known(work["total"]),
                "last_progress_at": _known(activity["last_progress_at"]),
            }
            if activity["state"] in {"suspected_stalled", "no_recent_progress"}:
                response["reason"] = _reason(
                    str(activity["state"]),
                    "The execution owner is unresponsive."
                    if activity["state"] == "suspected_stalled"
                    else "The owner is responsive but has not made recent durable progress.",
                    **(
                        {
                            "resume_when": "Explicitly resume after verifying the prior owner is stale."
                        }
                        if activity["state"] == "suspected_stalled"
                        else {}
                    ),
                )
                if activity["state"] == "suspected_stalled":
                    response["allowed_actions"] = ["resume", "cancel"]
        elif state in {"paused", "blocked", "failed"}:
            response["reason"] = record["reason"]
        if state == "paused" and record["confirmation"] is not None:
            try:
                response["confirmation"] = self._confirmation_view(
                    record, include=include, page=page
                )
            except _ReadFailure as error:
                return _error("status", error.code, str(error))
        if state == "completed":
            published = record["published_result"]
            verified = (
                record["_verified_result"]
                if "_verified_result" in record
                else self._verified_result(str(published["result_ref"]))
            )
            if isinstance(verified, _ReadFailure):
                return _error("status", verified.code, str(verified))
            from .read import _effective_result_view

            response["result"] = _effective_result_view(verified[1])
        issues = self._issues(record)
        if record["execution_checkpoint"].get("progress_scope_changed"):
            scope_reason = _reason(
                "progress_scope_changed",
                "The current phase work membership changed; reset progress comparisons.",
            )
            if state == "running" and "reason" not in response:
                response["reason"] = scope_reason
            else:
                issues.append(
                    {
                        **scope_reason,
                        "phase": activity["phase"],
                        "unit": "phase",
                        "count": 1,
                    }
                )
        if issues:
            response["issues"] = issues[:5]
            if len(issues) > 5:
                response["issues_truncated"] = True
        if "accounting" in include:
            response["accounting"] = self._accounting(record)
        local_execution = None
        if "diagnostics" in include or "local_execution" in include:
            from ._local_execution import collect_local_execution, execution_summary

            local_execution = collect_local_execution(
                self.database_path,
                record["accounting_run_id"],
                record["execution_config"],
            )
        if "local_execution" in include:
            from .read import (
                _page_request,
                _paged_response,
                _sha256_identity,
                _canonical_json,
            )

            digest = _sha256_identity(_canonical_json(local_execution).encode())
            query = _canonical_json(
                {"include": sorted(include), "order": "observed_at_batch_id"}
            )
            try:
                limit, offset = _page_request(
                    page,
                    default=50,
                    maximum=200,
                    result_ref=str(record["run_ref"]),
                    result_digest=digest,
                    operation="status",
                    query_key=query,
                )
                response["local_execution"] = _paged_response(
                    execution_summary(local_execution),
                    collection="batches",
                    values=local_execution["batches"],
                    offset=offset,
                    limit=limit,
                    result_ref=str(record["run_ref"]),
                    result_digest=digest,
                    operation="status",
                    query_key=query,
                )
            except _ReadFailure as error:
                return _error("status", error.code, str(error))
        if "diagnostics" in include:
            from .read import (
                _page_request,
                _paged_response,
                _sha256_identity,
                _canonical_json,
            )

            work = {key: _known(value) for key, value in activity["work"].items()}
            work = {
                "phase": activity["phase"],
                "unit": _phase_unit(str(activity["phase"])),
                **work,
            }
            facts = (
                record["_facts"]
                if "_facts" in record
                else self._store.execution_facts(record["accounting_run_id"])
            )
            boundary = _execution_summary(facts, str(record["run_ref"]))
            digest = _sha256_identity(
                _canonical_json(
                    {
                        "work": work,
                        "issues": issues,
                        "execution_boundary": boundary,
                        "local_execution": execution_summary(local_execution),
                    }
                ).encode()
            )
            query_key = _canonical_json(
                {"include": sorted(include), "order": "phase_code_unit"}
            )
            try:
                limit, offset = _page_request(
                    page,
                    default=50,
                    maximum=200,
                    result_ref=str(record["run_ref"]),
                    result_digest=digest,
                    operation="status",
                    query_key=query_key,
                )
                response["diagnostics"] = _paged_response(
                    {
                        "work": work,
                        "execution_boundary": boundary,
                        "local_execution": execution_summary(local_execution),
                    },
                    collection="issues",
                    values=issues,
                    offset=offset,
                    limit=limit,
                    result_ref=str(record["run_ref"]),
                    result_digest=digest,
                    operation="status",
                    query_key=query_key,
                )
            except _ReadFailure as error:
                return _error("status", error.code, str(error))
        return response

    def _issues(self, record: dict[str, object]) -> list[dict[str, object]]:
        facts = (
            record["_facts"]
            if "_facts" in record
            else self._store.execution_facts(record["accounting_run_id"])
        )
        groups: dict[tuple[str, str, str], int] = {}
        for row in facts.get("work", ()):
            if row["status"] not in _WORK_FAILURE_STATES:
                continue
            phase = _CAPABILITY_PHASE.get(row["capability"], "unknown")
            code = row.get("error_code") or row["status"]
            key = (phase, code, _phase_unit(phase))
            groups[key] = groups.get(key, 0) + row["count"]
        for output in facts.get("geo_effects", ()):
            outcomes = json.loads(output["components"] or "{}")
            if any(state in {"failed", "indeterminate"} for state in outcomes.values()):
                code = (
                    "geo_effect_indeterminate"
                    if "indeterminate" in outcomes.values()
                    else "location_query_failed"
                )
                key = ("geo", code, "location_query")
                groups[key] = groups.get(key, 0) + output["count"]
        return [
            {
                "phase": phase,
                "code": code,
                "unit": unit,
                "count": count,
                "message": f"{count} logical operations report {code}.",
            }
            for (phase, code, unit), count in sorted(groups.items())
        ]

    def _accounting(self, record: dict[str, object]) -> dict[str, object]:
        if record["state"] == "completed":
            from copy import deepcopy
            from .read import _reconciliation

            verified = (
                record["_verified_result"]
                if "_verified_result" in record
                else self._verified_result(
                    str(record["published_result"]["result_ref"])
                )
            )
            if isinstance(verified, _ReadFailure):
                raise ValueError(str(verified))
            accounting = _reconciliation(verified[1])
            result = {
                "discovered": _known(record["progress"]["discovered"]),
                "accounted": accounting["total"],
                "scope_condition": deepcopy(accounting["scope_condition"]),
            }
        else:
            result = (
                record["_accounting"]
                if "_accounting" in record
                else self._store.accounting_detail(record)
            )
        scope_review = (
            record["_scope_review"]
            if "_scope_review" in record
            else self._store.latest_scope_review(str(record["run_ref"]))
        )
        if scope_review is not None and scope_review["state"] in {"accepted", "reused"}:
            selection = dict(scope_review["selection"])
            selection["provenance"] = scope_review["state"]
            if scope_review["reused_from_run_ref"] is not None:
                selection["reused_from_run_ref"] = scope_review["reused_from_run_ref"]
            result["selection"] = selection
        return result

    def _confirmation_view(
        self, record: dict[str, object], *, include: object, page: object
    ) -> dict[str, object]:
        confirmation = record["confirmation"]
        if confirmation["kind"] == "source_scope":
            return {
                "kind": "source_scope",
                "inventory_fingerprint": confirmation["inventory_fingerprint"],
                "inventory": {
                    key: value
                    for key, value in confirmation["inventory"].items()
                    if key not in {"inventory_fingerprint", "scan_generation"}
                },
            }
        from .read import (
            _page_request,
            _paged_response,
            _encoded_size,
            _MAX_RESPONSE_BYTES,
        )

        view = {
            key: confirmation[key] for key in ("kind", "content_identity", "summary")
        }
        disclosure = dict(confirmation["disclosure"])
        coordinates = disclosure.pop("coordinates", [])
        if (
            "confirmation" not in include
            and _encoded_size(confirmation) > _MAX_RESPONSE_BYTES - 8192
        ):
            view["summary"] += (
                " Read status include=confirmation for paged coordinate details."
            )
            return view
        query_key = json.dumps(
            {"view": "confirmation", "include": sorted(include)}, sort_keys=True
        )
        limit, offset = _page_request(
            page,
            default=50 if "confirmation" in include else max(1, len(coordinates)),
            maximum=200 if "confirmation" in include else max(200, len(coordinates)),
            result_ref=str(record["run_ref"]),
            result_digest=confirmation["content_identity"],
            operation="status",
            query_key=query_key,
        )
        paged = _paged_response(
            disclosure,
            collection="coordinates",
            values=coordinates,
            offset=offset,
            limit=limit,
            result_ref=str(record["run_ref"]),
            result_digest=confirmation["content_identity"],
            operation="status",
            query_key=query_key,
        )
        view["page"] = paged.pop("page")
        view["disclosure"] = paged
        return view

    def _activity_record(self, record: dict[str, object]) -> dict[str, object]:
        checkpoint = record["execution_checkpoint"]
        assert isinstance(checkpoint, dict)
        internal_phase = str(checkpoint["phase"])
        phase = _PHASE_NAMES.get(internal_phase, "unknown")
        facts = (
            record["_facts"]
            if "_facts" in record
            else self._store.execution_facts(
                None
                if record["accounting_run_id"] is None
                else str(record["accounting_run_id"])
            )
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
            if isinstance(reason, dict) and reason.get("code") in {
                "confirmation_required",
                "scope_confirmation_required",
            }:
                return "waiting"
            return "paused"
        checkpoint = record["execution_checkpoint"]
        assert isinstance(checkpoint, dict)
        worker = checkpoint.get("worker")
        if not isinstance(worker, dict) or not isinstance(
            worker.get("heartbeat_at"), str
        ):
            return "suspected_stalled"
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
        status = str(row["status"])
        if status in {"cancelled", "invalidated"}:
            continue
        count = int(row["count"])
        observed += count
        if status == "succeeded":
            if row.get("geo_status") in {"failed", "indeterminate"}:
                failed += count
            elif row["attempted_here"]:
                completed += count
            else:
                reused += count
        elif status == "terminal_failure":
            failed += count
        if status in {"succeeded", "terminal_failure"}:
            last_progress_at = _latest_timestamp(
                last_progress_at, str(row["last_progress_at"])
            )
    settled = completed + reused + failed
    if complete:
        total = max(observed, settled)
        remaining: int | str = max(total - settled, 0)
    elif observed:
        total = observed
        remaining = total - settled
    else:
        total = "unknown"
        remaining = "unknown"
    return (
        _work_counts(completed, reused, failed, remaining, total),
        last_progress_at,
    )


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


def _validate_progress(progress: dict[str, object]) -> None:
    if set(progress) != _PROGRESS_KEYS:
        raise ValueError(
            "accounting progress must contain exactly the five internal counters"
        )
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
    graph: _ResultGraph,
) -> dict[str, object]:
    if not isinstance(current, dict):
        raise ValueError("Run progress is invalid")
    accounts = graph.accounts
    conditions = [item.get("condition") for item in accounts.values()]
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
    return {"run_ref": record["run_ref"]}


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
    if allowed_actions:
        detail["allowed_actions"] = list(allowed_actions)
    if run_ref is not None:
        detail["run_ref"] = run_ref
    return {"error": detail}


def _execution_summary(facts: Mapping[str, object], run_ref: str) -> dict[str, object]:
    rows = facts.get("geo_effects", ())
    historical = current = bills = 0
    unknown_historical = unknown_current = unknown_bills = False
    providers: set[str] = set()
    for row in rows:
        if row["owner"] == run_ref:
            current += row["requests"] or 0
            unknown_current |= bool(row["requests_unknown"])
        else:
            historical += row["requests"] or 0
            unknown_historical |= bool(row["requests_unknown"])
        bills += row["bills"] or 0
        unknown_bills |= bool(row["bills_unknown"])
        providers.update(
            json.loads(row["providers"])
            if row["providers"]
            else [row["provider"]]
            if row["provider"]
            else []
        )
    return {
        "source_read_only": True,
        "remote_models": False,
        "logical_external_queries": sum(row["count"] for row in rows),
        "historical_provider_requests": None if unknown_historical else historical,
        "current_provider_requests": None if unknown_current else current,
        "billable_calls": None if unknown_bills else bills,
        "transmitted_data_classes": ["coordinate", "datum", "locale"]
        if unknown_current or unknown_historical or current + historical > 0
        else [],
        "providers_attempted": sorted(providers),
    }


def _known(value: object) -> object:
    return None if value == "unknown" else value


def _phase_unit(phase: str) -> str:
    return (
        "source_item"
        if phase == "source_accounting"
        else "location_query"
        if phase == "geo"
        else "logical_operation"
    )


__all__ = ["PrecheckRunTool"]
