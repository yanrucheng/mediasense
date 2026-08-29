"""Scheduling regressions characterized from AI Album c90."""

from __future__ import annotations

from threading import Lock
import time

import pytest

from mediasense.precheck.resources import (
    BoundedWorkExecutor,
    ResourceBudget,
    ResourceClaim,
    ScheduledCall,
)


pytestmark = pytest.mark.characterization


def test_pending_window_prevents_legacy_style_full_task_materialization() -> None:
    lock = Lock()
    yielded = 0
    completed = 0
    peak_unfinished = 0

    def execute(value: int) -> int:
        nonlocal completed
        time.sleep(0.002)
        with lock:
            completed += 1
        return value

    def calls():
        nonlocal yielded, peak_unfinished
        for value in range(100):
            with lock:
                yielded += 1
                peak_unfinished = max(peak_unfinished, yielded - completed)
            yield ScheduledCall(
                key=str(value),
                claim=ResourceClaim(cpu_slots=1),
                function=lambda value=value: execute(value),
            )

    outcomes = BoundedWorkExecutor(
        ResourceBudget(
            capacity=ResourceClaim(cpu_slots=2),
            max_workers=2,
            max_pending=4,
        )
    ).run(calls())

    assert len(outcomes) == 100
    assert peak_unfinished <= 4
