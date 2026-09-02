from __future__ import annotations

from datetime import datetime, timezone
import multiprocessing
from pathlib import Path
import platform
import resource
import sqlite3
from threading import Event

import pytest

from mediasense.precheck import AccountingStore, WorkStatus
from mediasense.precheck._orchestrator import (
    PrecheckExecutionConfig,
    PrecheckOrchestrator,
    _batched,
    _initial_evidence_media,
)
from mediasense.precheck._work_types import WorkRecord, WorkSpec
from mediasense.precheck.bundling import BundleCandidateProducer, BundleProfile
from mediasense.precheck.resources import (
    BoundedWorkExecutor,
    ResourceBudget,
    ResourceClaim,
    ScheduledCall,
)


pytestmark = pytest.mark.scale


_MILLION = 1_000_000


class _SuccessfulBundleWork:
    """Avoid measuring durable bundle output while exercising its production planner."""

    def __init__(self) -> None:
        self.count = 0

    def ensure_work(self, _run_id: str, spec: WorkSpec) -> WorkRecord:
        self.count += 1
        candidate_id = next(
            dependency.value
            for dependency in spec.dependencies
            if dependency.key == "candidate_id"
        )
        return WorkRecord(
            work_id=f"generated:{candidate_id}",
            semantic_key=f"generated-semantic:{candidate_id}",
            spec=spec,
            status=WorkStatus.SUCCEEDED,
            max_attempts=1,
            attempt_count=1,
            lease_run_id=None,
            lease_owner=None,
            lease_expires_at=None,
            retry_not_before=None,
            checkpoint=None,
            last_failure_code=None,
            last_failure_message=None,
            invalidation_reason=None,
            output={"generated": True},
            output_digest="generated",
        )


def _generated_scale_run(database: Path, source: Path, count: int) -> str:
    source.mkdir()
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-scale")
    run_id = accounting.start_or_resume_run("dataset-scale", source)
    accounting.process_run(run_id)
    now = datetime(2026, 9, 1, tzinfo=timezone.utc).isoformat()
    metadata_output = (
        '{"observations":[{"name":"capture_time","status":"available",'
        '"value":"2026-09-01T12:00:00+00:00"}]}'
    )
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA synchronous = OFF")
        connection.executescript(
            """
            CREATE TEMP TABLE generated_numbers(n INTEGER PRIMARY KEY);
            WITH digits(n) AS (
                VALUES (0),(1),(2),(3),(4),(5),(6),(7),(8),(9)
            )
            INSERT INTO generated_numbers(n)
            SELECT a.n + 10*b.n + 100*c.n + 1000*d.n + 10000*e.n + 100000*f.n
            FROM digits AS a, digits AS b, digits AS c,
                 digits AS d, digits AS e, digits AS f;
            """
        )
        path = "printf('group-%04d/item-%07d.jpg', n / 1000, n)"
        connection.execute(
            f"""
            INSERT INTO source_state(
                dataset_id, relative_path, revision, kind, scope, condition,
                basis_json, size_bytes, mtime_ns, device_id, inode, mode,
                fingerprint_algorithm, fingerprint, producer_identity,
                reuse_domain, present, last_observed_run_id
            )
            SELECT 'dataset-scale', {path}, 1, 'image', 'source_media', 'usable',
                   '[]', 1, n, 1, n + 1, 33188, 'stat-v1',
                   printf('generated-%07d', n), 'generated-scale-v1',
                   'generated-scale-v1', 1, ?
            FROM generated_numbers WHERE n < ?
            """,
            (run_id, count),
        )
        connection.execute(
            f"""
            INSERT INTO run_items(
                run_id, relative_path, normalized_path, association_key,
                source_revision, kind, scope, condition, basis_json, size_bytes,
                mtime_ns, device_id, inode, mode, fingerprint_algorithm,
                fingerprint, producer_identity, reuse_domain, change_kind,
                last_seen_generation
            )
            SELECT ?, {path}, {path}, printf('group-%04d', n / 1000),
                   1, 'image', 'source_media', 'usable', '[]', 1,
                   n, 1, n + 1, 33188, 'stat-v1', printf('generated-%07d', n),
                   'generated-scale-v1', 'generated-scale-v1', 'new', 1
            FROM generated_numbers WHERE n < ?
            """,
            (run_id, count),
        )
        connection.execute(
            """
            INSERT INTO work_records(
                work_id, semantic_key, descriptor_json, capability,
                producer_identity, status, max_attempts, attempt_count,
                output_json, output_digest, created_at, updated_at, succeeded_at
            )
            SELECT printf('metadata-%07d', n), printf('semantic-%07d', n), '{}',
                   'source-metadata', 'generated-index-metadata-v1', 'succeeded',
                   1, 1, ?, 'generated', ?, ?, ?
            FROM generated_numbers WHERE n < ?
            """,
            (metadata_output, now, now, now, count),
        )
        connection.execute(
            """
            INSERT INTO run_work_records(run_id, work_id, requested_at)
            SELECT ?, printf('metadata-%07d', n), ?
            FROM generated_numbers WHERE n < ?
            """,
            (run_id, now, count),
        )
        connection.execute(
            f"""
            INSERT INTO work_dependencies(
                work_id, dependency_kind, dependency_key, dependency_value
            )
            SELECT printf('metadata-%07d', n), 'parameter',
                   'subject_relative_path', {path}
            FROM generated_numbers WHERE n < ?
            """,
            (count,),
        )
    return run_id


def _measure_bundle_peak(database: Path, run_id: str, result_queue) -> None:
    producer = BundleCandidateProducer(database)
    work = _SuccessfulBundleWork()
    producer.work = work
    accounting = AccountingStore(database)
    selected, selected_bundles = _initial_evidence_media(
        (
            item
            for item in accounting.iter_run_items(run_id)
            if item.scope == "source_media" and item.source_revision is not None
        ),
        producer.produce(
            run_id,
            None,
            profile=BundleProfile(max_members=1_000),
        ),
        PrecheckExecutionConfig(compression_target=200),
    )
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes = peak if platform.system() == "Darwin" else peak * 1024
    result_queue.put((work.count, len(selected), len(selected_bundles), peak_bytes))


def test_four_thousand_nine_metadata_candidates_form_twenty_one_batches() -> None:
    assert [len(batch) for batch in _batched(range(4_009), 200)] == [200] * 20 + [9]


def test_million_source_items_and_index_metadata_use_bounded_bundle_memory(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    run_id = _generated_scale_run(database, tmp_path / "source", _MILLION)
    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM run_items WHERE run_id = ?", (run_id,)
        ).fetchone()[0] == _MILLION
        assert connection.execute(
            """
            SELECT COUNT(*)
            FROM run_work_records JOIN work_records USING (work_id)
            WHERE run_id = ? AND capability = 'source-metadata'
            """,
            (run_id,),
        ).fetchone()[0] == _MILLION

    context = multiprocessing.get_context("spawn")
    result_queue = context.Queue()
    worker = context.Process(
        target=_measure_bundle_peak,
        args=(database, run_id, result_queue),
    )
    worker.start()
    worker.join(timeout=180)
    assert worker.exitcode == 0
    candidate_count, selected_count, selected_bundle_count, peak = result_queue.get(
        timeout=5
    )
    print(
        "million-item production planning: "
        f"candidates={candidate_count}, selected_bundles={selected_bundle_count}, "
        f"selected_items={selected_count}, peak_rss_bytes={peak}"
    )

    assert candidate_count == 1_000
    assert selected_bundle_count == 800
    assert selected_count == 1_600
    assert peak < 256 * 1024 * 1024


def test_million_call_stream_stops_at_bounded_window_on_cancellation() -> None:
    cancel = Event()
    enumerated: list[int] = []
    executor = BoundedWorkExecutor(
        ResourceBudget(
            capacity=ResourceClaim(cpu_slots=2),
            max_workers=2,
            max_pending=4,
        )
    )

    def calls():
        for value in range(1_000_000):
            enumerated.append(value)

            def execute(value: int = value) -> int:
                if value == 0:
                    cancel.set()
                return value

            yield ScheduledCall(
                key=str(value),
                claim=ResourceClaim(cpu_slots=1),
                function=execute,
            )

    run_control = type(
        "RunningControl",
        (),
        {
            "current_state": lambda _self, _run_ref: (
                "cancelled" if cancel.is_set() else "running"
            )
        },
    )()
    orchestrator = PrecheckOrchestrator(Path("unused.sqlite3"), run_control)
    outcomes = tuple(orchestrator._execute("run", executor, calls()))

    assert 1 <= len(enumerated) <= 4
    assert 1 <= len(outcomes) <= len(enumerated)
    assert any(value == 0 for _key, value in outcomes)


def test_million_item_batching_is_lazy() -> None:
    consumed = 0

    def items():
        nonlocal consumed
        for value in range(1_000_000):
            consumed += 1
            yield value

    batches = _batched(items(), 1_000)

    assert len(next(batches)) == 1_000
    assert len(next(batches)) == 1_000
    assert consumed == 2_000
