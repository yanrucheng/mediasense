---
id: "design-260830-1527-reusable-capability-architecture"
title: "MediaSense Reusable Capability Architecture"
type: design
status: active
created: 2026-08-30
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: ""
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
superseded-by: ""
tags: ["capability", "tool", "skill", "provider", "reuse", "architecture"]
---

# MediaSense Reusable Capability Architecture

## Purpose and authority

This document is the active MediaSense architecture for capabilities that may be
used by more than one product stage or by products other than MediaSense. It tells
future designers and Agents how to recognize such a capability, decide which
entities it actually needs, preserve a usable progression from high-level intent
to lower-level evidence or control, and integrate it without transferring stage
authority into shared code.

The framework governs new reusable-capability design and any refactor that claims
to create a reusable capability. It does not itself create a public Tool, Skill,
provider registry, service, artifact type, or compatibility promise. Existing
PreCheck, Plan, Apply, handoff, and Tool contracts remain authoritative for their
current product forms. A capability-specific contract becomes authoritative only
when that capability is separately reviewed and activated.

The intended reader is a competent contributor who did not participate in the
original implementation. The reader must be able to decide what to create, what
not to create, what must remain observable, and what evidence is required without
reverse-engineering the current codebase.

## Governed concept

A **reusable capability family** is a coherent set of operations that serves one
stable purpose without owning a MediaSense stage's business decisions or private
working state. The family may retain real domain semantics. Geographic lookup is
business-agnostic relative to MediaSense even though it is not domain-free.

Reusable capability is not synonymous with reusable code:

| Form | Meaning | Does not imply |
| --- | --- | --- |
| Pure function or value type | Replaceable computation with no independent effect, authority, or lifecycle | A public Tool or Skill |
| Shared module | Code used from more than one context under an existing caller's contract | Stable external semantics |
| Port or protocol | The behavior a replaceable implementation must supply | Runtime discovery or a plugin system |
| Provider or platform adapter | Translation between one external implementation and a capability port | Product policy, authorization, or a separate Agent-facing product |
| Tool | A callable boundary with explicit inputs, effects, authority, guarantees, failure, and evidence | A separate service or a Skill |
| Skill | Independently loadable domain criteria for choosing, composing, challenging, or explaining capability use | Runtime authority, credentials, state, or execution |
| Artifact | Independently meaningful retained output with its own reading or retention lifecycle | Every cached file or intermediate result |
| Service | An independently operated lifecycle or authority boundary | A convenient package or a second consumer |

A Python import, helper name, repeated algorithm, or hypothetical future consumer
does not establish a reusable capability contract.

## Governing relation

Every accepted family preserves this relation:

```text
caller intent and delegated authority
        |
        v
high-level capability operation
        |
        | sufficient result ----------------------> caller judgment
        |
        | insufficient, conflicting, or limited
        v
more specific operation or evidence view
        |
        v
provider / model / platform adapter
        |
        v
observed result, effects, provenance, and limits
```

The high-level operation is optimized for the caller's purpose. Lower levels add
specific evidence, control, or diagnostics. They do not silently broaden
authority, increase permitted effects, reinterpret the caller's goal, or become a
second source of business truth.

This relation, rather than the current code decomposition, generates the public
abstraction. A family may expose one level or several. It must not expose a level
merely because an implementation function exists.

## Responsibility allocation

### Caller and owning workflow

The caller owns why the capability is being used and how the result participates
in its business decision. A MediaSense stage therefore retains ownership of:

- which subjects or inputs are selected;
- the scope that is frozen or otherwise bound for an authorized call;
- the consequence of accepting, rejecting, or ignoring a returned candidate;
- any stage-specific persistence, Result projection, Plan judgment, or Receipt
  statement; and
- whether new evidence changes a stage handoff or requires reopening upstream
  work.

A reusable capability must not read another stage's private database, cache,
Work Record, journal, or mutable lifecycle to obtain these decisions.

### Human or governing policy

The Human or an explicit standing policy owns consequential authorization that has
not already been delegated. Authorization binds the exact material dimensions
that affect risk: selected inputs, permitted operation, data egress, providers or
provider constraints where material, cost ceiling, retained output, and relevant
time or batch scope.

Loading a Skill, selecting a provider default, possessing credentials, or having
authorized a prior call does not widen this authority.

### Agent

The Agent owns interpretation of the caller's purpose and adaptive use of the
capability. Within delegated authority it decides:

- whether the default high-level operation is sufficient;
- which available continuation can resolve a material uncertainty;
- whether provider comparison or more detailed evidence is worthwhile;
- when remaining uncertainty no longer changes the caller's decision; and
- when to stop, ask the Human, or return the problem to the owning workflow.

The Agent must not reconstruct a lower-level operation in model reasoning when an
adequate Tool operation already exists.

### Capability Skill

A family-specific Skill exists only when independently maintained domain criteria
materially improve selection, composition, challenge, escalation, or explanation.
It may teach the Agent how to choose among operations and how to interpret limits.
It does not own credentials, consent, runtime state, provider truth, or effects.

There is no universal operational Skill that selects and runs every reusable
capability. The present architecture is the common design authority. Each family
gets its own Skill only when its domain judgment passes the necessity test below.

### Capability Tool

A Tool owns bounded execution or observation. It enforces the supplied authority
at or before the effect boundary and reports what actually happened. A coherent
family should normally expose one Tool contract with a small operation set when
those operations share authority, effects, provenance, credentials, and failure
semantics. It should split into multiple Tools only when independent effects,
authority, lifecycle, or guarantees would otherwise be misleading.

### Provider or platform adapter

An adapter owns protocol translation and normalization for one provider, model,
codec, external executable, or operating system. It may classify transport-level
failure when the family contract defines the classification. It does not choose
business scope, obtain authorization, interpret domain meaning for the caller, or
persist stage state.

Credentials terminate at the narrowest component that needs them. They never
enter result identity, cache identity, provenance exposed to ordinary callers,
logs, or stage artifacts.

## Capability discovery and entity progression

Design proceeds from responsibility to entity. A candidate passes through the
following progression; it may stop permanently at any level.

### 1. State the capability claim

The claim identifies:

- one stable purpose;
- callers that have a present, evidenced need;
- inputs and returned meaning independent of one stage's storage;
- externally observable effects and risks;
- the authority that remains with each caller; and
- what independent responsibility would be lost if the candidate disappeared.

If the last question has no answer beyond code reuse, the candidate remains an
implementation detail or shared module.

### 2. Separate invariant semantics from current methods

The candidate defines only meaning that must survive a compatible replacement.
Provider names, models, hash algorithms, thresholds, database tables, directory
layouts, HTTP endpoints, retry loops, cache keys, and current orchestration remain
methods unless callers must rely on their consequences.

### 3. Identify the narrow reusable kernel

Pure values, algorithms, and ports are separated from stage coordination before
any public boundary is proposed. A stage adapter may compose the kernel with its
own selection, authorization, Work lifecycle, and handoff projection.

### 4. Derive the semantic ladder

Start from caller questions, not implementation layers. Each proposed level must
answer a materially different question:

```text
goal-oriented result
    -> focused domain observation
        -> attempt or diagnostic evidence
            -> replaceable implementation adapter
```

If exposing a lower level gives the caller no new decision, evidence, or control,
that level remains internal. Provider APIs and raw responses are not automatically
levels in the public ladder.

### 5. Select the minimum entities

| Observed need | Minimum entity |
| --- | --- |
| Pure reusable computation | Function or module |
| Replace provider, model, codec, executable, or OS implementation | Port plus adapter |
| Bounded work or observation must be callable with enforceable effects and evidence | Tool operation |
| Agent needs independently maintained domain selection or interpretation criteria | Family Skill |
| Output must be independently addressed, retained, read, challenged, or transferred | Artifact and read contract |
| Credentials, quota, locking, scheduling, or recovery have an independent operated lifecycle | Runtime or service boundary |

Multiple consumers alone justify none of the last four rows.

### 6. Activate only with acceptance evidence

A public Tool, Skill, artifact, or service is not accepted from an interface sketch.
It requires a real consumer path, contrastive examples, runtime and failure
semantics, and tests at its claimed replacement boundaries.

## Progressive abstraction contract

### Default operation

A family with an Agent-facing Tool provides one goal-oriented default operation
when a stable common purpose exists. The default minimizes unnecessary cost and
effects while returning enough evidence for ordinary use. It must not claim a
semantic conclusion that belongs to the caller.

### Continuations

A result that may be insufficient exposes bounded **continuations**: named next
questions the family can answer, not imperative instructions the caller must obey.
A continuation states:

- what additional information or control it provides;
- what new effects or cost it may cause;
- whether new authorization is required;
- what result identity or subject it remains bound to; and
- what condition makes it inapplicable.

The physical continuation may be another Tool operation, a bounded read over an
existing result, or an internal detail selected by the same operation. It is not
required to be a new Tool.

### Monotonic scope and authority

Moving downward in the ladder may narrow the question or reveal more evidence. It
must not silently add inputs, transmit more data, select another provider class,
raise the cost ceiling, persist new material, or broaden the permitted use.

When a continuation needs a larger effect envelope, the Tool returns
`authorization_required` with the exact proposed delta. It performs no part of
that larger effect before the authority is supplied.

### Evidence preservation

High-level results may summarize lower-level observations, but must preserve:

- which operation actually ran;
- normalized provenance sufficient to challenge the result;
- actual effects and request counts;
- material fallback, conflict, or partial failure;
- qualifications and applicability limits; and
- an exact, bounded route to retained detail when that detail has its own reading
  lifecycle.

Provider-specific raw output may be retained for diagnostics when policy permits,
but it is not ordinary product truth and does not become a stable public schema by
default.

## Capability Tool contract

Every public reusable-capability Tool contract makes the following relations
human-readable and machine-enforceable to the extent material to the family.

### Purpose and operations

The contract states the stable purpose and a small set of caller-meaningful
operations. Operations are named for the question or effect they provide, not the
provider or implementation that happens to answer it.

### Input and binding

Inputs distinguish:

- subject data from caller policy;
- caller-supplied fact from inferred default;
- omitted selection from an explicit empty selection;
- normalized data from provider-native data; and
- new work from a read of an existing immutable result.

An exact operation binds all effect-relevant inputs. A retry cannot silently
resolve them again against changing mutable state.

### Effect envelope

Before an effect, the caller can determine the maximum permitted:

- network and provider access;
- data classes transmitted;
- local and remote model use;
- monetary or quota cost where knowable;
- filesystem mutation;
- retained data and retention scope; and
- concurrency or long-running work when material.

The result reports observed effects independently from the permitted maximum.
Unknown cost or unobserved external activity is reported as unknown, never zero.

### Result semantics

The common result envelope distinguishes at least the applicable meanings among:

| Condition | Meaning | Permitted reliance |
| --- | --- | --- |

| `available` | The requested observation is present | Use within stated provenance and limits |
| `partial` | Useful observation exists but material requested information or an attempt is missing | Use only with the exposed qualification |
| `no_result` | Work completed but established no matching observation | Do not infer that the real-world subject does not exist |
| `not_requested` | Policy or caller chose not to run the work | Do not treat as negative evidence |
| `refused` | Authority or safety policy prevented execution | No prohibited effect occurred |
| `unavailable` | A required provider or local dependency could not be used | Retry or select an allowed alternative only as reported |
| `failed` | The operation did not produce a reliable result | Do not promote partial internal facts unless separately returned as partial |
| `indeterminate` | The Tool cannot prove the effect or outcome boundary | Stop automatic continuation and expose takeover limits |

Families may use more precise states, but they must not collapse these materially
different meanings into null, empty output, or one generic error.

### Provenance and uncertainty

Every challengeable result carries the effective operation/profile, observation
time, producing capability version, providers actually attempted, normalized
input basis, and material qualifications. Confidence is included only with a
defined meaning. Provider output remains candidate observation rather than
confirmed business truth.

### Failure, retry, and partial success

The contract declares whether work is stateless, immediate, batch-bound, or
long-running; what retry identity means; whether completed subwork is retained;
and which failures permit continuation. A caller never needs provider exception
text or private state to decide whether retry is safe.

### Replacement

A compatible implementation may change algorithms, providers, storage,
concurrency, and representation. It preserves promised input meaning, authority,
effect ceiling, result semantics, provenance, failure distinction, and
continuations. Adding a provider does not by itself change the family contract.

## Provider and adapter contract

A capability family defines ports from its stable semantics. Each adapter declares
through configuration or code, not necessarily a runtime registry:

- a stable diagnostic provider identity;
- supported family operations and input constraints;
- locality and data-egress properties;
- provider coordinate, language, model, codec, or platform requirements;
- request-count semantics and relevant quota behavior;
- normalization guarantees;
- timeout, transient failure, permanent failure, no-result, and partial-result
  mapping; and
- credential requirements without exposing credential values.

The family owns provider selection policy only when that policy is part of the
capability's promised behavior. Otherwise the caller supplies an allowed provider
constraint and the Tool chooses a method within it. A provider fallback never
changes locality, transmitted data classes, cost authority, or retained output
without renewed authorization.

No general provider registry or plugin platform is created until multiple active
families demonstrate the same discovery lifecycle and cannot carry it honestly in
ordinary dependency injection or configuration.

## Skill contract and granularity

The repository-level architecture remains the shared design rule. It must not be
duplicated into one universal runtime Skill.

A family-specific Skill is justified when all of the following hold:

1. The Agent has a recurring family goal rather than a one-off API call.
2. Material choices among operations, continuations, evidence, providers, or stop
   conditions require domain knowledge.
3. The knowledge should evolve independently from one workflow and from the
   general model.
4. At least one real Agent workflow exercises those choices.
5. The Skill can remain free of credentials, mutable product state, and effect
   authority.

A Skill should teach goal selection, evidence sufficiency, authorization
disclosure, continuation choice, contradiction handling, and stopping. It should
not restate every Tool field, encode a fixed call sequence, or create a provider
menu that the Tool cannot enforce.

Two capability families share a Skill only when they serve one recurring Agent
goal and require one coherent body of judgment. Common implementation technology
is not sufficient. Geographic lookup and media inspection therefore do not belong
in one generic utility Skill.

## State, caching, and artifact ownership

Stateless operation is the default. Shared mutable state is introduced only when
the family itself needs continuity that callers cannot honestly own, such as a
durable long-running job, cross-caller quota, or independently meaningful retained
result.

A shared capability may cache replaceable method output. Such a cache:

- is not product authority;
- never requires a caller to read private keys or tables;
- includes every semantic dependency needed to prevent invalid reuse;
- does not let one caller inherit another caller's authorization;
- does not persist credentials;
- makes freshness and reuse observable when material; and
- may be deleted without changing retained authoritative results.

If output must remain independently readable or auditable after the producing call,
the design evaluates an immutable artifact and read boundary. It does not expose a
cache path as a substitute.

## Local topology

Topology follows maturity rather than anticipating it.

### Single reusable kernel

A small capability with one consumer may remain a direct module:

```text
src/mediasense/<capability>.py
```

### Established capability family

When multiple adapters or consumers make responsibilities materially difficult to
inspect in one module, the preferred topology is:

```text
src/mediasense/capabilities/<family>/
├── __init__.py          # deliberately exported family surface
├── model.py             # stable internal value semantics
├── protocol.py          # provider, transport, model, or platform ports
├── service.py           # provider-neutral composition
├── tool.py              # only after a public Tool is accepted
└── providers/
    ├── __init__.py
    └── <provider>.py

src/mediasense/<stage>/<family>.py
└── stage-owned selection, authorization binding, persistence, and handoff projection
```

Files are added only for responsibilities that exist. A family with no public Tool
has no `tool.py`. A family with one adapter does not need a `providers/` directory.

### Contract and Skill topology

After activation, public family contracts follow the repository's existing formal
specification topology. A family Skill, when justified, has one separately loadable
home:

```text
docs/spec/<active-family-contract>/
├── index.md
├── <family>.tool.json
└── human-reviewable examples

.agents/skills/<family>/
└── SKILL.md
```

Current contracts are indexed in `docs/spec/`; proposals and transition work may
live in OpenSpec but never become a competing current authority. Source tree shape,
Tool transport, and filenames remain implementation choices unless a public
discovery promise makes them consequential.

## Integration with MediaSense stages

A stage integrates a reusable capability through a stage adapter:

```text
stage purpose and private state
        |
        | selects subject and supplies delegated authority
        v
reusable capability contract
        |
        | returns observation, effects, provenance, limits
        v
stage-owned projection or judgment
```

The adapter may translate Result references, Work Records, Frozen Plan context, or
Receipt facts into capability inputs and translate outputs back into stage-owned
evidence. The reusable family never reads those private representations directly.

The same returned observation may lead to different authorized decisions in
different stages. Shared implementation does not imply shared business policy,
state, cache authority, or result interpretation.

## Acceptance evidence

An accepted reusable family demonstrates all applicable evidence below:

1. **Purpose test:** two materially distinct callers can state the same capability
   purpose without sharing stage policy.
2. **Independent-identity test:** removing the family loses an independent
   responsibility, not merely a code-deduplication opportunity.
3. **Replacement test:** a fake or second adapter satisfies the same normalized
   semantics without the caller learning provider-native fields.
4. **Authority test:** attempts to exceed input, provider, egress, cost, retention,
   or effect authority are refused before the larger effect.
5. **Progression test:** ordinary use succeeds at the highest useful level, while
   insufficient or conflicting cases expose a bounded continuation.
6. **Evidence test:** fallback, actual effects, provider attempts, partial results,
   no-result, and uncertainty remain distinguishable through the high-level result.
7. **Isolation test:** no reusable module reads stage-private storage or mutates
   another caller's state.
8. **Credential test:** credentials do not enter identity, result, logs, cache, or
   stage artifacts.
9. **Failure test:** transient, permanent, refused, unavailable, failed, and
   indeterminate outcomes remain distinguishable where consequential.
10. **Consumer test:** at least one real end-to-end caller uses the accepted public
    boundary; mocks alone do not prove integration.

A provider adapter additionally requires conformance vectors for normalization,
request accounting, partial failure, and credential exclusion. A family Skill
requires workflow fixtures that test selection, escalation, and stopping rather
than memorized call order.

## Geo pressure test

The Geo pressure test has now advanced from a reusable kernel to an active
Agent-facing Tool family. The stage-neutral values, ports, routing, effect guard,
idempotency journal, and composition live under
`src/mediasense/capabilities/geo/`. The compatibility module
`src/mediasense/geo.py` retains coordinate conversion, transport, current provider
adapters, and the legacy ordered-batch composition while callers migrate. Neither
boundary reads PreCheck, Plan, Apply, SQLite, Work, or Result state.

Its current logical shape is:

```text
AdaptiveReverseGeocoder
├── ReverseGeocodeProvider
│   ├── AMapReverseGeocoder
│   └── GoogleMapsReverseGeocoder
├── CoordinateConverter
│   └── XYConvertCoordinateConverter
└── JsonTransport
    └── UrllibJsonTransport
```

The accepted Agent-facing surface is one Tool family with caller-meaningful
operations, not one Tool per provider:

```text
geo capability Tool
├── resolve_place        # goal-oriented default
├── reverse_geocode      # address and administrative components
├── nearby_places        # nearby POI evidence
```

`coordinate.convert`, raw HTTP transport, AMap, and Google remain internal
operations or adapters unless a real caller proves an independent public purpose.
Provider selection defaults and fallback may stay internal, but the result reports
providers actually attempted and cannot cross the authorized effect envelope.

PreCheck retains its frozen batch, confirmation, Work, reuse, and Result projection
through the family batch port. Plan uses `mediasense.plan.work` `enrich_geo` to
validate exact Result-bound coordinates, invoke `mediasense.geo.query`, and retain
the returned observation under a new Plan revision. The capability Tool owns only
effect enforcement, normalized observations, provenance, and safe request replay.

The active Tool contract is
[`spec-260830-2034-geo-query`](../spec/spec-260830-2034-geo-query/). Provider
attempts remain in the ordinary result; no `inspect_attempts` operation or Geo
Artifact has been created.

A Geo Skill is still not justified. The first real selection and stopping criteria
remain in the Plan Skill. A separate Skill is created only if those judgments recur
across independent Agent workflows and need their own evolution lifecycle.

## Additional pressure tests

### Safe file observation

Stable regular-file reading, symlink refusal, pre/post identity checks, and streaming
content verification have reusable implementation value across PreCheck and Apply.
They do not require Agent judgment, independent authority, or a retained product
lifecycle. The correct next entity is a shared internal module, not a Skill or Tool.
The calling contract continues to choose the verification profile and consequence
of mismatch.

### Media inspection

Metadata extraction, image rendition, video probing, frame sampling, visual
comparison, and local sensitivity observation can serve the common purpose of
turning media into bounded inspectable evidence. Current producers still bind this
work to PreCheck Work and Artifact state. A family contract is justified only when
a second real workflow, such as Plan-local inspection, establishes common input,
effect, temporary-material, provenance, and failure semantics.

That family may eventually justify a `media-inspection` Skill because an Agent may
need domain criteria for selecting the cheapest sufficient evidence and deciding
when to inspect more. It must not expose embeddings or current model thresholds as
the high-level purpose.

### Resource admission

Resource claims, bounded concurrency, and cancellation are stage-neutral runtime
infrastructure. They have no Agent-facing domain judgment or independent product
authority. They remain a library and may move to a shared package after a second
consumer proves the topology useful. They do not become a Tool or Skill.

### GPX matching, embeddings, and sensitivity detectors

GPX parsing and timestamp matching may become local geographic-evidence operations.
Embedding encoders and sensitivity detectors already have useful adapter ports.
None currently establishes an Agent-facing family by itself: an embedding vector,
detector score, or GPX match is a method-level observation, not the caller's stable
goal. They remain kernels or adapters until a higher-level purpose and real
consumer satisfy the activation tests.

These cases demonstrate that the framework does not force uniform entity shape.
The same review can legitimately produce a Tool family, a family Skill, a shared
module, a provider adapter, or no new entity.

## Review outcomes

Every reusable-capability review ends with one of these explicit outcomes:

| Outcome | Meaning |
| --- | --- |
| `implementation_detail` | No independent reusable responsibility is established |
| `shared_kernel` | Stable values or computation may be reused under caller contracts |
| `provider_adapter` | One replaceable external implementation conforms to a family port |
| `stage_adapter` | Stage-owned selection, authority, state, or projection composes a reusable family |
| `candidate_family` | Purpose is credible, but public activation evidence is incomplete |
| `active_tool_family` | Callable effects and evidence have an accepted public contract |
| `active_skill_family` | Reusable Agent judgment has an accepted independently loadable Skill |
| `independent_service` | A distinct operated authority or lifecycle has been proven necessary |

`candidate_family` is not permission to publish speculative Tool or Skill entities.

## Reopen conditions

Revisit this architecture when evidence shows that:

- one Tool family cannot honestly express operations with materially different
  authority, effects, or lifecycle;
- provider discovery requires an independently operated lifecycle rather than
  configuration or dependency injection;
- a universal capability Skill would carry real coherent judgment that cannot be
  maintained in family Skills or this architecture;
- stage adapters repeatedly duplicate semantic logic that belongs to a capability
  family;
- a shared cache or artifact obtains an independent authority or retention purpose;
- stronger Agents cannot use better operations because the public ladder fixes a
  current method; or
- an accepted family cannot report effects, uncertainty, or failure honestly
  without exposing provider-native implementation as product semantics.

Do not reopen this architecture merely because another provider, model, algorithm,
codec, database, or directory layout is introduced.
