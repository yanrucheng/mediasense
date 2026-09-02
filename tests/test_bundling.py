from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess

from PIL import Image

from mediasense.precheck import (
    AccountingStore,
    BundleCandidateProducer,
    BundleItem,
    BundleProfile,
    DependencyKind,
    MetadataProducer,
    WorkStatus,
    build_bundle_candidates,
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


class FakeExifTool:
    def __init__(self, times: dict[str, str]) -> None:
        self.times = times

    def __call__(self, command: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        if "-ver" in command:
            return subprocess.CompletedProcess(command, 0, "13.30\n", "")
        records = []
        for value in command:
            path = Path(value)
            if path.name in self.times:
                records.append(
                    {
                        "SourceFile": str(path),
                        "EXIF:DateTimeOriginal": self.times[path.name],
                    }
                )
        return subprocess.CompletedProcess(command, 0, json.dumps(records), "")


def test_large_temporal_chain_is_split_at_the_member_limit() -> None:
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    items = tuple(
        BundleItem(
            Path(f"item-{index}.jpg"),
            started + timedelta(seconds=index),
            source_revision=1,
        )
        for index in range(5)
    )

    groups = build_bundle_candidates(
        items,
        BundleProfile(max_gap_seconds=60, max_members=2),
    )

    assert [len(group.members) for group in groups] == [2, 2, 1]
    assert all(
        "bundle_member_limit_applied" in group.qualifications for group in groups
    )


def test_bundle_candidate_work_has_exact_members_and_cross_run_reuse(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    for index, name in enumerate(("a.jpg", "b.jpg", "c.jpg")):
        Image.new("RGB", (12, 12), (index * 20, 30, 40)).save(source / name)
    runner = FakeExifTool(
        {
            "a.jpg": "2026:01:01 00:00:00+00:00",
            "b.jpg": "2026:01:01 00:00:50+00:00",
            "c.jpg": "2026:01:01 00:01:50+00:00",
        }
    )
    first_run = _closed_run(database, source)
    metadata_producer = MetadataProducer(database, command_runner=runner)
    first_metadata = tuple(
        metadata_producer.produce(first_run, Path(name))
        for name in ("a.jpg", "b.jpg", "c.jpg")
    )

    first = tuple(
        BundleCandidateProducer(database).produce(
            first_run,
            [outcome.work.work_id for outcome in first_metadata],
            profile=BundleProfile(max_gap_seconds=60),
        )
    )

    assert len(first) == 1
    assert first[0].work.status is WorkStatus.SUCCEEDED
    assert first[0].candidate is not None
    assert first[0].candidate.members == (
        Path("a.jpg"),
        Path("b.jpg"),
        Path("c.jpg"),
    )
    dependencies = first[0].work.spec.dependencies
    assert (
        sum(item.kind is DependencyKind.SOURCE_REVISION for item in dependencies) == 3
    )
    assert sum(item.kind is DependencyKind.UPSTREAM_WORK for item in dependencies) == 3

    second_run = _closed_run(database, source)
    second_metadata = tuple(
        metadata_producer.produce(second_run, Path(name))
        for name in ("a.jpg", "b.jpg", "c.jpg")
    )
    second = tuple(
        BundleCandidateProducer(database).produce(
            second_run,
            [outcome.work.work_id for outcome in second_metadata],
            profile=BundleProfile(max_gap_seconds=60),
        )
    )

    assert len(second) == 1
    assert second[0].work.work_id == first[0].work.work_id
    assert second[0].reused is True


def test_far_source_addition_does_not_invalidate_unchanged_candidate(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (12, 12), "red").save(source / "a.jpg")
    Image.new("RGB", (12, 12), "blue").save(source / "b.jpg")
    runner = FakeExifTool(
        {
            "a.jpg": "2026:01:01 00:00:00+00:00",
            "b.jpg": "2026:01:01 00:00:30+00:00",
            "far.jpg": "2026:01:02 00:00:00+00:00",
        }
    )
    first_run = _closed_run(database, source)
    metadata = MetadataProducer(database, command_runner=runner)
    initial_metadata = [
        metadata.produce(first_run, Path(name)).work.work_id
        for name in ("a.jpg", "b.jpg")
    ]
    initial = tuple(
        BundleCandidateProducer(database).produce(
            first_run, initial_metadata, profile=BundleProfile(max_gap_seconds=60)
        )
    )

    Image.new("RGB", (12, 12), "green").save(source / "far.jpg")
    second_run = _closed_run(database, source)
    next_metadata = [
        metadata.produce(second_run, Path(name)).work.work_id
        for name in ("a.jpg", "b.jpg", "far.jpg")
    ]
    current = tuple(
        BundleCandidateProducer(database).produce(
            second_run, next_metadata, profile=BundleProfile(max_gap_seconds=60)
        )
    )

    original_group = next(
        outcome
        for outcome in current
        if outcome.candidate.members == initial[0].candidate.members
    )
    assert original_group.work.work_id == initial[0].work.work_id
    assert original_group.reused is True
    assert len(current) == 2
