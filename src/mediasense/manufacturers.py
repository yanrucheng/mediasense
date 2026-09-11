"""Local manufacturer knowledge: validated files, explicit overlays and snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
import json
import hashlib
from pathlib import Path
import re
from typing import Any, Mapping

from jsonschema import Draft202012Validator
import yaml


class KnowledgeError(ValueError):
    """A knowledge file or snapshot cannot be used as declared."""


class _KnowledgeLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        event = self.peek_event()
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            raise KnowledgeError("YAML anchors and aliases are not supported")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        result = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str) or key in result:
                raise KnowledgeError(f"duplicate or non-string YAML key: {key!r}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def _canonical(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _identity(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode()).hexdigest()


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    resource = files("mediasense").joinpath(
        "_resources/contracts/manufacturer-knowledge.schema.json"
    )
    return Draft202012Validator(json.loads(resource.read_text(encoding="utf-8")))


def validate_document(document: object, *, source: str = "knowledge") -> dict[str, Any]:
    try:
        _canonical(document)
    except (TypeError, ValueError, RecursionError) as error:
        raise KnowledgeError(
            f"{source}: knowledge must contain finite JSON values"
        ) from error
    errors = list(_validator().iter_errors(document))
    if errors:
        error = errors[0]
        location = ".".join(map(str, error.absolute_path)) or "document"
        detail = "; ".join(item.message for item in error.context) or error.message
        raise KnowledgeError(f"{source}:{location}: {detail}")
    assert isinstance(document, dict)
    for rule in document["rules"]:
        if rule["operation"] == "disable":
            continue
        for condition in rule["when"]:
            try:
                re.compile(condition["pattern"])
            except re.error as error:
                raise KnowledgeError(
                    f"{source}:{rule['id']}: invalid pattern: {error}"
                ) from error
        names = [item["name"] for item in rule["apply"].get("fields", [])]
        if len(names) != len(set(names)):
            raise KnowledgeError(f"{source}:{rule['id']}: duplicate field effects")
    return document


def _read_document(path) -> dict[str, Any]:
    try:
        document = yaml.load(path.read_text(encoding="utf-8"), Loader=_KnowledgeLoader)
    except (OSError, UnicodeError, yaml.YAMLError, KnowledgeError) as error:
        raise KnowledgeError(f"{path}: {error}") from error
    return validate_document(document, source=str(path))


def _load_sources(root, layer: str) -> list[dict[str, Any]]:
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name)
    except OSError as error:
        raise KnowledgeError(
            f"Cannot read manufacturer directory {root}: {error}"
        ) from error
    result = []
    for path in children:
        if Path(path.name).suffix.lower() not in {".yaml", ".yml"}:
            continue
        if not path.is_file():
            raise KnowledgeError(f"Manufacturer entry is not a regular file: {path}")
        result.append(
            {"layer": layer, "name": path.name, "document": _read_document(path)}
        )
    return result


def _merge(
    sources: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: dict[str, dict[str, Any]] = {}
    builtin_ids: set[str] = set()
    user_ids: set[str] = set()
    source_names: set[tuple[str, str]] = set()
    disabled = []
    for source in sources:
        if set(source) != {"layer", "name", "document"} or source["layer"] not in {
            "builtin",
            "user",
        }:
            raise KnowledgeError("invalid manufacturer snapshot source")
        name = source["name"]
        if not isinstance(name, str) or Path(name).name != name:
            raise KnowledgeError("invalid manufacturer source name")
        key = (source["layer"], name)
        if key in source_names:
            raise KnowledgeError(f"duplicate manufacturer source: {key}")
        source_names.add(key)
        document = validate_document(
            source["document"], source=f"{source['layer']}:{name}"
        )
        origin = {
            "layer": source["layer"],
            "file": name,
            "document_identity": _identity(document),
        }
        for rule in document["rules"]:
            identifier, operation = rule["id"], rule["operation"]
            if source["layer"] == "builtin":
                if operation != "add" or identifier in active or user_ids:
                    raise KnowledgeError(
                        f"{name}:{identifier}: invalid or duplicate builtin rule"
                    )
                builtin_ids.add(identifier)
            else:
                if identifier in user_ids:
                    raise KnowledgeError(
                        f"{name}:{identifier}: duplicate user rule operation"
                    )
                user_ids.add(identifier)
            if operation == "add" and identifier in active:
                raise KnowledgeError(
                    f"{name}:{identifier}: already exists; use replace or disable"
                )
            if operation != "add" and identifier not in builtin_ids:
                raise KnowledgeError(
                    f"{name}:{identifier}: replace/disable requires an existing builtin rule"
                )
            previous = active.get(identifier)
            if operation == "disable":
                disabled.append(
                    {
                        "id": identifier,
                        "reason": rule["reason"],
                        "origin": origin,
                        "replaces": previous["origin"],
                    }
                )
                active.pop(identifier)
                continue
            active[identifier] = {"rule": rule, "origin": origin}
            if previous is not None:
                active[identifier]["replaces"] = previous["origin"]
    declarations = {}
    for entry in active.values():
        for effect in entry["rule"]["apply"].get("fields", []):
            if not effect["name"].startswith("manufacturer."):
                continue
            signature = (
                effect["value_type"],
                effect.get("unit"),
                effect["description"],
            )
            prior = declarations.setdefault(effect["name"], signature)
            if prior != signature:
                raise KnowledgeError(f"conflicting field meaning: {effect['name']}")
    return sorted(active.values(), key=lambda entry: entry["rule"]["id"]), sorted(
        disabled, key=lambda entry: entry["id"]
    )


@lru_cache(maxsize=64)
def _compiled(content: str):
    return _merge(json.loads(content)["sources"])


@dataclass(frozen=True, slots=True)
class KnowledgeSnapshot:
    """Immutable source documents; reconstruction never opens the live directory."""

    content: str

    def __post_init__(self):
        try:
            value = json.loads(self.content)
            if (
                set(value) != {"schema_version", "sources"}
                or value["schema_version"] != 1
                or not isinstance(value["sources"], list)
            ):
                raise KnowledgeError("unsupported manufacturer snapshot")
            _compiled(self.content)
        except (TypeError, KeyError, json.JSONDecodeError) as error:
            raise KnowledgeError("invalid manufacturer snapshot") from error

    @classmethod
    def from_value(cls, value: Mapping[str, Any]) -> KnowledgeSnapshot:
        return cls(_canonical(value))

    @classmethod
    def empty(cls) -> KnowledgeSnapshot:
        return cls.from_value({"schema_version": 1, "sources": []})

    def value(self) -> dict[str, Any]:
        return json.loads(self.content)

    @property
    def identity(self) -> str:
        return "sha256:" + hashlib.sha256(self.content.encode()).hexdigest()

    @property
    def entries(self) -> list[dict[str, Any]]:
        # Internal consumers treat these compiled definitions as read-only.
        return _compiled(self.content)[0]

    @property
    def tags(self) -> tuple[str, ...]:
        tags = set()
        for entry in self.entries:
            rule = entry["rule"]
            for condition in rule["when"]:
                tags.update(condition["tags"])
            time = rule["apply"].get("capture_time")
            if time:
                tags.update(time["tags"])
            for effect in rule["apply"].get("fields", []):
                tags.update(effect["tags"])
        return tuple(sorted(tags))

    def summary(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "sources": [
                {
                    "layer": source["layer"],
                    "file": source["name"],
                    "document_identity": _identity(source["document"]),
                }
                for source in self.value()["sources"]
            ],
            "active_rules": [entry["rule"]["id"] for entry in self.entries],
            "overridden_rules": [
                {
                    "id": entry["rule"]["id"],
                    "origin": dict(entry["origin"]),
                    "replaces": dict(entry["replaces"]),
                }
                for entry in self.entries
                if "replaces" in entry
            ],
            "disabled_rules": json.loads(_canonical(_compiled(self.content)[1])),
            "execution": "not_checked",
        }


@lru_cache(maxsize=1)
def builtin_knowledge() -> KnowledgeSnapshot:
    root = files("mediasense").joinpath("_resources/manufacturers")
    return KnowledgeSnapshot.from_value(
        {"schema_version": 1, "sources": _load_sources(root, "builtin")}
    )


def load_knowledge(user_config_root: Path) -> KnowledgeSnapshot:
    sources = builtin_knowledge().value()["sources"]
    root = user_config_root / "manufacturers"
    if root.exists() or root.is_symlink():
        sources.extend(_load_sources(root, "user"))
    return KnowledgeSnapshot.from_value({"schema_version": 1, "sources": sources})


def evaluate_rules(
    snapshot: KnowledgeSnapshot,
    indexed: Mapping[str, Mapping[str, Any]],
    ordered: list[str],
    subject: str,
) -> dict[str, Any]:
    """Resolve independent attribute effects while retaining applicability evidence."""
    outputs: dict[str, list[dict[str, Any]]] = {}
    for entry in snapshot.entries:
        rule = entry["rule"]
        conditions = []
        for condition in rule["when"]:
            paths = (
                [subject] if condition.get("scope", "source") == "source" else ordered
            )
            found = None
            for tag in condition["tags"]:
                for path in [subject] if tag.startswith("File:") else paths:
                    raw = indexed.get(path, {}).get(tag)
                    if raw is not None and raw != "":
                        found = {"relative_path": path, "tag": tag, "raw_value": raw}
                        break
                if found is not None:
                    break
            if found is None:
                conditions.append({"status": "unknown", "tags": condition["tags"]})
            else:
                conditions.append(
                    {
                        "status": "matched"
                        if re.search(condition["pattern"], str(found["raw_value"]))
                        else "not_matched",
                        **found,
                    }
                )
        statuses = {condition["status"] for condition in conditions}
        status = (
            "not_matched"
            if "not_matched" in statuses
            else "unknown"
            if "unknown" in statuses
            else "matched"
        )
        effects = {effect["name"]: effect for effect in rule["apply"].get("fields", [])}
        if "capture_time" in rule["apply"]:
            effects["capture_time"] = rule["apply"]["capture_time"]
        for name, effect in effects.items():
            outputs.setdefault(name, []).append(
                {
                    "id": rule["id"],
                    "status": status,
                    "priority": rule.get("priority", 0),
                    "origin": entry["origin"],
                    **({"replaces": entry["replaces"]} if "replaces" in entry else {}),
                    "basis": rule["basis"],
                    "conditions": conditions,
                    "effect": effect,
                }
            )
    resolved = {}
    for name, candidates in outputs.items():
        matched = [
            candidate for candidate in candidates if candidate["status"] == "matched"
        ]
        priority = max((candidate["priority"] for candidate in matched), default=None)
        winners = [
            candidate for candidate in matched if candidate["priority"] == priority
        ]
        signatures = {
            _canonical(_effect_defaults(candidate["effect"], name))
            for candidate in winners
        }
        conflict = len(signatures) > 1
        trace = []
        for candidate in candidates:
            state = candidate["status"]
            if state == "matched":
                state = (
                    "shadowed"
                    if candidate not in winners
                    else "conflict"
                    if conflict
                    else "applied"
                )
            trace.append(
                {
                    key: value
                    for key, value in {**candidate, "status": state}.items()
                    if key != "effect"
                }
            )
        resolved[name] = {
            "effect": None
            if conflict or not winners
            else _effect_defaults(winners[0]["effect"], name),
            "conflict": conflict,
            "unknown": any(
                candidate["status"] == "unknown" for candidate in candidates
            ),
            "trace": {"snapshot_identity": snapshot.identity, "rules": trace},
            "declaration": candidates[0]["effect"]
            if name.startswith("manufacturer.")
            else None,
            "candidate_tags": list(
                dict.fromkeys(
                    tag
                    for candidate in candidates
                    for tag in candidate["effect"]["tags"]
                )
            ),
        }
    return resolved


def _effect_defaults(effect: dict[str, Any], name: str) -> dict[str, Any]:
    result = {"fallback": True, **effect}
    if name == "capture_time":
        shift = result.get("shift_seconds", 0)
        result["shift_seconds"] = (
            int(shift) if isinstance(shift, float) and shift.is_integer() else shift
        )
    elif name.startswith("manufacturer."):
        result.setdefault("unit", None)
    return result
