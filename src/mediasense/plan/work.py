"""Public handler for the four-action ``mediasense.plan.work`` contract."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import binascii
import hashlib
import hmac
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from mediasense.frozen_plan import (
    load_frozen_content_validator,
    load_frozen_plan_validator,
)
from mediasense.precheck.read import (
    PrecheckReadBoundary,
    require_precheck_read_boundary,
)

from ._candidate import (
    CandidateAnalysis,
    analyze_candidate,
    materialize_candidate,
)
from ._publication import FrozenPlanPublisher, PublicationConflict
from ._update_execution import (
    UpdateCancelled,
    UpdateExecution,
    UpdateOwnershipError,
    update_ownership,
)
from ._sqlite import (
    IdempotencyConflict,
    RevisionConflict,
    SealConflict,
    SQLitePlanStore,
    WorkClosed,
    WorkNotFound,
    WorkSnapshot,
)


_WORK_REF = re.compile(r"^plan-work:[^\s]+$")
_RESULT_REF = re.compile(r"^precheck-result:[^\s]+$")
_REVISION = re.compile(r"^work-revision:[^\s]+$")
_REQUEST_ID = re.compile(r"^request:[^\s]+$")
_CONTENT_IDENTITY = re.compile(r"^sha256:[0-9a-f]{64}$")
_DEFAULT_SECTIONS = (
    "overview",
    "preferences",
    "working_notes",
    "content",
    "validation",
)
_SECTIONS = _DEFAULT_SECTIONS
_COLLECTIONS = ("groups", "other_outcomes", "decision_notes")


@dataclass(frozen=True, slots=True)
class ConfirmationContext:
    principal_ref: str
    confirmed_content_identity: str
    confirmed_at: datetime


class PlanFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        work_ref: str | None = None,
        revision: str | None = None,
        current_revision: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.work_ref = work_ref
        self.revision = revision
        self.current_revision = current_revision


class PlanWorkTool:
    """Coordinate Plan state without owning semantic planning decisions."""

    def __init__(
        self,
        plan_store: Path,
        precheck_read: PrecheckReadBoundary,
        *,
        id_factory: Callable[[str], str] | None = None,
        frozen_plan_schema: Path | None = None,
    ) -> None:
        precheck_boundary = require_precheck_read_boundary(precheck_read)
        self.plan_store = Path(plan_store)
        self.store = SQLitePlanStore(self.plan_store / "work-v3.sqlite3")
        self.frozen_dir = self.plan_store / "frozen"
        self.precheck_read = precheck_boundary
        self._id_factory = id_factory or (lambda prefix: f"{prefix}:{uuid4()}")
        self._frozen_content_validator = load_frozen_content_validator(
            frozen_plan_schema
        )
        self._frozen_plan_validator = load_frozen_plan_validator(frozen_plan_schema)
        self._publisher = FrozenPlanPublisher(
            self.frozen_dir, self._frozen_plan_validator
        )
        self._cursor_signing_key = self.store.cursor_signing_key()

    def handle(
        self,
        request: Mapping[str, Any],
        *,
        confirmation: ConfirmationContext | None = None,
        execution: UpdateExecution | None = None,
    ) -> dict[str, Any]:
        action = request.get("action") if isinstance(request, Mapping) else None
        if action not in {"create", "update", "inspect", "seal"}:
            raise ValueError("request action must be create, update, inspect, or seal")
        try:
            if action == "create":
                return self._create(dict(request))
            if action == "update":
                # Freeze the payload before it may wait for another invocation.
                return self._update(deepcopy(dict(request)), execution=execution)
            if action == "inspect":
                return self._inspect(dict(request))
            return self._seal(dict(request), confirmation)
        except UpdateCancelled:
            return _error_response(
                action,
                PlanFailure(
                    "operation_failed",
                    "This update invocation was cancelled before commit; it changed no candidate or revision.",
                    work_ref=_maybe_work_ref(request),
                ),
            )
        except UpdateOwnershipError as exc:
            return _error_response(
                action,
                PlanFailure(
                    "operation_failed", str(exc), work_ref=_maybe_work_ref(request)
                ),
            )
        except PlanFailure as exc:
            return _error_response(action, exc)
        except WorkNotFound:
            return _error_response(
                action,
                PlanFailure(
                    "work_not_found",
                    "The Working State does not exist.",
                    work_ref=_maybe_work_ref(request),
                ),
            )
        except WorkClosed:
            snapshot = self._optional_snapshot(_maybe_work_ref(request))
            return _error_response(
                action,
                PlanFailure(
                    "work_closed",
                    "The Working State was closed by a successful seal.",
                    work_ref=_maybe_work_ref(request),
                    revision=None if snapshot is None else snapshot.revision,
                    current_revision=None if snapshot is None else snapshot.revision,
                ),
            )
        except RevisionConflict as exc:
            return _error_response(
                action,
                PlanFailure(
                    "revision_conflict",
                    "The requested revision is not current.",
                    work_ref=_maybe_work_ref(request),
                    revision=exc.current_revision,
                    current_revision=exc.current_revision,
                ),
            )
        except IdempotencyConflict:
            return _error_response(
                action,
                PlanFailure(
                    "idempotency_conflict",
                    "The request_id was already used with different input.",
                    work_ref=_maybe_work_ref(request),
                ),
            )
        except (SealConflict, PublicationConflict) as exc:
            return _error_response(
                action,
                PlanFailure(
                    "operation_failed",
                    str(exc),
                    work_ref=_maybe_work_ref(request),
                ),
            )

    def snapshot_for_preview(
        self, work_ref: str, revision: str
    ) -> tuple[WorkSnapshot, CandidateAnalysis]:
        _require_ref(work_ref, _WORK_REF, "work_ref")
        _require_ref(revision, _REVISION, "revision")
        snapshot = self.store.snapshot(work_ref)
        if snapshot.revision != revision:
            raise RevisionConflict(snapshot.revision)
        if snapshot.candidate is None:
            raise PlanFailure(
                "candidate_invalid",
                "The Working State has no candidate content.",
                work_ref=work_ref,
                revision=revision,
            )
        analysis = analyze_candidate(
            snapshot.candidate,
            result_ref=snapshot.result_ref,
            plan_ref=snapshot.plan_ref,
            reader=self.precheck_read,
            schema_validator=self._frozen_content_validator,
        )
        if not analysis.seal_ready:
            raise PlanFailure(
                "candidate_invalid",
                analysis.issues[0].message,
                work_ref=work_ref,
                revision=revision,
            )
        return snapshot, analysis

    def _create(self, request: dict[str, Any]) -> dict[str, Any]:
        _require_keys(
            request,
            required={"action", "result_ref", "request_id"},
            allowed={"action", "result_ref", "request_id", "organization_preferences"},
        )
        result_ref = _require_ref(request["result_ref"], _RESULT_REF, "result_ref")
        request_id = _require_ref(request["request_id"], _REQUEST_ID, "request_id")
        preferences = request.get("organization_preferences", {})
        if not isinstance(preferences, dict):
            raise PlanFailure(
                "invalid_request", "organization_preferences must be an object."
            )
        digest = _request_digest(request)
        try:
            replay = self.store.replay(request_id, digest)
        except IdempotencyConflict:
            raise
        if replay is not None:
            return replay

        response = self.precheck_read.read(
            {
                "result_ref": result_ref,
                "action": "review",
                "page": {"limit": 1},
            }
        )
        if not isinstance(response, Mapping) or "error" in response:
            error = response.get("error", {}) if isinstance(response, Mapping) else {}
            code = error.get("code", "result_not_found")
            if code not in {
                "result_not_found",
                "result_unavailable",
                "result_untrusted",
                "result_inconsistent",
            }:
                code = "operation_failed"
            raise PlanFailure(
                code, "The exact PreCheck Result could not be trusted or read."
            )
        from mediasense.runtime.resources import contract_validator

        if not contract_validator("mediasense.precheck.read", "review").is_valid(
            response
        ):
            raise PlanFailure(
                "result_untrusted", "PreCheck returned an invalid Result response."
            )
        target = response.get("result")
        if not isinstance(target, Mapping) or target.get("ref") != result_ref:
            raise PlanFailure(
                "operation_failed", "PreCheck returned an invalid Result view."
            )
        if target.get("readiness") != "plan_ready":
            raise PlanFailure(
                "result_not_ready", "The PreCheck Result is not plan-ready."
            )
        if target.get("coverage") not in {"complete", "partial"}:
            raise PlanFailure(
                "result_not_ready", "The PreCheck Result has unsupported coverage."
            )
        work_ref = self._id_factory("plan-work")
        revision = self._id_factory("work-revision")
        plan_ref = self._id_factory("frozen-plan")
        result = {
            "outcome": "ok",
            "action": "create",
            "work_ref": work_ref,
            "result_ref": result_ref,
            "revision": revision,
            "state": "open",
            "organization_preferences": preferences,
        }
        return self.store.create(
            request_id=request_id,
            request_digest=digest,
            work_ref=work_ref,
            result_ref=result_ref,
            revision=revision,
            plan_ref=plan_ref,
            organization_preferences=preferences,
            response=result,
        )

    def _update(
        self, request: dict[str, Any], *, execution: UpdateExecution | None = None
    ) -> dict[str, Any]:
        _require_keys(
            request,
            required={
                "action",
                "work_ref",
                "base_revision",
                "request_id",
            },
            allowed={
                "action",
                "work_ref",
                "base_revision",
                "candidate_content",
                "request_id",
                "organization_preferences",
                "working_notes",
            },
        )
        if (
            not {"candidate_content", "organization_preferences", "working_notes"}
            & request.keys()
        ):
            raise PlanFailure(
                "invalid_request", "update requires at least one modifiable field."
            )
        if "working_notes" in request and not isinstance(request["working_notes"], str):
            raise PlanFailure("invalid_request", "working_notes must be a string.")
        work_ref = _require_ref(request["work_ref"], _WORK_REF, "work_ref")
        base_revision = _require_ref(
            request["base_revision"], _REVISION, "base_revision"
        )
        request_id = _require_ref(request["request_id"], _REQUEST_ID, "request_id")
        preferences = request.get("organization_preferences")
        if "organization_preferences" in request and not isinstance(preferences, dict):
            raise PlanFailure(
                "invalid_request",
                "organization_preferences must be an object.",
                work_ref=work_ref,
            )
        digest = _request_digest(request)
        execution = execution or UpdateExecution()
        with execution.operation(work_ref, request_id):
            replay, _ = self._update_preflight(
                work_ref, base_revision, request_id, digest
            )
            if replay is not None:
                execution.report("replayed")
                return replay
            candidate = request.get("candidate_content")
            if candidate is not None and not isinstance(candidate, Mapping):
                raise PlanFailure(
                    "invalid_request",
                    "candidate_content must be an object or null.",
                    work_ref=work_ref,
                )
            with update_ownership(self.store.database_path, work_ref, execution):
                # The owner ahead of us may have committed, failed or cancelled.
                # Re-read facts after admission; a lock is never a success receipt.
                replay, snapshot = self._update_preflight(
                    work_ref, base_revision, request_id, digest
                )
                if replay is not None:
                    execution.report("replayed")
                    return replay
                assert snapshot is not None
                candidate_identity = None
                if candidate is not None:
                    analysis = analyze_candidate(
                        candidate,
                        result_ref=snapshot.result_ref,
                        plan_ref=snapshot.plan_ref,
                        reader=execution.reader(self.precheck_read),
                        schema_validator=self._frozen_content_validator,
                        checkpoint=execution.checkpoint,
                        progress=execution.report,
                    )
                    execution.checkpoint()
                    if not analysis.seal_ready or analysis.content_identity is None:
                        message = "; ".join(
                            issue.message for issue in analysis.issues[:3]
                        )
                        raise PlanFailure(
                            "candidate_invalid",
                            message or "Candidate is invalid.",
                            work_ref=work_ref,
                            revision=snapshot.revision,
                        )
                    candidate_identity = analysis.content_identity
                execution.checkpoint()
                revision = self._id_factory("work-revision")
                result = {
                    "outcome": "ok",
                    "action": "update",
                    "work_ref": work_ref,
                    "result_ref": snapshot.result_ref,
                    "revision": revision,
                    "state": "open",
                }
                result = self.store.update(
                    request_id=request_id,
                    request_digest=digest,
                    work_ref=work_ref,
                    base_revision=base_revision,
                    revision=revision,
                    candidate=None if candidate is None else dict(candidate),
                    candidate_identity=candidate_identity,
                    replace_candidate="candidate_content" in request,
                    working_notes=request.get("working_notes"),
                    organization_preferences=preferences,
                    response=result,
                    before_write=execution.begin_commit,
                )
                execution.report(
                    "committed" if execution.commit_started else "replayed"
                )
                return result

    def _update_preflight(
        self, work_ref: str, base_revision: str, request_id: str, digest: str
    ) -> tuple[dict[str, Any] | None, WorkSnapshot | None]:
        replay = self.store.replay(request_id, digest)
        if replay is not None:
            return replay, None
        try:
            snapshot = self.store.snapshot(work_ref, include_candidate=False)
            if snapshot.state != "open":
                raise WorkClosed(work_ref)
            if snapshot.revision != base_revision:
                raise RevisionConflict(snapshot.revision)
        except (WorkClosed, RevisionConflict):
            # A commit may land after the receipt lookup but before the snapshot.
            # Receipts are durable and atomic with state/revision changes, so
            # recheck before rejecting. Never repeat candidate validation here.
            replay = self.store.replay(request_id, digest)
            if replay is None:
                raise
            return replay, None
        return None, snapshot

    def _inspect(self, request: dict[str, Any]) -> dict[str, Any]:
        _require_keys(
            request,
            required={"action", "work_ref"},
            allowed={"action", "work_ref", "revision", "sections", "page"},
        )
        work_ref = _require_ref(request["work_ref"], _WORK_REF, "work_ref")
        snapshot = self.store.snapshot(work_ref)
        requested_revision = request.get("revision")
        if "revision" in request:
            _require_ref(requested_revision, _REVISION, "revision")
            if requested_revision != snapshot.revision:
                raise RevisionConflict(snapshot.revision)
        sections = request.get("sections", list(_DEFAULT_SECTIONS))
        if (
            not isinstance(sections, list)
            or not sections
            or any(not isinstance(section, str) for section in sections)
            or len(sections) != len(set(sections))
            or any(section not in _SECTIONS for section in sections)
        ):
            raise PlanFailure(
                "invalid_request",
                "sections must be a nonempty unique list of supported names.",
                work_ref=work_ref,
            )
        page_request = request.get("page")
        if "page" in request and (
            sections != ["content"] or not isinstance(page_request, Mapping)
        ):
            raise PlanFailure(
                "invalid_request",
                "page requires content as the only requested section.",
                work_ref=work_ref,
            )
        returned: list[str] = []
        values: dict[str, Any] = {}
        if "overview" in sections:
            returned.append("overview")
            values["overview"] = {"state": snapshot.state}
        if "preferences" in sections:
            returned.append("preferences")
            values["preferences"] = snapshot.organization_preferences
        if "working_notes" in sections:
            returned.append("working_notes")
            values["working_notes"] = snapshot.working_notes
        if "content" in sections:
            returned.append("content")
            values["content"] = self._content_section(snapshot, page_request)
        if "validation" in sections:
            returned.append("validation")
            if snapshot.candidate_identity is None:
                values["validation"] = {
                    "seal_ready": False,
                    "issues": [
                        {
                            "code": "candidate_missing",
                            "severity": "error",
                            "message": "The Working State has no candidate content.",
                        }
                    ],
                }
            else:
                values["validation"] = {"seal_ready": True, "issues": []}
        result: dict[str, Any] = {
            "outcome": "ok",
            "action": "inspect",
            "work_ref": work_ref,
            "result_ref": snapshot.result_ref,
            "revision": snapshot.revision,
            "state": snapshot.state,
            "returned_sections": returned,
            "sections": values,
        }
        if snapshot.candidate_identity is not None:
            result["candidate_content_identity"] = snapshot.candidate_identity
        return result

    def _content_section(
        self,
        snapshot: WorkSnapshot,
        page_request: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        if page_request is None:
            return (
                None
                if snapshot.candidate is None
                else {
                    "mode": "complete",
                    "value": materialize_candidate(
                        snapshot.candidate, plan_ref=snapshot.plan_ref
                    ),
                }
            )
        allowed = {"collection", "limit", "cursor"}
        _require_keys(page_request, required={"collection"}, allowed=allowed)
        collection = page_request["collection"]
        if collection not in _COLLECTIONS:
            raise PlanFailure(
                "invalid_request",
                "Unsupported paged collection.",
                work_ref=snapshot.work_ref,
            )
        requested_limit = page_request.get("limit")
        limit = 100 if requested_limit is None else requested_limit
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 500
        ):
            raise PlanFailure(
                "invalid_request",
                "Page limit must be between 1 and 500.",
                work_ref=snapshot.work_ref,
            )
        offset = 0
        if "cursor" in page_request:
            offset, limit = _decode_cursor(
                page_request["cursor"],
                work_ref=snapshot.work_ref,
                revision=snapshot.revision,
                collection=collection,
                requested_limit=requested_limit,
                signing_key=self._cursor_signing_key,
            )
        if snapshot.candidate is None:
            return None
        sealed_content = materialize_candidate(
            snapshot.candidate, plan_ref=snapshot.plan_ref
        )
        items = sealed_content.get(collection, [])
        page_items = items[offset : offset + limit]
        complete = offset + len(page_items) >= len(items)
        page: dict[str, Any] = {
            "collection": collection,
            "returned": len(page_items),
            "complete": complete,
        }
        if not complete:
            page["next_cursor"] = _encode_cursor(
                snapshot.work_ref,
                snapshot.revision,
                collection,
                offset + len(page_items),
                limit,
                self._cursor_signing_key,
            )
        header = {
            key: sealed_content[key]
            for key in ("contract", "plan_ref", "result_ref", "scope", "logical_root")
        }
        return {
            "mode": "page",
            "header": header,
            "collection": collection,
            "items": page_items,
            "page": page,
        }

    def _seal(
        self,
        request: dict[str, Any],
        confirmation: ConfirmationContext | None,
    ) -> dict[str, Any]:
        _require_keys(
            request,
            required={
                "action",
                "work_ref",
                "revision",
                "candidate_content_identity",
                "request_id",
            },
            allowed={
                "action",
                "work_ref",
                "revision",
                "candidate_content_identity",
                "request_id",
            },
        )
        work_ref = _require_ref(request["work_ref"], _WORK_REF, "work_ref")
        _require_ref(request["revision"], _REVISION, "revision")
        _require_ref(
            request["candidate_content_identity"],
            _CONTENT_IDENTITY,
            "candidate_content_identity",
        )
        request_id = _require_ref(request["request_id"], _REQUEST_ID, "request_id")
        revision = request["revision"]
        requested_identity = request["candidate_content_identity"]
        if confirmation is None:
            raise PlanFailure(
                "confirmation_required",
                "Trusted Human confirmation is required.",
                work_ref=work_ref,
                revision=revision,
            )
        principal_ref = _require_trusted_principal(confirmation.principal_ref)
        if confirmation.confirmed_at.tzinfo is None:
            raise PlanFailure(
                "access_denied",
                "Trusted confirmation time must include a timezone.",
                work_ref=work_ref,
                revision=revision,
            )
        if confirmation.confirmed_content_identity != requested_identity:
            raise PlanFailure(
                "content_identity_mismatch",
                "Human confirmation is bound to different content.",
                work_ref=work_ref,
                revision=revision,
            )
        confirmation_digest = _confirmation_digest(confirmation)
        digest = _seal_request_digest(request, confirmation)

        replay = self.store.replay(request_id, digest)
        if replay is not None:
            frozen_plan = replay.get("frozen_plan")
            if not isinstance(frozen_plan, dict):
                raise PublicationConflict("stored seal response is invalid")
            snapshot = self.store.snapshot(work_ref)
            if snapshot.published_path is None:
                raise PublicationConflict("closed Work has no published artifact")
            observed = self._publisher.read_verified(Path(snapshot.published_path))
            if observed != frozen_plan:
                raise PublicationConflict(
                    "published artifact differs from seal response"
                )
            return replay

        snapshot = self.store.snapshot(work_ref)
        if snapshot.state != "open":
            raise WorkClosed(work_ref)
        if snapshot.revision != revision:
            raise RevisionConflict(snapshot.revision)
        if snapshot.candidate is None or snapshot.candidate_identity is None:
            raise PlanFailure(
                "candidate_invalid",
                "The Working State has no sealable candidate.",
                work_ref=work_ref,
                revision=revision,
            )
        if snapshot.candidate_identity != requested_identity:
            raise PlanFailure(
                "content_identity_mismatch",
                "Requested content identity is not the current candidate.",
                work_ref=work_ref,
                revision=revision,
            )

        analysis = analyze_candidate(
            snapshot.candidate,
            result_ref=snapshot.result_ref,
            plan_ref=snapshot.plan_ref,
            reader=self.precheck_read,
            schema_validator=self._frozen_content_validator,
        )
        if not analysis.seal_ready or analysis.content_identity != requested_identity:
            message = "; ".join(issue.message for issue in analysis.issues[:3])
            raise PlanFailure(
                "candidate_invalid",
                message or "Candidate failed seal validation.",
                work_ref=work_ref,
                revision=revision,
            )

        frozen_plan = {
            "sealed_content": analysis.sealed_content,
            "seal": {
                "encoding_profile": "mediasense-json-strings-sha256-v1",
                "content_identity": requested_identity,
                "final_confirmation": {
                    "confirmed_content_identity": requested_identity,
                    "confirmed_at": _format_datetime(confirmation.confirmed_at),
                    "confirmed_by": principal_ref,
                },
            },
        }
        artifact_path = self._publisher.artifact_path(snapshot.plan_ref)
        reservation = self.store.reserve_seal(
            request_id=request_id,
            request_digest=digest,
            confirmation_digest=confirmation_digest,
            work_ref=work_ref,
            revision=revision,
            candidate_identity=requested_identity,
            plan_ref=snapshot.plan_ref,
            artifact_path=str(artifact_path),
            frozen_plan=frozen_plan,
        )
        expected_bytes = self._publisher.serialize(reservation.frozen_plan)
        self._publisher.publish(Path(reservation.artifact_path), expected_bytes)
        verified = self._publisher.read_verified(Path(reservation.artifact_path))
        if verified != reservation.frozen_plan:
            raise PublicationConflict("published Frozen Plan changed after publication")

        result = {
            "outcome": "ok",
            "action": "seal",
            "work_ref": work_ref,
            "revision": revision,
            "state": "closed",
            "plan_ref": snapshot.plan_ref,
            "result_ref": snapshot.result_ref,
            "content_identity": requested_identity,
            "frozen_plan": reservation.frozen_plan,
        }
        return self.store.complete_seal(
            request_id=request_id,
            request_digest=digest,
            confirmation_digest=confirmation_digest,
            response=result,
        )

    def _optional_snapshot(self, work_ref: str | None) -> WorkSnapshot | None:
        if work_ref is None:
            return None
        try:
            return self.store.snapshot(work_ref)
        except WorkNotFound:
            return None


def _request_digest(request: Mapping[str, Any]) -> str:
    data = json.dumps(
        request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(data.encode("utf-8")).hexdigest()


def _confirmation_digest(confirmation: ConfirmationContext) -> str:
    value = {
        "principal_ref": confirmation.principal_ref,
        "confirmed_content_identity": confirmation.confirmed_content_identity,
        "confirmed_at": _format_datetime(confirmation.confirmed_at),
    }
    return _request_digest(value)


def _seal_request_digest(
    request: Mapping[str, Any], confirmation: ConfirmationContext
) -> str:
    return _request_digest(
        {
            "request": dict(request),
            "trusted_confirmation": {
                "principal_ref": confirmation.principal_ref,
                "confirmed_content_identity": confirmation.confirmed_content_identity,
                "confirmed_at": _format_datetime(confirmation.confirmed_at),
            },
        }
    )


def _format_datetime(value: datetime) -> str:
    normalized = value.astimezone(timezone.utc)
    return normalized.isoformat().replace("+00:00", "Z")


def _require_trusted_principal(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"^[^\s]+:[^\s]+$", value):
        raise PlanFailure("access_denied", "Trusted Human principal is invalid.")
    return value


def _require_keys(
    value: Mapping[str, Any], *, required: set[str], allowed: set[str]
) -> None:
    missing = required - set(value)
    extra = set(value) - allowed
    if missing or extra:
        parts = []
        if missing:
            parts.append("missing " + ", ".join(sorted(missing)))
        if extra:
            parts.append("unknown " + ", ".join(sorted(extra)))
        raise PlanFailure("invalid_request", "; ".join(parts))


def _require_ref(value: Any, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise PlanFailure("invalid_request", f"{name} is invalid.")
    return value


def _maybe_work_ref(request: Mapping[str, Any]) -> str | None:
    value = request.get("work_ref")
    return value if isinstance(value, str) and _WORK_REF.fullmatch(value) else None


def _error_response(action: str, error: PlanFailure) -> dict[str, Any]:
    response: dict[str, Any] = {
        "outcome": "error",
        "action": action,
        "error": {"code": error.code, "message": str(error)},
    }
    if error.work_ref is not None:
        response["work_ref"] = error.work_ref
    if error.revision is not None:
        response["revision"] = error.revision
    if error.current_revision is not None:
        response["error"]["current_revision"] = error.current_revision
    return response


def _encode_cursor(
    work_ref: str,
    revision: str,
    collection: str,
    offset: int,
    limit: int,
    signing_key: bytes,
) -> str:
    return _encode_cursor_value(
        {
            "work_ref": work_ref,
            "revision": revision,
            "collection": collection,
            "offset": offset,
            "limit": limit,
        },
        signing_key,
    )


def _encode_cursor_value(value: Any, signing_key: bytes) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded_payload = _base64_encode(payload)
    signature = hmac.new(
        signing_key, encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    return f"plan-cursor:{encoded_payload}.{_base64_encode(signature)}"


def _decode_cursor(
    token: Any,
    *,
    work_ref: str,
    revision: str,
    collection: str,
    requested_limit: int | None,
    signing_key: bytes,
) -> tuple[int, int]:
    if not isinstance(token, str) or not token.startswith("plan-cursor:"):
        raise PlanFailure(
            "invalid_cursor",
            "The page cursor is invalid.",
            work_ref=work_ref,
            revision=revision,
        )
    encoded = token.removeprefix("plan-cursor:")
    try:
        encoded_payload, encoded_signature = encoded.split(".", 1)
        signature = _base64_decode(encoded_signature)
        expected_signature = hmac.new(
            signing_key, encoded_payload.encode("ascii"), hashlib.sha256
        ).digest()
        if not hmac.compare_digest(signature, expected_signature):
            raise ValueError("cursor signature mismatch")
        payload = json.loads(_base64_decode(encoded_payload).decode("utf-8"))
    except (
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as exc:
        raise PlanFailure(
            "invalid_cursor",
            "The page cursor is invalid.",
            work_ref=work_ref,
            revision=revision,
        ) from exc
    if not isinstance(payload, dict) or set(payload) != {
        "work_ref",
        "revision",
        "collection",
        "offset",
        "limit",
    }:
        raise PlanFailure(
            "invalid_cursor",
            "The page cursor payload is invalid.",
            work_ref=work_ref,
            revision=revision,
        )
    expected = {
        "work_ref": work_ref,
        "revision": revision,
        "collection": collection,
    }
    if any(payload.get(key) != value for key, value in expected.items()):
        raise PlanFailure(
            "invalid_cursor",
            "The page cursor belongs to a different query.",
            work_ref=work_ref,
            revision=revision,
        )
    offset = payload.get("offset")
    cursor_limit = payload.get("limit")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise PlanFailure(
            "invalid_cursor",
            "The page cursor has an invalid position.",
            work_ref=work_ref,
            revision=revision,
        )
    if (
        not isinstance(cursor_limit, int)
        or isinstance(cursor_limit, bool)
        or not 1 <= cursor_limit <= 500
    ):
        raise PlanFailure(
            "invalid_cursor",
            "The page cursor has an invalid limit.",
            work_ref=work_ref,
            revision=revision,
        )
    if requested_limit is not None and requested_limit != cursor_limit:
        raise PlanFailure(
            "invalid_cursor",
            "The page cursor belongs to a different query.",
            work_ref=work_ref,
            revision=revision,
        )
    return offset, cursor_limit


def _base64_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _base64_decode(value: str) -> bytes:
    padded = value + "=" * (-len(value) % 4)
    return base64.b64decode(padded, altchars=b"-_", validate=True)
