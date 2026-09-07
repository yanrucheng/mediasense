---
name: mediasense-precheck
description: "Prepares or re-prepares a MediaSense Dataset through PreCheck: run initial compression, explain costs, diagnose unsatisfactory evidence, recover long Runs, handle bounded address-and-nearby-place confirmation, interpret Results, and hand one exact result_ref to Plan. Use before Plan or when Plan needs new upstream evidence; not for Plan grouping or naming, or Apply filesystem execution."
---

# MediaSense PreCheck

Prepare one Dataset into an honest immutable PreCheck Result that is useful for
later reasoning. Keep heavy work economical and observable without treating
thoroughness, a particular implementation, or a large Evidence count as the
goal.

## Tool Host prerequisite

Proceed only when the current Honeycomb session exposes a compatible MediaSense
`0.8.x` Tool Host and `mediasense.dataset.open`, `mediasense.precheck.run`,
`mediasense.precheck.read`, and `mediasense.geo.query` are discoverable. A CLI found in `PATH` or an MCP table
present on disk is not sufficient. If the Host is absent or incompatible, stop
PreCheck work and use the `mediasense` product entry Skill's local Honeycomb
bootstrap; do not duplicate setup, edit user-level Agent configuration, or claim
the current session reloaded a newly written project configuration.

## Boundaries

- Stay in PreCheck. Plan owns final grouping, naming, disposition, and Plan-local
  inspection; Apply owns execution of one Frozen Plan and filesystem recovery.
- Perform no source, workspace, cache, database, artifact, or network I/O
  directly. When the user supplies a filesystem path rather than an exact
  `dataset_ref`, first use `mediasense.dataset.open` to resolve or create the
  Dataset and report its selected workspace. Use
  [`mediasense.precheck.run`](references/precheck-run.tool.json)
  for discovery, long work, controls, confirmation enforcement, recovery, and
  automatic publication. Use
  [`mediasense.precheck.read`](references/precheck-read.tool.json)
  for immutable Result review, targeted expansion, and exact Source Set
  resolution.
- Treat the Tool responses and the linked Run and Read contract snapshots as
  authoritative for the installed release. Read the relevant snapshot when an
  exact field or action is needed. Do not invent actions or fields, copy their
  schemas into conversation, or infer state from private storage.
- Source media remains read-only. A Skill instruction, Agent statement, accepted
  request, checkpoint, or mutable Run is not a Result and grants no new effect.

## Review source scope before expensive work

The first local discovery pass may pause with
`reason.code=scope_confirmation_required`. Treat the returned inventory as Tool
facts, not a Tool judgment about what the user wants. It reports a bounded
source-relative entries view with counts, bytes, kinds, size buckets, representative
paths, and discovery limitations. Use `status.scope_path` to expand a collapsed
subtree and `status.scope_after` to continue its child list when the current
confirmation permits it.

Interpret the entries for the Human. Explain why a subtree may be a cache, derived
output, backup, index, or legitimate hidden media as Agent judgment; never claim
that a dot name or Tool statistic proves that meaning. Focus attention on
media-bearing or materially large subtrees rather than enumerating every
ordinary dotfile.

When the intended boundary is clear, submit the exact current
`inventory_fingerprint`, one `default_disposition` (`include` or `exclude`), and
only the non-overlapping source-relative subtree exceptions the Human accepted
or existing delegation permits. Inclusion authorizes only local PreCheck scope;
it does not authorize remote or billable work. Exclusion changes no source byte
and excluded discoveries remain accounted in the Result.

If the Tool reports a refreshed inventory after a source change, present the
changed facts and obtain any newly required direction. Never replay a stale
selection, generalize it to future descendants, or turn silence into consent.
An unattended caller without an exact reusable or delegated selection remains
paused before expensive work.

## Begin without an arbitrary count target

Learn enough about the Dataset and intended Plan use to select a suitable
available initial configuration, then start through `mediasense.precheck.run`.
Both PreCheck Tools use flat inputs: put `action`, the exact `dataset_ref`, and
operation parameters at the top level. Do not send a `request` wrapper or an
`operation` alias. A successor start still carries `dataset_ref` alongside `prior_result_ref`.
Do not ask the user to guess a desired Evidence count or treat one universal
count as the definition of good compression. The useful frontier depends on the
Dataset; its size is an observed result to review alongside coverage, variation,
review burden, local cost, and residual uncertainty.

Use the exact `dataset_ref` supplied by `mediasense.dataset.open`. If the user
supplies only a filesystem path, open it through that Tool and explain whether
the workspace was explicitly selected, found on the source's external volume,
or resolved from the machine-local fallback. If opening reports invalid,
incompatible, ambiguous, or unsafe higher-priority state, stop and explain the
recovery choices; do not bypass it by creating lower-priority state or scanning
the source directly.

Keep methods open. Do not prescribe clustering, persistence, hashing,
extraction, decoding, models, thresholds, directory layouts, or a fixed profile
as permanent method. Use only configuration choices the Tool host actually
supports, and never invent request fields to express a preference.

State before starting that external work is disabled until an exact Run-scoped
authorization is accepted. Credential or provider availability never grants
authority by itself.

## Explain cost when it becomes knowable

At each Tool-exposed checkpoint, separate observed cost from defensible
estimates and unknowns. Include what is material among:

- completed, reused, remaining, and blocked local work and resource pressure;
- the compression frontier and represented population;
- the exact pending logical-query count for required coordinate acquisition;
- the expected downstream Evidence-review and user-attention burden; and
- after publication, actual provider requests, fallback or retries, and known
  or unknown billable calls from the Result execution boundary.

Do not turn Source Item counts into Evidence counts, logical queries into
provider requests, or an unavailable estimate into a promise. The purpose is to
let the user judge whether the observed compression and prospective cost are
reasonable, not to force a target before the Dataset has been processed. Claim
an exact frontier count only after a complete `review` pagination reports it.

## Observe and control the Run

Use `status` as the source of current state. Report the returned business
progress, reason, recovery condition, and allowed controls in terms the user can
act on. An accepted start, pause, resume, skip, or cancel request says only that
the transition was accepted; continue observing until the Tool reports a
truthful attention or terminal state.

Treat `status` as observational: polling never starts, resumes, or reclaims a
worker. There is no public queued state. If reason.code is `suspected_stalled`,
report its required reason and use explicit `resume` only when the user already
authorized continuation; do not wait or poll as a substitute for recovery.

Keep counting domains distinct. `progress` counts terminal logical work in the
current phase, including valid reuse and finalized localized failure.
`accounting` reports Source Item coverage through status include.
Unknown counts and times are null. Do not derive a
percentage, ETA, throughput, or success promise from counts across phases.
Use `progress_scope_changed` to reset comparisons after a same-phase membership change.
Default issues contain at most five classes; when issues_truncated is true,
read diagnostics pages for all classes and their exact units.

A responsive owner may report `no_recent_progress`; expired owner liveness
reports `suspected_stalled` through reason. Status never recovers execution.
Follow allowed_actions and the reported condition. A control response's state is
what is observed after acceptance, not a promise that pause or cancellation has finished.

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

## Keep Geo coverage complete and acquisition compressed

PreCheck owns the decision about which Source Items may share one geographic
observation. It first uses local media relationships, time, coordinates, GPX
movement, and other available evidence to form conservative acquisition units;
then it calls the stage-neutral `mediasense.geo.query` Tool for the remaining
coordinates and projects each returned observation back to every covered Source
Item. Bundle or compression membership is a candidate scope, never proof that one
representative location applies to every member. Exact or near-coordinate
deduplication is a final request defense, not a substitute for this media-aware
step.

Every Source Item has separate address_candidate and nearby_place_candidates
Observations. Missing coordinates, no_result, known terminal service failure, and
policy-disabled lookup do not alone block Plan, even if the whole collection lacks location.
The Tool owns finite authorized retries; do not resubmit terminal failures in an Agent loop.
This does not require one
Provider call per Source Item or per component. Pending confirmation, in-flight
acquisition, indeterminate effects, and invalid Result data still require their real resolution. When the Run pauses,
proceed only if the returned confirmation identifies the exact bounded
`mediasense.geo.query` request fingerprint and effect envelope; otherwise stop and
surface the ambiguity.

1. Show the exact Tool-reported number of logical queries and the coordinate-only
   scope.
2. Explain that the coordinates themselves leave the local boundary and may
   reveal visited places. Report the exact providers, request ceiling, cost
   knowledge, immutable Result retention, and each known or explicitly unknown
   provider data-handling policy from the disclosure.
3. Explain that media, renditions, features, prompts, and ordinary metadata are
   not authorized to leave the local boundary.
4. Present that disclosure as orientation, not as a separate confirmation turn.
   Do not ask the Human to reply with `proceed`, `decline`, or equivalent wording
   in conversation. Explain that the client will now show the single final
   authorization control, then request `resume` with `proceed`. The MCP Host must
   obtain trusted Human confirmation bound to the exact disclosure identity
   through that session elicitation and create the trusted confirmation context
   only after acceptance; never place a caller-authored `authority` object in the
   MCP request. Dismissing the elicitation leaves the Run paused. Do not request
   per-coordinate confirmation, synthesize confirmation, or reuse it for a
   changed pending effect set.

A decline ends the Run without a Plan-ready Result. `provider_unavailable` is a
different terminal condition and must be reported before asking for authority.
Retry and fallback never widen the frozen authorized set. The shared Geo Tool
owns provider routing, request accounting, idempotency, and hard effect ceilings;
PreCheck owns compression, the Run checkpoint, and Result projection.

## Diagnose before revising compression

If the user dislikes the observed frontier, first ask what is wrong with its
content or distribution. A large or small count alone is not evidence of a bad
Result. `review` the exact Result, select Evidence refs from coverage-card
anchors, and request only advertised `expand` includes needed to compare the
complaint with representation bases, coverage, outliers, boundaries,
qualifications, processing provenance, and cost. Use `resolve` when exact member
identity is required; do not substitute review summaries for membership proof.

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

After publication, `review` the exact `result_ref` through
`mediasense.precheck.read`. Interpret coverage and readiness as
independent axes; successful Read enforces integrity and preserve qualifications, omissions, provenance, confidence,
failures, and externally observable cost. Follow each card's
`available_expansions` menu for targeted detail and use its
`source_set` when exact members are needed.

Before handoff, rely on Result `readiness` as the stage contract. Every Source Item
must expose honest component outcomes or explicit not_checked historical gaps;
visual compression must not reduce source coverage. Use
`geo_summary` only when
diagnosing PreCheck acquisition, deduplication, provider outcomes, or historical
Results. Each coordinate group contains a compact `geo_coordinate` Source Set;
pass it unchanged to paged `resolve` when exact members are needed instead of
expecting all refs inline.

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
- state that the current public Run contract has no directed-evidence selector;
  do not translate the internal orchestration seam into an invented Tool field; or
- retain an explicit partial or blocked Result when more work is unavailable or
  not worth its cost.

A valid partial Result may proceed when readiness is `plan_ready`; explain the
material qualifications first. A Result whose readiness is `blocked` is not
Plan-ready: present the blocking evidence and ask the Human whether to continue
with a supported successor/profile revision, accept the limitation, or stop.

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
