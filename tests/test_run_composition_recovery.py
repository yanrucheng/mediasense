"""Snapshot waits, publication retries and contradictory retained lineage."""

from copy import deepcopy
import hashlib
import json
import os

import pytest

from test_run_composition import (
    host_collection,
    finish,
    result,
    members,
    isolated_configuration,  # noqa: F401 - shared pytest fixture
)


@pytest.mark.parametrize(
    "boundary", ["_write_unpublished_result", "_after_file_published"]
)
def test_publication_retry_preserves_one_result_and_frozen_input(
    tmp_path, monkeypatch, boundary
):
    from mediasense.precheck._result_sqlite import SQLiteResultStore

    _, runtime, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    original = getattr(SQLiteResultStore, boundary)
    failed = False

    def once(*args, **kwargs):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("synthetic publication interruption")
        return original(*args, **kwargs)

    monkeypatch.setattr(SQLiteResultStore, boundary, once)
    started = call(
        "run",
        action="start",
        request_id="retry",
        prior_result_ref=old,
        **page["preparation"],
    )
    ref = started["run_ref"]
    status = finish(call, ref)
    assert status["state"] == "blocked", status
    assert status["reason"]["code"] == "workspace_write_failed"
    assert call("run", action="resume", run_ref=ref)["state"] == "running"
    done = finish(call, ref)
    assert done["state"] == "completed", done
    assert (
        call(
            "run",
            action="start",
            request_id="retry",
            prior_result_ref=old,
            **page["preparation"],
        )
        == started
    )
    with runtime.precheck_run._store._connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM sealed_results").fetchone()[0] == 2
        )
    mapped = members(
        call,
        old,
        page["preparation"]["source_set"],
        target_result_ref=done["result"]["ref"],
    )
    assert all(m["correspondence"]["status"] == "matched" for m in mapped["members"])


def test_disconnected_attachment_resumes_same_snapshot_despite_default_change(
    tmp_path, monkeypatch
):
    import mediasense.precheck._snapshot as snapshots

    _, _, call, source = host_collection(tmp_path)
    _, old, page = result(call, "first")
    original = snapshots.snapshot_events
    detached = tmp_path / "detached"
    once = True

    def disconnect(*args):
        nonlocal once
        if once:
            once = False
            source.rename(detached)
        yield from original(*args)

    monkeypatch.setattr(snapshots, "snapshot_events", disconnect)
    started = call(
        "run",
        action="start",
        request_id="unavailable",
        prior_result_ref=old,
        **page["preparation"],
    )
    status = finish(call, started["run_ref"])
    assert status["state"] == "blocked", status
    assert status["reason"]["code"] == "source_attachment_unavailable"
    detached.rename(source)
    (tmp_path / "config/config.toml").write_text(
        '[embedding]\nenabled=false\n[metadata]\noutput_timezone="UTC"\n'
    )
    assert (
        call("run", action="resume", run_ref=started["run_ref"])["state"] == "running"
    )
    resumed = finish(call, started["run_ref"])
    assert resumed["state"] == "completed", resumed
    read = call(
        "read",
        action="review",
        result_ref=resumed["result"]["ref"],
        include=["preparation"],
    )
    assert read["preparation"]["profile"] == page["preparation"]["profile"]


def test_same_inode_names_remain_distinct_input_occurrences(tmp_path):
    _, _, call, source = host_collection(tmp_path)
    (source / "00001.jpg").unlink()
    os.link(source / "00000.jpg", source / "00001.jpg")
    _, old, page = result(call, "first")
    _, new, _ = result(call, "second", prior_result_ref=old, **page["preparation"])
    response = members(
        call, old, page["preparation"]["source_set"], target_result_ref=new
    )
    rows = [
        m
        for m in response["members"]
        if m["locator"]["value"] in {"00000.jpg", "00001.jpg"}
    ]
    assert len({m["correspondence"]["source_item_ref"] for m in rows}) == 2


def test_historical_preparation_and_lineage_remain_unrecorded(tmp_path):
    from test_precheck_delivery import prepared
    from mediasense.precheck import PrecheckReadTool

    database, store, draft, _ = prepared(tmp_path)
    sealed = store.seal(draft)
    before = sealed.path.read_bytes()
    reader = PrecheckReadTool(database)
    base = {"dataset_ref": "dataset:delivery", "result_ref": sealed.result_ref}
    read = reader.read({**base, "action": "review", "include": ["preparation"]})
    assert read["preparation"] is None
    assert "processing_profile_unrecorded" in {
        q["code"] for q in read["result"]["qualifications"]
    }
    source_set = {
        "kind": "precheck_relation",
        "origin": sealed.result_ref,
        "relation": "accounts_for",
        "direction": "outbound",
    }
    resolved = reader.read(
        {
            **base,
            "action": "resolve",
            "source_set": source_set,
            "target_result_ref": sealed.result_ref,
        }
    )
    assert all(
        m["correspondence"]
        == {"status": "unproven", "basis": {"code": "input_binding_unrecorded"}}
        for m in resolved["members"]
    )
    assert (
        reader.read(
            {
                **base,
                "action": "resolve",
                "source_set": {"kind": "profile_scope", "index": 0},
            }
        )["error"]["code"]
        == "invalid_source_set"
    )
    assert sealed.path.read_bytes() == before


@pytest.mark.parametrize("corrupt", ["duplicate", "contradiction", "outside", "digest"])
def test_contradictory_sealed_bindings_are_integrity_failure(tmp_path, corrupt):
    _, runtime, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    _, new, _ = result(call, "second", prior_result_ref=old, **page["preparation"])
    with runtime.precheck_run._store._connect() as connection:
        row = connection.execute(
            "SELECT relative_path FROM sealed_results WHERE result_ref = ?", (new,)
        ).fetchone()
    path = runtime.precheck_run.database_path.parent / row[0]
    package = json.loads(path.read_text())
    binding = package["input_bindings"]
    if corrupt == "duplicate":
        binding["members"].append(deepcopy(binding["members"][0]))
    elif corrupt == "outside":
        binding["members"][0]["target_ref"] = "source-item:outside"
    elif corrupt == "contradiction":
        binding["members"][0]["locator"]["value"] = "different.jpg"
    else:
        binding["digest"] = "f" * 64
    encoded = json.dumps(
        package, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    path.chmod(0o644)
    path.write_bytes(encoded)
    path.chmod(0o444)
    with runtime.precheck_run._store._transaction() as connection:
        connection.execute(
            "UPDATE sealed_results SET digest = ?, size_bytes = ? WHERE result_ref = ?",
            (hashlib.sha256(encoded).hexdigest(), len(encoded), new),
        )
    response = call(
        "read",
        action="resolve",
        result_ref=old,
        source_set=page["preparation"]["source_set"],
        target_result_ref=new,
    )
    assert response["error"]["code"] == "result_inconsistent", response
