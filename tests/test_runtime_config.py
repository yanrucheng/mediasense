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


def test_embedding_is_explicit_pinned_and_can_be_disabled_per_dataset(tmp_path):
    user = tmp_path / "user.toml"
    user.write_text(
        '[embedding]\nmodel_id="OFA-Sys/chinese-clip-vit-huge-patch14"\n'
        'revision="503e16b560aff94c1922f13a86a7693d36957a4f"\ndimensions=1024\n'
    )
    config = load_runtime_config(user_config=user)
    assert config.embedding["device"] == "cpu"
    assert config.public_value()["local_embedding"]["execution"] == "not_checked"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "config.toml").write_text("[embedding]\nenabled=false\n")
    assert (
        load_runtime_config(user_config=user, dataset_workspace=workspace).embedding
        is None
    )
    user.write_text(
        user.read_text().replace("503e16b560aff94c1922f13a86a7693d36957a4f", "main")
    )
    with pytest.raises(ConfigurationError, match="immutable"):
        load_runtime_config(user_config=user)


@pytest.mark.parametrize(
    "field", ['enabled="yes"', "dimensions=true", 'device="auto"', "batch_size=0"]
)
def test_embedding_rejects_ambiguous_configuration(tmp_path, field):
    config = tmp_path / "config.toml"
    values = dict(
        model_id='"OFA-Sys/chinese-clip-vit-huge-patch14"',
        revision='"' + "a" * 40 + '"',
        dimensions="1024",
    )
    key, value = field.split("=", 1)
    values[key] = value
    config.write_text(
        "[embedding]\n" + "\n".join(f"{key}={value}" for key, value in values.items())
    )
    with pytest.raises(ConfigurationError):
        load_runtime_config(user_config=config)
