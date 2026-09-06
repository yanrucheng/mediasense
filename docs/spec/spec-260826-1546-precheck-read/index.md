---
id: "spec-260826-1546-precheck-read"
title: "MediaSense PreCheck Read Tool Contract"
type: spec
status: active
created: 2026-08-26
updated: 2026-09-04
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
superseded-by: ""
tags: ["mediasense", "precheck", "tool", "result", "review"]
---

# MediaSense PreCheck Read Tool Contract

## Decision

`mediasense.precheck.read` exposes one exact immutable PreCheck Result through
three consumer-meaningful operations plus one PreCheck diagnostic projection:

- `review` gives an Agent a bounded, comparable, loss-aware first reading of the
  Result;
- `expand` reads selected Evidence or Source Items in more detail; and
- `resolve` expands one exact Source Set without loss for deterministic Plan and
  Apply consumers; and
- `geo_summary` audits coordinate acquisition and internal query consolidation
  without becoming a Plan-stage prerequisite.

The Tool does not expose graph traversal as its public abstraction. Result
entities and relationships remain the provenance and derivation authority, but
the Tool internally composes them at the consumption granularity required by its
callers.

[`precheck-read.tool.json`](precheck-read.tool.json) is authoritative for request
and response shape. [`hong-kong.mock.json`](hong-kong.mock.json) is a compact
human-readable transcript over one Result-local slice.

## Non-goals

The Tool does not:

- recognize events, people, places, activities, themes, or memories;
- recommend an Organization Profile, group, split, order, name, or disposition;
- correct timestamps, coordinates, paths, captions, or similarity claims;
- create Plan Working State or retain an exploratory session;
- acquire new Evidence or reopen PreCheck;
- expose SQLite, tables, cache keys, private indexes, or Working Run state; or
- authorize or perform filesystem changes.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumers exist. The former public `inspect` and `traverse`
actions, their cursors, fields, errors, aliases, and adapters are removed rather
than deprecated. Clean-slate deployment is assumed.

## Authority and responsibility

The immutable PreCheck Result remains the sole authority for Result identity,
accounting, Evidence, observations, relationships, provenance, and
qualifications. `review` and `expand` are regenerable views over that authority;
they have no reference, revision, persistence, or independent lifecycle.

The Tool owns deterministic projection, pagination, exact binding, integrity
checks, response bounds, and honest failure. The Agent owns interpretation,
comparison, evidence selection, semantic grouping, naming, and deciding whether
the Result is sufficient for the user's organization purpose.

`resolve` owns only exact set materialization. It proves what a Source Set means;
it does not prove that the set is a useful organization.

## Common binding and effects

Every request names an exact `result_ref`; no operation resolves an implicit
`latest`. All four operations are immediate, read-only, local, stateless, and
safe to retry. They cause no source mutation, network access, model use, billable
call, Plan revision, or retained query state.

The Tool may use private stores or deletable indexes internally. Public meaning
must be derivable from the sealed Result. Removing an optimization cache cannot
change a response's semantics.

## `review`

`review` returns the Result trust view, a complete accounting reconciliation,
and a page of coverage cards in immutable `frontier_order`.

The reconciliation partitions every accounted Source Item into:

- `frontier_only`: represented by default entry Evidence and not exceptional;
- `exception_only`: handled by an explicit non-normal scope, condition, or
  qualification and not represented by the frontier;
- `frontier_and_exception`: represented while still materially exceptional; or
- `residual`: explained by neither route.

These four counts must sum to `accounted_total`. A Result that claims
`coverage: complete` but has residual items is inconsistent and cannot produce a
successful review.

A coverage card is anchored by an existing entry Evidence ref. It summarizes
only direct `represents` members and directly prepared `expands_to` targets. It
does not create a Coverage Region entity or silently follow an unbounded graph
closure.

Each card exposes:

- the anchor Evidence access;
- represented membership and `scope × condition` counts;
- deterministic `capture_time` and `media_type` projections;
- representative, boundary, outlier, and conflict Evidence refs;
- prepared Evidence with no assigned public role;
- material qualification counts and full qualification meanings;
- the exact observation scope projected by the card;
- available `expand` includes; and
- a Source Set expression suitable for `resolve`.

The card never reports a semantic event, suggested split, likely place, final
group, or directory name.

## `expand`

`expand` accepts exactly one selector:

- up to sixteen `evidence_refs`; or
- up to sixteen `source_item_refs`.

Evidence expansion supports:

- `anchor_evidence`;
- `prepared_targets`;
- `provenance`;
- `coverage_basis`; and
- paged `member_observations` for exactly one Evidence ref.

Source Item expansion supports:

- `source_item`;
- `observations`; and
- `covering_evidence`.

Every include is explicit. An unknown include or any reference outside the
bound Result rejects the entire request. A valid Result-recorded
`missing`, `failed`, `not_checked`, or `not_applicable` observation is returned
as data rather than upgraded into a Tool failure.

## `resolve`

`resolve` accepts one Source Set composed from:

- explicit Result-local Source Item refs;
- outbound Result `accounts_for`;
- outbound Evidence `represents`;
- one exact normalized `geo_coordinate` under the declared GPX-over-GPS rule;
- unions; and
- differences.

It returns canonical Source Item ref ordering plus compact member records:

- exact Source Item ref;
- Result-local locator;
- accounting scope and condition;
- source-content-verification observation when present; and
- material qualifications.

Every page repeats a `source_set_identity`, `membership_identity`, and total.
The membership identity covers the exact Result, canonical Source Set, and
complete ordered membership. `complete: false` is only transport continuation;
the Tool never presents an unproven partial set as resolved.

Review counts and cards cannot substitute for `resolve`. Conversely, exact
resolution proves no retrieval value or organization meaning.

## `geo_summary`

`geo_summary` is a deterministic, paged PreCheck diagnostic projection over the exact immutable
Result. It reports GPS and GPX observation states, conflicting observations, the
exact no-rounding coordinate deduplication rule, and one ordered record per unique
coordinate. Each record contains its member count and a compact Result-bound
`geo_coordinate` Source Set whose exact members are retrieved through paged
`resolve`, plus reverse-geocode outcome, Provider candidate Evidence references,
provenance, and qualifications. `not_applicable` means no Source Item had an
available final coordinate; `incomplete` identifies a Result whose located Source
Items do not all expose an outcome. Result `readiness`, not this diagnostic view,
governs Plan entry. A large same-coordinate population
therefore cannot make one `geo_summary` item exceed the response byte limit.

The operation performs no provider request and does not infer an event, a true
place, a grouping, or a directory name.

## Public projection semantics

### `capture_time`

An available capture time is an observed timestamp with an explicit UTC offset,
not corrected event time. The review projection reports every observation state
and compares available values as instants. Timezone assumptions, basis, and
qualifications remain available through expansion. The Tool does not classify an
old or unusual timestamp as wrong.

### `media_type`

An available media type is a normalized MIME type with observation provenance.
The review projection counts exact values and every unavailable state. It does
not convert media type into semantic content.

### Evidence roles

The public roles are `representative`, `boundary`, `outlier`, and `conflict`.
They describe Evidence's review function inside a coverage claim. One Evidence
may have several roles; prepared Evidence may have none. Absence of a role does
not create a fifth role, and the Tool does not assign roles while reading.

Other observation names remain open. Every card states that its projection is
limited to `capture_time`, `media_type`, and `evidence_role` and whether other
observations exist.

## Pagination and response bounds

The maximum encoded Tool response body is 524,288 UTF-8 JSON bytes. Requested
limits are upper bounds:

- `review`: default 25, maximum 100 cards;
- paged `expand`: default 50, maximum 200 member observations; and
- `resolve`: default 250, maximum 1,000 members.

The Tool stops only between complete items. `stop_reason` is `complete`, `limit`,
or `byte_limit`. A single indivisible item exceeding the response limit returns
`response_item_too_large`.

Every opaque cursor binds the Result digest, operation, normalized selector,
limit, order, and continuation position. Cursors survive process restart but
cannot cross a Result, operation, selector, include set, Source Set, or limit.

## Failure and retry

Expected failures use the common error envelope. Principal codes are:

- `invalid_request`;
- `result_not_found`;
- `result_unavailable`;
- `result_untrusted`;
- `result_inconsistent`;
- `invalid_cursor`;
- `reference_not_in_result`;
- `unsupported_include`;
- `invalid_source_set`;
- `response_item_too_large`.

Foreign and unknown references intentionally share
`reference_not_in_result`; the Tool does not reveal whether a ref exists in a
different Result.

There is no top-level partial-success outcome. Request errors and Result
integrity failures are atomic. Honest partial Result coverage, unavailable
observations, and incomplete pagination remain explicit data states. Unexpected
implementation exceptions propagate rather than becoming ordinary Result state.

Identical requests are safe to repeat after transport timeout, 429, 503, or
`result_unavailable`. `result_untrusted` and `result_inconsistent` require repair
or a new Result rather than blind retry.

## Conformance

A conforming implementation proves at least:

- exact Result binding for every operation and cursor;
- reconciliation of accounting, frontier, exception routes, overlap, and
  residual items;
- deterministic cards and public projection semantics;
- atomic validation of batched refs and includes;
- complete Source Set identity and membership across pages;
- response byte bounds without partial JSON items;
- no public SQLite, cache, or internal group identity;
- safe retry without retained read state; and
- no semantic organization decision in any response.
