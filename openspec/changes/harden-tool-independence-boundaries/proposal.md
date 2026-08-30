## Why

The current public contracts and runtimes leave several stage boundaries unverifiable: Geo input validation differs between schema and code, PreCheck Geo wording is contradictory, Apply does not validate the complete Frozen Plan contract, Source Set completeness can be asserted by an arbitrary caller, the Plan-to-Apply handoff requires private-path knowledge, and Apply Read may leak internal exceptions. These gaps permit individually passing stages to compose into an unsafe or ambiguous product flow.

## What Changes

- Reconcile all current Geo wording around zero egress by default, PreCheck Run-scoped frozen-batch reverse geocoding, Plan-owned authorized enrichment, caller-owned refusal, independent stage state, and Apply's no-Geo boundary.
- **BREAKING**: reject whitespace-only Geo `subject_ref` and `locale` values at the JSON Schema boundary; keep `datum` explicitly required and remove the runtime's implicit `WGS84` fallback.
- Require Apply preparation to validate the complete Frozen Plan schema, supported encoding profile, content identity, and final-confirmation binding before any filesystem effect.
- Provide one repository-owned deterministic Source Set expander over the public `mediasense.precheck.read` boundary, fail closed on incomplete or inconsistent traversal, and use it in production Apply composition while retaining injectable fakes only for tests.
- **BREAKING**: replace Apply forward preparation's `frozen_plan_path` input with the complete Frozen Plan object returned by Plan seal, so composition requires neither a private Plan path nor an invented locator protocol.
- Convert Apply Read failures into schema-valid public error envelopes instead of leaking `ReceiptError`.
- Add a no-network public-boundary E2E from sealed PreCheck Result through Plan seal to Apply prepare, plus focused contract, negative, and adversarial tests.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `geo-capability`: align strict input semantics and distinguish missing/mismatched authorization from caller-recorded Human refusal.
- `precheck-confirmed-geocoding`: clarify Run-scoped frozen-batch authorization, permitted coordinate-only egress, and stage-owned evidence lifecycle.
- `plan-agent-workflow`: clarify Plan-only additional Geo acquisition and caller-owned refusal without changing Plan interpretation authority.
- `plan-working-state`: make the successful seal payload a directly consumable Frozen Plan handoff and preserve Plan-owned Geo evidence boundaries.
- `apply-stage-runtime`: require complete Frozen Plan validation, trusted Source Set expansion, object handoff, structured Read errors, and the no-Geo Apply boundary.
- `apply-skill-workflow`: describe the direct Plan-seal handoff and schema-valid error/recovery behavior visible to the Agent.

## Impact

- Contracts and schemas under `docs/spec/` for Geo, Frozen Plan, Plan Work, Apply Run, and Apply Read.
- Current OpenSpec specifications and stage Skills for PreCheck, Plan, and Apply.
- Geo request parsing and conformance tests.
- Apply preparation, Source Set expansion, Tool adapters, Receipt reading, and cross-stage integration tests.
- Foundation, stage ownership, reusable-capability/Geo designs, Plan local-artifact design, and README guidance.
- No AI Album or Hong Kong fixture mutation, real provider call, paid API, real media move, new public Tool, registry, service, or plugin system.
