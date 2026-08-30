"""MCP stdio adapter over the MediaSense runtime host."""

from __future__ import annotations

import json
from typing import Any

import anyio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .composition import HostRequestError, ToolDescriptor, tool_descriptors
from .host import RuntimeHost
from .versioning import application_version


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
                request = arguments.get("request")
                authority = arguments.get("authority")
                if not isinstance(dataset_ref, str) or not dataset_ref:
                    raise HostRequestError("dataset_ref must be a non-empty string")
                if not isinstance(request, dict):
                    raise HostRequestError("request must be an object")
                if authority is not None and not isinstance(authority, dict):
                    raise HostRequestError("authority must be an object")
                result = await anyio.to_thread.run_sync(
                    lambda: runtime.call_tool(
                        params.name,
                        dataset_ref=dataset_ref,
                        request=request,
                        authority=authority,
                    )
                )
        except (HostRequestError, TypeError, ValueError) as error:
            result = {
                "outcome": "error",
                "error": {"code": "host_invalid_request", "message": str(error)},
            }
            return _tool_result(result, is_error=True)
        return _tool_result(result)

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
    if descriptor.name == "mediasense.dataset.open":
        input_schema = descriptor.input_schema
    else:
        input_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["dataset_ref", "request"],
            "properties": {
                "dataset_ref": {
                    "type": "string",
                    "pattern": "^dataset:[^\\s]+$",
                    "description": "Exact identity returned by mediasense.dataset.open.",
                },
                "request": descriptor.input_schema,
                "authority": {
                    "type": "object",
                    "description": (
                        "Transport-only trusted confirmation or effect authorization; "
                        "omitted for operations that do not require it."
                    ),
                },
            },
        }
    return types.Tool(
        name=descriptor.name,
        description=descriptor.description,
        input_schema=input_schema,
        output_schema={"type": "object", **descriptor.output_schema},
        meta={
            "contract_id": descriptor.contract_id,
            "contract_digest": descriptor.contract_digest,
        },
    )


def _tool_result(
    result: dict[str, object], *, is_error: bool = False
) -> types.CallToolResult:
    return types.CallToolResult(
        content=[
            types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False, sort_keys=True),
            )
        ],
        structured_content=None if is_error else result,
        is_error=is_error,
    )
