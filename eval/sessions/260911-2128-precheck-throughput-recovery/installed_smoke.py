"""Exercise a built wheel through its real Host, public Run and public Read.

Run with the isolated wheel's Python. No checkout imports, model, or Geo calls.
Synthetic sources are created before the check and stay read-only during it.
"""

from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sqlite3
import sys
import time


SESSION = Path(__file__).resolve().parent
DIRECTORY = SESSION / "outputs/installed-smoke"
NETWORK = []
PROCESSES = Counter()


def audit(event, args):
    if event == "socket.connect":
        NETWORK.append(event)
        raise RuntimeError("Installed smoke permits no network connections")
    if event == "subprocess.Popen":
        PROCESSES[Path(os.fsdecode(args[0])).name] += 1


sys.addaudithook(audit)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def source_state(source):
    return {
        path.name: [
            path.stat().st_size,
            path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        ]
        for path in sorted(source.iterdir())
    }


def make_video(path, times):
    import av
    from PIL import Image

    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=10)
        stream.width, stream.height = 96, 64
        stream.pix_fmt = "yuv420p"
        stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
        stream.codec_context.options = {"bf": "0", "g": "1"}
        for index, position in enumerate(times):
            with Image.new("RGB", (96, 64), (index * 70, 30, 80)) as image:
                frame = av.VideoFrame.from_image(image)
            frame.pts = round(position * 1000)
            frame.time_base = Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)


def main():
    global DIRECTORY
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="installed-smoke-final")
    args = parser.parse_args()
    if Path(args.case).name != args.case:
        raise ValueError("case must be a single directory name")
    DIRECTORY = SESSION / "outputs" / args.case
    if DIRECTORY.exists():
        raise SystemExit(f"refusing to overwrite installed smoke: {DIRECTORY}")
    source = DIRECTORY / "source"
    source.mkdir(parents=True)
    os.environ["MEDIASENSE_DATA_HOME"] = str(DIRECTORY / "data")
    os.environ["MEDIASENSE_CONFIG_HOME"] = str(DIRECTORY / "config")

    import mediasense
    from PIL import Image
    from mediasense.precheck import ResultStore
    from mediasense.runtime.host import RuntimeHost
    from mediasense.runtime.doctor import diagnose
    from mediasense.runtime.resources import contract_path

    package = Path(mediasense.__file__).resolve()
    assert package.is_relative_to(Path(sys.prefix).resolve()), package
    Image.new("RGB", (96, 64), "purple").save(source / "photo.jpg")
    make_video(source / "sparse.mp4", (0.0, 4.0, 8.0))
    make_video(source / "short.mp4", (0.0, 0.1))
    for index, path in enumerate(sorted(source.iterdir())):
        timestamp = 1_770_000_000 + index * 86_400
        os.utime(path, (timestamp, timestamp))
        path.chmod(0o444)
    before = source_state(source)
    write(DIRECTORY / "source-before.json", before)
    host = RuntimeHost()
    workspace = DIRECTORY / "workspace"
    opened = host.open_dataset(str(source), str(workspace))
    dataset = opened["dataset_ref"]
    transcript = []

    def call(tool, **request):
        request["dataset_ref"] = dataset
        response = host.call_tool(tool, dataset_ref=dataset, request=request)
        transcript.append(dict(tool=tool, request=request, response=response))
        if "error" in response:
            raise AssertionError(response)
        return response

    def wait(run):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            response = call("mediasense.precheck.run", action="status", run_ref=run)
            if response["state"] != "running":
                return response
            time.sleep(0.05)
        raise AssertionError("installed Run did not finish in the smoke allowance")

    def prepare(request_id, prior=None):
        start = time.perf_counter()
        args = {} if prior is None else {"prior_result_ref": prior}
        run = call(
            "mediasense.precheck.run", action="start", request_id=request_id, **args
        )["run_ref"]
        paused = wait(run)
        if prior is not None and paused["state"] == "completed":
            # The existing public contract reuses an unchanged accepted scope.
            # A new confirmation is only needed when that authority is stale.
            return run, paused["result"]["ref"], time.perf_counter() - start
        assert paused["state"] == "paused", paused
        assert paused["reason"]["code"] == "scope_confirmation_required", paused
        call(
            "mediasense.precheck.run",
            action="resume",
            run_ref=run,
            decision={
                "kind": "source_scope",
                "inventory_fingerprint": paused["confirmation"][
                    "inventory_fingerprint"
                ],
                "default_disposition": "include",
                "exceptions": [],
            },
        )
        finished = wait(run)
        assert finished["state"] == "completed", finished
        return run, finished["result"]["ref"], time.perf_counter() - start

    try:
        first_run, result, seconds = prepare("installed-first")
        review = call("mediasense.precheck.read", action="review", result_ref=result)
        pending = {item["evidence_ref"] for item in review["items"]}
        for item in review["items"]:
            for refs in item.get("roles", {}).values():
                pending.update(refs)
        seen = set()
        frame_values = []
        sheet_values = []
        while pending:
            current = sorted(pending - seen)
            pending.clear()
            if not current:
                break
            expanded = call(
                "mediasense.precheck.read",
                action="expand",
                result_ref=result,
                evidence_refs=current,
                include=["anchor_evidence", "prepared_targets"],
            )
            for item in expanded["items"]:
                assert "error" not in item, item
                seen.add(item["evidence_ref"])
                included = item["included"]
                for observation in included["anchor_evidence"]["observations"]:
                    if observation["name"] == "video_frame":
                        frame_values.append(observation)
                    if observation["name"] == "video_contact_sheet":
                        sheet_values.append(observation)
                for target in included.get("prepared_targets", []):
                    if (
                        isinstance(target["target"], dict)
                        and target["target"]["kind"] == "evidence"
                    ):
                        pending.add(target["target"]["ref"])
        assert len(frame_values) == 5, frame_values
        assert len(sheet_values) == 2, sheet_values
        assert any(
            value["value"]["sample_time_seconds"]
            != value["value"]["decoded_time_seconds"]
            for value in frame_values
        )
        assert all(
            value["basis"]["producer"]["identity"] == "builtin-pts-video-frame-v2"
            for value in frame_values
        )
        assert all(
            value["basis"]["position"]["method"] == "presentation_timestamp"
            for value in frame_values
        )
        database = workspace / "precheck/work.sqlite3"
        old_result = ResultStore(database).get(result)
        old_bytes = old_result.path.read_bytes()
        second_run, successor, reuse_seconds = prepare("installed-reuse", result)
        with sqlite3.connect(database) as connection:
            run_ids = dict(
                connection.execute(
                    "SELECT run_ref, accounting_run_id FROM precheck_runs"
                )
            )
            attempts = {
                ref: dict(
                    connection.execute(
                        "SELECT w.capability, count(*) FROM work_attempts a JOIN work_records w USING(work_id) WHERE a.run_id = ? GROUP BY w.capability",
                        (run_ids[ref],),
                    )
                )
                for ref in (first_run, second_run)
            }
        assert attempts[second_run].get("video-frame", 0) == 0, attempts
        assert attempts[second_run].get("source-metadata", 0) == 0, attempts
        assert old_result.path.read_bytes() == old_bytes
        assert source_state(source) == before
        diagnosis = diagnose()
        decoder_check = next(
            check for check in diagnosis["checks"] if check["name"] == "video_decoder"
        )
        assert decoder_check["status"] == "ok"
        schema = Path(contract_path("mediasense.precheck.read"))
        assert (
            schema.read_bytes()
            == (
                SESSION.parents[2]
                / "docs/spec/contract/precheck-read/precheck-read.tool.json"
            ).read_bytes()
        )
        summary = dict(
            installed_package=str(package),
            python=sys.version,
            version=importlib.metadata.version("mediasense"),
            av_version=importlib.metadata.version("av"),
            first_run=first_run,
            second_run=second_run,
            result=result,
            successor=successor,
            first_seconds=seconds,
            reuse_seconds=reuse_seconds,
            public_frames=len(frame_values),
            public_contact_sheets=len(sheet_values),
            actual_positions=[
                value["value"]["decoded_time_seconds"] for value in frame_values
            ],
            work_attempts=attempts,
            source_unchanged=True,
            old_result_bytes_unchanged=True,
            process_starts=dict(PROCESSES),
            network_attempts=NETWORK,
            doctor_decoder=decoder_check,
            result_sha256=hashlib.sha256(old_bytes).hexdigest(),
        )
        write(DIRECTORY / "metrics.json", summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        write(DIRECTORY / "public-transcript.json", transcript)


if __name__ == "__main__":
    main()
