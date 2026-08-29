## Why

PreCheck's producers and durable records are individually implemented, but the
Run entry point does not yet coordinate them into a resumable Result-producing
execution. Tests that manually invoke each producer cannot prove the public Run
lifecycle is operational.

## What Changes

- Add one private Run orchestrator behind `mediasense.precheck.run`; it is
  coordination code, not a service, Agent, public entity, or plugin system.
- Make `start` and `resume` persist their state transitions and return
  immediately; the existing host/worker boundary invokes private
  `advance(run_ref)` so status and control remain available during long work.
- Begin from an already source-bound Working Run, close or resume accounting,
  execute only producers enabled by the persisted Run configuration, and use
  existing Work, lease, Artifact, and resource-budget mechanisms.
- Convert localized producer failures into explicit Result observations and
  accounting outcomes while allowing independent work to continue.
- Stop at pause, confirmation, cancellation, blocking, or interruption; resume
  by re-deriving demand and reusing committed Work rather than replaying a
  procedural phase log.
- Have the internal worker automatically build, validate, seal, and publish one
  immutable Result when closure succeeds.
- Replace manual end-to-end assembly tests with Run-driven coverage, including
  repeated compression targets and fake-provider confirmation.

## Capabilities

### New Capabilities

- `precheck-run-orchestration`: Defines the internal execution semantics behind
  the existing Run lifecycle and its automatic Result publication.

### Modified Capabilities

None. The public Run actions and Result/Read entities remain unchanged.

## Impact

Affected code is limited to PreCheck Run persistence/control, an internal
orchestration module, existing producer/result adapters, and PreCheck tests.
There is no Plan or Apply implementation change and no new public Tool action.
