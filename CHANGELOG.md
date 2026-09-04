# Changelog

All notable MediaSense changes are recorded here. Versions follow Semantic
Versioning, with documented breaking changes permitted in minor releases before
1.0.0.

## [Unreleased]

## [0.7.1] - 2026-09-04

### Fixed

- Scope-confirmation `resume` now continues the public Run's exact bound
  accounting Run instead of creating a second unowned accounting attempt and
  failing the public Run on a binding conflict.
- Pre-worker failures leave bound accounting state non-running, and the MCP
  PreCheck Run output schema is self-contained for client-side validation.

## [0.7.0] - 2026-09-04

### Changed

- **Breaking:** replaced the public `mediasense.precheck.read` `inspect` and
  `traverse` operations with consumer-oriented `review`, `expand`, and
  `resolve`; there is no compatibility layer.
- Added deterministic Result reconciliation and frontier-ordered coverage
  cards with public `capture_time`, `media_type`, and Evidence-role projections.
- Added bounded Evidence and Source Item expansion plus exact Source Set
  resolution with Result-bound cursors, membership identities, atomic failures,
  and a 512 KiB response limit.
- Updated Plan, Apply, Runtime, packaged Skills, and public examples to consume
  the new PreCheck Read contract without exposing SQLite or cache state.

### Fixed

- Plan and Apply now verify resolved Source Set identity, complete membership,
  ordering, and cross-page consistency before trusting a handoff.

## [0.6.0] - 2026-09-03

### Changed

- Removed public PreCheck `queued` activity. A successful `start` or `resume`
  now requires a worker lease and a launched worker; ownerless or stale retained
  execution is reported as `suspected_stalled` with an explicit reason and
  `resume`, while `status` remains observational.
- One-shot `mediasense tools call` now rejects PreCheck `start` and `resume`;
  those long-running actions require the persistent MCP Tool Host.

### Fixed

- Successor PreCheck Runs now create and bind their own source-accounting Run
  before execution instead of remaining ownerless with unknown work forever.
- Worker preparation and launch failures now fail the Run immediately instead
  of being hidden as queued. Failures after a worker has acquired the Run remain
  explicit resumable interruptions so committed work is preserved.

## [0.5.0] - 2026-09-02

### Changed

- **Breaking:** every PreCheck `status` response now includes a durable
  `activity` projection with coarse phase, exact-or-unknown phase Work counts,
  last effective progress time, bounded failure summaries, and explicit
  liveness classification.

### Fixed

- Bounded PreCheck compression now projects represented Source Items as usable
  without inventing direct per-item Evidence, while retaining incomplete
  comparison qualifications and continuing to block genuinely unrepresented
  media.
- PreCheck no longer appears unchanged throughout long producer phases merely
  because Source Item accounting is stable. In-process worker exits become a
  resumable pause, while expired worker liveness is reported as
  `suspected_stalled` and can be reclaimed under the same `run_ref`.

## [0.4.1] - 2026-09-02

### Fixed

- Unified the process-local PreCheck Read port used by Plan, Source Set
  expansion, and Apply, so the production composition can create a Plan Working
  State from a valid Result instead of treating `PrecheckReadTool` as a callable.
- Distinguished invalid Host envelopes from unexpected implementation failures,
  and stopped Apply status reads from scheduling execution work.

## [0.3.0] - 2026-08-31

### Changed

- **Breaking:** scoped default Agent integration to a user-selected local
  Honeycomb: `.agents/skills/` for Skills and `.codex/config.toml` for the Codex
  MCP entry. User-level MediaSense Skill and MCP registration are no longer the
  supported default.
- Added the `mediasense` product entry Skill to own authorized installation
  guidance, conflict-safe local MCP setup, session restart, seven-Tool discovery,
  and routing to the three independently loadable stage Skills.
- Kept PreCheck, Plan, and Apply focused on their stage work and redirected
  unavailable-Host recovery to the product entry Skill.
- Clarified that the globally invokable CLI, local Agent integration, and Dataset
  workspace have independent locations and lifecycles.

### Fixed

- Normalized public `dataset_ref` values to the internal Dataset identity before
  dispatch, so an installed Tool Host can complete
  `mediasense.dataset.open → mediasense.precheck.run start`.
- Added an explicit installed-global-CLI acceptance probe so repository `.venv`
  command shadowing cannot be mistaken for deployed-runtime evidence.

## [0.2.0] - 2026-08-31

### Added

- Installable `mediasense` executable and Python wheel metadata.
- Portable-first Dataset workspace discovery with explicit, external-volume, and
  platform-local precedence.
- Local stdio MCP Tool Host and one composition root for the accepted Tool set.
- Installation diagnostics, packaged Skill discovery, and non-overwriting Skill
  installation.
- Independent application, Tool-contract, Dataset-manifest, store-schema, and
  computation-version policy.

## [0.1.0]

- Repository-local PreCheck, Plan, Apply, Geo, contracts, and Skills before the
  installable product surface.
