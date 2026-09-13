# Plan 信息收集与可选工作保存：开发交接

## 状态与权威

**本次按当前工作区重新验收已完成，并补齐两处请求校验遗漏。** 基线 `615c335` 已包含下述功能及四项历史补修；本轮新增拒绝显式 `page.limit:null` 和非法偏好键，未改动合约或确认流程。新 wheel 仅完成隔离交付，未切换全局安装。默认 1296 项经沙箱失败项恢复全部通过，安装包专项 234 项、42 次真实 MCP 调用及六类独立 Agent 推演通过；浏览器图片加载证据与进程退出超时分开记录。详见[本轮验收](acceptance.md#当前基线重新验收与输入校验补修)。下文日常升级记录仅对应其注明的历史构建。

**设计与此前四项补修均已获独立复核通过；日常 CLI、四个项目 Skills 和注册 MCP 链路已完成升级验证。新 Agent 会话加载仍需在实际操作项目确认。** 实现、测试、构建身份及未认证范围见[实现验收](acceptance.md)。未执行真实媒体 Apply；精确安装目标和回滚见上述记录。

2026-09-12，用户在逐轮认可并明确保留“看预览 HTML → 聊天说行”的确认方式后，确认“所以简单来说，我们后续的研发可以开始了，是吧？”。当前合约已同步，本包是另一位 Agent 的开发入口；已讨论的字段、职责和流程无需再次征询。

本包记录实现范围和验收，当前协议以 [`docs/spec/contract/`](../../../docs/spec/contract/index.md) 为唯一权威。

- [当前 Plan Work 合约](../../../docs/spec/contract/plan-work/index.md)
- [当前请求／返回 schema](../../../docs/spec/contract/plan-work/plan-work.tool.json)
- [当前合成交换与反例](../../../docs/spec/contract/plan-work/interaction.mock.json)
- [讨论及用户回答](../../../docs/clarify/clarify-260912-0601-plan-work-discussion.md)
- [原场景取证与 Tool 审查](../../../docs/eval/eval-260912-0224-plan-memory-risk-audit.md)

本目录的 [contract.patch](contract.patch) 和 [interaction.mock.json](interaction.mock.json) 保留为本次审阅快照，不能重复应用或用它们覆盖当前合约。当前合约、Foundation 和存储职责已同步；Tool／存储、Skill、Preview 和隔离安装入口现已实现并验收。以下保留已放行的实现范围与验收依据，实际结果统一见[实现验收](acceptance.md)。

## 要实现的结果

Plan Agent 对组织决定的信息充分性负责。它能够先调查和与用户讨论，再一次提交完整候选；也能自主选择把足以继续的工作说明保存在既有 Work 中。名字、人物关系、活动边界、时间、地点、用户的找回目的都可能需要澄清，输入形式不限定为某一种文件或选项。

目的锚是形成可理解、可质疑、符合找回目的的组织决定；归宿锚是原 Result 保有其事实与范围，Work 保存当前工作，Frozen Plan 保存最终确认的组织。调查方法、提问时机和工具组合由 Agent 选择。

本次不重做 PreCheck，不修正已封存 Result，不新增通用材料仓库，不改变 Frozen Plan 的 Source Set 或 Apply 语义。此前已修复的 Plan 吞吐、取消和幂等行为必须保留；原场景的轨迹匹配问题按取证报告独立处理。

## Tool 决定

### 写入与生命周期

沿用 `create / update / inspect / seal` 四个 action。`create` 的输入和返回不变，新 Work 的工作说明初始为空字符串。

`update` 必须提供 `work_ref / base_revision / request_id`，并至少提供以下一个可修改字段：

| 字段 | 省略 | 提供值 | 清空 |
| --- | --- | --- | --- |
| `organization_preferences` | 保留 | 对象整体替换 | `{}` |
| `working_notes` | 保留 | 字符串整体替换 | `""` |
| `candidate_content` | 保留 | 完整对象经原有校验后整体替换 | `null` |

不新增局部 Candidate patch，也不保存不完整或非法 Candidate。`null` 表示没有当前候选，不表示空目录或排除所有来源。清空不承诺历史版本恢复；预留的 `plan_ref` 保持 Work 原有身份。

一次更新是原子的。只要任意提供值非法或完整 Candidate 校验失败，说明、偏好、候选、revision 均不改变。每个新接受的更新都生成新 revision，即使提供的值与现值相同；同一 request_id 的相同请求重试返回原回执，不产生新 revision。省略字段和显式清空不是同一个幂等请求。

仅修改说明／偏好，或显式清空 Candidate，不运行 Candidate 分析、不读取 PreCheck、不调用模型或 Geo。它们仍遵守同一 Work 的并发、取消和原子提交边界。提交完整 Candidate 时继续执行已有校验；同一次调用不得先保存说明再异步校验候选。

`revision` 保护整份已保存 Work，`candidate_content_identity` 标识既有编码规则下的完整最终组织。说明、偏好不进入 Frozen Plan，不改变未替换候选的 identity。影响最终解释的内容应进入 Candidate 的 `decision_notes`；Tool 不解析自由文本来判断是否需要重组或撤下。

closed Work 保持只读；后续组织仍创建新 Work。已经发布的 Frozen Plan 不变。并发 seal 的预留与恢复边界继续适用于所有 update，不能因本次写入只含说明而绕开。

### 读取

增加 `working_notes` section。默认 `inspect` 仍读取全部 section，按 `overview / preferences / working_notes / content / validation` 返回；显式选择时只返回所选 section。`returned_sections` 与实际字段一致。

无 Candidate 是可正常读取的 Work：

- 工作说明返回实际文本，未写入或已清空时为 `""`；偏好沿用 `{}`。
- `content` 返回 JSON `null`。
- 选择了 `validation` 时返回 `seal_ready: false` 和 `candidate_missing` issue。
- 整个响应不返回 `candidate_content_identity`。

已有 Candidate 的 complete／paged 形状和分页规则不变。无 Candidate 时合法的无 cursor 分页请求同样返回 `content: null`，不伪造空集合或 continuation。请求形状、显式 revision 和已有 cursor 仍须验证；旧 cursor 不能因为候选已清空就被忽略。说明没有分页或结构化引用语法。

工作说明沿用普通 JSON string，不增加未经规模证据支持的字段专属字符上限。保存与读回必须保持完整文本，不得静默截断、改写或摘要。调用方用 section 选择控制读取范围；入口已有的整体资源／传输限制仍适用，这不构成任意大文本的吞吐承诺。

`inspect` 报告已保存的 Candidate 校验结果，不为说明写入重新获取证据。`seal_ready` 不认证事实真伪、偏好符合性、当前外部材料可用性或人类接受；`seal` 仍重新验证其所拥有的条件。

### 错误与恢复

| 条件 | 结果与恢复 |
| --- | --- |
| update 没有可修改字段、顶层字段类型错误或额外请求字段 | `invalid_request`；没有写入。 |
| 传入 Candidate 对象的结构／组织／引用／覆盖校验失败 | `candidate_invalid`；组合更新全部不保存。传输层也可能在派发前拒绝不符合 schema 的请求。 |
| 当前 Work 无 Candidate，普通 inspect | 正常返回上述空候选表示。 |
| 当前 Work 无 Candidate，seal 的其他前提有效 | `candidate_invalid`；没有 Frozen Plan。 |
| base_revision／指定 revision 陈旧 | `revision_conflict`；读回当前版本，由 Agent 重新决定修改。 |
| cursor 无效或属于另一版 | `invalid_cursor`；重新读取所需版本，不拼接不同版本。 |
| request_id 改了有效请求内容 | `idempotency_conflict`；不重用该 ID。 |
| 更新在提交前取消 | 无该次写入；沿用已有取消机制。 |
| 提交成功但响应丢失 | 同一请求重试恢复原回执；超时不等于未写入。 |
| 预留 seal 尚待恢复 | 沿用已有 publication recovery，普通更新不得覆盖预留。 |

这些描述以其他前提有效为条件，不新增全局错误排序。未知异常不能伪装成普通缺候选、等待用户或成功保存。

### 真实 Host 包装

Plan 保持 `dataset_ref + request` 的 MCP 包装；成功返回放在 `structuredContent`，`content` 为空数组。调用方根据业务 `outcome` 判断结果；本次不扩大为整个 Host 的错误包装重构。普通说明保存不需要 Human confirmation。

本次沿用现有确认流程：用户查看针对确切 Candidate 的预览 HTML，向 Agent 明确接受，Agent 经现有本地客户端的 transport authority 传递确认，Tool 核对所确认的内容与待冻结对象一致。用户不需要读出 digest、输入固定口令或再点击一个新增确认入口。

本包不新增 MCP 确认弹窗、授权缓存、Confirm Tool、撤回实体或新的可信来源。独立收取人类确认的通道若未来需要，应另行明确其收益和恢复语义。

现有本地模型信任客户端传递的上下文；内容匹配检查不能独立证明一次真实人类事件。Agent 仍负责依据用户实际表达保留确认的对象、范围与有效性。工作说明中的“已确认”、结构校验成功和局部事实纠正都不构成最终确认。

## 补充信息的保留边界

本次保证保存的是 Agent 主动写入的工作摘要与最终必要依据，不自动托管用户提供的原件。

| 内容 | 保存及使用方式 |
| --- | --- |
| 用户的口述、纠正或偏好 | 明确其来源与适用范围；偏好放 preferences，工作期理解放 working_notes。 |
| 补充文件或外部 Tool 结果 | 使用适当且已授权的能力读取／计算；收到路径不等于读取，读取不等于解释成立。必要来源信息可写入说明。 |
| 最终决定所依赖的重要补充 | 把最短必要解释、来源类别和适用 Source Set 保留在 `decision_notes`，供最终审阅。 |
| 后续必须复核的原件 | 依赖实际具备保留和读取保证的现有能力；仅有文字路径时明确该限制，不能声称 MediaSense 已接管原件。 |

既有 `evidence_refs` 仍只指向绑定 Result 中的 Evidence。补充信息不伪装成 Result Observation，不自动扩充组织范围；新媒体若确实进入组织范围，应通过相应 PreCheck 范围和新 Work 处理。

## Agent／Skill 的具体修改

按已更新的 Foundation 信息充分性职责，修改权威来源 [`mediasense-plan/SKILL.md`](../../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md)。不能只增加工作说明字段后就宣称原交互问题已解决。

1. 将“只有偏好分歧才询问用户”改为：用户也可以提供知识、背景和证据；当缺失信息会实质改变组织决定时，Agent 主动寻找可用信息，包括询问用户。
2. 区分来源缺陷与正常语义不确定。原 Result 的完整性、核算或准备义务确需纠正时才要求上游修复；普通缺地点、用户补充信息或不同输入形式不自动触发 PreCheck。
3. 判断何时提问依据决定的重要性、现有支持、成本、注意力和已授权范围。证据足够时可直接使用；不给所有低分对象设统一阈值或必问节点，不要求固定的候选名单或输入体裁。
4. Agent 可以先完整讨论再 create/update。自主选择保存工作说明；文字保留足以继续的当前理解、重要依据、影响范围和未决后果，不要求记录全部对话或推理过程。
5. 当前“Before update”的组织检查只约束提交完整 Candidate，不阻止更早的说明／偏好保存。完整候选需要重审时，明确保留、替换或撤下；Tool 不从说明自动推断。
6. 最终审阅必须让用户看到重要的 `decision_notes`、适用范围和残余不确定性。修复当前渲染器只展示树而丢失决定说明的情况；工作说明不自动进入最终审阅或 Frozen Plan。
7. 修正循环前提：核算完整、信息足以支持所提处置、组织有效这三项支持后，请用户审阅精确 Candidate；从用户实际接受取得第四项“Human confirmed”，再 seal。最终冻结与后续 Apply 授权仍分开。

这些是职责与结果约束。Skill 不固定调查顺序、每轮 Tool 调用数、问答轮数、展示技术或下一步动作。

## 展示与确认

保留现有 Preview 为派生视图的定位，不增加 Preview Tool 或持久化预览实体。

- 确认前的展示绑定确切 Work、revision 和全局 Candidate identity；目录、计数、代表素材、其他去向及必要说明均来自同一候选。
- 内置 `PlanPreviewRenderer` 应携带并呈现已保存的 `decision_notes`：最短说明、适用 Source Set、已有 Evidence 引用。不把用户提供的文字当作 HTML 或自动访问其路径。
- Agent 也可用现有 inspect 自己组织展示，表达方式开放，但不能省去影响接受的重要含义。
- 没有 Candidate 时，内置最终 Preview 明确不能生成；Agent 的方向性展示仍可独立进行，不能标成可冻结候选。
- 只补工作说明后，旧 revision 的请求仍冲突；重新读取最新 revision。相同内容与仍有效的接受可经现有可信上下文传递，不因纯记事变化要求用户重复接受。若最终组织或重要解释变化，应展示新候选；用户对旧 HTML 的接受不能用于新内容。

## 实现范围与交接顺序

| 归属 | 需要完成的改动 |
| --- | --- |
| 当前合约 | 已同步 Plan Work prose/schema、interaction.mock.json、默认 inspect Mock 和合约检查；按这些承诺实现。Frozen Plan schema 不变。 |
| Foundation／存储设计 | 已明确信息来源开放与 Work 可选说明，保留 Result、Work、Frozen Plan 三个归宿；按既有本地存储设计实现。 |
| Plan Tool／存储 | 更新 `plan/work.py`、`plan/_sqlite.py` 的原子写入和读回路径；显式区分字段省略与 null；保持预留 plan_ref、缓存候选 identity、并发、取消与恢复。 |
| Preview | 更新 `plan/preview.py` 的派生文档及渲染，把决定说明交付给用户。 |
| Skill | 按上述职责修改权威 packaged Skill，更新与其行为对应的工作流验收。 |
| Host／发布副本 | schema 副本已同步；实现所有入口并交付同一协议，沿用现有本地客户端确认路径；完成 Skill 与发布一致性、隔离安装验收。 |

SQLite 列、索引、代码分解和迁移实现由开发者选择。已有版本的数据若需要升级，应按现有版本政策和 [安装升级 runbook](../../../readme/installation.md)处理；不能清空实际 Work 或改写 Frozen Plan／Result 来通过测试。Zero BC 不授权静默破坏既有数据。

源码中的厂商知识、安装和模型相关并行变更不属于本包。选择一个明确基线审查差异；不要回滚或顺手合并不相关工作。

## 验收必须证明什么

### 确定性 Tool 与交付

1. 已有的一次完整 Candidate 提交路径仍可使用；新路径可在无 Candidate 时保存说明、偏好、重启并准确读回。
2. 三个字段的省略／替换／清空及组合请求全部符合表格；空请求、错误类型、部分 Candidate 被拒绝；合法形状但错误核算的 Candidate 使整次组合写入失败。
3. 说明／偏好更新和撤下操作发生零次 PreCheck Read、Geo 或模型调用；不能因缓存候选较大重新遍历全部媒体。
4. 不同请求的同值保存产生新 revision；同请求重试不产生新 revision。保留候选时 digest 不变；修改最终 decision_notes 时 digest 改变；撤下后无 identity，不能 seal。
5. 并发完整候选与说明写入不会互相静默覆盖；跨进程互斥、旧 revision、取消、提交后失联、请求重放和 seal recovery 保留既有保证。
6. 默认／选择／分页 inspect 对有无 Candidate 都诚实，说明完整读回；旧 cursor、不同 revision 和闭合 Work 的行为符合约定。
7. 真实内置 HTML 呈现决定说明、适用范围、引用与同一 Candidate 身份；特殊字符不执行；无 Candidate 不生成最终 Preview。
8. 匹配的可信确认可 seal，缺失／不匹配确认不能 seal；补充输入与工作说明不产生确认。经真实 Host 验证客户端上下文传递与版本／内容匹配，不把该检查声称为独立的人类身份或点击认证；用户实际接受与确认范围由 Agent 工作流验收覆盖。
9. 经实际隔离 wheel 的 MCP 调用 create → notes-only update → default inspect → candidate update → withdraw，检查单一 structuredContent、字段清空与重启保留；按现有客户端确认路径补齐 seal。验证过程中只使用临时合成 Dataset。

已有相关检查入口：`tests/test_plan_work_contract.py`、`test_plan_work.py`、`test_plan_candidate.py`、`test_plan_update_execution.py`、`test_plan_update_replay.py`、`test_plan_update_process.py`、`test_plan_update_mcp.py`、`test_plan_preview.py`、`test_frozen_plan_contract.py` 及 Host／发布一致性检查。扩充必要语义案例，不把仅搜索 Skill 关键词作为行为验收。

### Agent 行为

用合成对话记录与调用轨迹检查以下不同情形；不调用真实地图或模型服务来伪造充分性证据：

- 关键身份缺依据，用户给出口述更正：Agent 采用正确范围，不把代表项名字推广到全部成员。
- 用户提供补充文件：Agent 选择可用能力，区分收到、读到和解释后的判断；能力缺失时如实处理。
- 现有信息足够：Agent 直接推进，不为了满足模板强行提问或保存每轮对话。
- 用户不记得或尚未答复：不制造答案；独立工作可继续，依赖该答案的决定保持未定，或提出有依据的较粗处置。
- 已有候选出现实质冲突：Agent 明确替换／撤下，不只在工作说明里写反对意见后继续冻结。
- 用户已就局部事实回答，尚未接受完整方案：最终审阅和接受仍针对确切 Candidate，不能把局部回答算作整份批准。

这认证的是遵守职责的代表性路径，不承诺所有未来 Agent 都能识别所有场景。原事件可作为后续有授权的人工回归，不能改写原结果冒充修复效果。

## 完成定义

设计阶段已完成用户进入研发确认、当前合约与职责同步、交换值及正反例检查。确认通道升级不在本次范围内。实现完成另需上述功能、行为及安装入口证据；设计完成不代表已经开发或发布。

2026-09-12 已完成设计侧检查：Draft 2020-12 schema 编译通过；22 组新交换和 8 组既有交换的请求／返回符合 schema；6 组非法输入、2 组矛盾输出被拒绝；版本／内容身份、组合失败后的未变状态及最终确认示例一致。合约 patch 已采用，不需再应用。未发布、安装或修改真实 Dataset。

当前合约采用后的检查：`tests/test_contract_authority.py`、`tests/test_plan_work_contract.py`、`tests/test_frozen_plan_contract.py` 共 55 项通过；包括新合约例子、反例和发布 schema 同步。这是当时的设计／合约检查；后续运行实现与验收现已完成，结果见[实现验收](acceptance.md)。实际能力状态已记录到[迁移台账](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。

原开发交接任务（现已完成，保留作为范围记录）：读取本包、当前 Plan Work／Frozen Plan 合约及 Foundation，按“实现范围与交接顺序”完成 Tool、存储、Skill、Preview 和交付验收。工程方法自主选择；保留已修复的吞吐、取消、并发、重放和来源安全保证，按结果证据报告完成。全局安装切换与真实媒体 Apply 不属于本次开发放行。


## 2026-09-12 开发交接完成

已按上述承诺完成实现，新增 `tests/test_plan_optional_work.py` 与实际安装验收入口 `tests/run_plan_interaction_smoke.py`，补齐 Preview、并发／取消／进程恢复和真实 MCP 验证。隔离验收同时发现并修复 MCP 外部 schema 引用和 Frozen Plan 默认历史源码路径两处入口缺陷；未改动定稿承诺。最终默认测试 1271 passed、16 deselected。

[实现验收](acceptance.md)记录精确 wheel、209 项安装包检查、24 次真实 MCP 调用、六类独立合成交互推演及失败恢复记录。此开发阶段日常安装尚未切换，后续已按用户授权完成本记录顶部所述升级；真实语义质量、原事件复测及人类身份独立认证不在本次完成声明内。后续实施者不需重新实现本包，后续安装与回滚仍按唯一 runbook 执行。


## 2026-09-12 用户复核补修

首轮整体验收未通过：非法 Candidate 可覆盖 plan_ref、部分非法结构返回内部故障、默认 HTML 未显示已有准备图片。三项已补修，未修改设计或 schema。默认测试 1288 passed、16 deselected。最新 wheel、226 项安装包检查、35 次 MCP 调用、Plan 编号一致性及 Chrome 80×40 图片加载证据见[实现验收的补修节](acceptance.md#用户复核后的三处补修)。首轮 24 次调用仍作为正常路径证据保留，不能再作为三项遗漏的通过依据。


## 2026-09-12 Preview 分页补修

用户确认上轮三项已修复，又指出选定 Evidence 因字节上限分页时未续读。现已保持同一 Result、选集与 limit 续读 next_cursor，直到完成；不扩大最多 16 条 Evidence 的扫描范围。真实字节分页回归及续读失败保护、新 wheel 229 项专项、36 次 MCP 调用通过，独立 Chrome 观察到第二页图片可显示。构建身份、完整轨迹、浏览器首次超时及复跑结果见[最新验收节](acceptance.md#最新补修选定-evidence-的字节分页)。未修改设计或全局安装，整体验收仍待用户复核。


## 2026-09-12 日常升级完成

用户确认四项问题均闭合并授权实际升级。已原样保留和安装 hash `1c454027…` 的 wheel，保留 Python3.13.5、embeddings 和59项依赖，更新实际操作项目四个 Skills/lock；原凭据包装及用户配置不变。实际127包文件、12 Skill文件、doctor、七Tool以及注册launcher的36次合成Plan调用通过。稳定备份、完整构建身份、回滚命令和新会话要求见[日常升级记录](acceptance.md#日常环境升级2026-09-12)。
