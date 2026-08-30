## MODIFIED Requirements

### Requirement: Skill preserves Apply authority boundaries
The `mediasense-apply` Skill SHALL guide Agent/Human interaction without owning
Run state, Human authorization, filesystem effects, Receipt truth, Geo acquisition,
or private Plan artifact paths. It SHALL pass the complete `frozen_plan` object
returned by Plan seal directly into Apply prepare with Apply-owned current-root and
destination bindings, and SHALL treat structured Tool errors as outcomes rather
than internal exceptions to interpret.

#### Scenario: Plan has just sealed
- **WHEN** `mediasense.plan.work` returns a successful seal response
- **THEN** the Skill uses its exact `frozen_plan` object for forward preparation without discovering or constructing a Plan storage path

#### Scenario: Human authorizes prepared content
- **WHEN** a ready Run is presented for execution
- **THEN** the Skill explains the exact prepared identity and consequences while
  trusted host context, not Skill-authored request data, supplies confirmation

#### Scenario: Apply Read returns an error
- **WHEN** Receipt inspection or traversal returns a structured error envelope
- **THEN** the Skill reports the error and recovery boundary without relying on a leaked implementation exception
