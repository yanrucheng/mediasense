## MODIFIED Requirements

### Requirement: Exact PreCheck entry boundary
The Plan Working State implementation SHALL consume one exact immutable PreCheck
Result only through `mediasense.precheck.read`. It SHALL accept `coverage` of
`complete` or bounded `partial` only when `readiness` is `plan_ready`, `integrity`
is `valid`. It SHALL NOT inspect Geo query batches, deduplication, caches,
acquisition status, PreCheck SQLite, or internal runtime records.

#### Scenario: Create from a usable partial Result
- **WHEN** `create` names a readable Result with partial coverage, Plan-ready readiness, and valid integrity
- **THEN** the Tool creates one Working State bound to that exact `result_ref`

#### Scenario: Reject effective historical readiness
- **WHEN** PreCheck Read safely projects an old incomplete Result as `blocked`
- **THEN** the Tool returns `precheck_not_ready` without inspecting Geo acquisition internals and creates no Working State

#### Scenario: Reject an unusable Result
- **WHEN** the named Result is missing, blocked, or invalid
- **THEN** the Tool returns the contract-defined error and creates no Working State

### Requirement: Source safety and stage boundary
Plan operations SHALL remain read-only with respect to source media and SHALL NOT
perform Apply filesystem operations or new PreCheck evidence production. The Plan
Work Tool SHALL NOT invoke a Geo Provider; a Plan Agent may separately call the
stage-neutral Geo Tool and record only the material Plan judgment or request
reference. Plan SHALL require a successor PreCheck when Result coverage is
incomplete.

#### Scenario: Plan handles a candidate
- **WHEN** any Plan action validates, stores, previews, or seals candidate content
- **THEN** no source media is moved, copied, renamed, deleted, or rewritten and the Plan Work Tool performs no provider request

#### Scenario: Machine place evidence is insufficient
- **WHEN** Result Geo evidence cannot support a material Plan judgment
- **THEN** Plan may ask the Human, make a separately authorized bounded Geo Tool query, or return to PreCheck, while keeping the immutable Result unchanged

## REMOVED Requirements

### Requirement: Plan-owned Geo observations remain epistemically and operationally separate
**Reason**: Provider acquisition is available through the shared Geo Tool; duplicating its authorization, replay, and observation lifecycle inside Plan divides authority.

**Migration**: Read ordinary evidence through `mediasense.precheck.read`, call `mediasense.geo.query` directly only for bounded investigation, and record only distinguishable Agent judgment, request reference, or Human semantic decisions in Plan.

### Requirement: Geo enrichment does not weaken the Plan stage boundary
**Reason**: `enrich_geo` is removed because the shared Geo Tool is the integration boundary.

**Migration**: Complete missing coverage in a successor PreCheck Run; use the shared Geo Tool only to challenge or refine already complete Result evidence.

### Requirement: Geo observation storage is revision-bound and idempotent
**Reason**: Plan no longer owns provider observations, authorization, replay, or retention state.

**Migration**: Abandon old no-Candidate Working State and create new Plan state from a compliant Result; no private database migration is provided.
