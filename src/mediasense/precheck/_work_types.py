"""Private value types for reusable PreCheck work and lease state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from pathlib import Path


class DependencyKind(StrEnum):
    SOURCE_REVISION = "source_revision"
    UPSTREAM_WORK = "upstream_work"
    PARAMETER = "parameter"
    MODEL = "model"
    ENVIRONMENT = "environment"


class WorkStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    BLOCKED = "blocked"
    INVALIDATED = "invalidated"
    CANCELLED = "cancelled"


class AttemptOutcome(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    TERMINAL_FAILURE = "terminal_failure"
    LEASE_EXPIRED = "lease_expired"
    INVALIDATED = "invalidated"
    CANCELLED = "cancelled"


class WorkStateError(RuntimeError):
    """Base error for an invalid Work Record operation."""


class WorkIdentityCollision(WorkStateError):
    """Raised when a semantic-key collision does not match its descriptor."""


class InvalidWorkTransition(WorkStateError):
    """Raised when a Work Record cannot make the requested transition."""


class LeaseLost(WorkStateError):
    """Raised when a worker no longer owns the active lease."""


class InvalidWorkSpec(ValueError):
    """Raised when a semantic descriptor is empty, ambiguous, or too broad."""


_FORBIDDEN_BLANKET_KEYS = {
    "application_version",
    "dataset_version",
    "full_configuration",
    "repository_commit",
}


@dataclass(frozen=True, slots=True, order=True)
class WorkDependency:
    """One Work-owned semantic dependency; it has no independent lifecycle."""

    kind: DependencyKind
    key: str
    value: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", DependencyKind(self.kind))
        if not self.key.strip() or not self.value.strip():
            raise InvalidWorkSpec("dependency key and value must be non-empty")
        if self.key.casefold() in _FORBIDDEN_BLANKET_KEYS:
            raise InvalidWorkSpec(
                f"{self.key!r} is a blanket invalidation key, not a semantic input"
            )


@dataclass(frozen=True, slots=True)
class WorkSpec:
    """The minimum declared inputs that give one computation its meaning."""

    capability: str
    producer_identity: str
    dependencies: tuple[WorkDependency, ...] = ()

    def __post_init__(self) -> None:
        if not self.capability.strip() or not self.producer_identity.strip():
            raise InvalidWorkSpec("capability and producer_identity must be non-empty")
        dependencies = tuple(sorted(self.dependencies))
        keys = [(dependency.kind, dependency.key) for dependency in dependencies]
        if len(keys) != len(set(keys)):
            raise InvalidWorkSpec("dependency kind/key pairs must be unique")
        object.__setattr__(self, "dependencies", dependencies)


@dataclass(frozen=True, slots=True)
class WorkRecord:
    work_id: str
    semantic_key: str
    spec: WorkSpec
    status: WorkStatus
    max_attempts: int
    attempt_count: int
    lease_run_id: str | None
    lease_owner: str | None
    lease_expires_at: datetime | None
    retry_not_before: datetime | None
    checkpoint: str | None
    last_failure_code: str | None
    last_failure_message: str | None
    invalidation_reason: str | None
    output: object | None
    output_digest: str | None


@dataclass(frozen=True, slots=True)
class WorkLease:
    work_id: str
    run_id: str
    owner: str
    token: str
    attempt_number: int
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class WorkAttempt:
    work_id: str
    attempt_number: int
    run_id: str
    lease_owner: str
    lease_token: str
    started_at: datetime
    lease_expires_at: datetime
    finished_at: datetime | None
    outcome: AttemptOutcome
    retryable: bool | None
    error_code: str | None
    error_message: str | None
    checkpoint: str | None


def upstream_dependency(record: WorkRecord) -> WorkDependency:
    """Bind downstream work to one immutable Work Record's eventual result."""

    return WorkDependency(
        kind=DependencyKind.UPSTREAM_WORK,
        key=record.work_id,
        value=record.semantic_key,
    )


def source_revision_dependency(
    dataset_id: str,
    relative_path: Path,
    revision: int,
) -> WorkDependency:
    """Identify one run-accounted source revision without defining public identity."""

    if not dataset_id.strip() or revision < 1:
        raise InvalidWorkSpec("source Dataset and revision must be valid")
    path = Path(relative_path)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise InvalidWorkSpec("source dependency path must stay relative to its root")
    return WorkDependency(
        kind=DependencyKind.SOURCE_REVISION,
        key=json.dumps([dataset_id, path.as_posix()], ensure_ascii=False),
        value=str(revision),
    )
