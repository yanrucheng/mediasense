"""Reusable GPX location candidates derived from local PreCheck observations."""

from __future__ import annotations

from bisect import bisect_left
from contextlib import AbstractContextManager, nullcontext
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from operator import attrgetter
import sys
from threading import Lock
from typing import Any, Mapping, Sequence

import gpxpy
from gpxpy.gpx import GPXException

from ._fingerprint import SourceChangedDuringRead
from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    source_revision_dependency,
    upstream_dependency,
)
from .source_validity import SourceContentProof, SourceValidityStore
from .work import WorkStore

PRODUCER_IDENTITY = "builtin-gpx-match-v1"


@dataclass(frozen=True, slots=True)
class GPXMatchProfile:
    max_time_difference_seconds: float = 3 * 60 * 60
    interpolate: bool = True

    def __post_init__(self) -> None:
        if self.max_time_difference_seconds <= 0:
            raise ValueError("GPX maximum time difference must be positive")


@dataclass(frozen=True, slots=True)
class GPXTrackPoint:
    timestamp: float
    latitude: float
    longitude: float


@dataclass(frozen=True, slots=True)
class GPXTrackSegment:
    relative_path: Path
    segment_index: int
    points: tuple[GPXTrackPoint, ...]


@dataclass(frozen=True, slots=True)
class GPXMatch:
    relative_path: Path
    segment_index: int
    latitude: float
    longitude: float
    method: str
    time_error_seconds: float
    point_times: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class GPXOutcome:
    work: WorkRecord
    observations: tuple[dict[str, Any], ...]
    reused: bool


class GPXMatchProducer:
    """Match one validated capture time against explicitly adopted local tracks."""

    def __init__(
        self,
        database_path: Path,
        *,
        max_cache_bytes: int = 64 * 1024**2,
        memory_admission: Callable[[int], AbstractContextManager] | None = None,
    ) -> None:
        if max_cache_bytes < 0:
            raise ValueError("GPX preparation cache bound must be nonnegative")
        self.database_path = Path(database_path)
        self.validity = SourceValidityStore(self.database_path)
        self.work = WorkStore(self.database_path)
        self.max_cache_bytes = max_cache_bytes
        self._memory_admission = memory_admission
        self._preparation_lock = Lock()
        self._prepared_key: tuple | None = None
        self._prepared_segments: tuple[GPXTrackSegment, ...] = ()

    def memory_estimate(self, proofs: Sequence[SourceContentProof]) -> int:
        """Conservative admission estimate, not an observed RSS guarantee."""
        size = sum(proof.size_bytes for proof in proofs)
        # XML trees, decoded text and point objects can coexist during parsing.
        return self.max_cache_bytes + 8 * 1024**2 + size * 64

    def _prepare_tracks(self, run_id: str, proofs: Sequence[SourceContentProof]):
        key = tuple(
            (
                p.dataset_id,
                p.reuse_domain,
                p.relative_path,
                p.source_revision,
                p.algorithm,
                p.digest,
                p.size_bytes,
                p.source_path,
            )
            for p in proofs
        )
        # One retained set per producer. Concurrent source Work shares a cold
        # parse; retained state dies with the phase and owns no product authority.
        with self._preparation_lock:
            if key == self._prepared_key:
                return self._prepared_segments, ()
            self._prepared_key, self._prepared_segments = None, ()
            segments, failures = parse_gpx_sources(proofs)
            _verify_proofs(self.validity, run_id, proofs)
            # I/O failures must be attempted again even if ordinary stat identity
            # is unchanged (e.g. access restored). Do not memoize partial failures.
            if not failures and _prepared_size(segments) <= self.max_cache_bytes:
                self._prepared_key, self._prepared_segments = key, segments
            return segments, failures

    def produce(
        self,
        run_id: str,
        metadata_work_id: str,
        gpx_paths: Sequence[Path],
        *,
        profile: GPXMatchProfile = GPXMatchProfile(),
        owner: str = "builtin-gpx-location-candidate",
    ) -> GPXOutcome:
        metadata_work = self._metadata_work(run_id, metadata_work_id)
        subject = _metadata_subject(metadata_work)
        metadata_observations = _work_observations(metadata_work.output)
        embedded_gps = _observation(metadata_observations, "gps_coordinates")
        capture_time = _observation(metadata_observations, "capture_time")

        if embedded_gps is not None and embedded_gps.get("status") == "available":
            spec = self._spec(metadata_work, subject, (), profile)
            return self._complete_without_tracks(
                run_id,
                spec,
                {
                    "name": "gpx_coordinates",
                    "status": "not_applicable",
                    "provenance": {
                        "method": "gpx_match_v1",
                        "reason": "embedded_gps_available",
                    },
                },
                owner,
            )
        target_time = _capture_timestamp(capture_time)
        if target_time is None:
            spec = self._spec(metadata_work, subject, (), profile)
            return self._complete_without_tracks(
                run_id,
                spec,
                {
                    "name": "gpx_coordinates",
                    "status": "not_checked",
                    "provenance": {
                        "method": "gpx_match_v1",
                        "reason": "capture_time_unavailable",
                    },
                },
                owner,
            )

        normalized_paths = tuple(
            sorted({_validated_gpx_path(path) for path in gpx_paths})
        )
        if not normalized_paths:
            raise ValueError(
                "GPX matching requires at least one adopted GPX Source Item"
            )
        proofs = tuple(self.validity.prove(run_id, path) for path in normalized_paths)
        spec = self._spec(metadata_work, subject, proofs, profile)
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            return GPXOutcome(record, _work_observations(record.output), True)
        if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
            return GPXOutcome(record, (), False)
        # Reusable Work and metadata-only outcomes need no parsing memory. Each
        # active match claim covers the retained cache plus possible cold parse;
        # the phase owns the producer lifetime and releases it before other work.
        admission = (
            self._memory_admission(self.memory_estimate(proofs))
            if self._memory_admission is not None
            else nullcontext()
        )
        with admission:
            return self._execute_match(
                run_id, record, proofs, target_time, profile, subject, owner
            )

    def _execute_match(
        self, run_id, record, proofs, target_time, profile, subject, owner
    ):
        spec = record.spec
        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=5),
            work_id=record.work_id,
        )
        if not leases:
            return GPXOutcome(self.work.get_work(record.work_id), (), False)
        lease = leases[0]
        try:
            segments, failures = self._prepare_tracks(run_id, proofs)
            match = match_gpx_segments(segments, target_time, profile)
            observation = _match_observation(
                match,
                proofs=proofs,
                target_time=target_time,
                failures=failures,
                profile=profile,
            )
            _verify_proofs(self.validity, run_id, proofs)
            completed = self.work.succeed_work(
                lease,
                {
                    "observations": [observation],
                    "producer": {"identity": spec.producer_identity},
                    "subject": {"relative_path": subject.as_posix()},
                },
            )
            return GPXOutcome(completed, (observation,), False)
        except SourceChangedDuringRead:
            self.work.invalidate_work(
                record.work_id, "GPX source changed during matching"
            )
            return GPXOutcome(self.work.get_work(record.work_id), (), False)
        except (OSError, ValueError) as error:
            failed = self.work.fail_work(
                lease,
                error_code="gpx_matching_failed",
                message=str(error) or type(error).__name__,
                retryable=False,
            )
            return GPXOutcome(failed, (), False)

    def _metadata_work(self, run_id: str, work_id: str) -> WorkRecord:
        try:
            record = self.work.get_run_work(run_id, work_id)
        except KeyError as error:
            raise ValueError(
                "GPX matching requires metadata Work attached to this run"
            ) from error
        if record.spec.capability != "source-metadata":
            raise ValueError("GPX matching requires metadata Work attached to this run")
        if record.status is not WorkStatus.SUCCEEDED:
            raise ValueError("GPX matching requires successful metadata Work")
        return record

    def _spec(
        self,
        metadata_work: WorkRecord,
        subject: Path,
        proofs: Sequence[SourceContentProof],
        profile: GPXMatchProfile,
    ) -> WorkSpec:
        dependencies: list[WorkDependency] = [
            upstream_dependency(metadata_work),
            WorkDependency(
                DependencyKind.PARAMETER,
                "subject_relative_path",
                subject.as_posix(),
            ),
            WorkDependency(
                DependencyKind.PARAMETER,
                "gpx_match_profile",
                (
                    f"max_time_difference_seconds={profile.max_time_difference_seconds};"
                    f"interpolate={str(profile.interpolate).lower()};"
                    "datum=WGS84"
                ),
            ),
        ]
        for proof in proofs:
            dependencies.extend(
                (
                    source_revision_dependency(
                        proof.dataset_id, proof.relative_path, proof.source_revision
                    ),
                    proof.dependency(),
                )
            )
        return WorkSpec(
            capability="gpx-location-candidate",
            producer_identity=PRODUCER_IDENTITY,
            dependencies=tuple(dependencies),
        )

    def _complete_without_tracks(
        self,
        run_id: str,
        spec: WorkSpec,
        observation: dict[str, Any],
        owner: str,
    ) -> GPXOutcome:
        record = self.work.ensure_work(run_id, spec)
        if record.status is WorkStatus.SUCCEEDED:
            return GPXOutcome(record, _work_observations(record.output), True)
        leases = self.work.claim_ready_work(
            run_id,
            owner,
            lease_duration=timedelta(minutes=1),
            work_id=record.work_id,
        )
        if not leases:
            return GPXOutcome(self.work.get_work(record.work_id), (), False)
        completed = self.work.succeed_work(
            leases[0],
            {
                "observations": [observation],
                "producer": {"identity": spec.producer_identity},
                "subject": {
                    "relative_path": next(
                        dependency.value
                        for dependency in spec.dependencies
                        if dependency.key == "subject_relative_path"
                    )
                },
            },
        )
        return GPXOutcome(completed, (observation,), False)


def parse_gpx_sources(
    proofs: Sequence[SourceContentProof],
) -> tuple[tuple[GPXTrackSegment, ...], tuple[dict[str, str], ...]]:
    segments: list[GPXTrackSegment] = []
    failures: list[dict[str, str]] = []
    for proof in proofs:
        try:
            parsed = gpxpy.parse(proof.source_path.read_text(encoding="utf-8"))
        except (GPXException, OSError, UnicodeError, ValueError) as error:
            failures.append(
                {
                    "relative_path": proof.relative_path.as_posix(),
                    "reason": str(error) or type(error).__name__,
                }
            )
            continue
        segment_index = 0
        for track in parsed.tracks:
            for segment in track.segments:
                points: list[GPXTrackPoint] = []
                for point in segment.points:
                    if point.time is None or point.time.tzinfo is None:
                        continue
                    try:
                        latitude = float(point.latitude)
                        longitude = float(point.longitude)
                        timestamp = point.time.timestamp()
                    except (OSError, TypeError, ValueError):
                        continue
                    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                        points.append(GPXTrackPoint(timestamp, latitude, longitude))
                points.sort(key=lambda point: point.timestamp)
                if points:
                    segments.append(
                        GPXTrackSegment(
                            proof.relative_path,
                            segment_index,
                            tuple(points),
                        )
                    )
                segment_index += 1
    return tuple(segments), tuple(failures)


def match_gpx_segments(
    segments: Sequence[GPXTrackSegment],
    target_timestamp: float,
    profile: GPXMatchProfile = GPXMatchProfile(),
) -> GPXMatch | None:
    candidates: list[GPXMatch] = []
    for segment in segments:
        index = bisect_left(
            segment.points, target_timestamp, key=attrgetter("timestamp")
        )
        if profile.interpolate and 0 < index < len(segment.points):
            left = segment.points[index - 1]
            right = segment.points[index]
            left_diff = target_timestamp - left.timestamp
            right_diff = right.timestamp - target_timestamp
            if (
                left.timestamp < right.timestamp
                and left_diff <= profile.max_time_difference_seconds
                and right_diff <= profile.max_time_difference_seconds
            ):
                factor = left_diff / (right.timestamp - left.timestamp)
                candidates.append(
                    GPXMatch(
                        segment.relative_path,
                        segment.segment_index,
                        left.latitude + factor * (right.latitude - left.latitude),
                        left.longitude + factor * (right.longitude - left.longitude),
                        "linear_interpolation",
                        min(left_diff, right_diff),
                        (left.timestamp, right.timestamp),
                    )
                )
        for point_index in {index - 1, index}:
            if 0 <= point_index < len(segment.points):
                point = segment.points[point_index]
                difference = abs(point.timestamp - target_timestamp)
                if difference <= profile.max_time_difference_seconds:
                    candidates.append(
                        GPXMatch(
                            segment.relative_path,
                            segment.segment_index,
                            point.latitude,
                            point.longitude,
                            "nearest_point",
                            difference,
                            (point.timestamp,),
                        )
                    )
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            item.time_error_seconds,
            0 if item.method == "linear_interpolation" else 1,
            item.relative_path.as_posix(),
            item.segment_index,
            item.point_times,
        ),
    )


def _prepared_size(segments: Sequence[GPXTrackSegment]) -> int:
    # Only immutable points/segments are retained, never the XML tree or source
    # text. Include the Python containers and scalar objects in the cache bound.
    return sys.getsizeof(segments) + sum(
        sys.getsizeof(segment)
        + sys.getsizeof(segment.relative_path)
        + sys.getsizeof(segment.relative_path.as_posix())
        + sys.getsizeof(segment.segment_index)
        + sys.getsizeof(segment.points)
        + sum(
            sys.getsizeof(point)
            + sys.getsizeof(point.timestamp)
            + sys.getsizeof(point.latitude)
            + sys.getsizeof(point.longitude)
            for point in segment.points
        )
        for segment in segments
    )


def _match_observation(
    match: GPXMatch | None,
    *,
    proofs: Sequence[SourceContentProof],
    target_time: float,
    failures: Sequence[Mapping[str, str]],
    profile: GPXMatchProfile,
) -> dict[str, Any]:
    sources = [{"relative_path": proof.relative_path.as_posix()} for proof in proofs]
    if match is None:
        status = "failed" if failures and len(failures) == len(proofs) else "missing"
        reason = (
            "no_valid_gpx_points" if status == "failed" else "no_match_within_limit"
        )
        observation: dict[str, Any] = {
            "name": "gpx_coordinates",
            "status": status,
            "provenance": {
                "method": "gpx_match_v1",
                "reason": reason,
                "max_time_difference_seconds": profile.max_time_difference_seconds,
                "sources": sources,
            },
        }
        if failures and len(failures) < len(proofs):
            observation["qualifications"] = [_partial_gpx_qualification(failures)]
        return observation
    observation = {
        "name": "gpx_coordinates",
        "status": "available",
        "value": {
            "datum": "WGS84",
            "latitude": match.latitude,
            "longitude": match.longitude,
        },
        "provenance": {
            "method": match.method,
            "relative_path": match.relative_path.as_posix(),
            "segment_index": match.segment_index,
            "sources": sources,
            "target_timestamp": target_time,
            "time_error_seconds": match.time_error_seconds,
        },
    }
    if failures:
        observation["qualifications"] = [_partial_gpx_qualification(failures)]
    return observation


def _partial_gpx_qualification(
    failures: Sequence[Mapping[str, str]],
) -> dict[str, str]:
    return {
        "code": "gpx_inputs_partial",
        "effect": "limits_interpretation",
        "message": f"{len(failures)} adopted GPX input(s) could not be parsed.",
    }


def _metadata_subject(record: WorkRecord) -> Path:
    if not isinstance(record.output, Mapping):
        raise ValueError("metadata Work has no structured output")
    subject = record.output.get("subject")
    if not isinstance(subject, Mapping) or not isinstance(
        subject.get("relative_path"), str
    ):
        raise ValueError("metadata Work has no subject path")
    return Path(str(subject["relative_path"]))


def _capture_timestamp(observation: Mapping[str, Any] | None) -> float | None:
    if observation is None or observation.get("status") != "available":
        return None
    value = observation.get("value")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.timestamp()


def _observation(
    observations: Sequence[Mapping[str, Any]], name: str
) -> Mapping[str, Any] | None:
    return next((item for item in observations if item.get("name") == name), None)


def _work_observations(output: object | None) -> tuple[dict[str, Any], ...]:
    if not isinstance(output, Mapping) or not isinstance(
        output.get("observations"), list
    ):
        return ()
    return tuple(
        dict(item) for item in output["observations"] if isinstance(item, Mapping)
    )


def _verify_proofs(
    validity: SourceValidityStore,
    run_id: str,
    proofs: Sequence[SourceContentProof],
) -> None:
    for expected in proofs:
        observed = validity.prove(run_id, expected.relative_path)
        if observed.dependency().value != expected.dependency().value:
            raise SourceChangedDuringRead(
                f"GPX source changed during matching: {expected.relative_path}"
            )


def _validated_gpx_path(value: Path) -> Path:
    path = Path(value)
    if (
        path.is_absolute()
        or path == Path(".")
        or ".." in path.parts
        or path.suffix.casefold() != ".gpx"
    ):
        raise ValueError("adopted GPX path must be a relative .gpx Source Item")
    return path


__all__ = [
    "GPXMatch",
    "GPXMatchProducer",
    "GPXMatchProfile",
    "GPXOutcome",
    "GPXTrackPoint",
    "GPXTrackSegment",
    "match_gpx_segments",
    "parse_gpx_sources",
]
