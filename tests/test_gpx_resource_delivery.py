"""Resource refusal must survive production orchestration and public Run status."""

from dataclasses import replace

import pytest
from PIL import Image

from mediasense.precheck import PrecheckRunTool, GPXMatchProducer, AccountingStore
from mediasense.precheck._orchestrator import (
    PrecheckExecutionConfig,
    PrecheckExecutionDependencies,
)
from mediasense.precheck.work import WorkStore
from test_gpx import _gpx, TimeOnlyExifTool
from test_precheck_orchestration import _prepare_source_bound_run, _advance_after_scope


def configuration(memory_bytes):
    config = PrecheckExecutionConfig(
        video=False, bundles=False, image_renditions=False
    ).resolve_resources(
        source_storage="local",
        source_storage_evidence="synthetic",
        logical_cpu_count=2,
        available_memory_bytes=1024**3,
    )
    return replace(
        config,
        resource_budget=replace(
            config.resource_budget,
            capacity=replace(
                config.resource_budget.capacity, memory_bytes=memory_bytes
            ),
            max_workers=1,
            max_pending=1,
        ),
    )


def test_gpx_budget_refusal_is_public_blocked_and_successor_reuses_work(
    tmp_path, monkeypatch
):
    database, source, run_id = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (24, 24), "blue").save(source / "photo.jpg")
    (source / "track.gpx").write_text(_gpx([("2026-05-04T12:27:28Z", 22.3, 114.1)]))
    # A replaceable estimator supplies a known over-budget claim. The producer,
    # admission, executor, orchestrator and public Run state transitions are real.
    monkeypatch.setattr(GPXMatchProducer, "memory_estimate", lambda *_: 256 * 1024**2)
    dependencies = PrecheckExecutionDependencies(
        metadata_runner=TimeOnlyExifTool(), exiftool_version="13.30"
    )
    tool = PrecheckRunTool(
        database,
        execution_config=configuration(128 * 1024**2),
        execution_dependencies=dependencies,
    )
    base = {"dataset_ref": "dataset:dataset-a"}
    started = tool.run({**base, "action": "start", "request_id": "gpx-memory"})
    _advance_after_scope(tool, started["run_ref"])
    status_request = {**base, "action": "status", "run_ref": started["run_ref"]}
    status = tool.run(status_request)
    assert status["state"] == "blocked"
    assert status["reason"]["code"] == "gpx_resource_budget_insufficient"
    assert "frozen" in status["reason"]["resume_when"]
    assert "successor" in status["reason"]["resume_when"]
    assert "result" not in status
    work = WorkStore(database)
    metadata = [
        r for r in work.list_run_work(run_id) if r.spec.capability == "source-metadata"
    ]
    pending = [
        r
        for r in work.list_run_work(run_id)
        if r.spec.capability == "gpx-location-candidate"
    ]
    assert len(metadata) == len(pending) == 1
    assert metadata[0].status == "succeeded"
    assert pending[0].status == "ready" and pending[0].attempt_count == 0
    assert tool.run(status_request)["reason"] == status["reason"]

    # Resuming keeps the original frozen budget; it cannot pretend resources grew.
    tool.run({**base, "action": "resume", "run_ref": started["run_ref"]})
    tool.advance(started["run_ref"])
    assert (
        tool.run(status_request)["reason"]["code"] == "gpx_resource_budget_insufficient"
    )
    tool.run({**base, "action": "cancel", "run_ref": started["run_ref"]})
    successor = PrecheckRunTool(
        database,
        execution_config=configuration(512 * 1024**2),
        execution_dependencies=dependencies,
    )
    AccountingStore(database).start_or_resume_run("dataset-a", source)
    next_run = successor.run(
        {**base, "action": "start", "request_id": "gpx-memory-successor"}
    )
    _advance_after_scope(successor, next_run["run_ref"])
    assert work.get_work(metadata[0].work_id).attempt_count == metadata[0].attempt_count
    assert work.get_work(pending[0].work_id).status == "succeeded"
    next_status = successor.run(
        {**base, "action": "status", "run_ref": next_run["run_ref"]}
    )
    assert next_status["reason"]["code"] == "provider_unavailable"
    assert "result" not in next_status  # no maps authorized or fake completion


def test_unknown_gpx_exception_is_not_relabelled_as_resource_wait(
    tmp_path, monkeypatch
):
    database, source, _ = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (24, 24), "blue").save(source / "photo.jpg")
    (source / "track.gpx").write_text(_gpx([("2026-05-04T12:27:28Z", 22.3, 114.1)]))

    def broken(*args, **kwargs):
        raise RuntimeError("unexpected GPX implementation failure")

    monkeypatch.setattr(GPXMatchProducer, "produce", broken)
    tool = PrecheckRunTool(
        database,
        execution_config=configuration(512 * 1024**2),
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=TimeOnlyExifTool(), exiftool_version="13.30"
        ),
    )
    started = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "start", "request_id": "gpx-bug"}
    )
    with pytest.raises(RuntimeError, match="unexpected GPX"):
        _advance_after_scope(tool, started["run_ref"])
    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )
    assert status["state"] == "failed"
    assert status["reason"]["code"] == "execution_worker_crashed"
