"""Deterministic, non-authoritative review rendering for Plan candidates."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
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
    geo_observations: tuple[Mapping[str, Any], ...] = ()


class PlanPreviewRenderer:
    def __init__(
        self,
        tool: PlanWorkTool,
        *,
        asset_resolver: AssetResolver | None = None,
    ) -> None:
        self.tool = tool
        self.asset_resolver = asset_resolver or _default_asset_resolver

    def build(self, work_ref: str, revision: str) -> PreviewDocument:
        try:
            snapshot, analysis = self.tool.snapshot_for_preview(work_ref, revision)
        except (PlanFailure, RevisionConflict) as exc:
            raise PreviewError(str(exc)) from exc
        assert analysis.content_identity is not None
        directories: list[PreviewDirectory] = []
        for group, members, representatives in zip(
            analysis.sealed_content["groups"],
            analysis.group_members,
            analysis.group_representatives,
            strict=True,
        ):
            samples = self._samples(representatives, analysis)
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
            geo_observations=snapshot.geo_observations,
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
        organized_count = sum(
            len(directory.member_refs) for directory in document.directories
        )
        outcome_count = sum(
            len(outcome.member_refs) for outcome in document.other_outcomes
        )
        tree = _tree_text(document)
        geo_evidence = _geo_evidence_html(document.geo_observations)
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
  <main>{directories}</main>
  <article><h2>其他已交代结果</h2><ul>{outcomes}</ul></article>
  {geo_evidence}
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
        self, representative_refs: tuple[str, ...], analysis: CandidateAnalysis
    ) -> tuple[PreviewSample, ...]:
        samples: list[PreviewSample] = []
        for ref in representative_refs:
            view = analysis.source_views.get(ref, {})
            uri = self.asset_resolver(ref, view)
            label = _source_label(ref, view)
            if uri is not None or not samples:
                samples.append(PreviewSample(ref, label, uri))
            if len(samples) == 2:
                break
        return tuple(samples)

    @staticmethod
    def _directory_html(directory: PreviewDirectory, *, member_limit: int) -> str:
        display_path = "/".join(directory.relative_path) or "(root)"
        samples = []
        for sample in directory.samples:
            if sample.uri:
                samples.append(
                    f'<figure><img src="{escape(sample.uri, quote=True)}" alt="{escape(sample.label, quote=True)}"><figcaption>{escape(sample.label)}</figcaption></figure>'
                )
            else:
                samples.append(
                    f'<figure><div class="missing">Preview unavailable</div><figcaption>{escape(sample.label)}</figcaption></figure>'
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


def _geo_evidence_html(observations: tuple[Mapping[str, Any], ...]) -> str:
    if not observations:
        return ""
    items: list[str] = []
    for observation in observations:
        result = observation.get("result")
        result = result if isinstance(result, Mapping) else {}
        names: list[str] = []
        components = result.get("components")
        for component in components if isinstance(components, list) else ():
            if not isinstance(component, Mapping):
                continue
            candidates = component.get("candidates")
            for candidate in candidates if isinstance(candidates, list) else ():
                if isinstance(candidate, Mapping) and isinstance(
                    candidate.get("name"), str
                ):
                    names.append(str(candidate["name"]))
        attempts = result.get("attempts")
        providers = [
            str(attempt["provider"])
            for attempt in (attempts if isinstance(attempts, list) else ())
            if isinstance(attempt, Mapping) and isinstance(attempt.get("provider"), str)
        ]
        subject_names = ", ".join(names) or "No place candidate"
        provider_names = ", ".join(providers) or "No provider attempt"
        items.append(
            "<li><strong>Candidate observation:</strong> "
            + escape(subject_names)
            + " <span class=\"binding\">Providers: "
            + escape(provider_names)
            + "; outcome: "
            + escape(str(result.get("outcome", "unknown")))
            + "</span></li>"
        )
    return (
        '<article><h2>地点候选证据</h2><p class="binding">Provider observations; '
        "not confirmed Plan truth.</p><ul>"
        + "".join(items)
        + "</ul></article>"
    )


def _source_label(ref: str, view: Mapping[str, Any]) -> str:
    locator = view.get("locator")
    if isinstance(locator, Mapping) and isinstance(locator.get("value"), str):
        return Path(locator["value"]).name
    return ref


def _default_asset_resolver(ref: str, view: Mapping[str, Any]) -> str | None:
    del ref
    locator = view.get("locator")
    if not isinstance(locator, Mapping):
        return None
    value = locator.get("value")
    if not isinstance(value, str):
        return None
    suffix = Path(value).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
        return None
    path = Path(value)
    if not path.is_absolute() or not path.is_file():
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
