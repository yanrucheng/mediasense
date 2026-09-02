from __future__ import annotations

import sys
from pathlib import Path
import subprocess

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {
    "mediasense.dataset.open",
    "mediasense.precheck.run",
    "mediasense.precheck.read",
    "mediasense.plan.work",
    "mediasense.geo.query",
    "mediasense.apply.run",
    "mediasense.apply.read",
}


def test_stdio_mcp_handshake_discovery_and_non_destructive_call(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace = tmp_path / "workspace"

    async def scenario() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mediasense", "mcp"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            initialized = await session.initialize()
            assert initialized.server_info.name == "mediasense"
            listed = await session.list_tools()
            names = {tool.name for tool in listed.tools}
            assert names == EXPECTED_TOOLS
            precheck_run = next(
                tool for tool in listed.tools if tool.name == "mediasense.precheck.run"
            )
            assert precheck_run.input_schema["properties"]["request"]["$id"] == (
                "urn:mediasense:tool:precheck-run-input"
            )
            assert precheck_run.output_schema is not None
            assert precheck_run.output_schema["type"] == "object"
            opened = await session.call_tool(
                "mediasense.dataset.open",
                {"source_root": str(source), "workspace": str(workspace)},
            )
            assert opened.is_error is False
            assert opened.structured_content is not None
            dataset_ref = opened.structured_content["dataset_ref"]
            status = await session.call_tool(
                "mediasense.precheck.run",
                {
                    "dataset_ref": dataset_ref,
                    "request": {
                        "action": "status",
                        "run_ref": "precheck-run:not-found",
                    },
                },
            )
            assert status.is_error is False
            assert status.structured_content is not None
            assert status.structured_content["outcome"] == "error"
            assert status.structured_content["error"]["code"] == "run_not_found"

    anyio.run(scenario)


def test_stdio_mcp_exits_when_client_closes_input() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "mediasense", "mcp"],
        input="",
        text=True,
        capture_output=True,
        cwd=ROOT,
        timeout=5,
        check=False,
    )

    assert completed.returncode == 0


def test_stdio_mcp_opened_dataset_can_start_precheck(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace = tmp_path / "workspace"

    async def scenario() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mediasense", "mcp"],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with (
            stdio_client(parameters) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream) as session,
        ):
            await session.initialize()
            opened = await session.call_tool(
                "mediasense.dataset.open",
                {"source_root": str(source), "workspace": str(workspace)},
            )
            assert opened.is_error is False
            assert opened.structured_content is not None
            dataset_ref = opened.structured_content["dataset_ref"]

            started = await session.call_tool(
                "mediasense.precheck.run",
                {
                    "dataset_ref": dataset_ref,
                    "request": {
                        "action": "start",
                        "dataset_ref": dataset_ref,
                        "request_id": "request:stdio-first-use",
                    },
                },
            )

            assert started.is_error is False
            assert started.structured_content is not None
            assert started.structured_content["outcome"] == "ok"
            assert str(started.structured_content["run_ref"]).startswith(
                "precheck-run:"
            )

    anyio.run(scenario)
