---
name: mediasense-apply
description: "Safely operates one exact MediaSense Frozen Plan through Apply preparation, Human-bound execution, recovery, Receipt reading, and whole-Run rewind. Use after Plan is frozen; not for grouping, renaming decisions, PreCheck production, or direct filesystem mutation."
---

# MediaSense Apply

Faithfully materialize one exact Human-confirmed Frozen Plan with the active
Apply Tools. Let the Agent explain and coordinate; let the Human authorize; let
the Tools own Run state, safety gates, filesystem effects, recovery, and Receipt
truth.

## Tool Host prerequisite

Proceed only when the current Honeycomb session exposes a compatible MediaSense
`0.4.x` Tool Host and both `mediasense.apply.run` and `mediasense.apply.read` are
discoverable. A CLI found in `PATH` or an MCP table present on disk is not
sufficient. If the Host is absent or incompatible, stop before preparation and
use the `mediasense` product entry Skill's local Honeycomb bootstrap; do not duplicate
setup, edit user-level Agent configuration, or perform filesystem effects
directly.

## Boundaries

- Accept organization semantics only from one immutable Frozen Plan. Never add,
  remove, regroup, rename, or choose a fallback target inside Apply.
- Resolve source facts only through the exact PreCheck Result referenced by the
  Plan and `mediasense.precheck.read`. Never inspect PreCheck databases or copy
  source hashes into the Plan.
- Use `mediasense.apply.run` for preparation, status, authorization, controls,
  recovery, and closure. Do not move, copy, link, delete, create target
  directories, or edit Run storage directly.
- Use `mediasense.apply.read` for immutable outcome evidence. A Receipt, not an
  Agent narrative, is authoritative for what happened.
- Treat trusted Human confirmation as host-provided context. Never infer,
  synthesize, replay, or place a principal assertion in ordinary Tool input.
- The active effect is `move_originals`. Copy, link, and thumbnail output are not
  available Apply profiles; preview remains Plan-owned.
- Do not request, refresh, or interpret geographic evidence. Apply consumes only
  the organization decisions already fixed by the Frozen Plan.

## Prepare and orient

Confirm the Human intends to apply this exact Frozen Plan, then call `prepare`
with a fresh `request_id`, the exact `frozen_plan` object returned by Plan seal,
`effect: move_originals`, the current root for every referenced `source_root_ref`,
and the destination parent. Do not discover a Plan-private path or construct an
artifact locator. Preparation must remain zero-media-effect.

Poll `status` until it leaves `preparing`. Explain the bounded result in terms a
Human can act on:

- Plan and prepared identities, item and operation counts;
- destination and source-root bindings;
- same-filesystem rename or verified cross-filesystem route;
- metadata-preservation and content-verification profiles;
- warnings, blockers, and their stated recovery conditions; and
- the actions currently allowed by the Tool.

Do not call `execute` from `blocked`, substitute a source, invent a collision
name, or treat a warning as permission to weaken a guarantee. Explain that no
media effect has started. When the stated external condition is repaired without
changing prepared semantics, call `resume` and inspect the newly observed
status. Source mismatch or unsafe binding that changes the operation set returns
to a new PreCheck Result and, where semantics can change, a new Frozen Plan.

## Obtain exact Human authorization

When status is `ready_for_authorization`, present the exact `run_ref`, prepared
revision, prepared content identity, effect, destination, route, operation
counts, and consequential warnings. State that authorization can move originals
and that an accepted response is not proof of completion.

Only after the Human confirms that exact prepared content, call `execute` with a
fresh request ID and the unchanged coordinates. Pass confirmation through the
trusted host context. If any coordinate changed, inspect the current status and
ask again; never adapt an old confirmation.

## Observe and control

Continue through `status`; do not infer progress from elapsed time or an
accepted control response.

- `executing`: report bounded progress. Offer `pause` or `cancel` only when the
  Human requests intervention.
- `paused`: explain that no new effects are issued and use `resume` only for the
  same prepared content.
- ordinary `needs_attention`: report completed, failed, refused, remaining, and
  indeterminate facts separately. Resume only after the returned recovery
  condition is verifiably satisfied; otherwise offer cancellation.
- metadata-loss `needs_attention`: obtain the complete Run-owned, bounded,
  content-identity-bound disclosure. Explain the exact discrepancy set. Only a
  new `execute` confirmation for the new prepared identity may accept it;
  `resume` cannot.
- source drift, root rebound, target collision, wrong volume, or ambiguous
  recovery: do not retry blindly. Preserve completed facts and route the issue
  to the owning stage or Human.
- `cancel`: explain that completed effects are not automatically reversed.
  After authorization, wait for an immutable incomplete Receipt.
- `failed` or an indeterminate effect: never describe the Run as complete;
  expose possible effects and takeover limits exactly as status reports them.

## Read the Receipt

At `closed`, call `mediasense.apply.read` with the exact `receipt_ref`. Start
with `inspect`, then use bound cursors to traverse operations, exceptions,
metadata discrepancies, or created directories only as needed. Report
completion independently from closure, include every exception, and keep the
Receipt identity discoverable.

Treat a structured Apply Read error as the complete public outcome. Do not expect
or interpret `ReceiptError`, storage paths, segment names, or schema exceptions;
report the returned code and recovery boundary instead.

## Whole-Run rewind

Rewind is available only when the Human requests it, the Receipt's window is
still open, and `prepare` can verify the actual completed set and original
locations. Prepare from the exact Receipt, explain the reverse impact and new
prepared identity, and obtain fresh Human confirmation before `execute`.

Never edit the original Receipt, guess around an occupied original location, or
present rewind as guaranteed merely because a deadline has not expired. Read
the new Receipt after closure; both forward and reverse Receipts remain history.

## Completion

Report the Frozen Plan, Run, prepared identity that was authorized, selected
effect and route, completion/closure, Receipt, exceptions, recovery facts,
accepted metadata discrepancies, and any remaining upstream or Human action.
Distinguish requested, accepted, executing, needs-attention, and closed states.
