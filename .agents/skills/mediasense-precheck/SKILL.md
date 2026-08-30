---
name: mediasense-precheck
description: "Prepares or re-prepares a MediaSense Dataset through PreCheck: run initial compression, explain costs, diagnose unsatisfactory evidence, recover long Runs, handle bounded reverse-geocode confirmation, interpret Results, and hand one exact result_ref to Plan. Use before Plan or when Plan needs new upstream evidence; not for Plan grouping or naming, or Apply filesystem execution."
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

## Begin without an arbitrary count target

Learn enough about the Dataset and intended Plan use to select a suitable
available initial configuration, then start through `mediasense.precheck.run`.
Do not ask the user to guess a desired Evidence count or treat one universal
count as the definition of good compression. The useful frontier depends on the
Dataset; its size is an observed result to review alongside coverage, variation,
review burden, local cost, and residual uncertainty.

Use the exact `dataset_ref` supplied through the host's supported Dataset
boundary. If the user supplies only a filesystem path and no such boundary is
available, do not scan or register it directly; explain that onboarding is not
exposed by the current PreCheck Run Tool.

Keep methods open. Do not prescribe clustering, persistence, hashing,
extraction, decoding, models, thresholds, directory layouts, or a fixed profile
as permanent method. Use only configuration choices the Tool host actually
supports, and never invent request fields to express a preference.

State before starting that external work is disabled by default. Do not enable
remote models, uploads, online maps, or billable services as an optimization.

## Explain cost when it becomes knowable

At each Tool-exposed checkpoint, separate observed cost from defensible
estimates and unknowns. Include what is material among:

- completed, reused, remaining, and blocked local work and resource pressure;
- the compression frontier and represented population;
- the exact pending logical-query count for the optional coordinate lookup;
- the expected downstream Evidence-review and user-attention burden; and
- after publication, actual provider requests, fallback or retries, and known
  or unknown billable calls from the Result execution boundary.

Do not turn Source Item counts into Evidence counts, logical queries into
provider requests, or an unavailable estimate into a promise. The purpose is to
let the user judge whether the observed compression and prospective cost are
reasonable, not to force a target before the Dataset has been processed. Claim
an exact frontier count only after `mediasense.precheck.read` reports it or a
complete traversal accounts for every page.

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
- on insufficient workspace capacity, report only the required capacity and
  retained work the Tool actually exposes, and resume only after the reported
  condition is satisfied; and
- preserve a corrupt or unsupported item's explicit outcome while unrelated
  work continues when the Tool says it can.

Do not retry blindly, bypass a blocker, edit state, or turn a recoverable
condition into a claim of completion. When the returned choices require a
material Human decision, explain their consequences and ask. If the Tool does
not expose a verifiable recovery condition or retained-work fact, call it
unknown rather than guessing.

## Keep the external exception exact

The sole current online exception is reverse geocoding after compression has
produced a normalized, deduplicated, frozen coordinate set. When the Tool pauses
for it, proceed only if the returned confirmation clearly identifies that exact
contract-bound exception; otherwise stop and surface the ambiguity.

1. Show the exact Tool-reported number of logical queries and the coordinate-only
   scope.
2. Explain that the coordinates themselves leave the local boundary and may
   reveal visited places. State that provider, precision, retention,
   jurisdiction, request amplification, and price are unknown unless the Tool
   reports them.
3. Explain that media, renditions, features, prompts, and ordinary metadata are
   not authorized to leave the local boundary.
4. Obtain the Human's matching proceed or skip decision, then use only the
   supported Tool transition. Never synthesize or reuse confirmation.

Skipping continues without this optional evidence. Tell the user it will be
absent, but claim a durable qualification only if the immutable Result returns
one. Retry and fallback never widen the frozen authorized set.

## Diagnose before revising compression

If the user dislikes the observed frontier, first ask what is wrong with its
content or distribution. A large or small count alone is not evidence of a bad
Result. Inspect the exact Result through `mediasense.precheck.read` and compare
the complaint with representation bases, coverage, outliers, boundaries,
qualifications, processing provenance, and cost.

Identify the narrowest producer, profile choice, parameter, or upstream
evidence gap that plausibly caused the problem. Explain how a proposed change
could affect coverage, fragmentation, over-merging, local work, later model
cost, and user attention. Apply only a revision that the current Tool host can
actually configure; otherwise report the capability gap.

Start the revised work as a successor from the exact prior `result_ref` through
`mediasense.precheck.run`. Each run publishes a distinct immutable Result and
the Tool decides which still-valid work can be reused. If successive revisions
happen to produce 500, then 3, then 200 entry Evidence objects, those numbers are
observations of three configurations—not requested output targets, in-place
rewrites, or proof that any one count is inherently correct.

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
- diagnose and propose a supported profile or parameter revision;
- request directed upstream rebuild through the supported Tool boundary when
  available, otherwise expose that limitation; or
- retain an explicit partial or blocked Result when more work is unavailable or
  not worth its cost.

A valid partial Result may proceed when readiness is `plan_ready`; explain the
material qualifications first. A Result whose readiness is `blocked` is not
Plan-ready: present the blocking evidence and ask the Human whether to continue
preparation, request directed rebuild or other evidence, or stop.

Stopping a completed blocked Result means retaining it and taking no further
action. `cancel` applies only to a mutable Run when the Tool says it is allowed;
do not try to cancel an already published Result. Continuing from a completed
Result starts a successor by supplying that Result's exact `result_ref` as the
new start request's `prior_result_ref`; it is not `resume`.

## Hand off to Plan

When the Human proceeds with a valid, `plan_ready` Result, hand Plan the exact
immutable `result_ref` together with material qualifications. Plan resolves all
PreCheck facts and Evidence through `mediasense.precheck.read`; never hand it a
PreCheck database, cache, workspace path, copied digest, or mutable Run.

Finish by distinguishing what completed, what remains uncertain, which external
effects were observed, and which new Result supersedes which prior Result for
the user's current purpose. Do not claim that Plan or Apply has begun.
