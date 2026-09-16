"""Cold-read equivalence/Reader reachability on a supplied synthetic Work only."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import weakref

from mediasense.precheck.read import PrecheckReadTool
from mediasense.runtime._view_lifecycle import Lifecycle, construct_view
from mediasense.plan._sqlite import SQLitePlanStore


def run(args):
    clock = [0.0]
    refs = []

    def factory(route):
        view = construct_view(route)
        reader = next(
            cell.cell_contents
            for cell in view.tool.precheck_read.read.__closure__
            if isinstance(cell.cell_contents, PrecheckReadTool)
        )
        refs.append((weakref.ref(view), weakref.ref(reader)))
        return view

    workspace = args.workspace.resolve()
    database = workspace / "plan" / "work-v3.sqlite3"
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    binding = SQLitePlanStore.read_binding(database, args.work_ref)
    life = Lifecycle(clock=lambda: clock[0], factory=factory)
    token = life.register(
        {
            "workspace": str(workspace),
            "dataset_ref": args.dataset_ref,
            "work_ref": args.work_ref,
            "revision": binding["revision"],
        }
    )
    revision = binding["revision"]
    start = time.monotonic()
    with life.heavy(token, revision) as view:
        page = view.page(revision, "groups")
        first = view.page(revision, "group:0")
        assert first["next_cursor"] and len(first["items"]) == 50
        second = view.page(revision, "group:0", first["next_cursor"])
        asset_ref = next(
            s["evidence_ref"] for s in page["items"][0]["samples"] if s["available"]
        )
        asset = view.asset(revision, asset_ref)
    del view
    warm_seconds = time.monotonic() - start
    clock[0] = life.policy.cache_idle
    life.sweep()
    assert not life.contexts and all(ref() is None for pair in refs for ref in pair)
    assert life.current(token)["revision"] == revision and not life.contexts
    start = time.monotonic()
    with life.heavy(token, revision) as view:
        assert view.page(revision, "groups") == page
        assert view.page(revision, "group:0", first["next_cursor"]) == second
        assert view.asset(revision, asset_ref) == asset
    reload_seconds = time.monotonic() - start
    del view
    clock[0] += life.policy.cache_idle
    life.sweep()
    assert all(ref() is None for pair in refs for ref in pair)
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    report = {
        "work_ref": args.work_ref,
        "revision": revision,
        "reader_weakrefs_released": True,
        "cold_member_cursor_equal": True,
        "cold_group_page_equal": True,
        "cold_asset_bytes_equal": True,
        "work_database_unchanged": True,
        "initial_seconds": warm_seconds,
        "reload_seconds": reload_seconds,
        "rss_kib": int(
            subprocess.check_output(
                ["ps", "-o", "rss=", "-p", str(os.getpid())], text=True
            ).strip()
        ),
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dataset-ref", required=True)
    parser.add_argument("--work-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())
