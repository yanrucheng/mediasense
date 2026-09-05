---
id: "eval-260823-1918C-fixture-coverage"
title: "Hong Kong Representative Fixture Coverage"
type: eval
status: active
created: 2026-08-23
updated: 2026-08-23
timezone: "Asia/Shanghai"
parent: "eval-260823-1918-ai-album-migration-baseline"
depends-on:
  - "eval-260823-1918A-legacy-system"
superseded-by: ""
tags: ["fixture", "regression", "coverage"]
---

# Hong Kong Representative Fixture Coverage

## Identity and authority

Fixture ID: `ai-album-hk-representative-v1`

The Git-tracked locator and compact identity record is `eval/fixtures/ai-album-hk-representative-v1.yaml`. The external package's own `README.md`, handoff document, manifests, checksums, and validation files are authoritative for how that package was derived and verified. This document is authoritative for how MediaSense may use the package and what conclusions it supports.

The package is immutable by version. If media, manifests, baselines, or checksums change, publish a new fixture version and redo validation. Evaluation output must be written outside the package.

## What the fixture contains

- Total logical package size: 1,759,421,497 bytes.
- 2,134 media paths: 1,851 JPG and 283 MP4.
- 2,133 readable media and one intentionally truncated invalid MP4.
- All 168 reconstructed legacy bundles and all 168 representatives.
- Representative split: 71 images and 97 videos; 148 representatives have GPS.
- Two GPX tracks plus isolated ARW and DNG fixtures.
- Re-keyed cached artifacts for deterministic historical replay.
- A copy of the 2026-05-09 production cache and clustered output.
- Machine-readable media and bundle manifests, expected metrics, SHA-256 inventory, verification script, and Docker replay script.

Most images are resized derivatives. Most videos are sparse proxies. The package preserves path/topology and selected metadata; it does not pretend to preserve all media characteristics.

## What it can establish

The fixture is suitable as the first migration gate for:

- Recursive traversal and explicit scope handling.
- JPG/MP4 paths, GPX discovery/use, and isolated RAW/DNG format cases.
- Same-stem, sidecar, adjacency, representative, and bundle-weight logic.
- EXIF/QuickTime timestamp and GPS extraction, including missing and abnormal cases.
- Corrupt-video localization and skip behavior.
- Cache identity, reuse, and invalidation interfaces.
- Candidate grouping and comparison with the legacy output tree.
- Planning experiments over real visual content and known contaminated groups.
- Functional differences between AI Album and MediaSense without routine access to the 1.09 TB source.

For AI Album's cached replay only, the strict historical baseline is 168 output thumbnails, 73 terminal groups, 8 named date roots, and an output tree matching the production baseline after removing content-hash suffixes.

For MediaSense, those values are observations, not correctness labels. MediaSense may intentionally change bundles, groups, names, and output structure if the ledger records why and evaluation supports the change.

## What it cannot establish

The package is insufficient evidence for:

- Multi-terabyte scan time, memory, inode, or cache-capacity behavior.
- Full decoding throughput for hundreds of gigabytes of original video.
- Audio, source bitrate, HDR/color fidelity, full frame streams, or DJI private telemetry.
- Full-volume RAW/DNG/LRF/AAC association behavior.
- Physical-drive disconnects, bad sectors, sleep/wake, or storage exhaustion.
- Cross-filesystem apply semantics.
- Provider rate limits, current model drift, or thousands of live API calls.
- Exact historic token spend or retry count.
- Semantic truth of legacy folder names.

Passing this fixture must never be reported as proof that a multi-terabyte production run cannot fail.

## Complementary evidence strategy

Use three evidence levels rather than creating many hand-curated large packages:

| Level | Evidence | Primary use |
| --- | --- | --- |
| Daily migration | HK representative v1 | Real topology, formats, legacy behavior, and planning quality |
| Generated scale/fault profiles | Reproducible generated fixtures outside Git | Hundred-thousand-path state, interruption, ENOSPC, collision, and EXDEV behavior |
| Milestone production test | Original source, read-only until an explicitly authorized apply rehearsal | Real I/O, full video decode, cache size, and overnight stability |

Generated fixtures should be defined by small tracked recipes and manifests. Generated bulk outputs remain untracked. The production source should be used only when the decision depends on properties that the representative or generated fixtures cannot preserve.

## Usage sequence

1. Resolve the package from the tracked descriptor rather than assuming Downloads paths.
2. Read the package `README.md` and `docs/RESEARCH-AND-HANDOFF.zh-CN.md`.
3. Run `./scripts/verify.zsh`; use `--deep` when media-container readability matters.
4. Keep `dataset/`, `baseline/`, and manifests unchanged.
5. Write all test output to a new external path.
6. Record the MediaSense commit, fixture ID/fingerprint, configuration, stage, and comparison class in the evaluation session.
7. Escalate to generated scale/fault evidence or the original source only when the remaining uncertainty can change the decision.

## Privacy and portability

The data owner authorized this fixture for internal testing without redacting faces, private scenes, GPS, or metadata. That authorization does not make the package public or suitable for arbitrary distribution. A material change in purpose, recipients, or publication scope requires renewed review.

The package contains no credentials. Receiving machines must provide any optional runtime credentials independently. Credential presence does not authorize external effects: MediaSense PreCheck must make zero Provider requests until a Human authorizes the exact frozen request batch and disclosed policy.
