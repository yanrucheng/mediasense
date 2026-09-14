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
    "damage", ["missing", "null", "invalid_json", "input", "scopes", "profile"]
)
def test_resume_refuses_damaged_frozen_requirements(tmp_path, monkeypatch, damage):
    import mediasense.precheck._snapshot as snapshots

    _, runtime, call, source = host_collection(tmp_path)
    _, old, page = result(call, "first")
    selected = members(call, old, page["preparation"]["source_set"])["members"][:2]
    requested = deepcopy(page["preparation"])
    requested["profile"]["overrides"] = [
        {
            "source_set": {
                "kind": "explicit",
                "source_item_refs": [m["source_item_ref"] for m in selected],
            },
            "compression": None,
        }
    ]
    detached = tmp_path / "detached"
    source.rename(detached)
    started = call(
        "run", action="start", request_id="damaged", prior_result_ref=old, **requested
    )
    ref = started["run_ref"]
    assert finish(call, ref)["reason"]["code"] == "source_attachment_unavailable"
    detached.rename(source)
    with runtime.precheck_run._store._transaction() as connection:
        frozen = json.loads(
            connection.execute(
                "SELECT value_json FROM precheck_run_preparation WHERE run_ref = ?",
                (ref,),
            ).fetchone()[0]
        )
        if damage == "missing":
            connection.execute(
                "DELETE FROM precheck_run_preparation WHERE run_ref = ?", (ref,)
            )
        else:
            if damage == "input":
                frozen["input"] = None
            elif damage == "scopes":
                frozen["scopes"][0].pop()
            elif damage == "profile":
                frozen["profile"]["overrides"][0]["compression"] = frozen["profile"][
                    "compression"
                ]
            encoded = (
                "null"
                if damage == "null"
                else "{"
                if damage == "invalid_json"
                else json.dumps(frozen)
            )
            connection.execute(
                "UPDATE precheck_run_preparation SET value_json = ? WHERE run_ref = ?",
                (encoded, ref),
            )
    visited = []
    original = snapshots.snapshot_events

    def observe(*args):
        visited.append(True)
        yield from original(*args)

    monkeypatch.setattr(snapshots, "snapshot_events", observe)
    resumed = call("run", action="resume", run_ref=ref)
    assert "error" not in resumed, resumed
    status = finish(call, ref)
    assert status["state"] == "failed", status
    assert status["reason"]["code"] == "execution_failed", status
    assert not visited
    with runtime.precheck_run._store._connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM sealed_results").fetchone()[0] == 1
        )
    assert (
        call("read", action="review", result_ref=old, include=["preparation"]) == page
    )


@pytest.mark.parametrize("changed", [True, False])
@pytest.mark.parametrize("during_publication", [False, True])
def test_fingerprint_change_is_terminal_but_read_unavailable_resumes(
    tmp_path, monkeypatch, changed, during_publication
):
    import mediasense.precheck._snapshot as snapshots
    from mediasense.precheck._fingerprint import SourceChangedDuringRead

    _, _, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    original = snapshots.fingerprint_candidate
    calls = 0

    def fail(*args):
        nonlocal calls
        calls += 1
        if during_publication and calls <= 8:
            return original(*args)
        raise (
            SourceChangedDuringRead("source changed")
            if changed
            else PermissionError("temporarily unreadable")
        )

    monkeypatch.setattr(snapshots, "fingerprint_candidate", fail)
    started = call(
        "run",
        action="start",
        request_id="verify",
        prior_result_ref=old,
        **page["preparation"],
    )
    ref = started["run_ref"]
    status = finish(call, ref)
    assert status["state"] == ("failed" if changed else "blocked"), status
    assert status["reason"]["code"] == (
        "source_snapshot_changed" if changed else "source_verification_unavailable"
    )
    monkeypatch.setattr(snapshots, "fingerprint_candidate", original)
    if changed:
        assert (
            call("run", action="resume", run_ref=ref)["error"]["code"]
            == "invalid_state"
        )
    else:
        assert call("run", action="resume", run_ref=ref)["state"] == "running"
        assert finish(call, ref)["state"] == "completed"


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


@pytest.mark.parametrize("replacement_directory", [False, True])
def test_disconnected_attachment_resumes_same_snapshot_despite_default_change(
    tmp_path, monkeypatch, replacement_directory
):
    import mediasense.precheck._snapshot as snapshots

    _, runtime, call, source = host_collection(tmp_path)
    _, old, page = result(call, "first")
    original = snapshots.snapshot_events
    detached = tmp_path / "detached"
    once = True

    def disconnect(*args):
        nonlocal once
        if once:
            once = False
            source.rename(detached)
            if replacement_directory:
                source.mkdir()
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
    if replacement_directory:
        # Valid pre-repair frozen Runs had no payload digest. They still resume
        # from their recorded requirements, never from current Dataset defaults.
        with runtime.precheck_run._store._transaction() as connection:
            row = connection.execute(
                "SELECT execution_config_json FROM precheck_runs WHERE run_ref = ?",
                (started["run_ref"],),
            ).fetchone()
            config = json.loads(row[0])
            config.pop("preparation_digest")
            connection.execute(
                "UPDATE precheck_runs SET execution_config_json = ? WHERE run_ref = ?",
                (json.dumps(config), started["run_ref"]),
            )
    if replacement_directory:
        source.rmdir()
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
