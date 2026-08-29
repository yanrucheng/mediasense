## Automated evidence

- Focused provider, Run-confirmation, Result-projection, and zero-network tests are implemented in `tests/test_geocode.py` and `tests/test_precheck_orchestration.py`.
- Tests use only fake providers. No live provider, online map, or billable API is invoked.
- Focused orchestration/Result/geocode/source-validity/Artifact/Work/accounting: `100 passed`.
- Full fast suite: `259 passed, 7 deselected`.
- Read/Run contract conformance: `30 passed`.
- Full scale suite: `3 passed, 263 deselected`.
- Hong Kong ordinary verifier: passed; local read-only fixture tests: `4 passed`.
- OpenSpec strict: `3 passed, 0 failed`; Ruff check and format, lock, diff, secret, network, and source-write boundary scans passed.

## Legacy comparison

- `preserved`: c90 AMap/Google address and POI lookup, WGS84/GCJ02 handling, provider/language continuity, fallback, and rate limiting.
- `intentionally_changed`: queries run only for the post-compression frozen representative set; authorization is explicit and fingerprint-bound; actual provider requests and outcomes are retained.
- `regression`: none demonstrated by current characterization.
- `not_comparable`: durable pause/decision authority and Result effect proof have no c90 equivalent.

## Production certification

Live-provider smoke tests, quota and retention-policy review, switching-quality measurement, and real error/cost observations remain production certification. They do not authorize a live call in this change and do not block the default local path.
