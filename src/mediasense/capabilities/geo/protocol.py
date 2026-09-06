"""Replaceable provider and routing ports for the Geo capability family."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from typing import Protocol

from .model import (
    GeoComponentResult,
    GeoCoordinate,
    GeoLookupResult,
    GeoOperation,
    GeoProviderAttempt,
    GeoRequest,
    GeoProviderResult,
    GeoRouteContext,
    MapDatum,
)


@dataclass(frozen=True, slots=True)
class GeoProviderCapabilities:
    provider_id: str
    operations: tuple[GeoOperation, ...]
    input_datum: MapDatum
    max_requests_per_operation: int = 1
    max_billable_units_per_operation: int | None = None
    operation_request_ceilings: tuple[tuple[GeoOperation, int], ...] = ()

    def __post_init__(self) -> None:
        if not self.provider_id or self.provider_id.isspace():
            raise ValueError("provider_id must be non-empty")
        object.__setattr__(
            self,
            "operations",
            tuple(GeoOperation(operation) for operation in self.operations),
        )
        object.__setattr__(self, "input_datum", MapDatum(self.input_datum))
        if not self.operations:
            raise ValueError("provider must support at least one operation")
        if len(set(self.operations)) != len(self.operations):
            raise ValueError("provider operations must be unique")
        if self.max_requests_per_operation < 1:
            raise ValueError("max_requests_per_operation must be positive")
        if (
            self.max_billable_units_per_operation is not None
            and self.max_billable_units_per_operation < 0
        ):
            raise ValueError("max_billable_units_per_operation cannot be negative")
        ceilings = tuple(
            (GeoOperation(operation), int(limit))
            for operation, limit in self.operation_request_ceilings
        )
        if len({operation for operation, _limit in ceilings}) != len(ceilings):
            raise ValueError("operation request ceilings must be unique")
        if any(operation not in self.operations for operation, _limit in ceilings):
            raise ValueError("operation request ceiling requires provider support")
        if any(limit < 1 for _operation, limit in ceilings):
            raise ValueError("operation request ceilings must be positive")
        object.__setattr__(self, "operation_request_ceilings", ceilings)

    def request_ceiling(self, operation: GeoOperation) -> int:
        selected = GeoOperation(operation)
        return next(
            (
                limit
                for candidate, limit in self.operation_request_ceilings
                if candidate == selected
            ),
            self.max_requests_per_operation,
        )


@dataclass(frozen=True, slots=True)
class GeoProviderExecution:
    component: GeoComponentResult
    attempt: GeoProviderAttempt
    additional_components: tuple[GeoComponentResult, ...] = ()
    additional_attempts: tuple[GeoProviderAttempt, ...] = ()

    @property
    def components(self) -> tuple[GeoComponentResult, ...]:
        return (self.component, *self.additional_components)

    @property
    def attempts(self) -> tuple[GeoProviderAttempt, ...]:
        return (self.attempt, *self.additional_attempts)


class GeoProvider(Protocol):
    capabilities: GeoProviderCapabilities

    def execute(
        self,
        operation: GeoOperation,
        coordinate: GeoCoordinate,
        *,
        locale: str,
        radius_meters: float | None = None,
        max_places: int | None = None,
    ) -> GeoProviderExecution: ...


class ReverseGeocodeProvider(Protocol):
    provider_id: str
    datum: MapDatum

    def lookup(
        self, coordinate: GeoCoordinate, *, language: str
    ) -> GeoProviderResult: ...


class ReverseGeocodeBatchEngine(Protocol):
    """Provider-neutral batch port retained by the PreCheck stage adapter."""

    def reset(self) -> None: ...

    def routing_state(self) -> dict[str, str]: ...

    def lookup(self, coordinate: GeoCoordinate) -> GeoLookupResult: ...

    def observe(self, result: Mapping[str, object]) -> None: ...


class GeoRoutingPolicy(Protocol):
    def routes(
        self,
        request: GeoRequest,
        context: GeoRouteContext,
        providers: tuple[GeoProviderCapabilities, ...],
    ) -> tuple[str, ...]: ...

    def observe(
        self,
        request: GeoRequest,
        context: GeoRouteContext,
        execution: GeoProviderExecution,
    ) -> GeoRouteContext: ...
