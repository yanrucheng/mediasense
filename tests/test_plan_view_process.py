"""Actual ordinary CLI clients share one host; no startup/render client step."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import sys

from mediasense.runtime import plan_views
from test_runtime_host import _opened_host_with_plan_ready_result


def test_simultaneous_first_cli_delivery_and_state_only_do_not_start(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("MEDIASENSE_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(tmp_path / "config"))
    host, dataset, result, *_ = _opened_host_with_plan_ready_result(tmp_path)
    tool = host._datasets[dataset].plan_work
    tool.view_delivery = None
    state = tool.handle(
        {"action": "create", "result_ref": result, "request_id": "request:cli-create"}
    )
    prefix = [
        sys.executable,
        "-m",
        "mediasense",
        "tools",
        "call",
        "mediasense.plan.work",
        "--source",
        str(tmp_path / "source"),
        "--workspace",
        str(tmp_path / "workspace"),
    ]

    def inspect(sections):
        response = subprocess.run(
            prefix
            + [
                "--request",
                json.dumps(
                    {
                        "action": "inspect",
                        "work_ref": state["work_ref"],
                        "sections": sections,
                    }
                ),
                "--json",
            ],
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            timeout=30,
            check=True,
        )
        return json.loads(response.stdout)["result"]

    assert inspect(["working_notes"])["revision"] == state["revision"]
    assert plan_views.control("status")["state"] == "stopped"
    assert not plan_views.runtime_directory(create=False).exists()
    try:
        with ThreadPoolExecutor(4) as pool:
            responses = list(pool.map(inspect, [["view"]] * 4))
        views = [r["sections"]["view"] for r in responses]
        assert all(v["status"] == "ready" for v in views)
        assert len({v["current_uri"] for v in views}) == 1
        assert {v["revision"] for v in views} == {state["revision"]}
        status = plan_views.control("status")
        assert (
            status["state"] == "running" and status["routes"] == status["contexts"] == 1
        )
        before = tool.store.snapshot(state["work_ref"])
        stopped = plan_views.control("stop")
        assert stopped["state"] == "stopped" and stopped["exit_verified"]
        recovered = inspect(["view"])
        assert recovered["sections"]["view"]["current_uri"] != views[0]["current_uri"]
        assert tool.store.snapshot(state["work_ref"]) == before
    finally:
        assert plan_views.control("stop")["state"] == "stopped"


def test_real_retiring_bind_reconnects_once_without_resaving(tmp_path, monkeypatch):
    import time
    from types import SimpleNamespace

    monkeypatch.setenv("MEDIASENSE_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(tmp_path / "config"))
    host, dataset, result, *_ = _opened_host_with_plan_ready_result(tmp_path)
    tool = host._datasets[dataset].plan_work
    tool.view_delivery = None
    receipt = tool.handle(
        {"action": "create", "result_ref": result, "request_id": "request:race"}
    )
    before = tool.store.snapshot(receipt["work_ref"])
    root = plan_views.runtime_directory()
    code = """
import time
from mediasense.plan.view import PlanView
from mediasense.runtime._view_server import main
original=PlanView.overview
def slow(self, revision):
 time.sleep(2)
 return original(self, revision)
PlanView.overview=slow
main()
"""
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(root), plan_views.build_identity()]
    )
    original_rpc = plan_views.rpc
    info = None
    try:
        deadline = time.monotonic() + 12
        while info is None and time.monotonic() < deadline:
            info = plan_views._info(root)
            time.sleep(0.01)
        assert info is not None
        value = {
            "workspace": str(tmp_path / "workspace"),
            "dataset_ref": dataset,
            "work_ref": receipt["work_ref"],
            "revision": receipt["revision"],
        }
        with ThreadPoolExecutor(1) as pool:
            active = pool.submit(original_rpc, info, "bind", value)
            while original_rpc(info, "health")["inflight"] == 0:
                assert time.monotonic() < deadline
                time.sleep(0.01)
            calls = []

            def race(info, action, value=None, **kwargs):
                if action == "bind":
                    calls.append(value)
                    if len(calls) == 1:
                        original_rpc(info, "stop", timeout=1)
                return original_rpc(info, action, value, **kwargs)

            monkeypatch.setattr(plan_views, "rpc", race)
            delivered = plan_views.deliver(
                SimpleNamespace(
                    workspace=tmp_path / "workspace",
                    manifest=SimpleNamespace(dataset_ref=dataset),
                ),
                receipt,
            )
            assert delivered["status"] == "ready"
            assert len(calls) == 2 and calls[0] == calls[1] == value
            assert active.result()["status"] == "ready"
        assert child.wait(timeout=2) == 0
        assert plan_views.control("status")["instance"] != info["instance"]
        assert tool.store.snapshot(receipt["work_ref"]) == before
    finally:
        plan_views.control("stop")
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=3)
