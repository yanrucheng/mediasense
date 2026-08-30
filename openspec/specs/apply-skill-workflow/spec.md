# apply-skill-workflow Specification

## Purpose
TBD - created by archiving change complete-apply-product-stage. Update Purpose after archive.
## Requirements
### Requirement: Skill preserves Apply authority boundaries
The `mediasense-apply` Skill SHALL guide Agent/Human interaction without owning
Run state, Human authorization, filesystem effects, or Receipt truth.

#### Scenario: Human authorizes prepared content
- **WHEN** a ready Run is presented for execution
- **THEN** the Skill explains the exact prepared identity and consequences while
  trusted host context, not Skill-authored request data, supplies confirmation

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
