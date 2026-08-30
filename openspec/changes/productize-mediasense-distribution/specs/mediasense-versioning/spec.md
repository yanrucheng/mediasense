## ADDED Requirements

### Requirement: Application version has one authoritative source

MediaSense SHALL declare the application version once in package metadata and
derive installed runtime, CLI, built artifact, and release-tag validation from
that value.

#### Scenario: Installed version is inspected

- **WHEN** a cleanly installed executable reports its version
- **THEN** it exactly matches the installed distribution metadata and built wheel metadata

### Requirement: Compatibility domains evolve independently

MediaSense SHALL distinguish application SemVer, public Tool contract identity,
Dataset manifest format, component store schema, Skill compatibility, and
producer computation identity.

#### Scenario: Patch release changes no computation semantics

- **WHEN** only the application patch version changes
- **THEN** previously valid PreCheck Work remains reusable unless one of its real semantic dependencies changed

#### Scenario: Tool contract changes incompatibly

- **WHEN** a public Tool input or output changes incompatibly during pre-1.0 development
- **THEN** its contract identity or declared revision changes and the Host exposes the supported combination without treating the application version alone as proof of compatibility

### Requirement: Persistent state is checked before mutation

MediaSense SHALL record Dataset manifest and component store versions and SHALL
classify each opened combination as supported, explicitly migratable, unsupported
newer, corrupt, or unversioned before ordinary state mutation.

#### Scenario: Supported current state is opened

- **WHEN** every Dataset and component version is supported by the installed release
- **THEN** MediaSense opens the workspace without rewriting it merely because the application version changed

#### Scenario: Newer state is encountered

- **WHEN** a workspace declares a format or store version newer than the installed runtime supports
- **THEN** MediaSense refuses to write, reports the incompatible component and versions, and recommends upgrading the executable

#### Scenario: Migration fails

- **WHEN** a future explicitly supported migration cannot complete
- **THEN** MediaSense reports the journaled failure and preserves a recoverable pre-migration copy rather than claiming the workspace is upgraded

### Requirement: Release and rollback claims are reproducible

MediaSense SHALL document SemVer `0.y.z` policy, prerelease identifiers, release
notes, supported contract/store combinations, upgrade steps, and rollback limits,
and SHALL verify artifacts before any publication.

#### Scenario: Pre-1.0 minor release is prepared

- **WHEN** a release introduces a breaking CLI, Host, manifest, or store change
- **THEN** it increments the minor version, records the break and migration behavior, and does not add an unneeded compatibility shim

#### Scenario: User rolls back the executable

- **WHEN** an older executable encounters state already migrated beyond its supported range
- **THEN** it refuses writes and directs the user to the preserved backup or a compatible executable instead of attempting an unsafe downgrade
