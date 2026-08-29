"""Durable, read-only preparation for the first ``move_originals`` slice.

Preparation may read source bytes and filesystem metadata, but it never creates,
renames, copies, deletes, or changes metadata beneath a source or destination
binding.  The only writes are to the caller-selected Apply Run database.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path, PurePath
import sqlite3
import stat
from typing import Protocol
import unicodedata
from uuid import uuid4


_SCHEMA_VERSION = 1
_VERIFICATION_OBSERVATION = "source_content_verification"
_SUPPORTED_VERIFICATION_PROFILE = "sha256-full-v1"


class ApplyPreparationError(ValueError):
    """The supplied handoff or binding cannot produce a trustworthy Run."""


class IdempotencyConflict(ApplyPreparationError):
    """A request identity was reused for different preparation content."""


class SourceEvidenceError(ApplyPreparationError):
    """One selected Source Item cannot satisfy the Apply verification gate."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PrecheckReadBoundary(Protocol):
    """Structural boundary of the accepted ``mediasense.precheck.read`` Tool."""

    name: str

    def read(self, request: dict[str, object]) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class VerificationBasis:
    """Normalized Apply-grade evidence owned by one exact PreCheck Result."""

    profile: str
    value: str
    size_bytes: int
    observed_at: str
    producer: str
    basis: object
    limitations: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if self.profile != _SUPPORTED_VERIFICATION_PROFILE:
            raise SourceEvidenceError(
                "source_verification_profile_unsupported",
                f"unsupported source verification profile: {self.profile}",
            )
        if not self.value.startswith("sha256:") or len(self.value) != 71:
            raise SourceEvidenceError(
                "source_verification_invalid",
                "source verification needs a sha256 value",
            )
        try:
            int(self.value.removeprefix("sha256:"), 16)
        except ValueError as error:
            raise SourceEvidenceError(
                "source_verification_invalid",
                "source verification sha256 value is malformed",
            ) from error
        if self.size_bytes < 0:
            raise SourceEvidenceError(
                "source_verification_invalid",
                "source verification size must be non-negative",
            )
        _parse_timestamp(self.observed_at)
        _nonempty_string(self.producer, "verification producer")
        _validate_basis(self.basis)


@dataclass(frozen=True, slots=True)
class SourceItemEvidence:
    """One Result-scoped Source Item normalized from the public read boundary."""

    result_ref: str
    source_item_ref: str
    source_root_ref: str
    relative_path: str
    verification: VerificationBasis

    @classmethod
    def from_precheck_view(
        cls,
        *,
        result_ref: str,
        view: Mapping[str, object],
    ) -> SourceItemEvidence:
        if view.get("kind") != "source_item":
            raise SourceEvidenceError(
                "source_item_invalid", "PreCheck view is not a Source Item"
            )
        source_item_ref = _nonempty_string(view.get("ref"), "Source Item ref")
        locator = _mapping(view.get("locator"), "Source Item locator")
        if locator.get("kind") != "source_root_relative_path":
            raise SourceEvidenceError(
                "source_locator_invalid",
                f"{source_item_ref} has no source-root-relative locator",
            )
        try:
            relative_path = _safe_relative_path(
                _nonempty_string(locator.get("value"), "Source Item locator value")
            )
            source_root_ref = _nonempty_string(
                locator.get("source_root_ref"), "source root ref"
            )
        except ApplyPreparationError as error:
            raise SourceEvidenceError("source_locator_invalid", str(error)) from error
        if not source_root_ref.startswith("source-root:"):
            raise SourceEvidenceError(
                "source_locator_invalid",
                f"{source_item_ref} has an invalid source_root_ref",
            )

        observations = view.get("observations")
        if not isinstance(observations, list):
            raise SourceEvidenceError(
                "source_verification_missing",
                f"{source_item_ref} has no Apply-grade verification observation",
            )
        matches = [
            item
            for item in observations
            if isinstance(item, Mapping)
            and item.get("name") == _VERIFICATION_OBSERVATION
        ]
        if len(matches) != 1:
            code = (
                "source_verification_missing"
                if not matches
                else "source_verification_ambiguous"
            )
            raise SourceEvidenceError(
                code,
                f"{source_item_ref} must have exactly one Apply-grade verification observation",
            )
        observation = matches[0]
        if observation.get("status") != "available":
            raise SourceEvidenceError(
                "source_verification_unavailable",
                f"{source_item_ref} Apply-grade verification is not available",
            )
        value = _mapping(observation.get("value"), "verification value")
        limitations = observation.get("qualifications", [])
        if not isinstance(limitations, list) or not all(
            isinstance(item, Mapping) for item in limitations
        ):
            raise SourceEvidenceError(
                "source_verification_invalid",
                "verification qualifications must be structured objects",
            )
        try:
            verification = VerificationBasis(
                profile=_nonempty_string(value.get("profile"), "verification profile"),
                value=_nonempty_string(value.get("value"), "verification value"),
                size_bytes=_nonnegative_int(
                    value.get("size_bytes"), "verification size"
                ),
                observed_at=_nonempty_string(
                    value.get("observed_at"), "verification observation time"
                ),
                producer=_nonempty_string(
                    value.get("producer"), "verification producer"
                ),
                basis=observation.get("basis"),
                limitations=tuple(limitations),
            )
        except ApplyPreparationError as error:
            if isinstance(error, SourceEvidenceError):
                raise
            raise SourceEvidenceError(
                "source_verification_invalid", str(error)
            ) from error
        return cls(
            result_ref=_nonempty_string(result_ref, "PreCheck Result ref"),
            source_item_ref=source_item_ref,
            source_root_ref=source_root_ref,
            relative_path=relative_path,
            verification=verification,
        )


@dataclass(frozen=True, slots=True)
class SourceSetExpansion:
    """A complete, streaming expansion of one Frozen Plan source-set expression."""

    source_item_refs: Iterable[str]
    complete: bool


@dataclass(frozen=True, slots=True)
class PreparedRun:
    """Stable identity and current observable state of one prepared Run."""

    run_ref: str
    state: str
    prepared_revision: str | None
    prepared_content_identity: str | None


SourceSetResolver = Callable[[str, Mapping[str, object]], SourceSetExpansion]


class ApplyRunStore:
    """SQLite authority for mutable Apply Run preparation state.

    The store owns Run state and its operation ledger.  It neither owns Frozen
    Plan semantics nor PreCheck evidence, and it contains no media mutation API.
    """

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path)
        self._verify_schema()

    @classmethod
    def initialize(cls, database_path: Path) -> ApplyRunStore:
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA synchronous = FULL;
                PRAGMA foreign_keys = ON;

                CREATE TABLE internal_schema (
                    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                    version INTEGER NOT NULL
                );
                INSERT INTO internal_schema (singleton, version) VALUES (1, 1);

                CREATE TABLE runs (
                    run_ref TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL UNIQUE,
                    request_identity TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                        state IN (
                            'preparing', 'ready_for_authorization', 'blocked',
                            'cancelled'
                        )
                    ),
                    frozen_plan_ref TEXT NOT NULL,
                    frozen_plan_content_identity TEXT NOT NULL,
                    result_ref TEXT NOT NULL,
                    logical_root TEXT NOT NULL,
                    destination_parent TEXT NOT NULL,
                    destination_observed_identity TEXT NOT NULL,
                    execution_route TEXT,
                    prepared_revision TEXT,
                    prepared_content_identity TEXT,
                    plan_staged INTEGER NOT NULL DEFAULT 0 CHECK (plan_staged IN (0, 1))
                );

                CREATE TABLE source_roots (
                    run_ref TEXT NOT NULL REFERENCES runs(run_ref) ON DELETE CASCADE,
                    source_root_ref TEXT NOT NULL,
                    current_root TEXT NOT NULL,
                    observed_identity TEXT NOT NULL,
                    observed_device INTEGER NOT NULL,
                    PRIMARY KEY (run_ref, source_root_ref)
                );

                CREATE TABLE run_items (
                    run_ref TEXT NOT NULL REFERENCES runs(run_ref) ON DELETE CASCADE,
                    ordinal INTEGER NOT NULL,
                    source_item_ref TEXT NOT NULL,
                    planned_outcome TEXT CHECK (
                        planned_outcome IN ('materialize', 'retain', 'exclude')
                    ),
                    relative_directory TEXT,
                    override_name TEXT,
                    source_root_ref TEXT,
                    relative_source_path TEXT,
                    source_path TEXT,
                    intended_target TEXT,
                    target_comparison_key TEXT,
                    verification_profile TEXT,
                    expected_verification TEXT,
                    verification_observed_at TEXT,
                    verification_producer TEXT,
                    verification_basis_json TEXT,
                    verification_limitations_json TEXT,
                    observed_verification TEXT,
                    observed_device INTEGER,
                    observed_inode INTEGER,
                    observed_size INTEGER,
                    observed_mtime_ns INTEGER,
                    preparation_status TEXT NOT NULL DEFAULT 'pending' CHECK (
                        preparation_status IN ('pending', 'verified', 'blocked')
                    ),
                    issue_code TEXT,
                    PRIMARY KEY (run_ref, source_item_ref),
                    UNIQUE (run_ref, ordinal)
                );

                CREATE UNIQUE INDEX unique_materialized_target
                    ON run_items(run_ref, target_comparison_key)
                    WHERE planned_outcome = 'materialize'
                      AND target_comparison_key IS NOT NULL;

                CREATE TABLE findings (
                    run_ref TEXT NOT NULL REFERENCES runs(run_ref) ON DELETE CASCADE,
                    code TEXT NOT NULL,
                    source_item_ref TEXT NOT NULL DEFAULT '',
                    message TEXT NOT NULL,
                    PRIMARY KEY (run_ref, code, source_item_ref, message)
                );
                """
            )
        return cls(path)

    def prepare_forward(
        self,
        *,
        request_id: str,
        frozen_plan: Mapping[str, object],
        source_roots: Mapping[str, Path],
        destination_parent: Path,
        resolve_source_set: SourceSetResolver,
        precheck_read: PrecheckReadBoundary,
    ) -> PreparedRun:
        """Create or resume one deterministic, zero-media-effect forward Run."""

        plan = _validated_plan(frozen_plan)
        content = _mapping(plan["sealed_content"], "sealed content")
        plan_ref = _nonempty_string(content.get("plan_ref"), "Frozen Plan ref")
        plan_identity = _nonempty_string(
            _mapping(plan["seal"], "seal").get("content_identity"),
            "Frozen Plan content identity",
        )
        result_ref = _nonempty_string(content.get("result_ref"), "PreCheck Result ref")
        logical_root = _safe_segment(content.get("logical_root"), "logical root")
        destination = _strict_directory(destination_parent, "destination parent")
        destination_stat = destination.stat()
        destination_identity = _filesystem_identity(destination, destination_stat)
        normalized_roots = _observe_source_roots(source_roots)
        request_content = {
            "direction": "forward",
            "effect": "move_originals",
            "frozen_plan_ref": plan_ref,
            "frozen_plan_content_identity": plan_identity,
            "source_roots": [
                {
                    "source_root_ref": ref,
                    "current_root": str(path),
                    "observed_identity": identity,
                }
                for ref, (path, identity, _device) in sorted(normalized_roots.items())
            ],
            "destination_parent": str(destination),
            "destination_observed_identity": destination_identity,
        }
        request_identity = _content_identity(request_content)

        run_ref, existing = self._begin_run(
            request_id=request_id,
            request_identity=request_identity,
            plan_ref=plan_ref,
            plan_identity=plan_identity,
            result_ref=result_ref,
            logical_root=logical_root,
            destination=destination,
            destination_identity=destination_identity,
            source_roots=normalized_roots,
        )
        if existing.state in {"ready_for_authorization", "cancelled"}:
            return existing
        if existing.state == "blocked":
            self._reopen_blocked_preparation(run_ref)

        self._stage_plan(
            run_ref=run_ref,
            result_ref=result_ref,
            content=content,
            resolve_source_set=resolve_source_set,
        )

        if precheck_read.name != "mediasense.precheck.read":
            raise ApplyPreparationError(
                "source evidence must come from mediasense.precheck.read"
            )
        for source_item_ref in self._pending_materialization_refs(run_ref):
            try:
                item = _read_source_item(
                    precheck_read=precheck_read,
                    result_ref=result_ref,
                    source_item_ref=source_item_ref,
                )
            except SourceEvidenceError as error:
                self._block_item(
                    run_ref,
                    source_item_ref,
                    error.code,
                    str(error),
                )
                continue
            self._prepare_item(
                run_ref=run_ref,
                result_ref=result_ref,
                item=item,
                source_roots=normalized_roots,
                destination=destination,
                logical_root=logical_root,
            )

        self._finalize_preparation(run_ref, normalized_roots, destination_stat.st_dev)
        return self.get_run(run_ref)

    def _pending_materialization_refs(self, run_ref: str) -> Iterable[str]:
        after_ordinal = -1
        while True:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT ordinal, source_item_ref FROM run_items
                    WHERE run_ref = ? AND ordinal > ?
                      AND planned_outcome = 'materialize'
                      AND preparation_status <> 'verified'
                    ORDER BY ordinal LIMIT 1000
                    """,
                    (run_ref, after_ordinal),
                ).fetchall()
            if not rows:
                return
            for row in rows:
                after_ordinal = int(row["ordinal"])
                yield str(row["source_item_ref"])

    def get_run(self, run_ref: str) -> PreparedRun:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_ref, state, prepared_revision, prepared_content_identity
                FROM runs WHERE run_ref = ?
                """,
                (run_ref,),
            ).fetchone()
        if row is None:
            raise KeyError(run_ref)
        return PreparedRun(
            run_ref=str(row["run_ref"]),
            state=str(row["state"]),
            prepared_revision=row["prepared_revision"],
            prepared_content_identity=row["prepared_content_identity"],
        )

    def get_run_for_request(self, request_id: str) -> PreparedRun:
        """Resolve the durable Run created for one idempotent prepare request."""

        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_ref FROM runs WHERE request_id = ?", (request_id,)
            ).fetchone()
        if row is None:
            raise KeyError(request_id)
        return self.get_run(str(row["run_ref"]))

    def status(self, run_ref: str) -> dict[str, object]:
        """Return a review-contract-shaped bounded status view."""

        with self._connect() as connection:
            run = connection.execute(
                "SELECT * FROM runs WHERE run_ref = ?", (run_ref,)
            ).fetchone()
            if run is None:
                raise KeyError(run_ref)
            counts = connection.execute(
                """
                SELECT COUNT(*) AS scope_count,
                       SUM(planned_outcome = 'materialize') AS operation_count,
                       SUM(planned_outcome IN ('retain', 'exclude')) AS no_effect_count,
                       SUM(
                           planned_outcome = 'materialize'
                           AND preparation_status = 'verified'
                       ) AS verified_count
                FROM run_items WHERE run_ref = ?
                """,
                (run_ref,),
            ).fetchone()
            findings = [
                {"code": str(row["code"]), "message": str(row["message"])}
                for row in connection.execute(
                    """
                    SELECT code, message FROM findings
                    WHERE run_ref = ? ORDER BY code, source_item_ref, message
                    """,
                    (run_ref,),
                )
            ]
            roots = [
                {
                    "source_root_ref": str(row["source_root_ref"]),
                    "current_root": str(row["current_root"]),
                    "observed_identity": str(row["observed_identity"]),
                }
                for row in connection.execute(
                    """
                    SELECT source_root_ref, current_root, observed_identity
                    FROM source_roots WHERE run_ref = ? ORDER BY source_root_ref
                    """,
                    (run_ref,),
                )
            ]
        scope_count = int(counts["scope_count"] or 0)
        operation_count = int(counts["operation_count"] or 0)
        no_effect_count = int(counts["no_effect_count"] or 0)
        verified_count = int(counts["verified_count"] or 0)
        route = str(run["execution_route"] or "same_filesystem_atomic_move")
        summary = {
            "frozen_plan_ref": str(run["frozen_plan_ref"]),
            "frozen_plan_content_identity": str(run["frozen_plan_content_identity"]),
            "effect": "move_originals",
            "execution_binding": {
                "kind": "forward",
                "source_roots": roots,
                "destination_parent": str(run["destination_parent"]),
                "resolved_logical_root": str(
                    Path(run["destination_parent"]) / str(run["logical_root"])
                ),
                "destination_observed_identity": str(
                    run["destination_observed_identity"]
                ),
            },
            "execution_route": route,
            "metadata_preservation_profile": (
                "same_filesystem_rename_v1"
                if route == "same_filesystem_atomic_move"
                else "cross_filesystem_user_metadata_v1"
            ),
            "content_verification_profile": (
                "filesystem_identity_and_location"
                if route == "same_filesystem_atomic_move"
                else "byte_for_byte"
            ),
            "plan_scope_items": scope_count,
            "materialization_operations": operation_count,
            "no_effect_items": no_effect_count,
            "verified_sources": verified_count,
            "unique_targets": operation_count,
            "blockers": len(findings),
            "warnings": 0,
        }
        state = str(run["state"])
        allowed_actions = {
            "ready_for_authorization": ["execute", "cancel"],
            "blocked": ["resume", "cancel"],
        }.get(state, [])
        response: dict[str, object] = {
            "outcome": "ok",
            "action": "status",
            "run_ref": str(run["run_ref"]),
            "state": state,
            "progress": {
                "planned_operations": operation_count,
                "completed_and_verified": 0,
                "failed": 0,
                "remaining": operation_count,
                "indeterminate": 0,
            },
            "allowed_actions": allowed_actions,
        }
        if run["prepared_revision"] is not None:
            response.update(
                {
                    "prepared_revision": str(run["prepared_revision"]),
                    "prepared_content_identity": str(run["prepared_content_identity"]),
                    "summary": summary,
                }
            )
        if state == "blocked":
            response["reasons"] = findings
        if state == "cancelled":
            response["guaranteed_zero_media_effects"] = True
        return response

    def cancel_before_execution(self, run_ref: str) -> PreparedRun:
        """Idempotently cancel a Run whose ledger proves zero media effects."""

        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            run = connection.execute(
                "SELECT state FROM runs WHERE run_ref = ?", (run_ref,)
            ).fetchone()
            if run is None:
                raise KeyError(run_ref)
            state = str(run["state"])
            if state == "cancelled":
                connection.commit()
                return self.get_run(run_ref)
            if state not in {"preparing", "ready_for_authorization", "blocked"}:
                raise ApplyPreparationError(
                    "zero-effect cancellation is unavailable after execution"
                )
            attempted = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM run_items
                    WHERE run_ref = ? AND preparation_status NOT IN (
                        'pending', 'verified', 'blocked'
                    )
                    """,
                    (run_ref,),
                ).fetchone()[0]
            )
            if attempted:
                raise ApplyPreparationError(
                    "Run cannot prove zero effects for pre-execution cancellation"
                )
            connection.execute(
                "UPDATE runs SET state = 'cancelled' WHERE run_ref = ?", (run_ref,)
            )
            connection.commit()
        return self.get_run(run_ref)

    def iter_items(
        self,
        run_ref: str,
        *,
        after_ordinal: int = -1,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Traverse the persisted ledger without loading the full Run."""

        if limit < 1 or limit > 1_000:
            raise ValueError("limit must be between 1 and 1000")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT ordinal, source_item_ref, planned_outcome, source_path,
                       intended_target, verification_profile,
                       expected_verification, verification_observed_at,
                       verification_producer, verification_basis_json,
                       verification_limitations_json, observed_verification,
                       preparation_status, issue_code
                FROM run_items
                WHERE run_ref = ? AND ordinal > ?
                ORDER BY ordinal LIMIT ?
                """,
                (run_ref, after_ordinal, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def assert_authorization_binding(
        self,
        *,
        run_ref: str,
        prepared_revision: str,
        prepared_content_identity: str,
    ) -> None:
        """Reject stale or self-selected authorization coordinates.

        A future Tool host must additionally supply authenticated Human context.
        This method intentionally does not record authorization or start effects.
        """

        run = self.get_run(run_ref)
        if run.state != "ready_for_authorization":
            raise ApplyPreparationError("Run is not ready for authorization")
        if run.prepared_revision != prepared_revision:
            raise ApplyPreparationError("prepared revision mismatch")
        if run.prepared_content_identity != prepared_content_identity:
            raise ApplyPreparationError("prepared content identity mismatch")

    def _begin_run(
        self,
        *,
        request_id: str,
        request_identity: str,
        plan_ref: str,
        plan_identity: str,
        result_ref: str,
        logical_root: str,
        destination: Path,
        destination_identity: str,
        source_roots: Mapping[str, tuple[Path, str, int]],
    ) -> tuple[str, PreparedRun]:
        _nonempty_string(request_id, "request id")
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM runs WHERE request_id = ?", (request_id,)
            ).fetchone()
            if existing is not None:
                if existing["request_identity"] != request_identity:
                    raise IdempotencyConflict(
                        "prepare request_id was reused with different content"
                    )
                run = PreparedRun(
                    run_ref=str(existing["run_ref"]),
                    state=str(existing["state"]),
                    prepared_revision=existing["prepared_revision"],
                    prepared_content_identity=existing["prepared_content_identity"],
                )
                connection.commit()
                return run.run_ref, run
            run_ref = f"apply-run:{uuid4().hex}"
            connection.execute(
                """
                INSERT INTO runs (
                    run_ref, request_id, request_identity, state,
                    frozen_plan_ref, frozen_plan_content_identity, result_ref,
                    logical_root, destination_parent,
                    destination_observed_identity
                ) VALUES (?, ?, ?, 'preparing', ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_ref,
                    request_id,
                    request_identity,
                    plan_ref,
                    plan_identity,
                    result_ref,
                    logical_root,
                    str(destination),
                    destination_identity,
                ),
            )
            connection.executemany(
                """
                INSERT INTO source_roots (
                    run_ref, source_root_ref, current_root,
                    observed_identity, observed_device
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (run_ref, ref, str(path), identity, device)
                    for ref, (path, identity, device) in sorted(source_roots.items())
                ),
            )
            connection.commit()
        return run_ref, PreparedRun(run_ref, "preparing", None, None)

    def _reopen_blocked_preparation(self, run_ref: str) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM findings WHERE run_ref = ?", (run_ref,))
            connection.execute(
                """
                UPDATE run_items
                SET preparation_status = 'pending', issue_code = NULL
                WHERE run_ref = ? AND preparation_status = 'blocked'
                """,
                (run_ref,),
            )
            connection.execute(
                """
                UPDATE runs
                SET state = 'preparing', prepared_revision = NULL,
                    prepared_content_identity = NULL
                WHERE run_ref = ?
                """,
                (run_ref,),
            )
            connection.commit()

    def _stage_plan(
        self,
        *,
        run_ref: str,
        result_ref: str,
        content: Mapping[str, object],
        resolve_source_set: SourceSetResolver,
    ) -> None:
        with self._connect() as connection:
            staged = connection.execute(
                "SELECT plan_staged FROM runs WHERE run_ref = ?", (run_ref,)
            ).fetchone()
            if staged is None:
                raise KeyError(run_ref)
            if int(staged["plan_staged"]):
                return
            connection.execute("BEGIN IMMEDIATE")
            scope = _expand(resolve_source_set, result_ref, content.get("scope"))
            for ordinal, source_item_ref in enumerate(scope):
                try:
                    connection.execute(
                        """
                        INSERT INTO run_items (run_ref, ordinal, source_item_ref)
                        VALUES (?, ?, ?)
                        """,
                        (run_ref, ordinal, source_item_ref),
                    )
                except sqlite3.IntegrityError as error:
                    raise ApplyPreparationError(
                        f"Frozen Plan scope repeats {source_item_ref}"
                    ) from error

            groups = content.get("groups")
            if not isinstance(groups, list):
                raise ApplyPreparationError("Frozen Plan groups must be an array")
            for group in groups:
                group_map = _mapping(group, "logical group")
                relative_directory = _relative_directory(group_map.get("relative_path"))
                members = _expand(
                    resolve_source_set, result_ref, group_map.get("members")
                )
                for source_item_ref in members:
                    _assign_item(
                        connection,
                        run_ref,
                        source_item_ref,
                        "materialize",
                        relative_directory,
                    )
                naming = _mapping(group_map.get("source_naming"), "source naming")
                if naming.get("default") != "preserve_source_basename":
                    raise ApplyPreparationError("unsupported source naming policy")
                overrides = naming.get("overrides", [])
                if not isinstance(overrides, list):
                    raise ApplyPreparationError("name overrides must be an array")
                for override in overrides:
                    override_map = _mapping(override, "name override")
                    source_item_ref = _nonempty_string(
                        override_map.get("source_item_ref"), "override Source Item ref"
                    )
                    name = _safe_segment(override_map.get("name"), "override name")
                    changed = connection.execute(
                        """
                        UPDATE run_items SET override_name = ?
                        WHERE run_ref = ? AND source_item_ref = ?
                          AND planned_outcome = 'materialize'
                        """,
                        (name, run_ref, source_item_ref),
                    ).rowcount
                    if changed != 1:
                        raise ApplyPreparationError(
                            f"name override escapes its group: {source_item_ref}"
                        )

            other_outcomes = content.get("other_outcomes")
            if not isinstance(other_outcomes, list):
                raise ApplyPreparationError(
                    "Frozen Plan other_outcomes must be an array"
                )
            outcome_map = {
                "retain_current_organization": "retain",
                "exclude_from_logical_organization": "exclude",
            }
            for outcome in other_outcomes:
                outcome_value = _mapping(outcome, "other outcome")
                try:
                    planned_outcome = outcome_map[str(outcome_value.get("outcome"))]
                except KeyError as error:
                    raise ApplyPreparationError("unsupported other outcome") from error
                for source_item_ref in _expand(
                    resolve_source_set, result_ref, outcome_value.get("members")
                ):
                    _assign_item(
                        connection,
                        run_ref,
                        source_item_ref,
                        planned_outcome,
                        None,
                    )

            unassigned = connection.execute(
                """
                SELECT source_item_ref FROM run_items
                WHERE run_ref = ? AND planned_outcome IS NULL LIMIT 1
                """,
                (run_ref,),
            ).fetchone()
            if unassigned is not None:
                raise ApplyPreparationError(
                    f"Frozen Plan does not account for {unassigned['source_item_ref']}"
                )
            connection.execute(
                "UPDATE runs SET plan_staged = 1 WHERE run_ref = ?", (run_ref,)
            )
            connection.commit()

    def _prepare_item(
        self,
        *,
        run_ref: str,
        result_ref: str,
        item: SourceItemEvidence,
        source_roots: Mapping[str, tuple[Path, str, int]],
        destination: Path,
        logical_root: str,
    ) -> None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM run_items
                WHERE run_ref = ? AND source_item_ref = ?
                """,
                (run_ref, item.source_item_ref),
            ).fetchone()
            if row is None:
                self._add_finding(
                    run_ref,
                    "foreign_source_item",
                    f"{item.source_item_ref} is outside the Frozen Plan scope",
                    item.source_item_ref,
                )
                return
            if row["preparation_status"] == "verified":
                return
        if item.result_ref != result_ref:
            self._block_item(run_ref, item.source_item_ref, "foreign_result")
            return
        root_binding = source_roots.get(item.source_root_ref)
        if root_binding is None:
            self._block_item(run_ref, item.source_item_ref, "source_root_unbound")
            return
        root, _root_identity, _root_device = root_binding
        source_path = root.joinpath(*PurePath(item.relative_path).parts)
        try:
            observed = _verify_source(source_path, root, item.verification)
        except (OSError, ApplyPreparationError) as error:
            self._block_item(
                run_ref,
                item.source_item_ref,
                "source_unverifiable",
                str(error),
            )
            return

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT planned_outcome, relative_directory, override_name
                FROM run_items WHERE run_ref = ? AND source_item_ref = ?
                """,
                (run_ref, item.source_item_ref),
            ).fetchone()
            assert row is not None
            intended_target: str | None = None
            target_key: str | None = None
            if row["planned_outcome"] == "materialize":
                basename = row["override_name"] or source_path.name
                basename = _safe_segment(basename, "target basename")
                relative_directory = json.loads(row["relative_directory"])
                target = destination / logical_root
                for segment in relative_directory:
                    target /= segment
                target /= basename
                intended_target = str(target)
                target_key = _target_comparison_key(target)
                if _lexically_overlaps(root, destination / logical_root):
                    self._block_item(
                        run_ref,
                        item.source_item_ref,
                        "source_target_overlap",
                    )
                    return
                if target.exists() or target.is_symlink():
                    self._block_item(
                        run_ref,
                        item.source_item_ref,
                        "target_conflict",
                    )
                    return
            try:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    """
                    UPDATE run_items
                    SET source_root_ref = ?, relative_source_path = ?,
                        source_path = ?, intended_target = ?,
                        target_comparison_key = ?, verification_profile = ?,
                        expected_verification = ?, verification_observed_at = ?,
                        verification_producer = ?, verification_basis_json = ?,
                        verification_limitations_json = ?, observed_verification = ?,
                        observed_device = ?, observed_inode = ?, observed_size = ?,
                        observed_mtime_ns = ?, preparation_status = 'verified',
                        issue_code = NULL
                    WHERE run_ref = ? AND source_item_ref = ?
                    """,
                    (
                        item.source_root_ref,
                        item.relative_path,
                        str(source_path),
                        intended_target,
                        target_key,
                        item.verification.profile,
                        item.verification.value,
                        item.verification.observed_at,
                        item.verification.producer,
                        _canonical_json(item.verification.basis).decode("utf-8"),
                        _canonical_json(item.verification.limitations).decode("utf-8"),
                        observed["digest"],
                        observed["device"],
                        observed["inode"],
                        observed["size"],
                        observed["mtime_ns"],
                        run_ref,
                        item.source_item_ref,
                    ),
                )
                connection.commit()
            except sqlite3.IntegrityError:
                connection.rollback()
                self._block_item(
                    run_ref,
                    item.source_item_ref,
                    "target_conflict",
                    "planned targets collide under the active comparison profile",
                )

    def _block_item(
        self,
        run_ref: str,
        source_item_ref: str,
        code: str,
        detail: str | None = None,
    ) -> None:
        message = f"{source_item_ref}: {code}"
        if detail:
            message += f" ({detail})"
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE run_items SET preparation_status = 'blocked', issue_code = ?
                WHERE run_ref = ? AND source_item_ref = ?
                """,
                (code, run_ref, source_item_ref),
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO findings (
                    run_ref, code, source_item_ref, message
                ) VALUES (?, ?, ?, ?)
                """,
                (run_ref, code, source_item_ref, message),
            )

    def _add_finding(
        self,
        run_ref: str,
        code: str,
        message: str,
        source_item_ref: str = "",
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO findings (
                    run_ref, code, source_item_ref, message
                ) VALUES (?, ?, ?, ?)
                """,
                (run_ref, code, source_item_ref, message),
            )

    def _finalize_preparation(
        self,
        run_ref: str,
        source_roots: Mapping[str, tuple[Path, str, int]],
        destination_device: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            pending = connection.execute(
                """
                SELECT source_item_ref FROM run_items
                WHERE run_ref = ? AND planned_outcome = 'materialize'
                  AND preparation_status = 'pending'
                ORDER BY ordinal LIMIT 1
                """,
                (run_ref,),
            ).fetchone()
            if pending is not None:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO findings (
                        run_ref, code, source_item_ref, message
                    ) VALUES (?, 'source_evidence_missing', ?, ?)
                    """,
                    (
                        run_ref,
                        str(pending["source_item_ref"]),
                        f"missing evidence for {pending['source_item_ref']}",
                    ),
                )
            aliases = connection.execute(
                """
                SELECT observed_device, observed_inode, COUNT(*) AS item_count
                FROM run_items
                WHERE run_ref = ? AND planned_outcome = 'materialize'
                  AND preparation_status = 'verified'
                GROUP BY observed_device, observed_inode HAVING COUNT(*) > 1
                LIMIT 1
                """,
                (run_ref,),
            ).fetchone()
            if aliases is not None:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO findings (
                        run_ref, code, source_item_ref, message
                    ) VALUES (?, 'source_alias_conflict', '', ?)
                    """,
                    (
                        run_ref,
                        "multiple Source Items resolve to one filesystem object",
                    ),
                )
            root_alias = connection.execute(
                """
                SELECT observed_identity FROM source_roots
                WHERE run_ref = ?
                GROUP BY observed_identity HAVING COUNT(*) > 1
                LIMIT 1
                """,
                (run_ref,),
            ).fetchone()
            if root_alias is not None:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO findings (
                        run_ref, code, source_item_ref, message
                    ) VALUES (?, 'source_root_alias_conflict', '', ?)
                    """,
                    (
                        run_ref,
                        "multiple source_root_ref values resolve to one current root",
                    ),
                )
            used_roots = {
                str(row["source_root_ref"])
                for row in connection.execute(
                    """
                    SELECT DISTINCT source_root_ref FROM run_items
                    WHERE run_ref = ? AND planned_outcome = 'materialize'
                      AND source_root_ref IS NOT NULL
                    """,
                    (run_ref,),
                )
            }
            extra_roots = sorted(set(source_roots) - used_roots)
            if extra_roots:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO findings (
                        run_ref, code, source_item_ref, message
                    ) VALUES (?, 'extraneous_source_root_binding', '', ?)
                    """,
                    (
                        run_ref,
                        "unreferenced source root bindings: " + ", ".join(extra_roots),
                    ),
                )
            route = (
                "same_filesystem_atomic_move"
                if all(source_roots[ref][2] == destination_device for ref in used_roots)
                else "verified_cross_filesystem_transfer"
            )
            if route == "verified_cross_filesystem_transfer":
                connection.execute(
                    """
                    INSERT OR IGNORE INTO findings (
                        run_ref, code, source_item_ref, message
                    ) VALUES (?, 'cross_filesystem_effect_not_activated', '', ?)
                    """,
                    (
                        run_ref,
                        "cross-filesystem effects remain disabled until Human activation",
                    ),
                )
            self._record_concurrency_conflict(connection, run_ref)
            identity = _prepared_identity(connection, run_ref, route)
            revision = f"prepared-revision:{identity.removeprefix('sha256:')[:24]}"
            blocker_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM findings WHERE run_ref = ?", (run_ref,)
                ).fetchone()[0]
            )
            state = "blocked" if blocker_count else "ready_for_authorization"
            connection.execute(
                """
                UPDATE runs
                SET state = ?, execution_route = ?, prepared_revision = ?,
                    prepared_content_identity = ?
                WHERE run_ref = ?
                """,
                (state, route, revision, identity, run_ref),
            )
            connection.commit()

    def _record_concurrency_conflict(
        self, connection: sqlite3.Connection, run_ref: str
    ) -> None:
        conflict = connection.execute(
            """
            SELECT current.source_item_ref
            FROM run_items AS current
            JOIN run_items AS other
              ON other.run_ref <> current.run_ref
             AND (
                 (current.observed_device = other.observed_device
                  AND current.observed_inode = other.observed_inode)
                 OR (current.target_comparison_key IS NOT NULL
                     AND current.target_comparison_key = other.target_comparison_key)
             )
            JOIN runs AS other_run ON other_run.run_ref = other.run_ref
            WHERE current.run_ref = ?
              AND other_run.state IN ('preparing', 'ready_for_authorization')
            LIMIT 1
            """,
            (run_ref,),
        ).fetchone()
        if conflict is not None:
            connection.execute(
                """
                INSERT OR IGNORE INTO findings (
                    run_ref, code, source_item_ref, message
                ) VALUES (?, 'concurrency_conflict', ?, ?)
                """,
                (
                    run_ref,
                    str(conflict["source_item_ref"]),
                    "another active Run overlaps a source object or final target",
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def _verify_schema(self) -> None:
        with self._connect() as connection:
            try:
                row = connection.execute(
                    "SELECT version FROM internal_schema WHERE singleton = 1"
                ).fetchone()
            except sqlite3.OperationalError as error:
                raise RuntimeError("initialize the Apply Run store first") from error
        if row is None or int(row["version"]) != _SCHEMA_VERSION:
            raise RuntimeError("unsupported Apply Run store schema")


def _read_source_item(
    *,
    precheck_read: PrecheckReadBoundary,
    result_ref: str,
    source_item_ref: str,
) -> SourceItemEvidence:
    request = {
        "result_ref": result_ref,
        "action": "inspect",
        "target": {"kind": "source_item", "ref": source_item_ref},
    }
    try:
        response = precheck_read.read(request)
    except (OSError, ValueError) as error:
        raise SourceEvidenceError(
            "precheck_read_failed",
            f"PreCheck read failed for {source_item_ref}: {error}",
        ) from error
    if not isinstance(response, Mapping):
        raise SourceEvidenceError(
            "precheck_read_failed",
            f"PreCheck read returned no structured result for {source_item_ref}",
        )
    if response.get("outcome") == "error":
        error = response.get("error")
        error_code = (
            str(error.get("code"))
            if isinstance(error, Mapping) and error.get("code")
            else "unknown"
        )
        raise SourceEvidenceError(
            "precheck_read_failed",
            f"PreCheck read refused {source_item_ref}: {error_code}",
        )
    if (
        response.get("outcome") != "ok"
        or response.get("action") != "inspect"
        or response.get("result_ref") != result_ref
    ):
        raise SourceEvidenceError(
            "precheck_read_mismatch",
            f"PreCheck read response is not bound to {result_ref}",
        )
    target = response.get("target")
    if not isinstance(target, Mapping) or target.get("ref") != source_item_ref:
        raise SourceEvidenceError(
            "precheck_read_mismatch",
            f"PreCheck read returned the wrong Source Item for {source_item_ref}",
        )
    try:
        return SourceItemEvidence.from_precheck_view(
            result_ref=result_ref,
            view=target,
        )
    except SourceEvidenceError:
        raise
    except ApplyPreparationError as error:
        raise SourceEvidenceError("source_verification_invalid", str(error)) from error


def _validated_plan(plan: Mapping[str, object]) -> Mapping[str, object]:
    content = _mapping(plan.get("sealed_content"), "sealed content")
    seal = _mapping(plan.get("seal"), "seal")
    if content.get("contract") != "mediasense.frozen-plan":
        raise ApplyPreparationError("unsupported Frozen Plan contract")
    expected = _nonempty_string(seal.get("content_identity"), "content identity")
    if expected != _content_identity(content):
        raise ApplyPreparationError("Frozen Plan content identity mismatch")
    confirmation = _mapping(seal.get("final_confirmation"), "final confirmation")
    if confirmation.get("confirmed_content_identity") != expected:
        raise ApplyPreparationError(
            "Frozen Plan is not confirmed at its exact identity"
        )
    _nonempty_string(confirmation.get("confirmed_by"), "confirming authority")
    _nonempty_string(confirmation.get("confirmed_at"), "confirmation time")
    return plan


def _observe_source_roots(
    source_roots: Mapping[str, Path],
) -> dict[str, tuple[Path, str, int]]:
    if not source_roots:
        raise ApplyPreparationError("at least one source root binding is required")
    observed: dict[str, tuple[Path, str, int]] = {}
    for ref, raw_path in source_roots.items():
        if not ref.startswith("source-root:"):
            raise ApplyPreparationError(f"invalid source root ref: {ref}")
        path = _strict_directory(raw_path, f"source root {ref}")
        info = path.stat()
        observed[ref] = (path, _filesystem_identity(path, info), int(info.st_dev))
    return observed


def _verify_source(
    source_path: Path,
    root: Path,
    basis: VerificationBasis,
) -> dict[str, int | str]:
    _require_exact_path_spelling(root, source_path)
    _reject_symlink_components(root, source_path)
    resolved = source_path.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ApplyPreparationError(
            "source locator escapes its root binding"
        ) from error
    before = source_path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise ApplyPreparationError("source is not a regular file")
    digest = hashlib.sha256()
    with source_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    after = source_path.stat(follow_symlinks=False)
    stable = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    observed = "sha256:" + digest.hexdigest()
    if not stable:
        raise ApplyPreparationError("source changed while it was verified")
    if before.st_size != basis.size_bytes or observed != basis.value:
        raise ApplyPreparationError("source does not match immutable PreCheck evidence")
    return {
        "digest": observed,
        "device": int(before.st_dev),
        "inode": int(before.st_ino),
        "size": int(before.st_size),
        "mtime_ns": int(before.st_mtime_ns),
    }


def _require_exact_path_spelling(root: Path, source_path: Path) -> None:
    current = root
    for part in source_path.relative_to(root).parts:
        try:
            names = {entry.name for entry in os.scandir(current)}
        except OSError as error:
            raise ApplyPreparationError(
                f"source path component cannot be inspected: {current}"
            ) from error
        if part not in names:
            raise ApplyPreparationError(
                "source locator is ambiguous under actual filesystem semantics"
            )
        current /= part


def _reject_symlink_components(root: Path, source_path: Path) -> None:
    root_info = root.lstat()
    if stat.S_ISLNK(root_info.st_mode):
        raise ApplyPreparationError("source root cannot be a symlink")
    relative = source_path.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        if stat.S_ISLNK(current.lstat().st_mode):
            raise ApplyPreparationError("source locator traverses a symlink")


def _assign_item(
    connection: sqlite3.Connection,
    run_ref: str,
    source_item_ref: str,
    outcome: str,
    relative_directory: str | None,
) -> None:
    row = connection.execute(
        """
        SELECT planned_outcome FROM run_items
        WHERE run_ref = ? AND source_item_ref = ?
        """,
        (run_ref, source_item_ref),
    ).fetchone()
    if row is None:
        raise ApplyPreparationError(
            f"decision escapes Frozen Plan scope: {source_item_ref}"
        )
    if row["planned_outcome"] is not None:
        raise ApplyPreparationError(f"repeated outcome for {source_item_ref}")
    connection.execute(
        """
        UPDATE run_items SET planned_outcome = ?, relative_directory = ?
        WHERE run_ref = ? AND source_item_ref = ?
        """,
        (outcome, relative_directory, run_ref, source_item_ref),
    )


def _expand(
    resolver: SourceSetResolver,
    result_ref: str,
    expression: object,
) -> Iterable[str]:
    expression_map = _mapping(expression, "source set")
    expansion = resolver(result_ref, expression_map)
    if not expansion.complete:
        raise ApplyPreparationError("source set is not fully expandable")
    for value in expansion.source_item_refs:
        source_item_ref = _nonempty_string(value, "Source Item ref")
        yield source_item_ref


def _prepared_identity(connection: sqlite3.Connection, run_ref: str, route: str) -> str:
    run = connection.execute(
        """
        SELECT frozen_plan_ref, frozen_plan_content_identity, result_ref,
               logical_root, destination_parent, destination_observed_identity
        FROM runs WHERE run_ref = ?
        """,
        (run_ref,),
    ).fetchone()
    assert run is not None
    digest = hashlib.sha256()
    header = dict(run)
    header["execution_route"] = route
    digest.update(_canonical_json(header))
    for root in connection.execute(
        """
        SELECT source_root_ref, current_root, observed_identity
        FROM source_roots WHERE run_ref = ? ORDER BY source_root_ref
        """,
        (run_ref,),
    ):
        digest.update(b"\n")
        digest.update(_canonical_json(dict(root)))
    for item in connection.execute(
        """
        SELECT ordinal, source_item_ref, planned_outcome, relative_directory,
               override_name, source_root_ref, relative_source_path,
               source_path, intended_target, verification_profile,
               expected_verification, verification_observed_at,
               verification_producer, verification_basis_json,
               verification_limitations_json, observed_verification,
               observed_device, observed_inode, observed_size,
               observed_mtime_ns, preparation_status, issue_code
        FROM run_items WHERE run_ref = ? ORDER BY ordinal
        """,
        (run_ref,),
    ):
        digest.update(b"\n")
        digest.update(_canonical_json(dict(item)))
    for finding in connection.execute(
        """
        SELECT code, source_item_ref, message FROM findings
        WHERE run_ref = ? ORDER BY code, source_item_ref, message
        """,
        (run_ref,),
    ):
        digest.update(b"\n")
        digest.update(_canonical_json(dict(finding)))
    return "sha256:" + digest.hexdigest()


def _content_identity(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _filesystem_identity(path: Path, info: os.stat_result) -> str:
    return f"filesystem-object-v1:dev={info.st_dev}:ino={info.st_ino}:path={path}"


def _strict_directory(value: Path, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise ApplyPreparationError(f"{label} must be absolute")
    try:
        if stat.S_ISLNK(path.lstat().st_mode):
            raise ApplyPreparationError(f"{label} cannot be a symlink")
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ApplyPreparationError(f"{label} is unavailable") from error
    if not resolved.is_dir():
        raise ApplyPreparationError(f"{label} must be an existing directory")
    return resolved


def _safe_relative_path(value: object) -> str:
    text = _nonempty_string(value, "relative path")
    path = PurePath(text)
    if path.is_absolute() or path == PurePath(".") or ".." in path.parts:
        raise ApplyPreparationError("source path must remain relative to its root")
    if any("\x00" in part for part in path.parts):
        raise ApplyPreparationError("source path contains a NUL")
    return path.as_posix()


def _relative_directory(value: object) -> str:
    if not isinstance(value, list):
        raise ApplyPreparationError("logical relative path must be an array")
    return json.dumps(
        [_safe_segment(part, "logical path segment") for part in value],
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _safe_segment(value: object, label: str) -> str:
    text = _nonempty_string(value, label)
    if text in {".", ".."} or "/" in text or "\x00" in text:
        raise ApplyPreparationError(f"invalid {label}")
    return text


def _target_comparison_key(path: Path) -> str:
    normalized = unicodedata.normalize("NFD", str(path))
    return normalized.casefold()


def _lexically_overlaps(first: Path, second: Path) -> bool:
    try:
        first.relative_to(second)
        return True
    except ValueError:
        pass
    try:
        second.relative_to(first)
        return True
    except ValueError:
        return False


def _parse_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SourceEvidenceError(
            "source_verification_invalid",
            "verification observed_at must be an ISO 8601 timestamp",
        ) from error
    if parsed.tzinfo is None:
        raise SourceEvidenceError(
            "source_verification_invalid",
            "verification observed_at must include a timezone",
        )


def _validate_basis(value: object) -> None:
    if isinstance(value, str):
        if value.strip():
            return
    elif isinstance(value, Mapping):
        if value:
            _canonical_json(value)
            return
    raise SourceEvidenceError(
        "source_verification_invalid",
        "verification basis must be a non-empty observation-level value",
    )


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ApplyPreparationError(f"{label} must be an object")
    return value


def _nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ApplyPreparationError(f"{label} must be a non-empty string")
    return value


def _nonnegative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ApplyPreparationError(f"{label} must be a non-negative integer")
    return value
