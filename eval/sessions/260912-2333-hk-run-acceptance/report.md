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

| 编号 | 独立交接包 | 当前阶段 |
| --- | --- | --- |
| 1 | [Google 附近地点请求失败与 PreCheck 交付状态](../../../openspec/changes/review-google-nearby-failures/README.md) | 事实已记录，待讨论 |
| 2 | [GPX 匹配重复工作与本地处理耗时](../../../openspec/changes/review-gpx-matching-cost/README.md) | 事实已记录，待讨论 |
| 3 | [视觉压缩未消费已有 GPX 坐标](../../../openspec/changes/review-compression-gpx-evidence/README.md) | 事实已记录，待讨论 |
| 4 | [Plan 初版的信息收集与过早提交最终确认](../../../openspec/changes/review-plan-information-sufficiency/README.md) | 事实已记录，待讨论 |
| 5 | [Plan 对损坏、未决与辅助素材的处置依据](../../../openspec/changes/review-plan-exception-dispositions/README.md) | 事实已记录，待讨论 |
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
