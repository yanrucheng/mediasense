## Context

PreCheck has the right durable authorities but an inverted cost shape. Accounting, Work identity, immutable Artifacts, Run control, Result publication, and resource admission already own the facts needed for safe recovery. The current orchestrator nevertheless demands metadata and visual Work for nearly every media candidate before bundling, starts ExifTool once per item, repeatedly computes full-file SHA-256 inside producer hot paths, and materializes or rescans whole-Run collections. Fixed capacities make every major media phase effectively serial.

AI Album is historical evidence, not authority. Its reusable lessons are early representative reduction, multi-path ExifTool calls, long-lived process protocol, and frame-model batching. Its eager coroutine lists, dependency-blind caches, global locks, coarse 12 GB gate, partial wildcard caches, and missing durable recovery are not inherited.

The Human has confirmed two product boundaries:

- PreCheck protects against ordinary source changes, not an adversary that changes bytes while restoring size, timestamps, inode-visible identity, and other observations.
- Initial expensive visual evidence may cover representatives, useful boundaries, and explicit exceptions rather than every accounted Source Item.

Source media remains read-only. Remote and billable access remains disabled by default. Apply retains deterministic exact-byte gates for selected filesystem effects.

## Goals / Non-Goals

### Goals

- Make cold metadata extraction amortize external-process startup while preserving one semantic outcome per Source Item.
- Reduce expensive metadata detail, rendition, video, and model demand before those producers run.
- Make unchanged PreCheck reuse avoid full-byte source reads in ordinary operation.
- Bound queued work and memory independently of total Dataset cardinality.
- Resolve safe, useful resource capacities from the host and storage context and persist the effective values with the Run.
- Remove scale-critical `O(N^2)` behavior and establish acceptance evidence through one million generated Source Items without running paid, remote, or fresh model work.
- Preserve existing Run, Work, Artifact, Result, Dataset, cancellation, failure-isolation, and source-read-only authority.

### Non-Goals

- A scheduler service, daemon, plugin system, registry, new public Tool, new Skill, or separate batch-state authority.
- Adversarial tamper detection inside PreCheck when all ordinary file observations are deliberately restored.
- A universal hardware benchmark, one fixed worker count, or user-facing tuning of implementation-level batch sizes.
- Changing Plan interpretation authority, Apply semantic decisions, or source organization behavior.
- Reproducing AI Album cache keys, eager task fan-out, model downloads, or remote-call policy.
- Running the Hong Kong fixture, the earlier long benchmark, fresh local models, or network/provider calls as part of this change.

## Backward Compatibility Policy

| Attribute | Value |
|-----------|-------|
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumers. BC mechanisms are prohibited to avoid code debt. Clean-slate deployment is assumed. The private schema and execution semantics are replaced directly; no schema upgrader, version router, dual-write path, old executor, behavior feature flag, old workspace reader, or old Result adapter will be retained. Existing files may remain historical evidence outside the supported runtime, but using the new implementation requires a fresh workspace and Run.

## System Context and Authority

The change retains these authoritative homes:

- Dataset accounting owns Source Item scope, locator binding, revision, ordinary-change observations, and availability.
- Work records own semantic demand, item outcome, lease, retry, and dependency identity.
- Artifacts own immutable derived bytes and their integrity.
- Run configuration owns the resolved execution profile and resource ceilings.
- Result owns the immutable evidence projection and coverage claims.
- Apply preparation/execution owns exact verification of selected filesystem effects.

Batch membership, queue position, ExifTool process identity, adaptive heuristics, and pipeline scheduling are replaceable execution methods. They do not become durable product entities.

## Decisions

### 1. Order work by information cost

The orchestrator uses four dependency layers:

1. Account every source path and retain ordinary-change observations.
2. Produce an index metadata profile for all eligible source media in bounded batches.
3. Build bundle candidates and derive an execution demand set from a deterministic bounded sample of representatives, distinct temporal boundaries, and explicit internal exceptions.
4. Produce detailed metadata when demanded, visual/video Artifacts, optional local-model observations, and compression only for that demand set.

Accounting coverage is never reduced. A Source Item without initial visual Work remains present in the Result's Source Item authority. Directed evidence exists only as an internal orchestration seam; the public Run request does not expose it until authorization, Result binding, and failure semantics receive a separate contract review.

The initial index metadata profile contains only facts required for stable grouping and routing: source media type, capture time, orientation, numeric coordinates where present, and the provenance needed to challenge them. Richer fields remain an optional profile of the same metadata capability; a new Tool or public artifact type is unnecessary.

Alternative rejected: preserve the current phase order and merely raise worker counts. It retains all-item decode/model demand and cannot scale even with ideal parallelism.

### 2. Keep per-item Work semantics while batching provider execution

Metadata Work remains one Work identity and outcome per source subject. The producer gains a bounded multi-item operation that prepares item specs and leases, groups ready items into batches, invokes an internal ExifTool adapter, maps returned rows to subjects and sidecars, and commits each item outcome independently.

One Run owns a small number of long-lived ExifTool lanes. Each lane uses ExifTool's stay-open protocol and accepts bounded batches constrained by item count and encoded command size. Process identity and batch membership are ephemeral. The ExifTool version is observed once and remains a Work environment dependency.

If a batch fails without trustworthy per-item output, the producer subdivides it until it isolates failing items or reaches the single-item boundary. One heartbeat renews every still-active item lease across a long provider call and all recursive subdivisions. Successful siblings commit and leave that heartbeat set immediately; cancellation converts every remaining lease to retryable state. If the heartbeat itself fails, the producer stops it, transitions every still-owned active lease to retryable failure immediately, and re-raises the renewal error; a lease already recovered after expiry is accepted as converged rather than overwritten. A crashed process is replaced inside the same lane, while an abandoned worker's leases expire and existing Work recovery remains authoritative.

Alternative rejected: one batch Work for many Source Items. It would conflate semantic identity, retry, failure, provenance, and incremental invalidation merely to match an implementation convenience.

Alternative rejected: a standalone ExifTool service. One stage currently owns the only proven consumer and no independent authority or lifecycle exists.

### 3. Use ordinary-change identity in PreCheck and exact bytes at Apply

Accounting revision, pre/post stat identity, and the existing bounded source fingerprint are sufficient to detect supported ordinary changes during PreCheck. A producer binds Work to the observed Source revision/fingerprint, checks identity immediately before and after its read, and invalidates affected Work if the observations drift.

PreCheck no longer computes full SHA-256 merely to start or reuse every producer. A `source_content_verification` observation may still describe an exact or limited profile when deliberately produced, but its absence does not make an otherwise eligible Source Item unselectable by Plan.

Apply resolves selected `result_ref + source_item_ref` values, computes a fresh exact byte proof during preparation, persists it in the existing prepared operation record, and rechecks it at the authorized effect boundary. That fact is Apply-Run safety state, not Source Item identity or a new source authority.

Alternative rejected: cache one full SHA-256 per every Source revision during PreCheck. It removes repeated reads but still requires a complete byte scan of a million-item Dataset before Plan has selected any filesystem effect.

### 4. Index association and page demand through existing stores

The accounting representation stores the deterministic filename association key as a derived column and indexes `(run_id, association_key)`. Metadata batching obtains subjects and sidecars by ordered pages or bounded joins rather than calling `get_run_items()` for each subject.

The orchestrator enumerates Source Items, Work demand, and outcomes in pages. Only the bounded executor window, current provider batch, one bounded bundle group, and the configured evidence frontier are materialized. Bundle ordering and metadata joins use a disposable SQLite spool rather than a whole-Dataset Python map. Immutable Result construction is the explicit exception: its canonical Source Item, Evidence, and relationship sequences necessarily scale with published facts and are not execution-coordination state.

Alternative rejected: construct one in-memory association dictionary as the final design. It fixes 4,000-item behavior but duplicates authoritative Run state and keeps memory proportional to the whole Dataset.

### 5. Resolve resource ceilings, do not expose method knobs as product contract

The runtime derives an effective resource profile from operator ceilings plus observable host facts: logical CPU count, supported available-memory probes, independently established source-storage evidence, available accelerator identity/memory when explicitly configured, and enabled producers. Source/workspace same-filesystem status is retained for file-safety decisions and is not storage-performance evidence. The resolved numeric `ResourceBudget`, provider batch bounds, FFmpeg thread allowance, storage class, and storage evidence are persisted in the existing Run execution configuration for reproducibility.

Initial policy is deliberately bounded:

- remote or unknown source storage starts with one source-heavy lane;
- a Darwin source identified by `diskutil` as physical solid-state storage may admit multiple independent metadata/decode/encode lanes within memory and CPU ceilings; non-solid-state, virtual, failed, unsupported, remote, and unknown observations remain conservative;
- FFmpeg process count and threads per process share one CPU ceiling;
- model residency remains one slot per loaded model, while inference batch size is bounded by the configured device budget;
- workspace writes remain separately bounded from source reads.

Worker count, batch size, and semaphore topology remain internal methods. Advanced overrides may cap effective resources but cannot enable network work or exceed an authorization boundary.

Alternative rejected: copy AI Album's `4/1/1/4`, batch 200, or 12 GB gate as universal defaults. They are benchmark inputs without a capacity model.

### 6. Remove unbounded and quadratic scale paths

The supported main path has no whole-Run rescan per item. Filename association and temporal ordering are `O(N log N)` or better with bounded memory outside database indexes. Bundle representative lookup uses direct maps or indexed rows rather than scanning all items per component.

Embedding representative selection does not perform all-pairs comparison over an unbounded compression group. It uses a bounded candidate sample, streaming centroid/nearest candidates, or another replaceable method with an explicit maximum comparison budget. Exact c90 top-half comparison remains permitted only for groups below that bound.

Generated acceptance populates one million Source Item rows and one million index-metadata Work rows, then exercises the production metadata-to-bundle planner, bounded evidence selector, and pending-call cancellation path. These non-authoritative coordination structures are bounded by page, group, evidence, and pending limits. The immutable Result's Source Item and evidence payload is necessary `O(N)` authority and is tested for correctness separately; it is not included in the bounded-coordination claim. The generated gate does not claim real-media byte throughput, decoder quality, model throughput, or storage-device performance.

On the 2026-09-01 Darwin development host, the supported probes reported 18
logical CPUs, 17,421,549,568 available bytes from `vm_stat`, and a physical
solid-state source from `diskutil`. With no operator ceiling and network disabled,
the resolver produced 8 workers, 16 pending calls, 8 CPU slots, 4 source-I/O,
workspace-I/O, process, decoder, and encoder slots, one ExifTool slot, one model
slot, 4 GiB admitted memory, 1 GiB temporary space, and zero GPU/network capacity.
This is a point-in-time observation, not a portable default or a storage-throughput
certification. The one-million-row generated gate completed in 41.41 seconds and
measured 64,077,824 bytes peak RSS in the fresh planner process, below its 256 MiB
ceiling, after replacing an unindexed join that exhibited scale-critical growth.

### 7. Keep observability in existing Run and Work projections

Existing activity projection and Work outcomes report phase totals, computed/reused/failed/remaining counts, and liveness. Performance acceptance may additionally derive process starts, batch sizes, bytes read, queue wait, and resource peaks from test instrumentation and bounded runtime diagnostics. No second progress ledger or permanent metrics artifact is introduced.

## Risks / Trade-offs

- [Ordinary-change checks can miss adversarial same-stat byte replacement] → The accepted threat model excludes it; Apply still computes and rechecks exact bytes for selected effects, and Result limitations remain explicit.
- [A failing ExifTool batch can obscure which item failed] → Require trustworthy row mapping; otherwise subdivide the batch to single-item outcomes with bounded attempts.
- [Early representative reduction can hide useful variation] → Include distinct boundaries and explicit exceptions by default and retain complete accounting. A future public directed-evidence request requires its own reviewed authorization, Result-binding, and failure contract; the current selector remains internal only.
- [Host heuristics may choose poor concurrency on unusual storage] → Start conservatively for unknown/remote storage, persist effective values, expose ceiling overrides, and measure queue wait and throughput before widening.
- [SQLite write contention can erase concurrency gains] → Claim and commit bounded item groups, keep media work outside transactions, and test contention before increasing lanes.
- [Fresh-start replacement invalidates private Work and Results] → Fail clearly on an incompatible workspace, leave source media untouched, and require creation of a fresh workspace rather than carrying compatibility branches.
- [A million generated items do not prove terabyte media throughput] → Report the evidence boundary and require later explicitly authorized physical-storage milestones.

## Migration Plan

1. Add characterization and count-based performance tests for the current metadata, proof, association, and scheduling paths.
2. Add indexed association data and paged accounting/Work enumeration in a replacement private SQLite schema; reject incompatible workspaces with a clear fresh-start recovery instruction.
3. Introduce the Run-local ExifTool adapter and batch metadata producer with per-item Work outcomes, subdivision, cancellation, and process recovery tests.
4. Replace repeated full-byte PreCheck proof demand with revision/fingerprint dependencies and pre/post ordinary-change checks; move selected exact-proof establishment to existing Apply preparation state.
5. Reorder orchestration around index metadata, bundle candidates, and the bounded representative/boundary/exception demand set.
6. Resolve and persist host-aware resource ceilings; separate source I/O, workspace I/O, external process, codec, and model admission while retaining one bounded executor authority.
7. Remove remaining eager and quadratic paths, then run generated 100,000- and 1,000,000-item coordination acceptance plus short local ExifTool/media micro-tests.
8. Update migration evidence and product/design documentation, run focused and full non-live tests, Ruff, and strict OpenSpec validation.

Rollback during development is a normal code revert plus recreation of private workspaces. No runtime downgrade or dual-schema rollback path is maintained.

## Open Questions

None at the product boundary. Exact provider batch sizes, lane counts, storage heuristics, bounded representative algorithms, and diagnostic presentation are implementation choices constrained by the requirements and acceptance evidence.
