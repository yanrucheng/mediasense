"""Required, authorization-bound reverse-geocode Evidence Work."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from mediasense.capabilities.geo import (
    GeoCoordinate,
    GeoLookupResult,
    MapDatum,
    ReverseGeocodeBatchEngine,
)

from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkRecord,
    WorkSpec,
    WorkStatus,
    upstream_dependency,
)
from .work import WorkStore

if TYPE_CHECKING:
    from .run import PrecheckRunTool


@dataclass(frozen=True, slots=True)
class ReverseGeocodeProfile:
    provider_profile: str = "amap-google-address-poi-v1"
    routing_policy: str = "c90-continuity-bounded-v1"
    refresh_token: str = "reuse-until-explicit-refresh"
    max_attempts: int = 3
    retry_delay_seconds: float = 3

    def __post_init__(self) -> None:
        for name in ("provider_profile", "routing_policy", "refresh_token"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"reverse-geocode {name} must be non-empty")
        if self.max_attempts < 1 or self.retry_delay_seconds < 0:
            raise ValueError("reverse-geocode retry policy is invalid")

    def descriptor(self) -> str:
        return _json(
            {
                "provider_profile": self.provider_profile,
                "refresh_token": self.refresh_token,
                "routing_policy": self.routing_policy,
            }
        )


@dataclass(frozen=True, slots=True)
class FrozenGeocodeQuery:
    coordinate: GeoCoordinate
    source_paths: tuple[Path, ...]
    basis_work_ids: tuple[str, ...]

    @property
    def key(self) -> str:
        return _json(self.coordinate.value())


@dataclass(frozen=True, slots=True)
class FrozenGeocodeBatch:
    queries: tuple[FrozenGeocodeQuery, ...]
    work: tuple[WorkRecord, ...]
    batch_fingerprint: str
    pending_fingerprint: str

    @property
    def logical_query_count(self) -> int:
        return len(self.queries)

    @property
    def pending_query_count(self) -> int:
        return len(self.pending_queries)

    @property
    def pending_queries(self) -> tuple[FrozenGeocodeQuery, ...]:
        return tuple(
            query
            for query, record in zip(self.queries, self.work, strict=True)
            if record.status
            in {WorkStatus.PENDING, WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}
        )


@dataclass(frozen=True, slots=True)
class ReverseGeocodeWorkOutcome:
    query: FrozenGeocodeQuery
    work: WorkRecord
    observations: tuple[Mapping[str, object], ...]
    reused: bool


@dataclass(frozen=True, slots=True)
class ReverseGeocodeBatchOutcome:
    status: str
    batch: FrozenGeocodeBatch
    outcomes: tuple[ReverseGeocodeWorkOutcome, ...]
    actual_provider_requests: int

    def work_by_source(self) -> dict[Path, str]:
        selected: dict[Path, str] = {}
        for outcome in self.outcomes:
            if outcome.work.status is not WorkStatus.SUCCEEDED:
                continue
            for source_path in outcome.query.source_paths:
                selected[source_path] = outcome.work.work_id
        return selected


class ReverseGeocodeProducer:
    """Freeze, authorize, execute, and reuse source-coordinate queries."""

    def __init__(
        self,
        database_path: Path,
        run_tool: PrecheckRunTool,
        geocoder: ReverseGeocodeBatchEngine | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.run_tool = run_tool
        self.geocoder = geocoder
        self.work = WorkStore(self.database_path)

    def freeze(
        self,
        run_id: str,
        coordinate_work_ids: Sequence[str],
        *,
        profile: ReverseGeocodeProfile = ReverseGeocodeProfile(),
    ) -> FrozenGeocodeBatch:
        if self.geocoder is not None:
            self.geocoder.reset()
        queries = _queries_from_work(
            self.work.list_run_work(run_id), coordinate_work_ids
        )
        records: list[WorkRecord] = []
        previous_work: WorkRecord | None = None
        for query in queries:
            record = self.work.ensure_work(
                run_id,
                _spec(query, profile, previous_work),
                max_attempts=profile.max_attempts,
            )
            records.append(record)
            previous_work = record
        batch_fingerprint = (
            "sha256:"
            + hashlib.sha256(
                _json(
                    {
                        "work_ids": [record.work_id for record in records],
                        "profile": profile.descriptor(),
                        "queries": [query.key for query in queries],
                    }
                ).encode("utf-8")
            ).hexdigest()
        )
        pending = [
            (query, record)
            for query, record in zip(queries, records, strict=True)
            if record.status
            in {WorkStatus.PENDING, WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}
        ]
        disclosure = self._disclosure(
            [query for query, _record in pending],
            batch_fingerprint=batch_fingerprint,
        )
        pending_fingerprint = (
            "sha256:"
            + hashlib.sha256(
                _json(
                    {
                        "batch_fingerprint": batch_fingerprint,
                        "pending_work_ids": [record.work_id for _query, record in pending],
                        "disclosure": disclosure,
                    }
                ).encode("utf-8")
            ).hexdigest()
        )
        return FrozenGeocodeBatch(
            queries,
            tuple(records),
            batch_fingerprint,
            pending_fingerprint,
        )

    def produce(
        self,
        public_run_ref: str,
        run_id: str,
        coordinate_work_ids: Sequence[str],
        *,
        profile: ReverseGeocodeProfile = ReverseGeocodeProfile(),
        owner: str = "builtin-reverse-geocode",
    ) -> ReverseGeocodeBatchOutcome:
        self.run_tool.bind_working_run(public_run_ref, run_id)
        batch = self.freeze(run_id, coordinate_work_ids, profile=profile)
        if not batch.queries:
            return ReverseGeocodeBatchOutcome("not_applicable", batch, (), 0)
        if self.geocoder is None and batch.pending_query_count:
            return ReverseGeocodeBatchOutcome("unavailable", batch, (), 0)
        if batch.pending_query_count:
            disclosure = self._disclosure(
                batch.pending_queries,
                batch_fingerprint=batch.batch_fingerprint,
            )
            status = self.run_tool.require_confirmation(
                public_run_ref,
                summary="Reverse-geocode the frozen source coordinate set.",
                quantity=batch.pending_query_count,
                unit="logical_queries",
                skip_allowed=False,
                pending_fingerprint=batch.pending_fingerprint,
                disclosure=disclosure,
            )
            if status["state"] == "paused":
                return ReverseGeocodeBatchOutcome("confirmation_required", batch, (), 0)
            decision = self.run_tool.confirmation_decision(
                public_run_ref,
                pending_fingerprint=batch.pending_fingerprint,
            )
            if decision != "proceed":
                raise RuntimeError("frozen external work lacks matching authorization")
            authority = self.run_tool.confirmation_authority(
                public_run_ref, pending_fingerprint=batch.pending_fingerprint
            )
            if authority is None:
                raise RuntimeError("frozen external work lacks trusted authorization")

        outcomes: list[ReverseGeocodeWorkOutcome] = []
        actual_provider_requests = 0
        for query, initial_record in zip(batch.queries, batch.work, strict=True):
            if self.run_tool.current_state(public_run_ref) != "running":
                break
            record = self.work.get_work(initial_record.work_id)
            if record.status is WorkStatus.SUCCEEDED:
                observations, result = _reused_output(record)
                if self.geocoder is not None:
                    self.geocoder.observe(result)
                outcomes.append(
                    ReverseGeocodeWorkOutcome(query, record, observations, True)
                )
                continue
            if record.status not in {WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}:
                outcomes.append(ReverseGeocodeWorkOutcome(query, record, (), False))
                continue
            assert self.geocoder is not None
            leases = self.work.claim_ready_work(
                run_id,
                owner,
                lease_duration=timedelta(minutes=2),
                work_id=record.work_id,
            )
            if not leases:
                outcomes.append(
                    ReverseGeocodeWorkOutcome(
                        query, self.work.get_work(record.work_id), (), False
                    )
                )
                continue
            lookup = self.geocoder.lookup(query.coordinate)
            actual_provider_requests += lookup.provider_request_count
            observations = _observations(lookup, query, profile)
            result_value = lookup.work_value()
            result_value["routing_after"] = self.geocoder.routing_state()
            completed = self.work.succeed_work(
                leases[0],
                {
                    "authorization": {
                        **dict(authority),
                        "confirmed_logical_queries": batch.pending_query_count,
                        "decision": "proceed",
                        "pending_fingerprint": batch.pending_fingerprint,
                        "run_ref": public_run_ref,
                    },
                    "observations": list(observations),
                    "producer": {
                        "identity": "builtin-adaptive-reverse-geocode-v1",
                        "profile": profile.descriptor(),
                    },
                    "query": query.coordinate.value(),
                    "result": result_value,
                },
            )
            outcomes.append(
                ReverseGeocodeWorkOutcome(query, completed, observations, False)
            )
        statuses = {
            str(observation.get("status"))
            for outcome in outcomes
            for observation in outcome.observations
            if observation.get("name") == "reverse_geocode_candidate"
        }
        status = (
            "completed"
            if len(outcomes) == len(batch.queries)
            and all(outcome.work.status is WorkStatus.SUCCEEDED for outcome in outcomes)
            and "failed" not in statuses
            else "partial"
        )
        return ReverseGeocodeBatchOutcome(
            status,
            batch,
            tuple(outcomes),
            actual_provider_requests,
        )

    def _disclosure(
        self,
        queries: Sequence[FrozenGeocodeQuery],
        *,
        batch_fingerprint: str,
    ) -> dict[str, object]:
        provider = self.geocoder
        if provider is None:
            provider_disclosure: list[Mapping[str, object]] = []
        elif hasattr(provider, "effect_disclosure"):
            provider_disclosure = list(provider.effect_disclosure(len(queries)))
        else:
            provider_disclosure = [
                {
                    "provider": str(getattr(provider, "provider_id", "configured")),
                    "data_handling": "unknown",
                    "max_provider_requests": len(queries),
                }
            ]
        max_requests = sum(
            int(item.get("max_provider_requests", 0))
            for item in provider_disclosure
        )
        return {
            "frozen_batch_identity": batch_fingerprint,
            "operation": "reverse_geocode",
            "coordinates": [query.coordinate.value() for query in queries],
            "transmitted_data_classes": ["coordinate", "datum", "locale"],
            "providers": provider_disclosure,
            "max_provider_requests": max_requests,
            "billable_calls": "unknown",
            "result_retention": "immutable_precheck_result",
        }


def _queries_from_work(
    attached_work: Iterable[WorkRecord], selected_ids: Sequence[str]
) -> tuple[FrozenGeocodeQuery, ...]:
    by_id = {record.work_id: record for record in attached_work}
    selected: dict[str, tuple[int, GeoCoordinate, str]] = {}
    source_order: list[str] = []
    for work_id in dict.fromkeys(selected_ids):
        record = by_id.get(work_id)
        if record is None or record.spec.capability not in {
            "source-metadata",
            "gpx-location-candidate",
        }:
            raise ValueError(
                f"coordinate Work is not attached or has the wrong capability: {work_id}"
            )
        if record.status is not WorkStatus.SUCCEEDED:
            continue
        output = record.output
        if not isinstance(output, Mapping):
            raise ValueError("coordinate Work has no structured output")
        subject = output.get("subject")
        if not isinstance(subject, Mapping) or not isinstance(
            subject.get("relative_path"), str
        ):
            raise ValueError("coordinate Work has no Source Item subject")
        relative_path = str(subject["relative_path"])
        if relative_path not in selected:
            source_order.append(relative_path)
        observation_name = (
            "gpx_coordinates"
            if record.spec.capability == "gpx-location-candidate"
            else "gps_coordinates"
        )
        priority = 2 if observation_name == "gpx_coordinates" else 1
        observation = _find_observation(output, observation_name)
        coordinate = _coordinate(observation)
        if coordinate is None:
            continue
        previous = selected.get(relative_path)
        if (
            previous is not None
            and previous[0] == priority
            and previous[1] != coordinate
        ):
            raise ValueError(f"conflicting coordinate Work for {relative_path}")
        if previous is None or priority >= previous[0]:
            selected[relative_path] = (priority, coordinate, record.work_id)

    grouped: dict[str, dict[str, object]] = {}
    query_order: list[str] = []
    for relative_path in source_order:
        candidate = selected.get(relative_path)
        if candidate is None:
            continue
        _priority, coordinate, work_id = candidate
        key = _json(coordinate.value())
        if key not in grouped:
            grouped[key] = {
                "coordinate": coordinate,
                "source_paths": [],
                "basis_work_ids": [],
            }
            query_order.append(key)
        grouped[key]["source_paths"].append(Path(relative_path))
        grouped[key]["basis_work_ids"].append(work_id)
    return tuple(
        FrozenGeocodeQuery(
            coordinate=grouped[key]["coordinate"],
            source_paths=tuple(grouped[key]["source_paths"]),
            basis_work_ids=tuple(grouped[key]["basis_work_ids"]),
        )
        for key in query_order
    )


def _find_observation(
    output: Mapping[str, object], name: str
) -> Mapping[str, object] | None:
    observations = output.get("observations")
    if not isinstance(observations, Sequence):
        return None
    return next(
        (
            item
            for item in observations
            if isinstance(item, Mapping)
            and item.get("name") == name
            and item.get("status") == "available"
        ),
        None,
    )


def _coordinate(observation: Mapping[str, object] | None) -> GeoCoordinate | None:
    if observation is None or not isinstance(observation.get("value"), Mapping):
        return None
    value = observation["value"]
    try:
        return GeoCoordinate(
            latitude=float(value["latitude"]),
            longitude=float(value["longitude"]),
            datum=MapDatum(str(value["datum"]).upper()),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _spec(
    query: FrozenGeocodeQuery,
    profile: ReverseGeocodeProfile,
    previous_work: WorkRecord | None,
) -> WorkSpec:
    dependencies = [
        WorkDependency(
            DependencyKind.PARAMETER,
            "normalized_coordinate",
            query.key,
        ),
        WorkDependency(
            DependencyKind.PARAMETER,
            "reverse_geocode_profile",
            profile.descriptor(),
        ),
    ]
    if previous_work is not None:
        dependencies.append(upstream_dependency(previous_work))
    return WorkSpec(
        capability="reverse-geocode-observation",
        producer_identity="builtin-adaptive-reverse-geocode-v1",
        dependencies=tuple(dependencies),
    )


def _observations(
    result: GeoLookupResult,
    query: FrozenGeocodeQuery,
    profile: ReverseGeocodeProfile,
) -> tuple[dict[str, object], ...]:
    status = {
        "success": "available",
        "partial": "available",
        "no_result": "missing",
        "failed": "failed",
    }[result.status]
    provenance = {
        "method": "adaptive_reverse_geocode_v1",
        "provider": result.provider,
        "language": result.language,
        "observed_at": result.observed_at,
        "input_datum": result.input_coordinate.datum.value,
        "provider_datum": result.provider_coordinate.datum.value,
        "logical_query_count": result.logical_query_count,
        "provider_request_count": result.provider_request_count,
        "basis_work_ids": list(query.basis_work_ids),
    }
    attempt_observation: dict[str, object] = {
        "name": "reverse_geocode_attempt",
        "status": "available",
        "value": {
            "attempts": list(result.attempts),
            "input_coordinate": result.input_coordinate.value(),
            "language": result.language,
            "producer": "builtin-adaptive-reverse-geocode-v1",
            "provider": result.provider,
            "provider_coordinate": result.provider_coordinate.value(),
            "provider_request_count": result.provider_request_count,
            "query_profile": json.loads(profile.descriptor()),
            "observed_at": result.observed_at,
        },
        "provenance": provenance,
    }
    candidate: dict[str, object] = {
        "name": "reverse_geocode_candidate",
        "status": status,
        "provenance": {
            **provenance,
            "observation": "provider_candidate",
        },
    }
    if status == "available":
        candidate["value"] = {
            "address": None if result.location is None else dict(result.location),
            "pois": [dict(poi) for poi in result.pois],
        }
    if result.qualifications:
        candidate["qualifications"] = list(result.qualifications)
    if result.error_code is not None:
        candidate.setdefault("qualifications", []).append(
            {
                "code": result.error_code,
                "effect": "limits_interpretation",
                "message": result.error_message or result.error_code,
            }
        )
    return attempt_observation, candidate


def _reused_output(
    record: WorkRecord,
) -> tuple[tuple[Mapping[str, object], ...], Mapping[str, object]]:
    if not isinstance(record.output, Mapping):
        raise ValueError("reverse-geocode Work has no structured output")
    observations = record.output.get("observations")
    result = record.output.get("result")
    if (
        not isinstance(observations, Sequence)
        or not observations
        or any(not isinstance(item, Mapping) for item in observations)
        or not isinstance(result, Mapping)
    ):
        raise ValueError("reverse-geocode Work output is invalid")
    return tuple(observations), result


def _json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = [
    "FrozenGeocodeBatch",
    "FrozenGeocodeQuery",
    "ReverseGeocodeBatchOutcome",
    "ReverseGeocodeProducer",
    "ReverseGeocodeProfile",
    "ReverseGeocodeWorkOutcome",
]
