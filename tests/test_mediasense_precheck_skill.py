from __future__ import annotations

import json
from pathlib import Path
import re


ROOT = Path(__file__).parents[1]
SKILL_DIR = ROOT / ".agents" / "skills" / "mediasense-precheck"
SKILL_PATH = SKILL_DIR / "SKILL.md"
OPENAI_PATH = SKILL_DIR / "agents" / "openai.yaml"
SCENARIOS = json.loads(
    (ROOT / "tests" / "fixtures" / "precheck-skill-forward-v1.json").read_text(
        encoding="utf-8"
    )
)["scenarios"]


def test_skill_package_is_minimal_and_normally_discoverable() -> None:
    files = sorted(
        path.relative_to(SKILL_DIR).as_posix()
        for path in SKILL_DIR.rglob("*")
        if path.is_file()
    )
    assert files == ["SKILL.md", "agents/openai.yaml"]

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
        ROOT / "docs/spec/spec-260827-1915A-precheck-run/index.md",
        ROOT / "docs/spec/spec-260827-1915A-precheck-run/precheck-run.tool.json",
        ROOT / "docs/spec/spec-260826-1546-precheck-read/index.md",
        ROOT / "docs/spec/spec-260826-1546-precheck-read/precheck-read.tool.json",
    }
    assert resolved == expected
    assert all(path.is_file() for path in resolved)


def test_forward_scenarios_cover_required_behavior_and_phase_boundaries() -> None:
    expected_coverage = {
        "positive_activation",
        "negative_activation",
        "initial_compression",
        "recompression",
        "interruption",
        "disconnect",
        "disk_full",
        "corrupt_item",
        "external_default_off",
        "reverse_geocode",
        "exact_confirmation",
        "skip_optional",
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
    assert {scenario["id"] for scenario in negative} == {
        "negative_apply_execution",
        "negative_plan_naming",
    }
    assert all(scenario["tool_route"] for scenario in positive)
    assert all(scenario["must"] and scenario["must_not"] for scenario in SCENARIOS)
    assert all(
        not any(
            forbidden in route
            for forbidden in ("sqlite", "cache", "filesystem", "shell")
        )
        for scenario in positive
        for route in scenario["tool_route"]
    )
