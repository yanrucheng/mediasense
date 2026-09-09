"""Reacceptance regressions at the sealed Result and public Reader boundary."""

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess

import pytest

from mediasense.precheck import MetadataProducer, PrecheckReadTool
from test_precheck_delivery import prepared
from test_precheck_read_contract import check_semantics


LIMIT = 524288


def encoded_size(value):
    return len(
        json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()
    )


def request_for(sealed, **values):
    return {
        "action": "review",
        "dataset_ref": "dataset:delivery",
        "result_ref": sealed.result_ref,
        **values,
    }


def test_metadata_rejected_values_survive_producer_result_and_read(tmp_path):
    database, store, initial, renditions = prepared(tmp_path)

    def exiftool(command):
        paths = command[command.index("--") + 1 :]
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps(
                [
                    {
                        "SourceFile": path,
                        "QuickTime:Encoder": "Lavf-controlled",
                        "EXIF:FocalLength": -7,
                        "File:MIMEType": "image/jpeg",
                    }
                    for path in paths
                ]
            ),
            "",
        )

    metadata = MetadataProducer(
        database, command_runner=exiftool, exiftool_version="controlled"
    ).produce(initial.run_id, Path("0.jpg"))
    original = deepcopy(metadata.work.output)
    producer_observations = {o["name"]: o for o in original["observations"]}
    assert (
        producer_observations["camera_model"]["basis"]["candidates"][0]["rejection"]
        == "encoder_is_not_camera_identity"
    )
    assert (
        producer_observations["focal_length_mm"]["basis"]["candidates"][0]["raw_value"]
        == -7
    )
    draft = store.build_minimal(
        initial.run_id,
        [o.work.work_id for o in renditions],
        metadata_work_ids=[metadata.work.work_id],
    )
    sealed = store.seal(draft)
    reader = PrecheckReadTool(database)
    request = request_for(sealed)
    response = reader.read(request)
    check_semantics(request, response)
    source = next(
        source
        for item in response["items"]
        for source in item["source_items"]
        if source["locator"]["value"] == "0.jpg"
    )
    observations = {o["name"]: o for o in source["observations"]}
    for name in ("camera_model", "focal_length_mm"):
        observation = observations[name]
        expected = deepcopy(producer_observations[name]["basis"])
        for candidate in expected["candidates"]:
            assert candidate.pop("relative_path") == "0.jpg"
            candidate["source_item_ref"] = source["source_item_ref"]
        assert observation["basis"] == expected
        assert observation["status"] == "missing" and "value" not in observation
        assert observation["provenance"]["producer"]["exiftool_version"] == "controlled"
    expanded = reader.read(
        {
            **request,
            "action": "expand",
            "source_item_refs": [source["source_item_ref"]],
            "include": ["observations"],
        }
    )
    assert expanded["items"][0]["included"]["observations"] == source["observations"]
    assert metadata.work.output == original


@pytest.mark.parametrize("size", [LIMIT - 10, LIMIT - 1, LIMIT, LIMIT + 1])
@pytest.mark.parametrize(
    "selection_size,page_limit", [(1, 1), (2, 1), (2, 2), (3, 2), (3, 3)]
)
def test_review_byte_boundary_uses_only_actual_page_fields(
    tmp_path, size, selection_size, page_limit
):
    database, store, draft, _ = prepared(tmp_path)
    refs = sorted(draft.entry_evidence)[:selection_size]
    index = next(
        i for i, evidence in enumerate(draft.evidence) if evidence.ref == refs[0]
    )
    anchor = draft.evidence[index]
    payload = {"name": "retained_text", "status": "available", "value": ""}

    def with_text(text):
        evidence = list(draft.evidence)
        evidence[index] = replace(
            anchor, observations=(*anchor.observations, {**payload, "value": text})
        )
        return replace(draft, evidence=tuple(evidence))

    reader = PrecheckReadTool(database)
    warm = store.seal(with_text(""))
    request = request_for(warm, evidence_refs=refs, page={"limit": page_limit})
    expected = reader.read(request)
    assert "stop_reason" not in expected["page"]
    padding = "x" * (size - encoded_size(expected))
    sealed = store.seal(with_text(padding))
    expected["result"]["ref"] = sealed.result_ref
    expected["items"][0]["observations"][-1]["value"] = padding
    assert encoded_size(expected) == size
    request["result_ref"] = sealed.result_ref
    response = reader.read(request)
    check_semantics(request, response)
    if size <= LIMIT:
        assert len(response["items"]) == min(selection_size, page_limit)
        assert all("error" not in item for item in response["items"]), response.get(
            "page"
        )
        assert "stop_reason" not in response["page"]
        assert encoded_size(response) == size
    elif min(selection_size, page_limit) == 1:
        assert response["items"][0]["error"]["code"] == "response_item_too_large"
    else:
        assert response["page"]["stop_reason"] == "byte_limit"
        assert all("error" not in item for item in response["items"])
    seen = [item["evidence_ref"] for item in response["items"]]
    while response["page"]["next_cursor"]:
        request["page"]["cursor"] = response["page"]["next_cursor"]
        response = reader.read(request)
        check_semantics(request, response)
        seen.extend(item["evidence_ref"] for item in response["items"])
    assert seen == refs


def middle_page_case(
    store, draft, reader, dataset_ref, single_page_size, *, explicit=False
):
    """Size the middle item using the public response's real outgoing cursor."""
    refs = sorted(draft.entry_evidence) if explicit else list(draft.entry_evidence)
    index = next(i for i, item in enumerate(draft.evidence) if item.ref == refs[1])
    anchor = draft.evidence[index]

    def padded(text):
        evidence = list(draft.evidence)
        evidence[index] = replace(
            anchor,
            observations=(
                *anchor.observations,
                {
                    "name": "retained_text",
                    "status": "available",
                    "value": text,
                },
            ),
        )
        return replace(draft, evidence=tuple(evidence))

    warm = store.seal(padded(""))
    request = {
        "action": "review",
        "dataset_ref": dataset_ref,
        "result_ref": warm.result_ref,
        "page": {"limit": 2},
    }
    if explicit:
        request["evidence_refs"] = refs
    hypothetical = deepcopy(reader.read(request))
    assert [item["evidence_ref"] for item in hypothetical["items"]] == refs[:2]
    assert "stop_reason" not in hypothetical["page"]
    # The outgoing cursor already points after the middle item and binds limit=2.
    hypothetical["items"] = [hypothetical["items"][1]]
    padding = "x" * (single_page_size - encoded_size(hypothetical))
    sealed = store.seal(padded(padding))
    hypothetical["items"][0]["observations"][-1]["value"] = padding
    hypothetical["result"]["ref"] = sealed.result_ref
    assert encoded_size(hypothetical) == single_page_size
    request["result_ref"] = sealed.result_ref
    return sealed, refs, request


@pytest.mark.parametrize(
    "single_page_size", [LIMIT - 28, LIMIT - 27, LIMIT - 26, LIMIT - 10]
)
@pytest.mark.parametrize("explicit", [False, True])
def test_near_limit_middle_item_never_blocks_unchanged_cursor_continuation(
    tmp_path, single_page_size, explicit
):
    database, store, draft, _ = prepared(tmp_path)
    reader = PrecheckReadTool(database)
    sealed, refs, request = middle_page_case(
        store, draft, reader, "dataset:delivery", single_page_size, explicit=explicit
    )
    sealed_bytes = sealed.path.read_bytes()
    pages, cursors = [], set()
    while True:
        response = reader.read(request)
        assert "error" not in response, response
        check_semantics(request, response)
        assert response["page"]["total"] == 3
        assert encoded_size(response) <= LIMIT
        pages.append(response)
        cursor = response["page"]["next_cursor"]
        if cursor is None:
            break
        assert cursor not in cursors
        cursors.add(cursor)
        request["page"]["cursor"] = cursor
        assert request["page"]["limit"] == 2
    assert [item["evidence_ref"] for item in pages[0]["items"]] == [refs[0]]
    assert pages[0]["page"]["stop_reason"] == "byte_limit"
    items = [item for page in pages for item in page["items"]]
    assert [item["evidence_ref"] for item in items] == refs
    assert "error" not in items[0] and "error" not in items[2]
    if single_page_size + 27 <= LIMIT:
        assert "error" not in items[1]
        assert pages[1]["page"]["stop_reason"] == "byte_limit"
        assert encoded_size(pages[1]) == single_page_size + 27
    else:
        assert items[1]["error"]["code"] == "response_item_too_large"
        assert len(pages) == 2
        assert [item["evidence_ref"] for item in pages[1]["items"]] == refs[1:]
    assert all(page["accounting"] == pages[0]["accounting"] for page in pages)
    assert sealed.path.read_bytes() == sealed_bytes


def test_later_large_item_is_judged_in_its_own_actual_page(tmp_path):
    database, store, draft, renditions = prepared(tmp_path)
    reader = PrecheckReadTool(database)
    sealed, refs, request = middle_page_case(
        store, draft, reader, "dataset:delivery", LIMIT + 1
    )
    # A short final fault can share the last page with the large middle item:
    # that page has no cursor or stop marker. Do not fail the middle item while
    # deciding how many items fit on the preceding page.
    renditions[2].artifact.path.unlink()
    first = reader.read(request)
    check_semantics(request, first)
    assert [item["evidence_ref"] for item in first["items"]] == refs[:1]
    second_request = {
        **request,
        "page": {"limit": 2, "cursor": first["page"]["next_cursor"]},
    }
    second = reader.read(second_request)
    check_semantics(second_request, second)
    assert [item["evidence_ref"] for item in second["items"]] == refs[1:]
    assert "error" not in second["items"][0]
    assert second["items"][1]["error"]["code"] == "evidence_unavailable"
    assert second["page"]["next_cursor"] is None
    assert "stop_reason" not in second["page"]
    assert encoded_size(second) <= LIMIT


def legacy_observation(
    detector, input_id, score, *, status="available", profile="historical-test-v1"
):
    observation = {
        "name": "content_sensitivity",
        "status": status,
        "basis": {"summary": "Original detector input record", "recorded_score": score},
        "provenance": {
            "input_work_id": input_id,
            "detector_identity": detector,
            "profile": profile,
            "observed_at": "2026-08-01T10:00:00+00:00",
        },
        "qualifications": [
            {
                "code": "sample_only",
                "effect": "limits_interpretation",
                "message": "Only this original sample was checked.",
            }
        ],
    }
    if status == "available":
        observation["value"] = {
            "detector_identity": detector,
            "profile": profile,
            "labels": [{"label": "test", "score": score}],
        }
    return observation


def seed_legacy_result(database, store, draft, observations):
    """Construct a synthetic v1 sealed fixture; never touch a retained user Result."""
    sealed = store.seal(draft)
    package = json.loads(sealed.path.read_bytes())
    package["schema_version"] = 1
    source = next(
        record["view"]
        for record in package["sources"]
        if record["view"]["locator"]["value"] == "0.jpg"
    )
    source["observations"] = observations
    encoded = json.dumps(package, ensure_ascii=False, separators=(",", ":")).encode()
    sealed.path.chmod(0o600)
    sealed.path.write_bytes(encoded)
    sealed.path.chmod(0o444)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sealed_results SET digest = ?, size_bytes = ? WHERE result_ref = ?",
            (hashlib.sha256(encoded).hexdigest(), len(encoded), sealed.result_ref),
        )
    return sealed, encoded


@pytest.mark.parametrize(
    "detectors", [("detector-a", "detector-b"), ("detector-a", "detector-a")]
)
def test_legacy_missing_inputs_keep_each_detection_readable(tmp_path, detectors):
    database, store, draft, renditions = prepared(tmp_path)
    old = [
        legacy_observation(detectors[0], "old-frame-1", 0.1),
        legacy_observation(
            detectors[1],
            "old-frame-2",
            0.2,
            status="failed",
            profile="historical-test-v2",
        ),
        legacy_observation(detectors[0], "old-frame-3", 0.3),
        legacy_observation(detectors[0], renditions[0].work.work_id, 0.4),
    ]
    old[0]["provenance"].pop(
        "detector_identity"
    )  # Identity is still proven by its value.
    sealed, encoded = seed_legacy_result(database, store, draft, old)
    reader = PrecheckReadTool(database)
    request = request_for(sealed)
    response = reader.read(request)
    assert "error" not in response, response
    check_semantics(request, response)
    source = next(
        source
        for item in response["items"]
        for source in item["source_items"]
        if source["locator"]["value"] == "0.jpg"
    )
    observations = [
        o for o in source["observations"] if o["name"] == "content_sensitivity"
    ]
    available = [o for o in observations if o["status"] == "available"]
    assert len(available) == 1
    assert available[0]["provenance"]["input_evidence_ref"] == draft.evidence[0].ref
    gaps = [o for o in observations if o["status"] == "not_checked"]
    assert {o["provenance"]["detector_identity"] for o in gaps} == set(detectors)
    retained = [record for o in gaps for record in o["basis"]["retained_observations"]]
    assert sorted(record["basis"]["recorded_score"] for record in retained) == [
        0.1,
        0.2,
        0.3,
    ]
    assert sorted(record["status"] for record in retained) == [
        "available",
        "available",
        "failed",
    ]
    assert all(
        record["qualifications"] == old[0]["qualifications"] for record in retained
    )
    assert all(
        record["provenance"]["observed_at"] == old[0]["provenance"]["observed_at"]
        for record in retained
    )
    assert all("input_evidence_ref" not in o["provenance"] for o in gaps)
    assert "input_work_id" not in json.dumps(response)
    assert "old-frame" not in json.dumps(response)
    assert reader.read(request) == response
    expanded = reader.read(
        {
            **request,
            "action": "expand",
            "source_item_refs": [source["source_item_ref"]],
            "include": ["observations"],
        }
    )
    check_semantics({**request, "action": "expand"}, expanded)
    assert expanded["items"][0]["included"]["observations"] == source["observations"]
    assert sealed.path.read_bytes() == encoded


def test_legacy_duplicate_proven_detection_still_refuses_invalid_result(tmp_path):
    database, store, draft, renditions = prepared(tmp_path)
    observation = legacy_observation("detector-a", renditions[0].work.work_id, 0.4)
    sealed, _ = seed_legacy_result(
        database, store, draft, [observation, deepcopy(observation)]
    )
    response = PrecheckReadTool(database).read(request_for(sealed))
    assert response["error"]["code"] == "result_untrusted"
