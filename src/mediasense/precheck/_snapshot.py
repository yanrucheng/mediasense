"""Verify a declared immutable input snapshot and retain occurrence bindings."""

from dataclasses import replace
from pathlib import Path

from ._fingerprint import FINGERPRINT_ALGORITHM, fingerprint_candidate, stat_identity
from ._result_types import source_root_reference
from .discovery import DiscoveredSource, SourceKind, SourceScope, SourceCondition


ACCOUNTING_FIELDS = (
    "kind",
    "source_revision",
    "size_bytes",
    "mtime_ns",
    "device_id",
    "inode",
    "mode",
    "fingerprint_algorithm",
    "fingerprint",
)


class SourceSnapshotChanged(ValueError):
    pass


def snapshot_events(accounting, run_id, snapshot):
    """Observe only explicitly bound occurrences; never enumerate the directory."""
    from .accounting import _same_root_identity
    from .source_attachment import AttachmentState
    from ._orchestrator import _BlockedExecution

    attachment = accounting.get_source_attachment(run_id)
    probe = accounting._probe(attachment.source_root)
    if probe.state is not AttachmentState.AVAILABLE:
        raise _BlockedExecution(
            "source_attachment_unavailable",
            "The bound source attachment is unavailable.",
            "Restore the bound source attachment and resume this Run.",
        )
    if not _same_root_identity(attachment, probe):
        raise SourceSnapshotChanged("The declared source root binding changed.")
    row = accounting._database.load_run(run_id)
    root_ref = source_root_reference(row["dataset_id"], attachment.reuse_domain)
    for member in snapshot["members"]:
        locator = member["locator"]
        if locator["source_root_ref"] != root_ref:
            raise SourceSnapshotChanged(
                "The input occurrence belongs to a different source attachment."
            )
        relative = Path(locator["value"])
        if relative.is_absolute() or relative == Path(".") or ".." in relative.parts:
            raise SourceSnapshotChanged(
                "The sealed input locator is not source relative."
            )
        path = attachment.source_root / relative
        # Do not traverse symlinked parent directories while verifying a binding.
        parent = path.parent
        while parent != attachment.source_root:
            if parent.is_symlink():
                raise SourceSnapshotChanged("An input parent became a symbolic link.")
            parent = parent.parent
        recorded = member.get("accounting")
        try:
            observed = path.lstat()
        except FileNotFoundError as error:
            if not attachment.source_root.exists():
                raise _BlockedExecution(
                    "source_attachment_unavailable",
                    "Source attachment disconnected during verification.",
                    "Restore the bound source attachment and resume.",
                ) from error
            raise SourceSnapshotChanged(
                "A declared input occurrence no longer exists."
            ) from error
        except OSError as error:
            raise _BlockedExecution(
                "source_verification_unavailable",
                "A declared input could not be inspected.",
                "Restore read access to the bound input and resume.",
            ) from error
        if recorded is not None:
            expected = tuple(
                recorded.get(k)
                for k in ("size_bytes", "mtime_ns", "device_id", "inode", "mode")
            )
            if (
                all(v is not None for v in expected)
                and stat_identity(observed) != expected
            ):
                raise SourceSnapshotChanged(
                    "A declared input revision changed since its Result was sealed."
                )
        kind = (
            SourceKind(recorded["kind"])
            if recorded is not None
            else _historical_kind(relative)
        )
        event = DiscoveredSource(
            relative,
            path,
            kind,
            SourceScope(member["scope"]),
            SourceCondition(member["condition"]),
            ("explicit_result_input",),
            *stat_identity(observed),
        )
        try:
            proof = fingerprint_candidate(event)
        except OSError as error:
            raise _BlockedExecution(
                "source_verification_unavailable",
                "A declared input could not be verified.",
                "Restore stable read access to this input and resume.",
            ) from error
        verification = member["source_content_verification"]
        algorithm = (
            recorded.get("fingerprint_algorithm")
            if recorded
            else verification.get("profile")
        )
        digest = (
            recorded.get("fingerprint")
            if recorded
            else str(verification.get("value", "")).removeprefix("sha256:")
        )
        if algorithm == FINGERPRINT_ALGORITHM and digest and proof.value != digest:
            raise SourceSnapshotChanged(
                "A declared input fingerprint changed since its Result was sealed."
            )
        yield event, proof


def process_snapshot(accounting, run_id, snapshot, should_continue):
    from ._accounting_types import WorkingRunStatus
    from itertools import chain

    # Verification is repeated after interruption; preparation Work remains reusable.
    iterator = snapshot_events(accounting, run_id, snapshot)
    first = next(iterator, None)
    attachment = accounting.get_source_attachment(run_id)
    generation = accounting._database.prepare_run(
        run_id, accounting._probe(attachment.source_root)
    )
    events, proofs = [], {}
    for event, proof in chain(() if first is None else (first,), iterator):
        events.append(event)
        proofs[event.relative_path] = proof
        if len(events) >= 256:
            accounting._database.commit_batch(
                run_id, generation, events, lambda item: proofs[item.relative_path]
            )
            events, proofs = [], {}
            if not should_continue():
                accounting._database.set_status(run_id, WorkingRunStatus.PAUSED)
                return
    if events:
        accounting._database.commit_batch(
            run_id, generation, events, lambda item: proofs[item.relative_path]
        )
    accounting._database.finish_run(run_id, generation, reconcile_absence=False)


def seal_preparation(draft, preparation):
    """Rebind already verified explicit occurrences into this Result's namespace."""
    if preparation is None:
        return draft
    from copy import deepcopy
    from ._preparation import preparation_readback, canonical
    from ._result_types import ResultSealError

    sealed = {
        k: deepcopy(preparation[k]) for k in ("profile", "configuration", "scopes")
    }
    snapshot = preparation["input"]
    bindings = None
    if snapshot is not None:
        by_path = {s.relative_path.as_posix(): s for s in draft.sources}
        refs = {}
        bindings = {
            "result_ref": snapshot["result_ref"],
            "digest": snapshot["digest"],
            "members": [],
        }
        for member in snapshot["members"]:
            source = by_path[member["locator"]["value"]]
            refs[member["source_item_ref"]] = source.ref
            record = member.get("accounting")
            verification = member["source_content_verification"]
            algorithm = (
                record.get("fingerprint_algorithm")
                if record
                else verification.get("profile")
            )
            digest = (
                record.get("fingerprint")
                if record
                else str(verification.get("value", "")).removeprefix("sha256:")
            )
            status = (
                "verified"
                if algorithm == FINGERPRINT_ALGORITHM and digest
                else ("unsupported" if algorithm else "unavailable")
            )
            bindings["members"].append(
                {
                    "input_ref": member["source_item_ref"],
                    "target_ref": source.ref,
                    "locator": deepcopy(member["locator"]),
                    "verification": {
                        "profile": algorithm,
                        "value": digest,
                        "status": status,
                    },
                }
            )
        sealed["scopes"] = [[refs[ref] for ref in scope] for scope in sealed["scopes"]]
    # The Result stores normalized selectors, not references into the old Result.
    readback = preparation_readback("precheck-result:pending", sealed)
    sealed["profile"] = readback["profile"]
    if len(canonical(readback).encode()) > 524288:
        raise ResultSealError(
            "Complete preparation readback exceeds the response envelope"
        )
    return replace(draft, preparation=sealed, input_bindings=bindings)


def _historical_kind(path):
    from .discovery import (
        _IMAGE_EXTENSIONS,
        _VIDEO_EXTENSIONS,
        _RAW_EXTENSIONS,
        _SIDECAR_EXTENSIONS,
    )

    suffix = path.suffix.lower()
    for extensions, kind in (
        (_IMAGE_EXTENSIONS, SourceKind.IMAGE),
        (_VIDEO_EXTENSIONS, SourceKind.VIDEO),
        (_RAW_EXTENSIONS, SourceKind.RAW_IMAGE),
        (_SIDECAR_EXTENSIONS, SourceKind.SIDECAR),
    ):
        if suffix in extensions:
            return kind
    return SourceKind.GPX if suffix == ".gpx" else SourceKind.UNKNOWN


def binding_correspondence(row):
    """A regenerable public view of the retained occurrence verification."""
    verification = row["verification"]
    if verification["status"] != "verified":
        return {
            "status": "unproven",
            "basis": {
                "code": "verification_not_supported"
                if verification["status"] == "unsupported"
                else "verification_unavailable"
            },
        }
    return {
        "status": "matched",
        "source_item_ref": row["target_ref"],
        "basis": {
            "code": "recorded_input_binding",
            "verification_profile": verification["profile"],
        },
        "qualifications": [
            {
                "code": "ordinary_change_detection_only",
                "effect": "limits_interpretation",
                "message": "The bound occurrence passed ordinary change detection, not a full-byte equality proof.",
            }
        ],
    }
