> Current public API authority: [`docs/spec/contract/`](../../../docs/spec/contract/index.md). This OpenSpec capability record does not override that contract; finalized contract and installed implementation are separate milestone states.

# mediasense-distribution Specification

## Purpose
Define the installable CLI distribution, its Human-facing controls, and the safe,
explicit integration of release-matched Skills and the CLI-bundled MCP Host into a
user-selected local Honeycomb.
## Requirements
### Requirement: MediaSense is installable as one local executable

MediaSense SHALL build as a Python 3.11+ distribution with one authoritative
`mediasense` console entry point, an explicit build system, declared runtime
dependencies, and all resources required to run outside the source checkout.

#### Scenario: Clean wheel installation

- **WHEN** a wheel is built and installed into a new isolated environment
- **THEN** `mediasense --help` and `mediasense --version` succeed without the repository or its existing virtual environment on `sys.path`

#### Scenario: Required release resources are installed

- **WHEN** the installed runtime constructs its public Tools
- **THEN** it can load byte-identical release copies of the authoritative contracts, product entry Skill, and stage Skills from the installed distribution

### Requirement: Human controls expose orientation and truthful diagnosis

The executable SHALL expose help, version, Dataset open and inspect, doctor, Tool
discovery, diagnostic invocation, and stdio Host startup while preserving the same
target, effects, state, and outcome as the machine-facing surface.

#### Scenario: User diagnoses a new installation

- **WHEN** the user runs doctor before opening a Dataset
- **THEN** MediaSense distinguishes required failures, optional unavailable capabilities, uncertified platform behavior, and disabled external effects and gives actionable remediation without installing anything

#### Scenario: User invokes a Dataset-bound command

- **WHEN** a command resolves a Dataset workspace
- **THEN** its output identifies the source, Dataset, workspace, selection tier, loaded configuration sources, and effect policy without revealing secrets

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

### Requirement: One product entry owns setup and stage routing

MediaSense SHALL provide one separately loadable `mediasense` Skill as the
default new-user entry. It SHALL own installation guidance, readiness
verification, and routing to the independently loadable PreCheck, Plan, and Apply
Skills without duplicating their stage methods or claiming installation effects.

#### Scenario: User does not know which stage to install

- **WHEN** a new user selects the `mediasense` Skill without knowing the internal stage split
- **THEN** the Skill can guide installation of the complete release-matched set and route the ready request from the user's goal and exact retained references

#### Scenario: Returning user has downstream state

- **WHEN** the user supplies an exact Plan-ready Result, Frozen Plan, Apply Run, or Receipt
- **THEN** the entry Skill routes to the owning stage without restarting PreCheck or reconstructing state from private storage

### Requirement: Skills install only to an explicit target

The `mediasense skills install` command SHALL require an explicit target, write
only below that target, be idempotent for byte-identical content, and refuse to
overwrite a differing destination. It SHALL NOT derive the target from a Dataset
source or workspace.

#### Scenario: Explicit local Skill target is empty

- **WHEN** the user authorizes installation to `<honeycomb>/.agents/skills/`
- **THEN** the product entry Skill and three stage Skills are copied only below that exact directory

#### Scenario: Existing Skill differs

- **WHEN** a named destination already exists with different content
- **THEN** installation reports the exact conflict and leaves it unchanged
