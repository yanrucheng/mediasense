> 2026-09-13 实施状态：用户已授权按本定案设计开发。当前接口权威已对齐至 [Plan Work 合约](../../../docs/spec/contract/plan-work/index.md)，实际验证与未验范围见 [实施记录](acceptance.md)。下文“本轮仅 Spec”描述保留为设计阶段历史范围，不限制已授权实施。

> 本文件是变更范围支撑；主方案见[README](README.md)。本包不顺带清理其他能力或历史设计。

## Why

用户需要在Plan讨论全过程查看当前已保存规划，现有入口却只有Agent自行制作的最终HTML；内部renderer只接受完整Candidate，无法交付部分目录、正常无候选状态或可操作的大集合浏览。本变更让工具承担持续可视化及精确版本交付，Agent继续负责理解、组织与讨论。

## What Changes

- **BREAKING**：Work用一份`organization_content`保存`draft`或`candidate`，取代只接受完整方案的`candidate_content`输入；仍不允许两份可独立修改的当前组织。
- **BREAKING**：inspect内容返回带kind的当前组织，预留Plan引用单独标为reserved_plan_ref；无效组织统一使用organization_invalid替代旧candidate_invalid。新增view交付观察不属于逐字重放的业务回执，失败时可报告已提交的业务回执。
- 草案校验已写部分，显示未安排范围；完整候选须由Agent明确提交并通过原有完整性检查。Frozen Plan格式和Source Set语言保持不变。
- create/update/seal结果及默认inspect提供工具管理的页面入口、精确版本入口和交付状态。页面来源限于Work、冻结后的Plan及绑定Result，不需要Agent写HTML或展示业务数据。
- **BREAKING**：可信确认同时绑定Work、所审阅revision和Candidate identity。用户已选择严格规则：工作说明更新也使旧确认失效；显示操作和幂等重放不改变revision。
- 明确保存回执与每次调用的页面交付观察、失败后恢复、旧版访问、真实分页及证据不可读的含义。
- 首版工程建议采用本机只读页面宿主；它是现有运行时的交付机制，不增加Plan业务实体、公共Confirm Tool或另一位Agent。

## Capabilities

### New Capabilities

无。复用现有Plan能力和责任边界。

### Modified Capabilities

- `plan-working-state`：部分草案、当前组织读取、严格确认绑定及保存/显示的结果边界。
- `plan-review-preview`：从空Work到冻结状态的自动入口、版本一致性、成员/说明/证据浏览、失败与恢复。
- `plan-agent-workflow`：尽早建立Work、保存讨论变化、使用工具入口和按确切版本请求接受。

## Impact

后续实现涉及Plan Work合约及公开样例、Plan存储/校验/发布、现有renderer、Runtime/CLI/MCP装配和Plan Skill。需要更新当前合约及其发布副本，并按单一安装runbook验证实际交付。原始媒体、已封存Result、Frozen Plan编码及Apply语义保持原职责。

本包当前是Spec与项目设计交付，未改变`docs/spec/contract/`、生产实现、安装环境或业务状态。用户已选择确认规则并授权继续完成设计；后续接口和工程细节在本包形成可审阅结果，不冒称已发布或已通过实现验收。
