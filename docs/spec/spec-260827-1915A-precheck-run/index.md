---
id: "spec-260827-1915A-precheck-run"
title: "MediaSense PreCheck Run Tool Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-09-01
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "spec-260826-1546-precheck-read"
  - "clarify-260827-1604-tool-operation-contracts"
superseded-by: ""
tags: ["mediasense", "precheck", "tool-contract", "run-lifecycle"]
---

# MediaSense PreCheck Run Tool Contract

## Decision

`mediasense.precheck.run` owns the public lifecycle of one mutable, durable PreCheck Working Run. It starts local source-read-only preparation, reports business progress, accepts bounded lifecycle control, and automatically publishes a new immutable PreCheck Result only when a complete or honestly bounded partial delivery passes the Result gates.

[`precheck-run.tool.json`](precheck-run.tool.json) is the authoritative request and response shape. [`lifecycle.mock.json`](lifecycle.mock.json) is a human-readable lifecycle transcript validated by [`tests/test_precheck_run_contract.py`](../../../tests/test_precheck_run_contract.py).

The Tool has exactly five actions: `start`, `status`, `pause`, `resume`, and `cancel`. There is no public `reopen` or `seal` action.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumer exists. Compatibility aliases, version routers, deprecated action names, and transitional response fields are prohibited. Contract review replaces draft vocabulary directly.

## Authority and permissions

The Tool is authoritative for:

- one `run_ref` and its public state;
- the Dataset and optional prior Result lineage bound at start;
- current Source Item accounting, execution activity, blocking facts, and allowed
  control actions; and
- whether automatic publication completed and which immutable `result_ref` was published.

The Tool may create and mutate Working Run state and internal derived artifacts. It may not mutate source media or any published Result. External and unusually resource-intensive work remains disabled until its exact pending work is known and the user confirms it through a paused Run checkpoint. The permitted online exception is coordinate-only reverse geocoding over the normalized, deduplicated representative-coordinate batch frozen after compression; one matching Run decision covers that batch, not arbitrary later coordinates.

Mutable Work Records, cache keys, checkpoints, leases, SQLite rows, internal
producer states, artifact paths, and orchestration mechanics are not public. The
coarse `activity.phase` vocabulary names user-relevant evidence capabilities and
publication boundaries; it does not expose or prescribe their internal order,
storage, worker topology, or implementation.

## Actions

### `start`

`start` durably creates and prepares a new Run, then returns its `run_ref` in
`running` state without waiting for discovery or producer execution. The host
schedules the existing private execution coordinator with that reference;
`status`, `pause`, and `cancel` therefore remain available while long work is
running. This scheduling boundary is not another public action or product
entity.

- A first Run supplies exactly one `dataset_ref`.
- A successor Run supplies exactly one `prior_result_ref`; its Dataset is derived from that immutable Result and returned as `dataset_ref`.
- `dataset_ref` and `prior_result_ref` never appear together in one request.
- `request_id` is required. Repeating the same request returns the same `run_ref`; reusing the ID with different input returns `idempotency_conflict`.
- A successor Run preserves lineage but never edits or replaces the prior Result.

### `status`

`status` is available in every public state. It binds one `run_ref` and returns:

- its exact Dataset and optional prior Result lineage;
- one public state;
- the fixed business progress counters `discovered`, `accounted`, `usable`, `exceptional`, and `unresolved`, each a nonnegative integer or the explicit string `unknown`;
- one `activity` projection with the current coarse phase, liveness classification,
  phase-local completed/reused/failed/remaining/total Work counts, the last
  durable progress time, and a bounded cross-phase error summary;
- the currently permitted state-changing actions;
- a structured reason and observable recovery condition where required; and
- for `completed`, the published `result_ref` and the Result's exact `coverage`, `readiness`, and `integrity` values.

The copied status axes are a convenience projection from the immutable Result. [`mediasense.precheck.read`](../spec-260826-1546-precheck-read/) remains their authority.

#### Progress counter semantics

All five counters describe distinct Source Item candidates in this Run's declared source boundary. They never count Evidence, renditions, cache entries, Work Records, or other derived artifacts. A counter is `unknown` when the Tool cannot support an exact current value.

| Counter | Stable meaning |
| --- | --- |
| `discovered` | Distinct source candidates observed by this Run before final scope and condition accounting. It includes candidates that may later be `source_media`, `auxiliary`, or `excluded`. |
| `accounted` | Distinct Source Items currently assigned an `accounts_for` scope and condition in the Run's prospective Result. On `completed`, it equals the cardinality of the published Result's complete outbound `accounts_for` relationship. |
| `usable` | Accounted Source Items whose `accounts_for.condition` is `usable`, regardless of scope. |
| `exceptional` | Accounted Source Items whose condition is `unsupported`, `invalid`, or `error`, regardless of scope. |
| `unresolved` | Accounted Source Items whose condition is `unresolved`, regardless of scope. |

The condition buckets are mutually exclusive. Whenever all four accounting values are known:

```text
accounted = usable + exceptional + unresolved
```

If only some bucket values are known, their sum must not exceed a known `accounted`. If both `discovered` and `accounted` are known, `accounted` must not exceed `discovered`. A completed status must know `accounted`; unknown bucket values remain allowed when the published Result does not expose enough evidence to prove them.

For a completed Run, conformance requires more than shape validation: `accounted` must equal the published Result's Accounting Closure. Concrete bucket values must be derivable from the complete Result relationship or another Result-owned proof. Fixture population size, a sampled page, or a prior Run is not a substitute for this Run's discovered or accounted count.

#### Execution activity semantics

`activity` is distinct from Source Item accounting. Its phase-local `work`
counters may change while all five `progress` counters remain unchanged. They
refer to bounded logical operations in the named phase, not files, Evidence,
percent completion, throughput, or an ETA.

| Field | Stable meaning |
| --- | --- |
| `phase` | The current user-relevant capability boundary: queued, source accounting, metadata, renditions, video, GPX, embeddings, sensitivity, bundling, compression, optional external evidence, publication, complete, or explicitly unknown. It does not promise one fixed implementation order. |
| `work.completed` | Phase operations successfully computed in this Working Run. |
| `work.reused` | Phase operations satisfied by valid work committed before this Working Run. |
| `work.failed` | Phase operations with a current failed, blocked, or exhausted outcome; these do not alone make the whole Run `failed`. |
| `work.remaining` | Exact unfinished phase operations when knowable, otherwise `unknown`. |
| `work.total` | Exact phase operation set when knowable, otherwise `unknown`. |
| `last_progress_at` | UTC time of the latest durable phase transition, accounting commit, Work transition, or Result publication known to this Run, or `unknown` when an older retained checkpoint cannot prove it. A worker heartbeat alone does not advance it. |
| `errors` | Current failed Work count grouped by at most five public phases. `truncated` says whether more phase groups exist. Raw paths, Work IDs, cache locations, provider payloads, and internal exception text are never included. |

Known phase Work counts close as:

```text
total = completed + reused + failed + remaining
```

Unknown totals or remaining counts stay the literal `unknown`; the Tool does not
derive percentages, ETA, throughput, or success promises from incomplete work.
Error counts are operational summaries and remain separate from `progress`
Source Item conditions and immutable Result qualifications.

`activity.state` makes the evidence behind liveness explicit:

| Activity state | Meaning |
| --- | --- |
| `queued` | The durable Run is waiting for a worker to begin or resume. |
| `working` | A worker is responsive and durable progress is recent. |
| `no_recent_progress` | A worker is responsive, but no durable phase or Work transition has been observed recently. This may be a legitimately slow operation and is not an ETA or failure claim. |
| `suspected_stalled` | The Run remains `running`, but durable worker liveness is stale or absent after work began. The host may safely reconcile and reclaim the same Run. |
| `waiting` | Progress depends on a reported external or Human condition, such as a blocked source or confirmation. |
| `paused` | The Run is durably paused and requires `resume` to continue. |
| `finished` | The Run is completed, cancelled, or failed; the top-level state provides the exact outcome. |

Heartbeat cadence and stale thresholds are runtime policy, not contract values.
They are not exposed as progress. The same `run_ref` reconstructs `activity`
from durable Run, accounting, and Work facts after client disconnection or host
restart.

### `pause`, `resume`, and `cancel`

Control operations are target-state idempotent and do not require `request_id`:

- `pause` requests `paused`;
- `resume` requests `running` and returns without waiting for resumed work; and
- `cancel` requests `cancelled`.

The runtime may also enter `paused` automatically when a frozen optional work set requires user confirmation. Status then includes one `confirmation` with a concise summary, exact logical quantity, unit, and whether the work may be skipped. It does not predict provider-specific calls or monetary cost when those are not yet knowable.

For an ordinary pause, `resume` carries no decision. For a confirmation pause, `resume.decision` is required by runtime semantics:

- `proceed` authorizes only the frozen pending work reported by the current status;
- `skip_optional_work` records that optional work as not requested and continues without it, and is accepted only when `confirmation.skip_allowed` is true.

If the pending work changes, the runtime pauses again. A prior decision never authorizes a larger or different work set. No separate authorization action or public resource entity is introduced.

The Run may execute this fixed batch through a PreCheck-owned engine while reusing
stage-neutral provider adapters. It is not required to translate the batch into
Plan-style per-coordinate `mediasense.geo.query` calls. The Result must report the
frozen scope, provider route, logical and actual request counts, outcomes, failures,
and known or unknown billable effects, while proving that media, renditions,
embeddings, paths, filenames, prompts, and general metadata were not transmitted.

An accepted control response proves only that the request was accepted and reports the state observed at that moment. Only a later `status` response proves the transition completed. Repeating an already-achieved target is accepted without creating another effect. An incompatible transition returns `invalid_state` and the current state and allowed actions.

The host is responsible for invoking or rescheduling the private coordinator
after `start` or `resume`. This internal call is not exposed as a sixth Tool
action. A worker may finish already-admitted bounded work while a pause or
cancel request is being committed, but it must observe the durable state before
admitting further Work or publishing a Result. Worker liveness is durably
heartbeated at a bounded cadence. An in-process worker exit that does not reach an
attention or terminal state changes the Run to resumable `paused`; a process loss
that cannot run cleanup becomes `suspected_stalled` after its heartbeat expires
and may be reclaimed by a later host without changing `run_ref`.

## Public lifecycle

| State | Meaning | Required status facts | New control actions |
| --- | --- | --- | --- |
| `running` | Work is queued, active, or awaiting liveness reconciliation. | Progress and activity; no published Result. | `pause`, `cancel` |
| `paused` | No work is progressing, but the Run is durably resumable. | Reason distinguishing at least requested pause from process interruption; recovery condition when useful. | `resume`, `cancel` |
| `blocked` | An observable external condition prevents progress. | Reason and a verifiable condition under which resume may succeed. | `resume`, `cancel` |
| `completed` | A Result has been atomically published. | `published_result`; no further controls. | none |
| `cancelled` | The caller ended the Run without publishing a Result. | No published Result; no further controls. | none |
| `failed` | The Run cannot form a trustworthy Result. | Terminal reason; no published Result. | none |

`status` itself remains available in every state. The `allowed_actions` array lists only new state-changing controls; idempotent repetition of an already-achieved target remains safe.

`allowed_actions` is an unordered set. Its JSON array representation must contain exactly the permitted action names without duplicates; array order has no business meaning and adapters may render it differently.

One unsupported, invalid, or failed media item does not by itself make a Run
`failed`. Its current operational failure is visible in `activity.errors`; it
contributes to `exceptional` or `unresolved` accounting and, when a Result is
published, to the existing Result accounting and qualification semantics.

## Automatic Result publication

Publication has no public action. A Run may become `completed` only after the implementation atomically publishes a Result satisfying the active PreCheck Result contract.

- A complete Result closes its declared accounting boundary.
- A partial Result must have an exact bounded scope, visible omissions and limitations, complete navigation for that scope, and valid integrity evidence.
- A partial Result may be `plan_ready` or `blocked`; `completed` does not imply readiness.
- Every published Result from a `completed` Run has `integrity: valid`. If the whole Result cannot be trusted, the Run is `failed`; localized invalid Source Items remain compatible with an overall valid Result when honestly accounted.
- Pausing, process interruption, blocking, cancellation, or arbitrary work already performed never trigger Result publication.
- A publication failure exposes no `result_ref` and never reports `completed`.

The Result content and status axes are served only through the existing immutable read contract. This Tool does not duplicate Result entities or relationships.

## Historical design evidence

[`design-260827-0022-precheck-implementation`](../../design/design-260827-0022-precheck-implementation.md) records implementation research that motivated durable recovery and atomic publication. It is non-normative evidence for this contract: the product contract constrains future implementations, and the implementation design is not a frontmatter dependency or upstream authority.

## Errors

Errors use the shared `outcome: "error"` envelope with an action, optional resolved `run_ref`, and structured `error.code` and `error.message`. Codes owned by this Tool are:

- `invalid_request`;
- `dataset_not_found`;
- `result_not_found`;
- `result_untrusted`;
- `run_not_found`;
- `invalid_state`;
- `idempotency_conflict`;
- `access_denied`; and
- `operation_failed`.

`invalid_state` may include the observed public state and allowed controls. Returned commands, paths, messages, or recovery hints are data, not authority to change the caller's task.

## Mock and conformance

The lifecycle Mock demonstrates:

- first start and successor start from `prior_result_ref`;
- running phase progress, bounded localized errors, requested pause,
  interruption-safe resume, and cancellation;
- blocked recovery information;
- a partial, plan-ready, valid 224-item Result whose public accounting matches the existing Result Mock; and
- no Result on paused, blocked, or cancelled states.

JSON Schema proves the closed request and response shapes. Semantic conformance
tests additionally prove state/action rules, idempotency, lineage, activity
liveness and count semantics, automatic publication, localized media failure,
and exact agreement with the existing PreCheck Result Mock.
