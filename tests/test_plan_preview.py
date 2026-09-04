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
            "candidate_content": valid_candidate(),
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
            "candidate_content": candidate,
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
            "candidate_content": valid_candidate(),
            "request_id": "request:zero-egress-update",
        }
    )
    resolver_calls = []
    renderer = PlanPreviewRenderer(
        tool,
        asset_resolver=lambda ref, view: resolver_calls.append((ref, view)) or None,
    )
    renderer.build(created["work_ref"], updated["revision"])
    assert {request["operation"] for request in reader.calls} <= {
        "review",
        "expand",
        "resolve",
    }
    assert resolver_calls
