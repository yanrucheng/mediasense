from __future__ import annotations

from pathlib import Path
import platform
import plistlib
import subprocess
from threading import Lock
import time

from PIL import Image
import pytest

from mediasense.precheck import AccountingStore, ImageRenditionProducer, WorkStatus
from mediasense.precheck._orchestrator import PrecheckExecutionConfig
from mediasense.precheck.resources import (
    BoundedWorkExecutor,
    ResourceBudget,
    ResourceClaim,
    ResourceLimitExceeded,
    ScheduledCall,
    _available_memory_bytes,
    detect_source_storage,
    resolve_resource_budget,
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


def test_resource_resolution_uses_host_facts_and_storage_conservatism() -> None:
    local = resolve_resource_budget(
        source_storage="local",
        logical_cpu_count=8,
        available_memory_bytes=4 * 1024 * 1024 * 1024,
    )
    unknown = resolve_resource_budget(
        source_storage="unknown",
        logical_cpu_count=8,
        available_memory_bytes=4 * 1024 * 1024 * 1024,
    )

    assert local.capacity.source_io_slots > 1
    assert local.capacity.process_slots > 1
    assert local.max_workers > 2
    assert unknown.capacity.source_io_slots == 1
    assert unknown.capacity.process_slots == 1
    assert unknown.capacity.network_slots == 0


def test_darwin_memory_uses_supported_vm_stat_fields() -> None:
    output = b"""Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free:                               100.\nPages active:                             999.\nPages inactive:                           200.\nPages speculative:                         25.\nPages purgeable:                           80.\n"""

    available = _available_memory_bytes(
        system="Darwin",
        command_runner=lambda _command: subprocess.CompletedProcess(
            _command, 0, output, b""
        ),
    )

    assert available == (100 + 200 + 25) * 16_384


def test_darwin_storage_requires_physical_solid_state_evidence(
    tmp_path: Path,
) -> None:
    def probe(details: dict[str, object]):
        return lambda command: subprocess.CompletedProcess(
            command, 0, plistlib.dumps(details), b""
        )

    assert detect_source_storage(
        tmp_path,
        system="Darwin",
        command_runner=probe(
            {
                "FilesystemType": "apfs",
                "SolidState": True,
                "VirtualOrPhysical": "Physical",
            }
        ),
    ) == ("local", "darwin_diskutil_physical_solid_state")
    assert detect_source_storage(
        tmp_path,
        system="Darwin",
        command_runner=probe({"FilesystemType": "apfs", "SolidState": False}),
    ) == ("unknown", "darwin_diskutil_non_solid_state")


@pytest.mark.skipif(platform.system() != "Darwin", reason="Darwin-only host probe")
def test_current_darwin_resource_probes_return_supported_observations(
    tmp_path: Path,
) -> None:
    assert _available_memory_bytes() is not None
    storage, evidence = detect_source_storage(tmp_path)
    assert storage in {"local", "remote", "unknown"}
    assert evidence.startswith("darwin_diskutil_")


def test_unverified_local_override_cannot_widen_storage_lanes() -> None:
    resolved = PrecheckExecutionConfig(source_storage_hint="local").resolve_resources(
        source_storage="unknown",
        source_storage_evidence="test_no_physical_storage_evidence",
        logical_cpu_count=8,
        available_memory_bytes=4 * 1024 * 1024 * 1024,
    )

    assert resolved.source_storage_hint == "unknown"
    assert resolved.source_storage_evidence.startswith("operator_local_not_verified:")
    assert resolved.resource_budget is not None
    assert resolved.resource_budget.capacity.source_io_slots == 1


def test_operator_resource_budget_only_caps_detected_capacity() -> None:
    ceiling = ResourceBudget(
        capacity=ResourceClaim(
            source_io_slots=2,
            workspace_io_slots=2,
            cpu_slots=3,
            process_slots=2,
            memory_bytes=768 * 1024 * 1024,
            temporary_bytes=512 * 1024 * 1024,
            model_slots=1,
            exiftool_slots=1,
            decoder_slots=2,
            encoder_slots=2,
            network_slots=0,
        ),
        max_workers=3,
        max_pending=4,
    )

    resolved = resolve_resource_budget(
        source_storage="local",
        logical_cpu_count=16,
        available_memory_bytes=16 * 1024 * 1024 * 1024,
        ceiling=ceiling,
    )

    assert resolved == ceiling


def test_effective_resource_configuration_round_trips_for_resume() -> None:
    resolved = PrecheckExecutionConfig(
        directed_evidence_paths=(Path("later.jpg"),),
    ).resolve_resources(
        source_storage="unknown",
        source_storage_evidence="test_unknown_storage",
        logical_cpu_count=12,
        available_memory_bytes=8 * 1024 * 1024 * 1024,
    )

    assert resolved.source_storage_hint == "unknown"
    assert resolved.resource_budget is not None
    assert resolved.resource_budget.capacity.source_io_slots == 1
    assert resolved.ffmpeg_threads == 2
    restored = PrecheckExecutionConfig.from_value(resolved.value())
    assert restored == resolved
    assert (
        restored.resolve_resources(
            source_storage="local",
            source_storage_evidence="ignored_after_resolution",
            logical_cpu_count=2,
            available_memory_bytes=256 * 1024 * 1024,
        )
        == resolved
    )
    obsolete = dict(resolved.value())
    obsolete["version"] = 2
    with pytest.raises(ValueError, match="unsupported PreCheck execution configuration"):
        PrecheckExecutionConfig.from_value(obsolete)


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


def test_executor_materializes_only_the_pending_window() -> None:
    enumerated: list[int] = []
    executor = BoundedWorkExecutor(
        ResourceBudget(
            capacity=ResourceClaim(cpu_slots=2),
            max_workers=2,
            max_pending=3,
        )
    )

    def calls():
        for value in range(100):
            enumerated.append(value)
            yield ScheduledCall(
                key=str(value),
                claim=ResourceClaim(cpu_slots=1),
                function=lambda value=value: value,
            )

    outcomes = executor.iter_run(calls())
    first = next(outcomes)

    assert first.succeeded
    assert len(enumerated) == 3
    assert len(tuple(outcomes)) == 99


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
