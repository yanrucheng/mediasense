from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import errno
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import tracemalloc
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

import mediasense.apply.filesystem as apply_filesystem
from mediasense.apply import (
    ApplyExecutor,
    LocalFilesystem,
    ApplyPreparationError,
    ApplyReceiptReader,
    ApplyRunStore,
    ApplyRunTool,
    ApplyConfirmationContext,
    ReceiptError,
    ReceiptStore,
)
from mediasense.apply.filesystem import (
    EffectObservation,
    FilesystemEffectError,
    MetadataDiscrepancy,
    canonical_identity,
)
from mediasense.apply.receipt import content_identity
from test_apply_preparation import _fixture, _plan, _prepare, _tree_facts


ROOT = Path(__file__).parents[1]
APPLY_SPEC = ROOT / "docs" / "spec" / "contract/apply"
FROZEN_PLAN_SCHEMA = (
    ROOT
    / "docs"
    / "spec"
    / "contract/frozen-plan"
    / "frozen-plan.schema.json"
)


def _receipt_with_operations(item_count: int) -> dict[str, object]:
    receipt = json.loads((APPLY_SPEC / "receipt.mock.json").read_text(encoding="utf-8"))
    template = receipt["sealed_content"]["operation_ledger"]["items"][0]
    items = []
    for index in range(item_count):
        item = json.loads(json.dumps(template))
        item["source_item_ref"] = f"source-item:scale-{index:06d}"
        item["source_before"] = f"/fixture/source/{index:06d}.jpg"
        item["intended_target"] = f"/fixture/target/{index:06d}.jpg"
        items.append(item)
    content = receipt["sealed_content"]
    content["receipt_ref"] = "apply-receipt:scale"
    content["run_ref"] = "apply-run:scale"
    content["operation_ledger"] = {"kind": "inline", "items": items}
    content["accounting"] = {
        "plan_scope_items": item_count,
        "materialization_operations": item_count,
        "retained_without_effect": 0,
        "excluded_without_effect": 0,
        "completed_and_verified": item_count,
        "failed": 0,
        "refused": 0,
        "not_attempted": 0,
        "indeterminate": 0,
    }
    content["verification"]["planned_targets_present"] = item_count
    content["verification"]["original_locations_absent"] = item_count
    receipt["seal"]["content_identity"] = content_identity(content)
    return receipt


def _executor(
    tmp_path: Path,
    store: ApplyRunStore,
    *,
    fault_hook=None,
) -> ApplyExecutor:
    return ApplyExecutor(
        store,
        ReceiptStore(tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"),
        fault_hook=fault_hook,
        clock=lambda: datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
    )


def _execute_prepared(tmp_path: Path, *, fault_hook=None):
    store, run, source, destination, files, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store, fault_hook=fault_hook)
    response = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-1",
        authorization_binding="test:trusted-human",
    )
    return store, executor, response, source, destination, files


def test_same_filesystem_move_closes_with_schema_valid_receipt(tmp_path: Path) -> None:
    store, executor, status, source, destination, files = _execute_prepared(tmp_path)

    assert status["state"] == "closed"
    assert not (source / "a.jpg").exists()
    assert not (source / "b.jpg").exists()
    assert (source / "c.jpg").read_bytes() == files["c.jpg"]
    assert (destination / "Media" / "Trip" / "a.jpg").read_bytes() == files["a.jpg"]
    assert (destination / "Media" / "Trip" / "renamed.jpg").read_bytes() == files[
        "b.jpg"
    ]

    receipt_ref = status["published_receipt"]["receipt_ref"]
    receipt = executor.receipt_store.read(receipt_ref)
    schema = json.loads(
        (APPLY_SPEC / "apply-receipt.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(receipt)
    content = receipt["sealed_content"]
    assert content["completion"] == "complete"
    assert content["closure"] == "automatic"
    assert content["accounting"] == {
        "plan_scope_items": 3,
        "materialization_operations": 2,
        "retained_without_effect": 1,
        "excluded_without_effect": 0,
        "completed_and_verified": 2,
        "failed": 0,
        "refused": 0,
        "not_attempted": 0,
        "indeterminate": 0,
    }
    assert (
        store.status(status["run_ref"])["published_receipt"]
        == status["published_receipt"]
    )


def test_effect_boundary_source_drift_fails_without_moving_item(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    (source / "a.jpg").write_bytes(b"changed-after-prepare")
    executor = _executor(tmp_path, store)

    status = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-drift",
        authorization_binding="test:trusted-human",
    )

    assert status["state"] == "needs_attention"
    assert (source / "a.jpg").read_bytes() == b"changed-after-prepare"
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()


def test_target_collision_after_prepare_never_overwrites(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    target = destination / "Media" / "Trip" / "a.jpg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"unrelated")
    executor = _executor(tmp_path, store)

    status = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-collision",
        authorization_binding="test:trusted-human",
    )

    assert status["state"] == "needs_attention"
    assert target.read_bytes() == b"unrelated"
    assert (source / "a.jpg").exists()


def test_source_object_replaced_with_same_bytes_is_refused(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    original = source / "a.jpg"
    replacement = source / "replacement"
    replacement.write_bytes(original.read_bytes())
    original.unlink()
    replacement.rename(original)
    executor = _executor(tmp_path, store)

    status = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-stale-object",
        authorization_binding="test:trusted-human",
    )

    assert status["state"] == "needs_attention"
    assert original.exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()


def test_source_volume_disappears_before_effect_and_stops_run(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    detached = tmp_path / "detached-source"
    source.rename(detached)
    executor = _executor(tmp_path, store)

    status = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-source-disconnected",
        authorization_binding="test:trusted-human",
    )

    assert status["state"] == "needs_attention"
    assert status["progress"]["indeterminate"] == 1
    assert any(
        reason["code"] == "source_root_unavailable" for reason in status["reasons"]
    )
    assert (detached / "a.jpg").exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()

    detached.rename(source)
    executor.resume(run.run_ref)
    executor.advance(run.run_ref)
    closed = store.status(run.run_ref)
    assert closed["state"] == "closed"
    receipt = executor.receipt_store.read(closed["published_receipt"]["receipt_ref"])
    recovered_item = next(
        item
        for item in receipt["sealed_content"]["operation_ledger"]["items"]
        if item["source_item_ref"] == "source-item:a"
    )
    assert recovered_item["result"] == "completed_and_verified"
    assert "reason" not in recovered_item


def test_destination_rebind_at_same_path_stops_before_effect(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    detached = tmp_path / "detached-destination"
    destination.rename(detached)
    destination.mkdir()
    executor = _executor(tmp_path, store)

    status = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-destination-rebound",
        authorization_binding="test:trusted-human",
    )

    assert status["state"] == "needs_attention"
    assert any(reason["code"] == "destination_rebound" for reason in status["reasons"])
    assert (source / "a.jpg").exists()
    assert not (destination / "Media").exists()

    destination.rmdir()
    detached.rename(destination)
    executor.resume(run.run_ref)
    executor.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "closed"


def test_crash_after_move_reconciles_without_second_effect(tmp_path: Path) -> None:
    crashed = False

    def fault(point: str, source_item_ref: str | None) -> None:
        nonlocal crashed
        if (
            point == "after_effect_before_record"
            and source_item_ref == "source-item:a"
            and not crashed
        ):
            crashed = True
            raise RuntimeError("simulated process crash")

    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store, fault_hook=fault)
    with pytest.raises(RuntimeError, match="simulated process crash"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-crash",
            authorization_binding="test:trusted-human",
        )
    assert not (source / "a.jpg").exists()
    assert (destination / "Media" / "Trip" / "a.jpg").exists()

    recovered_executor = _executor(tmp_path, store)
    accepted = recovered_executor.resume(run.run_ref)
    assert accepted["target_state"] == "executing"
    recovered_executor.advance(run.run_ref)
    recovered = store.status(run.run_ref)
    assert recovered["state"] == "closed"
    receipt = _executor(tmp_path, store).receipt_store.read(
        recovered["published_receipt"]["receipt_ref"]
    )
    recovered_operations = [
        item
        for item in receipt["sealed_content"]["operation_ledger"]["items"]
        if item.get("recovery_fact")
    ]
    assert [item["source_item_ref"] for item in recovered_operations] == [
        "source-item:a"
    ]


def test_crash_after_intent_retries_from_verified_source(tmp_path: Path) -> None:
    crashed = False

    def fault(point: str, source_item_ref: str | None) -> None:
        nonlocal crashed
        if (
            point == "after_intent"
            and source_item_ref == "source-item:a"
            and not crashed
        ):
            crashed = True
            raise RuntimeError("simulated pre-effect crash")

    store, run, source, destination, *_rest = _prepare(tmp_path)
    with pytest.raises(RuntimeError, match="pre-effect crash"):
        _executor(tmp_path, store, fault_hook=fault).execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-intent-crash",
            authorization_binding="test:trusted-human",
        )
    assert (source / "a.jpg").exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()

    recovered_executor = _executor(tmp_path, store)
    recovered_executor.resume(run.run_ref)
    recovered_executor.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "closed"


def test_crash_after_directory_effect_recovers_conservatively(
    tmp_path: Path,
) -> None:
    crashed = False

    def fault(point: str, _source_item_ref: str | None) -> None:
        nonlocal crashed
        if point == "after_directory_effect_before_record" and not crashed:
            crashed = True
            raise RuntimeError("simulated directory-intent crash")

    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store, fault_hook=fault)
    with pytest.raises(RuntimeError, match="directory-intent crash"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-directory-crash",
            authorization_binding="test:trusted-human",
        )
    assert (source / "a.jpg").exists()
    assert (destination / "Media").exists()

    recovered_executor = _executor(tmp_path, store)
    recovered_executor.resume(run.run_ref)
    recovered_executor.advance(run.run_ref)
    recovered = store.status(run.run_ref)
    assert recovered["state"] == "closed"
    receipt = _executor(tmp_path, store).receipt_store.read(
        recovered["published_receipt"]["receipt_ref"]
    )
    created = {
        item["path"] for item in receipt["sealed_content"]["created_directories"]
    }
    assert str(destination / "Media") not in created


def test_crash_after_directory_intent_retries_without_unrecorded_effect(
    tmp_path: Path,
) -> None:
    crashed = False

    def fault(point: str, _source_item_ref: str | None) -> None:
        nonlocal crashed
        if point == "after_directory_intent" and not crashed:
            crashed = True
            raise RuntimeError("simulated pre-directory crash")

    store, run, source, destination, *_rest = _prepare(tmp_path)
    with pytest.raises(RuntimeError, match="pre-directory crash"):
        _executor(tmp_path, store, fault_hook=fault).execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-directory-intent-crash",
            authorization_binding="test:trusted-human",
        )
    assert (source / "a.jpg").exists()
    assert not (destination / "Media").exists()

    recovered = _executor(tmp_path, store)
    recovered.resume(run.run_ref)
    recovered.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "closed"


def test_execute_retry_returns_same_closed_receipt(tmp_path: Path) -> None:
    store, executor, status, *_rest = _execute_prepared(tmp_path)
    run = store.get_run(status["run_ref"])
    retried = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-1",
        authorization_binding="test:trusted-human",
    )
    assert retried["published_receipt"] == status["published_receipt"]


def test_authorize_acknowledges_without_claiming_file_effect(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store)

    accepted = executor.authorize(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:authorize-only",
        authorization_binding="test:trusted-human",
    )

    assert accepted == {
        "outcome": "accepted",
        "action": "execute",
        "run_ref": run.run_ref,
        "observed_state": "ready_for_authorization",
        "target_state": "executing",
    }
    assert (source / "a.jpg").exists()
    assert not (destination / "Media").exists()
    assert store.get_run(run.run_ref).state == "executing"


def test_post_authorization_cancel_publishes_incomplete_receipt(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store)
    executor.authorize(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:authorize-cancel",
        authorization_binding="test:trusted-human",
    )

    accepted = executor.cancel(run.run_ref)
    assert accepted["target_state"] == "verifying"
    executor.advance(run.run_ref)
    status = store.status(run.run_ref)
    assert status["state"] == "closed"
    assert status["published_receipt"]["completion"] == "incomplete"
    assert status["published_receipt"]["closure"] == "human_cancelled"
    assert (source / "a.jpg").exists()
    assert not (destination / "Media").exists()


def test_cancel_after_one_completed_effect_seals_partial_reality(
    tmp_path: Path,
) -> None:
    cancelled = False
    executor: ApplyExecutor

    def fault(point: str, source_item_ref: str | None) -> None:
        nonlocal cancelled
        if (
            point == "after_effect_before_record"
            and source_item_ref == "source-item:a"
            and not cancelled
        ):
            cancelled = True
            executor.pause(executor_run_ref)

    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor_run_ref = run.run_ref
    executor = _executor(tmp_path, store, fault_hook=fault)
    first = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-partial-cancel",
        authorization_binding="test:trusted-human",
    )
    assert first["state"] == "paused"
    accepted = executor.cancel(run.run_ref)
    assert accepted["target_state"] == "verifying"
    executor.advance(run.run_ref)
    status = store.status(run.run_ref)
    assert status["state"] == "closed"
    assert status["published_receipt"]["completion"] == "incomplete"
    assert status["published_receipt"]["completed_and_verified"] == 1
    assert not (source / "a.jpg").exists()
    assert (source / "b.jpg").exists()
    assert (destination / "Media" / "Trip" / "a.jpg").exists()


def test_execute_rejects_stale_authorization_without_effect(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store)

    with pytest.raises(ApplyPreparationError, match="content identity mismatch"):
        executor.authorize(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity="sha256:stale",
            request_id="request:execute-1",
            authorization_binding="test:trusted-human",
        )
    assert (source / "a.jpg").exists()
    assert not (destination / "Media").exists()


def test_crash_after_receipt_publish_recovers_same_receipt(tmp_path: Path) -> None:
    crashed = False

    def fault(point: str, _source_item_ref: str | None) -> None:
        nonlocal crashed
        if point == "after_receipt_publish_before_close" and not crashed:
            crashed = True
            raise RuntimeError("simulated receipt publication crash")

    store, run, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store, fault_hook=fault)
    with pytest.raises(RuntimeError, match="receipt publication crash"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-receipt-crash",
            authorization_binding="test:trusted-human",
        )

    recovered_executor = _executor(tmp_path, store)
    recovered_executor.resume(run.run_ref)
    recovered_executor.advance(run.run_ref)
    recovered = store.status(run.run_ref)
    assert recovered["state"] == "closed"
    assert recovered["published_receipt"]["receipt_ref"].startswith("apply-receipt:")


def test_receipt_store_failure_after_reservation_recovers_same_receipt(
    tmp_path: Path,
) -> None:
    store, run, *_rest = _prepare(tmp_path)
    receipt_root = tmp_path / "receipts"
    receipt_root.write_text("controlled path obstruction", encoding="utf-8")
    receipt_store = ReceiptStore(receipt_root, APPLY_SPEC / "apply-receipt.schema.json")
    executor = ApplyExecutor(
        store,
        receipt_store,
        clock=lambda: datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
    )
    with pytest.raises(ReceiptError, match="Receipt root"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-publication-reservation-crash",
            authorization_binding="test:trusted-human",
        )
    assert store.status(run.run_ref)["state"] == "verifying"

    receipt_root.unlink()
    recovered = ApplyExecutor(
        store,
        ReceiptStore(tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"),
        clock=lambda: datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
    )
    recovered.resume(run.run_ref)
    recovered.advance(run.run_ref)
    status = store.status(run.run_ref)
    assert status["state"] == "closed"
    assert status["published_receipt"]["receipt_ref"].startswith("apply-receipt:")


def test_restart_reopens_existing_run_store_and_recovers(tmp_path: Path) -> None:
    crashed = False

    def fault(point: str, source_item_ref: str | None) -> None:
        nonlocal crashed
        if (
            point == "after_effect_before_record"
            and source_item_ref == "source-item:a"
            and not crashed
        ):
            crashed = True
            raise RuntimeError("simulated restart")

    store, run, *_rest = _prepare(tmp_path)
    with pytest.raises(RuntimeError, match="simulated restart"):
        _executor(tmp_path, store, fault_hook=fault).execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-restart",
            authorization_binding="test:trusted-human",
        )
    reopened = ApplyRunStore(store.database_path)
    executor = _executor(tmp_path, reopened)
    executor.resume(run.run_ref)
    executor.advance(run.run_ref)
    assert reopened.status(run.run_ref)["state"] == "closed"


def test_receipt_publication_retry_refuses_conflicting_artifact(tmp_path: Path) -> None:
    store, run, *_rest = _prepare(tmp_path)
    receipt_path = (
        tmp_path / "receipts" / run.run_ref.split(":", 1)[-1] / "receipt.json"
    )
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text('{"unrelated":true}\n', encoding="utf-8")
    executor = _executor(tmp_path, store)

    with pytest.raises(Exception, match="conflict"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-receipt-conflict",
            authorization_binding="test:trusted-human",
        )
    assert store.status(run.run_ref)["state"] == "verifying"


def test_concurrent_executor_is_refused_without_effect(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store)
    executor.authorize(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-concurrent",
        authorization_binding="test:trusted-human",
    )
    token = canonical_identity(run.run_ref).removeprefix("sha256:")
    lock_path = store.database_path.parent / "locks" / f"{token}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl,sys; "
                "f=open(sys.argv[1],'a+b'); "
                "fcntl.flock(f.fileno(),fcntl.LOCK_EX); "
                "print('ready',flush=True); sys.stdin.read(1)"
            ),
            str(lock_path),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "ready"
        with pytest.raises(Exception, match="another executor"):
            executor.advance(run.run_ref)
    finally:
        assert holder.stdin is not None
        holder.stdin.write("x")
        holder.stdin.flush()
        holder.wait(timeout=5)
    assert (source / "a.jpg").exists()
    assert not (destination / "Media").exists()


def test_effect_reservation_prevents_overlap_across_run_stores(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source")
    target_parent = tmp_path / "target"
    target_parent.mkdir()
    target = target_parent / "source.jpg"
    observed = source.stat()
    source_key = f"object:{observed.st_dev}:{observed.st_ino}"
    token = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    lock_root = (
        Path(apply_filesystem.tempfile.gettempdir())
        / f"mediasense-apply-locks-{apply_filesystem.os.getuid()}"
    )
    lock_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import fcntl,sys; "
                "f=open(sys.argv[1],'a+b'); "
                "fcntl.flock(f.fileno(),fcntl.LOCK_EX); "
                "print('ready',flush=True); sys.stdin.read(1)"
            ),
            str(lock_root / f"{token}.lock"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "ready"
        with pytest.raises(FilesystemEffectError, match="overlapping") as error:
            LocalFilesystem().move(
                source=source,
                target=target,
                expected_digest="sha256:" + hashlib.sha256(b"source").hexdigest(),
                expected_size=6,
                route="same_filesystem_atomic_move",
                temporary_path=None,
                expected_source_stat=(
                    observed.st_dev,
                    observed.st_ino,
                    observed.st_mtime_ns,
                ),
            )
        assert error.value.global_risk is True
    finally:
        assert holder.stdin is not None
        holder.stdin.write("x")
        holder.stdin.flush()
        holder.wait(timeout=5)
    assert source.read_bytes() == b"source"
    assert not target.exists()


def test_receipt_read_is_bounded_and_cursor_bound(tmp_path: Path) -> None:
    _store, executor, status, *_rest = _execute_prepared(tmp_path)
    receipt_ref = status["published_receipt"]["receipt_ref"]
    reader = ApplyReceiptReader(
        executor.receipt_store, APPLY_SPEC / "apply-read.tool.json"
    )

    inspected = reader.read({"receipt_ref": receipt_ref, "action": "inspect"})
    assert inspected["receipt"]["completion"] == "complete"
    first = reader.read(
        {
            "receipt_ref": receipt_ref,
            "action": "traverse",
            "section": "operations",
            "page": {"limit": 1},
        }
    )
    assert first["page"]["returned"] == 1
    assert first["page"]["complete"] is False
    second = reader.read(
        {
            "receipt_ref": receipt_ref,
            "action": "traverse",
            "section": "operations",
            "page": {"limit": 1, "cursor": first["page"]["next_cursor"]},
        }
    )
    assert second["page"]["complete"] is True

    output_validator = Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-read.tool.json").read_text())["outputSchema"]
    )
    wrong_section = reader.read(
        {
            "receipt_ref": receipt_ref,
            "action": "traverse",
            "section": "created_directories",
            "page": {"cursor": first["page"]["next_cursor"]},
        }
    )
    wrong_filter = reader.read(
        {
            "receipt_ref": receipt_ref,
            "action": "traverse",
            "section": "operations",
            "filter": {"source_item_ref": "source-item:b"},
            "page": {"cursor": first["page"]["next_cursor"]},
        }
    )
    malformed = reader.read(
        {
            "receipt_ref": receipt_ref,
            "action": "traverse",
            "section": "operations",
            "page": {"cursor": "not-an-opaque-cursor"},
        }
    )
    for response in (wrong_section, wrong_filter, malformed):
        assert response["outcome"] == "error"
        assert response["error"]["code"] == "invalid_cursor"
        output_validator.validate(response)


@pytest.mark.parametrize(
    "payload",
    [
        {"receipt_ref": "apply-receipt:missing", "action": "delete"},
        {
            "receipt_ref": "apply-receipt:missing",
            "action": "traverse",
            "section": "unknown",
        },
        {
            "receipt_ref": "apply-receipt:missing",
            "action": "traverse",
            "section": "operations",
            "page": {"limit": 0},
        },
        {
            "receipt_ref": "apply-receipt:missing",
            "action": "traverse",
            "section": "created_directories",
            "filter": {"source_item_ref": "source-item:a"},
        },
    ],
)
def test_apply_read_invalid_requests_return_schema_valid_errors(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    store = ReceiptStore(
        tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"
    )
    reader = ApplyReceiptReader(store, APPLY_SPEC / "apply-read.tool.json")
    output_validator = Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-read.tool.json").read_text())["outputSchema"]
    )

    response = reader.read(payload)

    assert response["outcome"] == "error"
    assert response["error"]["code"] == "invalid_request"
    output_validator.validate(response)


def test_apply_read_missing_receipt_returns_schema_valid_error(tmp_path: Path) -> None:
    store = ReceiptStore(
        tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"
    )
    reader = ApplyReceiptReader(store, APPLY_SPEC / "apply-read.tool.json")
    output_validator = Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-read.tool.json").read_text())["outputSchema"]
    )

    response = reader.read(
        {"receipt_ref": "apply-receipt:missing", "action": "inspect"}
    )

    assert response["outcome"] == "error"
    assert response["error"]["code"] == "receipt_not_found"
    output_validator.validate(response)


def test_apply_read_corrupt_receipt_returns_schema_valid_error(tmp_path: Path) -> None:
    store = ReceiptStore(
        tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"
    )
    artifact = store.artifact_path("apply-receipt:corrupt")
    artifact.mkdir(parents=True)
    (artifact / "receipt.json").write_text("{not-json", encoding="utf-8")
    reader = ApplyReceiptReader(store, APPLY_SPEC / "apply-read.tool.json")
    output_validator = Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-read.tool.json").read_text())["outputSchema"]
    )

    response = reader.read(
        {"receipt_ref": "apply-receipt:corrupt", "action": "inspect"}
    )

    assert response["outcome"] == "error"
    assert response["error"]["code"] == "receipt_untrusted"
    output_validator.validate(response)


def test_large_receipt_is_segmented_and_read_without_exposing_segments(
    tmp_path: Path,
) -> None:
    store = ReceiptStore(
        tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"
    )
    package = store.prepare(_receipt_with_operations(1_001))
    ledger = package.document["sealed_content"]["operation_ledger"]
    assert ledger == {
        "kind": "immutable_segments",
        "coverage": "all_materialization_operations",
        "item_count": 1_001,
        "segment_count": 2,
        "content_identity": ledger["content_identity"],
    }
    store.publish(package)

    restarted = ReceiptStore(
        tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"
    )
    reader = ApplyReceiptReader(restarted, APPLY_SPEC / "apply-read.tool.json")
    first = reader.read(
        {
            "receipt_ref": "apply-receipt:scale",
            "action": "traverse",
            "section": "operations",
            "page": {"limit": 1_000},
        }
    )
    assert first["page"] == {
        "returned": 1_000,
        "total": 1_001,
        "complete": False,
        "next_cursor": first["page"]["next_cursor"],
    }
    assert "operations-" not in first["page"]["next_cursor"]
    second = reader.read(
        {
            "receipt_ref": "apply-receipt:scale",
            "action": "traverse",
            "section": "operations",
            "page": {"limit": 1_000, "cursor": first["page"]["next_cursor"]},
        }
    )
    assert second["page"] == {"returned": 1, "total": 1_001, "complete": True}
    assert second["items"][0]["source_item_ref"] == "source-item:scale-001000"

    segment = restarted.artifact_path("apply-receipt:scale") / "operations-000001.json"
    segment.write_text('{"tampered":true}\n', encoding="utf-8")
    with pytest.raises(ReceiptError, match="segment integrity"):
        restarted.read("apply-receipt:scale")
    public_error = reader.read(
        {
            "receipt_ref": "apply-receipt:scale",
            "action": "traverse",
            "section": "operations",
        }
    )
    assert public_error["outcome"] == "error"
    assert public_error["error"]["code"] == "receipt_untrusted"
    Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-read.tool.json").read_text())["outputSchema"]
    ).validate(public_error)
    segment.unlink()
    unavailable = reader.read(
        {
            "receipt_ref": "apply-receipt:scale",
            "action": "traverse",
            "section": "operations",
        }
    )
    assert unavailable["outcome"] == "error"
    assert unavailable["error"]["code"] == "receipt_untrusted"
    Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-read.tool.json").read_text())["outputSchema"]
    ).validate(unavailable)


@pytest.mark.scale
def test_100k_receipt_publication_restart_and_read_are_bounded(tmp_path: Path) -> None:
    store = ReceiptStore(
        tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"
    )
    package = store.prepare(_receipt_with_operations(100_000))
    store.publish(package)
    del package

    restarted = ReceiptStore(
        tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"
    )
    reader = ApplyReceiptReader(restarted, APPLY_SPEC / "apply-read.tool.json")
    tracemalloc.start()
    page = reader.read(
        {
            "receipt_ref": "apply-receipt:scale",
            "action": "traverse",
            "section": "operations",
            "page": {"limit": 1_000},
        }
    )
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert page["page"]["returned"] == 1_000
    assert page["page"]["total"] == 100_000
    assert peak < 32 * 1024 * 1024


def test_whole_run_rewind_creates_new_run_and_receipt(tmp_path: Path) -> None:
    store, executor, forward_status, source, destination, files = _execute_prepared(
        tmp_path
    )
    forward_ref = forward_status["published_receipt"]["receipt_ref"]
    forward_receipt = executor.receipt_store.read(forward_ref)

    rewind = store.prepare_rewind(
        request_id="request:rewind-1",
        receipt=forward_receipt,
        now=datetime(2026, 8, 30, 1, 30, tzinfo=timezone.utc),
    )
    assert rewind.state == "ready_for_authorization"
    rewind_status = executor.execute(
        run_ref=rewind.run_ref,
        prepared_revision=rewind.prepared_revision,
        prepared_content_identity=rewind.prepared_content_identity,
        request_id="request:execute-rewind-1",
        authorization_binding="test:trusted-human-rewind",
    )
    assert rewind_status["state"] == "closed"
    assert (source / "a.jpg").read_bytes() == files["a.jpg"]
    assert (source / "b.jpg").read_bytes() == files["b.jpg"]
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()
    assert executor.receipt_store.read(forward_ref) == forward_receipt
    rewind_receipt = executor.receipt_store.read(
        rewind_status["published_receipt"]["receipt_ref"]
    )
    assert rewind_receipt["sealed_content"]["execution_binding"] == {
        "kind": "rewind",
        "rewind_of_receipt_ref": forward_ref,
        "restored_source_parents": [str(source)],
    }


def test_rewind_blocks_when_original_location_is_occupied(tmp_path: Path) -> None:
    store, executor, forward_status, source, *_rest = _execute_prepared(tmp_path)
    receipt = executor.receipt_store.read(
        forward_status["published_receipt"]["receipt_ref"]
    )
    (source / "a.jpg").write_bytes(b"unrelated")

    rewind = store.prepare_rewind(
        request_id="request:rewind-collision",
        receipt=receipt,
        now=datetime(2026, 8, 30, 1, 30, tzinfo=timezone.utc),
    )
    assert rewind.state == "blocked"
    assert (source / "a.jpg").read_bytes() == b"unrelated"

    (source / "a.jpg").unlink()
    resumed = store.resume_preparation(
        run_ref=rewind.run_ref,
        precheck_read=SimpleNamespace(name="mediasense.precheck.read"),
    )
    assert resumed.state == "ready_for_authorization"


def test_rewind_rejects_an_expired_window(tmp_path: Path) -> None:
    store, executor, forward_status, *_rest = _execute_prepared(tmp_path)
    receipt = executor.receipt_store.read(
        forward_status["published_receipt"]["receipt_ref"]
    )

    with pytest.raises(ApplyPreparationError, match="expired"):
        store.prepare_rewind(
            request_id="request:rewind-expired",
            receipt=receipt,
            now=datetime(2026, 8, 30, 2, 1, tzinfo=timezone.utc),
        )


def test_rewind_blocks_when_organized_content_drifted(tmp_path: Path) -> None:
    store, executor, forward_status, _source, destination, *_rest = _execute_prepared(
        tmp_path
    )
    receipt = executor.receipt_store.read(
        forward_status["published_receipt"]["receipt_ref"]
    )
    (destination / "Media" / "Trip" / "a.jpg").write_bytes(b"changed")

    rewind = store.prepare_rewind(
        request_id="request:rewind-drift",
        receipt=receipt,
        now=datetime(2026, 8, 30, 1, 30, tzinfo=timezone.utc),
    )
    assert rewind.state == "blocked"
    status = store.status(rewind.run_ref)
    assert any(
        reason["code"] == "rewind_source_unverifiable" for reason in status["reasons"]
    )


def test_rewind_receipt_is_available_through_public_read(tmp_path: Path) -> None:
    store, executor, forward_status, *_rest = _execute_prepared(tmp_path)
    forward_ref = forward_status["published_receipt"]["receipt_ref"]
    rewind = store.prepare_rewind(
        request_id="request:rewind-read",
        receipt=executor.receipt_store.read(forward_ref),
        now=datetime(2026, 8, 30, 1, 30, tzinfo=timezone.utc),
    )
    closed = executor.execute(
        run_ref=rewind.run_ref,
        prepared_revision=rewind.prepared_revision,
        prepared_content_identity=rewind.prepared_content_identity,
        request_id="request:execute-rewind-read",
        authorization_binding="test:trusted-human-rewind",
    )
    reader = ApplyReceiptReader(
        executor.receipt_store, APPLY_SPEC / "apply-read.tool.json"
    )
    response = reader.read(
        {
            "receipt_ref": closed["published_receipt"]["receipt_ref"],
            "action": "inspect",
        }
    )
    assert response["receipt"]["execution_binding"] == {
        "kind": "rewind",
        "rewind_of_receipt_ref": forward_ref,
        "restored_source_parents": response["receipt"]["execution_binding"][
            "restored_source_parents"
        ],
    }


def test_public_tool_requires_trusted_confirmation_and_returns_acceptance(
    tmp_path: Path,
) -> None:
    _store, run, _source, _destination, _files, reader, *_rest = _prepare(tmp_path)
    tool = ApplyRunTool(
        tmp_path / "tool-store",
        reader,
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    # Use the already prepared store to focus this test on the public action.
    tool.run_store = _store
    tool.executor.run_store = _store
    request = {
        "action": "execute",
        "run_ref": run.run_ref,
        "prepared_revision": run.prepared_revision,
        "prepared_content_identity": run.prepared_content_identity,
        "request_id": "request:tool-execute",
    }
    refused = tool.handle(request)
    assert refused["outcome"] == "error"
    assert refused["error"]["code"] == "access_denied"

    accepted = tool.handle(
        request,
        confirmation=ApplyConfirmationContext(
            principal_ref="human:test",
            confirmed_content_identity=run.prepared_content_identity,
            confirmed_at=datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
        ),
    )
    assert accepted["outcome"] == "accepted"
    assert accepted["target_state"] == "executing"
    assert _store.status(run.run_ref)["state"] == "executing"
    tool.run_pending(run.run_ref)
    assert _store.status(run.run_ref)["state"] == "closed"


def test_public_tool_prepare_status_execute_and_read_end_to_end(tmp_path: Path) -> None:
    source, destination, _state, files, precheck_read = _fixture(tmp_path)
    tool = ApplyRunTool(
        tmp_path / "apply-store",
        precheck_read,
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    prepared = tool.handle(
        {
            "action": "prepare",
            "request_id": "request:tool-prepare",
            "forward": {
                "frozen_plan": _plan(),
                "effect": "move_originals",
                "current_source_roots": [
                    {
                        "source_root_ref": "source-root:test",
                        "current_root": str(source),
                    }
                ],
                "destination_parent": str(destination),
            },
        }
    )
    assert prepared["state"] == "preparing"
    status = tool.handle({"action": "status", "run_ref": prepared["run_ref"]})
    assert status["state"] == "ready_for_authorization"

    accepted = tool.handle(
        {
            "action": "execute",
            "run_ref": prepared["run_ref"],
            "prepared_revision": status["prepared_revision"],
            "prepared_content_identity": status["prepared_content_identity"],
            "request_id": "request:tool-e2e-execute",
        },
        confirmation=ApplyConfirmationContext(
            principal_ref="human:test",
            confirmed_content_identity=status["prepared_content_identity"],
            confirmed_at=datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
        ),
    )
    assert accepted["target_state"] == "executing"
    closed = tool.run_pending(prepared["run_ref"])
    assert closed["state"] == "closed"
    assert (destination / "Media" / "Trip" / "a.jpg").read_bytes() == files["a.jpg"]
    receipt_reader = ApplyReceiptReader(
        tool.receipt_store, APPLY_SPEC / "apply-read.tool.json"
    )
    read = receipt_reader.read(
        {
            "receipt_ref": closed["published_receipt"]["receipt_ref"],
            "action": "inspect",
        }
    )
    assert read["receipt"]["completion"] == "complete"


@pytest.mark.parametrize("case", ["extra_field", "unknown_profile"])
def test_public_prepare_rejects_invalid_frozen_plan_with_schema_valid_error(
    tmp_path: Path, case: str
) -> None:
    source, destination, _state, _files, precheck_read = _fixture(tmp_path)
    plan = deepcopy(_plan())
    if case == "extra_field":
        plan["sealed_content"]["unexpected"] = "forbidden"
        identity = content_identity(plan["sealed_content"])
        plan["seal"]["content_identity"] = identity
        plan["seal"]["final_confirmation"]["confirmed_content_identity"] = identity
    else:
        plan["seal"]["encoding_profile"] = "future-profile"
    tool = ApplyRunTool(
        tmp_path / "apply-invalid-plan",
        precheck_read,
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    before_source = _tree_facts(source)
    before_destination = _tree_facts(destination)

    response = tool.handle(
        {
            "action": "prepare",
            "request_id": f"request:invalid-plan-{case}",
            "forward": {
                "frozen_plan": plan,
                "effect": "move_originals",
                "current_source_roots": [
                    {
                        "source_root_ref": "source-root:test",
                        "current_root": str(source),
                    }
                ],
                "destination_parent": str(destination),
            },
        }
    )

    assert response["outcome"] == "error"
    assert response["error"]["code"] == "invalid_request"
    Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-run.tool.json").read_text())["outputSchema"]
    ).validate(response)
    assert _tree_facts(source) == before_source
    assert _tree_facts(destination) == before_destination


def test_public_prepare_rejects_incomplete_result_resolution(tmp_path: Path) -> None:
    source, destination, _state, _files, base_reader = _fixture(tmp_path)
    source_before = _tree_facts(source)

    class IncompleteRead:
        name = "mediasense.precheck.read"

        def read(self, request: dict[str, object]) -> dict[str, object]:
            if request["operation"] == "resolve":
                source_set = request["source_set"]
                encoded_set = json.dumps(
                    source_set,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                return {
                    "outcome": "ok",
                    "result_ref": "precheck-result:prepare-test",
                    "operation": "resolve",
                    "resolution": {
                        "source_set_identity": "sha256:"
                        + hashlib.sha256(encoded_set).hexdigest(),
                        "membership_identity": "sha256:" + "0" * 64,
                        "ordering": "source_item_ref_ascending",
                        "total": 3,
                    },
                    "members": [
                        {
                            "source_item_ref": "source-item:a",
                            "locator": {"kind": "test"},
                            "scope": "source_media",
                            "condition": "usable",
                            "source_content_verification": {
                                "status": "not_checked"
                            },
                        }
                    ],
                    "page": {
                        "returned": 1,
                        "total": 3,
                        "complete": True,
                        "stop_reason": "complete",
                    },
                }
            return base_reader.read(request)

    plan = deepcopy(_plan())
    relation = {
        "kind": "precheck_relation",
        "origin": "precheck-result:prepare-test",
        "relation": "accounts_for",
        "direction": "outbound",
    }
    plan["sealed_content"]["scope"] = relation
    identity = content_identity(plan["sealed_content"])
    plan["seal"]["content_identity"] = identity
    plan["seal"]["final_confirmation"]["confirmed_content_identity"] = identity
    tool = ApplyRunTool(
        tmp_path / "apply-incomplete-traversal",
        IncompleteRead(),
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )

    response = tool.handle(
        {
            "action": "prepare",
            "request_id": "request:incomplete-traversal",
            "forward": {
                "frozen_plan": plan,
                "effect": "move_originals",
                "current_source_roots": [
                    {
                        "source_root_ref": "source-root:test",
                        "current_root": str(source),
                    }
                ],
                "destination_parent": str(destination),
            },
        }
    )

    assert response["outcome"] == "error"
    assert response["error"]["code"] == "invalid_request"
    Draft202012Validator(
        json.loads((APPLY_SPEC / "apply-run.tool.json").read_text())["outputSchema"]
    ).validate(response)
    assert _tree_facts(source) == source_before
    assert not (destination / "Media").exists()


def test_public_tool_rejects_mismatched_confirmation_identity(tmp_path: Path) -> None:
    store, run, _source, _destination, _files, reader, *_rest = _prepare(tmp_path)
    tool = ApplyRunTool(
        tmp_path / "tool-store",
        reader,
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    tool.run_store = store
    tool.executor.run_store = store
    response = tool.handle(
        {
            "action": "execute",
            "run_ref": run.run_ref,
            "prepared_revision": run.prepared_revision,
            "prepared_content_identity": run.prepared_content_identity,
            "request_id": "request:tool-mismatched-confirmation",
        },
        confirmation=ApplyConfirmationContext(
            principal_ref="human:test",
            confirmed_content_identity="sha256:not-the-prepared-content",
            confirmed_at=datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
        ),
    )
    assert response["outcome"] == "error"
    assert response["error"]["code"] == "access_denied"


def test_pause_and_resume_control_new_effects(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store)
    executor.authorize(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:authorize-pause",
        authorization_binding="test:trusted-human",
    )
    paused = executor.pause(run.run_ref)
    assert paused["target_state"] == "paused"
    executor.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "paused"
    assert (source / "a.jpg").exists()
    assert not (destination / "Media").exists()

    resumed = executor.resume(run.run_ref)
    assert resumed["target_state"] == "executing"
    executor.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "closed"


class _MetadataLossFilesystem:
    def move(self, **kwargs) -> EffectObservation:
        accepted = kwargs["accepted_discrepancies"]
        source = kwargs["source"]
        target = kwargs["target"]
        discrepancy = MetadataDiscrepancy("finder_tags", ["Family"], [])
        if source.name == "a.jpg" and accepted != (discrepancy,):
            return EffectObservation(
                status="metadata_loss",
                bytes_moved=kwargs["expected_size"],
                source_after="present",
                target_after="absent",
                verification_profile="cross_filesystem_content_and_metadata",
                verification_basis="Content matched; Finder tags differed.",
                temporary_path=str(target.with_suffix(".partial")),
                discrepancies=(discrepancy,),
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return EffectObservation(
            status="completed",
            bytes_moved=kwargs["expected_size"],
            source_after="absent",
            target_after="verified_present",
            verification_profile="cross_filesystem_content_and_metadata",
            verification_basis="Content matched and exact metadata loss was authorized.",
        )

    def reconcile(self, **_kwargs) -> EffectObservation:
        raise AssertionError("no reconciliation expected")


class _ChangingMetadataLossFilesystem:
    def __init__(self) -> None:
        self.calls = 0

    def move(self, **kwargs) -> EffectObservation:
        source = kwargs["source"]
        target = kwargs["target"]
        if source.name != "a.jpg":
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            return EffectObservation(
                status="completed",
                bytes_moved=kwargs["expected_size"],
                source_after="absent",
                target_after="verified_present",
                verification_profile="cross_filesystem_content_and_metadata",
                verification_basis="Content and metadata matched.",
            )
        self.calls += 1
        discrepancy = MetadataDiscrepancy(
            "finder_tags", ["Family"], ["Changed"] if self.calls > 1 else []
        )
        if kwargs["accepted_discrepancies"] != (discrepancy,):
            return EffectObservation(
                status="metadata_loss",
                bytes_moved=kwargs["expected_size"],
                source_after="present",
                target_after="absent",
                verification_profile="cross_filesystem_content_and_metadata",
                verification_basis="Content matched; current metadata loss differed.",
                temporary_path=str(target.with_suffix(".partial")),
                discrepancies=(discrepancy,),
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return EffectObservation(
            status="completed",
            bytes_moved=kwargs["expected_size"],
            source_after="absent",
            target_after="verified_present",
            verification_profile="cross_filesystem_content_and_metadata",
            verification_basis="The newly authorized metadata loss matched exactly.",
        )

    def reconcile(self, **_kwargs) -> EffectObservation:
        raise AssertionError("no reconciliation expected")


def test_cross_filesystem_metadata_loss_requires_new_exact_authorization(
    tmp_path: Path,
) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    with store._connect() as connection:
        connection.execute(
            "UPDATE runs SET execution_route = 'verified_cross_filesystem_transfer' WHERE run_ref = ?",
            (run.run_ref,),
        )
        connection.commit()
    executor = ApplyExecutor(
        store,
        ReceiptStore(tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"),
        filesystem=_MetadataLossFilesystem(),
        clock=lambda: datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
    )

    first = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-crossfs-first",
        authorization_binding="test:trusted-human",
    )
    assert first["state"] == "needs_attention"
    assert first["allowed_actions"] == ["execute", "cancel"]
    assert first["metadata_loss_authorization"]["source_deletion_blocked"] is True
    assert (source / "a.jpg").exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()
    disclosure = store.iter_metadata_discrepancies(run.run_ref)
    assert disclosure[0]["attribute"] == "finder_tags"

    second = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=first["prepared_revision"],
        prepared_content_identity=first["prepared_content_identity"],
        request_id="request:execute-crossfs-metadata-loss",
        authorization_binding="test:trusted-human-metadata-loss",
    )
    assert second["state"] == "closed"
    receipt = executor.receipt_store.read(second["published_receipt"]["receipt_ref"])
    preservation = receipt["sealed_content"]["metadata_preservation"]
    assert preservation["accepted_discrepancy_refs"]
    assert preservation["discrepancy_authorizations"][0]["binding"] == (
        "test:trusted-human-metadata-loss"
    )


def test_changed_metadata_loss_invalidates_the_previous_authorization(
    tmp_path: Path,
) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    with store._connect() as connection:
        connection.execute(
            "UPDATE runs SET execution_route = 'verified_cross_filesystem_transfer' WHERE run_ref = ?",
            (run.run_ref,),
        )
        connection.commit()
    executor = ApplyExecutor(
        store,
        ReceiptStore(tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"),
        filesystem=_ChangingMetadataLossFilesystem(),
        clock=lambda: datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
    )
    first = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:changing-metadata-first",
        authorization_binding="test:trusted-human",
    )
    second = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=first["prepared_revision"],
        prepared_content_identity=first["prepared_content_identity"],
        request_id="request:changing-metadata-second",
        authorization_binding="test:trusted-human-first-loss",
    )
    assert second["state"] == "needs_attention"
    assert second["prepared_content_identity"] != first["prepared_content_identity"]
    assert (source / "a.jpg").exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()

    closed = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=second["prepared_revision"],
        prepared_content_identity=second["prepared_content_identity"],
        request_id="request:changing-metadata-third",
        authorization_binding="test:trusted-human-current-loss",
    )
    assert closed["state"] == "closed"


class _OneFailureFilesystem:
    def __init__(self) -> None:
        self.failed = False

    def move(self, **kwargs) -> EffectObservation:
        source = kwargs["source"]
        target = kwargs["target"]
        if source.name == "a.jpg" and not self.failed:
            self.failed = True
            raise FilesystemEffectError("temporary_read_failure", "temporary failure")
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return EffectObservation(
            status="completed",
            bytes_moved=kwargs["expected_size"],
            source_after="absent",
            target_after="verified_present",
            verification_profile="same_filesystem_identity_and_location",
            verification_basis="Verified move.",
        )

    def reconcile(self, **_kwargs) -> EffectObservation:
        raise AssertionError("no intent remains")


def test_localized_failure_continues_independent_items_then_resumes(
    tmp_path: Path,
) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    filesystem = _OneFailureFilesystem()
    executor = ApplyExecutor(
        store,
        ReceiptStore(tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"),
        filesystem=filesystem,
        clock=lambda: datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
    )
    first = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-local-failure",
        authorization_binding="test:trusted-human",
    )
    assert first["state"] == "needs_attention"
    assert (source / "a.jpg").exists()
    assert (destination / "Media" / "Trip" / "renamed.jpg").exists()

    accepted = executor.resume(run.run_ref)
    assert accepted["target_state"] == "executing"
    executor.advance(run.run_ref)
    second = store.status(run.run_ref)
    assert second["state"] == "closed"
    assert not (source / "a.jpg").exists()


class _GlobalRiskFilesystem:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def move(self, **kwargs) -> EffectObservation:
        self.calls.append(kwargs["source"].name)
        raise FilesystemEffectError(
            "destination_rebound", "destination identity changed", global_risk=True
        )

    def reconcile(self, **_kwargs) -> EffectObservation:
        raise AssertionError("no reconciliation expected")


def test_global_risk_stops_before_issuing_any_later_effect(tmp_path: Path) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    filesystem = _GlobalRiskFilesystem()
    executor = ApplyExecutor(
        store,
        ReceiptStore(tmp_path / "receipts", APPLY_SPEC / "apply-receipt.schema.json"),
        filesystem=filesystem,
        clock=lambda: datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
    )
    status = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-global-risk",
        authorization_binding="test:trusted-human",
    )
    assert status["state"] == "needs_attention"
    assert filesystem.calls == ["a.jpg"]
    assert (source / "a.jpg").exists()
    assert (source / "b.jpg").exists()
    assert not (destination / "Media" / "Trip" / "renamed.jpg").exists()


def test_cross_filesystem_acl_is_blocked_before_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source")
    target_parent = tmp_path / "target"
    target_parent.mkdir()
    target = target_parent / "source.jpg"
    monkeypatch.setattr(apply_filesystem.sys, "platform", "darwin")
    monkeypatch.setattr(apply_filesystem, "has_nontrivial_acl", lambda _path: True)
    copied = False

    def unexpected_copy(_source: Path, _target: Path) -> None:
        nonlocal copied
        copied = True

    monkeypatch.setattr(apply_filesystem, "_copyfile_all_exclusive", unexpected_copy)
    digest = "sha256:" + hashlib.sha256(b"source").hexdigest()
    with pytest.raises(FilesystemEffectError, match="ACL-bearing") as error:
        LocalFilesystem().move(
            source=source,
            target=target,
            expected_digest=digest,
            expected_size=6,
            route="verified_cross_filesystem_transfer",
            temporary_path=target_parent / ".source.partial",
        )
    assert error.value.global_risk is True
    assert copied is False
    assert source.read_bytes() == b"source"
    assert not target.exists()


@pytest.mark.parametrize(
    ("error_number", "expected_code"),
    [
        (errno.ENOSPC, "insufficient_capacity"),
        (errno.EACCES, "permission_denied"),
        (errno.ENODEV, "volume_unavailable"),
    ],
)
def test_storage_errors_are_normalized_as_global_risk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error_number: int,
    expected_code: str,
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source")
    target_parent = tmp_path / "target"
    target_parent.mkdir()
    target = target_parent / "source.jpg"
    observed = source.stat()

    def fail_publish(_source: Path, _target: Path) -> None:
        raise OSError(error_number, "controlled storage fault")

    monkeypatch.setattr(apply_filesystem, "rename_exclusive", fail_publish)
    with pytest.raises(FilesystemEffectError) as captured:
        LocalFilesystem().move(
            source=source,
            target=target,
            expected_digest="sha256:" + hashlib.sha256(b"source").hexdigest(),
            expected_size=6,
            route="same_filesystem_atomic_move",
            temporary_path=None,
            expected_source_stat=(
                observed.st_dev,
                observed.st_ino,
                observed.st_mtime_ns,
            ),
        )
    assert captured.value.code == expected_code
    assert captured.value.global_risk is True
    assert source.read_bytes() == b"source"
    assert not target.exists()


def test_target_race_is_normalized_as_local_collision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.jpg"
    source.write_bytes(b"source")
    target_parent = tmp_path / "target"
    target_parent.mkdir()
    target = target_parent / "source.jpg"
    observed = source.stat()

    def collide(_source: Path, _target: Path) -> None:
        raise FileExistsError(errno.EEXIST, "controlled collision")

    monkeypatch.setattr(apply_filesystem, "rename_exclusive", collide)
    with pytest.raises(FilesystemEffectError) as captured:
        LocalFilesystem().move(
            source=source,
            target=target,
            expected_digest="sha256:" + hashlib.sha256(b"source").hexdigest(),
            expected_size=6,
            route="same_filesystem_atomic_move",
            temporary_path=None,
            expected_source_stat=(
                observed.st_dev,
                observed.st_ino,
                observed.st_mtime_ns,
            ),
        )
    assert captured.value.code == "target_collision"
    assert captured.value.global_risk is False
    assert source.exists()
    assert not target.exists()


def test_enospc_after_intent_stops_then_recovers_from_filesystem_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    executor = _executor(tmp_path, store)
    original_rename = apply_filesystem.rename_exclusive
    failed = False

    def fail_once(source_path: Path, target_path: Path) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise OSError(errno.ENOSPC, "controlled capacity loss")
        original_rename(source_path, target_path)

    monkeypatch.setattr(apply_filesystem, "rename_exclusive", fail_once)
    first = executor.execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:execute-enospc",
        authorization_binding="test:trusted-human",
    )
    assert first["state"] == "needs_attention"
    assert first["progress"]["indeterminate"] == 1
    assert first["progress"]["completed_and_verified"] == 0
    assert (source / "a.jpg").exists()
    assert (source / "b.jpg").exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()

    executor.resume(run.run_ref)
    executor.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "closed"


def test_journal_write_failure_precedes_any_media_effect_and_is_retryable(
    tmp_path: Path,
) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    with store._connect() as connection:
        connection.execute(
            """
            CREATE TRIGGER controlled_journal_failure
            BEFORE UPDATE OF execution_status ON run_items
            WHEN NEW.execution_status = 'intent'
            BEGIN
                SELECT RAISE(ABORT, 'controlled journal write failure');
            END
            """
        )
        connection.commit()
    executor = _executor(tmp_path, store)
    with pytest.raises(sqlite3.IntegrityError, match="journal write failure"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:execute-journal-failure",
            authorization_binding="test:trusted-human",
        )
    assert (source / "a.jpg").exists()
    assert (source / "b.jpg").exists()
    assert not (destination / "Media" / "Trip" / "a.jpg").exists()

    with store._connect() as connection:
        connection.execute("DROP TRIGGER controlled_journal_failure")
        connection.commit()
    executor.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "closed"


@pytest.mark.scale
def test_generated_large_file_move_has_verified_local_throughput(
    tmp_path: Path,
) -> None:
    source = tmp_path / "large-source.bin"
    target_parent = tmp_path / "target"
    target_parent.mkdir()
    target = target_parent / source.name
    block = bytes(range(256)) * 4096
    block_count = 512
    digest = hashlib.sha256()
    with source.open("wb") as stream:
        for _index in range(block_count):
            stream.write(block)
            digest.update(block)
    observed = source.stat()
    size = len(block) * block_count
    started = time.monotonic()
    result = LocalFilesystem().move(
        source=source,
        target=target,
        expected_digest="sha256:" + digest.hexdigest(),
        expected_size=size,
        route="same_filesystem_atomic_move",
        temporary_path=None,
        expected_source_stat=(
            observed.st_dev,
            observed.st_ino,
            observed.st_mtime_ns,
        ),
    )
    elapsed = time.monotonic() - started
    throughput_mib_s = size / (1024 * 1024) / max(elapsed, 0.000_001)
    print(
        f"controlled_large_file_mib={size / (1024 * 1024):.0f} "
        f"elapsed_seconds={elapsed:.3f} "
        f"verified_move_mib_per_second={throughput_mib_s:.1f}"
    )
    assert result.status == "completed"
    assert result.bytes_moved == size
    assert target.stat().st_size == size
    assert throughput_mib_s > 1
