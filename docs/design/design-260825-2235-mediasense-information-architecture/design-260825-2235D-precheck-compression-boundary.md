---
id: "design-260825-2235D-precheck-compression-boundary"
title: "MediaSense PreCheck Compression Boundary"
type: design
status: active
created: 2026-08-26
updated: 2026-08-26
timezone: "Asia/Shanghai"
parent: "design-260825-2235-mediasense-information-architecture"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235A-information-domain-map"
  - "design-260825-2235B-stage-ownership"
  - "eval-260823-1918D-ai-album-stored-information"
  - "clarify-260826-1819-precheck-contract-concepts"
superseded-by: ""
tags: ["mediasense", "precheck", "compression", "handoff-boundary"]
---

# MediaSense PreCheck Compression Boundary

## Status and purpose

This document records the accepted conceptual model for the PreCheck-to-Plan handoff. It preserves the reasoning that emerged from inspecting the first concrete PreCheck reference handoff and testing a smaller abstraction against materially different compression approaches.

It does not define a schema, Tool, file layout, query API, storage lifecycle, or serialized contract. Its authority is limited to why PreCheck exists, the minimum semantic concepts and relations that follow from that purpose, and which details must remain replaceable.

The reference instance exposed an abstraction error: SQLite, YAML files, GPS, RAW treatment, representative images, run progress, and Plan guidance were allowed to resemble permanent handoff structure before each entity and field had justified an independent responsibility, authority, and lifecycle. This is not primarily a naming problem. It is a boundary problem.

## Why PreCheck exists

If time, compute, model context, and money were unlimited, Plan could inspect every original asset directly. At that limit, a separate PreCheck stage would add little value. PreCheck exists because real collections may contain tens of thousands, millions, or more media assets, while direct semantic inspection is slow and expensive.

PreCheck's essential product responsibility is therefore **compression**:

> Produce, at low and sustainable cost, a sealed and progressively explorable representation that substantially reduces what Plan must inspect by default without silently losing the ability to account for and return to the source.

Scanning, metadata extraction, thumbnails, embeddings, grouping, anomaly detection, indexes, and databases are possible means. None is the purpose itself.

## Accepted conceptual model

> PreCheck produces, for a continuing Dataset, an immutable compressed Result that directly accounts for its bounded Source Items and lets downstream work begin from substantially smaller Evidence, expand progressively, trace in both directions, and inspect material loss, exceptions, and unknowns.

The model has four addressable logical concepts and five authoritative relationship meanings. They are not files, tables, or algorithms:

```text
Dataset
└── referenced by an immutable PreCheck Result
      ├── accounts_for ──────→ Source Items
      ├── entry_evidence ────→ Evidence
      └── Evidence
            ├── represents ──→ Source Items
            ├── derived_from → Source Items or Evidence
            └── expands_to ──→ Source Items or Evidence

Material loss, exceptions, and unknowns qualify the result,
an entity, or a relationship wherever their consequence belongs.
```

### Dataset

A continuing business subject whose contents may change while its identity and attributable context persist. Dataset identity comes from the user or owning product; it is not inferred from a directory path, whole-population hash, cluster, or one PreCheck run.

This continuity matters because new or moved media may reuse unaffected PreCheck work and because Dataset-level context may inform later planning. It does not make a mutable current inventory part of an old Result.

### Source Item

A concrete source object directly accounted for by one Result. A Source Item may be source media, an auxiliary input, an excluded object, or a discovered object in an unsupported, invalid, error, or unresolved condition. Scope and condition are independent.

Its reference is stable within the Result. Its locator allows access to the observed source object. Paths, fingerprints, and other implementation-owned identity evidence may support incremental reuse across Results, but no one mechanism becomes the permanent cross-stage identity contract.

### PreCheck Result

The only authoritative PreCheck product that crosses into Plan. It references one Dataset, directly accounts for every Source Item in its declared boundary, exposes low-cost entry Evidence, and fixes the relationships used for downstream navigation. A later source change, correction, or stronger compression produces a new Result rather than mutating the old one; unaffected internal work may still be reused.

The Result states coverage, readiness, and integrity independently. Immutability fixes result meaning and relationships; it does not require every pagination, ordering, contact sheet, attention view, or other regenerable presentation to have been materialized in advance.

### Evidence

An inspectable expression whose downstream reading cost is lower than directly reading what it represents. Evidence may be a rendition, media excerpt, source item reused directly, text, structured summary, time range, sampling result, or a future form not yet chosen. It is not necessarily a separate file and does not become source truth.

An entry surface is not an additional entity or a natural-language role field. It is the Result's `entry_evidence` relationship to one or more Evidence items selected as a low-cost starting point.

### Relationships

The semantic connections that make compression accountable and navigable have five independent meanings:

- `accounts_for`: which Source Items belong to the Result's immutable accounting boundary, including independent scope and condition;
- `entry_evidence`: where Plan can begin at low cost;
- `represents`: which Source Items the Evidence lets downstream work defer reading;
- `derived_from`: which Source Items or Evidence actually produced it; and
- `expands_to`: which already-produced detail can be inspected next.

These meanings cannot be collapsed. One image may be derived from one Source Item while representing many. Evidence may also derive from other Evidence, preserving multi-step provenance. `represents` remains a challengeable compression claim rather than source truth.

Relationship records need no independent object identity. A paged query states origin, relation, and direction once; members contain targets and only their distinct basis or qualifications. Shared basis and qualifications belong to the page. `attention_items` is a derived query view over exceptional `accounts_for` members, not a sixth authoritative relationship.

## What compression requires

A trustworthy compressed result has structural consequences independent of the current algorithm:

1. **Reduced default reading cost.** Plan can begin without reading the entire source population.
2. **Bounded source identity.** The Result directly and immutably accounts for the Source Items within its declared boundary; later Dataset changes do not silently alter that meaning.
3. **No silent disappearance.** Every discovered Source Item has an explicit scope and condition through `accounts_for`, including exclusions, unsupported material, failures, and unknowns.
4. **Traceability in both directions.** Evidence can be traced to what it represents and what produced it, and a Source Item can be located in the compressed Result.
5. **Progressive expansion.** Plan can move from a small entry surface through already-produced detail toward particular source assets without default full-source inspection.
6. **Visible loss and limits.** Material variation that may have been hidden, unavailable content, uncertain relations, omissions, and evidence limits remain challengeable.
7. **Stable inspection.** A planning session queries one sealed result rather than hidden mutable working state.
8. **Open methods.** Replacing clustering, sampling, models, storage, or artifact forms does not require changing the preceding guarantees.

These are accepted invariants because removing one can make compression cheap but no longer entrustable.

## Clustering is not the invariant

Clustering is one possible compression method, not an inevitable product entity. Compression may instead or additionally use:

- lower-fidelity one-to-one renditions;
- multiple key frames for one video;
- one Evidence item for many similar assets;
- several Evidence items jointly covering overlapping source sets;
- timelines, indexes, sampling, summaries, anomaly surfacing, or methods not yet chosen.

The stable abstraction is not a cluster. It is the inspectable and navigable relationship between smaller Evidence and the larger source population. That relationship may be one-to-one, one-to-many, many-to-one, or many-to-many.

GPS, time, RAW, captions, thumbnails, embeddings, and model outputs are likewise possible observations, content, or methods beneath this boundary. Their current usefulness does not make them permanent handoff fields.

## Runtime responsibility is not the stage handoff

PreCheck also has an internal operational responsibility: long work must be observable, interruptible, resumable, incrementally reusable, locally invalidatable, and honest about partial progress and localized failure.

Mutable working state may therefore record checkpoints, completed work, dependencies, failures, reuse decisions, invalidations, and process events. A user or operator may need a review or audit surface over that state while the run is active or being diagnosed. This information has real value, but its purpose is to operate and inspect PreCheck, not to give Plan a second input product.

The distinction is:

```text
mutable Working Run
  owns progress, checkpoints, reuse, invalidation, failure localization, and process audit
        |
        | may eventually produce
        v
sealed PreCheck Result
  owns the stable compressed representation and the claims needed to rely on it
```

The complete working log should not be copied into the cross-stage contract. A sealed result may retain only those provenance, integrity, source-read-only, offline, or limitation claims needed to establish the result's trust boundary. It must not depend on mutable working state after sealing.

This resolves the apparent overlap between `working-state.yaml` and `final-result.yaml` in the first sample: they may illustrate two lifecycle states, but that does not justify two permanent cross-stage file types. Working state belongs to PreCheck operation. The sealed result alone crosses into Plan.

## Storage and access boundary

SQLite is a reasonable PreCheck internal implementation and may even be its internal authoritative store. It is not the stage interface. If Plan reads its tables directly, table names, columns, migrations, indexes, and storage choices become accidental cross-stage contracts.

Plan should instead bind every read to an immutable result identity and use stable, read-only product semantics. A Tool or equivalent access boundary may translate those semantics onto SQLite today and another implementation later. It must not silently resolve to a mutable "latest" result.

Conceptually:

```text
PreCheck algorithms and mutable runtime
        -> internal SQLite, files, caches, checkpoints, evidence artifacts
        -> seal(result identity)
        -> read-only semantic access bound to that result
        -> Plan
```

The active read boundary uses one Tool with `inspect` and `traverse`; its exact contract belongs to the formal specification. The important separation is that downstream consumers depend on product meaning, not storage representation.

## Questions implied by compressed delivery

Stable downstream questions should be derived from compression rather than copied from current fields:

- Where is the low-cost place to begin inspecting this result?
- Which Dataset and explicitly accounted Source Items does this Result describe?
- What does an Evidence item represent, and what are the limits of that compression claim?
- Where is a particular source item represented?
- How can existing detail be expanded progressively toward particular source assets?
- Which material was not normally represented, and where are its exception, failure, exclusion, or unknown paths?
- What material variation or uncertainty may the compression hide?
- Can the current sealed result still answer the planning need, or is new upstream compression work required?

These are questions Plan may ask of PreCheck's result. They are not instructions from PreCheck about how Plan must reason, which evidence it must read, or how it constructs a VLM payload.

## Consequences for the first reference instance

The concrete review pack remains useful because it made the abstraction problem visible, but its files and fields must not be promoted directly into a contract:

- `precheck.sqlite` is a plausible internal implementation, not a Plan handoff format;
- `working-state.yaml` illustrates runtime responsibility, not a required delivered file;
- `plan-default.yaml` resembles one regenerable entry projection, not a permanent authority and not a place to prescribe Plan behavior;
- `final-result.yaml` may contain useful result-level meaning, but its existence and every field still require necessity tests;
- `audit.json` mixes potentially material trust claims with construction-specific process facts and should not automatically become a separate product entity;
- evidence artifacts may exist, but their directory names, encodings, and generation methods remain replaceable.

Every proposed entity and field must answer:

1. What indispensable meaning does it carry?
2. Which stage owns that meaning, and where is its authority?
3. What downstream responsibility becomes impossible without it?
4. Can it be derived without losing material semantics?
5. Is it only an artifact of the current method or implementation?
6. Does it improperly express another stage's responsibility?
7. Would it remain meaningful under a substantially different PreCheck implementation?

## Pressure-test results

The minimal Dataset, Result, Source Item, Evidence, and relationship model was tested against three materially different producers. The test asks whether each producer can expose its real compression semantics and limitations without imitating the current implementation or inventing guarantees it does not possess.

### Current MediaSense candidate and Hong Kong material

The current approach maps naturally:

- the continuing subject maps to Dataset, while the reviewed media population is expressed by each Result's direct `accounts_for` relation to Source Items;
- image renditions, video frames, RAW previews, structured summaries, and group entry material can all be Evidence;
- group coverage, production lineage, source lookup, and progressive detail map to the five accepted relationships;
- unreadable media, missing observations, uncertain repair-family identity, proxy fidelity, and possible hidden variation qualify the appropriate Result, Source Item, Evidence, or relationship.

SQLite, YAML, clustering, GPS, named frontier roles, and evidence filenames remain possible implementations or content. None is required by the model. The first sample's business information can therefore be retained without promoting its storage or field layout into the handoff.

### Historical AI Album

AI Album preserved substantial compression value: ordinary and high-resolution thumbnails, video sample frames, metadata, embeddings, bundles, representatives, and clustered output. These map to Evidence, observations, or relationships where the historical material actually preserves their derivation or membership.

The mapping also exposes rather than repairs historical gaps:

- the native output did not bind its Dataset, completely accounted Source Items, effective configuration, caches, and output into one immutable Result;
- it did not provide a complete handoff-level proof that every source item was represented or had an explicit exception path;
- some bundle membership and source traceability had to be reconstructed or added by the later fixture package rather than read from one native authoritative result;
- compression loss, hidden variation, omissions, and uncertainty were not systematically retained.

Captions, inferred locations, titles, privacy results, embeddings, and similar information are not lost by the model. They may be exposed as Evidence or observations when useful, but their presence does not turn those particular semantics into permanent PreCheck concepts. Historical semantic judgments that belong to planning remain comparison evidence rather than PreCheck truth.

The accepted eighteen-class historical inventory remains authoritative in [AI Album Stored Information Inventory](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918D-ai-album-stored-information.md); this module records only what its mapping demonstrates about the handoff model.

### Plausible implementation without clustering

A different producer may create low-fidelity renditions, divide a collection into inspectable ranges, sample each range, extract video excerpts, surface exceptions separately, and permit progressive expansion without computing clusters.

It still maps naturally:

```text
range entry
  -> sampled Evidence
  -> denser existing Evidence
  -> particular Source Items
```

Compression may reduce bytes, decode cost, attention cost, or the number of items read initially; it need not always reduce the number of stored objects. This producer satisfies the model if its entry cost is materially lower for the declared purpose and its coverage, traceability, expansion, loss, and exceptions remain inspectable.

### Pressure-test judgment

All three producers fit without making clustering, metadata categories, database layout, or artifact form permanent. The current producer retains its information, AI Album's missing guarantees remain honestly missing, and the non-clustering producer does not have to masquerade as today's design. No additional core concept is justified by these tests, and relationship records need no separate object identity.

## Boundary and follow-on contract

This document stops at the accepted conceptual model. The active [PreCheck Read Contract](../../spec/spec-260826-1546-precheck-read/index.md) owns the stable machine-facing access semantics derived from these concepts, five relationships, and eight invariants.

Internal storage and implementation remain outside this document's authority. The downstream Tool name, request and response contract, and development Mock are fixed by the formal specification.
