## MODIFIED Requirements

### Requirement: External semantic work remains controlled
Plan SHALL prefer qualified place Evidence already in the immutable Result and
SHALL NOT use a live lookup to repair missing PreCheck coverage. When a complete
Result contains a materially questionable or over-broad place assignment, the
Agent MAY call the stage-neutral `mediasense.geo.query` Tool for a bounded set of
selected coordinates under its own exact authorization. Human context, Tool
observations, PreCheck Evidence, and Agent judgment SHALL remain distinguishable.

#### Scenario: Existing place evidence is sufficient
- **WHEN** the bound Result contains place Evidence sufficient for the current organization decision
- **THEN** the Agent uses that Evidence and performs no live Geo request

#### Scenario: Plan lacks material place evidence
- **WHEN** the bound Result is Plan-ready but a bounded location ambiguity could materially change grouping or naming
- **THEN** the Agent may issue a separately authorized Geo Tool request for only the selected coordinates and records the resulting judgment without mutating the Result

#### Scenario: PreCheck coverage is incomplete
- **WHEN** a located Source Item lacks its PreCheck Result outcome
- **THEN** the Agent requires a successor PreCheck and does not use direct Geo lookup to conceal the missing upstream fact

#### Scenario: Human supplies or confirms a place meaning
- **WHEN** the Human supplies or confirms semantic place context for the Plan
- **THEN** the Agent records it as Human input or confirmation and never as provider or PreCheck observation

#### Scenario: PreCheck reports the Result as blocked
- **WHEN** the effective Result view reports `readiness: blocked`
- **THEN** the Agent does not create Plan Working State and directs the workflow back to PreCheck without inspecting acquisition internals
