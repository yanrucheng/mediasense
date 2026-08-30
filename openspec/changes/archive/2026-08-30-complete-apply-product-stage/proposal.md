## Why

The active Apply runtime completes the first `move_originals` profile, but the
user-facing Agent workflow is not yet packaged as a repository Skill and the
remaining legacy copy/link claims and production-support boundaries are not
closed with current evidence.

## What Changes

- Add a `mediasense-apply` Skill that guides one exact Frozen Plan through
  preparation, Human-bound authorization, execution controls, Receipt reading,
  and whole-Run rewind without owning state or effects.
- Add fixture-driven Skill workflow acceptance tests over the real Apply Tool
  boundary, including blockers, effect-boundary drift, partial failure, resume,
  Receipt reading, and rewind.
- Record a legacy-first copy/link disposition from AI Album c90. Keep
  `move_originals` as the only active materialization profile: c90 had no
  user-facing original-copy implementation, while its relative symlink mode was
  a preview convenience now superseded by Plan and lacks an accepted durable
  lifecycle.
- Harden and test filesystem error classification, volume identity changes,
  ACL refusal, journal/Receipt recovery, and controlled large-file throughput.
- Update the active Apply contract, activation evidence, README, and migration
  ledger with the certified platform matrix and explicit deferred scope.

## Capabilities

### New Capabilities

- `apply-skill-workflow`: Defines the non-authoritative Agent/Human workflow for
  operating the active Apply Tools.

### Modified Capabilities

- `apply-stage-runtime`: Adds production-boundary requirements for structured
  storage faults, volume rebinding, and controlled scale evidence.

## Impact

- Adds `.agents/skills/mediasense-apply/` and Skill workflow tests.
- Hardens existing Apply filesystem/runtime modules without changing
  `move_originals` semantics or introducing another runtime authority.
- Updates existing Apply and migration documents and archives this OpenSpec
  change after strict validation.
- Performs no operation on user media and does not add copy, hard-link, or
  symbolic-link effects to the active contract.
