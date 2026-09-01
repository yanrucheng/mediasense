## ADDED Requirements

### Requirement: Apply requires the current Honeycomb Tool Host

The Apply Skill SHALL require a compatible MediaSense Tool Host already loaded in
the current Honeycomb session. It SHALL route a missing or incompatible Host to
the PreCheck bootstrap guidance rather than duplicating installation instructions,
editing user-level configuration, or performing filesystem effects directly.

#### Scenario: Apply Tool is unavailable

- **WHEN** `mediasense.apply.run` or `mediasense.apply.read` is not discoverable in the current session
- **THEN** the Agent stops before preparation, explains the local integration prerequisite, and routes setup through the PreCheck Skill before a new session retries discovery
