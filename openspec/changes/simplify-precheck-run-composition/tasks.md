## 0. Planning completion and handoff

- [x] 0.1 Define the proposed fields, behavior, responsibility boundaries, implementation order and acceptance criteria in this OpenSpec. No implementation or executable test work is part of this step.
- [x] 0.2 The user assigned and explicitly authorized the implementation Agent on 2026-09-13. Development and isolated acceptance are authorized; daily installation and release remain outside this task.

## 1. Formal contract, shared values and request validation

Owner boundary: current Run/Read contract directories and their packaged snapshots, `precheck/run.py`, `_orchestrator.py` configuration value, existing runtime schema validation, and a small internal profile-value module if responsibility separation requires it. No new public Tool or registry.

- [x] 1.0 Translate this design into canonical prose/schema and human-reviewable positive/negative exchanges; add their validation tests. Keep one contract authority and resolve any discrepancy against this design before implementing behavior. Do not redefine public behavior merely to make code pass.
- [x] 1.1 Implement canonical preparation projection/identity from design section 1; expose recipe declarations through the existing composition root. Pass the fixed identity vectors, including scheduling/path exclusion and semantic-change invalidation.
- [x] 1.2 Parse complete Profiles and explicit same-Result input Source Sets. Reject incomplete parameters, empty/non-media/outside/overlapping overrides and smaller outer snapshots before effects. Prove no implicit prior inheritance.
- [x] 1.3 Freeze original request, current effective defaults and normalized scope membership in the ordinary Run. Preserve idempotent replay before mutable configuration checks and unchanged resume semantics.

Exit: one authoritative process-local representation and validated frozen inputs are available to downstream tasks; public schema examples and rejection vectors pass through the real Run boundary.

## 2. Capability reuse and demands

Owner boundary: `_work_sqlite.py`, producer dependency declarations, `_orchestrator.py` demand construction and existing resource admission. Do not edit public contracts to accommodate an implementation shortcut.

- [x] 2.1 Audit semantic dependencies of metadata, renditions/video, embedding, sensitivity, association, Geo and final compression; remove whole-Run/whole-Profile invalidation where it is not a true dependency.
- [x] 2.2 Build baseline preparation from fixed preparation settings and add directed override-member demands. Expand cross-boundary old bundles to actual members; prepare missing inputs without inheriting one representative's observations.
- [x] 2.3 Preserve disabled-capability policy, locality, cost/effect authorization and explicit backend failures. Valid cache hits must not load models merely to read results.
- [x] 2.4 Verify warm same-request reuse, local threshold-only reuse, missing selected inputs, changed model/recipe invalidation and unchanged sibling outputs.

Exit: producer call counts and input identities prove the real recomputation boundary; no interpretation or additional external authority has moved into PreCheck.

## 3. Run execution and immutable publication

Owner boundary: `_orchestrator.py`, `_compression_strategy.py`, `_compression_producer.py`, `_run_sqlite.py`, `_result_types.py`, `_result_assembly.py`, `_result_sqlite.py` and artifact retention.

- [x] 3.1 Compose final compression independently within resolved partitions. Keep count fallback and threshold semantics; retain exact membership/basis when groups outside T change.
- [x] 3.2 Verify explicitly selected input occurrences against the source attachment and observed revision; persist source-local binding evidence and honest verification strength.
- [x] 3.3 Seal Profile, configuration projection, override membership and direct input bindings as ordinary Result-owned data. Historical missing data stays missing.
- [x] 3.4 Prove interruption/recovery, known source-unavailable wait, source-revision refusal, idempotent publication, old Result readability and cache-eviction independence.

Exit: completed Results can be consumed without live Run/Work access, and each exact new request produces one new ordinary Run with at most one publication.

## 4. Read and Plan continuation

Owner boundary: `precheck/read.py`, `_read_projection.py`, existing Source Set interpretation, `plan/work.py` only if integration requires it, and the existing Plan/PreCheck Skill sources. Coordinate with the separate Plan preview implementation; use its current canonical field names.

- [x] 4.1 Implement optional preparation readback, Result-local profile_scope resolution and bounded large-scope paging. Keep execution audit pagination and include exclusivity intact.
- [x] 4.2 Implement direct-successor resolve correspondence, dual-Result cursor binding and complete per-input outcomes. Reject contradictory sealed lineage; report unproven instead of matching paths/digests heuristically.
- [x] 4.3 Exercise a public-only Plan continuation: inspect old Work, verify source correspondence, create new Work, carry justified notes/preferences, inspect current Evidence, and save/review a new organization.
- [x] 4.4 Update existing stage Skill guidance for the new ordinary Run path without prescribing a fixed conversation, semantic taxonomy or question for every item. No old confirmation transfer and no Work rebinding.

Exit: the Agent can complete the round trip with current public Tools and does not need private caches, vectors, Work tables or result-local reference guessing.

## 5. Integration and delivery acceptance

Owner boundary: `runtime/composition.py`, `host.py`, `mcp_host.py`, shipped schemas/Skill snapshots, focused contract/runtime tests, distribution smoke and the existing migration ledger.

- [x] 5.1 Run the deterministic vertical acceptance matrix with real internal components through the same Host. Mock/schema validation alone does not close this item.
- [x] 5.2 Update the stale `tests/scale/test_multiple_results.py` call shapes against the current contracts, then verify the round trip and measured cost breakdown at declared sizes.
- [x] 5.3 Verify the focused failure/recovery suites and required repository checks; broaden testing only for uncovered integration concerns. Record exact builds and unrelated concurrent failures separately.
- [x] 5.4 Build an isolated wheel and exercise installed CLI/MCP Run→Read→new Run→Read→Plan Work. Prove schema/Skill snapshot consistency and source read-only behavior with synthetic local inputs and no provider effects.
- [x] 5.5 Record capability, configuration, composition, public delivery and migration outcomes in existing acceptance/ledger homes. Do not claim daily installation has upgraded or publish without the applicable authorization.

Exit: the second milestone is complete only with actual implementation and installed-entry evidence. The current design-only milestone cannot check these boxes.

验收结论与确切构建见 [acceptance.md](acceptance.md#实施验收记录2026-09-14)。勾选项表示该项自验完成，不代表整体成本验收、日常安装、发布或用户独立验收。r6 的 5.2 成本门槛曾未通过；本轮第 6 节完成独立重复测量和补修，已关闭该自验缺口。最终数据与限制见 acceptance 的独立验收补修记录，用户独立验收尚未执行。


## 6. 独立验收补修（2026-09-14）

本轮用户授权定位、补修、测试和隔离验收；未授权日常安装升级或发布。r6 的自验勾选是历史证据，不能覆盖独立验收发现的缺口。

- [x] 6.1 核对工作树与 r6 快照，保留并行改动；记录修复前冻结缺失/损坏与源变化误分类的失败反例。
- [x] 6.2 Run 执行必须读取原冻结要求；缺行、非法 JSON/null、被改动的输入/范围/Profile 终止执行，不能默认扫描或发布历史缺项 Result。历史 Result 独立读取、合法旧冻结 Run 恢复继续保留。
- [x] 6.3 SourceChangedDuringRead 映射为 failed/source_snapshot_changed；暂时读取不可用保留 blocked/source_verification_unavailable 和同 Run 恢复。覆盖初始与发布前核验。
- [x] 6.4 隔离 wheel 的 CLI/MCP 往返、三个故障注入、无重复发布、删除 Run 快照后的 Result 冷读取通过；准确构建及限制见 acceptance。
- [x] 6.5 每个规模和重复样本使用独立进程；固定暖工作区副本，区分 Run RSS 与进程累计峰值，完成基线/候选各三次的 4096/8192 成本比较及局部参数复用检查。
- [x] 6.6 根据阶段内存记录验证增量编码优化；保持相同规范封存字节、完整核验、全部输出和旧 Result 留存，完成成本归因与最终交接。

本轮全部补修自验完成后停止，等待独立验收；不继续日常安装、升级或发布。
