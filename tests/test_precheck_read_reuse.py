"""Trust, isolation and bounded work when repeatedly reading an immutable Result."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from threading import Barrier

import pytest

from mediasense.precheck import PrecheckReadTool, PrecheckRunTool
import mediasense.precheck.read as reading
import mediasense.precheck._read_projection as projection
from test_precheck_delivery import prepared
from test_precheck_delivery_regressions import request_for
from test_precheck_read_contract import check_semantics


def overwrite_retained(path, content):
    """Simulate external corruption only on this test's read-only published files."""
    mode = path.stat().st_mode & 0o777
    path.chmod(mode | 0o200)
    try:
        path.write_bytes(content)
    finally:
        path.chmod(mode)


def reader_case(tmp_path, monkeypatch):
    database, store, draft, _ = prepared(tmp_path)
    sealed = store.seal(draft)
    reader = PrecheckReadTool(database)
    validations = []
    original = reader._validate_package

    def validate(*args):
        validations.append(args[1])
        return original(*args)

    monkeypatch.setattr(reader, "_validate_package", validate)
    return database, store, draft, sealed, reader, validations


def test_pages_reuse_validation_and_return_detached_information(tmp_path, monkeypatch):
    _, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed, page={"limit": 1})
    first = reader.read(request)
    expected = deepcopy(first)
    first["items"][0]["observations"].clear()
    first["items"][0]["source_items"].clear()
    first["accounting"]["scope_condition"].clear()
    first["items"][0]["represents"]["source_count"] = -1
    assert reader.read(request) == expected
    seen = []
    while True:
        response = reader.read(request)
        check_semantics(request, response)
        seen.extend(item["evidence_ref"] for item in response["items"])
        cursor = response["page"]["next_cursor"]
        if cursor is None:
            break
        request = {**request, "page": {"limit": 1, "cursor": cursor}}
    assert len(seen) == len(set(seen)) == 3
    assert validations == [sealed.result_ref]


def test_cached_result_detects_same_size_changed_bytes_with_restored_mtime(
    tmp_path, monkeypatch
):
    _, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed)
    expected = reader.read(request)
    original = sealed.path.read_bytes()
    before = sealed.path.stat()
    changed = original.replace(b'"complete"', b'"completf"', 1)
    assert changed != original and len(changed) == len(original)
    overwrite_retained(sealed.path, changed)
    os.utime(sealed.path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert reader.read(request)["error"]["code"] == "result_untrusted"
    overwrite_retained(sealed.path, original)
    assert reader.read(request) == expected
    assert len(validations) == 2


@pytest.mark.parametrize(
    "change", ["replacement", "projection_revision", "validator_schema"]
)
def test_identity_and_interpretation_changes_revalidate(tmp_path, monkeypatch, change):
    _, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed)
    expected = reader.read(request)
    if change == "replacement":
        replacement = sealed.path.with_suffix(".replacement")
        replacement.write_bytes(sealed.path.read_bytes())
        replacement.replace(sealed.path)
    elif change == "projection_revision":
        monkeypatch.setattr(
            reading, "_READ_PROJECTION_REVISION", reading._READ_PROJECTION_REVISION + 1
        )
    else:
        from mediasense.runtime.resources import contract_validator

        validator = contract_validator(reader.name, "review")
        monkeypatch.setitem(validator.schema, "$comment", "reloaded schema identity")
    assert reader.read(request) == expected
    assert len(validations) == 2


@pytest.mark.parametrize("target", ["file", "directory", "escape"])
def test_cache_does_not_hide_unconfined_sealed_paths(tmp_path, monkeypatch, target):
    database, _, _, sealed, reader, _ = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed)
    reader.read(request)
    if target == "file":
        backup = tmp_path / "same-bytes.json"
        backup.write_bytes(sealed.path.read_bytes())
        sealed.path.unlink()
        sealed.path.symlink_to(backup)
    elif target == "directory":
        directory = sealed.path.parent
        backup = directory.with_name("moved-sealed")
        directory.rename(backup)
        directory.symlink_to(backup, target_is_directory=True)
    else:
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE sealed_results SET relative_path=? WHERE result_ref=?",
                (str(sealed.path), sealed.result_ref),
            )
    assert reader.read(request)["error"]["code"] == "result_untrusted"


def test_cached_graph_does_not_cache_image_availability(tmp_path, monkeypatch):
    _, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed, page={"limit": 1})
    first = reader.read(request)
    image = Path(first["items"][0]["access"]["locator"]["value"])
    original = image.read_bytes()
    overwrite_retained(image, b"corrupt")
    failed = reader.read(request)
    check_semantics(request, failed)
    assert failed["items"][0]["error"]["code"] == "evidence_unavailable"
    assert failed["page"] == first["page"]
    later = reader.read(
        {**request, "page": {"limit": 1, "cursor": failed["page"]["next_cursor"]}}
    )
    assert "error" not in later["items"][0]
    overwrite_retained(image, original)
    assert reader.read(request) == first
    assert len(validations) == 1


def test_changed_artifact_proof_invalidates_reuse(tmp_path, monkeypatch):
    database, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed, page={"limit": 1})
    first = reader.read(request)
    graph = reader._cached_result[2]
    artifact_id = graph.evidence_records[first["items"][0]["evidence_ref"]][
        "artifact_id"
    ]
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE artifacts SET digest=? WHERE artifact_id=?", ("0" * 64, artifact_id)
        )
    assert reader.read(request)["items"][0]["error"]["code"] == "evidence_unavailable"
    assert len(validations) == 2


def test_rendition_verification_timestamp_does_not_invalidate_result(
    tmp_path, monkeypatch
):
    database, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    expected = reader.read(request_for(sealed))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE artifacts SET last_verified_at='2026-09-11T00:00:00Z'"
        )
    assert reader.read(request_for(sealed)) == expected
    assert len(validations) == 1


def test_proof_change_during_validation_stays_a_local_evidence_failure(
    tmp_path, monkeypatch
):
    database, _, _, sealed, reader, _ = reader_case(tmp_path, monkeypatch)
    validate = reader._validate_package

    def change_proof(*args):
        graph = validate(*args)
        artifact_id = graph.evidence_records[graph.entry_evidence_refs[0]][
            "artifact_id"
        ]
        with sqlite3.connect(database) as connection:
            connection.execute(
                "UPDATE artifacts SET digest=? WHERE artifact_id=?",
                ("0" * 64, artifact_id),
            )
        return graph

    monkeypatch.setattr(reader, "_validate_package", change_proof)
    request = request_for(sealed)
    response = reader.read(request)
    check_semantics(request, response)
    assert response["items"][0]["error"]["code"] == "evidence_unavailable"
    assert all("error" not in item for item in response["items"][1:])
    assert reader._cached_result is None


def test_modification_during_a_cached_hash_is_detected(tmp_path, monkeypatch):
    _, _, _, sealed, reader, _ = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed)
    reader.read(request)
    before, original = sealed.path.stat(), sealed.path.read_bytes()
    raw_read = os.read
    changed = False

    def changing_read(descriptor, size):
        nonlocal changed
        data = raw_read(descriptor, size)
        observed = os.fstat(descriptor)
        if not changed and (observed.st_dev, observed.st_ino) == (
            before.st_dev,
            before.st_ino,
        ):
            changed = True
            overwrite_retained(sealed.path, original)
            os.utime(sealed.path, ns=(before.st_atime_ns, before.st_mtime_ns))
        return data

    monkeypatch.setattr(os, "read", changing_read)
    assert reader.read(request)["error"]["code"] == "result_untrusted"
    assert changed


@pytest.mark.parametrize(
    "change,code",
    [("duplicate_observation", "result_untrusted"), ("cycle", "result_inconsistent")],
)
def test_changed_but_rehashed_package_still_needs_semantic_validation(
    tmp_path, monkeypatch, change, code
):
    database, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed)
    reader.read(request)
    package = json.loads(sealed.path.read_bytes())
    if change == "duplicate_observation":
        observations = next(
            s["view"]["observations"]
            for s in package["sources"]
            if s["view"]["observations"]
        )
        observations.append(deepcopy(observations[0]))
    else:
        edge = next(
            r for r in package["relationships"] if r["relation"] == "derived_from"
        )
        edge["member"]["target"] = {"kind": "evidence", "ref": edge["origin"]}
    encoded = json.dumps(package, ensure_ascii=False).encode()
    overwrite_retained(sealed.path, encoded)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sealed_results SET digest=?, size_bytes=? WHERE result_ref=?",
            (hashlib.sha256(encoded).hexdigest(), len(encoded), sealed.result_ref),
        )
    assert reader.read(request)["error"]["code"] == code
    assert len(validations) == 2
    assert reader._cached_result is None


def test_invalid_cursor_keeps_bindings_and_does_not_open_images(tmp_path, monkeypatch):
    _, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    request = request_for(sealed, page={"limit": 1})
    first = reader.read(request)

    def forbidden(*args):
        raise AssertionError("An invalid cursor must not inspect images")

    monkeypatch.setattr(projection, "require_evidence_access", forbidden)
    for params in [
        {"page": {"limit": 1, "cursor": "bad"}},
        {"page": {"limit": 2, "cursor": first["page"]["next_cursor"]}},
        {
            "page": {"limit": 1, "cursor": first["page"]["next_cursor"]},
            "include": ["execution_boundary"],
        },
    ]:
        assert reader.read({**request, **params})["error"]["code"] == "invalid_cursor"
    assert len(validations) == 1


def test_concurrent_reads_validate_once_and_remain_independent(tmp_path, monkeypatch):
    _, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    ready = Barrier(4)

    def read_page():
        ready.wait(timeout=5)
        return reader.read(request_for(sealed))

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: read_page(), range(4)))
    assert all(result == results[0] for result in results)
    results[0]["items"].clear()
    assert len(results[1]["items"]) == 3
    assert validations == [sealed.result_ref]


def test_eviction_and_oversized_results_fall_back_to_validation(tmp_path, monkeypatch):
    _, store, draft, first, reader, validations = reader_case(tmp_path, monkeypatch)
    changed = replace(
        draft.evidence[0],
        observations=(
            *draft.evidence[0].observations,
            {"name": "extension", "status": "available", "value": "second result"},
        ),
    )
    second = store.seal(replace(draft, evidence=(changed, *draft.evidence[1:])))
    expected = reader.read(request_for(first))
    reader.read(request_for(second))
    assert reader.read(request_for(first)) == expected
    assert validations == [first.result_ref, second.result_ref, first.result_ref]
    monkeypatch.setattr(reading, "_MAX_CACHED_RESULT_BYTES", 0)
    reader.read(request_for(first))
    assert reader._cached_result is None
    assert reader.read(request_for(first)) == expected
    assert len(validations) == 4


def test_completed_status_and_read_share_validation(tmp_path, monkeypatch):
    database, _, _, sealed, reader, validations = reader_case(tmp_path, monkeypatch)
    first = reader.read(request_for(sealed))
    run = PrecheckRunTool(database, reader=reader)
    started = run.run(
        {
            "action": "start",
            "dataset_ref": "dataset:delivery",
            "request_id": "reuse-status",
        }
    )
    run_ref = started["run_ref"]
    assert run.complete_with_result(run_ref, sealed.result_ref)["state"] == "completed"
    request = {
        "action": "status",
        "dataset_ref": "dataset:delivery",
        "run_ref": run_ref,
        "include": ["accounting"],
    }
    status = run.run(request)
    assert status["result"] == first["result"]
    status["accounting"]["scope_condition"].clear()
    assert run.run(request)["accounting"]["scope_condition"]
    assert validations == [sealed.result_ref]
    overwrite_retained(sealed.path, b"corrupt")
    assert run.run(request)["error"]["code"] == "result_untrusted"


def test_runtime_assembly_shares_the_real_reader(tmp_path):
    from test_runtime_host import _opened_host_with_plan_ready_result

    host, dataset_ref, *_ = _opened_host_with_plan_ready_result(tmp_path)
    runtime = host._datasets[dataset_ref]
    assert runtime.precheck_run._reader is runtime.precheck_read


def test_byte_limited_page_only_checks_its_records_and_boundary_candidate(
    tmp_path, monkeypatch
):
    database, store, draft, _ = prepared(tmp_path)
    evidence = tuple(
        replace(
            e,
            observations=(
                *e.observations,
                {
                    "name": "retained_text",
                    "status": "available",
                    "value": "x" * 300_000,
                },
            ),
        )
        for e in draft.evidence
    )
    sealed = store.seal(replace(draft, evidence=evidence))
    reader = PrecheckReadTool(database)
    inspected = []
    original = projection.require_evidence_access

    def inspect(graph, ref):
        inspected.append(ref)
        return original(graph, ref)

    monkeypatch.setattr(projection, "require_evidence_access", inspect)
    request = request_for(sealed, page={"limit": 100})
    seen = []
    while True:
        inspected.clear()
        response = reader.read(request)
        check_semantics(request, response)
        assert len(response["items"]) == 1
        assert len(inspected) <= len(response["items"]) + 1
        seen.extend(item["evidence_ref"] for item in response["items"])
        cursor = response["page"]["next_cursor"]
        if cursor is None:
            break
        request = {**request, "page": {"limit": 100, "cursor": cursor}}
    assert seen == list(draft.entry_evidence)


@pytest.mark.parametrize("table", ["sealed_results", "artifacts"])
def test_cached_proof_must_still_name_a_supported_digest(tmp_path, monkeypatch, table):
    database, _, _, sealed, reader, _ = reader_case(tmp_path, monkeypatch)
    reader.read(request_for(sealed))
    with sqlite3.connect(database) as connection:
        connection.execute(f"UPDATE {table} SET digest_algorithm='unrecognized'")
    response = reader.read(request_for(sealed))
    if table == "sealed_results":
        assert response["error"]["code"] == "result_untrusted"
    else:
        assert all(
            item["error"]["code"] == "evidence_unavailable"
            for item in response["items"]
        )
