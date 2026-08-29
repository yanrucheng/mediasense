---
name: mediasense-plan
description: "Turns one exact MediaSense PreCheck Result into a complete, previewed, Human-confirmed Frozen Organization Plan. Use for interactive media grouping, naming, exception handling, revision, and Plan-stage evidence expansion; not for producing PreCheck evidence or executing Apply effects."
---

# MediaSense Plan

Produce an organization decision the Human can understand and correct before any filesystem change. Preserve the exact PreCheck Result as factual authority, the Working State as mutable draft authority, and the Frozen Plan as the confirmed cross-stage authority.

## Boundaries

- Read source facts and prepared Evidence only through `mediasense.precheck.read`; never inspect PreCheck databases or caches.
- Interpret evidence, propose grouping and names, choose what to inspect, and decide what to ask. Do not ask `mediasense.plan.work` to make semantic judgments.
- Keep Observations, Candidate Relations, Agent judgment, Human preferences, and Human confirmation distinguishable.
- Do not move, copy, rename, delete, or rewrite source media. Apply owns those effects after a Plan is frozen and separately authorized.
- Do not perform reverse geocoding inside Plan. Use qualified place evidence already in the Result or identify an upstream evidence gap.
- Make remote provider, media or metadata egress, model use, cost, and material uncertainty visible before optional remote semantic work.

## Enter Plan

Use only an exact Result whose `readiness` is `plan_ready` and `integrity` is `valid`; bounded partial coverage is acceptable when its limit is explicit. Begin with Result qualifications, entry Evidence, boundaries, outliers, conflicts, and residual uncertainty.

Create one Working State with the Human's current organization preferences. Apply the Default Organization Profile only where an explicit preference does not override it.

## Investigate and propose

Expand prepared Result-local evidence progressively. Inspect additional Source Items or renditions when they can materially change membership, naming, disposition, or the decision to reopen PreCheck. Stop expanding when remaining uncertainty cannot change those decisions.

Reopen PreCheck when a decision requires missing or misleading upstream evidence. Ordinary inspection of reachable Evidence and temporary crops, scales, or compositions remain Plan-local and do not reopen PreCheck.

Submit a complete coherent candidate through `update`; do not encode conversational turns as revisions. A revision is warranted when grouping, paths, membership, source-name overrides, other outcomes, decision notes, or the plan-scoped preference snapshot changes.

Every scoped Source Item must resolve to exactly one logical group or explicit other outcome. Keep exclusions, damaged items, and unresolved material visible rather than omitting them.

## Preview and revise

Generate preview for the exact returned revision and `candidate_content_identity`. Present:

- the final logical directory tree;
- expanded media counts per directory;
- one or two available representative visuals per directory;
- every other accounted outcome; and
- bounded member drill-down where the Human needs detail.

Treat preview as a regenerable review view, not authority. Expanding a directory or changing presentation does not create a revision. When the Human requests a semantic change, consolidate the accepted changes into one complete update, then generate a new preview. Never use an old preview to confirm a newer revision.

## Confirm and freeze

Request final confirmation only when the current candidate is complete and `seal_ready`, and the Human has reviewed the preview bound to that exact identity. Human confirmation must arrive through the trusted interaction context; never construct, infer, or copy authentication claims into the request.

Call `seal` with the exact `work_ref`, revision, candidate identity, and a new idempotent request ID. A successful response is the immutable Frozen Plan. Explain that it is not Apply authorization and causes no source-media change.

If seal returns an error, preserve the distinction among stale revision, identity mismatch, missing confirmation, access denial, invalid candidate, and operation failure. Reinspect or retry only as the returned state permits; never invent a replacement Plan or bypass Tool safety checks.

## Completion

Report the bound Result, coverage limitation, final Plan identity, material unresolved uncertainty, preview/confirmation status, model or egress cost actually incurred, and whether any upstream reopen remains necessary. When comparing with AI Album, classify material differences as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`; a changed directory tree alone is not a regression.
