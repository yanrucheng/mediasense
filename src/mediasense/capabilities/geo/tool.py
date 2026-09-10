"""Candidate public adapter for the ``mediasense.geo.query`` contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from dataclasses import replace
import hashlib
import json
import sqlite3
import re
from typing import Any

from .journal import GeoIdempotencyConflict, GeoOperationJournal
from .model import (
    GeoAuthorization,
    GeoCapabilityResult,
    GeoComponentResult,
    GeoComponentStatus,
    GeoCoordinate,
    GeoEffects,
    GeoOperation,
    GeoOutcome,
    GeoRequest,
    GeoRetention,
    GeoRouteContext,
    GeoSubject,
    MapDatum,
)
from .service import GeoCapability
from ._execution_codec import encode

_REQUEST_ID = re.compile(r"^request:[^\s]+$")
_REQUEST_KEYS = {
    "request_id",
    "operation",
    "subjects",
    "locale",
    "radius_meters",
    "max_places",
    "retention",
    "route_context",
    "recovery",
}


class GeoQueryTool:
    """Validate, authorize, journal, and execute one bounded Geo request."""

    name = "mediasense.geo.query"

    def __init__(self, capability: GeoCapability, journal: GeoOperationJournal) -> None:
        self.capability = capability
        self.journal = journal

    def handle(
        self, request, *, authorization=None, cancelled=None, confirmation_proof=None
    ):
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
            return _error("invalid_request", "request_id is missing or invalid")
        with self.journal.ownership(request_id) as owned:
            if not owned:
                return _error(
                    "execution_in_progress",
                    "This request has a live execution owner; replay after it returns.",
                    request_id=request_id,
                )
            return self._handle(
                request,
                authorization=authorization,
                cancelled=cancelled,
                confirmation_proof=confirmation_proof,
            )

    def _handle(
        self,
        request: Mapping[str, Any],
        *,
        authorization: GeoAuthorization | None = None,
        cancelled: Callable[[], bool] | None = None,
        confirmation_proof: Mapping | None = None,
    ) -> dict[str, object]:
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
            return _error("invalid_request", "request_id is missing or invalid")
        try:
            parsed = _parse_request(request)
        except (TypeError, ValueError) as error:
            return _error("invalid_request", str(error), request_id=request_id)

        recovery = request.get("recovery")
        prior = None
        cycle = None
        fingerprint = self.capability.fingerprint(parsed)
        if recovery is not None:
            if not isinstance(recovery, dict) or set(recovery) != {
                "prior_request_id",
                "result_digest",
            }:
                return _error(
                    "invalid_request",
                    "Recovery requires prior_request_id and result_digest",
                    request_id=request_id,
                )
            prior = self.journal.get(str(recovery["prior_request_id"]))
            if prior is None:
                return _error(
                    "request_not_found",
                    "Prior Geo request is not retained",
                    request_id=request_id,
                )
            if result_digest(prior.result) != recovery["result_digest"]:
                return _error(
                    "recovery_stale", "Prior Geo result changed", request_id=request_id
                )
            cycle = self.journal.cycle(prior.request_id)
            if cycle is None or not cycle["closed"]:
                return _error(
                    "recovery_unavailable",
                    "Prior effect has no closed, budgeted execution record",
                    request_id=request_id,
                )
            if (
                _parse_request(json.loads(cycle["request_json"])).fingerprint()
                != parsed.fingerprint()
            ):
                return _error(
                    "idempotency_conflict",
                    "Recovery must retain the original query scope",
                    request_id=request_id,
                )
            parsed = _parse_request(json.loads(cycle["request_json"]))
            fingerprint = result_digest({"request": fingerprint, "recovery": recovery})

        existing = self.journal.get(request_id)
        if existing is not None:
            retained = self.journal.cycle(request_id)
            same_scope = retained is not None and (
                _parse_request(json.loads(retained["request_json"])).fingerprint()
                == parsed.fingerprint()
                and retained["prior_request_id"]
                == (recovery["prior_request_id"] if recovery else None)
            )
            if existing.request_fingerprint != fingerprint and not same_scope:
                return _error(
                    "idempotency_conflict",
                    "request_id was already used with different input",
                    request_id=request_id,
                )
            if (
                authorization is not None
                and existing.authorization_binding != authorization.binding()
            ):
                return _error(
                    "idempotency_conflict",
                    "request_id was already used with different authority",
                    request_id=request_id,
                )
            if existing.state == "indeterminate" and self.journal.cycle(request_id):
                from ._checkpoint import reconcile

                response = reconcile(self.journal, existing, parsed)
                self.journal.complete(request_id, response)
                return response
            return existing.result

        if prior is not None:
            return self._recover(
                request_id,
                parsed,
                prior,
                cycle,
                fingerprint,
                authorization,
                cancelled,
                confirmation_proof,
            )

        preflight = self.capability.preflight(parsed, authorization=authorization)
        if preflight is not None:
            return _response(request_id, preflight)
        assert authorization is not None

        from dataclasses import replace

        indeterminate = replace(
            _indeterminate_result(parsed),
            request_fingerprint=self.capability.fingerprint(parsed),
        )
        try:
            existing = self.journal.admit(
                request_id=request_id,
                request_fingerprint=self.capability.fingerprint(parsed),
                authorization_binding=authorization.binding(),
                indeterminate_result=_response(request_id, indeterminate),
                execution={
                    "request": parsed.value(),
                    "authority": {
                        **authorization.value(),
                        "execution_profile": self.capability.execution_profile,
                        "retry_policy": self.capability.retry_policy.value(),
                        "routing": self.capability.routing_plan(parsed),
                        "precheck_confirmation": dict(confirmation_proof)
                        if confirmation_proof
                        else None,
                    },
                    "max_requests": authorization.envelope.max_provider_requests,
                    "max_billable_units": authorization.envelope.max_billable_units,
                },
            )
        except GeoIdempotencyConflict as error:
            return _error("idempotency_conflict", str(error), request_id=request_id)
        if existing is not None:
            return existing.result

        try:
            result = self.capability.invoke(
                parsed,
                authorization=authorization,
                cancelled=cancelled,
                execute=lambda provider, operation, coordinate, **kwargs: self._execute(
                    request_id, provider, operation, coordinate, **kwargs
                ),
            )
            response = _response(request_id, result)
            self.journal.complete(request_id, response)
        except Exception:
            # The admission journal retains uncertainty; programming failures still surface.
            raise
        return response

    def _recover(
        self,
        request_id,
        parsed,
        prior,
        cycle,
        fingerprint,
        authorization,
        cancelled,
        confirmation_proof,
    ):
        from .model import GeoEffectEnvelope

        root = self.journal.cycle(cycle["root_request_id"])
        original = json.loads(root["authority_json"])
        envelope = GeoEffectEnvelope(**original["effect_envelope"])
        prior_effects = prior.result["effects"]
        used = prior_effects["provider_requests"]
        upper = prior_effects.get("provider_requests_upper_bound", used)
        recovery_context = {
            "root_request_id": cycle["root_request_id"],
            "prior_request_id": prior.request_id,
            "prior_provider_requests": used,
            "prior_provider_requests_upper_bound": upper,
            "prior_billable_units": prior_effects["billable_units"],
            "cumulative_provider_request_ceiling": root["max_requests"],
            "remaining_provider_request_budget": max(0, root["max_requests"] - upper)
            if upper is not None
            else None,
        }
        # The recovery grant includes the cumulative ceiling, not a fresh quota.
        from .service import remaining_request

        if remaining_request(parsed, prior.result) is None:
            return _error(
                "recovery_unavailable",
                "All requested components already have terminal evidence",
                request_id=request_id,
            )
        preflight = self.capability.preflight(parsed, previous=prior.result)
        if preflight is not None and preflight.outcome is GeoOutcome.UNAVAILABLE:
            return _response(
                request_id, replace(preflight, request_fingerprint=fingerprint)
            )
        if authorization is None or (
            authorization.request_fingerprint != fingerprint
            or authorization.envelope != envelope
        ):
            result = self.capability._empty_result(
                parsed,
                GeoOutcome.AUTHORIZATION_REQUIRED,
                fingerprint,
                parsed.route_context,
                required_authorization=envelope,
                qualification=(
                    "recovery_authorization_required",
                    "Authorize recovery under the original cumulative ceiling; prior unknown effects remain recorded.",
                ),
            )
            return {**_response(request_id, result), "recovery": recovery_context}
        for provider in self.capability.providers.values():
            if (
                provider.capabilities.provider_id in envelope.allowed_providers
                and not provider.capabilities.repeatable_queries
            ):
                return _error(
                    "recovery_unavailable",
                    "Provider has not declared repeatable query semantics",
                    request_id=request_id,
                )
        placeholder = _response(
            request_id,
            replace(
                _indeterminate_result(parsed),
                request_fingerprint=fingerprint,
            ),
        )
        try:
            replay = self.journal.admit(
                request_id=request_id,
                request_fingerprint=fingerprint,
                authorization_binding=authorization.binding(),
                indeterminate_result=placeholder,
                execution={
                    "request": parsed.value(),
                    "authority": {
                        **authorization.value(),
                        "execution_profile": self.capability.execution_profile,
                        "retry_policy": self.capability.retry_policy.value(),
                        "routing": self.capability.routing_plan(parsed),
                        "precheck_confirmation": dict(confirmation_proof)
                        if confirmation_proof
                        else None,
                    },
                    "root_request_id": cycle["root_request_id"],
                    "prior_request_id": prior.request_id,
                    "max_requests": root["max_requests"],
                    "max_billable_units": root["max_billable_units"],
                },
            )
        except (GeoIdempotencyConflict, sqlite3.IntegrityError):
            return _error(
                "recovery_stale",
                "Another recovery already owns this result",
                request_id=request_id,
            )
        if replay is not None:
            return replay.result
        result = self.capability.invoke(
            parsed,
            authorization=replace(
                authorization, request_fingerprint=self.capability.fingerprint(parsed)
            ),
            cancelled=cancelled,
            previous={
                **prior.result,
                "attempts": [
                    {
                        "execution_request_id": prior.request_id,
                        "observed_at": prior.result["observed_at"],
                        **a,
                    }
                    for a in prior.result["attempts"]
                ],
                "components": [
                    {"observed_at": prior.result["observed_at"], **c}
                    for c in prior.result["components"]
                ],
            },
            execute=lambda provider, operation, coordinate, **kwargs: self._execute(
                request_id, provider, operation, coordinate, **kwargs
            ),
        )
        response = _response(
            request_id, replace(result, request_fingerprint=fingerprint)
        )
        response["recovery"] = recovery_context
        self.journal.complete(request_id, response)
        return response

    def _execute(self, request_id, provider, operation, coordinate, **kwargs):
        sequence = self.journal.reserve(
            request_id,
            descriptor={
                "provider": provider.capabilities.provider_id,
                "operation": operation.value,
                "coordinate": coordinate.value(),
                "locale": kwargs["locale"],
            },
            requests=provider.capabilities.request_ceiling(operation),
            billable_units=provider.capabilities.max_billable_units_per_operation,
        )
        execution = provider.execute(operation, coordinate, **kwargs)
        observed_at = datetime.now(timezone.utc).isoformat()
        execution = replace(
            execution,
            component=replace(execution.component, observed_at=observed_at),
            additional_components=tuple(
                replace(c, observed_at=observed_at)
                for c in execution.additional_components
            ),
            attempt=replace(
                execution.attempt,
                execution_request_id=request_id,
                observed_at=observed_at,
            ),
            additional_attempts=tuple(
                replace(a, execution_request_id=request_id, observed_at=observed_at)
                for a in execution.additional_attempts
            ),
        )
        self.journal.record_execution(request_id, sequence, encode(execution))
        return execution


def _parse_request(request: Mapping[str, Any]) -> GeoRequest:
    unknown = set(request) - _REQUEST_KEYS
    if unknown:
        raise ValueError(f"unsupported request fields: {', '.join(sorted(unknown))}")
    subjects_value = request.get("subjects")
    if not isinstance(subjects_value, list):
        raise ValueError("subjects must be an array")
    subjects = tuple(_parse_subject(item) for item in subjects_value)
    route_value = request.get("route_context")
    if route_value is None:
        route_context = GeoRouteContext()
    elif isinstance(route_value, Mapping):
        unknown_route = set(route_value) - {"preferred_provider", "locale"}
        if unknown_route:
            raise ValueError("route_context contains unsupported fields")
        route_context = GeoRouteContext(
            _optional_text(route_value.get("preferred_provider")),
            _optional_text(route_value.get("locale")),
        )
    else:
        raise ValueError("route_context must be an object")
    return GeoRequest(
        operation=GeoOperation(str(request.get("operation"))),
        subjects=subjects,
        locale=_required_text(request.get("locale"), "locale"),
        radius_meters=_optional_number(request.get("radius_meters"), "radius_meters"),
        max_places=_optional_integer(request.get("max_places"), "max_places"),
        retention=GeoRetention(str(request.get("retention", "none"))),
        route_context=route_context,
    )


def _parse_subject(value: object) -> GeoSubject:
    if not isinstance(value, Mapping):
        raise ValueError("each subject must be an object")
    if set(value) - {"subject_ref", "coordinate"}:
        raise ValueError("subject contains unsupported fields")
    coordinate = value.get("coordinate")
    if not isinstance(coordinate, Mapping):
        raise ValueError("subject coordinate must be an object")
    if set(coordinate) - {"latitude", "longitude", "datum"}:
        raise ValueError("coordinate contains unsupported fields")
    return GeoSubject(
        _required_text(value.get("subject_ref"), "subject_ref"),
        GeoCoordinate(
            _required_number(coordinate.get("latitude"), "latitude"),
            _required_number(coordinate.get("longitude"), "longitude"),
            MapDatum(_required_text(coordinate.get("datum"), "datum")),
        ),
    )


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("optional text must be a non-empty string")
    return value


def _required_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    return float(value)


def _optional_number(value: object, name: str) -> float | None:
    return None if value is None else _required_number(value, name)


def _optional_integer(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _response(request_id: str, result: GeoCapabilityResult) -> dict[str, object]:
    return {"tool": GeoQueryTool.name, "request_id": request_id, **result.value()}


def result_digest(value: Mapping) -> str:
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )


def _error(
    code: str, message: str, *, request_id: str | None = None
) -> dict[str, object]:
    value: dict[str, object] = {
        "tool": GeoQueryTool.name,
        "outcome": "error",
        "error": {"code": code, "message": message},
    }
    if request_id is not None:
        value["request_id"] = request_id
    return value


def _indeterminate_result(request: GeoRequest) -> GeoCapabilityResult:
    operations = (
        (GeoOperation.REVERSE_GEOCODE, GeoOperation.NEARBY_PLACES)
        if request.expands_nearby
        else (
            GeoOperation.REVERSE_GEOCODE
            if request.operation is GeoOperation.RESOLVE_PLACE
            else request.operation,
        )
    )
    return GeoCapabilityResult(
        operation=request.operation,
        outcome=GeoOutcome.INDETERMINATE,
        request_fingerprint=request.fingerprint(),
        components=tuple(
            GeoComponentResult(
                operation,
                GeoComponentStatus.INDETERMINATE,
                (subject.subject_ref,),
                subject.coordinate,
                qualifications=(
                    {
                        "code": "execution_indeterminate",
                        "message": "The admitted provider effect has no terminal result.",
                    },
                ),
            )
            for subject in request.subjects
            for operation in operations
        ),
        attempts=(),
        effects=GeoEffects(
            request.logical_query_count,
            None,
            None,
            ("coordinate", "datum", "locale"),
            (),
        ),
        continuations=(),
        observed_at=datetime.now(timezone.utc),
        qualifications=(
            {
                "code": "execution_indeterminate",
                "message": "The request was admitted and is not retried automatically.",
            },
        ),
        route_context=request.route_context,
    )
