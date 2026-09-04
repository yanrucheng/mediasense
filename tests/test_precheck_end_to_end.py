from __future__ import annotations

from pathlib import Path
import socket

from PIL import Image

from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    PrecheckReadTool,
    ResultStore,
    WorkStatus,
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


def test_narrow_real_chain_is_local_reusable_and_failure_isolated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def refuse_network(*_args, **_kwargs):
        raise AssertionError("PreCheck Slice 1 attempted network access")

    monkeypatch.setattr(socket, "create_connection", refuse_network)
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    good_path = source / "good.jpg"
    bad_path = source / "bad.jpg"
    Image.new("RGB", (160, 90), "purple").save(good_path)
    bad_path.write_bytes(b"not an image")
    source_bytes = {path.name: path.read_bytes() for path in source.iterdir()}

    first_run = _closed_run(database, source)
    producer = ImageRenditionProducer(database)
    good = producer.produce(first_run, Path("good.jpg"))
    bad = producer.produce(first_run, Path("bad.jpg"))

    assert good.work.status is WorkStatus.SUCCEEDED
    assert good.artifact is not None
    assert bad.work.status is WorkStatus.TERMINAL_FAILURE
    assert bad.artifact is None
    results = ResultStore(database)
    first_result = results.seal(
        results.build_minimal(first_run, [good.work.work_id, bad.work.work_id])
    )
    first_bytes = first_result.path.read_bytes()
    reader = PrecheckReadTool(database)
    accounts = reader.read(
        {
            "result_ref": first_result.result_ref,
            "operation": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": first_result.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    assert {item["condition"] for item in accounts["members"]} == {
        "invalid",
        "usable",
    }
    assert (
        reader.read({"result_ref": first_result.result_ref, "operation": "review"})[
            "result"
        ]["readiness"]
        == "plan_ready"
    )

    second_run = _closed_run(database, source)
    reused_good = producer.produce(second_run, Path("good.jpg"))
    reused_bad = producer.produce(second_run, Path("bad.jpg"))
    second_result = results.seal(
        results.build_minimal(
            second_run,
            [reused_good.work.work_id, reused_bad.work.work_id],
        )
    )

    assert reused_good.reused is True
    assert reused_good.artifact is not None
    assert reused_good.artifact.artifact_id == good.artifact.artifact_id
    assert first_result.result_ref != second_result.result_ref
    assert first_result.path.read_bytes() == first_bytes
    assert {path.name: path.read_bytes() for path in source.iterdir()} == source_bytes
