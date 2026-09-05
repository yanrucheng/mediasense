from __future__ import annotations

from pathlib import Path

import pytest

from mediasense.runtime.config import (
    ConfigurationError,
    default_user_config_path,
    load_runtime_config,
)


def test_dataset_config_overrides_user_config_and_reports_sources(
    tmp_path: Path,
) -> None:
    user = tmp_path / "user.toml"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    dataset = workspace / "config.toml"
    user.write_text(
        '[providers]\namap_api_key_env = "USER_AMAP"\n',
        encoding="utf-8",
    )
    dataset.write_text(
        '[providers]\namap_api_key_env = "DATASET_AMAP"\n',
        encoding="utf-8",
    )

    config = load_runtime_config(dataset_workspace=workspace, user_config=user)

    assert config.amap_api_key_env == "DATASET_AMAP"
    assert config.sources == (user, dataset)


def test_legacy_offline_mode_is_rejected(tmp_path: Path) -> None:
    user = tmp_path / "user.toml"
    user.write_text("[runtime]\noffline = false\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Unknown configuration section"):
        load_runtime_config(user_config=user)


def test_unknown_configuration_is_rejected(tmp_path: Path) -> None:
    user = tmp_path / "user.toml"
    user.write_text("[runtime]\nmagic = true\n", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="Unknown configuration section"):
        load_runtime_config(user_config=user)


def test_config_home_can_be_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(tmp_path / "config"))

    assert default_user_config_path() == tmp_path / "config" / "config.toml"
