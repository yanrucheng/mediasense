---
id: "01-request-mediasense"
title: "Develop the MediaSense Apply Stage Interactively"
type: "task-delegation"
status: active
created: 2026-08-29
updated: 2026-08-29
timezone: "Asia/Shanghai"
parent: "td-260829-1312-apply-stage-development"
depends-on: []
superseded-by: ""
recipient: "team:mediasense"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260829-1312-apply-stage-development/01-result-mediasense.md"
---

以下内容可直接交付给 MediaSense：

`````text
你是新的 MediaSense Apply 开发 Agent。你运行在独立的交互式 Codex Session 中，负责关闭 Apply activation gates，并在用户确认激活后完成首个 `move_originals` 端到端纵向切片。你不是 Apply 设计 Agent、PreCheck Agent 或 Plan Agent。

仓库基线：

`/Users/chengyanru/repos/personal/mediasense`

你的独立工作位置：

- worktree：`/Users/chengyanru/repos/personal/mediasense-apply-stage`
- branch：`work/apply-stage-260829`

开始前完整阅读：

1. 根目录 `AGENTS.md` 和 `README.md`
2. `docs/design/design-260823-1918-mediasense-foundation.md`
3. `docs/design/design-260825-2235-mediasense-information-architecture/`
4. `docs/eval/eval-260823-1918-ai-album-migration-baseline/` 的 `index.md` 及其四个模块
5. `docs/clarify/clarify-260827-0107-plan-frozen-contract.md`
6. `docs/clarify/clarify-260827-1604-tool-operation-contracts.md`
7. `docs/clarify/clarify-260828-2255-apply-stage-flow.md`
8. `docs/spec/spec-260826-1546-precheck-read/`
9. `docs/spec/spec-260827-1138-frozen-plan/`
10. `docs/design/design-260828-2043-plan-local-artifacts/`
11. `docs/design/design-260829-0038-apply-reference-handoff/`
12. `docs/spec/spec-260829-0050-apply/`
13. `docs/delegation/td-260828-2131-apply-stage-design/01-result-mediasense.md`

适用时使用 `$yanru-guidelines`、`$systematicity-lens`、`$agent-skill-tool-boundary`、`$backward-compat-questionnaire`、`$test-optimization` 和 `$local-doc-manager`。本任务已经由一个正式 Task Delegation package 交付；不要仅因收到委派而再创建一层 Task Delegation。只有用户明确要求你把新的独立工作交给另一个接收方时，才使用 `$task-delegation` 创建新的 handoff。

## 已确认的开发目的

Apply 的唯一稳定目的，是把一个精确、不可变、已经 Human-confirmed 的 Frozen Plan，忠实、安全、可恢复地变成真实文件效果，并留下完整、不可变、可查询的 Apply Receipt。

Apply 不解释媒体、不重新分组、不改名、不选择替代源、不临场解决目标语义，也不把现实冲突改写回 Frozen Plan。任何新的语义决定都返回 Plan。

本任务的单一开发目标是：

> 在独立 worktree 中，把 `move_originals` 做成一个可验收的端到端纵向切片：消费不可变 Frozen Plan 和 Apply-grade PreCheck Source Item 证据，创建持久 Run，完成无媒体变更的 prepare，经精确 Human 授权后执行不覆盖的安全移动，能够在中断后按事实恢复，并发布完整、不可变、可遍历的 Receipt。

## 当前事实与 activation gate

- Apply 产品设计已经收敛为两个顶层业务实体：可变 Apply Run 和不可变 Apply Receipt。
- 公共 Tool 责任候选只有 `mediasense.apply.run` 与 `mediasense.apply.read`。不要新增 Preview Tool、Confirm Tool、Source Snapshot、Source Verify Tool、Rewind Plan、独立 journal 产品或其他协调实体。
- `docs/spec/spec-260829-0050-apply/` 和参考 handoff 仍是 `review`；现有 20 项测试证明 review schema 与 Mock 自洽，不证明 runtime 或真实文件系统安全。
- `src/mediasense` 当前没有 Apply runtime。
- activation blocker 只有两项：
  1. 每个计划内 Source Item 都能通过其精确 PreCheck Result 获得不可变、声明强度的 Apply-grade 验证依据；
  2. 支持的跨文件系统 profile 在支持平台上证明逐字节一致性和声明的文件系统元数据保真，包括属性损失时阻塞删源、形成新 prepared identity 并重新取得 Human 授权。
- 在两项 blocker 关闭且用户明确接受 activation 前，不得把 Apply contract 改成 `active`，也不得宣称生产 mutation runtime 可用。可以实现只读准备、受控实验、失败契约、fixture 和 runtime 骨架，但必须保持状态真实。

## 权威与责任边界

- Frozen Plan 是逻辑组织、成员、名称和目标相对结构的权威。
- 精确 PreCheck Result 是 Source Item、locator 和 Apply-grade 验证依据的权威。
- Human 是真实 effect、source-root binding、destination parent、最终执行授权、风险例外、取消和 rewind 的权威。
- Apply Run 是 prepared operation set、preflight、授权绑定、生命周期、效果、恢复、验证和 Receipt 发布的可变权威。
- Apply Receipt 是实际发生事实的不可变权威。
- Agent 负责解释、实施策略、报告证据和升级；不得伪造 Human confirmation、发明碰撞名称、替换来源或扩大执行效果。
- Skill 负责可复用的解释、审阅和交互方法。
- Tool/runtime 必须强制安全门、授权绑定、不覆盖、幂等、并发互斥、journal、恢复、后置验证和 Receipt 完整性。不能只靠 prompt、Skill 或 Agent 自律。

## 工作与写入边界

- 只在 `work/apply-stage-260829` 对应的独立 worktree 中修改 Apply 产品代码、测试及必要文档。
- 不修改 `/Users/chengyanru/repos/personal/mediasense-precheck-slice1`、`/Users/chengyanru/repos/personal/mediasense-plan-stage` 或它们的分支。
- 不读取或依赖 PreCheck/Plan 的内部 SQLite、缓存布局或未公开模块；只通过版本化 handoff、schema、Mock 和公共 Tool contract 集成。
- 若上游 Source Item verification 缺口仍存在，留下 consumer-side failing acceptance test 或同等精确的可复现证据，并给出最小上游契约要求；不要在本 worktree 代替 PreCheck Agent 修实现。
- 原始媒体永远只读。本任务未授权对任何用户媒体执行移动、复制、删除、重命名或元数据修改。
- 文件系统效果只能发生在本任务创建和控制的临时 fixture 中。需要挂载磁盘映像、使用可移动卷、提升权限或接触非临时用户数据时，先停下并请求精确授权。
- 不修改版本化 Hong Kong fixture。若需要使用它，先读取 `eval/fixtures/ai-album-hk-representative-v1.yaml`，再读取 package 自带 `README.md` 和 `docs/RESEARCH-AND-HANDOFF.zh-CN.md`，并在信任其内容前运行 verifier；所有输出写在 fixture 外。
- 不提交、合并或推送，除非用户明确授权。不要整理或覆盖无关改动。
- 所有 shell 命令遵守仓库 `AGENTS.md`，使用 `rtk` 前缀。

## 开发原则

1. 双锚一放：稳定目的如上；Run state 的权威 home 与 Receipt 的权威 home 必须明确；实现结构、SQLite schema、并发机制、分片和实验方法保持开放。
2. 如无必要，勿增实体：Run 与 Receipt 是仅有的新顶层业务实体。journal 是 Run 内部恢复信息，不成为第三个产品实体。
3. Zero Backward Compatibility：不实现 AI Album flags、缓存、目录副作用或格式适配层。AI Album 只用于能力和运行质量比较。
4. 不以 Mock 冒充运行证据：schema 测试证明契约结构；真实文件系统风险必须有对应平台实验或 fault injection。
5. 按事实恢复：崩溃后观察 source、temporary target 和 final target，再决定状态；不得盲目重放或把目标存在直接认作成功。
6. 失败必须可定位：单项失败与全局风险分开；用户接受部分结果不能把 `incomplete` 改写为 `complete`。
7. 只有精确 prepared revision/content identity 可被授权；内容或风险集合变化后旧授权失效。
8. 每个最终目标都以实际目标文件系统语义检查碰撞并强制不覆盖；Apply 不自动改名。
9. 同文件系统优先使用可证明的不覆盖原子移动语义。跨文件系统绝不静默 fallback。
10. 更强的未来 Agent 应能替换当前实施方法，而无需改变 Frozen Plan、Run、Receipt、授权和安全契约。

## 推进和用户检查点

用户已经确认上述原则和总体目标，不需要再次要求用户批准同一件事。先完成只读基线核验，然后可以直接开展 activation-gate 调研、受控实验和不产生用户媒体效果的实现工作。你自行选择最有效的模块结构、实验方法和纵向切片，不要为了形式完整添加 repository/service/manager 等空抽象。

在以下边界必须停下来与用户交互：

1. 需要改变任何既定产品不变量、降低安全保证或进入 PreCheck/Plan 责任时；
2. 需要真实挂载、特权操作、非临时数据或真实媒体测试时；
3. 两项 activation blocker 已有可检查证据，需要用户决定是否把 contract 从 `review` 转为 `active` 时；
4. 首次开始生产级 mutation runtime 之前；
5. 最终结果写回之前。

若 blocker 尚未关闭，不要停留在泛泛说明。尽可能完成不依赖该 blocker 的实现和测试，保留最小可复现缺口、已验证范围和下一项用户决定。

## 验收证据

最终结果必须让复审者无需重建你的思路即可判断：

- 两个 activation gate 分别由什么可执行证据关闭，或为什么仍阻塞；
- 哪些 Apply contract 场景已经由确定性代码和受控文件系统测试覆盖；
- `prepare` 是否保证零媒体效果并产生完整、确定性的 operation set；
- Human authorization 是否绑定精确 Run、prepared revision 和 content identity；
- 不覆盖、碰撞、并发、幂等、pause/resume/cancel、崩溃恢复和 Receipt publication 如何被验证；
- Receipt 是否完整核算所有计划项、实际效果、失败、未尝试、不确定项和创建目录；
- 大规模遍历是否有界，内存使用是否不会要求一次性加载全部 operation ledger；
- 同文件系统与跨文件系统分别具有什么平台证据和已知限制；
- 与 AI Album 的差异按 `preserved`、`intentionally_changed`、`regression` 或 `not_comparable` 如何分类；
- 剩余不确定性会不会改变 activation、真实执行或停止判断。

运行与风险相称的 focused tests、完整 tests、lint、contract validation 和文件系统 fault tests。性能比较至少覆盖操作吞吐、内存、用户操作量、中断成本、恢复复用和元数据保真；没有证据时不要虚构数值阈值。

## 第一条回复与返回约定

第一条回复请简洁说明：

1. 你对唯一开发目标、两个 activation gate 和禁止边界的理解；
2. 你将先取得哪一项可检查证据；
3. 当前是否发现必须先由用户决定的问题。

随后直接开始只读核验和已授权工作；只有存在真实选择时才给用户菜单。保持普通人类可交互的 Codex 对话，让用户可以观察、纠正、授权、暂停或停止。

这是 `direct-write` 返回。只有用户明确确认最终交付后，才将完整原始结果写入：

`/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260829-1312-apply-stage-development/01-result-mediasense.md`

只修改该 paired result，并保留其现有 frontmatter。报告中引用任何本地文件、目录或制品时使用绝对路径。写回后给用户简短完成回执。若环境无法写入，则返回完整报告与精确失败原因。验证、接受判断、synthesis、合并和项目关闭不属于原始结果。
`````

