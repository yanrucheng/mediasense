## ADDED Requirements

### Requirement: Dataset state declares the independent Geo effect journal
Dataset manifests and workspaces SHALL declare a versioned `geo` store for the
stage-neutral Geo Tool's effect-idempotency journal. The journal SHALL NOT become
the authority for PreCheck per-Source-Item outcomes or Plan decisions.

#### Scenario: New Dataset is created
- **WHEN** `mediasense.dataset.open` creates a new workspace
- **THEN** its version 3 manifest and directories contain a `geo` store at version 1

#### Scenario: Supported version 2 manifest is migrated
- **WHEN** Dataset open encounters the exact supported version 2 manifest without a Geo declaration
- **THEN** it atomically advances the manifest to version 3 and adds `geo: 1` without rewriting existing private stores or immutable Results

#### Scenario: Historical version 1 Geo journal exists
- **WHEN** a supported version 1 workspace already contains a valid Geo journal
- **THEN** migration preserves and verifies that journal rather than discarding its idempotency evidence
