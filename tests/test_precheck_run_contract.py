from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource


ROOT = Path(__file__).parents[1]
RUN_SPEC = ROOT / "docs" / "spec" / "spec-260827-1915A-precheck-run"
READ_SPEC = ROOT / "docs" / "spec" / "spec-260826-1546-precheck-read"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _tool() -> dict:
    return _load(RUN_SPEC / "precheck-run.tool.json")


def _mock() -> dict:
    return _load(RUN_SPEC / "lifecycle.mock.json")


def _read_tool() -> dict:
    return _load(READ_SPEC / "precheck-read.tool.json")


def _registry() -> Registry:
    output = _read_tool()["outputSchema"]
    return Registry().with_resource(output["$id"], Resource.from_contents(output))


def _validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    tool = _tool()
    registry = _registry()
    return (
        Draft202012Validator(tool["inputSchema"], registry=registry),
        Draft202012Validator(tool["outputSchema"], registry=registry),
    )


def _result_view(result_ref: str) -> dict:
    mock = _load(READ_SPEC / "hong-kong.mock.json")
    for exchange in mock["exchanges"]:
        result = exchange["response"].get("result", {})
        if result.get("kind") == "result" and result.get("ref") == result_ref:
            return result
    raise AssertionError(f"missing Result view: {result_ref}")


def _review_view(result_ref: str) -> dict:
    mock = _load(READ_SPEC / "hong-kong.mock.json")
    return next(
        exchange["response"]
        for exchange in mock["exchanges"]
        if exchange["request"].get("result_ref") == result_ref
        and exchange["request"].get("operation") == "review"
    )


def _assert_progress_relations(
    progress: dict, *, accounting_total: int | None = None
) -> None:
    accounted = progress["accounted"]
    buckets = [progress["usable"], progress["exceptional"], progress["unresolved"]]
    known_buckets = [value for value in buckets if isinstance(value, int)]
    if isinstance(accounted, int):
        assert sum(known_buckets) <= accounted
        if len(known_buckets) == len(buckets):
            assert sum(known_buckets) == accounted
    discovered = progress["discovered"]
    if isinstance(discovered, int) and isinstance(accounted, int):
        assert accounted <= discovered
    if accounting_total is not None:
        assert accounted == accounting_total


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


def test_schemas_strictly_compile_as_draft_2020_12() -> None:
    tool = _tool()
    assert tool["inputSchema"]["$schema"].endswith("2020-12/schema")
    assert tool["outputSchema"]["$schema"].endswith("2020-12/schema")
    Draft202012Validator.check_schema(tool)
    Draft202012Validator.check_schema(tool["inputSchema"])
    Draft202012Validator.check_schema(tool["outputSchema"])


def test_published_result_axes_match_the_precheck_result_contract() -> None:
    published = _tool()["outputSchema"]["$defs"]["published_result"]["properties"]
    result = _read_tool()["outputSchema"]["$defs"]["result_view"]["properties"]

    assert published["coverage"] == result["coverage"]
    assert published["readiness"] == result["readiness"]
    assert published["integrity"] == {"const": "valid"}
    assert "valid" in result["integrity"]["enum"]


def test_mock_requests_and_responses_conform() -> None:
    input_validator, output_validator = _validators()
    for exchange in _mock()["exchanges"]:
        input_validator.validate(exchange["request"])
        output_validator.validate(exchange["response"])


def test_contract_exposes_only_five_actions() -> None:
    tool = _tool()
    input_defs = tool["inputSchema"]["$defs"]
    assert {
        schema["properties"]["action"]["const"]
        for name, schema in input_defs.items()
        if name.endswith("_request")
    } == {"start", "status", "pause", "resume", "cancel"}
    serialized = json.dumps(tool)
    assert '"reopen"' not in serialized
    assert '"seal"' not in serialized


def test_start_requires_exactly_one_upstream_reference() -> None:
    validator, _ = _validators()
    request = {
        "action": "start",
        "request_id": "request:test",
    }
    with pytest.raises(ValidationError):
        validator.validate(request)
    request["dataset_ref"] = "dataset:a"
    request["prior_result_ref"] = "precheck-result:a"
    with pytest.raises(ValidationError):
        validator.validate(request)


def test_start_requires_safe_retry_identity() -> None:
    validator, _ = _validators()
    request = deepcopy(_mock()["exchanges"][0]["request"])
    request.pop("request_id")
    with pytest.raises(ValidationError):
        validator.validate(request)


def test_scope_inventory_navigation_stays_inside_status() -> None:
    validator, _ = _validators()
    validator.validate(
        {
            "action": "status",
            "run_ref": "precheck-run:test",
            "scope_path": ".",
            "scope_after": ".similarity_cache",
        }
    )
    with pytest.raises(ValidationError):
        validator.validate(
            {
                "action": "status",
                "run_ref": "precheck-run:test",
                "scope_after": ".similarity_cache",
            }
        )


def test_request_id_replay_is_stable_and_conflicts_are_detected() -> None:
    exchange = deepcopy(_mock()["exchanges"][0])
    _assert_request_id_consistency([exchange, deepcopy(exchange)])
    conflict = deepcopy(exchange)
    conflict["request"]["dataset_ref"] = "dataset:other"
    with pytest.raises(ValueError, match="idempotency conflict"):
        _assert_request_id_consistency([exchange, conflict])


def test_control_actions_are_acknowledgements_not_completion_claims() -> None:
    _, output_validator = _validators()
    expected = {
        "pause": "paused",
        "resume": "running",
        "cancel": "cancelled",
    }
    controls = [
        exchange["response"]
        for exchange in _mock()["exchanges"]
        if exchange["request"]["action"] in expected
    ]
    assert controls
    for response in controls:
        output_validator.validate(response)
        assert response["outcome"] == "accepted"
        assert response["target_state"] == expected[response["action"]]
        assert "state" not in response


def test_confirmation_pause_reuses_resume_without_adding_an_action() -> None:
    input_validator, output_validator = _validators()
    input_validator.validate(
        {
            "action": "resume",
            "run_ref": "precheck-run:test",
            "decision": "proceed",
        }
    )
    input_validator.validate(
        {
            "action": "resume",
            "run_ref": "precheck-run:test",
            "decision": "decline",
        }
    )
    input_validator.validate(
        {
            "action": "resume",
            "run_ref": "precheck-run:test",
            "decision": {
                "kind": "source_scope",
                "inventory_fingerprint": "sha256:" + "a" * 64,
                "default_disposition": "include",
                "exceptions": [".similarity_cache"],
            },
        }
    )
    with pytest.raises(ValidationError):
        input_validator.validate(
            {
                "action": "resume",
                "run_ref": "precheck-run:test",
                "decision": "authorize_more",
            }
        )

    paused = deepcopy(_mock()["exchanges"][3]["response"])
    paused["reason"] = {
        "code": "confirmation_required",
        "message": "237 reverse-geocode lookups are ready.",
        "resume_when": "The Human authorizes the exact disclosure or declines it.",
    }
    paused["confirmation"] = {
        "kind": "external_effect",
        "summary": "Reverse-geocode the frozen representative set.",
        "quantity": 237,
        "unit": "logical_queries",
        "skip_allowed": False,
        "content_identity": "sha256:" + "a" * 64,
        "disclosure": {
            "operation": "reverse_geocode",
            "provider_policy": "unknown",
        },
    }
    paused["activity"]["state"] = "waiting"
    output_validator.validate(paused)
    paused.pop("confirmation")
    with pytest.raises(ValidationError):
        output_validator.validate(paused)


def test_status_may_report_an_auditable_scope_selection() -> None:
    _, output_validator = _validators()
    completed = deepcopy(_mock()["exchanges"][5]["response"])
    completed["scope_selection"] = {
        "kind": "source_scope",
        "inventory_fingerprint": "sha256:" + "a" * 64,
        "default_disposition": "include",
        "exceptions": [".similarity_cache"],
        "provenance": "accepted",
    }

    output_validator.validate(completed)


def test_status_state_rules_and_allowed_actions_are_exact() -> None:
    expected = {
        "running": ["pause", "cancel"],
        "paused": ["resume", "cancel"],
        "blocked": ["resume", "cancel"],
        "completed": [],
        "cancelled": [],
        "failed": [],
    }
    _, validator = _validators()
    statuses = [
        exchange["response"]
        for exchange in _mock()["exchanges"]
        if exchange["request"]["action"] == "status"
    ]
    for response in statuses:
        assert set(response["allowed_actions"]) == set(expected[response["state"]])
        reversed_order = deepcopy(response)
        reversed_order["allowed_actions"].reverse()
        validator.validate(reversed_order)

    running = deepcopy(_mock()["exchanges"][1]["response"])
    running["allowed_actions"] = ["pause"]
    with pytest.raises(ValidationError):
        validator.validate(running)
    running["allowed_actions"] = ["pause", "pause"]
    with pytest.raises(ValidationError):
        validator.validate(running)


def test_noncompleted_status_cannot_publish_a_result() -> None:
    _, validator = _validators()
    running = deepcopy(_mock()["exchanges"][1]["response"])
    running["published_result"] = {
        "result_ref": "precheck-result:impossible",
        "coverage": "partial",
        "readiness": "plan_ready",
        "integrity": "valid",
    }
    with pytest.raises(ValidationError):
        validator.validate(running)


def test_completed_status_requires_a_published_result() -> None:
    _, validator = _validators()
    completed = deepcopy(_mock()["exchanges"][5]["response"])
    completed.pop("published_result")
    with pytest.raises(ValidationError):
        validator.validate(completed)

    completed = deepcopy(_mock()["exchanges"][5]["response"])
    completed["progress"]["accounted"] = "unknown"
    with pytest.raises(ValidationError):
        validator.validate(completed)


def test_published_result_matches_existing_result_authority() -> None:
    completed = _mock()["exchanges"][5]["response"]
    published = completed["published_result"]
    result = _result_view(published["result_ref"])
    assert published == {
        "result_ref": result["ref"],
        "coverage": result["coverage"],
        "readiness": result["readiness"],
        "integrity": result["integrity"],
    }
    assert published == {
        "result_ref": "precheck-result:hk-review-slice-002",
        "coverage": "partial",
        "readiness": "plan_ready",
        "integrity": "valid",
    }


def test_published_result_rejects_unknown_status_axis() -> None:
    _, validator = _validators()
    completed = deepcopy(_mock()["exchanges"][5]["response"])
    completed["published_result"]["coverage"] = "mostly_complete"
    with pytest.raises(ValidationError):
        validator.validate(completed)


def test_completed_status_rejects_invalid_result_integrity() -> None:
    _, validator = _validators()
    completed = deepcopy(_mock()["exchanges"][5]["response"])
    completed["published_result"]["integrity"] = "invalid"
    with pytest.raises(ValidationError):
        validator.validate(completed)


def test_completed_status_allows_both_coverage_and_readiness_values() -> None:
    _, validator = _validators()
    completed = deepcopy(_mock()["exchanges"][5]["response"])
    completed["published_result"]["coverage"] = "complete"
    completed["published_result"]["readiness"] = "blocked"
    completed["published_result"]["integrity"] = "valid"
    validator.validate(completed)


def test_completed_progress_matches_result_accounting_closure() -> None:
    completed = _mock()["exchanges"][5]["response"]
    progress = completed["progress"]
    result_ref = completed["published_result"]["result_ref"]
    review = _review_view(result_ref)
    reconciliation = review["reconciliation"]
    total = reconciliation["accounted_total"]
    exceptional = sum(
        route["count"]
        for route in reconciliation["exception_routes"]
        if route["condition"] in {"unsupported", "invalid", "error"}
    )
    unresolved = sum(
        route["count"]
        for route in reconciliation["exception_routes"]
        if route["condition"] == "unresolved"
    )
    usable = total - exceptional - unresolved

    assert progress == {
        "discovered": "unknown",
        "accounted": total,
        "usable": usable,
        "exceptional": exceptional,
        "unresolved": unresolved,
    }
    _assert_progress_relations(progress, accounting_total=total)

    result = _result_view(result_ref)
    assert any(
        item["code"] == "selected_slice_only" for item in result["qualifications"]
    )
    assert progress["discovered"] == "unknown"


def test_accounting_closure_mismatch_is_rejected_semantically() -> None:
    completed = deepcopy(_mock()["exchanges"][5]["response"])
    review = _review_view(completed["published_result"]["result_ref"])
    accounting_total = review["reconciliation"]["accounted_total"]
    completed["progress"]["accounted"] = accounting_total - 1
    with pytest.raises(AssertionError):
        _assert_progress_relations(
            completed["progress"],
            accounting_total=accounting_total,
        )


def test_localized_media_failure_does_not_force_run_failure() -> None:
    completed = _mock()["exchanges"][5]["response"]
    assert completed["state"] == "completed"
    assert completed["progress"]["exceptional"] == 1
    assert completed["activity"]["errors"]["total"] == 1
    assert completed["activity"]["errors"]["by_phase"] == [
        {"phase": "metadata", "count": 1}
    ]
    assert completed["published_result"]["integrity"] == "valid"


def test_prior_result_lineage_derives_the_same_dataset() -> None:
    started = _mock()["exchanges"][6]["response"]
    result = _result_view(started["prior_result_ref"])
    assert started["dataset_ref"] == result["dataset_ref"]


def test_paused_blocked_and_cancelled_have_no_result() -> None:
    statuses = [
        exchange["response"]
        for exchange in _mock()["exchanges"]
        if exchange["request"]["action"] == "status"
    ]
    for response in statuses:
        if response["state"] in {"paused", "blocked", "cancelled"}:
            assert "published_result" not in response
    for response in statuses:
        if response["state"] in {"paused", "blocked"}:
            assert response["reason"]["code"]
            assert response["reason"]["resume_when"]


def test_control_repetition_at_achieved_target_is_schema_valid() -> None:
    _, validator = _validators()
    validator.validate(
        {
            "outcome": "accepted",
            "action": "pause",
            "run_ref": "precheck-run:already-paused",
            "observed_state": "paused",
            "target_state": "paused",
        }
    )
    validator.validate(
        {
            "outcome": "accepted",
            "action": "cancel",
            "run_ref": "precheck-run:already-cancelled",
            "observed_state": "cancelled",
            "target_state": "cancelled",
        }
    )


def test_invalid_transition_has_structured_error_state() -> None:
    _, validator = _validators()
    validator.validate(
        {
            "outcome": "error",
            "action": "resume",
            "run_ref": "precheck-run:completed",
            "error": {
                "code": "invalid_state",
                "message": "A completed Run cannot resume.",
                "current_state": "completed",
                "allowed_actions": [],
            },
        }
    )


def test_failed_status_requires_reason_and_cannot_publish() -> None:
    _, validator = _validators()
    failed = deepcopy(_mock()["exchanges"][5]["response"])
    failed["state"] = "failed"
    failed.pop("published_result")
    failed["reason"] = {
        "code": "result_untrusted",
        "message": "No trustworthy Result can be formed.",
    }
    validator.validate(failed)
    failed.pop("reason")
    with pytest.raises(ValidationError):
        validator.validate(failed)


def test_activity_exposes_bounded_non_percentage_progress() -> None:
    _, validator = _validators()
    running = deepcopy(_mock()["exchanges"][1]["response"])
    activity = running["activity"]

    assert activity["state"] == "working"
    assert activity["phase"] == "metadata"
    assert activity["work"] == {
        "completed": 71,
        "reused": 120,
        "failed": 1,
        "remaining": 1944,
        "total": 2136,
    }
    assert activity["errors"] == {
        "total": 1,
        "by_phase": [{"phase": "metadata", "count": 1}],
        "truncated": False,
    }
    assert set(activity) == {
        "state",
        "phase",
        "work",
        "last_progress_at",
        "errors",
    }
    assert set(activity["work"]) == {
        "completed",
        "reused",
        "failed",
        "remaining",
        "total",
    }

    missing = deepcopy(running)
    missing.pop("activity")
    with pytest.raises(ValidationError):
        validator.validate(missing)

    unknown = deepcopy(running)
    unknown["activity"]["work"]["remaining"] = "unknown"
    unknown["activity"]["work"]["total"] = "unknown"
    validator.validate(unknown)


def test_activity_rejects_private_execution_details_and_unbounded_errors() -> None:
    _, validator = _validators()
    running = deepcopy(_mock()["exchanges"][1]["response"])
    running["activity"]["worker_id"] = "private-worker"
    with pytest.raises(ValidationError):
        validator.validate(running)

    running = deepcopy(_mock()["exchanges"][1]["response"])
    running["activity"]["errors"]["by_phase"] = [
        {"phase": "metadata", "count": 1} for _ in range(6)
    ]
    with pytest.raises(ValidationError):
        validator.validate(running)


def test_internal_storage_and_phase_names_are_not_schema_fields() -> None:
    serialized = json.dumps(_tool()).lower()
    for forbidden in (
        "sqlite",
        "cache_key",
        "checkpoint",
        "directed_evidence_paths",
        '"discovering"',
        '"preparing"',
        '"assembling"',
        '"validating"',
        '"sealing"',
    ):
        assert forbidden not in serialized
