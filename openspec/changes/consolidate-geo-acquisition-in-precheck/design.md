# Design: Compressed PreCheck Geo Acquisition Through a Shared Capability

## Context

The current Run contains 2,136 media items, 241 bundle candidates, 200 adaptive
visual-compression groups, 1,838 located Source Items, and 1,611 exact coordinate
queries. The Run is paused before authorization and has sent no Provider request.
The large query set is not evidence that bundling is absent: the orchestrator
builds bundles first, but Geo later consumes all metadata and GPX Work without the
bundle relation.

AI Album demonstrates useful local compression through same-asset association and
temporal shooting chains. It also demonstrates the danger of promoting that
method into a rule: a transitive 60-second chain produced bundles as large as 201
items and 322 seconds. MediaSense therefore preserves the capability but changes
the decision boundary.

Two earlier corrections produced opposite regressions. Representative-only Geo
left many Source Items without an outcome; all-coordinate Geo restored coverage
but discarded PreCheck compression. This design fixes both by separating coverage
from acquisition.

## Purpose and ownership

The purpose anchor is: PreCheck performs the least reusable and controlled local
and external work that can prepare sufficient facts for every Source Item.

The ownership anchors are:

- PreCheck Result owns the authoritative per-Source-Item location outcome.
- PreCheck owns media/bundle interpretation, acquisition-unit selection, query
  freezing, Run confirmation, cache reuse, and Result projection.
- `mediasense.geo.query` owns stage-neutral Provider access, routing, effect
  limits, request accounting, and effect idempotency.
- Plan consumes per-item Result facts. It may call the same Geo Tool for bounded
  Plan-local investigation, but cannot mutate the Result or repair missing
  PreCheck coverage.
- MediaSense is authoritative for these contracts. AI Album is migration evidence
  only and is never a runtime dependency.

## Data flow

```text
Source Items + metadata + GPX
            │
            ▼
     bundle candidates
            │  candidate scope only
            ▼
 local consistency split ── movement/conflict/missing time ──► smaller units
            │
            ▼
 exact-coordinate request deduplication + compatible Work reuse
            │
            ▼
 frozen bounded resolve_place request
            │  exact Human authorization + hard request ceiling
            ▼
 address + nearby-place observations
            │
            ▼
 per-Source-Item outcome projection in immutable PreCheck Result
            │
            ▼
 Plan reads item facts; optional targeted Geo query is separate Plan work
```

For example, 30 photos of one table taken in ten seconds still yield 30 Result
outcomes. If their bundle and coordinates support a stationary capture, PreCheck
may acquire one observation and project it 30 times. If the same temporal chain
moves along a street, local coordinate evidence splits it before any Provider is
called.

## Decisions

### 1. Bundle candidates seed Geo units; visual compression groups do not

Bundle candidates preserve same-stem/sidecar associations and local temporal
adjacency, so they are useful candidate scopes. They are not accepted wholesale.
Within each bundle, PreCheck first keeps same-asset relationships together where
their coordinates agree, orders timed assets, and uses a complete-link spatial
consistency check so a transitive walking chain cannot grow without bound. Missing
time is shared only within the deterministic same-asset association. Datum or
coordinate conflict splits the unit.

The current implementation uses a 15-metre maximum pairwise diameter and a
120-second maximum span for non-identical coordinates. These are versioned method
choices, not product invariants. A stronger local movement model may replace them
without changing the Result or Geo Tool contracts. Exact equal coordinates may
still deduplicate after units are formed because they produce the same Provider
input regardless of media relationship.

Adaptive compression groups optimize a visual review frontier toward a target
count. They can join items for reasons that do not establish location equivalence,
so they are not used directly as Geo acquisition units.

### 2. Coverage and queries are distinct

The coverage set contains every Source Item with a selected final coordinate. The
query set contains the smaller acquisition-unit representatives after local
compression and exact-input deduplication. A deterministic medoid chooses an
actual member coordinate; no synthetic coordinate is invented. The projection
maps the returned observation Work to every member while each Source Item retains
its own coordinate and its own Result outcome.

The immutable Result never asks Plan to reconstruct bundle membership, cache
hits, routing, or request counts in order to know a photo's place outcome.

### 3. PreCheck calls the public Geo Tool

There is one Provider execution boundary. PreCheck constructs one pending,
bounded `resolve_place` request with `caller_state` retention and calls
`mediasense.geo.query` first without authority. The returned request fingerprint
and effect envelope become the existing PreCheck Run confirmation. After trusted
Human confirmation, PreCheck converts that authority to the Tool's exact
authorization and invokes the same request.

The bounds expand `resolve_place` to request distinct `reverse_geocode` and
`nearby_places` components under that one identity. Unbounded `resolve_place`
retains the Plan-oriented address-first behavior and separately authorized
continuation. AMap may satisfy both expanded components from one `extensions=all`
request; Google records its reverse and nearby requests separately.
The current PreCheck profile sets upper bounds of 500 metres and 30 candidates;
the AMap and Google adapters retain their narrower characterized provider limits.
These bounds and adapter methods are versioned policy, not product invariants.

The Tool journal records an indeterminate result before execution and a terminal
result afterward. A lost response is replayed without another Provider call.
Cancellation prevents later coordinates from starting. The authorized envelope
caps the entire batch's logical queries, Provider requests, data classes, Provider
set, retention, and known or unknown billable units.

### 4. Observation identity excludes order and membership

Reusable place-observation Work identity contains normalized coordinate, operation,
nearby bounds, locale, effective Provider/routing profile, and refresh policy. It
does not contain the previous Work ID, input position, bundle ID, or Source Item
membership.
Provider routing starts from the same request context for every coordinate, so
batch order cannot silently alter a coordinate's semantics.

Successful legacy observations may be copied into the stable identity without a
Provider request only when coordinate, legacy profile, refresh policy, and
language are compatible. Legacy pending chains are superseded rather than
executed. Old immutable Results are never rewritten.

### 5. Plan may investigate but cannot repair PreCheck

Plan's normal input remains the immutable, Plan-ready Result. If it believes one
prepared grouping is too broad, the Agent may select a small set of coordinates
and call `mediasense.geo.query` under a separate exact authorization. The Tool
returns candidate evidence, not a grouping decision. Plan records only the
material judgment or request reference it needs.

If a located Source Item lacks a Result outcome, Plan rejects or reopens PreCheck.
It does not use an ad hoc Geo call to make an incomplete Result appear complete.

### 6. Dataset state declares the Geo journal

The Geo effect journal has its own persistence lifecycle and therefore its own
Dataset store entry. Manifest version 3 declares `geo: 1`. Supported version 1
and version 2 manifests migrate atomically; existing private stores and immutable
Results are not rewritten.

## Failure semantics

| Condition | Owner | Consequence |
| --- | --- | --- |
| no final coordinate | PreCheck | no Geo outcome required |
| no compatible Provider | Geo Tool / PreCheck | Run fails before authorization |
| authority absent | PreCheck Run | paused; zero Provider requests |
| authority mismatches request | Geo Tool | authorization required; zero effect |
| address and nearby place succeed | Geo Tool / PreCheck | one complete observation projected per covered Source Item |
| nearby place returns no result | Geo Tool / PreCheck | explicit executed `no_result`; never confused with `not_requested` |
| address succeeds but nearby place fails | Geo Tool / PreCheck | explicit partial outcome and qualification after bounded fallback |
| Provider no-result/failure | Geo Tool | explicit per-component and per-item missing/failed outcome |
| transmitted effect becomes uncertain | Geo Tool journal | indeterminate result; no automatic replay |
| Run cancellation | PreCheck | completed query Work retained; later calls stop |
| missing projected outcome | Result validator | Result is not Plan-ready |

## Migration comparison

| Capability | Classification | Judgment |
| --- | --- | --- |
| same-stem, RAW/JPG/sidecar association | `preserved` | reused as a local candidate scope |
| temporal shooting-chain compression | `preserved` | retained, then checked for stationary consistency |
| one representative per legacy bundle | `intentionally_changed` | unsafe for moving or conflicting bundles |
| per-located-item Result coverage | `regression` in the first MediaSense correction, now repaired | every located item receives an outcome |
| all exact coordinates become queries | `regression` in the second correction, now repaired | coverage no longer determines request cardinality |
| adaptive visual groups as Geo units | `not_comparable` | their optimization objective is visual review, not location equivalence |
| order-dependent reverse-geocode Work chain | `regression`, now repaired | identity is stable per coordinate and policy |
| address without historical nearby-place evidence | `regression`, now repaired | bounded PreCheck resolution restores both components without changing Plan's default progressive call |
| public stage-neutral Geo Tool | `preserved` from the earlier MediaSense capability design | PreCheck and Plan can both call it |

## Risks and controls

- A local stationary heuristic can still cross a real address boundary. The
  conservative complete-link bound limits this; Result outcomes remain candidates,
  and Plan can request targeted Geo evidence when the distinction matters.
- Refusing all near-coordinate sharing would regress to GPX interpolation fan-out.
  Treating every bundle as one unit would reproduce AI Album over-merging. Tests
  cover both sides.
- A Provider or language policy change can invalidate cache compatibility. The
  stable Work descriptor includes the effective policy; the legacy bridge accepts
  only the explicitly characterized old default and Chinese-language results.
- Final-coordinate arbitration remains upstream of Geo acquisition. The current
  GPX producer does not also match an adopted track when embedded GPS is available,
  so this change detects movement and conflicts among selected final coordinates
  but does not claim to detect disagreement between embedded GPS and GPX. Adding
  that comparison requires an explicit coordinate-candidate/arbitration contract;
  it must not be hidden inside the shared Geo Tool or its request deduplication.
- The Geo journal is an effect ledger, not a second location-truth store. PreCheck
  Work remains the reusable observation cache; Result remains the stage handoff.

## Verification

Tests cover same-asset sharing, stationary bursts, moving chains, time and datum
conflicts, exact deduplication after unit formation, per-item projection,
order-independent Work identity, legacy cache reuse, no-provider behavior,
authorization mismatch/decline, cancellation, hard request ceilings, Tool replay,
MCP elicitation, AMap one-request address/POI resolution, Google two-request
resolution, component-level partial/no-result semantics, manifest migration,
contract parity, and zero real network use.

Read-only evaluation against the paused Hong Kong Run must remain separate from
execution. The current algorithm yields 225 queries for 1,838 located Source
Items (down from 1,611 exact-coordinate queries). All 144 historical successes
remain semantically addressable; 98 are selected by the compressed set, leaving
127 pending queries and a 381-Provider-request hard ceiling for complete
address-and-POI acquisition with both current adapters. The Run remains paused
and no Provider attempt was made.

## Open Questions

None that block this implementation. Spatial and temporal thresholds are internal
versioned methods and should be changed only with evaluation evidence, not exposed
as Plan or product invariants.
