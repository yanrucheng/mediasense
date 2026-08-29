"""Compression mechanics characterized from AI Album c90 clustering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from mediasense.precheck.compression import (
    AdaptiveCompressionProfile,
    CompressionPoint,
    build_adaptive_groups,
    select_embedding_representative,
)


pytestmark = pytest.mark.characterization


def test_key_frame_uses_c90_top_half_average_similarity_and_stable_ties() -> None:
    vectors = (
        (1.0, 0.0),
        (0.9, 0.1),
        (0.0, 1.0),
    )

    assert select_embedding_representative(vectors, top_k=0.5) == 1
    assert select_embedding_representative(((1.0, 0.0), (1.0, 0.0))) == 0


def test_adaptive_frontier_hits_each_requested_size_without_changing_inputs() -> None:
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    points = tuple(
        CompressionPoint(
            relative_path=Path(f"item-{index:03d}.jpg"),
            capture_time=started + timedelta(minutes=index),
            gps=(22.30 + index / 100_000, 114.17),
            embedding=(1.0, index / 500),
        )
        for index in range(500)
    )

    three = build_adaptive_groups(points, AdaptiveCompressionProfile(target_entries=3))
    two_hundred = build_adaptive_groups(
        points, AdaptiveCompressionProfile(target_entries=200)
    )
    five_hundred = build_adaptive_groups(
        points, AdaptiveCompressionProfile(target_entries=500)
    )

    assert len(three) == 3
    assert len(two_hundred) == 200
    assert len(five_hundred) == 500
    for groups in (three, two_hundred, five_hundred):
        assert sorted(path for group in groups for path in group.members) == sorted(
            point.relative_path for point in points
        )


def test_missing_similarity_is_qualified_instead_of_treated_as_identical() -> None:
    points = (
        CompressionPoint(Path("a.jpg")),
        CompressionPoint(Path("b.jpg")),
    )

    group = build_adaptive_groups(points, AdaptiveCompressionProfile(target_entries=1))[
        0
    ]

    assert "limited_similarity_evidence" in group.qualifications
    assert group.representative_path == Path("a.jpg")

    balanced = build_adaptive_groups(
        tuple(CompressionPoint(Path(f"item-{index}.jpg")) for index in range(6)),
        AdaptiveCompressionProfile(target_entries=2),
    )
    assert [len(item.members) for item in balanced] == [3, 3]


def test_disagreeing_time_and_content_axes_remain_visible_as_conflicts() -> None:
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    group = build_adaptive_groups(
        (
            CompressionPoint(
                Path("a.jpg"),
                capture_time=started,
                embedding=(1.0, 0.0),
            ),
            CompressionPoint(
                Path("b.jpg"),
                capture_time=started + timedelta(seconds=10),
                embedding=(0.0, 1.0),
            ),
        ),
        AdaptiveCompressionProfile(target_entries=1),
    )[0]

    assert group.conflict_paths == (Path("a.jpg"), Path("b.jpg"))
    assert "candidate_axes_disagree" in group.qualifications
