from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path

from mediasense.precheck import discovery
from mediasense.precheck.discovery import (
    DiscoveredSource,
    DiscoveryIssue,
    DiscoveryIssueCode,
    SourceCondition,
    SourceScope,
    discover_source_events,
)


def _partition(
    events: Iterator[DiscoveredSource | DiscoveryIssue],
) -> tuple[dict[Path, DiscoveredSource], tuple[DiscoveryIssue, ...]]:
    items: dict[Path, DiscoveredSource] = {}
    issues: list[DiscoveryIssue] = []
    for event in events:
        if isinstance(event, DiscoveredSource):
            items[event.relative_path] = event
        else:
            issues.append(event)
    return items, tuple(issues)


def test_root_and_nested_albumignore_add_basis_without_excluding_media(
    tmp_path: Path,
) -> None:
    (tmp_path / ".albumignore").touch()
    (tmp_path / "root.JPG").write_bytes(b"root")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / ".albumignore").touch()
    (nested / "inside.DNG").write_bytes(b"raw")

    items, issues = _partition(discover_source_events(tmp_path))

    assert not issues
    assert items[Path("root.JPG")].scope is SourceScope.SOURCE_MEDIA
    assert items[Path("nested/inside.DNG")].scope is SourceScope.SOURCE_MEDIA
    assert "albumignore_ancestor_observed" in items[Path("root.JPG")].basis
    assert "albumignore_ancestor_observed" in items[Path("nested/inside.DNG")].basis


def test_nested_scandir_failure_is_local_and_readable_siblings_continue(
    tmp_path: Path,
    monkeypatch,
) -> None:
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "hidden.JPG").write_bytes(b"hidden")
    (tmp_path / "visible.JPG").write_bytes(b"visible")
    real_scandir = os.scandir

    def fail_one_directory(path: os.PathLike[str] | str):
        if Path(path) == blocked:
            raise PermissionError("simulated unreadable directory")
        return real_scandir(path)

    monkeypatch.setattr(discovery.os, "scandir", fail_one_directory)

    items, issues = _partition(discover_source_events(tmp_path))

    assert set(items) == {Path("visible.JPG")}
    assert len(issues) == 1
    assert issues[0].relative_path == Path("blocked")
    assert issues[0].code is DiscoveryIssueCode.DIRECTORY_READ_FAILED
    assert not issues[0].blocked


def test_root_scandir_failure_is_reported_as_blocking(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fail_root(path: os.PathLike[str] | str):
        raise PermissionError(f"simulated unreadable root: {path}")

    monkeypatch.setattr(discovery.os, "scandir", fail_root)

    items, issues = _partition(discover_source_events(tmp_path))

    assert not items
    assert len(issues) == 1
    assert issues[0].code is DiscoveryIssueCode.DIRECTORY_READ_FAILED
    assert issues[0].blocked


def test_disappearing_entry_is_accounted_as_error_and_scan_continues(
    tmp_path: Path,
    monkeypatch,
) -> None:
    victim = tmp_path / "a.JPG"
    victim.write_bytes(b"gone")
    (tmp_path / "b.JPG").write_bytes(b"present")
    real_scandir = os.scandir
    removed = False

    class Snapshot:
        def __init__(self, entries) -> None:
            self.entries = entries

        def __enter__(self):
            return iter(self.entries)

        def __exit__(self, *args) -> None:
            return None

    def remove_after_listing(path: os.PathLike[str] | str):
        nonlocal removed
        scan = real_scandir(path)
        entries = list(scan)
        scan.close()
        if Path(path) == tmp_path and not removed:
            victim.unlink()
            removed = True
        return Snapshot(entries)

    monkeypatch.setattr(discovery.os, "scandir", remove_after_listing)

    items, issues = _partition(discover_source_events(tmp_path))

    assert items[Path("a.JPG")].condition is SourceCondition.ERROR
    assert items[Path("b.JPG")].condition is SourceCondition.UNRESOLVED
    assert any(issue.relative_path == Path("a.JPG") for issue in issues)


def test_symlink_cycle_and_boundary_escape_are_accounted_without_following(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.JPG"
    outside.write_bytes(b"outside")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "inside.JPG").write_bytes(b"inside")
    (nested / "cycle").symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / "escape").symlink_to(outside)

    items, issues = _partition(discover_source_events(tmp_path))

    assert not issues
    assert set(items) == {
        Path("escape"),
        Path("nested/cycle"),
        Path("nested/inside.JPG"),
    }
    assert items[Path("escape")].scope is SourceScope.EXCLUDED
    assert items[Path("nested/cycle")].scope is SourceScope.EXCLUDED
    assert all(item.locator != outside for item in items.values())


def test_unavailable_root_is_a_blocking_issue_instead_of_empty_discovery(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "detached-volume"

    items, issues = _partition(discover_source_events(missing))

    assert not items
    assert len(issues) == 1
    assert issues[0].code is DiscoveryIssueCode.ROOT_UNAVAILABLE
    assert issues[0].blocked
