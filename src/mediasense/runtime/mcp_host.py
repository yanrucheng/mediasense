"""MCP stdio adapter over the MediaSense runtime host."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import NoBackChannelError

from .composition import HostRequestError, ToolDescriptor, tool_descriptors
from .host import RuntimeHost
from .resources import schema_path
from .versioning import application_version


_LOGGER = logging.getLogger(__name__)


def create_mcp_server(host: RuntimeHost | None = None) -> Server[Any]:
    runtime = host or RuntimeHost()
    descriptors = {item.name: item for item in tool_descriptors()}

    async def list_tools(_context: Any, _params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[_mcp_tool(descriptor) for descriptor in descriptors.values()]
        )

    async def call_tool(
        _context: Any, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        arguments = dict(params.arguments or {})
        try:
            if params.name == "mediasense.dataset.open":
                unknown = set(arguments) - {"source_root", "workspace"}
                if unknown:
                    raise HostRequestError(
                        f"Unknown Dataset open fields: {sorted(unknown)}"
                    )
                result = await anyio.to_thread.run_sync(
                    lambda: runtime.open_dataset(
                        str(arguments.get("source_root", "")),
                        (
                            None
                            if arguments.get("workspace") is None
                            else str(arguments["workspace"])
                        ),
                    )
                )
            else:
                dataset_ref = arguments.get("dataset_ref")
                precheck = params.name in {
                    "mediasense.precheck.run",
                    "mediasense.precheck.read",
                }
                request = arguments if precheck else arguments.get("request")
                authority = arguments.get("authority")
                if not isinstance(dataset_ref, str) or not dataset_ref:
                    raise HostRequestError("dataset_ref must be a non-empty string")
                if not isinstance(request, dict):
                    raise HostRequestError("request must be an object")
                if (
                    params.name
                    in {
                        "mediasense.precheck.run",
                        "mediasense.geo.query",
                    }
                    and "authority" in arguments
                ):
                    raise HostRequestError(
                        "External-effect authority is supplied only by MCP Human elicitation"
                    )
                if authority is not None and not isinstance(authority, dict):
                    raise HostRequestError("authority must be an object")
                if precheck:
                    from .resources import contract_validator

                    if not contract_validator(params.name).is_valid(request):
                        return _tool_result(
                            {
                                "error": {
                                    "code": "invalid_request",
                                    "message": "Invalid flat PreCheck request.",
                                }
                            },
                            is_error=True,
                        )
                if params.name == "mediasense.precheck.run":
                    request, authority = await _elicit_precheck_authority(
                        _context,
                        runtime,
                        dataset_ref,
                        request,
                    )
                if params.name == "mediasense.geo.query":
                    preflight = await anyio.to_thread.run_sync(
                        lambda: runtime.call_tool(
                            params.name,
                            dataset_ref=dataset_ref,
                            request=request,
                        )
                    )
                    authority = await _elicit_geo_authority(
                        _context, preflight, request
                    )
                    if authority is None:
                        result = preflight
                        return _tool_result(result)
                if (
                    params.name == "mediasense.plan.work"
                    and request.get("action") == "update"
                ):
                    from ._plan_update import call_plan_update

                    result = await call_plan_update(
                        runtime, _context, dataset_ref, request, authority
                    )
                else:
                    result = await anyio.to_thread.run_sync(
                        lambda: runtime.call_tool(
                            params.name,
                            dataset_ref=dataset_ref,
                            request=request,
                            authority=authority,
                        )
                    )
        except HostRequestError as error:
            result = {
                "outcome": "error",
                "error": {
                    "code": (
                        "invalid_request"
                        if error.code == "host_invalid_request"
                        else error.code
                    )
                    if params.name
                    in {"mediasense.precheck.run", "mediasense.precheck.read"}
                    else error.code,
                    "message": str(error),
                },
            }
            if params.name in {"mediasense.precheck.run", "mediasense.precheck.read"}:
                result.pop("outcome", None)
            return _tool_result(result, is_error=True)
        except Exception:
            diagnostic_id = f"diagnostic:{uuid4()}"
            _LOGGER.exception(
                "MediaSense Tool call failed [diagnostic_id=%s]", diagnostic_id
            )
            result = {
                "outcome": "error",
                "error": {
                    "code": "host_operation_failed",
                    "message": (
                        "The Tool Host encountered an internal operation failure; "
                        "no completion is implied. Retry after diagnosis."
                    ),
                    "diagnostic_id": diagnostic_id,
                },
            }
            if params.name in {"mediasense.precheck.run", "mediasense.precheck.read"}:
                result.pop("outcome", None)
            return _tool_result(result, is_error=True)
        if params.name in {"mediasense.precheck.run", "mediasense.precheck.read"}:
            result.pop("outcome", None)
        return _tool_result(
            result,
            is_error=params.name
            in {"mediasense.precheck.run", "mediasense.precheck.read"}
            and "error" in result,
            structured_error=params.name
            in {"mediasense.precheck.run", "mediasense.precheck.read"},
        )

    return Server(
        "mediasense",
        title="MediaSense",
        description="Local-first, Dataset-bound media organization Tools.",
        instructions=(
            "Open a source with mediasense.dataset.open before calling a "
            "Dataset-bound Tool. External effects are disabled by default. "
            "The Dataset-open result reports the selected workspace and configuration."
        ),
        version=application_version(),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def run_stdio() -> None:
    async def serve() -> None:
        server = create_mcp_server()
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    anyio.run(serve)


def _mcp_tool(descriptor: ToolDescriptor) -> types.Tool:
    request_schema = descriptor.input_schema
    response_schema = descriptor.output_schema
    if descriptor.name == "mediasense.plan.work":
        # MCP clients have no access to the Host's local schema registry. Bundle
        # the canonical resource (with its $id) so absolute references resolve
        # offline, including recursive Source Sets. Contract bytes stay canonical.
        frozen = json.loads(schema_path("frozen-plan.schema.json").read_text())
        request_schema = deepcopy(request_schema)
        response_schema = deepcopy(response_schema)
        request_schema.setdefault("$defs", {})["frozen_plan_resource"] = frozen
        response_schema.setdefault("$defs", {})["frozen_plan_resource"] = frozen
    if descriptor.name in {
        "mediasense.dataset.open",
        "mediasense.precheck.run",
        "mediasense.precheck.read",
    }:
        input_schema = {"type": "object", **request_schema}
    else:
        properties: dict[str, object] = {
            "dataset_ref": {
                "type": "string",
                "pattern": "^dataset:[^\\s]+$",
                "description": "Exact identity returned by mediasense.dataset.open.",
            },
            "request": request_schema,
        }
        if descriptor.name not in {
            "mediasense.precheck.run",
            "mediasense.geo.query",
        }:
            properties["authority"] = {
                "type": "object",
                "description": (
                    "Transport-only confirmation or effect authorization; omitted "
                    "for operations that do not require it."
                ),
            }
        input_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["dataset_ref", "request"],
            "properties": properties,
        }
    return types.Tool(
        name=descriptor.name,
        description=descriptor.description,
        input_schema=input_schema,
        output_schema={"type": "object", **response_schema},
        meta={
            "contract_id": descriptor.contract_id,
            "contract_digest": descriptor.contract_digest,
        },
    )


async def _elicit_precheck_authority(
    context: Any,
    runtime: RuntimeHost,
    dataset_ref: str,
    request: dict[str, Any],
) -> tuple[dict[str, Any], Mapping[str, object] | None]:
    if request.get("action") != "resume" or request.get("decision") != "proceed":
        return request, None
    confirmation = await anyio.to_thread.run_sync(
        lambda: runtime.precheck_confirmation(dataset_ref, str(request.get("run_ref")))
    )
    if not isinstance(confirmation, Mapping) or confirmation.get("kind") != (
        "external_effect"
    ):
        return request, None
    content_identity = confirmation.get("content_identity")
    disclosure = confirmation.get("disclosure")
    if not isinstance(content_identity, str) or not isinstance(disclosure, Mapping):
        return request, None
    if len(json.dumps(disclosure, ensure_ascii=False).encode()) > 524288:
        raise HostRequestError(
            "The client cannot present the complete frozen disclosure.",
            code="confirmation_unavailable",
        )
    quantity = disclosure.get("pending_logical_queries")
    unit = confirmation.get("unit")
    session = getattr(context, "session", None)
    if session is None:
        return request, None
    capabilities = getattr(session, "client_capabilities", None)
    elicitation = getattr(capabilities, "elicitation", None)
    if getattr(elicitation, "form", None) is None:
        return request, None
    try:
        elicited = await session.elicit_form(
            _precheck_authorization_message(disclosure, quantity=quantity, unit=unit),
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            related_request_id=getattr(context, "request_id", None),
        )
    except NoBackChannelError:
        _LOGGER.info(
            "MCP client did not provide Human elicitation for PreCheck authorization",
        )
        return request, None
    if elicited.action == "decline":
        return {**request, "decision": "decline"}, None
    if elicited.action == "cancel":
        return {
            "action": "pause",
            "dataset_ref": dataset_ref,
            "run_ref": request.get("run_ref"),
        }, None
    if elicited.action != "accept":
        return {"action": "status", "run_ref": request.get("run_ref")}, None
    return request, {
        "principal_ref": "human:mcp-elicitation",
        "confirmed_content_identity": content_identity,
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }


async def _elicit_geo_authority(
    context: Any,
    preflight: Mapping[str, object],
    request: Mapping[str, object] | None = None,
) -> Mapping[str, object] | None:
    if preflight.get("outcome") != "authorization_required":
        return None
    fingerprint = preflight.get("request_fingerprint")
    envelope = preflight.get("required_authorization")
    if not isinstance(fingerprint, str) or not isinstance(envelope, Mapping):
        return None
    session = getattr(context, "session", None)
    if session is None:
        return None
    capabilities = getattr(session, "client_capabilities", None)
    elicitation = getattr(capabilities, "elicitation", None)
    if getattr(elicitation, "form", None) is None:
        return None
    try:
        elicited = await session.elicit_form(
            _geo_authorization_message(envelope)
            + "\nExact request and execution disclosure: "
            + json.dumps(
                {
                    "request": request,
                    "request_fingerprint": fingerprint,
                    "execution_profile": preflight.get("execution_profile"),
                    "routing": preflight.get("routing"),
                    "recovery": preflight.get("recovery"),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
            related_request_id=getattr(context, "request_id", None),
        )
    except NoBackChannelError:
        _LOGGER.info(
            "MCP client did not provide Human elicitation for Geo authorization"
        )
        return None
    if elicited.action != "accept":
        return None
    return {
        "principal_ref": "human:mcp-elicitation",
        "request_fingerprint": fingerprint,
        "authorized_at": datetime.now(timezone.utc).isoformat(),
        "effect_envelope": dict(envelope),
    }


def _geo_authorization_message(envelope: Mapping[str, object]) -> str:
    providers = envelope.get("allowed_providers")
    provider_names = (
        ", ".join(str(item) for item in providers)
        if isinstance(providers, list)
        else "unknown"
    )
    data_classes = envelope.get("allowed_data_classes")
    transmitted = (
        ", ".join(str(item) for item in data_classes)
        if isinstance(data_classes, list)
        else "unknown"
    )
    return "\n".join(
        [
            "Authorize this exact MediaSense Geo request.",
            f"Logical queries: {envelope.get('max_logical_queries', 'unknown')}.",
            f"Data sent: {transmitted}. Media files are not sent.",
            f"Providers: {provider_names}.",
            f"Maximum provider requests: {envelope.get('max_provider_requests', 'unknown')}.",
            f"Maximum billable units: {envelope.get('max_billable_units', 'unknown')}.",
            f"Retention: {envelope.get('retention', 'unknown')}.",
            "Accept to authorize this request. Decline or dismiss to make no external call.",
        ]
    )


def _precheck_authorization_message(
    disclosure: Mapping[str, object], *, quantity: object, unit: object
) -> str:
    providers = disclosure.get("providers")
    provider_names: list[str] = []
    handling: list[str] = []
    if isinstance(providers, list):
        for item in providers:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("provider", "unknown"))
            provider_names.append(name)
            handling.append(f"{name}: {item.get('data_handling', 'unknown')}")
    data_classes = disclosure.get("transmitted_data_classes")
    transmitted = (
        ", ".join(str(item) for item in data_classes)
        if isinstance(data_classes, list)
        else "unknown"
    )
    query_count = str(quantity) if isinstance(quantity, int) else "unknown"
    query_unit = (
        str(unit).replace("_", " ") if isinstance(unit, str) else "logical queries"
    )
    return "\n".join(
        [
            "Authorize MediaSense to reverse-geocode this exact frozen batch.",
            f"Scope: {query_count} {query_unit}.",
            f"Data sent: {transmitted}. Media files are not sent.",
            f"Providers: {', '.join(provider_names) or 'unknown'}.",
            f"Maximum provider requests: {disclosure.get('max_provider_requests', 'unknown')}.",
            f"Billing: {disclosure.get('billable_calls', 'unknown')}.",
            f"Provider data handling: {'; '.join(handling) or 'unknown'}.",
            f"Result retention: {disclosure.get('result_retention', 'unknown')}.",
            "Exact frozen disclosure: "
            + json.dumps(dict(disclosure), ensure_ascii=False, sort_keys=True),
            "Accept to authorize and continue. Decline to cancel this Run. "
            "Dismiss to leave the Run paused.",
        ]
    )


def _tool_result(
    result: dict[str, object], *, is_error: bool = False, structured_error: bool = False
) -> types.CallToolResult:
    return types.CallToolResult(
        content=[],
        structured_content=result,
        is_error=is_error,
    )
