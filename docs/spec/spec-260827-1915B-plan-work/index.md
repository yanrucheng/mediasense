---
id: "spec-260827-1915B-plan-work"
title: "MediaSense Plan Working State Tool Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "spec-260826-1546-precheck-read"
  - "spec-260827-1138-frozen-plan"
  - "clarify-260827-1604-tool-operation-contracts"
superseded-by: ""
tags: ["mediasense", "plan", "tool-contract", "working-state"]
---

# MediaSense Plan Working State Tool Contract

## Decision

`mediasense.plan.work` owns one mutable, revisioned Plan Working State and the deterministic transition from one exact revision to a conforming, immutable Frozen Plan. It stores decisions already made by an Agent or Human; it does not interpret media, recognize events, choose groups, generate names, or modify source files.

[`plan-work.tool.json`](plan-work.tool.json) is the authoritative request and response shape. [`hong-kong.mock.json`](hong-kong.mock.json) is a complete human-readable transcript validated by [`tests/test_plan_work_contract.py`](../../../tests/test_plan_work_contract.py).

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
- the current organization preference snapshot and complete candidate organization content;
- deterministic validation issues and the global identity of an exact sealable candidate; and
- the successful transition from an exact confirmed candidate to one `plan_ref`.

The Planning Agent remains responsible for interpretation, evidence selection, grouping, naming, and deciding what to ask the Human. Organization preferences are plan-scoped input inside the existing Working State; they are not a Profile entity or `profile_ref`.

Only a trusted Human authentication context may authorize `seal`. The ordinary request has no `confirmed_by`, credential, UI assertion, or self-declared authority field. Authentication technology and interaction design are outside this contract.

## Entry gate and lifecycle

`create` binds one exact immutable PreCheck Result. The Tool resolves its Result view through the existing [`mediasense.precheck.read`](../spec-260826-1546-precheck-read/) semantics and accepts only:

- `readiness: plan_ready`;
- `integrity: valid`.

Coverage may be `complete` or honestly bounded `partial`. A blocked or invalid
Result returns `result_not_ready` or `result_untrusted` and creates no Working
State. PreCheck Read owns the effective readiness judgment, including safely
blocking a historical Result that lacks a required per-Source-Item fact. Plan does
not inspect Geo acquisition summaries, batches, deduplication, caching, or
provider-request state.

A new Working State is `open`. Every accepted `update` replaces its candidate
atomically and produces a new opaque revision token. Successful `seal` closes the
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

## Candidate content and `update`

Each `update` supplies one complete `candidate_content`, not JSON Patch, natural language, or work-only group entities. The content composes the existing Frozen Plan source-set, logical-group, other-outcome, and decision-note schemas by reference. It omits only fields owned by sealing: `contract`, `plan_ref`, and the `seal` envelope.

The Tool validates the request against the exact bound Result and either replaces the whole candidate and preference snapshot or changes nothing. It may store diffs internally, but diff format is not public.

Before returning a sealable candidate, the Tool reserves the future `plan_ref` and constructs the exact Frozen Plan `sealed_content`, including `contract` and that `plan_ref`. Reservation does not create an authoritative Frozen Plan. It is necessary because the existing Frozen Plan contract covers `plan_ref` with the confirmed content digest.

## `inspect` and pagination

`inspect` reads one exact revision. If the request omits `revision`, the Tool atomically resolves the current revision and returns its opaque token. Supported sections are:

- `overview`;
- `preferences`;
- `content`; and
- `validation`.

Omitting `sections` requests all sections. The default complete content section is the exact candidate `sealed_content` conforming to the existing Frozen Plan `$defs.sealedContent` schema. Large `groups`, `other_outcomes`, or `decision_notes` collections may instead be returned page by page.

Every cursor binds `work_ref`, revision, collection, query shape, and continuation position. A page from another revision or section is invalid. Paging changes only transport: every page of one sealable revision reports the same global `candidate_content_identity`. Page identities do not exist. The complete candidate must remain obtainable by following `next_cursor` until `complete: true`.

Validation issues are deterministic Tool findings, not Agent judgments. `seal_ready: true` requires a complete candidate content identity. `seal_ready: false` returns issues and no sealable identity.

## `seal`

`seal` requires:

- `work_ref`;
- exact `revision`;
- exact `candidate_content_identity` returned by `inspect`;
- `request_id`; and
- a trusted Human authentication context bound to that same identity.

The Tool proves the current revision, identity, Human confirmation, exact Result binding, complete source-set expansion, outcome partition, path and naming safety, and every semantic condition owned by the existing [Frozen Plan Contract](../spec-260827-1138-frozen-plan/). Failure produces no Plan and leaves the Work open.

Success atomically:

1. creates the complete Frozen Plan artifact using the already-confirmed `sealed_content`;
2. records the trusted confirming principal and time in the existing `seal.final_confirmation` fields;
3. closes the Working State; and
4. returns the complete conforming Frozen Plan plus `plan_ref`, `result_ref`, and `content_identity`.

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

JSON Schema validates all request and response shapes with Draft 2020-12 strict compilation and registered external schemas. Semantic tests additionally prove Result entry gates, revision conflicts, cursor binding, one global candidate identity, Human confirmation boundaries, idempotency, Working State closure, and complete Frozen Plan conformance.
