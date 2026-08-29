---
id: "spec-260829-0050-apply"
title: "MediaSense Apply Contract"
type: spec
status: active
created: 2026-08-29
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
  - "spec-260826-1546-precheck-read"
  - "spec-260827-1138-frozen-plan"
  - "design-260829-0038-apply-reference-handoff"
superseded-by: ""
---

# MediaSense Apply Contract

## Decision and activation boundary

Apply has two public Tool responsibilities and two top-level business entities:

```text
mediasense.apply.run  <-> mutable Apply Run
mediasense.apply.read  -> immutable Apply Receipt
```

[`apply-run.tool.json`](apply-run.tool.json), [`apply-receipt.schema.json`](apply-receipt.schema.json), and [`apply-read.tool.json`](apply-read.tool.json) are the active contracts. [`lifecycle.mock.json`](lifecycle.mock.json) remains a Human-authored exchange example; [`receipt.mock.json`](receipt.mock.json) remains a schema-conforming reference Receipt. The examples are not runtime output, actual authorization, or evidence that their illustrative paths were changed.

Both activation dependencies have executable evidence recorded in [`../../eval/eval-260829-1350-apply-activation-evidence.md`](../../eval/eval-260829-1350-apply-activation-evidence.md):

1. each planned Source Item has an immutable Apply-grade verification basis reachable through its exact PreCheck Result; and
2. the supported cross-filesystem transfer profile proves its byte and declared filesystem-metadata preservation behavior on supported platforms.

The first production-capable `move_originals` runtime is implemented under `src/mediasense/apply/`. The contract itself never authorizes an operation: effects begin only after a trusted Human confirmation is bound to the exact prepared Run revision and content identity. Repository tests operate only on controlled temporary fixtures.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

AI Album formats, command flags, directory trees, caches, and implicit output behavior are evidence only. Compatibility aliases, format adapters, and deprecated fields are prohibited.

## Authority and boundaries

- The Frozen Plan is authoritative for logical root, relative organization, membership, output names, and accounted non-materialized outcomes.
- The exact PreCheck Result is authoritative for Result-scoped Source Items, locators, and the Apply-grade verification basis.
- The Human is authoritative for the selected real effect, source and destination bindings where needed, final execution authorization, cancellation, acceptance of an incomplete result, and a requested whole-run rewind.
- `mediasense.apply.run` is authoritative for one Run's prepared operation set, preflight, authorization binding, lifecycle, effects, recovery, verification, and Receipt publication.
- The Apply Receipt is authoritative for what actually happened. It never changes Plan semantics to match reality.
- `mediasense.apply.read` exposes one exact immutable Receipt without mutating state or re-verifying history.
- The Agent explains, routes, and escalates; it cannot supply Human authorization, invent a collision name, substitute a source, or broaden an execution effect.

## First Apply profile

The first profile is `move_originals`, corresponding to AI Album's user-valued `original` outcome. One forward Run binds:

- one complete Frozen Plan artifact;
- one current local-root binding for every `source_root_ref` used by the Result's planned Source Items;
- one destination parent beneath which the Frozen Plan's `logical_root` is materialized; and
- one deterministic prepared operation set.

The source namespace and final organization namespace must not overlap. An existing destination parent is allowed, but every final target must be absent and collision-free under the actual target filesystem's semantics.

Same-filesystem moves use non-overwriting atomic move semantics where the platform supports them. Cross-filesystem move is a distinct disclosed route: write to a non-final destination, verify content byte for byte, and preserve timestamps, permissions, extended attributes, Finder tags, and other attributes declared user-relevant by the active platform profile before publishing without overwrite. If any such attribute cannot be preserved, deletion of that source item is blocked until the exact loss is disclosed under a new prepared-content identity and receives new Human authorization. The Receipt records accepted discrepancies and their authorization binding. Content inequality is never an authorizable metadata exception. No fallback may silently change route or guarantees.

The active `cross_filesystem_user_metadata_v1` profile currently supports
Darwin APFS-to-APFS transfer and declares exact preservation of byte content and
logical length, modification and creation timestamps, POSIX mode bits, owner and
group IDs, BSD file flags, and all extended attributes including Finder tags.
Access time and metadata change time are observationally volatile and are not
preservation claims. ACL-bearing sources are unsupported by this profile until
a non-empty ACL fixture proves preservation; preparation must block rather than
silently omit such ACLs. Any declared-field difference follows the discrepancy,
new prepared identity, and new Human authorization rule above.

Copy and link remain explicit deferred profiles. A Run never combines effect profiles.

## Source compatibility gate

Path equality does not prove source identity. Before authorization and again at the individual effect boundary, Apply must resolve every planned Source Item and verify it against immutable evidence bound to the exact PreCheck Result.

The active PreCheck Read contract permits open Source Item Observations because items outside dangerous effects need not carry Apply evidence. For every Source Item selected for `move_originals`, Apply requires the exact Result-scoped view to contain:

- a `source_root_relative_path` locator with `source_root_ref` and root-relative `value`;
- exactly one `source_content_verification` observation with `status: available`;
- the supported `sha256-full-v1` profile, digest `value`, `size_bytes`, `observed_at`, and `producer`; and
- observation-level basis, with qualifications only when real limitations exist.

Apply obtains that evidence only through exact `result_ref + source_item_ref` calls to `mediasense.precheck.read`, then binds the current root and re-reads size plus full SHA-256. The contract does not require Dataset-wide snapshots, permanent identity across Results, a new Source Verify Tool, hash duplication in Frozen Plan, or exposure of PreCheck cache keys. Missing, unavailable, unsupported, mismatched, stale, escaping, rebound, or ambiguous evidence makes `prepare` block without media effects.

## Run actions

### `prepare`

`prepare` creates one durable Run from exactly one direction source:

- `forward`: a complete Frozen Plan artifact, `move_originals`, the current local-root binding for every referenced source root, and a destination parent; or
- `rewind`: one exact Receipt reference whose rewind window has not expired.

The operation is safely retryable by `request_id`. It may be long-running. Preparation resolves complete item coverage, paths, source verification, destination identity, filesystem route, capacity, permissions, collisions, namespace overlap, concurrency conflicts, metadata preservation, and journal availability without changing media.

It returns the Run identity and observed state. A later `status` supplies the authoritative ready, blocked, or current progress view.

### `status`

`status` is available in every state. It returns bounded business progress, the exact prepared revision and content identity when meaningful, decision-relevant warnings, blockers or attention reasons, verifiable recovery conditions, allowed actions, and a published Receipt summary after closure. An attribute-loss decision carries a Run-owned disclosure reference, exact discrepancy-set identity and count. The complete disclosure must be obtainable by the Human through bounded reads before authorization. Inline representation, files, pagination, and database projections are implementation methods rather than stable contract commitments.

Status never returns the complete operation ledger. That belongs to the Receipt and `apply.read`.

### `execute`

`execute` binds trusted Human confirmation to the exact `run_ref`, prepared revision, and prepared-content identity. It is safely retryable by `request_id`; request fields cannot self-assert the confirming Human. The same action is reused when a cross-filesystem copy exposes an exact user-relevant attribute loss: the source remains present, status identifies the Run-owned disclosure and new prepared revision, the Human can obtain the complete discrepancy set through bounded reads, and only a new `execute` authorization may permit deletion. `resume` cannot accept that risk.

Acceptance means execution has been durably authorized and requested, not that a file has moved or that the Run completed. Before every effect, the Tool rechecks the relevant mutable preconditions and commits through a non-overwriting boundary.

### `pause`, `resume`, and `cancel`

These controls are target-state idempotent and do not require `request_id`.

- `pause` stops issuing new item effects and lets in-flight operations reach a safe recorded boundary.
- `resume` rechecks stated recovery conditions and continues the same prepared content; it cannot change Plan, effect, source-root bindings, destination parent, target mapping, or accepted preservation loss.
- `cancel` stops future work and never automatically reverses completed effects. Before `execute`, it closes with proven zero effects and no Receipt. After `execute`, it reconciles and verifies reality, then publishes a Receipt with `closure: human_cancelled`; `completion` independently records whether all operations completed.

An accepted control response is not proof that the target state has been reached. `status` reports the observed state.

## Run lifecycle

| State | Stable meaning | Typical allowed actions |
| --- | --- | --- |
| `preparing` | No media effects are allowed; preflight is progressing. | `pause`, `cancel` |
| `ready_for_authorization` | Prepared content has no blockers and can be shown for Human confirmation. | `execute`, `cancel` |
| `blocked` | No media effects have occurred; stated external or upstream conditions prevent readiness. | `resume`, `cancel` |
| `executing` | Authorized item effects may be progressing. | `pause`, `cancel` |
| `paused` | No new item effect is being issued; durable continuation remains possible. | `resume`, `cancel` |
| `needs_attention` | Some effects may exist; safe automatic progress has stopped with explicit recovery conditions or an exact metadata-loss decision. | `resume`, `cancel`; or `execute`, `cancel` when a new Human authorization is required |
| `verifying` | No new forward effects are issued; actual outcomes and Receipt accounting are being closed. | none |
| `closed` | One immutable Receipt has been published and bound to the Run. | none |
| `cancelled` | Preparation ended before execution authorization with proven zero media effects. | none |
| `failed` | The Tool cannot establish a trustworthy closed result; possible effects and takeover limits are explicit. | none |

One localized item failure does not change `executing` to `failed`; independent safe work continues, then the Run enters `needs_attention` if unresolved items remain. A process crash is not a public state: restart reconciles durable intent with observed source and destination facts.

Once `execute` is accepted, every ordinary terminal path publishes a Receipt, even if zero items completed. The exceptional `failed` state exists only when trustworthy accounting or Receipt publication cannot be recovered and must never be presented as completion.

## Operation and recovery invariants

- Journal intent is durable before its file effect; observed outcome is durable before the next dependent effect.
- Repetition never creates a second effect for a completed item.
- An existing target is recognized as prior completion only when it matches the exact operation verification basis and the source is absent.
- Two active Runs cannot mutate overlapping sources or final targets.
- A media container may be invalid yet safely movable as bytes; Apply follows the Frozen Plan rather than reclassifying it.
- Source and target aliases, symlinks, hard links, mount boundaries, case folding, Unicode normalization, path limits, and reserved names are checked under actual filesystem semantics.
- Apply-created directories are effects. Rewind removes only directories created by the original Run that remain empty and unchanged.
- Cross-filesystem content must verify byte for byte. A user-relevant attribute discrepancy blocks deletion of that source item unless the exact discrepancy set is bound to a new prepared revision and Human authorization; any changed or additional discrepancy invalidates that authorization.
- Mutable Run state and Receipt publication state remain available independently of the source and destination volumes.

## Receipt semantics

The immutable Receipt binds the exact Run, Frozen Plan, prepared content, Human authorization, effect, current filesystem bindings, preflight, complete operation accounting, observed postconditions, content and metadata-preservation verification, exact unpreserved attributes, any reauthorization that accepted them, recovery, created directories, resource facts, and its own integrity seal.

Operation accounting partitions the planned operation set into exactly one result per item. `complete` requires every planned item to be completed and verified. A Human may cancel with residual items; the Receipt remains explicitly incomplete and lists every exception.

A Receipt carries or binds an immutable operation ledger containing each Source Item's original resolved location, intended target, actual result, attempt facts, and verification conclusion. It may represent a large success set compactly as the deterministic planned set minus explicit exceptions, or use immutable physical segments. These representations remain one logical Receipt. Preservation discrepancies remain exact, addressable Receipt facts even when the ordinary success ledger is compact.

The Receipt records a rewind deadline, not an eternal claim that rewind is currently safe. Rewind creates a new Run over the original Receipt's actual completed set and passes through the same preflight and Human authorization boundary. Both Receipts remain immutable.

[`apply-receipt.schema.json`](apply-receipt.schema.json) constrains the active encoding. Semantic closure, set equality, target uniqueness, operation-ledger coverage, digest verification, source/target observation consistency, and rewind eligibility require checks beyond JSON Schema.

## Receipt read semantics

`mediasense.apply.read` has two actions:

- `inspect` returns the bounded summary for one exact `receipt_ref`; and
- `traverse` reads a bounded page from `operations`, `exceptions`, `metadata_discrepancies`, or `created_directories`, optionally narrowed by an exact Source Item or operation result where applicable.

Cursors bind the Receipt, section, filter, order, and page position. A later page cannot silently switch to another Receipt or query. Storage segment names are not exposed as business references.

## Idempotency, concurrency, and publication

- `prepare` and `execute` require `request_id`. Same ID plus the same request returns the same logical result; the same ID plus different content reports `idempotency_conflict`.
- Control operations converge on their target state and can be repeated safely.
- A prepared revision is opaque and used only for equality binding. Any material re-preparation produces another revision and content identity and invalidates prior authorization.
- Receipt publication is non-overwriting and recoverable. A verified Receipt package written before the Run close transition is a pending publication of that same Receipt, not a second result.

## Errors

The Tool contracts use structured errors. The minimum owned classes are invalid request, missing or untrusted Plan/Receipt/Result, source-unverifiable, target conflict, source-target overlap, unsupported filesystem semantics, insufficient capacity or permission, metadata-preservation loss requiring authorization, invalid state, revision conflict, idempotency conflict, concurrency conflict, access denied, operation failure, and receipt-integrity failure.

Messages and recovery hints are evidence, not authorization. Errors that can resume must state a verifiable recovery condition. An indeterminate effect is never collapsed into a generic failure.

## Local persistence boundary

The minimum local shape has one durable mutable Run authority and one immutable Receipt authority:

```text
<apply-store>/
├── work.sqlite3
└── receipts/
    └── <receipt-artifact>/
        ├── receipt.json
        └── <optional immutable operation segments>
```

The current runtime uses this layout, but it is not a portable contract. Table shape, journal encoding, file extension, segment threshold, locking, flush strategy, and garbage collection remain replaceable. The stable requirements are independent survival from media-volume loss, complete recovery semantics, independently readable Receipts, and no competing journal authority.

## AI Album migration disposition

Preserved capabilities include original-media movement, complete bundle expansion, logical hierarchy materialization, basename preservation, explicit existing destination parents, complete source-to-target preparation, efficient directory creation, concurrency as a quality property, same-filesystem rename, and observable progress.

Intentional changes include collision refusal instead of automatic parent-name injection, explicit target authorization instead of an implicit unique output, explicit verified cross-filesystem transfer instead of silent copy-delete fallback, non-overwriting publication, per-item outcome accounting, durable restart, post-verification, and immutable Receipt publication.

Thumbnail/summary preview is preserved outside Apply in Plan. Copy and relative-link effects remain deferred and cannot be claimed as delivered. Combining multiple effect profiles in one Run is intentionally unsupported.

## Acceptance and ongoing verification

Apply is a high-risk filesystem and concurrency boundary. The active profile is maintained by:

- fast schema and semantic model tests for lifecycle transitions, authorization identity, set closure, compact accounting, idempotency, and pagination;
- temporary-filesystem integration tests for non-overwriting same-filesystem moves, source/target aliases, directory effects, pause/cancel, and recovery reconciliation;
- deterministic fault injection at every journal/effect/publication boundary, without real sleeps;
- a platform/filesystem matrix proving byte-for-byte cross-filesystem verification and declared preservation behavior for timestamps, permissions, extended attributes, Finder tags, and any additional user-relevant attributes;
- a separate slow scale suite for 100,000-item preparation, status, Receipt publication, read pagination, restart, and memory bounds; and
- representative throughput and metadata-preservation comparison with AI Album before broadening migration claims.

Mocks must not replace real filesystem integration where atomicity, overwrite behavior, durability, or metadata preservation is the risk under test.

## Activation record and reopening rule

The contract became `active` after the following conditions were met:

1. the Source Item verification profile and access path are formally owned upstream and exercised by the Apply reference;
2. the fixed cross-filesystem byte and user-relevant-attribute guarantee is supported by representative platform evidence, including the block-and-reauthorize loss path;
3. the Run and Receipt schemas plus mocks pass structural and semantic conformance checks;
4. the lifecycle and every material fault window have an unambiguous observable outcome and continuation; and
5. the migration ledger distinguishes delivered behavior from deferred copy/link profiles.

Reopen activation if the accepted PreCheck projection changes incompatibly, supported filesystem evidence is invalidated, a material fault window loses a trustworthy recovery outcome, or complete Receipt accounting can no longer be produced. Do not reopen the two-entity model merely because the database, journal, hashing method, concurrency strategy, filesystem API, CLI text, or artifact sharding changes.
