# apply-stage-runtime Specification

## Purpose
TBD - created by archiving change implement-apply-stage. Update Purpose after archive.
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
The Apply Read boundary SHALL inspect one exact Receipt and traverse its operations, exceptions, metadata discrepancies, or created directories in bounded pages without changing history.

#### Scenario: Traverse a large receipt
- **WHEN** a caller requests one bounded page
- **THEN** the response stays within the limit and its cursor remains bound to that Receipt, section, filter, order, and page position

### Requirement: Controlled execution scope
Tests and evaluation SHALL execute file mutations only beneath isolated temporary fixtures or explicit opt-in probe roots and SHALL NOT target user media.

#### Scenario: End-to-end test executes a move
- **WHEN** the test authorizes `move_originals`
- **THEN** every source, target, Run store, and Receipt store is contained by the test fixture
