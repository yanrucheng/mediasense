from __future__ import annotations

import os
import sqlite3
import socket
from pathlib import Path
from types import SimpleNamespace

import pytest

from mediasense.precheck import accounting
from mediasense.precheck import discovery
from mediasense.precheck import _fingerprint
from mediasense.precheck.accounting import (
    AccountingStore,
    ChangeKind,
    SourceAttachmentError,
    SourceRebindRequired,
    WorkingRunStatus,
)
from mediasense.precheck.source_attachment import UnsafeWorkspace
from mediasense.precheck import source_attachment


def _complete_run(
    store: AccountingStore,
    dataset_id: str,
    root: Path,
):
    store.register_dataset(dataset_id)
    run_id = store.start_or_resume_run(dataset_id, root)
    return store.process_run(run_id, batch_size=2)


@pytest.mark.parametrize("old_version", [11, 12, 13, 14])
def test_supported_schema_is_upgraded_without_discarding_existing_state(
    tmp_path: Path,
    old_version: int,
) -> None:
    database = tmp_path / "working.sqlite3"
    store = AccountingStore(database)
    store.register_dataset("dataset-a")
    with sqlite3.connect(database) as connection:
        connection.execute("DROP INDEX run_items_normalized_path")
        connection.execute("ALTER TABLE run_items DROP COLUMN normalized_path")
        connection.execute(
            "ALTER TABLE precheck_runs DROP COLUMN execution_config_json"
        )
        connection.execute("ALTER TABLE precheck_runs DROP COLUMN execution_checkpoint")
        connection.execute("DROP TABLE result_work_records")
        if old_version == 11:
            connection.execute("DROP TABLE precheck_runs")
        connection.execute(
            "UPDATE internal_schema SET version = ? WHERE singleton = 1",
            (old_version,),
        )

    AccountingStore(database).register_dataset("dataset-b")

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM internal_schema WHERE singleton = 1"
        ).fetchone()[0]
        datasets = {
            row[0] for row in connection.execute("SELECT dataset_id FROM datasets")
        }
        run_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'precheck_runs'"
        ).fetchone()
        result_work_table = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name = 'result_work_records'"
        ).fetchone()
    assert version == 15
    assert datasets == {"dataset-a", "dataset-b"}
    assert run_table == ("precheck_runs",)
    assert result_work_table == ("result_work_records",)
    with sqlite3.connect(database) as connection:
        run_item_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(run_items)")
        }
    assert "normalized_path" in run_item_columns
    with sqlite3.connect(database) as connection:
        precheck_run_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(precheck_runs)")
        }
    assert {"execution_config_json", "execution_checkpoint"} <= precheck_run_columns


def test_unicode_normalized_collisions_are_visible_without_merging_sources(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    payload = source / "payload.jpg"
    payload.write_bytes(b"same bytes")
    observed = payload.stat()
    names = (
        Path("caf\N{LATIN SMALL LETTER E WITH ACUTE}.jpg"),
        Path("cafe\N{COMBINING ACUTE ACCENT}.jpg"),
    )
    events = tuple(
        discovery.DiscoveredSource(
            relative_path=name,
            locator=payload,
            kind=discovery.SourceKind.IMAGE,
            scope=discovery.SourceScope.SOURCE_MEDIA,
            condition=discovery.SourceCondition.UNRESOLVED,
            basis=("media_extension_candidate",),
            size_bytes=observed.st_size,
            mtime_ns=observed.st_mtime_ns,
            device_id=observed.st_dev,
            inode=observed.st_ino,
            mode=observed.st_mode,
        )
        for name in names
    )
    monkeypatch.setattr(
        accounting,
        "discover_source_events",
        lambda _root: iter(events),
    )
    monkeypatch.setattr(
        accounting,
        "_fingerprint_candidate",
        lambda item: _fingerprint.CandidateFingerprint(
            algorithm="test-full-sha256-v1",
            value=item.relative_path.as_posix(),
            size_bytes=observed.st_size,
            mtime_ns=observed.st_mtime_ns,
            device_id=observed.st_dev,
            inode=observed.st_ino,
            mode=observed.st_mode,
        ),
    )
    store = AccountingStore(tmp_path / "working.sqlite3")

    summary = _complete_run(store, "dataset-a", source)

    assert summary.status is WorkingRunStatus.COMPLETED_WITH_ISSUES
    assert {item.relative_path for item in store.get_run_items(summary.run_id)} == set(
        names
    )
    issues = store.get_run_issues(summary.run_id)
    assert {issue.relative_path for issue in issues} == set(names)
    assert {issue.code for issue in issues} == {
        discovery.DiscoveryIssueCode.NORMALIZED_PATH_COLLISION
    }
    assert all(issue.basis == ("unicode_nfc_collision",) for issue in issues)


def test_small_dataset_has_one_explainable_accounting_row_per_path(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / ".albumignore").touch()
    (source / "photo.JPG").write_bytes(b"photo")
    (source / "track.gpx").write_text("<gpx/>", encoding="utf-8")
    (source / "notes.txt").write_text("notes", encoding="utf-8")
    store = AccountingStore(tmp_path / "working.sqlite3")

    summary = _complete_run(store, "dataset-a", source)
    items = store.get_run_items(summary.run_id)

    assert summary.status is WorkingRunStatus.COMPLETED
    assert summary.item_count == 4
    assert {item.relative_path for item in items} == {
        Path(".albumignore"),
        Path("notes.txt"),
        Path("photo.JPG"),
        Path("track.gpx"),
    }
    assert all(item.scope and item.condition and item.basis for item in items)


def test_interrupted_run_reconciles_prior_generation_before_completion(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    for index in range(5):
        (source / f"{index}.JPG").write_bytes(str(index).encode())
    database = tmp_path / "working.sqlite3"
    store = AccountingStore(database)
    store.register_dataset("dataset-a")
    run_id = store.start_or_resume_run("dataset-a", source)
    commit_batch = store._database.commit_batch
    committed_stat = (source / "0.JPG").stat()

    def interrupt_after_commit(run: str, generation: int, events, fingerprint) -> None:
        commit_batch(run, generation, events, fingerprint)
        raise KeyboardInterrupt

    monkeypatch.setattr(store._database, "commit_batch", interrupt_after_commit)
    with pytest.raises(KeyboardInterrupt):
        store.process_run(run_id, batch_size=2)

    interrupted = store.get_run_summary(run_id)
    assert interrupted.status is WorkingRunStatus.RUNNING
    assert interrupted.item_count == 2
    assert interrupted.committed_batches == 1
    assert interrupted.checkpoint is not None

    (source / "0.JPG").write_bytes(b"X")
    os.utime(
        source / "0.JPG",
        ns=(committed_stat.st_atime_ns, committed_stat.st_mtime_ns),
    )
    rewritten_stat = (source / "0.JPG").stat()
    assert (
        rewritten_stat.st_size,
        rewritten_stat.st_mtime_ns,
        rewritten_stat.st_dev,
        rewritten_stat.st_ino,
        rewritten_stat.st_mode,
    ) == (
        committed_stat.st_size,
        committed_stat.st_mtime_ns,
        committed_stat.st_dev,
        committed_stat.st_ino,
        committed_stat.st_mode,
    )
    reopened = AccountingStore(database)
    assert reopened.start_or_resume_run("dataset-a", source) == run_id
    complete = reopened.process_run(run_id, batch_size=2)

    assert complete.status is WorkingRunStatus.COMPLETED
    assert complete.item_count == 5
    assert complete.committed_batches == 4
    items = {item.relative_path: item for item in reopened.get_run_items(run_id)}
    assert len(items) == 5
    assert items[Path("0.JPG")].change_kind is ChangeKind.CHANGED
    assert items[Path("0.JPG")].source_revision == 2
    assert items[Path("1.JPG")].change_kind is ChangeKind.NEW
    assert items[Path("1.JPG")].source_revision == 1


@pytest.mark.parametrize("operation", ["delete", "rename"])
def test_paused_run_reconciles_committed_path_removed_before_resume(
    tmp_path: Path,
    operation: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    committed = source / "a.JPG"
    committed.write_bytes(b"a")
    (source / "b.JPG").write_bytes(b"b")
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")
    run_id = store.start_or_resume_run("dataset-a", source)

    paused = store.process_run(run_id, batch_size=1, max_batches=1)
    assert paused.status is WorkingRunStatus.PAUSED
    assert [item.relative_path for item in store.get_run_items(run_id)] == [
        Path("a.JPG")
    ]

    if operation == "delete":
        committed.unlink()
        expected_items = [Path("b.JPG")]
    else:
        committed.rename(source / "c.JPG")
        expected_items = [Path("b.JPG"), Path("c.JPG")]

    complete = store.process_run(run_id, batch_size=1)

    assert complete.status is WorkingRunStatus.COMPLETED
    assert complete.scan_generation == 2
    assert [
        item.relative_path for item in store.get_run_items(run_id)
    ] == expected_items
    assert [item.relative_path for item in store.get_run_removals(run_id)] == [
        Path("a.JPG")
    ]


def test_new_and_modified_files_only_change_their_own_revision(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "a.JPG").write_bytes(b"a-v1")
    (source / "b.JPG").write_bytes(b"b-v1")
    store = AccountingStore(tmp_path / "working.sqlite3")

    first = _complete_run(store, "dataset-a", source)
    first_revisions = {
        item.relative_path: item.source_revision
        for item in store.get_run_items(first.run_id)
    }

    (source / "c.JPG").write_bytes(b"c-v1")
    second_id = store.start_or_resume_run("dataset-a", source)
    second = store.process_run(second_id)
    second_items = {item.relative_path: item for item in store.get_run_items(second_id)}

    assert second.new_count == 1
    assert second.changed_count == 0
    assert second.reused_count == 2
    assert second_items[Path("c.JPG")].change_kind is ChangeKind.NEW

    (source / "b.JPG").write_bytes(b"b-v2-changed")
    third_id = store.start_or_resume_run("dataset-a", source)
    third = store.process_run(third_id)
    third_items = {item.relative_path: item for item in store.get_run_items(third_id)}

    assert third.new_count == 0
    assert third.changed_count == 1
    assert third.reused_count == 2
    assert third_items[Path("b.JPG")].change_kind is ChangeKind.CHANGED
    assert third_items[Path("a.JPG")].source_revision == first_revisions[Path("a.JPG")]
    assert third_items[Path("b.JPG")].source_revision == (
        first_revisions[Path("b.JPG")] + 1
    )


def test_move_is_conservatively_treated_as_a_new_path(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    original = source / "before.JPG"
    original.write_bytes(b"same bytes")
    store = AccountingStore(tmp_path / "working.sqlite3")
    _complete_run(store, "dataset-a", source)

    original.rename(source / "after.JPG")
    run_id = store.start_or_resume_run("dataset-a", source)
    summary = store.process_run(run_id)
    items = store.get_run_items(run_id)

    assert summary.new_count == 1
    assert summary.reused_count == 0
    assert summary.removed_count == 1
    assert [item.relative_path for item in items] == [Path("after.JPG")]
    assert store.get_run_removals(run_id)[0].relative_path == Path("before.JPG")


def test_deleted_path_creates_one_durable_removal_fact(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "kept.JPG").write_bytes(b"kept")
    removed = source / "removed.JPG"
    removed.write_bytes(b"removed")
    store = AccountingStore(tmp_path / "working.sqlite3")
    first = _complete_run(store, "dataset-a", source)
    first_items = {
        item.relative_path: item for item in store.get_run_items(first.run_id)
    }

    removed.unlink()
    second_id = store.start_or_resume_run("dataset-a", source)
    second = store.process_run(second_id)
    removals = store.get_run_removals(second_id)

    assert second.item_count == 1
    assert second.removed_count == 1
    assert removals[0].relative_path == Path("removed.JPG")
    assert (
        removals[0].previous_revision
        == first_items[Path("removed.JPG")].source_revision
    )
    assert removals[0].basis == ("absent_after_complete_reconciliation",)

    third_id = store.start_or_resume_run("dataset-a", source)
    third = store.process_run(third_id)
    assert third.removed_count == 0


def test_one_fingerprint_failure_does_not_remove_other_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "bad.JPG").write_bytes(b"bad")
    (source / "good.JPG").write_bytes(b"good")
    real_fingerprint = accounting._fingerprint_candidate

    def fail_one(item):
        if item.relative_path == Path("bad.JPG"):
            raise PermissionError("simulated read failure")
        return real_fingerprint(item)

    monkeypatch.setattr(accounting, "_fingerprint_candidate", fail_one)
    store = AccountingStore(tmp_path / "working.sqlite3")

    summary = _complete_run(store, "dataset-a", source)
    items = {item.relative_path: item for item in store.get_run_items(summary.run_id)}

    assert summary.status is WorkingRunStatus.COMPLETED_WITH_ISSUES
    assert items[Path("bad.JPG")].change_kind is ChangeKind.ERROR
    assert items[Path("good.JPG")].change_kind is ChangeKind.NEW
    assert summary.issue_count == 1


def test_source_change_during_fingerprint_is_detected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "photo.JPG"
    source.write_bytes(b"before")
    item = next(
        event
        for event in discovery.discover_source_events(tmp_path)
        if isinstance(event, discovery.DiscoveredSource)
    )
    real_hash = _fingerprint.hash_regular_file

    def mutate_after_read(path: Path, observed: os.stat_result) -> str:
        digest = real_hash(path, observed)
        path.write_bytes(b"after-with-a-different-size")
        return digest

    monkeypatch.setattr(_fingerprint, "hash_regular_file", mutate_after_read)

    with pytest.raises(accounting.SourceChangedDuringRead):
        _fingerprint.fingerprint_candidate(item)


def test_sampled_fingerprint_is_not_exact_content_identity(tmp_path: Path) -> None:
    source = tmp_path / "large.MP4"
    source.write_bytes(b"A" * 200_000)
    observed = source.stat()
    item = next(
        event
        for event in discovery.discover_source_events(tmp_path)
        if isinstance(event, discovery.DiscoveredSource)
    )
    before = _fingerprint.fingerprint_candidate(item)

    with source.open("r+b") as media:
        media.seek(80_000)
        media.write(b"B")
    os.utime(source, ns=(observed.st_atime_ns, observed.st_mtime_ns))
    after = _fingerprint.fingerprint_candidate(item)

    assert before.algorithm.startswith("candidate-")
    assert before.value == after.value
    assert _fingerprint.fingerprint_stat_identity(before) == (
        _fingerprint.fingerprint_stat_identity(after)
    )


def test_unreadable_subtree_keeps_known_items_on_an_explicit_exception_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    blocked_dir = source / "blocked"
    blocked_dir.mkdir(parents=True)
    (blocked_dir / "known.JPG").write_bytes(b"known")
    (source / "visible.JPG").write_bytes(b"visible")
    removed = source / "removed.JPG"
    removed.write_bytes(b"removed")
    store = AccountingStore(tmp_path / "working.sqlite3")
    first = _complete_run(store, "dataset-a", source)
    assert first.status is WorkingRunStatus.COMPLETED
    removed.unlink()

    real_scandir = os.scandir

    def fail_one_directory(path: os.PathLike[str] | str):
        if Path(path) == blocked_dir:
            raise PermissionError("simulated detached subtree")
        return real_scandir(path)

    monkeypatch.setattr(discovery.os, "scandir", fail_one_directory)
    second_id = store.start_or_resume_run("dataset-a", source)
    second = store.process_run(second_id)
    items = {item.relative_path: item for item in store.get_run_items(second_id)}

    assert second.status is WorkingRunStatus.COMPLETED_WITH_ISSUES
    assert second.removed_count == 1
    assert items[Path("visible.JPG")].change_kind is ChangeKind.REUSED
    assert items[Path("blocked/known.JPG")].condition == "unresolved"
    assert items[Path("blocked/known.JPG")].change_kind is ChangeKind.ERROR
    assert "ancestor_directory_read_failed" in items[Path("blocked/known.JPG")].basis
    assert store.get_run_removals(second_id)[0].relative_path == Path("removed.JPG")
    assert store.get_run_issues(second_id)[0].relative_path == Path("blocked")


def test_temporarily_unavailable_source_blocks_without_inferred_deletion(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    detached = tmp_path / "detached"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    store = AccountingStore(tmp_path / "working.sqlite3")
    first = _complete_run(store, "dataset-a", source)

    source.rename(detached)
    blocked_id = store.start_or_resume_run("dataset-a", source)
    blocked = store.process_run(blocked_id)

    assert first.item_count == 1
    assert blocked.status is WorkingRunStatus.BLOCKED
    assert blocked.item_count == 0
    assert blocked.removed_count == 0
    assert blocked.issue_count == 1
    assert store.get_run_removals(blocked_id) == ()

    detached.rename(source)
    recovered = store.process_run(blocked_id)

    assert recovered.status is WorkingRunStatus.COMPLETED
    assert recovered.reused_count == 1
    assert recovered.issue_count == 0


def test_root_scandir_failure_blocks_with_a_durable_reason(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")
    run_id = store.start_or_resume_run("dataset-a", source)

    def fail_root(path: os.PathLike[str] | str):
        raise PermissionError(f"simulated unreadable root: {path}")

    monkeypatch.setattr(discovery.os, "scandir", fail_root)
    summary = store.process_run(run_id, batch_size=1, max_batches=1)

    assert summary.status is WorkingRunStatus.BLOCKED
    assert summary.blocked_reason == "directory_read_failed"
    assert store.get_run_issues(run_id)[0].blocked


def test_accounting_path_does_not_call_python_network_or_change_content_mtime(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Exercise one code path; this is not a sandbox or read-only-mount proof."""

    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.JPG"
    media.write_bytes(b"source bytes")
    before = media.stat()

    def reject_network(*args, **kwargs):
        raise AssertionError("network access is forbidden in PreCheck")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    store = AccountingStore(tmp_path / "working.sqlite3")
    summary = _complete_run(store, "dataset-a", source)

    after = media.stat()
    assert summary.status is WorkingRunStatus.COMPLETED
    assert media.read_bytes() == b"source bytes"
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)


def test_run_source_attachment_requires_reason_for_a_different_root(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")
    first_run = store.start_or_resume_run("dataset-a", first)
    store.process_run(first_run)

    with pytest.raises(SourceRebindRequired, match="provide rebind_reason"):
        store.start_or_resume_run("dataset-a", second)

    second_id = store.start_or_resume_run(
        "dataset-a",
        second,
        rebind_reason="operator selected replacement root",
    )
    attachment = store.get_source_attachment(second_id)
    audit = store.get_source_rebindings(second_id)

    assert attachment.source_root == second
    assert store.get_source_attachment(first_run).source_root == first
    assert (
        attachment.reuse_domain != store.get_source_attachment(first_run).reuse_domain
    )
    assert audit[0].previous_source_root == first
    assert audit[0].source_root == second
    assert audit[0].continuity == "operator_confirmed_unverified"


def test_dataset_identity_does_not_store_a_source_locator(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")
    run_id = store.start_or_resume_run("dataset-a", source)

    with store._database.connect() as connection:
        dataset_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(datasets)")
        }
        run_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(working_runs)")
        }

    assert "source_root" not in dataset_columns
    assert "source_root" in run_columns
    assert store.get_source_attachment(run_id).source_root == source


def test_source_attachment_rejects_workspace_inside_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    store = AccountingStore(source / ".mediasense" / "working.sqlite3")

    with pytest.raises((SourceAttachmentError, OSError), match="must not be inside"):
        store.start_or_resume_run("dataset-a", source)
    assert not (source / ".mediasense").exists()


def test_later_run_at_same_root_keeps_attachment_reuse_domain(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    store = AccountingStore(tmp_path / "working.sqlite3")

    first = _complete_run(store, "dataset-a", source)
    first_attachment = store.get_source_attachment(first.run_id)
    second_id = store.start_or_resume_run("dataset-a", source)
    second_attachment = store.get_source_attachment(second_id)

    assert second_id != first.run_id
    assert second_attachment.source_root == source
    assert second_attachment.reuse_domain == first_attachment.reuse_domain
    assert second_attachment.binding_reason == "verified_existing_source"


def test_same_physical_root_relocation_is_verified_and_audited(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    relocated = tmp_path / "relocated"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    store = AccountingStore(tmp_path / "working.sqlite3")
    first = _complete_run(store, "dataset-a", source)
    first_attachment = store.get_source_attachment(first.run_id)

    source.rename(relocated)
    second_id = store.start_or_resume_run("dataset-a", relocated)
    second_attachment = store.get_source_attachment(second_id)
    summary = store.process_run(second_id)
    audit = store.get_source_rebindings(second_id)

    assert summary.reused_count == 1
    assert second_attachment.reuse_domain == first_attachment.reuse_domain
    assert audit[0].previous_source_root == source
    assert audit[0].source_root == relocated
    assert audit[0].continuity == "verified_root_identity"
    assert audit[0].previous_root_identity == audit[0].root_identity


def test_wrong_root_identity_at_same_locator_blocks_until_explicit_rebind(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    detached = tmp_path / "detached"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"same bytes")
    store = AccountingStore(tmp_path / "working.sqlite3")

    constant = _fingerprint.CandidateFingerprint(
        algorithm="test-candidate-v1",
        value="constant",
        size_bytes=10,
        mtime_ns=20,
        device_id=30,
        inode=40,
        mode=50,
    )
    monkeypatch.setattr(accounting, "_fingerprint_candidate", lambda _item: constant)
    first = _complete_run(store, "dataset-a", source)
    first_attachment = store.get_source_attachment(first.run_id)

    source.rename(detached)
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"same bytes")
    blocked_id = store.start_or_resume_run("dataset-a", source)
    blocked_attachment = store.get_source_attachment(blocked_id)
    blocked = store.process_run(blocked_id)

    assert blocked.status is WorkingRunStatus.BLOCKED
    assert blocked.removed_count == 0
    assert blocked_attachment.root_identity == first_attachment.root_identity
    assert blocked_attachment.reuse_domain == first_attachment.reuse_domain
    assert store.get_source_rebindings(blocked_id) == ()

    reopened = AccountingStore(tmp_path / "working.sqlite3")
    resumed_id = reopened.start_or_resume_run(
        "dataset-a",
        source,
        rebind_reason="operator verified replacement source",
    )
    rebound_attachment = reopened.get_source_attachment(resumed_id)
    complete = reopened.process_run(resumed_id)
    item = reopened.get_run_items(resumed_id)[0]
    audit = reopened.get_source_rebindings(resumed_id)

    assert resumed_id == blocked_id
    assert rebound_attachment.reuse_domain != first_attachment.reuse_domain
    assert complete.status is WorkingRunStatus.COMPLETED
    assert item.change_kind is ChangeKind.CHANGED
    assert item.source_revision == 2
    assert audit[0].reason == "operator verified replacement source"
    assert audit[0].continuity == "operator_confirmed_unverified"
    assert audit[0].previous_root_identity != audit[0].root_identity


def test_initially_unavailable_attachment_can_adopt_first_observed_identity(
    tmp_path: Path,
) -> None:
    source = tmp_path / "not-mounted"
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")

    run_id = store.start_or_resume_run("dataset-a", source)
    blocked = store.process_run(run_id)
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    resumed_id = store.start_or_resume_run("dataset-a", source)
    attachment = store.get_source_attachment(resumed_id)
    complete = store.process_run(resumed_id)

    assert blocked.status is WorkingRunStatus.BLOCKED
    assert resumed_id == run_id
    assert attachment.root_identity is not None
    assert complete.status is WorkingRunStatus.COMPLETED
    assert store.get_source_rebindings(run_id)[0].continuity == (
        "first_available_observation"
    )


def test_source_root_symlink_is_blocked_and_not_followed(tmp_path: Path) -> None:
    source = tmp_path / "source"
    alias = tmp_path / "source-alias"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    alias.symlink_to(source, target_is_directory=True)
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")

    run_id = store.start_or_resume_run("dataset-a", alias)
    summary = store.process_run(run_id)

    assert summary.status is WorkingRunStatus.BLOCKED
    assert summary.item_count == 0
    assert store.get_run_issues(run_id)[0].basis == ("source_root_probe",)


def test_capability_probe_persists_observations_without_overclaiming(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")
    monkeypatch.setattr(
        "mediasense.precheck.source_attachment.os.statvfs",
        lambda _path: (_ for _ in ()).throw(OSError("not supported")),
    )

    run_id = store.start_or_resume_run("dataset-a", source)
    capabilities = store.get_source_attachment(run_id).capabilities

    assert capabilities.source_mount_read_only is None
    assert capabilities.source_process_writable in {True, False}
    assert capabilities.source_case_sensitivity == "unknown_not_probed_on_source"
    assert capabilities.workspace_atomic_replace is True
    assert capabilities.workspace_case_sensitive in {True, False, None}
    assert capabilities.workspace_same_filesystem_as_source in {True, False}
    assert capabilities.sqlite_locking.endswith("_immediate_lock_verified")
    assert capabilities.symlink_policy == "root_and_descendant_symlinks_not_followed"


@pytest.mark.parametrize(
    (
        "source_device",
        "workspace_device",
        "atomic_replace",
        "case_sensitive",
        "expected_same_filesystem",
    ),
    [
        (7, 7, True, True, True),
        (7, 8, True, False, False),
        (None, 8, False, None, None),
    ],
)
def test_filesystem_capability_matrix_preserves_observed_boundaries(
    tmp_path: Path,
    source_device: int | None,
    workspace_device: int,
    atomic_replace: bool,
    case_sensitive: bool | None,
    expected_same_filesystem: bool | None,
) -> None:
    source_stat = (
        None if source_device is None else SimpleNamespace(st_dev=source_device)
    )

    capabilities = source_attachment._capabilities(
        source_root=tmp_path,
        source_stat=source_stat,
        workspace_stat=SimpleNamespace(st_dev=workspace_device),
        atomic_replace=atomic_replace,
        case_sensitive=case_sensitive,
        sqlite_locking="wal_immediate_lock_verified",
    )

    assert capabilities.workspace_same_filesystem_as_source is (
        expected_same_filesystem
    )
    assert capabilities.workspace_atomic_replace is atomic_replace
    assert capabilities.workspace_case_sensitive is case_sensitive
    assert capabilities.source_case_sensitivity == "unknown_not_probed_on_source"


def test_unverified_sqlite_locking_refuses_the_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    store = AccountingStore(tmp_path / "working.sqlite3")
    store.register_dataset("dataset-a")
    monkeypatch.setattr(
        "mediasense.precheck.source_attachment._probe_sqlite_locking",
        lambda _workspace: "wal_lock_not_enforced",
    )

    with pytest.raises(UnsafeWorkspace, match="SQLite locking"):
        store.start_or_resume_run("dataset-a", source)
