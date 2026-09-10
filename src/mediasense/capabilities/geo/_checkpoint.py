"""Reconcile a stopped execution from persisted reservations, without network I/O."""

from dataclasses import replace
from datetime import datetime, timezone
import json

from ._execution_codec import component as decode_component, attempt as decode_attempt
from .model import (
    GeoCapabilityResult,
    GeoComponentResult,
    GeoComponentStatus,
    GeoCoordinate,
    GeoEffects,
    GeoOutcome,
    GeoProviderAttempt,
    GeoOperation,
)
from .service import _coordinate_groups, _component_operations, _overall_outcome


def reconcile(journal, entry, request):
    cycle = journal.cycle(entry.request_id)
    prior = (
        journal.get(cycle["prior_request_id"]) if cycle["prior_request_id"] else None
    )
    selected = {}
    attempts = []
    if prior:
        selected = {
            (
                GeoCoordinate(**c["coordinate"]),
                GeoOperation(c["operation"]),
            ): decode_component(c)
            for c in prior.result["components"]
        }
        attempts = [decode_attempt(a) for a in prior.result["attempts"]]
    for coordinate, refs in _coordinate_groups(request):
        for operation in _component_operations(request):
            selected.setdefault(
                (coordinate, operation),
                GeoComponentResult(
                    operation,
                    GeoComponentStatus.NOT_REQUESTED,
                    refs,
                    coordinate,
                    qualifications=(
                        {
                            "code": "execution_interrupted",
                            "message": "No provider reservation was recorded for this component.",
                        },
                    ),
                ),
            )
    for row in journal.executions(entry.request_id):
        descriptor = json.loads(row["descriptor_json"])
        coordinate = GeoCoordinate(**descriptor["coordinate"])
        if row["execution_json"] is not None:
            execution = json.loads(row["execution_json"])
            attempts.extend(decode_attempt(a) for a in execution["attempts"])
            components = [decode_component(c) for c in execution["components"]]
        else:
            operation = GeoOperation(descriptor["operation"])
            message = "Execution stopped after reservation; transmission and completion are unknown. The reserved upper bound remains occupied."
            attempts.append(
                GeoProviderAttempt(
                    descriptor["provider"],
                    operation,
                    GeoComponentStatus.INDETERMINATE,
                    coordinate,
                    None,
                    row["reserved_requests"],
                    None,
                    "execution_interrupted",
                    message,
                    request_count_kind="reserved_upper_bound",
                    execution_request_id=entry.request_id,
                )
            )
            operations = (
                _component_operations(request)
                if operation is GeoOperation.RESOLVE_PLACE
                else (operation,)
            )
            components = [
                GeoComponentResult(
                    op,
                    GeoComponentStatus.INDETERMINATE,
                    (),
                    coordinate,
                    qualifications=(
                        {"code": "execution_interrupted", "message": message},
                    ),
                )
                for op in operations
            ]
        for component in components:
            key = (coordinate, component.operation)
            old = selected[key]
            if old.status not in {
                GeoComponentStatus.SUCCESS,
                GeoComponentStatus.NO_RESULT,
            }:
                selected[key] = replace(
                    component, subject_refs=old.subject_refs, coordinate=coordinate
                )
    components = tuple(selected.values())
    # A legacy root's attempts are already included in its persisted response.
    upper = sum(a.provider_requests for a in attempts)
    unknown = any(a.request_count_kind != "exact" for a in attempts)
    bills = (
        None
        if any(a.billable_units is None for a in attempts)
        else sum(a.billable_units for a in attempts)
    )
    latest_attempts = {}
    for attempt in attempts:
        operations = (
            _component_operations(request)
            if attempt.operation is GeoOperation.RESOLVE_PLACE
            else (attempt.operation,)
        )
        for operation in operations:
            latest_attempts[(attempt.input_coordinate, operation)] = attempt
    service_failures = {
        "transient",
        "service_transient",
        "rate_limited",
        "dns_failure",
        "connection_refused",
        "authentication",
        "tls_certificate",
        "tls_failure",
        "provider_quota",
        "provider_response_invalid",
    }
    needs_attention = any(
        c.status is GeoComponentStatus.NOT_REQUESTED for c in components
    )
    for component in components:
        attempt = latest_attempts.get((component.coordinate, component.operation))
        if (
            component.status is GeoComponentStatus.FAILED
            and attempt is not None
            and attempt.status is GeoComponentStatus.FAILED
            and attempt.error_code in service_failures
        ):
            needs_attention = True
    original_authority = json.loads(cycle["authority_json"])
    result = GeoCapabilityResult(
        request.operation,
        GeoOutcome.BLOCKED if needs_attention else _overall_outcome(components),
        entry.request_fingerprint,
        components,
        tuple(attempts),
        GeoEffects(
            request.logical_query_count,
            None if unknown else upper,
            bills,
            ("coordinate", "datum", "locale") if upper else (),
            tuple(dict.fromkeys(a.provider for a in attempts)),
            upper if unknown else None,
        ),
        (),
        datetime.now(timezone.utc),
        qualifications=(
            {
                "code": "execution_checkpoint_reconciled",
                "message": "Retained provider checkpoints were reconciled without sending a request.",
            },
        ),
        route_context=request.route_context,
        execution_profile=original_authority.get("execution_profile"),
        routing=tuple(original_authority.get("routing", ())),
    )
    return {
        "tool": "mediasense.geo.query",
        "request_id": entry.request_id,
        **result.value(),
    }
