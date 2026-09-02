## Context

MediaSense currently declares application `0.3.0`, targets a `0.3.x` Tool Host
in all packaged Skills, and documents a previous store combination. The source
now contains a breaking PreCheck Run contract and PreCheck store schema 17.
MediaSense is not in production, so the repository's Zero Backward
Compatibility policy prohibits an old-contract adapter, dual store writes, or
an automatic schema-16 migration merely to preserve pre-release state.

CLI installation, Honeycomb-local Skills, MCP registration, and Dataset state
are independent locations. A truthful upgrade must handle each explicitly.

## Goals / Non-Goals

**Goals:**

- publish the current source as one coherent `0.4.0` release;
- expose one supported compatibility combination;
- provide a safe, explicit upgrade for the four packaged MediaSense Skills;
- preserve unrelated Honeycomb Skills and configuration;
- reject old Dataset state before mutation; and
- verify the exact built wheel and local installation.

**Non-Goals:**

- migrate PreCheck schema 16 to 17;
- overwrite arbitrary or user-modified Skills without a recoverable backup;
- edit MCP configuration when the existing command remains valid;
- download optional models or system packages; or
- certify the Hong Kong fixture or physical-volume throughput.

## Backward Compatibility Policy

| Attribute | Value |
|-----------|-------|
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumers exist. Compatibility aliases, version routers, dual
writes, and store adapters are prohibited. Clean-start Dataset state is assumed.

## Decisions

### 1. Release as application version 0.4.0

The package-metadata version changes once from `0.3.0` to `0.4.0`. Runtime
`--version`, built wheel name, packaged resources, and release verification
derive from that source. The packaged Skills target `0.4.x` because their
workflow depends on the new Run contract.

Patch `0.3.1` was rejected: the Tool request/response semantics and store format
are breaking. Version `1.0.0` was rejected because no production/stability gate
has declared the public surface stable.

### 2. Publish one exact compatibility matrix

`0.4.x` supports:

| Domain | Value |
| --- | --- |
| Dataset manifest | 1 |
| PreCheck store | 17 |
| Plan store | 2 |
| Geo journal | 1 |
| Apply store | 2 |
| Skills | From the same `0.4.x` release |

Public Tool compatibility additionally requires the installed contract ID and
exact schema digest; application version alone is not proof.

### 3. Old Dataset workspaces are preserved and refused

`0.4.x` does not mutate a manifest or PreCheck database declaring schema 16.
Dataset Open/Inspect reports `store_unsupported`. The user creates a distinct
schema-17 workspace for the same read-only source. The schema-16 workspace is
retained for rollback with `0.3.x`.

Changing only an internal schema integer was rejected because scope review adds
new authority and lifecycle semantics. An in-place migration was rejected under
Zero BC because recomputing a factual tree and Human scope choice is the honest
new boundary.

### 4. CLI replacement uses one exact wheel

Build `dist/mediasense-0.4.0-py3-none-any.whl`, inspect its metadata and packaged
contracts/Skills, then install it with:

```text
uv tool install --force <exact-wheel>
```

The trusted checkout installer remains a convenience wrapper. Release evidence
uses the exact wheel so the verified and installed bytes are the same artifact.

### 5. Skill upgrade is explicit and scoped

Add:

```text
mediasense skills upgrade --target <absolute-skills-root>
```

The operation considers only the four packaged Skill names. It:

1. stages the complete release-matched set under the explicit target;
2. moves each differing existing MediaSense Skill to one operation-owned backup;
3. atomically installs every staged replacement;
4. rolls all touched names back if any replacement fails; and
5. removes the backup only after success.

Unrelated Skill directories are never read as candidates or changed. A target
that is not an existing directory, contains a MediaSense Skill target that is
not a directory, or cannot support the transaction is refused. The JSON result
distinguishes installed, upgraded, and unchanged names.

`skills install` remains idempotent for identical content and refuses different
existing content. That preserves its narrow first-install contract.

### 6. Restart and verification remain explicit

An explicitly selected operational Honeycomb may retain an MCP table that calls
`mediasense mcp`; that command does not need to change for `0.4.0`. A current
Agent session may retain old Skill text or an MCP child, so an upgraded
Honeycomb requires a new trusted session. A fresh subprocess verifies CLI
version, doctor output, seven Tool descriptors, the new PreCheck contract digest,
and release-matched Skill hashes.

### 7. The source checkout is not an implicit Honeycomb

The authoritative distributable Skill sources live under
`src/mediasense/_resources/skills/`. Repository-root `.agents/skills/` entries
are an Agent-client activation surface, not a second source tree. The MediaSense
checkout therefore does not track or install its own four Skills and does not
carry a project MCP registration merely because it builds the product.

Release verification installs the packaged Skills into a temporary explicit
Honeycomb. A Human may still explicitly choose the source checkout as an
operational Honeycomb, but that is a local ignored installation, not release
state and not a default inferred from the current working directory.

## Risks / Trade-offs

- **[Skill upgrade could overwrite local edits]** → The operation is explicit,
  scoped to MediaSense names, transactional, and reports upgraded names; the
  user is told to preserve intentional customizations before invoking it.
- **[Four directory renames are not one filesystem atomic operation]** → Stage
  the full set first, keep an operation-owned backup, roll back all touched
  names on failure, and test injected mid-upgrade failure.
- **[Clean-start loses derived PreCheck reuse]** → Preserve the old workspace,
  keep source media untouched, and state the recomputation cost before creating
  the new workspace.
- **[An old Agent session may appear upgraded]** → Treat filesystem installation
  as incomplete integration until a new session discovers the release-matched
  Host and Skills.
- **[The product checkout could be mistaken for the operational WorkTree]** →
  Keep packaged Skill sources separate from Agent discovery paths, require an
  explicit Honeycomb target, and verify installation in temporary directories.
- **[Rollback can select the wrong workspace]** → Document the 0.3/schema-16 and
  0.4/schema-17 pairing explicitly; neither executable rewrites unsupported
  state.

## Migration Plan

1. Update package version and every current compatibility declaration.
2. Implement and test transactional `skills upgrade`.
3. Update installation/upgrade/rollback documentation and packaged Skills.
4. Run Ruff, focused tests, the non-Hong-Kong suite, strict OpenSpec validation,
   and reproducible wheel build/inspection.
5. Clean-install the exact wheel in isolation and verify CLI, Host, contracts,
   and Skills.
6. Replace the local uv tool with that wheel.
7. Remove the repository-local activated Skill copies and verify packaged Skill
   installation and upgrade against an explicit temporary Honeycomb.
8. Retain old Dataset workspaces; create schema-17 workspaces only on later
   explicit Dataset work.

## Open Questions

None. The user authorized the local `0.4.0` CLI upgrade and removal of the
mistaken repository-local Skill activation, while Dataset migration and
operational-Honeycomb MCP configuration changes remain out of scope.
