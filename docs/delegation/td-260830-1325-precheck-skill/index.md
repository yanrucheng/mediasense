---
id: "td-260830-1325-precheck-skill"
title: "MediaSense PreCheck Skill Completion"
type: delegation
status: active
created: 2026-08-30
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "index-delegation"
depends-on:
  - "design-260823-1918-mediasense-foundation"
superseded-by: ""
---

# MediaSense PreCheck Skill Completion

## Shared purpose and intended use

Close the missing user-facing `mediasense-precheck` Skill after the PreCheck runtime and contracts have stabilized. The result will support one judgment: whether an Agent can correctly scope, start, supervise, challenge, and hand off PreCheck work without duplicating Tool authority or weakening safety.

## Scope

- Recipient: `team:mediasense` through its local workspace route.
- Engagement: user-interactive in a dedicated cmux workspace.
- Deliverables: one repository-local Skill, its minimal UI metadata, a focused OpenSpec change, realistic behavioral validation, and an evidence-backed completion report.
- Excludes reopening or redesigning PreCheck runtime, public contracts, Plan, or Apply unless a real contradiction is first reported to the user.

## Confirmed starting facts

- The repository currently contains `mediasense-plan` and `mediasense-apply` Skills but no `mediasense-precheck` Skill; Git history shows none was previously committed.
- Foundation defines three user-facing Skills and requires a Skill after stable Tool/runtime semantics.
- The omission arose when the original Slice 1 delegation was expanded interactively to the whole PreCheck stage without updating its completion checklist.
- PreCheck Run, Read, Result, orchestration, source verification, and confirmed coordinate-geocoding contracts are implemented on current `main`.
- The Skill must guide Agent judgment and interaction; deterministic I/O, state, authorization enforcement, and safety remain Tool-owned.

## Unresolved questions and checkpoints

- Which user requests should activate the Skill, and which belong directly to Plan or Apply?
- How should the Skill help a user choose Dataset boundary, evidence/compression profile, and optional geocoding without freezing replaceable implementation methods?
- Which Run states require explanation, user choice, retry, pause, cancellation, or reopening?
- What realistic interaction scenarios are sufficient to validate the Skill's decisions rather than merely its file syntax?
- The recipient must discuss these questions with the user before implementation and wait for confirmation.

## Closing and acceptance criteria

- The Skill has a stable purpose and does not become a duplicate contract, runtime authority, or fixed reasoning script.
- It correctly uses exact PreCheck Run/Read semantics, preserves source-read-only and local-first boundaries, and scopes coordinate geocoding confirmation narrowly.
- It handles success, partial/blocked results, local failures, pause/resume/cancel, repeated compression, and handoff to Plan.
- It distinguishes internal methods from public invariants and does not expose SQLite, cache layout, hashes, models, or algorithms as permanent user-facing semantics.
- Skill structure validation and independent realistic behavioral checks pass.
- OpenSpec and repository quality gates pass, and no unrelated implementation is modified.
- Final result writeback waits for explicit user acceptance.

## Request and result inventory

| Request | Recipient | Result | Status |
| --- | --- | --- | --- |
| [01-request-mediasense.md](01-request-mediasense.md) | `team:mediasense` | [01-result-mediasense.md](01-result-mediasense.md) | awaiting interactive completion |

## Material handoff evidence

- 2026-08-30 13:25 Asia/Shanghai — The user identified the missing PreCheck Skill and requested a dedicated interactive Agent to close the gap with original development context.
- 2026-08-30 13:25 Asia/Shanghai — Repository and Git history confirmed that Plan and Apply Skills exist, while no PreCheck Skill was ever committed or deleted.
- 2026-08-30 13:25 Asia/Shanghai — Created non-focusing workspace `95ECE731-DDF1-478C-B1F2-D6E835270753` with terminal surface `E9CF998C-59AC-45E7-9911-FE126BA481FA` in the invoking window; direct entry: `cmux://workspace/95ECE731-DDF1-478C-B1F2-D6E835270753/surface/E9CF998C-59AC-45E7-9911-FE126BA481FA`.
- 2026-08-30 13:25 Asia/Shanghai — Verified the MediaSense cwd, ordinary interactive Codex UI, unchanged original focus, exact 3,518-character payload delivery, and recipient acknowledgement of Skill/Tool/Result authority boundaries before read-only investigation.
