from __future__ import annotations

from collections.abc import Iterator
import json
from pathlib import Path

from jsonschema import Draft202012Validator


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
        branch["properties"].get("target", {}).get("$ref") == "#/$defs/opaque_ref"
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


def test_contract_exposes_replaceable_result_local_source_verification() -> None:
    tool = _load("precheck-read.tool.json")
    definitions = tool["outputSchema"]["$defs"]
    result_view = definitions["result_view"]
    source_locator = definitions["source_locator"]
    verification = definitions["source_verification_value"]

    assert "source_root_ref" not in result_view["required"]
    assert "source_root_ref" not in result_view["properties"]
    assert source_locator["required"] == ["kind", "source_root_ref", "value"]
    assert source_locator["properties"]["source_root_ref"] == {
        "$ref": "#/$defs/source_root_ref"
    }
    assert "execution_boundary" in result_view["required"]
    assert result_view["properties"]["execution_boundary"] == {
        "$ref": "#/$defs/execution_boundary"
    }
    assert verification["required"] == [
        "profile",
        "value",
        "size_bytes",
        "observed_at",
        "producer",
    ]
    assert verification["properties"]["profile"]["type"] == "string"
    assert "enum" not in verification["properties"]["profile"]

    mock = _load("hong-kong.mock.json")
    source_views = [
        exchange["response"]["target"]
        for exchange in mock["exchanges"]
        if exchange["response"].get("target", {}).get("kind") == "source_item"
    ]
    assert source_views
    assert all(
        item["locator"]["source_root_ref"].startswith("source-root:")
        for item in source_views
    )


def test_contract_allows_one_result_to_reference_multiple_source_roots() -> None:
    output_schema = _load("precheck-read.tool.json")["outputSchema"]
    validator = Draft202012Validator(output_schema)
    result_ref = "precheck-result:multi-root"

    for item_ref, root_ref, relative_path in (
        ("source-item:a", "source-root:disk-a", "DCIM/a.jpg"),
        ("source-item:b", "source-root:disk-b", "archive/b.jpg"),
    ):
        validator.validate(
            {
                "outcome": "ok",
                "result_ref": result_ref,
                "action": "inspect",
                "target": {
                    "kind": "source_item",
                    "ref": item_ref,
                    "locator": {
                        "kind": "source_root_relative_path",
                        "source_root_ref": root_ref,
                        "value": relative_path,
                    },
                },
            }
        )


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
    assert not [value for value in _objects(mock) if value.get("qualifications") == []]


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
