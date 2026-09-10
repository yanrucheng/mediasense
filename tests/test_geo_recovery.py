"""Recovery must preserve evidence independently of later transport outcomes."""

from datetime import datetime, timezone

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCoordinate,
    GeoOperation,
    GeoRequest,
    GeoSubject,
    OrderedGeoRoutingPolicy,
    GeoTransientError,
)
from mediasense.capabilities.geo.service import GeoCapability
from mediasense.geo import GoogleMapsReverseGeocoder


class FailingNearbyTransport:
    def __init__(self):
        self.gets = 0
        self.posts = 0

    def get_json(self, *args, **kwargs):
        self.gets += 1
        if self.gets > 1:
            raise GeoTransientError("later address unavailable", request_count=1)
        return {
            "status": "OK",
            "results": [
                {"formatted_address": "Retained address", "address_components": []}
            ],
        }

    def post_json(self, *args, **kwargs):
        self.posts += 1
        raise GeoTransientError(
            "provider HTTP 503", request_count=1, safe_to_retry=True
        )


def test_later_unknown_attempt_does_not_revoke_successful_address():
    transport = FailingNearbyTransport()
    provider = GoogleMapsReverseGeocoder(
        "synthetic", transport=transport, minimum_interval=0
    )
    capability = GeoCapability(
        {provider.provider_id: provider},
        OrderedGeoRoutingPolicy((provider.provider_id,)),
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("synthetic", GeoCoordinate(35.0, 139.0)),),
        "en",
        radius_meters=500.0,
        max_places=10,
    )
    authority = GeoAuthorization(
        "human:synthetic",
        capability.fingerprint(request),
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )
    result = capability.invoke(request, authorization=authority)
    address = next(
        c for c in result.components if c.operation is GeoOperation.REVERSE_GEOCODE
    )
    assert address.status.value == "success"
    assert address.candidates[0].formatted_address == "Retained address"
    assert any(a.status.value in {"failed", "indeterminate"} for a in result.attempts)


def test_recovery_only_queries_missing_component_and_preserves_unknown_cost(tmp_path):
    from mediasense.capabilities.geo import (
        GeoQueryTool,
        GeoOperationJournal,
        GeoEffectEnvelope,
    )
    from mediasense.capabilities.geo.tool import result_digest

    class Transport(FailingNearbyTransport):
        recovered = False

        def post_json(self, *args, **kwargs):
            self.posts += 1
            if not self.recovered:
                raise GeoTransientError("response lost", request_count=1)
            return {"places": [{"displayName": {"text": "Recovered place"}}]}

    transport = Transport()
    provider = GoogleMapsReverseGeocoder(
        "synthetic", transport=transport, minimum_interval=0
    )
    capability = GeoCapability(
        {provider.provider_id: provider},
        OrderedGeoRoutingPolicy((provider.provider_id,)),
    )
    journal = GeoOperationJournal(tmp_path / "geo.sqlite3")
    tool = GeoQueryTool(capability, journal)
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("synthetic", GeoCoordinate(35.0, 139.0)),),
        "en",
        radius_meters=500.0,
        max_places=10,
    )
    public = {"request_id": "request:original", **request.value()}
    authority = GeoAuthorization(
        "human:synthetic",
        capability.fingerprint(request),
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )
    first = tool.handle(public, authorization=authority)
    assert first["outcome"] == "indeterminate"
    assert len(journal.executions(public["request_id"])) == 2
    assert transport.gets == transport.posts == 1
    transport.recovered = True
    recovery = {
        **public,
        "request_id": "request:recovery",
        "recovery": {
            "prior_request_id": public["request_id"],
            "result_digest": result_digest(first),
        },
    }
    proposal = tool.handle(recovery)
    assert proposal["outcome"] == "authorization_required"
    auth = GeoAuthorization(
        "human:synthetic",
        proposal["request_fingerprint"],
        datetime.now(timezone.utc),
        GeoEffectEnvelope(**proposal["required_authorization"]),
    )
    second = tool.handle(recovery, authorization=auth)
    assert second["outcome"] == "success"
    assert second["effects"]["provider_requests"] == 3
    assert second["effects"]["billable_units"] is None
    assert len(second["attempts"]) == 3
    assert second["attempts"][1]["status"] == "indeterminate"
    assert (
        second["components"][0]["observed_at"] == first["components"][0]["observed_at"]
    )
    assert second["attempts"][0]["execution_request_id"] == public["request_id"]
    assert second["attempts"][2]["execution_request_id"] == recovery["request_id"]
    assert transport.gets == 1 and transport.posts == 2
    assert tool.handle(public) == first
    assert tool.handle(recovery) == second
    assert transport.gets == 1 and transport.posts == 2
    conflict = tool.handle(
        {**recovery, "request_id": "request:duplicate-recovery"}, authorization=auth
    )
    assert conflict["error"]["code"] == "recovery_stale"


def test_reservations_survive_crash_and_share_budget_across_cycles(tmp_path):
    from mediasense.capabilities.geo import GeoOperationJournal
    from mediasense.capabilities.geo.journal import GeoBudgetExhausted
    import pytest

    journal = GeoOperationJournal(tmp_path / "geo.sqlite3")
    execution = {"request": {"scope": "same"}, "authority": {}, "max_requests": 2}
    journal.admit(
        request_id="root",
        request_fingerprint="fingerprint",
        authorization_binding="binding",
        indeterminate_result={},
        execution=execution,
    )
    descriptor = {"provider": "synthetic", "operation": "reverse_geocode"}
    journal.reserve("root", descriptor=descriptor, requests=1, billable_units=None)
    journal.complete("root", {"unknown": True})
    journal.admit(
        request_id="next",
        request_fingerprint="next",
        authorization_binding="recovery-binding",
        indeterminate_result={},
        execution={**execution, "root_request_id": "root", "prior_request_id": "root"},
    )
    journal.reserve("next", descriptor=descriptor, requests=1, billable_units=None)
    with pytest.raises(GeoBudgetExhausted):
        journal.reserve("next", descriptor=descriptor, requests=1, billable_units=None)
    reopened = GeoOperationJournal(tmp_path / "geo.sqlite3")
    assert reopened.executions("root")[0]["execution_json"] is None
    with pytest.raises(GeoBudgetExhausted):
        reopened.reserve("next", descriptor=descriptor, requests=1, billable_units=None)


def test_precheck_recovery_confirmation_and_projection_replay(tmp_path, monkeypatch):
    from test_geocode import _closed_run, _coordinate_work, _public_run, _authorize
    from mediasense.precheck import (
        AccountingStore,
        PrecheckRunTool,
        ReverseGeocodeProducer,
    )
    from mediasense.capabilities.geo import GeoQueryTool, GeoOperationJournal
    import pytest

    class Transport(FailingNearbyTransport):
        recovered = False

        def get_json(self, *args, **kwargs):
            self.gets += 1
            return {
                "status": "OK",
                "results": [{"formatted_address": "Saved", "address_components": []}],
            }

        def post_json(self, *args, **kwargs):
            self.posts += 1
            if self.posts == 2 and not self.recovered:
                raise GeoTransientError("response lost", request_count=1)
            return {"places": [{"displayName": {"text": "Place"}}]}

    database = tmp_path / "work.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg", "c.jpg"))
    metadata = [
        _coordinate_work(database, run_id, name, latitude=35.0 + i, longitude=139.0)
        for i, name in enumerate(("a.jpg", "b.jpg", "c.jpg"))
    ]
    run = PrecheckRunTool(database)
    run_ref = _public_run(run, "request:precheck-recovery")
    transport = Transport()
    provider = GoogleMapsReverseGeocoder(
        "synthetic", transport=transport, minimum_interval=0
    )
    geo = GeoQueryTool(
        GeoCapability(
            {provider.provider_id: provider},
            OrderedGeoRoutingPolicy((provider.provider_id,)),
        ),
        GeoOperationJournal(tmp_path / "geo.sqlite3"),
    )
    producer = ReverseGeocodeProducer(database, run, geo)

    def produce():
        return producer.produce(run_ref, run_id, [m.work_id for m in metadata])

    assert produce().status == "confirmation_required"
    _authorize(run, run_ref)
    first = produce()
    assert first.status == "indeterminate"
    assert transport.gets == transport.posts == 2
    original = [r.work for r in first.outcomes]
    assert produce().status == "confirmation_required"
    from mediasense.runtime.resources import contract_validator

    status = run.run(
        {"action": "status", "dataset_ref": "dataset:dataset-a", "run_ref": run_ref}
    )
    contract_validator("mediasense.precheck.run", "status").validate(status)
    disclosure = status["confirmation"]["disclosure"]
    assert disclosure["pending_logical_queries"] == 2
    assert disclosure["original_logical_queries"] == 3
    assert disclosure["recovery_accounting"]["prior_provider_requests"] == 4
    assert transport.gets == transport.posts == 2
    _authorize(run, run_ref)
    transport.recovered = True
    with monkeypatch.context() as crash:

        def fail(*args, **kwargs):
            raise RuntimeError("synthetic projection crash")

        crash.setattr(producer, "_persist_response", fail)
        with pytest.raises(RuntimeError, match="synthetic projection crash"):
            produce()
    assert transport.gets == 3 and transport.posts == 4
    recovered = produce()
    assert recovered.status == "completed"
    assert transport.gets == 3 and transport.posts == 4
    assert all(
        r.work.output["result"]["status"] == "success" for r in recovered.outcomes
    )
    assert recovered.outcomes[0].work.work_id == original[0].work_id
    assert producer.work.get_work(original[1].work_id).output == original[1].output
    from mediasense.precheck._result_assembly import _external_effect_boundary
    import json

    rows = [
        {"work_id": o.work.work_id, "output_json": json.dumps(o.work.output)}
        for o in recovered.outcomes
    ]
    audit = _external_effect_boundary(rows, {}, run_id, {run_ref})["audit"]
    assert audit["current_provider_requests"] == 7
    assert audit["historical_provider_requests"] == 0
    assert audit["billable_calls"] is None
    assert len(audit["attempts"]) == 7
    from mediasense.precheck._result_sqlite import _validate_execution_boundary

    boundary = _external_effect_boundary(rows, {}, run_id, {run_ref})
    _validate_execution_boundary(boundary)
    assert produce().status == "completed"
    assert transport.gets == 3 and transport.posts == 4


def test_crashed_reservation_is_reconciled_without_sending_and_budget_is_retained(
    tmp_path,
):
    from mediasense.capabilities.geo import (
        GeoQueryTool,
        GeoOperationJournal,
        GeoEffectEnvelope,
    )
    from mediasense.capabilities.geo.tool import result_digest
    import pytest

    class Transport(FailingNearbyTransport):
        crashed = False

        def post_json(self, *args, **kwargs):
            self.posts += 1
            if not self.crashed:
                self.crashed = True
                raise RuntimeError("synthetic process interruption after send")
            return {"places": [{"displayName": {"text": "Recovered"}}]}

    transport = Transport()
    provider = GoogleMapsReverseGeocoder(
        "synthetic", transport=transport, minimum_interval=0
    )
    capability = GeoCapability(
        {provider.provider_id: provider},
        OrderedGeoRoutingPolicy((provider.provider_id,)),
    )
    journal = GeoOperationJournal(tmp_path / "geo.sqlite3")
    tool = GeoQueryTool(capability, journal)
    value = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("synthetic", GeoCoordinate(35.0, 139.0)),),
        "en",
        radius_meters=500.0,
        max_places=10,
    )
    request = {"request_id": "request:crash", **value.value()}
    auth = GeoAuthorization(
        "human:test",
        capability.fingerprint(value),
        datetime.now(timezone.utc),
        capability.proposed_envelope(value),
    )
    with pytest.raises(RuntimeError, match="synthetic process"):
        tool.handle(request, authorization=auth)
    assert transport.gets == transport.posts == 1
    with journal.ownership(request["request_id"]) as owned:
        assert owned
        assert tool.handle(request)["error"]["code"] == "execution_in_progress"
    reconciled = tool.handle(request)
    assert reconciled["components"][0]["status"] == "success"
    assert reconciled["effects"]["provider_requests"] is None
    assert reconciled["effects"]["provider_requests_upper_bound"] == 2
    assert reconciled["attempts"][1]["request_count_kind"] == "reserved_upper_bound"
    assert reconciled["attempts"][1]["provider_coordinate"] is None
    assert transport.gets == transport.posts == 1
    assert tool.handle(request) == reconciled
    recovery = {
        **request,
        "request_id": "request:after-crash",
        "recovery": {
            "prior_request_id": request["request_id"],
            "result_digest": result_digest(reconciled),
        },
    }
    proposal = tool.handle(recovery)
    auth = GeoAuthorization(
        "human:test",
        proposal["request_fingerprint"],
        datetime.now(timezone.utc),
        GeoEffectEnvelope(**proposal["required_authorization"]),
    )
    response = tool.handle(recovery, authorization=auth)
    assert response["outcome"] == "success"
    assert response["effects"]["provider_requests"] is None
    assert response["effects"]["provider_requests_upper_bound"] == 3
    assert response["effects"]["billable_units"] is None
    assert transport.gets == 1 and transport.posts == 2
    assert tool.handle(request) == reconciled


def test_new_journal_guards_against_already_open_legacy_writer(tmp_path):
    import sqlite3
    import pytest
    from mediasense.capabilities.geo import GeoOperationJournal

    database = tmp_path / "geo.sqlite3"
    # A 0.9 connection can predate migration; constructor checks alone do not protect it.
    legacy = sqlite3.connect(database)
    journal = GeoOperationJournal(database)
    with pytest.raises(sqlite3.OperationalError, match="mediasense_geo_schema_version"):
        legacy.execute(
            "INSERT INTO geo_operation_journal VALUES ('old', 'fingerprint', 'binding', 'indeterminate', '{}')"
        )
    legacy.close()
    assert journal.get("old") is None


def test_provider_outage_stops_before_later_locations_but_point_failure_continues(
    tmp_path,
):
    from dataclasses import replace
    from test_precheck_simplification_edges import configured

    clock, provider, capability, request, authority, tool = configured(
        tmp_path, ["transient"]
    )
    request = replace(
        request,
        subjects=(
            request.subjects[0],
            GeoSubject("second", GeoCoordinate(35.0, 139.0)),
        ),
    )
    authority = replace(
        authority,
        request_fingerprint=capability.fingerprint(request),
        envelope=capability.proposed_envelope(request),
    )
    response = tool.handle(
        {"request_id": "request:outage", **request.value()}, authorization=authority
    )
    assert response["outcome"] == "blocked"
    assert provider.calls == 3
    assert response["components"][1]["status"] == "not_requested"
    provider.script = ["permanent", "success"]
    provider.calls = 0
    authority = replace(authority, authorized_at=datetime.now(timezone.utc))
    response = tool.handle(
        {"request_id": "request:point-failure", **request.value()},
        authorization=authority,
    )
    assert response["outcome"] == "partial"
    assert provider.calls == 2
    assert [c["status"] for c in response["components"]] == ["failed", "success"]


def test_changing_request_id_cannot_reuse_a_consumed_authorization(tmp_path):
    from test_precheck_simplification_edges import configured

    _, provider, _, value, auth, tool = configured(tmp_path, ["success"])
    original = tool.handle(
        {"request_id": "request:grant-owner", **value.value()}, authorization=auth
    )
    assert original["outcome"] == "success"
    duplicate = tool.handle(
        {"request_id": "request:another-id", **value.value()}, authorization=auth
    )
    assert duplicate["error"]["code"] == "idempotency_conflict"
    assert provider.calls == 1


def test_legacy_114_reuse_54_batch_recovers_23_requests_and_delivers_read(tmp_path):
    """Reproduce the reported 0.9 accounting shape, entirely with synthetic media."""
    import hashlib
    import json
    from pathlib import Path
    from PIL import Image
    from test_geocode import _closed_run, _coordinate_work, _public_run, _authorize
    from mediasense.precheck import (
        AccountingStore,
        PrecheckRunTool,
        ReverseGeocodeProducer,
        ImageRenditionProducer,
        ResultStore,
        PrecheckReadTool,
    )
    from mediasense.capabilities.geo import GeoQueryTool, GeoOperationJournal
    from mediasense.capabilities.geo.routing import RegionalGeoRoutingPolicy
    from mediasense.geo import AMapReverseGeocoder

    class LegacyCapability(GeoCapability):
        def fingerprint(self, value):
            return (
                "sha256:"
                + hashlib.sha256(
                    json.dumps(
                        {
                            "request": value.fingerprint(),
                            "retry_policy": self.retry_policy.value(),
                        },
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest()
            )

    class Transport:
        gets = posts = 0
        recovered = False

        def get_json(self, url, **kwargs):
            assert "amap.com" not in url
            self.gets += 1
            return {
                "status": "OK",
                "results": [
                    {
                        "formatted_address": "Synthetic Hong Kong address",
                        "address_components": [],
                    }
                ],
            }

        def post_json(self, url, **kwargs):
            self.posts += 1
            if self.posts == 157 and not self.recovered:
                raise GeoTransientError(
                    "Legacy unclassified transport failure", request_count=1
                )
            return {"places": [{"displayName": {"text": "Synthetic place"}}]}

    class LegacyTool(GeoQueryTool):
        def _execute(self, request_id, provider, operation, coordinate, **kwargs):
            return provider.execute(operation, coordinate, **kwargs)

    class LegacyJournal(GeoOperationJournal):
        def admit(self, **kwargs):
            kwargs.pop("execution", None)
            return super().admit(**kwargs)

    database = tmp_path / "work.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    names = tuple(f"item-{i:03}.jpg" for i in range(168))
    old_run_id = _closed_run(tmp_path, database, accounting, names[:114])
    old_metadata = [
        _coordinate_work(
            database,
            old_run_id,
            name,
            latitude=22.29 + i * 0.0001,
            longitude=114.15 + i * 0.0001,
        )
        for i, name in enumerate(names[:114])
    ]
    run = PrecheckRunTool(database)
    old_ref = _public_run(run, "request:114-historical")
    transport = Transport()
    providers = {
        "google_maps": GoogleMapsReverseGeocoder(
            "synthetic", transport=transport, minimum_interval=0
        ),
        "amap": AMapReverseGeocoder(
            "synthetic", transport=transport, minimum_interval=0
        ),
    }
    path = tmp_path / "geo.sqlite3"
    legacy = LegacyTool(
        LegacyCapability(providers, OrderedGeoRoutingPolicy(("google_maps", "amap"))),
        LegacyJournal(path),
    )
    producer = ReverseGeocodeProducer(database, run, legacy)
    assert (
        producer.produce(old_ref, old_run_id, [m.work_id for m in old_metadata]).status
        == "confirmation_required"
    )
    _authorize(run, old_ref)
    historical = producer.produce(
        old_ref, old_run_id, [m.work_id for m in old_metadata]
    )
    assert historical.status == "completed" and transport.gets == transport.posts == 114
    renditions = ImageRenditionProducer(database)
    old_evidence = [
        renditions.produce(old_run_id, Path(name)).work.work_id for name in names[:114]
    ]
    store = ResultStore(database)
    old_sealed = store.seal(
        store.build_minimal(
            old_run_id,
            old_evidence,
            metadata_work_ids=[m.work_id for m in old_metadata],
            reverse_geocode_work_by_source=historical.work_by_source(),
        )
    )
    old_bytes = old_sealed.path.read_bytes()
    run.run(
        {"action": "cancel", "dataset_ref": "dataset:dataset-a", "run_ref": old_ref}
    )
    for name in names[114:]:
        Image.new("RGB", (40, 30), "blue").save(tmp_path / "source" / name)
    current_id = _closed_run(tmp_path, database, accounting, names)
    metadata = [
        _coordinate_work(
            database,
            current_id,
            name,
            latitude=22.29 + i * 0.0001,
            longitude=114.15 + i * 0.0001,
        )
        for i, name in enumerate(names)
    ]
    current_ref = _public_run(run, "request:54-current")
    pending = producer.produce(current_ref, current_id, [m.work_id for m in metadata])
    assert (
        pending.status == "confirmation_required"
        and pending.batch.pending_query_count == 54
    )
    _authorize(run, current_ref)
    interrupted = producer.produce(
        current_ref, current_id, [m.work_id for m in metadata]
    )
    assert interrupted.status == "indeterminate"
    assert transport.gets == transport.posts == 157  # historical 228 + current 86
    original_work = {o.work.work_id: o.work.output_digest for o in interrupted.outcomes}
    proof = next(
        o.work.output
        for o in interrupted.outcomes
        if o.work.output.get("result", {}).get("status") == "indeterminate"
    )
    original_request = proof["geo_request_id"]
    original_response = legacy.journal.get(original_request).result
    assert original_response["effects"]["provider_requests"] == 86
    assert legacy.journal.cycle(original_request) is None

    geo = GeoQueryTool(
        GeoCapability(providers, RegionalGeoRoutingPolicy()), GeoOperationJournal(path)
    )
    producer = ReverseGeocodeProducer(database, run, geo)
    assert (
        producer.produce(current_ref, current_id, [m.work_id for m in metadata]).status
        == "confirmation_required"
    )
    assert geo.journal.cycle(original_request)["max_requests"] == 486
    _authorize(run, current_ref)
    transport.recovered = True
    recovered = producer.produce(current_ref, current_id, [m.work_id for m in metadata])
    assert recovered.status == "completed"
    assert transport.gets == 168 and transport.posts == 169
    assert (transport.gets + transport.posts) - (157 * 2) == 23
    assert (
        geo.journal.latest(original_request).result["effects"]["provider_requests"]
        == 109
    )
    assert (
        geo.journal.latest(original_request).result["effects"]["billable_units"] is None
    )
    assert geo.journal.get(original_request).result == original_response
    for work_id, digest in original_work.items():
        assert producer.work.get_work(work_id).output_digest == digest
    assert old_sealed.path.read_bytes() == old_bytes
    evidence = [
        renditions.produce(current_id, Path(name)).work.work_id for name in names
    ]
    sealed = store.seal(
        store.build_minimal(
            current_id,
            evidence,
            metadata_work_ids=[m.work_id for m in metadata],
            reverse_geocode_work_by_source=recovered.work_by_source(),
        )
    )
    read = PrecheckReadTool(database).read(
        {
            "action": "review",
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "include": ["execution_boundary"],
            "page": {"limit": 1},
        }
    )
    assert "error" not in read
    assert read["execution_boundary"]["current_provider_requests"] == 109
    assert read["execution_boundary"]["historical_provider_requests"] == 228
    assert read["execution_boundary"]["billable_calls"] is None
    assert read["result"]["readiness"] == "plan_ready"


def test_checkpoint_does_not_turn_resolved_old_transient_into_a_new_global_block(
    tmp_path, monkeypatch
):
    from dataclasses import replace
    from test_precheck_simplification_edges import configured
    import pytest

    _, provider, capability, value, authority, tool = configured(
        tmp_path, ["transient", "success", "permanent"]
    )
    value = replace(
        value,
        subjects=(*value.subjects, GeoSubject("second", GeoCoordinate(35.0, 139.0))),
    )
    authority = replace(
        authority,
        request_fingerprint=capability.fingerprint(value),
        envelope=capability.proposed_envelope(value),
    )
    request = {"request_id": "request:resolved-transient", **value.value()}
    with monkeypatch.context() as crash:

        def fail(*args):
            raise RuntimeError("synthetic completion interruption")

        crash.setattr(tool.journal, "complete", fail)
        with pytest.raises(RuntimeError, match="synthetic completion"):
            tool.handle(request, authorization=authority)
    result = tool.handle(request)
    assert result["outcome"] == "partial"
    assert [c["status"] for c in result["components"]] == ["success", "failed"]
    assert provider.calls == 3
