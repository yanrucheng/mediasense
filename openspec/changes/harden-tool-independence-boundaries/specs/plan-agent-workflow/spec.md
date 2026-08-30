## MODIFIED Requirements

### Requirement: External semantic work remains controlled
The Agent SHALL make provider locality, transmitted data classes, model usage,
cost, retention, and material uncertainty visible before optional remote semantic
work. It MAY request additional live geographic observations only through the
accepted stage-neutral Geo capability for exact coordinates from the bound
PreCheck Result and only under matching Human or standing-policy authority. Plan
SHALL own the lookup purpose, selected scope, authorization binding, retained
observation, and evidence lifecycle. It SHALL NOT call provider APIs directly,
transmit media or unrelated metadata, mutate the PreCheck Result, reuse PreCheck
Run authorization, or treat a provider observation as a confirmed Plan judgment.

#### Scenario: Existing place evidence is sufficient
- **WHEN** the bound Result already contains place evidence sufficient for the current organization decision
- **THEN** the Agent uses that evidence and performs no live Geo request

#### Scenario: Plan lacks material place evidence
- **WHEN** the bound Result contains an exact coordinate but lacks place evidence that could materially change grouping, naming, disposition, or the decision to stop
- **THEN** the Agent may request bounded Geo enrichment, discloses the proposed effects, and proceeds only after matching Plan-scoped authority is available

#### Scenario: Human declines Geo enrichment
- **WHEN** the Human declines the proposed coordinate egress
- **THEN** Plan records the refusal if useful, does not invoke Geo to manufacture a `refused` result, and continues with available evidence, Human context, an unresolved location, or an upstream recommendation

#### Scenario: No permitted provider is available
- **WHEN** the authorized constraints admit no configured provider
- **THEN** Plan treats the Geo capability as unavailable without fabricating a Human refusal or place observation
