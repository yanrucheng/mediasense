## ADDED Requirements

### Requirement: MediaSense 0.4 has one declared compatibility combination
MediaSense `0.4.x` SHALL support Dataset manifest 1, PreCheck store 17, Plan
store 2, Geo journal 1, Apply store 2, release-matched `0.4.x` Skills, and the
installed exact public Tool contract digests.

#### Scenario: 0.4.0 release is inspected
- **WHEN** a cleanly installed `0.4.0` executable reports its version, Dataset store versions, Tool descriptors, and packaged Skills
- **THEN** every reported surface matches the one declared `0.4.x` compatibility combination

### Requirement: PreCheck schema 16 has a clean-start boundary
MediaSense `0.4.x` SHALL refuse to mutate a Dataset workspace whose manifest or
PreCheck database declares schema 16 and SHALL direct the user to retain it for
`0.3.x` rollback or create a distinct schema-17 workspace.

#### Scenario: 0.4 opens a 0.3 workspace
- **WHEN** `0.4.x` resolves an otherwise valid Dataset workspace with PreCheck store 16
- **THEN** it reports `store_unsupported`, performs no migration or ordinary write, and identifies the incompatible component and versions

#### Scenario: User rolls back to 0.3
- **WHEN** the user reinstalls the exact `0.3.x` executable after testing `0.4.x`
- **THEN** the user selects the preserved schema-16 workspace rather than attempting to downgrade the schema-17 workspace

