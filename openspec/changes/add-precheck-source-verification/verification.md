## Automated evidence

- Result and Read conformance tests prove locator-level `source_root_ref`, source-root-relative path projection, multi-root schema acceptance, `sha256-full-v1` observation shape, and source change refusal at seal.
- Artifact validity tests separately prove that the sampled discovery fingerprint cannot authorize exact Artifact reuse.
- Focused orchestration/Result/geocode/source-validity/Artifact/Work/accounting: `100 passed`.
- Full fast suite: `259 passed, 7 deselected`.
- Read/Run contract conformance: `30 passed`.
- Full scale suite: `3 passed, 263 deselected`.
- Hong Kong ordinary verifier: passed; local read-only fixture tests: `4 passed`.
- OpenSpec strict: `3 passed, 0 failed`; Ruff check and format, lock, diff, secret, network, and source-write boundary scans passed.

## Authority and downstream work

PreCheck owns the sealed observation. Plan freezes only `result_ref` and `source_item_ref`. Apply must later resolve those references, safely bind each selected locator's source root, support the declared profile, re-read bytes immediately before effects, and block on missing, unknown, unsafe, or mismatched input. No Apply code is changed here.

## Legacy comparison

- `preserved`: c90's practical use of source hashing to reject stale derived output.
- `intentionally_changed`: full-content proof, explicit profile/provenance, source-root-relative handoff, and fail-closed downstream semantics replace cache-path/hash coupling.
- `regression`: none demonstrated by current characterization.
- `not_comparable`: Result-local Apply verification observation and source-root binding have no c90 equivalent.

## Apply-side enforcement evidence (2026-08-30)

- `src/mediasense/apply/preparation.py` resolves every Frozen Plan item selected
  for `move_originals` by calling the public `mediasense.precheck.read` boundary
  with its exact `result_ref` and `source_item_ref`. It does not accept caller-
  supplied verification facts as a substitute.
- The consumer accepts the contract's `source_root_relative_path` locator and
  `source_content_verification` observation, supports `sha256-full-v1`, binds
  observation-level basis plus producer/time provenance into prepared content,
  and re-reads current source bytes for exact size and full SHA-256 comparison.
- A separate read-only effect-boundary guard rechecks the prepared root and
  destination identities, target absence, source object identity, size, and full
  SHA-256 immediately before any future mutation implementation may proceed.
- Non-materialized Source Items may remain unverified. Missing, unavailable,
  failed, unknown-profile, malformed, wrong-result, unbound-root, escaping,
  aliased, mismatched, or concurrently changing selected sources block the Run
  with zero destination effects.
- `tests/test_apply_precheck_integration.py` creates and seals a real PreCheck
  Result through public APIs, reads it through `PrecheckReadTool`, and reaches a
  verified Apply `ready_for_authorization` state without changing source or
  destination media.
- Focused Apply contract, negative-path, preparation, and real-Result integration:
  `32 passed, 1 deselected`.
- Combined PreCheck Read/Result/source-validity and Apply integration suite:
  `63 passed, 1 deselected`.
- Full fast suite after integration: `355 passed, 10 deselected` in 24.66
  seconds on the restored worktree.
- Apply 100,000-item bounded-ledger scale test: `1 passed, 28 deselected` in
  1.55 seconds; traversal remains capped at 1,000 rows and below the asserted
  8 MiB peak allocation.
- Full repository scale suite: `4 passed, 361 deselected` in 80.33 seconds.
- The previously accepted Darwin APFS cross-filesystem evidence remains valid;
  no transfer implementation used by that evidence changed in this integration.
- Ruff check and format checks pass for all changed Apply source and tests.
- `openspec validate add-precheck-source-verification --strict` passes.

Apply Contract activation and production mutation remain separate Human
decisions. This evidence completes implementation task 3.1 without changing the
Apply contract from `review`.
