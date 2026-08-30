from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from jsonschema import Draft202012Validator
import pytest
from referencing import Registry, Resource

from mediasense.capabilities.geo import (
    GeoAuthorization,
    GeoCandidate,
    GeoCandidateKind,
    GeoComponentResult,
    GeoComponentStatus,
    GeoCoordinate,
    GeoOperation,
    GeoOperationJournal,
    GeoProviderAttempt,
    GeoProviderCapabilities,
    GeoProviderExecution,
    GeoQueryTool,
    MapDatum,
    OrderedGeoRoutingPolicy,
)
from mediasense.capabilities.geo.service import GeoCapability
from mediasense.capabilities.geo.tool import _parse_request
from mediasense.plan import PlanGeoAdapter, PlanPreviewRenderer, PlanWorkTool

from _plan_support import MockPrecheckReader, StableIdFactory, valid_candidate

ROOT = Path(__file__).parents[1]


@dataclass
class FakeProvider:
    capabilities: GeoProviderCapabilities
    calls: int = 0
    fail_latitude: float | None = None

    def execute(
        self,
        operation: GeoOperation,
        coordinate: GeoCoordinate,
        *,
        locale: str,
        radius_meters: float | None = None,
        max_places: int | None = None,
    ) -> GeoProviderExecution:
        self.calls += 1
        status = (
            GeoComponentStatus.FAILED
            if self.fail_latitude == coordinate.latitude
            else GeoComponentStatus.SUCCESS
        )
        candidates = (
            (
                GeoCandidate(
                    GeoCandidateKind.ADDRESS,
                    "Shanghai Disneyland area",
                    coordinate=coordinate,
                ),
            )
            if status is GeoComponentStatus.SUCCESS
            else ()
        )
        return GeoProviderExecution(
            GeoComponentResult(
                operation,
                status,
                (),
                coordinate,
                candidates,
            ),
            GeoProviderAttempt(
                self.capabilities.provider_id,
                operation,
                status,
                coordinate,
                coordinate,
                1,
                1,
            ),
        )


def _reader_with_coordinate() -> MockPrecheckReader:
    reader = MockPrecheckReader()
    source_ref = "source-item:215"
    view = reader.views[("source_item", source_ref)]
    view.setdefault("observations", []).append(
        {
            "name": "gps_coordinates",
            "status": "available",
            "value": {
                "latitude": 31.1434,
                "longitude": 121.6579,
                "datum": "WGS84",
            },
            "basis": "Test coordinate.",
        }
    )
    return reader


def _setup(tmp_path: Path):
    ids = StableIdFactory()
    reader = _reader_with_coordinate()
    plan_store = tmp_path / "plan-store"
    provider = FakeProvider(
        GeoProviderCapabilities(
            "provider-a",
            (GeoOperation.REVERSE_GEOCODE, GeoOperation.NEARBY_PLACES),
            MapDatum.WGS84,
            max_billable_units_per_operation=1,
        )
    )
    capability = GeoCapability(
        {"provider-a": provider}, OrderedGeoRoutingPolicy(("provider-a",))
    )
    geo_tool = GeoQueryTool(
        capability,
        GeoOperationJournal(tmp_path / "geo-runtime" / "journal.sqlite3"),
    )
    plan_tool = PlanWorkTool(
        plan_store,
        reader,
        id_factory=ids,
        geo_tool=geo_tool,
    )
    created = plan_tool.handle(
        {
            "action": "create",
            "result_ref": reader.result_ref,
            "request_id": "request:create-plan-geo",
        }
    )
    adapter = PlanGeoAdapter(plan_tool.store, reader, geo_tool, id_factory=ids)
    return reader, plan_tool, adapter, provider, capability, created


def _geo_request() -> dict[str, object]:
    return {
        "request_id": "request:geo-plan-one",
        "operation": "resolve_place",
        "subjects": [
            {
                "subject_ref": "source-item:215",
                "coordinate": {
                    "latitude": 31.1434,
                    "longitude": 121.6579,
                    "datum": "WGS84",
                },
            }
        ],
        "locale": "zh-CN",
        "retention": "caller_state",
    }


def _plan_request(created: dict[str, object]) -> dict[str, object]:
    return {
        "work_ref": created["work_ref"],
        "base_revision": created["revision"],
        "request_id": "request:plan-geo-one",
        "geo_request": _geo_request(),
    }


def _authorization(
    capability: GeoCapability, request: dict[str, object]
) -> GeoAuthorization:
    parsed = _parse_request(request)
    return GeoAuthorization(
        "human:plan-owner",
        parsed.fingerprint(),
        datetime.now(timezone.utc),
        capability.proposed_envelope(parsed),
    )


def _plan_geo_validators() -> tuple[Draft202012Validator, Draft202012Validator]:
    plan_contract = json.loads(
        (
            ROOT
            / "docs"
            / "spec"
            / "spec-260827-1915B-plan-work"
            / "plan-work.tool.json"
        ).read_text(encoding="utf-8")
    )
    geo_contract = json.loads(
        (
            ROOT
            / "docs"
            / "spec"
            / "spec-260830-2034-geo-query"
            / "geo-query.tool.json"
        ).read_text(encoding="utf-8")
    )
    frozen = json.loads(
        (
            ROOT
            / "docs"
            / "spec"
            / "spec-260827-1138-frozen-plan"
            / "frozen-plan.schema.json"
        ).read_text(encoding="utf-8")
    )
    registry = Registry()
    for resource in (frozen, geo_contract["inputSchema"], geo_contract["outputSchema"]):
        registry = registry.with_resource(
            resource["$id"], Resource.from_contents(resource)
        )
    return (
        Draft202012Validator(plan_contract["inputSchema"], registry=registry),
        Draft202012Validator(plan_contract["outputSchema"], registry=registry),
    )


def test_plan_geo_preflight_does_not_change_revision_or_state(tmp_path: Path) -> None:
    _reader, plan_tool, adapter, provider, _capability, created = _setup(tmp_path)

    result = adapter.enrich(_plan_request(created))
    snapshot = plan_tool.store.snapshot(str(created["work_ref"]))

    assert result["outcome"] == "authorization_required"
    assert result["revision"] == created["revision"]
    assert snapshot.revision == created["revision"]
    assert snapshot.geo_observations == ()
    assert provider.calls == 0


def test_plan_work_tool_exposes_geo_enrichment_without_another_stage_tool(
    tmp_path: Path,
) -> None:
    _reader, plan_tool, _adapter, provider, capability, created = _setup(tmp_path)
    request = {"action": "enrich_geo", **_plan_request(created)}

    preflight = plan_tool.handle(request)
    authorization = _authorization(capability, request["geo_request"])
    accepted = plan_tool.handle(request, geo_authorization=authorization)

    assert preflight["outcome"] == "authorization_required"
    assert accepted["outcome"] == "ok"
    assert accepted["action"] == "enrich_geo"
    assert provider.calls == 1


def test_plan_work_reports_unconfigured_geo_capability(tmp_path: Path) -> None:
    reader = _reader_with_coordinate()
    ids = StableIdFactory()
    tool = PlanWorkTool(tmp_path / "plan-store", reader, id_factory=ids)
    created = tool.handle(
        {
            "action": "create",
            "result_ref": reader.result_ref,
            "request_id": "request:create-without-geo",
        }
    )

    result = tool.handle({"action": "enrich_geo", **_plan_request(created)})

    assert result["outcome"] == "error"
    assert result["error"]["code"] == "capability_unavailable"


def test_plan_geo_requests_and_results_conform_to_proposed_contract(
    tmp_path: Path,
) -> None:
    _reader, plan_tool, _adapter, _provider, capability, created = _setup(tmp_path)
    input_validator, output_validator = _plan_geo_validators()
    request = {"action": "enrich_geo", **_plan_request(created)}

    input_validator.validate(request)
    preflight = plan_tool.handle(request)
    output_validator.validate(preflight)
    authorization = _authorization(capability, request["geo_request"])
    accepted = plan_tool.handle(request, geo_authorization=authorization)
    output_validator.validate(accepted)
    inspected = plan_tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": accepted["revision"],
            "sections": ["geo_evidence"],
        }
    )
    output_validator.validate(inspected)


def test_plan_geo_persists_observation_in_new_revision(tmp_path: Path) -> None:
    _reader, plan_tool, adapter, provider, capability, created = _setup(tmp_path)
    plan_request = _plan_request(created)
    authorization = _authorization(capability, plan_request["geo_request"])

    result = adapter.enrich(plan_request, authorization=authorization)
    snapshot = plan_tool.store.snapshot(str(created["work_ref"]))

    assert result["outcome"] == "ok"
    assert result["revision"] != created["revision"]
    assert snapshot.revision == result["revision"]
    assert snapshot.result_ref == created["result_ref"]
    assert len(snapshot.geo_observations) == 1
    observation = snapshot.geo_observations[0]
    assert observation["result"]["outcome"] == "success"
    assert observation["authorization"]["principal_ref"] == "human:plan-owner"
    assert provider.calls == 1

    inspected = plan_tool.handle(
        {
            "action": "inspect",
            "work_ref": created["work_ref"],
            "revision": result["revision"],
            "sections": ["geo_evidence"],
        }
    )
    assert inspected["sections"]["geo_evidence"]["count"] == 1

    updated = plan_tool.handle(
        {
            "action": "update",
            "work_ref": created["work_ref"],
            "base_revision": result["revision"],
            "candidate_content": valid_candidate(),
            "request_id": "request:update-after-geo",
        }
    )
    calls_before_preview = provider.calls
    document = PlanPreviewRenderer(plan_tool).build(
        str(created["work_ref"]), str(updated["revision"])
    )
    html = PlanPreviewRenderer(plan_tool).render_html(document)
    assert "Shanghai Disneyland area" in html
    assert "not confirmed Plan truth" in html
    assert provider.calls == calls_before_preview


def test_plan_geo_replay_does_not_repeat_effect_or_revision(tmp_path: Path) -> None:
    _reader, plan_tool, adapter, provider, capability, created = _setup(tmp_path)
    request = _plan_request(created)
    authorization = _authorization(capability, request["geo_request"])

    first = adapter.enrich(request, authorization=authorization)
    replay = adapter.enrich(request, authorization=authorization)

    assert replay == first
    assert plan_tool.store.snapshot(str(created["work_ref"])).revision == first["revision"]
    assert provider.calls == 1


def test_plan_geo_rejects_coordinate_not_observed_in_bound_result(tmp_path: Path) -> None:
    _reader, _plan_tool, adapter, provider, capability, created = _setup(tmp_path)
    request = _plan_request(created)
    request["geo_request"]["subjects"][0]["coordinate"]["latitude"] = 0.0
    authorization = _authorization(capability, request["geo_request"])

    with pytest.raises(ValueError, match="not an observation"):
        adapter.enrich(request, authorization=authorization)

    assert provider.calls == 0


def test_plan_geo_requires_plan_local_retention(tmp_path: Path) -> None:
    _reader, _plan_tool, adapter, provider, _capability, created = _setup(tmp_path)
    request = _plan_request(created)
    request["geo_request"]["retention"] = "none"

    with pytest.raises(ValueError, match="caller_state retention"):
        adapter.enrich(request)

    assert provider.calls == 0


def test_plan_geo_refuses_stale_authority_without_changing_state(tmp_path: Path) -> None:
    _reader, plan_tool, adapter, provider, capability, created = _setup(tmp_path)
    request = _plan_request(created)
    parsed = _parse_request(request["geo_request"])
    stale = GeoAuthorization(
        "human:plan-owner",
        "sha256:" + "a" * 64,
        datetime.now(timezone.utc),
        capability.proposed_envelope(parsed),
    )

    result = adapter.enrich(request, authorization=stale)
    snapshot = plan_tool.store.snapshot(str(created["work_ref"]))

    assert result["outcome"] == "refused"
    assert snapshot.revision == created["revision"]
    assert snapshot.geo_observations == ()
    assert provider.calls == 0


def test_plan_geo_replay_survives_adapter_restart(tmp_path: Path) -> None:
    reader, plan_tool, adapter, provider, capability, created = _setup(tmp_path)
    request = _plan_request(created)
    authorization = _authorization(capability, request["geo_request"])
    first = adapter.enrich(request, authorization=authorization)

    restarted_provider = FakeProvider(provider.capabilities)
    restarted_capability = GeoCapability(
        {"provider-a": restarted_provider},
        OrderedGeoRoutingPolicy(("provider-a",)),
    )
    restarted_geo_tool = GeoQueryTool(
        restarted_capability,
        GeoOperationJournal(tmp_path / "geo-runtime" / "journal.sqlite3"),
    )
    restarted_plan = PlanWorkTool(
        tmp_path / "plan-store",
        reader,
        id_factory=StableIdFactory(),
        geo_tool=restarted_geo_tool,
    )
    replay = restarted_plan.handle(
        {"action": "enrich_geo", **request},
        geo_authorization=authorization,
    )

    assert replay == first
    assert provider.calls == 1
    assert restarted_provider.calls == 0


def test_plan_geo_partial_result_keeps_each_subject_outcome(tmp_path: Path) -> None:
    reader, plan_tool, adapter, provider, capability, created = _setup(tmp_path)
    second_ref = "source-item:geo-second"
    reader.views[("source_item", second_ref)] = {
        "kind": "source_item",
        "ref": second_ref,
        "observations": [
            {
                "name": "gps_coordinates",
                "status": "available",
                "value": {
                    "latitude": 35.6580,
                    "longitude": 139.7013,
                    "datum": "WGS84",
                },
            }
        ],
    }
    provider.fail_latitude = 35.6580
    request = _plan_request(created)
    request["geo_request"]["subjects"].append(
        {
            "subject_ref": second_ref,
            "coordinate": {
                "latitude": 35.6580,
                "longitude": 139.7013,
                "datum": "WGS84",
            },
        }
    )
    authorization = _authorization(capability, request["geo_request"])

    result = adapter.enrich(request, authorization=authorization)
    stored = plan_tool.store.snapshot(str(created["work_ref"])).geo_observations

    assert result["geo_result"]["outcome"] == "partial"
    assert [item["status"] for item in result["geo_result"]["components"]] == [
        "success",
        "failed",
    ]
    assert stored[0]["result"] == result["geo_result"]
    assert provider.calls == 2


def test_plan_geo_nearby_continuation_gets_a_new_bound_revision(tmp_path: Path) -> None:
    _reader, plan_tool, adapter, provider, capability, created = _setup(tmp_path)
    first_request = _plan_request(created)
    first_authorization = _authorization(capability, first_request["geo_request"])
    first = adapter.enrich(first_request, authorization=first_authorization)

    nearby_geo = _geo_request()
    nearby_geo.update(
        {
            "request_id": "request:geo-plan-nearby",
            "operation": "nearby_places",
            "radius_meters": 500,
            "max_places": 10,
        }
    )
    nearby_request = {
        "work_ref": created["work_ref"],
        "base_revision": first["revision"],
        "request_id": "request:plan-geo-nearby",
        "geo_request": nearby_geo,
    }
    nearby_authorization = _authorization(capability, nearby_geo)

    nearby = adapter.enrich(nearby_request, authorization=nearby_authorization)
    snapshot = plan_tool.store.snapshot(str(created["work_ref"]))

    assert nearby["outcome"] == "ok"
    assert nearby["geo_result"]["operation"] == "nearby_places"
    assert nearby["revision"] != first["revision"]
    assert len(snapshot.geo_observations) == 2
    assert provider.calls == 2


def test_plan_store_migrates_existing_v1_database_for_geo_observations(
    tmp_path: Path,
) -> None:
    database = tmp_path / "plan-store" / "work.sqlite3"
    database.parent.mkdir(parents=True)
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE internal_schema (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                version INTEGER NOT NULL
            );
            INSERT INTO internal_schema(singleton, version) VALUES (1, 1);
            CREATE TABLE plan_works (
                work_ref TEXT PRIMARY KEY,
                result_ref TEXT NOT NULL,
                state TEXT NOT NULL CHECK (state IN ('open', 'closed')),
                revision TEXT NOT NULL,
                organization_preferences_json TEXT NOT NULL,
                candidate_json TEXT,
                candidate_identity TEXT,
                plan_ref TEXT NOT NULL UNIQUE,
                published_path TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at TEXT
            );
            """
        )

    reader = _reader_with_coordinate()
    PlanWorkTool(tmp_path / "plan-store", reader, id_factory=StableIdFactory())

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT version FROM internal_schema WHERE singleton = 1"
        ).fetchone()[0]
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(plan_works)")
        }
    assert version == 2
    assert "geo_observations_json" in columns
