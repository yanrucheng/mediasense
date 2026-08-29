from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path

import pytest
from PIL import Image

from mediasense.precheck import (
    AccountingStore,
    ArtifactIntegrity,
    ArtifactStore,
    ImageRenditionProducer,
    PrecheckRunTool,
    ResultStore,
    WorkStore,
    WorkspaceMaintenance,
)


def _produced_rendition(tmp_path: Path):
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir(parents=True)
    media = source / "photo.jpg"
    Image.new("RGB", (80, 60), "green").save(media)
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    rendition = ImageRenditionProducer(database).produce(run_id, Path("photo.jpg"))
    assert rendition.artifact is not None
    return database, source, run_id, rendition


def test_collect_quarantines_only_expired_workspace_orphans(tmp_path: Path) -> None:
    database, source, _run_id, _rendition = _produced_rendition(tmp_path)
    maintenance = WorkspaceMaintenance(database)
    old = datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp()
    paths = (
        database.parent / "_artifacts" / "sha256" / "ff" / "orphan.jpg",
        database.parent / "_artifacts" / "unpublished" / "draft.jpg.part",
        database.parent / "_results" / "sealed" / "orphan.json",
        database.parent / "_results" / "unpublished" / "draft.json.part",
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"untracked")
        os.utime(path, (old, old))
    young = database.parent / "_artifacts" / "unpublished" / "young.part"
    young.write_bytes(b"young")
    source_before = (source / "photo.jpg").read_bytes()

    audit = maintenance.audit(grace_period=timedelta(days=1))
    assert {item.path for item in audit.candidates if item.path is not None} == set(
        paths
    )
    receipt = maintenance.collect(grace_period=timedelta(days=1))

    assert receipt.failures == ()
    assert len(receipt.quarantined_paths) == 4
    assert all(path.is_file() for path in receipt.quarantined_paths)
    assert all(not path.exists() for path in paths)
    assert young.is_file()
    assert (source / "photo.jpg").read_bytes() == source_before


def test_collect_removes_only_unreferenced_invalidated_work_and_artifact(
    tmp_path: Path,
) -> None:
    database, source, _run_id, rendition = _produced_rendition(tmp_path)
    work = WorkStore(database)
    old = datetime.now(timezone.utc) - timedelta(days=2)
    work.invalidate_work(rendition.work.work_id, "obsolete test output", now=old)
    artifact_path = rendition.artifact.path
    source_before = (source / "photo.jpg").read_bytes()
    maintenance = WorkspaceMaintenance(database)

    audit = maintenance.audit(grace_period=timedelta(days=1))
    assert rendition.work.work_id in {
        item.identifier for item in audit.candidates if item.kind == "work"
    }
    assert rendition.artifact.artifact_id in {
        item.identifier for item in audit.candidates if item.kind == "artifact"
    }
    receipt = maintenance.collect(grace_period=timedelta(days=1))

    assert receipt.removed_work_ids == (rendition.work.work_id,)
    assert receipt.removed_artifact_ids == (rendition.artifact.artifact_id,)
    assert not artifact_path.exists()
    assert any(path.read_bytes() for path in receipt.quarantined_paths)
    with pytest.raises(KeyError):
        work.get_work(rendition.work.work_id)
    assert (source / "photo.jpg").read_bytes() == source_before


def test_sealed_result_and_active_run_pin_internal_work(tmp_path: Path) -> None:
    database, _source, run_id, rendition = _produced_rendition(tmp_path)
    results = ResultStore(database)
    sealed = results.seal(results.build_minimal(run_id, [rendition.work.work_id]))
    old = datetime.now(timezone.utc) - timedelta(days=2)
    WorkStore(database).invalidate_work(
        rendition.work.work_id, "rebuild requested", now=old
    )
    maintenance = WorkspaceMaintenance(database)

    audit = maintenance.audit(grace_period=timedelta(days=1))

    assert rendition.work.work_id not in {
        item.identifier for item in audit.candidates if item.kind == "work"
    }
    assert rendition.artifact.artifact_id not in {
        item.identifier for item in audit.candidates if item.kind == "artifact"
    }
    assert sealed.path.is_file()

    database_two, _source_two, run_two, rendition_two = _produced_rendition(
        tmp_path / "active"
    )
    run_tool = PrecheckRunTool(database_two)
    public = run_tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:active-pin",
        }
    )
    run_tool.bind_working_run(str(public["run_ref"]), run_two)
    WorkStore(database_two).invalidate_work(
        rendition_two.work.work_id, "rebuild requested", now=old
    )
    active_audit = WorkspaceMaintenance(database_two).audit(
        grace_period=timedelta(days=1)
    )
    assert rendition_two.work.work_id not in {
        item.identifier for item in active_audit.candidates if item.kind == "work"
    }


def test_integrity_matching_quarantine_bytes_can_repair_missing_artifact(
    tmp_path: Path,
) -> None:
    database, _source, _run_id, rendition = _produced_rendition(tmp_path)
    maintenance = WorkspaceMaintenance(database)
    original_path = rendition.artifact.path
    quarantined = maintenance._quarantine(original_path, datetime.now(timezone.utc))
    assert quarantined.is_file()
    assert ArtifactStore(database).verify(rendition.artifact.artifact_id).integrity is (
        ArtifactIntegrity.MISSING
    )

    restored = maintenance.restore_artifact(rendition.artifact.artifact_id)

    assert restored == original_path
    assert restored.is_file()
    assert ArtifactStore(database).verify(rendition.artifact.artifact_id).integrity is (
        ArtifactIntegrity.AVAILABLE
    )
