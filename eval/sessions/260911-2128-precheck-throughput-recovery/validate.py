"""Joint acceptance: values, real frames, reuse, source safety and installed bytes."""

from __future__ import annotations

from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import time
from zipfile import ZipFile

from PIL import Image, ImageChops, ImageStat

from run import BASELINE, ROOT, SESSION, SOURCE, digest, write_json


OUTPUTS = SESSION / "outputs"


def read(path):
    return json.loads(path.read_text())


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def series(prefix):
    return [
        read(OUTPUTS / f"{prefix}-{index}/fresh-metrics.json") for index in (1, 2, 3)
    ]


def main():
    old_metadata = read(BASELINE / "outputs/metadata-producer/fresh-observations.json")
    for case in ("metadata", "metadata-final"):
        assert read(OUTPUTS / case / "fresh-observations.json") == old_metadata
        assert read(OUTPUTS / case / "reuse-observations.json") == old_metadata
    metadata = read(OUTPUTS / "metadata-final/fresh-metrics.json")
    metadata_reuse = read(OUTPUTS / "metadata-final/reuse-metrics.json")
    assert metadata["requested"] == metadata["success"] == 2134
    assert metadata["seconds"] <= 35 and metadata_reuse["seconds"] <= 8
    assert metadata_reuse["success"] == metadata_reuse["reused"] == 2134
    assert all(call["subjects"] == 0 for call in metadata_reuse["exif_calls"])

    legacy_exif, current_exif = series("exif-legacy"), series("exif-current")
    old_raw = read(BASELINE / "outputs/exif-kernel-legacy-1/raw-values.json")
    for kind in ("legacy", "current"):
        for index in (1, 2, 3):
            assert read(OUTPUTS / f"exif-{kind}-{index}/raw-values.json") == old_raw
    legacy_exif_median = statistics.median(row["seconds"] for row in legacy_exif)
    current_exif_median = statistics.median(row["seconds"] for row in current_exif)
    assert current_exif_median <= 4 and current_exif_median <= legacy_exif_median * 1.2

    common_metrics = series("video-common")
    common_median = statistics.median(row["seconds"] for row in common_metrics)
    assert common_median <= 35 and common_median <= 31.800127 * 1.1
    assert all(row["success"] == row["requested"] == 843 for row in common_metrics)
    legacy_frames = read(BASELINE / "outputs/video-common-legacy-1/frames.json")
    common_frames = read(OUTPUTS / "video-common-1/frames.json")
    errors = []
    image_digests = {}
    positions = set()
    for left, right in zip(legacy_frames, common_frames, strict=True):
        assert (left["path"], left["sample"]) == (right["path"], right["sample"])
        assert (
            abs(right["decoded_time_seconds"] - right["requested_seconds"])
            <= right["time_base_seconds"]
        )
        with Image.open(left["output"]) as a, Image.open(right["output"]) as b:
            a.load()
            b.load()
            assert a.size == b.size
            aa = a.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
            bb = b.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
            mae = sum(ImageStat.Stat(ImageChops.difference(aa, bb)).mean) / 3
            errors.append(dict(path=left["path"], sample=left["sample"], mae=mae))
        key = right["path"], right["decoded_time_seconds"]
        positions.add(key)
        image_digests[key] = sha(Path(right["output"]))
    assert len(positions) == 843
    # Same target PTS plus a lower pixel error than the accepted old pair.
    assert max(row["mae"] for row in errors) <= 1.511
    write_json(
        OUTPUTS / "common-frame-comparison.json",
        sorted(errors, key=lambda row: row["mae"], reverse=True),
    )
    for index in (2, 3):
        rows = read(OUTPUTS / f"video-common-{index}/frames.json")
        assert {(row["path"], row["decoded_time_seconds"]) for row in rows} == positions
        assert all(
            sha(Path(row["output"]))
            == image_digests[row["path"], row["decoded_time_seconds"]]
            for row in rows
        )

    video = read(OUTPUTS / "video/fresh-metrics.json")
    video_reuse = read(OUTPUTS / "video/reuse-metrics.json")
    assert video["requested_videos"] == 283 and video["successful_videos"] == 282
    assert video["probe_failures"] == 1 and video["returned_frame_failures"] == 0
    assert video["distinct_frames"] == 843 and video["frame_work_status"] == {
        "succeeded": 846
    }
    assert video["seconds"] <= 30 and video_reuse["seconds"] <= 10
    assert video_reuse["reused_frames"] == 843
    assert video_reuse["decoder_opens"] == video_reuse["decoder_frame_requests"] == 0
    rows = read(OUTPUTS / "video/fresh-frames.json")
    assert {
        (row["path"], row["value"]["value"]["decoded_time_seconds"]) for row in rows
    } == positions
    assert all(
        sha(Path(row["output"]))
        == image_digests[row["path"], row["value"]["value"]["decoded_time_seconds"]]
        for row in rows
    )

    from mediasense.precheck import (
        AccountingStore,
        ArtifactStore,
        BundleCandidateProducer,
        WorkStore,
    )
    from mediasense.precheck._orchestrator import (
        PrecheckExecutionConfig,
        _initial_evidence_media,
    )

    database = OUTPUTS / "video/workspace/work.sqlite3"
    work, artifacts = WorkStore(database), ArtifactStore(database)
    sheets = 0
    for record in work.iter_run_work(video["run_id"], capability="video-contact-sheet"):
        for artifact in artifacts.artifacts_for_work(record.work_id, verify=False):
            assert sha(artifact.path) == artifact.digest
            with Image.open(artifact.path) as image:
                image.load()
            sheets += 1
    assert sheets == 282

    database = OUTPUTS / "metadata-final/workspace/work.sqlite3"
    work, accounting = WorkStore(database), AccountingStore(database)
    requested = {row["path"] for row in read(BASELINE / "outputs/inputs.json")}
    start = time.perf_counter()
    bundles = tuple(
        outcome
        for outcome in BundleCandidateProducer(database).iter_produce(
            metadata["run_id"],
            work.iter_run_work_ids(metadata["run_id"], capability="source-metadata"),
        )
        if outcome.candidate is not None
        and any(path.as_posix() in requested for path in outcome.candidate.members)
    )
    media = tuple(
        item
        for item in accounting.iter_run_items(metadata["run_id"])
        if item.relative_path.as_posix() in requested
    )
    selected, _ = _initial_evidence_media(media, bundles, PrecheckExecutionConfig())
    selection_seconds = time.perf_counter() - start
    grouping_path = OUTPUTS / "metadata-final/grouping-metrics.json"
    if not grouping_path.exists():
        write_json(
            grouping_path,
            {
                "run_id": metadata["run_id"],
                "seconds": selection_seconds,
                "bundles": len(bundles),
                "origin": "first joint validation",
            },
        )
    grouping = read(grouping_path)
    assert grouping["run_id"] == metadata["run_id"] and grouping["bundles"] == len(
        bundles
    )
    selected_paths = {item.relative_path.as_posix() for item in selected}
    assert selected_paths == set(
        read(BASELINE / "outputs/metadata-producer/selection.json")
    )
    write_json(OUTPUTS / "selection.json", sorted(selected_paths))

    spec = importlib.util.spec_from_file_location(
        "baseline_inventory", BASELINE / "run.py"
    )
    recipe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recipe)
    state = recipe.source_state(SOURCE)
    assert state == read(BASELINE / "outputs/source-state-before.json")
    write_json(OUTPUTS / "source-state-after.json", state)
    baseline_inventory = read(BASELINE / "metrics/inventory.json")
    assert (
        sha(BASELINE / "outputs/source-state-before.json")
        == baseline_inventory["source_state_sha256"]
    )

    installed = read(OUTPUTS / "installed-smoke-final/metrics.json")
    assert installed["public_frames"] == 5 and installed["public_contact_sheets"] == 2
    assert installed["source_unchanged"] and installed["old_result_bytes_unchanged"]
    assert installed["network_attempts"] == []
    wheel = OUTPUTS / "wheel-validated/mediasense-0.10.0-py3-none-any.whl"
    with ZipFile(wheel) as package:
        for name in package.namelist():
            if not name.startswith("mediasense/"):
                continue
            assert package.read(name) == (ROOT / "src" / name).read_bytes(), name
    for packaged in (
        ROOT / "src/mediasense/_resources/contracts/precheck-read.tool.json",
        ROOT
        / "src/mediasense/_resources/skills/mediasense-precheck/references/precheck-read.tool.json",
    ):
        assert (
            packaged.read_bytes()
            == (
                ROOT / "docs/spec/contract/precheck-read/precheck-read.tool.json"
            ).read_bytes()
        )

    measured = (
        legacy_exif
        + current_exif
        + common_metrics
        + [metadata, metadata_reuse, video, video_reuse]
    )
    assert all(row["network_denials"] == [] for row in measured)
    assert max(row["peak_rss_bytes"] for row in common_metrics) <= 1.25 * 1024**3
    summary = dict(
        acceptance="passed",
        metadata=metadata,
        metadata_reuse=metadata_reuse,
        exif=dict(
            current_seconds=[row["seconds"] for row in current_exif],
            legacy_four_lane_seconds=[row["seconds"] for row in legacy_exif],
            current_median=current_exif_median,
            legacy_four_lane_median=legacy_exif_median,
            ratio=current_exif_median / legacy_exif_median,
            raw_values_equal=True,
        ),
        video_common=dict(
            seconds=[row["seconds"] for row in common_metrics],
            median=common_median,
            images=843,
            dimensions_equal=True,
            real_positions_match=True,
            pixel_mae_median=statistics.median(row["mae"] for row in errors),
            pixel_mae_max=max(row["mae"] for row in errors),
        ),
        video=video,
        video_reuse=video_reuse,
        validation=dict(
            source_files_unchanged=len(state),
            manifest_media_unchanged=2134,
            source_state_canonical_sha256=digest(state),
            source_snapshot_file_sha256=sha(OUTPUTS / "source-state-after.json"),
            metadata_observations_equal=True,
            default_and_common_frame_bytes_equal=True,
            decoded_contact_sheets=sheets,
            selected_paths_equal=True,
            selected_sources=len(selected),
            selected_kinds=dict(Counter(item.kind for item in selected)),
            bundles=len(bundles),
            grouping_selection_seconds=grouping["seconds"],
            grouping_recheck_seconds=selection_seconds,
            selected_video_frames=sum(row["path"] in selected_paths for row in rows),
        ),
        installed=installed,
        wheel_sha256=sha(wheel),
        code_scope="working tree candidate after b3aa696; every packaged MediaSense file matches source",
        baseline_recipe_sha256={
            name: sha(BASELINE / name)
            for name in ("config.json", "run.py", "worker.py", "validate.py")
        },
        limits=[
            "local M5 Pro/48 GiB, caches not cleared, machine not exclusive",
            "proxy fixture and three short native HEVC clips, not original long-video/RAW/storage certification",
            "memory claims are estimates; time/cancel checks are cooperative between decode steps",
            "source and isolated wheel only; the live global Host is not switched",
        ],
    )
    write_json(SESSION / "metrics/combined.json", summary)
    print(
        json.dumps(
            {
                "acceptance": summary["acceptance"],
                "exif": summary["exif"],
                "video_common": summary["video_common"],
                "validation": summary["validation"],
                "wheel_sha256": summary["wheel_sha256"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
