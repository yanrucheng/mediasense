"""Actual installed MCP Runs plus CLI reads/Plan; local synthetic media only."""

from __future__ import annotations

import argparse
from collections import Counter
from contextlib import asynccontextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from time import monotonic

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
import mediasense


async def exercise(executable: Path, root: Path):
    assert "site-packages" in Path(mediasense.__file__).resolve().parts
    source, workspace = root / "source", root / "dataset"
    source.mkdir()
    config = root / "config"
    config.mkdir()
    (config / "config.toml").write_text(
        "[embedding]\nenabled=false\n[sensitivity]\nenabled=false\n"
    )
    for i in range(8):
        Image.new("RGB", (16, 8), ("blue" if i < 4 else "red")).save(
            source / f"{i:02}.jpg"
        )
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    env = {
        **os.environ,
        "MEDIASENSE_CONFIG_HOME": str(config),
        "MEDIASENSE_DATA_HOME": str(root / "data"),
        "AMAP_API_KEY": "",
        "GOOGLE_MAPS_API_KEY": "",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    env.pop("PYTHONPATH", None)
    trace = []
    dataset = None

    def cli(tool, request, *, error=False):
        completed = subprocess.run(
            [
                str(executable),
                "tools",
                "call",
                tool,
                "--source",
                str(source),
                "--workspace",
                str(workspace),
                "--request",
                json.dumps(request),
                "--json",
            ],
            env=env,
            cwd=root,
            capture_output=True,
            text=True,
        )
        value = json.loads(completed.stdout)
        assert (completed.returncode != 0) == error, (value, completed.stderr)
        response = value.get("result", value)
        trace.append(
            {"transport": "cli", "tool": tool, "request": request, "response": response}
        )
        return response

    async def no_effect_confirmation(*args):
        raise AssertionError(
            "Synthetic local inputs must not request provider/model effects"
        )

    @asynccontextmanager
    async def connected():
        params = StdioServerParameters(
            command=str(executable), args=["mcp"], cwd=str(root), env=env
        )
        async with (
            stdio_client(params) as (incoming, outgoing),
            ClientSession(
                incoming, outgoing, elicitation_callback=no_effect_confirmation
            ) as session,
        ):
            await session.initialize()
            yield session

    async def call(session, tool, request, *, error=False):
        arguments = (
            request
            if tool.startswith("mediasense.precheck.")
            or tool == "mediasense.dataset.open"
            else {"dataset_ref": dataset, "request": request}
        )
        value = await session.call_tool(tool, arguments)
        assert value.content == [] and value.structured_content is not None, value
        response = value.structured_content
        assert ("error" in response) == error, value
        if tool.startswith("mediasense.precheck."):
            assert bool(value.is_error) == error, value
        trace.append(
            {"transport": "mcp", "tool": tool, "request": request, "response": response}
        )
        return response

    async def finish(session, ref):
        deadline = monotonic() + 120
        while monotonic() < deadline:
            status = await call(
                session,
                "mediasense.precheck.run",
                {"dataset_ref": dataset, "action": "status", "run_ref": ref},
            )
            if status["state"] == "paused":
                confirmation = status["confirmation"]
                assert confirmation["kind"] == "source_scope", status
                await call(
                    session,
                    "mediasense.precheck.run",
                    {
                        "dataset_ref": dataset,
                        "action": "resume",
                        "run_ref": ref,
                        "decision": {
                            "kind": "source_scope",
                            "inventory_fingerprint": confirmation[
                                "inventory_fingerprint"
                            ],
                            "default_disposition": "include",
                            "exceptions": [],
                        },
                    },
                )
            elif status["state"] != "running":
                assert status["state"] == "completed", status
                return status["result"]["ref"]
            await anyio.sleep(0.05)
        raise AssertionError("Installed Run did not finish")

    async with connected() as session:
        opened = await call(
            session,
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )
        assert opened["outcome"] == "ok", opened
        dataset = opened["dataset_ref"]
        discovered = await session.list_tools()
        descriptors = {t.name: t.meta for t in discovered.tools}
        assert len(descriptors) == 7
        start = {
            "action": "start",
            "dataset_ref": dataset,
            "request_id": "request:installed-a",
        }
        refusal = cli("mediasense.precheck.run", start, error=True)
        assert refusal["error"]["code"] == "persistent_host_required"
        created = await call(session, "mediasense.precheck.run", start)
        old = await finish(session, created["run_ref"])
        old_page = cli(
            "mediasense.precheck.read",
            {
                "action": "review",
                "dataset_ref": dataset,
                "result_ref": old,
                "include": ["preparation", "execution_boundary"],
            },
        )
        assert old_page["accounting"]["total"] == 8
        assert old_page["execution_boundary"]["current_provider_requests"] == 0
        preparation = old_page["preparation"]
        resolved = await call(
            session,
            "mediasense.precheck.read",
            {
                "action": "resolve",
                "dataset_ref": dataset,
                "result_ref": old,
                "source_set": preparation["source_set"],
            },
        )
        selected = [m["source_item_ref"] for m in resolved["members"][:2]]
        work = cli(
            "mediasense.plan.work",
            {
                "action": "create",
                "result_ref": old,
                "request_id": "request:old-work",
                "organization_preferences": {"preserve_source_basename": True},
            },
        )
        assert work["outcome"] == "ok", work
        notes = await call(
            session,
            "mediasense.plan.work",
            {
                "action": "update",
                "work_ref": work["work_ref"],
                "base_revision": work["revision"],
                "request_id": "request:notes",
                "working_notes": "Preserve basenames; inspect new Evidence before deciding the organization.",
            },
        )
        old_work = await call(
            session,
            "mediasense.plan.work",
            {
                "action": "inspect",
                "work_ref": work["work_ref"],
                "sections": ["preferences", "working_notes", "content"],
            },
        )
        modified = deepcopy(preparation)
        modified["profile"]["overrides"] = [
            {
                "source_set": {"kind": "explicit", "source_item_refs": selected},
                "compression": None,
            }
        ]
        next_start = {
            "action": "start",
            "dataset_ref": dataset,
            "request_id": "request:installed-b",
            "prior_result_ref": old,
            **modified,
        }
        successor = await call(session, "mediasense.precheck.run", next_start)
        new = await finish(session, successor["run_ref"])
        assert new != old
        assert await call(session, "mediasense.precheck.run", next_start) == successor
        new_page = await call(
            session,
            "mediasense.precheck.read",
            {
                "action": "review",
                "dataset_ref": dataset,
                "result_ref": new,
                "include": ["preparation", "execution_boundary"],
            },
        )
        assert (
            new_page["accounting"]["total"] == 8
            and new_page["execution_boundary"]["current_provider_requests"] == 0
        )
        assert new_page["preparation"]["profile"]["overrides"][0]["source_set"] == {
            "kind": "profile_scope",
            "index": 0,
        }
        correspondence = await call(
            session,
            "mediasense.precheck.read",
            {
                "action": "resolve",
                "dataset_ref": dataset,
                "result_ref": old,
                "source_set": preparation["source_set"],
                "target_result_ref": new,
            },
        )
        assert all(
            m["correspondence"]["status"] == "matched"
            for m in correspondence["members"]
        )
        assert (
            len(
                {
                    m["correspondence"]["source_item_ref"]
                    for m in correspondence["members"]
                }
            )
            == 8
        )
        new_refs = [
            m["correspondence"]["source_item_ref"] for m in correspondence["members"]
        ]
        evidence = await call(
            session,
            "mediasense.precheck.read",
            {
                "action": "expand",
                "dataset_ref": dataset,
                "result_ref": new,
                "source_item_refs": new_refs[:2],
                "include": ["covering_evidence", "observations"],
            },
        )
        assert len(evidence["items"]) == 2
        new_work = await call(
            session,
            "mediasense.plan.work",
            {
                "action": "create",
                "result_ref": new,
                "request_id": "request:new-work",
                "organization_preferences": old_work["sections"]["preferences"],
            },
        )
        scope = new_page["preparation"]["source_set"]
        candidate = {
            "kind": "candidate",
            "result_ref": new,
            "scope": scope,
            "logical_root": "Media",
            "groups": [
                {
                    "relative_path": ["Collection"],
                    "members": scope,
                    "source_naming": {"default": "preserve_source_basename"},
                }
            ],
            "other_outcomes": [],
            "decision_notes": [],
        }
        saved = await call(
            session,
            "mediasense.plan.work",
            {
                "action": "update",
                "work_ref": new_work["work_ref"],
                "base_revision": new_work["revision"],
                "request_id": "request:new-candidate",
                "organization_content": candidate,
                "working_notes": old_work["sections"]["working_notes"],
            },
        )
        assert saved["outcome"] == "ok", saved
        review = cli(
            "mediasense.plan.work",
            {
                "action": "inspect",
                "work_ref": new_work["work_ref"],
                "sections": ["content", "validation", "working_notes", "view"],
            },
        )
        assert review["sections"]["validation"]["seal_ready"] is True
        await call(
            session,
            "mediasense.plan.work",
            {
                "action": "seal",
                "work_ref": new_work["work_ref"],
                "revision": review["revision"],
                "candidate_content_identity": review["candidate_content_identity"],
                "request_id": "request:unconfirmed",
            },
            error=True,
        )
        assert (
            cli(
                "mediasense.precheck.read",
                {
                    "action": "review",
                    "dataset_ref": dataset,
                    "result_ref": old,
                    "include": ["preparation", "execution_boundary"],
                },
            )
            == old_page
        )
    async with connected() as session:
        await call(
            session,
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )
        assert await call(session, "mediasense.precheck.run", next_start) == successor
        retained = await call(
            session,
            "mediasense.precheck.read",
            {
                "action": "review",
                "dataset_ref": dataset,
                "result_ref": new,
                "include": ["preparation", "execution_boundary"],
            },
        )
        assert retained == new_page
        old_again = await call(
            session,
            "mediasense.plan.work",
            {
                "action": "inspect",
                "work_ref": work["work_ref"],
                "sections": ["preferences", "working_notes", "content"],
            },
        )
        assert (
            old_again["revision"] == notes["revision"]
            and old_again["result_ref"] == old
        )
    after = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    assert after == before
    subprocess.run(
        [str(executable), "views", "stop", "--json"],
        cwd=root,
        env=env,
        capture_output=True,
        check=False,
    )
    (root / "trace.json").write_text(json.dumps(trace, ensure_ascii=False, indent=2))
    report = {
        "package": str(Path(mediasense.__file__).resolve()),
        "descriptors": descriptors,
        "calls": dict(Counter(row["transport"] for row in trace)),
        "source_unchanged": True,
        "source_sha256": before,
        "old_result": old,
        "new_result": new,
        "old_work": work["work_ref"],
        "new_work": new_work["work_ref"],
        "plan_review": review,
        "provider_requests": 0,
        "model_execution": "disabled",
        "restart_replay": True,
    }
    (root / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in {"plan_review", "descriptors", "source_sha256"}
            },
            indent=2,
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    anyio.run(exercise, args.host.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
