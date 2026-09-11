from pathlib import Path
import hashlib

import pytest

from mediasense.precheck import dinov3
from mediasense.precheck.embedding import ChineseCLIPEncoder, EmbeddingBackendUnavailable
from mediasense.runtime.config import ConfigurationError, load_runtime_config
from mediasense.runtime.embedding import make_encoder


def config(tmp_path, body):
    path = tmp_path / "config.toml"
    path.write_text(body)
    return load_runtime_config(user_config=path)


def test_opt_in_selects_the_accepted_recipe_and_real_factory(tmp_path):
    for body in ("", "[embedding]\n", "[embedding]\nenabled=false\n"):
        assert config(tmp_path, body).embedding is None
    selected = config(tmp_path, "[embedding]\nenabled=true\n")
    assert selected.embedding["model_id"] == dinov3.MODEL_ID
    assert selected.embedding["revision"] == dinov3.REVISION
    assert selected.embedding["image_size"] == 384
    assert selected.embedding["dimensions"] == 768
    assert selected.embedding["batch_size"] == 1
    assert isinstance(make_encoder(selected.embedding), dinov3.DinoV3CoreMLEncoder)
    assert selected.public_value()["local_embedding"]["execution"] == "not_checked"


def test_existing_chineseclip_profile_and_dataset_override_are_preserved(tmp_path):
    old = config(tmp_path, '[embedding]\nmodel_id="OFA-Sys/chinese-clip-vit-huge-patch14"\nrevision="' + "a" * 40 + '"\ndimensions=1024\n')
    assert isinstance(make_encoder(old.embedding), ChineseCLIPEncoder)
    workspace = tmp_path / "dataset"
    workspace.mkdir()
    (workspace / "config.toml").write_text("[embedding]\nenabled=false\n")
    assert load_runtime_config(user_config=tmp_path / "config.toml", dataset_workspace=workspace).embedding is None


@pytest.mark.parametrize("field", ['image_size=512', 'image_size=true', 'device="cpu"', 'device="auto"', 'batch_size=4', 'dimensions=1024', 'revision="main"', 'model_path="relative"'])
def test_unreleased_recipes_are_explicit_errors(tmp_path, field):
    with pytest.raises(ConfigurationError):
        config(tmp_path, "[embedding]\nenabled=true\n" + field)


def test_compiled_asset_integrity_is_checked_and_never_silently_replaced(tmp_path, monkeypatch):
    model = tmp_path / "vision.mlmodelc"
    model.mkdir()
    data = model / "weight.bin"
    data.write_bytes(b"correct")
    monkeypatch.setattr(dinov3, "recipe", lambda: {"files_sha256": {"vision.mlmodelc/weight.bin": hashlib.sha256(b"correct").hexdigest()}})
    dinov3.verify_model(tmp_path)
    data.write_bytes(b"wrong")
    with pytest.raises(EmbeddingBackendUnavailable, match="checksum"):
        dinov3.verify_model(tmp_path)
    data.unlink()
    with pytest.raises(EmbeddingBackendUnavailable, match="missing"):
        dinov3.verify_model(tmp_path)


def test_identity_binds_recipe_and_actual_runtime_but_not_asset_location(monkeypatch):
    monkeypatch.setattr(dinov3, "_package_version", lambda name: dinov3.recipe()["runtime_versions"][name])
    encoder = dinov3.DinoV3CoreMLEncoder(model_path=Path("/a"))
    original = encoder.identity
    assert original == dinov3.DinoV3CoreMLEncoder(model_path=Path("/b")).identity
    base = dinov3.recipe()
    for change in ({"preprocessing": {**base["preprocessing"], "image_size": 512}}, {"revision": "b" * 40}, {"compute_units": "CPU_ONLY"}, {"normalization": "model_native"}, {"graph_precision": "float16"}):
        monkeypatch.setattr(dinov3, "recipe", lambda change=change: {**base, **change})
        assert encoder.identity != original
    monkeypatch.setattr(dinov3, "recipe", lambda: base)
    monkeypatch.setattr(dinov3, "_package_version", lambda name: "unexpected")
    assert encoder.identity != original
    assert original != ChineseCLIPEncoder(revision=dinov3.REVISION).identity


@pytest.mark.parametrize("system,machine", [("Darwin", "x86_64"), ("Windows", "AMD64"), ("Linux", "aarch64")])
def test_unvalidated_platforms_refuse_loading_before_optional_imports(tmp_path, monkeypatch, system, machine):
    monkeypatch.setattr(dinov3.platform, "system", lambda: system)
    monkeypatch.setattr(dinov3.platform, "machine", lambda: machine)
    encoder = dinov3.DinoV3CoreMLEncoder(model_path=tmp_path)
    assert encoder.diagnose()["state"] == "unavailable"
    with pytest.raises(EmbeddingBackendUnavailable, match="no backend fallback"):
        encoder.check_available()


def test_missing_model_is_diagnostic_and_does_not_create_files(tmp_path):
    encoder = dinov3.DinoV3CoreMLEncoder(model_path=tmp_path / "missing")
    assert encoder.diagnose()["execution"] == "not_checked"
    with pytest.raises(EmbeddingBackendUnavailable):
        encoder.check_available()
    assert list(tmp_path.iterdir()) == []
