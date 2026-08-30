---
id: "eval-260829-1350-apply-activation-evidence"
title: "Apply Activation Evidence"
type: eval
status: active
created: 2026-08-29
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "spec-260829-0050-apply"
depends-on:
  - "spec-260826-1546-precheck-read"
  - "spec-260827-1138-frozen-plan"
  - "design-260829-0038-apply-reference-handoff"
superseded-by: ""
---

# Apply Activation Evidence

## Purpose and boundary

This evaluation is the inspectable activation record for the first
`move_originals` vertical slice. It distinguishes contract evidence, read-only
preparation evidence, controlled filesystem evidence, and production mutation
evidence. A passing schema or Mock test is never counted as filesystem safety
evidence.

The Apply contract is `active` for the first `move_originals` profile. The
implementation in `src/mediasense/apply/` exposes the contracted Run and Receipt
boundaries, performs no media effects during preparation, and starts mutation
only after trusted Human context authorizes the exact prepared revision and
content identity. Repository tests use controlled temporary roots only.

## Responsibility allocation

| Responsibility | Owner and authority | Current evidence | Escalation boundary |
| --- | --- | --- | --- |
| Logical membership, names, and relative targets | Exact Human-confirmed Frozen Plan | Seal identity and final confirmation are checked before preparation | Any new semantic decision returns to Plan |
| Source Item, locator, root association, and verification claim | Exact immutable PreCheck Result | Consumer parser and activation acceptance test define the minimum usable evidence | Missing or weaker evidence blocks preparation; Apply does not synthesize it |
| Current source-root and destination bindings | Human | Inputs are bound to observed filesystem identities in prepared content | Binding changes produce different prepared content and require new authorization |
| Prepared operation set, preflight, lifecycle, and ledger | Apply Run | Durable SQLite Run and bounded ledger traversal | Any material re-preparation invalidates old authorization coordinates |
| Effect authorization and risk exceptions | Human through a trusted Tool host | `ApplyConfirmationContext` is converted to a binding outside the public request and checked against exact prepared coordinates | Request fields cannot self-assert Human authority |
| File effects, non-overwrite, recovery, verification, Receipt publication | Apply Tool/runtime | Controlled end-to-end and injected-fault tests cover same-filesystem execution; the accepted Darwin probe covers the cross-filesystem profile | Unsupported platforms, ACL-bearing sources, unsafe bindings, and indeterminate effects stop fail-closed |
| Actual immutable outcome | Apply Receipt | Runtime publication, integrity, bounded Read, restart, incomplete closure, and rewind tests | Receipt history is immutable; repair proceeds through a new Run |

## Agent workflow Skill evidence

`.agents/skills/mediasense-apply/` packages only the reusable interaction
procedure: prepare one exact Frozen Plan, explain status, obtain exact Human
confirmation, operate allowed controls, read the immutable Receipt, and prepare
a newly authorized whole-Run rewind. It does not persist state, manufacture
confirmation, perform filesystem I/O, or reinterpret organization semantics.

Fixture-driven tests exercise the real Run and Read Tool adapters from Frozen
Plan through Receipt and rewind. Separate fixtures prove that the workflow stops
at a preparation blocker, refuses blind retry after source drift, and reports a
partially completed Run before resuming only an allowed recoverable failure.

## Activation gate status

| Gate | Status | Executable evidence | Conclusion |
| --- | --- | --- | --- |
| Exact Result-scoped Apply-grade Source Item evidence | **Closed for `sha256-full-v1`** | `tests/test_apply_activation_gates.py`, `tests/test_apply_preparation.py`, and `tests/test_apply_precheck_integration.py` pass the accepted contract, fail-closed matrix, and a real sealed-Result path | Apply resolves each materialized item through exact `result_ref + source_item_ref`, binds the locator root, and re-reads size plus full SHA-256; unselected items may remain unverified |
| Supported cross-filesystem byte and metadata preservation | **Closed for the declared Darwin APFS profile** | `tests/test_apply_filesystem_profiles.py` passed both opt-in distinct-device cases against a disposable 64 MiB APFS image | Bytes, declared metadata including ownership, non-overwrite publication, loss blocking, identity renewal, and exact reauthorization were exercised |

### Accepted upstream contract and Apply enforcement

The accepted PreCheck contract keeps verification optional at the general
Source Item schema because excluded, unsupported, invalid, erroneous,
unresolved, and unselected items remain legitimate accounted facts. Apply owns
the narrower enforcement rule: every Source Item selected for `move_originals`
must resolve from the exact immutable Result to:

- a `source_root_relative_path` locator carrying `source_root_ref`;
- exactly one available `source_content_verification` observation;
- the supported `sha256-full-v1` profile with `value`, `size_bytes`,
  `observed_at`, and `producer`; and
- observation-level basis plus qualifications only when actual limitations
  exist.

Apply neither copies this proof into Frozen Plan nor turns SHA-256 into Source
Item identity. Unsupported future profiles block until deliberately implemented.

## Read-only preparation evidence

`ApplyRunStore.prepare_forward` currently proves the following without changing
source or destination media:

- verifies the Frozen Plan canonical content identity and exact Human final
  confirmation;
- expands source sets through a caller-supplied exact-Result resolver and rejects
  incomplete, duplicate, escaping, or multiply assigned membership;
- resolves each materialized Source Item through `mediasense.precheck.read`
  using exact `result_ref + source_item_ref`, binds its locator to one current
  root, rejects path spelling ambiguity and symlink traversal, reads the complete
  file, and checks size plus SHA-256 before and after a stable stat observation;
- derives target paths from the Frozen Plan only, preserves basenames unless the
  Plan explicitly overrides them, rejects source/destination overlap, existing
  targets, and conservative Darwin case/Unicode-equivalent collisions;
- persists the Run and item ledger incrementally, resumes an interrupted
  preparation, rejects idempotency-key reuse with different content, and prevents
  two locally visible active Runs from becoming authorizable over the same source
  object or target;
- derives prepared revision/content identity from the exact plan, bindings,
  observed facts, operation rows, and blockers; and
- validates authorization coordinates without recording authorization or
  starting effects; pre-execution cancellation is idempotent, publishes no
  Receipt, and reports proven zero media effects.

Preparation detects overlap within its authoritative Run store. At the effect
boundary, the production filesystem adapter also takes process-independent,
OS-account-wide reservations keyed by source filesystem identity and normalized
final target, so separate Run stores cannot concurrently mutate the same source
object or target. Native non-overwriting publication remains the final guard.

## Filesystem profile evidence

On macOS 26.4.1 arm64, the default temporary fixture test invokes the platform
`renamex_np` primitive with `RENAME_EXCL`. It establishes that an existing target
is not overwritten and both files remain unchanged on conflict. On success, the
move preserves the same filesystem object identity, bytes, POSIX mode,
ownership, modification time, creation time, flags, arbitrary extended
attributes, and Finder tags.

The cross-filesystem probe uses Darwin `copyfile` with
`COPYFILE_ALL | COPYFILE_EXCL | COPYFILE_NOFOLLOW`, verifies bytes and the same
declared metadata set on the non-final target, fsyncs the file and containing
directory, and publishes with `renamex_np(RENAME_EXCL)`. Its loss-injection case
removes Finder tags, proves the source is retained for absent or stale
authorization, derives a different prepared-content identity from the exact
discrepancy set, and deletes the source only when that changed identity is
supplied as the newly authorized identity.

The test runner created an ordinary temporary source directory and mounted a
disposable 64 MiB APFS image at a second task-owned temporary directory. The
probe rejected equal device IDs before testing. Both distinct-device cases
passed in 0.08 seconds, the image was ejected, and no probe mount or temporary
directory remained afterward.

An initial distinct-device execution found that a file created below the
set-group-ID `/private/tmp` source inherited GID `0`, while the mounted APFS
target assigned GID `20`; the probe correctly detected the difference while the
other declared fields matched. The ordinary preservation fixture now explicitly
uses the invoking user's primary group, which is representative of user-owned
media and lets the no-loss path prove ownership preservation. A source owner or
group that the process cannot reproduce remains an exact metadata discrepancy:
the source-deletion and reauthorization rule applies instead of silently
downgrading the profile.

The exact declared Darwin APFS profile covers byte content and logical length,
modification and creation timestamps, POSIX mode bits, owner and group IDs, BSD
flags, and every extended attribute including Finder tags. Access and metadata
change times are volatile observations rather than preservation claims.
Non-empty ACLs remain unsupported and must block preparation until separately
proved; the present fixture does not claim ACL preservation.

### Certified support matrix

| Boundary | Evidence-backed scope | Uncertified or blocked scope |
| --- | --- | --- |
| Same-filesystem move | Darwin APFS, native non-overwriting rename, full pre/post byte verification | Linux code path exists but has no current-host filesystem certification; Windows is unsupported |
| Cross-filesystem move | Darwin APFS-to-APFS disposable-image probe with `copyfile`, byte equality, declared metadata, and non-overwrite checks | Other filesystem pairs and platforms |
| ACL-bearing source | Same-filesystem rename retains the source object; detection is tested | Cross-filesystem deletion is blocked until ACL preservation has evidence |
| Remount/disconnect | Missing and same-path-rebound source/destination roots stop before a later effect and resume only after the original identity returns | No claim that path equality identifies a remounted volume |
| Run and Receipt storage | Local POSIX SQLite/immutable package paths with injected journal and publication failure recovery | Network/distributed filesystems and storage without verified locking/durability |

## Runtime, recovery, and scale evidence

The old activation xfail has been replaced by passing consumer enforcement:
the public PreCheck schema may omit verification for items not selected for a
dangerous effect, while Apply rejects every selected move without usable
Result-scoped evidence. The integration suite consumes a real sealed PreCheck
Result through `mediasense.precheck.read`; it does not read PreCheck SQLite or
copy verification hashes into Frozen Plan.

Controlled runtime tests exercise same-filesystem move, target non-overwrite,
effect-boundary source drift, source-object replacement, Run-store restart,
cross-store overlap reservation, local-failure continuation, global-risk stop,
pause/resume/cancel, exact metadata-loss reauthorization, ACL refusal, immutable
Receipt publication/read, rewind, and every injected intent/effect/directory/
publication fault point. Final repository-wide counts are recorded in the
OpenSpec validation before closure. The current full fast suite reports `405
passed, 12 deselected`; the Apply/Skill-focused suite reports `96 passed, 5
deselected`; the four fixture-driven Skill workflows pass; and the targeted
fault/recovery and production-boundary selection reports `18 passed, 57
deselected`.

Capacity/quota, permission/read-only, disconnected/stale-volume, and generic I/O
errors are normalized as global-risk outcomes. Durable intent remains available
for reconciliation; tests prove ENOSPC recovery does not start a later item,
journal failure precedes media effects, and Receipt permission loss converges on
the same immutable Receipt after storage recovers.

The opt-in scale suite covers two separate 100,000-item paths. Preparation
stages a synthetic 100,000-row Run and reads a 1,000-row page with a peak
allocation bound. Receipt scale packages 100,000 immutable operation facts into
content-bound physical segments, republishes safely across a restarted store,
and reads a 1,000-row page with a separate memory bound. Segment names remain an
internal method and never become business references. These tests do not claim
100,000 real-file hashing or move throughput. The complete opt-in scale suite
reports `6 passed, 411 deselected` on this development host.

A separate generated 512 MiB regular-file probe exercises the production
same-filesystem boundary, including full source and target SHA-256 reads. On the
current local APFS development volume it completed in 0.368 seconds, or 1,392.3
MiB/s of logical file size. This is warm local-fixture evidence, not a promise
for external disks, cold cache, network storage, or a real media collection.

## Legacy copy and link closure

The c90 source at `c90aa8f04fd0d3348284e0ad19e18462987b1af2` contradicts
its README wording: CLI `original` invokes `async_safe_move`, whose pinned
Jinnang 0.2.2 implementation attempts `os.rename` and silently falls back to
`copy2` plus deletion. There is no user-facing original-copy branch. Generic
`copy_with_meta` is used by thumbnail output and tests, tolerates metadata-copy
failure, and may overwrite through `copy2`; that is not an acceptable Apply
profile or migration baseline.

c90 `link` invokes `create_relative_symlink`: it creates a relative symbolic
link named after the source basename, leaves the source in place, and catches
errors by printing rather than returning durable accounting. Its documented
value is a pre-run preview before original movement. Plan preview preserves that
purpose without persistent links. A durable symlink profile remains deferred
because dangling links, remounted source identity, coexistence with later moves,
and reverse-operation policy require a separate Human-reviewed lifecycle. It is
not silently reinterpreted as a hard link. The c90 file-operation history adds
async wrappers, tests, typing, and formatting but no later journal, collision,
permission, remount, or recovery hardening that MediaSense would need to carry
forward.

## AI Album migration judgment

| Capability or operating quality | Classification | Current implementation status |
| --- | --- | --- |
| Complete original-media target derivation, hierarchy, and basename preservation | `preserved` | Implemented through controlled end-to-end `move_originals` execution |
| Automatic collision-name injection | `intentionally_changed` | Replaced by deterministic collision refusal |
| Same-filesystem move | `preserved` | Production-capable orchestration uses non-overwriting native rename and post-verification; temporary integration tests pass |
| Silent cross-filesystem copy-delete fallback | `intentionally_changed` | Replaced by disclosed verified transfer and metadata-loss reauthorization; distinct-device Darwin APFS probe passed |
| Original-file copy | `not_comparable` | c90 exposed no such runtime branch despite README wording; a new duplicate-retention profile remains deferred |
| Relative symbolic-link preview | `intentionally_changed` | The preview purpose is preserved by Plan; persistent symlink materialization remains explicitly deferred rather than weakened or redefined |
| Durable restart and per-item outcome accounting | `intentionally_changed` | Effect intent, reconciliation, recovery, immutable Receipt publication, and bounded Read are implemented |
| Mutation throughput and interruption cost | `not_comparable` | Synthetic 100,000-item state and Receipt tests pass, but no representative real-media throughput comparison has been run |
| Cache reuse | `not_comparable` | Apply consumes immutable upstream evidence and does not adopt AI Album caches |
| User effort | `intentionally_changed` | Exact prepared content requires explicit Human authorization; no measured end-to-end user study yet |

No regression is currently identified in the migrated `move_originals`
capability. Representative real-media throughput and broader filesystem
profiles remain capable of changing the operating-quality judgment.

## Continue, stop, and reopen conditions

Both activation gates are closed for the first supported profiles, and Human
authorization on 2026-08-30 activated the Apply contract and first
`move_originals` runtime. Reopen a gate if the accepted PreCheck projection
changes incompatibly, a new source-verification or filesystem profile is
supported, or new evidence contradicts the current platform result.

The repository supplies a mutation-capable Tool, but validation and evaluation
must continue to stop before operating on non-fixture media unless a Human
separately supplies the real paths and exact execution authorization. Reopen the
structure if upstream evidence cannot bind a Source Item to a current root
without a new top-level entity, or if platform evidence shows that the declared
metadata profile cannot be preserved or precisely disclosed.
