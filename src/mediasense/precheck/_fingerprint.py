"""Source observations used for conservative Slice 1 change detection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
from typing import Final

from .discovery import DiscoveredSource, SourceKind


FINGERPRINT_ALGORITHM: Final = "candidate-sha256-full-or-3x4k-v1"
_SAMPLE_BYTES: Final = 4 * 1024
_FULL_HASH_LIMIT: Final = _SAMPLE_BYTES * 3


@dataclass(frozen=True, slots=True)
class CandidateFingerprint:
    algorithm: str
    value: str
    size_bytes: int
    mtime_ns: int
    device_id: int
    inode: int
    mode: int


class SourceChangedDuringRead(OSError):
    """Raised when a source cannot be fingerprinted as one stable observation."""


def fingerprint_candidate(item: DiscoveredSource) -> CandidateFingerprint:
    """Return cheap change evidence, never an exact content identity proof."""

    if item.kind is SourceKind.SYMLINK:
        before = item.locator.lstat()
        target = os.readlink(item.locator)
        after = item.locator.lstat()
        digest = hashlib.sha256(
            target.encode("utf-8", errors="surrogateescape")
        ).hexdigest()
    else:
        before = item.locator.stat(follow_symlinks=False)
        digest = hash_regular_file(item.locator, before)
        after = item.locator.stat(follow_symlinks=False)

    if stat_identity(before) != stat_identity(after):
        raise SourceChangedDuringRead(f"source changed while reading: {item.locator}")
    return CandidateFingerprint(
        algorithm=FINGERPRINT_ALGORITHM,
        value=digest,
        size_bytes=after.st_size,
        mtime_ns=after.st_mtime_ns,
        device_id=after.st_dev,
        inode=after.st_ino,
        mode=after.st_mode,
    )


def hash_regular_file(path: Path, observed: os.stat_result) -> str:
    """Hash small files fully and sample large files at three fixed offsets."""

    hasher = hashlib.sha256()
    hasher.update(str(observed.st_size).encode("ascii"))
    if not stat.S_ISREG(observed.st_mode):
        hasher.update(str(observed.st_mode).encode("ascii"))
        return hasher.hexdigest()

    # No Python read-ahead beyond the declared sample budget. Filesystem/device
    # caching and physical read-ahead remain outside this logical byte count.
    with path.open("rb", buffering=0) as source:
        if observed.st_size <= _FULL_HASH_LIMIT:
            # A concurrent append must not turn a bounded observation into an
            # unbounded scan. Callers check the file state after this read.
            hasher.update(source.read(observed.st_size))
        else:
            offsets = sorted(
                {
                    0,
                    observed.st_size // 2,
                    observed.st_size - _SAMPLE_BYTES,
                }
            )
            for offset in offsets:
                source.seek(offset)
                hasher.update(offset.to_bytes(8, "big"))
                hasher.update(source.read(_SAMPLE_BYTES))
    return hasher.hexdigest()


def stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (value.st_size, value.st_mtime_ns, value.st_dev, value.st_ino, value.st_mode)


def fingerprint_stat_identity(value: CandidateFingerprint) -> tuple[int, ...]:
    return (
        value.size_bytes,
        value.mtime_ns,
        value.device_id,
        value.inode,
        value.mode,
    )
