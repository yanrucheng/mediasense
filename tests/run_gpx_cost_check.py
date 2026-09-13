"""Compare GPX execution on a private copy of retained, identical source Work.

No provider/model calls. Only the copied GPX Work is reset to measure cold
execution; source checks, matching, per-item persistence and replay all run.
Use --baseline-module with the unmodified gpx.py captured before this repair.
"""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sqlite3
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-module", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    private = args.output / "work.sqlite3"
    with sqlite3.connect(
        args.database.resolve().as_uri() + "?mode=ro", uri=True
    ) as original:
        with sqlite3.connect(private) as copy:
            original.backup(copy)
    from mediasense.precheck import AccountingStore
    from mediasense.precheck.work import WorkStore
    import mediasense.precheck.gpx as module

    if args.baseline_module:
        spec = importlib.util.spec_from_file_location(
            "mediasense.precheck._cost_baseline", args.baseline_module
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    with sqlite3.connect(private) as db:
        dataset_id = db.execute(
            "SELECT dataset_id FROM working_runs WHERE run_id=?", (args.run_id,)
        ).fetchone()[0]
    AccountingStore(private).register_dataset(dataset_id)  # migrate only the copy
    store = WorkStore(private)
    work = [
        r
        for r in store.list_run_work(args.run_id)
        if r.spec.capability == "gpx-location-candidate"
    ]
    expected = {r.work_id: r.output for r in work}
    inputs = []
    for record in work:
        metadata = next(
            d.key for d in record.spec.dependencies if d.kind == "upstream_work"
        )
        paths = sorted(
            {
                Path(json.loads(d.key)[1])
                for d in record.spec.dependencies
                if d.kind == "source_revision"
            }
        )
        # Every call sees the identical full adopted track set, including metadata
        # paths that will legitimately short-circuit because embedded GPS exists.
        inputs.append((record.work_id, metadata, paths))
    tracks = sorted({p for _, _, paths in inputs for p in paths})
    with sqlite3.connect(private) as db:
        db.executemany(
            "DELETE FROM work_attempts WHERE work_id=?", ((i,) for i in expected)
        )
        db.executemany(
            """UPDATE work_records SET status='ready', attempt_count=0,
            output_json=NULL, output_digest=NULL, succeeded_at=NULL,
            lease_run_id=NULL, lease_owner=NULL, lease_token=NULL, lease_expires_at=NULL
            WHERE work_id=?""",
            ((i,) for i in expected),
        )

    counts = Counter()
    seconds = Counter()
    actual_parse = module.gpxpy.parse
    actual_match = module.match_gpx_segments
    actual_prove = module.SourceValidityStore.prove
    actual_read = Path.read_text

    def measured(name, function):
        def call(*a, **kw):
            start = time.perf_counter()
            counts[name] += 1
            try:
                return function(*a, **kw)
            finally:
                seconds[name] += time.perf_counter() - start

        return call

    def read(path, *a, **kw):
        if path.suffix.lower() == ".gpx":
            counts["track_reads"] += 1
            counts["track_bytes"] += path.stat().st_size
        return actual_read(path, *a, **kw)

    module.gpxpy.parse = measured("parses", actual_parse)
    module.match_gpx_segments = measured("matches", actual_match)
    module.SourceValidityStore.prove = measured("proofs", actual_prove)
    Path.read_text = read
    results = {}
    for phase in ("first_execution", "new_producer_work_reuse"):
        counts.clear()
        seconds.clear()
        producer = module.GPXMatchProducer(private)
        start, cpu = time.perf_counter(), time.process_time()
        observed, reused = {}, 0
        for i, (work_id, metadata, _) in enumerate(inputs):
            outcome = producer.produce(args.run_id, metadata, tracks)
            assert outcome.work.work_id == work_id
            assert outcome.work.output == expected[work_id], work_id
            observed[work_id] = outcome.work.output
            reused += outcome.reused
            if i % 128 == 0:
                print(f"{phase}: {i}/{len(inputs)}", flush=True)
        results[phase] = {
            "wall_seconds": time.perf_counter() - start,
            "cpu_seconds": time.process_time() - cpu,
            "counts": dict(counts),
            "timing_seconds": dict(seconds),
            "work_count": len(observed),
            "reused": reused,
            "output_digest": hashlib.sha256(
                json.dumps(observed, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
    results["source_database"] = str(args.database)
    results["baseline_module_sha256"] = (
        hashlib.sha256(args.baseline_module.read_bytes()).hexdigest()
        if args.baseline_module
        else None
    )
    results["module"] = str(Path(module.__file__).resolve())
    (args.output / "metrics.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    main()
