---
name: mediasense-precheck
description: "Prepares or re-prepares a MediaSense Dataset through PreCheck: choose a compression purpose, operate and recover long Runs, handle bounded reverse-geocode confirmation, interpret partial or blocked Results, and hand one exact result_ref to Plan. Use before Plan or when Plan needs new upstream evidence; not for Plan grouping or naming, or Apply filesystem execution."
---

# MediaSense PreCheck

Prepare one Dataset into an honest immutable PreCheck Result that is useful for
later reasoning. Keep heavy work economical and observable without treating
thoroughness, a particular implementation, or a large Evidence count as the
goal.

## Boundaries

- Stay in PreCheck. Plan owns final grouping, naming, disposition, and Plan-local
  inspection; Apply owns execution of one Frozen Plan and filesystem recovery.
- Perform no source, workspace, cache, database, artifact, or network I/O
  directly. Use [`mediasense.precheck.run`](../../../docs/spec/spec-260827-1915A-precheck-run/precheck-run.tool.json)
  for discovery, long work, controls, confirmation enforcement, recovery, and
  automatic publication. Use [`mediasense.precheck.read`](../../../docs/spec/spec-260826-1546-precheck-read/precheck-read.tool.json)
  for immutable Result facts and Result-local navigation.
- Treat the Tool responses and the [Run](../../../docs/spec/spec-260827-1915A-precheck-run/index.md)
  and [Read](../../../docs/spec/spec-260826-1546-precheck-read/index.md)
  contracts as authoritative. Do not invent actions or fields, copy their
  schemas into conversation, or infer state from private storage.
- Source media remains read-only. A Skill instruction, Agent statement, accepted
  request, checkpoint, or mutable Run is not a Result and grants no new effect.

## Establish the preparation purpose

Learn enough about the intended Plan decision to choose an initial compression
purpose. Balance coverage, meaningful variation, review burden, local resource
cost, and the consequence of missing evidence. Explain the intended trade-off;
do not prescribe clustering, persistence, hashing, extraction, decoding,
models, thresholds, directory layouts, or a fixed profile as permanent method.

Start through `mediasense.precheck.run`. For a changed evidence budget, changed
purpose, or directed rebuild, begin a successor from the exact prior
`result_ref` through the supported Tool boundary. Each accepted target produces
a distinct immutable Result; rely on the Tool to reuse still-valid work. A
request to move from 500 entries to 3 and later 200 is therefore two explicit
trade-off revisions, not an in-place rewrite or a reason to discard all prior
computation.

State before starting that external work is disabled by default. Do not enable
remote models, uploads, online maps, or billable services as an optimization.

## Observe and control the Run

Use `status` as the source of current state. Report the returned business
progress, reason, recovery condition, and allowed controls in terms the user can
act on. An accepted start, pause, resume, skip, or cancel request says only that
the transition was accepted; continue observing until the Tool reports a
truthful attention or terminal state.

Follow the Tool's localized recovery facts:

- after interruption, resume the same durable Run when allowed so valid
  completed work can be reused;
- treat a disconnected source as unavailable, never as proof of deletion, and
  wait for the reported compatible recovery condition;
- on insufficient workspace capacity, explain what committed work remains and
  resume only after the reported capacity condition is satisfied; and
- preserve a corrupt or unsupported item's explicit outcome while unrelated
  work continues when the Tool says it can.

Do not retry blindly, bypass a blocker, edit state, or turn a recoverable
condition into a claim of completion. When the returned choices require a
material Human decision, explain their consequences and ask.

## Keep the external exception exact

The sole current online exception is reverse geocoding after compression has
produced a normalized, deduplicated, frozen coordinate set. When the Tool pauses
for it:

1. Show the exact Tool-reported number of logical queries and the coordinate-only
   scope.
2. Explain that media, renditions, features, prompts, and ordinary metadata are
   not authorized to leave the local boundary.
3. Obtain the Human's matching proceed or skip decision, then use only the
   supported Tool transition. Never synthesize or reuse confirmation.

Skipping continues without this optional evidence and remains visible as a
qualification. Retry and fallback never widen the frozen authorized set.

## Judge the immutable Result

After publication, inspect the exact `result_ref` through
`mediasense.precheck.read`. Interpret coverage, readiness, and integrity as
independent axes and preserve qualifications, omissions, provenance, confidence,
failures, and externally observable cost.

Every accounted Source Item must remain reachable through the normal Evidence
frontier or an explicit auxiliary, excluded, unsupported, invalid, error, or
unresolved path. Do not require every Source Item to have visual Evidence and do
not silently drop exceptional items.

If evidence is insufficient for the intended decision, choose the narrowest
honest next step that can change it:

- while still deciding whether PreCheck can hand off, inspect relevant
  Result-local Evidence through `mediasense.precheck.read`; once Plan is active,
  ordinary Result-local expansion remains Plan-owned;
- propose a new compression purpose or budget;
- request directed upstream rebuild through `mediasense.precheck.run`; or
- retain an explicit partial or blocked Result when more work is unavailable or
  not worth its cost.

A valid partial Result may proceed when readiness is `plan_ready`; explain the
material qualifications first. A Result whose readiness is `blocked` is not
Plan-ready: present the blocking evidence and ask the Human whether to continue
preparation, request directed rebuild or other evidence, or stop.

## Hand off to Plan

When the Human proceeds with a valid, `plan_ready` Result, hand Plan the exact
immutable `result_ref` together with material qualifications. Plan resolves all
PreCheck facts and Evidence through `mediasense.precheck.read`; never hand it a
PreCheck database, cache, workspace path, copied digest, or mutable Run.

Finish by distinguishing what completed, what remains uncertain, which external
effects were observed, and which new Result supersedes which prior Result for
the user's current purpose. Do not claim that Plan or Apply has begun.
