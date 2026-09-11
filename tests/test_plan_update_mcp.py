"""Cancellation and lost-response recovery through the actual MCP/Host path."""

from contextlib import asynccontextmanager
import asyncio
import logging
from threading import Event, Lock

import anyio

from mcp import ClientSession
from mcp.shared.exceptions import MCPError
from mcp.server.session import ServerSession
import pytest

from mediasense.runtime.composition import DatasetRuntime
from mediasense.runtime.host import RuntimeHost
from mediasense.runtime.mcp_host import create_mcp_server
from _plan_support import MockPrecheckReader, valid_candidate
from test_plan_work import _create, _tool


class GatedReader(MockPrecheckReader):
    def __init__(self):
        super().__init__()
        self.started, self.release = Event(), Event()

    def read(self, request):
        if request["action"] == "resolve" and not self.started.is_set():
            self.started.set()
            assert self.release.wait(10), "test did not release the Read"
        return super().read(request)


class TrackingHost(RuntimeHost):
    def __init__(self, tool):
        runtime = DatasetRuntime.__new__(DatasetRuntime)
        runtime.plan_work = tool
        self._datasets = {"dataset:test": runtime}
        self._lock = Lock()
        self.finished = Event()
        self.responses = []

    def call_tool(self, *args, **kwargs):
        try:
            response = super().call_tool(*args, **kwargs)
            self.responses.append(response)
            return response
        finally:
            self.finished.set()


@asynccontextmanager
async def connection(host, *, streams=None):
    outgoing, incoming = anyio.create_memory_object_stream(10)
    client_outgoing, server_incoming = anyio.create_memory_object_stream(10)
    cancelled = anyio.Event()
    server = create_mcp_server(host)
    if streams is not None:
        streams["client_output"] = client_outgoing

    async def observe(context, call_next):
        if context.method == "notifications/cancelled":
            cancelled.set()
        return await call_next(context)

    server.middleware.append(observe)
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(
            server.run,
            server_incoming,
            outgoing,
            server.create_initialization_options(),
        )
        async with ClientSession(incoming, client_outgoing) as session:
            await session.initialize()
            yield session, cancelled, tasks
        tasks.cancel_scope.cancel()


def update_request(created, **values):
    return {
        "action": "update",
        "work_ref": created["work_ref"],
        "base_revision": created["revision"],
        "candidate_content": valid_candidate(),
        "request_id": "request:update-mcp",
        **values,
    }


async def call_update(session, request, **kwargs):
    return await session.call_tool(
        "mediasense.plan.work",
        {"dataset_ref": "dataset:test", "request": request},
        **kwargs,
    )


def test_mcp_cancel_stops_update_before_commit(tmp_path):
    reader = GatedReader()
    tool = _tool(tmp_path, reader)
    created = _create(tool)
    request = update_request(created)
    host = TrackingHost(tool)

    async def scenario():
        async with connection(host) as (session, cancelled, tasks):
            scopes = []
            caller_done = anyio.Event()

            async def submit():
                with anyio.CancelScope() as scope:
                    scopes.append(scope)
                    await call_update(session, request)
                caller_done.set()

            tasks.start_soon(submit)
            try:
                assert await anyio.to_thread.run_sync(reader.started.wait, 5)
                scopes[0].cancel()
                with anyio.fail_after(5):
                    await cancelled.wait()
                    await caller_done.wait()
            finally:
                reader.release.set()
            assert await anyio.to_thread.run_sync(host.finished.wait, 5)

    anyio.run(scenario)
    snapshot = tool.store.snapshot(created["work_ref"])
    assert snapshot.revision == created["revision"]
    assert snapshot.candidate is None
    assert len([c for c in reader.calls if c["action"] == "resolve"]) == 1


def test_mcp_timeout_delivers_cancel_and_stops_update(tmp_path):
    reader = GatedReader()
    tool = _tool(tmp_path, reader)
    created = _create(tool)
    host = TrackingHost(tool)

    async def scenario():
        async with connection(host) as (session, cancelled, tasks):
            done = anyio.Event()

            async def submit():
                with pytest.raises(MCPError, match="timed out"):
                    await call_update(
                        session, update_request(created), read_timeout_seconds=0.1
                    )
                done.set()

            tasks.start_soon(submit)
            try:
                with anyio.fail_after(5):
                    await done.wait()
                    await cancelled.wait()
            finally:
                reader.release.set()
            # A short timeout may win before the worker even starts. Leaving the
            # connection also joins any started, shielded synchronous handler.

    anyio.run(scenario)
    assert tool.store.snapshot(created["work_ref"]).candidate is None
    assert all(value["error"]["code"] == "operation_failed" for value in host.responses)


def test_disconnect_cancels_worker_before_commit(tmp_path):
    class CancellationTapReader(GatedReader):
        def __init__(self):
            super().__init__()
            self.saw_scope_cancellation = Event()

        def read(self, request):
            if request["action"] == "resolve" and not self.started.is_set():
                self.started.set()
                for _ in range(1000):
                    if self.release.wait(0.01):
                        break
                    try:
                        anyio.from_thread.check_cancelled()
                    except asyncio.CancelledError:
                        # Observe only. The production execution checkpoint,
                        # after this Read returns, must actually stop the update.
                        self.saw_scope_cancellation.set()
                else:
                    raise AssertionError("test did not release the Read")
            return MockPrecheckReader.read(self, request)

    reader = CancellationTapReader()
    tool = _tool(tmp_path, reader)
    created = _create(tool)
    host = TrackingHost(tool)

    async def scenario():
        streams = {}
        async with connection(host, streams=streams) as (session, _cancelled, tasks):

            async def submit():
                with pytest.raises(MCPError):
                    await call_update(session, update_request(created))

            tasks.start_soon(submit)
            try:
                assert await anyio.to_thread.run_sync(reader.started.wait, 5)
                await streams["client_output"].aclose()
                assert await anyio.to_thread.run_sync(
                    reader.saw_scope_cancellation.wait, 5
                )
            finally:
                reader.release.set()
            assert await anyio.to_thread.run_sync(host.finished.wait, 5)

    anyio.run(scenario)
    assert tool.store.snapshot(created["work_ref"]).candidate is None


def test_progress_and_diagnostics_are_correlated_without_candidate_payload(
    tmp_path, caplog
):
    caplog.set_level(logging.INFO, logger="mediasense")
    tool = _tool(tmp_path)
    created = _create(tool)
    host = TrackingHost(tool)
    observed = []

    async def progress(value, total, message):
        observed.append((value, total, message))

    async def scenario():
        async with connection(host) as (session, _cancelled, _tasks):
            result = await call_update(
                session,
                update_request(
                    created,
                    organization_preferences={
                        "private_test_note": "not-for-diagnostic"
                    },
                ),
                progress_callback=progress,
            )
            assert result.structured_content["outcome"] == "ok"
            with anyio.fail_after(5):
                while not any("committed" in (row[2] or "") for row in observed):
                    await anyio.sleep(0)

    anyio.run(scenario)
    assert [row[0] for row in observed] == sorted(row[0] for row in observed)
    assert all(row[1] is None for row in observed)
    assert observed[-1][0] > 0
    assert "rpc_id=" in caplog.text
    assert "committing" in caplog.text and "committed" in caplog.text
    assert "request:update-mcp" in caplog.text
    assert "not-for-diagnostic" not in caplog.text + str(observed)


@pytest.mark.parametrize("failure", ["closed", "stalled"])
def test_progress_transport_does_not_prevent_commit(tmp_path, monkeypatch, failure):
    attempts = []

    async def broken_progress(*_args, **_kwargs):
        attempts.append(failure)
        if failure == "closed":
            raise anyio.ClosedResourceError
        await anyio.sleep_forever()

    monkeypatch.setattr(ServerSession, "report_progress", broken_progress)
    tool = _tool(tmp_path)
    created = _create(tool)
    host = TrackingHost(tool)

    async def progress(*_args):
        pass

    async def scenario():
        async with connection(host) as (session, _cancelled, _tasks):
            result = await call_update(
                session,
                update_request(created),
                progress_callback=progress,
                read_timeout_seconds=10,
            )
            assert result.structured_content["outcome"] == "ok"

    anyio.run(scenario)
    assert attempts == [failure]


def test_wait_timeout_without_cancel_may_commit_and_replay(tmp_path):
    reader = GatedReader()
    tool = _tool(tmp_path, reader)
    created = _create(tool)
    request = update_request(created)
    host = TrackingHost(tool)

    async def scenario():
        async with connection(host) as (session, cancelled, tasks):
            result, done = [], anyio.Event()

            async def submit():
                result.append(await call_update(session, request))
                done.set()

            tasks.start_soon(submit)
            try:
                assert await anyio.to_thread.run_sync(reader.started.wait, 5)
                # Only this wait times out. The RPC receives no cancellation.
                with anyio.move_on_after(0.01) as waiting:
                    await done.wait()
                assert waiting.cancel_called and not cancelled.is_set()
            finally:
                reader.release.set()
            with anyio.fail_after(5):
                await done.wait()
            reads = len(reader.calls)
            replay = await call_update(session, request)
            assert replay.structured_content == result[0].structured_content
            assert replay.structured_content["outcome"] == "ok"
            assert len(reader.calls) == reads

    anyio.run(scenario)


def test_mcp_cancel_after_commit_gate_recovers_the_committed_result(
    tmp_path, monkeypatch
):
    tool = _tool(tmp_path)
    created = _create(tool)
    request = update_request(created)
    entered, release = Event(), Event()
    record = tool.store._record_request

    def delayed_receipt(*args):
        entered.set()
        assert release.wait(10), "test did not release the transaction"
        return record(*args)

    monkeypatch.setattr(tool.store, "_record_request", delayed_receipt)
    host = TrackingHost(tool)

    async def scenario():
        async with connection(host) as (session, cancelled, tasks):
            scopes = []
            done = anyio.Event()

            async def submit():
                with anyio.CancelScope() as scope:
                    scopes.append(scope)
                    await call_update(session, request)
                done.set()

            tasks.start_soon(submit)
            try:
                assert await anyio.to_thread.run_sync(entered.wait, 5)
                scopes[0].cancel()
                with anyio.fail_after(5):
                    await cancelled.wait()
                    await done.wait()
            finally:
                release.set()
            assert await anyio.to_thread.run_sync(host.finished.wait, 5)
            committed = host.responses[-1]
            assert committed["outcome"] == "ok"
            replay = await call_update(session, request)
            assert replay.structured_content == committed
            assert (
                tool.store.snapshot(created["work_ref"]).revision
                == committed["revision"]
            )

    anyio.run(scenario)
