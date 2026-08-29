from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
import os
from pathlib import Path

import pytest

from mediasense.precheck import (
    HIGH_RESOLUTION_RENDITION_PROFILE,
    BundleItem,
    BundleProfile,
    ImageRenditionProducer,
    MetadataProducer,
    WorkStatus,
    build_bundle_candidates,
)
from mediasense.precheck.accounting import AccountingStore, WorkingRunStatus
from mediasense.precheck.discovery import (
    DiscoveredSource,
    DiscoveryIssue,
    SourceCondition,
    SourceKind,
    SourceScope,
    discover_source_events,
)


PACKAGE_ROOT = Path(
    os.environ.get(
        "MEDIASENSE_HK_FIXTURE",
        Path.home() / "Downloads" / "ai-album-hk-representative-v1",
    )
)
SOURCE_ROOT = PACKAGE_ROOT / "dataset" / "260501-HK美食之旅"
MANIFEST = PACKAGE_ROOT / "manifests" / "media-manifest.jsonl"

pytestmark = [
    pytest.mark.local_fixture,
    pytest.mark.skipif(
        not SOURCE_ROOT.is_dir(), reason="Hong Kong fixture is not installed"
    ),
]


def _signed_source_paths() -> set[Path]:
    rows = _manifest_rows()
    paths = {Path(row["path"]) for row in rows}
    paths.update(
        {
            Path("a-files/.albumignore"),
            Path("a-files/GPX/2026-05-03T05-33-10+0800.gpx"),
            Path("a-files/GPX/2026-05-05T21-47-16+0800.gpx"),
            Path("fixtures/.albumignore"),
            Path("fixtures/raw-sidecar/DJI_20260501183924_0002_D.DNG"),
            Path("fixtures/raw-sidecar/DSC01519.ARW"),
        }
    )
    return paths


def _manifest_rows() -> list[dict[str, object]]:
    return [json.loads(line) for line in MANIFEST.read_text().splitlines() if line]


def _discover_fixture() -> tuple[
    dict[Path, DiscoveredSource], tuple[DiscoveryIssue, ...]
]:
    items: dict[Path, DiscoveredSource] = {}
    issues: list[DiscoveryIssue] = []
    for event in discover_source_events(SOURCE_ROOT):
        if isinstance(event, DiscoveredSource):
            items[event.relative_path] = event
        else:
            issues.append(event)
    return items, tuple(issues)


def test_hong_kong_signed_source_state_and_local_extras_are_explicit() -> None:
    items, issues = _discover_fixture()
    signed_paths = _signed_source_paths()
    local_extras = set(items) - signed_paths

    assert not issues
    assert len(signed_paths) == 2_140
    assert local_extras == {Path(".DS_Store"), Path("0502/.DS_Store")}
    assert len(items) == 2_142

    scopes = {scope: 0 for scope in SourceScope}
    for item in items.values():
        scopes[item.scope] += 1
    assert scopes == {
        SourceScope.SOURCE_MEDIA: 2_136,
        SourceScope.AUXILIARY: 4,
        SourceScope.EXCLUDED: 2,
    }
    assert all(
        items[path].condition is SourceCondition.UNSUPPORTED for path in local_extras
    )

    assert items[Path("fixtures/raw-sidecar/DSC01519.ARW")].kind is SourceKind.RAW_IMAGE
    assert (
        items[Path("fixtures/raw-sidecar/DJI_20260501183924_0002_D.DNG")].kind
        is SourceKind.RAW_IMAGE
    )
    assert (
        items[Path("a-files/GPX/2026-05-03T05-33-10+0800.gpx")].kind is SourceKind.GPX
    )
    assert (
        items[Path("a-files/GPX/2026-05-05T21-47-16+0800.gpx")].kind is SourceKind.GPX
    )


def test_hong_kong_source_state_reaches_sqlite_accounting_closure(
    tmp_path: Path,
) -> None:
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("hk-representative-v1")
    run_id = store.start_or_resume_run("hk-representative-v1", SOURCE_ROOT)

    summary = store.process_run(run_id, batch_size=128)
    items = store.get_run_items(run_id)

    assert summary.status is WorkingRunStatus.COMPLETED
    assert summary.item_count == 2_142
    assert summary.new_count == 2_142
    assert summary.issue_count == 0
    assert all(item.scope and item.condition and item.basis for item in items)


def test_hong_kong_representative_supports_real_local_metadata_and_rendition(
    tmp_path: Path,
) -> None:
    relative_path = Path("0502/100MSDCF/DSC00085.JPG")
    media = SOURCE_ROOT / relative_path
    source_before = media.read_bytes()
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("hk-representative-v1")
    run_id = accounting.start_or_resume_run("hk-representative-v1", SOURCE_ROOT)
    accounting.process_run(run_id, batch_size=128)

    metadata = MetadataProducer(database).produce(run_id, relative_path)
    rendition = ImageRenditionProducer(database).produce(
        run_id,
        relative_path,
        profile=HIGH_RESOLUTION_RENDITION_PROFILE,
    )

    assert metadata.work.status is WorkStatus.SUCCEEDED
    capture_time = next(
        item for item in metadata.observations if item["name"] == "capture_time"
    )
    assert capture_time["status"] == "available"
    # The proxy's current EXIF contains subsecond precision; the historical
    # manifest cache recorded only whole seconds and is not source authority.
    assert capture_time["value"] == "2026-05-01T18:03:03.046000+08:00"
    assert capture_time["provenance"]["relative_path"] == relative_path.as_posix()
    assert rendition.work.status is WorkStatus.SUCCEEDED
    assert rendition.artifact is not None
    assert rendition.artifact.path.stat().st_size > 0
    assert media.read_bytes() == source_before


def test_hong_kong_bundle_candidates_match_recorded_valid_media_membership() -> None:
    rows = _manifest_rows()
    items = []
    expected_members: dict[int, list[Path]] = defaultdict(list)
    for row in rows:
        path = Path(str(row["path"]))
        metadata = row.get("cached_metadata")
        time_value = None
        if isinstance(metadata, dict) and isinstance(metadata.get("time"), dict):
            time_value = metadata["time"].get("create_date")
        items.append(
            BundleItem(
                path,
                None
                if not isinstance(time_value, str)
                else datetime.fromisoformat(time_value),
            )
        )
        bundle_index = int(row["bundle_index"])
        expected_members[bundle_index].append(path)

    actual = build_bundle_candidates(items, BundleProfile(max_gap_seconds=60))
    actual_by_members = {frozenset(group.members): group for group in actual}

    expected_sets = {
        bundle_index: frozenset(members)
        for bundle_index, members in expected_members.items()
    }
    matched_indices = {
        bundle_index
        for bundle_index, members in expected_sets.items()
        if members in actual_by_members
    }
    assert len(actual) == 169
    assert matched_indices == set(expected_sets) - {114}

    legacy_114 = expected_sets[114]
    split_114 = [
        group
        for group in actual
        if set(group.members) and set(group.members) <= legacy_114
    ]
    assert sorted(len(group.members) for group in split_114) == [1, 31]
    missing_time_group = next(group for group in split_114 if len(group.members) == 1)
    assert missing_time_group.members == (
        Path("0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.MP4"),
    )
    assert "capture_time_unavailable" in missing_time_group.qualifications
