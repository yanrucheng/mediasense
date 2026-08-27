from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
PLAN_SPEC = ROOT / "docs" / "spec" / "spec-260827-1138-frozen-plan"
PRECHECK_SPEC = ROOT / "docs" / "spec" / "spec-260826-1546-precheck-read"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_strings_json(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_canonical_strings_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            _canonical_strings_json(key) + ":" + _canonical_strings_json(value[key])
            for key in sorted(value)
        ) + "}"
    raise ValueError("profile permits only objects, arrays, and strings")


def _content_identity(content: dict) -> str:
    canonical = _canonical_strings_json(content).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


class Resolver:
    def __init__(
        self,
        *,
        result_ref: str,
        source_items: set[str],
        evidence_refs: set[str],
        relations: dict[tuple[str, str, str], tuple[set[str], bool]],
        basenames: dict[str, str],
    ) -> None:
        self.result_ref = result_ref
        self.source_items = source_items
        self.evidence_refs = evidence_refs
        self.relations = relations
        self.basenames = basenames

    def resolve_set(self, expression: dict) -> set[str]:
        kind = expression["kind"]
        if kind == "explicit":
            result = set(expression["source_item_refs"])
        elif kind == "precheck_relation":
            key = (
                expression["origin"],
                expression["relation"],
                expression["direction"],
            )
            if key not in self.relations:
                raise ValueError("referenced PreCheck relationship does not exist")
            result, complete = self.relations[key]
            if not complete:
                raise ValueError("referenced PreCheck relationship is not fully expandable")
            result = set(result)
        elif kind == "union":
            result = set().union(*(self.resolve_set(item) for item in expression["sets"]))
        elif kind == "difference":
            result = self.resolve_set(expression["base"]) - self.resolve_set(
                expression["subtract"]
            )
        else:
            raise ValueError(f"unknown set expression: {kind}")
        if not result <= self.source_items:
            raise ValueError("source set escapes the bound PreCheck Result")
        return result


def _validate_semantics(plan: dict, resolver: Resolver) -> None:
    content = plan["sealed_content"]
    if content["result_ref"] != resolver.result_ref:
        raise ValueError("wrong PreCheck Result")

    scope = resolver.resolve_set(content["scope"])
    if not scope:
        raise ValueError("scope is empty")

    outcomes: list[tuple[set[str], tuple[str, ...], dict]] = []
    for group in content["groups"]:
        members = resolver.resolve_set(group["members"])
        outcomes.append((members, tuple(group["relative_path"]), group))
    for outcome in content["other_outcomes"]:
        members = resolver.resolve_set(outcome["members"])
        outcomes.append((members, ("@other", outcome["outcome"]), outcome))

    accounted: set[str] = set()
    for members, _, _ in outcomes:
        if accounted & members:
            raise ValueError("undeclared repeated outcome")
        accounted |= members
    if accounted != scope:
        raise ValueError("outcomes do not exactly partition scope")

    group_paths = [path for _, path, _ in outcomes if path[0] != "@other"]
    if len(group_paths) != len(set(group_paths)):
        raise ValueError("duplicate logical group path")

    targets: set[tuple[tuple[str, ...], str]] = set()
    for members, path, record in outcomes:
        if path[0] == "@other":
            continue
        overrides = {
            item["source_item_ref"]: item["name"]
            for item in record["source_naming"].get("overrides", [])
        }
        if not set(overrides) <= members:
            raise ValueError("name override is outside its group")
        for source_item_ref in members:
            name = (
                overrides[source_item_ref]
                if source_item_ref in overrides
                else resolver.basenames[source_item_ref]
            )
            target = (path, name)
            if target in targets:
                raise ValueError("logical target collision")
            targets.add(target)

    for note in content.get("decision_notes", []):
        if not resolver.resolve_set(note["applies_to"]) <= scope:
            raise ValueError("decision note applies outside scope")
        if not set(note.get("evidence_refs", [])) <= resolver.evidence_refs:
            raise ValueError("decision note references unavailable Evidence")
    for outcome in content["other_outcomes"]:
        if not set(outcome.get("evidence_refs", [])) <= resolver.evidence_refs:
            raise ValueError("outcome references unavailable Evidence")

    seal = plan["seal"]
    identity = _content_identity(content)
    if seal["encoding_profile"] != "mediasense-json-strings-sha256-v1":
        raise ValueError("unsupported encoding profile")
    if seal["content_identity"] != identity:
        raise ValueError("content identity mismatch")
    if seal["final_confirmation"]["confirmed_content_identity"] != identity:
        raise ValueError("confirmation is not bound to exact content")


def _hong_kong_resolver() -> Resolver:
    precheck = _load(PRECHECK_SPEC / "hong-kong.mock.json")
    inspected = {
        exchange["response"]["target"]["ref"]: exchange["response"]["target"]
        for exchange in precheck["exchanges"]
        if exchange["response"].get("target", {}).get("kind") == "source_item"
    }
    basenames = {
        ref: target["locator"]["value"].rsplit("/", 1)[-1]
        for ref, target in inspected.items()
    }
    evidence_refs = {
        value
        for exchange in precheck["exchanges"]
        for value in _strings(exchange)
        if value.startswith("evidence:")
    }
    source_items = {
        value
        for exchange in precheck["exchanges"]
        for value in _strings(exchange)
        if value.startswith("source-item:")
    }
    relations = {}
    for exchange in precheck["exchanges"]:
        response = exchange["response"]
        if response.get("action") != "traverse":
            continue
        targets = {
            item["target"]
            for item in response.get("items", [])
            if isinstance(item.get("target"), str)
            and item["target"].startswith("source-item:")
        }
        if not targets:
            continue
        relations[
            (response["origin"], response["relation"], response["direction"])
        ] = (targets, response["page"]["complete"])
    return Resolver(
        result_ref=precheck["result_ref"],
        source_items=source_items,
        evidence_refs=evidence_refs,
        relations=relations,
        basenames=basenames,
    )


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _mock_plan() -> dict:
    return _load(PLAN_SPEC / "hong-kong.mock.json")["frozen_plan"]


def _reseal(plan: dict) -> None:
    identity = _content_identity(plan["sealed_content"])
    plan["seal"]["content_identity"] = identity
    plan["seal"]["final_confirmation"]["confirmed_content_identity"] = identity


def test_encoding_profile_has_independent_vectors() -> None:
    assert _canonical_strings_json({"z": ["雪", "\n"], "a": "x"}) == (
        '{"a":"x","z":["雪","\\n"]}'
    )
    assert _content_identity({"z": ["雪", "\n"], "a": "x"}) == (
        "sha256:87e05c0bfff59d2029c0e91818d1f2361300feeeaa190d140f4e5ce4eaf68bf1"
    )


def test_hong_kong_mock_is_closed_and_confirmed() -> None:
    _validate_semantics(_mock_plan(), _hong_kong_resolver())


def test_hong_kong_mock_reuses_complete_precheck_relation() -> None:
    plan = _mock_plan()
    resolver = _hong_kong_resolver()
    relation = plan["sealed_content"]["scope"]["sets"][0]
    assert relation == plan["sealed_content"]["groups"][0]["members"]
    assert resolver.resolve_set(relation) == {
        "source-item:13",
        "source-item:14",
        "source-item:15",
    }
    _validate_semantics(plan, resolver)


def test_scope_member_without_outcome_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["groups"] = []
    _reseal(plan)
    with pytest.raises(ValueError, match="partition scope"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_outcome_outside_scope_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["scope"] = {
        "kind": "explicit",
        "source_item_refs": ["source-item:215"],
    }
    _reseal(plan)
    with pytest.raises(ValueError, match="partition scope"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_repeated_outcome_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["groups"].append(
        deepcopy(plan["sealed_content"]["groups"][0])
    )
    plan["sealed_content"]["groups"][-1]["relative_path"] = ["Duplicate"]
    _reseal(plan)
    with pytest.raises(ValueError, match="repeated outcome"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_logical_name_collision_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["scope"] = {
        "kind": "explicit",
        "source_item_refs": ["source-item:215", "source-item:217"],
    }
    group = plan["sealed_content"]["groups"][0]
    group["members"] = {
        "kind": "explicit",
        "source_item_refs": ["source-item:215", "source-item:217"],
    }
    group["source_naming"]["overrides"] = [
        {"source_item_ref": "source-item:215", "name": "same.mp4"},
        {"source_item_ref": "source-item:217", "name": "same.mp4"},
    ]
    plan["sealed_content"]["groups"] = [group]
    plan["sealed_content"]["other_outcomes"] = []
    _reseal(plan)
    with pytest.raises(ValueError, match="target collision"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_duplicate_logical_group_path_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["scope"] = {
        "kind": "explicit",
        "source_item_refs": ["source-item:215", "source-item:217"],
    }
    first_group = deepcopy(plan["sealed_content"]["groups"][1])
    second_group = deepcopy(first_group)
    first_group["members"]["source_item_refs"] = [
        "source-item:215"
    ]
    second_group["members"]["source_item_refs"] = ["source-item:217"]
    plan["sealed_content"]["groups"] = [first_group, second_group]
    plan["sealed_content"]["other_outcomes"] = []
    _reseal(plan)
    with pytest.raises(ValueError, match="duplicate logical group path"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_reference_outside_bound_result_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["scope"]["sets"][1]["source_item_refs"].append(
        "source-item:missing"
    )
    _reseal(plan)
    with pytest.raises(ValueError, match="escapes the bound"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_evidence_outside_bound_result_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["decision_notes"][0]["evidence_refs"] = [
        "evidence:missing"
    ]
    _reseal(plan)
    with pytest.raises(ValueError, match="unavailable Evidence"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_incomplete_precheck_relation_is_rejected() -> None:
    plan = _mock_plan()
    relation = {
        "kind": "precheck_relation",
        "origin": "evidence:bundle61-entry",
        "relation": "represents",
        "direction": "outbound",
    }
    plan["sealed_content"]["scope"] = relation
    plan["sealed_content"]["groups"][0]["members"] = relation
    plan["sealed_content"]["other_outcomes"] = []
    resolver = _hong_kong_resolver()
    resolver.relations[("evidence:bundle61-entry", "represents", "outbound")] = (
        {"source-item:13", "source-item:14", "source-item:15"},
        False,
    )
    _reseal(plan)
    with pytest.raises(ValueError, match="not fully expandable"):
        _validate_semantics(plan, resolver)


def test_decision_note_outside_scope_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["decision_notes"][0]["applies_to"] = {
        "kind": "explicit",
        "source_item_refs": ["source-item:217"],
    }
    plan["sealed_content"]["scope"] = {
        "kind": "explicit",
        "source_item_refs": ["source-item:215"],
    }
    plan["sealed_content"]["groups"] = []
    _reseal(plan)
    with pytest.raises(ValueError, match="outside scope"):
        _validate_semantics(plan, _hong_kong_resolver())
