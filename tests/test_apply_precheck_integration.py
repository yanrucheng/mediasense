from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from mediasense.apply import (
    ApplyExecutor,
    ApplyRunStore,
    ReceiptStore,
)
from mediasense.apply.preparation import SourceSetExpansion
from mediasense.precheck.read import bind_precheck_read

from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    PrecheckReadTool,
    ResultStore,
)


def _identity(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _plan(*, result_ref: str, source_item_ref: str) -> dict[str, object]:
    content = {
        "contract": "mediasense.frozen-plan",
        "plan_ref": "frozen-plan:real-precheck-integration",
        "result_ref": result_ref,
        "scope": {"kind": "explicit", "source_item_refs": [source_item_ref]},
        "logical_root": "Media",
        "groups": [
            {
                "relative_path": ["Verified"],
                "members": {
                    "kind": "explicit",
                    "source_item_refs": [source_item_ref],
                },
                "source_naming": {"default": "preserve_source_basename"},
            }
        ],
        "other_outcomes": [],
    }
    content_identity = _identity(content)
    return {
        "sealed_content": content,
        "seal": {
            "encoding_profile": "mediasense-json-strings-sha256-v1",
            "content_identity": content_identity,
            "final_confirmation": {
                "confirmed_content_identity": content_identity,
                "confirmed_at": "2026-08-30T09:00:00+08:00",
                "confirmed_by": "human:integration-test",
            },
        },
    }


def _resolve(_result_ref: str, source_set: dict) -> SourceSetExpansion:
    return SourceSetExpansion(iter(source_set["source_item_refs"]), complete=True)


def test_prepare_resolves_and_verifies_one_real_sealed_precheck_result(
    tmp_path: Path,
) -> None:
    database = tmp_path / "precheck-state" / "working.sqlite3"
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    Image.new("RGB", (80, 40), "blue").save(source / "original.jpg")
    source_before = (source / "original.jpg").read_bytes()

    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-apply-integration")
    run_id = accounting.start_or_resume_run("dataset-apply-integration", source)
    accounting.process_run(run_id)
    rendition = ImageRenditionProducer(database).produce(run_id, Path("original.jpg"))
    result = ResultStore(database).seal(
        ResultStore(database).build_minimal(run_id, [rendition.work.work_id])
    )
    reader = bind_precheck_read(
        PrecheckReadTool(database), "dataset:dataset-apply-integration"
    )

    accounts = reader.read(
        {
            "dataset_ref": "dataset:dataset-apply-integration",
            "result_ref": result.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": result.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    source_item_ref = next(
        str(item["source_item_ref"])
        for item in accounts["members"]
        if item["scope"] == "source_media"
    )
    inspected = reader.read(
        {
            "dataset_ref": "dataset:dataset-apply-integration",
            "result_ref": result.result_ref,
            "action": "expand",
            "source_item_refs": [source_item_ref],
            "include": ["source_item", "observations"],
        }
    )
    included = inspected["items"][0]["included"]
    source_root_ref = included["source_item"]["locator"]["source_root_ref"]
    verification = next(
        observation
        for observation in included["observations"]
        if observation["name"] == "source_content_verification"
    )
    assert verification["value"]["profile"] == "candidate-sha256-full-or-3x4k-v1"

    apply = ApplyRunStore.initialize(tmp_path / "apply-state" / "apply.sqlite3")
    prepared = apply.prepare_forward(
        request_id="request:real-precheck-integration",
        frozen_plan=_plan(
            result_ref=result.result_ref,
            source_item_ref=source_item_ref,
        ),
        source_roots={source_root_ref: source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )

    assert prepared.state == "ready_for_authorization"
    item = apply.iter_items(prepared.run_ref, limit=1)[0]
    assert item["source_item_ref"] == source_item_ref
    assert item["verification_profile"] == "candidate-sha256-full-or-3x4k-v1"
    assert item["verification_producer"] == verification["value"]["producer"]
    assert item["expected_verification"] == item["observed_verification"]
    assert (source / "original.jpg").read_bytes() == source_before
    assert list(destination.iterdir()) == []


def test_real_sealed_precheck_result_executes_controlled_move_and_receipt(
    tmp_path: Path,
) -> None:
    database = tmp_path / "precheck-state" / "working.sqlite3"
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    Image.new("RGB", (80, 40), "green").save(source / "original.jpg")
    original = (source / "original.jpg").read_bytes()

    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-apply-e2e")
    run_id = accounting.start_or_resume_run("dataset-apply-e2e", source)
    accounting.process_run(run_id)
    rendition = ImageRenditionProducer(database).produce(run_id, Path("original.jpg"))
    result = ResultStore(database).seal(
        ResultStore(database).build_minimal(run_id, [rendition.work.work_id])
    )
    reader = bind_precheck_read(PrecheckReadTool(database), "dataset:dataset-apply-e2e")
    accounts = reader.read(
        {
            "dataset_ref": "dataset:dataset-apply-e2e",
            "result_ref": result.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": result.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    source_item_ref = next(
        str(item["source_item_ref"])
        for item in accounts["members"]
        if item["scope"] == "source_media"
    )
    source_view = reader.read(
        {
            "dataset_ref": "dataset:dataset-apply-e2e",
            "result_ref": result.result_ref,
            "action": "expand",
            "source_item_refs": [source_item_ref],
            "include": ["source_item"],
        }
    )["items"][0]["included"]["source_item"]
    source_root_ref = source_view["locator"]["source_root_ref"]

    apply = ApplyRunStore.initialize(tmp_path / "apply-state" / "work.sqlite3")
    prepared = apply.prepare_forward(
        request_id="request:real-precheck-e2e",
        frozen_plan=_plan(
            result_ref=result.result_ref, source_item_ref=source_item_ref
        ),
        source_roots={source_root_ref: source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    executor = ApplyExecutor(
        apply,
        ReceiptStore(
            tmp_path / "apply-state" / "receipts",
            Path(__file__).parents[1]
            / "docs/spec/contract/apply/apply-receipt.schema.json",
        ),
    )
    status = executor.execute(
        run_ref=prepared.run_ref,
        prepared_revision=prepared.prepared_revision,
        prepared_content_identity=prepared.prepared_content_identity,
        request_id="request:real-precheck-e2e-execute",
        authorization_binding="test:trusted-human",
    )

    assert status["state"] == "closed"
    assert not (source / "original.jpg").exists()
    assert (
        destination / "Media" / "Verified" / "original.jpg"
    ).read_bytes() == original
    receipt = executor.receipt_store.read(status["published_receipt"]["receipt_ref"])
    operation = receipt["sealed_content"]["operation_ledger"]["items"][0]
    assert operation["source_item_ref"] == source_item_ref
    assert (
        operation["source_verification"]["profile"]
        == "candidate-sha256-full-or-3x4k-v1"
    )
