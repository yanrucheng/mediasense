"""Audit one retained run; stdout only, no provider/model execution or DB writes.

Use the audited installation's Python with PYTHONDONTWRITEBYTECODE=1. Pure
compression and Geo selection replays consume retained vectors/Work values.
Google payload probes use a capturing transport with a dummy credential.
"""

from __future__ import annotations

import base64
from collections import Counter, defaultdict
from dataclasses import replace
from datetime import datetime
import hashlib
from html.parser import HTMLParser
import io
import json
import math
from pathlib import Path
import sqlite3
import struct
from types import SimpleNamespace
from urllib.parse import unquote, urlparse


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def counted(values):
    return dict(sorted(Counter(values).items()))


def database(path):
    c = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA query_only=ON")
    return c


def session_rows(config):
    lines = Path(config["session"]).read_bytes().splitlines(keepends=True)
    raw = b"".join(lines[:config["session_prefix_lines"]])
    assert digest(raw) == config["session_prefix_sha256"]
    return raw, [json.loads(line) for line in raw.splitlines()]


def recorded_plan(config):
    _, rows = session_rows(config)
    selected = None
    for row in rows:
        payload = row.get("payload", {})
        if payload.get("type") != "item_completed":
            continue
        item = payload["item"]
        if item.get("type") != "McpToolCall" or item.get("tool") != "mediasense.plan.work":
            continue
        result = (item.get("result") or {}).get("structuredContent", {})
        if result.get("action") == "inspect" and result.get("candidate_content_identity") == config["candidate_identity"]:
            selected = result
    assert selected is not None
    content = selected["sections"]["content"]["value"]
    candidate = {k: v for k, v in content.items() if k not in {"contract", "plan_ref"}}
    return {**selected, "candidate_identity": selected["candidate_content_identity"],
            "candidate_json": canonical(candidate),
            "organization_preferences_json": canonical(selected["sections"]["preferences"])}


def observation(record, name):
    return next((x.get("value") for x in record["output"].get("observations", [])
                 if x["name"] == name and x["status"] == "available"), None)


def source_paths(record):
    return tuple(sorted(Path(json.loads(d["key"])[1]) for d in record["spec"]["dependencies"]
                        if d["kind"] == "source_revision"))


def subject(record):
    output = record["output"].get("subject", {}).get("relative_path")
    if output:
        return Path(output)
    parameter = next((d["value"] for d in record["spec"]["dependencies"]
                      if d["kind"] == "parameter" and d["key"] == "subject_relative_path"), None)
    return Path(parameter) if parameter else source_paths(record)[0]


def compression_replay(work, artifact_paths, precheck_root):
    from mediasense.precheck._compression_strategy import (
        AdaptiveCompressionProfile, CompressionPoint, build_adaptive_groups,
    )

    by_cap = defaultdict(list)
    for r in work.values():
        if r["status"] == "succeeded":
            by_cap[r["capability"]].append(r)
    visual = {}
    for r in by_cap["image-rendition"]:
        path = subject(r)
        if path not in visual or r["output"]["value"]["profile"]["name"] == "high_resolution":
            visual[path] = r
    for r in by_cap["video-key-frame-candidate"]:
        visual[subject(r)] = work[r["output"]["candidate"]["selected_frame_work_id"]]
    for r in by_cap["video-contact-sheet"]:
        visual.setdefault(subject(r), r)
    metadata = {subject(r): r for r in by_cap["source-metadata"]}
    gpx = {subject(r): r for r in by_cap["gpx-location-candidate"]}
    embeddings = {r["output"]["value"]["input_work_id"]: r for r in by_cap["image-embedding"]}
    missing = {"output": {}}
    points, corrected, covered = [], [], set()
    lost_gpx = []

    def add(path, members):
        r = visual[path]
        e = embeddings.get(r["work_id"])
        vector = None
        if e is not None:
            aid = e["output"]["artifacts"][0]["artifact_ref"]
            raw = (precheck_root / artifact_paths[aid]).read_bytes()
            assert digest(raw) == aid.split(":")[-1]
            vector = struct.unpack("<" + "f" * (len(raw) // 4), raw)
        time = observation(metadata.get(path, missing), "capture_time")
        native = observation(metadata.get(path, missing), "gps_coordinates")
        # Reproduce the installed consumer exactly: it requests gps_coordinates
        # even on GPX Work, whose actual public observation is gpx_coordinates.
        actual = native or observation(gpx.get(path, missing), "gps_coordinates")
        repaired = native or observation(gpx.get(path, missing), "gpx_coordinates")
        def coord(value):
            return None if value is None else (value["latitude"], value["longitude"])
        p = CompressionPoint(path, datetime.fromisoformat(time) if time else None,
                             coord(actual), vector, members, len(members))
        points.append(p)
        corrected.append(replace(p, gps=coord(repaired)))
        if actual is None and repaired is not None:
            lost_gpx.append(path.as_posix())

    for r in by_cap["bundle-candidate"]:
        members = source_paths(r)
        path = Path(r["output"]["candidate"]["representative_path"])
        if path not in visual:
            alternatives = sorted(p for p in members if p in visual)
            if not alternatives:
                continue
            path = alternatives[0]
        add(path, members)
        covered.update(p for p in members if p in visual)
    for path in visual:
        if path not in covered:
            add(path, (path,))
    saved = by_cap["adaptive-compression-group"]
    profile = AdaptiveCompressionProfile(**saved[0]["output"]["profile"])
    groups = build_adaptive_groups(points, profile)
    expected = {r["output"]["group"]["group_id"] for r in saved}
    assert {g.group_id for g in groups} == expected
    no_embedding = build_adaptive_groups(
        [replace(p, embedding=None) for p in points], replace(profile, content_based_boundaries=False),
    )
    with_gpx = build_adaptive_groups(corrected, profile)
    return {
        "input_points": len(points), "embedded_points": sum(p.embedding is not None for p in points),
        "input_member_count": sum(len(p.members) for p in points),
        "replayed_groups": len(groups), "saved_groups_match": True,
        "no_embedding_same_prepared_inputs_groups": len(no_embedding),
        "correct_gpx_observation_groups": len(with_gpx),
        "correct_gpx_changed_group_ids": len(expected.symmetric_difference(g.group_id for g in with_gpx)),
        "correct_gpx_qualifications": counted(q for g in with_gpx for q in g.qualifications),
        "gpx_available_but_ignored_points": len(lost_gpx),
        "ignored_gpx_example_paths": lost_gpx[:3],
        "native_gps_points": sum(p.gps is not None for p in points),
        "profile": saved[0]["output"]["profile"],
        "qualifications": counted(q for g in groups for q in g.qualifications),
        "single_source_groups": sum(len(g.members) == 1 for g in groups),
        "max_group_members": max(len(g.members) for g in groups),
        "representative_methods": counted(g.basis["representative_method"] for g in groups),
        "points_per_group": counted(g.basis["candidate_point_count"] for g in groups),
    }


def geo_replay(work):
    from mediasense.precheck._work_types import DependencyKind, WorkStatus
    from mediasense.precheck import geocode

    records = []
    coordinates = []
    producers = Counter()
    for r in work.values():
        if r["capability"] not in {"source-metadata", "gpx-location-candidate", "bundle-candidate"}:
            continue
        deps = [SimpleNamespace(**{**d, "kind": DependencyKind(d["kind"])})
                for d in r["spec"]["dependencies"]]
        records.append(SimpleNamespace(work_id=r["work_id"], status=WorkStatus(r["status"]),
                       output=r["output"], spec=SimpleNamespace(capability=r["capability"], dependencies=deps)))
        for name in ("gps_coordinates", "gpx_coordinates"):
            v = observation(r, name)
            if v:
                coordinates.append((v["latitude"], v["longitude"]))
                producers[r["capability"]] += 1
    selected = [r.work_id for r in records if r.spec.capability != "bundle-candidate"]
    bundles = [r.work_id for r in records if r.spec.capability == "bundle-candidate"]
    unit_sizes = []
    split = geocode._split_bundle

    def record_units(members):
        units = split(members)
        unit_sizes.extend(len(u) for u in units)
        return units

    geocode._split_bundle = record_units
    try:
        queries = geocode._queries_from_work(records, selected, bundle_work_ids=bundles)
    finally:
        geocode._split_bundle = split
    return {
        "source_coordinate_observations": len(coordinates), "unique_exact_source_coordinates": len(set(coordinates)),
        "coordinate_producers": dict(producers), "zero_coordinate_sources": coordinates.count((0, 0)),
        "units_before_exact_dedup": len(unit_sizes), "unit_sizes": counted(unit_sizes),
        "logical_queries": len(queries), "covered_source_items": sum(len(q.source_paths) for q in queries),
        "query_coordinate_fingerprint": digest(canonical(sorted(canonical(q.coordinate.value()) for q in queries)).encode()),
        "max_shared_diameter_meters": geocode._MAX_SHARED_DIAMETER_METERS,
        "max_shared_span_seconds": geocode._MAX_SHARED_SPAN_SECONDS,
    }


def google_payload_probe():
    from mediasense.geo import GoogleMapsReverseGeocoder
    from mediasense.capabilities.geo.model import GeoCoordinate, GeoOperation

    class Capture:
        def __init__(self):
            self.posts = []

        def get_json(self, url, **kwargs):
            return {"status": "ZERO_RESULTS", "results": []}

        def post_json(self, url, **kwargs):
            self.posts.append(kwargs["payload"])
            return {}

    transport = Capture()
    provider = GoogleMapsReverseGeocoder("audit-dummy-not-a-key", transport=transport, minimum_interval=0)
    result = {"network_requests": 0, "requested_max_places": 30, "configured_provider_max": provider.max_pois}
    for operation in (GeoOperation.NEARBY_PLACES, GeoOperation.RESOLVE_PLACE):
        transport.posts.clear()
        provider.execute(operation, GeoCoordinate(22.3, 114.17), locale="zh", radius_meters=500, max_places=30)
        result[operation.value + "_maxResultCount"] = transport.posts[0]["maxResultCount"]
    assert result["nearby_places_maxResultCount"] == 30
    assert result["resolve_place_maxResultCount"] == 10
    return result


class Preview(HTMLParser):
    def __init__(self):
        super().__init__()
        self.collect = False
        self.candidate = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "pre" and attrs.get("id") == "candidate-content":
            self.collect = True
        if tag == "img":
            self.images.append(attrs.get("src", ""))

    def handle_endtag(self, tag):
        if tag == "pre":
            self.collect = False

    def handle_data(self, data):
        if self.collect:
            self.candidate.append(data)


def trajectory(config, sealed):
    path = Path(config["session"])
    raw, rows = session_rows(config)
    seen, events = set(), []
    for line, row in enumerate(rows, 1):
        p = row.get("payload", {})
        if p.get("type") == "item_completed" and p["item"]["id"] not in seen:
            seen.add(p["item"]["id"])
            events.append((line, p["item"]))
    mcp = [(line, e) for line, e in events if e["type"] == "McpToolCall"]
    image_events = [(line, e) for line, e in events if e["type"] == "ImageView"]
    manifest = None
    for _, e in events:
        change = e.get("changes", {}).get("/tmp/mediasense-plan-hk-manifest.json")
        if change and change["type"] == "add":
            manifest = json.loads(change["content"])
    assert manifest is not None
    opened = [unquote(urlparse(e["path"]).path) for _, e in image_events]
    direct = {p for p in opened if "/precheck/_artifacts/" in p}
    entry_images = {r["path"] for r in manifest}
    viewed = direct | entry_images
    derivations = defaultdict(set)
    for r in sealed["relationships"]:
        if r["relation"] == "derived_from":
            derivations[r["origin"]].add(r["member"]["target"]["ref"])

    def sources(ref):
        if ref.startswith("source-item:"):
            return {ref}
        return set().union(*(sources(child) for child in derivations[ref]))

    image_sources = {}
    for e in sealed["evidence"]:
        v = e["view"]
        p = v.get("access", {}).get("locator", {}).get("value")
        if p in viewed:
            image_sources.setdefault(p, set()).update(sources(v["ref"]))
    assert set(image_sources) == viewed
    reads = [(line, e) for line, e in mcp if e["tool"] == "mediasense.precheck.read"]

    def usage_from(first_line):
        usage, responses = Counter(), set()
        for line, r in enumerate(rows, 1):
            if r["type"] == "token_usage_record" and line >= first_line:
                p = r["payload"]
                if p["response_id"] not in responses:
                    responses.add(p["response_id"])
                    usage.update({k: v for k, v in p["usage"].items() if isinstance(v, int)})
        return {"requests": len(responses), "usage": dict(usage)}

    plan_usage = usage_from(config["plan_start_line"])
    first_review_line = min(line for line, e in reads if e["arguments"]["action"] == "review")
    return {
        "file": str(path), "sha256": digest(raw), "id": rows[0]["payload"]["id"],
        "first": rows[0]["timestamp"], "last": rows[-1]["timestamp"],
        "mcp_tools": counted(e["tool"] for _, e in mcp),
        "precheck_reads": counted(e["arguments"]["action"] for _, e in reads),
        "plan_reads": counted(e["arguments"]["action"] for line, e in reads if line >= config["plan_start_line"]),
        "plan_geo_calls": sum(e["tool"] == "mediasense.geo.query" for line, e in mcp if line >= config["plan_start_line"]),
        "image_attachments": len(opened), "entry_images_in_sheets": len(entry_images),
        "direct_image_opens": len(direct), "distinct_derived_images": len(viewed),
        "distinct_source_items_viewed": len(set().union(*image_sources.values())),
        "image_event_lines": [line for line, _ in image_events],
        "plan_model_requests": plan_usage["requests"], "plan_usage": plan_usage["usage"],
        "from_first_result_review": {"line": first_review_line, **usage_from(first_review_line)},
    }


def main():
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    root = Path(config["workspace"])
    with database(root / "precheck/work.sqlite3") as c:
        run = dict(c.execute("SELECT * FROM precheck_runs WHERE run_ref=?", (config["run_ref"],)).fetchone())
        rows = [dict(r) for r in c.execute("SELECT * FROM work_records")]
        artifacts = {r["artifact_id"]: r["relative_path"] for r in c.execute("SELECT * FROM artifacts")}
        saved = dict(c.execute("SELECT * FROM sealed_results WHERE result_ref=?", (config["result_ref"],)).fetchone())
        attempts = [dict(r) for r in c.execute("SELECT * FROM work_attempts")]
    work = {r["work_id"]: {**r, "spec": json.loads(r["descriptor_json"]), "output": json.loads(r["output_json"] or "{}")} for r in rows}
    run_config = json.loads(run["execution_config_json"])
    raw = (root / "precheck" / saved["relative_path"]).read_bytes()
    assert digest(raw) == saved["digest"] and len(raw) == saved["size_bytes"]
    sealed = json.loads(raw)
    assert sealed["result"]["ref"] == config["result_ref"]
    scope = {r["member"]["target"]: r["member"] for r in sealed["relationships"] if r["relation"] == "accounts_for"}
    entries = [r["member"]["target"] for r in sealed["relationships"] if r["relation"] == "entry_evidence"]
    with database(root / "geo/journal.sqlite3") as c:
        geo_rows = c.execute("SELECT result_json FROM geo_operation_journal").fetchall()
        assert len(geo_rows) == 1
        geo = json.loads(geo_rows[0][0])
        geo_request = json.loads(c.execute("SELECT request_json FROM geo_execution_cycles").fetchone()[0])
    with database(root / "plan/work-v3.sqlite3") as c:
        live_plan = dict(c.execute("SELECT * FROM plan_works WHERE work_ref=?", (config["work_ref"],)).fetchone())
        sealed_plans = c.execute("SELECT count(*) FROM plan_works WHERE state='closed'").fetchone()[0]
    plan = recorded_plan(config)
    candidate = json.loads(plan["candidate_json"])
    assert plan["candidate_identity"] == config["candidate_identity"]
    assigned = [ref for g in candidate["groups"] for ref in g["members"]["source_item_refs"]]
    other = [ref for o in candidate["other_outcomes"] for ref in o["members"]["source_item_refs"]]
    assert len(assigned + other) == len(set(assigned + other)) == len(scope)
    assert set(assigned + other) == set(scope)
    preview_path = Path(config["preview"])
    if not preview_path.is_absolute():
        preview_path = Path(__file__).parent / preview_path
    preview_raw = preview_path.read_bytes()
    parser = Preview()
    parser.feed(preview_raw.decode())
    preview_candidate = json.loads("".join(parser.candidate))
    assert all(preview_candidate[k] == v for k, v in candidate.items())
    assert "sha256:" + digest(canonical(preview_candidate).encode()) == plan["candidate_identity"]
    from PIL import Image
    for uri in parser.images:
        assert uri.startswith("data:image/")
        Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1]))).verify()
    fixture = Path(config["fixture"])
    assert digest((fixture / "manifests/SHA256SUMS").read_bytes()) == config["fixture_manifest_sha256"]
    media = [json.loads(line) for line in (fixture / "manifests/media-manifest.jsonl").read_text().splitlines()]
    mismatches = []
    for item in media:
        path = Path(config["source"]) / "260501-HK美食之旅" / item["path"]
        if not path.exists() or digest(path.read_bytes()) != item["derived_sha256"]:
            mismatches.append(item["path"])
    declared_paths = {"260501-HK美食之旅/" + m["path"] for m in media}
    additional_media = []
    for source in sealed["sources"]:
        path = source["relative_path"]
        if scope[source["view"]["ref"]]["scope"] == "source_media" and path not in declared_paths:
            actual = (Path(config["source"]) / path).read_bytes()
            baseline = (fixture / "dataset" / path).read_bytes()
            assert digest(actual) == digest(baseline)
            additional_media.append(path)
    embeddings = [r for r in work.values() if r["capability"] == "image-embedding"]
    norm_errors = []
    for record in embeddings:
        aid = record["output"]["artifacts"][0]["artifact_ref"]
        data = (root / "precheck" / artifacts[aid]).read_bytes()
        assert digest(data) == aid.split(":")[-1] and len(data) == 768 * 4
        vector = struct.unpack("<768f", data)
        assert all(math.isfinite(v) for v in vector)
        norm_errors.append(abs(math.sqrt(sum(v * v for v in vector)) - 1))
    frame_positions = defaultdict(list)
    for record in work.values():
        if record["capability"] == "video-frame" and record["status"] == "succeeded":
            frame_positions[subject(record)].append(record["output"]["value"]["decoded_time_seconds"])
    duplicate_pts = [str(path) for path, positions in frame_positions.items() if len(positions) != len(set(positions))]
    times = {}
    for cap in sorted({r["capability"] for r in rows}):
        a = [r for r in attempts if work[r["work_id"]]["capability"] == cap and r["finished_at"]]
        if a:
            start = min(r["started_at"] for r in a)
            end = max(r["finished_at"] for r in a)
            times[cap] = {"first_attempt": start, "last_finished": end,
                          "wall_span_seconds": (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds()}
    gpx_with_tracks = sum(r["capability"] == "gpx-location-candidate" and bool(source_paths(r)) for r in work.values())
    metrics = {
        "run_ref": config["run_ref"], "result_ref": config["result_ref"], "result_file_sha256": digest(raw),
        "run_state": run["state"], "run_created_at": run["created_at"], "run_updated_at": run["updated_at"],
        "source": {"accounted": len(scope), "scope_condition": counted(s["scope"] + "/" + s["condition"] for s in scope.values()),
                   "manifest_media": len(media), "hash_mismatches": mismatches,
                   "additional_media_hash_matched_to_package": additional_media,
                   "checksum_manifest_sha256": config["fixture_manifest_sha256"]},
        "work": {"capability_status": counted(r["capability"] + "/" + r["status"] for r in rows),
                 "attempts": sum(r["attempt_count"] for r in rows), "phases": times,
                 "gpx_work_with_track_dependencies": gpx_with_tracks,
                 "embedding_encoder_identity": run_config["embedding_encoder_identity"], "entry_evidence": len(entries),
                 "embedding_artifacts_verified": len(embeddings), "embedding_max_norm_error": max(norm_errors),
                 "videos_with_prepared_frames": len(frame_positions), "duplicate_pts_video_paths": duplicate_pts},
        "compression": compression_replay(work, artifacts, root / "precheck"),
        "geo_selection": geo_replay(work),
        "geo": {"outcome": geo["outcome"], "logical_queries": geo["effects"]["logical_queries"],
                "provider_requests": geo["effects"]["provider_requests"], "billable_units": geo["effects"]["billable_units"],
                "attempts": counted("/".join(a[k] for k in ("provider", "operation", "status")) for a in geo["attempts"]),
                "errors": counted(a.get("error_code", "") + "/" + a.get("error_message", "") for a in geo["attempts"] if a.get("error_code")),
                "request_max_places": geo_request.get("max_places"),
                "components": counted(c["operation"] + "/" + c["status"] for c in geo["components"])},
        "google_payload_probe": google_payload_probe(),
        "plan": {"work_ref": plan["work_ref"], "revision": plan["revision"], "state": plan["state"],
                 "candidate_identity": plan["candidate_identity"], "groups": len(candidate["groups"]),
                 "grouped_media": len(assigned), "other_outcome_counts": [len(o["members"]["source_item_refs"]) for o in candidate["other_outcomes"]],
                 "full_partition_verified": True, "sealed_plans": sealed_plans,
                 "preview_sha256": digest(preview_raw), "preview_embedded_images_valid": len(parser.images),
                 "preview_matches_exact_candidate": True, "organization_preferences": json.loads(plan["organization_preferences_json"])},
        "live_work_at_audit": {k: live_plan[k] for k in ("work_ref", "state", "revision", "candidate_identity", "updated_at")},
        "trajectory": trajectory(config, sealed),
    }
    assert not mismatches
    assert metrics["geo_selection"]["logical_queries"] == metrics["geo"]["logical_queries"]
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
