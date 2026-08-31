from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from mediasense.cli import run
from mediasense.runtime.composition import tool_descriptors
from mediasense.runtime.resources import CONTRACT_FILES, contract_path, skill_roots
from mediasense.runtime.skills import install_skills
from mediasense.runtime.versioning import application_version


def test_version_command_uses_installed_distribution_metadata(capsys) -> None:
    assert run(["version", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == {"version": application_version()}


def test_doctor_distinguishes_optional_missing_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("MEDIASENSE_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(
        "mediasense.runtime.doctor.shutil.which",
        lambda name: "/usr/bin/uv" if name == "uv" else None,
    )
    monkeypatch.setattr("mediasense.runtime.doctor.find_spec", lambda name: None)

    assert run(["doctor", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    checks = {item["name"]: item for item in result["checks"]}
    assert result["status"] == "ok"
    assert checks["exiftool"]["status"] == "warning"
    assert checks["ffmpeg"]["status"] == "warning"
    assert checks["local_models"]["status"] == "warning"


def test_dataset_open_command_reports_selected_workspace(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace = tmp_path / "workspace"

    assert (
        run(
            [
                "dataset",
                "open",
                str(source),
                "--workspace",
                str(workspace),
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["selection_tier"] == "explicit"
    assert result["workspace"] == str(workspace)
    assert result["configuration"]["offline"] is True

    assert run(["dataset", "inspect", str(workspace), "--json"]) == 0
    inspected = json.loads(capsys.readouterr().out)
    assert inspected["dataset_ref"] == result["dataset_ref"]


def test_invalid_user_config_blocks_before_dataset_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace = tmp_path / "workspace"
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "config.toml").write_text(
        "[runtime]\nunknown = true\n", encoding="utf-8"
    )
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(config_root))

    exit_code = run(
        [
            "dataset",
            "open",
            str(source),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["error"]["code"] == "configuration_invalid"
    assert not workspace.exists()


def test_tool_discovery_lists_dataset_and_six_existing_tools(capsys) -> None:
    assert run(["tools", "list", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert [item["name"] for item in result["tools"]] == [
        "mediasense.dataset.open",
        "mediasense.precheck.run",
        "mediasense.precheck.read",
        "mediasense.plan.work",
        "mediasense.geo.query",
        "mediasense.apply.run",
        "mediasense.apply.read",
    ]
    assert len(tool_descriptors()) == 7

    assert run(["tools", "show", "mediasense.precheck.run", "--json"]) == 0
    detail = json.loads(capsys.readouterr().out)
    assert detail["input_schema"]["$id"] == ("urn:mediasense:tool:precheck-run-input")


def test_tool_call_reports_dataset_binding_and_business_result(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    workspace = tmp_path / "workspace"

    exit_code = run(
        [
            "tools",
            "call",
            "mediasense.precheck.run",
            "--source",
            str(source),
            "--workspace",
            str(workspace),
            "--request",
            '{"action":"status","run_ref":"precheck-run:not-found"}',
            "--json",
        ]
    )
    value = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert value["dataset"]["workspace"] == str(workspace)
    assert value["dataset"]["configuration"]["offline"] is True
    assert value["result"]["error"]["code"] == "run_not_found"


def test_packaged_resources_match_repository_authorities() -> None:
    root = Path(__file__).resolve().parents[1]
    authorities = {
        "mediasense.dataset.open": root
        / "docs/spec/spec-260831-0009-dataset-open/dataset-open.tool.json",
        "mediasense.precheck.run": root
        / "docs/spec/spec-260827-1915A-precheck-run/precheck-run.tool.json",
        "mediasense.precheck.read": root
        / "docs/spec/spec-260826-1546-precheck-read/precheck-read.tool.json",
        "mediasense.plan.work": root
        / "docs/spec/spec-260827-1915B-plan-work/plan-work.tool.json",
        "mediasense.geo.query": root
        / "docs/spec/spec-260830-2034-geo-query/geo-query.tool.json",
        "mediasense.apply.run": root
        / "docs/spec/spec-260829-0050-apply/apply-run.tool.json",
        "mediasense.apply.read": root
        / "docs/spec/spec-260829-0050-apply/apply-read.tool.json",
    }
    for name in CONTRACT_FILES:
        assert contract_path(name).read_bytes() == authorities[name].read_bytes()
        contract = json.loads(contract_path(name).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(contract["inputSchema"])
        Draft202012Validator.check_schema(contract["outputSchema"])
    for packaged in skill_roots():
        source = root / ".agents" / "skills" / packaged.name / "SKILL.md"
        assert (packaged / "SKILL.md").read_bytes() == source.read_bytes()
        source_root = source.parent
        packaged_files = {
            path.relative_to(packaged): path
            for path in packaged.rglob("*")
            if path.is_file()
        }
        source_files = {
            path.relative_to(source_root): path
            for path in source_root.rglob("*")
            if path.is_file()
        }
        assert set(packaged_files) == set(source_files)
        assert all(
            packaged_files[relative].read_bytes() == source_files[relative].read_bytes()
            for relative in source_files
        )


def test_skill_install_is_idempotent_and_refuses_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "skills"

    first = install_skills(target)
    second = install_skills(target)

    assert first["installed"] == [
        "mediasense-precheck",
        "mediasense-plan",
        "mediasense-apply",
    ]
    assert second["installed"] == []
    assert second["unchanged"] == first["installed"]

    changed = target / "mediasense-plan" / "SKILL.md"
    changed.write_text("locally changed\n", encoding="utf-8")
    result = run(["skills", "install", "--target", str(target), "--json"])
    assert result == 2
