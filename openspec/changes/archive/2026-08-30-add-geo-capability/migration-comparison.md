# Geo Capability Migration Comparison

## Scope

This comparison covers coordinate conversion, reverse geocoding, nearby-place
lookup, provider routing, reuse, effect accounting, and the newly accepted
Plan-owned enrichment path. The AI Album baseline remains historical evidence, not
a runtime or design authority.

## Comparison

| Capability or quality | Classification | Evidence and consequence |
| --- | --- | --- |
| WGS84 and GCJ02 conversion | `preserved` | MediaSense retains explicit datum conversion and reports both input and provider datum. |
| AMap address and nearby POI lookup | `preserved` | The adapter retains the one-request combined legacy path for PreCheck and adds operation-aware address-only or nearby-only calls for the shared capability. |
| Google reverse and nearby lookup | `preserved` | The adapter retains the two-request legacy composition and adds independently callable components with separate outcomes. |
| Provider and language continuity in ordered PreCheck batches | `preserved` | PreCheck continues to persist route-observation dependencies and restore reused prefixes. |
| Hidden singleton or cross-caller routing state | `intentionally_changed` | Routing context is explicit and request-scoped for the shared family, preventing Plan and PreCheck calls from influencing each other. |
| Per-file cache identity | `intentionally_changed` | PreCheck keeps dependency-aware Work reuse; the public Geo Tool has only an effect-idempotency journal and does not treat cached place data as current truth. |
| Default network behavior | `intentionally_changed` | Provider work is refused until exact inputs and the effect envelope are authorized. Credentials or provider availability never imply permission. |
| Provider fallback | `preserved` | Bounded fallback remains available, but it cannot exceed the authorized providers, request count, cost, data classes, or retention. |
| Failure and partial-result semantics | `intentionally_changed` | Missing, failed, partial, refused, unavailable, cancelled, and indeterminate outcomes remain distinguishable instead of collapsing into an absent `gps_resolved` value. |
| Logical query and provider request accounting | `intentionally_changed` | The new contract separates logical operations, actual provider requests, and billable units or `unknown`. |
| Credential exclusion | `preserved` and strengthened | Credentials remain adapter-private and are excluded from identities, results, logs, stage evidence, and journal records. |
| Plan-owned live Geo enrichment | `not_comparable` | AI Album mixed geographic enrichment into its pipeline. MediaSense adds an explicitly authorized Plan evidence path while retaining epistemic separation and immutable PreCheck Results. |
| Final location and organization judgment | `intentionally_changed` | Provider output remains candidate evidence; the Agent and Human own interpretation and confirmation. |

## Regression judgment

No known legacy Geo capability is intentionally removed. PreCheck continues to
exercise its existing combined provider path, datum handling, fallback, rate
limiting, ordered continuity, reuse, and effect reporting. The new public path adds
stricter authorization, replay, isolation, and failure semantics.

Environment-dependent live-provider accuracy, quota behavior, and switching
quality remain outside deterministic local acceptance. They require an explicitly
authorized smoke evaluation and do not block the zero-network test suite.
