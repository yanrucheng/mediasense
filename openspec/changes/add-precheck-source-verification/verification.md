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
