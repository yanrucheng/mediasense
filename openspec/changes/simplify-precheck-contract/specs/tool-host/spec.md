## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: PreCheck public operations retain their two Tool identities
The Host SHALL expose five actions on mediasense.precheck.run and four actions on mediasense.precheck.read using the packet contracts, SHALL NOT create nine new Tools, and SHALL synchronize real callers, packed schemas and Skill examples when changing the interface.

#### Scenario: Discovery agrees with invocation
- **WHEN** a fresh stdio client lists and invokes each PreCheck action
- **THEN** advertised input/output schemas accept the same operation shapes that the runtime executes
