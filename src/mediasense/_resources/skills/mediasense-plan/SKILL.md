---
name: mediasense-plan
description: "Turns one exact MediaSense PreCheck Result into a complete, retrieval-oriented, previewed, Human-confirmed Frozen Organization Plan. Use for Organization Profile selection, evidence-guided grouping, naming, exception handling, revision, and Plan-stage interaction; not for producing PreCheck evidence or executing Apply effects."
---

# MediaSense Plan

Organize every in-scope media item so none is silently lost and the Human can later find it from the cues they are likely to remember. In suitable personal-media collections, make the path from file to event or scene support recall rather than merely filling directories. Produce an organization decision the Human can understand and correct before any filesystem change. Preserve the exact PreCheck Result as factual authority, the Working State as mutable draft authority, and the Frozen Plan as the confirmed cross-stage authority.

## Tool Host prerequisite

Proceed only when the current Honeycomb session exposes a compatible MediaSense
`0.7.x` Tool Host and `mediasense.plan.work` is discoverable. A CLI found in
`PATH` or an MCP table present on disk is not sufficient. If the Host is absent or
incompatible, stop Plan work and use the `mediasense` product entry Skill's local
Honeycomb bootstrap; do not duplicate setup, edit user-level Agent configuration,
or claim the current session reloaded a newly written project configuration.

## Boundaries

- Read source facts and prepared Evidence only through `mediasense.precheck.read`; never inspect PreCheck databases or caches.
- Treat `review`, `expand`, and `resolve` as factual consumption boundaries. They expose coverage, observations, Evidence, and exact membership; they do not select an Organization Profile or prove retrieval value.
- Interpret evidence, propose grouping and names, choose what to inspect, and decide what to ask. Do not ask `mediasense.plan.work` to make semantic judgments.
- Keep Observations, Candidate Relations, Agent judgment, Human preferences, and Human confirmation distinguishable.
- Do not move, copy, rename, delete, or rewrite source media. Apply owns those effects after a Plan is frozen and separately authorized.
- Prefer qualified place evidence already in the Result. When missing place evidence can materially change the Plan decision, use only the authorization-bound Geo capability through `mediasense.plan.work` `enrich_geo`; never call a map provider or import its adapter directly.
- Make remote provider, media or metadata egress, model use, cost, and material uncertainty visible before optional remote semantic work.

## Enter Plan

Use only an exact Result whose `readiness` is `plan_ready` and `integrity` is `valid`; bounded partial coverage is acceptable when its limit is explicit. Begin with Result qualifications, entry Evidence, boundaries, outliers, conflicts, and residual uncertainty.

Create one Working State with the Human's current organization preferences. An empty `organization_preferences` object means only that no explicit preference is stored; it does not select or confirm a Profile. When the Human accepts a user-visible organization direction, record the actual preferences that shaped the candidate instead of leaving `{}` as if it expressed that choice.

## Choose a starting mode

Do not make every possible organization compete from scratch. First use the Human's likely retrieval cues and a bounded reading of Dataset-wide facts to eliminate clearly unsuitable directions. Treat the event-memory Profile as the default candidate starting point, adopt it only after targeted validation, and adjust or abandon it when material counterevidence appears. Do not ask the Human to choose a Profile label; ask about the future finding behavior or semantic distinction that would change the organization.

A Profile is a reusable set of challengeable propositions, default consequences, counterevidence, and retrieval tests. It is not a directory template, source fact, Tool-managed object, or substitute for Agent judgment. The Frozen Plan remains self-contained and never depends on a `profile_ref`.

### Mature Profile: event memory

- **Proposition:** the Human normally enters through a remembered trip, gathering, exhibition, or other bounded activity; date, place, theme, and scene narrow the search inside it.
- **Fits:** the time range is relatively concentrated, one or a few event boundaries are meaningful, and the collection is not primarily a production or longitudinal record.
- **Clearly does not fit:** the collection spans unrelated years, repeatedly follows one person or place, carries a real project lifecycle, mixes materially different purposes, or leaves the Human scanning most media after entering an event directory.
- **Default consequences:** prefer events; keep simple events shallow; add date, place, theme, or ordered scene groups only when they aid retrieval; default to at most three semantic levels; avoid one-child layers; keep related media together; preserve source basenames; keep auxiliary, damaged, and unresolved material visible; do not split by device or format by default.
- **Counterevidence:** unclear or multiple event boundaries, broad labels that hide important distinctions, large unresolved populations, meaningless layers, or repeated conflict with the Human's stated finding habits.
- **Retrieval test:** “If I remember the event and one partial cue such as a day, place, companion, or activity, where would I enter and how would I narrow the search?”

### Candidate directions

The following named directions shorten hypothesis generation but are not yet accepted MediaSense Profiles. Use them as candidate propositions only, make their unvalidated status visible when material, and accumulate real Human-reviewed cases before promoting any of them. Do not add a registry, Tool operation, schema, service, or separate Skill for them.

#### Time archive

- **Proposition:** approximate time is the Human's most reliable first cue when durable event boundaries are weak.
- **Fits:** long-running, mixed personal media with useful timestamps and no dominant event, person, place, or project axis.
- **Clearly does not fit:** the Human rarely remembers time first, timestamps are materially unreliable, or another stable subject already provides a stronger entry.
- **Default consequences:** navigate from year to month, date, or period, recognizing local events only where they improve retrieval rather than fabricating semantics.
- **Counterevidence:** time buckets remain highly heterogeneous or the Human repeatedly starts from another cue.
- **Retrieval test:** “If I only remember roughly when this happened, can I narrow the search without scanning an entire year?”

#### Person or family memory

- **Proposition:** a Human-confirmed person, family unit, or life stage is the stable entry across many events.
- **Fits:** longitudinal growth, family history, or repeated activities where the same subject is what the Human recalls first.
- **Clearly does not fit:** identity or relationship is unconfirmed, privacy makes the axis unacceptable, or event relationships matter more than person continuity.
- **Default consequences:** consider person or family stage before event and time or scene, without inferring identity, relationship, or privacy choices.
- **Counterevidence:** person-first organization fragments important shared events or conflicts with the Human's normal search path.
- **Retrieval test:** “If I remember the person and life stage but not the event date, can I find the media?”

#### Project or creative work

- **Proposition:** the production context—project, assignment, shoot, batch, selection, or delivery—is the durable retrieval entry.
- **Fits:** photography projects, work shoots, production materials, or deliverables whose source organization carries trustworthy task meaning.
- **Clearly does not fit:** the material is primarily personal memory, project boundaries are absent or untrustworthy, or production and personal media cannot yet be separated safely.
- **Default consequences:** consider project before batch, scene, or task and then material, selection, delivery, or auxiliary roles; do not reinterpret a life event as a production project.
- **Counterevidence:** the proposed lifecycle does not match how the Human retrieves work or depends on invented production status.
- **Retrieval test:** “If I know the assignment or delivery context, can I reach the needed shoot and material state directly?”

#### Place observation

- **Proposition:** one recurring place is the subject, and change across time is what the Human wants to inspect.
- **Fits:** repeated visits, field observation, construction records, or other longitudinal spatial records.
- **Clearly does not fit:** locations are one-off stops inside an event, place evidence is materially uncertain, or the Human starts from an event rather than a site.
- **Default consequences:** consider place before time and then event, change, or theme.
- **Counterevidence:** the place does not materially narrow the search or place-first organization hides the events the Human remembers.
- **Retrieval test:** “If I want to see what changed at this place across visits, can I follow one stable path?”

For a mixed Dataset, use different starting directions only for clearly bounded, disjoint subscopes whose top-level distinction is itself useful to the Human. Keep ambiguous boundaries visible and do not create a separate Profile for every local variation.

## First-principles fallback

When no mature Profile fits, or material counterevidence defeats the event-memory Profile, design from the stable purpose instead of patching the Profile until it merely looks usable. Determine:

- what the Human will want to find and which cues they will remember;
- which cues form a useful broad-to-narrow path;
- which media relationships must remain intact;
- which distinctions materially improve retrieval and which are device, format, or model noise;
- how every in-scope item receives an explicit outcome; and
- how a directional Preview will let the Human challenge the proposed navigation.

Keep the investigation method open. Do not require a universal tree, scoring system, questionnaire, sampling count, or competition among every candidate direction.

## Investigate and propose

Use `review` to establish Result trust, accounting reconciliation, exception routes, and the coverage-card frontier. A complete reconciliation proves that the Result explains its scope; it does not prove Profile fit or organization quality. Before claiming Dataset-wide Profile fit, establish that the whole coverage frontier has been included in the judgment or that the claim is explicitly limited. This is a proof obligation, not a fixed pagination or sampling procedure.

Use `expand` selectively when representative, boundary, outlier, conflict, unassigned prepared Evidence, member observations, or Source Item details can distinguish the current Profile proposition from a material rival. Evidence roles describe review functions inside a compression claim; they are not semantic truth. Use `resolve` for exact membership after semantic decisions require it; exact resolution does not prove that a group is useful.

Expand Result-local evidence progressively. Stop when additional evidence cannot materially change the Profile choice, future retrieval paths, important grouping or naming, exception treatment, questions for the Human, or the decision to reopen PreCheck. Do not substitute a fixed evidence count for this condition.

Handle evidence states without collapsing their meanings:

- `missing`, `failed`, `not_checked`, and `not_applicable` observations remain evidence states, not Tool failures or negative facts;
- incomplete pagination requires continuation before making a claim that depends on unseen content;
- transient `result_unavailable` may be retried safely;
- `result_untrusted` or `result_inconsistent` requires repair or a new Result rather than semantic improvisation; and
- if available evidence still cannot distinguish a material factual rival, preserve the uncertainty and do not form a complete Candidate. Ask the Human only when the unresolved branch is a value or retrieval preference they own.

Reopen PreCheck when a decision requires missing or misleading upstream evidence. Ordinary inspection of reachable Evidence and temporary crops, scales, or compositions remain Plan-local and do not reopen PreCheck.

For a bounded location gap, first identify exact Result-bound Source Items with
available coordinates. Call `enrich_geo` without inventing authorization. If it
returns `authorization_required`, show the Human the exact coordinate count, data
egress, allowed providers, request or cost ceiling, and retention, then continue
only through the trusted authorization boundary. If the Human declines, record the
Plan decision if useful and do not invoke Geo merely to manufacture a `refused`
result. Missing or mismatched authority remains `authorization_required`; provider
unavailability is not a Human refusal.

Begin with `resolve_place`. Use `reverse_geocode` or `nearby_places` only when the
returned candidate remains materially insufficient or conflicting. A continuation
does not inherit authority for larger effects. Treat every returned place as a
provider observation: preserve provenance and uncertainty, keep it distinct from
your interpretation, and stop when more lookup cannot change the Plan decision.

The Tool records accepted Geo outcomes in Plan Working State under a new revision.
Reinspect that revision before updating the candidate. Missing or contradictory
coordinates, or evidence needs beyond the bounded Geo contract, still require an
upstream PreCheck reopen.

Submit a complete coherent candidate through `update`; do not encode conversational turns as revisions. A revision is warranted when grouping, paths, membership, source-name overrides, other outcomes, decision notes, or the plan-scoped preference snapshot changes.

Every scoped Source Item must resolve to exactly one logical group or explicit other outcome. Keep exclusions, damaged items, and unresolved material visible rather than omitting them.

## Preview and revise

Use a directional Preview before the complete candidate when the Human needs to compare organization directions. It may be incomplete, show material alternatives, questions, unsupported retrieval paths, and unresolved Evidence, but it must not be presented as sealable or as an exact final Candidate.

Generate preview for the exact returned revision and `candidate_content_identity`. Present:

- the final logical directory tree;
- expanded media counts per directory;
- one or two available representative visuals per directory;
- every other accounted outcome; and
- material Plan-owned Geo observations, their provider basis, and qualifications;
- bounded member drill-down where the Human needs detail.

Before presenting this final Preview, distinguish four claims:

- **accounting complete:** every scoped item has one explicit outcome;
- **evidence sufficient:** material rivals and counterevidence have been investigated far enough that more Evidence would not change the decision;
- **organization effective:** the structure answers the Human's representative future retrieval questions without avoidable broad rescanning; and
- **Human confirmed:** the Human has reviewed and accepted the exact final Candidate, not merely a Profile direction or earlier Preview.

Treat preview as a regenerable review view, not authority. Expanding a directory or changing presentation does not create a revision. When the Human requests a semantic change, consolidate the accepted changes into one complete update, then generate a new preview. Never use an old preview to confirm a newer revision.

## Confirm and freeze

Request final confirmation only when the current candidate is complete and `seal_ready`, and the Human has reviewed the preview bound to that exact identity. Human confirmation must arrive through the trusted interaction context; never construct, infer, or copy authentication claims into the request.

Call `seal` with the exact `work_ref`, revision, candidate identity, and a new idempotent request ID. A successful response contains the complete immutable `frozen_plan` object that can be passed directly to Apply preparation. Do not discover or construct a Plan-private artifact path. Explain that sealing is not Apply authorization and causes no source-media change.

If seal returns an error, preserve the distinction among stale revision, identity mismatch, missing confirmation, access denial, invalid candidate, and operation failure. Reinspect or retry only as the returned state permits; never invent a replacement Plan or bypass Tool safety checks.

## Completion

Report the bound Result, coverage limitation, final Plan identity, material unresolved uncertainty, preview/confirmation status, Geo or model egress and cost actually incurred, and whether any upstream reopen remains necessary. When comparing with AI Album, classify material differences as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`; a changed directory tree alone is not a regression.
