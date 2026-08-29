---
id: "design-260825-2235B-stage-ownership"
title: "MediaSense Stage Ownership"
type: design
status: active
created: 2026-08-25
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "design-260825-2235-mediasense-information-architecture"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235A-information-domain-map"
  - "eval-260823-1918B-capability-ledger"
  - "eval-260823-1918D-ai-album-stored-information"
superseded-by: ""
tags: ["mediasense", "information-architecture", "stage-ownership", "handoff"]
---

# MediaSense Stage Ownership

## Purpose and boundary

This document assigns the business concepts in the accepted [MediaSense Information Domain Map](design-260825-2235A-information-domain-map.md) to `mediasense.precheck`, `mediasense.plan`, and `mediasense.apply`.

It answers:

> Which stage first establishes each kind of information, which stage owns its authoritative meaning, how other stages may consume or challenge it, where it is sealed, and where a failure must be routed?

Ownership does not prohibit downstream reading, local computation, challenge, or supplementation. It prevents a downstream stage from silently rewriting an upstream fact, candidate, decision, or execution result under a different authority.

### Non-goals

This document does not define:

- a schema, serialization format, database, directory layout, or cache key;
- a Tool, Skill, Agent implementation, model, detector, embedding, clustering method, or VLM request format;
- the sequence by which an Agent and user reach an organization decision;
- a Diagnostic Package contract;
- physical storage, retention, garbage collection, or migration mechanisms.

The three handoff boundaries below define business-content ownership. PreCheck has a formal [Read contract](../../spec/spec-260826-1546-precheck-read/), Plan has an active [Frozen Plan contract](../../spec/spec-260827-1138-frozen-plan/), and Apply has an active [Run, Receipt, and Read contract](../../spec/spec-260829-0050-apply/).

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC level | None — Zero Backward Compatibility |

No legacy-cache reader, adapter, dual write, deprecated field, old cache flag, or historical directory convention is permitted. Historical AI Album evidence may justify a capability or expose a gap, but it cannot own a MediaSense stage boundary.

## Ownership semantics

The ownership columns below have these meanings:

- **Producer:** the stage in which an information instance is first established. A Tool, model, Agent, or human may supply the value while operating within that stage.
- **Authoritative owner:** the stage responsible for the retained business meaning. Every information instance has exactly one authoritative home, even when many stages consume it.
- **Consumer:** a stage allowed to read or use the information without changing its upstream meaning.
- **Challenger:** a stage allowed to reject validity, identify insufficiency, or request replacement. Challenge creates a new downstream judgment or routes work back; it does not mutate a sealed upstream record.
- **Validator:** a stage that checks declared integrity, compatibility, completeness, or postconditions. Validation does not transfer semantic ownership.
- **Sealing stage:** the stage that makes the information immutable as part of a formal handoff.
- **Mutation boundary:** working information may change only before its owning handoff is sealed. A later correction produces a new handoff version rather than editing history.
- **Failure destination:** the stage that must resolve missing, untrusted, incompatible, or insufficient information.

For cross-cutting semantics such as provenance or availability, the authoritative owner follows the information being qualified. There is no detached global provenance, status, confidence, or lifecycle record that can contradict its subject.

## Governing stage flow

```text
mediasense.precheck
  mutable Working Run
    -> source accounting + local evidence + coverage
    -> sealed, trustworthy PreCheck Result
          |
          | read, challenge, and locally expand existing evidence
          v
mediasense.plan
  open Agent/user interpretation
    -> complete organization intent
    -> sealed Frozen Organization Plan
          |
          | exact plan, source binding, and authorization
          v
mediasense.apply
  deterministic validation + execution + post-verification
    -> sealed Apply Receipt
```

The flow has four invariants:

1. PreCheck is source-read-only and local-first. Remote calls and data egress are disabled by default. Post-compression coordinate reverse geocoding is permitted only for an exact frozen logical query set confirmed by the user and recorded with provider and actual-request evidence; remote models and media, feature, prompt, or general-metadata egress remain outside this stage.
2. Plan does not replace PreCheck's source facts, candidate evidence, coverage, or declared omissions. It may interpret, ignore, challenge, or request replacement of them.
3. Apply receives only an exact Frozen Organization Plan as semantic authority. It does not caption, identify places, classify, group, name, or repair intent.
4. Every replacement of a sealed upstream handoff creates a new version and invalidates downstream compatibility until the downstream handoff is reconsidered and resealed.

No stage may depend on another stage's hidden mutable working state.

## Stage Ownership matrix

### Source and scope

| Concept | Authoritative owner | Producer | Consumers | Challenger / validator | Seal and formal handoff | Mutation and failure route |
| --- | --- | --- | --- | --- | --- | --- |
| Dataset | The user or owning product maintains its continuing identity; PreCheck owns its use within the stage. | Created from user or product intent and referenced by PreCheck. | Plan and Apply reference it. | Plan may challenge mistaken identity; Apply validates only the bound reference. | Each PreCheck Result carries the exact Dataset reference; later handoffs cite it. | Never silently rebound. Source changes do not create a new Dataset, but a wrong Dataset binding requires new downstream handoffs. |
| Source Item | PreCheck within one Result. | PreCheck discovery and validation. | Plan assigns organization intent; Apply resolves only the exact planned item reference. | Plan challenges missing or contradictory facts; Apply validates existence and compatibility. | Directly accounted for by the PreCheck Result, then referenced by Frozen Plan and Apply Receipt. | Result-local facts are immutable. Source change or a missing or misidentified item requires a new Result, while unaffected internal work may be reused. |
| Scope Discovery | PreCheck. | PreCheck traversal and discovery. | Plan reads the declared boundary and discovered population. | Plan may challenge unexplained omissions; PreCheck validates discovery accounting. | PreCheck Result. | Mutable only during the Working Run. Undiscovered or ambiguously skipped material returns to PreCheck. |
| Scope Decision | PreCheck, including any Agent/user scope choice made within that stage. | PreCheck stage from rules, evidence, and necessary confirmation. | Plan accepts the declared planning scope; Apply acts only on items represented in the plan. | Plan may challenge a consequential exclusion; Apply validates that no out-of-scope effect is requested. | The Result's `accounts_for` member records `scope` independently from processing `condition`. | Changed scope requires a new PreCheck Result; Plan cannot silently add source items. |
| Accounting Closure | PreCheck. | PreCheck reconciles discovery and dispositions. | Plan uses it to determine whether source material silently disappeared; Apply relies on the plan's complete in-scope disposition. | Plan validates the declared closure and may expose contradictions. | PreCheck Result. | Unreconciled items prevent a trustworthy cross-stage handoff or return to PreCheck. |

### Evidence and compression

| Concept | Authoritative owner | Producer | Consumers | Challenger / validator | Seal and formal handoff | Mutation and failure route |
| --- | --- | --- | --- | --- | --- | --- |
| Observation | PreCheck for source-derived and local observations. | PreCheck local extraction or measurement. | Plan may use or ignore it. Apply does not reinterpret it. | Plan may challenge provenance, availability, or reliability. | PreCheck Result. | A corrected or newly acquired observation requires a new PreCheck Result. A semantic interpretation remains Plan-owned instead. |
| Evidence | PreCheck for source-derived material exposed through the compressed result. | PreCheck local computation or direct reuse of a Source Item. | Plan reads, expands, transforms into temporary review views, or ignores it. | Plan challenges validity or fitness; PreCheck validates dependencies before seal. | PreCheck Result. | Existing Evidence is immutable after seal. New decoding, extraction, or reusable evidence generation returns to PreCheck. |
| Candidate Relation | PreCheck when retained as evidence content; it is not a sixth universal Tool relationship. | PreCheck local comparison or grouping. | Plan uses or rejects the candidate while deciding final organization. | Plan may challenge membership, alternatives, or confidence. | Exposed through Evidence, observations, basis, or qualifications in the PreCheck Result when material. | Plan never rewrites the candidate into a fact. Missing or materially misleading candidates return to PreCheck; final grouping remains Plan-owned. |
| Coverage Relationship | PreCheck. | PreCheck compression work connects lower-cost Evidence to the Source Items it represents and keeps production lineage and expansion navigation distinct. | Plan can begin from entry Evidence and traverse existing detail while retaining full control over what it actually reads. | Plan may challenge hidden material differences; PreCheck validates declared coverage, traceability, expansion, and limits. | PreCheck Result. | A broken or materially inadequate relation requires a new PreCheck Result. Plan-specific reading choices do not mutate it. |
| Evidence Sufficiency | PreCheck owns the claim that the result is sufficient for planning within its stated boundary. | PreCheck evaluates accounting, evidence, coverage, and residual uncertainty. | Plan uses it as an entry claim, not as a guarantee of correct semantic judgment. | Plan is the principal downstream challenger. | PreCheck Result. | If challenged successfully, Plan issues a Reopen Signal and PreCheck produces a new result. Complete accounting alone cannot silently restore sufficiency. |
| Reopen Signal | The detecting stage owns each signal; PreCheck owns resolution of signals targeting evidence preparation. | PreCheck may record known triggers before seal; Plan may issue a new signal during planning. | PreCheck consumes Plan-issued signals; Plan consumes known triggers in the result. | The target stage validates whether the trigger is material and records its resolution. | Known triggers are in the PreCheck Result. A Plan-issued signal is a routing record, not a fourth formal handoff. | Immutable once issued. It is resolved by continuing PreCheck work and sealing a new result, never by editing the old result. |

### Interpretation and organization intent

| Concept | Authoritative owner | Producer | Consumers | Challenger / validator | Seal and formal handoff | Mutation and failure route |
| --- | --- | --- | --- | --- | --- | --- |
| Semantic Claim | Plan when a claim is retained for planning. | A model, Agent, or human operating in Plan. | Agent and user may use or ignore it. Apply does not consume it as authority. | Agent and user challenge it against evidence and alternatives. | No separate handoff is required; only plan-relevant accepted effects enter the Frozen Plan. | Mutable or discardable during Plan. Evidence gaps route to PreCheck; interpretation errors remain in Plan. |
| Agent Judgment | Plan. | Agent during Plan. | User reviews consequential judgments; the Frozen Plan carries accepted results. | User challenges or changes it; Plan validates internal consistency. | No required transcript; accepted decision effects are sealed in the Frozen Plan. | Mutable until plan freeze. A changed judgment creates a new plan version, not an upstream evidence rewrite. |
| User Confirmation | Plan owns the retained binding; the human is the decision source. | User interaction within Plan. | Plan validation and Apply authorization checks consume only the confirmation needed for the exact plan. | Plan validates scope and binding; the user may supersede it before a new freeze. | Relevant confirmation and authorization binding are sealed with the Frozen Plan. | Cannot be broadened by inference. Missing or changed confirmation returns to Plan. |
| Organization Intent | Plan. | Agent and user collaboratively establish it. | Plan validation and plan freezing consume it. Apply consumes only its frozen execution form. | User is the principal challenger; Plan checks completeness and conflicts. | Its complete execution form is the Frozen Organization Plan. | Freely mutable during planning. After freeze, any change requires a new Frozen Plan. |
| Frozen Organization Plan | Plan. | Plan freezes complete, reviewed Organization Intent. | Apply is the execution consumer; audit and later evaluation may read it. | Apply validates integrity, source compatibility, authorization, completeness, and deterministic executability without changing semantics. | Plan seals the Frozen Organization Plan. | Immutable. Semantic ambiguity, incompleteness, conflicts, or authorization defects return to Plan. A replacement PreCheck Result also requires Plan reconsideration and a new freeze. |

### Execution and verification

| Concept | Authoritative owner | Producer | Consumers | Challenger / validator | Seal and formal handoff | Mutation and failure route |
| --- | --- | --- | --- | --- | --- | --- |
| Execution Outcome | Apply. | Apply's deterministic execution Tools. | Apply verification, the user, and later evaluation. | Apply validates operation state and idempotency against the exact plan. | Apply Receipt. | Journaled working state may advance during execution; sealed outcomes never change. Recoverable operational failure stays in Apply; a required semantic change returns to Plan. |
| Verification Evidence | Apply. | Apply postcondition checks. | Apply Receipt, user, and evaluation. | Apply compares observed facts with planned postconditions. | Apply Receipt. | Additional deterministic checking may continue before seal. A discrepancy is recorded, not explained away; source/evidence defects may route through Plan to PreCheck. |
| Apply Receipt | Apply. | Apply seals complete operation accounting and verification. | User, audit, evaluation, and any later recovery workflow. | The user or evaluator may challenge internal completeness; Apply validates receipt integrity. | Apply seals the Apply Receipt. | Immutable. An incomplete receipt remains an Apply failure; a retry or resumed execution produces new outcome history without rewriting prior facts. |

### Cross-cutting information semantics

| Concept | Authoritative owner | Producer | Consumers | Challenger / validator | Seal and formal handoff | Mutation and failure route |
| --- | --- | --- | --- | --- | --- | --- |
| Processing Profile | The stage owning the qualified result. | Each stage records effective choices that materially affect interpretation or validity. | Downstream consumers and validators of that result. | The consumer may reject an unknown, incomplete, or incompatible profile. | Included in the corresponding handoff when needed to interpret or validate it. | Immutable with the qualified record. Material profile change produces a new result, plan, or receipt as applicable. |
| Derivation Provenance | The owner of the Observation, Evidence, planning result, or execution evidence it qualifies. | The stage producing that information. | Downstream consumers, evaluators, and regeneration logic. | Consumers challenge missing inputs, producer identity, dependencies, or lineage. | Travels with the qualified information in its formal handoff when retained. | Never repaired out of band. Missing material provenance invalidates or blocks the qualified information at its owner. |
| Epistemic State | The owner of the qualified statement. | The stage producing or retaining the statement. | Every downstream reader. | Consumers validate that fact, candidate, judgment, confirmation, intent, and outcome remain distinguishable. | Travels with the qualified information. | Cannot be promoted silently. A changed epistemic status requires a new owned statement or handoff version. |
| Availability State | The owner of the qualified information. | The stage attempting or deciding whether to produce it. | Every consumer of that information. | Consumers challenge ambiguous absence or empty values. | Travels with the qualified information. | `Not-requested`, unavailable, partial, and error remain distinct. Resolution occurs in the owning stage and yields a new sealed version when already handed off. |
| Confidence and Quality | The owner of the qualified evidence or claim. | The relevant producer using a declared meaning or method. | Downstream reasoning and evaluation. | Consumers challenge calibration, provenance, or unsupported precision. | Travels with the qualified information when available and material. | No universal score is invented. Recalculation or changed meaning belongs to the owner and creates a new version. |
| Resource and External-effect Facts | The stage causing the resource use or external effect. | PreCheck records local work, default-zero external proof, and any confirmed coordinate reverse-geocode requests; Plan records its model use, egress, authorization, cost, and user-attention effects; Apply records filesystem operations and execution resources. | User, stage validators, audit, and evaluation. | The next stage validates only facts needed for entry; audit may challenge proof boundaries. | Relevant summaries and required authorization/effect bindings enter the owning stage's handoff; detailed Plan diagnostics remain deferred. | Facts are append-only while working and immutable when sealed. Unknown or unobservable scope must be explicit, never inferred as zero. |
| Lifecycle Role | The stage owning the information or artifact. | Each stage labels mutable working state, reusable artifacts, sealed results, and derived views under its control. | Runtime, downstream consumers, and evaluation. | Consumers validate that working state is not presented as a sealed authority and that derived views do not replace their sources. | Sealed role is represented by the corresponding formal handoff; working state never crosses as authority. | Mutable work may advance; reusable artifacts may invalidate; sealed handoffs are replaced only by new versions; derived views may be regenerated. |

### Diagnostic responsibility

Plan owns the secondary responsibility to retain or make discoverable enough externally observable context to investigate a poor organization decision. PreCheck Result and Apply Receipt remain their own authoritative evidence and need not be copied into diagnostic material.

Diagnostic material:

- does not participate in plan validity or Apply execution;
- cannot override the Frozen Plan, PreCheck Result, or Apply Receipt;
- does not require storage of private Agent reasoning;
- may be incomplete without invalidating an already valid Frozen Plan;
- remains without a formal package, capture, redaction, retention, or completeness contract in this stage.

## Formal handoff boundaries

These define business-content responsibility rather than physical storage. Active PreCheck Read, Frozen Plan, and Apply contracts formalize all three handoff boundaries while preserving the ownership split below.

### PreCheck Result

PreCheck seals one immutable compression result. Its accepted conceptual model is defined by [PreCheck Compression Boundary](design-260825-2235D-precheck-compression-boundary.md):

```text
Dataset
└── referenced by an immutable PreCheck Result
      ├── accounts for Source Items
      ├── exposes lower-cost entry Evidence
      └── lets Evidence represent, derive from, and expand toward
          Source Items or other Evidence
```

These are logical concepts, not required files, tables, or serialized components. The handoff must carry or make available enough stable semantics to establish:

- immutable result identity, its Dataset reference, and the Source Items directly accounted for within its declared boundary;
- lower-cost entry Evidence that materially reduces default inspection cost for that purpose;
- what each relevant Evidence item represents, what it derives from, and where existing detail expands next;
- bidirectional traceability between in-boundary Source Items and the compressed result;
- an explicit path for every in-boundary Source Item, including exceptions, exclusions, failures, and unknowns rather than silent disappearance;
- material compression loss, hidden variation, uncertainty, basis, and other limits at the Result, Source Item, Evidence, or relationship where each consequence belongs;
- enough integrity and trust-boundary evidence to rely on the sealed result without mutable Working Run state.

Within the declared MediaSense control boundary, a trustworthy PreCheck handoff must establish zero media upload, zero metadata, coordinate, or feature-artifact egress, zero remote-model and online-map calls, and zero billable requests. Configuration intent, enforced network policy, observed zero-request audit evidence, and unobserved external processes remain distinguishable.

Content-sensitivity probing may be explicitly `not_checked`; capability does not imply mandatory invocation. The state must remain honest and must not be interpreted as a negative signal.

Providing a low-cost, traceable compression entry is a PreCheck responsibility, not a command about Plan attention. Plan owns its reading and reasoning methods. The PreCheck Result describes its own Evidence, relationships, limits, and trust boundary; it does not prescribe Plan behavior.

### Frozen Organization Plan

Plan seals the primary organization outcome. The handoff candidate must carry or bind:

- exact compatible PreCheck Result and Dataset identities, plus the Source Items from that Result used by the plan;
- the complete disposition of every item in its planning scope;
- final organization units, membership, naming, ordering, and intended operations;
- target identities or deterministic target rules sufficient for Apply without semantic invention;
- handled conflicts, collisions, and unresolved-condition policy;
- required safety preconditions;
- plan version, integrity, freeze state, and exact user confirmation or authorization binding.

It need not contain every Semantic Claim, model response, Agent Judgment, dialogue turn, review view, or VLM payload. Plan remains free to use better methods as long as the frozen result is complete and independently executable.

Plan alone decides which existing evidence to read, how to crop, scale, compose, or re-encode it for a VLM, whether to use local or remote providers, what may be uploaded, and how requests, privacy policy, tokens, and cost are controlled. These method choices do not mutate PreCheck evidence.

### Apply Receipt

Apply seals the actual execution record. The handoff candidate must carry or bind:

- exact Frozen Organization Plan identity, integrity, and authorization binding;
- preflight and source-compatibility results;
- every planned operation and its attempted, completed, refused, or failed outcome;
- journal and restart/idempotency facts needed to understand the run;
- observed postconditions and Verification Evidence;
- planned-versus-actual discrepancies, unresolved failures, and complete operation accounting;
- receipt identity, integrity, and execution resource facts.

The receipt never repairs a plan by changing a name, group, target, or operation. It reports reality even when reality differs from intent.

## Expansion and reopening boundaries

### PreCheck internal expansion

Before sealing, PreCheck may scan further, extract additional observations, derive evidence, recompute candidates, improve coverage, and update Working Run checkpoints. This is ordinary ownership of mutable preparation.

After sealing, the same activities do not mutate the result. They occur in a new Working Run and, if successful, produce a new PreCheck Result.

### Plan local expansion

Plan may, without reopening PreCheck:

- follow existing coverage and expansion links;
- inspect more Source Items, Observations, Evidence, candidate information, or known conflicts already contained in or bound by the sealed result;
- derive temporary review views from existing evidence;
- crop, scale, compose, or re-encode existing evidence for an actual VLM request;
- choose to use or ignore any available evidence, including content-sensitivity candidates.

This is normal progressive use. Plan owns the reading strategy and does not write the resulting attention choices back into PreCheck.

### Reopen PreCheck

Plan must issue a Reopen Signal when the needed corrective action would create or change upstream evidence authority, including:

- a material source region is absent or unaccounted;
- compressed Evidence or its relationships hide a major difference;
- an expansion path is missing or does not reach the claimed covered set;
- a necessary observation or reusable evidence artifact was not requested, is unavailable, invalid, or failed and must now be acquired;
- candidate membership, provenance, validity, or quality is materially unreliable;
- source change makes the sealed result incompatible.

Reopening creates a new PreCheck Result. Plan then re-evaluates compatibility and, if necessary, produces a new Frozen Plan. Reopen is not proof that the earlier result was dishonest: an explicit partial result or an optional `not_checked` observation may have been valid for its original declared purpose.

## Cross-stage validation and compatibility

### PreCheck Result entering Plan

Plan validates, without re-performing PreCheck:

- result identity and integrity;
- the bound Dataset and directly accounted Source Items within the declared purpose and boundary;
- availability of lower-cost entry Evidence;
- reachability of every in-boundary Source Item through a normal compressed path or explicit exception path;
- resolvable representation, derivation, expansion, and reverse-lookup relationships over Evidence and Source Items;
- visible material compression loss, uncertainty, provenance, and limits;
- independence from mutable Working Run state;
- source-read-only and external-effect proof within its observation boundary, including either observed zero external calls or the exact authorization and actual effects of optional coordinate reverse geocoding.

A readable result is not automatically compatible. Missing integrity, stale dependencies, an unsupported declared boundary, or material insufficiency blocks planning and routes to PreCheck.

### Frozen Organization Plan entering Apply

Apply validates, without semantic reinterpretation:

- plan identity, integrity, freeze state, and exact authorization;
- the compatible PreCheck Result and Dataset binding declared by the plan;
- current source compatibility required by the planned operations;
- complete item disposition and operation accounting;
- deterministic targets, collision decisions, and safety preconditions;
- absence of unresolved semantic choices.

An incomplete or ambiguous plan returns to Plan. A changed or untrustworthy source returns through Plan to PreCheck, because new source evidence may invalidate organization intent. No compatibility adapter may make an old or foreign format appear valid under Zero BC.

### Apply Receipt completion

Apply may seal a receipt only when every planned operation is accounted for, including refused and failed operations, and every required postcondition has an observed result or an explicit unavailable/error state. Receipt completion does not mean every operation succeeded; it means actual outcomes are no longer hidden.

## Failure and reopen routing

| Condition | Continue or return to | Required effect |
| --- | --- | --- |
| PreCheck Working Run is paused, interrupted, or recoverably incomplete | PreCheck | Resume from working state; do not present it as a sealed result. |
| Source binding, compression coverage, traceability, material-loss disclosure, integrity, source-read-only proof, or external-effect proof cannot support a trustworthy handoff | PreCheck | Continue preparation; do not present mutable or insufficient work as the cross-stage result. |
| Plan needs more detail already present behind coverage/expansion links | Plan | Locally expand the sealed result; no reopen. |
| Plan wants a different review view or VLM composition from existing evidence | Plan | Create temporary Plan-owned working material; no upstream mutation. |
| Plan discovers missing source items, material hidden variation, broken coverage, or necessary absent/invalid evidence | PreCheck | Issue Reopen Signal; produce a new PreCheck Result. |
| Evidence is adequate but classification, naming, user preference, or confirmation is unresolved | Plan | Continue Agent/user planning. |
| Frozen Plan is incomplete, ambiguous, unauthorized, or requires a new semantic choice | Plan | Refuse Apply entry; amend and freeze a new plan. |
| Apply detects source incompatibility that may invalidate evidence or membership | PreCheck through Plan | Refuse effects; create a new PreCheck Result, then reconsider and refreeze Plan. |
| Apply encounters a recoverable operational error while plan semantics remain exact | Apply | Journal, retry, or resume deterministically within the authorized plan. |
| Apply encounters a collision or safety condition not resolved by the plan | Plan | Refuse the affected operation; do not invent a target or fallback. |
| Post-verification differs from the plan | Apply, then Plan if intent must change | Record the discrepancy in the receipt; never rewrite the plan to match. |
| Diagnostic material is absent or incomplete | Plan diagnostic responsibility | Report diagnostic limits; do not invalidate or alter an otherwise valid Frozen Plan or Apply decision. |

## Historical capability coverage check

AI Album remains evidence only. The ownership split preserves useful capability while removing pipeline coupling:

| Historical capability family | MediaSense ownership disposition |
| --- | --- |
| Recursive inventory, ignore/scope behavior, discovered GPX inputs, and validation | PreCheck owns discovery, Scope Decisions, Source Items, and Accounting Closure. |
| Same-stem/sidecar association, temporal chaining, weights, and representative selection | PreCheck owns inspectable Candidate and Coverage Relationships; Plan owns the final organization decision. |
| Metadata, timestamp candidates, video sampling, visual renditions, local embeddings, and local content-sensitivity signals | PreCheck owns local Observations and Evidence with basis, status, validity, and replaceable methods. |
| Date/location/content clustering | PreCheck may produce local candidates and coverage evidence; Plan alone decides final grouping and semantics. |
| Captioning, visual place inference, title generation, translation, and coherent naming | Plan-owned open interpretation methods; only accepted final effects enter the Frozen Plan. |
| Sensitivity-informed local/remote routing | Intentionally changed: PreCheck owns candidate signals; Plan owns explicit VLM policy, provider choice, authorization, egress, and cost. |
| Direct output-tree construction | Split into Plan-owned Frozen Organization Plan and Apply-owned deterministic execution plus receipt. |
| Copy, link, move, thumbnail, and other operation modes | Plan authorizes exact intended operations; Apply validates and executes without semantic fallback. |
| Cache reuse, interruption behavior, and invalidation | The producing stage owns working/reusable/sealed lifecycle semantics; no historical cache format or flag is inherited. |
| Usage and operation monitoring | Each stage owns the resource and external-effect facts it causes; evidence limits remain explicit. |

This allocation preserves the historical compression and reuse capabilities while preventing a local candidate, cached semantic output, or partially materialized tree from acquiring authority it did not earn.

## Unresolved decisions deliberately deferred

The following decisions remain open by design:

- exact fields, schemas, serialization, filenames, and physical locations of the Plan and Apply handoffs, plus PreCheck's internal storage;
- Dataset, Source Item, handoff, and authorization identity mechanisms;
- PreCheck profiles, sufficiency measures, representative/coverage algorithms, and artifact invalidation implementation;
- which optional observations are requested by a particular PreCheck profile;
- Plan evidence-selection methods, VLM payload construction, provider interface, policy representation, and budget controls;
- Plan freeze, amendment, confirmation, and authorization contract details;
- whether and when diagnostic material is captured, plus its privacy, redaction, retention, deletion, completeness, and binding rules;
- Apply transaction, journal, fault recovery, and cross-filesystem contract details beyond the Foundation invariants;
- storage lifecycle, retention, garbage collection, database, and directory design;
- Plan and Apply Tool and Skill choices, plus all implementation choices behind the PreCheck read boundary.

These questions require reviewed handoff examples, runtime/failure semantics, or discriminating experiments. They are not prerequisites for assigning business authority.

## Coverage and stopping rule

This ownership map covers every concept and cross-cutting semantic in the accepted Information Domain Map. It is sufficient for human review because:

- every information instance has one authoritative home;
- producers, consumers, challengers, validators, sealing, mutation, handoff, and failure routing are explicit;
- the three formal handoffs do not depend on hidden mutable state;
- PreCheck evidence preparation, Plan evidence use, and Apply execution remain distinct;
- local Plan expansion and upstream reopening are distinguishable by whether upstream evidence authority changes;
- facts, candidates, judgments, confirmation, frozen intent, and actual outcomes cannot silently replace one another;
- historical capabilities have an ownership disposition without inheriting historical product identifiers or formats;
- method freedom is preserved for stronger Agents, models, and Tools.

Reopen this ownership map if evidence shows that:

- a required information meaning has no authoritative stage;
- a handoff cannot be consumed without hidden mutable state;
- Plan cannot normally reach an effective decision from coverage-constrained evidence without taking over full preprocessing;
- Apply needs a semantic decision not present in the Frozen Plan;
- a failure cannot be routed without one stage overwriting another stage's authority; or
- a deferred diagnostic mechanism is later shown to participate in plan validity or execution authority.

Do not reopen it merely because storage, schema, algorithms, models, providers, or Agent capabilities change.
