"""Local ExifTool metadata observations for reusable PreCheck Work."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ._fingerprint import SourceChangedDuringRead
from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
)
from .accounting import AccountingStore
from .discovery import association_key
from .source_validity import SourceContentProof, SourceValidityStore
from .work import WorkStore


_SIDECAR_SUFFIXES = (".xmp", ".exif", ".json", ".xml")
_EXIF_DATETIME = re.compile(
    r"^(?P<year>\d{4}):(?P<month>\d{2}):(?P<day>\d{2})(?P<rest>[ T].*)$"
)


@dataclass(frozen=True, slots=True)
class MetadataProfile:
    """Effective metadata fields and interpretation policy."""

    timezone: str = "Asia/Shanghai"
    time_tags: tuple[str, ...] = (
        "XMP:DateTimeOriginal",
        "QuickTime:CreateDate",
        "Composite:SubSecCreateDate",
        "XMP:CreateDate",
        "EXIF:DateTimeOriginal",
        "File:FileModifyDate",
    )
    latitude_tags: tuple[str, ...] = (
        "XMP:GPSLatitude",
        "Composite:GPSLatitude",
        "EXIF:GPSLatitude",
    )
    longitude_tags: tuple[str, ...] = (
        "XMP:GPSLongitude",
        "Composite:GPSLongitude",
        "EXIF:GPSLongitude",
    )

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError(f"unknown metadata timezone: {self.timezone}") from error
        for name, tags in (
            ("time_tags", self.time_tags),
            ("latitude_tags", self.latitude_tags),
            ("longitude_tags", self.longitude_tags),
        ):
            if not tags or any(not tag.strip() for tag in tags):
                raise ValueError(f"metadata {name} must contain non-empty tags")

    def descriptor(self) -> str:
        return json.dumps(
            {
                "latitude_tags": self.latitude_tags,
                "longitude_tags": self.longitude_tags,
                "sidecar_precedence": _SIDECAR_SUFFIXES,
                "time_tags": self.time_tags,
                "timezone": self.timezone,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


@dataclass(frozen=True, slots=True)
class MetadataOutcome:
    work: WorkRecord
    observations: tuple[dict[str, Any], ...]
    reused: bool


class MetadataExtractionError(RuntimeError):
    """ExifTool could not return a trustworthy local metadata response."""


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


class MetadataProducer:
    """Extract bounded structured facts without creating a second cache authority."""

    def __init__(
        self,
        database_path: Path,
        *,
        executable: str = "exiftool",
        command_runner: CommandRunner | None = None,
        exiftool_version: str | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.validity = SourceValidityStore(self.database_path)
        self.work = WorkStore(self.database_path)
        self.accounting = AccountingStore(self.database_path)
        self.executable = executable
        self._run = command_runner or _run_command
        self.exiftool_version = exiftool_version or _read_exiftool_version(
            executable, self._run
        )

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        *,
        profile: MetadataProfile = MetadataProfile(),
        owner: str = "builtin-source-metadata",
    ) -> MetadataOutcome:
        subject = _validated_relative_path(relative_path)
        inputs = self._input_paths(run_id, subject)
        proofs = tuple(self.validity.prove(run_id, path) for path in inputs)
        dependencies: list[WorkDependency] = []
        for proof in proofs:
            dependencies.extend(
                (
                    source_revision_dependency(
                        proof.dataset_id, proof.relative_path, proof.source_revision
                    ),
                    proof.dependency(),
                )
            )
        dependencies.extend(
            (
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "subject_relative_path",
                    subject.as_posix(),
                ),
                WorkDependency(
                    DependencyKind.PARAMETER,
                    "metadata_profile",
                    profile.descriptor(),
                ),
                WorkDependency(
                    DependencyKind.ENVIRONMENT,
                    "exiftool_version",
                    self.exiftool_version,
                ),
            )
        )
        spec = WorkSpec(
            capability="source-metadata",
            producer_identity="builtin-exiftool-metadata-v1",
            dependencies=tuple(dependencies),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            return MetadataOutcome(record, _work_observations(record.output), True)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return MetadataOutcome(record, (), False)

        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=5),
            work_id=record.work_id,
        )
        if not leases:
            return MetadataOutcome(self.work.get_work(record.work_id), (), False)
        lease = leases[0]
        try:
            records = self._extract(proofs, profile)
            observations = select_metadata_observations(
                records,
                subject=subject,
                source_precedence=_source_precedence(proofs, subject),
                profile=profile,
            )
            _verify_proofs(self.validity, run_id, proofs)
            completed = self.work.succeed_work(
                lease,
                {
                    "observations": observations,
                    "producer": {
                        "identity": spec.producer_identity,
                        "exiftool_version": self.exiftool_version,
                    },
                    "subject": {"relative_path": subject.as_posix()},
                },
            )
            return MetadataOutcome(completed, tuple(observations), False)
        except SourceChangedDuringRead:
            self.work.invalidate_work(
                record.work_id, "source changed during metadata extraction"
            )
            return MetadataOutcome(self.work.get_work(record.work_id), (), False)
        except (
            MetadataExtractionError,
            OSError,
            subprocess.SubprocessError,
            ValueError,
        ) as error:
            failed = self.work.fail_work(
                lease,
                error_code="metadata_extraction_failed",
                message=str(error) or type(error).__name__,
                retryable=False,
            )
            return MetadataOutcome(failed, (), False)

    def _input_paths(self, run_id: str, subject: Path) -> tuple[Path, ...]:
        family = association_key(subject)
        sidecars = sorted(
            (
                item.relative_path
                for item in self.accounting.get_run_items(run_id)
                if item.relative_path != subject
                and item.relative_path.suffix.casefold() in _SIDECAR_SUFFIXES
                and association_key(item.relative_path) == family
            ),
            key=lambda path: (
                _SIDECAR_SUFFIXES.index(path.suffix.casefold()),
                path.as_posix(),
            ),
        )
        return (subject, *sidecars)

    def _extract(
        self,
        proofs: tuple[SourceContentProof, ...],
        profile: MetadataProfile,
    ) -> list[dict[str, Any]]:
        tags = tuple(
            dict.fromkeys(
                (
                    *profile.time_tags,
                    *profile.latitude_tags,
                    *profile.longitude_tags,
                    "EXIF:Make",
                    "XMP:Make",
                    "EXIF:Model",
                    "XMP:Model",
                    "EXIF:Orientation",
                    "XMP:Orientation",
                    "File:MIMEType",
                )
            )
        )
        command = [
            self.executable,
            "-j",
            "-G",
            "-n",
            "-api",
            "largefilesupport=1",
            *(f"-{tag}" for tag in tags),
            "--",
            *(str(proof.source_path) for proof in proofs),
        ]
        completed = self._run(command)
        if completed.returncode != 0:
            message = completed.stderr.strip() or "ExifTool exited unsuccessfully"
            raise MetadataExtractionError(message)
        try:
            decoded = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise MetadataExtractionError("ExifTool returned invalid JSON") from error
        if not isinstance(decoded, list) or any(
            not isinstance(row, dict) for row in decoded
        ):
            raise MetadataExtractionError(
                "ExifTool returned an unexpected response shape"
            )
        paths = {
            str(proof.source_path.resolve()): proof.relative_path for proof in proofs
        }
        records: list[dict[str, Any]] = []
        for row in decoded:
            source_file = row.get("SourceFile")
            if not isinstance(source_file, str):
                continue
            relative = paths.get(str(Path(source_file).resolve()))
            if relative is None:
                continue
            records.append({"relative_path": relative.as_posix(), "fields": row})
        if not records:
            raise MetadataExtractionError(
                "ExifTool returned no requested source records"
            )
        return records


def select_metadata_observations(
    records: Sequence[Mapping[str, Any]],
    *,
    subject: Path,
    source_precedence: Sequence[Path],
    profile: MetadataProfile = MetadataProfile(),
) -> list[dict[str, Any]]:
    """Select candidate facts while retaining the exact file and tag basis."""

    indexed = {
        str(record.get("relative_path")): record.get("fields")
        for record in records
        if isinstance(record.get("fields"), Mapping)
    }
    ordered = [
        path.as_posix() for path in source_precedence if path.as_posix() in indexed
    ]
    observations = [
        _time_observation(indexed, ordered, profile),
        _gps_observation(indexed, ordered, profile),
    ]
    for name, tags in (
        ("camera_make", ("XMP:Make", "EXIF:Make")),
        ("camera_model", ("XMP:Model", "EXIF:Model")),
        ("orientation", ("XMP:Orientation", "EXIF:Orientation")),
        ("media_type", ("File:MIMEType",)),
    ):
        selected = _first_value(indexed, ordered, tags)
        if selected is None:
            observations.append({"name": name, "status": "missing"})
            continue
        relative, tag, value = selected
        observations.append(
            {
                "name": name,
                "status": "available",
                "value": value,
                "provenance": _provenance(relative, tag),
            }
        )
    return observations


def _time_observation(
    indexed: Mapping[str, Mapping[str, Any]],
    ordered: Sequence[str],
    profile: MetadataProfile,
) -> dict[str, Any]:
    saw_value = False
    for tag in profile.time_tags:
        for relative in ordered:
            value = indexed[relative].get(tag)
            if value in (None, ""):
                continue
            saw_value = True
            normalized = _normalize_datetime(value, profile.timezone)
            if normalized is None:
                continue
            iso_value, assumed = normalized
            return {
                "name": "capture_time",
                "status": "available",
                "value": iso_value,
                "provenance": {
                    **_provenance(relative, tag),
                    "timezone_assumed": assumed,
                    "timezone_policy": profile.timezone,
                },
            }
    if saw_value:
        return {
            "name": "capture_time",
            "status": "failed",
            "provenance": {"method": "exiftool", "reason": "unparseable_time"},
        }
    return {"name": "capture_time", "status": "missing"}


def _gps_observation(
    indexed: Mapping[str, Mapping[str, Any]],
    ordered: Sequence[str],
    profile: MetadataProfile,
) -> dict[str, Any]:
    latitude_value = _first_value(indexed, ordered, profile.latitude_tags)
    longitude_value = _first_value(indexed, ordered, profile.longitude_tags)
    if latitude_value is None and longitude_value is None:
        return {"name": "gps_coordinates", "status": "missing"}
    latitude = _as_numeric(latitude_value)
    longitude = _as_numeric(longitude_value)
    if latitude is None or longitude is None:
        return {
            "name": "gps_coordinates",
            "status": "failed",
            "provenance": {"method": "exiftool", "reason": "incomplete_coordinates"},
        }
    lat_relative, lat_tag, lat_value = latitude
    lon_relative, lon_tag, lon_value = longitude
    if not -90 <= lat_value <= 90 or not -180 <= lon_value <= 180:
        return {
            "name": "gps_coordinates",
            "status": "failed",
            "provenance": {"method": "exiftool", "reason": "coordinates_out_of_range"},
        }
    return {
        "name": "gps_coordinates",
        "status": "available",
        "value": {
            "datum": "WGS84",
            "latitude": lat_value,
            "longitude": lon_value,
        },
        "provenance": {
            "method": "exiftool",
            "sources": [
                {"relative_path": lat_relative, "tag": lat_tag},
                {"relative_path": lon_relative, "tag": lon_tag},
            ],
        },
    }


def _first_value(
    indexed: Mapping[str, Mapping[str, Any]],
    ordered: Sequence[str],
    tags: Sequence[str],
) -> tuple[str, str, Any] | None:
    for tag in tags:
        for relative in ordered:
            value = indexed[relative].get(tag)
            if value not in (None, ""):
                return relative, tag, value
    return None


def _as_numeric(
    selected: tuple[str, str, Any] | None,
) -> tuple[str, str, float] | None:
    if selected is None:
        return None
    relative, tag, value = selected
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return relative, tag, numeric


def _normalize_datetime(value: Any, timezone_name: str) -> tuple[str, bool] | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    if match := _EXIF_DATETIME.match(text):
        text = (
            f"{match.group('year')}-{match.group('month')}-{match.group('day')}"
            f"{match.group('rest')}"
        )
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    timezone = ZoneInfo(timezone_name)
    assumed = parsed.tzinfo is None
    normalized = (
        parsed.replace(tzinfo=timezone) if assumed else parsed.astimezone(timezone)
    )
    return normalized.isoformat(), assumed


def _source_precedence(
    proofs: Sequence[SourceContentProof], subject: Path
) -> tuple[Path, ...]:
    sidecars = tuple(
        proof.relative_path for proof in proofs if proof.relative_path != subject
    )
    return (*sidecars, subject)


def _verify_proofs(
    validity: SourceValidityStore,
    run_id: str,
    proofs: Sequence[SourceContentProof],
) -> None:
    for expected in proofs:
        observed = validity.prove(run_id, expected.relative_path)
        if observed.dependency().value != expected.dependency().value:
            raise SourceChangedDuringRead(
                f"source changed during metadata extraction: {expected.relative_path}"
            )


def _provenance(relative_path: str, tag: str) -> dict[str, Any]:
    return {
        "method": "exiftool",
        "relative_path": relative_path,
        "tag": tag,
    }


def _work_observations(output: object | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(output, Mapping):
        return ()
    observations = output.get("observations")
    if not isinstance(observations, list):
        return ()
    return tuple(dict(item) for item in observations if isinstance(item, Mapping))


def _read_exiftool_version(executable: str, runner: CommandRunner) -> str:
    try:
        completed = runner((executable, "-ver"))
    except (OSError, subprocess.SubprocessError) as error:
        raise MetadataExtractionError(f"ExifTool is unavailable: {error}") from error
    version = completed.stdout.strip()
    if completed.returncode != 0 or not version:
        raise MetadataExtractionError("ExifTool version could not be determined")
    return version


def _run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )


def _validated_relative_path(value: Path) -> Path:
    path = Path(value)
    if path.is_absolute() or path == Path(".") or ".." in path.parts:
        raise ValueError("metadata source path must stay relative to its root")
    return path


__all__ = [
    "MetadataExtractionError",
    "MetadataOutcome",
    "MetadataProducer",
    "MetadataProfile",
]
