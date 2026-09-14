# Changelog

All notable MediaSense changes are recorded here. Versions follow Semantic
Versioning, with documented breaking changes permitted in minor releases before
1.0.0.

## [Unreleased]

## [0.11.0] - 2026-09-14

- Deliver continuous Plan pages from saved Work and its bound PreCheck Result,
  including notes-only work, partial drafts, nested groups, unassigned members,
  paginated evidence and frozen versions. Ordinary CLI/MCP replies supply the
  runtime-managed local page; Agents do not author HTML or host a separate app.
- Bind final acceptance to the exact saved Work revision. Every new save invalidates
  earlier acceptance; refresh, paging and idempotent replay do not. Retain saved
  work when page delivery fails and distinguish unreadable evidence from defects.
- Deliver ordinary successor PreCheck Runs with complete Profile snapshots,
  scoped preparation, dependency-based reuse and immutable preparation readback.
  Preserve direct source correspondence without transferring Plan confirmation.
- Include the current Google quota/retry classification, GPX resource diagnostics
  and compression-evidence corrections, plus the current Plan interaction Skills.
- Update all four packaged Skills and public contract resources together.

### Compatibility and verification scope

- Private Dataset manifest 3; stores: Apply 2, Geo 2, Plan 4, PreCheck 19. Supported
  migrations preserve retained evidence; older Hosts cannot write newer stores.
  Follow the installation runbook before opening retained Datasets, finish pending
  old Plan seals and back up stores consistently before migration. Package rollback
  alone is not a rollback of subsequently migrated or modified Dataset state.
- Existing model settings, credentials and compatible dependencies are retained.
  Installation does not run models, call external providers or modify business Plans.
- Reuse the recorded Plan and PreCheck functional checks; this local release checks
  packaging, the retained dependency combination and actual installed CLI/MCP/Skills.
  Real-data acceptance remains with the user. The recorded PreCheck scale memory
  increase remains an open cost limitation; release does not claim it is resolved.

## [0.10.2] - 2026-09-12

- Deliver bundled manufacturer knowledge and personal YAML additions, full
  replacements and disabling, with source evidence and frozen Run snapshots.
- Add paired manufacturer mappings for standard GPS coordinates and source pixel
  dimensions. Keep paired values on the same source and preserve fallback evidence.
- Reopen Datasets and resume frozen work when current manufacturer YAML is invalid;
  report its diagnostic explicitly and reject new work until the configuration is fixed.
- Preserve exact custom integer values, including values beyond binary floating-point
  precision. Invalidate affected metadata work without rewriting sealed Results.
- Preserve existing installation extras, model choices and persistent store formats.

- Connect the accepted DINOv3 ViT-B/16 **384px** Core ML recipe to the production
  CLI/MCP runtime as the recommendation for newly enabled local embedding.
  Embedding stays off by default; explicit ChineseCLIP profiles retain their model.
- Pin preprocessing/runtime and compiled-weight identity, verify local assets,
  diagnose unsupported platforms, and refuse downloads or backend fallback.
  Intel macOS and Windows DINOv3 inference are not released or validated.
- Add an atomic local model preparation script and installed-path checks for
  inference, cache reuse, unavailable-backend blocking and recovery. Update the
  installation runbook and packaged snapshot together. The local 0.10.1 content
  build and installation evidence are recorded in the migration ledger.

## [0.10.1] - 2026-09-12

### Fixed

- Reuse verified PreCheck Result graphs and bound page reads and schema validation.
- Make Plan updates observable and cancellable, serialize execution ownership, and
  recheck durable receipts across concurrent commits and request replay.
- Reduce metadata coordination cost and restore bounded video-frame coverage with
  PyAV, reporting requested positions separately from actual presentation times.

### Distribution

- Ship the single installation/upgrade runbook with the product entry Skill;
  verify source, wheel, project resources, dependency constraints and session readiness.
- PyAV 16.x is now a core dependency. Existing extras remain optional and disabled
  capabilities are not enabled by installation. Persistent store formats are unchanged.
- Existing sealed Results are retained; new decoding does not rewrite old evidence.
  Local release evidence and installation scope are recorded in the capability ledger.

## [0.10.0] - 2026-09-10

### Changed

- Geo routes from offline target-location evidence: mainland locations use AMap;
  overseas locations use Google. Provider reachability does not imply regional
  suitability. Boundary-near locations produce an explicit unresolved route.
- Provider/network prerequisites and exhausted execution budgets block PreCheck
  while retaining progress. Proven point-specific failures remain local outcomes.
- Repeatable map queries may retry classified transient transport failures within
  a finite authorized cycle. Prior unknown effects and charges remain unknown.
- Explicit Geo recovery and the existing PreCheck confirmation/resume path retain
  successful components, continue missing evidence, and share a cumulative budget.
  Replay sends no requests; changing request IDs cannot reuse one consumed grant.
- Geo journal v2 checkpoints reservations/results and rejects legacy writers.
  Dataset, PreCheck, Plan, Apply and Result format versions are unchanged.
- HTTP(S) Proxy, NO_PROXY, CA and timing configuration reaches the production Host;
  profile changes require matching authorization. Diagnostics redact credentials.

### Distribution and limits

- CLI/MCP and all four packaged Skills use the 0.10 release line. Install all from
  the same verified wheel; project Skills and lock remain managed through `npx skills`.
- Natural Earth 5.1.1 routing geometry is bundled with source hashes, provenance
  and public-domain notice. Its 500 m guard does not certify boundary accuracy;
  coastal, reclaimed and disputed areas may require better evidence.
- Synthetic transport/legacy accounting and isolated installed-entry validation
  do not certify live China/overseas network availability, provider billing,
  model quality, or real-Dataset throughput. This release work does not resume the
  blocked business Run or change its old Result.

## [0.9.0] - 2026-09-10

### Changed

- **Breaking:** PreCheck Read uses `review.items`, joining Evidence attributes
  and actual Source Items with separate `represents` relationships. Callers can
  select exact prepared Evidence. There is no permanent old/new Read protocol.
- MCP delivers one business result in `structuredContent` with empty `content`.
  Upgrade the CLI/Host, all four Skills, and independent Read consumers together.
- Current contracts live only under `docs/spec/contract/`; packaged schemas and
  Skill references are release snapshots. Both delivery milestones and the
  acceptance corrections have passed user acceptance.

### Added

- Photographic metadata and source dimensions with provenance, independent
  ordinary/high-resolution preparation, and public video and Geo projections.
- Explicit configuration and production wiring for optional local sensitivity
  detectors. Detection remains disabled by default, with no model download or
  remote fallback. Installing extras does not enable detection.

### Fixed

- Retained metadata raw values and rejection reasons through producer, Result,
  and Read, including Encoder and invalid focal-length candidates.
- Preserved provable historical detection observations when public input
  references cannot be recovered, without rewriting sealed Results.
- Sized pages using their actual envelopes. An oversized middle item becomes a
  local fault and later items remain readable with the same cursor-bound limit.

### Upgrade and validation

- Follow [the installation upgrade steps](readme/installation.md#upgrade-and-rollback),
  retain optional dependencies/configuration and actual installation targets,
  then start a new Agent session. Persistent format versions are unchanged by
  this application release.
- The existing [capability ledger](docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)
  retains the accepted implementation tests, historical 0.8.0-labelled milestone
  candidates, and final 0.9.0 build/install evidence. Quality of models and
  representatives, broad codec/HDR behavior, live Geo accuracy/terms/quotas,
  large-Dataset throughput, and arbitrary clients' large-page handling remain
  uncertified. This release does not imply a new real-Dataset or Apply audit.

## [0.8.0] - 2026-09-08

### Changed

- PreCheck run/read retain two Tools and nine actions with flat `action` and
  `dataset_ref` inputs. Removed the nested `request` wrapper, `operation` alias,
  and redundant successful-response fields. Upgrade the CLI and Skills together.
- Unified phase progress while preserving source accounting, liveness, bounded
  diagnostics, exact pagination, member identities, and Plan/Apply safety checks.
- Address and nearby-place candidates use separate standard Observations.
  Missing GPS, no-result queries, and known terminal location failures do not
  independently block Result publication or Plan entry.
- Geo Tools own bounded retries within the authorized effect ceiling; audit
  reads distinguish current and historical requests and preserve unknown costs.

### Fixed

- Normalized fresh, reused v3, and provable legacy Geo evidence before Result
  projection, preventing non-available Observations from carrying a value.
- Preserved GPS/GPX conflict semantics, unknown journal-replay effects and costs,
  and expected MCP `run_not_found` errors without suppressing implementation errors.

## [0.7.2] - 2026-09-06

### Added

- Added the shared, stage-neutral `mediasense.geo.query` Tool for PreCheck bulk
  acquisition and bounded Plan investigation.

### Fixed

- Restored media-aware PreCheck Geo compression with complete per-Source-Item
  address and nearby-place Evidence.
- Preserved every Provider involved in a composed place observation and kept
  the primary Provider aligned with its transformed coordinate.
- Recorded failed AMap address-and-nearby requests as `resolve_place`, matching
  the single `extensions=all` Provider effect.

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
