# dataset-workspace Specification

## Purpose
TBD - created by archiving change productize-mediasense-distribution. Update Purpose after archive.
## Requirements
### Requirement: Dataset opening resolves one exact portable identity

MediaSense SHALL provide one stage-neutral Dataset-open boundary that accepts a
source root and optional explicit workspace, resolves or creates one durable
Dataset identity, and returns the exact `dataset_ref`, canonical source root,
workspace path, creation status, selection tier, and configuration provenance.

#### Scenario: New removable source is opened directly

- **WHEN** a user opens a source on an eligible removable volume and no matching Dataset exists in any supported location
- **THEN** MediaSense creates one Dataset under the volume's `.mediasense/datasets/` root and returns its exact identity without requiring a prior init command

#### Scenario: Existing Dataset is reopened

- **WHEN** the same source is opened again and its matching Dataset manifest is valid
- **THEN** MediaSense returns the existing identity and workspace without creating duplicate state

### Requirement: Workspace lookup uses the confirmed precedence

MediaSense SHALL search an explicit workspace first, then the supplied source's
non-system volume root, then the platform-local Dataset root, and SHALL distinguish
absence from invalid, incompatible, or ambiguous state.

#### Scenario: Explicit workspace is valid

- **WHEN** the caller supplies a valid explicit workspace matching the source
- **THEN** MediaSense uses it and reports the explicit selection tier without consulting lower-priority state

#### Scenario: Portable workspace is absent but local state exists

- **WHEN** no portable match exists and one valid matching local Dataset exists
- **THEN** MediaSense opens the local Dataset and reports the local fallback tier

#### Scenario: Higher-priority state is invalid

- **WHEN** the selected explicit path or a matching portable Dataset is corrupt, incompatible, or ambiguous
- **THEN** MediaSense stops with a recoverable diagnostic and does not silently open or create lower-priority state

### Requirement: Automatic placement preserves the source boundary

MediaSense SHALL create new state on an eligible removable source volume and
otherwise in the platform-local Dataset root, but SHALL NOT place a workspace
inside the declared source root or write source media.

#### Scenario: Removable volume is eligible

- **WHEN** the external Dataset root is writable and satisfies required SQLite locking and atomic-replacement capabilities without nesting inside the source root
- **THEN** MediaSense selects the external Dataset root for new state

#### Scenario: External placement is unsafe

- **WHEN** external placement is unavailable, nested inside the declared source boundary, or lacks a required filesystem capability
- **THEN** MediaSense reports the failed portable condition and uses local placement only when no conflicting portable state exists

### Requirement: Portable continuity is verified independently of mount path

Dataset identity SHALL remain independent of an absolute mount path or
session-local device number, and MediaSense SHALL verify source continuity before
reusing work after relocation.

#### Scenario: Same Dataset is mounted under another path

- **WHEN** a portable workspace and its source are reopened under a different mount path and platform-neutral evidence verifies continuity
- **THEN** MediaSense preserves the Dataset identity and eligible reuse domain and audits the new locator

#### Scenario: Continuity cannot be verified

- **WHEN** the selected workspace cannot establish that the current source is the previously attached source
- **THEN** MediaSense requires explicit rebinding and prevents unverified reuse

### Requirement: Dataset state and machine state are separated

MediaSense SHALL keep Dataset-owned databases, Artifacts, Results, Plans, journals,
Receipts, and migration records in the selected Dataset workspace while keeping
the executable, client configuration, credentials, shared models, and
non-authoritative recent-location hints machine-owned.

#### Scenario: Workspace moves to another computer

- **WHEN** a user connects a portable Dataset to another compatible MediaSense installation
- **THEN** all Dataset-owned state needed to inspect and resume eligible work is available from the portable workspace without copying credentials or client settings

#### Scenario: Diagnostics report configuration

- **WHEN** MediaSense reports the selected workspace and loaded configuration
- **THEN** it identifies every source and effective safety policy while redacting all secret values

