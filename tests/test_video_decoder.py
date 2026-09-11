"""Real local PTS, finite sampling, per-video reuse, and interruption semantics."""

from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

import av
from PIL import Image
import pytest

from mediasense.precheck import (
    ContactSheetProducer,
    PrecheckReadTool,
    ResultStore,
    VideoFrameProducer,
    VideoProbeProducer,
    WorkStatus,
)
from mediasense.precheck._video_decoder import (
    DecodedVideoFrame,
    PyAVVideoDecoder,
    VideoDecodeCancelled,
    VideoDecodeLimitExceeded,
)
from mediasense.precheck.video import sample_video_times
from test_video import _closed_run, FakeVideoTools


def make_video(path: Path, times: tuple[float, ...]) -> None:
    with av.open(str(path), "w") as container:
        stream = container.add_stream("libx264", rate=10)
        stream.width, stream.height = 64, 48
        stream.pix_fmt = "yuv420p"
        stream.time_base = stream.codec_context.time_base = Fraction(1, 1000)
        stream.codec_context.options = {"bf": "0", "g": "1"}
        for index, position in enumerate(times):
            with Image.new("RGB", (64, 48), (index * 60, 40, 60)) as image:
                frame = av.VideoFrame.from_image(image)
            frame.pts = round(position * 1000)
            frame.time_base = Fraction(1, 1000)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)


@pytest.mark.parametrize("times", [(0.0,), (0.0, 4.0), (0.0, 4.0, 8.0)])
def test_real_short_sparse_video_resolves_end_and_deduplicates(
    tmp_path: Path, times
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "clip.mp4"
    make_video(path, times)
    before = path.read_bytes()
    database = tmp_path / "workspace/work.sqlite3"
    run_id = _closed_run(database, source)
    probe = VideoProbeProducer(database).produce(run_id, Path("clip.mp4"))
    targets = sample_video_times(probe.probe.duration_seconds, max_frames=3)
    producer = VideoFrameProducer(database, threads=2)
    frames = producer.produce_many(
        run_id, Path("clip.mp4"), probe.work.work_id, targets
    )
    assert len(frames) == len(times)
    assert [
        frame.work.output["value"]["decoded_time_seconds"] for frame in frames
    ] == list(times)
    assert all(frame.work.status is WorkStatus.SUCCEEDED for frame in frames)
    assert len(
        tuple(producer.work.iter_run_work(run_id, capability="video-frame"))
    ) == len(targets)
    for frame in frames:
        with Image.open(frame.artifact.path) as image:
            image.load()
            assert image.size == (64, 48)

    second_run = _closed_run(database, source)
    reused_probe = VideoProbeProducer(database).produce(second_run, Path("clip.mp4"))

    class ReuseOnly:
        identity = producer.decoder_identity

        def open(self, *args, **kwargs):
            raise AssertionError("a valid reused video must not be opened for decode")

    reused = VideoFrameProducer(database, decoder=ReuseOnly(), threads=1).produce_many(
        second_run,
        Path("clip.mp4"),
        reused_probe.work.work_id,
        targets,
    )
    assert all(frame.reused for frame in reused)
    assert [frame.work.work_id for frame in frames] == [
        frame.work.work_id for frame in reused
    ]
    assert path.read_bytes() == before


def test_vfr_and_nonzero_stream_origin_use_pts_not_average_rate(tmp_path: Path) -> None:
    path = tmp_path / "offset-vfr.mp4"
    make_video(path, (5.0, 5.1, 5.9, 7.8))
    decoder = PyAVVideoDecoder()
    with decoder.open(path, threads=2, should_continue=lambda: True) as session:
        positions = []
        for target in (0.0, 0.5, 1.5, 20.0, 0.5):
            decoded = session.frame_at(target, max_edge=32)
            positions.append(decoded.decoded_time_seconds)
            with decoded.image as image:
                assert image.size == (32, 24)
                assert decoded.time_base_seconds > 0
        assert positions == pytest.approx([0.0, 0.1, 0.9, 2.8, 0.1])


def test_decoder_enforces_cancel_and_work_bounds(tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    make_video(path, (0.0, 0.1, 0.2, 0.3))
    with pytest.raises(VideoDecodeCancelled):
        with PyAVVideoDecoder().open(path, threads=1, should_continue=lambda: False):
            pass
    decoder = PyAVVideoDecoder(max_decoded_frames=1)
    with decoder.open(path, threads=1, should_continue=lambda: True) as session:
        with pytest.raises(VideoDecodeLimitExceeded):
            session.frame_at(0.2, max_edge=32)


def test_batch_cancellation_preserves_success_and_retries_only_pending_targets(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "clip.mp4").write_bytes(b"test fixture")
    database = tmp_path / "workspace/work.sqlite3"
    run_id = _closed_run(database, source)
    probe = VideoProbeProducer(
        database, command_runner=FakeVideoTools(), ffprobe_version="test"
    ).produce(run_id, Path("clip.mp4"))

    class CancellingDecoder:
        identity = "test-cancelling-decoder"

        @contextmanager
        def open(self, *args, **kwargs):
            class Session:
                def frame_at(self, target_seconds, *, max_edge):
                    if target_seconds > 0:
                        raise VideoDecodeCancelled("stopped after first frame")
                    return DecodedVideoFrame(Image.new("RGB", (16, 16), "red"), 0.0)

            yield Session()

    producer = VideoFrameProducer(database, decoder=CancellingDecoder())
    with pytest.raises(VideoDecodeCancelled):
        producer.produce_many(
            run_id, Path("clip.mp4"), probe.work.work_id, (0.0, 10.0, 25.0)
        )
    works = tuple(producer.work.iter_run_work(run_id, capability="video-frame"))
    assert sum(work.status is WorkStatus.SUCCEEDED for work in works) == 1
    assert sum(work.status is WorkStatus.RETRYABLE_FAILURE for work in works) == 2
    replacement = FakeVideoTools()
    replacement.identity = CancellingDecoder.identity
    retried = VideoFrameProducer(database, decoder=replacement).produce_many(
        run_id,
        Path("clip.mp4"),
        probe.work.work_id,
        (0.0, 10.0, 25.0),
    )
    assert [frame.reused for frame in retried] == [True, False, False]
    assert replacement.opened == [source / "clip.mp4"]
    assert [time for time, _threads in replacement.decode_calls] == [10.0, 25.0]


def test_source_change_invalidates_only_its_probe_and_frames(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    path = source / "clip.mp4"
    path.write_bytes(b"test fixture")
    (source / "other.mp4").write_bytes(b"other fixture")
    database = tmp_path / "workspace/work.sqlite3"
    run_id = _closed_run(database, source)
    fake = FakeVideoTools()
    probes = VideoProbeProducer(database, command_runner=fake, ffprobe_version="test")
    probe = probes.produce(run_id, Path("clip.mp4"))
    other = probes.produce(run_id, Path("other.mp4"))

    class ChangingDecoder(FakeVideoTools):
        @contextmanager
        def open(self, *args, **kwargs):
            with super().open(*args, **kwargs) as session:
                original = session.frame_at

                def frame_at(target_seconds, **options):
                    frame = original(target_seconds, **options)
                    path.write_bytes(b"changed during decode")
                    return frame

                session.frame_at = frame_at
                yield session

    producer = VideoFrameProducer(database, decoder=ChangingDecoder())
    frames = producer.produce_many(
        run_id, Path("clip.mp4"), probe.work.work_id, (0.0, 10.0)
    )
    assert all(frame.work.status is WorkStatus.INVALIDATED for frame in frames)
    assert producer.work.get_work(probe.work.work_id).status is WorkStatus.INVALIDATED
    assert producer.work.get_work(other.work.work_id).status is WorkStatus.SUCCEEDED


def test_decoder_change_preserves_old_result_and_unrelated_work(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "clip.mp4").write_bytes(b"video fixture")
    (source / "other.mp4").write_bytes(b"other fixture")
    database = tmp_path / "workspace/work.sqlite3"
    run_id = _closed_run(database, source)
    fake = FakeVideoTools()
    probe_producer = VideoProbeProducer(
        database, command_runner=fake, ffprobe_version="test"
    )
    probe = probe_producer.produce(run_id, Path("clip.mp4"))
    other_probe = probe_producer.produce(run_id, Path("other.mp4"))
    other = VideoFrameProducer(database, decoder=fake).produce(
        run_id, Path("other.mp4"), other_probe.work.work_id, 0.0
    )

    class HistoricalDecoder(FakeVideoTools):
        identity = "historical-decoder-without-pts"

        @contextmanager
        def open(self, *args, **kwargs):
            with super().open(*args, **kwargs) as session:
                original = session.frame_at

                def frame_at(target_seconds, **options):
                    frame = original(target_seconds, **options)
                    return DecodedVideoFrame(frame.image, None)

                session.frame_at = frame_at
                yield session

    old = VideoFrameProducer(database, decoder=HistoricalDecoder()).produce(
        run_id, Path("clip.mp4"), probe.work.work_id, 10.0
    )
    results = ResultStore(database)
    draft = results.build_minimal(
        run_id,
        [],
        video_probe_work_ids=[probe.work.work_id, other_probe.work.work_id],
        video_frame_work_ids=[old.work.work_id, other.work.work_id],
    )
    old_evidence_ref = next(
        item.ref for item in draft.evidence if item.work_id == old.work.work_id
    )
    sealed = results.seal(draft)
    old_bytes = sealed.path.read_bytes()
    next_run = _closed_run(database, source)
    reused_probe = probe_producer.produce(next_run, Path("clip.mp4"))
    reused_other_probe = probe_producer.produce(next_run, Path("other.mp4"))
    producer = VideoFrameProducer(database, decoder=fake)
    updated = producer.produce(
        next_run, Path("clip.mp4"), reused_probe.work.work_id, 10.0
    )
    reused_other = producer.produce(
        next_run, Path("other.mp4"), reused_other_probe.work.work_id, 0.0
    )
    assert reused_probe.reused and reused_other.reused
    assert updated.work.work_id != old.work.work_id
    assert updated.work.output["value"]["decoded_time_seconds"] == 10.0
    assert sealed.path.read_bytes() == old_bytes
    reader = PrecheckReadTool(database)
    expanded = reader.read(
        {
            "action": "expand",
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "evidence_refs": [old_evidence_ref],
            "include": ["anchor_evidence"],
        }
    )
    frame_values = [
        o["value"]
        for item in expanded["items"]
        for o in item["included"]["anchor_evidence"]["observations"]
        if o["name"] == "video_frame"
    ]
    assert any("decoded_time_seconds" not in value for value in frame_values)


def test_contact_sheet_projects_requested_and_actual_positions(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    make_video(source / "clip.mp4", (0.0, 4.0, 8.0))
    database = tmp_path / "workspace/work.sqlite3"
    run_id = _closed_run(database, source)
    probe = VideoProbeProducer(database).produce(run_id, Path("clip.mp4"))
    frames = VideoFrameProducer(database).produce_many(
        run_id, Path("clip.mp4"), probe.work.work_id, (0.0, 4.05, 8.1)
    )
    sheet = ContactSheetProducer(database).produce(
        run_id, Path("clip.mp4"), [frame.work.work_id for frame in frames]
    )
    results = ResultStore(database)
    draft = results.build_minimal(
        run_id,
        [],
        video_frame_work_ids=[frame.work.work_id for frame in frames],
        contact_sheet_work_ids=[sheet.work.work_id],
    )
    frame_evidence = {
        item.ref: item
        for item in draft.evidence
        if item.observations[0]["name"] == "video_frame"
    }
    sheet_evidence = next(
        item
        for item in draft.evidence
        if item.observations[0]["name"] == "video_contact_sheet"
    )
    cells = sheet_evidence.observations[0]["value"]["frames"]
    assert [cell["sample_time_seconds"] for cell in cells] == [0.0, 4.05, 8.1]
    assert [cell["decoded_time_seconds"] for cell in cells] == [0.0, 4.0, 8.0]
    for cell in cells:
        observation = frame_evidence[cell["evidence_ref"]].observations[0]
        assert (
            observation["value"]["decoded_time_seconds"] == cell["decoded_time_seconds"]
        )
        assert (
            observation["basis"]["producer"]["identity"] == "builtin-pts-video-frame-v2"
        )
        assert observation["basis"]["position"]["method"] == "presentation_timestamp"
