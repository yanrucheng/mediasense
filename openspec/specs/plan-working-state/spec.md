# plan-working-state Specification

## Purpose
TBD - created by archiving change implement-plan-stage. Update Purpose after archive.
## Requirements
### Requirement: Exact PreCheck entry boundary
The Plan Working State implementation SHALL consume one exact immutable PreCheck Result only through the `mediasense.precheck.read` contract. It SHALL accept `coverage` of `complete` or bounded `partial` only when `readiness` is `plan_ready` and `integrity` is `valid`, and SHALL NOT read PreCheck SQLite, caches, or internal runtime records.

#### Scenario: Create from a usable partial Result
- **WHEN** `create` names a readable Result with `coverage=partial`, `readiness=plan_ready`, and `integrity=valid`
- **THEN** the Tool creates one Working State bound to that exact `result_ref`

#### Scenario: Reject an unusable Result
- **WHEN** the named Result is missing, blocked, or invalid
- **THEN** the Tool returns the contract-defined error and creates no Working State

### Requirement: Mutable Working State authority
The implementation SHALL keep each Work's exact Result binding, open or closed lifecycle, opaque current revision, organization-preference snapshot, complete candidate content, and idempotency state in `work.sqlite3`. It SHALL NOT copy the PreCheck Result or Default Organization Profile into the Plan store.

#### Scenario: Inspect current state
- **WHEN** `inspect` omits a revision for an open Work
- **THEN** the Tool atomically resolves and returns the current opaque revision and requested sections

#### Scenario: Inspect exact state
- **WHEN** `inspect` names an available exact revision
- **THEN** every returned section and cursor is bound to that revision

### Requirement: Safe request replay
The implementation SHALL apply the existing `request_id` semantics to `create`, `update`, and `seal`: an identical replay returns the original result, while reuse with different effective input returns `idempotency_conflict` without another state transition.

#### Scenario: Recover a lost create response
- **WHEN** an identical successful `create` request is repeated
- **THEN** the Tool returns the same `work_ref` and revision rather than creating another Work

#### Scenario: Reject changed input under the same request ID
- **WHEN** a caller reuses a prior `request_id` with different effective input
- **THEN** the Tool returns `idempotency_conflict` and preserves existing state

### Requirement: Atomic candidate replacement
The `update` action SHALL require the current `base_revision` and a complete candidate. A successful update SHALL atomically replace candidate content and, when supplied, the complete organization-preference snapshot, then return a new opaque revision. Conversation and tentative reasoning that have not been submitted through `update` SHALL NOT create revisions.

#### Scenario: Replace a coherent candidate
- **WHEN** `update` supplies the current revision and conforming complete candidate content
- **THEN** the Tool stores the candidate as one transition and returns a different opaque revision

#### Scenario: Reject a stale writer
- **WHEN** `update` supplies a non-current `base_revision`
- **THEN** the Tool returns `revision_conflict` and does not overwrite the current candidate

### Requirement: Deterministic candidate validation and identity
The Tool SHALL first materialize candidate content as `sealed_content` and validate it with the authoritative active Frozen Plan Schema. It SHALL then validate Result binding, Result-local references, complete source-set expansion, disjoint outcome coverage, path and naming constraints, and companion semantic invariants. Only a candidate that passes both authoritative Schema validation and semantic validation SHALL receive a global `candidate_content_identity`.

#### Scenario: Candidate is sealable
- **WHEN** the exact candidate satisfies every structural and semantic invariant for its bounded scope
- **THEN** `inspect` reports `seal_ready=true` and one candidate content identity shared by every page

#### Scenario: Candidate is not sealable
- **WHEN** candidate references, coverage, paths, or outcomes violate a deterministic invariant
- **THEN** `inspect` reports localized validation issues, `seal_ready=false`, and no sealable identity

#### Scenario: Schema rejects materialized content
- **WHEN** materialized `sealed_content` violates the authoritative Frozen Plan Schema, including uniqueness constraints
- **THEN** the runtime rejects the candidate before identity generation and cannot report `seal_ready=true`

#### Scenario: File path collides with a logical directory
- **WHEN** one Source Item resolves to `foo/bar` while a logical group requires `foo/bar/` as a directory
- **THEN** semantic validation reports a file/directory collision and the candidate is not sealable

### Requirement: Cursor integrity
Every pagination cursor SHALL be opaque, revision-bound, query-bound, restart-stable, and protected against undetected modification. Any malformed cursor or modification of its position, limit, revision, collection, or other payload SHALL return `invalid_cursor` rather than omitting or duplicating content.

#### Scenario: Cursor payload is modified
- **WHEN** a caller changes a cursor payload without a valid integrity signature
- **THEN** `inspect` returns `invalid_cursor` and no content page

#### Scenario: Cursor is used after Tool restart
- **WHEN** an unmodified cursor is submitted to a new Tool instance over the same Plan store
- **THEN** the Tool verifies it with the persisted signing key and continues the bound page correctly

### Requirement: Trusted and recoverable sealing
The `seal` action SHALL bind one open Work, exact current revision, exact candidate identity, idempotent request, and trusted Human authentication context. Success SHALL publish one complete immutable Frozen Plan JSON and close the Work only when the file and committed SQLite outcome agree.

#### Scenario: Seal the reviewed candidate
- **WHEN** trusted Human confirmation is bound to the current sealable candidate identity
- **THEN** the Tool publishes the conforming Frozen Plan, closes the Work, and returns the same authoritative Plan on identical retry

#### Scenario: Reject stale confirmation
- **WHEN** confirmation names an older revision or content identity
- **THEN** the Tool refuses sealing and preserves the current open Work

#### Scenario: Recover interrupted publication
- **WHEN** a verified final artifact exists for a reserved seal attempt but the SQLite close transition was interrupted
- **THEN** retry recovers that exact artifact and completes the original transition without allocating a second Plan

### Requirement: Source safety and stage boundary
Plan operations SHALL remain read-only with respect to source media and SHALL NOT perform Apply operations, reverse geocoding, or new upstream evidence production.

#### Scenario: Plan handles a candidate
- **WHEN** any Plan action validates, stores, previews, or seals candidate content
- **THEN** no source media is moved, copied, renamed, deleted, or rewritten

