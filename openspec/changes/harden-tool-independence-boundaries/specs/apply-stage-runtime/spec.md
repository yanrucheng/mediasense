## ADDED Requirements

### Requirement: Preparation validates the complete Frozen Plan before effects
Apply prepare SHALL validate the complete Frozen Plan against the authoritative
`frozen-plan.schema.json`, reject every unsupported `encoding_profile`, verify the
sealed-content identity, and verify final-confirmation binding before creating a
Run or probing supplied source and destination paths. Recomputing a matching digest
SHALL NOT make a schema-invalid document acceptable.

#### Scenario: Schema-forbidden field has a matching digest
- **WHEN** a Frozen Plan contains an additional forbidden field and its content identity is recomputed
- **THEN** prepare returns an error before Run creation or filesystem probing

#### Scenario: Encoding profile is unknown
- **WHEN** the seal names an encoding profile Apply does not implement
- **THEN** prepare returns an error before interpreting or hashing the sealed content under that profile

### Requirement: Apply owns trustworthy Source Set expansion
Production Apply composition SHALL expand `explicit`, `accounts_for`,
`represents`, `union`, and `difference` Source Sets through a repository-owned
deterministic resolver bound to the Frozen Plan's exact `result_ref` and the public
`mediasense.precheck.read` `inspect` and `traverse` operations. It SHALL validate
expression shape, reference kinds, response bindings, pagination completeness,
duplicates, and set operations, and SHALL fail closed without reading PreCheck
private SQLite or accepting a caller's completeness assertion as proof.

#### Scenario: Traversal silently omits a member
- **WHEN** a Read adapter returns inconsistent totals, repeats a cursor, duplicates a target, crosses the bound Result, or ends before complete coverage
- **THEN** Apply rejects preparation rather than producing a smaller operation set

#### Scenario: Test supplies a fake resolver
- **WHEN** an internal unit test exercises ApplyRunStore with an injected resolver
- **THEN** that seam does not become a public ApplyRunTool input or production completeness authority

### Requirement: Plan seal output is a direct Apply prepare input
Forward Apply prepare SHALL accept the complete Frozen Plan object returned in a
successful `mediasense.plan.work` `seal` response. The caller SHALL NOT need a Plan
private path, artifact-directory convention, new Plan Read Tool, or invented
locator protocol.

#### Scenario: Caller hands off a sealed Plan
- **WHEN** Plan seal returns `frozen_plan`
- **THEN** the caller can place that exact object in Apply's `forward.frozen_plan` field together with Apply-owned root and destination bindings

### Requirement: Apply performs no geographic acquisition or interpretation
Apply SHALL neither invoke Geo providers nor interpret candidate place observations.
It SHALL execute only the filesystem decisions already fixed by the validated
Frozen Plan.

#### Scenario: Prepare a place-informed Plan
- **WHEN** a valid Frozen Plan was informed by PreCheck or Plan Geo evidence
- **THEN** Apply validates and expands the Plan without performing a Geo request or requiring Geo state

## MODIFIED Requirements

### Requirement: Receipt reads are bounded and immutable
The Apply Read boundary SHALL inspect one exact Receipt and traverse its operations,
exceptions, metadata discrepancies, or created directories in bounded pages
without changing history. Missing or corrupt Receipts, unsupported action or
section, invalid page or filter, invalid or query-mismatched cursor, and unavailable
or integrity-failed segmented ledgers SHALL return a contract-defined,
schema-valid error response rather than leaking `ReceiptError`, schema exceptions,
or storage details.

#### Scenario: Traverse a large receipt
- **WHEN** a caller requests one valid bounded page
- **THEN** the response stays within the limit and its cursor remains bound to that Receipt, section, filter, order, and page position

#### Scenario: Receipt is missing or corrupt
- **WHEN** the addressed Receipt cannot be loaded and verified
- **THEN** Apply Read returns a schema-valid error identifying unavailable or untrusted Receipt state

#### Scenario: Read query is invalid
- **WHEN** action, section, page, filter, or cursor is unsupported, malformed, or bound to another query
- **THEN** Apply Read returns a schema-valid error and no Receipt content page

#### Scenario: Segmented ledger cannot be verified
- **WHEN** a required operation index or segment is absent, malformed, incomplete, or fails identity verification
- **THEN** Apply Read returns a schema-valid integrity error rather than a partial page
