# Design: Stage-Neutral Geo Capability

## Context

The accepted design direction and review fixture live in
`docs/design/design-260830-1626-geo-capability-evolution.md`. The governing entity
and abstraction rules live in
`docs/design/design-260830-1527-reusable-capability-architecture.md`.

Current code already separates coordinates, conversion, transport, AMap and Google
Maps adapters, and adaptive composition from stage storage. PreCheck wraps that
kernel with the exact stage responsibilities required by its contract. The missing
boundary is an effect-enforcing capability surface that an Agent can use without
learning provider APIs or inheriting PreCheck Work state.

## Goals / Non-Goals

### Goals

- Offer the least expansive useful geographic observation first and preserve a
  bounded path to more detailed evidence.
- Enforce coordinate-only egress and exact authorization before network effects.
- Keep provider selection, fallback, transport, coordinate conversion, and routing
  replaceable while preserving observable provenance and effects.
- Let PreCheck and Plan reuse one capability family without sharing mutable stage
  state or business judgments.
- Preserve all current PreCheck behavior during migration.

### Non-Goals

- Determining final place truth, album naming, grouping, or Human intent.
- Exposing provider-specific Tools, raw HTTP, or coordinate conversion to Agents.
- Adding Geo behavior to Apply.
- Creating a Geo Skill in the first delivery.
- Creating a provider registry, shared cache, Geo Artifact, or service.
- Making directory layout, provider order, routing heuristic, hash algorithm,
  SQLite schema, or current provider set a permanent product promise.

## Decisions

### 1. Use one capability family with three caller-meaningful operations

The first contract contains `resolve_place`, `reverse_geocode`, and
`nearby_places`. They share purpose, authority, effects, evidence, and failure
semantics and therefore do not justify separate Tool families.

`resolve_place` is the high-level default. The other operations are available when
the Agent needs a narrower observation or follows an applicable continuation. A
continuation never exposes provider APIs or implementation primitives.

### 2. Keep preflight inside each operation lifecycle

The Tool does not add public `prepare` and `execute` business operations. An
effectful operation without sufficient authority returns `authorization_required`
and an exact proposed effect envelope without making a provider request. The same
operation can then continue with authority bound to the normalized request
fingerprint.

This preserves a goal-oriented Tool surface while making authorization enforceable.
The fingerprint representation remains an implementation method; equality of the
effective request is the invariant.

### 3. Separate capability observations from Plan judgment

The Tool returns provider-derived candidates, component outcomes, qualifications,
and provenance. It does not say that a candidate is the correct album location or
that evidence is sufficient for a Plan decision.

The Plan Agent owns that judgment. Plan Working State stores the observation,
Agent interpretation, and Human confirmation as distinguishable information.

### 4. Bind authority to the complete effect envelope

Authority covers exact normalized subjects, operation, allowed data classes,
provider constraints, fallback ceiling, maximum logical operations, maximum
provider requests, cost or quota ceiling when knowable, and retention scope.

The Tool rejects a changed or broader request before network access. A continuation
inherits subject identity and prior evidence, not permission for added effects.

### 5. Use component outcomes and ordered attempt evidence

An overall result alone cannot distinguish address success from nearby-place
failure. Every requested component reports its own outcome, while the result also
records ordered provider attempts and separates logical operations, actual provider
requests, and billable units.

`not_requested`, `no_result`, `failed`, and `indeterminate` remain distinct. A
timeout after transmission cannot be reported as zero external effect.

### 6. Make routing state request-scoped

The current adaptive geocoder mutates provider and language state across a batch.
The family replaces that implicit shared state with an immutable route context
passed and returned by the composition layer. Concurrent calls cannot influence
one another.

PreCheck may persist the returned context as a Work dependency to preserve its
ordered-batch reuse semantics. Plan receives its own context and never reads
PreCheck routing state.

### 7. Keep providers behind operation-aware ports

Each adapter declares its supported operations and request semantics. An adapter
may combine authorized evidence components efficiently when a provider supports
that shape, but it cannot fetch or retain an unrequested component merely because
the provider API makes it convenient.

AMap and Google Maps are wired explicitly at the composition root. Adding a
provider does not require a public contract change unless it changes promised
semantics or effects.

### 8. Keep stage state and projection with each stage

PreCheck retains frozen batch selection, Human checkpoint, Work, retry, reuse,
cancellation, and Result projection. Plan owns selection for its current question,
authorization binding, Plan-local observation persistence, and preview exposure.

The family does not read either stage's SQLite database. No mutable authorization,
cache, or routing state is shared across stages.

### 9. Do not create a Geo Skill yet

The first workflow can keep evidence-selection judgment in the Plan Skill. A Geo
Skill is reconsidered only after real workflows demonstrate independently reusable
criteria for sufficiency, escalation, provider conflict, and stopping.

### 10. Journal effectful calls without creating a shared observation cache

The public Tool owns a minimal idempotency journal for `request_id`, effective
request identity, authorization binding, execution state, and terminal result.
Identical retry returns the recorded outcome. Conflicting reuse is refused. An
interrupted call whose provider effect cannot be determined becomes
`indeterminate` rather than being sent again automatically.

This journal proves and recovers Tool effects. It does not answer geographic
queries from prior observations, establish freshness, or become a cross-stage
source of truth.

### 11. Extend the existing Plan Working Tool instead of adding another stage Tool

`mediasense.plan.work` gains an `enrich_geo` action implemented by a Plan-owned
adapter. The action validates coordinates through the exact PreCheck Read contract,
invokes `mediasense.geo.query`, and stores a terminal observation in the same
Working State transaction that advances the Plan revision.

This keeps one Plan state authority. Authorization preflight and refusal leave the
revision unchanged. A stored observation advances the revision even when candidate
content is unchanged so preview content remains exactly revision-bound.

## Target Flow

```text
Plan Agent
└── PlanGeoAdapter selects exact Result-bound coordinates
    └── Geo Tool operation
        ├── insufficient authority
        │   └── authorization_required, zero provider requests
        └── matching authority
            └── provider-neutral service
                ├── request-scoped routing policy
                ├── AMap adapter
                └── Google Maps adapter
                    ↓
                normalized candidate observation
                    ├── provenance and observed effects
                    ├── component outcomes
                    └── bounded continuations
                        ↓
                Plan stores observation separately from judgment
```

## Delivery Strategy

1. Establish delta requirements and contract examples before public schema names
   become implementation commitments.
2. Introduce the internal family model and ports with adapters that preserve
   existing behavior.
3. Migrate PreCheck through the family boundary and prove contract compatibility.
4. Add the authorization-bound Tool and its formal JSON contract.
5. Add Plan-owned persistence and the first real Plan workflow.
6. Update the Plan Skill only after deterministic behavior is stable.
7. Reconcile active specs and docs, evaluate migration behavior, and archive the
   change only after full acceptance.

## Risks / Trade-offs

- **Plan can appear to rewrite PreCheck facts** → label Geo output as Plan-owned
  provider observation and preserve the exact upstream Result unchanged.
- **A high-level operation can hide added effects** → report every component and
  require a new authorization delta before broader continuation work.
- **Provider optimizations can violate least privilege** → adapters accept the
  authorized evidence components explicitly and cannot retain extras.
- **Adaptive routing can leak state across callers** → use immutable request-scoped
  route context and concurrency tests.
- **Fallback can exceed cost or provider consent** → evaluate each attempt against
  the remaining effect envelope before sending it.
- **New persistence can become an accidental Geo artifact** → keep observations in
  Plan Working State until independent addressability and retention are proven.
- **Refactoring can regress PreCheck reuse** → preserve its current public tests and
  route-context dependency semantics before switching the implementation.
- **A provider timeout can hide a billable request** → represent indeterminate
  effects explicitly.
- **A lost Tool response can cause a billable retry** → journal effect admission
  and return the original terminal or indeterminate outcome for identical replay.

## Migration Plan

The repository uses Zero Backward Compatibility for unreleased internals, but the
active PreCheck contracts remain binding.

1. Add the family package alongside `src/mediasense/geo.py`.
2. Move behavior behind the new ports with characterization tests.
3. Retain temporary compatibility exports from `mediasense.geo` while PreCheck and
   tests migrate.
4. Switch PreCheck to the family port without changing its public results.
5. Add the Geo Tool and Plan adapter.
6. Remove compatibility code only after all in-repository callers have migrated.

No stored PreCheck Result is rewritten. Existing Work remains interpretable under
its recorded provider and routing profile.

## Open Questions

No unresolved product decision blocks implementation. Exact field names, package
boundaries below the accepted family, and persistence representation may be chosen
during implementation so long as the delta specifications remain true.
