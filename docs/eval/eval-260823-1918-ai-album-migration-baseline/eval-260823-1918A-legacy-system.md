---
id: "eval-260823-1918A-legacy-system"
title: "Legacy System and Hong Kong Run"
type: eval
status: active
created: 2026-08-23
updated: 2026-08-23
timezone: "Asia/Shanghai"
parent: "eval-260823-1918-ai-album-migration-baseline"
depends-on: []
superseded-by: ""
tags: ["ai-album", "legacy", "hong-kong"]
---

# Legacy System and Hong Kong Run

## Reconstructed production run

Multiple debugging and production-like runs occurred from 2026-05-07 through 2026-05-09. The last identified production command started at 2026-05-09 12:21:36 Asia/Shanghai:

```zsh
drun chengyanru/ai-album:3.0.0 \
  ./260501-HK美食之旅 \
  -ot thumbnail \
  --gpx-files ./260501-HK美食之旅/a-files/GPX/* \
  --thumbnail-resolution 720p
```

The current production clustered directory was created by that v3.0.0 run. Its output mode was thumbnail, so it did not move original media.

## Actual processing path

1. Recursively scan the input while applying directory-local `.albumignore` markers. GPX files are passed separately and may reside under ignored directories.
2. Group same-stem and sidecar-related files, including RAW/JPG relationships and `M01`/`M02` variants.
3. Choose a timed member, sort groups by time, and chain adjacent groups separated by at most 60 seconds into bundles.
4. Select one representative with a format priority that favors ordinary images before video.
5. Cache metadata, thumbnails, embeddings, captions, privacy classification, titles, locations, and translations as configured. Video processing samples at most 20 frames at approximately 10-second intervals and selects a representative using frame embeddings.
6. Cluster by date, then 3,000 m coarse location, then 500 m fine location, then image distance `0.311`, with weight thresholds.
7. Generate or retrieve semantic titles and locations, derive directory names, and materialize the output tree.

Important implementation evidence remains in these AI Album files:

- `src/media_libs.py`: grouping, sidecars, time chaining, representative selection, ignore behavior.
- `src/content_analysis/clustering_engine.py`: hierarchical clustering and thresholds.
- `src/media_processors/video/video_processor.py`: video frame selection.
- `src/metadata/metadata_loader.py` and `src/metadata/timestamp_service.py`: metadata, GPX, and differing timestamp fallback paths.
- `src/media_processors/llm/llm_processor.py`: embedding, privacy, caption, location, title, and translation orchestration.
- `src/cluster/async_file_ops.py`: copy, link, and move behavior.

These paths are historical evidence, not a required MediaSense module layout.

## Quantitative funnel

The fixture handoff records 4,896 regular files in the original source tree. The production grouping scope contained 4,365 members, including 3 AppleDouble entries; 4,362 non-AppleDouble members are represented in the bundle manifest. There were 2,134 supported image/video paths, one of which was intentionally unreadable.

```text
4,365 grouping members
  -> 2,134 supported media paths
  -> 168 bundles and representatives
  -> 73 leaf output groups
  -> 28 observed date/location macro groups
```

Relevant compression ratios:

- `2,134 -> 168`: 12.7x at the supported-media-to-representative boundary.
- `4,365 -> 168`: 26.0x when active sidecars and other bundle members are included.

Representative types were 71 JPG and 97 MP4. Of 168 representatives, 148 had GPS and 20 did not. The final tree had 8 date roots, 26 second-level directories, 50 third-level directories, and 73 leaf groups; 30 leaf groups contained only one representative.

Bundle structure was highly skewed:

- Median supported-media count: 2.
- Mean supported-media count: 12.7.
- Maximum supported-media count: 201.
- Median total member count including sidecars: 5.
- Maximum total member count including sidecars: 402.
- 35 bundles with at least 20 supported media covered 79.2% of supported media.
- 13 bundles with at least 50 supported media covered 46.5%.
- Bundle time-span median was 3 seconds, P90 was 119 seconds, P95 was 182 seconds, and maximum was 322 seconds.

The maximum bundle was represented by `DSC00594.JPG`; it held 201 supported media and 402 total members across 322 seconds. These figures show strong compression and a material over-merge risk.

## Reconstructed model work

The production cache contained 168 each of metadata, asset embedding, privacy result, ordinary thumbnail, and high-resolution thumbnail. It contained 159 valid captions, 165 location results, 159 titles, and no translations. It also contained 97 video-frame directories with 1,369 frame images and 1,369 frame embeddings.

Based on routing and successful artifacts:

- Approximately 143 captions used a remote visual model; approximately 16 used local BLIP.
- Approximately 133 location results used remote image analysis; 15 used local-caption text analysis; 17 were empty.
- Remote caption and remote image-location work overlapped on 127 assets.
- The successful artifacts therefore imply roughly 276 remote visual analyses spanning 149 unique representatives.
- Text-model artifacts include roughly 159 titles and 15 caption-based location decisions.

These are reconstructed lower-bound proxies. Retries and exact token/cost totals are unknown because the final production command did not enable the usage log.

## What worked well

- Large reduction before remote model use.
- Batch metadata processing and reusable per-stage caches.
- Same-stem, sidecar, and time-adjacent logical grouping.
- Local video-frame sampling and embedding-based representative choice.
- Local privacy routing for some sensitive content.
- No need to copy the full source collection into a work area before analysis.

These are capabilities to preserve, subject to contract and correctness improvements.

## Material failure modes

### Input preparation leaked into the user experience

Users needed to remember GPX command-line arguments and `.albumignore` mechanics. Forgetting them could materially alter results without a clear preflight explanation. MediaSense should discover and evaluate such inputs, then let the Agent explain consequential choices in ordinary language.

### A local semantic error could propagate globally

The pipeline could infer one nearby restaurant incorrectly and reuse that name for a broad cluster. In the production tree, `260505/2-The Steak House Regent Hong Kong` held 31 representatives covering multiple recognizable areas and events. All 34 representatives from that day had GPS; the issue is consistent with 3,000 m chaining and cluster-level naming, not missing GPS.

### Naming was mechanically embedded in the pipeline

Among 159 valid titles, 158 strings were unique and one appeared twice. Taking a mode across a cluster therefore usually approximated taking an arbitrary first title while paying per-representative caption/title cost. Naming did not consider the whole proposed album tree or user preference.

### Time failures could masquerade as dates

The batch metadata path could return `0.0` when timestamp extraction failed, while a separate single-item service had filename fallback logic. The output roots `000114` and `260428`, plus one metadata record without a time, are important evidence that provenance and confidence must be explicit. They must remain fixtures until the intended behavior is decided.

### Completion and quality were underreported

The output primarily exposed a directory tree. It did not provide sufficient evidence about bundle membership, boundary distance, internal heterogeneity, uncovered content, uncertainty, cost, or why a propagated label should be trusted.

## Interpretation

AI Album achieved useful file-level compression but insufficient semantic evidence compression. The core migration target is not its fixed date/location/content DAG or specific model stack. It is the ability to convert full-scale media into reusable local evidence before an Agent spends visual tokens, while exposing enough structure for the Agent and user to detect and repair uncertain high-impact decisions.
