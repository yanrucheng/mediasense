## MODIFIED Requirements

### Requirement: The local MCP Host is a conforming stdio subprocess

The installed `mediasense` CLI distribution SHALL include `mediasense mcp` as an
on-demand stdio MCP server that completes protocol initialization, lists the
Dataset-open boundary and all six existing Tools, invokes them with bounded
structured results, keeps logs off protocol stdout, and exits when its client
stdio session ends. Installation SHALL NOT create a daemon, listener, service, or
background process.

#### Scenario: Client initializes a fresh subprocess

- **WHEN** an MCP client launches `mediasense mcp` and sends initialize followed by tools/list
- **THEN** the server completes the handshake and returns stable Tool names, descriptions, and input schemas without repository-only paths

#### Scenario: Client invokes a non-destructive operation

- **WHEN** an initialized client calls Dataset open, Tool discovery, PreCheck status, or another no-effect path with valid input
- **THEN** the Host returns a structured result matching the advertised semantics and performs no network or media mutation

#### Scenario: Client session closes

- **WHEN** the MCP client's stdio connection closes
- **THEN** the child `mediasense mcp` process exits without leaving a persistent MediaSense service

## ADDED Requirements

### Requirement: MCP registration is local transport configuration

An MCP registration SHALL only tell the current Agent client how to launch the
CLI-bundled Tool Host. It SHALL NOT own Tool business semantics, Dataset state,
authorization, or durable Run continuity.

#### Scenario: Codex reads a trusted project configuration

- **WHEN** a fresh Codex process starts in a trusted Honeycomb whose `.codex/config.toml` contains the exact MediaSense server table
- **THEN** it can discover the MediaSense MCP registration and launch the same seven-Tool Host

#### Scenario: Codex starts outside the configured Honeycomb

- **WHEN** a fresh Codex process starts in a directory with no applicable MediaSense project configuration and no user-level MediaSense registration
- **THEN** MediaSense is absent from that client's configured MCP servers
