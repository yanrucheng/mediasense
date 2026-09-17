"""Apply control acceptance must reach its outcome through real Host workers."""

from contextlib import contextmanager
from datetime import datetime, timezone
import os
import subprocess
import sys
import threading
from time import monotonic, sleep

import pytest

from mediasense.runtime.host import RuntimeHost
from test_apply_preparation import _fixture, _plan


def _hosts(tmp_path, monkeypatch):
    source, destination, workspace, _files, reader = _fixture(tmp_path)
    config = tmp_path / "config"
    config.mkdir()
    (config / "config.toml").write_text(
        "[embedding]\nenabled=false\n[sensitivity]\nenabled=false\n"
    )
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(config))
    monkeypatch.setenv("MEDIASENSE_DATA_HOME", str(tmp_path / "data"))
    hosts = (RuntimeHost(), RuntimeHost())
    for host in hosts:
        opened = host.open_dataset(str(source), str(workspace))
        assert opened["outcome"] == "ok", opened
    dataset = opened["dataset_ref"]
    runtime = hosts[0]._datasets[dataset]
    runtime.apply_run.precheck_read = reader
    prepared = hosts[0].call_tool(
        "mediasense.apply.run",
        dataset_ref=dataset,
        request={
            "action": "prepare",
            "request_id": "request:host-controls",
            "forward": {
                "frozen_plan": _plan(),
                "effect": "move_originals",
                "current_source_roots": [
                    {"source_root_ref": "source-root:test", "current_root": str(source)}
                ],
                "destination_parent": str(destination),
            },
        },
    )
    assert prepared["outcome"] == "ok", prepared
    run_ref = prepared["run_ref"]

    def call(host, action, **fields):
        return host.call_tool(
            "mediasense.apply.run",
            dataset_ref=dataset,
            request={"action": action, "run_ref": run_ref, **fields},
        )

    status = call(hosts[0], "status")
    assert status["state"] == "ready_for_authorization"
    execute = {
        "action": "execute",
        "run_ref": run_ref,
        "request_id": "request:host-execute",
        "prepared_revision": status["prepared_revision"],
        "prepared_content_identity": status["prepared_content_identity"],
    }
    return hosts, dataset, runtime, call, execute, source, destination, workspace


def _wait_state(call, host, expected):
    deadline = monotonic() + 10
    while monotonic() < deadline:
        status = call(host, "status")
        if status["state"] == expected:
            return status
        assert status["state"] != "failed", status
        sleep(0.005)
    pytest.fail(f"Host did not reach {expected}: {status}")


def _start(host, dataset, execute):
    result = host.call_tool(
        "mediasense.apply.run",
        dataset_ref=dataset,
        request=execute,
        authority={
            "principal_ref": "human:isolated-host-test",
            "confirmed_content_identity": execute["prepared_content_identity"],
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert result["outcome"] == "accepted", result


@contextmanager
def _hold_first_effect(runtime):
    reached, release = threading.Event(), threading.Event()

    def fault(point, item):
        if point == "after_effect_before_record" and item == "source-item:a":
            reached.set()
            assert release.wait(10), "test did not release the first effect"

    runtime.apply_run.executor.fault_hook = fault
    try:
        yield reached, release
    finally:
        release.set()
        with runtime._worker_lock:
            workers = list(runtime._workers.values())
        for worker in workers:
            worker.join(10)
            assert not worker.is_alive()


def _pause_after_first(host, dataset, runtime, call, execute, reached, release):
    _start(host, dataset, execute)
    assert reached.wait(10)
    assert call(host, "pause")["target_state"] == "paused"
    with runtime._worker_lock:
        worker = runtime._workers[f"apply:{execute['run_ref']}"]
    release.set()
    worker.join(10)
    assert not worker.is_alive()
    assert call(host, "status")["state"] == "paused"


def _assert_cancelled(runtime, status, source, destination):
    receipt = runtime.apply_run.receipt_store.read(
        status["published_receipt"]["receipt_ref"]
    )
    content = receipt["sealed_content"]
    assert content["closure"] == "human_cancelled"
    assert content["completion"] == "incomplete"
    assert content["accounting"]["completed_and_verified"] == 1
    assert content["accounting"]["not_attempted"] == 1
    assert (destination / "Media/Trip/a.jpg").exists()
    assert (source / "b.jpg").exists()
    assert not (destination / "Media/Trip/renamed.jpg").exists()
    assert all(row["attempts"] <= 1 for row in content["operation_ledger"]["items"])


@pytest.mark.parametrize("cancelling_host", [0, 1])
def test_paused_cancel_is_closed_by_host_without_manual_advance(
    tmp_path, monkeypatch, cancelling_host
):
    hosts, dataset, runtime, call, execute, source, destination, _ = _hosts(
        tmp_path, monkeypatch
    )
    with _hold_first_effect(runtime) as (reached, release):
        _pause_after_first(hosts[0], dataset, runtime, call, execute, reached, release)
        cancelled = call(hosts[cancelling_host], "cancel")
        assert cancelled["target_state"] == "verifying"
        status = _wait_state(call, hosts[cancelling_host], "closed")
    _assert_cancelled(runtime, status, source, destination)


@pytest.mark.parametrize("action", ["execute", "resume"])
def test_second_host_contention_does_not_fail_the_active_run(
    tmp_path, monkeypatch, action
):
    hosts, dataset, runtime, call, execute, source, destination, _ = _hosts(
        tmp_path, monkeypatch
    )
    contender = hosts[1]._datasets[dataset]
    returned, threads = threading.Event(), []
    real_pending = contender.apply_run.run_pending

    def pending(run_ref):
        threads.append(threading.current_thread())
        try:
            return real_pending(run_ref)
        finally:
            returned.set()

    monkeypatch.setattr(contender.apply_run, "run_pending", pending)
    with _hold_first_effect(runtime) as (reached, release):
        _start(hosts[0], dataset, execute)
        assert reached.wait(10)
        if action == "execute":
            result = hosts[1].call_tool(
                "mediasense.apply.run", dataset_ref=dataset, request=execute
            )
        else:
            result = call(hosts[1], "resume")
        assert result["outcome"] == "accepted", result
        assert returned.wait(10)
        threads[0].join(10)
        assert not threads[0].is_alive()
        assert call(hosts[1], "status")["state"] == "executing"
        with runtime.apply_run.run_store._connect() as connection:
            assert not connection.execute(
                "SELECT 1 FROM findings WHERE code = 'executor_failed'"
            ).fetchall()
        release.set()
        status = _wait_state(call, hosts[0], "closed")
    receipt = runtime.apply_run.receipt_store.read(
        status["published_receipt"]["receipt_ref"]
    )
    assert receipt["sealed_content"]["completion"] == "complete"
    assert all(
        row["attempts"] == 1
        for row in receipt["sealed_content"]["operation_ledger"]["items"]
    )
    assert not (source / "b.jpg").exists()
    assert (destination / "Media/Trip/renamed.jpg").exists()


@pytest.mark.parametrize("window", ["pause_decision", "worker_exit"])
def test_cancel_is_not_lost_when_the_worker_is_leaving(tmp_path, monkeypatch, window):
    hosts, dataset, runtime, call, execute, source, destination, _ = _hosts(
        tmp_path, monkeypatch
    )
    leaving, finish = threading.Event(), threading.Event()
    real_set_state = runtime.apply_run.executor._set_state
    real_pending = runtime.apply_run.run_pending

    def set_state(run_ref, state, **kwargs):
        if window == "pause_decision" and state == "paused":
            leaving.set()
            assert finish.wait(10)
        return real_set_state(run_ref, state, **kwargs)

    def pending(run_ref):
        result = real_pending(run_ref)
        if window == "worker_exit" and result["state"] == "paused":
            leaving.set()
            assert finish.wait(10)
        return result

    monkeypatch.setattr(runtime.apply_run.executor, "_set_state", set_state)
    monkeypatch.setattr(runtime.apply_run, "run_pending", pending)
    with _hold_first_effect(runtime) as (reached, release):
        try:
            _start(hosts[0], dataset, execute)
            assert reached.wait(10)
            call(hosts[0], "pause")
            release.set()
            assert leaving.wait(10)
            assert call(hosts[0], "cancel")["target_state"] == "verifying"
        finally:
            finish.set()
        status = _wait_state(call, hosts[0], "closed")
    _assert_cancelled(runtime, status, source, destination)


@pytest.mark.parametrize("window", ["before_close", "before_lock"])
def test_interrupted_cancel_resume_keeps_the_cancellation(
    tmp_path, monkeypatch, window
):
    hosts, dataset, runtime, call, execute, source, destination, workspace = _hosts(
        tmp_path, monkeypatch
    )
    with _hold_first_effect(runtime) as (reached, release):
        _pause_after_first(hosts[0], dataset, runtime, call, execute, reached, release)
    script = """
import os, sys, time
from mediasense.runtime.host import RuntimeHost
host = RuntimeHost()
opened = host.open_dataset(sys.argv[1], sys.argv[2])
assert opened["outcome"] == "ok", opened
runtime = host._datasets[opened["dataset_ref"]]
if sys.argv[4] == "before_lock":
    runtime.apply_run.executor._run_lock = lambda *args, **kwargs: os._exit(42)
else:
    runtime.apply_run.executor._close = lambda *args, **kwargs: os._exit(42)
response = host.call_tool("mediasense.apply.run", dataset_ref=opened["dataset_ref"],
                         request={"action":"cancel", "run_ref":sys.argv[3]})
assert response["target_state"] == "verifying", response
time.sleep(10)
raise AssertionError("Host never started cancellation closure")
"""
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(source),
            str(workspace),
            execute["run_ref"],
            window,
        ],
        env=dict(os.environ),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 42, completed.stderr
    assert call(hosts[1], "status")["state"] == "needs_attention"
    assert call(hosts[1], "resume")["outcome"] == "accepted"
    status = _wait_state(call, hosts[1], "closed")
    _assert_cancelled(runtime, status, source, destination)


def test_real_worker_failure_still_surfaces(tmp_path, monkeypatch):
    hosts, dataset, runtime, call, execute, source, _, _ = _hosts(tmp_path, monkeypatch)
    errors, failed = [], threading.Event()

    def fault(point, item):
        if point == "after_intent":
            # Matching an admission error's text must not classify a bug as busy.
            raise RuntimeError("another executor is already advancing this Run")

    def thread_error(args):
        errors.append(args.exc_value)
        failed.set()

    monkeypatch.setattr(threading, "excepthook", thread_error)
    runtime.apply_run.executor.fault_hook = fault
    _start(hosts[0], dataset, execute)
    assert failed.wait(10)
    status = call(hosts[0], "status")
    assert status["state"] == "failed"
    assert any(reason["code"] == "executor_failed" for reason in status["reasons"])
    assert isinstance(errors[0], RuntimeError)
    assert (source / "a.jpg").exists()


def test_new_cancel_wakes_a_contender_that_is_exiting(tmp_path, monkeypatch):
    from mediasense.apply.execution import ApplyExecutorBusy

    hosts, dataset, runtime, call, execute, source, destination, _ = _hosts(
        tmp_path, monkeypatch
    )
    contender = hosts[1]._datasets[dataset]
    busy, finish = threading.Event(), threading.Event()
    real_pending = contender.apply_run.run_pending

    def pending(run_ref):
        try:
            return real_pending(run_ref)
        except ApplyExecutorBusy:
            busy.set()
            assert finish.wait(10)
            raise

    monkeypatch.setattr(contender.apply_run, "run_pending", pending)
    with _hold_first_effect(runtime) as (reached, release):
        try:
            _start(hosts[0], dataset, execute)
            assert reached.wait(10)
            call(hosts[0], "pause")
            with runtime._worker_lock:
                owner = runtime._workers[f"apply:{execute['run_ref']}"]
            retry = hosts[1].call_tool(
                "mediasense.apply.run", dataset_ref=dataset, request=execute
            )
            assert retry["outcome"] == "accepted"
            assert busy.wait(10)
            release.set()
            owner.join(10)
            assert not owner.is_alive()
            assert call(hosts[0], "status")["state"] == "paused"
            assert call(hosts[1], "cancel")["target_state"] == "verifying"
        finally:
            finish.set()
        status = _wait_state(call, hosts[1], "closed")
    _assert_cancelled(runtime, status, source, destination)


@pytest.mark.parametrize("window", ["before_schedule", "before_execution_lock"])
def test_other_host_status_cannot_interrupt_cancel_startup(
    tmp_path, monkeypatch, window
):
    hosts, dataset, runtime, call, execute, source, destination, workspace = _hosts(
        tmp_path, monkeypatch
    )
    starting, release = threading.Event(), threading.Event()
    accepted, errors = [], []

    with _hold_first_effect(runtime) as (reached, finish_effect):
        _pause_after_first(
            hosts[0], dataset, runtime, call, execute, reached, finish_effect
        )

    schedule = runtime._schedule_apply
    run_lock = runtime.apply_run.executor._run_lock

    def delayed_schedule(run_ref):
        if window == "before_schedule":
            starting.set()
            assert release.wait(10)
        return schedule(run_ref)

    @contextmanager
    def delayed_execution_lock(run_ref):
        if window == "before_execution_lock":
            starting.set()
            assert release.wait(10)
        with run_lock(run_ref):
            yield

    def cancel():
        try:
            accepted.append(call(hosts[0], "cancel"))
        except BaseException as error:
            errors.append(error)

    monkeypatch.setattr(runtime, "_schedule_apply", delayed_schedule)
    monkeypatch.setattr(runtime.apply_run.executor, "_run_lock", delayed_execution_lock)
    caller = threading.Thread(target=cancel)
    caller.start()
    try:
        assert starting.wait(10)
        if window == "before_execution_lock":
            # The public cancel response has returned, but the worker cannot
            # yet acquire its effect lock. This is the reported interleaving.
            caller.join(10)
            assert accepted[0]["target_state"] == "verifying"
        for _ in range(3):
            status = call(hosts[1], "status")
            assert status["state"] == "verifying", status
        if window == "before_execution_lock":
            # Also prove the liveness claim across processes, not just two
            # RuntimeHost objects with independent local worker registries.
            script = """
import sys
from mediasense.runtime.host import RuntimeHost
host = RuntimeHost()
opened = host.open_dataset(sys.argv[1], sys.argv[2])
assert opened["outcome"] == "ok", opened
status = host.call_tool("mediasense.apply.run", dataset_ref=opened["dataset_ref"],
                       request={"action":"status", "run_ref":sys.argv[3]})
print(status["state"])
"""
            observed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    script,
                    str(source),
                    str(workspace),
                    execute["run_ref"],
                ],
                env=dict(os.environ),
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert observed.returncode == 0, observed.stderr
            assert observed.stdout.strip() == "verifying"
        with runtime.apply_run.run_store._connect() as connection:
            assert not connection.execute(
                "SELECT 1 FROM findings WHERE code = 'executor_interrupted'"
            ).fetchall()
        assert (source / "b.jpg").exists()
    finally:
        release.set()
        caller.join(10)
    assert not caller.is_alive() and not errors, errors
    assert accepted[0]["target_state"] == "verifying"
    status = _wait_state(call, hosts[1], "closed")
    _assert_cancelled(runtime, status, source, destination)


def test_failed_worker_start_releases_liveness_and_can_resume_cancel(
    tmp_path, monkeypatch
):
    hosts, dataset, runtime, call, execute, source, destination, _ = _hosts(
        tmp_path, monkeypatch
    )
    with _hold_first_effect(runtime) as (reached, release):
        _pause_after_first(hosts[0], dataset, runtime, call, execute, reached, release)
    start = threading.Thread.start

    def fail_start(worker):
        if worker.name == f"mediasense-{execute['run_ref']}":
            raise RuntimeError("controlled worker startup failure")
        return start(worker)

    with monkeypatch.context() as patch:
        patch.setattr(threading.Thread, "start", fail_start)
        with pytest.raises(RuntimeError, match="controlled worker startup failure"):
            call(hosts[0], "cancel")
    assert call(hosts[1], "status")["state"] == "needs_attention"
    assert call(hosts[1], "resume")["outcome"] == "accepted"
    status = _wait_state(call, hosts[1], "closed")
    _assert_cancelled(runtime, status, source, destination)


@pytest.mark.parametrize("action", ["execute", "resume"])
def test_other_host_status_cannot_interrupt_forward_startup(
    tmp_path, monkeypatch, action
):
    hosts, dataset, runtime, call, execute, source, destination, _ = _hosts(
        tmp_path, monkeypatch
    )
    if action == "resume":
        with _hold_first_effect(runtime) as (reached, release):
            _pause_after_first(
                hosts[0], dataset, runtime, call, execute, reached, release
            )
    starting, release = threading.Event(), threading.Event()
    run_lock = runtime.apply_run.executor._run_lock

    @contextmanager
    def delayed_execution_lock(run_ref):
        starting.set()
        assert release.wait(10)
        with run_lock(run_ref):
            yield

    monkeypatch.setattr(runtime.apply_run.executor, "_run_lock", delayed_execution_lock)
    try:
        if action == "execute":
            _start(hosts[0], dataset, execute)
        else:
            assert call(hosts[0], "resume")["outcome"] == "accepted"
        assert starting.wait(10)
        assert call(hosts[1], "status")["state"] == "executing"
    finally:
        release.set()
    status = _wait_state(call, hosts[1], "closed")
    assert status["published_receipt"]["completion"] == "complete"
    assert not (source / "b.jpg").exists()
    assert (destination / "Media/Trip/renamed.jpg").exists()
