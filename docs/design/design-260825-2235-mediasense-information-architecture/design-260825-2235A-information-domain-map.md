---
id: "design-260825-2235A-information-domain-map"
title: "MediaSense Information Domain Map"
type: design
status: active
created: 2026-08-25
updated: 2026-08-25
timezone: "Asia/Shanghai"
parent: "design-260825-2235-mediasense-information-architecture"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "eval-260823-1918D-ai-album-stored-information"
superseded-by: ""
tags: ["mediasense", "information-architecture", "domain-model", "migration"]
---

# MediaSense Information Domain Map

## Purpose and boundary

This map answers:

> What new, stage-neutral business information must MediaSense understand to turn a large source collection into sufficient evidence, an effective organization decision, and a verified execution result?

The map exists so that later stage ownership, handoff examples, storage lifecycle, and contracts can share one stable meaning without inheriting AI Album's implementation structure. It distinguishes what the source is, what was observed, what remains a candidate, what the user ultimately intends, and what execution actually did.

MediaSense is a fresh product. AI Album is evidence of useful capabilities, failure modes, costs, and missing information. It is not the authority for MediaSense terminology, data shape, stage ownership, or runtime dependencies.

### Non-goals

This document does not:

- assign formal ownership to `mediasense.precheck`, `mediasense.plan`, or `mediasense.apply`;
- define a database, file layout, serialization schema, or cache key;
- require a thumbnail size, embedding model, vector dimension, detector, clustering algorithm, or VLM provider;
- prescribe how an Agent and a user reach an organization decision;
- freeze a Diagnostic Package contract before a Plan reference handoff exists;
- adopt historical counts, names, groups, or output directories as semantic truth.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC level | None — Zero Backward Compatibility |

No production consumer depends on a MediaSense format. Legacy-cache readers, adapters, dual writes, deprecated fields, old filename patterns, and compatibility with AI Album cache flags are prohibited. Current design formats may change directly after human review.

## Governing business relations

```text
source media reality
  -> bounded source state and complete accounting
  -> observations and derived evidence
  -> challengeable candidate relations
  -> coverage-constrained evidence compression
  -> open Agent/user interpretation and decision
  -> frozen organization intent
  -> deterministic execution and verification
```

These relations generate the information map because each arrow changes either authority or information density:

- A source object is not the same thing as an observation about it.
- An observation or method output is not the same thing as semantic truth.
- A candidate relation is not a confirmed organization decision.
- Compressed evidence is trustworthy only while its coverage and expansion path remain visible.
- An Agent judgment is not user authorization.
- A frozen plan describes intended effects; it does not prove actual effects.
- A receipt records actual execution and must not rewrite the plan to match reality.

This chain covers MediaSense's primary purpose. Diagnostic support is secondary: it may preserve context for investigating a poor decision, but it neither changes the decision nor participates in execution.

## Fresh MediaSense domain concepts

The sections below define business concepts, not storage entities. A concept becomes an independent artifact only when later work proves that it owns a distinct authority or lifecycle.

### Source and scope

| Concept | Business meaning and purpose | Authority and indispensable semantics | Loss consequence and relations |
| --- | --- | --- | --- |
| Collection | The continuing media-organization subject across source observations, plans, and executions. It is not a directory path. | Stable identity and human-recognizable subject. Current paths, evidence, and organization intent are referenced rather than copied into it. | Without it, successive source states and outcomes cannot be understood as work on the same collection. It relates to Source States, Frozen Plans, and execution history. |
| Source State | A bounded claim about the source media observed at a particular time. | Source boundaries, observation time, identity evidence and its strength, known limits, and complete or explicitly partial coverage. Original media remains the factual source. | Without it, evidence and plans cannot be tied to a particular source reality or invalidated after change. |
| Source Item | One discovered object within a Source State. Media, sidecars, GPX inputs, unsupported objects, and other discovered entries use one identity model with different roles and dispositions. | Snapshot-local identity, observed location, physical facts, media/type observations, support/readability state, and source-media, auxiliary, or other role. | Without one identity, observations, relations, coverage, and plan dispositions cannot refer to the same object reliably. |
| Scope Discovery | The factual record of what was found within a declared discovery boundary. | Discovery source, observed entry, traversal result, and error or unavailable state. It does not itself decide inclusion. | Without it, exclusions and omissions cannot be distinguished from undiscovered content. It supplies Scope Decisions and Accounting Closure. |
| Scope Decision | The explicit decision to include, exclude, defer, or use a discovered item as auxiliary input. | Decision, reason, applicable rule or confirmation, and the Source State to which it applies. It remains distinct from discovery facts. | Without it, files disappear from processing without an accountable reason. |
| Accounting Closure | The claim that every discovered item has a disposition and that counts and unresolved items reconcile within the stated boundary. | Included, auxiliary, excluded, unsupported, invalid, error, and unresolved populations, with honest partiality. | Without it, completeness cannot be checked and later coverage claims have no reliable denominator. |

Scope Discovery, Scope Decision, and Accounting Closure are statement types over Source State and Source Items, not three required databases or file types.

### Evidence and compression

| Concept | Business meaning and purpose | Authority and indispensable semantics | Loss consequence and relations |
| --- | --- | --- | --- |
| Observation | A source-derived or locally measured statement about a Source Item, such as a time candidate, coordinate, duration, orientation, decodability result, or content-sensitivity signal. | Subject, observation kind, raw and normalized values where relevant, candidates, producer, field-level provenance, confidence or quality, and explicit completion/error/omission state. It is evidence, not corrected world truth. | Without it, planning must rescan source media or trust flattened values whose origin and failures are unknowable. |
| Derived Evidence | A reviewable or machine-usable result derived from Source Items or other evidence. | Input references, processing profile, derivation provenance, integrity, quality, completion, validity dependencies, and regeneration conditions. | Without it, expensive local work cannot be reused or challenged. It may support Candidate Relations and Coverage Relationships. |
| Candidate Relation | A challengeable claim that Source Items or Evidence may belong together or differ materially. | Endpoints or members, relation type, supporting evidence, score or basis, span or boundary, alternatives, conflicts, profile, and state. | Without it, a final group is opaque and over-merge or under-merge errors cannot be localized. |
| Coverage Relationship | A claim that selected Evidence represents, bounds, conflicts with, or exposes a wider set of Source Items or Candidate Relations. | Covered set, evidence role, basis, extent or weight, quality, known exclusions, and expansion links. | Without it, evidence compression becomes untraceable sampling and cannot support economical downstream reasoning. |
| Evidence Sufficiency | A bounded judgment about whether available evidence and coverage can support a stated downstream purpose. | Purpose, current coverage, residual uncertainty, blocking gaps, and reasons for sufficiency or insufficiency. | Without it, complete accounting can be mistaken for adequate evidence. It produces Reopen Signals when material gaps remain. |
| Reopen Signal | An explicit reason to acquire or recompute evidence rather than treating ordinary downstream exploration as a substitute for missing preparation. | Trigger, affected scope, missing or misleading evidence, and expected corrective action. | Without it, systematic upstream defects become repeated downstream work. |

A downstream consumer may derive any useful review or access view from Coverage Relationships. Such a view is regenerable, owns no evidence, and does not prescribe what an Agent must read.

#### Stable capability versus method artifacts

Stable requirements are the ability to express evidence inputs, provenance, profiles, quality, status, validity, regeneration, coverage, and the relation to representative, boundary, outlier, and conflict roles.

Method-dependent artifacts exist only when a selected method uses them. Examples include a particular rendition, sampled frame, embedding, vector dimension, distance metric, vector index, local detector result, or clustering intermediate. They may be saved and reused, but their concrete form is not a permanent MediaSense concept.

#### Content-sensitivity evidence

Local content-sensitivity observations are a preserved evidence capability. A result may record that probing was not requested; capability does not imply mandatory invocation in every profile. When a detector runs, its output must retain the subject, producer, effective profile, model or detector identity, thresholds, label or score, quality, per-detector completion/error state, validity dependencies, and regeneration conditions.

The signal is not content truth, user authorization, a routing command, or a Frozen Plan conclusion. The exact detector, model, taxonomy, threshold, and output format remain replaceable.

### Interpretation and organization intent

| Concept | Business meaning and purpose | Authority and indispensable semantics | Loss consequence and relations |
| --- | --- | --- | --- |
| Semantic Claim | A proposition made by a model, Agent, or person about the meaning of media, such as an event, place, subject, or suggested name. | Producer and epistemic status must remain distinguishable from source evidence when the claim is retained. It is not automatically a required durable record. | Conflating it with Observation turns guesses into facts. It may inform Agent Judgment or appear in diagnostic material. |
| Agent Judgment | An Agent's interpretation or decision during planning. | Distinct from facts and user confirmation. MediaSense does not prescribe the reasoning sequence or require private reasoning to be stored. | Conflation with user authority can make an unapproved choice executable. |
| User Confirmation | A user's acceptance, rejection, change, constraint, or authorization. | The confirmation needed to validate a final plan must be attributable to the exact decision scope. Full conversation history is not required by this map. | Without relevant confirmation, semantic intent and authorization cannot be distinguished. |
| Organization Intent | The evolving desired grouping, naming, ordering, and disposition of source items. | User purpose and accepted decisions remain distinct from evidence and method. Its working representation is open. | Without it, a plan becomes a mechanical output rather than an expression of user intent. |
| Frozen Organization Plan | The complete, versioned, human-reviewed, immutable execution form of Organization Intent. | Compatible source/evidence references, complete disposition of in-scope items, intended organization and operations, handled conflicts, verifiable freeze and authorization. | Without it, execution must make new semantic decisions or act on incomplete intent. |

Planning is intentionally method-open. An Agent may inspect different evidence, use different models, ask different questions, or write the result through a Tool or a defined format. The stable primary outcome is the Frozen Organization Plan, not a prescribed deliberation transcript.

### Execution and verification

| Concept | Business meaning and purpose | Authority and indispensable semantics | Loss consequence and relations |
| --- | --- | --- | --- |
| Execution Outcome | The actual result of attempting one planned operation. | Planned-operation reference, attempted/completed/refused/failed state, actual source and target facts, error, and restart or idempotency information. | Without it, a partial execution can look complete and cannot be resumed safely. |
| Verification Evidence | Observed postconditions used to compare actual state with the Frozen Plan. | Observation method, checked objects, expected versus observed facts, and unresolved discrepancies. | Without it, successful return codes can be mistaken for correct filesystem state. |
| Apply Receipt | The sealed account of all planned operations, outcomes, verification, and residual discrepancies. | Exact Frozen Plan reference, complete per-operation accounting, result integrity, and no retrospective rewriting of plan intent. | Without it, users cannot know what actually changed or distinguish execution failure from planning error. |

### Cross-cutting information semantics

These meanings attach to the information they qualify; they are not general-purpose containers.

- **Processing Profile:** the effective, reusable description of method choices needed to interpret or invalidate a result. Global mutable configuration files are not authoritative substitutes.
- **Derivation Provenance:** the inputs, producer, profile, software/model identity, time, and dependencies that produced an observation or artifact.
- **Epistemic State:** fact, candidate, judgment, confirmation, audit fact, or working state.
- **Availability State:** complete, partial, error, unavailable, omitted, or not requested. An empty value or missing artifact must not carry all of these meanings.
- **Confidence and Quality:** evidence strength appropriate to the producer; absence of a universal score does not justify fabricating one.
- **Resource and External-effect Facts:** local compute, I/O, storage and time; remote requests, data egress, tokens, fees, authorization, provider locality, and fallback where applicable.
- **Lifecycle Role:** mutable working state, reusable artifact, immutable sealed result, or regenerable derived view.

For a PreCheck projection, an interrupted Working Run is not a sealed result. A sealed result separately expresses complete or explicitly partial coverage, plan-ready or blocked readiness, and valid or invalid integrity. Partial does not automatically mean blocked, and complete does not automatically mean plan-ready. A new run produces a new sealed result rather than modifying an old one.

A future PreCheck projection may claim `plan-ready` only when it can show, within the stated MediaSense control boundary, zero media upload, zero metadata, coordinate, or feature-artifact egress, zero remote-model and online-map calls, and zero billable requests. It must distinguish an offline configuration claim, enforced network policy, observed zero-request audit evidence, and external processes outside the proof boundary.

### Diagnostic responsibility

MediaSense has a secondary responsibility to preserve enough externally observable context to investigate a poor organization result and improve future planning. It is independent from the primary Frozen Plan authority and must not participate in execution, override the plan, or require preservation of private Agent reasoning.

The existence of this responsibility is accepted; a formal Diagnostic Package entity and contract are deferred until a Plan reference handoff can decide generation policy, authorization, sensitive contents, secret exclusion, redaction, retention, completeness states, binding, and failure reporting.

## Historical evidence traceability

The following identifiers are historical evaluation references only.

| Historical evidence | MediaSense business disposition | Migration boundary |
| --- | --- | --- |
| `AA-STORED-IDENT-001` | Supports Source State and Source Item identity evidence, Derivation Provenance, and validity. | The old namespace, partial-hash key, filename pattern, and relocation behavior do not migrate. |
| `AA-STORED-CACHE-001` | Supports field-level Observations for time, camera, photo, lens, coordinates, and geographic candidates. The embedded path becomes a Source Item reference. | The flat YAML and provenance-free final values do not migrate. |
| `AA-STORED-CACHE-002` | Supports Derived Evidence in a lower-cost visual profile. | The historical dimensions, JPEG choice, and cache filename do not become contract. |
| `AA-STORED-CACHE-003` | Supports Derived Evidence in a higher-detail visual profile. | It is not a separate permanent entity, and the historical `1080p` behavior is not standardized. |
| `AA-STORED-CACHE-004` | Supports reusable method artifacts and comparative evidence used to propose Candidate Relations. | ChineseCLIP, float32 `(1024,)`, cosine distance, and the array format remain replaceable. |
| `AA-STORED-CACHE-005` | Supports local content-sensitivity Observations with per-detector provenance, quality, and state. | The capability is preserved; NudeNet/NSFW models, labels, thresholds, and direct routing behavior are not. |
| `AA-STORED-CACHE-006` | Supports the distinction between a Semantic Claim and source evidence, and may inform future diagnostic material. | Captions are not required PreCheck evidence or a mandatory planning intermediate. |
| `AA-STORED-CACHE-007` | Supports Semantic Claims and evolving Organization Intent. | A generated title does not own final naming authority; only an accepted Frozen Plan does. |
| `AA-STORED-CACHE-008` | Local coordinate and geographic candidates support Observations; model-inferred place text supports Semantic Claims. | The historical VLM/caption routing and empty-result semantics do not migrate. |
| `AA-STORED-CACHE-009` | Supports optional semantic transformation or a derived language view. | Translation is not an independent durable product entity; no artifact was observed in the historical run. |
| `AA-STORED-CACHE-010` | Supports video-derived visual Evidence. | The interval, cap, frame resolution, wildcard filenames, and incomplete-set behavior do not migrate. |
| `AA-STORED-CACHE-011` | Supports reusable method artifacts and comparative evidence over video frames. | The embedding model, vector shape, and wildcard completion semantics remain replaceable. |
| `AA-STORED-OUTPUT-001` | Supports the necessary separation among Frozen Organization Plan, Execution Outcome, Verification Evidence, and Derived View. | The historical directory tree, counts, and names are evaluation evidence, not a plan or receipt. |
| `AA-STORED-AUDIT-001` | Supports Resource and External-effect Facts and the secondary diagnostic responsibility. | The optional JSON log, static prices, excerpts, and incomplete attribution do not migrate. |
| `AA-STORED-CONFIG-001` | Supports Processing Profiles and Derivation Provenance. | Per-user mutable configuration files do not become authoritative run records or product entities. |
| `AA-STORED-FIXTURE-001` | Supports Source State, Source Items, Accounting Closure, Evidence derivation, and historical traceability. | The package JSONL schema, proxy transforms, and sampled source hash are evaluation mechanisms. |
| `AA-STORED-FIXTURE-002` | Supports Candidate Relations, candidate groups, representative roles, and Coverage Relationships. | The historical bundle index and grouping rules are not MediaSense identities or truth labels. |
| `AA-STORED-FIXTURE-003` | Provides evaluation-only integrity, replay, and provenance evidence. | The package audit set does not enter the product information model. |

### Important historical gaps

| Historical gap | New business destination |
| --- | --- |
| Complete scan, ignore decisions, unsupported/skipped paths, and validation outcomes | Scope Discovery, Scope Decision, Source Items, and Accounting Closure |
| Strong source identity and cache-wide manifest | Source State identity evidence and sealed-result integrity; exact mechanism remains deferred |
| Same-stem/sidecar and temporal edges, membership, weights, spans, and representative rationale | Candidate Relations and Coverage Relationships |
| Config, timezone, GPX, model, prompt, language, rendition, library, and threshold dependencies | Processing Profile and Derivation Provenance |
| Field-level metadata provenance and confidence | Observation |
| Complete, partial, not-requested, unavailable, and error states | Availability State attached to the affected information |
| Intermediate local candidates, distances, merge reasons, and alternatives | Candidate Relations; semantic naming work remains method-open |
| Frozen source-to-output mapping and collision decisions | Frozen Organization Plan |
| Operation journal, restart state, and post-verification | Execution Outcome, Verification Evidence, and Apply Receipt |
| Progress, checkpoints, local timing, resources, and run binding | Working lifecycle and sealed-result manifest information |
| LLM calls, retries, token accounting, cost, and structured-output metrics | Resource/External-effect Facts and deferred diagnostic responsibility |
| Transient dictionaries, union-find state, progress bars, and provider-selection state | Not automatically migrated; only their necessary business results, recovery state, or diagnostic evidence qualify |

### Reverse traceability

| New concept family | Origin |
| --- | --- |
| Collection, Source State, Source Item, Scope Decision, Accounting Closure | Historical inventory and manifest evidence, explicit scan/accounting gaps, and MediaSense source-integrity invariants |
| Observation | Historical metadata and local-analysis capabilities plus missing field-level provenance and state |
| Derived Evidence | Historical renditions, frames, embeddings, and the MediaSense requirement for reusable local evidence |
| Content-sensitivity Observation | Historical local classifier evidence plus the product decision to preserve upstream evidence while separating downstream policy |
| Candidate Relation | Historical grouping/clustering behavior and missing stored edges, reasons, spans, and alternatives |
| Coverage Relationship and Evidence Sufficiency | Historical representative compression and failure modes plus the new requirement for coverage-constrained, expandable evidence |
| Semantic Claim, Agent Judgment, User Confirmation, Organization Intent | Historical semantic outputs and failure propagation plus the product decision to keep facts, interpretations, and confirmation distinct |
| Frozen Organization Plan | Historical output effects, the missing frozen mapping, and the invariant that execution makes no semantic decisions |
| Execution Outcome, Verification Evidence, Apply Receipt | Historical output behavior and the missing journal/receipt plus deterministic safety invariants |
| Processing/Profile, epistemic, availability, resource, and lifecycle semantics | Historical stale-cache, empty-value, partial-completion, cost, and audit failures plus resumability and integrity requirements |
| Diagnostic responsibility | Historical audit gaps and the secondary product goal of investigating poor decisions without constraining primary planning methods |

The accepted evidence boundary therefore closes in both directions at the business-semantic level: every known historical class or explicit gap has a disposition, and every required concept has a historical, corrective, or product-invariant origin. Reopening conditions below still apply.

## Evidence, uncertainty, and contradictions

Claims in this map retain their evidence level:

- **Historical source-confirmed:** producer/consumer behavior, write paths, dependencies, and in-memory gaps at the historical commit.
- **Fixture directly observed:** packaged files, counts, shapes, manifests, checksums, and directory topology.
- **Historical run reconstructed:** facts inferred from the package, handoff, and surviving output without the original 1.09 TB source mounted.
- **MediaSense product decision:** new authority boundaries, required information, non-migration, and method openness.
- **Unknown:** alternatives the available evidence cannot distinguish.

Material constraints include:

- The historical implementation used the high-resolution rendition for asset embeddings despite conflicting descriptive wording; the implementation is authoritative for that historical data-flow claim.
- The difference between 4,365 grouping members and 4,362 manifest members is explained by three AppleDouble entries, not by semantic ground truth.
- No translation cache or LLM usage log was observed. This establishes absence in the package, not absence of source capability.
- The 168 bundles, 73 terminal groups, captions, inferred locations, generated titles, and output names are historical observations, not MediaSense truth labels.
- Exact production retries, provider-side token accounting, billed cost, full-source throughput, semantic correctness, and the cause of every missing lazy artifact remain unknown.

No conclusion in this map is more specific than these evidence levels support.

## Coverage and stopping rule

This map is sufficient to proceed to Stage Ownership because:

- source identity, scope, evidence, compression, intent, and execution facts have distinct business meanings;
- evidence can remain traceable from compressed representations to source items;
- observed facts, candidates, Agent judgment, user confirmation, frozen intent, and actual effects cannot silently overwrite one another;
- all 18 historical entries and the important unpersisted information have explicit dispositions;
- new concepts are traceable to evidence, a known historical gap, or a MediaSense invariant;
- replaceable methods have not become permanent product entities.

Stage Ownership must still decide:

- which stage produces, consumes, challenges, validates, and seals each concept;
- which concepts belong in each formal handoff;
- how local evidence expansion and upstream reopening are requested;
- which confirmations make a plan valid;
- how execution reports incompatibility back to planning.

Storage Lifecycle must still decide:

- physical persistence, schemas, and directory layout;
- identity and hashing mechanisms;
- checkpoint, atomicity, retention, garbage collection, and invalidation implementation;
- which working information is retained and which derived views are regenerated.

Reopen this map when:

- an important judgment or handoff requires information with no place in the current concepts;
- one concept is shown to mix incompatible authorities or lifecycles;
- coverage cannot connect compressed evidence to the full accounted source;
- safe execution requires hidden semantic state outside the Frozen Plan;
- new evidence changes the accepted historical inventory boundary; or
- the secondary diagnostic responsibility is shown not to have an independent purpose or lifecycle.

Do not reopen it merely because a detector, model, database, embedding, clustering method, VLM provider, or serialization format changes.
