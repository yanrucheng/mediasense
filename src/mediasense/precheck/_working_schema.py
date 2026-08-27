"""Private SQLite schema for mutable PreCheck working state."""

SCHEMA_VERSION = 7

SCHEMA = """
CREATE TABLE IF NOT EXISTS internal_schema (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    version INTEGER NOT NULL
);
INSERT OR IGNORE INTO internal_schema (singleton, version) VALUES (1, 7);

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS working_runs (
    run_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
    source_root TEXT NOT NULL,
    expected_volume_identity TEXT,
    expected_root_identity TEXT,
    identity_strength TEXT NOT NULL,
    reuse_domain TEXT NOT NULL,
    filesystem_capabilities_json TEXT NOT NULL,
    binding_reason TEXT NOT NULL,
    status TEXT NOT NULL,
    scan_generation INTEGER NOT NULL DEFAULT 0,
    checkpoint TEXT,
    committed_batches INTEGER NOT NULL DEFAULT 0,
    blocked_reason TEXT,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE INDEX IF NOT EXISTS working_runs_dataset_status
    ON working_runs(dataset_id, status);

CREATE TABLE IF NOT EXISTS run_source_rebindings (
    run_id TEXT NOT NULL REFERENCES working_runs(run_id),
    sequence INTEGER NOT NULL,
    previous_source_root TEXT NOT NULL,
    previous_volume_identity TEXT,
    previous_root_identity TEXT,
    source_root TEXT NOT NULL,
    volume_identity TEXT,
    root_identity TEXT,
    identity_strength TEXT NOT NULL,
    reuse_domain TEXT NOT NULL,
    reason TEXT NOT NULL,
    continuity TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    PRIMARY KEY (run_id, sequence)
);

CREATE TABLE IF NOT EXISTS source_state (
    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
    relative_path TEXT NOT NULL,
    revision INTEGER NOT NULL,
    kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    condition TEXT NOT NULL,
    basis_json TEXT NOT NULL,
    size_bytes INTEGER,
    mtime_ns INTEGER,
    device_id INTEGER,
    inode INTEGER,
    mode INTEGER,
    fingerprint_algorithm TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    producer_identity TEXT NOT NULL,
    reuse_domain TEXT NOT NULL,
    present INTEGER NOT NULL,
    last_observed_run_id TEXT NOT NULL,
    PRIMARY KEY (dataset_id, relative_path)
);

CREATE TABLE IF NOT EXISTS run_items (
    run_id TEXT NOT NULL REFERENCES working_runs(run_id),
    relative_path TEXT NOT NULL,
    source_revision INTEGER,
    kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    condition TEXT NOT NULL,
    basis_json TEXT NOT NULL,
    size_bytes INTEGER,
    mtime_ns INTEGER,
    device_id INTEGER,
    inode INTEGER,
    mode INTEGER,
    fingerprint_algorithm TEXT,
    fingerprint TEXT,
    producer_identity TEXT NOT NULL,
    reuse_domain TEXT NOT NULL,
    change_kind TEXT NOT NULL,
    last_seen_generation INTEGER NOT NULL,
    PRIMARY KEY (run_id, relative_path)
);

CREATE TABLE IF NOT EXISTS run_issues (
    run_id TEXT NOT NULL REFERENCES working_runs(run_id),
    relative_path TEXT NOT NULL,
    code TEXT NOT NULL,
    message TEXT NOT NULL,
    blocked INTEGER NOT NULL,
    basis_json TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    last_seen_generation INTEGER NOT NULL,
    PRIMARY KEY (run_id, relative_path, code)
);

CREATE TABLE IF NOT EXISTS run_removals (
    run_id TEXT NOT NULL REFERENCES working_runs(run_id),
    relative_path TEXT NOT NULL,
    previous_revision INTEGER NOT NULL,
    basis_json TEXT NOT NULL,
    detected_at TEXT NOT NULL,
    scan_generation INTEGER NOT NULL,
    PRIMARY KEY (run_id, relative_path)
);

CREATE TABLE IF NOT EXISTS work_records (
    work_id TEXT PRIMARY KEY,
    semantic_key TEXT NOT NULL,
    descriptor_json TEXT NOT NULL,
    capability TEXT NOT NULL,
    producer_identity TEXT NOT NULL,
    status TEXT NOT NULL,
    max_attempts INTEGER NOT NULL CHECK (max_attempts > 0),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    lease_run_id TEXT REFERENCES working_runs(run_id),
    lease_owner TEXT,
    lease_token TEXT,
    lease_expires_at TEXT,
    retry_not_before TEXT,
    checkpoint TEXT,
    last_failure_code TEXT,
    last_failure_message TEXT,
    invalidation_reason TEXT,
    output_json TEXT,
    output_digest TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    succeeded_at TEXT,
    CHECK (
        (status = 'running' AND lease_run_id IS NOT NULL
            AND lease_owner IS NOT NULL AND lease_token IS NOT NULL
            AND lease_expires_at IS NOT NULL)
        OR
        (status <> 'running' AND lease_run_id IS NULL
            AND lease_owner IS NULL AND lease_token IS NULL
            AND lease_expires_at IS NULL)
    ),
    CHECK (status <> 'succeeded' OR
        (output_json IS NOT NULL AND output_digest IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS work_records_current_semantic_key
    ON work_records(semantic_key)
    WHERE status <> 'invalidated' AND status <> 'cancelled';
CREATE INDEX IF NOT EXISTS work_records_status_retry
    ON work_records(status, retry_not_before, created_at);

CREATE TABLE IF NOT EXISTS work_dependencies (
    work_id TEXT NOT NULL REFERENCES work_records(work_id),
    dependency_kind TEXT NOT NULL,
    dependency_key TEXT NOT NULL,
    dependency_value TEXT NOT NULL,
    PRIMARY KEY (work_id, dependency_kind, dependency_key)
);
CREATE INDEX IF NOT EXISTS work_dependencies_lookup
    ON work_dependencies(dependency_kind, dependency_key, dependency_value);

CREATE TABLE IF NOT EXISTS run_work_records (
    run_id TEXT NOT NULL REFERENCES working_runs(run_id),
    work_id TEXT NOT NULL REFERENCES work_records(work_id),
    requested_at TEXT NOT NULL,
    PRIMARY KEY (run_id, work_id)
);
CREATE INDEX IF NOT EXISTS run_work_records_work
    ON run_work_records(work_id, run_id);

CREATE TABLE IF NOT EXISTS work_attempts (
    work_id TEXT NOT NULL REFERENCES work_records(work_id),
    attempt_number INTEGER NOT NULL,
    run_id TEXT NOT NULL REFERENCES working_runs(run_id),
    lease_owner TEXT NOT NULL,
    lease_token TEXT NOT NULL,
    started_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    finished_at TEXT,
    outcome TEXT NOT NULL,
    retryable INTEGER,
    error_code TEXT,
    error_message TEXT,
    checkpoint TEXT,
    PRIMARY KEY (work_id, attempt_number),
    UNIQUE (lease_token)
);
"""
