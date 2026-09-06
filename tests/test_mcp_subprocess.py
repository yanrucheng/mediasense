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


class GeoElicitationRuntimeHost:
    content_identity = "sha256:" + "a" * 64
    disclosure = {
        "frozen_batch_identity": "sha256:" + "b" * 64,
        "operation": "reverse_geocode",
        "coordinates": [{"latitude": 22.3193, "longitude": 114.1694, "datum": "WGS84"}],
        "transmitted_data_classes": ["coordinate", "datum", "locale"],
        "providers": [
            {
                "provider": "fake_maps",
                "data_handling": "unknown",
                "max_provider_requests": 1,
            }
        ],
        "max_provider_requests": 1,
        "billable_calls": "unknown",
        "result_retention": "immutable_precheck_result",
    }

    def __init__(self) -> None:
        self.authorities: list[object] = []
        self.provider_coordinates: list[object] = []

    def call_tool(
        self,
        name: str,
        *,
        dataset_ref: str,
        request: dict[str, object],
        authority: object = None,
    ) -> dict[str, object]:
        assert name == "mediasense.precheck.run"
        assert dataset_ref == "dataset:test"
        if request.get("action") == "status":
            return {
                "outcome": "ok",
                "action": "status",
                "run_ref": "precheck-run:test",
                "dataset_ref": "dataset:test",
                "state": "paused",
                "progress": {
                    "discovered": 1,
                    "accounted": 1,
                    "usable": 1,
                    "exceptional": 0,
                    "unresolved": 0,
                },
                "activity": {
                    "state": "waiting",
                    "phase": "external_evidence",
                    "work": {
                        "completed": 0,
                        "reused": 0,
                        "failed": 0,
                        "remaining": 1,
                        "total": 1,
                    },
                    "last_progress_at": "unknown",
                    "errors": {"total": 0, "by_phase": [], "truncated": False},
                },
                "allowed_actions": ["resume", "cancel"],
                "reason": {
                    "code": "confirmation_required",
                    "message": "Human authorization is required.",
                },
                "confirmation": {
                    "kind": "external_effect",
                    "summary": "Reverse-geocode one coordinate.",
                    "content_identity": self.content_identity,
                    "quantity": 1,
                    "unit": "logical_queries",
                    "skip_allowed": False,
                    "disclosure": self.disclosure,
                },
            }
        self.authorities.append(authority)
        if request.get("decision") == "decline":
            return {
                "outcome": "accepted",
                "action": "resume",
                "run_ref": "precheck-run:test",
                "observed_state": "paused",
                "target_state": "cancelled",
            }
        if authority is None:
            return {
                "outcome": "error",
                "action": "resume",
                "run_ref": "precheck-run:test",
                "error": {
                    "code": "authorization_required",
                    "message": "Human authorization is required.",
                },
            }
        self.provider_coordinates.extend(self.disclosure["coordinates"])
        return {
            "outcome": "accepted",
            "action": "resume",
            "run_ref": "precheck-run:test",
            "observed_state": "paused",
            "target_state": "running",
        }


class DirectGeoRuntimeHost:
    fingerprint = "sha256:" + "c" * 64
    envelope = {
        "allowed_providers": ["fake_maps"],
        "allowed_data_classes": ["coordinate", "datum", "locale"],
        "max_logical_queries": 1,
        "max_provider_requests": 1,
        "max_billable_units": None,
        "allow_unknown_billable_units": True,
        "retention": "none",
    }

    def __init__(self) -> None:
        self.authorities: list[object] = []

    def call_tool(
        self,
        name: str,
        *,
        dataset_ref: str,
        request: dict[str, object],
        authority: object = None,
    ) -> dict[str, object]:
        assert name == "mediasense.geo.query"
        assert dataset_ref == "dataset:test"
        self.authorities.append(authority)
        if authority is None:
            return {
                "tool": "mediasense.geo.query",
                "request_id": str(request["request_id"]),
                "outcome": "authorization_required",
                "operation": "reverse_geocode",
                "request_fingerprint": self.fingerprint,
                "components": [],
                "attempts": [],
                "effects": {
                    "logical_queries": 0,
                    "provider_requests": 0,
                    "billable_units": 0,
                    "transmitted_data_classes": [],
                    "providers_attempted": [],
                },
                "continuations": [],
                "observed_at": "2026-09-06T12:00:00+08:00",
                "qualifications": [
                    {
                        "code": "authorization_required",
                        "message": "No provider request was sent.",
                    }
                ],
                "route_context": {"preferred_provider": None, "locale": None},
                "required_authorization": self.envelope,
            }
        return {
            "tool": "mediasense.geo.query",
            "request_id": str(request["request_id"]),
            "outcome": "success",
            "operation": "reverse_geocode",
            "request_fingerprint": self.fingerprint,
            "components": [
                {
                    "operation": "reverse_geocode",
                    "status": "success",
                    "subject_refs": ["source-item:test"],
                    "coordinate": {
                        "latitude": 22.3193,
                        "longitude": 114.1694,
                        "datum": "WGS84",
                    },
                    "candidates": [
                        {"kind": "address", "name": "Hong Kong", "components": {}}
                    ],
                    "qualifications": [],
                }
            ],
            "attempts": [
                {
                    "provider": "fake_maps",
                    "operation": "reverse_geocode",
                    "status": "success",
                    "input_coordinate": {
                        "latitude": 22.3193,
                        "longitude": 114.1694,
                        "datum": "WGS84",
                    },
                    "provider_coordinate": {
                        "latitude": 22.3193,
                        "longitude": 114.1694,
                        "datum": "WGS84",
                    },
                    "provider_requests": 1,
                    "billable_units": None,
                }
            ],
            "effects": {
                "logical_queries": 1,
                "provider_requests": 1,
                "billable_units": None,
                "transmitted_data_classes": ["coordinate", "datum", "locale"],
                "providers_attempted": ["fake_maps"],
            },
            "continuations": [],
            "observed_at": "2026-09-06T12:00:00+08:00",
            "qualifications": [],
            "route_context": {"preferred_provider": "fake_maps", "locale": "zh-CN"},
        }


async def _mcp_geo_resume(
    runtime: GeoElicitationRuntimeHost,
    elicitation_callback=None,
) -> types.CallToolResult:
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream(
        10
    )
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream(
        10
    )
    server = create_mcp_server(runtime)  # type: ignore[arg-type]
    result: types.CallToolResult
    async with anyio.create_task_group() as group:
        group.start_soon(
            server.run,
            client_to_server_receive,
            server_to_client_send,
            server.create_initialization_options(),
        )
        async with ClientSession(
            server_to_client_receive,
            client_to_server_send,
            elicitation_callback=elicitation_callback,
        ) as session:
            await session.initialize()
            result = await session.call_tool(
                "mediasense.precheck.run",
                {
                    "dataset_ref": "dataset:test",
                    "request": {
                        "action": "resume",
                        "run_ref": "precheck-run:test",
                        "decision": "proceed",
                    },
                },
            )
        group.cancel_scope.cancel()
    return result


async def _mcp_direct_geo(
    runtime: DirectGeoRuntimeHost,
    elicitation_callback=None,
) -> types.CallToolResult:
    server_to_client_send, server_to_client_receive = anyio.create_memory_object_stream(
        10
    )
    client_to_server_send, client_to_server_receive = anyio.create_memory_object_stream(
        10
    )
    server = create_mcp_server(runtime)  # type: ignore[arg-type]
    result: types.CallToolResult
    async with anyio.create_task_group() as group:
        group.start_soon(
            server.run,
            client_to_server_receive,
            server_to_client_send,
            server.create_initialization_options(),
        )
        async with ClientSession(
            server_to_client_receive,
            client_to_server_send,
            elicitation_callback=elicitation_callback,
        ) as session:
            await session.initialize()
            result = await session.call_tool(
                "mediasense.geo.query",
                {
                    "dataset_ref": "dataset:test",
                    "request": {
                        "request_id": "request:direct-geo",
                        "operation": "reverse_geocode",
                        "subjects": [
                            {
                                "subject_ref": "source-item:test",
                                "coordinate": {
                                    "latitude": 22.3193,
                                    "longitude": 114.1694,
                                    "datum": "WGS84",
                                },
                            }
                        ],
                        "locale": "zh-CN",
                    },
                },
            )
        group.cancel_scope.cancel()
    return result


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


def test_mcp_geo_resume_uses_session_elicitation_as_trusted_authority() -> None:
    prompts: list[types.ElicitRequestParams] = []

    async def approve(_context, params):
        prompts.append(params)
        return types.ElicitResult(action="accept", content={})

    async def decline(_context, _params):
        return types.ElicitResult(action="decline")

    async def cancel(_context, _params):
        return types.ElicitResult(action="cancel")

    async def fail(_context, _params):
        return types.ErrorData(
            code=types.INTERNAL_ERROR,
            message="elicitation implementation failed",
        )

    async def scenario() -> None:
        accepted_runtime = GeoElicitationRuntimeHost()
        accepted = await _mcp_geo_resume(accepted_runtime, approve)
        assert accepted.is_error is False
        assert accepted.structured_content is not None
        assert accepted.structured_content["target_state"] == "running"
        assert (
            accepted_runtime.provider_coordinates
            == (accepted_runtime.disclosure["coordinates"])
        )
        assert accepted_runtime.authorities == [
            {
                "principal_ref": "human:mcp-elicitation",
                "confirmed_content_identity": accepted_runtime.content_identity,
                "confirmed_at": accepted_runtime.authorities[0]["confirmed_at"],
            }
        ]
        assert prompts[0].requested_schema == {
            "type": "object",
            "additionalProperties": False,
            "properties": {},
        }
        assert "boolean" not in json.dumps(prompts[0].requested_schema)
        assert "1 logical queries" in prompts[0].message
        assert "fake_maps" in prompts[0].message
        assert "Maximum provider requests: 1" in prompts[0].message
        assert "Media files are not sent" in prompts[0].message
        assert "22.3193" not in prompts[0].message

        declined_runtime = GeoElicitationRuntimeHost()
        declined = await _mcp_geo_resume(declined_runtime, decline)
        assert declined.is_error is False
        assert declined.structured_content is not None
        assert declined.structured_content["target_state"] == "cancelled"
        assert declined_runtime.authorities == [None]
        assert declined_runtime.provider_coordinates == []

        cancelled_runtime = GeoElicitationRuntimeHost()
        cancelled = await _mcp_geo_resume(cancelled_runtime, cancel)
        assert cancelled.is_error is False
        assert cancelled.structured_content is not None
        assert cancelled.structured_content["state"] == "paused"
        assert cancelled_runtime.authorities == []
        assert cancelled_runtime.provider_coordinates == []

        unsupported_runtime = GeoElicitationRuntimeHost()
        unsupported = await _mcp_geo_resume(unsupported_runtime)
        assert unsupported.structured_content is not None
        assert unsupported.structured_content["error"]["code"] == (
            "authorization_required"
        )
        assert unsupported_runtime.authorities == [None]
        assert unsupported_runtime.provider_coordinates == []

        failed_runtime = GeoElicitationRuntimeHost()
        failed = await _mcp_geo_resume(failed_runtime, fail)
        assert failed.is_error is True
        assert failed.structured_content is None
        failed_payload = json.loads(failed.content[0].text)
        assert failed_payload["error"]["code"] == "host_operation_failed"
        assert (
            "elicitation implementation failed"
            not in (failed_payload["error"]["message"])
        )
        assert failed_runtime.authorities == []
        assert failed_runtime.provider_coordinates == []

    anyio.run(scenario)


def test_mcp_direct_geo_uses_session_elicitation_as_trusted_authority() -> None:
    prompts: list[types.ElicitRequestParams] = []

    async def approve(_context, params):
        prompts.append(params)
        return types.ElicitResult(action="accept", content={})

    async def scenario() -> None:
        runtime = DirectGeoRuntimeHost()
        result = await _mcp_direct_geo(runtime, approve)
        assert result.is_error is False
        assert result.structured_content is not None
        assert result.structured_content["outcome"] == "success"
        assert runtime.authorities[0] is None
        assert runtime.authorities[1] == {
            "principal_ref": "human:mcp-elicitation",
            "request_fingerprint": runtime.fingerprint,
            "authorized_at": runtime.authorities[1]["authorized_at"],
            "effect_envelope": runtime.envelope,
        }
        assert "Maximum provider requests: 1" in prompts[0].message
        assert "Media files are not sent" in prompts[0].message

    anyio.run(scenario)


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
            assert "authority" not in precheck_run.input_schema["properties"]
            geo_query = next(
                tool for tool in listed.tools if tool.name == "mediasense.geo.query"
            )
            assert "authority" not in geo_query.input_schema["properties"]
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
