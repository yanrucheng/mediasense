"""Explicit, non-overwriting installation of packaged MediaSense Skills."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from .resources import skill_roots


class SkillInstallError(RuntimeError):
    """A Skill target conflicts with the packaged release copy."""


def install_skills(target_root: Path) -> dict[str, object]:
    target = Path(target_root).expanduser().absolute()
    target.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    unchanged: list[str] = []
    for source in skill_roots():
        destination = target / source.name
        destination_file = destination / "SKILL.md"
        if destination.exists():
            if (
                destination.is_dir()
                and destination_file.is_file()
                and _directories_equal(source, destination)
            ):
                unchanged.append(source.name)
                continue
            raise SkillInstallError(
                f"Refusing to overwrite existing Skill target: {destination}"
            )
        staging = target / f".{source.name}.installing-{uuid4().hex}"
        try:
            shutil.copytree(source, staging)
            staging.replace(destination)
        except OSError:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        installed.append(source.name)
    return {
        "outcome": "ok",
        "target": str(target),
        "installed": installed,
        "unchanged": unchanged,
    }


def _directories_equal(source: Path, destination: Path) -> bool:
    source_files = {
        path.relative_to(source): path for path in source.rglob("*") if path.is_file()
    }
    destination_files = {
        path.relative_to(destination): path
        for path in destination.rglob("*")
        if path.is_file()
    }
    if set(source_files) != set(destination_files):
        return False
    return all(
        source_files[relative].read_bytes() == destination_files[relative].read_bytes()
        for relative in source_files
    )
