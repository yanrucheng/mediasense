---
id: "spec-260828-2026-default-organization-profile"
title: "MediaSense Default Organization Profile"
type: spec
status: active
created: 2026-08-28
updated: 2026-08-28
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "eval-260823-1918-ai-album-migration-baseline"
  - "spec-260827-1138-frozen-plan"
  - "spec-260827-1915B-plan-work"
superseded-by: ""
tags: ["mediasense", "plan", "organization-profile", "default-policy"]
---

# MediaSense Default Organization Profile

## Decision

This document defines MediaSense's default product policy for the logical media tree proposed during Plan. It preserves the useful shape repeatedly observed in the owner's accepted media collections: events are the primary browsing unit, simple events remain shallow, complex events expand only as needed, related media stay together, and auxiliary or unresolved material remains visibly separated from normal groups.

This profile is a versioned product policy, not a Tool-managed object. It has no `profile_ref`, registry, independent runtime lifecycle, or public operation. `mediasense.plan.work` continues to store only the exact plan-scoped `organization_preferences` snapshot. The Planning Agent applies this default when preferences do not override it, combines it with the actual Dataset evidence and Human feedback, and writes only the resulting organization into candidate content. A Frozen Plan remains self-contained and does not require this profile to be interpreted or applied.

The policy and a complete conforming Frozen Plan example have received Human review. The later Hong Kong exercise remains an end-to-end product acceptance target rather than a prerequisite for this policy. Its naming and folder examples are product proposals, not historical or geographic truth.

## Evidence boundary

The policy draws on two different forms of evidence without treating either as product authority:

- the AI Album migration baseline establishes the historical generated shape and operational behavior;
- a Data Estate read-only investigation of seventeen non-Hong-Kong owner-retained final collections shows repeated final-tree patterns, including event-first naming, adaptive depth, ordered content groups, co-location of related media, and separate auxiliary or exceptional material.

The automatic AI Album trees for those final collections were not retained, so the evidence does not prove which individual directories were manually renamed, merged, split, or moved. It supports the recurring final shape, not a mechanical replay of historical edits.

`dataset:yr-230520-8` and `260501-HK美食之旅` are excluded from policy fitting. The available May 7 source-tree snapshot predates the verified May 9 AI Album production run. The Hong Kong collection is instead the future end-to-end acceptance exercise for MediaSense.

## Default logical shape

```text
<logical-root>/
├── YYMMDD-<small-event>/
│   ├── <media-and-related-files>
│   └── ...
├── YYMMDD-<large-event>/
│   ├── MMDD-<place-or-daily-theme>/
│   │   ├── 1-<content-group>/
│   │   └── 2-<content-group>/
│   ├── a-files/
│   └── d-damaged-info/
├── Uncategorized/
└── d-damaged-info/
```

The tree shows the available roles, not mandatory directories. Empty or redundant layers are omitted. The default maximum is three semantic levels below the logical root:

1. event;
2. chapter within a complex event, commonly a date/place or date/theme combination; and
3. ordered content group within a chapter.

Auxiliary and exception containers do not count as semantic grouping levels. A deeper tree requires a specific Human preference or a reviewed reason visible during Plan; item count or a fixed clustering threshold alone does not justify it.

## Event and depth policy

- The event is the primary Human browsing unit.
- A small or semantically coherent event places its media directly in the event directory. Plan must not create a one-child chapter or content-group directory merely to reproduce a nominal hierarchy.
- A large or heterogeneous event may add chapters when they make distinct days, places, or themes materially easier to browse.
- A chapter may add ordered content groups when several meaningful scenes or activities would otherwise be mixed together.
- The Planning Agent decides whether a distinction is meaningful from available evidence and Human intent. File counts, geographic distances, embedding thresholds, cluster weights, and model pipelines are replaceable methods and are not part of this profile.

## Naming and ordering

- A normal event name defaults to `YYMMDD-<event-name>`. For a multi-day event, the event date is its chosen identifying or starting date; uncertainty must remain visible rather than fabricated.
- A chapter within a multi-day event defaults to `MMDD-<place-or-daily-theme>` when the date is useful for navigation. A same-day thematic chapter may use a concise Human-readable name without repeating unhelpful date text.
- Ordered content groups default to `<number>-<name>`, such as `1-女木島` and `2-男木島`.
- Numeric prefixes express intended browsing order. They need not be contiguous and may preserve an intentional domain-specific code confirmed by the Human. Lexical sort behavior alone must not change the intended order.
- Names should be concise, distinguishable among siblings, and natural to the Human. Sanitization removes or replaces only characters required for the target filesystem; it must not silently rewrite meaning.
- Source basenames are preserved by default. Any rename needed to avoid a collision or satisfy an explicit Human decision belongs in the Frozen Plan as an exact override.

## Related media

Files that belong to one captured moment or source-media bundle remain together by default. This includes, when the evidence supports the relationship:

- RAW and rendered image pairs;
- image and XMP sidecars;
- Live Photo image/video pairs;
- a video and its camera-native companions such as LRF, AAC, THM, SCR, XML, WAV, or M4A; and
- burst or near-adjacent captures that form one meaningful sequence.

The profile does not create `RAW/`, `JPEG/`, or `Videos/` directories by default. Format is secondary to event and capture context. A Human preference may choose a different organization, but Plan must preserve the relationship and make every in-scope item accountable.

## Auxiliary material

Auxiliary material that is useful with the collection but is not normal browsable media is separated from ordinary groups. The default reserved container is `a-files/`; a narrower child such as `a-files/GPX/` may be used when it adds useful orientation.

This treatment is appropriate for track files, handoff notes, camera support material, or other supporting artifacts only when they are inside Plan scope. The profile does not require copying evidence or PreCheck artifacts into the output tree.

## Valid but unresolved media

`Uncategorized/` is the fallback for readable, in-scope media that cannot be assigned to a trustworthy event or group. It is not a substitute for ordinary Agent judgment.

- If the event is trustworthy but the finer group is not, place the media at the event or chapter level rather than in root `Uncategorized/`.
- Use `Uncategorized/` at the nearest trustworthy level when doing so preserves known context.
- Use the root container only when no trustworthy event is known.
- Plan inspection must make unresolved membership and its extent visible before seal.

## Damaged or unreadable media

Damage does not by itself break contextual membership. Plan uses the strongest trustworthy non-content evidence available:

1. If same-stem relationships, a burst sequence, temporal adjacency, source-directory context, or another reliable association identifies the group, the damaged item follows its related media into the normal group.
2. If only the event or chapter is trustworthy, the item remains at that nearest trustworthy level without a fabricated finer classification.
3. If contextual association is not trustworthy, the item goes to `d-damaged-info/` under the nearest trustworthy event or chapter.
4. If no event can be established, it goes to the root `d-damaged-info/`.

`d-damaged-info/` is distinct from `Uncategorized/`: the former records an unreadable or damaged item whose placement cannot be resolved; the latter contains readable media whose semantics remain unresolved. A normal group may therefore contain a damaged item when its relationship is still known.

The Frozen Plan must still account for every in-scope Source Item. If later Apply cannot safely materialize a damaged item, that execution outcome belongs to Apply's deterministic safety and receipt semantics rather than a new semantic decision.

## Preference and authority rules

- Explicit Human preferences override this default within their authorized scope.
- Dataset evidence may justify a departure, but the Agent must present a material or easily misunderstood departure for Human review.
- `organization_preferences` records the exact preferences used by one Plan Working State; it is not a pointer to this document and does not make the Tool choose names or groups.
- The Frozen Plan contains final paths, memberships, source-name overrides, and justified other outcomes. It does not store a dependency on this profile.
- Apply executes the Frozen Plan exactly. It must not reinterpret this profile or make new organization decisions.

## Deliberate non-defaults

The profile does not default to:

- fixed location distances, content-similarity thresholds, cluster sizes, or folder-count limits;
- a mandatory location layer or a mandatory content-group layer;
- top-level `Memory`, `Recording`, `Raw`, `Compressed`, or device-model partitions;
- separation by image/video/RAW file format;
- copying PreCheck Evidence, caches, thumbnails, or databases into the final media tree; or
- treating historical AI Album output, a Dataset's original layout, or a model-generated label as unquestionable truth.

These may be selected for a particular Plan when the Human asks for them or the Dataset provides a reviewed reason.

## Worked product proposal

The following names and hierarchy are illustrative product proposals. They do not assert historical facts about Hong Kong or any other collection.

```text
Media/
├── 260501-香港美食之旅/
│   ├── 0501-抵达与晚餐/
│   │   ├── 1-街区漫步/
│   │   └── 2-晚餐/
│   ├── 0502-城市游览/
│   ├── a-files/GPX/
│   └── d-damaged-info/
├── 260520-家庭晚餐/
│   ├── IMG_0001.JPG
│   ├── IMG_0001.ARW
│   └── IMG_0001.XMP
└── Uncategorized/
```

The Hong Kong labels above are product proposals only. When the real Hong Kong acceptance exercise begins, MediaSense must derive and review its organization from the sealed PreCheck Result and Human feedback rather than treating this example as expected truth.

## Acceptance boundary

This active profile is accepted because the accompanying complete proposed Frozen Plan demonstrates that the existing artifact contract can express:

- a folded small event;
- a multi-day or otherwise complex event with ordered groups;
- related media kept together across formats;
- an auxiliary-material outcome;
- a damaged item that follows known context and one that falls back to `d-damaged-info/`; and
- readable but unresolved media placed in `Uncategorized/` at the nearest trustworthy level.

The later Hong Kong end-to-end exercise evaluates product quality but is not required to make this policy document syntactically valid or independently interpretable.
