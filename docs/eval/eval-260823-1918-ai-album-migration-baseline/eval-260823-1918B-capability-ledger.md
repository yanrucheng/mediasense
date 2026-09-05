---
id: "eval-260823-1918B-capability-ledger"
title: "Migration Capability Ledger"
type: eval
status: active
created: 2026-08-23
updated: 2026-09-01
timezone: "Asia/Shanghai"
parent: "eval-260823-1918-ai-album-migration-baseline"
depends-on:
  - "eval-260823-1918A-legacy-system"
superseded-by: ""
tags: ["migration", "capability", "parity"]
---

# Migration Capability Ledger

## Purpose

This ledger is the authoritative place to decide whether each material AI Album capability is preserved, intentionally changed, regressed, or not comparable in MediaSense. It prevents both accidental feature loss and blind reproduction of known legacy defects.

The capability inventory records target intent. The implementation-status table below separately records what has actually been delivered and evaluated; intent must never be reported as implementation completion.

## Difference classes

- `preserved`: the useful capability and relevant operating qualities remain available.
- `intentionally_changed`: behavior differs for a stated product, correctness, cost, or safety reason.
- `regression`: a useful legacy capability is unexpectedly missing or materially worse.
- `not_comparable`: MediaSense changes the problem boundary, so equality is not meaningful; evaluation uses a different criterion.

Implementation status is independent of the difference class:

- `implemented`: the stated capability unit is wired into the current MediaSense path and covered by the cited evidence;
- `characterized_only`: legacy or desired behavior is captured, but no production path consumes it yet;
- `deferred`: the capability unit is intentionally not implemented and remains a gate for dependent work.

`pending implementation comparison` is not a fifth difference class; it means there is not yet enough MediaSense implementation evidence to assign one of the four migration judgments.

## Capability inventory

| Legacy capability | Legacy behavior | MediaSense stage | Intended disposition | Required comparison |
| --- | --- | --- | --- | --- |
| Recursive media inventory | Walked a root and recognized a fixed format set | `precheck` | Preserve and broaden behind a stable inventory contract | Coverage, errors, unsupported files, scan throughput |
| `.albumignore` scope control | Required directory-local marker knowledge | `precheck` | Intentionally change: automatic discovery plus Agent-assisted scope confirmation; retain advanced override | Included/excluded paths, user effort, reproducibility |
| Explicit GPX argument | User supplied paths even when files were discoverable | `precheck` | Intentionally change: discover candidates, compute overlap/benefit, record adopted sources | GPS coverage, false matches, provenance, user questions |
| Same-stem and sidecar grouping | Associated JPG/RAW/LRF and name variants | `precheck` | Preserve the capability; make membership and rationale inspectable | Bundle membership, attachment coverage, false association |
| 60-second adjacent chaining | Chained adjacent groups without limiting total span | `precheck` | Intentionally change or bound after evaluation; never hide span | Over-merge/under-merge review, span and boundary metrics |
| Representative selection | Chose one preferred file per bundle | `precheck` and `plan` | Preserve stable identity; improve semantic evidence selection separately | Representative stability and coverage |
| Batch metadata extraction | Used ExifTool and configured tags | `precheck` | Preserve and strengthen provenance/error semantics | Value equality, source tags, failures, throughput |
| Coordinate reverse geocoding and nearby-place lookup | Reverse-geocoded each GPS-bearing bundle representative; AMap returned address/POI in one logical lookup, while Google called reverse and nearby endpoints and could switch provider/language across neighboring media | `precheck` producer with an internal provider-neutral kernel | Preserve post-compression lookup, datum conversion, address/POI normalization, sequential provider prediction, fallback, and rate limiting; intentionally change hidden singleton state, per-file cache identity, failure ambiguity, uncounted provider requests, and the temporary public/Plan Geo lifecycle | Logical query count after representative selection, actual provider requests, switching hit rate, normalized values, reuse, privacy, user confirmation, and failure/partial semantics |
| Timestamp fallback | Batch and single-item paths behaved differently | `precheck` | Intentionally change: unified typed candidates and confidence | `000114`, `260428`, missing-time fixtures |
| Video frame sampling | Up to 20 frames, roughly 10-second interval | `precheck` | Preserve the capability, leave sampling strategy open | Decode coverage, representative quality, cost |
| Thumbnail generation | Cached ordinary and high-resolution thumbnails | `precheck` | Preserve with versioned profiles and exact invalidation | Visual fidelity, cache hits, regenerated work |
| Asset/frame embeddings | ChineseCLIP arrays cached per representative/frame | `precheck` | Preserve local embedding capability; model remains replaceable | Neighbor quality, storage, throughput, version invalidation |
| Local content-sensitivity evidence | Local NudeNet/NSFW results supplied scores and sensitivity signals | `precheck` | Preserve the local evidence capability with explicit detector provenance, profile, score or quality, and completion/error semantics; the historical classifier, labels, and thresholds remain replaceable | Signal quality, false positives/negatives, local cost, reproducibility, version invalidation |
| Sensitivity-informed VLM routing | Sensitivity results directly selected local or remote processing paths | `plan` | Intentionally change: planning owns whether to ignore or use the signals and may choose all-local, all-remote, automatic routing, warnings, user confirmation, or another explicit policy; provider locality and data-egress effects must be visible and must not change silently | Policy adherence, authorization scope, provider locality, actual data egress, user effort, remote cost |
| Date/location/content clustering | Fixed hierarchy and thresholds | `precheck` and `plan` | Not comparable as a final truth; preserve local candidate computation, move organization judgment to Agent | Coverage, heterogeneity, outliers, visual budget |
| Per-representative caption | Most representatives captioned, usually remotely | `plan` | Intentionally change: budgeted, progressive Agent vision over selected evidence | Images read, image tokens, semantic coverage |
| Visual location inference | Often separate remote call, output used as label | `plan` | Intentionally change: return scoped candidates/evidence and escalate high-impact uncertainty | Wrong-label propagation, candidate quality, confirmations |
| Per-item title and cluster mode | 158 of 159 titles unique; mode usually unhelpful | `plan` | Intentionally change: Agent names the whole organization coherently | Duplicate/similar names, hierarchy clarity, user acceptance |
| Direct output-tree construction | Semantic guesses became filesystem paths early | `plan` then `apply` | Intentionally change: produce and freeze a complete plan before effects | Coverage, conflicts, reviewability |
| Thumbnail/link/move output modes and generic copy helper | `original` moved files; `link` created relative symbolic links for preview; `thumbnail` used generic metadata-copy code, while no user-facing original-copy branch existed | `plan`, `precheck`, and `apply` | Preserve move; move preview to Plan; preserve rendition production in PreCheck; defer persistent links and any new original-copy profile until they have independent accepted lifecycle semantics | No overwrite/loss, source retention, dangling-link behavior, authorization, rewind, receipts |
| Per-stage cache | Many results were reusable by flags and hashes | `precheck` | Preserve and strengthen: checkpointing, atomic writes, provenance, dependency-aware invalidation | Resume work, cache hits, interrupted equivalence |
| Usage monitoring | Optional log, absent from final production run | all | Intentionally change: relevant cost/operation accounting is part of stage results | Zero external calls for local-only runs; confirmed logical work versus actual provider calls for enabled external producers; plan visual cost; apply operations |

## Current MediaSense implementation status

This table is deliberately narrower than the inventory above. A row marked `implemented` proves only the stated unit, not the whole legacy capability family or a complete PreCheck stage.

| Capability unit | Implementation status | Migration judgment | Current evidence | Remaining gate |
| --- | --- | --- | --- | --- |
| Recursive path discovery and extension classification | `implemented` | `preserved` | `src/mediasense/precheck/discovery.py`; fast discovery tests; verified Hong Kong package with 2,140 signed paths plus two explicit local `.DS_Store` items; a generated 100,000-path stream completed in 6.389 s with 6,649,587 bytes peak Python-traced memory on the development host | Physical-directory and network-volume throughput remain environment-specific production measurements |
| Local discovery failure and symlink accounting | `implemented` | `intentionally_changed` | `tests/test_discovery.py` covers failed `scandir`, disappearing entries, loops, and boundary escape; accounting tests preserve both spellings and report both sides of an NFC collision without merging Source Items | Removable-volume and non-POSIX fault coverage remain platform-specific |
| `.albumignore` observation and path accounting | `implemented` | `intentionally_changed` | Marker and descendants remain visible with `albumignore_*_observed` basis; Hong Kong RAW/DNG and GPX paths remain accounted | Compression-scope effect is `deferred`; marker presence alone is not exclusion authorization |
| `.albumignore`-driven compression exclusion | `deferred` | `intentionally_changed` | c90 marker behavior is characterized, while the current MediaSense implementation deliberately treats markers as visible observations and does not parse them or alter producer/compression scope | Define an explicit Run policy, retained basis, and coverage behavior before enabling exclusion |
| PreCheck source-scope review and admission | `implemented` | `intentionally_changed` | `tests/test_precheck_scope_review.py` covers bounded factual trees, media-bearing `.similarity_cache`, legal hidden media, ordinary dotfiles, nested historical output, exact selection, stale-tree refusal, reuse, and unattended waiting | AI Album recursively scanned subject to `.albumignore`; MediaSense instead pauses before expensive Work, leaves semantic interpretation to the Agent/Human, and accounts excluded items without treating names or hiddenness as authority |
| RAW/DNG, GPX, sidecar, and AppleDouble discovery roles | `implemented` | `intentionally_changed` | Characterization tests and Hong Kong local-fixture assertions; metadata/sidecar interpretation and explicit GPX matching are implemented as dependency-complete Work | Wider RAW decoder/metadata coverage and automatic GPX adoption-benefit policy remain |
| Same-stem, temporal-chain, and bundle representative candidates | `implemented` | `intentionally_changed` | AI Album c90 unions same-directory stems, AppleDouble names and M01/M02 families, then transitively chains adjacent timestamps and selects JPG/JPEG, HEIC, PNG, MOV, MP4 in that order. `BundleCandidateProducer` preserves those candidate capabilities as dependency-complete Work, uses deterministic ordering, retains every member, reports total capture span and boundary paths, and marks a chain whose total span exceeds the per-edge gap. Missing time remains separate rather than becoming epoch zero. To prevent one transitive chain from creating unbounded Work, MediaSense splits it at a versioned member ceiling and records that limitation. Tests prove cross-run reuse and that a far source addition leaves an unchanged candidate reusable. | Compare representative stability, long-chain user-correction burden, and the bounded split on reviewed production collections |
| Resumable batched Working Run accounting and feedback | `implemented` | `intentionally_changed` | AI Album exposed transient terminal progress bars and logs but no durable per-item ledger or Run-level complete/partial state. MediaSense status now keeps Source Item accounting separate from a durable activity projection: coarse phase, computed/reused/failed/remaining/total Work, last effective progress, bounded error summaries, responsive-but-quiet versus suspected-stalled liveness, and resumable worker interruption. Synthetic SQLite/checkpoint, fake-clock, fault-injection, pause/resume, localized-failure, and publication tests cover the contract without replaying real media; generated discovery covers 100,000 paths. | Long-running real-media cancellation, hard process-kill, sleep/wake, and database/process crash soak tests remain. |
| Run-scoped source attachment and safe remount | `implemented` | `intentionally_changed` | AI Album c90 `argparser.py` expands input paths and `cache_manager.py` derives path/hash cache locations but has no durable run attachment or remount identity check. `source_attachment.py` and accounting tests bind locator plus observed root/volume identity to each Working Run; compatible relocation is audited, identity mismatch blocks, and operator-confirmed rebinding starts a new reuse domain. The installed macOS path now prefers a stable volume UUID and root inode, with an explicit session-local fallback. | Validate physical removable-volume reconnect and cross-machine behavior on the supported filesystem matrix; non-Darwin stable volume identity remains future work. |
| Filesystem capability observation | `implemented` | `not_comparable` | No equivalent source/workspace capability record was found in AI Album c90. Attachment tests persist observed mount writability, process writability, verified SQLite locking, workspace replace behavior, same/cross/unknown filesystem status, case behavior, and symlink policy without probing writes on the source. NFC-equivalent paths remain separate authoritative spellings and produce explicit non-blocking accounting issues. | Read-only mount enforcement plus removable-volume and non-POSIX certification remain platform-specific |
| Normal-path removal detection | `implemented` | `intentionally_changed` | Run-owned removal facts retain the previous revision before the current source view becomes absent; tests cover deletion, rename, non-repetition, deletion beside an unrelated unreadable subtree, and transitive invalidation of path-dependent Work. Bundle and compression group Work now declare exact member Source revisions plus direct upstream Work, so member change/removal invalidates only affected candidates. | Production-scale candidate membership and bridge-addition profiles remain |
| Fast source-change candidate fingerprint | `implemented` | `preserved` | AI Album commit `d10f42a` introduced a constant-I/O partial MD5 over the first, middle, and final 4 KiB and c90 retained it through `jinnang.MyPath.hash`. MediaSense preserves that bounded-read geometry for large files and full reads for files up to 12 KiB; characterization tests cover sampled and unsampled mutations. Internal hardening intentionally uses SHA-256 with size/offset domain separation, pre/post stat checks, and no path-only process cache. The fingerprint remains candidate-only. A generated sparse 1.5 TB candidate completed in 0.003 s on the development host. | Real-storage latency and exact Artifact validity cost remain separate measurements |
| PreCheck source-content validity | `implemented` | `intentionally_changed` | AI Album's bounded fingerprint is retained and hardened for ordinary-change detection. MediaSense Work binds source revision plus the versioned bounded fingerprint and verifies pre/post stat identity, avoiding repeated whole-file SHA-256 reads. This deliberately does not detect adversarial same-size, same-time changes outside sampled ranges. | Measure real-storage latency and observe false-reuse risk under the accepted non-adversarial threat model |
| Result-local source verification handoff | `implemented` | `intentionally_changed` | Eligible Source Items expose the actual replaceable verification profile, including its limitations, plus a locator-owned `source_root_ref` and root-relative path. Seal revalidates that profile without upgrading it to an exact-byte claim. Missing or limited PreCheck verification does not make an otherwise eligible item unselectable. | New verification profiles require profile-aware seal and consumer tests |
| Apply-side selected-source revalidation | `implemented` | `not_comparable` | Apply resolves every selected move through exact `result_ref + source_item_ref`, safely binds the current root, establishes a fresh full SHA-256 and size proof during preparation even when PreCheck supplied only limited or no verification, then rechecks root, destination, source object, bytes, and target absence at the effect boundary. Malformed exact evidence and exact mismatches fail closed. | Broader platform volume identity remains certification work |
| Authorized `move_originals`, recovery, and Receipt | `implemented` | `intentionally_changed` | The active Apply Run/Read Tools bind trusted Human confirmation to exact prepared content, use non-overwriting moves, durable intent and fact-based recovery, preserve partial truth, publish one immutable Receipt, and support whole-Run rewind. Same-filesystem Darwin APFS and cross-filesystem Darwin APFS-to-APFS have controlled evidence. | Real removable-media throughput, Linux filesystem certification, and broader filesystem pairs remain |
| User-facing Apply Skill | `implemented` | `not_comparable` | `mediasense-apply` explains prepared impact and Tool-owned states, obtains exact Human confirmation through trusted context, handles blockers/drift/partial recovery, reads Receipts, and guides newly authorized rewind without owning state or effects. Fixture workflows cover forward, blocker, drift, recovery, Receipt, and rewind paths. | End-user host/UI usability study remains |
| Original-file copy profile | `deferred` | `not_comparable` | c90 README said “Copy original,” but c90 code routes `original` to `safe_move`; `copy_with_meta` serves thumbnails/tests, may overwrite, and tolerates metadata failure. MediaSense does not invent duplicate-retention, authorization, or rewind semantics and does not place thumbnail output in Apply. | Requires a new Human-reviewed product purpose and lifecycle before implementation |
| Persistent relative symbolic-link profile | `deferred` | `intentionally_changed` | c90 creates relative symlinks as a preview before moving originals and reports failures only by printing. MediaSense preserves preview in Plan without filesystem effects and refuses to reinterpret link as a hard link. | Requires accepted dangling-link, source-volume rebinding, coexistence, authorization, and rewind policy |
| Semantic Work identity and direct dependency records | `implemented` | `intentionally_changed` | AI Album c90 `cache_manager.py` reuses path/hash-addressed files and eight cache flags, but has no dependency-complete Work identity. Work tests cover canonical descriptors, narrow producer identity, source revision and exact-content inputs, exact upstream Work references, cross-run reuse, source-driven transitive invalidation, and Artifact-integrity invalidation without an application-wide version key. Bundle and adaptive compression groups declare their exact Source membership and evidence Work rather than a Dataset-wide snapshot. | Measure descriptor/dependency-table cost for very large groups and introduce a semantically equivalent compact representation only if required |
| Durable Work attempts, leases, retry, and checkpoints | `implemented` | `intentionally_changed` | AI Album c90 `clustering_engine.py`, `cluster/linear.py`, and metadata batching use fixed semaphores/batches and eagerly materialized coroutine lists but retain no durable attempt or lease. Work tests cover atomic cross-run claiming, restart recovery, stale-token refusal, renewal, bounded retry/backoff, terminal blocking, retained attempt history, transitive invalidation, and cooperative cancellation before new external Work | Process/GPU crash soak tests and production media throughput remain |
| Durable Run control and confirmation breakpoint | `implemented` | `not_comparable` | AI Album c90 has no equivalent durable operator authority. `PrecheckRunTool` implements idempotent `start`, `status`, `pause`, `resume`, and `cancel`; exact frozen optional-work counts cause an automatic pause; matching decisions are fingerprint-bound; internal publication marks validation failure terminal, workspace-write failure resumable, and completion only after the sealed Result re-verifies. Public `seal` is rejected. | End-user host integration and long-duration restart/cancellation exercises remain |
| Internal configured Run orchestration | `implemented` | `intentionally_changed` | AI Album c90 groups before expensive media analysis but eagerly creates coroutine lists and controls each stage with fixed parallelism. MediaSense now preserves the useful cost funnel explicitly: all eligible media receive `index-v1` metadata, bundle candidates are built through a disk-backed ordering path, and a deterministic bounded representative/boundary frontier receives initial rendition/video/model Work. A generated production-path gate populates one million Source Items and index-metadata Work rows, then bounds planner RSS and pending-call cancellation; immutable Result payloads remain necessary `O(N)` authority. The internal directed-evidence seam is not exposed by the public Run contract. | Public directed-evidence authorization/Result/failure semantics, host worker lifecycle integration, long process/GPU fault soak, and real storage/codec/model throughput remain certification work |
| Selective manual rebuild and bounded resource admission | `implemented` | `intentionally_changed` | AI Album c90 exposes eight cache flags, clears related cache families procedurally, uses stage parallelism 4/1/1/4, frame-embedding batches of 8, configurable ExifTool batches, global model locks, and a coarse 12 GB startup gate. MediaSense rebuild selectors invalidate only matched Work and real dependents. Its Run-start resolver combines CPU, Darwin `vm_stat` available-memory evidence, verified physical-solid-state/remote/unknown source classification, enabled providers, and optional ceiling-only overrides; freezes the result; keeps unknown or remote source I/O at one lane; bounds pending work; and separates process, decoder, encoder, model, source-I/O, workspace-I/O, and network admission. Same-filesystem status remains a file-safety fact and does not imply fast storage. | Physical storage throughput and GPU-memory calibration remain production measurements |
| Immutable Artifact cache and publication | `implemented` | `intentionally_changed` | Artifact tests cover workspace-local unpublished files, copying producer output onto a publication-owned inode, complete-byte digest/size validation before transactional Work binding, atomic content-addressed publication, crash orphans, missing/corrupt detection, Work invalidation, restoration, cross-run reuse, and ENOSPC without partial success | Broader filesystem and concurrent-publication soak measurements remain |
| Workspace retention, quarantine, and repair | `implemented` | `intentionally_changed` | AI Album c90 repairs cache path collisions but has no Result-reachability retention authority. MediaSense derives reachability from existing sealed Result and active-Run references, pins their Work, removes only unreferenced invalidated Work/Artifact pairs, quarantines expired unpublished/orphan bytes, and restores a missing Artifact only from integrity-matching quarantined bytes. | Policy tuning for retention windows and concurrent maintenance remains operational follow-up |
| Ordinary and high-resolution still-image rendition | `implemented` | `intentionally_changed` | Pillow producer and c90 characterization tests preserve EXIF orientation, bounded aspect-preserving resize, no upscale, RGB JPEG output, source immutability, local terminal decode failure, exact source dependency, and immutable Artifact publication. Stable ordinary (640 px / legacy 360p role) and high-resolution (1920 px / legacy 1080p role) profiles create independently reusable Work; the ordinary rendition enters the default frontier and expands to the higher-resolution Evidence. Unlike c90's `keep_original_ratio=False` high-resolution path, both profiles preserve aspect ratio rather than risk stretching. The verified Hong Kong package now supplies a real representative JPEG test without modifying package bytes. | HEIF/RAW coverage, decoder matrix, color/HDR policy, throughput, and visual-fidelity comparison remain |
| Local video probe, sampled frames, key-frame candidate, and contact sheet | `implemented` | `intentionally_changed` | AI Album c90 samples at roughly ten-second intervals with a twenty-frame cap, batches frame embeddings by eight, and has no cross-stage process budget. MediaSense keeps each probe/frame/sheet as dependency-complete Work, initially runs video only for demanded bundle evidence, bounds concurrent FFmpeg processes through process/decoder/encoder lanes, and writes the resolved FFmpeg thread count into Work identity and command arguments. | Wider codec/container/orientation/HDR matrix, decode throughput, visual-quality/key-frame comparison, and production fixture coverage remain |
| Local image and video-frame embeddings | `implemented` | `intentionally_changed` | AI Album c90 lazily loads singleton ChineseCLIP under a global model lock and batches frame embeddings by eight. MediaSense keeps exact input Work, pinned model/runtime identity, dimensions, dtype, and normalization as semantic dependencies, and now gives compatible adapters a bounded true-batch interface while retaining one Work/Artifact/failure boundary per input. Large-group representative comparison uses an exact small-group path and a recorded bounded approximation beyond the configured comparison budget. | Run a pinned local ChineseCLIP model against representative media; compare vector shape, neighbor quality, CPU/GPU throughput, memory, and frame-key selection before claiming production parity |
| Pinned local model quality and throughput certification | `characterized_only` | `not_comparable` | c90 model identities and retained vectors provide a historical baseline; MediaSense adapters, semantic dependencies, fake-model orchestration, and failure behavior are implemented, but no reviewed MediaSense quality/throughput result from the pinned real models is recorded yet | Required before production-parity claims, not before three-stage contract integration |
| Local content-sensitivity observations | `implemented` | `intentionally_changed` | AI Album c90 runs NudeNet 3.4.2 plus `Falconsai/nsfw_image_detection` on high-resolution renditions, keeps maximum per-label scores, and derives inclusive `sensitive` plus threshold/3 `mild_sensitive` flags. Its fixture has 168 nonempty privacy files, including 16 mildly sensitive and 7 sensitive representatives; these are historical outputs, not truth labels. `SensitivityProducer` preserves the local detectors, raw labels/scores, and c90 threshold profiles, while making each detector/input/profile independent dependency-complete Work and projecting available or failed observations through the existing Read Contract. It intentionally eliminates the default-mode ambiguity where detector failure could be cached as an empty non-sensitive dictionary, and it never owns remote-routing policy. | Run both pinned local detectors on reviewed fixtures; measure false positives/negatives, CPU cost and throughput; validate video representative coverage and model-upgrade comparisons |
| Minimal local metadata, time, and GPS observations | `implemented` | `intentionally_changed` | AI Album c90 uses ExifTool `-G -n -api largefilesupport=1`, batches timestamp extraction (configured 200), then opens an `ExifToolHelper` context for each later metadata call over representatives. MediaSense defines the versioned `index-v1` profile, sends bounded multi-item commands through one Run-local stay-open process, preserves one Work/result per source, subdivides unattributed failures, and keeps source/sidecar provenance. For 4,009 healthy candidates at batch 200 this is 21 execute batches and one process start rather than roughly 4,009 per-item extraction starts; retries after malformed batches are data-dependent. A short installed-ExifTool test verifies reuse/restart/shutdown without a large fixture. | Wider camera/RAW/video matrix and physical-storage throughput remain |
| GPX adoption and time-based coordinate candidates | `implemented` | `intentionally_changed` | AI Album c90 parses time-bearing track segments, sorts points, applies a maximum time difference, and intends nearest-point or linear interpolation; its history fixed path loading, fatal missing inputs, matching limits, and diagnostics. `GPXMatchProducer` preserves the useful behavior with exact dependencies on every explicitly adopted GPX Source Item and the upstream metadata Work, distinguishes embedded-GPS `not_applicable`, missing capture-time `not_checked`, no match, full failure, and partial input failure, and projects Result-local provenance for all adopted tracks. It intentionally fixes c90's right-index interpolation defect and localizes one malformed GPX instead of aborting all tracks. | Automatic adoption/benefit policy, production HK track comparison, clock-offset candidates, multi-media batching, and throughput remain |
| Minimal Evidence frontier and immutable Result read path | `implemented` | `intentionally_changed` | Result tests cover exact `accounts_for` for the enumerated boundary, partial coverage when discovery leaves an unenumerated region, entry Evidence, all five relationship meanings, many-to-one and one-to-many boundaries, normal/exception navigation closure, unresolved readiness blocking, atomic seal publication, exact `result_ref`, pagination, current-Run Artifact provenance and final pin revalidation, read-only integrity checks, and `inspect`/`traverse` schema conformance. Seal rechecks inline supporting Work as well as visible Artifact Work; Run-level tests cover automatic publication, validation refusal, ENOSPC blocking, retry adoption after a crash before registration, reuse after a crash before Run completion, and absence of a public seal action. Adaptive Results expose representative, boundary, outlier and conflict roles using existing observations and relations. | Large-page latency and additional filesystem-specific fault profiles remain |
| Adaptive local compression and multiple Results | `implemented` | `intentionally_changed` | AI Album c90 applies a fixed date → 3,000 m/500 m location → cosine-content hierarchy with distance `0.311`, minimum weights and opaque final naming. MediaSense preserves local temporal, WGS84 spatial, cosine-content and c90 top-half representative signals but treats them as replaceable candidate methods. A declared target ranks adjacent boundaries, retains limitations and axis conflicts, emits exact-member group Work, and projects challengeable `represents`/`expands_to` paths without naming or final organization judgment. Lower-level Work is reused across profiles. The public-Run generated acceptance seals three immutable Results with entry frontiers `500 → 3 → 200` in 62.00 s on the development host, reuses the same 500 low-level rendition Work records and Artifact references, and leaves source bytes unchanged. Result comparison reports source-boundary, entry-count, compression-ratio, shared-Artifact and identical-group metrics from sealed projections without exposing Work. | Compare compression quality, hidden variation, group balance, reopen/user-correction burden and Hong Kong legacy groups; complete production-scale profiling |
| Coordinate reverse geocoding and nearby-place lookup | `implemented` | `intentionally_changed` | AI Album c90 post-representative AMap/Google source and tests establish WGS84/GCJ02 conversion, one-request AMap address/POI lookup, sequential provider/language continuity, fallback, and rate limiting. MediaSense preserves those useful behaviors through the internal provider-neutral kernel. `ReverseGeocodeProducer` deduplicates exact coordinates, checks provider availability before authorization, binds trusted Human confirmation to the frozen disclosure, restores routing continuity across reused Work, and projects provider attempts, request counts, datum, language, no-result/failure, provenance, and qualifications into immutable Result Evidence. Plan and the removed public Geo Tool perform no acquisition. | A user-confirmed live-provider smoke, provider-policy review, switching-quality measurement, and real quota/error observations remain environment-specific |
| Live reverse-geocode deployment certification | `characterized_only` | `not_comparable` | c90 source/tests and the current fake-provider suite characterize routing, fallback, counts, authorization, and failure behavior without issuing a live request in this acceptance run | Confirm provider terms, quotas, retention, keys, regional coverage, route quality, and observed billing in an explicitly authorized production check |

### 2026-09 PreCheck scale correction

- `preserved`: AI Album's useful funnel—batch enough metadata to group first,
  then create thumbnails, video evidence, embeddings, and sensitivity evidence
  for representatives—is restored. Per-item caching and local model reuse remain.
- `intentionally_changed`: MediaSense uses one Run-local stay-open ExifTool,
  dependency-complete Work, item-local failure subdivision, bounded model
  batches, exact Apply-time byte proof, and host-resolved resource lanes instead
  of AI Album's cache flags, per-call helper lifetime, global model locks, and
  fixed 12 GB admission gate.
- `regression`: the earlier MediaSense orchestrator ran rendition, video,
  embedding, and sensitivity stages for all media before bundling, launched
  metadata extraction per item, repeatedly required full source hashes, and
  defaulted to two workers with one process/codec lane. Those behaviors explain
  why it could be much slower than AI Album despite the smaller candidate count;
  they are removed by `scale-precheck-execution`.
- `not_comparable`: durable Run/Work leases, dependency-scoped invalidation,
  immutable Result/Artifact validation, exact Apply revalidation, and explicit
  source/workspace safety have no equivalent guarantee in AI Album.

For 4,009 healthy metadata subjects and the default batch ceiling of 200, the
new path issues 21 ExifTool execute requests through one stay-open child
process. Recursive subdivision adds calls only for failing batches. Exact
decode/encode and video subprocess counts cannot be inferred without the media
kind and bundle distribution: each demanded still creates one ordinary
rendition, plus one high-resolution rendition when a local model is enabled;
each demanded video creates one ffprobe process and at most three ffmpeg frame
processes under the current default. Undemanded bundle members remain present
in Result accounting but create none of those visual calls.

Increasing `max_workers` from two to eight alone would not have fixed the old
shape: it would retain per-item process startup, all-item decode/model demand,
repeated source reads, eager task construction, and quadratic representative
comparison. The current design reduces and batches work first, then uses
resolved concurrency only within explicit CPU, memory, process, codec, model,
and I/O ceilings.

## Acceptance dimensions

Every migrated capability must be evaluated on the dimensions that can change the product judgment:

- Functional coverage and correctness.
- Local compute, I/O, memory, cache growth, and wall time.
- Remote requests, image inputs, provider-reported tokens, and monetary cost.
- Reuse after restart and after a localized input/profile change.
- User knowledge and confirmation burden.
- Visibility of uncertainty, omissions, and failure.
- Source integrity, collision behavior, recoverability, and auditability.

An implementation is not accepted merely because it reproduces one legacy directory tree. Conversely, a changed directory tree is not a regression when the change follows an approved plan and fixes an evidenced legacy failure.

## Stage development gate

Before implementing a stage's production Tool or Skill, preserve these links:

```text
human-reviewed handoff example
  + runtime/interruption/failure semantics
  -> minimal formal contract
  -> Tool implementation and tests
  -> Skill guidance and Agent evaluation
  -> ledger comparison and acceptance judgment
```

The three stage tracks may develop concurrently using manually approved fixtures. Downstream work must not depend on unversioned upstream internal databases or caches.

## Open work that can change priorities

- Quantify bundle purity and missed grouping on high-weight bundles.
- Compare representative strategies at 32, 64, 128, and 256-image planning budgets.
- Measure whether contact sheets reduce API turns, visual tokens, user effort, or only request overhead.
- Measure dependency-descriptor and invalidation cost for very large population-wide candidate groups.
- Define plan completeness, freeze, amendment, and approval semantics through a manual example.
- Define apply transaction, recovery, same-filesystem move, and cross-filesystem refusal through a manual example and generated fault fixtures.

These are decision-bearing unknowns. Do not select final schemas or frameworks until the relevant experiment or example distinguishes the alternatives.

## Existing components to evaluate before building

These are implementation candidates and capability baselines, not permanent architecture commitments:

- ExifTool already provides mature batch image/video metadata extraction. MediaSense's distinctive responsibility is the provenance, confidence, error, and incremental-state contract around it.
- FFmpeg and ffprobe already provide video decoding, probing, sampling, and scene signals. MediaSense should not build a general video decoder.
- ImageMagick montage can produce labeled contact sheets. Its effect on actual provider-reported visual tokens must be measured rather than assumed from the reduction in request count.
- CLIP/SigLIP-family embeddings, FAISS, scikit-learn, and HDBSCAN are replaceable candidates for local similarity, indexing, and grouping. Their names should not enter stage contracts.
- FiftyOne provides similarity, duplicate, uniqueness, representativeness, and clustering capabilities and is useful as a research benchmark or prototype. It should not become a required heavy runtime dependency without an explicit comparison.
- Immich, PhotoPrism, and digiKam demonstrate that persistent media indexes, thumbnails, embeddings, and similarity search form a stable problem domain. They are full applications, not direct MediaSense Tool contracts.

The currently inspected machine already has ImageMagick 7.1.1-47, ExifTool 13.25, FFmpeg 7.1.1, ffprobe, Quick Look, and `mdls`. Availability on one development host is not a portability guarantee.

## Planning-budget baseline from the legacy tree

The historical tree provides useful upper-bound scenarios even though its groups are not semantic ground truth:

| Sampling policy | Images presented to the Agent |
| --- | ---: |
| One image from each of 28 date/location macro groups | 28 |
| Up to two per macro group | 46 |
| Up to three per macro group | 61 |
| One image from each of 73 leaf groups | 73 |
| Up to two per leaf group | 116 |
| Up to three per leaf group | 140 |

This suggests that a first semantic pass on the Hong Kong fixture can plausibly start at 32-64 images and expand only heterogeneous or uncertain regions. It does not establish that every dataset, especially a hundred-thousand-item collection with many independent events, can be understood with the same fixed count.

The stopping rule should combine budget, mass/quality-weighted coverage, residual uncertainty, and marginal information gain. A fixed `N images per cluster` rule is not sufficient.
