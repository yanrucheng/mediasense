"""Load selected Work and project bounded source observations for Result assembly."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from typing import Iterator

from ._result_types import ResultSealError, result_local_reference
from ._work_types import DependencyKind, WorkStatus


def _load_mapped_observation_work(
    connection: sqlite3.Connection,
    run_id: str,
    known_sources: Set[str],
    work_by_source: Mapping[Path | str, str],
    *,
    capability: str,
    label: str,
) -> dict[str, sqlite3.Row]:
    """Load one reusable observation Work explicitly mapped to each source."""

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
    source_observations: Iterable[Mapping[str, object]] = (),
    acquisition_policy: Mapping[str, object] | None = None,
) -> list[dict[str, object]]:
    from .geocode import normalize_geo_observations

    output = json.loads(work["output_json"])
    projected = []
    for item in normalize_geo_observations(output):
        observation = dict(item)
        observation["basis"] = {
            **item["basis"],
            "refs": [{"kind": "source_item", "ref": source_ref}],
        }
        source_coordinates = {
            o["name"]: o["value"]
            for o in source_observations
            if o.get("name") in {"gps_coordinates", "gpx_coordinates"}
            and o.get("status") == "available"
        }
        selected_name = (
            "gpx_coordinates"
            if "gpx_coordinates" in source_coordinates
            else "gps_coordinates"
        )
        coordinate = source_coordinates.get(selected_name)
        query_coordinate = observation["basis"].get("query_coordinate")
        projection = {
            "source_item_ref": source_ref,
            "source_coordinate_observation": selected_name,
            "source_coordinate": coordinate,
            "query_coordinate": query_coordinate,
        }
        if acquisition_policy is not None:
            projection["acquisition_policy"] = dict(acquisition_policy)
        if (
            coordinate is not None
            and query_coordinate is not None
            and coordinate != query_coordinate
        ):
            from .geocode import _distance_meters
            from mediasense.capabilities.geo import GeoCoordinate, MapDatum

            if coordinate["datum"] == query_coordinate["datum"]:
                projection["query_point_distance_meters"] = _distance_meters(
                    GeoCoordinate(
                        coordinate["latitude"],
                        coordinate["longitude"],
                        MapDatum(coordinate["datum"]),
                    ),
                    GeoCoordinate(
                        query_coordinate["latitude"],
                        query_coordinate["longitude"],
                        MapDatum(query_coordinate["datum"]),
                    ),
                )
            observation.setdefault("qualifications", []).append(
                {
                    "code": "geo_query_point_reused",
                    "effect": "limits_interpretation",
                    "message": "This candidate was acquired at another source coordinate. Candidate distances refer to the query point; nearby media can occupy different venues.",
                }
            )
        observation["basis"]["projection"] = projection
        projected.append(observation)
    return projected


def _has_available_coordinate(
    observations: Iterable[Mapping[str, object]],
) -> bool:
    return any(
        observation.get("name") in {"gps_coordinates", "gpx_coordinates"}
        and observation.get("status") == "available"
        and isinstance(observation.get("value"), Mapping)
        for observation in observations
    )


def _metadata_result_observations(
    output: object,
    run_id: str,
) -> list[dict[str, object]]:
    if not isinstance(output, dict) or not isinstance(output.get("observations"), list):
        raise ResultSealError("metadata Work has an invalid inline result")
    projected: list[dict[str, object]] = []
    for item in output["observations"]:
        if not isinstance(item, dict):
            raise ResultSealError("metadata Work contains an invalid observation")
        observation = {
            key: item[key]
            for key in (
                "name",
                "status",
                "value",
                "confidence",
                "qualifications",
                "basis",
                "provenance",
            )
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
                refs.append(
                    {
                        "kind": "source_item",
                        "ref": result_local_reference(
                            "source-item", run_id, relative_path
                        ),
                    }
                )
            details = ", ".join(
                f"{key}={value}"
                for key, value in provenance.items()
                if key
                not in {"relative_path", "sources", "candidates", "input_work_id"}
            )
            basis: dict[str, object] = {
                "summary": details or "local ExifTool metadata extraction"
            }
            if refs:
                basis["refs"] = refs

            observation["provenance"] = _public_metadata_value(provenance, run_id)
            # Selection/rejection evidence belongs to the producer. A fallback
            # description of provenance must never replace that existing basis.
            observation.setdefault("basis", basis)
        if "basis" in observation:
            observation["basis"] = _public_metadata_value(observation["basis"], run_id)
        if isinstance(output.get("producer"), Mapping):
            observation.setdefault("provenance", {})["producer"] = dict(
                output["producer"]
            )
        projected.append(observation)
    return projected


def _public_metadata_value(value, run_id):
    if isinstance(value, list):
        return [_public_metadata_value(item, run_id) for item in value]
    if isinstance(value, dict):
        return {
            ("source_item_ref" if key == "relative_path" else key): (
                result_local_reference("source-item", run_id, child)
                if key == "relative_path" and isinstance(child, str)
                else _public_metadata_value(child, run_id)
            )
            for key, child in value.items()
        }
    return value


def _load_source_observation_work(
    connection: sqlite3.Connection,
    run_id: str,
    known_sources: Set[str],
    work_ids: tuple[str, ...],
    *,
    capability: str,
    label: str,
) -> dict[str, sqlite3.Row]:
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
    known_sources: Set[str],
    work_ids: tuple[str, ...],
    *,
    capability: str,
    label: str,
) -> dict[str, list[sqlite3.Row]]:
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
    known_sources: Set[str],
    work_ids: tuple[str, ...],
) -> tuple[dict[str, object], ...]:
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
    known_sources: Set[str],
    work_ids: tuple[str, ...],
    *,
    capability: str,
    label: str,
) -> dict[str, list[sqlite3.Row]]:
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
    from ._sqlite_scope import connect

    with connect(database_path) as connection:
        yield connection
