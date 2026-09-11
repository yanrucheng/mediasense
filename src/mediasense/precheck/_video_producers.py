"""FFprobe and Pillow producers for local video inspection and contact sheets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import timedelta
import json
import math
from pathlib import Path
import subprocess
from typing import Any

from PIL import Image, ImageOps

from ._artifact_types import InvalidArtifactDraft
from ._fingerprint import SourceChangedDuringRead
from ._sqlite_scope import connection_scope
from ._video_types import (
    CommandRunner,
    ContactSheetOutcome,
    ContactSheetProfile,
    VideoProbe,
    VideoProbeOutcome,
    VideoProcessingError,
    frame_identity,
)
from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
    upstream_dependency,
)
from .artifact import ArtifactStore
from .source_validity import SourceContentProof, SourceValidityStore
from .work import WorkStore


class VideoProbeProducer:
    def __init__(
        self,
        database_path: Path,
        *,
        executable: str = "ffprobe",
        command_runner: CommandRunner | None = None,
        ffprobe_version: str | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.validity = SourceValidityStore(self.database_path)
        self.work = WorkStore(self.database_path)
        self.executable = executable
        self._run = command_runner or _run_command
        self.ffprobe_version = ffprobe_version or _tool_version(executable, self._run)

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        *,
        owner: str = "builtin-video-probe",
    ) -> VideoProbeOutcome:
        with connection_scope(self.database_path):
            return self._produce(run_id, relative_path, owner=owner)

    def _produce(self, run_id: str, relative_path: Path, *, owner: str) -> VideoProbeOutcome:
        proof = self.validity.prove(run_id, relative_path)
        spec = WorkSpec(
            capability="video-probe",
            producer_identity="builtin-ffprobe-video-v1",
            dependencies=(
                source_revision_dependency(
                    proof.dataset_id, proof.relative_path, proof.source_revision
                ),
                proof.dependency(),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "subject_relative_path",
                    proof.relative_path.as_posix(),
                ),
                WorkDependency(
                    DependencyKind.ENVIRONMENT,
                    "ffprobe_version",
                    self.ffprobe_version,
                ),
            ),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            return VideoProbeOutcome(record, _probe_from_output(record.output), True)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return VideoProbeOutcome(record, None, False)
        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=2),
            work_id=record.work_id,
        )
        if not leases:
            return VideoProbeOutcome(self.work.get_work(record.work_id), None, False)
        lease = leases[0]
        try:
            probe = self._probe(proof.source_path)
            _verify_proof(self.validity, run_id, proof)
            completed = self.work.succeed_work(
                lease,
                {
                    "probe": _probe_value(probe),
                    "producer": {
                        "identity": spec.producer_identity,
                        "ffprobe_version": self.ffprobe_version,
                    },
                    "subject": {"relative_path": proof.relative_path.as_posix()},
                },
            )
            return VideoProbeOutcome(completed, probe, False)
        except SourceChangedDuringRead:
            self.work.invalidate_work(
                record.work_id, "source changed during video probe"
            )
            return VideoProbeOutcome(self.work.get_work(record.work_id), None, False)
        except (
            OSError,
            subprocess.SubprocessError,
            ValueError,
            VideoProcessingError,
        ) as error:
            failed = self.work.fail_work(
                lease,
                error_code="video_probe_failed",
                message=str(error) or type(error).__name__,
                retryable=False,
            )
            return VideoProbeOutcome(failed, None, False)

    def _probe(self, path: Path) -> VideoProbe:
        completed = self._run(
            (
                self.executable,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height,avg_frame_rate,nb_frames:format=duration",
                "-of",
                "json",
                "--",
                str(path),
            )
        )
        if completed.returncode != 0:
            raise VideoProcessingError(
                completed.stderr.strip() or "ffprobe exited unsuccessfully"
            )
        try:
            decoded = json.loads(completed.stdout)
            stream = decoded["streams"][0]
            duration = float(decoded["format"]["duration"])
            width = int(stream["width"])
            height = int(stream["height"])
        except (
            IndexError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            raise VideoProcessingError(
                "ffprobe returned incomplete video facts"
            ) from error
        if not math.isfinite(duration) or duration < 0 or width < 1 or height < 1:
            raise VideoProcessingError("ffprobe returned invalid video facts")
        return VideoProbe(
            duration_seconds=duration,
            width=width,
            height=height,
            frame_rate=_parse_rate(stream.get("avg_frame_rate")),
            frame_count=_parse_optional_int(stream.get("nb_frames")),
        )


class ContactSheetProducer:
    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.validity = SourceValidityStore(self.database_path)
        self.work = WorkStore(self.database_path)
        self.artifacts = ArtifactStore(self.database_path)

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        frame_work_ids: Sequence[str],
        *,
        profile: ContactSheetProfile = ContactSheetProfile(),
        owner: str = "builtin-contact-sheet",
    ) -> ContactSheetOutcome:
        with connection_scope(self.database_path):
            return self._produce(run_id, relative_path, frame_work_ids, profile=profile, owner=owner)

    def _produce(self, run_id, relative_path, frame_work_ids, *, profile, owner):
        if not frame_work_ids:
            raise ValueError("contact sheet requires at least one frame Work")
        proof = self.validity.prove(run_id, relative_path)
        frames = tuple(
            _attached_work(self.work, run_id, work_id, "video-frame")
            for work_id in frame_work_ids
        )
        if any(next(d.value for d in frame.spec.dependencies if d.key == "subject_relative_path")
               != proof.relative_path.as_posix() for frame in frames):
            raise ValueError("video frames belong to another Source Item")
        distinct: dict[tuple[str, object], WorkRecord] = {}
        for frame in frames:
            distinct.setdefault(frame_identity(frame), frame)
        frames = tuple(distinct.values())
        spec = WorkSpec(
            capability="video-contact-sheet",
            producer_identity="builtin-video-contact-sheet-v1",
            dependencies=(
                source_revision_dependency(
                    proof.dataset_id, proof.relative_path, proof.source_revision
                ),
                proof.dependency(),
                *(upstream_dependency(frame) for frame in frames),
                WorkDependency(
                    DependencyKind.PARAMETER, "columns", str(profile.columns)
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "subject_relative_path",
                    proof.relative_path.as_posix(),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER, "tile_edge", str(profile.tile_edge)
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "jpeg_quality",
                    str(profile.jpeg_quality),
                ),
            ),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            artifacts = self.artifacts.artifacts_for_work(record.work_id)
            if artifacts and artifacts[0].integrity.value == "available":
                return ContactSheetOutcome(record, artifacts[0], True)
            record = self.work.ensure_work(run_id, spec)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return ContactSheetOutcome(record, None, False)
        frame_artifacts = tuple(
            self.artifacts.require_available(
                self.artifacts.artifacts_for_work(frame.work_id)[0].artifact_id
            )
            for frame in frames
        )
        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=5),
            work_id=record.work_id,
        )
        if not leases:
            return ContactSheetOutcome(self.work.get_work(record.work_id), None, False)
        lease = leases[0]
        draft = self.artifacts.create_draft(lease, suffix=".jpg")
        try:
            width, height = _render_contact_sheet(
                [artifact.path for artifact in frame_artifacts], draft.path, profile
            )
            finished, artifact = self.artifacts.publish(
                lease,
                draft,
                suffix=".jpg",
                media_type="image/jpeg",
                role="contact_sheet",
                output={
                    "columns": profile.columns,
                    "frame_work_ids": [frame.work_id for frame in frames],
                    "height": height,
                    "tile_edge": profile.tile_edge,
                    "width": width,
                },
            )
            return ContactSheetOutcome(finished, artifact, False)
        except (InvalidArtifactDraft, OSError, ValueError) as error:
            draft.path.unlink(missing_ok=True)
            failed = self.work.fail_work(
                lease,
                error_code="contact_sheet_failed",
                message=str(error) or type(error).__name__,
                retryable=False,
            )
            return ContactSheetOutcome(failed, None, False)


def _attached_work(
    work: WorkStore, run_id: str, work_id: str, capability: str
) -> WorkRecord:
    try:
        record = work.get_run_work(run_id, work_id)
    except KeyError as error:
        raise ValueError(f"{capability} Work is not attached to this run") from error
    if record.spec.capability != capability:
        raise ValueError(f"{capability} Work is not attached to this run")
    if record.status is not WorkStatus.SUCCEEDED:
        raise ValueError(f"{capability} Work must succeed first")
    return record


def _probe_value(probe: VideoProbe) -> dict[str, Any]:
    return {
        "duration_seconds": probe.duration_seconds,
        "frame_count": probe.frame_count,
        "frame_rate": probe.frame_rate,
        "height": probe.height,
        "width": probe.width,
    }


def _probe_from_output(output: object | None) -> VideoProbe | None:
    if not isinstance(output, Mapping) or not isinstance(output.get("probe"), Mapping):
        return None
    value = output["probe"]
    try:
        return VideoProbe(
            duration_seconds=float(value["duration_seconds"]),
            width=int(value["width"]),
            height=int(value["height"]),
            frame_rate=None
            if value.get("frame_rate") is None
            else float(value["frame_rate"]),
            frame_count=None
            if value.get("frame_count") is None
            else int(value["frame_count"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_rate(value: object) -> float | None:
    if not isinstance(value, str) or value in {"", "0/0", "N/A"}:
        return None
    try:
        numerator, denominator = value.split("/", 1)
        rate = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return None
    return rate if math.isfinite(rate) and rate > 0 else None


def _parse_optional_int(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _render_contact_sheet(
    paths: Sequence[Path], destination: Path, profile: ContactSheetProfile
) -> tuple[int, int]:
    tiles: list[Image.Image] = []
    try:
        for path in paths:
            with Image.open(path) as image:
                image.load()
                tile = ImageOps.contain(
                    image.convert("RGB"),
                    (profile.tile_edge, profile.tile_edge),
                    Image.Resampling.LANCZOS,
                )
            cell = Image.new("RGB", (profile.tile_edge, profile.tile_edge), "black")
            cell.paste(
                tile,
                (
                    (profile.tile_edge - tile.width) // 2,
                    (profile.tile_edge - tile.height) // 2,
                ),
            )
            tiles.append(cell)
        rows = math.ceil(len(tiles) / profile.columns)
        sheet = Image.new(
            "RGB",
            (profile.columns * profile.tile_edge, rows * profile.tile_edge),
            "black",
        )
        for index, tile in enumerate(tiles):
            sheet.paste(
                tile,
                (
                    (index % profile.columns) * profile.tile_edge,
                    (index // profile.columns) * profile.tile_edge,
                ),
            )
        sheet.save(
            destination, format="JPEG", quality=profile.jpeg_quality, optimize=True
        )
        with destination.open("rb") as stream:
            import os

            os.fsync(stream.fileno())
        return sheet.size
    finally:
        for tile in tiles:
            tile.close()


def _tool_version(executable: str, runner: CommandRunner) -> str:
    try:
        completed = runner((executable, "-version"))
    except (OSError, subprocess.SubprocessError) as error:
        raise VideoProcessingError(f"{executable} is unavailable: {error}") from error
    if completed.returncode != 0 or not completed.stdout.strip():
        raise VideoProcessingError(f"{executable} version could not be determined")
    return completed.stdout.splitlines()[0].strip()


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=180,
    )


def _verify_proof(
    validity: SourceValidityStore, run_id: str, expected: SourceContentProof
) -> None:
    observed = validity.prove(run_id, expected.relative_path)
    if observed.dependency().value != expected.dependency().value:
        raise SourceChangedDuringRead(
            f"source changed during video operation: {expected.relative_path}"
        )


__all__ = [
    "ContactSheetProducer",
    "VideoProbeProducer",
]
