from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCandidate,
    GeoCandidateKind,
    GeoComponentResult,
    GeoComponentStatus,
    GeoCoordinate,
    GeoOperation,
    GeoOperationJournal,
    GeoProviderAttempt,
    GeoProviderCapabilities,
    GeoProviderExecution,
    GeoQueryTool,
    GeoRequest,
    GeoSubject,
    MapDatum,
    OrderedGeoRoutingPolicy,
)
from mediasense.capabilities.geo.model import RetryPolicy
from mediasense.capabilities.geo.service import GeoCapability
from mediasense.precheck.geocode import normalize_geo_observations


class Clock:
    now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class ScriptedProvider:
    capabilities = GeoProviderCapabilities(
        "fake",
        (GeoOperation.REVERSE_GEOCODE,),
        MapDatum.WGS84,
        max_billable_units_per_operation=1,
    )

    def __init__(self, script, clock):
        self.script = script
        self.clock = clock
        self.calls = 0
        self.elapsed_per_call = 0

    def execute(
        self,
        operation,
        coordinate,
        *,
        locale,
        radius_meters=None,
        max_places=None,
        deadline=None,
        cancelled=None,
    ):
        assert deadline > self.clock()
        assert not (cancelled and cancelled())
        token = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        self.clock.now += self.elapsed_per_call
        status = (
            GeoComponentStatus.FAILED
            if token in {"transient", "permanent"}
            else GeoComponentStatus(token)
        )
        candidates = (
            (
                GeoCandidate(
                    GeoCandidateKind.ADDRESS, "Synthetic", formatted_address="Synthetic"
                ),
            )
            if token == "success"
            else ()
        )
        return GeoProviderExecution(
            GeoComponentResult(operation, status, (), coordinate, candidates),
            GeoProviderAttempt(
                "fake",
                operation,
                status,
                coordinate,
                coordinate,
                1,
                1,
                token if status is GeoComponentStatus.FAILED else None,
            ),
        )


def configured(tmp_path, script):
    clock = Clock()
    provider = ScriptedProvider(script, clock)
    capability = GeoCapability(
        {"fake": provider},
        OrderedGeoRoutingPolicy(("fake",)),
        monotonic=clock,
        sleeper=clock.sleep,
    )
    request = GeoRequest(
        GeoOperation.REVERSE_GEOCODE,
        (GeoSubject("synthetic", GeoCoordinate(22.3, 114.1)),),
        "zh",
    )
    authorization = GeoAuthorization(
        "human:synthetic",
        capability.fingerprint(request),
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )
    tool = GeoQueryTool(capability, GeoOperationJournal(tmp_path / "journal.sqlite3"))
    return clock, provider, capability, request, authorization, tool


@pytest.mark.parametrize(
    "script,outcome,calls,delay",
    [
        (["transient", "transient", "success"], "success", 3, 4),
        (["transient"], "failed", 3, 4),
        (["permanent"], "failed", 1, 0),
        (["no_result"], "no_result", 1, 0),
        (["indeterminate"], "indeterminate", 1, 0),
    ],
)
def test_geo_retry_is_finite_accounted_and_replay_only(
    tmp_path, script, outcome, calls, delay
):
    clock, provider, capability, request, authorization, tool = configured(
        tmp_path, script
    )
    assert capability.proposed_envelope(request).max_provider_requests == 3
    assert capability.proposed_envelope(request).max_billable_units == 3
    public = {"request_id": "request:retry", **request.value()}
    result = tool.handle(public, authorization=authorization)
    assert result["outcome"] == outcome
    assert provider.calls == calls
    assert clock.now == pytest.approx(delay)
    assert (
        result["effects"]["provider_requests"]
        == result["effects"]["billable_units"]
        == calls
    )
    assert len(result["attempts"]) == calls
    assert tool.handle(public) == result
    assert provider.calls == calls


def test_retry_respects_smaller_authority_and_effective_profile(tmp_path):
    _, provider, capability, request, authorization, tool = configured(
        tmp_path, ["transient"]
    )
    authorization = replace(
        authorization,
        envelope=replace(
            authorization.envelope, max_provider_requests=1, max_billable_units=1
        ),
    )
    public = {"request_id": "request:small", **request.value()}
    result = tool.handle(public, authorization=authorization)
    assert result["outcome"] == "failed"
    assert provider.calls == 1
    changed = GeoQueryTool(
        GeoCapability(
            {"fake": provider},
            capability.routing,
            retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=()),
        ),
        tool.journal,
    )
    assert changed.handle(public)["error"]["code"] == "idempotency_conflict"
    assert provider.calls == 1


def test_retry_deadline_and_cancellation_stop_new_effects(tmp_path):
    clock, provider, capability, request, authorization, _ = configured(
        tmp_path, ["transient"]
    )
    provider.elapsed_per_call = 119.5
    result = capability.invoke(request, authorization=authorization)
    assert provider.calls == 1
    assert clock.now == pytest.approx(120)
    assert result.outcome.value == "failed"
    clock.now = 0
    provider.calls = 0
    provider.elapsed_per_call = 0
    result = capability.invoke(
        request, authorization=authorization, cancelled=lambda: provider.calls > 0
    )
    assert result.outcome.value == "cancelled"
    assert provider.calls == 1


@pytest.mark.parametrize(
    "outcome,status",
    [
        ("no_result", "missing"),
        ("failed", "failed"),
        ("not_requested", "not_checked"),
        ("indeterminate", "failed"),
    ],
)
def test_fresh_and_v3_components_have_no_illegal_values(outcome, status):
    output = {
        "producer": {"identity": "builtin-geo-query-address-poi-v3"},
        "result": {
            "component_outcomes": {
                "reverse_geocode": outcome,
                "nearby_places": outcome,
            },
            "location": None,
            "pois": [],
        },
        "observations": [
            {
                "name": "reverse_geocode_candidate",
                "status": "missing",
                "value": {
                    "component_outcomes": {
                        "reverse_geocode": outcome,
                        "nearby_places": outcome,
                    }
                },
            }
        ],
    }
    observations = normalize_geo_observations(output)
    assert {item["name"] for item in observations} == {
        "address_candidate",
        "nearby_place_candidates",
    }
    assert all(
        item["status"] == status and "value" not in item and item["basis"]
        for item in observations
    )
    assert output["observations"][0]["value"]


def test_legacy_guessed_outcomes_are_not_independent_proof():
    output = {
        "producer": {
            "identity": "builtin-geo-query-address-poi-v3",
            "reused_from": "builtin-adaptive-reverse-geocode-v1",
        },
        "result": {
            "component_outcomes": {
                "reverse_geocode": "no_result",
                "nearby_places": "no_result",
            },
            "provider_request_count": 2,
            "location": None,
            "pois": [],
        },
    }
    assert all(
        item["status"] == "not_checked"
        and item["basis"]["code"] == "historical_geo_unrecorded"
        for item in normalize_geo_observations(output)
    )
    assert all(
        item["status"] == "not_applicable"
        for item in normalize_geo_observations(None, coordinate_available=False)
    )


@pytest.mark.parametrize(
    "response,status",
    [
        ({"status": "1", "regeocode": {}}, "missing"),
        ({"status": "0", "infocode": "10001", "info": "denied"}, "failed"),
    ],
)
def test_whole_batch_without_provider_location_seals_and_enters_plan(
    tmp_path, response, status
):
    from pathlib import Path
    from test_geocode import (
        FakeTransport,
        IdentityConverter,
        _closed_run,
        _coordinate_work,
        _public_run,
        _authorize,
    )
    from mediasense.geo import AMapReverseGeocoder
    from mediasense.precheck import (
        AccountingStore,
        PrecheckRunTool,
        ImageRenditionProducer,
        ResultStore,
        PrecheckReadTool,
    )
    from mediasense.precheck.geocode import ReverseGeocodeProducer
    from mediasense.precheck.read import bind_precheck_read
    from mediasense.plan import PlanWorkTool

    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    metadata = [
        _coordinate_work(database, run_id, name, latitude=22.3, longitude=114.1)
        for name in ("a.jpg", "b.jpg")
    ]
    transport = FakeTransport(get_response=response)
    provider = AMapReverseGeocoder(
        "synthetic",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
    )
    geo = GeoQueryTool(
        GeoCapability({"amap": provider}, OrderedGeoRoutingPolicy(("amap",))),
        GeoOperationJournal(tmp_path / "geo.sqlite3"),
    )
    run = PrecheckRunTool(database)
    run_ref = _public_run(run, "request:place-gap")
    producer = ReverseGeocodeProducer(database, run, geo)
    pending = producer.produce(run_ref, run_id, [item.work_id for item in metadata])
    assert pending.status == "confirmation_required"
    assert not transport.gets
    _authorize(run, run_ref)
    completed = producer.produce(run_ref, run_id, [item.work_id for item in metadata])
    assert completed.status == "completed"
    assert len(transport.gets) == 1

    renditions = [
        ImageRenditionProducer(database).produce(run_id, Path(name))
        for name in ("a.jpg", "b.jpg")
    ]
    store = ResultStore(database)
    draft = store.build_minimal(
        run_id,
        [item.work.work_id for item in renditions],
        metadata_work_ids=[item.work_id for item in metadata],
        reverse_geocode_work_by_source=completed.work_by_source(),
    )
    sealed = store.seal(draft)
    original = sealed.path.read_bytes()
    reader = bind_precheck_read(PrecheckReadTool(database), "dataset:dataset-a")
    review = reader.read(
        {
            "action": "review",
            "result_ref": sealed.result_ref,
            "include": ["execution_boundary"],
        }
    )
    assert review["result"]["coverage"] == "complete"
    assert review["result"]["readiness"] == "plan_ready"
    assert review["execution_boundary"]["current_provider_requests"] == 1
    for item in draft.sources:
        expanded = reader.read(
            {
                "action": "expand",
                "result_ref": sealed.result_ref,
                "source_item_refs": [item.ref],
                "include": ["observations"],
            }
        )
        components = [
            value
            for value in expanded["items"][0]["included"]["observations"]
            if value["name"] in {"address_candidate", "nearby_place_candidates"}
        ]
        assert len(components) == 2
        assert all(
            value["status"] == status and "value" not in value for value in components
        )
    summary = reader.read({"action": "geo_summary", "result_ref": sealed.result_ref})
    assert summary["acquisition_status"] == "complete"
    assert summary["coordinate_groups"][0]["candidate_evidence_refs"] == []
    created = PlanWorkTool(tmp_path / "plan", reader).handle(
        {
            "action": "create",
            "request_id": "request:gap-plan",
            "result_ref": sealed.result_ref,
        }
    )
    assert created["outcome"] == "ok", created
    assert sealed.path.read_bytes() == original
    assert (
        producer.produce(
            run_ref, run_id, [item.work_id for item in metadata]
        ).actual_provider_requests
        == 0
    )
    assert len(transport.gets) == 1


def test_diagnostics_pages_bind_content_but_not_heartbeats(tmp_path):
    from datetime import timedelta
    from test_geocode import _closed_run, _public_run
    from mediasense.precheck import AccountingStore, PrecheckRunTool
    from mediasense.precheck.work import (
        WorkStore,
        WorkSpec,
        WorkDependency,
        DependencyKind,
    )

    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    tool = PrecheckRunTool(database)
    run_ref = _public_run(tool, "request:diagnostics")
    tool.bind_working_run(run_ref, run_id)
    work = WorkStore(database)

    def failed(index):
        record = work.ensure_work(
            run_id,
            WorkSpec(
                "image-rendition",
                "synthetic-failure",
                (WorkDependency(DependencyKind.PARAMETER, "case", str(index)),),
            ),
        )
        lease = work.claim_ready_work(
            run_id, "test", work_id=record.work_id, lease_duration=timedelta(minutes=1)
        )[0]
        work.fail_work(
            lease,
            error_code=f"failure_{index}",
            message="Synthetic terminal failure",
            retryable=False,
        )

    for index in range(7):
        failed(index)
    tool.record_phase(run_ref, "renditions", total=7)
    base = {"action": "status", "dataset_ref": "dataset:dataset-a", "run_ref": run_ref}
    status = tool.run(base)
    assert status["issues_truncated"] is True and len(status["issues"]) == 5
    assert status["progress"]["processed"] == status["progress"]["total"] == 7
    page = tool.run({**base, "include": ["diagnostics"], "page": {"limit": 2}})
    cursor = page["diagnostics"]["page"]["next_cursor"]
    assert page["diagnostics"]["page"]["total"] == 7
    tool._store.claim_execution_worker(
        run_ref, "synthetic-owner", stale_after=timedelta(seconds=120)
    )
    tool._store.heartbeat_execution_worker(run_ref, "synthetic-owner")
    continued = tool.run(
        {**base, "include": ["diagnostics"], "page": {"limit": 2, "cursor": cursor}}
    )
    assert "error" not in continued
    failed(8)
    stale = tool.run(
        {**base, "include": ["diagnostics"], "page": {"limit": 2, "cursor": cursor}}
    )
    assert stale["error"]["code"] == "invalid_cursor"
    assert tool.run(base)["reason"]["code"] == "progress_scope_changed"


def test_mutable_v3_missing_value_normalizes_without_rewriting_old_work(tmp_path):
    import json
    from pathlib import Path
    from datetime import timedelta
    from test_geocode import _closed_run, _coordinate_work
    from mediasense.precheck import (
        AccountingStore,
        PrecheckRunTool,
        ResultStore,
        ImageRenditionProducer,
        PrecheckReadTool,
    )
    from mediasense.precheck.work import WorkStore
    from mediasense.precheck.geocode import (
        FrozenGeocodeQuery,
        ReverseGeocodeProfile,
        ReverseGeocodeProducer,
        _spec,
    )

    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=22.3, longitude=114.1
    )
    coordinate = GeoCoordinate(22.3, 114.1)
    query = FrozenGeocodeQuery(coordinate, (Path("a.jpg"),), (metadata.work_id,))
    profile = ReverseGeocodeProfile()
    work = WorkStore(database)
    old = work.ensure_work(
        run_id,
        replace(
            _spec(query, profile), producer_identity="builtin-geo-query-address-poi-v3"
        ),
    )
    lease = work.claim_ready_work(
        run_id, "fixture", work_id=old.work_id, lease_duration=timedelta(minutes=1)
    )[0]
    components = {"reverse_geocode": "no_result", "nearby_places": "no_result"}
    identity = "sha256:" + "a" * 64
    old = work.succeed_work(
        lease,
        {
            "producer": {
                "identity": "builtin-geo-query-address-poi-v3",
                "profile": profile.descriptor(),
            },
            "query": coordinate.value(),
            "observations": [
                {
                    "name": "reverse_geocode_candidate",
                    "status": "missing",
                    "value": {
                        "address": None,
                        "pois": [],
                        "component_outcomes": components,
                    },
                }
            ],
            "result": {
                "component_outcomes": components,
                "location": None,
                "pois": [],
                "status": "no_result",
                "input_coordinate": coordinate.value(),
                "provider_coordinate": coordinate.value(),
                "provider": "fake",
                "providers": ["fake"],
                "provider_request_count": 1,
                "observed_at": "2026-09-01T00:00:00+00:00",
                "attempts": [
                    {
                        "provider": "fake",
                        "operation": "resolve_place",
                        "status": "no_result",
                        "provider_requests": 1,
                        "billable_units": 0,
                    }
                ],
            },
            "authorization": {
                "decision": "proceed",
                "run_ref": "precheck-run:historical",
                "pending_fingerprint": identity,
                "confirmed_content_identity": identity,
                "principal_ref": "human:historical",
                "confirmed_at": "2026-09-01T00:00:00+00:00",
                "confirmed_logical_queries": 1,
            },
        },
    )
    original = json.dumps(old.output, sort_keys=True)
    producer = ReverseGeocodeProducer(database, PrecheckRunTool(database))
    batch = producer.freeze(run_id, [metadata.work_id])
    assert batch.pending_query_count == 0
    replacement = batch.work[0]
    assert replacement.work_id != old.work_id
    assert replacement.spec.producer_identity == "builtin-geo-component-observations-v4"
    assert all(
        item["status"] == "missing" and "value" not in item
        for item in replacement.output["observations"]
    )
    assert json.dumps(work.get_work(old.work_id).output, sort_keys=True) == original
    assert work.get_work(old.work_id).output_digest == old.output_digest
    rendition = ImageRenditionProducer(database).produce(run_id, Path("a.jpg"))
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(
            run_id,
            [rendition.work.work_id],
            metadata_work_ids=[metadata.work_id],
            reverse_geocode_work_by_source={Path("a.jpg"): replacement.work_id},
        )
    )
    before = sealed.path.read_bytes()
    reviewed = PrecheckReadTool(database).read(
        {
            "action": "review",
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "include": ["execution_boundary"],
        }
    )
    assert reviewed["result"]["readiness"] == "plan_ready"
    assert reviewed["execution_boundary"]["current_provider_requests"] == 0
    assert reviewed["execution_boundary"]["historical_provider_requests"] == 1
    assert (
        reviewed["execution_boundary"]["attempts"][0]["observed_at"]
        == "2026-09-01T00:00:00+00:00"
    )
    assert sealed.path.read_bytes() == before


def test_confirmation_pages_and_unpresentable_full_disclosure_have_zero_effects(
    tmp_path,
):
    import anyio
    from test_precheck_run import _disclosure
    from mediasense.precheck import PrecheckRunTool
    from mediasense.runtime.host import RuntimeHost
    from mediasense.runtime.mcp_host import _elicit_precheck_authority
    from mediasense.runtime.composition import HostRequestError

    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    dataset = opened["dataset_ref"]
    tool: PrecheckRunTool = host._datasets[dataset].precheck_run
    run_ref = tool.run(
        {
            "action": "start",
            "dataset_ref": dataset,
            "request_id": "request:large-disclosure",
        }
    )["run_ref"]
    disclosure = _disclosure()
    disclosure["coordinates"] = [
        {"latitude": 22 + i / 100000, "longitude": 114.1, "datum": "WGS84"}
        for i in range(10000)
    ]
    disclosure["pending_logical_queries"] = 10000
    disclosure["max_provider_requests"] = 30000
    paused = tool.require_confirmation(
        run_ref,
        summary="Synthetic full coordinate disclosure",
        quantity=10000,
        unit="logical_queries",
        skip_allowed=False,
        pending_fingerprint=disclosure["geo_request_fingerprint"],
        disclosure=disclosure,
    )
    assert "disclosure" not in paused["confirmation"]
    first = tool.run(
        {
            "action": "status",
            "dataset_ref": dataset,
            "run_ref": run_ref,
            "include": ["confirmation"],
            "page": {"limit": 200},
        }
    )
    assert first["confirmation"]["page"]["total"] == 10000
    assert len(first["confirmation"]["disclosure"]["coordinates"]) == 200
    cursor = first["confirmation"]["page"]["next_cursor"]
    next_page = tool.run(
        {
            "action": "status",
            "dataset_ref": dataset,
            "run_ref": run_ref,
            "include": ["confirmation"],
            "page": {"limit": 200, "cursor": cursor},
        }
    )
    assert (
        next_page["confirmation"]["content_identity"]
        == first["confirmation"]["content_identity"]
    )
    assert (
        next_page["confirmation"]["disclosure"]["coordinates"][0]
        == disclosure["coordinates"][200]
    )

    async def elicit():
        with pytest.raises(HostRequestError) as error:
            await _elicit_precheck_authority(
                None,
                host,
                dataset,
                {
                    "action": "resume",
                    "dataset_ref": dataset,
                    "run_ref": run_ref,
                    "decision": "proceed",
                },
            )
        assert error.value.code == "confirmation_unavailable"

    anyio.run(elicit)
    assert tool.current_state(run_ref) == "paused"


def test_provider_checks_deadline_before_each_http_admission(monkeypatch):
    from mediasense import geo
    from test_geocode import FakeTransport, IdentityConverter

    clock = Clock()
    monkeypatch.setattr(geo.time, "monotonic", clock)

    class SlowTransport(FakeTransport):
        def get_json(self, *args, **kwargs):
            value = super().get_json(*args, **kwargs)
            clock.now += 1
            return value

    transport = SlowTransport(get_response={"status": "ZERO_RESULTS"})
    provider = geo.GoogleMapsReverseGeocoder(
        "synthetic",
        transport=transport,
        converter=IdentityConverter(),
        minimum_interval=0,
        timeout=15,
    )
    result = provider.execute(
        GeoOperation.RESOLVE_PLACE,
        GeoCoordinate(22.3, 114.1),
        locale="zh",
        radius_meters=500,
        max_places=5,
        deadline=1,
    )
    assert len(transport.gets) == 1 and not transport.posts
    assert transport.gets[0][3] == 1
    assert sum(attempt.provider_requests for attempt in result.attempts) == 1
    assert result.components[1].status is GeoComponentStatus.FAILED


def test_legal_historical_result_projects_gaps_without_changing_bytes(tmp_path):
    from pathlib import Path
    from test_geocode import _closed_run, _coordinate_work
    from mediasense.precheck import (
        AccountingStore,
        ImageRenditionProducer,
        ResultStore,
        PrecheckReadTool,
    )

    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = _closed_run(tmp_path, database, accounting, ("a.jpg",))
    metadata = _coordinate_work(
        database, run_id, "a.jpg", latitude=22.3, longitude=114.1
    )
    rendition = ImageRenditionProducer(database).produce(run_id, Path("a.jpg"))
    store = ResultStore(database)
    draft = store.build_minimal(
        run_id, [rendition.work.work_id], metadata_work_ids=[metadata.work_id]
    )
    historical = replace(
        draft,
        sources=tuple(
            replace(
                source,
                observations=tuple(
                    item
                    for item in source.observations
                    if item["name"]
                    not in {"address_candidate", "nearby_place_candidates"}
                )
                + (
                    {
                        "name": "reverse_geocode_candidate",
                        "status": "missing",
                        "basis": "Historical aggregate without component proof.",
                    },
                ),
            )
            for source in draft.sources
        ),
        readiness="blocked",
        qualifications=(
            {
                "code": "reverse_geocode_incomplete",
                "effect": "blocks_use",
                "message": "Historical Geo gate.",
            },
        ),
    )
    sealed = store.seal(historical)
    before = sealed.path.read_bytes()
    reader = PrecheckReadTool(database)
    request = {"dataset_ref": "dataset:dataset-a", "result_ref": sealed.result_ref}
    review = reader.read({**request, "action": "review"})
    assert review["result"]["readiness"] == "plan_ready"
    expanded = reader.read(
        {
            **request,
            "action": "expand",
            "source_item_refs": [historical.sources[0].ref],
            "include": ["observations"],
        }
    )
    components = [
        item
        for item in expanded["items"][0]["included"]["observations"]
        if item["name"] in {"address_candidate", "nearby_place_candidates"}
    ]
    assert len(components) == 2 and all(
        item["status"] == "not_checked" for item in components
    )
    assert all(
        item["basis"]["code"] == "historical_geo_unrecorded" for item in components
    )
    assert sealed.path.read_bytes() == before
    assert store.get(sealed.result_ref).digest == sealed.digest


@pytest.mark.parametrize(
    "failure,expected,calls,requests",
    [
        ("429", "failed", 3, 3),
        ("503", "failed", 3, 3),
        ("401", "failed", 1, 1),
        ("connect", "failed", 3, 0),
        ("timeout", "indeterminate", 1, 1),
    ],
)
def test_real_http_adapter_classification_preserves_retry_and_billing_bounds(
    monkeypatch, failure, expected, calls, requests
):
    from urllib.error import HTTPError, URLError
    from mediasense import geo

    clock = Clock()
    monkeypatch.setattr(geo.time, "monotonic", clock)
    sent = []

    def fail_http(request, *, timeout):
        sent.append(timeout)
        if failure == "connect":
            raise URLError(ConnectionRefusedError("not sent"))
        if failure == "timeout":
            raise TimeoutError("unknown completion")
        raise HTTPError(
            "https://synthetic.invalid", int(failure), "synthetic", {}, None
        )

    monkeypatch.setattr(geo, "urlopen", fail_http)
    provider = geo.AMapReverseGeocoder("credential-must-not-leak", minimum_interval=0)
    capability = GeoCapability(
        {"amap": provider},
        OrderedGeoRoutingPolicy(("amap",)),
        monotonic=clock,
        sleeper=clock.sleep,
    )
    request = GeoRequest(
        GeoOperation.RESOLVE_PLACE,
        (GeoSubject("synthetic", GeoCoordinate(22.3, 114.1)),),
        "zh",
        radius_meters=100,
        max_places=5,
    )
    authorization = GeoAuthorization(
        "human:synthetic",
        capability.fingerprint(request),
        datetime.now(timezone.utc),
        capability.proposed_envelope(request),
    )
    result = capability.invoke(request, authorization=authorization)
    assert result.outcome.value == expected
    assert len(sent) == calls
    assert result.effects.provider_requests == requests
    assert result.effects.billable_units is None
    assert all(timeout <= 15 for timeout in sent)
    assert "credential-must-not-leak" not in str(result.value())
