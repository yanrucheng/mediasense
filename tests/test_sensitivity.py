from __future__ import annotations

from dataclasses import replace
from mediasense.precheck._sensitivity_profiles import FREEPIK, SensitivityPrediction

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    HIGH_RESOLUTION_RENDITION_PROFILE,
    ImageRenditionProducer,
    PrecheckReadTool,
    ResultSealError,
    ResultStore,
    SensitivityProducer,
    WorkStatus,
    WorkStore,
)


SPEC_ROOT = Path(__file__).parents[1] / "docs" / "spec" / "contract/precheck-read"


def _closed_run(database: Path, source: Path) -> str:
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    return run_id


PROFILE = replace(
    FREEPIK,
    name="test-sensitivity-v2",
    model_id="synthetic/sensitivity",
    definitions={
        "declared_properties": ["classification_distribution"],
        "taxonomy": "synthetic",
        "labels": ["sensitive", "ordinary"],
        "meaning": "Synthetic exclusive scores",
    },
    basis={},
    memory_bytes=64 * 1024**2,
)


class FakeDetector:
    def __init__(self, *, identity="fake-detector@sha256:one", profile=PROFILE):
        self.identity, self.profile = identity, profile
        self.calls, self.batch_calls = [], []
        self.fail = False
        self.execution = {"device": "synthetic", "precision": "float32"}

    @property
    def declaration(self):
        return self.profile.value()

    def analyze(self, inputs):
        self.calls.extend(i.path for i in inputs)
        self.batch_calls.append(tuple(i.path for i in inputs))
        return tuple(
            SensitivityPrediction(
                i.key,
                i.sha256,
                None
                if self.fail
                else {
                    "classification_distribution": {
                        "taxonomy": "synthetic",
                        "score_semantics": "categorical_probability",
                        "probabilities": {"sensitive": 0.8, "ordinary": 0.2},
                    }
                },
                "known local input failure" if self.fail else None,
            )
            for i in inputs
        )

    def close(self):
        pass


BatchDetector = FakeDetector


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
    assert value["classification_distribution"]["probabilities"]["sensitive"] == 0.8
    assert "labels" not in value
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


def test_sensitivity_many_uses_one_backend_batch_with_per_item_work(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    for name, color in (("a.jpg", "red"), ("b.jpg", "blue")):
        Image.new("RGB", (80, 40), color).save(source / name)
    run_id = _closed_run(database, source)
    renditions = tuple(
        ImageRenditionProducer(database).produce(
            run_id,
            Path(name),
            profile=HIGH_RESOLUTION_RENDITION_PROFILE,
        )
        for name in ("a.jpg", "b.jpg")
    )
    detector = BatchDetector()

    outcomes = SensitivityProducer(database, detector).produce_many(
        run_id,
        tuple(
            (Path(name), rendition.work.work_id)
            for name, rendition in zip(("a.jpg", "b.jpg"), renditions, strict=True)
        ),
        profile=PROFILE,
    )

    assert len(detector.batch_calls) == 1
    assert len(detector.batch_calls[0]) == 2
    assert len(outcomes) == 2
    assert all(
        outcome.work.status is WorkStatus.SUCCEEDED for outcome in outcomes.values()
    )


def test_detector_or_semantic_recipe_change_has_narrow_semantic_invalidation(
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
    changed_threshold = replace(PROFILE, adapter_revision="changed-output-v2")
    second = SensitivityProducer(
        database, FakeDetector(profile=changed_threshold)
    ).produce(
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
    assert (
        failed.work.output["observations"][0]["provenance"]["definitions"]
        == PROFILE.definitions
    )
    assert (
        failed.work.output["observations"][0]["provenance"]["actual_execution"]
        == detector.execution
    )

    draft = ResultStore(database).build_minimal(
        run_id,
        [good_rendition.work.work_id, failed_rendition.work.work_id],
        sensitivity_work_ids=[good.work.work_id, failed.work.work_id],
    )
    sealed = ResultStore(database).seal(draft)
    reader = PrecheckReadTool(database)
    accounted = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "resolve",
            "result_ref": sealed.result_ref,
            "source_set": {
                "kind": "precheck_relation",
                "origin": sealed.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )
    source_by_path = {
        item["locator"]["value"]: item["source_item_ref"]
        for item in accounted["members"]
    }
    source_response = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "action": "expand",
            "result_ref": sealed.result_ref,
            "source_item_refs": [
                source_by_path["good.jpg"],
                source_by_path["failed.jpg"],
            ],
            "include": ["source_item", "observations"],
        }
    )
    schema = json.loads((SPEC_ROOT / "precheck-read.tool.json").read_text())
    Draft202012Validator(schema["outputSchema"]).validate(source_response)
    views = {
        item["source_item_ref"]: item["included"] for item in source_response["items"]
    }
    good_view = views[source_by_path["good.jpg"]]
    failed_view = views[source_by_path["failed.jpg"]]

    assert any(
        item["name"] == "content_sensitivity" and item["status"] == "available"
        for item in good_view["observations"]
    )
    assert any(
        item["name"] == "content_sensitivity" and item["status"] == "failed"
        for item in failed_view["observations"]
    )


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
