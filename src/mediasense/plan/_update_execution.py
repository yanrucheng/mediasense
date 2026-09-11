"""Private ownership and cooperative cancellation for one Plan update invocation.

The OS lock only admits validation; SQLite remains authoritative for revisions
and request replay. Nothing here survives as a business state or success receipt.
"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
import fcntl
import hashlib
import logging
import os
from pathlib import Path
import stat
from threading import Event, Lock
from time import monotonic
from types import SimpleNamespace


_LOGGER = logging.getLogger(__name__)


class UpdateCancelled(BaseException):
    """Cancellation control flow must not become a candidate validation issue."""


class UpdateOwnershipError(RuntimeError):
    """The local execution lock could not be safely acquired."""


class UpdateExecution:
    def __init__(
        self,
        *,
        check_cancelled: Callable[[], None] | None = None,
        observe: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self._probe = check_cancelled
        self._observe = observe
        self._cancelled = Event()
        self._gate = Lock()
        self._committing = False
        self._used = False
        self._started = monotonic()
        self._last_report = self._started
        self._phase = "accepted"
        self._work_ref = self._request_id = None
        self.read_calls = 0
        self.read_seconds = 0.0

    def cancel(self) -> None:
        with self._gate:
            self._cancelled.set()

    @property
    def commit_started(self) -> bool:
        return self._committing

    def _check(self) -> None:
        if not self._committing:
            if self._cancelled.is_set():
                raise UpdateCancelled()
            if self._probe is not None:
                self._probe()

    def checkpoint(self) -> None:
        with self._gate:
            self._check()

    def begin_commit(self) -> None:
        # Arbitration point: cancellation observed here wins without mutation;
        # otherwise the short atomic store transaction owns the final outcome.
        with self._gate:
            self._check()
            self._committing = True
        # Never wait for a progress transport while holding a DB write transaction.
        self.report("committing", notify=False)

    @contextmanager
    def operation(self, work_ref: str, request_id: str) -> Iterator[None]:
        with self._gate:
            if self._used:
                raise RuntimeError("An update execution context is single-use")
            self._used = True
        self._work_ref, self._request_id = work_ref, request_id
        self._started = monotonic()
        self.report("accepted")
        try:
            self.checkpoint()
            yield
        except UpdateCancelled:
            self.report("cancelled")
            raise
        except BaseException:
            self.report("failed")
            raise

    def report(self, phase: str, *, notify: bool = True) -> None:
        now = monotonic()
        self._phase, self._last_report = phase, now
        event = {
            "phase": phase,
            "work_ref": self._work_ref,
            "request_id": self._request_id,
            "elapsed_seconds": round(now - self._started, 6),
            "read_calls": self.read_calls,
            "read_seconds": round(self.read_seconds, 6),
        }
        _LOGGER.info("Plan update %s", event)
        if notify and self._observe is not None:
            self._observe(event)

    def reader(self, reader):
        def read(request):
            self.checkpoint()
            started = monotonic()
            try:
                response = reader.read(request)
            finally:
                self.read_calls += 1
                self.read_seconds += monotonic() - started
            self.checkpoint()
            if monotonic() - self._last_report >= 1:
                self.report(self._phase)
            return response

        return SimpleNamespace(name=reader.name, read=read)

    def wait(self) -> None:
        self._cancelled.wait(0.05)
        self.checkpoint()


@contextmanager
def update_ownership(database: Path, work_ref: str, execution: UpdateExecution):
    # Separate opens conflict both within a process and across Hosts. Never
    # unlink these files: recreating a path could admit two different inodes.
    database = database.resolve()
    directory = database.parent / (database.name + ".updates")
    path = directory / hashlib.sha256(work_ref.encode()).hexdigest()
    try:
        directory.mkdir(exist_ok=True)
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    except OSError as error:
        raise UpdateOwnershipError("Plan update ownership is unavailable") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise UpdateOwnershipError("Plan update ownership is not a regular file")
        waiting = False
        while True:
            execution.checkpoint()
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not waiting:
                    execution.report("waiting")
                    waiting = True
                execution.wait()
            except OSError as error:
                raise UpdateOwnershipError(
                    "Plan update ownership is unavailable"
                ) from error
        try:
            execution.checkpoint()
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)
