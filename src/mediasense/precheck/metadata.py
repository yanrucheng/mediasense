"""Local ExifTool metadata observations for reusable PreCheck Work."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
from threading import Event, Lock, Thread
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ._exiftool import ExifToolCancelled, StayOpenExifTool
from ._fingerprint import SourceChangedDuringRead
from ._work_types import (
    DependencyKind,
    LeaseLost,
    WorkDependency,
    WorkLease,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
)
from .accounting import AccountingStore
from .source_validity import SourceContentProof, SourceValidityStore
from .work import WorkStore


_SIDECAR_SUFFIXES = (".xmp", ".exif", ".json", ".xml")
_EXIF_DATETIME = re.compile(
    r"^(?P<year>\d{4}):(?P<month>\d{2}):(?P<day>\d{2})(?P<rest>[ T].*)$"
)


@dataclass(frozen=True, slots=True)
class MetadataProfile:
    """Effective metadata fields and interpretation policy."""

    profile_id: str = "index-v1"
    timezone: str = "Asia/Shanghai"
    time_tags: tuple[str, ...] = (
        "XMP:DateTimeOriginal",
        "Composite:SubSecDateTimeOriginal",
        "QuickTime:CreationDate",
        "QuickTime:DateTimeOriginal",
        "EXIF:DateTimeOriginal",
        "Composite:SubSecCreateDate",
        "XMP:CreateDate",
        "QuickTime:CreateDate",
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
        if not self.profile_id.strip():
            raise ValueError("metadata profile_id must be non-empty")
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
                "profile_id": self.profile_id,
                "sidecar_precedence": _SIDECAR_SUFFIXES,
                "time_tags": self.time_tags,
                "timezone": self.timezone,
                "time_interpretation": "field-semantics-v2",
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


@dataclass(frozen=True, slots=True)
class _PreparedMetadata:
    subject: Path
    proofs: tuple[SourceContentProof, ...]
    spec: WorkSpec
    record: WorkRecord
    lease: WorkLease | None = None


class MetadataExtractionError(RuntimeError):
    """ExifTool could not return a trustworthy local metadata response."""


class MetadataLeaseRenewalError(RuntimeError):
    """The batch heartbeat could not retain its still-active Work leases."""


CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]
Clock = Callable[[], datetime]


class _MetadataLeaseHeartbeat:
    """Keep a batch's still-active item leases alive through recursive isolation."""

    def __init__(
        self,
        work: WorkStore,
        prepared: tuple[_PreparedMetadata, ...],
        *,
        lease_duration: timedelta,
        renew_interval: float,
        clock: Clock,
    ) -> None:
        self._work = work
        self._lease_duration = lease_duration
        self._renew_interval = renew_interval
        self._clock = clock
        self._lock = Lock()
        self._stop = Event()
        self._error: BaseException | None = None
        self._leases = {
            item.lease.work_id: item.lease
            for item in prepared
            if item.lease is not None
        }
        self._thread = Thread(
            target=self._run,
            name="mediasense-metadata-lease-heartbeat",
            daemon=True,
        )

    def __enter__(self) -> _MetadataLeaseHeartbeat:
        self.renew_now()
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self.stop()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join()

    def renew_now(self) -> None:
        with self._lock:
            self._raise_if_failed()
            try:
                observed_at = self._clock()
                for work_id, lease in tuple(self._leases.items()):
                    self._leases[work_id] = self._work.renew_lease(
                        lease,
                        lease_duration=self._lease_duration,
                        now=observed_at,
                    )
            except BaseException as error:
                self._record_renewal_failure(error)

    def succeed(self, item: _PreparedMetadata, output: object) -> WorkRecord:
        with self._lock:
            lease = self._active_lease(item)
            observed_at = self._clock()
            try:
                lease = self._work.renew_lease(
                    lease,
                    lease_duration=self._lease_duration,
                    now=observed_at,
                )
            except BaseException as error:
                self._record_renewal_failure(error)
            completed = self._work.succeed_work(lease, output, now=observed_at)
            self._leases.pop(lease.work_id, None)
            return completed

    def fail(
        self,
        item: _PreparedMetadata,
        *,
        error_code: str,
        message: str,
        retryable: bool,
    ) -> WorkRecord:
        with self._lock:
            lease = self._active_lease(item)
            failed = self._work.fail_work(
                lease,
                error_code=error_code,
                message=message,
                retryable=retryable,
                now=self._clock(),
            )
            self._leases.pop(lease.work_id, None)
            return failed

    def invalidate(self, item: _PreparedMetadata, reason: str) -> WorkRecord:
        with self._lock:
            lease = self._active_lease(item)
            self._work.invalidate_work(lease.work_id, reason, now=self._clock())
            self._leases.pop(lease.work_id, None)
            return self._work.get_work(lease.work_id)

    def fail_active(self, *, error_code: str, message: str) -> None:
        self.stop()
        cleanup_errors: list[BaseException] = []
        with self._lock:
            for work_id, lease in tuple(self._leases.items()):
                try:
                    self._work.fail_work(
                        lease,
                        error_code=error_code,
                        message=message,
                        retryable=True,
                        now=self._clock(),
                    )
                except LeaseLost as error:
                    record = self._work.get_work(work_id)
                    if record.status is WorkStatus.RUNNING:
                        cleanup_errors.append(error)
                        continue
                except BaseException as error:
                    cleanup_errors.append(error)
                    continue
                self._leases.pop(work_id, None)
        if cleanup_errors:
            raise RuntimeError(
                "metadata active leases did not converge to retryable state"
            ) from cleanup_errors[0]

    def _run(self) -> None:
        while not self._stop.wait(self._renew_interval):
            try:
                self.renew_now()
            except MetadataLeaseRenewalError:
                return

    def _active_lease(self, item: _PreparedMetadata) -> WorkLease:
        self._raise_if_failed()
        if item.lease is None or item.lease.work_id not in self._leases:
            raise RuntimeError("metadata Work lease is no longer active")
        return self._leases[item.lease.work_id]

    def _raise_if_failed(self) -> None:
        if self._error is not None:
            raise MetadataLeaseRenewalError(
                "metadata lease renewal failed"
            ) from self._error

    def _record_renewal_failure(self, error: BaseException) -> None:
        self._error = error
        self._stop.set()
        raise MetadataLeaseRenewalError("metadata lease renewal failed") from error


class MetadataProducer:
    """Extract bounded structured facts without creating a second cache authority."""

    def __init__(
        self,
        database_path: Path,
        *,
        executable: str = "exiftool",
        command_runner: CommandRunner | None = None,
        exiftool_version: str | None = None,
        should_continue: Callable[[], bool] | None = None,
        lease_duration: timedelta = timedelta(minutes=5),
        lease_renew_interval: float = 60.0,
        clock: Clock | None = None,
    ) -> None:
        if lease_duration <= timedelta(0):
            raise ValueError("metadata lease_duration must be positive")
        if lease_renew_interval <= 0:
            raise ValueError("metadata lease_renew_interval must be positive")
        if lease_renew_interval >= lease_duration.total_seconds():
            raise ValueError("metadata lease renewal must precede lease expiry")
        self.database_path = Path(database_path)
        self.validity = SourceValidityStore(self.database_path)
        self.work = WorkStore(self.database_path)
        self.accounting = AccountingStore(self.database_path)
        self.executable = executable
        self.lease_duration = lease_duration
        self.lease_renew_interval = lease_renew_interval
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._owned_runner = (
            None
            if command_runner is not None
            else StayOpenExifTool(
                executable,
                should_continue=should_continue,
            )
        )
        self._run = command_runner or self._owned_runner
        assert self._run is not None
        self.exiftool_version = exiftool_version or _read_exiftool_version(
            executable, self._run
        )

    def close(self) -> None:
        if self._owned_runner is not None:
            self._owned_runner.close()

    def __enter__(self) -> MetadataProducer:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def produce(
        self,
        run_id: str,
        relative_path: Path,
        *,
        profile: MetadataProfile = MetadataProfile(),
        owner: str = "builtin-source-metadata",
    ) -> MetadataOutcome:
        subject = _validated_relative_path(relative_path)
        return self.produce_many(
            run_id,
            (subject,),
            profile=profile,
            owner=owner,
        )[subject]

    def produce_many(
        self,
        run_id: str,
        relative_paths: Iterable[Path],
        *,
        profile: MetadataProfile = MetadataProfile(),
        owner: str = "builtin-source-metadata",
    ) -> dict[Path, MetadataOutcome]:
        subjects = tuple(_validated_relative_path(path) for path in relative_paths)
        if len(set(subjects)) != len(subjects):
            raise ValueError("metadata batch subjects must be unique")
        outcomes: dict[Path, MetadataOutcome] = {}
        pending: list[_PreparedMetadata] = []
        for subject in subjects:
            prepared = self._prepare(run_id, subject, profile=profile)
            if isinstance(prepared, MetadataOutcome):
                outcomes[subject] = prepared
            else:
                pending.append(prepared)
        ready: list[_PreparedMetadata] = []
        for item in pending:
            leases = self.work.claim_ready_work(
                run_id,
                owner,
                lease_duration=self.lease_duration,
                work_id=item.record.work_id,
                now=self._clock(),
            )
            if leases:
                ready.append(replace(item, lease=leases[0]))
            else:
                outcomes[item.subject] = MetadataOutcome(
                    self.work.get_work(item.record.work_id), (), False
                )
        if ready:
            outcomes.update(self._produce_prepared(run_id, tuple(ready), profile))
        return outcomes

    def _prepare(
        self,
        run_id: str,
        subject: Path,
        *,
        profile: MetadataProfile,
    ) -> _PreparedMetadata | MetadataOutcome:
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
            producer_identity="builtin-field-aware-exiftool-metadata-v1",
            dependencies=tuple(dependencies),
        )
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            return MetadataOutcome(record, _work_observations(record.output), True)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return MetadataOutcome(record, (), False)

        return _PreparedMetadata(subject, proofs, spec, record)

    def _produce_prepared(
        self,
        run_id: str,
        prepared: tuple[_PreparedMetadata, ...],
        profile: MetadataProfile,
    ) -> dict[Path, MetadataOutcome]:
        heartbeat = _MetadataLeaseHeartbeat(
            self.work,
            prepared,
            lease_duration=self.lease_duration,
            renew_interval=self.lease_renew_interval,
            clock=self._clock,
        )
        try:
            with heartbeat:
                return self._produce_active(run_id, prepared, profile, heartbeat)
        except ExifToolCancelled:
            heartbeat.fail_active(
                error_code="metadata_cancelled",
                message="metadata extraction was cancelled",
            )
            raise
        except MetadataLeaseRenewalError as error:
            heartbeat.fail_active(
                error_code="metadata_lease_renewal_failed",
                message=str(error.__cause__ or error),
            )
            raise

    def _produce_active(
        self,
        run_id: str,
        prepared: tuple[_PreparedMetadata, ...],
        profile: MetadataProfile,
        heartbeat: _MetadataLeaseHeartbeat,
    ) -> dict[Path, MetadataOutcome]:
        heartbeat.renew_now()
        try:
            proofs = tuple(
                dict.fromkeys(proof for item in prepared for proof in item.proofs)
            )
            records = self._extract(proofs, profile)
        except ExifToolCancelled:
            raise
        except (
            MetadataExtractionError,
            OSError,
            subprocess.SubprocessError,
            ValueError,
        ) as error:
            if len(prepared) > 1 and not isinstance(error, OSError):
                midpoint = len(prepared) // 2
                return {
                    **self._produce_active(
                        run_id, prepared[:midpoint], profile, heartbeat
                    ),
                    **self._produce_active(
                        run_id, prepared[midpoint:], profile, heartbeat
                    ),
                }
            return {
                item.subject: self._fail_prepared(item, error, heartbeat)
                for item in prepared
            }

        heartbeat.renew_now()
        outcomes: dict[Path, MetadataOutcome] = {}
        for item in prepared:
            try:
                observations = select_metadata_observations(
                    records,
                    subject=item.subject,
                    source_precedence=_source_precedence(item.proofs, item.subject),
                    profile=profile,
                )
                _verify_proofs(self.validity, run_id, item.proofs)
                completed = heartbeat.succeed(
                    item,
                    {
                        "observations": observations,
                        "producer": {
                            "identity": item.spec.producer_identity,
                            "exiftool_version": self.exiftool_version,
                        },
                        "subject": {"relative_path": item.subject.as_posix()},
                    },
                )
                outcomes[item.subject] = MetadataOutcome(
                    completed, tuple(observations), False
                )
            except SourceChangedDuringRead:
                invalidated = heartbeat.invalidate(
                    item, "source changed during metadata extraction"
                )
                outcomes[item.subject] = MetadataOutcome(invalidated, (), False)
            except (
                MetadataExtractionError,
                OSError,
                subprocess.SubprocessError,
                ValueError,
            ) as error:
                outcomes[item.subject] = self._fail_prepared(item, error, heartbeat)
        return outcomes

    def _fail_prepared(
        self,
        item: _PreparedMetadata,
        error: BaseException,
        heartbeat: _MetadataLeaseHeartbeat,
    ) -> MetadataOutcome:
        failed = heartbeat.fail(
            item,
            error_code="metadata_extraction_failed",
            message=str(error) or type(error).__name__,
            retryable=False,
        )
        return MetadataOutcome(failed, (), False)

    def _input_paths(self, run_id: str, subject: Path) -> tuple[Path, ...]:
        sidecars = sorted(
            (
                path
                for path in self.accounting.associated_paths(run_id, subject)
                if path != subject and path.suffix.casefold() in _SIDECAR_SUFFIXES
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
                    "QuickTime:Make",
                    "QuickTime:Model",
                    "EXIF:OffsetTimeOriginal",
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
            "-api",
            "QuickTimeUTC=0",
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
        _time_observation(indexed, ordered, profile, subject),
        _gps_observation(indexed, ordered, profile),
    ]
    for name, tags in (
        ("camera_make", ("XMP:Make", "EXIF:Make", "QuickTime:Make")),
        ("camera_model", ("XMP:Model", "EXIF:Model", "QuickTime:Model")),
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
    subject: Path,
) -> dict[str, Any]:
    candidates = []
    for tag in profile.time_tags:
        for relative in ordered:
            value = indexed[relative].get(tag)
            if value in (None, ""):
                continue
            interpreted = value
            interpretation = "explicit_offset_or_configured_local_time"
            if tag.startswith("File:"):
                interpretation = "filesystem_modification_time_fallback"
            if tag == "EXIF:DateTimeOriginal" and isinstance(value, str):
                offset = indexed[relative].get("EXIF:OffsetTimeOriginal")
                if isinstance(offset, str) and re.fullmatch(r"[+-]\d{2}:\d{2}", offset):
                    if not re.search(r"(?:Z|[+-]\d{2}:?\d{2})$", value):
                        interpreted = value + offset
                        interpretation = "EXIF:OffsetTimeOriginal"
            normalized = _normalize_datetime(interpreted, profile.timezone)
            if (
                normalized is not None
                and normalized[1]
                and tag == "QuickTime:CreateDate"
            ):
                # ExifTool deliberately returns the unconverted integer-container
                # clock. Do not let the host's TZ or a video suffix set its meaning.
                normalized = _normalize_datetime(
                    str(value) + "+00:00", profile.timezone
                )
                assert normalized is not None
                normalized = (normalized[0], True)
                interpretation = "quicktime_integer_utc_assumption"
            candidates.append(
                {
                    "relative_path": relative,
                    "tag": tag,
                    "raw_value": value,
                    "value": normalized[0] if normalized else None,
                    "timezone_assumed": normalized[1] if normalized else None,
                    "interpretation": interpretation,
                }
            )

    # Basenames can supply a lower-confidence fallback, never overwrite a
    # parseable capture field. Directory semantics play no part in this rule.
    filename = re.search(r"(?<!\d)(\d{8})[_-]?(\d{6})(?!\d)", subject.name)
    if filename:
        try:
            naive = datetime.strptime("".join(filename.groups()), "%Y%m%d%H%M%S")
        except ValueError:
            pass
        else:
            candidates.append(
                {
                    "relative_path": subject.as_posix(),
                    "tag": "filename",
                    "raw_value": filename.group(),
                    "value": naive.replace(
                        tzinfo=ZoneInfo(profile.timezone)
                    ).isoformat(),
                    "timezone_assumed": True,
                    "interpretation": "filename_local_time_fallback",
                }
            )
    valid = [candidate for candidate in candidates if candidate["value"] is not None]
    capture = [
        candidate for candidate in valid if not candidate["tag"].startswith("File:")
    ]
    selected = next(iter(capture or valid), None)
    if selected is None and candidates:
        return {
            "name": "capture_time",
            "status": "failed",
            "provenance": {
                "method": "exiftool",
                "reason": "unparseable_time",
                "candidates": candidates,
            },
        }
    if selected is None:
        return {"name": "capture_time", "status": "missing"}
    qualifications = []
    code = None
    if selected["tag"] == "filename":
        code = "filename_time_fallback"
    elif selected["tag"].startswith("File:"):
        code = "filesystem_time_fallback"
    elif selected["timezone_assumed"]:
        code = "capture_timezone_assumed"
    if code:
        qualifications.append(
            {
                "code": code,
                "effect": "limits_interpretation",
                "message": "Capture time is interpreted using "
                + selected["interpretation"]
                + "; it is not an original offset-bearing camera timestamp.",
            }
        )
    selected_time = datetime.fromisoformat(selected["value"])
    conflicts = [
        candidate
        for candidate in capture
        if abs(
            (datetime.fromisoformat(candidate["value"]) - selected_time).total_seconds()
        )
        > 2
    ]
    if conflicts:
        qualifications.append(
            {
                "code": "capture_time_conflict",
                "effect": "limits_interpretation",
                "message": "Capture fields or filename disagree; inspect retained candidates before relying on chronology.",
            }
        )
    observation = {
        "name": "capture_time",
        "status": "available",
        "value": selected["value"],
        "provenance": {
            **_provenance(selected["relative_path"], selected["tag"]),
            "method": "filename" if selected["tag"] == "filename" else "exiftool",
            "raw_value": selected["raw_value"],
            "interpretation": selected["interpretation"],
            "timezone_assumed": selected["timezone_assumed"],
            "timezone_policy": profile.timezone,
            "candidates": candidates,
        },
    }
    if qualifications:
        observation["qualifications"] = qualifications
    return observation


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
        validity.verify(run_id, expected)


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
