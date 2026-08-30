from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


ROOT = Path(__file__).parents[1]
SKILL = (ROOT / ".agents" / "skills" / "mediasense-plan" / "SKILL.md").read_text(
    encoding="utf-8"
)
SCENARIOS = json.loads(
    (ROOT / "tests" / "fixtures" / "plan-skill-geo-v1.json").read_text(
        encoding="utf-8"
    )
)["scenarios"]


def _plan_input_validator() -> Draft202012Validator:
    plan = json.loads(
        (
            ROOT
            / "docs"
            / "spec"
            / "spec-260827-1915B-plan-work"
            / "plan-work.tool.json"
        ).read_text(encoding="utf-8")
    )
    geo = json.loads(
        (
            ROOT
            / "docs"
            / "spec"
            / "spec-260830-2034-geo-query"
            / "geo-query.tool.json"
        ).read_text(encoding="utf-8")
    )
    registry = Registry().with_resource(
        geo["inputSchema"]["$id"], Resource.from_contents(geo["inputSchema"])
    )
    return Draft202012Validator(plan["inputSchema"], registry=registry)


def test_plan_skill_teaches_bounded_geo_enrichment_without_provider_escape() -> None:
    required = {
        "mediasense.plan.work",
        "enrich_geo",
        "resolve_place",
        "reverse_geocode",
        "nearby_places",
        "authorization_required",
        "provider observation",
        "trusted authorization boundary",
        "reopen",
    }
    assert all(term in SKILL for term in required)
    assert "never call a map provider" in SKILL
    assert "do not invoke Geo merely to manufacture a `refused`" in SKILL


def test_plan_geo_skill_scenarios_cover_selection_authority_and_stopping() -> None:
    covered = {tag for scenario in SCENARIOS for tag in scenario["covers"]}
    assert {
        "prefer_existing_evidence",
        "stop_condition",
        "geo_preflight",
        "exact_authorization",
        "plan_owned_observation",
        "bounded_continuation",
        "authorization_delta",
        "refusal",
        "zero_effect",
        "usable_fallback",
        "precheck_reopen",
        "stage_boundary",
    } <= covered
    assert all(scenario["must"] and scenario["must_not"] for scenario in SCENARIOS)


def test_plan_geo_skill_tool_routes_conform_to_proposed_plan_contract() -> None:
    validator = _plan_input_validator()
    for scenario in SCENARIOS:
        for step in scenario["tool_route"]:
            assert step["tool"] == "mediasense.plan.work"
            validator.validate(step["request"])
