## 1. Baseline and private schema

- [x] 1.1 Add count-based characterization tests for metadata process starts, whole-Run association scans, source-byte proof reads, and effective lane concurrency without running large media.
- [x] 1.2 Add the derived Source association key and supporting `(run_id, association_key)` index to the replacement private PreCheck schema, reject incompatible workspaces, and add fresh-start/query tests without an upgrade path.
- [x] 1.3 Add paged accounting and Work enumeration APIs needed by batch planning without creating a second state store.

## 2. Ordinary-change source validity

- [x] 2.1 Replace unconditional producer-time full hashing with revision, bounded fingerprint, and pre/post file-identity validation for PreCheck Work dependencies.
- [x] 2.2 Change Result seal validation to honor each verification profile without upgrading limited observations to exact-byte claims.
- [x] 2.3 Make Apply preparation establish a fresh exact selected-source proof and effect execution recheck it when the Result has limited or no exact PreCheck observation.
- [x] 2.4 Add mutation, reuse, missing-source, and selected-effect regression tests for the revised verification boundary.

## 3. Batched ExifTool metadata

- [x] 3.1 Add a private long-lived ExifTool adapter with bounded command batches, version observation, cancellation, restart, and deterministic shutdown.
- [x] 3.2 Add multi-item metadata production that retains one Work spec, lease, output, failure, and invalidation boundary per subject.
- [x] 3.3 Isolate unattributed batch failures through bounded subdivision, renew active item leases throughout recursion, and prove successful sibling commitment, cancellation convergence, and immediate retryability after heartbeat renewal failure.
- [x] 3.4 Integrate metadata batches with resource admission and verify process-start and batch-count ceilings using a fake adapter plus a short real-ExifTool micro-test.

## 4. Cost-ordered evidence demand

- [x] 4.1 Define and version the index metadata profile used for all eligible source media without adding a new public capability.
- [x] 4.2 Reorder orchestration to build bundle candidates after index metadata and before rendition, video, embedding, and sensitivity demand.
- [x] 4.3 Derive the bounded initial evidence set from representatives, distinct boundaries, explicit exceptions, and internal directed rebuild requests.
- [x] 4.4 Preserve Result accounting/navigation for unrendered members and document that directed additions have no public request contract yet.
- [x] 4.5 Add a Result regression where a successful compression frontier
  represents included members that have no direct visual Artifact, and prove
  those members become usable while relationship limitations remain visible.
- [x] 4.6 Keep genuinely unrepresented included Source Items unresolved and
  blocking, then exercise the corrected projection through the default
  production RuntimeHost path.

## 5. Resource resolution and pipelining

- [x] 5.1 Resolve host-aware CPU, memory, source/workspace I/O, process, codec, and model ceilings into the existing persisted Run configuration.
- [x] 5.2 Admit independent post-grouping producer Work through bounded resource lanes without whole-stage task materialization.
- [x] 5.3 Bound FFmpeg process count and internal threads, and add true batch interfaces for compatible local-model adapters.
- [x] 5.4 Add deterministic override, resume, cancellation, Darwin memory, storage-evidence, and unknown-storage fallback tests.

## 6. Scale-critical algorithms

- [x] 6.1 Remove whole-Run per-item rescans from metadata and bundling, including direct representative lookup for each component.
- [x] 6.2 Replace unbounded all-pairs embedding representative selection with an exact small-group path and bounded large-group method that records its limitations.
- [x] 6.3 Stream or page Source Items, Work demand, and non-authoritative outcomes so peak coordination memory is controlled by batch and pending-window limits; distinguish unavoidable final Result O(N).
- [x] 6.4 Add production-path generated scale tests whose populated Source Items and index metadata match the stated item count, plus memory, cancellation, and incremental-reuse evidence.

## 7. Acceptance and migration evidence

- [x] 7.1 Compare affected AI Album behaviors and classify metadata, video, cache, recovery, and resource differences as preserved, intentionally changed, regression, or not comparable.
- [x] 7.2 Run focused unit/integration tests, the full default non-live suite, Ruff, and strict OpenSpec validation without fixture mutation, fresh models, or network access.
  - Post-regression acceptance reports 46 focused tests passed, 583 default
    non-live tests passed with 16 deselected, and 10 explicit generated scale
    tests passed with 589 deselected. Full Ruff, changed-file format, all 18
    strict OpenSpec items, isolated wheel/MCP smoke, documentation contract,
    and diff whitespace gates passed without fixture execution or mutation.
- [x] 7.3 Update authoritative design and migration documentation with measured evidence, necessary versus avoidable O(N), internal-only directed evidence, remaining physical-storage/model gates, and the zero-BC fresh-start policy.
