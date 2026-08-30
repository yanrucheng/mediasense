# geo-capability Specification

## Purpose
Define the stage-neutral, authorization-bound Geo Tool family that turns exact
coordinates into challengeable place observations while preserving progressive
evidence, provider replacement, observable effects, safe replay, and caller-owned
interpretation and state.
## Requirements
### Requirement: Geo exposes progressive caller-meaningful operations
The Geo capability SHALL expose one Tool family with a high-level
`resolve_place` operation and bounded `reverse_geocode` and `nearby_places`
operations. It SHALL return provider-derived candidate observations rather than a
final place, naming, grouping, or Human-intent decision.

#### Scenario: High-level evidence is sufficient
- **WHEN** `resolve_place` returns candidate evidence that the calling Agent judges sufficient for its task
- **THEN** the caller can stop without invoking a lower-level operation or learning provider-specific APIs

#### Scenario: More specific evidence may help
- **WHEN** a result is incomplete, ambiguous, or conflicting and a narrower operation is applicable
- **THEN** the result identifies a bounded continuation, its additional information, and any additional effect or authority requirement

### Requirement: Every external effect is bound to exact authority
Before a provider request, the Geo Tool SHALL verify authority for the exact
normalized subjects, operation, transmitted data classes, provider constraints,
fallback ceiling, logical-query count, provider-request ceiling, cost or quota
ceiling when knowable, and retention scope. Without authority it SHALL perform no
network effect and return `authorization_required` with the exact proposed
authorization envelope. If supplied authority does not match, it SHALL perform no
network effect, return `authorization_required` with an
`authorization_mismatch` qualification, and expose the newly required envelope.
Neither result means that the Human refused; explicit refusal belongs to the caller
stage and does not require invoking Geo.

#### Scenario: First live lookup requires authorization
- **WHEN** a caller requests an effectful operation without matching delegated authority
- **THEN** the Tool returns `authorization_required` with the normalized request fingerprint and proposed effect envelope and sends zero provider requests

#### Scenario: Supplied authorization does not match
- **WHEN** authority is supplied for a different request or insufficient effect envelope
- **THEN** the Tool returns `authorization_required` with an `authorization_mismatch` qualification and the exact proposed envelope and sends zero provider requests

#### Scenario: Human declines the proposed request
- **WHEN** the Human declines the proposed coordinate egress before invocation
- **THEN** the caller records the refusal if needed and does not call the Geo Tool

#### Scenario: A continuation needs broader effects
- **WHEN** a continuation would add a provider, request, cost, transmitted data class, or retained result beyond existing authority
- **THEN** the Tool does not begin that additional effect and returns the exact authority required for a new request

#### Scenario: A frozen request changes
- **WHEN** any authority-bearing dimension of an authorized request changes
- **THEN** the prior authorization does not apply to the changed request

### Requirement: Geo enforces coordinate-only data egress
The Geo provider boundary SHALL admit only normalized coordinates, datum, requested
locale, and provider-required lookup controls. It SHALL reject source media,
renditions, embeddings, prompts, paths, filenames, captions, and general metadata
as `invalid_request` before provider access.

#### Scenario: Caller includes forbidden context
- **WHEN** a request attempts to transmit a media path, media content, feature, prompt, caption, or unrelated metadata
- **THEN** the Tool returns `invalid_request` and sends zero provider requests

### Requirement: Results preserve component outcomes and effect evidence
Each result SHALL distinguish requested from unrequested evidence components and
SHALL report normalized candidates, qualifications, ordered provider attempts,
actual data egress, logical operations, provider requests, billable units or
`unknown`, fallback, and material uncertainty. Overall `success`, `partial`,
`no_result`, `authorization_required`, `unavailable`, `failed`, `indeterminate`,
and `cancelled` outcomes SHALL remain distinguishable where applicable. The Tool
SHALL NOT report Human refusal unless a future contract supplies trusted refusal
evidence.

#### Scenario: Address succeeds and nearby lookup fails
- **WHEN** an authorized operation produces address evidence but its requested nearby-place component fails
- **THEN** the Tool returns `partial`, preserves the address candidate, and reports the nearby component failure and observed effects

#### Scenario: Nearby lookup was not requested
- **WHEN** authority and operation cover address evidence only
- **THEN** the nearby component is `not_requested`, not `no_result`, and no nearby provider work occurs

#### Scenario: Provider effect cannot be determined
- **WHEN** a timeout or transport failure occurs after request transmission and completion or billing cannot be established
- **THEN** the attempt and overall effect report preserve the indeterminate state rather than reporting zero requests or zero cost

#### Scenario: Cancellation is observed between provider requests
- **WHEN** cancellation is requested before another provider request begins
- **THEN** the Tool admits no new request, preserves effects already observed, marks remaining components `not_requested`, and returns `cancelled`

#### Scenario: One effect becomes indeterminate in a batch
- **WHEN** one provider request may have been transmitted but its completion or billing cannot be established
- **THEN** the Tool sends no later batch request automatically and marks the remaining components `not_requested`

### Requirement: Geo request validation is strict and contract-conformant
The Geo Tool SHALL accept every request that satisfies its input schema and SHALL reject every request that violates a runtime-enforced input invariant. Every coordinate SHALL name its datum explicitly. Required references and locales SHALL contain at least one non-whitespace character, and neither JSON Schema defaults nor runtime code SHALL silently supply a missing datum.

#### Scenario: Datum is omitted
- **WHEN** a subject coordinate omits `datum`
- **THEN** both the input schema and runtime reject the request before any provider effect

#### Scenario: Required text contains only whitespace
- **WHEN** `subject_ref` or the request locale contains only whitespace
- **THEN** both the input schema and runtime reject the request before any provider effect

#### Scenario: Contract-valid request reaches preflight
- **WHEN** a request satisfies every input-schema invariant and has no matching authority
- **THEN** the runtime accepts the request shape and returns a schema-valid, zero-effect authorization preflight

### Requirement: Provider replacement preserves capability semantics
Providers SHALL implement operation-aware ports and normalize their results without
exposing provider-native response fields as the public contract. Routing and
fallback MAY select among configured providers but SHALL remain within the caller's
effect envelope and SHALL preserve every attempted provider as provenance.

#### Scenario: Provider fallback is permitted
- **WHEN** the selected provider fails transiently and the authorized envelope permits another configured provider
- **THEN** the Tool may attempt the fallback and reports both attempts and their actual effects

#### Scenario: Provider fallback is not permitted
- **WHEN** the next provider or request would exceed the authorized envelope
- **THEN** the Tool stops before that request and reports the bounded next action without silently broadening authority

### Requirement: Routing and caller state remain isolated
Geo request or batch routing state SHALL be immutable and invocation-scoped. The
public Tool and shared provider-neutral implementation SHALL NOT read or mutate
PreCheck or Plan private storage, confirmation state, Work records, or caches.
Reuse of provider adapters SHALL NOT require PreCheck to invoke the public Tool.

#### Scenario: PreCheck and Plan calls overlap
- **WHEN** a PreCheck batch and a Plan Geo Tool request use shared provider adapters concurrently
- **THEN** provider or language observations from either call cannot alter the other's route unless supplied explicitly in that call's authorized context

### Requirement: Credentials remain outside durable identity and evidence
Provider credentials SHALL be supplied only to the adapter that needs them and
SHALL NOT appear in request fingerprints, results, logs, stage state, cache keys,
or retained observations.

#### Scenario: Result and persisted evidence are inspected
- **WHEN** a completed or failed Geo operation is serialized or stored by a caller
- **THEN** no provider credential value is present

### Requirement: Effectful request replay is safe
The Geo Tool SHALL bind each effectful invocation's `request_id` to its effective
request identity, authorization binding, execution state, and terminal result in a
minimal operation journal. An identical retry SHALL return the recorded terminal
outcome without another provider request. Reuse with different effective input or
authority SHALL be refused. An interrupted invocation whose provider effect cannot
be established SHALL remain `indeterminate` and SHALL NOT be retried automatically.

#### Scenario: Successful response was lost
- **WHEN** a caller repeats the same authorized request with the same `request_id` after the original operation completed
- **THEN** the Tool returns the recorded result and sends zero additional provider requests

#### Scenario: Request ID is reused with changed authority
- **WHEN** a caller reuses a prior `request_id` with a different request fingerprint or authorization binding
- **THEN** the Tool returns an idempotency conflict and performs no provider request

#### Scenario: Prior provider effect is indeterminate
- **WHEN** the journal records that a request may have been transmitted but no terminal provider outcome is known
- **THEN** an identical retry returns `indeterminate` and does not automatically repeat the effect
