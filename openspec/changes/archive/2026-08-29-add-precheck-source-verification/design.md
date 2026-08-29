## Context

PreCheck already computes full-content proofs to authorize Artifact reuse, but
those facts remain private. Frozen Plan intentionally carries only Result-local
references, leaving Apply unable to prove that current source bytes still match
the selected Source Item. The existing Source Item observation model is the
smallest authoritative home for this handoff.

## Goals / Non-Goals

**Goals:**

- expose a replaceable, sealed source verification observation;
- bind relative locators to an opaque Result-owned source-root reference;
- revalidate included observations at seal time;
- define the downstream fail-closed obligation without modifying Apply here.

**Non-Goals:**

- a permanent source identity or Dataset-wide snapshot;
- copying hashes into Frozen Plan;
- requiring Apply-grade proof for every exceptional or excluded Source Item;
- a new verification service, Tool, registry, or filesystem action.

## Decisions

Each Source Item locator gains `source_root_ref` and its locator value stays
relative to that root. The current single-root implementation derives the
reference from the Working Run's Dataset and reuse domain, not its absolute
path, so explicit unverified rebinding changes the reference without turning
location into Dataset identity. The public shape does not impose that current
single-root implementation limit on future multi-root Results.

The existing `observation` shape carries `source_content_verification`.
`sha256-full-v1` is the first supported profile because Artifact-producing Work
already computes it with descriptor-based, no-follow, pre/post-stat validation.
The value also carries byte length, observed time, and producer identity. Seal
recomputes every included proof and rejects drift. No new database authority is
needed: the existing source-content proof is projected into the Result.

Plan stores only `result_ref` and `source_item_ref`. Apply later resolves the
current observation from that exact immutable Result and performs its own read
immediately before the operation. An absent or unsupported profile is a hard
Apply preflight block, not permission to fall back to path or mtime.

## Risks / Trade-offs

- Full-byte seal revalidation adds I/O. → Include proofs only for eligible
  Source Items and keep the profile replaceable; never weaken correctness by
  substituting the sampled discovery fingerprint.
- A source root can move. → Use the existing audited attachment/rebind boundary
  and an opaque root reference; Apply must establish a safe current binding.
- The Read schema changes before Apply implements consumption. → Keep this as a
  separate active OpenSpec change and record Apply work explicitly; do not
  modify the Apply worktree in this change.

## Migration Plan

Add the proposed Read field and observation constraints, project existing exact
proofs, add seal-time checks and conformance tests, and leave the OpenSpec change
unarchived for human review. Existing unproved Source Items remain validly
accounted but cannot authorize Apply operations.

## Open Questions

No PreCheck semantic question remains. Platform-specific source-root rebinding
and the first Apply-side verifier implementation are explicitly downstream.
