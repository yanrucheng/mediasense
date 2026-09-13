from __future__ import annotations

from copy import deepcopy

import pytest

from mediasense.plan import PlanPreviewRenderer, PlanWorkTool, PreviewError
from mediasense.plan.preview import PreviewDirectory, PreviewDocument, PreviewSample

from _plan_support import MockPrecheckReader, StableIdFactory, valid_candidate


def _prepared_tool(tmp_path):
    tool = PlanWorkTool(
        tmp_path / "plan-store",
        MockPrecheckReader(),
        id_factory=StableIdFactory(),
    )
    created = tool.handle(
        {
            "action": "create",
            "result_ref": "precheck-result:hk-review-slice-002",
            "request_id": "request:create-preview",
        }
    )
    updated = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "organization_content": valid_candidate(),
            "request_id": "request:update-preview",
        }
    )
    return tool, created, updated


def test_preview_contains_tree_counts_samples_outcomes_and_binding(tmp_path) -> None:
    tool, created, updated = _prepared_tool(tmp_path)
    renderer = PlanPreviewRenderer(
        tool,
        asset_resolver=lambda ref, view: f"mock://{ref}.jpg",
    )
    document = renderer.build(created["work_ref"], updated["revision"])
    html = renderer.render_html(document)
    assert tuple(directory.member_refs for directory in document.directories) == (
        ("source-item:13", "source-item:14", "source-item:15"),
        ("source-item:217",),
    )
    assert "Illustrative bundle 61 subset" in html
    assert "最终目录结构" in html
    assert "(3 media)" in html
    assert "exclude_from_logical_organization" in html
    assert updated["revision"] in html
    assert document.candidate_content_identity in html
    assert html == renderer.render_html(
        renderer.build(created["work_ref"], updated["revision"])
    )


def test_preview_reports_missing_local_sample(tmp_path) -> None:
    tool, created, updated = _prepared_tool(tmp_path)
    renderer = PlanPreviewRenderer(tool, asset_resolver=lambda ref, view: None)
    html = renderer.render_html(
        renderer.build(created["work_ref"], updated["revision"])
    )
    assert "Preview unavailable" in html
    assert "source-item:13" in html


def test_directory_drill_down_is_bounded_and_bound(tmp_path) -> None:
    tool, created, updated = _prepared_tool(tmp_path)
    renderer = PlanPreviewRenderer(tool)
    document = renderer.build(created["work_ref"], updated["revision"])
    first = renderer.directory_page(document, 0, limit=2)
    second = renderer.directory_page(document, 0, offset=first["next_offset"], limit=2)
    assert first["items"] == ["source-item:13", "source-item:14"]
    assert first["complete"] is False
    assert second["items"] == ["source-item:15"]
    assert second["complete"] is True
    assert first["revision"] == updated["revision"]


def test_old_revision_cannot_be_rendered_after_update(tmp_path) -> None:
    tool, created, updated = _prepared_tool(tmp_path)
    candidate = deepcopy(valid_candidate())
    candidate["logical_root"] = "Revised Hong Kong review slice"
    newer = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": updated["revision"],
            "organization_content": candidate,
            "request_id": "request:update-preview-again",
        }
    )
    renderer = PlanPreviewRenderer(tool)
    with pytest.raises(PreviewError, match="revision conflict"):
        renderer.build(created["work_ref"], updated["revision"])
    assert (
        renderer.build(created["work_ref"], newer["revision"]).revision
        == newer["revision"]
    )


def test_write_html_is_atomic_at_the_visible_path(tmp_path) -> None:
    tool, created, updated = _prepared_tool(tmp_path)
    renderer = PlanPreviewRenderer(tool, asset_resolver=lambda ref, view: None)
    output = tmp_path / "preview" / "index.html"
    renderer.write_html(created["work_ref"], updated["revision"], output)
    assert output.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert not output.with_name("index.html.tmp").exists()


def test_large_directory_is_bounded_in_html_and_expandable_by_page(tmp_path) -> None:
    tool, created, updated = _prepared_tool(tmp_path)
    renderer = PlanPreviewRenderer(tool)
    base = renderer.build(created["work_ref"], updated["revision"])
    members = tuple(f"source-item:{index}" for index in range(1000, 2000))
    document = PreviewDocument(
        work_ref=base.work_ref,
        result_ref=base.result_ref,
        revision=base.revision,
        candidate_content_identity=base.candidate_content_identity,
        logical_root=base.logical_root,
        directories=(PreviewDirectory(("Large",), members, ()),),
        other_outcomes=(),
    )
    html = renderer.render_html(document, member_limit=3)
    page = renderer.directory_page(document, 0, offset=300, limit=100)
    assert "997 more items" in html
    assert len(page["items"]) == 100
    assert page["next_offset"] == 400


def test_preview_escapes_paths_labels_and_uris(tmp_path) -> None:
    tool, created, updated = _prepared_tool(tmp_path)
    renderer = PlanPreviewRenderer(tool)
    base = renderer.build(created["work_ref"], updated["revision"])
    document = PreviewDocument(
        work_ref=base.work_ref,
        result_ref=base.result_ref,
        revision=base.revision,
        candidate_content_identity=base.candidate_content_identity,
        logical_root="<script>alert(1)</script>",
        directories=(
            PreviewDirectory(
                ("<unsafe>",),
                ("source-item:1",),
                (
                    PreviewSample(
                        "source-item:1", '"bad" <label>', 'file:///tmp/a"b.jpg'
                    ),
                ),
            ),
        ),
        other_outcomes=(),
    )
    html = renderer.render_html(document)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'src="file:///tmp/a&quot;b.jpg"' in html


def test_preview_uses_only_read_contract_and_asset_resolver(tmp_path) -> None:
    reader = MockPrecheckReader()
    tool = PlanWorkTool(tmp_path / "plan-store", reader, id_factory=StableIdFactory())
    created = tool.handle(
        {
            "action": "create",
            "result_ref": reader.result_ref,
            "request_id": "request:zero-egress-create",
        }
    )
    updated = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "organization_content": valid_candidate(),
            "request_id": "request:zero-egress-update",
        }
    )
    resolver_calls = []
    renderer = PlanPreviewRenderer(
        tool,
        asset_resolver=lambda ref, view: resolver_calls.append((ref, view)) or None,
    )
    renderer.build(created["work_ref"], updated["revision"])
    assert {request["action"] for request in reader.calls} <= {
        "review",
        "expand",
        "resolve",
        "geo_summary",
    }
    assert resolver_calls


def test_decision_notes_render_exact_scope_refs_and_escaped_text(tmp_path):
    tool, created, updated = _prepared_tool(tmp_path)
    candidate = valid_candidate()
    candidate["decision_notes"][0]["summary"] = (
        "用户口述 <script>alert(1)</script> & “只适用这组”"
    )
    newer = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": updated["revision"],
            "request_id": "request:notes-preview",
            "organization_content": candidate,
        }
    )
    renderer = PlanPreviewRenderer(tool, asset_resolver=lambda ref, view: None)
    document = renderer.build(created["work_ref"], newer["revision"])
    html = renderer.render_html(document)
    assert document.decision_notes == tuple(candidate["decision_notes"])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "决定说明与适用范围" in html
    assert "适用 Source Set" in html
    for note in candidate["decision_notes"]:
        for ref in note.get("evidence_refs", []):
            assert ref in html
    assert document.candidate_content_identity in html


@pytest.mark.parametrize("artifact_state", ["available", "missing", "corrupt"])
def test_default_preview_uses_real_prepared_evidence_with_relative_source_locator(
    tmp_path, monkeypatch, artifact_state
):
    from pathlib import Path
    from urllib.parse import unquote, urlsplit
    from PIL import Image
    from test_runtime_host import _opened_host_with_plan_ready_result

    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(tmp_path / "config"))
    host, dataset, result, _root, source, original = (
        _opened_host_with_plan_ready_result(tmp_path)
    )
    tool = host._datasets[dataset].plan_work
    created = tool.handle(
        {"action": "create", "result_ref": result, "request_id": "request:real-preview"}
    )
    scope = {
        "kind": "precheck_relation",
        "origin": result,
        "relation": "accounts_for",
        "direction": "outbound",
    }
    updated = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "request_id": "request:real-preview-update",
            "organization_content": {
                "kind": "candidate",
                "result_ref": result,
                "scope": scope,
                "logical_root": "Media",
                "groups": [
                    {
                        "relative_path": ["Sample"],
                        "members": scope,
                        "source_naming": {"default": "preserve_source_basename"},
                    }
                ],
                "other_outcomes": [],
            },
        }
    )
    reviewed = tool.precheck_read.read({"action": "review", "result_ref": result})
    card = reviewed["items"][0]
    # A valid Result-local reference remains valid when its image disappears.
    # Exercise both note evidence and a relation-origin group after reopening.
    organization = deepcopy(tool.store.snapshot(created["work_ref"]).candidate)
    organization["decision_notes"] = [
        {
            "summary": "Source-bound explanation",
            "applies_to": scope,
            "evidence_refs": [card["evidence_ref"]],
        }
    ]
    updated = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": updated["revision"],
            "request_id": "request:with-note-evidence",
            "organization_content": organization,
        }
    )
    assert updated["outcome"] == "ok"
    artifact = Path(card["access"]["locator"]["value"])
    assert artifact.is_file()
    from mediasense.plan.view import PlanView

    member_page = PlanView(tool, created["work_ref"]).page(
        updated["revision"], "group:0"
    )
    assert member_page["items"][0]["name"] == "original.jpg"
    assert member_page["items"][0]["observations"]
    if artifact_state == "missing":
        artifact.unlink()
    elif artifact_state == "corrupt":
        artifact.unlink()  # replace only this test's synthetic read-only Artifact
        artifact.write_bytes(b"not an image")
    renderer = PlanPreviewRenderer(tool)
    document = renderer.build(created["work_ref"], updated["revision"])
    html = renderer.render_html(document)
    sample = document.directories[0].samples[0]
    if artifact_state == "available":
        assert sample.evidence_ref == card["evidence_ref"]
        assert sample.source_item_ref == card["source_items"][0]["source_item_ref"]
        assert sample.label == "original.jpg"
        assert Path(unquote(urlsplit(sample.uri).path)) == artifact
        with Image.open(artifact) as image:
            image.load()
            assert image.width > 0 and image.height > 0
        assert "<img " in html and "Preview unavailable" not in html
        assert sample.evidence_ref in html
    else:
        assert sample.uri is None
        assert "Preview unavailable" in html
        from mediasense.plan.view import PlanView
        from test_plan_work import _confirmation, _seal_request

        reopened = PlanWorkTool(tool.plan_store, tool.precheck_read)
        projection = PlanView(reopened, created["work_ref"])
        assert (
            projection.overview(updated["revision"])["scope_summary"]["unassigned"] == 0
        )
        identity = reopened.store.snapshot(created["work_ref"]).candidate_identity
        sealed = reopened.handle(
            _seal_request(created, updated, identity),
            confirmation=_confirmation(identity, updated),
        )
        assert sealed["outcome"] == "ok", sealed
    assert (source / "original.jpg").read_bytes() == original


def test_default_preview_does_not_label_covering_evidence_as_another_source(
    tmp_path, monkeypatch
):
    from PIL import Image

    tool, created, updated = _prepared_tool(tmp_path)
    path = tmp_path / 'prepared # "图".png'
    Image.new("RGB", (12, 8), "purple").save(path)
    original_read = tool.precheck_read.read

    def read(request):
        response = original_read(request)
        if request["action"] == "review":
            for card in response["items"]:
                card["access"] = {
                    "kind": "local_artifact",
                    "locator": {"kind": "local_file_path", "value": str(path)},
                }
                # All pictures actually derive from the excluded outcome item,
                # although their represents relation covers logical-group items.
                for origin in card["source_items"]:
                    origin["source_item_ref"] = "source-item:215"
        return response

    monkeypatch.setattr(tool.precheck_read, "read", read)
    renderer = PlanPreviewRenderer(tool)
    doc = renderer.build(created["work_ref"], updated["revision"])
    assert all(
        sample.uri is None
        for directory in doc.directories
        for sample in directory.samples
    )


@pytest.mark.parametrize("continuation", ["complete", "repeated_cursor", "read_error"])
def test_preview_follows_byte_limited_review_to_image_on_second_page(
    tmp_path, monkeypatch, continuation
):
    from dataclasses import replace
    from pathlib import Path
    from urllib.parse import unquote, urlsplit
    from PIL import Image
    from mediasense.precheck import PrecheckReadTool
    from test_precheck_delivery import prepared

    database, store, draft, _ = prepared(tmp_path)
    selected = sorted(draft.entry_evidence)[:2]
    evidence = []
    for item in draft.evidence:
        if item.ref in selected:
            item = replace(
                item,
                observations=(
                    *item.observations,
                    {
                        "name": "retained_text",
                        "status": "available",
                        "value": "x" * 300_000,
                    },
                ),
            )
        if item.ref == selected[0]:
            item = replace(
                item,
                access={
                    "kind": "inline",
                    "value": {"description": "non-image context"},
                },
                artifact_id=None,
                work_id=None,
            )
        evidence.append(item)
    sealed = store.seal(replace(draft, evidence=tuple(evidence)))
    sources = sorted(
        {
            r.target_ref
            for r in draft.relationships
            if r.origin_ref in selected and r.relation == "represents"
        }
    )
    reader = PrecheckReadTool(database)
    from mediasense.precheck.read import bind_precheck_read

    tool = PlanWorkTool(
        tmp_path / "plan", bind_precheck_read(reader, "dataset:delivery")
    )
    created = tool.handle(
        {
            "action": "create",
            "result_ref": sealed.result_ref,
            "request_id": "request:paged-preview",
        }
    )
    assert created["outcome"] == "ok", created
    scope = {"kind": "explicit", "source_item_refs": sources}
    updated = tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": created["revision"],
            "request_id": "request:paged-candidate",
            "organization_content": {
                "kind": "candidate",
                "result_ref": sealed.result_ref,
                "scope": scope,
                "logical_root": "Media",
                "groups": [
                    {
                        "relative_path": ["Together"],
                        "members": scope,
                        "source_naming": {"default": "preserve_source_basename"},
                    }
                ],
                "other_outcomes": [],
            },
        }
    )
    assert updated["outcome"] == "ok", updated
    calls, responses = [], []
    original_read = reader.read

    def read(request):
        if "cursor" in request.get("page", {}) and continuation == "repeated_cursor":
            response = deepcopy(responses[0])
        elif "cursor" in request.get("page", {}) and continuation == "read_error":
            response = original_read(
                {**request, "page": {"limit": 16, "cursor": "invalid-cursor"}}
            )
        else:
            response = original_read(request)
        if request["action"] == "review" and "evidence_refs" in request:
            calls.append(deepcopy(request))
            responses.append(response)
        return response

    monkeypatch.setattr(reader, "read", read)
    renderer = PlanPreviewRenderer(tool)
    if continuation != "complete":
        output = tmp_path / "preview.html"
        output.write_text("previous complete preview")
        with pytest.raises(
            PreviewError, match="pagination made no progress|invalid_cursor"
        ):
            renderer.write_html(created["work_ref"], updated["revision"], output)
        assert output.read_text() == "previous complete preview"
        assert len(calls) == 2
        return
    document = renderer.build(created["work_ref"], updated["revision"])
    assert len(calls) == 2
    assert calls[0]["result_ref"] == calls[1]["result_ref"] == sealed.result_ref
    assert calls[0]["evidence_refs"] == calls[1]["evidence_refs"]
    assert sorted(calls[0]["evidence_refs"]) == selected
    assert calls[0]["page"] == {"limit": 16}
    assert responses[0]["page"]["stop_reason"] == "byte_limit"
    assert responses[0]["items"][0]["access"]["kind"] == "inline"
    assert calls[1]["page"] == {
        "limit": 16,
        "cursor": responses[0]["page"]["next_cursor"],
    }
    assert responses[1]["page"]["next_cursor"] is None
    sample = document.directories[0].samples[0]
    assert sample.evidence_ref == selected[1]
    with Image.open(Path(unquote(urlsplit(sample.uri).path))) as picture:
        picture.load()
        assert picture.size == (20, 10)
    html = renderer.render_html(document)
    assert "<img " in html and "Preview unavailable" not in html
