"""Fixed semantic identity vectors and operational exclusion boundaries."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from mediasense.precheck._preparation import (
    preparation_configuration_identity,
    preparation_configuration_value,
)

VECTOR = json.loads(
    (
        Path(__file__).parents[1]
        / "docs/spec/contract/precheck-run/composition.mock.json"
    ).read_text()
)["configuration_vectors"][0]


def test_fixed_projection_and_utf8_hash_vector():
    value = preparation_configuration_value(VECTOR["config"], VECTOR["recipes"])
    assert value == VECTOR["value"]
    assert preparation_configuration_identity(value) == VECTOR["identity"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("metadata_batch_size", 1024),
        ("model_batch_size", 32),
        ("ffmpeg_threads", 8),
        ("model_path", "/other/copied/model"),
        ("source_storage", "remote"),
        ("dataset_name", "renamed"),
        ("artifact_path", "/other/cache"),
        ("resource_budget", {"memory": 1234}),
        ("credentials", {"secret": "never-projected"}),
    ],
)
def test_pure_scheduling_and_locations_do_not_change_identity(key, value):
    config = {**VECTOR["config"], key: value}
    assert (
        preparation_configuration_identity(
            preparation_configuration_value(config, VECTOR["recipes"])
        )
        == VECTOR["identity"]
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("metadata", False),
        ("metadata_profile", {"timezone": "Asia/Shanghai"}),
        ("gpx", False),
        ("image_renditions", False),
        ("video_frame_limit", 4),
        ("bundles", False),
        ("compression_target", 201),
        ("directed_evidence_paths", ["input/b.jpg"]),
        ("embedding_encoder_identity", "synthetic-encoder@sha256:two"),
        ("reverse_geocode_profile", {"max_attempts": 1}),
    ],
)
def test_semantic_dependency_changes_identity(key, value):
    config = {**VECTOR["config"], key: value}
    assert (
        preparation_configuration_identity(
            preparation_configuration_value(config, VECTOR["recipes"])
        )
        != VECTOR["identity"]
    )


def test_recipe_changes_and_missing_model_declaration_are_explicit():
    recipes = {**VECTOR["recipes"], "compression_recipe": "changed-output-v2"}
    assert (
        preparation_configuration_identity(
            preparation_configuration_value(VECTOR["config"], recipes)
        )
        != VECTOR["identity"]
    )
    config = {**VECTOR["config"], "embedding_encoder_identity": None}
    with pytest.raises(ValueError, match="immutable encoder"):
        preparation_configuration_value(config, VECTOR["recipes"])
    config = deepcopy(VECTOR["config"])
    config["reverse_geocode_profile"]["max_places"] = float("nan")
    with pytest.raises(ValueError):
        preparation_configuration_value(config, VECTOR["recipes"])
