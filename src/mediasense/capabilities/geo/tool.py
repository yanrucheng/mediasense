"""Candidate public adapter for the ``mediasense.geo.query`` contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
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
}


class GeoQueryTool:
    """Validate, authorize, journal, and execute one bounded Geo request."""

    name = "mediasense.geo.query"

    def __init__(self, capability: GeoCapability, journal: GeoOperationJournal) -> None:
        self.capability = capability
        self.journal = journal

    def handle(
        self,
        request: Mapping[str, Any],
        *,
        authorization: GeoAuthorization | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        request_id = request.get("request_id")
        if not isinstance(request_id, str) or _REQUEST_ID.fullmatch(request_id) is None:
            return _error("invalid_request", "request_id is missing or invalid")
        try:
            parsed = _parse_request(request)
        except (TypeError, ValueError) as error:
            return _error("invalid_request", str(error), request_id=request_id)

        existing = self.journal.get(request_id)
        if existing is not None:
            if existing.request_fingerprint != parsed.fingerprint():
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
            return existing.result

        preflight = self.capability.preflight(parsed, authorization=authorization)
        if preflight is not None:
            return _response(request_id, preflight)
        assert authorization is not None

        indeterminate = _indeterminate_result(parsed)
        try:
            existing = self.journal.admit(
                request_id=request_id,
                request_fingerprint=parsed.fingerprint(),
                authorization_binding=authorization.binding(),
                indeterminate_result=_response(request_id, indeterminate),
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
            )
            response = _response(request_id, result)
            self.journal.complete(request_id, response)
        except Exception:
            return _response(request_id, indeterminate)
        return response


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
    return GeoCapabilityResult(
        operation=request.operation,
        outcome=GeoOutcome.INDETERMINATE,
        request_fingerprint=request.fingerprint(),
        components=tuple(
            GeoComponentResult(
                GeoOperation.REVERSE_GEOCODE
                if request.operation is GeoOperation.RESOLVE_PLACE
                else request.operation,
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
