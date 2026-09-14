from __future__ import annotations

from dataclasses import replace
import errno
import json
import os
from pathlib import Path
import sqlite3

from jsonschema import Draft202012Validator
from PIL import Image
import pytest

import mediasense.precheck.read as precheck_read_module
from mediasense.precheck import (
    AccountingStore,
    HIGH_RESOLUTION_RENDITION_PROFILE,
    ImageRenditionProducer,
    ORDINARY_RENDITION_PROFILE,
    PrecheckReadTool,
    ResultEvidence,
    ResultRelationship,
    ResultSealError,
    ResultStore,
    WorkStatus,
)
from mediasense.precheck import discovery


SPEC_ROOT = Path(__file__).parents[1] / "docs" / "spec" / "contract/precheck-read"


def test_result_encoding_preserves_exact_canonical_bytes():
    from mediasense.precheck._result_sqlite import _encode_package

    # Non-ASCII and non-BMP content must not change identities, escaping, key
    # ordering or numeric spelling when a large Result is encoded in chunks.
    value = {"z": [None, True, 1.25, -0.0], "a": {"说明": "来源 🖼\n\\\""}}
    assert _encode_package(value) == (
        '{"a":{"说明":"来源 🖼\\n\\\\\\\""},"z":[null,true,1.25,-0.0]}'
    ).encode("utf-8")
    with pytest.raises(ValueError):
        _encode_package({"value": float("nan")})


def test_ordinary_rendition_is_frontier_and_high_resolution_expands_from_it(
    tmp_path: Path,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (2400, 1200), "blue").save(source / "photo.jpg")
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    producer = ImageRenditionProducer(database)
    ordinary = producer.produce(
        run_id, Path("photo.jpg"), profile=ORDINARY_RENDITION_PROFILE
    )
    high = producer.produce(
        run_id, Path("photo.jpg"), profile=HIGH_RESOLUTION_RENDITION_PROFILE
    )
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(run_id, [ordinary.work.work_id, high.work.work_id])
    )
    reader = PrecheckReadTool(database)

    entry = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )
    assert len(entry["items"]) == 1
    ordinary_ref = entry["items"][0]["evidence_ref"]
    expanded = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "evidence_refs": [ordinary_ref],
            "include": ["anchor_evidence", "prepared_targets"],
        }
    )
    ordinary_view = expanded["items"][0]["included"]["anchor_evidence"]
    assert ordinary_view["observations"][0]["value"]["profile"]["name"] == "ordinary"
    high_ref = next(
        item["target"]["ref"]
        for item in expanded["items"][0]["included"]["prepared_targets"]
        if isinstance(item["target"], dict) and item["target"]["kind"] == "evidence"
    )
    high_view = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "evidence_refs": [high_ref],
            "include": ["anchor_evidence"],
        }
    )["items"][0]["included"]["anchor_evidence"]
    assert high_view["observations"][0]["value"]["profile"]["name"] == "high_resolution"
    _assert_response_conforms(entry)
    _assert_response_conforms(expanded)


def _prepared(tmp_path: Path):
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    source.mkdir()
    Image.new("RGB", (100, 50), "blue").save(source / "first.jpg")
    Image.new("RGB", (60, 120), "green").save(source / "second.jpg")
    (source / "notes.txt").write_text("not visual", encoding="utf-8")
    source_before = {
        path.name: path.read_bytes() for path in source.iterdir() if path.is_file()
    }
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    accounting.process_run(run_id)
    producer = ImageRenditionProducer(database)
    first = producer.produce(run_id, Path("first.jpg"))
    second = producer.produce(run_id, Path("second.jpg"))
    return database, source, source_before, run_id, first, second


def _assert_response_conforms(response: dict[str, object]) -> None:
    schema = json.loads((SPEC_ROOT / "precheck-read.tool.json").read_text())
    Draft202012Validator(schema["outputSchema"]).validate(response)


def test_geo_summary_source_set_stays_bounded_for_high_fanout_coordinate() -> None:
    result_ref = "precheck-result:high-fanout"
    evidence_ref = "evidence:geo-high-fanout"
    coordinate = {"latitude": 22.3193, "longitude": 114.1694, "datum": "WGS84"}
    source_refs = [f"source-item:{index:05d}" for index in range(10_000)]
    graph = precheck_read_module._ResultGraph(
        {
            "result": {"kind": "result", "ref": result_ref},
            "dataset": {},
            "sources": [
                {
                    "view": {
                        "kind": "source_item",
                        "ref": source_ref,
                        "observations": [
                            {
                                "name": "gps_coordinates",
                                "status": "available",
                                "value": coordinate,
                            }
                        ],
                    }
                }
                for source_ref in source_refs
            ],
            "evidence": [
                {
                    "view": {
                        "kind": "evidence",
                        "ref": evidence_ref,
                        "observations": [
                            {
                                "name": "reverse_geocode_candidate",
                                "status": "available",
                                "value": {"formatted_address": "Hong Kong"},
                                "provenance": {"provider": "fake_maps"},
                                "qualifications": [],
                            }
                        ],
                    }
                }
            ],
            "relationships": [
                *[
                    {
                        "origin": result_ref,
                        "relation": "accounts_for",
                        "member": {"target": source_ref, "scope": "source_media"},
                    }
                    for source_ref in source_refs
                ],
                *[
                    {
                        "origin": evidence_ref,
                        "relation": "represents",
                        "member": {"target": source_ref},
                    }
                    for source_ref in source_refs
                ],
            ],
        }
    )

    projection = precheck_read_module._geo_projection(graph)
    group = projection["coordinate_groups"][0]

    assert group["member_count"] == len(source_refs)
    assert group["source_set"] == {
        "kind": "geo_coordinate",
        "coordinate": coordinate,
        "selection_rule": "gpx_over_gps_exact_normalized_v1",
    }
    assert precheck_read_module._encoded_size(group) < 512 * 1024
    assert precheck_read_module._resolve_source_set(
        graph, group["source_set"]
    ) == frozenset(source_refs)


def test_review_allows_historical_plan_ready_result_missing_per_source_geo() -> None:
    result_ref = "precheck-result:historical-incomplete-geo"
    source_ref = "source-item:located"
    graph = precheck_read_module._ResultGraph(
        {
            "result": {
                "kind": "result",
                "ref": result_ref,
                "readiness": "plan_ready",
                "coverage": "complete",
                "qualifications": [],
            },
            "dataset": {},
            "sources": [
                {
                    "view": {
                        "kind": "source_item",
                        "ref": source_ref,
                        "observations": [
                            {
                                "name": "gps_coordinates",
                                "status": "available",
                                "value": {
                                    "latitude": 22.3193,
                                    "longitude": 114.1694,
                                    "datum": "WGS84",
                                },
                            }
                        ],
                    }
                }
            ],
            "evidence": [],
            "relationships": [
                {
                    "origin": result_ref,
                    "relation": "accounts_for",
                    "member": {"target": source_ref, "scope": "source_media"},
                }
            ],
        }
    )

    view = precheck_read_module._effective_result_view(graph)

    assert view["readiness"] == "plan_ready"
    assert "qualifications" not in view


def test_end_to_end_result_is_sealed_and_read_only_through_exact_reference(
    tmp_path: Path,
) -> None:
    database, source, source_before, run_id, first, second = _prepared(tmp_path)
    results = ResultStore(database)
    draft = results.build_minimal(
        run_id,
        [first.work.work_id, second.work.work_id],
        dataset_name="Local test dataset",
    )
    sealed = results.seal(draft)
    reader = PrecheckReadTool(database)
    database_before_reads = database.read_bytes()

    inspected = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )
    first_page = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": sealed.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
            "page": {"limit": 2},
        }
    )
    second_page = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": sealed.result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
            "page": {"limit": 2, "cursor": first_page["page"]["next_cursor"]},
        }
    )

    for response in (inspected, first_page, second_page):
        _assert_response_conforms(response)
    assert inspected["result"]["coverage"] == "complete"
    assert inspected["result"]["readiness"] == "plan_ready"
    assert "source_root_ref" not in inspected["result"]
    assert first_page["page"]["next_cursor"] is not None
    assert second_page["page"]["next_cursor"] is None
    assert first_page["page"]["total"] == 3
    assert inspected["accounting"]["frontier"]["entry_evidence_count"] == 2
    member_refs = [
        item["source_item_ref"]
        for item in (*first_page["members"], *second_page["members"])
    ]
    source_views = [
        reader.read(
            {
                "dataset_ref": "dataset:dataset-a",
                "result_ref": sealed.result_ref,
                "action": "expand",
                "source_item_refs": [ref],
                "include": ["source_item", "observations"],
            }
        )["items"][0]["included"]
        for ref in member_refs
    ]
    first_source = next(
        item
        for item in source_views
        if item["source_item"]["locator"]["value"] == "first.jpg"
    )
    assert first_source["source_item"]["locator"]["kind"] == "source_root_relative_path"
    assert first_source["source_item"]["locator"]["source_root_ref"].startswith(
        "source-root:"
    )
    verification = next(
        item
        for item in first_source["observations"]
        if item["name"] == "source_content_verification"
    )
    assert verification["status"] == "available"
    assert verification["value"]["profile"] == "candidate-sha256-full-or-3x4k-v1"
    assert verification["value"]["value"].startswith("sha256:")
    assert verification["value"]["size_bytes"] == (source / "first.jpg").stat().st_size
    assert database.read_bytes() == database_before_reads
    assert {path.name: path.read_bytes() for path in source.iterdir()} == source_before
    assert (
        reader.read(
            {
                "dataset_ref": "dataset:dataset-a",
                "result_ref": "precheck-result:not-latest",
                "action": "review",
            }
        )["error"]["code"]
        == "result_not_found"
    )


def test_seal_revalidates_projected_source_content_observation(
    tmp_path: Path,
) -> None:
    database, source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    Image.new("RGB", (100, 50), "red").save(source / "first.jpg")

    with pytest.raises(ResultSealError, match="source verification failed at seal"):
        store.seal(draft)


def test_seal_rejects_source_locator_bound_to_the_wrong_root(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    source = draft.sources[0]
    invalid = replace(
        draft,
        sources=(
            replace(
                source,
                locator={
                    **source.locator,
                    "source_root_ref": "source-root:different",
                },
            ),
            *draft.sources[1:],
        ),
    )

    with pytest.raises(ResultSealError, match="Source Item root"):
        store.seal(invalid)

    assert store.audit().available == ()


def test_review_expand_and_resolve_cover_public_result_questions(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    sealed = store.seal(draft)
    reader = PrecheckReadTool(database)
    result_ref = sealed.result_ref
    entry = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": result_ref,
            "action": "review",
        }
    )
    evidence_ref = entry["items"][0]["evidence_ref"]
    represents = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": evidence_ref,
                "relation": "represents",
                "direction": "outbound",
            },
        }
    )
    source_ref = represents["members"][0]["source_item_ref"]
    reverse = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": result_ref,
            "action": "expand",
            "source_item_refs": [source_ref],
            "include": ["covering_evidence"],
        }
    )
    derived = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": result_ref,
            "action": "expand",
            "evidence_refs": [evidence_ref],
            "include": ["provenance"],
        }
    )
    expanded = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": result_ref,
            "action": "expand",
            "evidence_refs": [evidence_ref],
            "include": ["prepared_targets"],
        }
    )
    attention = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": result_ref,
                "relation": "accounts_for",
                "direction": "outbound",
            },
        }
    )

    for response in (represents, reverse, derived, expanded, attention):
        _assert_response_conforms(response)
    assert (
        reverse["items"][0]["included"]["covering_evidence"][0]["evidence_ref"]
        == evidence_ref
    )
    assert derived["items"][0]["included"]["provenance"][0]["target"] == {
        "kind": "source_item",
        "ref": source_ref,
    }
    assert expanded["items"][0]["included"]["prepared_targets"][0]["target"] == {
        "kind": "source_item",
        "ref": source_ref,
    }
    assert [item["condition"] for item in attention["members"]].count(
        "unsupported"
    ) == 1


def test_expand_and_resolve_validation_is_atomic_and_result_bound(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    )
    reader = PrecheckReadTool(database)
    review = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )
    evidence_ref = review["items"][0]["evidence_ref"]

    missing_evidence = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "evidence_refs": [evidence_ref, "evidence:not-in-result"],
            "include": ["anchor_evidence"],
        }
    )
    unknown_include = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "evidence_refs": [evidence_ref],
            "include": ["semantic_recommendation"],
        }
    )
    missing_member = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "explicit",
                "source_item_refs": ["source-item:not-in-result"],
            },
        }
    )
    malformed_set = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "explicit",
                "source_item_refs": ["source-item:a", "source-item:a"],
            },
        }
    )

    assert missing_evidence["error"]["code"] == "reference_not_in_result"
    assert "items" not in missing_evidence
    assert unknown_include["error"]["code"] == "unsupported_include"
    assert "items" not in unknown_include
    assert missing_member["error"]["code"] == "reference_not_in_result"
    assert malformed_set["error"]["code"] == "invalid_source_set"
    for response in (
        missing_evidence,
        unknown_include,
        missing_member,
        malformed_set,
    ):
        _assert_response_conforms(response)


def test_review_cursor_is_repeatable_query_bound_and_byte_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    )
    reader = PrecheckReadTool(database)
    request = {
        "dataset_ref": "dataset:dataset-a",
        "result_ref": sealed.result_ref,
        "action": "review",
        "page": {"limit": 1},
    }

    first_page = reader.read(request)
    assert reader.read(request) == first_page
    cursor = first_page["page"]["next_cursor"]
    second_page = reader.read(
        {
            **request,
            "page": {"limit": 1, "cursor": cursor},
        }
    )
    wrong_limit = reader.read(
        {
            **request,
            "page": {"limit": 2, "cursor": cursor},
        }
    )
    assert second_page["page"]["next_cursor"] is None
    assert wrong_limit["error"]["code"] == "invalid_cursor"

    complete = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
            "page": {"limit": 2},
        }
    )
    complete_size = len(
        json.dumps(complete, ensure_ascii=False, separators=(",", ":")).encode()
    )
    monkeypatch.setattr(precheck_read_module, "_MAX_RESPONSE_BYTES", complete_size - 1)
    bounded = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
            "page": {"limit": 2},
        }
    )
    assert len(bounded["items"]) == 1
    assert bounded["page"]["stop_reason"] == "byte_limit"
    assert len(
        json.dumps(bounded, ensure_ascii=False, separators=(",", ":")).encode()
    ) <= (complete_size - 1)

    monkeypatch.setattr(precheck_read_module, "_MAX_RESPONSE_BYTES", 1)
    oversized = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
            "page": {"limit": 1},
        }
    )
    assert oversized["error"]["code"] == "response_item_too_large"


def test_frontier_model_supports_many_to_one_and_one_to_many(tmp_path: Path) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    first_source, second_source = draft.sources[:2]
    first_evidence = draft.evidence[0]
    extra_evidence = ResultEvidence(
        ref="evidence:inline-detail",
        access={"kind": "inline", "value": {"detail": "alternate crop"}},
    )
    relationships = draft.relationships + (
        ResultRelationship(
            origin_ref=first_evidence.ref,
            relation="represents",
            target_ref=second_source.ref,
            target_kind="source_item",
            basis="explicit test grouping candidate",
        ),
        ResultRelationship(
            origin_ref=extra_evidence.ref,
            relation="represents",
            target_ref=first_source.ref,
            target_kind="source_item",
            basis="explicit alternate evidence",
        ),
        ResultRelationship(
            origin_ref=extra_evidence.ref,
            relation="derived_from",
            target_ref=first_source.ref,
            target_kind="source_item",
            basis="inline test derivation",
        ),
    )
    draft = replace(
        draft,
        evidence=draft.evidence + (extra_evidence,),
        entry_evidence=draft.entry_evidence + (extra_evidence.ref,),
        relationships=relationships,
    )

    sealed = store.seal(draft)
    reader = PrecheckReadTool(database)
    many = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "resolve",
            "source_set": {
                "kind": "precheck_relation",
                "origin": first_evidence.ref,
                "relation": "represents",
                "direction": "outbound",
            },
        }
    )
    one_to_many = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "expand",
            "source_item_refs": [first_source.ref],
            "include": ["covering_evidence"],
        }
    )

    assert len(many["members"]) == 2
    assert len(one_to_many["items"][0]["included"]["covering_evidence"]) == 2


def test_seal_rejects_navigation_gap_and_does_not_publish_partial_result(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, _second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id])
    usable = next(source for source in draft.sources if source.condition == "usable")
    broken = replace(
        draft,
        relationships=tuple(
            relation
            for relation in draft.relationships
            if not (
                relation.relation in {"represents", "expands_to"}
                and relation.target_ref == usable.ref
            )
        ),
    )

    with pytest.raises(ResultSealError, match="navigation path"):
        store.seal(broken)
    assert store.audit().available == ()


def test_unprocessed_source_media_blocks_minimal_result_readiness(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, _second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id])

    assert draft.readiness == "blocked"
    assert draft.qualifications[0]["code"] == "unresolved_source_media"


def test_interrupted_seal_leaves_an_unpublished_orphan_not_a_result(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)

    class CrashingResultStore(ResultStore):
        def _after_file_published(self, path: Path) -> None:
            raise RuntimeError("simulated seal interruption")

    store = CrashingResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    with pytest.raises(RuntimeError, match="simulated seal interruption"):
        store.seal(draft)

    audit = store.audit()
    assert audit.available == ()
    assert len(audit.orphan_paths) == 1


def test_interrupted_seal_refuses_a_semantically_different_retry(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)

    class CrashingResultStore(ResultStore):
        def _after_file_published(self, path: Path) -> None:
            raise RuntimeError("simulated seal interruption")

    result_ref = "precheck-result:" + "a" * 32
    store = CrashingResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    with pytest.raises(RuntimeError, match="simulated seal interruption"):
        store.seal(draft, result_ref=result_ref)

    with pytest.raises(ResultSealError, match="different content"):
        ResultStore(database).seal(
            replace(draft, dataset_name="different"), result_ref=result_ref
        )


def test_disk_full_during_seal_leaves_only_detectable_unpublished_bytes(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)

    class DiskFullResultStore(ResultStore):
        def _write_unpublished_result(self, path: Path, encoded: bytes) -> None:
            path.write_bytes(encoded[:17])
            raise OSError(errno.ENOSPC, "simulated disk full")

    store = DiskFullResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    with pytest.raises(OSError) as raised:
        store.seal(draft)

    assert raised.value.errno == errno.ENOSPC
    audit = store.audit()
    assert audit.available == ()
    assert audit.orphan_paths == ()
    assert len(audit.unpublished_paths) == 1


def test_sealed_result_bytes_never_change_and_corruption_is_refused(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    )
    original = sealed.path.read_bytes()
    reader = PrecheckReadTool(database)
    assert "error" not in reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )

    sealed.path.chmod(0o644)
    sealed.path.write_bytes(b"corrupt")
    response = reader.read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )

    assert response["error"]["code"] == "result_untrusted"
    assert original != sealed.path.read_bytes()


def test_unenumerated_discovery_issue_forces_partial_coverage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = tmp_path / "workspace" / "working.sqlite3"
    source = tmp_path / "source"
    blocked = source / "blocked"
    blocked.mkdir(parents=True)
    Image.new("RGB", (40, 30), "blue").save(source / "visible.jpg")

    real_scandir = os.scandir

    def fail_blocked(path: os.PathLike[str] | str):
        if Path(path) == blocked:
            raise PermissionError("simulated unreadable subtree")
        return real_scandir(path)

    monkeypatch.setattr(discovery.os, "scandir", fail_blocked)
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-a")
    run_id = accounting.start_or_resume_run("dataset-a", source)
    summary = accounting.process_run(run_id)
    assert summary.issue_count == 1
    produced = ImageRenditionProducer(database).produce(run_id, Path("visible.jpg"))

    draft = ResultStore(database).build_minimal(run_id, [produced.work.work_id])

    assert draft.coverage == "partial"
    assert any(item["code"] == "discovery_incomplete" for item in draft.qualifications)

    with pytest.raises(ResultSealError, match="requires partial coverage"):
        ResultStore(database).seal(replace(draft, coverage="complete"))


def test_seal_rejects_unknown_relationship_target_kind(tmp_path: Path) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    relationship = draft.relationships[0]
    broken = replace(
        draft,
        relationships=(
            replace(relationship, target_kind="unknown"),
            *draft.relationships[1:],
        ),
    )

    with pytest.raises(ResultSealError, match="target kind"):
        store.seal(broken)


def test_seal_rejects_artifact_work_not_attached_to_current_run(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    with sqlite3.connect(database) as connection:
        connection.execute(
            "DELETE FROM run_work_records WHERE run_id = ? AND work_id = ?",
            (run_id, first.work.work_id),
        )

    with pytest.raises(ResultSealError, match="successful Work"):
        store.seal(draft)


def test_seal_rejects_artifact_work_from_another_dataset(tmp_path: Path) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    other_source = tmp_path / "other-source"
    other_source.mkdir()
    Image.new("RGB", (50, 50), "red").save(other_source / "first.jpg")
    accounting = AccountingStore(database)
    accounting.register_dataset("dataset-b")
    other_run = accounting.start_or_resume_run("dataset-b", other_source)
    accounting.process_run(other_run)
    other = ImageRenditionProducer(database).produce(other_run, Path("first.jpg"))
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    mixed_evidence = replace(
        draft.evidence[0],
        artifact_id=other.artifact.artifact_id,
        work_id=other.work.work_id,
        access={
            "kind": "local_artifact",
            "locator": {
                "kind": "local_file_path",
                "value": str(other.artifact.path),
            },
        },
    )
    mixed = replace(draft, evidence=(mixed_evidence, *draft.evidence[1:]))

    with pytest.raises(ResultSealError, match="outside this Dataset"):
        store.seal(mixed)


def test_final_seal_gate_rechecks_artifact_and_work_eligibility(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)

    class InvalidatingResultStore(ResultStore):
        def _after_file_published(self, path: Path) -> None:
            self.artifacts.verify(first.artifact.artifact_id)
            with sqlite3.connect(self.database_path) as connection:
                connection.execute(
                    "UPDATE work_records SET status = ? WHERE work_id = ?",
                    (WorkStatus.INVALIDATED, first.work.work_id),
                )

    store = InvalidatingResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])

    with pytest.raises(ResultSealError, match="no longer eligible"):
        store.seal(draft)
    assert store.audit().available == ()


def test_final_seal_gate_rechecks_source_after_bytes_are_published(
    tmp_path: Path,
) -> None:
    database, source, _source_before, run_id, first, second = _prepared(tmp_path)

    class SourceChangingResultStore(ResultStore):
        def _after_file_published(self, path: Path) -> None:
            (source / "first.jpg").write_bytes(b"changed after publication")

    store = SourceChangingResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])

    with pytest.raises(ResultSealError, match="source verification"):
        store.seal(draft)
    assert store.audit().available == ()


def test_read_integrity_check_does_not_mutate_working_state(tmp_path: Path) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    )
    first.artifact.path.chmod(0o600)
    first.artifact.path.write_bytes(b"corrupt after seal")
    before = database.read_bytes()

    response = PrecheckReadTool(database).read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )

    assert response["items"][0]["error"]["code"] == "evidence_unavailable"
    assert database.read_bytes() == before


def test_unavailable_result_is_retryable_without_changing_the_request(
    tmp_path: Path,
) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    sealed = store.seal(
        store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    )
    reader = PrecheckReadTool(database)
    request = {
        "dataset_ref": "dataset:dataset-a",
        "result_ref": sealed.result_ref,
        "action": "review",
    }
    unavailable = sealed.path.with_suffix(".temporarily-unavailable")
    sealed.path.rename(unavailable)
    try:
        failed = reader.read(request)
    finally:
        unavailable.rename(sealed.path)

    assert failed["error"]["code"] == "result_unavailable"
    assert "result" not in failed
    _assert_response_conforms(failed)
    recovered = reader.read(request)
    assert "error" not in recovered
    _assert_response_conforms(recovered)


def test_byte_trusted_invalid_result_is_rejected(tmp_path: Path) -> None:
    database, _source, _source_before, run_id, first, second = _prepared(tmp_path)
    store = ResultStore(database)
    draft = store.build_minimal(run_id, [first.work.work_id, second.work.work_id])
    invalid = replace(
        draft,
        integrity="invalid",
        qualifications=(
            {
                "code": "integrity_limitation",
                "effect": "blocks_use",
                "message": "The sealed diagnostic Result records a known limitation.",
            },
        ),
    )

    with pytest.raises(ResultSealError, match="valid Result"):
        store.seal(invalid)
    sealed = store.seal(draft)
    package = json.loads(sealed.path.read_bytes())
    package["result"]["integrity"] = "invalid"
    encoded = json.dumps(package).encode()
    sealed.path.chmod(0o644)
    sealed.path.write_bytes(encoded)
    import hashlib

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE sealed_results SET size_bytes = ?, digest = ? WHERE result_ref = ?",
            (len(encoded), hashlib.sha256(encoded).hexdigest(), sealed.result_ref),
        )
    response = PrecheckReadTool(database).read(
        {
            "dataset_ref": "dataset:dataset-a",
            "result_ref": sealed.result_ref,
            "action": "review",
        }
    )

    _assert_response_conforms(response)
    assert response["error"]["code"] == "result_untrusted"
