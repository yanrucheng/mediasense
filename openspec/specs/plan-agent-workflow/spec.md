# plan-agent-workflow Specification

## Purpose
TBD - created by archiving change implement-plan-stage. Update Purpose after archive.
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
The Agent SHALL make provider locality, media or metadata egress, model usage, cost, and material uncertainty visible before optional remote semantic work. Reverse geocoding and reusable geographic enrichment SHALL remain outside the Plan implementation and SHALL be consumed only when present in the bound PreCheck Result.

#### Scenario: Plan lacks resolved place evidence
- **WHEN** the bound Result contains coordinates but no reusable resolved-place evidence
- **THEN** the Agent may reason from available evidence or recommend upstream enrichment, but does not perform live reverse geocoding inside Plan

### Requirement: Migration acceptance remains explicit
The completed Plan capability SHALL compare relevant behavior with AI Album using `preserved`, `intentionally_changed`, `regression`, or `not_comparable` and SHALL include functional coverage, model cost, reuse, user effort, uncertainty visibility, and file safety.

#### Scenario: Plan behavior differs from AI Album
- **WHEN** an evaluated grouping, naming, evidence, or interaction behavior differs from the legacy output
- **THEN** the result records the applicable migration class and evidence rather than treating difference alone as regression

