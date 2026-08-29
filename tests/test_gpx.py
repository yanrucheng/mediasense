from __future__ import annotations

import json
from pathlib import Path
import subprocess

from jsonschema import Draft202012Validator
from PIL import Image

from mediasense.precheck import (
    AccountingStore,
    GPXMatchProducer,
    GPXMatchProfile,
    ImageRenditionProducer,
    MetadataProducer,
    PrecheckReadTool,
    ResultStore,
    WorkStatus,
)


class TimeOnlyExifTool:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, command) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.calls.append(command)
        if command[-1] == "-ver":
            return subprocess.CompletedProcess(command, 0, "13.30\n", "")
        records = [
            {
                "SourceFile": value,
                "EXIF:DateTimeOriginal": "2026:05:04 20:27:28+08:00",
                "File:MIMEType": "image/jpeg",
            }
            for value in command[command.index("--") + 1 :]
        ]
        return subprocess.CompletedProcess(command, 0, json.dumps(records), "")


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


def _gpx(points: list[tuple[str, float, float]]) -> str:
    rows = "".join(
        f'<trkpt lat="{lat}" lon="{lon}"><time>{time}</time></trkpt>'
        for time, lat, lon in points
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{rows}</trkseg></trk></gpx>"
    )


def test_gpx_match_is_reusable_and_tracks_exact_adopted_inputs(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"image")
    (source / "track.gpx").write_text(
        _gpx(
            [
                ("2026-05-04T12:26:28Z", 22.0, 114.0),
                ("2026-05-04T12:28:28Z", 24.0, 116.0),
            ]
        ),
        encoding="utf-8",
    )
    runner = TimeOnlyExifTool()
    run_id = _closed_run(database, source)
    metadata = MetadataProducer(database, command_runner=runner).produce(
        run_id, Path("photo.jpg")
    )
    outcome = GPXMatchProducer(database).produce(
        run_id,
        metadata.work.work_id,
        [Path("track.gpx")],
        profile=GPXMatchProfile(max_time_difference_seconds=120),
    )

    assert outcome.work.status is WorkStatus.SUCCEEDED
    observation = outcome.observations[0]
    assert observation["status"] == "available"
    assert observation["value"] == {
        "datum": "WGS84",
        "latitude": 23.0,
        "longitude": 115.0,
    }
    assert observation["provenance"]["method"] == "linear_interpolation"

    second_run = _closed_run(database, source)
    reused_metadata = MetadataProducer(database, command_runner=runner).produce(
        second_run, Path("photo.jpg")
    )
    reused = GPXMatchProducer(database).produce(
        second_run,
        reused_metadata.work.work_id,
        [Path("track.gpx")],
        profile=GPXMatchProfile(max_time_difference_seconds=120),
    )
    assert reused.work.work_id == outcome.work.work_id
    assert reused.reused is True

    (source / "track.gpx").write_text(
        _gpx([("2026-05-04T12:27:28Z", 20.0, 110.0)]), encoding="utf-8"
    )
    third_run = _closed_run(database, source)
    same_metadata = MetadataProducer(database, command_runner=runner).produce(
        third_run, Path("photo.jpg")
    )
    replacement = GPXMatchProducer(database).produce(
        third_run, same_metadata.work.work_id, [Path("track.gpx")]
    )
    assert replacement.work.work_id != outcome.work.work_id
    assert replacement.observations[0]["value"]["latitude"] == 20.0


def test_bad_gpx_is_localized_and_result_retains_selected_track_basis(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    Image.new("RGB", (80, 60), "blue").save(media)
    (source / "good.gpx").write_text(
        _gpx([("2026-05-04T12:27:28Z", 22.3, 114.1)]), encoding="utf-8"
    )
    (source / "bad.gpx").write_text("not xml", encoding="utf-8")
    run_id = _closed_run(database, source)
    metadata = MetadataProducer(
        database,
        command_runner=TimeOnlyExifTool(),
        exiftool_version="13.30",
    ).produce(run_id, Path("photo.jpg"))
    match = GPXMatchProducer(database).produce(
        run_id,
        metadata.work.work_id,
        [Path("bad.gpx"), Path("good.gpx")],
    )
    rendition = ImageRenditionProducer(database).produce(run_id, Path("photo.jpg"))

    assert match.work.status is WorkStatus.SUCCEEDED
    assert match.observations[0]["status"] == "available"
    assert match.observations[0]["qualifications"][0]["code"] == "gpx_inputs_partial"
    results = ResultStore(database)
    sealed = results.seal(
        results.build_minimal(
            run_id,
            [rendition.work.work_id],
            metadata_work_ids=[metadata.work.work_id],
            gpx_work_ids=[match.work.work_id],
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
    source_ref = next(
        item["target"]
        for item in accounted["items"]
        if reader.read(
            {
                "result_ref": sealed.result_ref,
                "action": "inspect",
                "target": {"kind": "source_item", "ref": item["target"]},
            }
        )["target"]["locator"]["value"]
        == "photo.jpg"
    )
    view = reader.read(
        {
            "result_ref": sealed.result_ref,
            "action": "inspect",
            "target": {"kind": "source_item", "ref": source_ref},
        }
    )["target"]
    observation = next(
        item for item in view["observations"] if item["name"] == "gpx_coordinates"
    )
    assert len(observation["basis"]["refs"]) == 2
    assert observation["qualifications"][0]["code"] == "gpx_inputs_partial"
    schema = json.loads(
        (
            Path(__file__).parents[1]
            / "docs/spec/spec-260826-1546-precheck-read/precheck-read.tool.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator(schema["outputSchema"]).validate(
        {
            "outcome": "ok",
            "result_ref": sealed.result_ref,
            "action": "inspect",
            "target": view,
        }
    )
