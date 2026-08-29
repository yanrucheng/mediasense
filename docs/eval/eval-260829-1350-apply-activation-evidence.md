---
id: "eval-260829-1350-apply-activation-evidence"
title: "Apply Activation Evidence"
type: eval
status: review
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

The Apply contract remains `review`. The implementation in
`src/mediasense/apply/` deliberately has no media-mutation entry point. Its only
writes are to a caller-selected Apply Run SQLite database; all source and
destination paths are read-only during preparation.

## Responsibility allocation

| Responsibility | Owner and authority | Current evidence | Escalation boundary |
| --- | --- | --- | --- |
| Logical membership, names, and relative targets | Exact Human-confirmed Frozen Plan | Seal identity and final confirmation are checked before preparation | Any new semantic decision returns to Plan |
| Source Item, locator, root association, and verification claim | Exact immutable PreCheck Result | Consumer parser and activation acceptance test define the minimum usable evidence | Missing or weaker evidence blocks preparation; Apply does not synthesize it |
| Current source-root and destination bindings | Human | Inputs are bound to observed filesystem identities in prepared content | Binding changes produce different prepared content and require new authorization |
| Prepared operation set, preflight, lifecycle, and ledger | Apply Run | Durable SQLite Run and bounded ledger traversal | Any material re-preparation invalidates old authorization coordinates |
| Effect authorization and risk exceptions | Human through a trusted Tool host | Exact revision/content guard exists; no authorization is recorded yet | Request fields cannot self-assert Human authority |
| File effects, non-overwrite, recovery, verification, Receipt publication | Apply Tool/runtime | Only controlled filesystem probes exist | Production mutation runtime cannot begin before activation approval |
| Actual immutable outcome | Apply Receipt | Review schema/Mock only | No runtime Receipt is claimed before execution exists |

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

`ApplyRunStore.revalidate_prepared_item` is the read-only guard reserved for the
future effect boundary. It rechecks source-root and destination identities,
target absence, exact source filesystem object, size, and full SHA-256. It has no
mutation capability, but prevents production execution from treating the
earlier prepare observation as timeless authority.

The current concurrency check is store-local. A production Tool must establish
one authoritative store/lock domain for every path it can mutate; separate
databases are not a safe concurrency boundary.

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

## Scale and test evidence

The focused Apply contract, negative-path, preparation, and real sealed-Result
integration suite reports `32 passed, 1 deselected` in 1.81 seconds. The old
activation xfail has been replaced by passing tests: the public schema may omit
verification for unselected Source Items, while the Apply consumer rejects every
selected move without a usable proof.

The full fast suite after integration reports `355 passed, 10 deselected` in
24.66 seconds on the restored worktree. The full repository scale suite reports
`4 passed, 361 deselected` in 80.33 seconds. Ruff check and format checks pass
for the changed Apply source and tests, and the source-verification OpenSpec
change passes strict validation.

The opt-in `scale` 100,000-item preparation/ledger test reports one pass in 1.55 seconds
on this development host. It stages and seals a synthetic 100,000-row Run, then
reads a 1,000-row page while asserting a peak allocation below 8 MiB for that
traversal. This establishes bounded ledger reading; it is not a claim about
100,000 real-file hashing throughput or production latency.

## AI Album migration judgment

| Capability or operating quality | Classification | Current implementation status |
| --- | --- | --- |
| Complete original-media target derivation, hierarchy, and basename preservation | `preserved` | Implemented for prepared operations; file effects are not active |
| Automatic collision-name injection | `intentionally_changed` | Replaced by deterministic collision refusal |
| Same-filesystem move | `preserved` | Darwin primitive proved in temporary fixtures; production orchestration not implemented |
| Silent cross-filesystem copy-delete fallback | `intentionally_changed` | Replaced by disclosed verified transfer and metadata-loss reauthorization; distinct-device Darwin APFS probe passed |
| Durable restart and per-item outcome accounting | `intentionally_changed` | Preparation ledger implemented; effect journal and Receipt publication remain pending |
| Mutation throughput and interruption cost | `not_comparable` | No production mutation runtime exists, so no honest AI Album comparison can yet be made |
| Cache reuse | `not_comparable` | Apply consumes immutable upstream evidence and does not adopt AI Album caches |
| User effort | `intentionally_changed` | Exact prepared content requires explicit Human authorization; no measured end-to-end user study yet |

No regression judgment is supported yet. Mutation throughput, full recovery,
and metadata fidelity remain capable of changing that conclusion.

## Continue, stop, and reopen conditions

Both pre-activation evidence gates are now closed for the first supported
profiles. The next decision is Human activation of the Apply contract. Reopen a
gate if the accepted PreCheck projection changes, a new source verification or
filesystem profile is supported, or new evidence contradicts the current
platform result.

Stop before changing the Apply contract to `active`, recording real Human
authorization, exposing a mutation entry point, or operating on non-fixture
media. Reopen the structure if the upstream evidence cannot bind a Source Item
to a current root without a new top-level entity, or if the platform probe shows
that the declared metadata profile cannot be preserved or precisely disclosed.
