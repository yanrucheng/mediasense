## 1. Baseline and shared boundary

- [x] 1.1 Develop from local commit `5813cef` or a descendant containing the active Plan contracts, preserve unrelated dirty files, and record the starting test result (`113 passed, 2 deselected`).
- [x] 1.2 Add the minimal `src/mediasense/plan/` package and public `work.py` boundary without adding repository, service, manifest, or copied-contract layers.
- [x] 1.3 Add reusable test fixtures that drive Plan only through the published PreCheck Read Mock and active Plan/Frozen Plan schemas.

## 2. Slice 1 — Create and inspect

- [x] 2.1 Implement the private SQLite schema for exact Result binding, open/closed lifecycle, current opaque revision, organization preferences, candidate state, and idempotency records.
- [x] 2.2 Implement `create` with strict `plan_ready + valid` entry checks through the injected PreCheck Read boundary.
- [x] 2.3 Implement current-revision and exact-revision `inspect` for overview, preferences, and initial validation state.
- [x] 2.4 Implement safe `create` replay and conflicting request-ID rejection.
- [x] 2.5 Add focused tests and record observable create/inspect request and response examples.

## 3. Slice 2 — Update, concurrency, and paging

- [x] 3.1 Implement complete candidate replacement and exact organization-preference replacement, preservation, and clearing semantics.
- [x] 3.2 Implement opaque revision advancement, stale `base_revision` refusal, update idempotency, and closed-Work refusal.
- [x] 3.3 Implement exact-revision content inspection and revision-bound cursors for groups, other outcomes, and decision notes.
- [x] 3.4 Add concurrency, replay, cursor misuse, and complete-page traversal tests, then record the observable outcomes.

## 4. Slice 3 — Candidate validation and identity

- [x] 4.1 Implement one candidate materialization path that combines the stored candidate with Tool-owned envelope fields without changing Agent decisions.
- [x] 4.2 Resolve source sets only through PreCheck Read and validate Result-local references, expansion closure, disjoint group/outcome coverage, and exact Result binding.
- [x] 4.3 Validate path segments, sibling names, source-name overrides, outcome forms, and other active Frozen Plan invariants with localized issues.
- [x] 4.4 Implement `mediasense-json-strings-sha256-v1` candidate canonicalization and global content identity shared by inspection pages.
- [x] 4.5 Add contract-vector, malformed-candidate, incomplete-coverage, duplicate-member, and identity tests, then record the observable outcomes.

## 5. Slice 4 — Revision-bound preview

- [x] 5.1 Build a reference preview from the verified Hong Kong fixture and Mock using the exact candidate materialization path and no network access.
- [x] 5.2 Render the final logical directory tree, per-directory expanded counts, deterministic representative samples, and explicit other outcomes.
- [x] 5.3 Add bounded directory-member drill-down and ensure every view remains bound to one Work revision and candidate identity.
- [x] 5.4 Report inaccessible or unavailable representative evidence without hiding directories, altering membership, or making semantic substitutions.
- [x] 5.5 Add deterministic regeneration, stale-preview, large-directory, escaping, and zero-egress tests.
- [x] 5.6 Present the first concrete preview for the required Human review checkpoint and pause before treating its presentation shape as accepted.
- [x] 5.7 Incorporate accepted review findings while keeping HTML or any other presentation technology outside the stable product contract.
- [x] 5.8 Make every empty-Candidate inspect that requests `content` return `candidate_invalid`, including the default all-sections request.
- [x] 5.9 Protect revision-bound cursors with a persistent HMAC key and reject malformed or tampered payloads.
- [x] 5.10 Gate seal readiness and candidate identity on the authoritative Frozen Plan Schema before semantic validation.
- [x] 5.11 Reject logical file destinations that collide with any logical directory path and cover the invariant in runtime and Frozen Plan semantic tests.

## 6. Slice 5 — Trusted seal and recoverable publication

- [x] 6.1 Define the injected trusted Human confirmation context and reject request-body self-assertion, missing authority, stale revision, and stale identity.
- [x] 6.2 Reserve one idempotent seal outcome and stable `plan_ref` under the Work serialization boundary.
- [x] 6.3 Serialize and verify the complete Frozen Plan, write a new temporary file, apply the durability policy, and atomically rename without replacement.
- [x] 6.4 Commit the SQLite close transition only for the verified published artifact and implement recovery for every interrupted publication boundary.
- [x] 6.5 Add conflict, corruption, missing-file, concurrent-seal, identical-retry, and successful conformance tests, then record observable outcomes.

## 7. Slice 6 — Plan Skill and end-to-end acceptance

- [x] 7.1 Create the repository-local `mediasense-plan` Skill after Tool and preview behavior are stable.
- [x] 7.2 Teach progressive Result inspection, epistemic separation, Default Profile use, preview-led revision, exact Human confirmation, and PreCheck reopen decisions without prescribing a fixed reasoning sequence.
- [x] 7.3 Run a Mock-driven Agent workflow from Result entry through proposal, preview feedback, revised preview, confirmation, and Frozen Plan seal.
- [x] 7.4 Compare relevant Plan behavior with AI Album and classify each material difference as `preserved`, `intentionally_changed`, `regression`, or `not_comparable` across functionality, model cost, reuse, user effort, uncertainty, and safety.
- [x] 7.5 Run the full non-local test suite and report Plan-layer completion separately from unavailable upstream production Evidence and real-fixture acceptance.
