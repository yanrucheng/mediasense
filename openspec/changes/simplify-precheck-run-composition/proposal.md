## Why

Plan can discover that part of an immutable PreCheck Result needs finer preparation. The current start request cannot state the selected inputs and complete local compression settings, and the public reader cannot supply a repeatable request or prove how old Source Items correspond to new ones. Reusing internal computation alone does not close that user journey.

The accepted [basic model](../../../docs/model/model-260913-1408-precheck-basics.md) already supplies the necessary entities: changed requirements create another ordinary Run, which publishes another immutable Result; Profile is a configuration value.

## What Changes

- Extend ordinary `precheck.run start` with explicit `source_set` and complete `profile` values. Omission continues to mean current Dataset defaults, never inheritance from `prior_result_ref`.
- Freeze local compression parameters and the identity of other effective preparation settings. A mismatch refuses a new request rather than silently replacing its assumptions.
- Apply overrides only to explicitly selected sources. Other parameters remain as declared; derived groups may change through actual dependencies. This does not require a purely threshold-driven algorithm or a fixed number of groups.
- Add an optional preparation view to existing `precheck.read review`, and optional direct-successor correspondence to existing `resolve`.
- Extend Source Set with one Result-local `profile_scope` selector so a large saved selection can be reused without returning all its members. The selector addresses a position in a frozen configuration value, not a new entity.
- Keep Plan Work bound to one Result. The Agent uses existing Work operations to retain justified decisions in a new Work and obtains confirmation for its new organization.
- Specify dependency-based reuse, scope boundaries, recovery, immutable retention and end-to-end acceptance. No production implementation is part of this design milestone.

## Capabilities

### New Capabilities

None. No new public Tool, Skill, Run kind, Profile management service or migration entity.

### Modified Capabilities

- `precheck-run-orchestration`: explicit ordinary Run input/configuration, bounded local preparation, dependency reuse and immutable publication.
- `precheck-result-read`: preparation readback, bounded saved-scope resolution and evidence-backed correspondence.
- `plan-agent-workflow`: preserve semantic continuity across a deliberate new Result through the existing public boundaries.

## Impact

Current authority remains `docs/spec/contract/`. This OpenSpec proposes the changes; it does not activate or modify that contract. The implementation Agent will put Processing Profile definitions under Run and Source Set/correspondence semantics under Read, with consistent schema fragments and packaged snapshots.

Implementation affects Run validation/snapshots, orchestration, compression inputs, producer dependencies, Result sealing/reading, Plan Skill guidance and Host integration. Existing Plan Work, Frozen Plan and Apply exchange shapes remain sufficient. The separate Plan preview development is not redefined by this change.

This package contains the development design, proposed spec deltas, ordered tasks and acceptance criteria. Machine schemas, executable examples, validators, tests and production implementation are deliverables for the assigned implementation Agent. This planning task stops after the OpenSpec is ready; it does not perform those development tasks or deploy anything.
