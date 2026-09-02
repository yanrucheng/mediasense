from __future__ import annotations

from pathlib import Path

from jsonschema import Draft202012Validator

from mediasense.precheck import AccountingStore, PrecheckReadTool, PrecheckRunTool
from mediasense.precheck._orchestrator import PrecheckExecutionConfig
from mediasense.precheck._orchestrator import PrecheckExecutionDependencies
from mediasense.precheck.scope_review import build_scope_inventory
from mediasense.precheck.work import WorkStore


ROOT = Path(__file__).parents[1]
RUN_CONTRACT = (
    ROOT / "docs" / "spec" / "spec-260827-1915A-precheck-run" / "precheck-run.tool.json"
)


def _tool(tmp_path: Path) -> tuple[PrecheckRunTool, Path]:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    accounting = AccountingStore(database)
    accounting.register_dataset("scope-review")
    accounting.start_or_resume_run("scope-review", source)
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            metadata=False,
            gpx=False,
            image_renditions=False,
            video=False,
            bundles=False,
            compression_target=None,
        ),
    )
    return tool, source


def _start_and_inventory(
    tool: PrecheckRunTool, request_id: str
) -> tuple[str, dict[str, object]]:
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:scope-review",
            "request_id": request_id,
        }
    )
    run_ref = str(started["run_ref"])
    paused = tool.advance(run_ref)
    assert paused["state"] == "paused"
    assert paused["reason"]["code"] == "scope_confirmation_required"
    assert paused["confirmation"]["kind"] == "source_scope"
    return run_ref, paused


def _selection(
    paused: dict[str, object],
    *,
    default: str = "include",
    exceptions: list[str] | None = None,
) -> dict[str, object]:
    confirmation = paused["confirmation"]
    assert isinstance(confirmation, dict)
    return {
        "kind": "source_scope",
        "inventory_fingerprint": confirmation["inventory_fingerprint"],
        "default_disposition": default,
        "exceptions": exceptions or [],
    }


def test_scope_inventory_is_factual_bounded_and_expandable(tmp_path: Path) -> None:
    tool, source = _tool(tmp_path)
    cache = source / ".similarity_cache" / "frames"
    cache.mkdir(parents=True)
    (cache / "frame-1.jpg").write_bytes(b"a" * 1_024)
    (cache / "frame-2.jpg").write_bytes(b"b" * 2_048)
    hidden = source / ".private-album"
    hidden.mkdir()
    (hidden / "original.jpg").write_bytes(b"original")
    (source / ".DS_Store").write_bytes(b"metadata")

    run_ref, paused = _start_and_inventory(tool, "request:scope-tree")
    inventory = paused["confirmation"]["inventory"]
    tree = inventory["view"]["tree"]

    assert tree["file_count"] == 4
    assert tree["byte_count"] == 1_024 + 2_048 + 8 + 8
    assert {child["path"] for child in tree["children"]} >= {
        ".DS_Store",
        ".private-album",
        ".similarity_cache",
    }
    assert "candidate" not in str(inventory).lower()
    assert "confidence" not in str(inventory).lower()
    assert (
        WorkStore(tool.database_path).list_run_work(
            str(tool._store.get(run_ref)["accounting_run_id"])
        )
        == ()
    )

    expanded = tool.run(
        {
            "action": "status",
            "run_ref": run_ref,
            "scope_path": ".similarity_cache",
        }
    )
    expanded_tree = expanded["confirmation"]["inventory"]["view"]["tree"]
    assert expanded_tree["path"] == ".similarity_cache"
    assert expanded_tree["file_count"] == 2


def test_scope_selection_excludes_cache_frames_but_keeps_accounting(
    tmp_path: Path,
) -> None:
    tool, source = _tool(tmp_path)
    cache = source / ".similarity_cache"
    cache.mkdir()
    (cache / "frame.jpg").write_bytes(b"frame")
    hidden = source / ".private-album"
    hidden.mkdir()
    (hidden / "original.jpg").write_bytes(b"original")

    run_ref, paused = _start_and_inventory(tool, "request:scope-exclude")
    decision = _selection(paused, exceptions=[".similarity_cache"])
    accepted = tool.run({"action": "resume", "run_ref": run_ref, "decision": decision})
    assert accepted["outcome"] == "accepted"
    finished = tool.advance(run_ref)
    assert finished["state"] == "completed"
    assert finished["scope_selection"] == {
        **decision,
        "provenance": "accepted",
    }

    accounting_run_id = tool._store.get(run_ref)["accounting_run_id"]
    items = {
        item.relative_path.as_posix(): item
        for item in AccountingStore(tool.database_path).iter_run_items(
            str(accounting_run_id)
        )
    }
    assert items[".similarity_cache/frame.jpg"].scope == "excluded"
    assert items[".private-album/original.jpg"].scope == "source_media"
    assert any(
        value.startswith("scope_selection_excluded:sha256:")
        for value in items[".similarity_cache/frame.jpg"].basis
    )
    result_items = PrecheckReadTool(tool.database_path).read(
        {
            "action": "traverse",
            "result_ref": finished["published_result"]["result_ref"],
            "relation": "accounts_for",
            "direction": "outbound",
        }
    )["items"]
    assert sum(item["scope"] == "excluded" for item in result_items) == 1


def test_default_exclude_can_include_a_legal_hidden_media_directory(
    tmp_path: Path,
) -> None:
    tool, source = _tool(tmp_path)
    hidden = source / ".private-album"
    hidden.mkdir()
    (hidden / "original.jpg").write_bytes(b"original")
    (source / "unselected.jpg").write_bytes(b"other")
    run_ref, paused = _start_and_inventory(tool, "request:scope-hidden")

    decision = _selection(
        paused,
        default="exclude",
        exceptions=[".private-album"],
    )
    tool.run({"action": "resume", "run_ref": run_ref, "decision": decision})
    assert tool.advance(run_ref)["state"] == "completed"

    accounting_run_id = tool._store.get(run_ref)["accounting_run_id"]
    items = {
        item.relative_path.as_posix(): item
        for item in AccountingStore(tool.database_path).iter_run_items(
            str(accounting_run_id)
        )
    }
    assert items[".private-album/original.jpg"].scope == "source_media"
    assert items["unselected.jpg"].scope == "excluded"


def test_changed_tree_rejects_old_selection_before_expensive_work(
    tmp_path: Path,
) -> None:
    tool, source = _tool(tmp_path)
    (source / "photo.jpg").write_bytes(b"first")
    run_ref, paused = _start_and_inventory(tool, "request:scope-stale")
    decision = _selection(paused)
    tool.run({"action": "resume", "run_ref": run_ref, "decision": decision})
    (source / "new.jpg").write_bytes(b"new")

    refreshed = tool.advance(run_ref)

    assert refreshed["state"] == "paused"
    assert refreshed["reason"]["code"] == "scope_confirmation_required"
    assert (
        refreshed["confirmation"]["inventory_fingerprint"]
        != decision["inventory_fingerprint"]
    )


def test_scope_selection_rejects_overlapping_or_absent_exceptions(
    tmp_path: Path,
) -> None:
    tool, source = _tool(tmp_path)
    frames = source / ".similarity_cache" / "frames"
    frames.mkdir(parents=True)
    (frames / "frame.jpg").write_bytes(b"frame")
    run_ref, paused = _start_and_inventory(tool, "request:scope-invalid")

    overlap = _selection(
        paused,
        exceptions=[".similarity_cache", ".similarity_cache/frames"],
    )
    overlap_response = tool.run(
        {"action": "resume", "run_ref": run_ref, "decision": overlap}
    )
    assert overlap_response["error"]["code"] == "invalid_request"

    absent = _selection(paused, exceptions=["missing"])
    absent_response = tool.run(
        {"action": "resume", "run_ref": run_ref, "decision": absent}
    )
    assert absent_response["error"]["code"] == "invalid_request"
    assert tool.run({"action": "status", "run_ref": run_ref})["state"] == "paused"


def test_unattended_run_waits_without_expensive_work(tmp_path: Path) -> None:
    tool, source = _tool(tmp_path)
    (source / "photo.jpg").write_bytes(b"photo")
    run_ref, paused = _start_and_inventory(tool, "request:scope-unattended")

    status = tool.run({"action": "status", "run_ref": run_ref})

    assert status == paused
    assert status["activity"]["state"] == "waiting"
    assert status["allowed_actions"] == ["resume", "cancel"]


def test_scope_gate_precedes_enabled_metadata_work(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"photo")
    accounting = AccountingStore(database)
    accounting.register_dataset("scope-review")
    accounting_run_id = accounting.start_or_resume_run("scope-review", source)
    calls: list[object] = []

    def metadata_runner(command: object) -> object:
        calls.append(command)
        raise AssertionError("metadata must not run before scope selection")

    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            metadata=True,
            gpx=False,
            image_renditions=False,
            video=False,
            bundles=False,
            compression_target=None,
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            metadata_runner=metadata_runner,
            exiftool_version="test-exiftool",
        ),
    )
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:scope-review",
            "request_id": "request:scope-before-metadata",
        }
    )

    paused = tool.advance(str(started["run_ref"]))

    assert paused["reason"]["code"] == "scope_confirmation_required"
    assert calls == []
    assert WorkStore(database).list_run_work(accounting_run_id) == ()


def test_historical_output_is_reported_without_a_tool_verdict(tmp_path: Path) -> None:
    tool, source = _tool(tmp_path)
    output = source / "old-output" / "2024-trip"
    output.mkdir(parents=True)
    (output / "copy.jpg").write_bytes(b"copy")

    _run_ref, paused = _start_and_inventory(tool, "request:scope-output")
    inventory = paused["confirmation"]["inventory"]

    assert "old-output" in str(inventory)
    assert "historical_output" not in str(inventory)
    assert "derived" not in str(inventory)


def test_many_ordinary_dotfiles_are_aggregated_in_a_bounded_tree(
    tmp_path: Path,
) -> None:
    tool, source = _tool(tmp_path)
    for index in range(100):
        (source / f".setting-{index:03d}").write_bytes(b"x")

    run_ref, paused = _start_and_inventory(tool, "request:scope-dotfiles")
    tree = paused["confirmation"]["inventory"]["view"]["tree"]

    assert tree["file_count"] == 100
    assert tree["byte_count"] == 100
    assert len(tree["children"]) == 63
    assert tree["omitted_children"] == 37
    assert tree["kind_counts"] == [{"kind": "unknown", "count": 100}]
    next_page = tool.run(
        {
            "action": "status",
            "run_ref": run_ref,
            "scope_path": ".",
            "scope_after": paused["confirmation"]["inventory"]["view"]["next_after"],
        }
    )
    next_children = next_page["confirmation"]["inventory"]["view"]["tree"]["children"]
    assert next_children[0]["path"] == ".setting-063"


def test_large_flat_inventory_projection_has_a_fixed_node_budget() -> None:
    def facts():
        for index in range(10_000):
            yield {
                "relative_path": f"item-{index:05d}.jpg",
                "kind": "image",
                "scope": "source_media",
                "condition": "unresolved",
                "basis": ("media_extension_candidate",),
                "size_bytes": 1,
                "mtime_ns": index,
                "device_id": 1,
                "inode": index,
                "mode": 0o100644,
                "fingerprint_algorithm": "test",
                "fingerprint": f"test:{index}",
                "producer_identity": "test-discovery",
                "reuse_domain": "test-domain",
            }

    inventory = build_scope_inventory(facts(), (), scan_generation=1)
    tree = inventory["view"]["tree"]

    assert tree["file_count"] == 10_000
    assert tree["byte_count"] == 10_000
    assert len(tree["children"]) == 63
    assert tree["omitted_children"] == 9_937
    assert len(tree["representative_paths"]) == 3
    assert inventory["view"]["next_after"] == "item-00062.jpg"

    next_page = build_scope_inventory(
        facts(),
        (),
        scan_generation=1,
        scope_after="item-00062.jpg",
    )
    assert next_page["view"]["tree"]["children"][0]["path"] == "item-00063.jpg"


def test_unchanged_later_run_reuses_exact_scope_selection(tmp_path: Path) -> None:
    tool, source = _tool(tmp_path)
    (source / "photo.jpg").write_bytes(b"photo")
    first_ref, paused = _start_and_inventory(tool, "request:scope-first")
    decision = _selection(paused)
    tool.run({"action": "resume", "run_ref": first_ref, "decision": decision})
    assert tool.advance(first_ref)["state"] == "completed"

    AccountingStore(tool.database_path).start_or_resume_run("scope-review", source)
    second = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:scope-review",
            "request_id": "request:scope-second",
        }
    )
    second_status = tool.advance(str(second["run_ref"]))

    assert second_status["state"] == "completed"
    review = tool._store.latest_scope_review(str(second["run_ref"]))
    assert review is not None
    assert review["state"] == "reused"
    assert review["reused_from_run_ref"] == first_ref
    assert second_status["scope_selection"]["provenance"] == "reused"
    assert second_status["scope_selection"]["reused_from_run_ref"] == first_ref


def test_scope_review_responses_match_public_contract(tmp_path: Path) -> None:
    import json

    tool, source = _tool(tmp_path)
    (source / "photo.jpg").write_bytes(b"photo")
    run_ref, paused = _start_and_inventory(tool, "request:scope-contract")
    contract = json.loads(RUN_CONTRACT.read_text(encoding="utf-8"))
    output = Draft202012Validator(contract["outputSchema"])
    request = Draft202012Validator(contract["inputSchema"])
    request.check_schema(contract["inputSchema"])
    output.check_schema(contract["outputSchema"])
    output.validate(paused)

    decision = _selection(paused)
    resume_request = {"action": "resume", "run_ref": run_ref, "decision": decision}
    request.validate(resume_request)
    output.validate(tool.run(resume_request))
