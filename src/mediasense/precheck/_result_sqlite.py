"""Private SQLite and filesystem adapter for immutable PreCheck Results."""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from typing import Iterator
from uuid import uuid4

from ._accounting_types import WorkingRunStatus
from ._fingerprint import SourceChangedDuringRead, stat_identity
from ._result_types import (
    ResultAudit,
    ResultDraft,
    ResultSealError,
    SealedResult,
    source_root_reference,
)
from ._result_work_projection import (
    _has_available_coordinate,
    _has_complete_place_outcome,
)
from ._working_schema import SCHEMA_VERSION
from ._work_types import DependencyKind, WorkStatus
from .artifact import ArtifactStore
from .source_validity import SourceValidityStore


class SQLiteResultStore:
    """Validate and atomically publish immutable result packages."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self.workspace = self.database_path.parent.absolute()
        self.results_root = self.workspace / "_results"
        self.unpublished_root = self.results_root / "unpublished"
        self.published_root = self.results_root / "sealed"
        self.artifacts = ArtifactStore(self.database_path)
        self.source_validity = SourceValidityStore(self.database_path)
        self._verify_schema()

    def seal(
        self,
        draft: ResultDraft,
        *,
        result_ref: str | None = None,
    ) -> SealedResult:
        artifact_ids = self._validate(draft)
        result_ref = result_ref or f"precheck-result:{uuid4().hex}"
        _validate_result_ref(result_ref)
        existing = self._matching_registered_result(draft, result_ref)
        if existing is not None:
            return existing
        published_at = datetime.now(timezone.utc)
        package = _package(draft, result_ref, published_at)
        encoded = _encode_package(package)
        digest = hashlib.sha256(encoded).hexdigest()
        self.unpublished_root.mkdir(parents=True, exist_ok=True)
        self.published_root.mkdir(parents=True, exist_ok=True)
        temporary = self.unpublished_root / f"{uuid4().hex}.json.part"
        self._write_unpublished_result(temporary, encoded)
        final_path = (
            self.published_root / f"{result_ref.removeprefix('precheck-result:')}.json"
        )
        try:
            os.link(temporary, final_path)
        except FileExistsError:
            temporary.unlink(missing_ok=True)
            published_at, encoded = _recover_unregistered_publication(
                final_path,
                draft,
                result_ref,
            )
            digest = hashlib.sha256(encoded).hexdigest()
            final_path.chmod(0o444)
            _fsync_directory(final_path.parent)
        else:
            temporary.unlink()
            final_path.chmod(0o444)
            _fsync_directory(final_path.parent)
            self._after_file_published(final_path)

        relative_path = final_path.relative_to(self.workspace).as_posix()
        timestamp = published_at.isoformat(timespec="microseconds")
        self._validate_source_verifications(draft)
        with self._transaction() as connection:
            self._validate_final_pins(connection, draft)
            registered = connection.execute(
                "SELECT * FROM sealed_results WHERE result_ref = ?", (result_ref,)
            ).fetchone()
            if registered is None:
                connection.execute(
                    """
                    INSERT INTO sealed_results (
                        result_ref, dataset_id, relative_path, digest_algorithm,
                        digest, size_bytes, published_at
                    ) VALUES (?, ?, ?, 'sha256', ?, ?, ?)
                    """,
                    (
                        result_ref,
                        draft.dataset_id,
                        relative_path,
                        digest,
                        len(encoded),
                        timestamp,
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO result_artifacts (result_ref, artifact_id)
                    VALUES (?, ?)
                    """,
                    ((result_ref, artifact_id) for artifact_id in artifact_ids),
                )
                connection.executemany(
                    """
                    INSERT INTO result_work_records (result_ref, work_id)
                    VALUES (?, ?)
                    """,
                    (
                        (result_ref, work_id)
                        for work_id in dict.fromkeys(draft.supporting_work_ids)
                    ),
                )
            elif (
                str(registered["dataset_id"]),
                str(registered["relative_path"]),
                str(registered["digest"]),
                int(registered["size_bytes"]),
                str(registered["published_at"]),
            ) != (
                draft.dataset_id,
                relative_path,
                digest,
                len(encoded),
                timestamp,
            ):
                raise ResultSealError("Result reference is bound to different content")
        return SealedResult(
            result_ref=result_ref,
            dataset_id=draft.dataset_id,
            path=final_path,
            digest=digest,
            size_bytes=len(encoded),
            published_at=published_at,
        )

    def _matching_registered_result(
        self,
        draft: ResultDraft,
        result_ref: str,
    ) -> SealedResult | None:
        try:
            result = self.get(result_ref)
        except KeyError:
            return None
        try:
            encoded = result.path.read_bytes()
        except OSError as error:
            raise ResultSealError(
                "Previously registered Result bytes are unavailable"
            ) from error
        expected_value = _package(draft, result_ref, result.published_at)
        expected = _encode_package(expected_value)
        digest = hashlib.sha256(encoded).hexdigest()
        try:
            existing_value = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError):
            existing_value = None
        if (
            (
                encoded != expected
                and _recovery_semantics(existing_value)
                != _recovery_semantics(expected_value)
            )
            or len(encoded) != result.size_bytes
            or digest != result.digest
        ):
            raise ResultSealError(
                "Result reference is already registered with different or corrupt content"
            )
        return result

    def get(self, result_ref: str) -> SealedResult:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sealed_results WHERE result_ref = ?", (result_ref,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown sealed Result: {result_ref}")
        return _sealed_from_row(self.workspace, row)

    def audit(self) -> ResultAudit:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sealed_results ORDER BY result_ref"
            ).fetchall()
            referenced = {str(row["relative_path"]) for row in rows}
        available: list[str] = []
        missing: list[str] = []
        corrupt: list[str] = []
        for row in rows:
            path = self.workspace / str(row["relative_path"])
            if not path.is_file():
                missing.append(str(row["result_ref"]))
                continue
            digest, size = _digest_file(path)
            if digest != row["digest"] or size != int(row["size_bytes"]):
                corrupt.append(str(row["result_ref"]))
            else:
                available.append(str(row["result_ref"]))
        paths = (
            tuple(path for path in self.published_root.iterdir() if path.is_file())
            if self.published_root.exists()
            else ()
        )
        orphan_paths = tuple(
            sorted(
                path
                for path in paths
                if path.relative_to(self.workspace).as_posix() not in referenced
            )
        )
        unpublished_paths = (
            tuple(
                sorted(
                    path for path in self.unpublished_root.iterdir() if path.is_file()
                )
            )
            if self.unpublished_root.exists()
            else ()
        )
        return ResultAudit(
            available=tuple(available),
            missing=tuple(missing),
            corrupt=tuple(corrupt),
            orphan_paths=orphan_paths,
            unpublished_paths=unpublished_paths,
        )

    def _validate(self, draft: ResultDraft) -> tuple[str, ...]:
        _validate_contract_values(draft)
        if draft.coverage not in {"complete", "partial"}:
            raise ResultSealError("unknown Result coverage")
        if draft.readiness not in {"plan_ready", "blocked"}:
            raise ResultSealError("unknown Result readiness")
        if draft.integrity not in {"valid", "invalid"}:
            raise ResultSealError("unknown Result integrity")
        if (
            draft.coverage == "partial"
            or draft.readiness == "blocked"
            or draft.integrity == "invalid"
        ) and not draft.qualifications:
            raise ResultSealError(
                "partial, blocked, or invalid Result requires a qualification"
            )
        _validate_execution_boundary(draft.execution_boundary)

        with self._connect() as connection:
            run = connection.execute(
                "SELECT dataset_id, status, reuse_domain FROM working_runs WHERE run_id = ?",
                (draft.run_id,),
            ).fetchone()
            if run is None or str(run["dataset_id"]) != draft.dataset_id:
                raise ResultSealError("Result draft does not match its Working Run")
            if WorkingRunStatus(run["status"]) not in {
                WorkingRunStatus.COMPLETED,
                WorkingRunStatus.COMPLETED_WITH_ISSUES,
            }:
                raise ResultSealError("source accounting is not closed")
            self._validate_supporting_work(connection, draft)
            accounted = {
                str(row["relative_path"]): str(row["scope"])
                for row in connection.execute(
                    "SELECT relative_path, scope FROM run_items WHERE run_id = ?",
                    (draft.run_id,),
                )
            }
            has_unaccounted_issue = connection.execute(
                """
                SELECT 1 FROM run_issues
                WHERE run_issues.run_id = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM run_items
                      WHERE run_items.run_id = run_issues.run_id
                        AND run_items.relative_path = run_issues.relative_path
                  )
                LIMIT 1
                """,
                (draft.run_id,),
            ).fetchone()
            expected_source_root_ref = source_root_reference(
                draft.dataset_id, str(run["reuse_domain"])
            )
        if any(
            source.locator.get("source_root_ref") != expected_source_root_ref
            for source in draft.sources
        ):
            raise ResultSealError(
                "Source Item root does not match its current Working Run"
            )
        self._validate_source_verifications(draft)
        if has_unaccounted_issue is not None and draft.coverage != "partial":
            raise ResultSealError(
                "known unenumerated discovery region requires partial coverage"
            )
        source_paths = {source.relative_path.as_posix() for source in draft.sources}
        if len(source_paths) != len(draft.sources) or source_paths != accounted.keys():
            raise ResultSealError(
                "accounts_for does not exactly match accounting closure"
            )
        for source in draft.sources:
            if source.scope not in {"source_media", "auxiliary", "excluded"}:
                raise ResultSealError("unknown accounts_for scope")
            if source.condition not in {
                "usable",
                "unsupported",
                "invalid",
                "error",
                "unresolved",
            }:
                raise ResultSealError("unknown accounts_for condition")
            if source.scope != accounted[source.relative_path.as_posix()]:
                raise ResultSealError("Result cannot rewrite accounted source scope")
            if (
                draft.readiness == "plan_ready"
                and
                source.scope == "source_media"
                and _has_available_coordinate(source.observations)
                and not _has_complete_place_outcome(source.observations)
            ):
                raise ResultSealError("located Source Item lacks a complete place outcome")

        sources = {source.ref: source for source in draft.sources}
        evidence = {item.ref: item for item in draft.evidence}
        if len(sources) != len(draft.sources) or len(evidence) != len(draft.evidence):
            raise ResultSealError("Result-scoped references must be unique")
        if not set(draft.entry_evidence) <= evidence.keys():
            raise ResultSealError("entry_evidence references an unknown Evidence item")

        reachable = set(draft.entry_evidence)
        graph: dict[str, set[str]] = {}
        derived_by_evidence: dict[str, set[str]] = {}
        for relation in draft.relationships:
            if relation.origin_ref not in evidence:
                raise ResultSealError("relationship origin is not Evidence")
            if relation.target_kind not in {"source_item", "evidence"}:
                raise ResultSealError("unknown relationship target kind")
            targets = sources if relation.target_kind == "source_item" else evidence
            if relation.target_ref not in targets:
                raise ResultSealError("relationship target is outside this Result")
            if relation.relation == "represents":
                if relation.target_kind != "source_item" or relation.basis is None:
                    raise ResultSealError(
                        "represents requires Source Item target and basis"
                    )
                graph.setdefault(relation.origin_ref, set()).add(relation.target_ref)
            elif relation.relation == "expands_to":
                graph.setdefault(relation.origin_ref, set()).add(relation.target_ref)
            elif relation.relation == "derived_from":
                derived_by_evidence.setdefault(relation.origin_ref, set()).add(
                    relation.target_ref
                )
            else:
                raise ResultSealError(f"unknown relationship: {relation.relation}")
        queue = list(reachable)
        while queue:
            current = queue.pop()
            for target in graph.get(current, set()):
                if target not in reachable:
                    reachable.add(target)
                    if target in evidence:
                        queue.append(target)
        missing_navigation = [
            source.ref
            for source in draft.sources
            if source.scope == "source_media"
            and source.condition == "usable"
            and source.ref not in reachable
        ]
        if missing_navigation:
            raise ResultSealError(
                "usable Source Items lack a frontier navigation path: "
                + ", ".join(missing_navigation)
            )

        artifact_ids: list[str] = []
        for item in draft.evidence:
            if item.artifact_id is None:
                continue
            if item.work_id is None:
                raise ResultSealError("Artifact Evidence must retain producing Work")
            artifact = self.artifacts.require_available(item.artifact_id)
            if item.access != {
                "kind": "local_artifact",
                "locator": {"kind": "local_file_path", "value": str(artifact.path)},
            }:
                raise ResultSealError("Evidence access does not match its Artifact")
            with self._connect() as connection:
                linked = connection.execute(
                    """
                    SELECT 1 FROM work_artifacts
                    JOIN work_records USING (work_id)
                    JOIN run_work_records USING (work_id)
                    WHERE work_artifacts.work_id = ?
                      AND work_artifacts.artifact_id = ?
                      AND work_records.status = ?
                      AND run_work_records.run_id = ?
                    """,
                    (
                        item.work_id,
                        item.artifact_id,
                        WorkStatus.SUCCEEDED,
                        draft.run_id,
                    ),
                ).fetchone()
                source_dependencies: set[str] = set()
                for row in connection.execute(
                    """
                        SELECT dependency_key FROM work_dependencies
                        WHERE work_id = ? AND dependency_kind = ?
                        """,
                    (item.work_id, DependencyKind.SOURCE_CONTENT),
                ):
                    try:
                        source_dataset, source_path = json.loads(row["dependency_key"])
                    except (TypeError, ValueError) as error:
                        raise ResultSealError(
                            "Artifact Work has an invalid source dependency"
                        ) from error
                    if source_dataset != draft.dataset_id:
                        raise ResultSealError(
                            "Artifact Work source dependency is outside this Dataset"
                        )
                    source_dependencies.add(str(source_path))
            if linked is None:
                raise ResultSealError("Artifact is not bound to successful Work")
            derived_sources = {
                sources[ref].relative_path.as_posix()
                for ref in derived_by_evidence.get(item.ref, set())
                if ref in sources
            }
            if not derived_sources or not derived_sources <= source_dependencies:
                raise ResultSealError("derived_from does not match production inputs")
            artifact_ids.append(item.artifact_id)
        return tuple(sorted(set(artifact_ids)))

    def _validate_source_verifications(self, draft: ResultDraft) -> None:
        for source in draft.sources:
            observations = tuple(
                observation
                for observation in source.observations
                if observation.get("name") == "source_content_verification"
            )
            if not observations:
                continue
            if len(observations) != 1:
                raise ResultSealError(
                    "Source Item has multiple content verification observations"
                )
            value = observations[0].get("value")
            if not isinstance(value, Mapping):
                raise ResultSealError("source verification value is invalid")
            try:
                current = self.source_validity.prove(draft.run_id, source.relative_path)
            except (KeyError, OSError, ValueError, SourceChangedDuringRead) as error:
                raise ResultSealError(
                    f"source verification failed at seal: {source.relative_path}"
                ) from error
            if (
                value.get("profile") != current.algorithm
                or value.get("value") != f"sha256:{current.digest}"
                or value.get("size_bytes") != current.size_bytes
            ):
                raise ResultSealError(
                    f"source verification changed before seal: {source.relative_path}"
                )

    def _validate_final_pins(
        self,
        connection: sqlite3.Connection,
        draft: ResultDraft,
    ) -> None:
        """Recheck pin eligibility at the final Result registration boundary."""

        self._validate_supporting_work(connection, draft)
        verified_artifacts: set[str] = set()
        for item in draft.evidence:
            if item.artifact_id is None or item.work_id is None:
                continue
            row = connection.execute(
                """
                SELECT artifacts.*
                FROM work_artifacts
                JOIN artifacts USING (artifact_id)
                JOIN work_records USING (work_id)
                JOIN run_work_records USING (work_id)
                WHERE artifacts.artifact_id = ?
                  AND work_artifacts.work_id = ?
                  AND artifacts.integrity_status = 'available'
                  AND work_records.status = ?
                  AND run_work_records.run_id = ?
                """,
                (
                    item.artifact_id,
                    item.work_id,
                    WorkStatus.SUCCEEDED,
                    draft.run_id,
                ),
            ).fetchone()
            if row is None:
                raise ResultSealError(
                    "Artifact-producing Work is no longer eligible for this Result: "
                    f"{item.work_id}"
                )
            if item.artifact_id in verified_artifacts:
                continue
            path = self.workspace / str(row["relative_path"])
            try:
                digest, size = _digest_file(path)
            except OSError as error:
                raise ResultSealError(
                    f"Artifact is unavailable during Result seal: {item.artifact_id}"
                ) from error
            if digest != row["digest"] or size != int(row["size_bytes"]):
                raise ResultSealError(
                    f"Artifact integrity changed during Result seal: {item.artifact_id}"
                )
            verified_artifacts.add(item.artifact_id)

    def _validate_supporting_work(
        self,
        connection: sqlite3.Connection,
        draft: ResultDraft,
    ) -> None:
        eligible = {
            str(row["work_id"]): WorkStatus(row["status"])
            for row in connection.execute(
                """
                SELECT work_records.work_id, work_records.status
                FROM run_work_records
                JOIN work_records USING (work_id)
                WHERE run_work_records.run_id = ?
                """,
                (draft.run_id,),
            )
        }
        for work_id in draft.supporting_work_ids:
            if eligible.get(work_id) not in {
                WorkStatus.SUCCEEDED,
                WorkStatus.TERMINAL_FAILURE,
            }:
                raise ResultSealError(
                    "supporting Work (successful Work or recorded terminal failure) "
                    "is no longer eligible for this Result: "
                    f"{work_id}"
                )

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
            except sqlite3.OperationalError as error:
                raise RuntimeError(
                    "initialize the PreCheck working store before ResultStore"
                ) from error
        if row is None or int(row["version"]) != SCHEMA_VERSION:
            raise RuntimeError("unsupported or uninitialized internal schema")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
            except BaseException:
                connection.rollback()
                raise
            else:
                connection.commit()

    def _after_file_published(self, path: Path) -> None:
        """Fault-injection seam after atomic bytes publication, before DB commit."""

    def _write_unpublished_result(self, path: Path, encoded: bytes) -> None:
        """Write and durably close private bytes before atomic publication."""

        with path.open("xb") as output:
            output.write(encoded)
            output.flush()
            os.fsync(output.fileno())


def _validate_result_ref(result_ref: str) -> None:
    prefix = "precheck-result:"
    suffix = result_ref.removeprefix(prefix)
    if (
        not result_ref.startswith(prefix)
        or len(suffix) not in {32, 64}
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise ResultSealError("internal Result reference is invalid")


def _encode_package(package: Mapping[str, object]) -> bytes:
    return json.dumps(
        package,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _recover_unregistered_publication(
    path: Path,
    draft: ResultDraft,
    result_ref: str,
) -> tuple[datetime, bytes]:
    encoded = path.read_bytes()
    try:
        value = json.loads(encoded)
        timestamp = value["published_at"]
        if not isinstance(timestamp, str):
            raise TypeError
        published_at = datetime.fromisoformat(timestamp)
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise ResultSealError(
            "Existing unpublished Result target is not recoverable"
        ) from error
    if published_at.tzinfo is None:
        raise ResultSealError("Existing unpublished Result timestamp has no timezone")
    expected_value = _package(draft, result_ref, published_at)
    expected = _encode_package(expected_value)
    if encoded != expected and _recovery_semantics(value) != _recovery_semantics(
        expected_value
    ):
        raise ResultSealError(
            "Existing unpublished Result target belongs to different content"
        )
    return published_at, encoded


def _recovery_semantics(package: object) -> object:
    """Ignore only the repeatable proof timestamp when matching orphan bytes."""

    normalized = json.loads(_encode_package(package))
    if not isinstance(normalized, dict):
        return normalized
    for source in normalized.get("sources", []):
        view = source.get("view", {})
        for observation in view.get("observations", []):
            if observation.get("name") == "source_content_verification":
                value = observation.get("value", {})
                value.pop("observed_at", None)
    return normalized


def _package(
    draft: ResultDraft,
    result_ref: str,
    published_at: datetime,
) -> dict[str, object]:
    result_view: dict[str, object] = {
        "kind": "result",
        "ref": result_ref,
        "dataset_ref": draft.dataset_ref,
        "coverage": draft.coverage,
        "readiness": draft.readiness,
        "integrity": draft.integrity,
        "execution_boundary": draft.execution_boundary,
    }
    if draft.qualifications:
        result_view["qualifications"] = list(draft.qualifications)
    dataset_view: dict[str, object] = {"kind": "dataset", "ref": draft.dataset_ref}
    if draft.dataset_name:
        dataset_view["name"] = draft.dataset_name
    if draft.dataset_context:
        dataset_view["context"] = list(draft.dataset_context)
    source_records = []
    relationships = []
    for source in draft.sources:
        view: dict[str, object] = {
            "kind": "source_item",
            "ref": source.ref,
            "locator": source.locator,
        }
        if source.observations:
            view["observations"] = list(source.observations)
        if source.qualifications:
            view["qualifications"] = list(source.qualifications)
        source_records.append(
            {"relative_path": source.relative_path.as_posix(), "view": view}
        )
        member: dict[str, object] = {
            "target": source.ref,
            "scope": source.scope,
            "condition": source.condition,
        }
        if source.basis is not None:
            member["basis"] = source.basis
        if source.qualifications:
            member["qualifications"] = list(source.qualifications)
        relationships.append(
            {
                "origin": result_ref,
                "relation": "accounts_for",
                "target_kind": "source_item",
                "member": member,
            }
        )
    evidence_records = []
    for item in draft.evidence:
        view = {"kind": "evidence", "ref": item.ref, "access": item.access}
        if item.observations:
            view["observations"] = list(item.observations)
        if item.qualifications:
            view["qualifications"] = list(item.qualifications)
        evidence_records.append(
            {
                "artifact_id": item.artifact_id,
                "view": view,
                "work_id": item.work_id,
            }
        )
    relationships.extend(
        {
            "origin": result_ref,
            "relation": "entry_evidence",
            "target_kind": "evidence",
            "member": {"target": evidence_ref},
        }
        for evidence_ref in draft.entry_evidence
    )
    for relation in draft.relationships:
        member = {
            "target": (
                {"kind": relation.target_kind, "ref": relation.target_ref}
                if relation.relation in {"derived_from", "expands_to"}
                else relation.target_ref
            )
        }
        if relation.basis is not None:
            member["basis"] = relation.basis
        if relation.qualifications:
            member["qualifications"] = list(relation.qualifications)
        relationships.append(
            {
                "origin": relation.origin_ref,
                "relation": relation.relation,
                "target_kind": relation.target_kind,
                "member": member,
            }
        )
    return {
        "schema_version": 1,
        "published_at": published_at.isoformat(timespec="microseconds"),
        "result": result_view,
        "dataset": dataset_view,
        "sources": source_records,
        "evidence": evidence_records,
        "relationships": relationships,
        "artifact_refs": sorted(
            item.artifact_id for item in draft.evidence if item.artifact_id is not None
        ),
        "execution_boundary": draft.execution_boundary,
    }


def _validate_contract_values(draft: ResultDraft) -> None:
    """Reject internal drafts that could emit an invalid public read projection."""

    _nonempty(draft.dataset_id, "Dataset identity")
    _nonempty(draft.dataset_ref, "Dataset reference")
    if draft.dataset_name is not None:
        _nonempty(draft.dataset_name, "Dataset name")
    _validate_qualifications(draft.qualifications)
    for entry in draft.dataset_context:
        if (
            not isinstance(entry, dict)
            or not {"content", "provided_by"} <= entry.keys()
        ):
            raise ResultSealError("Dataset context requires content and provided_by")
        if set(entry) - {"content", "provided_by", "qualifications"}:
            raise ResultSealError("Dataset context contains unknown fields")
        _nonempty(entry["provided_by"], "Dataset context provider")
        if "qualifications" in entry and not entry["qualifications"]:
            raise ResultSealError("Dataset context qualifications cannot be empty")
        _validate_qualifications(tuple(entry.get("qualifications", ())))
    for source in draft.sources:
        _nonempty(source.ref, "Source Item reference")
        if source.relative_path.is_absolute() or source.relative_path == Path("."):
            raise ResultSealError("Source Item path must be relative")
        if ".." in source.relative_path.parts:
            raise ResultSealError("Source Item path must stay inside its Dataset")
        _validate_source_locator(source.locator, source.relative_path)
        if source.basis is not None:
            _validate_basis(source.basis)
        _validate_observations(source.observations)
        _validate_source_verification_shape(source.observations)
        _validate_qualifications(source.qualifications)
    source_refs = {source.ref for source in draft.sources}
    for item in draft.evidence:
        _nonempty(item.ref, "Evidence reference")
        _validate_access(item.access, source_refs)
        _validate_observations(item.observations)
        _validate_qualifications(item.qualifications)
        if item.access.get("kind") == "local_artifact":
            if item.artifact_id is None or item.work_id is None:
                raise ResultSealError(
                    "local Artifact Evidence requires Artifact and Work references"
                )
        elif item.artifact_id is not None or item.work_id is not None:
            raise ResultSealError(
                "only local Artifact Evidence may retain Artifact or Work references"
            )
    for evidence_ref in draft.entry_evidence:
        _nonempty(evidence_ref, "entry Evidence reference")
    for relation in draft.relationships:
        _nonempty(relation.origin_ref, "relationship origin")
        _nonempty(relation.target_ref, "relationship target")
        if relation.relation not in {"represents", "derived_from", "expands_to"}:
            raise ResultSealError(f"unknown relationship: {relation.relation}")
        if relation.target_kind not in {"source_item", "evidence"}:
            raise ResultSealError("unknown relationship target kind")
        if relation.basis is not None:
            _validate_basis(relation.basis)
        _validate_qualifications(relation.qualifications)


def _validate_execution_boundary(boundary: object) -> None:
    if not isinstance(boundary, Mapping):
        raise ResultSealError("Result execution boundary must be an object")
    if boundary.get("source_read_only") is not True:
        raise ResultSealError("Result cannot claim source-read-only execution")
    if boundary.get("remote_models") is not False:
        raise ResultSealError("PreCheck Result cannot include remote model effects")
    network_access = boundary.get("network_access")
    if network_access is False:
        if dict(boundary) != {
            "billable_calls": 0,
            "network_access": False,
            "remote_models": False,
            "source_read_only": True,
        }:
            raise ResultSealError("local-only Result has invalid effect evidence")
        return
    required = {
        "authorizations",
        "billable_calls",
        "logical_external_queries",
        "network_access",
        "provider_requests",
        "providers",
        "remote_models",
        "source_read_only",
    }
    if network_access is not True or set(boundary) != required:
        raise ResultSealError("external Result has incomplete effect evidence")
    logical_queries = boundary["logical_external_queries"]
    provider_requests = boundary["provider_requests"]
    if (
        not isinstance(logical_queries, int)
        or isinstance(logical_queries, bool)
        or logical_queries < 1
        or not isinstance(provider_requests, int)
        or isinstance(provider_requests, bool)
        or provider_requests < logical_queries
    ):
        raise ResultSealError("external Result request counts are invalid")
    billable_calls = boundary["billable_calls"]
    if billable_calls != "unknown" and (
        not isinstance(billable_calls, int)
        or isinstance(billable_calls, bool)
        or billable_calls < 0
    ):
        raise ResultSealError("external Result billable-call count is invalid")
    providers = boundary["providers"]
    if (
        not isinstance(providers, list)
        or not providers
        or any(not isinstance(item, str) or not item for item in providers)
    ):
        raise ResultSealError("external Result provider evidence is invalid")
    authorizations = boundary["authorizations"]
    if not isinstance(authorizations, list) or not authorizations:
        raise ResultSealError("external Result lacks authorization evidence")
    for authorization in authorizations:
        if not isinstance(authorization, Mapping) or set(authorization) != {
            "confirmed_at",
            "confirmed_content_identity",
            "confirmed_logical_queries",
            "decision",
            "pending_fingerprint",
            "principal_ref",
            "run_ref",
        }:
            raise ResultSealError("external Result authorization is invalid")
        if authorization.get("decision") != "proceed":
            raise ResultSealError("external Result was not authorized to proceed")
        quantity = authorization.get("confirmed_logical_queries")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            raise ResultSealError("external Result authorization count is invalid")
        _nonempty(authorization.get("run_ref"), "authorization Run reference")
        _nonempty(
            authorization.get("pending_fingerprint"),
            "authorization pending fingerprint",
        )
        if authorization.get("confirmed_content_identity") != authorization.get(
            "pending_fingerprint"
        ):
            raise ResultSealError("external Result authorization identity is invalid")
        _nonempty(authorization.get("principal_ref"), "authorization principal")
        _nonempty(authorization.get("confirmed_at"), "authorization timestamp")


def _validate_access(access: dict[str, object], source_refs: set[str]) -> None:
    if not isinstance(access, dict):
        raise ResultSealError("Evidence access must be an object")
    kind = access.get("kind")
    if kind == "local_artifact":
        if set(access) != {"kind", "locator"}:
            raise ResultSealError("local Artifact access has invalid fields")
        _validate_artifact_locator(access["locator"])
    elif kind == "source_item":
        if set(access) != {"kind", "source_item_ref"}:
            raise ResultSealError("Source Item access has invalid fields")
        ref = _nonempty(access["source_item_ref"], "Source Item access reference")
        if ref not in source_refs:
            raise ResultSealError("Evidence access references an unknown Source Item")
    elif kind == "inline":
        if set(access) != {"kind", "value"}:
            raise ResultSealError("inline Evidence access has invalid fields")
    else:
        raise ResultSealError("unknown Evidence access kind")


def _validate_artifact_locator(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"kind", "value"}:
        raise ResultSealError("Artifact locator requires exactly kind and value")
    if value["kind"] != "local_file_path":
        raise ResultSealError("Artifact locator has an invalid kind")
    _nonempty(value["value"], "Artifact locator value")


def _validate_source_locator(value: object, relative_path: Path) -> None:
    required = {"kind", "source_root_ref", "value"}
    if not isinstance(value, dict) or set(value) != required:
        raise ResultSealError(
            "Source Item locator requires kind, source_root_ref, and value"
        )
    if value["kind"] != "source_root_relative_path":
        raise ResultSealError("Source Item locator has an invalid kind")
    root_ref = _nonempty(value["source_root_ref"], "source root reference")
    if not root_ref.startswith("source-root:"):
        raise ResultSealError("source root reference has an invalid kind")
    if value["value"] != relative_path.as_posix():
        raise ResultSealError("Source Item locator does not match its relative path")


def _validate_observations(observations: tuple[dict[str, object], ...]) -> None:
    allowed = {
        "name",
        "status",
        "value",
        "basis",
        "confidence",
        "qualifications",
        "provenance",
    }
    statuses = {"available", "missing", "failed", "not_checked", "not_applicable"}
    for observation in observations:
        if not isinstance(observation, dict) or set(observation) - allowed:
            raise ResultSealError("Observation contains unknown fields")
        _nonempty(observation.get("name"), "Observation name")
        status = observation.get("status")
        if status not in statuses:
            raise ResultSealError("Observation has an unknown status")
        if status == "available" and "value" not in observation:
            raise ResultSealError("available Observation requires a value")
        if status == "failed" and "basis" not in observation:
            raise ResultSealError("failed Observation requires a basis")
        if status != "available" and "value" in observation:
            raise ResultSealError("non-available Observation cannot contain a value")
        if "basis" in observation:
            _validate_basis(observation["basis"])
        if "confidence" in observation:
            confidence = observation["confidence"]
            if (
                not isinstance(confidence, (int, float))
                or isinstance(confidence, bool)
                or not 0 <= confidence <= 1
            ):
                raise ResultSealError("Observation confidence must be from 0 to 1")
        if "qualifications" in observation and not observation["qualifications"]:
            raise ResultSealError("Observation qualifications cannot be empty")
        _validate_qualifications(tuple(observation.get("qualifications", ())))


def _validate_source_verification_shape(
    observations: tuple[dict[str, object], ...],
) -> None:
    selected = tuple(
        observation
        for observation in observations
        if observation.get("name") == "source_content_verification"
    )
    if len(selected) > 1:
        raise ResultSealError(
            "Source Item has multiple content verification observations"
        )
    if not selected:
        return
    observation = selected[0]
    value = observation.get("value")
    if observation.get("status") != "available" or not isinstance(value, Mapping):
        raise ResultSealError("source verification must be an available value")
    if set(value) != {
        "observed_at",
        "producer",
        "profile",
        "size_bytes",
        "value",
    }:
        raise ResultSealError("source verification value has invalid fields")
    for key in ("observed_at", "producer", "profile", "value"):
        _nonempty(value[key], f"source verification {key}")
    size_bytes = value["size_bytes"]
    if (
        not isinstance(size_bytes, int)
        or isinstance(size_bytes, bool)
        or size_bytes < 0
    ):
        raise ResultSealError("source verification size must be nonnegative")


def _validate_qualifications(qualifications: tuple[dict[str, object], ...]) -> None:
    for qualification in qualifications:
        if not isinstance(qualification, dict) or set(qualification) - {
            "code",
            "effect",
            "message",
            "basis",
        }:
            raise ResultSealError("Qualification contains unknown fields")
        _nonempty(qualification.get("code"), "Qualification code")
        _nonempty(qualification.get("message"), "Qualification message")
        if qualification.get("effect") not in {
            "limits_interpretation",
            "blocks_use",
        }:
            raise ResultSealError("Qualification has an unknown effect")
        if "basis" in qualification:
            _validate_basis(qualification["basis"])


def _validate_basis(basis: object) -> None:
    if isinstance(basis, str):
        _nonempty(basis, "basis")
        return
    if not isinstance(basis, dict) or not {"summary"} <= basis.keys():
        raise ResultSealError("basis must be text or a summary object")
    if set(basis) - {"summary", "refs"}:
        raise ResultSealError("basis contains unknown fields")
    _nonempty(basis["summary"], "basis summary")
    refs = basis.get("refs", ())
    if not isinstance(refs, (list, tuple)):
        raise ResultSealError("basis refs must be an array")
    for ref in refs:
        if (
            not isinstance(ref, dict)
            or set(ref) != {"kind", "ref"}
            or ref.get("kind") not in {"result", "dataset", "source_item", "evidence"}
        ):
            raise ResultSealError("basis contains an invalid typed reference")
        _nonempty(ref["ref"], "basis reference")


def _nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResultSealError(f"{label} must be a non-empty string")
    return value


def _digest_file(path: Path) -> tuple[str, int]:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise OSError(f"Result dependency is not a regular file: {path}")
        digest = hashlib.sha256()
        size = 0
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if stat_identity(before) != stat_identity(after):
        raise OSError(f"Result dependency changed while reading: {path}")
    return digest.hexdigest(), size


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _sealed_from_row(workspace: Path, row: sqlite3.Row) -> SealedResult:
    return SealedResult(
        result_ref=str(row["result_ref"]),
        dataset_id=str(row["dataset_id"]),
        path=workspace / str(row["relative_path"]),
        digest=str(row["digest"]),
        size_bytes=int(row["size_bytes"]),
        published_at=datetime.fromisoformat(str(row["published_at"])),
    )


__all__ = ["SQLiteResultStore"]
