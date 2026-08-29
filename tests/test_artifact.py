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
