"""Ordinary Run→immutable read→local Run, through real composed Host internals."""

from copy import deepcopy
from dataclasses import replace
from time import monotonic, sleep

import pytest
from PIL import Image

from mediasense.runtime.host import RuntimeHost


@pytest.fixture(autouse=True)
def isolated_configuration(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    (config / "config.toml").write_text(
        "[embedding]\nenabled=false\n[sensitivity]\nenabled=false\n"
    )
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(config))
    monkeypatch.setenv("MEDIASENSE_DATA_HOME", str(tmp_path / "data"))


def host_collection(tmp_path, count=8):
    source = tmp_path / "source"
    source.mkdir()
    for i in range(count):
        Image.new("RGB", (8, 8), "blue").save(source / f"{i:05}.jpg")
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(tmp_path / "workspace"))
    assert opened["outcome"] == "ok", opened
    dataset = opened["dataset_ref"]
    runtime = host._datasets[dataset]
    runtime.precheck_run._execution_config = replace(
        runtime.precheck_run._execution_config,
        metadata=False,
        gpx=False,
        video=False,
        bundles=False,
        compression_target=2,
    )

    def call(tool, **request):
        return host.call_tool(
            "mediasense.precheck." + tool,
            dataset_ref=dataset,
            request={"dataset_ref": dataset, **request},
        )

    return host, runtime, call, source


def finish(call, ref):
    deadline = monotonic() + 30
    while monotonic() < deadline:
        status = call("run", action="status", run_ref=ref)
        assert "error" not in status, status
        if status["state"] == "paused":
            c = status["confirmation"]
            assert c["kind"] == "source_scope", status
            resumed = call(
                "run",
                action="resume",
                run_ref=ref,
                decision={
                    "kind": "source_scope",
                    "inventory_fingerprint": c["inventory_fingerprint"],
                    "default_disposition": "include",
                    "exceptions": [],
                },
            )
            if "error" in resumed:
                assert resumed["error"]["code"] == "invalid_state", resumed
        elif status["state"] != "running":
            return status
        sleep(0.01)
    raise AssertionError("Run did not reach a real boundary")


def result(call, request_id, **request):
    started = call("run", action="start", request_id=request_id, **request)
    assert "error" not in started, started
    status = finish(call, started["run_ref"])
    assert status["state"] == "completed", status
    ref = status["result"]["ref"]
    page = call("read", action="review", result_ref=ref, include=["preparation"])
    assert "error" not in page, page
    return started["run_ref"], ref, page


def members(call, ref, selection, **kwargs):
    response = call(
        "read", action="resolve", result_ref=ref, source_set=selection, **kwargs
    )
    assert "error" not in response, response
    return response


def test_accepted_run_releases_input_graph_after_freezing(tmp_path):
    import weakref

    host, runtime, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    graph = weakref.ref(runtime.precheck_read._cached_result[2])
    # Direct Run start freezes/initializes but does not schedule a Host worker.
    # This observes the execution boundary without racing publication.
    started = runtime.precheck_run.run({
        "action": "start",
        "dataset_ref": runtime.opened.manifest.dataset_ref,
        "request_id": "second",
        "prior_result_ref": old,
        **page["preparation"],
    })
    assert "error" not in started, started
    assert graph() is None
    assert call("read", action="review", result_ref=old, include=["preparation"]) == page
    assert "error" not in call("run", action="cancel", run_ref=started["run_ref"])


def test_correspondence_pages_reuse_two_verified_graphs(tmp_path, monkeypatch):
    from mediasense.precheck import PrecheckReadTool
    import mediasense.precheck.read as reading

    host, runtime, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    _, new, _ = result(call, "second", prior_result_ref=old, **page["preparation"])
    reader = PrecheckReadTool(runtime.precheck_run.database_path)
    validate = reader._validate_package
    validations = []

    def counted(*args):
        validations.append(args[1])
        return validate(*args)

    monkeypatch.setattr(reader, "_validate_package", counted)
    request = {
        "dataset_ref": runtime.opened.manifest.dataset_ref,
        "action": "resolve",
        "result_ref": old,
        "target_result_ref": new,
        "source_set": page["preparation"]["source_set"],
        "page": {"limit": 1},
    }
    refs = []
    while True:
        response = reader.read(request)
        assert "error" not in response, response
        refs.extend(m["correspondence"]["source_item_ref"] for m in response["members"])
        assert all(m["correspondence"]["status"] == "matched" for m in response["members"])
        cursor = response["page"]["next_cursor"]
        if cursor is None:
            break
        request["page"]["cursor"] = cursor
    assert len(set(refs)) == 8
    assert validations == [old, new]
    assert reader._cached_secondary is not None
    # Both graphs share the existing cap; neither errors nor an oversized
    # read may leave an old peer behind as a successful cache entry.
    monkeypatch.setattr(reading, "_MAX_CACHED_RESULT_BYTES", 0)
    assert "error" not in reader.read(request)
    assert reader._cached_result is reader._cached_secondary is None


def test_local_partition_readback_correspondence_and_retention(tmp_path, monkeypatch):
    host, runtime, call, source = host_collection(tmp_path)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    _, old, page = result(call, "first")
    from mediasense.precheck import ResultStore

    retained_path = ResultStore(runtime.precheck_run.database_path).get(old).path
    retained_bytes = retained_path.read_bytes()
    preparation = page["preparation"]
    assert preparation["profile"]["compression"]["target_entries"] == 2
    old_members = members(call, old, preparation["source_set"])["members"]
    chosen = [
        m["source_item_ref"]
        for m in sorted(old_members, key=lambda m: m["locator"]["value"])[:2]
    ]
    # Prove valid warm work never calls the actual decode implementation.
    from mediasense.precheck import rendition

    def no_decode(*args, **kwargs):
        raise AssertionError("A valid rendition was decoded again")

    monkeypatch.setattr(rendition, "_decode_rgb", no_decode)
    changed = deepcopy(preparation)
    changed["profile"]["overrides"] = [
        {
            "source_set": {"kind": "explicit", "source_item_refs": chosen},
            "compression": None,
        }
    ]
    new_run, new, new_page = result(call, "second", prior_result_ref=old, **changed)
    assert new != old and new_page["accounting"]["total"] == 8
    assert new_page["page"]["total"] == 4
    groups = {
        tuple(
            sorted(
                m["locator"]["value"]
                for m in members(call, new, item["represents"]["source_set"])["members"]
            )
        )
        for item in new_page["items"]
    }
    assert groups == {
        ("00000.jpg",),
        ("00001.jpg",),
        ("00002.jpg", "00003.jpg", "00004.jpg"),
        ("00005.jpg", "00006.jpg", "00007.jpg"),
    }
    assert all(len(item["source_items"]) == 1 for item in new_page["items"])
    assert (
        new_page["preparation"]["profile"]["compression"]
        == preparation["profile"]["compression"]
    )
    assert new_page["preparation"]["profile"]["overrides"][0]["source_set"] == {
        "kind": "profile_scope",
        "index": 0,
    }
    mapped = members(call, old, preparation["source_set"], target_result_ref=new)[
        "members"
    ]
    assert len({m["correspondence"]["source_item_ref"] for m in mapped}) == 8
    assert all(m["correspondence"]["status"] == "matched" for m in mapped)
    new_scope = members(call, new, {"kind": "profile_scope", "index": 0})["members"]
    assert {m["locator"]["value"] for m in new_scope} == {"00000.jpg", "00001.jpg"}
    # A copied public Profile is independently usable for another ordinary Run.
    _, third, _ = result(call, "third", prior_result_ref=new, **new_page["preparation"])
    assert third != new
    replay = call(
        "run", action="start", request_id="second", prior_result_ref=old, **changed
    )
    assert replay == {"run_ref": new_run}
    assert (
        call("read", action="review", result_ref=old, include=["preparation"]) == page
    )
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    # Producer-cache maintenance must not remove published Artifact material.
    from mediasense.precheck.maintenance import WorkspaceMaintenance
    from datetime import timedelta

    WorkspaceMaintenance(runtime.precheck_run.database_path).collect(
        grace_period=timedelta(0)
    )
    assert (
        call("read", action="review", result_ref=old, include=["preparation"]) == page
    )
    with runtime.precheck_run._store._transaction() as connection:
        connection.execute("DELETE FROM precheck_run_preparation")
    from mediasense.precheck import PrecheckReadTool

    cold = PrecheckReadTool(runtime.precheck_run.database_path)
    assert (
        cold.read(
            {
                "dataset_ref": runtime.opened.manifest.dataset_ref,
                "action": "review",
                "result_ref": old,
                "include": ["preparation"],
            }
        )
        == page
    )
    assert retained_path.read_bytes() == retained_bytes


def test_changed_snapshot_fails_and_new_directory_entries_do_not_join(tmp_path):
    _, runtime, call, source = host_collection(tmp_path)
    _, old, page = result(call, "first")
    Image.new("RGB", (8, 8), "red").save(source / "new.jpg")
    _, new, new_page = result(
        call, "same-snapshot", prior_result_ref=old, **page["preparation"]
    )
    assert new_page["accounting"]["total"] == 8
    (source / "00000.jpg").write_bytes(b"changed")
    started = call(
        "run",
        action="start",
        request_id="changed",
        prior_result_ref=new,
        **new_page["preparation"],
    )
    status = finish(call, started["run_ref"])
    assert status["state"] == "failed"
    assert status["reason"]["code"] == "source_snapshot_changed"
    assert "result" not in status
    failed_accounting = runtime.precheck_run._store.get(started["run_ref"])[
        "accounting_run_id"
    ]
    fresh_run, _, fresh_page = result(call, "fresh-current-input")
    assert (
        runtime.precheck_run._store.get(fresh_run)["accounting_run_id"]
        != failed_accounting
    )
    assert fresh_page["accounting"]["total"] == 9


def test_scope_rejections_and_configuration_guard_precede_new_run(tmp_path):
    _, runtime, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    selected = members(call, old, page["preparation"]["source_set"])["members"][0][
        "source_item_ref"
    ]
    base = {"prior_result_ref": old, **page["preparation"]}
    override = {
        "source_set": {"kind": "explicit", "source_item_refs": [selected]},
        "compression": None,
    }
    cases = []
    req = deepcopy(base)
    req["source_set"] = override["source_set"]
    cases.append((req, "invalid_source_set"))
    req = deepcopy(base)
    req["profile"]["overrides"] = [
        {
            **override,
            "source_set": {
                "kind": "difference",
                "base": base["source_set"],
                "subtract": base["source_set"],
            },
        }
    ]
    cases.append((req, "invalid_source_set"))
    req = deepcopy(base)
    req["profile"]["overrides"] = [override, override]
    cases.append((req, "invalid_source_set"))
    req = deepcopy(base)
    req["profile"]["configuration_identity"] = "sha256:" + "f" * 64
    cases.append((req, "configuration_changed"))
    req = deepcopy(base)
    req["profile"]["overrides"] = [
        {
            "source_set": {
                "kind": "explicit",
                "source_item_refs": ["source-item:outside"],
            },
            "compression": None,
        }
    ]
    cases.append((req, "reference_not_in_result"))
    req = deepcopy(base)
    req["profile"]["overrides"] = [
        {
            **override,
            "compression": {
                **req["profile"]["compression"],
                "content_distance_scale": 0.1,
            },
        }
    ]
    cases.append((req, "configuration_invalid"))
    for i, (req, code) in enumerate(cases):
        response = call("run", action="start", request_id=f"bad-{i}", **req)
        assert response["error"]["code"] == code, response
    with runtime.precheck_run._store._connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM precheck_runs").fetchone()[0] == 1
        )
        assert (
            connection.execute("SELECT count(*) FROM working_runs").fetchone()[0] == 1
        )


def test_independent_run_is_unproven_and_cursor_binds_target(tmp_path):
    _, _, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    _, independent, _ = result(call, "independent", prior_result_ref=old)
    selection = page["preparation"]["source_set"]
    response = members(
        call, old, selection, target_result_ref=independent, page={"limit": 1}
    )
    assert response["members"][0]["correspondence"] == {
        "status": "unproven",
        "basis": {"code": "not_direct_successor"},
    }
    cursor = response["page"]["next_cursor"]
    bad = call(
        "read",
        action="resolve",
        result_ref=old,
        source_set=selection,
        target_result_ref=old,
        page={"limit": 1, "cursor": cursor},
    )
    assert bad["error"]["code"] == "invalid_cursor"


def test_auxiliary_is_accounted_but_cannot_be_a_compression_override(tmp_path):
    _, _, call, source = host_collection(tmp_path)
    (source / "track.gpx").write_text('<gpx version="1.1" creator="synthetic"/>')
    _, old, page = result(call, "first")
    rows = members(call, old, page["preparation"]["source_set"])["members"]
    auxiliary = next(m for m in rows if m["scope"] == "auxiliary")
    request = deepcopy(page["preparation"])
    request["profile"]["overrides"] = [
        {
            "source_set": {
                "kind": "explicit",
                "source_item_refs": [auxiliary["source_item_ref"]],
            },
            "compression": None,
        }
    ]
    rejected = call(
        "run",
        action="start",
        request_id="aux-override",
        prior_result_ref=old,
        **request,
    )
    assert rejected["error"]["code"] == "invalid_source_set"
    _, new, current = result(
        call, "same-snapshot", prior_result_ref=old, **page["preparation"]
    )
    preserved = members(
        call, old, page["preparation"]["source_set"], target_result_ref=new
    )["members"]
    assert current["accounting"]["total"] == 9
    assert [m["scope"] for m in preserved].count("auxiliary") == 1


def test_replay_storage_failure_is_not_misclassified_as_caller_input(
    tmp_path, monkeypatch
):
    _, runtime, call, _ = host_collection(tmp_path)

    def corrupt_record(_request):
        raise ValueError("corrupt retained execution JSON")

    monkeypatch.setattr(runtime.precheck_run._store, "replay_start", corrupt_record)
    with pytest.raises(ValueError, match="corrupt retained"):
        call("run", action="start", request_id="valid-request")
    with pytest.raises(ValueError, match="corrupt retained"):
        runtime.precheck_run.run(
            {
                "action": "start",
                "dataset_ref": runtime.opened.manifest.dataset_ref,
                "request_id": "valid-request",
            }
        )


def test_missing_directed_input_prepares_only_that_source(tmp_path, monkeypatch):
    _, _, call, _ = host_collection(tmp_path, count=129)
    _, old, page = result(call, "first")
    all_members = members(call, old, page["preparation"]["source_set"])["members"]
    missing = [m for m in all_members if m["condition"] == "unresolved"]
    assert len(missing) == 1
    from mediasense.precheck import rendition

    decoded = []
    original = rendition._decode_rgb

    def decode(path):
        decoded.append(path.name)
        return original(path)

    monkeypatch.setattr(rendition, "_decode_rgb", decode)
    request = deepcopy(page["preparation"])
    request["profile"]["overrides"] = [
        {
            "source_set": {
                "kind": "explicit",
                "source_item_refs": [missing[0]["source_item_ref"]],
            },
            "compression": None,
        }
    ]
    _, _, prepared = result(call, "directed", prior_result_ref=old, **request)
    assert decoded == [missing[0]["locator"]["value"]]
    assert prepared["accounting"]["total"] == 129


@pytest.mark.parametrize(
    "selected_paths,expected_new",
    [
        (["00050.jpg"], {"00050.jpg"}),
        (["00000.jpg", "00099.jpg", "00050.jpg"], {"00001.jpg", "00050.jpg"}),
    ],
)
def test_crossing_bundle_keeps_remainder_sampling(
    tmp_path, monkeypatch, selected_paths, expected_new
):
    from test_precheck_orchestration import FakeExifTool
    from mediasense.precheck import rendition

    _, runtime, call, _ = host_collection(tmp_path, count=100)
    runtime.precheck_run._execution_config = replace(
        runtime.precheck_run._execution_config, metadata=True, bundles=True
    )
    runtime.precheck_run._orchestrator.dependencies = replace(
        runtime.precheck_run._orchestrator.dependencies,
        metadata_runner=FakeExifTool(
            {f"{i:05}.jpg": "2026:05:01 12:00:00+08:00" for i in range(100)}
        ),
        exiftool_version="13.30",
    )
    _, old, page = result(call, "first")
    assert page["page"]["total"] == 1
    rows = members(call, old, page["preparation"]["source_set"])["members"]
    refs = [
        m["source_item_ref"] for m in rows if m["locator"]["value"] in selected_paths
    ]
    decoded = []
    original = rendition._decode_rgb

    def decode(path):
        decoded.append(path.name)
        return original(path)

    monkeypatch.setattr(rendition, "_decode_rgb", decode)
    request = deepcopy(page["preparation"])
    request["profile"]["overrides"] = [
        {
            "source_set": {"kind": "explicit", "source_item_refs": refs},
            "compression": None,
        }
    ]
    _, _, current = result(call, "partition", prior_result_ref=old, **request)
    assert set(decoded) == expected_new
    assert current["accounting"]["total"] == 100
    assert current["page"]["total"] == len(selected_paths) + 1
    assert (
        current["preparation"]["profile"]["compression"]
        == page["preparation"]["profile"]["compression"]
    )


def test_threshold_only_reuses_embedding_without_checking_backend(
    tmp_path, monkeypatch
):
    from test_precheck_orchestration import FakeEncoder
    from mediasense.runtime import embedding

    encoder = FakeEncoder()
    monkeypatch.setattr(embedding, "make_encoder", lambda profile: encoder)
    (tmp_path / "config/config.toml").write_text(
        "[embedding]\nenabled=true\n[sensitivity]\nenabled=false\n"
    )
    host, runtime, call, _ = host_collection(tmp_path)
    # FakeEncoder declares four output dimensions, under a real profile boundary.
    original_reload = runtime._reload_metadata_configuration

    def reload():
        original_reload()
        config = runtime.precheck_run._execution_config
        runtime.precheck_run._execution_config = replace(
            config, embedding_profile=replace(config.embedding_profile, dimensions=4)
        )

    monkeypatch.setattr(runtime, "_reload_metadata_configuration", reload)
    _, old, page = result(call, "first")
    calls = len(encoder.batch_calls)
    assert calls > 0

    def unavailable():
        raise AssertionError("Warm reuse must not load/check the model backend")

    encoder.check_available = unavailable
    selection = members(call, old, page["preparation"]["source_set"])["members"][:2]
    request = deepcopy(page["preparation"])
    request["profile"]["overrides"] = [
        {
            "source_set": {
                "kind": "explicit",
                "source_item_refs": [m["source_item_ref"] for m in selection],
            },
            "compression": {
                **request["profile"]["compression"],
                "content_distance_scale": 0.1,
            },
        }
    ]
    result(call, "threshold", prior_result_ref=old, **request)
    assert len(encoder.batch_calls) == calls
    # An actual model identity change invalidates embeddings, not their images.
    del encoder.check_available
    encoder.identity = "fake-local-embedding@sha256:two"
    from mediasense.precheck import rendition

    def no_decode(*args):
        raise AssertionError("Model changes must retain valid input renditions")

    monkeypatch.setattr(rendition, "_decode_rgb", no_decode)
    result(
        call,
        "changed-model",
        prior_result_ref=old,
        source_set=page["preparation"]["source_set"],
    )
    assert len(encoder.batch_calls) > calls


def test_request_replay_precedes_changed_current_defaults(tmp_path):
    _, _, call, _ = host_collection(tmp_path)
    _, old, page = result(call, "first")
    request = {"prior_result_ref": old, **page["preparation"]}
    run, _, _ = result(call, "accepted", **request)
    (tmp_path / "config/config.toml").write_text(
        '[embedding]\nenabled=false\n[metadata]\noutput_timezone="UTC"\n'
    )
    assert call("run", action="start", request_id="accepted", **request) == {
        "run_ref": run
    }
    assert (
        call("run", action="start", request_id="new", **request)["error"]["code"]
        == "configuration_changed"
    )

    changed = deepcopy(request)
    changed["profile"]["compression"]["target_entries"] += 1
    assert (
        call("run", action="start", request_id="accepted", **changed)["error"]["code"]
        == "idempotency_conflict"
    )


def test_public_plan_continuation_keeps_new_work_and_requires_confirmation(tmp_path):
    host, runtime, call, _ = host_collection(tmp_path)
    dataset = runtime.opened.manifest.dataset_ref

    def plan(**request):
        if "request_id" in request:
            request["request_id"] = "request:" + request["request_id"]
        return host.call_tool(
            "mediasense.plan.work", dataset_ref=dataset, request=request
        )

    _, old, page = result(call, "first")
    work = plan(
        action="create",
        result_ref=old,
        request_id="plan-old",
        organization_preferences={"preserve_source_basename": True},
    )
    assert work["outcome"] == "ok", work
    saved = plan(
        action="update",
        work_ref=work["work_ref"],
        base_revision=work["revision"],
        request_id="notes",
        working_notes="Keep original basenames; review finer evidence before grouping.",
    )
    assert saved["outcome"] == "ok", saved
    previous = plan(
        action="inspect",
        work_ref=work["work_ref"],
        sections=["preferences", "working_notes", "content"],
    )
    selected = members(call, old, page["preparation"]["source_set"])["members"][:2]
    request = deepcopy(page["preparation"])
    request["profile"]["overrides"] = [
        {
            "source_set": {
                "kind": "explicit",
                "source_item_refs": [m["source_item_ref"] for m in selected],
            },
            "compression": None,
        }
    ]
    _, new, current = result(call, "local", prior_result_ref=old, **request)
    mapping = members(
        call, old, page["preparation"]["source_set"], target_result_ref=new
    )
    assert all(m["correspondence"]["status"] == "matched" for m in mapping["members"])
    refs = [m["correspondence"]["source_item_ref"] for m in mapping["members"]]
    evidence = call(
        "read",
        action="expand",
        result_ref=new,
        source_item_refs=refs[:2],
        include=["covering_evidence", "observations"],
    )
    assert "error" not in evidence, evidence
    successor = plan(
        action="create",
        result_ref=new,
        request_id="plan-new",
        organization_preferences=previous["sections"]["preferences"],
    )
    assert successor["work_ref"] != work["work_ref"]
    scope = current["preparation"]["source_set"]
    candidate = {
        "kind": "candidate",
        "result_ref": new,
        "scope": scope,
        "logical_root": "Media",
        "groups": [
            {
                "relative_path": ["Selected"],
                "members": scope,
                "source_naming": {"default": "preserve_source_basename"},
            }
        ],
        "other_outcomes": [],
        "decision_notes": [],
    }
    saved_new = plan(
        action="update",
        work_ref=successor["work_ref"],
        base_revision=successor["revision"],
        request_id="new-candidate",
        working_notes=previous["sections"]["working_notes"],
        organization_content=candidate,
    )
    assert saved_new["outcome"] == "ok", saved_new
    review = plan(
        action="inspect",
        work_ref=successor["work_ref"],
        sections=["content", "validation", "working_notes"],
    )
    assert review["sections"]["validation"]["seal_ready"] is True, review
    refused = plan(
        action="seal",
        work_ref=successor["work_ref"],
        revision=saved_new["revision"],
        candidate_content_identity=review["candidate_content_identity"],
        request_id="unconfirmed",
    )
    assert refused["error"]["code"] == "confirmation_required", refused
    old_again = plan(
        action="inspect",
        work_ref=work["work_ref"],
        sections=["preferences", "working_notes", "content"],
    )
    assert old_again["revision"] == previous["revision"]
    assert old_again["result_ref"] == old
