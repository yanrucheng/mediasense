"""Stable entry point for immutable PreCheck Result assembly and sealing."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
from typing import Iterable

from ._result_assembly import build_minimal_result
from ._result_sqlite import SQLiteResultStore
from ._result_types import (
    ResultAudit,
    ResultDraft,
    ResultEvidence,
    ResultRelationship,
    ResultSealError,
    ResultSourceItem,
    SealedResult,
)


class ResultStore(SQLiteResultStore):
    """Build a narrow frontier and publish immutable result packages."""

    def build_minimal(
        self,
        run_id: str,
        rendition_work_ids: Iterable[str],
        *,
        compression_work_ids: Iterable[str] = (),
        contact_sheet_work_ids: Iterable[str] = (),
        gpx_work_ids: Iterable[str] = (),
        metadata_work_ids: Iterable[str] = (),
        reverse_geocode_work_by_source: Mapping[Path | str, str] | None = None,
        sensitivity_work_ids: Iterable[str] = (),
        sensitivity_enabled: bool = False,
        video_probe_work_ids: Iterable[str] = (),
        video_frame_work_ids: Iterable[str] = (),
        video_key_frame_work_ids: Iterable[str] = (),
        dataset_name: str | None = None,
        dataset_context: Iterable[dict[str, object]] = (),
        external_policy_status: str | None = None,
        geo_acquisition_policy: Mapping[str, object] | None = None,
    ) -> ResultDraft:
        return build_minimal_result(
            self.database_path,
            self.artifacts,
            run_id,
            rendition_work_ids,
            compression_work_ids=compression_work_ids,
            contact_sheet_work_ids=contact_sheet_work_ids,
            gpx_work_ids=gpx_work_ids,
            metadata_work_ids=metadata_work_ids,
            reverse_geocode_work_by_source=reverse_geocode_work_by_source,
            sensitivity_work_ids=sensitivity_work_ids,
            sensitivity_enabled=sensitivity_enabled,
            video_probe_work_ids=video_probe_work_ids,
            video_frame_work_ids=video_frame_work_ids,
            video_key_frame_work_ids=video_key_frame_work_ids,
            dataset_name=dataset_name,
            dataset_context=dataset_context,
            external_policy_status=external_policy_status,
            geo_acquisition_policy=geo_acquisition_policy,
        )

    def compare(self, left_result_ref: str, right_result_ref: str) -> dict[str, object]:
        """Compare sealed public projections without exposing internal Work."""

        left = _verified_package(self.get(left_result_ref))
        right = _verified_package(self.get(right_result_ref))
        left_view = _comparison_view(left)
        right_view = _comparison_view(right)
        left_paths = set(left_view["source_paths"])
        right_paths = set(right_view["source_paths"])
        left_groups = set(left_view["groups"])
        right_groups = set(right_view["groups"])
        return {
            "left": _side_metrics(left_result_ref, left_view),
            "right": _side_metrics(right_result_ref, right_view),
            "source_boundary": {
                "added": sorted(right_paths - left_paths),
                "removed": sorted(left_paths - right_paths),
                "same": left_paths == right_paths,
            },
            "shared_artifact_count": len(
                set(left_view["artifact_refs"]) & set(right_view["artifact_refs"])
            ),
            "representation": {
                "identical_group_count": len(left_groups & right_groups),
                "left_group_count": len(left_groups),
                "right_group_count": len(right_groups),
            },
        }


def _verified_package(result: SealedResult) -> Mapping[str, object]:
    payload = result.path.read_bytes()
    if (
        len(payload) != result.size_bytes
        or hashlib.sha256(payload).hexdigest() != result.digest
    ):
        raise ResultSealError(
            f"sealed Result failed integrity verification: {result.result_ref}"
        )
    value = json.loads(payload)
    if not isinstance(value, Mapping) or value.get("schema_version") not in {1, 2}:
        raise ResultSealError("sealed Result has an unsupported package shape")
    return value


def _comparison_view(package: Mapping[str, object]) -> dict[str, object]:
    source_records = package.get("sources")
    relationships = package.get("relationships")
    artifact_refs = package.get("artifact_refs")
    result = package.get("result")
    if (
        not isinstance(source_records, list)
        or not isinstance(relationships, list)
        or not isinstance(artifact_refs, list)
        or not isinstance(result, Mapping)
    ):
        raise ResultSealError("sealed Result comparison fields are invalid")
    source_by_ref = {
        str(record["view"]["ref"]): str(record["relative_path"])
        for record in source_records
        if isinstance(record, Mapping) and isinstance(record.get("view"), Mapping)
    }
    entry_refs = {
        str(record["member"]["target"])
        for record in relationships
        if isinstance(record, Mapping)
        and record.get("origin") == result.get("ref")
        and record.get("relation") == "entry_evidence"
        and isinstance(record.get("member"), Mapping)
    }
    represented: dict[str, set[str]] = {ref: set() for ref in entry_refs}
    source_media_count = 0
    for record in relationships:
        if not isinstance(record, Mapping) or not isinstance(
            record.get("member"), Mapping
        ):
            continue
        member = record["member"]
        if (
            record.get("relation") == "accounts_for"
            and member.get("scope") == "source_media"
        ):
            source_media_count += 1
        if (
            record.get("relation") == "represents"
            and str(record.get("origin")) in represented
        ):
            target = str(member.get("target"))
            if target in source_by_ref:
                represented[str(record["origin"])].add(source_by_ref[target])
    groups = tuple(
        sorted(tuple(sorted(paths)) for paths in represented.values() if paths)
    )
    return {
        "artifact_refs": tuple(str(value) for value in artifact_refs),
        "entry_count": len(entry_refs),
        "groups": groups,
        "source_media_count": source_media_count,
        "source_paths": tuple(sorted(source_by_ref.values())),
    }


def _side_metrics(result_ref: str, view: Mapping[str, object]) -> dict[str, object]:
    entry_count = int(view["entry_count"])
    source_media_count = int(view["source_media_count"])
    return {
        "accounted_source_media": source_media_count,
        "compression_ratio": (
            None if entry_count == 0 else source_media_count / entry_count
        ),
        "entry_evidence": entry_count,
        "result_ref": result_ref,
    }


__all__ = [
    "ResultAudit",
    "ResultDraft",
    "ResultEvidence",
    "ResultRelationship",
    "ResultSealError",
    "ResultSourceItem",
    "ResultStore",
    "SealedResult",
]
