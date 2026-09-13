"""Provider-neutral composition for bounded geographic observations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import time

from .model import (
    GeoAuthorization,
    GeoCapabilityResult,
    GeoComponentResult,
    GeoComponentStatus,
    GeoContinuation,
    GeoCoordinate,
    GeoEffectEnvelope,
    GeoEffects,
    GeoOperation,
    GeoOutcome,
    GeoRequest,
    GeoRetention,
    GeoRouteContext,
    GeoSubject,
    RetryPolicy,
    raise_for_unresolved_request_failure,
)
from .protocol import GeoProvider, GeoRoutingPolicy, GeoProviderExecution
from .routing import provider_operation
from .journal import GeoBudgetExhausted
from ._execution_codec import component as decode_component, attempt as decode_attempt

_EGRESS = ("coordinate", "datum", "locale")
_PROVIDER_CONDITIONS = {
    "authentication",
    "tls_certificate",
    "tls_failure",
    "provider_quota",
    "provider_configuration",
    "provider_response_invalid",
}


def _raise_unexpected_provider_failure(attempts) -> None:
    for attempt in attempts:
        # The Tool has already checkpointed the attempt. These errors cannot
        # prove a location-level outcome, including when read back after a stop.
        raise_for_unresolved_request_failure(attempt.provider, attempt.error_code)


class GeoCapability:
    """Execute one request without reading or mutating caller-owned state."""

    def __init__(
        self,
        providers: Mapping[str, GeoProvider],
        routing: GeoRoutingPolicy,
        *,
        clock: Callable[[], datetime] | None = None,
        execution_profile: Mapping | None = None,
        retry_policy: RetryPolicy = RetryPolicy(),
        monotonic: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not providers:
            raise ValueError("at least one Geo provider is required")
        self.execution_profile = dict(execution_profile) if execution_profile else None
        self.retry_policy = retry_policy
        self._monotonic = monotonic
        self._sleeper = sleeper
        self.providers = dict(providers)
        for provider_id, provider in self.providers.items():
            if provider.capabilities.provider_id != provider_id:
                raise ValueError("provider key and capability identity must match")
        self.routing = routing
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def fingerprint(self, request: GeoRequest) -> str:
        value = {
            "request": request.fingerprint(),
            "execution_semantics": "component-recovery-v3",
            "retry_policy": self.retry_policy.value(),
        }
        if self.routing_plan(request):
            value["routing"] = self.routing_plan(request)
        if self.execution_profile:
            value["execution_profile"] = self.execution_profile
        return (
            "sha256:"
            + hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
        )

    def _wait(
        self, delay: float, deadline: float, cancelled: Callable[[], bool] | None
    ) -> bool:
        until = min(self._monotonic() + delay, deadline)
        while self._monotonic() < until:
            if cancelled is not None and cancelled():
                return False
            self._sleeper(min(0.1, until - self._monotonic()))
        return self._monotonic() < deadline and not (
            cancelled is not None and cancelled()
        )

    def proposed_envelope(
        self,
        request: GeoRequest,
    ) -> GeoEffectEnvelope:
        routes = self._routes(request, request.route_context)
        if not routes:
            raise ValueError("no configured provider supports the requested operation")
        operation = provider_operation(request)
        per_coordinate = [
            self._routes(
                replace(request, subjects=(GeoSubject(refs[0], coordinate),)),
                request.route_context,
            )
            for coordinate, refs in _coordinate_groups(request)
        ]
        max_requests = self.retry_policy.max_attempts * sum(
            self.providers[item].capabilities.request_ceiling(operation)
            for group in per_coordinate
            for item in group
        )
        billable_ceilings = [
            self.providers[item].capabilities.max_billable_units_per_operation
            for group in per_coordinate
            for item in group
        ]
        max_billable_units = (
            self.retry_policy.max_attempts * sum(billable_ceilings)
            if all(item is not None for item in billable_ceilings)
            else None
        )
        return GeoEffectEnvelope(
            allowed_providers=routes,
            allowed_data_classes=_EGRESS,
            max_logical_queries=request.logical_query_count,
            max_provider_requests=max_requests,
            max_billable_units=max_billable_units,
            allow_unknown_billable_units=max_billable_units is None,
            retention=request.retention,
        )

    def invoke(
        self,
        request: GeoRequest,
        *,
        authorization: GeoAuthorization | None = None,
        cancelled: Callable[[], bool] | None = None,
        execute: Callable[..., GeoProviderExecution] | None = None,
        previous: Mapping | None = None,
    ) -> GeoCapabilityResult:
        preflight = self.preflight(
            request, authorization=authorization, previous=previous
        )
        if preflight is not None:
            return preflight

        assert authorization is not None
        fingerprint = self.fingerprint(request)
        route_context = request.route_context
        allowed = set(authorization.envelope.allowed_providers)
        available_routes = self._routes(request, route_context)
        routes = tuple(item for item in available_routes if item in allowed)

        components: list[GeoComponentResult] = []
        attempts = [decode_attempt(a) for a in previous["attempts"]] if previous else []
        current_context = route_context
        request_count = previous["effects"]["provider_requests"] if previous else 0
        if request_count is None:
            request_count = previous["effects"].get("provider_requests_upper_bound")
            if request_count is None:
                raise ValueError("Cannot resume an unbounded cumulative request count")
        billable_known = (
            not previous or previous["effects"]["billable_units"] is not None
        )
        billable_units = (previous["effects"]["billable_units"] or 0) if previous else 0
        groups = _coordinate_groups(request)
        provider_op = provider_operation(request)
        component_operations = _component_operations(request)
        was_cancelled = False
        blocked_code = None

        for index, (coordinate, subject_refs) in enumerate(groups):
            if cancelled is not None and cancelled():
                was_cancelled = True
                components.extend(
                    _unattempted_components(
                        component_operations,
                        groups[index:],
                        "cancelled_before_provider_request",
                        "Cancellation prevented a new provider request.",
                    )
                )
                break
            # Each coordinate is an independent logical query.  A result from an
            # earlier coordinate may suggest a useful continuation to the caller,
            # but must not silently change the provider/language semantics of a
            # later coordinate in the same batch.  That keeps observation identity
            # stable when callers reorder or extend a batch.
            query_context = route_context
            routes = tuple(
                item
                for item in self._routes(
                    replace(
                        request, subjects=(GeoSubject(subject_refs[0], coordinate),)
                    ),
                    query_context,
                )
                if item in allowed
            )
            selected: dict[GeoOperation, GeoComponentResult] = {}
            if previous:
                for raw in previous["components"]:
                    if raw["coordinate"] == coordinate.value() and raw["status"] in {
                        "success",
                        "no_result",
                    }:
                        item = decode_component(raw)
                        selected[item.operation] = item
            if all(op in selected for op in component_operations):
                components.extend(selected[op] for op in component_operations)
                continue
            last: dict[GeoOperation, GeoComponentResult] = {}
            indeterminate = False
            repeat_unknown = False
            stop_code = None
            deadline = self._monotonic() + self.retry_policy.coordinate_deadline_seconds
            for provider_id in routes:
                # An authorized suitable alternative gets its own bounded cycle.
                # Request/billable ceilings and the deadline are still rechecked.
                stop_code = None
                for attempt_number in range(self.retry_policy.max_attempts):
                    provider = self.providers[provider_id]
                    missing = tuple(
                        op for op in component_operations if op not in selected
                    )
                    execute_ops = (
                        missing
                        if provider.capabilities.independent_components
                        else (provider_op,)
                    )
                    ceiling = sum(
                        provider.capabilities.request_ceiling(op) for op in execute_ops
                    )
                    if (
                        request_count + ceiling
                        > authorization.envelope.max_provider_requests
                    ):
                        stop_code = "geo_authority_exhausted"
                        break
                    billable_ceiling = (
                        provider.capabilities.max_billable_units_per_operation
                    )
                    if billable_ceiling is None:
                        if not authorization.envelope.allow_unknown_billable_units:
                            stop_code = "geo_authority_exhausted"
                            break
                    elif (
                        authorization.envelope.max_billable_units is None
                        or billable_units + billable_ceiling
                        > authorization.envelope.max_billable_units
                    ):
                        stop_code = "geo_authority_exhausted"
                        break
                    if cancelled is not None and cancelled():
                        was_cancelled = True
                        break
                    if self._monotonic() >= deadline:
                        stop_code = "geo_deadline_exhausted"
                        break
                    pieces = []
                    for execute_op in execute_ops:
                        kwargs = dict(
                            locale=request.locale,
                            radius_meters=request.radius_meters,
                            max_places=request.max_places,
                            deadline=deadline,
                            cancelled=cancelled,
                        )
                        try:
                            piece = (
                                provider.execute(execute_op, coordinate, **kwargs)
                                if execute is None
                                else execute(provider, execute_op, coordinate, **kwargs)
                            )
                        except GeoBudgetExhausted:
                            stop_code = "geo_authority_exhausted"
                            break
                        pieces.append(piece)
                        _raise_unexpected_provider_failure(piece.attempts)
                        if any(
                            a.error_code in _PROVIDER_CONDITIONS for a in piece.attempts
                        ):
                            stop_code = "geo_provider_condition_unresolved"
                            break
                        if any(
                            c.status is GeoComponentStatus.INDETERMINATE
                            for c in piece.components
                        ):
                            break
                    if not pieces:
                        break
                    indeterminate = False
                    all_components = tuple(
                        c for piece in pieces for c in piece.components
                    )
                    all_attempts = tuple(a for piece in pieces for a in piece.attempts)
                    execution = GeoProviderExecution(
                        all_components[0],
                        all_attempts[0],
                        all_components[1:],
                        all_attempts[1:],
                    )
                    execution_attempts = execution.attempts
                    if any(
                        attempt.provider != provider_id
                        for attempt in execution_attempts
                    ):
                        raise ValueError(
                            "provider attempt identity does not match adapter"
                        )
                    execution_request_count = sum(
                        attempt.provider_requests for attempt in execution_attempts
                    )
                    if execution_request_count > ceiling:
                        raise ValueError(
                            "provider exceeded its declared request ceiling"
                        )
                    if billable_ceiling is not None and any(
                        attempt.billable_units is None for attempt in execution_attempts
                    ):
                        raise ValueError(
                            "provider did not report declared billable-unit accounting"
                        )
                    execution_billable_units = sum(
                        attempt.billable_units or 0 for attempt in execution_attempts
                    )
                    if (
                        billable_ceiling is not None
                        and execution_billable_units > billable_ceiling
                    ):
                        raise ValueError("provider exceeded its billable-unit ceiling")
                    attempts.extend(execution_attempts)
                    request_count += execution_request_count
                    if any(
                        attempt.billable_units is None for attempt in execution_attempts
                    ):
                        billable_known = False
                    else:
                        billable_units += execution_billable_units
                    current_context = self.routing.observe(
                        request, query_context, execution
                    )
                    returned = {
                        component.operation: replace(
                            component,
                            subject_refs=subject_refs,
                            coordinate=coordinate,
                        )
                        for component in execution.components
                    }
                    if len(returned) != len(execution.components):
                        raise ValueError("provider returned duplicate Geo components")
                    unexpected = set(returned) - set(component_operations)
                    if unexpected:
                        raise ValueError(
                            "provider returned an unexpected Geo component"
                        )
                    for operation in missing:
                        component = returned.get(operation)
                        if component is None:
                            component = GeoComponentResult(
                                operation,
                                GeoComponentStatus.NOT_REQUESTED
                                if stop_code
                                else GeoComponentStatus.FAILED,
                                subject_refs,
                                coordinate,
                                qualifications=(
                                    {
                                        "code": stop_code
                                        or "provider_result_incomplete",
                                        "message": (
                                            "Provider condition prevented this component request."
                                            if stop_code
                                            else "Provider omitted a required Geo component."
                                        ),
                                    },
                                ),
                            )
                        if component.status in {
                            GeoComponentStatus.SUCCESS,
                            GeoComponentStatus.NO_RESULT,
                        }:
                            selected.setdefault(operation, component)
                        if component.status is GeoComponentStatus.INDETERMINATE:
                            # A later unobserved attempt does not revoke evidence
                            # already obtained by an earlier successful request.
                            last[operation] = component
                            indeterminate = True
                        else:
                            prior_component = last.get(operation)
                            if prior_component is None or _component_rank(
                                component
                            ) >= _component_rank(prior_component):
                                last[operation] = component
                    repeat_unknown = provider.capabilities.repeatable_queries and all(
                        a.error_code
                        in {"transport_timeout", "connection_lost", "transport_unknown"}
                        for a in execution_attempts
                        if a.status is GeoComponentStatus.INDETERMINATE
                    )
                    if indeterminate and not repeat_unknown:
                        break
                    if all(operation in selected for operation in component_operations):
                        break
                    if stop_code is not None:
                        break
                    retryable = (indeterminate and repeat_unknown) or any(
                        attempt.error_code
                        in {
                            "transient",
                            "rate_limited",
                            "service_transient",
                            "dns_failure",
                            "connection_refused",
                        }
                        and attempt.status is GeoComponentStatus.FAILED
                        for attempt in execution_attempts
                    )
                    if not retryable:
                        if any(
                            a.error_code in _PROVIDER_CONDITIONS
                            for a in execution_attempts
                        ):
                            stop_code = "geo_provider_condition_unresolved"
                        break
                    if attempt_number + 1 == self.retry_policy.max_attempts:
                        stop_code = "geo_retry_exhausted"
                    if attempt_number + 1 < self.retry_policy.max_attempts:
                        if not self._wait(
                            max(
                                self.retry_policy.backoff_seconds[attempt_number],
                                *(
                                    a.retry_after_seconds or 0
                                    for a in execution_attempts
                                ),
                            ),
                            deadline,
                            cancelled,
                        ):
                            was_cancelled = bool(cancelled is not None and cancelled())
                            stop_code = (
                                "geo_cancelled"
                                if was_cancelled
                                else "geo_deadline_exhausted"
                            )
                            break
                if (
                    (indeterminate and not repeat_unknown)
                    or was_cancelled
                    or all(op in selected for op in component_operations)
                ):
                    break
            coordinate_components = tuple(
                selected.get(operation)
                or last.get(operation)
                or GeoComponentResult(
                    operation,
                    GeoComponentStatus.FAILED,
                    subject_refs,
                    coordinate,
                    qualifications=(
                        {
                            "code": "request_ceiling_exhausted",
                            "message": "No further authorized provider request remained.",
                        },
                    ),
                )
                for operation in component_operations
            )
            if stop_code is not None:
                coordinate_components = tuple(
                    replace(
                        component,
                        qualifications=(
                            *component.qualifications,
                            {
                                "code": stop_code,
                                "message": f"No further Geo request is admissible: {stop_code}.",
                            },
                        ),
                    )
                    if component.status is GeoComponentStatus.FAILED
                    else component
                    for component in coordinate_components
                )
            components.extend(coordinate_components)
            unresolved = any(
                c.status
                not in {GeoComponentStatus.SUCCESS, GeoComponentStatus.NO_RESULT}
                for c in coordinate_components
            )
            if unresolved and stop_code is not None:
                blocked_code = stop_code
                components.extend(
                    _unattempted_components(
                        component_operations,
                        groups[index + 1 :],
                        stop_code,
                        "The required provider or execution budget is unavailable; resolve this condition before continuing.",
                    )
                )
                break
            if any(
                component.status is GeoComponentStatus.INDETERMINATE
                for component in coordinate_components
            ):
                components.extend(
                    _unattempted_components(
                        component_operations,
                        groups[index + 1 :],
                        "stopped_after_indeterminate_effect",
                        "No new request was admitted after an indeterminate effect.",
                    )
                )
                break

        outcome = (
            GeoOutcome.CANCELLED
            if was_cancelled
            else GeoOutcome.BLOCKED
            if blocked_code
            else _overall_outcome(tuple(components))
        )
        continuations = (
            ()
            if outcome
            in {GeoOutcome.CANCELLED, GeoOutcome.INDETERMINATE, GeoOutcome.BLOCKED}
            else _continuations(request, tuple(components))
        )
        return GeoCapabilityResult(
            operation=request.operation,
            outcome=outcome,
            request_fingerprint=fingerprint,
            components=tuple(components),
            attempts=tuple(attempts),
            effects=GeoEffects(
                logical_queries=request.logical_query_count,
                provider_requests=None
                if any(a.request_count_kind != "exact" for a in attempts)
                else request_count,
                provider_requests_upper_bound=request_count
                if any(a.request_count_kind != "exact" for a in attempts)
                else None,
                billable_units=billable_units if billable_known else None,
                transmitted_data_classes=_EGRESS if request_count else (),
                providers_attempted=tuple(attempt.provider for attempt in attempts),
            ),
            continuations=continuations,
            observed_at=self._clock(),
            route_context=current_context,
            execution_profile=self.execution_profile,
            routing=self.routing_plan(request),
            qualifications=(
                {
                    "code": blocked_code,
                    "message": "Resolve the provider, network, or budget condition, then explicitly authorize recovery.",
                },
            )
            if blocked_code
            else (),
        )

    def preflight(
        self,
        request: GeoRequest,
        *,
        authorization: GeoAuthorization | None = None,
        previous: Mapping | None = None,
    ) -> GeoCapabilityResult | None:
        """Return a no-effect terminal result, or ``None`` when execution is allowed."""

        fingerprint = self.fingerprint(request)
        route_context = request.route_context
        execution_scope = remaining_request(request, previous) or request
        available_routes = self._routes(execution_scope, route_context)
        plan = self.routing_plan(execution_scope)
        missing = [item for item in plan if not item["provider_order"]]
        if missing:
            uncertain = any(item["region"] == "uncertain" for item in missing)
            return self._empty_result(
                request,
                GeoOutcome.UNAVAILABLE,
                fingerprint,
                route_context,
                qualification=(
                    "region_uncertain" if uncertain else "provider_unavailable",
                    "The offline boundary cannot establish a suitable route for a boundary-near coordinate; inspect routing evidence before changing scope."
                    if uncertain
                    else "Configure the required service shown in routing evidence; a reachable service for another region is not an alternative.",
                ),
            )

        if not available_routes:
            return self._empty_result(
                request,
                GeoOutcome.UNAVAILABLE,
                fingerprint,
                route_context,
                qualification=(
                    "provider_unavailable",
                    "No configured provider supports the requested operation.",
                ),
            )
        proposed = self.proposed_envelope(execution_scope)
        if authorization is None:
            return self._empty_result(
                request,
                GeoOutcome.AUTHORIZATION_REQUIRED,
                fingerprint,
                route_context,
                required_authorization=proposed,
                qualification=(
                    "authorization_required",
                    "No provider request was sent.",
                ),
            )
        mismatch = (
            "authorization does not match the exact request"
            if authorization.request_fingerprint != fingerprint
            else self._authorization_mismatch(
                execution_scope,
                replace(
                    authorization, request_fingerprint=self.fingerprint(execution_scope)
                ),
                proposed,
            )
        )
        if mismatch is not None:
            return self._empty_result(
                request,
                GeoOutcome.AUTHORIZATION_REQUIRED,
                fingerprint,
                route_context,
                required_authorization=proposed,
                qualification=("authorization_mismatch", mismatch),
            )

        allowed = set(authorization.envelope.allowed_providers)
        routes = tuple(item for item in available_routes if item in allowed)
        if not routes:
            return self._empty_result(
                request,
                GeoOutcome.UNAVAILABLE,
                fingerprint,
                route_context,
                qualification=(
                    "provider_unavailable",
                    "No authorized provider supports the requested operation.",
                ),
            )
        return None

    def routing_plan(self, request):
        disclosure = getattr(self.routing, "disclosure", None)
        return (
            tuple(
                disclosure(
                    request, tuple(p.capabilities for p in self.providers.values())
                )
            )
            if disclosure
            else ()
        )

    def _routes(self, request: GeoRequest, context: GeoRouteContext) -> tuple[str, ...]:
        routes = self.routing.routes(
            request,
            context,
            tuple(provider.capabilities for provider in self.providers.values()),
        )
        if any(item not in self.providers for item in routes):
            raise ValueError("routing policy selected an unconfigured provider")
        return routes

    def _authorization_mismatch(
        self,
        request: GeoRequest,
        authorization: GeoAuthorization,
        proposed: GeoEffectEnvelope,
    ) -> str | None:
        envelope = authorization.envelope
        if authorization.request_fingerprint != self.fingerprint(request):
            return "authorization does not match the exact request"
        if envelope.max_logical_queries < request.logical_query_count:
            return "logical-query ceiling is too small"
        if not set(_EGRESS) <= set(envelope.allowed_data_classes):
            return "authorization does not permit the required data classes"
        if (
            request.retention is GeoRetention.CALLER_STATE
            and envelope.retention is not GeoRetention.CALLER_STATE
        ):
            return "authorization does not permit caller-state retention"
        supported = set(proposed.allowed_providers)
        permitted = supported.intersection(envelope.allowed_providers)
        if not permitted:
            return "authorization permits no compatible provider"
        operation = provider_operation(request)
        coordinate_routes = [
            set(
                self._routes(
                    replace(request, subjects=(GeoSubject(refs[0], coordinate),)),
                    request.route_context,
                )
            ).intersection(permitted)
            for coordinate, refs in _coordinate_groups(request)
        ]
        if any(not routes for routes in coordinate_routes):
            return "authorization does not cover the suitable provider for every coordinate"
        minimum_requests = sum(
            min(
                self.providers[item].capabilities.request_ceiling(operation)
                for item in routes
            )
            for routes in coordinate_routes
        )
        if envelope.max_provider_requests < minimum_requests:
            return "provider-request ceiling cannot cover the logical queries"
        billable_ceilings = [
            self.providers[item].capabilities.max_billable_units_per_operation
            for item in permitted
        ]
        if any(item is None for item in billable_ceilings):
            if not envelope.allow_unknown_billable_units:
                return "authorization does not permit unknown billable units"
        else:
            required_billable_units = request.logical_query_count * min(
                billable_ceilings
            )
            if (
                envelope.max_billable_units is None
                or envelope.max_billable_units < required_billable_units
            ):
                return "billable-unit ceiling cannot cover the logical queries"
        return None

    def _empty_result(
        self,
        request: GeoRequest,
        outcome: GeoOutcome,
        fingerprint: str,
        route_context: GeoRouteContext,
        *,
        required_authorization: GeoEffectEnvelope | None = None,
        qualification: tuple[str, str],
    ) -> GeoCapabilityResult:
        code, message = qualification
        return GeoCapabilityResult(
            operation=request.operation,
            outcome=outcome,
            request_fingerprint=fingerprint,
            components=(),
            attempts=(),
            effects=GeoEffects(0, 0, 0, (), ()),
            continuations=(),
            observed_at=self._clock(),
            qualifications=({"code": code, "message": message},),
            required_authorization=required_authorization,
            route_context=route_context,
            execution_profile=self.execution_profile,
            routing=self.routing_plan(request),
        )


def remaining_request(request, previous):
    if previous is None:
        return request
    required = set(_component_operations(request))
    complete = {}
    for raw in previous["components"]:
        if raw["status"] in {"success", "no_result"}:
            complete.setdefault(GeoCoordinate(**raw["coordinate"]), set()).add(
                GeoOperation(raw["operation"])
            )
    subjects = tuple(
        s for s in request.subjects if not required <= complete.get(s.coordinate, set())
    )
    return replace(request, subjects=subjects) if subjects else None


def _coordinate_groups(
    request: GeoRequest,
) -> tuple[tuple[GeoCoordinate, tuple[str, ...]], ...]:
    grouped: dict[tuple[float, float, str], tuple[GeoCoordinate, list[str]]] = {}
    for subject in request.subjects:
        coordinate = subject.coordinate
        key = (coordinate.latitude, coordinate.longitude, coordinate.datum.value)
        if key not in grouped:
            grouped[key] = (coordinate, [])
        grouped[key][1].append(subject.subject_ref)
    return tuple(
        (coordinate, tuple(subject_refs))
        for coordinate, subject_refs in grouped.values()
    )


def _component_operations(request: GeoRequest) -> tuple[GeoOperation, ...]:
    if request.expands_nearby:
        return (GeoOperation.REVERSE_GEOCODE, GeoOperation.NEARBY_PLACES)
    return (provider_operation(request),)


def _component_rank(component: GeoComponentResult) -> int:
    return {
        GeoComponentStatus.NOT_REQUESTED: 0,
        GeoComponentStatus.FAILED: 1,
        GeoComponentStatus.NO_RESULT: 2,
        GeoComponentStatus.SUCCESS: 3,
        GeoComponentStatus.INDETERMINATE: 4,
    }[component.status]


def _overall_outcome(components: tuple[GeoComponentResult, ...]) -> GeoOutcome:
    statuses = {component.status for component in components}
    if statuses == {GeoComponentStatus.SUCCESS}:
        return GeoOutcome.SUCCESS
    if GeoComponentStatus.INDETERMINATE in statuses:
        return GeoOutcome.INDETERMINATE
    if GeoComponentStatus.SUCCESS in statuses:
        return GeoOutcome.PARTIAL
    if statuses == {GeoComponentStatus.NO_RESULT}:
        return GeoOutcome.NO_RESULT
    return GeoOutcome.FAILED


def _unattempted_components(
    operations: tuple[GeoOperation, ...],
    groups: tuple[tuple[GeoCoordinate, tuple[str, ...]], ...],
    code: str,
    message: str,
) -> tuple[GeoComponentResult, ...]:
    return tuple(
        GeoComponentResult(
            operation,
            GeoComponentStatus.NOT_REQUESTED,
            subject_refs,
            coordinate,
            qualifications=({"code": code, "message": message},),
        )
        for coordinate, subject_refs in groups
        for operation in operations
    )


def _continuations(
    request: GeoRequest, components: tuple[GeoComponentResult, ...]
) -> tuple[GeoContinuation, ...]:
    if request.operation is not GeoOperation.RESOLVE_PLACE or request.expands_nearby:
        return ()
    if not any(
        component.status in {GeoComponentStatus.SUCCESS, GeoComponentStatus.NO_RESULT}
        for component in components
    ):
        return ()
    return (
        GeoContinuation(
            GeoOperation.NEARBY_PLACES,
            "Nearby-place evidence may refine or challenge the address candidate.",
            True,
        ),
    )
