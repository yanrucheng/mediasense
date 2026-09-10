"""Prepare the production-demanded inputs locally using existing producers."""

from dataclasses import asdict
import json
from pathlib import Path
import subprocess

from model_evaluation_business import prepared_identity, verify_business
from model_evaluation_inputs import (
    digest,
    fingerprint,
    fixture_roots,
    outside,
    source_rows,
    write_json,
)
from prepare_input import prepare


def prepare_business_inputs(config: dict, destination: Path) -> dict:
    verify_business(config)
    from mediasense.precheck import (
        AccountingStore,
        BundleCandidateProducer,
        ImageRenditionProducer,
        MetadataProducer,
    )
    from mediasense.precheck._compression_producer import _capture_time, _gps_value
    from mediasense.precheck._orchestrator import (
        PrecheckExecutionConfig,
        _initial_evidence_media,
    )
    from mediasense.precheck.rendition import HIGH_RESOLUTION_RENDITION_PROFILE
    from mediasense.precheck.video import (
        VideoProbeProducer,
        VideoFrameProducer,
        sample_video_times,
    )

    original_root, sources = source_rows(config)
    destination = outside(destination, *fixture_roots(config))
    destination.mkdir(parents=True, exist_ok=False)
    for executable, expected in config["inputs"]["tools"].items():
        args = [executable, "-ver" if executable == "exiftool" else "-version"]
        actual = subprocess.check_output(args, text=True).splitlines()[0]
        if actual != expected:
            raise ValueError(f"Preparation tool version changed: {executable}")
    # The scoped copy excludes package reports, caches, ignore markers and auxiliary files.
    source_root = destination / "source"
    prepare(
        original_root,
        {row["path"]: row["sha256"] for row in sources},
        source_root,
        path_policy="preserve",
    )
    database = destination / "workspace" / "work.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("model-evaluation-hk-v1")
    run_id = accounting.start_or_resume_run("model-evaluation-hk-v1", source_root)
    accounting.process_run(run_id)
    media = tuple(
        item
        for item in accounting.iter_run_items(run_id)
        if item.scope == "source_media"
        and item.kind in {"image", "video"}
        and item.source_revision is not None
    )
    if {item.relative_path.as_posix() for item in media} != {
        row["path"] for row in sources
    }:
        raise ValueError("Production accounting differs from the fixed media allowlist")
    metadata = {}
    producer = MetadataProducer(database)
    try:
        batch_size = config["inputs"]["metadata_batch_size"]
        for start in range(0, len(media), batch_size):
            metadata.update(
                producer.produce_many(
                    run_id,
                    [item.relative_path for item in media[start : start + batch_size]],
                )
            )
            print(
                f"metadata {min(start + batch_size, len(media))}/{len(media)}",
                flush=True,
            )
    finally:
        producer.close()
    bundles = tuple(BundleCandidateProducer(database).iter_produce(run_id, None))
    execution = PrecheckExecutionConfig(
        compression_target=config["inputs"]["compression_target"],
        video_frame_limit=config["inputs"]["video_frame_limit"],
    )
    demanded, selected_work_ids = _initial_evidence_media(media, bundles, execution)
    demanded_paths = {item.relative_path.as_posix() for item in demanded}
    business_sources = {}
    for source in sources:
        record = metadata[Path(source["path"])].work
        time = _capture_time(record)
        business_sources[source["path"]] = {
            **source,
            "capture_time": time.isoformat() if time else None,
            "gps": list(_gps_value(record)) if _gps_value(record) else None,
            "metadata_state": record.status.value,
            "visual_requested": source["path"] in demanded_paths,
        }
    bundle_values = [
        {
            "id": outcome.candidate.candidate_id,
            "representative": outcome.candidate.representative_path.as_posix(),
            "members": [path.as_posix() for path in outcome.candidate.members],
            "boundaries": [
                path.as_posix() for path in outcome.candidate.boundary_paths
            ],
            "qualifications": list(outcome.candidate.qualifications),
            "selected": outcome.work.work_id in selected_work_ids,
        }
        for outcome in bundles
    ]
    rendition = ImageRenditionProducer(database)
    probe_producer = VideoProbeProducer(database)
    frame_producer = VideoFrameProducer(
        database, threads=config["inputs"]["ffmpeg_threads"]
    )
    inputs = []

    def append_input(source, outcome, slot, sample=None):
        row = {
            "id": f"{source['index']:05d}:{slot:02d}",
            "source": source["path"],
            "source_sha256": source["sha256"],
            "kind": source["kind"],
            "sample_time_seconds": sample,
            "state": "failed",
        }
        if outcome.artifact is not None:
            row.update(
                state="ready",
                image_path=str(outcome.artifact.path.resolve()),
                image_sha256=digest(outcome.artifact.path),
            )
        else:
            row["error"] = (
                outcome.work.last_failure_message or outcome.work.status.value
            )
        inputs.append(row)

    by_path = {
        row["path"]: {**row, "index": index} for index, row in enumerate(sources)
    }
    for number, item in enumerate(
        sorted(demanded, key=lambda item: item.relative_path.as_posix()), 1
    ):
        path = item.relative_path
        source = by_path[path.as_posix()]
        if item.kind == "image":
            result = rendition.produce(
                run_id, path, profile=HIGH_RESOLUTION_RENDITION_PROFILE
            )
            append_input(source, result, 0)
        else:
            probe = probe_producer.produce(run_id, path)
            if probe.probe is None:
                inputs.append(
                    {
                        "id": f"{source['index']:05d}:probe",
                        "source": source["path"],
                        "source_sha256": source["sha256"],
                        "kind": "video",
                        "state": "failed",
                        "sample_time_seconds": None,
                        "error": probe.work.last_failure_message
                        or probe.work.status.value,
                    }
                )
                continue
            for slot, sample in enumerate(
                sample_video_times(
                    probe.probe.duration_seconds, max_frames=execution.video_frame_limit
                )
            ):
                frame = frame_producer.produce(run_id, path, probe.work.work_id, sample)
                append_input(source, frame, slot, sample)
        if number % 20 == 0:
            print(f"business visuals {number}/{len(demanded)}", flush=True)
    inputs.sort(key=lambda row: row["id"])
    source_rows(config)
    for row in sources:
        if digest(source_root / row["path"]) != row["sha256"]:
            raise ValueError("Staged source bytes changed during preparation")
    prepared = {
        "source_root": str(source_root.resolve()),
        "source_count": len(sources),
        "source_fingerprint": fingerprint(sources),
        "recipe": config["inputs"],
        "inputs": inputs,
        "business": {"sources": business_sources, "bundles": bundle_values},
        "preparation": {
            "database": str(database.resolve()),
            "run_id": run_id,
            "high_resolution_profile": asdict(HIGH_RESOLUTION_RENDITION_PROFILE),
            "metadata_observations": "workspace Work records; not historical cache",
            "video_pts": "requested seek time; production producer does not expose decoded PTS",
            "remote_calls": 0,
        },
    }
    prepared["input_fingerprint"] = prepared_identity(prepared)
    write_json(destination / "inputs.json", prepared)
    return {
        "source_count": len(sources),
        "bundle_count": len(bundles),
        "visual_sources": len(demanded),
        "ready": sum(row["state"] == "ready" for row in inputs),
        "failed": sum(row["state"] == "failed" for row in inputs),
        "input_fingerprint": prepared["input_fingerprint"],
    }


def validate_business_inputs(config: dict, path: Path) -> dict:
    verify_business(config)
    prepared = json.loads(path.read_text())
    _, sources = source_rows(config)
    if (
        prepared["source_fingerprint"] != fingerprint(sources)
        or prepared["source_count"] != len(sources)
        or prepared["recipe"] != config["inputs"]
        or prepared_identity(prepared) != prepared["input_fingerprint"]
        or prepared["input_fingerprint"] != config["expected_input_fingerprint"]
    ):
        raise ValueError("Business input fingerprint or recipe changed")
    source_map = {row["path"]: row for row in sources}
    if set(source_map) != set(prepared["business"]["sources"]):
        raise ValueError("Missing business source accounting")
    seen = set()
    for row in prepared["inputs"]:
        if (
            row["id"] in seen
            or row["source"] not in source_map
            or row["state"] not in {"ready", "failed"}
        ):
            raise ValueError("Invalid or duplicate business input identity")
        seen.add(row["id"])
        if row["source_sha256"] != source_map[row["source"]]["sha256"]:
            raise ValueError("Input is bound to a different source")
        if (
            row["state"] == "ready"
            and digest(Path(row["image_path"])) != row["image_sha256"]
        ):
            raise ValueError(f"Business raster changed: {row['id']}")
    for source in sources:
        if digest(Path(prepared["source_root"]) / source["path"]) != source["sha256"]:
            raise ValueError("Staged source changed")
    return prepared
