from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    ArtifactIntegrity,
    HIGH_RESOLUTION_RENDITION_PROFILE,
    ImageRenditionProducer,
    ORDINARY_RENDITION_PROFILE,
    RenditionProfile,
    WorkStatus,
)


pytestmark = pytest.mark.characterization


def _completed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


def test_ordinary_and_high_resolution_profiles_preserve_c90_review_tiers(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "large.jpg"
    Image.new("RGB", (2400, 1200), "blue").save(media)
    run_id = _completed_run(database, source)
    producer = ImageRenditionProducer(database)

    ordinary = producer.produce(
        run_id, Path("large.jpg"), profile=ORDINARY_RENDITION_PROFILE
    )
    high = producer.produce(
        run_id, Path("large.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )

    assert ordinary.work.work_id != high.work.work_id
    assert ordinary.artifact is not None
    assert high.artifact is not None
    with Image.open(ordinary.artifact.path) as image:
        assert image.size == (640, 320)
    with Image.open(high.artifact.path) as image:
        assert image.size == (1920, 960)
    assert ordinary.work.output["value"]["profile"]["name"] == "ordinary"
    assert high.work.output["value"]["profile"]["name"] == "high_resolution"


def test_rendition_preserves_c90_orientation_and_aspect_ratio_behavior(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "oriented.jpg"
    image = Image.new("RGB", (80, 40), "red")
    exif = Image.Exif()
    exif[274] = 6
    image.save(media, format="JPEG", exif=exif)
    source_before = media.read_bytes()
    run_id = _completed_run(database, source)

    outcome = ImageRenditionProducer(database).produce(
        run_id,
        Path("oriented.jpg"),
        profile=RenditionProfile(max_edge=64, jpeg_quality=90),
    )

    assert outcome.work.status is WorkStatus.SUCCEEDED
    assert outcome.artifact is not None
    assert outcome.artifact.integrity is ArtifactIntegrity.AVAILABLE
    with Image.open(outcome.artifact.path) as rendered:
        rendered.load()
        assert rendered.size == (32, 64)
        assert rendered.mode == "RGB"
        assert rendered.getexif().get(274, 1) == 1
    assert media.read_bytes() == source_before


def test_rendition_does_not_upscale_small_source_and_reuses_across_runs(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "small.png"
    Image.new("RGBA", (40, 20), (255, 0, 0, 128)).save(media)
    first_run = _completed_run(database, source)
    producer = ImageRenditionProducer(database)

    first = producer.produce(
        first_run,
        Path("small.png"),
        profile=RenditionProfile(max_edge=64, jpeg_quality=90),
    )
    second_run = _completed_run(database, source)
    second = producer.produce(
        second_run,
        Path("small.png"),
        profile=RenditionProfile(max_edge=64, jpeg_quality=90),
    )

    assert first.artifact is not None
    assert second.artifact is not None
    assert second.reused is True
    assert second.work.work_id == first.work.work_id
    assert second.artifact.artifact_id == first.artifact.artifact_id
    with Image.open(second.artifact.path) as rendered:
        assert rendered.size == (40, 20)


def test_corrupt_image_is_a_local_terminal_work_failure(tmp_path: Path) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "broken.jpg"
    media.write_bytes(b"not an image")
    run_id = _completed_run(database, source)

    outcome = ImageRenditionProducer(database).produce(
        run_id,
        Path("broken.jpg"),
    )

    assert outcome.work.status is WorkStatus.TERMINAL_FAILURE
    assert outcome.work.last_failure_code == "image_decode_failed"
    assert outcome.artifact is None
