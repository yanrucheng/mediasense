## MODIFIED Requirements

### Requirement: One composition root constructs the local product
MediaSense SHALL have one Dataset-bound composition root that validates runtime
configuration and constructs packaged schemas, stores, configured providers, the
Dataset opener, and the six Dataset-bound public Tools without requiring a
client to assemble stage dependencies. The root SHALL construct one shared
`mediasense.geo.query` instance for direct callers and PreCheck execution.

#### Scenario: Composition has no configured map provider
- **WHEN** a valid Dataset is opened without a configured map-provider credential
- **THEN** the composition root constructs all seven total public Tools without network access and Geo reports unavailability only when a request requires a Provider

#### Scenario: Composition has a configured map provider
- **WHEN** a valid Dataset is opened with one or more configured map-provider credentials
- **THEN** provider availability is reported as a fact but no provider request occurs until exact Geo or PreCheck-mediated authority is accepted

#### Scenario: Two adapters invoke the product
- **WHEN** the CLI and MCP Host invoke the same Tool operation
- **THEN** both use the same composition root, business request validation, state, and result semantics

### Requirement: Tool business contracts remain transport-independent
The Host SHALL validate each business request and response against its
authoritative Tool contract and SHALL keep transport-only principal,
confirmation, cancellation, and effect-authorization context outside that
business request.

#### Scenario: Transport envelope contains confirmation
- **WHEN** a Plan seal or Apply call supplies transport authorization
- **THEN** the Host binds it to the underlying Tool's accepted context without adding transport fields to the business request

#### Scenario: MCP requests PreCheck external-effect authorization
- **WHEN** a stdio MCP caller requests `proceed` for a paused PreCheck external-effect disclosure
- **THEN** the MCP Host obtains the Human decision through session elicitation, constructs matching confirmation context only after acceptance, and never treats caller-authored authority JSON as trusted

#### Scenario: MCP client cannot elicit authorization
- **WHEN** the connected MCP client declines, cancels, or cannot support the elicitation
- **THEN** the Run is respectively terminated by explicit decline or remains paused with zero Provider requests, and no caller-authored fallback authority is accepted

#### Scenario: PreCheck authorization is absent
- **WHEN** PreCheck `proceed` lacks trusted confirmation for the pending frozen-batch disclosure
- **THEN** the Host leaves the Run paused and the shared Geo Tool sends no Provider request

#### Scenario: MCP requests direct Geo authorization
- **WHEN** a caller invokes `mediasense.geo.query` without caller-authored authority
- **THEN** the Host performs zero-effect preflight, elicits trusted Human approval for the exact request envelope, and invokes the Tool only after acceptance

#### Scenario: Required authority is absent
- **WHEN** another operation requires confirmation or external-effect authority and the Host has no matching trusted context
- **THEN** the call fails before the effect with a structured actionable outcome

#### Scenario: Host request is invalid
- **WHEN** the transport envelope or business request cannot be bound to the advertised Tool contract
- **THEN** the Host returns `host_invalid_request` without invoking a larger effect

#### Scenario: Tool implementation fails unexpectedly
- **WHEN** a validly bound Tool call raises an unexpected implementation or composition exception
- **THEN** the Host returns a sanitized `host_operation_failed` result with a diagnostic identifier and does not describe the caller's request as invalid
