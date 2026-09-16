"""Partial Work, exact review binding, projection and delivery recovery boundaries."""

from copy import deepcopy
from dataclasses import replace
import sqlite3

import pytest

from mediasense.plan import PlanWorkTool
from mediasense.plan._sqlite import SQLitePlanStore
from mediasense.plan.view import PlanView, ViewDeliveryFailure, unavailable_view
from mediasense.plan._sqlite import RevisionConflict
from _plan_support import valid_candidate
from test_plan_work import _tool, _create, _confirmation, _seal_request


def save(tool, state, **fields):
    return tool.handle(
        {
            "action": "update",
            "work_ref": state["work_ref"],
            "base_revision": state["revision"],
            "request_id": "request:" + state["revision"],
            **fields,
        }
    )


def inspect(tool, state):
    return tool.handle(
        {
            "action": "inspect",
            "work_ref": state["work_ref"],
            "sections": ["overview", "content", "validation"],
        }
    )


def test_partial_draft_unassigned_and_candidate_promotion(tmp_path):
    tool = _tool(tmp_path)
    state = _create(tool)
    view = PlanView(tool, state["work_ref"])
    assert view.overview(state["revision"])["scope_summary"] is None
    draft = valid_candidate()
    draft["kind"] = "draft"
    draft["groups"] = draft["groups"][:1]
    draft["other_outcomes"] = []
    state = save(
        tool, state, organization_content=draft, working_notes="A partial decision"
    )
    observed = inspect(tool, state)
    assert observed["sections"]["overview"]["scope_summary"] == {
        "scope": 5,
        "organized": 3,
        "other_outcomes": 0,
        "unassigned": 2,
    }
    assert "candidate_content_identity" not in observed
    assert (
        observed["sections"]["validation"]["issues"][0]["code"] == "draft_not_candidate"
    )
    assert view.page(state["revision"], "unassigned")["total"] == 2
    all_draft = {**valid_candidate(), "kind": "draft"}
    state = save(tool, state, organization_content=all_draft)
    assert (
        inspect(tool, state)["sections"]["overview"]["scope_summary"]["unassigned"] == 0
    )
    assert "candidate_content_identity" not in inspect(tool, state)
    invalid = {**draft, "kind": "candidate"}
    assert (
        save(tool, state, organization_content=invalid)["error"]["code"]
        == "organization_invalid"
    )
    assert inspect(tool, state)["revision"] == state["revision"]
    state = save(tool, state, organization_content=valid_candidate())
    assert inspect(tool, state)["sections"]["validation"]["seal_ready"]


def test_notes_same_value_withdraw_restore_invalidate_acceptance(tmp_path):
    tool = _tool(tmp_path)
    state = save(tool, _create(tool), organization_content=valid_candidate())
    identity = inspect(tool, state)["candidate_content_identity"]
    confirmation = _confirmation(identity, state)
    original = deepcopy(state)
    for fields in (
        {"working_notes": ""},
        {"organization_content": None},
        {"organization_content": valid_candidate()},
    ):
        old = state
        state = save(tool, state, **fields)
        assert state["revision"] != old["revision"]
        rejected = tool.handle(
            _seal_request(state, state, identity), confirmation=confirmation
        )
        assert rejected["error"]["code"] == "confirmation_binding_mismatch"
    assert inspect(tool, state)["candidate_content_identity"] == identity
    view = PlanView(tool, state["work_ref"])
    with pytest.raises(RevisionConflict):
        view.page(original["revision"], "group:0")
    view.overview(state["revision"])
    view.page(state["revision"], "group:0")
    sealed = tool.handle(
        _seal_request(state, state, identity),
        confirmation=_confirmation(identity, state),
    )
    assert sealed["outcome"] == "ok"
    assert view.overview(state["revision"])["confirmation"]


def test_delivery_observation_replay_and_unexpected_failure_preserve_commit(tmp_path):
    tool = _tool(tmp_path)
    state = _create(tool)
    request = {
        "action": "update",
        "work_ref": state["work_ref"],
        "base_revision": state["revision"],
        "request_id": "request:delivery",
        "working_notes": "saved",
    }

    def broken(receipt):
        raise RuntimeError("renderer defect")

    tool.view_delivery = broken
    with pytest.raises(ViewDeliveryFailure) as caught:
        tool.handle(request)
    receipt = caught.value.receipt
    assert caught.value.__cause__.args == ("renderer defect",)
    assert (
        tool.handle(
            {
                "action": "inspect",
                "work_ref": state["work_ref"],
                "sections": ["working_notes"],
            }
        )["sections"]["working_notes"]
        == "saved"
    )
    tool.view_delivery = lambda r: unavailable_view(
        r, "view_service_unavailable", "fixture transport offline"
    )
    replay = tool.handle(request)
    assert {k: v for k, v in replay.items() if k != "view"} == receipt
    assert tool.store.snapshot(state["work_ref"]).revision == receipt["revision"]
    assert replay["view"]["status"] == "unavailable"


def test_v3_migration_retains_receipts_keys_and_frozen_identity(tmp_path):
    tool = _tool(tmp_path)
    state = save(tool, _create(tool), organization_content=valid_candidate())
    before = tool.store.snapshot(state["work_ref"])
    key = tool._cursor_signing_key
    import json

    with sqlite3.connect(tool.store.database_path) as db:
        legacy = {k: v for k, v in before.candidate.items() if k != "kind"}
        db.execute("UPDATE plan_works SET candidate_json = ?", (json.dumps(legacy),))
        db.execute("UPDATE internal_schema SET version = 3")
        rows = db.execute("SELECT * FROM plan_requests").fetchall()
        db.execute("ALTER TABLE plan_works DROP COLUMN scope_summary_json")
    migrated = PlanWorkTool(tool.plan_store, tool.precheck_read)
    after = migrated.store.snapshot(state["work_ref"])
    assert after == replace(before, scope_summary=None)
    assert migrated._cursor_signing_key == key
    assert migrated.store.database_path.with_suffix(".v3-backup.sqlite3").exists()
    with sqlite3.connect(migrated.store.database_path) as db:
        assert db.execute("SELECT * FROM plan_requests").fetchall() == rows
    assert (
        inspect(migrated, state)["sections"]["overview"]["scope_summary"]["scope"] == 5
    )


def test_pending_legacy_publication_refuses_migration(tmp_path):
    tool = _tool(tmp_path)
    with sqlite3.connect(tool.store.database_path) as db:
        db.execute("UPDATE internal_schema SET version = 3")
        db.execute(
            "INSERT INTO plan_seal_reservations VALUES (?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
            tuple(str(i) for i in range(9)),
        )
    with pytest.raises(RuntimeError, match="Recover pending v3 seals"):
        SQLitePlanStore(tool.store.database_path)


def test_runtime_reports_committed_receipt_after_unexpected_renderer_failure(tmp_path):
    from test_runtime_host import _opened_host_with_plan_ready_result

    host, dataset, result, *_ = _opened_host_with_plan_ready_result(tmp_path)
    runtime = host._datasets[dataset]

    def broken(receipt):
        raise RuntimeError("injected renderer defect")

    runtime.plan_work.view_delivery = broken
    response = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset,
        request={
            "action": "create",
            "result_ref": result,
            "request_id": "request:runtime-commit",
        },
    )
    assert response["error"]["code"] == "operation_failed"
    receipt = response["committed_receipt"]
    assert receipt["outcome"] == "ok"
    observed = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset,
        request={
            "action": "inspect",
            "work_ref": receipt["work_ref"],
            "sections": ["overview"],
        },
    )
    assert observed["revision"] == receipt["revision"]
    assert observed["outcome"] == "ok"


def test_unexpected_reader_exception_is_not_a_normal_view_or_validation_issue(
    tmp_path, monkeypatch
):
    tool = _tool(tmp_path)
    state = _create(tool)

    def defect(request):
        raise RuntimeError("unexpected reader bug")

    monkeypatch.setattr(tool.precheck_read, "read", defect)
    with pytest.raises(RuntimeError, match="unexpected reader bug"):
        save(tool, state, organization_content=valid_candidate())
    assert tool.store.snapshot(state["work_ref"]).revision == state["revision"]


@pytest.mark.parametrize("collection", ["decision_notes", "note:0"])
@pytest.mark.parametrize("failure", [RuntimeError, ValueError, KeyError, None])
def test_note_resolution_errors_keep_their_meaning_at_the_page_boundary(
    tmp_path, monkeypatch, collection, failure
):
    from types import SimpleNamespace
    from urllib.parse import urlencode
    from mediasense.runtime._view_server import Handler
    from mediasense.source_sets import SourceSetResolutionError

    tool = _tool(tmp_path)
    state = save(tool, _create(tool), organization_content=valid_candidate())
    view = PlanView(tool, state["work_ref"])
    # The initial analysis succeeded. Exercise the later note resolver rather
    # than failing the already-covered candidate-analysis path.
    view.overview(state["revision"])
    before = tool.store.snapshot(state["work_ref"])
    original = tool.precheck_read.read

    def read(request):
        if request["action"] == "resolve":
            if failure is not None:
                raise failure("injected note-resolution defect")
            return {"error": {"code": "result_unavailable", "message": "offline"}}
        return original(request)

    monkeypatch.setattr(tool.precheck_read, "read", read)
    with pytest.raises(failure or SourceSetResolutionError):
        view.page(state["revision"], collection)

    responses = []
    from contextlib import nullcontext

    route = SimpleNamespace(
        work_ref=state["work_ref"], database=tool.store.database_path
    )
    lifecycle = SimpleNamespace(
        current=lambda *a, **kw: {"revision": state["revision"], "state": "open"},
        heavy=lambda *a, **kw: nullcontext(view),
        last_failure=None,
    )
    handler = SimpleNamespace(
        path="/v/test/page?"
        + urlencode({"revision": state["revision"], "collection": collection}),
        server=SimpleNamespace(
            routes={"test": route}, lifecycle=lifecycle, origin="http://127.0.0.1:12345"
        ),
        _allowed=lambda: True,
        send=lambda *args: responses.append(args),
    )
    handler.failure = lambda *args: Handler.failure(handler, *args)
    Handler.do_GET(handler)
    status, body = responses.pop()
    assert status == (500 if failure else 503)
    assert body["error"] == (
        "operation_failed" if failure else "view_resource_unavailable"
    )
    assert tool.store.snapshot(state["work_ref"]) == before
    # Malformed page input remains an input error, including while Read fails.
    handler.path = "/v/test/page?" + urlencode(
        {"revision": state["revision"], "collection": "note:bad"}
    )
    Handler.do_GET(handler)
    assert responses.pop()[0] == 400
    monkeypatch.setattr(tool.precheck_read, "read", original)
    assert view.page(state["revision"], collection)["items"]


def test_derived_directory_totals_include_own_members_and_descendants(tmp_path):
    tool = _tool(tmp_path)
    candidate = valid_candidate()
    candidate["groups"][0]["relative_path"] = ["Parent", "Child", "Leaf"]
    candidate["groups"][1]["relative_path"] = ["Parent"]
    state = save(tool, _create(tool), organization_content=candidate)
    view = PlanView(tool, state["work_ref"])
    groups = view.page(state["revision"], "groups")["items"]
    assert groups[0]["total"] == 3
    assert groups[0]["path_totals"] == [4, 4, 3, 3]
    assert groups[1]["total"] == 1
    assert groups[1]["path_totals"] == [4, 4]
