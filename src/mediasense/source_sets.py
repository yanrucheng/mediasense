"""Deterministic Frozen Plan Source Set resolution over PreCheck Read."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
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
        self._complete_source_views: set[str] = set()
        self._set_cache: dict[str, frozenset[str]] = {}

    def inspect(self, kind: str, ref: str) -> Mapping[str, Any]:
        if kind == "source_item":
            _require_ref(ref, _SOURCE_REF, "source_item_ref")
            if ref in self._complete_source_views:
                return self.source_views[ref]
            response = self._call(
                {
                    "result_ref": self.result_ref,
                    "operation": "expand",
                    "source_item_refs": [ref],
                    "include": ["source_item", "observations"],
                }
            )
            item = _single_item(response, "Source Item")
            if item.get("source_item_ref") != ref:
                raise SourceSetResolutionError(
                    f"PreCheck read returned the wrong Source Item for {ref}"
                )
            included = item.get("included")
            if not isinstance(included, Mapping):
                raise SourceSetResolutionError("Source Item expansion is incomplete")
            base = included.get("source_item")
            observations = included.get("observations")
            if not isinstance(base, Mapping) or not isinstance(observations, list):
                raise SourceSetResolutionError("Source Item expansion is incomplete")
            view = {**dict(base), "observations": observations}
            if view.get("kind") != "source_item" or view.get("ref") != ref:
                raise SourceSetResolutionError(f"unexpected source_item view for {ref}")
            self.source_views[ref] = view
            self._complete_source_views.add(ref)
            return view
        if kind == "evidence":
            _require_ref(ref, _EVIDENCE_REF, "evidence_ref")
            if ref in self.evidence_views:
                return self.evidence_views[ref]
            response = self._call(
                {
                    "result_ref": self.result_ref,
                    "operation": "expand",
                    "evidence_refs": [ref],
                    "include": ["anchor_evidence"],
                }
            )
            item = _single_item(response, "Evidence")
            if item.get("anchor_evidence_ref") != ref:
                raise SourceSetResolutionError(
                    f"PreCheck read returned the wrong Evidence for {ref}"
                )
            included = item.get("included")
            target = (
                included.get("anchor_evidence")
                if isinstance(included, Mapping)
                else None
            )
            if (
                not isinstance(target, Mapping)
                or target.get("kind") != "evidence"
                or target.get("ref") != ref
            ):
                raise SourceSetResolutionError(f"unexpected evidence view for {ref}")
            self.evidence_views[ref] = target
            return target
        raise SourceSetResolutionError(f"unsupported Result target kind: {kind}")

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
        expected_source_set_identity = _identity(key.encode("utf-8"))

        members: list[str] = []
        seen: set[str] = set()
        cursor: str | None = None
        seen_cursors: set[str] = set()
        expected_total: int | None = None
        source_set_identity: str | None = None
        membership_identity: str | None = None
        while True:
            request: dict[str, Any] = {
                "result_ref": self.result_ref,
                "operation": "resolve",
                "source_set": dict(source_set),
                "page": {"limit": 1000},
            }
            if cursor is not None:
                request["page"]["cursor"] = cursor
            response = self._call(request)
            if response.get("operation") != "resolve":
                raise SourceSetResolutionError(
                    "PreCheck read returned the wrong operation"
                )
            resolution = response.get("resolution")
            page = response.get("page")
            values = response.get("members")
            if (
                not isinstance(resolution, Mapping)
                or not isinstance(page, Mapping)
                or not isinstance(values, list)
            ):
                raise SourceSetResolutionError(
                    "PreCheck resolve response is structurally incomplete"
                )
            current_set_identity = resolution.get("source_set_identity")
            current_membership_identity = resolution.get("membership_identity")
            ordering = resolution.get("ordering")
            total = resolution.get("total")
            if (
                not isinstance(current_set_identity, str)
                or not isinstance(current_membership_identity, str)
                or ordering != "source_item_ref_ascending"
                or isinstance(total, bool)
                or not isinstance(total, int)
                or total < 0
            ):
                raise SourceSetResolutionError("PreCheck resolution identity is invalid")
            if current_set_identity != expected_source_set_identity:
                raise SourceSetResolutionError(
                    "PreCheck resolution does not match the requested Source Set"
                )
            if expected_total is None:
                expected_total = total
                source_set_identity = current_set_identity
                membership_identity = current_membership_identity
            elif (
                total != expected_total
                or current_set_identity != source_set_identity
                or current_membership_identity != membership_identity
            ):
                raise SourceSetResolutionError(
                    "PreCheck resolution changed between pages"
                )
            for value in values:
                if not isinstance(value, Mapping):
                    raise SourceSetResolutionError("Resolved member is not an object")
                ref = _require_ref(
                    value.get("source_item_ref"), _SOURCE_REF, "source_item_ref"
                )
                if ref in seen:
                    raise SourceSetResolutionError(
                        f"PreCheck resolution repeats Source Item {ref}"
                    )
                if members and ref < members[-1]:
                    raise SourceSetResolutionError(
                        "PreCheck resolution is not in declared Source Item order"
                    )
                seen.add(ref)
                members.append(ref)
                self.source_views.setdefault(ref, _resolved_member_view(value))

            returned = page.get("returned")
            page_total = page.get("total")
            complete = page.get("complete")
            if (
                isinstance(returned, bool)
                or not isinstance(returned, int)
                or returned != len(values)
                or page_total != expected_total
                or not isinstance(complete, bool)
            ):
                raise SourceSetResolutionError("PreCheck resolution page is invalid")
            if complete:
                if len(members) != expected_total or page.get("next_cursor") is not None:
                    raise SourceSetResolutionError(
                        "PreCheck resolution completed without its declared members"
                    )
                break
            next_cursor = page.get("next_cursor")
            if (
                not isinstance(next_cursor, str)
                or not next_cursor
                or next_cursor in seen_cursors
                or len(members) >= expected_total
            ):
                raise SourceSetResolutionError(
                    "PreCheck resolution did not make cursor progress"
                )
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        expected_membership_identity = _identity(
            json.dumps(
                {
                    "result_ref": self.result_ref,
                    "source_set": json.loads(key),
                    "members": members,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        if membership_identity != expected_membership_identity:
            raise SourceSetResolutionError(
                "PreCheck resolution membership identity does not match its members"
            )
        result = frozenset(members)
        self._set_cache[key] = result
        return result

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

    def _call(self, request: dict[str, Any]) -> Mapping[str, Any]:
        try:
            response = self.reader.read(request)
        except Exception as error:
            raise SourceSetResolutionError(
                "PreCheck read failed while resolving a Source Set"
            ) from error
        if not isinstance(response, Mapping):
            raise SourceSetResolutionError("PreCheck read returned a non-object response")
        if response.get("outcome") != "ok":
            error = response.get("error")
            code = error.get("code") if isinstance(error, Mapping) else "unknown_error"
            raise SourceSetResolutionError(f"PreCheck read failed: {code}")
        if response.get("result_ref") != self.result_ref:
            raise SourceSetResolutionError("PreCheck read crossed the bound Result")
        return response


def _single_item(response: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    items = response.get("items")
    if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], Mapping):
        raise SourceSetResolutionError(f"{label} expansion did not return one item")
    return items[0]


def _resolved_member_view(value: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = value.get("source_item_ref")
    view: dict[str, Any] = {
        "kind": "source_item",
        "ref": ref,
        "locator": value.get("locator"),
    }
    if value.get("qualifications"):
        view["qualifications"] = value["qualifications"]
    verification = value.get("source_content_verification")
    if isinstance(verification, Mapping):
        status = verification.get("status")
        observation: dict[str, Any] = {
            "name": "source_content_verification",
            "status": status,
        }
        projected = {
            key: item
            for key, item in verification.items()
            if key not in {"status", "basis", "qualifications"}
        }
        if projected:
            observation["value"] = projected
        for field in ("basis", "qualifications"):
            if field in verification:
                observation[field] = verification[field]
        view["observations"] = [observation]
    return view


def _require_ref(value: object, pattern: re.Pattern[str], label: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise SourceSetResolutionError(f"{label} has the wrong reference type")
    return value


def _identity(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


__all__ = [
    "ResultSourceSetResolver",
    "SourceSetResolutionError",
]
