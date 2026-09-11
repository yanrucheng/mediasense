"""Check result comparability, decoded outputs, failure coverage and source safety."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import statistics
import subprocess

import numpy as np
from PIL import Image

from run import CONFIG, OUTPUTS, SESSION, source_state, write_json


def read(path):
    return json.loads(path.read_text())


def percentile(values, fraction):
    return float(np.quantile(values, fraction)) if values else None


def main():
    state = source_state(Path(CONFIG["source_root"]))
    assert state == read(OUTPUTS / "source-state-before.json")
    exif = [read(path) for path in sorted(OUTPUTS.glob("exif-kernel-*/fresh.json"))]
    assert len(exif) == 6
    assert all(row["success"] == 2133 and row["failures"] == 0 for row in exif)
    assert len({row["values_sha256"] for row in exif}) == 1
    # Compare actual retained values as well as their reported digests.
    raw = [read(path) for path in sorted(OUTPUTS.glob("exif-kernel-*/raw-values.json"))]
    assert all(value == raw[0] for value in raw)
    legacy_common = read(OUTPUTS / "video-common-legacy-1/frames.json")
    current_common = read(OUTPUTS / "video-common-current-1/frames.json")
    assert len(legacy_common) == len(current_common) == 843
    errors = []
    mismatched_shapes = []
    per_frame = []
    for left, right in zip(legacy_common, current_common, strict=True):
        assert left["path"] == right["path"] and left["sample"] == right["sample"]
        assert left["success"] and right["success"]
        with Image.open(left["output"]) as a, Image.open(right["output"]) as b:
            a.load()
            b.load()
            if a.size != b.size:
                mismatched_shapes.append(
                    {"path": left["path"], "legacy": a.size, "current": b.size}
                )
            aa = np.asarray(
                a.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS), dtype=float
            )
            bb = np.asarray(
                b.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS), dtype=float
            )
            mae = float(np.mean(np.abs(aa - bb)))
            errors.append(mae)
            per_frame.append(
                {"path": left["path"], "sample": left["sample"], "mae": mae}
            )
    write_json(
        OUTPUTS / "common-frame-comparison.json",
        sorted(per_frame, key=lambda row: row["mae"], reverse=True),
    )
    probes = {row["path"]: row for row in read(OUTPUTS / "video-probes/probes.json")}
    legacy = read(OUTPUTS / "video-native-legacy/fresh-videos.json")
    current = read(OUTPUTS / "video-native-current/fresh-videos.json")
    assert len(legacy) == len(current) == 283
    by_transform = defaultdict(
        lambda: {
            "videos": 0,
            "legacy_frames": 0,
            "current_frames": 0,
            "current_frame_failures": 0,
        }
    )
    by_path = {row["path"]: row for row in legacy}
    failure_positions = Counter()
    interior_failures = []
    frame_histogram = Counter()
    decoded_native = {"legacy": 0, "current": 0}
    selected_current = set(read(OUTPUTS / "metadata-producer/selection.json"))
    selected = {
        "legacy": {"videos": 0, "frames": 0, "frame_failures": 0},
        "current": {"videos": 0, "frames": 0, "frame_failures": 0},
    }
    for row in current:
        previous = by_path[row["path"]]
        aggregate = by_transform[row["transform"]]
        aggregate["videos"] += 1
        aggregate["legacy_frames"] += previous["frames"]
        successes = [
            sample for sample in row["samples"] if sample["status"] == "succeeded"
        ]
        failures = [
            sample for sample in row["samples"] if sample["status"] != "succeeded"
        ]
        aggregate["current_frames"] += len(successes)
        aggregate["current_frame_failures"] += len(failures)
        frame_histogram[len(successes)] += 1
        for sample in failures:
            duration = probes[row["path"]]["duration"]
            location = (
                "duration_endpoint"
                if abs(sample["time"] - duration) < 0.002
                else "inside_duration"
            )
            failure_positions[location] += 1
            if location == "inside_duration":
                interior_failures.append((row["path"], sample["time"]))
        for path in previous.get("outputs", []):
            with Image.open(path) as image:
                image.load()
            decoded_native["legacy"] += 1
        for sample in successes:
            with Image.open(sample["output"]) as image:
                image.load()
            decoded_native["current"] += 1
        if previous["legacy_representative"]:
            selected["legacy"]["videos"] += 1
            selected["legacy"]["frames"] += previous["frames"]
        if row["path"] in selected_current:
            selected["current"]["videos"] += 1
            selected["current"]["frames"] += len(successes)
            selected["current"]["frame_failures"] += len(failures)
    native_summaries = {}
    for variant in ("legacy", "current"):
        fresh = read(OUTPUTS / f"video-native-{variant}/fresh.json")
        reuse = read(OUTPUTS / f"video-native-{variant}/reuse.json")
        assert fresh["frames"] == reuse["frames"] == decoded_native[variant]
        native_summaries[variant] = {
            "fresh_seconds": fresh["seconds"],
            "reuse_seconds": reuse["seconds"],
            "frames": fresh["frames"],
            "successful_videos": fresh["success"],
            "failed_videos": fresh["failures"],
            "frame_failures": fresh.get("frame_failures"),
            "reuse_process_starts": reuse["process_starts"],
            "reuse_opencv_capture_starts": reuse.get("opencv_capture_starts"),
        }
    kernel_medians = {}
    for kind in ("exif-kernel", "video-common"):
        pair = {}
        for variant in ("legacy", "current"):
            values = [
                read(path)["seconds"]
                for path in OUTPUTS.glob(f"{kind}-{variant}-*/fresh.json")
            ]
            assert len(values) == 3
            pair[variant] = {
                "n": 3,
                "median_seconds": statistics.median(values),
                "min_seconds": min(values),
                "max_seconds": max(values),
            }
        pair["current_over_legacy_seconds"] = (
            pair["current"]["median_seconds"] / pair["legacy"]["median_seconds"]
        )
        kernel_medians[kind] = pair
    diagnostics = []
    for path, requested_time in interior_failures:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=best_effort_timestamp_time,pkt_duration_time",
            "-of",
            "json",
            str(Path(CONFIG["source_root"]) / path),
        ]
        detail = json.loads(subprocess.check_output(command, text=True, timeout=60))
        times = [
            float(frame["best_effort_timestamp_time"]) for frame in detail["frames"]
        ]
        diagnostics.append(
            {
                "path": path,
                "requested_time": requested_time,
                "container_duration": probes[path]["duration"],
                "frame_pts": times,
                "last_frame_pts": max(times),
                "request_after_last_frame_pts": requested_time > max(times),
            }
        )
    write_json(OUTPUTS / "interior-failure-diagnostics.json", diagnostics)
    result = {
        "source_unchanged": True,
        "all_six_exif_results_identical": True,
        "exif_rows_each": 2133,
        "common_frame_pairs": len(errors),
        "common_output_shape_mismatches": mismatched_shapes,
        "common_rgb_64_mae": {
            "median": statistics.median(errors),
            "p95": percentile(errors, 0.95),
            "max": max(errors),
            "over_5": sum(error > 5 for error in errors),
            "qualification": "Resizing/JPEG implementations differ; low pixel error supports frame correspondence, not semantic quality.",
        },
        "kernel_comparisons": kernel_medians,
        "native_sampling": native_summaries,
        "current_frame_failure_positions": dict(failure_positions),
        "interior_failure_diagnostics": diagnostics,
        "all_native_output_images_fully_decoded": decoded_native,
        "current_successful_frame_histogram": dict(sorted(frame_histogram.items())),
        "native_by_transform": dict(by_transform),
        "selection_counts_applied_to_retained_results": selected,
        "selection_timing": "No full pipeline wall-time comparison; selected subset wall time is not inferred from overlapping tasks.",
    }
    write_json(SESSION / "metrics/validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
