## Why

PreCheck currently performs high-fixed-cost and repeated source work before it narrows the Dataset: metadata starts one ExifTool process per media item, every major media lane is effectively serial under fixed conservative capacities, unchanged source bytes are re-hashed across producers, and several coordination paths rescan whole-Run state. This makes a roughly 4,000-candidate local Run take tens of minutes and leaves the implementation structurally unable to approach the intended hundred-thousand- and million-item scale.

The product decisions are now explicit: PreCheck protects against ordinary source change rather than adversarial metadata-preserving byte tampering, and initial expensive visual evidence may be limited to representatives, boundary evidence, and explicit exceptions while every Source Item remains accounted. The execution architecture should realize those decisions without weakening source read-only behavior, item-local failure, durable recovery, cache validity, or Apply revalidation.

## What Changes

- Make low-cost Dataset accounting and index metadata precede representative selection, then demand detailed metadata, renditions, video evidence, embeddings, and sensitivity observations only for selected representatives, useful boundaries, and explicit exceptions.
- Replace per-item ExifTool startup with bounded batches executed through a small number of Run-local long-lived ExifTool lanes while retaining one semantic Work outcome per Source Item and isolating malformed inputs by bounded batch subdivision.
- **BREAKING**: treat revision/stat/fingerprint observations as sufficient for ordinary-change detection inside PreCheck instead of requiring every Apply-eligible Source Item to carry a PreCheck-produced full-byte proof; Apply establishes and rechecks exact bytes for the selected filesystem effects.
- Replace whole-Run per-item rescans and eager task materialization with indexed association lookup, paged demand enumeration, bounded queues, and algorithms whose supported scale path is no worse than `O(N log N)` outside explicitly bounded groups.
- Resolve resource capacities from host and source/workspace characteristics into a persisted Run configuration, while preserving local-only defaults, explicit ceilings, cancellation, and advanced overrides.
- Preserve existing Run, Work, Artifact, Result, Dataset, and resource-admission authorities. No new public Tool, Skill, registry, daemon, service, or parallel progress/cache authority is introduced.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `precheck-run-orchestration`: require cost-ordered demand reduction, bounded batch execution with item-local outcomes, scalable enumeration, and resolved resource capacities rather than fixed universal worker/slot defaults.
- `precheck-source-verification`: align PreCheck verification with ordinary source-change detection and reusable revision-bound observations while retaining exact byte verification at the Apply effect boundary.

## Impact

- PreCheck orchestration, metadata, source-validity, bundling, compression, resource-admission, Work/Artifact persistence, and runtime composition implementations.
- Fresh-start replacement of the private PreCheck SQLite schema plus updated execution and producer profiles; no old workspace or old Result compatibility layer.
- Focused and generated scale tests, real local ExifTool micro-tests, failure/cancellation/reuse tests, and migration-ledger updates.
- No Hong Kong fixture mutation, long real-media benchmark, fresh model execution, paid or network operation, source-media write, or direct Apply effect is part of this change.
