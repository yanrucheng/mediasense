from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path


SPEC_ROOT = (
    Path(__file__).parents[1] / "docs" / "spec" / "spec-260826-1546-precheck-read"
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


def test_contract_exposes_only_business_required_traversal_directions() -> None:
    tool = _load("precheck-read.tool.json")
    expected = {
        ("accounts_for", "outbound"),
        ("entry_evidence", "outbound"),
        ("represents", "outbound"),
        ("represents", "inbound"),
        ("derived_from", "outbound"),
        ("expands_to", "outbound"),
    }
    input_branches = tool["inputSchema"]["allOf"][3]["then"]["oneOf"]
    output_rules = tool["outputSchema"]["$defs"]["traverse_response"]["allOf"]
    output_branches = next(rule["oneOf"] for rule in output_rules if "oneOf" in rule)

    assert _relation_directions(input_branches) == expected
    assert _relation_directions(output_branches) == expected
    assert all(
        branch["properties"].get("target", {}).get("$ref")
        == "#/$defs/opaque_ref"
        for branch in input_branches
        if "target" in branch["properties"]
        and branch["properties"]["target"] is not False
    )
    assert all(
        branch["properties"]["origin"]["$ref"] == "#/$defs/opaque_ref"
        for branch in output_branches
    )


def test_contract_keeps_qualification_and_basis_minimal() -> None:
    tool = _load("precheck-read.tool.json")
    definitions = tool["outputSchema"]["$defs"]

    assert definitions["qualification"]["properties"]["effect"]["enum"] == [
        "limits_interpretation",
        "blocks_use",
    ]
    available_rule = definitions["observation"]["allOf"][0]["then"]
    failed_rule = definitions["observation"]["allOf"][1]["then"]
    assert available_rule["required"] == ["value"]
    assert failed_rule["required"] == ["basis"]
    qualification_lists = [
        value["qualifications"]
        for value in _objects(definitions)
        if "qualifications" in value
        and isinstance(value["qualifications"], dict)
        and value["qualifications"].get("type") == "array"
    ]
    assert qualification_lists
    assert all(value["minItems"] == 1 for value in qualification_lists)


def test_mock_uses_kind_only_when_relationship_target_type_is_ambiguous() -> None:
    mock = _load("hong-kong.mock.json")
    for exchange in mock["exchanges"]:
        request = exchange["request"]
        if request["action"] != "traverse":
            continue
        response = exchange["response"]
        assert isinstance(response["origin"], str)
        if "target" in request:
            assert isinstance(request["target"], str)

        target_types = {type(item["target"]) for item in response["items"]}
        if request["relation"] in {"derived_from", "expands_to"}:
            assert target_types <= {dict}
            assert all(
                item["target"]["kind"] in {"source_item", "evidence"}
                for item in response["items"]
            )
        else:
            assert target_types <= {str}
    assert not [
        value
        for value in _objects(mock)
        if value.get("qualifications") == []
    ]


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


def _relation_directions(branches: list[dict]) -> set[tuple[str, str]]:
    result = set()
    for branch in branches:
        properties = branch["properties"]
        relations = properties["relation"].get("enum") or [
            properties["relation"]["const"]
        ]
        result.update(
            (relation, properties["direction"]["const"]) for relation in relations
        )
    return result
