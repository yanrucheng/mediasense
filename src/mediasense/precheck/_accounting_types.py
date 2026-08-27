"""Private value types shared by Slice 1 accounting modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from .discovery import DiscoveryIssueCode


class WorkingRunStatus(StrEnum):
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    COMPLETED_WITH_ISSUES = "completed_with_issues"
    BLOCKED = "blocked"


class ChangeKind(StrEnum):
    """Change in the current discovery view, not proof of Artifact validity."""

    NEW = "new"
    CHANGED = "changed"
    REUSED = "reused"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class WorkingRunSummary:
    run_id: str
    dataset_id: str
    status: WorkingRunStatus
    scan_generation: int
    checkpoint: str | None
    committed_batches: int
    item_count: int
    new_count: int
    changed_count: int
    reused_count: int
    error_count: int
    removed_count: int
    issue_count: int
    blocked_reason: str | None


@dataclass(frozen=True, slots=True)
class AccountedItem:
    relative_path: Path
    scope: str
    condition: str
    basis: tuple[str, ...]
    change_kind: ChangeKind
    source_revision: int | None


@dataclass(frozen=True, slots=True)
class RecordedIssue:
    relative_path: Path
    code: DiscoveryIssueCode
    message: str
    blocked: bool
    basis: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RemovedSource:
    """Run-owned evidence that a previously present path is now absent."""

    relative_path: Path
    previous_revision: int
    basis: tuple[str, ...]
