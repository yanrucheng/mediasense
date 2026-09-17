"""B profile: bounded source evidence, object continuity, and trusted Host entry."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import anyio
from mcp import types
import pytest

from mediasense.apply import ApplyConfirmationContext, ApplyRunTool
from mediasense.apply.preparation import _verify_source, VerificationBasis
import mediasense.apply.filesystem as fs
from mediasense.runtime.mcp_host import create_mcp_server
from test_apply_preparation import _prepare, _candidate_digest, _precheck_view
from test_apply_execution import (
    _executor,
    _execute_prepared,
    APPLY_SPEC,
    FROZEN_PLAN_SCHEMA,
)


def _basis(content):
    observation = _precheck_view("source-item:a", "a", content)["observations"][0]
    return VerificationBasis(**observation["value"], basis=observation["basis"])


@pytest.mark.parametrize("size", [0, 1, 12287, 12288, 12289, 8 * 1024 * 1024])
def test_source_read_is_bounded_and_matches_independent_algorithm(
    tmp_path, monkeypatch, size
):
    data = bytes(range(256)) * (size // 256) + bytes(range(size % 256))
    path = tmp_path / "media"
    path.write_bytes(data)
    real_open = Path.open
    reads = []

    class ReadCounter:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def read(self, size=-1):
            assert 0 <= size <= 12288
            result = self.handle.read(size)
            reads.append(len(result))
            return result

        def seek(self, offset):
            return self.handle.seek(offset)

    def counted(path_, *args, **kwargs):
        handle = real_open(path_, *args, **kwargs)
        return ReadCounter(handle) if path_ == path else handle

    monkeypatch.setattr(Path, "open", counted)
    observed = _verify_source(path, tmp_path, _basis(data))
    assert observed["digest"] == _candidate_digest(data)
    assert sum(reads) == min(size, 12288)


def test_small_file_growth_cannot_expand_the_read_budget(tmp_path, monkeypatch):
    path = tmp_path / "media"
    path.write_bytes(b"a")
    real_open = Path.open
    reads = []

    class GrowingRead:
        def __enter__(self):
            with real_open(path, "ab") as writer:
                writer.write(b"b" * 100000)
            self.handle = real_open(path, "rb")
            return self

        def __exit__(self, *args):
            self.handle.close()

        def read(self, size):
            value = self.handle.read(size)
            reads.append(len(value))
            return value

    monkeypatch.setattr(
        Path,
        "open",
        lambda p, *a, **kw: GrowingRead() if p == path else real_open(p, *a, **kw),
    )
    with pytest.raises(ValueError, match="changed"):
        _verify_source(path, tmp_path, _basis(b"a"))
    assert reads == [1]


def test_full_only_evidence_does_not_trigger_a_same_volume_scan(tmp_path, monkeypatch):
    path = tmp_path / "media"
    path.write_bytes(b"a")
    basis = VerificationBasis(
        "sha256-full-v1",
        "sha256:" + "0" * 64,
        1,
        "2026-09-17T00:00:00Z",
        "test",
        "sealed evidence",
    )
    monkeypatch.setattr(
        Path, "open", lambda *a, **kw: pytest.fail("must reject before content I/O")
    )
    with pytest.raises(ValueError, match="full-only"):
        _verify_source(path, tmp_path, basis)


def test_unsampled_change_before_preparation_is_an_explicit_limitation(tmp_path):
    data = b"a" * 40000
    path = tmp_path / "media"
    path.write_bytes(data)
    with path.open("r+b") as handle:
        handle.seek(8000)
        handle.write(b"b")
    # No old stat exists in this Result. Finite evidence cannot detect this.
    assert _verify_source(path, tmp_path, _basis(data))["digest"] == _candidate_digest(
        data
    )


def test_restored_mtime_does_not_hide_post_preparation_write(tmp_path):
    store, run, source, *_ = _prepare(tmp_path)
    path = source / "a.jpg"
    old = path.stat()
    path.write_bytes(b"x" * old.st_size)
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    status = _executor(tmp_path, store).execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:ctime",
        authorization_binding="test:human",
    )
    assert status["state"] == "needs_attention"
    assert path.exists()


@pytest.mark.parametrize(
    "window",
    [
        "before_target_sync",
        "before_source_sync",
        "after_both_syncs",
        "after_effect_before_record",
    ],
)
def test_sync_and_record_interruptions_recover_without_content_reads(
    tmp_path, monkeypatch, window
):
    store, run, source, destination, *_ = _prepare(tmp_path)
    real_sync = fs._fsync_directory
    hit = False
    calls = []

    def sync(path):
        nonlocal hit
        # Ignore directory creation; trigger only once an item has moved.
        moved = (destination / "Media/Trip/a.jpg").exists()
        calls.append(path)
        if (
            moved
            and not hit
            and (
                (window == "before_target_sync" and path == destination / "Media/Trip")
                or (window == "before_source_sync" and path == source)
            )
        ):
            hit = True
            raise RuntimeError("interrupt")
        real_sync(path)
        if moved and not hit and window == "after_both_syncs" and path == source:
            hit = True
            raise RuntimeError("interrupt")

    def fault(point, _item):
        nonlocal hit
        if not hit and window == point:
            hit = True
            raise RuntimeError("interrupt")

    monkeypatch.setattr(fs, "_fsync_directory", sync)
    real_open = Path.open

    def deny_media(p, *args, **kwargs):
        assert p.suffix != ".jpg", "effect/recovery must not open media content"
        return real_open(p, *args, **kwargs)

    monkeypatch.setattr(Path, "open", deny_media)
    executor = _executor(tmp_path, store, fault_hook=fault)
    with pytest.raises(RuntimeError, match="interrupt"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:interrupt",
            authorization_binding="test:human",
        )
    assert hit
    restarted = _executor(tmp_path, store)
    restarted.advance(run.run_ref)
    status = store.status(run.run_ref)
    assert status["state"] == "closed"
    receipt = restarted.receipt_store.read(status["published_receipt"]["receipt_ref"])
    rows = receipt["sealed_content"]["operation_ledger"]["items"]
    assert all(row["attempts"] == 1 for row in rows)
    assert all(
        json.loads(row["verification"]["basis"])["type"] == "regular" for row in rows
    )
    assert calls.count(source) >= 2


@pytest.mark.parametrize(
    "reality", ["wrong_target", "both_present", "neither_present", "source_replaced"]
)
def test_ambiguous_recovery_never_claims_completion(tmp_path, reality):
    store, run, source, destination, files, *_ = _prepare(tmp_path)

    def fault(point, _item):
        if point == "after_intent":
            raise RuntimeError("interrupt")

    with pytest.raises(RuntimeError):
        _executor(tmp_path, store, fault_hook=fault).execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:interrupt",
            authorization_binding="test:human",
        )
    path, target = source / "a.jpg", destination / "Media/Trip/a.jpg"
    if reality in {"wrong_target", "both_present"}:
        target.write_bytes(files["a.jpg"])
    if reality != "both_present":
        path.rename(source / "retained-original")
    if reality == "source_replaced":
        path.write_bytes(files["a.jpg"])
    _executor(tmp_path, store).advance(run.run_ref)
    status = store.status(run.run_ref)
    assert status["state"] == "needs_attention"
    assert (
        store.iter_items(run.run_ref)[0]["execution_status"] != "completed_and_verified"
    )


def test_rewind_rejects_same_bytes_in_a_replacement_object(tmp_path):
    store, executor, status, _, destination, *_ = _execute_prepared(tmp_path)
    receipt = executor.receipt_store.read(status["published_receipt"]["receipt_ref"])
    path = destination / "Media/Trip/a.jpg"
    data = path.read_bytes()
    path.rename(path.with_suffix(".retained"))
    path.write_bytes(data)
    rewind = store.prepare_rewind(
        request_id="request:rewind-replaced",
        receipt=receipt,
        now=datetime(2026, 8, 30, 1, 30, tzinfo=timezone.utc),
    )
    assert rewind.state == "blocked"


def test_object_replaced_between_check_and_rename_stops_after_effect(
    tmp_path, monkeypatch
):
    store, run, source, destination, *_ = _prepare(tmp_path)
    real_rename = fs.rename_exclusive

    def swap_then_move(old, new):
        info = old.stat()
        data = old.read_bytes()
        old.rename(old.with_suffix(".retained"))
        old.write_bytes(data)
        os.utime(old, ns=(info.st_atime_ns, info.st_mtime_ns))
        real_rename(old, new)

    monkeypatch.setattr(fs, "rename_exclusive", swap_then_move)
    status = _executor(tmp_path, store).execute(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:race",
        authorization_binding="test:human",
    )
    assert status["state"] == "needs_attention"
    assert (destination / "Media/Trip/a.jpg").exists()
    assert (source / "b.jpg").exists()
    item = store.iter_items(run.run_ref)[0]
    assert item["execution_status"] == "intent"
    assert item["postcondition_result"] == "indeterminate"


def test_result_journal_failure_recovers_existing_rename(tmp_path):
    import sqlite3

    store, run, source, _, *_ = _prepare(tmp_path)
    with store._connect() as connection:
        connection.execute("""CREATE TRIGGER fail_result BEFORE UPDATE OF execution_status ON run_items
                            WHEN NEW.execution_status = 'completed_and_verified'
                            BEGIN SELECT RAISE(ABORT, 'controlled result journal failure'); END""")
        connection.commit()
    executor = _executor(tmp_path, store)
    with pytest.raises(sqlite3.IntegrityError, match="controlled result"):
        executor.execute(
            run_ref=run.run_ref,
            prepared_revision=run.prepared_revision,
            prepared_content_identity=run.prepared_content_identity,
            request_id="request:result-failure",
            authorization_binding="test:human",
        )
    assert not (source / "a.jpg").exists()
    assert store.iter_items(run.run_ref)[0]["execution_status"] == "intent"
    with store._connect() as connection:
        connection.execute("DROP TRIGGER fail_result")
        connection.commit()
    executor.advance(run.run_ref)
    assert store.status(run.run_ref)["state"] == "closed"
    assert store.iter_items(run.run_ref)[0]["attempts"] == 1


def _mcp_fixture(tmp_path):
    store, run, source, destination, _, reader, *_ = _prepare(tmp_path)
    tool = ApplyRunTool(
        tmp_path / "tool",
        reader,
        run_schema_path=APPLY_SPEC / "apply-run.tool.json",
        frozen_plan_schema_path=FROZEN_PLAN_SCHEMA,
        receipt_schema_path=APPLY_SPEC / "apply-receipt.schema.json",
    )
    tool.run_store = store
    tool.executor.run_store = store
    request = dict(
        action="execute",
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:mcp-confirm",
    )

    class Host:
        def call_tool(self, name, *, dataset_ref, request, authority=None):
            assert name == "mediasense.apply.run"
            context = (
                None
                if authority is None
                else ApplyConfirmationContext(
                    authority["principal_ref"],
                    authority["confirmed_content_identity"],
                    datetime.fromisoformat(authority["confirmed_at"]),
                )
            )
            return tool.handle(request, confirmation=context)

    server = create_mcp_server(Host())
    return server, tool, request, source, destination


@pytest.mark.parametrize(
    "answer", ["accept", "decline", "cancel", "unavailable", "forged"]
)
def test_mcp_confirmation_and_exact_replay(tmp_path, answer):
    server, tool, request, source, destination = _mcp_fixture(tmp_path)
    prompts = []

    class Session:
        client_capabilities = SimpleNamespace(elicitation=SimpleNamespace(form={}))

        async def elicit_form(self, message, schema, **kwargs):
            prompts.append(message)
            return SimpleNamespace(action=answer)

    async def scenario():
        entry = server.get_request_handler("tools/call")
        args = {"dataset_ref": "dataset:test", "request": request}
        if answer == "forged":
            args["authority"] = dict(
                principal_ref="human:fake",
                confirmed_content_identity=request["prepared_content_identity"],
                confirmed_at="2026-09-17T00:00:00Z",
            )
        context = (
            None
            if answer == "unavailable"
            else SimpleNamespace(session=Session(), request_id=1)
        )
        first = await entry.handler(
            context,
            types.CallToolRequestParams(name="mediasense.apply.run", arguments=args),
        )
        if answer == "accept":
            assert first.structured_content["outcome"] == "accepted"
            assert len(prompts) == 1
            assert (
                str(destination) in prompts[0]
                and "filesystem_identity_and_location" in prompts[0]
            )
            tool.run_pending(request["run_ref"])
            second = await entry.handler(
                None,
                types.CallToolRequestParams(
                    name="mediasense.apply.run", arguments=args
                ),
            )
            assert second.structured_content["observed_state"] == "closed"
            assert len(prompts) == 1
            assert not (source / "a.jpg").exists()
        else:
            assert first.structured_content["outcome"] == "error"
            assert (source / "a.jpg").exists()
            assert not list(destination.iterdir())

    anyio.run(scenario)


def test_mcp_schema_has_no_apply_authority(tmp_path):
    server, *_ = _mcp_fixture(tmp_path)

    async def scenario():
        listing = await server.get_request_handler("tools/list").handler(None, None)
        for tool in listing.tools:
            if tool.name.startswith("mediasense.apply."):
                assert "authority" not in tool.input_schema["properties"]

    anyio.run(scenario)


def test_confirmation_cannot_follow_changed_prepared_content(tmp_path):
    server, tool, request, source, destination = _mcp_fixture(tmp_path)

    class Session:
        client_capabilities = SimpleNamespace(elicitation=SimpleNamespace(form={}))

        async def elicit_form(self, *args, **kwargs):
            with tool.run_store._connect() as connection:
                connection.execute(
                    "UPDATE runs SET prepared_content_identity = ? WHERE run_ref = ?",
                    ("sha256:" + "0" * 64, request["run_ref"]),
                )
                connection.commit()
            return SimpleNamespace(action="accept")

    async def scenario():
        response = await server.get_request_handler("tools/call").handler(
            SimpleNamespace(session=Session(), request_id=1),
            types.CallToolRequestParams(
                name="mediasense.apply.run",
                arguments={"dataset_ref": "dataset:test", "request": request},
            ),
        )
        assert response.structured_content["outcome"] == "error"

    anyio.run(scenario)
    assert (source / "a.jpg").exists() and not list(destination.iterdir())


def test_resolved_source_projection_is_reused_and_invalid_projection_is_rejected():
    from mediasense.apply.preparation import _read_source_item, SourceEvidenceError

    class NoExpansion:
        def read(self, request):
            pytest.fail("complete resolve evidence must not be expanded again")

    view = _precheck_view("source-item:a", "a", b"a")
    result = _read_source_item(
        precheck_read=NoExpansion(),
        result_ref="precheck-result:test",
        source_item_ref="source-item:a",
        resolved_source_views={"source-item:a": view},
    )
    assert result.verification.value == _candidate_digest(b"a")
    view["observations"][0]["value"] = None
    with pytest.raises(SourceEvidenceError):
        _read_source_item(
            precheck_read=NoExpansion(),
            result_ref="precheck-result:test",
            source_item_ref="source-item:a",
            resolved_source_views={"source-item:a": view},
        )


@pytest.mark.parametrize(
    "window",
    [
        "after_intent",
        "after_effect_before_record",
        "after_receipt_publish_before_close",
        "before_directory_sync",
        "after_result_commit",
    ],
)
def test_abrupt_process_exit_recovers_same_effects(tmp_path, window):
    store, run, source, destination, *_ = _prepare(tmp_path)
    executor = _executor(tmp_path, store)
    executor.authorize(
        run_ref=run.run_ref,
        prepared_revision=run.prepared_revision,
        prepared_content_identity=run.prepared_content_identity,
        request_id="request:process-exit",
        authorization_binding="test:human",
    )
    script = """
import os, sys
from pathlib import Path
from mediasense.apply import ApplyRunStore
import mediasense.apply.filesystem as fs
from test_apply_execution import _executor
root, run_ref, window = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
store = ApplyRunStore(root / "state/apply.sqlite3")
real_sync = fs._fsync_directory
def sync(path):
    if window == "before_directory_sync" and (root / "destination/Media/Trip/a.jpg").exists():
        os._exit(42)
    real_sync(path)
fs._fsync_directory = sync
def fault(point, item):
    if point == window:
        os._exit(42)
executor = _executor(root, store, fault_hook=fault)
record = executor._record_observation
def record_then_exit(*args, **kwargs):
    record(*args, **kwargs)
    if window == "after_result_commit":
        os._exit(42)
executor._record_observation = record_then_exit
executor.advance(run_ref)
"""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path), run.run_ref, window],
        env={**os.environ, "PYTHONPATH": f"{root / 'src'}:{root / 'tests'}"},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 42, result.stderr
    restarted = _executor(tmp_path, store)
    restarted.mark_owner_interrupted(run.run_ref)
    assert store.status(run.run_ref)["state"] == "needs_attention"
    restarted.resume(run.run_ref)
    restarted.advance(run.run_ref)
    status = store.status(run.run_ref)
    assert status["state"] == "closed"
    assert not (source / "a.jpg").exists()
    assert (destination / "Media/Trip/a.jpg").exists()
    receipt = restarted.receipt_store.read(status["published_receipt"]["receipt_ref"])
    assert receipt["sealed_content"]["accounting"]["completed_and_verified"] == 2


def test_cli_rejects_self_authored_apply_authority_before_dataset_open(
    tmp_path, capsys
):
    from mediasense.cli import run

    result = run(
        [
            "tools",
            "call",
            "mediasense.apply.run",
            "--source",
            str(tmp_path / "missing"),
            "--request",
            '{"action":"execute"}',
            "--authority",
            '{"principal_ref":"human:fake"}',
            "--json",
        ]
    )
    assert result == 2
    assert "invalid_invocation" in capsys.readouterr().out


def test_legacy_apply_store_is_not_silently_migrated(tmp_path):
    import sqlite3
    from mediasense.runtime.dataset import DatasetResolver, DatasetOpenError

    source, workspace = tmp_path / "source", tmp_path / "workspace"
    source.mkdir()
    resolver = DatasetResolver(local_root=tmp_path / "local")
    resolver.open(source, explicit_workspace=workspace)
    manifest_path = workspace / "dataset.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["stores"] = {"apply": 2, "geo": 2, "plan": 4, "precheck": 18}
    manifest_path.write_text(json.dumps(manifest))
    database = workspace / "apply/work.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE retained (value TEXT)")
        connection.execute("INSERT INTO retained VALUES ('authorized-run')")
    before_manifest, before_db = manifest_path.read_bytes(), database.read_bytes()
    with pytest.raises(DatasetOpenError, match="original build"):
        resolver.open(source, explicit_workspace=workspace)
    assert manifest_path.read_bytes() == before_manifest
    assert database.read_bytes() == before_db


@pytest.mark.parametrize("drift", [False, True])
def test_real_result_and_runtime_mcp_boundary(tmp_path, drift):
    from PIL import Image
    from mediasense.precheck import AccountingStore, ImageRenditionProducer, ResultStore
    from mediasense.runtime.dataset import dataset_id_from_ref
    from mediasense.runtime.host import RuntimeHost
    from test_apply_precheck_integration import _plan as real_plan

    source, destination, workspace = (
        tmp_path / "source",
        tmp_path / "destination",
        tmp_path / "workspace",
    )
    source.mkdir()
    destination.mkdir()
    Image.new("RGB", (80, 40), "blue").save(source / "original.jpg")
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    assert opened["outcome"] == "ok", opened
    dataset = str(opened["dataset_ref"])
    database = workspace / "precheck/work.sqlite3"
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run(dataset_id_from_ref(dataset), source)
    accounting.process_run(run_id)
    rendition = ImageRenditionProducer(database).produce(run_id, Path("original.jpg"))
    results = ResultStore(database)
    result = results.seal(results.build_minimal(run_id, [rendition.work.work_id]))
    resolve = {
        "dataset_ref": dataset,
        "result_ref": result.result_ref,
        "action": "resolve",
        "source_set": {
            "kind": "precheck_relation",
            "origin": result.result_ref,
            "relation": "accounts_for",
            "direction": "outbound",
        },
    }
    before = host.call_tool(
        "mediasense.precheck.read", dataset_ref=dataset, request=resolve
    )
    item = before["members"][0]
    if drift:
        Image.new("RGB", (160, 100), "red").save(source / "original.jpg")
    server = create_mcp_server(host)
    prompts = []

    class Session:
        client_capabilities = SimpleNamespace(elicitation=SimpleNamespace(form={}))

        async def elicit_form(self, message, schema, **kwargs):
            prompts.append(message)
            return SimpleNamespace(action="accept")

    async def scenario():
        entry = server.get_request_handler("tools/call")

        async def call(request, context=None):
            response = await entry.handler(
                context,
                types.CallToolRequestParams(
                    name="mediasense.apply.run",
                    arguments={"dataset_ref": dataset, "request": request},
                ),
            )
            return response.structured_content

        prepared = await call(
            {
                "action": "prepare",
                "request_id": "request:real-mcp-prepare",
                "forward": {
                    "frozen_plan": real_plan(
                        result_ref=result.result_ref,
                        source_item_ref=item["source_item_ref"],
                    ),
                    "effect": "move_originals",
                    "destination_parent": str(destination),
                    "current_source_roots": [
                        {
                            "source_root_ref": item["locator"]["source_root_ref"],
                            "current_root": str(source),
                        }
                    ],
                },
            }
        )
        status = await call({"action": "status", "run_ref": prepared["run_ref"]})
        if drift:
            assert status["state"] == "blocked"
            assert not prompts and not list(destination.iterdir())
            return
        assert status["state"] == "ready_for_authorization"
        execute = {
            "action": "execute",
            "request_id": "request:real-mcp-execute",
            "run_ref": status["run_ref"],
            "prepared_revision": status["prepared_revision"],
            "prepared_content_identity": status["prepared_content_identity"],
        }
        accepted = await call(execute, SimpleNamespace(session=Session(), request_id=2))
        assert accepted["outcome"] == "accepted"
        with anyio.fail_after(10):
            while True:
                status = await call({"action": "status", "run_ref": status["run_ref"]})
                if status["state"] == "closed":
                    break
                assert status["state"] in {"executing", "verifying"}, status
                await anyio.sleep(0.01)
        repeated = await call(execute)
        assert repeated["observed_state"] == "closed"
        assert len(prompts) == 1 and not (source / "original.jpg").exists()
        assert status["published_receipt"]["completed_and_verified"] == 1

    anyio.run(scenario)
    after = host.call_tool(
        "mediasense.precheck.read", dataset_ref=dataset, request=resolve
    )
    assert after == before
