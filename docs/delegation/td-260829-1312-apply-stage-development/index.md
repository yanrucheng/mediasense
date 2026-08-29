---
id: "td-260829-1312-apply-stage-development"
title: "MediaSense Apply Stage Interactive Development"
type: delegation
status: active
created: 2026-08-29
updated: 2026-08-29
timezone: "Asia/Shanghai"
parent: "index-delegation"
depends-on:
  - "td-260828-2131-apply-stage-design"
  - "design-260829-0038-apply-reference-handoff"
  - "spec-260829-0050-apply"
superseded-by: ""
---

# MediaSense Apply Stage Interactive Development

## Shared purpose and intended use

Give a new independent interactive Codex Agent a dedicated workline and Git worktree in which it can close the two Apply activation gates, obtain Human review of activation, and then implement and verify the first `move_originals` vertical slice without entering PreCheck or Plan implementation ownership.

The package supports one closing judgment: whether MediaSense can faithfully turn one exact Frozen Plan into authorized, recoverable, non-overwriting filesystem effects and an immutable, completely accounted Apply Receipt, with every remaining limitation stated honestly.

## Scope

- Deliver the complete recipient task as the initial user message in a new interactive Codex TUI, never TraeCLI or a non-interactive executor.
- Develop in the isolated branch `work/apply-stage-260829` and worktree `/Users/chengyanru/repos/personal/mediasense-apply-stage`.
- Begin with the activation-gate evidence; do not activate the review contract or claim production readiness until the Human reviews both gates.
- Use only controlled temporary fixtures for filesystem effects unless the user separately authorizes a precisely bounded real-media test.
- Keep the current main workspace and the PreCheck and Plan development worktrees untouched, except for the paired raw-result writeback after explicit user confirmation.
- Leave implementation structure, experiment design, and slice decomposition open while preserving the agreed product, authority, safety, and evidence invariants.

## Confirmed starting facts

- `team:mediasense` is the active virtual Team, with short name `MediaSense`, workspace route `/Users/chengyanru/repos/personal/mediasense`, and `direct-write` result mode.
- Apply product behavior has converged on one mutable Apply Run, one immutable Apply Receipt, `mediasense.apply.run`, and `mediasense.apply.read`.
- The reference handoff and formal contract are review candidates, not active contracts or production runtime behavior.
- The current Apply review artifacts pass 20 contract tests; `src/mediasense` has no Apply runtime implementation.
- Two activation blockers remain: a Result-scoped Apply-grade Source Item verification basis, and executable supported-platform evidence for cross-filesystem byte and declared metadata preservation including the block-and-reauthorize path.
- PreCheck and Plan have independent, uncommitted development work in separate worktrees. Apply must integrate only through public handoff contracts and must not edit their internal state or branches.
- MediaSense is not in production and retains Zero Backward Compatibility. AI Album is historical evidence rather than a format or runtime dependency.

## Unresolved questions and checkpoints

- If the current public PreCheck Result cannot satisfy the source-binding gate, the recipient must preserve a consumer-side failing test or equally precise evidence and return the smallest upstream contract requirement; it must not repair the PreCheck implementation in this worktree.
- Any experiment requiring a mounted disk image, removable volume, privileged operation, or non-temporary user data requires a new explicit user authorization before the effect.
- The Human must explicitly accept activation before the recipient changes Apply contract status from `review` to `active` or starts production-grade mutation runtime work.
- A proposed relaxation of cross-filesystem guarantees, source-verification strength, no-overwrite behavior, or Human authorization binding must stop for user review rather than being treated as an implementation choice.
- The Human must explicitly confirm the final return before the recipient writes the paired raw result.

## Closing and acceptance criteria

- The independent worktree and branch contain all Apply implementation and test changes; the other stage worktrees and original media remain untouched.
- Both activation gates are either closed with executable, inspectable evidence and Human acceptance, or remain explicitly blocking with a minimal reproducible gap; no mock is presented as platform evidence.
- After activation approval, the `move_originals` vertical slice consumes an immutable Frozen Plan and public PreCheck evidence, prepares a deterministic operation set without media effects, binds trusted Human authorization to exact prepared content, applies only authorized non-overwriting effects, recovers by observing facts after interruption, and publishes one immutable Receipt with complete accounting.
- Safety, idempotency, concurrency, journaling, recovery, and Receipt integrity are enforced by deterministic Tool/runtime code rather than Agent or Skill compliance.
- Tests cover the applicable contract acceptance scenarios using controlled fixtures, and the final report distinguishes implemented behavior, platform evidence, deferred profiles, known gaps, and migration judgments.
- No commit, merge, push, original-media mutation, or final result writeback occurs without the corresponding explicit user authorization.

## Request and result inventory

| Request | Recipient | Delivery shape | Result | Return mode |
| --- | --- | --- | --- | --- |
| [01-request-mediasense](01-request-mediasense.md) | `team:mediasense` | `user-interactive` | [01-result-mediasense](01-result-mediasense.md) | `direct-write` |

## Material handoff evidence

- 2026-08-29 13:12 Asia/Shanghai — The user accepted the reviewed development principles, the activation-gated `move_originals` objective, a new independent Apply development Agent, and continued delivery.
- 2026-08-29 13:12 Asia/Shanghai — The user required the new workline to run an interactive Codex Session rather than TraeCLI.

