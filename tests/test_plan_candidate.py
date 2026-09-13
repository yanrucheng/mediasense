from __future__ import annotations

from copy import deepcopy
import json

from mediasense.frozen_plan import content_identity, load_frozen_content_validator
from mediasense.plan._candidate import (
    analyze_candidate,
    materialize_candidate,
)

from _plan_support import MockPrecheckReader, PLAN_SPEC, valid_candidate


RESULT_REF = "precheck-result:hk-review-slice-002"
PLAN_REF = "frozen-plan:hk-review-slice-reference-001"
FROZEN_CONTENT_VALIDATOR = load_frozen_content_validator()


def _analyze(candidate):
    return analyze_candidate(
        candidate,
        result_ref=RESULT_REF,
        plan_ref=PLAN_REF,
        reader=MockPrecheckReader(),
        schema_validator=FROZEN_CONTENT_VALIDATOR,
    )


def test_mock_candidate_is_complete_and_sealable() -> None:
    analysis = _analyze(valid_candidate())
    assert analysis.seal_ready
    assert analysis.scope_members == (
        "source-item:13",
        "source-item:14",
        "source-item:15",
        "source-item:215",
        "source-item:217",
    )
    assert tuple(map(len, analysis.group_members)) == (3, 1)
    assert analysis.group_representatives[0][0] == "source-item:13"
    assert tuple(map(len, analysis.outcome_members)) == (1,)


def test_content_identity_matches_frozen_plan_reference_vector() -> None:
    mock = json.loads((PLAN_SPEC / "hong-kong.mock.json").read_text(encoding="utf-8"))
    frozen = mock["frozen_plan"]
    assert (
        content_identity(frozen["sealed_content"]) == frozen["seal"]["content_identity"]
    )


def test_duplicate_assignment_and_missing_scope_are_localized() -> None:
    candidate = deepcopy(valid_candidate())
    candidate["groups"][1]["members"] = candidate["groups"][0]["members"]
    analysis = _analyze(candidate)
    codes = {issue.code for issue in analysis.issues}
    assert "overlapping_membership" in codes
    assert "incomplete_scope" in codes


def test_unsafe_path_and_wrong_result_are_rejected() -> None:
    candidate = deepcopy(valid_candidate())
    candidate["logical_root"] = "../unsafe"
    candidate["result_ref"] = "precheck-result:other"
    analysis = _analyze(candidate)
    codes = {issue.code for issue in analysis.issues}
    assert "schema_violation" in codes
    assert "result_binding_mismatch" in codes


def test_exclusion_requires_a_reason() -> None:
    candidate = deepcopy(valid_candidate())
    candidate["other_outcomes"][0].pop("reason")
    analysis = _analyze(candidate)
    assert "schema_violation" in {issue.code for issue in analysis.issues}
    assert any("reason" in issue.message for issue in analysis.issues)


def test_destination_collision_is_rejected() -> None:
    candidate = deepcopy(valid_candidate())
    candidate["groups"][0]["source_naming"]["overrides"][1]["name"] = "item-013.jpg"
    analysis = _analyze(candidate)
    assert "destination_collision" in {issue.code for issue in analysis.issues}


def test_schema_rejection_always_prevents_seal_ready_identity() -> None:
    candidate = deepcopy(valid_candidate())
    evidence_refs = candidate["decision_notes"][0]["evidence_refs"]
    evidence_refs.append(evidence_refs[0])
    sealed_content = materialize_candidate(candidate, plan_ref=PLAN_REF)
    assert list(FROZEN_CONTENT_VALIDATOR.iter_errors(sealed_content))

    analysis = _analyze(candidate)
    assert not analysis.seal_ready
    assert analysis.content_identity is None
    assert "schema_violation" in {issue.code for issue in analysis.issues}


def test_file_destination_cannot_also_be_a_logical_directory() -> None:
    candidate = {
        "kind": "candidate",
        "result_ref": RESULT_REF,
        "scope": {
            "kind": "explicit",
            "source_item_refs": ["source-item:215", "source-item:217"],
        },
        "logical_root": "root",
        "groups": [
            {
                "relative_path": ["foo"],
                "members": {
                    "kind": "explicit",
                    "source_item_refs": ["source-item:215"],
                },
                "source_naming": {
                    "default": "preserve_source_basename",
                    "overrides": [
                        {"source_item_ref": "source-item:215", "name": "bar"}
                    ],
                },
            },
            {
                "relative_path": ["foo", "bar"],
                "members": {
                    "kind": "explicit",
                    "source_item_refs": ["source-item:217"],
                },
                "source_naming": {"default": "preserve_source_basename"},
            },
        ],
        "other_outcomes": [],
    }
    analysis = _analyze(candidate)
    assert not analysis.seal_ready
    assert "file_directory_collision" in {issue.code for issue in analysis.issues}
