"""The single Dataset-bound composition root for installed MediaSense."""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mediasense.apply import (
    ApplyConfirmationContext,
    ApplyReceiptReader,
    ApplyRunTool,
)
from mediasense.geo import (
    AMapReverseGeocoder,
    AdaptiveReverseGeocoder,
    GoogleMapsReverseGeocoder,
)
from mediasense.plan import ConfirmationContext, PlanWorkTool
from mediasense.precheck import (
    AccountingStore,
    PrecheckConfirmationContext,
    PrecheckExecutionDependencies,
    PrecheckReadTool,
    PrecheckRunTool,
)
from mediasense.precheck.source_attachment import (
    SourceAttachmentError,
    SourceRebindRequired,
)

from .config import RuntimeConfig
from .dataset import DatasetOpenResult
from .resources import contract_digest, load_contract, schema_path


_LOGGER = logging.getLogger(__name__)


class HostRequestError(RuntimeError):
    """The transport envelope cannot be bound to a public Tool call."""


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    name: str
    description: str
    contract_id: str
    contract_digest: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]

    def to_value(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "contract_id": self.contract_id,
            "contract_digest": self.contract_digest,
        }


class DatasetRuntime:
    """All Tool instances and durable state for one opened Dataset."""

    def __init__(self, opened: DatasetOpenResult, config: RuntimeConfig) -> None:
        self.opened = opened
        self.config = config
        workspace = opened.workspace
        precheck_database = workspace / "precheck" / "work.sqlite3"
        self.dataset_id = opened.manifest.dataset_id
        AccountingStore(precheck_database).register_dataset(self.dataset_id)
        self.precheck_run = PrecheckRunTool(
            precheck_database,
            execution_dependencies=PrecheckExecutionDependencies(
                geocoder=_precheck_geocoder(config)
            ),
        )
        self.precheck_read = PrecheckReadTool(precheck_database)
        frozen_plan = schema_path("frozen-plan.schema.json")
        self.plan_work = PlanWorkTool(
            workspace / "plan",
            self.precheck_read,
            frozen_plan_schema=frozen_plan,
        )
        self.apply_run = ApplyRunTool(
            workspace / "apply",
            self.precheck_read,
            run_schema_path=contract_path_for("mediasense.apply.run"),
            frozen_plan_schema_path=frozen_plan,
            receipt_schema_path=schema_path("apply-receipt.schema.json"),
        )
        self.apply_read = ApplyReceiptReader(
            self.apply_run.receipt_store,
            schema_path=contract_path_for("mediasense.apply.read"),
        )
        self._workers: dict[str, threading.Thread] = {}
        self._worker_lock = threading.Lock()

    def call(
        self,
        name: str,
        request: Mapping[str, Any],
        authority: Mapping[str, Any] | None = None,
    ) -> dict[str, object]:
        payload = dict(request)
        context = dict(authority or {})
        if name == "mediasense.precheck.run":
            response = self._call_precheck(payload, context)
        elif name == "mediasense.precheck.read":
            response = self.precheck_read.read(payload)
        elif name == "mediasense.plan.work":
            response = self.plan_work.handle(
                payload,
                confirmation=_confirmation(context, ConfirmationContext),
            )
        elif name == "mediasense.apply.run":
            response = self.apply_run.handle(
                payload,
                confirmation=_confirmation(context, ApplyConfirmationContext),
            )
            run_ref = response.get("run_ref")
            if isinstance(run_ref, str) and (
                response.get("state") == "executing"
                or response.get("target_state") == "executing"
            ):
                self._schedule_apply(run_ref)
        elif name == "mediasense.apply.read":
            response = self.apply_read.read(payload)
        else:
            raise HostRequestError(f"Unknown MediaSense Tool: {name}")
        return dict(response)

    def _call_precheck(
        self, request: dict[str, Any], authority: Mapping[str, Any]
    ) -> dict[str, object]:
        action = request.get("action")
        if action == "start":
            requested_dataset = request.get("dataset_ref")
            if (
                requested_dataset is not None
                and requested_dataset != self.opened.manifest.dataset_ref
            ):
                raise HostRequestError(
                    "PreCheck request dataset_ref does not match the opened Dataset."
                )
            prior_result_ref = request.get("prior_result_ref")
            if isinstance(prior_result_ref, str) and prior_result_ref:
                inspected = self.precheck_read.read(
                    {
                        "operation": "review",
                        "result_ref": prior_result_ref,
                        "page": {"limit": 1},
                    }
                )
                if inspected.get("outcome") != "ok":
                    return self.precheck_run.run(request)
                target = inspected.get("result")
                if (
                    not isinstance(target, Mapping)
                    or target.get("dataset_ref") != self.opened.manifest.dataset_ref
                ):
                    raise HostRequestError(
                        "Prior Result does not belong to the opened Dataset."
                    )
            rebind_reason = authority.get("rebind_reason")
            if rebind_reason is not None and not isinstance(rebind_reason, str):
                raise HostRequestError("rebind_reason must be a string")
            try:
                AccountingStore(self.precheck_run.database_path).start_or_resume_run(
                    self.dataset_id,
                    self.opened.source_root,
                    rebind_reason=rebind_reason,
                )
            except SourceAttachmentError as error:
                return {
                    "outcome": "error",
                    "action": "start",
                    "error": {
                        "code": (
                            "source_rebind_required"
                            if isinstance(error, SourceRebindRequired)
                            else "source_attachment_failed"
                        ),
                        "message": str(error),
                    },
                }
        response = self.precheck_run.run(
            request,
            confirmation=_confirmation(authority, PrecheckConfirmationContext),
        )
        run_ref = response.get("run_ref")
        should_schedule = isinstance(run_ref, str) and (
            (
                action == "start"
                and response.get("outcome") == "ok"
                and response.get("state") == "running"
            )
            or (
                action == "resume"
                and response.get("outcome") == "accepted"
                and response.get("target_state") == "running"
            )
        )
        if should_schedule:
            assert isinstance(run_ref, str)
            if response.get("dataset_ref", self.opened.manifest.dataset_ref) != (
                self.opened.manifest.dataset_ref
            ):
                failed = self.precheck_run.mark_failed(
                    run_ref,
                    code="dataset_binding_mismatch",
                    message=(
                        "The Run belongs to a different Dataset than the opened "
                        "Tool Host. Execution was not started."
                    ),
                )
                return _execution_start_error(str(action), failed)
            if action == "resume":
                try:
                    # The public Run already owns its accounting identity. A
                    # resume may revalidate that attachment, never select a
                    # newer Dataset-level accounting Run.
                    self.precheck_run.prepare_execution(
                        run_ref,
                        dataset_id=self.dataset_id,
                        source_root=self.opened.source_root,
                        rebind_reason=authority.get("rebind_reason"),
                    )
                except SourceRebindRequired as error:
                    blocked = self.precheck_run.stop_unstarted_execution(
                        run_ref,
                        target_state="blocked",
                        code="source_rebind_required",
                        message=str(error),
                        resume_when=(
                            "Provide authority.rebind_reason for the intended source "
                            "root, then resume this Run."
                        ),
                    )
                    return _execution_start_error(str(action), blocked)
                except SourceAttachmentError as error:
                    blocked = self.precheck_run.stop_unstarted_execution(
                        run_ref,
                        target_state="blocked",
                        code="source_attachment_unavailable",
                        message=str(error),
                        resume_when=(
                            "Make the bound source available, then resume this Run."
                        ),
                    )
                    return _execution_start_error(str(action), blocked)
                except (ValueError, OSError):
                    _LOGGER.exception(
                        "PreCheck resume preparation failed for %s", run_ref
                    )
                    failed = self.precheck_run.stop_unstarted_execution(
                        run_ref,
                        target_state="failed",
                        code="execution_initialization_failed",
                        message=("The Run could not prepare a source-bound execution."),
                    )
                    return _execution_start_error(str(action), failed)
            failed = self._schedule(run_ref)
            if failed is not None:
                return _execution_start_error(str(action), failed)
        return response

    def _schedule(self, run_ref: str) -> dict[str, object] | None:
        with self._worker_lock:
            current = self._workers.get(run_ref)
            if current is not None and current.is_alive():
                return None
            worker_token, status = self.precheck_run.claim_execution(run_ref)
            if worker_token is None:
                return status if status.get("state") == "failed" else None
            worker = threading.Thread(
                target=self._advance,
                args=(run_ref, worker_token),
                name=f"mediasense-{run_ref}",
                daemon=True,
            )
            self._workers[run_ref] = worker
            try:
                worker.start()
            except Exception:
                self._workers.pop(run_ref, None)
                _LOGGER.exception("PreCheck worker launch failed for %s", run_ref)
                return self.precheck_run.stop_unstarted_execution(
                    run_ref,
                    target_state="failed",
                    code="execution_worker_start_failed",
                    message="The execution worker could not be started.",
                    worker_token=worker_token,
                )
        return None

    def _advance(self, run_ref: str, worker_token: str) -> None:
        try:
            self.precheck_run.advance_claimed(run_ref, worker_token)
        except Exception:
            _LOGGER.exception("PreCheck worker crashed for %s", run_ref)
            try:
                self.precheck_run.mark_failed(
                    run_ref,
                    code="execution_worker_crashed",
                    message="The execution worker crashed unexpectedly.",
                )
            except Exception:
                _LOGGER.exception(
                    "PreCheck worker failure could not be recorded for %s", run_ref
                )
        finally:
            with self._worker_lock:
                self._workers.pop(run_ref, None)

    def _schedule_apply(self, run_ref: str) -> None:
        worker_ref = f"apply:{run_ref}"
        with self._worker_lock:
            current = self._workers.get(worker_ref)
            if current is not None and current.is_alive():
                return
            worker = threading.Thread(
                target=self._advance_apply,
                args=(worker_ref, run_ref),
                name=f"mediasense-{run_ref}",
                daemon=True,
            )
            self._workers[worker_ref] = worker
            worker.start()

    def _advance_apply(self, worker_ref: str, run_ref: str) -> None:
        try:
            self.apply_run.run_pending(run_ref)
        finally:
            with self._worker_lock:
                self._workers.pop(worker_ref, None)


def _execution_start_error(
    action: str, status: Mapping[str, object]
) -> dict[str, object]:
    reason = status.get("reason")
    message = (
        str(reason.get("message"))
        if isinstance(reason, Mapping)
        else "The execution worker could not be started."
    )
    state = str(status.get("state", "failed"))
    allowed_actions = status.get("allowed_actions")
    return {
        "outcome": "error",
        "action": action,
        "run_ref": status["run_ref"],
        "error": {
            "code": "operation_failed",
            "message": message,
            "current_state": state,
            "allowed_actions": (
                list(allowed_actions)
                if isinstance(allowed_actions, list)
                else []
            ),
        },
    }


def tool_descriptors() -> tuple[ToolDescriptor, ...]:
    result = []
    for name in (
        "mediasense.dataset.open",
        "mediasense.precheck.run",
        "mediasense.precheck.read",
        "mediasense.plan.work",
        "mediasense.apply.run",
        "mediasense.apply.read",
    ):
        contract = load_contract(name)
        result.append(
            ToolDescriptor(
                name=name,
                description=str(contract["description"]),
                contract_id=str(contract["$id"]),
                contract_digest=contract_digest(name),
                input_schema=dict(contract["inputSchema"]),
                output_schema=dict(contract["outputSchema"]),
            )
        )
    return tuple(result)


def contract_path_for(name: str) -> Path:
    from .resources import contract_path

    return contract_path(name)


def _precheck_geocoder(config: RuntimeConfig) -> AdaptiveReverseGeocoder | None:
    import os

    providers: dict[str, Any] = {}
    amap_key = os.environ.get(config.amap_api_key_env)
    google_key = os.environ.get(config.google_maps_api_key_env)
    if amap_key:
        providers["amap"] = AMapReverseGeocoder(amap_key)
    if google_key:
        providers["google_maps"] = GoogleMapsReverseGeocoder(google_key)
    if not providers:
        return None
    order = tuple(providers)
    return AdaptiveReverseGeocoder(
        providers,
        provider_order=order,
        initial_provider="google_maps" if "google_maps" in providers else order[0],
    )


def _confirmation(value: Mapping[str, Any], confirmation_type: type[Any]) -> Any | None:
    if not value:
        return None
    required = {"principal_ref", "confirmed_content_identity", "confirmed_at"}
    if not required <= set(value):
        return None
    return confirmation_type(
        principal_ref=str(value["principal_ref"]),
        confirmed_content_identity=str(value["confirmed_content_identity"]),
        confirmed_at=_datetime(value["confirmed_at"]),
    )


def _datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise HostRequestError("authorization time must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise HostRequestError(
            "authorization time must be a valid ISO-8601 timestamp"
        ) from error
    if parsed.tzinfo is None:
        raise HostRequestError("authorization time must include a timezone")
    return parsed
