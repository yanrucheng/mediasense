# Proposal: Consolidate Geo Acquisition in PreCheck

## Why

The 0.7.1 flow allowed a locally complete PreCheck to publish a `plan_ready`
Result even though material coordinate-derived evidence had never been acquired,
then created a second Geo lifecycle inside Plan whose authorization preflight
could mask provider unavailability. Geo acquisition must return to the stage
that owns reusable source-derived evidence so Plan can interpret one trustworthy
immutable handoff instead of repairing it.
This change supersedes the Geo and Plan-enrichment portions of the completed but
unarchived `harden-tool-independence-boundaries` change; that change's independent
Apply hardening remains unaffected.

## What Changes

- **BREAKING** Remove product-level `offline` configuration. External effects
  remain disabled until an exact frozen PreCheck batch receives trusted Human
  authorization; configured providers and their availability remain observable
  facts.
- **BREAKING** Make a reverse-geocode outcome for every Source Item with an
  available final coordinate a required PreCheck closure gate. Provider
  unavailability, missing authorization, Human decline, no-result, per-coordinate
  failure, and implementation failure remain distinct and cannot publish a
  misleading `plan_ready` Result. Exact-coordinate deduplication remains an
  internal execution optimization and does not reduce Source Item coverage.
- Add a deterministic, paged Geo summary operation to
  `mediasense.precheck.read`, derived only from the immutable Result. It reports
  coordinate evidence states, exact deduplication semantics, Result-bound Source
  Sets, provider-candidate Evidence references, provenance, qualifications, and
  per-coordinate execution outcomes without creating events, place truth, or
  organization recommendations.
- **BREAKING** Remove `mediasense.plan.work/enrich_geo`, Plan Geo observations,
  Geo inspection/preview sections, Plan Geo authorization and retention choices,
  and all Plan Skill guidance that acquires provider evidence. Plan relies only on
  the effective Result readiness and reads each Source Item's place outcome as
  ordinary PreCheck evidence; it does not inspect acquisition internals.
- **BREAKING** Remove the public `mediasense.geo.query` Tool, its contract,
  Dataset Geo journal/store, and MCP exposure because no independent caller
  remains. Retain only provider-neutral values, adapters, routing, normalization,
  and effect enforcement that PreCheck actually uses.
- Fix Geo observation retention in the immutable PreCheck Result. Provider data
  handling is disclosed separately, and an unknown provider policy can be
  authorized only by confirmation bound to that explicit `unknown` disclosure.
- Preserve old immutable Result bytes as historical objects, but require a new
  PreCheck Result before Plan when old readiness claims omit required Geo
  acquisition. Do not add aliases, dual reads, legacy adapters, or private-
  database repair.

## Capabilities

### New Capabilities

None. The new Geo summary is an operation of the existing PreCheck Read boundary,
not a new Tool, Artifact, service, Skill, or place-cluster entity.

### Modified Capabilities

- `precheck-confirmed-geocoding`: make all-located-Source-Item Geo coverage a
  Result closure responsibility with provider-first availability checks, trusted
  Human authorization, fixed Result retention, and deterministic diagnostic
  summary projection.
- `precheck-run-orchestration`: gate immutable publication on required Geo
  acquisition and preserve distinct terminal/attention/failure meanings.
- `precheck-agent-workflow`: guide disclosure, authorization, decline,
  unavailable-provider recovery, Geo summary review, and Plan handoff.
- `plan-working-state`: remove Plan Geo acquisition and storage and strengthen
  create-time Result readiness validation.
- `plan-agent-workflow`: restrict Plan to interpreting Result evidence or asking
  the Human/reopening PreCheck when machine evidence is insufficient.
- `plan-review-preview`: remove Plan-owned Geo evidence from Preview.
- `geo-capability`: retire the public Tool family and its independent replay
  journal while preserving only the PreCheck-owned internal kernel.
- `tool-host`: remove Geo Tool discovery/dispatch and compose configured map
  providers only into PreCheck execution.
- `dataset-workspace`: remove the independent Geo store from new Dataset state.
- `mediasense-distribution`: remove product `offline` configuration and report
  actual provider configuration/availability instead.

## Impact

- Public contracts: PreCheck Run, PreCheck Read, Plan Work, Dataset Open, MCP Tool
  listing, packaged Skill snapshots, and removal of Geo Query.
- Runtime: provider composition moves into PreCheck; Plan Geo adapter/state and
  public Geo dispatch/journal are deleted; configuration and diagnostics no longer
  expose `offline`.
- Results and migration: new Results carry immutable Geo candidate Evidence and
  an honest acquisition summary. Old Result bytes are not rewritten and old Plan
  Working State is not migrated.
- Documentation/tests: active foundation and reusable-capability design,
  contracts, Skills, distribution guidance, migration ledger, deterministic
  spies, MCP subprocess/runtime coverage, and integration evidence are updated.

