---
id: "eval-260823-1918B-capability-ledger"
title: "Migration Capability Ledger"
type: eval
status: active
created: 2026-08-23
updated: 2026-08-25
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

The table records current intent, not implementation completion. Update the status and evidence when a MediaSense capability is built and evaluated.

## Difference classes

- `preserved`: the useful capability and relevant operating qualities remain available.
- `intentionally_changed`: behavior differs for a stated product, correctness, cost, or safety reason.
- `regression`: a useful legacy capability is unexpectedly missing or materially worse.
- `not_comparable`: MediaSense changes the problem boundary, so equality is not meaningful; evaluation uses a different criterion.

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
- Define precheck checkpoint and invalidation semantics through interruption experiments.
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
