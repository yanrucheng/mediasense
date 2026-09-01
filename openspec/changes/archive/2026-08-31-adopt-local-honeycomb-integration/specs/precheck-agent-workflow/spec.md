## ADDED Requirements

### Requirement: PreCheck guides local Honeycomb bootstrap before Dataset work

The PreCheck Skill SHALL, after the Agent client's standard mechanism loads it
locally, diagnose the compatible CLI, explicit Honeycomb Skill target,
project-scoped MCP configuration, Codex trust requirement, session reload, and
seven-Tool discovery before attempting Dataset Open. Inspection SHALL be
read-only; every CLI installation or Honeycomb mutation SHALL disclose its exact
target and network implications and require Human authorization.

#### Scenario: Compatible CLI is absent

- **WHEN** `mediasense` is missing from PATH or its version is incompatible with the loaded Skill
- **THEN** the Agent explains the trusted installation source, executable destination, and possible network access and waits for Human authorization before installing or replacing it

#### Scenario: Project MCP registration is absent

- **WHEN** an exact Honeycomb is confirmed and its parseable `.codex/config.toml` has no `mcp_servers.mediasense` table
- **THEN** the Agent reports the absolute target and, after authorization, safely creates or merges the exact `command = "mediasense"` and `args = ["mcp"]` registration while preserving all unrelated TOML content

#### Scenario: Project MCP registration conflicts

- **WHEN** `mcp_servers.mediasense` exists with different content or the file is invalid or not writable
- **THEN** the Agent reports the conflict or failure and does not overwrite, fall back to user-level configuration, or claim successful setup

#### Scenario: Configuration was written in the current session

- **WHEN** local MCP configuration has been added or changed
- **THEN** the Agent explains that a new session from the trusted Honeycomb is normally required and does not claim activation from file presence alone

#### Scenario: New session verifies integration

- **WHEN** a fresh Agent session begins from the trusted configured Honeycomb
- **THEN** the Agent verifies discovery of all seven exact MediaSense Tool names before calling `mediasense.dataset.open`
