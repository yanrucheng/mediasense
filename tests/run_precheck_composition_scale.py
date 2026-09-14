"""Independent processes per warm sample; no OS cache flush or state deletion.

Use the same interpreter/script with PYTHONPATH selecting each source build.
Each sample clones a fixed warmed workspace, reads its prior Result, executes
one Run, then checks complete output and retained Results. --reuse-fixtures
accepts the previous runner's layout; otherwise a separate process seeds it.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from copy import deepcopy
import ctypes
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import statistics
import struct
import subprocess
import sys
from threading import Event, Lock, Thread
from time import monotonic, perf_counter, sleep


def high_water():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


def file_digest(path):
    # Retention verification must not itself allocate a whole Result buffer and
    # contaminate the process high-water mark before the measured Run starts.
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rss_reader():
    if sys.platform == "darwin":
        library = ctypes.CDLL("/usr/lib/libproc.dylib")

        def read():
            info = ctypes.create_string_buffer(96)
            if library.proc_pidinfo(os.getpid(), 4, 0, info, 96) != 96:
                raise RuntimeError("Cannot measure current resident memory")
            return struct.unpack_from("QQ", info.raw)[1]

        return read
    if sys.platform.startswith("linux"):
        return lambda: (
            int(Path("/proc/self/statm").read_text().split()[1])
            * os.sysconf("SC_PAGE_SIZE")
        )
    raise RuntimeError("Current RSS measurement is unsupported")


class Measurements:
    def __init__(self):
        self.read_rss = rss_reader()
        self.lock = Lock()
        self.active, self.spans = {}, []
        self.seconds, self.counts = defaultdict(float), Counter()
        self.stop = Event()
        self.sampler = Thread(target=self.sample, daemon=True)
        self.sampler.start()

    def sample(self):
        while not self.stop.wait(0.02):
            current = self.read_rss()
            with self.lock:
                for row in self.active.values():
                    row["sampled_peak_rss_bytes"] = max(
                        row["sampled_peak_rss_bytes"], current
                    )

    @contextmanager
    def span(self, name):
        row = {
            "phase": name,
            "start_rss_bytes": self.read_rss(),
            "historical_peak_before_bytes": high_water(),
        }
        row["sampled_peak_rss_bytes"] = row["start_rss_bytes"]
        start = perf_counter()
        with self.lock:
            self.active[id(row)] = row
        try:
            yield row
        finally:
            row["seconds"] = perf_counter() - start
            row["end_rss_bytes"] = self.read_rss()
            row["historical_peak_after_bytes"] = high_water()
            with self.lock:
                self.active.pop(id(row))
                row["sampled_peak_rss_bytes"] = max(
                    row["sampled_peak_rss_bytes"], row["end_rss_bytes"]
                )
                row["peak_increment_bytes"] = (
                    row["sampled_peak_rss_bytes"] - row["start_rss_bytes"]
                )
                self.spans.append(row)
            print(json.dumps({"event": "phase", **row}), flush=True)

    def wrap(self, owner, name, category, memory=False):
        original = getattr(owner, name)

        def call(*args, **kwargs):
            start = perf_counter()
            try:
                if memory:
                    with self.span(category):
                        return original(*args, **kwargs)
                return original(*args, **kwargs)
            finally:
                with self.lock:
                    self.seconds[category] += perf_counter() - start
                    self.counts[category] += 1

        setattr(owner, name, call)


def worker(args):
    started_at = datetime.now(timezone.utc).isoformat()
    load_before = os.getloadavg()
    from PIL import Image
    import mediasense
    from mediasense.runtime.host import RuntimeHost
    from mediasense.precheck.accounting import AccountingStore
    from mediasense.precheck._work_sqlite import SQLiteWorkStore
    from mediasense.precheck._result_sqlite import SQLiteResultStore
    from mediasense.precheck.result import ResultStore
    from mediasense.precheck.read import PrecheckReadTool
    from mediasense.precheck.run import PrecheckRunTool
    from mediasense.precheck._run_sqlite import SQLiteRunStore
    from mediasense.precheck.resources import ResourceBudget, ResourceClaim
    import mediasense.precheck.rendition as rendition
    import mediasense.precheck._result_sqlite as sealing
    import sqlite3

    args.output.mkdir(parents=True, exist_ok=False)
    config = args.output / "config"
    config.mkdir()
    (config / "config.toml").write_text(
        "[embedding]\nenabled=false\n[sensitivity]\nenabled=false\n"
    )
    os.environ["MEDIASENSE_CONFIG_HOME"] = str(config)
    os.environ["MEDIASENSE_DATA_HOME"] = str(args.output / "data")
    size = args.sizes[0]
    home = (args.reuse_fixtures or args.output) / str(size)
    workspace = home / "workspace"
    if args.reuse_fixtures:
        source = Path(
            json.loads((workspace / "dataset.json").read_text())["source"]["value"]
        )
    else:
        source = home / "source"
        source.mkdir(parents=True)
        image = source / "00000.jpg"
        Image.new("RGB", (8, 8), "blue").save(image)
        payload = image.read_bytes()
        for i in range(1, size):
            (source / f"{i:05}.jpg").write_bytes(payload)
    source_before = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    }
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
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

    def call(tool, **request):
        return host.call_tool(
            "mediasense.precheck." + tool,
            dataset_ref=dataset,
            request={"dataset_ref": dataset, **request},
        )

    measure = Measurements()
    measure.wrap(PrecheckRunTool, "_start", "run_acceptance", True)
    measure.wrap(SQLiteRunStore, "start", "frozen_input_write", True)
    measure.wrap(AccountingStore, "process_run", "verification", True)
    if args.explicit:
        import mediasense.precheck._snapshot as snapshot
        import mediasense.precheck._preparation as preparation

        measure.wrap(snapshot, "process_snapshot", "verification", True)
        measure.wrap(snapshot, "seal_preparation", "preparation_sealing", True)
        measure.wrap(preparation, "freeze_preparation", "freezing", True)
        if hasattr(SQLiteRunStore, "execution_configuration"):
            measure.wrap(
                SQLiteRunStore, "execution_configuration", "frozen_input_read", True
            )
    measure.wrap(SQLiteWorkStore, "ensure_work", "reusable_work_lookup")
    measure.wrap(rendition, "_decode_rgb", "producer_execution")
    measure.wrap(ResultStore, "build_minimal", "assembly", True)
    measure.wrap(SQLiteResultStore, "seal", "sealing", True)
    measure.wrap(PrecheckReadTool, "_validate_package", "result_read_validation", True)
    measure.wrap(sealing, "_package", "package_projection", True)
    measure.wrap(sealing, "_encode_package", "package_encoding", True)
    connect = sqlite3.connect

    def counted_connect(*a, **kw):
        connection = connect(*a, **kw)

        def trace(statement):
            with measure.lock:
                measure.counts[
                    "sql_" + statement.lstrip().split(None, 1)[0].upper()
                ] += 1

        connection.set_trace_callback(trace)
        return connection

    sqlite3.connect = counted_connect
    prior, old_page, extras = None, None, {}
    old_results = {}
    store = ResultStore(runtime.precheck_run.database_path)
    with runtime.precheck_run._store._connect() as connection:
        for row in connection.execute("SELECT result_ref FROM sealed_results"):
            saved = store.get(row[0])
            old_results[row[0]] = (
                saved.path,
                file_digest(saved.path),
            )
    if args.reuse_fixtures:
        earlier = json.loads((args.reuse_fixtures / "metrics.json").read_text())
        case = next(c for c in earlier["cases"] if c["size"] == size)
        prior = next(
            r["result_ref"]
            for r in reversed(case["records"])
            if r.get("case", "warm") in {"warm", "cold"}
        )
        with measure.span("prior_read_warmup"):
            old_page = call(
                "read",
                action="review",
                result_ref=prior,
                **({"include": ["preparation"]} if args.explicit else {}),
            )
        assert "error" not in old_page, old_page
        if args.explicit:
            extras = {"prior_result_ref": prior, **old_page["preparation"]}
        if args.local_override:
            extras = deepcopy(extras)
            extras["profile"]["overrides"] = [
                {
                    "source_set": old_page["items"][0]["represents"]["source_set"],
                    "compression": {
                        **extras["profile"]["compression"],
                        "target_entries": 4,
                    },
                }
            ]
    prelude = list(measure.spans)
    measure.spans.clear()
    measure.seconds.clear()
    measure.counts.clear()
    with measure.span("single_run") as run_memory:
        start = monotonic()
        created = call(
            "run",
            action="start",
            request_id="isolated-cost-warm"
            if args.reuse_fixtures
            else "isolated-cost-cold",
            **extras,
        )
        assert "error" not in created, created
        ref = created["run_ref"]
        while True:
            status = call("run", action="status", run_ref=ref)
            assert "error" not in status, status
            if status["state"] == "paused":
                c = status["confirmation"]
                resumed = call(
                    "run",
                    action="resume",
                    run_ref=ref,
                    decision={
                        "kind": "source_scope",
                        "inventory_fingerprint": c["inventory_fingerprint"],
                        "default_disposition": "include",
                        "exceptions": [],
                    },
                )
                if "error" in resumed:
                    assert resumed["error"]["code"] == "invalid_state", resumed
            elif status["state"] != "running":
                assert status["state"] == "completed", status
                break
            if monotonic() - start > 3600:
                raise RuntimeError("Run exceeded measurement guard")
            sleep(0.1)
    record = {
        "case": "local_override"
        if args.local_override
        else "warm"
        if args.reuse_fixtures
        else "cold",
        "result_ref": status["result"]["ref"],
        "wall_seconds": run_memory["seconds"],
        "seconds": dict(measure.seconds),
        "counts": dict(measure.counts),
        "memory": dict(run_memory),
        "phases": list(measure.spans),
    }
    assert record["result_ref"] not in old_results
    with runtime.precheck_run._store._connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM sealed_results").fetchone()[0]
            == len(old_results) + 1
        )
    with measure.span("public_read"):
        read = call(
            "read",
            action="review",
            result_ref=record["result_ref"],
            **({"include": ["preparation"]} if args.explicit else {}),
        )
    assert read["accounting"]["total"] == size, read
    expected_entries = 6 if args.local_override else 2
    assert read["page"]["total"] == expected_entries, read
    assert not any("error" in item for item in read["items"]), read
    record.update(
        accounted=size,
        entry_count=expected_entries,
        result_bytes=store.get(record["result_ref"]).size_bytes,
    )
    if args.reuse_fixtures:
        assert record["counts"].get("producer_execution", 0) == 0, record
    measured_process_peak = high_water()
    # These post-measurement checks preserve all old state and verify its bytes.
    for path, digest in old_results.values():
        assert file_digest(path) == digest
    if prior:
        assert (
            call(
                "read",
                action="review",
                result_ref=prior,
                **({"include": ["preparation"]} if args.explicit else {}),
            )
            == old_page
        )
    assert {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source.iterdir()
    } == source_before
    measure.stop.set()
    measure.sampler.join()
    report = {
        "measurement_script_sha256": hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "load_average_before": load_before,
        "load_average_after": os.getloadavg(),
        "source_content_identity": hashlib.sha256(
            json.dumps(source_before, sort_keys=True).encode()
        ).hexdigest(),
        "source_root": str(source),
        "resource_budget": runtime.precheck_run._execution_config.value()[
            "resource_budget"
        ],
        "pid": os.getpid(),
        "hardware": platform.platform(),
        "python": platform.python_version(),
        "implementation": str(Path(mediasense.__file__).resolve()),
        "explicit": args.explicit,
        "local_override": args.local_override,
        "verification_profile": "candidate-sha256-full-or-3x4k-v1",
        "sample_interval_seconds": 0.02,
        "cache_condition": "warm producer cache; fresh interpreter; prior read; OS caches uncontrolled",
        "prelude": prelude,
        "process_peak_through_run_and_read_bytes": measured_process_peak,
        "process_peak_after_retention_checks_bytes": high_water(),
        "old_results_retained": len(old_results),
        "source_unchanged": True,
        "public_read": next(s for s in measure.spans if s["phase"] == "public_read"),
        "cases": [{"size": size, "records": [record]}],
    }
    (args.output / "metrics.json").write_text(json.dumps(report, indent=2))
    print(
        json.dumps(
            {
                "size": size,
                "pid": os.getpid(),
                "wall_seconds": record["wall_seconds"],
                "run_peak_mib": run_memory["sampled_peak_rss_bytes"] / 1024**2,
            }
        ),
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=[4096, 8192])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--explicit", action="store_true")
    parser.add_argument("--local-override", action="store_true")
    parser.add_argument("--reuse-fixtures", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    if args.local_override and not (args.explicit and args.reuse_fixtures):
        parser.error("local override requires explicit warm fixtures")
    args.output = args.output.resolve()
    if args.reuse_fixtures:
        args.reuse_fixtures = args.reuse_fixtures.resolve()
    if args.worker:
        assert len(args.sizes) == 1
        return worker(args)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {
        "measurement": "independent-process-per-size-and-repeat-v2",
        "samples": [],
    }

    def launch(output, size, fixtures=None):
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            "--output",
            str(output),
            "--sizes",
            str(size),
        ]
        if args.explicit:
            command.append("--explicit")
        if args.local_override:
            command.append("--local-override")
        if fixtures:
            command.extend(["--reuse-fixtures", str(fixtures)])
        subprocess.run(command, check=True)
        return json.loads((output / "metrics.json").read_text())

    for size in args.sizes:
        template = args.reuse_fixtures
        if template is None:
            template = args.output / f"template-{size}"
            launch(template, size)
        for repeat in range(args.repeats):
            sample = args.output / f"{size}-{repeat}"
            fixture = sample / "fixture"
            (fixture / str(size)).mkdir(parents=True)
            original = template / str(size) / "workspace"
            target = fixture / str(size) / "workspace"
            if sys.platform == "darwin":
                # APFS clone is independent, never a hard link to mutable state.
                subprocess.run(["cp", "-cR", str(original), str(target)], check=True)
            else:
                shutil.copytree(original, target)
            shutil.copy2(template / "metrics.json", fixture / "metrics.json")
            measured = launch(sample / "measurement", size, fixture)
            report["samples"].append(measured)
            report["medians"] = {
                str(n): statistics.median(
                    s["cases"][0]["records"][0]["wall_seconds"]
                    for s in report["samples"]
                    if s["cases"][0]["size"] == n
                )
                for n in {s["cases"][0]["size"] for s in report["samples"]}
            }
            (args.output / "metrics.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
