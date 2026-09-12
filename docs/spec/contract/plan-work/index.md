---
id: "plan-work"
title: "MediaSense Plan Working State Tool Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-09-12
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

本页位于稳定合约目录。当前规范以此处为准；迁移到此目录本身不构成新的实现或真实数据验收。

2026-09-12，用户在完成交互与确认流程讨论后确认进入研发。本次可选工作说明、候选保留／替换／撤下及读取语义已定稿；Tool、Skill、Preview 及实际隔离 wheel/MCP 已完成实现验收，日常 CLI/项目 Skills 已按独立复核的构建升级，原注册的新 Host 已验证；现有 Agent 会话加载仍需重新确认。范围见[开发交接](../../../../openspec/changes/refine-plan-interaction/README.md)，证据与未认证范围见[实现验收](../../../../openspec/changes/refine-plan-interaction/acceptance.md)。


2026-09-12 用户复核收窄首轮验收：正常保存路径证据成立，但发现身份字段注入、非法结构错误分类、Preview 图片交付三处缺口。上述三项已通过用户独立复验；后续发现的 Preview 选定 Evidence 分页缺口也已获用户独立复核通过。2026-09-12 按用户授权完成日常安装升级，保留原 Python、extras、依赖和配置。当前契约承诺不变，详细证据见上述实现验收链接。

## Decision

`mediasense.plan.work` owns one mutable, revisioned Plan Working State and the deterministic transition from one exact revision to a conforming, immutable Frozen Plan. It stores Agent-authored working notes, Human organization preferences, and complete candidate decisions. It does not interpret media, recognize events, choose groups, generate names, decide what to ask, or modify source files.

[`plan-work.tool.json`](plan-work.tool.json) is the authoritative request and response shape. [`hong-kong.mock.json`](hong-kong.mock.json) is a complete human-readable transcript validated by [`tests/test_plan_work_contract.py`](../../../../tests/test_plan_work_contract.py).

The Tool has four actions: `create`, `update`, `inspect`, and `seal`. There is no Geo acquisition, `preview`, `validate`, independent Confirm Tool, or Frozen Plan read Tool.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumer exists. Compatibility aliases, version routers, deprecated draft fields, and dual representations are prohibited.

## Authority and permissions

The Tool is authoritative for:

- one `work_ref`, its exact bound `result_ref`, open or closed lifecycle, and revision tokens;
- the current organization preference snapshot, optional working-note text, and optional complete candidate organization content;
- deterministic validation issues and the global identity of an exact sealable candidate; and
- the successful transition from an exact confirmed candidate to one `plan_ref`.

The Planning Agent remains responsible for interpretation, evidence selection, grouping, naming, and deciding what to ask the Human. Organization preferences are plan-scoped input inside the existing Working State; they are not a Profile entity or `profile_ref`.

Only a trusted Human authentication context may authorize `seal`. The ordinary request has no `confirmed_by`, credential, UI assertion, or self-declared authority field. Authentication technology and interaction design are outside this contract.

## Entry gate and lifecycle

`create` binds one exact immutable PreCheck Result. The Tool resolves its Result view through the existing [`mediasense.precheck.read`](../precheck-read/) semantics and accepts only:

- `readiness: plan_ready`;
- successful trusted PreCheck Read, which enforces seal, hash, reference and Observation integrity without a returned constant.

Missing coordinates, no_result and terminal known Geo failure never independently prevent entry, including a whole collection without locations.

Coverage may be `complete` or honestly bounded `partial`. A blocked or invalid
Result returns `result_not_ready` or `result_untrusted` and creates no Working
State. PreCheck Read owns the effective readiness judgment, including safely
blocking a historical Result that lacks a required per-Source-Item fact. Plan does
not inspect Geo acquisition summaries, batches, deduplication, caching, or
provider-request state.

A new Working State is `open`, has empty working notes, and has no Candidate.
Each newly accepted `update` atomically changes its explicitly supplied fields and
produces a new opaque revision token, including a same-value write. An idempotent
replay returns the original receipt without another revision. Successful `seal` closes the
exact revision, publishes a Frozen Plan, and returns that complete Frozen Plan
object as the formal input to Apply preparation. A closed Work remains inspectable
but rejects update and a semantically different seal. Later changes require
another `create`; draft retention and cloning from a Frozen Plan are outside this
contract.

## Safe retry and concurrency

`create`, `update`, and `seal` require `request_id`:

- the same ID with the same request returns the same result;
- the same ID with a different request returns `idempotency_conflict`; and
- a lost successful response can be recovered without creating another Work, revision, or Plan.

Revision tokens are opaque. Callers may compare them only for equality. `update` requires `base_revision`; a stale token returns `revision_conflict` and never overwrites newer content. `seal` requires an exact revision and candidate content identity.

## Organization preferences

`organization_preferences` is a JSON object stored as an exact plan-scoped snapshot. It contains only user-visible planning preferences and constraints. It has no independent ID, version, registry, or lifecycle.

`create` stores the initial object. On `update`, omission and an empty object have different stable meanings:

- omitting `organization_preferences` preserves the current snapshot unchanged;
- providing any object replaces the entire snapshot atomically; and
- providing `{}` explicitly clears the snapshot to no preferences.

There is no preference patch or merge behavior. The Tool preserves the resulting snapshot for re-entry and inspection but does not treat an unknown preference as authority to invent organization semantics. Final organization decisions must appear in candidate content and, after sealing, in the Frozen Plan.

## Working notes

`working_notes` is optional free text inside the existing Working State. It holds
only the work summary an Agent chooses to save: relevant understanding, supplied
information and its source, affected scope, material alternatives, and unresolved
implications when needed to continue. It is not a full transcript, a structured
partial organization, a verified Observation, an attachment store, or confirmation.

On `update`, omission preserves the text, a string replaces it completely, and
`""` clears it. New Works read as `""`. The field has no additional character cap
or pagination in this profile. Accepted text must be preserved and read back in
full without silent truncation or normalization; existing whole-request transport
and resource limits still apply. A textual path does not create a retention or
reading guarantee for the referenced material.

Working notes and preferences never enter the Frozen Plan or its content identity.
The Agent transfers any material final rationale into existing `decision_notes`
and uses only Result-local Evidence in `evidence_refs`. Additional information
keeps its actual source and never rewrites the bound Result or expands its scope.

## Candidate content and `update`

`update` requires `work_ref`, `base_revision`, `request_id`, and at least one of
`organization_preferences`, `working_notes`, or `candidate_content`. Supplying a
field counts even if its value is unchanged. The three fields can change together
in one atomic update; an invalid field or Candidate rejects the entire write.

`candidate_content` has three distinct meanings:

- omitted: preserve the current Candidate and identity, including their absence;
- a complete object: validate and atomically replace the whole Candidate; and
- `null`: clear the current Candidate and its sealable identity.

An object composes the existing Frozen Plan source-set, logical-group,
other-outcome, and decision-note schemas. It omits only fields owned by sealing:
`contract`, `plan_ref`, and the `seal` envelope. Partial objects, JSON Patch, and
natural-language instructions are not candidate content.

Only a supplied complete Candidate is analyzed against the exact bound Result.
Notes-only, preferences-only, and withdrawal updates perform no Candidate
analysis or PreCheck Read; they preserve the same concurrency, cancellation,
commit and seal-recovery protections. Invalid candidate structure, references or
organization change nothing. The Tool does not interpret notes or preferences to
decide whether to preserve, replace, or withdraw a Candidate.

The reserved future `plan_ref` remains attached to the Work, including after
withdrawal. It is included in the materialized `sealed_content` and its digest;
reservation creates no published Frozen Plan. A new Work revision therefore need
not change `candidate_content_identity`. Clearing does not promise recovery of
historical candidates, and re-entering a sealable state requires a complete
Candidate submission. Closed Works remain immutable.

## `inspect` and pagination

`inspect` reads one exact revision. Omitting `revision` atomically resolves the
current revision and returns its opaque token; supplying a stale token returns
`revision_conflict`. Historical revision retrieval is not promised.

Supported sections, also returned by default in this order, are `overview`,
`preferences`, `working_notes`, `content`, and `validation`. Explicit selection
returns only the requested sections, in the same canonical order.
`returned_sections` and the actual section fields agree.

When no Candidate exists, the Work is normally readable. Requested `content` is
JSON `null`; requested `validation` is `seal_ready: false` with a
`candidate_missing` error issue. No candidate identity is returned. Notes and
preferences remain available, including `""` and `{}` when empty. A valid paged
request without a cursor also returns `content: null` in this state, not an empty
organization or a continuation. Request, revision and cursor checks still apply;
an old or invalid cursor is never silently ignored after withdrawal.

When a Candidate exists, the complete content section contains its exact
`sealed_content` conforming to Frozen Plan `$defs.sealedContent`. Large `groups`,
`other_outcomes`, or `decision_notes` collections may be requested page by page.
Page requests still require `sections: ["content"]`.

Every cursor binds `work_ref`, revision, collection, query shape, and continuation
position. A page from another revision or section is invalid. Every page of a
sealable revision reports the same global `candidate_content_identity`; page
identities do not exist. Following `next_cursor` until `complete: true` obtains
the complete requested collection without changing the Candidate's meaning.

Validation reports the saved deterministic Candidate validation. It does not
reacquire evidence for a note edit or prove semantic correctness, preference fit,
current availability of external material, or Human acceptance. `seal_ready: true`
requires a complete candidate identity; `false` returns issues and no sealable
identity. Sealing revalidates the conditions owned by that operation.

## `seal`

`seal` requires:

- `work_ref`;
- exact `revision`;
- exact `candidate_content_identity` returned by `inspect`;
- `request_id`; and
- a trusted Human authentication context bound to that same identity.

The Tool proves the current revision, identity, Human confirmation, exact Result binding, complete source-set expansion, outcome partition, path and naming safety, and every semantic condition owned by the existing [Frozen Plan Contract](../frozen-plan/). Failure produces no Plan and leaves the Work open.

Success atomically:

1. creates the complete Frozen Plan artifact using the already-confirmed `sealed_content`;
2. records the trusted confirming principal and time in the existing `seal.final_confirmation` fields;
3. closes the Working State; and
4. returns the complete conforming Frozen Plan plus `plan_ref`, `result_ref`, and `content_identity`.

A stale Work revision is rejected even when candidate content is unchanged.
After reading the current revision, the same exact content may be sealed under a
still-valid trusted confirmation; a note edit alone does not require another
semantic discussion. User withdrawal or correction cannot be overridden by an
unchanged digest. Working-note prose never supplies authentication.

The returned `plan_ref` becomes authoritative only on successful seal. Repeating the identical request in the same confirmation context returns the same artifact. A new semantic change requires another Working State and another Human confirmation.

## Errors

Errors use the shared `outcome: "error"` envelope with action, optional resolved Work and revision, and structured code and message. Codes owned by this Tool are:

- `invalid_request`;
- `result_not_found`;
- `result_not_ready`;
- `result_untrusted`;
- `work_not_found`;
- `work_closed`;
- `revision_conflict`;
- `idempotency_conflict`;
- `invalid_cursor`;
- `candidate_invalid`;
- `content_identity_mismatch`;
- `capability_unavailable`;
- `confirmation_required`;
- `access_denied`; and
- `operation_failed`.

Missing update fields, wrong top-level field types and unknown request fields use
`invalid_request`. A supplied Candidate object that fails its structure, reference
or organization validation uses `candidate_invalid` and changes no field. A
transport may reject a schema-invalid request before Tool dispatch. An ordinary
inspect without a Candidate is successful; seal without a Candidate uses
`candidate_invalid` when its other preconditions hold. These statements do not
prescribe a total error order for multiply-invalid calls.

Existing Result-local reference failures retain the meanings established by the PreCheck read and Frozen Plan contracts. Errors never silently rebind a Work, repair a candidate, reinterpret a source set, or widen Human authority.

## Boundaries

This Tool does not expose or define:

- SQLite, storage layout, caches, checkpoints, provider APIs, model calls, or planning algorithms;
- CLI syntax, UI presentation, identity-provider implementation, or credentials;
- event recognition, semantic grouping, naming, or user-question strategy;
- copy, move, link, filesystem destination, Apply authorization, or execution receipts; or
- a generic Job, Organization Profile, Dataset Tool, Confirm Tool, or Frozen Plan Read Tool.

## Mock and conformance

The primary Mock uses the exact plan-ready, valid partial Result from the existing PreCheck read Mock and returns the exact Frozen Plan from the existing Frozen Plan Mock. It demonstrates create, atomic update, current-revision inspect, paged inspection, trusted Human seal, safe seal retry, and closed-work rejection. The active Geo Tool Mock and Plan Geo workflow fixtures additionally demonstrate authorization preflight, revision-bound enrichment, refusal, continuation, partial failure, and restart-safe replay.

[`interaction.mock.json`](interaction.mock.json) adds synthetic examples for optional
work saving, absent Candidates, preservation and withdrawal, atomic failures,
revision/content separation and final sealing. Its trusted context is test input,
not a claim that the JSON request can authenticate a Human.

JSON Schema validates all request and response shapes with Draft 2020-12 strict compilation and registered external schemas. Semantic tests additionally prove Result entry gates, revision conflicts, cursor binding, one global candidate identity, Human confirmation boundaries, idempotency, Working State closure, and complete Frozen Plan conformance.
