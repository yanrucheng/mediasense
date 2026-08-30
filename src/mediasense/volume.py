"""Stage-neutral observations for filesystem and volume identity."""

from __future__ import annotations

import plistlib
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

Runner = Callable[..., subprocess.CompletedProcess[bytes]]


@dataclass(frozen=True, slots=True)
class PathIdentity:
    """Observed path identity, with the strongest locally available evidence."""

    mount_root: Path
    volume_identity: str
    root_identity: str
    identity_strength: str


def find_mount_root(path: Path) -> Path:
    """Return the nearest mounted ancestor without scanning unrelated volumes."""

    current = Path(path).expanduser().absolute()
    if not current.exists():
        raise FileNotFoundError(current)
    if not current.is_dir():
        current = current.parent
    for candidate in (current, *current.parents):
        if candidate.is_mount():
            return candidate
    return Path(current.anchor)


def observe_path_identity(
    path: Path,
    *,
    platform_name: str | None = None,
    runner: Runner = subprocess.run,
) -> PathIdentity:
    """Observe a root without writing to it or treating its locator as identity."""

    root = Path(path).expanduser().absolute()
    observed = root.stat(follow_symlinks=False)
    mount_root = find_mount_root(root)
    stable_volume = _darwin_volume_uuid(
        mount_root,
        platform_name=platform_name or sys.platform,
        runner=runner,
    )
    if stable_volume is not None:
        return PathIdentity(
            mount_root=mount_root,
            volume_identity=f"darwin-volume-uuid-v1:{stable_volume}",
            root_identity=f"darwin-volume-root-v1:{stable_volume}:{observed.st_ino}",
            identity_strength="stable_volume",
        )
    return PathIdentity(
        mount_root=mount_root,
        volume_identity=f"stat-device-session-v1:{observed.st_dev}",
        root_identity=f"stat-root-v1:{observed.st_dev}:{observed.st_ino}",
        identity_strength="session_local",
    )


def is_non_system_volume(path: Path, *, mount_root: Path | None = None) -> bool:
    """Classify a path by its actual mount boundary, not a `/Volumes` spelling."""

    observed_root = mount_root or find_mount_root(path)
    return observed_root != Path(observed_root.anchor)


def _darwin_volume_uuid(
    mount_root: Path,
    *,
    platform_name: str,
    runner: Runner,
) -> str | None:
    if platform_name != "darwin":
        return None
    executable = shutil.which("diskutil")
    if executable is None:
        return None
    command: Sequence[str] = (executable, "info", "-plist", str(mount_root))
    try:
        completed = runner(
            command,
            check=False,
            capture_output=True,
            timeout=5,
        )
        if completed.returncode != 0:
            return None
        payload = plistlib.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException):
        return None
    for key in ("VolumeUUID", "DiskUUID"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return None
