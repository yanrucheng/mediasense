from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mediasense.runtime.resources import FORMAT_CHECKER

ROOT = Path(__file__).parents[1]
SPEC = ROOT / "docs/spec/spec-260826-1546-precheck-read"
PACKET = ROOT / "openspec/changes/simplify-precheck-contract/contracts"
TOOL = json.loads((SPEC / "precheck-read.tool.json").read_text())
CASES = json.loads((PACKET / "examples.json").read_text())


def validator(action=None):
    schema = (
        TOOL["inputSchema"]
        if action is None
        else {"$defs": TOOL["outputSchema"]["$defs"], **TOOL["responseSchemas"][action]}
    )
    return Draft202012Validator(schema, format_checker=FORMAT_CHECKER)


@pytest.mark.parametrize(
    "exchange",
    [e for e in CASES["exchanges"] if e["tool"] == "read"],
    ids=lambda e: e["name"],
)
def test_read_transcript_is_action_bound(exchange):
    validator().validate(exchange["request"])
    validator(exchange["request"]["action"]).validate(exchange["response"])


@pytest.mark.parametrize(
    "case",
    [e for e in CASES["negative"] if e["tool"] == "read"],
    ids=lambda e: e["name"],
)
def test_read_rejects_invalid_shape(case):
    selected = (
        validator()
        if case["side"] == "inputSchema"
        else Draft202012Validator(TOOL["outputSchema"])
    )
    assert not selected.is_valid(case["value"])


def test_mock_requests_and_responses_conform():
    for exchange in json.loads((SPEC / "hong-kong.mock.json").read_text())["exchanges"]:
        validator().validate(exchange["request"])
        validator(exchange["request"]["action"]).validate(exchange["response"])


@pytest.mark.parametrize(
    "action,limit",
    [("review", 100), ("expand", 200), ("geo_summary", 200), ("resolve", 1000)],
)
def test_page_limits_and_selector_requirements(action, limit):
    request = {
        "action": action,
        "dataset_ref": "dataset:a",
        "result_ref": "precheck-result:a",
        "page": {"limit": limit},
    }
    if action == "expand":
        request.update(evidence_refs=["evidence:a"], include=["member_observations"])
    if action == "resolve":
        request["source_set"] = {
            "kind": "explicit",
            "source_item_refs": ["source-item:a"],
        }
    validator().validate(request)
    request["page"]["limit"] += 1
    assert not validator().is_valid(request)


def test_prepared_targets_keep_both_kinds_and_atomic_expansion():
    response = deepcopy(
        next(
            e["response"] for e in CASES["exchanges"] if e["name"] == "expand-evidence"
        )
    )
    target = response["items"][0]["included"]["prepared_targets"][0]
    validator("expand").validate(response)
    target["target"] = {"kind": "evidence", "ref": "evidence:other"}
    validator("expand").validate(response)
    target["target"]["kind"] = "private_work"
    assert not validator("expand").is_valid(response)
    request = {
        "action": "expand",
        "dataset_ref": "dataset:a",
        "result_ref": "precheck-result:a",
        "source_item_refs": [f"source-item:{n}" for n in range(16)],
        "include": ["observations"],
    }
    validator().validate(request)
    request["source_item_refs"].append("source-item:17")
    assert not validator().is_valid(request)


def test_observation_and_verification_guarantees_are_preserved():
    definitions = TOOL["outputSchema"]["$defs"]
    assert definitions["qualification"]["properties"]["effect"]["enum"] == [
        "limits_interpretation",
        "blocks_use",
    ]
    assert "source_content_verification" in definitions["resolved_member"]["required"]
    assert (
        definitions["source_verification"]["properties"]["profile"]["type"] == "string"
    )
    assert definitions["page"]["required"] == ["total", "next_cursor"]
    encoded = json.dumps(TOOL).lower()
    for forbidden in ("sqlite", "cache_key", "row_id", "compression_group"):
        assert forbidden not in encoded


def test_active_mock_accounting_and_membership_are_recomputable():
    import hashlib

    def identity(value):
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
        )

    for exchange in json.loads((SPEC / "hong-kong.mock.json").read_text())["exchanges"]:
        request, response = exchange["request"], exchange["response"]
        if request["action"] == "review":
            assert response["accounting"]["total"] == sum(
                row["count"] for row in response["accounting"]["scope_condition"]
            )
            assert response["accounting"]["total"] == sum(
                response["accounting"]["routes"].values()
            )
        if request["action"] == "resolve":
            members = sorted(item["source_item_ref"] for item in response["members"])
            assert response["resolution"]["source_set_identity"] == identity(
                request["source_set"]
            )
            assert response["resolution"]["membership_identity"] == identity(
                {
                    "result_ref": request["result_ref"],
                    "source_set": request["source_set"],
                    "members": members,
                }
            )
