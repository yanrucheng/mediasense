## 1. PreCheck Geo ownership and authorization

- [x] 1.1 Remove optional/offline Geo selection from PreCheck execution configuration and make a non-empty frozen coordinate batch a publication gate.
- [x] 1.2 Compose configured providers into the PreCheck batch engine and return provider-unavailable before any authorization request.
- [x] 1.3 Bind trusted Human confirmation to the exact frozen coordinates, provider/request/cost ceilings, provider-policy disclosure, and immutable Result retention; make decline terminal and zero-effect.
- [x] 1.4 Preserve per-coordinate success, no-result, localized failure, attempts, provenance, effect accounting, reuse, and unexpected exception semantics.

## 2. Immutable Result and Read projection

- [x] 2.1 Project each unique provider candidate as ordinary inline Result Evidence with Result-local refs and exact Source Item membership.
- [x] 2.2 Add the deterministic paged `precheck.read/geo_summary` implementation and contract, including state counts, conflict detection, exact deduplication rule, Source Sets, outcomes, Evidence refs, provenance, and qualifications.
- [x] 2.3 Reject historical or malformed Result readiness in Plan when `geo_summary` is incomplete, while allowing complete and not-applicable acquisition.

## 3. Remove displaced Plan and public Geo entities

- [x] 3.1 Remove `enrich_geo`, `PlanGeoAdapter`, Plan Geo authorization, Working State Geo observations, inspect/preview branches, and related exports.
- [x] 3.2 Remove the public `mediasense.geo.query` contract, dispatch, listing, Tool adapter, replay journal, Dataset Geo store, fixtures, and tests.
- [x] 3.3 Trim provider-neutral Geo modules to the values, adapters, routing, normalization, accounting, and effect blocking that PreCheck actually invokes.

## 4. Runtime configuration and migration

- [x] 4.1 Remove product `offline` configuration from runtime, Dataset Open, doctor/CLI presentation, schemas, fixtures, and distribution smoke paths.
- [x] 4.2 Report provider credential/capability/policy facts without treating credentials as authorization.
- [x] 4.3 Implement the one-way public Dataset manifest migration that removes Geo store declaration without reading private databases or rewriting Results; use a clean Plan private store.

## 5. Contracts, Skills, and documentation

- [x] 5.1 Synchronize canonical and packaged PreCheck Run, PreCheck Read, Plan Work, and Dataset Open contracts and remove Geo Query resources.
- [x] 5.2 Update PreCheck and Plan Skills, preserving concurrent Organization Profile edits, and remove Plan Geo fixture/guidance.
- [x] 5.3 Update foundation, reusable-capability architecture, active design/spec indexes, migration ledger, and distribution guidance with the new authority boundary and migration classification.

## 6. Verification

- [x] 6.1 Add acceptance tests for no provider, missing authority, Human decline, exact authorized batch/effect ceilings, no-result, localized failure, no GPS, and source immutability using provider/network spies.
- [x] 6.2 Add exhaustive Result-versus-Geo-summary equivalence, Plan readiness rejection, public Tool listing, MCP subprocess/authorization, resumability, accounting, idempotency, and Result immutability coverage.
- [x] 6.3 Run focused and full contract/runtime/PreCheck/Plan tests, Honeycomb integration, lint/type checks if configured, and strict OpenSpec validation; record outcomes and remaining risks.
  - Acceptance completed with 166 focused contract/runtime/PreCheck/Plan/MCP tests,
    5 explicit Honeycomb integration tests, and 565 full-suite tests passing with
    16 deselected. Ruff, strict OpenSpec validation, contract authority parity,
    and diff whitespace checks also passed. No type checker is configured.
  - Remaining operational risk is Provider policy/configuration drift outside the
    repository; each Run therefore binds authorization to the disclosed policy and
    treats unknown policy as `unknown`, never as implicit acceptance.

## 7. Acceptance remediation

- [x] 7.1 Replace distribution smoke resource and Tool counts with exact expected filename/name sets, update packaged entry guidance, and pass a clean wheel install.
- [x] 7.2 Separate the full frozen-batch identity from the pending external-effect identity so disclosure, quantity, coordinates, and request ceilings describe only work that can still be transmitted.
- [x] 7.3 Replace unbounded inline Geo group membership with the existing Result-bound resolvable Source Set and add high-fanout response-size coverage.
- [x] 7.4 Add a human-reviewable `geo_summary` mock exchange and synchronize its canonical and packaged copies.
- [x] 7.5 Remove remaining active optional/Plan-local Geo wording and align information architecture, Skills, module descriptions, and README.
- [x] 7.6 Make MCP Geo resume obtain trusted confirmation through host elicitation rather than caller-authored authority JSON, and add a real stdio MCP acceptance test for accept, decline, and unsupported elicitation.
- [x] 7.7 Re-run focused tests, clean wheel smoke, full pytest, Ruff, strict OpenSpec validation, and diff/worktree audits.
  - The remediation-focused suite passed `202` tests. The final explicit MCP
    subprocess/runtime/contract consistency suite passed `160` tests, including
    accept, decline, unsupported elicitation, and non-capability implementation
    error behavior. The explicit Honeycomb integration suite passed `5` tests.
  - The default full suite passed `568` tests with `16` deselected. Ruff reported
    `All checks passed!`; strict OpenSpec validation passed; and
    `git diff --check` passed. No type checker is configured.
  - `mediasense 0.7.1` was rebuilt at
    `/private/tmp/mediasense-wheel-docfix.SrOCu2/mediasense-0.7.1-py3-none-any.whl`;
    its offline clean-install distribution smoke passed with the exact six-Tool,
    contract-file, and Skill-file sets.
  - Canonical, packaged, and Skill-reference contract copies matched by SHA-256:
    PreCheck Read `5c3ebe10dba65a07f69041eb6b66b62343d344ad892482b71ececabf568d9273`,
    PreCheck Run `29b8de27bd3b4d7af5b848ed1793c5714f6a51c251bb7114ed5c3095f4fd296a`,
    Plan Work `b0c53f357b35266b81e29627bf6a4804025fe6e459e8be2d83d1beea80668777`,
    and Dataset Open `09c95b73009c1363fa3ccf88611205d6f42202f2bc8cb9df0d2353880bd67543`.
  - A real local Codex CLI `0.153.4` app-server session connected to the
    MediaSense stdio MCP server and issued form elicitation for both accept and
    decline. Accept produced Host-authored `human:mcp-elicitation` authority and
    exactly one request for the disclosed pending coordinate; decline produced a
    cancelled terminal state and zero Provider requests. This verifies the real
    installed client protocol path, not a graphical Codex UI interaction.
  - The final stale-vocabulary scan found only removal/history/negative assertions,
    and the worktree audit found no untracked media, caches, raw logs, model output,
    or other untracked files.
