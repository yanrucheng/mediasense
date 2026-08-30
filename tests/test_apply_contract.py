from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from mediasense.frozen_plan import load_frozen_plan_validator, validate_frozen_plan


ROOT = Path(__file__).parents[1]
APPLY_SPEC = ROOT / "docs" / "spec" / "spec-260829-0050-apply"
PLAN_EXAMPLE = (
    ROOT
    / "docs"
    / "design"
    / "design-260828-2043-plan-local-artifacts"
    / "example-plan.json"
)
FROZEN_PLAN_SCHEMA = (
    ROOT
    / "docs"
    / "spec"
    / "spec-260827-1138-frozen-plan"
    / "frozen-plan.schema.json"
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _run_tool() -> dict:
    return _load(APPLY_SPEC / "apply-run.tool.json")


def _read_tool() -> dict:
    return _load(APPLY_SPEC / "apply-read.tool.json")


def _receipt_schema() -> dict:
    return _load(APPLY_SPEC / "apply-receipt.schema.json")


def _receipt() -> dict:
    return _load(APPLY_SPEC / "receipt.mock.json")


def _run_input_validator() -> Draft202012Validator:
    frozen = _load(FROZEN_PLAN_SCHEMA)
    registry = Registry().with_resource(frozen["$id"], Resource.from_contents(frozen))
    return Draft202012Validator(_run_tool()["inputSchema"], registry=registry)


def _canonical_identity(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _discrepancy_set_identity(discrepancies: list[dict]) -> str:
    canonical_facts = [
        {
            "discrepancy_ref": item["discrepancy_ref"],
            "source_item_ref": item["source_item_ref"],
            "attribute": item["attribute"],
            "expected": item["expected"],
            "observed": item["observed"],
        }
        for item in discrepancies
    ]
    return _canonical_identity(canonical_facts)


def _assert_receipt_semantics(receipt: dict) -> None:
    content = receipt["sealed_content"]
    if content["execution_binding"]["kind"] == "forward":
        source_root_refs = [
            root["source_root_ref"]
            for root in content["execution_binding"]["source_roots"]
        ]
        assert len(source_root_refs) == len(set(source_root_refs))

    operations = content["operation_ledger"]["items"]
    operation_by_ref = {item["source_item_ref"]: item for item in operations}
    assert len(operation_by_ref) == len(operations)

    preservation = content["metadata_preservation"]
    discrepancies = preservation["unpreserved_attributes"]
    discrepancy_by_ref = {item["discrepancy_ref"]: item for item in discrepancies}
    assert len(discrepancy_by_ref) == len(discrepancies)
    accepted_refs = set(preservation["accepted_discrepancy_refs"])
    assert accepted_refs <= set(discrepancy_by_ref)

    authorized_refs: set[str] = set()
    for authorization in preservation["discrepancy_authorizations"]:
        refs = authorization["accepted_discrepancy_refs"]
        authorized_facts = [discrepancy_by_ref[ref] for ref in refs]
        assert authorization[
            "confirmed_discrepancy_set_identity"
        ] == _discrepancy_set_identity(authorized_facts)
        assert not authorized_refs.intersection(refs)
        authorized_refs.update(refs)
    assert authorized_refs == accepted_refs

    for discrepancy in discrepancies:
        operation = operation_by_ref[discrepancy["source_item_ref"]]
        if discrepancy["discrepancy_ref"] not in accepted_refs:
            assert operation["source_after"] == "present"
            assert operation["result"] != "completed_and_verified"

    if content["preflight"]["execution_route"] == "verified_cross_filesystem_transfer":
        for operation in operations:
            if operation["source_after"] == "absent":
                assert (
                    operation["verification"]["profile"]
                    == "cross_filesystem_content_and_metadata"
                )
                assert operation["verification"]["result"] == "verified"

    if content["completion"] == "complete":
        assert all(
            operation["result"] == "completed_and_verified"
            and operation["source_verification"]["result"] == "matched"
            and operation["verification"]["result"] == "verified"
            for operation in operations
        )
        assert preservation["content_verification"]["result"] == "verified"


def test_active_schemas_compile() -> None:
    for schema in (_run_tool(), _read_tool(), _receipt_schema()):
        Draft202012Validator.check_schema(schema)
    Draft202012Validator.check_schema(_run_tool()["inputSchema"])
    Draft202012Validator.check_schema(_run_tool()["outputSchema"])
    Draft202012Validator.check_schema(_read_tool()["inputSchema"])
    Draft202012Validator.check_schema(_read_tool()["outputSchema"])


def test_run_lifecycle_mock_conforms() -> None:
    tool = _run_tool()
    inputs = _run_input_validator()
    outputs = Draft202012Validator(tool["outputSchema"])
    mock = _load(APPLY_SPEC / "lifecycle.mock.json")
    for exchange in mock["exchanges"]:
        inputs.validate(exchange["request"])
        outputs.validate(exchange["response"])
    forward_plan = mock["exchanges"][0]["request"]["forward"]["frozen_plan"]
    validate_frozen_plan(
        forward_plan,
        validator=load_frozen_plan_validator(FROZEN_PLAN_SCHEMA),
    )


def test_run_contract_exposes_only_six_actions() -> None:
    tool = _run_tool()
    actions = {
        schema["properties"]["action"]["const"]
        for name, schema in tool["inputSchema"]["$defs"].items()
        if name.endswith("_request")
    }
    assert actions == {"prepare", "status", "execute", "pause", "resume", "cancel"}
    serialized = json.dumps(tool)
    assert "prepare_rewind" not in serialized
    assert "close_incomplete" not in serialized
    assert "confirmed_by" not in serialized


def test_prepare_requires_exactly_one_direction_source() -> None:
    validator = _run_input_validator()
    request = {
        "action": "prepare",
        "request_id": "request:test",
    }
    with pytest.raises(ValidationError):
        validator.validate(request)
    request["forward"] = {
        "frozen_plan": _load(PLAN_EXAMPLE),
        "effect": "move_originals",
        "current_source_roots": [
            {"source_root_ref": "source-root:test", "current_root": "/source"}
        ],
        "destination_parent": "/destination",
    }
    request["rewind"] = {"receipt_ref": "apply-receipt:test"}
    with pytest.raises(ValidationError):
        validator.validate(request)


def test_execute_binds_exact_prepared_content_and_retry_identity() -> None:
    validator = _run_input_validator()
    request = {
        "action": "execute",
        "run_ref": "apply-run:test",
        "prepared_revision": "revision:1",
        "prepared_content_identity": "sha256:test",
        "request_id": "request:execute-test",
    }
    validator.validate(request)
    for required in ("prepared_revision", "prepared_content_identity", "request_id"):
        invalid = deepcopy(request)
        invalid.pop(required)
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_prepare_forward_and_rewind_shapes_are_strict() -> None:
    validator = _run_input_validator()
    forward = {
        "action": "prepare",
        "request_id": "request:forward",
        "forward": {
            "frozen_plan": _load(PLAN_EXAMPLE),
            "effect": "move_originals",
            "current_source_roots": [
                {"source_root_ref": "source-root:test", "current_root": "/source"}
            ],
            "destination_parent": "/destination",
        },
    }
    rewind = {
        "action": "prepare",
        "request_id": "request:rewind",
        "rewind": {"receipt_ref": "apply-receipt:test"},
    }
    validator.validate(forward)
    validator.validate(rewind)
    for deferred_effect in ("copy_originals", "create_relative_symlinks"):
        invalid = deepcopy(forward)
        invalid["forward"]["effect"] = deferred_effect
        with pytest.raises(ValidationError):
            validator.validate(invalid)


def test_control_acknowledgement_does_not_claim_completion() -> None:
    tool = _run_tool()
    validator = Draft202012Validator(tool["outputSchema"])
    response = {
        "outcome": "accepted",
        "action": "pause",
        "run_ref": "apply-run:test",
        "observed_state": "executing",
        "target_state": "paused",
    }
    validator.validate(response)
    response["state"] = "paused"
    with pytest.raises(ValidationError):
        validator.validate(response)

    wrong_target = {
        "outcome": "accepted",
        "action": "execute",
        "run_ref": "apply-run:test",
        "observed_state": "ready_for_authorization",
        "target_state": "cancelled",
    }
    with pytest.raises(ValidationError):
        validator.validate(wrong_target)


def test_closed_status_requires_receipt_and_cancelled_requires_zero_effect_proof() -> (
    None
):
    validator = Draft202012Validator(_run_tool()["outputSchema"])
    base = {
        "outcome": "ok",
        "action": "status",
        "run_ref": "apply-run:test",
        "state": "closed",
        "progress": {
            "planned_operations": 1,
            "completed_and_verified": 1,
            "failed": 0,
            "remaining": 0,
            "indeterminate": 0,
        },
        "allowed_actions": [],
    }
    with pytest.raises(ValidationError):
        validator.validate(base)
    cancelled = deepcopy(base)
    cancelled["state"] = "cancelled"
    cancelled["progress"]["completed_and_verified"] = 0
    cancelled["progress"]["remaining"] = 1
    with pytest.raises(ValidationError):
        validator.validate(cancelled)
    cancelled["guaranteed_zero_media_effects"] = True
    validator.validate(cancelled)


def test_status_progress_and_allowed_actions_are_truthful() -> None:
    mock = _load(APPLY_SPEC / "lifecycle.mock.json")
    statuses = [
        exchange["response"]
        for exchange in mock["exchanges"]
        if exchange["request"]["action"] == "status"
    ]
    expected_actions = {
        "ready_for_authorization": {"execute", "cancel"},
        "needs_attention": {"resume", "cancel"},
        "closed": set(),
    }
    for status in statuses:
        progress = status["progress"]
        values = [
            progress[k]
            for k in ("completed_and_verified", "failed", "remaining", "indeterminate")
        ]
        if all(
            isinstance(value, int)
            for value in values + [progress["planned_operations"]]
        ):
            assert sum(values) == progress["planned_operations"]
        assert set(status["allowed_actions"]) == expected_actions[status["state"]]
    closed = next(status for status in statuses if status["state"] == "closed")
    assert closed["published_receipt"]["receipt_ref"] == "apply-receipt:example-001"

    invalid = deepcopy(closed)
    invalid["allowed_actions"] = ["pause", "cancel"]
    with pytest.raises(ValidationError):
        Draft202012Validator(_run_tool()["outputSchema"]).validate(invalid)


def test_metadata_loss_requires_a_new_execute_authorization_boundary() -> None:
    validator = Draft202012Validator(_run_tool()["outputSchema"])
    discrepancies = [
        {
            "discrepancy_ref": "metadata-discrepancy:item-13-finder-tags",
            "source_item_ref": "source-item:13",
            "attribute": "finder_tags",
            "expected": ["Family"],
            "observed": [],
        }
    ]
    status = {
        "outcome": "ok",
        "action": "status",
        "run_ref": "apply-run:test",
        "state": "needs_attention",
        "prepared_revision": "revision:metadata-loss-1",
        "prepared_content_identity": "sha256:metadata-loss-1",
        "progress": {
            "planned_operations": 1,
            "completed_and_verified": 0,
            "failed": 0,
            "remaining": 1,
            "indeterminate": 0,
        },
        "reasons": [
            {
                "code": "metadata_preservation_loss_requires_authorization",
                "message": "Source deletion is blocked until the exact Finder tag loss is authorized.",
            }
        ],
        "metadata_loss_authorization": {
            "profile": "cross_filesystem_user_metadata_v1",
            "discrepancy_set_identity": _discrepancy_set_identity(discrepancies),
            "discrepancy_count": 1,
            "source_deletion_blocked": True,
            "disclosure": {
                "ref": "apply-run-disclosure:metadata-loss-test",
                "content_identity": _discrepancy_set_identity(discrepancies),
                "item_count": 1,
                "coverage": "complete_discrepancy_set",
                "access": "bounded_human_obtainable",
            },
        },
        "allowed_actions": ["execute", "cancel"],
    }
    validator.validate(status)

    unsafe_resume = deepcopy(status)
    unsafe_resume["allowed_actions"] = ["resume", "cancel"]
    with pytest.raises(ValidationError):
        validator.validate(unsafe_resume)

    file_coupled = deepcopy(status)
    file_coupled["metadata_loss_authorization"]["disclosure"]["path"] = (
        "/tmp/losses.json"
    )
    with pytest.raises(ValidationError):
        validator.validate(file_coupled)


def test_receipt_mock_conforms_and_accounting_closes() -> None:
    receipt = _receipt()
    Draft202012Validator(_receipt_schema()).validate(receipt)
    content = receipt["sealed_content"]
    accounting = content["accounting"]
    assert (
        sum(
            accounting[key]
            for key in (
                "completed_and_verified",
                "failed",
                "refused",
                "not_attempted",
                "indeterminate",
            )
        )
        == accounting["materialization_operations"]
    )
    assert (
        accounting["materialization_operations"]
        + accounting["retained_without_effect"]
        + accounting["excluded_without_effect"]
        == accounting["plan_scope_items"]
    )
    assert content["completion"] == "complete"
    assert content["closure"] == "automatic"
    assert (
        accounting["completed_and_verified"] == accounting["materialization_operations"]
    )
    assert (
        content["authorization"]["confirmed_prepared_content_identity"]
        == content["prepared_content_identity"]
    )
    assert content["preflight"]["source_compatibility"] == "verified"
    assert content["preflight"]["target_binding"] == "verified"
    assert content["preflight"]["target_collisions"] == 0
    assert content["preflight"]["blockers"] == 0
    _assert_receipt_semantics(receipt)

    failed_receipt = deepcopy(receipt)
    failed_receipt["sealed_content"]["completion"] = "failed"
    with pytest.raises(ValidationError):
        Draft202012Validator(_receipt_schema()).validate(failed_receipt)

    incomplete = deepcopy(receipt)
    incomplete["sealed_content"]["completion"] = "incomplete"
    with pytest.raises(ValidationError):
        Draft202012Validator(_receipt_schema()).validate(incomplete)
    incomplete["sealed_content"]["closure"] = "human_cancelled"
    Draft202012Validator(_receipt_schema()).validate(incomplete)


def test_unaccepted_metadata_loss_keeps_source_and_receipt_incomplete() -> None:
    receipt = _receipt()
    content = receipt["sealed_content"]
    content["preflight"]["execution_route"] = "verified_cross_filesystem_transfer"
    discrepancy = {
        "discrepancy_ref": "metadata-discrepancy:item-13-finder-tags",
        "source_item_ref": "source-item:13",
        "attribute": "finder_tags",
        "expected": ["Family"],
        "observed": [],
    }
    content["metadata_preservation"] = {
        "profile": "cross_filesystem_user_metadata_v1",
        "content_verification": {"profile": "byte_for_byte", "result": "verified"},
        "checked_attributes": [
            "timestamps",
            "permissions",
            "extended_attributes",
            "finder_tags",
        ],
        "unpreserved_attributes": [discrepancy],
        "accepted_discrepancy_refs": [],
        "discrepancy_authorizations": [],
    }
    for item in content["operation_ledger"]["items"]:
        item["verification"] = {
            "profile": "cross_filesystem_content_and_metadata",
            "result": "verified",
            "basis": "Target bytes matched and declared user-relevant attributes were checked.",
        }

    unsafe = deepcopy(receipt)
    with pytest.raises(AssertionError):
        _assert_receipt_semantics(unsafe)

    operation = next(
        item
        for item in content["operation_ledger"]["items"]
        if item["source_item_ref"] == discrepancy["source_item_ref"]
    )
    operation.update(
        {
            "result": "refused",
            "source_after": "present",
            "target_after": "absent",
            "verification": {
                "profile": "cross_filesystem_content_and_metadata",
                "result": "failed",
                "basis": "Content matched, but Finder tags were not preserved; source deletion was refused.",
            },
        }
    )
    content["completion"] = "incomplete"
    content["closure"] = "human_cancelled"
    content["accounting"]["completed_and_verified"] = 6
    content["accounting"]["refused"] = 1
    content["verification"]["planned_targets_present"] = 6
    content["verification"]["original_locations_absent"] = 6
    content["verification"]["unverified_items"] = 1
    Draft202012Validator(_receipt_schema()).validate(receipt)
    _assert_receipt_semantics(receipt)


def test_accepted_metadata_loss_records_exact_reauthorization() -> None:
    receipt = _receipt()
    content = receipt["sealed_content"]
    content["preflight"]["execution_route"] = "verified_cross_filesystem_transfer"
    discrepancy = {
        "discrepancy_ref": "metadata-discrepancy:item-13-finder-tags",
        "source_item_ref": "source-item:13",
        "attribute": "finder_tags",
        "expected": ["Family"],
        "observed": [],
    }
    authorization_ref = "authorization:metadata-loss-item-13"
    content["metadata_preservation"] = {
        "profile": "cross_filesystem_user_metadata_v1",
        "content_verification": {"profile": "byte_for_byte", "result": "verified"},
        "checked_attributes": [
            "timestamps",
            "permissions",
            "extended_attributes",
            "finder_tags",
        ],
        "unpreserved_attributes": [discrepancy],
        "accepted_discrepancy_refs": [discrepancy["discrepancy_ref"]],
        "discrepancy_authorizations": [
            {
                "authorization_ref": authorization_ref,
                "binding": "illustrative:trusted-human-confirmation-metadata-loss",
                "confirmed_prepared_content_identity": "sha256:metadata-loss-prepared-content",
                "confirmed_discrepancy_set_identity": _discrepancy_set_identity(
                    [discrepancy]
                ),
                "accepted_discrepancy_refs": [discrepancy["discrepancy_ref"]],
                "confirmed_at": "2026-08-29T00:41:00+08:00",
            }
        ],
    }
    for item in content["operation_ledger"]["items"]:
        item["verification"] = {
            "profile": "cross_filesystem_content_and_metadata",
            "result": "verified",
            "basis": "Target bytes matched and any accepted metadata discrepancy is separately bound.",
        }
    Draft202012Validator(_receipt_schema()).validate(receipt)
    _assert_receipt_semantics(receipt)
    assert (
        content["metadata_preservation"]["discrepancy_authorizations"][0][
            "authorization_ref"
        ]
        == authorization_ref
    )

    changed_loss_set = deepcopy(receipt)
    changed_loss_set["sealed_content"]["metadata_preservation"][
        "unpreserved_attributes"
    ][0]["observed"] = ["Travel"]
    with pytest.raises(AssertionError):
        _assert_receipt_semantics(changed_loss_set)

    wrong_content_profile = deepcopy(receipt)
    wrong_content_profile["sealed_content"]["metadata_preservation"][
        "content_verification"
    ]["profile"] = "filesystem_identity_and_location"
    with pytest.raises(ValidationError):
        Draft202012Validator(_receipt_schema()).validate(wrong_content_profile)


def test_inline_operation_ledger_exactly_covers_frozen_plan_scope_and_targets() -> None:
    receipt = _receipt()["sealed_content"]
    plan = _load(PLAN_EXAMPLE)["sealed_content"]
    operations = receipt["operation_ledger"]["items"]
    operation_by_ref = {item["source_item_ref"]: item for item in operations}
    assert len(operation_by_ref) == len(operations)
    assert set(operation_by_ref) == set(plan["scope"]["source_item_refs"])

    expected_targets = {}
    for group in plan["groups"]:
        overrides = {
            item["source_item_ref"]: item["name"]
            for item in group["source_naming"].get("overrides", [])
        }
        for source_item_ref in group["members"]["source_item_refs"]:
            operation = operation_by_ref[source_item_ref]
            name = overrides.get(source_item_ref, Path(operation["source_before"]).name)
            expected_targets[source_item_ref] = str(
                Path(receipt["execution_binding"]["destination"]["parent"])
                / plan["logical_root"]
                / Path(*group["relative_path"])
                / name
            )
    assert {
        ref: operation["intended_target"] for ref, operation in operation_by_ref.items()
    } == expected_targets
    if receipt["completion"] == "complete":
        assert all(
            operation["result"] == "completed_and_verified"
            and operation["source_verification"]["result"] == "matched"
            and operation["verification"]["result"] == "verified"
            for operation in operations
        )


def test_forward_source_root_refs_are_unique() -> None:
    receipt = _receipt()
    roots = receipt["sealed_content"]["execution_binding"]["source_roots"]
    refs = [root["source_root_ref"] for root in roots]
    assert len(refs) == len(set(refs))
    _assert_receipt_semantics(receipt)

    duplicate_ref = deepcopy(receipt)
    duplicate_ref["sealed_content"]["execution_binding"]["source_roots"].append(
        {
            "source_root_ref": roots[0]["source_root_ref"],
            "current_root": "/Volumes/SecondSource",
            "observed_identity": "illustrative:volume-second-source",
        }
    )
    with pytest.raises(AssertionError):
        _assert_receipt_semantics(duplicate_ref)


def test_receipt_content_identity_matches_canonical_content() -> None:
    receipt = _receipt()
    assert receipt["seal"]["content_identity"] == _canonical_identity(
        receipt["sealed_content"]
    )


def test_read_mock_conforms_and_pages_are_bounded() -> None:
    tool = _read_tool()
    inputs = Draft202012Validator(tool["inputSchema"])
    outputs = Draft202012Validator(tool["outputSchema"])
    mock = _load(APPLY_SPEC / "read.mock.json")
    for exchange in mock["exchanges"]:
        inputs.validate(exchange["request"])
        outputs.validate(exchange["response"])
        response = exchange["response"]
        if response["outcome"] == "ok" and response["action"] == "traverse":
            page = response["page"]
            assert page["returned"] == len(response["items"])
            assert page["complete"] == ("next_cursor" not in page)


def test_read_sections_cannot_return_the_wrong_item_shape() -> None:
    tool = _read_tool()
    validator = Draft202012Validator(tool["outputSchema"])
    mock = _load(APPLY_SPEC / "read.mock.json")
    directory_page = deepcopy(mock["exchanges"][2]["response"])
    directory_page["items"] = deepcopy(mock["exchanges"][1]["response"]["items"])
    with pytest.raises(ValidationError):
        validator.validate(directory_page)


def test_read_metadata_discrepancy_exposes_acceptance_binding() -> None:
    input_validator = Draft202012Validator(_read_tool()["inputSchema"])
    request = {
        "receipt_ref": "apply-receipt:test",
        "action": "traverse",
        "section": "metadata_discrepancies",
        "filter": {"source_item_ref": "source-item:13"},
    }
    input_validator.validate(request)
    invalid_filter = deepcopy(request)
    invalid_filter["filter"]["result"] = "completed_and_verified"
    with pytest.raises(ValidationError):
        input_validator.validate(invalid_filter)

    validator = Draft202012Validator(_read_tool()["outputSchema"])
    response = {
        "outcome": "ok",
        "action": "traverse",
        "receipt_ref": "apply-receipt:test",
        "section": "metadata_discrepancies",
        "items": [
            {
                "discrepancy_ref": "metadata-discrepancy:item-13-finder-tags",
                "source_item_ref": "source-item:13",
                "attribute": "finder_tags",
                "expected": ["Family"],
                "observed": [],
                "accepted": True,
                "authorization_ref": "authorization:metadata-loss-item-13",
            }
        ],
        "page": {"returned": 1, "total": 1, "complete": True},
    }
    validator.validate(response)

    missing_authorization = deepcopy(response)
    missing_authorization["items"][0].pop("authorization_ref")
    with pytest.raises(ValidationError):
        validator.validate(missing_authorization)


def test_read_summary_matches_receipt() -> None:
    receipt = _receipt()["sealed_content"]
    read = _load(APPLY_SPEC / "read.mock.json")
    summary = read["exchanges"][0]["response"]["receipt"]
    assert summary["receipt_ref"] == receipt["receipt_ref"]
    assert summary["run_ref"] == receipt["run_ref"]
    assert summary["frozen_plan_ref"] == receipt["frozen_plan_ref"]
    assert summary["completion"] == receipt["completion"]
    assert summary["closure"] == receipt["closure"]
    assert summary["execution_binding"]["kind"] == receipt["execution_binding"]["kind"]
    assert summary["accounting"] == receipt["accounting"]
    assert (
        summary["metadata_preservation"]["profile"]
        == receipt["metadata_preservation"]["profile"]
    )
    assert (
        summary["metadata_preservation"]["content_verification_result"]
        == receipt["metadata_preservation"]["content_verification"]["result"]
    )
    assert summary["metadata_preservation"]["unpreserved_attribute_count"] == len(
        receipt["metadata_preservation"]["unpreserved_attributes"]
    )
    assert summary["metadata_preservation"]["accepted_discrepancy_count"] == len(
        receipt["metadata_preservation"]["accepted_discrepancy_refs"]
    )
