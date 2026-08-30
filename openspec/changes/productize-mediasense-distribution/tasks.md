## 1. Dataset onboarding and portable workspace

- [x] 1.1 Define and test the Dataset manifest, exact three-tier lookup, external-volume discovery, atomic creation, and idempotent reopen behavior.
- [x] 1.2 Fail closed for explicit-path errors, corrupt/incompatible higher-priority state, ambiguous matches, source/workspace nesting, and unsafe filesystem capabilities.
- [x] 1.3 Prove relocation to a different mount path preserves verified eligible work and unverified rebinding creates a new reuse domain.
- [x] 1.4 Report workspace and configuration provenance with complete secret redaction.

## 2. Installable distribution and Human control surface

- [x] 2.1 Add an explicit build system, `mediasense` entry point, authoritative runtime version lookup, and packaged contract/Skill resources with parity tests.
- [x] 2.2 Implement help, version, Dataset open/inspect, doctor, Tool listing, diagnostic call, and MCP startup commands with aligned human and machine outcomes.
- [x] 2.3 Diagnose Python, platform, workspace, SQLite/atomic-replace, ExifTool, FFmpeg/ffprobe, model, resource, and offline-policy status without hidden installation or network effects.
- [x] 2.4 Document installation, upgrade, rollback, uninstall, cleanup, and supported/uncertified boundaries from an empty environment.

## 3. Composition root and Tool Host

- [x] 3.1 Implement one Dataset-bound composition root for packaged schemas, configuration, stores, providers, the Dataset opener, and all six existing Tools.
- [x] 3.2 Keep external providers disabled by default and bind confirmation/authorization through a transport-only envelope without changing business requests.
- [x] 3.3 Implement an SDK-backed stdio MCP Host with protocol-safe logging, stable discovery, schema-valid errors, and lifecycle cleanup.
- [x] 3.4 Update the PreCheck Skill to open a source path through `mediasense.dataset.open` and hand only the returned exact `dataset_ref` to PreCheck Run.

## 4. Version and persistence policy

- [x] 4.1 Make package metadata the single application-version source and align runtime output, built wheel metadata, release notes, and artifact naming.
- [x] 4.2 Record Tool contract identities/digests and Dataset manifest/component store versions; reject unsupported newer, corrupt, and unversioned installed state before mutation.
- [x] 4.3 Define an explicit migration preflight/journal/backup boundary for future supported older stores without adding unused compatibility routes in the first release.
- [x] 4.4 Prove application upgrades do not act as blanket PreCheck Work invalidation keys.

## 5. Product acceptance

- [x] 5.1 Add focused unit, negative, contract, and integration tests for Dataset lookup, config precedence, diagnostics, resource parity, composition, and compatibility matrices.
- [x] 5.2 Build a wheel and install it into a new temporary environment independent of the repository `.venv`.
- [x] 5.3 Exercise installed help, version, doctor, automatic Dataset opening, repeated opening, Tool discovery, real subprocess MCP initialize, and a non-destructive Tool call.
- [x] 5.4 Run Ruff, all non-live tests, OpenSpec strict validation, documentation frontmatter/index/link checks, package inspection, and `git diff --check`.
- [x] 5.5 Present the complete implementation, limitations, clean-install transcript, and migration comparison to the user; leave this change active and unarchived.
- [ ] 5.6 Only after explicit user acceptance, replace the delegation result placeholder while preserving its frontmatter; do not commit, merge, push, publish, or close the delegation.
