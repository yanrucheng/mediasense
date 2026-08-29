"""Project prepared Artifact Work into Result Evidence and relationships."""

from __future__ import annotations

from dataclasses import replace
import json
import sqlite3

from ._artifact_types import ArtifactIntegrity
from ._result_types import (
    ResultEvidence,
    ResultRelationship,
    ResultSealError,
    result_local_reference,
)
from ._work_types import WorkStatus
from .artifact import ArtifactStore


def _has_available_artifact(artifacts: ArtifactStore, work: sqlite3.Row) -> bool:
    if WorkStatus(work["status"]) is not WorkStatus.SUCCEEDED:
        return False
    produced = artifacts.artifacts_for_work(str(work["work_id"]))
    return bool(produced and produced[0].integrity is ArtifactIntegrity.AVAILABLE)


def _apply_compression_frontier(
    groups: tuple[dict[str, object], ...],
    source_refs: dict[str, str],
    primary_evidence_by_path: dict[str, str],
    evidence: list[ResultEvidence],
    entry_evidence: list[str],
    relationships: list[ResultRelationship],
) -> list[ResultEvidence]:
    grouped_paths: set[str] = set()
    roles: dict[str, list[dict[str, object]]] = {}
    relationship_keys = {
        (item.origin_ref, item.relation, item.target_ref, item.target_kind)
        for item in relationships
    }
    representative_refs = []
    for group in groups:
        members = tuple(str(path) for path in group["members"])
        overlap = grouped_paths & set(members)
        if overlap:
            raise ResultSealError(
                "compression groups overlap: " + ", ".join(sorted(overlap))
            )
        grouped_paths.update(members)
        representative_path = str(group["representative_path"])
        representative_ref = primary_evidence_by_path.get(representative_path)
        if representative_ref is None:
            raise ResultSealError(
                "compression representative lacks selected visual Evidence: "
                f"{representative_path}"
            )
        representative_refs.append(representative_ref)
        group_id = str(group["group_id"])
        roles.setdefault(representative_ref, []).append(
            _role_observation("representative", group_id)
        )
        for path in group["boundary_paths"]:
            evidence_ref = primary_evidence_by_path.get(str(path))
            if evidence_ref is not None:
                roles.setdefault(evidence_ref, []).append(
                    _role_observation("boundary", group_id)
                )
        for path in group["outlier_paths"]:
            evidence_ref = primary_evidence_by_path.get(str(path))
            if evidence_ref is not None:
                roles.setdefault(evidence_ref, []).append(
                    _role_observation("outlier", group_id)
                )
        for path in group["conflict_paths"]:
            evidence_ref = primary_evidence_by_path.get(str(path))
            if evidence_ref is not None:
                roles.setdefault(evidence_ref, []).append(
                    _role_observation("conflict", group_id)
                )
        qualifications = tuple(
            {
                "code": str(code),
                "effect": "limits_interpretation",
                "message": "This compression claim has incomplete comparison evidence.",
            }
            for code in group.get("qualifications", [])
        )
        basis = "adaptive candidate representation; " + json.dumps(
            group.get("basis") or {}, sort_keys=True
        )
        for path in members:
            source_ref = source_refs[path]
            key = (representative_ref, "represents", source_ref, "source_item")
            if key not in relationship_keys:
                relationships.append(
                    ResultRelationship(
                        origin_ref=representative_ref,
                        relation="represents",
                        target_ref=source_ref,
                        target_kind="source_item",
                        basis=basis,
                        qualifications=qualifications,
                    )
                )
                relationship_keys.add(key)
            detail_ref = primary_evidence_by_path.get(path)
            detail_key = (representative_ref, "expands_to", detail_ref, "evidence")
            if (
                detail_ref is not None
                and detail_ref != representative_ref
                and detail_key not in relationship_keys
            ):
                relationships.append(
                    ResultRelationship(
                        origin_ref=representative_ref,
                        relation="expands_to",
                        target_ref=detail_ref,
                        target_kind="evidence",
                        basis="prepared member Evidence for this compression candidate",
                    )
                )
                relationship_keys.add(detail_key)
    grouped_primary = {
        primary_evidence_by_path[path]
        for path in grouped_paths
        if path in primary_evidence_by_path
    }
    entry_evidence[:] = [
        ref for ref in entry_evidence if ref not in grouped_primary
    ] + list(dict.fromkeys(representative_refs))
    return [
        replace(item, observations=item.observations + tuple(roles.get(item.ref, ())))
        for item in evidence
    ]


def _role_observation(role: str, group_id: str) -> dict[str, object]:
    return {
        "name": "evidence_role",
        "status": "available",
        "value": {"group_ref": group_id, "role": role},
        "basis": "builtin-ranked-adjacent-compression-v1",
    }


def _append_video_evidence(
    artifacts: ArtifactStore,
    source_ref: str,
    frame_works: list[sqlite3.Row],
    sheet_works: list[sqlite3.Row],
    key_frame_work: sqlite3.Row | None,
    evidence: list[ResultEvidence],
    entry_evidence: list[str],
    relationships: list[ResultRelationship],
) -> str | None:
    frame_refs: dict[str, str] = {}
    primary_ref: str | None = None
    for work in frame_works:
        if not _has_available_artifact(artifacts, work):
            continue
        produced = artifacts.artifacts_for_work(str(work["work_id"]), verify=False)
        output = json.loads(work["output_json"])
        value = output.get("value") or {}
        evidence_ref = result_local_reference(
            "evidence", str(work["work_id"]), produced[0].artifact_id
        )
        frame_refs[str(work["work_id"])] = evidence_ref
        evidence.append(
            ResultEvidence(
                ref=evidence_ref,
                access={
                    "kind": "local_artifact",
                    "locator": {
                        "kind": "local_file_path",
                        "value": str(produced[0].path),
                    },
                },
                artifact_id=produced[0].artifact_id,
                work_id=str(work["work_id"]),
                observations=(
                    {
                        "name": "video_frame",
                        "status": "available",
                        "value": value,
                        "basis": "builtin-ffmpeg-video-frame-v1",
                    },
                ),
            )
        )
        relationships.extend(_visual_source_relationships(evidence_ref, source_ref))

    selected_frame_ref: str | None = None
    if key_frame_work is not None:
        if WorkStatus(key_frame_work["status"]) is not WorkStatus.SUCCEEDED:
            raise ResultSealError("selected video key-frame Work must succeed")
        output = json.loads(key_frame_work["output_json"])
        candidate = output.get("candidate")
        selected_work_id = (
            None
            if not isinstance(candidate, dict)
            else candidate.get("selected_frame_work_id")
        )
        if not isinstance(selected_work_id, str) or selected_work_id not in frame_refs:
            raise ResultSealError(
                "video key-frame candidate requires its selected frame in this Result"
            )
        selected_frame_ref = frame_refs[selected_work_id]
        for index, item in enumerate(evidence):
            if item.ref == selected_frame_ref:
                evidence[index] = replace(
                    item,
                    observations=item.observations
                    + (_role_observation("representative", "video-key-frame"),),
                )
                break

    for work in sheet_works:
        if not _has_available_artifact(artifacts, work):
            continue
        produced = artifacts.artifacts_for_work(str(work["work_id"]), verify=False)
        output = json.loads(work["output_json"])
        value = output.get("value") or {}
        expected_frame_ids = value.get("frame_work_ids")
        if (
            not isinstance(expected_frame_ids, list)
            or not expected_frame_ids
            or any(work_id not in frame_refs for work_id in expected_frame_ids)
        ):
            raise ResultSealError(
                "contact sheet requires every producing frame Work in this Result"
            )
        sheet_ref = result_local_reference(
            "evidence", str(work["work_id"]), produced[0].artifact_id
        )
        evidence.append(
            ResultEvidence(
                ref=sheet_ref,
                access={
                    "kind": "local_artifact",
                    "locator": {
                        "kind": "local_file_path",
                        "value": str(produced[0].path),
                    },
                },
                artifact_id=produced[0].artifact_id,
                work_id=str(work["work_id"]),
                observations=(
                    {
                        "name": "video_contact_sheet",
                        "status": "available",
                        "value": value,
                        "basis": "builtin-video-contact-sheet-v1",
                    },
                ),
                qualifications=(
                    {
                        "code": "sampled_video_evidence",
                        "effect": "limits_interpretation",
                        "message": "The contact sheet samples the video timeline rather than showing every frame.",
                    },
                ),
            )
        )
        entry_evidence.append(sheet_ref)
        if primary_ref is None:
            primary_ref = sheet_ref
        relationships.extend(_visual_source_relationships(sheet_ref, source_ref))
        relationships.extend(
            ResultRelationship(
                origin_ref=sheet_ref,
                relation="expands_to",
                target_ref=frame_refs[work_id],
                target_kind="evidence",
                basis="sampled frame included in this contact sheet",
            )
            for work_id in expected_frame_ids
        )
        if selected_frame_ref is not None and selected_frame_ref not in {
            frame_refs[work_id] for work_id in expected_frame_ids
        }:
            relationships.append(
                ResultRelationship(
                    origin_ref=sheet_ref,
                    relation="expands_to",
                    target_ref=selected_frame_ref,
                    target_kind="evidence",
                    basis="selected video key-frame candidate",
                )
            )
    if primary_ref is None and selected_frame_ref is not None:
        entry_evidence.append(selected_frame_ref)
        primary_ref = selected_frame_ref
    return primary_ref


def _visual_source_relationships(
    evidence_ref: str, source_ref: str
) -> tuple[ResultRelationship, ...]:
    return (
        ResultRelationship(
            origin_ref=evidence_ref,
            relation="represents",
            target_ref=source_ref,
            target_kind="source_item",
            basis="sampled visual evidence from this video Source Item",
        ),
        ResultRelationship(
            origin_ref=evidence_ref,
            relation="derived_from",
            target_ref=source_ref,
            target_kind="source_item",
            basis="exact source content dependency",
        ),
        ResultRelationship(
            origin_ref=evidence_ref,
            relation="expands_to",
            target_ref=source_ref,
            target_kind="source_item",
        ),
    )
