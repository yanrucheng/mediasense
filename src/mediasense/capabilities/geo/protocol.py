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
    GeoProviderResult,
    MapDatum,
)


@dataclass(frozen=True, slots=True)
class GeoProviderCapabilities:
    provider_id: str
    operations: tuple[GeoOperation, ...]
    input_datum: MapDatum
    max_requests_per_operation: int = 1
    max_billable_units_per_operation: int | None = None

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


@dataclass(frozen=True, slots=True)
class GeoProviderExecution:
    component: GeoComponentResult
    attempt: GeoProviderAttempt


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

    def effect_disclosure(
        self, logical_query_count: int
    ) -> tuple[Mapping[str, object], ...]: ...
