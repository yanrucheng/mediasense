# Changelog

All notable MediaSense changes are recorded here. Versions follow Semantic
Versioning, with documented breaking changes permitted in minor releases before
1.0.0.

## [Unreleased]

### Changed

- **Breaking:** every PreCheck `status` response now includes a durable
  `activity` projection with coarse phase, exact-or-unknown phase Work counts,
  last effective progress time, bounded failure summaries, and explicit
  liveness classification.

### Fixed

- PreCheck no longer appears unchanged throughout long producer phases merely
  because Source Item accounting is stable. In-process worker exits become a
  resumable pause, while expired worker liveness is reported as
  `suspected_stalled` and can be reclaimed under the same `run_ref`.

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
