"""Isolated installed CLI/MCP sensitivity delivery, reuse, recovery and core reads."""

import argparse
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from run_precheck_delivery_smoke import make_media, check_public


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configuration(models, selected):
    text = "[embedding]\nenabled=false\n[sensitivity]\nenabled=true\n"
    for name in ("freepik", "nudenet640"):
        path = models / ("freepik" if name == "freepik" else "640m.onnx")
        text += f"[sensitivity.models.{name}]\nenabled={str(name in selected).lower()}\nmodel_path={json.dumps(str(path))}\n"
    return text


def work_snapshot(workspace):
    with sqlite3.connect(workspace / "precheck/work.sqlite3") as db:
        return db.execute(
            "SELECT capability,work_id,attempt_count,output_digest FROM work_records ORDER BY work_id"
        ).fetchall()


def seals(workspace):
    # Hash actual result files, independently of DB's recorded digest.
    return {
        str(p): digest(p)
        for p in (workspace / "precheck").rglob("*")
        if p.is_file()
        and p.suffix not in {".sqlite3", ".db"}
        and not p.name.endswith(("-wal", "-shm"))
        and "_results" in p.parts
    }


async def exercise(args):
    args.output.mkdir(exist_ok=False)
    root = args.output
    source = root / "source"
    before = make_media(source)
    workspace = root / "dataset"
    workspace.mkdir()
    env = {
        **os.environ,
        "MEDIASENSE_CONFIG_HOME": str(root / "config"),
        "MEDIASENSE_DATA_HOME": str(root / "data"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTORCH_ENABLE_MPS_FALLBACK": "0",
        "AMAP_API_KEY": "",
        "GOOGLE_MAPS_API_KEY": "",
    }
    env.pop("PYTHONPATH", None)
    report = {
        "python": sys.executable,
        "hosts": {"model": str(args.host), "core": str(args.core_host)},
        "scenarios": [],
    }
    opened = json.loads(
        subprocess.check_output(
            [
                str(args.host),
                "dataset",
                "open",
                str(source),
                "--workspace",
                str(workspace),
                "--json",
            ],
            env=env,
            cwd=root,
            text=True,
        )
    )
    dataset = opened["dataset_ref"]
    (workspace / "config.toml").write_text(
        configuration(args.models, {"freepik", "nudenet640"})
    )

    @asynccontextmanager
    async def connect(host):
        params = StdioServerParameters(
            command=str(host), args=["mcp"], cwd=str(root), env=env
        )
        async with (
            stdio_client(params) as (incoming, outgoing),
            ClientSession(incoming, outgoing) as session,
        ):
            await session.initialize()
            yield session

    async def open_dataset(session, src=source, ws=workspace):
        response = await session.call_tool(
            "mediasense.dataset.open", {"source_root": str(src), "workspace": str(ws)}
        )
        assert not response.is_error, response
        return response.structured_content["dataset_ref"]

    async def call(session, tool, action, ds=dataset, **kwargs):
        request = {"action": action, "dataset_ref": ds, **kwargs}
        response = await session.call_tool("mediasense.precheck." + tool, request)
        assert response.content == [] and not response.is_error, response
        value = response.structured_content
        assert "error" not in value, value
        check_public(value)
        return value

    async def wait(session, ref, ds):
        with anyio.fail_after(240):
            while True:
                state = await call(session, "run", "status", ds=ds, run_ref=ref)
                if state["state"] != "running":
                    return state
                await anyio.sleep(0.1)

    async def run(session, index, ds=dataset, prior=None):
        start = await call(
            session,
            "run",
            "start",
            ds=ds,
            request_id=f"request:sensitivity-{index}",
            **({"prior_result_ref": prior} if prior else {}),
        )
        ref = start["run_ref"]
        state = await wait(session, ref, ds)
        if (
            state["state"] == "paused"
            and state.get("reason", {}).get("code") == "scope_confirmation_required"
        ):
            await call(
                session,
                "run",
                "resume",
                ds=ds,
                run_ref=ref,
                decision={
                    "kind": "source_scope",
                    "inventory_fingerprint": state["confirmation"][
                        "inventory_fingerprint"
                    ],
                    "default_disposition": "include",
                    "exceptions": [],
                },
            )
            state = await wait(session, ref, ds)
        return ref, state

    async def inspect(session, result, selected, ds=dataset):
        review = await call(
            session,
            "read",
            "review",
            ds=ds,
            result_ref=result,
            include=["execution_boundary"],
        )
        assert review["execution_boundary"]["current_provider_requests"] == 0
        assert review["result"]["readiness"] == "plan_ready", review
        resolution = await call(
            session,
            "read",
            "resolve",
            ds=ds,
            result_ref=result,
            source_set={
                "kind": "precheck_relation",
                "origin": result,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        )
        refs = [m["source_item_ref"] for m in resolution["members"]]
        expanded = await call(
            session,
            "read",
            "expand",
            ds=ds,
            result_ref=result,
            source_item_refs=refs,
            include=["observations"],
        )
        observations = [
            o
            for item in expanded["items"]
            for o in item["included"]["observations"]
            if o["name"] == "content_sensitivity"
        ]
        available = [o for o in observations if o["status"] == "available"]
        actual = {
            ("freepik" if o["value"]["profile"].startswith("freepik") else "nudenet640")
            for o in available
        }
        assert actual == set(selected), (actual, selected, observations)
        assert all(
            o.get("basis", {}).get("code") == "capability_disabled"
            for o in observations
            if o["status"] == "not_checked"
        ), observations
        for o in available:
            assert o["provenance"]["input_evidence_ref"]
            if "region_detections" in o["value"]:
                assert o["provenance"]["actual_execution"]["actual_providers"] == [
                    "CPUExecutionProvider"
                ]
            else:
                assert o["provenance"]["actual_execution"]["device"] == "mps"
        return {
            "result_ref": result,
            "available_observations": len(available),
            "observations": observations,
            "review": review,
        }

    async with connect(args.host) as session:
        await open_dataset(session)
        prior = None
        baseline = None
        hashes = {}
        for index, selected in enumerate(
            [
                {"freepik", "nudenet640"},
                {"freepik"},
                {"nudenet640"},
                set(),
                {"freepik", "nudenet640"},
            ]
        ):
            (workspace / "config.toml").write_text(configuration(args.models, selected))
            _, state = await run(session, index, prior=prior)
            assert state["state"] == "completed", state
            prior = state["result"]["ref"]
            delivery = await inspect(session, prior, selected)
            report["scenarios"].append({"selection": sorted(selected), **delivery})
            snapshot = work_snapshot(workspace)
            if baseline is None:
                baseline = snapshot
                hashes = seals(workspace)
                assert hashes, "No sealed files found"
            else:
                # Scope/compression can attach new bookkeeping; successful producer
                # identities and attempts for retained work must stay unchanged.
                assert [r for r in snapshot if r[0] == "content-sensitivity"] == [
                    r for r in baseline if r[0] == "content-sensitivity"
                ]
                assert {r[1]: r for r in snapshot}.items() >= {
                    r[1]: r for r in baseline
                }.items()
                assert {p: digest(Path(p)) for p in hashes} == hashes
        plan = await session.call_tool(
            "mediasense.plan.work",
            {
                "dataset_ref": dataset,
                "request": {
                    "action": "create",
                    "request_id": "request:sensitivity-plan",
                    "result_ref": prior,
                },
            },
        )
        assert not plan.is_error, plan
        assert plan.structured_content["outcome"] == "ok", plan
        report["plan"] = plan.structured_content

        # Fresh isolated dataset: missing weights block; editing selection must not
        # change the frozen Run. Restoring exact assets resumes that Run.
        recovery = root / "recovery-dataset"
        recovery.mkdir()
        missing = root / "recovery-models"
        recovery_ds = await open_dataset(session, ws=recovery)
        (recovery / "config.toml").write_text(
            configuration(missing, {"freepik", "nudenet640"})
        )
        ref, state = await run(session, "missing", ds=recovery_ds)
        assert (
            state["state"] == "blocked"
            and state["reason"]["code"] == "sensitivity_backend_unavailable"
        ), state
        (recovery / "config.toml").write_text(configuration(missing, set()))
        shutil.copytree(args.models, missing)
        await call(session, "run", "resume", ds=recovery_ds, run_ref=ref)
        recovered = await wait(session, ref, recovery_ds)
        assert recovered["state"] == "completed", recovered
        report["recovery"] = await inspect(
            session,
            recovered["result"]["ref"],
            {"freepik", "nudenet640"},
            ds=recovery_ds,
        )

    # Core-only Host: no optional inference distributions, no configured weights;
    # invalid legacy config must not prevent Read. Cached new execution also works.
    moved = args.models.with_name(args.models.name + "-temporarily-unavailable")
    args.models.rename(moved)
    try:
        async with connect(args.core_host) as session:
            (workspace / "config.toml").write_text(
                '[sensitivity]\nenabled=true\nnsfw_revision="' + "a" * 40 + '"\n'
            )
            await open_dataset(session)
            report["core_read"] = await inspect(
                session, prior, {"freepik", "nudenet640"}
            )
            (workspace / "config.toml").write_text(
                configuration(args.models, {"freepik", "nudenet640"})
            )
            _, state = await run(session, "core-cached", prior=prior)
            assert state["state"] == "completed", state
            report["core_cached"] = await inspect(
                session, state["result"]["ref"], {"freepik", "nudenet640"}
            )
            assert {r[1]: r for r in work_snapshot(workspace)}.items() >= {
                r[1]: r for r in baseline
            }.items()
            if args.legacy:
                legacy = json.loads(args.legacy.read_text())
                ds = await open_dataset(
                    session, Path(legacy["source"]), Path(legacy["workspace"])
                )
                read = await call(
                    session, "read", "review", ds=ds, result_ref=legacy["result_ref"]
                )
                values = [
                    o["value"]
                    for item in read["items"]
                    for src in item["source_items"]
                    for o in src["observations"]
                    if o["name"] == "content_sensitivity" and o["status"] == "available"
                ]
                labels = [
                    label for value in values for label in value.get("labels", [])
                ]
                assert any(
                    x["threshold"] == 99
                    and x["mild_threshold"] == 33
                    and not x["sensitive"]
                    for x in labels
                )
                assert digest(Path(legacy["result_path"])) == legacy["sha256"]
                report["legacy_read"] = {
                    "unchanged_sha256": legacy["sha256"],
                    "read": read,
                }
    finally:
        moved.rename(args.models)
    assert {p.name: digest(p) for p in source.iterdir()} == before
    assert {p: digest(Path(p)) for p in hashes} == hashes
    report["status"] = "passed"
    report["source_sha256"] = before
    report["sealed_sha256"] = hashes
    (root / "report.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "status": "passed",
                "scenarios": len(report["scenarios"]),
                "legacy_read": "legacy_read" in report,
                "output": str(root),
            },
            indent=2,
        )
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", type=Path, required=True)
    p.add_argument("--core-host", type=Path, required=True)
    p.add_argument("--models", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--legacy", type=Path)
    args = p.parse_args()
    anyio.run(exercise, args)


if __name__ == "__main__":
    main()
