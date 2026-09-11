"""Bounded real-image check through an exact installed CLI/MCP, outside pytest.

Uses owner-approved prepared image inputs; outputs must be outside the fixture.
Checks actual vectors, source safety, successor reuse, unavailable backend and
same-profile recovery. No network/model downloads are permitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import struct

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def exercise(args):
    root = args.output.absolute()
    root.mkdir(parents=True, exist_ok=False)
    source, workspace = root / "source", root / "dataset"
    source.mkdir()
    workspace.mkdir()
    inputs = json.loads(args.inputs.read_text())["inputs"]
    selected = [r for r in inputs if r["state"] == "ready"][:8]
    for index, row in enumerate(selected):
        original = Path(row["image_path"])
        assert digest(original) == row["image_sha256"]
        target = source / f"input-{index:02d}{original.suffix}"
        shutil.copy2(original, target)
        os.utime(target, (1_780_000_000 + index * 120, 1_780_000_000 + index * 120))
    before = {p.name: digest(p) for p in source.iterdir()}
    model = root / "model"
    model.symlink_to(args.model_path.absolute(), target_is_directory=True)
    guard = root / "guard"
    guard.mkdir()
    (guard / "sitecustomize.py").write_text('''import socket, os, importlib.util
from pathlib import Path
Path(os.environ["MS_PROBE_IMPORT"]).write_text(importlib.util.find_spec("mediasense").origin)
original = socket.socket.connect
def connect(self, address):
    if self.family in (socket.AF_INET, socket.AF_INET6):
        with open(os.environ["MS_PROBE_NETWORK"], "a") as stream: stream.write("attempt\\n")
        raise RuntimeError("Network forbidden in installed DINOv3 check")
    return original(self, address)
socket.socket.connect = connect
socket.socket.connect_ex = connect
''')
    environment = {**os.environ, "MEDIASENSE_CONFIG_HOME": str(root / "config"),
                   "MEDIASENSE_DATA_HOME": str(root / "data"), "PYTHONPATH": str(guard),
                   "MS_PROBE_IMPORT": str(root / "import.txt"), "MS_PROBE_NETWORK": str(root / "network.txt"),
                   "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
                   "AMAP_API_KEY": "", "GOOGLE_MAPS_API_KEY": ""}
    db = workspace / "precheck/work.sqlite3"
    initialized = subprocess.run([str(args.executable), "dataset", "open", str(source), "--workspace", str(workspace), "--json"], env=environment, cwd=root, capture_output=True, text=True, check=True)
    assert json.loads(initialized.stdout).get("dataset_ref"), initialized.stdout
    (workspace / "config.toml").write_text('[embedding]\nenabled=true\nmodel_path=' + json.dumps(str(model)) + '\n')

    def works():
        with sqlite3.connect(db) as connection:
            return connection.execute("SELECT capability, work_id, attempt_count, output_digest FROM work_records WHERE capability IN ('source-metadata','image-rendition','image-embedding') ORDER BY capability, work_id").fetchall()

    async def session_run(action):
        params = StdioServerParameters(command=str(args.executable), args=["mcp"], cwd=str(root), env=environment)
        async with stdio_client(params) as (incoming, outgoing), ClientSession(incoming, outgoing) as session:
            await session.initialize()
            response = await session.call_tool("mediasense.dataset.open", {"source_root": str(source), "workspace": str(workspace)})
            assert not response.is_error, response
            assert response.structured_content.get("dataset_ref"), response
            dataset = response.structured_content["dataset_ref"]
            assert response.structured_content["configuration"]["local_embedding"]["profile"]["image_size"] == 384

            async def call(tool, action, **kwargs):
                reply = await session.call_tool("mediasense.precheck." + tool, {"action": action, "dataset_ref": dataset, **kwargs})
                assert not reply.is_error and reply.content == [], reply
                value = reply.structured_content
                assert "error" not in value, value
                return value

            async def wait(ref):
                with anyio.fail_after(180):
                    while True:
                        state = await call("run", "status", run_ref=ref)
                        if state["state"] != "running":
                            return state
                        await anyio.sleep(0.1)

            if action == "resume":
                ref = evidence["blocked"]["run_ref"]
                await call("run", "resume", run_ref=ref)
            else:
                started = await call("run", "start", request_id="dinov3-smoke-" + action,
                                     **({"prior_result_ref": evidence["first"]["result"]["ref"]} if action != "first" else {}))
                ref = started["run_ref"]
            state = await wait(ref)
            if state["state"] == "paused" and state.get("reason", {}).get("code") == "scope_confirmation_required":
                await call("run", "resume", run_ref=ref, decision={"kind": "source_scope", "inventory_fingerprint": state["confirmation"]["inventory_fingerprint"], "default_disposition": "include", "exceptions": []})
                state = await wait(ref)
            if action == "blocked":
                assert state["state"] == "blocked", state
                assert state["reason"]["code"] == "embedding_backend_unavailable", state
            else:
                assert state["state"] == "completed", state
                page = await call("read", "review", result_ref=state["result"]["ref"], include=["execution_boundary"])
                assert page["execution_boundary"]["current_provider_requests"] == 0
                assert page["execution_boundary"]["billable_calls"] == 0
                assert page["accounting"]["total"] == len(selected)
                (root / f"{action}-read.json").write_text(json.dumps(page, indent=2))
            return {**state, "run_ref": ref}

    evidence = {}
    evidence["first"] = await session_run("first")
    first = works()
    assert any(r[0] == "image-embedding" for r in first)
    with sqlite3.connect(db) as connection:
        outputs = [json.loads(r[0])["value"] for r in connection.execute("SELECT output_json FROM work_records WHERE capability='image-embedding'")]
        for relative, size in connection.execute("SELECT relative_path, size_bytes FROM artifacts WHERE media_type='application/vnd.mediasense.embedding-f32le'"):
            assert size == 768 * 4
            vector = struct.unpack("<768f", (db.parent / relative).read_bytes())
            assert all(math.isfinite(v) for v in vector)
            assert abs(math.sqrt(sum(v*v for v in vector)) - 1) < 1e-6
    assert all(o["dimensions"] == 768 and o["normalization"] == "unit_length" and o["encoder_identity"].startswith("dinov3-coreml-384:") for o in outputs), outputs
    evidence["reuse"] = await session_run("reuse")
    assert works() == first, "successor repeated valid work"
    model.unlink()  # Only our test-owned model locator; real weights remain intact.
    evidence["blocked"] = await session_run("blocked")
    assert works() == first
    model.symlink_to(args.model_path.absolute(), target_is_directory=True)
    evidence["resume"] = await session_run("resume")
    assert works() == first
    assert {p.name: digest(p) for p in source.iterdir()} == before
    assert not (root / "network.txt").exists()
    imported = (root / "import.txt").read_text()
    assert "site-packages" in imported and "/src/" not in imported, imported
    evidence.update(source_unchanged=True, network_attempts=0, repeated_work_attempts=0,
                    installed_module=imported, embedding_outputs=outputs, selected_inputs=selected)
    (root / "evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps({"status": "passed", "output": str(root), "embeddings": len(outputs), "installed_module": imported}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    anyio.run(exercise, parser.parse_args())


if __name__ == "__main__":
    main()
