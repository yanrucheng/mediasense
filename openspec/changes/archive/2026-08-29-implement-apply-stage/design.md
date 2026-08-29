## Context

Apply already has reviewed JSON contracts, a two-entity Run/Receipt model, accepted source-verification evidence, and accepted Darwin APFS preservation probes. The current implementation stops at durable read-only preparation. The remaining work is a high-risk local filesystem boundary with interruption windows and immutable outcome publication.

## Goals / Non-Goals

**Goals:**

- Implement the reviewed `move_originals` lifecycle end to end.
- Preserve exact authorization, non-overwrite, per-effect revalidation, durable recovery, and truthful Receipt semantics.
- Keep tests hermetic by default and retain the explicit opt-in cross-filesystem probe.

**Non-Goals:**

- No copy/link profiles, semantic replanning, arbitrary partial rewind, or source identity registry.
- No PreCheck database access, hash duplication in Frozen Plans, Dataset snapshot, or Source Verify Tool.
- No promise beyond the platform/filesystem profiles supported by executable evidence.

## Decisions

### Keep one Run authority and one Receipt authority

The existing Run SQLite store remains authoritative for mutable lifecycle, authorization, journal intent, observations, and recoverable publication. Immutable Receipt packages remain the terminal authority. Journal rows and publication reservations are internal Run mechanisms, not new product entities.

### Split by side-effect responsibility

`preparation.py` remains the stable preparation facade. `filesystem.py` owns non-overwriting effects, cross-store effect reservations, and postcondition observations. `execution.py` owns lifecycle transitions and reconciliation. `receipt.py` owns immutable encoding, atomic publication, segmentation, and bounded reads. This keeps public Tool boundaries unchanged while isolating dangerous code.

### Reverify at the effect boundary

Execution reuses the Result-scoped verification facts persisted by preparation, rechecks root and destination identities, streams current bytes for full SHA-256 and size, then records intent before mutation. Preparation success is not treated as a permanent permit.

### Recover from facts, not blind replay

For each durable intent, recovery distinguishes source-present/target-absent, source-absent/verified-target-present, duplicate presence, collision, and indeterminate states. Only the verified second state becomes completed without another effect.

### Publish one non-overwriting Receipt package

Receipt content is built from the durable ledger, schema-validated, written to a temporary sibling, fsynced, and published without replacement. A durable publication reservation lets restart converge on the same logical Receipt.

## Risks / Trade-offs

- **Filesystem behavior differs by platform** → Same-filesystem behavior uses tested non-overwrite primitives; cross-filesystem execution is enabled only for the accepted Darwin profile and blocks elsewhere.
- **Crash timing can make an effect uncertain** → Durable intent plus source/target re-observation prevents blind repetition and exposes indeterminate states.
- **Large receipts can exceed memory** → Receipts above the current internal threshold use content-bound immutable operation segments; Read verifies the package and streams bounded pages without exposing segment names as business references.
- **Existing preparation file is large** → Preserve its public facade and add focused private modules rather than mixing mutation code into it.

## Migration Plan

1. Preserve and merge the accepted preparation/Gate evidence.
2. Add runtime schema support and same-filesystem execution behind the current prepared Run.
3. Add Receipt publication/read and fault recovery.
4. Integrate the accepted cross-filesystem profile and discrepancy authorization.
5. Run focused, fault, scale, full, lint, and strict OpenSpec validation.
6. Activate the Apply contract only after both gates and runtime acceptance remain green.

Rollback is commit-level before release. Runtime tests use only isolated fixtures; no production migration is performed by this change.

## Open Questions

None blocking. Copy/link profiles and broader platform support remain later changes.
