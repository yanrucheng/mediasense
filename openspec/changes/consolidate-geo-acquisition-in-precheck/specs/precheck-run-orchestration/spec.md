## MODIFIED Requirements

### Requirement: Execution is configuration- and dependency-driven
The orchestrator SHALL run only capabilities required by the durable Run contract
and SHALL derive ordering from producer dependencies. It MUST NOT materialize
every optional producer merely because one implementation exists. Product-level
`offline` configuration SHALL NOT select execution semantics; every external
effect SHALL instead depend on exact Run authority.

#### Scenario: Local work before external authorization
- **WHEN** a Run has not received reverse-geocode authority
- **THEN** local dependency-complete Work may finish, but zero provider requests occur and no incomplete Result is published

#### Scenario: Optional local evidence enabled
- **WHEN** an embedding or sensitivity profile and its local backend are enabled
- **THEN** the producer runs only after its required visual Artifact is available

### Requirement: Completion is gated by closure and immutable publication
The orchestrator SHALL publish only after accounting, navigation, Work/Artifact,
source-verification, required Geo acquisition, and Result integrity gates pass.
Publication SHALL recover idempotently across crashes before or after Result
registration. A provider-unavailable, authorization-missing, or Human-declined
Run SHALL NOT publish a Result.

#### Scenario: Seal succeeds
- **WHEN** every selected local gate succeeds and Geo acquisition is complete or not applicable
- **THEN** Run status becomes `completed` and references the exact readable immutable Result

#### Scenario: Geo closure is absent
- **WHEN** the frozen batch is non-empty and Geo acquisition has not reached an authorized executed outcome for every required coordinate
- **THEN** publication does not begin and no `plan_ready` Result exists

#### Scenario: Seal crash window
- **WHEN** execution stops after Result bytes are published or registered but before Run completion
- **THEN** retry adopts or reuses the one matching Result and never reports partial success

## ADDED Requirements

### Requirement: Expected Geo boundaries and implementation failures remain distinct
The Run lifecycle SHALL represent provider unavailability, missing authorization,
Human decline, localized provider outcome, and unexpected implementation failure
with different observable semantics. It SHALL NOT translate an unexpected
exception or invariant violation into `paused`, `blocked`, or authorization state.

#### Scenario: Provider is unavailable
- **WHEN** a non-empty frozen coordinate batch has no compatible configured provider
- **THEN** the Run terminates as `failed` with reason `provider_unavailable` before any authorization request or network access

#### Scenario: Authorization is missing
- **WHEN** a provider exists but matching trusted Human authority does not
- **THEN** the Run remains `paused` with reason `authorization_required` and a real resume condition

#### Scenario: Human declines
- **WHEN** the Human declines the exact pending disclosure
- **THEN** the Run becomes terminal `cancelled` with reason `authorization_declined`

#### Scenario: Implementation crashes
- **WHEN** a valid authorized provider path raises an unexpected exception
- **THEN** the exception reaches the worker failure boundary and the Run becomes `failed` with an implementation diagnostic rather than an expected domain outcome

