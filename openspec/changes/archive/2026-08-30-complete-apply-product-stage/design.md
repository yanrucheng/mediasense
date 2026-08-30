## Context

Apply already owns a durable Run, immutable Receipt, public Run/Read Tools, and
an active `move_originals` profile. The missing product surface is reusable
Agent guidance plus explicit closure of legacy copy/link and production support
claims.

## Goals / Non-Goals

**Goals:**

- Give an Agent enough reusable guidance to operate Apply truthfully while all
  hard safety and state guarantees remain Tool-enforced.
- Close copy/link migration status from c90 evidence rather than README wording.
- Turn storage and volume failures into explicit fail-closed Run outcomes and
  retain bounded controlled scale evidence.

**Non-Goals:**

- No new organization semantics, workflow service, state store, authorization
  source, effect registry, or plugin system.
- No thumbnail output in Apply.
- No original-file copy, hard-link, or symbolic-link runtime profile in this
  change.
- No mutation of real user media.

## Decisions

### Skill remains procedural knowledge

`mediasense-apply` explains the prepared summary, blockers, warnings, route,
progress, recovery, Receipt, and rewind. It selects only actions already allowed
by Tool status. Trusted Human confirmation is supplied by the host and bound by
the Tool; the Skill never fabricates it. The Skill stores no state and cannot
claim that an accepted command completed.

### Legacy copy and link remain outside the active profile set

At c90, CLI `original` invokes `safe_move`; the README phrase "Copy original"
does not describe the implementation. Generic `copy_with_meta` is used for
derived thumbnails and tests, not as a user-facing original-copy mode. A new
copy profile would therefore need fresh authorization, retention, duplicate
accounting, and rewind semantics rather than being migration parity.

The c90 `link` mode creates relative symbolic links and leaves sources in place.
Its stated value is a pre-run preview before moving originals. MediaSense Plan
already owns a safer preview without persistent filesystem effects. A durable
link profile would additionally need an accepted policy for dangling links,
source-volume rebinding, post-Apply coexistence, and rewind. It is intentionally
deferred rather than silently redefined as hard links or added to the active
contract.

### Storage failures use existing Run/Receipt authority

Filesystem `errno` values are normalized at the existing effect boundary.
Capacity, permission, read-only-volume, stale/disconnected-volume, and I/O
failures stop new effects as global risk while retaining durable intent for
fact-based recovery. Receipt and journal publication failures remain recoverable
inside the same Run; no failure manager or secondary journal is introduced.

## Risks / Trade-offs

- **Skill tests cannot prove model wording** → Test the observable Tool call
  sequence and safety decisions with fixture-driven workflows, plus validate the
  Skill package structurally.
- **Temporary storage is not every production filesystem** → Publish a narrow
  certified matrix and keep unsupported combinations fail-closed.
- **Large-file tests consume local I/O** → Keep them opt-in under the existing
  `scale` marker and use generated temporary bytes only.
- **Deferring link can look like lost parity** → Record its actual c90 preview
  purpose and the Plan replacement explicitly in the migration ledger.

## Migration Plan

1. Add and validate the Skill and its controlled workflow fixtures.
2. Harden storage-error classification and add volume/failure tests.
3. Add opt-in large-file evidence and update the platform matrix.
4. Update contracts and migration disposition without changing active effect
   enums.
5. Run full validation, archive the change, and commit locally.

## Open Questions

None blocking. Copy and durable link materialization can be proposed later only
with independent Human-reviewed authorization and lifecycle semantics.
