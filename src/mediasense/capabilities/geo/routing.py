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


@dataclass(frozen=True, slots=True)
class RegionalGeoRoutingPolicy:
    """Use suitable services directly; reachability is not geographic evidence."""

    def routes(self, request, context, providers):
        del context
        operation = provider_operation(request)
        available = {p.provider_id for p in providers if operation in p.operations}
        wanted = {
            provider
            for item in self.disclosure(request, providers)
            for provider in item["provider_order"]
        }
        return tuple(
            p for p in ("amap", "google_maps") if p in wanted and p in available
        )

    def disclosure(self, request, providers):
        from .regions import service_region, BOUNDARY_SHA256, BOUNDARY_GUARD_METERS

        available = {
            p.provider_id
            for p in providers
            if provider_operation(request) in p.operations
        }
        coordinates = sorted(
            {s.coordinate for s in request.subjects},
            key=lambda c: (c.latitude, c.longitude, c.datum.value),
        )
        result = []
        for coordinate in coordinates:
            region = service_region(coordinate)
            wanted = {
                "mainland": ("amap",),
                "overseas": ("google_maps",),
                "uncertain": (),
            }[region]
            result.append(
                {
                    "coordinate": coordinate.value(),
                    "region": region,
                    "provider_order": [p for p in wanted if p in available],
                    "required_provider": wanted[0] if wanted else None,
                    "basis": f"Natural Earth 5.1.1 WGS84; sha256:{BOUNDARY_SHA256}; boundary guard {BOUNDARY_GUARD_METERS} m",
                }
            )
        return result

    def observe(self, request, context, execution):
        # A prior point's successful provider never determines the next point.
        return context
