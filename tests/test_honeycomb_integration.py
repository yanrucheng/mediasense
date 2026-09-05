from __future__ import annotations

from pathlib import Path
import re

import pytest

from mediasense.cli import build_parser, run
from mediasense.runtime.resources import skill_roots
from mediasense.runtime.versioning import application_version


ROOT = Path(__file__).parents[1]
PACKAGED_SKILL_ROOT = ROOT / "src" / "mediasense" / "_resources" / "skills"
TOOL_NAMES = {
    "mediasense.dataset.open",
    "mediasense.precheck.run",
    "mediasense.precheck.read",
    "mediasense.plan.work",
    "mediasense.apply.run",
    "mediasense.apply.read",
}


def test_source_checkout_is_not_an_implicit_honeycomb() -> None:
    assert not (ROOT / ".codex" / "config.toml").exists()
    for name in (
        "mediasense",
        "mediasense-precheck",
        "mediasense-plan",
        "mediasense-apply",
    ):
        assert not (ROOT / ".agents" / "skills" / name).exists()


def test_skills_install_requires_and_uses_only_explicit_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    with pytest.raises(SystemExit) as missing:
        build_parser().parse_args(["skills", "install"])
    assert missing.value.code == 2

    home = tmp_path / "home"
    dataset_workspace = tmp_path / "dataset-workspace"
    honeycomb = tmp_path / "chosen-honeycomb"
    home.mkdir()
    dataset_workspace.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("MEDIASENSE_DATA_HOME", str(dataset_workspace))
    target = honeycomb / ".agents" / "skills"

    assert run(["skills", "install", "--target", str(target), "--json"]) == 0
    capsys.readouterr()
    assert {path.name for path in target.iterdir()} == {
        "mediasense",
        "mediasense-precheck",
        "mediasense-plan",
        "mediasense-apply",
    }
    assert (
        target
        / "mediasense-plan"
        / "references"
        / "organization-profiles.md"
    ).is_file()
    assert not (home / ".codex").exists()
    assert not (home / ".agents").exists()
    assert list(dataset_workspace.iterdir()) == []


def test_entry_skill_owns_bootstrap_and_stage_local_prerequisites() -> None:
    skill_root = PACKAGED_SKILL_ROOT
    entry = (skill_root / "mediasense" / "SKILL.md").read_text()
    precheck = (skill_root / "mediasense-precheck" / "SKILL.md").read_text()
    plan = (skill_root / "mediasense-plan" / "SKILL.md").read_text()
    apply = (skill_root / "mediasense-apply" / "SKILL.md").read_text()

    assert "Establish readiness" in entry
    assert "<honeycomb>/.codex/config.toml" in entry
    assert "trusted project" in entry
    assert "MediaSense `0.7.x` CLI" in entry
    assert "MediaSense `0.2.x` CLI" not in entry
    assert "current Agent session" in entry
    assert "cannot load it dynamically" in entry
    assert TOOL_NAMES <= set(re.findall(r"`(mediasense\.[a-z.]+)`", entry))
    assert "Route to the owning stage" in entry
    for stage_name in (
        "mediasense-precheck",
        "mediasense-plan",
        "mediasense-apply",
    ):
        assert stage_name in entry
    assert "uv tool install" not in precheck
    for stage in (precheck, plan, apply):
        assert "mediasense` product entry Skill's local" in stage
        assert "bootstrap" in stage
        assert "uv tool install" not in stage


def test_packaged_skills_match_application_release_line() -> None:
    major, minor, _patch = application_version().split(".", maxsplit=2)
    expected = f"{major}.{minor}.x"
    release_lines = re.compile(r"\b\d+\.\d+\.x\b")

    for root in skill_roots():
        declared = set(release_lines.findall((root / "SKILL.md").read_text()))
        assert declared == {expected}, (root.name, declared, expected)


def test_active_guidance_has_no_obsolete_default_commands() -> None:
    roots = [
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "readme",
        PACKAGED_SKILL_ROOT,
        ROOT / "docs" / "design",
        ROOT / "docs" / "spec",
        ROOT / "docs" / "eval",
        ROOT / "docs" / "delegation",
        ROOT / "openspec" / "specs",
        ROOT / "openspec" / "changes",
    ]
    files: list[Path] = []
    for root in roots:
        files.extend([root] if root.is_file() else root.rglob("*.md"))
    forbidden = {
        "user-level Codex MCP command": re.compile(
            r"(?m)^\s*codex mcp add mediasense -- mediasense mcp\s*$"
        ),
        "user-level Codex Skill target": re.compile(
            r"(?m)^\s*mediasense skills install --target ~/\.codex/skills\s*$"
        ),
    }

    findings = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for label, pattern in forbidden.items():
            historical = path == (
                ROOT
                / "docs"
                / "delegation"
                / "td-260830-2227-mediasense-distribution"
                / "01-result-mediasense.md"
            )
            if pattern.search(text) and not historical:
                findings.append(f"{path.relative_to(ROOT)}: {label}")
    assert findings == []

    historical_text = (
        ROOT
        / "docs"
        / "delegation"
        / "td-260830-2227-mediasense-distribution"
        / "01-result-mediasense.md"
    ).read_text(encoding="utf-8")
    warning = historical_text.index("Historical Agent connection (superseded)")
    assert warning < historical_text.index("codex mcp add mediasense -- mediasense mcp")
    assert warning < historical_text.index(
        "mediasense skills install --target ~/.codex/skills"
    )
