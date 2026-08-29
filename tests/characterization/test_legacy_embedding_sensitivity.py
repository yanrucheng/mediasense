"""Local embedding and sensitivity behavior characterized from AI Album c90."""

from __future__ import annotations

import pytest

from mediasense.precheck.embedding import EmbeddingProfile, cosine_similarity
from mediasense.precheck.sensitivity import (
    Detection,
    SensitivityProfile,
    SensitivityThreshold,
    classify_detections,
)


pytestmark = pytest.mark.characterization


def test_chinese_clip_vectors_keep_the_observed_shape_and_cosine_semantics() -> None:
    profile = EmbeddingProfile(
        name="legacy-chinese-clip-image",
        dimensions=1024,
        normalization="model_native",
    )

    assert profile.dimensions == 1024
    assert profile.dtype == "float32-le"
    assert cosine_similarity((1.0, 0.0), (1.0, 0.0)) == pytest.approx(1.0)
    assert cosine_similarity((1.0, 0.0), (0.0, 1.0)) == pytest.approx(0.0)


def test_nudenet_duplicate_labels_use_the_max_score_and_two_thresholds() -> None:
    profile = SensitivityProfile(
        name="legacy-nudenet-thresholds",
        thresholds=(
            SensitivityThreshold("FEMALE_BREAST_EXPOSED", 0.5),
            SensitivityThreshold("FEMALE_GENITALIA_EXPOSED", 0.4),
            SensitivityThreshold("FACE_FEMALE", 99.0),
        ),
        mild_ratio=1 / 3,
    )

    classified = classify_detections(
        (
            Detection("FEMALE_BREAST_EXPOSED", 0.2),
            Detection("FEMALE_BREAST_EXPOSED", 0.8),
            Detection("FEMALE_GENITALIA_EXPOSED", 0.3),
            Detection("FACE_FEMALE", 0.99),
        ),
        profile,
    )

    by_label = {item.label: item for item in classified}
    assert by_label["FEMALE_BREAST_EXPOSED"].score == 0.8
    assert by_label["FEMALE_BREAST_EXPOSED"].sensitive is True
    assert by_label["FEMALE_GENITALIA_EXPOSED"].sensitive is False
    assert by_label["FEMALE_GENITALIA_EXPOSED"].mild_sensitive is True
    assert by_label["FACE_FEMALE"].sensitive is False
    assert by_label["FACE_FEMALE"].mild_sensitive is False


def test_binary_nsfw_threshold_is_inclusive_and_unknown_labels_fail() -> None:
    profile = SensitivityProfile(
        name="legacy-falconsai-nsfw-thresholds",
        thresholds=(
            SensitivityThreshold("nsfw", 0.02),
            SensitivityThreshold("normal", 99.0),
        ),
        mild_ratio=1 / 3,
    )

    classified = classify_detections(
        (Detection("nsfw", 0.02), Detection("normal", 0.98)), profile
    )
    by_label = {item.label: item for item in classified}
    assert by_label["nsfw"].sensitive is True
    assert by_label["normal"].sensitive is False

    with pytest.raises(ValueError, match="unknown sensitivity label"):
        classify_detections((Detection("unexpected", 0.9),), profile)
