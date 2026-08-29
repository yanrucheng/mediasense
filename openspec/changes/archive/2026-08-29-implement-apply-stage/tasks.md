## 1. Preserve accepted inputs

- [x] 1.1 Merge the existing Apply preparation, Gate 1 consumer enforcement, Gate 2 probes, and evidence into main without loss.
- [x] 1.2 Complete `add-precheck-source-verification` task 3.1 with real Result integration and fail-closed tests.

## 2. Runtime state and filesystem boundary

- [x] 2.1 Extend the private Run store for authorization, effect intent, attempts, observations, recovery, and Receipt publication.
- [x] 2.2 Implement non-overwriting same-filesystem move with source/target revalidation and directory accounting.
- [x] 2.3 Implement the accepted cross-filesystem content/metadata profile and exact discrepancy reauthorization path.

## 3. Lifecycle and recovery

- [x] 3.1 Implement execute, status, pause, resume, and post-authorization cancel semantics.
- [x] 3.2 Reconcile every journal/effect fault window without repeating completed effects.
- [x] 3.3 Isolate localized failures, stop on global risk, and preserve truthful incomplete outcomes.

## 4. Receipt and read boundary

- [x] 4.1 Build and schema-validate complete immutable Receipts from the durable ledger.
- [x] 4.2 Publish Receipts atomically without replacement and recover interrupted publication.
- [x] 4.3 Implement bounded immutable Receipt inspect and traversal.

## 5. Activation and acceptance

- [x] 5.1 Add controlled end-to-end, negative, fault-recovery, and 100,000-item tests.
- [x] 5.2 Update Apply contract/evidence to close both gates and activate the contract.
- [x] 5.3 Run all tests, Ruff, format, lock, diff, and strict OpenSpec validation.
