"""Real wheel/stdio/elicitation/Apply probe, using only generated temporary media."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import anyio
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from PIL import Image

from mediasense.precheck import AccountingStore, ImageRenditionProducer, ResultStore
from mediasense.runtime.host import RuntimeHost
from mediasense.runtime.dataset import dataset_id_from_ref

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))
from test_apply_precheck_integration import _plan  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mediasense-apply-b-host-", dir="/private/tmp") as temp:
        home = Path(temp)
        source, destination, workspace = home / "source", home / "destination", home / "workspace"
        for path in (source, destination, home / "config"):
            path.mkdir()
        (home / "config/config.toml").write_text("[embedding]\nenabled=false\n[sensitivity]\nenabled=false\n")
        os.environ["MEDIASENSE_CONFIG_HOME"] = str(home / "config")
        os.environ["MEDIASENSE_DATA_HOME"] = str(home / "data")
        Image.new("RGB", (80, 40), "blue").save(source / "original.jpg")
        original = (source / "original.jpg").read_bytes()
        opened = RuntimeHost().open_dataset(str(source), str(workspace))
        assert opened["outcome"] == "ok", opened
        database = workspace / "precheck/work.sqlite3"
        account = AccountingStore(database)
        run_id = account.start_or_resume_run(dataset_id_from_ref(opened["dataset_ref"]), source)
        account.process_run(run_id)
        rendition = ImageRenditionProducer(database).produce(run_id, Path("original.jpg"))
        store = ResultStore(database)
        result = store.seal(store.build_minimal(run_id, [rendition.work.work_id]))
        prompts = []
        metrics = {}

        async def approve(_context, params):
            prompts.append(params)
            return types.ElicitResult(action="accept", content={})

        async def scenario():
            parameters = StdioServerParameters(command=sys.executable, args=["-m", "mediasense", "mcp"],
                                                cwd=str(home), env=dict(os.environ))
            async with stdio_client(parameters) as (incoming, outgoing), ClientSession(
                incoming, outgoing, elicitation_callback=approve
            ) as session:
                initialized = await session.initialize()
                listing = await session.list_tools()
                metrics["server_version"] = initialized.server_info.version
                metrics["tool_count"] = len(listing.tools)
                for tool in listing.tools:
                    if tool.name.startswith("mediasense.apply."):
                        assert "authority" not in tool.input_schema["properties"]
                opened_rpc = (await session.call_tool("mediasense.dataset.open", {"source_root": str(source), "workspace": str(workspace)})).structured_content
                assert opened_rpc["outcome"] == "ok", opened_rpc
                dataset = opened_rpc["dataset_ref"]

                async def call(name, arguments):
                    return (await session.call_tool(name, arguments)).structured_content

                resolve = {"action": "resolve", "dataset_ref": dataset, "result_ref": result.result_ref,
                           "source_set": {"kind": "precheck_relation", "origin": result.result_ref,
                                          "relation": "accounts_for", "direction": "outbound"}}
                before = await call("mediasense.precheck.read", resolve)
                item = before["members"][0]
                prepare = {"action": "prepare", "request_id": "request:stdio-prepare",
                           "forward": {"frozen_plan": _plan(result_ref=result.result_ref, source_item_ref=item["source_item_ref"]),
                                       "effect": "move_originals", "destination_parent": str(destination),
                                       "current_source_roots": [{"source_root_ref": item["locator"]["source_root_ref"], "current_root": str(source)}]}}

                async def apply(request, **extra):
                    return await call("mediasense.apply.run", {"dataset_ref": dataset, "request": request, **extra})

                prepared = await apply(prepare)
                assert prepared["outcome"] == "ok", prepared
                status = await apply({"action": "status", "run_ref": prepared["run_ref"]})
                assert status["state"] == "ready_for_authorization"
                execute = {"action": "execute", "request_id": "request:stdio-execute", "run_ref": status["run_ref"],
                           "prepared_revision": status["prepared_revision"], "prepared_content_identity": status["prepared_content_identity"]}
                forged = await apply(execute, authority={"principal_ref": "human:forged", "confirmed_content_identity": status["prepared_content_identity"], "confirmed_at": "2026-09-17T00:00:00Z"})
                assert forged["outcome"] == "error" and not prompts and (source / "original.jpg").exists()
                metrics["forged_authority_rejected"] = True
                accepted = await apply(execute)
                assert accepted["outcome"] == "accepted", accepted
                with anyio.fail_after(20):
                    while True:
                        status = await apply({"action": "status", "run_ref": status["run_ref"]})
                        if status["state"] == "closed":
                            break
                        assert status["state"] in {"executing", "verifying"}, status
                        await anyio.sleep(0.02)
                replay = await apply(execute)
                assert replay["observed_state"] == "closed" and len(prompts) == 1
                metrics["whole_preparation_confirmations"] = len(prompts)
                metrics["replay_without_reconfirmation"] = True
                after = await call("mediasense.precheck.read", resolve)
                assert before == after
                metrics["immutable_result_unchanged"] = True
                receipt_ref = status["published_receipt"]["receipt_ref"]
                read = await call("mediasense.apply.read", {"dataset_ref": dataset,
                                  "request": {"action": "inspect", "receipt_ref": receipt_ref}})
                assert read["receipt"]["completion"] == "complete", read
                metrics["receipt_complete"] = True
                assert not (source / "original.jpg").exists()
                assert (destination / "Media/Verified/original.jpg").read_bytes() == original
                metrics["isolated_result_bytes_match"] = True
                metrics["fixture_sha256"] = hashlib.sha256(original).hexdigest()
        anyio.run(scenario)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics))


if __name__ == "__main__":
    main()
