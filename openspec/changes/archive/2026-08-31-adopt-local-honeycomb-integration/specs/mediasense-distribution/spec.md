## MODIFIED Requirements

### Requirement: Installation and removal do not claim hidden effects

MediaSense SHALL document one repeatable `uv tool` installation route and SHALL
not silently download optional models, install system packages, edit user-level or
project-level Agent client configuration, install Agent Skills, delete Dataset
state, or remove user configuration.

#### Scenario: Optional dependency is absent

- **WHEN** ExifTool, FFmpeg/ffprobe, or a local model needed only by an optional capability is absent
- **THEN** installation remains valid and doctor reports exactly which capability is unavailable

#### Scenario: Executable installation completes

- **WHEN** the global `mediasense` CLI is installed
- **THEN** no `~/.codex/config.toml`, `~/.codex/skills`, `~/.agents/skills`, or Honeycomb-local Agent configuration is created or changed by that installation

#### Scenario: Executable is uninstalled

- **WHEN** the user removes the MediaSense tool installation
- **THEN** Dataset workspaces and user configuration remain intact and cleanup guidance lists them separately

### Requirement: Client integration follows client-owned MCP registration

MediaSense SHALL publish the stable stdio server command and guide each Agent
client to bind it only in an explicitly selected local Honeycomb by default. It
SHALL NOT present user-level registration, a MediaSense-owned `connect` command,
or a dedicated Agent launcher as the default or cross-client standard.

#### Scenario: Codex Honeycomb is configured

- **WHEN** a user follows the certified Codex integration guide
- **THEN** the guide targets `<honeycomb>/.agents/skills/` and `<honeycomb>/.codex/config.toml`, shows the resolved absolute paths before mutation, and configures `mediasense mcp` without changing user-level Codex configuration

#### Scenario: Honeycomb root is unclear

- **WHEN** no Honeycomb root has been explicitly supplied and the current directory is only a candidate
- **THEN** the Agent asks the Human to confirm the resolved root before writing either Skills or project configuration

#### Scenario: Another MCP client is considered

- **WHEN** an stdio MCP client has not completed MediaSense's product acceptance matrix
- **THEN** documentation distinguishes protocol compatibility from certified Skill-guided product support

## ADDED Requirements

### Requirement: Skills install only to an explicit target

The `mediasense skills install` command SHALL require an explicit target, write
only below that target, be idempotent for byte-identical content, and refuse to
overwrite a differing destination. It SHALL NOT derive the target from a Dataset
source or workspace.

#### Scenario: Explicit local Skill target is empty

- **WHEN** the user authorizes installation to `<honeycomb>/.agents/skills/`
- **THEN** the three packaged Skills are copied only below that exact directory

#### Scenario: Existing Skill differs

- **WHEN** a named destination already exists with different content
- **THEN** installation reports the exact conflict and leaves it unchanged
