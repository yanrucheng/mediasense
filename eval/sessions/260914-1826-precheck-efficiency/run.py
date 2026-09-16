"""Same-location, serial PreCheck cost recipe. Bulk evidence belongs in .local.

Worker invocations run one public Host sample. The driver restores only its own
marked workspace, after the previous process has exited and been archived.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import sqlite3
import sys
from threading import Lock, local
from time import perf_counter, sleep


ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "tests/run_precheck_composition_scale.py"
spec = importlib.util.spec_from_file_location("cost_helpers", HELPER)
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def normalized_package(package, database):
    """Whitelist only identities and real observation/publication timestamps.

    Every source occurrence has its own path key, regardless of equal bytes.
    Work references map to their semantic keys, never to a content-only key.
    Relationships, provenance and all other fields remain in the comparison.
    """
    refs = {package["result"]["ref"]: "RESULT"}
    refs.update({s["view"]["ref"]: "SOURCE:" + s["relative_path"] for s in package["sources"]})
    with sqlite3.connect(database) as connection:
        rows = {row[0]: row for row in connection.execute("SELECT work_id, semantic_key, descriptor_json, output_json FROM work_records")}
        domains = dict(connection.execute("SELECT reuse_domain, source_root FROM working_runs"))
    from mediasense.precheck._result_types import source_root_reference
    dataset_id = package["dataset"]["ref"].removeprefix("dataset:")
    for domain, source_root in domains.items():
        refs[source_root_reference(dataset_id, domain)] = "ROOT:" + source_root

    def work_key(work_id):
        if work_id in refs:
            return refs[work_id]
        row = rows[work_id]
        descriptor = json.loads(row[2])
        for dependency in descriptor["dependencies"]:
            if dependency["kind"] == "source_content":
                value = json.loads(dependency["value"])
                value["reuse_domain"] = "DOMAIN:" + domains[value["reuse_domain"]]
                dependency["value"] = canonical(value)
            elif dependency["kind"] == "upstream_work":
                assert rows[dependency["key"]][1] == dependency["value"]
                dependency["value"] = dependency["key"] = work_key(dependency["key"])
        key = "WORK:" + hashlib.sha256(canonical(descriptor).encode()).hexdigest()
        refs[work_id] = refs[row[1]] = key
        return key

    for work_id in rows:
        work_key(work_id)
    evidence_keys = set()
    for evidence in package["evidence"]:
        key = refs[evidence["work_id"]] + ":" + str(evidence["artifact_id"])
        assert key not in evidence_keys
        evidence_keys.add(key)
        refs[evidence["view"]["ref"]] = "EVIDENCE:" + key

    def walk(value, path=()):
        if isinstance(value, str):
            return refs.get(value, value)
        if isinstance(value, list):
            return [walk(child, (*path, index)) for index, child in enumerate(value)]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, child in value.items():
            if key == "published_at" and not path:
                result[key] = "PUBLICATION_TIME"
            elif key == "observed_at" and path[-1:] == ("value",) and value.get("producer") in {"builtin-source-content-proof-v1", "builtin-source-revision-observation-v1"}:
                result[key] = "SOURCE_OBSERVATION_TIME"
            else:
                result[key] = walk(child, (*path, key))
        return result

    value = walk(package)
    # These are object collections, not semantic order. Entry order is retained
    # separately; each complete relationship still participates in equality.
    entries = [r for r in value["relationships"] if r["relation"] == "entry_evidence"]
    value["sources"].sort(key=lambda row: row["relative_path"])
    value["evidence"].sort(key=lambda row: row["view"]["ref"])
    value["relationships"].sort(key=canonical)
    value["entry_order"] = entries
    return value


def worker(args):
    import mediasense
    from PIL import Image
    from mediasense.runtime.host import RuntimeHost
    from mediasense.precheck import rendition
    from mediasense.precheck.accounting import AccountingStore
    from mediasense.precheck.result import ResultStore
    from mediasense.precheck.read import PrecheckReadTool
    from mediasense.precheck.run import PrecheckRunTool
    from mediasense.precheck._orchestrator import PrecheckOrchestrator
    from mediasense.precheck._result_sqlite import SQLiteResultStore
    from mediasense.precheck.resources import ResourceBudget, ResourceClaim
    from mediasense.precheck import _snapshot

    args.output.mkdir(parents=True, exist_ok=False)
    source, workspace = args.slot / "source", args.slot / "workspace"
    config = args.slot / "config"
    config.mkdir(exist_ok=True)
    (config / "config.toml").write_text("[embedding]\nenabled=false\n[sensitivity]\nenabled=false\n")
    os.environ["MEDIASENSE_CONFIG_HOME"] = str(config)
    os.environ["MEDIASENSE_DATA_HOME"] = str(args.slot / "data")
    if not source.exists():
        source.mkdir()
        for index in range(args.size):
            color = (index % 256, (index // 256) * 70, (index * 37) % 256) if args.varied else "blue"
            Image.new("RGB", (32, 24) if args.varied else (8, 8), color).save(source / f"{index:05}.jpg")
    source_before = {p.name: digest(p) for p in source.iterdir()}
    stat_before = {p.name: (p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns) for p in source.iterdir()}
    host = RuntimeHost()
    opened = host.open_dataset(str(source), str(workspace))
    assert opened["outcome"] == "ok", opened
    dataset = opened["dataset_ref"]
    runtime = host._datasets[dataset]
    runtime.precheck_run._execution_config = replace(
        runtime.precheck_run._execution_config, metadata=False, gpx=False,
        video=False, bundles=False, compression_target=2,
        directed_evidence_paths=() if args.local else tuple(Path(name) for name in sorted(source_before)),
        resource_budget=ResourceBudget(ResourceClaim(
            source_io_slots=1, workspace_io_slots=1, cpu_slots=1, process_slots=1,
            memory_bytes=512 * 1024**2, temporary_bytes=128 * 1024**2,
            decoder_slots=1, encoder_slots=1, network_slots=1), max_workers=1, max_pending=2),
    )
    if args.empty:
        save(args.output / "metrics.json", {"dataset": dataset, "empty": True})
        return
    database = runtime.precheck_run.database_path
    store = ResultStore(database)
    trace = (args.output / "public-trace.jsonl").open("w")

    def call(tool, **request):
        response = host.call_tool("mediasense.precheck." + tool, dataset_ref=dataset,
                                  request={"dataset_ref": dataset, **request})
        trace.write(canonical({"tool": tool, "request": request, "response": response}) + "\n")
        assert "error" not in response, response
        return response

    with sqlite3.connect(database) as connection:
        old_results = {row[0]: (store.get(row[0]).path, digest(store.get(row[0]).path))
                       for row in connection.execute("SELECT result_ref FROM sealed_results")}
        attempts_before = connection.execute("SELECT count(*) FROM work_attempts").fetchone()[0]
    prior, old_page, extras, local_refs = None, None, {}, []
    prepared_paths, required_new_paths = set(), set()
    prior_seconds = 0
    if old_results:
        assert len(old_results) == 1
        prior = next(iter(old_results))
        start = perf_counter()
        old_page = call("read", action="review", result_ref=prior, include=["preparation"])
        prior_seconds = perf_counter() - start
        assert old_page["items"] and all("error" not in row for row in old_page["items"])
        if not args.discovery:
            extras = {"prior_result_ref": prior, **deepcopy(old_page["preparation"])}
        if args.local:
            package = json.loads(old_results[prior][0].read_text())
            prepared = {r["member"]["target"]["ref"] for r in package["relationships"]
                        if r["relation"] == "derived_from" and r["target_kind"] == "source_item"}
            sources = sorted(row["view"]["ref"] for row in package["sources"])
            paths_by_ref = {row["view"]["ref"]: row["relative_path"] for row in package["sources"]}
            prepared_paths = {paths_by_ref[ref] for ref in prepared}
            local_refs = [ref for ref in sources if ref not in prepared][:4] + [ref for ref in sources if ref in prepared][:2]
            assert len(local_refs) == 6 and sum(ref in prepared for ref in local_refs) == 2
            required_new_paths = {paths_by_ref[ref] for ref in local_refs if ref not in prepared}
            extras["profile"]["overrides"] = [{"source_set": {"kind": "explicit", "source_item_refs": local_refs}, "compression": None}]
            del package

    measure = helpers.Measurements()
    stages, counts, lock, current = [], Counter(), Lock(), local()
    decoded_paths = []

    def wrap(owner, name, stage, *, principal=False):
        original = getattr(owner, name)
        def wrapped(*a, **kw):
            start = perf_counter()
            previous = getattr(current, "stage", "other")
            current.stage = stage
            with lock:
                counts[stage] += 1
                if stage == "decode":
                    decoded_paths.append(Path(a[0]).relative_to(source).as_posix())
            try:
                return original(*a, **kw)
            finally:
                end = perf_counter()
                current.stage = previous
                if principal:
                    with lock:
                        stages.append({"stage": stage, "start": start, "end": end, "seconds": end - start})
        setattr(owner, name, wrapped)

    wrap(rendition, "_decode_rgb", "decode")
    wrap(PrecheckRunTool, "_start", "acceptance", principal=True)
    wrap(AccountingStore, "process_run", "accounting", principal=True)
    wrap(_snapshot, "process_snapshot", "snapshot", principal=True)
    wrap(PrecheckOrchestrator, "_renditions", "preparation", principal=True)
    wrap(PrecheckOrchestrator, "_compression", "compression", principal=True)
    wrap(ResultStore, "build_minimal", "assembly", principal=True)
    wrap(SQLiteResultStore, "seal", "seal", principal=True)
    wrap(PrecheckReadTool, "_validate_package", "read_validation", principal=True)
    wrap(rendition.ImageRenditionProducer, "produce_profiles", "preparation_worker")
    if hasattr(rendition.ImageRenditionProducer, "produce_many"):
        wrap(rendition.ImageRenditionProducer, "produce_many", "preparation_worker")
    from mediasense.precheck.embedding import EmbeddingProducer
    from mediasense.precheck.sensitivity import SensitivityProducer
    from mediasense.capabilities.geo import GeoQueryTool
    wrap(EmbeddingProducer, "produce_many", "embedding_calls")
    wrap(SensitivityProducer, "produce_many", "sensitivity_calls")
    wrap(GeoQueryTool, "handle", "geo_calls")
    sql_counts = defaultdict(Counter)
    if args.diagnostic:
        original_connect = sqlite3.connect
        def connect(*a, **kw):
            with lock:
                sql_counts[getattr(current, "stage", "other")]["connect"] += 1
            connection = original_connect(*a, **kw)
            def sql(statement):
                with lock:
                    sql_counts[getattr(current, "stage", "other")][statement.lstrip().split(None, 1)[0].upper()] += 1
            connection.set_trace_callback(sql)
            return connection
        sqlite3.connect = connect
        from mediasense.runtime._validation import ReadValidator
        original_evolve = ReadValidator.evolve
        def evolve(self, **changes):
            if changes.get("schema", {}).get("$ref") == "#/$defs/observation":
                with lock:
                    counts["observation_validator_constructions"] += 1
            return original_evolve(self, **changes)
        ReadValidator.evolve = evolve

    started_at, load_before = datetime.now(timezone.utc).isoformat(), os.getloadavg()
    cpu_before = resource.getrusage(resource.RUSAGE_SELF)
    with measure.span("run") as memory:
        created = call("run", action="start", request_id="efficiency-warm" if prior else "efficiency-cold", **extras)
        run_ref = created["run_ref"]
        deadline = perf_counter() + 3600
        while True:
            status = call("run", action="status", run_ref=run_ref)
            if status["state"] == "paused":
                confirmation = status["confirmation"]
                call("run", action="resume", run_ref=run_ref, decision={"kind": "source_scope", "inventory_fingerprint": confirmation["inventory_fingerprint"], "default_disposition": "include", "exceptions": []})
            elif status["state"] != "running":
                assert status["state"] == "completed", status
                break
            assert perf_counter() < deadline
            sleep(0.1)
    cpu_after = resource.getrusage(resource.RUSAGE_SELF)
    run_counts, run_stages = dict(counts), list(stages)
    run_sql = {key: dict(value) for key, value in sql_counts.items()}
    result_ref = status["result"]["ref"]
    start = perf_counter()
    page = call("read", action="review", result_ref=result_ref, include=["preparation"])
    read_seconds = perf_counter() - start
    assert page["accounting"]["total"] == args.size
    assert page["page"]["total"] == (8 if args.local and prior else 2), page
    assert all("error" not in row for row in page["items"])
    measured_peak = helpers.high_water()
    measure.stop.set()
    measure.sampler.join()

    # All auditing below is outside the Run and first public Read timing.
    start = perf_counter()
    saved = store.get(result_ref)
    package = json.loads(saved.path.read_text())
    assert len(package["sources"]) == args.size
    assert not package["execution_boundary"]["network_access"]
    assert not package["execution_boundary"]["remote_models"]
    assert run_counts.get("embedding_calls", 0) == run_counts.get("sensitivity_calls", 0) == run_counts.get("geo_calls", 0) == 0
    if args.local and prior:
        assert required_new_paths <= set(decoded_paths)
        assert not prepared_paths.intersection(decoded_paths)
        assert len(decoded_paths) == len(set(decoded_paths))
    else:
        expected_decode = 0 if prior else 128 if args.local else args.size
        assert run_counts.get("decode", 0) == expected_decode, run_counts

    def resolve(ref, expression, target=None):
        members, cursors, cursor = [], set(), None
        while True:
            response = call("read", action="resolve", result_ref=ref, source_set=expression,
                            **({"target_result_ref": target} if target else {}),
                            page={"limit": 1000, **({"cursor": cursor} if cursor else {})})
            members.extend(response["members"])
            cursor = response["page"]["next_cursor"]
            if cursor is None:
                break
            assert cursor not in cursors
            cursors.add(cursor)
        refs = [row["source_item_ref"] for row in members]
        assert refs == sorted(set(refs)) and len(refs) == response["page"]["total"]
        expected = "sha256:" + hashlib.sha256(canonical({"result_ref": ref, "source_set": expression, "members": refs}).encode()).hexdigest()
        assert response["resolution"]["membership_identity"] == expected
        return members

    source_set = page["preparation"]["source_set"]
    assert len(resolve(result_ref, source_set)) == args.size
    if extras:
        mapped = resolve(prior, extras["source_set"], result_ref)
        assert len(mapped) == args.size and all(row["correspondence"]["status"] == "matched" for row in mapped)
        prior_package = json.loads(old_results[prior][0].read_text())
        original_paths = {row["view"]["ref"]: row["relative_path"] for row in prior_package["sources"]}
        current_paths = {row["view"]["ref"]: row["relative_path"] for row in package["sources"]}
        for row in mapped:
            assert original_paths[row["source_item_ref"]] == current_paths[row["correspondence"]["source_item_ref"]]
        del prior_package
    for override in page["preparation"]["profile"]["overrides"]:
        members = resolve(result_ref, override["source_set"])
        assert len(members) == 6
    source_refs = [row["view"]["ref"] for row in package["sources"]]
    for offset in range(0, len(source_refs), 16):
        selected = source_refs[offset:offset + 16]
        expanded = call("read", action="expand", result_ref=result_ref,
                        source_item_refs=selected,
                        include=["source_item", "observations", "covering_evidence"])
        assert {row["source_item_ref"] for row in expanded["items"]} == set(selected)
    refs = [row["view"]["ref"] for row in package["evidence"]]
    for offset in range(0, len(refs), 16):
        selected, seen, cursors, cursor = refs[offset:offset + 16], [], set(), None
        while True:
            response = call("read", action="review", result_ref=result_ref, evidence_refs=selected,
                            page={"limit": 16, **({"cursor": cursor} if cursor else {})})
            assert all("error" not in row for row in response["items"])
            seen.extend(row["evidence_ref"] for row in response["items"])
            cursor = response["page"]["next_cursor"]
            if cursor is None:
                break
            assert cursor not in cursors
            cursors.add(cursor)
        assert seen == sorted(selected)
    for old_ref, (path, old_digest) in old_results.items():
        assert digest(path) == old_digest
        assert call("read", action="review", result_ref=old_ref, include=["preparation"]) == old_page
    assert {p.name: digest(p) for p in source.iterdir()} == source_before
    assert {p.name: (p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns) for p in source.iterdir()} == stat_before
    normalized = normalized_package(package, database)
    (args.output / "normalized.json").write_text(canonical(normalized))
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM sealed_results").fetchone()[0] == len(old_results) + 1
        attempts = connection.execute("SELECT count(*) FROM work_attempts").fetchone()[0] - attempts_before
        run_id = connection.execute("SELECT accounting_run_id FROM precheck_runs WHERE run_ref = ?", (run_ref,)).fetchone()[0]
        reused = connection.execute("SELECT count(*) FROM run_work_records r JOIN work_records w USING (work_id) WHERE r.run_id = ? AND w.status = 'succeeded' AND NOT EXISTS (SELECT 1 FROM work_attempts a WHERE a.work_id = w.work_id AND a.run_id = r.run_id)", (run_id,)).fetchone()[0]
        artifacts = connection.execute("SELECT count(*), sum(size_bytes) FROM artifacts").fetchone()
        pragmas = {name: connection.execute("PRAGMA " + name).fetchone()[0] for name in ("journal_mode", "synchronous")}
    trace.close()
    audit_seconds = perf_counter() - start
    report = {
        "started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
        "implementation": str(Path(mediasense.__file__).resolve()), "python": sys.version,
        "script_sha256": digest(__file__), "helper_sha256": digest(HELPER),
        "size": args.size, "varied": args.varied, "local": args.local, "discovery": args.discovery,
        "diagnostic": args.diagnostic, "pid": os.getpid(), "load_before": load_before, "load_after": os.getloadavg(),
        "wall_seconds": memory["seconds"], "user_seconds": cpu_after.ru_utime - cpu_before.ru_utime,
        "system_seconds": cpu_after.ru_stime - cpu_before.ru_stime, "memory": memory,
        "read_seconds": read_seconds, "run_plus_read_seconds": memory["seconds"] + read_seconds,
        "prior_read_seconds": prior_seconds, "audit_seconds": audit_seconds, "stages": run_stages,
        "counts": run_counts, "sql": run_sql, "pragmas": pragmas,
        "decoded_paths": decoded_paths, "required_new_paths": sorted(required_new_paths),
        "source_identity": hashlib.sha256(canonical(source_before).encode()).hexdigest(),
        "source_unchanged": True, "source_root": str(source), "workspace": str(workspace),
        "old_result_digests": {key: value[1] for key, value in old_results.items()},
        "result_ref": result_ref, "result_sha256": saved.digest, "result_bytes": saved.size_bytes,
        "source_count": len(package["sources"]), "evidence_count": len(refs),
        "relationship_count": len(package["relationships"]), "entry_count": page["page"]["total"],
        "new_attempts": attempts, "reused_work": reused, "physical_artifacts": artifacts[0],
        "artifact_bytes": artifacts[1], "workspace_bytes": sum(p.stat().st_size for p in workspace.rglob("*") if p.is_file()),
        "measured_peak_through_read": measured_peak, "normalized_sha256": digest(args.output / "normalized.json"),
        "config": runtime.precheck_run._execution_config.value(), "all_public_evidence_read": True,
        "all_members_verified": True, "direct_correspondence_verified": bool(extras),
    }
    save(args.output / "metrics.json", report)
    print(canonical({key: report[key] for key in ("size", "wall_seconds", "read_seconds", "counts", "new_attempts", "physical_artifacts")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--size", type=int, default=512)
    for name in ("varied", "local", "discovery", "diagnostic", "empty"):
        parser.add_argument("--" + name, action="store_true")
    args = parser.parse_args()
    args.slot = args.slot.resolve()
    args.output = args.output.resolve()
    args.slot.mkdir(parents=True, exist_ok=True)
    worker(args)


if __name__ == "__main__":
    main()
