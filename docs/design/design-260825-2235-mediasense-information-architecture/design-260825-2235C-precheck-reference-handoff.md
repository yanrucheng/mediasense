---
id: "design-260825-2235C-precheck-reference-handoff"
title: "MediaSense PreCheck Reference Handoff"
type: design
status: review
created: 2026-08-26
updated: 2026-08-26
timezone: "Asia/Shanghai"
parent: "design-260825-2235-mediasense-information-architecture"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235A-information-domain-map"
  - "design-260825-2235B-stage-ownership"
  - "eval-260823-1918A-legacy-system"
  - "eval-260823-1918C-fixture-coverage"
  - "eval-260823-1918D-ai-album-stored-information"
superseded-by: ""
tags: ["mediasense", "precheck", "reference-handoff", "human-review"]
---

# MediaSense PreCheck Reference Handoff

## Purpose and review decision

This document is a manually constructed product prototype of what a person and `mediasense.plan` should receive after PreCheck. It applies the accepted [MediaSense Foundation](../design-260823-1918-mediasense-foundation.md) and [Stage Ownership](design-260825-2235B-stage-ownership.md) to the [Hong Kong representative fixture](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918C-fixture-coverage.md), but it is not an output produced by a MediaSense runtime.

The prototype tests one proposition:

> Can a sealed PreCheck Result make its source accounting, evidence compression, limitations, and expansion paths sufficiently inspectable that a user can trust it and Plan can normally reason from it without rescanning the source or depending on hidden working state?

Human review should accept, revise, or reject the product information and interactions shown here. Acceptance does not approve a schema, database, file layout, query language, hashing algorithm, evidence-selection algorithm, or implementation.

### Non-goals

This document does not:

- describe SQLite tables, columns, indexes, migrations, or SQL;
- freeze filenames, directory layout, serialization, hash algorithms, or cache keys;
- make the historical 168 bundles, captions, inferred locations, titles, or output tree MediaSense ground truth;
- claim that the Hong Kong fixture is a fresh PreCheck run or a complete copy of the original 1.09 TB source;
- define a Tool, Skill, Agent workflow, model, detector, embedding, clustering algorithm, or VLM request format;
- run a fresh replay, remote model, reverse-geocoder, online map, or billable API;
- define Storage Lifecycle or the minimal formal PreCheck contract.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumer depends on a MediaSense PreCheck format. Compatibility adapters, dual writes, deprecated fields, and preservation of AI Album cache or fixture formats are prohibited. This review prototype may change directly after human feedback.

## Evidence legend and authority boundary

Every material statement below uses one of five evidence classes:

- **Fixture fact:** directly observed in the checksum-protected package or its manifests.
- **Historical reconstruction:** recorded by the accepted package handoff or migration baseline about the unavailable original source or production run.
- **Product decision:** proposed MediaSense behavior or information responsibility.
- **Illustrative display:** an example of how a user or Plan might see the information; it is not a schema or a claim that a runtime already emitted it.
- **Review question:** a material choice still awaiting human confirmation.

The package verifier passed its declared SHA-256, manifest-count, path-existence, cache-inventory, and normalized-output checks during preparation of this document. The manifest scope contains 10,608 files including the checksum manifest and 1,759,421,497 logical bytes, matching the MediaSense fixture descriptor. Three local `.DS_Store` files exist outside the checksum manifest; they are transport-directory noise and are not fixture evidence.

The primary reference Source State is the actually observable package dataset rooted at `dataset/260501-HK美食之旅/`, not the unavailable original 1.09 TB collection. Direct enumeration finds 2,140 regular files and 1,095,090,414 logical bytes. Every one of those paths is present in the package SHA-256 manifest. The 2,134 media-manifest paths plus six explicitly listed non-manifest paths below provide path-level Accounting Closure for this bounded Source State.

The original source volume was not mounted during this design work. Its 4,896 regular files, 4,362 ordinary-traversal members, 534 ignored-directory files, and original RAW/DNG/LRF/AAC populations remain historical comparison and evidence limits. They do not belong to the sealed Source State demonstrated by the primary instance.

## Logical handoff and human review surface

**Product decision:** the PreCheck handoff retains the four responsibility groups accepted by Stage Ownership:

```text
PreCheck Result
├── Result Manifest
├── Source Account
├── Evidence Base
└── Coverage Map
```

These are logical responsibilities, not four required files or database tables.

The human-review surface is a regenerable projection over the sealed result. A person should not have to inspect raw SQLite rows, and a generated report must not become a second source of truth.

If a later Storage Lifecycle uses both a filesystem and SQLite, the authoritative homes should remain unambiguous:

- the Result Manifest binds the identity, seal, declared components, integrity, and status of the whole result;
- structured facts and relationships have one authoritative structured home;
- evidence files are authoritative for their own bytes;
- the review projection summarizes and links to those authorities and can be regenerated;
- a summary value that cannot be expanded to its contributing items is not reviewable;
- a database relation that cannot be reached through a product query or review view is hidden state and cannot support Plan.

### Result Manifest reference view

**Illustrative display:** the entry view binds the other responsibilities without exposing their storage implementation.

| Manifest responsibility | What the reviewer receives |
| --- | --- |
| Result identity | One immutable result identity and version, visibly distinct from its Working Run. |
| Collection and Source State binding | The exact subject, observed boundary, observation time, identity strength, and known limits to which all facts refer. |
| Effective profile | The material preparation choices and dependencies needed to interpret validity and reuse, without making one algorithm permanent. |
| Component binding | The declared Source Account, Evidence Base, and Coverage Map authorities plus their integrity and availability. |
| Status axes | Coverage, readiness, and integrity shown independently with reasons. |
| Resource facts | Local I/O, compute, time, and storage facts available within the observation boundary. |
| External-effect proof | Declared policy, enforced boundary, observed zero-egress facts, and unknown external scope kept distinct. |
| Seal | The point after which correction requires a new result instead of an in-place edit. |

The reviewer then sees four connected projections: the trust page, the exception queue, the default evidence frontier, and deterministic validation results. Every summary or exception can be expanded to its authoritative structured facts and evidence objects.

### Deterministic review support

Human review is not a manual row-by-row audit. The review surface must be accompanied by deterministic checks that establish properties for which sampling is insufficient:

- every discovered Source Item has a scope disposition;
- scope totals reconcile to the declared discovery population;
- attempted processing has an explicit availability outcome;
- every retained Observation and Derived Evidence item has a subject and provenance;
- every Coverage Relationship names its covered set and expansion path;
- no claimed covered item is unreachable from its coverage entry;
- every referenced evidence object exists and satisfies the result's declared integrity rule;
- no unresolved item is silently counted as complete;
- a sealed result has no mutable working dependency.

The person reviews the meaning of these claims, all material exceptions, the default evidence frontier, selected drill-downs, and the remaining uncertainty. Deterministic checks prove the exhaustive structural properties.

## Reference trust page: what the user sees first

The first view should establish trust before asking the user to understand internal processing.

### Collection and source state

**Illustrative display:**

| Item | Displayed value | Evidence status |
| --- | --- | --- |
| Collection | Hong Kong representative fixture | Human-recognizable subject for this bounded reference; not a replacement identity for the original collection. |
| Source State | `dataset/260501-HK美食之旅/` inside the verified package | Fixture fact and the authoritative source boundary for this reference instance. |
| Declared discovery boundary | All regular files recursively reachable under that root, including paths below both `.albumignore` markers | Product decision applied to a directly observed tree. Ignore markers inform Scope Decisions but do not suppress discovery. |
| Observed source size | 2,140 regular files; 1,095,090,414 bytes | Fixture fact; all paths are covered by the package SHA-256 manifest. |
| Source roles | 2,136 source-media items; 4 auxiliary scope/location items | Product decision over an exhaustively enumerated fixture population. |
| Historical comparison | 4,896-file original source and 168 legacy bundles | Historical reconstruction outside this Source State. |
| Source mutation | None permitted | Product decision. Fixture derivation was also source-read-only. |

### Three independent result axes

**Illustrative display:**

```text
Coverage:   complete | partial
Readiness:  plan-ready | blocked
Integrity:  valid | invalid
```

The axes answer different questions:

- `complete / partial` describes the result's declared coverage within its boundary;
- `plan-ready / blocked` describes whether the evidence is sufficient for the stated planning purpose;
- `valid / invalid` describes whether result identity, integrity, dependencies, and seal can be trusted.

The reference page must never collapse them into one “success” badge. A result may be `complete + blocked + valid`, for example when every item is accounted for but representative evidence is insufficient. A bounded `partial + plan-ready + valid` result is possible when its declared limits do not impair the stated planning purpose. An invalid result cannot enter Plan regardless of the other displayed claims.

**Reference judgment for this bounded instance:** Source Account closure is complete, result coverage is partial, readiness is blocked, and the inspected package evidence is valid. Coverage remains partial because the two RAW source-media items have no reviewed PreCheck evidence treatment, the invalid-media substitute relationship is still only a candidate, and this document demonstrates rather than exhaustively constructs the frontier for all 2,136 source-media items. Readiness is therefore decidable and currently `blocked`, not unknown. This is a reviewed product judgment over the fixture, not a claim that a MediaSense runtime already sealed a result.

### Trust summary

**Illustrative display for the bounded fixture Source State:**

| Trust question | Reference answer |
| --- | --- |
| All discovered items accounted for? | Yes: 2,140 of 2,140 regular-file paths have a scope disposition. |
| Default planning evidence prepared? | Partially: concrete frontier cards are reviewable, but this document does not establish coverage for every one of the 2,136 source-media items. |
| Material omissions or failed evidence? | Two RAW evidence acquisitions are `not-requested`; one MP4 is invalid; one separate readable MP4 has a missing time; the invalid item's substitute relationship is not yet accepted. |
| Known representative conflicts? | Yes: bundle 61 hides person and wider-context evidence behind a food-only representative; abnormal-time and repair-family conflicts are also surfaced below. |
| Local-only external-effect proof sufficient? | No actual PreCheck run audit exists. Package inspection was local, but that is not a sealed runtime proof. |
| Source stayed read-only? | Yes during this review and during documented fixture derivation, within the stated observation boundary. |
| Can Plan proceed? | `blocked` for an authoritative full-fixture plan until evidence coverage and source-read-only/external-effect proof are sufficient; read-only exploratory review may continue. |

The summary links to, rather than duplicates, the Source Account, Evidence Base, Coverage Map, exceptions, and proof facts.

## Source Account reference instance

### Path-level Accounting Closure for the observed dataset

**Fixture fact:** the declared Source State contains exactly 2,140 regular files. All are present in the package checksum manifest, and the 2,134 media-manifest paths exist under the source root.

```text
2,140 discovered regular-file paths
  = 2,134 media-manifest JPG/MP4 paths
  +     1 fixture-only ARW
  +     1 fixture-only DNG
  +     2 GPX tracks
  +     2 .albumignore markers
```

**Product decision and illustrative display:**

| Scope disposition | Count | Exact population |
| --- | ---: | --- |
| Included source media | 2,136 | 1,851 JPG, 283 MP4, `fixtures/raw-sidecar/DSC01519.ARW`, and `fixtures/raw-sidecar/DJI_20260501183924_0002_D.DNG`. |
| Auxiliary | 4 | Two GPX tracks and two `.albumignore` scope-control markers listed below. |
| Excluded | 0 | Nothing inside this bounded fixture Source State is silently excluded. |
| Unresolved | 0 | Every discovered regular-file path has a current scope disposition. |
| **Discovered total** | **2,140** | `included + auxiliary + excluded + unresolved` reconciles exactly. |

The two RAW files default to source media. Same-stem or capture-time similarity with a JPEG is a Candidate Relation, not authority to demote the RAW file. Only a later explicit, traceable Scope Decision supported by concrete evidence may classify a particular item as an auxiliary companion.

### Processing and availability closure

Scope closure does not imply that every observation succeeded:

| Population | Count | Availability or validity |
| --- | ---: | --- |
| Resized JPEG fixture media | 1,851 | Readable; every file is a derived JPEG proxy rather than an original full-resolution source. |
| Sparse representative video proxies | 94 | Readable; source timeline is approximated from production frames. |
| Three-frame non-representative video proxies | 185 | Readable; source duration, audio, bitrate, full frame stream, HDR fidelity, and DJI telemetry are not preserved. |
| Native-copy videos | 3 | Readable within the fixture checks. |
| Truncated invalid MP4 | 1 | Invalid media; no usable metadata, time, or visual evidence. |
| Fixture-only ARW/DNG | 2 | File presence and integrity are verified; PreCheck decoding and visual-evidence production are `not-requested` in this prototype. |
| GPX and `.albumignore` auxiliaries | 4 | Present and integrity-checked; they are not organization targets. |

The 2,133 readable JPG/MP4 paths and one invalid MP4 reconcile to the 2,134 media-manifest paths. The two RAW source-media items remain included even though their evidence-acquisition state is `not-requested`; this contributes to partial coverage and the current `blocked` readiness judgment.

### Proxy-source limitation

This Source State is the representative fixture itself. Its files are factual source bytes for this bounded reference, but they are not equivalent to the unavailable originals:

- all 1,851 JPEGs are resized derivatives with a maximum dimension of 2,560 px;
- 94 videos are sparse timeline proxies built from production frames;
- 185 videos contain approximately three selected frames and do not preserve original duration;
- only three MP4s are native copies;
- one MP4 is an intentionally truncated invalid fixture;
- the two RAW files are isolated format samples, not coverage of the original RAW population.

This result may support planning for the representative fixture. It cannot support a claim that the original 1.09 TB collection has equivalent visual coverage, full video fidelity, or the same source state.

### Package material outside the Source State

The rest of the representative package supports evaluation but is not source media in this Source State:

| Fixture-relative location | Role |
| --- | --- |
| `dataset/.similarity_cache/` | Re-keyed historical/replay cache; derived evidence available for inspection, not Source Items. |
| `dataset/representative-run-clustered/` | Cached replay output; historical derived view, not organization truth. |
| `baseline/production-cache/` | Historical production cache used for comparison and provenance limits. |
| `baseline/production-clustered/` | Historical production output tree; regression evidence, not a MediaSense plan. |
| `manifests/` | Fixture inventory and integrity support. It helps construct this reference but is not automatically a future MediaSense contract. |
| `validation/` | Fixture verification evidence. |
| `scripts/` and `docs/` | Fixture operation and handoff support; outside the media Collection. |

### Distinguishing disposition from processing outcome

**Product decision:** `included`, `auxiliary`, and `excluded` answer the scope question. `unsupported`, `invalid`, `error`, and `unresolved` answer different capability or outcome questions and must not be forced into a misleading single bucket.

| Term | Meaning in the product | Hong Kong illustration |
| --- | --- | --- |
| Included | The item is in the planning subject and requires a final Plan disposition. | All 2,134 JPG/MP4 paths plus both fixture RAW files are included source media. |
| Auxiliary | The item informs scope or source interpretation but is not itself an organization target. | The two GPX tracks and two `.albumignore` markers are auxiliary in this instance. |
| Excluded | The item is intentionally outside the current planning scope, with a reason and applicable rule or confirmation. | This bounded instance has zero excluded regular files. Historical ignored-directory aggregates do not become exclusions in this Source State. |
| Unsupported | The current profile cannot interpret the item's format or required capability. It may still be included or auxiliary and remains accounted for. | The RAW files remain source media even while their decoding/evidence work is `not-requested`; a future attempted but unsupported profile would report `unsupported` without changing their source role. |
| Invalid | Validation established that the item cannot satisfy the expected media contract. | The truncated MP4 has no readable media container. |
| Error | An attempted operation failed; the item itself is not thereby proven invalid. | A decoder crash, storage read error, or extractor failure must be local and retryable where possible. |
| Unresolved | No defensible disposition or required observation is available yet. | Unresolved source identity, ambiguous ignore effect, or missing required evidence blocks honest closure or makes the declared result partial. |

Accounting Closure therefore needs at least two reviewable reconciliations:

1. every discovered item has exactly one current scope disposition; and
2. every required attempt or observation has a distinct availability outcome.

The exact physical representation of these meanings remains deferred.

### `.albumignore`, GPX, and isolated RAW/DNG

The six non-manifest Source Items are directly inspectable at these fixture-relative paths:

- auxiliary scope control: `dataset/260501-HK美食之旅/a-files/.albumignore`;
- auxiliary GPX: `dataset/260501-HK美食之旅/a-files/GPX/2026-05-03T05-33-10+0800.gpx`;
- auxiliary GPX: `dataset/260501-HK美食之旅/a-files/GPX/2026-05-05T21-47-16+0800.gpx`;
- auxiliary scope control: `dataset/260501-HK美食之旅/fixtures/.albumignore`;
- included RAW source media: `dataset/260501-HK美食之旅/fixtures/raw-sidecar/DSC01519.ARW`;
- included RAW source media: `dataset/260501-HK美食之旅/fixtures/raw-sidecar/DJI_20260501183924_0002_D.DNG`.

An ignore marker informs a Scope Decision; it does not erase discovery. The reference deliberately includes all six paths in Accounting Closure. The two GPX files may support local coordinate candidates but imply neither online-map use nor reverse geocoding.

The ARW has a same-stem JPEG candidate at `dataset/260501-HK美食之旅/0505/100MSDCF-steak-house/DSC01519.JPG`. The DNG has a same-stem JPEG candidate at `dataset/260501-HK美食之旅/0502/DJI_001-action-sd/DJI_20260501183924_0002_D.JPG`. These are Candidate Relations and possible visual expansion paths. They do not prove byte equivalence, identical exposure, or authority to treat the RAW files as auxiliary.

### Localized corrupt-media outcome

**Fixture fact:** `dataset/260501-HK美食之旅/0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.MP4` is a 1 MiB truncated file with no usable `moov` atom. It is the sole invalid media fixture. The other 2,133 manifest media are readable.

**Illustrative display:**

```text
Source Item: 0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.MP4
Scope disposition: included
Validation: invalid media container
Time observation: unavailable because metadata extraction did not succeed
Visual evidence: unavailable
Affected coverage: this item and any relation that depended exclusively on it
Retry: not automatically useful without source replacement
Global effect: none on unrelated completed items
Planning consequence: visible residual uncertainty; readiness depends on its materiality
```

Accounting can still be complete when an item is honestly classified as invalid. An invalid item is compatible with `plan-ready` only when it is fully accounted, the failure and affected coverage are explicit, residual uncertainty is visible, and existing alternative evidence is sufficient to show that the missing content cannot materially change planning. This instance does not yet claim that sufficiency; the related repaired variants below remain a Candidate Relation rather than an accepted substitute.

### Missing-time and repaired-variant observations

Two readable fixture items share the damaged video's base name but are separate Source Items:

- `dataset/260501-HK美食之旅/0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.patched-full.MP4` is readable, has `create_date = 2026-05-04T20:27:29+08:00`, and is historical bundle 127;
- `dataset/260501-HK美食之旅/0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.remux-faststart.MP4` is readable, has an explicit `create_date = null`, and is historical bundle 128.

The truncated item and `patched-full` share the package's historical partial source hash; `remux-faststart` has a different recorded source hash. Both readable variants have visually similar local renditions, while their time and other metadata differ. This supports a repair-family Candidate Relation and a conflict card, not silent identity collapse.

Useful local renditions are:

- `dataset/.similarity_cache/260501-HK美食之旅/DJI_20260504202728_0029_D.patched-full_highres_thumbnail_cf043a2dea4afa06be60729cac9fcc9c.jpg`;
- `dataset/.similarity_cache/260501-HK美食之旅/DJI_20260504202728_0029_D.remux-faststart_highres_thumbnail_6992df3e26f8f2df1c7c27adb6d3a1ad.jpg`.

The missing-time observation is `complete` as an observation attempt with a null result, not an extractor error and not an invalid-media result. Plan can use visual and relation evidence while preserving the unresolved time.

### Time, GPS, and provenance

**Fixture facts:**

- 2,132 readable media rows have a non-empty `create_date`;
- the readable `remux-faststart` item above has `create_date = null`;
- the truncated MP4 is a separate invalid item with no usable metadata or time;
- two observed dates are abnormal relative to the main trip population:
  - `0503/DJI_001-pocket4/DJI_20000114013849_0001_D.MP4` → `2000-01-14T09:38:50+08:00`;
  - `0502/DJI_001-action-sd/DJI_20260428201430_0001_D.MP4` → `2026-04-28T20:14:31+08:00`;
- 148 media metadata snapshots retain GPS coordinates;
- historical metadata does not say whether a coordinate came from embedded metadata or GPX and does not retain field-level tag provenance or confidence;
- historical `gps_resolved` content used online reverse-geocoding and is legacy evidence, not acceptable PreCheck output.

**Product decision:** PreCheck presents abnormal and missing values as observations with candidates, provenance, quality, and availability. It does not correct an abnormal date into the trip range. A conflict view may compare the observed value with collection context, filename evidence, neighboring times, and GPX candidates while preserving their separate authority.

The default evidence frontier should surface both abnormal-date videos because their date could materially affect downstream organization. The dark, low-information local rendition for the 2000-dated video strengthens the need for explicit uncertainty; it does not establish the correct date. The 2026-04-28 rendition contains documentary visual content that may be relevant to Plan, but visible text is not silently promoted into a corrected timestamp. The exact rendition references appear below.

### Historical-source comparison, not the main Source State

The unavailable original source remains useful only as a bounded comparison:

```text
4,896 historical regular files
  = 4,362 ordinary-traversal paths
  +   534 files under two historically ignored directories
```

The package records the 4,362 non-AppleDouble historical members as 1,851 JPG, 283 MP4, 1,833 ARW, 4 DNG, 209 LRF, 110 AAC, and 72 XML. It does not retain the path-level list for all 534 ignored-directory files, and the original volume is unavailable.

A hypothetical handoff that bound itself to that original source using only current evidence would be blocked: the 1,837 original RAW/DNG items are source media under the adopted product decision but their full bytes and PreCheck evidence are unavailable here, and all 534 ignored-directory paths would require direct discovery and disposition. Aggregate counts can explain the limitation but cannot support a real sealed Accounting Closure.

## Evidence Base and Coverage Map reference instance

### Default evidence frontier

**Product decision:** PreCheck prepares a small, coverage-constrained starting frontier with four roles:

- **representative:** shows a useful center or common appearance of a covered set;
- **boundary:** exposes where a candidate relation or covered set begins, ends, or changes;
- **outlier:** exposes material variation that a center would hide;
- **conflict:** exposes evidence that supports materially different interpretations or challenges the coverage claim.

The roles describe Coverage Relationships. They do not require four artifact types, four algorithms, or four separate images for every set.

### Concrete Hong Kong frontier cards

The following cards are illustrative displays built from real fixture items and historical relations. Every path is relative to the root of `ai-album-hk-representative-v1`. The paths are review references, not proposed MediaSense filenames.

#### Card A — bundle 61 representative, boundary, and hidden variation

| Field | Displayed value |
| --- | --- |
| Candidate Relation | Historical bundle 61, located by `bundle_index = 61` in `manifests/bundle-manifest.json`. |
| Covered Source Items | The 201 fixture paths in that entry's `included_valid_media`. The historical `source_member_count = 402` describes unavailable original companions and is comparison context, not this Source State's covered set. |
| Representative | `dataset/260501-HK美食之旅/0503/100MSDCF/DSC00594.JPG` at `21:51:29`; a direct fixture JPEG showing a close dish view. |
| Early corroborating evidence | `dataset/260501-HK美食之旅/0503/CLIP-260503/C0558.MP4`, inspect around 1 second; a three-frame proxy showing the same dish context. |
| Outlier / conflict evidence | `dataset/260501-HK美食之旅/0503/CLIP-260503/C0561.MP4`, inspect around 1 second; a three-frame proxy showing a diner with the dish rather than the representative's food-only framing. |
| Late boundary evidence | `dataset/260501-HK美食之旅/0503/DJI_001-action/DJI_20260503215611_0014_D.MP4`, inspect around 1 second; a three-frame proxy showing a wider table/restaurant scene at `21:56:12`. |
| Selection basis | First/early contextual/visually divergent/last observed points across the candidate's `21:51:29`–`21:56:12` sampled time range, plus manual visual inspection of the local fixture media. |
| Known exclusions | The three video paths are reduced proxies. They do not expose audio, complete original streams, source bitrate, HDR fidelity, DJI telemetry, or all variation between the selected frames. |
| Next expansion | Bundle 61 record → all 201 `included_valid_media` paths → each `media-manifest.jsonl` record → the exact fixture Source Item path. The unavailable original-media bytes are outside this Source State. |

This is a verified example of a representative hiding material within-group variation: the dish-only representative does not expose the person or the wider dining context visible in two member videos. It challenges a one-image coverage claim. It does not by itself prove that the historical bundle should be split; Plan still decides semantic organization after inspecting the conflict evidence.

#### Card B — abnormal temporal boundary

| Field | Displayed value |
| --- | --- |
| Covered Source Items | `dataset/260501-HK美食之旅/0503/DJI_001-pocket4/DJI_20000114013849_0001_D.MP4` and `dataset/260501-HK美食之旅/0502/DJI_001-action-sd/DJI_20260428201430_0001_D.MP4`. |
| Role | boundary + outlier + conflict |
| Supporting observations | `create_date = 2000-01-14T09:38:50+08:00` and `2026-04-28T20:14:31+08:00`, filenames, neighboring collection dates, and local visual renditions. |
| Local renditions | `dataset/.similarity_cache/260501-HK美食之旅/DJI_20000114013849_0001_D_highres_thumbnail_634db49ea7b3cdf58d99e15a58e8b8c8.jpg`; `dataset/.similarity_cache/260501-HK美食之旅/DJI_20260428201430_0001_D_highres_thumbnail_e0017e304d7e465703527ed74aad6b39.jpg`. |
| Selection basis | Both dates lie outside the main May 1–6 population and can materially change time-based organization. The first rendition is dark and low-information; the second contains documentary content but cannot establish timestamp correctness. |
| Known exclusions | The package does not preserve field-level timestamp provenance sufficient to select a corrected value. Visible text, filenames, and neighboring times remain separate candidates. |
| Next expansion | Frontier card → per-item media-manifest record → time Observation and alternatives → exact Source Item video → neighboring items and any applicable GPX candidates. |

These items establish a real temporal conflict surface. They do not establish a corrected date.

#### Card C — invalid, repaired, and missing-time family

| Field | Displayed value |
| --- | --- |
| Candidate Relation | A three-item repair family suggested by shared base name, package construction history, partial hashes, metadata, and rendition similarity. It is not confirmed source identity. |
| Invalid Source Item | `dataset/260501-HK美食之旅/0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.MP4`; historical bundle 114; no usable media, metadata, time, or rendition. |
| Readable candidate | `dataset/260501-HK美食之旅/0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.patched-full.MP4`; historical bundle 127; `create_date = 2026-05-04T20:27:29+08:00`. |
| Missing-time candidate | `dataset/260501-HK美食之旅/0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.remux-faststart.MP4`; historical bundle 128; readable with explicit `create_date = null`. |
| Local renditions | `dataset/.similarity_cache/260501-HK美食之旅/DJI_20260504202728_0029_D.patched-full_highres_thumbnail_cf043a2dea4afa06be60729cac9fcc9c.jpg`; `dataset/.similarity_cache/260501-HK美食之旅/DJI_20260504202728_0029_D.remux-faststart_highres_thumbnail_6992df3e26f8f2df1c7c27adb6d3a1ad.jpg`. |
| Conflict | The two readable renditions are visually similar, but the variants have different time/GPS availability and occupy different historical bundles. The invalid and `patched-full` records share the historical partial source hash; `remux-faststart` does not. |
| Known exclusions | A partial hash and common stem do not prove identity. The invalid item has no direct visual evidence. Historical online-resolved location data is not PreCheck authority. |
| Next expansion | Three media-manifest records → historical bundles 114/127/128 → per-field Observations → both local renditions and source videos → package construction notes. |
| Readiness consequence | Keep the invalid item accounted and the missing time explicit. Treat alternate content as sufficient only after the Coverage Relationship and materiality judgment are reviewed; otherwise remain blocked or reopen. |

#### Card D — fixture RAW source media and same-stem candidates

| Field | Displayed value |
| --- | --- |
| Included Source Items | `dataset/260501-HK美食之旅/fixtures/raw-sidecar/DSC01519.ARW`; `dataset/260501-HK美食之旅/fixtures/raw-sidecar/DJI_20260501183924_0002_D.DNG`. |
| Candidate Relations | ARW ↔ `dataset/260501-HK美食之旅/0505/100MSDCF-steak-house/DSC01519.JPG`; DNG ↔ `dataset/260501-HK美食之旅/0502/DJI_001-action-sd/DJI_20260501183924_0002_D.JPG`. |
| Selection basis | Exact same stems plus the fixture's explicit RAW-sidecar purpose support association candidates. The JPEGs provide immediately inspectable but non-authoritative visual clues. |
| Known exclusions | The prototype did not decode the RAW files, establish exposure equivalence, or prove that either JPEG fully represents its RAW candidate. Two samples cannot establish original full-volume RAW behavior. |
| Next expansion | RAW Source Item bytes → same-stem Candidate Relation → JPEG Source Item and its media-manifest Observation → future RAW-derived evidence when requested. |
| Readiness consequence | RAW remains source media. Because reviewed RAW evidence is absent, this part of the current reference coverage is partial and contributes to `blocked`. |

### Coverage claims required on every card

A useful frontier card makes the following inspectable:

- what Source Items or Candidate Relations it claims to cover;
- the role of each visible evidence item;
- why the selected evidence can support that role;
- the amount or weight of the covered population;
- known exclusions, invalid items, and failed evidence;
- conflicts and rival interpretations;
- the next expansion links;
- the condition under which the coverage claim should be challenged or reopened.

A gallery without these relations is only a sample browser. It cannot establish Evidence Sufficiency.

## Plan-ready completion variant

This variant does not replace or weaken the blocked reference above. It answers a different review question:

> What additional local evidence, reviewed decisions, coverage relationships, and deterministic proof would be sufficient to turn the same fixture-bound Source State into a plan-ready result?

No MediaSense runtime has produced this variant. Its authority classes are explicit:

- **Fixture facts:** the 2,140-path Source Account, 2,136 source-media population, 168 historical candidate relations, 2,133 readable manifest media, exact special-item paths, and existing local fixture bytes and renditions.
- **Human review decisions:** whether proposed evidence is sufficient for the bounded planning purpose, whether the repair-family relation may represent the invalid item's content, and whether residual uncertainty is acceptable.
- **Illustrative completion assumptions:** new local RAW observations and renditions exist, every required Coverage Relationship is constructed and valid, deterministic checks pass, and an actual PreCheck run supplies adequate source-read-only and external-effect proof. This fixture variant remains deliberately local-only.

The bounded purpose is planning the representative fixture's 2,136 source-media paths. It does not claim coverage of the unavailable original 1.09 TB collection or properties discarded by the proxy transformations.

### Completion of the two RAW Source Items

The ARW and DNG remain independent source media. Closing their evidence gap requires local evidence derived from each RAW Source Item, not only its same-stem JPEG:

| Required local evidence | Completion meaning |
| --- | --- |
| Readability and decode outcome | A complete local attempt distinguishes readable, unsupported, invalid, and error without changing the source role. |
| Reviewable local rendition | A locally derived preview exposes enough visible content for the bounded organization purpose, with orientation, dimensions, color/profile limits, integrity, and regeneration conditions. |
| Source-derived observations | Available capture time, camera/lens, orientation, dimensions, and other planning-relevant facts retain field-level producer and provenance; unavailable values remain explicit. |
| Same-stem Candidate Relation | The ARW ↔ `0505/100MSDCF-steak-house/DSC01519.JPG` and DNG ↔ `0502/DJI_001-action-sd/DJI_20260501183924_0002_D.JPG` relations state their filename basis, alternatives, confidence/quality, and non-equivalence limits. |
| Coverage Relationship | The RAW rendition represents the RAW item directly. The JPEG may corroborate or conflict, but it does not silently substitute for the RAW bytes. |
| Expansion path | RAW frontier entry → RAW observations and rendition → association candidate → same-stem JPEG evidence → exact RAW Source Item reference. |

**Illustrative completion assumption:** both local decodes succeed, the new RAW renditions are valid and sufficient for fixture-level semantic planning, and human review accepts the association limits. If either RAW cannot produce sufficient local evidence, this completion variant does not become `plan-ready`; the blocked reference remains authoritative for review.

### Completion of the invalid / patched / remux family

The three paths remain three Source Items with separate identity, observations, Plan dispositions, and eventual Apply operations:

- invalid: `0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.MP4`;
- readable repaired candidate: `0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.patched-full.MP4`;
- readable missing-time candidate: `0504/DJI_001-action-sd-amber/DJI_20260504202728_0029_D.remux-faststart.MP4`.

Making the invalid item non-blocking requires all of the following:

1. The invalid item remains included and fully accounted, with its validation failure, absent time, absent direct visual evidence, and affected coverage explicit.
2. A repair-family Candidate Relation retains the shared stem, package construction evidence, partial-hash evidence, rendition similarity, conflicting metadata, and the fact that these signals do not prove identity.
3. Human review accepts the `patched-full` and `remux-faststart` local renditions as sufficient alternative content evidence for the bounded planning purpose.
4. A Coverage Relationship states that the alternative evidence represents the invalid item's otherwise unavailable visible content for planning only; it does not rewrite the invalid Source Item's facts or make the three items interchangeable.
5. `patched-full` keeps its observed time; `remux-faststart` keeps `create_date = null`; the invalid item keeps time unavailable. Any Plan-level temporal placement is a judgment over candidates, not an upstream correction.
6. Plan gives all three Source Items independent final dispositions. Apply later acts on each exact item and never deduplicates them merely because Plan grouped them together.
7. Residual uncertainty records that full content identity is not proven. If that uncertainty could materially change planning, the result remains blocked or PreCheck reopens.

**Illustrative completion assumption:** human review accepts the alternate renditions as materially sufficient, the Coverage Relationship and residual uncertainty are valid, and no organization decision requires the invalid item's missing frames or metadata. Under those conditions the invalid item does not block Plan even though it remains invalid.

### Full 2,136-item coverage construction

**Fixture fact:** the 168 historical candidate relations contain 2,133 `included_valid_media` references. Their union has exactly 2,133 unique paths and equals the complete readable JPG/MP4 manifest population.

**Illustrative completion assumption:** PreCheck constructs or validates a Coverage Relationship for each of those 168 candidate sets. Historical bundle membership is only a starting candidate; the relation must expose its members, basis, boundaries, conflicts, and expansion links and may be split or challenged without changing the source accounting.

The completed reachable set is:

```text
2,136 source-media items
  = union of 168 readable candidate-set coverage relationships  2,133
  + explicit invalid-media exception path                           1
  + explicit RAW evidence paths                                     2
```

The repair-family relation overlaps the readable-set coverage for `patched-full` and `remux-faststart` and adds the invalid item through its explicit exception path. It is an overlay, not three extra counts. The RAW/JPEG relations likewise link evidence across already counted Source Items without changing the denominator.

Every coverage entry provides:

- its exact covered Source Item set;
- representative, boundary, outlier, and conflict roles where material;
- selection basis, quality, known exclusions, and failed evidence;
- a next expansion link to the candidate set, observations, local renditions, and exact Source Item;
- a reopen condition when its representative evidence proves inadequate.

### Default frontier regions

The default frontier is not one rendered wall of 168 cards. It is a coverage graph whose top level exposes important regions and highest-risk cards while keeping every candidate-set card reachable. Plan decides which regions and cards it actually reads.

The following fixture counts are factual under the illustrative review partitions shown here; the thresholds are replaceable review methods, not contract constants:

| Frontier region | Fixture coverage and example entry | Completion behavior |
| --- | --- | --- |
| Singleton | 79 candidate sets with one readable member. A normal image singleton example is bundle 143, `0505/100MSDCF-steak-house/DSC01672.JPG`. | Show direct evidence and explicit singleton coverage; do not force artificial neighbors. |
| Normal small groups | 54 candidate sets contain 2–19 members; 27 also meet the illustrative “image-majority, representative has GPS, non-special” normal filter. Example: bundle 28, `0502/100MSDCF/DSC00227.JPG`, with five images. | Representative-first display with direct expansion to every member; add boundary/outlier evidence when internal variation warrants it. |
| Large groups | 35 candidate sets contain at least 20 readable members. Bundle 61 is the reviewed high-risk example. | Always expose size, span, boundary evidence, internal variation, and over-merge risk before claiming coverage. |
| Video-heavy | 101 candidate sets have video count greater than or equal to image count under this illustrative tag. Example: bundle 15, `0502/DJI_001-action-sd/DJI_20260502175437_0020_D.MP4`, covers two videos. | Include temporal/frame coverage and proxy limitations; one key frame cannot stand for an entire video-heavy set. |
| No representative GPS | 20 historical representatives lack GPS. Example: bundle 3, `0502/DJI_001-action-sd/DJI_20260501183924_0002_D.JPG`. | Surface GPS absence and any GPX candidate provenance; never infer online locations. |
| Abnormal time | Bundles 1 and 2 contain the two reviewed abnormal-date videos. | Force outlier/conflict visibility and retain rival time evidence without correction. |
| RAW/JPEG association | Two RAW Source Items plus their same-stem JPEG candidates. | Keep RAW independently covered; show association as candidate evidence and make RAW rendition expansion available. |
| Repair family | Invalid item plus `patched-full` and `remux-faststart`, spanning historical bundles 114, 127, and 128. | Preserve three identities, surface metadata conflict, and route the invalid item through the accepted alternative-evidence exception. |

The exhaustive size partition is `79 singleton + 54 small + 35 large = 168 candidate sets`. Video-heavy, no-GPS, abnormal-time, RAW-association, and repair-family regions are overlapping risk overlays. They change default attention, not accounting totals.

### Deterministic completion checks

Before the variant may claim Plan readiness, deterministic checks must prove at least:

1. **Source accounting:** the 2,140 discovered regular-file paths reconcile to 2,136 source media and 4 auxiliaries with zero excluded and zero unresolved.
2. **Readable candidate coverage:** the union of the 168 candidate-set covered populations equals all 2,133 readable manifest media, with no missing or foreign path.
3. **Size partition:** every one of the 168 candidate sets belongs to exactly one of singleton, small, or large; the counts reconcile to 168.
4. **Risk overlays:** every video-heavy, no-GPS, abnormal-time, RAW-association, and repair-family condition that is true has a reachable frontier entry and cannot be hidden only behind a normal representative.
5. **Exception closure:** the invalid Source Item has exactly one explicit invalid-media exception path; each RAW Source Item has a direct RAW evidence path; none is counted only through a JPEG or repair variant.
6. **Reachability:** graph traversal from the default frontier or declared exception roots reaches exactly all 2,136 Source Items. Orphan count is zero, foreign-item count is zero, and every terminal reference resolves to the sealed Source State.
7. **Evidence integrity:** every retained rendition exists, is bound to its producer input and profile, passes the declared integrity rule, and records validity and regeneration conditions.
8. **No silent identity collapse:** the three repair-family paths and both RAW/JPEG pairs retain separate Source Item identities and independent Plan dispositions.
9. **Status honesty:** missing time, invalid media, `not-requested`, proxy limitations, residual uncertainty, and any failed evidence remain visible after aggregation.
10. **Seal independence:** Plan can execute these queries without mutable Working Run state, source rescanning, or an undocumented database relation.

These checks specify proof obligations, not SQL, tables, JSON/YAML fields, directory layout, or one universal traversal implementation.

### Completion-variant status

If and only if the local RAW evidence, reviewed repair-family decision, complete Coverage Relationships, deterministic checks, immutable seal, and source-read-only/external-effect proof above all hold, the variant displays:

```text
Coverage:   complete
Readiness:  plan-ready
Integrity:  valid
```

`complete` is bounded to all 2,136 source-media items in the representative fixture and the stated fixture-level planning purpose. It does not restore original media fidelity or make the 168 candidate relations semantic truth. `plan-ready` means Plan can begin from the sealed frontier and expand without taking over PreCheck work. `valid` assumes the completed result and all retained evidence pass integrity and dependency validation.

Until a human accepts the completion assumptions and a future MediaSense run actually produces and verifies them, this remains an illustrative variant inside a `review` document. The blocked reference remains the factual current reference state.

## Progressive expansion for Plan

Plan should normally begin with the trust summary, entry validation, default frontier, exceptions, and residual uncertainty. It should not default to scanning the entire source again.

**Illustrative query path:**

```text
Level 0 — result trust and readiness
  -> Level 1 — representative / boundary / outlier / conflict frontier
      -> Level 2 — covered candidate relation and alternative boundaries
          -> Level 3 — Source Items, Observations, provenance, and reusable evidence
              -> Level 4 — original asset reference or available local rendition
```

Examples of Plan-owned queries include:

- show every blocker or material uncertainty affecting `plan-ready`;
- show the largest and longest candidate relations and their boundary evidence;
- expand bundle 61 from its representative to boundary and outlier evidence;
- show all Source Items covered only by evidence that is invalid or unavailable;
- show abnormal time candidates with raw values and provenance;
- show which GPS observations have known origin and which remain origin-unknown;
- show all items affected by one failed decoder or invalidated processing profile;
- reach the original local asset for a selected Source Item when available.

Plan may then crop, scale, compose, or re-encode existing evidence for an actual VLM request. Those attention and payload choices are Plan-owned temporary views. They do not mutate the sealed PreCheck Result.

## Plan entry, normal expansion, and reopening

### Conditions that allow entry to Plan

Plan may accept a PreCheck Result only when all of the following hold for the stated planning purpose:

- result identity, integrity, and immutable seal are valid;
- Collection and Source State identity and limits are understandable;
- the discovery boundary is explicit;
- Accounting Closure reconciles every discovered item within that boundary;
- complete or explicitly partial coverage and its limits are stated;
- required evidence is available and valid, or its absence is shown not to be material;
- Coverage Relationships reach their claimed Source Items through usable expansion links;
- residual uncertainty and known Reopen Signals are explicit;
- Evidence Sufficiency supports `plan-ready`;
- the declared source-read-only and external-effect proof is adequate within its observation boundary; this local-only reference expects zero egress and zero provider requests.

One invalid asset does not automatically block Plan. It blocks Plan when its missing content or broken coverage could materially change the intended organization and no sufficient alternative evidence exists.

### Normal Plan expansion

The following remain within Plan:

- following existing expansion links;
- reading more Source Items, Observations, Candidate Relations, or available evidence already bound by the result;
- creating temporary galleries, crops, contact sheets, or VLM payloads from existing evidence;
- selecting local or remote VLM policy under user authorization;
- interpreting evidence, proposing groups and names, and asking the user.

### Reopen PreCheck

Plan issues a Reopen Signal when the corrective action would change upstream evidence authority, including when:

- a material source region or discovered item is absent from accounting;
- a representative hides a major difference in its claimed covered set;
- an expansion path is missing or cannot reach claimed items;
- required evidence was not requested, failed, is invalid, or must be newly acquired;
- candidate membership, provenance, validity, or quality is materially unreliable;
- a source change makes the Source State incompatible;
- repeated Plan-side inspection shows that the default frontier routinely transfers preprocessing work into Plan.

Reopening starts or resumes mutable PreCheck work and seals a new PreCheck Result. It never edits the old result in place.

## External-effect and source-read-only proof

The trust page must distinguish four kinds of statements:

1. **Declared policy:** remote calls, uploads, online maps, reverse geocoding, and billable models are disabled by default; an enabled coordinate reverse-geocode producer is bound to a frozen logical query set and explicit user confirmation.
2. **Enforced boundary:** the runtime restrictions that prevent or constrain those effects.
3. **Observed facts:** requests, egress, providers, fees, and source writes observed within the MediaSense control boundary.
4. **Unknown outside scope:** external processes or infrastructure the run could not observe.

`plan-ready` requires an honest proof, within that boundary, of:

- zero media upload;
- zero general metadata or feature-artifact egress;
- zero remote-model calls;
- either zero coordinate/online-map egress or an exact confirmed all-source reverse-geocode query set with provider, datum, actual-request, per-located-Source-Item result-state, and authorization evidence;
- zero billable requests when the local-only path is claimed, otherwise an explicit observed or unknown billable-call count rather than an inferred zero;
- no source-media mutation.

Configuration intent alone is not proof. A network-disabled claim and an observed zero-request audit answer different questions and should both be visible. Historical AI Album reverse-geocoded location text and remote semantic caches are excluded from PreCheck authority even when they exist in the fixture; a new confirmed PreCheck observation may independently provide equivalent candidate evidence.

## Working Run, interruption, reuse, and sealing

The user should see a Working Run as progress toward a possible result, never as a partially sealed authority.

### Reference lifecycle

| Event | User-visible behavior | Retained meaning |
| --- | --- | --- |
| Work starts | Declared source boundary, profile, local resource budget, current phase, completed/remaining counts | Mutable Working Run only. |
| Item completes | Its reusable observations and evidence become available to later work | Completion is item- and profile-specific. |
| One item fails | Failure, affected evidence, retryability, and downstream impact are localized | Unrelated completed work remains reusable. |
| Process is interrupted | Checkpoint and last durable progress are shown; no sealed result is claimed | Resume may reuse completed valid work. |
| Source volume disconnects | Source becomes unavailable; previously seen files are not reported as deleted | Resume waits for a compatible source state. |
| Source or profile changes | Only affected dependencies are invalidated where that can be proven | Unaffected reusable work remains valid. |
| Preparation reaches a stopping decision | Sufficiency, residual uncertainty, blockers, and proof facts are evaluated | The run may continue or seal an honest result. |
| Result seals | Identity, integrity, status axes, source binding, and immutable content become fixed | No mutable Working Run state is required by Plan. |
| New evidence is needed later | A Reopen Signal starts new work | A new result version is sealed; the prior result remains history. |

The product goal is efficient entrustable preparation at scale. Long runtime is a condition to survive, not a target or proof of thoroughness.

## Stable contract candidates

Human approval of this reference should permit later contract design to require these meanings, without yet choosing their physical encoding:

- immutable result identity, integrity, version, and Source State binding;
- declared discovery boundary and reviewable Accounting Closure;
- stable Source Item references and distinct scope, support, validation, attempt, and availability meanings;
- Observation and Derived Evidence provenance, profile, quality, validity, and regeneration conditions;
- challengeable Candidate Relations rather than opaque final groups;
- Coverage Relationships with covered sets, evidence roles, exclusions, and expansion paths;
- Evidence Sufficiency, residual uncertainty, blockers, and known Reopen Signals;
- separate coverage, readiness, and integrity axes;
- local-resource and external-effect facts sufficient to support the source-read-only boundary and either a local-only run or explicitly confirmed coordinate enrichment;
- Working Run versus sealed-result lifecycle, resumability, localized failure, incremental reuse, and immutable replacement semantics;
- deterministic review checks plus a regenerable human/Plan review projection.

## Replaceable artifacts and views

The following may be useful and reusable, but their concrete form is not a permanent product entity:

- SQLite or another structured store;
- exact filesystem layout and filenames;
- thumbnails, sampled frames, crops, contact sheets, and video proxies;
- embeddings, vector dimensions, indexes, fingerprints, and distance metrics;
- detector outputs, taxonomies, thresholds, and clustering intermediates;
- a particular representative-selection or boundary-selection algorithm;
- Markdown, HTML, gallery, map, tree, or query UI review projections;
- Plan-owned VLM crops, mosaics, encodings, and payloads;
- hash algorithms, cache keys, checkpoint formats, and invalidation implementation;
- the historical AI Album bundle count, directory tree, captions, titles, locations, and names.

The stable capability is that a stronger future Agent can query trustworthy source accounting, evidence, provenance, coverage, uncertainty, and expansion paths. It must not be constrained to today's storage or compression method.

## Material review questions

Human review should answer these before the example becomes `active` or a formal contract is extracted:

1. Is the proposed distinction between scope disposition and processing/availability outcome understandable enough that counts cannot be double-counted or hidden?
2. Are the proposed local RAW decode, rendition, provenance, association, and expansion requirements sufficient to close both RAW evidence gaps without demoting either RAW item?
3. Does the invalid/`patched-full`/`remux-faststart` evidence justify the proposed content-representation relationship, or must provenance remain a blocker?
4. Does the size partition plus overlapping video-heavy, no-GPS, abnormal-time, RAW-association, and repair-family regions provide an adequate default frontier for this fixture?
5. Is the bundle 61 frontier concrete enough to demonstrate representative, boundary, outlier, and conflict behavior while leaving Plan free to choose what it reads?
6. Are the ten deterministic proof obligations sufficient for a human to trust 2,136-of-2,136 reachability without inspecting raw structured storage?
7. If all completion assumptions pass, is `complete + plan-ready + valid` the correct bounded result, or should proxy-media limitations require a declared bounded `partial + plan-ready + valid` result instead?

## Coverage, stopping rule, and reopen conditions

This reference is sufficient for human review when a reviewer can determine, without reconstructing missing product logic:

- what the ordinary user sees first and why it should establish trust;
- what Plan queries by default and how it expands progressively;
- how every discovered item must receive a visible disposition;
- which conditions permit Plan entry;
- which activities remain normal Plan expansion;
- which defects require a new PreCheck Result;
- which meanings must survive into a stable contract;
- which stores, artifacts, methods, and views remain replaceable;
- where fixture evidence ends and illustration begins.

Stop after human review of this reference. Do not proceed in this document to Storage Lifecycle, a formal schema, SQLite design, Tool or Skill implementation, or fresh replay.

Reopen this reference before contract extraction if:

- a reviewer cannot reconcile source counts or distinguish dispositions from processing outcomes;
- a material conclusion cannot be expanded to its supporting items and evidence;
- the default frontier cannot normally support Plan without broad source reprocessing;
- the SQLite/filesystem split would create two conflicting authorities or a review projection that can drift from the sealed result;
- an important uncertainty has no consequence for readiness, continuation, stopping, or reopening;
- new fixture or original-source evidence contradicts a displayed fact or closes a limitation on which the prototype currently relies.
