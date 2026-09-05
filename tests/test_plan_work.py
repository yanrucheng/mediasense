from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from mediasense.plan import PlanWorkTool
from mediasense.plan import ConfirmationContext
from mediasense.plan.work import _encode_cursor_value

from _plan_support import (
    CountingPrecheckReader,
    MockPrecheckReader,
    ResultOverrideReader,
    StableIdFactory,
    valid_candidate,
    validators,
)


def _tool(tmp_path, reader=None) -> PlanWorkTool:
    return PlanWorkTool(
        tmp_path / "plan-store",
        reader or MockPrecheckReader(),
        id_factory=StableIdFactory(),
    )


def _create(tool: PlanWorkTool, *, request_id: str = "request:create-1") -> dict:
    return tool.handle(
        {
            "action": "create",
            "result_ref": "precheck-result:hk-review-slice-002",
            "organization_preferences": {"maximum_depth": 3},
            "request_id": request_id,
        }
    )


def test_constructor_rejects_callable_without_read_boundary(tmp_path: Path) -> None:
    def callable_only(_request: dict[str, object]) -> dict[str, object]:
        return {"outcome": "ok"}

    with pytest.raises(TypeError, match=r"read\(request\)"):
        PlanWorkTool(tmp_path / "plan-store", callable_only)  # type: ignore[arg-type]


def test_create_rejects_historical_result_with_incomplete_geo_acquisition(
    tmp_path: Path,
) -> None:
    class IncompleteGeoReader(MockPrecheckReader):
        def read(self, request):
            response = super().read(request)
            if request.get("operation") == "geo_summary":
                response["acquisition_status"] = "incomplete"
            return response

    result = _create(_tool(tmp_path, IncompleteGeoReader()))

    assert result["outcome"] == "error"
    assert result["error"]["code"] == "result_not_ready"


def _update(
    tool: PlanWorkTool,
    created: dict,
    *,
    request_id: str = "request:update-1",
    candidate=None,
) -> dict:
    return tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "candidate_content": candidate or valid_candidate(),
            "request_id": request_id,
        }
    )


def _confirmation(content_identity: str) -> ConfirmationContext:
    return ConfirmationContext(
        principal_ref="user:test-reviewer",
        confirmed_content_identity=content_identity,
        confirmed_at=datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc),
    )


def _seal_request(created: dict, updated: dict, content_identity: str) -> dict:
    return {
        "action": "seal",
        "work_ref": created["work_ref"],
        "revision": updated["revision"],
        "candidate_content_identity": content_identity,
        "request_id": "request:seal-1",
    }


def _prepared_for_seal(tmp_path):
    reader = MockPrecheckReader()
    tool = PlanWorkTool(tmp_path / "plan-store", reader, id_factory=StableIdFactory())
    created = _create(tool)
    updated = _update(tool, created)
    inspected = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["validation"],
        }
    )
    return tool, reader, created, updated, inspected["candidate_content_identity"]


def test_create_and_initial_inspect_conform_to_contract(tmp_path) -> None:
    _, output_validator = validators()
    tool = _tool(tmp_path)
    created = _create(tool)
    output_validator.validate(created)

    default_inspect = tool.handle(
        {"action": "inspect", "work_ref": created["work_ref"]}
    )
    explicit_content = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["content"],
        }
    )
    for response in (default_inspect, explicit_content):
        output_validator.validate(response)
        assert response["error"]["code"] == "candidate_invalid"
    assert default_inspect == explicit_content

    metadata = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["overview", "preferences", "validation"],
        }
    )
    output_validator.validate(metadata)
    assert metadata["revision"] == created["revision"]
    assert metadata["sections"]["preferences"] == {"maximum_depth": 3}
    assert metadata["sections"]["validation"]["seal_ready"] is False


def test_create_replays_and_rejects_request_id_reuse(tmp_path) -> None:
    tool = _tool(tmp_path)
    first = _create(tool)
    assert _create(tool) == first

    conflict = _create(tool, request_id="request:create-1")
    assert conflict == first
    changed = tool.handle(
        {
            "action": "create",
            "result_ref": "precheck-result:hk-review-slice-002",
            "organization_preferences": {"maximum_depth": 2},
            "request_id": "request:create-1",
        }
    )
    assert changed["error"]["code"] == "idempotency_conflict"


def test_create_enforces_result_gate(tmp_path) -> None:
    blocked = _create(
        _tool(tmp_path / "blocked", ResultOverrideReader(readiness="blocked"))
    )
    invalid = _create(
        _tool(tmp_path / "invalid", ResultOverrideReader(integrity="invalid"))
    )
    assert blocked["error"]["code"] == "result_not_ready"
    assert invalid["error"]["code"] == "result_untrusted"


def test_update_and_inspect_materialize_sealable_content(tmp_path) -> None:
    _, output_validator = validators()
    tool = _tool(tmp_path)
    created = _create(tool)
    updated = _update(tool, created)
    output_validator.validate(updated)
    assert updated["revision"] != created["revision"]

    inspected = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
        }
    )
    output_validator.validate(inspected)
    assert inspected["sections"]["validation"] == {"seal_ready": True, "issues": []}
    assert (
        inspected["sections"]["content"]["value"]["contract"]
        == "mediasense.frozen-plan"
    )
    assert inspected["candidate_content_identity"].startswith("sha256:")


def test_all_inspect_shapes_use_only_persisted_validated_revision(tmp_path) -> None:
    reader = CountingPrecheckReader()
    tool = PlanWorkTool(tmp_path / "plan-store", reader, id_factory=StableIdFactory())
    created = _create(tool)
    updated = _update(tool, created)
    reader.reset()

    requests = [
        {"sections": ["overview"]},
        {"sections": ["preferences"]},
        {"sections": ["content"]},
        {"sections": ["validation"]},
        {},
    ]
    responses = []
    for extra in requests:
        response = tool.handle(
            {
                "action": "inspect",
                "work_ref": created["work_ref"],
                "revision": updated["revision"],
                **extra,
            }
        )
        assert response["outcome"] == "ok"
        assert response["candidate_content_identity"].startswith("sha256:")
        assert reader.call_count == 0
        responses.append(response)

    content = responses[2]["sections"]["content"]
    assert content["mode"] == "complete"
    assert content["value"]["groups"] == valid_candidate()["groups"]
    assert responses[0]["sections"] == {"overview": {"state": "open"}}
    assert responses[1]["sections"] == {"preferences": {"maximum_depth": 3}}
    assert responses[3]["sections"]["validation"] == {
        "seal_ready": True,
        "issues": [],
    }
    assert set(responses[4]["returned_sections"]) == {
        "overview",
        "preferences",
        "content",
        "validation",
    }
    assert responses[4]["sections"]["content"] == content

    first_page = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "groups", "limit": 1},
        }
    )
    assert first_page["outcome"] == "ok"
    assert first_page["sections"]["content"]["items"] == valid_candidate()["groups"][:1]
    assert first_page["sections"]["content"]["page"]["returned"] == 1
    assert first_page["sections"]["content"]["page"]["complete"] is False
    assert reader.call_count == 0

    cursor = first_page["sections"]["content"]["page"]["next_cursor"]
    second_page = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "groups", "cursor": cursor},
        }
    )
    assert second_page["outcome"] == "ok"
    assert (
        second_page["sections"]["content"]["items"] == valid_candidate()["groups"][1:]
    )
    assert second_page["sections"]["content"]["page"] == {
        "collection": "groups",
        "returned": 1,
        "complete": True,
    }
    assert reader.call_count == 0


def test_update_is_atomic_and_revision_checked(tmp_path) -> None:
    tool = _tool(tmp_path)
    created = _create(tool)
    updated = _update(tool, created)
    assert _update(tool, created) == updated

    stale = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "candidate_content": valid_candidate(),
            "request_id": "request:update-stale",
        }
    )
    assert stale["error"]["code"] == "revision_conflict"
    assert stale["error"]["current_revision"] == updated["revision"]


def test_update_preference_omission_preserves_and_object_replaces(tmp_path) -> None:
    tool = _tool(tmp_path)
    created = _create(tool)
    updated = _update(tool, created)
    first_inspect = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["preferences"],
        }
    )
    assert first_inspect["sections"]["preferences"] == {"maximum_depth": 3}

    request = {
        "action": "update",
        "work_ref": created["work_ref"],
        "base_revision": updated["revision"],
        "candidate_content": valid_candidate(),
        "organization_preferences": {},
        "request_id": "request:update-2",
    }
    second = tool.handle(request)
    inspected = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["preferences"],
        }
    )
    assert second["outcome"] == "ok"
    assert inspected["sections"]["preferences"] == {}


def test_paged_inspect_binds_cursor_to_revision_collection_and_limit(tmp_path) -> None:
    _, output_validator = validators()
    tool = _tool(tmp_path)
    created = _create(tool)
    updated = _update(tool, created)
    first = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "groups", "limit": 1},
        }
    )
    assert first["sections"]["content"]["page"]["complete"] is False
    output_validator.validate(first)
    cursor = first["sections"]["content"]["page"]["next_cursor"]
    second = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "groups", "cursor": cursor},
        }
    )
    assert second["sections"]["content"]["page"] == {
        "collection": "groups",
        "returned": 1,
        "complete": True,
    }
    output_validator.validate(second)

    wrong = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "other_outcomes", "limit": 1, "cursor": cursor},
        }
    )
    assert wrong["error"]["code"] == "invalid_cursor"


def test_invalid_candidate_changes_nothing(tmp_path) -> None:
    tool = _tool(tmp_path)
    created = _create(tool)
    candidate = deepcopy(valid_candidate())
    candidate["groups"][1]["members"] = candidate["groups"][0]["members"]
    rejected = _update(tool, created, candidate=candidate)
    assert rejected["error"]["code"] == "candidate_invalid"
    inspected = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["overview", "validation"],
        }
    )
    assert inspected["revision"] == created["revision"]
    assert inspected["sections"]["validation"]["seal_ready"] is False


def _tamper_cursor(cursor: str, field: str, value) -> str:
    encoded_payload, signature = cursor.removeprefix("plan-cursor:").split(".", 1)
    padded = encoded_payload + "=" * (-len(encoded_payload) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    payload[field] = value
    changed = (
        base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        )
        .decode()
        .rstrip("=")
    )
    return f"plan-cursor:{changed}.{signature}"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("offset", 999),
        ("limit", 499),
        ("revision", "work-revision:forged"),
        ("collection", "other_outcomes"),
    ],
)
def test_tampered_cursor_is_rejected(tmp_path, field, value) -> None:
    tool = _tool(tmp_path)
    created = _create(tool)
    updated = _update(tool, created)
    first = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["content"],
            "page": {"collection": "groups", "limit": 1},
        }
    )
    cursor = first["sections"]["content"]["page"]["next_cursor"]
    forged = _tamper_cursor(cursor, field, value)
    response = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "groups", "cursor": forged},
        }
    )
    assert response["error"]["code"] == "invalid_cursor"


def test_signed_non_object_cursor_payload_is_rejected(tmp_path) -> None:
    tool = _tool(tmp_path)
    created = _create(tool)
    updated = _update(tool, created)
    cursor = _encode_cursor_value(["not", "an", "object"], tool._cursor_signing_key)
    response = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "groups", "cursor": cursor},
        }
    )
    assert response["error"]["code"] == "invalid_cursor"


def test_cursor_signature_survives_tool_restart(tmp_path) -> None:
    reader = MockPrecheckReader()
    plan_store = tmp_path / "plan-store"
    first_tool = PlanWorkTool(plan_store, reader, id_factory=StableIdFactory())
    created = _create(first_tool)
    updated = _update(first_tool, created)
    first_page = first_tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["content"],
            "page": {"collection": "groups", "limit": 1},
        }
    )
    cursor = first_page["sections"]["content"]["page"]["next_cursor"]

    restarted_tool = PlanWorkTool(plan_store, reader, id_factory=StableIdFactory())
    response = restarted_tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["content"],
            "page": {"collection": "groups", "cursor": cursor},
        }
    )
    assert response["outcome"] == "ok"
    assert response["sections"]["content"]["page"]["complete"] is True


def test_schema_invalid_candidate_is_never_stored_or_reported_seal_ready(
    tmp_path,
) -> None:
    tool = _tool(tmp_path)
    created = _create(tool)
    candidate = valid_candidate()
    evidence_refs = candidate["decision_notes"][0]["evidence_refs"]
    evidence_refs.append(evidence_refs[0])
    rejected = _update(tool, created, candidate=candidate)
    assert rejected["error"]["code"] == "candidate_invalid"

    inspected = tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "sections": ["overview", "validation"],
        }
    )
    assert inspected["sections"]["validation"]["seal_ready"] is False


def test_seal_requires_trusted_confirmation_and_exact_identity(tmp_path) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    request = _seal_request(created, updated, identity)

    missing = tool.handle(request)
    assert missing["error"]["code"] == "confirmation_required"
    assert tool.store.snapshot(created["work_ref"]).state == "open"

    mismatched = tool.handle(
        request,
        confirmation=_confirmation("sha256:" + "0" * 64),
    )
    assert mismatched["error"]["code"] == "content_identity_mismatch"
    assert tool.store.snapshot(created["work_ref"]).state == "open"


def test_successful_seal_publishes_conforming_plan_and_replays(tmp_path) -> None:
    _, output_validator = validators()
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    request = _seal_request(created, updated, identity)
    confirmation = _confirmation(identity)

    sealed = tool.handle(request, confirmation=confirmation)
    output_validator.validate(sealed)
    assert sealed["outcome"] == "ok"
    assert sealed["state"] == "closed"
    assert sealed["frozen_plan"]["seal"]["final_confirmation"] == {
        "confirmed_content_identity": identity,
        "confirmed_at": "2026-08-29T01:00:00Z",
        "confirmed_by": "user:test-reviewer",
    }
    snapshot = tool.store.snapshot(created["work_ref"])
    assert snapshot.state == "closed"
    assert snapshot.published_path is not None
    artifact = Path(snapshot.published_path)
    assert artifact.is_file()
    assert tool._publisher.read_verified(artifact) == sealed["frozen_plan"]
    assert tool.handle(request, confirmation=confirmation) == sealed


def test_mock_driven_preview_revision_and_seal_workflow(tmp_path) -> None:
    reader = CountingPrecheckReader()
    tool = PlanWorkTool(tmp_path / "plan-store", reader, id_factory=StableIdFactory())
    created = _create(tool)
    first_candidate = valid_candidate()
    first = _update(tool, created, candidate=first_candidate)

    from mediasense.plan import PlanPreviewRenderer

    renderer = PlanPreviewRenderer(tool, asset_resolver=lambda ref, view: None)
    first_preview = renderer.build(created["work_ref"], first["revision"])
    revised_candidate = valid_candidate()
    revised_candidate["logical_root"] = "Human-reviewed Hong Kong slice"
    second = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": first["revision"],
            "candidate_content": revised_candidate,
            "request_id": "request:update-after-preview",
        }
    )
    second_preview = renderer.build(created["work_ref"], second["revision"])
    assert first_preview.candidate_content_identity != (
        second_preview.candidate_content_identity
    )
    assert second_preview.logical_root == "Human-reviewed Hong Kong slice"

    request = _seal_request(created, second, second_preview.candidate_content_identity)
    sealed = tool.handle(
        request,
        confirmation=_confirmation(second_preview.candidate_content_identity),
    )
    assert sealed["outcome"] == "ok"
    assert sealed["frozen_plan"]["sealed_content"]["logical_root"] == (
        "Human-reviewed Hong Kong slice"
    )
    assert sealed["content_identity"] == second_preview.candidate_content_identity


def test_seal_idempotency_binds_trusted_confirmation_context(tmp_path) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    request = _seal_request(created, updated, identity)
    first = tool.handle(request, confirmation=_confirmation(identity))
    changed = ConfirmationContext(
        principal_ref="user:another-reviewer",
        confirmed_content_identity=identity,
        confirmed_at=datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc),
    )
    conflict = tool.handle(request, confirmation=changed)
    assert first["outcome"] == "ok"
    assert conflict["error"]["code"] == "idempotency_conflict"


def test_seal_recovers_artifact_written_before_database_close(
    tmp_path, monkeypatch
) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    request = _seal_request(created, updated, identity)
    confirmation = _confirmation(identity)
    original_complete = tool.store.complete_seal

    def interrupted(**kwargs):
        raise RuntimeError("simulated crash after file publication")

    monkeypatch.setattr(tool.store, "complete_seal", interrupted)
    with pytest.raises(RuntimeError, match="simulated crash"):
        tool.handle(request, confirmation=confirmation)
    snapshot = tool.store.snapshot(created["work_ref"])
    assert snapshot.state == "open"
    artifact = tool._publisher.artifact_path(snapshot.plan_ref)
    assert artifact.is_file()

    monkeypatch.setattr(tool.store, "complete_seal", original_complete)
    recovered = tool.handle(request, confirmation=confirmation)
    assert recovered["outcome"] == "ok"
    assert tool.store.snapshot(created["work_ref"]).state == "closed"
    assert list(tool.frozen_dir.glob("*.json")) == [artifact]


def test_conflicting_existing_artifact_refuses_seal_and_keeps_work_open(
    tmp_path,
) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    snapshot = tool.store.snapshot(created["work_ref"])
    artifact = tool._publisher.artifact_path(snapshot.plan_ref)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("{}\n", encoding="utf-8")

    response = tool.handle(
        _seal_request(created, updated, identity),
        confirmation=_confirmation(identity),
    )
    assert response["error"]["code"] == "operation_failed"
    assert tool.store.snapshot(created["work_ref"]).state == "open"
    assert artifact.read_text(encoding="utf-8") == "{}\n"


def test_closed_work_with_corrupted_artifact_refuses_retry(tmp_path) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    request = _seal_request(created, updated, identity)
    confirmation = _confirmation(identity)
    sealed = tool.handle(request, confirmation=confirmation)
    assert sealed["outcome"] == "ok"
    path = Path(tool.store.snapshot(created["work_ref"]).published_path)
    path.write_text("{}\n", encoding="utf-8")

    retry = tool.handle(request, confirmation=confirmation)
    assert retry["error"]["code"] == "operation_failed"


def test_seal_refuses_invalid_principal_and_naive_confirmation_time(tmp_path) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    request = _seal_request(created, updated, identity)
    invalid_principal = ConfirmationContext(
        principal_ref="not-a-ref",
        confirmed_content_identity=identity,
        confirmed_at=datetime(2026, 8, 29, 1, 0, tzinfo=timezone.utc),
    )
    denied = tool.handle(request, confirmation=invalid_principal)
    assert denied["error"]["code"] == "access_denied"

    naive_time = ConfirmationContext(
        principal_ref="user:test-reviewer",
        confirmed_content_identity=identity,
        confirmed_at=datetime(2026, 8, 29, 1, 0),
    )
    denied = tool.handle(request, confirmation=naive_time)
    assert denied["error"]["code"] == "access_denied"


def test_seal_rejects_stale_revision_and_request_identity(tmp_path) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    stale = _seal_request(created, updated, identity)
    stale["revision"] = created["revision"]
    response = tool.handle(stale, confirmation=_confirmation(identity))
    assert response["error"]["code"] == "revision_conflict"

    wrong_identity = _seal_request(created, updated, "sha256:" + "0" * 64)
    response = tool.handle(
        wrong_identity,
        confirmation=_confirmation("sha256:" + "0" * 64),
    )
    assert response["error"]["code"] == "content_identity_mismatch"


def test_second_seal_request_for_same_work_is_refused_while_reserved(
    tmp_path, monkeypatch
) -> None:
    tool, _, created, updated, identity = _prepared_for_seal(tmp_path)
    first_request = _seal_request(created, updated, identity)
    confirmation = _confirmation(identity)
    original_complete = tool.store.complete_seal

    def interrupted(**kwargs):
        raise RuntimeError("leave reservation pending")

    monkeypatch.setattr(tool.store, "complete_seal", interrupted)
    with pytest.raises(RuntimeError, match="leave reservation pending"):
        tool.handle(first_request, confirmation=confirmation)
    monkeypatch.setattr(tool.store, "complete_seal", original_complete)

    second_request = dict(first_request)
    second_request["request_id"] = "request:seal-2"
    response = tool.handle(second_request, confirmation=confirmation)
    assert response["error"]["code"] == "operation_failed"
    assert tool.store.snapshot(created["work_ref"]).state == "open"

    update = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": updated["revision"],
            "candidate_content": valid_candidate(),
            "request_id": "request:update-while-seal-pending",
        }
    )
    assert update["error"]["code"] == "operation_failed"
    assert tool.store.snapshot(created["work_ref"]).revision == updated["revision"]
