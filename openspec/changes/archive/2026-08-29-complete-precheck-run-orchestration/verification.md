## Automated evidence

- `tests/test_precheck_orchestration.py` enters through `mediasense.precheck.run`, verifies that `start` returns before Work begins, and then uses only the private host-worker `advance` boundary rather than manually invoking producers or seal.
- It controls a live worker from another thread to prove external pause and cancel, then covers the complete selected local graph, item failure isolation, restart/resume, cross-Run reuse, pre/post seal crash windows, default zero network, and confirmed fake geocoding.
- `tests/scale/test_multiple_results.py` drives 500 → 3 → 200 through three public starts plus internal worker advancement and compares lower-level Work identities.
- Focused orchestration/Result/geocode/source-validity/Artifact/Work/accounting: `100 passed`.
- Full fast suite: `259 passed, 7 deselected`.
- Read/Run contract conformance: `30 passed`.
- Full scale suite: `3 passed, 263 deselected`; the Run-driven 500 → 3 → 200 test passed within that suite.
- Hong Kong ordinary verifier: passed; local read-only fixture tests: `4 passed`.
- OpenSpec strict: `3 passed, 0 failed`; Ruff check and format, lock, diff, secret, network, and source-write boundary scans passed.

## Legacy comparison

- `preserved`: c90 producer ordering, bounded stage concurrency, metadata/rendition/video/embedding/sensitivity/bundle/compression capabilities, and resumable reuse intent.
- `intentionally_changed`: durable semantic Work and dependencies replace cache flags; bounded lazy admission replaces eager whole-population task creation; item failure and partial output are explicit; Result publication is atomic and independently verifiable.
- `regression`: none demonstrated by current characterization.
- `not_comparable`: durable Run control, leases, source attachment, closure, immutable Result seal, and exact Read boundary have no c90 equivalent.

## Production certification

Pinned real-model quality, broader codec/RAW coverage, non-POSIX and removable-volume behavior, long process/GPU fault soak, and a real 1.5 TB run remain production certification. They are not substitutes for the integration-blocking Run-driven and contract tests in this change.
