"""Read's schema execution shortcuts preserve the authoritative validator's rules."""

from copy import deepcopy

import pytest
from jsonschema import Draft202012Validator

from mediasense.runtime._validation import ReadValidator
from mediasense.runtime.resources import FORMAT_CHECKER, load_contract


def errors(validator, value):
    return [
        (e.message, list(e.absolute_path), list(e.absolute_schema_path))
        for e in validator.iter_errors(value)
    ]


def test_observation_validator_reuses_definition_and_resets_with_root_cache():
    from concurrent.futures import ThreadPoolExecutor
    from mediasense.runtime.resources import contract_validator, observation_validator

    first = observation_validator()
    assert isinstance(first, ReadValidator)
    assert first.format_checker is FORMAT_CHECKER
    assert observation_validator() is first
    expected = contract_validator("mediasense.precheck.read", "review").evolve(
        schema={"$defs": first.schema["$defs"], "$ref": "#/$defs/observation"}
    )
    for value in (
        {"name": "capture_time", "status": "available", "value": "2026-09-11"},
        {"name": "capture_time", "status": "available", "value": "2026-09-11T01:00:00+08:00"},
        {"name": "extension", "status": "available", "value": {"nested": [True, 3]}},
        {"name": "iso", "status": "available", "value": True},
    ):
        assert errors(first, value) == errors(expected, value)
    with ThreadPoolExecutor(max_workers=1) as executor:
        child = executor.submit(observation_validator).result()
        assert child is not first
    contract_validator.cache_clear()
    assert observation_validator() is not first


@pytest.mark.parametrize(
    "schema",
    [
        {"oneOf": [{"type": "boolean"}, {"type": "number"}]},
        {"oneOf": [{"type": "integer"}, {"type": "number"}]},
        {"oneOf": [{"type": "string", "minLength": 2}, {"type": "null"}]},
        {"oneOf": [{"type": ["integer", "null"]}, {"const": True}]},
        {
            "oneOf": [
                {"type": "array", "items": {"type": "string"}},
                {"type": "object", "required": ["x"]},
            ]
        },
        {
            "if": {"properties": {"name": {"const": "x"}}},
            "then": {"required": ["value"]},
            "else": {"type": "null"},
        },
        {
            "if": {"properties": {"name": {"enum": ["x", "y"]}}, "required": ["name"]},
            "then": {"required": ["value"]},
            "else": {"type": "null"},
        },
        {
            "if": {"properties": {"value": {"const": True}}},
            "then": {"required": ["name"]},
            "else": {"type": "null"},
        },
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        1,
        1.5,
        "",
        "x",
        "xx",
        [],
        ["x"],
        [1],
        {},
        {"x": 1},
        {"name": "x"},
        {"name": "x", "value": 1},
        {"value": True},
        {"value": 1},
    ],
)
def test_shortcuts_preserve_validity_and_failure_paths(schema, value):
    assert errors(ReadValidator(schema), value) == errors(
        Draft202012Validator(schema), value
    )


@pytest.mark.parametrize(
    "observation",
    [
        {
            "name": "capture_time",
            "status": "available",
            "value": "2026-09-11T01:00:00+08:00",
        },
        {"name": "capture_time", "status": "available", "value": "2026-09-11"},
        {"name": "iso", "status": "available", "value": True},
        {"name": "iso", "status": "available", "value": 100},
        {"name": "camera_model", "status": "available", "value": "Camera"},
        {"name": "camera_model", "status": "available", "value": None},
        {
            "name": "camera_model",
            "status": "not_checked",
            "basis": {"code": "historical_unrecorded"},
        },
        {"name": "camera_model", "status": "failed"},
        {
            "name": "extension",
            "status": "available",
            "value": {
                "observations": [{"status": "a domain value", "value": None}],
                "nested": [False, 1, None, "text", [2.5]],
            },
        },
        {"name": "extension", "status": "available", "value": {"bad": {1, 2}}},
        {"name": "extension", "status": "available", "value": {"tuple": (1, 2)}},
        {"name": "extension", "status": "missing", "value": "must not exist"},
    ],
)
def test_real_observation_contract_uses_identical_rules(observation):
    contract = load_contract("mediasense.precheck.read")
    schema = {"$defs": contract["outputSchema"]["$defs"], "$ref": "#/$defs/observation"}
    saved = deepcopy(observation)
    assert errors(
        ReadValidator(schema, format_checker=FORMAT_CHECKER), observation
    ) == errors(
        Draft202012Validator(schema, format_checker=FORMAT_CHECKER), observation
    )
    assert observation == saved


@pytest.mark.parametrize("restricted", [False, True])
@pytest.mark.parametrize(
    "value",
    [None, True, 1, {}, [], [1], [None, {"nested": ["x", False]}], {"bad": {1, 2}}],
)
def test_recursive_json_union_honors_changes_to_the_schema(restricted, value):
    contract = load_contract("mediasense.precheck.read")
    schema = {"$defs": contract["outputSchema"]["$defs"], "$ref": "#/$defs/json_value"}
    if restricted:
        array = next(
            b for b in schema["$defs"]["json_value"]["oneOf"] if b["type"] == "array"
        )
        array["minItems"] = 2
    assert errors(ReadValidator(schema), value) == errors(
        Draft202012Validator(schema), value
    )


def test_a_similar_union_with_different_reference_semantics_is_not_shortcut():
    contract = load_contract("mediasense.precheck.read")
    definition = deepcopy(contract["outputSchema"]["$defs"]["json_value"])
    for branch in definition["oneOf"]:
        if branch["type"] == "array":
            branch["items"] = {"$ref": "#/$defs/member"}
        if branch["type"] == "object":
            branch["additionalProperties"] = {"$ref": "#/$defs/member"}
    schema = {"$defs": {"member": {"type": "number"}}, **definition}
    for value in ["valid scalar", [1], ["invalid member"], {"x": False}]:
        assert errors(ReadValidator(schema), value) == errors(
            Draft202012Validator(schema), value
        )
