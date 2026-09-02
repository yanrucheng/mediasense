"""The single Dataset-bound composition root for installed MediaSense."""

from __future__ import annotations

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
from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoEffectEnvelope,
    GeoOperation,
    GeoOperationJournal,
    GeoProviderCapabilities,
    GeoQueryTool,
    GeoRetention,
    MapDatum,
)
from mediasense.capabilities.geo.service import GeoCapability
from mediasense.geo import AMapReverseGeocoder, GoogleMapsReverseGeocoder
from mediasense.plan import ConfirmationContext, PlanWorkTool
from mediasense.precheck import AccountingStore, PrecheckReadTool, PrecheckRunTool
from mediasense.precheck.source_attachment import (
    SourceAttachmentError,
    SourceRebindRequired,
)

from .config import RuntimeConfig
from .dataset import DatasetOpenResult
from .resources import contract_digest, load_contract, schema_path


class HostRequestError(RuntimeError):
    """The transport envelope cannot be bound to a public Tool call."""


class _OfflineRouting:
    def routes(
        self, request: object, context: object, providers: tuple[object, ...]
    ) -> tuple[str, ...]:
        return ()

    def observe(self, request: object, context: object, execution: object) -> object:
        return context


class _OfflineProvider:
    capabilities = GeoProviderCapabilities(
        "offline-disabled",
        (GeoOperation.REVERSE_GEOCODE, GeoOperation.NEARBY_PLACES),
        MapDatum.WGS84,
    )

    def execute(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("offline routing must never execute a provider")


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
        self.precheck_run = PrecheckRunTool(precheck_database)
        self.precheck_read = PrecheckReadTool(precheck_database)
        self.geo_query = _geo_tool(workspace / "geo", config)
        frozen_plan = schema_path("frozen-plan.schema.json")
        self.plan_work = PlanWorkTool(
            workspace / "plan",
            self.precheck_read,
            frozen_plan_schema=frozen_plan,
            geo_tool=self.geo_query,
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
                geo_authorization=_geo_authorization(context),
            )
        elif name == "mediasense.geo.query":
            response = self.geo_query.handle(
                payload, authorization=_geo_authorization(context)
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
        if action == "start" and "prior_result_ref" not in request:
            requested_dataset = request.get("dataset_ref")
            if requested_dataset != self.opened.manifest.dataset_ref:
                raise HostRequestError(
                    "PreCheck request dataset_ref does not match the opened Dataset."
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
        response = self.precheck_run.run(request)
        run_ref = response.get("run_ref")
        if isinstance(run_ref, str) and response.get("state") == "running":
            self._schedule(run_ref)
        if (
            isinstance(run_ref, str)
            and response.get("outcome") == "accepted"
            and response.get("target_state") == "running"
        ):
            self._schedule(run_ref)
        return response

    def _schedule(self, run_ref: str) -> None:
        with self._worker_lock:
            current = self._workers.get(run_ref)
            if current is not None and current.is_alive():
                return
            worker = threading.Thread(
                target=self._advance,
                args=(run_ref,),
                name=f"mediasense-{run_ref}",
                daemon=True,
            )
            self._workers[run_ref] = worker
            worker.start()

    def _advance(self, run_ref: str) -> None:
        try:
            self.precheck_run.advance(run_ref)
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


def tool_descriptors() -> tuple[ToolDescriptor, ...]:
    result = []
    for name in (
        "mediasense.dataset.open",
        "mediasense.precheck.run",
        "mediasense.precheck.read",
        "mediasense.plan.work",
        "mediasense.geo.query",
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


def _geo_tool(workspace: Path, config: RuntimeConfig) -> GeoQueryTool:
    providers: dict[str, Any] = {}
    if not config.offline:
        import os

        amap_key = os.environ.get(config.amap_api_key_env)
        google_key = os.environ.get(config.google_maps_api_key_env)
        if amap_key:
            providers["amap"] = AMapReverseGeocoder(amap_key)
        if google_key:
            providers["google_maps"] = GoogleMapsReverseGeocoder(google_key)
    if providers:
        from mediasense.capabilities.geo import OrderedGeoRoutingPolicy

        routing: Any = OrderedGeoRoutingPolicy(tuple(providers))
    else:
        providers = {"offline-disabled": _OfflineProvider()}
        routing = _OfflineRouting()
    capability = GeoCapability(providers, routing)
    return GeoQueryTool(capability, GeoOperationJournal(workspace / "journal.sqlite3"))


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


def _geo_authorization(value: Mapping[str, Any]) -> GeoAuthorization | None:
    envelope = value.get("effect_envelope")
    required = {"principal_ref", "request_fingerprint", "authorized_at"}
    if not required <= set(value) or not isinstance(envelope, Mapping):
        return None
    try:
        return GeoAuthorization(
            principal_ref=str(value["principal_ref"]),
            request_fingerprint=str(value["request_fingerprint"]),
            authorized_at=_datetime(value["authorized_at"]),
            envelope=GeoEffectEnvelope(
                allowed_providers=tuple(envelope.get("allowed_providers", ())),
                allowed_data_classes=tuple(envelope.get("allowed_data_classes", ())),
                max_logical_queries=int(envelope.get("max_logical_queries", 0)),
                max_provider_requests=int(envelope.get("max_provider_requests", 0)),
                max_billable_units=(
                    None
                    if envelope.get("max_billable_units") is None
                    else int(envelope["max_billable_units"])
                ),
                allow_unknown_billable_units=bool(
                    envelope.get("allow_unknown_billable_units", False)
                ),
                retention=GeoRetention(str(envelope.get("retention", "none"))),
            ),
        )
    except (TypeError, ValueError) as error:
        raise HostRequestError(f"invalid Geo authorization: {error}") from error


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
