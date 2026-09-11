"""Read the sealed bytes through stable, non-symlink workspace-relative handles."""

from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import stat


def _identity(value):
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def read_sealed_bytes(
    workspace, relative_path, expected_size, expected_digest, cached_identity=None
):
    """Always hash current bytes; retain them only when semantic validation is needed."""
    relative = Path(relative_path)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Sealed Result path escapes its workspace")
    root = Path(workspace).resolve(strict=True)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as opened:
        root_fd = os.open(root, directory_flags)
        opened.callback(os.close, root_fd)
        root_stat = os.fstat(root_fd)
        parent = root_fd
        directories = []
        for part in relative.parts[:-1]:
            descriptor = os.open(part, directory_flags, dir_fd=parent)
            opened.callback(os.close, descriptor)
            directories.append((parent, part, os.fstat(descriptor)))
            parent = descriptor
        descriptor = os.open(
            relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
        opened.callback(os.close, descriptor)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("Sealed Result is not a regular file")
        if before.st_size != expected_size:
            raise ValueError("Sealed Result integrity verification failed")
        identity = _identity(before)
        encoded = None
        if identity != cached_identity:
            # One buffer for a cold read, rather than retaining both chunks and
            # their joined copy alongside a large decoded graph.
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                encoded = stream.read(expected_size + 1)
            size, digest = len(encoded), hashlib.sha256(encoded).hexdigest()
        else:
            hasher, size = hashlib.sha256(), 0
            while chunk := os.read(
                descriptor, min(1024 * 1024, expected_size - size + 1)
            ):
                hasher.update(chunk)
                size += len(chunk)
                if size > expected_size:
                    break
            digest = hasher.hexdigest()
        if size != expected_size or digest != expected_digest:
            raise ValueError("Sealed Result integrity verification failed")
        if (
            _identity(os.fstat(descriptor)) != identity
            or _identity(os.stat(relative.name, dir_fd=parent, follow_symlinks=False))
            != identity
        ):
            raise ValueError("Sealed Result changed while reading")
        for directory, name, observed in directories:
            current = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if (current.st_dev, current.st_ino, current.st_mode) != (
                observed.st_dev,
                observed.st_ino,
                observed.st_mode,
            ):
                raise ValueError("Sealed Result directory changed while reading")
        current_root = root.stat(follow_symlinks=False)
        if (current_root.st_dev, current_root.st_ino, current_root.st_mode) != (
            root_stat.st_dev,
            root_stat.st_ino,
            root_stat.st_mode,
        ) or Path(workspace).resolve(strict=True) != root:
            raise ValueError("Result workspace changed while reading")
        return encoded, identity
