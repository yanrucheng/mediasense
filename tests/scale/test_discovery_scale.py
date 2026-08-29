from __future__ import annotations

import os
from pathlib import Path
import time
import tracemalloc

import pytest

from mediasense.precheck import DiscoveredSource, discover_source_events
from mediasense.precheck._fingerprint import hash_regular_file


pytestmark = pytest.mark.scale


def test_streams_one_hundred_thousand_paths_with_bounded_python_memory(
    tmp_path: Path,
    monkeypatch,
    record_property,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    sample = source / "sample.jpg"
    sample.write_bytes(b"")
    sample_stat = sample.stat()

    class GeneratedEntry:
        def __init__(self, index: int) -> None:
            self.name = f"item-{index:06d}.jpg"
            self.path = str(source / self.name)

        @staticmethod
        def is_symlink() -> bool:
            return False

        @staticmethod
        def is_dir(*, follow_symlinks: bool) -> bool:
            assert follow_symlinks is False
            return False

        @staticmethod
        def stat(*, follow_symlinks: bool):
            assert follow_symlinks is False
            return sample_stat

    class GeneratedScan:
        def __enter__(self):
            return iter(GeneratedEntry(index) for index in range(100_000))

        def __exit__(self, *_args) -> None:
            return None

    original_scandir = os.scandir
    monkeypatch.setattr(
        "mediasense.precheck.discovery.os.scandir",
        lambda path: (
            GeneratedScan() if Path(path) == source else original_scandir(path)
        ),
    )

    tracemalloc.start()
    started = time.perf_counter()
    count = sum(
        isinstance(item, DiscoveredSource) for item in discover_source_events(source)
    )
    elapsed = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    record_property("discovered_paths", count)
    record_property("discovery_seconds", round(elapsed, 6))
    record_property("peak_python_bytes", peak)
    assert count == 100_000
    assert peak < 16 * 1024 * 1024
    assert sample.stat().st_mtime_ns == sample_stat.st_mtime_ns
    assert sample.read_bytes() == b""


def test_sparse_one_point_five_tb_candidate_fingerprint_has_constant_io(
    tmp_path: Path,
    record_property,
) -> None:
    media = tmp_path / "large-video.mp4"
    logical_size = 1_500_000_000_000
    with media.open("wb") as stream:
        stream.seek(logical_size - 1)
        stream.write(b"\0")
    before = media.stat()

    started = time.perf_counter()
    digest = hash_regular_file(media, before)
    elapsed = time.perf_counter() - started
    after = media.stat()

    record_property("logical_bytes", logical_size)
    record_property("fingerprint_seconds", round(elapsed, 6))
    assert len(digest) == 64
    assert after.st_size == logical_size
    assert after.st_mtime_ns == before.st_mtime_ns
    assert elapsed < 5
