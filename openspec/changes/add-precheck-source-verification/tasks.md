## 1. Public handoff contract

- [x] 1.1 Add `source_root_ref` to each source-root-relative Source Item locator without constraining a Result to one root.
- [x] 1.2 Define a replaceable `source_content_verification` observation without making SHA-256 or a path the Source Item identity.
- [x] 1.3 State Plan reference-only freezing and Apply fail-closed revalidation obligations without modifying the Apply worktree.

## 2. PreCheck implementation

- [x] 2.1 Project existing exact source-content proofs into eligible Source Items with profile, value, size, time, producer, and basis.
- [x] 2.2 Re-read and verify every projected source observation during the seal gate.
- [x] 2.3 Add contract and Result tests for relative locators, source-root binding, successful projection, and source drift refusal.
- [x] 2.4 Run the final repository quality and boundary gates and record them in verification.md.

## 3. Downstream integration

- [x] 3.1 Implement Apply-side resolution and verification in the dedicated Apply worktree after this contract is accepted.
- [x] 3.2 Obtain human acceptance of the PreCheck contract, producer, projection,
  and conformance evidence; keep the change active until Apply-side enforcement
  is implemented and accepted.
