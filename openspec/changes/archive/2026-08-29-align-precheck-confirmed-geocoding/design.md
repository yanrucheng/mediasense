## Context

MediaSense previously described PreCheck as absolutely offline. The approved
boundary is narrower and more useful: PreCheck is local-first and permits an
optional coordinate-only enrichment after compression has reduced the source
population to a frozen query set. The existing Run pause/decision fields,
reverse-geocode producer, shared geo adapter, and Result execution boundary are
the authoritative homes for this behavior.

## Goals / Non-Goals

**Goals:**

- remove contradictory absolute-offline wording;
- keep confirmation exact, durable, and bound to the frozen set;
- preserve c90's useful AMap/Google datum, nearby, continuity, fallback, and
  rate-limit behavior with complete semantic dependencies;
- make actual effects and uncertainty visible in the immutable Result.

**Non-Goals:**

- media, feature, metadata, or prompt egress;
- remote models, automatic account spending, or general network permission;
- a provider registry, geography service, or new public Tool;
- predicting provider-specific request amplification before querying.

## Decisions

The existing generic Run confirmation is reused. It reports one exact logical
query count because Google nearby/fallback amplification is not knowable in
advance; actual provider requests and billable impact are recorded afterward.
The decision fingerprint covers the ordered Work/query set and effective
profile, so progress does not invalidate an authorization but changed scope
does.

`mediasense.geo` remains a stage-neutral adapter library. PreCheck owns the
post-compression producer and immutable candidate Evidence; Plan owns whether
and how to use a place candidate. Provider continuity is explicit batch state,
and a downstream query depends on the preceding route-observation Work so cache
reuse cannot erase sequence semantics. API keys remain in adapter memory only.

## Risks / Trade-offs

- Provider calls per logical query can vary. → Report the exact logical count
  before authorization and actual request count afterward; never invent a cost
  estimate.
- Provider data and policy can drift. → Include an explicit refresh token and
  effective provider profile in Work identity; new observations produce a new
  Result rather than mutating one.
- A long confirmed batch may be interrupted. → Persist completed Work and the
  frozen-set fingerprint; resume only the remaining Work under the same scope.

## Migration Plan

Align existing authority documents and Run examples, retain the current
default-zero path, verify with fake providers only, and keep this change active
for human review. No archive or real provider call occurs in this worktree.

## Open Questions

None for the product boundary. Provider-specific production quotas, retention
terms, and live switching quality remain deployment certification rather than
contract ambiguity.
