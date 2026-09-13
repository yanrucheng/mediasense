"""OS ownership and atomic replay across independent Plan processes."""

from multiprocessing import get_context

import pytest

from mediasense.plan import PlanWorkTool
from mediasense.plan._update_execution import UpdateExecution
from mediasense.runtime.resources import schema_path
from _plan_support import MockPrecheckReader
from test_plan_update_mcp import update_request
from test_plan_update_execution import update_count
from test_plan_work import _create, _tool


def process_update(plan_store, request, started, release, waiting, output, crash):
    import os

    class Reader(MockPrecheckReader):
        def read(self, value):
            if value["action"] == "resolve" and not started.is_set():
                started.set()
                assert release.wait(15), "test did not release the child Read"
            return super().read(value)

    execution = UpdateExecution(
        observe=lambda event: waiting.set() if event["phase"] == "waiting" else None
    )
    tool = PlanWorkTool(
        plan_store, Reader(), frozen_plan_schema=schema_path("frozen-plan.schema.json")
    )
    if crash == "inside_transaction":
        # UPDATE has happened in this connection; the receipt and COMMIT have not.
        def die(*_args):
            os._exit(72)

        tool.store._record_request = die
    result = tool.handle(request, execution=execution)
    if crash == "after_commit":
        os._exit(73)
    output.send(result)
    output.close()


def launch(context, tool, request, *, crash=None):
    incoming, outgoing = context.Pipe(duplex=False)
    started, release, waiting = (context.Event() for _ in range(3))
    process = context.Process(
        target=process_update,
        args=(tool.plan_store, request, started, release, waiting, outgoing, crash),
    )
    process.start()
    outgoing.close()
    return process, incoming, started, release, waiting


def cleanup(children):
    for process, incoming, _started, release, _waiting in children:
        # A killed process may have died while holding the Event's semaphore.
        # Never touch its shared synchronization primitives after termination.
        if process.is_alive():
            release.set()
        process.join(5)
        if process.is_alive():
            # These are exclusively this test's synthetic child processes.
            process.terminate()
            process.join(5)
        incoming.close()
        process.close()


@pytest.mark.parametrize("notes_waiter", [False, True])
@pytest.mark.parametrize("owner_exits", [False, True])
def test_processes_serialize_and_dead_owner_does_not_leave_a_busy_lock(
    tmp_path, owner_exits, notes_waiter
):
    tool = _tool(tmp_path)
    request = update_request(_create(tool))
    context = get_context("spawn")
    children = []
    try:
        first = launch(context, tool, request)
        children.append(first)
        assert first[2].wait(10)
        following = dict(request)
        if notes_waiter:
            following.pop("organization_content")
            following.update(
                working_notes="waiting notes", request_id="request:waiting-notes"
            )
        second = launch(context, tool, following)
        children.append(second)
        assert second[4].wait(10)
        assert not second[2].is_set()
        assert update_count(tool) == 0
        if owner_exits:
            first[0].terminate()
            first[0].join(5)
            assert first[0].exitcode is not None
        if not owner_exits:
            first[3].set()
        second[3].set()
        assert second[1].poll(10)
        result = second[1].recv()
        if notes_waiter and not owner_exits:
            assert result["error"]["code"] == "revision_conflict"
        else:
            assert result["outcome"] == "ok"
        assert second[2].is_set() == (owner_exits and not notes_waiter)
        if not owner_exits:
            assert first[1].poll(5)
            first_result = first[1].recv()
            assert first_result["outcome"] == "ok"
            if not notes_waiter:
                assert receipt(first_result) == receipt(result)
        if not notes_waiter or owner_exits:
            assert receipt(tool.handle(following)) == receipt(result)
        assert update_count(tool) == 1
    finally:
        cleanup(children)


@pytest.mark.parametrize("notes_only", [False, True])
@pytest.mark.parametrize("crash", ["inside_transaction", "after_commit"])
def test_process_crash_leaves_an_atomic_recoverable_outcome(
    tmp_path, crash, notes_only
):
    tool = _tool(tmp_path)
    created = _create(tool)
    request = update_request(created, organization_preferences={})
    if notes_only:
        request.pop("organization_content")
        request["working_notes"] = "process notes"
    before = tool.store.snapshot(created["work_ref"])
    child = launch(get_context("spawn"), tool, request, crash=crash)
    try:
        if not notes_only:
            assert child[2].wait(10)
        child[3].set()
        child[0].join(10)
        assert child[0].exitcode == (72 if crash == "inside_transaction" else 73)
        after = tool.store.snapshot(created["work_ref"])
        if crash == "inside_transaction":
            assert after == before
            assert update_count(tool) == 0
        else:
            assert after.revision != before.revision
            assert after.organization_preferences == {}
            assert after.candidate == request.get("organization_content")
            if notes_only:
                assert after.working_notes == "process notes"
            assert update_count(tool) == 1
        recovered = tool.handle(request)
        assert recovered["outcome"] == "ok"
        assert update_count(tool) == 1
        if crash == "after_commit":
            assert recovered["revision"] == after.revision
    finally:
        cleanup([child])


def receipt(value):
    return {k: v for k, v in value.items() if k != "view"}
