---
id: "design-260828-2043-plan-local-artifacts"
title: "MediaSense Plan Local Artifact Design"
type: design
status: review
created: 2026-08-28
updated: 2026-08-28
timezone: "Asia/Shanghai"
parent: "index-design"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "spec-260826-1546-precheck-read"
  - "spec-260827-1138-frozen-plan"
  - "spec-260827-1915B-plan-work"
  - "spec-260828-2026-default-organization-profile"
superseded-by: ""
tags: ["mediasense", "plan", "storage", "artifacts"]
---

# MediaSense Plan Local Artifact Design

## Decision

Plan uses the smallest mixed local persistence shape that gives mutable work and immutable handoff artifacts distinct authoritative homes:

```text
<plan-store>/
├── work.sqlite3
└── frozen/
    ├── <artifact-key-1>.json
    └── <artifact-key-2>.json
```

`work.sqlite3` is the authoritative home for mutable Plan Working State. Each JSON file under `frozen/` is the authoritative, immutable Frozen Plan identified by its internal `plan_ref` and `seal.content_identity`. No persisted preview, manifest, per-action directory, Profile copy, or PreCheck Result copy is required.

This is a storage design beneath the existing Tool and artifact contracts. It does not change their request fields, response fields, lifecycle states, references, or validation rules.

## Why each component exists

### `<plan-store>/`

The store root is the stable local discovery boundary for Plan-owned state and artifacts. Its concrete path and directory name remain deployment choices.

Removing the common root would leave no bounded place to discover, protect, or recover Plan-owned material. It has no business identity of its own and is not addressed by a new public reference.

### `work.sqlite3`

The database supports the mutable and transactional responsibilities already owned by `mediasense.plan.work`:

- the binding from `work_ref` to one exact `result_ref`;
- open or closed lifecycle;
- the current opaque revision and complete candidate content;
- the current plan-scoped `organization_preferences` snapshot;
- idempotency records needed to return the same result for the same accepted `request_id`;
- concurrency protection needed to reject a stale `base_revision`; and
- the successful seal outcome needed for retry and recovery.

It is not a Frozen Plan, a PreCheck Result replica, or an Apply input. It does not own event interpretation, grouping, names, Human preference, or Default Organization Profile semantics. Table names, columns, indexes, journaling mode, page size, migrations, and other SQLite choices remain implementation details.

The contract requires only the observable state needed to honor `create`, `update`, `inspect`, and `seal`. It does not require permanent storage of every historical revision. Retention of closed Working States and old revisions remains open until product or recovery evidence requires a policy.

Removing this component would lose durable draft recovery, revision conflict detection, safe retry, and the authoritative open/closed Working State lifecycle. Those responsibilities cannot honestly be carried by immutable Frozen Plan files.

### `frozen/`

This directory is the discovery boundary for published Frozen Plan artifacts. A successful seal adds one JSON artifact. A later semantic change requires a new Working State and a new artifact; an existing Frozen Plan is never overwritten.

The directory does not introduce a collection-level manifest or lifecycle. It is a container whose entries can be inspected to rebuild a lost acceleration index. Dataset, Working State, and Tool-action subdirectories are omitted because no independently managed attachment or lifecycle currently requires them.

### `<artifact-key>.json`

Each file is one complete instance of the existing Frozen Plan Contract. It is the cross-stage authority consumed by Apply and includes its own:

- `plan_ref` and bound `result_ref`;
- exact logical root, relative paths, membership expressions, and source-name decisions;
- accounted exceptions and concise decision notes; and
- content identity and trusted final-confirmation record.

The artifact is independently openable, copyable, and verifiable. Apply must be able to interpret it using the Frozen Plan and referenced PreCheck Result contracts without reading `work.sqlite3`.

Removing a published JSON artifact would destroy the immutable stage handoff even if a database record remained. The database therefore cannot replace it.

## Authority and regeneration

| Information | Authoritative home | May be rebuilt? |
| --- | --- | --- |
| Open Working State, current revision, candidate, preferences, retry and close state | `work.sqlite3` | No, except through an explicitly defined future recovery path |
| Published organization decision and seal | Frozen Plan JSON | No |
| `plan_ref` to artifact-location lookup | SQLite acceleration index or runtime scan | Yes, from valid Frozen Plan files |
| Human-readable tree or Markdown preview | Adapter output | Yes; it is not persisted by default |
| PreCheck Result and Evidence | Existing PreCheck artifact home | No copy is stored by Plan |
| Default Organization Profile | Its product specification | No copy is required in the store |

An index entry is never sufficient evidence that a Frozen Plan exists. Resolution succeeds only after reading the located file, validating it against the active Frozen Plan Contract, and matching its internal `plan_ref` and content identity. If the index is absent or stale, the implementation may scan `frozen/` and rebuild it.

## Reference and filename boundary

`plan_ref` is the public logical identity. The concrete artifact filename is private storage metadata and need not encode that reference reversibly. Implementations may choose a safe deterministic key or another collision-resistant local name.

The following remain invariant:

- two distinct `plan_ref` values cannot resolve to the same authoritative artifact;
- a file whose internal `plan_ref` does not match the requested reference is rejected;
- duplicate files claiming the same `plan_ref` are a recovery conflict unless their complete verified bytes and identities agree; and
- lookup failure must be reported rather than silently selecting a nearby file.

The filename algorithm, escaping, shard directories, and scan acceleration may change without changing product semantics.

## Seal publication

SQLite and the filesystem do not share a transaction manager. Seal therefore uses a recoverable publication protocol rather than pretending to provide a cross-system atomic write:

1. Under the Working State's serialization boundary, verify the exact open `work_ref`, revision, candidate content identity, semantic validity, and trusted Human confirmation.
2. Reserve the seal outcome for the idempotent `request_id` and choose the one resulting `plan_ref` and artifact location.
3. Serialize the complete Frozen Plan, compute and verify its content identity, write it to a new temporary file in the target filesystem, flush it as required by the implementation's durability policy, and atomically rename it to its final non-overwriting location.
4. Commit the SQLite transition that records the published artifact and closes the Working State.
5. Return success only after both the immutable file and committed closed state agree.

The final rename must not replace an unrelated existing file. Implementations must protect the publication sequence from concurrent seals of the same Working State.

The durable recovery rule is result-oriented:

- no verified final artifact means no published Frozen Plan and the Work remains or recovers as open;
- a verified final artifact written before the SQLite close commit is a recoverable pending publication, not a second Plan;
- retrying the same request and confirmation recovers that exact artifact and completes the close transition;
- an artifact with conflicting bytes, identity, `plan_ref`, revision binding, or request binding stops recovery and reports a conflict; and
- a successful response is never returned for only one side of the publication.

Temporary filename, transaction table, intent-record representation, lock mechanism, `fsync` strategy, startup reconciliation, and retry loop are implementation methods. They may vary while preserving these outcomes.

## Multiple Works and Plans

- Every `create` produces a distinct `work_ref`, including work begun after an earlier Plan was sealed.
- A successful seal closes that Working State. It remains inspectable according to the existing Tool contract but rejects further updates.
- A later change creates another Working State and, when sealed, another `plan_ref` and Frozen Plan file.
- Old Frozen Plans remain immutable and are never replaced by a newer preferred Plan.
- This design does not define a mutable `latest` pointer. A caller that wants a particular Plan must hold or select its exact `plan_ref`.
- Draft retention and initializing a new Work from an old Frozen Plan remain outside the current contract.

## Human entry and derived views

The first authoritative file a Human can open after seal is the Frozen Plan JSON. A CLI or UI may render its logical groups as a tree or produce Markdown, HTML, or an index page on demand.

Those views are deliberately absent from the minimum stored tree. They carry no independent decisions, can be deleted safely, and must be reproducible from the Frozen Plan plus the referenced PreCheck Result when expanded membership or source names are needed. If later evidence shows that a persistent review document has an independent archival or signing purpose, it requires a separate design decision.

Before seal, Human inspection is served through `mediasense.plan.work.inspect`; a mutable working file editable outside the Tool would create competing authority and bypass revision protection.

## Default Profile interaction

The Default Organization Profile guides the Agent while producing candidate content. Any Human override is reflected in the Working State's revisioned `organization_preferences` and in the resulting final paths and memberships.

Neither the SQLite store nor Frozen Plan needs a copied Profile document or `profile_ref`:

- the SQLite preference snapshot preserves the inputs needed to resume the current work;
- the Frozen Plan preserves the complete final decision needed by Apply; and
- the product specification remains the maintained source for future default behavior.

## Failure and recovery expectations

| Observed condition | Required treatment |
| --- | --- |
| SQLite contains an open Work and no final artifact exists | Resume or update the Work normally. |
| SQLite contains a closed Work and its recorded Frozen Plan validates | Return or resolve the existing Plan. |
| A verified pending artifact exists but the Work is not closed | Recover the same seal attempt; do not allocate another `plan_ref`. |
| SQLite claims publication but the artifact is missing or invalid | Report corruption or incomplete publication; do not reconstruct a different Plan from mutable rows. |
| Artifact scan finds a valid file absent from the acceleration index | Rebuild the index without modifying the artifact. |
| Multiple non-identical artifacts claim the same `plan_ref` | Report conflict and require repair; do not choose by timestamp or filename. |
| A preview or index is missing | Regenerate it if requested; no authoritative state is lost. |

Storage corruption diagnosis and repair tooling are future implementation work. This design fixes only the externally meaningful recovery outcomes.

## Minimality check

The design has two authoritative components because each owns a responsibility the other cannot carry honestly:

| Component removed | Capability lost |
| --- | --- |
| `work.sqlite3` | Mutable recovery, revision concurrency, safe retries, and open/closed Working State lifecycle |
| Frozen Plan JSON | Immutable, self-contained, inspectable cross-stage handoff to Apply |

No third persistent component is necessary now:

- a manifest duplicates rebuildable discovery information;
- persistent previews duplicate renderable content;
- per-Plan directories have no independent attachment lifecycle;
- copied PreCheck Results divide upstream authority;
- copied Profile documents divide product-policy authority; and
- revision files duplicate state whose observable meaning is already owned by the Tool.

This remains the minimum practical design unless a future requirement demonstrates an independent authority or lifecycle for another artifact.

## Example package

[`example-plan.json`](example-plan.json) shows the exact file that could appear under the runtime `frozen/` directory after seal. It conforms to the existing Frozen Plan Schema and resolves against the existing Hong Kong PreCheck review slice. The sample paths are product proposals used only to demonstrate an event, an ordered content group, and a nearest-context damaged-item decision. It is not a complete Hong Kong Plan, actual runtime output, real Human confirmation, or Apply authorization.

The example deliberately does not include a database file or SQL definition. A hand-written SQLite file would freeze implementation details without proving the design's product boundary.

## Deferred decisions

The following are explicitly outside this design:

- the absolute store location and names shown in the example tree;
- SQLite schema, migrations, journal mode, locks, backups, and compaction;
- artifact filename encoding and optional sharding;
- retention of drafts, closed Works, and obsolete Frozen Plans;
- cloning or initializing a Working State from a Frozen Plan;
- persisted preview or catalog generation;
- CLI and UI presentation;
- Apply storage, authorization, journal, execution, verification, and recovery; and
- runtime implementation.

These decisions must preserve the two authority boundaries above and require their own evidence before becoming stable contracts.
