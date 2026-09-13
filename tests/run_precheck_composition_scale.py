"""Controlled local Run cost measurements; artifacts live at explicit --output."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sqlite3
import statistics
from threading import Lock
from time import monotonic, perf_counter, sleep

from PIL import Image
from mediasense.runtime.host import RuntimeHost
from mediasense.precheck.accounting import AccountingStore
from mediasense.precheck._work_sqlite import SQLiteWorkStore
from mediasense.precheck._result_sqlite import SQLiteResultStore
from mediasense.precheck.result import ResultStore
from mediasense.precheck.resources import ResourceBudget, ResourceClaim
import mediasense.precheck.rendition as rendition


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[4096, 8192])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--explicit", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    config = args.output / "config"
    config.mkdir()
    (config / "config.toml").write_text(
        "[embedding]\nenabled=false\n[sensitivity]\nenabled=false\n"
    )
    os.environ["MEDIASENSE_CONFIG_HOME"] = str(config)
    os.environ["MEDIASENSE_DATA_HOME"] = str(args.output / "data")
    stats = defaultdict(float)
    counts = Counter()
    lock = Lock()

    def timed(owner, name, category):
        original = getattr(owner, name)

        def call(*a, **kw):
            start = perf_counter()
            try:
                return original(*a, **kw)
            finally:
                with lock:
                    stats[category] += perf_counter() - start
                    counts[category] += 1

        setattr(owner, name, call)

    timed(AccountingStore, "process_run", "verification")
    if args.explicit:
        import mediasense.precheck._snapshot as snapshot

        timed(snapshot, "process_snapshot", "verification")
    timed(SQLiteWorkStore, "ensure_work", "reusable_work_lookup")
    timed(rendition, "_decode_rgb", "producer_execution")
    timed(ResultStore, "build_minimal", "assembly")
    timed(SQLiteResultStore, "seal", "sealing")
    connect = sqlite3.connect

    def counted_connect(*a, **kw):
        connection = connect(*a, **kw)

        def trace(statement):
            # Count statements only; never retain row data or SQL text.
            category = statement.lstrip().split(None, 1)[0].upper()
            with lock:
                counts["sql_" + category] += 1

        connection.set_trace_callback(trace)
        return connection

    sqlite3.connect = counted_connect
    report = {
        "hardware": platform.platform(),
        "python": platform.python_version(),
        "explicit": args.explicit,
        "verification_profile": "candidate-sha256-full-or-3x4k-v1",
        "repeats": args.repeats,
        "cases": [],
    }
    for size in args.sizes:
        home = args.output / str(size)
        source = home / "source"
        source.mkdir(parents=True)
        image = source / "00000.jpg"
        Image.new("RGB", (8, 8), "blue").save(image)
        payload = image.read_bytes()
        for i in range(1, size):
            (source / f"{i:05}.jpg").write_bytes(payload)
        source_digest = hashlib.sha256(payload).hexdigest()
        host = RuntimeHost()
        opened = host.open_dataset(str(source), str(home / "workspace"))
        assert opened["outcome"] == "ok", opened
        dataset = opened["dataset_ref"]
        runtime = host._datasets[dataset]
        runtime.precheck_run._execution_config = replace(
            runtime.precheck_run._execution_config,
            metadata=False,
            gpx=False,
            video=False,
            bundles=False,
            compression_target=2,
            directed_evidence_paths=tuple(Path(f"{i:05}.jpg") for i in range(size)),
            resource_budget=ResourceBudget(
                capacity=ResourceClaim(
                    source_io_slots=1,
                    workspace_io_slots=1,
                    cpu_slots=1,
                    process_slots=1,
                    memory_bytes=512 * 1024**2,
                    temporary_bytes=128 * 1024**2,
                    decoder_slots=1,
                    encoder_slots=1,
                    network_slots=1,
                ),
                max_workers=1,
                max_pending=2,
            ),
        )

        def call(action, **request):
            return host.call_tool(
                "mediasense.precheck.run",
                dataset_ref=dataset,
                request={"action": action, "dataset_ref": dataset, **request},
            )

        records, prior, preparation = [], None, None
        for sequence in range(args.repeats + 1 + int(args.explicit)):
            with lock:
                stats.clear()
                counts.clear()
            start = monotonic()
            extras = (
                {"prior_result_ref": prior, **preparation}
                if args.explicit and prior
                else {}
            )
            local = args.explicit and sequence == args.repeats + 1
            if local:
                from copy import deepcopy

                extras = deepcopy(extras)
                extras["profile"]["overrides"] = [
                    {
                        "source_set": read["items"][0]["represents"]["source_set"],
                        "compression": {
                            **extras["profile"]["compression"],
                            "target_entries": 4,
                        },
                    }
                ]
            created = call("start", request_id=f"bench-{sequence}", **extras)
            assert "error" not in created, created
            ref = created["run_ref"]
            while True:
                status = call("status", run_ref=ref)
                assert "error" not in status, status
                if status["state"] == "paused":
                    confirmation = status["confirmation"]
                    resumed = call(
                        "resume",
                        run_ref=ref,
                        decision={
                            "kind": "source_scope",
                            "inventory_fingerprint": confirmation[
                                "inventory_fingerprint"
                            ],
                            "default_disposition": "include",
                            "exceptions": [],
                        },
                    )
                    if "error" in resumed:
                        assert resumed["error"]["code"] == "invalid_state", resumed
                elif status["state"] != "running":
                    assert status["state"] == "completed", status
                    break
                if monotonic() - start > 1800:
                    raise RuntimeError("Run did not complete within measurement guard")
                sleep(0.1)
            wall = monotonic() - start
            prior = status["result"]["ref"]
            record = {
                "wall_seconds": wall,
                "case": "local_override"
                if local
                else "cold"
                if sequence == 0
                else "warm",
                "seconds": dict(stats),
                "counts": dict(counts),
                "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "result_ref": prior,
            }
            if sequence:
                assert record["counts"].get("producer_execution", 0) == 0, record
            request = {
                "dataset_ref": dataset,
                "action": "review",
                "result_ref": prior,
                "page": {"limit": 1},
            }
            if args.explicit:
                request["include"] = ["preparation"]
            read = host.call_tool(
                "mediasense.precheck.read", dataset_ref=dataset, request=request
            )
            assert read["accounting"]["total"] == size, read
            if args.explicit:
                preparation = read["preparation"]
            record["accounted"] = read["accounting"]["total"]
            record["entry_count"] = read["page"]["total"]
            records.append(record)
            (args.output / "progress.json").write_text(
                json.dumps({"size": size, "records": records}, indent=2)
            )
            print(
                json.dumps(
                    {
                        "size": size,
                        "sequence": sequence,
                        "wall_seconds": wall,
                        "case": "local_override"
                        if local
                        else "cold"
                        if sequence == 0
                        else "warm",
                        "producer_calls": record["counts"].get("producer_execution", 0),
                    }
                ),
                flush=True,
            )
        assert all(
            hashlib.sha256(p.read_bytes()).hexdigest() == source_digest
            for p in source.iterdir()
        )
        report["cases"].append(
            {
                "size": size,
                "records": records,
                "median_wall_seconds": statistics.median(
                    r["wall_seconds"] for r in records[1 : args.repeats + 1]
                ),
                "median_seconds": {
                    key: statistics.median(
                        r["seconds"].get(key, 0) for r in records[1 : args.repeats + 1]
                    )
                    for key in stats
                },
            }
        )
        (args.output / "metrics.json").write_text(json.dumps(report, indent=2))
    print(args.output / "metrics.json")


if __name__ == "__main__":
    main()
