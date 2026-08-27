---
id: "design-260827-0022-precheck-implementation"
title: "MediaSense PreCheck Implementation Design"
type: design
status: active
created: 2026-08-27
updated: 2026-08-27
timezone: "Asia/Shanghai"
parent: ""
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
  - "clarify-260826-1819-precheck-contract-concepts"
  - "spec-260826-1546-precheck-read"
  - "eval-260823-1918-ai-album-migration-baseline"
superseded-by: ""
tags: ["precheck", "implementation", "compression", "incremental", "recovery"]
---

# MediaSense PreCheck Implementation Design

## Status and authority

This document defines the active target implementation architecture and staged delivery plan for MediaSense PreCheck. It remains subordinate to, and does not replace, the accepted product contracts.

The following remain authoritative over this design:

- the [MediaSense Foundation](design-260823-1918-mediasense-foundation.md) for stage purpose, safety, and contract-first development;
- the [MediaSense Information Architecture](design-260825-2235-mediasense-information-architecture/) for business concepts and stage ownership;
- the [PreCheck concept clarification](../clarify/clarify-260826-1819-precheck-contract-concepts.md) for accepted concept decisions; and
- the [PreCheck Read Contract](../spec/spec-260826-1546-precheck-read/) for the machine-facing handoff to Plan.

If implementation pressure conflicts with those authorities, implementation must stop and report the conflict. It must not silently alter the public concepts, relationships, status axes, or Tool behavior.

The [AI Album migration baseline](../eval/eval-260823-1918-ai-album-migration-baseline/) and Hong Kong fixture are historical evidence and evaluation inputs. They are not runtime dependencies or product authority.

## Evidence boundaries

Three evidence classes must remain separate throughout implementation and evaluation:

1. **Direct fixture facts** are paths, bytes, manifests, checksums, media probes, and relationships directly verifiable inside the current representative package. They may establish closure only for the fixture boundary that was actually enumerated.
2. **Historical production reconstruction** includes the original Hong Kong source size, its 4,896 regular files, 4,365 grouping members, historical caches, and output tree inferred from the package and AI Album commit `c90aa8f04fd0d3348284e0ad19e18462987b1af2`. These facts explain production behavior but cannot prove path-level Accounting Closure for the current fixture Source State.
3. **MediaSense product or implementation claims** include the contracts, requirements, proposed architecture, and acceptance hypotheses in this repository. They must be tested independently and cannot be presented as fixture observations.

AI Album's current HEAD is separate later evidence and must be labeled as such whenever it is used. The historical production path remains bound to `c90aa8f04fd0d3348284e0ad19e18462987b1af2`.

The ordinary fixture verifier validates all listed checksums and expected structures but does not currently reject unlisted files. The inspected local package contained six unmanifested `.DS_Store` files while its signed file set remained intact. Future evaluation must state whether it is proving the signed manifest set or a closed directory tree.

## Decision summary

1. PreCheck is an accountable compression system, not a clustering pipeline. A valid result lowers Plan's default reading cost while preserving explicit routes to every accounted Source Item.
2. A long-lived Dataset may produce many immutable Results. Mutable work and reusable artifacts live outside every sealed Result.
3. Reuse and invalidation operate on the smallest semantically complete dependency set. No application-wide implementation version or Dataset-wide snapshot invalidates unrelated work.
4. The first implementation is one local runtime with one internal structured store and one artifact store. The boundaries in this document are responsibility boundaries, not separate services.
5. SQLite is the initial structured authority for working state and sealed projections. Its schema, indexes, journal mode, and migration mechanics are internal and never enter the cross-stage contract.
6. PreCheck is local, offline, source-read-only, and non-billable. Stage ownership is determined by meaning, not by whether an algorithm happens to be local or remote.
7. Multiple compression profiles may reuse the same valid lower-level work while producing different Evidence graphs and immutable Results.
8. There is no general plugin system. Narrow internal strategies are introduced only where multiple implementations or real replacement pressure exist.
9. The target architecture is designed as a whole and delivered through independently testable slices.
10. Every capability passes a legacy-first implementation gate before coding and a migration comparison before its delivery slice is accepted.

## Problem to solve

If Plan could inspect unlimited media at zero cost, PreCheck would be unnecessary. In practice a Dataset may contain 1.5 TB or more of media and hundreds of thousands of files. PreCheck must reduce the default inspection surface without hiding the source population or transferring bulk preprocessing to Plan.

The implementation therefore has two simultaneous closure obligations:

### Accounting closure

Every discovered Source Item inside the declared accounting boundary receives an `accounts_for` disposition. Scope and condition remain independent. Unsupported, invalid, failed, excluded, auxiliary, and unresolved items remain visible rather than disappearing from totals.

### Navigation closure

Every Source Item named by `accounts_for` must also satisfy one of these routes:

1. **Normal frontier route:** it is reachable from the Result's `entry_evidence` through already-produced `expands_to` detail, a justified `represents` edge, or a combination of the two; or
2. **Explicit exception route:** it is reachable through its `accounts_for` scope or non-usable condition, including the derived attention view where applicable.

The normal route does not require one visual Evidence item per Source Item. A structured index, timeline, contact sheet, representative rendition, several key frames, or another inspectable form may cover one or many Source Items. The exception route prevents an item with no useful visual representation from being hidden.

`derived_from` is provenance, not coverage. It cannot substitute for `represents` or the exception route.

## Goals

- Preserve the read-only source and produce no remote call, upload, online-map request, or billable request.
- Scale by reusing valid work across runs, profiles, and Results.
- Support many-to-one, one-to-many, and multi-level Evidence without making clustering a permanent abstraction.
- Make progress, reuse, invalidation, failures, resource consumption, and remaining work observable.
- Resume after process termination and localize failures to the smallest affected work.
- Seal immutable Results that remain readable without mutable Working Run state.
- Implement the existing `mediasense.precheck.read` contract without exposing storage layout.
- Preserve every valuable AI Album production capability in the responsible stage while rejecting its unsafe coupling and ambiguous failure semantics.

## Non-goals

- Deciding the user's final organization, names, hierarchy, or semantic interpretation.
- Sending media, metadata, coordinates, embeddings, or prompts to remote providers.
- Applying filesystem moves, copies, links, or an organization tree to source media.
- Preserving AI Album cache filenames, cache bitmap semantics, directory layout, thresholds, or model choices.
- Building a distributed scheduler, cloud artifact service, dynamic plugin registry, or third-party plugin protocol without demonstrated need.
- Making a Source Item reference permanent across Results.
- Treating a Dataset-wide snapshot or application version as the unit of cache validity.

## Compatibility posture

### Stable compatibility surface

`mediasense.precheck.read` is already active. This design must conform to its current request and response schema and semantic rules. In particular:

- every read binds an exact immutable `result_ref`;
- `inspect` and `traverse` retain their current meanings;
- the four public concepts and five relationship meanings do not change;
- traversal is asymmetric: all five relationships support outbound reads and only `represents` additionally guarantees inbound lookup;
- Qualification effects are limited to `limits_interpretation` and `blocks_use`; direct facts may inherit basis and references repeat `kind` only where type would otherwise be ambiguous;
- Result status remains the independent `coverage`, `readiness`, and `integrity` axes;
- references and cursors remain scoped to the exact Result, except for Dataset identity; and
- no internal database or cache concept appears as cross-stage authority.

A contradiction discovered during implementation requires a separate contract issue with evidence and impact. It does not authorize an implementation-local contract change.

### Internal zero-BC boundary

MediaSense has no released PreCheck internal store or runtime. The initial internal data model therefore has no backward-compatibility obligation to a previous MediaSense implementation. AI Album caches are not imported or read as live state.

Once MediaSense seals a Result, that Result becomes immutable history. Later internal migrations must either continue to serve it through the stable read contract or preserve a versioned, self-contained reader for it. Internal schema freedom does not permit an existing Result to drift.

## Architectural shape

The first implementation is a single local application. The following are modules or responsibility boundaries inside it, not independently deployed services:

```text
declared Dataset roots and scope inputs
        |
        v
discovery and source accounting
        |
        v
dependency planner -> resource-aware scheduler -> local producers
        |                                      |
        |                                      v
        |                              immutable artifacts
        v
mutable Working Run and reusable Work Records
        |
        v
compression and Evidence assembly
        |
        v
seal validation -> immutable PreCheck Result projection
        |
        v
mediasense.precheck.read -> Plan
```

An operator-facing runtime surface starts, pauses, resumes, cancels, rebuilds, inspects, and seals work. It is not a second Plan-facing contract. A future Skill or Tool for operating PreCheck requires its own reviewed interaction and failure semantics; this design does not invent one prematurely.

## Necessary internal records

The names below describe responsibilities. They do not prescribe SQL table names, classes, or serialized files.

| Candidate | Independent necessity | Decision and authority |
| --- | --- | --- |
| Working Run | Yes. A mutable attempt has progress, policy, resource budget, interruption, and sealing lifecycle distinct from both Dataset and Result. | Persist one run identity and its current operational state in the internal structured store. |
| Work Record | Yes. One reusable computation can outlive a run, be consumed by several Results, fail and retry independently, and be invalidated without deleting history. | Persist its semantic inputs, producer identity, status, attempts, output references, and validity facts in the internal structured store. |
| Artifact | Only when bytes exist independently of a structured value. Large renditions, frames, vectors, and composite Evidence have storage, integrity, sharing, and garbage-collection lifecycles. | Store immutable bytes in the artifact store and keep their identity and integrity binding in structured state. Small structured outputs may remain inline and need no artifact object. |
| Dependency | No independent business identity. A dependency exists only as part of why a Work Record is valid. | Store dependency edges as Work Record-owned facts. They may have an indexed representation, but no independent ID or lifecycle is required. |
| Checkpoint | No independent top-level identity by default. A checkpoint is the durable continuation position of a run or producer. | Store it inside the owning Working Run or Work Record. Promote it only if a future checkpoint must be shared or retained independently. |
| Failure record | No independent top-level identity by default. Failure attempts explain one Work Record or run transition. | Retain attempt history under its owner. Project only material final consequences into Result observations or qualifications. |
| Producer definition | No independent runtime entity. Producer code and effective identity are inputs to Work validity. | Record a narrow producer identity and relevant semantic version data on the Work Record. Do not create a registry service. |
| Source revision evidence | Required information, but not a public Source Item identity and not necessarily a standalone entity. | Record the observed facts needed to recognize exact or likely-equivalent source content and to detect change. |
| Evidence | Yes only when selected into a Result-facing, inspectable basis. Not every cache artifact is Evidence. | A sealed Result owns its Evidence references and relationships. Backing immutable bytes may be shared internally. |
| PreCheck Result | Yes. It owns an immutable accounting boundary, Evidence graph, status, qualifications, and integrity proof. | Publish only after seal validation succeeds. |

There is deliberately no unified `Prepared Information Unit`. Combining Work Records, artifacts, checkpoints, dependencies, and failures would merge different authorities and lifecycles and make invalidation less precise.

## Authority and storage ownership

| Information | Authority | Lifecycle |
| --- | --- | --- |
| Original media and auxiliary source bytes | Source filesystem | Never written by PreCheck; factual source |
| Dataset identity and durable user-supplied context | MediaSense product state | Long-lived and mutable through explicit product actions |
| Current discovery view | Internal structured store | Mutable, rebuildable, not a cross-stage snapshot |
| Working Run progress, leases, attempts, invalidations, and checkpoints | Internal structured store | Mutable until terminal; retained for diagnosis according to policy |
| Work Record meaning and validity | Internal structured store | Reusable across runs; superseded work remains historical until collected |
| Artifact bytes | Artifact store | Immutable after publication; shared while referenced |
| Sealed Result entities and relationships | Immutable result projection in the structured store | Append-only and immutable after publication |
| Query indexes | Rebuildable internal indexes | Derived from authoritative sealed content |
| Human review reports and operational dashboards | Regenerable projections | Never authoritative |

SQLite is the initial structured store because the first runtime is local and needs transactions, indexed traversal, and a simple recovery boundary. Large bytes do not belong in SQLite. Directory names and cache filenames do not carry semantic authority.

Workers do not mutate authoritative rows independently. A single commit coordinator serializes state transitions and Artifact references through short transactions; expensive extraction and encoding occur outside the transaction. Journal mode and durability settings are selected only after the workspace capability probe and may not be assumed from an operating-system family.

The Result projection may reside in the same physical SQLite database as mutable work, but it must be logically append-only, transactionally sealed, independently integrity-checked, and readable without consulting mutable run status. A later storage replacement is allowed behind the read contract.

## Dataset discovery and accounting

### Declaring a boundary

A run binds:

- one durable Dataset identity;
- one or more user-selected source roots;
- traversal and symlink policy;
- explicit scope inputs such as ignore markers or operator decisions;
- a processing profile and resource policy; and
- the observed filesystem capabilities required to interpret locators safely.

This is a run input, not a Dataset-wide immutable Source Snapshot entity.

### Discovery before classification

Discovery and scope classification are separate operations:

1. Enumerate reachable entries inside the declared roots without opening them for write.
2. Record file type, locator, source-volume identity, and cheap change evidence.
3. Interpret `.albumignore`, explicit include/exclude rules, sidecar conventions, and supported-format policies as traceable scope decisions.
4. Classify every discovered object as source media, auxiliary, or excluded and assign a current condition.
5. Preserve the rule and basis for each non-default disposition.

Enumeration is streamed into bounded durable batches. The runtime must not retain the full path population, decoded metadata population, or ready-work population in memory merely to sort or schedule it. Deterministic ordering comes from the structured store or a bounded external ordering strategy.

An ignore marker must not make discovered content vanish from accounting. By default it is an observed scope hint, not automatic authorization to exclude media from compression. Any policy that turns it into an exclusion decision must be explicit in the Working Run inputs and retain the marker as its basis. If policy prevents enumeration of a subtree, the run must expose that limit and cannot claim complete path-level coverage for the unenumerated subtree.

RAW/DNG and other original media are Source Items even when the current decoder cannot prepare visual Evidence. XMP, EXIF, JSON/XML sidecars, GPX, AppleDouble, LRF, M01/M02 variants, control markers, and similar objects are classified by their role and condition; filename proximity alone does not permanently demote an original.

### Stable-enough source recognition

Paths are locators, not durable content identity. The implementation may reuse prior work after a move when the available evidence is strong enough, but it must not expose its recognition mechanism as the public Source Item identity.

Recognition uses an escalating strategy:

- cheap path, volume, size, time, and platform file-identity observations identify likely candidates;
- a fast content fingerprint may reject changed candidates cheaply;
- stronger content verification is required when a false reuse would affect semantics or integrity; and
- ambiguous matches remain distinct or unresolved rather than being silently unified.

The chosen algorithms and thresholds are versioned internal producer inputs. They remain replaceable.

### Concurrent source change

A producer records the source evidence it read. Before committing an output whose correctness depends on stable bytes, it checks that the relevant source evidence still matches. A changed or unavailable source invalidates that attempt; it does not publish an artifact against mixed source states.

Before sealing, PreCheck reconciles the declared boundary against a final discovery pass or an equivalent change journal. New, changed, missing, or ambiguous objects are incorporated, marked explicitly, or cause sealing to block according to the requested coverage. A normally missing object produces a run-owned change fact or tombstone before it leaves the current discovery view, so dependent Work can be invalidated without erasing why. A disconnected source volume is `unavailable`, never inferred as mass deletion.

## Work identity, reuse, and invalidation

### Semantic input descriptor

Each reusable Work Record binds the smallest known set that can change its result:

- actual source evidence consumed by that computation;
- exact direct upstream Work results or artifact digests;
- the identity of the producer or algorithm that gives the output its meaning;
- only the effective parameters, model identity, prompt where relevant, and configuration values read by that producer; and
- environment facts only when they can change semantics, such as decoder behavior, model weights, numeric backend, or nondeterminism policy.

The application version, repository commit, Dataset version, full configuration file, and unrelated environment values are forbidden as blanket invalidation keys. They may be recorded for diagnosis without participating in validity.

Two Work Records are reusable when their semantic input descriptors are equivalent under the owning producer's declared compatibility rule and their outputs pass integrity validation. If equivalence cannot be proven, the work is recomputed.

### Dependency graph

Dependencies point from a Work Record to its direct inputs. Transitive impact is derived by graph traversal; it is not copied into every record.

Examples:

- metadata depends on the source bytes, relevant sidecars, selected tag policy, time interpretation, and any adopted GPX input;
- an oriented rendition depends on source decode, the chosen rendition profile, and the orientation observation;
- video-frame embeddings depend on the exact frame artifacts and embedding producer identity;
- a `represents` claim depends on the candidate set, relevant observations, compression producer, and compression profile;
- an entry frontier depends on the Evidence and relationship claims selected for that Result purpose.

Changing a compression profile must not invalidate metadata, renditions, frames, or embeddings whose semantic descriptors are unchanged. Conversely, a global grouping algorithm may honestly depend on a broad population; the design does not pretend every downstream invalidation is local.

### Invalidation is not deletion

Invalidation means “do not select this Work Record for new work under these inputs.” It does not erase the record or an Artifact still referenced by a sealed Result.

Every invalidation records a reason such as source change, upstream change, producer change, effective parameter change, relevant environment change, integrity failure, or explicit operator rebuild. Manual rebuild requests use the same graph machinery and may target:

- one producer capability;
- one Source Item;
- one Work Record and its dependent subgraph;
- one Result-building run; or
- all reusable work in a deliberately confirmed scope.

An unrelated code, documentation, configuration, or application version change must produce zero invalidations.

## Artifact lifecycle

An Artifact is published only after its complete bytes are written and verified:

1. write to a workspace-local temporary or unique unpublished location;
2. finish encoder output and close handles;
3. compute and verify the required integrity evidence;
4. publish immutably using an available atomic primitive or a unique-name plus transactional-reference fallback; and
5. commit the successful Work Record reference in the structured store.

A crash before step 5 may leave an orphan but never a successful Work Record. A structured reference to missing or corrupt bytes is an integrity failure and triggers quarantine or recomputation for new work. If bytes referenced by a sealed Result later fail integrity validation, the Result is not rewritten: the read adapter refuses to serve the affected result or access with the contract's `result_untrusted` or `access_failed` outcome until the exact bytes are restored. New work may produce a new Result.

Artifact identity may be content-derived, randomly allocated with a stored digest, or supplied by another backend. The choice is internal. Artifact paths never serve as Source Item or Evidence identity.

## Local producers

The target architecture supports narrow producer strategies for capabilities that genuinely admit replacement:

- media validation and probing;
- metadata and sidecar extraction;
- time and location candidate extraction, including GPX correlation;
- image rendition and orientation handling;
- video frame sampling and key-frame or multi-frame selection;
- local feature or embedding generation;
- local content-sensitivity candidate observation;
- similarity, neighborhood, bundling, representative, anomaly, and compression candidates; and
- structured or visual Evidence composition.

Each producer declares:

- accepted input kinds;
- semantic inputs and compatibility identity;
- possible structured outputs and Artifact outputs;
- resource claims;
- deterministic or nondeterministic behavior;
- timeout, retry, cancellation, and localized failure semantics; and
- provenance sufficient for later observations and qualifications.

This is static internal wiring in the first implementation. There is no runtime plugin discovery, registry service, package negotiation, or public provider schema.

Locality does not decide stage ownership. A future local model may create a source-derived, inspectable, provenance-bearing candidate observation in PreCheck. A deterministic rule that makes a final organization choice still belongs to Plan. Current PreCheck producers may not perform network access or billable work.

## Resource-aware scheduling

Every ready Work Record submits a resource claim rather than directly creating unbounded tasks. The scheduler admits work against run-level budgets for:

- source-volume and workspace-volume I/O;
- CPU and process slots;
- memory reservation and temporary-space reservation;
- GPU or accelerator memory and model residency;
- ExifTool process lanes;
- decoder and encoder lanes; and
- network access, fixed to zero for the current PreCheck profile.

Queues are bounded. Producers receive backpressure before materializing large input lists or decoded frames. Work is grouped by locality where beneficial, but batches remain interruptible and record item-level outcomes.

Operator-facing configuration should expose intent and resource ceilings: total memory, temporary-space budget, CPU/GPU allowance, source-volume I/O pressure, enabled local producers, and optional advanced overrides. Producer batch sizes, semaphore counts, and worker counts default to measured adaptive choices and remain internal unless operators need them to resolve a real resource problem.

AI Album's concrete values—ExifTool batch 200, frame embedding batch 8, per-stage parallelism 4/1/1/4, cluster naming 20, and a fixed 12 GB startup gate—are benchmark inputs, not defaults to inherit. In particular, one coarse memory gate is not runtime memory control, and creating all ExifTool batches or output operations at once is not acceptable backpressure.

## Evidence and compression

### Observations are not automatically Evidence

Work outputs first become source-derived observations or internal artifacts. They become public Evidence only when a Result selects an inspectable representation useful to Plan. This prevents the cache inventory from becoming the handoff schema.

Evidence may be:

- a direct use of one Source Item;
- a lower-fidelity rendition;
- one or several video frames;
- a contact sheet or representative set;
- a structured timeline, index, anomaly summary, or candidate relation view; or
- a future locally generated candidate description with explicit provenance and limitations.

### Compression claims

`represents` says that Plan may defer directly reading the target Source Item for the declared purpose. It requires an inspectable basis and material qualifications. It is never source truth.

A compression producer must retain enough information to challenge its claims, including relevant boundary examples, outliers, hidden variation, unavailable inputs, and quality limits. A single representative selected only by file extension cannot make a strong semantic coverage claim.

### Many-to-one

One Evidence item may be `derived_from` one Source Item while `represents` links it to many Source Items. Boundary, outlier, or alternate Evidence may expand the default item. The Result records each meaning separately.

### One-to-many

One video Source Item may produce several frame Evidence items. A low-cost contact sheet or selected frame may be entry Evidence and `expands_to` the additional frames and source. All frames remain derived material, not Source Items.

### Frontier construction

The default frontier is selected under a declared compression purpose and budget. Selection may consider coverage, diversity, temporal or spatial structure, anomaly risk, rendition cost, and known uncertainty, but no one method is permanent.

The frontier must satisfy navigation closure. It need not optimize one universal score, and it must not hide an item merely to meet a target count. Requested target size is a pressure or budget input; the Result records achieved size and material limits.

## Repeated compression of one Dataset

The following is a required acceptance scenario:

```text
Dataset A, about 1.5 TB
  -> Result R1, about 500 entry Evidence items: insufficient compression
  -> Result R2, about   3 entry Evidence items: excessive compression
  -> Result R3, about 200 entry Evidence items: accepted balance
```

The three runs behave as follows:

- each run freezes its own effective compression profile;
- each successful seal creates a new immutable Result and never edits R1 or R2;
- stable metadata, renditions, video frames, embeddings, and other lower-level work are reused by semantic dependency match;
- profile-dependent grouping, representation claims, composite Evidence, frontier selection, and seal proof are recomputed only where their inputs differ;
- Results may reference the same immutable backing Artifact without copying it;
- each Result creates its own result-scoped Evidence and Source Item references and relationships; and
- no Work Record, cache key, dependency edge, or reuse decision is exposed through the read contract.

User rejection or acceptance of a frontier is a reopen signal for new work. It does not retroactively change the old Result's status or content.

## Incremental Dataset change

When Dataset A gains a small number of files:

- earlier Results continue to account for exactly their old populations;
- a new Working Run discovers and accounts for the current population without creating a Dataset-wide invalidation key;
- unchanged Source Items reuse valid lower-level work, including after a safely recognized move;
- new or changed items produce new work;
- candidate relations and frontier decisions recompute only across their declared dependency scope; and
- the run seals a new Result with new result-scoped references.

A missing source root or volume blocks reconciliation as unavailable. It is not interpreted as deletion from the Dataset.

## Algorithm change and directed rebuild

Changing one algorithm or debugging one cache class produces a new identity only for Work Records whose meaning depends on that producer, its effective parameters, or its outputs. Downstream dependents are found by graph traversal. Independent metadata, rendition, frame, or embedding work remains valid.

Operator rebuild requests use selectors over the same graph rather than a parallel deletion mechanism. A full rebuild is supported as an explicit broad selector, not as the only trustworthy recovery path.

## Working Run lifecycle and recovery

The operational lifecycle is:

```text
created -> discovering -> preparing -> assembling -> validating -> sealing -> sealed
                 |             |             |
                 +---- paused / blocked / interrupted ----+
```

Cancellation or terminal failure ends a Working Run without publishing a Result. An explicitly requested partial Result may still be sealed if its boundary, omissions, navigation paths, readiness, and qualifications satisfy the contract. A merely interrupted run is never presented as a partial Result.

### Work execution states

A Work Record distinguishes at least pending, leased/running, succeeded, retryable failure, terminal failure, and invalidated outcomes. Exact storage enums remain internal.

- A lease identifies in-flight ownership and expires after process death.
- Equivalent ready work is claimed once by semantic identity; concurrent runs wait for, then validate and reuse, the committed output instead of computing duplicate copies.
- Only committed outputs make work succeeded.
- Retrying creates an attempt history without erasing earlier evidence.
- Cancellation stops admitting new work and lets active producers reach a safe cancellation boundary.
- Resume reconstructs ready work from durable states rather than replaying a procedural phase counter.

### Failure responses

| Failure | Required behavior |
| --- | --- |
| One corrupt or unsupported medium | Localize condition and affected downstream work; continue unrelated work. |
| Source volume disconnect | Pause dependent work as unavailable; do not infer deletion; require compatible remount before reuse. |
| Process exit or host restart | Expire leases, discard unpublished temporary outputs, validate committed outputs, and continue ready work. |
| Workspace disk full | Stop admission before further writes where possible, retain committed work, expose required space, and resume after capacity returns. |
| Artifact corruption | Quarantine or ignore the bad artifact, invalidate dependent work for new runs, and preserve the historical Result identity. |
| Producer or effective parameter change | Create new Work identities only for affected computations and descendants. |
| Seal interruption | Publish no Result until the seal transaction and integrity record are complete. |

Retries are producer-specific and bounded. Permanent decode failure is not retried like a transient filesystem error. Current PreCheck has no remote rate-limit path; AI Album's network retry behavior is retained only as operational experience for Plan-owned capabilities.

## Filesystem capability boundary

The design depends on capabilities, not POSIX identity.

| Required capability | Use and fallback |
| --- | --- |
| Stable source location and volume recognition | Record the strongest platform evidence available. If a remount cannot be distinguished safely, require operator confirmation or stronger content verification. |
| Read-only source access | Open source objects only for reading, reject workspace containment under source roots, and use OS sandbox or read-only mounts when available. Record the enforcement boundary and observed writes. |
| Atomic or equivalent Artifact publication | Prefer an atomic replace inside the workspace. Otherwise publish to a unique immutable name and make it visible only through a successful structured-store transaction. |
| Durable structured transactions | The workspace must support the selected database's locking and durability assumptions. Otherwise use a supported local workspace or refuse the run. |
| File-change detection | Use tiered observations appropriate to the producer's correctness needs; do not equate path or mtime alone with identity. |
| Disconnect and remount detection | Bind locators to a volume observation and distinguish unavailable from deleted. |
| Same-volume and cross-volume behavior | PreCheck only reads source and writes workspace, so it never requires source-to-workspace rename. Cross-filesystem organization remains Apply-owned. |
| Case and Unicode semantics | Preserve observed spelling, detect normalized collisions, and do not assume case sensitivity. |
| Symbolic-link or alias semantics | Detect links without following them silently, prevent traversal cycles and boundary escape, and record the selected policy. |

Capability probing occurs before expensive work and is retained with the Working Run. It is not added to the public read schema unless a resulting limitation materially affects Result trust.

## Sealing an immutable Result

Sealing is a validation and publication boundary, not a directory rename.

### Inputs frozen for sealing

- Dataset identity and Result-bound Dataset context;
- the exact accounted Source Item population and locators;
- the selected Evidence objects and immutable access targets;
- all five relationship sets;
- the declared compression purpose and effective profile;
- material observations, bases, and qualifications;
- source-read-only, offline, cost, and integrity evidence; and
- the independently evaluated coverage, readiness, and integrity axes.

### Seal gates

1. Every discovered in-boundary Source Item has exactly one `accounts_for` scope and condition.
2. Every accounted Source Item satisfies normal navigation closure or an explicit exception route.
3. Every referenced target exists within the same Result and every contract-required traversal direction can be answered from the sealed relationships.
4. Every `represents` claim has an inspectable basis and any material compression loss is visible.
5. `derived_from` matches actual production inputs and is not substituted for representation.
6. Every retained Artifact passes integrity verification and remains pinned for the Result lifetime.
7. Dataset context and Source Item locators are frozen as observed for this Result.
8. Policy, enforcement, and observed facts establish the declared source-read-only, offline, and non-billable boundary.
9. Status axes are evaluated independently and qualifications explain any partial or blocked state.
10. The read projection passes contract conformance and traversal closure checks.

The seal transaction allocates a new opaque `result_ref`, freezes the result-scoped references and relationship pages, records integrity evidence, and only then publishes the Result as readable. There is no mutable `latest` alias in the read path.

### Readiness

`integrity` is a mechanical trust judgment. `coverage` describes the declared accounting extent. `readiness` asks whether the available Evidence and explicit exception paths are sufficient for the declared planning purpose.

- `coverage=complete` requires exhaustive accounting for the declared discovery scope. A deliberately bounded subset or a known unaccounted region is `partial` and carries its exact limit.
- `integrity=valid` requires the sealed identity, relationships, retained bytes, and trust proof to pass the seal gates. A Result may be intentionally sealed as `invalid` for diagnosis, but Plan cannot use it as trusted input.
- `readiness=plan_ready` requires sufficient navigable Evidence and exception disclosure for the declared planning purpose, not universal semantic certainty.

Readiness does not certify that a cluster, caption, location, or representative is semantically correct. A technically plan-ready Result may later prove unsatisfactory to the user; that feedback opens a new run and Result. A localized invalid item may coexist with `plan_ready` when its effect and alternatives are explicit and the planning purpose remains supportable.

## Serving `mediasense.precheck.read`

The read adapter accepts only the active contract and queries the sealed projection:

- `inspect` reads one Result, Dataset view, Source Item, or Evidence;
- `traverse` reads one of the contract-declared directions: outbound for all five relationships and additionally inbound for `represents`;
- `attention_only` is derived from `accounts_for` condition and material qualifications;
- cursors bind the exact Result, query shape, ordering, and continuation position;
- inbound `represents` traversal is an index over the same relationship, not a new relationship; and
- Evidence access returns only local, read-only artifacts, direct Source Item access, or inline structured content allowed by the contract.

Mutable Work Records, attempt history, dependency keys, internal source-recognition evidence, database row IDs, cache locations, and garbage-collection state are never returned. Query indexes may be rebuilt without changing responses.

## Source-read-only, offline, and cost proof

The run records four separate levels:

1. **Policy:** network, upload, online maps, remote models, and billable calls are forbidden.
2. **Construction:** enabled producers have no remote provider path and receive no API credentials.
3. **Enforcement:** the strongest available process, container, firewall, filesystem, or mount restriction is recorded.
4. **Observation:** network attempts, external requests, billable calls, and source writes observed within the declared boundary are counted.

Configuration intent alone is insufficient. A Result qualification states any enforcement limitation that prevents a stronger claim.

PreCheck may use local models when their output is source-derived, inspectable candidate evidence with provenance and uncertainty. It may not convert such observations into final names or organization decisions.

## Cleanup and retention

Cleanup is reachability-based, not filename- or age-only deletion.

Roots that pin internal data are:

- every sealed Result retained by policy;
- every active or resumable Working Run;
- explicit operator retention pins; and
- work protected by an active publication or repair transaction.

Garbage collection marks referenced Work Records and Artifacts, identifies unreachable candidates, applies a grace period, rechecks references transactionally, and then deletes only workspace-owned data. It never deletes source objects.

An invalidated Work Record may remain collectible only after no retained Result or run references its output. Unknown files in the workspace are quarantined or reported before deletion. The system reports reclaimable bytes, reasons, and failures.

## Observability

The operator must be able to inspect:

- discovered, accounted, usable, exceptional, and unresolved Source Item counts;
- pending, running, reused, succeeded, retrying, failed, invalidated, and blocked work by producer;
- cache/reuse decisions and exact invalidation reasons;
- bytes read and written, artifact size, temporary-space demand, and reclaimable space;
- CPU, memory, GPU, decoder, ExifTool, and per-volume I/O pressure;
- current bottleneck, estimated remaining work where defensible, and last durable checkpoint;
- compression frontier size, represented population, uncovered normal paths, exception counts, and material qualifications; and
- observed source writes, network attempts, remote calls, and billable cost, expected to remain zero.

Detailed events belong to the mutable operational record. A sealed Result keeps only the proof and qualifications needed for downstream trust.

## AI Album capability disposition

The table maps every capability in the migration ledger to a target responsibility. The classification is a design commitment; it becomes an implementation result only after the listed acceptance evidence exists.

| AI Album capability | Destination | Classification | MediaSense treatment |
| --- | --- | --- | --- |
| Recursive media inventory | PreCheck | `preserved` | Enumerate broadly, account explicitly, report errors and throughput. |
| `.albumignore` scope control | PreCheck | `intentionally_changed` | Treat as traceable scope input; do not silently hide traversed content. |
| Explicit GPX argument | PreCheck | `intentionally_changed` | Discover candidates, evaluate overlap, record adoption and provenance, retain explicit override. |
| Same-stem and sidecar grouping | PreCheck | `preserved` | Produce inspectable candidate relations with reasons; do not demote originals automatically. |
| 60-second adjacent chaining | PreCheck | `intentionally_changed` | Preserve time-neighborhood capability, expose total span and boundaries, keep algorithm and threshold replaceable. |
| Representative selection | PreCheck and Plan | `preserved` | PreCheck supplies candidate Evidence and limitations; Plan decides how much to inspect and trust. |
| Batch metadata extraction | PreCheck | `preserved` | Keep batched local extraction with item-level status, provenance, resource bounds, and dependency validity. |
| Timestamp fallback | PreCheck | `intentionally_changed` | Unify typed candidates; never turn missing or failed time into epoch zero or a false date. |
| Video frame sampling | PreCheck | `preserved` | Retain local multi-frame Evidence with versioned profiles and partial-decode semantics. |
| Thumbnail generation | PreCheck | `preserved` | Preserve ordinary and high-resolution renditions with explicit profiles, actual dimensions, orientation dependencies, and integrity checks. |
| Asset/frame embeddings | PreCheck | `preserved` | Keep local feature generation behind replaceable producers with model and input provenance. |
| Local content-sensitivity evidence | PreCheck | `preserved` | Store candidate signals, scores, detector identity, completion, and failures without making policy decisions. |
| Sensitivity-informed VLM routing | Plan | `intentionally_changed` | Plan owns whether and how a signal affects local/remote inspection, authorization, and user interaction. |
| Date/location/content clustering | PreCheck and Plan | `not_comparable` as final truth | PreCheck may produce candidates; Plan owns final semantic grouping. |
| Per-representative caption | Plan by default; PreCheck only for qualifying candidate observers | `intentionally_changed` | Do not bulk-call remote models. A future local candidate observation is allowed only under PreCheck semantics. |
| Visual location inference | Plan | `intentionally_changed` | Keep observations and candidates distinct from final place interpretation; no online maps in PreCheck. |
| Per-item title and cluster mode | Plan | `intentionally_changed` | Name the whole organization coherently after evidence review rather than propagating representative titles. |
| Direct output-tree construction | Plan then Apply | `intentionally_changed` | Freeze intent first; perform no organizational filesystem effect in PreCheck. |
| Thumbnail/copy/link/move modes | PreCheck Evidence or Apply | `preserved` with stronger boundary | PreCheck may materialize Evidence copies; Apply owns authorized organization effects and receipts. |
| Per-stage cache | PreCheck | `preserved` capability, `intentionally_changed` mechanism | Replace the imperative eight-bit bitmap with dependency-aware reuse and targeted rebuild selectors. |
| Usage monitoring | All stages | `intentionally_changed` | Attribute relevant local cost and work; PreCheck proves zero remote and billable use. |

Additional operating lessons retained from code and tests include configuration overrides, collision detection, cache corruption recovery, bounded retries, progress display, timing, Docker parity, and memory awareness. Their historical implementations and constants are not copied.

### Historical code evidence checked

The disposition above was rechecked against the fixture-bound production commit rather than copied only from documentation:

| Capability area | Principal `c90aa8f` code evidence | Material finding carried into this design |
| --- | --- | --- |
| Discovery and grouping | `src/media_libs.py:97-223`, `src/media_utils.py:28-60` | The walk, marker ignore, stem/AppleDouble/M01/M02 unioning, validation, temporal chaining, and extension-priority representative are coupled; MediaSense separates discovery, scope, candidate relation, and evidence selection. |
| Metadata and time | `src/metadata/metadata_loader.py:151-188,339-388,470-544`, `src/metadata/timestamp_service.py:41-92` | ExifTool batching and sidecar priority are valuable, but batch time failure can become `0.0` while the single-item path uses filename fallback; typed candidates and failures replace this divergence. |
| Renditions and video | `src/media_processors/image/image_processor.py`, `src/media_processors/video/video_processor.py` | Ordinary/high-resolution renditions, up to 20 sampled frames, frame embeddings, and representative-frame selection are separate reusable products with different dependencies. |
| Cache and hash | `src/my_class.py`, `src/cache_manager.py:81-87,293-375` | Eight flags control more than eight artifact forms; wildcard sets can look complete when partial, wildcard clear is ineffective, and readable stale artifacts lack dependency provenance. |
| Local models and semantic calls | `src/llm/embedding.py`, `src/llm/detection.py`, `src/media_processors/llm/llm_processor.py` | Local embeddings and sensitivity signals are useful source-derived candidates; caption/location/title routing mixes those facts with semantic and remote decisions that belong to Plan. |
| Scheduling | `src/content_analysis/clustering_engine.py:245-285`, `src/cluster/linear.py:269-284` | Stage constants, semaphores, and progress exist, but resource classes and global backpressure do not. The apparent CLI batch size is forced to 16 and is not consumed by the cache scheduler. |
| Output effects | `src/app.py:55-69`, `src/cluster/file_operations.py`, `src/cluster/async_file_ops.py` | Thumbnail copy, symlink, and original-media move are launched from the semantic pipeline without a journal or receipt; organization effects move to Apply. |
| Operations and audit | `src/memory_check.py`, `src/function_tracker.py`, `src/llm/monitor.py` | A 12 GB startup check, progress, function timing, and optional token/cost logging show real operational needs but lack work-level attribution and continuous resource control. |

## Legacy-first implementation gate

AI Album is not architectural authority, but its production code is the default implementation evidence for capabilities it already exercised. A developer may not replace an existing mature capability from memory or from this design's summary alone.

This gate applies to each implementation unit that touches a migrated capability. It uses the existing migration ledger, implementation plan or change review, test suite, and eval artifacts; it does not create a new public contract, registry, or mandatory document type.

### Entry gate before coding

Before production code begins, the implementer must:

1. identify the affected rows in the migration capability ledger;
2. read the corresponding source, tests, configuration, and relevant fix history at AI Album commit `c90aa8f04fd0d3348284e0ad19e18462987b1af2`;
3. inspect current AI Album HEAD only when it may contain a relevant later fix, and label that evidence separately from the production commit;
4. state the real production problem, supported inputs, edge cases, failure behavior, resource behavior, and consumers that the old implementation served;
5. establish characterization tests, fixture cases, or a performance baseline before replacing behavior; and
6. make one explicit, evidence-backed implementation choice:
   - directly reuse or extract the implementation into MediaSense ownership;
   - port it while adapting MediaSense responsibility and safety boundaries;
   - reimplement it against characterized behavior when the old structure cannot be carried safely; or
   - replace or retire it because a named defect or changed product boundary makes preservation wrong.

Direct reuse or extraction cannot create a runtime dependency on the AI Album repository. Reimplementation requires a stronger reason than local coding preference. A known defect is captured as an expected intentional difference, not encoded as a golden behavior.

Coding may begin only when a reviewer can trace the selected option to source evidence and to a pre-implementation characterization. When evidence cannot distinguish the options, the implementation unit remains blocked or explicitly narrows its claim.

### First required characterization scope

| Capability family | Historical material to inspect before coding | Characterization evidence required |
| --- | --- | --- |
| Discovery and association | `src/media_libs.py`, `src/media_utils.py`, `src/conf/conf.yml`, related discovery tests and fixes | Recursive traversal, directory-local `.albumignore`, same-stem relationships, RAW/JPEG, AppleDouble, M01/M02, supported and unsupported formats, temporal adjacency, long chained spans, and representative priority. |
| Source recognition and cache control | `src/cache_manager.py`, `src/my_class.py`, cache collision tests, thumbnail/cache repair records, and fixture cache manifests | Fast/content hash behavior, cache addressing and basename collisions, selective eight-bit clearing, moved/changed files, readable stale entries, corrupt payload regeneration, wildcard clearing, partial wildcard sets, and incremental reuse. |
| Metadata and sidecars | `src/metadata/metadata_loader.py`, `metadata_manager.py`, `photo_info_extractor.py`, `src/conf/conf.yml`, metadata tests and sidecar repair records | ExifTool batch behavior, XMP/EXIF/JSON/XML priority and merging, RAW companions, camera-brand field variants, sparse results, batch failure scope, provenance loss, and throughput. |
| Time interpretation | batch metadata path, `src/metadata/timestamp_service.py`, time specification and tests | Batch versus single-item behavior, timezone-bearing and timezone-missing values, DJI and Canon cases, filename fallback, missing time, malformed time, epoch-zero behavior, and ordering consequences. |
| GPX | `src/my_gpx.py`, metadata integration, configuration, tests, and Hong Kong GPX cases | Segment ordering, binary search, interval interpolation, nearest boundary point, maximum time difference, embedded-GPS precedence, timezones, datum handling, unmatched points, and malformed tracks. |
| Image rendition | `src/media_processors/image/image_processor.py`, `src/media_utils.py`, cache tests, and fixture renditions | Decode and validation boundaries, orientation correction, aspect behavior, declared versus actual dimensions, ordinary/high-resolution profiles, cache dependencies, corruption, and CPU/memory/I/O cost. |
| Video evidence | `src/media_processors/video/video_processor.py`, media pipeline tests, and fixture frame caches | Interval and maximum-frame rules, final-frame handling, partial decode, frame ordering, frame embeddings, representative-frame selection, empty results, profile dependencies, and decode cost. |
| Scheduling and resources | `src/content_analysis/clustering_engine.py`, `src/cluster/linear.py`, metadata batching, async tests, `memory_check.py`, and `function_tracker.py` | Per-stage parallelism, batch sizes, semaphore behavior, one-shot task materialization, cancellation, progress, peak memory, model serialization, source/workspace I/O pressure, and throughput. |
| Corruption and diagnosis | `src/cache_manager.py`, collision tests, log configuration, progress/timing code, and historical repair notes | Recovery for each serialized form, file/directory collisions, incomplete writes and wildcard sets, retry visibility, cache hit/miss truthfulness, localized failures, progress continuity, and diagnostic attribution. |

Historical constants—including concurrency limits, ExifTool batch size, frame interval and count, GPX time window, memory threshold, and similarity distances—enter characterization as candidate baselines. They are retained, tuned, or rejected only after comparable measurements; none becomes a public contract.

Mature general-purpose components such as ExifTool and FFmpeg/ffprobe are preferred when they already own parsing or decoding complexity. Replacing them with custom parsers or decoders requires evidence of an unmet requirement and an equivalent compatibility, correctness, and failure test set.

### Exit gate after implementation

Before a capability or Slice is accepted, compare MediaSense with the characterized legacy baseline on both function and operating quality:

- supported and exceptional inputs;
- output meaning, provenance, and known intentional differences;
- local/remote and billable cost;
- throughput, peak memory, I/O, concurrency, and backpressure;
- interruption, retry, corruption, and partial-failure behavior;
- cache reuse and invalidation precision;
- user effort and source safety; and
- test coverage for historical production cases.

Update the existing migration ledger with implementation evidence and classify the result as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`. An unexplained loss or material operating-quality degradation is a regression and blocks Slice completion. A different output is acceptable only when the product boundary or defect evidence justifies it.

### Reuse decisions still requiring human review

The gate, not this document alone, decides these choices:

- whether discovery and filename-association code can be extracted or must be rewritten to achieve explicit accounting;
- whether metadata and GPX implementations can be ported around ExifTool or need replacement after edge-case characterization;
- whether image/video processors can be extracted after separating their cache and failure semantics;
- whether any CacheManager serialization or corruption handling is worth retaining while replacing its validity and wildcard-completion model;
- whether later fixes from current AI Album HEAD should be adopted in addition to the production baseline; and
- which historical tuning values remain suitable under measured MediaSense resource and quality targets.

## Delivery slices

The target architecture above governs every slice. A slice may defer capability, but it may not introduce a shortcut that contradicts the final authority or lifecycle model.

Each Slice has two mandatory migration gates:

| Slice | Before coding | Before completion |
| --- | --- | --- |
| Slice 1 | Characterize discovery, scope/ignore behavior, filename associations, validation, source recognition, cache addressing, corruption handling, and basic operational reporting. | Compare accounting coverage, edge-case behavior, scan throughput, restart reuse, source safety, and read-contract output with the legacy baseline where comparable. |
| Slice 2 | Characterize metadata/sidecar, time, GPX, rendition, video, embedding, cache, batching, concurrency, memory, and I/O behavior. | Compare values and failures on shared cases plus throughput, peak resources, cache hits, selective invalidation, and interrupted recovery. |
| Slice 3 | Characterize temporal bundling, representative choice, date/location/content candidates, weights, thresholds, naming inputs, and known contaminated groups. | Compare compression coverage, hidden variation, frontier cost, user effort, and the 500 → 3 → 200 reuse scenario; semantic output equality is not presumed. |
| Slice 4 | Revisit every ledger row and any separately labeled relevant current-HEAD fix before integrated hardening. | Run the full Hong Kong migration gate and production-scale/fault profiles, resolve all unexplained regressions, and publish final evidence-backed ledger states. |

### Slice 1 — Accounting and resumable walking skeleton

Deliver:

- Dataset binding, filesystem capability probing, source discovery, scope classification, and accounting closure;
- Working Run, minimal Work Record persistence, lease recovery, and structured progress;
- immutable Artifact publication and integrity checks;
- a conservative local rendition path;
- an end-to-end sealed Result and conforming `mediasense.precheck.read` implementation; and
- source-read-only and offline enforcement tests.

The slice may use a deliberately simple frontier, but it must reduce default reading for its test purpose and satisfy navigation or exception closure.

### Slice 2 — Reusable local evidence

Add:

- metadata, time candidates, GPS and GPX provenance;
- ordinary and high-resolution rendition profiles;
- video probing, frame sampling, partial-decode behavior, and composite Evidence;
- local embeddings and optional local content-sensitivity observations;
- fine-grained dependency invalidation and manual rebuild selectors; and
- per-resource scheduling and backpressure.

### Slice 3 — Adaptive compression and multiple Results

Add:

- replaceable similarity, temporal, spatial, anomaly, representative, and composition strategies;
- inspectable `represents`, `derived_from`, and `expands_to` bases;
- frontier budget and qualification evaluation;
- the 500 → 3 → 200 repeated-compression acceptance scenario; and
- Result comparison metrics without exposing internal work.

### Slice 4 — Production hardening and final migration gate

Add:

- crash, cancellation, disconnect, remount, corruption, and disk-full fault injection;
- cross-filesystem-capability test matrix;
- reachability-based garbage collection and repair tooling;
- generated hundred-thousand-item scale profiles and a read-only 1.5 TB milestone run;
- Hong Kong fixture comparison and capability-ledger status updates; and
- operational runbooks after runtime behavior is proven.

## Verification strategy

### Legacy characterization and per-Slice comparison

- Every migrated implementation unit links its ledger row to the exact `c90aa8f` source, tests, configuration, and relevant repair history reviewed before coding.
- Characterization tests capture successful behavior, edge cases, failures, and resource behavior at the narrowest practical boundary. Black-box fixture or benchmark evidence supplements tests when the behavior depends on external tools or real media.
- Known defects such as epoch-zero timestamps, dependency-blind cache hits, partial wildcard sets treated as complete, and unbounded task creation are represented as negative cases with an expected MediaSense correction.
- Current-HEAD evidence is labeled separately and cannot silently redefine the historical production baseline.
- Each Slice records its pre-implementation baseline and post-implementation comparison; Slice 4 aggregates those records rather than performing the first comparison.
- No fresh replay, remote model, online map, or billable API is required for PreCheck migration acceptance.

### Contract conformance

- Validate every request and response shape against the active Tool schema.
- Exercise `inspect`, outbound traversal for all five relationships, inbound traversal for `represents`, pagination, derived attention filtering, rejection of unsupported reverse traversal, invalid references, and cursor/result isolation.
- Compare generated responses with the Hong Kong development Mock semantically, without treating its values as runtime truth.

### Accounting and navigation properties

- Reconcile discovered counts with `accounts_for` scope and condition counts.
- Prove that every normal Source Item is reachable from entry Evidence and every exception is reachable through an explicit exception path.
- Reject dangling references, cross-Result references, hidden Source Items, collapsed `derived_from`/`represents`, and Evidence without valid access.

### Incremental reuse and invalidation

- Add, modify, move, remove, disconnect, and remount small source subsets.
- Change one producer, parameter, model, sidecar, GPX input, rendition profile, or relevant environment fact at a time and verify only actual dependents recompute.
- Change unrelated code, documentation, or configuration and verify zero semantic invalidation.
- Exercise producer-, Source Item-, subgraph-, run-, and full-rebuild requests.

### Repeated compression pressure test

- Build three Results over the same large logical Dataset with controlled frontiers near 500, 3, and 200 Evidence items.
- Verify all three Results remain immutable and independently readable.
- Verify unchanged low-level Work and Artifact bytes are reused rather than regenerated or copied.
- Verify each Result independently satisfies accounting and navigation closure and reports its own compression loss.

### Fault injection

- Terminate the process before and after Artifact publication and before, during, and after seal commit.
- Inject single-item decode failures, ExifTool batch failures, database lock failures, artifact corruption, ENOSPC, source disconnection, and cancellation.
- Verify no partial result is published, committed work remains reusable, and retries do not erase diagnostic evidence.

### Resource and scale tests

- Measure discovery, metadata, rendition, video, embedding, compression, seal, and read throughput separately.
- Exercise case-sensitive and case-insensitive paths, Unicode normalization, symlink cycles, removable volumes, and workspaces with different atomicity and locking capabilities.
- Use generated scale/fault fixtures for repeatability and the original source only as a controlled read-only milestone.

### Migration evaluation

- Use the verified Hong Kong package for topology, bundle, media-failure, cache, and historical-output comparisons.
- Keep directly observed package facts separate from reconstructed original-production facts.
- Never use the historical 4,896-file or 4,365-member populations to prove path-level closure of the current fixture Source State.
- Record each capability as `preserved`, `intentionally_changed`, `regression`, or `not_comparable` only after implementation evidence exists.

## Known risks and explicit follow-up decisions

- Slice 1 now keeps source attachment on each Working Run rather than on Dataset identity. It audits verified root relocation and operator-confirmed rebinding, and isolates unverified rebinding with a new reuse domain. Before removable-volume production use, replace the current session-local device/inode evidence with the strongest supported platform volume identity and validate it on the filesystem matrix.
- The current implementation exposes discovery accounting completion separately from Work Record completion; the full `created` through `sealed` orchestration state machine is not implemented yet and must be introduced before Result sealing.
- Work Records currently commit only bounded inline structured results. Artifact-backed success remains unavailable until immutable publication and integrity verification are implemented.
- A complete scan must retain a run-owned removal fact before deleting an absent path from the current discovery view. Artifact or Evidence dependency reuse cannot begin until removal propagation and tombstone behavior have characterization tests.
- A fast sampled fingerprint is only candidate evidence. Any reuse whose false hit could affect Artifact semantics or Result integrity requires stronger producer-appropriate verification, including a negative test for an unsampled middle-byte change with preserved size and timestamps.
- `.albumignore` is an observed hint by default. Compression scope changes require an explicit run policy or operator decision; marker presence alone must not silently suppress Evidence or Source Item accounting.
- Source-read-only and offline claims must state the evidence level actually achieved. Unit tests establish only observed behavior on their exercised paths; sealing requires the policy, construction, enforcement, and observation evidence described above.
- Source identity evidence must balance false reuse against the cost of full hashing; benchmarks and corruption tests will choose the first implementation, not the public contract.
- Compression quality has no single objective metric. Frontier size, coverage, variation, user effort, and reopen frequency must be evaluated together.
- Some compression methods have population-wide dependencies. The implementation must report broad invalidation honestly rather than claiming locality it cannot prove.
- SQLite durability and locking vary by filesystem. Unsupported workspace capabilities require a local supported workspace or a future storage adapter, not silent degradation.
- Local models can be large and nondeterministic across hardware or library versions. Producer identity and relevant environment capture must be empirically sufficient without falling back to a global version stamp.
- A stronger future model must be able to replace extraction or compression strategies without changing Dataset, Source Item, Evidence, Result, or the read contract.

## Design acceptance criteria

This design is ready to move into implementation planning when reviewers agree that:

1. its accounting and navigation closure exactly match the accepted PreCheck contract;
2. each internal record has a justified independent responsibility or lifecycle;
3. validity depends on minimal semantic inputs rather than global versions;
4. the three-Result compression scenario is covered without rewriting history or duplicating low-level work;
5. stage ownership follows semantics and permits future local candidate models without admitting semantic decisions into PreCheck;
6. filesystem behavior is capability-based rather than POSIX-assumed;
7. every AI Album capability has an explicit destination and comparison class; and
8. the delivery slices can validate the architecture incrementally without establishing a second public contract; and
9. every Slice enforces the legacy-first entry and exit gates with inspectable characterization and comparison evidence.
