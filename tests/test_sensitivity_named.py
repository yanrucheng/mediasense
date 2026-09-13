"""Replacement-port, integrity, cache and failure boundaries on real prepared images."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sqlite3

from PIL import Image
import pytest
from test_sensitivity import _closed_run

from mediasense.precheck import (
    ImageRenditionProducer,
    HIGH_RESOLUTION_RENDITION_PROFILE,
    ResultStore,
    PrecheckReadTool,
    WorkStatus,
)
from mediasense.precheck.sensitivity import SensitivityProducer
from mediasense.precheck._sensitivity_profiles import (
    FREEPIK,
    NUDENET640,
    SensitivityPrediction,
    SensitivityError,
    SensitivityBackendUnavailable,
    normalize_sensitivity,
)
from mediasense.precheck._sensitivity_values import validate_named_value

PROFILE = replace(
    FREEPIK,
    name="synthetic-weather-v1",
    model_id="synthetic/weather",
    definitions={
        "declared_properties": ["classification_distribution"],
        "taxonomy": "weather",
        "labels": ["dry", "wet"],
        "meaning": "Synthetic mutually exclusive probabilities",
    },
    basis={},
)


class Adapter:
    def __init__(self, profile=PROFILE, mode="reverse"):
        self.profile, self.mode = profile, mode
        self.calls = []
        self.execution = {"device": "synthetic", "precision": "float32"}

    @property
    def identity(self):
        return self.profile.identity

    def analyze(self, inputs):
        self.calls.append(inputs)
        if self.mode == "unavailable":
            raise SensitivityBackendUnavailable("test missing weights")
        if self.mode == "unexpected":
            raise RuntimeError("unexpected implementation defect")
        rows = [
            SensitivityPrediction(
                i.key,
                i.sha256,
                {
                    "classification_distribution": {
                        "taxonomy": "weather",
                        "score_semantics": "categorical_probability",
                        "probabilities": {
                            "dry": i.width / (i.width + i.height),
                            "wet": i.height / (i.width + i.height),
                        },
                    }
                },
            )
            for i in inputs
        ]
        if self.mode == "reverse":
            rows.reverse()
        elif self.mode == "duplicate":
            rows[-1] = rows[0]
        elif self.mode == "missing":
            rows.pop()
        elif self.mode == "nested_undeclared":
            rows[0].values["classification_distribution"]["logits"] = [1, 2]
        elif self.mode == "wrong_identity":
            rows[0] = replace(rows[0], sha256="0" * 64)
        elif self.mode == "localized":
            rows[0] = replace(rows[0], values=None, failure="known input failure")
        return rows

    def close(self):
        pass


def prepared(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for i in range(2):
        Image.new("RGB", (40 + i * 40, 60), "purple").save(source / f"{i}.jpg")
    database = tmp_path / "workspace" / "work.sqlite3"
    run = _closed_run(database, source)
    renditions = [
        ImageRenditionProducer(database).produce(
            run, Path(f"{i}.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
        )
        for i in range(2)
    ]
    inputs = [(Path(f"{i}.jpg"), r.work.work_id) for i, r in enumerate(renditions)]
    return source, database, run, renditions, inputs


def test_generic_reversed_classifier_flows_through_seal_read_and_cache(tmp_path):
    source, database, run, renditions, inputs = prepared(tmp_path)
    adapter = Adapter()
    out = SensitivityProducer(database, adapter).produce_many(
        run, inputs, profile=PROFILE
    )
    assert [
        out[k].observations[0]["value"]["classification_distribution"]["probabilities"][
            "dry"
        ]
        for _, k in inputs
    ] == [0.4, 80 / 140]
    draft = ResultStore(database).build_minimal(
        run,
        [r.work.work_id for r in renditions],
        sensitivity_work_ids=[o.work.work_id for o in out.values()],
    )
    sealed = ResultStore(database).seal(draft)
    read = PrecheckReadTool(database).read(
        {
            "action": "review",
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
        }
    )
    assert "error" not in read, read
    assert (
        len(
            [
                o
                for item in read["items"]
                for src in item["source_items"]
                for o in src["observations"]
                if o["name"] == "content_sensitivity" and o["status"] == "available"
            ]
        )
        == 2
    )
    before = {r.work.work_id for r in renditions}
    second = _closed_run(database, source)
    next_inputs = [
        (
            p,
            ImageRenditionProducer(database)
            .produce(second, p, profile=HIGH_RESOLUTION_RENDITION_PROFILE)
            .work.work_id,
        )
        for p, _ in inputs
    ]
    assert {w for _, w in next_inputs} == before
    unavailable = Adapter(mode="unavailable")
    reused = SensitivityProducer(database, unavailable).produce_many(
        second, next_inputs, profile=PROFILE
    )
    assert all(o.reused for o in reused.values()) and not unavailable.calls
    # Scheduling and memory estimates do not change semantic identity.
    scheduled = replace(PROFILE, batch_size=1, memory_bytes=1)
    assert scheduled.identity == PROFILE.identity
    changed = replace(PROFILE, adapter_revision="semantic-change-v2")
    assert changed.identity != PROFILE.identity
    assert NUDENET640.identity == deepcopy(NUDENET640).identity


@pytest.mark.parametrize(
    "mode",
    ["duplicate", "missing", "wrong_identity", "unexpected", "nested_undeclared"],
)
def test_invalid_batch_cannot_publish_any_success(tmp_path, mode):
    _, database, run, _, inputs = prepared(tmp_path)
    with pytest.raises((SensitivityError, RuntimeError, ValueError)):
        SensitivityProducer(database, Adapter(mode=mode)).produce_many(
            run, inputs, profile=PROFILE
        )
    with sqlite3.connect(database) as db:
        assert (
            db.execute(
                "SELECT count(*) FROM work_records WHERE capability='content-sensitivity' AND status='succeeded'"
            ).fetchone()[0]
            == 0
        )


def test_known_input_failure_preserves_sibling_success(tmp_path):
    _, database, run, _, inputs = prepared(tmp_path)
    out = SensitivityProducer(database, Adapter(mode="localized")).produce_many(
        run, inputs, profile=PROFILE
    )
    assert out[inputs[0][1]].work.status is WorkStatus.TERMINAL_FAILURE
    assert out[inputs[1][1]].work.status is WorkStatus.SUCCEEDED


def test_missing_backend_can_restore_original_work(tmp_path):
    _, database, run, _, inputs = prepared(tmp_path)
    with pytest.raises(SensitivityBackendUnavailable):
        SensitivityProducer(database, Adapter(mode="unavailable")).produce_many(
            run, inputs, profile=PROFILE
        )
    recovered = SensitivityProducer(database, Adapter()).produce_many(
        run, inputs, profile=PROFILE
    )
    assert all(o.work.status is WorkStatus.SUCCEEDED for o in recovered.values())


@pytest.mark.parametrize(
    "bad",
    [
        {"enabled": 1},
        {"device": "cpu"},
        {"models": {"unknown": {}}},
        {"models": {"freepik": {"batch_size": True}}},
        {"enabled": True, "models": {"freepik": {"enabled": True}}},
        {"models": {"nudenet640": {"device": "mps"}}},
        {"models": {"freepik": {"model_path": "relative"}}},
    ],
)
def test_configuration_rejects_unreviewed_recipes(bad):
    with pytest.raises(ValueError):
        normalize_sensitivity(bad)


def test_region_instances_and_dimension_proof():
    value = {
        "detector_identity": NUDENET640.identity,
        "profile": NUDENET640.name,
        "region_detections": {
            "taxonomy": NUDENET640.definitions["taxonomy"],
            "score_semantics": "model_detection_score",
            "coordinate_system": "input_evidence_pixels_xyxy",
            "input_dimensions": {"width": 1000, "height": 1500},
            "instances": [
                {"label": "FACE_FEMALE", "score": 0.8, "box_xyxy": [1, 2, 3, 4]},
                {"label": "FACE_FEMALE", "score": 0.7, "box_xyxy": [5, 6, 7, 8]},
            ],
        },
    }
    validate_named_value(
        value, NUDENET640.definitions, NUDENET640.basis, {"width": 1000, "height": 1500}
    )
    with pytest.raises(ValueError):
        validate_named_value(
            value,
            NUDENET640.definitions,
            NUDENET640.basis,
            {"width": 1500, "height": 1000},
        )
    value["region_detections"]["instances"] = []
    validate_named_value(value, NUDENET640.definitions, NUDENET640.basis)


def test_model_residency_is_admitted_through_close_and_batches_are_independent(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from mediasense.precheck._orchestrator import PrecheckOrchestrator
    from mediasense.precheck.resources import (
        ResourceBudget,
        ResourceClaim,
        BoundedWorkExecutor,
    )

    _, database, run, renditions, _ = prepared(tmp_path)
    profile = replace(PROFILE, batch_size=1, memory_bytes=64 * 1024**2)
    budget = ResourceBudget(
        ResourceClaim(
            cpu_slots=2, workspace_io_slots=1, memory_bytes=64 * 1024**2, model_slots=1
        ),
        max_workers=1,
        max_pending=1,
    )
    executor = BoundedWorkExecutor(budget)
    closed = []

    class Accounted(Adapter):
        def analyze(self, inputs):
            assert len(inputs) == 1
            assert executor.admission.usage().memory_bytes == profile.memory_bytes
            return super().analyze(inputs)

        def close(self):
            assert executor.admission.usage().memory_bytes == profile.memory_bytes
            closed.append(True)

    adapter = Accounted(profile)
    orchestrator = PrecheckOrchestrator(database, None)
    monkeypatch.setattr(orchestrator, "_running", lambda ref: True)
    monkeypatch.setattr(orchestrator, "_checkpoint", lambda *a, **kw: None)
    config = SimpleNamespace(model_batch_size=16)
    result = orchestrator._detect_sensitivity(
        "run:test", run, tuple(renditions), (), config, executor, profile, adapter
    )
    assert len(result) == 2 and len(adapter.calls) == 2 and closed
    assert executor.admission.usage().memory_bytes == 0
    assert executor.admission.peak_usage().memory_bytes == profile.memory_bytes


def test_oversized_model_demand_is_not_clamped(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from mediasense.precheck._orchestrator import PrecheckOrchestrator
    from mediasense.precheck.resources import (
        ResourceBudget,
        ResourceClaim,
        BoundedWorkExecutor,
        ResourceLimitExceeded,
    )

    _, database, run, renditions, _ = prepared(tmp_path)
    executor = BoundedWorkExecutor(
        ResourceBudget(
            ResourceClaim(
                cpu_slots=2, workspace_io_slots=1, memory_bytes=1, model_slots=1
            ),
            max_workers=1,
            max_pending=1,
        )
    )
    orchestrator = PrecheckOrchestrator(database, None)
    monkeypatch.setattr(orchestrator, "_running", lambda ref: True)
    monkeypatch.setattr(orchestrator, "_checkpoint", lambda *a, **kw: None)
    adapter = Adapter(PROFILE)
    with pytest.raises(ResourceLimitExceeded):
        orchestrator._detect_sensitivity(
            "run:test",
            run,
            tuple(renditions),
            (),
            SimpleNamespace(model_batch_size=1),
            executor,
            PROFILE,
            adapter,
        )
    assert not adapter.calls and executor.admission.peak_usage().memory_bytes == 0


def test_one_recipe_change_reuses_unrelated_model_work(tmp_path):
    _, database, run, _, inputs = prepared(tmp_path)
    first = Adapter(PROFILE)
    sibling_profile = replace(
        PROFILE, name="another-taxonomy-profile", model_id="synthetic/sibling"
    )
    sibling = Adapter(sibling_profile)
    a = SensitivityProducer(database, first).produce_many(run, inputs, profile=PROFILE)
    b = SensitivityProducer(database, sibling).produce_many(
        run, inputs, profile=sibling_profile
    )
    changed_profile = replace(PROFILE, adapter_revision="semantic-v3")
    changed = Adapter(changed_profile)
    a2 = SensitivityProducer(database, changed).produce_many(
        run, inputs, profile=changed_profile
    )
    b2 = SensitivityProducer(database, sibling).produce_many(
        run, inputs, profile=sibling_profile
    )
    assert {x.work.work_id for x in a.values()}.isdisjoint(
        {x.work.work_id for x in a2.values()}
    )
    assert [x.work.work_id for x in b.values()] == [x.work.work_id for x in b2.values()]
    assert all(x.reused for x in b2.values()) and len(sibling.calls) == 1


def test_multiple_native_regions_survive_public_read_and_wrong_source_is_rejected(
    tmp_path,
):
    from dataclasses import replace
    from mediasense.precheck import ResultSealError

    _, database, run, renditions, inputs = prepared(tmp_path)

    class Regions(Adapter):
        def analyze(self, images):
            self.calls.append(images)
            return [
                SensitivityPrediction(
                    i.key,
                    i.sha256,
                    {
                        "region_detections": {
                            "taxonomy": self.profile.definitions["taxonomy"],
                            "score_semantics": "model_detection_score",
                            "coordinate_system": "input_evidence_pixels_xyxy",
                            "input_dimensions": {"width": i.width, "height": i.height},
                            "instances": [
                                {
                                    "label": "FACE_FEMALE",
                                    "score": 0.9,
                                    "box_xyxy": [1, 2, 10, 20],
                                },
                                {
                                    "label": "FACE_FEMALE",
                                    "score": 0.7,
                                    "box_xyxy": [11, 22, 30, 50],
                                },
                                {
                                    "label": "FEMALE_BREAST_COVERED",
                                    "score": 0.8,
                                    "box_xyxy": [4, 6, 20, 40],
                                },
                            ],
                        }
                    },
                )
                for i in images
            ]

    adapter = Regions(NUDENET640)
    outcome = SensitivityProducer(database, adapter).produce(
        run, inputs[0][0], inputs[0][1], profile=NUDENET640
    )
    store = ResultStore(database)
    draft = store.build_minimal(
        run,
        [r.work.work_id for r in renditions],
        sensitivity_work_ids=[outcome.work.work_id],
    )
    source = next(s for s in draft.sources if s.relative_path == inputs[0][0])
    other = next(s for s in draft.sources if s.relative_path == inputs[1][0])
    observation = next(
        o for o in source.observations if o["name"] == "content_sensitivity"
    )
    wrong_other = replace(
        other,
        observations=tuple(
            o for o in other.observations if o["name"] != "content_sensitivity"
        )
        + (observation,),
    )
    with pytest.raises(ResultSealError, match="derive from its Source Item"):
        store.seal(
            replace(
                draft,
                sources=tuple(
                    wrong_other if s.ref == other.ref else s for s in draft.sources
                ),
            )
        )
    sealed = store.seal(draft)
    read = PrecheckReadTool(database).read(
        {
            "action": "expand",
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "source_item_refs": [source.ref],
            "include": ["observations"],
        }
    )
    delivered = next(
        o
        for o in read["items"][0]["included"]["observations"]
        if o["name"] == "content_sensitivity"
    )
    assert (
        delivered["value"]["region_detections"]
        == outcome.observations[0]["value"]["region_detections"]
    )
    assert len(delivered["value"]["region_detections"]["instances"]) == 3
