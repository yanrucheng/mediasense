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
