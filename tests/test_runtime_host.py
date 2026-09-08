from __future__ import annotations

import sqlite3
from pathlib import Path
from time import sleep

from PIL import Image
import pytest

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
from mediasense.precheck.source_attachment import SourceRebindRequired
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
            "dataset_ref": dataset_ref,
            "action": "resolve",
            "result_ref": result.result_ref,
            "source_set": {
                "kind": "precheck_relation",
                "origin": result.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        },
    )
    source_item_ref = str(accounts["members"][0]["source_item_ref"])
    source_view = host.call_tool(
        "mediasense.precheck.read",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "expand",
            "result_ref": result.result_ref,
            "source_item_refs": [source_item_ref],
            "include": ["source_item"],
        },
    )["items"][0]["included"]["source_item"]
    return (
        host,
        dataset_ref,
        result.result_ref,
        str(source_view["locator"]["source_root_ref"]),
        source,
        source_before,
    )


def test_precheck_confirmation_does_not_hide_store_errors(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    dataset_ref = host.open_dataset(str(source), str(tmp_path / "workspace"))[
        "dataset_ref"
    ]
    store = host._datasets[dataset_ref].precheck_run._store

    def invalid_record(_run_ref):
        raise KeyError("confirmation")

    monkeypatch.setattr(store, "get", invalid_record)
    with pytest.raises(KeyError, match="confirmation"):
        host.precheck_confirmation(dataset_ref, "precheck-run:not-found")


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

    assert set(started) == {"run_ref"}
    assert str(started["run_ref"]).startswith("precheck-run:")
    assert (
        host._datasets[dataset_ref].precheck_run._store.get(started["run_ref"])[
            "dataset_ref"
        ]
        == dataset_ref
    )
    assert started["run_ref"].startswith("precheck-run:")
    status = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "status",
            "run_ref": started["run_ref"],
        },
    )
    if status["state"] == "running":
        assert status.get("reason", {}).get("code") != "suspected_stalled"


def test_precheck_status_never_schedules_an_ownerless_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    dataset_ref = str(opened["dataset_ref"])
    runtime = host._datasets[dataset_ref]
    started = runtime.precheck_run.run(
        {
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:ownerless-status",
        }
    )

    def unexpected_schedule(_run_ref: str) -> None:
        pytest.fail("status must not schedule PreCheck execution")

    monkeypatch.setattr(runtime, "_schedule", unexpected_schedule)
    status = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "status",
            "run_ref": started["run_ref"],
        },
    )

    assert status["reason"]["code"] == "suspected_stalled"
    assert status["reason"]["code"] == "suspected_stalled"
    assert set(status["allowed_actions"]) == {"resume", "cancel"}


def test_successor_start_creates_work_and_never_reports_queued(
    tmp_path: Path,
) -> None:
    host, dataset_ref, result_ref, _root_ref, _source, _source_before = (
        _opened_host_with_plan_ready_result(tmp_path)
    )

    started = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "start",
            "prior_result_ref": result_ref,
            "request_id": "request:successor-runtime",
        },
    )
    assert set(started) == {"run_ref"}

    deadline = 200
    while deadline:
        status = host.call_tool(
            "mediasense.precheck.run",
            dataset_ref=dataset_ref,
            request={
                "dataset_ref": dataset_ref,
                "action": "status",
                "run_ref": started["run_ref"],
            },
        )
        assert status["state"] != "queued"
        if status["state"] != "running":
            break
        sleep(0.01)
        deadline -= 1

    assert status["state"] == "paused"
    assert status["reason"]["code"] == "scope_confirmation_required"


def test_scope_confirmation_resume_reuses_the_bound_accounting_run(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    media = source / "original.jpg"
    Image.new("RGB", (80, 40), "purple").save(media)
    source_before = media.read_bytes()
    workspace = tmp_path / "workspace"
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    started = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:runtime-scope-resume",
        },
    )
    paused = _wait_for_precheck_attention(host, dataset_ref, str(started["run_ref"]))
    assert paused["state"] == "paused"
    assert paused["reason"]["code"] == "scope_confirmation_required"

    database = workspace / "precheck" / "work.sqlite3"
    with sqlite3.connect(database) as connection:
        before = connection.execute(
            "SELECT run_id, status FROM working_runs ORDER BY started_at"
        ).fetchall()
        bound_run = connection.execute(
            "SELECT accounting_run_id FROM precheck_runs WHERE run_ref = ?",
            (started["run_ref"],),
        ).fetchone()[0]
    assert before == [(bound_run, "completed")]

    resumed = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "resume",
            "run_ref": started["run_ref"],
            "decision": {
                "kind": "source_scope",
                "inventory_fingerprint": paused["confirmation"][
                    "inventory_fingerprint"
                ],
                "default_disposition": "include",
                "exceptions": [],
            },
        },
    )
    assert "error" not in resumed
    assert resumed["state"] == "running"

    finished = _wait_for_precheck_attention(
        host, dataset_ref, str(started["run_ref"]), attempts=1000
    )
    assert finished["state"] == "completed", finished
    assert "progress" not in finished
    with sqlite3.connect(database) as connection:
        after = connection.execute(
            "SELECT run_id, status FROM working_runs ORDER BY started_at"
        ).fetchall()
        public = connection.execute(
            "SELECT state, accounting_run_id FROM precheck_runs WHERE run_ref = ?",
            (started["run_ref"],),
        ).fetchone()
        scope_state = connection.execute(
            """
            SELECT state FROM precheck_scope_reviews
            WHERE run_ref = ? ORDER BY revision DESC LIMIT 1
            """,
            (started["run_ref"],),
        ).fetchone()[0]
        orphan_running = connection.execute(
            """
            SELECT COUNT(*) FROM working_runs AS accounting
            LEFT JOIN precheck_runs AS public
              ON public.accounting_run_id = accounting.run_id
            WHERE accounting.status = 'running' AND public.run_ref IS NULL
            """
        ).fetchone()[0]
    assert after == [(bound_run, "completed")]
    assert public == ("completed", bound_run)
    assert scope_state == "accepted"
    assert orphan_running == 0
    assert media.read_bytes() == source_before


def test_scope_resume_initialization_failure_has_no_orphan_accounting_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "item.txt").write_text("account me", encoding="utf-8")
    workspace = tmp_path / "workspace"
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    runtime = host._datasets[dataset_ref]
    started = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:runtime-scope-resume-failure",
        },
    )
    paused = _wait_for_precheck_attention(host, dataset_ref, str(started["run_ref"]))

    def fail_preparation(*_args, **_kwargs) -> None:
        raise ValueError("simulated invariant failure")

    monkeypatch.setattr(runtime.precheck_run, "prepare_execution", fail_preparation)
    failed = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "resume",
            "run_ref": started["run_ref"],
            "decision": {
                "kind": "source_scope",
                "inventory_fingerprint": paused["confirmation"][
                    "inventory_fingerprint"
                ],
                "default_disposition": "include",
                "exceptions": [],
            },
        },
    )

    assert "error" in failed
    assert failed["error"]["code"] == "execution_start_failed"
    assert failed["error"]["current_state"] == "failed"
    assert "allowed_actions" not in failed["error"]
    status = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "status",
            "run_ref": started["run_ref"],
        },
    )
    assert status["state"] == "failed"
    assert status["reason"]["code"] == "execution_initialization_failed"
    assert (
        host._datasets[dataset_ref].precheck_run._store.latest_scope_review(
            started["run_ref"]
        )["state"]
        == "accepted"
    )
    with sqlite3.connect(workspace / "precheck" / "work.sqlite3") as connection:
        accounting = connection.execute(
            "SELECT status FROM working_runs ORDER BY started_at"
        ).fetchall()
        orphan_running = connection.execute(
            """
            SELECT COUNT(*) FROM working_runs AS accounting
            LEFT JOIN precheck_runs AS public
              ON public.accounting_run_id = accounting.run_id
            WHERE accounting.status = 'running' AND public.run_ref IS NULL
            """
        ).fetchone()[0]
    assert accounting == [("completed",)]
    assert orphan_running == 0


def test_scope_resume_reports_recoverable_source_rebind_as_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "item.txt").write_text("account me", encoding="utf-8")
    workspace = tmp_path / "workspace"
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    started = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:runtime-scope-rebind",
        },
    )
    paused = _wait_for_precheck_attention(host, dataset_ref, str(started["run_ref"]))

    def require_rebind(*_args, **_kwargs):
        raise SourceRebindRequired("source attachment changed")

    monkeypatch.setattr(
        AccountingStore,
        "resume_run_attachment",
        require_rebind,
    )
    response = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "resume",
            "run_ref": started["run_ref"],
            "decision": {
                "kind": "source_scope",
                "inventory_fingerprint": paused["confirmation"][
                    "inventory_fingerprint"
                ],
                "default_disposition": "include",
                "exceptions": [],
            },
        },
    )

    assert "error" in response
    assert response["error"] == {
        "code": "execution_start_failed",
        "run_ref": started["run_ref"],
        "message": "source attachment changed",
        "current_state": "blocked",
        "allowed_actions": ["resume", "cancel"],
    }
    status = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "status",
            "run_ref": started["run_ref"],
        },
    )
    assert status["state"] == "blocked"
    assert status["reason"]["code"] == "source_rebind_required"
    assert "rebind_reason" in status["reason"]["resume_when"]


def test_worker_launch_failure_is_returned_and_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    dataset_ref = str(opened["dataset_ref"])

    def fail_start(_thread: object) -> None:
        raise RuntimeError("simulated thread launch failure")

    monkeypatch.setattr(
        "mediasense.runtime.composition.threading.Thread.start", fail_start
    )
    failed = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:worker-launch-failure",
        },
    )

    assert "error" in failed
    assert failed["error"]["code"] == "execution_start_failed"
    status = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "status",
            "run_ref": failed["error"]["run_ref"],
        },
    )
    assert status["state"] == "failed"
    assert status["reason"]["code"] == "execution_worker_start_failed"
    runtime = host._datasets[dataset_ref]
    with sqlite3.connect(runtime.precheck_run.database_path) as connection:
        accounting_status = connection.execute(
            """
            SELECT accounting.status
            FROM precheck_runs AS public
            JOIN working_runs AS accounting
              ON accounting.run_id = public.accounting_run_id
            WHERE public.run_ref = ?
            """,
            (failed["error"]["run_ref"],),
        ).fetchone()[0]
        checkpoint = connection.execute(
            "SELECT execution_checkpoint FROM precheck_runs WHERE run_ref = ?",
            (failed["error"]["run_ref"],),
        ).fetchone()[0]
    assert accounting_status == "paused"
    assert '"worker":null' in checkpoint


def test_start_preparation_failure_pauses_the_unowned_accounting_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "item.txt").write_text("account me", encoding="utf-8")
    workspace = tmp_path / "workspace"
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    dataset_ref = str(opened["dataset_ref"])
    runtime = host._datasets[dataset_ref]

    def fail_preparation(*_args, **_kwargs) -> None:
        raise ValueError("simulated preparation failure")

    monkeypatch.setattr(
        runtime.precheck_run,
        "_resolved_execution_config",
        fail_preparation,
    )
    failed = host.call_tool(
        "mediasense.precheck.run",
        dataset_ref=dataset_ref,
        request={
            "action": "start",
            "dataset_ref": dataset_ref,
            "request_id": "request:runtime-start-preparation-failure",
        },
    )

    assert "error" in failed
    assert failed["error"]["current_state"] == "failed"
    with sqlite3.connect(workspace / "precheck" / "work.sqlite3") as connection:
        accounting = connection.execute(
            "SELECT status FROM working_runs ORDER BY started_at"
        ).fetchall()
        public = connection.execute(
            "SELECT state FROM precheck_runs WHERE run_ref = ?",
            (failed["error"]["run_ref"],),
        ).fetchone()[0]
    assert accounting == [("paused",)]
    assert public == "failed"


def _wait_for_precheck_attention(
    host: RuntimeHost,
    dataset_ref: str,
    run_ref: str,
    *,
    attempts: int = 500,
) -> dict[str, object]:
    for _ in range(attempts):
        status = host.call_tool(
            "mediasense.precheck.run",
            dataset_ref=dataset_ref,
            request={
                "dataset_ref": dataset_ref,
                "action": "status",
                "run_ref": run_ref,
            },
        )
        if status["state"] != "running":
            return status
        sleep(0.01)
    raise AssertionError("PreCheck Run did not reach an attention or terminal state")


def test_unavailable_preferred_representative_uses_prepared_member(
    tmp_path, monkeypatch
):
    import json

    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(tmp_path / "config"))
    source = tmp_path / "source"
    source.mkdir()
    (source / "pair.JPG").write_bytes(b"broken jpeg")
    Image.new("RGB", (24, 24), "blue").save(source / "pair.PNG")
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    dataset = opened["dataset_ref"]

    def call(request):
        return host.call_tool(
            "mediasense.precheck.run",
            dataset_ref=dataset,
            request={"dataset_ref": dataset, **request},
        )

    run = call({"action": "start", "request_id": "request:fallback"})["run_ref"]
    paused = _wait_for_precheck_attention(host, dataset, run)
    call(
        {
            "action": "resume",
            "run_ref": run,
            "decision": {
                "kind": "source_scope",
                "inventory_fingerprint": paused["confirmation"][
                    "inventory_fingerprint"
                ],
                "default_disposition": "include",
                "exceptions": [],
            },
        }
    )
    finished = _wait_for_precheck_attention(host, dataset, run)
    assert finished["state"] == "completed", finished
    assert (source / "pair.JPG").read_bytes() == b"broken jpeg"
    database = tmp_path / "workspace/precheck/work.sqlite3"
    with sqlite3.connect(database) as db:
        group = json.loads(
            db.execute(
                "SELECT output_json FROM work_records WHERE capability='adaptive-compression-group'"
            ).fetchone()[0]
        )["group"]
    assert group["representative_path"] == "pair.PNG"
    assert group["member_count"] == 2
    assert "unavailable_bundle_representative_replaced" in group["qualifications"]


def test_configured_unavailable_encoder_reports_blocked_not_success(
    tmp_path, monkeypatch
):
    from mediasense.precheck.embedding import EmbeddingBackendUnavailable

    config = tmp_path / "config"
    config.mkdir()
    (config / "config.toml").write_text(
        '[embedding]\nmodel_id="test/model"\nrevision="'
        + "a" * 40
        + '"\ndimensions=4\n'
    )
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(config))

    def unavailable(_self):
        raise EmbeddingBackendUnavailable("test local weights missing")

    monkeypatch.setattr(
        "mediasense.precheck.embedding.ChineseCLIPEncoder.check_available", unavailable
    )
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (24, 24), "blue").save(source / "photo.jpg")
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    assert opened["configuration"]["local_embedding"]["state"] == "configured"
    dataset = opened["dataset_ref"]

    def call(request):
        return host.call_tool(
            "mediasense.precheck.run",
            dataset_ref=dataset,
            request={"dataset_ref": dataset, **request},
        )

    run = call({"action": "start", "request_id": "request:unavailable"})["run_ref"]
    paused = _wait_for_precheck_attention(host, dataset, run)
    call(
        {
            "action": "resume",
            "run_ref": run,
            "decision": {
                "kind": "source_scope",
                "inventory_fingerprint": paused["confirmation"][
                    "inventory_fingerprint"
                ],
                "default_disposition": "include",
                "exceptions": [],
            },
        }
    )
    blocked = _wait_for_precheck_attention(host, dataset, run)
    assert blocked["state"] == "blocked"
    assert blocked["reason"]["code"] == "embedding_backend_unavailable"


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
        tmp_path / "workspace" / "plan" / "work-v3.sqlite3"
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
        request={
            "dataset_ref": dataset_ref,
            "action": "review",
            "result_ref": result.result_ref,
        },
    )
    accounts = host.call_tool(
        "mediasense.precheck.read",
        dataset_ref=dataset_ref,
        request={
            "dataset_ref": dataset_ref,
            "action": "resolve",
            "result_ref": result.result_ref,
            "source_set": {
                "kind": "precheck_relation",
                "origin": result.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
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

    assert inspected["result"]["readiness"] == "plan_ready"
    assert {item["condition"] for item in accounts["members"]} == {"usable"}
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
