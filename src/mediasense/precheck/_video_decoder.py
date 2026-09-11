"""Replaceable local video decoder; no Work, Artifact, or model ownership.

One context owns one container and a bounded codec. Targets select the last
presented frame at or before the requested time (the first frame if earlier).
Container duration is only a target, never a claim that a frame exists there.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from fractions import Fraction
import math
from pathlib import Path
import time
from typing import Protocol

from PIL import Image

from ._video_types import VideoProcessingError


class VideoDecoderUnavailable(RuntimeError):
    """The installed local decoder cannot load; this is not a media failure."""


class VideoDecodeCancelled(RuntimeError):
    """The execution owner stopped preparation before another decode step."""


class VideoDecodeLimitExceeded(VideoProcessingError):
    """A finite per-video work/time allowance was exhausted."""


@dataclass(frozen=True, slots=True)
class DecodedVideoFrame:
    image: Image.Image
    decoded_time_seconds: float | None
    time_base_seconds: float | None = None


class VideoDecodeSession(Protocol):
    def frame_at(
        self, target_seconds: float, *, max_edge: int
    ) -> DecodedVideoFrame: ...


class VideoDecoder(Protocol):
    @property
    def identity(self) -> str: ...

    def open(
        self,
        path: Path,
        *,
        threads: int,
        should_continue: Callable[[], bool],
    ) -> AbstractContextManager[VideoDecodeSession]: ...


def _load_av():
    try:
        import av
    except (ImportError, OSError) as error:
        raise VideoDecoderUnavailable(
            "Local video decoding requires the packaged PyAV dependency. Repair the Host installation."
        ) from error
    return av


class PyAVVideoDecoder:
    """FFmpeg bindings with explicit codec threads and cooperative work limits."""

    def __init__(
        self, *, max_decoded_frames: int = 20_000, timeout_seconds: float = 120
    ) -> None:
        if (
            max_decoded_frames < 1
            or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("video decode limits must be positive and finite")
        self.max_decoded_frames = max_decoded_frames
        self.timeout_seconds = timeout_seconds

    @property
    def identity(self) -> str:
        av = _load_av()
        libraries = ";".join(
            f"{name}={'.'.join(map(str, version))}"
            for name, version in sorted(av.library_versions.items())
        )
        return f"pyav-{av.__version__};{libraries}"

    @contextmanager
    def open(
        self,
        path: Path,
        *,
        threads: int,
        should_continue: Callable[[], bool],
    ) -> Iterator[VideoDecodeSession]:
        if threads < 1:
            raise ValueError("video decoder threads must be positive")
        av = _load_av()
        if not should_continue():
            raise VideoDecodeCancelled("video preparation was stopped")
        start = time.monotonic()
        try:
            # A local binary stream cannot instruct libavformat to fetch a URL.
            # Protocol whitelist also denies network references in containers.
            with av.open(
                str(path), mode="r", options={"protocol_whitelist": "file,crypto,data"}
            ) as container:
                if not container.streams.video:
                    raise VideoProcessingError("source has no video stream")
                stream = container.streams.video[0]
                stream.codec_context.thread_count = threads
                stream.codec_context.thread_type = "SLICE"
                yield _PyAVSession(
                    av,
                    container,
                    stream,
                    should_continue,
                    start + self.timeout_seconds,
                    self.max_decoded_frames,
                )
        except av.error.FFmpegError as error:
            raise VideoProcessingError(
                f"local video decoding failed: {error}"
            ) from error


class _PyAVSession:
    def __init__(
        self, av, container, stream, should_continue, deadline, frame_limit
    ) -> None:
        self.av = av
        self.container = container
        self.stream = stream
        self.should_continue = should_continue
        self.deadline = deadline
        self.frame_limit = frame_limit
        self.decoded_frames = 0
        self.time_base = stream.time_base
        if self.time_base is None or self.time_base <= 0:
            raise VideoProcessingError(
                "video stream has no usable presentation time base"
            )
        self.origin = stream.start_time
        self.frames = iter(container.decode(stream))
        self.previous = None
        self.ahead = None
        self.last_target: float | None = None
        self.eof = False

    def _check(self) -> None:
        if not self.should_continue():
            raise VideoDecodeCancelled("video preparation was stopped")
        if time.monotonic() >= self.deadline:
            raise VideoDecodeLimitExceeded(
                "per-video decode time/frame allowance exhausted"
            )

    def _next(self):
        self._check()
        if self.decoded_frames >= self.frame_limit:
            raise VideoDecodeLimitExceeded(
                "per-video decoded-frame allowance exhausted"
            )
        try:
            frame = next(self.frames)
        except StopIteration:
            self.eof = True
            return None
        self.decoded_frames += 1
        if frame.pts is None:
            raise VideoProcessingError("decoded frame has no presentation timestamp")
        if self.origin is None:
            self.origin = frame.pts
        position = (frame.pts - self.origin) * self.time_base
        return frame, position

    def _seek(self, target_seconds: float) -> None:
        self._check()
        offset = int(Fraction(str(target_seconds)) / self.time_base)
        if self.stream.duration is not None:
            offset = min(offset, max(0, self.stream.duration - 1))
        self.container.seek(
            (self.origin or 0) + max(0, offset),
            stream=self.stream,
            backward=True,
            any_frame=False,
        )
        self.frames = iter(self.container.decode(self.stream))
        self.previous = self.ahead = None
        self.eof = False

    def frame_at(self, target_seconds: float, *, max_edge: int) -> DecodedVideoFrame:
        if not math.isfinite(target_seconds) or target_seconds < 0 or max_edge < 1:
            raise ValueError("frame target and size must be valid")
        self._check()
        try:
            # Decode nearby targets sequentially; far targets seek to a keyframe.
            # This avoids repeated decoding of short clips and bounds long ones.
            if self.origin is None:
                self.ahead = self._next()
            if self.last_target is not None and (
                target_seconds < self.last_target
                or target_seconds - self.last_target > 2
            ):
                self._seek(target_seconds)
            elif self.last_target is None and target_seconds > 2:
                self._seek(target_seconds)
            self.last_target = target_seconds
            target = (
                round(Fraction(str(target_seconds)) / self.time_base) * self.time_base
            )
            while True:
                if self.ahead is None and not self.eof:
                    self.ahead = self._next()
                if self.ahead is None:
                    break
                frame, position = self.ahead
                if position < 0:
                    self.ahead = None
                    continue
                if position > target:
                    break
                self.previous = self.ahead
                self.ahead = None
            selected = self.previous or self.ahead
            if selected is None:
                raise VideoProcessingError(
                    "source has no decodable frame at this target"
                )
            frame, position = selected
            self._check()
            scale = min(1.0, max_edge / max(frame.width, frame.height))
            width, height = (
                max(1, round(frame.width * scale)),
                max(1, round(frame.height * scale)),
            )
            # Downscale before RGB allocation, especially for 4K/8K sources.
            image = frame.reformat(
                width=width, height=height, format="rgb24", interpolation="LANCZOS"
            ).to_image()
            rotation = frame.rotation
            if rotation:
                rotated = image.rotate(rotation, expand=True)
                image.close()
                image = rotated
            return DecodedVideoFrame(image, float(position), float(self.time_base))
        except self.av.error.FFmpegError as error:
            # Only known decoder failures are local media errors. Programming
            # failures propagate to the execution owner with their traceback.
            raise VideoProcessingError(
                f"local frame decoding failed: {error}"
            ) from error
