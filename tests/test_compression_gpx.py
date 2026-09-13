"""Actual GPX producer output must affect compression and its qualifications."""

from dataclasses import replace
from pathlib import Path

from PIL import Image

from mediasense.precheck import (
    AdaptiveCompressionProducer,
    AdaptiveCompressionProfile,
    CompressionInput,
    EmbeddingProducer,
    EmbeddingProfile,
    GPXMatchProducer,
    ImageRenditionProducer,
    MetadataProducer,
)
from test_compression import ColorEncoder
from test_gpx import TimeOnlyExifTool, _closed_run, _gpx


def test_gpx_producer_coordinates_enter_distance_and_remove_only_real_limits(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (24, 24), "red").save(source / "photo.jpg")
    (source / "track.gpx").write_text(_gpx([("2026-05-04T12:27:28Z", 22.3, 114.1)]))
    database = tmp_path / "work.sqlite3"
    run = _closed_run(database, source)
    metadata = MetadataProducer(database, command_runner=TimeOnlyExifTool()).produce(
        run, Path("photo.jpg")
    )
    gpx = GPXMatchProducer(database).produce(
        run, metadata.work.work_id, [Path("track.gpx")]
    )
    rendition = ImageRenditionProducer(database).produce(run, Path("photo.jpg"))
    embedding = EmbeddingProducer(database, ColorEncoder()).produce(
        run,
        rendition.work.work_id,
        profile=EmbeddingProfile(name="color-test", dimensions=3),
    )
    item = CompressionInput(
        Path("photo.jpg"),
        rendition.work.work_id,
        metadata_work_id=metadata.work.work_id,
        gpx_work_id=gpx.work.work_id,
        embedding_work_id=embedding.work.work_id,
    )
    producer = AdaptiveCompressionProducer(database)
    attached = {r.work_id: r for r in producer.work.list_run_work(run)}
    point, records = producer._prepare_input(run, item, attached)
    assert point.gps == (22.3, 114.1)
    assert gpx.work.work_id in {r.work_id for r in records}
    profile = AdaptiveCompressionProfile(
        target_entries=1, content_based_boundaries=True
    )
    assert profile.content_distance_scale == 0.311
    missing = producer.produce(run, [replace(item, gpx_work_id=None)], profile=profile)[
        0
    ]
    complete = producer.produce(run, [item], profile=profile)[0]
    assert missing.group.members == complete.group.members
    assert "limited_similarity_evidence" in missing.group.qualifications
    assert "limited_similarity_evidence" not in complete.group.qualifications
    assert (
        "limited_similarity_evidence"
        not in complete.work.output["group"]["qualifications"]
    )

    # The point reaches the actual spatial metric, not just an unused field.
    from mediasense.precheck._compression_strategy import _boundary_strength

    distant = replace(
        point,
        relative_path=Path("far.jpg"),
        members=(Path("far.jpg"),),
        gps=(23.3, 114.1),
    )
    assert _boundary_strength(point, distant, profile)["spatial_distance"] > 1
    assert (
        _boundary_strength(point, replace(distant, gps=None), profile)[
            "spatial_distance"
        ]
        == 0
    )
