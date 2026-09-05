"""Locate release snapshots of contracts and user-facing Skills."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path
import re
from typing import Any

CONTRACT_FILES = {
    "mediasense.dataset.open": "dataset-open.tool.json",
    "mediasense.precheck.run": "precheck-run.tool.json",
    "mediasense.precheck.read": "precheck-read.tool.json",
    "mediasense.plan.work": "plan-work.tool.json",
    "mediasense.apply.run": "apply-run.tool.json",
    "mediasense.apply.read": "apply-read.tool.json",
}


def resource_root() -> Path:
    return Path(str(files("mediasense").joinpath("_resources")))


def contract_path(name: str) -> Path:
    try:
        filename = CONTRACT_FILES[name]
    except KeyError as error:
        raise KeyError(f"unknown MediaSense Tool contract: {name}") from error
    path = resource_root() / "contracts" / filename
    if not path.is_file():
        raise FileNotFoundError(f"installed Tool contract is missing: {path}")
    return path


def schema_path(filename: str) -> Path:
    path = resource_root() / "contracts" / filename
    if not path.is_file():
        raise FileNotFoundError(f"installed schema is missing: {path}")
    return path


def load_contract(name: str) -> dict[str, Any]:
    value = json.loads(contract_path(name).read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("name") != name:
        raise ValueError(f"installed Tool contract is invalid: {name}")
    return value


def contract_digest(name: str) -> str:
    return "sha256:" + hashlib.sha256(contract_path(name).read_bytes()).hexdigest()


def skill_roots() -> tuple[Path, ...]:
    root = resource_root() / "skills"
    paths = tuple(
        root / name
        for name in (
            "mediasense",
            "mediasense-precheck",
            "mediasense-plan",
            "mediasense-apply",
        )
    )
    missing = tuple(path for path in paths if not (path / "SKILL.md").is_file())
    if missing:
        raise FileNotFoundError(
            "installed Skill resources are missing: "
            + ", ".join(str(path) for path in missing)
        )
    return paths


def validate_skill_release_line(application_version: str) -> None:
    """Require every packaged Skill to name only this application's minor line."""

    try:
        major, minor, _patch = application_version.split(".", maxsplit=2)
    except ValueError as error:
        raise ValueError(
            "application version must be semantic major.minor.patch"
        ) from error
    expected = f"{major}.{minor}.x"
    pattern = re.compile(r"\b\d+\.\d+\.x\b")
    for root in skill_roots():
        declared = set(pattern.findall((root / "SKILL.md").read_text(encoding="utf-8")))
        if declared != {expected}:
            raise ValueError(
                f"installed Skill {root.name} declares {sorted(declared)}; "
                f"expected only {expected}"
            )
