"""Explicit installation and transactional upgrade of packaged Skills."""

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


def upgrade_skills(target_root: Path) -> dict[str, object]:
    """Replace only packaged MediaSense Skills as one recoverable set."""

    target = Path(target_root).expanduser().absolute()
    if not target.is_dir():
        raise SkillInstallError(
            f"Skill upgrade target must be an existing directory: {target}"
        )
    sources = skill_roots()
    installed: list[str] = []
    upgraded: list[str] = []
    unchanged: list[str] = []
    for source in sources:
        destination = target / source.name
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise SkillInstallError(
                    f"Refusing non-directory Skill target: {destination}"
                )
            if _directories_equal(source, destination):
                unchanged.append(source.name)
            else:
                upgraded.append(source.name)
        else:
            installed.append(source.name)

    changed = [*installed, *upgraded]
    if not changed:
        return {
            "outcome": "ok",
            "target": str(target),
            "installed": [],
            "upgraded": [],
            "unchanged": unchanged,
        }

    operation = target / f".mediasense-skills-upgrade-{uuid4().hex}"
    staged = operation / "staged"
    backup = operation / "backup"
    touched: list[str] = []
    try:
        staged.mkdir(parents=True)
        backup.mkdir()
        for source in sources:
            if source.name in changed:
                shutil.copytree(source, staged / source.name)
        for name in changed:
            destination = target / name
            if destination.exists():
                _replace(destination, backup / name)
            _replace(staged / name, destination)
            touched.append(name)
    except BaseException:
        for name in reversed(touched):
            destination = target / name
            if destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
            elif destination.exists() or destination.is_symlink():
                destination.unlink()
            saved = backup / name
            if saved.exists():
                _replace(saved, destination)
        for name in changed:
            saved = backup / name
            destination = target / name
            if saved.exists() and not destination.exists():
                _replace(saved, destination)
        shutil.rmtree(operation, ignore_errors=True)
        raise
    shutil.rmtree(operation)
    return {
        "outcome": "ok",
        "target": str(target),
        "installed": installed,
        "upgraded": upgraded,
        "unchanged": unchanged,
    }


def _replace(source: Path, destination: Path) -> None:
    source.replace(destination)


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
