"""Deterministic candidate materialization and validation.

The module interprets only the active Plan and PreCheck contracts.  It never
chooses semantic groups or names; those decisions arrive in candidate content.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator

from mediasense.frozen_plan import (
    FrozenPlanValidationError,
    content_identity,
)
from mediasense.precheck.read import PrecheckReadBoundary
from mediasense.source_sets import (
    ResultSourceSetResolver as ResultResolver,
    SourceSetResolutionError as ResultAccessError,
)


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


def materialize_candidate(
    candidate_content: Mapping[str, Any], *, plan_ref: str
) -> dict[str, Any]:
    content = {
        "contract": "mediasense.frozen-plan",
        "plan_ref": plan_ref,
        **deepcopy(dict(candidate_content)),
    }
    return content


def analyze_candidate(
    candidate_content: Mapping[str, Any],
    *,
    result_ref: str,
    plan_ref: str,
    reader: PrecheckReadBoundary,
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
        except (CandidateValidationError, FrozenPlanValidationError) as exc:
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
