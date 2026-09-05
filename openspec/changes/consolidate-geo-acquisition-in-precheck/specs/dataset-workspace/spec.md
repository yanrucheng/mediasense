## ADDED Requirements

### Requirement: Dataset state contains no independent Geo store
New Dataset manifests and workspaces SHALL contain PreCheck, Plan, Apply, and
immutable handoff state only. They SHALL NOT declare or create a Geo journal or
Geo store because provider acquisition is part of PreCheck.

#### Scenario: New Dataset is created
- **WHEN** `mediasense.dataset.open` creates a new workspace
- **THEN** its manifest and directories contain no Geo store entry

#### Scenario: Supported predecessor manifest is migrated
- **WHEN** a 0.7.1 Dataset manifest has the exact supported predecessor shape including a Geo store declaration
- **THEN** Dataset open atomically replaces it with the clean current manifest without reading or rewriting private databases or immutable Results

#### Scenario: Historical Geo bytes exist
- **WHEN** an upgraded workspace still physically contains old Geo journal bytes
- **THEN** no runtime component reads, writes, discovers, or treats them as current Dataset state

