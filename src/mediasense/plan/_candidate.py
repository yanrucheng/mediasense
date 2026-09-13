"""Deterministic candidate materialization and validation.

The module interprets only the active Plan and PreCheck contracts.  It never
chooses semantic groups or names; those decisions arrive in candidate content.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from mediasense.frozen_plan import (
    FrozenPlanValidationError,
    content_identity,
    load_frozen_plan_schema,
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


class _PlanResultResolver(ResultResolver):
    """Plan validates reference custody separately from image availability."""

    def _call(self, request):
        try:
            return super()._call(request)
        except ResultAccessError as error:
            # The shared resolver's legacy adapter wraps reader exceptions.
            # A programming failure is not an ordinary Plan validation issue.
            if error.__cause__ is not None:
                raise error.__cause__
            raise

    def inspect(self, kind, ref):
        try:
            return super().inspect(kind, ref)
        except ResultAccessError:
            if kind != "evidence":
                raise
            # Only the public selected-item evidence_unavailable result proves
            # that this reference exists but its local bytes cannot be delivered.
            # Unknown refs, Result failures and unexpected exceptions still fail.
            response = self._call(
                {
                    "action": "review",
                    "result_ref": self.result_ref,
                    "evidence_refs": [ref],
                    "page": {"limit": 1},
                }
            )
            items = response.get("items", [])
            if (
                len(items) == 1
                and items[0].get("evidence_ref") == ref
                and items[0].get("error", {}).get("code") == "evidence_unavailable"
                and response["page"]["next_cursor"] is None
            ):
                # This limited view supplies no image origin or attributes.
                return {"kind": "evidence", "ref": ref}
            raise


def materialize_candidate(
    candidate_content: Mapping[str, Any], *, plan_ref: str
) -> dict[str, Any]:
    if {"contract", "plan_ref", "seal"} & candidate_content.keys():
        raise CandidateValidationError("Candidate contains Tool-owned sealing fields")
    content = {
        **{k: deepcopy(v) for k, v in candidate_content.items() if k != "kind"},
        "contract": "mediasense.frozen-plan",
        "plan_ref": plan_ref,
    }
    return content


def analyze_candidate(
    candidate_content: Mapping[str, Any],
    *,
    result_ref: str,
    plan_ref: str,
    reader: PrecheckReadBoundary,
    schema_validator: Draft202012Validator,
    checkpoint: Callable[[], None] | None = None,
    progress: Callable[[str], None] | None = None,
) -> CandidateAnalysis:
    check = checkpoint or (lambda: None)

    def stage(name):
        check()
        if progress is not None:
            progress(name)
        check()

    def checked(values):
        for value in values:
            check()
            yield value

    stage("schema")
    # Validate the input representation, before adding Tool-owned fields or
    # traversing any nested value. A valid sealedContent is not a valid Candidate.
    issues = _schema_issues(candidate_content, _candidate_validator())
    sealed_content = {}
    if not issues:
        sealed_content = materialize_candidate(candidate_content, plan_ref=plan_ref)
        if candidate_content.get("kind") == "candidate":
            issues.extend(_schema_issues(sealed_content, schema_validator))
    if candidate_content.get("result_ref") != result_ref:
        issues.append(
            ValidationIssue(
                "result_binding_mismatch",
                "Candidate result_ref does not match the Working State.",
            )
        )
    if not issues:
        for index, outcome in enumerate(sealed_content["other_outcomes"]):
            if (
                outcome["outcome"] == "exclude_from_logical_organization"
                and not outcome["reason"].strip()
            ):
                issues.append(
                    ValidationIssue(
                        "missing_exclusion_reason",
                        f"other_outcomes[{index}] requires a concrete exclusion reason.",
                    )
                )
    if issues:
        check()
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

    resolver = _PlanResultResolver(result_ref, reader)
    try:
        stage("scope")
        scope = resolver.resolve(candidate_content["scope"])
        stage("groups")
        groups = tuple(
            tuple(sorted(resolver.resolve(group["members"])))
            for group in checked(candidate_content["groups"])
        )
        stage("representatives")
        group_representatives = tuple(
            resolver.representative_refs(group["members"], frozenset(members))
            for group, members in checked(
                zip(candidate_content["groups"], groups, strict=True)
            )
        )
        stage("outcomes")
        outcomes = tuple(
            tuple(sorted(resolver.resolve(outcome["members"])))
            for outcome in checked(candidate_content["other_outcomes"])
        )
        for outcome in checked(candidate_content["other_outcomes"]):
            for evidence_ref in checked(outcome.get("evidence_refs", [])):
                resolver.verify_evidence(evidence_ref)
        stage("decision_notes")
        for note in checked(candidate_content.get("decision_notes", [])):
            note_members = resolver.resolve(note["applies_to"])
            if not note_members <= scope:
                issues.append(
                    ValidationIssue(
                        "decision_note_outside_scope",
                        "A decision note applies to Source Items outside Plan scope.",
                    )
                )
            for evidence_ref in checked(note.get("evidence_refs", [])):
                resolver.verify_evidence(evidence_ref)
    except (CandidateValidationError, ResultAccessError) as exc:
        issues.append(ValidationIssue("result_resolution_failed", str(exc)))
        scope = frozenset()
        groups = ()
        group_representatives = ()
        outcomes = ()

    if scope:
        stage("partition")
        _validate_partition(
            scope,
            groups,
            outcomes,
            issues,
            checkpoint=check,
            require_complete=candidate_content["kind"] == "candidate",
        )
        stage("destinations")
        _validate_destinations(
            candidate_content,
            groups,
            resolver.source_views,
            issues,
            checkpoint=check,
        )
    elif not issues:
        issues.append(ValidationIssue("empty_scope", "Plan scope must be nonempty."))

    identity: str | None = None
    if not issues and candidate_content["kind"] == "candidate":
        stage("identity")
        try:
            identity = content_identity(sealed_content)
        except (CandidateValidationError, FrozenPlanValidationError) as exc:
            issues.append(ValidationIssue("invalid_encoding_profile", str(exc)))

    check()
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


@lru_cache(maxsize=1)
def _candidate_validator() -> Draft202012Validator:
    from mediasense.runtime.resources import load_contract

    inputs = load_contract("mediasense.plan.work")["inputSchema"]
    frozen = load_frozen_plan_schema()
    registry = Registry().with_resource(frozen["$id"], Resource.from_contents(frozen))
    return Draft202012Validator(
        {
            "$schema": inputs["$schema"],
            "$defs": inputs["$defs"],
            "$ref": "#/$defs/organization_content",
        },
        registry=registry,
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
    *,
    checkpoint: Callable[[], None] = lambda: None,
    require_complete: bool = True,
) -> None:
    assigned: set[str] = set()
    for label, collections in (("group", groups), ("outcome", outcomes)):
        for index, members in enumerate(collections):
            checkpoint()
            member_set = set(members)
            if not member_set:
                issues.append(
                    ValidationIssue(
                        "empty_membership", f"{label} {index} has no members."
                    )
                )
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
    if missing and require_complete:
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
    *,
    checkpoint: Callable[[], None] = lambda: None,
) -> None:
    paths: set[tuple[str, ...]] = set()
    directory_paths: set[tuple[str, ...]] = {(candidate["logical_root"],)}
    destinations: dict[tuple[str, ...], str] = {}
    root = candidate["logical_root"]
    for group in candidate["groups"]:
        checkpoint()
        relative = tuple(group["relative_path"])
        for depth in range(1, len(relative) + 1):
            directory_paths.add((root, *relative[:depth]))
    for index, (group, members) in enumerate(
        zip(candidate["groups"], groups, strict=True)
    ):
        checkpoint()
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
            checkpoint()
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
