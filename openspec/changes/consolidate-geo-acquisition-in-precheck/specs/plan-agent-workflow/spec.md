## MODIFIED Requirements

### Requirement: External semantic work remains controlled
Plan SHALL prefer qualified place Evidence already in the immutable Result and
SHALL perform no map-provider acquisition. When machine place evidence remains
insufficient, the Agent SHALL either ask the Human for a semantic judgment or
stop and require a successor PreCheck. Human context SHALL remain distinguishable
from provider observation and PreCheck Evidence.

#### Scenario: Existing place evidence is sufficient
- **WHEN** the bound Result contains place Evidence sufficient for the current organization decision
- **THEN** the Agent uses that Evidence and performs no live Geo request

#### Scenario: Plan lacks material place evidence
- **WHEN** the bound Result lacks place Evidence that could materially change grouping, naming, disposition, or the decision to stop
- **THEN** the Agent asks only a Human-owned semantic question or requires a successor PreCheck and does not call a provider

#### Scenario: Human supplies or confirms a place meaning
- **WHEN** the Human supplies or confirms semantic place context for the Plan
- **THEN** the Agent records it as Human input or confirmation and never as provider or PreCheck observation

#### Scenario: Result acquisition is incomplete
- **WHEN** `geo_summary` reports `incomplete`
- **THEN** Plan does not create Working State and directs the workflow back to PreCheck

