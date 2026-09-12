"""Stage-neutral validation for the immutable Frozen Plan contract."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


FROZEN_PLAN_SCHEMA_ID = "https://mediasense.local/spec/frozen-plan.schema.json"
SUPPORTED_ENCODING_PROFILE = "mediasense-json-strings-sha256-v1"


class FrozenPlanValidationError(ValueError):
    """A Frozen Plan is not safe to publish or consume."""


def frozen_plan_schema_path() -> Path:
    return Path(
        str(
            files("mediasense").joinpath(
                "_resources", "contracts", "frozen-plan.schema.json"
            )
        )
    )


def load_frozen_plan_schema(schema_path: Path | None = None) -> dict[str, Any]:
    path = Path(schema_path) if schema_path is not None else frozen_plan_schema_path()
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    if schema.get("$id") != FROZEN_PLAN_SCHEMA_ID:
        raise FrozenPlanValidationError("unexpected Frozen Plan schema identity")
    return schema


def load_frozen_content_validator(
    schema_path: Path | None = None,
) -> Draft202012Validator:
    schema = load_frozen_plan_schema(schema_path)
    sealed_content_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/sealedContent",
    }
    return Draft202012Validator(sealed_content_schema)


def load_frozen_plan_validator(
    schema_path: Path | None = None,
) -> Draft202012Validator:
    return Draft202012Validator(
        load_frozen_plan_schema(schema_path), format_checker=FormatChecker()
    )


def canonical_strings_json(value: Any) -> str:
    """Serialize the current Frozen Plan encoding profile."""

    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(canonical_strings_json(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise FrozenPlanValidationError("JSON object keys must be strings")
        return (
            "{"
            + ",".join(
                canonical_strings_json(key) + ":" + canonical_strings_json(value[key])
                for key in sorted(value)
            )
            + "}"
        )
    raise FrozenPlanValidationError(
        f"{SUPPORTED_ENCODING_PROFILE} permits only objects, arrays, and strings"
    )


def content_identity(sealed_content: Mapping[str, Any]) -> str:
    canonical = canonical_strings_json(dict(sealed_content)).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def validate_frozen_plan(
    plan: Mapping[str, object],
    *,
    validator: Draft202012Validator,
) -> Mapping[str, object]:
    """Validate schema, supported encoding, identity, and Human confirmation."""

    if not isinstance(plan, Mapping):
        raise FrozenPlanValidationError("Frozen Plan must be an object")
    seal_value = plan.get("seal")
    if not isinstance(seal_value, Mapping):
        raise FrozenPlanValidationError("Frozen Plan seal must be an object")
    profile = seal_value.get("encoding_profile")
    if profile != SUPPORTED_ENCODING_PROFILE:
        raise FrozenPlanValidationError(
            f"unsupported Frozen Plan encoding profile: {profile}"
        )

    errors = sorted(validator.iter_errors(dict(plan)), key=_error_path)
    if errors:
        error = errors[0]
        raise FrozenPlanValidationError(
            f"Frozen Plan schema violation at {_format_error_path(error.absolute_path)}: "
            f"{error.message}"
        )

    content = plan["sealed_content"]
    seal = plan["seal"]
    assert isinstance(content, Mapping) and isinstance(seal, Mapping)
    expected = seal["content_identity"]
    assert isinstance(expected, str)
    if content_identity(content) != expected:
        raise FrozenPlanValidationError("Frozen Plan content identity mismatch")
    confirmation = seal["final_confirmation"]
    assert isinstance(confirmation, Mapping)
    if confirmation["confirmed_content_identity"] != expected:
        raise FrozenPlanValidationError(
            "Frozen Plan is not confirmed at its exact identity"
        )
    return plan


def _error_path(error: Any) -> tuple[str, ...]:
    return tuple(str(part) for part in error.absolute_path)


def _format_error_path(parts: Any) -> str:
    rendered = "$"
    for part in parts:
        rendered += f"[{part}]" if isinstance(part, int) else f".{part}"
    return rendered


__all__ = [
    "FROZEN_PLAN_SCHEMA_ID",
    "SUPPORTED_ENCODING_PROFILE",
    "FrozenPlanValidationError",
    "canonical_strings_json",
    "content_identity",
    "frozen_plan_schema_path",
    "load_frozen_content_validator",
    "load_frozen_plan_schema",
    "load_frozen_plan_validator",
    "validate_frozen_plan",
]
