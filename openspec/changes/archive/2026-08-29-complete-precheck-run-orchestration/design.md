## Context

All core PreCheck responsibilities already have focused implementations. The
missing layer is a private coordinator that turns the public Run lifecycle into
actual work. Its authority remains the Working Run; Work Records, Artifacts,
and Results retain their existing independent lifecycles.

## Goals / Non-Goals

**Goals:**

- make `start` durably prepare and return a configured Run for immediate worker
  scheduling;
- persist enough configuration to resume after process loss;
- use bounded scheduling and producer-level failure isolation;
- publish automatically through the existing Result seal gate.

**Non-Goals:**

- a daemon, distributed queue, Agent, plugin registry, or new public action;
- forcing every Run to execute every available producer;
- replacing producer-specific Work identities or failure semantics;
- implementing Plan, Frozen Plan, or Apply.

## Decisions

One internal orchestrator is owned by `PrecheckRunTool`. When `start` finds the
current unfinished, source-bound accounting Run, it fixes the execution
configuration and immediately returns the durable `run_ref`. The host invokes
private `advance(run_ref)` on a worker and reschedules it after an accepted
`resume`; neither public control call waits for the media pipeline. A lifecycle
record with no source-bound accounting Run remains controllable but does not
invent a source or silently begin work. The configuration is stored on the
Working Run, while model/provider adapters remain injected process resources
and never become serialized secrets.

The coordinator executes dependency layers rather than persisting a second job
graph. Re-entry enumerates the same demanded producers; existing semantic Work
records and Artifacts make this idempotent. A lightweight Run-owned checkpoint
is diagnostic only and is not authority for skipping work. Existing bounded
resource admission limits fan-out, and every scheduled call checks current Run
state before executing.

Images use ordinary rendition as frontier Evidence and high-resolution input
only when an enabled embedding or sensitivity producer needs it. Videos use
probe, bounded frames, optional frame embeddings/key-frame selection, and a
contact sheet. Metadata and explicitly discovered GPX inputs feed bundling and
compression. Reverse geocoding is attempted only after compression fixes the
representative set and can pause the Run before any request.

## Risks / Trade-offs

- A worker process or thread can stop independently from the caller. → All
  authoritative progress is durable; a restarted host calls the same private
  advance method and reuses completed work.
- Some local backends may be absent. → Only enabled optional profiles require
  them; expected item failures remain local, while a missing required backend
  blocks with a recovery condition.
- Re-deriving demand repeats inexpensive coordination queries. → Avoid a second
  cache or phase authority; producer Work and Artifact reuse prevents repeated
  expensive computation.
- Very large runs need bounded fan-out. → Reuse the existing resource executor
  and stream source-item call construction.

## Migration Plan

Add private Run configuration/checkpoint fields with an in-place schema
migration, add the internal coordinator and Run hook, extend Result projection
for video failures and optional-work omissions, then replace manual integration
claims with Run-driven tests. No Git commit or OpenSpec archive occurs before
human acceptance.

## Open Questions

None at the contract boundary. Host-process scheduling and UI presentation of
ongoing status remain integration concerns as long as they preserve the five
public actions and durable semantics.
