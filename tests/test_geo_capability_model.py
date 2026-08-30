from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
import ast
from pathlib import Path

import pytest

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCandidate,
    GeoCandidateKind,
    GeoCapabilityResult,
    GeoComponentResult,
    GeoComponentStatus,
    GeoContinuation,
    GeoCoordinate,
    GeoEffectEnvelope,
    GeoEffects,
    GeoOperation,
    GeoOutcome,
    GeoProviderAttempt,
    GeoProviderCapabilities,
    GeoProviderExecution,
    GeoRequest,
    GeoRetention,
    GeoRouteContext,
    GeoSubject,
    MapDatum,
    OrderedGeoRoutingPolicy,
)


def test_request_fingerprint_binds_operation_subjects_and_options() -> None:
    subject = GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579))
    address = GeoRequest(GeoOperation.REVERSE_GEOCODE, (subject,), "zh-CN")
    nearby = GeoRequest(
        GeoOperation.NEARBY_PLACES,
        (subject,),
        "zh-CN",
        radius_meters=500,
        max_places=10,
    )

    assert address.fingerprint() == address.fingerprint()
    assert address.fingerprint() != nearby.fingerprint()
    assert address.logical_query_count == 1


def test_logical_query_count_deduplicates_coordinates_without_losing_subjects() -> None:
    coordinate = GeoCoordinate(31.1434, 121.6579)
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (
            GeoSubject("source-item:one", coordinate),
            GeoSubject("source-item:two", coordinate),
        ),
        "zh-CN",
    )

    assert request.logical_query_count == 1
    assert [item["subject_ref"] for item in request.value()["subjects"]] == [
        "source-item:one",
        "source-item:two",
    ]


def test_nearby_places_requires_bounded_radius_and_result_count() -> None:
    subject = GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579))

    with pytest.raises(ValueError, match="requires radius_meters and max_places"):
        GeoRequest(GeoOperation.NEARBY_PLACES, (subject,), "zh-CN")

    with pytest.raises(ValueError, match="apply only to nearby_places"):
        GeoRequest(
            GeoOperation.REVERSE_GEOCODE,
            (subject,),
            "zh-CN",
            radius_meters=500,
        )


def test_effect_envelope_rejects_forbidden_egress_and_invalid_ceilings() -> None:
    with pytest.raises(ValueError, match="forbidden egress"):
        GeoEffectEnvelope(
            ("amap",),
            1,
            1,
            allowed_data_classes=("coordinate", "filename"),
        )

    with pytest.raises(ValueError, match="max_provider_requests"):
        GeoEffectEnvelope(("amap",), 1, 0)


def test_authorization_requires_exact_identity_and_timezone() -> None:
    envelope = GeoEffectEnvelope(
        ("amap",),
        1,
        1,
        retention=GeoRetention.CALLER_STATE,
    )

    with pytest.raises(ValueError, match="sha256 identity"):
        GeoAuthorization("human:one", "request:one", datetime.now(timezone.utc), envelope)

    with pytest.raises(ValueError, match="timezone"):
        GeoAuthorization("human:one", "sha256:" + "a" * 64, datetime.now(), envelope)


def test_component_status_distinguishes_not_requested_from_no_result() -> None:
    coordinate = GeoCoordinate(31.1434, 121.6579)
    not_requested = GeoComponentResult(
        GeoOperation.NEARBY_PLACES,
        GeoComponentStatus.NOT_REQUESTED,
        ("source-item:one",),
        coordinate,
    )
    no_result = GeoComponentResult(
        GeoOperation.NEARBY_PLACES,
        GeoComponentStatus.NO_RESULT,
        ("source-item:one",),
        coordinate,
    )

    assert not_requested.status is GeoComponentStatus.NOT_REQUESTED
    assert no_result.status is GeoComponentStatus.NO_RESULT


def test_result_keeps_candidate_attempt_effect_and_continuation_distinct() -> None:
    coordinate = GeoCoordinate(31.1434, 121.6579)
    candidate = GeoCandidate(
        GeoCandidateKind.ADDRESS,
        "Shanghai Disneyland area",
        coordinate=coordinate,
    )
    component = GeoComponentResult(
        GeoOperation.REVERSE_GEOCODE,
        GeoComponentStatus.SUCCESS,
        ("source-item:one",),
        coordinate,
        (candidate,),
    )
    attempt = GeoProviderAttempt(
        "amap",
        GeoOperation.REVERSE_GEOCODE,
        GeoComponentStatus.SUCCESS,
        coordinate,
        GeoCoordinate(31.1417, 121.6628, MapDatum.GCJ02),
        provider_requests=1,
        billable_units=1,
    )
    result = GeoCapabilityResult(
        GeoOperation.RESOLVE_PLACE,
        GeoOutcome.SUCCESS,
        "sha256:" + "a" * 64,
        (component,),
        (attempt,),
        GeoEffects(1, 1, 1, ("coordinate", "datum", "locale"), ("amap",)),
        (
            GeoContinuation(
                GeoOperation.NEARBY_PLACES,
                "Nearby candidates may disambiguate the address.",
                True,
            ),
        ),
        datetime.now(timezone.utc),
    )

    assert result.components[0].candidates[0].name == "Shanghai Disneyland area"
    assert result.attempts[0].provider == "amap"
    assert result.continuations[0].requires_authorization is True


def test_provider_capabilities_are_normalized_and_unique() -> None:
    capabilities = GeoProviderCapabilities(
        "google_maps",
        (GeoOperation.REVERSE_GEOCODE, GeoOperation.NEARBY_PLACES),
        MapDatum.WGS84,
    )

    assert capabilities.operations == (
        GeoOperation.REVERSE_GEOCODE,
        GeoOperation.NEARBY_PLACES,
    )
    assert GeoRouteContext("google_maps", "en").preferred_provider == "google_maps"

    with pytest.raises(ValueError, match="unique"):
        GeoProviderCapabilities(
            "google_maps",
            (GeoOperation.REVERSE_GEOCODE, GeoOperation.REVERSE_GEOCODE),
            MapDatum.WGS84,
        )


@dataclass
class _FakeProvider:
    capabilities: GeoProviderCapabilities
    status: GeoComponentStatus = GeoComponentStatus.SUCCESS
    calls: int = 0

    def execute(
        self,
        operation: GeoOperation,
        coordinate: GeoCoordinate,
        *,
        locale: str,
        radius_meters: float | None = None,
        max_places: int | None = None,
    ) -> GeoProviderExecution:
        self.calls += 1
        candidates = (
            GeoCandidate(GeoCandidateKind.ADDRESS, "candidate", coordinate=coordinate),
        ) if self.status is GeoComponentStatus.SUCCESS else ()
        return GeoProviderExecution(
            GeoComponentResult(operation, self.status, ("provider",), coordinate, candidates),
            GeoProviderAttempt(
                self.capabilities.provider_id,
                operation,
                self.status,
                coordinate,
                coordinate,
                1,
                None,
            ),
        )


def test_capability_preflight_has_zero_effects_and_exact_proposal() -> None:
    from mediasense.capabilities.geo import GeoCapability

    provider = _FakeProvider(
        GeoProviderCapabilities(
            "provider-a",
            (GeoOperation.REVERSE_GEOCODE, GeoOperation.NEARBY_PLACES),
            MapDatum.WGS84,
        )
    )
    capability = GeoCapability(
        {"provider-a": provider}, OrderedGeoRoutingPolicy(("provider-a",))
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579)),),
        "zh-CN",
        retention=GeoRetention.CALLER_STATE,
    )

    result = capability.invoke(request)

    assert result.outcome is GeoOutcome.AUTHORIZATION_REQUIRED
    assert result.required_authorization is not None
    assert result.required_authorization.max_logical_queries == 1
    assert result.effects.provider_requests == 0
    assert provider.calls == 0


def test_capability_requires_new_authority_for_stale_binding_before_effect() -> None:
    from mediasense.capabilities.geo import GeoCapability

    provider = _FakeProvider(
        GeoProviderCapabilities(
            "provider-a", (GeoOperation.REVERSE_GEOCODE,), MapDatum.WGS84
        )
    )
    capability = GeoCapability(
        {"provider-a": provider}, OrderedGeoRoutingPolicy(("provider-a",))
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579)),),
        "zh-CN",
    )
    authorization = GeoAuthorization(
        "human:one",
        "sha256:" + "a" * 64,
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )

    result = capability.invoke(request, authorization=authorization)

    assert result.outcome is GeoOutcome.AUTHORIZATION_REQUIRED
    assert result.required_authorization == capability.proposed_envelope(request)
    assert result.qualifications[0]["code"] == "authorization_mismatch"
    assert result.effects.provider_requests == 0
    assert provider.calls == 0


def test_capability_executes_with_exact_authority_and_offers_bounded_continuation() -> None:
    from mediasense.capabilities.geo import GeoCapability

    provider = _FakeProvider(
        GeoProviderCapabilities(
            "provider-a",
            (GeoOperation.REVERSE_GEOCODE, GeoOperation.NEARBY_PLACES),
            MapDatum.WGS84,
        )
    )
    capability = GeoCapability(
        {"provider-a": provider}, OrderedGeoRoutingPolicy(("provider-a",))
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579)),),
        "zh-CN",
    )
    envelope = capability.proposed_envelope(request)
    authorization = GeoAuthorization(
        "human:one",
        request.fingerprint(),
        datetime.now(timezone.utc),
        envelope,
    )

    result = capability.invoke(request, authorization=authorization)

    assert result.outcome is GeoOutcome.SUCCESS
    assert result.effects.provider_requests == 1
    assert result.effects.billable_units is None
    assert result.components[0].subject_refs == ("source-item:one",)
    assert result.continuations == (
        GeoContinuation(
            GeoOperation.NEARBY_PLACES,
            "Nearby-place evidence may refine or challenge the address candidate.",
            True,
        ),
    )


def test_capability_fallback_is_bounded_by_authorized_providers() -> None:
    from mediasense.capabilities.geo import GeoCapability

    failed = _FakeProvider(
        GeoProviderCapabilities(
            "provider-a", (GeoOperation.REVERSE_GEOCODE,), MapDatum.WGS84
        ),
        GeoComponentStatus.FAILED,
    )
    successful = _FakeProvider(
        GeoProviderCapabilities(
            "provider-b", (GeoOperation.REVERSE_GEOCODE,), MapDatum.WGS84
        )
    )
    capability = GeoCapability(
        {"provider-a": failed, "provider-b": successful},
        OrderedGeoRoutingPolicy(("provider-a", "provider-b")),
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579)),),
        "zh-CN",
    )
    envelope = GeoEffectEnvelope(
        ("provider-a",),
        max_logical_queries=1,
        max_provider_requests=1,
        allow_unknown_billable_units=True,
    )
    authorization = GeoAuthorization(
        "human:one",
        request.fingerprint(),
        datetime.now(timezone.utc),
        envelope,
    )

    result = capability.invoke(request, authorization=authorization)

    assert result.outcome is GeoOutcome.FAILED
    assert failed.calls == 1
    assert successful.calls == 0


def test_route_context_is_explicit_and_does_not_leak_between_calls() -> None:
    from mediasense.capabilities.geo import GeoCapability

    first = _FakeProvider(
        GeoProviderCapabilities(
            "provider-a", (GeoOperation.REVERSE_GEOCODE,), MapDatum.WGS84
        )
    )
    second = _FakeProvider(
        GeoProviderCapabilities(
            "provider-b", (GeoOperation.REVERSE_GEOCODE,), MapDatum.WGS84
        )
    )
    capability = GeoCapability(
        {"provider-a": first, "provider-b": second},
        OrderedGeoRoutingPolicy(("provider-a", "provider-b")),
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579)),),
        "zh-CN",
    )
    envelope = capability.proposed_envelope(request)
    authorization = GeoAuthorization(
        "human:one",
        request.fingerprint(),
        datetime.now(timezone.utc),
        envelope,
    )

    preferred_request = GeoRequest(
        request.operation,
        request.subjects,
        request.locale,
        route_context=GeoRouteContext("provider-b", "zh-CN"),
    )
    preferred_authorization = GeoAuthorization(
        "human:one",
        preferred_request.fingerprint(),
        datetime.now(timezone.utc),
        capability.proposed_envelope(preferred_request),
    )
    preferred_result = capability.invoke(
        preferred_request, authorization=preferred_authorization
    )
    default_result = capability.invoke(request, authorization=authorization)

    assert preferred_result.attempts[0].provider == "provider-b"
    assert default_result.attempts[0].provider == "provider-a"
    assert first.calls == 1
    assert second.calls == 1


def test_indeterminate_effect_stops_later_batch_requests() -> None:
    from mediasense.capabilities.geo import GeoCapability

    provider = _FakeProvider(
        GeoProviderCapabilities(
            "provider-a", (GeoOperation.REVERSE_GEOCODE,), MapDatum.WGS84
        ),
        GeoComponentStatus.INDETERMINATE,
    )
    capability = GeoCapability(
        {"provider-a": provider}, OrderedGeoRoutingPolicy(("provider-a",))
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (
            GeoSubject("source-item:one", GeoCoordinate(31.1434, 121.6579)),
            GeoSubject("source-item:two", GeoCoordinate(35.6580, 139.7013)),
        ),
        "zh-CN",
    )
    authorization = GeoAuthorization(
        "human:one",
        request.fingerprint(),
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )

    result = capability.invoke(request, authorization=authorization)

    assert result.outcome is GeoOutcome.INDETERMINATE
    assert [component.status for component in result.components] == [
        GeoComponentStatus.INDETERMINATE,
        GeoComponentStatus.NOT_REQUESTED,
    ]
    assert provider.calls == 1


def test_legacy_geo_imports_share_the_authoritative_coordinate_types() -> None:
    from mediasense.geo import GeoCoordinate as LegacyCoordinate
    from mediasense.geo import MapDatum as LegacyDatum

    assert LegacyCoordinate is GeoCoordinate
    assert LegacyDatum is MapDatum


def test_geo_family_has_no_stage_private_imports() -> None:
    family = Path(__file__).parents[1] / "src" / "mediasense" / "capabilities" / "geo"
    forbidden = ("mediasense.precheck", "mediasense.plan", "mediasense.apply")
    imports: list[str] = []
    for path in family.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imports.append(node.module)

    assert not [name for name in imports if name.startswith(forbidden)]
