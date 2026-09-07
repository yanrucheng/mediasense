from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
from threading import Event, Thread

from PIL import Image
import pytest

from mediasense.capabilities.geo import (
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
    OrderedGeoRoutingPolicy,
)
from mediasense.plan import PlanWorkTool
from mediasense.geo import (
    GeoCoordinate,
    GeoProviderResult,
    MapDatum,
)
from mediasense.precheck import (
    AccountingStore,
    Detection,
    EmbeddingProfile,
    PrecheckReadTool,
    PrecheckConfirmationContext,
    PrecheckRunTool,
    ResultStore,
    SensitivityProfile,
    SensitivityThreshold,
)
from mediasense.precheck._orchestrator import (
    PrecheckExecutionConfig,
    PrecheckExecutionDependencies,
    PrecheckOrchestrator,
)
from mediasense.precheck.work import WorkStore
from mediasense.precheck.read import bind_precheck_read


class FakeExifTool:
    def __init__(
        self,
        capture_times: dict[str, str] | None = None,
        *,
        include_gps: bool = False,
        gps_coordinates: dict[str, tuple[float, float]] | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.capture_times = capture_times or {}
        self.include_gps = include_gps
        self.gps_coordinates = gps_coordinates or {}

    def __call__(self, command) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.calls.append(command)
        if command[-1] == "-ver":
            return subprocess.CompletedProcess(command, 0, "13.30\n", "")
        paths = [Path(value) for value in command[command.index("--") + 1 :]]
        records = []
        for path in paths:
            record: dict[str, object] = {"SourceFile": str(path)}
            if path.suffix.casefold() == ".xmp":
                record["XMP:DateTimeOriginal"] = "2026:05:04 20:27:28+08:00"
            else:
                record.update(
                    {
                        "File:MIMEType": (
                            "video/mp4"
                            if path.suffix.casefold() == ".mp4"
                            else "image/jpeg"
                        ),
                    }
                )
                coordinate = self.gps_coordinates.get(path.name)
                if coordinate is not None:
                    record.update(
                        {
                            "Composite:GPSLatitude": coordinate[0],
                            "Composite:GPSLongitude": coordinate[1],
                        }
                    )
                elif self.include_gps:
                    record.update(
                        {
                            "Composite:GPSLatitude": 22.3193,
                            "Composite:GPSLongitude": 114.1694,
                        }
                    )
                if path.name in self.capture_times:
                    record["XMP:DateTimeOriginal"] = self.capture_times[path.name]
            records.append(record)
        return subprocess.CompletedProcess(command, 0, json.dumps(records), "")


class FakeVideoTools:
    def __init__(self, *, fail_at: set[float] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_at = fail_at or set()

    def __call__(self, command) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.calls.append(command)
        if "-show_entries" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "streams": [
                            {
                                "width": 1920,
                                "height": 1080,
                                "avg_frame_rate": "30/1",
                                "nb_frames": "751",
                            }
                        ],
                        "format": {"duration": "25.0"},
                    }
                ),
                "",
            )
        sample_time = float(command[command.index("-ss") + 1])
        if sample_time in self.fail_at:
            return subprocess.CompletedProcess(command, 1, "", "decode failed")
        Image.new("RGB", (320, 180), (int(sample_time) % 255, 40, 60)).save(
            Path(command[-1]), format="JPEG"
        )
        return subprocess.CompletedProcess(command, 0, "", "")


class FakeEncoder:
    identity = "fake-local-embedding@sha256:one"

    def __init__(self) -> None:
        self.batch_calls: list[tuple[Path, ...]] = []

    def encode_image(self, image_path: Path) -> tuple[float, ...]:
        with Image.open(image_path) as image:
            width, height = image.size
        return float(width), float(height), 1.0, 2.0

    def encode_images(
        self, image_paths: tuple[Path, ...]
    ) -> tuple[tuple[float, ...], ...]:
        self.batch_calls.append(image_paths)
        return tuple(self.encode_image(path) for path in image_paths)


class FakeSensitivityDetector:
    identity = "fake-local-sensitivity@sha256:one"

    def __init__(self) -> None:
        self.batch_calls: list[tuple[Path, ...]] = []

    def detect(self, _image_path: Path) -> tuple[Detection, ...]:
        return (Detection("ordinary", 0.1),)

    def detect_many(
        self, image_paths: tuple[Path, ...]
    ) -> tuple[tuple[Detection, ...], ...]:
        self.batch_calls.append(image_paths)
        return tuple(self.detect(path) for path in image_paths)


@dataclass
class FakeGeocodeProvider:
    provider_id: str = "fake_maps"
    datum: MapDatum = MapDatum.WGS84
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
                "formatted_address": (
                    f"{coordinate.latitude:.4f},{coordinate.longitude:.4f}"
                ),
                "components": {"country": "China", "country_code": "HK"},
            },
            pois=(
                {
                    "name": "Nearby fixture place",
                    "address": "Fixture address",
                    "latitude": coordinate.latitude,
                    "longitude": coordinate.longitude,
                },
            ),
            request_count=2,
        )


class FakeGeoProviderAdapter:
    def __init__(self, provider: FakeGeocodeProvider) -> None:
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
        location = result.location or {}
        address = GeoCandidate(
            GeoCandidateKind.ADDRESS,
            str(location.get("formatted_address", "unknown")),
            formatted_address=str(location.get("formatted_address", "unknown")),
            coordinate=coordinate,
            components=tuple(
                sorted(
                    (str(key), str(value))
                    for key, value in dict(location.get("components", {})).items()
                )
            ),
            provider_ref=result.provider,
        )
        address_component = GeoComponentResult(
            GeoOperation.REVERSE_GEOCODE,
            GeoComponentStatus.SUCCESS,
            (),
            coordinate,
            (address,),
        )
        reverse_attempt = GeoProviderAttempt(
            result.provider,
            GeoOperation.REVERSE_GEOCODE,
            GeoComponentStatus.SUCCESS,
            coordinate,
            result.provider_coordinate,
            1,
            None,
        )
        if operation is not GeoOperation.RESOLVE_PLACE:
            return GeoProviderExecution(address_component, reverse_attempt)
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
        nearby_component = GeoComponentResult(
            GeoOperation.NEARBY_PLACES,
            GeoComponentStatus.SUCCESS,
            (),
            coordinate,
            places,
        )
        nearby_attempt = GeoProviderAttempt(
            result.provider,
            GeoOperation.NEARBY_PLACES,
            GeoComponentStatus.SUCCESS,
            coordinate,
            result.provider_coordinate,
            1,
            None,
        )
        return GeoProviderExecution(
            address_component,
            reverse_attempt,
            (nearby_component,),
            (nearby_attempt,),
        )


def _geo_tool(tmp_path: Path, provider: FakeGeocodeProvider) -> GeoQueryTool:
    adapter = FakeGeoProviderAdapter(provider)
    return GeoQueryTool(
        GeoCapability(
            {provider.provider_id: adapter},
            OrderedGeoRoutingPolicy((provider.provider_id,)),
        ),
        GeoOperationJournal(tmp_path / "geo-journal.sqlite3"),
    )


def _prepare_source_bound_run(
    tmp_path: Path,
    *,
    dataset_id: str = "dataset-a",
) -> tuple[Path, Path, str]:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    accounting = AccountingStore(database)
    accounting.register_dataset(dataset_id)
    accounting_run_id = accounting.start_or_resume_run(dataset_id, source)
    return database, source, accounting_run_id


def _resume_with_default_scope(tool: PrecheckRunTool, run_ref: str) -> None:
    paused = tool.advance(run_ref)
    assert paused["state"] == "paused"
    assert paused["reason"]["code"] == "scope_confirmation_required"
    confirmation = paused["confirmation"]
    decision = {
        "kind": "source_scope",
        "inventory_fingerprint": confirmation["inventory_fingerprint"],
        "default_disposition": "include",
        "exceptions": [],
    }
    accepted = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": run_ref,
            "decision": decision,
        }
    )
    assert "error" not in accepted


def _advance_after_scope(tool: PrecheckRunTool, run_ref: str) -> dict[str, object]:
    _resume_with_default_scope(tool, run_ref)
    return tool.advance(run_ref)


def test_start_then_internal_worker_drives_mixed_source_to_readable_result(
    tmp_path: Path,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (80, 60), "purple").save(source / "photo.jpg")
    (source / "photo.xmp").write_text("sidecar", encoding="utf-8")
    (source / "track.gpx").write_text(
        """<?xml version="1.0"?><gpx version="1.1"><trk><trkseg>
        <trkpt lat="22.3193" lon="114.1694">
        <time>2026-05-04T12:27:28Z</time></trkpt>
        </trkseg></trk></gpx>""",
        encoding="utf-8",
    )
    (source / "clip.mp4").write_bytes(b"fake video bytes")
    source_before = {
        path.name: path.read_bytes() for path in source.iterdir() if path.is_file()
    }
    metadata = FakeExifTool()
    video = FakeVideoTools()
    encoder = FakeEncoder()
    detector = FakeSensitivityDetector()
    geo_provider = FakeGeocodeProvider()
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            compression_target=3,
            model_batch_size=2,
            embedding_profile=EmbeddingProfile(name="test-vector-v1", dimensions=4),
            sensitivity_profile=SensitivityProfile(
                name="test-sensitivity-v1",
                thresholds=(
                    SensitivityThreshold("sensitive", 0.8),
                    SensitivityThreshold("ordinary", 99.0),
                ),
            ),
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=metadata,
            exiftool_version="13.30",
            video_runner=video,
            ffprobe_version="ffprobe 8.1",
            ffmpeg_version="ffmpeg 8.1",
            embedding_encoder=encoder,
            sensitivity_detector=detector,
            geo_tool=_geo_tool(tmp_path, geo_provider),
        ),
    )

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:mixed-e2e",
        }
    )
    assert set(started) == {"run_ref"}
    assert WorkStore(database).list_run_work(_accounting_run_id) == ()
    advanced = _advance_after_scope(tool, str(started["run_ref"]))
    if (
        advanced["state"] == "paused"
        and advanced["reason"]["code"] == "confirmation_required"
    ):
        tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "resume",
                "run_ref": started["run_ref"],
                "decision": "proceed",
            },
            confirmation=PrecheckConfirmationContext(
                principal_ref="human:test",
                confirmed_content_identity=advanced["confirmation"]["content_identity"],
                confirmed_at=datetime.now(timezone.utc),
            ),
        )
        tool.advance(str(started["run_ref"]))
    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )

    assert "error" not in started
    assert status["state"] == "completed", status
    assert set(status["result"]) >= {"ref", "coverage", "readiness"}
    result_ref = status["result"]["ref"]
    inspected = PrecheckReadTool(database).read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "review",
            "result_ref": result_ref,
        }
    )
    assert "error" not in inspected
    assert inspected["result"]["ref"] == result_ref
    assert inspected["result"]["coverage"] == "complete"
    assert inspected["result"]["readiness"] == "plan_ready"
    capabilities = {
        work.spec.capability
        for work in WorkStore(database).list_run_work(_accounting_run_id)
    }
    assert {
        "adaptive-compression-group",
        "bundle-candidate",
        "gpx-location-candidate",
        "image-embedding",
        "image-rendition",
        "content-sensitivity",
        "source-metadata",
        "video-contact-sheet",
        "video-frame",
        "video-key-frame-candidate",
        "video-probe",
    } <= capabilities
    assert {
        path.name: path.read_bytes() for path in source.iterdir() if path.is_file()
    } == source_before
    assert encoder.batch_calls
    assert detector.batch_calls
    assert all(len(batch) <= 2 for batch in encoder.batch_calls)
    assert all(len(batch) <= 2 for batch in detector.batch_calls)


@pytest.mark.parametrize(
    ("directed_paths", "expected_renditions"),
    [
        ((), {"a.jpg", "c.jpg"}),
        ((Path("b.jpg"),), {"a.jpg", "b.jpg", "c.jpg"}),
    ],
)
def test_bundle_reduces_initial_visual_demand_without_reducing_accounting(
    tmp_path: Path,
    directed_paths: tuple[Path, ...],
    expected_renditions: set[str],
) -> None:
    database, source, accounting_run_id = _prepare_source_bound_run(tmp_path)
    for name, color in (("a.jpg", "red"), ("b.jpg", "blue"), ("c.jpg", "green")):
        Image.new("RGB", (48, 32), color).save(source / name)
    metadata_runner = FakeExifTool(
        {
            "a.jpg": "2026:05:04 20:27:00+08:00",
            "b.jpg": "2026:05:04 20:27:20+08:00",
            "c.jpg": "2026:05:04 20:27:40+08:00",
        }
    )
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            directed_evidence_paths=directed_paths,
            gpx=False,
            video=False,
            compression_target=1,
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=metadata_runner,
            exiftool_version="13.30",
        ),
    )

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": f"request:bounded-visual-{len(directed_paths)}",
        }
    )
    _advance_after_scope(tool, str(started["run_ref"]))

    works = WorkStore(database).list_run_work(accounting_run_id)
    metadata = [work for work in works if work.spec.capability == "source-metadata"]
    bundles = [work for work in works if work.spec.capability == "bundle-candidate"]
    renditions = [work for work in works if work.spec.capability == "image-rendition"]
    rendition_subjects = {
        json.loads(
            next(
                dependency.key
                for dependency in work.spec.dependencies
                if dependency.kind.value == "source_revision"
            )
        )[1]
        for work in renditions
    }
    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    accounts = PrecheckReadTool(database).read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resolve",
            "result_ref": status["result"]["ref"],
            "source_set": {
                "kind": "precheck_relation",
                "origin": status["result"]["ref"],
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )

    assert status["state"] == "completed"
    assert len(metadata) == 3
    assert len(bundles) == 1
    assert rendition_subjects == expected_renditions
    assert sum(item["scope"] == "source_media" for item in accounts["members"]) == 3


def test_later_run_can_direct_additional_visual_evidence(tmp_path: Path) -> None:
    database, source, first_accounting = _prepare_source_bound_run(tmp_path)
    for name, color in (("a.jpg", "red"), ("b.jpg", "blue"), ("c.jpg", "green")):
        Image.new("RGB", (48, 32), color).save(source / name)
    metadata_runner = FakeExifTool(
        {
            "a.jpg": "2026:05:04 20:27:00+08:00",
            "b.jpg": "2026:05:04 20:27:20+08:00",
            "c.jpg": "2026:05:04 20:27:40+08:00",
        }
    )
    base = dict(
        gpx=False,
        video=False,
        compression_target=1,
    )
    dependencies = PrecheckExecutionDependencies(
        metadata_runner=metadata_runner,
        exiftool_version="13.30",
    )
    first_tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(**base),
        execution_dependencies=dependencies,
    )
    first = first_tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:initial-evidence",
        }
    )
    _advance_after_scope(first_tool, str(first["run_ref"]))
    assert (
        sum(
            work.spec.capability == "image-rendition"
            for work in WorkStore(database).list_run_work(first_accounting)
        )
        == 2
    )

    second_accounting = AccountingStore(database).start_or_resume_run(
        "dataset-a", source
    )
    second_tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            **base,
            directed_evidence_paths=(Path("b.jpg"),),
        ),
        execution_dependencies=dependencies,
    )
    second = second_tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:additional-evidence",
        }
    )
    second_tool.advance(str(second["run_ref"]))

    attached = WorkStore(database).list_run_work(second_accounting)
    renditions = [
        work for work in attached if work.spec.capability == "image-rendition"
    ]
    assert len(renditions) == 3


def test_metadata_batches_respect_configured_provider_ceiling(tmp_path: Path) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    for index in range(5):
        (source / f"image-{index}.jpg").write_bytes(f"image-{index}".encode())
    metadata_runner = FakeExifTool()
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            metadata_batch_size=2,
            gpx=False,
            image_renditions=False,
            video=False,
            bundles=False,
            compression_target=None,
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=metadata_runner,
            exiftool_version="13.30",
        ),
    )

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:metadata-batches",
        }
    )
    _advance_after_scope(tool, str(started["run_ref"]))

    assert (
        tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "status",
                "run_ref": started["run_ref"],
            }
        )["state"]
        == "completed"
    )
    assert len(metadata_runner.calls) == 3
    assert all(
        len(command[command.index("--") + 1 :]) <= 2
        for command in metadata_runner.calls
    )


def test_default_orchestration_makes_no_external_requests(tmp_path: Path) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (32, 24), "navy").save(source / "photo.jpg")

    class RejectNetwork:
        def handle(self, _request):
            raise AssertionError("default PreCheck must not invoke a provider")

    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            metadata=False,
            gpx=False,
            video=False,
            bundles=False,
            compression_target=1,
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            geo_tool=RejectNetwork()  # type: ignore[arg-type]
        ),
    )
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:zero-network",
        }
    )
    _advance_after_scope(tool, str(started["run_ref"]))
    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    assert status["state"] == "completed"


def test_geocode_pauses_for_exact_frozen_query_count_before_fake_provider(
    tmp_path: Path,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    for name, color in (("a.jpg", "red"), ("b.jpg", "blue")):
        Image.new("RGB", (48, 32), color).save(source / name)
    provider = FakeGeocodeProvider()
    geo_tool = _geo_tool(tmp_path, provider)
    base = PrecheckExecutionConfig()
    auto_budget = base.resolve_resources(
        source_storage="local",
        source_storage_evidence="test_verified_local_ssd",
        logical_cpu_count=4,
        available_memory_bytes=1024 * 1024 * 1024,
    ).resource_budget
    assert auto_budget is not None
    capacity = replace(auto_budget.capacity, network_slots=1)
    config = replace(
        base,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=2,
        reverse_geocode_profile=replace(
            base.reverse_geocode_profile,
            provider_profile="fake-maps-v1",
        ),
        resource_budget=replace(auto_budget, capacity=capacity),
    )
    tool = PrecheckRunTool(
        database,
        execution_config=config,
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=FakeExifTool(include_gps=True),
            exiftool_version="13.30",
            geo_tool=geo_tool,
        ),
    )

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:geocode-e2e",
        }
    )
    _advance_after_scope(tool, str(started["run_ref"]))
    paused = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    assert paused["state"] == "paused"
    assert paused["reason"]["code"] == "confirmation_required"
    assert paused["confirmation"]["disclosure"]["pending_logical_queries"] == 1
    assert paused["confirmation"]["page"]["total"] == 1
    assert provider.calls == []

    resumed = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": started["run_ref"],
            "decision": "proceed",
        },
        confirmation=PrecheckConfirmationContext(
            principal_ref="human:test",
            confirmed_content_identity=paused["confirmation"]["content_identity"],
            confirmed_at=datetime.now(timezone.utc),
        ),
    )
    assert (
        tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "status",
                "run_ref": started["run_ref"],
            }
        )["state"]
        == "running"
    )
    assert provider.calls == []
    tool.advance(str(started["run_ref"]))
    completed = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )

    assert "error" not in resumed
    assert completed["state"] == "completed", completed
    assert len(provider.calls) == 1
    result_ref = completed["result"]["ref"]
    inspected = PrecheckReadTool(database).read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "review",
            "result_ref": result_ref,
            "include": ["execution_boundary"],
        }
    )
    boundary = inspected["execution_boundary"]
    assert boundary["logical_external_queries"] == 1
    assert boundary["current_provider_requests"] == 2
    assert boundary["historical_provider_requests"] == 0


def test_visual_compression_does_not_reduce_per_source_geocode_coverage(
    tmp_path: Path,
) -> None:
    database, source, accounting_run_id = _prepare_source_bound_run(tmp_path)
    coordinates = {
        "a.jpg": (22.2819, 114.1589),
        "b.jpg": (22.3193, 114.1694),
        "c.jpg": (22.3964, 114.1095),
        "d.jpg": (22.3193, 114.1694),
    }
    for name, color in (
        ("a.jpg", "red"),
        ("b.jpg", "blue"),
        ("c.jpg", "green"),
        ("d.jpg", "yellow"),
    ):
        Image.new("RGB", (48, 32), color).save(source / name)
    provider = FakeGeocodeProvider()
    base = PrecheckExecutionConfig()
    config = replace(
        base,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
        reverse_geocode_profile=replace(
            base.reverse_geocode_profile,
            provider_profile="fake-maps-v1",
        ),
    )
    tool = PrecheckRunTool(
        database,
        execution_config=config,
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=FakeExifTool(gps_coordinates=coordinates),
            exiftool_version="13.30",
            geo_tool=_geo_tool(tmp_path, provider),
        ),
    )

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:per-source-geocode",
        }
    )
    paused = _advance_after_scope(tool, str(started["run_ref"]))

    assert paused["state"] == "paused"
    unique_coordinates = set(coordinates.values())
    assert paused["confirmation"]["disclosure"]["pending_logical_queries"] == len(
        unique_coordinates
    )
    assert (
        sum(
            work.spec.capability == "adaptive-compression-group"
            for work in WorkStore(database).list_run_work(accounting_run_id)
        )
        == 1
    )

    tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": started["run_ref"],
            "decision": "proceed",
        },
        confirmation=PrecheckConfirmationContext(
            principal_ref="human:test",
            confirmed_content_identity=paused["confirmation"]["content_identity"],
            confirmed_at=datetime.now(timezone.utc),
        ),
    )
    tool.advance(str(started["run_ref"]))
    completed = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )

    assert completed["state"] == "completed", completed
    assert len(provider.calls) == len(unique_coordinates)
    result_ref = completed["result"]["ref"]
    reader = PrecheckReadTool(database)
    accounts = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resolve",
            "result_ref": result_ref,
            "source_set": {
                "kind": "precheck_relation",
                "origin": result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    source_refs = [
        member["source_item_ref"]
        for member in accounts["members"]
        if member["scope"] == "source_media"
    ]
    expanded = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "expand",
            "result_ref": result_ref,
            "source_item_refs": source_refs,
            "include": ["source_item", "observations"],
        }
    )
    locations = {}
    for item in expanded["items"]:
        included = item["included"]
        path = included["source_item"]["locator"]["value"]
        assert all(
            observation["name"] != "reverse_geocode_attempt"
            for observation in included["observations"]
        )
        components = {
            observation["name"]: observation
            for observation in included["observations"]
            if observation["name"] in {"address_candidate", "nearby_place_candidates"}
        }
        assert set(components) == {"address_candidate", "nearby_place_candidates"}
        assert all(item["status"] == "available" for item in components.values())
        assert (
            components["nearby_place_candidates"]["value"][0]["name"]
            == "Nearby fixture place"
        )
        assert "provider_ref" not in components["nearby_place_candidates"]["value"][0]
        locations[path] = components["address_candidate"]["value"]["formatted_address"]

    assert locations == {
        path: f"{latitude:.4f},{longitude:.4f}"
        for path, (latitude, longitude) in coordinates.items()
    }
    assert (
        reader.read(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "review",
                "result_ref": result_ref,
            }
        )["result"]["readiness"]
        == "plan_ready"
    )
    plan = PlanWorkTool(
        tmp_path / "plan-store", bind_precheck_read(reader, "dataset:dataset-a")
    ).handle(
        {
            "action": "create",
            "result_ref": result_ref,
            "request_id": "request:plan-from-per-source-geocode",
        }
    )
    assert "error" not in plan


def test_nonempty_geo_batch_without_provider_is_terminal_unavailable(
    tmp_path: Path,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (48, 32), "red").save(source / "gps.jpg")
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            gpx=False, video=False, bundles=False, compression_target=1
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=FakeExifTool(include_gps=True),
            exiftool_version="13.30",
        ),
    )
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:no-geo-provider",
        }
    )

    _advance_after_scope(tool, str(started["run_ref"]))
    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )

    assert status["state"] == "failed"
    assert status["reason"]["code"] == "provider_unavailable"
    assert "result" not in status


def test_human_declines_frozen_geo_batch_without_provider_request(
    tmp_path: Path,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (48, 32), "red").save(source / "gps.jpg")
    provider = FakeGeocodeProvider()
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            gpx=False, video=False, bundles=False, compression_target=1
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=FakeExifTool(include_gps=True),
            exiftool_version="13.30",
            geo_tool=_geo_tool(tmp_path, provider),
        ),
    )
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:decline-geo",
        }
    )
    _advance_after_scope(tool, str(started["run_ref"]))
    paused = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )

    assert paused["state"] == "paused"
    assert provider.calls == []
    declined = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": started["run_ref"],
            "decision": "decline",
        }
    )
    assert declined["state"] == "cancelled"
    assert provider.calls == []
    assert "result" not in tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )


def test_local_item_failure_isolated_while_other_source_completes(
    tmp_path: Path,
) -> None:
    database, source, accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (40, 30), "green").save(source / "good.jpg")
    (source / "broken.jpg").write_bytes(b"not an image")
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )
    tool = PrecheckRunTool(database, execution_config=config)

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:isolated-failure",
        }
    )
    _advance_after_scope(tool, str(started["run_ref"]))
    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )

    assert status["state"] == "completed"
    details = tool.run(
        {
            "action": "status",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": started["run_ref"],
            "include": ["accounting", "diagnostics"],
        }
    )
    assert details["accounting"]["accounted"] == 2
    assert sorted(
        (item["condition"], item["count"])
        for item in details["accounting"]["scope_condition"]
    ) == [("invalid", 1), ("usable", 1)]
    assert "progress" not in status
    assert (
        sum(
            item["count"]
            for item in status["issues"]
            if item["phase"] == "renditions" and item["unit"] != "phase"
        )
        == 1
    )
    works = WorkStore(database).list_run_work(accounting_run_id)
    assert sum(work.status.value == "succeeded" for work in works) >= 2
    assert sum(work.status.value == "terminal_failure" for work in works) == 1


def test_local_item_failure_is_visible_before_result_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (40, 30), "green").save(source / "good.jpg")
    (source / "broken.jpg").write_bytes(b"not an image")
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )
    reached_boundary = Event()
    release_worker = Event()

    def wait_after_rendition(
        _orchestrator: PrecheckOrchestrator, _run_ref: str, phase: str
    ) -> None:
        if phase == "renditions":
            reached_boundary.set()
            assert release_worker.wait(timeout=5)

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", wait_after_rendition)
    tool = PrecheckRunTool(database, execution_config=config)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:visible-isolated-failure",
        }
    )
    _resume_with_default_scope(tool, str(started["run_ref"]))
    results: list[dict[str, object]] = []
    worker = Thread(
        target=lambda: results.append(tool.advance(str(started["run_ref"])))
    )
    worker.start()
    assert reached_boundary.wait(timeout=5)

    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    assert status["state"] == "running"
    assert status["progress"]["phase"] == "renditions"
    assert status["progress"]["processed"] == status["progress"]["total"]
    assert (
        sum(
            item["count"]
            for item in status["issues"]
            if item["phase"] == "renditions" and item["unit"] != "phase"
        )
        == 1
    )

    release_worker.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert results[0]["state"] == "completed"


def test_user_pause_resume_and_cancel_are_honored_between_phases(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (40, 30), "green").save(source / "photo.jpg")
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )
    original = PrecheckOrchestrator._after_phase
    reached_boundary = Event()
    release_worker = Event()

    def wait_after_rendition(
        _orchestrator: PrecheckOrchestrator, _run_ref: str, phase: str
    ) -> None:
        if phase == "renditions":
            reached_boundary.set()
            assert release_worker.wait(timeout=5)

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", wait_after_rendition)
    tool = PrecheckRunTool(database, execution_config=config)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:pause-resume",
        }
    )
    assert set(started) == {"run_ref"}
    _resume_with_default_scope(tool, str(started["run_ref"]))
    worker_results: list[dict[str, object]] = []
    worker = Thread(
        target=lambda: worker_results.append(tool.advance(str(started["run_ref"])))
    )
    worker.start()
    assert reached_boundary.wait(timeout=5)
    boundary = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    assert boundary["state"] == "running"
    assert boundary.get("reason", {}).get("code") not in {
        "suspected_stalled",
        "no_recent_progress",
    }
    assert boundary["progress"]["phase"] == "renditions"
    assert boundary["progress"]["processed"] == boundary["progress"]["total"]
    accepted_pause = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "pause",
            "run_ref": started["run_ref"],
        }
    )
    release_worker.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert worker_results[0]["state"] == "paused"
    assert "error" not in accepted_pause
    paused = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    assert paused["state"] == "paused"
    assert paused["reason"]["code"] == "user_requested"
    assert "progress" not in paused

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", original)
    accepted_resume = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": started["run_ref"],
        }
    )
    assert "error" not in accepted_resume
    assert (
        tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "status",
                "run_ref": started["run_ref"],
            }
        )["state"]
        == "running"
    )
    tool.advance(str(started["run_ref"]))
    assert (
        tool.run(
            {
                "dataset_ref": "dataset:dataset-a",
                "action": "status",
                "run_ref": started["run_ref"],
            }
        )["state"]
        == "completed"
    )

    second_accounting = AccountingStore(database).start_or_resume_run(
        "dataset-a", source
    )
    assert second_accounting

    cancel_boundary = Event()
    release_cancelled_worker = Event()

    def wait_before_cancel(
        _orchestrator: PrecheckOrchestrator, _run_ref: str, phase: str
    ) -> None:
        if phase == "renditions":
            cancel_boundary.set()
            assert release_cancelled_worker.wait(timeout=5)

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", wait_before_cancel)
    cancel_tool = PrecheckRunTool(database, execution_config=config)
    cancelled_start = cancel_tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:cancel",
        }
    )
    cancel_results: list[dict[str, object]] = []
    cancel_worker = Thread(
        target=lambda: cancel_results.append(
            cancel_tool.advance(str(cancelled_start["run_ref"]))
        )
    )
    cancel_worker.start()
    assert cancel_boundary.wait(timeout=5)
    accepted_cancel = cancel_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "cancel",
            "run_ref": cancelled_start["run_ref"],
        }
    )
    release_cancelled_worker.set()
    cancel_worker.join(timeout=5)
    assert not cancel_worker.is_alive()
    assert cancel_results[0]["state"] == "cancelled"
    assert "error" not in accepted_cancel
    cancelled = cancel_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": cancelled_start["run_ref"],
        }
    )
    assert cancelled["state"] == "cancelled"
    assert "result" not in cancelled


def test_process_interruption_resumes_without_repeating_completed_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, source, accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (40, 30), "orange").save(source / "photo.jpg")
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )
    original = PrecheckOrchestrator._after_phase

    def crash_after_rendition(
        _orchestrator: PrecheckOrchestrator, _run_ref: str, phase: str
    ) -> None:
        if phase == "renditions":
            raise KeyboardInterrupt("simulated process loss")

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", crash_after_rendition)
    first_tool = PrecheckRunTool(database, execution_config=config)
    request = {
        "action": "start",
        "dataset_ref": "dataset:dataset-a",
        "request_id": "request:interrupt",
    }
    started = first_tool.run(request)
    run_ref = str(started["run_ref"])
    _resume_with_default_scope(first_tool, run_ref)
    with pytest.raises(KeyboardInterrupt, match="simulated process loss"):
        first_tool.advance(run_ref)
    interrupted = first_tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    assert interrupted["state"] == "paused"
    assert interrupted["reason"]["code"] == "process_interrupted"
    detail = first_tool.run(
        {
            "action": "status",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": run_ref,
            "include": ["diagnostics"],
        }
    )
    assert detail["diagnostics"]["work"]["phase"] == "renditions"
    before = {
        work.work_id
        for work in WorkStore(database).list_run_work(accounting_run_id)
        if work.spec.capability == "image-rendition"
    }
    assert len(before) == 1

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", original)
    restarted = PrecheckRunTool(database, execution_config=config)
    resumed = restarted.run(
        {"dataset_ref": "dataset:dataset-a", "action": "resume", "run_ref": run_ref}
    )
    restarted.advance(run_ref)
    completed = restarted.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    after = {
        work.work_id
        for work in WorkStore(database).list_run_work(accounting_run_id)
        if work.spec.capability == "image-rendition"
    }

    assert "error" not in resumed
    assert completed["state"] == "completed"
    assert after == before


def test_crash_immediately_before_seal_resumes_to_one_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (40, 30), "teal").save(source / "photo.jpg")
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )
    original = PrecheckOrchestrator._after_phase

    def crash_before_seal(
        _orchestrator: PrecheckOrchestrator, _run_ref: str, phase: str
    ) -> None:
        if phase == "external_evidence":
            raise KeyboardInterrupt("simulated crash before seal")

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", crash_before_seal)
    tool = PrecheckRunTool(database, execution_config=config)
    request = {
        "action": "start",
        "dataset_ref": "dataset:dataset-a",
        "request_id": "request:before-seal-crash",
    }
    started = tool.run(request)
    _resume_with_default_scope(tool, str(started["run_ref"]))
    with pytest.raises(KeyboardInterrupt, match="simulated crash before seal"):
        tool.advance(str(started["run_ref"]))
    assert ResultStore(database).audit().available == ()

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", original)
    restarted = PrecheckRunTool(database, execution_config=config)
    restarted.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": started["run_ref"],
        }
    )
    restarted.advance(str(started["run_ref"]))
    completed = restarted.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    assert completed["state"] == "completed"
    assert ResultStore(database).audit().available == (completed["result"]["ref"],)


def test_crash_after_sealed_bytes_recovers_without_partial_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (40, 30), "teal").save(source / "photo.jpg")
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )

    def crash_after_bytes(_store: ResultStore, _path: Path) -> None:
        raise RuntimeError("simulated crash after sealed bytes")

    monkeypatch.setattr(ResultStore, "_after_file_published", crash_after_bytes)
    tool = PrecheckRunTool(database, execution_config=config)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:after-bytes-crash",
        }
    )
    _resume_with_default_scope(tool, str(started["run_ref"]))
    tool.advance(str(started["run_ref"]))
    interrupted = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    audit = ResultStore(database).audit()
    assert interrupted["state"] == "paused"
    assert interrupted["reason"]["code"] == "process_interrupted"
    assert audit.available == ()
    assert len(audit.orphan_paths) == 1

    monkeypatch.undo()
    restarted = PrecheckRunTool(database, execution_config=config)
    restarted.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": started["run_ref"],
        }
    )
    restarted.advance(str(started["run_ref"]))
    completed = restarted.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    recovered = ResultStore(database).audit()
    assert completed["state"] == "completed", completed
    assert recovered.orphan_paths == ()
    assert recovered.available == (completed["result"]["ref"],)


def test_crash_after_result_registration_rebinds_run_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (40, 30), "gold").save(source / "photo.jpg")
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )
    original = PrecheckRunTool.complete_with_result

    def crash_after_registration(
        tool: PrecheckRunTool, run_ref: str, result_ref: str
    ) -> dict[str, object]:
        assert ResultStore(tool.database_path).get(result_ref).result_ref == result_ref
        raise KeyboardInterrupt("simulated crash after Result registration")

    monkeypatch.setattr(
        PrecheckRunTool, "complete_with_result", crash_after_registration
    )
    tool = PrecheckRunTool(database, execution_config=config)
    request = {
        "action": "start",
        "dataset_ref": "dataset:dataset-a",
        "request_id": "request:registered-crash",
    }
    started = tool.run(request)
    _resume_with_default_scope(tool, str(started["run_ref"]))
    with pytest.raises(KeyboardInterrupt, match="after Result registration"):
        tool.advance(str(started["run_ref"]))
    record = tool._store.get(str(started["run_ref"]))
    available = ResultStore(database).audit().available
    assert len(available) == 1
    assert record["state"] == "paused"
    interrupted = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": record["run_ref"],
        }
    )
    assert interrupted["reason"]["code"] == "process_interrupted"

    monkeypatch.setattr(PrecheckRunTool, "complete_with_result", original)
    restarted = PrecheckRunTool(database, execution_config=config)
    restarted.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": record["run_ref"],
        }
    )
    restarted.advance(str(record["run_ref"]))
    completed = restarted.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": record["run_ref"],
        }
    )
    assert completed["state"] == "completed"
    assert completed["result"]["ref"] == available[0]


def test_low_level_work_and_artifact_are_reused_across_public_runs(
    tmp_path: Path,
) -> None:
    database, source, first_accounting = _prepare_source_bound_run(tmp_path)
    for name, color in (("a.jpg", "red"), ("b.jpg", "blue")):
        Image.new("RGB", (40, 30), color).save(source / name)
    config = PrecheckExecutionConfig(
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=1,
    )
    first_tool = PrecheckRunTool(database, execution_config=config)
    first = first_tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:reuse-first",
        }
    )
    _advance_after_scope(first_tool, str(first["run_ref"]))
    first_status = first_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": first["run_ref"],
        }
    )
    assert first_status["state"] == "completed"
    first_renditions = {
        work.work_id: work.output["artifacts"][0]["artifact_ref"]
        for work in WorkStore(database).list_run_work(first_accounting)
        if work.spec.capability == "image-rendition"
    }

    second_accounting = AccountingStore(database).start_or_resume_run(
        "dataset-a", source
    )
    second_tool = PrecheckRunTool(database, execution_config=config)
    second = second_tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:reuse-second",
        }
    )
    second_tool.advance(str(second["run_ref"]))
    second_status = second_tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": second["run_ref"],
        }
    )
    second_renditions = {
        work.work_id: work.output["artifacts"][0]["artifact_ref"]
        for work in WorkStore(database).list_run_work(second_accounting)
        if work.spec.capability == "image-rendition"
    }

    assert second_status["state"] == "completed"
    assert second_status["result"]["ref"] != first_status["result"]["ref"]
    assert second_renditions == first_renditions
