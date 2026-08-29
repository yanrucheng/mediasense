"""Bounded in-process resource admission for PreCheck Work execution."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import contextmanager
from dataclasses import dataclass, fields
from threading import Condition, Event
from typing import Generic, TypeVar


T = TypeVar("T")


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
]
