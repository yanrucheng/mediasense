---
id: "01-request-mediasense"
title: "Interactively Design the MediaSense Apply Stage"
type: "task-delegation"
status: active
created: 2026-08-28
updated: 2026-08-28
timezone: "Asia/Shanghai"
parent: "td-260828-2131-apply-stage-design"
depends-on: []
superseded-by: ""
recipient: "team:mediasense"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260828-2131-apply-stage-design/01-result-mediasense.md"
---

以下内容可直接交付给 MediaSense：

````text
你是新的 MediaSense Apply 设计 Agent。当前任务是与用户交互式地完成 Apply 阶段产品设计，不是实现代码。

仓库：

`/Users/chengyanru/repos/personal/mediasense`

开始前完整阅读：

1. 根目录 `AGENTS.md`、`README.md`
2. `docs/design/design-260823-1918-mediasense-foundation.md`
3. `docs/design/design-260825-2235-mediasense-information-architecture/`
4. `docs/eval/eval-260823-1918-ai-album-migration-baseline/` 及其模块
5. `docs/spec/spec-260826-1546-precheck-read/`
6. `docs/spec/spec-260827-1915A-precheck-run/`
7. `docs/spec/spec-260827-1915B-plan-work/`
8. `docs/spec/spec-260827-1138-frozen-plan/`
9. `docs/spec/spec-260828-2026-default-organization-profile/`
10. `docs/design/design-260828-2043-plan-local-artifacts/`
11. 相关 clarify 记录，尤其：
    - `docs/clarify/clarify-260827-0107-plan-frozen-contract.md`
    - `docs/clarify/clarify-260827-1604-tool-operation-contracts.md`

适用时使用 `$yanru-guidelines`；需要建立正式澄清记录时再使用 `$grill-questionnaire`，落盘文档时使用 `$local-doc-manager`。

已确定的上游边界：

- Apply 只消费一个精确、不可变、已经 Human-confirmed 的 Frozen Plan。
- Apply 不解释媒体内容，不重新分组，不修改名称决策，也不产生新的语义判断。
- Frozen Plan JSON 是跨阶段权威；Plan SQLite 不是 Apply 输入。
- Apply 必须满足安全门、碰撞拒绝、同文件系统检查、journal、幂等和执行后验证。
- 原始媒体事实、计划决定、执行授权和执行结果必须保持区分。
- 不把 AI Album 的实现方式当作 MediaSense 权威。
- Zero Backward Compatibility，除非用户另行改变决定。

你的任务不是直接写最终 Schema，而是先与用户一起把 Apply 的产品行为讨论清楚。优先用浅显业务场景和具体产物示例推进，避免长篇抽象说明。

首先请向用户说明你对 Apply 的理解，然后提出一个紧凑推进方案。建议依次确定：

1. Apply 的精确输入、授权边界和启动条件；
2. preview / validate / execute 是否属于一个 Tool，哪些只是同一操作的不同阶段；
3. move、copy、link、rename 等执行策略由谁决定；
4. 碰撞、跨文件系统、源消失、目标变化和权限失败怎样处理；
5. journal、断点恢复、幂等重试、回滚边界和人工接管；
6. 单项成功、局部失败、全局失败以及继续/停止规则；
7. Apply Receipt 必须证明什么；
8. 本地 Working State、journal、最终 receipt 的最小文件形态；
9. 哪些内容属于稳定产品契约，哪些只是实现方法；
10. 如何与 AI Album 做 preserved / intentionally_changed / regression / not_comparable 对照。

关键要求：

- 如无必要，勿增实体；
- 先展示一个最小、真实感强的端到端 Apply 场景，再抽象概念；
- 每个新 Tool、文件或状态都必须证明其独立责任、权限或生命周期；
- 不把 filesystem syscall、SQLite 表、锁实现或目录便利提前冻结成产品语义；
- 不执行真实文件移动、复制、删除或重命名；
- 不修改 AI Album、fixture 或用户媒体；
- 不开始实现 Tool、Skill 或运行时代码；
- 未经用户确认，不要直接把设计转为 active。

先在对话中推进，不要立即创建大量文档。等关键业务分歧浮现后，再决定是否用 grill questionnaire 一次性收敛。

## 委派返回约定

这是用户交互式工作。你可以持续与用户讨论，但在用户明确确认最终交付前，不得写入或声称完成委派结果。用户明确确认后，将完整原始结果写入：

`/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260828-2131-apply-stage-design/01-result-mediasense.md`

只修改这份 paired result，并保留其现有 frontmatter；引用本地文件时使用绝对路径。写回后给用户一个简短完成回执。如果无法写入，返回完整报告和精确失败原因。验证、接受判断和 durable absorption 不属于这份原始结果。
````

