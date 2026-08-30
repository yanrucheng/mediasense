## ADDED Requirements

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

The Host SHALL validate each business request and response against its
authoritative Tool contract and SHALL keep transport-only principal,
confirmation, cancellation, and effect-authorization context outside that
business request.

#### Scenario: Transport envelope contains confirmation

- **WHEN** a Plan, Geo, or Apply call supplies transport authorization
- **THEN** the Host binds it to the underlying Tool's accepted context without adding the transport fields to the business request

#### Scenario: Required authority is absent

- **WHEN** an operation requires confirmation or external-effect authority and the Host has no matching trusted context
- **THEN** the call fails before the effect with a structured actionable outcome

### Requirement: The local MCP Host is a conforming stdio subprocess

MediaSense SHALL provide an on-demand stdio MCP server that completes protocol
initialization, lists the Dataset-open boundary and all six existing Tools, invokes
them with bounded structured results, and keeps logs off protocol stdout.

#### Scenario: Client initializes a fresh subprocess

- **WHEN** an MCP client launches the installed server and sends initialize followed by tools/list
- **THEN** the server completes the handshake and returns stable Tool names, descriptions, and input schemas without repository-only paths

#### Scenario: Client invokes a non-destructive operation

- **WHEN** an initialized client calls Dataset open, Tool discovery, PreCheck status, or another no-effect path with valid input
- **THEN** the Host returns a structured result matching the advertised semantics and performs no network or media mutation

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
