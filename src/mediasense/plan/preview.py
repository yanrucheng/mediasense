"""Deterministic, non-authoritative review rendering for Plan candidates."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from html import escape
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from typing import Any, Callable, Mapping

from ._candidate import CandidateAnalysis
from ._sqlite import RevisionConflict
from .work import PlanFailure, PlanWorkTool


AssetResolver = Callable[[str, Mapping[str, Any]], str | None]


class PreviewError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreviewSample:
    source_item_ref: str
    label: str
    uri: str | None
    evidence_ref: str | None = None


@dataclass(frozen=True, slots=True)
class PreviewDirectory:
    relative_path: tuple[str, ...]
    member_refs: tuple[str, ...]
    samples: tuple[PreviewSample, ...]


@dataclass(frozen=True, slots=True)
class PreviewOutcome:
    outcome: str
    reason: str | None
    member_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PreviewDocument:
    work_ref: str
    result_ref: str
    revision: str
    candidate_content_identity: str
    logical_root: str
    directories: tuple[PreviewDirectory, ...]
    other_outcomes: tuple[PreviewOutcome, ...]
    decision_notes: tuple[dict[str, Any], ...] = ()


class PlanPreviewRenderer:
    def __init__(
        self,
        tool: PlanWorkTool,
        *,
        asset_resolver: AssetResolver | None = None,
    ) -> None:
        self.tool = tool
        self.asset_resolver = asset_resolver

    def build(self, work_ref: str, revision: str) -> PreviewDocument:
        try:
            snapshot, analysis = self.tool.snapshot_for_preview(work_ref, revision)
        except (PlanFailure, RevisionConflict) as exc:
            raise PreviewError(str(exc)) from exc
        assert analysis.content_identity is not None
        directories: list[PreviewDirectory] = []
        evidence_cache: dict[str, Mapping[str, Any]] = {}
        for group, members, representatives in zip(
            analysis.sealed_content["groups"],
            analysis.group_members,
            analysis.group_representatives,
            strict=True,
        ):
            samples = self._samples(
                representatives, analysis, frozenset(members), evidence_cache
            )
            directories.append(
                PreviewDirectory(
                    relative_path=tuple(group["relative_path"]),
                    member_refs=members,
                    samples=samples,
                )
            )
        return PreviewDocument(
            work_ref=work_ref,
            result_ref=snapshot.result_ref,
            revision=revision,
            candidate_content_identity=analysis.content_identity,
            logical_root=analysis.sealed_content["logical_root"],
            directories=tuple(directories),
            decision_notes=tuple(
                deepcopy(analysis.sealed_content.get("decision_notes", []))
            ),
            other_outcomes=tuple(
                PreviewOutcome(
                    outcome=outcome["outcome"],
                    reason=outcome.get("reason"),
                    member_refs=members,
                )
                for outcome, members in zip(
                    analysis.sealed_content["other_outcomes"],
                    analysis.outcome_members,
                    strict=True,
                )
            ),
        )

    def render_html(self, document: PreviewDocument, *, member_limit: int = 100) -> str:
        if member_limit < 1:
            raise ValueError("member_limit must be positive")
        directories = "\n".join(
            self._directory_html(directory, member_limit=member_limit)
            for directory in document.directories
        )
        outcomes = (
            "\n".join(
                "<li><code>"
                + escape(item.outcome)
                + f"</code> ({len(item.member_refs)} media) — "
                + escape(item.reason or "No reason recorded")
                + "</li>"
                for item in document.other_outcomes
            )
            or "<li>None</li>"
        )
        notes = (
            "\n".join(
                "<li><p>"
                + escape(note["summary"])
                + "</p>"
                + "<p>适用 Source Set</p><pre>"
                + escape(json.dumps(note["applies_to"], ensure_ascii=False, indent=2))
                + "</pre><p>Evidence 引用："
                + escape(", ".join(note.get("evidence_refs", [])) or "无")
                + "</p></li>"
                for note in document.decision_notes
            )
            or "<li>无</li>"
        )
        organized_count = sum(
            len(directory.member_refs) for directory in document.directories
        )
        outcome_count = sum(
            len(outcome.member_refs) for outcome in document.other_outcomes
        )
        tree = _tree_text(document)
        return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(document.logical_root)} · MediaSense Plan Preview</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, sans-serif; background: #f4f1e8; color: #20231f; }}
    body {{ margin: 0 auto; max-width: 1080px; padding: 2rem; }}
    header, article {{ background: #fffdf7; border: 1px solid #d8d3c7; border-radius: 12px; padding: 1rem 1.2rem; margin: 0 0 1rem; }}
    .binding {{ color: #5d6259; font-size: .86rem; overflow-wrap: anywhere; }}
    .summary {{ display: flex; gap: 1.5rem; margin-top: .8rem; }}
    .summary strong {{ display: block; font-size: 1.4rem; }}
    pre {{ white-space: pre-wrap; line-height: 1.55; }}
    .samples {{ display: flex; gap: .75rem; flex-wrap: wrap; }}
    figure {{ margin: 0; width: 220px; }}
    img {{ width: 220px; height: 150px; object-fit: cover; background: #e7e2d6; border-radius: 8px; }}
    .missing {{ width: 220px; height: 150px; display: grid; place-items: center; background: #e7e2d6; border-radius: 8px; }}
    code {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(document.logical_root)}</h1>
    <div class="binding">Work: {escape(document.work_ref)}</div>
    <div class="binding">Revision: {escape(document.revision)}</div>
    <div class="binding">Candidate: {escape(document.candidate_content_identity)}</div>
    <div class="summary"><span><strong>{len(document.directories)}</strong>目录</span><span><strong>{organized_count}</strong>已组织媒体</span><span><strong>{outcome_count}</strong>其他结果</span></div>
  </header>
  <article><h2>最终目录结构</h2><pre>{escape(tree)}</pre></article>
  <article><h2>决定说明与适用范围</h2><ul>{notes}</ul></article>
  <main>{directories}</main>
  <article><h2>其他已交代结果</h2><ul>{outcomes}</ul></article>
</body>
</html>
"""

    def write_html(
        self,
        work_ref: str,
        revision: str,
        output_path: Path,
        *,
        member_limit: int = 100,
    ) -> PreviewDocument:
        document = self.build(work_ref, revision)
        html = self.render_html(document, member_limit=member_limit)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(output_path.name + ".tmp")
        temporary.write_text(html, encoding="utf-8")
        temporary.replace(output_path)
        return document

    @staticmethod
    def directory_page(
        document: PreviewDocument,
        directory_index: int,
        *,
        offset: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        if directory_index < 0 or directory_index >= len(document.directories):
            raise PreviewError("directory index is out of range")
        if offset < 0 or limit < 1:
            raise PreviewError("directory page bounds are invalid")
        directory = document.directories[directory_index]
        items = directory.member_refs[offset : offset + limit]
        next_offset = offset + len(items)
        return {
            "work_ref": document.work_ref,
            "revision": document.revision,
            "candidate_content_identity": document.candidate_content_identity,
            "relative_path": list(directory.relative_path),
            "items": list(items),
            "returned": len(items),
            "complete": next_offset >= len(directory.member_refs),
            **(
                {"next_offset": next_offset}
                if next_offset < len(directory.member_refs)
                else {}
            ),
        }

    def _samples(
        self,
        representative_refs: tuple[str, ...],
        analysis: CandidateAnalysis,
        group_members: frozenset[str],
        evidence_cache: dict[str, Mapping[str, Any]],
    ) -> tuple[PreviewSample, ...]:
        samples: list[PreviewSample] = []
        if self.asset_resolver is not None:
            for ref in representative_refs:
                view = analysis.source_views.get(ref, {})
                uri = self.asset_resolver(ref, view)
                if uri is not None or not samples:
                    samples.append(PreviewSample(ref, _source_label(ref, view), uri))
                if len(samples) == 2:
                    break
            return tuple(samples)
        # Use one bounded public expansion, rather than querying every member
        # until an image happens to be found. The Read selector allows 16 sources.
        if representative_refs:
            covered = self._read(
                {
                    "action": "expand",
                    "result_ref": analysis.sealed_content["result_ref"],
                    "source_item_refs": list(representative_refs[:16]),
                    "include": ["covering_evidence"],
                }
            )
            refs = list(
                dict.fromkeys(
                    coverage["evidence_ref"]
                    for item in covered["items"]
                    for coverage in item["included"]["covering_evidence"]
                )
            )[:16]
            missing = [ref for ref in refs if ref not in evidence_cache]
            if missing:
                request = {
                    "action": "review",
                    "result_ref": analysis.sealed_content["result_ref"],
                    "evidence_refs": missing,
                    "page": {"limit": 16},
                }
                collected: dict[str, Mapping[str, Any]] = {}
                cursors: set[str] = set()
                while True:
                    response = self._read(request)
                    collected.update(
                        (item["evidence_ref"], item)
                        for item in response["items"]
                        if item["evidence_ref"] in missing
                    )
                    cursor = response["page"]["next_cursor"]
                    if cursor is None:
                        break
                    if (
                        not response["items"]
                        or cursor in cursors
                        or len(cursors) + 1 >= len(missing)
                    ):
                        raise PreviewError(
                            "PreCheck preview Evidence pagination made no progress"
                        )
                    cursors.add(cursor)
                    # A byte-limited page is not the end of this selection.
                    # Keep the exact Result, selection and limit bound by cursor.
                    request = {**request, "page": {"limit": 16, "cursor": cursor}}
                evidence_cache.update(collected)
            for evidence_ref in refs:
                evidence = evidence_cache.get(evidence_ref, {})
                if "error" in evidence:
                    continue
                origins = tuple(
                    item["source_item_ref"] for item in evidence.get("source_items", [])
                )
                # represents is not derivation. Never label another source's
                # picture as this member, or show excluded media as its sample.
                if not origins or not set(origins) <= group_members:
                    continue
                uri = _default_asset_resolver(evidence_ref, evidence)
                if uri is None:
                    continue
                label = ", ".join(
                    _source_label(origin, analysis.source_views.get(origin, {}))
                    for origin in origins
                )
                samples.append(PreviewSample(origins[0], label, uri, evidence_ref))
                if len(samples) == 2:
                    break
        if not samples and representative_refs:
            ref = representative_refs[0]
            samples.append(
                PreviewSample(
                    ref, _source_label(ref, analysis.source_views.get(ref, {})), None
                )
            )
        return tuple(samples)

    def _read(self, request: dict[str, Any]) -> Mapping[str, Any]:
        from mediasense.runtime.resources import contract_validator

        response = self.tool.precheck_read.read(request)
        if not isinstance(response, Mapping) or not contract_validator(
            "mediasense.precheck.read", request["action"]
        ).is_valid(response):
            raise PreviewError("PreCheck returned an invalid preview Evidence response")
        if "error" in response:
            raise PreviewError(
                f"PreCheck preview Evidence unavailable: {response['error']['code']}"
            )
        return response

    @staticmethod
    def _directory_html(directory: PreviewDirectory, *, member_limit: int) -> str:
        display_path = "/".join(directory.relative_path) or "(root)"
        samples = []
        for sample in directory.samples:
            caption = escape(sample.label)
            if sample.evidence_ref:
                caption += "<br><code>" + escape(sample.evidence_ref) + "</code>"
            if sample.uri:
                samples.append(
                    f'<figure><img src="{escape(sample.uri, quote=True)}" alt="{escape(sample.label, quote=True)}"><figcaption>{caption}</figcaption></figure>'
                )
            else:
                samples.append(
                    f'<figure><div class="missing">Preview unavailable</div><figcaption>{caption}</figcaption></figure>'
                )
        visible = directory.member_refs[:member_limit]
        member_items = "".join(
            f"<li><code>{escape(ref)}</code></li>" for ref in visible
        )
        omitted = len(directory.member_refs) - len(visible)
        more = (
            f"<p>{omitted} more items available through bounded drill-down.</p>"
            if omitted
            else ""
        )
        return f"""<article>
  <h2>{escape(display_path)} <small>({len(directory.member_refs)} media)</small></h2>
  <div class="samples">{"".join(samples)}</div>
  <details><summary>展开查看目录内容</summary><ol>{member_items}</ol>{more}</details>
</article>"""


def _source_label(ref: str, view: Mapping[str, Any]) -> str:
    locator = view.get("locator")
    if isinstance(locator, Mapping) and isinstance(locator.get("value"), str):
        return Path(locator["value"]).name
    return ref


def _default_asset_resolver(ref: str, view: Mapping[str, Any]) -> str | None:
    del ref
    access = view.get("access", {})
    if access.get("kind") != "local_artifact":
        return None
    locator = access.get("locator", {})
    if locator.get("kind") != "local_file_path":
        return None
    value = locator.get("value")
    if not isinstance(value, str):
        return None
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
        return None
    try:
        with Image.open(path) as picture:
            if picture.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
                return None
            picture.load()
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError):
        return None
    return path.resolve().as_uri()


def _tree_text(document: PreviewDocument) -> str:
    root: dict[str, Any] = {}
    counts: dict[tuple[str, ...], int] = {}
    for directory in document.directories:
        node = root
        for segment in directory.relative_path:
            node = node.setdefault(segment, {})
        counts[directory.relative_path] = len(directory.member_refs)

    lines = [document.logical_root + "/"]

    def visit(node: dict[str, Any], prefix: tuple[str, ...], indent: str) -> None:
        names = sorted(node)
        for index, name in enumerate(names):
            last = index == len(names) - 1
            path = (*prefix, name)
            count = counts.get(path)
            suffix = f" ({count} media)" if count is not None else ""
            lines.append(indent + ("└── " if last else "├── ") + name + "/" + suffix)
            visit(node[name], path, indent + ("    " if last else "│   "))

    visit(root, (), "")
    return "\n".join(lines)
