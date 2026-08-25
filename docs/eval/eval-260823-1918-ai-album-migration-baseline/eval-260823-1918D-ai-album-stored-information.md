---
id: "eval-260823-1918D-ai-album-stored-information"
title: "AI Album Stored Information Inventory"
type: eval
status: active
created: 2026-08-25
updated: 2026-08-25
timezone: "Asia/Shanghai"
parent: "eval-260823-1918-ai-album-migration-baseline"
depends-on:
  - "eval-260823-1918A-legacy-system"
  - "eval-260823-1918C-fixture-coverage"
superseded-by: ""
tags: ["ai-album", "migration", "persistence", "inventory"]
---

# AI Album Stored Information Inventory

## Purpose and boundary

This module answers one stage-neutral question:

> What information did AI Album actually persist, in what form, from which inputs, for which consumers, with what lifecycle and limitations?

It inventories native AI Album artifacts, information recoverable only from the final output tree, and evidence added later by the Hong Kong representative package. It does not assign anything to `mediasense.precheck`, `mediasense.plan`, or `mediasense.apply`; select a MediaSense storage technology; define a schema or directory layout; adopt an AI Album algorithm; or propose compatibility with an AI Album cache.

MediaSense is not in production, so the applicable compatibility policy is Zero Backward Compatibility. AI Album names, cache flags, filename patterns, and the `AA-STORED-*` identifiers below are evaluation vocabulary only. They are prohibited from becoming MediaSense product identifiers merely because they appear here. No adapter, dual-write path, deprecated field, or legacy-cache reader is proposed.

## Evidence sources and verification

### Evidence layers

| Layer | Material used | What it can establish | Label used below |
| --- | --- | --- | --- |
| Historical source | AI Album commit `c90aa8f04fd0d3348284e0ad19e18462987b1af2`, inspected with `git show` and a read-only archive | Producer and consumer code, filenames, dependencies, cache behavior, and in-memory state | `source-confirmed` |
| Package contents | `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` | Files, byte-level shapes, counts, empty values, directory topology, and manifest fields on this machine | `directly observed` |
| Package handoff and existing baseline | Package README/handoff plus modules A and C | Historical run reconstruction and facts whose original 1.09 TB source is not mounted | `reconstructed` unless independently observed |
| Current AI Album HEAD | `6eccb3711f4817242b0700dc370a070680edbaaf` | Supplementary comparison only | explicitly marked `current HEAD` |

`inferred` means that multiple observations support a conclusion but neither source nor an artifact states it directly. `unknown` means the available evidence cannot distinguish the alternatives.

The repository-local fixture descriptor points to `/Users/chengyanru/Datasets/mediasense/fixtures/ai-album-hk-representative-v1`; the package inspected here is under `Downloads`. This is a portability difference, not a descriptor update.

### Verification on 2026-08-25

`./scripts/verify.zsh` completed with exit code 0. It verified every listed SHA-256, manifest counts, cache inventory, expected date roots, all manifest media paths, and normalized equality between the replay and production output trees: 168 files and 73 terminal groups. `--deep`, cached replay, fresh replay, remote APIs, and billable models were not run.

The local directory has three unlisted 6,148-byte `.DS_Store` files at the package root, `dataset/`, and `baseline/`. They account exactly for the difference between the descriptor's 10,608 files and 1,759,421,497 logical bytes and the locally observed 10,611 files and 1,759,439,941 bytes. All 10,607 entries in `manifests/SHA256SUMS` match and none is missing; the verifier does not reject additional files. The versioned evidence is intact, but the three extras are outside its checksum claim.

## Completeness method

The inventory structure was generated from durable-write paths, not from the eight cache flags alone:

1. Enumerate every `CacheManager(...)` construction at the historical commit. This yielded 11 instances: nine top-level per-representative families and two wildcard video-frame families.
2. Trace each generator and every source-code consumer, including lazy consumers reached only during clustering.
3. Map all eight cache flags to deletion behavior and check cross-family dependencies that the flags do not encode.
4. Scan `src/` for other filesystem writes. Outside `CacheManager`, the relevant native paths are user-config template creation, optional LLM usage JSON, and output-tree materialization through move/copy/symlink operations.
5. Trace filename/stem union, temporal chaining, representative choice, hierarchical clustering, naming, bundle expansion, and output materialization, then distinguish their in-memory state from durable residue.
6. Enumerate both package cache trees by filename family, extension, array header, image dimensions, count, and size; compare their SHA-256 multisets.
7. Inspect both manifests, expected metrics, the SHA-256 inventory, replay evidence, and both clustered trees.
8. Compare the historical commit with current HEAD only for persistence-relevant changes.

This method closes over known write mechanisms in the historical `src/` tree and all declared package artifact classes. It does not claim closure over behavior hidden inside third-party libraries, provider-side records, shell history not shipped in the package, or the unavailable original-media filesystem.

## Stored-information overview

### Native similarity-cache inventory

All rows below occur under the sibling cache root `.similarity_cache/<input-folder-name>/`. The production cache and the derived-media re-keyed cache each contain the same 4,061 files and 277,333,383 bytes. Their per-family SHA-256 multisets are identical; only cache addressing was changed for the derived media.

| Historical ID | Family and historical filename pattern | Shape | Production count | Bytes | Native granularity |
| --- | --- | --- | ---: | ---: | --- |
| `AA-STORED-CACHE-001` | metadata, `{base}_meta_{file_hash}.yml` | structured record | 168 | 979,019 | per representative source path |
| `AA-STORED-CACHE-002` | ordinary thumbnail, `{base}_thumbnail_{file_hash}.jpg` | image | 168 | 12,215,486 | per representative source path |
| `AA-STORED-CACHE-003` | high-resolution thumbnail, `{base}_highres_thumbnail_{file_hash}.jpg` | image | 168 | 52,480,830 | per representative source path |
| `AA-STORED-CACHE-004` | asset embedding, `{base}_emb_{file_hash}.npy` | vector | 168 | 709,632 | per representative source path |
| `AA-STORED-CACHE-005` | privacy result, `{base}_privacy_{file_hash}.yml` | structured record | 168 | 40,354 | per representative source path |
| `AA-STORED-CACHE-006` | caption, `{base}_caption_{file_hash}.txt` | text | 159 | 284,933 | per demanded representative |
| `AA-STORED-CACHE-007` | title, `{base}_title_{file_hash}.yml` | structured record | 159 | 613,334 | per demanded representative |
| `AA-STORED-CACHE-008` | inferred location, `{base}_location_{file_hash}.yml` | structured record | 165 | 570,355 | per demanded representative |
| `AA-STORED-CACHE-009` | translation, `{base}_translation_{file_hash}.yml` | structured record | 0 | 0 | per demanded representative |
| `AA-STORED-CACHE-010` | video frames, `{base}_{file_hash}_video_frames/{base}_frame_*.jpg` | ordered image set by numeric filename | 1,369 in 97 directories | 203,656,784 | per video frame |
| `AA-STORED-CACHE-011` | video-frame embeddings, `{base}_{file_hash}_video_frames/{base}_emb_*.npy` | ordered vector set by numeric filename | 1,369 in 97 directories | 5,782,656 | per video frame |

The 1,323 top-level files are the sum of the first nine rows. The two wildcard families add 2,738 nested files. No translation artifact exists in either cache tree, but the historical source contains the manager and generator, so it remains part of the capability inventory.

### Other durable evidence

| Historical ID | Information | Native or package-added | Shape and granularity | Observed quantity |
| --- | --- | --- | --- | ---: |
| `AA-STORED-OUTPUT-001` | Final clustered hierarchy and representative thumbnails | native output, copied into the package | directory tree plus image files, per run | 168 files, 84 directories, 73 terminal groups |
| `AA-STORED-AUDIT-001` | Optional LLM usage records | native when explicitly enabled | JSON document containing a per-call record list | absent from production and cached replay |
| `AA-STORED-CONFIG-001` | Effective user configuration templates | native installation/runtime state | YAML files under `~/.config/ai-album/` | not included in the package |
| `AA-STORED-FIXTURE-001` | Media manifest | package-added evidence | JSONL, per included media path | 2,134 records |
| `AA-STORED-FIXTURE-002` | Bundle manifest | package-added reconstruction | JSON relation set, per legacy bundle | 168 records |
| `AA-STORED-FIXTURE-003` | Summary, expected metrics, checksums, and replay record | package-added evidence | JSON plus checksum list, per package/replay | one set |

## Detailed inventory

### Asset identity and cache addressing

#### `AA-STORED-IDENT-001` — cache namespace and source-derived key

- **Meaning, shape, and location:** a path convention rather than a standalone record. `CacheManager` places artifacts in the absolute sibling directory `.similarity_cache/<input-folder-name>/`; all 11 historical instances use `cache_key_type='path'`.
- **Granularity and cardinality:** one address per source path and family, except wildcard video families, which place multiple indexed files under one source-derived directory.
- **Producer and consumers:** `src/cache_manager.py:CacheManager._get_cache_file_path_from_path()` combines the source basename and `jinnang.MyPath(path).hash`; every cache producer and accessor consumes it. In the fixture, all 168 `source_cache_metadata_file` hash suffixes equal the representative's recorded source hash.
- **Dependencies:** source basename, sampled content hash, input parent and folder name, and family format string. The package identifies the source hash algorithm as partial MD5 over the first, middle, and last 4,096 bytes. The source path itself is not part of the filename beyond its basename.
- **Reuse and invalidation:** a content change detected by that partial hash creates a new key; a basename change also misses; an input-root relocation changes the surrounding cache directory unless it is copied. Old keys are not garbage-collected. Model, prompt, config, language, timezone, GPX, resolution, threshold, and software version do not participate in the key.
- **Errors, provenance, and cost:** parse/decode errors in a single cache file generally cause regeneration. The key gives neither a collision-proof content identity nor derivation provenance. Regeneration cost is the cost of the family it addresses.
- **Evidence and limit:** source-confirmed and directly observed. It cannot establish full-file identity, and two different paths with the same basename and sampled hash can collide.

### Metadata and temporal/geographic observations

#### `AA-STORED-CACHE-001` — metadata record

- **Meaning and shape:** a YAML dictionary containing `file_path`, `time`, `camera`, `photo`, and, when available, `lens`, `gps`, and `gps_resolved`. The `gps_resolved` subtree may retain coordinate-conversion metadata, provider/language/original-provider information, address components, and nearby POIs.
- **Granularity and quantity:** per representative source path. All 168 production representatives have a record; all have `file_path`, `time`, `camera`, and `photo`; 74 have `lens`; 148 have both `gps` and `gps_resolved`.
- **Producer:** `MetadataProcessor._generate_metadata()` delegates to `PhotoMetadataManager.get_metadata_raw()` and `MetaDataLoader`; ExifTool reads the media and related XMP/EXIF/JSON/XML sidecars, GPX may fill missing coordinates, and `GeoProcessor` may reverse-geocode coordinates.
- **Consumers:** timestamp/date extraction and sorting, temporal bundling, GPS clustering, orientation correction, privacy/caption/location/title prompts, and human-readable photography/geography context.
- **Dependencies and reuse:** source bytes and sidecars; configured EXIF tag priority and batch behavior; timezone; GPX tracks and match window; datum; reverse-geocoder provider/language/network response. Only source basename/hash and an explicit metadata flag clear participate in cache selection, so all other dependency changes can silently reuse stale metadata.
- **Regeneration cost:** mostly local metadata I/O, but GPX matching and especially reverse geocoding can add network/provider cost.
- **Failure and partial semantics:** ExifTool batch failure can yield empty dictionaries; missing/unparseable time can abort timestamp consumers; a reverse-geocode failure is logged and leaves `gps_resolved` absent. A valid dictionary, including a sparse one, is a cache hit. The record does not say whether coordinates came from EXIF or GPX and does not retain per-field tag provenance or confidence.
- **Evidence:** source-confirmed; counts and shapes directly observed. Cached values are observations, not corrected geographic or temporal ground truth.

### Visual renditions

#### `AA-STORED-CACHE-002` — ordinary thumbnail

- **Meaning and shape:** a JPEG rendering of the representative, rotated using cached orientation and normally bounded by the requested processing profile. It is per representative.
- **Producer and consumers:** `ImageProcessor._generate_thumbnail()` decodes an image or asks `VideoProcessor.extract_key_frame()` for a video. Remote caption and image-location calls consume its path.
- **Dependencies and reuse:** source decodability, orientation metadata, requested resolution, image library behavior, and for videos the frame/embedding/key-frame path. Resolution and orientation provenance are not in the cache key; changing either does not invalidate an existing file unless the thumbnail flag is cleared.
- **Regeneration and failures:** local image work for stills; video decode plus embeddings for videos. Invalid media returns `None`, after which the generic serializer/path expectations do not provide a durable typed failure record. A corrupt JPEG is normally regenerated on read.
- **Fixture evidence:** 168 files and 12,215,486 bytes. In width-by-height order, observed dimensions are 1,080x720 (55), 1,280x720 (102), 720x1,080 (9), and 1,273x720 (2). Evidence is directly observed plus source-confirmed.

#### `AA-STORED-CACHE-003` — high-resolution thumbnail

- **Meaning and shape:** a JPEG rendition under the separate high-resolution profile, per representative.
- **Producer and consumers:** `ImageProcessor._generate_highres_thumbnail()`; asset embedding, privacy detection, and thumbnail-mode output consume it. Video generation uses the selected cached frame.
- **Dependencies and reuse:** the source, orientation metadata, high-resolution profile, decoder, and video frame selection. None except source basename/hash is encoded in its key.
- **Regeneration and failures:** local decode/resize; potentially expensive for large stills and videos. Error and partial semantics match the ordinary thumbnail.
- **Fixture evidence:** 168 files and 52,480,830 bytes. All 97 video representatives are observed at 1,920x1,080; the 71 still-image representatives remain at 3,504x2,336 or portrait equivalent (64), 3,840x2,160 (5), or 7,808x4,416 (2). Therefore the label/default `1080p` does not prove a uniform 1080p stored raster. Evidence is directly observed plus source-confirmed.

The historical CLI help said the ordinary thumbnail served embedding and remote processing and the high-resolution thumbnail served privacy. The historical implementation instead calls `get_highres_thumbnail()` for asset embeddings, while caption and image-location use the ordinary thumbnail. Current HEAD corrects this help text. The package handoff's compressed wording about a 720p “embedding/remote-processing thumbnail” is therefore not reliable for the embedding input; source behavior is stronger evidence.

### Video frames and frame analysis

#### `AA-STORED-CACHE-010` — sampled video frames

- **Meaning and shape:** JPEG frames in one source-keyed directory, numbered by a wildcard expansion. Granularity is per sampled frame and per video representative.
- **Producer and consumers:** `VideoProcessor.extract_frames_async()` uses OpenCV, targets roughly 10-second intervals, caps a video at 20 frames, includes the last frame in some cases, and resizes using `frame_resolution`. Frame embeddings and key-frame selection consume the images.
- **Dependencies and reuse:** video bytes/decodability, FPS/frame-count reports, interval/cap algorithm, frame resolution, OpenCV behavior, and source key. Sampling/profile/software values are absent from the key.
- **Regeneration and failures:** local video decode and image work; potentially high I/O/CPU. A read failure stops extraction and returns the frames collected so far. An empty result creates no files and is recomputed on the next access.
- **Partial-completion hazard:** any nonempty wildcard match is treated as a complete cache; there is no expected-count manifest or completion marker. An interrupted write can therefore be accepted as a shorter valid-looking frame set.
- **Fixture evidence:** 1,369 JPEGs in 97 directories, 2–20 per video, 203,656,784 bytes; all observed frames are 1,920x1,080. Evidence is directly observed plus source-confirmed.

#### `AA-STORED-CACHE-011` — video-frame embeddings

- **Meaning and shape:** one NumPy float32 vector of shape `(1024,)` per cached video frame, stored beside the frames with corresponding numeric filenames.
- **Producer and consumers:** `VideoProcessor._generate_embeddings()` applies the same lazy ChineseCLIP embedder to cached frames. `extract_key_frame()` compares every frame against the others and selects the frame with greatest average similarity among its top half.
- **Dependencies and reuse:** the frame set and ordering, `OFA-Sys/chinese-clip-vit-huge-patch14`, processor/library weights, and key-frame algorithm. None is versioned in the filenames or payloads.
- **Regeneration and failures:** local model inference, usually expensive relative to metadata. Empty frames produce no embedding files. Partial wildcard sets can be mistaken for completion, and `CacheManager.clear()` tests the literal wildcard path, so source inspection indicates that video frame/embedding clearing through the thumbnail flag is ineffective.
- **Fixture evidence:** 1,369 vectors in the same 97 directories, 5,782,656 bytes; every inspected header is float32 `(1024,)`. Evidence is directly observed plus source-confirmed.

### Embeddings and similarity evidence

#### `AA-STORED-CACHE-004` — asset embedding

- **Meaning and shape:** a NumPy float32 vector of shape `(1024,)`, one per representative.
- **Producer and consumers:** `LLMProcessor._generate_embedding()` embeds the high-resolution thumbnail with `ChineseCLIPEmbedder`; image clustering consumes pairwise cosine similarity and converts it to distance `1 - similarity`.
- **Dependencies and reuse:** source-derived key, high-resolution rendition and orientation, model weights/processor/library versions, and numeric implementation. The cache stores no model ID, version, input profile, normalization declaration, or generation time, so those changes do not invalidate it automatically.
- **Regeneration and failures:** local model inference; computationally heavy but no remote call. Load failure regenerates; semantically incompatible but readable arrays remain hits.
- **Fixture evidence:** 168 vectors, all float32 `(1024,)`, totaling 709,632 bytes. Evidence is directly observed plus source-confirmed. The vectors do not establish semantic correctness of the resulting clusters.

### Privacy, caption, location, title, and translation

#### `AA-STORED-CACHE-005` — privacy result

- **Meaning and shape:** YAML keyed by detected NSFW/NudeNet label. Each value can contain score, message, `sensitive`, and `mild_sensitive` decisions.
- **Producer and consumers:** `LLMProcessor._generate_privacy_tag()` runs local `Falconsai/nsfw_image_detection` and NudeNet taggers on the high-resolution rendition. The two boolean levels determine whether captions and location inference remain local/text-only or send an image remotely.
- **Dependencies and reuse:** source/rendition, both model weights and thresholds, libraries, and run mode. None is recorded as a versioned dependency in the key or value.
- **Regeneration and failures:** local model inference. In privacy mode a detector failure raises; in default mode each detector failure is logged and the remaining partial dictionary, possibly empty, is cached. Absence of a label cannot distinguish “not detected” from a failed tagger, so provenance is insufficient despite per-label scores.
- **Fixture evidence:** 168 nonempty files and 40,354 bytes; 16 representatives have at least one `mild_sensitive` result and 7 at least one `sensitive` result. Evidence is directly observed plus source-confirmed; these are historical classifier outputs, not truth labels.

#### `AA-STORED-CACHE-006` — caption

- **Meaning and shape:** unstructured UTF-8 text, per representative only when demanded.
- **Producer and consumers:** `LLMProcessor._generate_caption()` sends the ordinary thumbnail and metadata to a remote captioner unless privacy marks it mildly sensitive; that path uses local `Salesforce/blip-image-captioning-large`. Title generation and privacy-preserving location inference consume the caption.
- **Dependencies and reuse:** privacy result, metadata, ordinary rendition, model/provider, prompt, target language, and retry behavior. None is represented in the key; the text does not carry model, prompt, route, confidence, or timestamps.
- **Regeneration and failures:** remote and potentially billable for ordinary content; local model inference for mildly sensitive content. Exhausted or unexpected failures return `''`, which the generic text cache can persist as a valid hit. File absence cannot distinguish not-requested, interrupted, or failed-before-save.
- **Fixture evidence:** 159 nonempty files and 284,933 bytes; 16 single-line results are consistent with the local route and about 143 with the remote route, as reconstructed in module A. Evidence for file count/content shape is direct; route totals are reconstructed.

#### `AA-STORED-CACHE-008` — inferred location

- **Meaning and shape:** YAML. Successful remote-image records have `location`, `reasoning`, `vlm`, and `prompt`; successful caption-based records have `location`, `reasoning`, `caption_locator`, and `prompt`; an empty result is `{}`.
- **Producer and consumers:** `LLMProcessor._generate_location_info()` first requires usable geographic metadata. Non-sensitive representatives use the ordinary thumbnail plus metadata with `RemoteImageLocator`; mildly sensitive representatives use caption plus metadata with `CaptionLocator`. Coarse/fine geographic cluster naming, title generation, and the otherwise-unused translation accessor consume it.
- **Dependencies and reuse:** metadata and reverse-geocoded candidates, privacy route, caption or ordinary thumbnail, prompt, target language, model/provider, and retry behavior. Only source identity and the location flag invalidate it.
- **Regeneration and failures:** remote visual or text model work. Missing/unusable GPS and caught generation/request errors return `{}`, which is deliberately persisted as a hit and is indistinguishable from a completed negative result without reading surrounding evidence.
- **Fixture evidence:** 165 files and 570,355 bytes: 133 remote-image records, 15 caption-locator records, and 17 empty mappings. The 148 nonempty records exactly match the 148 representatives with GPS; the 20 without GPS divide into 17 empty files and 3 absent files. Recorded model fields name `volcengineark-aids/doubao-2-0-pro`, but no model revision or confidence is stored. Evidence is directly observed plus source-confirmed.

#### `AA-STORED-CACHE-007` — generated title

- **Meaning and shape:** YAML with `title`, `reasoning`, `model`, and full `prompt`, per demanded representative.
- **Producer and consumers:** `LLMProcessor._generate_title_info()` combines caption, metadata, and inferred-location text through `CaptionTitler`. `ClusteringEngine._generate_folder_name()` cleans the resulting title for image-cluster directory names.
- **Dependencies and reuse:** every caption/location/metadata dependency plus title prompt, target language, model/provider, response contract, and retries. The source-derived key encodes none of them.
- **Regeneration and failures:** remote, potentially billable text-model work. Caught failures or `None` become `{}` and would persist; the accessor maps a missing `title` to `Unknown`.
- **Fixture evidence:** 159 nonempty files and 613,334 bytes, all naming `volcengineark-aids/doubao-2-0-pro`; none has blank or `Unknown` title. Caption and title identity sets overlap on 158 representatives, with one file unique to each and eight having neither, showing that absence is demand-shaped rather than a trustworthy failure signal. Evidence is directly observed plus source-confirmed. Reasoning and prompt improve traceability, but there is no confidence or model revision.

#### `AA-STORED-CACHE-009` — translation result

- **Meaning and shape:** the source defines YAML containing `location_zh`, `translation_note`, `translator`, and `prompt` when successful.
- **Producer and consumers:** `LLMProcessor._generate_translation_info()` translates the cached location using `RemoteLocationTranslator`. No production call site outside its accessor was found at the historical commit.
- **Dependencies and reuse:** location record, prompt, target language, model/provider, and retries; only source identity and the translation flag affect reuse.
- **Regeneration and failures:** remote and potentially billable. Missing location or caught generation/request failure becomes `{}`.
- **Fixture evidence:** zero files in both production and re-keyed caches. The persistence capability is source-confirmed; use in the Hong Kong run is directly disproved. No production behavior should be inferred beyond that absence.

### Bundles and representatives

#### `AA-STORED-FIXTURE-002` — reconstructed bundle relationship set

- **Meaning and shape:** `manifests/bundle-manifest.json` is a package-added relation set with `bundle_index`, `representative_path`, `source_members`, `source_member_count`, `included_valid_media`, and `source_valid_media_count`.
- **Granularity and quantity:** 168 bundles; 4,362 recorded source members and 2,133 included valid media. Per-bundle source membership ranges from 1 to 402 with median 4.5; included valid media ranges from 1 to 201 with median 2. The package excludes three AppleDouble entries that were present in the 4,365-member production grouping scope.
- **Producer and consumers:** the fixture-construction research reconstructed it from the historical run; the package verifier and future migration evaluations consume it. It was not emitted by the AI Album runtime.
- **Dependencies and reuse:** same-directory/stem normalization, AppleDouble and `M01`/`M02` rules, media validation, selected timestamps, the 60-second adjacent-chain setting, and extension-priority representative selection. Fixture immutability and SHA-256, not cache flags, govern reuse.
- **Regeneration and cost:** regeneration requires the historical source topology and grouping logic; reconstructing it from the original collection would require access to the unavailable large source. It requires local traversal and metadata work, not semantic model calls by itself.
- **Errors and provenance:** representative identity and membership are explicit, but the union reason for each edge is not. Bundle span is not stored as a field; it is reconstructed from member timestamps. Module A records median 3 s, P90 119 s, P95 182 s, and maximum 322 s. These are historical observations, not correctness labels.
- **Evidence:** package contents are directly observed; their relation to the original production run is reconstructed and checksum-protected.

The native runtime holds the same working concepts only in `MediaOrganizer.parent`, `files`, and `bundles`. Filename unions, timestamp ordering, transitive adjacent unions, representative identity, weights, and spans have no native run artifact. A process exit loses them; a rerun rebuilds them from current inputs and configuration.

### Clusters and output trees

#### `AA-STORED-OUTPUT-001` — materialized cluster hierarchy

- **Meaning and shape:** a directory tree whose keys encode the surviving date, location, and title names, with leaf files representing the chosen output mode. For the production thumbnail run, leaves are copies of high-resolution representative thumbnails rather than original media or full bundle membership.
- **Granularity and quantity:** per run and per terminal group. Both package trees contain 168 JPEGs, 84 directories, and 73 terminal directories. Directory depths are 8 at level one, 26 at level two, and 50 at level three; terminal groups occur at depths one (2), two (21), and three (50). The eight date roots are `000114`, `260428`, and `260501` through `260506`.
- **Producer and consumers:** `ClusteringEngine` groups by exact date, a fixed 3,000 m coarse pass, configured 500 m fine pass, then configured image distance `0.311`; `LinearHierarchicalCluster` names a partition by the most common per-item name and may prefix indexes or uniquify collisions. `cluster/file_operations.py` turns the in-memory tree into paths; the user and later evaluation consume the directory tree.
- **Dependencies and reuse:** representative order/timestamps/GPS/embeddings, bundle valid-media weights, thresholds and minimum weights, cached locations/titles, output mode, filename-collision resolution, and current filesystem state. The output tree embeds no explicit dependency snapshot and is not a reusable cache with validity checks.
- **Regeneration and failures:** clustering itself is local once caches exist; uncached semantic naming can be remote and billable. Materialization launches file operations concurrently after creating directories. There is no journal, completion marker, rollback, or post-verification receipt, so interruption can leave a plausible partial tree.
- **Provenance and limits:** dates and names are visible, but distance values, partition boundaries, merge reasons, votes behind a modal name, thresholds, skipped items, and source-to-output decisions are not serialized. Collision handling can insert source-parent components that are not semantic cluster levels. The tree therefore cannot reconstruct the full cluster decision process.
- **Evidence:** both trees and their normalized equality are directly observed; interpretation of the historical semantics is source-confirmed. The 168 representatives, 73 groups, and names are not semantic ground truth.

The date, coarse/fine geographic, and image-similarity cluster objects exist only as nested dictionaries/lists in memory. Expanded full-bundle membership is also materialized only for `original` or `link` output modes; the historical `thumbnail` run persisted representative thumbnails only.

### Execution, cost, and audit evidence

#### `AA-STORED-AUDIT-001` — optional LLM usage JSON

- **Meaning and shape:** when `--llm-usage-log-file` is supplied, `LLMUsageTracker` maintains one JSON object with a `usage_records` array. Each record contains timestamp, model, prompt/completion/total tokens, a cost estimate, duration, success, optional error message, and the first 200 characters of prompt and response.
- **Granularity and producer:** per callback-observed LLM request, accumulated in memory and rewritten to the specified file after every record by `src/llm/monitor.py`. `src/app.py` prints an in-memory aggregate at normal exit.
- **Consumers:** human debugging/cost review only; no clustering or output behavior reads this log.
- **Dependencies and reuse:** explicit CLI opt-in, callback support and provider response metadata, local static 2024 price constants, filesystem availability, and process concurrency. Existing JSON is appended; malformed JSON is replaced with an empty record list on the next successful write.
- **Failure and provenance:** failed callbacks store zero tokens and zero cost. Records have no asset/cache key, operation purpose, retry lineage, request ID, provider invoice identity, image-token accounting method, prompt/model version, or linkage to structured-output metrics. Shared callback state may also weaken attribution under concurrency. Structured-output metrics such as repair attempts are emitted to the ordinary logger, not added to this JSON.
- **Fixture evidence:** no usage/log file exists. The production command did not enable one; cached replay made zero LLM requests and likewise produced none. Exact production token use, cost, retry count, and latency are therefore unknown and cannot be reconstructed from cache counts. Source behavior is source-confirmed; absence is directly observed.

#### `AA-STORED-CONFIG-001` — user configuration templates and mutable inputs

- **Meaning and shape:** YAML at `~/.config/ai-album/conf.yml`, `llm.yml`, and `geo_config.yml`. `config_loader.py` gives user files precedence and atomically copies a system template when a user file is absent.
- **Granularity and consumers:** per user installation, consumed by metadata extraction, timezone handling, ignore behavior, geocoding, target language, model/provider selection, and prompts indirectly. API credentials remain environment inputs and are not copied into the fixture.
- **Lifecycle:** these files persist across runs, but AI Album does not snapshot the effective values or their digests into cache artifacts or output. CLI flags and the effective run command are printed, not natively saved.
- **Evidence and limit:** source-confirmed; the production files are not included, so exact effective values beyond reconstructed command semantics, timezone, observed model names, and package validation metadata are unknown.

#### `AA-STORED-FIXTURE-001` — media manifest

- **Meaning and shape:** package-added JSONL with one record per included media path. Every record has path, bundle index, representative flag, media type, transform, source/derived byte counts, source mtime, partial source hash and algorithm, derived SHA-256, notes, and a metadata snapshot; duration fields apply to 282 readable videos. The 168 representatives also name their source metadata-cache file.
- **Granularity and quantity:** 2,134 records: 1,851 images and 283 videos, of which 2,133 are readable and one is intentionally truncated. There are 168 representatives: 71 images and 97 videos.
- **Producer and consumers:** fixture construction produced it; verifier/evaluation tooling consumes it. It is not an AI Album runtime artifact.
- **Dependencies and lifecycle:** original source, proxy transformation policy, historical metadata/cache, and package version. Reuse is valid only while its SHA-protected package remains unchanged; modification requires a new fixture version.
- **Cost, provenance, and limits:** it makes the reduced fixture auditable without routine source access, but most images are resized derivatives and most videos are sparse proxies. It cannot establish original video/audio/HDR/bitrate/telemetry fidelity or multi-terabyte behavior. Evidence is directly observed for the package and reconstructed for original-source facts.

#### `AA-STORED-FIXTURE-003` — package-level audit set

- **Meaning and shape:** `package-summary.json` records scope and transform policy; `validation/expected.json` records count-based gates; `SHA256SUMS` records 10,607 file digests; `docker-replay-2026-08-23.json` records image/commit/mode and the successful cached replay. The copied production cache and production output preserve historical bytes for comparison.
- **Producer and consumers:** fixture construction and validation produced them; `verify.zsh`, replay scripts, and evaluators consume them.
- **Dependencies and lifecycle:** package version, Docker image, historical commit, checked file set, normalization rule, and replay configuration. Any mutation invalidates the claim and requires a new fixture version.
- **Evidence and limits:** the replay record confirms 168 bundles, 168 output files, 73 terminal groups, eight date roots, normalized equality, and zero LLM requests. It does not prove fresh-model behavior, exact production cost/retries, semantic correctness, source-scale throughput, or failure resilience. Evidence is directly observed for packaged files and reconstructed for the historical run.

## Persisted relationships

| Relationship | Native durable representation | Package durable representation | What remains unavailable |
| --- | --- | --- | --- |
| Source path to cache artifact | basename plus sampled content hash in filename; metadata also stores the caller's path string | source cache filename and hashes in media manifest; re-keyed cache filenames | collision-free identity and dependency/version provenance |
| Filename/stem, RAW/JPG/sidecar, AppleDouble, `M01`/`M02` | none; union-find state is in memory | `source_members`, counts, and included valid media per bundle; AppleDouble exclusions documented | per-edge grouping reason |
| Temporal adjacency | none; consecutive timestamped roots are unioned in memory | bundle membership plus member timestamps permit reconstruction | stored edge, threshold snapshot, and direct bundle span |
| Bundle membership and representative | none outside output effects | explicit bundle index, members, representative path, and media-level membership | native completion/version identity |
| Bundle weight | none; computed from current member lists | source and valid-media counts | historical per-stage weight after every merge |
| Date/geographic/image clusters | only directory topology after output | production/replay tree and checksummed paths | assignments, distances, candidate alternatives, and merge reasons |
| Generated group name | final directory component; per-item title/location caches may survive | both cache copies and output trees | vote set and exact item responsible for each final name |
| Expanded membership | original/link output can materialize members; thumbnail output does not | bundle manifest preserves source membership | a native source-to-output plan or receipt |

## Invalidations and reuse behavior

The eight positions are, in order: metadata, thumbnail, embedding, caption, privacy, title, location, and translation. `1` means keep/reuse; `0` requests deletion before recomputation. The default is `11111111`.

| Flag | Direct deletion | Coupled behavior | Missing dependency invalidation |
| --- | --- | --- | --- |
| metadata | metadata file | none | does not clear orientation-dependent thumbnails, caption/location/title, or date/geographic results |
| thumbnail | ordinary and high-resolution files | attempts to clear video frames and frame embeddings | wildcard clear checks a literal `*` path, so source inspection indicates nested video caches remain |
| embedding | asset embedding | none | does not include high-resolution profile or model version |
| caption | caption text | none | does not clear dependent title or caption-based location |
| privacy | privacy YAML | none | does not clear route-dependent caption/location |
| title | title YAML | none | does not track caption/location/prompt/model changes |
| location | location YAML | none | does not clear dependent title/translation |
| translation | translation YAML | none | does not track location/language/model changes |

These flags are imperative cleanup controls, not a dependency-aware validity model. Independently, an observed source hash change causes a new filename and cache miss, but leaves the old artifact behind. Readable stale artifacts survive all unencoded dependency changes.

## Errors, empty values, and partial completion

| Condition | Historical durable expression | Consequence |
| --- | --- | --- |
| Corrupt single cache file | loader logs selected parse/I/O failures and regenerates | no corruption record remains after replacement; not every deserialization exception is caught |
| Empty semantic result | `''` for caption or `{}` for privacy/title/location/translation can be serialized | later loads treat it as a hit; negative result and swallowed failure are not distinguished |
| Missing semantic file | no file | may mean not demanded, interrupted, failed before save, or explicitly cleared |
| Interrupted wildcard generation | whichever numbered frame/vector files were already written | any nonempty glob is accepted as complete on restart |
| Stage progress | terminal progress bars and logs only | no per-item completion ledger or run-level complete/partial state |
| Metadata/provider partial failure | sparse metadata or missing `gps_resolved`; log message | no typed per-field error/provenance record |
| Privacy partial failure | remaining tagger dictionary, possibly `{}` | absent detector output is ambiguous in default mode |
| LLM retries | callbacks may record calls if opt-in usage logging is active; repair metrics go to logger | no durable request lineage or exact retry total for the production run |
| Output interruption/collision handling | directories and successfully completed operations remain | no journal, atomic run boundary, rollback record, or verified receipt |

## Information not persisted

The following state materially existed or would be required to interpret the run, but AI Album did not natively persist it as a complete artifact:

- the complete scanned inventory, unsupported/skipped-file decisions, `.albumignore` traversal result, and validation outcome per path;
- same-stem/sidecar union edges, temporal-adjacency edges, bundle membership, representative rationale, weights, and spans;
- a source snapshot identity stronger than the sampled hash, plus a cache-wide manifest and garbage-collection state;
- dependency provenance for config, timezone, GPX, datum, model weights/version, prompt version, language, resolution/profile, libraries, and clustering thresholds;
- per-field metadata provenance and confidence, including whether GPS came from embedded metadata or GPX;
- complete/partial/not-requested/error status for every cache family and item;
- intermediate date/coarse-location/fine-location/image clusters, distances, merge reasons, naming votes, and alternatives;
- a frozen source-to-output mapping, collision decisions, operation journal, restart state, and post-verification receipt;
- durable progress/checkpoints, timing for local stages, resource use, or a run manifest binding command, commit, configuration, inputs, and outputs;
- exact production LLM calls, transport/repair retries, token accounting, monetary cost, and structured-output metrics;
- transient in-memory caches and state: metadata/timestamp dictionaries, union-find parents, bundles, nested cluster nodes, progress bars, function-timing statistics, retry counters, and provider-selection state.

The fixture adds several of these for evaluation, especially inventory and bundle relationships, but that does not make them native AI Album persistence or a MediaSense contract.

## Fixture-backed quantities

| Quantity | Observed value | Interpretation boundary |
| --- | ---: | --- |
| Original regular files recorded by the handoff | 4,896 | reconstructed; original source is not mounted |
| Production grouping members | 4,365 | includes three AppleDouble entries |
| Bundle-manifest source members | 4,362 | excludes those AppleDouble entries |
| Included media | 2,134 | 1,851 JPG and 283 MP4 |
| Readable / intentionally invalid media | 2,133 / 1 | proxy fixture coverage, not source-scale decode proof |
| Bundles / representatives | 168 / 168 | historical grouping observation, not ground truth |
| Representative image / video / GPS | 71 / 97 / 148 | directly represented in manifests/cache |
| Production and re-keyed caches | 4,061 files each | 1,323 top-level plus 2,738 nested; byte-identical family multisets |
| Output files / terminal groups | 168 / 73 | thumbnail-mode historical baseline only |
| Output directories | 84 | 8 first-level, 26 second-level, 50 third-level |
| Cached replay LLM calls | 0 | cache-hit replay, not fresh behavior |

## Evidence strength and contradictions

1. **Strongly triangulated:** all 11 cache formats, the eight flag positions, 4,061-file cache inventory, 168 representatives, 97 video-frame directories, 1,369 frame pairs, 73 terminal groups, and normalized output equality agree across source, manifest/expected files, package contents, and verifier where applicable.
2. **Documentation versus implementation:** historical CLI/help and package wording can be read as assigning embeddings to the 720p ordinary thumbnail. The historical implementation uses the high-resolution thumbnail for asset embeddings; current HEAD corrects the CLI wording. The implementation is authoritative for this data-flow claim.
3. **Descriptor versus local directory totals:** the exact 18,444-byte and three-file excess is fully explained by unlisted `.DS_Store` files. Checksummed contents match, but the verifier establishes listed-file integrity rather than absence of extras.
4. **Directly observed negative evidence:** there is no translation cache and no usage log in the package. Absence does not prove that the feature could never write such a file; source confirms both optional paths.
5. **Reconstructed, not exact:** approximately 143 remote and 16 local captions, 133 remote-image and 15 caption-based location records, and about 276 successful remote visual analyses are inferred from successful artifacts. They exclude unknown retries and failures.
6. **Unknown:** exact production retries, provider-side image token accounting, billed cost, runtime duration by stage, semantic correctness, original-data full decode behavior, and the cause of every missing lazy cache remain unresolved.
7. **Current HEAD supplement:** the same 11 cache managers and filename patterns remain. The relevant behavioral addition is explicit pruning of `.similarity_cache` directories during source traversal; help text now accurately associates high-resolution renditions with embeddings/privacy/output. Current HEAD does not replace the historical commit as production evidence.

## Coverage statement

This inventory covers:

- every `CacheManager` instance and format string in the historical source;
- every cache-flag bit and its implemented clearing behavior;
- independent video-frame and frame-embedding caches;
- metadata, both thumbnail classes, asset embeddings, privacy, caption, location, title, and translation;
- filename/stem relations, temporal bundling, representative selection, weights, cluster hierarchy, name generation, expansion, and output materialization;
- user configuration, optional LLM usage JSON, console-only progress/metrics, and missing run-level audit state;
- production-cache and re-keyed-cache file patterns and byte identity;
- media/bundle manifests, expected metrics, checksums, replay evidence, and both final trees.

The scope is sufficient to present a stage-neutral evidence base for human review before a MediaSense information-domain map is attempted. It is not sufficient to approve that map automatically: stage ownership, durable contract membership, schema, storage, algorithms, and lifecycle policy remain explicitly undecided.

## Continuation and reopening conditions

Stop here after review of this module. Do not project these entries into MediaSense stages or storage until a human accepts the inventory boundary.

Reopen the inventory if any of the following appears:

- another persistence constructor, write path, or external-library side effect in the historical commit;
- a production log, effective configuration snapshot, or original-source artifact that resolves current audit/provenance unknowns;
- a package checksum mismatch, missing listed file, unexplained extra beyond the three observed `.DS_Store` files, or changed fixture version;
- evidence that the copied production cache/tree does not originate from the stated run;
- a consumer of translation or another cache family missed by the source scan;
- a proposed downstream map containing information that cannot be traced to an entry or an explicit gap above.

Stronger models, alternative storage systems, and improved algorithms alone do not reopen this historical inventory. They belong to later product design, where the evaluation IDs and legacy formats must not become MediaSense schema.
