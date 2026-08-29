## Why

The accepted Apply contract now has executable evidence for both activation gates, but the repository only implements read-only preparation. The first `move_originals` profile needs a recoverable implementation that preserves the existing Run, Receipt, authorization, and filesystem-safety boundaries.

## What Changes

- Activate the reviewed Apply Run, Receipt, and Read contracts after recording the closed gate evidence.
- Extend the durable Apply Run store through authorization, execution, pause/resume/cancel, reconciliation, verification, and Receipt publication.
- Implement non-overwriting same-filesystem moves and the accepted Darwin cross-filesystem preservation profile only inside controlled or caller-authorized roots.
- Publish immutable Receipts and expose bounded Receipt inspection/traversal.
- Add deterministic fault injection, recovery, scale, and end-to-end tests using temporary fixtures only.
- Preserve `mediasense.precheck.read` as the sole Source Item evidence boundary and keep hashes out of Frozen Plans.

## Capabilities

### New Capabilities

- `apply-stage-runtime`: Implements the already reviewed Apply Run, Receipt, and Read behavior for `move_originals`.

### Modified Capabilities

None. The existing Apply JSON contracts remain authoritative; this change implements and activates them.

## Impact

- Adds private Apply execution, filesystem, and Receipt modules under `src/mediasense/apply/`.
- Extends the existing private Run SQLite schema and public Apply package facade.
- Adds controlled temporary-filesystem, fault-recovery, Receipt, and end-to-end tests.
- Updates Apply lifecycle documentation, activation evidence, and indexes without changing PreCheck or Frozen Plan ownership.
