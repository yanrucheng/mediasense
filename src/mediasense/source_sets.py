"""Deterministic Frozen Plan Source Set expansion over PreCheck Read."""

from __future__ import annotations

from collections.abc import Mapping
import json
import re
from typing import Any

from mediasense.precheck.read import (
    PrecheckReadBoundary,
    require_precheck_read_boundary,
)

_RESULT_REF = re.compile(r"^precheck-result:[^\s]+$")
_SOURCE_REF = re.compile(r"^source-item:[^\s]+$")
_EVIDENCE_REF = re.compile(r"^evidence:[^\s]+$")


class SourceSetResolutionError(RuntimeError):
    """A Source Set cannot be proven complete through the public read boundary."""


class ResultSourceSetResolver:
    """Resolve one Result's Source Sets without reading stage-private storage."""

    def __init__(self, result_ref: str, reader: PrecheckReadBoundary) -> None:
        self.result_ref = _require_ref(result_ref, _RESULT_REF, "result_ref")
        self.reader = require_precheck_read_boundary(reader)
        self.source_views: dict[str, Mapping[str, Any]] = {}
        self.evidence_views: dict[str, Mapping[str, Any]] = {}
        self._set_cache: dict[str, frozenset[str]] = {}

    def inspect(self, kind: str, ref: str) -> Mapping[str, Any]:
        if kind == "source_item":
            _require_ref(ref, _SOURCE_REF, "source_item_ref")
            cache = self.source_views
        elif kind == "evidence":
            _require_ref(ref, _EVIDENCE_REF, "evidence_ref")
            cache = self.evidence_views
        else:
            raise SourceSetResolutionError(f"unsupported Result target kind: {kind}")
        if ref in cache:
            return cache[ref]
        response = self._call(
            {
                "result_ref": self.result_ref,
                "action": "inspect",
                "target": {"kind": kind, "ref": ref},
            }
        )
        if response.get("action") != "inspect":
            raise SourceSetResolutionError("PreCheck read returned the wrong action")
        target = response.get("target")
        if not isinstance(target, Mapping) or target.get("kind") != kind:
            raise SourceSetResolutionError(f"unexpected {kind} view for {ref}")
        if target.get("ref") != ref:
            raise SourceSetResolutionError(
                f"Result returned the wrong target for {ref}"
            )
        cache[ref] = target
        return target

    def resolve(self, source_set: Mapping[str, Any]) -> frozenset[str]:
        if not isinstance(source_set, Mapping):
            raise SourceSetResolutionError("source set must be an object")
        try:
            key = json.dumps(
                dict(source_set),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (TypeError, ValueError) as error:
            raise SourceSetResolutionError(
                "source set is not JSON-compatible"
            ) from error
        cached = self._set_cache.get(key)
        if cached is not None:
            return cached

        kind = source_set.get("kind")
        if kind == "explicit":
            _require_keys(source_set, {"kind", "source_item_refs"})
            values = source_set.get("source_item_refs")
            if not isinstance(values, list) or not values:
                raise SourceSetResolutionError(
                    "explicit source set requires a non-empty source_item_refs array"
                )
            refs = tuple(
                _require_ref(value, _SOURCE_REF, "source_item_ref") for value in values
            )
            if len(set(refs)) != len(refs):
                raise SourceSetResolutionError(
                    "explicit source set repeats a Source Item"
                )
            members = frozenset(refs)
            for ref in refs:
                self.inspect("source_item", ref)
        elif kind == "precheck_relation":
            _require_keys(source_set, {"kind", "origin", "relation", "direction"})
            relation = source_set.get("relation")
            direction = source_set.get("direction")
            if direction != "outbound":
                raise SourceSetResolutionError(
                    "Frozen Plan relations require outbound traversal"
                )
            if relation == "accounts_for":
                origin = _require_ref(source_set.get("origin"), _RESULT_REF, "origin")
                if origin != self.result_ref:
                    raise SourceSetResolutionError(
                        "accounts_for origin does not match the bound Result"
                    )
            elif relation == "represents":
                origin = _require_ref(source_set.get("origin"), _EVIDENCE_REF, "origin")
                self.inspect("evidence", origin)
            else:
                raise SourceSetResolutionError(
                    f"unsupported Frozen Plan relation: {relation}"
                )
            members = self._traverse(origin, str(relation), "outbound")
        elif kind == "union":
            _require_keys(source_set, {"kind", "sets"})
            children = source_set.get("sets")
            if not isinstance(children, list) or len(children) < 2:
                raise SourceSetResolutionError("union requires at least two sets")
            expanded: set[str] = set()
            for child in children:
                if not isinstance(child, Mapping):
                    raise SourceSetResolutionError("union child must be a source set")
                expanded.update(self.resolve(child))
            members = frozenset(expanded)
        elif kind == "difference":
            _require_keys(source_set, {"kind", "base", "subtract"})
            base = source_set.get("base")
            subtract = source_set.get("subtract")
            if not isinstance(base, Mapping) or not isinstance(subtract, Mapping):
                raise SourceSetResolutionError(
                    "difference base and subtract must be source sets"
                )
            members = self.resolve(base) - self.resolve(subtract)
        else:
            raise SourceSetResolutionError(f"unsupported source-set kind: {kind}")

        self._set_cache[key] = members
        return members

    def verify_evidence(self, ref: str) -> None:
        self.inspect("evidence", ref)

    def representative_refs(
        self, source_set: Mapping[str, Any], members: frozenset[str]
    ) -> tuple[str, ...]:
        preferred: list[str] = []
        kind = source_set.get("kind")
        if kind == "explicit":
            values = source_set.get("source_item_refs")
            if isinstance(values, list):
                preferred.extend(item for item in values if isinstance(item, str))
        elif kind == "precheck_relation" and source_set.get("relation") == "represents":
            origin = source_set.get("origin")
            if isinstance(origin, str):
                evidence = self.inspect("evidence", origin)
                access = evidence.get("access")
                if isinstance(access, Mapping):
                    ref = access.get("source_item_ref")
                    if isinstance(ref, str):
                        preferred.append(ref)
        elif kind == "union":
            children = source_set.get("sets")
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, Mapping):
                        preferred.extend(
                            self.representative_refs(child, self.resolve(child))
                        )
        elif kind == "difference":
            base = source_set.get("base")
            if isinstance(base, Mapping):
                preferred.extend(self.representative_refs(base, self.resolve(base)))

        ordered: list[str] = []
        for ref in [*preferred, *sorted(members)]:
            if ref in members and ref not in ordered:
                ordered.append(ref)
        return tuple(ordered)

    def _traverse(self, origin: str, relation: str, direction: str) -> frozenset[str]:
        members: list[str] = []
        seen_members: set[str] = set()
        cursor: str | None = None
        seen_cursors: set[str] = set()
        expected_total: int | None = None
        while True:
            request: dict[str, Any] = {
                "result_ref": self.result_ref,
                "action": "traverse",
                "relation": relation,
                "direction": direction,
                "page": {"limit": 1000},
            }
            if origin != self.result_ref:
                request["target"] = origin
            if cursor is not None:
                request["page"]["cursor"] = cursor
            response = self._call(request)
            if response.get("action") != "traverse":
                raise SourceSetResolutionError(
                    "PreCheck read returned the wrong action"
                )
            if response.get("origin") != origin:
                raise SourceSetResolutionError(
                    f"Result returned the wrong origin for {origin}"
                )
            if (
                response.get("relation") != relation
                or response.get("direction") != direction
            ):
                raise SourceSetResolutionError(
                    "Result returned a different relationship"
                )
            items = response.get("items")
            page = response.get("page")
            if not isinstance(items, list) or not isinstance(page, Mapping):
                raise SourceSetResolutionError(
                    "Result traversal response is structurally incomplete"
                )
            returned = page.get("returned")
            total = page.get("total")
            complete = page.get("complete")
            if (
                isinstance(returned, bool)
                or not isinstance(returned, int)
                or returned != len(items)
                or isinstance(total, bool)
                or not isinstance(total, int)
                or total < 0
                or not isinstance(complete, bool)
            ):
                raise SourceSetResolutionError(
                    "Result traversal page accounting is invalid"
                )
            if expected_total is None:
                expected_total = total
            elif total != expected_total:
                raise SourceSetResolutionError(
                    "Result traversal total changed between pages"
                )
            for item in items:
                target = item.get("target") if isinstance(item, Mapping) else None
                ref = _require_ref(target, _SOURCE_REF, f"{relation} target")
                if ref in seen_members:
                    raise SourceSetResolutionError(
                        f"relationship {relation} repeats Source Item {ref}"
                    )
                seen_members.add(ref)
                members.append(ref)
            if len(members) > total:
                raise SourceSetResolutionError(
                    "Result traversal returned more members than declared"
                )
            if complete:
                if len(members) != total:
                    raise SourceSetResolutionError(
                        "Result traversal completed without its declared members"
                    )
                if page.get("next_cursor") is not None:
                    raise SourceSetResolutionError(
                        "complete Result traversal returned a continuation cursor"
                    )
                break
            next_cursor = page.get("next_cursor")
            if (
                not isinstance(next_cursor, str)
                or not next_cursor
                or next_cursor in seen_cursors
            ):
                raise SourceSetResolutionError(
                    "Result traversal did not make cursor progress"
                )
            if len(members) >= total:
                raise SourceSetResolutionError(
                    "incomplete Result traversal has no remaining declared members"
                )
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        for ref in members:
            self.inspect("source_item", ref)
        return frozenset(members)

    def _call(self, request: dict[str, Any]) -> Mapping[str, Any]:
        try:
            response = self.reader.read(request)
        except Exception as error:
            raise SourceSetResolutionError(
                "PreCheck read failed while resolving a Source Set"
            ) from error
        if not isinstance(response, Mapping) or response.get("outcome") != "ok":
            raise SourceSetResolutionError(f"PreCheck read failed for {request!r}")
        if response.get("result_ref") != self.result_ref:
            raise SourceSetResolutionError("PreCheck read crossed the bound Result")
        return response


def _require_keys(value: Mapping[str, Any], expected: set[str]) -> None:
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        raise SourceSetResolutionError(
            f"source set misses fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise SourceSetResolutionError(
            f"source set contains unsupported fields: {', '.join(sorted(unknown))}"
        )


def _require_ref(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise SourceSetResolutionError(f"{label} has the wrong reference type")
    return value


__all__ = [
    "ResultSourceSetResolver",
    "SourceSetResolutionError",
]
