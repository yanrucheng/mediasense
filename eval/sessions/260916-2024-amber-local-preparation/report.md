---
title: "Amber 逐菜细分与局部 PreCheck 准备使用复核"
service_version: "MediaSense 0.11.0；以留存请求、Result 与 Frozen Plan 为行为证据"
date: 2026-09-16
environment: "macOS；用户实际 cmux 会话；只读复核"
model_id: "gpt-6-astra / low（被评估会话）"
dataset_version: "test-260831；precheck-result:0ce9b26fda788c858dff1ff8416c34964a5c069cf51139f682afd0a08e7e2ed1"
purpose: "判断局部细分时 Agent 的证据选择、压缩价值判断与方法限制，并复核实际组织结果"
baseline_ref: "docs/spec/contract/precheck-run/index.md；docs/spec/contract/precheck-read/index.md；mediasense-plan/SKILL.md"
---

**这次细分改善了 Plan 的检索入口，但没有走局部 PreCheck 准备路径，不能作为该能力的实际使用验收。** Amber 的 663 个源条目仍由原来的 37 个代表集合整体分配；Plan 将它们从 4 个目录重新组合成 20 个目录，没有拆开任何一个原代表集合。

没有发现这轮细分改写旧 Result、遗漏或重复分配 Amber 成员、沿用错误版本确认的问题。Agent 也明确披露了剩余混组，用户随后接受并要求冻结。因此，问题不宜概括为违规完成或虚假确认。值得改进的是：**用户提高了局部整理粒度，Agent 又碰到了具体的准备缺口，却未展示对直接读取原材料、局部补准备及保留较粗结果的收益取舍，而是停在当前已准备证据能支持的粗细程度。**

用户随后明确：期望 Agent 自主理解并判断压缩的价值，而非强制二次 PreCheck。直接调查原始材料、重新压缩后阅读较少的代表，或组合两种方法，都可能是合理选择。未调用二次 PreCheck 本身不作为缺陷；本报告区分路径是否被执行、方法选择是否有可核实依据，以及哪些指导可能过度约束方法。

本复核遵循 `yanru-guidelines`：检查目的、权威与必要边界；不把某一套调用顺序当作所有细分请求必须执行的流程。

## 实际调用与结果

以下时间均为 2026-09-16，Asia/Shanghai。行号属于目标会话 JSONL，完整本机路径见末尾。

| 环节 | 实际行为与证据 | 判断 |
| --- | --- | --- |
| 14:37 用户要求 | 更正暖心芝作，并要求 Amber「每道菜都分出来，结合网络上的资料和命名」（行 198） | 新增局部检索要求，未直接指定压缩参数 |
| 撤回为草案 | 在原 Work 上保存更正、`kind=draft` 及 `amber_detail` 偏好（行 216） | 局部意图已保存；此前偏好为空，未发生覆盖已有偏好的损失 |
| 阅读已有证据 | 读取 37 个代表，展开高清、视频和成员信息，读取现场菜单；网上菜单被识别为换季后的资料（行 244—377） | 真实调查发生了；没有把当前官网菜单当作当餐点单事实 |
| 遇到准备缺口 | 对原代表集合 17、18、31 解析 55、46、34 项成员，选出 12 个边界源文件，查询 `covering_evidence`（行 316、329、348、351） | 封存图谱复核显示，这 12 项均没有来自自身的已准备图像；覆盖它们的代表不等于它们自己的画面 |
| 保存 20 组 | `set(ns)` 直接取原 `represents.source_set` 或它们的 union；保存到同一 Work、同一 Result（行 400、409） | 改变 Plan 组织；没有降低 PreCheck 压缩力度，也没有在原代表集合内部重分成员 |
| 15:04 交付 | 说明 20 个菜品、饮品及活动组，并披露厨房品尝、餐后合盘仍为组合展示（行 426） | 有真实局限披露；「20 组」不等于「20 道菜」，也不等于逐素材完成细分 |
| 15:28 以后冻结 | 用户明确说「非常好，固化吧」；随后直接冻结刚审阅的 revision，没有再保存新版本（行 433、444） | 此轮可核实的确认与冻结版本对应 |

这段交互约 26 分 50 秒，共有 **56 次图像载荷实际进入会话**。它们包含普通图、高清图和视频材料；不是 56 个独立源文件，也不是逐项实测推理成本。该轮模型费用未独立计量，不能据此推算局部重跑会更贵或更便宜。

只读核对 Dataset 数据库、封存 Result 和 Frozen Plan 后得到：

| 项目 | 结果 |
| --- | --- |
| 留存 PreCheck Run / Result / Plan Work | 各 1 个；Run 是 9 月 15 日的原始运行 |
| 原 Result 的 Processing Profile | `target_entries=200`、时间尺度 86400 秒、空间尺度 3000 米、内容距离尺度 0.311；`overrides=[]` |
| Amber 组织范围 | 前后均为 663 项，其中 usable 662、invalid 1 |
| 原代表集合 | 37 个；被拆到不同新目录的集合数为 0 |
| 新目录成员对账 | 与旧 Amber 范围完全相同；重复分配 0 |
| 被点名调查的边界文件 | 12 项；拥有自身已准备图像的为 0 |
| 新 Run、preparation 回读、跨 Result correspondence、新 Work | 在该轮均未发生 |
| 最终确认 | revision `ec6e52c0-eb98-485b-9794-0bafd9eabbb4`；冻结内容身份 `sha256:a049b76ba3449b7b36179a572ba6a0ad0d0643118180b2a9ca147e2c92cdaf1f` |

详细计数及完整引用见 [metrics/combined.json](metrics/combined.json)。其中「有自身准备图像」按留存图像 Evidence 的实际 `derived_from` 链统计；不沿 `represents` 扩大来源。76 个 Amber 源条目有此类材料，这个数量仅描述准备范围，不是组织合格阈值或本轮已看过的数量。

## 暴露的使用问题

### 1. 准备缺口后，未见两条调查路径的取舍依据

最有辨别力的证据不是「没有调用 start」，而是 Agent 已经找到了需要检查的具体边界文件，普通 Read 又没有提供这些文件自己的图像，之后仍未读取 `preparation`、尝试局部准备或说明放弃该方法的原因。

对应的 12 个文件为：`DSC01230`、`DSC01240`、`DSC01250`、`DSC01260`、`DSC01268`、`DSC01275`、`DSC01285`、`DSC01310`、`DSC01485`、`DSC01490`、`DSC01500`、`DSC01509`，均为 JPG。它们分布于 55、46、34 项的三个原集合。

现有 [Plan Skill](../../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md) 已经写明：需要局部准备改变时，读取旧 preparation，带完整输入集合和 overrides 创建普通新 Run，再核对来源对应并创建新 Work。父会话在 9 月 15 日 10:50 实际读过包含这段内容的 Skill；目标会话继承的历史范围包含该读取。原 Result 也确实封存了完整 Profile。不能将这次未使用简单解释为能力说明尚未安装。读取记录不证明模型当轮充分使用了这条指引。

这是 **Agent 方法选择与实际使用验收的缺口**，尚不能证明 Tool 执行实现有错，也不能仅凭没有新 Run 断言其选择错误。可接受的修订目标是：需要更细区分而现有准备缺失时，Agent 能评估直接读取所需原材料与使用局部准备的收益；若选择保留较粗结果，交代具体剩余影响和不再调查的理由。用户只需表达检索目的，不应被要求知道 `overrides` 或参数名。

### 2. 菜名更细，素材分配仍受旧代表集合限制

最终「炭烤萤火鱿配豌豆」直接接收原来的 **55 项整组**；「厨房参观、发酵食材讲解与厨师合照」包含 **53 项**。后者的冻结说明明确写着：

> 此组末端含萤火鱿品尝视频，保留在厨房活动中并以本说明交叉指向07。

因此，以「萤火鱿」查找全部相关素材，仍需要回到厨房活动组寻找。另有 **34 项**保留在餐后小点、水果与 Ambershu 组合展示。计数校验通过可以证明成员没有丢失，但不能证明逐菜检索已经满足。

旧压缩集合是可质疑的证据范围，并不是 Plan 必须遵守的不可分单元。现有 Source Set 的 explicit、union、difference 已能表达有依据的新分配；有必要时可先准备新的证据。无需新增餐厅、菜品、子 Run 或另一种 Plan 实体。

同时要区分两种问题：

- **多个文件被混在一个旧代表集合里：** 可通过局部准备取得更多自身证据，再重分文件。
- **一个文件本身包含多道菜或完整活动：** 更密的证据不会把一个源视频变成多个独立源文件。组合展示可以是正确处置；当前完整分区也不允许把同一源项重复安排到多个目录。逐菜目录、逐文件归属、视频切段是不同要求。

这轮已经披露组合展示并取得用户接受。需要改善的是对这两类剩余限制的解释，以及对前一类问题的继续调查能力，而不是宣称所有混合内容都应强行拆净。

### 3. 易把结构完整当作细分能力已经验证

最终 `validation.seal_ready=true`、`unassigned=0`，对整个 Plan 的 6373 个已交代源条目都有处置。这些是机械校验，符合 [Plan Work 契约](../../../docs/spec/contract/plan-work/index.md) 的职责；Tool 不负责判断菜名或检索价值。

本轮对用户的局限披露确实存在，因此不将其判为虚假完成。但是，仅凭 20 组页面、用户满意和完整性通过，容易在产品评估时误记为「局部调压缩已跑通」。这里应分别记录：

- Plan 根据更细目标重组并获接受：有证据。
- 已有材料不足时自动选择局部准备：本轮没有发生。
- 局部新 Run 的复用、成本、来源对应及 Plan 接续：本轮没有验证。

## 对既定设计的判断

[基础模型](../../../docs/model/model-260913-1408-precheck-basics.md)、[压缩模型](../../../docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md) 和 [Run/Read 契约](../../../docs/spec/contract/precheck-run/index.md#普通-run-与完整-processing-profile) 已给出足够的责任与实体：用户表达所需细节，Agent 判断缺什么证据，Tool 负责有界准备与复用，Result 保存不可变事实，Work 保存组织判断。

如果已有证据足够，Plan 直接重分完全合理；普通语义变化不必触发新的 PreCheck。若决定改变 PreCheck 准备，则须保留这些不变条件：完整固定输入、完整配置值、精确局部范围、旧 Result 不变、直接来源对应、新 Work 和新的确切确认。调用次序中的调查方法、采样数量和参数选择保持开放。

源码也有相应路径：[_initial_evidence_media](../../../src/mediasense/precheck/_orchestrator.py) 将 override 成员作为定向准备需求；最终压缩先拆出 override 成员，再处理基础分区和局部分区，拒绝跨分区输入。[_preparation.py](../../../src/mediasense/precheck/_preparation.py) 校验完整输入、互斥可处理成员和配置身份。因此新能力在结构上能够处理本例的跨文件准备缺口，本次未作实际执行认证。

还需保留一个具体调用边界：Amber 的完整集合包含 1 个已知 invalid 源项，不能把全部 663 项直接作为要求「可处理成员」的 override。它继续留在完整输入和组织对账中；局部准备范围应选择需要且可处理的成员。这是现有契约的作用，不需要增加餐厅专用规则。

建议优先改进现有 Plan Skill 的信息充分性判断：让「用户要求更细，而所需成员自身材料尚未准备」成为比较调查方法的条件，明确已有局部准备入口及直接查看原材料的适用性。目前局部准备操作放在保存 Work 的章节，前面的调查文字又主要把重开 PreCheck 与完整性或准备义务纠错相连。此处可能影响发现和选用能力；单个运行样本不能证明它是唯一原因。

不建议增加固定的「每次细分必重跑」流程，也不建议给 Tool 增加语义验收职责。前者会浪费已有充分证据，后者会把 Agent 的组织判断错误地下放。

## 用户澄清后的目标与限制核查

用户期待的选择关系是：

```text
目的：以合理总成本，达到当前要求的整理粒度
├── 已有代表和细节足够：直接继续组织
└── 还不足：由 Agent 判断调查方式
    ├── 直接读选定原材料，数量少时可能更省
    ├── 局部重新准备和压缩，再读较少的代表
    └── 两者组合，并随新证据调整
```

这里的「信任阈值」更准确地说，是判断该压缩结果是否适合当前决策。阈值属于算法配置，不是语义正确率；一个适合区分整场活动的压缩结果，未必适合区分活动内部细节。多做一次局部准备能增加可读证据，同时仍可能比直接读取全部原件省模型阅读成本；收益要连同准备、来源验证、发布、Plan 接续和用户注意力一起评估，不预设必然更便宜。

本轮并非完全没有向成员展开：它调用 `member_observations`，解析三个集合共 135 个成员的名字、引用和路径，再挑选 12 个具体文件查询已有覆盖证据。成员观测返回后只向会话输出每组截断样本，不能由 Tool 取回数据推断 Agent 已充分阅读 135 份观测。图像读取均指向已准备材料；没有逐项打开上述 12 个原始 JPG，也没有为它们启动新准备。可以确认这些动作，不能由缺少调用反推出一份已完成的成本比较。

相关措辞逐条区分如下；这是审阅判断，没有改写产品约束：

| 权威位置与原文 | 实际限制及本次判断 |
| --- | --- |
| [Foundation](../../../docs/design/design-260823-1918-mediasense-foundation.md)：「Plan … must not inspect every asset.」 | 是真实的强禁止，针对逐项查看的措辞过于绝对。节省默认成本不应排除小集合或高价值局部范围中的完整阅读。应保留成本目的与预算，由 Agent 选择必要阅读范围。没有证据证明本轮消费者直接读取了 Foundation，不能认定此句是当轮原因。 |
| [Plan Skill，Boundaries](../../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md)：「Read bound Result facts and prepared Evidence only through mediasense.precheck.read; never inspect PreCheck databases or caches.」 | 限制的是取得封存 Result 事实和准备材料的权威途径，以及私有存储访问。它没有直接禁止只读打开原始媒体。若解释成「Agent 的全部信息只能来自已准备 Evidence」，就扩大了原句的适用范围。原材料的新调查须保留真实来源，不能伪装成旧 Result 观测。 |
| 同一 Skill，调查段：「Use resolve … only after the semantic decision requires it」以及多处 prepared detail / prepared Evidence | 意图是避免无用展开，并非禁止成员调查；本轮确实执行了 resolve。但相较于反复明确的已准备材料路径，直接读取原始媒体缺少同样清楚的说明，可能被理解为无准备图就没有调查入口。 |
| 同一 Skill：「on a food trip … identifying a meal … may matter more than identifying every dish」 | 不是禁止逐菜调查，也不能覆盖用户此次明确提出的逐菜目的。作为价值判断示例，它仍把某种业务优先级带入默认指导；更稳妥的判据应是当前用户的检索目标。 |
| 同一 Skill，保存与展示段：「do not … build mosaics」 | 上下文是禁止 Agent 另造方案展示和第二份业务数据。它不宜被扩大为禁止为自身调查制作临时联系表。临时派生材料与 Plan 权威展示的责任不同；本轮没有直接证据证明它阻止了某次调查。 |

未找到一条明确写着「Plan 不准读取原始文件或源条目字段」的 Skill 规定。也不能把没有按需生成新材料的 Read Tool，理解为禁止 Agent 使用其他已授权读取或解码能力。必要边界是源只读、真实身份与来源、旧 Result 不改写、效果和预算守约；选择读代表、读原件或重新准备属于开放方法。

能力发现仍有具体不足：完整参数可通过 [review include=["preparation"]](../../../docs/spec/contract/precheck-read/index.md#准备回读与直接来源对应) 回读，但需要主动选择；[Run 机器定义](../../../docs/spec/contract/precheck-run/precheck-run.tool.json) 的顶层描述仅为「控制一次 PreCheck 或只读观察其状态」，四个压缩参数主要列出类型和数值范围，未在字段 description 中解释影响。人工契约有解释，Skill 也给出了新 Run 的做法，但普通发现入口尚未充分交代「何时一次额外准备能节省后续阅读」的使用价值。接口存在、配置可读、Agent 理解并采用它，是三项不同证据。

因此，本轮可以归纳为「已有证据内的重组和保守收尾」；尚不能认证为充分比较所有开放方法后的成本选择。应改进方法空间和收益的可发现性，并清除过强或容易外推的限制，再检验 Agent 能否自适应选择。验收标准不应变成是否固定调用了二次 PreCheck。

## 尚需验证的真实路径

已有[工程验收记录](../../../openspec/changes/simplify-precheck-run-composition/acceptance.md)包含合成来源对应、局部准备及成本检查；本次真实交互不能替代或扩大它的认证范围。后续应以同类自然语言请求，在安全独立副本上验证：

1. Agent 能在实质准备缺口出现时自行选择有界局部准备，或给出可复核的其他充分方法；不能只让验收器提前喂完整 start 请求。
2. 新 Run 确实准备缺失材料并复用有效成果，记录全范围验证、封存、局部解码和模型成本。局部计算可复用不等于总成本与所选项数成比例。
3. 新 Result 后通过直接 correspondence 保留有依据的偏好与组织，创建新 Work；旧 Result/Work 不变，确认不转移，最后用具体查找问题检查所得粒度。

本次没有启动新的 PreCheck、保存业务 Plan、执行 Apply 或改变源媒体。未发现的成本、复用或跨 Result 迁移问题保持未验证，不以推测写成已发生缺陷。

## 复核来源、命令与边界

- cmux 目标：workspace `00309E9E-42AF-4484-AF6A-01B06A8CDDBD`，surface `1E22F6DB-7256-4C33-B752-4735C318D886`。通过当前 `identify` 和 `list-panels` 同时核对 ID、工作目录及恢复会话；没有向该终端输入或打断其后续操作。
- 实际会话：`/Users/chengyanru/.codex/sessions/2026/09/16/rollout-2026-09-16T12-51-28-01a0a88e-3a94-74c1-abf2-e8a283910da3.jsonl`。主体为行 198—432，确认续段为 433—454；只将用户消息、对外回复、工具调用和返回用作报告证据。
- 父历史：`/Users/chengyanru/.codex/sessions/2026/09/15/rollout-2026-09-15T10-22-03-01a0a2df-1458-7c30-8d84-1199f167d74b.jsonl`，继承上界 681 行、25,826,224 字节。Plan Skill 的实际读取在行 323/326。
- 数据源：`/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`。Dataset 工作区：`/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e`。
- API：被评估 Agent 使用 `mediasense mcp` 的 stdio Tools。局部调整阶段只用了 PreCheck Read 和 Plan Work，没有 PreCheck Run；本次审计通过只读文件和 SQLite `mode=ro` 交叉复核，不注册或调用新的业务 Host。
- 源码基点：`e10abe8ed78a10205f6e00e1d70906f786ae74b2`，调研开始时工作树已有其他改动。当前 CLI 报告 0.11.0；不由相同版本号推断当时运行构建与当前源码逐字节相同。具体行为结论由原始调用和留存产物支持。
- Result 文件 109,351,716 字节，SHA-256 为 `3c3227e7561daffc59655f4d0bdd5a76edf7eba16bdba66007df6120141db2aa`，与 `sealed_results` 登记摘要一致。Frozen Plan 引用和确认身份见上述指标。
- 原始会话、媒体、图像和数据库只在本机保留，不进入本评估的 Git 文件。仓库只增加本报告、只读复核脚本和小型指标。

按项目要求已先读 fixture 登记与包内两份说明，并运行包自带 `scripts/verify.zsh`。清单 SHA-256 为登记值 `f56caa6b1f1dd56e1b02850a5bfc17567d11f5617899db166eb8d670889d67fe`，脚本报告所有清单文件摘要通过；随后因当前目录总量 **4,613,748,609 字节超过 2 GB** 而退出 1。因此不宣称该 Downloads 目录通过完整的 v1 包验证，也不把它的历史分组当作正确答案。本报告判断依据是本次用户要求、实际调用和单独验真的封存数据；这不是一次 AI Album 回归对比。

复算命令：

```sh
rtk proxy python3 eval/sessions/260916-2024-amber-local-preparation/run.py \
  --trace /Users/chengyanru/.codex/sessions/2026/09/16/rollout-2026-09-16T12-51-28-01a0a88e-3a94-74c1-abf2-e8a283910da3.jsonl \
  --workspace '/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e'
```

[run.py](run.py) 只解析目标交互、读取封存文件、验证已登记摘要并计算集合交集。它依赖本次保存结构，属于会话内复核工具，不是新的产品 Tool 或稳定通用读取接口。复算结果与 [metrics/combined.json](metrics/combined.json) 一致；报告引用与文件格式另作静态核对。没有为文档调研运行媒体处理或生产测试套件。
