# tool-host Specification

## Purpose
Define one transport-independent local composition root and the lifecycle and
behavior of the CLI-bundled, session-scoped stdio MCP Tool Host.
## Requirements
### Requirement: One composition root constructs the local product

MediaSense SHALL have one Dataset-bound composition root that validates runtime
configuration and constructs packaged schemas, stores, providers, the Dataset
opener, and the six existing public Tools without requiring a client to assemble
stage dependencies.

#### Scenario: Offline composition succeeds

- **WHEN** a valid Dataset is opened with external providers disabled
- **THEN** the composition root constructs every existing Tool and reports their availability without a network request

#### Scenario: Two adapters invoke the product

- **WHEN** the CLI and MCP Host invoke the same Tool operation
- **THEN** both use the same composition root, business request validation, state, and result semantics

### Requirement: Tool business contracts remain transport-independent

The Host SHALL validate business inputs and outputs against the advertised contract and SHALL keep trusted principal, confirmation, cancellation and effect authorization outside caller-authored business fields. The two existing PreCheck Tools SHALL use flat inputs with `action`, exactly one `dataset_ref`, and action-specific fields. They SHALL reject `request` wrappers, `operation` aliases and caller-authored authority. Other Tool transports SHALL retain their existing contracts.

#### Scenario: Transport envelope contains confirmation
- **WHEN** Plan, Geo or Apply receives its contract-supported trusted transport authorization
- **THEN** the Host binds it as context without modifying the business request or weakening PreCheck elicitation

#### Scenario: Required authority is absent
- **WHEN** an external PreCheck resume has no matching trusted Human confirmation
- **THEN** no Provider effect occurs and the Run remains at the confirmation boundary

#### Scenario: Host request is invalid
- **WHEN** a request has a legacy wrapper, unknown action or Dataset mismatch
- **THEN** it is rejected before work and no fallback Dataset is selected

#### Scenario: Tool implementation fails unexpectedly
- **WHEN** a valid Tool call raises an unexpected exception
- **THEN** the Host returns sanitized `host_operation_failed` with diagnostic_id and marks MCP isError true, without inventing a business wait state

#### Scenario: Flat PreCheck status
- **WHEN** an opened Dataset receives `action=status` and a matching run_ref
- **THEN** the Host validates the same flat schema that it advertises and returns compact status without an extra wrapper

#### Scenario: Failed Run is successfully observed
- **WHEN** status reads a Run whose state is failed
- **THEN** its `state` and `reason` are ordinary successful data and MCP isError is false

#### Scenario: Dataset continuity across restart
- **WHEN** a new Host opens the original Dataset and receives its retained Run reference
- **THEN** it resolves the same Run without a global ref registry or implicit latest Dataset

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

### Requirement: Long-running Tool lifecycle remains observable and resumable

The Host SHALL distinguish accepted work from completion, retain durable operation
identity, reconcile interrupted work before retry, and stop background execution
cleanly when the stdio session ends.

#### Scenario: PreCheck start returns before completion

- **WHEN** `mediasense.precheck.run` accepts a long-running start request
- **THEN** the Host returns the durable `run_ref`, schedules only Tool-owned advancement, and leaves progress and controls available through the existing Run contract

#### Scenario: Host exits during work

- **WHEN** the stdio Host terminates while a durable Run is incomplete
- **THEN** a later Host can reopen the same Dataset state and reconcile or resume through the existing Tool lifecycle rather than starting untracked duplicate work

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


### Requirement: PreCheck public operations retain their two Tool identities
The Host SHALL expose five actions on mediasense.precheck.run and four actions on mediasense.precheck.read using the packet contracts, SHALL NOT create nine new Tools, and SHALL synchronize real callers, packed schemas and Skill examples when changing the interface.

#### Scenario: Discovery agrees with invocation
- **WHEN** a fresh stdio client lists and invokes each PreCheck action
- **THEN** advertised input/output schemas accept the same operation shapes that the runtime executes
