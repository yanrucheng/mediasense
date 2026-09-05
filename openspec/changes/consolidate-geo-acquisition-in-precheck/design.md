# Design: Consolidate Geo Acquisition in PreCheck

## Context

MediaSense currently has two paths from coordinates to provider observations.
PreCheck owns a frozen, deduplicated post-compression reverse-geocode batch, but
its product `offline` mode lets the Run publish without that evidence. Plan then
offers `enrich_geo`, validates Result coordinates, calls the public
`mediasense.geo.query` Tool, and stores a revision-bound observation. In the
reported 0.7.1 flow this divided ownership made Plan attempt authorization before
the runtime could report the more fundamental fact that no provider existed.

The current contracts are not production contracts and explicitly use Zero BC.
Old immutable Results remain historical bytes; they are never rewritten. Source
media remains read-only. Existing local PreCheck Work may be reused by a successor
Run, but private databases are not read or patched as a product migration API.

This design applies `$yanru-guidelines` directly:

- **Anchor purpose and home:** PreCheck's stable purpose includes acquiring
  reusable source-derived Geo evidence and publishing it in the immutable Result.
  Plan's stable purpose is interpretation and Human interaction over that Result.
- **Leave methods open:** exact provider, normalization library, routing heuristic,
  batching, Work layout, and summary implementation remain replaceable. The
  contract fixes only frozen scope, authorization, outcome distinctions,
  provenance, accounting, and immutable handoff semantics.
- **Independent-identity test:** Plan Geo disappears without losing an independent
  responsibility; PreCheck already owns the subject selection, acquisition
  lifecycle, and authoritative persistence. Product `offline` likewise has no
  independent purpose: it conflates a default effect policy with runtime
  capability. A public Geo Tool has no remaining real caller after Plan Geo is
  removed. The provider-neutral values/adapters/routing kernel does retain an
  independent implementation responsibility because PreCheck must replace
  providers without changing Result semantics.
- **Capability-growth test:** a stronger Plan Agent can ask better semantic
  questions or use better Result views without reconstructing provider
  acquisition, while a stronger PreCheck implementation can change coordinate
  selection and routing methods without creating a second stage lifecycle.

## Goals / Non-Goals

### Goals

- Make one PreCheck Run own local coordinate extraction, exact deduplication,
  provider availability, trusted authorization, provider execution, accounting,
  immutable Geo Evidence, and publication gating.
- Keep zero provider requests before authorization and prove it with provider and
  transport spies.
- Distinguish `provider_unavailable`, `authorization_required`,
  `authorization_declined`, `no_result`, localized failure, and unexpected
  implementation failure.
- Give Plan one bounded deterministic Geo summary without expanding all Evidence
  Cards and reject old or malformed Results whose acquisition is incomplete.
- Remove Plan Geo, the public Geo Tool, and Geo-only durable state completely.

### Non-Goals

- No Geo preflight Tool, Geo Skill, Geo Artifact type, place-cluster entity,
  provider registry, service process, or compatibility adapter.
- No event inference, place truth, semantic grouping, directory naming, or Human
  preference inside PreCheck or PreCheck Read.
- No mutation of old Result packages or versioned external fixtures.
- No automatic fallback from an unavailable provider to an unauthorized provider,
  and no global switch that silently changes effect policy.

## Decisions

### 1. PreCheck publication is the only Geo acquisition lifecycle

After compression, PreCheck derives one ordered coordinate batch using the same
precedence as acquisition: an available GPX coordinate supersedes embedded GPS for
the same Source Item; multiple identical normalized `(latitude, longitude, datum)`
triples become one logical query while retaining every Result-local Source Item
member. No rounding is part of the deduplication contract.

An empty batch records Geo as `not_applicable` and may publish. A non-empty batch
must reach one of these boundaries:

| Condition | Run consequence | Result consequence |
| --- | --- | --- |
| no compatible configured provider | terminal `failed` with `provider_unavailable` | none |
| provider exists, trusted authority absent | `paused` with `authorization_required` | none |
| Human declines | terminal `cancelled` with `authorization_declined` | none |
| authority matches frozen batch and disclosure | execute only authorized batch | publish after closure |
| provider no-result | successful attempted observation, explicitly `no_result` | immutable candidate Evidence |
| localized coordinate failure | completed attempted Work plus qualification | immutable partial/failure Evidence |
| unexpected exception/invariant violation | propagated to worker failure | none |

`blocked` is not used for absent providers or unknown exceptions because neither
has a real automatic wake-up mechanism. The Human can start a successor Run after
provider configuration changes.

Alternative rejected: publish a locally complete partial Result. It repeats the
0.7.1 defect by turning an internal stage boundary into a successful handoff.

### 2. Authorization binds the frozen batch and full disclosure

The existing Run confirmation checkpoint remains the one attention boundary, but
its external-effect confirmation becomes non-optional and content-addressed. The
confirmation content includes:

- every exact normalized coordinate and the batch fingerprint;
- operation and transmitted data classes;
- configured provider identities and maximum provider-request ceiling;
- known cost ceiling or explicit `unknown`;
- each provider's declared data-handling policy or explicit `unknown`; and
- fixed Result retention for accepted observations.

`resume` with `proceed` requires transport-only trusted Human confirmation whose
`confirmed_content_identity` equals this content identity. The authority is stored
with the Run decision and copied into completed Work provenance. A plain request
field, an old decision, credentials, or a changed batch is insufficient. `decline`
needs no effect authority and terminates the Run. Because the MCP resume request
contains only the Run reference, decision, and trusted content identity, exact
coordinates do not enter a separate public effectful Provider Tool call.

Unknown provider policy is not encoded as `none`: it appears as `unknown` inside
the exact content the Human accepts. Accepted candidate observations always belong
to the immutable Result; callers do not choose `caller_state` or `none` retention.

Alternative rejected: reuse the public Geo Tool preflight. It would retain the
second public lifecycle and reintroduce approval ordering before PreCheck owns the
batch.

### 3. Keep only the Geo kernel PreCheck invokes

Provider-neutral coordinate/result values, provider protocols, AMap and Google
adapters, datum conversion, normalization, bounded routing/fallback, request
accounting, and the PreCheck effect guard remain ordinary internal modules.
`GeoQueryTool`, `GeoOperationJournal`, Plan-specific adapters, public operation
models that have no PreCheck caller, and the Dataset Geo store are deleted.

Runtime composition constructs providers only from configured credentials and
injects the resulting batch engine into PreCheck. Credential presence is a fact,
not authorization. With no configured provider, the engine is absent and
PreCheck reports `provider_unavailable` before requesting Human authorization.

Alternative rejected: retain the Tool or journal for hypothetical reuse. It fails
the independent-identity test and creates long-term authority and retention
semantics with no caller.

### 4. Geo candidate observations become ordinary Result Evidence

Each completed unique coordinate Work projects one ordinary inline
`ResultEvidence` with a stable Result-local Evidence reference. Existing
`represents` relations bind it to every member Source Item. Provider address/POI
values remain candidate observations with attempt provenance and qualifications;
they are not entry Evidence, place clusters, events, grouping recommendations, or
truth claims.

The Result execution boundary continues to reconcile logical queries, actual
provider requests, provider identities, billable units or `unknown`, and network
access. Publication remains impossible until Result integrity and all existing
accounting gates pass.

Alternative rejected: a Geo Artifact or dedicated place-cluster model. Neither
owns an independent read/retention lifecycle; the existing Result and Evidence
structures carry the meaning without divided authority.

### 5. PreCheck Read adds a deterministic `geo_summary` operation

`mediasense.precheck.read` gains a paged `geo_summary` operation. It derives its
entire response from the verified immutable Result and reports:

- GPS and GPX observation-state counts plus combined available, missing, failed,
  and conflicting Source Item counts;
- exact normalized-coordinate deduplication rule and unique-coordinate count;
- per coordinate: member count, explicit Result-bound Source Set, acquisition
  outcome, candidate Evidence refs, provenance, and qualifications; and
- overall acquisition status: `not_applicable`, `complete`, or `incomplete`.

The projection performs no I/O beyond ordinary Result verification, no provider
request, and no semantic inference. Pagination order is canonical coordinate key.
Tests compare the projection with exhaustive Result traversal.

Alternative rejected: add a Geo summary Tool or retained summary Artifact. Both
duplicate the Result authority and lifecycle.

### 6. Plan has no Geo effect or retention state

`PlanWorkTool` accepts only `create`, `update`, `inspect`, and `seal`. `create`
reads the Result's deterministic Geo summary and rejects `incomplete` acquisition
even if an old Result says `plan_ready`. Plan Working State removes Geo
observations, `geo_evidence` sections, authorization fields, preview rendering,
fixtures, and tests.

When machine evidence is insufficient, the Agent may ask the Human for a semantic
decision and record that answer as Human context/judgment, or stop and require a
successor PreCheck. It never labels Human input as provider or PreCheck evidence.

Existing Plan Working databases are not interpreted or migrated. Runtime uses the
new clean private schema; an old no-Candidate Work is abandoned and recreated from
the new Result.

### 7. Remove product `offline`; report actual runtime facts

Runtime and Dataset configuration expose provider credential configuration,
provider capability availability, and policy disclosure facts. They expose no
`offline` mode or CLI flag. Provider calls remain impossible until the exact Run
authorization gate opens, regardless of credentials.

For existing 0.7.1 Dataset workspaces, a one-way public manifest migration removes
the Geo store declaration while preserving PreCheck directories and immutable
Result files. It does not read or rewrite private PreCheck/Plan databases. A fresh
Plan private store is used; old Geo journal bytes, if physically present, remain
unreferenced historical residue and are never read. New workspaces do not create
a Geo store.

Alternative rejected: keep `offline` as a test-only product field. Tests inject
providers or spies directly; product semantics do not need a global mode.

## Risks / Trade-offs

- **[A Dataset with coordinates cannot become Plan-ready without a provider and
  authorization]** → This is the intended honest boundary. Status names the
  missing provider before asking for authorization, and successor Runs reuse valid
  local Work.
- **[A one-way Dataset manifest migration changes mutable workspace metadata]** →
  Migrate only the public manifest atomically, never Result bytes or private DBs;
  verify source identity and supported old shape first.
- **[Provider policy may be unknown]** → Keep `unknown` in the exact disclosure
  and require Human confirmation bound to it; never translate it to `none`.
- **[Geo summary could drift from exhaustive Result semantics]** → Share one
  canonical coordinate parser/precedence rule and test projection equivalence
  against complete Result traversal.
- **[Removing Plan Geo breaks current callers]** → Zero BC is explicit. Remove
  schemas, dispatch, Skill guidance, fixtures, and tests together so no false
  partial compatibility remains.
- **[Provider effects can be replayed after a crash between request and Work
  commit]** → Preserve per-coordinate Work boundaries and existing reuse;
  report indeterminate provider errors honestly. A new public journal/service is
  not justified by this change.

## Migration Plan

1. Validate this proposal, design, deltas, and tasks before implementation.
2. Add PreCheck authorization disclosure, provider-first availability handling,
   required publication gating, Result Evidence projection, and Geo summary.
3. Wire configured providers into PreCheck and remove `offline` from configuration,
   Dataset manifests, diagnostics, CLI presentation, and distribution tests.
4. Make Plan reject incomplete Geo Results, then delete Plan Geo state, adapter,
   contract branches, preview, Skill guidance, fixtures, and tests.
5. Remove Geo Tool dispatch/contract/journal/store and trim the internal kernel to
   actual PreCheck callers.
6. Synchronize formal contracts, packaged snapshots, active design docs, Skills,
   migration ledger, and indexes.
7. Run contract, unit, integration, real MCP subprocess/listing, network-spy,
   source-immutability, Honeycomb integration, and OpenSpec validation suites.

Rollback during development is a source revert before release. There is no runtime
dual path: once shipped, a successor PreCheck Result is required for Plan.

## Open Questions

None. Product ownership, Zero BC, provider-policy handling, and the absence of new
public entities are decided by this change.

