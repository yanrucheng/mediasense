---
id: "01-request-mediasense"
title: "Complete and Accept MediaSense PreCheck Slice 1"
type: "task-delegation"
status: active
created: 2026-08-28
updated: 2026-08-28
timezone: "Asia/Shanghai"
parent: "td-260828-2125-precheck-slice1-completion"
depends-on: []
superseded-by: ""
recipient: "team:mediasense"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260828-2125-precheck-slice1-completion/01-result-mediasense.md"
---

以下内容可直接交付给 MediaSense：

````text
你位于 MediaSense 项目：

/Users/chengyanru/repos/personal/mediasense

你的目标是与用户共同完成并验收 PreCheck Slice 1。你拥有实现授权，但必须保持用户可观察、可纠正、可暂停；不要擅自提交 Git。

开场时请先简短确认：本任务所说的“Slice E”按当前上下文解释为“Slice 1”。

## Git worktree 隔离

当前路径是需要保护的主工作树。任何实现编辑前，先只读核对主工作树的 HEAD、已跟踪修改和未跟踪文件，然后与用户确认独立 Git worktree 的准确路径、基线以及承接相关未提交修改的方式。随后由你创建并进入该独立 worktree，在其中实施和测试；不要 stash、reset、checkout、clean 或覆盖主工作树，也不要让隔离 worktree 的改动回写主工作树。除最终结果得到用户明确确认后写入下述 paired result 外，不在主工作树产生实现修改。不要擅自创建提交。

独立 worktree 必须以主工作树当前真实状态为基线，而不是仅凭 HEAD 忽略已有未提交修改；应通过可审查、非破坏性的方式仅承接本任务需要的现有修改，并清楚区分继承修改与自己的新增工作。

请先完整阅读项目 `AGENTS.md`、根目录 `README.md`，以及：

- `docs/design/design-260823-1918-mediasense-foundation.md`
- `docs/design/design-260827-0022-precheck-implementation.md`
- `docs/clarify/clarify-260826-1819-precheck-contract-concepts.md`
- `docs/spec/spec-260826-1546-precheck-read/`
- `docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md`
- capability ledger 及其关联模块
- 当前 `src/mediasense/precheck/` 与相关 tests

以当前工作树为准。这里包含用户和其他 Agent 尚未提交的修改。禁止 reset、checkout、清理、覆盖或把其他改动算成自己的成果。

## 产品心智模型

MediaSense 的产品阶段是：

PreCheck → Plan → Apply

Slice 1–4 只是 PreCheck 内部的实施切片，不是新的产品阶段。

PreCheck 的稳定目的只有一个：把可能达到 1.5 TB、几十万文件的 Dataset 压缩成 Plan 可低成本开始阅读的可信证据，同时保持对全部来源的可追溯和可展开能力。

必须始终保持：

- 压缩是目的，聚类、embedding、thumbnail、SQLite、hash 和模型只是可替换方法。
- Dataset 长期存在；Result 针对明确核算边界封存且不可变。
- Source Item 是压缩前被核算的来源对象。
- rendition、视频帧、contact sheet 等派生内容不是 Source Item。
- 每个被 `accounts_for` 核算的 Source Item，必须能从默认 frontier 展开到达，或通过 auxiliary、excluded、unsupported、invalid、error、unresolved 等明确异常路径到达；不能静默消失。
- Plan 只通过 `mediasense.precheck.read` 读取 sealed Result，不读取 SQLite 或缓存目录。
- PreCheck 当前必须本地、离线、源只读、无远程模型、无在线地图、无收费调用。
- 语义责任决定阶段归属：来源派生、可复查且有 provenance 的候选观察可以属于 PreCheck；解释、命名、组织判断和用户确认属于 Plan；文件系统执行属于 Apply。
- 内部复用只依赖真正影响结果语义的最小集合：实际来源依据、直接上游结果、生产者身份、有效参数/模型/配置和必要环境条件。
- 禁止用应用版本、仓库提交、Dataset-wide snapshot 或完整配置文件作为粗粒度失效键。
- 不把 SQLite 表、缓存文件名、目录布局、hash、算法、模型、阈值或并行度升级为公共契约。
- 不引入没有独立责任、权威或生命周期的服务、实体、注册表、插件系统或统一 `Prepared Information Unit`。

## 当前已经完成

当前工作树已经实现并通过快速测试：

- 递归 discovery、scope/condition 核算及局部失败；
- SQLite Accounting Closure；
- scan generation、中断恢复、删除/重命名 reconciliation；
- 增量发现和候选指纹；
- run-scoped source attachment；
- 安全重挂载、显式 rebind audit 和 reuse-domain 隔离；
- 文件系统能力观测；
- Work Record 的语义身份和直接依赖；
- 跨 run Work 复用；
- atomic lease claim、renewal、expiry recovery；
- attempt history、checkpoint、retry/backoff、terminal failure；
- transitive Work invalidation；
- 不超过 64 KiB 的原子 inline JSON Work result。

最近验证基线为：

- Work/lease：10 passed
- Accounting：23 passed
- 全部快速测试：65 passed，2 deselected
- 香港本机 fixture：2 passed
- Ruff 和 diff checks 通过

这些数据是起点，不是无需重验的真值。

## Artifact 的准确含义

Artifact 是 PreCheck 生成并需要独立保存的派生字节，例如：

- 低分辨率或高分辨率 rendition；
- 视频帧；
- contact sheet；
- embedding 文件；
- 其他大型派生内容。

必须区分：

- Work Record：一次计算的语义、依赖和执行状态；
- Artifact：该计算产生并独立保存的不可变字节；
- Evidence：sealed Result 选择给 Plan 检查的证据及其关系和限制；
- Result：不可变的跨阶段交付。

Artifact 不是 Evidence。很多 Artifact 只是可复用内部产物，并不进入任何 Result。小型结构化结果可以内联，不需要 Artifact。

## Slice 1 剩余目标

Slice 1 必须第一次跑通一条窄而真实的端到端链路：

Discovery
→ Accounting Closure
→ Work
→ Artifact
→ 最小本地 rendition
→ 最小 Evidence/frontier
→ immutable Result seal
→ `mediasense.precheck.read`

需要完成：

1. 将 source add/change/remove/unavailable 与真正受影响的 Work 失效连接起来。
2. 为 Artifact 复用建立足够强的来源有效性证明；现有大文件抽样 fingerprint 只能用于候选判断，不能证明 Artifact 精确有效。
3. 实现最小 Artifact 生命周期：
   - workspace 内临时或未发布写入；
   - 完整关闭生产者输出；
   - digest、大小等完整性验证；
   - 原子替换或唯一不可变名称加事务引用；
   - 成功 Artifact 与 Work Record 的事务绑定；
   - 崩溃不能把部分文件标为成功；
   - orphan、丢失、损坏和重新计算行为可检测；
   - 暂不建设复杂 GC。
4. 按 legacy-first gate，研究 AI Album 生产提交
   `c90aa8f04fd0d3348284e0ad19e18462987b1af2`
   中 image rendition、方向修正、thumbnail cache、损坏恢复和相关 tests/修复记录。
5. 移植或重新实现一条最小、保守、本地的图片 rendition producer，证明真实 Work → Artifact 链路。
6. 建立最小 Evidence/frontier：
   - 正确区分 `accounts_for`、`entry_evidence`、`represents`、`derived_from`、`expands_to`；
   - 支持 many-to-one 和 one-to-many 的模型边界；
   - 不要求每个 Source Item 都有视觉 Evidence；
   - 证明 normal route 或明确 exception route 的 navigation closure。
7. 实现 mutable working state 与 immutable sealed Result 的清晰分离。
8. 实现最小 seal：
   - seal 前进行 accounting/navigation/integrity 检查；
   - seal 中断不能发布部分 Result；
   -旧 Result 不得被后续工作改写。
9. 实现或接通 `mediasense.precheck.read` 的 `inspect`/`traverse`。

## Read Contract 独立闸门

正式 PreCheck Read Contract 的同期修改属于独立审阅事项。

在实现 Result/Read Tool 前，必须先检查这些修改是否已经得到用户独立批准。若状态不明确：

- 不要静默修改合同；
- 不要把内部实现反向写入公共 schema；
- 在交互 Workspace 中向用户提出一个明确的合同审阅 checkpoint；
- 可以先完成不依赖该决定的 Artifact、rendition、Evidence 内部工作。

## Legacy-first gate

每项能力编码前必须：

1. 阅读 AI Album c90 对应源码、测试、配置和历史修复；
2. 如需看当前 HEAD，必须与 c90 证据分开标注；
3. 说明旧实现解决的真实问题、边界和运行质量；
4. 判断是直接复用/抽取、移植适配、参考重写，还是因明确缺陷替换；
5. 重写前建立 characterization test、回归样例或性能基线；
6. 完成后更新 `preserved / intentionally_changed / regression / not_comparable`。

不得照搬 AI Album 的架构、缓存格式、目录布局或运行时依赖；也不得只凭自己的理解重写一个旧系统已经打磨成熟的能力。

明确不保留：

- 部分 wildcard 产物冒充完整成功；
- 无依赖感知的 cache hit；
- 无界任务一次性创建；
- epoch-zero 时间；
- 粗粒度 cache bitmap 作为有效性模型。

优先使用成熟组件，例如 Pillow、ExifTool、FFmpeg/ffprobe，不自行重造通用解析器或解码器。

## 香港 fixture 边界

使用前读取：

- `eval/fixtures/ai-album-hk-representative-v1.yaml`
- package `README.md`
- `docs/RESEARCH-AND-HANDOFF.zh-CN.md`

先运行普通 verifier。不得运行：

- fresh replay；
- `--deep`；
- 远程模型；
- 在线地图；
- 收费 API。

严格区分：

1. 当前代表包可直接路径级验证的事实；
2. 对原始香港生产源的历史重建；
3. MediaSense 产品或实现假设。

历史 4,896 文件、4,365 分组成员等信息不能证明当前 fixture Source State 的 Accounting Closure。

## 工作方式

这是用户交互式开发 Workspace。第一条回复应：

1. 简洁复述 PreCheck、Slice 1、Artifact、Evidence、Result 的区别；
2. 核对当前代码和测试状态；
3. 提出 Slice 1 剩余工作的最小可审阅顺序；
4. 明确第一个准备实现的边界及验收标准；
5. 只提出真正影响结果的重大问题。

其中第一条回复还必须给出独立 Git worktree 的建议路径、基线和承接当前未提交修改的非破坏性方案；在用户确认并完成隔离前只做只读检查，不在主工作树实现。

之后与用户持续协作：

- 让用户能够观察、纠正、暂停和停止；
- 高风险或合同边界到达时设置明确 checkpoint；
- 不因普通实现细节反复请求许可；
- 每一小段完成后运行 focused tests，再运行快速套件；
- 不覆盖并行产生的 Plan/eval/contract 修改；
- 不提交 Git；
- 不修改 AI Album 或香港 fixture；
- 不创建大型新迁移文档；
- capability ledger 只记录有实现证据的状态；
- 不宣称 Slice 1 完成，除非端到端链路和验收项都实际通过。

## Slice 1 验收重点

至少证明：

- Artifact 永远不会以部分写入状态被标记成功；
- 崩溃前后的状态可恢复且诚实；
- 损坏或缺失 Artifact 不会被静默复用；
- 单个媒体或 producer 失败不抹掉其他工作；
- source 变化只失效真实依赖；
- 无关代码或配置变化产生零语义失效；
- 相同有效底层工作可被不同 run/Result 复用；
- 每个 accounted Source Item 具有 normal 或 exception 路径；
- sealed Result 不可变；
- Plan 只能通过精确 `result_ref` 读取；
- 源文件没有被修改；
- PreCheck 没有网络、远程模型、在线地图或收费调用；
- Ruff、快速测试、合同 conformance 和必要的本机 fixture 测试通过。

## 返回要求

这是 user-interactive delegation：

- 不要在未经用户明确确认时写入最终 paired result；
- 工作期间的说明、方案和中间结果保留在交互对话；
- 用户确认 Slice 1 的最终结果后，把完整、未经二次解释的交付报告写入：
  `/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260828-2125-precheck-slice1-completion/01-result-mediasense.md`
- 报告应包含实际实现范围、证据、测试、legacy comparison、未完成事项和是否满足 Slice 1 acceptance；
- 只修改 paired result，不修改 request 或 package synthesis；
- 写回后返回简短 receipt，并继续等待用户明确结束 Workspace。
````
