"""Actual isolated wheel/MCP Plan interaction acceptance on synthetic media only.

Run using the installed Python: run_plan_interaction_smoke.py --host ... --output ...
Keeps a bounded JSON trace and HTML for inspection; never switches global tools.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
from html.parser import HTMLParser
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
from urllib.parse import unquote, urlsplit

from PIL import Image

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import mediasense
from mediasense.plan import PlanPreviewRenderer
from mediasense.runtime.host import RuntimeHost
from run_distribution_smoke import _seed_plan_ready_result


async def exercise(
    host: Path, root: Path, browser: Path | None = None, paged_preview: bool = False
):
    package = Path(mediasense.__file__).resolve()
    assert "site-packages" in package.parts, package
    source, workspace = root / "source", root / "dataset"
    source.mkdir()
    env = {
        **os.environ,
        "MEDIASENSE_CONFIG_HOME": str(root / "config"),
        "MEDIASENSE_DATA_HOME": str(root / "data"),
        "AMAP_API_KEY": "",
        "GOOGLE_MAPS_API_KEY": "",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    env.pop("PYTHONPATH", None)
    trace = []
    elicited = []

    async def no_popup(*args):
        elicited.append(args)
        raise AssertionError("Plan must not introduce an MCP confirmation popup")

    @asynccontextmanager
    async def connect():
        params = StdioServerParameters(
            command=str(host), args=["mcp"], cwd=str(root), env=env
        )
        async with (
            stdio_client(params) as (incoming, outgoing),
            ClientSession(incoming, outgoing, elicitation_callback=no_popup) as session,
        ):
            await session.initialize()
            yield session

    async def call(session, name, args):
        result = await session.call_tool(name, args)
        assert result.content == [], result
        assert result.structured_content is not None, result
        trace.append(
            {"tool": name, "arguments": args, "response": result.structured_content}
        )
        return result.structured_content

    async def opened(session):
        return await call(
            session,
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )

    async with connect() as session:
        listing = await session.list_tools()
        descriptors = {tool.name: tool.meta for tool in listing.tools}
        dataset = (await opened(session))["dataset_ref"]
    result_ref = (
        seed_paged_preview_result(workspace, source, dataset)
        if paged_preview
        else _seed_plan_ready_result(host, workspace, source, dataset, env, root)
    )
    original = (source / "original.jpg").read_bytes()
    notes = "用户知识仅适用于此项；未确认完整方案。\n原件路径不表示托管。" * 2000
    async with connect() as session:
        assert (await opened(session))["dataset_ref"] == dataset

        async def plan(request, authority=None):
            args = {"dataset_ref": dataset, "request": request}
            if authority is not None:
                args["authority"] = authority
            return await call(session, "mediasense.plan.work", args)

        created = await plan(
            {
                "action": "create",
                "result_ref": result_ref,
                "request_id": "request:smoke-create",
            }
        )
        work = created["work_ref"]
        note_request = {
            "action": "update",
            "work_ref": work,
            "base_revision": created["revision"],
            "request_id": "request:smoke-notes",
            "working_notes": notes,
        }
        saved = await plan(note_request)
        assert saved["outcome"] == "ok"
        view = await plan({"action": "inspect", "work_ref": work})
        assert view["sections"]["working_notes"] == notes
        assert view["sections"]["content"] is None
        assert "candidate_content_identity" not in view
        assert (
            view["sections"]["validation"]["issues"][0]["code"] == "candidate_missing"
        )
    async with connect() as session:
        await opened(session)

        async def plan(request, authority=None):
            args = {"dataset_ref": dataset, "request": request}
            if authority is not None:
                args["authority"] = authority
            return await call(session, "mediasense.plan.work", args)

        assert await plan(note_request) == saved
        view = await plan({"action": "inspect", "work_ref": work})
        assert (
            view["revision"] == saved["revision"]
            and view["sections"]["working_notes"] == notes
        )
        scope = {
            "kind": "precheck_relation",
            "origin": result_ref,
            "relation": "accounts_for",
            "direction": "outbound",
        }
        reviewed = await call(
            session,
            "mediasense.precheck.read",
            {"dataset_ref": dataset, "action": "review", "result_ref": result_ref},
        )
        evidence = [item["evidence_ref"] for item in reviewed["items"]]
        while reviewed["page"]["next_cursor"] is not None:
            reviewed = await call(
                session,
                "mediasense.precheck.read",
                {
                    "dataset_ref": dataset,
                    "action": "review",
                    "result_ref": result_ref,
                    "page": {"cursor": reviewed["page"]["next_cursor"]},
                },
            )
            evidence.extend(item["evidence_ref"] for item in reviewed["items"])
        candidate = {
            "result_ref": result_ref,
            "scope": scope,
            "logical_root": "Synthetic collection",
            "groups": [
                {
                    "relative_path": ["Gathering"],
                    "members": scope,
                    "source_naming": {"default": "preserve_source_basename"},
                }
            ],
            "other_outcomes": [],
            "decision_notes": [
                {
                    "summary": "用户口述仅适用此范围 <script>alert(1)</script>",
                    "applies_to": scope,
                    "evidence_refs": evidence,
                }
            ],
        }

        async def update(state, request_id, **fields):
            result = await plan(
                {
                    "action": "update",
                    "work_ref": work,
                    "base_revision": state["revision"],
                    "request_id": request_id,
                    **fields,
                }
            )
            assert result["outcome"] == "ok", result
            return result

        current = await update(
            saved, "request:smoke-candidate", candidate_content=candidate
        )
        baseline = await plan({"action": "inspect", "work_ref": work})
        invalid_candidates = [
            {"plan_ref": "frozen-plan:injected"},
            {"contract": "mediasense.frozen-plan"},
            {"seal": {}},
            {"other_outcomes": [None]},
            {"other_outcomes": 1},
        ]
        for index, fields in enumerate(invalid_candidates):
            invalid = {**deepcopy(candidate), **fields}
            response = await plan(
                {
                    "action": "update",
                    "work_ref": work,
                    "base_revision": current["revision"],
                    "request_id": f"request:smoke-invalid-{index}",
                    "candidate_content": invalid,
                    "working_notes": "must not save",
                    "organization_preferences": {"invalid": True},
                }
            )
            assert response["error"]["code"] == "candidate_invalid", response
            assert await plan({"action": "inspect", "work_ref": work}) == baseline
        identity = (await plan({"action": "inspect", "work_ref": work}))[
            "candidate_content_identity"
        ]
        withdrawn = await update(
            current,
            "request:smoke-withdraw",
            candidate_content=None,
            working_notes="",
            organization_preferences={},
        )
        absent = await plan({"action": "inspect", "work_ref": work})
        assert (
            absent["sections"]["content"] is None
            and absent["sections"]["working_notes"] == ""
        )
        assert (
            absent["sections"]["preferences"] == {}
            and "candidate_content_identity" not in absent
        )
    async with connect() as session:
        await opened(session)

        async def plan(request, authority=None):
            args = {"dataset_ref": dataset, "request": request}
            if authority is not None:
                args["authority"] = authority
            return await call(session, "mediasense.plan.work", args)

        assert (await plan({"action": "inspect", "work_ref": work}))["sections"][
            "content"
        ] is None
        current = await plan(
            {
                "action": "update",
                "work_ref": work,
                "base_revision": withdrawn["revision"],
                "request_id": "request:smoke-replace",
                "candidate_content": candidate,
            }
        )
        assert current["outcome"] == "ok"
        inspected = await plan({"action": "inspect", "work_ref": work})
        assert inspected["candidate_content_identity"] == identity
        # Render using the same installed production composition, never checkout code.
        local = RuntimeHost()
        local.open_dataset(str(source), str(workspace))
        renderer = PlanPreviewRenderer(local._datasets[dataset].plan_work)
        reader = local._datasets[dataset].precheck_read
        real_read = reader.read
        preview_pages = []

        def observe_preview_read(request):
            response = real_read(request)
            if request["action"] == "review" and "evidence_refs" in request:
                preview_pages.append(
                    {
                        "request": deepcopy(request),
                        "page": response["page"],
                        "items": [
                            {
                                "evidence_ref": item["evidence_ref"],
                                "access_kind": item.get("access", {}).get("kind"),
                            }
                            for item in response["items"]
                        ],
                    }
                )
            return response

        reader.read = observe_preview_read
        try:
            document = renderer.write_html(
                work, current["revision"], root / "preview.html"
            )
        finally:
            reader.read = real_read
        if paged_preview:
            assert len(preview_pages) == 2, preview_pages
            first, second = preview_pages
            assert first["page"]["stop_reason"] == "byte_limit"
            assert first["items"][0]["access_kind"] == "inline"
            assert second["items"][0]["access_kind"] == "local_artifact"
            assert (
                first["request"]["evidence_refs"] == second["request"]["evidence_refs"]
            )
            assert len(first["request"]["evidence_refs"]) == 2
            assert second["request"]["page"] == {
                "limit": 16,
                "cursor": first["page"]["next_cursor"],
            }
            assert second["page"]["next_cursor"] is None
        assert document.candidate_content_identity == identity
        html = (root / "preview.html").read_text()
        assert (
            "&lt;script&gt;alert(1)&lt;/script&gt;" in html
            and "<script>alert(1)</script>" not in html
        )
        assert result_ref in html and all(ref in html for ref in evidence)
        image_checks = verify_preview_images(root / "preview.html")
        assert image_checks and "Preview unavailable" not in html
        samples = [
            sample for directory in document.directories for sample in directory.samples
        ]
        assert all(sample.evidence_ref in evidence and sample.uri for sample in samples)
        browser_checks = verify_browser_images(browser, root) if browser else None
        seal = {
            "action": "seal",
            "work_ref": work,
            "revision": current["revision"],
            "candidate_content_identity": identity,
            "request_id": "request:smoke-seal",
        }
        assert (await plan(seal))["error"]["code"] == "confirmation_required"
        authority = {
            "principal_ref": "human:synthetic-acceptance",
            "confirmed_content_identity": identity,
            "confirmed_at": "2026-09-12T10:00:00+00:00",
        }
        wrong = {**authority, "confirmed_content_identity": "sha256:" + "0" * 64}
        assert (await plan(seal, wrong))["error"]["code"] == "content_identity_mismatch"
        newer = await plan(
            {
                "action": "update",
                "work_ref": work,
                "base_revision": current["revision"],
                "request_id": "request:smoke-after-preview-notes",
                "working_notes": "same content; synthetic acceptance context",
            }
        )
        assert (await plan(seal, authority))["error"]["code"] == "revision_conflict"
        latest = await plan({"action": "inspect", "work_ref": work})
        assert latest["candidate_content_identity"] == identity
        seal["revision"] = newer["revision"]
        frozen = await plan(seal, authority)
        assert frozen["outcome"] == "ok" and frozen["state"] == "closed", frozen
        assert await plan(seal, authority) == frozen
        assert (
            frozen["plan_ref"]
            == frozen["frozen_plan"]["sealed_content"]["plan_ref"]
            == inspected["sections"]["content"]["value"]["plan_ref"]
        )
        assert (
            frozen["frozen_plan"]["sealed_content"]["decision_notes"]
            == candidate["decision_notes"]
        )
        assert "working_notes" not in frozen["frozen_plan"]["sealed_content"]
    assert not elicited
    assert (source / "original.jpg").read_bytes() == original
    report = {
        "status": "passed",
        "python": sys.executable,
        "package": str(package),
        "host": str(host),
        "tools": descriptors,
        "source_sha256": hashlib.sha256(original).hexdigest(),
        "candidate_identity": identity,
        "calls": len(trace),
        "image_checks": image_checks,
        "preview_pages": preview_pages,
        "browser_checks": browser_checks,
        "mcp_elicitations": 0,
        "confirmation_limit": "Synthetic trusted client context; not independent Human authentication",
        "trace": trace,
    }
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {k: v for k, v in report.items() if k != "trace"},
            ensure_ascii=False,
            indent=2,
        )
    )


def seed_paged_preview_result(workspace, source, dataset):
    """Real sealed synthetic Result: one context card, then one picture, >512KiB together."""
    from mediasense.dataset_reference import dataset_id_from_ref
    from mediasense.precheck import AccountingStore, ImageRenditionProducer, ResultStore

    Image.new("RGB", (80, 40), "purple").save(source / "original.jpg")
    database = workspace / "precheck" / "work.sqlite3"
    accounting = AccountingStore(database)
    run_id = accounting.start_or_resume_run(dataset_id_from_ref(dataset), source)
    accounting.process_run(run_id)
    rendition = ImageRenditionProducer(database).produce(run_id, Path("original.jpg"))
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [rendition.work.work_id])
    anchor = draft.evidence[0]
    picture = replace(
        anchor,
        observations=(
            *anchor.observations,
            {
                "name": "retained_text",
                "status": "available",
                "value": "x" * 300_000,
            },
        ),
    )
    context = replace(
        picture,
        ref="evidence:000-context",
        artifact_id=None,
        work_id=None,
        access={"kind": "inline", "value": {"description": "non-image context"}},
    )
    draft = replace(
        draft,
        evidence=(context, picture),
        entry_evidence=(context.ref, anchor.ref),
        relationships=(
            *draft.relationships,
            *(
                replace(r, origin_ref=context.ref)
                for r in draft.relationships
                if r.origin_ref == anchor.ref
            ),
        ),
    )
    return store.seal(draft).result_ref


class PreviewHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []
        self.result = ""
        self.in_result = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img":
            self.images.append(attrs["src"])
        if attrs.get("id") == "result":
            self.in_result = True

    def handle_endtag(self, tag):
        if tag == "pre":
            self.in_result = False

    def handle_data(self, data):
        if self.in_result:
            self.result += data


def verify_preview_images(path):
    parsed = PreviewHTML()
    parsed.feed(path.read_text())
    results = []
    for uri in parsed.images:
        url = urlsplit(uri)
        assert url.scheme == "file" and not url.netloc
        file = Path(unquote(url.path))
        with Image.open(file) as picture:
            picture.load()
            assert picture.width > 0 and picture.height > 0
            results.append(
                {"uri": uri, "width": picture.width, "height": picture.height}
            )
    assert results, "The final HTML contains no displayable images"
    return results


def verify_browser_images(browser, root):
    harness = root / "browser-check.html"
    harness.write_text("""<!doctype html><iframe id="preview" src="preview.html"></iframe>
<pre id="result"></pre><script>
window.onload = () => {
 const doc = document.getElementById('preview').contentDocument;
 document.getElementById('result').textContent = JSON.stringify(
   Array.from(doc.images).map(img => ({src: img.src, complete: img.complete,
       width: img.naturalWidth, height: img.naturalHeight})));
};
</script>""")
    completed = subprocess.run(
        [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--no-default-browser-check",
            "--allow-file-access-from-files",
            f"--user-data-dir={root / 'browser-profile'}",
            "--virtual-time-budget=3000",
            "--dump-dom",
            harness.as_uri(),
        ],
        text=True,
        capture_output=True,
        timeout=40,
        check=True,
    )
    parsed = PreviewHTML()
    parsed.feed(completed.stdout)
    results = json.loads(parsed.result)
    assert results and all(
        item["complete"] and item["width"] > 0 and item["height"] > 0
        for item in results
    )
    (root / "browser-images.json").write_text(json.dumps(results, indent=2))
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--browser",
        type=Path,
        help="Optional isolated headless Chrome image-load check",
    )
    parser.add_argument(
        "--paged-preview",
        action="store_true",
        help="Exercise byte-limited Evidence review before rendering",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    anyio.run(
        exercise,
        args.host.resolve(),
        args.output.resolve(),
        args.browser,
        args.paged_preview,
    )


if __name__ == "__main__":
    main()
