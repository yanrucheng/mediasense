"""Metadata behavior characterized from AI Album c90 and its fix history."""

from pathlib import Path

import pytest

from mediasense.precheck.metadata import MetadataProfile, select_metadata_observations


@pytest.mark.characterization
def test_sidecar_and_tag_precedence_retain_field_level_basis() -> None:
    observations = select_metadata_observations(
        (
            {
                "relative_path": "IMG_0001.JPG",
                "fields": {
                    "EXIF:DateTimeOriginal": "2024:06:15 14:30:00",
                    "EXIF:Make": "Camera body",
                },
            },
            {
                "relative_path": "IMG_0001.xmp",
                "fields": {
                    "XMP:DateTimeOriginal": "2024:06:15 15:31:02+08:00",
                    "XMP:Make": "Sidecar correction",
                },
            },
        ),
        subject=Path("IMG_0001.JPG"),
        source_precedence=(Path("IMG_0001.xmp"), Path("IMG_0001.JPG")),
    )

    capture = next(item for item in observations if item["name"] == "capture_time")
    make = next(item for item in observations if item["name"] == "camera_make")
    assert capture["value"] == "2024-06-15T15:31:02+08:00"
    assert capture["provenance"]["relative_path"] == "IMG_0001.xmp"
    assert capture["provenance"]["tag"] == "XMP:DateTimeOriginal"
    assert capture["provenance"]["timezone_assumed"] is False
    assert make["value"] == "Sidecar correction"


@pytest.mark.characterization
def test_naive_time_is_explicitly_interpreted_and_invalid_time_is_not_epoch_zero() -> (
    None
):
    profile = MetadataProfile(timezone="Asia/Shanghai")
    naive = select_metadata_observations(
        (
            {
                "relative_path": "photo.jpg",
                "fields": {"EXIF:DateTimeOriginal": "2025:09:30 16:39:34"},
            },
        ),
        subject=Path("photo.jpg"),
        source_precedence=(Path("photo.jpg"),),
        profile=profile,
    )[0]
    invalid = select_metadata_observations(
        ({"relative_path": "photo.jpg", "fields": {"EXIF:DateTimeOriginal": 0}},),
        subject=Path("photo.jpg"),
        source_precedence=(Path("photo.jpg"),),
        profile=profile,
    )[0]

    assert naive["value"] == "2025-09-30T16:39:34+08:00"
    assert naive["provenance"]["timezone_assumed"] is True
    assert invalid["status"] == "failed"
    assert invalid["provenance"]["reason"] == "unparseable_time"
    assert invalid["provenance"]["candidates"][0]["raw_value"] == 0
    assert "value" not in invalid


@pytest.mark.characterization
def test_numeric_gps_is_local_wgs84_candidate_not_resolved_place() -> None:
    observations = select_metadata_observations(
        (
            {
                "relative_path": "photo.jpg",
                "fields": {
                    "Composite:GPSLatitude": 22.3193,
                    "Composite:GPSLongitude": 114.1694,
                },
            },
        ),
        subject=Path("photo.jpg"),
        source_precedence=(Path("photo.jpg"),),
    )
    gps = next(item for item in observations if item["name"] == "gps_coordinates")

    assert gps["status"] == "available"
    assert gps["value"] == {
        "datum": "WGS84",
        "latitude": 22.3193,
        "longitude": 114.1694,
    }
    assert all("resolved" not in item["name"] for item in observations)


@pytest.mark.characterization
def test_present_but_invalid_gps_is_a_failure_not_silent_missing_data() -> None:
    observations = select_metadata_observations(
        (
            {
                "relative_path": "photo.jpg",
                "fields": {
                    "Composite:GPSLatitude": "not-a-coordinate",
                    "Composite:GPSLongitude": 114.1694,
                },
            },
        ),
        subject=Path("photo.jpg"),
        source_precedence=(Path("photo.jpg"),),
    )

    gps = next(item for item in observations if item["name"] == "gps_coordinates")
    assert gps == {
        "name": "gps_coordinates",
        "status": "failed",
        "provenance": {"method": "exiftool", "reason": "incomplete_coordinates"},
    }
