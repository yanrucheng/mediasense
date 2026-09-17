---
name: mediasense-plan
description: "Turns one exact MediaSense PreCheck Result into a complete, retrieval-oriented, previewed, Human-confirmed Frozen Organization Plan. Use for evidence investigation, grouping, naming, local detail requests, exception handling, revision, and Plan-stage interaction; not for publishing PreCheck Results or executing Apply effects."
---

# MediaSense Plan

Organize every in-scope media item so none is silently lost and the Human can later find it from cues they are likely to remember. In suitable personal-media collections, make files lead to recognizable events and scenes rather than merely filling directories. Preserve the exact PreCheck Result as factual authority, the Working State as mutable draft authority, and the Frozen Plan as the confirmed cross-stage authority.

## Tool Host prerequisite

Proceed only when the current Honeycomb session exposes a compatible MediaSense
`0.11.x` Tool Host, `mediasense.plan.work`, and `mediasense.geo.query` are discoverable. A CLI found in
`PATH` or an MCP table present on disk is not sufficient. If the Host is absent or
incompatible, stop Plan work and use the `mediasense` product entry Skill's local
Honeycomb bootstrap; do not duplicate setup, edit user-level Agent configuration,
or claim the current session reloaded a newly written project configuration.

## Boundaries

- Read sealed Result facts, recorded source attributes, memberships and prepared Evidence through `mediasense.precheck.read`; never reconstruct them from PreCheck databases or caches. This authority boundary leaves original-media investigation open: the Agent may read selected source files through available, authorized readers. Human knowledge, background, supplementary files and investigative results retain their actual sources and affected scope; they do not rewrite the Result or expand its media scope.
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

Before applying event memory, read the [default organization Profile](references/default-organization-profile.md), including its related-media, auxiliary, unresolved and damaged-item rules. This is the offline release snapshot of the single authority at `docs/spec/contract/default-organization-profile/index.md`; do not independently author the copy. Its tree illustrates available roles, not mandatory folders. Apply the rules to the evidence and the Human's retrieval purpose; do not invent unsupported people, relationships, places, activities or names.

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

Use `expand` for prepared detail, member observations, relationship bases and limitations that can change a decision. Use `resolve` when exact members, source locators or verification evidence help the investigation or organization; these reads may inform the decision before groups are chosen. A member list does not establish that its files have been viewed. Evidence roles and `represents` describe a compression claim, not semantic equivalence or an indivisible unit of organization.

Choose investigation depth from the Human's current retrieval goal. A compression result that supported an earlier broad grouping may hide distinctions needed by a finer request. Evaluate its actual members, basis and limitations for that decision; a threshold is a processing setting, not semantic confidence. Time adjacency and a shared representative do not establish one activity.

Available methods can be combined in any useful order:

- Reuse prepared Evidence and recorded attributes when they already support the required distinction.
- Inspect selected original media or source fields with available readers when direct investigation is worthwhile. Result-linked locators from `resolve` keep this investigation scoped; use available verification evidence to assess correspondence to the recorded source snapshot. A path alone does not prove unchanged content. Temporary renditions, sampled frames or contact sheets may aid investigation; keep them outside source media and retain their source and sampling limits.
- Choose new local PreCheck preparation when reusable computation and compression can reduce the expected reading burden. `review include=["preparation"]` exposes the recorded Processing Profile and complete input Source Set; use its actual settings and the Tool's supported controls to assess a change. More detailed compression can yield more entries than before while still requiring fewer reads than the original subset.

Weigh local preparation and I/O, model reading, elapsed time and Human attention against the value of the unresolved decision. New preparation also has source validation, publication and Plan continuation costs; do not assume its total cost scales only with the selected subset. Estimates and unknowns remain distinguishable from measurements. Reading every item in a selected scope is valid when its value warrants the cost within existing authority and budgets. Missing prepared imagery neither prohibits original-media inspection nor requires a new Run. Explain the choice briefly when it materially affects cost, completion or retained uncertainty; routine reads need no separate approval or cost report.

Stop when the available support meets the current organization goal and further investigation is unlikely to change a material decision. Human knowledge and authorized background research can supply missing context. If a useful distinction remains unsupported, investigate it or offer a supported coarser placement with the unmet retrieval detail visible. Avoiding a guessed name or inspecting many images does not establish sufficiency; no fixed image count, confidence threshold, question quota or mandatory recompression sequence decides it.

Preserve failure meanings:

- `missing`, `failed`, `not_checked`, and `not_applicable` are Evidence states, not negative facts;
- incomplete pagination requires continuation before relying on unseen content;
- transient `result_unavailable` may be retried safely;
- `result_untrusted` or `result_inconsistent` requires repair or a new Result; and
- a material factual rival requires further information or a supported coarser disposition. Actively seek information that can change the decision, including Human knowledge, background and corrections, as well as preferences. Do not invent an answer when the Human cannot remember or has not replied; continue independent work while dependent decisions remain unresolved.

Result integrity, accounting or preparation obligations that need correction still require their PreCheck remedy; local investigation cannot bypass a broken handoff. Publishing revised PreCheck observations or compression relationships requires a new immutable Result. Ordinary semantic uncertainty or a finer retrieval goal can instead be resolved within Plan using sufficient existing or newly investigated information. Keep original-file and supplementary observations as attributed Plan investigation, not fabricated observations in the bound Result; `evidence_refs` remains limited to Evidence already in that Result. If a needed reader or original is unavailable, disclose the actual limitation. A path in notes does not establish MediaSense custody of that original.

## Profile conformance checkpoint

Before submitting a complete `organization_content` with `kind: "candidate"` through `update`, establish and make inspectable when material:

- why the active Profile fits and which primary and secondary retrieval axes the Candidate uses;
- which Evidence supports the proposed chapters, scenes, names, and exceptions, including material counterevidence;
- which missing information could still change an important retrieval path or decision, and how the Candidate resolves or explicitly preserves that uncertainty;
- whether the Candidate follows the active Profile's defaults and why every departure is justified;
- which statements are Agent judgment, which are Human preferences, and which high-impact semantics still need confirmation; and
- how representative future-find questions traverse the proposed structure without avoidable broad rescanning.

If the Candidate fails this checkpoint, continue investigating or show a directional Preview. Do not submit a complete Candidate merely because exact membership can be resolved or deterministic validation would pass.

## Human interaction and directional Preview

The Agent owns information sufficiency for the proposed organization. Choose when to investigate or ask using the decision’s importance, available support, cost, Human attention and authorized scope. Ask for knowledge, context or supplementary material when it can materially change a decision; do not limit interaction to preferences. When information is sufficient, proceed directly. Input forms, investigation methods and conversation pace remain open; no universal uncertainty threshold, fixed shortlist or required question per item applies. Do not make the Human choose internal Profile labels or complete a fixed intake questionnaire.

Before submitting a complete Candidate, show a directional Preview whenever Profile fit, the primary organization axis, high-impact names, or large heterogeneous groups remain material. It may be incomplete, compare only live alternatives, show questions and unsupported paths, and use representative visuals or find-questions. It is not a Candidate identity and must not be presented as sealable.

When the Human accepts a user-visible direction, preserve that scope precisely. Confirmation of one event, person, restaurant, or group does not silently confirm unrelated media or the complete Candidate.

A supported coarser Candidate may be offered for review without claiming the Human has already accepted its lost detail. No reply is not acceptance. Later requests for finer detail may extend the retrieval goal; distinguish them from information the earlier goal already needed. A later factual correction can supersede an earlier Human account without implying that the Agent could have known it in advance. A photographed menu establishes its listed choices, not everything ordered or the contents of every represented member.

## Place exceptions using their context

Interpret scope, condition, content readability, contextual association and execution feasibility separately. Follow the selected Profile's nearest trustworthy placement; do not filter all group memberships to `usable` and send the remainder to one fallback. A damaged file can belong with related media, and a readable file can still lack a trustworthy finer group.

For an unreadable original with readable related versions, inspect the retained relationship basis and available source context. A shared stem, source directory, capture sequence or Human account may support co-location without proving byte identity, repair completeness or identical content. A representative from another source supplies only its own observed content. Preserve the qualifications; do not invent fine classification or discard a version to make the group simpler.

Judge auxiliary material by how it serves the collection. An in-scope track can be kept with the trip's auxiliary files while its validity remains unresolved. A traversal-control marker has a different purpose and may reasonably remain in its original location. Retaining current organization is a valid outcome; review its fit with the active Profile and make material departures clear, rather than requiring an exceptional justification for every retained item. Apply owns current filesystem verification and cannot change the logical disposition to compensate for a failed move.

Keep material exception explanations in existing `decision_notes` or other-outcome reasons, with their exact Source Sets: what is placed where, the supporting context, what remains unknown and any consequence for later finding. A damaged item in a normal group still needs its damage visible. A combined exception count does not explain different treatments of unreadable media, readable unresolved media, tracks and control files.

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

## Save and review the evolving Work

When new local preparation is the chosen method, read the old Result's
preparation and send a complete ordinary PreCheck start request with its explicit
input Source Set and chosen overrides. The Processing Profile is a configuration
value, distinct from this stage's Organization Profile. Other declared parameters
remain unchanged; group membership may change. Preserve the old Result and Work.

To continue on the new Result, inspect the old Work's notes, preferences and
organization, then use PreCheck resolve with target_result_ref to verify the
relevant source correspondence. Only matched recorded input bindings justify
carrying source-specific scope; unproven correspondence cannot be guessed from
equal paths, bytes or copied references. Even matched sources do not prove equal
observations or representative groups. Inspect current covering Evidence where
it matters, create a new ordinary Work bound to the new Result, and retain only
justified notes, preferences and organization. Never rebind the old Work or
transfer its Human confirmation. Review and confirm the new exact Candidate.

Establish or restore a Work when discussion begins from a usable Result. Share the Tool-returned current page from the beginning, including notes-only discussion. Before claiming that planning content changed or requesting review of a change, save the relevant current organization, explanation or unresolved implications. Do not record every chat turn or private reasoning.

`organization_content` holds one organization: omit to preserve, provide an object to replace, or `null` to clear. Use `kind: "draft"` for partially decided organization and `kind: "candidate"` only after the complete-Candidate checkpoint. Reuse scope, groups, other_outcomes and decision_notes. Keep only directories with explicit resolvable members in the tree; unsupported directory ideas belong in working_notes. Unassigned scope is computed and readable through the Tool; disclose its material extent in conversation. Never invent retention, exclusions or a fallback group just to complete a draft. A fully assigned draft remains a draft until explicitly submitted as a candidate.

`update` also accepts working_notes (string replacement, `""` clears) and organization_preferences (object replacement, `{}` clears). All supplied changes commit together using work_ref, base_revision and request_id. Rejected organization saves none of them. Notes and preferences remain discussion context; transfer necessary final rationale into decision_notes.

Every successful save returns `view` with current_uri and revision_uri, or explicit delivery limitations. Use these entries for organization review; do not replace the saved Work's page with Agent-authored HTML, a temporary presentation server or separately maintained planning data. Temporary investigative images remain investigation aids, not a second Plan authority. The Tool owns rendering, images and bounded group/member reads. The “整理方案” page shows only saved groups, initially collapsed and independently expandable, with readable paths, exact counts and horizontal responsive previews. Working context, other dispositions, unassigned scope and decision explanations remain readable through existing Tools; they are not additional page panels. Page visits, refresh, pagination and re-rendering do not save a revision.

Default inspect includes overview, preferences, working_notes, content, validation and view. An absent organization or draft is a normal saved state, even though validation says candidate_missing or draft_not_candidate. If display fails, state that the planning revision was saved and the page is unavailable. Use state-only inspect without view to recover authority; use inspect with view or identical request replay to restore delivery. Unexpected operation_failed may carry committed_receipt. Do not repeat the semantic write after a known commit. Replay retains its original business receipt but observes current delivery anew; superseded means its old revision is no longer current.

The Runtime automatically reclaims idle display contexts and exits after sustained
inactivity. Use the returned entry normally; do not add start, keepalive, renewal,
render or stop steps to Plan work. A link is stable for its Work within the serving
process and transient across restart. Cache reclamation or an offline link does
not invalidate the saved Plan or its revision. The next ordinary inspect with
view (or normal save) returns the current serving entry. Only runtime faults need
`views status/stop` diagnostics for the same executable and data home. A busy
resource is retryable; an image gap is local; superseded requires review of the
current revision. Browser activity supplies no Human acceptance.

## Build, preview, and freeze

After the conformance checkpoint passes, submit one complete coherent Candidate through `update`. Every scoped Source Item must resolve to exactly one logical group or explicit other outcome. Keep exclusions, damaged items, auxiliary material, and unresolved media visible. Store material Agent rationale and Profile departures in decision notes, not `organization_preferences`.

Use the Tool-returned `view.revision_uri` for the exact returned revision and `candidate_content_identity`. The page presents groups, exact counts and selected previews. Complete its review in conversation using that same revision: disclose every omitted fact that could change acceptance, including scope/coverage limits, other accounted outcomes, unassigned items, target naming changes, exceptions, material Result Evidence qualifications and gaps, important `decision_notes` with their applicable Source Sets, and residual uncertainty. Use existing bounded Tool/Result reads for member detail where needed. Keep these explanations in the Candidate’s notes or outcome reasons; do not hide them as working process or add the removed page panels back. If material disclosure is incomplete, do not claim whole-Plan review or request whole-Plan acceptance. Transfer the shortest necessary final explanation and source category from supplementary inputs into these notes; working notes do not automatically enter final review. Without a Candidate, a directional display cannot be labeled a final, sealable Preview. Demonstrate representative future-find paths rather than showing only structural completeness.

Before requesting confirmation, distinguish four claims:

- **accounting complete:** every scoped item has one explicit outcome;
- **evidence sufficient:** available evidence supports the proposed granularity; known material gaps and conflicts are resolved or explicitly handled by supported coarse or unresolved dispositions;
- **organization effective:** representative retrieval questions work without avoidable broad rescanning; and
- **Human confirmed:** the Human reviewed and accepted this exact final Candidate, not merely a Profile direction or earlier Preview.

The first three claims support requesting review of a complete, `seal_ready` Candidate. Show the HTML and complete the same-revision conversational disclosure for that exact Candidate, then obtain explicit acceptance in chat; that actual acceptance establishes the fourth claim. A local factual correction, directional acceptance, saved note saying “confirmed”, or Tool validation is not whole-Plan acceptance. Use the existing local client transport authority to convey that acceptance; do not add an MCP confirmation popup or ask the Human to recite a digest. The local client context is trusted, but a content match is not independent proof of a real Human event: the Agent must preserve the actual acceptance scope and validity.

Any new saved revision invalidates earlier acceptance, including notes-only, preference-only and same-value writes. Withdrawal followed by restoration of identical content also requires new acceptance. Refresh, member pagination, re-rendering and identical request replay do not invalidate it. When the Human withdraws acceptance, stop sealing and save the appropriate draft or withdrawal promptly.

After explicit acceptance, pass the actual trusted local-client context with principal_ref, work_ref, reviewed_revision, confirmed_content_identity and confirmed_at, and seal that exact revision directly. Do not first save a redundant “confirmed” note: that would create a new revision requiring review again. A matching digest alone cannot carry acceptance across revisions.

Call `seal` with the exact `work_ref`, revision, candidate identity, and a new idempotent request ID. Explain that sealing is not Apply authorization and causes no source-media change. Preserve distinctions among stale revision, identity mismatch, missing confirmation, access denial, invalid candidate, and operation failure; never bypass Tool safety checks.

## Completion

Report the bound Result, coverage limitation, final Plan identity, material unresolved uncertainty, Profile departures, preview and confirmation status, Geo or model egress and cost actually incurred, and whether upstream reopen remains necessary. Distinguish additional Geo/provider calls from the Agent's own model use: no extra provider call does not establish zero model processing, data egress or cost. Report unmeasured effects or charges as unknown. When comparing with AI Album, classify material differences as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`; a changed directory tree alone is not a regression.
