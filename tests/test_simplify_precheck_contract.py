from __future__ import annotations

from pathlib import Path
from time import monotonic, sleep

from PIL import Image

from mediasense.runtime.host import RuntimeHost


def test_production_run_read_plan_without_location(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (80, 40), "purple").save(source / "image.jpg")
    original = (source / "image.jpg").read_bytes()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    dataset = opened["dataset_ref"]

    def run(action, **values):
        return host.call_tool(
            "mediasense.precheck.run",
            dataset_ref=dataset,
            request={"action": action, "dataset_ref": dataset, **values},
        )

    started = run("start", request_id="request:compact")
    assert set(started) == {"run_ref"}
    ref = started["run_ref"]
    deadline = monotonic() + 15
    while monotonic() < deadline:
        status = run("status", run_ref=ref)
        if status.get("state") != "running":
            break
        sleep(0.01)
    assert status["state"] == "paused", status
    confirmation = status["confirmation"]
    assert confirmation["kind"] == "source_scope"
    assert confirmation["inventory"]["view"]["entries"]
    response = run(
        "resume",
        run_ref=ref,
        decision={
            "kind": "source_scope",
            "inventory_fingerprint": confirmation["inventory_fingerprint"],
            "default_disposition": "include",
            "exceptions": [],
        },
    )
    assert response == {"state": "running"}
    while monotonic() < deadline:
        status = run("status", run_ref=ref)
        if status.get("state") != "running":
            break
        sleep(0.01)
    assert status["state"] == "completed", status
    assert status["result"]["readiness"] == "plan_ready"
    result_ref = status["result"]["ref"]
    review = host.call_tool(
        "mediasense.precheck.read",
        dataset_ref=dataset,
        request={"action": "review", "dataset_ref": dataset, "result_ref": result_ref},
    )
    assert review["accounting"]["total"] == 1
    assert review["page"]["next_cursor"] is None
    plan = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset,
        request={
            "action": "create",
            "result_ref": result_ref,
            "request_id": "request:plan",
        },
    )
    assert plan["outcome"] == "ok", plan
    assert run("start", request_id="request:compact") == started
    assert (source / "image.jpg").read_bytes() == original


def test_all_nine_actions_and_failed_run_observation_over_real_stdio(
    tmp_path: Path,
) -> None:
    import sys
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    source = tmp_path / "media"
    source.mkdir()
    Image.new("RGB", (40, 30), "blue").save(source / "one.jpg")
    workspace = tmp_path / "state"
    original = (source / "one.jpg").read_bytes()
    fixture_host = RuntimeHost()
    opened = fixture_host.open_dataset(str(source), str(workspace))
    dataset = opened["dataset_ref"]
    fixture_run = fixture_host._datasets[dataset].precheck_run
    failed_ref = fixture_run.run(
        {
            "action": "start",
            "dataset_ref": dataset,
            "request_id": "request:failed-fixture",
        }
    )["run_ref"]
    fixture_run.mark_failed(
        failed_ref, code="synthetic_failure", message="Synthetic retained failure."
    )

    async def scenario():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mediasense", "mcp"],
            cwd=str(Path(__file__).parents[1]),
            env={
                "MEDIASENSE_CONFIG_HOME": str(tmp_path / "config"),
                "MEDIASENSE_DATA_HOME": str(tmp_path / "data"),
                "AMAP_API_KEY": "",
                "GOOGLE_MAPS_API_KEY": "",
            },
        )
        async with (
            stdio_client(parameters) as (incoming, outgoing),
            ClientSession(incoming, outgoing) as session,
        ):
            await session.initialize()
            opened = await session.call_tool(
                "mediasense.dataset.open",
                {"source_root": str(source), "workspace": str(workspace)},
            )
            assert opened.structured_content["dataset_ref"] == dataset
            actions = set()

            async def call(tool, action, **values):
                actions.add(action)
                response = await session.call_tool(
                    "mediasense.precheck." + tool,
                    {"action": action, "dataset_ref": dataset, **values},
                )
                assert not response.is_error, response
                assert response.structured_content is not None
                return response.structured_content

            async def attention(ref):
                with anyio.fail_after(15):
                    while True:
                        status = await call("run", "status", run_ref=ref)
                        if status["state"] != "running":
                            return status
                        await anyio.sleep(0.01)

            failed = await call("run", "status", run_ref=failed_ref)
            assert failed == {
                "state": "failed",
                "reason": {
                    "code": "synthetic_failure",
                    "message": "Synthetic retained failure.",
                },
            }
            started = await call("run", "start", request_id="request:stdio-nine")
            run_ref = started["run_ref"]
            paused = await attention(run_ref)
            assert paused["state"] == "paused"
            assert await call("run", "pause", run_ref=run_ref) == {"state": "paused"}
            assert await call(
                "run",
                "resume",
                run_ref=run_ref,
                decision={
                    "kind": "source_scope",
                    "inventory_fingerprint": paused["confirmation"][
                        "inventory_fingerprint"
                    ],
                    "default_disposition": "include",
                    "exceptions": [],
                },
            ) == {"state": "running"}
            complete = await attention(run_ref)
            assert complete["state"] == "completed"
            result_ref = complete["result"]["ref"]
            review = await call(
                "read", "review", result_ref=result_ref, include=["execution_boundary"]
            )
            assert review["execution_boundary"]["current_provider_requests"] == 0
            expanded = await call(
                "read",
                "expand",
                result_ref=result_ref,
                evidence_refs=[review["items"][0]["evidence_ref"]],
                include=[
                    "anchor_evidence",
                    "prepared_targets",
                    "provenance",
                    "coverage_basis",
                ],
            )
            assert expanded["items"] and expanded["page"]["next_cursor"] is None
            resolved = await call(
                "read",
                "resolve",
                result_ref=result_ref,
                source_set={
                    "kind": "precheck_relation",
                    "origin": result_ref,
                    "relation": "accounts_for",
                    "direction": "outbound",
                },
            )
            assert len(resolved["members"]) == resolved["page"]["total"] == 1
            geo = await call("read", "geo_summary", result_ref=result_ref)
            assert geo["acquisition_status"] == "not_applicable"
            # A completed Result is immutable: cancellation is a business error.
            refused = await session.call_tool(
                "mediasense.precheck.run",
                {"action": "cancel", "dataset_ref": dataset, "run_ref": run_ref},
            )

            assert (
                refused.is_error
                and refused.structured_content["error"]["code"]
                == "invalid_state"
            )
            actions.add("cancel")
            Image.new("RGB", (40, 30), "green").save(source / "two.jpg")
            second = await call(
                "run",
                "start",
                request_id="request:stdio-cancel",
                prior_result_ref=result_ref,
            )
            second_pause = await attention(second["run_ref"])
            assert second_pause["state"] == "paused"
            assert await call("run", "cancel", run_ref=second["run_ref"]) == {
                "state": "cancelled"
            }
            cancelled = await call("run", "status", run_ref=second["run_ref"])
            assert cancelled["state"] == "cancelled" and "result" not in cancelled
            assert actions == {
                "start",
                "status",
                "pause",
                "resume",
                "cancel",
                "review",
                "expand",
                "resolve",
                "geo_summary",
            }
            legacy = await session.call_tool(
                "mediasense.precheck.read",
                {
                    "dataset_ref": dataset,
                    "request": {"operation": "review", "result_ref": result_ref},
                },
            )
            assert legacy.is_error
            assert (source / "one.jpg").read_bytes() == original

    anyio.run(scenario)
