## Context and accepted decisions

The [basic model](../../../docs/model/model-260913-1408-precheck-basics.md), [Foundation](../../../docs/design/design-260823-1918-mediasense-foundation.md), [compression model](../../../docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md) and [reusable-capability architecture](../../../docs/design/design-260830-1527-reusable-capability-architecture.md) govern this change.

The Human has accepted ordinary new Runs, interface A (explicit complete requirements), business-agnostic design, local parameter changes with unchanged parameters elsewhere, and possible changes in derived groups through actual dependencies. PreCheck prepares and compresses evidence; Plan interprets it and chooses where more preparation is useful.

```text
Run A → immutable Result A
            ↓ Plan selects T within the same accounted collection S
Run B
├── explicit S
├── complete Profile
│   ├── base compression P
│   └── T uses complete compression P′
├── valid computation reused by its real dependencies
└── immutable Result B → a new ordinary Plan Work
```

Trees describe relationships, not additional stored entities. This design does not introduce Subrun, a revision Run, or a Profile lifecycle.

## Goals and non-goals

Deliver the same-collection round trip through public Tools: read settings, choose a bounded subset, start a new Run, inspect its Result, and retain justified Plan decisions. First delivery supports input snapshots from one prior Result; it does not automatically reconcile arbitrary moved/deleted/added media or merge Results.

Do not build an attribute-by-attribute public Tool family, public cache API, generic mapping service, implicit profile patch operation, or a new semantic classifier. The present compression algorithm remains replaceable. This change does not select a pure-threshold algorithm or authorize a new global compression policy.

## Backward Compatibility Policy

The existing Zero public API BC policy applies. There is no new API version router, compatibility alias or dual write. Normal old start requests remain meaningful because the new fields are optional, not because a compatibility layer is being introduced. Published Result bytes and existing Work state remain protected. Historical Read projection may truthfully report missing new information; it may not synthesize it from mutable Run state.

## 1. Exact public request

The implementation Agent will incorporate the following proposed shape into the existing [Run contract](../../../docs/spec/contract/precheck-run/index.md) and machine schema before implementing execution. This OpenSpec defines the intended change; the current public contract has not been changed by this planning task.

```text
start
├── dataset_ref, request_id
├── prior_result_ref?       existing association / Source Set reference context
├── source_set?             explicit immutable input snapshot
└── profile?
    ├── configuration_identity
    ├── compression         complete parameters, or null
    └── overrides[]
        ├── source_set
        └── compression     complete parameters, or null
```

`source_set` requires `prior_result_ref`. In this first delivery it must resolve to the prior Result's complete `accounts_for` membership. Scope roles are part of those explicitly selected input records: excluded/auxiliary entries remain accounted and are not silently promoted to source media. Newly discovered directory entries are not added. A smaller outer set is rejected with `invalid_source_set`; the supported local variation is an override within the same S. Ordinary discovery and scope confirmation remain available by omitting `source_set`.

Omitted `profile` means resolve and freeze current Dataset defaults. A supplied Profile is a complete value: no omitted compression fields, default insertion into overrides, or inheritance from an old Result. Nonempty overrides require the explicit input snapshot. Every override must select nonempty, processable `source_media` within S; overlaps are rejected even when parameter values match. Array order establishes frozen scope positions, not precedence.

The four public compression parameters are `target_entries`, `temporal_scale_seconds`, `spatial_scale_meters`, and `content_distance_scale`. They already exist in the compression implementation and respectively control count fallback, temporal/spatial boundary scales and cosine-distance threshold. Lower content distance makes content separation stricter. All four must be supplied in every non-null value. `null` bypasses final adaptive compression for that partition; it does not turn source files into semantic business objects. The rest of the compression recipe, representation selection and preparation settings are fixed by the configuration identity.

### Why a configuration identity is necessary

The complete public Profile must not silently combine an old compression value with newly changed metadata/model/Geo defaults. Copying all private `execution_config` fields would expose paths and scheduling implementation and create many unrelated public knobs. An equality guard is sufficient for this delivery.

`configuration_identity` is a SHA-256 content identity of the resolved non-editable preparation semantics, not a Profile ID, cache key, lookup handle or authorization. Start resolves the current settings and compares their identity before accepting a new request. A mismatch yields `configuration_changed`; it never loads an old Result's configuration to merge or execute it. The caller can restore the intended configuration or deliberately start with current defaults, then read the newly recorded Profile. Read always returns the identity sealed at preparation time.

Identity construction is fixed below so implementation tracks cannot choose different projections. Canonical JSON is UTF-8, sorted object keys, unchanged array order, no nonfinite numbers and compact separators. Hash the object `{"kind":"precheck-preparation","values":...}`. The `values` object has these exact keys:

| Key | Semantic value |
| --- | --- |
| `metadata` | enabled flag and the complete effective MetadataProfile value, including its fixed knowledge/context |
| `gpx` | enabled flag and the installed GPX matching recipe identity |
| `image_renditions` | enabled flag and the installed ordinary/high-resolution rendition recipe identities |
| `video` | enabled flag, frame limit and probe/frame/contact-sheet recipe identities |
| `bundles` | enabled flag and base association recipe identity |
| `visual_selection` | installed initial-selection recipe, its resolved base target and explicit directed inputs from existing configuration |
| `embedding` | null when disabled; otherwise effective semantic profile and encoder/model identity |
| `sensitivity` | sorted enabled detector identities and semantic profiles; disabled entries are represented only by their disabled policy |
| `geo` | complete existing effective lookup/routing/retry semantics; never credentials, proxy secrets or prior consent |
| `compression_recipe` | installed algorithm/representative-selection recipe identity and fixed non-public selection/comparison settings |

Installed recipes must include output-affecting implementation revisions. Public compression parameters and overrides are excluded. Run identity, Dataset display name, artifact paths, local model locations, storage hints, batch size, threads, resource admission and credentials are excluded. If a supposedly operational option changes output meaning, the owning recipe must include that semantic choice. Missing immutable model declarations are reported; a valid cache hit must not require loading model weights or inference libraries.

The first implementation adds one internal pure projection function, `preparation_configuration_value(config, recipes) -> JSON object`, and one hash function over that value. `recipes` are supplied by the composition root from existing producer declarations; no registry or discovery service is introduced. Its implementation must supply synthetic input/value/hash vectors that prove semantic changes affect the identity while pure scheduling and location changes do not. No validator or test implementation belongs to this planning task.

## 2. Scope and actual compression behavior

Resolve overrides before expensive preparation. Let T1…Tn be disjoint selected sets and R = source_media(S) minus their union. R uses base P; Ti uses its declared Pi. Final compression never crosses these partitions. A previous representative that spans a boundary is expanded through its exact source membership before selecting inputs; its own observations must never stand for unobserved members.

The existing initial selection is evaluated using its frozen base preparation settings. Public local compression parameters do not alter that base sampling budget. Explicit override members become directed preparation demands, so adjusting a threshold cannot silently operate only on the old representative. Reuse all valid renditions/embeddings; prepare missing local inputs only where the demanded comparison or a changed representative actually needs them. Boundary dependencies can require preparation outside T, but never outside S or the authorized effect/resource envelope.

Final compression may reuse metadata, time, geography and embeddings as evidence. It does not interpret why Plan chose T. A configured content-comparison mode with a missing backend remains a known prerequisite failure; a disabled mode is not silently enabled. If a requested change in `content_distance_scale` cannot take effect because content comparison is disabled, reject that override with `configuration_invalid`. Known corrupt inputs retain source-local failure/qualification; they do not become fake successful comparisons.

This implementation choice keeps existing count fallback when comparison evidence is unavailable. It does not promise the old grouping outside T survives. The earlier pure synthetic counterexample used eight chronological inputs without embeddings and target 2:

```text
before: {a,b,c,d} | {e,f,g,h}
T={a,b} separately: {a} | {b}
remaining with unchanged target 2: {c,d,e} | {f,g,h}
```

This demonstrates a possible dependency effect, not a requirement to regroup everything and not a claim about every threshold-based method. When inputs and real dependencies remain unchanged, valid output should be reused. Actual memberships and basis remain inspectable through existing Read relationships.

Base source associations and Geo acquisition units are not redefined by final compression partitions. A local compression request is not permission for new remote/model/Geo effects. Existing exact effect authorization still applies if a real dependency requires new external acquisition.

## 3. Readback without a Profile entity

`review include=["preparation"]` returns a `preparation` value containing a Source Set for all the current Result's accounted inputs and the complete reusable Profile. For a historical Result without sealed preparation data, it returns `null` and the `processing_profile_unrecorded` qualification. It does not read the original Run database or current Dataset configuration to invent historical settings.

The readback rebinds each override to `{"kind":"profile_scope","index":i}` in the current Result. This Source Set selects the exact frozen members of override position i. It is resolved from sealed membership, not by recursively interpreting the readback selector or rerunning compression. It has no independent identity, lifecycle, read API or management operation. Unknown positions and Results without preparation data yield `invalid_source_set`.

This one selector is necessary for bounded readback: T may contain tens of thousands of sources, and its new groups need not have the same boundaries as the old ones. Returning all new Source Item references just to copy a Profile would make an otherwise small request unreasonably large. Exact members remain available through ordinary paginated resolve.

The compact canonical `{source_set, profile}` request portion is limited to 262144 UTF-8 bytes. The normalized preparation readback uses short scope selectors and must fit the existing 524288-byte response envelope by itself. Optional audit data and Evidence pages keep their existing separate limits and explicit oversized-response errors; no truncation or partial configuration value is allowed.

Run snapshots keep original input binding and resolved scope membership for recovery. Result sealing records the public Profile, normalized preparation value and scope membership inside the existing Result lifecycle. Internal tables/JSON layout are replaceable. These records are retained Result data, not evictable producer cache.

## 4. Source correspondence and Plan continuity

`resolve` accepts optional `target_result_ref`. Both Results must be visible in the same Dataset. Source membership/digests still describe the request's original Result. Every returned original member additionally gets `correspondence`; the resolution echoes the exact target Result. Cursor binding includes both immutable Result digests, source expression, limit and position.

First delivery proves only a direct successor created from the explicit original input snapshot. The target seals, for each input occurrence, its original Result and Source Item reference, source-root binding, verification outcome and new Result-local reference. A matched row requires a unique recorded input binding and unchanged observed revision under the stated verification profile. Root/locator checks and verification support that declared input binding; paths or equal digests alone never create one. Two identical files and two names for one inode remain separate accounted occurrences.

The proposed correspondence value has two shapes. A matched value supplies `status=matched`, `source_item_ref`, `basis.code=recorded_input_binding`, `basis.verification_profile`, and any necessary qualifications. An unproven value supplies `status=unproven` and `basis.code`, with no target reference. Its reason is one of `input_binding_unrecorded`, `not_direct_successor`, `verification_unavailable`, or `verification_not_supported`.

`matched` does not claim unchanged observations, unchanged representative relationships or cryptographic byte equality when the underlying proof only detects ordinary changes. It carries the actual verification profile and required qualifications. Independent Runs, historical missing lineage, unsupported verification or an unavailable proof never become guessed matches. Corrupt/contradictory sealed bindings fail Result integrity validation rather than returning convenient unproven rows. Unknown/out-of-Result references retain `reference_not_in_result`; valid expressions with illegal membership/overlap return `invalid_source_set`.

Known source revision changes during the same-snapshot Run fail it with `source_snapshot_changed`; no silent acceptance of new bytes. A disconnected source attachment is a known recoverable prerequisite, not evidence of deletion. Auxiliary/excluded/error records stay accounted, and their verification limits remain explicit. The first implementation does not guarantee automatic reconciliation of source edits, relocation or missing history.

Plan uses existing operations:

```text
inspect old Work: preferences, notes, organization
    ↓ resolve old Source Sets toward new Result
create new Work bound to new Result
    ↓ inspect new covering Evidence and material changes
update preserved notes/preferences and justified organization
    ↓ current Plan review/confirmation flow
seal only the new exact reviewed organization
```

Do not rebind an existing Work, copy Result-local references, transfer Human confirmation, or claim evidence equivalence from source correspondence. New Evidence is discovered via existing expand/review. The current Plan Work contract owns organization field names and draft/candidate behavior; this package does not fork that concurrent design.

## 5. Internal ports and implementation order

These are proposed process-local responsibilities for implementation, not already-written functions, public Tools or durable entities:

| Owner | Required input/output |
| --- | --- |
| Run validation | validated request + current configuration + trusted prior Result → frozen effective Profile, exact input/source bindings, disjoint scope memberships |
| configuration projection | resolved configuration + producer recipe declarations → canonical preparation value and identity; no I/O or private state lookup |
| demand construction | frozen input records/Profile + available valid outputs → producer demands by source and actual semantic dependencies |
| compression composition | prepared source-aware inputs + resolved partition parameters → groups, representatives, exact members, basis and limitations |
| Result sealing | completed preparation + scope/input bindings → independently readable immutable Result; no mutable Work dependency for Read |
| Read projection | one or two trusted Results + selector/page → preparation, exact members or justified correspondence; no preparation or source-file acquisition |

Reuse identities remain capability-local. Changing Run ID, the whole Profile hash or one unrelated override must not invalidate every Work. Model, source revision, decoder/recipe or true input changes invalidate their dependants. Disabled capabilities are not delivered just because cached output exists. The producer layer owns validity; Run composes demands and accounts for outcomes.

Implementation proceeds through shared value/validation ports, producer demand/reuse, orchestration/publication, Read projection/Plan guidance, then Host and installed-artifact acceptance. `tasks.md` assigns concrete file boundaries and pass gates. A single implementation owner must integrate shared port changes before dependent tracks proceed; this design phase starts no Agents or implementation tasks.

## 6. Failure, replay and retention

- Check an existing request_id binding before resolving mutable defaults. Exact canonical request replay returns the original Run; changed content conflicts even if it happens to select equal members. Resume always uses the frozen original snapshot.
- Invalid shapes, Source Sets, overlaps and configuration guards fail before worker/producer effects. Validate exact scope membership using trusted Result data, not source scanning.
- Current source availability/revision is checked by the worker under the existing source-validity mechanism. Known waits retain explicit recovery; unexpected implementation errors surface as failures.
- Valid outputs survive interruption. A restarted publication produces one Result identity; a new user request produces a new Run and Result. No special revision path exists.
- Result-owned material remains pinned or publication-owned using the existing artifact mechanism. Producer cache eviction cannot silently erase retained Result contents. No automatic Result deletion or cache purge is authorized.
- Read absence of historical preparation/lineage honestly. It must never reconstruct authority by searching private Run/Work databases.

## 7. Engineering risk decisions and stopping conditions

Resolved here: scope is explicit and same-collection; overlapping overrides reject; count fallback remains; other parameters are guarded; compact scope readback uses a value-position selector; correspondence is a qualified direct input-binding proof; Plan uses a new Work. No additional Human choice is currently required to implement these rules.

Stop for Human discussion if implementation evidence shows that the contracted path requires losing old Results, clearing reusable work, broadening effects beyond authorization, or substantially different source-scope/parameter behavior. Normal missing inputs and unproven correspondence follow the specified outcomes; they are not new business decisions for every item.

Performance acceptance separates expensive computation from source verification, indexing and sealing. A lightweight Run is not a promise of zero O(N) accounting or wall time. Exact mechanisms, test workloads and stop gates are fixed in [acceptance.md](acceptance.md); measurements must not be replaced by historical test claims.
