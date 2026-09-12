"""Small, inspectable runtime configuration with explicit provenance."""

from __future__ import annotations

import os
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mediasense.manufacturers import (
    KnowledgeError,
    KnowledgeSnapshot,
    builtin_knowledge,
    load_knowledge,
)


class ConfigurationError(RuntimeError):
    """Configuration is invalid or requests an unsupported effect policy."""


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    amap_api_key_env: str
    google_maps_api_key_env: str
    sources: tuple[Path, ...]
    embedding: dict[str, Any] | None = None
    sensitivity: dict[str, Any] | None = None
    geo_network: dict[str, Any] | None = None
    metadata: dict[str, str] = field(
        default_factory=lambda: {
            "assumed_timezone": "Asia/Shanghai",
            "output_timezone": "Asia/Shanghai",
        }
    )
    manufacturer_knowledge: KnowledgeSnapshot | None = field(
        default_factory=builtin_knowledge
    )
    manufacturer_knowledge_error: str | None = None
    user_config_path: Path | None = None

    def metadata_profile(self):
        from mediasense.precheck.metadata import MetadataProfile

        if self.manufacturer_knowledge is None:
            raise ConfigurationError(
                self.manufacturer_knowledge_error
                or "Manufacturer knowledge is unavailable"
            )
        return MetadataProfile(
            timezone=self.metadata["output_timezone"],
            assumed_timezone=self.metadata["assumed_timezone"],
            knowledge=self.manufacturer_knowledge,
        )

    def public_value(self) -> dict[str, object]:
        from mediasense.geo import UrllibJsonTransport

        network = self.geo_network or {}
        transport = UrllibJsonTransport(
            proxy_url=network.get("proxy_url"),
            ca_bundle=network.get("ca_bundle"),
            configured=True,
        )
        return {
            "metadata": {
                **self.metadata,
                "manufacturer_knowledge": (
                    self.manufacturer_knowledge.summary()
                    if self.manufacturer_knowledge is not None
                    else {
                        "error": {
                            "code": "configuration_invalid",
                            "message": self.manufacturer_knowledge_error
                            or "Manufacturer knowledge is unavailable",
                        },
                        "execution": "not_checked",
                    }
                ),
            },
            "geo_network": transport.network_profile,
            "sources": [str(path) for path in self.sources],
            "local_embedding": {
                "state": "configured" if self.embedding else "disabled",
                "reason": "explicit_local_profile"
                if self.embedding
                else "no_local_profile_configured",
                "profile": self.embedding,
                "execution": "not_checked",
                "model_downloads": False,
            },
            "providers": {
                "amap": {
                    "credential": "configured"
                    if os.environ.get(self.amap_api_key_env)
                    else "not_configured",
                    "capability": "available"
                    if os.environ.get(self.amap_api_key_env)
                    else "unavailable",
                    "data_handling": "unknown",
                },
                "google_maps": {
                    "credential": "configured"
                    if os.environ.get(self.google_maps_api_key_env)
                    else "not_configured",
                    "capability": "available"
                    if os.environ.get(self.google_maps_api_key_env)
                    else "unavailable",
                    "data_handling": "unknown",
                },
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
    load_manufacturers: bool = True,
    allow_invalid_manufacturers: bool = False,
) -> RuntimeConfig:
    values: dict[str, Any] = {
        "amap_api_key_env": "AMAP_API_KEY",
        "google_maps_api_key_env": "GOOGLE_MAPS_API_KEY",
        "metadata": {
            "assumed_timezone": "Asia/Shanghai",
            "output_timezone": "Asia/Shanghai",
        },
    }
    sources: list[Path] = []
    user_path = Path(user_config or default_user_config_path())
    candidates = [user_path]
    if dataset_workspace is not None:
        candidates.append(Path(dataset_workspace) / "config.toml")
    for path in candidates:
        if not path.exists():
            continue
        parsed = _read_config(path)
        if "metadata" in parsed:
            values["metadata"].update(parsed.pop("metadata"))
        values.update(parsed)
        sources.append(path)
    knowledge_error = None
    try:
        knowledge = (
            load_knowledge(user_path.parent)
            if load_manufacturers
            else KnowledgeSnapshot.empty()
        )
    except KnowledgeError as error:
        if not allow_invalid_manufacturers:
            raise ConfigurationError(str(error)) from error
        knowledge = None
        knowledge_error = str(error)
    return RuntimeConfig(
        amap_api_key_env=str(values["amap_api_key_env"]),
        google_maps_api_key_env=str(values["google_maps_api_key_env"]),
        sources=tuple(sources),
        embedding=values.get("embedding"),
        sensitivity=values.get("sensitivity"),
        geo_network=values.get("geo_network"),
        metadata=values["metadata"],
        manufacturer_knowledge=knowledge,
        manufacturer_knowledge_error=knowledge_error,
        user_config_path=user_path,
    )


def _read_config(path: Path) -> dict[str, object]:
    try:
        value = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigurationError(
            f"Cannot read configuration {path}: {error}"
        ) from error
    if set(value) - {
        "providers",
        "embedding",
        "sensitivity",
        "geo_network",
        "metadata",
    }:
        raise ConfigurationError(f"Unknown configuration section in {path}")
    providers = value.get("providers", {})
    if not isinstance(providers, dict):
        raise ConfigurationError(f"Configuration sections must be tables in {path}")
    if set(providers) - {"amap_api_key_env", "google_maps_api_key_env"}:
        raise ConfigurationError(f"Unknown provider configuration key in {path}")
    result: dict[str, object] = {}
    if "metadata" in value:
        metadata = value["metadata"]
        if not isinstance(metadata, dict) or set(metadata) - {
            "assumed_timezone",
            "output_timezone",
        }:
            raise ConfigurationError(f"Invalid metadata configuration in {path}")
        for key, zone in metadata.items():
            try:
                if not isinstance(zone, str) or not zone:
                    raise ValueError("timezone must be a non-empty IANA name")
                ZoneInfo(zone)
            except (ValueError, ZoneInfoNotFoundError) as error:
                raise ConfigurationError(
                    f"Invalid metadata.{key} timezone in {path}: {zone}"
                ) from error
        result["metadata"] = metadata
    if "geo_network" in value:
        from math import isfinite
        from urllib.parse import urlsplit

        network = value["geo_network"]
        if not isinstance(network, dict) or set(network) - {
            "proxy_url",
            "ca_bundle",
            "google_timeout_seconds",
            "amap_timeout_seconds",
            "minimum_interval_seconds",
        }:
            raise ConfigurationError("Invalid geo_network configuration")
        for key in (
            "google_timeout_seconds",
            "amap_timeout_seconds",
            "minimum_interval_seconds",
        ):
            if key in network and (
                type(network[key]) not in {int, float}
                or not isfinite(network[key])
                or network[key] <= 0
            ):
                raise ConfigurationError(
                    f"geo_network.{key} must be finite and positive"
                )
        if "proxy_url" in network:
            proxy = network["proxy_url"]
            if (
                not isinstance(proxy, str)
                or urlsplit(proxy).scheme not in {"http", "https"}
                or not urlsplit(proxy).hostname
            ):
                raise ConfigurationError(
                    "geo_network.proxy_url requires an HTTP/HTTPS proxy URL"
                )
        if "ca_bundle" in network:
            bundle = network["ca_bundle"]
            if not isinstance(bundle, str) or not Path(bundle).expanduser().is_file():
                raise ConfigurationError(
                    "geo_network.ca_bundle must name an existing CA file"
                )
            network["ca_bundle"] = str(Path(bundle).expanduser().absolute())
        result["geo_network"] = network
    if "embedding" in value:
        embedding = value["embedding"]
        if not isinstance(embedding, dict):
            raise ConfigurationError("embedding must be a table")
        if set(embedding) - {
            "enabled",
            "model_id",
            "revision",
            "dimensions",
            "device",
            "batch_size",
            "image_size",
            "model_path",
        }:
            raise ConfigurationError("Unknown embedding configuration key")
        # Preserve legacy complete ChineseCLIP tables that omitted enabled.
        # New shorthand needs an explicit opt-in; an empty table stays off.
        enabled = embedding.get("enabled", "model_id" in embedding)
        if not isinstance(enabled, bool):
            raise ConfigurationError("embedding.enabled must be a boolean")
        if not enabled:
            result["embedding"] = None
        elif embedding.get("model_id", "timm/vit_base_patch16_dinov3.lvd1689m") == "timm/vit_base_patch16_dinov3.lvd1689m":
            from .embedding import dinov3_profile

            result["embedding"] = dinov3_profile(embedding)
        else:
            if "image_size" in embedding or "model_path" in embedding:
                raise ConfigurationError("image_size and model_path belong to the DINOv3 profile")
            model_id = embedding.get("model_id")
            revision = embedding.get("revision")
            dimensions = embedding.get("dimensions")
            device = embedding.get("device", "cpu")
            batch_size = embedding.get("batch_size", 4)
            if not isinstance(model_id, str) or not re.fullmatch(
                r"[\w.-]+/[\w.-]+", model_id
            ):
                raise ConfigurationError(
                    "embedding.model_id must name a Hugging Face model repository"
                )
            if not isinstance(revision, str) or not re.fullmatch(
                r"[0-9a-f]{40}", revision
            ):
                raise ConfigurationError(
                    "embedding.revision must be an immutable 40-character commit"
                )
            if type(dimensions) is not int or dimensions < 1:
                raise ConfigurationError("embedding.dimensions must be positive")
            if device not in {"cpu", "mps", "cuda"}:
                raise ConfigurationError("embedding.device must be cpu, mps, or cuda")
            if type(batch_size) is not int or batch_size < 1:
                raise ConfigurationError("embedding.batch_size must be positive")
            result["embedding"] = dict(
                model_id=model_id,
                revision=revision,
                dimensions=dimensions,
                device=device,
                batch_size=batch_size,
            )
    if "sensitivity" in value:
        sensitivity = value["sensitivity"]
        if not isinstance(sensitivity, dict) or set(sensitivity) - {
            "enabled",
            "device",
            "nsfw_model_id",
            "nsfw_revision",
        }:
            raise ConfigurationError("Invalid sensitivity configuration table")
        enabled = sensitivity.get("enabled", False)
        device = sensitivity.get("device", "cpu")
        model_id = sensitivity.get("nsfw_model_id", "Falconsai/nsfw_image_detection")
        revision = sensitivity.get("nsfw_revision")
        if type(enabled) is not bool:
            raise ConfigurationError("sensitivity.enabled must be a boolean")
        if not isinstance(device, str) or device not in {"cpu", "mps", "cuda"}:
            raise ConfigurationError("sensitivity.device must be cpu, mps, or cuda")
        if not isinstance(model_id, str) or not re.fullmatch(
            r"[\w.-]+/[\w.-]+", model_id
        ):
            raise ConfigurationError(
                "sensitivity.nsfw_model_id must name a model repository"
            )
        if (enabled or revision is not None) and (
            not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)
        ):
            raise ConfigurationError(
                "sensitivity.nsfw_revision must be an immutable 40-character commit"
            )
        result["sensitivity"] = (
            dict(device=device, nsfw_model_id=model_id, nsfw_revision=revision)
            if enabled
            else None
        )
    for key in ("amap_api_key_env", "google_maps_api_key_env"):
        if key in providers:
            item = providers[key]
            if not isinstance(item, str) or not item.strip():
                raise ConfigurationError(f"providers.{key} must be non-empty in {path}")
            result[key] = item.strip()
    return result
