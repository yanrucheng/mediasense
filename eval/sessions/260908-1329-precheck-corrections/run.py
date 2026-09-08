"""Local MCP replay; no remote authority, no Plan judge, no Apply effects.

Run after the registered fixture verifier. Output must be outside the fixture.
The full mode preserves manifest-media paths, excluding all historical outputs.
The controlled mode makes pixel derivatives of three inputs with repeated images
and synthetic capture times, to test content selection without hidden labels.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
REVISION = "503e16b560aff94c1922f13a86a7693d36957a4f"
spec = importlib.util.spec_from_file_location(
    "prepare_input", ROOT / "eval/shared/prepare_input.py"
)
preparer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preparer)


def metrics(workspace, run_ref):
    database = workspace / "precheck/work.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        public = dict(
            db.execute(
                "SELECT * FROM precheck_runs WHERE run_ref=?", (run_ref,)
            ).fetchone()
        )
        run_id = public["accounting_run_id"]
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT w.* FROM work_records w JOIN run_work_records r USING(work_id) WHERE r.run_id=?",
                (run_id,),
            )
        ]
        attempts = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM work_attempts WHERE run_id=?", (run_id,)
            )
        ]
        source_count = db.execute(
            "SELECT COUNT(*) FROM run_items WHERE run_id=?", (run_id,)
        ).fetchone()[0]
    groups = []
    for row in rows:
        if (
            row["capability"] == "adaptive-compression-group"
            and row["status"] == "succeeded"
        ):
            group = json.loads(row["output_json"])["group"]
            group["members"] = [
                json.loads(dep["key"])[1]
                for dep in json.loads(row["descriptor_json"])["dependencies"]
                if dep["kind"] == "source_revision"
            ]
            groups.append(group)
    embedding = [row for row in rows if row["capability"] == "image-embedding"]
    executed = {row["work_id"] for row in attempts}
    journal = workspace / "geo/journal.sqlite3"
    with sqlite3.connect(journal.as_uri() + "?mode=ro", uri=True) as db:
        entries = db.execute("SELECT result_json FROM geo_operation_journal").fetchall()
    # This offline experiment must not admit any external request. Do not infer
    # zero calls merely from remote_models=false or an absent model profile.
    assert not entries, "Unexpected Geo effect admission in local-only evaluation"
    return {
        "run_ref": run_ref,
        "state": public["state"],
        "run_elapsed_seconds": round(
            (
                datetime.fromisoformat(public["updated_at"])
                - datetime.fromisoformat(public["created_at"])
            ).total_seconds(),
            3,
        ),
        "sources": source_count,
        "work_by_capability_status": dict(
            Counter(row["capability"] + ":" + row["status"] for row in rows)
        ),
        "embedding_executed": sum(row["work_id"] in executed for row in embedding),
        "embedding_reused": sum(
            row["status"] == "succeeded" and row["work_id"] not in executed
            for row in embedding
        ),
        "compression_entries": len(groups),
        "represented_sources": len(
            {path for group in groups for path in group["members"]}
        ),
        "representative_methods": dict(
            Counter(g["basis"]["representative_method"] for g in groups)
        ),
        "representative_comparisons": sum(
            g["basis"]["representative_comparison_count"] for g in groups
        ),
        "outlier_paths": sum(len(g["outlier_paths"]) for g in groups),
        "group_members": [g["members"] for g in groups],
        "remote_provider_requests": len(entries),
        "plan": {
            "different_media_seen": 0,
            "derived_images_seen": 0,
            "collage_attachments": 0,
            "repeat_views": 0,
            "model_requests": 0,
            "tokens": 0,
            "cache_tokens": 0,
            "end_to_end_cost": "not_measured",
            "independent_blind_judgment": False,
        },
    }


def verified_result_reference(workspace: Path, metric: dict) -> str | None:
    """Recover only the exact published reference, without changing execution."""
    database = workspace / "precheck/work.sqlite3"
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        public = db.execute(
            "SELECT state,published_result_json FROM precheck_runs WHERE run_ref=?",
            (metric["run_ref"],),
        ).fetchone()
        if public is None or public["state"] != metric["state"]:
            raise ValueError("Metric is not bound to the retained Run state")
        if public["state"] != "completed":
            if public["published_result_json"] is not None:
                raise ValueError(
                    "Non-completed Run unexpectedly has a published Result"
                )
            return None
        published = json.loads(public["published_result_json"])
        ref = published["result_ref"]
        sealed = db.execute(
            "SELECT * FROM sealed_results WHERE result_ref=?", (ref,)
        ).fetchone()
        if sealed is None or sealed["digest_algorithm"] != "sha256":
            raise ValueError("Published Result is not registered with a SHA-256 seal")
    path = (database.parent / sealed["relative_path"]).resolve()
    if not path.is_relative_to(database.parent.resolve()):
        raise ValueError("Sealed Result path escapes the retained workspace")
    raw = path.read_bytes()
    if (
        len(raw) != sealed["size_bytes"]
        or hashlib.sha256(raw).hexdigest() != sealed["digest"]
    ):
        raise ValueError("Published Result integrity check failed")
    if json.loads(raw)["result"]["ref"] != ref:
        raise ValueError("Published Result identity does not match its contents")
    return ref


def repair_metric_references(output: Path) -> dict[str, str | None]:
    """Repair this recipe's summaries only; keep Run, Result and timing intact."""
    repaired = {}
    for path in sorted(output.glob("*.json")):
        if path.is_symlink():
            raise ValueError("Metric files must not be symlinks")
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or "run_ref" not in value:
            continue
        ref = verified_result_reference(output / "workspace", value)
        if value.get("public_result") not in (None, ref):
            raise ValueError("Metric already names a different Result")
        value["public_result"] = ref
        value["result_reference_basis"] = (
            "retained Run publication + verified sealed SHA-256"
        )
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2))
        repaired[path.name] = ref
    return repaired


async def replay(output, label, enabled):
    config = output / "config"
    config.mkdir(exist_ok=True)
    text = '[providers]\namap_api_key_env="MEDIASENSE_EVAL_NO_AMAP"\ngoogle_maps_api_key_env="MEDIASENSE_EVAL_NO_GOOGLE"\n'
    if enabled:
        text += (
            '[embedding]\nmodel_id="OFA-Sys/chinese-clip-vit-huge-patch14"\n'
            f'revision="{REVISION}"\ndimensions=1024\ndevice="cpu"\nbatch_size=4\n'
        )
    (config / "config.toml").write_text(text)
    env = {
        **os.environ,
        "MEDIASENSE_CONFIG_HOME": str(config),
        "MEDIASENSE_DATA_HOME": str(output / "data"),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "OMP_NUM_THREADS": "4",
    }
    env.pop("MEDIASENSE_EVAL_NO_AMAP", None)
    env.pop("MEDIASENSE_EVAL_NO_GOOGLE", None)
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "mediasense", "mcp"], cwd=str(ROOT), env=env
    )
    started_at = time.monotonic()
    workspace = output / "workspace"
    with (output / (label + "-host.log")).open("w") as errlog:
        async with (
            stdio_client(parameters, errlog=errlog) as (incoming, outgoing),
            ClientSession(incoming, outgoing) as session,
        ):
            await session.initialize()

            async def call(tool, request):
                response = await session.call_tool(tool, request)
                if response.is_error:
                    raise RuntimeError(response.structured_content)
                return response.structured_content

            opened = await call(
                "mediasense.dataset.open",
                {"source_root": str(output / "source"), "workspace": str(workspace)},
            )
            dataset = opened["dataset_ref"]
            started = await call(
                "mediasense.precheck.run",
                {
                    "action": "start",
                    "dataset_ref": dataset,
                    "request_id": "request:" + label,
                },
            )
            ref = started["run_ref"]
            while True:
                status = await call(
                    "mediasense.precheck.run",
                    {"action": "status", "dataset_ref": dataset, "run_ref": ref},
                )
                state = status["state"]
                if (
                    state == "paused"
                    and status.get("confirmation", {}).get("kind") == "source_scope"
                ):
                    await call(
                        "mediasense.precheck.run",
                        {
                            "action": "resume",
                            "dataset_ref": dataset,
                            "run_ref": ref,
                            "decision": {
                                "kind": "source_scope",
                                "inventory_fingerprint": status["confirmation"][
                                    "inventory_fingerprint"
                                ],
                                "default_disposition": "include",
                                "exceptions": [],
                            },
                        },
                    )
                elif state != "running":
                    break
                if time.monotonic() - started_at > 3600:
                    await call(
                        "mediasense.precheck.run",
                        {"action": "cancel", "dataset_ref": dataset, "run_ref": ref},
                    )
                    raise TimeoutError("Local replay exceeded its one-hour bound")
                await anyio.sleep(1)
            result = metrics(workspace, ref)
            result["elapsed_seconds"] = round(time.monotonic() - started_at, 3)
            result["public_reason"] = status.get("reason")
            result["configuration"] = opened["configuration"]["local_embedding"]
            if state == "completed":
                result["public_result"] = status["result"]["ref"]
            (output / (label + ".json")).write_text(
                json.dumps(result, ensure_ascii=False, indent=2)
            )
            print(
                label,
                {
                    k: result[k]
                    for k in [
                        "state",
                        "elapsed_seconds",
                        "embedding_executed",
                        "embedding_reused",
                        "compression_entries",
                    ]
                },
                flush=True,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--full", action="store_true")
    parser.add_argument(
        "--repair-result-refs",
        action="store_true",
        help="Verify and repair stored metric references only; no execution or source reads",
    )
    parser.add_argument(
        "--run-prefix",
        default="",
        help="New labels/idempotency keys for a subsequent implementation revision",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse this recipe's existing staged source and idempotency keys",
    )
    args = parser.parse_args()
    if args.repair_result_refs:
        print(json.dumps(repair_metric_references(args.output.resolve()), indent=2))
        return
    if args.fixture is None:
        parser.error("--fixture is required for execution")
    fixture = args.fixture.resolve()
    output = args.output.resolve()
    if args.resume:
        if (
            output.is_relative_to(fixture)
            or not (output / "operator-manifest.json").is_file()
        ):
            parser.error("Resume requires an existing experiment outside the fixture")
        for label, enabled in (
            ("without-embedding", False),
            ("with-embedding", True),
            ("embedding-reuse", True),
        ):
            anyio.run(replay, output, args.run_prefix + label, enabled)
        return
    if output.is_relative_to(fixture) or output.exists():
        parser.error("Output must be new and outside the fixture")
    output.mkdir(parents=True)
    manifest = [
        json.loads(line)
        for line in (fixture / "manifests/media-manifest.jsonl")
        .read_text()
        .splitlines()
    ]
    allowed = {row["path"]: row["derived_sha256"] for row in manifest}
    original = fixture / "test-260831/260501-HK美食之旅"
    if args.full:
        staged = preparer.prepare(
            original, allowed, output / "source", path_policy="preserve"
        )
    else:
        photos = [row for row in manifest if row["media_type"] == "image"]
        chosen = [photos[0], photos[len(photos) // 2], photos[-1]]
        (output / "source").mkdir()
        staged = {"path_policy": "opaque", "controlled_derivatives": []}
        for scene, row in enumerate(chosen):
            path = original / row["path"]
            assert (
                hashlib.sha256(path.read_bytes()).hexdigest() == row["derived_sha256"]
            )
            for copy in range(3):
                index = scene * 3 + copy
                with Image.open(path) as image:
                    image = image.convert("RGB")
                    image.thumbnail((640, 640))
                    exif = Image.Exif()
                    exif[36867] = (
                        datetime(2026, 1, 1, 12) + timedelta(minutes=index * 2)
                    ).strftime("%Y:%m:%d %H:%M:%S")
                    image.save(output / f"source/item-{index:03d}.jpg", exif=exif)
                staged["controlled_derivatives"].append(
                    {"source": row["path"], "item": index, "scene": scene}
                )
    (output / "operator-manifest.json").write_text(
        json.dumps(staged, ensure_ascii=False, indent=2)
    )
    for label, enabled in (
        ("without-embedding", False),
        ("with-embedding", True),
        ("embedding-reuse", True),
    ):
        anyio.run(replay, output, args.run_prefix + label, enabled)


if __name__ == "__main__":
    main()
