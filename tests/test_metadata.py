from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import subprocess
from threading import Event, Lock, current_thread
import time

from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    MetadataProducer,
    PrecheckReadTool,
    ResultStore,
    WorkStatus,
)
from mediasense.precheck._exiftool import ExifToolCancelled, StayOpenExifTool
from mediasense.precheck.metadata import MetadataLeaseRenewalError


class ControlledClock:
    def __init__(self) -> None:
        self._value = datetime(2026, 9, 1, tzinfo=timezone.utc)
        self._lock = Lock()

    def __call__(self) -> datetime:
        with self._lock:
            return self._value

    def advance(self, seconds: float) -> None:
        with self._lock:
            self._value += timedelta(seconds=seconds)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


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
            fields = {"SourceFile": str(path)}
            if path.suffix.casefold() == ".xmp":
                fields.update(
                    {
                        "XMP:DateTimeOriginal": "2026:05:04 20:27:28+08:00",
                        "XMP:Make": "DJI",
                    }
                )
            else:
                fields.update(
                    {
                        "Composite:GPSLatitude": 22.3193,
                        "Composite:GPSLongitude": 114.1694,
                        "File:MIMEType": "image/jpeg",
                    }
                )
            records.append(fields)
        import json

        return subprocess.CompletedProcess(command, 0, json.dumps(records), "")


def test_metadata_many_subjects_share_one_exiftool_command(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    subjects = tuple(Path(f"photo-{index}.jpg") for index in range(5))
    for subject in subjects:
        (source / subject).write_bytes(subject.as_posix().encode())
    run_id = _closed_run(database, source)
    runner = FakeExifTool()
    producer = MetadataProducer(database, command_runner=runner)

    outcomes = producer.produce_many(run_id, subjects)

    assert set(outcomes) == set(subjects)
    assert all(
        outcome.work.status is WorkStatus.SUCCEEDED for outcome in outcomes.values()
    )
    assert len(runner.calls) == 2  # one version command plus one multi-item extraction
    paths = runner.calls[-1][runner.calls[-1].index("--") + 1 :]
    assert len(paths) == len(subjects)


def test_result_is_plan_ready_when_a_located_source_lacks_geocode_outcome(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (40, 30), "blue").save(source / "photo.jpg")
    run_id = _closed_run(database, source)
    metadata = MetadataProducer(database, command_runner=FakeExifTool()).produce(
        run_id, Path("photo.jpg")
    )
    rendition = ImageRenditionProducer(database).produce(run_id, Path("photo.jpg"))

    draft = ResultStore(database).build_minimal(
        run_id,
        [rendition.work.work_id],
        metadata_work_ids=[metadata.work.work_id],
    )

    assert draft.readiness == "plan_ready"
    components = {item["name"]: item for item in draft.sources[0].observations}
    assert components["address_candidate"]["status"] == "not_checked"
    assert components["nearby_place_candidates"]["status"] == "not_checked"
    sealed = ResultStore(database).seal(draft)
    assert sealed.result_ref.startswith("precheck-result:")


def test_real_exiftool_stay_open_process_is_reused_and_closed(tmp_path: Path) -> None:
    executable = shutil.which("exiftool")
    if executable is None:
        pytest.skip("ExifTool is not installed")
    image = tmp_path / "micro.jpg"
    Image.new("RGB", (4, 3), "red").save(image)
    runner = StayOpenExifTool(executable, timeout=10)
    try:
        first = runner((executable, "-j", "-File:MIMEType", "--", str(image)))
        assert first.returncode == 0
        process = runner._process
        assert process is not None
        first_pid = process.pid
        second = runner((executable, "-j", "-File:FileSize", "--", str(image)))
        assert second.returncode == 0
        assert runner._process is not None
        assert runner._process.pid == first_pid
        assert runner.start_count == 1
        runner._process.kill()
        runner._process.wait(timeout=5)
        restarted = runner((executable, "-ver"))
        assert restarted.returncode == 0
        assert runner.start_count == 2
    finally:
        runner.close()
    assert runner._process is None


def test_stay_open_exiftool_honors_cancellation_before_start() -> None:
    runner = StayOpenExifTool("exiftool", should_continue=lambda: False)

    with pytest.raises(ExifToolCancelled):
        runner(("exiftool", "-ver"))

    assert runner.start_count == 0


def test_metadata_batch_subdivision_isolates_one_bad_subject(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    subjects = (Path("bad.jpg"), Path("good-a.jpg"), Path("good-b.jpg"))
    for subject in subjects:
        (source / subject).write_bytes(subject.as_posix().encode())
    run_id = _closed_run(database, source)
    calls: list[tuple[str, ...]] = []

    def split_runner(command) -> subprocess.CompletedProcess[str]:
        import json

        command = tuple(command)
        calls.append(command)
        paths = [Path(value) for value in command[command.index("--") + 1 :]]
        if Path(source / "bad.jpg") in paths:
            return subprocess.CompletedProcess(command, 1, "", "bad metadata")
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                [
                    {"SourceFile": str(path), "File:MIMEType": "image/jpeg"}
                    for path in paths
                ]
            ),
            "",
        )

    outcomes = MetadataProducer(
        database,
        command_runner=split_runner,
        exiftool_version="13.30",
    ).produce_many(run_id, subjects)

    assert outcomes[Path("bad.jpg")].work.status is WorkStatus.TERMINAL_FAILURE
    assert outcomes[Path("good-a.jpg")].work.status is WorkStatus.SUCCEEDED
    assert outcomes[Path("good-b.jpg")].work.status is WorkStatus.SUCCEEDED
    assert len(calls) == 3  # failed batch, isolated bad item, successful sibling batch


def test_metadata_heartbeat_renews_batch_beyond_original_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    subjects = (Path("a.jpg"), Path("b.jpg"))
    for subject in subjects:
        (source / subject).write_bytes(subject.as_posix().encode())
    run_id = _closed_run(database, source)
    clock = ControlledClock()
    original_expiry = clock() + timedelta(seconds=10)
    renewed = Event()
    renewal_count = 0

    def runner(command) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        paths = [Path(value) for value in command[command.index("--") + 1 :]]
        clock.advance(6)
        assert renewed.wait(timeout=2)
        clock.advance(6)
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                [
                    {"SourceFile": str(path), "File:MIMEType": "image/jpeg"}
                    for path in paths
                ]
            ),
            "",
        )

    producer = MetadataProducer(
        database,
        command_runner=runner,
        exiftool_version="13.30",
        lease_duration=timedelta(seconds=10),
        lease_renew_interval=0.01,
        clock=clock,
    )
    original_renew = producer.work.renew_lease

    def tracked_renew(*args, **kwargs):
        nonlocal renewal_count
        result = original_renew(*args, **kwargs)
        renewal_count += 1
        if clock() >= original_expiry - timedelta(seconds=4):
            renewed.set()
        return result

    monkeypatch.setattr(producer.work, "renew_lease", tracked_renew)

    outcomes = producer.produce_many(run_id, subjects)

    assert clock() > original_expiry
    assert renewal_count >= len(subjects) * 2
    assert all(
        outcome.work.status is WorkStatus.SUCCEEDED for outcome in outcomes.values()
    )


def test_metadata_heartbeat_failure_releases_active_leases_for_immediate_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    subjects = (Path("a.jpg"), Path("b.jpg"))
    for subject in subjects:
        (source / subject).write_bytes(subject.as_posix().encode())
    run_id = _closed_run(database, source)
    heartbeat_failed = Event()

    def runner(command) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        paths = [Path(value) for value in command[command.index("--") + 1 :]]
        assert heartbeat_failed.wait(timeout=2)
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                [
                    {"SourceFile": str(path), "File:MIMEType": "image/jpeg"}
                    for path in paths
                ]
            ),
            "",
        )

    producer = MetadataProducer(
        database,
        command_runner=runner,
        exiftool_version="13.30",
        lease_renew_interval=0.01,
    )
    original_renew = producer.work.renew_lease

    def failing_renew(*args, **kwargs):
        if current_thread().name == "mediasense-metadata-lease-heartbeat":
            heartbeat_failed.set()
            raise OSError("injected heartbeat renewal failure")
        return original_renew(*args, **kwargs)

    monkeypatch.setattr(producer.work, "renew_lease", failing_renew)

    with pytest.raises(MetadataLeaseRenewalError, match="lease renewal failed"):
        producer.produce_many(run_id, subjects)

    failed = tuple(producer.work.iter_run_work(run_id, capability="source-metadata"))
    assert len(failed) == len(subjects)
    assert all(record.status is WorkStatus.RETRYABLE_FAILURE for record in failed)
    assert all(
        record.last_failure_code == "metadata_lease_renewal_failed" for record in failed
    )

    retried = MetadataProducer(
        database,
        command_runner=FakeExifTool(),
        exiftool_version="13.30",
    ).produce_many(run_id, subjects)

    assert all(
        outcome.work.status is WorkStatus.SUCCEEDED for outcome in retried.values()
    )
    assert all(outcome.work.attempt_count == 2 for outcome in retried.values())


def test_metadata_recursive_isolation_renews_all_active_leases(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    subjects = tuple(Path(f"item-{index}.jpg") for index in range(8))
    for subject in subjects:
        (source / subject).write_bytes(subject.as_posix().encode())
    run_id = _closed_run(database, source)
    clock = ControlledClock()
    calls = 0

    def runner(command) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        command = tuple(command)
        calls += 1
        paths = [Path(value) for value in command[command.index("--") + 1 :]]
        clock.advance(1)
        time.sleep(0.02)
        if source / "item-0.jpg" in paths:
            return subprocess.CompletedProcess(command, 1, "", "bad metadata")
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                [
                    {"SourceFile": str(path), "File:MIMEType": "image/jpeg"}
                    for path in paths
                ]
            ),
            "",
        )

    outcomes = MetadataProducer(
        database,
        command_runner=runner,
        exiftool_version="13.30",
        lease_duration=timedelta(seconds=3),
        lease_renew_interval=0.01,
        clock=clock,
    ).produce_many(run_id, subjects)

    assert calls >= 4
    assert clock() > datetime(2026, 9, 1, tzinfo=timezone.utc) + timedelta(seconds=3)
    assert outcomes[subjects[0]].work.status is WorkStatus.TERMINAL_FAILURE
    assert all(
        outcomes[subject].work.status is WorkStatus.SUCCEEDED
        for subject in subjects[1:]
    )


def test_metadata_cancellation_converges_leases_and_preserves_successful_sibling(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    subjects = tuple(Path(f"item-{index}.jpg") for index in range(4))
    for subject in subjects:
        (source / subject).write_bytes(subject.as_posix().encode())
    run_id = _closed_run(database, source)
    calls = 0

    def cancelling_runner(command) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        command = tuple(command)
        calls += 1
        paths = [Path(value) for value in command[command.index("--") + 1 :]]
        if calls == 1:
            return subprocess.CompletedProcess(command, 1, "", "split")
        if calls == 3:
            raise ExifToolCancelled("cancelled")
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                [
                    {"SourceFile": str(path), "File:MIMEType": "image/jpeg"}
                    for path in paths
                ]
            ),
            "",
        )

    producer = MetadataProducer(
        database,
        command_runner=cancelling_runner,
        exiftool_version="13.30",
    )
    with pytest.raises(ExifToolCancelled):
        producer.produce_many(run_id, subjects)

    work_by_subject = {
        next(
            dependency.value
            for dependency in record.spec.dependencies
            if dependency.key == "subject_relative_path"
        ): record
        for record in producer.work.iter_run_work(run_id, capability="source-metadata")
    }
    assert {record.status for record in work_by_subject.values()} == {
        WorkStatus.SUCCEEDED,
        WorkStatus.RETRYABLE_FAILURE,
    }
    assert (
        sum(
            record.status is WorkStatus.SUCCEEDED for record in work_by_subject.values()
        )
        == 2
    )
    assert all(
        record.status is not WorkStatus.RUNNING for record in work_by_subject.values()
    )

    replay_runner = FakeExifTool()
    replay = MetadataProducer(
        database,
        command_runner=replay_runner,
        exiftool_version="13.30",
    ).produce_many(run_id, subjects)

    assert sum(outcome.reused for outcome in replay.values()) == 2
    assert all(
        outcome.work.status is WorkStatus.SUCCEEDED for outcome in replay.values()
    )
    replay_paths = replay_runner.calls[-1][replay_runner.calls[-1].index("--") + 1 :]
    assert len(replay_paths) == 2


def test_metadata_work_uses_revision_bound_source_and_sidecar_inputs_and_reuses(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"image bytes")
    (source / "photo.xmp").write_text("sidecar", encoding="utf-8")
    source_bytes = {
        path.name: path.read_bytes() for path in source.iterdir() if path.is_file()
    }
    runner = FakeExifTool()

    first_run = _closed_run(database, source)
    producer = MetadataProducer(database, command_runner=runner)
    first = producer.produce(first_run, Path("photo.jpg"))

    assert first.work.status is WorkStatus.SUCCEEDED
    assert first.reused is False
    assert len(runner.calls) == 2  # version plus one bounded extraction
    command = runner.calls[-1]
    assert command[1:6] == ("-j", "-G", "-n", "-api", "largefilesupport=1")
    metadata_profile = next(
        dependency.value
        for dependency in first.work.spec.dependencies
        if dependency.key == "metadata_profile"
    )
    assert json.loads(metadata_profile)["profile_id"] == "index-v1"
    assert str(source / "photo.jpg") in command
    assert str(source / "photo.xmp") in command
    capture = next(
        item for item in first.observations if item["name"] == "capture_time"
    )
    assert capture["provenance"]["relative_path"] == "photo.xmp"

    second_run = _closed_run(database, source)
    reused = producer.produce(second_run, Path("photo.jpg"))
    assert reused.work.work_id == first.work.work_id
    assert reused.reused is True
    assert len(runner.calls) == 2
    assert {
        path.name: path.read_bytes() for path in source.iterdir() if path.is_file()
    } == source_bytes

    (source / "photo.xmp").write_text("changed sidecar", encoding="utf-8")
    third_run = _closed_run(database, source)
    replacement = producer.produce(third_run, Path("photo.jpg"))
    assert replacement.work.work_id != first.work.work_id
    assert replacement.work.status is WorkStatus.SUCCEEDED
    assert len(runner.calls) == 3


def test_source_change_during_metadata_extraction_invalidates_work(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"original bytes")
    run_id = _closed_run(database, source)

    def mutate(command) -> subprocess.CompletedProcess[str]:
        media.write_bytes(b"changed during extraction")
        import json

        return subprocess.CompletedProcess(
            tuple(command),
            0,
            json.dumps([{"SourceFile": str(media), "EXIF:Make": "Camera"}]),
            "",
        )

    outcome = MetadataProducer(
        database,
        command_runner=mutate,
        exiftool_version="13.30",
    ).produce(run_id, Path("photo.jpg"))

    assert outcome.work.status is WorkStatus.INVALIDATED
    assert outcome.observations == ()


def test_metadata_failure_is_local_and_result_exposes_field_provenance(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    good_path = source / "good.jpg"
    bad_path = source / "bad.jpg"
    Image.new("RGB", (80, 60), "blue").save(good_path)
    Image.new("RGB", (80, 60), "red").save(bad_path)
    runner = FakeExifTool()
    run_id = _closed_run(database, source)
    metadata = MetadataProducer(database, command_runner=runner)
    good = metadata.produce(run_id, Path("good.jpg"))

    def fail(command) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(tuple(command), 1, "", "bad metadata")

    failing = MetadataProducer(
        database,
        command_runner=fail,
        exiftool_version="13.30",
    ).produce(run_id, Path("bad.jpg"))
    rendition = ImageRenditionProducer(database).produce(run_id, Path("good.jpg"))

    assert good.work.status is WorkStatus.SUCCEEDED
    assert failing.work.status is WorkStatus.TERMINAL_FAILURE
    assert rendition.work.status is WorkStatus.SUCCEEDED
    result = ResultStore(database)
    sealed = result.seal(
        result.build_minimal(
            run_id,
            [rendition.work.work_id],
            metadata_work_ids=[good.work.work_id, failing.work.work_id],
        )
    )
    reader = PrecheckReadTool(database)
    accounted = reader.read(
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
    source_refs = {
        item["locator"]["value"]: item["source_item_ref"]
        for item in accounted["members"]
    }
    expanded = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "source_item_refs": [source_refs["good.jpg"], source_refs["bad.jpg"]],
            "include": ["source_item", "observations"],
        }
    )
    views = {item["source_item_ref"]: item["included"] for item in expanded["items"]}
    good_view = views[source_refs["good.jpg"]]
    bad_view = views[source_refs["bad.jpg"]]

    gps = next(
        item for item in good_view["observations"] if item["name"] == "gps_coordinates"
    )
    assert gps["value"]["datum"] == "WGS84"
    assert gps["basis"]["refs"] == [
        {"kind": "source_item", "ref": source_refs["good.jpg"]}
    ]
    failed_metadata = next(
        item for item in bad_view["observations"] if item["name"] == "source_metadata"
    )
    assert failed_metadata["status"] == "failed"


@pytest.mark.skipif(
    shutil.which("exiftool") is None, reason="ExifTool is not installed"
)
def test_installed_exiftool_extracts_real_local_metadata_without_source_writes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    Image.new("RGB", (40, 30), "green").save(media)
    subprocess.run(
        (
            "exiftool",
            "-overwrite_original",
            "-EXIF:DateTimeOriginal=2026:05:04 20:27:28",
            "-EXIF:Make=Canon",
            "-EXIF:Model=EOS Test",
            "-EXIF:GPSLatitude=22.3193",
            "-EXIF:GPSLongitude=114.1694",
            "-EXIF:GPSLatitudeRef=N",
            "-EXIF:GPSLongitudeRef=E",
            str(media),
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    source_bytes = media.read_bytes()
    run_id = _closed_run(database, source)

    outcome = MetadataProducer(database).produce(run_id, Path("photo.jpg"))

    assert outcome.work.status is WorkStatus.SUCCEEDED
    assert media.read_bytes() == source_bytes
    observations = {item["name"]: item for item in outcome.observations}
    assert observations["capture_time"]["value"] == "2026-05-04T20:27:28+08:00"
    assert observations["camera_make"]["value"] == "Canon"
    assert observations["camera_model"]["value"] == "EOS Test"
    assert observations["gps_coordinates"]["value"] == {
        "datum": "WGS84",
        "latitude": 22.3193,
        "longitude": 114.1694,
    }
