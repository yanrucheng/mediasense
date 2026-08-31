# mediasense-distribution Specification

## Purpose
TBD - created by archiving change productize-mediasense-distribution. Update Purpose after archive.
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
- **THEN** it can load byte-identical release copies of the authoritative contracts and user Skills from the installed distribution

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
not silently download optional models, install system packages, edit Agent client
configuration, delete Dataset state, or remove user configuration.

#### Scenario: Optional dependency is absent

- **WHEN** ExifTool, FFmpeg/ffprobe, or a local model needed only by an optional capability is absent
- **THEN** installation remains valid and doctor reports exactly which capability is unavailable

#### Scenario: Executable is uninstalled

- **WHEN** the user removes the MediaSense tool installation
- **THEN** Dataset workspaces and user configuration remain intact and cleanup guidance lists them separately

### Requirement: Client integration follows client-owned MCP registration

MediaSense SHALL publish the stable stdio server command and instructions for
native client registration, and SHALL NOT present a MediaSense-owned `connect`
command as a cross-client standard.

#### Scenario: Codex is configured

- **WHEN** a user follows the Codex integration guide
- **THEN** the guide uses Codex's native MCP registration or `config.toml` mechanism and allows Codex to start the installed `mediasense` server command

#### Scenario: Another MCP client is considered

- **WHEN** an stdio MCP client has not completed MediaSense's product acceptance matrix
- **THEN** documentation distinguishes protocol compatibility from certified Skill-guided product support

