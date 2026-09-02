from __future__ import annotations

import sqlite3
from pathlib import Path
from time import sleep

from PIL import Image

from mediasense.dataset_reference import dataset_id_from_ref
from mediasense.precheck import (
    AccountingStore,
    AdaptiveCompressionProducer,
    AdaptiveCompressionProfile,
    BundleCandidateProducer,
    CompressionInput,
    ImageRenditionProducer,
    ResultStore,
)
from mediasense.runtime.host import RuntimeHost


def _opened_host_with_plan_ready_result(
    tmp_path: Path,
) -> tuple[RuntimeHost, str, str, str, Path, bytes]:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "original.jpg"
    Image.new("RGB", (80, 40), "purple").save(media)
    source_before = media.read_bytes()
    workspace = tmp_path / "workspace"
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    dataset_id = dataset_id_from_ref(dataset_ref)
    database = workspace / "precheck" / "work.sqlite3"
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run(dataset_id, source)
    accounting.process_run(run_id)
    rendition = ImageRenditionProducer(database).produce(run_id, Path("original.jpg"))
    result_store = ResultStore(database)
    result = result_store.seal(
        result_store.build_minimal(run_id, [rendition.work.work_id])
    )
    accounts = host.call_tool(
        "mediasense.precheck.read",
        dataset_ref=dataset_ref,
        request={
            "action": "traverse",
            "result_ref": result.result_ref,
            "relation": "accounts_for",
            "direction": "outbound",
        },
    )
    source_item_ref = str(accounts["items"][0]["target"])
    source_view = host.call_tool(
        "mediasense.precheck.read",
        dataset_ref=dataset_ref,
        request={
            "action": "inspect",
            "result_ref": result.result_ref,
            "target": {"kind": "source_item", "ref": source_item_ref},
        },
    )["target"]
    return (
        host,
        dataset_ref,
        result.result_ref,
        str(source_view["locator"]["source_root_ref"]),
        source,
        source_before,
    )


def test_composition_root_constructs_all_tools_offline(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))

    assert opened["outcome"] == "ok"
    assert [item["name"] for item in host.tools()] == [
        "mediasense.dataset.open",
        "mediasense.precheck.run",
        "mediasense.precheck.read",
        "mediasense.plan.work",
        "mediasense.geo.query",
        "mediasense.apply.run",
        "mediasense.apply.read",
    ]


def test_opened_dataset_can_start_precheck_immediately(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    dataset_ref = str(opened["dataset_ref"])

    started = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:runtime-first-use",
        },
    )

    assert started["outcome"] == "ok"
    assert str(started["run_ref"]).startswith("precheck-run:")
    assert started["dataset_ref"] == dataset_ref
    assert started["state"] == "running"


def test_real_composition_creates_plan_from_precheck_result(tmp_path: Path) -> None:
    host, dataset_ref, result_ref, _root_ref, source, source_before = (
        _opened_host_with_plan_ready_result(tmp_path)
    )

    created = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset_ref,
        request={
            "action": "create",
            "result_ref": result_ref,
            "organization_preferences": {"maximum_depth": 2},
            "request_id": "request:runtime-plan-create",
        },
    )

    assert created["outcome"] == "ok"
    assert created["action"] == "create"
    assert created["result_ref"] == result_ref
    assert str(created["work_ref"]).startswith("plan-work:")
    assert str(created["revision"]).startswith("work-revision:")
    assert created["state"] == "open"
    assert (source / "original.jpg").read_bytes() == source_before
    with sqlite3.connect(
        tmp_path / "workspace" / "plan" / "work.sqlite3"
    ) as connection:
        work_count = connection.execute("SELECT COUNT(*) FROM plan_works").fetchone()[0]
    assert work_count == 1


def test_real_composition_accepts_qualified_represented_source_result(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (80, 40), "purple").save(source / "IMG_0001.JPG")
    (source / "IMG_0001.ARW").write_bytes(b"raw source bytes")
    source_before = {
        path.name: path.read_bytes() for path in source.iterdir() if path.is_file()
    }
    workspace = tmp_path / "workspace"
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    database = workspace / "precheck" / "work.sqlite3"
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run(dataset_id_from_ref(dataset_ref), source)
    accounting.process_run(run_id)
    bundle = next(BundleCandidateProducer(database).produce(run_id))
    assert bundle.candidate is not None
    rendition = ImageRenditionProducer(database).produce(run_id, Path("IMG_0001.JPG"))
    compression = AdaptiveCompressionProducer(database).produce(
        run_id,
        (
            CompressionInput(
                relative_path=Path("IMG_0001.JPG"),
                visual_work_id=rendition.work.work_id,
                member_paths=bundle.candidate.members,
                bundle_work_id=bundle.work.work_id,
            ),
        ),
        profile=AdaptiveCompressionProfile(target_entries=1),
    )
    result_store = ResultStore(database)
    result = result_store.seal(
        result_store.build_minimal(
            run_id,
            [rendition.work.work_id],
            compression_work_ids=[compression[0].work.work_id],
        )
    )

    inspected = host.call_tool(
        "mediasense.precheck.read",
        dataset_ref=dataset_ref,
        request={"action": "inspect", "result_ref": result.result_ref},
    )
    accounts = host.call_tool(
        "mediasense.precheck.read",
        dataset_ref=dataset_ref,
        request={
            "action": "traverse",
            "result_ref": result.result_ref,
            "relation": "accounts_for",
            "direction": "outbound",
        },
    )
    created = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset_ref,
        request={
            "action": "create",
            "result_ref": result.result_ref,
            "request_id": "request:runtime-represented-plan-create",
        },
    )

    assert inspected["target"]["readiness"] == "plan_ready"
    assert {item["condition"] for item in accounts["items"]} == {"usable"}
    assert created["outcome"] == "ok"
    assert created["result_ref"] == result.result_ref
    assert {
        path.name: path.read_bytes() for path in source.iterdir() if path.is_file()
    } == source_before


def test_real_composition_hands_frozen_plan_to_apply_prepare(tmp_path: Path) -> None:
    host, dataset_ref, result_ref, source_root_ref, source, source_before = (
        _opened_host_with_plan_ready_result(tmp_path)
    )
    destination = tmp_path / "destination"
    destination.mkdir()
    created = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset_ref,
        request={
            "action": "create",
            "result_ref": result_ref,
            "request_id": "request:runtime-handoff-create",
        },
    )
    all_sources = {
        "kind": "precheck_relation",
        "origin": result_ref,
        "relation": "accounts_for",
        "direction": "outbound",
    }
    updated = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset_ref,
        request={
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "request_id": "request:runtime-handoff-update",
            "candidate_content": {
                "result_ref": result_ref,
                "scope": all_sources,
                "logical_root": "Media",
                "groups": [
                    {
                        "relative_path": ["Verified"],
                        "members": all_sources,
                        "source_naming": {"default": "preserve_source_basename"},
                    }
                ],
                "other_outcomes": [],
            },
        },
    )
    inspected = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset_ref,
        request={
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "sections": ["validation"],
        },
    )
    candidate_identity = str(inspected["candidate_content_identity"])
    sealed = host.call_tool(
        "mediasense.plan.work",
        dataset_ref=dataset_ref,
        request={
            "action": "seal",
            "work_ref": created["work_ref"],
            "revision": updated["revision"],
            "candidate_content_identity": candidate_identity,
            "request_id": "request:runtime-handoff-seal",
        },
        authority={
            "principal_ref": "human:test",
            "confirmed_content_identity": candidate_identity,
            "confirmed_at": "2026-09-02T00:00:00+00:00",
        },
    )
    assert sealed["outcome"] == "ok", sealed
    prepared = host.call_tool(
        "mediasense.apply.run",
        dataset_ref=dataset_ref,
        request={
            "action": "prepare",
            "request_id": "request:runtime-handoff-prepare",
            "forward": {
                "frozen_plan": sealed["frozen_plan"],
                "effect": "move_originals",
                "current_source_roots": [
                    {
                        "source_root_ref": source_root_ref,
                        "current_root": str(source),
                    }
                ],
                "destination_parent": str(destination),
            },
        },
    )
    assert prepared["outcome"] == "ok", prepared
    run_ref = str(prepared["run_ref"])
    status = prepared
    for _ in range(100):
        status = host.call_tool(
            "mediasense.apply.run",
            dataset_ref=dataset_ref,
            request={"action": "status", "run_ref": run_ref},
        )
        if status.get("state") != "preparing":
            break
        sleep(0.01)

    assert status["state"] == "ready_for_authorization"
    assert status["summary"]["materialization_operations"] == 1
    assert (source / "original.jpg").read_bytes() == source_before
    assert list(destination.iterdir()) == []


def test_reopen_does_not_rewrite_legacy_prefixed_dataset_registration(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace = tmp_path / "workspace"
    original_host = RuntimeHost()
    opened = original_host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    dataset_id = dataset_id_from_ref(dataset_ref)
    database = workspace / "precheck" / "work.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE datasets SET dataset_id = ? WHERE dataset_id = ?",
            (dataset_ref, dataset_id),
        )

    reopened_host = RuntimeHost()
    reopened = reopened_host.open_dataset(str(source), str(workspace))

    assert reopened["outcome"] == "ok"
    assert reopened["created"] is False
    with sqlite3.connect(database) as connection:
        stored_ids = [
            str(row[0])
            for row in connection.execute(
                "SELECT dataset_id FROM datasets ORDER BY dataset_id"
            )
        ]
    assert set(stored_ids) == {dataset_id, dataset_ref}


def test_offline_geo_call_is_unavailable_without_provider_effect(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))

    result = host.call_tool(
        "mediasense.geo.query",
        dataset_ref=str(opened["dataset_ref"]),
        request={
            "request_id": "request:offline",
            "operation": "reverse_geocode",
            "subjects": [
                {
                    "subject_ref": "source-item:test",
                    "coordinate": {
                        "latitude": 22.3193,
                        "longitude": 114.1694,
                        "datum": "WGS84",
                    },
                }
            ],
            "locale": "zh-HK",
        },
    )

    assert result["outcome"] == "unavailable"
    assert result["effects"]["provider_requests"] == 0
    assert result["effects"]["transmitted_data_classes"] == []
