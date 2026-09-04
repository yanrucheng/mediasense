from __future__ import annotations

import sys
from pathlib import Path
import subprocess
import json
import sqlite3

import anyio
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from PIL import Image

from mediasense.runtime.mcp_host import create_mcp_server


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


class FailingRuntimeHost:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def call_tool(self, *_args, **_kwargs):
        raise self.error


def _host_error(
    error: Exception, *, arguments: dict | None = None
) -> dict[str, object]:
    async def scenario() -> dict[str, object]:
        server = create_mcp_server(FailingRuntimeHost(error))  # type: ignore[arg-type]
        entry = server.get_request_handler("tools/call")
        assert entry is not None
        result = await entry.handler(
            None,
            types.CallToolRequestParams(
                name="mediasense.plan.work",
                arguments=(
                    {"dataset_ref": "dataset:test", "request": {}}
                    if arguments is None
                    else arguments
                ),
            ),
        )
        assert result.is_error is True
        assert result.structured_content is None
        return json.loads(result.content[0].text)

    return anyio.run(scenario)


def test_mcp_host_reports_request_binding_failure() -> None:
    result = _host_error(AssertionError("runtime must not be called"), arguments={})

    assert result == {
        "outcome": "error",
        "error": {
            "code": "host_invalid_request",
            "message": "dataset_ref must be a non-empty string",
        },
    }


def test_mcp_host_sanitizes_unexpected_operation_failure(caplog) -> None:
    result = _host_error(TypeError("sensitive implementation detail"))

    assert result["outcome"] == "error"
    assert result["error"]["code"] == "host_operation_failed"
    assert str(result["error"]["diagnostic_id"]).startswith("diagnostic:")
    assert "sensitive implementation detail" not in result["error"]["message"]
    assert str(result["error"]["diagnostic_id"]) in caplog.text
    assert "TypeError" in caplog.text


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


def test_stdio_mcp_scope_confirmation_resume_continues_the_same_run(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "original.jpg"
    Image.new("RGB", (80, 40), "purple").save(media)
    source_before = media.read_bytes()
    workspace = tmp_path / "workspace"

    async def scenario() -> None:
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mediasense", "mcp"],
            cwd=str(ROOT),
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
            dataset_ref = str(opened.structured_content["dataset_ref"])
            started = await session.call_tool(
                "mediasense.precheck.run",
                {
                    "dataset_ref": dataset_ref,
                    "request": {
                        "action": "start",
                        "dataset_ref": dataset_ref,
                        "request_id": "request:mcp-scope-resume",
                    },
                },
            )
            assert started.structured_content is not None
            run_ref = str(started.structured_content["run_ref"])

            paused: dict[str, object] | None = None
            for _ in range(500):
                current = await session.call_tool(
                    "mediasense.precheck.run",
                    {
                        "dataset_ref": dataset_ref,
                        "request": {"action": "status", "run_ref": run_ref},
                    },
                )
                assert current.structured_content is not None
                paused = dict(current.structured_content)
                if paused["state"] != "running":
                    break
                await anyio.sleep(0.01)
            assert paused is not None
            assert paused["state"] == "paused"
            assert paused["reason"]["code"] == "scope_confirmation_required"

            database = workspace / "precheck" / "work.sqlite3"
            with sqlite3.connect(database) as connection:
                before = connection.execute(
                    "SELECT run_id, status FROM working_runs ORDER BY started_at"
                ).fetchall()
                bound_run = connection.execute(
                    "SELECT accounting_run_id FROM precheck_runs WHERE run_ref = ?",
                    (run_ref,),
                ).fetchone()[0]
            assert before == [(bound_run, "completed")]

            resumed = await session.call_tool(
                "mediasense.precheck.run",
                {
                    "dataset_ref": dataset_ref,
                    "request": {
                        "action": "resume",
                        "run_ref": run_ref,
                        "decision": {
                            "kind": "source_scope",
                            "inventory_fingerprint": paused["confirmation"][
                                "inventory"
                            ]["inventory_fingerprint"],
                            "default_disposition": "include",
                            "exceptions": [],
                        },
                    },
                },
            )
            assert resumed.is_error is False
            assert resumed.structured_content is not None
            assert resumed.structured_content["outcome"] == "accepted"

            finished: dict[str, object] | None = None
            for _ in range(1000):
                current = await session.call_tool(
                    "mediasense.precheck.run",
                    {
                        "dataset_ref": dataset_ref,
                        "request": {"action": "status", "run_ref": run_ref},
                    },
                )
                assert current.structured_content is not None
                finished = dict(current.structured_content)
                if finished["state"] != "running":
                    break
                await anyio.sleep(0.01)
            assert finished is not None
            assert finished["state"] == "completed", finished

            with sqlite3.connect(database) as connection:
                after = connection.execute(
                    "SELECT run_id, status FROM working_runs ORDER BY started_at"
                ).fetchall()
                public = connection.execute(
                    "SELECT state, accounting_run_id FROM precheck_runs WHERE run_ref = ?",
                    (run_ref,),
                ).fetchone()
                scope_state = connection.execute(
                    """
                    SELECT state FROM precheck_scope_reviews
                    WHERE run_ref = ? ORDER BY revision DESC LIMIT 1
                    """,
                    (run_ref,),
                ).fetchone()[0]
                orphan_running = connection.execute(
                    """
                    SELECT COUNT(*) FROM working_runs AS accounting
                    LEFT JOIN precheck_runs AS public
                      ON public.accounting_run_id = accounting.run_id
                    WHERE accounting.status = 'running' AND public.run_ref IS NULL
                    """
                ).fetchone()[0]
            assert after == [(bound_run, "completed")]
            assert public == ("completed", bound_run)
            assert scope_state == "accepted"
            assert orphan_running == 0
            assert media.read_bytes() == source_before

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


def test_stdio_mcp_plan_create_reaches_precheck_read_boundary(tmp_path: Path) -> None:
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

            created = await session.call_tool(
                "mediasense.plan.work",
                {
                    "dataset_ref": dataset_ref,
                    "request": {
                        "action": "create",
                        "result_ref": "precheck-result:not-found",
                        "request_id": "request:stdio-plan-create",
                    },
                },
            )
            assert created.is_error is False
            assert created.structured_content is not None
            assert created.structured_content["outcome"] == "error"
            assert created.structured_content["error"]["code"] == "result_not_found"

    anyio.run(scenario)
