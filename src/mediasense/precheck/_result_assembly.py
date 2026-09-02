"""Assemble a minimal ResultDraft from closed accounting and selected Work."""

from __future__ import annotations

from collections.abc import Iterator, Set
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from typing import Iterable, Mapping

from mediasense.dataset_reference import dataset_ref_from_id

from ._accounting_types import WorkingRunStatus
from ._artifact_types import ArtifactIntegrity, ArtifactRecord
from ._result_evidence_projection import (
    _append_video_evidence,
    _apply_compression_frontier,
    _has_available_artifact,
)
from ._result_types import (
    ResultDraft,
    ResultEvidence,
    ResultRelationship,
    ResultSealError,
    ResultSourceItem,
    result_local_reference,
    source_root_reference,
)
from ._result_work_projection import (
    _connect,
    _load_compression_groups,
    _load_mapped_observation_work,
    _load_source_artifact_work,
    _load_source_observation_work,
    _load_source_observation_works,
    _metadata_result_observations,
    _mapped_result_observations,
)
from ._work_types import DependencyKind, WorkStatus
from .artifact import ArtifactStore


class _RunSourcePaths(Set[str]):
    """Use the authoritative run_items index without copying every path."""

    def __init__(self, connection: sqlite3.Connection, run_id: str) -> None:
        self._connection = connection
        self._run_id = run_id

    def __contains__(self, value: object) -> bool:
        if not isinstance(value, str):
            return False
        return (
            self._connection.execute(
                """
                SELECT 1 FROM run_items
                WHERE run_id = ? AND relative_path = ?
                """,
                (self._run_id, value),
            ).fetchone()
            is not None
        )

    def __iter__(self) -> Iterator[str]:
        return (
            str(row["relative_path"])
            for row in self._connection.execute(
                "SELECT relative_path FROM run_items WHERE run_id = ?",
                (self._run_id,),
            )
        )

    def __len__(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) AS count FROM run_items WHERE run_id = ?",
            (self._run_id,),
        ).fetchone()
        assert row is not None
        return int(row["count"])


def build_minimal_result(
    database_path: Path,
    artifacts: ArtifactStore,
    run_id: str,
    rendition_work_ids: Iterable[str],
    *,
    compression_work_ids: Iterable[str] = (),
    contact_sheet_work_ids: Iterable[str] = (),
    gpx_work_ids: Iterable[str] = (),
    metadata_work_ids: Iterable[str] = (),
    reverse_geocode_work_by_source: Mapping[Path | str, str] | None = None,
    sensitivity_work_ids: Iterable[str] = (),
    video_probe_work_ids: Iterable[str] = (),
    video_frame_work_ids: Iterable[str] = (),
    video_key_frame_work_ids: Iterable[str] = (),
    dataset_name: str | None = None,
    dataset_context: Iterable[dict[str, object]] = (),
    external_policy_status: str | None = None,
) -> ResultDraft:
    """Build the immutable Result authority.

    The returned Source Item, Evidence, and relationship sequences are
    intentionally O(N) in the facts the Result publishes. Upstream execution
    coordination must stay bounded; this publication boundary is the explicit
    exception because the canonical JSON payload itself contains those rows.
    """

    selected_ids = tuple(dict.fromkeys(rendition_work_ids))
    selected_compression_ids = tuple(dict.fromkeys(compression_work_ids))
    selected_metadata_ids = tuple(dict.fromkeys(metadata_work_ids))
    selected_geocode_map = dict(reverse_geocode_work_by_source or {})
    selected_gpx_ids = tuple(dict.fromkeys(gpx_work_ids))
    selected_sensitivity_ids = tuple(dict.fromkeys(sensitivity_work_ids))
    selected_probe_ids = tuple(dict.fromkeys(video_probe_work_ids))
    selected_frame_ids = tuple(dict.fromkeys(video_frame_work_ids))
    selected_key_frame_ids = tuple(dict.fromkeys(video_key_frame_work_ids))
    selected_sheet_ids = tuple(dict.fromkeys(contact_sheet_work_ids))
    with _connect(database_path) as connection:
        run = connection.execute(
            "SELECT dataset_id, status, reuse_domain FROM working_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if run is None:
            raise KeyError(f"unknown Working Run: {run_id}")
        if WorkingRunStatus(run["status"]) not in {
            WorkingRunStatus.COMPLETED,
            WorkingRunStatus.COMPLETED_WITH_ISSUES,
        }:
            raise ResultSealError("source accounting must close before assembly")
        rows = connection.execute(
            """
            SELECT relative_path, kind, scope, condition, basis_json
            FROM run_items WHERE run_id = ? ORDER BY relative_path
            """,
            (run_id,),
        ).fetchall()
        source_paths = _RunSourcePaths(connection, run_id)
        verification_rows = {
            str(row["relative_path"]): row
            for row in connection.execute(
                """
                SELECT source_content_proofs.*
                FROM source_content_proofs
                JOIN run_items
                  ON run_items.run_id = ?
                 AND run_items.relative_path = source_content_proofs.relative_path
                 AND run_items.source_revision = source_content_proofs.source_revision
                WHERE source_content_proofs.dataset_id = ?
                  AND source_content_proofs.reuse_domain = ?
                """,
                (run_id, run["dataset_id"], run["reuse_domain"]),
            )
        }
        unaccounted_issues = connection.execute(
            """
            SELECT run_issues.relative_path, run_issues.code
            FROM run_issues
            WHERE run_issues.run_id = ?
              AND NOT EXISTS (
                  SELECT 1 FROM run_items
                  WHERE run_items.run_id = run_issues.run_id
                    AND run_items.relative_path = run_issues.relative_path
              )
            ORDER BY run_issues.relative_path, run_issues.code
            """,
            (run_id,),
        ).fetchall()
        work_rows: dict[str, list[sqlite3.Row]] = {}
        for work_id in selected_ids:
            work = connection.execute(
                """
                SELECT work_records.* FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                  AND work_records.work_id = ?
                  AND work_records.capability = 'image-rendition'
                """,
                (run_id, work_id),
            ).fetchone()
            if work is None:
                raise ResultSealError(
                    f"selected rendition Work is not attached to this run: {work_id}"
                )
            dependency = connection.execute(
                """
                SELECT dependency_key FROM work_dependencies
                WHERE work_id = ? AND dependency_kind = ?
                """,
                (work_id, DependencyKind.SOURCE_CONTENT),
            ).fetchone()
            if dependency is None:
                raise ResultSealError(
                    f"rendition Work lacks exact source proof: {work_id}"
                )
            _dataset, relative_path = json.loads(dependency["dependency_key"])
            work_rows.setdefault(relative_path, []).append(work)
        metadata_rows = {}
        for work_id in selected_metadata_ids:
            work = connection.execute(
                """
                SELECT work_records.* FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                  AND work_records.work_id = ?
                  AND work_records.capability = 'source-metadata'
                """,
                (run_id, work_id),
            ).fetchone()
            if work is None:
                raise ResultSealError(
                    f"selected metadata Work is not attached to this run: {work_id}"
                )
            subject = connection.execute(
                """
                SELECT dependency_value FROM work_dependencies
                WHERE work_id = ? AND dependency_kind = ?
                  AND dependency_key = 'subject_relative_path'
                """,
                (work_id, DependencyKind.PARAMETER),
            ).fetchone()
            if subject is None or str(subject["dependency_value"]) not in source_paths:
                raise ResultSealError(
                    f"metadata Work has an invalid subject: {work_id}"
                )
            relative_path = str(subject["dependency_value"])
            if relative_path in metadata_rows:
                raise ResultSealError(
                    f"multiple selected metadata Work Records for one source: {relative_path}"
                )
            metadata_rows[relative_path] = work
        gpx_rows = _load_source_observation_work(
            connection,
            run_id,
            source_paths,
            selected_gpx_ids,
            capability="gpx-location-candidate",
            label="GPX",
        )
        sensitivity_rows = _load_source_observation_works(
            connection,
            run_id,
            source_paths,
            selected_sensitivity_ids,
            capability="content-sensitivity",
            label="sensitivity",
        )
        video_probe_rows = _load_source_observation_work(
            connection,
            run_id,
            source_paths,
            selected_probe_ids,
            capability="video-probe",
            label="video probe",
        )
        geocode_rows = _load_mapped_observation_work(
            connection,
            run_id,
            source_paths,
            selected_geocode_map,
            capability="reverse-geocode-observation",
            label="reverse geocode",
        )
        video_frame_rows = _load_source_artifact_work(
            connection,
            run_id,
            source_paths,
            selected_frame_ids,
            capability="video-frame",
            label="video frame",
        )
        video_key_frame_rows = _load_source_observation_work(
            connection,
            run_id,
            source_paths,
            selected_key_frame_ids,
            capability="video-key-frame-candidate",
            label="video key frame",
        )
        contact_sheet_rows = _load_source_artifact_work(
            connection,
            run_id,
            source_paths,
            selected_sheet_ids,
            capability="video-contact-sheet",
            label="contact sheet",
        )
        compression_groups = _load_compression_groups(
            connection,
            run_id,
            source_paths,
            selected_compression_ids,
        )

    dataset_id = str(run["dataset_id"])
    source_root_ref = source_root_reference(dataset_id, str(run["reuse_domain"]))
    sources: list[ResultSourceItem] = []
    evidence: list[ResultEvidence] = []
    relationships: list[ResultRelationship] = []
    entry_evidence: list[str] = []
    primary_evidence_by_path: dict[str, str] = {}
    for row in rows:
        relative_path = str(row["relative_path"])
        scope = str(row["scope"])
        condition = str(row["condition"])
        observations: list[dict[str, object]] = []
        verification = verification_rows.get(relative_path)
        if verification is not None:
            observations.append(_source_verification_observation(verification))
        qualifications: list[dict[str, object]] = []
        rendition_works = work_rows.get(relative_path, [])
        metadata_work = metadata_rows.get(relative_path)
        gpx_work = gpx_rows.get(relative_path)
        sensitivity_works = sensitivity_rows.get(relative_path, [])
        geocode_work = geocode_rows.get(relative_path)
        video_probe_work = video_probe_rows.get(relative_path)
        frame_works = video_frame_rows.get(relative_path, [])
        key_frame_work = video_key_frame_rows.get(relative_path)
        sheet_works = contact_sheet_rows.get(relative_path, [])
        rendition_outputs: list[
            tuple[sqlite3.Row, ArtifactRecord, dict[str, object]]
        ] = []
        if metadata_work is not None:
            if WorkStatus(metadata_work["status"]) is WorkStatus.SUCCEEDED:
                metadata_output = json.loads(metadata_work["output_json"])
                observations.extend(
                    _metadata_result_observations(metadata_output, run_id)
                )
            elif WorkStatus(metadata_work["status"]) is WorkStatus.TERMINAL_FAILURE:
                observations.append(
                    {
                        "name": "source_metadata",
                        "status": "failed",
                        "basis": str(metadata_work["last_failure_code"]),
                        "qualifications": [
                            {
                                "code": "metadata_unavailable",
                                "effect": "limits_interpretation",
                                "message": str(metadata_work["last_failure_message"]),
                            }
                        ],
                    }
                )
        if gpx_work is not None:
            if WorkStatus(gpx_work["status"]) is WorkStatus.SUCCEEDED:
                gpx_output = json.loads(gpx_work["output_json"])
                observations.extend(_metadata_result_observations(gpx_output, run_id))
            elif WorkStatus(gpx_work["status"]) is WorkStatus.TERMINAL_FAILURE:
                observations.append(
                    {
                        "name": "gpx_coordinates",
                        "status": "failed",
                        "basis": str(gpx_work["last_failure_code"]),
                        "qualifications": [
                            {
                                "code": "gpx_matching_unavailable",
                                "effect": "limits_interpretation",
                                "message": str(gpx_work["last_failure_message"]),
                            }
                        ],
                    }
                )
        if geocode_work is not None:
            observations.extend(
                _mapped_result_observations(
                    geocode_work,
                    result_local_reference("source-item", run_id, relative_path),
                    label="reverse geocode",
                )
            )
        for sensitivity_work in sensitivity_works:
            if WorkStatus(sensitivity_work["status"]) is WorkStatus.SUCCEEDED:
                sensitivity_output = json.loads(sensitivity_work["output_json"])
                observations.extend(
                    _metadata_result_observations(sensitivity_output, run_id)
                )
            elif WorkStatus(sensitivity_work["status"]) is WorkStatus.TERMINAL_FAILURE:
                observations.append(
                    {
                        "name": "content_sensitivity",
                        "status": "failed",
                        "basis": str(sensitivity_work["last_failure_code"]),
                        "qualifications": [
                            {
                                "code": "sensitivity_unavailable",
                                "effect": "limits_interpretation",
                                "message": str(
                                    sensitivity_work["last_failure_message"]
                                ),
                            }
                        ],
                    }
                )
        if (
            video_probe_work is not None
            and WorkStatus(video_probe_work["status"]) is WorkStatus.TERMINAL_FAILURE
        ):
            condition = "invalid"
            observations.append(
                {
                    "name": "video_probe",
                    "status": "failed",
                    "basis": str(video_probe_work["last_failure_code"]),
                    "qualifications": [
                        {
                            "code": "video_unavailable",
                            "effect": "limits_interpretation",
                            "message": str(video_probe_work["last_failure_message"]),
                        }
                    ],
                }
            )
        failed_frames = [
            work
            for work in frame_works
            if WorkStatus(work["status"]) is WorkStatus.TERMINAL_FAILURE
        ]
        if failed_frames:
            observations.append(
                {
                    "name": "video_frame",
                    "status": "failed",
                    "basis": "one or more selected frame Work Records failed",
                    "qualifications": [
                        {
                            "code": "video_frames_partial",
                            "effect": "limits_interpretation",
                            "message": (
                                f"{len(failed_frames)} selected video frame(s) "
                                "could not be decoded."
                            ),
                        }
                    ],
                }
            )
            if not any(
                _has_available_artifact(artifacts, work) for work in frame_works
            ):
                condition = "invalid"
        for work in rendition_works:
            if WorkStatus(work["status"]) is WorkStatus.SUCCEEDED:
                produced = artifacts.artifacts_for_work(str(work["work_id"]))
                if produced and produced[0].integrity is ArtifactIntegrity.AVAILABLE:
                    output = json.loads(work["output_json"])
                    rendition_outputs.append(
                        (work, produced[0], output.get("value") or {})
                    )
                    condition = "usable"
            elif WorkStatus(work["status"]) is WorkStatus.TERMINAL_FAILURE:
                if not rendition_outputs:
                    condition = (
                        "invalid"
                        if work["last_failure_code"] == "image_decode_failed"
                        else "error"
                    )
                observations.append(
                    {
                        "name": "image_rendition",
                        "status": "failed",
                        "basis": str(work["last_failure_code"]),
                        "qualifications": [
                            {
                                "code": "rendition_unavailable",
                                "effect": "limits_interpretation",
                                "message": str(work["last_failure_message"]),
                            }
                        ],
                    }
                )
        if any(_has_available_artifact(artifacts, work) for work in sheet_works):
            condition = "usable"
        source_ref = result_local_reference("source-item", run_id, relative_path)
        sources.append(
            ResultSourceItem(
                ref=source_ref,
                relative_path=Path(relative_path),
                locator={
                    "kind": "source_root_relative_path",
                    "source_root_ref": source_root_ref,
                    "value": relative_path,
                },
                scope=scope,
                condition=condition,
                basis="; ".join(json.loads(row["basis_json"])),
                observations=tuple(observations),
                qualifications=tuple(qualifications),
            )
        )
        if not rendition_outputs:
            video_entry = _append_video_evidence(
                artifacts,
                source_ref,
                frame_works,
                sheet_works,
                key_frame_work,
                evidence,
                entry_evidence,
                relationships,
            )
            if video_entry is not None:
                primary_evidence_by_path[relative_path] = video_entry
            continue
        rendition_refs: list[tuple[str, str]] = []
        for work, artifact, value in sorted(
            rendition_outputs,
            key=lambda item: (
                0 if (item[2].get("profile") or {}).get("name") == "ordinary" else 1,
                str(item[0]["work_id"]),
            ),
        ):
            profile = value.get("profile") or {}
            profile_name = str(profile.get("name") or "custom")
            evidence_ref = result_local_reference(
                "evidence", run_id, str(work["work_id"]), artifact.artifact_id
            )
            rendition_refs.append((profile_name, evidence_ref))
            evidence.append(
                ResultEvidence(
                    ref=evidence_ref,
                    access={
                        "kind": "local_artifact",
                        "locator": {
                            "kind": "local_file_path",
                            "value": str(artifact.path),
                        },
                    },
                    artifact_id=artifact.artifact_id,
                    work_id=str(work["work_id"]),
                    observations=(
                        {
                            "name": "pixel_dimensions",
                            "status": "available",
                            "value": {
                                "height": value.get("height"),
                                "profile": profile,
                                "width": value.get("width"),
                            },
                            "basis": "builtin-image-rendition-v1",
                        },
                    ),
                    qualifications=(
                        {
                            "code": "lower_fidelity_rendition",
                            "effect": "limits_interpretation",
                            "message": "JPEG rendition is smaller and may omit source detail.",
                        },
                    ),
                )
            )
            relationships.extend(
                (
                    ResultRelationship(
                        origin_ref=evidence_ref,
                        relation="represents",
                        target_ref=source_ref,
                        target_kind="source_item",
                        basis="one locally decoded rendition of this Source Item",
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
            )
        ordinary_ref = next(
            (ref for name, ref in rendition_refs if name == "ordinary"),
            rendition_refs[0][1],
        )
        entry_evidence.append(ordinary_ref)
        primary_evidence_by_path[relative_path] = ordinary_ref
        relationships.extend(
            ResultRelationship(
                origin_ref=ordinary_ref,
                relation="expands_to",
                target_ref=ref,
                target_kind="evidence",
                basis="higher-resolution rendition of the same Source Item",
            )
            for name, ref in rendition_refs
            if ref != ordinary_ref and name == "high_resolution"
        )
        _append_video_evidence(
            artifacts,
            source_ref,
            frame_works,
            sheet_works,
            key_frame_work,
            evidence,
            entry_evidence,
            relationships,
        )

    if compression_groups:
        evidence, represented_source_refs = _apply_compression_frontier(
            compression_groups,
            run_id,
            primary_evidence_by_path,
            evidence,
            entry_evidence,
            relationships,
        )
        sources = [
            replace(source, condition="usable")
            if (
                source.scope == "source_media"
                and source.condition == "unresolved"
                and source.ref in represented_source_refs
            )
            else source
            for source in sources
        ]

    unresolved_source_media = tuple(
        source.ref
        for source in sources
        if source.scope == "source_media" and source.condition == "unresolved"
    )
    readiness = (
        "plan_ready" if entry_evidence and not unresolved_source_media else "blocked"
    )
    result_qualifications: list[dict[str, object]] = []
    coverage = "partial" if unaccounted_issues else "complete"
    if unaccounted_issues:
        boundaries = ", ".join(
            f"{row['relative_path']} ({row['code']})" for row in unaccounted_issues
        )
        result_qualifications.append(
            {
                "code": "discovery_incomplete",
                "effect": "limits_interpretation",
                "message": f"Discovery could not enumerate: {boundaries}.",
            }
        )
    if readiness == "blocked":
        message = (
            "Source media remains unresolved and requires more PreCheck work."
            if unresolved_source_media
            else "No usable default Evidence is available for planning."
        )
        result_qualifications.append(
            {
                "code": (
                    "unresolved_source_media"
                    if unresolved_source_media
                    else "no_entry_evidence"
                ),
                "effect": "blocks_use",
                "message": message,
            }
        )
    external_boundary = _external_effect_boundary(geocode_rows.values())
    if external_boundary is not None:
        result_qualifications.append(
            {
                "code": "external_reverse_geocode_candidates",
                "effect": "limits_interpretation",
                "message": (
                    "Reverse-geocode candidate Evidence used "
                    f"{external_boundary['logical_external_queries']} logical "
                    "queries and observed "
                    f"{external_boundary['provider_requests']} provider requests; "
                    "provider data remains a candidate rather than confirmed place truth."
                ),
            }
        )
    elif external_policy_status in {"policy_disabled", "not_requested"}:
        result_qualifications.append(
            {
                "code": f"reverse_geocode_{external_policy_status}",
                "effect": "limits_interpretation",
                "message": (
                    "Reverse-geocode candidate Evidence was disabled by policy."
                    if external_policy_status == "policy_disabled"
                    else "Reverse-geocode candidate Evidence was skipped by user decision."
                ),
            }
        )
    return ResultDraft(
        run_id=run_id,
        dataset_id=dataset_id,
        dataset_ref=dataset_ref_from_id(dataset_id),
        dataset_name=dataset_name,
        dataset_context=tuple(dataset_context),
        coverage=coverage,
        readiness=readiness,
        integrity="valid",
        sources=tuple(sources),
        evidence=tuple(evidence),
        entry_evidence=tuple(entry_evidence),
        relationships=tuple(relationships),
        qualifications=tuple(result_qualifications),
        execution_boundary=(
            {
                "billable_calls": 0,
                "network_access": False,
                "remote_models": False,
                "source_read_only": True,
            }
            if external_boundary is None
            else external_boundary
        ),
        supporting_work_ids=tuple(
            sorted(
                set(
                    selected_ids
                    + selected_compression_ids
                    + selected_metadata_ids
                    + selected_gpx_ids
                    + tuple(selected_geocode_map.values())
                    + selected_sensitivity_ids
                    + selected_probe_ids
                    + selected_frame_ids
                    + selected_key_frame_ids
                    + selected_sheet_ids
                )
            )
        ),
    )


def _source_verification_observation(row: sqlite3.Row) -> dict[str, object]:
    profile = str(row["algorithm"])
    exact = profile == "sha256-full-v1"
    return {
        "name": "source_content_verification",
        "status": "available",
        "value": {
            "profile": profile,
            "value": f"sha256:{row['digest']}",
            "size_bytes": int(row["size_bytes"]),
            "observed_at": str(row["observed_at"]),
            "producer": (
                "builtin-source-content-proof-v1"
                if exact
                else "builtin-source-revision-observation-v1"
            ),
        },
        "basis": (
            "complete source-byte read with stable pre/post file observations"
            if exact
            else "accounted Source revision, bounded fingerprint, and stable current file identity"
        ),
        **(
            {}
            if exact
            else {
                "qualifications": [
                    {
                        "code": "ordinary_change_detection_only",
                        "effect": "limits_interpretation",
                        "message": (
                            "The observation detects ordinary source changes but is "
                            "not an exact full-byte proof."
                        ),
                    }
                ]
            }
        ),
    }


def _external_effect_boundary(
    rows: Iterable[sqlite3.Row],
) -> dict[str, object] | None:
    unique = {str(row["work_id"]): row for row in rows}
    if not unique:
        return None
    provider_requests = 0
    authorizations: dict[tuple[str, str], dict[str, object]] = {}
    providers: set[str] = set()
    for work in unique.values():
        output = json.loads(work["output_json"])
        result = output.get("result")
        authorization = output.get("authorization")
        if not isinstance(result, dict) or not isinstance(authorization, dict):
            raise ResultSealError(
                "reverse geocode Work lacks effect or authorization evidence"
            )
        request_count = result.get("provider_request_count")
        if not isinstance(request_count, int) or isinstance(request_count, bool):
            raise ResultSealError(
                "reverse geocode Work has an invalid provider request count"
            )
        run_ref = authorization.get("run_ref")
        fingerprint = authorization.get("pending_fingerprint")
        if (
            not isinstance(run_ref, str)
            or not isinstance(fingerprint, str)
            or authorization.get("decision") != "proceed"
        ):
            raise ResultSealError("reverse geocode Work was not explicitly authorized")
        provider = result.get("provider")
        if isinstance(provider, str) and provider:
            providers.add(provider)
        provider_requests += request_count
        authorizations[(run_ref, fingerprint)] = dict(authorization)
    return {
        "authorizations": [authorizations[key] for key in sorted(authorizations)],
        "billable_calls": "unknown",
        "logical_external_queries": len(unique),
        "network_access": True,
        "provider_requests": provider_requests,
        "providers": sorted(providers),
        "remote_models": False,
        "source_read_only": True,
    }


__all__ = ["build_minimal_result"]
