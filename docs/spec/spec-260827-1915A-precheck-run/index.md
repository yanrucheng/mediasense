---
id: "spec-260827-1915A-precheck-run"
title: "MediaSense PreCheck Run Tool Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-09-04
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

The Tool may create and mutate Working Run state and internal derived artifacts. It may not mutate source media or any published Result. Before expensive local work, the Tool exposes factual source-tree statistics and enforces an exact caller-selected scope; it does not decide whether a named or hidden subtree is semantically wanted. External work remains disabled until its exact pending work is known and the user confirms it through a later paused Run checkpoint. The permitted online exception is coordinate-only reverse geocoding over a media-aware acquisition set derived from every Source Item with an available final coordinate. Bundle, time, and trajectory evidence may reduce requests without reducing per-item Result coverage, and one matching Run decision covers only that frozen pending work.

Mutable Work Records, cache keys, checkpoints, leases, SQLite rows, internal
producer states, artifact paths, and orchestration mechanics are not public. The
coarse `activity.phase` vocabulary names user-relevant evidence capabilities and
publication boundaries; it does not expose or prescribe their internal order,
storage, worker topology, or implementation.

## Actions

### `start`

`start` durably creates and prepares a new Run, acquires an execution-worker
lease, and launches the existing private execution coordinator before returning
its `run_ref` in `running` state. It does not wait for discovery or producer
completion. If source-bound preparation, worker acquisition, or worker launch
fails, `start` fails immediately and the retained Run records the failure; it
must not return an ownerless `running` Run. This execution boundary is not
another public action or product entity.

The first worker pass completes source discovery and ordinarily pauses for a
scope selection before admitting expensive producer Work. A later Run may skip
that pause only when it discovers an inventory exactly compatible with a prior
accepted selection for the same Dataset.

One public Run keeps one source-accounting identity for its whole lifetime.
`resume` revalidates and continues that exact bound accounting state; it never
selects or creates a newer Dataset-level accounting Run. A refreshed inventory
is another generation of the same bound Run. If preparation or worker launch
stops before an execution owner exists, any bound accounting state is retained
as non-running before the public response is returned.

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
- while source scope is pending, one bounded factual inventory tree; and
- after acceptance or exact reuse, the effective scope selection and its
  provenance; and
- for `completed`, the published `result_ref` and the Result's exact `coverage`, `readiness`, and `integrity` values.

While source scope is pending, callers may supply a source-relative
`scope_path` to `status` to replace the root view with a bounded view of that
subtree, and `scope_after` to continue an oversized sibling list. This is a
read-only projection, not a sixth action. `status` never starts, resumes,
reclaims, or schedules execution. Counts, byte totals, kind
distributions, size buckets, representative paths, omitted-child counts, and
discovery limitations are facts. Cache, backup, historical-output, or
legitimacy judgments are deliberately absent.

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
| `phase` | The current user-relevant capability boundary: source accounting, scope review, metadata, renditions, video, GPX, embeddings, sensitivity, bundling, compression, optional external evidence, publication, complete, or explicitly unknown. It does not promise one fixed implementation order. |
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
| `working` | A worker is responsive and durable progress is recent. |
| `no_recent_progress` | A worker is responsive, but no durable phase or Work transition has been observed recently. This may be a legitimately slow operation and is not an ETA or failure claim. |
| `suspected_stalled` | The retained Run has no current execution owner or its durable worker liveness has expired. Status includes the exact known reason and exposes explicit `resume`; it never reclaims the Run implicitly. |
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

The runtime may also enter `paused` automatically for source-scope selection or
for the required frozen Geo acquisition boundary. A source-scope confirmation
contains the exact inventory fingerprint and bounded factual inventory. An
external-effect confirmation contains its exact content identity, coordinates,
logical quantity, providers, request ceiling, known cost or `unknown`, provider
data-handling policy or `unknown`, transmitted data classes, and fixed immutable
Result retention.

For an ordinary pause, `resume` carries no decision. For a confirmation pause,
`resume.decision` is required by runtime semantics:

- a source-scope decision supplies the matching inventory fingerprint, a
  default `include` or `exclude` disposition, and non-overlapping subtree
  exceptions with the opposite disposition;
- `proceed` requires trusted Human confirmation bound to the exact disclosure and
  authorizes only that frozen pending work; and
- `decline` terminates the Run with `authorization_declined`, performs no provider
  request, and publishes no Result.

Before applying a source-scope decision, the worker performs another discovery
generation. If the inventory changes, the old decision is not applied and the
Run pauses on the refreshed inventory. The exact prior selection may be reused
by a later Run over the same Dataset only when its inventory fingerprint still
matches. Excluded items remain in Result accounting and create no source-tree
effect.

If optional pending work changes, the runtime pauses again. A prior decision
never authorizes a larger or different work set. No separate authorization
action or public resource entity is introduced.

The Run executes this fixed batch through the stage-neutral
`mediasense.geo.query` Tool. PreCheck owns media-aware compression, the Run
checkpoint, compatible observation reuse, and per-Source-Item Result projection;
the Geo Tool owns Provider routing, hard effect ceilings, and idempotent execution.
The Result must report logical and actual request counts, outcomes, failures, and
known or unknown billable effects, while proving that media, renditions,
embeddings, paths, filenames, prompts, and general metadata were not transmitted.

An accepted pause or cancel response proves only that the request was accepted
and reports the state observed at that moment. A successful `resume` additionally
proves that a live persistent host acquired and launched the execution worker;
it does not prove producer progress or completion. Repeating an already-achieved
target is accepted without creating another effect. An incompatible transition
returns `invalid_state` and the current state and allowed actions.

If source attachment continuity needs caller action, `resume` returns an error
whose `current_state` is `blocked` and whose `allowed_actions` remain `resume`
and `cancel`; `status.reason` supplies the stable reason and recovery condition.
An unrecoverable initialization failure reports `failed` with no allowed action.

The host is responsible for acquiring an execution lease and launching the
private coordinator before a successful `start` or `resume` response. A
one-shot host that cannot retain the worker must refuse those actions. `status`
never performs this work. A worker may finish already-admitted bounded work while a pause or
cancel request is being committed, but it must observe the durable state before
admitting further Work or publishing a Result. Worker liveness is durably
heartbeated at a bounded cadence. An in-process worker exit that does not reach an
attention or terminal state changes the Run to resumable `paused`; a process loss
that cannot run cleanup becomes `suspected_stalled` after its heartbeat expires
and may be reclaimed only by an explicit `resume` on a live persistent host,
without changing `run_ref`.

## Public lifecycle

| State | Meaning | Required status facts | New control actions |
| --- | --- | --- | --- |
| `running` | A worker owns execution, or retained liveness evidence explicitly reports that the owner is suspected stalled. | Progress and activity; stalled execution also requires a reason and recovery condition; no published Result. | active: `pause`, `cancel`; stalled: `resume`, `cancel` |
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
- a partial, plan-ready, valid 5-item Result whose public reconciliation matches the existing Result Mock; and
- no Result on paused, blocked, or cancelled states.

JSON Schema proves the closed request and response shapes. Semantic conformance
tests additionally prove state/action rules, idempotency, lineage, activity
liveness and count semantics, automatic publication, localized media failure,
and exact agreement with the existing PreCheck Result Mock.
