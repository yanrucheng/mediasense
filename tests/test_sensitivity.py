from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace

from jsonschema import Draft202012Validator
from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    Detection,
    HIGH_RESOLUTION_RENDITION_PROFILE,
    ImageRenditionProducer,
    NudeNetDetector,
    PrecheckReadTool,
    ResultSealError,
    ResultStore,
    SensitivityProducer,
    SensitivityProfile,
    SensitivityThreshold,
    TransformersNSFWDetector,
    WorkStatus,
    WorkStore,
)


SPEC_ROOT = (
    Path(__file__).parents[1] / "docs" / "spec" / "spec-260826-1546-precheck-read"
)


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


class FakeDetector:
    def __init__(self, *, identity: str = "fake-detector@sha256:one") -> None:
        self.identity = identity
        self.calls: list[Path] = []
        self.fail = False

    def detect(self, image_path: Path) -> tuple[Detection, ...]:
        self.calls.append(image_path)
        if self.fail:
            raise RuntimeError("detector unavailable")
        return (
            Detection("sensitive", 0.8),
            Detection("sensitive", 0.6),
            Detection("ordinary", 0.2),
        )


PROFILE = SensitivityProfile(
    name="test-sensitivity-v1",
    thresholds=(
        SensitivityThreshold("sensitive", 0.7),
        SensitivityThreshold("ordinary", 99.0),
    ),
)


def test_sensitivity_uses_rendition_provenance_and_reuses_across_runs(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    media = source / "photo.jpg"
    Image.new("RGB", (80, 60), "purple").save(media)
    source_before = media.read_bytes()
    detector = FakeDetector()

    first_run = _closed_run(database, source)
    first_rendition = ImageRenditionProducer(database).produce(
        first_run, Path("photo.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )
    first = SensitivityProducer(database, detector).produce(
        first_run,
        Path("photo.jpg"),
        first_rendition.work.work_id,
        profile=PROFILE,
    )

    assert first.work.status is WorkStatus.SUCCEEDED
    assert first.observations[0]["status"] == "available"
    value = first.observations[0]["value"]
    assert isinstance(value, dict)
    labels = {item["label"]: item for item in value["labels"]}
    assert labels["sensitive"]["score"] == 0.8
    assert labels["sensitive"]["sensitive"] is True
    assert media.read_bytes() == source_before

    second_run = _closed_run(database, source)
    reused_rendition = ImageRenditionProducer(database).produce(
        second_run, Path("photo.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )
    reused = SensitivityProducer(database, detector).produce(
        second_run,
        Path("photo.jpg"),
        reused_rendition.work.work_id,
        profile=PROFILE,
    )

    assert reused.work.work_id == first.work.work_id
    assert reused.reused is True
    assert len(detector.calls) == 1


def test_detector_or_threshold_change_has_narrow_semantic_invalidation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (40, 40), "yellow").save(source / "photo.jpg")
    run_id = _closed_run(database, source)
    rendition = ImageRenditionProducer(database).produce(
        run_id, Path("photo.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )
    first = SensitivityProducer(database, FakeDetector()).produce(
        run_id, Path("photo.jpg"), rendition.work.work_id, profile=PROFILE
    )
    changed_threshold = SensitivityProfile(
        name=PROFILE.name,
        thresholds=(
            SensitivityThreshold("sensitive", 0.9),
            SensitivityThreshold("ordinary", 99.0),
        ),
    )
    second = SensitivityProducer(database, FakeDetector()).produce(
        run_id,
        Path("photo.jpg"),
        rendition.work.work_id,
        profile=changed_threshold,
    )
    third = SensitivityProducer(
        database, FakeDetector(identity="fake-detector@sha256:two")
    ).produce(run_id, Path("photo.jpg"), rendition.work.work_id, profile=PROFILE)

    assert len({first.work.work_id, second.work.work_id, third.work.work_id}) == 3


def test_detector_failure_is_explicit_and_result_observations_remain_readable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (64, 32), "orange").save(source / "good.jpg")
    Image.new("RGB", (64, 32), "black").save(source / "failed.jpg")
    run_id = _closed_run(database, source)
    rendition_producer = ImageRenditionProducer(database)
    good_rendition = rendition_producer.produce(
        run_id, Path("good.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )
    failed_rendition = rendition_producer.produce(
        run_id, Path("failed.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )
    detector = FakeDetector()
    producer = SensitivityProducer(database, detector)
    good = producer.produce(
        run_id, Path("good.jpg"), good_rendition.work.work_id, profile=PROFILE
    )
    detector.fail = True
    failed = producer.produce(
        run_id,
        Path("failed.jpg"),
        failed_rendition.work.work_id,
        profile=PROFILE,
    )

    assert good.work.status is WorkStatus.SUCCEEDED
    assert failed.work.status is WorkStatus.TERMINAL_FAILURE
    assert failed.work.last_failure_code == "sensitivity_detection_failed"

    draft = ResultStore(database).build_minimal(
        run_id,
        [good_rendition.work.work_id, failed_rendition.work.work_id],
        sensitivity_work_ids=[good.work.work_id, failed.work.work_id],
    )
    sealed = ResultStore(database).seal(draft)
    reader = PrecheckReadTool(database)
    accounted = reader.read(
        {
            "action": "traverse",
            "direction": "outbound",
            "relation": "accounts_for",
            "result_ref": sealed.result_ref,
        }
    )
    source_views = [
        reader.read(
            {
                "action": "inspect",
                "result_ref": sealed.result_ref,
                "target": {"kind": "source_item", "ref": item["target"]},
            }
        )["target"]
        for item in accounted["items"]
    ]
    source_by_path = {item["locator"]["value"]: item["ref"] for item in source_views}
    good_response = reader.read(
        {
            "action": "inspect",
            "result_ref": sealed.result_ref,
            "target": {"kind": "source_item", "ref": source_by_path["good.jpg"]},
        }
    )
    failed_response = reader.read(
        {
            "action": "inspect",
            "result_ref": sealed.result_ref,
            "target": {
                "kind": "source_item",
                "ref": source_by_path["failed.jpg"],
            },
        }
    )
    schema = json.loads((SPEC_ROOT / "precheck-read.tool.json").read_text())
    Draft202012Validator(schema["outputSchema"]).validate(good_response)
    Draft202012Validator(schema["outputSchema"]).validate(failed_response)
    good_view = good_response["target"]
    failed_view = failed_response["target"]

    assert any(
        item["name"] == "content_sensitivity" and item["status"] == "available"
        for item in good_view["observations"]
    )
    assert any(
        item["name"] == "content_sensitivity" and item["status"] == "failed"
        for item in failed_view["observations"]
    )


def test_transformers_detector_requires_pinned_local_model_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_pipeline(task: str, **kwargs: object):
        calls.append((task, kwargs))

        def classify(_image: Image.Image) -> list[dict[str, object]]:
            return [
                {"label": "nsfw", "score": 0.1},
                {"label": "normal", "score": 0.9},
            ]

        return classify

    monkeypatch.setitem(
        sys.modules, "transformers", SimpleNamespace(pipeline=fake_pipeline)
    )
    image = tmp_path / "input.jpg"
    Image.new("RGB", (8, 8), "white").save(image)

    detections = TransformersNSFWDetector(revision="model-commit").detect(image)

    assert [item.label for item in detections] == ["nsfw", "normal"]
    assert calls == [
        (
            "image-classification",
            {
                "device": -1,
                "model": "Falconsai/nsfw_image_detection",
                "model_kwargs": {"local_files_only": True},
                "revision": "model-commit",
            },
        )
    ]


def test_seal_rechecks_inline_supporting_work_after_draft_build(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (16, 16), "blue").save(source / "photo.jpg")
    run_id = _closed_run(database, source)
    rendition = ImageRenditionProducer(database).produce(
        run_id, Path("photo.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )
    sensitivity = SensitivityProducer(database, FakeDetector()).produce(
        run_id, Path("photo.jpg"), rendition.work.work_id, profile=PROFILE
    )
    store = ResultStore(database)
    draft = store.build_minimal(
        run_id,
        [rendition.work.work_id],
        sensitivity_work_ids=[sensitivity.work.work_id],
    )

    WorkStore(database).invalidate_work(
        sensitivity.work.work_id, "changed before Result seal"
    )

    with pytest.raises(ResultSealError, match="supporting Work"):
        store.seal(draft)
    assert store.audit().available == ()
    assert store.audit().orphan_paths == ()


def test_nudenet_adapter_preserves_all_local_detections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FakeNudeDetector:
        def detect(self, image_path: str) -> list[dict[str, object]]:
            assert image_path.endswith("input.jpg")
            return [
                {"class": "FEMALE_BREAST_EXPOSED", "score": 0.8},
                {"class": "FACE_FEMALE", "score": 0.9},
            ]

    monkeypatch.setitem(
        sys.modules,
        "nudenet",
        SimpleNamespace(NudeDetector=FakeNudeDetector),
    )
    image = tmp_path / "input.jpg"
    Image.new("RGB", (8, 8), "white").save(image)

    detections = NudeNetDetector().detect(image)

    assert [(item.label, item.score) for item in detections] == [
        ("FEMALE_BREAST_EXPOSED", 0.8),
        ("FACE_FEMALE", 0.9),
    ]
