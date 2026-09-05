from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource


ROOT = Path(__file__).parents[1]
WORK_SPEC = ROOT / "docs" / "spec" / "spec-260827-1915B-plan-work"
PLAN_SPEC = ROOT / "docs" / "spec" / "spec-260827-1138-frozen-plan"
READ_SPEC = ROOT / "docs" / "spec" / "spec-260826-1546-precheck-read"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _tool() -> dict:
    return _load(WORK_SPEC / "plan-work.tool.json")


def _mock() -> dict:
    return _load(WORK_SPEC / "hong-kong.mock.json")


def _frozen_schema() -> dict:
    return _load(PLAN_SPEC / "frozen-plan.schema.json")


def _registry() -> Registry:
    frozen = _frozen_schema()
    registry = Registry().with_resource(frozen["$id"], Resource.from_contents(frozen))
    return registry


def _validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    tool = _tool()
    registry = _registry()
    return (
        Draft202012Validator(tool["inputSchema"], registry=registry),
        Draft202012Validator(tool["outputSchema"], registry=registry),
    )


def _result_view(result_ref: str) -> dict:
    precheck = _load(READ_SPEC / "hong-kong.mock.json")
    for exchange in precheck["exchanges"]:
        result = exchange["response"].get("result", {})
        if result.get("kind") == "result" and result.get("ref") == result_ref:
            return result
    raise AssertionError(f"missing Result view: {result_ref}")


def _canonical_strings_json(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_canonical_strings_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                _canonical_strings_json(key) + ":" + _canonical_strings_json(value[key])
                for key in sorted(value)
            )
            + "}"
        )
    raise ValueError("profile permits only objects, arrays, and strings")


def _content_identity(content: dict) -> str:
    canonical = _canonical_strings_json(content).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _assert_create_gate(result: dict) -> None:
    if result["integrity"] != "valid":
        raise ValueError("result is untrusted")
    if result["readiness"] != "plan_ready":
        raise ValueError("result is not ready")


def _assert_revision(base_revision: str, current_revision: str) -> None:
    if base_revision != current_revision:
        raise ValueError("revision conflict")


def _assert_request_id_consistency(exchanges: list[dict]) -> None:
    seen: dict[str, tuple[dict, dict]] = {}
    for exchange in exchanges:
        request_id = exchange["request"].get("request_id")
        if request_id is None:
            continue
        current = (exchange["request"], exchange["response"])
        if request_id in seen and seen[request_id] != current:
            raise ValueError("idempotency conflict")
        seen[request_id] = current


def _assert_confirmation(exchange: dict) -> None:
    try:
        context = exchange["context"]["human_confirmation"]
    except KeyError as error:
        raise ValueError("confirmation required") from error
    request = exchange["request"]
    response = exchange["response"]
    if context["content_identity"] != request["candidate_content_identity"]:
        raise ValueError("confirmation identity mismatch")
    if response["content_identity"] != context["content_identity"]:
        raise ValueError("sealed identity mismatch")


def _updated_preferences(current: dict, request: dict) -> dict:
    if "organization_preferences" not in request:
        return deepcopy(current)
    return deepcopy(request["organization_preferences"])


def _exchanges(action: str) -> list[dict]:
    return [
        exchange
        for exchange in _mock()["exchanges"]
        if exchange["request"]["action"] == action
    ]


def test_schemas_strictly_compile_as_draft_2020_12() -> None:
    tool = _tool()
    assert tool["inputSchema"]["$schema"].endswith("2020-12/schema")
    assert tool["outputSchema"]["$schema"].endswith("2020-12/schema")
    Draft202012Validator.check_schema(tool)
    Draft202012Validator.check_schema(tool["inputSchema"])
    Draft202012Validator.check_schema(tool["outputSchema"])


def test_mock_requests_and_responses_conform() -> None:
    input_validator, output_validator = _validators()
    for exchange in _mock()["exchanges"]:
        input_validator.validate(exchange["request"])
        output_validator.validate(exchange["response"])


def test_contract_exposes_only_five_actions() -> None:
    input_defs = _tool()["inputSchema"]["$defs"]
    assert {
        schema["properties"]["action"]["const"]
        for name, schema in input_defs.items()
        if name.endswith("_request") and "action" in schema.get("properties", {})
    } == {"create", "update", "inspect", "seal"}
    serialized = json.dumps(_tool())
    for forbidden in ('"preview"', '"validate"', '"confirm"'):
        assert forbidden not in serialized


def test_create_accepts_partial_plan_ready_valid_result() -> None:
    create = _exchanges("create")[0]
    result = _result_view(create["request"]["result_ref"])
    assert result["coverage"] == "partial"
    _assert_create_gate(result)


def test_create_rejects_blocked_or_invalid_result() -> None:
    result = _result_view("precheck-result:hk-review-slice-002")
    blocked = deepcopy(result)
    blocked["readiness"] = "blocked"
    with pytest.raises(ValueError, match="not ready"):
        _assert_create_gate(blocked)
    invalid = deepcopy(result)
    invalid["integrity"] = "invalid"
    with pytest.raises(ValueError, match="untrusted"):
        _assert_create_gate(invalid)


def test_preferences_are_preserved_in_the_working_state() -> None:
    create = _exchanges("create")[0]
    update = _exchanges("update")[0]
    inspect = _exchanges("inspect")[0]
    assert (
        create["request"]["organization_preferences"]
        == create["response"]["organization_preferences"]
    )
    assert "organization_preferences" not in update["request"]
    assert (
        _updated_preferences(
            create["response"]["organization_preferences"],
            update["request"],
        )
        == create["response"]["organization_preferences"]
    )
    assert (
        create["response"]["organization_preferences"]
        == inspect["response"]["sections"]["preferences"]
    )


def test_preference_object_replaces_and_empty_object_clears_snapshot() -> None:
    validator, _ = _validators()
    current = _exchanges("create")[0]["response"]["organization_preferences"]
    update = deepcopy(_exchanges("update")[0]["request"])

    update["organization_preferences"] = {"maximum_depth": 2}
    validator.validate(update)
    assert _updated_preferences(current, update) == {"maximum_depth": 2}

    update["organization_preferences"] = {}
    validator.validate(update)
    assert _updated_preferences(current, update) == {}
    assert _mock()["organization_preference_semantics"] == {
        "omitted_on_update": "preserve_current_snapshot",
        "object_on_update": "replace_entire_snapshot",
        "empty_object_on_update": "replace_with_no_preferences",
    }


def test_update_requires_full_candidate_and_base_revision() -> None:
    validator, _ = _validators()
    update = deepcopy(_exchanges("update")[0]["request"])
    update.pop("candidate_content")
    with pytest.raises(ValidationError):
        validator.validate(update)


def test_update_candidate_reuses_frozen_plan_path_rules() -> None:
    validator, _ = _validators()
    update = deepcopy(_exchanges("update")[0]["request"])
    update["candidate_content"]["logical_root"] = "bad/root"
    with pytest.raises(ValidationError):
        validator.validate(update)
    update = deepcopy(_exchanges("update")[0]["request"])
    update.pop("base_revision")
    with pytest.raises(ValidationError):
        validator.validate(update)
    update = deepcopy(_exchanges("update")[0]["request"])
    update["changes"] = []
    with pytest.raises(ValidationError):
        validator.validate(update)


def test_stale_revision_is_a_conflict_not_an_overwrite() -> None:
    update = _exchanges("update")[0]
    _assert_revision(
        update["request"]["base_revision"],
        "work-revision:hk-001",
    )
    with pytest.raises(ValueError, match="revision conflict"):
        _assert_revision(
            update["request"]["base_revision"],
            "work-revision:newer",
        )


def test_update_materializes_the_exact_sealable_content() -> None:
    candidate = deepcopy(_exchanges("update")[0]["request"]["candidate_content"])
    inspected = _exchanges("inspect")[0]["response"]["sections"]["content"]["value"]
    expected = {
        "contract": "mediasense.frozen-plan",
        "plan_ref": "frozen-plan:hk-review-slice-reference-001",
        **candidate,
    }
    assert inspected == expected


def test_inspect_without_revision_returns_an_exact_revision() -> None:
    inspect = _exchanges("inspect")[0]
    assert "revision" not in inspect["request"]
    assert inspect["response"]["revision"] == "work-revision:hk-002"


def test_paged_content_keeps_one_revision_and_global_identity() -> None:
    complete = _exchanges("inspect")[0]["response"]
    pages = [
        exchange for exchange in _exchanges("inspect") if "page" in exchange["request"]
    ]
    assert len(pages) == 2
    for exchange in _exchanges("inspect"):
        response = exchange["response"]
        assert set(response["returned_sections"]) == set(response["sections"])
    expected_groups = complete["sections"]["content"]["value"]["groups"]
    returned_groups = [
        item
        for exchange in pages
        for item in exchange["response"]["sections"]["content"]["items"]
    ]
    assert returned_groups == expected_groups
    assert (
        pages[0]["response"]["sections"]["content"]["page"]["next_cursor"]
        == pages[1]["request"]["page"]["cursor"]
    )
    identities = {
        complete["candidate_content_identity"],
        *(exchange["response"]["candidate_content_identity"] for exchange in pages),
    }
    revisions = {
        complete["revision"],
        *(exchange["response"]["revision"] for exchange in pages),
    }
    assert len(identities) == 1
    assert revisions == {"work-revision:hk-002"}


def test_page_from_another_revision_is_detectably_invalid() -> None:
    pages = [
        exchange for exchange in _exchanges("inspect") if "page" in exchange["request"]
    ]
    second = deepcopy(pages[1])
    second["response"]["revision"] = "work-revision:other"
    expected_revision = pages[0]["response"]["revision"]
    with pytest.raises(ValueError, match="revision conflict"):
        _assert_revision(second["response"]["revision"], expected_revision)


def test_candidate_identity_covers_reserved_plan_ref_and_complete_content() -> None:
    inspect = _exchanges("inspect")[0]["response"]
    content = inspect["sections"]["content"]["value"]
    assert content["plan_ref"] == "frozen-plan:hk-review-slice-reference-001"
    assert _content_identity(content) == inspect["candidate_content_identity"]


def test_seal_request_cannot_self_report_confirmation_identity() -> None:
    validator, _ = _validators()
    request = deepcopy(_exchanges("seal")[0]["request"])
    request["confirmed_by"] = "user:self-reported"
    with pytest.raises(ValidationError):
        validator.validate(request)


def test_seal_binds_trusted_context_to_exact_candidate() -> None:
    exchange = _exchanges("seal")[0]
    _assert_confirmation(exchange)
    context = exchange["context"]["human_confirmation"]
    response = exchange["response"]
    assert (
        context["content_identity"] == exchange["request"]["candidate_content_identity"]
    )
    assert response["content_identity"] == context["content_identity"]
    assert response["frozen_plan"]["seal"]["final_confirmation"] == {
        "confirmed_content_identity": context["content_identity"],
        "confirmed_at": "2026-08-27T11:38:00+08:00",
        "confirmed_by": context["principal_ref"],
    }


def test_seal_rejects_confirmation_for_another_identity() -> None:
    exchange = deepcopy(_exchanges("seal")[0])
    exchange["context"]["human_confirmation"]["content_identity"] = "sha256:" + "0" * 64
    with pytest.raises(ValueError, match="confirmation identity mismatch"):
        _assert_confirmation(exchange)


def test_seal_rejects_missing_confirmation_context() -> None:
    exchange = deepcopy(_exchanges("seal")[0])
    exchange.pop("context")
    with pytest.raises(ValueError, match="confirmation required"):
        _assert_confirmation(exchange)


def test_seal_returns_the_existing_conforming_frozen_plan() -> None:
    response = _exchanges("seal")[0]["response"]
    frozen = _load(PLAN_SPEC / "hong-kong.mock.json")["frozen_plan"]
    Draft202012Validator(_frozen_schema(), registry=_registry()).validate(
        response["frozen_plan"]
    )
    assert response["frozen_plan"] == frozen
    assert response["plan_ref"] == frozen["sealed_content"]["plan_ref"]
    assert response["content_identity"] == frozen["seal"]["content_identity"]


def test_identical_seal_retry_returns_the_same_artifact() -> None:
    seals = _exchanges("seal")
    assert len(seals) == 2
    assert seals[0] == seals[1]
    _assert_request_id_consistency(seals)


def test_request_id_reuse_with_different_input_is_rejected() -> None:
    seal = deepcopy(_exchanges("seal")[0])
    conflict = deepcopy(seal)
    conflict["request"]["revision"] = "work-revision:other"
    with pytest.raises(ValueError, match="idempotency conflict"):
        _assert_request_id_consistency([seal, conflict])


def test_closed_work_rejects_update() -> None:
    exchange = _exchanges("update")[-1]
    assert exchange["response"]["outcome"] == "error"
    assert exchange["response"]["error"]["code"] == "work_closed"


def test_invalid_candidate_has_no_sealable_identity() -> None:
    _, validator = _validators()
    inspect = deepcopy(_exchanges("inspect")[0]["response"])
    inspect["sections"]["validation"] = {
        "seal_ready": False,
        "issues": [
            {
                "code": "scope_incomplete",
                "severity": "error",
                "message": "One scoped item has no outcome.",
            }
        ],
    }
    with pytest.raises(ValidationError):
        validator.validate(inspect)
