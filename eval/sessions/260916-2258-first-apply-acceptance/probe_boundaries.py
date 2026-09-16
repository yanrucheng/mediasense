"""Reproduce two acceptance gaps without executing any Apply move.

The MCP probe stops at a recording runtime. The drift probe creates one tiny
real PreCheck Result and prepares an Apply only within a disposable directory.
It never authorizes, executes, rewinds, or references the user's actual Run.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import anyio
from mcp import types
from PIL import Image

from mediasense.apply import ApplyRunStore
from mediasense.apply.preparation import SourceSetExpansion
from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    PrecheckReadTool,
    ResultStore,
)
from mediasense.precheck._fingerprint import hash_regular_file
from mediasense.precheck.read import bind_precheck_read
from mediasense.runtime.mcp_host import create_mcp_server
from mediasense.runtime.resources import schema_path


def identity(value):
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(data).hexdigest()


class RecordingRuntime:
    def __init__(self):
        self.authority = None

    def call_tool(self, name, *, dataset_ref, request, authority=None):
        assert name == "mediasense.apply.run"
        assert dataset_ref == "dataset:synthetic-audit"
        self.authority = authority
        return {"outcome": "observed_at_recording_boundary"}


async def authority_probe():
    runtime = RecordingRuntime()
    server = create_mcp_server(runtime)
    entry = server.get_request_handler("tools/call")
    claimed = {
        "principal_ref": "human:synthetic-audit",
        "confirmed_content_identity": "sha256:" + "a" * 64,
        "confirmed_at": "2026-09-16T00:00:00Z",
    }
    response = await entry.handler(
        None,
        types.CallToolRequestParams(
            name="mediasense.apply.run",
            arguments={
                "dataset_ref": "dataset:synthetic-audit",
                "request": {
                    "action": "execute",
                    "run_ref": "apply-run:synthetic-audit",
                    "prepared_revision": "prepared-revision:synthetic-audit",
                    "prepared_content_identity": claimed["confirmed_content_identity"],
                    "request_id": "request:synthetic-audit",
                },
                "authority": claimed,
            },
        ),
    )
    return {
        "caller_authored_authority_forwarded": runtime.authority == claimed,
        "context": "None; no Human elicitation or authenticated confirmation supplied",
        "host_result": response.structured_content,
        "execution_boundary": "recording stub; no real Run or filesystem effects",
    }


def drift_probe():
    with TemporaryDirectory(
        prefix="mediasense-apply-audit-", dir="/private/tmp"
    ) as temporary:
        root = Path(temporary)
        source, destination = root / "source", root / "destination"
        source.mkdir()
        destination.mkdir()
        original = source / "original.jpg"
        Image.new("RGB", (80, 40), "blue").save(original)
        original_digest = "sha256:" + hashlib.sha256(original.read_bytes()).hexdigest()
        database = root / "precheck/work.sqlite3"
        accounting = AccountingStore(database)
        accounting.register_dataset("synthetic-apply-audit")
        run_id = accounting.start_or_resume_run("synthetic-apply-audit", source)
        accounting.process_run(run_id)
        rendition = ImageRenditionProducer(database).produce(
            run_id, Path("original.jpg")
        )
        results = ResultStore(database)
        result = results.seal(results.build_minimal(run_id, [rendition.work.work_id]))
        reader = bind_precheck_read(
            PrecheckReadTool(database), "dataset:synthetic-apply-audit"
        )
        members = reader.read(
            {
                "action": "resolve",
                "result_ref": result.result_ref,
                "source_set": {
                    "kind": "precheck_relation",
                    "origin": result.result_ref,
                    "relation": "accounts_for",
                    "direction": "outbound",
                },
            }
        )["members"]
        selected = next(item for item in members if item["scope"] == "source_media")
        ref = selected["source_item_ref"]
        source_set = {"kind": "explicit", "source_item_refs": [ref]}
        content = {
            "contract": "mediasense.frozen-plan",
            "plan_ref": "frozen-plan:synthetic-apply-audit",
            "result_ref": result.result_ref,
            "scope": source_set,
            "logical_root": "Media",
            "groups": [
                {
                    "relative_path": ["ConfirmedBlueImage"],
                    "members": source_set,
                    "source_naming": {"default": "preserve_source_basename"},
                }
            ],
            "other_outcomes": [],
        }
        content_identity = identity(content)
        plan = {
            "sealed_content": content,
            "seal": {
                "encoding_profile": "mediasense-json-strings-sha256-v1",
                "content_identity": content_identity,
                "final_confirmation": {
                    "confirmed_content_identity": content_identity,
                    "confirmed_by": "human:synthetic-test-fixture",
                    "confirmed_at": "2026-09-16T00:00:00Z",
                },
            },
        }

        # An ordinary visible change after the Plan's exact Result was sealed:
        # replace blue image content with a red image of different dimensions.
        Image.new("RGB", (160, 120), "red").save(original)
        changed_digest = "sha256:" + hashlib.sha256(original.read_bytes()).hexdigest()
        new_candidate = "sha256:" + hash_regular_file(original, original.stat())
        old_proof = selected["source_content_verification"]
        assert original_digest != changed_digest
        assert old_proof["value"] != new_candidate
        apply = ApplyRunStore.initialize(
            root / "apply/work.sqlite3", schema_path("frozen-plan.schema.json")
        )
        prepared = apply.prepare_forward(
            request_id="request:synthetic-source-drift",
            frozen_plan=plan,
            source_roots={selected["locator"]["source_root_ref"]: source},
            destination_parent=destination,
            resolve_source_set=lambda _result, expression: SourceSetExpansion(
                expression["source_item_refs"], complete=True
            ),
            precheck_read=reader,
        )
        status = apply.status(prepared.run_ref)
        item = apply.iter_items(prepared.run_ref, limit=1)[0]
        no_effect = original.exists() and not list(destination.iterdir())
        return {
            "precheck_profile": old_proof["profile"],
            "precheck_size": old_proof["size_bytes"],
            "current_size": original.stat().st_size,
            "ordinary_fingerprint_changed": old_proof["value"] != new_candidate,
            "full_content_changed": original_digest != changed_digest,
            "prepare_state": prepared.state,
            "blockers": status["summary"]["blockers"],
            "prepared_proof_equals_changed_bytes": item["expected_verification"]
            == changed_digest,
            "prepared_producer": item["verification_producer"],
            "zero_apply_media_effects": no_effect,
            "temporary_fixture_removed_on_return": True,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "authority": anyio.run(authority_probe),
        "source_drift": drift_probe(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
