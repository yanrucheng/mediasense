"""Discriminate authoring, applicability, execution and frozen knowledge semantics."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from mediasense.manufacturers import (
    KnowledgeError,
    KnowledgeSnapshot,
    builtin_knowledge,
    load_knowledge,
    validate_document,
)
from mediasense.precheck.metadata import MetadataProfile, select_metadata_observations
from mediasense.precheck._orchestrator import PrecheckExecutionConfig
from mediasense.runtime.config import ConfigurationError, load_runtime_config


def rule(identifier="acme.photo", *, shift=0, make="ACME", priority=0):
    return {
        "id": identifier,
        "operation": "add",
        "summary": "Synthetic camera knowledge",
        "priority": priority,
        "when": [{"tags": ["EXIF:Make"], "pattern": "^" + make + "$"}],
        "apply": {
            "capture_time": {
                "tags": ["EXIF:DateTimeOriginal"],
                "naive_time": "source_local",
                "shift_seconds": shift,
            }
        },
        "basis": {"sources": ["synthetic conformance input"], "limitations": []},
    }


def write_rules(root, rules, filename="custom.yaml"):
    directory = root / "manufacturers"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "rules": rules}, sort_keys=False)
    )
    return path


def observe(snapshot=None, fields=None, **profile):
    source = Path("sample.jpg")
    fields = (
        fields
        if fields is not None
        else {
            "EXIF:Make": "ACME",
            "EXIF:Model": "C1",
            "File:MIMEType": "image/jpeg",
            "EXIF:DateTimeOriginal": "2026:05:04 17:33:46",
            "XMP:DateTimeOriginal": "2026:05:04 09:33:46",
            "EXIF:Artist": "operator",
            "XMP:Rating": "1/2",
        }
    )
    values = select_metadata_observations(
        [{"relative_path": source.as_posix(), "fields": fields}],
        subject=source,
        source_precedence=(source,),
        profile=MetadataProfile(knowledge=snapshot or builtin_knowledge(), **profile),
    )
    return {value["name"]: value for value in values}


def test_authoritative_examples_and_builtin_files_conform():
    root = Path(__file__).parents[1]
    for path in (root / "docs/spec/contract/manufacturer-knowledge").glob("*.yaml"):
        validate_document(yaml.safe_load(path.read_text()), source=str(path))
    snapshot = builtin_knowledge()
    assert set(snapshot.summary()["active_rules"]) == {
        "dji.photo-time",
        "canon.dslr-photo-time",
        "sony.xml-device-fields",
        "dji.video-encoder-model",
    }
    assert snapshot.summary()["execution"] == "not_checked"


def test_user_rule_adds_real_extraction_tags_and_typed_observation(tmp_path):
    added = rule()
    added["apply"]["fields"] = [
        {
            "name": "manufacturer.acme.operator",
            "tags": ["EXIF:Artist"],
            "value_type": "string",
            "description": "Operator label",
        },
        {
            "name": "manufacturer.acme.rating",
            "tags": ["XMP:Rating"],
            "value_type": "number",
            "description": "Dimensionless rating",
            "unit": None,
        },
    ]
    write_rules(tmp_path, [added])
    snapshot = load_knowledge(tmp_path)
    assert {"EXIF:Artist", "XMP:Rating"} <= set(snapshot.tags)
    values = observe(snapshot)
    assert values["capture_time"]["value"] == "2026-05-04T17:33:46+08:00"
    assert values["manufacturer.acme.operator"]["value"] == "operator"
    assert values["manufacturer.acme.rating"]["value"] == 0.5
    trace = values["capture_time"]["provenance"]["manufacturer_knowledge"]
    applied = [entry for entry in trace["rules"] if entry["status"] == "applied"]
    assert [entry["id"] for entry in applied] == ["acme.photo"]
    assert applied[0]["conditions"][0]["raw_value"] == "ACME"
    assert applied[0]["origin"]["layer"] == "user"


@pytest.mark.parametrize(
    "make,model,mime,expected",
    [
        ("DJI", "FC220", "image/jpeg", "17:33:46"),
        ("DJI", "FC220", "video/mp4", "09:33:46"),
        ("Canon", "EOS 80D", "image/jpeg", "17:33:46"),
        ("Canon", "PowerShot", "image/jpeg", "09:33:46"),
    ],
)
def test_legacy_conditional_time_preferences_are_preserved(make, model, mime, expected):
    result = observe(
        fields={
            "EXIF:Make": make,
            "EXIF:Model": model,
            "File:MIMEType": mime,
            "EXIF:DateTimeOriginal": "2026:05:04 17:33:46",
            "XMP:DateTimeOriginal": "2026:05:04 09:33:46",
        }
    )["capture_time"]
    assert result["value"] == f"2026-05-04T{expected}+08:00"
    assert len(result["provenance"]["candidates"]) == 2


def test_missing_condition_is_unknown_and_explicit_nonmatch_is_not_unknown():
    result = observe(
        fields={"EXIF:Make": "DJI", "EXIF:DateTimeOriginal": "2026:05:04 17:33:46"}
    )["capture_time"]
    trace = result["provenance"]["manufacturer_knowledge"]["rules"]
    assert (
        next(item for item in trace if item["id"] == "dji.photo-time")["status"]
        == "unknown"
    )
    assert (
        next(item for item in trace if item["id"] == "canon.dslr-photo-time")["status"]
        == "not_matched"
    )
    assert "manufacturer_rule_applicability_unknown" in {
        q["code"] for q in result["qualifications"]
    }


def test_same_priority_conflicts_are_local_and_explicit_priority_resolves(tmp_path):
    write_rules(tmp_path, [rule("acme.a"), rule("acme.b", shift=3600)])
    values = observe(load_knowledge(tmp_path))
    assert values["capture_time"]["status"] == "failed"
    assert "value" not in values["capture_time"]
    assert values["capture_time"]["basis"]["code"] == "manufacturer_rule_conflict"
    assert values["camera_make"]["value"] == "ACME"
    write_rules(tmp_path, [rule("acme.a"), rule("acme.b", shift=3600, priority=1)])
    capture = observe(load_knowledge(tmp_path))["capture_time"]
    assert capture["value"] == "2026-05-04T18:33:46+08:00"
    assert {
        item["status"]
        for item in capture["provenance"]["manufacturer_knowledge"]["rules"]
        if item["id"].startswith("acme.")
    } == {"applied", "shadowed"}


def test_explicit_offsets_source_zone_and_output_zone_have_distinct_meanings(tmp_path):
    write_rules(tmp_path, [rule()])
    snapshot = load_knowledge(tmp_path)
    result = observe(
        snapshot,
        fields={"EXIF:Make": "ACME", "EXIF:DateTimeOriginal": "2026:05:04 17:33:46"},
        assumed_timezone="Asia/Tokyo",
        timezone="UTC",
    )["capture_time"]
    assert result["value"] == "2026-05-04T08:33:46+00:00"
    explicit = observe(
        snapshot,
        fields={
            "EXIF:Make": "ACME",
            "EXIF:DateTimeOriginal": "2026:05:04 17:33:46",
            "EXIF:OffsetTimeOriginal": "+02:00",
        },
        assumed_timezone="Asia/Tokyo",
        timezone="UTC",
    )["capture_time"]
    assert explicit["value"] == "2026-05-04T15:33:46+00:00"
    assert explicit["provenance"]["timezone_assumed"] is False


def test_disabled_fallback_retains_rejected_raw_candidate(tmp_path):
    definition = rule()
    definition["apply"]["capture_time"]["fallback"] = False
    write_rules(tmp_path, [definition])
    result = observe(
        load_knowledge(tmp_path),
        fields={"EXIF:Make": "ACME", "XMP:DateTimeOriginal": "2026:05:04 09:33:46"},
    )["capture_time"]
    assert result["status"] == "missing"
    assert result["provenance"]["candidates"][0]["raw_value"] == "2026:05:04 09:33:46"
    assert (
        result["provenance"]["candidates"][0]["rejection"]
        == "manufacturer_fallback_disabled"
    )


def test_replace_disable_and_remove_override_do_not_change_bundled_bytes(tmp_path):
    original = builtin_knowledge().content
    replacement = rule("dji.photo-time", make="DJI", shift=3600)
    replacement["operation"] = "replace"
    path = write_rules(tmp_path, [replacement])
    fields = {
        "EXIF:Make": "DJI",
        "File:MIMEType": "image/jpeg",
        "EXIF:DateTimeOriginal": "2026:05:04 17:33:46",
        "XMP:DateTimeOriginal": "2026:05:04 09:33:46",
    }
    snapshot = load_knowledge(tmp_path)
    assert (
        observe(snapshot, fields)["capture_time"]["value"]
        == "2026-05-04T18:33:46+08:00"
    )
    write_rules(
        tmp_path,
        [
            {
                "id": "dji.photo-time",
                "operation": "disable",
                "reason": "synthetic opt out",
            }
        ],
    )
    disabled = load_knowledge(tmp_path)
    assert disabled.summary()["disabled_rules"][0]["id"] == "dji.photo-time"
    assert (
        observe(disabled, fields)["capture_time"]["value"]
        == "2026-05-04T09:33:46+08:00"
    )
    path.unlink()
    assert load_knowledge(tmp_path).content == original
    assert (
        observe(KnowledgeSnapshot.from_value(snapshot.value()), fields)["capture_time"][
            "value"
        ]
        == "2026-05-04T18:33:46+08:00"
    )


def test_equivalent_effect_defaults_do_not_create_a_conflict(tmp_path):
    first, second = rule("acme.a", shift=0), rule("acme.b", shift=0.0)
    field = {
        "name": "manufacturer.acme.rating",
        "tags": ["XMP:Rating"],
        "value_type": "number",
        "description": "Rating",
    }
    first["apply"]["fields"] = [field]
    second["apply"]["fields"] = [{**deepcopy(field), "unit": None, "fallback": True}]
    write_rules(tmp_path, [first, second])
    snapshot = load_knowledge(tmp_path)
    values = observe(snapshot)
    assert values["capture_time"]["status"] == "available"
    assert values["manufacturer.acme.rating"]["value"] == 0.5
    invalid = observe(snapshot, fields={"EXIF:Make": "ACME", "XMP:Rating": "1e10000"})
    assert invalid["manufacturer.acme.rating"]["status"] == "missing"
    assert (
        invalid["manufacturer.acme.rating"]["basis"]["code"] == "invalid_metadata_value"
    )


@pytest.mark.parametrize(
    ("shift", "stamp"),
    [
        (1e100, "2026:05:04 17:33:46"),
        (-1e100, "2026:05:04 17:33:46"),
        (10**400, "2026:05:04 17:33:46"),
        (3600, "9999:12:31 23:30:00"),
        (-3600, "0001:01:01 00:30:00"),
    ],
)
def test_time_correction_out_of_range_is_local_and_retains_fallback(tmp_path, shift, stamp):
    correction = rule(shift=shift)
    correction["apply"]["capture_time"]["fallback"] = False
    write_rules(tmp_path, [correction])
    fields = {
        "EXIF:Make": "ACME",
        "EXIF:Model": "C1",
        "EXIF:DateTimeOriginal": stamp,
        "XMP:DateTimeOriginal": "2026:05:04 09:33:46+00:00",
    }
    values = observe(
        load_knowledge(tmp_path), fields, timezone="UTC", assumed_timezone="UTC"
    )
    assert values["capture_time"]["status"] == "failed"
    assert values["camera_model"]["value"] == "C1"
    candidate = values["capture_time"]["provenance"]["candidates"][0]
    assert candidate["raw_value"] == stamp and candidate["value"] is None
    assert candidate["invalid_reason"] == "manufacturer_clock_correction_out_of_range"

    correction["apply"]["capture_time"]["fallback"] = True
    write_rules(tmp_path, [correction])
    captured = observe(
        load_knowledge(tmp_path), fields, timezone="UTC", assumed_timezone="UTC"
    )["capture_time"]
    assert captured["value"] == "2026-05-04T09:33:46+00:00"
    assert captured["provenance"]["candidates"][0] == candidate


def test_override_summary_keeps_user_and_replaced_builtin_origins(tmp_path):
    replacement = rule("dji.photo-time", make="DJI")
    replacement["operation"] = "replace"
    write_rules(tmp_path, [replacement])
    item = load_knowledge(tmp_path).summary()["overridden_rules"][0]
    assert item["id"] == "dji.photo-time"
    assert item["origin"]["layer"] == "user"
    assert item["replaces"]["layer"] == "builtin"


def test_run_snapshot_survives_live_edits_and_legacy_run_does_not_adopt_new_rules(
    tmp_path,
):
    path = write_rules(tmp_path, [rule()])
    config = PrecheckExecutionConfig(
        metadata_profile=MetadataProfile(knowledge=load_knowledge(tmp_path))
    )
    frozen = config.value()
    path.unlink()
    restored = PrecheckExecutionConfig.from_value(frozen)
    assert (
        restored.metadata_profile.knowledge.content
        == config.metadata_profile.knowledge.content
    )
    legacy = deepcopy(frozen)
    legacy["version"] = 6
    legacy.pop("metadata_profile")
    assert (
        PrecheckExecutionConfig.from_value(legacy).metadata_profile.knowledge.entries
        == []
    )


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(operation="unknown"),
        lambda r: r.update(unrecognized=True),
        lambda r: r["when"][0].update(pattern="["),
        lambda r: r["when"][0].update(tags=["-execute"]),
        lambda r: r.update(operation="replace", id="absent"),
        lambda r: r.update(id="dji.photo-time"),
        lambda r: r["apply"].update(execute="anything"),
    ],
)
def test_invalid_knowledge_is_rejected_without_builtin_fallback(tmp_path, change):
    item = rule()
    change(item)
    write_rules(tmp_path, [item])
    with pytest.raises(ConfigurationError):
        load_runtime_config(user_config=tmp_path / "config.toml")


@pytest.mark.parametrize(
    "content",
    [
        "schema_version: 1\nschema_version: 1\nrules: []\n",
        "schema_version: 1\nrules: &r []\n",
        "schema_version: 1\nrules: !!python/object:object {}\n",
        "schema_version: 2\nrules: []\n",
    ],
)
def test_yaml_contract_refuses_ambiguous_documents(tmp_path, content):
    path = write_rules(tmp_path, [])
    path.write_text(content)
    with pytest.raises(KnowledgeError):
        load_knowledge(tmp_path)


def test_duplicate_ids_and_changed_extension_meaning_are_rejected(tmp_path):
    write_rules(tmp_path, [rule()], "a.yaml")
    write_rules(tmp_path, [rule()], "b.yaml")
    with pytest.raises(KnowledgeError, match="duplicate user"):
        load_knowledge(tmp_path)
    first, second = rule("acme.a"), rule("acme.b")
    first["apply"] = {
        "fields": [
            {
                "name": "manufacturer.acme.label",
                "tags": ["EXIF:Artist"],
                "value_type": "string",
                "description": "A label",
            }
        ]
    }
    second["apply"] = deepcopy(first["apply"])
    second["apply"]["fields"][0]["value_type"] = "number"
    write_rules(tmp_path, [first], "a.yaml")
    write_rules(tmp_path, [second], "b.yaml")
    with pytest.raises(KnowledgeError, match="conflicting field meaning"):
        load_knowledge(tmp_path)


def test_dataset_metadata_context_overrides_keys_without_own_knowledge_home(tmp_path):
    user = tmp_path / "user"
    user.mkdir()
    (user / "config.toml").write_text(
        '[metadata]\nassumed_timezone="Asia/Tokyo"\noutput_timezone="UTC"\n'
    )
    write_rules(user, [rule()])
    workspace = tmp_path / "dataset"
    workspace.mkdir()
    (workspace / "config.toml").write_text(
        '[metadata]\noutput_timezone="Asia/Shanghai"\n'
    )
    write_rules(workspace, [rule("dataset.should-not-be-read")])
    config = load_runtime_config(
        user_config=user / "config.toml", dataset_workspace=workspace
    )
    assert config.metadata == {
        "assumed_timezone": "Asia/Tokyo",
        "output_timezone": "Asia/Shanghai",
    }
    assert "acme.photo" in config.manufacturer_knowledge.summary()["active_rules"]
    assert (
        "dataset.should-not-be-read"
        not in config.manufacturer_knowledge.summary()["active_rules"]
    )
    assert (
        config.public_value()["metadata"]["manufacturer_knowledge"]["execution"]
        == "not_checked"
    )


def test_sony_associated_xml_and_dji_native_encoder_have_explicit_basis():
    source, sidecar = Path("clip.mp4"), Path("clip.xml")
    values = select_metadata_observations(
        [
            {"relative_path": str(source), "fields": {"File:MIMEType": "video/mp4"}},
            {
                "relative_path": str(sidecar),
                "fields": {
                    "XML:DeviceManufacturer": "Sony",
                    "XML:DeviceModelName": "FX3",
                    "XML:LensModelName": "50mm",
                },
            },
        ],
        subject=source,
        source_precedence=(sidecar, source),
    )
    model = next(value for value in values if value["name"] == "camera_model")
    assert model["value"] == "FX3"
    assert model["provenance"]["relative_path"] == "clip.xml"
    assert any(
        rule["status"] == "applied"
        for rule in model["provenance"]["manufacturer_knowledge"]["rules"]
    )
    native = observe(
        fields={"File:MIMEType": "video/mp4", "QuickTime:Encoder": "DJI Pocket 3"}
    )["camera_model"]
    remux = observe(
        fields={"File:MIMEType": "video/mp4", "QuickTime:Encoder": "Lavf-test"}
    )["camera_model"]
    assert native["value"] == "DJI Pocket 3"
    assert remux["status"] == "missing"


@pytest.mark.parametrize("remove_file", [False, True])
def test_reopened_host_resumes_frozen_knowledge_after_live_change(
    tmp_path, monkeypatch, remove_file
):
    import json
    import sqlite3
    import time
    from PIL import Image
    from mediasense.runtime.host import RuntimeHost

    user = tmp_path / "config"
    path = write_rules(user, [rule(shift=3600)])
    monkeypatch.setenv("MEDIASENSE_CONFIG_HOME", str(user))
    monkeypatch.delenv("AMAP_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    source, workspace = tmp_path / "source", tmp_path / "dataset"
    source.mkdir()
    exif = Image.Exif()
    exif[271] = "ACME"
    exif[36867] = "2026:05:04 17:33:46"
    Image.new("RGB", (80, 40), "blue").save(source / "photo.jpg", exif=exif)
    before = (source / "photo.jpg").read_bytes()
    first = RuntimeHost()
    opened = first.open_dataset(str(source), str(workspace))
    dataset = opened["dataset_ref"]

    def call(host, tool, action, **arguments):
        return host.call_tool(
            "mediasense.precheck." + tool,
            dataset_ref=dataset,
            request={"dataset_ref": dataset, "action": action, **arguments},
        )

    def wait(host, ref):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            status = call(host, "run", "status", run_ref=ref)
            if status["state"] != "running":
                return status
            time.sleep(0.02)
        pytest.fail("PreCheck did not reach an observable boundary")

    ref = call(first, "run", "start", request_id="manufacturer:restart")["run_ref"]
    paused = wait(first, ref)
    assert paused["state"] == "paused", paused
    runtime = first._datasets[dataset]
    with runtime._worker_lock:
        workers = list(runtime._workers.values())
    for worker in workers:
        worker.join(timeout=3)
        assert not worker.is_alive()
    database = workspace / "precheck/work.sqlite3"
    with sqlite3.connect(database) as connection:
        frozen = connection.execute(
            "SELECT execution_config_json FROM precheck_runs WHERE run_ref=?", (ref,)
        ).fetchone()[0]
    assert json.loads(frozen)["metadata_profile"]["manufacturer_knowledge"]
    if remove_file:
        path.unlink()
    else:
        write_rules(user, [rule(shift=7200)])
    reopened = RuntimeHost()
    assert reopened.open_dataset(str(source), str(workspace))["dataset_ref"] == dataset
    resumed = call(
        reopened,
        "run",
        "resume",
        run_ref=ref,
        decision={
            "kind": "source_scope",
            "inventory_fingerprint": paused["confirmation"]["inventory_fingerprint"],
            "default_disposition": "include",
            "exceptions": [],
        },
    )
    assert "error" not in resumed, resumed
    final = wait(reopened, ref)
    assert final["state"] == "completed", final
    page = call(reopened, "read", "review", result_ref=final["result"]["ref"])
    capture = next(
        observation
        for item in page["items"]
        for actual in item["source_items"]
        for observation in actual["observations"]
        if observation["name"] == "capture_time"
    )
    assert capture["value"] == "2026-05-04T18:33:46+08:00"
    with sqlite3.connect(database) as connection:
        assert (
            connection.execute(
                "SELECT execution_config_json FROM precheck_runs WHERE run_ref=?",
                (ref,),
            ).fetchone()[0]
            == frozen
        )
    assert (source / "photo.jpg").read_bytes() == before
