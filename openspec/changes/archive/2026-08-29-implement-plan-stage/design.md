## Context

MediaSense Plan sits between an immutable PreCheck Result and deterministic Apply. The active repository contracts already define `mediasense.precheck.read`, the four-action `mediasense.plan.work` Tool, Frozen Plan content and identity, the Default Organization Profile, and the two-component local artifact shape. They are authoritative; this OpenSpec change organizes their implementation and adds the accepted preview requirement.

The user review loop is now explicit:

```text
exact PreCheck Result
  -> Agent proposes one complete candidate
  -> Tool stores revision rN
  -> deterministic preview renders rN
  -> Human accepts or requests changes
  -> changed candidate becomes rN+1 and is previewed again
  -> trusted confirmation of the exact current identity permits seal
```

The repository is pre-production and uses Zero Backward Compatibility. Plan may be developed against the existing PreCheck Read Mock while upstream production evidence producers remain incomplete.

## Goals / Non-Goals

### Goals

- Implement the existing Plan Working State and Frozen Plan contracts without reopening their settled semantic boundaries.
- Make mutable drafts durable, safely retryable, concurrency-safe, and exactly inspectable.
- Give the Human a deterministic, scalable preview of the exact candidate that may be sealed.
- Publish one immutable Frozen Plan through an honest recoverable protocol.
- Teach an Agent to use evidence progressively, distinguish epistemic roles, revise from preview feedback, and seek exact confirmation.
- Leave reasoning, visual inspection strategy, model choice, HTML framework, SQL layout, and other replaceable methods open.

### Non-Goals

- Implementing Apply or mutating source media.
- Implementing PreCheck producers, caches, reverse geocoding, GPX matching, metadata extraction, thumbnails, embeddings, sensitivity detectors, or candidate clustering.
- Adding a fifth action to `mediasense.plan.work`.
- Treating preview as an authoritative or durable product artifact.
- Adding a Profile registry, manifest, latest pointer, per-Plan directory, copied PreCheck Result, or permanent revision history.
- Implementing a production identity provider, browser application, remote-model gateway, or model-response cache.
- Claiming production end-to-end readiness while required real PreCheck Evidence remains unavailable.

## Decisions

### 1. Preserve the existing authority map

| Responsibility or information | Owner and authoritative home |
| --- | --- |
| Source-derived facts and reusable Evidence | Exact immutable PreCheck Result |
| Interpretation, grouping, naming, and questions | Planning Agent |
| Reusable planning method and escalation criteria | `mediasense.plan` Skill |
| Human preferences and consequential semantic confirmation | Human, captured only through the defined Tool boundary |
| Mutable candidate, preferences, revisions, idempotency, lifecycle | `<plan-store>/work.sqlite3` |
| Final organization decision | Immutable `<plan-store>/frozen/<artifact-key>.json` |
| Preview | Regenerable view derived from an exact revision and PreCheck Result |

This prevents a cache, renderer, Skill, or Agent transcript from silently becoming product truth.

### 2. Use one small Plan package

The intended implementation shape is:

```text
src/mediasense/plan/
├── __init__.py
├── work.py
├── _sqlite.py
├── _candidate.py
├── preview.py
└── _publication.py
```

`work.py` is the public Tool handler/facade. `_sqlite.py` owns the private store and transactions. `_candidate.py` owns deterministic candidate materialization, Result-local expansion, validation, identity, and cursor semantics. `preview.py` exposes read-only rendering without becoming another authority. `_publication.py` owns only recoverable Frozen Plan file publication.

No repository/service/model layer is added. Small value types and errors remain with the module that owns their behavior until an independent responsibility justifies extraction.

### 3. Inject the PreCheck Read boundary

The Plan handler receives a callable adapter implementing the existing `mediasense.precheck.read` request/response contract. Tests use the published Hong Kong Mock. Production integration must provide the same contract and cannot expose PreCheck database objects or cache paths.

Alternative rejected: importing PreCheck implementation modules. That would couple Plan to unfinished upstream storage and violate Result authority.

### 4. Treat revision as an optimistic concurrency and review token

A revision is created only by a successful `create` or coherent `update`, not by conversation, preview generation, directory expansion, or tentative reasoning. Updates atomically replace the complete candidate and optionally the complete preference snapshot. The contract does not require retaining every historical candidate.

Alternative rejected: patch operations or conversational event sourcing. Both add ordering and replay semantics that the product does not need.

### 5. Share one candidate materialization path

Update validation, inspect pagination, preview counts, representative selection, content identity, and seal validation must derive from one logical candidate materialization path. Materialized `sealed_content` is first checked by a validator loaded directly from the authoritative `frozen-plan.schema.json`; hand-written code retains only Result-dependent and cross-record semantic proofs that JSON Schema cannot perform. Every paged or rendered projection remains bound to the same revision and global candidate identity.

Tests validate observable results against the active JSON contracts. Python internals do not become a second schema authority.

Pagination cursors carry their bound Work, revision, collection, limit, and continuation position in a canonical payload protected by HMAC-SHA256. One random signing key is stored in the existing Plan SQLite file and reused after restart. This adds no product entity or cursor registry, while any payload mutation becomes observable as `invalid_cursor`.

### 6. Keep preview separate from the four-action state Tool

Preview is a read-only callable capability over `work_ref + revision`. Its stable product meaning is the review information and exact binding, not HTML. The first reference implementation may use plain local HTML because it supports a hierarchy, counts, thumbnails, and drill-down, but the format is not fixed until the required Human reference review.

The renderer uses existing PreCheck representatives and renditions. Deterministic fallback selection may be used only among already available evidence and must expose missing samples. It never calls a model or map service and never changes candidate content.

Alternative rejected: persisting preview beside Frozen Plans. It is rebuildable and has no independent authority or lifecycle.

### 7. Bind confirmation to the previewed identity

Previewing revision `rN` does not lock the Work. A later update creates `rN+1` and makes the old preview stale for confirmation. Seal accepts only a trusted Human context bound to the current candidate identity; request fields cannot self-assert confirmation.

The implementation exposes an injected authentication/confirmation context and test double. A production identity system and UI remain outside this change.

### 8. Publish Frozen Plans with a recoverable intent

Seal serializes and verifies the exact Frozen Plan, writes a new temporary file, applies the implementation's durability policy, atomically renames without replacement, and then commits the SQLite close state. A reserved idempotent outcome allows retry to recover a verified artifact written before the database commit. Conflicting or missing artifacts are reported rather than reconstructed from a different candidate.

Alternative rejected: claiming a cross-filesystem transaction or writing SQLite first. Neither can provide the promised result.

### 9. Keep reverse geocoding upstream and optional

Plan performs no reverse geocoding. If a PreCheck Result contains qualified resolved-place observations, Plan may use them; otherwise it reasons from available coordinates/evidence or recommends a new upstream enrichment run. A future PreCheck change may add provider-aware, deduplicated, explicitly authorized enrichment while preserving the default offline profile.

This change does not add that upstream implementation or silently weaken the existing zero-egress PreCheck reference.

### 10. Build the Skill after deterministic boundaries exist

The Skill is added after Working State, preview, and seal behavior can be exercised through Mocks. It describes evidence selection, user interaction, cost visibility, revision checkpoints, confirmation, and reopen conditions. It does not contain database operations, hidden authority, or a fixed reasoning script.

## Risks / Trade-offs

- **Mock-backed success can be mistaken for production readiness** → Report Plan-layer completion separately and list unavailable upstream evidence producers in acceptance evidence.
- **Large previews can exhaust memory or browser capacity** → Render summaries first, page member drill-down, and cap loaded visual assets without changing counts or hiding omissions.
- **Local browsers may not load evidence paths consistently** → Keep resource resolution behind the preview boundary and use local, non-egressing delivery; report inaccessible renditions explicitly.
- **SQLite and JSON publication can diverge after interruption** → Reserve the outcome, verify artifacts on recovery, and never return success until both sides agree.
- **Duplicate validation logic can drift from the active Frozen Plan schema** → Use one materialization/validation path and contract-vector tests against the authoritative schema and Mock.
- **Model calls may repeat across Agent Sessions** → Persist accepted candidate decisions, observe actual cost, and avoid adding a model-result cache until evidence demonstrates an independent lifecycle.
- **Concurrent repository work can collide** → Develop from local commit `5813cef` or a descendant containing all active Plan contracts; do not base work on `origin/main` or modify PreCheck internals.
- **A presentation implementation may be mistaken for product contract** → Human-review one reference preview and specify only the information and binding that proved necessary.

## Migration Plan

There are no production consumers or persisted Plan stores to migrate.

1. Implement and verify `create` and `inspect` with a new local test database.
2. Add atomic `update`, revision conflict handling, preference replacement, idempotency, and paged inspection.
3. Add complete candidate materialization, validation, and identity.
4. Produce the first deterministic preview from the existing Mock and pause for Human review before fixing the presentation contract.
5. Implement trusted seal and recoverable Frozen Plan publication.
6. Add the Plan Skill, Mock-driven interaction evaluation, and AI Album migration judgment.

Rollback before production consists of stopping use of the new Plan package and preserving any generated test artifacts for diagnosis. No source media or upstream Result is changed. Published Frozen Plans are immutable evidence and must not be silently deleted or rewritten.

## Open Questions

- The durable preview semantics are fixed, but the first presentation format remains intentionally open until the Human reference-review checkpoint. Plain local HTML is the initial candidate, not a product constraint.
- Production adapters for Human authentication, browser presentation, remote semantic models, and incomplete PreCheck evidence producers are separate follow-on boundaries and do not block Mock-backed Plan implementation.
