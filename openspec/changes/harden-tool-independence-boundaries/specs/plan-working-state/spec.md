## MODIFIED Requirements

### Requirement: Trusted and recoverable sealing
The `seal` action SHALL bind one open Work, exact current revision, exact candidate
identity, idempotent request, and trusted Human authentication context. Success
SHALL publish one complete immutable Frozen Plan JSON, close the Work only when the
file and committed SQLite outcome agree, and return that complete schema-valid
Frozen Plan object as the formal handoff consumable by Apply prepare.

#### Scenario: Seal the reviewed candidate
- **WHEN** trusted Human confirmation is bound to the current sealable candidate identity
- **THEN** the Tool publishes the conforming Frozen Plan, closes the Work, returns the complete Frozen Plan object, and returns the same authoritative Plan on identical retry

#### Scenario: Reject stale confirmation
- **WHEN** confirmation names an older revision or content identity
- **THEN** the Tool refuses sealing and preserves the current open Work

#### Scenario: Recover interrupted publication
- **WHEN** a verified final artifact exists for a reserved seal attempt but the SQLite close transition was interrupted
- **THEN** retry recovers that exact artifact and completes the original transition without allocating a second Plan

### Requirement: Source safety and stage boundary
Plan operations SHALL remain read-only with respect to source media and SHALL NOT
perform Apply filesystem operations or new PreCheck evidence production. Candidate
validation, inspection, preview, and seal SHALL perform no Geo provider request;
only the explicit `enrich_geo` action MAY invoke the stage-neutral Geo capability
under matching Plan-scoped authority.

#### Scenario: Plan handles a candidate
- **WHEN** any Plan action validates, stores, previews, or seals candidate content
- **THEN** no source media is moved, copied, renamed, deleted, or rewritten and no implicit Geo request occurs

### Requirement: Geo observation storage is revision-bound and idempotent
The existing `mediasense.plan.work` Tool SHALL provide `enrich_geo` as the
Plan-owned coordination action. Authorization preflight or mismatch SHALL preserve
the current revision. A Human refusal recorded by Plan SHALL stop before Geo Tool
invocation. Persisting a terminal Geo observation outcome SHALL atomically append
its observation and authorization evidence, advance the Working State revision,
and apply Plan request-id replay semantics.

#### Scenario: Geo authorization is required
- **WHEN** `enrich_geo` reaches the Geo boundary without matching authority
- **THEN** it returns the proposed Geo authorization requirement and leaves Plan Working State unchanged

#### Scenario: Human refuses before invocation
- **WHEN** the Human declines Plan's proposed Geo request
- **THEN** Plan performs no Geo invocation and does not create a provider observation revision

#### Scenario: Geo observation is persisted
- **WHEN** an authorized Geo request returns a terminal observation outcome
- **THEN** Plan stores it under a new revision while preserving the existing candidate and immutable Result binding

#### Scenario: Plan enrichment response is lost
- **WHEN** an identical `enrich_geo` request is replayed after its Plan state transition completed
- **THEN** the Tool returns the recorded response without another revision or provider request
