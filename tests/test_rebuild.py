from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    EmbeddingProducer,
    EmbeddingProfile,
    ImageRenditionProducer,
    InvalidWorkTransition,
    PrecheckReadTool,
    ResultStore,
    WorkSpec,
    WorkStatus,
    WorkStore,
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


class FakeEncoder:
    identity = "fake-local-model@sha256:one"

    def encode_image(self, _image_path: Path) -> tuple[float, ...]:
        return (1.0, 2.0, 3.0, 4.0)


def test_manual_rebuild_selects_exact_work_and_invalidates_dependents_only(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (40, 20), "red").save(source / "selected.jpg")
    Image.new("RGB", (40, 20), "blue").save(source / "unrelated.jpg")
    run_id = _closed_run(database, source)
    renditions = ImageRenditionProducer(database)
    selected = renditions.produce(run_id, Path("selected.jpg"))
    unrelated = renditions.produce(run_id, Path("unrelated.jpg"))
    embedding = EmbeddingProducer(database, FakeEncoder()).produce(
        run_id,
        selected.work.work_id,
        profile=EmbeddingProfile(name="test", dimensions=4),
    )
    sealed = ResultStore(database).seal(
        ResultStore(database).build_minimal(
            run_id, [selected.work.work_id, unrelated.work.work_id]
        )
    )
    sealed_before = sealed.path.read_bytes()

    invalidated = WorkStore(database).invalidate_for_rebuild(
        run_id,
        "operator requested selected rendition rebuild",
        capabilities=["image-rendition"],
        source_paths=[Path("selected.jpg")],
    )

    assert selected.work.work_id in invalidated
    assert embedding.work.work_id in invalidated
    assert unrelated.work.work_id not in invalidated
    assert (
        WorkStore(database).get_work(selected.work.work_id).status
        is WorkStatus.INVALIDATED
    )
    assert (
        WorkStore(database).get_work(embedding.work.work_id).status
        is WorkStatus.INVALIDATED
    )
    assert (
        WorkStore(database).get_work(unrelated.work.work_id).status
        is WorkStatus.SUCCEEDED
    )
    assert (
        PrecheckReadTool(database).read(
            {"action": "inspect", "result_ref": sealed.result_ref}
        )["outcome"]
        == "ok"
    )
    assert sealed.path.read_bytes() == sealed_before

    replacement = renditions.produce(run_id, Path("selected.jpg"))
    replacement_embedding = EmbeddingProducer(database, FakeEncoder()).produce(
        run_id,
        replacement.work.work_id,
        profile=EmbeddingProfile(name="test", dimensions=4),
    )
    assert replacement.work.work_id != selected.work.work_id
    assert replacement_embedding.work.work_id != embedding.work.work_id
    assert replacement_embedding.work.status is WorkStatus.SUCCEEDED


def test_manual_rebuild_rejects_empty_unknown_and_actively_leased_selectors(
    tmp_path: Path,
) -> None:
    database = tmp_path / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "item.jpg").write_bytes(b"bytes")
    run_id = _closed_run(database, source)
    work = WorkStore(database)

    with pytest.raises(ValueError, match="at least one selector"):
        work.invalidate_for_rebuild(run_id, "reason")
    with pytest.raises(KeyError, match="not attached"):
        work.invalidate_for_rebuild(run_id, "reason", work_ids=["unknown"])

    record = work.ensure_work(run_id, WorkSpec("test-capability", "test-producer"))
    work.claim_ready_work(
        run_id,
        "worker",
        work_id=record.work_id,
        lease_duration=timedelta(minutes=1),
    )
    with pytest.raises(InvalidWorkTransition, match="actively leased"):
        work.invalidate_for_rebuild(
            run_id,
            "reason",
            work_ids=[record.work_id],
        )
    assert work.get_work(record.work_id).status is WorkStatus.RUNNING
