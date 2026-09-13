## 0. Planning completion and handoff

- [x] 0.1 Define the proposed fields, behavior, responsibility boundaries, implementation order and acceptance criteria in this OpenSpec. No implementation or executable test work is part of this step.
- [x] 0.2 The user assigned and explicitly authorized the implementation Agent on 2026-09-13. Development and isolated acceptance are authorized; daily installation and release remain outside this task.

## 1. Formal contract, shared values and request validation

Owner boundary: current Run/Read contract directories and their packaged snapshots, `precheck/run.py`, `_orchestrator.py` configuration value, existing runtime schema validation, and a small internal profile-value module if responsibility separation requires it. No new public Tool or registry.

- [ ] 1.0 Translate this design into canonical prose/schema and human-reviewable positive/negative exchanges; add their validation tests. Keep one contract authority and resolve any discrepancy against this design before implementing behavior. Do not redefine public behavior merely to make code pass.
- [ ] 1.1 Implement canonical preparation projection/identity from design section 1; expose recipe declarations through the existing composition root. Pass the fixed identity vectors, including scheduling/path exclusion and semantic-change invalidation.
- [ ] 1.2 Parse complete Profiles and explicit same-Result input Source Sets. Reject incomplete parameters, empty/non-media/outside/overlapping overrides and smaller outer snapshots before effects. Prove no implicit prior inheritance.
- [ ] 1.3 Freeze original request, current effective defaults and normalized scope membership in the ordinary Run. Preserve idempotent replay before mutable configuration checks and unchanged resume semantics.

Exit: one authoritative process-local representation and validated frozen inputs are available to downstream tasks; public schema examples and rejection vectors pass through the real Run boundary.

## 2. Capability reuse and demands

Owner boundary: `_work_sqlite.py`, producer dependency declarations, `_orchestrator.py` demand construction and existing resource admission. Do not edit public contracts to accommodate an implementation shortcut.

- [ ] 2.1 Audit semantic dependencies of metadata, renditions/video, embedding, sensitivity, association, Geo and final compression; remove whole-Run/whole-Profile invalidation where it is not a true dependency.
- [ ] 2.2 Build baseline preparation from fixed preparation settings and add directed override-member demands. Expand cross-boundary old bundles to actual members; prepare missing inputs without inheriting one representative's observations.
- [ ] 2.3 Preserve disabled-capability policy, locality, cost/effect authorization and explicit backend failures. Valid cache hits must not load models merely to read results.
- [ ] 2.4 Verify warm same-request reuse, local threshold-only reuse, missing selected inputs, changed model/recipe invalidation and unchanged sibling outputs.

Exit: producer call counts and input identities prove the real recomputation boundary; no interpretation or additional external authority has moved into PreCheck.

## 3. Run execution and immutable publication

Owner boundary: `_orchestrator.py`, `_compression_strategy.py`, `_compression_producer.py`, `_run_sqlite.py`, `_result_types.py`, `_result_assembly.py`, `_result_sqlite.py` and artifact retention.

- [ ] 3.1 Compose final compression independently within resolved partitions. Keep count fallback and threshold semantics; retain exact membership/basis when groups outside T change.
- [ ] 3.2 Verify explicitly selected input occurrences against the source attachment and observed revision; persist source-local binding evidence and honest verification strength.
- [ ] 3.3 Seal Profile, configuration projection, override membership and direct input bindings as ordinary Result-owned data. Historical missing data stays missing.
- [ ] 3.4 Prove interruption/recovery, known source-unavailable wait, source-revision refusal, idempotent publication, old Result readability and cache-eviction independence.

Exit: completed Results can be consumed without live Run/Work access, and each exact new request produces one new ordinary Run with at most one publication.

## 4. Read and Plan continuation

Owner boundary: `precheck/read.py`, `_read_projection.py`, existing Source Set interpretation, `plan/work.py` only if integration requires it, and the existing Plan/PreCheck Skill sources. Coordinate with the separate Plan preview implementation; use its current canonical field names.

- [ ] 4.1 Implement optional preparation readback, Result-local profile_scope resolution and bounded large-scope paging. Keep execution audit pagination and include exclusivity intact.
- [ ] 4.2 Implement direct-successor resolve correspondence, dual-Result cursor binding and complete per-input outcomes. Reject contradictory sealed lineage; report unproven instead of matching paths/digests heuristically.
- [ ] 4.3 Exercise a public-only Plan continuation: inspect old Work, verify source correspondence, create new Work, carry justified notes/preferences, inspect current Evidence, and save/review a new organization.
- [ ] 4.4 Update existing stage Skill guidance for the new ordinary Run path without prescribing a fixed conversation, semantic taxonomy or question for every item. No old confirmation transfer and no Work rebinding.

Exit: the Agent can complete the round trip with current public Tools and does not need private caches, vectors, Work tables or result-local reference guessing.

## 5. Integration and delivery acceptance

Owner boundary: `runtime/composition.py`, `host.py`, `mcp_host.py`, shipped schemas/Skill snapshots, focused contract/runtime tests, distribution smoke and the existing migration ledger.

- [ ] 5.1 Run the deterministic vertical acceptance matrix with real internal components through the same Host. Mock/schema validation alone does not close this item.
- [ ] 5.2 Update the stale `tests/scale/test_multiple_results.py` call shapes against the current contracts, then verify the round trip and measured cost breakdown at declared sizes.
- [ ] 5.3 Verify the focused failure/recovery suites and required repository checks; broaden testing only for uncovered integration concerns. Record exact builds and unrelated concurrent failures separately.
- [ ] 5.4 Build an isolated wheel and exercise installed CLI/MCP Run→Read→new Run→Read→Plan Work. Prove schema/Skill snapshot consistency and source read-only behavior with synthetic local inputs and no provider effects.
- [ ] 5.5 Record capability, configuration, composition, public delivery and migration outcomes in existing acceptance/ledger homes. Do not claim daily installation has upgraded or publish without the applicable authorization.

Exit: the second milestone is complete only with actual implementation and installed-entry evidence. The current design-only milestone cannot check these boxes.
