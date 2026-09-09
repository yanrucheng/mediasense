from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import hashlib
from pathlib import Path

from jsonschema import Draft202012Validator
from PIL import Image
import pytest

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCandidate,
    GeoCandidateKind,
    GeoCapability,
    GeoComponentResult,
    GeoComponentStatus,
    GeoOperation,
    GeoOperationJournal,
    GeoProviderAttempt,
    GeoProviderCapabilities,
    GeoProviderExecution,
    GeoQueryTool,
    GeoRequest,
    GeoSubject,
    OrderedGeoRoutingPolicy,
)
from mediasense.geo import (
    AMapReverseGeocoder,
    AdaptiveReverseGeocoder,
    GeoCoordinate,
    GeoProviderResult,
    GeoTransientError,
    GoogleMapsReverseGeocoder,
    MapDatum,
)
from mediasense.precheck import (
    AccountingStore,
    BundleCandidateProducer,
    DependencyKind,
    ImageRenditionProducer,
    PrecheckReadTool,
    PrecheckConfirmationContext,
    PrecheckRunTool,
    ReverseGeocodeProducer,
    ReverseGeocodeProfile,
    ResultSealError,
    ResultStore,
    WorkDependency,
    WorkSpec,
    WorkStatus,
    WorkStore,
    upstream_dependency,
)
from mediasense.precheck._result_assembly import _external_effect_boundary


class IdentityConverter:
    def convert(self, coordinate: GeoCoordinate, target: MapDatum) -> GeoCoordinate:
        return GeoCoordinate(coordinate.latitude, coordinate.longitude, target)


@dataclass
class FakeTransport:
    gets: list[tuple[str, dict[str, object], dict[str, str] | None, float]] = field(
        default_factory=list
    )
    posts: list[tuple[str, dict[str, object], dict[str, str] | None, float]] = field(
        default_factory=list
    )
    get_response: dict[str, object] | Exception = field(default_factory=dict)
    post_response: dict[str, object] | Exception = field(default_factory=dict)

    def get_json(self, url, *, params, headers, timeout):
        self.gets.append(
            (url, dict(params), None if headers is None else dict(headers), timeout)
        )
        if isinstance(self.get_response, Exception):
            raise self.get_response
        return self.get_response

    def post_json(self, url, *, payload, headers, timeout):
        self.posts.append(
            (url, dict(payload), None if headers is None else dict(headers), timeout)
        )
        if isinstance(self.post_response, Exception):
            raise self.post_response
        return self.post_response


@dataclass
class FakeGoogle:
    provider_id: str = "google_maps"
    datum: MapDatum = MapDatum.WGS84
    status: str = "success"
    calls: list[GeoCoordinate] = field(default_factory=list)

    def lookup(self, coordinate: GeoCoordinate, *, language: str) -> GeoProviderResult:
        self.calls.append(coordinate)
        return GeoProviderResult(
            status=self.status,
            provider=self.provider_id,
            language=language,
            input_coordinate=coordinate,
            provider_coordinate=coordinate,
            location=(
                None
                if self.status == "no_result"
                else {
                    "formatted_address": "Tokyo, Japan",
                    "components": {"country": "Japan", "country_code": "JP"},
                }
            ),
            pois=(
                ()
                if self.status == "no_result"
                else (
                    {
                        "name": "Nearby fixture place",
                        "address": "Fixture address",
                        "latitude": coordinate.latitude,
                        "longitude": coordinate.longitude,
                    },
                )
            ),
            request_count=2,
        )


@dataclass
class FakeCountryProvider:
    provider_id: str
    country: str
    country_code: str
    datum: MapDatum
    calls: list[tuple[GeoCoordinate, str]] = field(default_factory=list)

    def lookup(self, coordinate: GeoCoordinate, *, language: str) -> GeoProviderResult:
        self.calls.append((coordinate, language))
        return GeoProviderResult(
            status="success",
            provider=self.provider_id,
            language=language,
            input_coordinate=coordinate,
            provider_coordinate=coordinate,
            location={
                "formatted_address": self.country,
                "components": {
                    "country": self.country,
                    "country_code": self.country_code,
                },
            },
            pois=(
                {
                    "name": f"{self.country} place",
                    "address": self.country,
                    "latitude": coordinate.latitude,
                    "longitude": coordinate.longitude,
                },
            ),
            request_count=1,
        )


class FakeGeoProviderAdapter:
    def __init__(self, provider: FakeGoogle | FakeCountryProvider) -> None:
        self.provider = provider
        self.capabilities = GeoProviderCapabilities(
            provider.provider_id,
            (
                GeoOperation.RESOLVE_PLACE,
                GeoOperation.REVERSE_GEOCODE,
                GeoOperation.NEARBY_PLACES,
            ),
            provider.datum,
            max_requests_per_operation=2,
            operation_request_ceilings=((GeoOperation.RESOLVE_PLACE, 2),),
        )

    def execute(
        self,
        operation: GeoOperation,
        coordinate: GeoCoordinate,
        *,
        locale: str,
        radius_meters: float | None = None,
        max_places: int | None = None,
        deadline: float | None = None,
        cancelled=None,
    ) -> GeoProviderExecution:
        del radius_meters, max_places
        result = self.provider.lookup(coordinate, language=locale)
        address_candidates = ()
        if result.location is not None:
            address_candidates = (
                GeoCandidate(
                    GeoCandidateKind.ADDRESS,
                    str(result.location["formatted_address"]),
                    formatted_address=str(result.location["formatted_address"]),
                    coordinate=coordinate,
                    components=tuple(
                        sorted(
                            (str(key), str(value))
                            for key, value in result.location["components"].items()
                        )
                    ),
                    provider_ref=result.provider,
                ),
            )
        status = (
            GeoComponentStatus.SUCCESS
            if address_candidates
            else GeoComponentStatus.NO_RESULT
            if result.status == "no_result"
            else GeoComponentStatus.FAILED
        )
        address = GeoComponentResult(
            GeoOperation.REVERSE_GEOCODE,
            status,
            (),
            coordinate,
            address_candidates,
        )
        reverse_attempt = GeoProviderAttempt(
            result.provider,
            GeoOperation.REVERSE_GEOCODE,
            status,
            coordinate,
            result.provider_coordinate,
            1,
            None,
        )
        if operation is not GeoOperation.RESOLVE_PLACE:
            return GeoProviderExecution(address, reverse_attempt)
        places = tuple(
            GeoCandidate(
                GeoCandidateKind.PLACE,
                str(item["name"]),
                formatted_address=str(item.get("address", "")),
                coordinate=coordinate,
                provider_ref=result.provider,
            )
            for item in result.pois
        )
        nearby_status = (
            GeoComponentStatus.SUCCESS if places else GeoComponentStatus.NO_RESULT
        )
        nearby = GeoComponentResult(
            GeoOperation.NEARBY_PLACES,
            nearby_status,
            (),
            coordinate,
            places,
        )
        nearby_attempts = (
            (
                GeoProviderAttempt(
                    result.provider,
                    GeoOperation.NEARBY_PLACES,
                    nearby_status,
                    coordinate,
                    result.provider_coordinate,
                    1,
                    None,
                ),
            )
            if result.request_count > 1
            else ()
        )
        return GeoProviderExecution(
            address,
            reverse_attempt,
            (nearby,),
            nearby_attempts,
        )


def _geo_tool(
    tmp_path: Path, *providers: FakeGoogle | FakeCountryProvider
) -> GeoQueryTool:
    adapters = {
        provider.provider_id: FakeGeoProviderAdapter(provider) for provider in providers
    }
    return GeoQueryTool(
        GeoCapability(adapters, OrderedGeoRoutingPolicy(tuple(adapters))),
        GeoOperationJournal(tmp_path / "geo-journal.sqlite3"),
    )


def _closed_run(
    tmp_path: Path, database: Path, accounting: AccountingStore, names: tuple[str, ...]
) -> str:
    source = tmp_path / "source"
    if not source.exists():
        source.mkdir()
        for name in names:
            Image.new("RGB", (40, 30), "blue").save(source / name)
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


def _coordinate_work(
    database: Path,
    run_id: str,
    relative_path: str,
    *,
    latitude: float,
    longitude: float,
    capture_time: str | None = None,
):
    work = WorkStore(database)
    spec = WorkSpec(
        capability="source-metadata",
        producer_identity="test-metadata-v1",
        dependencies=(
            WorkDependency(
                DependencyKind.PARAMETER,
                "subject_relative_path",
                relative_path,
            ),
            WorkDependency(
                DependencyKind.PARAMETER,
                "fixture_coordinate",
                f"{latitude},{longitude}",
            ),
        ),
    )
    record = work.ensure_work(run_id, spec)
    if record.status is WorkStatus.SUCCEEDED:
        return record
    lease = work.claim_ready_work(
        run_id,
        "test-metadata",
        lease_duration=timedelta(minutes=1),
        work_id=record.work_id,
    )[0]
    observations = [
        {
            "name": "gps_coordinates",
            "status": "available",
            "value": {
                "datum": "WGS84",
                "latitude": latitude,
                "longitude": longitude,
            },
        }
    ]
    if capture_time is not None:
        observations.append(
            {
                "name": "capture_time",
                "status": "available",
                "value": capture_time,
            }
        )
    return work.succeed_work(
        lease,
        {
            "observations": observations,
            "subject": {"relative_path": relative_path},
        },
    )


def _public_run(tool: PrecheckRunTool, request_id: str) -> str:
    response = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": request_id,
        }
    )
    return str(response["run_ref"])


def _legacy_geocode_work(
    database: Path,
    run_id: str,
    coordinate: GeoCoordinate,
    *,
    previous=None,
    provider_request_count: int | None = 2,
):
    dependencies = [
        WorkDependency(
            DependencyKind.PARAMETER,
            "normalized_coordinate",
            json.dumps(
                coordinate.value(),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        ),
        WorkDependency(
            DependencyKind.PARAMETER,
            "reverse_geocode_profile",
            json.dumps(
                {
                    "provider_profile": "amap-google-address-poi-v1",
                    "refresh_token": "reuse-until-explicit-refresh",
                    "routing_policy": "c90-continuity-bounded-v1",
                },
                separators=(",", ":"),
                sort_keys=True,
            ),
        ),
    ]
    if previous is not None:
        dependencies.append(upstream_dependency(previous))
    store = WorkStore(database)
    record = store.ensure_work(
        run_id,
        WorkSpec(
            "reverse-geocode-observation",
            "builtin-adaptive-reverse-geocode-v1",
            tuple(dependencies),
        ),
    )
    lease = store.claim_ready_work(
        run_id,
        "legacy-test",
        lease_duration=timedelta(minutes=1),
        work_id=record.work_id,
    )[0]
    value = {
        "input_coordinate": coordinate.value(),
        "provider_coordinate": coordinate.value(),
        "provider": "google_maps",
        "language": "zh-CN",
        "location": {"formatted_address": "legacy", "components": {}},
        "pois": [],
        "observed_at": "2026-05-04T12:00:00+00:00",
        "logical_query_count": 1,
        "provider_request_count": provider_request_count,
        "attempts": [],
    }
    return store.succeed_work(
        lease,
        {
            "authorization": {
                "confirmed_at": "2026-05-04T12:00:00+00:00",
                "confirmed_content_identity": "sha256:" + "a" * 64,
                "confirmed_logical_queries": 2,
                "decision": "proceed",
                "pending_fingerprint": "sha256:" + "a" * 64,
                "principal_ref": "human:legacy",
                "run_ref": "precheck-run:legacy",
            },
            "observations": [
                {
                    "name": "reverse_geocode_candidate",
                    "status": "available",
                    "value": {
                        "address": {
                            "formatted_address": "legacy",
                            "components": {},
                        },
                        "pois": [],
                    },
                    "provenance": {
                        "method": "adaptive_reverse_geocode_v1",
                        "provider": "google_maps",
                        "language": "zh-CN",
                        "observed_at": "2026-05-04T12:00:00+00:00",
                        "input_datum": coordinate.datum.value,
                        "provider_datum": coordinate.datum.value,
                        "logical_query_count": 1,
                        "provider_request_count": 1,
                    },
                }
            ],
            "producer": {"identity": "builtin-adaptive-reverse-geocode-v1"},
            "query": coordinate.value(),
            "result": value,
        },
    )


def _authorize(tool: PrecheckRunTool, run_ref: str) -> dict[str, object]:
    status = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    identity = status["confirmation"]["content_identity"]
    return tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": run_ref,
            "decision": "proceed",
        },
        confirmation=PrecheckConfirmationContext(
            principal_ref="human:test",
            confirmed_content_identity=identity,
            confirmed_at=datetime.now(timezone.utc),
        ),
    )


def test_amap_preserves_datum_conversion_and_normalizes_pois() -> None:
    transport = FakeTransport(
        get_response={
            "status": "1",
            "regeocode": {
                "formatted_address": "北京市东城区",
                "addressComponent": {"country": "中国", "city": "北京市"},
                "pois": [
                    {
                        "name": "故宫",
                        "location": "116.397000,39.916000",
                        "distance": "50",
                        "type": "风景名胜;公园广场",
                        "address": "景山前街",
                        "poiweight": "0.9",
                    }
                ],
            },
        }
    )
    provider = AMapReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )

    result = provider.lookup(
        GeoCoordinate(39.916, 116.397, MapDatum.WGS84), language="en"
    )

    assert result.status == "success"
    assert result.language == "zh"
    assert result.provider_coordinate.datum is MapDatum.GCJ02
    assert result.pois[0]["class"] == "风景名胜"
    assert transport.gets[0][1]["location"] == "116.397000,39.916000"
    assert "secret" not in str(result)


def test_google_preserves_reverse_plus_nearby_and_partial_failure() -> None:
    transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Shibuya, Tokyo, Japan",
                    "address_components": [
                        {
                            "long_name": "Japan",
                            "short_name": "JP",
                            "types": ["country"],
                        },
                        {"long_name": "Tokyo", "types": ["locality"]},
                    ],
                }
            ],
        },
        post_response={
            "places": [
                {
                    "displayName": {"text": "Shibuya Station"},
                    "formattedAddress": "Shibuya",
                    "primaryTypeDisplayName": {"text": "Train station"},
                    "location": {"latitude": 35.6581, "longitude": 139.7014},
                    "types": ["train_station"],
                }
            ]
        },
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )

    result = provider.lookup(
        GeoCoordinate(35.6580, 139.7013, MapDatum.WGS84), language="ja"
    )

    assert result.status == "success"
    assert result.request_count == 2
    assert result.location["components"]["country_code"] == "JP"
    assert result.pois[0]["class"] == "train_station"
    assert transport.posts[0][1]["maxResultCount"] == 10

    transport.post_response = GeoTransientError("nearby timeout")
    partial = provider.lookup(
        GeoCoordinate(35.6580, 139.7013, MapDatum.WGS84), language="ja"
    )
    assert partial.status == "partial"
    assert partial.location is not None
    assert partial.error_message == "nearby timeout"


def test_amap_capability_adapter_requests_only_the_selected_operation() -> None:
    transport = FakeTransport(
        get_response={
            "status": "1",
            "regeocode": {
                "formatted_address": "北京市东城区",
                "addressComponent": {"country": "中国", "city": "北京市"},
                "pois": [
                    {
                        "name": "故宫",
                        "location": "116.397000,39.916000",
                        "distance": "50",
                        "type": "风景名胜;公园广场",
                        "address": "景山前街",
                    }
                ],
            },
        }
    )
    provider = AMapReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    coordinate = GeoCoordinate(39.916, 116.397, MapDatum.WGS84)

    address = provider.execute(GeoOperation.REVERSE_GEOCODE, coordinate, locale="en")
    nearby = provider.execute(
        GeoOperation.NEARBY_PLACES,
        coordinate,
        locale="en",
        radius_meters=100,
        max_places=1,
    )

    assert address.component.status is GeoComponentStatus.SUCCESS
    assert address.component.candidates[0].kind == "address"
    assert nearby.component.status is GeoComponentStatus.SUCCESS
    assert nearby.component.candidates[0].name == "故宫"
    assert transport.gets[0][1]["extensions"] == "base"
    assert transport.gets[1][1]["extensions"] == "all"
    assert transport.gets[1][1]["radius"] == 100


def test_amap_expanded_resolve_returns_address_and_poi_with_one_request() -> None:
    transport = FakeTransport(
        get_response={
            "status": "1",
            "regeocode": {
                "formatted_address": "北京市东城区",
                "addressComponent": {"country": "中国", "city": "北京市"},
                "pois": [
                    {
                        "name": "故宫",
                        "location": "116.397000,39.916000",
                        "distance": "50",
                        "type": "风景名胜;公园广场",
                        "address": "景山前街",
                    }
                ],
            },
        }
    )
    provider = AMapReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )

    result = provider.execute(
        GeoOperation.RESOLVE_PLACE,
        GeoCoordinate(39.916, 116.397, MapDatum.WGS84),
        locale="zh",
        radius_meters=500,
        max_places=30,
    )

    assert [component.operation for component in result.components] == [
        GeoOperation.REVERSE_GEOCODE,
        GeoOperation.NEARBY_PLACES,
    ]
    assert all(
        component.status is GeoComponentStatus.SUCCESS
        for component in result.components
    )
    assert sum(attempt.provider_requests for attempt in result.attempts) == 1
    assert result.attempts[0].operation is GeoOperation.RESOLVE_PLACE
    assert len(transport.gets) == 1
    assert transport.gets[0][1]["extensions"] == "all"
    assert transport.gets[0][1]["radius"] == 200


def test_amap_expanded_resolve_failure_records_the_combined_operation() -> None:
    transport = FakeTransport(
        get_response=GeoTransientError("AMap timeout", request_count=1)
    )
    provider = AMapReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )

    result = provider.execute(
        GeoOperation.RESOLVE_PLACE,
        GeoCoordinate(39.916, 116.397, MapDatum.WGS84),
        locale="zh",
        radius_meters=500,
        max_places=30,
    )

    assert [component.operation for component in result.components] == [
        GeoOperation.REVERSE_GEOCODE,
        GeoOperation.NEARBY_PLACES,
    ]
    assert all(
        component.status is GeoComponentStatus.INDETERMINATE
        for component in result.components
    )
    assert len(result.attempts) == 1
    assert result.attempts[0].operation is GeoOperation.RESOLVE_PLACE
    assert result.attempts[0].provider_requests == 1
    assert len(transport.gets) == 1


def test_google_capability_adapter_does_not_bundle_unrequested_work() -> None:
    transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Shibuya, Tokyo, Japan",
                    "address_components": [
                        {
                            "long_name": "Japan",
                            "short_name": "JP",
                            "types": ["country"],
                        }
                    ],
                }
            ],
        },
        post_response={
            "places": [
                {
                    "displayName": {"text": "Shibuya Station"},
                    "formattedAddress": "Shibuya",
                    "location": {"latitude": 35.6581, "longitude": 139.7014},
                    "types": ["train_station"],
                }
            ]
        },
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    coordinate = GeoCoordinate(35.6580, 139.7013, MapDatum.WGS84)

    address = provider.execute(GeoOperation.REVERSE_GEOCODE, coordinate, locale="ja")
    assert address.component.status is GeoComponentStatus.SUCCESS
    assert len(transport.gets) == 1
    assert transport.posts == []

    nearby = provider.execute(
        GeoOperation.NEARBY_PLACES,
        coordinate,
        locale="ja",
        radius_meters=250,
        max_places=1,
    )
    assert nearby.component.status is GeoComponentStatus.SUCCESS
    assert nearby.component.candidates[0].name == "Shibuya Station"
    assert len(transport.gets) == 1
    assert len(transport.posts) == 1
    assert transport.posts[0][1]["locationRestriction"]["circle"]["radius"] == 250


def test_google_expanded_resolve_returns_address_and_poi_with_two_requests() -> None:
    transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Shibuya, Tokyo, Japan",
                    "address_components": [],
                }
            ],
        },
        post_response={
            "places": [
                {
                    "displayName": {"text": "Shibuya Station"},
                    "formattedAddress": "Shibuya",
                    "location": {"latitude": 35.6581, "longitude": 139.7014},
                    "types": ["train_station"],
                }
            ]
        },
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )

    result = provider.execute(
        GeoOperation.RESOLVE_PLACE,
        GeoCoordinate(35.6580, 139.7013, MapDatum.WGS84),
        locale="ja",
        radius_meters=500,
        max_places=30,
    )

    assert [component.operation for component in result.components] == [
        GeoOperation.REVERSE_GEOCODE,
        GeoOperation.NEARBY_PLACES,
    ]
    assert all(
        component.status is GeoComponentStatus.SUCCESS
        for component in result.components
    )
    assert sum(attempt.provider_requests for attempt in result.attempts) == 2
    assert len(transport.gets) == 1
    assert len(transport.posts) == 1
    assert transport.posts[0][1]["maxResultCount"] == 10


def test_expanded_resolve_discloses_amap_plus_google_three_request_ceiling() -> None:
    amap = AMapReverseGeocoder(
        "amap-secret",
        transport=FakeTransport(),
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    google = GoogleMapsReverseGeocoder(
        "google-secret",
        transport=FakeTransport(),
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    capability = GeoCapability(
        {"amap": amap, "google_maps": google},
        OrderedGeoRoutingPolicy(("amap", "google_maps")),
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(22.3, 114.1)),),
        "zh",
        radius_meters=500,
        max_places=30,
    )

    assert capability.proposed_envelope(request).max_provider_requests == 9


def test_expanded_resolve_fallback_cannot_exceed_three_request_ceiling() -> None:
    amap_transport = FakeTransport(
        get_response={"status": "0", "infocode": "10001", "info": "denied"}
    )
    google_transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Hong Kong",
                    "address_components": [],
                }
            ],
        },
        post_response={
            "places": [
                {
                    "displayName": {"text": "Victoria Harbour"},
                    "formattedAddress": "Hong Kong",
                    "location": {"latitude": 22.293, "longitude": 114.169},
                    "types": ["tourist_attraction"],
                }
            ]
        },
    )
    amap = AMapReverseGeocoder(
        "amap-secret",
        transport=amap_transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    google = GoogleMapsReverseGeocoder(
        "google-secret",
        transport=google_transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    capability = GeoCapability(
        {"amap": amap, "google_maps": google},
        OrderedGeoRoutingPolicy(("amap", "google_maps")),
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(22.3, 114.1)),),
        "zh",
        radius_meters=500,
        max_places=30,
    )
    authorization = GeoAuthorization(
        "human:test",
        capability.fingerprint(request),
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )

    result = capability.invoke(request, authorization=authorization)

    assert result.outcome.value == "success"
    assert result.effects.provider_requests == 3
    assert len(amap_transport.gets) == 1
    assert len(google_transport.gets) == 1
    assert len(google_transport.posts) == 1


def test_google_expanded_resolve_preserves_address_when_poi_is_indeterminate() -> None:
    transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Shibuya, Tokyo, Japan",
                    "address_components": [],
                }
            ],
        },
        post_response=GeoTransientError("nearby timeout", request_count=1),
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )

    result = provider.execute(
        GeoOperation.RESOLVE_PLACE,
        GeoCoordinate(35.6580, 139.7013, MapDatum.WGS84),
        locale="ja",
        radius_meters=500,
        max_places=30,
    )

    assert [component.status for component in result.components] == [
        GeoComponentStatus.SUCCESS,
        GeoComponentStatus.INDETERMINATE,
    ]
    assert sum(attempt.provider_requests for attempt in result.attempts) == 2


def test_expanded_resolve_journal_does_not_replay_indeterminate_poi_effect(
    tmp_path: Path,
) -> None:
    transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Shibuya, Tokyo, Japan",
                    "address_components": [],
                }
            ],
        },
        post_response=GeoTransientError("nearby timeout", request_count=1),
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    capability = GeoCapability(
        {provider.provider_id: provider},
        OrderedGeoRoutingPolicy((provider.provider_id,)),
    )
    tool = GeoQueryTool(
        capability,
        GeoOperationJournal(tmp_path / "geo-journal.sqlite3"),
    )
    value = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source-item:one", GeoCoordinate(35.658, 139.7013)),),
        "ja",
        radius_meters=500.0,
        max_places=30,
    )
    request = {"request_id": "request:indeterminate-place", **value.value()}
    authorization = GeoAuthorization(
        "human:test",
        capability.fingerprint(value),
        datetime.now(timezone.utc),
        capability.proposed_envelope(value),
    )

    first = tool.handle(request, authorization=authorization)
    replay = tool.handle(request, authorization=authorization)

    assert first == replay
    assert first["outcome"] == "indeterminate"
    assert [component["status"] for component in first["components"]] == [
        "success",
        "indeterminate",
    ]
    assert first["effects"]["provider_requests"] == 2
    assert len(transport.gets) == 1
    assert len(transport.posts) == 1


def test_capability_adapters_normalize_provider_failures_without_credentials() -> None:
    coordinate = GeoCoordinate(39.916, 116.397, MapDatum.WGS84)
    amap = AMapReverseGeocoder(
        "amap-secret",
        transport=FakeTransport(
            get_response={
                "status": "0",
                "infocode": "10001",
                "info": "invalid key",
            }
        ),
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    amap_result = amap.execute(GeoOperation.REVERSE_GEOCODE, coordinate, locale="zh-CN")

    google = GoogleMapsReverseGeocoder(
        "google-secret",
        transport=FakeTransport(
            get_response={"status": "REQUEST_DENIED", "error_message": "denied"}
        ),
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    google_result = google.execute(
        GeoOperation.REVERSE_GEOCODE, coordinate, locale="en"
    )

    assert amap_result.component.status is GeoComponentStatus.FAILED
    assert amap_result.attempt.provider_requests == 1
    assert google_result.component.status is GeoComponentStatus.FAILED
    assert google_result.attempt.provider_requests == 1
    assert "amap-secret" not in repr(amap_result)
    assert "google-secret" not in repr(google_result)


def test_capability_adapter_preserves_indeterminate_transmitted_request() -> None:
    transport = FakeTransport(
        post_response=GeoTransientError("nearby timeout", request_count=1)
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )

    result = provider.execute(
        GeoOperation.NEARBY_PLACES,
        GeoCoordinate(35.6580, 139.7013),
        locale="ja",
        radius_meters=250,
        max_places=5,
    )

    assert result.component.status is GeoComponentStatus.INDETERMINATE
    assert result.attempt.provider_requests == 1
    assert result.attempt.billable_units is None


def test_geo_profile_has_no_optional_activation_switch() -> None:
    assert "enabled" not in ReverseGeocodeProfile.__dataclass_fields__


def test_complete_place_bounds_participate_in_precheck_work_identity(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=35.658, longitude=139.7013
    )
    producer = ReverseGeocodeProducer(database, PrecheckRunTool(database))

    first = producer.freeze(run_id, [metadata.work_id])
    changed = producer.freeze(
        run_id,
        [metadata.work_id],
        profile=ReverseGeocodeProfile(max_places=20),
    )

    assert first.work[0].work_id != changed.work[0].work_id
    first_dependencies = {
        dependency.key: dependency.value
        for dependency in first.work[0].spec.dependencies
        if dependency.kind is DependencyKind.PARAMETER
    }
    assert first_dependencies["operation"] == "resolve_place"
    assert (
        '"nearby_radius_meters":500.0' in first_dependencies["reverse_geocode_profile"]
    )
    assert '"max_places":30' in first_dependencies["reverse_geocode_profile"]


def test_batch_pauses_before_exact_deduplicated_queries(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    first = _coordinate_work(
        database, run_id, "a.jpg", latitude=35.658, longitude=139.7013
    )
    second = _coordinate_work(
        database, run_id, "b.jpg", latitude=35.658, longitude=139.7013
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:geocode")
    provider = FakeGoogle()
    producer = ReverseGeocodeProducer(
        database,
        run_tool,
        _geo_tool(tmp_path, provider),
    )
    profile = ReverseGeocodeProfile(provider_profile="mock-google-v1")

    pending = producer.produce(
        public_run_ref,
        run_id,
        [first.work_id, second.work_id],
        profile=profile,
    )

    assert pending.status == "confirmation_required"
    assert pending.batch.logical_query_count == 1
    assert pending.batch.pending_query_count == 1
    assert provider.calls == []
    status = run_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": public_run_ref,
        }
    )
    assert status["confirmation"]["disclosure"]["pending_logical_queries"] == 1
    assert status["confirmation"]["page"]["total"] == 1
    disclosure = status["confirmation"]["disclosure"]
    assert disclosure["source_item_outcomes"] == 2
    assert len(disclosure["coordinates"]) == 1
    assert disclosure["pending_logical_queries"] == 1
    assert disclosure["retry_policy"]["max_attempts"] == 3
    assert disclosure["operation"] == "resolve_place"
    assert disclosure["nearby_radius_meters"] == 500
    assert disclosure["max_places"] == 30
    assert disclosure["max_provider_requests"] == 6

    _authorize(run_tool, public_run_ref)
    completed = producer.produce(
        public_run_ref,
        run_id,
        [first.work_id, second.work_id],
        profile=profile,
    )
    assert completed.status == "completed"
    assert completed.actual_provider_requests == 2
    assert len(provider.calls) == 1
    assert len(set(completed.work_by_source().values())) == 1
    components = {item["name"]: item for item in completed.outcomes[0].observations}
    assert (
        components["nearby_place_candidates"]["value"][0]["name"]
        == "Nearby fixture place"
    )
    assert (
        components["address_candidate"]["status"]
        == components["nearby_place_candidates"]["status"]
        == "available"
    )

    reused = producer.produce(
        public_run_ref,
        run_id,
        [first.work_id, second.work_id],
        profile=profile,
    )
    assert reused.status == "completed"
    assert reused.actual_provider_requests == 0
    assert all(outcome.reused for outcome in reused.outcomes)
    assert len(provider.calls) == 1

    second_run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    second_metadata = [
        _coordinate_work(
            database,
            second_run_id,
            name,
            latitude=35.658,
            longitude=139.7013,
        )
        for name in ("a.jpg", "b.jpg")
    ]
    run_tool.run(
        {
            "action": "cancel",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": public_run_ref,
        }
    )
    second_public_ref = _public_run(run_tool, "request:geocode-reuse")
    cross_run = ReverseGeocodeProducer(database, run_tool).produce(
        second_public_ref,
        second_run_id,
        [item.work_id for item in second_metadata],
        profile=profile,
    )
    assert cross_run.status == "completed"
    assert cross_run.actual_provider_requests == 0
    assert all(outcome.reused for outcome in cross_run.outcomes)
    assert (
        run_tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "status",
                "run_ref": second_public_ref,
            }
        )["state"]
        == "running"
    )


def test_precheck_amap_acquires_address_and_poi_with_one_provider_request(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=39.916, longitude=116.397
    )
    transport = FakeTransport(
        get_response={
            "status": "1",
            "regeocode": {
                "formatted_address": "北京市东城区",
                "addressComponent": {"country": "中国", "city": "北京市"},
                "pois": [
                    {
                        "name": "故宫",
                        "location": "116.397000,39.916000",
                        "distance": "50",
                        "type": "风景名胜;公园广场",
                        "address": "景山前街",
                    }
                ],
            },
        }
    )
    provider = AMapReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    geo_tool = GeoQueryTool(
        GeoCapability(
            {provider.provider_id: provider},
            OrderedGeoRoutingPolicy((provider.provider_id,)),
        ),
        GeoOperationJournal(tmp_path / "geo-journal.sqlite3"),
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:amap-place")
    producer = ReverseGeocodeProducer(database, run_tool, geo_tool)

    pending = producer.produce(public_run_ref, run_id, [metadata.work_id])
    assert pending.status == "confirmation_required"
    status = run_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": public_run_ref,
        }
    )
    assert status["confirmation"]["disclosure"]["max_provider_requests"] == 3
    _authorize(run_tool, public_run_ref)
    completed = producer.produce(public_run_ref, run_id, [metadata.work_id])

    assert completed.actual_provider_requests == 1
    assert len(transport.gets) == 1
    components = {item["name"]: item for item in completed.outcomes[0].observations}
    assert (
        components["address_candidate"]["value"]["formatted_address"] == "北京市东城区"
    )
    assert components["nearby_place_candidates"]["value"][0]["name"] == "故宫"


def test_precheck_preserves_partial_when_nearby_lookup_fails(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=35.658, longitude=139.7013
    )
    transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Shibuya, Tokyo, Japan",
                    "address_components": [],
                }
            ],
        },
        post_response={"error": {"message": "Places quota exceeded"}},
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    geo_tool = GeoQueryTool(
        GeoCapability(
            {provider.provider_id: provider},
            OrderedGeoRoutingPolicy((provider.provider_id,)),
        ),
        GeoOperationJournal(tmp_path / "geo-journal.sqlite3"),
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:partial-place")
    producer = ReverseGeocodeProducer(database, run_tool, geo_tool)

    pending = producer.produce(public_run_ref, run_id, [metadata.work_id])
    assert pending.status == "confirmation_required"
    _authorize(run_tool, public_run_ref)
    completed = producer.produce(public_run_ref, run_id, [metadata.work_id])

    assert completed.status == "completed"
    assert completed.actual_provider_requests == 2
    components = {item["name"]: item for item in completed.outcomes[0].observations}
    assert components["address_candidate"]["status"] == "available"
    assert components["address_candidate"]["value"]["formatted_address"] == (
        "Shibuya, Tokyo, Japan"
    )
    assert components["nearby_place_candidates"]["status"] == "failed"
    assert "value" not in components["nearby_place_candidates"]
    assert any(
        q["code"] == "nearby_places:google_maps_error"
        for q in components["nearby_place_candidates"]["qualifications"]
    )
    assert completed.outcomes[0].work.output["result"]["status"] == "partial"


def test_precheck_preserves_cross_provider_provenance_in_result_audit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=22.293, longitude=114.169
    )
    google_transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Victoria Harbour, Hong Kong",
                    "address_components": [],
                }
            ],
        },
        post_response={"error": {"message": "Places quota exceeded"}},
    )
    amap_transport = FakeTransport(
        get_response={
            "status": "1",
            "regeocode": {
                "formatted_address": "香港维多利亚港",
                "addressComponent": {"country": "中国", "city": "香港"},
                "pois": [
                    {
                        "name": "维多利亚港",
                        "location": "114.169000,22.293000",
                        "distance": "50",
                        "type": "风景名胜",
                        "address": "香港",
                    }
                ],
            },
        }
    )
    google = GoogleMapsReverseGeocoder(
        "google-secret",
        transport=google_transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    amap = AMapReverseGeocoder(
        "amap-secret",
        transport=amap_transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    geo_tool = GeoQueryTool(
        GeoCapability(
            {google.provider_id: google, amap.provider_id: amap},
            OrderedGeoRoutingPolicy((google.provider_id, amap.provider_id)),
        ),
        GeoOperationJournal(tmp_path / "geo-journal.sqlite3"),
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:cross-provider-place")
    producer = ReverseGeocodeProducer(database, run_tool, geo_tool)

    producer.produce(public_run_ref, run_id, [metadata.work_id])
    _authorize(run_tool, public_run_ref)
    completed = producer.produce(public_run_ref, run_id, [metadata.work_id])

    assert completed.actual_provider_requests == 3
    work_result = completed.outcomes[0].work.output["result"]
    assert work_result["provider"] == "google_maps"
    assert work_result["provider_coordinate"]["datum"] == "WGS84"
    assert work_result["providers"] == ["amap", "google_maps"]
    assert {attempt["provider"] for attempt in work_result["attempts"]} == {
        "amap",
        "google_maps",
    }
    components = {item["name"]: item for item in completed.outcomes[0].observations}
    assert components["address_candidate"]["value"]["formatted_address"] == (
        "Victoria Harbour, Hong Kong"
    )
    assert components["nearby_place_candidates"]["value"][0]["name"] == "维多利亚港"

    rendition = ImageRenditionProducer(database).produce(run_id, Path("a.jpg"))
    result_store = ResultStore(database)
    sealed = result_store.seal(
        result_store.build_minimal(
            run_id,
            [rendition.work.work_id],
            metadata_work_ids=[metadata.work_id],
            reverse_geocode_work_by_source=completed.work_by_source(),
        )
    )
    reviewed = PrecheckReadTool(database).read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
            "include": ["execution_boundary"],
        }
    )
    assert reviewed["execution_boundary"]["providers_attempted"] == [
        "amap",
        "google_maps",
    ]

    from mediasense.precheck import read as read_module

    request = {
        "dataset_ref": "dataset:dataset-a",
        "result_ref": sealed.result_ref,
        "action": "review",
        "include": ["execution_boundary"],
    }
    monkeypatch.setattr(
        read_module, "_MAX_RESPONSE_BYTES", read_module._encoded_size(reviewed) - 1
    )
    limited = PrecheckReadTool(database).read(request)
    assert "error" not in limited
    assert limited["items"]
    assert 0 < len(limited["execution_boundary"]["attempts"]) < 3
    assert limited["execution_boundary"]["page"]["total"] == 3
    cursor = limited["execution_boundary"]["page"]["next_cursor"]
    assert cursor
    assert read_module._encoded_size(limited) <= read_module._MAX_RESPONSE_BYTES
    crossed = PrecheckReadTool(database).read({**request, "page": {"cursor": cursor}})
    assert crossed["error"]["code"] == "invalid_cursor"


def test_result_audit_accepts_legacy_single_provider_work() -> None:
    boundary = _external_effect_boundary(
        [
            {
                "work_id": "work:legacy-geocode",
                "output_json": json.dumps(
                    {
                        "result": {
                            "provider": "google_maps",
                            "provider_request_count": 1,
                        },
                        "authorization": {
                            "decision": "proceed",
                            "run_ref": "precheck-run:legacy",
                            "pending_fingerprint": "sha256:legacy",
                        },
                    }
                ),
            }
        ],
        {},
        "run:synthetic",
        set(),
    )

    assert boundary is not None
    assert boundary["providers"] == ["google_maps"]


def test_precheck_distinguishes_empty_poi_result_from_unexecuted_lookup(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=35.658, longitude=139.7013
    )
    transport = FakeTransport(
        get_response={
            "status": "OK",
            "results": [
                {
                    "formatted_address": "Shibuya, Tokyo, Japan",
                    "address_components": [],
                }
            ],
        },
        post_response={},
    )
    provider = GoogleMapsReverseGeocoder(
        "secret",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    geo_tool = GeoQueryTool(
        GeoCapability(
            {provider.provider_id: provider},
            OrderedGeoRoutingPolicy((provider.provider_id,)),
        ),
        GeoOperationJournal(tmp_path / "geo-journal.sqlite3"),
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:no-nearby-place")
    producer = ReverseGeocodeProducer(database, run_tool, geo_tool)

    producer.produce(public_run_ref, run_id, [metadata.work_id])
    _authorize(run_tool, public_run_ref)
    completed = producer.produce(public_run_ref, run_id, [metadata.work_id])
    components = {item["name"]: item for item in completed.outcomes[0].observations}

    assert components["nearby_place_candidates"]["status"] == "missing"
    assert "value" not in components["nearby_place_candidates"]
    assert completed.actual_provider_requests == 2


def test_bundle_is_a_candidate_scope_and_movement_splits_geo_units(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg", "c.jpg"))
    metadata = [
        _coordinate_work(
            database,
            run_id,
            name,
            latitude=latitude,
            longitude=114.1694,
            capture_time=capture_time,
        )
        for name, latitude, capture_time in (
            ("a.jpg", 22.319300, "2026-05-04T12:00:00+00:00"),
            ("b.jpg", 22.319330, "2026-05-04T12:00:05+00:00"),
            ("c.jpg", 22.320300, "2026-05-04T12:00:10+00:00"),
        )
    ]
    bundles = tuple(
        BundleCandidateProducer(database).produce(
            run_id, [record.work_id for record in metadata]
        )
    )
    run_tool = PrecheckRunTool(database)
    provider = FakeGoogle()
    producer = ReverseGeocodeProducer(database, run_tool, _geo_tool(tmp_path, provider))
    batch = producer.freeze(
        run_id,
        [record.work_id for record in metadata],
        bundle_work_ids=[outcome.work.work_id for outcome in bundles],
    )

    assert len(bundles) == 1
    assert batch.logical_query_count == 2
    assert batch.queries[0].source_paths == (Path("a.jpg"), Path("b.jpg"))
    assert batch.queries[1].source_paths == (Path("c.jpg"),)

    public_run_ref = _public_run(run_tool, "request:bundle-geo")
    pending = producer.produce(
        public_run_ref,
        run_id,
        [record.work_id for record in metadata],
        bundle_work_ids=[outcome.work.work_id for outcome in bundles],
    )
    assert pending.status == "confirmation_required"
    assert pending.batch.pending_query_count == 2
    _authorize(run_tool, public_run_ref)
    completed = producer.produce(
        public_run_ref,
        run_id,
        [record.work_id for record in metadata],
        bundle_work_ids=[outcome.work.work_id for outcome in bundles],
    )
    mapped = completed.work_by_source()
    assert completed.status == "completed"
    assert len(provider.calls) == 2
    assert set(mapped) == {Path("a.jpg"), Path("b.jpg"), Path("c.jpg")}
    assert mapped[Path("a.jpg")] == mapped[Path("b.jpg")]
    assert mapped[Path("a.jpg")] != mapped[Path("c.jpg")]
    renditions = [
        ImageRenditionProducer(database).produce(run_id, Path(name))
        for name in ("a.jpg", "b.jpg", "c.jpg")
    ]
    sealed = ResultStore(database).seal(
        ResultStore(database).build_minimal(
            run_id,
            [outcome.work.work_id for outcome in renditions],
            metadata_work_ids=[record.work_id for record in metadata],
            reverse_geocode_work_by_source=mapped,
        )
    )
    reviewed = PrecheckReadTool(database).read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
            "include": ["execution_boundary"],
        }
    )
    assert reviewed["result"]["readiness"] == "plan_ready"
    source_views = {source["locator"]["value"]: source for item in reviewed["items"] for source in item["source_items"]}
    projected = {o["name"]: o for o in source_views["b.jpg"]["observations"]}
    assert projected["gps_coordinates"]["value"]["latitude"] == 22.319330
    for name in ("address_candidate", "nearby_place_candidates"):
        observation = projected[name]
        assert observation["basis"]["query_coordinate"]["latitude"] == 22.319300
        assert 3 < observation["basis"]["projection"]["query_point_distance_meters"] < 4
        assert any(q["code"] == "geo_query_point_reused" for q in observation["qualifications"])
    assert projected["nearby_place_candidates"]["basis"]["requested_radius_meters"] == 500
    assert projected["nearby_place_candidates"]["basis"]["requested_max_places"] == 30



def test_nearby_coordinates_share_only_inside_a_media_bundle(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "a.jpeg", "b.jpg"))
    metadata = [
        _coordinate_work(
            database,
            run_id,
            name,
            latitude=latitude,
            longitude=114.1694,
        )
        for name, latitude in (
            ("a.jpg", 22.319300),
            ("a.jpeg", 22.319330),
            ("b.jpg", 22.319335),
        )
    ]
    bundles = tuple(
        BundleCandidateProducer(database).produce(
            run_id, [record.work_id for record in metadata]
        )
    )
    run_tool = PrecheckRunTool(database)
    producer = ReverseGeocodeProducer(database, run_tool)

    bundled = producer.freeze(
        run_id,
        [record.work_id for record in metadata],
        bundle_work_ids=[outcome.work.work_id for outcome in bundles],
    )
    unbundled = producer.freeze(
        run_id,
        [record.work_id for record in metadata],
    )

    assert len(bundles) == 2
    assert bundled.logical_query_count == 2
    assert unbundled.logical_query_count == 3
    assert any(
        set(query.source_paths) == {Path("a.jpg"), Path("a.jpeg")}
        for query in bundled.queries
    )


def test_same_asset_candidate_splits_when_time_and_coordinates_conflict(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "a.jpeg"))
    metadata = [
        _coordinate_work(
            database,
            run_id,
            name,
            latitude=latitude,
            longitude=114.1694,
            capture_time=capture_time,
        )
        for name, latitude, capture_time in (
            ("a.jpg", 22.319300, "2026-05-04T12:00:00+00:00"),
            ("a.jpeg", 22.319330, "2026-05-04T12:05:00+00:00"),
        )
    ]
    bundles = tuple(
        BundleCandidateProducer(database).produce(
            run_id, [record.work_id for record in metadata]
        )
    )

    batch = ReverseGeocodeProducer(database, PrecheckRunTool(database)).freeze(
        run_id,
        [record.work_id for record in metadata],
        bundle_work_ids=[outcome.work.work_id for outcome in bundles],
    )

    assert len(bundles) == 1
    assert batch.logical_query_count == 2


def test_provider_no_result_remains_an_executed_observation() -> None:
    provider = FakeGoogle(status="no_result")
    geocoder = AdaptiveReverseGeocoder(
        providers={"google_maps": provider},
        provider_order=("google_maps",),
        initial_provider="google_maps",
    )

    result = geocoder.lookup(GeoCoordinate(35.658, 139.7013))

    assert result.status == "no_result"
    assert result.location is None
    assert result.provider_request_count == 2
    assert len(provider.calls) == 1


def test_reused_query_identity_does_not_depend_on_batch_order(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    first_run = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    beijing = _coordinate_work(
        database, first_run, "a.jpg", latitude=39.9042, longitude=116.4074
    )
    run_tool = PrecheckRunTool(database)
    first_public_ref = _public_run(run_tool, "request:route-seed")
    first_google = FakeCountryProvider("google_maps", "China", "CN", MapDatum.WGS84)
    first_amap = FakeCountryProvider("amap", "中国", "CN", MapDatum.GCJ02)
    profile = ReverseGeocodeProfile(provider_profile="route-test-v1")
    first_producer = ReverseGeocodeProducer(
        database, run_tool, _geo_tool(tmp_path / "first", first_google, first_amap)
    )
    assert (
        first_producer.produce(
            first_public_ref, first_run, [beijing.work_id], profile=profile
        ).status
        == "confirmation_required"
    )
    _authorize(run_tool, first_public_ref)
    first_completed = first_producer.produce(
        first_public_ref, first_run, [beijing.work_id], profile=profile
    )
    assert len(first_completed.outcomes) == 1
    first_work_id = first_completed.outcomes[0].work.work_id
    assert len(first_google.calls) == 1
    assert first_amap.calls == []

    second_run = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    second_beijing = _coordinate_work(
        database, second_run, "a.jpg", latitude=39.9042, longitude=116.4074
    )
    shanghai = _coordinate_work(
        database, second_run, "b.jpg", latitude=31.2304, longitude=121.4737
    )
    run_tool.run(
        {
            "action": "cancel",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": first_public_ref,
        }
    )
    second_public_ref = _public_run(run_tool, "request:route-continuity")
    second_google = FakeCountryProvider("google_maps", "China", "CN", MapDatum.WGS84)
    second_amap = FakeCountryProvider("amap", "中国", "CN", MapDatum.GCJ02)
    second_producer = ReverseGeocodeProducer(
        database,
        run_tool,
        _geo_tool(tmp_path / "second", second_google, second_amap),
    )

    pending = second_producer.produce(
        second_public_ref,
        second_run,
        [second_beijing.work_id, shanghai.work_id],
        profile=profile,
    )
    assert pending.status == "confirmation_required"
    assert pending.batch.pending_query_count == 1
    assert pending.batch.logical_query_count == 2
    status = run_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": second_public_ref,
        }
    )
    disclosure = status["confirmation"]["disclosure"]
    assert status["confirmation"]["disclosure"]["pending_logical_queries"] == 1
    assert (
        status["confirmation"]["content_identity"]
        == "sha256:"
        + hashlib.sha256(
            json.dumps(
                disclosure, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )
    assert disclosure["geo_request_fingerprint"] == pending.batch.pending_fingerprint
    assert disclosure["coordinates"] == [
        GeoCoordinate(31.2304, 121.4737, MapDatum.WGS84).value()
    ]
    assert disclosure["max_provider_requests"] == 12
    assert pending.batch.pending_fingerprint != pending.batch.batch_fingerprint
    _authorize(run_tool, second_public_ref)
    completed = second_producer.produce(
        second_public_ref,
        second_run,
        [second_beijing.work_id, shanghai.work_id],
        profile=profile,
    )

    reused_outcome = next(
        outcome
        for outcome in completed.outcomes
        if outcome.work.work_id == first_work_id
    )
    assert reused_outcome.reused is True
    assert second_google.calls == [
        (GeoCoordinate(31.2304, 121.4737, MapDatum.WGS84), "zh")
    ]
    assert second_amap.calls == []
    shanghai_outcome = next(
        outcome
        for outcome in completed.outcomes
        if outcome.query.coordinate.latitude == 31.2304
    )
    chained = shanghai_outcome.work
    assert not any(
        dependency.kind is DependencyKind.UPSTREAM_WORK
        for dependency in chained.spec.dependencies
    )
    standalone = second_producer.freeze(
        second_run,
        [shanghai.work_id],
        profile=profile,
    )
    assert standalone.work[0].work_id == chained.work_id


def test_semantically_compatible_legacy_chain_observations_are_reused(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    coordinates = (
        GeoCoordinate(22.3193, 114.1694),
        GeoCoordinate(22.2819, 114.1589),
    )
    metadata = [
        _coordinate_work(
            database,
            run_id,
            name,
            latitude=coordinate.latitude,
            longitude=coordinate.longitude,
        )
        for name, coordinate in zip(("a.jpg", "b.jpg"), coordinates, strict=True)
    ]
    first_legacy = _legacy_geocode_work(database, run_id, coordinates[0])
    second_legacy = _legacy_geocode_work(
        database,
        run_id,
        coordinates[1],
        previous=first_legacy,
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:legacy-cache")

    outcome = ReverseGeocodeProducer(database, run_tool).produce(
        public_run_ref,
        run_id,
        [record.work_id for record in metadata],
    )

    assert outcome.status == "completed"
    assert outcome.batch.pending_query_count == 0
    assert outcome.actual_provider_requests == 0
    assert all(item.reused for item in outcome.outcomes)
    assert all(
        item.work.spec.producer_identity == "builtin-geo-component-observations-v4"
        for item in outcome.outcomes
    )
    assert all(
        not any(
            dependency.kind is DependencyKind.UPSTREAM_WORK
            for dependency in item.work.spec.dependencies
        )
        for item in outcome.outcomes
    )
    for item in outcome.outcomes:
        components = {
            observation["name"]: observation for observation in item.observations
        }
        assert components["address_candidate"]["status"] == "available"
        assert components["nearby_place_candidates"]["status"] == "not_checked"
        assert (
            components["nearby_place_candidates"]["basis"]["code"]
            == "historical_geo_unrecorded"
        )
    work = WorkStore(database)
    for legacy in (first_legacy, second_legacy):
        assert work.get_work(legacy.work_id).status is WorkStatus.SUCCEEDED
        with pytest.raises(KeyError, match="not attached to this run"):
            work.get_run_work(run_id, legacy.work_id)


def test_reverse_only_legacy_observation_is_not_reused_as_address_and_poi(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    coordinate = GeoCoordinate(22.3193, 114.1694)
    metadata = _coordinate_work(
        database,
        run_id,
        "a.jpg",
        latitude=coordinate.latitude,
        longitude=coordinate.longitude,
    )
    _legacy_geocode_work(
        database,
        run_id,
        coordinate,
        provider_request_count=1,
    )

    batch = ReverseGeocodeProducer(database, PrecheckRunTool(database)).freeze(
        run_id,
        [metadata.work_id],
    )

    assert batch.pending_query_count == 0
    assert batch.work[0].output["observations"][-1]["status"] == "not_checked"
    assert (
        batch.work[0].spec.producer_identity == "builtin-geo-component-observations-v4"
    )


def test_missing_authority_and_decline_make_no_calls(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=35.658, longitude=139.7013
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:disabled")
    provider = FakeGoogle()
    producer = ReverseGeocodeProducer(
        database,
        run_tool,
        _geo_tool(tmp_path, provider),
    )

    pending = producer.produce(public_run_ref, run_id, [metadata.work_id])
    assert pending.status == "confirmation_required"
    assert provider.calls == []
    missing = run_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": public_run_ref,
            "decision": "proceed",
        }
    )
    assert missing["error"]["code"] == "confirmation_required"
    declined = run_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": public_run_ref,
            "decision": "decline",
        }
    )
    assert declined["state"] == "cancelled"
    assert provider.calls == []


def test_changed_pending_set_requires_new_confirmation(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    first = _coordinate_work(
        database, run_id, "a.jpg", latitude=35.658, longitude=139.7013
    )
    second = _coordinate_work(
        database, run_id, "b.jpg", latitude=39.9042, longitude=116.4074
    )
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:changed")
    provider = FakeGoogle()
    producer = ReverseGeocodeProducer(
        database,
        run_tool,
        _geo_tool(tmp_path, provider),
    )
    profile = ReverseGeocodeProfile(provider_profile="mock-google-v1")
    first_pending = producer.produce(
        public_run_ref, run_id, [first.work_id], profile=profile
    )
    _authorize(run_tool, public_run_ref)
    producer.produce(public_run_ref, run_id, [first.work_id], profile=profile)

    changed = producer.produce(
        public_run_ref,
        run_id,
        [first.work_id, second.work_id],
        profile=profile,
    )

    assert first_pending.batch.pending_query_count == 1
    assert changed.status == "confirmation_required"
    assert changed.batch.pending_query_count == 1
    assert (
        run_tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "status",
                "run_ref": public_run_ref,
            }
        )["confirmation"]["disclosure"]["pending_logical_queries"]
        == 1
    )


def test_cancellation_stops_new_external_queries_without_discarding_finished_work(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    metadata = [
        _coordinate_work(
            database,
            run_id,
            name,
            latitude=latitude,
            longitude=longitude,
        )
        for name, latitude, longitude in (
            ("a.jpg", 35.658, 139.7013),
            ("b.jpg", 40.7128, -74.006),
        )
    ]
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:cancel-external")
    provider = FakeGoogle()
    original_lookup = provider.lookup

    def cancel_after_first(coordinate: GeoCoordinate, *, language: str):
        result = original_lookup(coordinate, language=language)
        run_tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "cancel",
                "run_ref": public_run_ref,
            }
        )
        return result

    provider.lookup = cancel_after_first
    producer = ReverseGeocodeProducer(
        database,
        run_tool,
        _geo_tool(tmp_path, provider),
    )
    profile = ReverseGeocodeProfile(provider_profile="mock-google-v1")
    producer.produce(
        public_run_ref,
        run_id,
        [item.work_id for item in metadata],
        profile=profile,
    )
    _authorize(run_tool, public_run_ref)

    interrupted = producer.produce(
        public_run_ref,
        run_id,
        [item.work_id for item in metadata],
        profile=profile,
    )

    assert interrupted.status == "partial"
    assert len(interrupted.outcomes) == 2
    assert interrupted.outcomes[0].work.status is WorkStatus.SUCCEEDED
    assert interrupted.outcomes[1].work.status is WorkStatus.RETRYABLE_FAILURE
    assert len(provider.calls) == 1
    status = run_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": public_run_ref,
        }
    )
    assert status["state"] == "cancelled"
    assert "result" not in status


@pytest.mark.parametrize("interrupted", [True, False], ids=["crash", "known-zero"])
@pytest.mark.parametrize("view", ["work", "diagnostics", "review", "historical"])
def test_recovered_geo_effects_preserve_unknown_and_known_zero(
    tmp_path: Path, monkeypatch, interrupted: bool, view: str
) -> None:
    class SyntheticProvider:
        capabilities = GeoProviderCapabilities(
            "synthetic",
            (GeoOperation.RESOLVE_PLACE,),
            MapDatum.WGS84,
            max_billable_units_per_operation=1,
        )
        calls = 0

        def execute(self, operation, coordinate, **_kwargs):
            assert operation is GeoOperation.RESOLVE_PLACE
            self.calls += 1
            status = (
                GeoComponentStatus.NO_RESULT
                if interrupted
                else GeoComponentStatus.FAILED
            )
            return GeoProviderExecution(
                GeoComponentResult(
                    GeoOperation.REVERSE_GEOCODE, status, (), coordinate
                ),
                GeoProviderAttempt(
                    "synthetic",
                    operation,
                    status,
                    coordinate,
                    coordinate,
                    1 if interrupted else 0,
                    1 if interrupted else 0,
                    None if interrupted else "permanent",
                ),
                (
                    GeoComponentResult(
                        GeoOperation.NEARBY_PLACES, status, (), coordinate
                    ),
                ),
            )

    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=22.3, longitude=114.1
    )
    run = PrecheckRunTool(database)
    run_ref = _public_run(run, "request:recover-effects")
    provider = SyntheticProvider()
    capability = GeoCapability(
        {"synthetic": provider}, OrderedGeoRoutingPolicy(("synthetic",))
    )
    journal_path = tmp_path / "geo-journal.sqlite3"
    geo = GeoQueryTool(capability, GeoOperationJournal(journal_path))
    producer = ReverseGeocodeProducer(database, run, geo)
    assert (
        producer.produce(run_ref, run_id, [metadata.work_id]).status
        == "confirmation_required"
    )
    assert provider.calls == 0
    _authorize(run, run_ref)
    journaled_requests = []

    def crash_before_completion(request_id, _response):
        journaled_requests.append(request_id)
        raise RuntimeError("synthetic crash before journal completion")

    if interrupted:
        with monkeypatch.context() as crash:
            crash.setattr(geo.journal, "complete", crash_before_completion)
            with pytest.raises(RuntimeError, match="synthetic crash"):
                producer.produce(run_ref, run_id, [metadata.work_id])
        entry = geo.journal.get(journaled_requests[0])
        assert entry.state == "indeterminate"
        assert entry.result["attempts"] == []
        assert entry.result["effects"]["provider_requests"] is None
        assert entry.result["effects"]["billable_units"] is None
        assert entry.result["effects"]["transmitted_data_classes"] == [
            "coordinate",
            "datum",
            "locale",
        ]
    else:
        completed = producer.produce(run_ref, run_id, [metadata.work_id])
        assert completed.actual_provider_requests == 0
    assert provider.calls == 1

    # Reopen both stores: recovery must consume retained evidence without new effects.
    run = PrecheckRunTool(database)
    geo = GeoQueryTool(capability, GeoOperationJournal(journal_path))
    producer = ReverseGeocodeProducer(database, run, geo)
    recovered = producer.produce(run_ref, run_id, [metadata.work_id])
    assert recovered.status == ("indeterminate" if interrupted else "completed")
    assert recovered.actual_provider_requests == (None if interrupted else 0)
    assert provider.calls == 1
    if interrupted:
        assert geo.journal.get(journaled_requests[0]) == entry

    if view == "historical":
        run.run(
            {"action": "cancel", "dataset_ref": "dataset:dataset-a", "run_ref": run_ref}
        )
        run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
        metadata = _coordinate_work(
            database, run_id, "a.jpg", latitude=22.3, longitude=114.1
        )
        run_ref = _public_run(run, "request:historical-effects")
        recovered = producer.produce(run_ref, run_id, [metadata.work_id])
        assert recovered.actual_provider_requests == 0
        assert provider.calls == 1

    expected_count = None if interrupted else 0
    if view == "work":
        output = recovered.outcomes[0].work.output["result"]
        assert output["provider_request_count"] == expected_count
        assert output["billable_units"] == expected_count
        return
    if view == "review":
        rendition = ImageRenditionProducer(database).produce(run_id, Path("a.jpg"))
        store = ResultStore(database)
        draft = store.build_minimal(
            run_id,
            [rendition.work.work_id],
            metadata_work_ids=[metadata.work_id],
            reverse_geocode_work_by_source=recovered.work_by_source(),
        )
        if interrupted:
            assert all(
                any(
                    q["code"] == "geo_effect_indeterminate"
                    and q["effect"] == "blocks_use"
                    for q in observation.get("qualifications", ())
                )
                for observation in recovered.outcomes[0].observations
                if observation["name"]
                in {"address_candidate", "nearby_place_candidates"}
            )
            # The admission journal cannot identify an attempted Provider.
            # Preserve the seal gate; do not invent that missing evidence.
            with pytest.raises(ResultSealError, match="provider evidence"):
                store.seal(draft)
            return
        sealed = store.seal(draft)
        original = sealed.path.read_bytes()
        review = PrecheckReadTool(database).read(
            {
                "action": "review",
                "dataset_ref": "dataset:dataset-a",
                "result_ref": sealed.result_ref,
                "include": ["execution_boundary"],
            }
        )
        assert review["result"]["readiness"] == (
            "blocked" if interrupted else "plan_ready"
        )
        assert sealed.path.read_bytes() == original
        boundary = review["execution_boundary"]
    else:
        status = run.run(
            {
                "action": "status",
                "dataset_ref": "dataset:dataset-a",
                "run_ref": run_ref,
                "include": ["diagnostics"],
            }
        )
        boundary = status["diagnostics"]["execution_boundary"]
    assert boundary["logical_external_queries"] == 1
    assert boundary["current_provider_requests"] == (
        0 if view == "historical" else expected_count
    )
    assert boundary["historical_provider_requests"] == (
        expected_count if view == "historical" else 0
    )
    assert boundary["billable_calls"] == expected_count
    assert boundary["transmitted_data_classes"] == (
        ["coordinate", "datum", "locale"] if interrupted else []
    )
    assert provider.calls == 1


@pytest.mark.parametrize("request_count", [None, 0, 2])
def test_legacy_result_review_preserves_unknown_effects(tmp_path, request_count):
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=22.3, longitude=114.1
    )
    legacy = _legacy_geocode_work(
        database,
        run_id,
        GeoCoordinate(22.3, 114.1),
        provider_request_count=request_count,
    )
    run = PrecheckRunTool(database)
    run_ref = _public_run(run, "request:legacy-unknown-effects")
    reused = ReverseGeocodeProducer(database, run).produce(
        run_ref, run_id, [metadata.work_id]
    )
    assert reused.actual_provider_requests == 0
    assert all(outcome.reused for outcome in reused.outcomes)
    assert WorkStore(database).get_work(legacy.work_id).output == legacy.output
    rendition = ImageRenditionProducer(database).produce(run_id, Path("a.jpg"))
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(
            run_id,
            [rendition.work.work_id],
            metadata_work_ids=[metadata.work_id],
            reverse_geocode_work_by_source=reused.work_by_source(),
        )
    )
    before = sealed.path.read_bytes()
    review = PrecheckReadTool(database).read(
        {
            "action": "review",
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "include": ["execution_boundary"],
        }
    )
    boundary = review["execution_boundary"]
    assert boundary["historical_provider_requests"] == request_count
    assert boundary["current_provider_requests"] == 0
    assert boundary["billable_calls"] is None
    assert boundary["transmitted_data_classes"] == (
        [] if request_count == 0 else ["coordinate", "datum", "locale"]
    )
    assert sealed.path.read_bytes() == before
    assert store.get(sealed.result_ref).digest == sealed.digest


def test_sealed_result_exposes_candidates_and_external_effect_proof(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    metadata = [
        _coordinate_work(
            database,
            run_id,
            name,
            latitude=35.658,
            longitude=139.7013,
        )
        for name in ("a.jpg", "b.jpg")
    ]
    run_tool = PrecheckRunTool(database)
    public_run_ref = _public_run(run_tool, "request:result-evidence")
    provider = FakeGoogle()
    producer = ReverseGeocodeProducer(
        database,
        run_tool,
        _geo_tool(tmp_path, provider),
    )
    profile = ReverseGeocodeProfile(provider_profile="mock-google-v1")
    producer.produce(
        public_run_ref,
        run_id,
        [item.work_id for item in metadata],
        profile=profile,
    )
    _authorize(run_tool, public_run_ref)
    geocoded = producer.produce(
        public_run_ref,
        run_id,
        [item.work_id for item in metadata],
        profile=profile,
    )
    renditions = [
        ImageRenditionProducer(database).produce(run_id, Path(name))
        for name in ("a.jpg", "b.jpg")
    ]
    result_store = ResultStore(database)
    sealed = result_store.seal(
        result_store.build_minimal(
            run_id,
            [item.work.work_id for item in renditions],
            metadata_work_ids=[item.work_id for item in metadata],
            reverse_geocode_work_by_source=geocoded.work_by_source(),
        )
    )

    reader = PrecheckReadTool(database)
    accounts = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": sealed.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    read_schema = json.loads(
        (
            Path(__file__).parents[1]
            / "docs/spec/contract/precheck-read/precheck-read.tool.json"
        ).read_text(encoding="utf-8")
    )["outputSchema"]
    validator = Draft202012Validator(read_schema)
    validator.validate(accounts)
    source_response = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "source_item_refs": [
                account["source_item_ref"] for account in accounts["members"]
            ],
            "include": ["source_item", "observations"],
        }
    )
    validator.validate(source_response)
    for item in source_response["items"]:
        source = item["included"]
        assert all(
            observation["name"] != "reverse_geocode_attempt"
            for observation in source["observations"]
        )
        components = {
            observation["name"]: observation for observation in source["observations"]
        }
        for name in ("address_candidate", "nearby_place_candidates"):
            assert components[name]["basis"]["refs"] == [
                {"kind": "source_item", "ref": item["source_item_ref"]}
            ]
            assert components[name]["basis"]["query_coordinate"]["datum"] == "WGS84"
            assert "provider_request_count" not in components[name].get(
                "provenance", {}
            )
        assert (
            components["address_candidate"]["value"]["formatted_address"]
            == "Tokyo, Japan"
        )
        assert (
            components["nearby_place_candidates"]["value"][0]["name"]
            == "Nearby fixture place"
        )

    result_response = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
            "include": ["execution_boundary"],
        }
    )
    validator.validate(result_response)
    result_view = result_response["result"]
    qualification = next(
        item
        for item in result_view["qualifications"]
        if item["code"] == "external_reverse_geocode_candidates"
    )
    assert "1 logical queries" in qualification["message"]
    boundary = result_response["execution_boundary"]
    assert boundary["logical_external_queries"] == 1
    assert boundary["current_provider_requests"] == 2
    assert boundary["historical_provider_requests"] == 0
    assert boundary["attempts"][0]["provider"] == "google_maps"
    assert boundary["billable_calls"] is None

    summary = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "geo_summary",
        }
    )
    validator.validate(summary)
    assert summary["acquisition_status"] == "complete"
    assert summary["page"]["total"] == 1
    assert summary["coordinate_groups"][0]["member_count"] == 2
    assert summary["coordinate_groups"][0]["components"] == {
        "address": {"success": 2},
        "nearby_places": {"success": 2},
    }
    assert len(summary["coordinate_groups"][0]["candidate_evidence_refs"]) == 2
    assert summary["coordinate_groups"][0]["source_set"]["kind"] == "geo_coordinate"
    resolved_members = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "resolve",
            "source_set": summary["coordinate_groups"][0]["source_set"],
        }
    )
    validator.validate(resolved_members)
    assert set(item["source_item_ref"] for item in resolved_members["members"]) == {
        item["source_item_ref"] for item in accounts["members"]
    }
