"""Discovery characterization derived from AI Album commit c90aa8f.

The legacy source of truth for these cases is ``src/media_libs.py:97-223`` and
``src/media_utils.py:28-60`` at commit
``c90aa8f04fd0d3348284e0ad19e18462987b1af2``. The tests retain useful filename
association behavior while making MediaSense's intentional scope differences
explicit. They do not import or execute the AI Album repository.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mediasense.precheck.discovery import (
    DiscoveredSource,
    DiscoveryIssue,
    SourceCondition,
    SourceKind,
    SourceScope,
    association_key,
    discover_source_events,
    group_filename_candidates,
)


def _items(root: Path) -> list[DiscoveredSource]:
    events = list(discover_source_events(root))
    assert not [event for event in events if isinstance(event, DiscoveryIssue)]
    return [event for event in events if isinstance(event, DiscoveredSource)]


@pytest.mark.characterization
def test_association_key_preserves_same_stem_and_appledouble_rules() -> None:
    root = Path("trip")

    assert association_key(root / "IMG_0001.JPG") == root / "IMG_0001"
    assert association_key(root / "IMG_0001.ARW") == root / "IMG_0001"
    assert association_key(root / "IMG_0001.xmp") == root / "IMG_0001"
    assert association_key(root / "._IMG_0001.JPG") == root / "IMG_0001"


@pytest.mark.characterization
def test_association_key_preserves_m01_m02_name_family() -> None:
    root = Path("trip")

    assert association_key(root / "DJI_0042M01.MP4") == root / "DJI_0042"
    assert association_key(root / "DJI_0042M02.LRF") == root / "DJI_0042"
    assert association_key(root / "DJI_0042.JPG") == root / "DJI_0042"


@pytest.mark.characterization
def test_association_key_does_not_merge_across_directories() -> None:
    assert association_key(Path("day-1/IMG_0001.JPG")) != association_key(
        Path("day-2/IMG_0001.JPG")
    )


@pytest.mark.characterization
def test_group_filename_candidates_keeps_all_members() -> None:
    paths = [
        Path("trip/IMG_0001.JPG"),
        Path("trip/IMG_0001.ARW"),
        Path("trip/IMG_0001.xmp"),
        Path("trip/other.JPG"),
    ]

    groups = group_filename_candidates(paths)

    assert groups[Path("trip/IMG_0001")] == tuple(paths[:3])
    assert groups[Path("trip/other")] == (paths[3],)


def test_appledouble_is_visible_as_auxiliary_instead_of_silently_dropped(
    tmp_path: Path,
) -> None:
    (tmp_path / "._IMG_0001.JPG").write_bytes(b"appledouble")

    item = _items(tmp_path)[0]

    assert item.kind is SourceKind.SIDECAR
    assert item.scope is SourceScope.AUXILIARY
    assert item.condition is SourceCondition.UNRESOLVED


def test_albumignore_contents_are_accounted_instead_of_silently_skipped(
    tmp_path: Path,
) -> None:
    """MediaSense intentionally changes c90's directory-pruning behavior."""
    ignored = tmp_path / "private"
    ignored.mkdir()
    (ignored / ".albumignore").write_text("", encoding="utf-8")
    (ignored / "hidden.JPG").write_bytes(b"not decoded in discovery")
    (tmp_path / "visible.JPG").write_bytes(b"not decoded in discovery")

    items = {item.relative_path: item for item in _items(tmp_path)}

    assert set(items) == {
        Path("private/.albumignore"),
        Path("private/hidden.JPG"),
        Path("visible.JPG"),
    }
    assert items[Path("private/.albumignore")].scope is SourceScope.AUXILIARY
    assert items[Path("private/.albumignore")].condition is SourceCondition.USABLE
    assert items[Path("private/hidden.JPG")].scope is SourceScope.SOURCE_MEDIA
    assert items[Path("private/hidden.JPG")].condition is SourceCondition.UNRESOLVED
    assert "albumignore_ancestor_observed" in items[Path("private/hidden.JPG")].basis
    assert items[Path("visible.JPG")].scope is SourceScope.SOURCE_MEDIA
    assert items[Path("visible.JPG")].condition is SourceCondition.UNRESOLVED


def test_raw_and_sidecar_roles_are_explicit_before_media_probe(tmp_path: Path) -> None:
    (tmp_path / "IMG_0001.ARW").write_bytes(b"raw")
    (tmp_path / "IMG_0001.xmp").write_text("<x:xmpmeta/>", encoding="utf-8")
    (tmp_path / "track.GPX").write_text("<gpx/>", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("notes", encoding="utf-8")

    items = {item.relative_path: item for item in _items(tmp_path)}

    assert items[Path("IMG_0001.ARW")].kind is SourceKind.RAW_IMAGE
    assert items[Path("IMG_0001.ARW")].scope is SourceScope.SOURCE_MEDIA
    assert items[Path("IMG_0001.xmp")].kind is SourceKind.SIDECAR
    assert items[Path("IMG_0001.xmp")].scope is SourceScope.AUXILIARY
    assert items[Path("track.GPX")].kind is SourceKind.GPX
    assert items[Path("track.GPX")].scope is SourceScope.AUXILIARY
    assert items[Path("notes.txt")].kind is SourceKind.UNKNOWN
    assert items[Path("notes.txt")].scope is SourceScope.EXCLUDED
    assert items[Path("notes.txt")].condition is SourceCondition.UNSUPPORTED


def test_discovery_is_deterministic_and_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "z.MP4").write_bytes(b"video")
    (tmp_path / "A.HeIc").write_bytes(b"image")

    items = _items(tmp_path)

    assert [item.relative_path for item in items] == [Path("A.HeIc"), Path("z.MP4")]
    assert [item.kind for item in items] == [SourceKind.IMAGE, SourceKind.VIDEO]


def test_symlinks_are_accounted_but_not_followed_by_default(tmp_path: Path) -> None:
    source = tmp_path / "source.JPG"
    source.write_bytes(b"image")
    link = tmp_path / "linked.JPG"
    link.symlink_to(source)

    items = {item.relative_path: item for item in _items(tmp_path)}

    assert items[Path("linked.JPG")].kind is SourceKind.SYMLINK
    assert items[Path("linked.JPG")].scope is SourceScope.EXCLUDED
    assert items[Path("linked.JPG")].condition is SourceCondition.UNRESOLVED
    assert items[Path("source.JPG")].scope is SourceScope.SOURCE_MEDIA


def test_discovery_does_not_modify_source_files(tmp_path: Path) -> None:
    source = tmp_path / "source.JPG"
    source.write_bytes(b"source bytes")
    before = source.stat()

    _items(tmp_path)

    after = source.stat()
    assert source.read_bytes() == b"source bytes"
    assert after.st_mtime_ns == before.st_mtime_ns
    assert after.st_size == before.st_size
