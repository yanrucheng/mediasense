"""Bounded real-media delivery through an installed MCP executable; no provider calls.

Run with an isolated installed Python and --host pointing to that install's CLI.
The optional model mode uses only existing pinned local weights.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
import subprocess
import tempfile

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image, ImageDraw

from mediasense.runtime.resources import contract_validator, resource_root


def observe(items, name):
    return [item for item in items if item["name"] == name]


def check_public(value):
    if isinstance(value, dict):
        assert (
            not {
                "work_id",
                "input_work_id",
                "frame_work_ids",
                "group_ref",
                "cache_key",
                "row_id",
            }
            & value.keys()
        ), value
        for child in value.values():
            check_public(child)
    elif isinstance(value, list):
        for child in value:
            check_public(child)


def make_media(source):
    source.mkdir()
    exif = Image.Exif()
    exif[271] = "MediaSense synthetic camera"
    exif[272] = "Controlled fixture"
    exif[274] = 6
    exif[36867] = "2026:09:09 10:00:00"
    exif[33434] = 0.04
    exif[33437] = 2.8
    exif[34855] = 400
    exif[37386] = 50.0
    exif[41989] = 75
    exif[42036] = "Synthetic 50mm lens"
    exif[42033] = "CAMERA-TEST-001"
    exif[42037] = "LENS-TEST-001"
    image = Image.new("RGB", (1200, 800), "navy")
    draw = ImageDraw.Draw(image)
    draw.rectangle((100, 100, 500, 600), fill="yellow")
    draw.text((150, 150), "MediaSense synthetic evidence", fill="black")
    image.save(source / "still.jpg", exif=exif)
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=4",
            "-t",
            "1",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            "-threads",
            "1",
            str(source / "clip.mp4"),
        ],
        check=True,
    )
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }


async def exercise(host, root, revision):
    source = root / "source"
    before = make_media(source)
    workspace = root / "dataset"
    workspace.mkdir()
    environment = {
        **os.environ,
        "MEDIASENSE_CONFIG_HOME": str(root / "user-config"),
        "MEDIASENSE_DATA_HOME": str(root / "data"),
        "AMAP_API_KEY": "",
        "GOOGLE_MAPS_API_KEY": "",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }
    environment.pop("PYTHONPATH", None)
    initialized = subprocess.run(
        [
            str(host),
            "dataset",
            "open",
            str(source),
            "--workspace",
            str(workspace),
            "--json",
        ],
        env=environment,
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(initialized.stdout).get("dataset_ref"), initialized.stdout
    if revision:
        (workspace / "config.toml").write_text(
            '[sensitivity]\nenabled=true\ndevice="cpu"\nnsfw_revision="'
            + revision
            + '"\n'
        )
    params = StdioServerParameters(
        command=str(host), args=["mcp"], cwd=str(root), env=environment
    )
    deliveries = []
    async with (
        stdio_client(params) as (incoming, outgoing),
        ClientSession(incoming, outgoing) as session,
    ):
        await session.initialize()
        opened = await session.call_tool(
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )
        assert not opened.is_error, opened
        assert opened.content == []
        assert opened.structured_content.get("dataset_ref"), opened
        dataset = opened.structured_content["dataset_ref"]

        async def call(tool, action, **kwargs):
            request = {"action": action, "dataset_ref": dataset, **kwargs}
            response = await session.call_tool("mediasense.precheck." + tool, request)
            assert response.content == [], response
            assert not response.is_error, response
            value = response.structured_content
            contract_validator("mediasense.precheck." + tool, action).validate(value)
            check_public(value)
            assert "error" not in value, value
            return value

        async def wait(ref):
            with anyio.fail_after(180):
                while True:
                    status = await call("run", "status", run_ref=ref)
                    if status["state"] != "running":
                        return status
                    await anyio.sleep(0.1)

        async def run(index, prior=None):
            start = await call(
                "run",
                "start",
                request_id=f"request:installed-delivery-{index}",
                **({"prior_result_ref": prior} if prior else {}),
            )
            state = await wait(start["run_ref"])
            if (
                state["state"] == "paused"
                and state.get("reason", {}).get("code") == "scope_confirmation_required"
            ):
                await call(
                    "run",
                    "resume",
                    run_ref=start["run_ref"],
                    decision={
                        "kind": "source_scope",
                        "inventory_fingerprint": state["confirmation"][
                            "inventory_fingerprint"
                        ],
                        "default_disposition": "include",
                        "exceptions": [],
                    },
                )
                state = await wait(start["run_ref"])
            assert state["state"] == "completed", state
            return state["result"]["ref"]

        result = await run(1)
        page = await call(
            "read", "review", result_ref=result, include=["execution_boundary"]
        )
        assert page["page"]["next_cursor"] is None
        assert page["execution_boundary"]["current_provider_requests"] == 0
        assert page["execution_boundary"]["historical_provider_requests"] == 0
        assert page["execution_boundary"]["billable_calls"] == 0
        assert page["accounting"]["total"] == 2
        deliveries.append(page)
        refs = set()
        for item in page["items"]:
            assert "error" not in item
            refs.add(item["evidence_ref"])
            expanded = await call(
                "read",
                "expand",
                result_ref=result,
                evidence_refs=[item["evidence_ref"]],
                include=["prepared_targets"],
            )
            refs.update(
                target["target"]["ref"]
                for target in expanded["items"][0]["included"]["prepared_targets"]
                if target["target"]["kind"] == "evidence"
            )
        selected = await call(
            "read", "review", result_ref=result, evidence_refs=sorted(refs)
        )
        assert selected["page"]["total"] == len(refs)
        deliveries.append(selected)
        all_items = selected["items"]
        observed_sources = {
            source["locator"]["value"]: source
            for item in all_items
            for source in item["source_items"]
        }
        still = observed_sources["still.jpg"]
        video = observed_sources["clip.mp4"]
        metadata = {o["name"]: o for o in still["observations"]}
        for name in (
            "camera_make",
            "camera_model",
            "camera_serial_number",
            "lens_model",
            "lens_serial_number",
            "focal_length_mm",
            "focal_length_35mm_equivalent_mm",
            "aperture_f_number",
            "exposure_time_seconds",
            "iso",
            "source_pixel_dimensions",
            "orientation",
            "media_type",
            "source_file_format",
        ):
            assert metadata[name]["status"] == "available", (name, metadata[name])
            assert metadata[name].get("provenance"), name
        assert metadata["source_pixel_dimensions"]["value"] == {
            "width": 1200,
            "height": 800,
        }
        assert metadata["exposure_time_seconds"]["value"] == 0.04
        assert metadata["focal_length_mm"]["value"] == 50
        assert metadata["focal_length_35mm_equivalent_mm"]["value"] == 75
        profiles = {
            o["value"]["profile"]["name"]
            for item in all_items
            for o in item["observations"]
            if o["name"] == "pixel_dimensions"
        }
        assert {"ordinary", "high_resolution"} <= profiles, profiles
        assert (
            observe(video["observations"], "video_probe")[0]["value"][
                "duration_seconds"
            ]
            == 1
        )
        sheets = [
            o
            for item in all_items
            for o in item["observations"]
            if o["name"] == "video_contact_sheet"
        ]
        assert sheets and sheets[0]["value"]["frames"]
        assert {frame["evidence_ref"] for frame in sheets[0]["value"]["frames"]} <= refs
        for item in all_items:
            assert "error" not in item, item
            with Image.open(item["access"]["locator"]["value"]) as image:
                image.load()
        detections = []
        for source_item in observed_sources.values():
            values = observe(source_item["observations"], "content_sensitivity")
            if revision:
                assert len(values) >= 2
                assert all(o["status"] == "available" for o in values), values
                assert all(
                    o["provenance"]["input_evidence_ref"] in refs for o in values
                )
                for observation in values:
                    for label in observation["value"]["labels"]:
                        assert label["sensitive"] == (
                            label["score"] >= label["threshold"]
                        )
                        assert label["mild_sensitive"] == (
                            label["score"] >= label["mild_threshold"]
                        )
                detections.extend(values)
            else:
                assert values[0]["status"] == "not_checked"
                assert values[0]["basis"]["code"] == "capability_disabled"

        # Independent evaluation audit, not a consumer data path: count actual
        # producer attempts before/after the public successor Run.
        def local_attempts():
            with sqlite3.connect(
                f"file:{workspace / 'precheck/work.sqlite3'}?mode=ro", uri=True
            ) as connection:
                return connection.execute(
                    "SELECT capability, work_id, attempt_count, output_digest FROM work_records WHERE capability IN ('source-metadata', 'image-rendition', 'video-probe', 'video-frame', 'video-contact-sheet', 'content-sensitivity', 'image-embedding') ORDER BY capability, work_id"
                ).fetchall()

        attempts_before = local_attempts()
        second = await run(2, result)
        assert local_attempts() == attempts_before, (
            "Successor unexpectedly repeated completed producer work"
        )

        second_page = await call("read", "review", result_ref=second)
        deliveries.append(second_page)
        assert {
            item["access"]["locator"]["value"] for item in second_page["items"]
        } == {item["access"]["locator"]["value"] for item in page["items"]}
        # Installed Plan consumer must accept the actual new Read shape.
        plan = await session.call_tool(
            "mediasense.plan.work",
            {
                "dataset_ref": dataset,
                "request": {
                    "action": "create",
                    "result_ref": second,
                    "request_id": "request:installed-plan",
                },
            },
        )
        assert not plan.is_error and plan.structured_content["outcome"] == "ok", plan
        assert plan.content == []
        # Local Artifact damage must retain the failed position and advance.
        victim = page["items"][0]
        path = Path(victim["access"]["locator"]["value"])
        saved = path.read_bytes()
        path.chmod(0o600)
        path.write_bytes(b"controlled damage")
        fault = await call("read", "review", result_ref=result, page={"limit": 1})
        assert fault["items"][0]["error"]["code"] == "evidence_unavailable"
        assert fault["page"]["next_cursor"]
        continued = await call(
            "read",
            "review",
            result_ref=result,
            page={"limit": 1, "cursor": fault["page"]["next_cursor"]},
        )
        assert "error" not in continued["items"][0]
        path.write_bytes(saved)
        path.chmod(0o444)
        deliveries.extend([fault, continued])
    assert before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    (root / "delivery.json").write_text(
        json.dumps(deliveries, ensure_ascii=False, indent=2)
    )
    summary = {
        "host": str(host),
        "installed_resources": str(resource_root()),
        "models_enabled": bool(revision),
        "source_items": 2,
        "prepared_evidence": len(refs),
        "detections": len(detections),
        "detectors": sorted({o["value"]["detector_identity"] for o in detections}),
        "provider_requests": 0,
        "source_unchanged": True,
        "results": [result, second],
        "artifact_reuse": True,
        "producer_attempts_unchanged": True,
        "plan_create": "ok",
        "fault_continuation": "ok",
        "delivery_path": str(root / "delivery.json"),
    }
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--nsfw-revision")
    args = parser.parse_args()
    root = args.output or Path(tempfile.mkdtemp(prefix="mediasense-delivery-"))
    root.mkdir(parents=True, exist_ok=True)
    anyio.run(exercise, args.host.resolve(), root.resolve(), args.nsfw_revision)


if __name__ == "__main__":
    main()
