from __future__ import annotations

from copy import deepcopy

import pytest

from mediasense.source_sets import (
    ResultSourceSetResolver,
    SourceSetResolutionError,
)


RESULT_REF = "precheck-result:source-sets"


class ContractReader:
    def __init__(self) -> None:
        self.sources = {
            ref: {"kind": "source_item", "ref": ref, "locator": {"kind": "test"}}
            for ref in ("source-item:a", "source-item:b", "source-item:c")
        }
        self.evidence = {
            "evidence:ab": {
                "kind": "evidence",
                "ref": "evidence:ab",
                "access": {"kind": "source_item", "source_item_ref": "source-item:a"},
            }
        }
        self.calls: list[dict] = []

    def __call__(self, request: dict) -> dict:
        self.calls.append(deepcopy(request))
        if request["action"] == "inspect":
            target = request["target"]
            values = self.sources if target["kind"] == "source_item" else self.evidence
            view = values.get(target["ref"])
            if view is None:
                return self._error("target_not_found")
            return {
                "outcome": "ok",
                "result_ref": RESULT_REF,
                "action": "inspect",
                "target": deepcopy(view),
            }
        origin = request.get("target", RESULT_REF)
        relation = request["relation"]
        cursor = request.get("page", {}).get("cursor")
        if relation == "accounts_for":
            items = (
                [{"target": "source-item:a"}, {"target": "source-item:b"}]
                if cursor is None
                else [{"target": "source-item:c"}]
            )
            page = (
                {"returned": 2, "total": 3, "complete": False, "next_cursor": "cursor:two"}
                if cursor is None
                else {"returned": 1, "total": 3, "complete": True}
            )
        else:
            items = [{"target": "source-item:a"}, {"target": "source-item:b"}]
            page = {"returned": 2, "total": 2, "complete": True}
        return {
            "outcome": "ok",
            "result_ref": RESULT_REF,
            "action": "traverse",
            "origin": origin,
            "relation": relation,
            "direction": request["direction"],
            "items": items,
            "page": page,
        }

    @staticmethod
    def _error(code: str) -> dict:
        return {
            "outcome": "error",
            "result_ref": RESULT_REF,
            "error": {"code": code, "message": code},
        }


def test_resolver_supports_all_frozen_plan_source_set_forms() -> None:
    resolver = ResultSourceSetResolver(RESULT_REF, ContractReader())
    explicit = {"kind": "explicit", "source_item_refs": ["source-item:c"]}
    accounts_for = {
        "kind": "precheck_relation",
        "origin": RESULT_REF,
        "relation": "accounts_for",
        "direction": "outbound",
    }
    represents = {
        "kind": "precheck_relation",
        "origin": "evidence:ab",
        "relation": "represents",
        "direction": "outbound",
    }
    union = {"kind": "union", "sets": [explicit, represents]}
    difference = {"kind": "difference", "base": accounts_for, "subtract": represents}

    assert resolver.resolve(explicit) == {"source-item:c"}
    assert resolver.resolve(accounts_for) == {
        "source-item:a",
        "source-item:b",
        "source-item:c",
    }
    assert resolver.resolve(represents) == {"source-item:a", "source-item:b"}
    assert resolver.resolve(union) == {
        "source-item:a",
        "source-item:b",
        "source-item:c",
    }
    assert resolver.resolve(difference) == {"source-item:c"}


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda response: response.update(result_ref="precheck-result:other"), "bound Result"),
        (
            lambda response: response["page"].update(total=4),
            "total changed",
        ),
        (
            lambda response: (
                response["items"].append(
                    {"target": response["items"][0]["target"]}
                ),
                response["page"].update(returned=2),
            ),
            "repeats Source Item",
        ),
        (
            lambda response: response.update(
                page={
                    "returned": 1,
                    "total": 3,
                    "complete": False,
                    "next_cursor": "cursor:two",
                }
            ),
            "cursor progress",
        ),
    ],
)
def test_resolver_fails_closed_on_untrustworthy_traversal(mutation, message) -> None:
    reader = ContractReader()
    original = reader.__call__

    def dishonest(request: dict) -> dict:
        response = original(request)
        if request["action"] == "traverse" and request.get("page", {}).get("cursor"):
            mutation(response)
        return response

    resolver = ResultSourceSetResolver(RESULT_REF, dishonest)
    expression = {
        "kind": "precheck_relation",
        "origin": RESULT_REF,
        "relation": "accounts_for",
        "direction": "outbound",
    }
    with pytest.raises(SourceSetResolutionError, match=message):
        resolver.resolve(expression)


def test_resolver_rejects_wrong_reference_type_and_explicit_duplicates() -> None:
    resolver = ResultSourceSetResolver(RESULT_REF, ContractReader())
    with pytest.raises(SourceSetResolutionError, match="wrong reference type"):
        resolver.resolve(
            {
                "kind": "precheck_relation",
                "origin": "source-item:a",
                "relation": "represents",
                "direction": "outbound",
            }
        )
    with pytest.raises(SourceSetResolutionError, match="repeats"):
        resolver.resolve(
            {
                "kind": "explicit",
                "source_item_refs": ["source-item:a", "source-item:a"],
            }
        )
