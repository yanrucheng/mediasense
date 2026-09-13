"""Bounded in-process resource admission for PreCheck Work execution."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, fields
import os
from pathlib import Path
import platform
import plistlib
import re
import subprocess
from threading import Condition, Event
from typing import Generic, Protocol, Sequence, TypeVar


T = TypeVar("T")


class ProbeRunner(Protocol):
    def __call__(
        self, command: Sequence[str]
    ) -> subprocess.CompletedProcess[bytes]: ...


class ResourceLimitExceeded(ValueError):
    """Raised when one Work claim can never fit within the active budget."""


class ResourceAdmissionCancelled(RuntimeError):
    """Raised when waiting Work is stopped before resource admission."""


@dataclass(frozen=True, slots=True)
class ResourceClaim:
    source_io_slots: int = 0
    workspace_io_slots: int = 0
    cpu_slots: int = 0
    process_slots: int = 0
    memory_bytes: int = 0
    temporary_bytes: int = 0
    gpu_memory_bytes: int = 0
    model_slots: int = 0
    exiftool_slots: int = 0
    decoder_slots: int = 0
    encoder_slots: int = 0
    network_slots: int = 0

    def __post_init__(self) -> None:
        if any(getattr(self, field.name) < 0 for field in fields(self)):
            raise ValueError("resource values must be nonnegative")


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    capacity: ResourceClaim
    max_workers: int
    max_pending: int

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("resource budget requires at least one worker")
        if self.max_pending < self.max_workers:
            raise ValueError("max_pending must be at least max_workers")


def resolve_resource_budget(
    *,
    source_storage: str,
    network_enabled: bool = False,
    memory_target_bytes: int = 4 * 1024**3,
    ceiling: ResourceBudget | None = None,
    logical_cpu_count: int | None = None,
    available_memory_bytes: int | None = None,
) -> ResourceBudget:
    """Resolve one conservative host-aware budget for a Run.

    ``source_storage`` is deliberately coarse. ``local`` means a positively
    identified local solid-state source, not merely a source on the same
    filesystem as the workspace. Remote and unknown sources share the
    conservative path.
    """

    if source_storage not in {"local", "remote", "unknown"}:
        raise ValueError("source_storage must be local, remote, or unknown")
    cpu_count = max(1, logical_cpu_count or os.cpu_count() or 1)
    available_memory = (
        _available_memory_bytes()
        if available_memory_bytes is None
        else available_memory_bytes
    )
    if available_memory is not None and available_memory < 1:
        raise ValueError("available memory must be positive when known")

    cpu_slots = min(8, max(1, cpu_count - 1 if cpu_count > 2 else cpu_count))
    memory_bytes = (
        512 * 1024 * 1024
        if available_memory is None
        else max(
            128 * 1024 * 1024,
            min(
                memory_target_bytes,
                available_memory // 2
                if memory_target_bytes <= 4 * 1024**3
                else max(0, available_memory - 4 * 1024**3),
            ),
        )
    )
    memory_workers = max(1, memory_bytes // (128 * 1024 * 1024))
    local = source_storage == "local"
    source_lanes = min(4, max(1, cpu_count // 2)) if local else 1
    process_lanes = min(source_lanes, max(1, cpu_slots // 2))
    worker_count = min(8, cpu_slots, memory_workers)
    resolved = ResourceBudget(
        capacity=ResourceClaim(
            source_io_slots=source_lanes,
            workspace_io_slots=min(4, max(1, cpu_count // 2)),
            cpu_slots=cpu_slots,
            process_slots=process_lanes,
            memory_bytes=memory_bytes,
            temporary_bytes=1024 * 1024 * 1024,
            gpu_memory_bytes=(
                0 if ceiling is None else ceiling.capacity.gpu_memory_bytes
            ),
            model_slots=1,
            exiftool_slots=process_lanes,
            decoder_slots=process_lanes,
            encoder_slots=process_lanes,
            network_slots=1 if network_enabled else 0,
        ),
        max_workers=worker_count,
        max_pending=max(worker_count * 2, worker_count),
    )
    return resolved if ceiling is None else _bounded_budget(resolved, ceiling)


def _available_memory_bytes(
    *,
    system: str | None = None,
    command_runner: ProbeRunner | None = None,
) -> int | None:
    if (system or platform.system()) == "Darwin":
        return _darwin_available_memory_bytes(command_runner=command_runner)
    try:
        pages = os.sysconf("SC_AVPHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
    except (AttributeError, OSError, ValueError):
        return None
    if not isinstance(pages, int) or not isinstance(page_size, int):
        return None
    return pages * page_size if pages > 0 and page_size > 0 else None


def _darwin_available_memory_bytes(
    *, command_runner: ProbeRunner | None = None
) -> int | None:
    runner = command_runner or _run_probe
    try:
        completed = runner(("/usr/bin/vm_stat",))
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    try:
        output = completed.stdout.decode("utf-8", errors="replace")
    except AttributeError:
        return None
    return _parse_darwin_vm_stat(output)


def _parse_darwin_vm_stat(output: str) -> int | None:
    page_match = re.search(r"page size of\s+(\d+) bytes", output)
    if page_match is None:
        return None
    page_size = int(page_match.group(1))
    page_counts: dict[str, int] = {}
    for name, count in re.findall(
        r"^Pages (free|inactive|speculative):\s+(\d+)\.\s*$",
        output,
        flags=re.MULTILINE,
    ):
        page_counts[name] = int(count)
    if "free" not in page_counts:
        return None
    # Inactive and speculative pages are reclaimable. Purgeable pages are not
    # added because Darwin may also count them as inactive.
    available_pages = sum(
        page_counts.get(name, 0) for name in ("free", "inactive", "speculative")
    )
    return available_pages * page_size if available_pages > 0 else None


def detect_source_storage(
    source_root: Path,
    *,
    system: str | None = None,
    command_runner: ProbeRunner | None = None,
) -> tuple[str, str]:
    """Return a conservative storage class and the evidence used for it."""

    if (system or platform.system()) != "Darwin":
        return "unknown", "unsupported_platform_storage_probe"
    runner = command_runner or _run_probe
    probe_target = str(Path(source_root))
    try:
        completed = runner(("/usr/sbin/diskutil", "info", "-plist", probe_target))
    except (OSError, subprocess.SubprocessError):
        return "unknown", "darwin_diskutil_unavailable"
    if completed.returncode != 0:
        try:
            filesystem = runner(("/bin/df", "-P", probe_target))
        except (OSError, subprocess.SubprocessError):
            return "unknown", "darwin_diskutil_failed"
        if filesystem.returncode != 0:
            return "unknown", "darwin_diskutil_failed"
        lines = filesystem.stdout.decode("utf-8", errors="replace").splitlines()
        if len(lines) < 2 or len(lines[-1].split(maxsplit=5)) < 6:
            return "unknown", "darwin_mount_point_unavailable"
        mount_point = lines[-1].split(maxsplit=5)[-1]
        try:
            completed = runner(("/usr/sbin/diskutil", "info", "-plist", mount_point))
        except (OSError, subprocess.SubprocessError):
            return "unknown", "darwin_diskutil_unavailable"
        if completed.returncode != 0:
            return "unknown", "darwin_diskutil_failed"
    try:
        details = plistlib.loads(completed.stdout)
    except (plistlib.InvalidFileException, TypeError, ValueError):
        return "unknown", "darwin_diskutil_invalid"
    volume_kind = str(details.get("FilesystemType") or details.get("VolumeKind") or "")
    if volume_kind.casefold() in {"afpfs", "nfs", "smbfs", "webdav"}:
        return "remote", f"darwin_diskutil_filesystem:{volume_kind.casefold()}"
    physical = (
        details.get("VirtualOrPhysical") == "Physical"
        or details.get("Internal") is True
    )
    if details.get("SolidState") is True and physical:
        return "local", "darwin_diskutil_physical_solid_state"
    if details.get("SolidState") is False:
        return "unknown", "darwin_diskutil_non_solid_state"
    return "unknown", "darwin_diskutil_no_solid_state_evidence"


def _run_probe(command: Sequence[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        timeout=2,
    )


def _bounded_budget(
    detected: ResourceBudget,
    ceiling: ResourceBudget,
) -> ResourceBudget:
    capacity = ResourceClaim(
        **{
            item.name: min(
                getattr(detected.capacity, item.name),
                getattr(ceiling.capacity, item.name),
            )
            for item in fields(ResourceClaim)
        }
    )
    max_workers = min(detected.max_workers, ceiling.max_workers)
    return ResourceBudget(
        capacity=capacity,
        max_workers=max_workers,
        max_pending=max(max_workers, min(detected.max_pending, ceiling.max_pending)),
    )


@dataclass(frozen=True, slots=True)
class ScheduledCall(Generic[T]):
    key: str
    claim: ResourceClaim
    function: Callable[[], T]

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("scheduled call key must be non-empty")


@dataclass(frozen=True, slots=True)
class ScheduledOutcome(Generic[T]):
    key: str
    value: T | None
    error: Exception | None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class ResourceAdmission:
    """Coordinate current and peak resource use without becoming state authority."""

    def __init__(self, capacity: ResourceClaim) -> None:
        self.capacity = capacity
        self._used = ResourceClaim()
        self._peak = ResourceClaim()
        self._condition = Condition()

    @contextmanager
    def hold(
        self,
        claim: ResourceClaim,
        *,
        cancel: Event | None = None,
    ) -> Iterator[None]:
        if not _fits(claim, self.capacity):
            raise ResourceLimitExceeded("Work resource claim exceeds the run budget")
        with self._condition:
            while not _fits(_add(self._used, claim), self.capacity):
                if cancel is not None and cancel.is_set():
                    raise ResourceAdmissionCancelled(
                        "resource admission cancelled while waiting"
                    )
                self._condition.wait(timeout=0.05)
            self._used = _add(self._used, claim)
            self._peak = _max(self._peak, self._used)
        try:
            yield
        finally:
            with self._condition:
                self._used = _subtract(self._used, claim)
                self._condition.notify_all()

    def usage(self) -> ResourceClaim:
        with self._condition:
            return self._used

    def peak_usage(self) -> ResourceClaim:
        with self._condition:
            return self._peak


class BoundedWorkExecutor:
    """Consume an iterable lazily and isolate each admitted call's outcome."""

    def __init__(self, budget: ResourceBudget) -> None:
        self.budget = budget
        self.admission = ResourceAdmission(budget.capacity)

    def run(
        self,
        calls: Iterable[ScheduledCall[T]],
        *,
        cancel: Event | None = None,
    ) -> tuple[ScheduledOutcome[T], ...]:
        return tuple(self.iter_run(calls, cancel=cancel))

    def iter_run(
        self,
        calls: Iterable[ScheduledCall[T]],
        *,
        cancel: Event | None = None,
    ) -> Iterator[ScheduledOutcome[T]]:
        iterator = iter(calls)
        pending: set[Future[ScheduledOutcome[T]]] = set()

        def submit_one(pool: ThreadPoolExecutor) -> bool:
            if cancel is not None and cancel.is_set():
                return False
            try:
                call = next(iterator)
            except StopIteration:
                return False
            future = pool.submit(self._execute, call, cancel)
            pending.add(future)
            return True

        with ThreadPoolExecutor(max_workers=self.budget.max_workers) as pool:
            while len(pending) < self.budget.max_pending and submit_one(pool):
                pass
            while pending:
                completed, _waiting = wait(tuple(pending), return_when=FIRST_COMPLETED)
                for future in completed:
                    pending.remove(future)
                    yield future.result()
                while len(pending) < self.budget.max_pending and submit_one(pool):
                    pass

    def _execute(
        self,
        call: ScheduledCall[T],
        cancel: Event | None,
    ) -> ScheduledOutcome[T]:
        try:
            with self.admission.hold(call.claim, cancel=cancel):
                if cancel is not None and cancel.is_set():
                    raise ResourceAdmissionCancelled(
                        "scheduled call cancelled before execution"
                    )
                return ScheduledOutcome(call.key, call.function(), None)
        except Exception as error:
            return ScheduledOutcome(call.key, None, error)


def _fits(value: ResourceClaim, capacity: ResourceClaim) -> bool:
    return all(
        getattr(value, field.name) <= getattr(capacity, field.name)
        for field in fields(value)
    )


def _add(left: ResourceClaim, right: ResourceClaim) -> ResourceClaim:
    return ResourceClaim(
        **{
            field.name: getattr(left, field.name) + getattr(right, field.name)
            for field in fields(left)
        }
    )


def _subtract(left: ResourceClaim, right: ResourceClaim) -> ResourceClaim:
    return ResourceClaim(
        **{
            field.name: getattr(left, field.name) - getattr(right, field.name)
            for field in fields(left)
        }
    )


def _max(left: ResourceClaim, right: ResourceClaim) -> ResourceClaim:
    return ResourceClaim(
        **{
            field.name: max(getattr(left, field.name), getattr(right, field.name))
            for field in fields(left)
        }
    )


__all__ = [
    "BoundedWorkExecutor",
    "ResourceAdmission",
    "ResourceAdmissionCancelled",
    "ResourceBudget",
    "ResourceClaim",
    "ResourceLimitExceeded",
    "ScheduledCall",
    "ScheduledOutcome",
    "resolve_resource_budget",
]
