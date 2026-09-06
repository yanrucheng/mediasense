---
id: "spec-260830-2034-geo-query"
title: "MediaSense Geo Query Tool Contract"
type: spec
status: active
created: 2026-08-30
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: ""
depends-on:
  - "design-260830-1527-reusable-capability-architecture"
  - "design-260830-1626-geo-capability-evolution"
superseded-by: ""
---

# MediaSense Geo Query Tool Contract

## Purpose and status

`mediasense.geo.query` returns challengeable geographic candidate observations for
exact coordinates. It offers a high-level `resolve_place` operation and bounded
`reverse_geocode` and `nearby_places` operations without transferring stage
selection, Plan interpretation, or Human authorization into the Tool.

This is the active, stage-neutral Geo Tool contract. PreCheck calls it after local
media-aware compression and owns the resulting per-Source-Item Result projection.
A Plan Agent may call it directly for bounded investigation when prepared evidence
needs scrutiny. The Tool does not own either stage's selection, interpretation, or
handoff state.

## Operations

| Operation | Purpose | Does not decide |
| --- | --- | --- |
| `resolve_place` | Obtain the least expansive useful place candidate and applicable continuations; when both nearby bounds are supplied, obtain address and bounded nearby-place components in the same authorized request | Final location, album name, grouping, or evidence sufficiency |
| `reverse_geocode` | Inspect normalized address and administrative components | Whether the address is the intended venue |
| `nearby_places` | Inspect bounded nearby-place candidates | Which candidate is correct or worth using |

Lower-level operations remain provider-neutral. They do not expose raw HTTP,
coordinate-conversion algorithms, AMap fields, or Google fields.

An unbounded `resolve_place` keeps the progressive default and returns a separately
authorizable nearby-place continuation. Supplying both `radius_meters` and
`max_places` explicitly expands that same operation: the request fingerprint and
effect envelope then cover both address and nearby-place acquisition. A Provider
may satisfy both components with one external request when its API returns them
together; separate Provider requests remain separately counted. The supplied
radius and result count are hard upper bounds. A versioned Provider profile may
use a narrower effective radius or result count, but never exceed the authorized
bounds.

For the current adapters, one expanded coordinate costs at most one AMap request
or two Google requests. If both Providers are authorized for fallback, the
request-wide hard ceiling therefore reserves at most three Provider requests per
logical coordinate; actual effects report only requests that were sent. A single
Provider request that supplies both components is recorded as a `resolve_place`
attempt, while the returned evidence remains two separately statused components.

## Authorization and effects

Without matching trusted authority, an effectful request returns
`authorization_required` and performs zero provider requests. The proposed
authorization binds:

- exact normalized subjects and coordinates;
- operation, locale, and route context;
- transmitted data classes;
- allowed providers and fallback;
- logical-query, provider-request, and billable-unit ceilings; and
- retention scope.

Changing any bound dimension invalidates the authorization. A continuation reuses
subject identity and prior evidence but does not inherit permission for a larger
effect.

Subject order is not part of the canonical effect identity. Each coordinate in a
batch begins from the request's route context, so inserting or reordering another
coordinate cannot silently alter its Provider/language semantics.

Missing authority and non-matching authority are distinct but both effect-free.
Missing authority returns `authorization_required`; non-matching authority returns
the same actionable outcome with an `authorization_mismatch` qualification and a
fresh proposed envelope. A Human refusal is not inferred by this Tool: the calling
stage records that decision and stops before invocation.

Only coordinates, datum, locale, and provider-required lookup controls may cross
the provider boundary. Media, renditions, embeddings, prompts, paths, filenames,
captions, and general metadata are rejected before network access.

Every coordinate supplies `datum` explicitly. Required references and locales must
contain a non-whitespace character. Neither JSON Schema `default` annotations nor
runtime parsing silently supply a missing datum.

## Result meaning

Results distinguish `success`, `partial`, `no_result`,
`authorization_required`, `unavailable`, `failed`, `indeterminate`, and
`cancelled`. Each requested evidence component separately distinguishes
`success`, `no_result`, `failed`, `indeterminate`, and `not_requested`.

The result reports logical queries, observed provider requests, billable units or
`null` when unknown, transmitted data classes, provider attempts, coordinate datum,
fallback, qualifications, and applicable continuations. Provider candidates remain
observations; absence means no candidate was returned under this request, not that
no place exists.

## Replay and lifecycle

An effectful request is admitted to a Tool-owned journal before provider access.
Once admitted, an identical `request_id` and effective request returns the recorded
terminal result without another authorization prompt or Provider request. If a
caller also supplies authority it must match the original binding; changed input
or explicit conflicting authority is an error. If completion cannot be
established, replay remains `indeterminate` and does not automatically repeat the
effect.

The journal is execution evidence, not a shared geographic cache or place-truth
store. Callers own retention and projection of accepted observations.

## Provider replacement

AMap, Google Maps, or another adapter may be selected within the authorized
envelope. Compatible replacement preserves normalized operation meaning,
authorization enforcement, outcome distinctions, provenance, request accounting,
and continuation behavior. Provider order, routing algorithms, transport, and
coordinate-conversion methods are not permanent contract.

## Files

- [`geo-query.tool.json`](geo-query.tool.json) — callable input and output contract.
- [`geo-query.mock.json`](geo-query.mock.json) — authorization-required,
  authorization-mismatch, success, partial, and continuation examples.
