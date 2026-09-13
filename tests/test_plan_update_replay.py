"""Successful receipts take precedence across update preflight commit gaps."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Event

import pytest

from mediasense.plan import PlanWorkTool
from mediasense.runtime.resources import schema_path
from test_plan_update_execution import count_analysis, update_count
from test_plan_update_mcp import GatedReader, update_request
from test_plan_work import _confirmation, _create, _seal_request, _tool


def _receipt(response):
    # Delivery is a fresh observation; only the committed business receipt is
    # replay-stable. Revision/state and all side-effect assertions remain exact.
    return {key: value for key, value in response.items() if key != "view"}


@pytest.mark.parametrize("retry", ["identical", "different_payload", "different_id"])
@pytest.mark.parametrize("seal_after_commit", [False, True])
def test_owner_commit_between_replay_lookup_and_state_check(
    tmp_path, monkeypatch, retry, seal_after_commit
):
    reader = GatedReader()
    owner = _tool(tmp_path, reader)
    created = _create(owner)
    request = update_request(created)
    following = deepcopy(request)
    if retry == "different_payload":
        following["organization_preferences"] = {"example": "different content"}
    elif retry == "different_id":
        following["request_id"] = "request:another-update"
    peer = PlanWorkTool(
        owner.plan_store,
        reader,
        frozen_plan_schema=schema_path("frozen-plan.schema.json"),
    )
    counts = count_analysis(monkeypatch)
    looked_up, committed = Event(), Event()
    replay = peer.store.replay

    def interleave(request_id, digest):
        result = replay(request_id, digest)
        if result is None:
            looked_up.set()
            assert committed.wait(5), "owner did not finish"
        return result

    monkeypatch.setattr(peer.store, "replay", interleave)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(owner.handle, request)
        try:
            assert reader.started.wait(5)
            second = pool.submit(peer.handle, following)
            assert looked_up.wait(5)
            reader.release.set()
            original = first.result(5)
            assert original["outcome"] == "ok"
            assert counts == {"calls": 1, "active": 0, "peak": 1}
            if seal_after_commit:
                identity = owner.store.snapshot(created["work_ref"]).candidate_identity
                sealed = owner.handle(
                    _seal_request(created, original, identity),
                    confirmation=_confirmation(identity),
                )
                assert sealed["outcome"] == "ok"
            before_retry = owner.store.snapshot(created["work_ref"])
            analysis_calls = counts["calls"]
            committed.set()
            retried = second.result(5)
        finally:
            reader.release.set()
            committed.set()

    assert _receipt(owner.handle(request)) == _receipt(original)
    if retry == "identical":
        assert _receipt(retried) == _receipt(original)
    else:
        assert retried["error"]["code"] == (
            "idempotency_conflict"
            if retry == "different_payload"
            else "work_closed"
            if seal_after_commit
            else "revision_conflict"
        )
    assert counts["calls"] == analysis_calls
    assert update_count(owner) == 1
    assert owner.store.snapshot(created["work_ref"]) == before_retry


def test_seal_commit_in_post_admission_check_preserves_idempotency_conflict(
    tmp_path, monkeypatch
):
    owner = _tool(tmp_path)
    created = _create(owner)
    updated = owner.handle(update_request(created))
    assert updated["outcome"] == "ok"
    identity = owner.store.snapshot(created["work_ref"]).candidate_identity
    seal = _seal_request(created, updated, identity)
    peer = PlanWorkTool(
        owner.plan_store,
        owner.precheck_read,
        frozen_plan_schema=schema_path("frozen-plan.schema.json"),
    )
    # Seal does not take the update validation lock. Its receipt and closed
    # state can appear between the second replay lookup and snapshot check.
    replay = peer.store.replay
    lookups = 0
    counts = count_analysis(monkeypatch)

    def interleave(request_id, digest):
        nonlocal lookups
        result = replay(request_id, digest)
        lookups += 1
        if lookups == 2:
            assert result is None
            sealed = owner.handle(seal, confirmation=_confirmation(identity))
            assert sealed["outcome"] == "ok"
        return result

    monkeypatch.setattr(peer.store, "replay", interleave)
    retried = peer.handle(update_request(updated, request_id=seal["request_id"]))

    assert retried["error"]["code"] == "idempotency_conflict"
    assert counts == {"calls": 1, "active": 0, "peak": 1}  # Seal only.
    assert update_count(owner) == 1
    snapshot = owner.store.snapshot(created["work_ref"])
    assert snapshot.state == "closed" and snapshot.revision == updated["revision"]
