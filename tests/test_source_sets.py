from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from mediasense.source_sets import (
    ResultSourceSetResolver,
    SourceSetResolutionError,
)


RESULT_REF = "precheck-result:source-sets"


class ContractReader:
    name = "mediasense.precheck.read"

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

    def read(self, request: dict) -> dict:
        self.calls.append(deepcopy(request))
        if request["operation"] == "expand":
            items = []
            if "source_item_refs" in request:
                for ref in request["source_item_refs"]:
                    view = self.sources.get(ref)
                    if view is None:
                        return self._error("reference_not_in_result")
                    included = {}
                    if "source_item" in request["include"]:
                        included["source_item"] = deepcopy(view)
                    if "observations" in request["include"]:
                        included["observations"] = []
                    items.append({"source_item_ref": ref, "included": included})
            else:
                for ref in request["evidence_refs"]:
                    view = self.evidence.get(ref)
                    if view is None:
                        return self._error("reference_not_in_result")
                    included = {}
                    if "anchor_evidence" in request["include"]:
                        included["anchor_evidence"] = deepcopy(view)
                    items.append({"anchor_evidence_ref": ref, "included": included})
            return {
                "outcome": "ok",
                "result_ref": RESULT_REF,
                "operation": "expand",
                "items": items,
                "page": {
                    "returned": len(items),
                    "total": len(items),
                    "complete": True,
                    "stop_reason": "complete",
                },
            }
        if request["operation"] != "resolve":
            return self._error("invalid_request")
        try:
            resolved = sorted(self._resolve(request["source_set"]))
        except KeyError:
            return self._error("invalid_source_set")
        except ValueError as error:
            return self._error(
                "reference_not_in_result"
                if str(error) == "foreign"
                else "invalid_source_set"
            )
        cursor = request.get("page", {}).get("cursor")
        paged = request["source_set"].get("relation") == "accounts_for"
        if paged:
            refs = resolved[:2] if cursor is None else resolved[2:]
            page = (
                {
                    "returned": 2,
                    "total": 3,
                    "complete": False,
                    "next_cursor": "cursor:two",
                    "stop_reason": "byte_limit",
                }
                if cursor is None
                else {
                    "returned": 1,
                    "total": 3,
                    "complete": True,
                    "stop_reason": "complete",
                }
            )
        else:
            refs = resolved
            page = {
                "returned": len(refs),
                "total": len(refs),
                "complete": True,
                "stop_reason": "complete",
            }
        members = [
            {
                "source_item_ref": ref,
                "locator": deepcopy(self.sources[ref]["locator"]),
                "scope": "source_media",
                "condition": "usable",
                "source_content_verification": {"status": "not_checked"},
            }
            for ref in refs
        ]
        source_set_json = json.dumps(
            request["source_set"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        source_set_identity = _identity(source_set_json.encode("utf-8"))
        membership_identity = _identity(
            json.dumps(
                {
                    "result_ref": RESULT_REF,
                    "source_set": json.loads(source_set_json),
                    "members": resolved,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        return {
            "outcome": "ok",
            "result_ref": RESULT_REF,
            "operation": "resolve",
            "resolution": {
                "source_set_identity": source_set_identity,
                "membership_identity": membership_identity,
                "ordering": "source_item_ref_ascending",
                "total": len(resolved),
            },
            "members": members,
            "page": page,
        }

    def _resolve(self, source_set: dict) -> set[str]:
        kind = source_set["kind"]
        if kind == "explicit":
            refs = source_set["source_item_refs"]
            if len(refs) != len(set(refs)):
                raise ValueError("duplicate")
            if not set(refs) <= self.sources.keys():
                raise ValueError("foreign")
            return set(refs)
        if kind == "precheck_relation":
            relation = source_set["relation"]
            origin = source_set["origin"]
            if relation == "accounts_for" and origin == RESULT_REF:
                return set(self.sources)
            if relation == "represents" and origin == "evidence:ab":
                return {"source-item:a", "source-item:b"}
            raise ValueError("foreign")
        if kind == "union":
            return set().union(*(self._resolve(child) for child in source_set["sets"]))
        if kind == "difference":
            return self._resolve(source_set["base"]) - self._resolve(
                source_set["subtract"]
            )
        raise ValueError(kind)

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
        (
            lambda response: response.update(result_ref="precheck-result:other"),
            "bound Result",
        ),
        (
            lambda response: response["resolution"].update(
                source_set_identity="sha256:" + "f" * 64
            ),
            "requested Source Set",
        ),
        (
            lambda response: response["resolution"].update(
                membership_identity="sha256:" + "f" * 64
            ),
            "changed between pages",
        ),
        (
            lambda response: (
                response["resolution"].update(total=4),
                response["page"].update(total=4),
            ),
            "changed between pages",
        ),
        (
            lambda response: (
                response["members"].append(deepcopy(response["members"][0])),
                response["page"].update(returned=2),
            ),
            "repeats Source Item",
        ),
        (
            lambda response: response["members"][0].update(
                source_item_ref="source-item:aa"
            ),
            "declared Source Item order",
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
    original = reader.read

    class DishonestReader:
        name = "mediasense.precheck.read"

        def read(self, request: dict) -> dict:
            response = original(request)
            if request["operation"] == "resolve" and request.get("page", {}).get(
                "cursor"
            ):
                mutation(response)
            return response

    resolver = ResultSourceSetResolver(RESULT_REF, DishonestReader())
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
    with pytest.raises(SourceSetResolutionError, match="reference_not_in_result"):
        resolver.resolve(
            {
                "kind": "precheck_relation",
                "origin": "source-item:a",
                "relation": "represents",
                "direction": "outbound",
            }
        )
    with pytest.raises(SourceSetResolutionError, match="invalid_source_set"):
        resolver.resolve(
            {
                "kind": "explicit",
                "source_item_refs": ["source-item:a", "source-item:a"],
            }
        )


def _identity(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()
