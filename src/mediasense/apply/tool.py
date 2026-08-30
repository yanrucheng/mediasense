"""Public adapter for the active ``mediasense.apply.run`` contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .execution import ApplyExecutionError, ApplyExecutor
from .filesystem import canonical_identity
from .preparation import (
    ApplyPreparationError,
    ApplyRunStore,
    PrecheckReadBoundary,
    SourceSetResolver,
)
from .receipt import ReceiptError, ReceiptStore


@dataclass(frozen=True, slots=True)
class ApplyConfirmationContext:
    principal_ref: str
    confirmed_content_identity: str
    confirmed_at: datetime


class ApplyRunTool:
    """Bind the six public actions to one durable Run implementation."""

    name = "mediasense.apply.run"

    def __init__(
        self,
        apply_store: Path,
        precheck_read: PrecheckReadBoundary,
        resolve_source_set: SourceSetResolver,
        *,
        run_schema_path: Path,
        receipt_schema_path: Path,
    ) -> None:
        self.apply_store = Path(apply_store)
        database = self.apply_store / "work.sqlite3"
        self.run_store = (
            ApplyRunStore(database)
            if database.exists()
            else ApplyRunStore.initialize(database)
        )
        self.receipt_store = ReceiptStore(
            self.apply_store / "receipts", receipt_schema_path
        )
        self.executor = ApplyExecutor(self.run_store, self.receipt_store)
        self.precheck_read = precheck_read
        self.resolve_source_set = resolve_source_set
        schema = json.loads(Path(run_schema_path).read_text(encoding="utf-8"))
        self._input = Draft202012Validator(schema["inputSchema"])
        self._output = Draft202012Validator(schema["outputSchema"])

    def handle(
        self,
        request: Mapping[str, Any],
        *,
        confirmation: ApplyConfirmationContext | None = None,
    ) -> dict[str, object]:
        payload = dict(request)
        self._input.validate(payload)
        action = str(payload["action"])
        try:
            if action == "prepare":
                response = self._prepare(payload)
            elif action == "status":
                response = self.run_store.status(str(payload["run_ref"]))
            elif action == "execute":
                response = self._execute(payload, confirmation)
            elif action == "pause":
                response = self.executor.pause(str(payload["run_ref"]))
            elif action == "resume":
                run_ref = str(payload["run_ref"])
                if self.run_store.get_run(run_ref).state == "blocked":
                    self.run_store.resume_preparation(
                        run_ref=run_ref, precheck_read=self.precheck_read
                    )
                    response = {
                        "outcome": "accepted",
                        "action": "resume",
                        "run_ref": run_ref,
                        "observed_state": "blocked",
                        "target_state": "preparing",
                    }
                else:
                    response = self.executor.resume(run_ref)
            elif action == "cancel":
                response = self.executor.cancel(str(payload["run_ref"]))
            else:  # pragma: no cover - guarded by JSON Schema
                raise ValueError("unsupported Apply action")
        except (ApplyPreparationError, ApplyExecutionError, ReceiptError) as error:
            response = {
                "outcome": "error",
                "action": action,
                "error": {
                    "code": _error_code(error),
                    "message": str(error),
                },
            }
            if isinstance(payload.get("run_ref"), str):
                response["run_ref"] = payload["run_ref"]
        self._output.validate(response)
        return response

    def run_pending(self, run_ref: str) -> dict[str, object]:
        """Advance authorized work; a scheduler may invoke this out of band."""

        self.executor.advance(run_ref)
        return self.run_store.status(run_ref)

    def _prepare(self, request: dict[str, Any]) -> dict[str, object]:
        if "rewind" in request:
            rewind = request["rewind"]
            receipt_ref = str(rewind["receipt_ref"])
            receipt = self.receipt_store.read(receipt_ref)
            run = self.run_store.prepare_rewind(
                request_id=str(request["request_id"]),
                receipt=receipt,
                operations=self.receipt_store.operation_items(receipt_ref, receipt),
            )
            return {
                "outcome": "ok",
                "action": "prepare",
                "run_ref": run.run_ref,
                "state": "preparing",
            }
        source = request["forward"]
        plan_path = Path(source["frozen_plan_path"])
        try:
            frozen_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ApplyPreparationError(
                "Frozen Plan is unavailable or invalid"
            ) from error
        roots = {
            item["source_root_ref"]: Path(item["current_root"])
            for item in source["current_source_roots"]
        }
        run = self.run_store.prepare_forward(
            request_id=str(request["request_id"]),
            frozen_plan=frozen_plan,
            source_roots=roots,
            destination_parent=Path(source["destination_parent"]),
            resolve_source_set=self.resolve_source_set,
            precheck_read=self.precheck_read,
        )
        return {
            "outcome": "ok",
            "action": "prepare",
            "run_ref": run.run_ref,
            "state": "preparing",
        }

    def _execute(
        self,
        request: dict[str, Any],
        confirmation: ApplyConfirmationContext | None,
    ) -> dict[str, object]:
        if confirmation is None:
            raise ApplyExecutionError("trusted Human confirmation is required")
        if confirmation.confirmed_at.tzinfo is None:
            raise ApplyExecutionError("trusted confirmation time requires a timezone")
        if (
            confirmation.confirmed_content_identity
            != request["prepared_content_identity"]
        ):
            raise ApplyExecutionError("confirmed content identity mismatch")
        binding = canonical_identity(
            {
                "principal_ref": confirmation.principal_ref,
                "confirmed_content_identity": confirmation.confirmed_content_identity,
                "confirmed_at": confirmation.confirmed_at.isoformat(),
            }
        )
        accepted = self.executor.authorize(
            run_ref=str(request["run_ref"]),
            prepared_revision=str(request["prepared_revision"]),
            prepared_content_identity=str(request["prepared_content_identity"]),
            request_id=str(request["request_id"]),
            authorization_binding=binding,
        )
        return accepted


def _error_code(error: BaseException) -> str:
    message = str(error)
    if "confirmation" in message or "content identity" in message:
        return "access_denied"
    if "idempotency" in message:
        return "idempotency_conflict"
    if "revision" in message:
        return "revision_conflict"
    if "not ready" in message or "cannot" in message:
        return "invalid_state"
    return "operation_failure"
