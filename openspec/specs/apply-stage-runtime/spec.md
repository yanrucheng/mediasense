# apply-stage-runtime Specification

## Purpose
Define deterministic preparation, authorization, filesystem effects, recovery,
verification, immutable Receipt publication, and bounded Receipt reading for one
exact Frozen Plan.
## Requirements
### Requirement: Execution binds exact Human authorization
The runtime SHALL start effects only when trusted Human context authorizes the exact Run, prepared revision, prepared content identity, and request identity.

#### Scenario: Prepared content changed
- **WHEN** execution coordinates differ from the current prepared Run
- **THEN** the runtime refuses execution before any media effect

### Requirement: Every effect is journaled and reverified
The runtime SHALL durably record per-item intent before mutation and SHALL reverify source evidence, source-root binding, and target absence at the individual effect boundary.

#### Scenario: Source changes after prepare
- **WHEN** source bytes or location change after preparation and before mutation
- **THEN** the item is refused without changing source or target and the Run reports an incomplete result

### Requirement: Move publication never overwrites
The runtime SHALL implement `move_originals` without overwriting an existing final target or silently changing a target name, route, or preservation guarantee.

#### Scenario: Target appears after authorization
- **WHEN** an unrelated final target exists at the effect boundary
- **THEN** the operation is refused and that target remains byte-for-byte unchanged

### Requirement: Recovery reconciles observed facts
After interruption, the runtime SHALL reconcile durable intent with authoritative source and target observations before retrying, and SHALL never repeat a verified completed effect.

#### Scenario: Crash follows filesystem move
- **WHEN** a same-filesystem move completes before its result is durably recorded
- **THEN** recovery recognizes the verified target and absent source as one completed effect

### Requirement: Receipt publication is immutable and complete
Every ordinary terminal Run after execution authorization SHALL publish one immutable Receipt that accounts for the entire Frozen Plan scope and verifies every claimed completed effect.

#### Scenario: Successful run closes
- **WHEN** every selected operation completes and verifies
- **THEN** one schema-valid Receipt is atomically published and the Run closes against that exact Receipt identity

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
Production Apply SHALL expand explicit, accounts_for, represents, union and difference Source Sets through the repository-owned deterministic resolver bound to the Frozen Plan's exact result_ref and Dataset, using the public PreCheck Read action=resolve contract. It SHALL preserve selection and membership digest checks, actual array counting, stable order, duplicate rejection, cursor binding/progress, final total membership and source verification requirements. It SHALL NOT read private PreCheck SQLite or accept caller completeness as proof. Removing redundant response fields SHALL NOT remove these checks.

#### Scenario: Traversal silently omits a member
- **WHEN** an adapter returns inconsistent totals, repeats a cursor, duplicates a member, crosses the bound Result or ends before all members are present
- **THEN** Apply rejects preparation rather than producing a smaller operation set

#### Scenario: Test supplies a fake resolver
- **WHEN** an internal test injects a resolver into the lower-level Apply store
- **THEN** that seam is not exposed as public authority or used to bypass production validation

#### Scenario: Compact final page
- **WHEN** resolve returns no returned/complete fields but has a null next_cursor
- **THEN** Apply counts the actual members and recomputes membership identity before accepting completeness

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

### Requirement: Controlled execution scope
Tests and evaluation SHALL execute file mutations only beneath isolated temporary fixtures or explicit opt-in probe roots and SHALL NOT target user media.

#### Scenario: End-to-end test executes a move
- **WHEN** the test authorizes `move_originals`
- **THEN** every source, target, Run store, and Receipt store is contained by the test fixture

### Requirement: Storage failures are classified before further effects
The runtime SHALL translate capacity, permission, read-only-volume,
disconnected/stale-volume, and I/O failures at a filesystem effect boundary into
explicit global-risk outcomes that stop issuance of later effects.

#### Scenario: Destination loses capacity or permission
- **WHEN** a file effect reports ENOSPC, EDQUOT, EACCES, EPERM, or EROFS
- **THEN** the current item is indeterminate, no later item effect starts, and
  status exposes the normalized recovery reason

#### Scenario: A bound volume disappears or is rebound
- **WHEN** source or destination identity no longer matches the prepared binding
- **THEN** execution stops before the next effect without accepting a path-only
  replacement

### Requirement: Operational evidence stays within controlled storage
Production-boundary tests SHALL use generated temporary media or separately
authorized probe volumes and SHALL publish the exact platform/filesystem scope
their evidence supports.

#### Scenario: Large-file throughput is measured
- **WHEN** the opt-in scale test reads and moves a generated large file
- **THEN** it verifies complete bytes and reports measured local throughput
  without claiming parity for untested user storage
