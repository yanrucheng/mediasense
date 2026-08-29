# precheck-source-verification Specification

## Purpose
TBD - created by archiving change add-precheck-source-verification. Update Purpose after archive.
## Requirements
### Requirement: Each Source Item identifies its source-root binding without embedding a path
Every sealed Source Item locator SHALL expose one opaque `source_root_ref` and
a path relative to that root. A Result MAY contain Source Items associated with
different source-root references; the Dataset identity and `source_root_ref`
MUST NOT be an absolute path.

#### Scenario: Read a Source Item selected by Plan
- **WHEN** a consumer inspects the Result and a Result-local Source Item
- **THEN** the Source Item locator supplies its opaque source-root reference and root-relative path so an authorized runtime can bind that specific source

### Requirement: Verification is a replaceable Source Item observation
PreCheck SHALL allow an eligible Source Item to carry a
`source_content_verification` observation.
An available observation SHALL contain a named verification profile, verification
value, byte length, observation time, producer identity, limitations where
applicable, and basis linking it to that Source Item. The profile and value MUST
NOT become Source Item identity.

#### Scenario: First supported profile
- **WHEN** PreCheck reads all bytes of an eligible regular source file with stable pre/post file observations
- **THEN** it may publish profile `sha256-full-v1`, a `sha256:` value, exact byte length, observation time, and producer provenance

#### Scenario: Source Item is not Apply-eligible
- **WHEN** a Source Item is excluded, unsupported, invalid, erroneous, unresolved, or otherwise not selected for exact proof
- **THEN** accounting still includes it and the Result is not required to fabricate an available verification observation

### Requirement: Seal revalidates projected source verification
Before publishing a Result, PreCheck SHALL re-read and verify every available
source verification observation included in that Result against the same bound
Working Run. A changed, missing, or mismatched source MUST prevent publication.

#### Scenario: Source changes after observation
- **WHEN** source bytes no longer match the observation at the seal gate
- **THEN** no Result containing that observation is published

### Requirement: Plan preserves references and Apply verifies selected effects
Plan SHALL freeze the exact `result_ref` and selected `source_item_ref` values
without copying verification values into Frozen Plan. Before each authorized
file operation, Apply SHALL resolve those references through
`mediasense.precheck.read`, safely bind each selected locator's declared
`source_root_ref`, and
re-read the selected source bytes using the declared profile.

#### Scenario: Selected source matches
- **WHEN** Apply supports the profile, safely binds the source root, and the current byte length and verification value match
- **THEN** source verification permits the already-authorized operation to proceed to its other safety gates

#### Scenario: Verification cannot be established
- **WHEN** the profile is unknown, the observation is absent, the root cannot be safely bound, or current bytes differ
- **THEN** Apply blocks that operation without inventing a replacement source or changing plan semantics

### Requirement: Verification adds no parallel source authority
The implementation MUST reuse Result, Source Item, observation, and runtime
source binding. It MUST NOT introduce a Dataset-wide Source Snapshot, permanent
Source Item identity, or independent Source Verify service.

#### Scenario: Verification implementation changes
- **WHEN** a later profile replaces SHA-256 for an eligible producer or platform
- **THEN** the Result identifies the new profile while Dataset and Source Item semantics remain unchanged
