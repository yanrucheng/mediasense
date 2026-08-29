from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path

from mediasense.precheck import (
    AccountingStore,
    ChangeKind,
    SourceValidityStore,
    WorkSpec,
    WorkStatus,
    WorkStore,
    source_revision_dependency,
    upstream_dependency,
)


def _completed_run(database: Path, source: Path, dataset_id: str = "dataset-a") -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset(dataset_id)
    run_id = accounting.start_or_resume_run(dataset_id, source)
    accounting.process_run(run_id)
    return run_id


def _source_spec(path: str, revision: int = 1) -> WorkSpec:
    return WorkSpec(
        capability="source-probe",
        producer_identity="test-source-probe-v1",
        dependencies=(source_revision_dependency("dataset-a", Path(path), revision),),
    )


def _succeed(work: WorkStore, run_id: str, work_id: str) -> None:
    while True:
        leases = work.claim_ready_work(
            run_id,
            "test-worker",
            lease_duration=timedelta(minutes=1),
        )
        if not leases:
            raise AssertionError(f"Work Record was not claimable: {work_id}")
        lease = leases[0]
        work.succeed_work(lease, {"ok": True})
        if lease.work_id == work_id:
            return


def test_accounting_change_invalidates_only_direct_and_transitive_work(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "changed.jpg").write_bytes(b"before")
    (source / "stable.jpg").write_bytes(b"stable")
    first_run = _completed_run(database, source)
    work = WorkStore(database)
    changed = work.ensure_work(first_run, _source_spec("changed.jpg"))
    stable = work.ensure_work(first_run, _source_spec("stable.jpg"))
    _succeed(work, first_run, changed.work_id)
    _succeed(work, first_run, stable.work_id)
    changed = work.get_work(changed.work_id)
    dependent = work.ensure_work(
        first_run,
        WorkSpec(
            capability="dependent",
            producer_identity="test-dependent-v1",
            dependencies=(upstream_dependency(changed),),
        ),
    )

    (source / "changed.jpg").write_bytes(b"after")
    second_run = _completed_run(database, source)
    items = {
        item.relative_path.as_posix(): item
        for item in AccountingStore(database).get_run_items(second_run)
    }

    assert items["changed.jpg"].change_kind is ChangeKind.CHANGED
    assert work.get_work(changed.work_id).status is WorkStatus.INVALIDATED
    assert work.get_work(dependent.work_id).status is WorkStatus.INVALIDATED
    assert work.get_work(stable.work_id).status is WorkStatus.SUCCEEDED


def test_removal_and_unavailable_root_invalidate_affected_source_work(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "removed.jpg").write_bytes(b"removed")
    (source / "remaining.jpg").write_bytes(b"remaining")
    first_run = _completed_run(database, source)
    work = WorkStore(database)
    removed = work.ensure_work(first_run, _source_spec("removed.jpg"))
    remaining = work.ensure_work(first_run, _source_spec("remaining.jpg"))
    _succeed(work, first_run, removed.work_id)
    _succeed(work, first_run, remaining.work_id)

    (source / "removed.jpg").unlink()
    second_run = _completed_run(database, source)
    assert AccountingStore(database).get_run_removals(second_run)[
        0
    ].relative_path == Path("removed.jpg")
    assert work.get_work(removed.work_id).status is WorkStatus.INVALIDATED
    assert work.get_work(remaining.work_id).status is WorkStatus.SUCCEEDED

    source.rename(tmp_path / "source-offline")
    third_run = AccountingStore(database).start_or_resume_run("dataset-a", source)
    AccountingStore(database).process_run(third_run)
    assert work.get_work(remaining.work_id).status is WorkStatus.INVALIDATED


def test_exact_source_proof_prevents_sampled_fingerprint_false_reuse(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "large.jpg"
    media.write_bytes(b"a" * 200_000)
    first_run = _completed_run(database, source)
    accounted = AccountingStore(database).get_run_items(first_run)[0]
    proof_store = SourceValidityStore(database)
    first_proof = proof_store.prove(first_run, Path("large.jpg"))
    work = WorkStore(database)
    first = work.ensure_work(
        first_run,
        WorkSpec(
            capability="artifact-input",
            producer_identity="test-artifact-input-v1",
            dependencies=(
                source_revision_dependency(
                    "dataset-a", Path("large.jpg"), accounted.source_revision or 0
                ),
                first_proof.dependency(),
            ),
        ),
    )
    _succeed(work, first_run, first.work_id)

    original_stat = media.stat()
    with media.open("r+b") as stream:
        stream.seek(30_000)
        stream.write(b"changed-but-unsampled")
    os.utime(media, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    second_run = _completed_run(database, source)
    second_item = AccountingStore(database).get_run_items(second_run)[0]
    assert second_item.change_kind is ChangeKind.REUSED
    assert second_item.source_revision == accounted.source_revision

    second_proof = proof_store.prove(second_run, Path("large.jpg"))
    assert second_proof.digest != first_proof.digest
    assert work.get_work(first.work_id).status is WorkStatus.INVALIDATED
    replacement = work.ensure_work(
        second_run,
        WorkSpec(
            capability="artifact-input",
            producer_identity="test-artifact-input-v1",
            dependencies=(
                source_revision_dependency(
                    "dataset-a", Path("large.jpg"), second_item.source_revision or 0
                ),
                second_proof.dependency(),
            ),
        ),
    )
    assert replacement.work_id != first.work_id


def test_exact_source_proof_and_work_are_reused_across_unchanged_runs(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"same bytes")
    first_run = _completed_run(database, source)
    validity = SourceValidityStore(database)
    first_proof = validity.prove(first_run, Path("photo.jpg"))
    first_item = AccountingStore(database).get_run_items(first_run)[0]
    spec = WorkSpec(
        capability="artifact-input",
        producer_identity="test-artifact-input-v1",
        dependencies=(
            source_revision_dependency(
                "dataset-a", Path("photo.jpg"), first_item.source_revision or 0
            ),
            first_proof.dependency(),
        ),
    )
    work = WorkStore(database)
    first = work.ensure_work(first_run, spec)
    _succeed(work, first_run, first.work_id)

    second_run = _completed_run(database, source)
    second_proof = validity.prove(second_run, Path("photo.jpg"))
    assert second_proof.dependency() == first_proof.dependency()
    assert work.ensure_work(second_run, spec).work_id == first.work_id


def test_new_source_does_not_invalidate_unrelated_existing_work(tmp_path: Path) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "existing.jpg").write_bytes(b"existing")
    first_run = _completed_run(database, source)
    work = WorkStore(database)
    existing = work.ensure_work(first_run, _source_spec("existing.jpg"))
    _succeed(work, first_run, existing.work_id)

    (source / "added.jpg").write_bytes(b"added")
    second_run = _completed_run(database, source)
    items = {
        item.relative_path.as_posix(): item
        for item in AccountingStore(database).get_run_items(second_run)
    }

    assert items["added.jpg"].change_kind is ChangeKind.NEW
    assert work.get_work(existing.work_id).status is WorkStatus.SUCCEEDED
