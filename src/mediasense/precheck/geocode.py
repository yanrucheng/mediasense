"""Required, authorization-bound reverse-geocode Evidence Work."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
import sqlite3
from typing import TYPE_CHECKING

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCoordinate,
    GeoEffectEnvelope,
    GeoOperation,
    GeoQueryTool,
    GeoRequest,
    GeoRetention,
    GeoRouteContext,
    GeoSubject,
    MapDatum,
)

from ._work_types import (
    DependencyKind,
    WorkDependency,
    WorkLease,
    WorkRecord,
    WorkSpec,
    WorkStatus,
)
from .work import WorkStore

if TYPE_CHECKING:
    from .run import PrecheckRunTool


_ACQUISITION_POLICY = "bundle-stationary-complete-link-v1"
_MAX_SHARED_DIAMETER_METERS = 15.0
_MAX_SHARED_SPAN_SECONDS = 120.0
_LEGACY_PRODUCER = "builtin-adaptive-reverse-geocode-v1"
_REVERSE_ONLY_PRODUCER = "builtin-geo-query-reverse-geocode-v2"
_V3_PRODUCER = "builtin-geo-query-address-poi-v3"
_PRODUCER = "builtin-geo-component-observations-v4"
_LEGACY_PROFILE = {
    "provider_profile": "amap-google-address-poi-v1",
    "refresh_token": "reuse-until-explicit-refresh",
    "routing_policy": "c90-continuity-bounded-v1",
}


@dataclass(frozen=True, slots=True)
class ReverseGeocodeProfile:
    provider_profile: str = "geo-query-address-poi-v2"
    routing_policy: str = "ordered-per-coordinate-v1"
    refresh_token: str = "reuse-until-explicit-refresh"
    nearby_radius_meters: float = 500.0
    max_places: int = 30
    max_attempts: int = 3
    retry_delay_seconds: float = 3

    def __post_init__(self) -> None:
        for name in ("provider_profile", "routing_policy", "refresh_token"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"reverse-geocode {name} must be non-empty")
        if self.max_attempts < 1 or self.retry_delay_seconds < 0:
            raise ValueError("reverse-geocode retry policy is invalid")
        if self.nearby_radius_meters <= 0 or self.max_places < 1:
            raise ValueError("reverse-geocode nearby-place bounds are invalid")

    def descriptor(self) -> str:
        return _json(
            {
                "provider_profile": self.provider_profile,
                "refresh_token": self.refresh_token,
                "routing_policy": self.routing_policy,
                "nearby_radius_meters": self.nearby_radius_meters,
                "max_places": self.max_places,
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
class _LocatedSource:
    relative_path: Path
    coordinate: GeoCoordinate
    basis_work_id: str
    capture_time: datetime | None


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
    actual_provider_requests: int | None

    def work_by_source(self) -> dict[Path, str]:
        selected: dict[Path, str] = {}
        for outcome in self.outcomes:
            if outcome.work.status is not WorkStatus.SUCCEEDED:
                continue
            for source_path in outcome.query.source_paths:
                selected[source_path] = outcome.work.work_id
        return selected


class ReverseGeocodeProducer:
    """Freeze, authorize, execute, and reuse complete source place queries."""

    def __init__(
        self,
        database_path: Path,
        run_tool: PrecheckRunTool,
        geo_tool: GeoQueryTool | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.run_tool = run_tool
        self.geo_tool = geo_tool
        self.work = WorkStore(self.database_path)

    def freeze(
        self,
        run_id: str,
        coordinate_work_ids: Sequence[str],
        *,
        bundle_work_ids: Sequence[str] = (),
        profile: ReverseGeocodeProfile = ReverseGeocodeProfile(),
    ) -> FrozenGeocodeBatch:
        queries = _queries_from_work(
            self.work.list_run_work(run_id),
            coordinate_work_ids,
            bundle_work_ids=bundle_work_ids,
        )
        records: list[WorkRecord] = []
        for query in queries:
            record = self.work.ensure_work(
                run_id,
                _spec(query, profile),
                max_attempts=profile.max_attempts,
            )
            if record.status is not WorkStatus.SUCCEEDED:
                record = self._reuse_legacy_observation(run_id, record, query, profile)
            records.append(record)
        self._retire_superseded_chain_work(
            run_id, {record.work_id for record in records}
        )
        batch_fingerprint = (
            "sha256:"
            + hashlib.sha256(
                _json(
                    {
                        "acquisition_policy": _ACQUISITION_POLICY,
                        "work_ids": [record.work_id for record in records],
                        "profile": profile.descriptor(),
                        "queries": [query.coordinate.value() for query in queries],
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
        pending_request = _geo_request(
            pending,
            profile,
            request_id="request:precheck-geo-preflight",
        )
        pending_fingerprint = (
            batch_fingerprint
            if pending_request is None
            else (
                self.geo_tool.capability.fingerprint(_request_value(pending_request))
                if self.geo_tool is not None
                else _request_value(pending_request).fingerprint()
            )
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
        bundle_work_ids: Sequence[str] = (),
        profile: ReverseGeocodeProfile = ReverseGeocodeProfile(),
        owner: str = "builtin-reverse-geocode",
    ) -> ReverseGeocodeBatchOutcome:
        self.run_tool.bind_working_run(public_run_ref, run_id)
        batch = self.freeze(
            run_id,
            coordinate_work_ids,
            bundle_work_ids=bundle_work_ids,
            profile=profile,
        )
        if not batch.queries:
            return ReverseGeocodeBatchOutcome("not_applicable", batch, (), 0)
        if any(
            isinstance(record.output, Mapping)
            and record.output.get("result", {}).get("status") == "indeterminate"
            for record in batch.work
        ):
            return self._collect(batch, actual_provider_requests=0)
        if self.geo_tool is None and batch.pending_query_count:
            return ReverseGeocodeBatchOutcome("unavailable", batch, (), 0)
        pending_records = tuple(
            (query, record)
            for query, record in zip(batch.queries, batch.work, strict=True)
            if record.status
            in {WorkStatus.PENDING, WorkStatus.READY, WorkStatus.RETRYABLE_FAILURE}
        )
        request = _geo_request(
            pending_records,
            profile,
            request_id=_tool_request_id(public_run_ref, batch.pending_fingerprint),
        )
        preflight: Mapping[str, object] | None = None
        if batch.pending_query_count:
            assert self.geo_tool is not None and request is not None
            preflight = self.geo_tool.handle(request)
            if preflight.get("outcome") == "unavailable":
                return ReverseGeocodeBatchOutcome("unavailable", batch, (), 0)
            if preflight.get("request_fingerprint") != batch.pending_fingerprint:
                raise RuntimeError("Geo Tool changed the frozen request identity")
            if preflight.get("outcome") == "authorization_required":
                disclosure = self._disclosure(preflight, batch=batch, profile=profile)
                status = self.run_tool.require_confirmation(
                    public_run_ref,
                    summary=(
                        "Resolve address and nearby-place evidence for the "
                        "compressed PreCheck acquisition set."
                    ),
                    quantity=batch.pending_query_count,
                    unit="logical_queries",
                    skip_allowed=False,
                    pending_fingerprint=batch.pending_fingerprint,
                    disclosure=disclosure,
                )
                if status["state"] == "paused":
                    return ReverseGeocodeBatchOutcome(
                        "confirmation_required", batch, (), 0
                    )
                decision = self.run_tool.confirmation_decision(
                    public_run_ref,
                    pending_fingerprint=batch.pending_fingerprint,
                )
                if decision != "proceed":
                    raise RuntimeError(
                        "frozen external work lacks matching authorization"
                    )
                authority = self.run_tool.confirmation_authority(
                    public_run_ref, pending_fingerprint=batch.pending_fingerprint
                )
                if authority is None:
                    raise RuntimeError(
                        "frozen external work lacks trusted authorization"
                    )
                geo_authorization = _geo_authorization(
                    authority,
                    batch.pending_fingerprint,
                    preflight,
                )
                response = self.geo_tool.handle(
                    request,
                    authorization=geo_authorization,
                    cancelled=lambda: (
                        self.run_tool.current_state(public_run_ref) != "running"
                    ),
                )
            else:
                response = preflight
                authority = self.run_tool.confirmation_authority(
                    public_run_ref, pending_fingerprint=batch.pending_fingerprint
                )
                if authority is None:
                    raise RuntimeError(
                        "journaled Geo result lacks its trusted PreCheck authorization"
                    )
            leases = self._claim_pending(run_id, pending_records, owner)
            if len(leases) != len(pending_records):
                for lease in leases.values():
                    self.work.fail_work(
                        lease,
                        error_code="geo_work_claim_incomplete",
                        message=(
                            "The complete Geo result set could not be claimed "
                            "atomically."
                        ),
                        retryable=True,
                        retry_delay=timedelta(seconds=profile.retry_delay_seconds),
                    )
                return self._collect(batch, actual_provider_requests=0)
            self._persist_response(
                public_run_ref,
                batch,
                pending_records,
                leases,
                response,
                authority,
                profile,
            )
            effects = response.get("effects")
            actual_provider_requests = (
                int(effects.get("provider_requests", 0))
                if isinstance(effects, Mapping)
                and isinstance(effects.get("provider_requests"), int)
                else None
            )
        else:
            actual_provider_requests = 0
        return self._collect(batch, actual_provider_requests=actual_provider_requests)

    def _collect(
        self,
        batch: FrozenGeocodeBatch,
        *,
        actual_provider_requests: int | None,
    ) -> ReverseGeocodeBatchOutcome:
        outcomes: list[ReverseGeocodeWorkOutcome] = []
        for query, initial_record in zip(batch.queries, batch.work, strict=True):
            record = self.work.get_work(initial_record.work_id)
            observations: tuple[Mapping[str, object], ...] = ()
            reused = initial_record.status is WorkStatus.SUCCEEDED
            if record.status is WorkStatus.SUCCEEDED:
                observations, _result = _reused_output(record)
            outcomes.append(
                ReverseGeocodeWorkOutcome(query, record, observations, reused)
            )
        indeterminate = any(
            q.get("code") == "geo_effect_indeterminate"
            for outcome in outcomes
            for observation in outcome.observations
            for q in observation.get("qualifications", ())
        )
        status = (
            "indeterminate"
            if indeterminate
            else "completed"
            if len(outcomes) == len(batch.queries)
            and all(outcome.work.status is WorkStatus.SUCCEEDED for outcome in outcomes)
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
        preflight: Mapping[str, object],
        *,
        batch: FrozenGeocodeBatch,
        profile: ReverseGeocodeProfile,
    ) -> dict[str, object]:
        envelope = preflight.get("required_authorization")
        if not isinstance(envelope, Mapping):
            raise RuntimeError("Geo Tool preflight omitted its authorization envelope")
        providers = envelope.get("allowed_providers")
        provider_ids = (
            tuple(str(item) for item in providers)
            if isinstance(providers, Sequence) and not isinstance(providers, str)
            else ()
        )
        return {
            "geo_request_fingerprint": batch.pending_fingerprint,
            "operation": "resolve_place",
            "nearby_radius_meters": profile.nearby_radius_meters,
            "max_places": profile.max_places,
            "coordinates": [
                query.coordinate.value() for query in batch.pending_queries
            ],
            "pending_logical_queries": int(envelope.get("max_logical_queries", 0)),
            "source_item_outcomes": sum(
                len(query.source_paths) for query in batch.queries
            ),
            "transmitted_data_classes": list(envelope.get("allowed_data_classes", ())),
            "providers": [
                {"provider": provider_id, "data_handling": "unknown"}
                for provider_id in provider_ids
            ],
            "max_provider_requests": int(envelope.get("max_provider_requests", 0)),
            "max_billable_units": envelope.get("max_billable_units"),
            "billable_calls": (
                None
                if bool(envelope.get("allow_unknown_billable_units"))
                else envelope.get("max_billable_units")
            ),
            "result_retention": "immutable_precheck_result",
            "retry_policy": self.geo_tool.capability.retry_policy.value(),
        }

    def _claim_pending(
        self,
        run_id: str,
        pending: Sequence[tuple[FrozenGeocodeQuery, WorkRecord]],
        owner: str,
    ) -> dict[str, WorkLease]:
        leases: dict[str, WorkLease] = {}
        for _query, record in pending:
            claimed = self.work.claim_ready_work(
                run_id,
                owner,
                lease_duration=timedelta(minutes=10),
                work_id=record.work_id,
            )
            if claimed:
                leases[record.work_id] = claimed[0]
        return leases

    def _persist_response(
        self,
        public_run_ref: str,
        batch: FrozenGeocodeBatch,
        pending: Sequence[tuple[FrozenGeocodeQuery, WorkRecord]],
        leases: Mapping[str, WorkLease],
        response: Mapping[str, object],
        authority: Mapping[str, object],
        profile: ReverseGeocodeProfile,
    ) -> None:
        if response.get("outcome") in {
            "authorization_required",
            "unavailable",
            "error",
        }:
            raise RuntimeError(
                f"Geo Tool did not execute the authorized request: {response}"
            )
        components = response.get("components")
        attempts = response.get("attempts")
        if not isinstance(components, Sequence) or not isinstance(attempts, Sequence):
            raise RuntimeError("Geo Tool returned an invalid result")
        by_subject: dict[str, dict[str, Mapping[str, object]]] = {}
        for component in components:
            if not isinstance(component, Mapping):
                continue
            refs = component.get("subject_refs")
            operation = component.get("operation")
            if not isinstance(operation, str):
                continue
            if not isinstance(refs, Sequence) or isinstance(refs, str):
                continue
            for subject_ref in refs:
                if isinstance(subject_ref, str):
                    by_subject.setdefault(subject_ref, {})[operation] = component
        observed_at = response.get("observed_at")
        completed: list[tuple[WorkLease, object]] = []
        not_requested: list[WorkLease] = []
        for query, record in pending:
            lease = leases.get(record.work_id)
            if lease is None:
                continue
            subject_components = by_subject.get(record.work_id)
            if subject_components is None or not {
                GeoOperation.REVERSE_GEOCODE.value,
                GeoOperation.NEARBY_PLACES.value,
            } <= set(subject_components):
                raise RuntimeError("Geo Tool omitted required component outcomes.")
            if all(
                component.get("status") == "not_requested"
                for component in subject_components.values()
            ):
                not_requested.append(lease)
                continue
            matching_attempts = tuple(
                attempt
                for attempt in attempts
                if isinstance(attempt, Mapping)
                and attempt.get("input_coordinate") == query.coordinate.value()
            )
            observations, result_value = _tool_observations(
                subject_components,
                matching_attempts,
                query,
                profile,
                observed_at=observed_at,
            )
            completed.append(
                (
                    lease,
                    {
                        "authorization": {
                            **dict(authority),
                            "confirmed_logical_queries": batch.pending_query_count,
                            "decision": "proceed",
                            "pending_fingerprint": batch.pending_fingerprint,
                            "run_ref": public_run_ref,
                            "disclosure_identity": authority[
                                "confirmed_content_identity"
                            ],
                        },
                        "observations": list(observations),
                        "producer": {
                            "identity": _PRODUCER,
                            "profile": profile.descriptor(),
                        },
                        "query": query.coordinate.value(),
                        "result": result_value,
                    },
                )
            )
        self.work.succeed_work_many(completed)
        for lease in not_requested:
            self.work.fail_work(
                lease,
                error_code="geo_query_not_requested",
                message="The authorized batch stopped before this query was sent.",
                retryable=True,
                retry_delay=timedelta(seconds=profile.retry_delay_seconds),
            )

    def _reuse_legacy_observation(
        self,
        run_id: str,
        target: WorkRecord,
        query: FrozenGeocodeQuery,
        profile: ReverseGeocodeProfile,
    ) -> WorkRecord:
        legacy = _legacy_observation(self.database_path, query, profile)
        if legacy is None:
            return target
        leases = self.work.claim_ready_work(
            run_id,
            "builtin-reverse-geocode-cache-migration",
            lease_duration=timedelta(minutes=1),
            work_id=target.work_id,
        )
        if not leases:
            return self.work.get_work(target.work_id)
        migrated = _upgrade_legacy_observation(legacy)
        migrated["producer"] = {
            "identity": _PRODUCER,
            "profile": profile.descriptor(),
            "reused_from": legacy.get("producer", {}).get("identity", _LEGACY_PRODUCER),
        }
        return self.work.succeed_work(leases[0], migrated)

    def _retire_superseded_chain_work(
        self, run_id: str, selected_work_ids: set[str]
    ) -> None:
        superseded = tuple(
            record.work_id
            for record in self.work.iter_run_work(
                run_id, capability="reverse-geocode-observation"
            )
            if record.work_id not in selected_work_ids
            and record.spec.producer_identity
            in {_LEGACY_PRODUCER, _REVERSE_ONLY_PRODUCER, _V3_PRODUCER}
            and record.status is not WorkStatus.RUNNING
        )
        self.work.detach_run_work(run_id, superseded)


def _queries_from_work(
    attached_work: Iterable[WorkRecord],
    selected_ids: Sequence[str],
    *,
    bundle_work_ids: Sequence[str] = (),
) -> tuple[FrozenGeocodeQuery, ...]:
    by_id = {record.work_id: record for record in attached_work}
    capture_times = _capture_times(by_id.values())
    selected: dict[str, tuple[int, GeoCoordinate, str, datetime | None]] = {}
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
            selected[relative_path] = (
                priority,
                coordinate,
                record.work_id,
                capture_times.get(Path(relative_path)),
            )

    located = {
        Path(relative_path): _LocatedSource(
            Path(relative_path), coordinate, work_id, capture_time
        )
        for relative_path, (
            _priority,
            coordinate,
            work_id,
            capture_time,
        ) in selected.items()
    }
    units: list[tuple[_LocatedSource, ...]] = []
    bundled_paths: set[Path] = set()
    for bundle_id in dict.fromkeys(bundle_work_ids):
        bundle = by_id.get(bundle_id)
        if (
            bundle is None
            or bundle.spec.capability != "bundle-candidate"
            or bundle.status is not WorkStatus.SUCCEEDED
        ):
            raise ValueError(
                f"bundle Work is not successful and attached to this run: {bundle_id}"
            )
        members = tuple(
            located[path] for path in _bundle_member_paths(bundle) if path in located
        )
        overlap = bundled_paths.intersection(item.relative_path for item in members)
        if overlap:
            raise ValueError("bundle Work contains overlapping Source Items")
        bundled_paths.update(item.relative_path for item in members)
        units.extend(_split_bundle(members))
    units.extend(
        (item,) for path, item in sorted(located.items()) if path not in bundled_paths
    )

    # Exact-coordinate deduplication is deliberately last.  It can collapse
    # equivalent provider inputs across acquisition units, but it never decides
    # whether nearby Source Items represent one shooting event.
    grouped: dict[str, dict[str, object]] = {}
    for unit in units:
        if not unit:
            continue
        representative = _coordinate_medoid(unit)
        key = _json(representative.coordinate.value())
        group = grouped.setdefault(
            key,
            {
                "coordinate": representative.coordinate,
                "source_paths": [],
                "basis_work_ids": [],
            },
        )
        group["source_paths"].extend(item.relative_path for item in unit)
        group["basis_work_ids"].extend(item.basis_work_id for item in unit)
    return tuple(
        FrozenGeocodeQuery(
            coordinate=grouped[key]["coordinate"],
            source_paths=tuple(sorted(set(grouped[key]["source_paths"]))),
            basis_work_ids=tuple(sorted(set(grouped[key]["basis_work_ids"]))),
        )
        for key in sorted(grouped)
    )


def _capture_times(records: Iterable[WorkRecord]) -> dict[Path, datetime]:
    captured: dict[Path, datetime] = {}
    for record in records:
        if record.spec.capability != "source-metadata" or not isinstance(
            record.output, Mapping
        ):
            continue
        subject = record.output.get("subject")
        if not isinstance(subject, Mapping) or not isinstance(
            subject.get("relative_path"), str
        ):
            continue
        observation = _find_observation(record.output, "capture_time")
        if observation is None or not isinstance(observation.get("value"), str):
            continue
        try:
            parsed = datetime.fromisoformat(str(observation["value"]))
        except ValueError:
            continue
        if parsed.tzinfo is not None and parsed.utcoffset() is not None:
            captured[Path(str(subject["relative_path"]))] = parsed
    return captured


def _bundle_member_paths(record: WorkRecord) -> tuple[Path, ...]:
    members: list[Path] = []
    for dependency in record.spec.dependencies:
        if dependency.kind is not DependencyKind.SOURCE_REVISION:
            continue
        try:
            _dataset_id, relative_path = json.loads(dependency.key)
        except (TypeError, ValueError) as error:
            raise ValueError("bundle Work has an invalid source dependency") from error
        members.append(Path(str(relative_path)))
    return tuple(sorted(members))


def _split_bundle(
    members: Sequence[_LocatedSource],
) -> tuple[tuple[_LocatedSource, ...], ...]:
    """Keep only locally supported stationary subsets of one bundle candidate."""

    if not members:
        return ()
    associations: dict[Path, list[_LocatedSource]] = defaultdict(list)
    from .discovery import association_key

    for item in members:
        associations[association_key(item.relative_path)].append(item)
    atomic = tuple(
        group
        for key in sorted(associations)
        for group in _complete_link_groups(
            tuple(
                sorted(
                    associations[key],
                    key=lambda item: item.relative_path.as_posix(),
                )
            )
        )
    )
    timed = sorted(
        (
            (
                min(
                    item.capture_time for item in group if item.capture_time is not None
                ),
                group,
            )
            for group in atomic
            if any(item.capture_time is not None for item in group)
        ),
        key=lambda value: (value[0], value[1][0].relative_path.as_posix()),
    )
    units = [
        group
        for group in atomic
        if not any(item.capture_time is not None for item in group)
    ]
    current: list[_LocatedSource] = []
    for _capture_time_value, atomic_group in timed:
        proposed = (*current, *atomic_group)
        if current and not _locally_consistent(proposed):
            units.append(tuple(current))
            current = []
        current.extend(atomic_group)
    if current:
        units.append(tuple(current))
    return tuple(units)


def _complete_link_groups(
    members: tuple[_LocatedSource, ...],
) -> tuple[tuple[_LocatedSource, ...], ...]:
    groups: list[list[_LocatedSource]] = []
    for member in members:
        target = next(
            (group for group in groups if _locally_consistent((*group, member))),
            None,
        )
        if target is None:
            groups.append([member])
        else:
            target.append(member)
    return tuple(tuple(group) for group in groups)


def _locally_consistent(members: Sequence[_LocatedSource]) -> bool:
    spatially_consistent = all(
        left.coordinate.datum is right.coordinate.datum
        and _distance_meters(left.coordinate, right.coordinate)
        <= _MAX_SHARED_DIAMETER_METERS
        for index, left in enumerate(members)
        for right in members[index + 1 :]
    )
    if not spatially_consistent:
        return False
    if len({item.coordinate for item in members}) == 1:
        return True
    times = sorted(
        item.capture_time for item in members if item.capture_time is not None
    )
    return (
        len(times) < 2
        or (times[-1] - times[0]).total_seconds() <= _MAX_SHARED_SPAN_SECONDS
    )


def _coordinate_medoid(members: Sequence[_LocatedSource]) -> _LocatedSource:
    return min(
        members,
        key=lambda candidate: (
            sum(
                _distance_meters(candidate.coordinate, other.coordinate)
                for other in members
            ),
            candidate.relative_path.as_posix(),
        ),
    )


def _distance_meters(left: GeoCoordinate, right: GeoCoordinate) -> float:
    if left.datum is not right.datum:
        return float("inf")
    latitude_delta = radians(right.latitude - left.latitude)
    longitude_delta = radians(right.longitude - left.longitude)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(left.latitude))
        * cos(radians(right.latitude))
        * sin(longitude_delta / 2) ** 2
    )
    return 6_371_000.0 * 2 * asin(sqrt(value))


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
) -> WorkSpec:
    return WorkSpec(
        capability="reverse-geocode-observation",
        producer_identity=_PRODUCER,
        dependencies=(
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
            WorkDependency(
                DependencyKind.PARAMETER,
                "operation",
                GeoOperation.RESOLVE_PLACE.value,
            ),
            WorkDependency(DependencyKind.PARAMETER, "locale", "zh"),
        ),
    )


def _geo_request_value(
    pending: Sequence[tuple[FrozenGeocodeQuery, WorkRecord]],
    profile: ReverseGeocodeProfile,
) -> GeoRequest:
    return GeoRequest(
        operation=GeoOperation.RESOLVE_PLACE,
        subjects=tuple(
            GeoSubject(record.work_id, query.coordinate) for query, record in pending
        ),
        locale="zh",
        radius_meters=profile.nearby_radius_meters,
        max_places=profile.max_places,
        retention=GeoRetention.CALLER_STATE,
        route_context=GeoRouteContext(locale="zh"),
    )


def _geo_request(
    pending: Sequence[tuple[FrozenGeocodeQuery, WorkRecord]],
    profile: ReverseGeocodeProfile,
    *,
    request_id: str,
) -> dict[str, object] | None:
    if not pending:
        return None
    return {"request_id": request_id, **_geo_request_value(pending, profile).value()}


def _request_value(request: Mapping[str, object]) -> GeoRequest:
    subjects = request.get("subjects")
    if not isinstance(subjects, Sequence) or isinstance(subjects, str):
        raise ValueError("Geo request subjects are invalid")
    parsed_subjects = []
    for subject in subjects:
        if not isinstance(subject, Mapping) or not isinstance(
            subject.get("coordinate"), Mapping
        ):
            raise ValueError("Geo request subject is invalid")
        coordinate = subject["coordinate"]
        parsed_subjects.append(
            GeoSubject(
                str(subject["subject_ref"]),
                GeoCoordinate(
                    float(coordinate["latitude"]),
                    float(coordinate["longitude"]),
                    MapDatum(str(coordinate["datum"])),
                ),
            )
        )
    return GeoRequest(
        GeoOperation(str(request["operation"])),
        tuple(parsed_subjects),
        str(request["locale"]),
        radius_meters=(
            None
            if request.get("radius_meters") is None
            else float(request["radius_meters"])
        ),
        max_places=(
            None if request.get("max_places") is None else int(request["max_places"])
        ),
        retention=GeoRetention(str(request["retention"])),
        route_context=GeoRouteContext(locale="zh"),
    )


def _tool_request_id(public_run_ref: str, pending_fingerprint: str) -> str:
    digest = hashlib.sha256(
        f"precheck-geo-v1\0{public_run_ref}\0{pending_fingerprint}".encode("utf-8")
    ).hexdigest()
    return f"request:precheck-geo:{digest}"


def _geo_authorization(
    authority: Mapping[str, object],
    request_fingerprint: str,
    preflight: Mapping[str, object],
) -> GeoAuthorization:
    envelope = preflight.get("required_authorization")
    if not isinstance(envelope, Mapping):
        raise RuntimeError("Geo Tool preflight omitted its authorization envelope")
    confirmed_at = authority.get("confirmed_at")
    if not isinstance(confirmed_at, str):
        raise RuntimeError("PreCheck authorization has no confirmation time")
    parsed_time = datetime.fromisoformat(confirmed_at)
    return GeoAuthorization(
        principal_ref=str(authority["principal_ref"]),
        request_fingerprint=request_fingerprint,
        authorized_at=parsed_time,
        envelope=GeoEffectEnvelope(
            allowed_providers=tuple(
                str(item) for item in envelope["allowed_providers"]
            ),
            allowed_data_classes=tuple(
                str(item) for item in envelope["allowed_data_classes"]
            ),
            max_logical_queries=int(envelope["max_logical_queries"]),
            max_provider_requests=int(envelope["max_provider_requests"]),
            max_billable_units=(
                None
                if envelope.get("max_billable_units") is None
                else int(envelope["max_billable_units"])
            ),
            allow_unknown_billable_units=bool(
                envelope.get("allow_unknown_billable_units", False)
            ),
            retention=GeoRetention(str(envelope["retention"])),
        ),
    )


def _tool_observations(
    components: Mapping[str, Mapping[str, object]],
    attempts: Sequence[Mapping[str, object]],
    query: FrozenGeocodeQuery,
    profile: ReverseGeocodeProfile,
    *,
    observed_at: object,
) -> tuple[tuple[dict[str, object], ...], dict[str, object]]:
    address_component = components[GeoOperation.REVERSE_GEOCODE.value]
    nearby_component = components[GeoOperation.NEARBY_PLACES.value]
    component_outcomes = {
        GeoOperation.REVERSE_GEOCODE.value: str(address_component.get("status")),
        GeoOperation.NEARBY_PLACES.value: str(nearby_component.get("status")),
    }
    component_statuses = set(component_outcomes.values())
    if component_statuses == {"success"}:
        result_status = "success"
    elif component_statuses == {"no_result"}:
        result_status = "no_result"
    elif "indeterminate" in component_statuses:
        result_status = "indeterminate"
    elif "success" in component_statuses:
        result_status = "partial"
    else:
        result_status = "failed"
    address_candidates = _component_candidates(address_component)
    nearby_candidates = _component_candidates(nearby_component)
    address_candidate = next(
        (item for item in address_candidates if item.get("kind") == "address"), None
    )
    place_candidates = tuple(
        item for item in nearby_candidates if item.get("kind") == "place"
    )
    candidates = (*address_candidates, *nearby_candidates)
    provider = next(
        (
            str(item["provider_ref"])
            for item in candidates
            if isinstance(item.get("provider_ref"), str)
        ),
        None,
    )
    if provider is None:
        provider = next(
            (
                str(item["provider"])
                for item in reversed(attempts)
                if isinstance(item.get("provider"), str)
            ),
            "unavailable",
        )
    providers = sorted(
        {
            str(item["provider"])
            for item in attempts
            if isinstance(item.get("provider"), str) and item["provider"]
        }
    )
    provider_coordinate = next(
        (
            dict(item["provider_coordinate"])
            for item in reversed(attempts)
            if item.get("provider") == provider
            and isinstance(item.get("provider_coordinate"), Mapping)
        ),
        query.coordinate.value(),
    )
    provider_request_count = (
        None
        if result_status == "indeterminate" and not attempts
        else sum(int(item.get("provider_requests", 0)) for item in attempts)
    )
    observed_at_value = str(observed_at or "unknown")
    provenance = {
        "method": "geo_query_tool_v1",
        "provider": provider,
        "language": "zh",
        "observed_at": observed_at_value,
        "input_datum": query.coordinate.datum.value,
        "provider_datum": str(
            provider_coordinate.get("datum", query.coordinate.datum.value)
        ),
        "logical_query_count": 1,
        "provider_request_count": provider_request_count,
        "component_outcomes": component_outcomes,
    }
    attempt_observation: dict[str, object] = {
        "name": "reverse_geocode_attempt",
        "status": "available",
        "value": {
            "attempts": [dict(item) for item in attempts],
            "input_coordinate": query.coordinate.value(),
            "language": "zh",
            "producer": _PRODUCER,
            "provider": provider,
            "providers": providers,
            "provider_coordinate": provider_coordinate,
            "provider_request_count": provider_request_count,
            "query_profile": json.loads(profile.descriptor()),
            "observed_at": observed_at_value,
        },
        "provenance": provenance,
    }
    address = None
    if address_candidate is not None:
        address = {
            "formatted_address": address_candidate.get("formatted_address")
            or address_candidate.get("name"),
            "components": dict(address_candidate.get("components", {})),
        }
    qualifications: list[dict[str, str]] = []
    for operation, component in (
        (GeoOperation.REVERSE_GEOCODE.value, address_component),
        (GeoOperation.NEARBY_PLACES.value, nearby_component),
    ):
        qualifications_value = component.get("qualifications")
        component_qualifications = tuple(
            item
            for item in (
                qualifications_value
                if isinstance(qualifications_value, Sequence)
                and not isinstance(qualifications_value, str)
                else ()
            )
            if isinstance(item, Mapping)
        )
        for item in component_qualifications:
            qualifications.append(
                {
                    "code": f"{operation}:{item.get('code', 'geo_query_failed')}",
                    "effect": "limits_interpretation",
                    "message": str(
                        item.get("message", "Geo query did not return a candidate.")
                    ),
                }
            )
        component_status = component_outcomes[operation]
        if (
            component_status in {"failed", "indeterminate", "not_requested"}
            and not component_qualifications
        ):
            qualifications.append(
                {
                    "code": f"{operation}:{component_status}",
                    "effect": "limits_interpretation",
                    "message": (
                        "The provider effect may have occurred; it was not retried."
                        if component_status == "indeterminate"
                        else f"The {operation} component was {component_status}."
                    ),
                }
            )
    result_value = {
        "component_qualifications": {
            key: list(component.get("qualifications", ()))
            for key, component in components.items()
        },
        "input_coordinate": query.coordinate.value(),
        "provider_coordinate": provider_coordinate,
        "provider": provider,
        "providers": providers,
        "language": "zh",
        "location": address,
        "pois": [dict(item) for item in place_candidates],
        "component_outcomes": component_outcomes,
        "status": result_status,
        "observed_at": observed_at_value,
        "logical_query_count": 1,
        "provider_request_count": provider_request_count,
        "billable_units": sum(item["billable_units"] for item in attempts)
        if provider_request_count is not None
        and all(isinstance(item.get("billable_units"), int) for item in attempts)
        else None,
        "attempts": [dict(item) for item in attempts],
    }
    if result_status in {"failed", "indeterminate"}:
        result_value["error"] = {
            "code": qualifications[0]["code"] if qualifications else "geo_query_failed",
            "message": (
                qualifications[0]["message"] if qualifications else "Geo query failed."
            ),
        }
    output = {
        "producer": {"identity": _PRODUCER, "profile": profile.descriptor()},
        "result": result_value,
        "observations": [attempt_observation],
    }
    return (attempt_observation, *normalize_geo_observations(output)), result_value


def _component_candidates(
    component: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    value = component.get("candidates")
    return tuple(
        item
        for item in (
            value if isinstance(value, Sequence) and not isinstance(value, str) else ()
        )
        if isinstance(item, Mapping)
    )


def _legacy_observation(
    database_path: Path,
    query: FrozenGeocodeQuery,
    profile: ReverseGeocodeProfile,
) -> Mapping[str, object] | None:
    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT work_records.output_json, work_records.producer_identity,
                   profile.dependency_value AS profile
            FROM work_records
            JOIN work_dependencies AS coordinate ON coordinate.work_id = work_records.work_id
             AND coordinate.dependency_key = 'normalized_coordinate'
            JOIN work_dependencies AS profile ON profile.work_id = work_records.work_id
             AND profile.dependency_key = 'reverse_geocode_profile'
            WHERE work_records.capability = 'reverse-geocode-observation'
              AND work_records.producer_identity IN (?, ?, ?)
              AND work_records.status = 'succeeded'
              AND coordinate.dependency_value = ?
            ORDER BY work_records.succeeded_at DESC, work_records.work_id
            """,
            (_V3_PRODUCER, _LEGACY_PRODUCER, _REVERSE_ONLY_PRODUCER, query.key),
        ).fetchall()
    eligible = []
    for row in rows:
        old_profile = json.loads(row["profile"])
        legacy_compatible = (
            profile.provider_profile == "geo-query-address-poi-v2"
            and profile.routing_policy == "ordered-per-coordinate-v1"
            and profile.refresh_token == _LEGACY_PROFILE["refresh_token"]
            and profile.nearby_radius_meters == 500
            and profile.max_places == 30
        )
        if old_profile != json.loads(profile.descriptor()) and not (
            legacy_compatible and old_profile == _LEGACY_PROFILE
        ):
            continue
        output = json.loads(row["output_json"])
        if not isinstance(output, Mapping) or not isinstance(
            output.get("result"), Mapping
        ):
            raise ValueError("Retained Geo Work is structurally invalid")
        eligible.append((row["producer_identity"], output))
    for identity, output in eligible:
        producer = output.get("producer", {})
        if identity == _V3_PRODUCER and producer.get("reused_from") == _LEGACY_PRODUCER:
            original = next(
                (value for kind, value in eligible if kind == _LEGACY_PRODUCER), None
            )
            if original is not None:
                return original
            # Guessed v3 migration statuses are not independent component proof.
            output = {
                **output,
                "producer": {**producer, "reused_from": _LEGACY_PRODUCER},
            }
        return output
    return None


def _upgrade_legacy_observation(
    output: Mapping[str, object],
) -> dict[str, object]:
    migrated = dict(output)
    observations = normalize_geo_observations(output)
    migrated["observations"] = [
        *[
            dict(item)
            for item in output.get("observations", ())
            if item.get("name") == "reverse_geocode_attempt"
        ],
        *observations,
    ]
    return migrated


def normalize_geo_observations(
    output: Mapping[str, object] | None,
    *,
    coordinate_available: bool = True,
    unrequested_reason: str = "historical_geo_unrecorded",
) -> tuple[dict[str, object], ...]:
    """One pure interpretation of fresh and provable retained component evidence."""
    output = output or {}
    observations = output.get("observations", ())
    names = {
        "reverse_geocode": "address_candidate",
        "nearby_places": "nearby_place_candidates",
    }
    existing = [
        dict(item) for item in observations if item.get("name") in names.values()
    ]
    if existing:
        if len(existing) != 2 or len({item["name"] for item in existing}) != 2:
            raise ValueError("Geo component observations must be unique and complete")
        from ._result_sqlite import _validate_observations

        _validate_observations(tuple(existing))
        for item in existing:
            if item["status"] == "available":
                if item["name"] == "address_candidate":
                    item["value"] = {
                        key: value
                        for key, value in item["value"].items()
                        if key != "provider_ref"
                    }
                else:
                    item["value"] = [
                        {
                            key: value
                            for key, value in candidate.items()
                            if key != "provider_ref"
                        }
                        for candidate in item["value"]
                    ]
        return tuple(existing)
    result = output.get("result", {})
    if not isinstance(result, Mapping):
        raise ValueError("Geo result must be an object")
    candidate = next(
        (
            item
            for item in observations
            if item.get("name") == "reverse_geocode_candidate"
        ),
        {},
    )
    value = candidate.get("value", {})
    value = value if isinstance(value, Mapping) else {}
    producer = output.get("producer", {})
    provenance = candidate.get("provenance", {})
    direct = (
        producer.get("identity") in {_PRODUCER, _V3_PRODUCER}
        or provenance.get("method") == "geo_query_tool_v1"
    )
    if producer.get("reused_from") == _LEGACY_PRODUCER:
        direct = False
    outcomes = (
        result.get("component_outcomes", value.get("component_outcomes", {}))
        if direct
        else {}
    )
    if outcomes and (not isinstance(outcomes, Mapping) or set(outcomes) != set(names)):
        raise ValueError("Geo component outcome set is contradictory")
    outcomes = dict(outcomes)
    address = result.get("location", value.get("address"))
    places = result.get("pois", value.get("pois", []))
    attempts = result.get("attempts", ())
    for observation in observations:
        if observation.get("name") == "reverse_geocode_attempt":
            details = observation.get("value", {})
            attempts = attempts or details.get("attempts", ())
    if not direct:
        for operation in names:
            proven = [item for item in attempts if item.get("operation") == operation]
            if proven:
                statuses = {item.get("status") for item in proven}
                outcomes[operation] = (
                    "success"
                    if "success" in statuses
                    else (
                        "no_result"
                        if "no_result" in statuses
                        else "indeterminate"
                        if "indeterminate" in statuses
                        else "failed"
                    )
                )
            elif address if operation == "reverse_geocode" else places:
                outcomes[operation] = "success"
    normalized = []
    for operation, name in names.items():
        outcome = outcomes.get(
            operation, "not_requested" if coordinate_available else "not_applicable"
        )
        states = {
            "success": "available",
            "no_result": "missing",
            "failed": "failed",
            "not_requested": "not_checked",
            "not_applicable": "not_applicable",
            "indeterminate": "failed",
        }
        if outcome not in states:
            raise ValueError("Geo component has an unknown outcome")
        component_value = address if operation == "reverse_geocode" else places
        if outcome == "success":
            if operation == "reverse_geocode":
                if (
                    not isinstance(address, Mapping)
                    or not address.get("formatted_address")
                    or not isinstance(address.get("components"), Mapping)
                ):
                    raise ValueError(
                        "Successful address requires a usable address candidate"
                    )
                component_value = {
                    key: value
                    for key, value in address.items()
                    if key != "provider_ref"
                }
            else:
                if (
                    not isinstance(places, (list, tuple))
                    or not places
                    or any(not isinstance(item, Mapping) or not item for item in places)
                ):
                    raise ValueError(
                        "Successful nearby lookup requires nonempty candidates"
                    )
                component_value = [
                    {key: value for key, value in item.items() if key != "provider_ref"}
                    for item in places
                ]
        elif component_value:
            raise ValueError("Non-success Geo component contains candidate data")
        basis = {"summary": f"{operation}: {outcome}", "outcome": outcome}
        if result.get("input_coordinate"):
            basis["query_coordinate"] = result["input_coordinate"]
        observed_at = result.get("observed_at", provenance.get("observed_at"))
        if observed_at and observed_at != "unknown":
            basis["observed_at"] = observed_at
        if producer.get("profile"):
            basis["profile"] = producer["profile"]
        if outcome == "not_requested":
            basis["code"] = unrequested_reason
        elif outcome == "not_applicable":
            basis["code"] = "coordinate_unavailable"
        observation = {"name": name, "status": states[outcome], "basis": basis}
        if outcome == "success":
            observation["value"] = component_value
        if outcome in {"failed", "indeterminate"}:
            observation["qualifications"] = [
                {
                    "code": "geo_effect_indeterminate"
                    if outcome == "indeterminate"
                    else "location_query_failed",
                    "effect": "blocks_use"
                    if outcome == "indeterminate"
                    else "limits_interpretation",
                    "message": "Geo effect is indeterminate; stop automatic continuation."
                    if outcome == "indeterminate"
                    else "Location lookup ended in a known service failure.",
                }
            ]
        details = result.get("component_qualifications", {}).get(operation, ())
        if details:
            observation.setdefault("qualifications", []).extend(
                {
                    "code": f"{operation}:{item['code']}",
                    "effect": "limits_interpretation",
                    "message": item["message"],
                }
                for item in details
            )
        normalized.append(observation)
    return tuple(normalized)


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
    return tuple(
        item for item in observations if item.get("name") == "reverse_geocode_attempt"
    ) + normalize_geo_observations(record.output), result


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
