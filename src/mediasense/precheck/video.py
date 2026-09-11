"""Stable facade for local video evidence capabilities."""

from ._video_keyframe import VideoKeyFrameCandidateProducer
from ._video_frames import VideoFrameProducer
from ._video_producers import (
    ContactSheetProducer,
    VideoProbeProducer,
)
from ._video_types import (
    CommandRunner,
    ContactSheetOutcome,
    ContactSheetProfile,
    VideoFrameOutcome,
    VideoFrameProfile,
    VideoKeyFrameOutcome,
    VideoKeyFrameProfile,
    VideoProbe,
    VideoProbeOutcome,
    VideoProcessingError,
    sample_video_times,
)

__all__ = [
    "CommandRunner",
    "ContactSheetOutcome",
    "ContactSheetProducer",
    "ContactSheetProfile",
    "VideoFrameOutcome",
    "VideoFrameProducer",
    "VideoFrameProfile",
    "VideoKeyFrameCandidateProducer",
    "VideoKeyFrameOutcome",
    "VideoKeyFrameProfile",
    "VideoProbe",
    "VideoProbeOutcome",
    "VideoProbeProducer",
    "VideoProcessingError",
    "sample_video_times",
]
