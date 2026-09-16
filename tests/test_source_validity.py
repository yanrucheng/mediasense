from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path

import pytest

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


def test_bounded_fingerprint_accepts_same_stat_unsampled_change(
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
    assert second_proof.dependency() == first_proof.dependency()
    assert work.get_work(first.work_id).status is WorkStatus.SUCCEEDED
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
    assert replacement.work_id == first.work_id


def test_source_validity_observation_does_not_reread_full_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "large.jpg"
    media.write_bytes(b"a" * 200_000)
    run_id = _completed_run(database, source)
    real_open = Path.open

    def reject_source_read(path: Path, *args, **kwargs):
        if path == media:
            raise AssertionError("PreCheck validity must reuse the bounded fingerprint")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", reject_source_read)

    proof = SourceValidityStore(database).prove(run_id, Path("large.jpg"))

    assert proof.algorithm == "candidate-sha256-full-or-3x4k-v1"


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


def test_batch_proofs_keep_occurrences_and_roll_back_unknown_failure(tmp_path, monkeypatch):
    import sqlite3
    database, source = tmp_path / "work.sqlite3", tmp_path / "source"
    source.mkdir()
    for name in ("a.jpg", "b.jpg"):
        (source / name).write_bytes(b"same bytes")
    run_id = _completed_run(database, source)
    validity = SourceValidityStore(database)
    assert validity.prove_many(run_id, ()) == ()
    first = validity.prove(run_id, Path("a.jpg"))
    original = validity._record_proof
    def fail_second(connection, proof):
        original(connection, proof)
        if proof.relative_path == Path("b.jpg"):
            raise RuntimeError("injected batch failure")
    monkeypatch.setattr(validity, "_record_proof", fail_second)
    with pytest.raises(RuntimeError, match="injected"):
        validity.prove_many(run_id, (Path("a.jpg"), Path("b.jpg")))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT relative_path, observed_at FROM source_content_proofs").fetchall() == [
            ("a.jpg", first.observed_at.isoformat(timespec="microseconds"))]
    monkeypatch.setattr(validity, "_record_proof", original)
    proofs = validity.prove_many(run_id, (Path("b.jpg"), Path("a.jpg"), Path("b.jpg")))
    assert [p.relative_path.name for p in proofs] == ["b.jpg", "a.jpg", "b.jpg"]
    assert proofs[0].dependency().key != proofs[1].dependency().key
    with pytest.raises(KeyError):
        validity.prove_many(run_id, (Path("absent.jpg"),))


@pytest.mark.parametrize("mutation", ["file", "revision", "run_state"])
def test_batch_proof_commit_rechecks_observed_source(tmp_path, monkeypatch, mutation):
    from contextlib import contextmanager
    import sqlite3
    from mediasense.precheck._fingerprint import SourceChangedDuringRead
    database, source = tmp_path / "work.sqlite3", tmp_path / "source"
    source.mkdir()
    (source / "a.jpg").write_bytes(b"first")
    run_id = _completed_run(database, source)
    validity = SourceValidityStore(database)
    original = validity._transaction
    @contextmanager
    def raced():
        if mutation == "file":
            (source / "a.jpg").write_bytes(b"changed")
        else:
            with sqlite3.connect(database) as connection:
                if mutation == "revision":
                    connection.execute("UPDATE run_items SET source_revision = source_revision + 1 WHERE run_id = ?", (run_id,))
                else:
                    connection.execute("UPDATE working_runs SET status = 'paused' WHERE run_id = ?", (run_id,))
        with original() as connection:
            yield connection
    monkeypatch.setattr(validity, "_transaction", raced)
    with pytest.raises(SourceChangedDuringRead):
        validity.prove_many(run_id, (Path("a.jpg"),))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM source_content_proofs").fetchone()[0] == 0


def test_process_exit_rolls_back_open_proof_batch_and_keeps_prior_commit(tmp_path):
    import mediasense
    import subprocess
    import sys
    import sqlite3
    database, source = tmp_path / "work.sqlite3", tmp_path / "source"
    source.mkdir()
    for name in ("a.jpg", "b.jpg"):
        (source / name).write_bytes(b"source")
    run_id = _completed_run(database, source)
    first = SourceValidityStore(database).prove(run_id, Path("a.jpg"))
    script = """
import os, sys
from pathlib import Path
from mediasense.precheck import SourceValidityStore
store = SourceValidityStore(Path(sys.argv[1]))
original = store._record_proof
def terminate(connection, proof):
    original(connection, proof)
    os._exit(23)
store._record_proof = terminate
store.prove_many(sys.argv[2], (Path('a.jpg'), Path('b.jpg')))
"""
    env = dict(os.environ)
    # The child must exercise the same source/installed package as its parent,
    # including when release checks explicitly disable pytest's src injection.
    env["PYTHONPATH"] = str(Path(mediasense.__file__).resolve().parents[1])
    completed = subprocess.run([sys.executable, "-c", script, str(database), run_id], env=env, capture_output=True, timeout=15)
    assert completed.returncode == 23, completed.stderr.decode()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT relative_path, observed_at FROM source_content_proofs").fetchall() == [
            ("a.jpg", first.observed_at.isoformat(timespec="microseconds"))]
