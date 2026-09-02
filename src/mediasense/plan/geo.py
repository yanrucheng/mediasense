"""Plan-owned integration for authorization-bound Geo observations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import json
import re
from typing import Any
from uuid import uuid4

from mediasense.capabilities.geo import GeoAuthorization, GeoQueryTool
from mediasense.precheck.read import (
    PrecheckReadBoundary,
    require_precheck_read_boundary,
)
from mediasense.source_sets import (
    ResultSourceSetResolver,
    SourceSetResolutionError,
)

from ._sqlite import (
    IdempotencyConflict,
    RevisionConflict,
    SQLitePlanStore,
    WorkClosed,
    WorkNotFound,
)

_WORK_REF = re.compile(r"^plan-work:[^\s]+$")
_REVISION = re.compile(r"^work-revision:[^\s]+$")
_REQUEST_ID = re.compile(r"^request:[^\s]+$")
_SOURCE_REF = re.compile(r"^source-item:[^\s]+$")
_PERSISTED_OUTCOMES = {
    "success",
    "partial",
    "no_result",
    "failed",
    "indeterminate",
    "cancelled",
}


class PlanGeoAdapter:
    """Acquire Geo evidence without transferring Plan authority into Geo."""

    def __init__(
        self,
        store: SQLitePlanStore,
        precheck_read: PrecheckReadBoundary,
        geo_tool: GeoQueryTool,
        *,
        id_factory: Callable[[str], str] | None = None,
    ) -> None:
        self.store = store
        self.precheck_read = require_precheck_read_boundary(precheck_read)
        self.geo_tool = geo_tool
        self._id_factory = id_factory or (lambda prefix: f"{prefix}:{uuid4()}")

    def enrich(
        self,
        request: Mapping[str, Any],
        *,
        authorization: GeoAuthorization | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        payload = dict(request)
        _require_keys(
            payload,
            {"work_ref", "base_revision", "request_id", "geo_request"},
        )
        work_ref = _require_ref(payload["work_ref"], _WORK_REF, "work_ref")
        base_revision = _require_ref(
            payload["base_revision"], _REVISION, "base_revision"
        )
        request_id = _require_ref(payload["request_id"], _REQUEST_ID, "request_id")
        geo_request = payload["geo_request"]
        if not isinstance(geo_request, Mapping):
            raise ValueError("geo_request must be an object")
        if geo_request.get("retention") != "caller_state":
            raise ValueError("Plan Geo requests require caller_state retention")
        authorization_binding = (
            None if authorization is None else authorization.binding()
        )
        digest = _digest(
            {
                **payload,
                "authorization_binding": authorization_binding,
            }
        )
        replay = self.store.replay(request_id, digest)
        if replay is not None:
            return replay
        snapshot = self.store.snapshot(work_ref)
        if snapshot.state != "open":
            raise WorkClosed(work_ref)
        if snapshot.revision != base_revision:
            raise RevisionConflict(snapshot.revision)
        self._validate_subjects(snapshot.result_ref, geo_request)

        geo_result = self.geo_tool.handle(
            geo_request,
            authorization=authorization,
            cancelled=cancelled,
        )
        outcome = geo_result.get("outcome")
        if outcome not in _PERSISTED_OUTCOMES:
            return {
                "outcome": outcome,
                "action": "enrich_geo",
                "work_ref": work_ref,
                "result_ref": snapshot.result_ref,
                "revision": snapshot.revision,
                "state": snapshot.state,
                "geo_result": geo_result,
            }

        revision = self._id_factory("work-revision")
        observation = {
            "geo_request_id": geo_result["request_id"],
            "request_fingerprint": geo_result["request_fingerprint"],
            "authorization": (None if authorization is None else authorization.value()),
            "result": geo_result,
        }
        response = {
            "outcome": "ok",
            "action": "enrich_geo",
            "work_ref": work_ref,
            "result_ref": snapshot.result_ref,
            "revision": revision,
            "state": "open",
            "geo_result": geo_result,
        }
        return self.store.record_geo_observation(
            request_id=request_id,
            request_digest=digest,
            work_ref=work_ref,
            base_revision=base_revision,
            revision=revision,
            observation=observation,
            response=response,
        )

    def observations(self, work_ref: str) -> tuple[dict[str, Any], ...]:
        _require_ref(work_ref, _WORK_REF, "work_ref")
        return self.store.snapshot(work_ref).geo_observations

    def _validate_subjects(
        self, result_ref: str, geo_request: Mapping[str, Any]
    ) -> None:
        subjects = geo_request.get("subjects")
        if not isinstance(subjects, list) or not subjects:
            raise ValueError("geo_request subjects must be a non-empty array")
        resolver = ResultSourceSetResolver(result_ref, self.precheck_read)
        for subject in subjects:
            if not isinstance(subject, Mapping):
                raise ValueError("Geo subject must be an object")
            subject_ref = _require_ref(
                subject.get("subject_ref"), _SOURCE_REF, "subject_ref"
            )
            coordinate = subject.get("coordinate")
            if not isinstance(coordinate, Mapping):
                raise ValueError("Geo subject coordinate must be an object")
            try:
                view = resolver.inspect("source_item", subject_ref)
            except SourceSetResolutionError as error:
                raise ValueError(str(error)) from error
            if not _coordinate_is_observed(view, coordinate):
                raise ValueError(
                    f"Geo coordinate is not an observation of {subject_ref}"
                )


def _coordinate_is_observed(
    source_view: Mapping[str, Any], coordinate: Mapping[str, Any]
) -> bool:
    observations = source_view.get("observations")
    if not isinstance(observations, list):
        return False
    expected = {
        "latitude": coordinate.get("latitude"),
        "longitude": coordinate.get("longitude"),
        "datum": coordinate.get("datum", "WGS84"),
    }
    for observation in observations:
        if not isinstance(observation, Mapping):
            continue
        if observation.get("name") not in {"gps_coordinates", "gpx_coordinates"}:
            continue
        if observation.get("status") != "available":
            continue
        value = observation.get("value")
        if isinstance(value, Mapping) and all(
            value.get(key) == item for key, item in expected.items()
        ):
            return True
    return False


def _require_keys(value: Mapping[str, Any], required: set[str]) -> None:
    missing = required - set(value)
    unknown = set(value) - required
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"unsupported fields: {', '.join(sorted(unknown))}")


def _require_ref(value: object, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError(f"{name} is invalid")
    return value


def _digest(value: object) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


__all__ = [
    "IdempotencyConflict",
    "PlanGeoAdapter",
    "RevisionConflict",
    "WorkClosed",
    "WorkNotFound",
]
