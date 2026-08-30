# Change: Add a Stage-Neutral Geo Capability

## Why

MediaSense has a reusable reverse-geocoding kernel and a safe PreCheck integration,
but no Agent-facing geographic capability. The current `lookup` boundary combines
address lookup, nearby-place lookup, provider fallback, and stateful routing, while
the current Plan contract requires every missing place observation to be produced
upstream.

The Human has accepted a future Plan behavior in which the Agent may request live,
coordinate-only Geo enrichment under exact bounded authorization. That behavior
needs one stage-neutral capability contract before either stage can reuse it safely.

## What Changes

- Add one `geo-capability` contract with a high-level `resolve_place` operation and
  bounded `reverse_geocode` and `nearby_places` continuations.
- Require effect preflight and authorization binding for exact normalized inputs,
  permitted egress, provider constraints, request and cost ceilings, and retention.
- Normalize candidate observations, component outcomes, provider attempts,
  uncertainty, and logical/request/billable accounting without exposing
  provider-native response schemas.
- Refactor the current Geo kernel into provider-neutral values, ports, composition,
  and explicit AMap and Google Maps adapters with request-scoped routing state.
- Preserve PreCheck ownership of coordinate selection, frozen batches,
  confirmation, Work lifecycle, reuse, cancellation, and Result projection.
- Permit Plan to acquire Geo observations through a Plan-owned adapter, retain them
  in Plan Working State, and show their provenance in preview without changing the
  immutable PreCheck Result.
- Keep Apply outside Geo and defer a Geo Skill, shared cache, Geo Artifact,
  provider registry, and independent service until separately justified.

## Capabilities

### New Capabilities

- `geo-capability`: Provides authorization-bound, provider-neutral geographic
  candidate observations with progressive evidence and observable effects.

### Modified Capabilities

- `plan-agent-workflow`: Allows bounded live Geo enrichment instead of requiring
  every missing place observation to reopen PreCheck.
- `plan-working-state`: Retains Plan-owned Geo observations separately from the
  bound PreCheck Result, Agent judgment, and Human confirmation.
- `plan-review-preview`: Presents material Plan-owned Geo evidence and provenance
  without performing network work during rendering.

The public PreCheck and Apply contracts are unchanged.

## Impact

- Adds a new capability family under `src/mediasense/capabilities/geo/` and retains
  compatibility imports while callers migrate from `src/mediasense/geo.py`.
- Adds one public Geo Tool contract only after both PreCheck and Plan exercise the
  accepted boundary end to end.
- Adds Plan-owned Geo integration and persistence without reading or mutating
  PreCheck private state.
- Changes the Plan Skill only after deterministic Tool and Working State behavior
  exists.
- Adds provider conformance, authorization, continuation, concurrency, stage
  isolation, contract, and end-to-end tests. Tests use fakes and do not make live
  provider requests.
- Introduces no filesystem organization effects, media egress, public provider
  Tools, plugin registry, shared mutable cache, or independently operated service.
