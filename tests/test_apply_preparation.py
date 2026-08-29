from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tracemalloc

import pytest
from jsonschema import Draft202012Validator

from mediasense.apply import (
    ApplyPreparationError,
    ApplyRunStore,
    IdempotencyConflict,
    SourceItemEvidence,
    SourceSetExpansion,
)


ROOT = Path(__file__).parents[1]
APPLY_RUN_SCHEMA = (
    ROOT / "docs" / "spec" / "spec-260829-0050-apply" / "apply-run.tool.json"
)


def _identity(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _plan() -> dict:
    content = {
        "contract": "mediasense.frozen-plan",
        "plan_ref": "frozen-plan:prepare-test",
        "result_ref": "precheck-result:prepare-test",
        "scope": {
            "kind": "explicit",
            "source_item_refs": ["source-item:a", "source-item:b", "source-item:c"],
        },
        "logical_root": "Media",
        "groups": [
            {
                "relative_path": ["Trip"],
                "members": {
                    "kind": "explicit",
                    "source_item_refs": ["source-item:a", "source-item:b"],
                },
                "source_naming": {
                    "default": "preserve_source_basename",
                    "overrides": [
                        {"source_item_ref": "source-item:b", "name": "renamed.jpg"}
                    ],
                },
            }
        ],
        "other_outcomes": [
            {
                "members": {
                    "kind": "explicit",
                    "source_item_refs": ["source-item:c"],
                },
                "outcome": "retain_current_organization",
            }
        ],
    }
    content_identity = _identity(content)
    return {
        "sealed_content": content,
        "seal": {
            "encoding_profile": "mediasense-json-strings-sha256-v1",
            "content_identity": content_identity,
            "final_confirmation": {
                "confirmed_content_identity": content_identity,
                "confirmed_at": "2026-08-29T12:00:00+08:00",
                "confirmed_by": "human:test",
            },
        },
    }


def _resolve(_result_ref: str, source_set: dict) -> SourceSetExpansion:
    assert source_set["kind"] == "explicit"
    return SourceSetExpansion(iter(source_set["source_item_refs"]), complete=True)


def _precheck_view(source_item_ref: str, relative_path: str, content: bytes) -> dict:
    return {
        "kind": "source_item",
        "ref": source_item_ref,
        "locator": {
            "kind": "source_root_relative_path",
            "source_root_ref": "source-root:test",
            "value": relative_path,
        },
        "observations": [
            {
                "name": "source_content_verification",
                "status": "available",
                "value": {
                    "profile": "sha256-full-v1",
                    "value": "sha256:" + hashlib.sha256(content).hexdigest(),
                    "size_bytes": len(content),
                    "observed_at": "2026-08-30T00:00:00+08:00",
                    "producer": "test-source-content-proof-v1",
                },
                "basis": "Test evidence sealed by the exact PreCheck Result.",
            }
        ],
    }


class _FakePrecheckRead:
    name = "mediasense.precheck.read"

    def __init__(self, views: list[dict]) -> None:
        self.views = {view["ref"]: view for view in views}
        self.requests: list[dict[str, object]] = []

    def read(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        result_ref = str(request["result_ref"])
        target = request["target"]
        assert request == {
            "result_ref": result_ref,
            "action": "inspect",
            "target": target,
        }
        source_item_ref = target["ref"]
        view = self.views.get(source_item_ref)
        if view is None:
            return {
                "outcome": "error",
                "result_ref": result_ref,
                "error": {"code": "target_not_found", "message": "missing"},
            }
        return {
            "outcome": "ok",
            "result_ref": result_ref,
            "action": "inspect",
            "target": view,
        }


def _fixture(tmp_path: Path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    state = tmp_path / "state"
    source.mkdir()
    destination.mkdir()
    state.mkdir()
    files = {
        "a.jpg": b"alpha\x00bytes",
        "b.jpg": b"beta\x01bytes",
        "c.jpg": b"retained",
    }
    for name, content in files.items():
        (source / name).write_bytes(content)
    views = [
        _precheck_view(f"source-item:{name[0]}", name, content)
        for name, content in files.items()
    ]
    # The retained item is accounted by PreCheck but is not selected for a
    # dangerous Apply effect, so the public contract need not prove its bytes.
    views[-1].pop("observations")
    return source, destination, state, files, _FakePrecheckRead(views)


def _tree_facts(root: Path) -> list[tuple[str, int, str]]:
    facts = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        facts.append((relative, path.stat().st_mode, digest))
    return facts


def _prepare(tmp_path: Path):
    source, destination, state, files, reader = _fixture(tmp_path)
    store = ApplyRunStore.initialize(state / "apply.sqlite3")
    before_source = _tree_facts(source)
    before_destination = _tree_facts(destination)
    run = store.prepare_forward(
        request_id="request:prepare-1",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    return (
        store,
        run,
        source,
        destination,
        files,
        reader,
        before_source,
        before_destination,
    )


def test_prepare_is_durable_deterministic_and_has_zero_media_effects(
    tmp_path: Path,
) -> None:
    (
        store,
        run,
        source,
        destination,
        _files,
        reader,
        before_source,
        before_destination,
    ) = _prepare(tmp_path)

    assert run.state == "ready_for_authorization"
    assert run.prepared_revision
    assert run.prepared_content_identity
    assert _tree_facts(source) == before_source
    assert _tree_facts(destination) == before_destination
    assert [request["target"]["ref"] for request in reader.requests] == [
        "source-item:a",
        "source-item:b",
    ]

    reopened = ApplyRunStore(store.database_path)
    assert reopened.get_run(run.run_ref) == run
    repeated = reopened.prepare_forward(
        request_id="request:prepare-1",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    assert repeated == run

    items = reopened.iter_items(run.run_ref, limit=2)
    assert len(items) == 2
    assert items[0]["source_item_ref"] == "source-item:a"
    assert items[0]["intended_target"] == str(destination / "Media" / "Trip" / "a.jpg")
    assert items[1]["intended_target"] == str(
        destination / "Media" / "Trip" / "renamed.jpg"
    )
    assert len(reopened.iter_items(run.run_ref, after_ordinal=1, limit=2)) == 1


def test_ready_status_conforms_to_active_contract(tmp_path: Path) -> None:
    store, run, *_rest = _prepare(tmp_path)
    status = store.status(run.run_ref)
    schema = json.loads(APPLY_RUN_SCHEMA.read_text(encoding="utf-8"))["outputSchema"]
    Draft202012Validator(schema).validate(status)
    assert status["summary"]["plan_scope_items"] == 3
    assert status["summary"]["materialization_operations"] == 2
    assert status["summary"]["no_effect_items"] == 1
    assert status["summary"]["verified_sources"] == 2
    assert status["allowed_actions"] == ["execute", "cancel"]


def test_prepare_rejects_idempotency_key_reuse(tmp_path: Path) -> None:
    store, _run, source, destination, _files, reader, *_rest = _prepare(tmp_path)
    changed = _plan()
    changed["sealed_content"]["logical_root"] = "Changed"
    changed_identity = _identity(changed["sealed_content"])
    changed["seal"]["content_identity"] = changed_identity
    changed["seal"]["final_confirmation"]["confirmed_content_identity"] = (
        changed_identity
    )
    with pytest.raises(IdempotencyConflict):
        store.prepare_forward(
            request_id="request:prepare-1",
            frozen_plan=changed,
            source_roots={"source-root:test": source},
            destination_parent=destination,
            resolve_source_set=_resolve,
            precheck_read=reader,
        )


def test_stale_authorization_coordinates_are_rejected(tmp_path: Path) -> None:
    store, run, *_rest = _prepare(tmp_path)
    store.assert_authorization_binding(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
    )
    with pytest.raises(ApplyPreparationError, match="revision mismatch"):
        store.assert_authorization_binding(
            run_ref=run.run_ref,
            prepared_revision="prepared-revision:stale",
            prepared_content_identity=run.prepared_content_identity,
        )
    with pytest.raises(ApplyPreparationError, match="content identity mismatch"):
        store.assert_authorization_binding(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity="sha256:" + "0" * 64,
        )


def test_prepare_blocks_source_changed_from_precheck_evidence(tmp_path: Path) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    (source / "b.jpg").write_bytes(b"changed after PreCheck")
    store = ApplyRunStore.initialize(state / "apply.sqlite3")
    run = store.prepare_forward(
        request_id="request:changed-source",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    assert run.state == "blocked"
    status = store.status(run.run_ref)
    assert status["summary"]["blockers"] == 1
    assert any(reason["code"] == "source_unverifiable" for reason in status["reasons"])
    assert (source / "b.jpg").read_bytes() == b"changed after PreCheck"
    assert list(destination.iterdir()) == []

    (source / "b.jpg").write_bytes(b"beta\x01bytes")
    resumed = store.prepare_forward(
        request_id="request:changed-source",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    assert resumed.run_ref == run.run_ref
    assert resumed.state == "ready_for_authorization"


@pytest.mark.parametrize(
    ("case", "expected_code"),
    [
        ("missing", "source_verification_missing"),
        ("not_checked", "source_verification_unavailable"),
        ("failed", "source_verification_unavailable"),
        ("unknown_profile", "source_verification_profile_unsupported"),
        ("missing_basis", "source_verification_invalid"),
        ("missing_producer", "source_verification_invalid"),
        ("digest_mismatch", "source_unverifiable"),
        ("size_mismatch", "source_unverifiable"),
        ("root_unbound", "source_root_unbound"),
        ("root_escape", "source_locator_invalid"),
        ("path_alias", "source_unverifiable"),
        ("missing_source_item", "precheck_read_failed"),
    ],
)
def test_selected_move_fails_closed_on_unusable_precheck_evidence(
    tmp_path: Path,
    case: str,
    expected_code: str,
) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    selected = reader.views["source-item:a"]
    observation = selected["observations"][0]
    if case == "missing":
        selected.pop("observations")
    elif case in {"not_checked", "failed"}:
        observation["status"] = case
        observation.pop("value")
    elif case == "unknown_profile":
        observation["value"]["profile"] = "future-proof-v2"
    elif case == "missing_basis":
        observation.pop("basis")
    elif case == "missing_producer":
        observation["value"].pop("producer")
    elif case == "digest_mismatch":
        observation["value"]["value"] = "sha256:" + "0" * 64
    elif case == "size_mismatch":
        observation["value"]["size_bytes"] += 1
    elif case == "root_unbound":
        selected["locator"]["source_root_ref"] = "source-root:missing"
    elif case == "root_escape":
        selected["locator"]["value"] = "../escape.jpg"
    elif case == "path_alias":
        selected["locator"]["value"] = "A.JPG"
    elif case == "missing_source_item":
        reader.views.pop("source-item:a")

    before_source = _tree_facts(source)
    before_destination = _tree_facts(destination)
    store = ApplyRunStore.initialize(state / "apply.sqlite3")
    run = store.prepare_forward(
        request_id=f"request:negative-{case}",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )

    assert run.state == "blocked"
    status = store.status(run.run_ref)
    assert any(reason["code"] == expected_code for reason in status["reasons"])
    assert _tree_facts(source) == before_source
    assert _tree_facts(destination) == before_destination


def test_prepare_blocks_source_changed_during_full_content_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    changing = source / "a.jpg"
    real_open = Path.open

    class MutatingRead:
        def __init__(self, handle) -> None:
            self.handle = handle
            self.changed = False

        def __enter__(self):
            self.handle.__enter__()
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def read(self, size=-1):
            chunk = self.handle.read(size)
            if not chunk and not self.changed:
                self.changed = True
                with real_open(changing, "wb") as writer:
                    writer.write(b"changed during verification")
            return chunk

    def changing_open(path: Path, *args, **kwargs):
        handle = real_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if path == changing and mode == "rb":
            return MutatingRead(handle)
        return handle

    monkeypatch.setattr(Path, "open", changing_open)
    store = ApplyRunStore.initialize(state / "apply.sqlite3")
    run = store.prepare_forward(
        request_id="request:source-changed-during-read",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )

    assert run.state == "blocked"
    assert any(
        reason["code"] == "source_unverifiable"
        for reason in store.status(run.run_ref)["reasons"]
    )
    assert list(destination.iterdir()) == []


def test_prepare_blocks_colliding_targets_without_writes(tmp_path: Path) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    plan = _plan()
    overrides = plan["sealed_content"]["groups"][0]["source_naming"]["overrides"]
    overrides.extend(
        [
            {"source_item_ref": "source-item:a", "name": "same.jpg"},
        ]
    )
    overrides[0]["name"] = "SAME.jpg"
    plan_identity = _identity(plan["sealed_content"])
    plan["seal"]["content_identity"] = plan_identity
    plan["seal"]["final_confirmation"]["confirmed_content_identity"] = plan_identity
    store = ApplyRunStore.initialize(state / "apply.sqlite3")
    run = store.prepare_forward(
        request_id="request:collision",
        frozen_plan=plan,
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    assert run.state == "blocked"
    assert list(destination.iterdir()) == []


def test_prepare_rejects_wrong_current_root_even_when_paths_exist(
    tmp_path: Path,
) -> None:
    _source, destination, state, _files, reader = _fixture(tmp_path)
    wrong_root = tmp_path / "wrong-volume"
    wrong_root.mkdir()
    (wrong_root / "a.jpg").write_bytes(b"unrelated alpha")
    (wrong_root / "b.jpg").write_bytes(b"unrelated beta")
    before = _tree_facts(wrong_root)
    store = ApplyRunStore.initialize(state / "apply.sqlite3")

    run = store.prepare_forward(
        request_id="request:wrong-current-root",
        frozen_plan=_plan(),
        source_roots={"source-root:test": wrong_root},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )

    assert run.state == "blocked"
    assert any(
        reason["code"] == "source_unverifiable"
        for reason in store.status(run.run_ref)["reasons"]
    )
    assert _tree_facts(wrong_root) == before
    assert list(destination.iterdir()) == []


def test_prepare_rejects_two_root_refs_bound_to_one_current_root(
    tmp_path: Path,
) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    store = ApplyRunStore.initialize(state / "apply.sqlite3")

    run = store.prepare_forward(
        request_id="request:root-alias",
        frozen_plan=_plan(),
        source_roots={
            "source-root:test": source,
            "source-root:alias": source,
        },
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )

    assert run.state == "blocked"
    reasons = {reason["code"] for reason in store.status(run.run_ref)["reasons"]}
    assert "source_root_alias_conflict" in reasons
    assert list(destination.iterdir()) == []


def test_prepare_rejects_precheck_response_bound_to_another_result(
    tmp_path: Path,
) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)

    class WrongResultRead:
        name = "mediasense.precheck.read"

        def read(self, request):
            response = reader.read(request)
            response["result_ref"] = "precheck-result:different"
            return response

    store = ApplyRunStore.initialize(state / "apply.sqlite3")
    run = store.prepare_forward(
        request_id="request:wrong-result-response",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=WrongResultRead(),
    )

    assert run.state == "blocked"
    assert any(
        reason["code"] == "precheck_read_mismatch"
        for reason in store.status(run.run_ref)["reasons"]
    )
    assert list(destination.iterdir()) == []


def test_source_evidence_uses_accepted_precheck_contract() -> None:
    view = _precheck_view("source-item:a", "a.jpg", b"a")
    evidence = SourceItemEvidence.from_precheck_view(
        result_ref="precheck-result:prepare-test", view=view
    )
    assert evidence.source_root_ref == "source-root:test"
    assert evidence.relative_path == "a.jpg"
    assert evidence.verification.profile == "sha256-full-v1"
    assert evidence.verification.value == "sha256:" + hashlib.sha256(b"a").hexdigest()
    assert evidence.verification.size_bytes == 1


def test_interrupted_prepare_resumes_from_persisted_item_facts(tmp_path: Path) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    store = ApplyRunStore.initialize(state / "apply.sqlite3")

    class InterruptingRead:
        name = "mediasense.precheck.read"

        def __init__(self) -> None:
            self.calls = 0

        def read(self, request):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("injected interruption")
            return reader.read(request)

    with pytest.raises(RuntimeError, match="injected interruption"):
        store.prepare_forward(
            request_id="request:interrupted",
            frozen_plan=_plan(),
            source_roots={"source-root:test": source},
            destination_parent=destination,
            resolve_source_set=_resolve,
            precheck_read=InterruptingRead(),
        )

    # The Run and first verified item survived; retry converges on that Run.
    persisted = store.get_run_for_request("request:interrupted")
    assert persisted.state == "preparing"
    run_ref = persisted.run_ref
    assert store.iter_items(run_ref, limit=10)[0]["preparation_status"] == "verified"

    resumed = store.prepare_forward(
        request_id="request:interrupted",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    assert resumed.run_ref == run_ref
    assert resumed.state == "ready_for_authorization"


def test_overlapping_active_runs_are_not_both_authorizable(tmp_path: Path) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    other_destination = tmp_path / "other-destination"
    other_destination.mkdir()
    store = ApplyRunStore.initialize(state / "apply.sqlite3")
    first = store.prepare_forward(
        request_id="request:first",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    second = store.prepare_forward(
        request_id="request:second",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=other_destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    assert first.state == "ready_for_authorization"
    assert second.state == "blocked"
    status = store.status(second.run_ref)
    Draft202012Validator(
        json.loads(APPLY_RUN_SCHEMA.read_text(encoding="utf-8"))["outputSchema"]
    ).validate(status)
    assert any(reason["code"] == "concurrency_conflict" for reason in status["reasons"])


def test_prepared_identity_is_stable_across_stores(tmp_path: Path) -> None:
    source, destination, state, _files, reader = _fixture(tmp_path)
    first_store = ApplyRunStore.initialize(state / "first.sqlite3")
    second_store = ApplyRunStore.initialize(state / "second.sqlite3")
    first = first_store.prepare_forward(
        request_id="request:first-store",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    second = second_store.prepare_forward(
        request_id="request:second-store",
        frozen_plan=_plan(),
        source_roots={"source-root:test": source},
        destination_parent=destination,
        resolve_source_set=_resolve,
        precheck_read=reader,
    )
    assert first.prepared_content_identity == second.prepared_content_identity
    assert first.prepared_revision == second.prepared_revision


def test_pre_execution_cancel_is_idempotent_and_proves_zero_effects(
    tmp_path: Path,
) -> None:
    store, run, source, destination, *_rest = _prepare(tmp_path)
    source_before = _tree_facts(source)
    destination_before = _tree_facts(destination)
    cancelled = store.cancel_before_execution(run.run_ref)
    assert cancelled.state == "cancelled"
    assert store.cancel_before_execution(run.run_ref) == cancelled
    status = store.status(run.run_ref)
    Draft202012Validator(
        json.loads(APPLY_RUN_SCHEMA.read_text(encoding="utf-8"))["outputSchema"]
    ).validate(status)
    assert status["guaranteed_zero_media_effects"] is True
    assert status["allowed_actions"] == []
    assert _tree_facts(source) == source_before
    assert _tree_facts(destination) == destination_before


@pytest.mark.scale
def test_100k_operation_ledger_traversal_is_bounded(tmp_path: Path) -> None:
    count = 100_000
    refs = [f"source-item:{index:06d}" for index in range(count)]
    content = {
        "contract": "mediasense.frozen-plan",
        "plan_ref": "frozen-plan:scale-100k",
        "result_ref": "precheck-result:scale-100k",
        "scope": {"kind": "explicit", "source_item_refs": refs},
        "logical_root": "Media",
        "groups": [
            {
                "relative_path": ["Scale"],
                "members": {"kind": "explicit", "source_item_refs": refs},
                "source_naming": {"default": "preserve_source_basename"},
            }
        ],
        "other_outcomes": [],
    }
    content_identity = _identity(content)
    plan = {
        "sealed_content": content,
        "seal": {
            "encoding_profile": "mediasense-json-strings-sha256-v1",
            "content_identity": content_identity,
            "final_confirmation": {
                "confirmed_content_identity": content_identity,
                "confirmed_at": "2026-08-29T12:00:00+08:00",
                "confirmed_by": "human:test",
            },
        },
    }
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    store = ApplyRunStore.initialize(tmp_path / "state" / "apply.sqlite3")

    class StopBeforeVerification:
        name = "mediasense.precheck.read"

        def read(self, _request):
            raise RuntimeError("stop after ledger staging")

    with pytest.raises(RuntimeError, match="stop after ledger staging"):
        store.prepare_forward(
            request_id="request:scale-100k",
            frozen_plan=plan,
            source_roots={"source-root:test": source},
            destination_parent=destination,
            resolve_source_set=_resolve,
            precheck_read=StopBeforeVerification(),
        )
    run = store.get_run_for_request("request:scale-100k")
    assert run.state == "preparing"

    tracemalloc.start()
    page = store.iter_items(run.run_ref, limit=1_000)
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert len(page) == 1_000
    assert peak < 8 * 1024 * 1024
    assert store.status(run.run_ref)["progress"]["planned_operations"] == count
