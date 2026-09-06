## 1. Shared Geo capability

- [x] 1.1 Restore the provider-neutral Geo values, operations, routing, Tool contract, and public runtime/MCP discovery.
- [x] 1.2 Restore trusted MCP elicitation and reject caller-authored Geo authority.
- [x] 1.3 Restore the durable effect journal and enforce request-wide logical-query, Provider-request, billable-unit, data-class, Provider, and retention ceilings.
- [x] 1.4 Make request identity and per-coordinate route seeding independent of subject order and other coordinates.

## 2. PreCheck acquisition and projection

- [x] 2.1 Replace the private adaptive-geocoder dependency with the shared `GeoQueryTool` instance.
- [x] 2.2 Feed all completed bundle candidates into Geo acquisition while keeping adaptive visual groups out of the equivalence decision.
- [x] 2.3 Split bundle candidates conservatively on local coordinate, datum, time, and movement evidence; apply exact-coordinate deduplication afterward.
- [x] 2.4 Preserve every located Source Item in the outcome mapping and project a per-item Result observation without exposing acquisition mechanics as a Plan responsibility.
- [x] 2.5 Derive PreCheck confirmation from the exact pending Geo Tool request and its enforced envelope.

## 3. Reuse and migration

- [x] 3.1 Remove previous-Work and membership dependencies from reusable Geo observation identity.
- [x] 3.2 Add local compatibility reuse for successful 0.7.1 observations whose coordinate, profile, refresh, and language semantics match.
- [x] 3.3 Supersede unexecuted legacy chain Work without discarding successful historical observations.
- [x] 3.4 Restore the Dataset Geo store declaration, advance the manifest to version 3, and migrate supported version 1 and version 2 manifests atomically.

## 4. Plan boundary

- [x] 4.1 Keep `mediasense.plan.work` free of Provider execution and Geo lifecycle state.
- [x] 4.2 Document direct `mediasense.geo.query` use for bounded Plan-local investigation while requiring a successor PreCheck for missing Result coverage.
- [x] 4.3 Keep the immutable PreCheck Result unchanged by Plan-local queries and record only material Plan judgment or request references.

## 5. Contracts and documentation

- [x] 5.1 Synchronize canonical and packaged Tool contracts, PreCheck/Plan Skills, foundation, reusable-capability architecture, and Dataset workspace documentation.
- [x] 5.2 Record the AI Album migration comparison as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`.
- [x] 5.3 Record current-Run read-only evidence and clearly distinguish facts, inferences, risks, and evidence that would reopen the design.

## 6. Verification

- [x] 6.1 Cover same-asset sharing, stationary bundle compression, movement/time conflict splitting, exact deduplication after unit formation, and per-item projection.
- [x] 6.2 Cover stable Work/request identity, legacy observation reuse, hard budget enforcement, idempotent replay, cancellation, and zero-effect preflight.
- [x] 6.3 Cover seven-Tool runtime/CLI/MCP discovery, trusted Geo elicitation, contract parity, and Dataset manifest migration.
- [x] 6.4 Run focused and full unit/contract suites, Ruff, strict OpenSpec validation, and clean-wheel resource verification without live Provider requests.
  - Full suite: 610 passed, 16 deselected.
  - Ruff and strict OpenSpec validation passed.
  - A clean 0.7.1 wheel installed and passed the distribution smoke.
  - Read-only production analysis preserved the paused Run and made no Provider request.

## 7. Address and nearby-place regression repair

- [x] 7.1 Extend the existing `resolve_place` request with an explicitly bounded
  address-and-nearby mode while preserving the unbounded Plan-oriented
  continuation behavior.
- [x] 7.2 Make AMap satisfy both components with one `extensions=all` request and
  make Google account separately for reverse and nearby requests.
- [x] 7.3 Persist separate component outcomes and qualifications in the existing
  PreCheck place observation and project them to every covered Source Item.
- [x] 7.4 Include nearby bounds in Work/request identity and reuse only legacy
  `amap-google-address-poi-v1` observations that prove complete compatible
  semantics.
- [x] 7.5 Pass focused and full tests, Ruff, strict OpenSpec validation, clean
  wheel verification, and final worktree audits without a live Provider request.
  - Focused Geo/PreCheck suite: 82 passed.
  - Full suite: 624 passed, 16 deselected.
  - Ruff and strict OpenSpec validation passed.
  - A clean 0.7.1 wheel installed and passed the offline distribution smoke.
  - Read-only production-copy analysis retained 225 logical queries, reused 98
    compatible complete observations, left 127 pending, and disclosed a
    381-Provider-request hard ceiling without touching the paused Run.
