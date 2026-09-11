"""Read-only installation and capability diagnostics."""

from __future__ import annotations

import os
import shutil
import stat
import sys
from dataclasses import dataclass
from importlib.util import find_spec
from pathlib import Path

from .config import ConfigurationError, default_user_config_path, load_runtime_config
from .dataset import default_local_dataset_root
from .resources import (
    CONTRACT_FILES,
    load_contract,
    skill_roots,
    validate_skill_release_line,
)
from .versioning import application_version


@dataclass(frozen=True, slots=True)
class Diagnostic:
    name: str
    status: str
    message: str
    required: bool

    def to_value(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "required": self.required,
        }


def diagnose() -> dict[str, object]:
    checks: list[Diagnostic] = []
    sensitivity_configuration = None
    checks.append(
        Diagnostic(
            "python",
            "ok" if sys.version_info >= (3, 11) else "error",
            f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            True,
        )
    )
    checks.append(
        Diagnostic(
            "platform",
            "ok" if sys.platform == "darwin" else "warning",
            (
                "macOS is the initially certified platform."
                if sys.platform == "darwin"
                else f"{sys.platform} is not yet product-certified."
            ),
            False,
        )
    )
    try:
        for name in CONTRACT_FILES:
            load_contract(name)
        skill_roots()
        validate_skill_release_line(application_version())
    except (OSError, ValueError) as error:
        checks.append(Diagnostic("resources", "error", str(error), True))
    else:
        checks.append(
            Diagnostic(
                "resources",
                "ok",
                (
                    f"{len(CONTRACT_FILES)} Tool contracts and "
                    f"{len(skill_roots())} Skills are available."
                ),
                True,
            )
        )
    try:
        config = load_runtime_config()
    except ConfigurationError as error:
        checks.append(Diagnostic("configuration", "error", str(error), True))
        config_sources: list[str] = []
    else:
        config_sources = [str(path) for path in config.sources]
        sensitivity_configuration = config.sensitivity
        configured_provider = bool(
            os.environ.get(config.amap_api_key_env)
            or os.environ.get(config.google_maps_api_key_env)
        )
        if configured_provider:
            configuration_status = "ok"
            configuration_message = (
                "A map provider is available; each effect still requires "
                "matching authorization."
            )
        else:
            configuration_status = "warning"
            configuration_message = (
                "No map-provider credential is configured; Geo acquisition is "
                "unavailable when a frozen coordinate batch is non-empty."
            )
        checks.append(
            Diagnostic(
                "configuration",
                configuration_status,
                configuration_message,
                True,
            )
        )
        for path in config.sources:
            try:
                broad = bool(stat.S_IMODE(path.stat().st_mode) & 0o077)
            except OSError:
                broad = True
            if broad:
                checks.append(
                    Diagnostic(
                        "configuration_permissions",
                        "warning",
                        f"Configuration permissions are broader than owner-only: {path}",
                        False,
                    )
                )
    local_root = default_local_dataset_root()
    parent = _nearest_existing_parent(local_root)
    checks.append(
        Diagnostic(
            "local_dataset_root",
            "ok" if os.access(parent, os.W_OK) else "error",
            f"Default local Dataset root: {local_root}",
            True,
        )
    )
    for executable, capability in (
        ("uv", "repeatable installation and upgrade"),
        ("exiftool", "photo metadata extraction"),
        ("ffprobe", "video inspection"),
    ):
        resolved = shutil.which(executable)
        checks.append(
            Diagnostic(
                executable,
                "ok" if resolved else "warning",
                f"Available at {resolved}."
                if resolved
                else f"Not installed; {capability} is unavailable.",
                False,
            )
        )
    checks.append(
        Diagnostic(
            "video_decoder", "ok" if find_spec("av") is not None else "warning",
            "Packaged PyAV decoder is installed; video execution verifies its local FFmpeg libraries."
            if find_spec("av") is not None else "PyAV is unavailable; repair this Host installation for video preparation.",
            False,
        )
    )
    local_models = all(
        find_spec(name) is not None for name in ("torch", "transformers", "nudenet")
    )
    embedding_dependencies = all(
        find_spec(name) is not None for name in ("torch", "transformers")
    )
    checks.append(
        Diagnostic(
            "embedding",
            "ok" if embedding_dependencies else "warning",
            "Encoder dependencies available; pinned model/device availability is checked locally at execution."
            if embedding_dependencies
            else "Embedding unavailable: install the embeddings extra in this Host environment.",
            False,
        )
    )
    checks.append(
        Diagnostic(
            "local_models",
            "ok" if local_models else "warning",
            (
                "Optional local-model dependencies are available."
                if local_models
                else "Optional local-model dependencies are not installed."
            ),
            False,
        )
    )
    from mediasense.precheck.sensitivity import (
        NudeNetDetector,
        SensitivityBackendUnavailable,
    )

    try:
        NudeNetDetector._weights()
        weights_state = "available"
    except SensitivityBackendUnavailable:
        weights_state = "unavailable"
    checks.append(
        Diagnostic(
            "sensitivity_weights",
            "ok" if weights_state == "available" else "warning",
            "Bundled NudeNet weights: "
            + weights_state
            + "; NSFW model/processor are loaded only from the pinned local cache at execution.",
            False,
        )
    )
    return {
        "application_version": application_version(),
        "status": ("error" if any(item.status == "error" for item in checks) else "ok"),
        "checks": [item.to_value() for item in checks],
        "configuration_sources": config_sources,
        "local_sensitivity": {
            "state": "configured" if sensitivity_configuration else "disabled",
            "profile": sensitivity_configuration,
            "execution": "not_checked",
            "locality": "local",
            "model_downloads": False,
            "nudenet_weights": weights_state,
        },
        "user_config": str(default_user_config_path()),
    }


def _nearest_existing_parent(path: Path) -> Path:
    current = path.expanduser().absolute()
    while not current.exists() and current.parent != current:
        current = current.parent
    return current
