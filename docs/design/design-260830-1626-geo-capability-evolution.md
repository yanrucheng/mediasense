---
id: "design-260830-1626-geo-capability-evolution"
title: "MediaSense Geo Capability Evolution"
type: design
status: active
created: 2026-08-30
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: ""
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235B-stage-ownership"
  - "design-260830-1527-reusable-capability-architecture"
superseded-by: ""
---

# MediaSense Geo Capability Evolution

## Status and accepted direction

This document applies the active reusable-capability architecture to geographic
lookup. It records the accepted product direction that a future Plan workflow may
perform live, coordinate-only Geo enrichment when the exact request and its
effects have been authorized.

This is the active Geo capability design. The public
[`mediasense.geo.query`](../spec/spec-260830-2034-geo-query/) contract and the
`mediasense.plan.work` `enrich_geo` integration implement the accepted direction.
An unconfigured runtime still reports the capability as unavailable and performs
no provider request.

## Purpose

The Geo capability turns one exact coordinate or a bounded coordinate set into
provider-derived, challengeable geographic observations. It gives a caller the
least expensive and least expansive useful evidence first, then exposes bounded
ways to request more detail.

The capability does not decide:

- what event, album, or semantic group a coordinate belongs to;
- which place name should appear in an organization plan;
- whether geographic evidence is sufficient for a Plan decision;
- which source items should be queried; or
- whether a Human accepts the privacy, cost, or provider trade-off.

Those decisions remain with the caller, Agent, and Human according to the owning
workflow.

## Product scenario

Given a PreCheck Result containing the coordinate `31.1434, 121.6579` but no place
observation, a future Plan Agent may ask for a place candidate.

```text
Plan Agent
└── resolve_place(31.1434, 121.6579)
    ├── no matching authority
    │   └── authorization_required
    │       ├── exact normalized input and fingerprint
    │       ├── logical-query count
    │       ├── permitted coordinate-only egress
    │       ├── provider constraints
    │       ├── maximum requests and cost information
    │       └── retention proposal
    │
    └── matching Human or standing-policy authority
        └── candidate observation: "Shanghai Disneyland area"
            ├── sufficient for this Plan decision
            │   └── Agent stops and interprets the evidence
            └── insufficient or conflicting
                └── bounded continuation: nearby_places
                    ├── already authorized → execute
                    └── larger effect envelope → request new authorization
```

The candidate does not become a factual place name merely because a provider
returned it. Plan records the observation, the Agent's interpretation, and any
Human confirmation as distinct information.

## Gate 1 review fixture

This fixture is a semantic example for Human review, not a proposed wire schema.

### Starting state

```text
Exact PreCheck Result
└── one relevant Source Item
    ├── coordinate: 31.1434, 121.6579 (WGS84)
    ├── place observation: absent
    └── qualifications: no online-map lookup was authorized in PreCheck

Plan Working State
├── candidate group: one Shanghai trip
├── candidate name: "Shanghai 2026"
└── unresolved question:
    "Would a recognizable venue make the group name materially better?"
```

The absence of a place observation does not mean that no place exists. It means
only that the exact PreCheck Result supplies no provider-derived place evidence.

### Accepted path

```text
1. Plan Agent chooses resolve_place for the one coordinate
   └── reason: a venue could materially improve the proposed name

2. Geo Tool performs no network request
   └── authorization_required
       ├── 1 logical query
       ├── coordinates + datum + locale may leave the device
       ├── permitted providers and fallback are shown
       ├── maximum provider requests are shown
       ├── known cost is shown; otherwise cost is "unknown"
       └── Plan-local retention is shown

3. Human authorizes that exact request
   └── authorization is bound to the normalized request fingerprint

4. Geo Tool executes resolve_place
   └── result
       ├── candidate: "Shanghai Disneyland area"
       ├── provider attempt and actual request evidence
       ├── qualifications and uncertainty
       └── continuation: nearby_places

5. Plan Agent judges the high-level candidate
   ├── enough for the current decision
   │   └── proposes a name without further Geo effects
   └── not enough because several venues are plausible
       └── requests the nearby_places continuation

6. Geo Tool evaluates the continuation
   ├── existing authority covers its effect → execute
   └── effect is larger → return the exact authorization delta first

7. Plan records distinct information
   ├── Geo observation and provenance
   ├── Agent interpretation: "the photos likely concern Disneyland"
   ├── proposed organization name
   └── Human confirmation or correction
```

The Plan preview may show the candidate and its basis. The Frozen Plan contains
the confirmed organization decision required by Apply; Apply neither repeats the
lookup nor needs access to provider credentials.

### Refusal path

```text
Human declines coordinate egress
├── Geo Tool reports refused with zero provider requests
├── Plan records no provider-derived place observation
└── Plan Agent chooses among:
    ├── continue with a less specific name
    ├── ask the Human for a place directly
    └── leave the location unresolved
```

Refusal is a supported outcome. It does not become `no_result`, a provider
failure, or permission to send another coordinate.

### Review questions

Gate 1 is accepted only if the Human agrees that:

- this bounded lookup is legitimately Plan-owned evidence expansion;
- the disclosed information is sufficient to make the authorization decision;
- nearby-place escalation is understandable and does not inherit broader
  authority silently;
- Plan keeps provider observation, Agent judgment, and Human confirmation
  distinct; and
- refusal leaves a useful Plan path instead of forcing an unsafe workaround.

## Current baseline

The current implementation has the following responsibility structure:

```text
PreCheck
└── ReverseGeocodeProducer                       stage adapter
    ├── selects representative coordinates from PreCheck Work
    ├── deduplicates and freezes the query set
    ├── binds Human confirmation to its fingerprint
    ├── owns Work retry, reuse, cancellation, and projection
    └── calls
        └── src/mediasense/geo.py                shared kernel
            ├── normalized coordinate and result values
            ├── coordinate conversion
            ├── HTTP transport
            ├── adaptive provider composition
            └── provider adapters
                ├── AMap
                └── Google Maps

Plan
└── reads existing qualified place evidence from the PreCheck Result

Apply
└── has no geographic lookup responsibility
```

The shared kernel does not read PreCheck, Plan, Apply, SQLite, Work, confirmation,
or Result state. The PreCheck producer correctly owns stage selection,
authorization, lifecycle, persistence, and projection.

The kernel is not yet a public capability contract:

- one `lookup` combines address lookup, nearby-place lookup, language routing,
  and fallback;
- AMap and Google perform materially different request combinations behind the
  same operation;
- adaptive provider and language state persists across coordinates;
- routing policy directly names current providers and regional rules;
- no callable boundary validates an effect authorization; and
- results do not expose bounded continuations.

## Responsibility allocation

| Responsibility | Owner |
| --- | --- |
| Decide why geographic evidence is needed | Calling Agent and workflow |
| Select source subjects and coordinates | Stage adapter |
| Approve coordinate egress, provider constraints, cost, and retention | Human or governing policy |
| Bind authorization to an exact normalized request | Stage adapter and Geo Tool boundary |
| Choose a provider within the authorized envelope | Geo capability policy |
| Convert coordinates and invoke provider APIs | Geo provider adapters |
| Normalize provider responses and preserve provenance | Geo capability |
| Judge grouping, naming, and evidence sufficiency | Plan Agent |
| Persist PreCheck Work and Result evidence | PreCheck |
| Persist Plan-local enrichment and judgment | Plan |
| Perform filesystem organization | Apply, from a Frozen Plan only |

The stage adapter establishes that the call is relevant and authorized in its
workflow. The Geo Tool independently enforces that the submitted operation,
inputs, provider constraints, egress, request ceiling, and retention do not exceed
that authorization.

## Target capability tree

```text
Human or governing policy
└── authorizes an exact effect envelope
    │
    ├── PreCheckGeoAdapter
    │   ├── frozen post-compression coordinate batch
    │   ├── PreCheck Work lifecycle
    │   └── immutable Result projection
    │
    └── PlanGeoAdapter
        ├── coordinates selected from one exact PreCheck Result
        ├── Plan-owned authorization binding
        └── Plan-private candidate observation
            │
            ▼
Geo Tool family
├── resolve_place                              high-level default
│   └── continuations
│       ├── reverse_geocode                    address evidence
│       └── nearby_places                      nearby POI evidence
├── effect guard
├── normalized observation model
├── request-scoped routing context
├── provider-neutral routing policy
└── provider ports
    ├── AMap adapter
    ├── Google Maps adapter
    └── future adapters without contract changes
```

There is one Geo Tool family because these operations share a purpose, authority
envelope, provider effects, provenance model, and failure semantics. Providers are
not public Tools. Coordinate conversion and HTTP transport remain implementation
details.

## Agent-facing operations

### `resolve_place`

`resolve_place` is the ordinary entry point. It returns place candidates and the
evidence that qualifies them. It may use address or nearby-place observations only
within the authorized envelope.

It does not return a final Plan location judgment. A result may state that no
additional capability-level evidence is currently available, but only the calling
Agent decides whether the evidence is sufficient for its task.

### `reverse_geocode`

`reverse_geocode` returns normalized address and administrative-area observations
for an exact coordinate. It is useful when the high-level summary is insufficient
or the caller needs to inspect the address basis directly.

### `nearby_places`

`nearby_places` returns normalized nearby-place observations under an explicit
radius and result bound. It is a separate caller-visible operation because it can
change provider support, request count, billable work, returned detail, and the
interpretation of absence.

### Operations not activated initially

Provider comparison is expressed through authorized routing and provenance, not a
public provider-specific operation. `inspect_attempts` remains unnecessary while
attempt evidence fits in the ordinary result. It becomes an operation only if
attempt detail acquires an independent retained reading lifecycle.

## Invocation and authorization

Preflight, authorization, and execution are phases of each effectful operation,
not separate Agent-facing business operations.

When authority is absent or insufficient, the operation performs no network
effect and returns `authorization_required` with:

- the normalized input fingerprint;
- the requested operation and subject count;
- exact logical-query count;
- permitted data classes, which initially contain coordinates, datum, and locale
  only;
- allowed provider constraints and fallback ceiling;
- maximum provider requests and known cost or quota information;
- retention scope; and
- the exact delta from any authority already supplied.

The caller may obtain Human confirmation or apply an explicit standing policy and
then continue the same operation with authority bound to that fingerprint. Any
change in input, operation, provider allowance, egress, request ceiling, cost, or
retention invalidates the binding.

A continuation reuses the original subject identity and evidence. It does not
inherit permission for a larger effect. For example, exposing already-returned
address components is read-only, while making a new nearby-place request may
require additional authorization.

## Effect boundary

The first public Geo Tool must enforce:

- network access is disabled without matching authority;
- only normalized coordinates, datum, requested locale, and provider-required
  request controls may leave the local boundary;
- source media, renditions, embeddings, prompts, paths, filenames, captions, and
  general metadata cannot enter provider requests;
- automatic fallback stays within the authorized provider, request, cost, and
  retention envelope;
- credentials never enter request identity, results, logs, stage state, or cache
  identity; and
- cancellation prevents new requests but does not misreport requests already sent.

An unknown billable effect or a timeout after request transmission is reported as
unknown or indeterminate, never as zero.

## Result semantics

A result distinguishes:

- `success`: all requested evidence components completed;
- `partial`: at least one requested component produced usable evidence and another
  did not complete;
- `no_result`: the completed request produced no matching observation;
- `refused`: the proposed effect exceeded authority or policy;
- `unavailable`: no permitted provider could perform the operation;
- `failed`: no usable result was produced and failure is known; and
- `indeterminate`: completion or external effect cannot be established safely.

Each requested evidence component separately reports `success`, `no_result`,
`failed`, or `not_requested`. This prevents an address success from concealing a
nearby-place failure and prevents an unrequested lookup from appearing to have
returned no results.

Every result includes, when material:

- exact normalized subject coordinates and datum;
- requested operation and locale;
- normalized candidate observations;
- provider attempts in order;
- provider-specific input datum without provider-native response fields;
- logical operations, actual provider requests, and billable units as distinct
  quantities;
- fallback, partial failure, timeout, and uncertainty;
- observed effects and retention; and
- bounded continuations that remain applicable to the same subject.

Provider results are observations that may be incomplete, stale, disputed, or
wrong. They are not final location truth.

## Multiple-provider boundary

Each provider adapter declares supported operations, coordinate and locale
requirements, data egress, request-count semantics, quota or cost information,
normalization guarantees, and failure mapping.

The capability uses an explicit composition root for the initial AMap and Google
Maps adapters. It does not introduce a dynamic registry or plugin platform.

Provider routing is selected from operation requirements and caller constraints.
Provider identifiers remain diagnostic provenance, not permanent product policy.
Automatic fallback may change implementation method but cannot widen authorized
effects.

The internal provider port may allow a provider to efficiently fetch multiple
evidence components in one request. That optimization does not permit the adapter
to request, retain, or expose an evidence component outside the caller's authorized
operation. Tool operations remain stable even when provider request shapes differ.

## State, reuse, and concurrency

Routing state becomes immutable and request-scoped before the capability is exposed
as a public Tool. Concurrent Plan and PreCheck calls must not influence one
another's provider or language route.

PreCheck continues to own its Work-based reuse and sequence dependencies. Plan
owns any Plan-local observation reuse. Neither caller reads or mutates the other's
database, Work records, confirmation state, or cache.

No shared persistent Geo cache is introduced initially. A future shared cache must
first establish independent retention, freshness, provider-terms, authorization,
and invalidation semantics. A cache hit never proves current geographic truth and
does not retroactively authorize the original provider request.

The public Tool does require a minimal operation journal because an authorized
provider call may be billable. The journal binds `request_id`, effective request,
authorization, execution state, and terminal result so an identical retry can
recover the original outcome instead of silently repeating an effect. It is Tool
execution state, not a geographic cache or source of place truth. Reusing a
`request_id` with different effective input is refused.

## Stage integration

### PreCheck

PreCheck retains ownership of representative-coordinate selection,
post-compression batch freezing, exact logical-query confirmation, Work lifecycle,
reuse, cancellation, and Result projection. Migration to a Geo family port must
preserve the current public PreCheck contract and evidence.

### Plan

Plan may eventually call the Geo Tool only through a Plan-owned integration that:

1. starts from one exact, valid PreCheck Result;
2. selects only coordinates relevant to the current Plan question;
3. obtains authority for the frozen Geo request;
4. persists the returned observation separately from PreCheck facts, Agent
   judgment, and Human confirmation;
5. records the evidence used in preview and revision; and
6. never mutates the PreCheck Result or reads PreCheck private storage.

Activating this path requires an explicit change to the current Plan workflow and
Skill, which currently prohibit Plan-stage reverse geocoding.

### Apply

Apply has no Geo integration. A Frozen Plan already contains the decisions Apply
must execute, and Apply may not acquire new semantic evidence.

## Local topology after activation

The package structure is created only when implementation work begins and the
separate responsibilities exist:

```text
src/mediasense/capabilities/geo/
├── __init__.py          exported internal or public family surface
├── model.py             normalized request, observation, and outcome semantics
├── protocol.py          provider and routing ports
├── service.py           provider-neutral composition and effect accounting
├── tool.py              only when the public Tool contract is accepted
└── providers/
    ├── __init__.py
    ├── amap.py
    └── google_maps.py

src/mediasense/precheck/geocode.py
└── PreCheck-owned selection, authorization, Work, and Result projection

src/mediasense/plan/geo.py
└── Plan-owned selection, authorization binding, and evidence persistence
```

The current `src/mediasense/geo.py` is migrated rather than duplicated. Temporary
compatibility imports may exist during migration, but provider implementations do
not fork between stages.

## Delivery gates

### Gate 0: product direction — accepted

The Human accepts future Plan-owned, live, coordinate-only Geo enrichment under
explicit bounded authorization. This acceptance does not activate the behavior.

### Gate 1: human-reviewable Plan scenario — accepted

The accepted review fixture above shows the complete path from a valid PreCheck Result with
a coordinate but no place observation through authorization, high-level lookup,
optional nearby-place continuation, Plan evidence storage, Agent interpretation,
preview, and refusal.

Acceptance requires that the scenario demonstrates a Plan decision that can
materially improve without reopening all of PreCheck and that refusal remains a
usable outcome.

### Gate 2: capability contract — accepted

Review the operations, authorization binding, normalized results, partial outcomes,
provider conformance, continuation behavior, and compatibility promise. The public
contract must not expose current Python classes, provider-native fields, routing
algorithm, cache layout, or filesystem layout.

### Gate 3: internal family boundary — accepted

Move provider-neutral values, ports, adapters, and composition behind the family
boundary. Adapt PreCheck without changing its public behavior. Prove that no family
module reads stage-private state and that concurrent calls do not share mutable
routing state.

The family remained `candidate_family` until the Plan consumer passed Gate 4.

### Gate 4: Plan integration and Tool activation — accepted

Implement the Plan adapter and one real end-to-end Plan consumer. Activate one Geo
Tool family only after the reusable-capability acceptance tests pass for both
PreCheck and Plan.

### Gate 5: Skill decision — no Geo Skill

Do not create a Geo Skill with the first Tool version. Collect real Agent traces
and workflow fixtures. A Geo Skill becomes justified only when recurring domain
judgment about evidence sufficiency, nearby-place escalation, provider conflict,
and stopping is useful beyond one stage workflow and can evolve independently.

### Gate 6: optional entities — deferred

Independently reassess an attempt-detail read operation, Geo Artifact, shared
cache, provider registry, or service only when it gains its own responsibility,
authority, or lifecycle. None is part of the current target.

## Acceptance evidence

The future Tool cannot become active until tests demonstrate:

1. a high-level request returns usable candidate evidence without requiring the
   caller to understand provider APIs;
2. insufficient or conflicting evidence exposes only applicable bounded
   continuations;
3. a continuation cannot widen input, egress, provider, request, cost, or retention
   authority silently;
4. AMap, Google Maps, and a fake adapter satisfy the same normalized semantics;
5. provider fallback and per-component partial failure remain observable;
6. logical operations, actual requests, and billable units remain distinct;
7. media and non-coordinate metadata cannot cross the provider boundary;
8. credentials cannot enter identity, results, logs, or persisted stage evidence;
9. concurrent stage calls cannot influence one another's routing state;
10. PreCheck and Plan retain separate mutable state and projection authority;
11. current PreCheck behavior remains compatible through migration; and
12. identical request replay does not repeat provider effects, while a conflicting
    `request_id` is refused; and
13. a real Plan workflow, not only mocks, uses the accepted boundary.

## Explicit non-goals

This evolution does not introduce:

- a universal shared-utility Skill;
- one public Tool per provider;
- a public coordinate-conversion Tool;
- a provider registry or plugin platform;
- a shared mutable PreCheck/Plan Geo database;
- a permanent cache, hash, routing algorithm, provider order, or directory layout
  contract;
- automatic acceptance of a provider result as a Plan location decision; or
- any Geo responsibility in Apply.

## Review outcome

The current implementation remains:

```text
src/mediasense/geo.py                 shared_kernel + provider_adapters
src/mediasense/precheck/geocode.py   stage_adapter
Geo Agent-facing family              candidate_family
```

The Plan path and the preserved PreCheck path now exercise the shared family under
separate stage ownership. The Tool contract is active; a separate Geo Skill,
Artifact, cache, registry, or service remains unjustified.
