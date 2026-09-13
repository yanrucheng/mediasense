from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from mediasense.runtime.resources import FORMAT_CHECKER

ROOT = Path(__file__).parents[1]
PACKET = ROOT / "openspec/changes/simplify-precheck-contract"
RUN = ROOT / "docs/spec/contract/precheck-run"
READ = ROOT / "docs/spec/contract/precheck-read"


def load(path):
    return json.loads(path.read_text())


def validator(action=None):
    tool = load(RUN / "precheck-run.tool.json")
    schema = (
        tool["inputSchema"]
        if action is None
        else {"$defs": tool["outputSchema"]["$defs"], **tool["responseSchemas"][action]}
    )
    return Draft202012Validator(schema, format_checker=FORMAT_CHECKER)


EXCHANGES = load(PACKET / "contracts/examples.json")["exchanges"]
NEGATIVE = load(PACKET / "contracts/examples.json")["negative"]


def test_schemas_compile_and_match_packaged_authority():
    # Existing control requests and historical transcripts remain valid. Geo
    # recovery adds disclosure fields in the current contract, not the old packet.
    for kind, root in (("run", RUN),):
        tool = load(root / f"precheck-{kind}.tool.json")
        historical = load(PACKET / f"contracts/precheck-{kind}.tool.json")[
            "inputSchema"
        ]

        def controls(schema):
            return [
                branch
                for branch in schema["oneOf"]
                if branch["properties"]["action"]["const"] != "status"
            ]

        assert controls(tool["inputSchema"]) == controls(historical)
        # status adds an explicit local-execution view; old transcripts below
        # must remain valid without rewriting the historical packet.
        assert tool == load(
            ROOT / f"src/mediasense/_resources/contracts/precheck-{kind}.tool.json"
        )
        for schema in (tool["inputSchema"], tool["outputSchema"]):
            Draft202012Validator.check_schema(schema)
    assert (
        load(RUN / "precheck-run.tool.json")["outputSchema"]["$defs"]["result"]
        == load(READ / "precheck-read.tool.json")["outputSchema"]["$defs"]["result"]
    )


@pytest.mark.parametrize(
    "exchange", [e for e in EXCHANGES if e["tool"] == "run"], ids=lambda e: e["name"]
)
def test_run_transcript_is_action_bound(exchange):
    validator().validate(exchange["request"])
    validator(exchange["request"]["action"]).validate(exchange["response"])


@pytest.mark.parametrize(
    "case", [e for e in NEGATIVE if e["tool"] == "run"], ids=lambda e: e["name"]
)
def test_rejected_run_shapes(case):
    selected = validator("status") if case["side"] == "response:status" else validator()
    assert not selected.is_valid(case["value"])


def test_start_requires_explicit_dataset_even_with_prior_result():
    request = {
        "action": "start",
        "request_id": "request:a",
        "prior_result_ref": "precheck-result:a",
    }
    assert not validator().is_valid(request)
    validator().validate({**request, "dataset_ref": "dataset:a"})


@pytest.mark.parametrize(
    "state,required",
    [
        ("running", "progress"),
        ("paused", "reason"),
        ("blocked", "reason"),
        ("failed", "reason"),
        ("completed", "result"),
    ],
)
def test_status_never_accepts_control_shorthand(state, required):
    response = deepcopy(
        next(
            e["response"]
            for e in EXCHANGES
            if e["tool"] == "run"
            and e["request"]["action"] == "status"
            and e["response"].get("state") == state
        )
    )
    response.pop(required)
    assert not validator("status").is_valid(response)


@pytest.mark.parametrize(
    "field,value",
    [
        ("processed", -1),
        ("total", "unknown"),
        ("last_progress_at", "yesterday"),
        ("worker_id", "private-worker"),
        ("percentage", 50),
    ],
)
def test_progress_rejects_unsupported_counts_and_private_state(field, value):
    response = deepcopy(
        next(e["response"] for e in EXCHANGES if e["name"] == "running")
    )
    response["progress"][field] = value
    assert not validator("status").is_valid(response)


def test_unknown_progress_is_explicit_null_and_issues_are_bounded():
    response = deepcopy(
        next(e["response"] for e in EXCHANGES if e["name"] == "running")
    )
    response["progress"].update(processed=None, total=None, last_progress_at=None)
    validator("status").validate(response)
    issue = {
        "phase": "video",
        "code": "invalid_media",
        "unit": "logical_operation",
        "count": 1,
        "message": "Cannot decode one operation.",
    }
    response["issues"] = [issue] * 6
    assert not validator("status").is_valid(response)


@pytest.mark.parametrize(
    "coverage,readiness",
    [
        ("complete", "plan_ready"),
        ("partial", "plan_ready"),
        ("complete", "blocked"),
        ("partial", "blocked"),
    ],
)
def test_coverage_and_readiness_are_independent(coverage, readiness):
    response = deepcopy(
        next(e["response"] for e in EXCHANGES if e["name"] == "completed-no-place")
    )
    response["result"].update(coverage=coverage, readiness=readiness)
    validator("status").validate(response)
    response["result"]["integrity"] = "valid"
    assert not validator("status").is_valid(response)


def test_scope_and_diagnostic_selectors_cannot_mix():
    base = {"action": "status", "dataset_ref": "dataset:a", "run_ref": "precheck-run:a"}
    validator().validate({**base, "scope_path": ".", "scope_after": "opaque"})
    assert not validator().is_valid({**base, "scope_after": "opaque"})
    assert not validator().is_valid(
        {**base, "scope_path": ".", "include": ["accounting"]}
    )
    validator().validate(
        {**base, "include": ["accounting", "diagnostics"], "page": {"limit": 200}}
    )
    assert not validator().is_valid(
        {**base, "include": ["diagnostics"], "page": {"limit": 201}}
    )
