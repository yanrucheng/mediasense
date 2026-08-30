## ADDED Requirements

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

## MODIFIED Requirements

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

### Requirement: Routing and caller state remain isolated
Geo request or batch routing state SHALL be immutable and invocation-scoped. The
public Tool and shared provider-neutral implementation SHALL NOT read or mutate
PreCheck or Plan private storage, confirmation state, Work records, or caches.
Reuse of provider adapters SHALL NOT require PreCheck to invoke the public Tool.

#### Scenario: PreCheck and Plan calls overlap
- **WHEN** a PreCheck batch and a Plan Geo Tool request use shared provider adapters concurrently
- **THEN** provider or language observations from either call cannot alter the other's route unless supplied explicitly in that call's authorized context
