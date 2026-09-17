"""Isolated dense-file benchmark; one case per fresh interpreter.

Select the implementation with PYTHONPATH (src or a retained baseline/src).
The same fixture, Tool request and instrumentation are used for both builds.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import platform
import resource
import sqlite3
import sys
import tempfile
from time import perf_counter, process_time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))

from mediasense.apply import ApplyRunTool, ApplyConfirmationContext  # noqa: E402
import mediasense.apply.filesystem as fs  # noqa: E402
from test_apply_preparation import _FakePrecheckRead, _plan, _identity  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

CASES = {
    "large": (8, 128 * 1024 * 1024, 0),
    "small": (20000, 512, 0),
    "mixed": (10000, 256 * 1024, 9000),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=CASES, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--native", action="store_true")
    args = parser.parse_args()
    count, size, sidecars = CASES[args.case]
    metrics = {
        "case": args.case,
        "label": args.label,
        "items": count,
        "sidecars": sidecars,
        "platform": platform.platform(),
        "cache": "warm/uncontrolled; dense generated files, no cache flush",
        "media_read_bytes": 0,
        "media_write_bytes": 0,
        "max_item_read_bytes": 0,
        "commits": 0,
        "commit_seconds": 0,
        "intent_commits": 0,
        "result_commits": 0,
        "intent_commit_seconds": 0,
        "result_commit_seconds": 0,
        "directory_syncs": 0,
        "directory_sync_seconds": 0,
    }
    with tempfile.TemporaryDirectory(
        prefix="mediasense-apply-b-", dir="/private/tmp"
    ) as temp:
        home = Path(temp)
        source, destination = home / "source", home / "destination"
        source.mkdir()
        destination.mkdir()
        views, native_pairs = [], []
        total = 0
        for index in range(count):
            item_size = 512 if index >= count - sidecars else size
            suffix = ".xmp" if index >= count - sidecars else ".mp4"
            path = source / f"d{index // 100:05d}" / f"{index:06d}{suffix}"
            path.parent.mkdir(exist_ok=True)
            block = bytes([index % 251]) * min(item_size, 1024 * 1024)
            with path.open("wb") as handle:
                remaining = item_size
                while remaining:
                    chunk = block[:remaining]
                    handle.write(chunk)
                    remaining -= len(chunk)
            digest = hashlib.sha256(str(item_size).encode())
            if item_size <= 12288:
                digest.update(block[:item_size])
            else:
                for offset in (0, item_size // 2, item_size - 4096):
                    digest.update(offset.to_bytes(8, "big"))
                    digest.update(block[:4096])
            views.append(
                {
                    "kind": "source_item",
                    "ref": f"source-item:{index:06d}",
                    "locator": {
                        "kind": "source_root_relative_path",
                        "source_root_ref": "source-root:test",
                        "value": str(path.relative_to(source)),
                    },
                    "observations": [
                        {
                            "name": "source_content_verification",
                            "status": "available",
                            "value": {
                                "profile": "candidate-sha256-full-or-3x4k-v1",
                                "value": "sha256:" + digest.hexdigest(),
                                "size_bytes": item_size,
                                "observed_at": "2026-09-17T00:00:00Z",
                                "producer": "synthetic-v1",
                            },
                            "basis": "Deterministic dense fixture bytes before preparation.",
                        }
                    ],
                }
            )
            native_pairs.append((path, destination / "Media/Trip" / path.name))
            total += item_size
        metrics["source_bytes"] = total
        metrics["finite_read_upper_bound"] = sum(
            min(v["observations"][0]["value"]["size_bytes"], 12288) for v in views
        )
        plan = _plan()
        refs = [v["ref"] for v in views]
        plan["sealed_content"]["scope"] = {"kind": "explicit", "source_item_refs": refs}
        plan["sealed_content"]["groups"][0]["members"] = {
            "kind": "explicit",
            "source_item_refs": refs,
        }
        plan["sealed_content"]["groups"][0]["source_naming"].pop("overrides")
        plan["sealed_content"]["other_outcomes"] = []
        identity = _identity(plan["sealed_content"])
        plan["seal"]["content_identity"] = identity
        plan["seal"]["final_confirmation"]["confirmed_content_identity"] = identity

        class Reader(_FakePrecheckRead):
            def read(self, request):
                result = super().read(request)
                if request["action"] == "resolve" and "members" in result:
                    offset = int(request.get("page", {}).get("cursor", "0"))
                    limit = request.get("page", {}).get("limit", 1000)
                    result["members"] = result["members"][offset : offset + limit]
                    for member in result["members"]:
                        observation = self.views[member["source_item_ref"]][
                            "observations"
                        ][0]
                        member["source_content_verification"] = {
                            "status": "available",
                            **observation["value"],
                            "basis": observation["basis"],
                        }
                    result["page"]["next_cursor"] = (
                        str(offset + limit) if offset + limit < len(views) else None
                    )
                return result

        reader = Reader(views)
        tool = ApplyRunTool(
            home / "state",
            reader,
            run_schema_path=ROOT / "docs/spec/contract/apply/apply-run.tool.json",
            frozen_plan_schema_path=ROOT
            / "docs/spec/contract/frozen-plan/frozen-plan.schema.json",
            receipt_schema_path=ROOT
            / "docs/spec/contract/apply/apply-receipt.schema.json",
        )
        real_open, real_connect, real_sync = (
            Path.open,
            sqlite3.connect,
            fs._fsync_directory,
        )
        per_item = {}

        class ReadCounter:
            def __init__(self, handle, path):
                self.handle, self.path = handle, path

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self.handle.close()

            def __getattr__(self, name):
                return getattr(self.handle, name)

            def read(self, n=-1):
                result = self.handle.read(n)
                metrics["media_read_bytes"] += len(result)
                per_item[self.path.name] = per_item.get(self.path.name, 0) + len(result)
                return result

        def counted_open(path, *a, **kw):
            media = path.suffix in {".mp4", ".xmp"}
            mode = a[0] if a else kw.get("mode", "r")
            if media and any(c in mode for c in "wa+"):
                raise AssertionError("unexpected media content write")
            handle = real_open(path, *a, **kw)
            return ReadCounter(handle, path) if media else handle

        class Connection(sqlite3.Connection):
            commit_kind = None

            def execute(self, sql, *a, **kw):
                if "SET execution_status = 'intent'" in sql:
                    self.commit_kind = "intent"
                if "SET execution_status = 'completed_and_verified'" in sql:
                    self.commit_kind = "result"
                return super().execute(sql, *a, **kw)

            def commit(self):
                start = perf_counter()
                value = super().commit()
                elapsed = perf_counter() - start
                metrics["commits"] += 1
                metrics["commit_seconds"] += elapsed
                if self.commit_kind:
                    metrics[self.commit_kind + "_commits"] += 1
                    metrics[self.commit_kind + "_commit_seconds"] += elapsed
                self.commit_kind = None
                return value

        def sync(path):
            start = perf_counter()
            real_sync(path)
            metrics["directory_syncs"] += 1
            metrics["directory_sync_seconds"] += perf_counter() - start

        with ExitStack() as stack:
            stack.enter_context(patch.object(Path, "open", counted_open))
            stack.enter_context(
                patch.object(
                    sqlite3,
                    "connect",
                    lambda *a, **kw: real_connect(*a, factory=Connection, **kw),
                )
            )
            stack.enter_context(patch.object(fs, "_fsync_directory", sync))
            start, cpu = perf_counter(), process_time()
            if args.native:
                native_pairs[0][1].parent.mkdir(parents=True)
                for old, new in native_pairs:
                    fs.rename_exclusive(old, new)
                metrics["prepare_seconds"] = 0
                metrics["execute_seconds"] = perf_counter() - start
            else:
                prepared = tool.handle(
                    {
                        "action": "prepare",
                        "request_id": "request:benchmark-prepare",
                        "forward": {
                            "frozen_plan": plan,
                            "effect": "move_originals",
                            "current_source_roots": [
                                {
                                    "source_root_ref": "source-root:test",
                                    "current_root": str(source),
                                }
                            ],
                            "destination_parent": str(destination),
                        },
                    }
                )
                assert prepared["outcome"] == "ok", prepared
                status = tool.handle(
                    {"action": "status", "run_ref": prepared["run_ref"]}
                )
                assert status["state"] == "ready_for_authorization", status
                metrics["prepare_seconds"] = perf_counter() - start
                metrics["prepare_read_bytes"] = metrics["media_read_bytes"]
                context = ApplyConfirmationContext(
                    "human:isolated-benchmark",
                    status["prepared_content_identity"],
                    datetime.now(timezone.utc),
                )
                executed = tool.handle(
                    {
                        "action": "execute",
                        "request_id": "request:benchmark-execute",
                        "run_ref": status["run_ref"],
                        "prepared_revision": status["prepared_revision"],
                        "prepared_content_identity": status[
                            "prepared_content_identity"
                        ],
                    },
                    confirmation=context,
                )
                assert executed["outcome"] == "accepted", executed
                effect_start = perf_counter()
                tool.run_pending(status["run_ref"])
                final = tool.handle({"action": "status", "run_ref": status["run_ref"]})
                assert final["state"] == "closed", final
                metrics["execute_seconds"] = perf_counter() - effect_start
                metrics["execute_read_bytes"] = (
                    metrics["media_read_bytes"] - metrics["prepare_read_bytes"]
                )
                receipt = tool.receipt_store.read(
                    final["published_receipt"]["receipt_ref"]
                )
                assert receipt["sealed_content"]["completion"] == "complete"
                assert (
                    receipt["sealed_content"]["accounting"]["completed_and_verified"]
                    == count
                )
                metrics["receipt_verified"] = True
                assert metrics["intent_commits"] == metrics["result_commits"] == count
            metrics["total_seconds"] = perf_counter() - start
            metrics["cpu_seconds"] = process_time() - cpu
        assert all(not old.exists() and new.exists() for old, new in native_pairs)
        metrics["max_item_read_bytes"] = max(per_item.values(), default=0)
        metrics["peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        metrics["read_calls"] = len(reader.requests)
        metrics["sqlite_synchronous"] = (
            tool.run_store._connect().execute("PRAGMA synchronous").fetchone()[0]
        )
        metrics["code_file"] = fs.__file__
        metrics["filesystem_device"] = source.stat().st_dev
        if args.label == "B":
            assert metrics["media_read_bytes"] == metrics["finite_read_upper_bound"]
            assert metrics["max_item_read_bytes"] <= 12288
            assert metrics["execute_read_bytes"] == 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metrics, indent=2) + "\n")
    print(json.dumps(metrics), flush=True)


if __name__ == "__main__":
    main()
