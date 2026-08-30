## ADDED Requirements

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
