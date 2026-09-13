"""Shared preparation must retain per-source validity, semantics and recovery."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from mediasense.precheck import GPXMatchProducer, GPXMatchProfile, MetadataProducer
from mediasense.precheck.gpx import GPXTrackPoint, GPXTrackSegment, match_gpx_segments
from test_gpx import TimeOnlyExifTool, _closed_run, _gpx


def prepared(tmp_path, count=8):
    source = tmp_path / "source"
    source.mkdir()
    for i in range(count):
        (source / f"photo-{i}.jpg").write_bytes(b"photo")
    (source / "track.gpx").write_text(
        _gpx(
            [
                ("2026-05-04T12:26:28Z", 22.0, 114.0),
                ("2026-05-04T12:28:28Z", 24.0, 116.0),
            ]
        )
    )
    database = tmp_path / "work.sqlite3"
    run = _closed_run(database, source)
    producer = MetadataProducer(database, command_runner=TimeOnlyExifTool())
    metadata = [producer.produce(run, Path(f"photo-{i}.jpg")) for i in range(count)]
    return source, database, run, metadata


def test_concurrent_sources_share_parse_and_match_preparation(tmp_path, monkeypatch):
    import mediasense.precheck.gpx as gpx

    source, database, run, metadata = prepared(tmp_path)
    actual_parse = gpx.gpxpy.parse
    parses = []

    def parse(*args, **kwargs):
        parses.append(1)
        return actual_parse(*args, **kwargs)

    monkeypatch.setattr(gpx.gpxpy, "parse", parse)
    producer = GPXMatchProducer(database)
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(
            pool.map(
                lambda item: producer.produce(
                    run, item.work.work_id, [Path("track.gpx")]
                ),
                metadata,
            )
        )
    assert len(parses) == 1
    assert len({o.work.work_id for o in outcomes}) == len(metadata)
    assert all(
        o.observations[0]["value"]
        == {"datum": "WGS84", "latitude": 23.0, "longitude": 115.0}
        for o in outcomes
    )
    assert all(
        len([d for d in o.work.spec.dependencies if "track.gpx" in d.key]) == 2
        for o in outcomes
    )

    # New producer/process reuses Work without any prepared cache or parser call.
    resumed = GPXMatchProducer(database)
    assert all(
        resumed.produce(run, m.work.work_id, [Path("track.gpx")]).reused
        for m in metadata
    )
    assert len(parses) == 1


def test_prepared_tracks_do_not_hide_source_mutation_or_unavailability(tmp_path):
    from mediasense.precheck._fingerprint import SourceChangedDuringRead

    source, database, run, metadata = prepared(tmp_path, 3)
    producer = GPXMatchProducer(database)
    first = producer.produce(run, metadata[0].work.work_id, [Path("track.gpx")])
    original = (source / "track.gpx").read_bytes()
    (source / "track.gpx").unlink()
    with pytest.raises(FileNotFoundError):
        producer.produce(run, metadata[1].work.work_id, [Path("track.gpx")])
    (source / "track.gpx").write_bytes(original + b"\n")
    with pytest.raises(SourceChangedDuringRead):
        producer.produce(run, metadata[1].work.work_id, [Path("track.gpx")])
    (source / "track.gpx").write_text(_gpx([("2026-05-04T12:27:28Z", 20.0, 110.0)]))
    successor = _closed_run(database, source)
    fresh = MetadataProducer(database, command_runner=TimeOnlyExifTool()).produce(
        successor, Path("photo-0.jpg")
    )
    changed = producer.produce(successor, fresh.work.work_id, [Path("track.gpx")])
    assert changed.work.work_id != first.work.work_id
    assert changed.observations[0]["value"]["latitude"] == 20.0


def test_segment_search_keeps_tie_interpolation_and_limit_semantics():
    segment = GPXTrackSegment(
        Path("track.gpx"),
        0,
        (
            GPXTrackPoint(10.0, 0.0, 0.0),
            GPXTrackPoint(20.0, 10.0, 20.0),
        ),
    )
    match = match_gpx_segments((segment,), 15.0, GPXMatchProfile(5, True))
    assert (match.latitude, match.longitude, match.method) == (
        5.0,
        10.0,
        "linear_interpolation",
    )
    nearest = match_gpx_segments((segment,), 15.0, GPXMatchProfile(5, False))
    assert (nearest.latitude, nearest.method) == (0.0, "nearest_point")
    assert match_gpx_segments((segment,), 26.0, GPXMatchProfile(5)) is None


def test_cache_bound_changes_cost_only_and_io_failure_can_recover(
    tmp_path, monkeypatch
):
    import mediasense.precheck.gpx as gpx

    source, database, run, metadata = prepared(tmp_path, 4)
    actual_read = Path.read_text
    reads = []

    def read(path, *a, **kw):
        if path.suffix == ".gpx":
            reads.append(path)
            if len(reads) == 1:
                raise PermissionError("transient local access failure")
        return actual_read(path, *a, **kw)

    monkeypatch.setattr(Path, "read_text", read)
    producer = GPXMatchProducer(database)
    failed = producer.produce(run, metadata[0].work.work_id, [Path("track.gpx")])
    recovered = producer.produce(run, metadata[1].work.work_id, [Path("track.gpx")])
    assert failed.observations[0]["status"] == "failed"
    assert recovered.observations[0]["status"] == "available"
    assert len(reads) == 2
    # With no memory retained, all sources are still matched to identical values.
    uncached = GPXMatchProducer(database, max_cache_bytes=0)
    for m in metadata[2:]:
        assert (
            uncached.produce(run, m.work.work_id, [Path("track.gpx")]).observations
            == recovered.observations
        )
    assert len(reads) == 4
    assert gpx._prepared_size(producer._prepared_segments) <= producer.max_cache_bytes


def test_cached_match_revalidates_source_before_commit(tmp_path, monkeypatch):
    import mediasense.precheck.gpx as gpx

    source, database, run, metadata = prepared(tmp_path, 2)
    producer = GPXMatchProducer(database)
    producer.produce(run, metadata[0].work.work_id, [Path("track.gpx")])
    actual_match = gpx.match_gpx_segments

    def match(*args, **kwargs):
        result = actual_match(*args, **kwargs)
        with (source / "track.gpx").open("a") as stream:
            stream.write("\n")
        return result

    monkeypatch.setattr(gpx, "match_gpx_segments", match)
    changed = producer.produce(run, metadata[1].work.work_id, [Path("track.gpx")])
    assert changed.work.status == "invalidated"
    assert changed.observations == ()


def test_resource_admission_applies_only_to_new_matching_work(tmp_path):
    from mediasense.precheck.resources import (
        ResourceAdmission,
        ResourceClaim,
        ResourceLimitExceeded,
    )

    source, database, run, metadata = prepared(tmp_path, 2)
    GPXMatchProducer(database).produce(
        run, metadata[0].work.work_id, [Path("track.gpx")]
    )
    admission = ResourceAdmission(ResourceClaim(memory_bytes=1))
    producer = GPXMatchProducer(
        database,
        memory_admission=lambda size: admission.hold(ResourceClaim(memory_bytes=size)),
    )
    assert producer.produce(run, metadata[0].work.work_id, [Path("track.gpx")]).reused
    with pytest.raises(ResourceLimitExceeded):
        producer.produce(run, metadata[1].work.work_id, [Path("track.gpx")])
    assert all(r.status != "running" for r in producer.work.list_run_work(run))
    assert admission.peak_usage().memory_bytes == 0
