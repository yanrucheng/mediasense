## 1. Contract and ownership alignment

- [x] 1.1 Reconcile foundation, stage ownership, Geo/PreCheck/Plan/Apply designs, README, current specs, and stage Skills with the confirmed Geo ownership and egress boundary.
- [x] 1.2 Align the Geo Tool JSON Schema and runtime on explicit datum, non-whitespace identifiers/locales, authorization mismatch, and caller-owned Human refusal.
- [x] 1.3 Add bidirectional Geo input/output conformance tests covering success, error, and zero-effect authorization preflight.

## 2. Frozen Plan trust boundary

- [x] 2.1 Extract stage-neutral Frozen Plan schema, encoding-profile, identity, and confirmation validation without changing the published contract.
- [x] 2.2 Make Apply preparation validate the complete Frozen Plan before Run creation or filesystem probing.
- [x] 2.3 Add regression tests for schema-forbidden fields, unknown encoding profiles, recomputed digests, and confirmation mismatch.

## 3. Trusted Source Set expansion

- [x] 3.1 Extract a stage-neutral deterministic Source Set resolver over the public PreCheck Read boundary and migrate Plan to it.
- [x] 3.2 Wire production ApplyRunTool composition to the trusted resolver while retaining the lower-level injected seam only for tests.
- [x] 3.3 Test all five Source Set forms, exact Result binding, reference types, duplicate/incomplete traversal, cursor progress, and adversarial under-expansion.

## 4. Cross-stage handoff and Read errors

- [x] 4.1 Replace Apply forward `frozen_plan_path` input with the complete Frozen Plan object returned by Plan seal and register the external schema reference at runtime.
- [x] 4.2 Convert every Apply Read validation, lookup, cursor, filter, page, and segmented-ledger failure into a schema-valid public error envelope.
- [x] 4.3 Update Apply and Plan Skills, formal Tool contracts, mocks, and focused tests for the direct handoff and error semantics.

## 5. Public-boundary acceptance

- [x] 5.1 Add a temporary, no-network PreCheck Result → Plan create/update/seal → Apply prepare E2E through public Tool boundaries.
- [x] 5.2 Prove invalid schema/profile rejection precedes effects, Source Set expansion cannot be caller-shrunk in production, error envelopes validate, and Apply performs no Geo work.
- [x] 5.3 Run focused tests, the full default non-live suite, OpenSpec strict validation, Ruff, diff hygiene, and documentation frontmatter/index/link checks.
- [x] 5.4 Leave the completed change active and unarchived for Human review; do not commit.
