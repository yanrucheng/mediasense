"""Optional work updates preserve whole-Work atomicity and content authority."""

from itertools import product
import sqlite3

import pytest

from mediasense.plan import PlanWorkTool, PlanPreviewRenderer, PreviewError
import mediasense.plan.work as working
from _plan_support import valid_candidate, validators
from test_plan_work import _tool, _create, _update, _confirmation, _seal_request


def update(tool, state, **fields):
    return tool.handle(
        {
            "action": "update",
            "work_ref": state["work_ref"],
            "base_revision": state["revision"],
            "request_id": "request:" + state["revision"],
            **fields,
        }
    )


def inspect(tool, state, **fields):
    return tool.handle({"action": "inspect", "work_ref": state["work_ref"], **fields})


@pytest.mark.parametrize("present", [False, True])
@pytest.mark.parametrize("modes", [m for m in product(range(3), repeat=3) if any(m)])
def test_field_omission_replacement_and_clear_matrix(tmp_path, present, modes):
    tool = _tool(tmp_path)
    state = _create(tool)
    if present:
        state = _update(tool, state)
    state = update(
        tool, state, working_notes="original", organization_preferences={"old": 1}
    )
    before = tool.store.snapshot(state["work_ref"])
    candidate = valid_candidate()
    candidate["decision_notes"][0]["summary"] = "Human supplied scoped correction"
    fields = {}
    for name, mode, values in zip(
        ("working_notes", "organization_preferences", "candidate_content"),
        modes,
        (("", "新说明\n\x00 e\u0301"), ({}, {"new": 2}), (None, candidate)),
        strict=True,
    ):
        if mode:
            fields[name] = values[mode - 1]
    result = update(tool, state, **fields)
    assert result["outcome"] == "ok"
    after = tool.store.snapshot(state["work_ref"])
    assert after.revision != before.revision
    assert after.working_notes == fields.get("working_notes", before.working_notes)
    assert after.organization_preferences == fields.get(
        "organization_preferences", before.organization_preferences
    )
    assert after.candidate == fields.get("candidate_content", before.candidate)
    assert after.plan_ref == before.plan_ref
    if modes[2] == 0:
        assert after.candidate_identity == before.candidate_identity
    elif modes[2] == 1:
        assert after.candidate_identity is None
    else:
        assert after.candidate_identity != before.candidate_identity
    assert update(tool, state, **fields) == result
    _, output = validators()
    output.validate(inspect(tool, state))


@pytest.mark.parametrize(
    "fields,code",
    [
        ({}, "invalid_request"),
        ({"working_notes": None}, "invalid_request"),
        ({"working_notes": {}}, "invalid_request"),
        ({"organization_preferences": None}, "invalid_request"),
        ({"candidate_content": []}, "invalid_request"),
        ({"unknown": True}, "invalid_request"),
        ({"candidate_content": {}}, "candidate_invalid"),
    ],
)
def test_invalid_update_changes_no_field(tmp_path, fields, code):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    before = tool.store.snapshot(state["work_ref"])
    result = update(tool, state, **fields)
    assert result["error"]["code"] == code
    assert tool.store.snapshot(state["work_ref"]) == before


def test_semantically_invalid_combination_is_atomic(tmp_path):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    before = tool.store.snapshot(state["work_ref"])
    candidate = valid_candidate()
    candidate["groups"][1]["members"] = candidate["groups"][0]["members"]
    result = update(
        tool,
        state,
        working_notes="must not save",
        organization_preferences={},
        candidate_content=candidate,
    )
    assert result["error"]["code"] == "candidate_invalid"
    assert tool.store.snapshot(state["work_ref"]) == before


def test_notes_restart_exact_text_replay_and_same_value_revision(tmp_path):
    tool = _tool(tmp_path)
    state = _create(tool)
    notes = "用户: “已确认”仅指人物，不是整份方案。\r\n\t\x00e\u0301 🐈" * 10000
    result = update(tool, state, working_notes=notes)
    restarted = PlanWorkTool(tool.plan_store, tool.precheck_read)
    observed = inspect(restarted, state)
    assert observed["sections"]["working_notes"] == notes
    assert observed["sections"]["content"] is None
    assert "candidate_content_identity" not in observed
    assert observed["returned_sections"] == [
        "overview",
        "preferences",
        "working_notes",
        "content",
        "validation",
    ]
    assert (
        observed["sections"]["validation"]["issues"][0]["code"] == "candidate_missing"
    )
    assert update(restarted, state, working_notes=notes) == result
    assert (
        update(restarted, state, working_notes=notes, candidate_content=None)["error"][
            "code"
        ]
        == "idempotency_conflict"
    )
    same = update(restarted, result, working_notes=notes)
    assert same["revision"] != result["revision"]
    selected = inspect(restarted, state, sections=["working_notes"])
    assert selected["sections"] == {"working_notes": notes}


def test_light_updates_do_not_read_analyze_or_decode_saved_candidate(
    tmp_path, monkeypatch
):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    identity = inspect(tool, state)["candidate_content_identity"]

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected Candidate analysis or Read")

    monkeypatch.setattr(working, "analyze_candidate", forbidden)
    monkeypatch.setattr(tool.precheck_read, "read", forbidden)
    # A sentinel stands in for a large candidate. No light update may decode it.
    with sqlite3.connect(tool.store.database_path) as db:
        db.execute(
            "UPDATE plan_works SET candidate_json = ?", ("not-json:must-not-load",)
        )
    for fields in (
        {"working_notes": "notes"},
        {"organization_preferences": {}},
        {"candidate_content": None},
    ):
        state = update(tool, state, **fields)
        assert state["outcome"] == "ok"
        with sqlite3.connect(tool.store.database_path) as db:
            saved = db.execute(
                "SELECT candidate_json, candidate_identity FROM plan_works"
            ).fetchone()
        assert saved == (
            (None, None)
            if "candidate_content" in fields
            else ("not-json:must-not-load", identity)
        )


def test_no_candidate_pagination_validates_cursor_and_shape(tmp_path):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    first = inspect(
        tool, state, sections=["content"], page={"collection": "groups", "limit": 1}
    )
    cursor = first["sections"]["content"]["page"]["next_cursor"]
    old_revision = state["revision"]
    state = update(tool, state, candidate_content=None)
    for collection in ("groups", "other_outcomes", "decision_notes"):
        result = inspect(
            tool,
            state,
            sections=["content"],
            page={"collection": collection, "limit": 1},
        )
        assert result["sections"] == {"content": None}
    assert (
        inspect(
            tool,
            state,
            sections=["content"],
            page={"collection": "groups", "cursor": cursor},
        )["error"]["code"]
        == "invalid_cursor"
    )
    assert (
        inspect(tool, state, revision=old_revision)["error"]["code"]
        == "revision_conflict"
    )
    for page in ({}, {"collection": "groups", "limit": 0}, {"collection": "unknown"}):
        assert (
            inspect(tool, state, sections=["content"], page=page)["error"]["code"]
            == "invalid_request"
        )
    with pytest.raises(PreviewError, match="no candidate"):
        PlanPreviewRenderer(tool).build(state["work_ref"], state["revision"])
    identity = "sha256:" + "0" * 64
    assert (
        tool.handle(
            _seal_request(state, state, identity), confirmation=_confirmation(identity)
        )["error"]["code"]
        == "candidate_invalid"
    )


def test_notes_revision_requires_refresh_but_not_new_content_acceptance(tmp_path):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    identity = inspect(tool, state)["candidate_content_identity"]
    request = _seal_request(state, state, identity)
    newer = update(tool, state, working_notes="local correction is not acceptance")
    assert (
        tool.handle(request, confirmation=_confirmation(identity))["error"]["code"]
        == "revision_conflict"
    )
    request["revision"] = newer["revision"]
    assert tool.handle(request)["error"]["code"] == "confirmation_required"
    result = tool.handle(request, confirmation=_confirmation(identity))
    assert result["outcome"] == "ok"
    assert "working_notes" not in result["frozen_plan"]["sealed_content"]
    assert (
        update(tool, newer, working_notes="after seal")["error"]["code"]
        == "work_closed"
    )
    assert (
        inspect(tool, newer)["sections"]["working_notes"]
        == "local correction is not acceptance"
    )


def test_v3_additive_extension_preserves_work_receipts_and_cursor_key(tmp_path):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    before = tool.store.snapshot(state["work_ref"])
    key = tool._cursor_signing_key
    with sqlite3.connect(tool.store.database_path) as db:
        db.execute("ALTER TABLE plan_works DROP COLUMN working_notes")
    reopened = PlanWorkTool(tool.plan_store, tool.precheck_read)
    assert reopened.store.snapshot(state["work_ref"]) == before
    assert reopened._cursor_signing_key == key
    assert _create(reopened)["work_ref"] == state["work_ref"]
    assert update(reopened, state, working_notes="after extension")["outcome"] == "ok"


def test_notes_cannot_overwrite_pending_seal_and_recovery_survives(
    tmp_path, monkeypatch
):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    identity = inspect(tool, state)["candidate_content_identity"]
    request = _seal_request(state, state, identity)

    def crash(**kwargs):
        raise RuntimeError("publication interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(tool.store, "complete_seal", crash)
        with pytest.raises(RuntimeError):
            tool.handle(request, confirmation=_confirmation(identity))
    before = tool.store.snapshot(state["work_ref"])
    assert (
        update(tool, state, working_notes="cannot overwrite")["error"]["code"]
        == "operation_failed"
    )
    assert tool.store.snapshot(state["work_ref"]) == before
    restarted = PlanWorkTool(tool.plan_store, tool.precheck_read)
    assert (
        restarted.handle(request, confirmation=_confirmation(identity))["outcome"]
        == "ok"
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"revision": None},
        {"sections": [{}]},
        {"sections": ["unknown"]},
        {"sections": ["content"], "page": None},
    ],
)
def test_absent_candidate_does_not_bypass_request_shape_checks(tmp_path, fields):
    tool = _tool(tmp_path)
    state = _create(tool)
    assert inspect(tool, state, **fields)["error"]["code"] == "invalid_request"


@pytest.mark.parametrize(
    "field,value",
    [
        ("plan_ref", "frozen-plan:injected"),
        ("contract", "mediasense.frozen-plan"),
        ("seal", {}),
        ("other_outcomes", [None]),
        ("other_outcomes", 1),
        ("groups", [None]),
        ("decision_notes", [None]),
        ("scope", None),
    ],
)
def test_candidate_structure_rejected_before_read_or_combined_write(
    tmp_path, monkeypatch, field, value
):
    tool = _tool(tmp_path)
    state = _update(tool, _create(tool))
    before = tool.store.snapshot(state["work_ref"])
    candidate = valid_candidate()
    candidate[field] = value

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid Candidate must not read PreCheck")

    monkeypatch.setattr(tool.precheck_read, "read", forbidden)
    response = update(
        tool,
        state,
        candidate_content=candidate,
        working_notes="must not save",
        organization_preferences={},
    )
    assert response["error"]["code"] == "candidate_invalid"
    assert tool.store.snapshot(state["work_ref"]) == before
    assert not list(tool.frozen_dir.glob("*.json"))
