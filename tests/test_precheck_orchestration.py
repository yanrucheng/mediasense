from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
import subprocess
from threading import Event, Thread

from PIL import Image
import pytest

from mediasense.geo import (
    AdaptiveReverseGeocoder,
    GeoCoordinate,
    GeoProviderResult,
    MapDatum,
)
from mediasense.precheck import (
    AccountingStore,
    Detection,
    EmbeddingProfile,
    PrecheckReadTool,
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


class FakeExifTool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

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
                        "Composite:GPSLatitude": 22.3193,
                        "Composite:GPSLongitude": 114.1694,
                        "File:MIMEType": (
                            "video/mp4"
                            if path.suffix.casefold() == ".mp4"
                            else "image/jpeg"
                        ),
                    }
                )
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

    def encode_image(self, image_path: Path) -> tuple[float, ...]:
        with Image.open(image_path) as image:
            width, height = image.size
        return float(width), float(height), 1.0, 2.0


class FakeSensitivityDetector:
    identity = "fake-local-sensitivity@sha256:one"

    def detect(self, _image_path: Path) -> tuple[Detection, ...]:
        return (Detection("ordinary", 0.1),)


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
                "formatted_address": "Kowloon, Hong Kong",
                "components": {"country": "China", "country_code": "HK"},
            },
            pois=(),
            request_count=2,
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
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            compression_target=3,
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
            embedding_encoder=FakeEncoder(),
            sensitivity_detector=FakeSensitivityDetector(),
        ),
    )

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:mixed-e2e",
        }
    )
    assert started["state"] == "running"
    assert WorkStore(database).list_run_work(_accounting_run_id) == ()
    tool.advance(str(started["run_ref"]))
    status = tool.run({"action": "status", "run_ref": started["run_ref"]})

    assert started["outcome"] == "ok"
    assert status["state"] == "completed", status
    assert status["published_result"]["integrity"] == "valid"
    result_ref = status["published_result"]["result_ref"]
    inspected = PrecheckReadTool(database).read(
        {"action": "inspect", "result_ref": result_ref}
    )
    assert inspected["outcome"] == "ok"
    assert inspected["target"]["ref"] == result_ref
    assert inspected["target"]["coverage"] == "complete"
    assert inspected["target"]["readiness"] == "plan_ready"
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


def test_default_orchestration_makes_no_external_requests(tmp_path: Path) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (32, 24), "navy").save(source / "photo.jpg")

    class RejectNetwork:
        def lookup(self, _coordinate):
            raise AssertionError("default PreCheck must not invoke a provider")

        def reset(self) -> None:
            pass

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
            geocoder=RejectNetwork()  # type: ignore[arg-type]
        ),
    )
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:zero-network",
        }
    )
    tool.advance(str(started["run_ref"]))
    status = tool.run({"action": "status", "run_ref": started["run_ref"]})
    assert status["state"] == "completed"


def test_geocode_pauses_for_exact_frozen_query_count_before_fake_provider(
    tmp_path: Path,
) -> None:
    database, source, _accounting_run_id = _prepare_source_bound_run(tmp_path)
    for name, color in (("a.jpg", "red"), ("b.jpg", "blue")):
        Image.new("RGB", (48, 32), color).save(source / name)
    provider = FakeGeocodeProvider()
    geocoder = AdaptiveReverseGeocoder(
        providers={provider.provider_id: provider},
        provider_order=(provider.provider_id,),
        initial_provider=provider.provider_id,
        initial_language="zh",
    )
    base = PrecheckExecutionConfig()
    capacity = replace(base.resource_budget.capacity, network_slots=1)
    config = replace(
        base,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=2,
        reverse_geocode_profile=replace(
            base.reverse_geocode_profile,
            enabled=True,
            provider_profile="fake-maps-v1",
        ),
        resource_budget=replace(base.resource_budget, capacity=capacity),
    )
    tool = PrecheckRunTool(
        database,
        execution_config=config,
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=FakeExifTool(),
            exiftool_version="13.30",
            geocoder=geocoder,
        ),
    )

    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:geocode-e2e",
        }
    )
    tool.advance(str(started["run_ref"]))
    paused = tool.run({"action": "status", "run_ref": started["run_ref"]})
    assert paused["state"] == "paused"
    assert paused["reason"]["code"] == "confirmation_required"
    assert paused["confirmation"]["quantity"] == 1
    assert paused["confirmation"]["unit"] == "logical_queries"
    assert provider.calls == []

    resumed = tool.run(
        {
            "action": "resume",
            "run_ref": started["run_ref"],
            "decision": "proceed",
        }
    )
    assert (
        tool.run({"action": "status", "run_ref": started["run_ref"]})["state"]
        == "running"
    )
    assert provider.calls == []
    tool.advance(str(started["run_ref"]))
    completed = tool.run({"action": "status", "run_ref": started["run_ref"]})

    assert resumed["outcome"] == "accepted"
    assert completed["state"] == "completed", completed
    assert len(provider.calls) == 1
    result_ref = completed["published_result"]["result_ref"]
    inspected = PrecheckReadTool(database).read(
        {"action": "inspect", "result_ref": result_ref}
    )
    boundary = inspected["target"]["execution_boundary"]
    assert boundary["logical_external_queries"] == 1
    assert boundary["provider_requests"] == 2


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
    tool.advance(str(started["run_ref"]))
    status = tool.run({"action": "status", "run_ref": started["run_ref"]})

    assert status["state"] == "completed"
    assert status["progress"] == {
        "discovered": 2,
        "accounted": 2,
        "usable": 1,
        "exceptional": 1,
        "unresolved": 0,
    }
    works = WorkStore(database).list_run_work(accounting_run_id)
    assert sum(work.status.value == "succeeded" for work in works) >= 2
    assert sum(work.status.value == "terminal_failure" for work in works) == 1


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
    assert started["state"] == "running"
    worker_results: list[dict[str, object]] = []
    worker = Thread(
        target=lambda: worker_results.append(tool.advance(str(started["run_ref"])))
    )
    worker.start()
    assert reached_boundary.wait(timeout=5)
    accepted_pause = tool.run({"action": "pause", "run_ref": started["run_ref"]})
    release_worker.set()
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert worker_results[0]["state"] == "paused"
    assert accepted_pause["outcome"] == "accepted"
    paused = tool.run({"action": "status", "run_ref": started["run_ref"]})
    assert paused["state"] == "paused"
    assert paused["reason"]["code"] == "user_requested"

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", original)
    accepted_resume = tool.run({"action": "resume", "run_ref": started["run_ref"]})
    assert accepted_resume["outcome"] == "accepted"
    assert (
        tool.run({"action": "status", "run_ref": started["run_ref"]})["state"]
        == "running"
    )
    tool.advance(str(started["run_ref"]))
    assert (
        tool.run({"action": "status", "run_ref": started["run_ref"]})["state"]
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
        {"action": "cancel", "run_ref": cancelled_start["run_ref"]}
    )
    release_cancelled_worker.set()
    cancel_worker.join(timeout=5)
    assert not cancel_worker.is_alive()
    assert cancel_results[0]["state"] == "cancelled"
    assert accepted_cancel["outcome"] == "accepted"
    cancelled = cancel_tool.run(
        {"action": "status", "run_ref": cancelled_start["run_ref"]}
    )
    assert cancelled["state"] == "cancelled"
    assert "published_result" not in cancelled


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
    with pytest.raises(KeyboardInterrupt, match="simulated process loss"):
        first_tool.advance(run_ref)
    before = {
        work.work_id
        for work in WorkStore(database).list_run_work(accounting_run_id)
        if work.spec.capability == "image-rendition"
    }
    assert len(before) == 1

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", original)
    restarted = PrecheckRunTool(database, execution_config=config)
    resumed = restarted.run({"action": "resume", "run_ref": run_ref})
    restarted.advance(run_ref)
    completed = restarted.run({"action": "status", "run_ref": run_ref})
    after = {
        work.work_id
        for work in WorkStore(database).list_run_work(accounting_run_id)
        if work.spec.capability == "image-rendition"
    }

    assert resumed["outcome"] == "accepted"
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
    with pytest.raises(KeyboardInterrupt, match="simulated crash before seal"):
        tool.advance(str(started["run_ref"]))
    assert ResultStore(database).audit().available == ()

    monkeypatch.setattr(PrecheckOrchestrator, "_after_phase", original)
    restarted = PrecheckRunTool(database, execution_config=config)
    restarted.run({"action": "resume", "run_ref": started["run_ref"]})
    restarted.advance(str(started["run_ref"]))
    completed = restarted.run({"action": "status", "run_ref": started["run_ref"]})
    assert completed["state"] == "completed"
    assert ResultStore(database).audit().available == (
        completed["published_result"]["result_ref"],
    )


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
    tool.advance(str(started["run_ref"]))
    interrupted = tool.run({"action": "status", "run_ref": started["run_ref"]})
    audit = ResultStore(database).audit()
    assert interrupted["state"] == "paused"
    assert interrupted["reason"]["code"] == "process_interrupted"
    assert audit.available == ()
    assert len(audit.orphan_paths) == 1

    monkeypatch.undo()
    restarted = PrecheckRunTool(database, execution_config=config)
    restarted.run({"action": "resume", "run_ref": started["run_ref"]})
    restarted.advance(str(started["run_ref"]))
    completed = restarted.run({"action": "status", "run_ref": started["run_ref"]})
    recovered = ResultStore(database).audit()
    assert completed["state"] == "completed", completed
    assert recovered.orphan_paths == ()
    assert recovered.available == (completed["published_result"]["result_ref"],)


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
    with pytest.raises(KeyboardInterrupt, match="after Result registration"):
        tool.advance(str(started["run_ref"]))
    record = tool._store.get(str(started["run_ref"]))
    available = ResultStore(database).audit().available
    assert len(available) == 1
    assert record["state"] == "running"

    monkeypatch.setattr(PrecheckRunTool, "complete_with_result", original)
    restarted = PrecheckRunTool(database, execution_config=config)
    restarted.run({"action": "resume", "run_ref": record["run_ref"]})
    restarted.advance(str(record["run_ref"]))
    completed = restarted.run({"action": "status", "run_ref": record["run_ref"]})
    assert completed["state"] == "completed"
    assert completed["published_result"]["result_ref"] == available[0]


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
    first_tool.advance(str(first["run_ref"]))
    first_status = first_tool.run({"action": "status", "run_ref": first["run_ref"]})
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
    second_status = second_tool.run({"action": "status", "run_ref": second["run_ref"]})
    second_renditions = {
        work.work_id: work.output["artifacts"][0]["artifact_ref"]
        for work in WorkStore(database).list_run_work(second_accounting)
        if work.spec.capability == "image-rendition"
    }

    assert second_status["state"] == "completed"
    assert (
        second_status["published_result"]["result_ref"]
        != first_status["published_result"]["result_ref"]
    )
    assert second_renditions == first_renditions
