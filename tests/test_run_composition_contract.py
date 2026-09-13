"""The accepted ordinary Run/Profile exchange, independent of execution."""

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).parents[1]
HOME = ROOT / "docs/spec/contract"
EXAMPLES = json.loads((HOME / "precheck-run/composition.mock.json").read_text())


def validator(tool, action=None):
    value = json.loads(
        (HOME / f"precheck-{tool}/precheck-{tool}.tool.json").read_text()
    )
    schema = (
        value["inputSchema"]
        if action is None
        else {
            "$defs": value["outputSchema"]["$defs"],
            **value["responseSchemas"][action],
        }
    )
    return Draft202012Validator(schema)


@pytest.mark.parametrize(
    "case",
    EXAMPLES["exchanges"] + EXAMPLES["semantic_rejections"],
    ids=lambda c: c["name"],
)
def test_complete_exchanges(case):
    tool = case.get("tool", "run")
    validator(tool).validate(case["request"])
    validator(tool, case["request"]["action"]).validate(case["response"])


@pytest.mark.parametrize("case", EXAMPLES["invalid_requests"], ids=lambda c: c["name"])
def test_incomplete_requests(case):
    assert not validator("run").is_valid(case["request"])


def test_shared_value_fragments_have_one_authority():
    run = validator("run").schema["$defs"]
    read = validator("read").schema["$defs"]
    output = validator("read", "review").schema["$defs"]
    for name in read:
        if name in run:
            assert read[name] == run[name]
    for name in ("processing_profile", "compression_parameters"):
        assert run[name] == output[name]


def test_preparation_does_not_relax_execution_include_exclusivity():
    request = deepcopy(EXAMPLES["exchanges"][1]["request"])
    for kind in ("execution_boundary", "local_execution"):
        validator("read").validate(
            {
                **request,
                "include": ["preparation", kind],
                "execution_page": {"limit": 1},
            }
        )
    assert not validator("read").is_valid({**request, "execution_page": {"limit": 1}})
    assert not validator("read").is_valid(
        {**request, "include": ["preparation", "execution_boundary", "local_execution"]}
    )


def test_correspondence_required_for_each_member_only_with_target():
    source = {
        "source_item_ref": "source-item:a",
        "locator": {
            "kind": "source_root_relative_path",
            "source_root_ref": "source-root:a",
            "value": "a.jpg",
        },
        "scope": "source_media",
        "condition": "usable",
        "source_content_verification": {"status": "not_checked"},
    }
    response = {
        "resolution": {
            "source_set_identity": "sha256:" + "1" * 64,
            "membership_identity": "sha256:" + "2" * 64,
            "target_result_ref": "precheck-result:b",
        },
        "members": [source],
        "page": {"total": 1, "next_cursor": None},
    }
    check = validator("read", "resolve")
    assert not check.is_valid(response)
    source["correspondence"] = {
        "status": "unproven",
        "basis": {"code": "not_direct_successor"},
    }
    check.validate(response)
    source["correspondence"]["source_item_ref"] = "source-item:b"
    assert not check.is_valid(response)
