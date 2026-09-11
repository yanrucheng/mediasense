"""Value types and pure sampling rules for local video evidence."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
import subprocess

from ._artifact_types import ArtifactRecord
from ._work_types import WorkRecord


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class VideoProbe:
    duration_seconds: float
    width: int
    height: int
    frame_rate: float | None
    frame_count: int | None


@dataclass(frozen=True, slots=True)
class VideoProbeOutcome:
    work: WorkRecord
    probe: VideoProbe | None
    reused: bool


@dataclass(frozen=True, slots=True)
class VideoFrameProfile:
    max_edge: int = 1920
    jpeg_quality: int = 90

    def __post_init__(self) -> None:
        if self.max_edge < 1:
            raise ValueError("video frame max_edge must be positive")
        if not 1 <= self.jpeg_quality <= 95:
            raise ValueError("video frame JPEG quality must be between 1 and 95")


@dataclass(frozen=True, slots=True)
class VideoFrameOutcome:
    work: WorkRecord
    artifact: ArtifactRecord | None
    reused: bool


@dataclass(frozen=True, slots=True)
class ContactSheetProfile:
    columns: int = 4
    tile_edge: int = 480
    jpeg_quality: int = 88

    def __post_init__(self) -> None:
        if self.columns < 1 or self.tile_edge < 1:
            raise ValueError("contact sheet geometry must be positive")
        if not 1 <= self.jpeg_quality <= 95:
            raise ValueError("contact sheet JPEG quality must be between 1 and 95")


@dataclass(frozen=True, slots=True)
class ContactSheetOutcome:
    work: WorkRecord
    artifact: ArtifactRecord | None
    reused: bool


@dataclass(frozen=True, slots=True)
class VideoKeyFrameProfile:
    top_k: int | float = 0.5

    def __post_init__(self) -> None:
        if isinstance(self.top_k, float):
            if not 0 < self.top_k <= 1:
                raise ValueError("video key-frame top_k ratio must be in (0, 1]")
        elif self.top_k < 1:
            raise ValueError("video key-frame top_k count must be positive")


@dataclass(frozen=True, slots=True)
class VideoKeyFrameOutcome:
    work: WorkRecord
    selected_frame_work_id: str | None
    reused: bool


class VideoProcessingError(RuntimeError):
    """A local video tool could not return a trustworthy result."""


def sample_video_times(
    duration_seconds: float,
    *,
    interval_seconds: float = 10.0,
    max_frames: int = 20,
) -> tuple[float, ...]:
    """Return bounded deterministic samples including the beginning and end."""

    if not math.isfinite(duration_seconds) or duration_seconds < 0:
        raise ValueError("video duration must be a finite nonnegative number")
    if not math.isfinite(interval_seconds) or interval_seconds <= 0:
        raise ValueError("video sampling interval must be positive")
    if max_frames < 1:
        raise ValueError("video maximum frame count must be positive")
    if duration_seconds == 0 or max_frames == 1:
        return (0.0,)
    if max_frames == 3 or (duration_seconds <= interval_seconds and max_frames >= 3):
        return tuple(dict.fromkeys((0.0, round(duration_seconds / 2, 6), round(duration_seconds, 6))))
    step = max(interval_seconds, duration_seconds / (max_frames - 1))
    samples = [0.0]
    current = step
    while current < duration_seconds and len(samples) < max_frames - 1:
        samples.append(round(current, 6))
        current += step
    samples.append(round(duration_seconds, 6))
    return tuple(dict.fromkeys(samples))


def frame_identity(work: WorkRecord) -> tuple[str, object]:
    """Identity within one source video; unknown positions never become exact PTS."""

    output = work.output if isinstance(work.output, Mapping) else {}
    value = output.get("value") or {}
    position = value.get("decoded_time_seconds")
    if isinstance(position, (int, float)) and math.isfinite(position) and position >= 0:
        return "pts", position
    artifacts = output.get("artifacts") or []
    if artifacts:
        return "artifact", artifacts[0]["artifact_ref"]
    return "work", work.work_id


__all__ = [
    "CommandRunner",
    "ContactSheetOutcome",
    "ContactSheetProfile",
    "VideoFrameOutcome",
    "VideoFrameProfile",
    "VideoKeyFrameOutcome",
    "VideoKeyFrameProfile",
    "VideoProbe",
    "VideoProbeOutcome",
    "VideoProcessingError",
    "sample_video_times",
]
