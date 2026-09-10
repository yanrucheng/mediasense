"""Production routing uses target geography and never probes Google to find it."""

from datetime import datetime, timezone
from dataclasses import replace

import pytest

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCoordinate,
    GeoRequest,
    GeoSubject,
    GeoOperation,
    GeoRouteContext,
)
from mediasense.capabilities.geo.model import RetryPolicy
from mediasense.capabilities.geo.regions import service_region
from mediasense.runtime.composition import _geo_tool
from mediasense.runtime.config import RuntimeConfig
from mediasense.geo import GeoTransientError


@pytest.mark.parametrize(
    "lat,lon,expected",
    [
        (39.9, 116.4, "mainland"),
        (31.23, 121.47, "mainland"),
        (30.67, 104.06, "mainland"),
        (22.3, 114.17, "overseas"),
        (22.1987, 113.5439, "overseas"),
        (25.03, 121.56, "overseas"),
        (35.68, 139.76, "overseas"),
        (1.35, 103.82, "overseas"),
        (22.531, 114.114, "uncertain"),
    ],
)
def test_offline_regions_and_boundary_guard(lat, lon, expected):
    assert service_region(GeoCoordinate(lat, lon)) == expected


def test_datum_conversion_does_not_change_mainland_route():
    from mediasense.geo import XYConvertCoordinateConverter, MapDatum

    coordinate = GeoCoordinate(39.9, 116.4)
    converted = XYConvertCoordinateConverter().convert(coordinate, MapDatum.GCJ02)
    assert service_region(converted) == "mainland"


class Transport:
    network_profile = {
        "identity": "sha256:" + "a" * 64,
        "proxy_receivers": [],
        "no_proxy_configured": False,
        "ca_source": "system",
        "reachability": "not_checked",
        "tls_verification": True,
    }
    fail_google = False

    def __init__(self):
        self.calls = []

    def get_json(self, url, **kwargs):
        self.calls.append(url)
        if "amap.com" in url:
            return {
                "status": "1",
                "regeocode": {
                    "formatted_address": "Mainland place",
                    "addressComponent": {},
                    "pois": [],
                },
            }
        if self.fail_google:
            raise GeoTransientError(
                "synthetic unreachable overseas service",
                request_count=1,
                failure_code="transport_timeout",
            )
        return {
            "status": "OK",
            "results": [
                {"formatted_address": "Overseas place", "address_components": []}
            ],
        }

    def post_json(self, url, **kwargs):
        self.calls.append(url)
        return {"places": []}


def configured(tmp_path, monkeypatch, google=True):
    transport = Transport()
    monkeypatch.setenv("AMAP_API_KEY", "synthetic")
    if google:
        monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "synthetic")
    else:
        monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    monkeypatch.setattr(
        "mediasense.geo.UrllibJsonTransport", lambda **kwargs: transport
    )
    tool = _geo_tool(tmp_path, RuntimeConfig("AMAP_API_KEY", "GOOGLE_MAPS_API_KEY", ()))
    tool.capability.retry_policy = RetryPolicy(backoff_seconds=(0, 0))
    for p in tool.capability.providers.values():
        p._limiter.minimum_interval = 0
    return tool, transport


def authorize(tool, request):
    return GeoAuthorization(
        "human:synthetic",
        tool.capability.fingerprint(request),
        datetime.now(timezone.utc),
        tool.capability.proposed_envelope(request),
    )


def test_mainland_production_uses_amap_even_when_google_is_unreachable(
    tmp_path, monkeypatch
):
    tool, transport = configured(tmp_path, monkeypatch)
    transport.fail_google = True
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("beijing", GeoCoordinate(39.9, 116.4)),),
        "zh",
        radius_meters=500,
        max_places=30,
        route_context=GeoRouteContext(preferred_provider="google_maps"),
    )
    result = tool.handle(
        {"request_id": "request:mainland", **request.value()},
        authorization=authorize(tool, request),
    )
    assert (
        result["outcome"] == "partial"
    )  # address available; bounded nearby query found none
    assert len(transport.calls) == 1 and "amap.com" in transport.calls[0]
    assert result["routing"][0]["region"] == "mainland"
    assert result["effects"]["provider_requests"] == 1


def test_overseas_outage_never_falls_back_to_reachable_amap(tmp_path, monkeypatch):
    tool, transport = configured(tmp_path, monkeypatch)
    transport.fail_google = True
    request = GeoRequest(
        GeoOperation.REVERSE_GEOCODE,
        (
            GeoSubject("tokyo", GeoCoordinate(35.68, 139.76)),
            GeoSubject("hk", GeoCoordinate(22.3, 114.17)),
        ),
        "zh",
    )
    result = tool.handle(
        {"request_id": "request:overseas", **request.value()},
        authorization=authorize(tool, request),
    )
    assert result["outcome"] == "blocked"
    assert len(transport.calls) == 3
    assert all("amap.com" not in url for url in transport.calls)
    assert result["components"][1]["status"] == "not_requested"
    assert result["effects"]["provider_requests"] == 3
    assert result["effects"]["billable_units"] is None
    assert all(a["status"] == "indeterminate" for a in result["attempts"])


def test_missing_suitable_provider_is_effect_free(tmp_path, monkeypatch):
    tool, transport = configured(tmp_path, monkeypatch, google=False)
    request = GeoRequest(
        GeoOperation.REVERSE_GEOCODE,
        (GeoSubject("hk", GeoCoordinate(22.3, 114.17)),),
        "zh",
    )
    result = tool.handle({"request_id": "request:missing", **request.value()})
    assert result["outcome"] == "unavailable"
    assert result["routing"][0]["required_provider"] == "google_maps"
    assert not transport.calls


def test_mixed_batch_and_reordered_identity_keep_per_coordinate_routes(
    tmp_path, monkeypatch
):
    tool, transport = configured(tmp_path, monkeypatch)
    request = GeoRequest(
        GeoOperation.REVERSE_GEOCODE,
        (
            GeoSubject("hk", GeoCoordinate(22.3, 114.17)),
            GeoSubject("bj", GeoCoordinate(39.9, 116.4)),
        ),
        "zh",
    )
    reordered = replace(request, subjects=tuple(reversed(request.subjects)))
    assert tool.capability.fingerprint(request) == tool.capability.fingerprint(
        reordered
    )
    result = tool.handle(
        {"request_id": "request:mixed", **request.value()},
        authorization=authorize(tool, request),
    )
    assert result["outcome"] == "success"
    assert "googleapis.com" in transport.calls[0] and "amap.com" in transport.calls[1]
    assert result["effects"]["provider_requests"] == 2
    from mediasense.runtime.resources import load_contract
    from jsonschema import Draft202012Validator

    Draft202012Validator(
        load_contract("mediasense.geo.query")["outputSchema"]
    ).validate(result)


def test_non_provider_response_is_a_service_condition_not_a_location_gap(
    tmp_path, monkeypatch
):
    tool, transport = configured(tmp_path, monkeypatch)
    transport.get_json = lambda *args, **kwargs: {"status": "NOT_A_GOOGLE_RESPONSE"}
    request = GeoRequest(
        GeoOperation.REVERSE_GEOCODE,
        (
            GeoSubject("tokyo", GeoCoordinate(35.68, 139.76)),
            GeoSubject("hk", GeoCoordinate(22.3, 114.17)),
        ),
        "zh",
    )
    result = tool.handle(
        {"request_id": "request:invalid-service-response", **request.value()},
        authorization=authorize(tool, request),
    )
    assert result["outcome"] == "blocked"
    assert result["attempts"][0]["error_code"] == "provider_response_invalid"
    assert result["components"][1]["status"] == "not_requested"
