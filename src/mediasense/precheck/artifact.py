"""Stable internal entry point for immutable PreCheck Artifacts."""

from ._artifact_sqlite import SQLiteArtifactStore
from ._artifact_types import (
    ArtifactAudit,
    ArtifactDraft,
    ArtifactError,
    ArtifactIntegrity,
    ArtifactIntegrityError,
    ArtifactRecord,
    InvalidArtifactDraft,
)


class ArtifactStore(SQLiteArtifactStore):
    """Coordinate unpublished writes, immutable publication, and verification."""


__all__ = [
    "ArtifactAudit",
    "ArtifactDraft",
    "ArtifactError",
    "ArtifactIntegrity",
    "ArtifactIntegrityError",
    "ArtifactRecord",
    "ArtifactStore",
    "InvalidArtifactDraft",
]
