from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).parents[1]
WORK_SPEC = ROOT / "docs" / "spec" / "contract/plan-work"
PLAN_SPEC = ROOT / "docs" / "spec" / "contract/frozen-plan"
READ_SPEC = ROOT / "docs" / "spec" / "contract/precheck-read"


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
    registry = Registry().with_resource(frozen["$id"], Resource.from_contents(frozen))
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

    name = "mediasense.precheck.read"

    def __init__(self) -> None:
        mock = load_json(ROOT / "tests/fixtures/plan-precheck-result.json")
        self.result_ref = mock["result_ref"]
        review = next(
            exchange["response"]
            for exchange in mock["exchanges"]
            if exchange["request"]["action"] == "review"
        )
        self.result = deepcopy(review["result"])
        self.review_response = deepcopy(review)
        self.source_views: dict[str, dict[str, Any]] = {}
        self.evidence_views: dict[str, dict[str, Any]] = {}
        self.relationships: dict[tuple[str, str], tuple[str, ...]] = {}
        self.calls: list[dict[str, Any]] = []
        for exchange in mock["exchanges"]:
            response = exchange["response"]
            if exchange["request"].get("action") == "expand":
                self._remember_expansion(response)
            if exchange["request"].get("action") == "resolve":
                source_set = exchange["request"]["source_set"]
                refs = tuple(item["source_item_ref"] for item in response["members"])
                if source_set.get("kind") == "precheck_relation":
                    self.relationships[
                        (source_set["origin"], source_set["relation"])
                    ] = refs
                for member in response["members"]:
                    self.source_views.setdefault(
                        member["source_item_ref"], _view_from_member(member)
                    )
        self.relationships[("evidence:repair-patched", "represents")] = (
            "source-item:217",
        )
        self.relationships[(self.result_ref, "accounts_for")] = tuple(
            sorted(self.source_views)
        )
        for card in review["items"]:
            ref = card["evidence_ref"]
            self.evidence_views.setdefault(ref, _synthetic_evidence(ref, card))
            represented = self.relationships.get((ref, "represents"), ())
            for refs in card.get("roles", {}).values():
                for evidence_ref in refs:
                    self.evidence_views.setdefault(
                        evidence_ref,
                        {
                            "kind": "evidence",
                            "ref": evidence_ref,
                            "access": {
                                "kind": "inline",
                                "value": {"mock": True},
                            },
                        },
                    )
                    if represented:
                        self.relationships.setdefault(
                            (evidence_ref, "represents"), represented
                        )

    def read(self, request: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(deepcopy(request))
        if request.get("result_ref") != self.result_ref:
            return _read_error(request, "result_not_found")
        operation = request.get("action")
        if operation == "review":
            return deepcopy(self.review_response)
        if operation == "geo_summary":
            return {
                "acquisition_status": "not_applicable",
                "coordinate_evidence": {
                    "gps": {},
                    "gpx": {},
                    "combined": {},
                },
                "coordinate_groups": [],
                "page": {
                    "total": 0,
                    "next_cursor": None,
                },
            }
        if operation == "expand":
            return self._expand(request)
        if operation == "resolve":
            return self._resolve(request)
        return _read_error(request, "invalid_request")

    def _remember_expansion(self, response: dict[str, Any]) -> None:
        for item in response.get("items", []):
            included = item.get("included", {})
            source = included.get("source_item")
            if isinstance(source, dict):
                view = deepcopy(source)
                view.update(kind="source_item", ref=item["source_item_ref"])
                view["observations"] = deepcopy(included.get("observations", []))
                self.source_views[view["ref"]] = view
            evidence = included.get("anchor_evidence")
            if isinstance(evidence, dict):
                self.evidence_views[item["evidence_ref"]] = {
                    **deepcopy(evidence),
                    "kind": "evidence",
                    "ref": item["evidence_ref"],
                }
            for prepared in included.get("prepared_targets", []):
                target = prepared.get("target", {})
                if target.get("kind") == "evidence":
                    ref = target["ref"]
                    self.evidence_views.setdefault(
                        ref,
                        {
                            "kind": "evidence",
                            "ref": ref,
                            "access": {"kind": "inline", "value": {"mock": True}},
                        },
                    )

    def _expand(self, request: dict[str, Any]) -> dict[str, Any]:
        items = []
        if "source_item_refs" in request:
            for ref in request["source_item_refs"]:
                view = self.source_views.get(ref)
                if view is None:
                    return _read_error(request, "reference_not_in_result")
                included = {}
                if "source_item" in request["include"]:
                    included["source_item"] = {
                        key: deepcopy(value)
                        for key, value in view.items()
                        if key not in {"observations", "kind", "ref"}
                    }
                if "observations" in request["include"]:
                    included["observations"] = deepcopy(view.get("observations", []))
                if "covering_evidence" in request["include"]:
                    included["covering_evidence"] = [
                        {"evidence_ref": origin}
                        for (origin, relation), refs in self.relationships.items()
                        if relation == "represents" and ref in refs
                    ]
                items.append({"source_item_ref": ref, "included": included})
        else:
            for ref in request.get("evidence_refs", []):
                view = self.evidence_views.get(ref)
                if view is None:
                    return _read_error(request, "reference_not_in_result")
                included = {}
                if "anchor_evidence" in request["include"]:
                    included["anchor_evidence"] = {
                        key: deepcopy(value)
                        for key, value in view.items()
                        if key not in {"kind", "ref"}
                    }
                    included["anchor_evidence"].setdefault("roles", [])
                    included["anchor_evidence"].setdefault("observations", [])
                if "prepared_targets" in request["include"]:
                    included["prepared_targets"] = []
                if "provenance" in request["include"]:
                    included["provenance"] = []
                if "coverage_basis" in request["include"]:
                    count = len(self.relationships.get((ref, "represents"), ()))
                    included["coverage_basis"] = {
                        "member_count": count,
                        "qualified_member_count": 0,
                        "qualification_groups": [],
                        "member_specific_basis": False,
                    }
                items.append({"evidence_ref": ref, "included": included})
        return {
            "items": items,
            "page": {
                "total": len(items),
                "next_cursor": None,
            },
        }

    def _resolve(self, request: dict[str, Any]) -> dict[str, Any]:
        try:
            refs = tuple(sorted(self._resolve_set(request["source_set"])))
        except (KeyError, ValueError):
            return _read_error(request, "invalid_source_set")
        members = [_member_from_view(self.source_views[ref]) for ref in refs]
        source_set_json = json.dumps(
            request["source_set"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        source_set_identity = (
            "sha256:" + hashlib.sha256(source_set_json.encode("utf-8")).hexdigest()
        )
        membership_payload = json.dumps(
            {
                "result_ref": self.result_ref,
                "source_set": json.loads(source_set_json),
                "members": refs,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        membership_identity = "sha256:" + hashlib.sha256(membership_payload).hexdigest()
        return {
            "resolution": {
                "source_set_identity": source_set_identity,
                "membership_identity": membership_identity,
            },
            "members": members,
            "page": {
                "total": len(members),
                "next_cursor": None,
            },
        }

    def _resolve_set(self, source_set: dict[str, Any]) -> set[str]:
        kind = source_set.get("kind")
        if kind == "explicit":
            refs = set(source_set["source_item_refs"])
        elif kind == "precheck_relation":
            refs = set(
                self.relationships[(source_set["origin"], source_set["relation"])]
            )
        elif kind == "union":
            refs = set().union(
                *(self._resolve_set(child) for child in source_set["sets"])
            )
        elif kind == "difference":
            refs = self._resolve_set(source_set["base"]) - self._resolve_set(
                source_set["subtract"]
            )
        else:
            raise ValueError(kind)
        if not refs <= self.source_views.keys():
            raise ValueError("source outside Result")
        return refs


class CountingPrecheckReader(MockPrecheckReader):
    @property
    def call_count(self) -> int:
        return len(self.calls)

    def reset(self) -> None:
        self.calls.clear()


class ResultOverrideReader(MockPrecheckReader):
    def __init__(self, **overrides: str) -> None:
        super().__init__()
        self.result.update(overrides)
        self.review_response["result"].update(overrides)


def _read_error(request: dict[str, Any], code: str) -> dict[str, Any]:
    return {
        "outcome": "error",
        "result_ref": request.get("result_ref", "precheck-result:missing"),
        "operation": request.get("operation", "unknown"),
        "error": {
            "code": code,
            "message": code.replace("_", " "),
            "retryable": False,
        },
    }


def _synthetic_evidence(ref: str, card: dict[str, Any]) -> dict[str, Any]:
    observations = deepcopy(card["observations"])
    return {
        "kind": "evidence",
        "ref": ref,
        "access": deepcopy(card["access"]),
        "observations": observations,
        "roles": [item["value"]["role"] for item in observations if item["name"] == "evidence_role"],
    }


def _view_from_member(member: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "source_item",
        "ref": member["source_item_ref"],
        "locator": deepcopy(member["locator"]),
        "observations": [],
    }


def _member_from_view(view: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_item_ref": view["ref"],
        "locator": deepcopy(view["locator"]),
        "scope": "source_media",
        "condition": "invalid" if view["ref"] == "source-item:215" else "usable",
        "source_content_verification": {"status": "not_checked"},
        **(
            {"qualifications": deepcopy(view["qualifications"])}
            if view.get("qualifications")
            else {}
        ),
    }
