## Why

Frozen Plan identifies selected Result-local Source Items, but Apply cannot yet
prove that bytes at the rebound source location are still the bytes PreCheck
validated. The missing handoff is a compact, replaceable verification
observation—not a new source identity or Dataset-wide snapshot.

## What Changes

- Extend the PreCheck Read Contract so eligible Source Items may expose a
  sealed verification observation with profile, value, byte length, status,
  limitations, and provenance, while preserving their source-root-relative
  locator.
- Add `source_root_ref` to each sealed Source Item locator so Apply can bind
  that locator to an explicitly verified current source root without turning
  the Dataset identity into a path or limiting a Result to one root.
- Produce and project a first SHA-256 full-content profile for Source Items
  selected for Apply-grade validation. The profile remains replaceable and is
  not Source Item identity.
- Require Plan to freeze only `result_ref` and selected `source_item_ref`; Apply
  will resolve the observation through PreCheck Read and re-read those selected
  source bytes before effects.
- Specify fail-closed Apply behavior for unknown profiles, missing observations,
  unsafe source-root binding, and mismatched bytes without modifying the Apply
  implementation in this worktree.

## Capabilities

### New Capabilities

- `precheck-source-verification`: Defines Result-local source verification
  observations, their PreCheck authority, and the downstream Apply preflight
  obligation.

### Modified Capabilities

None. This is an independently reviewed additive proposal to the existing
PreCheck Read Contract.

## Impact

Affected areas are the formal PreCheck Read prose/schema, Result assembly and
seal validation, source-validity producer/state, conformance tests, Foundation
handoff guidance, implementation design, and migration ledger. Plan and Apply
worktrees are not modified; Apply implementation remains an explicit follow-up.
