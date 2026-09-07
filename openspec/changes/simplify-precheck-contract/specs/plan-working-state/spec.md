## MODIFIED Requirements

### Requirement: Exact PreCheck entry boundary
Plan Working State SHALL consume one exact immutable Result only through the trusted PreCheck Read contract. Successful Read SHALL enforce integrity checks; Plan SHALL accept complete or bounded partial coverage when readiness is plan_ready without requiring an integrity constant in the payload. It SHALL NOT read PreCheck SQLite, caches, acquisition groups or Provider state. Missing coordinates, no_result or terminal location failure SHALL NOT alone prevent entry or force Agent reacquisition.

#### Scenario: Create from a usable partial Result
- **WHEN** trusted Read returns partial coverage and plan_ready with material qualifications
- **THEN** Plan creates one Working State bound to that exact Result without expecting integrity:valid

#### Scenario: Reject an unusable Result
- **WHEN** Read reports missing, unavailable, inconsistent or untrusted Result, or readiness is blocked for a valid non-location reason
- **THEN** Plan returns the contract error without creating Working State

#### Scenario: No photos have location
- **WHEN** all Source Items lack location but other prerequisites hold
- **THEN** Plan may organize from images, time and user intent without mandatory additional Geo work
