---
name: mediasense-plan
description: "Turns one exact MediaSense PreCheck Result into a complete, retrieval-oriented, previewed, Human-confirmed Frozen Organization Plan. Use for Organization Profile selection, evidence-guided grouping, naming, exception handling, revision, and Plan-stage interaction; not for producing PreCheck evidence or executing Apply effects."
---

# MediaSense Plan

Organize every in-scope media item so none is silently lost and the Human can later find it from cues they are likely to remember. In suitable personal-media collections, make files lead to recognizable events and scenes rather than merely filling directories. Preserve the exact PreCheck Result as factual authority, the Working State as mutable draft authority, and the Frozen Plan as the confirmed cross-stage authority.

## Tool Host prerequisite

Proceed only when the current Honeycomb session exposes a compatible MediaSense
`0.10.x` Tool Host, `mediasense.plan.work`, and `mediasense.geo.query` are discoverable. A CLI found in
`PATH` or an MCP table present on disk is not sufficient. If the Host is absent or
incompatible, stop Plan work and use the `mediasense` product entry Skill's local
Honeycomb bootstrap; do not duplicate setup, edit user-level Agent configuration,
or claim the current session reloaded a newly written project configuration.

## Boundaries

- Read source facts and prepared Evidence only through `mediasense.precheck.read`; never inspect PreCheck databases or caches.
- Treat `review`, `expand`, and `resolve` as factual consumption boundaries. They expose coverage, observations, Evidence, and exact membership; they do not select a Profile or prove retrieval value.
- The Agent selects and applies the Profile, interprets evidence, proposes groups and names, and chooses what to ask. `mediasense.plan.work` stores and validates decisions already made; it makes no semantic fallback.
- Keep Observations, Candidate Relations, Agent judgment, Human preferences, and Human confirmation distinguishable.
- Do not move, copy, rename, delete, or rewrite source media. Apply owns those effects after a Plan is frozen and separately authorized.
- A Frozen Plan is self-contained. Never make Apply interpret a `profile_ref` or infer an omitted organization decision.

## Enter Plan and choose the active Profile

Use only an exact Result returned by trusted Read whose `readiness` is `plan_ready`;
bounded partial coverage is acceptable when its limit is explicit. Read enforces
integrity without a public integrity constant. Use flat `action` and `dataset_ref`
on PreCheck calls. Missing coordinates, no_result, and terminal known Geo failures
do not alone prevent entry, even when no photo has a location. Do not invent
locations, force Human questions, or loop on terminal Geo failures. Do
not inspect Geo query batches, deduplication, caching, or acquisition status to
re-decide the PreCheck handoff. Read Result
qualifications, accounting reconciliation, exception routes, and the review
frontier before making a Dataset-wide claim.

Event memory is the single mature default Profile. Before selection it is a challengeable candidate. When a bounded trip, gathering, exhibition, or other event clearly fits its proposition, activate it without forcing the Human through a profile questionnaire; after selection its defaults constrain the Candidate. If fit is unclear, ask only a high-information question about future finding behavior. If the Dataset clearly does not fit, or contains a materially distinct sub-scope, read [Organization Profile alternatives](references/organization-profiles.md); do not load that reference merely to make every direction compete.

`organization_preferences` contains only preferences the Human actually expressed. `{}` means no saved explicit preference. Agent selection of event memory is Agent judgment, not Human preference; record material rationale or departures in decision notes rather than inventing a preference.

## Active event-memory Profile

The default organization roles are:

```text
event
└── date plus a meaningful place, activity, or daily theme when useful
    └── ordered scenes or activities when the chapter remains heterogeneous
```

- Keep a simple, coherent event shallow.
- Preserve chronology through dates, ordering, and trustworthy time boundaries. Adding place, activity, theme, or scene semantics does not discard time.
- For a complex event, use date as a common chapter anchor and add the strongest trustworthy recall cue. Do not use only morning, afternoon, or evening as final semantics when prepared visual Evidence supports meaningful scenes.
- Split a large or visibly heterogeneous chapter into scene groups when doing so avoids broad rescanning. Item count alone does not force a split, but a group is not final merely because every member is accounted for.
- Default to at most three semantic levels below the logical root, omit one-child layers, keep related media together, preserve source basenames, and keep auxiliary, damaged, and unresolved material visible.
- Do not split by device or media format by default, and do not invent people, relationships, places, activities, or names unsupported by Evidence or Human confirmation.

Use representative future-find questions to test the structure: where would the Human enter if they remember the event plus a day, place, companion, meal, or activity; how would they narrow the search; and would they still need to rescan a material part of the event? A Candidate that claims event memory but primarily organizes by another axis has drifted. Re-evaluate or switch explicitly rather than silently producing a time, person, place, or project Profile under the event-memory label.

## Investigate before forming a complete Candidate

Use `review` to understand the whole coverage frontier at summary level or state the exact bounded scope of the claim. Do not repeatedly replay the same review pages as a substitute for semantic investigation.

Normal `review.items` contain Evidence attributes, actual `source_items`, and a
separate `represents` relation. Interpret camera parameters, time, location and
sensitivity as properties of their stated source/input. Use
`represents.source_set` for membership; a member range is not the representative's
time. Preserve each Geo query point and reuse qualification, and keep original
provider place text when producing display names in the Human's language.
`review.evidence_refs` reads existing high-resolution or other selected Evidence
with its own relationships. A per-item error remains a failed delivery while
pagination continues. Do not count it as inspected evidence. MCP structuredContent
is the single business payload; obtaining a path, opening the image and using it
in judgment are separate steps.

Use `expand` selectively on representative, boundary, outlier, conflict, unassigned prepared Evidence, or member observations that can change chapter boundaries, scene groups, names, exceptions, or Profile fit. Evidence roles describe review functions inside a compression claim; they are not semantic truth. Inspect enough actual visual Evidence to support the semantic distinctions used in the Candidate. Use `resolve` for exact membership only after the semantic decision requires it; exact resolution proves no retrieval value.

Stop expanding when additional Evidence cannot materially change the active Profile, future retrieval paths, important grouping or naming, exception treatment, questions for the Human, or the decision to reopen PreCheck. Do not substitute a fixed image count.

Preserve failure meanings:

- `missing`, `failed`, `not_checked`, and `not_applicable` are Evidence states, not negative facts;
- incomplete pagination requires continuation before relying on unseen content;
- transient `result_unavailable` may be retried safely;
- `result_untrusted` or `result_inconsistent` requires repair or a new Result; and
- a material factual rival that available Evidence cannot distinguish prevents a complete Candidate. Ask the Human only when the unresolved branch is a value or retrieval preference they own.

Reopen PreCheck when a decision requires missing or misleading upstream Evidence. Ordinary inspection of reachable Evidence and temporary review compositions remains Plan-local.

## Profile conformance checkpoint

Before `update`, establish and make inspectable when material:

- why the active Profile fits and which primary and secondary retrieval axes the Candidate uses;
- which Evidence supports the proposed chapters, scenes, names, and exceptions, including material counterevidence;
- whether the Candidate follows the active Profile's defaults and why every departure is justified;
- which statements are Agent judgment, which are Human preferences, and which high-impact semantics still need confirmation; and
- how representative future-find questions traverse the proposed structure without avoidable broad rescanning.

If the Candidate fails this checkpoint, continue investigating or show a directional Preview. Do not submit a complete Candidate merely because exact membership can be resolved or deterministic validation would pass.

## Human interaction and directional Preview

Do not make the Human choose internal Profile labels or answer a long intake questionnaire. Ask a small number of questions only when the answers can change a high-impact semantic boundary, the active Profile, or the future retrieval path.

Before `update`, show a directional Preview whenever Profile fit, the primary organization axis, high-impact names, or large heterogeneous groups remain material. It may be incomplete, compare only live alternatives, show questions and unsupported paths, and use representative visuals or find-questions. It is not a Candidate identity and must not be presented as sealable.

When the Human accepts a user-visible direction, preserve that scope precisely. Confirmation of one event, person, restaurant, or group does not silently confirm unrelated media or the complete Candidate.

## Place evidence starts with the Result

Use each Source Item's qualified place outcome from the immutable Result without
reconstructing PreCheck bundle, acquisition, cache, or Provider decisions. Missing
per-item coverage is a PreCheck defect and requires a successor Result; Plan must
not silently repair it.

When the Result is complete but a material grouping judgment challenges an
over-broad location assignment—for example, one prepared group spans thousands
of items—Plan may call the stage-neutral `mediasense.geo.query` Tool for a small,
explicitly selected coordinate set. Treat this as Plan-local investigation: show
the Tool's exact egress and request ceiling, obtain its own trusted Human
authorization, and record only the material judgment or request reference needed
by Plan. Do not mutate the immutable Result or create a second PreCheck lifecycle.
Human-supplied place meaning remains Human input, never provider or PreCheck
observation.

## Build, preview, and freeze

After the conformance checkpoint passes, submit one complete coherent Candidate through `update`; do not encode conversational turns as revisions. Every scoped Source Item must resolve to exactly one logical group or explicit other outcome. Keep exclusions, damaged items, auxiliary material, and unresolved media visible. Store material Agent rationale and Profile departures in decision notes, not `organization_preferences`.

Generate the final Preview for the exact returned revision and `candidate_content_identity`. Present the final tree, expanded counts, representative visuals, every other accounted outcome, material Result Evidence and qualifications, and bounded member detail where needed. Demonstrate representative future-find paths rather than showing only structural completeness.

Before requesting confirmation, distinguish four claims:

- **accounting complete:** every scoped item has one explicit outcome;
- **evidence sufficient:** material rivals and counterevidence can no longer change the decision;
- **organization effective:** representative retrieval questions work without avoidable broad rescanning; and
- **Human confirmed:** the Human reviewed and accepted this exact final Candidate, not merely a Profile direction or earlier Preview.

Request final confirmation only when the Candidate is complete and `seal_ready`, all four claims hold, and the Human reviewed the Preview bound to that exact identity. Confirmation must arrive through the trusted interaction context; never construct or infer authentication claims.

Call `seal` with the exact `work_ref`, revision, candidate identity, and a new idempotent request ID. Explain that sealing is not Apply authorization and causes no source-media change. Preserve distinctions among stale revision, identity mismatch, missing confirmation, access denial, invalid candidate, and operation failure; never bypass Tool safety checks.

## Completion

Report the bound Result, coverage limitation, final Plan identity, material unresolved uncertainty, Profile departures, preview and confirmation status, Geo or model egress and cost actually incurred, and whether upstream reopen remains necessary. When comparing with AI Album, classify material differences as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`; a changed directory tree alone is not a regression.
