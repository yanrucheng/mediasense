## Context

MediaSense is a local-first, agent-native media organization product whose public
behavior is already divided among PreCheck, Plan, Apply, and the stage-neutral Geo
capability. The current Python package has no build-system declaration, executable,
composition root, installed contract resources, Dataset onboarding boundary, or
Tool Host. Callers construct stores and Tools by passing repository paths.

PreCheck may run for hours over multi-terabyte removable media. Repeating that
work merely because a drive moved to another computer is an unacceptable product
default. AI Album kept `.similarity_cache` beside the input directory and thereby
made derived work portable, but its path-derived identity, collision handling,
and recovery semantics are insufficient for MediaSense. Current MediaSense code
already separates source and workspace, records source attachment and rebinding,
keeps Artifacts beside the PreCheck database, and probes SQLite locking and atomic
replacement. It does not yet choose or rediscover a Dataset workspace, and its
`st_dev`/inode attachment identity is only session-local.

The MCP ecosystem standardizes server protocols and transports, not a universal
`connect <client>` command. Clients own their MCP registration. Codex, for example,
supports local stdio registration through `codex mcp add` and stores it in its own
configuration. MediaSense therefore supplies a stable stdio server command and
client-specific instructions, not a command that edits arbitrary client state.

## Goals / Non-Goals

### Goals

- Let a new user install one artifact and invoke `mediasense` outside a checkout.
- Let a Human or Agent open a filesystem path without first inventing a
  `dataset_ref` or manually wiring Python objects.
- Prefer portable Dataset state on a removable source volume so valid PreCheck
  work can be reused across machines.
- Make workspace selection, configuration sources, effect policy, compatibility,
  and missing dependencies visible without exposing secrets.
- Expose the accepted Tools through one composition root and a real stdio MCP
  subprocess while preserving their business contracts and authority boundaries.
- Make upgrades and unsupported state combinations fail safely and recoverably.

### Non-Goals

- Run a daemon, HTTP service, cloud control plane, Docker distribution, dynamic
  plugin system, provider registry, or automatic client-configuration editor.
- Put credentials, shared model downloads, or machine-specific client settings in
  a portable Dataset workspace.
- Write derived state inside a declared source-media root or weaken PreCheck's
  source-read-only boundary.
- Change the meaning of the six existing Tool contracts for transport convenience.
- Certify Windows, Linux, network filesystems, or every removable filesystem in
  the initial macOS release.
- Publish a package or release, invoke a live provider, or move real user media.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumers exist. The new CLI, Host envelope, Dataset manifest, and
store-version declarations may be corrected before a stable release without
compatibility shims. This does not authorize incidental changes to the six already
accepted stage and capability contracts; any such change remains a separate,
reviewed product decision.

## System Context

```text
Human                  Agent client
  |                         |
  | mediasense CLI          | client-owned MCP registration
  +------------+------------+
               |
       MediaSense runtime host
       ├── Dataset opener/resolver
       ├── configuration and diagnostics
       └── one composition root
           ├── mediasense.precheck.run
           ├── mediasense.precheck.read
           ├── mediasense.plan.work
           ├── mediasense.geo.query
           ├── mediasense.apply.run
           └── mediasense.apply.read
               |
        one Dataset workspace
```

The Human owns source selection, consequential confirmation, exceptions, and
acceptance. The Agent interprets intent and uses the Skills. The Dataset opener
owns only Dataset identity and workspace resolution. The composition root owns
construction and configuration binding. Each existing Tool continues to own its
current effects, state, guarantees, and evidence. The stdio Host owns protocol
lifecycle and presentation, not business semantics.

## Decisions

### 1. Opening a Dataset is one necessary public capability

`mediasense.precheck.run` intentionally accepts an exact `dataset_ref`, not a raw
filesystem path. Direct first use therefore requires one stage-neutral boundary
that can inspect a source path, select or create the correct workspace, and return
the exact reference. Hiding this work in every transport or changing PreCheck would
divide authority and produce inconsistent identities.

The new `mediasense.dataset.open` operation accepts a source root and an optional
explicit workspace. It returns the canonical source root, `dataset_ref`, workspace
path, whether state was created, selection tier, configuration sources, and any
capability warning. Creation is a bounded local metadata effect and never writes
source media or contacts a network.

Alternative rejected: require `init` before first use. It makes a product-internal
identity prerequisite the user's problem and preserves the current onboarding gap.

Alternative rejected: let the MCP adapter add a source path to PreCheck requests.
That would create a second, transport-specific version of the PreCheck contract.

### 2. Workspace lookup and creation use a fixed, observable precedence

For a canonical source path, the resolver applies these rules:

1. An explicit workspace path is authoritative. Missing, invalid, incompatible,
   or conflicting state at that path is reported and never falls through.
2. When the source is on a non-system mounted volume, inspect
   `<volume-root>/.mediasense/datasets/` for a matching manifest. Invalid,
   incompatible, or ambiguous matching state blocks rather than falling through.
3. Inspect the platform-local Dataset root. On macOS it is
   `~/Library/Application Support/MediaSense/datasets/`.
4. If no match exists, create portable state on an eligible removable volume;
   otherwise create local state and report why the portable location was not
   eligible.

The resolver derives the relevant mount from the supplied source path. It does not
scan arbitrary volumes. A candidate workspace inside the declared source root is
ineligible. Read-only roots, missing permissions, unverified SQLite locking,
unsupported atomic replacement, and ambiguous matches are reported explicitly.

### 3. Portable Dataset identity is not a mount path

Each workspace contains one small, atomic manifest with a generated stable
`dataset_ref`, manifest format version, creation provenance, workspace tier, and
source attachment descriptors. A portable descriptor records paths relative to
the containing volume plus platform-neutral verification evidence. Absolute mount
paths and session-local device numbers remain observations, not Dataset identity.

Opening the same sidecar on another machine verifies the source attachment before
reusing work. Verified continuity retains the reuse domain. Insufficient evidence
requires an explicit rebind and a new reuse domain; disappearance is reported as
unavailable rather than deletion. Initial implementation must not claim portable
reuse until a subprocess test proves a changed mount path can reopen the same
workspace and preserve eligible work.

### 4. Dataset-owned and machine-owned state remain separate

The Dataset workspace contains the manifest, PreCheck database and Artifacts,
immutable Results, Plan Working State and Frozen Plans, Geo operation journal,
Apply database and Receipts, and store migration records. These objects share the
Dataset lifecycle and must travel together.

The installed executable, MCP client configuration, credentials, shared model
downloads, and optional recent-location hints remain machine-owned. A recent list
is only a discovery accelerator and can be deleted without losing Dataset truth.
Secrets are referenced through environment or a future credential provider; they
are never copied into manifests, logs, Results, version strings, or Git.

### 5. Configuration has a separate precedence and visible provenance

Configuration values resolve from explicit invocation values, Dataset config,
user config, then built-in defaults. Workspace lookup precedence does not double as
configuration precedence. Every Human-facing invocation reports the source,
Dataset identity, selected workspace, selection reason, loaded configuration
files, offline/effect policy, and relevant warnings. Secret values are always
redacted.

For stdio MCP, stdout is reserved exclusively for protocol frames. The same startup
summary is emitted as structured server instructions or diagnostics and to stderr;
it is never interleaved with JSON-RPC messages.

### 6. One composition root owns runtime assembly

One runtime object accepts validated configuration plus an opened Dataset and
constructs all stores, packaged schema resources, provider adapters, the Dataset
opener, and the six existing Tools. CLI and MCP adapters call this root instead of
constructing stage dependencies independently. Providers and external effects are
disabled by default.

The root does not become a service, registry, or source of stage semantics. Tool
contract documents remain authoritative. The installed wheel carries byte-identical
release copies of required schemas and Skills, and tests compare those copies with
their repository authorities.

### 7. stdio MCP is the first Host transport

The installed server command starts an on-demand stdio MCP subprocess. It exposes
`mediasense.dataset.open` plus the six accepted Tools, stable descriptions and input
schemas, and schema-valid results. The protocol implementation uses the maintained
MCP SDK rather than an ad-hoc JSON-RPC subset.

MCP registration belongs to the client. Documentation gives the native Codex
registration command and equivalent manual configuration. MediaSense does not edit
`~/.codex/config.toml` or another client's files. The initial product certifies the
complete Skill-guided workflow on Codex; other stdio MCP clients are protocol-
compatible but not product-certified until exercised in their own acceptance
matrix.

Transport authorization is an envelope around the exact business request. It
binds the local principal and any confirmation or effect authorization required by
the underlying Tool, then removes the envelope before contract validation. The
local v0.x trust boundary is the operating-system account and client-launched stdio
process. A future remote transport requires a separate authentication design.

### 8. CLI is a small control plane, not a second product API

The executable provides help and version output, Dataset open/inspection, doctor,
Tool listing, a diagnostic call path, and MCP startup. It does not reproduce the
PreCheck/Plan/Apply workflow as a second set of business commands. Machine-readable
output is available where an Agent or test must branch on the result; human output
preserves the same target, effects, state, and outcome.

`doctor` checks Python/runtime compatibility, package resources, workspace access,
SQLite locking, atomic replacement, platform status, ExifTool, FFmpeg/ffprobe, local
model availability, client registration visibility where inspectable, and offline
defaults. Optional capabilities are not reported as installation failure.

Uninstall removes the executable only. Dataset workspaces and user configuration
remain until the Human explicitly removes them, and cleanup instructions identify
each location without issuing a destructive command automatically.

### 9. Versions express distinct compatibility questions

The version declared in `pyproject.toml` is the sole application-version source.
Installed runtime and `mediasense --version` read distribution metadata; release
artifacts and tags use the same SemVer value. During `0.y.z`, minor versions may
contain breaking CLI, Host, manifest, or store changes and patch versions are
compatible bug fixes. Prereleases use SemVer prerelease identifiers.

Each public Tool release manifest records its contract identity and exact schema
digest. Dataset manifests record their own format and component store versions.
Opening a newer unsupported format fails without writes. An older supported format
is migrated only by an explicit, journaled, preflighted migration with recoverable
backup; no migration is inferred from the application version. The first release
supports only format/store version 1 and contains no compatibility shim for
unreleased repository databases.

Producer identity, relevant parameters, model identity, input dependencies, and
material environment facts continue to govern Work validity. Application version,
Git commit, wheel version, and Host version are prohibited as blanket Dataset-wide
invalidation keys.

### 10. Delivery proceeds as one clean-install vertical slice

The first slice builds a wheel, installs it into a temporary isolated tool
environment, opens a synthetic Dataset through the accepted location policy,
reports version and doctor results, starts the real stdio subprocess, completes an
MCP initialize and tools/list handshake, and calls at least one non-destructive Tool.
No test relies on the repository `.venv`, Downloads, live providers, paid APIs, or
real media movement.

Focused unit and contract tests precede the affected fast suite. Final acceptance
adds all non-live tests, Ruff, OpenSpec strict validation, package metadata checks,
link/frontmatter/index validation, and `git diff --check`.

## Risks / Trade-offs

- [A removable filesystem may be slow or unsafe for SQLite] → probe required
  capabilities before creation/open, fail closed on an existing unsafe workspace,
  and offer an explicit local placement without claiming portability.
- [A drive can be disconnected during long work] → rely on durable stage state,
  surface unavailable/indeterminate status, and reconcile before retry.
- [A drive may mount under another path] → use a portable manifest and relative
  locator plus verification evidence, never the absolute mount path as identity.
- [A source root can equal the volume root] → do not place the workspace inside the
  declared source boundary; use an explicit safe path or the local fallback and
  report the reason.
- [Packaged schemas and Skills could drift from repository authorities] → generate
  or copy them only as release resources and enforce byte/digest parity in tests.
- [MCP clients differ in registration and optional capabilities] → keep stdio and
  Tool semantics standard, certify Codex first, and label other clients accurately.
- [A Host envelope could blur Tool semantics] → keep the exact business request as
  a distinct member, validate it against the authoritative contract, and document
  transport-only authority fields separately.

## Migration Plan

1. Add the Dataset manifest/resolver and focused location, conflict, capability,
   relocation, and redaction tests.
2. Add package metadata, resource snapshots, single-source runtime version, CLI,
   and doctor without changing existing Tool behavior.
3. Add the composition root and offline construction tests for all six Tools.
4. Add the SDK-backed stdio MCP Host, transport authorization envelope, subprocess
   handshake, discovery, and non-destructive invocation tests.
5. Update the PreCheck Skill and user documentation for Dataset opening and native
   client-owned Codex registration.
6. Build and install a wheel in a fresh temporary environment; run the full quality
   and documentation gates; record exact evidence without publishing.

Rollback before acceptance removes only the new uncommitted files and focused
edits. No package publication, user client mutation, or real Dataset migration is
performed by this change.

## Open Questions

None. The confirmed default external workspace is
`<volume-root>/.mediasense/datasets/`; the confirmed local macOS fallback is
`~/Library/Application Support/MediaSense/datasets/`. Wider platform and client
certification remain future evidence work rather than hidden first-release claims.
