"""Source discovery and filename-association candidates for PreCheck.

Discovery deliberately does not decode media. A recognized media extension is a
scope candidate whose condition remains unresolved until a later probe records a
real outcome. Ignore markers are recorded as scope-decision evidence; they never
erase paths from accounting.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
import os
from pathlib import Path
import stat


class SourceScope(StrEnum):
    """Result-facing accounting scope values."""

    SOURCE_MEDIA = "source_media"
    AUXILIARY = "auxiliary"
    EXCLUDED = "excluded"


class SourceCondition(StrEnum):
    """Result-facing accounting condition values."""

    USABLE = "usable"
    UNSUPPORTED = "unsupported"
    INVALID = "invalid"
    ERROR = "error"
    UNRESOLVED = "unresolved"


class SourceKind(StrEnum):
    """Internal discovery categories; these are not public contract kinds."""

    IMAGE = "image"
    VIDEO = "video"
    RAW_IMAGE = "raw_image"
    SIDECAR = "sidecar"
    GPX = "gpx"
    IGNORE_MARKER = "ignore_marker"
    SYMLINK = "symlink"
    UNKNOWN = "unknown"


class DiscoveryIssueCode(StrEnum):
    """Stable internal categories for recoverable discovery failures."""

    ROOT_UNAVAILABLE = "root_unavailable"
    ROOT_NOT_DIRECTORY = "root_not_directory"
    DIRECTORY_READ_FAILED = "directory_read_failed"
    ENTRY_INSPECTION_FAILED = "entry_inspection_failed"


@dataclass(frozen=True, slots=True)
class DiscoveredSource:
    """One path observed during discovery before expensive media probing."""

    relative_path: Path
    locator: Path
    kind: SourceKind
    scope: SourceScope
    condition: SourceCondition
    basis: tuple[str, ...]
    size_bytes: int | None = None
    mtime_ns: int | None = None
    device_id: int | None = None
    inode: int | None = None
    mode: int | None = None


@dataclass(frozen=True, slots=True)
class DiscoveryIssue:
    """A bounded discovery failure that must remain visible to accounting."""

    relative_path: Path
    locator: Path
    code: DiscoveryIssueCode
    message: str
    blocked: bool
    basis: tuple[str, ...]


DiscoveryEvent = DiscoveredSource | DiscoveryIssue


_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".heic", ".heif"})
_VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".mkv", ".flv", ".webm"})
_RAW_EXTENSIONS = frozenset({".arw", ".dng", ".cr2", ".cr3", ".nef", ".orf", ".raf", ".rw2", ".pef"})
_SIDECAR_EXTENSIONS = frozenset({".xmp", ".exif", ".json", ".xml"})


def association_key(path: Path) -> Path:
    """Return the filename-family key preserved from AI Album's c90 behavior.

    The key is directory-local. It strips one suffix, maps AppleDouble ``._``
    names to their apparent source name, and folds DJI-style ``M01``/``M02``
    variants into the base stem. The result is only candidate evidence.
    """

    path = Path(path)
    key = path.with_suffix("")
    stem = key.name

    if stem.startswith("._"):
        stem = stem[2:]

    if len(stem) > 3 and stem.endswith(("M01", "M02")):
        stem = stem[:-3]

    return key.with_name(stem)


def group_filename_candidates(paths: Iterable[Path]) -> dict[Path, tuple[Path, ...]]:
    """Group paths by filename evidence without asserting a source relationship."""

    grouped: dict[Path, list[Path]] = defaultdict(list)
    for path in paths:
        normalized = Path(path)
        grouped[association_key(normalized)].append(normalized)
    return {key: tuple(members) for key, members in grouped.items()}


def discover_source_events(
    root: Path,
    *,
    ignore_marker: str = ".albumignore",
) -> Iterator[DiscoveryEvent]:
    """Yield source observations and bounded failures in deterministic order.

    Directory-local ignore markers add scope-decision provenance but do not prune
    or exclude their subtree. Symlinks are accounted for and never followed.
    A failed child directory does not stop readable siblings; a failed root is a
    blocking issue because no trustworthy absence conclusion can be drawn.
    """

    root = Path(root).expanduser().absolute()
    try:
        root_stat = root.stat(follow_symlinks=False)
    except OSError as error:
        yield DiscoveryIssue(
            relative_path=Path("."),
            locator=root,
            code=DiscoveryIssueCode.ROOT_UNAVAILABLE,
            message=str(error),
            blocked=True,
            basis=("root_stat_failed",),
        )
        return
    if not stat.S_ISDIR(root_stat.st_mode):
        yield DiscoveryIssue(
            relative_path=Path("."),
            locator=root,
            code=DiscoveryIssueCode.ROOT_NOT_DIRECTORY,
            message=f"source root is not a directory: {root}",
            blocked=True,
            basis=("root_type_check",),
        )
        return

    def walk(directory: Path, inherited_ignore: bool) -> Iterator[DiscoveryEvent]:
        try:
            with os.scandir(directory) as scan:
                entries = sorted(scan, key=lambda entry: entry.name)
        except OSError as error:
            yield DiscoveryIssue(
                relative_path=directory.relative_to(root),
                locator=directory,
                code=DiscoveryIssueCode.DIRECTORY_READ_FAILED,
                message=str(error),
                blocked=directory == root,
                basis=("scandir_failed",),
            )
            return

        local_ignore = inherited_ignore or any(entry.name == ignore_marker for entry in entries)

        for entry in entries:
            path = Path(entry.path)
            try:
                is_symlink = entry.is_symlink()
                is_directory = entry.is_dir(follow_symlinks=False)
            except OSError as error:
                yield _failed_item(
                    root,
                    path,
                    ignore_marker=ignore_marker,
                    under_ignore=local_ignore,
                )
                yield DiscoveryIssue(
                    relative_path=path.relative_to(root),
                    locator=path,
                    code=DiscoveryIssueCode.ENTRY_INSPECTION_FAILED,
                    message=str(error),
                    blocked=False,
                    basis=("directory_entry_type_failed",),
                )
                continue

            if is_directory and not is_symlink:
                yield from walk(path, local_ignore)
                continue

            try:
                observed = entry.stat(follow_symlinks=False)
            except OSError as error:
                yield _failed_item(
                    root,
                    path,
                    ignore_marker=ignore_marker,
                    under_ignore=local_ignore,
                    is_symlink=is_symlink,
                )
                yield DiscoveryIssue(
                    relative_path=path.relative_to(root),
                    locator=path,
                    code=DiscoveryIssueCode.ENTRY_INSPECTION_FAILED,
                    message=str(error),
                    blocked=False,
                    basis=("entry_stat_failed",),
                )
                continue

            kind = _source_kind(
                path,
                ignore_marker=ignore_marker,
                is_symlink=is_symlink,
            )
            scope, condition, basis = _initial_disposition(
                kind,
                under_ignore=local_ignore,
            )
            yield DiscoveredSource(
                relative_path=path.relative_to(root),
                locator=path,
                kind=kind,
                scope=scope,
                condition=condition,
                basis=basis,
                size_bytes=observed.st_size,
                mtime_ns=observed.st_mtime_ns,
                device_id=observed.st_dev,
                inode=observed.st_ino,
                mode=observed.st_mode,
            )

    yield from walk(root, False)


def _source_kind(
    path: Path,
    *,
    ignore_marker: str,
    is_symlink: bool,
) -> SourceKind:
    if is_symlink:
        return SourceKind.SYMLINK
    if path.name == ignore_marker:
        return SourceKind.IGNORE_MARKER
    if path.name.startswith("._"):
        return SourceKind.SIDECAR

    extension = path.suffix.lower()
    if extension in _IMAGE_EXTENSIONS:
        return SourceKind.IMAGE
    if extension in _VIDEO_EXTENSIONS:
        return SourceKind.VIDEO
    if extension in _RAW_EXTENSIONS:
        return SourceKind.RAW_IMAGE
    if extension in _SIDECAR_EXTENSIONS:
        return SourceKind.SIDECAR
    if extension == ".gpx":
        return SourceKind.GPX
    return SourceKind.UNKNOWN


def _initial_disposition(
    kind: SourceKind,
    *,
    under_ignore: bool,
) -> tuple[SourceScope, SourceCondition, tuple[str, ...]]:
    if kind is SourceKind.IGNORE_MARKER:
        return (
            SourceScope.AUXILIARY,
            SourceCondition.USABLE,
            ("albumignore_marker_observed",),
        )
    if kind is SourceKind.SYMLINK:
        return SourceScope.EXCLUDED, SourceCondition.UNRESOLVED, ("symlink_not_followed",)
    if kind in {SourceKind.IMAGE, SourceKind.VIDEO, SourceKind.RAW_IMAGE}:
        disposition = (
            SourceScope.SOURCE_MEDIA,
            SourceCondition.UNRESOLVED,
            ("media_extension_candidate",),
        )
    elif kind in {SourceKind.SIDECAR, SourceKind.GPX}:
        disposition = (
            SourceScope.AUXILIARY,
            SourceCondition.UNRESOLVED,
            ("auxiliary_extension_candidate",),
        )
    else:
        disposition = (
            SourceScope.EXCLUDED,
            SourceCondition.UNSUPPORTED,
            ("unsupported_extension",),
        )

    scope, condition, basis = disposition
    if under_ignore:
        basis += ("albumignore_ancestor_observed",)
    return scope, condition, basis


def _failed_item(
    root: Path,
    path: Path,
    *,
    ignore_marker: str,
    under_ignore: bool,
    is_symlink: bool = False,
) -> DiscoveredSource:
    kind = _source_kind(
        path,
        ignore_marker=ignore_marker,
        is_symlink=is_symlink,
    )
    scope, _, basis = _initial_disposition(kind, under_ignore=under_ignore)
    return DiscoveredSource(
        relative_path=path.relative_to(root),
        locator=path,
        kind=kind,
        scope=scope,
        condition=SourceCondition.ERROR,
        basis=basis + ("entry_inspection_failed",),
    )
