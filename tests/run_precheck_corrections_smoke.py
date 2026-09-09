"""Exercise the three reacceptance fixes through an isolated installed MCP Host.

Use the isolated install's Python, with pytest installed for the shared fixture helpers.
Only generated media and synthetic retained records are used; no model/provider runs.
"""

import argparse
import hashlib
import json
import os
from dataclasses import replace
from pathlib import Path
import subprocess

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

import mediasense
from mediasense.dataset_reference import dataset_id_from_ref
from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    MetadataProducer,
    PrecheckReadTool,
    ResultStore,
)
from mediasense.runtime.resources import contract_validator
from test_precheck_delivery_regressions import (
    encoded_size,
    legacy_observation,
    middle_page_case,
    seed_legacy_result,
)


async def exercise(host, root):
    package = Path(mediasense.__file__).resolve()
    assert package.is_relative_to(host.resolve().parent.parent), package
    source, workspace = root / "source", root / "dataset"
    source.mkdir(parents=True)
    for i in range(3):
        Image.new("RGB", (20, 10), (i * 60, 50, 90)).save(source / f"{i}.jpg")
    before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
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
    params = StdioServerParameters(
        command=str(host), args=["mcp"], cwd=str(root), env=env
    )
    payloads = []
    async with (
        stdio_client(params) as (incoming, outgoing),
        ClientSession(incoming, outgoing) as session,
    ):
        await session.initialize()
        opened = await session.call_tool(
            "mediasense.dataset.open",
            {"source_root": str(source), "workspace": str(workspace)},
        )
        assert not opened.is_error and opened.content == [], opened
        dataset_ref = opened.structured_content["dataset_ref"]
        database = workspace / "precheck/work.sqlite3"
        accounting = AccountingStore(database)
        run = accounting.start_or_resume_run(dataset_id_from_ref(dataset_ref), source)
        accounting.process_run(run)
        renditions = [
            ImageRenditionProducer(database).produce(run, Path(f"{i}.jpg"))
            for i in range(3)
        ]
        store = ResultStore(database)
        draft = store.build_minimal(run, [o.work.work_id for o in renditions])

        async def read(sealed, **options):
            request = {
                "action": "review",
                "dataset_ref": dataset_ref,
                "result_ref": sealed.result_ref,
                **options,
            }
            response = await session.call_tool("mediasense.precheck.read", request)
            assert not response.is_error and response.content == [], response
            value = response.structured_content
            contract_validator("mediasense.precheck.read", request["action"]).validate(
                value
            )
            assert "error" not in value, value
            payloads.append(value)
            return value

        def exiftool(command):
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    [
                        {
                            "SourceFile": path,
                            "QuickTime:Encoder": "Lavf-controlled",
                            "EXIF:FocalLength": -7,
                            "File:MIMEType": "image/jpeg",
                        }
                        for path in command[command.index("--") + 1 :]
                    ]
                ),
                "",
            )

        metadata = MetadataProducer(
            database, command_runner=exiftool, exiftool_version="controlled"
        ).produce(run, Path("0.jpg"))
        metadata_result = store.seal(
            store.build_minimal(
                run,
                [o.work.work_id for o in renditions],
                metadata_work_ids=[metadata.work.work_id],
            )
        )
        response = await read(metadata_result)
        subject = next(
            source
            for item in response["items"]
            for source in item["source_items"]
            if source["locator"]["value"] == "0.jpg"
        )
        fields = {o["name"]: o for o in subject["observations"]}
        assert (
            fields["camera_model"]["basis"]["candidates"][0]["raw_value"]
            == "Lavf-controlled"
        )
        assert (
            fields["camera_model"]["basis"]["candidates"][0]["rejection"]
            == "encoder_is_not_camera_identity"
        )
        assert fields["focal_length_mm"]["basis"]["candidates"][0]["raw_value"] == -7

        anchor = draft.evidence[0]

        def padded(text):
            return replace(
                draft,
                evidence=(
                    replace(
                        anchor,
                        observations=(
                            *anchor.observations,
                            {
                                "name": "retained_text",
                                "status": "available",
                                "value": text,
                            },
                        ),
                    ),
                    *draft.evidence[1:],
                ),
            )

        small = store.seal(padded(""))
        options = {"evidence_refs": [anchor.ref], "page": {"limit": 1}}
        baseline = PrecheckReadTool(database).read(
            {
                "action": "review",
                "dataset_ref": dataset_ref,
                "result_ref": small.result_ref,
                **options,
            }
        )
        sizes = []
        for size in (524278, 524288, 524289):
            bounded = store.seal(padded("x" * (size - encoded_size(baseline))))
            value = await read(bounded, **options)
            if size <= 524288:
                assert "error" not in value["items"][0]
                assert encoded_size(value) == size
                assert value["page"] == {"total": 1, "next_cursor": None}
                sizes.append(encoded_size(value))
            else:
                assert value["items"][0]["error"]["code"] == "response_item_too_large"

        middle_checks = []
        for single_size in (524261, 524278):
            bounded, refs, _ = middle_page_case(
                store, draft, PrecheckReadTool(database), dataset_ref, single_size
            )
            page, pages, cursors = {"limit": 2}, [], set()
            while True:
                value = await read(bounded, page=page)
                assert value["page"]["total"] == 3
                assert encoded_size(value) <= 524288
                pages.append(value)
                cursor = value["page"]["next_cursor"]
                if cursor is None:
                    break
                assert cursor not in cursors
                cursors.add(cursor)
                page = {"limit": 2, "cursor": cursor}
            items = [item for value in pages for item in value["items"]]
            assert [item["evidence_ref"] for item in pages[0]["items"]] == refs[:1]
            assert pages[0]["page"]["stop_reason"] == "byte_limit"
            assert [item["evidence_ref"] for item in items] == refs
            assert "error" not in items[0] and "error" not in items[2]
            if single_size == 524261:
                assert "error" not in items[1]
                assert encoded_size(pages[1]) == 524288
            else:
                assert items[1]["error"]["code"] == "response_item_too_large"
                assert len(pages) == 2
            middle_checks.append(
                {
                    "limit": 2,
                    "single_page_without_stop_reason": single_size,
                    "single_page_with_stop_reason": single_size + 27,
                    "outcomes": [
                        item.get("error", {}).get("code", "delivered") for item in items
                    ],
                    "page_bytes": [encoded_size(value) for value in pages],
                }
            )

        legacy, original_bytes = seed_legacy_result(
            database,
            store,
            draft,
            [
                legacy_observation("detector-a", "unmapped-1", 0.1),
                legacy_observation("detector-a", "unmapped-2", 0.2, status="failed"),
                legacy_observation("detector-b", "unmapped-3", 0.3),
                legacy_observation("detector-a", renditions[0].work.work_id, 0.4),
            ],
        )
        value = await read(legacy)
        subject = next(
            source
            for item in value["items"]
            for source in item["source_items"]
            if source["locator"]["value"] == "0.jpg"
        )
        detections = [
            o for o in subject["observations"] if o["name"] == "content_sensitivity"
        ]
        gaps = [o for o in detections if o["status"] == "not_checked"]
        assert (
            len(gaps) == 2
            and sum(len(o["basis"]["retained_observations"]) for o in gaps) == 3
        )
        assert len([o for o in detections if o["status"] == "available"]) == 1
        assert legacy.path.read_bytes() == original_bytes
        assert before == {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
        }
    (root / "responses.json").write_text(
        json.dumps(payloads, ensure_ascii=False, separators=(",", ":"))
    )
    summary = {
        "installed_package": str(package),
        "metadata_rejections": "preserved",
        "successful_page_bytes": sizes,
        "oversized_item": "localized",
        "middle_item_continuation": middle_checks,
        "historical_gap_records": 3,
        "historical_proven_inputs": 1,
        "legacy_bytes_unchanged": True,
        "source_bytes_unchanged": True,
        "model_runs": 0,
        "provider_calls": 0,
        "mcp_single_structured_payload": True,
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    anyio.run(exercise, args.host.resolve(), args.output.resolve())
