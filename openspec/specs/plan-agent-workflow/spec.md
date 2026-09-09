> Current public API authority: [`docs/spec/contract/`](../../../docs/spec/contract/index.md). This OpenSpec capability record does not override that contract; finalized contract and installed implementation are separate milestone states.

# plan-agent-workflow Specification

## Purpose
Define how the Plan Agent turns one exact PreCheck Result and any separately
authorized Plan-owned observations into a reviewable, Human-confirmed organization
decision without mutating source media or upstream evidence.
## Requirements
### Requirement: Agent preserves epistemic boundaries
The Plan Skill SHALL guide the Agent to keep PreCheck facts and observations, candidate relations, Agent judgments, organization preferences, and Human confirmations distinguishable throughout planning.

#### Scenario: Agent proposes a place-based group
- **WHEN** geographic evidence supports more than one plausible organization
- **THEN** the Agent presents the evidence and its proposed judgment without promoting either to confirmed Human intent

### Requirement: Agent uses progressive evidence
The Agent SHALL begin from Result readiness, entry evidence, representatives, boundaries, outliers, conflicts, and residual uncertainty, and SHALL expand existing Result-local evidence only when the additional reading can materially change the organization decision.

#### Scenario: Existing evidence is sufficient
- **WHEN** remaining uncertainty cannot materially change grouping, naming, disposition, or the need to reopen PreCheck
- **THEN** the Agent stops expanding evidence and advances the candidate to review

#### Scenario: Upstream evidence is insufficient
- **WHEN** a material organization decision requires evidence not contained in or reachable from the exact Result
- **THEN** the Agent exposes the gap and recommends reopening PreCheck rather than fabricating evidence or reading PreCheck internals

### Requirement: Preview drives meaningful revision checkpoints
The Agent SHALL use preview as the primary Human review surface. It SHALL create a new revision only when it submits a coherent changed candidate or preference snapshot, not for every conversational statement or view interaction.

#### Scenario: User rejects part of a preview
- **WHEN** the user requests material changes after reviewing a bound preview
- **THEN** the Agent consolidates the accepted changes into one complete update, obtains the new revision, and regenerates preview from that revision

#### Scenario: User only expands a directory
- **WHEN** the user drills into preview content without changing organization intent
- **THEN** no new Working State revision is created

### Requirement: Human confirmation applies to the exact reviewed candidate
The Agent SHALL request final confirmation only after a complete, seal-ready preview of the current candidate is available. It SHALL NOT construct or self-declare trusted Human authentication data.

#### Scenario: User confirms the current preview
- **WHEN** the Human confirms the exact current candidate through the trusted interaction boundary
- **THEN** the Agent may request `seal` for that revision and identity

### Requirement: Default policy remains subordinate to Human intent
The Agent SHALL apply the Default Organization Profile when no explicit preference overrides it, expose material departures for review, and write only resulting decisions into candidate content.

#### Scenario: User preference conflicts with the default profile
- **WHEN** an authorized explicit preference conflicts with a default grouping or naming policy
- **THEN** the Agent follows the preference within scope and makes the resulting candidate visible in preview

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

### Requirement: Migration acceptance remains explicit
The completed Plan capability SHALL compare relevant behavior with AI Album using `preserved`, `intentionally_changed`, `regression`, or `not_comparable` and SHALL include functional coverage, model cost, reuse, user effort, uncertainty visibility, and file safety.

#### Scenario: Plan behavior differs from AI Album
- **WHEN** an evaluated grouping, naming, evidence, or interaction behavior differs from the legacy output
- **THEN** the result records the applicable migration class and evidence rather than treating difference alone as regression

### Requirement: Plan requires the current Honeycomb Tool Host

The Plan Skill SHALL require a compatible MediaSense Tool Host already loaded in
the current Honeycomb session. It SHALL route a missing or incompatible Host to
the `mediasense` product entry Skill rather than duplicating installation
instructions, editing user-level configuration, or treating CLI presence as Tool
discovery.

#### Scenario: Plan Tool is unavailable

- **WHEN** `mediasense.plan.work` is not discoverable in the current session
- **THEN** the Agent stops Plan work, explains the local integration prerequisite, and routes setup through the `mediasense` Skill before a new session retries discovery
