---
id: "plan-work"
title: "MediaSense Plan Working State Tool Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-09-13
timezone: "Asia/Shanghai"
parent: "index-contract"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "precheck-read"
  - "frozen-plan"
  - "clarify-260827-1604-tool-operation-contracts"
superseded-by: ""
tags: ["mediasense", "plan", "tool-contract", "working-state"]
---

# MediaSense Plan Working State Tool Contract

2026-09-13，第 6 包定案设计按用户授权进入实现。本页和机器定义共同拥有当前接口；
包内草案不构成另一套已发布接口。源码、隔离安装、页面操作及 Human/Agent 验收
分别见[实施记录](../../../../openspec/changes/review-plan-preview-delivery/acceptance.md)。
此前 optional-work 记录保留在[原验收](../../../../openspec/changes/refine-plan-interaction/acceptance.md)。

## Authority and compatibility

`mediasense.plan.work` owns one mutable Work bound to one exact trusted,
plan-ready PreCheck Result. Its four actions remain create, update, inspect and
seal. The Agent owns interpretation, grouping, naming, information sufficiency
and recording decisions. Tools own persistence, mechanical validation, rendering,
prepared-image delivery and page entry. Planning/viewing never reorganizes source
media or acquires remote/model/Geo evidence.

[`plan-work.tool.json`](plan-work.tool.json) is the authoritative exchange shape.
The existing Zero BC policy applies: `organization_content` replaces
`candidate_content`, without compatibility alias or dual organization.
Persistent-state conversion is separate from API compatibility. Frozen Plan
format, content encoding and publication/recovery semantics remain unchanged.

## Entry and lifecycle

Create requires result_ref and request_id, optionally organization_preferences.
Trusted PreCheck Read enforces Result integrity and plan_ready. Complete or
explicitly partial coverage is accepted; ordinary recorded location gaps do not
independently block entry. Result failures retain existing not-found,
unavailable, untrusted, inconsistent and not-ready meanings.

A new Work is open, with empty notes, no organization and no Plan scope, and
immediately offers a page. Open/closed describes its lifecycle, separately from
absent/draft/candidate organization, scope completeness, display availability and
Human confirmation. Closed Works preserve their Frozen Plan and reject edits;
later changes require a new Work. A reserved Plan reference is not publication.

## Atomic organization saving

Update requires work_ref, current base_revision, request_id and at least one
mutable field. All supplied fields commit together or not at all.

| Field | Omitted | Supplied |
| --- | --- | --- |
| organization_content | Preserve current organization | Object replaces whole organization; null clears |
| working_notes | Preserve text | String replaces exact text; empty string clears |
| organization_preferences | Preserve snapshot | Object replaces whole snapshot; empty object clears |

Every newly accepted update creates a new opaque revision, including same-value
writes. Stale base_revision returns revision_conflict. Notes/preferences/clear
do not analyze a replacement organization; post-commit display may read the
retained organization and Result. Revisions support equality only.

Organization reuses result_ref, scope, logical_root, groups, other_outcomes and
decision_notes with `kind: draft | candidate`. It excludes contract, plan_ref
and seal. Source Set, group, naming and note rules reuse Frozen Plan definitions.

Drafts require exact Result binding, nonempty resolvable scope, nonempty resolved
members for saved groups/outcomes, no overlapping or out-of-scope dispositions,
safe destinations/naming and valid note/evidence references. Empty group and
outcome arrays are allowed. Scope may remain partly unassigned; the Tool computes
the remainder without inventing retention, exclusion or fallback groups.
Directory ideas without definite membership belong in notes. Plan scope and
Result coverage remain distinct.

Candidates additionally require complete outcome partition and existing Frozen
Plan validation. Fully assigned drafts do not automatically become candidates.
Drafts have no sealable identity. Candidate identity removes kind and adds the
Tool-owned contract and reserved plan_ref before existing sealed_content encoding.
Notes, preferences and page data never enter that identity or Frozen Plan.

Working notes retain discussion context, actual sources, affected scope and
unresolved implications; they are not a transcript, verified Observation,
attachment store or confirmation. Exact text is preserved without silent
normalization/truncation. Preferences remain a JSON snapshot without independent
identity. Necessary final rationale belongs in decision_notes. Evidence references
remain Result-local; a textual path grants no file custody.

## Safe retry and view delivery

Identical accepted create/update/seal requests return the original business
receipt with no repeated transition. Different input under the same request_id
returns idempotency_conflict. Seal also binds trusted context. Historical
unsupported requests are retained for audit and cannot be reused under the new
interface.

`view` is a fresh observation per invocation, outside the immutable receipt.
Replay may recover unavailable delivery or report an old receipt as superseded
after another save. It never rewrites the old receipt or creates a revision.
Saving and display delivery have separate outcomes.

The descriptor binds work_ref, result_ref, requested revision, observed_at,
observed current_revision, current_uri, revision_uri, status and problems:

| Status | Meaning |
| --- | --- |
| ready | Core planning content and browsing entry can be delivered |
| degraded | Core content is delivered with identified local evidence limits |
| unavailable | Core page or runtime access cannot currently be delivered |
| superseded | The requested saved revision is no longer current |

Current URI continues discussion; revision URI identifies the exact review.
Unavailable addresses are null. Transient addresses are not Plan identities
and may be reacquired after restart. Limits discovered while drilling down appear
at the affected resource without changing organization.

Expected serving/resource failure returns a successful receipt plus truthful
view status. Unexpected implementation exceptions propagate from renderer code;
the outer runtime reports operation_failed, retains diagnostics and includes
committed_receipt when a create/update/seal commit is known. Rendering cannot
roll back planning or require a repeated semantic write. State-only inspect
remains available without rendering or launching a page host.

## Inspect and bounded reading

Inspect resolves one current revision atomically. A stale supplied revision
returns revision_conflict; permanent historical-draft retrieval is not promised.
It returns work_ref, result_ref, revision, state and reserved_plan_ref, plus
requested sections in canonical order:

`overview, preferences, working_notes, content, validation, view`.

Overview reports organization_kind and exact scope_summary (scope, organized,
other_outcomes, unassigned), or null scope when absent. Content is the saved
organization, not a Frozen Plan-shaped draft. Complete mode means the collection
was fully returned; kind separately determines draft/candidate meaning.

Groups, other_outcomes and decision_notes support pages with content as the sole
section. Page headers retain organization meaning. Absent organization returns
null content, including valid initial page requests. Invalid/stale cursors are
still errors. Cursors bind Work, revision, collection, query and position, retain
integrity across compatible restarts and reach a true end without mixing versions.
Candidate identity remains global.

Validation reports deterministic freeze conditions, not semantic sufficiency or
Human acceptance. Absent organization normally reads successfully with
candidate_missing; draft with draft_not_candidate. Complete validated candidates
report seal_ready and identity. Seal revalidates the conditions it owns.

## Continuous page

The ordinary Tool delivers pages for absent organization, notes-only discussion,
partial/full drafts, complete candidates, withdrawal and frozen Works. Agents
do not author HTML, start temporary servers or maintain duplicate presentation
business data. Views are regenerable from saved Work and bound Result.

The page distinguishes working context from retained final decisions and exposes
saved directory hierarchy, exact expanded counts, readable member filenames and
source information, target naming, other outcomes, unassigned scope, note scopes
and qualified actual Evidence. Groups and derived parents preserve saved
first-appearance order; members use stable source-path/ref ordering. Functional
bounded continuation must browse beyond the first 100 items to the true end.
Truncation and image failure never imply unseen members were reviewed.

A loaded page fixes Work/revision. Background detection only prompts; refresh
can resolve current state. Stale pages/cursors refuse incompatible reads and
offer the current entry. New content is not appended to old lists. Closure
updates actual frozen status under the same revision; projection dependencies
include Work state and publication, not revision alone.

Unreadable images retain explicit placeholders and provenance without invented
substitutes or automatic reacquisition. Such gaps do not automatically invalidate
organization. Untrusted/unavailable Result or unresolved membership prevents
claims of complete review and remains a seal barrier. Agent and Human assess
image-gap significance and retain material final limitations in decision_notes.

Runtime owns the real entry lifetime after CLI/Tool return, loopback access,
health/build identity, stop and reconnection. It serves only explicitly bound
Dataset/Work/Result resources, with no filesystem-root exposure or HTTP
write/confirmation/Apply endpoint. Text is data, not executable code. There is
no remote hosting/CDN/model dependency or login-service installation side effect.
Old drafts need not be permanently retained; old entries explicitly report
obsolescence. Closed Works never silently follow another Work.

## Strict revision-bound acceptance and seal

Seal requires work_ref, exact current revision, candidate_content_identity,
request_id, and trusted Human context:

`principal_ref, work_ref, reviewed_revision, confirmed_content_identity, confirmed_at`.

Trusted Work/reviewed revision must equal the requested/current Work/revision.
A stale request returns revision_conflict; mismatched trusted binding returns
confirmation_binding_mismatch; different identity returns content_identity_mismatch.
Missing context returns confirmation_required. Ordinary request fields, notes,
page visits and digests cannot supply Human authority.

**Every new save invalidates old confirmation**, including note/preference and
same-value writes. Withdrawal then restoration of identical content never revives
it. Refresh, pagination, re-rendering and idempotent replay do not create revisions
and therefore do not invalidate matching acceptance. Agent stops sealing after
Human withdrawal and saves the appropriate draft/withdrawal.

After exact-page review and explicit chat acceptance, the Agent conveys that
actual scope through the existing trusted local-client transport and seals
directly. No new popup or digest recital is required. Saving a redundant
confirmation note after acceptance would create a new revision requiring review.

The Tool checks complete candidate, trusted Result and deterministic Frozen Plan
constraints, publishes the unchanged-format artifact, records principal/time
in final_confirmation and closes the same revision. It returns the complete
artifact for Apply. Matching reserved-publication retry recovers exactly one
artifact. Freezing does not move media.

## Errors and conformance evidence

The machine definition enumerates error codes and envelopes. Unknown/invalid
top-level fields and missing mutable fields are invalid_request. Supplied
organization structure, references or organization-rule failures are
organization_invalid. Transport schema validation may reject before dispatch.
Multiple independent errors do not establish a universal error precedence.
Failures never repair groups, widen scope or widen authority silently.

[Primary exchanges](hong-kong.mock.json) and
[continuous scenarios](interaction.mock.json) are static examples, not runtime
receipts or Human acceptance. Implementation evidence separately covers ordinary
CLI/MCP, live entry after Tool return, actual browser navigation, large member
continuation, failures, installation resources and strict confirmation.
Human comprehensibility review and independent/weaker Agent effectiveness require
their own actual evidence; deterministic tests do not certify them.
