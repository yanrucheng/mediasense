"""Bundle behavior characterized from AI Album c90 MediaOrganizer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mediasense.precheck.bundling import (
    BundleItem,
    BundleProfile,
    build_bundle_candidates,
)


pytestmark = pytest.mark.characterization


def _time(seconds: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def test_same_stem_and_c90_representative_priority_are_preserved() -> None:
    groups = build_bundle_candidates(
        (
            BundleItem(Path("trip/IMG_0001.ARW"), _time(0)),
            BundleItem(Path("trip/IMG_0001.JPG"), _time(0)),
            BundleItem(Path("trip/._IMG_0001.JPG"), None),
        ),
        BundleProfile(max_gap_seconds=0),
    )

    assert len(groups) == 1
    assert groups[0].representative_path == Path("trip/IMG_0001.JPG")
    assert groups[0].members == (
        Path("trip/._IMG_0001.JPG"),
        Path("trip/IMG_0001.ARW"),
        Path("trip/IMG_0001.JPG"),
    )


def test_adjacent_time_links_preserve_chain_but_expose_total_span() -> None:
    groups = build_bundle_candidates(
        (
            BundleItem(Path("a.jpg"), _time(0)),
            BundleItem(Path("b.jpg"), _time(50)),
            BundleItem(Path("c.jpg"), _time(110)),
        ),
        BundleProfile(max_gap_seconds=60),
    )

    assert len(groups) == 1
    assert groups[0].span_seconds == 110
    assert "adjacent_chain_exceeds_gap" in groups[0].qualifications
    assert groups[0].boundary_paths == (Path("a.jpg"), Path("c.jpg"))


def test_missing_time_does_not_recreate_epoch_zero_grouping() -> None:
    groups = build_bundle_candidates(
        (
            BundleItem(Path("missing-a.jpg"), None),
            BundleItem(Path("missing-b.jpg"), None),
            BundleItem(Path("known.jpg"), _time(0)),
        ),
        BundleProfile(max_gap_seconds=60),
    )

    assert {group.members for group in groups} == {
        (Path("known.jpg"),),
        (Path("missing-a.jpg"),),
        (Path("missing-b.jpg"),),
    }
