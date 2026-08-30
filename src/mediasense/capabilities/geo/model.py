"""Stable, provider-neutral value semantics for geographic observations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import hashlib
import json
import re


class MapDatum(StrEnum):
    WGS84 = "WGS84"
    GCJ02 = "GCJ02"


class GeoOperation(StrEnum):
    RESOLVE_PLACE = "resolve_place"
    REVERSE_GEOCODE = "reverse_geocode"
    NEARBY_PLACES = "nearby_places"


class GeoOutcome(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NO_RESULT = "no_result"
    AUTHORIZATION_REQUIRED = "authorization_required"
    REFUSED = "refused"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"
    CANCELLED = "cancelled"


class GeoComponentStatus(StrEnum):
    SUCCESS = "success"
    NO_RESULT = "no_result"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"
    NOT_REQUESTED = "not_requested"


class GeoCandidateKind(StrEnum):
    ADDRESS = "address"
    PLACE = "place"


class GeoRetention(StrEnum):
    NONE = "none"
    CALLER_STATE = "caller_state"


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
class GeoSubject:
    subject_ref: str
    coordinate: GeoCoordinate

    def __post_init__(self) -> None:
        if not self.subject_ref or self.subject_ref.isspace():
            raise ValueError("subject_ref must be non-empty")

    def value(self) -> dict[str, object]:
        return {
            "subject_ref": self.subject_ref,
            "coordinate": self.coordinate.value(),
        }


@dataclass(frozen=True, slots=True)
class GeoEffectEnvelope:
    allowed_providers: tuple[str, ...]
    max_logical_queries: int
    max_provider_requests: int
    allowed_data_classes: tuple[str, ...] = ("coordinate", "datum", "locale")
    max_billable_units: int | None = None
    allow_unknown_billable_units: bool = False
    retention: GeoRetention = GeoRetention.NONE

    def __post_init__(self) -> None:
        object.__setattr__(self, "retention", GeoRetention(self.retention))
        if not self.allowed_providers:
            raise ValueError("allowed_providers must be non-empty")
        if len(set(self.allowed_providers)) != len(self.allowed_providers):
            raise ValueError("allowed_providers must be unique")
        if any(not item or item.isspace() for item in self.allowed_providers):
            raise ValueError("allowed_providers must contain non-empty identifiers")
        permitted = {"coordinate", "datum", "locale"}
        if not set(self.allowed_data_classes) <= permitted:
            raise ValueError("allowed_data_classes contains forbidden egress")
        if len(set(self.allowed_data_classes)) != len(self.allowed_data_classes):
            raise ValueError("allowed_data_classes must be unique")
        if self.max_logical_queries < 1:
            raise ValueError("max_logical_queries must be positive")
        if self.max_provider_requests < 1:
            raise ValueError("max_provider_requests must be positive")
        if self.max_billable_units is not None and self.max_billable_units < 0:
            raise ValueError("max_billable_units cannot be negative")

    def value(self) -> dict[str, object]:
        return {
            "allowed_providers": list(self.allowed_providers),
            "allowed_data_classes": list(self.allowed_data_classes),
            "max_logical_queries": self.max_logical_queries,
            "max_provider_requests": self.max_provider_requests,
            "max_billable_units": self.max_billable_units,
            "allow_unknown_billable_units": self.allow_unknown_billable_units,
            "retention": self.retention.value,
        }


@dataclass(frozen=True, slots=True)
class GeoRouteContext:
    preferred_provider: str | None = None
    locale: str | None = None

    def __post_init__(self) -> None:
        if self.preferred_provider is not None and not self.preferred_provider:
            raise ValueError("preferred_provider cannot be empty")
        if self.locale is not None and not self.locale:
            raise ValueError("route locale cannot be empty")

    def value(self) -> dict[str, object]:
        return {
            "preferred_provider": self.preferred_provider,
            "locale": self.locale,
        }


@dataclass(frozen=True, slots=True)
class GeoRequest:
    operation: GeoOperation
    subjects: tuple[GeoSubject, ...]
    locale: str
    radius_meters: float | None = None
    max_places: int | None = None
    retention: GeoRetention = GeoRetention.NONE
    route_context: GeoRouteContext = GeoRouteContext()

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", GeoOperation(self.operation))
        object.__setattr__(self, "retention", GeoRetention(self.retention))
        if not self.subjects:
            raise ValueError("subjects must be non-empty")
        refs = [subject.subject_ref for subject in self.subjects]
        if len(set(refs)) != len(refs):
            raise ValueError("subject_ref values must be unique")
        if not self.locale or self.locale.isspace():
            raise ValueError("locale must be non-empty")
        if self.radius_meters is not None and self.radius_meters <= 0:
            raise ValueError("radius_meters must be positive")
        if self.max_places is not None and self.max_places < 1:
            raise ValueError("max_places must be positive")
        if self.operation is GeoOperation.NEARBY_PLACES:
            if self.radius_meters is None or self.max_places is None:
                raise ValueError(
                    "nearby_places requires radius_meters and max_places"
                )
        elif self.radius_meters is not None or self.max_places is not None:
            raise ValueError(
                "radius_meters and max_places apply only to nearby_places"
            )

    @property
    def logical_query_count(self) -> int:
        coordinates = {
            json.dumps(subject.coordinate.value(), sort_keys=True, separators=(",", ":"))
            for subject in self.subjects
        }
        return len(coordinates)

    def value(self) -> dict[str, object]:
        value: dict[str, object] = {
            "operation": self.operation.value,
            "subjects": [subject.value() for subject in self.subjects],
            "locale": self.locale,
            "retention": self.retention.value,
            "route_context": self.route_context.value(),
        }
        if self.radius_meters is not None:
            value["radius_meters"] = self.radius_meters
        if self.max_places is not None:
            value["max_places"] = self.max_places
        return value

    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.value(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


@dataclass(frozen=True, slots=True)
class GeoAuthorization:
    principal_ref: str
    request_fingerprint: str
    authorized_at: datetime
    envelope: GeoEffectEnvelope

    def __post_init__(self) -> None:
        if not self.principal_ref or self.principal_ref.isspace():
            raise ValueError("principal_ref must be non-empty")
        if re.fullmatch(r"sha256:[0-9a-f]{64}", self.request_fingerprint) is None:
            raise ValueError("request_fingerprint must be a sha256 identity")
        if self.authorized_at.tzinfo is None:
            raise ValueError("authorized_at must include a timezone")

    def value(self) -> dict[str, object]:
        return {
            "principal_ref": self.principal_ref,
            "request_fingerprint": self.request_fingerprint,
            "authorized_at": self.authorized_at.isoformat(),
            "effect_envelope": self.envelope.value(),
        }

    def binding(self) -> str:
        encoded = json.dumps(
            self.value(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"
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


@dataclass(frozen=True, slots=True)
class GeoEffects:
    logical_queries: int
    provider_requests: int | None
    billable_units: int | None
    transmitted_data_classes: tuple[str, ...]
    providers_attempted: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.logical_queries < 0:
            raise ValueError("effect counts cannot be negative")
        if self.provider_requests is not None and self.provider_requests < 0:
            raise ValueError("effect counts cannot be negative")
        if self.billable_units is not None and self.billable_units < 0:
            raise ValueError("billable_units cannot be negative")

    def value(self) -> dict[str, object]:
        return {
            "logical_queries": self.logical_queries,
            "provider_requests": self.provider_requests,
            "billable_units": self.billable_units,
            "transmitted_data_classes": list(self.transmitted_data_classes),
            "providers_attempted": list(self.providers_attempted),
        }


@dataclass(frozen=True, slots=True)
class GeoContinuation:
    operation: GeoOperation
    reason: str
    requires_authorization: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", GeoOperation(self.operation))
        if not self.reason or self.reason.isspace():
            raise ValueError("continuation reason must be non-empty")

    def value(self) -> dict[str, object]:
        return {
            "operation": self.operation.value,
            "reason": self.reason,
            "requires_authorization": self.requires_authorization,
        }


@dataclass(frozen=True, slots=True)
class GeoCapabilityResult:
    operation: GeoOperation
    outcome: GeoOutcome
    request_fingerprint: str
    components: tuple[GeoComponentResult, ...]
    attempts: tuple[GeoProviderAttempt, ...]
    effects: GeoEffects
    continuations: tuple[GeoContinuation, ...]
    observed_at: datetime
    qualifications: tuple[Mapping[str, str], ...] = ()
    required_authorization: GeoEffectEnvelope | None = None
    route_context: GeoRouteContext = GeoRouteContext()

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", GeoOperation(self.operation))
        object.__setattr__(self, "outcome", GeoOutcome(self.outcome))
        if re.fullmatch(r"sha256:[0-9a-f]{64}", self.request_fingerprint) is None:
            raise ValueError("request_fingerprint must be a sha256 identity")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must include a timezone")
        if any(not component.subject_refs for component in self.components):
            raise ValueError("result components must be bound to subjects")
        if (
            self.outcome is GeoOutcome.AUTHORIZATION_REQUIRED
            and self.required_authorization is None
        ):
            raise ValueError(
                "authorization_required requires a proposed effect envelope"
            )
        if (
            self.outcome is not GeoOutcome.AUTHORIZATION_REQUIRED
            and self.required_authorization is not None
        ):
            raise ValueError(
                "only authorization_required may propose an effect envelope"
            )

    def value(self) -> dict[str, object]:
        value: dict[str, object] = {
            "outcome": self.outcome.value,
            "operation": self.operation.value,
            "request_fingerprint": self.request_fingerprint,
            "components": [component.value() for component in self.components],
            "attempts": [attempt.value() for attempt in self.attempts],
            "effects": self.effects.value(),
            "continuations": [item.value() for item in self.continuations],
            "observed_at": self.observed_at.isoformat(),
            "qualifications": [dict(item) for item in self.qualifications],
            "route_context": self.route_context.value(),
        }
        if self.required_authorization is not None:
            value["required_authorization"] = self.required_authorization.value()
        return value
