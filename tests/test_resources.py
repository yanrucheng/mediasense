from __future__ import annotations

from pathlib import Path
from threading import Lock
import time

from PIL import Image

from mediasense.precheck import AccountingStore, ImageRenditionProducer, WorkStatus
from mediasense.precheck.resources import (
    BoundedWorkExecutor,
    ResourceBudget,
    ResourceClaim,
    ResourceLimitExceeded,
    ScheduledCall,
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


def test_resource_admission_limits_decoder_use_and_localizes_failures() -> None:
    lock = Lock()
    active_decoders = 0
    peak_decoders = 0

    def run(value: int) -> int:
        nonlocal active_decoders, peak_decoders
        with lock:
            active_decoders += 1
            peak_decoders = max(peak_decoders, active_decoders)
        try:
            time.sleep(0.005)
            if value == 2:
                raise ValueError("bad media")
            return value * 10
        finally:
            with lock:
                active_decoders -= 1

    executor = BoundedWorkExecutor(
        ResourceBudget(
            capacity=ResourceClaim(cpu_slots=2, decoder_slots=1),
            max_workers=2,
            max_pending=3,
        )
    )
    outcomes = executor.run(
        ScheduledCall(
            key=str(value),
            claim=ResourceClaim(cpu_slots=1, decoder_slots=1),
            function=lambda value=value: run(value),
        )
        for value in range(5)
    )

    by_key = {outcome.key: outcome for outcome in outcomes}
    assert set(by_key) == {"0", "1", "2", "3", "4"}
    assert {outcome.value for outcome in outcomes if outcome.succeeded} == {
        0,
        10,
        30,
        40,
    }
    assert isinstance(by_key["2"].error, ValueError)
    assert peak_decoders == 1
    assert executor.admission.usage() == ResourceClaim()
    assert executor.admission.peak_usage().decoder_slots == 1


def test_zero_network_budget_rejects_network_work_without_blocking_local_work() -> None:
    executor = BoundedWorkExecutor(
        ResourceBudget(
            capacity=ResourceClaim(cpu_slots=1, network_slots=0),
            max_workers=1,
            max_pending=1,
        )
    )
    outcomes = executor.run(
        (
            ScheduledCall(
                key="network",
                claim=ResourceClaim(cpu_slots=1, network_slots=1),
                function=lambda: "must not run",
            ),
            ScheduledCall(
                key="local",
                claim=ResourceClaim(cpu_slots=1),
                function=lambda: "ok",
            ),
        )
    )

    by_key = {outcome.key: outcome for outcome in outcomes}
    assert isinstance(by_key["network"].error, ResourceLimitExceeded)
    assert by_key["local"].value == "ok"


def test_bounded_executor_runs_real_rendition_work_without_source_changes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    for index in range(20):
        Image.new("RGB", (80, 40), (index, 40, 80)).save(
            source / f"image-{index:02d}.jpg"
        )
    source_before = {path.name: path.read_bytes() for path in source.iterdir()}
    run_id = _closed_run(database, source)
    producer = ImageRenditionProducer(database)
    executor = BoundedWorkExecutor(
        ResourceBudget(
            capacity=ResourceClaim(
                cpu_slots=2,
                source_io_slots=2,
                workspace_io_slots=2,
            ),
            max_workers=2,
            max_pending=4,
        )
    )

    outcomes = executor.run(
        ScheduledCall(
            key=f"image-{index:02d}.jpg",
            claim=ResourceClaim(
                cpu_slots=1,
                source_io_slots=1,
                workspace_io_slots=1,
            ),
            function=lambda index=index: producer.produce(
                run_id, Path(f"image-{index:02d}.jpg")
            ),
        )
        for index in range(20)
    )

    assert all(outcome.succeeded for outcome in outcomes)
    assert all(
        outcome.value is not None
        and outcome.value.work.status is WorkStatus.SUCCEEDED
        and outcome.value.artifact is not None
        for outcome in outcomes
    )
    assert executor.admission.peak_usage().cpu_slots <= 2
    assert {path.name: path.read_bytes() for path in source.iterdir()} == source_before
