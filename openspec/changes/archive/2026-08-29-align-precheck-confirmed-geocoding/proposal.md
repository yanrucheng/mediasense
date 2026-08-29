## Why

PreCheck is intentionally local-first rather than absolutely offline. Existing
documents and the implemented Run checkpoint already allow one narrow external
capability—post-compression coordinate reverse geocoding—but residual absolute
offline wording can cause later Agents to remove it or bypass its authorization
boundary.

## What Changes

- State one consistent boundary across Foundation, stage ownership, Run,
  implementation, and operator-facing documentation: external work is disabled
  by default, with confirmed coordinate-only reverse geocoding as the sole
  current exception.
- Require compression to finish before the runtime freezes and deduplicates the
  coordinate query set.
- Require an automatic Run pause that displays the exact number of pending
  logical queries. Authorization is bound to that set and must be renewed when
  it changes.
- Retain provider route, fallback, failure, actual provider-request count, and
  cost observability in Work and the immutable Result.
- Keep media bytes, renditions, embeddings, prompts, and general metadata out of
  this exception. No remote model or general networking permission is added.

## Capabilities

### New Capabilities

- `precheck-confirmed-geocoding`: Defines the allowed post-compression
  coordinate lookup, its confirmation boundary, observable effects, reuse, and
  zero-call paths.

### Modified Capabilities

None. The repository has no prior OpenSpec capability; this change records and
aligns the already approved product decision.

## Impact

Affected authorities are the MediaSense Foundation, PreCheck stage-ownership
and reference documents, the PreCheck Run Contract, the implementation design,
README guidance, and the migration ledger. Runtime impact is limited to the
existing shared geo adapter, reverse-geocode producer, Run confirmation state,
and Result execution-boundary projection. No real provider call is part of this
change's verification.
