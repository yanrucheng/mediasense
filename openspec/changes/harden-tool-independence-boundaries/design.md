## Context

MediaSense has stable PreCheck, Plan, and Apply stage contracts, plus a stage-neutral Geo capability. The independence review found composition failures at the boundaries rather than missing product stages: contradictory Geo ownership prose, schema/runtime disagreement, incomplete Frozen Plan validation, caller-asserted Source Set completeness, a private-path Plan-to-Apply handoff, and Apply Read exceptions escaping its public envelope.

The governing product boundary is fixed. PreCheck may perform one optional, coordinate-only, frozen-batch reverse-geocode step under Run-scoped authority; Plan may acquire additional authorization-bound Geo observations for a planning question; Apply performs no Geo work. Provider choice, routing, coordinate conversion, cache representation, schema-loading location, and database layout remain replaceable methods.

## Goals / Non-Goals

### Goals

- Make every public contract agree with its runtime in both accepted and rejected cases.
- Let Apply trust a complete Frozen Plan and complete Source Set expansion without trusting private stage state or caller assertions.
- Make the Plan seal result directly consumable by Apply prepare.
- Keep every public failure machine-readable and schema-valid.
- Prove the cross-stage composition locally with no provider, paid API, or real media mutation.

### Non-Goals

- Change PreCheck into Plan-style per-query enrichment or require PreCheck to call `mediasense.geo.query`.
- Add a public Source Set Tool, Plan Read Tool, artifact service, registry, plugin system, or shared persistent Geo cache.
- Make provider, SQLite, hash, directory, or cache choices permanent product contracts.
- Change Apply execution semantics, execute a real user-media move, mutate AI Album, or modify the Hong Kong fixture.

## Decisions

### 1. Caller stages own selection, refusal, and retained evidence

PreCheck owns its frozen representative-coordinate batch, Run-scoped authorization checkpoint, Work reuse, and Result projection. Plan owns the purpose and scope of each additional lookup, its Human authorization binding, and its Plan-local observations. A Human refusal stops before Geo invocation and is recorded by the caller when useful.

The Geo Tool distinguishes absent authority from authority that does not match the request. Both require a new matching authorization before effects, but neither claims the Human explicitly refused. The public Geo `refused` outcome is removed because the current Tool has no trusted refusal input and therefore cannot establish that meaning.

Alternative rejected: add a refusal object or public authorization service. It would add an entity and lifecycle without improving the current caller-owned decision boundary.

### 2. Geo input is strict and never default-mutated by schema or runtime

Every subject coordinate explicitly supplies `datum`. Required textual identifiers and locales contain at least one non-whitespace character. JSON Schema declares these rules and runtime parsing enforces the same rules; Schema `default` remains documentary and is not treated as input mutation.

Alternative rejected: infer `WGS84` for omitted datum. That changes coordinate meaning silently and makes schema-validity depend on adapter behavior.

### 3. Frozen Plan validation has one stage-neutral implementation

A small internal `mediasense.frozen_plan` module owns loading the authoritative schema, validating the complete document, enforcing the supported encoding profile, calculating the current content identity, and checking final-confirmation binding. Plan publication and Apply preparation reuse it. It is a module, not a public Tool: it has no independent authorization, external effect, lifecycle, or state.

Apply performs this validation before destination/source probing, Run creation, or any other filesystem effect. Schema violations remain failures even when an attacker recomputes a matching digest.

Alternative rejected: copy selected schema checks into Apply. That recreates the present drift and lets unknown future fields or profiles pass silently.

### 4. Source Set interpretation is a shared deterministic module over PreCheck Read

A stage-neutral internal resolver interprets the five Frozen Plan Source Set forms: `explicit`, `accounts_for`, `represents`, `union`, and `difference`. It accepts one exact `result_ref` and only a callable implementation of the public `mediasense.precheck.read` contract. It validates expression shape, reference type, response binding, pagination progress, total coverage, and duplicates, and fails closed on every ambiguity.

Plan uses the resolver for candidate validation. Production `ApplyRunTool` constructs the resolver from its accepted PreCheck Read boundary; callers cannot substitute a completeness claim. The lower-level Apply store retains resolver injection only as an internal test seam.

Alternative rejected: expose a Source Set Tool or registry. The resolver has no authority, external effect, state, or lifecycle beyond deterministic interpretation of two existing contracts.

### 5. Apply prepare accepts the Frozen Plan object, not a Plan-private path

The forward prepare request replaces `frozen_plan_path` with `frozen_plan`, referencing the authoritative Frozen Plan schema by its stable schema ID. `mediasense.plan.work` already returns this object on successful seal, so a caller performs a mechanical field transfer and supplies only Apply-owned current root and destination bindings.

Alternative rejected: publish a new locator. The complete immutable object is already in the seal response; a locator would add ownership, retention, resolution, and failure semantics with no current need.

### 6. Apply Read converts boundary failures into one public error shape

`ApplyReceiptReader.read` catches input-schema errors, missing/corrupt Receipt failures, invalid action/section/filter/page/cursor, and segmented-ledger availability or integrity failures. It maps them to stable error codes and validates the resulting envelope before return. Internal `ReceiptError` and schema exceptions remain implementation diagnostics only.

### 7. Verification is layered by risk

This is a high-risk public API and filesystem-safety change. Development runs begin with focused Geo, Frozen Plan, Source Set, handoff, and Receipt tests; then affected integration tests; then the repository's default non-live suite. A single local E2E uses temporary files and real internal stage components through public boundaries, stopping at Apply preparation so it proves zero Apply effects.

## Risks / Trade-offs

- [Schema references require a resolver registry at runtime] → Apply loads the exact Frozen Plan schema supplied at construction and registers its `$id`; contract tests exercise standalone and composed validation.
- [Moving shared interpretation can accidentally change Plan behavior] → retain Plan-facing imports where useful and run all existing Plan contract/preview/Geo tests.
- [A dishonest test resolver can still bypass the lower-level store seam] → keep that seam internal and ensure the only public production composition constructs the trusted resolver itself; add an adversarial regression proving the public Tool cannot be shrunk by caller injection.
- [Pagination bugs can silently omit Source Items] → require stable result/origin/relation/direction, monotonic unseen cursors, consistent totals, exact returned counts, no duplicate targets, and final observed count equal to total.
- [Strict Geo strings reject previously schema-valid whitespace] → declare the boundary change explicitly and cover both schema and runtime rejection.
- [Full Plan schema validation adds preparation cost] → validation is linear in one already-materialized plan and occurs once before filesystem probing; safety value dominates this bounded cost.

## Migration Plan

1. Land the active OpenSpec delta without archiving it before Human review.
2. Add shared Frozen Plan and Source Set modules while preserving existing Plan-facing behavior.
3. Align Geo schemas/runtime and caller-owned refusal semantics.
4. Change Apply prepare input to the complete Frozen Plan object and update all internal callers/tests.
5. Normalize Apply Read failures.
6. Run focused tests after each slice, then OpenSpec strict validation, Ruff, the full default non-live pytest suite, diff hygiene, and documentation validation.

Rollback before acceptance is one worktree revert of this uncommitted change. No persistent production migration or external effect is performed in this work.

## Open Questions

None. The remaining production uncertainties are operational certification of additional filesystems, long-duration runs, and real provider behavior; they do not change this contract repair.
