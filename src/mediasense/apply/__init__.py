"""Pre-activation Apply preparation primitives.

This package deliberately exposes no filesystem-mutation entry point.  It can
build and inspect durable Apply Runs while the review contract's activation
gates remain open.
"""

from .preparation import (
    ApplyPreparationError,
    ApplyRunStore,
    IdempotencyConflict,
    PrecheckReadBoundary,
    PreparedRun,
    SourceEvidenceError,
    SourceItemEvidence,
    SourceSetExpansion,
    VerificationBasis,
)

__all__ = [
    "ApplyPreparationError",
    "ApplyRunStore",
    "IdempotencyConflict",
    "PrecheckReadBoundary",
    "PreparedRun",
    "SourceEvidenceError",
    "SourceItemEvidence",
    "SourceSetExpansion",
    "VerificationBasis",
]
