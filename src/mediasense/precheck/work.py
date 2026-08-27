"""Stable internal entry point for reusable Work Record coordination."""

from ._work_sqlite import SQLiteWorkStore
from ._work_types import (
    AttemptOutcome,
    DependencyKind,
    InvalidWorkSpec,
    InvalidWorkTransition,
    LeaseLost,
    WorkAttempt,
    WorkDependency,
    WorkIdentityCollision,
    WorkLease,
    WorkRecord,
    WorkSpec,
    WorkStateError,
    WorkStatus,
    source_revision_dependency,
    upstream_dependency,
)


class WorkStore(SQLiteWorkStore):
    """Coordinate work without exposing the private SQLite representation."""


__all__ = [
    "AttemptOutcome",
    "DependencyKind",
    "InvalidWorkSpec",
    "InvalidWorkTransition",
    "LeaseLost",
    "WorkAttempt",
    "WorkDependency",
    "WorkIdentityCollision",
    "WorkLease",
    "WorkRecord",
    "WorkSpec",
    "WorkStateError",
    "WorkStatus",
    "WorkStore",
    "source_revision_dependency",
    "upstream_dependency",
]
