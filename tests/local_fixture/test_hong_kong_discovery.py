from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

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
    rows = [json.loads(line) for line in MANIFEST.read_text().splitlines() if line]
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
