from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from PIL import Image

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
    DependencyKind,
    ImageRenditionProducer,
    PrecheckReadTool,
    PrecheckRunTool,
    ReverseGeocodeProducer,
    ReverseGeocodeProfile,
    ResultStore,
    WorkDependency,
    WorkSpec,
    WorkStatus,
    WorkStore,
)


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
    get_response: dict[str, object] = field(default_factory=dict)
    post_response: dict[str, object] | Exception = field(default_factory=dict)

    def get_json(self, url, *, params, headers, timeout):
        self.gets.append(
            (url, dict(params), None if headers is None else dict(headers), timeout)
        )
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
    calls: list[GeoCoordinate] = field(default_factory=list)

    def lookup(self, coordinate: GeoCoordinate, *, language: str) -> GeoProviderResult:
        self.calls.append(coordinate)
        return GeoProviderResult(
            status="success",
            provider=self.provider_id,
            language=language,
            input_coordinate=coordinate,
            provider_coordinate=coordinate,
            location={
                "formatted_address": "Tokyo, Japan",
                "components": {"country": "Japan", "country_code": "JP"},
            },
            pois=(),
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
            pois=(),
            request_count=1,
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
    return work.succeed_work(
        lease,
        {
            "observations": [
                {
                    "name": "gps_coordinates",
                    "status": "available",
                    "value": {
                        "datum": "WGS84",
                        "latitude": latitude,
                        "longitude": longitude,
                    },
                }
            ],
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


def test_optional_batch_pauses_before_exact_deduplicated_queries(
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
        AdaptiveReverseGeocoder(
            providers={"google_maps": provider},
            provider_order=("google_maps",),
            initial_provider="google_maps",
            initial_language="ja",
        ),
    )
    profile = ReverseGeocodeProfile(enabled=True, provider_profile="mock-google-v1")

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
    status = run_tool.run({"action": "status", "run_ref": public_run_ref})
    assert status["confirmation"]["quantity"] == 1
    assert status["confirmation"]["unit"] == "logical_queries"

    run_tool.run({"action": "resume", "run_ref": public_run_ref, "decision": "proceed"})
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
        run_tool.run({"action": "status", "run_ref": second_public_ref})["state"]
        == "running"
    )


def test_reused_query_restores_route_and_sequence_is_a_work_dependency(
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
    profile = ReverseGeocodeProfile(enabled=True, provider_profile="route-test-v1")
    first_producer = ReverseGeocodeProducer(
        database,
        run_tool,
        AdaptiveReverseGeocoder(
            providers={"google_maps": first_google, "amap": first_amap},
            provider_order=("amap", "google_maps"),
            initial_provider="google_maps",
            initial_language="zh",
        ),
    )
    assert (
        first_producer.produce(
            first_public_ref, first_run, [beijing.work_id], profile=profile
        ).status
        == "confirmation_required"
    )
    run_tool.run(
        {"action": "resume", "run_ref": first_public_ref, "decision": "proceed"}
    )
    first_completed = first_producer.produce(
        first_public_ref, first_run, [beijing.work_id], profile=profile
    )
    assert len(first_completed.outcomes) == 1
    first_work_id = first_completed.outcomes[0].work.work_id
    assert len(first_google.calls) == 1
    assert len(first_amap.calls) == 1

    second_run = _closed_run(tmp_path, database, accounting, ("a.jpg", "b.jpg"))
    second_beijing = _coordinate_work(
        database, second_run, "a.jpg", latitude=39.9042, longitude=116.4074
    )
    shanghai = _coordinate_work(
        database, second_run, "b.jpg", latitude=31.2304, longitude=121.4737
    )
    second_public_ref = _public_run(run_tool, "request:route-continuity")
    second_google = FakeCountryProvider("google_maps", "China", "CN", MapDatum.WGS84)
    second_amap = FakeCountryProvider("amap", "中国", "CN", MapDatum.GCJ02)
    second_producer = ReverseGeocodeProducer(
        database,
        run_tool,
        AdaptiveReverseGeocoder(
            providers={"google_maps": second_google, "amap": second_amap},
            provider_order=("amap", "google_maps"),
            initial_provider="google_maps",
            initial_language="zh",
        ),
    )

    pending = second_producer.produce(
        second_public_ref,
        second_run,
        [second_beijing.work_id, shanghai.work_id],
        profile=profile,
    )
    assert pending.status == "confirmation_required"
    assert pending.batch.pending_query_count == 1
    run_tool.run(
        {
            "action": "resume",
            "run_ref": second_public_ref,
            "decision": "proceed",
        }
    )
    completed = second_producer.produce(
        second_public_ref,
        second_run,
        [second_beijing.work_id, shanghai.work_id],
        profile=profile,
    )

    assert completed.outcomes[0].reused is True
    assert completed.outcomes[0].work.work_id == first_work_id
    assert second_google.calls == []
    assert len(second_amap.calls) == 1
    chained = completed.outcomes[1].work
    assert any(
        dependency.kind is DependencyKind.UPSTREAM_WORK
        and dependency.key == first_work_id
        for dependency in chained.spec.dependencies
    )
    standalone = second_producer.freeze(
        second_run,
        [shanghai.work_id],
        profile=profile,
    )
    assert standalone.work[0].work_id != chained.work_id


def test_disabled_profile_and_skipped_confirmation_make_no_calls(
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
        AdaptiveReverseGeocoder(
            providers={"google_maps": provider},
            provider_order=("google_maps",),
            initial_provider="google_maps",
            initial_language="ja",
        ),
    )

    disabled = producer.produce(public_run_ref, run_id, [metadata.work_id])
    assert disabled.status == "policy_disabled"
    assert provider.calls == []
    assert (
        run_tool.run({"action": "status", "run_ref": public_run_ref})["state"]
        == "running"
    )

    profile = ReverseGeocodeProfile(enabled=True, provider_profile="mock-google-v1")
    pending = producer.produce(
        public_run_ref, run_id, [metadata.work_id], profile=profile
    )
    run_tool.run(
        {
            "action": "resume",
            "run_ref": public_run_ref,
            "decision": "skip_optional_work",
        }
    )
    skipped = producer.produce(
        public_run_ref, run_id, [metadata.work_id], profile=profile
    )
    assert pending.status == "confirmation_required"
    assert skipped.status == "not_requested"
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
        AdaptiveReverseGeocoder(
            providers={"google_maps": provider},
            provider_order=("google_maps",),
            initial_provider="google_maps",
            initial_language="ja",
        ),
    )
    profile = ReverseGeocodeProfile(enabled=True, provider_profile="mock-google-v1")
    first_pending = producer.produce(
        public_run_ref, run_id, [first.work_id], profile=profile
    )
    run_tool.run({"action": "resume", "run_ref": public_run_ref, "decision": "proceed"})
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
        run_tool.run({"action": "status", "run_ref": public_run_ref})["confirmation"][
            "quantity"
        ]
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
        run_tool.run({"action": "cancel", "run_ref": public_run_ref})
        return result

    provider.lookup = cancel_after_first
    producer = ReverseGeocodeProducer(
        database,
        run_tool,
        AdaptiveReverseGeocoder(
            providers={"google_maps": provider},
            provider_order=("google_maps",),
            initial_provider="google_maps",
            initial_language="ja",
        ),
    )
    profile = ReverseGeocodeProfile(enabled=True, provider_profile="mock-google-v1")
    producer.produce(
        public_run_ref,
        run_id,
        [item.work_id for item in metadata],
        profile=profile,
    )
    run_tool.run({"action": "resume", "run_ref": public_run_ref, "decision": "proceed"})

    interrupted = producer.produce(
        public_run_ref,
        run_id,
        [item.work_id for item in metadata],
        profile=profile,
    )

    assert interrupted.status == "partial"
    assert len(interrupted.outcomes) == 1
    assert interrupted.outcomes[0].work.status is WorkStatus.SUCCEEDED
    assert len(provider.calls) == 1
    status = run_tool.run({"action": "status", "run_ref": public_run_ref})
    assert status["state"] == "cancelled"
    assert "published_result" not in status


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
        AdaptiveReverseGeocoder(
            providers={"google_maps": provider},
            provider_order=("google_maps",),
            initial_provider="google_maps",
            initial_language="ja",
        ),
    )
    profile = ReverseGeocodeProfile(enabled=True, provider_profile="mock-google-v1")
    producer.produce(
        public_run_ref,
        run_id,
        [item.work_id for item in metadata],
        profile=profile,
    )
    run_tool.run({"action": "resume", "run_ref": public_run_ref, "decision": "proceed"})
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
            "result_ref": sealed.result_ref,
            "action": "traverse",
            "relation": "accounts_for",
            "direction": "outbound",
        }
    )
    read_schema = json.loads(
        (
            Path(__file__).parents[1]
            / "docs/spec/spec-260826-1546-precheck-read/precheck-read.tool.json"
        ).read_text(encoding="utf-8")
    )["outputSchema"]
    validator = Draft202012Validator(read_schema)
    validator.validate(accounts)
    for account in accounts["items"]:
        source_response = reader.read(
            {
                "result_ref": sealed.result_ref,
                "action": "inspect",
                "target": {"kind": "source_item", "ref": account["target"]},
            }
        )
        validator.validate(source_response)
        source = source_response["target"]
        attempt = next(
            item
            for item in source["observations"]
            if item["name"] == "reverse_geocode_attempt"
        )
        candidate = next(
            item
            for item in source["observations"]
            if item["name"] == "reverse_geocode_candidate"
        )
        assert attempt["value"]["provider"] == "google_maps"
        assert attempt["value"]["input_coordinate"]["datum"] == "WGS84"
        assert attempt["basis"]["refs"] == [
            {"kind": "source_item", "ref": account["target"]}
        ]
        assert candidate["value"]["address"]["formatted_address"] == ("Tokyo, Japan")

    result_response = reader.read(
        {"result_ref": sealed.result_ref, "action": "inspect"}
    )
    validator.validate(result_response)
    result_view = result_response["target"]
    qualification = next(
        item
        for item in result_view["qualifications"]
        if item["code"] == "external_reverse_geocode_candidates"
    )
    assert "1 logical queries" in qualification["message"]
    boundary = result_view["execution_boundary"]
    assert boundary["logical_external_queries"] == 1
    assert boundary["provider_requests"] == 2
    assert boundary["billable_calls"] == "unknown"
