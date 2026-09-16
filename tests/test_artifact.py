from __future__ import annotations

from datetime import timedelta
import errno
from pathlib import Path

import pytest

from mediasense.precheck import (
    AccountingStore,
    ArtifactIntegrity,
    ArtifactStore,
    ArtifactIntegrityError,
    InvalidArtifactDraft,
    SourceValidityStore,
    WorkSpec,
    WorkStatus,
    WorkStore,
    source_revision_dependency,
)


def _prepared_work(tmp_path: Path) -> tuple[Path, Path, str, WorkStore, object]:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    media.write_bytes(b"source bytes")
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    item = accounting.get_run_items(run_id)[0]
    proof = SourceValidityStore(database).prove(run_id, Path("photo.jpg"))
    work = WorkStore(database)
    record = work.ensure_work(
        run_id,
        WorkSpec(
            capability="test-artifact",
            producer_identity="test-artifact-v1",
            dependencies=(
                source_revision_dependency(
                    "dataset-a", Path("photo.jpg"), item.source_revision or 0
                ),
                proof.dependency(),
            ),
        ),
    )
    lease = work.claim_ready_work(
        run_id,
        "test-worker",
        lease_duration=timedelta(minutes=5),
    )[0]
    assert lease.work_id == record.work_id
    return database, media, run_id, work, lease


def test_partial_draft_is_never_marked_successful_and_is_recoverable(
    tmp_path: Path,
) -> None:
    database, _media, _run_id, work, lease = _prepared_work(tmp_path)
    artifacts = ArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"partial")

    audit = artifacts.audit()

    assert audit.unpublished_paths == (draft.path,)
    assert audit.available == ()
    assert work.get_work(lease.work_id).status is WorkStatus.RUNNING
    assert artifacts.artifacts_for_work(lease.work_id) == ()
    assert work.recover_expired_leases(now=lease.expires_at + timedelta(seconds=1)) == (
        lease.work_id,
    )
    assert work.get_work(lease.work_id).status is WorkStatus.RETRYABLE_FAILURE


def test_artifact_publication_binds_complete_bytes_and_work_in_one_transaction(
    tmp_path: Path,
) -> None:
    database, _media, _run_id, work, lease = _prepared_work(tmp_path)
    artifacts = ArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"complete jpeg bytes")

    completed, artifact = artifacts.publish(
        lease,
        draft,
        suffix=".jpg",
        media_type="image/jpeg",
        role="rendition",
        output={"width": 320, "height": 200},
    )

    assert completed.status is WorkStatus.SUCCEEDED
    assert completed.output == {
        "artifacts": [{"artifact_ref": artifact.artifact_id, "role": "rendition"}],
        "value": {"height": 200, "width": 320},
    }
    assert artifact.integrity is ArtifactIntegrity.AVAILABLE
    assert artifact.path.read_bytes() == b"complete jpeg bytes"
    assert not draft.path.exists()
    assert artifacts.artifacts_for_work(lease.work_id) == (artifact,)
    assert artifacts.audit().available == (artifact.artifact_id,)


def test_crash_after_file_publication_leaves_only_detectable_orphan(
    tmp_path: Path,
) -> None:
    database, _media, _run_id, work, lease = _prepared_work(tmp_path)

    class CrashingArtifactStore(ArtifactStore):
        def _after_file_published(self, path: Path) -> None:
            raise RuntimeError("simulated crash")

    artifacts = CrashingArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"complete but uncommitted")

    with pytest.raises(RuntimeError, match="simulated crash"):
        artifacts.publish(
            lease,
            draft,
            suffix=".jpg",
            media_type="image/jpeg",
            role="rendition",
        )

    audit = artifacts.audit()
    assert len(audit.orphan_paths) == 1
    assert audit.available == ()
    assert work.get_work(lease.work_id).status is WorkStatus.RUNNING


def test_disk_full_during_publication_never_marks_partial_bytes_successful(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database, _media, _run_id, work, lease = _prepared_work(tmp_path)
    artifacts = ArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"complete producer output")

    def fail_copy(_source: Path, destination: Path) -> tuple[str, int]:
        destination.write_bytes(b"partial")
        raise OSError(errno.ENOSPC, "simulated disk full")

    monkeypatch.setattr(
        "mediasense.precheck._artifact_sqlite._copy_stable_regular_file",
        fail_copy,
    )
    with pytest.raises(OSError) as raised:
        artifacts.publish(
            lease,
            draft,
            suffix=".jpg",
            media_type="image/jpeg",
            role="rendition",
        )

    assert raised.value.errno == errno.ENOSPC
    audit = artifacts.audit()
    assert audit.available == ()
    assert audit.orphan_paths == ()
    assert len(audit.unpublished_paths) == 2
    assert work.get_work(lease.work_id).status is WorkStatus.RUNNING


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_missing_or_corrupt_artifact_invalidates_work_and_can_be_recomputed(
    tmp_path: Path,
    damage: str,
) -> None:
    database, _media, run_id, work, lease = _prepared_work(tmp_path)
    artifacts = ArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    expected = b"valid bytes"
    draft.path.write_bytes(expected)
    completed, artifact = artifacts.publish(
        lease,
        draft,
        suffix=".jpg",
        media_type="image/jpeg",
        role="rendition",
    )
    if damage == "missing":
        artifact.path.unlink()
        expected_integrity = ArtifactIntegrity.MISSING
    else:
        artifact.path.chmod(0o644)
        artifact.path.write_bytes(b"corrupt bytes")
        expected_integrity = ArtifactIntegrity.CORRUPT

    assert artifacts.verify(artifact.artifact_id).integrity is expected_integrity
    assert work.get_work(completed.work_id).status is WorkStatus.INVALIDATED

    replacement = work.ensure_work(run_id, completed.spec)
    replacement_lease = work.claim_ready_work(
        run_id,
        "replacement-worker",
        lease_duration=timedelta(minutes=5),
    )[0]
    replacement_draft = artifacts.create_draft(replacement_lease, suffix=".jpg")
    replacement_draft.path.write_bytes(expected)
    replacement, restored = artifacts.publish(
        replacement_lease,
        replacement_draft,
        suffix=".jpg",
        media_type="image/jpeg",
        role="rendition",
    )

    assert replacement.status is WorkStatus.SUCCEEDED
    assert replacement.work_id != completed.work_id
    assert restored.artifact_id == artifact.artifact_id
    assert restored.integrity is ArtifactIntegrity.AVAILABLE
    assert restored.path.read_bytes() == expected


def test_artifact_publish_requires_exact_source_dependency(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"source bytes")
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    item = accounting.get_run_items(run_id)[0]
    work = WorkStore(database)
    record = work.ensure_work(
        run_id,
        WorkSpec(
            capability="unsafe-artifact",
            producer_identity="test-unsafe-v1",
            dependencies=(
                source_revision_dependency(
                    "dataset-a", Path("photo.jpg"), item.source_revision or 0
                ),
            ),
        ),
    )
    lease = work.claim_ready_work(
        run_id, "test-worker", lease_duration=timedelta(minutes=5)
    )[0]
    artifacts = ArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"bytes")

    with pytest.raises(InvalidArtifactDraft, match="exact source content"):
        artifacts.publish(
            lease,
            draft,
            suffix=".jpg",
            media_type="image/jpeg",
            role="rendition",
        )

    assert work.get_work(record.work_id).status is WorkStatus.RUNNING


def test_source_change_before_publish_invalidates_work_without_publishing(
    tmp_path: Path,
) -> None:
    database, media, _run_id, work, lease = _prepared_work(tmp_path)
    artifacts = ArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"complete output")
    media.write_bytes(b"changed after accounting")

    with pytest.raises(InvalidArtifactDraft, match="source changed"):
        artifacts.publish(
            lease,
            draft,
            suffix=".jpg",
            media_type="image/jpeg",
            role="rendition",
        )

    assert work.get_work(lease.work_id).status is WorkStatus.INVALIDATED
    assert artifacts.audit().available == ()


def test_published_bytes_are_rechecked_before_work_is_marked_successful(
    tmp_path: Path,
) -> None:
    database, _media, _run_id, work, lease = _prepared_work(tmp_path)

    class MutatingArtifactStore(ArtifactStore):
        def _after_file_published(self, path: Path) -> None:
            path.chmod(0o600)
            path.write_bytes(b"changed after atomic publication")

    artifacts = MutatingArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"complete producer output")

    with pytest.raises(ArtifactIntegrityError, match="changed before Work binding"):
        artifacts.publish(
            lease,
            draft,
            suffix=".jpg",
            media_type="image/jpeg",
            role="rendition",
        )

    assert work.get_work(lease.work_id).status is WorkStatus.RUNNING
    assert artifacts.artifacts_for_work(lease.work_id) == ()
    assert len(artifacts.audit().orphan_paths) == 1


def _published_work(tmp_path):
    database, media, run_id, work, lease = _prepared_work(tmp_path)
    artifacts = ArtifactStore(database)
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"valid artifact")
    completed, artifact = artifacts.publish(lease, draft, suffix=".jpg", media_type="image/jpeg", role="rendition")
    return database, media, run_id, work, artifacts, completed, artifact


def test_reuse_attaches_only_after_verification_and_rechecks_work(tmp_path, monkeypatch):
    from mediasense.precheck import InvalidWorkTransition
    import sqlite3
    database, media, _, work, artifacts, completed, artifact = _published_work(tmp_path)
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run("dataset-a", media.parent)
    accounting.process_run(run_id)
    SourceValidityStore(database).prove(run_id, Path("photo.jpg"))
    original = artifacts._observe_artifacts
    def inspect(ids, *args):
        assert work.list_run_work(run_id) == ()
        observations = original(ids, *args)
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE work_records SET status = 'invalidated' WHERE work_id = ?", (completed.work_id,))
        return observations
    monkeypatch.setattr(artifacts, "_observe_artifacts", inspect)
    with pytest.raises(InvalidWorkTransition, match="qualification changed"):
        artifacts.ensure_artifact_work_many(run_id, (completed.spec,))
    assert work.list_run_work(run_id) == ()
    assert artifact.path.read_bytes() == b"valid artifact"


def test_reuse_batch_deduplicates_material_and_reports_committed_work(tmp_path, monkeypatch):
    database, media, _, work, artifacts, completed, artifact = _published_work(tmp_path)
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run("dataset-a", media.parent)
    accounting.process_run(run_id)
    SourceValidityStore(database).prove(run_id, Path("photo.jpg"))
    from mediasense.precheck import _artifact_sqlite
    original = _artifact_sqlite._digest_file
    calls = []
    def digest(path):
        assert work.list_run_work(run_id) == ()
        calls.append(path)
        return original(path)
    monkeypatch.setattr(_artifact_sqlite, "_digest_file", digest)
    values = artifacts.ensure_artifact_work_many(run_id, (completed.spec, completed.spec))
    assert values == ((completed, (artifact,)),) * 2
    assert calls == [artifact.path]
    assert work.list_run_work(run_id) == (completed,)
    assert artifacts.verify_many(()) == ()
    with pytest.raises(KeyError):
        artifacts.artifacts_for_works(("unknown",))


def test_artifact_replacement_after_hash_is_reverified_once(tmp_path, monkeypatch):
    _, _, _, work, artifacts, completed, artifact = _published_work(tmp_path)
    from mediasense.precheck import _artifact_sqlite
    original = _artifact_sqlite._digest_file
    calls = []
    def replace_after_hash(path):
        observed = original(path)
        calls.append(path)
        if len(calls) == 1:
            replacement = path.with_suffix(".replacement")
            replacement.write_bytes(b"changed artifact")
            replacement.replace(path)
        return observed
    monkeypatch.setattr(_artifact_sqlite, "_digest_file", replace_after_hash)
    assert artifacts.verify_many((artifact.artifact_id, artifact.artifact_id))[0].integrity is ArtifactIntegrity.CORRUPT
    assert len(calls) == 2
    assert work.get_work(completed.work_id).status is WorkStatus.INVALIDATED


def test_artifact_batch_error_rolls_back_invalidation_and_attachment(tmp_path, monkeypatch):
    import sqlite3
    database, media, _, work, artifacts, completed, artifact = _published_work(tmp_path)
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run("dataset-a", media.parent)
    accounting.process_run(run_id)
    SourceValidityStore(database).prove(run_id, Path("photo.jpg"))
    artifact.path.chmod(0o644)
    artifact.path.write_bytes(b"corrupt")
    original = artifacts._record_verifications
    def fail(connection, observations):
        original(connection, observations)
        raise RuntimeError("unknown database failure")
    monkeypatch.setattr(artifacts, "_record_verifications", fail)
    with pytest.raises(RuntimeError, match="unknown database failure"):
        artifacts.ensure_artifact_work_many(run_id, (completed.spec,))
    assert work.get_work(completed.work_id).status is WorkStatus.SUCCEEDED
    assert work.list_run_work(run_id) == ()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT integrity_status FROM artifacts").fetchone()[0] == "available"


def test_successful_artifact_work_without_binding_is_an_error(tmp_path):
    import sqlite3
    database, _, run_id, _, artifacts, completed, _ = _published_work(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM work_artifacts WHERE work_id = ?", (completed.work_id,))
    with pytest.raises(ArtifactIntegrityError, match="no material binding"):
        artifacts.ensure_artifact_work_many(run_id, (completed.spec,))


def test_corrupt_artifact_invalidates_same_batch_dependent_before_return(tmp_path):
    from mediasense.precheck import upstream_dependency
    from dataclasses import replace
    database, _, run_id, work, artifacts, completed, artifact = _published_work(tmp_path)
    spec = replace(completed.spec, producer_identity="dependent", dependencies=(*completed.spec.dependencies, upstream_dependency(completed)))
    dependent = work.ensure_work(run_id, spec)
    lease = work.claim_ready_work(run_id, "dependent", lease_duration=timedelta(minutes=1), work_id=dependent.work_id)[0]
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"healthy dependent")
    succeeded, healthy = artifacts.publish(lease, draft, suffix=".jpg", media_type="image/jpeg", role="rendition")
    artifact.path.chmod(0o644)
    artifact.path.write_bytes(b"corrupt")
    values = artifacts.ensure_artifact_work_many(run_id, (succeeded.spec, completed.spec))
    assert [record.status for record, _ in values] == [WorkStatus.BLOCKED, WorkStatus.READY]
    assert all(not materials for _, materials in values)
    assert work.get_work(succeeded.work_id).status is WorkStatus.INVALIDATED
    assert healthy.path.read_bytes() == b"healthy dependent"


def test_public_progress_does_not_count_unverified_reuse(tmp_path, monkeypatch):
    from mediasense.precheck import PrecheckRunTool
    database, media, _, work, artifacts, completed, _ = _published_work(tmp_path)
    tool = PrecheckRunTool(database)
    created = tool.run({"dataset_ref": "dataset:dataset-a", "action": "start", "request_id": "progress"})
    run_ref = created["run_ref"]
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run("dataset-a", media.parent)
    accounting.process_run(run_id)
    tool.bind_working_run(run_ref, run_id)
    # Use the rendition capability so the ordinary public phase counts it.
    from dataclasses import replace
    spec = replace(completed.spec, capability="image-rendition")
    # Seed that capability through the same publisher, before attaching to this Run.
    previous = work.get_attempts(completed.work_id)[0].run_id
    record = work.ensure_work(previous, spec)
    lease = work.claim_ready_work(previous, "seed", lease_duration=timedelta(minutes=1), work_id=record.work_id)[0]
    draft = artifacts.create_draft(lease, suffix=".jpg")
    draft.path.write_bytes(b"valid artifact")
    record, _ = artifacts.publish(lease, draft, suffix=".jpg", media_type="image/jpeg", role="rendition")
    SourceValidityStore(database).prove(run_id, Path("photo.jpg"))
    tool.record_phase(run_ref, "renditions", total="unknown")
    original = artifacts._observe_artifacts
    def observe(*args, **kwargs):
        status = tool.run({"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref})
        assert status["progress"]["processed"] == 0
        return original(*args, **kwargs)
    monkeypatch.setattr(artifacts, "_observe_artifacts", observe)
    artifacts.ensure_artifact_work_many(run_id, (spec,))
    status = tool.run({"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref})
    assert status["progress"]["processed"] == 1
    assert len(work.get_attempts(record.work_id)) == 1
