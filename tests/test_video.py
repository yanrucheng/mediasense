from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    ArtifactIntegrity,
    ContactSheetProducer,
    ContactSheetProfile,
    EmbeddingProducer,
    EmbeddingProfile,
    PrecheckReadTool,
    ResultStore,
    VideoFrameProducer,
    VideoKeyFrameCandidateProducer,
    VideoProbeProducer,
    WorkStatus,
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


class FakeVideoTools:
    def __init__(self, *, fail_at: set[float] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_at = fail_at or set()

    def __call__(self, command) -> subprocess.CompletedProcess[str]:
        command = tuple(command)
        self.calls.append(command)
        if "-show_entries" in command:
            return subprocess.CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "streams": [
                            {
                                "width": 1920,
                                "height": 1080,
                                "avg_frame_rate": "30/1",
                                "nb_frames": "751",
                            }
                        ],
                        "format": {"duration": "25.0"},
                    }
                ),
                "",
            )
        sample_time = float(command[command.index("-ss") + 1])
        if sample_time in self.fail_at:
            return subprocess.CompletedProcess(command, 1, "", "decode failed")
        Image.new("RGB", (320, 180), (int(sample_time) % 255, 40, 60)).save(
            Path(command[-1]), format="JPEG"
        )
        return subprocess.CompletedProcess(command, 0, "", "")


class FrameColorEncoder:
    identity = "frame-color-test-model@sha256:one"

    def encode_image(self, image_path: Path) -> tuple[float, ...]:
        with Image.open(image_path) as image:
            red, green, blue = image.convert("RGB").getpixel((0, 0))
        return float(red), float(green), float(blue)


def test_probe_frames_and_contact_sheet_have_independent_work_and_artifacts(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    video = source / "clip.mp4"
    video.write_bytes(b"fake video bytes")
    source_before = video.read_bytes()
    run_id = _closed_run(database, source)
    runner = FakeVideoTools(fail_at={10.0})
    probe = VideoProbeProducer(
        database, command_runner=runner, ffprobe_version="ffprobe 8.1"
    ).produce(run_id, Path("clip.mp4"))
    frame_producer = VideoFrameProducer(
        database,
        command_runner=runner,
        ffmpeg_version="ffmpeg 8.1",
        threads=2,
    )
    first = frame_producer.produce(run_id, Path("clip.mp4"), probe.work.work_id, 0.0)
    failed = frame_producer.produce(run_id, Path("clip.mp4"), probe.work.work_id, 10.0)
    last = frame_producer.produce(run_id, Path("clip.mp4"), probe.work.work_id, 25.0)
    sheet = ContactSheetProducer(database).produce(
        run_id,
        Path("clip.mp4"),
        [first.work.work_id, last.work.work_id],
        profile=ContactSheetProfile(columns=2, tile_edge=120),
    )

    assert probe.work.status is WorkStatus.SUCCEEDED
    assert probe.probe is not None and probe.probe.duration_seconds == 25.0
    assert first.work.status is WorkStatus.SUCCEEDED
    assert failed.work.status is WorkStatus.TERMINAL_FAILURE
    assert last.work.status is WorkStatus.SUCCEEDED
    assert sheet.work.status is WorkStatus.SUCCEEDED
    assert sheet.artifact is not None
    assert sheet.artifact.integrity is ArtifactIntegrity.AVAILABLE
    frame_commands = [command for command in runner.calls if "-ss" in command]
    assert all(
        command[command.index("-threads") + 1] == "2" for command in frame_commands
    )
    with Image.open(sheet.artifact.path) as image:
        assert image.size == (240, 120)
    assert video.read_bytes() == source_before

    second_run = _closed_run(database, source)
    reused_probe = VideoProbeProducer(
        database, command_runner=runner, ffprobe_version="ffprobe 8.1"
    ).produce(second_run, Path("clip.mp4"))
    reused_first = frame_producer.produce(
        second_run, Path("clip.mp4"), reused_probe.work.work_id, 0.0
    )
    reused_last = frame_producer.produce(
        second_run, Path("clip.mp4"), reused_probe.work.work_id, 25.0
    )
    reused_sheet = ContactSheetProducer(database).produce(
        second_run,
        Path("clip.mp4"),
        [reused_first.work.work_id, reused_last.work.work_id],
        profile=ContactSheetProfile(columns=2, tile_edge=120),
    )
    assert reused_probe.reused is True
    assert reused_first.reused is True
    assert reused_last.reused is True
    assert reused_sheet.reused is True


def test_video_key_frame_candidate_can_be_the_frontier_without_contact_sheet(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    video = source / "clip.mp4"
    video.write_bytes(b"fake video bytes")
    run_id = _closed_run(database, source)
    runner = FakeVideoTools()
    probe = VideoProbeProducer(
        database, command_runner=runner, ffprobe_version="ffprobe 8.1"
    ).produce(run_id, Path("clip.mp4"))
    frames = tuple(
        VideoFrameProducer(
            database, command_runner=runner, ffmpeg_version="ffmpeg 8.1"
        ).produce(run_id, Path("clip.mp4"), probe.work.work_id, sample_time)
        for sample_time in (0.0, 10.0, 25.0)
    )
    embedding_producer = EmbeddingProducer(database, FrameColorEncoder())
    embeddings = tuple(
        embedding_producer.produce(
            run_id,
            frame.work.work_id,
            profile=EmbeddingProfile(name="frame-color", dimensions=3),
        )
        for frame in frames
    )
    key_frame = VideoKeyFrameCandidateProducer(database).produce(
        run_id,
        Path("clip.mp4"),
        [
            (frame.work.work_id, embedding.work.work_id)
            for frame, embedding in zip(frames, embeddings, strict=True)
        ],
    )

    assert key_frame.work.status is WorkStatus.SUCCEEDED
    assert key_frame.selected_frame_work_id == frames[1].work.work_id
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(
            run_id,
            [],
            video_frame_work_ids=[frame.work.work_id for frame in frames],
            video_key_frame_work_ids=[key_frame.work.work_id],
        )
    )
    reader = PrecheckReadTool(database)
    entry = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "review",
            "result_ref": sealed.result_ref,
        }
    )
    assert len(entry["items"]) == 1
    evidence_ref = entry["items"][0]["evidence_ref"]
    view = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "expand",
            "result_ref": sealed.result_ref,
            "evidence_refs": [evidence_ref],
            "include": ["anchor_evidence"],
        }
    )["items"][0]["included"]["anchor_evidence"]
    assert any(
        item["name"] == "evidence_role" and item["value"]["role"] == "representative"
        for item in view["observations"]
    )


def test_contact_sheet_refuses_incomplete_frame_set(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "clip.mp4").write_bytes(b"fake video bytes")
    run_id = _closed_run(database, source)
    runner = FakeVideoTools(fail_at={10.0})
    probe = VideoProbeProducer(
        database, command_runner=runner, ffprobe_version="ffprobe 8.1"
    ).produce(run_id, Path("clip.mp4"))
    failed = VideoFrameProducer(
        database, command_runner=runner, ffmpeg_version="ffmpeg 8.1"
    ).produce(run_id, Path("clip.mp4"), probe.work.work_id, 10.0)

    try:
        ContactSheetProducer(database).produce(
            run_id, Path("clip.mp4"), [failed.work.work_id]
        )
    except ValueError as error:
        assert "must succeed" in str(error)
    else:
        raise AssertionError("incomplete frame set was accepted")


def test_contact_sheet_is_default_evidence_and_expands_to_frames(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    (source / "clip.mp4").write_bytes(b"fake video bytes")
    run_id = _closed_run(database, source)
    runner = FakeVideoTools()
    probe = VideoProbeProducer(
        database, command_runner=runner, ffprobe_version="ffprobe 8.1"
    ).produce(run_id, Path("clip.mp4"))
    frame_producer = VideoFrameProducer(
        database, command_runner=runner, ffmpeg_version="ffmpeg 8.1"
    )
    first = frame_producer.produce(run_id, Path("clip.mp4"), probe.work.work_id, 0.0)
    last = frame_producer.produce(run_id, Path("clip.mp4"), probe.work.work_id, 25.0)
    sheet = ContactSheetProducer(database).produce(
        run_id, Path("clip.mp4"), [first.work.work_id, last.work.work_id]
    )
    results = ResultStore(database)
    sealed = results.seal(
        results.build_minimal(
            run_id,
            [],
            video_frame_work_ids=[first.work.work_id, last.work.work_id],
            contact_sheet_work_ids=[sheet.work.work_id],
        )
    )
    reader = PrecheckReadTool(database)

    entry = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )
    assert len(entry["items"]) == 1
    sheet_ref = entry["items"][0]["evidence_ref"]
    sheet_view = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "evidence_refs": [sheet_ref],
            "include": ["anchor_evidence"],
        }
    )["items"][0]["included"]["anchor_evidence"]
    assert sheet_view["observations"][0]["name"] == "video_contact_sheet"
    expanded = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "evidence_refs": [sheet_ref],
            "include": ["prepared_targets"],
        }
    )
    frame_refs = [
        item["target"]["ref"]
        for item in expanded["items"][0]["included"]["prepared_targets"]
        if isinstance(item["target"], dict) and item["target"]["kind"] == "evidence"
    ]
    assert len(frame_refs) == 2
    frame_views = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "evidence_refs": frame_refs,
            "include": ["anchor_evidence"],
        }
    )
    assert all(
        item["included"]["anchor_evidence"]["observations"][0]["name"] == "video_frame"
        for item in frame_views["items"]
    )


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg tools are not installed",
)
def test_installed_ffmpeg_probes_and_extracts_without_source_writes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    video = source / "clip.mp4"
    subprocess.run(
        (
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x180:rate=10:duration=2",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(video),
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    source_bytes = video.read_bytes()
    run_id = _closed_run(database, source)

    probe = VideoProbeProducer(database).produce(run_id, Path("clip.mp4"))
    assert probe.probe is not None
    frame_producer = VideoFrameProducer(database)
    first = frame_producer.produce(run_id, Path("clip.mp4"), probe.work.work_id, 0.25)
    second = frame_producer.produce(run_id, Path("clip.mp4"), probe.work.work_id, 1.25)
    sheet = ContactSheetProducer(database).produce(
        run_id, Path("clip.mp4"), [first.work.work_id, second.work.work_id]
    )

    assert probe.work.status is WorkStatus.SUCCEEDED
    assert probe.probe.width == 320
    assert probe.probe.height == 180
    assert first.work.status is WorkStatus.SUCCEEDED
    assert second.work.status is WorkStatus.SUCCEEDED
    assert sheet.work.status is WorkStatus.SUCCEEDED
    assert sheet.artifact is not None
    assert video.read_bytes() == source_bytes
