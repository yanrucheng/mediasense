"""One measured route per process; both kernels use the legacy Python runtime."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import resource
import subprocess
import sys
import time


SESSION = Path(__file__).resolve().parent
CONFIG = json.loads((SESSION / "config.json").read_text())
OUTPUTS = SESSION / "outputs"
SOURCE = Path(CONFIG["source_root"])
LEGACY = OUTPUTS / "legacy-source"
CURRENT = OUTPUTS / "mediasense-source" / "src"
PROCESS_STARTS = Counter()
NETWORK_DENIALS = []
TAGS = [
    "EXIF:DateTimeOriginal",
    "EXIF:OffsetTimeOriginal",
    "QuickTime:CreateDate",
    "QuickTime:MediaCreateDate",
    "Composite:GPSLatitude",
    "Composite:GPSLongitude",
    "EXIF:Make",
    "EXIF:Model",
    "EXIF:LensModel",
    "EXIF:FocalLength",
    "EXIF:FNumber",
    "EXIF:ExposureTime",
    "EXIF:ISO",
    "EXIF:Orientation",
    "File:ImageWidth",
    "File:ImageHeight",
    "File:MIMEType",
    "File:FileType",
]


def audit(event, args):
    if event == "subprocess.Popen":
        PROCESS_STARTS[Path(os.fsdecode(args[0])).name] += 1
    elif event == "socket.connect":
        NETWORK_DENIALS.append("socket.connect")
        raise RuntimeError("This benchmark permits no network connections")


sys.addaudithook(audit)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def canonical_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def load_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def inputs(args, *, video=False, healthy=False):
    rows = json.loads((OUTPUTS / "inputs.json").read_text())
    if video:
        rows = [row for row in rows if row["media_type"] == "video"]
    if healthy:
        rows = [row for row in rows if row["transform"] != "invalid_truncated_fixture"]
    if args.limit is not None:
        selected = rows[: args.limit]
        invalid = [
            row for row in rows if row["transform"] == "invalid_truncated_fixture"
        ]
        if invalid and args.limit > 1:
            selected[-1] = invalid[0]
        rows = selected
    return rows


def legacy_exif_function():
    """Compile the exact c90 method without importing Geo/config/model consumers."""
    import exiftool
    import orjson

    source = LEGACY / "src/metadata/metadata_loader.py"
    tree = ast.parse(source.read_text())
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "MetaDataLoader"
    )
    method = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "_get_exif_data"
    )
    method.decorator_list = []
    unit = ast.Module(body=[method], type_ignores=[])
    namespace = {
        "exiftool": exiftool,
        "orjson": orjson,
        "logger": logging.getLogger("legacy-exif"),
        "List": list,
        "Dict": dict,
    }
    exec(compile(ast.fix_missing_locations(unit), str(source), "exec"), namespace)
    return namespace["_get_exif_data"]


def exif_kernel(args):
    rows = inputs(args, healthy=args.mode != "exif-legacy-all")
    paths = [str(SOURCE / row["path"]) for row in rows]
    batches = [
        paths[start : start + CONFIG["metadata_batch_size"]]
        for start in range(0, len(paths), CONFIG["metadata_batch_size"])
    ]
    records = []
    timings = []
    if args.mode.startswith("exif-legacy"):
        extract = legacy_exif_function()
        max_workers = 1 if args.workers == -1 else min(32, (os.cpu_count() or 1) + 4)

        def one(batch):
            start = time.perf_counter()
            result = extract(batch, TAGS)
            timings.append(time.perf_counter() - start)
            return result

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for batch_records in executor.map(one, batches):
                records.extend(batch_records)
        seconds = time.perf_counter() - start
    else:
        adapter = load_file(
            "bench_exiftool", CURRENT / "mediasense/precheck/_exiftool.py"
        )
        runner = adapter.StayOpenExifTool(timeout=120)
        max_workers = 1
        start = time.perf_counter()
        try:
            runner(("exiftool", "-ver"))
            for batch in batches:
                tick = time.perf_counter()
                result = runner(
                    (
                        "exiftool",
                        "-j",
                        "-G",
                        "-n",
                        "-api",
                        "largefilesupport=1",
                        "-api",
                        "QuickTimeUTC=0",
                        *("-" + tag for tag in TAGS),
                        "--",
                        *batch,
                    )
                )
                if result.returncode:
                    raise RuntimeError(result.stderr)
                records.extend(json.loads(result.stdout))
                timings.append(time.perf_counter() - tick)
        finally:
            runner.close()
        seconds = time.perf_counter() - start
    normalized = sorted(
        (row for row in records if row.get("SourceFile")),
        key=lambda row: row["SourceFile"],
    )
    write_json(args.directory / "raw-values.json", normalized)
    return {
        "seconds": seconds,
        "requested": len(paths),
        "success": len(normalized),
        "failures": len(paths) - len(normalized),
        "batch_count": len(batches),
        "batch_seconds": timings,
        "workers": max_workers,
        "tag_count": len(TAGS),
        "values_sha256": canonical_digest(normalized),
    }


def setup_accounting(args):
    sys.path.insert(0, str(CURRENT))
    from mediasense.precheck import AccountingStore

    database = args.directory / "workspace/work.sqlite3"
    tick = time.perf_counter()
    accounting = AccountingStore(database)
    accounting.register_dataset("benchmark-hk")
    run_id = accounting.start_or_resume_run("benchmark-hk", SOURCE)
    accounting.process_run(run_id)
    return database, accounting, run_id, time.perf_counter() - tick


def metadata_producer(args):
    database, accounting, run_id, discovery_seconds = setup_accounting(args)
    from mediasense.precheck import MetadataProducer, BundleCandidateProducer
    from mediasense.precheck._exiftool import StayOpenExifTool
    from mediasense.precheck._orchestrator import (
        PrecheckExecutionConfig,
        _initial_evidence_media,
    )

    rows = inputs(args)
    adapter = StayOpenExifTool()
    calls = []

    def execute(command):
        tick = time.perf_counter()
        result = adapter(command)
        calls.append(
            {
                "seconds": time.perf_counter() - tick,
                "returncode": result.returncode,
                "subjects": len(command) - command.index("--") - 1
                if "--" in command
                else 0,
            }
        )
        return result

    tick = time.perf_counter()
    producer = MetadataProducer(database, command_runner=execute)
    outcomes = {}
    try:
        for start in range(0, len(rows), CONFIG["metadata_batch_size"]):
            batch = rows[start : start + CONFIG["metadata_batch_size"]]
            outcomes.update(
                producer.produce_many(run_id, [Path(row["path"]) for row in batch])
            )
            print(
                f"metadata {min(start + len(batch), len(rows))}/{len(rows)}", flush=True
            )
    finally:
        adapter.close()
    seconds = time.perf_counter() - tick
    status = Counter(outcome.work.status.value for outcome in outcomes.values())
    result = {
        "seconds": seconds,
        "requested": len(rows),
        "success": status.get("succeeded", 0),
        "failures": len(rows) - status.get("succeeded", 0),
        "reused": sum(outcome.reused for outcome in outcomes.values()),
        "discovery_seconds": discovery_seconds,
        "status": dict(status),
        "exif_seconds": sum(call["seconds"] for call in calls),
        "exif_calls": calls,
        "run_id": run_id,
    }
    write_json(
        args.directory
        / ("reuse-observations.json" if args.reuse else "fresh-observations.json"),
        {str(path): outcome.work.output for path, outcome in outcomes.items()},
    )
    if args.limit is None:
        tick = time.perf_counter()
        work_ids = [
            outcome.work.work_id
            for outcome in outcomes.values()
            if outcome.work.status.value == "succeeded"
        ]
        requested = {row["path"] for row in rows}
        bundles = tuple(
            outcome
            for outcome in BundleCandidateProducer(database).iter_produce(
                run_id, work_ids
            )
            if outcome.candidate is not None
            and any(path.as_posix() in requested for path in outcome.candidate.members)
        )
        media = tuple(
            item
            for item in accounting.iter_run_items(run_id)
            if item.relative_path.as_posix() in requested
        )
        selected, _ = _initial_evidence_media(media, bundles, PrecheckExecutionConfig())
        result["bundle_selection_seconds"] = time.perf_counter() - tick
        result["bundles"] = len(bundles)
        result["selected_media"] = len(selected)
        result["selected_types"] = dict(Counter(item.kind for item in selected))
        write_json(
            args.directory / "selection.json",
            [item.relative_path.as_posix() for item in selected],
        )
    return result


def video_probes(args):
    rows = inputs(args, video=True)

    def probe(row):
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,nb_frames,avg_frame_rate,r_frame_rate,codec_name,duration:format=duration",
                "-of",
                "json",
                str(SOURCE / row["path"]),
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        record = {
            "path": row["path"],
            "index": row["index"],
            "transform": row["transform"],
        }
        if completed.returncode:
            return {**record, "error": completed.stderr.strip()}
        data = json.loads(completed.stdout)
        stream = data["streams"][0]
        numerator, denominator = stream["avg_frame_rate"].split("/")
        fps = float(numerator) / float(denominator)
        frame_count = int(stream["nb_frames"])
        indices = sorted({0, frame_count // 2, frame_count - 1})
        # Seek slightly before a target frame's timestamp to avoid rounding past it.
        samples = [
            {"frame_index": index, "seconds": round(max(0, index - 0.25) / fps, 6)}
            for index in indices
        ]
        return {
            **record,
            "fps": fps,
            "frame_count": frame_count,
            "duration": float(data["format"]["duration"]),
            "width": stream["width"],
            "height": stream["height"],
            "codec": stream["codec_name"],
            "samples": samples,
        }

    tick = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        values = list(executor.map(probe, rows))
    seconds = time.perf_counter() - tick
    write_json(args.directory / "probes.json", values)
    return {
        "seconds": seconds,
        "requested": len(rows),
        "success": sum("error" not in row for row in values),
        "failures": sum("error" in row for row in values),
    }


def ffmpeg_command(path, seconds, target, max_edge):
    # Identical options to VideoFrameProducer.produce in the pinned source.
    qscale = max(2, min(31, round((100 - CONFIG["jpeg_quality"]) * 29 / 99 + 2)))
    return [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-ss",
        f"{seconds:.6f}",
        "-i",
        str(path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={max_edge}:{max_edge}:force_original_aspect_ratio=decrease",
        "-q:v",
        str(qscale),
        "-vcodec",
        "mjpeg",
        "-threads",
        str(CONFIG["ffmpeg_threads"]),
        "-f",
        "image2",
        str(target),
    ]


def video_common(args):
    from PIL import Image

    probes = json.loads((OUTPUTS / "video-probes/probes.json").read_text())
    if args.limit is not None:
        probes = probes[: args.limit]
    legacy = args.mode.endswith("legacy")
    if legacy:
        import cv2
    values = []
    (args.directory / "frames").mkdir(exist_ok=True)
    tick = time.perf_counter()
    for number, probe in enumerate(probes):
        if "error" in probe:
            continue
        cap = cv2.VideoCapture(str(SOURCE / probe["path"])) if legacy else None
        max_edge = min(CONFIG["image_max_edge"], max(probe["width"], probe["height"]))
        for ordinal, sample in enumerate(probe["samples"]):
            target = args.directory / "frames" / f"{probe['index']:05d}-{ordinal}.jpg"
            record = {"path": probe["path"], "sample": sample, "output": str(target)}
            start = time.perf_counter()
            try:
                if legacy:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, sample["frame_index"])
                    ok, frame = cap.read()
                    if not ok:
                        raise ValueError("OpenCV read returned false")
                    image = Image.fromarray(
                        cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2RGB)
                    )
                    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                    image.save(target, format="JPEG", quality=CONFIG["jpeg_quality"])
                    image.close()
                else:
                    completed = subprocess.run(
                        ffmpeg_command(
                            SOURCE / probe["path"], sample["seconds"], target, max_edge
                        ),
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    if completed.returncode:
                        raise ValueError(completed.stderr.strip())
                with Image.open(target) as image:
                    image.verify()
                record["success"] = True
            except (ValueError, OSError) as error:
                record.update(success=False, error=str(error))
            record["seconds"] = time.perf_counter() - start
            values.append(record)
        if cap is not None:
            cap.release()
        if number % 20 == 0:
            print(f"common video {number + 1}/{len(probes)}", flush=True)
    seconds = time.perf_counter() - tick
    write_json(args.directory / "frames.json", values)
    return {
        "seconds": seconds,
        "requested": len(values),
        "success": sum(row["success"] for row in values),
        "failures": sum(not row["success"] for row in values),
        "probe_failures_excluded": sum("error" in row for row in probes),
        "video_count": sum("error" not in row for row in probes),
        "opencv_threads": cv2.getNumThreads() if legacy else None,
        "ffmpeg_threads": None if legacy else CONFIG["ffmpeg_threads"],
    }


def video_native_legacy(args):
    import asyncio
    import cv2
    import glob

    sys.path.insert(0, str(LEGACY))
    from src.media_processors.video.video_processor import VideoProcessor

    rows = inputs(args, video=True)
    real_capture = cv2.VideoCapture
    capture_records = []
    active = {}

    class RecordingCapture:
        def __init__(self, path):
            self.inner = real_capture(path)
            self.record = {"path": path, "seeks": [], "reads": 0, "failed_reads": 0}
            capture_records.append(self.record)
            active[path] = self.record

        def __getattr__(self, name):
            return getattr(self.inner, name)

        def set(self, prop, value):
            if prop == cv2.CAP_PROP_POS_FRAMES:
                self.record["seeks"].append(value)
            return self.inner.set(prop, value)

        def read(self):
            value = self.inner.read()
            self.record["reads"] += 1
            self.record["failed_reads"] += not value[0]
            return value

    cv2.VideoCapture = RecordingCapture
    cache_input = args.directory / "cache-home/input"
    cache_input.mkdir(parents=True, exist_ok=True)
    processor = VideoProcessor(str(cache_input))
    values = []

    async def run():
        for number, row in enumerate(rows):
            path = str(SOURCE / row["path"])
            tick = time.perf_counter()
            record = {
                "path": row["path"],
                "transform": row["transform"],
                "legacy_representative": row["is_representative"],
            }
            try:
                frames = await processor.get_frames(path)
                record["frames"] = len(frames)
                record["sizes"] = [list(frame.size) for frame in frames]
                record["success"] = bool(frames)
                for frame in frames:
                    frame.close()
                record["outputs"] = sorted(
                    glob.glob(processor.frame_cache_manager.to_cache_path(path))
                )
            except Exception as error:
                record.update(
                    frames=0, success=False, error=f"{type(error).__name__}: {error}"
                )
            record["seconds"] = time.perf_counter() - tick
            values.append(record)
            if number % 20 == 0:
                print(f"native legacy video {number + 1}/{len(rows)}", flush=True)

    tick = time.perf_counter()
    try:
        asyncio.run(run())
    finally:
        cv2.VideoCapture = real_capture
    seconds = time.perf_counter() - tick
    suffix = "reuse" if args.reuse else "fresh"
    write_json(args.directory / f"{suffix}-videos.json", values)
    write_json(args.directory / f"{suffix}-captures.json", capture_records)
    return {
        "seconds": seconds,
        "requested": len(rows),
        "success": sum(row["success"] for row in values),
        "failures": sum(not row["success"] for row in values),
        "frames": sum(row["frames"] for row in values),
        "opencv_capture_starts": len(capture_records),
        "opencv_reads": sum(row["reads"] for row in capture_records),
        "opencv_failed_reads": sum(row["failed_reads"] for row in capture_records),
        "workers": 1,
        "frame_limit": 20,
        "opencv_threads": cv2.getNumThreads(),
        "cache_hit_videos": len(rows) - len(capture_records),
    }


def video_native_current(args):
    database, _accounting, run_id, discovery_seconds = setup_accounting(args)
    from mediasense.precheck.video import (
        VideoProbeProducer,
        VideoFrameProducer,
        sample_video_times,
    )
    from mediasense.precheck._video_producers import _run_command

    rows = inputs(args, video=True)
    calls = []

    def execute(command):
        tick = time.perf_counter()
        result = _run_command(command)
        calls.append(
            {
                "tool": Path(command[0]).name,
                "seconds": time.perf_counter() - tick,
                "returncode": result.returncode,
                "version": "-version" in command,
            }
        )
        return result

    tick = time.perf_counter()
    probe_producer = VideoProbeProducer(database, command_runner=execute)
    frame_producer = VideoFrameProducer(
        database, command_runner=execute, threads=CONFIG["ffmpeg_threads"]
    )
    probe_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        probes = list(
            executor.map(
                lambda row: probe_producer.produce(run_id, Path(row["path"])), rows
            )
        )
    probe_seconds = time.perf_counter() - probe_start
    tasks = []
    values = {
        row["path"]: {
            "path": row["path"],
            "transform": row["transform"],
            "legacy_representative": row["is_representative"],
            "samples": [],
            "probe_status": probe.work.status.value,
            "probe_reused": probe.reused,
        }
        for row, probe in zip(rows, probes)
    }
    for row, probe in zip(rows, probes):
        if probe.probe is None:
            values[row["path"]]["probe_error"] = probe.work.last_failure_message
            continue
        for sample in sample_video_times(
            probe.probe.duration_seconds, max_frames=CONFIG["video_sample_limit"]
        ):
            tasks.append((row["path"], probe.work.work_id, sample))

    def frame(task):
        path, probe_id, sample = task
        start = time.perf_counter()
        outcome = frame_producer.produce(run_id, Path(path), probe_id, sample)
        record = {
            "time": sample,
            "seconds": time.perf_counter() - start,
            "status": outcome.work.status.value,
            "reused": outcome.reused,
            "error": outcome.work.last_failure_message,
            "output": str(outcome.artifact.path) if outcome.artifact else None,
        }
        return path, record

    frame_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for number, (path, record) in enumerate(executor.map(frame, tasks)):
            values[path]["samples"].append(record)
            if number % 50 == 0:
                print(f"native current frame {number + 1}/{len(tasks)}", flush=True)
    frame_seconds = time.perf_counter() - frame_start
    seconds = time.perf_counter() - tick
    result_rows = list(values.values())
    frames = [sample for row in result_rows for sample in row["samples"]]
    successful_frames = [sample for sample in frames if sample["status"] == "succeeded"]
    failures = [sample for sample in frames if sample["status"] != "succeeded"]
    suffix = "reuse" if args.reuse else "fresh"
    write_json(args.directory / f"{suffix}-videos.json", result_rows)
    return {
        "seconds": seconds,
        "requested": len(rows),
        "success": sum(
            any(sample["status"] == "succeeded" for sample in row["samples"])
            for row in result_rows
        ),
        "failures": sum(
            not any(sample["status"] == "succeeded" for sample in row["samples"])
            for row in result_rows
        ),
        "frames": len(successful_frames),
        "frame_attempts": len(frames),
        "frame_failures": len(failures),
        "probe_failures": sum(probe.probe is None for probe in probes),
        "successful_frames_reused": sum(
            sample["reused"] for sample in successful_frames
        ),
        "workers": args.workers,
        "frame_limit": CONFIG["video_sample_limit"],
        "ffmpeg_threads": CONFIG["ffmpeg_threads"],
        "discovery_seconds": discovery_seconds,
        "probe_seconds": probe_seconds,
        "frame_seconds": frame_seconds,
        "external_calls": dict(Counter(call["tool"] for call in calls)),
        "external_seconds_sum": sum(call["seconds"] for call in calls),
        "version_calls": sum(call["version"] for call in calls),
        "terminal_frame_failures_retained": sum(
            sample["status"] == "terminal_failure" for sample in failures
        ),
        "run_id": run_id,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    args.directory = OUTPUTS / args.case
    args.directory.mkdir(parents=True, exist_ok=True)
    os.nice(10)
    load_before = os.getloadavg()
    start = time.perf_counter()
    if args.mode.startswith("exif-"):
        result = exif_kernel(args)
    elif args.mode == "metadata-producer":
        result = metadata_producer(args)
    elif args.mode == "video-probes":
        result = video_probes(args)
    elif args.mode.startswith("video-common"):
        result = video_common(args)
    elif args.mode == "video-native-legacy":
        result = video_native_legacy(args)
    elif args.mode == "video-native-current":
        result = video_native_current(args)
    else:
        raise ValueError(args.mode)
    result.update(
        case=args.case,
        mode=args.mode,
        reuse=args.reuse,
        python=sys.version,
        process_starts=dict(PROCESS_STARTS),
        network_denials=NETWORK_DENIALS,
        worker_seconds=time.perf_counter() - start,
        peak_self_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
        load_average_before=list(load_before),
        load_average_after=list(os.getloadavg()),
        recipe_sha256={
            name: hashlib.sha256((SESSION / name).read_bytes()).hexdigest()
            for name in ("run.py", "worker.py", "config.json")
        },
    )
    if NETWORK_DENIALS:
        raise RuntimeError("An unexpected network attempt was blocked")
    write_json(args.directory / ("reuse.json" if args.reuse else "fresh.json"), result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
