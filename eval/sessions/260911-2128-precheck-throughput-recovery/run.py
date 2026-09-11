"""One offline recovery measurement per process, with real production adapters.

Examples: python run.py metadata --case metadata
          python run.py metadata --case metadata --reuse
          <legacy python> run.py exif-legacy --case exif-legacy-1
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from queue import SimpleQueue
import resource
import sys
from threading import Lock
import time
from unittest.mock import patch


SESSION = Path(__file__).resolve().parent
ROOT = SESSION.parents[2]
CONFIG = json.loads((SESSION / "config.json").read_text())
BASELINE = SESSION.parent / CONFIG["baseline_session"]
SOURCE = Path(CONFIG["source_root"])
sys.path.insert(0, str(ROOT / "src"))
PROCESS_STARTS = Counter()
NETWORK_DENIALS = []


def audit(event, args):
    if event == "subprocess.Popen":
        PROCESS_STARTS[Path(os.fsdecode(args[0])).name] += 1
    elif event == "socket.connect":
        NETWORK_DENIALS.append(event)
        raise RuntimeError("This evaluation permits no network connections")


sys.addaudithook(audit)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def baseline_recipe():
    spec = importlib.util.spec_from_file_location(
        "original_recipe", BASELINE / "worker.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inputs(args, *, healthy=False, video=False):
    rows = json.loads((BASELINE / "outputs/inputs.json").read_text())
    if healthy:
        rows = [row for row in rows if row["transform"] != "invalid_truncated_fixture"]
    if video:
        rows = [row for row in rows if row["media_type"] == "video"]
    return rows if args.limit is None else rows[: args.limit]


def exif_kernel(args):
    recipe = baseline_recipe()
    rows = inputs(args, healthy=True)
    paths = [str(SOURCE / row["path"]) for row in rows]
    batches = [
        paths[i : i + CONFIG["metadata_batch_size"]]
        for i in range(0, len(paths), CONFIG["metadata_batch_size"])
    ]
    legacy = args.mode == "exif-legacy"
    if legacy:
        extract = recipe.legacy_exif_function()
    else:
        from mediasense.precheck._exiftool import StayOpenExifTool
    start = time.perf_counter()
    batch_seconds = []
    with ExitStack() as stack:
        lanes = SimpleQueue()
        if not legacy:
            for _ in range(CONFIG["exif_lanes"]):
                runner = StayOpenExifTool()
                stack.callback(runner.close)
                lanes.put(runner)
            runner(("exiftool", "-ver"))

        def batch_read(batch):
            tick = time.perf_counter()
            if legacy:
                result = extract(batch, recipe.TAGS)
                batch_seconds.append(time.perf_counter() - tick)
                return result
            adapter = lanes.get()
            try:
                completed = adapter(
                    (
                        "exiftool",
                        "-j",
                        "-G",
                        "-n",
                        "-api",
                        "largefilesupport=1",
                        "-api",
                        "QuickTimeUTC=0",
                        *("-" + tag for tag in recipe.TAGS),
                        "--",
                        *batch,
                    )
                )
                if completed.returncode:
                    raise RuntimeError(completed.stderr)
                return json.loads(completed.stdout)
            finally:
                batch_seconds.append(time.perf_counter() - tick)
                lanes.put(adapter)

        with ThreadPoolExecutor(max_workers=CONFIG["exif_lanes"]) as pool:
            values = [
                value for batch in pool.map(batch_read, batches) for value in batch
            ]
        extracted_seconds = time.perf_counter() - start
    seconds = time.perf_counter() - start
    values.sort(key=lambda row: row["SourceFile"])
    write_json(args.directory / "raw-values.json", values)
    return dict(
        seconds=seconds,
        requested=len(paths),
        success=len(values),
        values_sha256=digest(values),
        lanes=CONFIG["exif_lanes"],
        tag_count=len(recipe.TAGS),
        batch_seconds=batch_seconds,
        close_seconds=seconds - extracted_seconds,
    )


class LocalStageControl:
    """Local-stage timings exclude public Run/Geo; installed Host is tested separately."""

    def current_state(self, _run_ref):
        return "running"


def setup(args):
    from mediasense.precheck import AccountingStore
    from mediasense.precheck._orchestrator import (
        PrecheckExecutionConfig,
        PrecheckOrchestrator,
    )
    from mediasense.precheck.resources import BoundedWorkExecutor

    database = args.directory / "workspace/work.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("benchmark-hk")
    start = time.perf_counter()
    run_id = accounting.start_or_resume_run("benchmark-hk", SOURCE)
    accounting.process_run(run_id)
    discovery_seconds = time.perf_counter() - start
    config = PrecheckExecutionConfig().resolve_resources(
        source_storage="local",
        source_storage_evidence="verified_baseline_internal_Apple_SSD",
    )
    executor = BoundedWorkExecutor(config.resource_budget)
    return (
        database,
        accounting,
        run_id,
        discovery_seconds,
        config,
        executor,
        PrecheckOrchestrator(database, LocalStageControl()),
    )


def metadata(args):
    from mediasense.precheck._exiftool import StayOpenExifTool
    from mediasense.precheck import WorkStore

    database, accounting, run_id, scan_seconds, config, executor, orchestrator = setup(
        args
    )
    requested = {row["path"] for row in inputs(args)}
    media = tuple(
        item
        for item in accounting.iter_run_items(run_id)
        if item.relative_path.as_posix() in requested
    )
    calls = []
    lock = Lock()
    original = StayOpenExifTool.__call__

    def observed(adapter, command):
        start = time.perf_counter()
        result = original(adapter, command)
        with lock:
            calls.append(
                dict(
                    seconds=time.perf_counter() - start,
                    subjects=len(command) - command.index("--") - 1
                    if "--" in command
                    else 0,
                    returncode=result.returncode,
                )
            )
        return result

    start = time.perf_counter()
    with patch.object(StayOpenExifTool, "__call__", observed):
        orchestrator._metadata("local-stage", run_id, media, config, executor)
    seconds = time.perf_counter() - start
    work = WorkStore(database)
    records = tuple(work.iter_run_work(run_id, capability="source-metadata"))
    observations = {
        next(
            d.value
            for d in record.spec.dependencies
            if d.key == "subject_relative_path"
        ): record.output
        for record in records
    }
    prefix = "reuse" if args.reuse else "fresh"
    write_json(args.directory / f"{prefix}-observations.json", observations)
    return dict(
        seconds=seconds,
        discovery_seconds=scan_seconds,
        requested=len(media),
        success=sum(record.status.value == "succeeded" for record in records),
        reused=sum(
            not any(
                attempt.run_id == run_id
                for attempt in work.get_attempts(record.work_id)
            )
            for record in records
        ),
        run_id=run_id,
        exif_calls=calls,
        resource_budget=asdict(executor.budget),
        resource_peak_claims=asdict(executor.admission.peak_usage()),
    )


def video_common(args):
    from PIL import Image
    from mediasense.precheck._video_decoder import PyAVVideoDecoder

    probes = json.loads((BASELINE / "outputs/video-probes/probes.json").read_text())
    probes = [row for row in probes if "error" not in row]
    if args.limit is not None:
        probes = probes[: args.limit]
    decoder = PyAVVideoDecoder()
    values = []
    (args.directory / "frames").mkdir(exist_ok=True)
    start = time.perf_counter()
    for number, probe in enumerate(probes):
        with decoder.open(
            SOURCE / probe["path"],
            threads=CONFIG["ffmpeg_threads"],
            should_continue=lambda: True,
        ) as session:
            for ordinal, sample in enumerate(probe["samples"]):
                # Each API receives the correct target for the same known frame
                # index. The baseline FFmpeg offset included an early seek bias.
                target_seconds = sample["frame_index"] / probe["fps"]
                frame = session.frame_at(
                    target_seconds,
                    max_edge=min(
                        CONFIG["image_max_edge"], max(probe["width"], probe["height"])
                    ),
                )
                target = (
                    args.directory / "frames" / f"{probe['index']:05d}-{ordinal}.jpg"
                )
                with frame.image as image:
                    image.save(target, format="JPEG", quality=CONFIG["jpeg_quality"])
                with Image.open(target) as image:
                    image.load()
                    size = list(image.size)
                values.append(
                    dict(
                        path=probe["path"],
                        sample=sample,
                        requested_seconds=target_seconds,
                        decoded_time_seconds=frame.decoded_time_seconds,
                        time_base_seconds=frame.time_base_seconds,
                        output=str(target),
                        size=size,
                        success=True,
                    )
                )
        if number % 40 == 0:
            print(f"decoded common video {number + 1}/{len(probes)}", flush=True)
    seconds = time.perf_counter() - start
    write_json(args.directory / "frames.json", values)
    return dict(
        seconds=seconds,
        requested=len(values),
        success=len(values),
        videos=len(probes),
        decoder=decoder.identity,
        codec_threads=CONFIG["ffmpeg_threads"],
        workers=1,
    )


def video(args):
    from mediasense.precheck._video_decoder import PyAVVideoDecoder, _PyAVSession
    from mediasense.precheck import WorkStore
    from mediasense.precheck.video import (
        VideoProbeProducer,
        VideoFrameProducer,
        ContactSheetProducer,
    )

    database, accounting, run_id, scan_seconds, config, executor, orchestrator = setup(
        args
    )
    requested = {row["path"] for row in inputs(args, video=True)}
    media = tuple(
        item
        for item in accounting.iter_run_items(run_id)
        if item.relative_path.as_posix() in requested
    )
    timings = {"probe": [], "frames": [], "sheets": []}
    opens = []
    decode_calls = []
    original_open = PyAVVideoDecoder.open
    original_decode = _PyAVSession.frame_at

    def observed_open(decoder, path, **kwargs):
        opens.append(str(path))
        return original_open(decoder, path, **kwargs)

    def observed_decode(session, target, **kwargs):
        decode_calls.append(target)
        return original_decode(session, target, **kwargs)

    def observe(kind, original):
        def measured(producer, *values, **options):
            start = time.perf_counter()
            try:
                return original(producer, *values, **options)
            finally:
                timings[kind].append((start, time.perf_counter()))

        return measured

    start = time.perf_counter()
    with ExitStack() as stack:
        stack.enter_context(patch.object(PyAVVideoDecoder, "open", observed_open))
        stack.enter_context(patch.object(_PyAVSession, "frame_at", observed_decode))
        for cls, method, kind in (
            (VideoProbeProducer, "produce", "probe"),
            (VideoFrameProducer, "produce_many", "frames"),
            (ContactSheetProducer, "produce", "sheets"),
        ):
            stack.enter_context(
                patch.object(cls, method, observe(kind, getattr(cls, method)))
            )
        probes, frames, sheets = orchestrator._video(
            "local-stage", run_id, media, config, executor
        )
    seconds = time.perf_counter() - start
    values = []
    for frame in frames:
        path = next(
            d.value
            for d in frame.work.spec.dependencies
            if d.key == "subject_relative_path"
        )
        values.append(
            dict(
                path=path,
                work_id=frame.work.work_id,
                status=frame.work.status.value,
                reused=frame.reused,
                output=str(frame.artifact.path) if frame.artifact else None,
                value=frame.work.output,
                error=frame.work.last_failure_message,
            )
        )
    suffix = "reuse" if args.reuse else "fresh"
    write_json(args.directory / f"{suffix}-frames.json", values)
    write_json(
        args.directory / f"{suffix}-probes.json",
        {
            str(path): dict(
                status=probe.work.status.value,
                error=probe.work.last_failure_message,
                probe=asdict(probe.probe) if probe.probe else None,
                reused=probe.reused,
            )
            for path, probe in probes.items()
        },
    )
    frame_work = tuple(
        WorkStore(database).iter_run_work(run_id, capability="video-frame")
    )
    return dict(
        seconds=seconds,
        discovery_seconds=scan_seconds,
        requested_videos=len(media),
        successful_videos=sum(probe.probe is not None for probe in probes.values()),
        probe_failures=sum(probe.probe is None for probe in probes.values()),
        distinct_frames=sum(frame.work.status.value == "succeeded" for frame in frames),
        frame_work_status=dict(Counter(work.status.value for work in frame_work)),
        returned_frame_failures=sum(
            frame.work.status.value != "succeeded" for frame in frames
        ),
        frame_work_count=len(frame_work),
        reused_frames=sum(frame.reused for frame in frames),
        contact_sheets=sum(sheet.work.status.value == "succeeded" for sheet in sheets),
        decoder_opens=len(opens),
        decoder_frame_requests=len(decode_calls),
        run_id=run_id,
        phase_wall_seconds={
            key: max(end for _, end in values) - min(start for start, _ in values)
            for key, values in timings.items()
            if values
        },
        resource_budget=asdict(executor.budget),
        resource_peak_claims=asdict(executor.admission.peak_usage()),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=["metadata", "exif-current", "exif-legacy", "video-common", "video"],
    )
    parser.add_argument("--case", required=True)
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    args.directory = SESSION / "outputs" / args.case
    args.directory.mkdir(parents=True, exist_ok=True)
    suffix = "reuse" if args.reuse else "fresh"
    target = args.directory / f"{suffix}-metrics.json"
    if target.exists():
        raise SystemExit(f"refusing to overwrite measurement: {target}")
    route = {"metadata": metadata, "video-common": video_common, "video": video}.get(
        args.mode, exif_kernel
    )
    result = route(args)
    result.update(
        mode=args.mode,
        case=args.case,
        reuse=args.reuse,
        python=sys.version,
        peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        process_starts=dict(PROCESS_STARTS),
        network_denials=NETWORK_DENIALS,
        product_fingerprint=digest(
            {
                str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "src/mediasense/precheck").glob("*.py"))
            }
        ),
    )
    write_json(target, result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
