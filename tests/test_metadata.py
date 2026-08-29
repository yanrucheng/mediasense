from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

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


def test_metadata_work_uses_exact_source_and_sidecar_inputs_and_reuses(
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
            "result_ref": sealed.result_ref,
            "action": "traverse",
            "relation": "accounts_for",
            "direction": "outbound",
        }
    )
    source_refs = {}
    for item in accounted["items"]:
        source_ref = item["target"]
        source_view = reader.read(
            {
                "result_ref": sealed.result_ref,
                "action": "inspect",
                "target": {"kind": "source_item", "ref": source_ref},
            }
        )["target"]
        source_refs[source_view["locator"]["value"]] = source_ref
    good_view = reader.read(
        {
            "result_ref": sealed.result_ref,
            "action": "inspect",
            "target": {"kind": "source_item", "ref": source_refs["good.jpg"]},
        }
    )["target"]
    bad_view = reader.read(
        {
            "result_ref": sealed.result_ref,
            "action": "inspect",
            "target": {"kind": "source_item", "ref": source_refs["bad.jpg"]},
        }
    )["target"]

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
