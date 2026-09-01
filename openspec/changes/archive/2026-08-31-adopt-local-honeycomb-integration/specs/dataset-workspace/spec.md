## MODIFIED Requirements

### Requirement: Dataset state and machine state are separated

MediaSense SHALL keep Dataset-owned databases, Artifacts, Results, Plans, journals,
Receipts, and migration records in the selected Dataset workspace while keeping
the executable, Agent client configuration, Agent Skills, credentials, shared
models, and non-authoritative recent-location hints outside it. Dataset paths
SHALL NOT select, imply, or relocate a Honeycomb root.

#### Scenario: Workspace moves to another computer

- **WHEN** a user connects a portable Dataset to another compatible MediaSense installation
- **THEN** all Dataset-owned state needed to inspect and resume eligible work is available from the portable workspace without copying credentials, Skills, or Agent client settings

#### Scenario: Honeycomb and Dataset use unrelated paths

- **WHEN** the selected Honeycomb and Dataset workspace are in different directory trees or volumes
- **THEN** Skill discovery and MCP registration remain bound to the Honeycomb while Tool state remains bound to the exact Dataset workspace

#### Scenario: Diagnostics report configuration

- **WHEN** MediaSense reports the selected workspace and loaded configuration
- **THEN** it identifies every Dataset-configuration source and effective safety policy while redacting all secret values and making no claim about Agent-client configuration
