"""Provider-neutral routing policies for geographic observations."""

from __future__ import annotations

from dataclasses import dataclass

from .model import GeoOperation, GeoRequest, GeoRouteContext
from .protocol import GeoProviderCapabilities, GeoProviderExecution


def provider_operation(request: GeoRequest) -> GeoOperation:
    if request.operation is GeoOperation.RESOLVE_PLACE and not request.expands_nearby:
        return GeoOperation.REVERSE_GEOCODE
    return request.operation


@dataclass(frozen=True, slots=True)
class OrderedGeoRoutingPolicy:
    """Choose compatible providers without retaining cross-request state."""

    provider_order: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.provider_order:
            raise ValueError("provider_order must be non-empty")
        if len(set(self.provider_order)) != len(self.provider_order):
            raise ValueError("provider_order must be unique")

    def routes(
        self,
        request: GeoRequest,
        context: GeoRouteContext,
        providers: tuple[GeoProviderCapabilities, ...],
    ) -> tuple[str, ...]:
        operation = provider_operation(request)
        available = {
            provider.provider_id
            for provider in providers
            if operation in provider.operations
        }
        configured = [item for item in self.provider_order if item in available]
        if context.preferred_provider in configured:
            preferred = str(context.preferred_provider)
            configured.remove(preferred)
            configured.insert(0, preferred)
        return tuple(configured)

    def observe(
        self,
        request: GeoRequest,
        context: GeoRouteContext,
        execution: GeoProviderExecution,
    ) -> GeoRouteContext:
        del request
        return GeoRouteContext(execution.attempt.provider, context.locale)
