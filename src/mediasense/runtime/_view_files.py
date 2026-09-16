"""Private process ownership and bounded diagnostic retention for Plan views."""

from contextlib import contextmanager
import fcntl
import json
from itertools import islice
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import re
import stat
import time

PROTOCOL = "plan-view-lifecycle-1"
FORMAT = "mediasense-plan-view-process"
_LOG = logging.getLogger(__name__)


def private_directory(path, *, create=False):
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise OSError("Unsafe Plan view runtime directory")
    if create:
        path.chmod(0o700)


def open_owned(path, *, create=False):
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT if create else 0), 0o600)
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
    ):
        os.close(fd)
        raise OSError("Unsafe Plan view runtime file")
    return os.fdopen(fd, "r+")


@contextmanager
def lifecycle_lock(root, *, deadline=None, blocking=True):
    """Parent lock never spans bind or waiting for another process to exit."""
    with open_owned(root.parent / "lifecycle.lock", create=True) as stream:
        while True:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not blocking:
                    yield False
                    return
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError("Plan view lifecycle lock deadline exceeded")
                time.sleep(0.02)
        try:
            yield True
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def read_json(path):
    with open_owned(path) as stream:
        return json.load(stream)


def write_header(stream, value):
    stream.seek(0)
    stream.truncate()
    json.dump(value, stream)
    stream.flush()


def recognized(value, build):
    return (
        isinstance(value, dict)
        and value.get("format") == FORMAT
        and value.get("protocol") == PROTOCOL
        and value.get("uid") == os.getuid()
        and value.get("build") == build
        and isinstance(value.get("instance"), str)
    )


def process_state(root):
    """Probe the actual lifetime lock. A failed health check is not death proof."""
    try:
        with open_owned(root / "process.lock") as stream:
            try:
                value = json.load(stream)
            except ValueError:
                value = {}
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return "held", value
            if recognized(value, root.name):
                return "released", value
            return "unknown", value
    except FileNotFoundError:
        return "absent", {}
    except OSError:
        return "unknown", {}


def remove_connection(root, instance):
    try:
        if read_json(root / "connection.json").get("instance") == instance:
            (root / "connection.json").unlink()
    except FileNotFoundError:
        pass


def configure_logging(root):
    for name in ("host.log", "host.log.1"):
        path = root / name
        if path.exists() or path.is_symlink():
            with open_owned(path):
                pass
    handler = RotatingFileHandler(
        root / "host.log", maxBytes=1024 * 1024, backupCount=1
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    return handler


class DiagnosticCleanup:
    """An in-memory iterator; no registry, permanent cursor or cleanup service."""

    def __init__(self, root):
        self.root, self.iterator = root, None

    def close(self):
        if self.iterator is not None:
            self.iterator.close()
            self.iterator = None

    def run(self):
        try:
            with lifecycle_lock(self.root, blocking=False) as acquired:
                if not acquired:
                    return
                deadline = time.monotonic() + 0.1
                if self.iterator is None:
                    self.iterator = os.scandir(self.root.parent)
                for _ in range(16):
                    if time.monotonic() >= deadline:
                        break
                    entry = next(self.iterator, None)
                    if entry is None:
                        self.close()
                        break
                    path = Path(entry.path)
                    if (
                        path == self.root
                        or re.fullmatch(r"[0-9a-f]{64}", entry.name) is None
                    ):
                        continue
                    try:
                        self._remove_old(path)
                    except (OSError, ValueError):
                        _LOG.warning(
                            "Plan view diagnostic cleanup skipped inaccessible files"
                        )
        except OSError:
            _LOG.warning("Plan view diagnostic cleanup unavailable")

    def _remove_old(self, path):
        private_directory(path)
        with open_owned(path / "process.lock") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            value = json.load(stream)
            if not recognized(value, path.name):
                return
            allowed = {
                "process.lock",
                "connection.json",
                "host.log",
                "host.log.1",
                value["instance"] + ".tmp",
            }
            with os.scandir(path) as scan:
                entries = [Path(entry.path) for entry in islice(scan, len(allowed) + 1)]
            if any(p.name not in allowed for p in entries):
                return
            for p in entries:
                with open_owned(p):
                    pass
            if max(p.stat().st_mtime for p in entries) > time.time() - 7 * 86400:
                return
            for p in entries:
                if p.name != "process.lock":
                    p.unlink()
        # Parent lifecycle lock still excludes all conforming starters.
        (path / "process.lock").unlink()
        path.rmdir()
