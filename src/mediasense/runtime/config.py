"""Small, inspectable runtime configuration with explicit provenance."""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigurationError(RuntimeError):
    """Configuration is invalid or requests an unsupported effect policy."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    offline: bool
    amap_api_key_env: str
    google_maps_api_key_env: str
    sources: tuple[Path, ...]

    def public_value(self) -> dict[str, object]:
        return {
            "offline": self.offline,
            "sources": [str(path) for path in self.sources],
            "credentials": {
                "amap": "configured"
                if os.environ.get(self.amap_api_key_env)
                else "not_configured",
                "google_maps": "configured"
                if os.environ.get(self.google_maps_api_key_env)
                else "not_configured",
            },
        }


def default_user_config_path(
    *, platform_name: str | None = None, home: Path | None = None
) -> Path:
    override = os.environ.get("MEDIASENSE_CONFIG_HOME")
    if override:
        return Path(override).expanduser().absolute() / "config.toml"
    platform_value = platform_name or sys.platform
    home_value = Path(home or Path.home())
    if platform_value == "darwin":
        return (
            home_value
            / "Library"
            / "Application Support"
            / "MediaSense"
            / "config.toml"
        )
    if platform_value == "win32":
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else home_value / "MediaSense"
        return base / "config.toml"
    config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(config_home).expanduser() if config_home else home_value / ".config"
    return base / "mediasense" / "config.toml"


def load_runtime_config(
    *,
    dataset_workspace: Path | None = None,
    user_config: Path | None = None,
    offline: bool | None = None,
) -> RuntimeConfig:
    values: dict[str, Any] = {
        "offline": True,
        "amap_api_key_env": "AMAP_API_KEY",
        "google_maps_api_key_env": "GOOGLE_MAPS_API_KEY",
    }
    sources: list[Path] = []
    candidates = [Path(user_config or default_user_config_path())]
    if dataset_workspace is not None:
        candidates.append(Path(dataset_workspace) / "config.toml")
    for path in candidates:
        if not path.exists():
            continue
        parsed = _read_config(path)
        values.update(parsed)
        sources.append(path)
    if offline is not None:
        values["offline"] = offline
    return RuntimeConfig(
        offline=bool(values["offline"]),
        amap_api_key_env=str(values["amap_api_key_env"]),
        google_maps_api_key_env=str(values["google_maps_api_key_env"]),
        sources=tuple(sources),
    )


def _read_config(path: Path) -> dict[str, object]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(
            f"Cannot read configuration {path}: {error}"
        ) from error
    if set(value) - {"runtime", "providers"}:
        raise ConfigurationError(f"Unknown configuration section in {path}")
    runtime = value.get("runtime", {})
    providers = value.get("providers", {})
    if not isinstance(runtime, dict) or not isinstance(providers, dict):
        raise ConfigurationError(f"Configuration sections must be tables in {path}")
    if set(runtime) - {"offline"}:
        raise ConfigurationError(f"Unknown runtime configuration key in {path}")
    if set(providers) - {"amap_api_key_env", "google_maps_api_key_env"}:
        raise ConfigurationError(f"Unknown provider configuration key in {path}")
    result: dict[str, object] = {}
    if "offline" in runtime:
        if not isinstance(runtime["offline"], bool):
            raise ConfigurationError(f"runtime.offline must be boolean in {path}")
        result["offline"] = runtime["offline"]
    for key in ("amap_api_key_env", "google_maps_api_key_env"):
        if key in providers:
            item = providers[key]
            if not isinstance(item, str) or not item.strip():
                raise ConfigurationError(f"providers.{key} must be non-empty in {path}")
            result[key] = item.strip()
    return result
