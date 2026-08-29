"""Deterministic candidate materialization and validation.

The module interprets only the active Plan and PreCheck contracts.  It never
chooses semantic groups or names; those decisions arrive in candidate content.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


PrecheckReader = Callable[[dict[str, Any]], Mapping[str, Any]]

_SOURCE_REF = re.compile(r"^source-item:[^\s]+$")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class CandidateAnalysis:
    sealed_content: dict[str, Any]
    content_identity: str | None
    scope_members: tuple[str, ...]
    group_members: tuple[tuple[str, ...], ...]
    group_representatives: tuple[tuple[str, ...], ...]
    outcome_members: tuple[tuple[str, ...], ...]
    source_views: Mapping[str, Mapping[str, Any]]
    issues: tuple[ValidationIssue, ...]

    @property
    def seal_ready(self) -> bool:
        return not self.issues and self.content_identity is not None


class CandidateValidationError(ValueError):
    """Raised when candidate structure prevents safe analysis."""


class ResultAccessError(RuntimeError):
    """Raised when the immutable Result cannot answer a required query."""


def canonical_strings_json(value: Any) -> str:
    """Serialize the first Frozen Plan encoding profile."""

    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(canonical_strings_json(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CandidateValidationError("JSON object keys must be strings")
        return (
            "{"
            + ",".join(
                canonical_strings_json(key) + ":" + canonical_strings_json(value[key])
                for key in sorted(value)
            )
            + "}"
        )
    raise CandidateValidationError(
        "mediasense-json-strings-sha256-v1 permits only objects, arrays, and strings"
    )


def content_identity(sealed_content: Mapping[str, Any]) -> str:
    canonical = canonical_strings_json(dict(sealed_content)).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def materialize_candidate(
    candidate_content: Mapping[str, Any], *, plan_ref: str
) -> dict[str, Any]:
    content = {
        "contract": "mediasense.frozen-plan",
        "plan_ref": plan_ref,
        **deepcopy(dict(candidate_content)),
    }
    return content


def load_frozen_content_validator(
    schema_path: Path | None = None,
) -> Draft202012Validator:
    """Load the authoritative Frozen Plan Schema without copying its rules."""

    path = schema_path or (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "spec"
        / "spec-260827-1138-frozen-plan"
        / "frozen-plan.schema.json"
    )
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    sealed_content_schema = {
        "$schema": schema["$schema"],
        "$defs": schema["$defs"],
        "$ref": "#/$defs/sealedContent",
    }
    return Draft202012Validator(sealed_content_schema)


def load_frozen_plan_validator(
    schema_path: Path | None = None,
) -> Draft202012Validator:
    """Load the complete immutable handoff schema for publication checks."""

    path = schema_path or (
        Path(__file__).resolve().parents[3]
        / "docs"
        / "spec"
        / "spec-260827-1138-frozen-plan"
        / "frozen-plan.schema.json"
    )
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


class ResultResolver:
    """Resolve Result-local source sets through the public read contract."""

    def __init__(self, result_ref: str, reader: PrecheckReader) -> None:
        self.result_ref = result_ref
        self.reader = reader
        self.source_views: dict[str, Mapping[str, Any]] = {}
        self.evidence_views: dict[str, Mapping[str, Any]] = {}
        self._set_cache: dict[str, frozenset[str]] = {}

    def inspect(self, kind: str, ref: str) -> Mapping[str, Any]:
        cache = self.source_views if kind == "source_item" else self.evidence_views
        if ref in cache:
            return cache[ref]
        response = self._call(
            {
                "result_ref": self.result_ref,
                "action": "inspect",
                "target": {"kind": kind, "ref": ref},
            }
        )
        target = response.get("target")
        if not isinstance(target, Mapping) or target.get("kind") != kind:
            raise ResultAccessError(f"unexpected {kind} view for {ref}")
        if target.get("ref") != ref:
            raise ResultAccessError(f"Result returned the wrong target for {ref}")
        cache[ref] = target
        return target

    def resolve(self, source_set: Mapping[str, Any]) -> frozenset[str]:
        key = canonical_strings_json(dict(source_set))
        cached = self._set_cache.get(key)
        if cached is not None:
            return cached

        kind = source_set["kind"]
        if kind == "explicit":
            members = frozenset(source_set["source_item_refs"])
            for ref in members:
                self.inspect("source_item", ref)
        elif kind == "precheck_relation":
            members = self._traverse(
                source_set["origin"],
                source_set["relation"],
                source_set["direction"],
            )
        elif kind == "union":
            expanded: set[str] = set()
            for member_set in source_set["sets"]:
                expanded.update(self.resolve(member_set))
            members = frozenset(expanded)
        elif kind == "difference":
            members = self.resolve(source_set["base"]) - self.resolve(
                source_set["subtract"]
            )
        else:  # pragma: no cover - guarded by structural validation
            raise CandidateValidationError(f"unsupported source-set kind: {kind}")

        self._set_cache[key] = members
        return members

    def verify_evidence(self, ref: str) -> None:
        self.inspect("evidence", ref)

    def representative_refs(
        self, source_set: Mapping[str, Any], members: frozenset[str]
    ) -> tuple[str, ...]:
        preferred: list[str] = []
        kind = source_set["kind"]
        if kind == "explicit":
            preferred.extend(source_set["source_item_refs"])
        elif kind == "precheck_relation" and source_set["relation"] == "represents":
            evidence = self.inspect("evidence", source_set["origin"])
            access = evidence.get("access")
            if isinstance(access, Mapping):
                ref = access.get("source_item_ref")
                if isinstance(ref, str):
                    preferred.append(ref)
        elif kind == "union":
            for child in source_set["sets"]:
                preferred.extend(self.representative_refs(child, self.resolve(child)))
        elif kind == "difference":
            base = source_set["base"]
            preferred.extend(self.representative_refs(base, self.resolve(base)))

        ordered: list[str] = []
        for ref in [*preferred, *sorted(members)]:
            if ref in members and ref not in ordered:
                ordered.append(ref)
        return tuple(ordered)

    def _traverse(self, origin: str, relation: str, direction: str) -> frozenset[str]:
        members: list[str] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
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
            if response.get("origin") != origin:
                raise ResultAccessError(
                    f"Result returned the wrong origin for {origin}"
                )
            if (
                response.get("relation") != relation
                or response.get("direction") != direction
            ):
                raise ResultAccessError("Result returned a different relationship")
            for item in response.get("items", []):
                target = item.get("target") if isinstance(item, Mapping) else None
                if not isinstance(target, str) or not _SOURCE_REF.fullmatch(target):
                    raise ResultAccessError(
                        f"relationship {relation} did not resolve to Source Items"
                    )
                members.append(target)
            page = response.get("page", {})
            if page.get("complete") is True:
                break
            cursor = page.get("next_cursor")
            if not isinstance(cursor, str) or cursor in seen_cursors:
                raise ResultAccessError("Result traversal did not make progress")
            seen_cursors.add(cursor)

        for ref in set(members):
            self.inspect("source_item", ref)
        return frozenset(members)

    def _call(self, request: dict[str, Any]) -> Mapping[str, Any]:
        response = self.reader(request)
        if not isinstance(response, Mapping) or response.get("outcome") != "ok":
            raise ResultAccessError(f"PreCheck read failed for {request!r}")
        if response.get("result_ref") != self.result_ref:
            raise ResultAccessError("PreCheck read crossed the bound Result")
        return response


def analyze_candidate(
    candidate_content: Mapping[str, Any],
    *,
    result_ref: str,
    plan_ref: str,
    reader: PrecheckReader,
    schema_validator: Draft202012Validator,
) -> CandidateAnalysis:
    sealed_content = materialize_candidate(candidate_content, plan_ref=plan_ref)
    issues = _schema_issues(sealed_content, schema_validator)
    if sealed_content.get("result_ref") != result_ref:
        issues.append(
            ValidationIssue(
                "result_binding_mismatch",
                "Candidate result_ref does not match the Working State.",
            )
        )
    for index, outcome in enumerate(sealed_content.get("other_outcomes", [])):
        if (
            outcome.get("outcome") == "exclude_from_logical_organization"
            and not str(outcome.get("reason", "")).strip()
        ):
            issues.append(
                ValidationIssue(
                    "missing_exclusion_reason",
                    f"other_outcomes[{index}] requires a concrete exclusion reason.",
                )
            )
    if issues:
        return CandidateAnalysis(
            sealed_content=sealed_content,
            content_identity=None,
            scope_members=(),
            group_members=(),
            group_representatives=(),
            outcome_members=(),
            source_views={},
            issues=tuple(issues),
        )

    resolver = ResultResolver(result_ref, reader)
    try:
        scope = resolver.resolve(candidate_content["scope"])
        groups = tuple(
            tuple(sorted(resolver.resolve(group["members"])))
            for group in candidate_content["groups"]
        )
        group_representatives = tuple(
            resolver.representative_refs(group["members"], frozenset(members))
            for group, members in zip(candidate_content["groups"], groups, strict=True)
        )
        outcomes = tuple(
            tuple(sorted(resolver.resolve(outcome["members"])))
            for outcome in candidate_content["other_outcomes"]
        )
        for outcome in candidate_content["other_outcomes"]:
            for evidence_ref in outcome.get("evidence_refs", []):
                resolver.verify_evidence(evidence_ref)
        for note in candidate_content.get("decision_notes", []):
            note_members = resolver.resolve(note["applies_to"])
            if not note_members <= scope:
                issues.append(
                    ValidationIssue(
                        "decision_note_outside_scope",
                        "A decision note applies to Source Items outside Plan scope.",
                    )
                )
            for evidence_ref in note.get("evidence_refs", []):
                resolver.verify_evidence(evidence_ref)
    except (CandidateValidationError, ResultAccessError, KeyError) as exc:
        issues.append(ValidationIssue("result_resolution_failed", str(exc)))
        scope = frozenset()
        groups = ()
        group_representatives = ()
        outcomes = ()

    if scope:
        _validate_partition(scope, groups, outcomes, issues)
        _validate_destinations(
            candidate_content,
            groups,
            resolver.source_views,
            issues,
        )
    elif not issues:
        issues.append(ValidationIssue("empty_scope", "Plan scope must be nonempty."))

    identity: str | None = None
    if not issues:
        try:
            identity = content_identity(sealed_content)
        except CandidateValidationError as exc:
            issues.append(ValidationIssue("invalid_encoding_profile", str(exc)))

    return CandidateAnalysis(
        sealed_content=sealed_content,
        content_identity=identity,
        scope_members=tuple(sorted(scope)),
        group_members=groups,
        group_representatives=group_representatives,
        outcome_members=outcomes,
        source_views=dict(resolver.source_views),
        issues=tuple(issues),
    )


def _schema_issues(
    sealed_content: Mapping[str, Any], validator: Draft202012Validator
) -> list[ValidationIssue]:
    errors = sorted(validator.iter_errors(dict(sealed_content)), key=_error_path)
    return [
        ValidationIssue(
            "schema_violation",
            f"{_format_error_path(error.absolute_path)}: {error.message}",
        )
        for error in errors
    ]


def _error_path(error: Any) -> tuple[str, ...]:
    return tuple(str(part) for part in error.absolute_path)


def _format_error_path(parts: Any) -> str:
    rendered = "$"
    for part in parts:
        rendered += f"[{part}]" if isinstance(part, int) else f".{part}"
    return rendered


def _validate_partition(
    scope: frozenset[str],
    groups: tuple[tuple[str, ...], ...],
    outcomes: tuple[tuple[str, ...], ...],
    issues: list[ValidationIssue],
) -> None:
    assigned: set[str] = set()
    for label, collections in (("group", groups), ("outcome", outcomes)):
        for index, members in enumerate(collections):
            member_set = set(members)
            overlap = assigned & member_set
            if overlap:
                issues.append(
                    ValidationIssue(
                        "overlapping_membership",
                        f"{label} {index} overlaps prior outcomes: {', '.join(sorted(overlap))}.",
                    )
                )
            outside = member_set - scope
            if outside:
                issues.append(
                    ValidationIssue(
                        "members_outside_scope",
                        f"{label} {index} contains items outside scope: {', '.join(sorted(outside))}.",
                    )
                )
            assigned.update(member_set)
    missing = scope - assigned
    if missing:
        issues.append(
            ValidationIssue(
                "incomplete_scope",
                f"Scoped items have no outcome: {', '.join(sorted(missing))}.",
            )
        )


def _validate_destinations(
    candidate: Mapping[str, Any],
    groups: tuple[tuple[str, ...], ...],
    source_views: Mapping[str, Mapping[str, Any]],
    issues: list[ValidationIssue],
) -> None:
    paths: set[tuple[str, ...]] = set()
    directory_paths: set[tuple[str, ...]] = {(candidate["logical_root"],)}
    destinations: dict[tuple[str, ...], str] = {}
    root = candidate["logical_root"]
    for group in candidate["groups"]:
        relative = tuple(group["relative_path"])
        for depth in range(1, len(relative) + 1):
            directory_paths.add((root, *relative[:depth]))
    for index, (group, members) in enumerate(
        zip(candidate["groups"], groups, strict=True)
    ):
        relative = tuple(group["relative_path"])
        if relative in paths:
            issues.append(
                ValidationIssue(
                    "duplicate_group_path", f"Group path {relative!r} is duplicated."
                )
            )
        paths.add(relative)
        overrides = {
            item["source_item_ref"]: item["name"]
            for item in group["source_naming"].get("overrides", [])
        }
        outside_overrides = set(overrides) - set(members)
        if outside_overrides:
            issues.append(
                ValidationIssue(
                    "override_outside_group",
                    f"Group {index} has overrides outside its membership: {', '.join(sorted(outside_overrides))}.",
                )
            )
        for ref in members:
            name = overrides.get(ref) or _source_basename(source_views.get(ref, {}))
            if not name:
                issues.append(
                    ValidationIssue(
                        "source_name_unavailable",
                        f"No source basename or override is available for {ref}.",
                    )
                )
                continue
            destination = (root, *relative, name)
            if destination in directory_paths:
                issues.append(
                    ValidationIssue(
                        "file_directory_collision",
                        f"{ref} resolves to {'/'.join(destination)}, which is also a logical directory.",
                    )
                )
            prior = destinations.get(destination)
            if prior is not None and prior != ref:
                issues.append(
                    ValidationIssue(
                        "destination_collision",
                        f"{prior} and {ref} resolve to the same destination {'/'.join(destination)}.",
                    )
                )
            destinations[destination] = ref


def _source_basename(view: Mapping[str, Any]) -> str | None:
    locator = view.get("locator")
    if not isinstance(locator, Mapping):
        return None
    value = locator.get("value")
    if not isinstance(value, str) or not value:
        return None
    return PurePosixPath(value.replace("\\", "/")).name or None
