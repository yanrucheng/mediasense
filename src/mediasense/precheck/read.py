"""Consumer-oriented reads over one exact immutable PreCheck Result."""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from copy import copy, deepcopy
from datetime import datetime
import hashlib
import hmac
import json
import errno
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Protocol, cast
from types import SimpleNamespace
from threading import Lock
from urllib.parse import quote

from ._working_schema import SCHEMA_VERSION


_MAX_RESPONSE_BYTES = 512 * 1024
_READ_PROJECTION_REVISION = 1
_MAX_CACHED_RESULT_BYTES = 128 * 1024 * 1024
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


def bind_precheck_read(
    reader: PrecheckReadBoundary, dataset_ref: str
) -> PrecheckReadBoundary:
    """Inject an explicitly opened Dataset at the in-process stage adapter."""

    def read(request: dict[str, object]) -> dict[str, object]:
        if request.get("dataset_ref", dataset_ref) != dataset_ref:
            return {
                "error": {
                    "code": "reference_not_in_dataset",
                    "message": "Conflicting Dataset references.",
                }
            }
        return reader.read({**request, "dataset_ref": dataset_ref})

    return cast(PrecheckReadBoundary, SimpleNamespace(name=reader.name, read=read))


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
                "result_inconsistent",
                "The sealed Result graph is structurally invalid.",
            ) from error

        self.reconciliation = None
        self.source_lineages = {}
        self.artifact_proofs = package.get("_artifact_proofs", {})
        self.workspace = package.get("_workspace")
        self.evidence_records = {
            str(record["view"]["ref"]): record for record in evidence_records
        }
        self.result_ref = str(self.result.get("ref", ""))
        self.by_origin_relation: dict[tuple[str, str], list[Mapping[str, object]]] = (
            defaultdict(list)
        )
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
                "result_inconsistent",
                "The entry Evidence frontier contains duplicates.",
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
    """Implement deterministic reads over one immutable Result."""

    name = "mediasense.precheck.read"

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.workspace = self.database_path.parent.absolute()
        self._verify_schema()
        self._cache_lock = Lock()
        self._cached_result = None

    def read(self, request: dict[str, object]) -> dict[str, object]:
        result_ref = request.get("result_ref")
        operation = request.get("action")
        try:
            from mediasense.runtime.resources import contract_validator

            if operation == "expand" and isinstance(request.get("include"), list):
                allowed = (
                    _SOURCE_INCLUDES
                    if "source_item_refs" in request
                    else _EVIDENCE_INCLUDES
                )
                if any(item not in allowed for item in request["include"]):
                    raise _ReadFailure(
                        "unsupported_include",
                        "The selector does not support a requested include.",
                    )
            if not contract_validator(self.name).is_valid(request):
                if operation == "resolve" and "source_set" in request:
                    schema = contract_validator(self.name).schema
                    selection_validator = contract_validator(self.name).evolve(
                        schema={"$defs": schema["$defs"], "$ref": "#/$defs/source_set"}
                    )
                    if not selection_validator.is_valid(request["source_set"]):
                        raise _ReadFailure(
                            "invalid_source_set", "Invalid Source Set expression."
                        )
                raise _ReadFailure(
                    "invalid_request", "Invalid flat PreCheck Read request."
                )
            if not isinstance(result_ref, str) or not result_ref:
                raise _ReadFailure(
                    "invalid_request", "result_ref must be a non-empty string."
                )
            if operation not in {"review", "expand", "resolve", "geo_summary"}:
                raise _ReadFailure(
                    "invalid_request",
                    "operation must be review, expand, resolve, or geo_summary.",
                )
            graph, result_digest = self._load(result_ref)
            if graph.result.get("dataset_ref") != request["dataset_ref"]:
                raise _ReadFailure(
                    "result_not_found", "Result does not exist in this Dataset."
                )
            if graph.result_ref != result_ref:
                raise _ReadFailure(
                    "result_untrusted",
                    "The sealed Result identity does not match its reference.",
                )
            if operation == "review":
                response = self._review(graph, result_digest, request)
            elif operation == "expand":
                response = self._expand(graph, result_digest, request)
            elif operation == "geo_summary":
                response = self._geo_summary(graph, result_digest, request)
            else:
                response = self._resolve(graph, result_digest, request)
            contract_validator(self.name, operation).validate(response)
            return deepcopy(response)
        except _ReadFailure as failure:
            return _error(
                result_ref if isinstance(result_ref, str) else None,
                operation if isinstance(operation, str) else None,
                failure,
            )

    def _result_snapshot(self, result_ref):
        with self._connect() as connection:
            connection.execute("BEGIN")
            row = connection.execute(
                "SELECT * FROM sealed_results WHERE result_ref = ?", (result_ref,)
            ).fetchone()
            if row is None:
                raise _ReadFailure("result_not_found", "Result does not exist.")
            artifacts = tuple(
                connection.execute(
                    """SELECT artifact_id, digest_algorithm, digest, size_bytes, relative_path FROM result_artifacts
                JOIN artifacts USING (artifact_id)
                WHERE result_ref = ? ORDER BY artifact_id""",
                    (result_ref,),
                )
            )
        return dict(row), tuple(dict(item) for item in artifacts)

    def _storage_binding(self):
        database = self.database_path.stat()
        root = self.workspace.resolve(strict=True)
        root_stat = root.stat()
        return (
            str(root),
            root_stat.st_dev,
            root_stat.st_ino,
            database.st_dev,
            database.st_ino,
        )

    def _load(self, result_ref: str) -> tuple[_ResultGraph, str]:
        from mediasense.runtime.resources import contract_validator
        from ._read_file import read_sealed_bytes

        # One bounded entry per Reader. The same Reader is shared by Read and Run.
        # The lock also prevents concurrent cold calls from validating the same
        # Result repeatedly. No failure is retained as a successful cache entry.
        with self._cache_lock:
            try:
                row, artifact_rows = self._result_snapshot(result_ref)
                if row["digest_algorithm"] != "sha256":
                    raise _ReadFailure(
                        "result_untrusted",
                        "Unsupported sealed Result digest algorithm.",
                    )
                binding = self._storage_binding()
                schema = contract_validator(self.name, "review").schema
                key = (
                    binding,
                    _canonical_json([row, artifact_rows]),
                    _READ_PROJECTION_REVISION,
                    _sha256_identity(_canonical_json(schema).encode()),
                )
                cached = self._cached_result
                candidate = cached is not None and cached[0] == key
                encoded, identity = read_sealed_bytes(
                    self.workspace,
                    row["relative_path"],
                    row["size_bytes"],
                    row["digest"],
                    cached[1] if candidate else None,
                )
                if encoded is None:
                    graph = cached[2]
                else:
                    self._cached_result = None
                    cached = None
                    graph = self._validate_package(encoded, result_ref, artifact_rows)
                # Do not publish a verification for a registration/proof snapshot
                # that changed while its bytes or semantics were being checked.
                current_row, current_artifacts = self._result_snapshot(result_ref)
                if current_row != row or self._storage_binding() != binding:
                    raise _ReadFailure(
                        "result_untrusted", "Result registration changed while reading."
                    )
                if current_artifacts != artifact_rows:
                    # Access proofs have their own current availability boundary.
                    # Never turn a changed image proof into a whole-Result error,
                    # or mutate the graph another reader may already be using.
                    graph = copy(graph)
                    graph.artifact_proofs = {
                        a["artifact_id"]: a for a in current_artifacts
                    }
                    self._cached_result = None
                    return graph, str(row["digest"])
                if row["size_bytes"] <= _MAX_CACHED_RESULT_BYTES:
                    self._cached_result = (key, identity, graph)
                else:
                    self._cached_result = None
                return graph, str(row["digest"])
            except OSError as error:
                self._cached_result = None
                if error.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise _ReadFailure(
                        "result_untrusted",
                        "Sealed Result path is not confined to regular directories.",
                    ) from error
                raise _ReadFailure(
                    "result_unavailable",
                    "Sealed Result bytes are unavailable.",
                    retryable=True,
                ) from error
            except ValueError as error:
                self._cached_result = None
                raise _ReadFailure("result_untrusted", str(error)) from error
            except BaseException:
                self._cached_result = None
                raise

    def _validate_package(self, encoded, result_ref, artifact_rows) -> _ResultGraph:
        try:
            package = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _ReadFailure(
                "result_untrusted", "Sealed Result cannot be decoded."
            ) from error
        if not isinstance(package, dict) or package.get("schema_version") not in {1, 2}:
            raise _ReadFailure(
                "result_untrusted", "Sealed Result has an unsupported shape."
            )
        # Artifact availability is checked at the selected Evidence boundary.
        # A missing rendition must not invalidate the immutable Result graph.
        package["_artifact_proofs"] = {
            str(a["artifact_id"]): dict(a) for a in artifact_rows
        }
        package["_workspace"] = self.workspace
        from ._result_sqlite import _validate_observations, _validate_execution_boundary
        from ._result_types import ResultSealError

        try:
            graph = _ResultGraph(package)
            if graph.result.get("integrity") != "valid":
                raise ValueError("Result was not validly sealed")
            if graph.result_ref != result_ref or graph.result.get(
                "dataset_ref"
            ) != graph.dataset.get("ref"):
                raise ValueError("Result identity mismatch")
            if set(graph.sources) != set(graph.accounts):
                raise ValueError("Result source accounting is incomplete")
            from ._read_projection import project_retained_observations

            project_retained_observations(
                graph, historical=package.get("schema_version", 1) == 1
            )
            for view in (*graph.sources.values(), *graph.evidence.values()):
                _validate_observations(tuple(view.get("observations", ())))
            _validate_execution_boundary(package["execution_boundary"])
            _reconciliation(graph)
            seen_relations = set()
            known_refs = {
                graph.result_ref,
                str(graph.dataset["ref"]),
                *graph.sources,
                *graph.evidence,
            }
            for relationship in graph.relationships:
                origin, relation, member = (
                    relationship["origin"],
                    relationship["relation"],
                    relationship["member"],
                )
                target = member.get("target")
                if relation not in {
                    "accounts_for",
                    "entry_evidence",
                    "represents",
                    "derived_from",
                    "expands_to",
                }:
                    raise ValueError("Unknown Result relationship")
                if origin not in known_refs:
                    raise ValueError("Relationship has an unknown origin")
                if (
                    relation in {"accounts_for", "entry_evidence"}
                    and origin != graph.result_ref
                ):
                    raise ValueError(
                        "Only the Result owns accounting and entry relationships"
                    )
                if (
                    relation in {"represents", "derived_from", "expands_to"}
                    and origin not in graph.evidence
                ):
                    raise ValueError("Only Evidence owns evidence relationships")
                target_ref = (
                    target.get("ref") if isinstance(target, Mapping) else target
                )
                if target_ref not in known_refs:
                    raise ValueError("Relationship target is missing")
                identity = (origin, relation, str(target_ref))
                if identity in seen_relations:
                    raise ValueError("Duplicate relationship membership")
                seen_relations.add(identity)
                if (
                    relation in {"accounts_for", "represents"}
                    and target_ref not in graph.sources
                ):
                    raise ValueError("Source relationship targets another kind")
                if relation == "entry_evidence" and target_ref not in graph.evidence:
                    raise ValueError("Entry relationship targets another kind")
            from ._read_projection import source_lineage

            for ref in graph.evidence:
                source_lineage(graph, ref)
                _represented_refs(graph, ref)
                for relation in ("derived_from", "expands_to"):
                    for member in graph.members(ref, relation):
                        _prepared_target(graph, member)
            from .geocode import normalize_geo_observations

            for view in graph.evidence.values():
                observations = list(view.get("observations", ()))
                if any(
                    item.get("name") == "reverse_geocode_candidate"
                    for item in observations
                ):
                    view["observations"] = [
                        item
                        for item in observations
                        if item.get("name")
                        not in {"reverse_geocode_candidate", "reverse_geocode_attempt"}
                    ] + list(normalize_geo_observations({"observations": observations}))
            for ref, view in graph.sources.items():
                if graph.accounts[ref]["scope"] != "source_media":
                    continue
                observations = list(view.get("observations", ()))
                available = any(
                    item.get("name") in {"gps_coordinates", "gpx_coordinates"}
                    and item.get("status") == "available"
                    for item in observations
                )
                normalized = normalize_geo_observations(
                    {"observations": observations}, coordinate_available=available
                )
                view["observations"] = [
                    item
                    for item in observations
                    if item.get("name")
                    not in {
                        "reverse_geocode_candidate",
                        "reverse_geocode_attempt",
                        "address_candidate",
                        "nearby_place_candidates",
                    }
                ] + list(normalized)
        except (ValueError, KeyError, TypeError, ResultSealError) as error:
            raise _ReadFailure(
                "result_untrusted", "Sealed Result has invalid evidence or references."
            ) from error
        return graph

    def _review(
        self,
        graph: _ResultGraph,
        result_digest: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        _require_keys(
            request,
            {
                "dataset_ref",
                "result_ref",
                "action",
                "page",
                "include",
                "execution_page",
                "evidence_refs",
            },
        )
        refs = (
            tuple(sorted(request["evidence_refs"]))
            if "evidence_refs" in request
            else graph.entry_evidence_refs
        )
        if any(ref not in graph.evidence for ref in refs):
            raise _ReadFailure(
                "reference_not_in_result", "Selected Evidence is not in this Result."
            )
        query_key = _query_key(
            "review:selection_order",
            {
                "include": sorted(request.get("include", [])),
                "evidence_refs": refs if "evidence_refs" in request else None,
            },
        )
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
        from ._read_projection import ReviewItems

        items = ReviewItems(graph, refs)
        base: dict[str, object] = {
            "result": _effective_result_view(graph),
            "accounting": reconciliation,
        }
        if "execution_boundary" in request.get("include", ()):
            boundary = graph.result.get("execution_boundary", {})
            audit = boundary.get("audit", {})
            local = boundary.get("network_access") is False
            execution = {
                "source_read_only": True,
                "remote_models": boundary.get("remote_models", False),
                "logical_external_queries": boundary.get(
                    "logical_external_queries", 0 if local else None
                ),
                "historical_provider_requests": audit.get(
                    "historical_provider_requests", 0 if local else None
                ),
                "current_provider_requests": audit.get(
                    "current_provider_requests", 0 if local else None
                ),
                "billable_calls": audit.get("billable_calls", 0 if local else None),
                "transmitted_data_classes": ["coordinate", "datum", "locale"]
                if boundary.get("network_access") is True
                and boundary.get("provider_requests") != 0
                else [],
                "providers_attempted": list(boundary.get("providers", ())),
            }
            execution_limit, execution_offset = _page_request(
                request.get("execution_page"),
                default=50,
                maximum=200,
                result_ref=graph.result_ref,
                result_digest=result_digest,
                operation="review",
                query_key="execution_boundary:durable_attempt_order",
            )
            minimum_page = _paged_response(
                base,
                collection="items",
                values=items,
                offset=offset,
                limit=limit,
                result_ref=graph.result_ref,
                result_digest=result_digest,
                operation="review",
                query_key=query_key,
                max_items=1,
                review_faults=True,
            )
            audit_budget = (
                _MAX_RESPONSE_BYTES
                - _encoded_size(minimum_page)
                - len('"execution_boundary":,')
            )
            base["execution_boundary"] = _paged_response(
                execution,
                collection="attempts",
                values=audit.get("attempts", []),
                offset=execution_offset,
                limit=execution_limit,
                byte_budget=audit_budget,
                result_ref=graph.result_ref,
                result_digest=result_digest,
                operation="review",
                query_key="execution_boundary:durable_attempt_order",
            )
        return _paged_response(
            base,
            collection="items",
            values=items,
            review_faults=True,
            offset=offset,
            limit=limit,
            result_ref=graph.result_ref,
            result_digest=result_digest,
            operation="review",
            query_key=query_key,
        )

    def _geo_summary(
        self,
        graph: _ResultGraph,
        result_digest: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        _require_keys(request, {"dataset_ref", "result_ref", "action", "page"})
        projection = _geo_projection(graph)
        groups = cast(list[dict[str, object]], projection.pop("coordinate_groups"))
        query_key = "geo_summary:exact_coordinate_order"
        limit, offset = _page_request(
            request.get("page"),
            default=50,
            maximum=200,
            result_ref=graph.result_ref,
            result_digest=result_digest,
            operation="geo_summary",
            query_key=query_key,
        )
        base: dict[str, object] = {
            **projection,
        }
        return _paged_response(
            base,
            collection="coordinate_groups",
            values=groups,
            offset=offset,
            limit=limit,
            result_ref=graph.result_ref,
            result_digest=result_digest,
            operation="geo_summary",
            query_key=query_key,
        )

    def _expand(
        self,
        graph: _ResultGraph,
        result_digest: str,
        request: Mapping[str, object],
    ) -> dict[str, object]:
        _require_keys(
            request,
            {
                "dataset_ref",
                "result_ref",
                "action",
                "evidence_refs",
                "source_item_refs",
                "include",
                "page",
            },
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
            member_refs = tuple(sorted(_represented_refs(graph, ref)))
            query_key = _query_key(
                "expand-member-observations",
                {"evidence_refs": refs, "include": include},
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
                    "source_item_ref": source_ref,
                    "observations": list(_observations(graph.sources[source_ref])),
                    **(
                        {"qualifications": graph.sources[source_ref]["qualifications"]}
                        if graph.sources[source_ref].get("qualifications")
                        else {}
                    ),
                }
                for source_ref in member_refs
            ]
            base = {}
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
            items.append({"evidence_ref": ref, "included": included})
        response: dict[str, object] = {
            "items": items,
            "page": {
                "total": len(items),
                "next_cursor": None,
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
                    if key not in {"observations", "kind", "ref"}
                }
            if "observations" in include:
                included["observations"] = list(view.get("observations", ()))
            if "covering_evidence" in include:
                included["covering_evidence"] = _covering_evidence(graph, ref)
            items.append({"source_item_ref": ref, "included": included})
        response: dict[str, object] = {
            "items": items,
            "page": {
                "total": len(items),
                "next_cursor": None,
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
        _require_keys(
            request, {"dataset_ref", "result_ref", "action", "source_set", "page"}
        )
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
            "resolution": {
                "source_set_identity": source_set_identity,
                "membership_identity": membership_identity,
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


def _effective_result_view(graph: _ResultGraph) -> dict[str, object]:
    """Apply current handoff invariants without rewriting immutable Result bytes."""

    view = {key: graph.result[key] for key in ("ref", "coverage", "readiness")}
    qualifications = [
        item
        for item in graph.result.get("qualifications", ())
        if item.get("code") != "reverse_geocode_incomplete"
    ]
    if (
        view["readiness"] == "blocked"
        and graph.result.get("qualifications")
        and not any(item.get("effect") == "blocks_use" for item in qualifications)
    ):
        if graph.entry_evidence_refs and all(
            item.get("condition") != "unresolved"
            for item in graph.accounts.values()
            if item.get("scope") == "source_media"
        ):
            view["readiness"] = "plan_ready"
    if qualifications:
        view["qualifications"] = qualifications
    return deepcopy(view)


def _reconciliation(graph: _ResultGraph) -> dict[str, object]:
    if graph.reconciliation is not None:
        return graph.reconciliation
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
    counts = Counter(
        (str(member.get("scope")), str(member.get("condition")))
        for member in graph.accounts.values()
    )
    graph.reconciliation = {
        "total": len(accounted),
        "scope_condition": [
            {"scope": scope, "condition": condition, "count": count}
            for (scope, condition), count in sorted(counts.items())
        ],
        "routes": {
            "frontier_only": len(frontier_only),
            "exception_only": len(exception_only),
            "frontier_and_exception": len(both),
            "residual": len(residual),
        },
        "frontier": {
            "entry_evidence_count": len(graph.entry_evidence_refs),
            "coverage_memberships": membership_count,
            "represented_unique_source_items": len(frontier),
        },
    }
    return graph.reconciliation


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
    result: dict[str, object] = {
        "status_counts": {state: count for state, count in states.items() if count}
    }
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
        "status_counts": {state: count for state, count in states.items() if count},
        "values": [
            {"value": value, "count": count} for value, count in sorted(values.items())
        ],
    }


def _coverage_basis(graph: _ResultGraph, ref: str) -> dict[str, object]:
    members = graph.members(ref, "represents")
    qualified = sum(bool(member.get("qualifications")) for member in members)
    return {
        "member_count": len(members),
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
    from ._read_projection import require_evidence_access

    require_evidence_access(graph, ref)
    view = graph.evidence[ref]
    return {
        "observations": list(view.get("observations", ())),
        **{key: value for key, value in view.items() if key not in {"kind", "ref"}},
        "roles": list(_evidence_roles(view)),
    }


def _prepared_target(
    graph: _ResultGraph, member: Mapping[str, object]
) -> dict[str, object]:
    target = member.get("target")
    if not isinstance(target, Mapping):
        raise _ReadFailure("result_inconsistent", "An expands_to target is not typed.")
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
                "result_inconsistent",
                "Prepared Source Item is missing from the Result.",
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
            "result_inconsistent",
            "Resolved Source Item is missing from Result accounting.",
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


def _geo_projection(graph: _ResultGraph) -> dict[str, object]:
    state_names = (*_OBSERVATION_STATES, "unreported")
    gps_counts = Counter({state: 0 for state in state_names})
    gpx_counts = Counter({state: 0 for state in state_names})
    combined = Counter(
        {state: 0 for state in ("available", "missing", "failed", "conflict")}
    )
    groups: dict[str, dict[str, object]] = {}

    for source_ref in sorted(graph.sources):
        account = graph.accounts.get(source_ref)
        if not isinstance(account, Mapping) or account.get("scope") != "source_media":
            continue
        source = graph.sources[source_ref]
        gps = _one_observation(source, "gps_coordinates")
        gpx = _one_observation(source, "gpx_coordinates")
        gps_counts[_geo_observation_state(gps)] += 1
        gpx_counts[_geo_observation_state(gpx)] += 1
        gps_coordinate = _geo_coordinate_value(gps)
        gpx_coordinate = _geo_coordinate_value(gpx)
        conflict = (
            gps_coordinate is not None
            and gpx_coordinate is not None
            and gps_coordinate != gpx_coordinate
        )
        selected = gpx_coordinate or gps_coordinate
        if conflict:
            combined["conflict"] += 1
        if selected is not None:
            combined["available"] += 1
            key = _canonical_json(selected)
            group = groups.setdefault(
                key,
                {
                    "coordinate": selected,
                    "source_item_refs": [],
                    "candidate_evidence_refs": set(),
                },
            )
            cast(list[str], group["source_item_refs"]).append(source_ref)
        elif (
            _geo_observation_state(gps) == "failed"
            or _geo_observation_state(gpx) == "failed"
        ):
            combined["failed"] += 1
        else:
            combined["missing"] += 1

    coordinate_groups = []
    incomplete = False
    for group in sorted(
        groups.values(),
        key=lambda item: (
            item["coordinate"]["latitude"],
            item["coordinate"]["longitude"],
            item["coordinate"]["datum"],
        ),
    ):
        members = tuple(sorted(group["source_item_refs"]))
        components = {}
        for name, component in (
            ("address_candidate", "address"),
            ("nearby_place_candidates", "nearby_places"),
        ):
            counts = Counter()
            for ref in members:
                observation = _one_observation(graph.sources[ref], name)
                outcome = {
                    "available": "success",
                    "missing": "no_result",
                    "failed": "failed",
                    "not_checked": "not_requested",
                    "not_applicable": "not_applicable",
                }.get(
                    observation.get("status") if observation else None, "not_requested"
                )
                if observation and any(
                    q.get("code") == "geo_effect_indeterminate"
                    for q in observation.get("qualifications", ())
                ):
                    outcome = "indeterminate"
                counts[outcome] += 1
                if outcome in {"not_requested", "indeterminate"}:
                    incomplete = True
            components[component] = dict(counts)
        evidence_refs = sorted(
            {
                str(relation["origin"])
                for relation in graph.relationships
                if relation.get("relation") == "represents"
                and relation["member"].get("target") in members
                and any(
                    item.get("name")
                    in {
                        "address_candidate",
                        "nearby_place_candidates",
                        "reverse_geocode_candidate",
                    }
                    and item.get("status") == "available"
                    for item in _observations(
                        graph.evidence.get(relation["origin"], {})
                    )
                )
            }
        )
        coordinate_groups.append(
            {
                "coordinate": group["coordinate"],
                "member_count": len(members),
                "source_set": {
                    "kind": "geo_coordinate",
                    "coordinate": group["coordinate"],
                    "selection_rule": "gpx_over_gps_exact_normalized_v1",
                },
                "components": components,
                "candidate_evidence_refs": evidence_refs,
            }
        )
    return {
        "acquisition_status": "not_applicable"
        if not coordinate_groups
        else "incomplete"
        if incomplete
        else "complete",
        "coordinate_evidence": {
            "gps": {key: count for key, count in gps_counts.items() if count},
            "gpx": {key: count for key, count in gpx_counts.items() if count},
            "combined": {key: count for key, count in combined.items() if count},
        },
        "coordinate_groups": coordinate_groups,
    }


def _geo_observation_state(observation: Mapping[str, object] | None) -> str:
    if observation is None:
        return "unreported"
    status = observation.get("status")
    if status not in _OBSERVATION_STATES:
        raise _ReadFailure(
            "result_inconsistent", "Geo observation has an unsupported status."
        )
    return str(status)


def _geo_coordinate_value(
    observation: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if observation is None or observation.get("status") != "available":
        return None
    value = observation.get("value")
    if not isinstance(value, Mapping):
        raise _ReadFailure(
            "result_inconsistent", "Available Geo observation has no coordinate."
        )
    try:
        latitude = float(value["latitude"])
        longitude = float(value["longitude"])
        datum = str(value["datum"])
    except (KeyError, TypeError, ValueError) as error:
        raise _ReadFailure(
            "result_inconsistent", "Available Geo observation is invalid."
        ) from error
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or not datum:
        raise _ReadFailure(
            "result_inconsistent", "Available Geo observation is out of range."
        )
    return {"latitude": latitude, "longitude": longitude, "datum": datum}


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
    if kind == "geo_coordinate":
        _require_exact_keys(
            source_set,
            {"kind", "coordinate", "selection_rule"},
            "source_set",
        )
        if source_set.get("selection_rule") != "gpx_over_gps_exact_normalized_v1":
            raise _ReadFailure(
                "invalid_source_set",
                "Geo Source Set has an unsupported selection rule.",
            )
        coordinate = source_set.get("coordinate")
        if not isinstance(coordinate, Mapping):
            raise _ReadFailure(
                "invalid_source_set", "Geo Source Set coordinate must be an object."
            )
        target = _geo_coordinate_value({"status": "available", "value": coordinate})
        assert target is not None
        members: set[str] = set()
        for source_ref, source in graph.sources.items():
            account = graph.accounts.get(source_ref)
            if (
                not isinstance(account, Mapping)
                or account.get("scope") != "source_media"
            ):
                continue
            selected = _geo_coordinate_value(
                _one_observation(source, "gpx_coordinates")
            ) or _geo_coordinate_value(_one_observation(source, "gps_coordinates"))
            if selected == target:
                members.add(source_ref)
        return frozenset(members)
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
        return _resolve_source_set(graph, base, depth=depth + 1) - _resolve_source_set(
            graph, subtract, depth=depth + 1
        )
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
        if (
            observation.get("name") == "additional_evidence_roles"
            and observation.get("status") == "available"
        ):
            for role in observation["value"]:
                if role not in _EVIDENCE_ROLES:
                    raise _ReadFailure(
                        "result_inconsistent",
                        "Evidence has an unsupported additional role.",
                    )
                if role not in roles:
                    roles.append(role)
            continue
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
        raise _ReadFailure("invalid_request", "page may contain only limit and cursor.")
    limit = page.get("limit", default)
    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= maximum
    ):
        raise _ReadFailure(
            "invalid_request",
            f"page.limit must be an integer from 1 through {maximum}.",
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
    max_items: int | None = None,
    byte_budget: int | None = None,
    review_faults: bool = False,
) -> dict[str, object]:
    if offset > len(values):
        raise _ReadFailure("invalid_cursor", "Cursor position is outside the result.")
    effective_limit = limit if max_items is None else min(limit, max_items)
    budget = (
        _MAX_RESPONSE_BYTES
        if byte_budget is None
        else min(_MAX_RESPONSE_BYTES, byte_budget)
    )

    def response(items, next_offset, *, byte_limited=False):
        page = {"total": len(values), "next_cursor": None}
        if next_offset < len(values):
            page["next_cursor"] = _encode_cursor(
                result_digest,
                result_ref=result_ref,
                operation=operation,
                query_key=query_key,
                limit=limit,
                offset=next_offset,
            )
            if byte_limited:
                page["stop_reason"] = "byte_limit"
        return {**base, collection: items, "page": page}

    # Serialize the shared envelope once. Only the cursor/page shape changes
    # while finding a prefix; the optional audit must not be re-encoded per item.
    fixed_size = _encoded_size({**base, collection: [], "page": {}}) - 2

    def envelope_size(next_offset, *, byte_limited=False):
        page = response([], next_offset, byte_limited=byte_limited)["page"]
        return fixed_size + _encoded_size(page)

    end = min(len(values), offset + effective_limit)
    full_envelope = envelope_size(end)
    if envelope_size(len(values)) > budget:
        raise _ReadFailure(
            "response_item_too_large",
            "The response envelope or execution audit exceeds the byte limit.",
        )
    if offset == end:
        return response([], end)

    fetched = {}
    for attempt in range(2):
        batch, size, best = [], 0, 0
        for index in range(offset, end):
            if index not in fetched:
                fetched[index] = values[index]
            item = fetched[index]
            batch.append(item)
            size += _encoded_size(item) + (1 if len(batch) > 1 else 0)
            next_offset = index + 1
            if next_offset == end and full_envelope + size <= budget:
                return response(batch, end)
            if envelope_size(next_offset, byte_limited=True) + size <= budget:
                best = len(batch)
            # A final page loses its cursor. Keep looking only while that smaller
            # full-page envelope could still make the requested batch fit. This
            # preserves final/count-limited boundaries without eagerly fetching
            # every position. Ordinary large records need one boundary lookahead.
            if full_envelope + size > budget:
                break
        if best:
            return response(batch[:best], offset + best, byte_limited=True)
        if not review_faults or attempt or "error" in fetched[offset]:
            break
        single = response([fetched[offset]], offset + 1, byte_limited=end > offset + 1)
        required = {
            key: value for key, value in single.items() if key != "execution_boundary"
        }
        if _encoded_size(required) <= budget:
            raise _ReadFailure(
                "response_item_too_large",
                "The execution audit leaves insufficient room for this Evidence; reduce execution_page or omit the audit.",
            )
        fetched[offset] = {
            "evidence_ref": fetched[offset]["evidence_ref"],
            "error": {
                "code": "response_item_too_large",
                "message": "This Evidence item and its required page envelope exceed the response byte limit.",
            },
        }
    raise _ReadFailure(
        "response_item_too_large",
        "The response item or required page envelope exceeds the response byte limit.",
    )


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
            "action": operation,
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
        "action": operation,
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
            "invalid_request",
            f"Request contains unsupported fields: {sorted(unknown)}.",
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
    return {"error": {"code": failure.code, "message": str(failure)}}


__all__ = ["PrecheckReadTool"]
