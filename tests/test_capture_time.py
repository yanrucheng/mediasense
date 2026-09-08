"""Discriminating temporal cases independent of the Hong Kong package."""

from datetime import datetime
import json
from pathlib import Path
import subprocess

import pytest
from PIL import Image

from mediasense.precheck import (
    AccountingStore,
    GPXMatchProducer,
    GPXMatchProfile,
    ImageRenditionProducer,
    ResultStore,
    PrecheckReadTool,
)
from mediasense.precheck.metadata import (
    MetadataProducer,
    MetadataProfile,
    select_metadata_observations,
)
from mediasense.precheck._compression_strategy import (
    AdaptiveCompressionProfile,
    CompressionPoint,
    build_adaptive_groups,
)


def capture(fields, name="clip.mp4", timezone="Asia/Shanghai"):
    path = Path(name)
    return select_metadata_observations(
        [{"relative_path": name, "fields": fields}],
        subject=path,
        source_precedence=(path,),
        profile=MetadataProfile(timezone=timezone),
    )[0]


@pytest.mark.parametrize(
    "fields,zone,expected",
    [
        (
            {"QuickTime:CreateDate": "2026:05:04 09:33:46"},
            "Asia/Shanghai",
            "2026-05-04T17:33:46+08:00",
        ),
        (
            {"QuickTime:CreateDate": "2026:05:04 09:33:46Z"},
            "Asia/Shanghai",
            "2026-05-04T17:33:46+08:00",
        ),
        (
            {"QuickTime:CreateDate": "2026:05:04 09:33:46-04:00"},
            "Asia/Shanghai",
            "2026-05-04T21:33:46+08:00",
        ),
        (
            {"QuickTime:CreateDate": "2026:07:04 09:33:46"},
            "America/New_York",
            "2026-07-04T05:33:46-04:00",
        ),
        (
            {"EXIF:Make": "DJI", "EXIF:DateTimeOriginal": "2026:05:04 17:33:46"},
            "Asia/Shanghai",
            "2026-05-04T17:33:46+08:00",
        ),
        (
            {
                "EXIF:Make": "Canon",
                "EXIF:Model": "EOS 80D",
                "EXIF:DateTimeOriginal": "2026:05:04 17:33:46",
            },
            "Asia/Shanghai",
            "2026-05-04T17:33:46+08:00",
        ),
        (
            {
                "EXIF:Make": "SONY",
                "EXIF:DateTimeOriginal": "2026:05:04 17:33:46",
                "EXIF:OffsetTimeOriginal": "+09:00",
            },
            "Asia/Shanghai",
            "2026-05-04T16:33:46+08:00",
        ),
    ],
)
def test_field_semantics_are_not_a_blanket_video_or_vendor_shift(
    fields, zone, expected
):
    result = capture(fields, timezone=zone)
    assert result["value"] == expected
    assert result["provenance"]["candidates"][0]["raw_value"] in fields.values()


def test_explicit_camera_time_wins_nonconforming_container_with_visible_conflict():
    result = capture(
        {
            "QuickTime:CreationDate": "2026:05:04 17:33:46+08:00",
            "QuickTime:CreateDate": "2026:05:04 17:33:46",
        }
    )
    assert result["value"] == "2026-05-04T17:33:46+08:00"
    assert result["provenance"]["timezone_assumed"] is False
    assert result["qualifications"][0]["code"] == "capture_time_conflict"
    assert len(result["provenance"]["candidates"]) == 2


def test_remux_fallback_precedes_copy_date_but_never_valid_camera_time():
    fields = {
        "QuickTime:CreateDate": "0000:00:00 00:00:00",
        "File:FileModifyDate": "2026:08:31 06:12:38+08:00",
    }
    result = capture(fields, "CAM_20260504_202728.remux.mp4")
    assert result["value"] == "2026-05-04T20:27:28+08:00"
    assert result["qualifications"][0]["code"] == "filename_time_fallback"
    assert len(result["provenance"]["candidates"]) == 3
    fields["QuickTime:CreateDate"] = "2000:01:01 00:00:00"
    valid = capture(fields, "CAM_20260504_202728.mp4")
    assert valid["value"] == "2000-01-01T08:00:00+08:00"
    assert "capture_time_conflict" in str(valid["qualifications"])
    assert capture({}, "x20261341256199.mp4")["status"] == "missing"
    fallback = capture({"File:FileModifyDate": "2026:08:31 06:12:38+08:00"})
    assert fallback["qualifications"][0]["code"] == "filesystem_time_fallback"


def test_time_policy_recomputes_gpx_and_preserves_sealed_raw_evidence(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (24, 24), "blue").save(source / "photo.jpg")
    (source / "track.gpx").write_text(
        '<gpx version="1.1" creator="test"><trk><trkseg>'
        '<trkpt lat="22" lon="114"><time>2026-05-04T04:00:00Z</time></trkpt>'
        '<trkpt lat="23" lon="115"><time>2026-05-04T12:00:00Z</time></trkpt>'
        "</trkseg></trk></gpx>"
    )
    database = tmp_path / "work.sqlite3"
    store = AccountingStore(database)
    store.register_dataset("test")

    def runner(command):
        assert "QuickTimeUTC=0" in command
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                [
                    {
                        "SourceFile": path,
                        "QuickTime:CreateDate": "2026:05:04 12:00:00",
                        "XMP:CreateDate": "2026:05:04 12:00:00",
                    }
                    for path in command[command.index("--") + 1 :]
                ]
            ),
            "",
        )

    results = []
    for tags in [
        ("XMP:CreateDate",),
        ("QuickTime:CreateDate",),
        ("QuickTime:CreateDate",),
    ]:
        run = store.start_or_resume_run("test", source)
        store.process_run(run)
        with MetadataProducer(
            database, command_runner=runner, exiftool_version="test"
        ) as producer:
            meta = producer.produce(
                run, Path("photo.jpg"), profile=MetadataProfile(time_tags=tags)
            )
        gpx = GPXMatchProducer(database).produce(
            run,
            meta.work.work_id,
            [Path("track.gpx")],
            profile=GPXMatchProfile(max_time_difference_seconds=60),
        )
        rendition = ImageRenditionProducer(database).produce(run, Path("photo.jpg"))
        sealed = ResultStore(database).seal(
            ResultStore(database).build_minimal(
                run,
                [rendition.work.work_id],
                metadata_work_ids=[meta.work.work_id],
                gpx_work_ids=[gpx.work.work_id],
            )
        )
        results.append((meta, gpx, sealed, sealed.path.read_bytes()))
    assert results[0][1].observations[0]["value"]["latitude"] == 22
    assert results[1][1].observations[0]["value"]["latitude"] == 23
    assert results[0][1].work.work_id != results[1][1].work.work_id
    assert results[2][1].reused and results[2][0].reused
    assert results[0][2].path.read_bytes() == results[0][3]
    for meta, _gpx, sealed, _bytes in results:
        data = json.loads(sealed.path.read_bytes())
        source_view = next(
            item["view"]
            for item in data["sources"]
            if item["relative_path"] == "photo.jpg"
        )
        observation = next(
            item
            for item in source_view["observations"]
            if item["name"] == "capture_time"
        )
        assert observation["provenance"]["raw_value"] == "2026:05:04 12:00:00"
        assert observation["value"] == meta.observations[0]["value"]
        assert "error" not in PrecheckReadTool(database).read(
            {
                "action": "review",
                "dataset_ref": "dataset:test",
                "result_ref": sealed.result_ref,
            }
        )


def test_corrected_time_changes_group_membership():
    lunch = CompressionPoint(
        Path("lunch.jpg"), datetime.fromisoformat("2026-05-04T09:34:00+08:00")
    )
    dinner = CompressionPoint(
        Path("dinner.jpg"), datetime.fromisoformat("2026-05-04T17:34:00+08:00")
    )
    corrected = capture({"QuickTime:CreateDate": "2026:05:04 09:33:46"})
    profile = AdaptiveCompressionProfile(target_entries=2)
    old = build_adaptive_groups(
        (
            lunch,
            dinner,
            CompressionPoint(
                Path("clip.mp4"), datetime.fromisoformat("2026-05-04T09:33:46+08:00")
            ),
        ),
        profile,
    )
    new = build_adaptive_groups(
        (
            lunch,
            dinner,
            CompressionPoint(
                Path("clip.mp4"), datetime.fromisoformat(corrected["value"])
            ),
        ),
        profile,
    )
    assert Path("lunch.jpg") in next(
        g.members for g in old if Path("clip.mp4") in g.members
    )
    assert Path("dinner.jpg") in next(
        g.members for g in new if Path("clip.mp4") in g.members
    )
