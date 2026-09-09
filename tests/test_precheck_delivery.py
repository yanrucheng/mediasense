"""Current contract delivery, failure continuation, source ownership and configuration."""

from dataclasses import replace
from pathlib import Path

from PIL import Image
import pytest

from mediasense.precheck import (
    AccountingStore,
    ImageRenditionProducer,
    ResultStore,
    PrecheckReadTool,
    ResultEvidence,
    ResultRelationship,
)
from mediasense.precheck.metadata import select_metadata_observations
from mediasense.runtime.config import load_runtime_config, ConfigurationError
from test_precheck_read_contract import check_semantics


def prepared(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    for index in range(3):
        Image.new("RGB", (20, 10), (index * 80, 80, 120)).save(source / f"{index}.jpg")
    database = tmp_path / "workspace" / "work.sqlite3"
    accounting = AccountingStore(database)
    accounting.register_dataset("delivery")
    run = accounting.start_or_resume_run("delivery", source)
    accounting.process_run(run)
    producer = ImageRenditionProducer(database)
    outcomes = [producer.produce(run, Path(f"{i}.jpg")) for i in range(3)]
    store = ResultStore(database)
    return (
        database,
        store,
        store.build_minimal(run, [o.work.work_id for o in outcomes]),
        outcomes,
    )


@pytest.mark.parametrize("failure", ["missing", "corrupt", "oversized"])
def test_review_fault_retains_position_and_continues(tmp_path, failure):
    database, store, draft, outcomes = prepared(tmp_path)
    if failure == "oversized":
        victim = draft.evidence[1]
        draft = replace(
            draft,
            evidence=(
                draft.evidence[0],
                replace(
                    victim,
                    observations=(
                        *victim.observations,
                        {
                            "name": "retained_text",
                            "status": "available",
                            "value": "长" * 200_000,
                        },
                    ),
                ),
                *draft.evidence[2:],
            ),
        )
    sealed = store.seal(draft)
    if failure == "missing":
        outcomes[1].artifact.path.unlink()
    elif failure == "corrupt":
        outcomes[1].artifact.path.chmod(0o600)
        outcomes[1].artifact.path.write_bytes(b"damage")
    reader = PrecheckReadTool(database)
    cursor = None
    pages = []
    for index in range(3):
        request = {
            "action": "review",
            "dataset_ref": "dataset:delivery",
            "result_ref": sealed.result_ref,
            "page": {"limit": 1, **({"cursor": cursor} if cursor else {})},
        }
        response = reader.read(request)
        check_semantics(request, response)
        assert response["page"]["total"] == 3
        pages.append(response["items"][0])
        cursor = response["page"]["next_cursor"]
        assert bool(cursor) == (index < 2)
    assert [item["evidence_ref"] for item in pages] == list(draft.entry_evidence)
    assert "error" not in pages[0] and "error" not in pages[2]
    assert pages[1]["error"]["code"] == (
        "response_item_too_large" if failure == "oversized" else "evidence_unavailable"
    )
    assert set(pages[1]) == {"evidence_ref", "error"}
    explicit = reader.read(
        {
            "action": "review",
            "dataset_ref": "dataset:delivery",
            "result_ref": sealed.result_ref,
            "evidence_refs": [pages[1]["evidence_ref"]],
        }
    )
    assert explicit["items"] == [pages[1]]


def test_review_actual_multisource_lineage_is_not_represented_members(tmp_path):
    database, store, draft, _ = prepared(tmp_path)
    refs = [source.ref for source in draft.sources]
    source_values = tuple(
        replace(
            source,
            observations=(
                *source.observations,
                {"name": "camera_model", "status": "available", "value": f"camera-{i}"},
            ),
        )
        for i, source in enumerate(draft.sources)
    )
    inline = ResultEvidence(
        ref="evidence:composite",
        access={
            "kind": "inline",
            "value": {"description": "synthetic two-source composition"},
        },
    )
    draft = replace(
        draft,
        sources=source_values,
        evidence=(*draft.evidence, inline),
        relationships=(
            *draft.relationships,
            ResultRelationship(
                origin_ref=inline.ref,
                relation="derived_from",
                target_ref=draft.evidence[0].ref,
                target_kind="evidence",
            ),
            ResultRelationship(
                origin_ref=inline.ref,
                relation="derived_from",
                target_ref=refs[1],
                target_kind="source_item",
            ),
            ResultRelationship(
                origin_ref=inline.ref,
                relation="represents",
                target_ref=refs[2],
                target_kind="source_item",
                basis="Synthetic unrelated coverage claim",
            ),
        ),
    )
    sealed = store.seal(draft)
    request = {
        "action": "review",
        "dataset_ref": "dataset:delivery",
        "result_ref": sealed.result_ref,
        "evidence_refs": [inline.ref],
    }
    response = PrecheckReadTool(database).read(request)
    check_semantics(request, response)
    item = response["items"][0]
    assert {source["source_item_ref"] for source in item["source_items"]} == set(
        refs[:2]
    )
    assert item["represents"]["source_count"] == 1
    assert {o["name"] for o in item["represents"]["observations"]} == {
        "capture_time_range",
        "media_type_counts",
    }


def test_metadata_sidecar_values_conflicts_and_source_dimensions_are_distinct():
    observations = select_metadata_observations(
        [
            {
                "relative_path": "photo.jpg",
                "fields": {
                    "EXIF:FocalLength": 50,
                    "EXIF:ExposureTime": "1/25",
                    "File:ImageWidth": 640,
                    "File:ImageHeight": 480,
                    "EXIF:SerialNumber": "C1",
                    "MakerNotes:FirmwareVersion": "1.2",
                    "EXIF:GPSAltitude": 10,
                    "EXIF:GPSAltitudeRef": 1,
                },
            },
            {
                "relative_path": "photo.xmp",
                "fields": {
                    "XMP:FocalLength": 100,
                    "EXIF:ImageWidth": 6000,
                    "EXIF:ImageHeight": 4000,
                    "XMP:LensSerialNumber": "L1",
                    "XMP:GPSVersionID": "2.3.0.0",
                },
            },
        ],
        subject=Path("photo.jpg"),
        source_precedence=(Path("photo.jpg"), Path("photo.xmp")),
    )
    values = {o["name"]: o for o in observations}
    assert values["focal_length_mm"]["value"] == 100
    assert values["focal_length_mm"]["provenance"]["relative_path"] == "photo.xmp"
    assert (
        values["focal_length_mm"]["qualifications"][0]["code"]
        == "metadata_source_conflict"
    )
    assert values["exposure_time_seconds"]["value"] == 0.04
    assert values["source_pixel_dimensions"]["value"] == {"width": 640, "height": 480}
    assert values["gps_altitude_meters"]["value"] == -10
    assert values["camera_firmware"]["value"] == "1.2"
    assert values["focal_length_35mm_equivalent_mm"]["status"] == "missing"


@pytest.mark.parametrize(
    "body",
    [
        'enabled="true"',
        'enabled=true\nnsfw_revision="main"',
        "enabled=false\nunknown=1",
        "device=3",
        "nsfw_model_id=42",
    ],
)
def test_sensitivity_rejects_invalid_configuration(tmp_path, body):
    config = tmp_path / "config.toml"
    config.write_text("[sensitivity]\n" + body)
    with pytest.raises(ConfigurationError):
        load_runtime_config(user_config=config)


def test_sensitivity_configuration_is_explicit_and_dataset_replaces_user(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[sensitivity]\nnsfw_revision="' + "a" * 40 + '"\n')
    assert load_runtime_config(user_config=config).sensitivity is None
    config.write_text(config.read_text() + "enabled=true\n")
    enabled = load_runtime_config(user_config=config).sensitivity
    assert (
        enabled["device"] == "cpu"
        and enabled["nsfw_model_id"] == "Falconsai/nsfw_image_detection"
    )
    workspace = tmp_path / "dataset"
    workspace.mkdir()
    (workspace / "config.toml").write_text("[sensitivity]\nenabled=false\n")
    assert (
        load_runtime_config(user_config=config, dataset_workspace=workspace).sensitivity
        is None
    )


def test_all_release_schema_snapshots_match_the_single_contract_home():
    from mediasense.runtime.resources import resource_root

    root = Path(__file__).parents[1]
    for contract in (root / "docs/spec/contract").rglob("*.json"):
        if contract.name.endswith((".tool.json", ".schema.json")):
            assert (
                contract.read_bytes()
                == (resource_root() / "contracts" / contract.name).read_bytes()
            )
    from _plan_support import MockPrecheckReader
    from mediasense.runtime.resources import contract_validator

    mock = MockPrecheckReader()
    contract_validator("mediasense.precheck.read", "review").validate(
        mock.review_response
    )


def test_shared_decode_keeps_independent_profile_reuse(tmp_path, monkeypatch):
    from mediasense.precheck import (
        HIGH_RESOLUTION_RENDITION_PROFILE,
        ORDINARY_RENDITION_PROFILE,
    )
    import mediasense.precheck.rendition as rendition

    database, _store, draft, _ = prepared(tmp_path)
    calls = []
    original = rendition._decode_rgb

    def decode(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(rendition, "_decode_rgb", decode)
    producer = ImageRenditionProducer(database)
    # Ordinary is cached; the independent high profile is the only work to decode.
    profiles = (ORDINARY_RENDITION_PROFILE, HIGH_RESOLUTION_RENDITION_PROFILE)
    values = producer.produce_profiles(draft.run_id, Path("0.jpg"), profiles=profiles)
    assert [value.reused for value in values] == [True, False]
    assert len(calls) == 1
    assert all(
        value.reused
        for value in producer.produce_profiles(
            draft.run_id, Path("0.jpg"), profiles=profiles
        )
    )
    assert len(calls) == 1
    uncached = (
        replace(ORDINARY_RENDITION_PROFILE, max_edge=18),
        replace(HIGH_RESOLUTION_RENDITION_PROFILE, max_edge=19),
    )
    assert all(
        not value.reused
        for value in producer.produce_profiles(
            draft.run_id, Path("0.jpg"), profiles=uncached
        )
    )
    assert len(calls) == 2  # Both newly prepared profiles share this one decode.


def test_seal_refuses_detection_input_outside_result(tmp_path):
    database, store, draft, _ = prepared(tmp_path)
    observation = {
        "name": "content_sensitivity",
        "status": "available",
        "value": {
            "detector_identity": "test-local",
            "profile": "test-v1",
            "labels": [],
        },
        "provenance": {"input_evidence_ref": "evidence:absent"},
    }
    source = replace(draft.sources[0], observations=(observation,))
    from mediasense.precheck import ResultSealError

    with pytest.raises(ResultSealError, match="input Evidence"):
        store.seal(replace(draft, sources=(source, *draft.sources[1:])))


@pytest.mark.parametrize(
    "distance,seconds,expected",
    [(14.9, 119.9, True), (15.1, 119.9, False), (14.9, 120.1, False)],
)
def test_geo_acquisition_boundary_is_pairwise_and_time_bounded(
    distance, seconds, expected
):
    from datetime import datetime, timedelta, timezone
    from math import degrees
    from mediasense.precheck.geocode import _LocatedSource, _locally_consistent
    from mediasense.capabilities.geo import GeoCoordinate

    start = datetime(2026, 9, 9, tzinfo=timezone.utc)
    sources = (
        _LocatedSource(Path("a.jpg"), GeoCoordinate(0, 0), "metadata-a", start),
        _LocatedSource(
            Path("b.jpg"),
            GeoCoordinate(degrees(distance / 6371000), 0),
            "metadata-b",
            start + timedelta(seconds=seconds),
        ),
    )
    assert _locally_consistent(sources) is expected


def test_geo_acquisition_does_not_chain_pairwise_distance_or_mix_datums():
    from datetime import datetime, timezone
    from math import degrees
    from mediasense.precheck.geocode import (
        _LocatedSource,
        _locally_consistent,
        _coordinate_medoid,
    )
    from mediasense.capabilities.geo import GeoCoordinate, MapDatum

    now = datetime.now(timezone.utc)
    sources = tuple(
        _LocatedSource(
            Path(f"{i}.jpg"),
            GeoCoordinate(degrees(i * 10 / 6371000), 0),
            f"metadata-{i}",
            now,
        )
        for i in range(3)
    )
    assert not _locally_consistent(
        sources
    )  # Adjacent 10 m does not license a 20 m unit.
    assert _coordinate_medoid(sources) == sources[1]
    assert not _locally_consistent(
        (
            sources[0],
            replace(sources[1], coordinate=GeoCoordinate(0, 0, MapDatum.GCJ02)),
        )
    )


def test_legacy_xml_firmware_and_encoder_information_is_preserved_without_false_camera_identity():
    fields = {
        "XML:DeviceManufacturer": "Sony",
        "XML:DeviceModelName": "FX3",
        "XML:DeviceSerialNo": "S1",
        "XMP:Firmware": "2.0",
        "XML:LensModelName": "50mm",
        "MakerNotes:ExposureTime": "1/50",
    }
    values = {
        o["name"]: o
        for o in select_metadata_observations(
            [{"relative_path": "clip.mp4", "fields": fields}],
            subject=Path("clip.mp4"),
            source_precedence=(Path("clip.mp4"),),
        )
    }
    assert [
        values[n]["value"]
        for n in (
            "camera_make",
            "camera_model",
            "camera_serial_number",
            "camera_firmware",
            "lens_model",
            "exposure_time_seconds",
        )
    ] == ["Sony", "FX3", "S1", "2.0", "50mm", 0.02]
    only_encoder = select_metadata_observations(
        [{"relative_path": "clip.mp4", "fields": {"QuickTime:Encoder": "lavf"}}],
        subject=Path("clip.mp4"),
        source_precedence=(Path("clip.mp4"),),
    )
    model = next(o for o in only_encoder if o["name"] == "camera_model")
    assert model["status"] == "missing"
    assert model["basis"]["candidates"][0]["raw_value"] == "lavf"
    assert (
        model["basis"]["candidates"][0]["rejection"] == "encoder_is_not_camera_identity"
    )


def test_missing_sensitivity_backend_is_blocked_and_preserves_work_for_resume(tmp_path):
    from mediasense.precheck import PrecheckRunTool
    from mediasense.precheck.run import PrecheckExecutionConfig, PrecheckExecutionDependencies
    from mediasense.precheck.sensitivity import (
        SensitivityBackendUnavailable,
        NSFW_BINARY_PROFILE_V1,
    )
    from test_precheck_orchestration import (
        _prepare_source_bound_run,
        _advance_after_scope,
    )

    database, source, _ = _prepare_source_bound_run(tmp_path)
    Image.new("RGB", (20, 10), "blue").save(source / "image.jpg")

    class Missing:
        identity = "test-local:model@immutable;runtime=unavailable"

        def detect(self, path):
            raise SensitivityBackendUnavailable("Configured weights are absent")

    tool = PrecheckRunTool(
        database,
        execution_config=PrecheckExecutionConfig(
            metadata=False,
            gpx=False,
            video=False,
            bundles=False,
            compression_target=None,
            sensitivity_profiles=(NSFW_BINARY_PROFILE_V1,),
        ),
        execution_dependencies=PrecheckExecutionDependencies(
            sensitivity_detectors=(Missing(),)
        ),
    )
    started = tool.run(
        {
            "action": "start",
            "dataset_ref": "dataset:dataset-a",
            "request_id": "request:missing-detector",
        }
    )
    _advance_after_scope(tool, started["run_ref"])
    status = tool.run(
        {
            "action": "status",
            "dataset_ref": "dataset:dataset-a",
            "run_ref": started["run_ref"],
        }
    )
    assert status["state"] == "blocked", status
    assert status["reason"]["code"] == "sensitivity_backend_unavailable"
    assert "resume" in status["allowed_actions"]
    from mediasense.precheck._orchestrator import _backend_identity_matches

    assert _backend_identity_matches(
        Missing.identity, "test-local:model@immutable;runtime=1.0"
    )
    assert not _backend_identity_matches(
        Missing.identity, "test-local:model@changed;runtime=1.0"
    )
    assert not _backend_identity_matches(
        "test-local:model@immutable;runtime=1.0",
        "test-local:model@immutable;runtime=2.0",
    )


def test_runtime_observation_check_keeps_legal_uninterpreted_provenance():
    from mediasense.precheck._result_sqlite import _validate_observations

    _validate_observations(
        (
            {
                "name": "content_sensitivity",
                "status": "not_checked",
                "basis": {"code": "capability_disabled"},
                "provenance": "uninterpreted extension",
            },
        )
    )
