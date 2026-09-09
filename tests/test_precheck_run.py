from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import errno
import json
from pathlib import Path
import sqlite3

import pytest
from jsonschema import Draft202012Validator
from PIL import Image

from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    PrecheckConfirmationContext,
    PrecheckRunTool,
    ResultStore,
)
from mediasense.precheck import run as run_module


ROOT = Path(__file__).parents[1]
RUN_SPEC = ROOT / "docs" / "spec" / "contract/precheck-run"
READ_SPEC = ROOT / "docs" / "spec" / "contract/precheck-read"


def _output_validator() -> Draft202012Validator:
    run_contract = json.loads(
        (RUN_SPEC / "precheck-run.tool.json").read_text(encoding="utf-8")
    )
    return Draft202012Validator(run_contract["outputSchema"])


def _disclosure():
    return {
        "geo_request_fingerprint": "sha256:" + "a" * 64,
        "operation": "resolve_place",
        "coordinates": [{"latitude": 22.3, "longitude": 114.1, "datum": "WGS84"}],
        "pending_logical_queries": 237,
        "source_item_outcomes": 237,
        "nearby_radius_meters": 500,
        "max_places": 30,
        "transmitted_data_classes": ["coordinate", "datum", "locale"],
        "providers": [{"provider": "fake", "data_handling": "synthetic"}],
        "max_provider_requests": 711,
        "max_billable_units": None,
        "billable_calls": None,
        "result_retention": "immutable_precheck_result",
        "retry_policy": {
            "max_attempts": 3,
            "backoff_seconds": [1, 3],
            "coordinate_deadline_seconds": 120,
        },
    }


def _workspace(tmp_path: Path, *dataset_ids: str) -> tuple[Path, AccountingStore]:
    database = tmp_path / "workspace" / "working.sqlite3"
    accounting = AccountingStore(database)
    for dataset_id in dataset_ids:
        accounting.register_dataset(dataset_id)
    return database, accounting


def _sealed_image_result(
    tmp_path: Path,
    database: Path,
    accounting: AccountingStore,
    *,
    dataset_id: str = "dataset-a",
    name: str = "photo.jpg",
):
    source = tmp_path / f"source-{dataset_id}-{name}"
    source.mkdir()
    Image.new("RGB", (80, 60), "purple").save(source / name)
    accounting_run = accounting.start_or_resume_run(dataset_id, source)
    accounting.process_run(accounting_run)
    outcome = ImageRenditionProducer(database).produce(accounting_run, Path(name))
    results = ResultStore(database)
    return results.seal(results.build_minimal(accounting_run, [outcome.work.work_id]))


def _draft_for_running_run(
    tmp_path: Path,
    database: Path,
    accounting: AccountingStore,
    tool: PrecheckRunTool,
    *,
    request_id: str,
):
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": request_id,
        }
    )
    source = tmp_path / request_id.replace(":", "-")
    source.mkdir()
    Image.new("RGB", (80, 60), "purple").save(source / "photo.jpg")
    accounting_run = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(accounting_run)
    tool.bind_working_run(str(started["run_ref"]), accounting_run)
    outcome = ImageRenditionProducer(database).produce(
        accounting_run, Path("photo.jpg")
    )
    draft = ResultStore(database).build_minimal(accounting_run, [outcome.work.work_id])
    return str(started["run_ref"]), draft


def _assert_valid(response: dict[str, object]) -> None:
    _output_validator().validate(response)


class _FakeClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 9, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


def test_start_is_durable_idempotent_and_conflict_safe(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a", "dataset-b")
    tool = PrecheckRunTool(database)
    request = {
        "action": "start",
        "dataset_ref": "dataset:dataset-a",
        "request_id": "request:run-a",
    }

    started = tool.run(request)
    _assert_valid(started)
    assert set(started) == {"run_ref"}
    tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "pause",
            "run_ref": started["run_ref"],
        }
    )

    replayed = tool.run(request)
    _assert_valid(replayed)
    assert replayed == started

    conflict = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-b",
            "request_id": "request:run-a",
        }
    )
    _assert_valid(conflict)
    assert conflict["error"]["code"] == "idempotency_conflict"

    missing = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:missing",
            "request_id": "request:missing",
        }
    )
    _assert_valid(missing)
    assert missing["error"]["code"] == "dataset_not_found"


def test_pause_resume_cancel_are_target_idempotent(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:controls",
        }
    )
    run_ref = str(started["run_ref"])
    running = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    _assert_valid(running)
    assert running["reason"]["code"] == "suspected_stalled"
    assert running["reason"]["code"] == "suspected_stalled"
    assert set(running["allowed_actions"]) == {"resume", "cancel"}
    assert set(running["progress"]) == {
        "phase",
        "unit",
        "processed",
        "total",
        "last_progress_at",
    }
    assert running["progress"]["total"] is None

    paused = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "pause", "run_ref": run_ref}
    )
    _assert_valid(paused)
    assert paused["state"] == "paused"
    paused_again = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "pause", "run_ref": run_ref}
    )
    _assert_valid(paused_again)
    assert paused_again["state"] == "paused"
    paused_status = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    _assert_valid(paused_status)
    assert paused_status["reason"]["code"] == "user_requested"
    assert "result" not in paused_status

    resumed = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "resume", "run_ref": run_ref}
    )
    _assert_valid(resumed)
    assert resumed["state"] == "running"
    resumed_again = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "resume", "run_ref": run_ref}
    )
    _assert_valid(resumed_again)
    assert resumed_again["state"] == "running"

    cancelled = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "cancel", "run_ref": run_ref}
    )
    _assert_valid(cancelled)
    cancelled_again = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "cancel", "run_ref": run_ref}
    )
    _assert_valid(cancelled_again)
    assert cancelled_again["state"] == "cancelled"
    cancelled_status = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    _assert_valid(cancelled_status)
    assert cancelled_status["state"] == "cancelled"
    assert "result" not in cancelled_status

    refused = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "pause", "run_ref": run_ref}
    )
    _assert_valid(refused)
    assert refused["error"] == {
        "code": "invalid_state",
        "message": "A cancelled Run cannot pause.",
        "current_state": "cancelled",
        "run_ref": run_ref,
    }


def test_advance_without_execution_preparation_fails_fast(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:unprepared",
        }
    )

    failed = tool.advance(str(started["run_ref"]))

    _assert_valid(failed)
    assert failed["state"] == "failed"
    assert failed["reason"]["code"] == "execution_not_prepared"


def test_confirmation_binds_authority_to_the_frozen_work_set(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:confirmation",
        }
    )
    run_ref = str(started["run_ref"])

    paused = tool.require_confirmation(
        run_ref,
        summary="Reverse-geocode the frozen representative set.",
        quantity=237,
        unit="logical_queries",
        skip_allowed=False,
        pending_fingerprint="sha256:" + "a" * 64,
        disclosure=_disclosure(),
    )
    _assert_valid(paused)
    assert paused["state"] == "paused"
    assert paused["reason"]["resume_when"]
    assert paused["confirmation"]["disclosure"]["pending_logical_queries"] == 237

    missing_decision = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "resume", "run_ref": run_ref}
    )
    _assert_valid(missing_decision)
    assert missing_decision["error"]["code"] == "invalid_request"
    assert (
        tool.run(
            {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
        )["state"]
        == "paused"
    )

    resumed = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resume",
            "run_ref": run_ref,
            "decision": "proceed",
        },
        confirmation=PrecheckConfirmationContext(
            principal_ref="human:test",
            confirmed_content_identity=paused["confirmation"]["content_identity"],
            confirmed_at=datetime.now(timezone.utc),
        ),
    )
    _assert_valid(resumed)
    assert (
        tool.confirmation_decision(run_ref, pending_fingerprint="sha256:" + "a" * 64)
        == "proceed"
    )

    still_running = tool.require_confirmation(
        run_ref,
        summary="Reverse-geocode the frozen representative set.",
        quantity=237,
        unit="logical_queries",
        skip_allowed=False,
        pending_fingerprint="sha256:" + "a" * 64,
        disclosure=_disclosure(),
    )
    assert still_running["state"] == "running"

    changed = tool.require_confirmation(
        run_ref,
        summary="Reverse-geocode the changed representative set.",
        quantity=238,
        unit="logical_queries",
        skip_allowed=False,
        pending_fingerprint="sha256:" + "b" * 64,
        disclosure=_disclosure(),
    )
    _assert_valid(changed)
    assert changed["state"] == "paused"
    assert (
        tool.confirmation_decision(run_ref, pending_fingerprint="sha256:frozen-b")
        is None
    )


def test_block_interruption_and_failure_remain_observable(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    first = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:recovery-a",
        }
    )
    first_ref = str(first["run_ref"])
    blocked = tool.mark_blocked(
        first_ref,
        code="source_unavailable",
        message="The source volume is not currently available.",
        resume_when="The same compatible source is available again.",
    )
    _assert_valid(blocked)
    assert blocked["state"] == "blocked"
    assert blocked["reason"]["resume_when"]
    tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "resume", "run_ref": first_ref}
    )
    interrupted = tool.mark_interrupted(first_ref)
    _assert_valid(interrupted)
    assert interrupted["reason"]["code"] == "process_interrupted"
    assert interrupted["state"] == "paused"

    tool.run(
        {"action": "cancel", "dataset_ref": "dataset:dataset-a", "run_ref": first_ref}
    )
    second = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:recovery-b",
        }
    )
    failed = tool.mark_failed(
        str(second["run_ref"]),
        code="result_untrusted",
        message="No trustworthy Result can be formed.",
    )
    _assert_valid(failed)
    assert failed["state"] == "failed"
    assert "allowed_actions" not in failed
    assert "result" not in failed


def test_completion_verifies_result_and_successor_lineage(tmp_path: Path) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:complete",
        }
    )
    result = _sealed_image_result(tmp_path, database, accounting)

    completed = tool.complete_with_result(str(started["run_ref"]), result.result_ref)
    _assert_valid(completed)
    assert completed["state"] == "completed"
    assert "progress" not in completed
    assert completed["result"]["coverage"] == "complete"
    assert completed["result"] == {
        "ref": result.result_ref,
        "coverage": "complete",
        "readiness": "plan_ready",
    }
    assert "allowed_actions" not in completed
    assert (
        tool._store.get(str(started["run_ref"]))["published_result"]["result_ref"]
        == result.result_ref
    )

    successor = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "start",
            "prior_result_ref": result.result_ref,
            "request_id": "request:successor",
        }
    )
    _assert_valid(successor)
    assert tool._store.get(successor["run_ref"])["dataset_ref"] == "dataset:dataset-a"
    assert (
        tool._store.get(successor["run_ref"])["prior_result_ref"] == result.result_ref
    )


def test_internal_publish_result_seals_verifies_and_completes_run(
    tmp_path: Path,
) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    run_ref, draft = _draft_for_running_run(
        tmp_path,
        database,
        accounting,
        tool,
        request_id="request:publish",
    )

    completed = tool.publish_result(run_ref, draft)

    _assert_valid(completed)
    assert completed["state"] == "completed"
    details = tool.run(
        {
            "action": "status",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": run_ref,
            "include": ["accounting"],
        }
    )
    assert (
        details["accounting"]["discovered"] == details["accounting"]["accounted"] == 1
    )
    assert details["accounting"]["scope_condition"] == [
        {"scope": "source_media", "condition": "usable", "count": 1}
    ]
    result_ref = str(completed["result"]["ref"])
    assert ResultStore(database).audit().available == (result_ref,)


def test_internal_publish_result_marks_validation_failure_without_publication(
    tmp_path: Path,
) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    run_ref, draft = _draft_for_running_run(
        tmp_path,
        database,
        accounting,
        tool,
        request_id="request:invalid-result",
    )
    usable = next(source for source in draft.sources if source.condition == "usable")
    broken = replace(
        draft,
        relationships=tuple(
            relationship
            for relationship in draft.relationships
            if relationship.target_ref != usable.ref
        ),
    )

    failed = tool.publish_result(run_ref, broken)

    _assert_valid(failed)
    assert failed["state"] == "failed"
    assert failed["reason"]["code"] == "result_validation_failed"
    assert "result" not in failed
    assert ResultStore(database).audit().available == ()


def test_internal_publish_result_blocks_on_disk_full_without_partial_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    run_ref, draft = _draft_for_running_run(
        tmp_path,
        database,
        accounting,
        tool,
        request_id="request:disk-full",
    )

    def fail_disk_full(_self, path: Path, encoded: bytes) -> None:
        path.write_bytes(encoded[:17])
        raise OSError(errno.ENOSPC, "simulated disk full")

    monkeypatch.setattr(
        run_module.ResultStore, "_write_unpublished_result", fail_disk_full
    )
    blocked = tool.publish_result(run_ref, draft)

    _assert_valid(blocked)
    assert blocked["state"] == "blocked"
    assert blocked["reason"]["code"] == "workspace_write_failed"
    assert "result" not in blocked
    audit = ResultStore(database).audit()
    assert audit.available == ()
    assert len(audit.unpublished_paths) == 1


def test_internal_publish_result_recovers_crash_before_result_registration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    run_ref, draft = _draft_for_running_run(
        tmp_path,
        database,
        accounting,
        tool,
        request_id="request:publish-file-crash",
    )

    def crash_after_file(_self, _path: Path) -> None:
        raise RuntimeError("simulated process exit after Result file publication")

    monkeypatch.setattr(
        run_module.ResultStore, "_after_file_published", crash_after_file
    )
    with pytest.raises(RuntimeError, match="simulated process exit"):
        tool.publish_result(run_ref, draft)
    interrupted = ResultStore(database).audit()
    assert interrupted.available == ()
    assert len(interrupted.orphan_paths) == 1

    monkeypatch.setattr(
        run_module.ResultStore,
        "_after_file_published",
        lambda _self, _path: None,
    )
    completed = tool.publish_result(run_ref, draft)

    _assert_valid(completed)
    assert completed["state"] == "completed"
    audit = ResultStore(database).audit()
    assert audit.available == (completed["result"]["ref"],)
    assert audit.orphan_paths == ()


def test_internal_publish_result_reuses_registered_result_after_completion_crash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    run_ref, draft = _draft_for_running_run(
        tmp_path,
        database,
        accounting,
        tool,
        request_id="request:publish-completion-crash",
    )
    complete = tool.complete_with_result

    def crash_before_completion(_run_ref: str, _result_ref: str):
        raise RuntimeError("simulated process exit before Run completion")

    monkeypatch.setattr(tool, "complete_with_result", crash_before_completion)
    with pytest.raises(RuntimeError, match="simulated process exit"):
        tool.publish_result(run_ref, draft)
    first_results = ResultStore(database).audit().available
    assert len(first_results) == 1

    monkeypatch.setattr(tool, "complete_with_result", complete)
    completed = tool.publish_result(run_ref, draft)

    _assert_valid(completed)
    assert completed["state"] == "completed"
    assert ResultStore(database).audit().available == first_results
    assert completed["result"]["ref"] == first_results[0]


def test_seal_is_not_a_public_run_action(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)

    response = tool.run(
        {
            "action": "seal",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:public-seal",
        }
    )
    assert response["error"]["code"] == "invalid_request"


def test_corrupt_result_fails_without_publishing_on_the_run(tmp_path: Path) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:corrupt",
        }
    )
    result = _sealed_image_result(tmp_path, database, accounting)
    result.path.chmod(0o644)
    result.path.write_bytes(b"corrupt")

    failed = tool.complete_with_result(str(started["run_ref"]), result.result_ref)
    _assert_valid(failed)
    assert failed["state"] == "failed"
    assert failed["reason"]["code"] == "result_untrusted"
    assert "result" not in failed


def test_prepare_execution_never_rebinds_to_a_newer_accounting_run(
    tmp_path: Path,
) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    source = tmp_path / "source"
    source.mkdir()
    first_accounting = accounting.start_or_resume_run("dataset-a", source)
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:fixed-accounting-binding",
        }
    )
    accounting.process_run(first_accounting)
    second_accounting = accounting.start_or_resume_run("dataset-a", source)
    assert second_accounting != first_accounting

    tool.prepare_execution(str(started["run_ref"]), dataset_id="dataset-a")

    assert tool._store.get(str(started["run_ref"]))["accounting_run_id"] == (
        first_accounting
    )


def test_progress_rejects_nonclosing_or_derived_counts(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:progress",
        }
    )
    run_ref = str(started["run_ref"])
    valid = tool.record_progress(
        run_ref,
        {
            "discovered": 5,
            "accounted": 4,
            "usable": 2,
            "exceptional": 1,
            "unresolved": 1,
        },
    )
    _assert_valid(valid)

    try:
        tool.record_progress(
            run_ref,
            {
                "discovered": 5,
                "accounted": 4,
                "usable": 4,
                "exceptional": 1,
                "unresolved": 0,
            },
        )
    except ValueError as error:
        assert "exceed" in str(error)
    else:
        raise AssertionError("non-closing progress was accepted")


def test_status_projects_work_progress_while_source_accounting_is_unchanged(
    tmp_path: Path,
) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a")
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (20, 20), "blue").save(source / "reused.jpg")
    first_run = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(first_run)
    ImageRenditionProducer(database).produce(first_run, Path("reused.jpg"))

    Image.new("RGB", (20, 20), "green").save(source / "new.jpg")
    second_run = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(second_run)
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:visible-work",
        }
    )
    run_ref = str(started["run_ref"])
    tool.bind_working_run(run_ref, second_run)
    tool.record_phase(run_ref, "renditions", total=2)
    before = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )

    reused = ImageRenditionProducer(database).produce(second_run, Path("reused.jpg"))
    after_reuse = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    created = ImageRenditionProducer(database).produce(second_run, Path("new.jpg"))
    after_create = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )

    assert reused.reused is True
    assert created.reused is False
    assert before["progress"]["total"] is None
    assert after_reuse["progress"]["processed"] == 1
    assert after_reuse["progress"]["total"] == 1
    assert after_create["progress"]["processed"] == 2
    assert after_create["progress"]["total"] == 2
    assert after_create["progress"]["phase"] == "renditions"
    assert (
        after_create["progress"]["last_progress_at"]
        >= after_reuse["progress"]["last_progress_at"]
    )
    assert any(
        issue["code"] == "progress_scope_changed" for issue in after_create["issues"]
    )
    details = tool.run(
        {
            "action": "status",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": run_ref,
            "include": ["accounting", "diagnostics"],
        }
    )
    assert details["accounting"]["accounted"] == 2
    assert details["diagnostics"]["work"] == {
        "phase": "renditions",
        "unit": "logical_operation",
        "completed": 1,
        "reused": 1,
        "failed": 0,
        "remaining": 0,
        "total": 2,
    }


def test_status_distinguishes_recent_work_no_progress_and_stale_worker(
    tmp_path: Path,
) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    clock = _FakeClock()
    tool = PrecheckRunTool(
        database,
        clock=clock,
        heartbeat_interval_seconds=10,
        worker_stale_seconds=30,
        progress_stale_seconds=20,
    )
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:liveness",
        }
    )
    run_ref = str(started["run_ref"])
    tool.record_phase(run_ref, "metadata", total=3)
    assert tool._store.claim_execution_worker(
        run_ref, "worker:test", stale_after=timedelta(seconds=30)
    )
    assert not tool._store.claim_execution_worker(
        run_ref, "worker:other", stale_after=timedelta(seconds=30)
    )

    working = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    clock.advance(21)
    assert tool._store.heartbeat_execution_worker(run_ref, "worker:test")
    quiet = tool.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    clock.advance(31)
    reopened = PrecheckRunTool(
        database,
        clock=clock,
        heartbeat_interval_seconds=10,
        worker_stale_seconds=30,
        progress_stale_seconds=20,
    )
    stale = reopened.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )

    for response in (working, quiet, stale):
        _assert_valid(response)
    assert "reason" not in working
    assert quiet["reason"]["code"] == "no_recent_progress"
    assert stale["state"] == "running"
    assert stale["reason"]["code"] == "suspected_stalled"
    assert stale["reason"]["code"] == "suspected_stalled"
    assert set(stale["allowed_actions"]) == {"resume", "cancel"}
    assert (
        stale["progress"]["last_progress_at"]
        == (working["progress"]["last_progress_at"])
    )
    assert reopened._store.claim_execution_worker(
        run_ref, "worker:replacement", stale_after=timedelta(seconds=30)
    )
    recovered = reopened.run(
        {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
    )
    _assert_valid(recovered)
    assert reopened._store.get(run_ref)["run_ref"] == run_ref
    assert recovered["reason"]["code"] == "no_recent_progress"


def test_status_recovers_a_legacy_plain_phase_checkpoint(tmp_path: Path) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:legacy-checkpoint",
        }
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE precheck_runs SET execution_checkpoint = ? WHERE run_ref = ?",
            ("metadata:complete", started["run_ref"]),
        )

    status = tool.run(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "status",
            "run_ref": started["run_ref"],
        }
    )

    _assert_valid(status)
    assert status["progress"]["phase"] == "metadata"
    assert status["progress"]["processed"] == status["progress"]["total"] == 0


def test_database_lock_returns_temporary_failure_without_state_change(
    tmp_path: Path,
) -> None:
    database, _accounting = _workspace(tmp_path, "dataset-a")
    tool = PrecheckRunTool(database, sqlite_timeout=0.01)
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:locked",
        }
    )
    run_ref = str(started["run_ref"])

    with sqlite3.connect(database, timeout=0) as blocker:
        blocker.execute("BEGIN EXCLUSIVE")
        response = tool.run(
            {"dataset_ref": "dataset:dataset-a", "action": "pause", "run_ref": run_ref}
        )

    _assert_valid(response)
    assert response["error"]["code"] == "operation_failed"
    assert (
        tool.run(
            {"dataset_ref": "dataset:dataset-a", "action": "status", "run_ref": run_ref}
        )["state"]
        == "running"
    )


def test_bound_accounting_progress_and_blocking_are_projected(tmp_path: Path) -> None:
    database, accounting = _workspace(tmp_path, "dataset-a", "dataset-b")
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (20, 20), "blue").save(source / "photo-a.jpg")
    Image.new("RGB", (20, 20), "green").save(source / "photo-b.jpg")
    accounting_run = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(accounting_run)
    tool = PrecheckRunTool(database)
    public = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:accounting-progress",
        }
    )

    status = tool.bind_working_run(str(public["run_ref"]), accounting_run)

    _assert_valid(status)
    details = tool.run(
        {
            "action": "status",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": public["run_ref"],
            "include": ["accounting"],
        }
    )
    assert details["accounting"] == {
        "discovered": 2,
        "accounted": 2,
        "scope_condition": [
            {"scope": "source_media", "condition": "unresolved", "count": 2}
        ],
    }

    other_source = tmp_path / "other-source"
    other_source.mkdir()
    other_run = accounting.start_or_resume_run("dataset-b", other_source)
    accounting.process_run(other_run)
    with pytest.raises(ValueError, match="different Dataset"):
        tool.bind_working_run(str(public["run_ref"]), other_run)

    accounting.register_dataset("dataset-c")
    missing_source = tmp_path / "missing-source"
    blocked_accounting = accounting.start_or_resume_run("dataset-c", missing_source)
    accounting.process_run(blocked_accounting)
    blocked_public = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-c",
            "request_id": "request:accounting-blocked",
        }
    )
    blocked = tool.bind_working_run(str(blocked_public["run_ref"]), blocked_accounting)
    _assert_valid(blocked)
    assert blocked["state"] == "blocked"
    assert blocked["reason"]["code"] == "root_unavailable"
