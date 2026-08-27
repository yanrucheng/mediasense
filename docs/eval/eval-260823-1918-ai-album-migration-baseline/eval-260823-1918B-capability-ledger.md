---
id: "eval-260823-1918B-capability-ledger"
title: "Migration Capability Ledger"
type: eval
status: active
created: 2026-08-23
updated: 2026-08-27
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
| Thumbnail/copy/link/move modes | File-operation layer supported all modes; original mode moved files | `apply` | Preserve useful modes with stronger authorization and safety contracts | No overwrite/loss, same-filesystem behavior, receipts |
| Per-stage cache | Many results were reusable by flags and hashes | `precheck` | Preserve and strengthen: checkpointing, atomic writes, provenance, dependency-aware invalidation | Resume work, cache hits, interrupted equivalence |
| Usage monitoring | Optional log, absent from final production run | all | Intentionally change: relevant cost/operation accounting is part of stage results | Zero remote precheck calls, plan visual cost, apply operations |

## Current MediaSense implementation status

This table is deliberately narrower than the inventory above. A row marked `implemented` proves only the stated unit, not the whole legacy capability family or a complete PreCheck stage.

| Capability unit | Implementation status | Migration judgment | Current evidence | Remaining gate |
| --- | --- | --- | --- | --- |
| Recursive path discovery and extension classification | `implemented` | `preserved` | `src/mediasense/precheck/discovery.py`; fast discovery tests; verified Hong Kong package with 2,140 signed paths plus two explicit local `.DS_Store` items | Generated hundred-thousand-path throughput profile |
| Local discovery failure and symlink accounting | `implemented` | `intentionally_changed` | `tests/test_discovery.py` covers failed `scandir`, disappearing entries, loops, and boundary escape | Filesystem capability matrix and production fault injection |
| `.albumignore` observation and path accounting | `implemented` | `intentionally_changed` | Marker and descendants remain visible with `albumignore_*_observed` basis; Hong Kong RAW/DNG and GPX paths remain accounted | Compression-scope effect is `deferred`; marker presence alone is not exclusion authorization |
| RAW/DNG, GPX, sidecar, and AppleDouble discovery roles | `implemented` | `intentionally_changed` | Characterization tests and Hong Kong local-fixture assertions | Metadata/sidecar interpretation and GPX matching are `deferred` |
| Same-stem and M01/M02 filename association candidates | `characterized_only` | pending implementation comparison | `association_key` and `group_filename_candidates` characterization tests reproduce c90 filename rules | No accounting, Work, Evidence, or compression producer consumes these candidates yet |
| Resumable batched Working Run accounting | `implemented` | `intentionally_changed` | SQLite batch/checkpoint tests cover interruption, restart, localized failures, add/change reuse, and unavailable roots | Run-level cancellation, database fault injection, and scale profile remain `deferred` |
| Run-scoped source attachment and safe remount | `implemented` | `intentionally_changed` | AI Album c90 `argparser.py` expands input paths and `cache_manager.py` derives path/hash cache locations but has no durable run attachment or remount identity check. `source_attachment.py` and accounting tests bind locator plus observed root/volume identity to each Working Run; compatible relocation is audited, identity mismatch blocks, and operator-confirmed rebinding starts a new reuse domain | Replace session-local `st_dev`/inode evidence with the strongest supported platform volume identity where available; validate removable-volume behavior on the platform matrix |
| Filesystem capability observation | `implemented` | `not_comparable` | No equivalent source/workspace capability record was found in AI Album c90. Attachment tests persist observed mount writability, process writability, workspace replace behavior, same-filesystem status, case behavior, and symlink policy without probing writes on the source | SQLite durability/locking certification, Unicode normalization behavior, read-only mount enforcement, and non-POSIX platform coverage remain `deferred` |
| Normal-path removal detection | `implemented` | `intentionally_changed` | Run-owned removal facts retain the previous revision before the current source view becomes absent; tests cover deletion, rename, non-repetition, and deletion beside an unrelated unreadable subtree | Dependency propagation into future Work and Artifact records is `deferred` |
| Fast source-change candidate fingerprint | `implemented` | `intentionally_changed` | Small files are fully hashed; large files use five samples plus stat evidence and are explicitly labeled candidate-only | Exact Artifact-validity proof is `deferred` |
| Exact large-file content validity | `characterized_only` | pending implementation comparison | Negative test proves an unsampled middle-byte rewrite with restored size and mtime can retain the same candidate fingerprint | Strong producer-appropriate verification is mandatory before Artifact reuse or Result sealing |
| Semantic Work identity and direct dependency records | `implemented` | `intentionally_changed` | AI Album c90 `cache_manager.py` reuses path/hash-addressed files and eight cache flags, but has no dependency-complete Work identity. `work.py`, `_work_types.py`, and Work tests cover canonical order-independent descriptors, narrow producer identity, source revision inputs, exact upstream Work references, cross-run reuse, and transitive invalidation without an application-wide version key | Connect source change/removal facts and later Artifact integrity to dependency invalidation before real producers consume the substrate |
| Durable Work attempts, leases, retry, and checkpoints | `implemented` | `intentionally_changed` | AI Album c90 `clustering_engine.py`, `cluster/linear.py`, and metadata batching use fixed semaphores/batches and eagerly materialized coroutine lists but retain no durable attempt or lease. Work tests cover atomic cross-run claiming, restart recovery, stale-token refusal, renewal, bounded retry/backoff, terminal blocking, and retained attempt history | Run cancellation, database-lock fault injection, scheduler resource admission, and production throughput remain `deferred` |
| Immutable Artifact cache and publication | `deferred` | pending implementation comparison | Work success currently commits only bounded inline JSON plus an integrity digest; no Artifact table, file publication, or garbage collection exists | Exact source validity, atomic-or-equivalent publication, corruption recovery, and reachability-based cleanup must pass before Artifact-backed success |

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
- Extend the implemented discovery checkpoint and removal facts into Work/Artifact dependency invalidation and fault-injection experiments.
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
