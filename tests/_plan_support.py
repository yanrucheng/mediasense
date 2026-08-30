from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).parents[1]
WORK_SPEC = ROOT / "docs" / "spec" / "spec-260827-1915B-plan-work"
PLAN_SPEC = ROOT / "docs" / "spec" / "spec-260827-1138-frozen-plan"
READ_SPEC = ROOT / "docs" / "spec" / "spec-260826-1546-precheck-read"
GEO_SPEC = ROOT / "docs" / "spec" / "spec-260830-2034-geo-query"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def plan_mock() -> dict[str, Any]:
    return load_json(WORK_SPEC / "hong-kong.mock.json")


def valid_candidate() -> dict[str, Any]:
    for exchange in plan_mock()["exchanges"]:
        if (
            exchange["request"]["action"] == "update"
            and exchange["response"]["outcome"] == "ok"
        ):
            return deepcopy(exchange["request"]["candidate_content"])
    raise AssertionError("missing successful Plan update in Mock")


def validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    tool = load_json(WORK_SPEC / "plan-work.tool.json")
    frozen = load_json(PLAN_SPEC / "frozen-plan.schema.json")
    geo = load_json(GEO_SPEC / "geo-query.tool.json")
    registry = Registry().with_resource(frozen["$id"], Resource.from_contents(frozen))
    for resource in (geo["inputSchema"], geo["outputSchema"]):
        registry = registry.with_resource(
            resource["$id"], Resource.from_contents(resource)
        )
    return (
        Draft202012Validator(tool["inputSchema"], registry=registry),
        Draft202012Validator(tool["outputSchema"], registry=registry),
    )


class StableIdFactory:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def __call__(self, prefix: str) -> str:
        count = self.counts.get(prefix, 0) + 1
        self.counts[prefix] = count
        return f"{prefix}:test-{count}"


class MockPrecheckReader:
    """Contract-shaped reader assembled from the published PreCheck Mock."""

    def __init__(self) -> None:
        mock = load_json(READ_SPEC / "hong-kong.mock.json")
        self.result_ref = mock["result_ref"]
        self.views: dict[tuple[str, str], dict[str, Any]] = {}
        self.relationships: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        self.known_sources: set[str] = set()
        self.known_evidence: set[str] = set()
        self.calls: list[dict[str, Any]] = []
        for exchange in mock["exchanges"]:
            response = exchange["response"]
            target = response.get("target")
            if isinstance(target, dict) and isinstance(target.get("kind"), str):
                self.views[(target["kind"], target["ref"])] = deepcopy(target)
                self._remember(target["ref"])
                access = target.get("access")
                if isinstance(access, dict):
                    self._remember(access.get("source_item_ref"))
            if response.get("action") == "traverse":
                key = (
                    response["origin"],
                    response["relation"],
                    response["direction"],
                )
                bucket = self.relationships.setdefault(key, [])
                for item in response.get("items", []):
                    target_ref = item.get("target")
                    if isinstance(target_ref, dict):
                        target_ref = target_ref.get("ref")
                    self._remember(target_ref)
                    normalized = deepcopy(item)
                    if isinstance(normalized.get("target"), dict):
                        normalized["target"] = normalized["target"]["ref"]
                    if normalized not in bucket:
                        bucket.append(normalized)

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(deepcopy(request))
        if request.get("result_ref") != self.result_ref:
            return _read_error(request, "result_not_found")
        action = request.get("action")
        if action == "inspect":
            target = request.get("target")
            if target is None:
                return {
                    "outcome": "ok",
                    "result_ref": self.result_ref,
                    "action": "inspect",
                    "target": deepcopy(self.views[("result", self.result_ref)]),
                }
            key = (target["kind"], target["ref"])
            view = self.views.get(key)
            if view is None:
                view = self._synthetic_view(*key)
            if view is None:
                return _read_error(request, "target_not_found")
            return {
                "outcome": "ok",
                "result_ref": self.result_ref,
                "action": "inspect",
                "target": deepcopy(view),
            }
        if action == "traverse":
            origin = request.get("target", self.result_ref)
            key = (origin, request["relation"], request["direction"])
            items = deepcopy(self.relationships.get(key, []))
            if not items and key not in self.relationships:
                return _read_error(request, "relationship_not_found")
            return {
                "outcome": "ok",
                "result_ref": self.result_ref,
                "action": "traverse",
                "origin": origin,
                "relation": request["relation"],
                "direction": request["direction"],
                "items": items,
                "page": {"returned": len(items), "total": len(items), "complete": True},
            }
        return _read_error(request, "invalid_request")

    def _remember(self, ref: Any) -> None:
        if isinstance(ref, str) and ref.startswith("source-item:"):
            self.known_sources.add(ref)
        elif isinstance(ref, str) and ref.startswith("evidence:"):
            self.known_evidence.add(ref)

    def _synthetic_view(self, kind: str, ref: str) -> dict[str, Any] | None:
        if kind == "source_item" and ref in self.known_sources:
            suffix = ref.split(":", 1)[1]
            return {
                "kind": "source_item",
                "ref": ref,
                "locator": {
                    "kind": "fixture_relative_path",
                    "value": f"dataset/mock/item-{suffix}.jpg",
                },
                "observations": [
                    {
                        "name": "media_type",
                        "status": "available",
                        "value": "image/jpeg",
                        "basis": "Synthetic locator over a Source Item present in the published Mock relationship.",
                    }
                ],
            }
        if kind == "evidence" and ref in self.known_evidence:
            return {"kind": "evidence", "ref": ref}
        return None


class CountingPrecheckReader(MockPrecheckReader):
    @property
    def call_count(self) -> int:
        return len(self.calls)

    def reset(self) -> None:
        self.calls.clear()


class ResultOverrideReader(MockPrecheckReader):
    def __init__(self, **overrides: str) -> None:
        super().__init__()
        self.views[("result", self.result_ref)].update(overrides)


def _read_error(request: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "outcome": "error",
        "result_ref": request.get("result_ref", "precheck-result:missing"),
        "action": request.get("action", "inspect"),
        "error": {"code": code, "message": code.replace("_", " ")},
    }
