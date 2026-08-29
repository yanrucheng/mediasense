"""Private dependency invalidation shared by accounting and Work stores."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import sqlite3

from ._work_types import AttemptOutcome, DependencyKind, WorkStatus


def invalidate_work_tree(
    connection: sqlite3.Connection,
    roots: dict[str, str],
    *,
    observed_at: str | None = None,
) -> tuple[str, ...]:
    """Invalidate roots and transitive dependents without deleting history."""

    timestamp = observed_at or datetime.now(timezone.utc).isoformat(
        timespec="microseconds"
    )
    queue = deque(roots.items())
    seen: set[str] = set()
    invalidated: list[str] = []
    while queue:
        work_id, reason = queue.popleft()
        if work_id in seen:
            continue
        seen.add(work_id)
        row = connection.execute(
            "SELECT * FROM work_records WHERE work_id = ?", (work_id,)
        ).fetchone()
        if row is None or WorkStatus(row["status"]) is WorkStatus.INVALIDATED:
            continue
        if WorkStatus(row["status"]) is WorkStatus.RUNNING:
            connection.execute(
                """
                UPDATE work_attempts
                SET finished_at = ?, outcome = ?, retryable = 0,
                    error_code = ?, error_message = ?
                WHERE work_id = ? AND attempt_number = ?
                """,
                (
                    timestamp,
                    AttemptOutcome.INVALIDATED,
                    "work_invalidated",
                    reason,
                    work_id,
                    row["attempt_count"],
                ),
            )
        connection.execute(
            """
            UPDATE work_records
            SET status = ?, lease_run_id = NULL, lease_owner = NULL,
                lease_token = NULL, lease_expires_at = NULL,
                retry_not_before = NULL, invalidation_reason = ?,
                updated_at = ?
            WHERE work_id = ?
            """,
            (WorkStatus.INVALIDATED, reason, timestamp, work_id),
        )
        invalidated.append(work_id)
        rows = connection.execute(
            """
            SELECT work_id FROM work_dependencies
            WHERE dependency_kind = ? AND dependency_key = ?
            ORDER BY work_id
            """,
            (DependencyKind.UPSTREAM_WORK, work_id),
        ).fetchall()
        queue.extend(
            (str(dependent["work_id"]), f"upstream_invalidated:{work_id}")
            for dependent in rows
        )
    return tuple(invalidated)


def invalidate_source_dependencies(
    connection: sqlite3.Connection,
    dataset_id: str,
    relative_paths: set[str] | None,
    *,
    reason: str,
    observed_at: str | None = None,
) -> tuple[str, ...]:
    """Invalidate Work that directly names affected sources, then its dependents."""

    rows = connection.execute(
        """
        SELECT DISTINCT work_id, dependency_key
        FROM work_dependencies
        WHERE dependency_kind IN (?, ?)
        ORDER BY work_id
        """,
        (DependencyKind.SOURCE_REVISION, DependencyKind.SOURCE_CONTENT),
    ).fetchall()
    roots: dict[str, str] = {}
    for row in rows:
        try:
            source_dataset, relative_path = json.loads(row["dependency_key"])
        except (TypeError, ValueError):
            continue
        if source_dataset != dataset_id:
            continue
        if relative_paths is not None and relative_path not in relative_paths:
            continue
        roots[str(row["work_id"])] = f"{reason}:{relative_path}"
    return invalidate_work_tree(connection, roots, observed_at=observed_at)
