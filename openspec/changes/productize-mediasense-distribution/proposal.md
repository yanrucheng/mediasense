## Why

MediaSense has working PreCheck, Plan, Apply, Geo, and Skill contracts, but an
owner still has to run repository Python and manually assemble storage, schemas,
providers, and Tool instances. There is no executable, no repeatable clean
installation, no first-use Dataset registration, no Tool Host, and no release or
persistent-store compatibility contract. This makes the implemented product
unusable outside its source checkout and makes expensive PreCheck work too easy
to strand on one computer.

## What Changes

- Build one installable Python distribution with one `mediasense` executable,
  explicit build metadata, packaged contracts and Skills, and a documented `uv
  tool install` path.
- Add a Dataset-open boundary that resolves or creates one Dataset workspace in
  this order: an explicit path, the source volume's
  `<volume-root>/.mediasense/datasets/`, then the platform-local application-data
  directory. Existing invalid, conflicting, or incompatible state blocks rather
  than silently falling through.
- Keep Dataset-owned databases, derived Artifacts, Results, Plans, Apply journals,
  and Receipts together so a removable Dataset can carry expensive work between
  computers. Keep executables, client configuration, credentials, shared model
  downloads, and non-authoritative recent-location hints outside that workspace.
- Add one composition root that constructs the Dataset resolver and the six
  existing public Tools from one validated runtime configuration.
- Add a local stdio MCP Host. Client registration remains owned by each MCP
  client; MediaSense exposes a stable server command and does not rewrite Codex,
  Claude, VS Code, Cursor, or other client configuration.
- Add a minimal Human-facing control surface for version, help, Dataset open,
  diagnostics, Tool discovery, and MCP startup, with truthful configuration and
  workspace provenance on every material invocation.
- Establish SemVer pre-1.0 policy, a single application-version source, explicit
  Tool-contract and persistent-store compatibility, release notes, upgrade and
  rollback behavior, and producer-specific computation invalidation.
- Add clean-wheel, isolated-install, subprocess MCP handshake, Tool discovery,
  non-destructive invocation, dependency-diagnostic, and compatibility tests.

## Capabilities

### New Capabilities

- `mediasense-distribution`: install, inspect, diagnose, integrate, upgrade, and
  remove the local MediaSense executable without repository-only assembly.
- `dataset-workspace`: resolve, create, identify, and safely reopen portable or
  local Dataset-owned state.
- `tool-host`: compose and expose the Dataset boundary and existing MediaSense
  Tools over a replaceable local transport.
- `mediasense-versioning`: govern application, Tool contract, persistent-store,
  Skill, and computation versions without conflating their compatibility.

### Modified Capabilities

- `precheck-agent-workflow`: replace the unsupported-path onboarding gap with the
  accepted Dataset-open boundary while preserving exact `dataset_ref` handoff to
  `mediasense.precheck.run`.

## Impact

- `pyproject.toml`, lock metadata, package entry points, and packaged resources.
- New distribution/runtime modules under `src/mediasense/` and focused tests.
- The PreCheck Skill, root README, user installation and troubleshooting guides,
  release notes, and current specification indexes after acceptance.
- Existing Tool business contracts remain authoritative. The MCP transport wraps
  requests and authorization context without redefining stage meaning.
- No AI Album or Hong Kong fixture mutation, real-media Apply execution, live
  provider request, paid API call, package publication, Git commit, merge, push,
  release creation, or hidden modification of an Agent client's configuration.
