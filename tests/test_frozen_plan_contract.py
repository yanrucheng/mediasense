from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]
PLAN_SPEC = ROOT / "docs" / "spec" / "spec-260827-1138-frozen-plan"
PRECHECK_SPEC = ROOT / "docs" / "spec" / "spec-260826-1546-precheck-read"
PLAN_ARTIFACT_DESIGN = (
    ROOT / "docs" / "design" / "design-260828-2043-plan-local-artifacts"
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_strings_json(value) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_canonical_strings_json(item) for item in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(
                _canonical_strings_json(key) + ":" + _canonical_strings_json(value[key])
                for key in sorted(value)
            )
            + "}"
        )
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
                raise ValueError(
                    "referenced PreCheck relationship is not fully expandable"
                )
            result = set(result)
        elif kind == "union":
            result = set().union(
                *(self.resolve_set(item) for item in expression["sets"])
            )
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

    group_paths = [path for _, path, record in outcomes if "relative_path" in record]
    if len(group_paths) != len(set(group_paths)):
        raise ValueError("duplicate logical group path")

    directory_paths = {
        path[:depth] for path in group_paths for depth in range(1, len(path) + 1)
    }

    targets: set[tuple[tuple[str, ...], str]] = set()
    for members, path, record in outcomes:
        if "relative_path" not in record:
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
            if (*path, name) in directory_paths:
                raise ValueError("logical file and directory collision")
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
    inspected = {}
    for exchange in precheck["exchanges"]:
        response = exchange["response"]
        if exchange["request"].get("action") == "expand":
            for item in response.get("items", []):
                included = item.get("included", {})
                source = included.get("source_item")
                if isinstance(source, dict):
                    inspected[item["source_item_ref"]] = source
        if exchange["request"].get("action") == "resolve":
            for member in response.get("members", []):
                inspected.setdefault(
                    member["source_item_ref"],
                    {
                        "kind": "source_item",
                        "ref": member["source_item_ref"],
                        "locator": member["locator"],
                    },
                )
    for ref in ("source-item:211", "source-item:216"):
        inspected.setdefault(
            ref,
            {
                "kind": "source_item",
                "ref": ref,
                "locator": {
                    "kind": "source_root_relative_path",
                    "source_root_ref": "source-root:hk-representative-v1",
                    "value": f"dataset/mock/{ref.split(':', 1)[1]}.jpg",
                },
            },
        )
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
    source_items.update(inspected)
    relations = {}
    for exchange in precheck["exchanges"]:
        response = exchange["response"]
        if exchange["request"].get("action") != "resolve":
            continue
        targets = {item["source_item_ref"] for item in response.get("members", [])}
        if not targets:
            continue
        source_set = exchange["request"]["source_set"]
        relations[
            (source_set["origin"], source_set["relation"], source_set["direction"])
        ] = (
            targets,
            response["page"]["next_cursor"] is None,
        )
    review = next(
        exchange["response"]
        for exchange in precheck["exchanges"]
        if exchange["request"].get("action") == "review"
    )
    for card in review["cards"]:
        anchor_key = (card["evidence_ref"], "represents", "outbound")
        represented = relations.get(anchor_key)
        if represented is None:
            continue
        for role_refs in card["roles"].values():
            for evidence_ref in role_refs:
                relations.setdefault(
                    (evidence_ref, "represents", "outbound"), represented
                )
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


def test_local_artifact_example_is_closed_and_covers_profile_cases() -> None:
    plan = _load(PLAN_ARTIFACT_DESIGN / "example-plan.json")
    schema = _load(PLAN_SPEC / "frozen-plan.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(plan)
    _validate_semantics(plan, _hong_kong_resolver())

    content = plan["sealed_content"]
    scope = set(content["scope"]["source_item_refs"])
    groups = {
        tuple(group["relative_path"]): set(group["members"]["source_item_refs"])
        for group in content["groups"]
    }

    assert scope == set().union(*groups.values())
    assert groups[("260501-示例小事件",)] == {"source-item:14"}
    assert groups[("260501-示例复杂事件", "0503-示例章节", "1-关联媒体")] == {
        "source-item:13",
        "source-item:211",
    }
    assert groups[("260501-示例复杂事件", "0503-示例章节", "2-同行人物")] == {
        "source-item:15"
    }
    assert groups[("260501-示例复杂事件", "a-files", "repair-reference")] == {
        "source-item:216"
    }
    assert groups[("260501-示例复杂事件", "d-damaged-info")] == {"source-item:215"}
    assert groups[("260501-示例复杂事件", "0504-示例章节", "Uncategorized")] == {
        "source-item:217"
    }

    notes = "\n".join(note["summary"] for note in content["decision_notes"])
    assert "Fixture fact" in notes
    assert "Human-authored assumption" in notes


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
    first_group["members"]["source_item_refs"] = ["source-item:215"]
    second_group["members"]["source_item_refs"] = ["source-item:217"]
    plan["sealed_content"]["groups"] = [first_group, second_group]
    plan["sealed_content"]["other_outcomes"] = []
    _reseal(plan)
    with pytest.raises(ValueError, match="duplicate logical group path"):
        _validate_semantics(plan, _hong_kong_resolver())


def test_logical_file_and_directory_collision_is_rejected() -> None:
    plan = _mock_plan()
    plan["sealed_content"]["scope"] = {
        "kind": "explicit",
        "source_item_refs": ["source-item:215", "source-item:217"],
    }
    plan["sealed_content"]["groups"] = [
        {
            "relative_path": ["foo"],
            "members": {
                "kind": "explicit",
                "source_item_refs": ["source-item:215"],
            },
            "source_naming": {
                "default": "preserve_source_basename",
                "overrides": [{"source_item_ref": "source-item:215", "name": "bar"}],
            },
        },
        {
            "relative_path": ["foo", "bar"],
            "members": {
                "kind": "explicit",
                "source_item_refs": ["source-item:217"],
            },
            "source_naming": {"default": "preserve_source_basename"},
        },
    ]
    plan["sealed_content"]["other_outcomes"] = []
    plan["sealed_content"]["decision_notes"] = []
    _reseal(plan)
    with pytest.raises(ValueError, match="file and directory collision"):
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
    plan["sealed_content"]["decision_notes"][0]["evidence_refs"] = ["evidence:missing"]
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
