## MODIFIED Requirements

### Requirement: External semantic work remains controlled
The Agent SHALL make provider locality, transmitted data classes, model usage,
cost, retention, and material uncertainty visible before optional remote semantic
work. It MAY request live geographic enrichment only through the accepted Geo Tool
for exact coordinates from the bound PreCheck Result and only under matching Human
or standing-policy authority. It SHALL NOT call provider APIs directly, transmit
media or unrelated metadata, mutate the PreCheck Result, or treat a provider
observation as a confirmed Plan judgment.

#### Scenario: Existing place evidence is sufficient
- **WHEN** the bound Result already contains place evidence sufficient for the current organization decision
- **THEN** the Agent uses that evidence and performs no live Geo request

#### Scenario: Plan lacks material place evidence
- **WHEN** the bound Result contains an exact coordinate but lacks place evidence that could materially change grouping, naming, disposition, or the decision to stop
- **THEN** the Agent may request bounded Geo enrichment, discloses the proposed effects, and proceeds only after matching authority is available

#### Scenario: Geo enrichment is refused
- **WHEN** the Human declines the proposed coordinate egress or no permitted provider is available
- **THEN** the Agent continues with available evidence, asks the Human for non-provider context, leaves the location unresolved, or recommends upstream work without fabricating a place
