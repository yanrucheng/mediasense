"""Run-local ExifTool stay-open adapter for bounded metadata batches."""

from __future__ import annotations

import locale
import os
from pathlib import Path
import subprocess
import time
from threading import Lock, Thread
from typing import BinaryIO, Callable, Sequence


class ExifToolCancelled(subprocess.SubprocessError):
    """The owning Run stopped while a stay-open request was in flight."""


class StayOpenExifTool:
    """Execute sequential commands through one restartable ExifTool process."""

    def __init__(
        self,
        executable: str = "exiftool",
        *,
        timeout: float = 120,
        should_continue: Callable[[], bool] | None = None,
    ) -> None:
        if timeout <= 0:
            raise ValueError("ExifTool timeout must be positive")
        self.executable = executable
        self.timeout = timeout
        self.encoding = locale.getpreferredencoding(False) or "utf-8"
        self.should_continue = should_continue or (lambda: True)
        self._process: subprocess.Popen[bytes] | None = None
        self._sequence = 0
        self._start_count = 0
        self._lock = Lock()

    @property
    def start_count(self) -> int:
        return self._start_count

    def __call__(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        values = tuple(str(value) for value in command)
        if not values or Path(values[0]).name != Path(self.executable).name:
            raise ValueError(
                "ExifTool command does not match the configured executable"
            )
        if any("\n" in value or "\r" in value for value in values[1:]):
            raise ValueError("ExifTool stay-open arguments cannot contain newlines")
        with self._lock:
            if not self.should_continue():
                raise ExifToolCancelled("ExifTool request cancelled before execution")
            process = self._ensure_process()
            self._sequence += 1
            signal = str(self._sequence)
            ready = f"{{ready{signal}}}".encode(self.encoding)
            stderr_ready = f"post{signal}".encode(self.encoding)
            # ``--`` is useful for one-shot argv parsing, but in ExifTool's
            # argfile/stay-open protocol it also hides the control arguments we
            # append below. Source paths are absolute, so option ambiguity does
            # not require it here.
            payload = [
                value.encode(self.encoding) for value in values[1:] if value != "--"
            ]
            payload.extend(
                (
                    b"-echo4",
                    f"=${{status}}=post{signal}".encode(self.encoding),
                    f"-execute{signal}".encode(self.encoding),
                )
            )
            stdout_chunks: list[bytes] = []
            stderr_chunks: list[bytes] = []
            errors: list[BaseException] = []
            stdout_thread = Thread(
                target=_read_until,
                args=(process.stdout, ready, stdout_chunks, errors),
                daemon=True,
            )
            stderr_thread = Thread(
                target=_read_until,
                args=(process.stderr, stderr_ready, stderr_chunks, errors),
                daemon=True,
            )
            stdout_thread.start()
            stderr_thread.start()
            try:
                assert process.stdin is not None
                process.stdin.write(b"\n".join(payload) + b"\n")
                process.stdin.flush()
                deadline = time.monotonic() + self.timeout
                while stdout_thread.is_alive() or stderr_thread.is_alive():
                    if not self.should_continue():
                        raise ExifToolCancelled("ExifTool request cancelled")
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(values, self.timeout)
                    stdout_thread.join(min(0.05, remaining))
                    stderr_thread.join(0)
                if errors:
                    raise OSError(str(errors[0])) from errors[0]
                stdout = _without_marker(stdout_chunks, ready).decode(
                    self.encoding, errors="replace"
                )
                stderr_bytes = _without_marker(stderr_chunks, stderr_ready)
                stderr, returncode = _stderr_and_status(stderr_bytes, self.encoding)
                return subprocess.CompletedProcess(values, returncode, stdout, stderr)
            except BaseException:
                self._terminate_locked()
                raise

    def close(self) -> None:
        with self._lock:
            self._terminate_locked()

    def _ensure_process(self) -> subprocess.Popen[bytes]:
        if self._process is not None and self._process.poll() is None:
            return self._process
        self._process = subprocess.Popen(
            (self.executable, "-stay_open", "True", "-@", "-"),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._start_count += 1
        if self._process.poll() is not None:
            raise OSError("ExifTool stay-open process exited during startup")
        return self._process

    def _terminate_locked(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        try:
            process.communicate(input=b"-stay_open\nFalse\n", timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
            process.communicate()


def _read_until(
    stream: BinaryIO | None,
    marker: bytes,
    chunks: list[bytes],
    errors: list[BaseException],
) -> None:
    try:
        if stream is None:
            raise OSError("ExifTool process stream is unavailable")
        while not _tail(chunks, len(marker) + 4).strip().endswith(marker):
            chunk = os.read(stream.fileno(), 4096)
            if not chunk:
                raise OSError("ExifTool process closed its output unexpectedly")
            chunks.append(chunk)
    except BaseException as error:
        errors.append(error)


def _tail(chunks: list[bytes], size: int) -> bytes:
    remaining = size
    selected: list[bytes] = []
    for chunk in reversed(chunks):
        selected.append(chunk[-remaining:])
        remaining -= len(chunk)
        if remaining <= 0:
            break
    return b"".join(reversed(selected))


def _without_marker(chunks: list[bytes], marker: bytes) -> bytes:
    value = b"".join(chunks).strip()
    if not value.endswith(marker):
        raise OSError("ExifTool response marker is missing")
    return value[: -len(marker)].rstrip()


def _stderr_and_status(value: bytes, encoding: str) -> tuple[str, int]:
    stripped = value.strip()
    if not stripped.endswith(b"="):
        raise OSError("ExifTool status marker is malformed")
    prefix = stripped[:-1]
    delimiter = prefix.rfind(b"=")
    if delimiter < 0:
        raise OSError("ExifTool status marker is missing")
    try:
        returncode = int(prefix[delimiter + 1 :].decode("ascii"))
    except ValueError as error:
        raise OSError("ExifTool status value is malformed") from error
    stderr = prefix[:delimiter].rstrip().decode(encoding, errors="replace")
    return stderr, returncode


__all__ = ["ExifToolCancelled", "StayOpenExifTool"]
