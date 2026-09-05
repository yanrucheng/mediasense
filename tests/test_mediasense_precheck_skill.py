from __future__ import annotations

import json
from pathlib import Path
import re

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[1]
SKILL_DIR = (
    ROOT
    / "src"
    / "mediasense"
    / "_resources"
    / "skills"
    / "mediasense-precheck"
)
SKILL_PATH = SKILL_DIR / "SKILL.md"
OPENAI_PATH = SKILL_DIR / "agents" / "openai.yaml"
RUN_TOOL_PATH = (
    ROOT / "docs" / "spec" / "spec-260827-1915A-precheck-run" / "precheck-run.tool.json"
)
READ_TOOL_PATH = (
    ROOT
    / "docs"
    / "spec"
    / "spec-260826-1546-precheck-read"
    / "precheck-read.tool.json"
)
RUN_TOOL = json.loads(RUN_TOOL_PATH.read_text(encoding="utf-8"))
READ_TOOL = json.loads(READ_TOOL_PATH.read_text(encoding="utf-8"))
TOOL_SCHEMAS = {
    RUN_TOOL["name"]: RUN_TOOL["inputSchema"],
    READ_TOOL["name"]: READ_TOOL["inputSchema"],
}
SCENARIOS = json.loads(
    (ROOT / "tests" / "fixtures" / "precheck-skill-forward-v1.json").read_text(
        encoding="utf-8"
    )
)["scenarios"]


def _operation_constants(value: object) -> set[str]:
    if isinstance(value, list):
        return set().union(*(_operation_constants(item) for item in value))
    if not isinstance(value, dict):
        return set()
    operations: set[str] = set()
    properties = value.get("properties")
    if isinstance(properties, dict):
        for field in ("action", "operation"):
            operation = properties.get(field)
            if isinstance(operation, dict) and isinstance(
                operation.get("const"), str
            ):
                operations.add(operation["const"])
    return operations | set().union(
        *(_operation_constants(item) for item in value.values())
    )


def test_skill_package_is_minimal_and_normally_discoverable() -> None:
    files = sorted(
        path.relative_to(SKILL_DIR).as_posix()
        for path in SKILL_DIR.rglob("*")
        if path.is_file()
    )
    assert files == [
        "SKILL.md",
        "agents/openai.yaml",
        "references/precheck-read.tool.json",
        "references/precheck-run.tool.json",
    ]

    skill = SKILL_PATH.read_text(encoding="utf-8")
    frontmatter = skill.split("---", 2)[1]
    assert re.search(r"^name: mediasense-precheck$", frontmatter, re.MULTILINE)
    description = next(
        line.removeprefix("description: ").strip('"')
        for line in frontmatter.splitlines()
        if line.startswith("description: ")
    )
    assert "Prepares or re-prepares" in description
    assert "not for Plan grouping or naming" in description
    assert "Apply filesystem execution" in description

    metadata = OPENAI_PATH.read_text(encoding="utf-8")
    assert "$mediasense-precheck" in metadata
    assert "allow_implicit_invocation: false" not in metadata


def test_skill_links_only_to_existing_authoritative_precheck_contracts() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]+)\)", skill)
    resolved = {(SKILL_DIR / link).resolve() for link in links}
    expected = {
        SKILL_DIR / "references/precheck-run.tool.json",
        SKILL_DIR / "references/precheck-read.tool.json",
    }
    assert resolved == expected
    assert all(path.is_file() for path in resolved)
    assert (
        SKILL_DIR / "references/precheck-run.tool.json"
    ).read_bytes() == RUN_TOOL_PATH.read_bytes()
    assert (
        SKILL_DIR / "references/precheck-read.tool.json"
    ).read_bytes() == READ_TOOL_PATH.read_bytes()


def test_skill_keeps_reverse_geocoding_run_scoped_and_batch_bound() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")
    assert "trusted Human confirmation bound to the exact disclosure identity" in skill
    assert "per-coordinate confirmation" in skill
    assert "there is no public Geo Tool" in skill


def test_skill_distinguishes_source_accounting_from_execution_liveness() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert "`progress` is Source Item accounting" in skill
    assert "`activity` is current execution evidence" in skill
    assert "`no_recent_progress`" in skill
    assert "`suspected_stalled`" in skill
    assert "percentage, ETA, throughput, or success promise" in skill


def test_skill_keeps_scope_facts_and_agent_judgment_separate() -> None:
    skill = SKILL_PATH.read_text(encoding="utf-8")

    assert "Treat the returned inventory as Tool\nfacts" in skill
    assert "Agent judgment" in skill
    assert "never claim\nthat a dot name" in skill
    assert "`status.scope_path`" in skill
    assert "Never replay a stale\nselection" in skill


def test_forward_scenarios_cover_required_behavior_and_phase_boundaries() -> None:
    expected_coverage = {
        "positive_activation",
        "negative_activation",
        "initial_compression",
        "scope_inventory",
        "scope_interpretation",
        "scope_confirmation",
        "stale_scope_refusal",
        "unattended_safety",
        "cost_reporting",
        "recompression",
        "diagnosis_led_revision",
        "observed_counts",
        "interruption",
        "disconnect",
        "disk_full",
        "corrupt_item",
        "external_default_off",
        "reverse_geocode",
        "exact_confirmation",
        "coordinate_privacy",
        "authorization_declined",
        "partial_result",
        "plan_ready",
        "blocked_result",
        "human_decision",
        "exact_handoff",
        "plan_boundary",
        "apply_boundary",
    }
    covered = {tag for scenario in SCENARIOS for tag in scenario["covers"]}
    assert expected_coverage <= covered

    positive = [scenario for scenario in SCENARIOS if scenario["expected_activation"]]
    negative = [
        scenario for scenario in SCENARIOS if not scenario["expected_activation"]
    ]
    assert positive
    assert all(
        scenario["expected_owner"] == "mediasense-precheck" for scenario in positive
    )
    assert {scenario["id"] for scenario in negative} == {
        "negative_apply_execution",
        "negative_plan_naming",
    }
    assert {scenario["expected_owner"] for scenario in negative} == {
        "mediasense-apply",
        "mediasense-plan",
    }
    assert all(scenario["tool_route"] for scenario in positive)
    assert all(not scenario["tool_route"] for scenario in negative)
    assert all(scenario["must"] and scenario["must_not"] for scenario in SCENARIOS)

    contract_operations = {
        name: _operation_constants(schema) for name, schema in TOOL_SCHEMAS.items()
    }
    for scenario in positive:
        for step in scenario["tool_route"]:
            assert set(step) == {"tool", "request"}
            tool_name = step["tool"]
            assert tool_name in TOOL_SCHEMAS
            operation = step["request"].get("action", step["request"].get("operation"))
            assert operation in contract_operations[tool_name]
            Draft202012Validator(TOOL_SCHEMAS[tool_name]).validate(step["request"])
