---
id: "01-request-mediasense"
title: "Complete the MediaSense PreCheck Skill"
type: task-delegation
status: active
created: 2026-08-30
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "td-260830-1325-precheck-skill"
depends-on: []
superseded-by: ""
recipient: "team:mediasense"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260830-1325-precheck-skill/01-result-mediasense.md"
---

以下内容可直接交付给 MediaSense：

````text
你负责补齐 MediaSense 缺失的用户侧 `mediasense-precheck` Skill，并与用户交互式完成设计、实现和验收。

仓库：
/Users/chengyanru/repos/personal/mediasense

背景与遗漏原因：

- MediaSense 的 Foundation 明确定义三个用户侧 Skill：PreCheck、Plan、Apply。
- 当前仓库已有 `.agents/skills/mediasense-plan` 和 `.agents/skills/mediasense-apply`，但从未存在 `mediasense-precheck`。
- 原 PreCheck Agent 最初承接的是 Slice 1；后来用户要求同一 Agent 完成整个 PreCheck，并加入 OpenSpec治理，但正式完成清单没有同步加入 Skill。
- 因此 PreCheck Tool、Run、Read、Result、orchestration、来源验证、压缩和地理反编码已经完成并合入 main，但用户侧 Skill 被遗漏。这是交付缺口，不是“有意不需要 Skill”的产品决策。

你的唯一目标是关闭这个 Skill 缺口。不要重写 PreCheck runtime，也不要因为 Skill 编写方便而修改公共契约、Plan 或 Apply。若发现真实契约矛盾，先向用户展示证据和影响，等待确认。

必须使用并完整遵循：

- 仓库 `AGENTS.md`；
- `$skill-creator`；
- `$yanru-guidelines`；
- `$agent-skill-tool-boundary`；
- 必要时 `$local-doc-manager`；
- OpenSpec 作为 change proposal/spec/tasks/verification/acceptance 治理载体。

先完整阅读至少以下权威材料：

- `README.md`
- `docs/design/design-260823-1918-mediasense-foundation.md`
- PreCheck Information Architecture、Clarification、Implementation Design
- 正式 `mediasense.precheck.run` 与 `mediasense.precheck.read` contracts、Mocks
- 当前 active/archived PreCheck OpenSpec specs
- capability ledger
- `.agents/skills/mediasense-plan/SKILL.md`
- `.agents/skills/mediasense-apply/SKILL.md`

第一轮只做只读理解并和用户讨论，不立即写 Skill。你的第一条实质回复应说明：

1. PreCheck Skill 的稳定目的和适用/不适用请求；
2. Human、Agent、Skill、Run Tool、Read Tool 各自负责什么；
3. Skill 应怎样引导 Dataset 边界、运行 profile、压缩目标和可选地理反编码确认；
4. 怎样处理 running、paused、blocked、cancelled、failed、partial、plan_ready 等状态；
5. 怎样支持 500→3→200 反复调压缩且不把算法写死；
6. 怎样把 exact `result_ref` 交给 Plan，并避免承担 Plan 的语义判断或 Apply 的文件操作；
7. 你准备用哪些真实交互场景验证 Skill；
8. 仍需用户确认的少量产品问题。

等待用户确认该理解后，再开始实施。

实施要求：

- 先建立一个小型 `add-precheck-skill` OpenSpec change；不要创建覆盖整个 PreCheck 的巨型 change。
- 在任何代码或文档修改前，先向用户建议并确认独立 Git worktree/branch；不得直接污染 main 或覆盖其他工作。
- Skill 的权威 home 是 `.agents/skills/mediasense-precheck/`。
- 使用 skill-creator 的 initializer/validator；只创建确有用途的 `SKILL.md`、`agents/openai.yaml` 和必要 references/scripts，不要生成 README 或无用脚手架。
- 默认允许正常自动发现；不要擅自改成 explicit-only。
- Skill 应保留方法开放性：不把 clustering、SQLite、SHA-256、ExifTool、FFmpeg、模型、阈值、目录布局或固定 profile 提升为 Skill 的永久方法。
- Skill 不复制 Tool schema，也不成为运行状态、用户授权或 Result 的第二权威；引用正式 Tool/contract，并教 Agent如何解释与使用。
- Skill 不执行 I/O。实际发现、长任务、状态变化、确认约束、封存和读取必须通过 Tool 边界。
- 当前 PreCheck 是 local-first、外部调用默认关闭；唯一已确认的在线例外是压缩后冻结、去重坐标集合的反向地理编码，必须先显示准确逻辑查询数并取得匹配确认。不得把它扩张为媒体、特征、prompt 或普通 metadata 外传。
- 所有 accounted Source Items 必须通过 normal frontier 或明确 auxiliary/excluded/unsupported/invalid/error/unresolved 路径可达；Skill 不要求每个来源都有视觉 Evidence。
- Plan 只通过精确 immutable `result_ref` 使用 `mediasense.precheck.read`；Skill 不让 Plan 读取 PreCheck SQLite/cache。
- 遇到证据不足时，应指导重新压缩、展开 Evidence、局部重建或形成明确 partial/blocked Result，而不是隐藏未知。

行为验证不能只跑 frontmatter validator。至少用独立、现实的 Agent 场景前向测试：

- 首次处理一个大型 Dataset，选择合适的初始压缩目的；
- 用户对 500 份 Evidence 不满意，改成 3，再改成 200；
- 运行中断、磁盘断开、空间不足、单项媒体损坏；
- 默认禁用在线调用，以及地理反编码冻结集合确认/跳过；
- 得到 partial 但 plan_ready 的 Result；
- Result blocked，需要用户决定继续、局部重建或停止；
- 成功后将 exact `result_ref` 交给 Plan；
- 误触发防护：用户正在 Plan 中命名、或 Apply 中执行文件操作时，PreCheck Skill不接管。

验收至少包括：

- skill-creator quick validation；
- OpenSpec strict validation；
- Skill 激活与负面激活测试；
- 场景中 Tool选择、用户确认、状态解释、恢复与阶段交接均符合契约；
- 仓库快速测试、Ruff、format、lock、`git diff --check`；
- 不修改原始媒体，不运行 fresh replay、远程模型、在线地图或收费 API。

完成后先向用户提交可审阅报告，明确 Skill 的责任、测试证据、剩余限制和变更范围。必须等待用户明确接受，才能写入下面的 paired result；不要自行提交、合并或 push：

/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260830-1325-precheck-skill/01-result-mediasense.md

写回时保持原始完成报告，不在 result 中替用户作最终接受判断；综合验收仍由发起方负责。
````

