"""Consumer-oriented reads over one exact immutable PreCheck Result."""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Protocol, cast
from urllib.parse import quote

from ._working_schema import SCHEMA_VERSION


_MAX_RESPONSE_BYTES = 512 * 1024
_EVIDENCE_ROLES = ("representative", "boundary", "outlier", "conflict")
_OBSERVATION_STATES = (
    "available",
    "missing",
    "failed",
    "not_checked",
    "not_applicable",
)
_EVIDENCE_INCLUDES = {
    "anchor_evidence",
    "prepared_targets",
    "provenance",
    "coverage_basis",
    "member_observations",
}
_SOURCE_INCLUDES = {"source_item", "observations", "covering_evidence"}


class PrecheckReadBoundary(Protocol):
    """Process-local port for the public ``mediasense.precheck.read`` Tool."""

    name: str

    def read(self, request: dict[str, object]) -> dict[str, object]: ...


def require_precheck_read_boundary(value: object) -> PrecheckReadBoundary:
    """Reject incompatible local wiring before any stage operation starts."""

    if getattr(value, "name", None) != "mediasense.precheck.read" or not callable(
        getattr(value, "read", None)
    ):
        raise TypeError(
            "precheck_read must expose mediasense.precheck.read through read(request)"
        )
    return cast(PrecheckReadBoundary, value)


class _ReadFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.details = dict(details or {})


class _ResultGraph:
    def __init__(self, package: Mapping[str, object]) -> None:
        try:
            self.result = _mapping(package["result"], "Result view")
            self.dataset = _mapping(package["dataset"], "Dataset view")
            source_records = _sequence(package["sources"], "Source records")
            evidence_records = _sequence(package["evidence"], "Evidence records")
            self.relationships = tuple(
                _mapping(value, "relationship")
                for value in _sequence(package["relationships"], "relationships")
            )
            self.sources = _unique_views(source_records, "Source")
            self.evidence = _unique_views(evidence_records, "Evidence")
        except (KeyError, TypeError) as error:
            raise _ReadFailure(
                "result_inconsistent", "The sealed Result graph is structurally invalid."
            ) from error

        self.result_ref = str(self.result.get("ref", ""))
        self.by_origin_relation: dict[
            tuple[str, str], list[Mapping[str, object]]
        ] = defaultdict(list)
        for relationship in self.relationships:
            origin = relationship.get("origin")
            relation = relationship.get("relation")
            member = relationship.get("member")
            if (
                not isinstance(origin, str)
                or not isinstance(relation, str)
                or not isinstance(member, Mapping)
            ):
                raise _ReadFailure(
                    "result_inconsistent",
                    "The sealed Result contains an invalid relationship.",
                )
            self.by_origin_relation[(origin, relation)].append(member)

        self.accounts = self._unique_members(self.result_ref, "accounts_for")
        self.entry_evidence_refs = tuple(
            self._targets(self.result_ref, "entry_evidence")
        )
        if len(set(self.entry_evidence_refs)) != len(self.entry_evidence_refs):
            raise _ReadFailure(
                "result_inconsistent", "The entry Evidence frontier contains duplicates."
            )

    def members(self, origin: str, relation: str) -> tuple[Mapping[str, object], ...]:
        return tuple(self.by_origin_relation.get((origin, relation), ()))

    def _targets(self, origin: str, relation: str) -> list[str]:
        targets: list[str] = []
        for member in self.members(origin, relation):
            target = member.get("target")
            if not isinstance(target, str):
                raise _ReadFailure(
                    "result_inconsistent",
                    f"{relation} contains a non-reference target.",
                )
            targets.append(target)
        return targets

    def _unique_members(
        self, origin: str, relation: str
    ) -> dict[str, Mapping[str, object]]:
        result: dict[str, Mapping[str, object]] = {}
        for member in self.members(origin, relation):
            target = member.get("target")
            if not isinstance(target, str) or target in result:
                raise _ReadFailure(
                    "result_inconsistent",
                    f"{relation} contains an invalid or repeated target.",
                )
            result[target] = member
        return result


class PrecheckReadTool:
    """Implement ``review``, ``expand``, and ``resolve`` Result reads."""

    name = "mediasense.precheck.read"

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.workspace = self.database_path.parent.absolute()
        self._verify_schema()

    def read(self, request: dict[str, object]) -> dict[str, object]:
        result_ref = request.get("result_ref")
        operation = request.get("operation")
        try:
            if not isinstance(result_ref, str) or not result_ref:
                raise _ReadFailure(
                    "invalid_request", "result_ref must be a non-empty string."
                )
            if operation not in {"review", "expand", "resolve"}:
                raise _ReadFailure(
                    "invalid_request",
                    "operation must be review, expand, or resolve.",
                )
            package, result_digest = self._load(result_ref)
            graph = _ResultGraph(package)
            if graph.result_ref != result_ref:
                raise _ReadFailure(
                    "result_untrusted",
                    "The sealed Result identity does not match its reference.",
                )
            if operation == "review":
                return self._review(graph, result_digest, request)
            if operation == "expand":
                return self._expand(graph, result_digest, request)
            return self._resolve(graph, result_digest, request)
        except _ReadFailure as failure:
            return _error(
                result_ref if isinstance(result_ref, str) else None,
                operation if isinstance(operation, str) else None,
                failure,
            )

    def _load(self, result_ref: str) -> tuple[dict[str, object], str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sealed_results WHERE result_ref = ?", (result_ref,)
            ).fetchone()
            artifact_rows = (
                ()
                if row is None
                else tuple(
                    connection.execute(
                        """
                        SELECT artifacts.* FROM result_artifacts
                        JOIN artifacts USING (artifact_id)
                        WHERE result_ref = ? ORDER BY artifact_id
                        """,
                        (result_ref,),
                    )
                )
            )
        if row is None:
            raise _ReadFailure("result_not_found", "Result does not exist.")
        path = self.workspace / str(row["relative_path"])
        try:
            encoded = path.read_bytes()
        except OSError as error:
            raise _ReadFailure(
                "result_unavailable",
                "Sealed Result bytes are unavailable.",
                retryable=True,
            ) from error
        if (
            len(encoded) != int(row["size_bytes"])
            or hashlib.sha256(encoded).hexdigest() != row["digest"]
        ):
            raise _ReadFailure(
                "result_untrusted", "Sealed Result integrity verification failed."
            )
        try:
            package = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _ReadFailure(
                "result_untrusted", "Sealed Result cannot be decoded."
            ) from error
        if not isinstance(package, dict):
            raise _ReadFailure(
                "result_untrusted", "Sealed Result has an unsupported shape."
            )
        for artifact in artifact_rows:
            artifact_path = self.workspace / str(artifact["relative_path"])
            try:
                artifact_bytes = artifact_path.read_bytes()
            except OSError as error:
                raise _ReadFailure(
                    "result_untrusted",
                    f"Retained Artifact is unavailable: {artifact['artifact_id']}.",
                ) from error
            if (
                len(artifact_bytes) != int(artifact["size_bytes"])
                or hashlib.sha256(artifact_bytes).hexdigest() != artifact["digest"]
            ):
                raise _ReadFailure(
                    "result_untrusted",
                    f"Retained Artifact is corrupt: {artifact['artifact_id']}.",
                )
        return package, str(row["digest"])

    def _review(
        self,
        graph: _ResultGraph,
        result_digest: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        _require_keys(request, {"result_ref", "operation", "page"})
        query_key = "review:frontier_order"
        limit, offset = _page_request(
            request.get("page"),
            default=25,
            maximum=100,
            result_ref=graph.result_ref,
            result_digest=result_digest,
            operation="review",
            query_key=query_key,
        )
        reconciliation = _reconciliation(graph)
        cards = [_coverage_card(graph, ref) for ref in graph.entry_evidence_refs]
        base: dict[str, object] = {
            "outcome": "ok",
            "operation": "review",
            "result_ref": graph.result_ref,
            "result": dict(graph.result),
            "reconciliation": reconciliation,
        }
        return _paged_response(
            base,
            collection="coverage_cards",
            values=cards,
            offset=offset,
            limit=limit,
            result_ref=graph.result_ref,
            result_digest=result_digest,
            operation="review",
            query_key=query_key,
            page_extra={"order": "frontier_order"},
        )

    def _expand(
        self,
        graph: _ResultGraph,
        result_digest: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        _require_keys(
            request,
            {"result_ref", "operation", "evidence_refs", "source_item_refs", "include", "page"},
        )
        evidence_refs = request.get("evidence_refs")
        source_refs = request.get("source_item_refs")
        if (evidence_refs is None) == (source_refs is None):
            raise _ReadFailure(
                "invalid_request",
                "expand requires exactly one of evidence_refs or source_item_refs.",
            )
        refs = _ref_list(
            evidence_refs if evidence_refs is not None else source_refs,
            label="evidence_refs" if evidence_refs is not None else "source_item_refs",
            maximum=16,
        )
        include = _include_list(request.get("include"))
        if evidence_refs is not None:
            return self._expand_evidence(
                graph, result_digest, refs, include, request.get("page")
            )
        return self._expand_sources(graph, refs, include, request.get("page"))

    def _expand_evidence(
        self,
        graph: _ResultGraph,
        result_digest: str,
        refs: tuple[str, ...],
        include: tuple[str, ...],
        page_request: object,
    ) -> dict[str, object]:
        invalid = [ref for ref in refs if ref not in graph.evidence]
        if invalid:
            raise _ReadFailure(
                "reference_not_in_result",
                "Every evidence_ref must resolve inside the exact bound Result.",
                details={"invalid_inputs": invalid},
            )
        unsupported = sorted(set(include) - _EVIDENCE_INCLUDES)
        if unsupported:
            raise _ReadFailure(
                "unsupported_include",
                "One or more include values are not available for Evidence expansion.",
                details={
                    "unsupported": unsupported,
                    "available": sorted(_EVIDENCE_INCLUDES),
                },
            )

        if "member_observations" in include:
            if len(refs) != 1 or include != ("member_observations",):
                raise _ReadFailure(
                    "invalid_request",
                    "member_observations must be paged alone for one evidence_ref.",
                )
            ref = refs[0]
            member_refs = _represented_refs(graph, ref)
            query_key = _query_key(
                "expand-member-observations", {"evidence_refs": refs, "include": include}
            )
            limit, offset = _page_request(
                page_request,
                default=50,
                maximum=200,
                result_ref=graph.result_ref,
                result_digest=result_digest,
                operation="expand",
                query_key=query_key,
            )
            values = [
                {
                    "anchor_evidence_ref": ref,
                    "source_item": dict(graph.sources[source_ref]),
                }
                for source_ref in member_refs
            ]
            base = {
                "outcome": "ok",
                "operation": "expand",
                "result_ref": graph.result_ref,
            }
            return _paged_response(
                base,
                collection="items",
                values=values,
                offset=offset,
                limit=limit,
                result_ref=graph.result_ref,
                result_digest=result_digest,
                operation="expand",
                query_key=query_key,
            )
        if page_request is not None:
            raise _ReadFailure(
                "invalid_request",
                "page is supported only for member_observations expansion.",
            )

        items = []
        for ref in refs:
            included: dict[str, object] = {}
            if "anchor_evidence" in include:
                included["anchor_evidence"] = _evidence_detail(graph, ref)
            if "prepared_targets" in include:
                included["prepared_targets"] = [
                    _prepared_target(graph, member)
                    for member in graph.members(ref, "expands_to")
                ]
            if "provenance" in include:
                included["provenance"] = [
                    _prepared_target(graph, member)
                    for member in graph.members(ref, "derived_from")
                ]
            if "coverage_basis" in include:
                included["coverage_basis"] = _coverage_basis(graph, ref)
            items.append({"anchor_evidence_ref": ref, "included": included})
        response: dict[str, object] = {
            "outcome": "ok",
            "operation": "expand",
            "result_ref": graph.result_ref,
            "items": items,
            "page": {
                "returned": len(items),
                "total": len(items),
                "complete": True,
                "stop_reason": "complete",
            },
        }
        _ensure_response_size(response)
        return response

    def _expand_sources(
        self,
        graph: _ResultGraph,
        refs: tuple[str, ...],
        include: tuple[str, ...],
        page_request: object,
    ) -> dict[str, object]:
        if page_request is not None:
            raise _ReadFailure(
                "invalid_request", "Source Item expansion does not accept page."
            )
        invalid = [ref for ref in refs if ref not in graph.sources]
        if invalid:
            raise _ReadFailure(
                "reference_not_in_result",
                "Every source_item_ref must resolve inside the exact bound Result.",
                details={"invalid_inputs": invalid},
            )
        unsupported = sorted(set(include) - _SOURCE_INCLUDES)
        if unsupported:
            raise _ReadFailure(
                "unsupported_include",
                "One or more include values are not available for Source Item expansion.",
                details={
                    "unsupported": unsupported,
                    "available": sorted(_SOURCE_INCLUDES),
                },
            )
        items = []
        for ref in refs:
            view = graph.sources[ref]
            included: dict[str, object] = {}
            if "source_item" in include:
                included["source_item"] = {
                    key: value
                    for key, value in view.items()
                    if key != "observations"
                }
            if "observations" in include:
                included["observations"] = list(view.get("observations", ()))
            if "covering_evidence" in include:
                included["covering_evidence"] = _covering_evidence(graph, ref)
            items.append({"source_item_ref": ref, "included": included})
        response: dict[str, object] = {
            "outcome": "ok",
            "operation": "expand",
            "result_ref": graph.result_ref,
            "items": items,
            "page": {
                "returned": len(items),
                "total": len(items),
                "complete": True,
                "stop_reason": "complete",
            },
        }
        _ensure_response_size(response)
        return response

    def _resolve(
        self,
        graph: _ResultGraph,
        result_digest: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        _require_keys(request, {"result_ref", "operation", "source_set", "page"})
        source_set = request.get("source_set")
        if not isinstance(source_set, Mapping):
            raise _ReadFailure("invalid_source_set", "source_set must be an object.")
        canonical_source_set = _canonical_json(source_set)
        source_set_identity = _sha256_identity(canonical_source_set.encode("utf-8"))
        refs = tuple(sorted(_resolve_source_set(graph, source_set)))
        membership_payload = _canonical_json(
            {
                "result_ref": graph.result_ref,
                "source_set": json.loads(canonical_source_set),
                "members": refs,
            }
        ).encode("utf-8")
        membership_identity = _sha256_identity(membership_payload)
        query_key = _query_key(
            "resolve",
            {
                "source_set_identity": source_set_identity,
                "membership_identity": membership_identity,
            },
        )
        limit, offset = _page_request(
            request.get("page"),
            default=250,
            maximum=1000,
            result_ref=graph.result_ref,
            result_digest=result_digest,
            operation="resolve",
            query_key=query_key,
        )
        values = [_resolved_member(graph, ref) for ref in refs]
        base: dict[str, object] = {
            "outcome": "ok",
            "operation": "resolve",
            "result_ref": graph.result_ref,
            "resolution": {
                "source_set_identity": source_set_identity,
                "membership_identity": membership_identity,
                "ordering": "source_item_ref_ascending",
                "total": len(values),
            },
        }
        return _paged_response(
            base,
            collection="members",
            values=values,
            offset=offset,
            limit=limit,
            result_ref=graph.result_ref,
            result_digest=result_digest,
            operation="resolve",
            query_key=query_key,
        )

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
            except sqlite3.OperationalError as error:
                raise RuntimeError(
                    "initialize the PreCheck working store before PrecheckReadTool"
                ) from error
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported or uninitialized internal schema")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        uri = f"file:{quote(str(self.database_path.absolute()))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=30)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()


def _reconciliation(graph: _ResultGraph) -> dict[str, object]:
    accounted = set(graph.accounts)
    membership_count = 0
    frontier: set[str] = set()
    for ref in graph.entry_evidence_refs:
        if ref not in graph.evidence:
            raise _ReadFailure(
                "result_inconsistent", "The frontier references missing Evidence."
            )
        represented = _represented_refs(graph, ref)
        membership_count += len(represented)
        frontier.update(represented)
    outside = frontier - accounted
    if outside:
        raise _ReadFailure(
            "result_inconsistent",
            "Frontier Evidence represents Source Items outside Result accounting.",
        )
    exceptions = {
        ref
        for ref, member in graph.accounts.items()
        if member.get("scope") != "source_media"
        or member.get("condition") != "usable"
        or bool(member.get("qualifications"))
    }
    frontier_only = frontier - exceptions
    exception_only = exceptions - frontier
    both = frontier & exceptions
    residual = accounted - frontier - exceptions
    if graph.result.get("coverage") == "complete" and residual:
        raise _ReadFailure(
            "result_inconsistent",
            "A complete Result has Source Items outside its frontier and exception routes.",
            details={"residual_count": len(residual)},
        )
    route_counts = Counter(
        (
            str(graph.accounts[ref].get("scope")),
            str(graph.accounts[ref].get("condition")),
        )
        for ref in sorted(exception_only)
    )
    right = len(frontier_only) + len(exception_only) + len(both) + len(residual)
    return {
        "accounted_total": len(accounted),
        "partition": {
            "frontier_only": len(frontier_only),
            "exception_only": len(exception_only),
            "frontier_and_exception": len(both),
            "residual": len(residual),
        },
        "frontier": {
            "entry_evidence_count": len(graph.entry_evidence_refs),
            "coverage_memberships": membership_count,
            "represented_unique_source_items": len(frontier),
            "overlap_count": membership_count - len(frontier),
        },
        "exception_routes": [
            {"scope": scope, "condition": condition, "count": count}
            for (scope, condition), count in sorted(route_counts.items())
        ],
        "closure_check": {
            "status": "passed" if not residual else "partial",
            "equation": {"left": len(accounted), "right": right},
        },
    }


def _coverage_card(graph: _ResultGraph, ref: str) -> dict[str, object]:
    evidence = graph.evidence.get(ref)
    if evidence is None:
        raise _ReadFailure("result_inconsistent", "Frontier Evidence is missing.")
    member_refs = _represented_refs(graph, ref)
    accounts = Counter(
        (
            str(graph.accounts[source_ref].get("scope")),
            str(graph.accounts[source_ref].get("condition")),
        )
        for source_ref in member_refs
    )
    prepared = graph.members(ref, "expands_to")
    role_refs: dict[str, list[str]] = {role: [] for role in _EVIDENCE_ROLES}
    for evidence_ref in [ref, *list(_prepared_evidence_refs(prepared))]:
        if evidence_ref not in graph.evidence:
            raise _ReadFailure(
                "result_inconsistent", "Prepared Evidence is missing from the Result."
            )
        for role in _evidence_roles(graph.evidence[evidence_ref]):
            if evidence_ref not in role_refs[role]:
                role_refs[role].append(evidence_ref)
    prepared_evidence = tuple(_prepared_evidence_refs(prepared))
    assigned = {item for values in role_refs.values() for item in values}
    qualifications = _qualification_summary(graph, ref, prepared_evidence)
    other_observations = any(
        observation.get("name") not in {"capture_time", "media_type"}
        for source_ref in member_refs
        for observation in _observations(graph.sources[source_ref])
    ) or any(
        observation.get("name") != "evidence_role"
        for evidence_ref in (ref, *prepared_evidence)
        for observation in _observations(graph.evidence[evidence_ref])
    )
    return {
        "anchor_evidence_ref": ref,
        "anchor_access": evidence.get("access"),
        "represented": {
            "relationship": "represents",
            "membership_count": len(member_refs),
            "unique_source_item_count": len(set(member_refs)),
            "scope_condition": [
                {"scope": scope, "condition": condition, "count": count}
                for (scope, condition), count in sorted(accounts.items())
            ],
        },
        "projected_facts": {
            "capture_time": _capture_time_projection(graph, member_refs),
            "media_type": _media_type_projection(graph, member_refs),
        },
        "evidence_roles": role_refs,
        "unassigned_prepared_evidence": [
            evidence_ref
            for evidence_ref in prepared_evidence
            if evidence_ref not in assigned
        ],
        "qualification_summary": qualifications,
        "projection_scope": {
            "projected_observations": [
                "capture_time",
                "media_type",
                "evidence_role",
            ],
            "other_observations_available": other_observations,
        },
        "available_expansions": [
            {"include": "anchor_evidence", "estimated_items": 1},
            {"include": "prepared_targets", "estimated_items": len(prepared)},
            {
                "include": "provenance",
                "estimated_items": len(graph.members(ref, "derived_from")),
            },
            {"include": "coverage_basis", "estimated_items": len(member_refs)},
            {"include": "member_observations", "estimated_items": len(member_refs)},
        ],
        "resolvable_source_set": {
            "kind": "precheck_relation",
            "origin": ref,
            "relation": "represents",
            "direction": "outbound",
        },
    }


def _represented_refs(graph: _ResultGraph, evidence_ref: str) -> tuple[str, ...]:
    refs: list[str] = []
    seen: set[str] = set()
    for member in graph.members(evidence_ref, "represents"):
        target = member.get("target")
        if not isinstance(target, str) or target not in graph.sources or target in seen:
            raise _ReadFailure(
                "result_inconsistent",
                "A represents relationship has an invalid or repeated Source Item.",
            )
        if target not in graph.accounts:
            raise _ReadFailure(
                "result_inconsistent",
                "A represents relationship escapes Result accounting.",
            )
        seen.add(target)
        refs.append(target)
    return tuple(refs)


def _capture_time_projection(
    graph: _ResultGraph, member_refs: Sequence[str]
) -> dict[str, object]:
    states = Counter({state: 0 for state in _OBSERVATION_STATES})
    states["unreported"] = 0
    available: list[tuple[datetime, str]] = []
    for ref in member_refs:
        observation = _one_observation(graph.sources[ref], "capture_time")
        if observation is None:
            states["unreported"] += 1
            continue
        status = observation.get("status")
        if status not in _OBSERVATION_STATES:
            raise _ReadFailure(
                "result_inconsistent", "capture_time has an unsupported status."
            )
        states[str(status)] += 1
        if status == "available":
            value = observation.get("value")
            if not isinstance(value, str):
                raise _ReadFailure(
                    "result_inconsistent", "Available capture_time is not a timestamp."
                )
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as error:
                raise _ReadFailure(
                    "result_inconsistent", "Available capture_time is not RFC 3339."
                ) from error
            if parsed.tzinfo is None:
                raise _ReadFailure(
                    "result_inconsistent", "Available capture_time has no UTC offset."
                )
            available.append((parsed, value))
    result: dict[str, object] = {"status_counts": dict(states)}
    if available:
        result["earliest"] = min(available, key=lambda item: item[0])[1]
        result["latest"] = max(available, key=lambda item: item[0])[1]
    return result


def _media_type_projection(
    graph: _ResultGraph, member_refs: Sequence[str]
) -> dict[str, object]:
    states = Counter({state: 0 for state in _OBSERVATION_STATES})
    states["unreported"] = 0
    values: Counter[str] = Counter()
    for ref in member_refs:
        observation = _one_observation(graph.sources[ref], "media_type")
        if observation is None:
            states["unreported"] += 1
            continue
        status = observation.get("status")
        if status not in _OBSERVATION_STATES:
            raise _ReadFailure(
                "result_inconsistent", "media_type has an unsupported status."
            )
        states[str(status)] += 1
        if status == "available":
            value = observation.get("value")
            if not isinstance(value, str) or "/" not in value:
                raise _ReadFailure(
                    "result_inconsistent", "Available media_type is not a MIME type."
                )
            values[value.lower()] += 1
    return {
        "status_counts": dict(states),
        "values": [
            {"value": value, "count": count} for value, count in sorted(values.items())
        ],
    }


def _qualification_summary(
    graph: _ResultGraph, anchor_ref: str, prepared_refs: Sequence[str]
) -> list[dict[str, object]]:
    grouped: dict[str, tuple[str, Mapping[str, object], int]] = {}

    def add(applies_to: str, qualification: Mapping[str, object]) -> None:
        key = applies_to + ":" + _canonical_json(qualification)
        current = grouped.get(key)
        grouped[key] = (applies_to, qualification, 1 if current is None else current[2] + 1)

    for qualification in _qualifications(graph.evidence[anchor_ref]):
        add("anchor_evidence", qualification)
    for prepared_ref in prepared_refs:
        for qualification in _qualifications(graph.evidence[prepared_ref]):
            add("prepared_evidence", qualification)
    for member in graph.members(anchor_ref, "represents"):
        for qualification in _qualifications(member):
            add("represents_member", qualification)
    return [
        {"applies_to": applies_to, **dict(qualification), "occurrences": count}
        for applies_to, qualification, count in (
            grouped[key] for key in sorted(grouped)
        )
    ]


def _coverage_basis(graph: _ResultGraph, ref: str) -> dict[str, object]:
    members = graph.members(ref, "represents")
    qualified = sum(bool(member.get("qualifications")) for member in members)
    return {
        "relationship": "represents",
        "member_count": len(members),
        "unqualified_member_count": len(members) - qualified,
        "qualified_member_count": qualified,
        "qualification_groups": _qualification_summary_for_members(members),
        "member_specific_basis": any("basis" in member for member in members),
    }


def _qualification_summary_for_members(
    members: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    grouped: dict[str, tuple[Mapping[str, object], int]] = {}
    for member in members:
        for qualification in _qualifications(member):
            key = _canonical_json(qualification)
            current = grouped.get(key)
            grouped[key] = (qualification, 1 if current is None else current[1] + 1)
    return [
        {**dict(qualification), "occurrences": count}
        for qualification, count in (grouped[key] for key in sorted(grouped))
    ]


def _evidence_detail(graph: _ResultGraph, ref: str) -> dict[str, object]:
    view = graph.evidence[ref]
    return {**dict(view), "roles": list(_evidence_roles(view))}


def _prepared_target(
    graph: _ResultGraph, member: Mapping[str, object]
) -> dict[str, object]:
    target = member.get("target")
    if not isinstance(target, Mapping):
        raise _ReadFailure(
            "result_inconsistent", "An expands_to target is not typed."
        )
    kind = target.get("kind")
    ref = target.get("ref")
    if not isinstance(ref, str) or kind not in {"source_item", "evidence"}:
        raise _ReadFailure(
            "result_inconsistent", "An expands_to target has an invalid reference."
        )
    result: dict[str, object] = {"target": dict(target)}
    for field in ("basis", "qualifications"):
        if field in member:
            result[field] = member[field]
    if kind == "evidence":
        view = graph.evidence.get(ref)
        if view is None:
            raise _ReadFailure(
                "result_inconsistent", "Prepared Evidence is missing from the Result."
            )
        result["roles"] = list(_evidence_roles(view))
        result["access_status"] = "available" if view.get("access") else "missing"
        if view.get("qualifications"):
            result["evidence_qualifications"] = view["qualifications"]
    else:
        view = graph.sources.get(ref)
        account = graph.accounts.get(ref)
        if view is None or account is None:
            raise _ReadFailure(
                "result_inconsistent", "Prepared Source Item is missing from the Result."
            )
        result["scope"] = account.get("scope")
        result["condition"] = account.get("condition")
    return result


def _covering_evidence(graph: _ResultGraph, source_ref: str) -> list[dict[str, object]]:
    result = []
    for relationship in graph.relationships:
        if relationship.get("relation") != "represents":
            continue
        member = _mapping(relationship.get("member"), "represents member")
        if member.get("target") != source_ref:
            continue
        item: dict[str, object] = {"evidence_ref": relationship["origin"]}
        for field in ("basis", "qualifications"):
            if field in member:
                item[field] = member[field]
        result.append(item)
    return result


def _resolved_member(graph: _ResultGraph, ref: str) -> dict[str, object]:
    view = graph.sources.get(ref)
    account = graph.accounts.get(ref)
    if view is None or account is None:
        raise _ReadFailure(
            "result_inconsistent", "Resolved Source Item is missing from Result accounting."
        )
    result: dict[str, object] = {
        "source_item_ref": ref,
        "locator": view.get("locator"),
        "scope": account.get("scope"),
        "condition": account.get("condition"),
        "source_content_verification": _source_verification(view),
    }
    qualifications = [
        *list(_qualifications(account)),
        *list(_qualifications(view)),
    ]
    if qualifications:
        result["qualifications"] = qualifications
    return result


def _source_verification(view: Mapping[str, object]) -> dict[str, object]:
    observation = _one_observation(view, "source_content_verification")
    if observation is None:
        return {"status": "not_checked"}
    result: dict[str, object] = {"status": observation.get("status")}
    if isinstance(observation.get("value"), Mapping):
        result.update(dict(cast(Mapping[str, object], observation["value"])))
    for field in ("basis", "qualifications"):
        if field in observation:
            result[field] = observation[field]
    return result


def _resolve_source_set(
    graph: _ResultGraph,
    source_set: Mapping[str, object],
    *,
    depth: int = 0,
) -> frozenset[str]:
    if depth > 64:
        raise _ReadFailure("invalid_source_set", "source_set nesting is too deep.")
    kind = source_set.get("kind")
    if kind == "explicit":
        _require_exact_keys(source_set, {"kind", "source_item_refs"}, "source_set")
        refs = _ref_list(
            source_set.get("source_item_refs"),
            "source_item_refs",
            100000,
            error_code="invalid_source_set",
        )
        invalid = [ref for ref in refs if ref not in graph.sources]
        if invalid:
            raise _ReadFailure(
                "reference_not_in_result",
                "Every explicit Source Item must resolve inside the exact bound Result.",
                details={"invalid_inputs": invalid},
            )
        return frozenset(refs)
    if kind == "precheck_relation":
        _require_exact_keys(
            source_set, {"kind", "origin", "relation", "direction"}, "source_set"
        )
        if source_set.get("direction") != "outbound":
            raise _ReadFailure(
                "invalid_source_set", "PreCheck source-set relations must be outbound."
            )
        relation = source_set.get("relation")
        origin = source_set.get("origin")
        if relation == "accounts_for":
            if origin != graph.result_ref:
                raise _ReadFailure(
                    "reference_not_in_result",
                    "accounts_for must originate from the exact bound Result.",
                    details={"invalid_inputs": [origin]},
                )
            return frozenset(graph.accounts)
        if relation == "represents":
            if not isinstance(origin, str) or origin not in graph.evidence:
                raise _ReadFailure(
                    "reference_not_in_result",
                    "represents must originate from Evidence in the exact bound Result.",
                    details={"invalid_inputs": [origin]},
                )
            return frozenset(_represented_refs(graph, origin))
        raise _ReadFailure(
            "invalid_source_set", "Only accounts_for and represents are resolvable."
        )
    if kind == "union":
        _require_exact_keys(source_set, {"kind", "sets"}, "source_set")
        children = source_set.get("sets")
        if not isinstance(children, list) or len(children) < 2:
            raise _ReadFailure(
                "invalid_source_set", "union requires at least two source sets."
            )
        result: set[str] = set()
        for child in children:
            if not isinstance(child, Mapping):
                raise _ReadFailure(
                    "invalid_source_set", "union children must be source sets."
                )
            result.update(_resolve_source_set(graph, child, depth=depth + 1))
        return frozenset(result)
    if kind == "difference":
        _require_exact_keys(source_set, {"kind", "base", "subtract"}, "source_set")
        base = source_set.get("base")
        subtract = source_set.get("subtract")
        if not isinstance(base, Mapping) or not isinstance(subtract, Mapping):
            raise _ReadFailure(
                "invalid_source_set", "difference operands must be source sets."
            )
        return _resolve_source_set(
            graph, base, depth=depth + 1
        ) - _resolve_source_set(graph, subtract, depth=depth + 1)
    raise _ReadFailure("invalid_source_set", "source_set has an unsupported kind.")


def _observations(value: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    raw = value.get("observations", [])
    if not isinstance(raw, list):
        raise _ReadFailure("result_inconsistent", "observations must be an array.")
    return tuple(_mapping(item, "observation") for item in raw)


def _one_observation(
    value: Mapping[str, object], name: str
) -> Mapping[str, object] | None:
    matches = [item for item in _observations(value) if item.get("name") == name]
    if len(matches) > 1:
        raise _ReadFailure(
            "result_inconsistent", f"{name} occurs more than once on one object."
        )
    return matches[0] if matches else None


def _evidence_roles(value: Mapping[str, object]) -> tuple[str, ...]:
    roles: list[str] = []
    for observation in _observations(value):
        if observation.get("name") != "evidence_role":
            continue
        if observation.get("status") != "available":
            raise _ReadFailure(
                "result_inconsistent", "evidence_role must be available when present."
            )
        raw = observation.get("value")
        role = raw.get("role") if isinstance(raw, Mapping) else None
        if role not in _EVIDENCE_ROLES:
            raise _ReadFailure(
                "result_inconsistent", "Evidence has an unsupported public role."
            )
        if role not in roles:
            roles.append(str(role))
    return tuple(roles)


def _prepared_evidence_refs(
    members: Sequence[Mapping[str, object]],
) -> Iterator[str]:
    for member in members:
        target = member.get("target")
        if isinstance(target, Mapping) and target.get("kind") == "evidence":
            ref = target.get("ref")
            if isinstance(ref, str):
                yield ref


def _qualifications(
    value: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    raw = value.get("qualifications", [])
    if not isinstance(raw, list):
        raise _ReadFailure("result_inconsistent", "qualifications must be an array.")
    return tuple(_mapping(item, "qualification") for item in raw)


def _page_request(
    value: object,
    *,
    default: int,
    maximum: int,
    result_ref: str,
    result_digest: str,
    operation: str,
    query_key: str,
) -> tuple[int, int]:
    page = {} if value is None else value
    if not isinstance(page, Mapping) or set(page) - {"limit", "cursor"}:
        raise _ReadFailure(
            "invalid_request", "page may contain only limit and cursor."
        )
    limit = page.get("limit", default)
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= maximum
    ):
        raise _ReadFailure(
            "invalid_request", f"page.limit must be an integer from 1 through {maximum}."
        )
    cursor = page.get("cursor")
    if cursor is None:
        return limit, 0
    if not isinstance(cursor, str):
        raise _ReadFailure("invalid_cursor", "cursor must be a string.")
    offset = _decode_cursor(
        cursor,
        result_digest,
        result_ref=result_ref,
        operation=operation,
        query_key=query_key,
        limit=limit,
    )
    if offset is None:
        raise _ReadFailure(
            "invalid_cursor", "Cursor is invalid or belongs to another query."
        )
    return limit, offset


def _paged_response(
    base: Mapping[str, object],
    *,
    collection: str,
    values: Sequence[object],
    offset: int,
    limit: int,
    result_ref: str,
    result_digest: str,
    operation: str,
    query_key: str,
    page_extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    if offset > len(values):
        raise _ReadFailure("invalid_cursor", "Cursor position is outside the result.")
    selected: list[object] = []
    byte_limited = False
    for value in values[offset : offset + limit]:
        candidate = [*selected, value]
        candidate_next_offset = offset + len(candidate)
        candidate_complete = candidate_next_offset >= len(values)
        candidate_page: dict[str, object] = {
            **dict(page_extra or {}),
            "returned": len(candidate),
            "total": len(values),
            "complete": candidate_complete,
            "stop_reason": "complete" if candidate_complete else "byte_limit",
        }
        if not candidate_complete:
            candidate_page["next_cursor"] = _encode_cursor(
                result_digest,
                result_ref=result_ref,
                operation=operation,
                query_key=query_key,
                limit=limit,
                offset=candidate_next_offset,
            )
        provisional = {
            **base,
            collection: candidate,
            "page": candidate_page,
        }
        if _encoded_size(provisional) > _MAX_RESPONSE_BYTES:
            byte_limited = True
            break
        selected = candidate
    if offset < len(values) and not selected:
        raise _ReadFailure(
            "response_item_too_large",
            "One response item exceeds the Tool response byte limit.",
        )
    next_offset = offset + len(selected)
    complete = next_offset >= len(values)
    page: dict[str, object] = {
        **dict(page_extra or {}),
        "returned": len(selected),
        "total": len(values),
        "complete": complete,
        "stop_reason": (
            "complete" if complete else "byte_limit" if byte_limited else "limit"
        ),
    }
    if not complete:
        page["next_cursor"] = _encode_cursor(
            result_digest,
            result_ref=result_ref,
            operation=operation,
            query_key=query_key,
            limit=limit,
            offset=next_offset,
        )
    response = {**base, collection: selected, "page": page}
    _ensure_response_size(response)
    return response


def _encode_cursor(
    result_digest: str,
    *,
    result_ref: str,
    operation: str,
    query_key: str,
    limit: int,
    offset: int,
) -> str:
    payload = _canonical_json(
        {
            "limit": limit,
            "offset": offset,
            "operation": operation,
            "query": query_key,
            "result_ref": result_ref,
        }
    ).encode("utf-8")
    signature = hmac.new(
        result_digest.encode("ascii"), payload, hashlib.sha256
    ).digest()
    token = base64.urlsafe_b64encode(payload + signature).rstrip(b"=").decode("ascii")
    return f"precheck-cursor:{token}"


def _decode_cursor(
    cursor: str,
    result_digest: str,
    *,
    result_ref: str,
    operation: str,
    query_key: str,
    limit: int,
) -> int | None:
    if not cursor.startswith("precheck-cursor:"):
        return None
    token = cursor.removeprefix("precheck-cursor:")
    try:
        decoded = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        payload, signature = decoded[:-32], decoded[-32:]
        expected = hmac.new(
            result_digest.encode("ascii"), payload, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected):
            return None
        value = json.loads(payload)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value != {
        "limit": limit,
        "offset": value.get("offset"),
        "operation": operation,
        "query": query_key,
        "result_ref": result_ref,
    }:
        return None
    offset = value.get("offset")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return None
    return offset


def _require_keys(value: Mapping[str, object], allowed: set[str]) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise _ReadFailure(
            "invalid_request", f"Request contains unsupported fields: {sorted(unknown)}."
        )


def _require_exact_keys(
    value: Mapping[str, object], expected: set[str], label: str
) -> None:
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing or unknown:
        raise _ReadFailure(
            "invalid_source_set",
            f"{label} has missing or unsupported fields.",
            details={"missing": sorted(missing), "unsupported": sorted(unknown)},
        )


def _ref_list(
    value: object,
    label: str,
    maximum: int,
    *,
    error_code: str = "invalid_request",
) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > maximum:
        raise _ReadFailure(
            error_code, f"{label} must contain 1 through {maximum} references."
        )
    if not all(isinstance(item, str) and item for item in value):
        raise _ReadFailure(error_code, f"{label} must contain strings.")
    refs = tuple(cast(list[str], value))
    if len(set(refs)) != len(refs):
        raise _ReadFailure(error_code, f"{label} must not repeat references.")
    return refs


def _include_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise _ReadFailure("invalid_request", "include must be a non-empty array.")
    if not all(isinstance(item, str) and item for item in value):
        raise _ReadFailure("invalid_request", "include must contain strings.")
    items = tuple(sorted(cast(list[str], value)))
    if len(set(items)) != len(items):
        raise _ReadFailure("invalid_request", "include must not repeat values.")
    return items


def _unique_views(
    records: Sequence[object], kind: str
) -> dict[str, Mapping[str, object]]:
    views: dict[str, Mapping[str, object]] = {}
    for record in records:
        envelope = _mapping(record, f"{kind} record")
        view = _mapping(envelope.get("view"), f"{kind} view")
        ref = view.get("ref")
        if not isinstance(ref, str) or not ref or ref in views:
            raise _ReadFailure(
                "result_inconsistent",
                f"{kind} records must have unique non-empty refs.",
            )
        views[ref] = view
    return views


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _ReadFailure("result_inconsistent", f"{label} must be an object.")
    return cast(Mapping[str, Any], value)


def _sequence(value: object, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise _ReadFailure("result_inconsistent", f"{label} must be an array.")
    return value


def _canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError) as error:
        raise _ReadFailure(
            "invalid_source_set", "Value is not JSON-compatible."
        ) from error


def _query_key(label: str, value: object) -> str:
    return label + ":" + hashlib.sha256(_canonical_json(value).encode()).hexdigest()


def _sha256_identity(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _encoded_size(value: object) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _ensure_response_size(value: object) -> None:
    if _encoded_size(value) > _MAX_RESPONSE_BYTES:
        raise _ReadFailure(
            "response_item_too_large",
            "The requested expansion exceeds the Tool response byte limit.",
        )


def _error(
    result_ref: str | None,
    operation: str | None,
    failure: _ReadFailure,
) -> dict[str, object]:
    error: dict[str, object] = {
        "code": failure.code,
        "message": str(failure),
        "retryable": failure.retryable,
    }
    if failure.details:
        error["details"] = failure.details
    response: dict[str, object] = {
        "outcome": "error",
        "operation": operation if operation in {"review", "expand", "resolve"} else "unknown",
        "error": error,
    }
    if result_ref:
        response["result_ref"] = result_ref
    return response


__all__ = ["PrecheckReadTool"]
