"""Stable, provider-neutral value semantics for geographic observations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum


class MapDatum(StrEnum):
    WGS84 = "WGS84"
    GCJ02 = "GCJ02"


class GeoOperation(StrEnum):
    RESOLVE_PLACE = "resolve_place"
    REVERSE_GEOCODE = "reverse_geocode"
    NEARBY_PLACES = "nearby_places"


class GeoComponentStatus(StrEnum):
    SUCCESS = "success"
    NO_RESULT = "no_result"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"
    NOT_REQUESTED = "not_requested"


class GeoCandidateKind(StrEnum):
    ADDRESS = "address"
    PLACE = "place"


class GeoLookupError(RuntimeError):
    """Base error for one provider attempt."""

    def __init__(self, message: str, *, request_count: int = 0) -> None:
        self.request_count = request_count
        super().__init__(message)


class GeoTransientError(GeoLookupError):
    """The provider attempt may succeed when retried later."""


class GeoPermanentError(GeoLookupError):
    """The provider attempt cannot succeed without changing its inputs."""


@dataclass(frozen=True, slots=True)
class GeoCoordinate:
    latitude: float
    longitude: float
    datum: MapDatum = MapDatum.WGS84

    def __post_init__(self) -> None:
        object.__setattr__(self, "datum", MapDatum(self.datum))
        if not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")

    def value(self) -> dict[str, object]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "datum": self.datum.value,
        }


@dataclass(frozen=True, slots=True)
class GeoProviderResult:
    status: str
    provider: str
    language: str
    input_coordinate: GeoCoordinate
    provider_coordinate: GeoCoordinate
    location: Mapping[str, object] | None
    pois: tuple[Mapping[str, object], ...]
    request_count: int
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"success", "partial", "no_result", "failed"}:
            raise ValueError("unknown provider result status")
        if not self.provider or not self.language:
            raise ValueError("provider and language must be non-empty")
        if self.request_count < 0:
            raise ValueError("request_count cannot be negative")


@dataclass(frozen=True, slots=True)
class GeoLookupResult:
    status: str
    provider: str
    language: str
    input_coordinate: GeoCoordinate
    provider_coordinate: GeoCoordinate
    location: Mapping[str, object] | None
    pois: tuple[Mapping[str, object], ...]
    attempts: tuple[dict[str, object], ...]
    qualifications: tuple[dict[str, str], ...]
    observed_at: str
    error_code: str | None = None
    error_message: str | None = None

    @property
    def logical_query_count(self) -> int:
        return 1

    @property
    def provider_request_count(self) -> int:
        return sum(int(attempt["provider_requests"]) for attempt in self.attempts)

    def work_value(self) -> dict[str, object]:
        value: dict[str, object] = {
            "input_coordinate": self.input_coordinate.value(),
            "provider_coordinate": self.provider_coordinate.value(),
            "provider": self.provider,
            "language": self.language,
            "location": None if self.location is None else dict(self.location),
            "pois": [dict(poi) for poi in self.pois],
            "observed_at": self.observed_at,
            "logical_query_count": self.logical_query_count,
            "provider_request_count": self.provider_request_count,
            "attempts": list(self.attempts),
        }
        if self.error_code is not None:
            value["error"] = {
                "code": self.error_code,
                "message": self.error_message or self.error_code,
            }
        return value


@dataclass(frozen=True, slots=True)
class GeoCandidate:
    kind: GeoCandidateKind
    name: str
    formatted_address: str | None = None
    coordinate: GeoCoordinate | None = None
    distance_meters: float | None = None
    components: tuple[tuple[str, str], ...] = ()
    provider_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", GeoCandidateKind(self.kind))
        if not self.name or self.name.isspace():
            raise ValueError("candidate name must be non-empty")
        if self.distance_meters is not None and self.distance_meters < 0:
            raise ValueError("distance_meters cannot be negative")

    def value(self) -> dict[str, object]:
        value: dict[str, object] = {
            "kind": self.kind.value,
            "name": self.name,
            "components": {key: item for key, item in self.components},
        }
        if self.formatted_address is not None:
            value["formatted_address"] = self.formatted_address
        if self.coordinate is not None:
            value["coordinate"] = self.coordinate.value()
        if self.distance_meters is not None:
            value["distance_meters"] = self.distance_meters
        if self.provider_ref is not None:
            value["provider_ref"] = self.provider_ref
        return value


@dataclass(frozen=True, slots=True)
class GeoComponentResult:
    operation: GeoOperation
    status: GeoComponentStatus
    subject_refs: tuple[str, ...]
    coordinate: GeoCoordinate
    candidates: tuple[GeoCandidate, ...] = ()
    qualifications: tuple[Mapping[str, str], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", GeoOperation(self.operation))
        object.__setattr__(self, "status", GeoComponentStatus(self.status))
        if any(not item for item in self.subject_refs):
            raise ValueError("component subject_refs cannot contain empty values")
        if self.status is GeoComponentStatus.SUCCESS and not self.candidates:
            raise ValueError("a successful component requires candidates")
        if self.status is GeoComponentStatus.NOT_REQUESTED and self.candidates:
            raise ValueError("an unrequested component cannot contain candidates")

    def value(self) -> dict[str, object]:
        return {
            "operation": self.operation.value,
            "status": self.status.value,
            "subject_refs": list(self.subject_refs),
            "coordinate": self.coordinate.value(),
            "candidates": [candidate.value() for candidate in self.candidates],
            "qualifications": [dict(item) for item in self.qualifications],
        }


@dataclass(frozen=True, slots=True)
class GeoProviderAttempt:
    provider: str
    operation: GeoOperation
    status: GeoComponentStatus
    input_coordinate: GeoCoordinate
    provider_coordinate: GeoCoordinate
    provider_requests: int
    billable_units: int | None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", GeoOperation(self.operation))
        object.__setattr__(self, "status", GeoComponentStatus(self.status))
        if not self.provider or self.provider.isspace():
            raise ValueError("provider must be non-empty")
        if self.provider_requests < 0:
            raise ValueError("provider_requests cannot be negative")
        if self.billable_units is not None and self.billable_units < 0:
            raise ValueError("billable_units cannot be negative")
        if self.status is GeoComponentStatus.NOT_REQUESTED:
            raise ValueError("a provider attempt cannot be not_requested")

    def value(self) -> dict[str, object]:
        value: dict[str, object] = {
            "provider": self.provider,
            "operation": self.operation.value,
            "status": self.status.value,
            "input_coordinate": self.input_coordinate.value(),
            "provider_coordinate": self.provider_coordinate.value(),
            "provider_requests": self.provider_requests,
            "billable_units": self.billable_units,
        }
        if self.error_code is not None:
            value["error_code"] = self.error_code
        if self.error_message is not None:
            value["error_message"] = self.error_message
        return value
