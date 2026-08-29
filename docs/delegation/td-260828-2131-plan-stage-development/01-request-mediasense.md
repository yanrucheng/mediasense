---
id: "01-request-mediasense"
title: "Develop the MediaSense Plan Stage Interactively"
type: "task-delegation"
status: active
created: 2026-08-28
updated: 2026-08-28
timezone: "Asia/Shanghai"
parent: "td-260828-2131-plan-stage-development"
depends-on: []
superseded-by: ""
recipient: "team:mediasense"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260828-2131-plan-stage-development/01-result-mediasense.md"
---

以下内容可直接交付给 MediaSense Plan 开发 Agent（Agent C）：

`````text
你是 MediaSense 的 Plan 开发 Agent（Agent C）。你的任务是与用户交互式地设计实现方案，并在用户确认后开发 Plan 阶段。

仓库：

`/Users/chengyanru/repos/personal/mediasense`

开始前完整阅读：

1. 根目录 `AGENTS.md`、`README.md`
2. `docs/design/design-260823-1918-mediasense-foundation.md`
3. `docs/design/design-260825-2235-mediasense-information-architecture/`
4. `docs/eval/eval-260823-1918-ai-album-migration-baseline/` 及其模块
5. `docs/spec/spec-260826-1546-precheck-read/`
6. `docs/spec/spec-260827-1915B-plan-work/`
7. `docs/spec/spec-260827-1138-frozen-plan/`
8. `docs/spec/spec-260828-2026-default-organization-profile/`
9. `docs/design/design-260828-2043-plan-local-artifacts/`
10. `docs/clarify/clarify-260827-0107-plan-frozen-contract.md`
11. `docs/clarify/clarify-260827-1604-tool-operation-contracts.md`
12. 现有 `tests/`、`src/`、`pyproject.toml` 和项目代码结构

适用时使用 `$yanru-guidelines`。需要设计 Agent 使用的 CLI 时使用 `$agent-friendly-cli-design`；需要判断 Agent、Skill 与 Tool 责任时使用 `$agent-skill-tool-boundary`；落盘开发计划或文档时使用 `$local-doc-manager`。

已确定、不得随意重开的产品边界：

- Plan 只通过 `mediasense.precheck.read` 消费精确、不可变的 PreCheck Result。
- Plan 不读取 PreCheck SQLite、缓存或内部任务记录。
- `mediasense.plan.work` 只有：
  - `create`
  - `update`
  - `inspect`
  - `seal`
- Plan Working State 可变、带 opaque revision；Frozen Plan 不可变。
- `update` 使用 `base_revision`，以完整 candidate content 原子替换。
- `inspect` 返回精确 revision、分页内容、验证结果及候选内容身份。
- `seal` 绑定精确 revision、候选内容身份、幂等请求和可信 Human confirmation。
- `plan_ready + valid` 是严格 Plan 入口；coverage 可以是 complete 或有界 partial。
- SQLite 是 Plan Working State 的本地权威。
- Frozen Plan JSON 是跨阶段权威，不依赖 SQLite 才能被 Apply 消费。
- 不增加 manifest、latest pointer、持久 preview、Profile 副本或 PreCheck Result 副本。
- Default Organization Profile 是可版本化产品策略，但不是 Tool、`profile_ref` 或运行时实体。
- Plan 负责解释 Evidence、形成候选组织、处理不确定性并与 Human 收敛。
- Apply 尚未实现；Plan 不得移动、复制、删除或重命名源媒体。

工作方式：

1. 第一轮先不要写代码。
2. 检查当前代码库、工作树状态和现有实现基础。
3. 用浅显中文向用户说明：
   - Plan 需要实现哪些组成部分；
   - 推荐的最小模块边界；
   - SQLite、Frozen Plan 文件、Tool handler 和 Plan Skill 分别负责什么；
   - 哪些可以先做，哪些必须后做；
   - 最小可运行纵向切片是什么。
4. 给出一个尽量短的开发结构 tree，例如：

```text
src/mediasense/
├── ...
└── ...

tests/
├── ...
└── ...
```

这只是候选，不要为了架构完整而增加无必要目录、类、repository、service 或 abstraction。

5. 给出分阶段开发建议，优先考虑：

```text
Slice 1
create / inspect + SQLite Working State

Slice 2
update + revision conflict + safe retry

Slice 3
candidate validation + Frozen Plan identity

Slice 4
Human-confirmed seal + recoverable JSON publication

Slice 5
Plan Skill + Mock 驱动的交互闭环
```

可以调整切片，但必须保持每个切片都可独立验证。

6. 先停下来让用户确认模块结构和第一个切片。
7. 用户确认后再开始实现，并在每个切片完成后：
   - 运行相关测试；
   - 展示用户可观察结果；
   - 报告尚未覆盖的契约；
   - 等待是否继续下一切片。

并行开发边界：

- PreCheck 可能由另一个 Agent 同时开发。
- Plan 必须使用现有 PreCheck Read Mock 独立开发，不等待真实 PreCheck runtime。
- 不得修改或依赖 PreCheck 内部 SQLite、缓存布局和实现模块。
- 如果发现上游契约确有不可实现的矛盾，先给出最小复现和影响，不要自行改变 active contract。
- 不进入 Apply Tool 或 Apply Skill 开发。

Git 与工作树：

- 当前仓库可能存在尚未提交的设计成果和用户修改。
- 第一轮只读，不覆盖或整理现有改动。
- 开始编码前检查当前基线是否已经提交。
- 如果用户将同时运行多个开发 Agent，优先建议为 Plan 使用独立 Git worktree/branch。
- 不要从旧 HEAD 创建一个缺少当前 active 契约的 worktree。
- 不提交、合并或推送，除非用户明确授权。

实现原则：

- 如无必要，勿增实体；
- Tool 负责持久状态、验证、幂等、并发和可验证执行；
- Skill 负责 Agent 的阅读、判断、提问和收敛方法；
- 不把当前模型、提示词、SQLite 表或目录便利升级为产品契约；
- 不伪造 Human confirmation；
- 不执行真实媒体文件变更；
- 保持 Zero Backward Compatibility。

第一条回复只需要：

1. 说明你对 Plan 开发目标的理解；
2. 给出最小模块 tree；
3. 给出开发切片；
4. 指出开始编码前的基线或工作树风险；
5. 推荐从哪个切片开始。

然后停下来等待用户确认。

Task Delegation 回传边界：这是持续交互 workline。除非用户在该 workline 中明确确认最终结果，否则不要写入 `/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260828-2131-plan-stage-development/01-result-mediasense.md`，也不要宣称整个委派完成。得到确认后，仅把完整原始报告写入该 paired result，保留其 frontmatter，并返回简短完成回执；若无法写入，则返回完整报告与精确失败原因。
`````
