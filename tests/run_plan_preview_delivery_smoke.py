"""Installed ordinary CLI + MCP and Chromium exercise using generated media only.

--playwright points to a locally installed playwright-core module; no browser or
model is downloaded. Outputs remain in an explicitly selected fresh directory.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def run(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source, workspace = root / "source", root / "dataset"
    source.mkdir()
    environment = {
        **os.environ,
        "MEDIASENSE_CONFIG_HOME": str(root / "config"),
        "MEDIASENSE_DATA_HOME": str(root / "data"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }
    environment.pop("PYTHONPATH", None)
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
            env=environment,
        )
    )
    assert opened["outcome"] == "ok", opened
    # Fixture setup may use producer internals; every Plan action below goes
    # through the installed public CLI/MCP, never a renderer or private Work.
    seed = r"""
from pathlib import Path
from PIL import Image
from mediasense.dataset_reference import dataset_id_from_ref
from mediasense.precheck import AccountingStore, ImageRenditionProducer, ResultStore
import json, sys
root=Path(sys.argv[1]); dataset=sys.argv[2]; source=root/'source'; workspace=root/'dataset'
for i in range(1200):Image.new('RGB',(32,24),(i%255,80,120)).save(source/f'item-{i:04}.jpg')
db=workspace/'precheck'/'work.sqlite3'; accounting=AccountingStore(db)
run=accounting.start_or_resume_run(dataset_id_from_ref(dataset),source);accounting.process_run(run)
producer=ImageRenditionProducer(db)
works=[producer.produce(run,Path(f'item-{i:04}.jpg')).work.work_id for i in range(1200)]
store=ResultStore(db); result=store.seal(store.build_minimal(run,works))
print(result.result_ref)
"""
    result_ref = subprocess.check_output(
        [
            str(args.host.parent / "python"),
            "-c",
            seed,
            str(root),
            opened["dataset_ref"],
        ],
        env=environment,
        text=True,
    ).strip()
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    config = {
        "host": str(args.host.resolve()),
        "root": str(root),
        "source": str(source),
        "workspace": str(workspace),
        "dataset_ref": opened["dataset_ref"],
        "result_ref": result_ref,
        "browser": str(args.browser),
        "playwright": str(args.playwright),
        "env": {key: environment[key] for key in (
            "MEDIASENSE_CONFIG_HOME", "MEDIASENSE_DATA_HOME",
            "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
        )},
    }
    config_path = root / "config.json"
    config_path.write_text(json.dumps(config))
    try:
        subprocess.run(
            ["node", str(Path(__file__).with_suffix(".cjs")), str(config_path)],
            env=environment,
            check=True,
            timeout=600,
        )
        anyio.run(mcp_check, args.host, root, environment, config)
    finally:
        subprocess.run(
            [str(args.host), "views", "stop", "--json"], env=environment, check=True
        )
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    report = json.loads((root / "browser-report.json").read_text())
    from jsonschema import Draft202012Validator
    from referencing import Registry, Resource
    from mediasense.runtime.resources import load_contract, schema_path

    contract = load_contract("mediasense.plan.work")
    frozen = json.loads(schema_path("frozen-plan.schema.json").read_text())
    registry = Registry().with_resource(frozen["$id"], Resource.from_contents(frozen))
    inputs = Draft202012Validator(contract["inputSchema"], registry=registry)
    outputs = Draft202012Validator(contract["outputSchema"], registry=registry)
    trace = json.loads((root / "cli-trace.json").read_text())
    for exchange in trace:
        inputs.validate(exchange["request"])
        outputs.validate(exchange["response"])
    outputs.validate(json.loads((root / "mcp-seal.json").read_text()))
    report["validated_actual_cli_exchanges"] = len(trace)
    report.update(
        source_items_unchanged=1200,
        mcp="inspect and seal via installed stdio verified",
        human_review="not_performed",
        weaker_agent="not_performed",
    )
    (root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    config_path.unlink()  # Do not retain inherited environment or credentials.
    print(json.dumps(report, ensure_ascii=False, indent=2))


async def mcp_check(host, root, environment, config):
    async def no_popup(*args):
        raise AssertionError("Plan introduced a confirmation popup")

    params = StdioServerParameters(
        command=str(host), args=["mcp"], cwd=str(root), env=environment
    )
    state = json.loads((root / "browser-report.json").read_text())
    async with (
        stdio_client(params) as (incoming, outgoing),
        ClientSession(incoming, outgoing, elicitation_callback=no_popup) as session,
    ):
        await session.initialize()
        opened = await session.call_tool(
            "mediasense.dataset.open",
            {"source_root": config["source"], "workspace": config["workspace"]},
        )
        assert opened.structured_content["outcome"] == "ok"

        async def plan(request, authority=None):
            value = {"dataset_ref": config["dataset_ref"], "request": request}
            if authority:
                value["authority"] = authority
            response = await session.call_tool("mediasense.plan.work", value)
            assert response.content == []
            return response.structured_content

        inspected = await plan({"action": "inspect", "work_ref": state["work_ref"]})
        assert inspected["sections"]["view"]["status"] in {"ready", "degraded"}
        identity = inspected["candidate_content_identity"]
        request = {
            "action": "seal",
            "work_ref": state["work_ref"],
            "revision": inspected["revision"],
            "candidate_content_identity": identity,
            "request_id": "request:mcp-freeze",
        }
        authority = {
            "principal_ref": "human:synthetic-acceptance",
            "work_ref": state["work_ref"],
            "reviewed_revision": inspected["revision"],
            "confirmed_content_identity": identity,
            "confirmed_at": "2026-09-13T10:00:00Z",
        }
        sealed = await plan(request, authority)
        assert sealed["outcome"] == "ok", sealed
        replay = await plan(request, authority)
        assert {k: v for k, v in sealed.items() if k != "view"} == {
            k: v for k, v in replay.items() if k != "view"
        }
        (root / "mcp-seal.json").write_text(
            json.dumps(sealed, ensure_ascii=False, indent=2)
        )
        # The real browser also opens the Frozen view from the MCP reply.
        subprocess.run(
            [
                "node",
                str(Path(__file__).with_suffix(".cjs")),
                str(root / "config.json"),
                "frozen",
                sealed["view"]["revision_uri"],
            ],
            env=environment,
            check=True,
            timeout=60,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--browser", type=Path, required=True)
    parser.add_argument("--playwright", type=Path, required=True)
    run(parser.parse_args())
