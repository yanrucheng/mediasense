---
id: "design-260829-0038-apply-reference-handoff"
title: "MediaSense Apply Reference Handoff"
type: design
status: review
created: 2026-08-29
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "index-design"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
  - "spec-260827-1138-frozen-plan"
  - "design-260828-2043-plan-local-artifacts"
  - "clarify-260828-2255-apply-stage-flow"
superseded-by: ""
---

# MediaSense Apply Reference Handoff

## Purpose and current status

This package is the Human-authored reference that pressure-tested the Apply workflow before activation. The resulting Run, Receipt, and Read contracts are now active, and the first `move_originals` runtime implements the same boundary. This package remains `review` because its examples are explanatory fixtures rather than runtime authority.

- [`lifecycle.mock.json`](../../spec/spec-260829-0050-apply/lifecycle.mock.json) demonstrates prepare, Human-bound execute, a localized failure, resume, verification, and Receipt publication.
- [`receipt.mock.json`](../../spec/spec-260829-0050-apply/receipt.mock.json) demonstrates immutable operation accounting and short-window whole-run rewind support.

Both files are Human-authored review evidence. They are not runtime output, actual authorization, proof that the referenced files were moved, or an active contract.

## Reference boundary

The example reuses the seven-item Frozen Plan from [`../design-260828-2043-plan-local-artifacts/example-plan.json`](../design-260828-2043-plan-local-artifacts/example-plan.json). Its Plan identity, content identity, scope, logical root, group paths, and output names are existing review facts.

The following are explicit illustrative assumptions needed to exercise Apply:

- `/Volumes/Archive/Inbox` is the currently selected Dataset parent and `/Volumes/Archive` is the selected destination parent;
- both are on the same writable filesystem;
- all seven current source objects are illustratively assumed to have sufficient immutable verification evidence;
- no final target exists before execution;
- source locators for items not exposed by the current PreCheck development Mock are placeholders; and
- the failure and retry of `source-item:217` are simulated.

The example itself cannot prove current source identity. That proof now comes from the accepted PreCheck `source_content_verification` observation and Apply's real Result-scoped consumer tests.

## User-visible walkthrough

The Agent asks Apply to prepare an `original` move from the exact Frozen Plan. Preparation performs no media mutation. The user sees one summary:

```text
7 planned items; 7 sources verified; 7 unique final targets
same-filesystem atomic move; 0 blockers; 1 non-blocking media-readability warning
destination parent /Volumes/Archive
resolved organization root /Volumes/Archive/Media
```

The user confirms this exact prepared content. Execution moves four items, encounters a localized read failure for `source-item:217`, and continues the other two safe items. The Run then reports six completed and one unresolved. After the source becomes readable again, resume revalidates and moves only that item. Verification closes the operation and publishes one immutable Receipt.

If the user requests rewind during the retained window, Apply creates a new reverse Run from the Receipt's actual completed set, rechecks all current conditions, displays a new impact summary, and obtains new Human authorization. The original Receipt remains unchanged.

## Stable responsibilities demonstrated

### Apply Run

The mutable Run owns:

- exact Frozen Plan or Receipt rewind source;
- selected effect and current source/destination bindings;
- deterministically resolved operation coverage;
- preflight, blockers, warnings, and prepared-content identity;
- exact Human authorization binding;
- progress, localized failures, pause/resume/cancel, recovery, and verification; and
- atomic publication of one final Receipt when any file effect may have occurred.

### Apply Receipt

The immutable Receipt owns:

- binding to the Run, Frozen Plan, prepared content, authorization, and actual target;
- complete planned-versus-actual operation accounting;
- final source and destination observations with risk-appropriate verification;
- metadata-preservation profile, exact unpreserved attributes, any Human reauthorization that accepted them, retries, recovery facts, and created-directory effects; and
- the promised rewind window and links to later reverse runs or receipts.

### Regenerable views and internal mechanisms

The impact summary, progress display, and metadata-loss disclosure are views over the Run. A discrepancy disclosure must be complete, bounded to consume, content-identity-bound, and obtainable by the Human before authorization. Inline values, files, pagination, and database projections are replaceable implementation methods. The journal, checkpoints, locks, temporary paths, task scheduling, concurrency, and physical Receipt shards are also implementation mechanisms. None is an additional cross-stage authority.

## Tool boundary

The example supports two Tool responsibilities:

```text
mediasense.apply.run
  prepare | status | execute | pause | resume | cancel

mediasense.apply.read
  inspect | traverse
```

`prepare` accepts exactly one direction source: a Frozen Plan for forward execution or an Apply Receipt for whole-run rewind. Preflight and execution remain in one Run so the exact checked content can be bound to Human authorization and rechecked at each effect boundary.

`apply.read` exists because a Receipt can cover hundreds of thousands of operations and outlives its mutable Run. It exposes an immutable summary and bounded traversal without exposing storage shards.

The active contract and runtime use these operation names. No Preview Tool, Confirm Tool, Rewind Plan, Source Snapshot, or Source Verify Tool is justified.

## Closed source-binding boundary

PreCheck Read exposes each applicable Result-scoped Source Item with a `source_root_relative_path` locator and an available `source_content_verification` observation. Apply consumes the exact `result_ref + source_item_ref`, binds the locator to the Human-supplied current root, and verifies size plus full SHA-256 before authorization and again at the effect boundary.

The evidence remains owned by the exact PreCheck Result. Apply supports `sha256-full-v1` without copying hashes into Frozen Plan, exposing cache keys, creating a Dataset-wide snapshot, or promising permanent identity across Results. Other profiles may be added deliberately without changing the authority boundary.

Apply refuses execution when:

- the current source cannot be verified to the required strength;
- a locator resolves ambiguously or escapes its authorized source binding;
- two logical locators resolve to one object in a way that changes planned effects; or
- the verified source state changes before the individual effect is committed.

## Minimal local persistence

Apply needs two authoritative local lifecycles and no third one:

```text
<apply-store>/
├── work.sqlite3
└── receipts/
    └── <receipt-artifact>/
        ├── receipt.json
        └── <optional immutable operation segments>
```

- `work.sqlite3` is the authoritative home for mutable Apply Runs, prepared-content identities, Human authorization bindings, idempotency records, operation intent and observation checkpoints, concurrency reservations, progress, and recoverable Receipt publication.
- Each artifact under `receipts/` is one immutable Apply Receipt. `receipt.json` owns identity, summary, accounting closure, references, verification conclusion, and discovery of any immutable operation segments.
- Small Receipts may store their complete operation ledger in `receipt.json`. Large Receipts may use immutable segments. This is one logical Receipt, not a manifest entity plus child Receipt entities.
- The store must be available independently of the mutable source and destination volumes. Disconnecting either media volume cannot erase the facts needed to stop or recover safely.

The journal is the subset of mutable Run information needed to reconcile an effect after interruption. It has no independent user authority or cross-stage lifecycle, so it remains inside the Run store. A separate `journal.json`, per-operation public directory, mutable Receipt, or copied Frozen Plan is not justified.

Receipt publication follows a recoverable result-oriented boundary:

1. stop starting new effects and finish or reconcile in-flight effects;
2. complete operation accounting and post-verification in the durable Run;
3. write a new immutable Receipt package without overwriting an existing artifact;
4. verify the package identity and completeness;
5. bind that exact `receipt_ref` to the Run terminal transition; and
6. on interruption, reconcile the verified package and Run state rather than publish a second Receipt.

SQLite, table names, journal mode, file extensions, segment encoding, sharding threshold, flush calls, and lock implementation are replaceable methods. The stable requirement is one durable mutable Run authority, one independently consumable immutable Receipt authority, non-overwriting publication, and deterministic recovery between them.

## Safety and concurrency conclusions

- Collision checks use the target filesystem's real comparison semantics, including case and Unicode behavior, not string equality alone.
- Every final destination publication is non-overwriting even when state changes after preflight.
- Concurrent Runs cannot mutate overlapping source objects or final targets.
- The first profile rejects overlapping source and final-output namespaces; in-place reorganization needs a separate reviewed recovery model.
- Same-filesystem move preserves the expected atomic rename effect where supported.
- Cross-filesystem move is a distinct disclosed path: copy to a non-final target, verify content byte for byte, and attempt to preserve timestamps, permissions, extended attributes, Finder tags, and any other declared user-relevant attributes before non-overwriting publication.
- If any user-relevant attribute cannot be preserved, deletion of that source item remains blocked. The Run discloses the exact item, attribute, expected value, and observed value, binds that discrepancy set into a new prepared revision, and requires new Human authorization through `execute`; the original authorization cannot cover the new loss.
- After such authorization, the Receipt records the exact accepted discrepancies and their authorization binding. Without it, the source remains present and the operation cannot be `completed_and_verified`.
- Apply-created directories are accounted effects. Rewind removes only directories created by that Run that remain empty and unchanged.
- An unreadable media container can still be moved if its byte object is safely readable and the Frozen Plan already accounts for it.
- Once execution is accepted, every terminal outcome publishes a Receipt, including a zero-completion refusal or failure. An inability to publish trustworthy accounting remains an observable unsealed failure and is never reported as completion.
- Durable Run state and Receipt publication cannot depend only on either mutable media volume; a source or destination disconnect must not erase the knowledge needed for recovery.
- Recovery treats an already-present target as completed only when it matches the exact operation verification basis and the source is absent; otherwise it remains a collision or indeterminate fact.

## Deferred scope

- broader verification profiles beyond `sha256-full-v1`;
- broader cross-filesystem platforms and ACL-bearing sources beyond the proven Darwin APFS profile;
- configurable rewind-window policy beyond the current short-window profile;
- long-term garbage collection and operational packaging;
- copy and link Apply profiles; and
- CLI and Agent presentation details.

These deferred methods and future profiles do not block the active two-entity model or the Run/Read Tool split. Any broader claim requires its own executable evidence and must preserve the same authority and safety invariants.

## Contract acceptance scenarios

The active contracts and implementation make these scenarios mechanically testable. The checks state observable outcomes, not required implementation techniques.

| Scenario | Required observable result |
| --- | --- |
| Invalid or incomplete Frozen Plan | `prepare` refuses or blocks before any media or target-directory effect. |
| Missing Apply-grade source verification | `prepare` identifies every affected item and reports that dangerous execution cannot be authorized. |
| Source changed after Plan | No affected file moves; the result routes through Plan to a new PreCheck Result instead of silently updating the operation set. |
| Existing unrelated final target | No overwrite and no automatic rename; `prepare` or the per-effect recheck reports a collision. |
| Case or Unicode collision visible only on the target filesystem | Both logical targets are refused before either conflicting effect is committed. |
| Source and final-output namespace overlap | First-profile `prepare` refuses the Run. |
| Two Runs overlap on a source or target | At most one Run may hold mutation authority; the other reports a resolvable conflict without changing media. |
| Crash before a per-item intent is durable | That item has no committed effect and can be considered not attempted after reconciliation. |
| Crash after an atomic move but before completion is recorded | Recovery observes the verified target and absent source, records exactly one completed effect, and does not move again. |
| One source becomes unreadable after preflight | The item is recorded as failed, independent items continue, and the Run remains incomplete until retry or cancellation. |
| Destination volume disappears | No new operations start; completed facts remain recoverable after process or machine restart. |
| Cross-filesystem copy fails before verification | Source remains; no final target is published as complete. |
| Cross-filesystem bytes differ | Source remains; the operation cannot be authorized as a metadata exception or reported complete. |
| Cross-filesystem user-relevant attribute cannot be preserved | Source deletion blocks; status identifies a Run-owned, complete, bounded, content-identity-bound disclosure through which the Human can obtain the exact item, attribute, expected value, and observed value under a new prepared-content identity. |
| Human accepts an exact attribute loss | Only the bound discrepancy set may proceed; the Receipt records the loss and the new authorization, while any additional or changed loss blocks again. |
| Cross-filesystem copy verifies but source deletion fails | Receipt or active Run reports both verified target presence and remaining source; duplicate presence is not mislabeled as a completed move. |
| User cancels before `execute` | The Run ends with proven zero media effects; no Apply Receipt is required. |
| User cancels after `execute` | In-flight work safely settles, actual effects are verified, and an immutable Receipt is published with `closure: human_cancelled`; `completion` independently states whether all operations completed. |
| Receipt publication is interrupted | Retry converges on the same Receipt identity or reports an integrity conflict; it never publishes a second logical Receipt. |
| Successful whole-run rewind | A new reverse Run and Receipt account for every reversed effect; the original Receipt is unchanged. |
| Rewind source position is occupied or target object changed | Rewind `prepare` blocks without overwriting or guessing. |
| Receipt covers 100,000 items | Summary remains bounded; `apply.read` can traverse complete accounting without requiring one response or exposing storage shards. |

Performance acceptance must compare MediaSense with the AI Album baseline for operation throughput, memory use, user effort, interruption cost, resume reuse, and metadata preservation. No numeric threshold is asserted until a representative filesystem and dataset benchmark exists; lack of a threshold cannot be used to waive bounded-memory or no-silent-loss guarantees.

## Reference disposition

This reference remains review evidence supporting the active Apply contract because it preserves the accepted conclusions that:

1. every mutation is traceable to exact confirmed prepared content;
2. Run and Receipt are the only necessary new top-level business entities;
3. partial effects and recovery remain truthful across interruption;
4. one immutable Receipt completely accounts for the planned operation set at large scale;
5. rewind is a new reverse Run rather than history mutation; and
6. source compatibility is a required upstream capability rather than an Apply guess; and
7. cross-filesystem byte equality is mandatory, while any user-relevant attribute loss requires a newly bound Human decision before source deletion and remains visible in the Receipt.
