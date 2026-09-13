"""Offline checks through the production Geo assembly and HTTP boundary."""

from datetime import datetime, timezone
from io import BytesIO
import json
from urllib.error import HTTPError

import pytest

from mediasense.capabilities.geo import GeoAuthorization
from mediasense.runtime.composition import _geo_tool
from mediasense.runtime.config import RuntimeConfig
from mediasense.capabilities.geo.tool import _parse_request


def assembled(tmp_path, monkeypatch, *, error=None, reverse_error=None):
    calls = []

    def open_request(request, timeout):
        calls.append(request)
        failure = error if request.data else reverse_error
        if failure is not None:
            code, payload = failure
            raise HTTPError(
                request.full_url,
                code,
                "rejected",
                {},
                BytesIO(json.dumps(payload).encode()),
            )
        value = (
            {"places": [{"displayName": {"text": "Offline place"}}]}
            if request.data
            else {
                "status": "OK",
                "results": [
                    {"formatted_address": "Offline address", "address_components": []}
                ],
            }
        )
        return BytesIO(json.dumps(value).encode())

    class Opener:
        open = staticmethod(open_request)

    monkeypatch.setattr("mediasense.geo.build_opener", lambda *args: Opener())
    monkeypatch.setattr("mediasense.geo.getproxies", lambda: {})
    monkeypatch.setenv("MEDIASENSE_TEST_GOOGLE_KEY", "offline-key")
    monkeypatch.delenv("MEDIASENSE_TEST_AMAP_KEY", raising=False)
    config = RuntimeConfig(
        sources=(),
        google_maps_api_key_env="MEDIASENSE_TEST_GOOGLE_KEY",
        amap_api_key_env="MEDIASENSE_TEST_AMAP_KEY",
        geo_network={"minimum_interval_seconds": 0},
    )
    tool = _geo_tool(tmp_path, config)
    public = {
        "request_id": "request:nearby-production",
        "operation": "resolve_place",
        "subjects": [
            {
                "subject_ref": f"source:{i}",
                "coordinate": {
                    "latitude": 22.30 + i * 0.01,
                    "longitude": 114.17,
                    "datum": "WGS84",
                },
            }
            for i in range(3)
        ],
        "locale": "zh-CN",
        "radius_meters": 800,
        "max_places": 30,
    }
    request = _parse_request(public)
    authorization = GeoAuthorization(
        "human:offline",
        tool.capability.fingerprint(request),
        datetime.now(timezone.utc),
        tool.capability.proposed_envelope(request),
    )
    return tool, public, authorization, calls


def test_production_split_applies_google_profile_bounds_and_replays(
    tmp_path, monkeypatch
):
    tool, request, authority, calls = assembled(tmp_path, monkeypatch)
    result = tool.handle(request, authorization=authority)
    assert result["outcome"] == "success"
    assert len(calls) == result["effects"]["provider_requests"] == 6
    assert result["effects"]["billable_units"] is None
    payloads = [json.loads(call.data) for call in calls if call.data]
    assert len(payloads) == 3
    assert {p["maxResultCount"] for p in payloads} == {10}
    assert {p["locationRestriction"]["circle"]["radius"] for p in payloads} == {500}
    assert tool.handle(request) == result
    assert len(calls) == 6


@pytest.mark.parametrize(
    "payload,code",
    [
        (
            {
                "error": {
                    "status": "INVALID_ARGUMENT",
                    "message": "secret-key must not escape",
                }
            },
            "provider_request_invalid",
        ),
        ({"unknown": "secret-key must not escape"}, "provider_http_rejected"),
    ],
)
def test_request_defects_surface_after_checkpoint_without_continuing(
    tmp_path, monkeypatch, payload, code
):
    tool, request, authority, calls = assembled(
        tmp_path, monkeypatch, error=(400, payload)
    )
    with pytest.raises(RuntimeError, match=code):
        tool.handle(request, authorization=authority)
    assert len(calls) == 2
    saved = [
        json.loads(row["execution_json"])
        for row in tool.journal.executions(request["request_id"])
    ]
    assert saved[0]["components"][0]["status"] == "success"
    assert saved[1]["attempts"][0]["error_code"] == code
    assert sum(a["provider_requests"] for row in saved for a in row["attempts"]) == 2
    assert all(a["billable_units"] is None for row in saved for a in row["attempts"])
    assert "secret-key" not in json.dumps(saved)
    # A later local replay must not turn a programming failure into Plan-ready partial evidence.
    with pytest.raises(RuntimeError, match=code):
        tool.handle(request)
    assert len(calls) == 2


@pytest.mark.parametrize("reverse", [False, True])
def test_service_disabled_stops_remaining_components_and_coordinates(
    tmp_path, monkeypatch, reverse
):
    failure = (
        400,
        {
            "error": {
                "status": "FAILED_PRECONDITION",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": "SERVICE_DISABLED",
                        "domain": "googleapis.com",
                    }
                ],
            }
        },
    )
    tool, request, authority, calls = assembled(
        tmp_path,
        monkeypatch,
        error=None if reverse else failure,
        reverse_error=failure if reverse else None,
    )
    result = tool.handle(request, authorization=authority)
    assert result["outcome"] == "blocked"
    assert len(calls) == result["effects"]["provider_requests"] == (1 if reverse else 2)
    assert result["effects"]["billable_units"] is None
    assert result["components"][0]["status"] == ("failed" if reverse else "success")
    assert all(c["status"] == "not_requested" for c in result["components"][2:])
    if reverse:
        assert result["components"][1]["status"] == "not_requested"
    assert tool.handle(request) == result


@pytest.mark.parametrize("limit,radius", [(1, 10), (10, 500), (20, 600), (30, 800)])
def test_lower_bounds_are_preserved_on_every_google_entry(limit, radius):
    from mediasense.capabilities.geo import GeoCoordinate, GeoOperation
    from mediasense.geo import GoogleMapsReverseGeocoder

    payloads = []

    class Transport:
        def get_json(self, *a, **kw):
            return {"status": "ZERO_RESULTS", "results": []}

        def post_json(self, *a, **kw):
            payloads.append(kw["payload"])
            return {"places": []}

    provider = GoogleMapsReverseGeocoder(
        "offline", transport=Transport(), minimum_interval=0
    )
    for operation in (GeoOperation.RESOLVE_PLACE, GeoOperation.NEARBY_PLACES):
        provider.execute(
            operation,
            GeoCoordinate(35.0, 139.0),
            locale="en",
            radius_meters=radius,
            max_places=limit,
        )
    assert len(payloads) == 2
    assert all(p["maxResultCount"] == min(limit, 10) for p in payloads)
    assert all(
        p["locationRestriction"]["circle"]["radius"] == min(radius, 500)
        for p in payloads
    )


def test_explicit_location_failure_remains_local(tmp_path, monkeypatch):
    from mediasense.geo import GeoPermanentError

    tool, request, authority, calls = assembled(tmp_path, monkeypatch)
    transport = tool.capability.providers["google_maps"]._transport
    real_post = transport.post_json
    failed = []

    def location_failure(*args, **kwargs):
        if not failed:
            failed.append(True)
            raise GeoPermanentError(
                "Known location-specific rejection from a conforming adapter",
                request_count=1,
                failure_code="location_terminal",
            )
        return real_post(*args, **kwargs)

    monkeypatch.setattr(transport, "post_json", location_failure)
    result = tool.handle(request, authorization=authority)
    assert result["outcome"] == "partial"
    assert result["effects"]["provider_requests"] == 6
    assert result["components"][1]["status"] == "failed"
    assert all(c["status"] == "success" for c in result["components"][2:])


def test_recovery_of_service_prerequisite_preserves_success_and_cumulative_cost(
    tmp_path, monkeypatch
):
    from mediasense.capabilities.geo import GeoEffectEnvelope
    from mediasense.capabilities.geo.tool import result_digest

    failure = (400, {"error": {"status": "FAILED_PRECONDITION"}})
    tool, request, authority, calls = assembled(tmp_path, monkeypatch, error=failure)
    first = tool.handle(request, authorization=authority)
    assert first["outcome"] == "blocked"
    transport = tool.capability.providers["google_maps"]._transport
    monkeypatch.setattr(transport, "post_json", lambda *a, **kw: {"places": []})
    recovery = {
        **request,
        "request_id": "request:nearby-recovery",
        "recovery": {
            "prior_request_id": request["request_id"],
            "result_digest": result_digest(first),
        },
    }
    proposal = tool.handle(recovery)
    second = tool.handle(
        recovery,
        authorization=GeoAuthorization(
            "human:recovery",
            proposal["request_fingerprint"],
            datetime.now(timezone.utc),
            GeoEffectEnvelope(**proposal["required_authorization"]),
        ),
    )
    assert second["outcome"] == "partial"  # addresses available, nearby valid no_result
    assert second["effects"]["provider_requests"] == 7
    assert second["effects"]["billable_units"] is None
    assert second["components"][0] == first["components"][0]
    assert sum(a["operation"] == "reverse_geocode" for a in second["attempts"]) == 3
    assert tool.handle(recovery) == second


def test_unclassified_historical_work_cannot_become_new_plan_ready_evidence(
    tmp_path, monkeypatch
):
    import hashlib
    import sqlite3
    from mediasense.precheck import (
        AccountingStore,
        PrecheckRunTool,
        ReverseGeocodeProducer,
    )
    from test_geocode import _closed_run, _coordinate_work, _public_run, _authorize

    tool, _, _, calls = assembled(tmp_path / "geo", monkeypatch)
    database = tmp_path / "work.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(database, run, "a.jpg", latitude=22.3, longitude=114.17)
    control = PrecheckRunTool(database)
    public = _public_run(control, "request:historical-geo")
    producer = ReverseGeocodeProducer(database, control, tool)
    producer.produce(public, run, [metadata.work_id])
    _authorize(control, public)
    complete = producer.produce(public, run, [metadata.work_id])
    record = complete.outcomes[0].work
    retained = record.output
    # Model the historical classification on a synthetic, isolated Work only.
    retained["result"]["status"] = "partial"
    retained["result"]["component_outcomes"]["nearby_places"] = "failed"
    retained["result"]["attempts"][-1]["error_code"] = "http_permanent"
    retained["result"]["attempts"][-1]["status"] = "failed"
    encoded = json.dumps(
        retained, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    with sqlite3.connect(database) as db:
        db.execute(
            "UPDATE work_records SET output_json=?, output_digest=? WHERE work_id=?",
            (
                encoded,
                hashlib.sha256(encoded.encode()).hexdigest(),
                record.work_id,
            ),
        )
    sent = len(calls)
    with pytest.raises(RuntimeError, match="http_permanent"):
        producer.produce(public, run, [metadata.work_id])
    assert len(calls) == sent


def test_authorized_alternative_keeps_its_own_retry_cycle(tmp_path):
    from mediasense.capabilities.geo import (
        GeoCoordinate,
        GeoOperation,
        GeoRequest,
        GeoSubject,
        OrderedGeoRoutingPolicy,
        GeoQueryTool,
        GeoOperationJournal,
        GeoTransientError,
    )
    from mediasense.capabilities.geo.model import RetryPolicy
    from mediasense.capabilities.geo.service import GeoCapability
    from mediasense.geo import AMapReverseGeocoder, GoogleMapsReverseGeocoder
    from test_geocode import FakeTransport, IdentityConverter

    google_transport = FakeTransport(
        get_response={"status": "ZERO_RESULTS", "results": []},
        post_response={"error": {"status": "RESOURCE_EXHAUSTED"}},
    )

    class AlternativeTransport(FakeTransport):
        def get_json(self, *args, **kwargs):
            response = super().get_json(*args, **kwargs)
            if len(self.gets) == 1:
                raise GeoTransientError(
                    "service transient", request_count=1, safe_to_retry=True
                )
            return response

    alternative_transport = AlternativeTransport(
        get_response={
            "status": "1",
            "regeocode": {"formatted_address": "Offline alternative", "pois": []},
        }
    )
    providers = {
        "google_maps": GoogleMapsReverseGeocoder(
            "offline", transport=google_transport, minimum_interval=0
        ),
        "amap": AMapReverseGeocoder(
            "offline",
            transport=alternative_transport,
            converter=IdentityConverter(),
            minimum_interval=0,
        ),
    }
    capability = GeoCapability(
        providers,
        OrderedGeoRoutingPolicy(tuple(providers)),
        retry_policy=RetryPolicy(backoff_seconds=(0, 0)),
    )
    tool = GeoQueryTool(capability, GeoOperationJournal(tmp_path / "geo.sqlite3"))
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("source:a", GeoCoordinate(35.0, 139.0)),),
        "en",
        radius_meters=500,
        max_places=30,
    )
    authority = GeoAuthorization(
        "human:offline",
        capability.fingerprint(request),
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )
    result = tool.handle(
        {"request_id": "request:alternative", **request.value()},
        authorization=authority,
    )
    assert result["outcome"] == "no_result"
    assert len(alternative_transport.gets) == 2
    assert result["effects"]["provider_requests"] == 4
