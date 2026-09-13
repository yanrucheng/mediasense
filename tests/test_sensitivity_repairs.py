"""Independent review counterexamples; synthetic ports only, no model inference."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from mediasense.precheck import ResultStore, PrecheckReadTool, ResultSealError
from mediasense.precheck.read import _ReadFailure
from mediasense.precheck._sensitivity_profiles import (
    FREEPIK,
    NUDENET640,
    SensitivityBackendUnavailable,
)
from mediasense.precheck._sensitivity_models import LocalSensitivityDetector
from mediasense.precheck._local_execution import (
    collect_local_execution,
    validate_local_execution,
    LocalExecutionError,
)
from mediasense.precheck.sensitivity import SensitivityProducer
from mediasense.runtime.resources import contract_validator
from test_sensitivity_named import prepared, Adapter, PROFILE


def region_result(tmp_path):
    from mediasense.precheck._sensitivity_profiles import SensitivityPrediction

    _, database, run, renditions, inputs = prepared(tmp_path)

    class Regions(Adapter):
        def analyze(self, images):
            return [
                SensitivityPrediction(
                    i.key,
                    i.sha256,
                    {
                        "region_detections": {
                            "taxonomy": NUDENET640.definitions["taxonomy"],
                            "score_semantics": "model_detection_score",
                            "coordinate_system": "input_evidence_pixels_xyxy",
                            "input_dimensions": {"width": i.width, "height": i.height},
                            "instances": [
                                {
                                    "label": "FACE_FEMALE",
                                    "score": 0.9,
                                    "box_xyxy": [1, 2, 10, 20],
                                }
                            ],
                        }
                    },
                )
                for i in images
            ]

    outcome = SensitivityProducer(database, Regions(NUDENET640)).produce(
        run, inputs[0][0], inputs[0][1], profile=NUDENET640
    )
    store = ResultStore(database)
    draft = store.build_minimal(
        run,
        [r.work.work_id for r in renditions],
        sensitivity_work_ids=[outcome.work.work_id],
    )
    return database, store, draft


@pytest.mark.parametrize("fault", ["outside", "wrong_source", "dimensions"])
def test_seal_and_read_both_reject_invalid_sensitivity_input(tmp_path, fault):
    database, store, draft = region_result(tmp_path)
    sealed = store.seal(draft)
    reader = PrecheckReadTool(database)
    package = json.loads(sealed.path.read_bytes())
    source = next(
        s
        for s in package["sources"]
        if any(
            o["name"] == "content_sensitivity" and o["status"] == "available"
            for o in s["view"]["observations"]
        )
    )
    observation = next(
        o for o in source["view"]["observations"] if o["name"] == "content_sensitivity"
    )
    replacement = deepcopy(observation)
    if fault == "outside":
        replacement["provenance"]["input_evidence_ref"] = "evidence:outside"
    elif fault == "dimensions":
        replacement["value"]["region_detections"]["input_dimensions"]["width"] += 1
    else:
        other = next(s for s in package["sources"] if s is not source)
        evidence = next(
            r["origin"]
            for r in package["relationships"]
            if r["relation"] == "derived_from"
            and (
                r["member"]["target"].get("ref")
                if isinstance(r["member"]["target"], dict)
                else r["member"]["target"]
            )
            == other["view"]["ref"]
        )
        replacement["provenance"]["input_evidence_ref"] = evidence
    source["view"]["observations"] = [
        replacement if o is observation else o for o in source["view"]["observations"]
    ]
    raw = json.dumps(package).encode()
    original = sealed.path.read_bytes()
    with pytest.raises(_ReadFailure) as failure:
        reader._validate_package(raw, sealed.result_ref, [])
    assert failure.value.code == "result_untrusted"
    changed = replace(
        draft,
        sources=tuple(
            replace(
                s,
                observations=tuple(
                    replacement
                    if o.get("name") == "content_sensitivity"
                    and o.get("status") == "available"
                    else o
                    for o in s.observations
                ),
            )
            if s.ref == source["view"]["ref"]
            else s
            for s in draft.sources
        ),
    )
    with pytest.raises(ResultSealError):
        store.seal(changed)
    assert sealed.path.read_bytes() == original
    reader._validate_package(original, sealed.result_ref, [])


def fake_load_imports(monkeypatch, tmp_path, backend, error):
    def explode(*args, **kwargs):
        raise error

    if backend == "freepik":
        monkeypatch.setitem(
            sys.modules,
            "torch",
            SimpleNamespace(
                backends=SimpleNamespace(
                    mps=SimpleNamespace(is_available=lambda: True)
                ),
                float32="float32",
                set_num_threads=lambda n: None,
                get_num_interop_threads=lambda: 1,
            ),
        )
        monkeypatch.setitem(
            sys.modules,
            "transformers",
            SimpleNamespace(
                AutoModelForImageClassification=SimpleNamespace(from_pretrained=explode)
            ),
        )
        monkeypatch.setitem(sys.modules, "timm", SimpleNamespace())
        monkeypatch.setitem(
            sys.modules,
            "timm.data",
            SimpleNamespace(
                create_transform=lambda **kw: None,
                resolve_data_config=lambda *a, **kw: {},
            ),
        )
        return LocalSensitivityDetector(FREEPIK, tmp_path)._load_freepik
    native = tmp_path / "native.py"
    native.write_text("synthetic")
    import mediasense.precheck._sensitivity_models as module

    monkeypatch.setattr(
        module.hashlib,
        "sha256",
        lambda b: SimpleNamespace(
            hexdigest=lambda: (
                "4ce2b9e18a698196afc7ec5bef66c2f2be14b85dc6c57041a4392fbb58c1952c"
            )
        ),
    )
    monkeypatch.setitem(
        sys.modules, "cv2", SimpleNamespace(setNumThreads=lambda n: None)
    )
    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(
            disable_telemetry_events=lambda: None,
            get_available_providers=lambda: ["CPUExecutionProvider"],
            SessionOptions=SimpleNamespace,
            InferenceSession=explode,
        ),
    )
    module_native = SimpleNamespace(__file__=str(native))
    monkeypatch.setitem(
        sys.modules,
        "nudenet",
        SimpleNamespace(
            NudeDetector=type("NudeDetector", (), {}), nudenet=module_native
        ),
    )
    monkeypatch.setitem(sys.modules, "nudenet.nudenet", module_native)
    return LocalSensitivityDetector(NUDENET640, tmp_path / "640m.onnx")._load_nudenet


@pytest.mark.parametrize("backend", ["freepik", "nudenet"])
@pytest.mark.parametrize("kind", [RuntimeError, ValueError, OSError, ImportError])
def test_unknown_loader_exceptions_are_not_prerequisite_waits(
    tmp_path, monkeypatch, backend, kind
):
    sentinel = kind("internal sentinel")
    load = fake_load_imports(monkeypatch, tmp_path, backend, sentinel)
    with pytest.raises(kind) as caught:
        load()
    assert caught.value is sentinel
    assert not isinstance(caught.value, SensitivityBackendUnavailable)


def test_known_missing_prerequisite_is_still_explicit(tmp_path, monkeypatch):
    import mediasense.precheck._sensitivity_models as module

    monkeypatch.setattr(
        module, "prerequisites", lambda *args: {"failures": ["fixed weights missing"]}
    )
    with pytest.raises(SensitivityBackendUnavailable, match="fixed weights missing"):
        LocalSensitivityDetector(FREEPIK, tmp_path).load()


def telemetry_result(tmp_path):
    _, database, run, renditions, inputs = prepared(tmp_path)
    adapter = Adapter()
    adapter.batch_execution = {"inference_input_count": len(inputs)}
    out = SensitivityProducer(database, adapter).produce_many(
        run, inputs, profile=PROFILE
    )
    from mediasense.precheck._orchestrator import PrecheckExecutionConfig

    config = PrecheckExecutionConfig(
        sensitivity_profiles=(PROFILE,),
        sensitivity_detector_identities=(adapter.identity,),
    ).value()
    local = collect_local_execution(database, run, config)
    draft = ResultStore(database).build_minimal(
        run,
        [r.work.work_id for r in renditions],
        sensitivity_work_ids=[o.work.work_id for o in out.values()],
    )
    return (
        database,
        run,
        out,
        config,
        local,
        replace(
            draft,
            execution_boundary={**draft.execution_boundary, "local_execution": local},
        ),
    )


def test_shared_batch_cost_is_counted_once_and_read_without_work(tmp_path):
    database, run, out, config, local, draft = telemetry_result(tmp_path)
    assert len(out) == 2 and len(local["batches"]) == 1
    batch = local["batches"][0]
    assert (
        batch["input_count"]
        == batch["inference_input_count"]
        == batch["included_work_count"]
        == 2
    )
    total = local["models"][0]["recorded_current"]
    assert (
        total["batch_count"] == 1
        and total["processing_wall_seconds"] == batch["processing_wall_seconds"]
    )
    assert local["resource_budget"] == config["resource_budget"]
    sealed = ResultStore(database).seal(draft)
    reader = PrecheckReadTool(database)
    graph = reader._validate_package(sealed.path.read_bytes(), sealed.result_ref, [])
    # Reading this graph needs no mutable Work/Run store or backend dependency.
    request = {
        "action": "review",
        "dataset_ref": "dataset:dataset-a",
        "result_ref": sealed.result_ref,
        "include": ["local_execution"],
        "execution_page": {"limit": 1},
    }
    response = reader._review(graph, sealed.digest, request)
    contract_validator("mediasense.precheck.read", "review").validate(response)
    assert response["local_execution"]["batches"] == local["batches"]
    assert response["local_execution"]["page"] == {"total": 1, "next_cursor": None}
    for fault in ("duplicate", "sum", "coverage"):
        bad = deepcopy(local)
        if fault == "duplicate":
            bad["batches"] *= 2
        elif fault == "coverage":
            bad["models"][0]["unreported_work_count"] += 1
        else:
            bad["models"][0]["recorded_current"]["processing_wall_seconds"] += 1
        with pytest.raises(LocalExecutionError):
            validate_local_execution(bad)


def test_local_execution_contract_fragments_have_one_authoring_source():
    root = Path(__file__).parents[1] / "docs/spec/contract"
    run = json.loads((root / "precheck-run/precheck-run.tool.json").read_text())
    read = json.loads((root / "precheck-read/precheck-read.tool.json").read_text())
    for name in read["x-derived-definitions"]["names"]:
        assert run["outputSchema"]["$defs"][name] == read["outputSchema"]["$defs"][name]


def run_fixture(tmp_path, *, fail=False):
    from PIL import Image
    from mediasense.precheck import PrecheckRunTool
    from mediasense.precheck._orchestrator import (
        PrecheckExecutionConfig,
        PrecheckExecutionDependencies,
    )
    from test_precheck_orchestration import (
        _prepare_source_bound_run,
        _advance_after_scope,
    )

    database, source, _ = _prepare_source_bound_run(tmp_path)
    for i in range(2):
        Image.new("RGB", (40 + i * 10, 60), "purple").save(source / f"{i}.jpg")
    profile = replace(
        PROFILE, device="synthetic", batch_size=1, memory_bytes=64 * 1024**2
    )

    class Measured(Adapter):
        def analyze(self, inputs):
            if fail:
                raise RuntimeError("injected unknown load defect")
            self.batch_execution = {"inference_input_count": len(inputs)}
            return super().analyze(inputs)

    adapter = Measured(profile)
    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            metadata=False,
            gpx=False,
            bundles=False,
            video=False,
            sensitivity_profiles=(profile,),
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            sensitivity_detectors=(adapter,)
        ),
    )
    request = {
        "action": "start",
        "dataset_ref": "dataset:dataset-a",
        "request_id": "request:repair",
    }
    ref = tool.run(request)["run_ref"]
    if fail:
        with pytest.raises(RuntimeError, match="injected unknown load defect"):
            _advance_after_scope(tool, ref)
        result = tool.run(
            {"action": "status", "dataset_ref": "dataset:dataset-a", "run_ref": ref}
        )
    else:
        result = _advance_after_scope(tool, ref)
    return tool, ref, result, adapter


def test_unexpected_load_failure_is_a_failed_run_not_normal_block(tmp_path):
    _, _, result, _ = run_fixture(tmp_path, fail=True)
    assert (
        result["state"] == "failed"
        and result["reason"]["code"] != "sensitivity_backend_unavailable"
    )


def test_public_run_and_sealed_read_deliver_same_budget_and_paged_batches(tmp_path):
    tool, ref, result, adapter = run_fixture(tmp_path)
    assert result["state"] == "completed", result
    query = {
        "action": "status",
        "dataset_ref": "dataset:dataset-a",
        "run_ref": ref,
        "include": ["local_execution"],
        "page": {"limit": 1},
    }
    first = tool.run(query)
    contract_validator("mediasense.precheck.run", "status").validate(first)
    local = first["local_execution"]
    assert local["resource_budget"]["capacity"]["memory_bytes"] > 0
    assert (
        local["page"]["total"] == 2
        and len(local["batches"]) == 1
        and local["page"]["next_cursor"]
    )
    second = tool.run(
        {**query, "page": {"limit": 1, "cursor": local["page"]["next_cursor"]}}
    )
    assert second["local_execution"]["page"]["next_cursor"] is None
    assert (
        first["local_execution"]["batches"][0]["batch_id"]
        != second["local_execution"]["batches"][0]["batch_id"]
    )
    diagnostics = tool.run({**query, "include": ["diagnostics"]})["diagnostics"][
        "local_execution"
    ]
    assert diagnostics["models"] == local["models"] and "batches" not in diagnostics
    request = {
        "action": "review",
        "dataset_ref": "dataset:dataset-a",
        "result_ref": result["result"]["ref"],
        "include": ["local_execution"],
        "execution_page": {"limit": 1},
    }
    read = PrecheckReadTool(tool.database_path).read(request)
    contract_validator("mediasense.precheck.read", "review").validate(read)
    assert read["local_execution"]["models"] == local["models"]
    assert read["local_execution"]["resource_budget"] == local["resource_budget"]
    assert read["local_execution"]["batches"] == local["batches"]
    read2 = PrecheckReadTool(tool.database_path).read(
        {
            **request,
            "execution_page": {
                "limit": 1,
                "cursor": read["local_execution"]["page"]["next_cursor"],
            },
        }
    )
    assert read2["local_execution"]["batches"] == second["local_execution"]["batches"]
    stale = tool.run(
        {**query, "page": {"limit": 2, "cursor": local["page"]["next_cursor"]}}
    )
    assert stale["error"]["code"] == "invalid_cursor"


def test_retained_result_without_execution_snapshot_stays_unknown(
    tmp_path, monkeypatch
):
    database, store, draft = region_result(tmp_path)
    result = store.seal(draft)
    from mediasense.precheck.work import WorkStore

    def forbidden(*args, **kwargs):
        raise AssertionError("Read must not query private Work")

    monkeypatch.setattr(WorkStore, "iter_run_work", forbidden)
    monkeypatch.setattr(WorkStore, "get_work", forbidden)
    response = PrecheckReadTool(database).read(
        {
            "action": "review",
            "dataset_ref": "dataset:dataset-a",
            "result_ref": result.result_ref,
            "include": ["local_execution"],
        }
    )
    assert response["local_execution"] == {
        "status": "not_recorded",
        "resource_budget": None,
        "models": [],
        "batches": [],
        "page": {"total": 0, "next_cursor": None},
    }


@pytest.mark.parametrize("kind", [RuntimeError, AttributeError, OSError])
def test_unknown_prerequisite_probe_error_is_not_reported_as_missing(
    tmp_path, monkeypatch, kind
):
    import mediasense.precheck._sensitivity_models as module

    monkeypatch.setattr(
        module, "version", lambda package: FREEPIK.dependencies[package]
    )

    def broken(*args, **kwargs):
        raise kind("unexpected probe defect")

    monkeypatch.setattr(Path, "open", broken)
    with pytest.raises(kind, match="unexpected probe defect"):
        module.prerequisites(FREEPIK, tmp_path)
