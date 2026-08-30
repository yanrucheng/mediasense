# Geo Capability Backlog

## 1. Product baseline and change contract

- [x] 1.1 Record the accepted Plan-owned, coordinate-only Geo enrichment direction in a review design.
- [x] 1.2 Preserve the current-state and target responsibility trees with explicit non-goals.
- [x] 1.3 Create the OpenSpec proposal, design, capability deltas, and complete delivery backlog.
- [x] 1.4 Validate the change strictly and resolve every structural or semantic validation error.

## 2. Slice 1 — Provider-neutral family model

- [x] 2.1 Add normalized operation, coordinate, request, effect-envelope, authorization-binding, component-outcome, attempt, continuation, and result value types.
- [x] 2.2 Define stable ports for operation-aware providers and provider-neutral routing without provider-native response fields.
- [x] 2.3 Replace implicit cross-call router mutation with immutable request-scoped route context.
- [x] 2.4 Add unit tests for validation, status distinctions, provenance, accounting, and concurrent route isolation.

## 3. Slice 2 — Provider adapters

- [x] 3.1 Adapt AMap to the operation-aware port while preserving datum conversion and exact request accounting.
- [x] 3.2 Adapt Google Maps to separate reverse-geocode and nearby-place component outcomes, including partial failure.
- [x] 3.3 Add shared conformance vectors for AMap, Google Maps, and a fake adapter covering normalization, request counts, billable uncertainty, failure mapping, and credential exclusion.
- [x] 3.4 Wire providers explicitly without a dynamic registry or provider-specific public Tool.

## 4. Slice 3 — Authorization-bound Geo Tool

- [x] 4.1 Define the human-readable Geo Tool contract, Tool JSON, and positive, refusal, partial, and continuation Mocks.
- [x] 4.2 Implement `resolve_place`, `reverse_geocode`, and `nearby_places` with effect-free authorization preflight.
- [x] 4.3 Bind supplied authority to the exact normalized request and reject every unauthorized widening before network access.
- [x] 4.4 Report logical operations, actual provider requests, billable units, data egress, fallback, uncertainty, and indeterminate effects separately.
- [x] 4.5 Add a minimal Tool-owned idempotency journal that recovers identical retries, refuses conflicting request IDs, and never acts as a shared geographic cache.
- [x] 4.6 Add contract-vector, effect-guard, retry, cancellation, fallback, and continuation tests with no live network calls.

## 5. Slice 4 — PreCheck migration

- [x] 5.1 Adapt `ReverseGeocodeProducer` to the family port without moving coordinate selection, freezing, confirmation, Work, reuse, cancellation, or Result projection.
- [x] 5.2 Preserve existing PreCheck output and authorization semantics, including routing continuity for reused ordered batches.
- [x] 5.3 Retain temporary `mediasense.geo` compatibility exports until every repository caller is migrated.
- [x] 5.4 Run existing geocoding and PreCheck orchestration tests and add isolation regressions proving the family never reads PreCheck private state.

## 6. Slice 5 — Plan-owned Geo enrichment

- [x] 6.1 Add Plan-private persistence for exact Result-bound Geo observations, authorization evidence, provenance, and idempotent request outcomes without copying the PreCheck Result.
- [x] 6.2 Add the Plan adapter that selects coordinates for one material Plan question and invokes only the public Geo boundary.
- [x] 6.3 Expose stored observations to Plan inspection and preview while keeping provider observation, Agent judgment, and Human confirmation distinct.
- [x] 6.4 Preserve a useful refusal path and prevent Plan or preview rendering from making undeclared provider calls.
- [x] 6.5 Add end-to-end tests for high-level success, nearby-place continuation, refusal, stale authorization, partial provider failure, restart recovery, and PreCheck/Plan state isolation.

## 7. Slice 6 — Agent workflow and evaluation

- [x] 7.1 Update the Plan Skill to select Geo enrichment only when it can materially affect grouping, naming, disposition, or the decision to stop.
- [x] 7.2 Teach the Agent to disclose effects, request exact authorization, distinguish observation from judgment, follow bounded continuations, and stop when evidence is sufficient.
- [x] 7.3 Add workflow fixtures that test success, refusal, conflict, escalation, and stopping without prescribing a fixed provider or call sequence.
- [x] 7.4 Decide whether a separate Geo Skill is justified from observed repeated judgment; default to no Skill.
- [x] 7.5 Compare relevant behavior with AI Album and classify differences across functionality, cost, reuse, user effort, privacy, uncertainty, and safety.

## 8. Slice 7 — Publication and acceptance

- [x] 8.1 Run focused tests, the full non-live suite, linters, and strict OpenSpec validation.
- [x] 8.2 Publish the accepted Geo Tool contract and Mocks under `docs/spec/` and update its index.
- [x] 8.3 Reconcile the active Plan specifications, Plan Skill, reusable-capability design, and Geo evolution design without leaving competing current truth.
- [x] 8.4 Record verification and acceptance evidence, including all ten reusable-capability acceptance tests.
- [x] 8.5 Archive the OpenSpec change only after both PreCheck and Plan use the accepted boundary end to end.

## Deferred, evidence-triggered backlog

- [x] D.1 Defer `inspect_attempts` until attempt detail gains an independent retained read lifecycle.
- [x] D.2 Defer a Geo Artifact until observations need independent addressing, transfer, or retention beyond caller-owned state.
- [x] D.3 Defer a shared cache until retention, freshness, provider terms, authorization reuse, and invalidation are independently specified.
- [x] D.4 Defer a Geo service until credential isolation, global rate limiting, scheduling, recovery, or deployment becomes independently operated.
- [x] D.5 Defer a provider registry until dynamic discovery and independent provider installation become real requirements.
