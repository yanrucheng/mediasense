"""Bounded filesystem effects for the active ``move_originals`` profile."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
import ctypes
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from typing import Any, Protocol
import unicodedata


_CHUNK_SIZE = 1024 * 1024
_RENAME_EXCL = 0x00000004
_COPYFILE_ALL = 0x0000000F
_COPYFILE_EXCL = 1 << 17
_COPYFILE_NOFOLLOW = (1 << 18) | (1 << 19)


class FilesystemEffectError(RuntimeError):
    """A filesystem effect could not be performed or verified safely."""

    def __init__(self, code: str, message: str, *, global_risk: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.global_risk = global_risk


@dataclass(frozen=True, slots=True)
class MetadataDiscrepancy:
    attribute: str
    expected: object
    observed: object


@dataclass(frozen=True, slots=True)
class EffectObservation:
    status: str
    bytes_moved: int
    source_after: str
    target_after: str
    verification_profile: str
    verification_basis: str
    temporary_path: str | None = None
    discrepancies: tuple[MetadataDiscrepancy, ...] = ()


class FilesystemBoundary(Protocol):
    """Replaceable effect boundary consumed by the Apply executor."""

    def move(
        self,
        *,
        source: Path,
        target: Path,
        expected_digest: str,
        expected_size: int,
        route: str,
        temporary_path: Path | None,
        accepted_discrepancies: tuple[MetadataDiscrepancy, ...] = (),
        expected_source_stat: tuple[int, int, int] | None = None,
    ) -> EffectObservation: ...

    def reconcile(
        self,
        *,
        source: Path,
        target: Path,
        expected_digest: str,
        expected_size: int,
        route: str,
        temporary_path: Path | None,
        accepted_discrepancies: tuple[MetadataDiscrepancy, ...] = (),
        expected_source_stat: tuple[int, int, int] | None = None,
    ) -> EffectObservation: ...


def _with_effect_reservation(
    method: Callable[..., EffectObservation],
) -> Callable[..., EffectObservation]:
    def reserved(self: object, **kwargs: Any) -> EffectObservation:
        source = kwargs.get("source")
        target = kwargs.get("target")
        if not isinstance(source, Path) or not isinstance(target, Path):
            raise FilesystemEffectError(
                "concurrency_conflict",
                "filesystem effect reservation requires exact source and target paths",
                global_risk=True,
            )
        with _effect_reservation(
            source=source,
            target=target,
            expected_source_stat=kwargs.get("expected_source_stat"),
        ):
            try:
                return method(self, **kwargs)
            except FilesystemEffectError:
                raise
            except OSError as error:
                raise _normalized_filesystem_error(error) from error

    return reserved


class LocalFilesystem:
    """Production filesystem adapter with explicit platform support."""

    @_with_effect_reservation
    def move(
        self,
        *,
        source: Path,
        target: Path,
        expected_digest: str,
        expected_size: int,
        route: str,
        temporary_path: Path | None,
        accepted_discrepancies: tuple[MetadataDiscrepancy, ...] = (),
        expected_source_stat: tuple[int, int, int] | None = None,
    ) -> EffectObservation:
        verify_file(
            source,
            expected_digest,
            expected_size,
            expected_stat=expected_source_stat,
        )
        if _lexists(target):
            raise FilesystemEffectError(
                "target_collision", f"final target already exists: {target}"
            )
        if route == "same_filesystem_atomic_move":
            if source.stat(follow_symlinks=False).st_dev != target.parent.stat().st_dev:
                raise FilesystemEffectError(
                    "filesystem_route_changed",
                    "source and target are no longer on the prepared filesystem",
                    global_risk=True,
                )
            rename_exclusive(source, target)
            _fsync_directory(target.parent)
            verify_file(target, expected_digest, expected_size)
            if _lexists(source):
                raise FilesystemEffectError(
                    "postcondition_failed", "source still exists after atomic move"
                )
            return EffectObservation(
                status="completed",
                bytes_moved=expected_size,
                source_after="absent",
                target_after="verified_present",
                verification_profile="same_filesystem_identity_and_location",
                verification_basis="Target bytes matched and original location was absent.",
            )
        if route != "verified_cross_filesystem_transfer":
            raise FilesystemEffectError(
                "filesystem_route_unsupported", f"unsupported execution route: {route}"
            )
        return self._cross_filesystem_move(
            source=source,
            target=target,
            expected_digest=expected_digest,
            expected_size=expected_size,
            temporary_path=temporary_path,
            accepted_discrepancies=accepted_discrepancies,
        )

    @_with_effect_reservation
    def reconcile(
        self,
        *,
        source: Path,
        target: Path,
        expected_digest: str,
        expected_size: int,
        route: str,
        temporary_path: Path | None,
        accepted_discrepancies: tuple[MetadataDiscrepancy, ...] = (),
        expected_source_stat: tuple[int, int, int] | None = None,
    ) -> EffectObservation:
        source_exists = _lexists(source)
        target_exists = _lexists(target)
        if not source_exists and target_exists:
            verify_file(target, expected_digest, expected_size)
            return EffectObservation(
                status="completed",
                bytes_moved=expected_size,
                source_after="absent",
                target_after="verified_present",
                verification_profile=(
                    "same_filesystem_identity_and_location"
                    if route == "same_filesystem_atomic_move"
                    else "cross_filesystem_content_and_metadata"
                ),
                verification_basis=(
                    "Recovery observed the verified target and absent source."
                ),
                temporary_path=str(temporary_path) if temporary_path else None,
            )
        if source_exists and not target_exists:
            if temporary_path is not None and _lexists(temporary_path):
                verify_file(temporary_path, expected_digest, expected_size)
                return EffectObservation(
                    status="retryable",
                    bytes_moved=0,
                    source_after="present",
                    target_after="absent",
                    verification_profile="cross_filesystem_content_and_metadata",
                    verification_basis="Verified non-final copy awaits safe publication.",
                    temporary_path=str(temporary_path),
                )
            verify_file(
                source,
                expected_digest,
                expected_size,
                expected_stat=expected_source_stat,
            )
            return EffectObservation(
                status="retryable",
                bytes_moved=0,
                source_after="present",
                target_after="absent",
                verification_profile="effect_boundary_source_verification",
                verification_basis="Source remains verified and final target is absent.",
            )
        if source_exists and target_exists:
            if route == "verified_cross_filesystem_transfer":
                verify_file(
                    source,
                    expected_digest,
                    expected_size,
                    expected_stat=expected_source_stat,
                )
                verify_file(target, expected_digest, expected_size)
                discrepancies = tuple(compare_declared_metadata(source, target))
                if discrepancies == accepted_discrepancies:
                    source.unlink()
                    _fsync_directory(source.parent)
                    return EffectObservation(
                        status="completed",
                        bytes_moved=expected_size,
                        source_after="absent",
                        target_after="verified_present",
                        verification_profile="cross_filesystem_content_and_metadata",
                        verification_basis=(
                            "Recovery verified the exclusively published target and "
                            "removed the retained source."
                        ),
                    )
            raise FilesystemEffectError(
                "duplicate_presence",
                "both source and final target exist; automatic recovery is unsafe",
            )
        raise FilesystemEffectError(
            "effect_indeterminate",
            "neither source nor final target exists",
            global_risk=True,
        )

    def _cross_filesystem_move(
        self,
        *,
        source: Path,
        target: Path,
        expected_digest: str,
        expected_size: int,
        temporary_path: Path | None,
        accepted_discrepancies: tuple[MetadataDiscrepancy, ...],
    ) -> EffectObservation:
        if sys.platform != "darwin":
            raise FilesystemEffectError(
                "filesystem_profile_unsupported",
                "cross_filesystem_user_metadata_v1 currently requires Darwin",
                global_risk=True,
            )
        temporary = temporary_path or target.with_name(
            f".{target.name}.mediasense-partial"
        )
        if has_nontrivial_acl(source):
            raise FilesystemEffectError(
                "filesystem_profile_unsupported",
                "cross-filesystem move blocks ACL-bearing sources until the profile is proven",
                global_risk=True,
            )
        if _lexists(temporary):
            verify_file(temporary, expected_digest, expected_size)
        else:
            _copyfile_all_exclusive(source, temporary)
        verify_file(temporary, expected_digest, expected_size)
        discrepancies = compare_declared_metadata(source, temporary)
        if discrepancies and tuple(discrepancies) != accepted_discrepancies:
            return EffectObservation(
                status="metadata_loss",
                bytes_moved=expected_size,
                source_after="present",
                target_after="absent",
                verification_profile="cross_filesystem_content_and_metadata",
                verification_basis="Target bytes matched; declared metadata differs.",
                temporary_path=str(temporary),
                discrepancies=tuple(discrepancies),
            )
        _fsync_file_and_parent(temporary)
        rename_exclusive(temporary, target)
        _fsync_file_and_parent(target)
        verify_file(target, expected_digest, expected_size)
        source.unlink()
        _fsync_directory(source.parent)
        return EffectObservation(
            status="completed",
            bytes_moved=expected_size,
            source_after="absent",
            target_after="verified_present",
            verification_profile="cross_filesystem_content_and_metadata",
            verification_basis=(
                "Target bytes and declared metadata matched before source deletion."
            ),
        )


def verify_file(
    path: Path,
    expected_digest: str,
    expected_size: int,
    *,
    expected_stat: tuple[int, int, int] | None = None,
) -> None:
    """Verify one regular non-symlink file without accepting a read-time drift."""

    try:
        before = path.stat(follow_symlinks=False)
    except FileNotFoundError as error:
        raise FilesystemEffectError(
            "source_missing", f"file is missing: {path}"
        ) from error
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise FilesystemEffectError(
            "source_unsafe_type", f"file is not a regular non-symlink object: {path}"
        )
    if (
        expected_stat is not None
        and (
            before.st_dev,
            before.st_ino,
            before.st_mtime_ns,
        )
        != expected_stat
    ):
        raise FilesystemEffectError(
            "source_stale", f"source object changed after preparation: {path}"
        )
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            size += len(chunk)
            digest.update(chunk)
    after = path.stat(follow_symlinks=False)
    if (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise FilesystemEffectError(
            "source_changed_during_read", f"file changed while being verified: {path}"
        )
    observed = "sha256:" + digest.hexdigest()
    if size != expected_size:
        raise FilesystemEffectError(
            "source_size_mismatch", f"file size changed since preparation: {path}"
        )
    if observed != expected_digest:
        raise FilesystemEffectError(
            "source_digest_mismatch", f"file content changed since preparation: {path}"
        )


def ensure_directories(root: Path, parent: Path) -> list[Path]:
    """Create only missing descendants beneath an existing destination root."""

    root = root.resolve(strict=True)
    try:
        relative = parent.relative_to(root)
    except ValueError as error:
        raise FilesystemEffectError(
            "target_escape",
            "target directory escapes destination parent",
            global_risk=True,
        ) from error
    created: list[Path] = []
    current = root
    for segment in relative.parts:
        current = current / segment
        try:
            current.mkdir()
            created.append(current)
            _fsync_directory(current.parent)
        except FileExistsError:
            if current.is_symlink() or not current.is_dir():
                raise FilesystemEffectError(
                    "target_namespace_changed",
                    f"target directory component is unsafe: {current}",
                    global_risk=True,
                )
    return created


def planned_directories(root: Path, parent: Path) -> list[Path]:
    """Return missing descendants after rejecting unsafe existing components."""

    root = root.resolve(strict=True)
    try:
        relative = parent.relative_to(root)
    except ValueError as error:
        raise FilesystemEffectError(
            "target_escape",
            "target directory escapes destination parent",
            global_risk=True,
        ) from error
    missing: list[Path] = []
    current = root
    for segment in relative.parts:
        current = current / segment
        if _lexists(current):
            if current.is_symlink() or not current.is_dir():
                raise FilesystemEffectError(
                    "target_namespace_changed",
                    f"target directory component is unsafe: {current}",
                    global_risk=True,
                )
        else:
            missing.append(current)
    return missing


def rename_exclusive(source: Path, target: Path) -> None:
    """Rename without replacement using a platform atomic primitive."""

    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        renamex = libc.renamex_np
        renamex.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        renamex.restype = ctypes.c_int
        if renamex(os.fsencode(source), os.fsencode(target), _RENAME_EXCL) != 0:
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(target))
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is not None:
            renameat2.argtypes = [
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            ]
            renameat2.restype = ctypes.c_int
            if renameat2(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0:
                code = ctypes.get_errno()
                raise OSError(code, os.strerror(code), str(target))
            return
    if source.stat(follow_symlinks=False).st_nlink == 1:
        try:
            os.link(source, target, follow_symlinks=False)
        except FileExistsError:
            raise
        except OSError as error:
            raise FilesystemEffectError(
                "atomic_move_unsupported",
                f"non-overwriting same-filesystem move is unsupported: {error}",
                global_risk=True,
            ) from error
        try:
            source.unlink()
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return
    raise FilesystemEffectError(
        "atomic_move_unsupported",
        "non-overwriting atomic rename is unsupported for multiply linked sources",
        global_risk=True,
    )


def declared_metadata(path: Path) -> dict[str, object]:
    info = path.stat(follow_symlinks=False)
    metadata: dict[str, object] = {
        "mode": stat.S_IMODE(info.st_mode),
        "uid": info.st_uid,
        "gid": info.st_gid,
        "mtime_ns": info.st_mtime_ns,
        "xattrs": {
            name: os.getxattr(path, name, follow_symlinks=False).hex()
            for name in sorted(os.listxattr(path, follow_symlinks=False))
        },
    }
    if hasattr(info, "st_birthtime"):
        metadata["birthtime_ns"] = int(info.st_birthtime * 1_000_000_000)
    if hasattr(info, "st_flags"):
        metadata["flags"] = info.st_flags
    return metadata


def compare_declared_metadata(source: Path, target: Path) -> list[MetadataDiscrepancy]:
    expected = declared_metadata(source)
    observed = declared_metadata(target)
    return [
        MetadataDiscrepancy(name, expected[name], observed.get(name))
        for name in expected
        if expected[name] != observed.get(name)
    ]


def canonical_identity(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _copyfile_all_exclusive(source: Path, target: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    copyfile = libc.copyfile
    copyfile.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_uint,
    ]
    copyfile.restype = ctypes.c_int
    flags = _COPYFILE_ALL | _COPYFILE_EXCL | _COPYFILE_NOFOLLOW
    if copyfile(os.fsencode(source), os.fsencode(target), None, flags) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(target))


def has_nontrivial_acl(path: Path) -> bool:
    """Detect Darwin ACL entries without treating ordinary mode text as an ACL."""

    result = subprocess.run(
        ["/bin/ls", "-lde", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FilesystemEffectError(
            "metadata_inspection_failed",
            f"cannot inspect ACL metadata for {path}",
            global_risk=True,
        )
    return any(
        line.lstrip().partition(":")[0].isdigit() for line in result.stdout.splitlines()
    )


def _fsync_file_and_parent(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _effect_reservation(
    *,
    source: Path,
    target: Path,
    expected_source_stat: tuple[int, int, int] | None,
):
    """Serialize overlapping effects across Run stores for this OS account."""

    lock_root = Path(tempfile.gettempdir()) / f"mediasense-apply-locks-{os.getuid()}"
    try:
        lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root_stat = lock_root.stat(follow_symlinks=False)
    except OSError as error:
        raise FilesystemEffectError(
            "concurrency_conflict",
            "cannot establish the global Apply effect reservation domain",
            global_risk=True,
        ) from error
    if lock_root.is_symlink() or not stat.S_ISDIR(root_stat.st_mode):
        raise FilesystemEffectError(
            "concurrency_conflict",
            "the global Apply effect reservation domain is unsafe",
            global_risk=True,
        )
    if root_stat.st_uid != os.getuid():
        raise FilesystemEffectError(
            "concurrency_conflict",
            "the global Apply effect reservation domain has the wrong owner",
            global_risk=True,
        )
    if expected_source_stat is None:
        source_key = f"path:{source.resolve(strict=False)}"
    else:
        source_key = f"object:{expected_source_stat[0]}:{expected_source_stat[1]}"
    target_key = (
        "target:"
        + unicodedata.normalize("NFD", str(target.resolve(strict=False))).casefold()
    )
    handles = []
    try:
        for key in sorted({source_key, target_key}):
            token = hashlib.sha256(key.encode("utf-8")).hexdigest()
            flags = os.O_CREAT | os.O_RDWR
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            try:
                descriptor = os.open(lock_root / f"{token}.lock", flags, 0o600)
                handle = os.fdopen(descriptor, "a+b")
            except OSError as error:
                raise FilesystemEffectError(
                    "concurrency_conflict",
                    "cannot open an Apply effect reservation",
                    global_risk=True,
                ) from error
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (BlockingIOError, OSError) as error:
                handle.close()
                raise FilesystemEffectError(
                    "concurrency_conflict",
                    "another Apply Run owns an overlapping source or target reservation",
                    global_risk=True,
                ) from error
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _normalized_filesystem_error(error: OSError) -> FilesystemEffectError:
    code = error.errno
    if code in {errno.ENOSPC, getattr(errno, "EDQUOT", -1)}:
        reason = "insufficient_capacity"
    elif code in {errno.EACCES, errno.EPERM, errno.EROFS}:
        reason = "permission_denied"
    elif code in {
        errno.ENODEV,
        errno.ENXIO,
        errno.EIO,
        getattr(errno, "ESTALE", -1),
        getattr(errno, "ENOTCONN", -1),
    }:
        reason = "volume_unavailable"
    elif code == errno.EEXIST:
        return FilesystemEffectError(
            "target_collision", f"final target appeared during publication: {error}"
        )
    else:
        reason = "filesystem_io_failure"
    return FilesystemEffectError(reason, str(error), global_risk=True)
