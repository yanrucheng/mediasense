# apply-skill-workflow Specification

## Purpose
Define how the Apply Skill guides a Human through direct Frozen Plan handoff,
preparation, exact authorization, observable execution, recovery, Receipt reading,
and whole-Run rewind without owning Tool state or effects.
## Requirements
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

### Requirement: Skill follows observable Run state
The Skill SHALL choose only actions allowed by the latest `status` and SHALL NOT
present accepted commands as completed effects.

#### Scenario: Execution is accepted
- **WHEN** `execute` returns `outcome: accepted`
- **THEN** the Skill reports authorization/request acceptance and continues
  observing status until a truthful terminal or attention state is available

### Requirement: Skill handles unsafe and partial outcomes
The Skill SHALL explain blockers, warnings, drift, localized failure,
indeterminate state, recovery conditions, and incomplete closure without
inventing source substitutions or organization changes.

#### Scenario: A selected source drifts
- **WHEN** execution stops with an effect-boundary source mismatch
- **THEN** the Skill does not retry blindly and routes semantic replacement to a
  new upstream Result and Plan

#### Scenario: Independent work partially completes
- **WHEN** one item fails while other authorized items complete
- **THEN** the Skill reports both realities and offers only Tool-allowed resume
  or cancel actions

### Requirement: Skill reads immutable outcomes and requests rewind safely
The Skill SHALL inspect or traverse the exact Receipt and SHALL treat whole-Run
rewind as a newly prepared, newly authorized Run within the recorded window.

#### Scenario: Human requests rewind
- **WHEN** the Receipt remains eligible and the original locations are safe
- **THEN** the Skill prepares a reverse Run, presents its exact prepared
  identity, and obtains fresh Human confirmation before execution

### Requirement: Apply requires the current Honeycomb Tool Host

The Apply Skill SHALL require a compatible MediaSense Tool Host already loaded in
the current Honeycomb session. It SHALL route a missing or incompatible Host to
the `mediasense` product entry Skill rather than duplicating installation
instructions, editing user-level configuration, or performing filesystem effects
directly.

#### Scenario: Apply Tool is unavailable

- **WHEN** `mediasense.apply.run` or `mediasense.apply.read` is not discoverable in the current session
- **THEN** the Agent stops before preparation, explains the local integration prerequisite, and routes setup through the `mediasense` Skill before a new session retries discovery
