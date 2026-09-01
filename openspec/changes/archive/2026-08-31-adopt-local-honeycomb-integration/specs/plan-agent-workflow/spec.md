## ADDED Requirements

### Requirement: Plan requires the current Honeycomb Tool Host

The Plan Skill SHALL require a compatible MediaSense Tool Host already loaded in
the current Honeycomb session. It SHALL route a missing or incompatible Host to
the PreCheck bootstrap guidance rather than duplicating installation instructions,
editing user-level configuration, or treating CLI presence as Tool discovery.

#### Scenario: Plan Tool is unavailable

- **WHEN** `mediasense.plan.work` is not discoverable in the current session
- **THEN** the Agent stops Plan work, explains the local integration prerequisite, and routes setup through the PreCheck Skill before a new session retries discovery
