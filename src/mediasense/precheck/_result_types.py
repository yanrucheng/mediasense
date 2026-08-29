"""Internal construction types for immutable PreCheck Results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path


class ResultSealError(RuntimeError):
    """Raised when mutable working state cannot be honestly sealed."""


@dataclass(frozen=True, slots=True)
class ResultSourceItem:
    ref: str
    relative_path: Path
    locator: dict[str, object]
    scope: str
    condition: str
    basis: object | None = None
    observations: tuple[dict[str, object], ...] = ()
    qualifications: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class ResultEvidence:
    ref: str
    access: dict[str, object]
    artifact_id: str | None = None
    work_id: str | None = None
    observations: tuple[dict[str, object], ...] = ()
    qualifications: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class ResultRelationship:
    origin_ref: str
    relation: str
    target_ref: str
    target_kind: str
    basis: object | None = None
    qualifications: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class ResultDraft:
    run_id: str
    dataset_id: str
    dataset_ref: str
    dataset_name: str | None
    dataset_context: tuple[dict[str, object], ...]
    coverage: str
    readiness: str
    integrity: str
    sources: tuple[ResultSourceItem, ...]
    evidence: tuple[ResultEvidence, ...]
    entry_evidence: tuple[str, ...]
    relationships: tuple[ResultRelationship, ...]
    qualifications: tuple[dict[str, object], ...]
    execution_boundary: dict[str, object]
    supporting_work_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SealedResult:
    result_ref: str
    dataset_id: str
    path: Path
    digest: str
    size_bytes: int
    published_at: datetime


@dataclass(frozen=True, slots=True)
class ResultAudit:
    available: tuple[str, ...]
    missing: tuple[str, ...]
    corrupt: tuple[str, ...]
    orphan_paths: tuple[Path, ...]
    unpublished_paths: tuple[Path, ...]


def source_root_reference(dataset_id: str, reuse_domain: str) -> str:
    """Name one source attachment without exposing its absolute path."""

    digest = hashlib.sha256(
        f"source-root-v1\0{dataset_id}\0{reuse_domain}".encode("utf-8")
    ).hexdigest()
    return f"source-root:{digest}"


def result_local_reference(kind: str, *semantic_parts: str) -> str:
    """Create a retry-stable opaque reference within one Result assembly."""

    if kind not in {"source-item", "evidence"} or not semantic_parts:
        raise ValueError("invalid Result-local reference input")
    digest = hashlib.sha256(
        json.dumps(
            ["result-local-v1", kind, *semantic_parts],
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return f"{kind}:{digest}"
