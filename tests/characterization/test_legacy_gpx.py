"""GPX matching characterized from AI Album c90 ``src/my_gpx.py``."""

from pathlib import Path

import pytest

from mediasense.precheck.gpx import (
    GPXMatchProfile,
    GPXTrackPoint,
    GPXTrackSegment,
    match_gpx_segments,
)


@pytest.mark.characterization
def test_matching_preserves_nearest_point_and_maximum_time_difference() -> None:
    segment = GPXTrackSegment(
        Path("track.gpx"),
        0,
        (GPXTrackPoint(100.0, 22.0, 114.0),),
    )

    match = match_gpx_segments((segment,), 105.0, GPXMatchProfile(10, False))
    missing = match_gpx_segments((segment,), 111.0, GPXMatchProfile(10, False))

    assert match is not None
    assert match.method == "nearest_point"
    assert match.time_error_seconds == 5.0
    assert missing is None


@pytest.mark.characterization
def test_interpolation_corrects_c90_right_index_defect_within_one_segment() -> None:
    segment = GPXTrackSegment(
        Path("track.gpx"),
        0,
        (
            GPXTrackPoint(100.0, 20.0, 110.0),
            GPXTrackPoint(200.0, 30.0, 120.0),
        ),
    )

    match = match_gpx_segments((segment,), 150.0, GPXMatchProfile(60, True))

    assert match is not None
    assert match.method == "linear_interpolation"
    assert (match.latitude, match.longitude) == (25.0, 115.0)
    assert match.point_times == (100.0, 200.0)
