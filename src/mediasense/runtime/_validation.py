"""Equivalent fast paths for common JSON Schema branches in large Read values.

The contract remains the schema. Only provably disjoint type unions and simple
string predicates take shortcuts; all other shapes and validation failures use
jsonschema's original evaluators, including their diagnostic paths.
"""

from jsonschema import Draft202012Validator, validators
from referencing.exceptions import Unresolvable


_ONE_OF = Draft202012Validator.VALIDATORS["oneOf"]
_IF = Draft202012Validator.VALIDATORS["if"]
_JSON_TYPES = {"null", "boolean", "number", "integer", "string", "array", "object"}


def _recursive_json_union(validator, alternatives):
    """Prove that this union and its recursive references impose only JSON types."""
    if len(alternatives) != 6 or any(not isinstance(a, dict) for a in alternatives):
        return False
    branches = {
        a.get("type"): a for a in alternatives if isinstance(a.get("type"), str)
    }
    if set(branches) != _JSON_TYPES - {"integer"}:
        return False
    if any(
        set(branches[t]) != {"type"} for t in ("null", "boolean", "number", "string")
    ):
        return False
    array, obj = branches["array"], branches["object"]
    if set(array) != {"type", "items"} or set(obj) != {"type", "additionalProperties"}:
        return False
    item, value = array["items"], obj["additionalProperties"]
    if not isinstance(item, dict) or not isinstance(value, dict):
        return False
    if set(item) != {"$ref"} or value != item:
        return False
    ref = item["$ref"]
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return False
    try:
        target = validator._resolver.lookup(ref).contents
    except Unresolvable:
        return False
    return (
        isinstance(target, dict)
        and set(target) == {"oneOf"}
        and target["oneOf"] is alternatives
    )


def _plain_json_value(instance):
    pending, seen = [instance], set()
    while pending:
        value = pending.pop()
        kind = type(value)
        if kind in (str, int, float, bool, type(None)):
            continue
        if kind not in (list, dict) or id(value) in seen:
            # Exotic Python values and shared/cyclic containers keep the native
            # evaluator's exact behavior. Finite-number checks remain with the
            # caller, just as they do for the original JSON Schema number type.
            return False
        seen.add(id(value))
        pending.extend(value.values() if kind is dict else value)
    return True


def _typed_one_of(validator, alternatives, instance, schema):
    if _recursive_json_union(validator, alternatives) and _plain_json_value(instance):
        return
    types = [
        item.get("type") if isinstance(item, dict) else None for item in alternatives
    ]
    if (
        types
        and all(isinstance(kind, str) and kind in _JSON_TYPES for kind in types)
        and len(set(types)) == len(types)
        and not {"integer", "number"} <= set(types)
    ):
        matching = [
            index
            for index, kind in enumerate(types)
            if validator.is_type(instance, kind)
        ]
        if len(matching) == 1:
            index = matching[0]
            errors = validator.descend(instance, alternatives[index], schema_path=index)
            if next(errors, None) is None:
                return
    yield from _ONE_OF(validator, alternatives, instance, schema)


def _string_predicate(validator, predicate, instance):
    """Return None when the predicate needs the general schema evaluator."""
    if not isinstance(predicate, dict) or set(predicate) - {"properties", "required"}:
        return None
    properties = predicate.get("properties", {})
    required = predicate.get("required", [])
    if not isinstance(properties, dict) or not isinstance(required, list):
        return None
    for condition in properties.values():
        if not isinstance(condition, dict):
            return None
        if set(condition) == {"const"} and isinstance(condition["const"], str):
            continue
        if (
            set(condition) == {"enum"}
            and isinstance(condition["enum"], list)
            and all(isinstance(value, str) for value in condition["enum"])
        ):
            continue
        return None
    # Both properties and required are ignored for non-objects by JSON Schema.
    if not validator.is_type(instance, "object"):
        return True
    if any(name not in instance for name in required):
        return False
    for name, condition in properties.items():
        if name in instance:
            if "const" in condition and instance[name] != condition["const"]:
                return False
            if "enum" in condition and instance[name] not in condition["enum"]:
                return False
    return True


def _simple_if(validator, predicate, instance, schema):
    matched = _string_predicate(validator, predicate, instance)
    if matched is None:
        yield from _IF(validator, predicate, instance, schema)
        return
    branch = "then" if matched else "else"
    if branch in schema:
        yield from validator.descend(instance, schema[branch], schema_path=branch)


ReadValidator = validators.extend(
    Draft202012Validator, {"oneOf": _typed_one_of, "if": _simple_if}
)
