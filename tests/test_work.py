from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier

import pytest

from mediasense.precheck import (
    AccountingStore,
    AttemptOutcome,
    DependencyKind,
    InvalidWorkSpec,
    InvalidWorkTransition,
    LeaseLost,
    WorkDependency,
    WorkSpec,
    WorkStatus,
    WorkStore,
    source_revision_dependency,
    upstream_dependency,
)


NOW = datetime(2026, 8, 27, 4, 0, tzinfo=timezone.utc)


def _completed_accounting_run(
    database: Path,
    source: Path,
    *,
    dataset_id: str = "dataset-a",
) -> str:
    source.mkdir(exist_ok=True)
    media = source / "photo.JPG"
    if not media.exists():
        media.write_bytes(b"photo-v1")
    accounting = AccountingStore(database)
    accounting.register_dataset(dataset_id)
    run_id = accounting.start_or_resume_run(dataset_id, source)
    accounting.process_run(run_id)
    return run_id


def _source_spec(revision: str = "1") -> WorkSpec:
    return WorkSpec(
        capability="source-validation",
        producer_identity="builtin-source-validation-v1",
        dependencies=(
            source_revision_dependency(
                "dataset-a",
                Path("photo.JPG"),
                int(revision),
            ),
            WorkDependency(
                kind=DependencyKind.PARAMETER,
                key="validation_profile",
                value="basic-v1",
            ),
        ),
    )


def test_equivalent_semantic_work_is_shared_across_runs(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    first_run = _completed_accounting_run(database, source)
    accounting = AccountingStore(database)
    second_run = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(second_run)
    work = WorkStore(database)

    first = work.ensure_work(first_run, _source_spec())
    second = work.ensure_work(
        second_run,
        WorkSpec(
            capability="source-validation",
            producer_identity="builtin-source-validation-v1",
            dependencies=tuple(reversed(_source_spec().dependencies)),
        ),
    )

    assert first.work_id == second.work_id
    assert first.semantic_key == second.semantic_key
    assert work.list_run_work(first_run)[0].work_id == first.work_id
    assert work.list_run_work(second_run)[0].work_id == first.work_id
    with pytest.raises(InvalidWorkSpec, match="different retry policy"):
        work.ensure_work(second_run, _source_spec(), max_attempts=4)


def test_work_cannot_be_registered_before_source_accounting_closes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    work = WorkStore(database)

    with pytest.raises(InvalidWorkTransition, match="source accounting"):
        work.ensure_work(run_id, _source_spec())


def test_semantic_change_creates_distinct_work_without_global_version(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    run_id = _completed_accounting_run(database, source)
    work = WorkStore(database)

    first = work.ensure_work(run_id, _source_spec("1"))
    changed_producer = work.ensure_work(
        run_id,
        WorkSpec(
            capability="source-validation",
            producer_identity="builtin-source-validation-v2",
            dependencies=_source_spec("1").dependencies,
        ),
    )
    (source / "photo.JPG").write_bytes(b"photo-v2")
    accounting = AccountingStore(database)
    changed_run = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(changed_run)
    changed_source = work.ensure_work(changed_run, _source_spec("2"))

    assert len({first.work_id, changed_source.work_id, changed_producer.work_id}) == 3
    with pytest.raises(InvalidWorkSpec, match="not accounted"):
        work.ensure_work(run_id, _source_spec("2"))
    with pytest.raises(InvalidWorkSpec, match="blanket invalidation key"):
        WorkDependency(
            kind=DependencyKind.ENVIRONMENT,
            key="application_version",
            value="0.1.0",
        )
    with pytest.raises(InvalidWorkSpec, match="stay relative"):
        source_revision_dependency("dataset-a", Path("../photo.JPG"), 1)


def test_upstream_work_must_succeed_before_dependent_is_claimable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    run_id = _completed_accounting_run(database, tmp_path / "source")
    work = WorkStore(database)
    upstream = work.ensure_work(run_id, _source_spec())
    dependent = work.ensure_work(
        run_id,
        WorkSpec(
            capability="derived-observation",
            producer_identity="builtin-derived-observation-v1",
            dependencies=(upstream_dependency(upstream),),
        ),
    )

    assert dependent.status is WorkStatus.PENDING
    first_lease = work.claim_ready_work(
        run_id,
        "worker-a",
        lease_duration=timedelta(minutes=1),
        now=NOW,
    )[0]
    assert first_lease.work_id == upstream.work_id
    assert (
        work.claim_ready_work(
            run_id,
            "worker-b",
            lease_duration=timedelta(minutes=1),
            now=NOW,
        )
        == ()
    )

    work.succeed_work(first_lease, {"valid": True}, now=NOW)
    assert work.get_work(dependent.work_id).status is WorkStatus.READY
    assert work.get_run_work_counts(run_id) == {
        WorkStatus.READY: 1,
        WorkStatus.SUCCEEDED: 1,
    }
    second_lease = work.claim_ready_work(
        run_id,
        "worker-b",
        lease_duration=timedelta(minutes=1),
        now=NOW,
    )[0]
    assert second_lease.work_id == dependent.work_id


def test_equivalent_work_is_claimed_once_across_concurrent_runs(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    first_run = _completed_accounting_run(database, source)
    accounting = AccountingStore(database)
    second_run = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(second_run)
    work = WorkStore(database)
    expected = work.ensure_work(first_run, _source_spec())
    assert work.ensure_work(second_run, _source_spec()).work_id == expected.work_id
    barrier = Barrier(2)

    def claim(run_id: str, owner: str):
        barrier.wait()
        return WorkStore(database).claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=1),
            now=NOW,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(claim, first_run, "worker-a")
        second = executor.submit(claim, second_run, "worker-b")
        claims = (*first.result(), *second.result())

    assert len(claims) == 1
    assert claims[0].work_id == expected.work_id
    assert work.get_work(expected.work_id).status is WorkStatus.RUNNING
    work.succeed_work(claims[0], {"valid": True}, now=NOW + timedelta(seconds=1))
    assert (
        WorkStore(database)
        .ensure_work(
            second_run,
            _source_spec(),
        )
        .status
        is WorkStatus.SUCCEEDED
    )


def test_expired_lease_is_recovered_after_restart_and_stale_token_is_refused(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    run_id = _completed_accounting_run(database, tmp_path / "source")
    work = WorkStore(database)
    record = work.ensure_work(run_id, _source_spec(), max_attempts=2, now=NOW)
    first = work.claim_ready_work(
        run_id,
        "worker-a",
        lease_duration=timedelta(seconds=10),
        now=NOW,
    )[0]
    work.save_checkpoint(first, "item=17", now=NOW + timedelta(seconds=1))

    reopened = WorkStore(database)
    second = reopened.claim_ready_work(
        run_id,
        "worker-b",
        lease_duration=timedelta(seconds=10),
        now=NOW + timedelta(seconds=11),
    )[0]

    assert second.work_id == record.work_id
    assert second.attempt_number == 2
    assert reopened.get_work(record.work_id).checkpoint == "item=17"
    attempts = reopened.get_attempts(record.work_id)
    assert attempts[0].outcome is AttemptOutcome.LEASE_EXPIRED
    assert attempts[0].checkpoint == "item=17"
    assert attempts[1].outcome is AttemptOutcome.RUNNING
    with pytest.raises(LeaseLost):
        reopened.succeed_work(first, {"stale": True}, now=NOW + timedelta(seconds=12))
    succeeded = reopened.succeed_work(
        second,
        {"resumed_from": "item=17"},
        now=NOW + timedelta(seconds=12),
    )
    assert succeeded.status is WorkStatus.SUCCEEDED
    assert succeeded.output == {"resumed_from": "item=17"}
    assert succeeded.output_digest is not None


def test_renewed_lease_is_not_reclaimed_at_the_original_expiry(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    run_id = _completed_accounting_run(database, tmp_path / "source")
    work = WorkStore(database)
    work.ensure_work(run_id, _source_spec(), max_attempts=2, now=NOW)
    original = work.claim_ready_work(
        run_id,
        "worker-a",
        lease_duration=timedelta(seconds=10),
        now=NOW,
    )[0]
    renewed = work.renew_lease(
        original,
        lease_duration=timedelta(seconds=10),
        now=NOW + timedelta(seconds=5),
    )

    assert renewed.expires_at == NOW + timedelta(seconds=15)
    assert work.recover_expired_leases(now=NOW + timedelta(seconds=11)) == ()
    assert work.recover_expired_leases(now=NOW + timedelta(seconds=16)) == (
        original.work_id,
    )


def test_success_rejects_non_json_or_oversized_inline_output(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    run_id = _completed_accounting_run(database, tmp_path / "source")
    work = WorkStore(database)
    record = work.ensure_work(run_id, _source_spec(), now=NOW)
    lease = work.claim_ready_work(
        run_id,
        "worker-a",
        lease_duration=timedelta(minutes=1),
        now=NOW,
    )[0]

    with pytest.raises(ValueError, match="valid JSON"):
        work.succeed_work(lease, {"not-json"}, now=NOW)
    with pytest.raises(ValueError, match="64 KiB"):
        work.succeed_work(lease, {"payload": "x" * 70_000}, now=NOW)

    assert work.get_work(record.work_id).status is WorkStatus.RUNNING
    assert work.get_attempts(record.work_id)[0].outcome is AttemptOutcome.RUNNING


def test_retry_backoff_and_attempt_limit_are_durable(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    run_id = _completed_accounting_run(database, tmp_path / "source")
    work = WorkStore(database)
    record = work.ensure_work(run_id, _source_spec(), max_attempts=2, now=NOW)
    dependent = work.ensure_work(
        run_id,
        WorkSpec(
            capability="derived-observation",
            producer_identity="builtin-derived-observation-v1",
            dependencies=(upstream_dependency(record),),
        ),
    )
    first = work.claim_ready_work(
        run_id,
        "worker-a",
        lease_duration=timedelta(minutes=1),
        now=NOW,
    )[0]
    failed = work.fail_work(
        first,
        error_code="temporary_io",
        message="device busy",
        retryable=True,
        retry_delay=timedelta(seconds=30),
        now=NOW + timedelta(seconds=1),
    )

    assert failed.status is WorkStatus.RETRYABLE_FAILURE
    assert (
        work.claim_ready_work(
            run_id,
            "worker-b",
            lease_duration=timedelta(minutes=1),
            now=NOW + timedelta(seconds=29),
        )
        == ()
    )
    second = work.claim_ready_work(
        run_id,
        "worker-b",
        lease_duration=timedelta(minutes=1),
        now=NOW + timedelta(seconds=31),
    )[0]
    terminal = work.fail_work(
        second,
        error_code="temporary_io",
        message="still busy",
        retryable=True,
        now=NOW + timedelta(seconds=32),
    )

    assert terminal.status is WorkStatus.TERMINAL_FAILURE
    assert work.get_work(dependent.work_id).status is WorkStatus.BLOCKED
    assert (
        work.claim_ready_work(
            run_id,
            "worker-c",
            lease_duration=timedelta(minutes=1),
            now=NOW + timedelta(minutes=2),
        )
        == ()
    )
    assert [attempt.outcome for attempt in work.get_attempts(record.work_id)] == [
        AttemptOutcome.RETRYABLE_FAILURE,
        AttemptOutcome.TERMINAL_FAILURE,
    ]


def test_invalidation_retains_history_and_invalidates_dependents(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    run_id = _completed_accounting_run(database, tmp_path / "source")
    work = WorkStore(database)
    upstream = work.ensure_work(run_id, _source_spec())
    lease = work.claim_ready_work(
        run_id,
        "worker-a",
        lease_duration=timedelta(minutes=1),
        now=NOW,
    )[0]
    upstream = work.succeed_work(
        lease,
        {"valid": True},
        now=NOW + timedelta(seconds=1),
    )
    dependent = work.ensure_work(
        run_id,
        WorkSpec(
            capability="derived-observation",
            producer_identity="builtin-derived-observation-v1",
            dependencies=(upstream_dependency(upstream),),
        ),
    )

    invalidated = work.invalidate_work(
        upstream.work_id,
        "source revision changed",
        now=NOW + timedelta(seconds=2),
    )
    replacement = work.ensure_work(
        run_id,
        _source_spec(),
        now=NOW + timedelta(seconds=3),
    )

    assert invalidated == (upstream.work_id, dependent.work_id)
    assert work.get_work(upstream.work_id).status is WorkStatus.INVALIDATED
    assert work.get_work(dependent.work_id).status is WorkStatus.INVALIDATED
    assert replacement.work_id != upstream.work_id
    assert len(work.get_attempts(upstream.work_id)) == 1
