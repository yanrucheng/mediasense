---
title: "香港素材 2026-09-12 运行验收"
service_version: "MediaSense 0.10.2"
date: 2026-09-12
updated: 2026-09-13
environment: "local macOS; retrospective read-only audit"
model_id: "DINOv3 ViT-B/16 384 Core ML; gpt-6-astra low"
dataset_version: "ai-album-hk-representative-v1/test-260831"
purpose: "验收本次 PreCheck、压缩收益、地图调用和 Plan 产品行为"
baseline_ref: "260908-1148-hk-trajectory-audit"
---

**验收结论：压缩确实生效，地图请求比可核对的上次运行更少；本次 PreCheck 和初版 Plan 仍不能整体验收通过。** Google 附近地点请求有确定的实现错误，初版 Plan 也过早把关键餐厅的泛称当作可以提交最终确认的组织。

本报告绑定 2026-09-12 22:09—23:11 的初次运行和初版候选。审计期间用户在原会话要求补确认餐厅，Agent 已撤回旧候选并重新收集信息。这次纠正与初版质量分别记录，新候选不在本报告的验收范围内。精确对象见 [config.json](config.json)，复核结果见 [metrics/combined.json](metrics/combined.json)。

用户于 2026-09-13 要求将问题分别交给后续 Agent 讨论定案。本轮已创建以下 OpenSpec 问题包；包内仅记录事实、影响、证据边界与未决问题，没有预定设计或实施任务。本报告此前的建议不作为这些包的已确认方案。

| 编号 | 独立交接包 | 记录阶段（最新以各包为准） |
| --- | --- | --- |
| 1 | [Google 附近地点请求失败与 PreCheck 交付状态](../../../openspec/changes/review-google-nearby-failures/README.md) | 二次补修及确切隔离包独立复验通过；日常未升级 |
| 2 | [GPX 匹配重复工作与本地处理耗时](../../../openspec/changes/review-gpx-matching-cost/README.md) | 资源反馈补修及确切隔离包独立复验通过；日常未升级 |
| 3 | [视觉压缩未消费已有 GPX 坐标](../../../openspec/changes/review-compression-gpx-evidence/README.md) | 代码与确切隔离包独立复验通过；日常未升级 |
| 4 | [Plan 初版的信息收集与过早提交最终确认](../../../openspec/changes/review-plan-information-sufficiency/README.md) | Skill 与确切隔离交付独立复验通过；行为结论限于已测场景，日常未升级 |
| 5 | [Plan 对损坏、未决与辅助素材的处置依据](../../../openspec/changes/review-plan-exception-dispositions/README.md) | 默认规则交付与确切隔离包独立复验通过；行为结论限于已测场景，日常未升级 |
| 6 | [Plan HTML 人工确认页面的正式交付与内容来源](../../../openspec/changes/review-plan-preview-delivery/README.md) | 事实已记录，待讨论 |


与 [9 月 8 日同一来源的审计](../../../docs/eval/eval-260908-1148-hk-trajectory-audit.md) 比较：

| 观察 | 9 月 8 日 | 本次初版 | 判断 |
| --- | ---: | ---: | --- |
| 纳入媒体 | 2,136 | 2,136 | 本次对应媒体字节已完整核对 |
| 初步 bundle | 241 | 167 | 时间解释等实现也已变化 |
| 默认代表入口 | 200 | 156 | 减少 22% |
| 实际查看的不同来源项 | 232 | 160 | 减少约 31% |
| 有坐标来源项 | 1,838 | 1,889 | 覆盖增加 |
| 地图逻辑查询点 | 225 | 168 | 减少约 25% |
| 地图实际服务请求 | 454 | 332 | 减少约 27% |
| Google 附近地点 | 221 成功、4 无结果 | 164 失败 | 明确退步 |

本次显示的 **996 是授权上限**：`(164 个 Google 点 × 2 个组件 + 4 个高德点) × 3 次尝试`。实际为 `164 × 2 + 4 = 332`，没有额外重试，费用未知。如果“以前”指77点的无GPX实验、缓存命中的运行，或AI Album的148个有GPS代表，口径不同，不能直接与本次168点比较。

639 个 DINOv3 Embedding Work 全部实际完成。639 份向量的 SHA-256、768维、有限值和单位长度通过核对，最大范数误差约 `5.36e-9`。167个压缩输入全部取得向量，使用用户已确认的 **0.311** 尺度，得到156组。纯函数重放与实际成员身份完全相同；在同一批已准备输入上移除向量并关闭内容边界后为167组。因此，**Embedding在本次后段额外省下11个入口，约6.6%**。这不是关闭模型重跑全流程，也不能把跨版本的200→156全部归功于模型。

主要缩减仍来自本地关联的2,136→167。156个最终组中，146个只包含一个初步候选、9个包含两个、1个包含三个；82组保留“bundle内成员未逐项视觉比较”的限定。全部代表取得向量，不证明全部原媒体经过视觉一致性验证。

地图则是 **1,889个有坐标来源→1,637个不同精确坐标→188个局部采集单元→168个去重查询点**。当前方法在初步bundle内检查15米直径、120秒跨度等一致性，选实际成员坐标，最后精确去重。[采集代码](../../../src/mediasense/precheck/geocode.py#L753) 使用metadata、GPX和初步bundle，**没有消费后续视觉压缩组**。[既有迁移边界](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md) 也明确：视觉压缩不证明地点等价。更好的Embedding不会自动减少这条路径的地图请求。

具体问题按优先级记录如下。

1. **P1：Google附近地点参数越界，并被当成逐地点终局失败。**

   冻结请求为 `max_places=30`。Google适配器自己限制可配置值在1—20，默认10；组合 `resolve_place` 路径会收窄到10。但 [共享Geo独立组件路径](../../../src/mediasense/capabilities/geo/service.py#L223) 拆分操作后直接把30交给 `nearby_places`，[独立分支及请求构造](../../../src/mediasense/geo.py#L755) 没有收窄，发出 `maxResultCount:30`。

   无网络捕获式复现得到：相同输入，组合入口发送10，独立附近地点入口发送30。真实journal的 **164次Google附近地点请求全部记录 `provider HTTP 400`**。响应体未保留，不能排除同时有其他参数问题，但这个确定的越界已足以解释失败，不能归因为当地没有POI。

   [HTTP分类](../../../src/mediasense/geo.py#L213) 把400归为 `http_permanent`，[停止策略](../../../src/mediasense/capabilities/geo/service.py#L404) 又未识别为整批请求问题，于是继续向其他点发送同样无效的请求，最终发布 `plan_ready`。这不满足 [Geo D6](../../../docs/spec/contract/geo-query/index.md) 的失败边界。

   修复应统一现有适配器所有入口的有效上限，保留请求上限与实际范围，并覆盖真实“共享服务→独立组件→适配器”路径。内部构造违反协议应按实现错误暴露，实际服务/配置前提问题按既有阻塞恢复处理；不能把所有400一概变成普通blocked。

2. **P2：GPX重复解析，是本次本地阶段的主要耗时。**

   GPX Work从首次到末次完成为 **587.44秒，约9分47秒**；Embedding Work为 **44.10秒**。2,034个源项走到带轨迹依赖的路径，[实现](../../../src/mediasense/precheck/gpx.py#L149) 每项重新解析同样两份GPX，对应4,068次轨迹解析入口。

   这些是Work执行跨度，包含相关处理和持久化，不是纯解析或推理内核基准。应在现有producer的固定输入范围内复用已验证的轨迹解析与时间索引，保留逐项Work的身份、失败和失效语义，不需要新增服务或Tool。本次没有测量修复后的提速倍数。

3. **P2：55个代表点已有GPX坐标未进入视觉压缩。**

   [压缩producer](../../../src/mediasense/precheck/_compression_producer.py#L262) 对metadata和GPX共用 `_gps_value`，但 [函数](../../../src/mediasense/precheck/_compression_producer.py#L366) 只查 `gps_coordinates`，GPX实际提供的是 `gpx_coordinates`。

   只读对照中，正确读取后仍为156组，成员身份完全不变；`limited_similarity_evidence` 从71组降到21组。所以这是实际消费缺口，**没有证据表明它造成了本次更多分组或地图请求**。修复现有Observation读取即可。

4. **P2：初版Plan仅因invalid把有可靠关联的坏片留原位。**

   `DJI_20260504202728_0029_D.MP4` 与 `.patched-full.MP4`、`.remux-faststart.MP4` 属于同一个PreCheck代表关系。两个可读版本进入Amber／面包与主菜，损坏原片仅因invalid留原位。原轨迹第808行对所有分组统一筛选 `condition==="usable"`。

   [默认组织Profile](../../../docs/spec/contract/default-organization-profile/index.md) 要求先用可靠关联安置损坏项，能否安全执行交给Apply。这里应先判断它能否跟随上下文，再解释留原位的必要性。两个GPX也因unresolved留原位，未采用默认辅助目录；新版审阅应明确这些例外，不能以对账完整认证组织质量。

Plan的主流程有实际通过的部分。它绑定同一不可变Result，采用事件/日期/活动组织，保留空的人类偏好 `{}`，把Profile选择记为Agent判断；实际通过8张拼图查看156个入口，另外7次单图打开中3次是放大已看入口、4次是补看。合计160个来源、160份派生图、15个图像附件。原会话做了一次选择性展开，精确核对全部处置范围。

初版的 **2,133媒体归34组，3媒体与4辅助项留原位，4,233项排除**，构成6,373项的完整唯一分区。HTML候选身份一致，86个内嵌图像全部通过解码检查。Agent没有把 `seal_ready` 当作Human确认，没有seal或Apply。这证明交付和授权边界，不证明全部语义正确。

**Plan初版的信息收集不足。** 美食旅行中的餐厅名，以及“酒廊与晚餐是否同一家”，是高价值检索线索。原会话只询问5月1—2日的城市/行程背景，随后将多个用餐场景保留为泛称并提交最终确认。泛称可以暂用；用户可能提供关键信息时，需要有选择地补问，而不是自动接受残留不确定性，也不要求对每张照片发问。

23:53用户明确反馈“其实我自己都知道餐厅……不希望他们这样保持不定”（JSONL第863行）。Agent随后撤回旧候选、保存工作说明，配A—G画面补问，符合 [Plan Work](../../../docs/spec/contract/plan-work/index.md) 的候选撤下语义。审计观察到revision为 `work-revision:3a7557f7-26a3-4444-9054-cf8404d00260`，candidate identity为null。23:59用户继续提供餐厅线索并要求核实。**纠正方向正确，旧稿已经失效，新版尚未验收。**

9月13日00:17，用户进一步将“丽晶餐前酒和点心”更正为康得思酒店的免费品酒班，并要求利用菜单核实菜名（第1088行）。Agent明确采用新的亲历说明，分开酒店活动与丽晶晚餐；00:23已读取当时拍摄的高清菜单，并说明不能把菜单上的两个主菜选项都当成实际点餐。00:21的最新观察是Work仍open、candidate identity再次为null，revision为 `work-revision:a8749d99-2c87-4756-993d-b9dad8960fae`。这展示了正确的来源区分和候选撤下行为；以上量化指标仍固定初版，不把正在修订的内容混入旧指标。

Geo缺陷与餐厅问题直接相关：香港附近地点证据实际没有取得，不能将其说成“查过但没有店名”。已有地址、画面和用户信息仍有价值；后续调查保留真实来源与授权边界。Plan不需要读取私有数据库来替PreCheck修复批量采集，也不能以候选校验通过反向认证PreCheck交付正确。

原会话初版没有直接调用Geo Tool或独立VLM provider，但Agent自身确实使用多模态模型。“没有新增远程模型请求”应收窄为“未另接远程模型服务”。从进入Plan的用户消息起有45次模型响应；按上次“首次Result review起算”对齐，本次为 **62次，上次52次**。当前对齐范围的input为8,101,274，cached input为7,921,911，非缓存input为179,363，output为17,008 tokens。图像token和费用未独立拆出，两次推理设置也不同，不能换算总费用或宣称纯性能优势。

PreCheck的普通准备也有正面证据：2,136项metadata、198项rendition、181项成功video probe、543项frame Work和181项联系表完成；唯一probe失败为保留的损坏fixture。543是工作数，其中三个视频有重复实际PTS，不能写成543个不同视频帧。本报告没有将低帧率代理片的重复请求自动判作新的坏源，也未认证完整视频覆盖。

本次实际来源是 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`；workspace是 `/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e`。包verifier的清单SHA-256全通过，但总大小 **3,193,053,792 bytes** 超过2GB上限而失败。目录已有额外测试输出，不能称整个工作副本仍是原始fixture。另行完整核对了实际来源的2,134个manifest媒体和两个额外RAW，全部与对应包内字节一致。预览写在包根、source root之外，未改变这些媒体；后续评测输出应放包外。

审计代码基点是 `615c3359941927515f0c0a8738a3f08122bcad46`。工作区有其他任务修改；Geo、GPX和压缩关键文件与实际安装一致，orchestrator在审计期间又有其他任务变化，所以重放使用**实际安装的Python与包**。客户端未提供可独立证明的在运行构建身份，不以版本号替代精确证据。API endpoint为本地MediaSense MCP；被审计运行使用Google Geocoding、Google Places searchNearby及高德，审计探针只使用内存捕获transport。

原始会话、媒体、数据库和 [已撤回HTML审计快照](outputs/preview-after-withdrawal.html) 仅保留本机，outputs已被Git忽略。脚本固定原会话前859行的SHA-256，从原MCP inspect回执恢复初版候选，当前Work另列；缺少证据时不能静默换成新候选。初版身份为 `sha256:6841c4bd5228fe5f23e7aa1bf99378b0e8879fa877c29aa842cb9bd9747fd56a`。

复核命令：

```sh
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python3 eval/sessions/260912-2333-hk-run-acceptance/run.py
rtk proxy .venv/bin/ruff check eval/sessions/260912-2333-hk-run-acceptance/run.py
```

两项已通过。期间复核遇到原会话撤回候选而失败，随后改读固定历史回执，没有把业务状态改回去。本审计没有重跑模型、调用地图、修改业务数据库或提交Plan；没有进行TB级、故障恢复或完整原片测试。

按现有迁移分类：本地关联、Embedding、代表读取和对账为 `preserved`；Agent/Human共同解释、分开确认与执行为 `intentionally_changed`；Google POI全失败为本次证实的 `regression`；模型质量、总费用、TB级表现和组数减少是否更符合检索目的仍为 `not_comparable`。这是运行级发现，不改写既有迁移台账的能力处置权威。

建议先闭合Google请求构造与失败边界，再处理GPX重复工作和坐标消费；原Plan会话继续确认关键餐厅、复核例外安置，随后生成新版预览。按照 `yanru-guidelines`，现有Geo adapter/Tool、PreCheck producer和Plan Agent/Skill已经能够承载修复，无须新增阶段、服务或确认实体，也无须改变用户已确认的0.311默认值。


**2026-09-13 追加验收：正式 HTML 确认链路未接通。**

用户明确补充：HTML 是最终 Plan 的直接人工确认入口，应由产品稳定生成，降低对 Agent 编写页面的能力与 token 预算的依赖；不需要把本次菜品调查做成固定业务板块。这是确认交付职责，不是让 Tool 接管分组、命名或证据解释。

复核发现：

- [PlanPreviewRenderer](../../../src/mediasense/plan/preview.py#L60) 已存在，实际安装副本与源码一致，SHA-256 为 `fa0d521eb2d4c062883660bd1293666c256ad154a9242784277987a9641cff0b`。它能读取候选、生成目录/样图/例外/decision_notes，并写出HTML。
- 当前 [Plan Work 合约](../../../docs/spec/contract/plan-work/index.md) 只有 create/update/inspect/seal。安装版 update 响应只有 outcome/action/work_ref/result_ref/revision/state，没有预览入口或生成状态；CLI 也没有对应生成入口。生产代码中没有调用这个 renderer 的正常 Tool/Host 路径。
- [现有验收脚本](../../../tests/run_plan_interaction_smoke.py#L309) 在 MCP 保存候选之后，另行创建 Python RuntimeHost，通过 `local._datasets[dataset].plan_work` 调用 renderer。这验证了内部渲染和图片交付，但没有证明普通 Agent 使用 Tool 后就能取得 HTML。
- 当前 [Plan Skill](../../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md#L139) 要求 Agent “Generate the final Preview”，没有给它一个已接通的正式生成路径。这次 Agent 自写 `/tmp/render_mediasense_hk_preview.py` 是该缺口的实际表现，不能只归因于 Agent 没选对工具。
- 现有 renderer 仍是基础实现：目录默认只显示前100个不透明 Source Item 引用；超出部分提示“可进一步读取”，但静态页面没有接入对应分页交互。仅把这个Python类暴露给Agent，尚不足以交付所需的完整人工确认体验。

关于菜品板块，需要校正一个事实边界。当前10条菜品名称及依据均有对应的 Candidate decision_notes；不是所有内容都在 Plan 外。但是临时脚本第37—40行读取独立的 `dishAnnotations`，其 name/basis/path/source/url/ids 由 Agent 另行维护，没有从 Candidate 的 notes、适用范围和 Evidence 关系确定性推导。可见页面因此还依赖一套临时展示定义。最新被检查 HTML 的 SHA-256 为 `2a3e98ec956b45d4efa6246512c8547ae0cb26155d017bd95b6faeff4e7b2581`，其 Candidate identity 为 `sha256:691c36d0031b011cb97ea0216934dee4b08a6e00cdc5c9d0b6114f203a1221af`；这与前文初版统计分别记录。

上次验证“HTML嵌入的候选内容和identity匹配”，不能被扩大为“全部可见内容都由候选派生”。正式确认页面还需要验证可见分组、成员、说明、图片适用范围与实际将冻结的内容一致。

建议责任分配为：

| 责任 | 归属 |
| --- | --- |
| 理解素材、提出分组和命名、取得所需信息、把有影响的判断写入Candidate | Agent，受Plan Skill指导 |
| 保存并验证Candidate，生成对应HTML，处理图片和成员详情，报告生成结果及失败 | 现有Plan Tool与内部renderer |
| 阅读该版HTML并接受确切Candidate | Human |
| 根据确切内容、当前状态和有效接受进行冻结 | 现有Plan Tool |

应将自动预览纳入**保存完整Candidate**的正式交付：保存成功后，工具生成由该Candidate及其绑定Result派生的页面，返回可打开的位置与确切内容绑定。Agent负责呈现入口和说明，无须编写HTML、拼接JSON或访问Python私有对象。只保存笔记/偏好、没有完整Candidate时，不生成可供最终确认的假页面；生成失败应区分“候选已保存”和“预览尚未交付”，重试保持同一内容；候选变更或撤回后，旧页面不得被当成新版接受依据。

页面采用通用的目录、成员、例外、决定说明、证据与限制表达。若菜名调查影响最终计划，内容先进入现有Candidate说明，再由通用组件展示其确切范围与证据；临时调查材料不靠专门“菜品模块”进入最终确认页。按照 yanru-guidelines 与 agent-skill-tool-boundary，优先接通现有Plan Tool和renderer，避免新增第二份Plan权威或要求Agent承担重复的页面工程。

本项是新增的 **P1 产品交付缺口**。本次仅完成现状核实和责任界定，没有修改当前四动作合约、生产实现或原会话HTML。


**2026-09-13 第 4、5 包独立复核：第一轮讨论依据通过，尚非修复验收。**

本轮按用户给出的 surface `7B978889-A337-432A-B709-D83292FF6618` 重新定位实际会话。读取当前 cmux 对象、终端和对应进程打开的会话文件，确认对象位于 MediaSense 仓库。未向原会话发送消息或命令，未改变其焦点、任务或业务状态。

被验收会话为 `01a096f7-aaf8-7481-91ba-2fef40b3ced0`，文件为 `/Users/chengyanru/.codex/sessions/2026/09/13/rollout-2026-09-13T02-53-28-01a096f7-aaf8-7481-91ba-2fef40b3ced0.jsonl`。本次读取 180 行，SHA-256 为 `5a5352f6ed85e40d26d6f37ff83bce296b34ec0af64a0ad89203477c10b65d11`；首轮任务从 02:57 至 03:13（Asia/Shanghai）。它只有一条任务用户消息，明确要求先讨论且不实施；尚无对其最后建议的用户答复。记录中的文件变更仅为两个问题包 README，与“第一轮讨论中”的声明一致。

验收对象的文件身份为：

| 对象 | SHA-256 |
| --- | --- |
| 第4包 README | `00a352b3533dd33d703360e35a09d8a4729e7f50ba6dfc835f71f3a0df5c4f78` |
| 第5包 README | `cbae7a316d207c7a5035d55ded1e0e4076c31c869dd2e5ea9cd1fb5a179e3cca` |

本次独立核对了原始运行前859行摘要、实际Skill读取回执、代表材料的真实来源、精确成员与条件、GPX和控制标记的公开读取结果、用户补充和更正的先后，以及相关合约。29条本地文件链接通过检查。主要判断成立：

- **第4包属于已有职责的落实问题。** 原运行第514行读取的Skill与当前权威内容逐字相同，SHA-256为 `adac003173e98b31b015f5e134c0b49936b30c8c6e56e1bd9827101d012d69b9`，不能归因为新版指导未读。餐厅身份和活动关系可能改变检索与分组，应按其影响判断调查充分性；首版、用户推动后的修订与最终接受需分别评价。没有将后来的菜名研究偏好倒算成事前已知要求，也没有把用户起初对品酒与晚餐的说法当成Agent本应预知的错误。
- **第5包按现有Profile判断，无需先新增异常策略。** `invalid`、`unresolved`和`usable`不能独立决定逻辑归属；Apply合约明确允许容器无效但可安全作为字节搬移的情况。共同代表实际覆盖4项，画面来自另一台Pocket相机，原代表不可用后替换以及未逐项比较的限定均真实存在。包内没有将共同代表关系误当成内容等价证明。
- **默认细则向运行Skill的交付缺口确实存在。** 当时和当前Skill只概括相关素材、异常可见和Profile偏离，未交付 `a-files/`、`Uncategorized/`、`d-damaged-info/` 及其具体适用规则；唯一随包Profile参考是默认不适用时的替代方向。这个缺口可以直接复核，但不是已证明的唯一行为原因。
- **GPX与范围控制标记的用途区分合理。** 两份GPX为auxiliary/unresolved，已有available来源验证观察，但附带“普通变化检测，不是精确完整字节证明”的限制。两个 `.albumignore` 为auxiliary/usable，来源验证未检查。包内没有把它们仅按auxiliary标签统一移动，也没有把available观察冒充Apply已通过。
- **没有虚报完成。** 两包明确保持方案未定案；本轮仅文档复核，不存在新Skill交付、真实Agent行为改善、安装升级或业务Plan修复证据。记录的fixture verifier清单匹配、整体大小超限失败，也未被写成整包通过。本轮复核消费原始公开回执和既有验证记录，没有再次运行模型、地图、媒体处理或Apply。

没有发现阻止继续讨论的事实或职责错误。该结论不等于对某个具体新目录、菜名默认深度或实施方案作出Human确认。以下仍属于后续闭合条件：

1. 已有Profile细则需真正交付到所使用的Skill或其明确阅读入口，并验证实际安装内容；仅把说明留在问题包中不能算第5包已解决。
2. 第4包需要针对可得证据、用户检索目的和重要未知进行真实行为验证，包括关键缺口时调查、充分时直接推进、未知时诚实处置，以及更正后的改版。只检查文字出现或继续增加Skill段落不足以证明改善。
3. 具体菜名的默认研究深度可以继续讨论，不应成为执行已确定的主动调查职责和异常处置规则的前提，也不应从本次案例固化为所有数据集的必问步骤。
4. 普通合约允许留原位的 `other_outcome`，不要求每次都证明某种特殊原因；在已采用默认Profile的上下文中，本次需要评价的是具体处置是否有适用依据、偏离是否清楚，而不是新增“所有保留都必须证明异常”的通用门槛。

本次复核时仓库HEAD为 `0794d3c9182793b7b25c1cac77793e3c97e42092`，存在与1—3包相关的其他工作区修改。只在本验收报告记录复核，不改写4、5包作者的提议或把其状态提升为已实施。


**2026-09-13 第 1—3 包再次独立验收：源码与确切隔离安装包通过。**

本轮根据用户给出的 surface `C5F5E542-A1F8-4CD6-8995-A47E9174C281` 核对实际会话、补修代码、持久产物和既有合约。实际工作会话为 `01a096f7-4af9-7842-a8a5-6692f5b18287`；读取时共909行，SHA-256为 `6d42359ca698a5cbe824fcb73b52ee990201c862d24b058b9ae05b037d251288`。第657行保留此前独立复核的两个遗漏与旧产物丢失反馈，第906行为二次交付。未向原会话发送消息或改变其状态。

本轮验收绑定新 wheel `9e813bda30fa4b7cc33517d582aefd7547f48e7836a8a78ed7a0f9df31df9f9f`，不是恢复旧 `55db4708…` 的字节身份。持久目录为 [.local/acceptance-releases/260913-1107-google-gpx-r2](../../../.local/acceptance-releases/260913-1107-google-gpx-r2/REVIEW.md)，源码基点为 `0794d3c9182793b7b25c1cac77793e3c97e42092` 加该目录的 source.diff。

独立执行证据：

| 检查 | 本轮实际结果 |
| --- | --- |
| SHA256SUMS | 17项全部匹配，包括wheel、源码归档、差异、约束和原交付日志 |
| 源码清单 | 793个文件与5个符号链接全部匹配 |
| 包内容 | distribution artifact检查通过；8个关键生产文件在当前源码、快照、wheel与隔离site-packages中逐字一致 |
| 隔离安装包回归 | 以CPython 3.11.13/core环境、`-o pythonpath=''`及禁用pytest缓存执行14个相关测试文件，**166 passed，69.89秒** |
| CLI/MCP分发 | 按保留依赖约束，离线创建新的临时uv tool环境，真实CLI/MCP smoke通过；只清理该临时环境 |
| 额外Provider边界 | 本审计另写内存探针，通过生产 `_geo_tool` 装配，只替换最外层opener，验证9种场景及重放；没有真实Provider请求 |
| 原业务Result | 文件SHA-256仍与原审计值相同，未改写 |

第1项的两轮问题均在当前安装包得到闭合：独立组件的数量与半径上限、明确错误分类、停止与恢复、实际请求及未知费用保留都通过。回归覆盖明确quota/rate原因在HTTP 400/429/503下的行为。额外探针验证quota或服务禁用若先发生在地址组件则1次请求后停止，若地址成功后发生在附近地点则2次停止；后续组件或坐标保持not_requested。明确INVALID_ARGUMENT即使随429返回也直接抛执行异常，未分类400同样不伪装成地点缺口；已有attempt保留，重放零新增请求，原始错误message/metadata未进入journal。真正限流仅重试失败组件并保留2/3秒退避；地址限流时同坐标的独立附近组件仍可先完成，累计4次请求符合两组件与有限重试含义。探针最初误将这一情形的上界写成3，检查实际请求序列后按现有独立组件语义纠正了审计断言，没有改产品或降低其承诺。

第2项的重复准备实现与此前等输出优化结论继续成立；本轮补修后的真实producer、准入、executor、orchestrator和公开Run状态回归通过。超预算返回 `blocked / gpx_resource_budget_insufficient`，保留metadata成功和未尝试的GPX Work，不发布Result；原预算下resume仍如实阻塞，取消后以足够预算建立后继Run可复用metadata并完成GPX。未知RuntimeError仍暴露并成为execution_worker_crashed，不转换为正常资源等待。**586.77→54.42秒与4,068→2次是首轮历史全量测量，本轮没有重新测量全量耗时。**

第3项实现未在二次补修中变化；本轮核对metadata优先、GPX补缺、available筛选、受影响组Work依赖标记，以及真实GPX producer到压缩空间比较/限定的回归。没有发现阻断问题。**55个坐标补用、71→21个限定、156组成员不变是首轮全量证据，本轮仅重新验证有界生产链与安装内容，未把它们冒称新一轮香港全量结果。** 用户已确认的0.311保持不变。

本轮安装回归命令使用保留的 source 目录作为cwd：

```sh
rtk proxy env -u PYTHONPATH PYTHONDONTWRITEBYTECODE=1 ../venv/bin/python -m pytest -o pythonpath='' -p no:cacheprovider -q tests/test_google_nearby_requests.py tests/test_geo_tool.py tests/test_geo_recovery.py tests/test_geo_process_recovery.py tests/test_geo_capability_model.py tests/test_geocode.py tests/test_gpx.py tests/test_gpx_preparation.py tests/test_gpx_resource_delivery.py tests/test_compression.py tests/test_compression_gpx.py tests/test_source_validity.py tests/test_resources.py tests/test_precheck_orchestration.py --tb=short
```

分发复验在仓库根运行保留快照内的 `tests/run_distribution_smoke.py`，参数为该wheel、`--offline`、该目录 `dependencies.txt` 约束和保留venv的Python。没有从checkout注入产品包；没有为审计下载依赖或加载模型。一次额外探针最初误用RuntimeConfig字段名而未执行，按真实装配接口修正后完成上述9种情形；失败不计入产品缺陷。

**通过范围是三项源码修复与这个确切隔离安装包，不是日常环境或历史业务恢复。** 本轮只读比对显示日常安装的geo.py、gpx.py、压缩producer和orchestrator仍与候选包不同，且摘要仍为原运行版本。日常CLI/Skills/已开Host未升级；旧失败Result没有被修复成成功，真实地图恢复和新的业务Result尚未执行。本次没有发现需要重新讨论产品语义的阻断问题，也没有给这些未执行事项记通过。


**2026-09-13 第 4、5 包再次独立验收：实现与确切隔离交付通过，行为结论限定于已运行场景。**

本轮重新读取用户指定的 surface `7B978889-A337-432A-B709-D83292FF6618`。当前交付会话为 `01a098d2-c21d-7a81-a37a-6907ec1b5368`，从此前讨论会话继续；第52行是用户“直接开始开发”的授权，第766行是最终交付。本次固定读取770行，SHA-256为 `6ef623dcac2ceaf7b6e0c756745e7000f97e154dbe423d652adf8895f87fb019`。没有向原会话发送消息或命令。本段更新此前“仅讨论通过”的状态，不改写当时的判断。

没有发现需要退回修复的阻断问题。第4包把重要缺口、可支持的粗表达和后续更正落实到既有Plan Skill；第5包补齐完整默认组织规则的离线交付，并要求按关联与上下文处置异常。默认Profile全文未改变，Skill引用其逐字发布副本；没有新增Profile对象、固定提问配额、condition统一去向或Tool语义认证。公开contract和schema无变更，仍使用现有Work、Candidate、decision_notes与Source Sets。

本次绑定 `.local/acceptance-releases/260913-1214-plan-skill/candidate-02/`，源码基点为 `0794d3c9182793b7b25c1cac77793e3c97e42092` 加明确列出的覆盖文件；没有包含第1—3包在途补修。独立结果见[复验指标](metrics/plan-packets-4-5-revalidation.json)，开发方原始材料见[行为验证报告](../260913-1214-plan-skill-behavior/report.md)。

| 独立检查 | 实际结果 |
| --- | --- |
| 最终wheel | SHA-256 `249398c2150fbf129a946c9822b174dab150bc57eff1efedc1386d8dfcd2b7ef`，身份匹配 |
| Skill交付 | 当前源码、构建快照、wheel和隔离site-packages逐字一致；Skill为 `16f15bb281460d05bdd61bb6b7ba1e3360757e1b1356c06a69d7a816d1842950` |
| 默认Profile | 发布副本与权威逐字一致，SHA-256 `5f561a600a397e4ce96b3a57abf10ae3f2bc5c8c08b53f2bbc4bd50349523189`；7条会话均有完整读取回执 |
| 安装版回归 | 独立复跑7个相关测试文件，**169 passed，10.83秒**；确认导入隔离安装，清除PYTHONPATH、禁用源码注入和pytest缓存 |
| 离线分发 | 用保留约束重新创建临时uv tool环境，实际安装、Skill安装、CLI/doctor和MCP检查通过；首次被沙箱拒绝访问已有uv缓存，按相同离线范围重试成功 |
| 行为数据与保存结果 | 7条会话前缀摘要、63次Read/Plan业务调用、18次discovery及35次图卡打开核对一致；7个最终候选均唯一完整对账、保持open，全部合成源与Result字节未变 |

安装版检查使用CPython 3.11.13/core组合。开发方记录的1377项完整源码测试属于首版隔离导出，本轮没有重新运行；首版至最终版的生产差异仅为Skill的模型处理与费用说明。独立测试命令、JUnit和分发日志保留在忽略目录[本轮原始验证输出](outputs/plan-packets-4-5-revalidation/)，没有把临时安装、数据库或原始轨迹加入Git。

第4包的实际候选有可核对的改善：旅行场景保留餐厅与活动两类检索线索，未知餐厅和品鉴归属进入调查；用户记不起时，候选明确保留店名、场所和活动关系的限制，没有猜酒店或把品鉴直接并入晚餐。书展与散步场景直接形成两个浅层活动目录，没有为了缺少城市或河名增加无关问题。后来更正品酒班归属时，真实update替换候选，相关两项改为独立酒店活动，其他组的成员保持；菜单选项没有变成全部实际点餐的事实。非餐饮场景也实际展开共同代表中的独立图卡，最后分开看展和体验课。

第5包的实际候选保留了不同处置的含义：损坏原片与两个可读版本及另一相机素材同组，但明确说明共同代表、同stem和时间关系不认证修复完整或内容相同。遮挡但可读的视频停在可信旅行日期层；只知旅行的坏片、无背景坏片和可读未决项分别保留对应上下文与兜底。相关GPX进入旅行辅助资料，两份控制标记留原父目录；另一场景中属于朋友其他徒步活动的GPX单独保留，没有仅按扩展名加入当前活动。依据、未知和适用成员在实际Candidate中可读，不只是报告中的解释。

7位执行者不能记成“最终版首轮7次全部成功”：首版4位后续重读升级内容，其中过宽的“无模型调用／费用”说明经修订才消除；最终版有另外3位从头执行。旧候选、修订和资源读取身份均保留。本轮确认了7次启动的 `fork_turns=none`、模型均为 `gpt-6-astra / low`，以及实际资源读取、命令、图卡和候选结果；任务及Agent间消息正文在本机JSONL中为加密内容，无法逐字独立审计全部提示和模拟回答。因此，本轮不认证严格盲测的无提示成功，也不从这些场景推导改动的因果收益或未来较弱模型的成功率。

**通过范围仍不包括日常安装、原香港Plan重做或最终人工接受。** 日常安装的Plan Skill仍是旧摘要 `adac003173e98b31b015f5e134c0b49936b30c8c6e56e1bd9827101d012d69b9`；原香港Result仍为最初审计的 `1f9141e72d3fa01b47f8edebc8990d4fc531761bb6801214a9411aede945c638`。本次不认证Python 3.13.5加embeddings、1—5包整合发布、真实照片识别、大集合阅读效率、seal或Apply。HTML自动交付继续属于第6包；已有Preview测试通过不能记为第6包修复完成。
