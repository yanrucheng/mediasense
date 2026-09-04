from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]
SPEC_ROOT = ROOT / "docs" / "spec" / "spec-260826-1546-precheck-read"
RUNTIME_CONTRACT = (
    ROOT / "src" / "mediasense" / "_resources" / "contracts" / "precheck-read.tool.json"
)


def _load(name: str):
    return json.loads((SPEC_ROOT / name).read_text(encoding="utf-8"))


def _objects(value) -> Iterator[dict]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def test_contract_is_zero_bc_and_exposes_only_consumer_operations() -> None:
    tool = _load("precheck-read.tool.json")
    branches = tool["inputSchema"]["oneOf"]
    definitions = tool["inputSchema"]["$defs"]
    operations = {
        definitions[branch["$ref"].rsplit("/", 1)[1]]["properties"]["operation"][
            "const"
        ]
        for branch in branches
    }

    assert operations == {"review", "expand", "resolve"}
    encoded = json.dumps(tool)
    assert '"action"' not in encoded
    assert '"inspect"' not in encoded
    assert '"traverse"' not in encoded


def test_expand_requires_one_selector_and_published_include_names() -> None:
    tool = _load("precheck-read.tool.json")
    validator = Draft202012Validator(tool["inputSchema"])
    result_ref = "precheck-result:test"

    valid = {
        "operation": "expand",
        "result_ref": result_ref,
        "evidence_refs": ["evidence:a"],
        "include": ["anchor_evidence", "prepared_targets"],
    }
    validator.validate(valid)

    assert list(
        validator.iter_errors(
            {
                **valid,
                "source_item_refs": ["source-item:a"],
            }
        )
    )
    assert list(
        validator.iter_errors(
            {
                **valid,
                "include": ["semantic_recommendation"],
            }
        )
    )


def test_contract_publishes_projection_roles_and_bounded_pages() -> None:
    tool = _load("precheck-read.tool.json")
    input_defs = tool["inputSchema"]["$defs"]
    output_defs = tool["outputSchema"]["$defs"]

    assert output_defs["evidence_role"]["enum"] == [
        "representative",
        "boundary",
        "outlier",
        "conflict",
    ]
    assert input_defs["page_100"]["properties"]["limit"]["maximum"] == 100
    assert input_defs["page_200"]["properties"]["limit"]["maximum"] == 200
    assert input_defs["page_1000"]["properties"]["limit"]["maximum"] == 1000
    assert output_defs["page"]["properties"]["stop_reason"]["enum"] == [
        "complete",
        "limit",
        "byte_limit",
    ]
    assert output_defs["review_response"]["properties"]["page"]["allOf"][1] == {
        "required": ["order"]
    }
    error_codes = output_defs["error_response"]["properties"]["error"][
        "properties"
    ]["code"]["enum"]
    assert "reference_not_in_result" in error_codes
    assert "source_set_out_of_scope" not in error_codes


def test_contract_keeps_qualification_and_source_verification_explicit() -> None:
    definitions = _load("precheck-read.tool.json")["outputSchema"]["$defs"]

    assert definitions["qualification"]["properties"]["effect"]["enum"] == [
        "limits_interpretation",
        "blocks_use",
    ]
    assert definitions["resolved_member"]["required"] == [
        "source_item_ref",
        "locator",
        "scope",
        "condition",
        "source_content_verification",
    ]
    assert definitions["source_verification"]["properties"]["profile"]["type"] == (
        "string"
    )


def test_contract_does_not_expose_private_storage_vocabulary() -> None:
    encoded = json.dumps(_load("precheck-read.tool.json")).lower()

    for forbidden in (
        "sqlite",
        "table_name",
        "row_id",
        "cache_key",
        "compression_group",
    ):
        assert forbidden not in encoded


def test_mock_requests_and_responses_conform() -> None:
    tool = _load("precheck-read.tool.json")
    mock = _load("hong-kong.mock.json")
    input_validator = Draft202012Validator(tool["inputSchema"])
    output_validator = Draft202012Validator(tool["outputSchema"])

    assert {exchange["request"]["operation"] for exchange in mock["exchanges"]} == {
        "review",
        "expand",
        "resolve",
    }
    for exchange in mock["exchanges"]:
        input_validator.validate(exchange["request"])
        output_validator.validate(exchange["response"])


def test_review_mock_carries_reconciliation_and_no_semantic_decision() -> None:
    mock = _load("hong-kong.mock.json")
    review = next(
        exchange["response"]
        for exchange in mock["exchanges"]
        if exchange["request"]["operation"] == "review"
    )
    reconciliation = review["reconciliation"]
    partition = reconciliation["partition"]

    assert reconciliation["accounted_total"] == sum(partition.values())
    assert partition["residual"] == 0
    assert reconciliation["closure_check"]["status"] == "passed"
    assert all(
        {item["include"] for item in card["available_expansions"]}
        == {
            "anchor_evidence",
            "prepared_targets",
            "provenance",
            "coverage_basis",
            "member_observations",
        }
        for card in review["coverage_cards"]
    )
    encoded = json.dumps(review, ensure_ascii=False)
    for forbidden in ("recommended_group", "directory_name", "organization_profile"):
        assert forbidden not in encoded


def test_all_local_schema_references_resolve() -> None:
    tool = _load("precheck-read.tool.json")
    for schema in (tool["inputSchema"], tool["outputSchema"]):
        for value in _objects(schema):
            reference = value.get("$ref")
            if not reference or not reference.startswith("#/"):
                continue
            resolved = schema
            for component in reference[2:].split("/"):
                resolved = resolved[component.replace("~1", "/").replace("~0", "~")]
            assert resolved


def test_runtime_contract_matches_authoritative_spec() -> None:
    assert json.loads(RUNTIME_CONTRACT.read_text(encoding="utf-8")) == _load(
        "precheck-read.tool.json"
    )
