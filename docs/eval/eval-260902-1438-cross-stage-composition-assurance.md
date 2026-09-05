---
id: "eval-260902-1438-cross-stage-composition-assurance"
title: "Cross-Stage Production Composition Assurance Review"
type: eval
status: active
created: 2026-09-02
updated: 2026-09-02
timezone: "Asia/Shanghai"
parent: "index-eval"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
  - "spec-260826-1546-precheck-read"
  - "spec-260827-1915B-plan-work"
superseded-by: ""
tags: ["composition", "cross-stage", "runtime", "acceptance"]
---

# Cross-Stage Production Composition Assurance Review

## Purpose and boundary

This review asks whether MediaSense can entrust independently developed stages
to compose correctly in the shipped product without requiring every development
Agent to reconstruct the whole repository. It was triggered when an installed
`mediasense.plan.work` `create` request returned
`host_invalid_request: 'PrecheckReadTool' object is not callable` for a valid,
Plan-ready PreCheck Result.

The review covers material boundaries among active Tool contracts, internal
ports, the Dataset-bound composition root, the MCP Host, packaged release
evidence, and test doubles. It does not reassess PreCheck evidence quality, Plan
grouping policy, Apply filesystem semantics, the Hong Kong media, or any live
provider. No PreCheck or media operation was run.

## Governing relation

The relevant development and release relation is:

```text
reviewed stage semantics and handoff examples
  -> public JSON Tool contracts
  -> independently developed provider and consumer components
  -> one production composition root
  -> RuntimeHost and MCP dispatch
  -> installed release artifact
  -> user-visible stage continuity
```

The existing development method establishes the first three terms well enough
to permit parallel work. Product correctness additionally depends on every
material edge from the real provider through the installed Host. A downstream
mock that accepts the right JSON values is necessary evidence, but it cannot
prove that the real provider exposes the invocation form used by the consumer.

## Incident evidence

The exact Plan request reached the installed Host and failed before
`SQLitePlanStore.create` could create a Working State. The source and installed
package had the same incompatible connection:

- `PrecheckReadTool` exposes `read(request)`.
- `PlanWorkTool` declares `PrecheckReader` as a callable and invokes
  `self.precheck_read(request)` during `create`.
- `DatasetRuntime` supplies the `PrecheckReadTool` object itself to
  `PlanWorkTool`.
- Apply separately declares an object-shaped `PrecheckReadBoundary` and calls
  `.read()`, while `ResultSourceSetResolver` accepts the callable shape.

The exception occurs before work identifiers are allocated and persisted, so
the failed request created no Working State, revision, or Frozen Plan and made no
media change. The exact PreCheck Result remains the correct upstream authority.

## Why existing assurance passed

Plan was implemented against the reviewed PreCheck Read Mock before the real
PreCheck Read implementation and production composition root were assembled.
This was an intentional parallel-development strategy, not a missing semantic
dependency: the Plan specification explicitly depends on PreCheck Read and the
Plan development request required that contract and Mock.

The assurance gap appeared later:

- Plan unit tests use callable readers.
- The cross-stage test wraps the real `PrecheckReadTool` in a
  `RecordingPrecheckRead` that exposes both `__call__` and `.read()`, a larger
  surface than the production provider.
- Runtime tests prove that all Tools can be constructed and discovered but do
  not call Plan `create` through `RuntimeHost`.
- The clean-install MCP smoke test opens a Dataset, lists all Tools, and calls
  PreCheck Run status; it does not execute the PreCheck-to-Plan edge.
- Ruff and JSON Schema validation do not check Python dependency compatibility,
  and the project currently has no enforced static type checker.

The tests therefore proved semantic handoff behavior and package discovery, but
not the exact shipped connection that failed.

## Rival explanations and judgment

| Explanation | Evidence | Judgment |
| --- | --- | --- |
| The Plan request or organization preferences were invalid | The failure is a Python callability error before Tool-level Result validation | Rejected |
| The installed 0.3.0/0.4.x mismatch alone caused the failure | A stale session is a separate compatibility risk, but repository and installed 0.4.0 source retain the same connection | Insufficient |
| The public PreCheck or Plan JSON Schema is wrong | The values and stage semantics agree; JSON Schema cannot specify a process-local Python invocation form | Rejected as primary cause |
| One developer missed one method name | This explains the immediate defect but not why unit, handoff, runtime, and installed smoke evidence all accepted it | True but not sufficient |
| Development lacks a production-composition closure rule | Mock-driven parallel development, permissive test doubles, construction-only runtime tests, and one-Tool release smoke jointly leave the real edge unproved | Best-supported explanation |

The high-level finding is therefore **a bounded but systemic assurance gap**:
MediaSense has cross-stage semantic contracts, yet previously had no explicit
invariant requiring each material edge to execute through the shipped production
composition before integrated readiness was claimed.

## Cross-stage assurance matrix

| Material edge | Semantic authority | Production owner | Existing evidence | Review status |
| --- | --- | --- | --- | --- |
| Dataset Open -> Dataset runtime construction | Dataset Open contract and runtime configuration | `RuntimeHost` / `DatasetRuntime` | Real open, reopen, construction, and installed smoke | Proven for current local boundary |
| PreCheck Read -> Plan create and candidate work | PreCheck Read and Plan Work contracts | `DatasetRuntime` | Shared port, constructor check, real `RuntimeHost` success, and installed-wheel MCP success | Proven for current local boundary |
| PreCheck provider acquisition -> immutable Result and Read Geo summary | PreCheck Run and Read contracts | `PrecheckOrchestrator` / `ReverseGeocodeProducer` | Frozen-batch authorization, provider/network spies, Result projection, and summary equivalence tests | Proven for the current PreCheck boundary |
| PreCheck Read -> Apply Source Set expansion | PreCheck Read, Frozen Plan, and Apply contracts | `ApplyRunTool` | Shared port, real components, and `RuntimeHost` handoff test | Proven for current local boundary |
| Plan Frozen Plan -> Apply preparation | Frozen Plan and Apply contracts | Plan publisher and `ApplyRunTool` | Real `RuntimeHost` create/update/seal/prepare chain stops before authorization with no media effect | Proven for current local boundary |
| Tool failure -> Host error presentation | Tool contracts plus Host transport boundary | MCP Host | Envelope errors remain `host_invalid_request`; unexpected failures are sanitized as `host_operation_failed` with a correlated local diagnostic | Proven by focused MCP handler tests |
| Skill release -> active Tool Host | MediaSense product entry Skill and release metadata | Client integration plus MCP Host | The isolated installed-wheel smoke now compares the initialized MCP server version with the installed CLI and requires every discovered Tool to advertise a contract identity and digest | Proven for a fresh supported client session; a pre-existing session still requires restart |

The matrix is deliberately limited to edges whose failure can change stage
continuity, authority, durable state, external effects, or release claims.
Ordinary helper calls do not become architecture entities merely because they
cross modules.

## Engineering decisions

### Keep public semantics where they are

The existing Tool JSON contracts remain authoritative for cross-stage values,
effects, authority, lifecycle, and failures. This incident does not justify a new
public Tool, schema, registry, service, coordination Agent, or fourth stage.

### Give each local port one shape

The PreCheck Read local port should use one structural, object-shaped boundary
matching the real public Tool: a named `read(request)` operation. Plan, Apply,
and stage-neutral Source Set interpretation should depend on that same minimal
port. Its authoritative code home should remain adjacent to the existing public
PreCheck Read boundary and be exported for consumers; a general protocol registry
would add no independent authority or lifecycle.

MediaSense is not in production and retains Zero Backward Compatibility. The
callable and object-shaped variants should therefore be consolidated directly;
no dual-form adapter, deprecation shim, or version router is warranted. The
method name is an internal replaceable choice, not a new product promise.

### Assign composition compatibility explicitly

The production composition root owns the compatibility of the concrete objects
it assembles. Stage Tools retain their own business semantics. Development Agents
need to read the contracts they consume, not every stage implementation; the
composition owner must close the executable connection after parallel work lands.

### Require shared conformance evidence

The real `PrecheckReadTool` and every reader test double should run against one
minimal port conformance suite. Test doubles must not expose an invocation form
that the production implementation lacks unless a test specifically evaluates a
separate adapter that also exists in production.

### Layer release tests by risk

Confidence should be gained at the cheapest layer that can detect the failure:

1. Schema and semantic tests continue to cover request/result behavior and stage
   lifecycle exhaustively.
2. Port conformance tests cover production implementations and test doubles.
3. Fast, in-process `RuntimeHost` vertical tests execute every material
   cross-stage edge with real internal components and temporary state.
4. A small installed-wheel MCP smoke executes each Host dispatch branch at least
   once and one successful zero-effect path for each material stage handoff.

This does not require every Tool action, live provider, large fixture, or media
mutation in the release smoke. Plan `create` and Apply `prepare` are particularly
valuable because they cross boundaries without changing source media.

### Preserve truthful failure ownership

`host_invalid_request` should be reserved for an invalid MCP/Host envelope.
Tool-declared validation stays in the Tool's schema-valid error result. An
unexpected implementation or composition exception should produce a distinct,
sanitized Host operation failure with diagnostic correlation, never imply that
the user's valid business request was malformed.

### Verify the active Host, not PATH

Compatibility decisions should use the current MCP server version and advertised
Tool contract digests. The CLI found in `PATH` is installation evidence only. If
the client cannot expose the active server identity, readiness is unverified; no
new MediaSense status Tool is justified while standard MCP metadata already owns
the information.

## Business judgment

No grouping, evidence, Apply, cost, privacy, or authorization policy needs Human
reconsideration. The intended product semantics are already clear: a valid,
Plan-ready Result must enter Plan without rerunning PreCheck, and Plan creation
must not modify media. Correcting the composition and assurance gates preserves
that intent.

The incident is a MediaSense regression against its active Plan contract. Against
AI Album it is `not_comparable`, because AI Album did not expose independently
versioned PreCheck and Plan stages. The architectural separation remains an
intentional improvement; the missing executable closure is not.

## Priority and acceptance boundary

The incident-class repair completed:

1. PreCheck Read now has one object-shaped local port used by Plan, Source Set
   interpretation, and Apply, with constructor-time rejection of incompatible
   wiring.
2. Reader doubles use the same shape as the production implementation.
3. A real `RuntimeHost` test covers PreCheck Result -> Plan create and another
   covers Plan create/update/seal -> Apply prepare with no media effect.
4. Host envelope failures and unexpected operation failures are distinct.
5. Focused tests, the default non-live suite, OpenSpec validation, Ruff, and an
   isolated installed-wheel MCP Plan-create smoke passed on 2026-09-02.
6. The complete default suite passed with 582 tests and 16 explicitly excluded
   `local_fixture` or `scale` tests; the installed-wheel smoke also verified the
   active MCP server version and every advertised Tool contract digest.

The complete RuntimeHost handoff test also exposed and closed a neighboring
composition defect: observing Apply status could reschedule a preparation that
had already reached `ready_for_authorization`, producing an unhandled background
thread failure. Runtime scheduling now starts only work whose returned or target
state is `executing`; preparation and status remain zero-effect observations.

The immediate fix is accepted only when the same exact Result can create a
Working State through a compatible newly started Tool Host without rerunning
PreCheck, and the failure-path test proves that no Working State or media effect
occurs when the upstream read is unavailable.

## Uncertainty, stopping, and reopening

This work did not mutate the failed Dataset, rerun its PreCheck, install over the
machine's active CLI, or restart the original Agent session. Verification used
temporary generated media and isolated Dataset workspaces. The current source
and an isolated `0.4.0` wheel pass the repaired path; the original session cannot
benefit until a separately authorized release installation and fresh Tool Host
are used.

The architecture review stops here because every currently material cross-stage
edge has an authority, owner, evidence classification, and next acceptance gate.
Reopen it when a new stage, transport, composition root, public capability, or
release path is introduced; when a test double gains behavior absent from its
production provider; or when a promised path lacks one deterministic production-
composition proof.
