"""Load selected Work and project bounded source observations for Result assembly."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from ._result_types import ResultSealError
from ._work_types import DependencyKind, WorkStatus


def _load_mapped_observation_work(
    connection: sqlite3.Connection,
    run_id: str,
    source_rows: list[sqlite3.Row],
    work_by_source: Mapping[Path | str, str],
    *,
    capability: str,
    label: str,
) -> dict[str, sqlite3.Row]:
    """Load one reusable observation Work explicitly mapped to each source."""

    known_sources = {str(row["relative_path"]) for row in source_rows}
    selected: dict[str, sqlite3.Row] = {}
    loaded: dict[str, sqlite3.Row] = {}
    for source_path, work_id in work_by_source.items():
        relative_path = Path(source_path).as_posix()
        if (
            Path(relative_path).is_absolute()
            or ".." in Path(relative_path).parts
            or relative_path not in known_sources
        ):
            raise ResultSealError(f"{label} Work has an invalid source mapping")
        work = loaded.get(work_id)
        if work is None:
            work = connection.execute(
                """
                SELECT work_records.* FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                  AND work_records.work_id = ?
                  AND work_records.capability = ?
                  AND work_records.status = ?
                """,
                (run_id, work_id, capability, WorkStatus.SUCCEEDED),
            ).fetchone()
            if work is None:
                raise ResultSealError(
                    f"selected {label} Work is not eligible: {work_id}"
                )
            loaded[work_id] = work
        selected[relative_path] = work
    return selected


def _mapped_result_observations(
    work: sqlite3.Row,
    source_ref: str,
    *,
    label: str,
) -> list[dict[str, object]]:
    output = json.loads(work["output_json"])
    observations = output.get("observations")
    if (
        not isinstance(observations, list)
        or not observations
        or any(not isinstance(item, dict) for item in observations)
    ):
        raise ResultSealError(f"{label} Work has an invalid inline result")
    projected: list[dict[str, object]] = []
    for item in observations:
        observation = {
            key: item[key]
            for key in ("name", "status", "value", "confidence", "qualifications")
            if key in item
        }
        provenance = item.get("provenance")
        summary = "reusable external coordinate observation"
        if isinstance(provenance, dict):
            summary = (
                ", ".join(
                    f"{key}={value}"
                    for key, value in provenance.items()
                    if key != "basis_work_ids"
                )
                or summary
            )
        observation["basis"] = {
            "summary": summary,
            "refs": [{"kind": "source_item", "ref": source_ref}],
        }
        projected.append(observation)
    return projected


def _metadata_result_observations(
    output: object,
    source_refs: dict[str, str],
) -> list[dict[str, object]]:
    if not isinstance(output, dict) or not isinstance(output.get("observations"), list):
        raise ResultSealError("metadata Work has an invalid inline result")
    projected: list[dict[str, object]] = []
    for item in output["observations"]:
        if not isinstance(item, dict):
            raise ResultSealError("metadata Work contains an invalid observation")
        observation = {
            key: item[key]
            for key in ("name", "status", "value", "confidence", "qualifications")
            if key in item
        }
        provenance = item.get("provenance")
        if isinstance(provenance, dict):
            refs: list[dict[str, str]] = []
            relative_paths: list[str] = []
            relative = provenance.get("relative_path")
            if isinstance(relative, str):
                relative_paths.append(relative)
            sources = provenance.get("sources")
            if isinstance(sources, list):
                relative_paths.extend(
                    str(source["relative_path"])
                    for source in sources
                    if isinstance(source, dict)
                    and isinstance(source.get("relative_path"), str)
                )
            for relative_path in dict.fromkeys(relative_paths):
                if relative_path in source_refs:
                    refs.append(
                        {"kind": "source_item", "ref": source_refs[relative_path]}
                    )
            details = ", ".join(
                f"{key}={value}"
                for key, value in provenance.items()
                if key not in {"relative_path", "sources"}
            )
            basis: dict[str, object] = {
                "summary": details or "local ExifTool metadata extraction"
            }
            if refs:
                basis["refs"] = refs
            observation["basis"] = basis
        projected.append(observation)
    return projected


def _load_source_observation_work(
    connection: sqlite3.Connection,
    run_id: str,
    source_rows: list[sqlite3.Row],
    work_ids: tuple[str, ...],
    *,
    capability: str,
    label: str,
) -> dict[str, sqlite3.Row]:
    known_sources = {str(row["relative_path"]) for row in source_rows}
    selected: dict[str, sqlite3.Row] = {}
    for work_id in work_ids:
        work = connection.execute(
            """
            SELECT work_records.* FROM run_work_records
            JOIN work_records USING (work_id)
            WHERE run_work_records.run_id = ?
              AND work_records.work_id = ?
              AND work_records.capability = ?
            """,
            (run_id, work_id, capability),
        ).fetchone()
        if work is None:
            raise ResultSealError(
                f"selected {label} Work is not attached to this run: {work_id}"
            )
        subject = connection.execute(
            """
            SELECT dependency_value FROM work_dependencies
            WHERE work_id = ? AND dependency_kind = ?
              AND dependency_key = 'subject_relative_path'
            """,
            (work_id, DependencyKind.PARAMETER),
        ).fetchone()
        if subject is None or str(subject["dependency_value"]) not in known_sources:
            raise ResultSealError(f"{label} Work has an invalid subject: {work_id}")
        relative_path = str(subject["dependency_value"])
        if relative_path in selected:
            raise ResultSealError(
                f"multiple selected {label} Work Records for one source: {relative_path}"
            )
        selected[relative_path] = work
    return selected


def _load_source_artifact_work(
    connection: sqlite3.Connection,
    run_id: str,
    source_rows: list[sqlite3.Row],
    work_ids: tuple[str, ...],
    *,
    capability: str,
    label: str,
) -> dict[str, list[sqlite3.Row]]:
    known_sources = {str(row["relative_path"]) for row in source_rows}
    selected: dict[str, list[sqlite3.Row]] = {}
    for work_id in work_ids:
        work = connection.execute(
            """
            SELECT work_records.* FROM run_work_records
            JOIN work_records USING (work_id)
            WHERE run_work_records.run_id = ?
              AND work_records.work_id = ?
              AND work_records.capability = ?
            """,
            (run_id, work_id, capability),
        ).fetchone()
        if work is None:
            raise ResultSealError(
                f"selected {label} Work is not attached to this run: {work_id}"
            )
        subject = connection.execute(
            """
            SELECT dependency_value FROM work_dependencies
            WHERE work_id = ? AND dependency_kind = ?
              AND dependency_key = 'subject_relative_path'
            """,
            (work_id, DependencyKind.PARAMETER),
        ).fetchone()
        if subject is None or str(subject["dependency_value"]) not in known_sources:
            raise ResultSealError(f"{label} Work has an invalid subject: {work_id}")
        selected.setdefault(str(subject["dependency_value"]), []).append(work)
    return selected


def _load_compression_groups(
    connection: sqlite3.Connection,
    run_id: str,
    source_rows: list[sqlite3.Row],
    work_ids: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
    known_sources = {str(row["relative_path"]) for row in source_rows}
    groups = []
    for work_id in work_ids:
        work = connection.execute(
            """
            SELECT work_records.* FROM run_work_records
            JOIN work_records USING (work_id)
            WHERE run_work_records.run_id = ?
              AND work_records.work_id = ?
              AND work_records.capability = 'adaptive-compression-group'
              AND work_records.status = ?
            """,
            (run_id, work_id, WorkStatus.SUCCEEDED),
        ).fetchone()
        if work is None:
            raise ResultSealError(
                f"selected compression Work is not eligible: {work_id}"
            )
        output = json.loads(work["output_json"])
        group = output.get("group")
        if not isinstance(group, dict):
            raise ResultSealError("compression Work has an invalid inline result")
        member_rows = connection.execute(
            """
            SELECT dependency_key FROM work_dependencies
            WHERE work_id = ? AND dependency_kind = ?
            ORDER BY dependency_key
            """,
            (work_id, DependencyKind.SOURCE_REVISION),
        ).fetchall()
        try:
            members = tuple(
                dict.fromkeys(
                    str(json.loads(row["dependency_key"])[1]) for row in member_rows
                )
            )
        except (IndexError, TypeError, ValueError) as error:
            raise ResultSealError(
                "compression Work has invalid source dependencies"
            ) from error
        representative = group.get("representative_path")
        boundary_paths = group.get("boundary_paths")
        conflict_paths = group.get("conflict_paths")
        outlier_paths = group.get("outlier_paths")
        if (
            not members
            or not set(members) <= known_sources
            or representative not in members
            or group.get("member_count") != len(members)
            or not isinstance(boundary_paths, list)
            or not set(boundary_paths) <= set(members)
            or not isinstance(conflict_paths, list)
            or not set(conflict_paths) <= set(members)
            or not isinstance(outlier_paths, list)
            or not set(outlier_paths) <= set(members)
        ):
            raise ResultSealError("compression Work membership is invalid")
        groups.append(
            {
                **group,
                "members": members,
                "work_id": work_id,
            }
        )
    return tuple(groups)


def _load_source_observation_works(
    connection: sqlite3.Connection,
    run_id: str,
    source_rows: list[sqlite3.Row],
    work_ids: tuple[str, ...],
    *,
    capability: str,
    label: str,
) -> dict[str, list[sqlite3.Row]]:
    known_sources = {str(row["relative_path"]) for row in source_rows}
    selected: dict[str, list[sqlite3.Row]] = {}
    for work_id in work_ids:
        work = connection.execute(
            """
            SELECT work_records.* FROM run_work_records
            JOIN work_records USING (work_id)
            WHERE run_work_records.run_id = ?
              AND work_records.work_id = ?
              AND work_records.capability = ?
            """,
            (run_id, work_id, capability),
        ).fetchone()
        if work is None:
            raise ResultSealError(
                f"selected {label} Work is not attached to this run: {work_id}"
            )
        subject = connection.execute(
            """
            SELECT dependency_value FROM work_dependencies
            WHERE work_id = ? AND dependency_kind = ?
              AND dependency_key = 'subject_relative_path'
            """,
            (work_id, DependencyKind.PARAMETER),
        ).fetchone()
        if subject is None or str(subject["dependency_value"]) not in known_sources:
            raise ResultSealError(f"{label} Work has an invalid subject: {work_id}")
        selected.setdefault(str(subject["dependency_value"]), []).append(work)
    return selected


@contextmanager
def _connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
    finally:
        connection.close()
