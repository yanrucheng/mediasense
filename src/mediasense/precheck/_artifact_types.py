"""Private value types for immutable Artifact publication and verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class ArtifactIntegrity(StrEnum):
    AVAILABLE = "available"
    MISSING = "missing"
    CORRUPT = "corrupt"


class ArtifactError(RuntimeError):
    """Base error for Artifact lifecycle failures."""


class InvalidArtifactDraft(ArtifactError):
    """Raised when unpublished bytes are absent, unsafe, or incomplete."""


class ArtifactIntegrityError(ArtifactError):
    """Raised when published Artifact bytes no longer match their identity."""


@dataclass(frozen=True, slots=True)
class ArtifactDraft:
    work_id: str
    lease_token: str
    path: Path


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    digest_algorithm: str
    digest: str
    size_bytes: int
    media_type: str
    path: Path
    integrity: ArtifactIntegrity
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ArtifactAudit:
    available: tuple[str, ...]
    missing: tuple[str, ...]
    corrupt: tuple[str, ...]
    orphan_paths: tuple[Path, ...]
    unpublished_paths: tuple[Path, ...]
