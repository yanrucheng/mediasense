"""L01-L18 mechanism boundaries; real CLI/browser coverage has its own runner."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import replace
import fcntl
import json
import logging
import os
from pathlib import Path
import sqlite3
from threading import Barrier, Event, Thread
import time
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import weakref

import pytest

from mediasense.plan._sqlite import SQLitePlanStore, RevisionConflict
from mediasense.plan import PlanWorkTool
from mediasense.plan.view import PlanView
from mediasense.runtime._view_files import (
    FORMAT,
    PROTOCOL,
    DiagnosticCleanup,
    configure_logging,
    open_owned,
    process_state,
    remove_connection,
    write_header,
)
from mediasense.runtime._view_lifecycle import Lifecycle, Policy, ViewUnavailable
from mediasense.runtime._view_server import ViewServer
from mediasense.runtime import plan_views
from test_plan_work import _create
from _plan_support import MockPrecheckReader, StableIdFactory


class Clock:
    value = 0

    def __call__(self):
        return self.value


@pytest.fixture
def prepared(tmp_path):
    tool = PlanWorkTool(
        tmp_path / "plan", MockPrecheckReader(), id_factory=StableIdFactory()
    )
    state = _create(tool)
    (tmp_path / "dataset.json").write_text(json.dumps({"dataset_ref": "dataset:test"}))
    (tmp_path / "precheck").mkdir()
    (tmp_path / "precheck" / "work.sqlite3").touch()
    value = {
        "workspace": str(tmp_path),
        "dataset_ref": "dataset:test",
        "work_ref": state["work_ref"],
        "revision": state["revision"],
    }
    clock = Clock()
    lifecycle = Lifecycle(clock=clock, factory=lambda r: PlanView(tool, r.work_ref))
    token = lifecycle.register(value)
    return tool, state, value, clock, lifecycle, token


def more_work(prepared, number):
    tool, _, value, _, lifecycle, _ = prepared
    state = tool.handle(
        {
            "action": "create",
            "result_ref": "precheck-result:hk-review-slice-002",
            "request_id": f"request:more-{number}",
        }
    )
    assert state["outcome"] == "ok"
    value = {**value, "work_ref": state["work_ref"], "revision": state["revision"]}
    return lifecycle.register(value), state["revision"]


def test_light_reads_do_not_load_or_write_and_clock_edges(prepared, monkeypatch):
    tool, state, _, clock, life, token = prepared
    database = tool.store.database_path
    before = database.read_bytes()
    with life.heavy(token, state["revision"]) as view:
        reader_ref = weakref.ref(view.renderer)
    clock.value = life.policy.cache_idle - 0.001
    assert not life.sweep()
    assert len(life.contexts) == 1
    clock.value = life.policy.cache_idle
    assert life.current(token)["idle_remaining_seconds"] == 255_600
    assert not life.sweep()
    assert not life.contexts and reader_ref() is None
    assert view.tool is None and view.analysis is None
    # Even invalid/huge payload columns must never be decoded by current.
    with sqlite3.connect(database) as db:
        db.execute(
            "UPDATE plan_works SET candidate_json='invalid json', organization_preferences_json='invalid'"
        )
    before = database.read_bytes()
    monkeypatch.setattr(
        SQLitePlanStore, "_initialize", lambda *a: pytest.fail("initialized")
    )
    for instant in (
        life.policy.cache_idle + 1,
        life.policy.service_idle - 0.001,
        life.policy.service_idle,
    ):
        clock.value = instant
        assert life.current(token)["revision"] == state["revision"]
    assert life.sweep() and life.reason == "idle_timeout"
    assert database.read_bytes() == before
    with pytest.raises(ViewUnavailable, match="retiring"):
        life.current(token)


def test_activity_renews_only_service_and_rejects_old_revision(prepared):
    _, state, _, clock, life, token = prepared
    with life.heavy(token, state["revision"]):
        pass
    clock.value = 100
    life.current(token, revision=state["revision"], activity=True)
    clock.value = life.policy.cache_idle
    life.sweep()
    assert not life.contexts
    assert life.status()["idle_seconds"] == life.policy.cache_idle - 100
    clock.value += 500
    with pytest.raises(RevisionConflict):
        life.current(token, revision="old", activity=True)
    assert life.last_use == 100
    clock.value = 100 + life.policy.service_idle
    assert life.sweep()


def test_two_pins_third_busy_waiter_limit_and_retry(prepared):
    _, state, _, _, life, token = prepared
    life.policy = replace(Policy(), wait_seconds=0.15, waiters=1)
    token2, rev2 = more_work(prepared, 2)
    token3, rev3 = more_work(prepared, 3)
    waiting = Event()

    def compete():
        waiting.set()
        with pytest.raises(ViewUnavailable, match="view_resource_busy"):
            with life.heavy(token3, rev3):
                pytest.fail("third context admitted")

    with ExitStack() as stack, ThreadPoolExecutor(1) as pool:
        stack.enter_context(life.heavy(token, state["revision"]))
        stack.enter_context(life.heavy(token2, rev2))
        future = pool.submit(compete)
        waiting.wait(1)
        until = time.monotonic() + 1
        while life.waiters != 1 and time.monotonic() < until:
            time.sleep(0.001)
        assert life.status()["contexts"] == 2
        start = time.monotonic()
        with pytest.raises(ViewUnavailable, match="view_resource_busy"):
            with life.heavy(token, state["revision"]):
                pass
        assert time.monotonic() - start < 0.1
        future.result()
    assert life.inflight == life.waiters == 0
    with life.heavy(token3, rev3):
        assert len(life.contexts) == 2


def test_twenty_works_release_whole_graph_and_keep_routes(prepared):
    _, state, value, clock, life, token = prepared
    refs = []
    for n in range(20):
        t, revision = (token, state["revision"]) if n == 0 else more_work(prepared, n)
        with life.heavy(t, revision) as view:
            refs.append(weakref.ref(view))
        del view
        clock.value += 1
        assert sum(ref() is not None for ref in refs) <= 2
    assert len(life.routes) == 20 and life.register(value) == token
    assert life.evictions == 18
    clock.value += life.policy.cache_idle
    life.sweep()
    assert all(ref() is None for ref in refs)
    assert all(not hasattr(route, "tool") for route in life.routes.values())


@pytest.mark.parametrize("error", [RuntimeError, BrokenPipeError, TimeoutError])
def test_inflight_blocks_idle_and_failure_releases(prepared, error):
    _, state, _, clock, life, token = prepared
    with pytest.raises(error):
        with life.heavy(token, state["revision"]):
            clock.value = life.policy.service_idle + 1
            assert not life.sweep() and life.inflight == 1
            raise error("injected")
    assert life.inflight == 0 and not life.contexts
    clock.value += life.policy.service_idle
    assert life.sweep()


def test_constructor_failure_and_version_change_dispose(prepared):
    tool, state, _, _, life, token = prepared

    def broken(route):
        raise RuntimeError("construction failed")

    life.factory = broken
    with pytest.raises(RuntimeError):
        with life.heavy(token, state["revision"]):
            pass
    assert not life.contexts and not life.active
    life.factory = lambda r: PlanView(tool, r.work_ref)
    with life.heavy(token, state["revision"]) as original:
        pass
    with sqlite3.connect(tool.store.database_path) as db:
        db.execute("UPDATE plan_works SET revision='work-revision:new'")
    with pytest.raises(RevisionConflict):
        with life.heavy(token, state["revision"]):
            pass
    with life.heavy(token, "work-revision:new") as new:
        assert new is not original and original.tool is None


def test_capacity_existing_route_and_physical_binding(prepared, tmp_path):
    _, _, value, _, life, token = prepared
    life.policy = replace(Policy(), routes=1)
    assert life.register(value) == token
    with pytest.raises(ViewUnavailable, match="view_capacity_exceeded"):
        more_work(prepared, 2)
    database = tmp_path / "plan" / "work-v3.sqlite3"
    database.rename(database.with_suffix(".old"))
    database.write_bytes(database.with_suffix(".old").read_bytes())
    with pytest.raises(ViewUnavailable, match="view_resource_unavailable"):
        life.current(token)


def test_admission_and_retirement_have_one_winner(prepared):
    _, _, _, clock, life, _ = prepared
    for _ in range(30):
        life.accepting, life.reason, life.last_use = True, None, 0
        clock.value = life.policy.service_idle
        barrier = Barrier(2)
        admitted = Event()
        release = Event()

        def request():
            barrier.wait()
            try:
                with life.request():
                    admitted.set()
                    release.wait(1)
                return "accepted"
            except ViewUnavailable:
                return "retiring"

        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(request)
            barrier.wait()
            retired = life.sweep()
            release.set()
            assert (future.result(), retired) in {
                ("retiring", True),
                ("accepted", False),
            }
        assert life.inflight == 0


@pytest.fixture
def http_server(prepared):
    server = ViewServer("test", lifecycle=prepared[4])
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    thread.join(2)
    server.server_close()


def http(server, path, *, data=None, headers=None):
    request = Request(server.origin + path, data=data, headers=headers or {})
    try:
        response = urlopen(request, timeout=2)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers, response.read()


def test_http_activity_security_and_invalid_reads_are_light(prepared, http_server):
    _, state, _, clock, life, token = prepared
    path = "/v/" + token
    clock.value = 80
    good = json.dumps({"revision": state["revision"]}).encode()
    headers = {"Origin": http_server.origin, "Content-Type": "application/json"}
    for body, extra, code in (
        (good, {}, 403),
        (b"{}", headers, 400),
        (good + b" " * 300, headers, 400),
        (b'{"revision":"old"}', headers, 409),
        (good, {**headers, "Origin": "https://foreign.invalid"}, 403),
    ):
        assert (
            http(http_server, path + "/activity", data=body, headers=extra)[0] == code
        )
    for query in (
        {"collection": "bad", "revision": state["revision"]},
        {"collection": "groups", "cursor": "bad", "revision": state["revision"]},
        {"collection": "groups"},
    ):
        assert http(http_server, path + "/page?" + urlencode(query))[0] == 400
    assert not life.contexts and life.last_use == 0
    assert http(http_server, path + "/activity", data=good, headers=headers)[0] == 200
    assert life.last_use == 80 and not life.contexts
    life.retire("explicit_stop")
    assert http(http_server, path + "/current")[0] == 503


def test_minimal_query_does_not_create_missing_store(tmp_path):
    path = tmp_path / "missing.sqlite3"
    with pytest.raises(sqlite3.OperationalError):
        SQLitePlanStore.read_binding(path, "plan-work:x")
    assert not path.exists()


def test_drain_is_bounded_and_reports_interrupted(prepared):
    _, _, _, _, life, _ = prepared
    life.policy = replace(Policy(), drain_seconds=0.02)
    with life.request():
        life.retire("explicit_stop")
        start = time.monotonic()
        assert life.drain() == 1
        assert time.monotonic() - start < 0.15
    assert life.drain() == 0


def test_retry_is_only_bind_and_shares_deadline(monkeypatch):
    opened = SimpleNamespace(
        workspace=Path("/synthetic"), manifest=SimpleNamespace(dataset_ref="dataset:x")
    )
    receipt = {
        "work_ref": "plan-work:x",
        "revision": "work-revision:x",
        "result_ref": "precheck-result:x",
    }
    deadlines, calls = [], []
    monkeypatch.setattr(
        plan_views,
        "ensure_host",
        lambda **kw: deadlines.append(kw["deadline"]) or {"instance": "test"},
    )

    def rpc(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            raise plan_views.Retiring()
        return {"status": "ready"}

    monkeypatch.setattr(plan_views, "rpc", rpc)
    assert plan_views.deliver(opened, receipt) == {"status": "ready"}
    assert len(calls) == 2 and deadlines[0] == deadlines[1]
    assert calls[0][0][2] == calls[1][0][2]
    assert calls[1][1]["timeout"] <= calls[0][1]["timeout"]
    calls.clear()

    def timeout(*args, **kwargs):
        calls.append(1)
        raise TimeoutError()

    monkeypatch.setattr(plan_views, "rpc", timeout)
    assert plan_views.deliver(opened, receipt)["status"] == "unavailable"
    assert len(calls) == 1


def header(root, instance="test"):
    return {
        "format": FORMAT,
        "protocol": PROTOCOL,
        "build": root.name,
        "uid": os.getuid(),
        "instance": instance,
        "pid": os.getpid(),
    }


def test_exit_proof_and_successor_connection(tmp_path, monkeypatch):
    root = tmp_path / ("a" * 64)
    root.mkdir()
    with open_owned(root / "process.lock", create=True) as owner:
        write_header(owner, header(root))
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        monkeypatch.setattr(plan_views, "runtime_directory", lambda **kw: root)
        monkeypatch.setattr(plan_views, "_info", lambda *a: None)
        assert process_state(root)[0] == "held"
        assert plan_views.control("status")["state"] == "unknown/unreachable"
        (root / "connection.json").write_text(json.dumps({"instance": "successor"}))
        remove_connection(root, "old")
        assert (root / "connection.json").exists()
    assert process_state(root)[0] == "released"
    assert plan_views.control("status")["state"] == "stopped"


def test_cleanup_safety_rotation_and_incremental_budget(tmp_path):
    root = tmp_path / ("a" * 64)
    root.mkdir()
    candidates = []
    for n in range(40):
        p = tmp_path / f"{n:064x}"
        p.mkdir()
        with open_owned(p / "process.lock", create=True) as stream:
            write_header(stream, header(p))
        os.utime(p / "process.lock", (1, 1))
        candidates.append(p)
    (candidates[0] / "unknown").write_text("preserve")
    (candidates[1] / "host.log").symlink_to(candidates[0] / "unknown")
    (candidates[2] / "process.lock").write_text('{"protocol":"old"}')
    with open_owned(candidates[3] / "process.lock") as active:
        fcntl.flock(active, fcntl.LOCK_EX | fcntl.LOCK_NB)
        cleanup = DiagnosticCleanup(root)
        cleanup.run()
        assert sum(p.exists() for p in candidates) >= 24
        for _ in range(5):
            cleanup.run()
        cleanup.close()
        assert all(p.exists() for p in candidates[:4])
        assert all(not p.exists() for p in candidates[4:])
    handler = configure_logging(root)
    try:
        logger = logging.getLogger("view-rotation-test")
        for _ in range(2500):
            logger.info("x" * 1000)
        assert (root / "host.log.1").exists()
        assert sum(p.stat().st_size for p in root.glob("host.log*")) < 2 * 1024 * 1024
    finally:
        logging.getLogger().removeHandler(handler)
        handler.close()


def test_real_reader_graph_reclaimed_and_exact_cold_reads(tmp_path):
    from test_runtime_host import _opened_host_with_plan_ready_result
    from mediasense.runtime._view_lifecycle import construct_view
    from mediasense.precheck.read import PrecheckReadTool

    host, dataset, result, *_ = _opened_host_with_plan_ready_result(tmp_path)
    tool = host._datasets[dataset].plan_work
    tool.view_delivery = None
    state = tool.handle(
        {"action": "create", "result_ref": result, "request_id": "request:real"}
    )
    scope = {
        "kind": "precheck_relation",
        "origin": result,
        "relation": "accounts_for",
        "direction": "outbound",
    }
    state = tool.handle(
        {
            "action": "update",
            "work_ref": state["work_ref"],
            "base_revision": state["revision"],
            "request_id": "request:real-update",
            "organization_content": {
                "kind": "draft",
                "result_ref": result,
                "scope": scope,
                "logical_root": "same-name",
                "groups": [
                    {
                        "relative_path": ["same-name"],
                        "members": scope,
                        "source_naming": {"default": "preserve_source_basename"},
                    }
                ],
                "other_outcomes": [],
                "decision_notes": [],
            },
        }
    )
    assert state["outcome"] == "ok"
    clock = Clock()
    refs = []

    def factory(route):
        view = construct_view(route)
        reader = next(
            c.cell_contents
            for c in view.tool.precheck_read.read.__closure__
            if isinstance(c.cell_contents, PrecheckReadTool)
        )
        refs.append((weakref.ref(view), weakref.ref(reader)))
        return view

    life = Lifecycle(clock=clock, factory=factory)
    token = life.register(
        {
            "workspace": str(tmp_path / "workspace"),
            "dataset_ref": dataset,
            "work_ref": state["work_ref"],
            "revision": state["revision"],
        }
    )
    before = tool.store.database_path.read_bytes()
    with life.heavy(token, state["revision"]) as view:
        page = view.page(state["revision"], "groups")
        members = view.page(state["revision"], "group:0")
        ref = page["items"][0]["samples"][0]["evidence_ref"]
        image = view.asset(state["revision"], ref)
        assert view.analysis and view.members
    del view
    clock.value = life.policy.cache_idle
    life.sweep()
    assert all(r() is None for pair in refs for r in pair)
    assert life.current(token)["revision"] == state["revision"] and not life.contexts
    with life.heavy(token, state["revision"]) as view:
        assert view.page(state["revision"], "groups") == page
        assert view.page(state["revision"], "group:0") == members
        assert view.asset(state["revision"], ref) == image
    assert tool.store.database_path.read_bytes() == before


def test_distinct_datasets_and_identical_work_names_never_share_routes(tmp_path):
    from test_runtime_host import _opened_host_with_plan_ready_result

    life = Lifecycle()
    entries = []
    for name in ("a", "b"):
        root = tmp_path / name
        root.mkdir()
        host, dataset, result, *_ = _opened_host_with_plan_ready_result(root)
        tool = host._datasets[dataset].plan_work
        tool.view_delivery = None
        state = tool.handle(
            {"action": "create", "result_ref": result, "request_id": "request:same"}
        )
        value = {
            "workspace": str(root / "workspace"),
            "dataset_ref": dataset,
            "work_ref": state["work_ref"],
            "revision": state["revision"],
        }
        token = life.register(value)
        with life.heavy(token, state["revision"]) as view:
            assert view.overview(state["revision"])["result_ref"] == result
        entries.append(token)
    assert len(set(entries)) == 2
    assert life.routes[entries[0]].dataset_ref != life.routes[entries[1]].dataset_ref


def test_failure_response_stays_pinned_until_sent(prepared):
    _, state, _, clock, life, token = prepared

    def send_failure(error):
        assert isinstance(error, RuntimeError)
        assert life.inflight == 1 and token in life.active
        clock.value = 900
        assert not life.sweep()

    with life.heavy(token, state["revision"], on_error=send_failure):
        raise RuntimeError("projection defect")
    assert life.inflight == 0 and not life.contexts


def test_real_stop_interrupts_a_hung_read_and_releases_process_lock(
    prepared, tmp_path, monkeypatch
):
    import subprocess
    import sys

    tool, state, value, _, _, _ = prepared
    root = tmp_path / "runtime" / ("b" * 64)
    root.mkdir(parents=True)
    script = """
import sys,time
from mediasense.runtime import _view_server as server
from mediasense.runtime._view_lifecycle import Lifecycle
Original=server.ViewServer
class Slow:
 def overview(self, revision): time.sleep(30)
 def close(self): pass
server.ViewServer=lambda build,root: Original(build, root=root, lifecycle=Lifecycle(factory=lambda route:Slow()))
server.main()
"""
    child = subprocess.Popen([sys.executable, "-c", script, str(root), root.name])
    monkeypatch.setattr(plan_views, "runtime_directory", lambda **kw: root)
    monkeypatch.setattr(plan_views, "build_identity", lambda: root.name)
    try:
        deadline = time.monotonic() + 10
        info = None
        while time.monotonic() < deadline and info is None:
            info = plan_views._info(root)
            time.sleep(0.01)
        assert info is not None
        with ThreadPoolExecutor(1) as pool:

            def read():
                try:
                    plan_views.rpc(info, "bind", value, timeout=10)
                except (OSError, Exception) as error:
                    return type(error).__name__
                pytest.fail("interrupted read claimed success")

            future = pool.submit(read)
            while plan_views.control("status")["inflight"] == 0:
                assert time.monotonic() < deadline
                time.sleep(0.01)
            started = time.monotonic()
            stopped = plan_views.control("stop")
            elapsed = time.monotonic() - started
            assert stopped["state"] == "stopped" and stopped["exit_verified"]
            assert stopped["interrupted_requests"] == 1
            assert 4.8 <= elapsed < 7.5
            assert future.result(timeout=2)
        assert child.wait(timeout=2) == 0
        assert process_state(root)[0] == "released"
        assert not (root / "connection.json").exists()
        assert tool.store.snapshot(state["work_ref"]).revision == state["revision"]
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=3)


def test_production_route_capacity_and_saved_receipt_are_separate(prepared):
    tool, state, value, _, life, first = prepared
    server = ViewServer("test", lifecycle=life)
    try:
        for n in range(1, 256):
            more_work(prepared, n)
        assert len(life.routes) == 256
        saved = _create(tool, request_id="request:beyond-capacity")
        assert saved["outcome"] == "ok"
        result = server.bind(
            {**value, "work_ref": saved["work_ref"], "revision": saved["revision"]}
        )
        assert result["status"] == "unavailable"
        assert result["problems"][0]["code"] == "view_capacity_exceeded"
        assert result["current_uri"] is None
        assert life.register(value) == first
        assert tool.store.snapshot(saved["work_ref"]).revision == saved["revision"]
    finally:
        server.server_close()


def test_wall_clock_changes_do_not_affect_monotonic_idle(prepared, monkeypatch):
    _, _, _, clock, life, _ = prepared
    clock.value = life.policy.service_idle - 1
    for wall in (-1000000000, 100000000000):
        monkeypatch.setattr(time, "time", lambda: wall)
        assert not life.sweep()
        assert life.status()["idle_remaining_seconds"] == 1
    # Models resuming scheduling after a sleep, without requiring a system sleep.
    clock.value += 5000
    assert life.sweep()


@pytest.mark.parametrize(
    "failure", [TimeoutError, ConnectionResetError, BrokenPipeError]
)
def test_ambiguous_transport_failure_does_not_repeat_expensive_bind(
    monkeypatch, failure
):
    calls = []
    monkeypatch.setattr(plan_views, "ensure_host", lambda **kw: {"instance": "test"})

    def fail(*args, **kwargs):
        calls.append(1)
        raise failure("outcome unknown")

    monkeypatch.setattr(plan_views, "rpc", fail)
    opened = SimpleNamespace(
        workspace=Path("/synthetic"), manifest=SimpleNamespace(dataset_ref="dataset:x")
    )
    receipt = {
        "work_ref": "plan-work:x",
        "revision": "work-revision:x",
        "result_ref": "precheck-result:x",
    }
    assert plan_views.deliver(opened, receipt)["status"] == "unavailable"
    assert len(calls) == 1


def test_http_busy_is_retryable_and_current_stays_light(prepared, http_server):
    _, state, _, clock, life, token = prepared
    life.policy = replace(Policy(), wait_seconds=0.02)
    path = "/v/" + token
    with life.heavy(token, state["revision"]):
        clock.value = 70
        status, headers, body = http(
            http_server,
            path
            + "/page?"
            + urlencode({"revision": state["revision"], "collection": "groups"}),
        )
        assert status == 503 and headers["Retry-After"] == "1"
        assert json.loads(body)["error"] == "view_resource_busy"
        assert life.last_failure == "view_resource_busy"
        assert http(http_server, path + "/current")[0] == 200
        assert life.last_use == 0 and life.inflight == 1


def test_failed_factory_traceback_cannot_retain_a_third_reader(prepared):
    _, state, _, _, life, token = prepared
    refs = []

    class Reader:
        pass

    def fail(route):
        reader = Reader()
        reader.payload = bytearray(1024 * 1024)
        refs.append(weakref.ref(reader))
        raise RuntimeError("factory defect")

    life.factory = fail
    with pytest.raises(RuntimeError) as retained_error:
        with life.heavy(token, state["revision"]):
            pass
    assert retained_error.value.__traceback__ is not None
    assert refs[0]() is None and not life.contexts and life.inflight == 0
