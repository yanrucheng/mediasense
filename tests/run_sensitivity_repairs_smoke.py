"""Installed Run/Read audit delivery with a declared synthetic adapter; no model inference."""

from dataclasses import replace
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import anyio
from PIL import Image
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mediasense.dataset_reference import dataset_id_from_ref
from mediasense.precheck import AccountingStore, PrecheckRunTool
from mediasense.precheck._orchestrator import (
    PrecheckExecutionConfig,
    PrecheckExecutionDependencies,
)
from mediasense.precheck._sensitivity_profiles import FREEPIK, SensitivityPrediction


PROFILE = replace(
    FREEPIK,
    name="synthetic-repair-audit-v1",
    model_id="synthetic/repair",
    device="synthetic",
    cpu_threads=1,
    memory_bytes=1024**2,
    batch_size=2,
    definitions={
        "declared_properties": ["classification_distribution"],
        "taxonomy": "weather",
        "labels": ["dry", "wet"],
        "meaning": "Synthetic exclusive values; not a model quality test.",
    },
    basis={},
)


class SyntheticAdapter:
    profile = PROFILE
    identity = PROFILE.identity
    execution = None
    calls = 0

    def load(self):
        if self.execution is not None:
            return False
        started = time.monotonic()
        self.execution = {
            "device": "synthetic",
            "precision": "float32",
            "load_seconds": time.monotonic() - started,
            "measured_memory_bytes": None,
        }
        return True

    def analyze(self, inputs):
        self.calls += 1
        self.batch_execution = {"inference_input_count": len(inputs)}
        return [
            SensitivityPrediction(
                i.key,
                i.sha256,
                {
                    "classification_distribution": {
                        "taxonomy": "weather",
                        "score_semantics": "categorical_probability",
                        "probabilities": {"dry": 0.25, "wet": 0.75},
                    }
                },
            )
            for i in inputs
        ]

    def close(self):
        self.execution = None


def run_local(tool, dataset, index, prior=None):
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": dataset,
            "request_id": f"request:repair-{index}",
            **({"prior_result_ref": prior} if prior else {}),
        }
    )
    ref = started["run_ref"]
    result = tool.advance(ref)
    if result["state"] == "paused":
        assert result["reason"]["code"] == "scope_confirmation_required", result
        response = tool.run(
            {
                "action": "resume",
                "dataset_ref": dataset,
                "run_ref": ref,
                "decision": {
                    "kind": "source_scope",
                    "inventory_fingerprint": result["confirmation"][
                        "inventory_fingerprint"
                    ],
                    "default_disposition": "include",
                    "exceptions": [],
                },
            }
        )
        assert "error" not in response, response
        result = tool.advance(ref)
    assert result["state"] == "completed", result
    return ref, result["result"]["ref"]


async def exercise(args):
    import mediasense

    assert "/site-packages/" in str(Path(mediasense.__file__).resolve()), (
        mediasense.__file__
    )
    args.output.mkdir(exist_ok=False)
    root = args.output
    source = root / "source"
    source.mkdir()
    for i in range(4):
        Image.new("RGB", (40 + i * 10, 60), "purple").save(source / f"{i}.jpg")
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    env = {
        **os.environ,
        "MEDIASENSE_CONFIG_HOME": str(root / "config"),
        "MEDIASENSE_DATA_HOME": str(root / "data"),
        "AMAP_API_KEY": "",
        "GOOGLE_MAPS_API_KEY": "",
    }
    env.pop("PYTHONPATH", None)
    workspace = root / "dataset"
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
            text=True,
            cwd=root,
        )
    )
    dataset = opened["dataset_ref"]
    db = workspace / "precheck/work.sqlite3"
    store = AccountingStore(db)
    store.register_dataset(dataset_id_from_ref(dataset))
    store.start_or_resume_run(dataset_id_from_ref(dataset), source)
    adapter = SyntheticAdapter()
    tool = PrecheckRunTool(
        db,
        execution_config=PrecheckExecutionConfig(
            metadata=False,
            gpx=False,
            video=False,
            bundles=False,
            sensitivity_profiles=(PROFILE,),
            sensitivity_detector_identities=(adapter.identity,),
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            sensitivity_detectors=(adapter,)
        ),
    )
    first = run_local(tool, dataset, 1)
    assert adapter.calls == 2, adapter.calls
    store.start_or_resume_run(dataset_id_from_ref(dataset), source)
    second = run_local(tool, dataset, 2, first[1])
    assert adapter.calls == 2, "Valid reuse must not rerun the adapter"
    reports = []
    async with (
        stdio_client(
            StdioServerParameters(
                command=str(args.host), args=["mcp"], cwd=str(root), env=env
            )
        ) as (incoming, outgoing),
        ClientSession(incoming, outgoing) as session,
    ):
        await session.initialize()
        response = await session.call_tool(
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )
        assert not response.is_error, response

        async def call(name, request):
            response = await session.call_tool(name, request)
            assert not response.is_error and response.content == [], response
            value = response.structured_content
            assert "error" not in value, value
            return value

        for index, (run_ref, result_ref) in enumerate([first, second]):
            request = {
                "action": "status",
                "dataset_ref": dataset,
                "run_ref": run_ref,
                "include": ["local_execution"],
                "page": {"limit": 1},
            }
            current = await call("mediasense.precheck.run", request)
            audit = current["local_execution"]
            batches = list(audit["batches"])
            assert audit["page"]["total"] == 2 and audit["page"]["next_cursor"], audit
            following = await call(
                "mediasense.precheck.run",
                {
                    **request,
                    "page": {"limit": 1, "cursor": audit["page"]["next_cursor"]},
                },
            )
            batches += following["local_execution"]["batches"]
            assert following["local_execution"]["page"]["next_cursor"] is None
            assert len({b["batch_id"] for b in batches}) == 2
            assert all(
                b["input_count"]
                == b["inference_input_count"]
                == b["included_work_count"]
                == 2
                for b in batches
            )
            origin = "current" if index == 0 else "reused"
            assert all(b["origin"] == origin for b in batches)
            total = audit["models"][0]["recorded_" + origin]
            assert total["batch_count"] == 2 and total["input_count"] == 4
            assert total["processing_wall_seconds"] == sum(
                b["processing_wall_seconds"] for b in batches
            )
            assert total["load_wall_seconds"] == sum(
                b["load_wall_seconds"] for b in batches
            )
            status = await call(
                "mediasense.precheck.run", {**request, "include": ["diagnostics"]}
            )
            assert status["diagnostics"]["local_execution"]["models"] == audit["models"]
            query = {
                "action": "review",
                "dataset_ref": dataset,
                "result_ref": result_ref,
                "include": ["local_execution"],
                "execution_page": {"limit": 1},
            }
            read = await call("mediasense.precheck.read", query)
            assert read["local_execution"]["models"] == audit["models"]
            assert (
                read["local_execution"]["resource_budget"] == audit["resource_budget"]
            )
            read2 = await call(
                "mediasense.precheck.read",
                {
                    **query,
                    "execution_page": {
                        "limit": 1,
                        "cursor": read["local_execution"]["page"]["next_cursor"],
                    },
                },
            )
            assert (
                read["local_execution"]["batches"] + read2["local_execution"]["batches"]
                == batches
            )
            reports.append(
                {"run": current, "read": read, "second_page": read2, "batches": batches}
            )
        if args.prior:
            old = json.loads(args.prior.read_text())
            old_workspace = Path(old["workspace"])
            copy = root / "retained-dataset"
            shutil.copytree(old_workspace, copy)
            hashes = {
                str(p.relative_to(copy)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (copy / "precheck/_results/sealed").glob("*.json")
            }
            response = await session.call_tool(
                "mediasense.dataset.open",
                {"source_root": old["source"], "workspace": str(copy)},
            )
            assert not response.is_error, response
            ds = response.structured_content["dataset_ref"]
            retained = await call(
                "mediasense.precheck.read",
                {
                    "action": "review",
                    "dataset_ref": ds,
                    "result_ref": old["result_ref"],
                    "include": ["local_execution"],
                },
            )
            assert retained["local_execution"] == {
                "status": "not_recorded",
                "resource_budget": None,
                "models": [],
                "batches": [],
                "page": {"total": 0, "next_cursor": None},
            }
            assert {
                str(p.relative_to(copy)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (copy / "precheck/_results/sealed").glob("*.json")
            } == hashes
            reports.append({"retained": retained, "unchanged_sha256": hashes})
    assert {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    } == before
    value = {
        "status": "passed",
        "mode": "synthetic adapter through installed producer/orchestrator, public installed MCP Run/Read; no model inference",
        "python": sys.executable,
        "loaded_from": mediasense.__file__,
        "adapter_calls": adapter.calls,
        "reports": reports,
        "source_sha256": before,
    }
    (root / "report.json").write_text(json.dumps(value, indent=2))
    print(
        json.dumps(
            {
                "status": "passed",
                "adapter_calls": adapter.calls,
                "public_runs": 2,
                "output": str(root),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prior", type=Path)
    anyio.run(exercise, parser.parse_args())
