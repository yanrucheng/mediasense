---
id: "spec-260826-1546-precheck-read"
title: "MediaSense PreCheck Read Contract"
type: spec
status: active
created: 2026-08-26
updated: 2026-08-29
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260825-2235D-precheck-compression-boundary"
  - "clarify-260826-1819-precheck-contract-concepts"
superseded-by: ""
tags: ["mediasense", "precheck", "tool-contract", "read-access"]
---

# MediaSense PreCheck Read Contract

## Decision

Plan reads one exact immutable PreCheck Result through the read-only Tool `mediasense.precheck.read`. The contract fixes the smallest semantics needed to begin cheaply, account for every item in the declared boundary, inspect material limits, trace compression in the directions required by downstream work, and progressively expand existing evidence.

The Tool does not expose SQLite, caches, hashes, working-run state, thumbnails, embeddings, clusters, or algorithms. Those remain replaceable PreCheck implementation details.

The contract has four addressable kinds:

- `result`: one immutable PreCheck delivery;
- `dataset`: the continuing business subject whose contents may change over time;
- `source_item`: one concrete source object accounted by this Result;
- `evidence`: content Plan can inspect directly as part of the compressed delivery.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumer exists. The earlier `collection`, `source_state`, and `representation` draft vocabulary is replaced directly; compatibility aliases, adapters, and deprecated fields are prohibited.

## Interface

Every request includes:

- `result_ref`: the exact immutable Result, never an implicit `latest`;
- `action`: `inspect` or `traverse`;
- optionally `target`: an opaque reference inside that Result; `inspect` uses `kind` to disambiguate the requested object, while `traverse` omits redundant `kind` when relation and direction already determine the origin type; omission means the Result itself;
- for `traverse`, one relationship, one direction, and optional pagination;
- only for outbound `accounts_for`, optional `filter.attention_only: true`.

`inspect` returns the target's minimal stable fields. `traverse` returns a page whose outer record states `origin`, `relation`, and `direction`; members return only `target` and fields specific to that member. Relationship records have no independent ID and do not repeat `type/from/to` per member.

## Result and entity fields

| Kind | Required | Optional when meaningful |
| --- | --- | --- |
| Result | `ref`, `dataset_ref`, `coverage`, `readiness`, `integrity`, `execution_boundary` | `qualifications` |
| Dataset | `ref` | `name`, attributed `context`, `qualifications` |
| Source Item | `ref`, `locator` | `observations`, `qualifications` |
| Evidence | `ref`, `access` | `observations`, `qualifications` |

`kind` remains the discriminator for `inspect` targets and returned object views, where several entity types share the same field position. Relationship origins and targets omit it when the selected relation and direction already determine the type; only `derived_from` and `expands_to` members retain a typed reference because either a Source Item or Evidence may be returned.

`dataset_ref` is a required Result field, not a duplicated relationship. Dataset identity may be referenced across Results. Each Source Item locator carries its own `source_root_ref` and a path relative to that root. This supports Results that account for one or multiple roots without exposing an absolute path or turning Dataset identity into a location; an explicitly unverified rebind receives a different root reference. A Dataset may expose a mutable current-discovery view elsewhere, but each Result accounts immutably for its own Source Items. Dataset context returned through this Tool is the immutable view bound to that Result; later context changes affect only later Results. Source Item references, Evidence references, and cursors are scoped to that exact Result.

`execution_boundary` is part of the Result view because consumers cannot inspect
private package fields. A local-only Result reports zero network and billable
effects. If the confirmed post-compression coordinate exception ran, this view
reports the authorization records, exact logical-query count, actual provider
request count, providers, and known or unknown billable-call count. It never
authorizes media, rendition, embedding, prompt, or general-metadata egress.

A Source Item reference is stable within its Result. Its runtime locator combines an opaque `source_root_ref` with a root-relative path; neither Dataset identity nor Source Item identity is an absolute path. The contract does not require permanent identity across Results. Implementations may recognize moved but unchanged media and reuse valid work without elevating a particular fingerprint or matching method into identity.

An eligible Source Item may carry a `source_content_verification` observation.
When available, its value contains a named `profile`, opaque verification
`value`, exact `size_bytes`, `observed_at`, and producer identity. The first
supported profile is `sha256-full-v1`, whose value is prefixed `sha256:`. The
profile is replaceable; it is neither the Source Item identity nor a permanent
promise that SHA-256 is the only supported method. PreCheck revalidates every
included observation at seal. Source Items that are excluded, unsupported,
invalid, erroneous, unresolved, or not selected for exact proof need not carry
one; their accounting must still remain explicit.

Plan freezes only the exact `result_ref` and selected `source_item_ref` values,
not a copied digest. Apply resolves those references through this Tool, safely
binds the locator's `source_root_ref`, and verifies current bytes immediately before each
authorized file operation. An unknown profile, absent observation, unsafe root
binding, size mismatch, or verification mismatch blocks that operation. This
contract does not create a Dataset-wide snapshot, permanent Source identity, or
independent source-verification service.

Evidence access may point to a local artifact, directly reuse a Source Item, or contain inline structured content. Evidence is not source truth: it is a compressed, inspectable basis whose limits remain visible.

## Status axes

Result status uses three independent axes:

- `coverage`: `complete` or `partial`;
- `readiness`: `plan_ready` or `blocked`;
- `integrity`: `valid` or `invalid`.

`partial + plan_ready + valid` is meaningful: a Result may be explicitly limited to a declared subset yet be trustworthy and sufficient for planning within that subset. A localized invalid Source Item may also coexist with a plan-ready Result when it is accounted, its affected scope is visible, and available evidence is sufficient for the declared planning boundary.

## Relationships

Five relationship meanings are authoritative:

| Relationship | Valid outbound origin and target | Stable meaning |
| --- | --- | --- |
| `accounts_for` | Result → Source Item | The item belongs to this Result's immutable accounting boundary. Each member states `scope` and `condition`. |
| `entry_evidence` | Result → Evidence | The low-cost default surface from which Plan can begin. |
| `represents` | Evidence → Source Item | The challengeable compression claim that reading this Evidence may defer direct reading of the target Source Item. |
| `derived_from` | Evidence → Source Item or Evidence | What actually produced this Evidence. |
| `expands_to` | Evidence → Source Item or Evidence | Already-prepared detail available as the next inspection step. |

Stable traversal directions are intentionally asymmetric:

- `accounts_for`, `entry_evidence`, `derived_from`, and `expands_to` support their declared outbound direction;
- `represents` supports both outbound coverage lookup and inbound lookup from a Source Item to covering Evidence.

Other reverse traversals are not part of the contract unless a later business need justifies them. The supported inbound `represents` traversal is a reverse lookup over the same relationship, not a reverse alias.

These meanings do not collapse. For example, one representative JPEG Evidence may be `derived_from` one Source Item while it `represents` many Source Items. A video frame Evidence can be derived from and represent one video while expanding to additional frames and the source video.

`attention_items` is not a sixth authoritative relationship. It is the derived view returned by querying outbound `accounts_for` with `filter.attention_only: true`; implementations derive it from non-usable conditions or material member qualifications.

## Accounting fields

Every `accounts_for` member carries two independent dimensions:

- `scope`: `source_media`, `auxiliary`, or `excluded`;
- `condition`: `usable`, `unsupported`, `invalid`, `error`, or `unresolved`.

This permits a damaged MP4 to remain both `source_media` and `invalid`, or a GPX item to be `auxiliary` and `usable`. No discovered item disappears merely because it is unsupported, invalid, excluded from planning, or unresolved.

## Basis, observations, and qualifications

Relationship types carry their own authority; there is no universal `epistemic_state`. In particular, `represents` is always a challengeable PreCheck compression claim rather than MediaSense semantic ground truth.

A relationship page may carry shared `basis` and `qualifications`. A member repeats or overrides them only when its basis or limitation differs. Every `represents` response must make its selection or coverage basis available; other relationships provide it only when materially useful.

An observation contains:

- required `name` and `status`;
- `value` when status is `available`, plus `basis` when that value is a challengeable derivation rather than a direct fact;
- `basis` and no value when status is `failed`;
- no value for `missing`, `not_checked`, or `not_applicable`;
- optional `confidence` or qualifications only when they add real meaning.

The five statuses distinguish a present value, an absent value, a failed attempt, work not performed, and a concept that does not apply. `null` does not silently merge those states.

A qualification contains required `code`, `effect`, and human-readable `message`. It adds `basis` only when the containing object, observation, or relationship does not already provide that basis. Stable effects are `limits_interpretation` and `blocks_use`; a message with no actual effect does not become a Qualification.

## Completeness, navigation, and replacement

For a Result to claim `coverage: complete`, every Source Item in its declared boundary must be reachable through `accounts_for`, and each account must have explicit scope and condition. Separately, every accounted Source Item must be reachable from entry Evidence through `represents` or `expands_to`, or through an explicit auxiliary, excluded, unsupported, invalid, error, or unresolved exception route. This does not require one visual Evidence item per Source Item.

Plan normally starts with `entry_evidence`, follows outbound `expands_to` for existing detail, uses `represents` in either supported direction to test coverage, and queries the derived attention view when exceptions matter. This read behavior does not prescribe Plan's reasoning or VLM payload.

The Tool only returns existing immutable information. If Plan requires new evidence, corrected provenance, different coverage, or a changed compression claim, it requests a new PreCheck Result through stage routing. Mutable working state may reuse unaffected work, but the old Result is not modified.

## Consumer-ready Mock

[`hong-kong.mock.json`](hong-kong.mock.json) is a human-authored development Mock, not runtime output. It demonstrates:

1. direct Dataset inspection through `result.dataset_ref`;
2. paginated `accounts_for` and the derived `attention_items` view;
3. a low-cost `entry_evidence` surface;
4. bundle 61 as a challengeable 201-item `represents` claim;
5. expansion to outlier and boundary Evidence;
6. reverse lookup from a hidden-person Source Item;
7. distinct invalid, patched-full, and remux Source Items;
8. a readable video whose `create_date` is `missing` rather than `null` or a decode failure;
9. the independent `partial / plan_ready / valid` result axes.

Fixture-relative locators are review conveniences. The Mock does not make the local review pack, historical bundle membership, AI Album cache, or filesystem layout part of the contract.

## Conformance

[`precheck-read.tool.json`](precheck-read.tool.json) is authoritative for request and response shape. A conforming implementation must additionally satisfy the semantic rules in this document:

- all reads bind the exact `result_ref`;
- Result contents do not change after publication;
- Source Item references, Evidence references, and cursors cannot escape that Result; Dataset identity may persist across Results;
- `accounts_for` is exhaustive for a `complete` Result;
- `attention_items` is derived rather than independently authored;
- only the declared traversal directions are accepted, including inbound lookup for `represents` and no formal reverse traversal for the other relationships;
- `represents` is challengeable and has an inspectable basis;
- direct facts need not repeat inherited basis, and `kind` appears only where omission would make a reference ambiguous;
- `derived_from` and `represents` never substitute for each other;
- returned locators are local and read-only within PreCheck policy;
- no storage technology or cache record is exposed as the cross-stage authority.
