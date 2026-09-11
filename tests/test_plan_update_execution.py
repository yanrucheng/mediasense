"""Update admission, cancellation/commit races, and truthful request recovery."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import sqlite3
from threading import Event, Lock

import pytest

from mediasense.plan import PlanWorkTool
import mediasense.plan.work as working
from mediasense.plan._update_execution import UpdateExecution
from mediasense.runtime.resources import schema_path
from test_plan_update_mcp import GatedReader, update_request
from test_plan_work import _create, _tool


def update_count(tool):
    with sqlite3.connect(tool.store.database_path) as connection:
        return connection.execute(
            "SELECT count(*) FROM plan_requests WHERE action='update'"
        ).fetchone()[0]


def waiting_execution():
    waiting = Event()
    execution = UpdateExecution(
        observe=lambda event: waiting.set() if event["phase"] == "waiting" else None
    )
    return execution, waiting


def count_analysis(monkeypatch):
    original = working.analyze_candidate
    guard = Lock()
    counts = {"calls": 0, "active": 0, "peak": 0}

    def analyze(*args, **kwargs):
        with guard:
            counts["calls"] += 1
            counts["active"] += 1
            counts["peak"] = max(counts["peak"], counts["active"])
        try:
            return original(*args, **kwargs)
        finally:
            with guard:
                counts["active"] -= 1

    monkeypatch.setattr(working, "analyze_candidate", analyze)
    return counts


@pytest.mark.parametrize("retry", ["identical", "different_payload", "different_id"])
def test_concurrent_updates_do_not_repeat_validation(tmp_path, monkeypatch, retry):
    reader = GatedReader()
    tool = _tool(tmp_path, reader)
    created = _create(tool)
    original = update_request(created)
    following = deepcopy(original)
    if retry == "different_payload":
        following["organization_preferences"] = {"maximum_depth": 4}
    elif retry == "different_id":
        following["request_id"] = "request:second-update"
    # A second Tool instance shares neither a Python lock nor the Reader object.
    peer = PlanWorkTool(
        tool.plan_store,
        reader,
        frozen_plan_schema=schema_path("frozen-plan.schema.json"),
    )
    execution, waiting = waiting_execution()
    counts = count_analysis(monkeypatch)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(tool.handle, original)
        try:
            assert reader.started.wait(5)
            second = pool.submit(peer.handle, following, execution=execution)
            assert waiting.wait(5)
            observed = peer.handle(
                {
                    "action": "inspect",
                    "work_ref": created["work_ref"],
                    "sections": ["overview", "preferences"],
                }
            )
            assert observed["revision"] == created["revision"]
            assert not first.done() and not second.done()
        finally:
            reader.release.set()
        result, subsequent = first.result(5), second.result(5)
    assert result["outcome"] == "ok"
    if retry == "identical":
        assert subsequent == result
    else:
        assert subsequent["error"]["code"] == (
            "idempotency_conflict"
            if retry == "different_payload"
            else "revision_conflict"
        )
    assert counts == {"calls": 1, "active": 0, "peak": 1}
    assert update_count(tool) == 1


def test_waiter_cancellation_does_not_cancel_owner(tmp_path):
    reader = GatedReader()
    tool = _tool(tmp_path, reader)
    request = update_request(_create(tool))
    execution, waiting = waiting_execution()
    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(tool.handle, request)
        try:
            assert reader.started.wait(5)
            waiter = pool.submit(tool.handle, request, execution=execution)
            assert waiting.wait(5)
            execution.cancel()
            assert waiter.result(5)["error"]["code"] == "operation_failed"
            assert not owner.done()
            assert update_count(tool) == 0
        finally:
            reader.release.set()
        assert owner.result(5)["outcome"] == "ok"
    assert tool.handle(request)["outcome"] == "ok"
    assert update_count(tool) == 1


def test_cancelled_owner_releases_waiter_and_request_payload_is_frozen(tmp_path):
    reader = GatedReader()
    tool = _tool(tmp_path, reader)
    created = _create(tool)
    owner_execution = UpdateExecution()
    waiting_control, waiting = waiting_execution()
    request = update_request(
        created,
        request_id="request:queued-new-update",
        organization_preferences={"label": "before"},
    )
    expected = deepcopy(request)
    with ThreadPoolExecutor(2) as pool:
        owner = pool.submit(
            tool.handle, update_request(created), execution=owner_execution
        )
        try:
            assert reader.started.wait(5)
            waiter = pool.submit(tool.handle, request, execution=waiting_control)
            assert waiting.wait(5)
            request["organization_preferences"]["label"] = "after"
            owner_execution.cancel()
        finally:
            reader.release.set()
        assert owner.result(5)["error"]["code"] == "operation_failed"
        result = waiter.result(5)
    assert result["outcome"] == "ok"
    assert tool.store.snapshot(created["work_ref"]).organization_preferences == {
        "label": "before"
    }
    assert tool.handle(expected) == result
    assert tool.handle(request)["error"]["code"] == "idempotency_conflict"
    assert update_count(tool) == 1


def test_other_work_is_not_blocked_by_validation(tmp_path):
    reader = GatedReader()
    tool = _tool(tmp_path, reader)
    first_work = _create(tool)
    second_work = _create(tool, request_id="request:other-work")
    with ThreadPoolExecutor(1) as pool:
        first = pool.submit(tool.handle, update_request(first_work))
        try:
            assert reader.started.wait(5)
            second = tool.handle(
                update_request(second_work, request_id="request:other-update")
            )
            assert second["outcome"] == "ok"
            assert not first.done()
        finally:
            reader.release.set()
        assert first.result(5)["outcome"] == "ok"
    assert update_count(tool) == 2


@pytest.mark.parametrize(
    "stage",
    [
        "schema",
        "scope",
        "groups",
        "representatives",
        "decision_notes",
        "destinations",
        "identity",
    ],
)
def test_cancellation_at_validation_boundaries_never_publishes(tmp_path, stage):
    tool = _tool(tmp_path)
    created = _create(tool)
    before = tool.store.snapshot(created["work_ref"])
    phases = []

    def observe(event):
        phases.append(event["phase"])
        if event["phase"] == stage:
            execution.cancel()

    execution = UpdateExecution(observe=observe)
    request = update_request(created, organization_preferences={})
    result = tool.handle(request, execution=execution)
    assert result["error"]["code"] == "operation_failed"
    assert phases[-1] == "cancelled" and "committing" not in phases
    assert tool.store.snapshot(created["work_ref"]) == before
    assert update_count(tool) == 0
    assert tool.handle(request)["outcome"] == "ok"


def test_cancellation_at_commit_gate_rolls_back_without_a_receipt(
    tmp_path, monkeypatch
):
    tool = _tool(tmp_path)
    created = _create(tool)
    before = tool.store.snapshot(created["work_ref"])
    execution = UpdateExecution()
    update = tool.store.update

    def cancel_at_gate(**kwargs):
        gate = kwargs["before_write"]

        def before_write():
            execution.cancel()
            gate()

        return update(**{**kwargs, "before_write": before_write})

    monkeypatch.setattr(tool.store, "update", cancel_at_gate)
    result = tool.handle(update_request(created), execution=execution)
    assert result["error"]["code"] == "operation_failed"
    assert tool.store.snapshot(created["work_ref"]) == before
    assert update_count(tool) == 0


def test_commit_winning_cancellation_remains_replayable(tmp_path, monkeypatch):
    tool = _tool(tmp_path)
    created = _create(tool)
    request = update_request(created, organization_preferences={})
    phases = []
    execution = UpdateExecution(observe=lambda event: phases.append(event["phase"]))
    record = tool.store._record_request

    def cancelled_after_write(*args):
        execution.cancel()
        return record(*args)

    monkeypatch.setattr(tool.store, "_record_request", cancelled_after_write)
    result = tool.handle(request, execution=execution)
    assert result["outcome"] == "ok"
    assert phases[-1] == "committed" and "cancelled" not in phases
    snapshot = tool.store.snapshot(created["work_ref"])
    assert snapshot.revision == result["revision"]
    assert snapshot.organization_preferences == {}
    assert snapshot.candidate == request["candidate_content"]
    assert tool.handle(request) == result
    assert update_count(tool) == 1


def test_failure_inside_commit_rolls_back_and_does_not_hold_ownership(
    tmp_path, monkeypatch
):
    tool = _tool(tmp_path)
    created = _create(tool)
    before = tool.store.snapshot(created["work_ref"])
    request = update_request(created, organization_preferences={})

    def fail(*_args):
        raise RuntimeError("injected transaction failure")

    with monkeypatch.context() as patch:
        patch.setattr(tool.store, "_record_request", fail)
        with pytest.raises(RuntimeError, match="injected transaction failure"):
            tool.handle(request)
    assert tool.store.snapshot(created["work_ref"]) == before
    assert update_count(tool) == 0
    assert tool.handle(request)["outcome"] == "ok"
