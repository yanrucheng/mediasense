"""Run-scoped source attachment and filesystem capability observations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
import stat
import tempfile
from uuid import uuid4


class AttachmentState(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class SourceAttachmentError(RuntimeError):
    """Base failure for an unsafe or ambiguous source attachment."""


class SourceRebindRequired(SourceAttachmentError):
    """Raised when source continuity cannot be proven automatically."""


class UnsafeWorkspace(SourceAttachmentError):
    """Raised when the workspace would violate the source-read-only boundary."""


@dataclass(frozen=True, slots=True)
class FilesystemCapabilities:
    """Observed capabilities, not stronger guarantees than the probe can prove."""

    source_mount_read_only: bool | None
    source_process_writable: bool | None
    source_case_sensitivity: str
    workspace_atomic_replace: bool
    workspace_case_sensitive: bool | None
    workspace_same_filesystem_as_source: bool | None
    sqlite_locking: str
    symlink_policy: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> FilesystemCapabilities:
        return cls(**json.loads(value))


@dataclass(frozen=True, slots=True)
class SourceAttachmentProbe:
    """One observation of a source root and the local workspace."""

    source_root: Path
    state: AttachmentState
    volume_identity: str | None
    root_identity: str | None
    identity_strength: str
    capabilities: FilesystemCapabilities
    blocked_reason: str | None = None


@dataclass(frozen=True, slots=True)
class SourceAttachment:
    """The current source binding owned by one Working Run."""

    source_root: Path
    volume_identity: str | None
    root_identity: str | None
    identity_strength: str
    reuse_domain: str
    binding_reason: str
    capabilities: FilesystemCapabilities


@dataclass(frozen=True, slots=True)
class SourceRebinding:
    """Audit entry for a changed Working Run source attachment."""

    sequence: int
    previous_source_root: Path
    previous_volume_identity: str | None
    previous_root_identity: str | None
    source_root: Path
    volume_identity: str | None
    root_identity: str | None
    identity_strength: str
    reason: str
    continuity: str
    reuse_domain: str
    capabilities: FilesystemCapabilities


def probe_source_attachment(
    source_root: Path,
    workspace_root: Path,
) -> SourceAttachmentProbe:
    """Probe without writing to the source; workspace probes use temporary files."""

    root = Path(source_root).expanduser().absolute()
    workspace = Path(workspace_root).expanduser().absolute()
    if _is_within(workspace, root):
        raise UnsafeWorkspace(
            "the PreCheck workspace must not be inside the source root"
        )

    workspace.mkdir(parents=True, exist_ok=True)
    workspace_stat = workspace.stat()
    atomic_replace, case_sensitive = _probe_workspace(workspace)
    source_is_symlink = root.is_symlink()

    try:
        observed = root.stat(follow_symlinks=False)
    except OSError as error:
        return SourceAttachmentProbe(
            source_root=root,
            state=AttachmentState.UNAVAILABLE,
            volume_identity=None,
            root_identity=None,
            identity_strength="unavailable",
            capabilities=_capabilities(
                source_root=root,
                source_stat=None,
                workspace_stat=workspace_stat,
                atomic_replace=atomic_replace,
                case_sensitive=case_sensitive,
            ),
            blocked_reason=f"source_root_unavailable:{type(error).__name__}",
        )

    if source_is_symlink or not stat.S_ISDIR(observed.st_mode):
        reason = (
            "source_root_symlink" if source_is_symlink else "source_root_not_directory"
        )
        return SourceAttachmentProbe(
            source_root=root,
            state=AttachmentState.INVALID,
            volume_identity=None,
            root_identity=None,
            identity_strength="unavailable",
            capabilities=_capabilities(
                source_root=root,
                source_stat=observed,
                workspace_stat=workspace_stat,
                atomic_replace=atomic_replace,
                case_sensitive=case_sensitive,
            ),
            blocked_reason=reason,
        )

    return SourceAttachmentProbe(
        source_root=root,
        state=AttachmentState.AVAILABLE,
        volume_identity=f"stat-device-session-v1:{observed.st_dev}",
        root_identity=f"stat-root-v1:{observed.st_dev}:{observed.st_ino}",
        identity_strength="session_local",
        capabilities=_capabilities(
            source_root=root,
            source_stat=observed,
            workspace_stat=workspace_stat,
            atomic_replace=atomic_replace,
            case_sensitive=case_sensitive,
        ),
    )


def new_reuse_domain() -> str:
    """Create an internal boundary that prevents unverified cross-root reuse."""

    return uuid4().hex


def _capabilities(
    *,
    source_root: Path,
    source_stat: os.stat_result | None,
    workspace_stat: os.stat_result,
    atomic_replace: bool,
    case_sensitive: bool | None,
) -> FilesystemCapabilities:
    mount_read_only: bool | None = None
    process_writable: bool | None = None
    same_filesystem: bool | None = None
    if source_stat is not None:
        try:
            readonly_flag = getattr(os, "ST_RDONLY")
            mount_read_only = bool(os.statvfs(source_root).f_flag & readonly_flag)
        except (AttributeError, OSError):
            mount_read_only = None
        process_writable = os.access(source_root, os.W_OK)
        same_filesystem = source_stat.st_dev == workspace_stat.st_dev

    return FilesystemCapabilities(
        source_mount_read_only=mount_read_only,
        source_process_writable=process_writable,
        source_case_sensitivity="unknown_not_probed_on_source",
        workspace_atomic_replace=atomic_replace,
        workspace_case_sensitive=case_sensitive,
        workspace_same_filesystem_as_source=same_filesystem,
        sqlite_locking="not_probed_by_attachment_probe",
        symlink_policy="root_and_descendant_symlinks_not_followed",
    )


def _probe_workspace(workspace: Path) -> tuple[bool, bool | None]:
    descriptor, first_name = tempfile.mkstemp(
        prefix="mediasense-probe-a", dir=workspace
    )
    os.close(descriptor)
    first = Path(first_name)
    replacement = first.with_name(f"{first.name}-replaced")
    swapped = first.with_name(first.name.swapcase())
    try:
        case_sensitive = not swapped.exists() if swapped != first else None
        os.replace(first, replacement)
        atomic_replace = replacement.exists() and not first.exists()
    except OSError:
        atomic_replace = False
    finally:
        first.unlink(missing_ok=True)
        replacement.unlink(missing_ok=True)
    return atomic_replace, case_sensitive


def _is_within(candidate: Path, root: Path) -> bool:
    return candidate.resolve().is_relative_to(root.resolve())
