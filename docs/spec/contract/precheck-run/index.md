---
id: "precheck-run"
title: "MediaSense PreCheck Run Tool Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-09-14
timezone: "Asia/Shanghai"
parent: "index-contract"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "precheck-read"
  - "clarify-260827-1604-tool-operation-contracts"
superseded-by: ""
tags: ["mediasense", "precheck", "tool-contract", "run-lifecycle"]
---

# MediaSense PreCheck Run Tool Contract

本页位于稳定合约目录。当前规范以此处为准；迁移到此目录本身不构成新的实现或真实数据验收。


`mediasense.precheck.run` 控制一次持久、可恢复的 PreCheck 执行。
[Tool Schema](precheck-run.tool.json) 是唯一交换值规范；
[lifecycle.mock.json](lifecycle.mock.json) 是合成调用示例。
本合约采用零公开 API 兼容政策；旧 request 包装、operation 别名及冗余返回不再公开。
源媒体只读；不可变 Result 的封存内容和引用不因接口更新而改写。

范围清单只揭示请求层级：目录的 `representative_paths` 为空，文件项可重复其自身路径。
更深的名称需要显式 `scope_path` 展开；发现错误只返回该层级路径和错误代码，不回显隐藏后代的诊断文本。
这减少提前暴露，不提供盲测隔离：正常 `accounts_for` 仍保留排除项的精确身份和追溯。
独立评估的允许输入和干净上下文由评估入口负责，不能把 scope exclusion 当作检索访问控制。

### D1. MCP 方案 A 与单一规范

保留 `mediasense.precheck.run` 和 `mediasense.precheck.read`。两者公开输入都是扁平对象，
含 `action`、`dataset_ref` 及该 action 参数。其他 Tools 输入不改。`dataset_ref` 先定位当前 Host
已经打开的 Dataset；子引用必须属于它，不扫描全机、不给默认 Dataset、不建全局引用索引。
不存在与其他Dataset内的子引用对普通调用统一使用run_not_found/result_not_found/reference_not_in_result，
不查询其他Dataset来区分；只有请求明确提供的Dataset互相矛盾才使用reference_not_in_dataset。
Host 重启需重新 open 同一 Dataset，Run/Result 引用仍稳定。后继 start 也显式带 dataset_ref，
同时验证 prior_result_ref 的 Dataset；不是两个 competing Dataset 来源。

MCP 直接暴露业务 inputSchema，不再给 PreCheck 套 request。RuntimeHost.call_tool 现有
dataset_ref 参数作为进程内路由保持，但调用前强制与 request.dataset_ref 一致；所有内部消费者
通过固定 Dataset 的现有 read callable 注入路由值，不让 Plan 自己探测 PreCheck 存储。
公开 API 无 operation/action 双别名，无旧 request wrapper。JSON Schema 是交换值权威，
代码共享校验，不给 UI/CLI 再维护另一套字段。MCP 成功用 structuredContent，content 为空，
不把相同业务 JSON 重复注入模型；业务/host error 用相同 error 对象且 isError=true；
查询到 failed Run 则 isError=false。图片是否打开由 Agent 决定。

错误区分 invalid_request、dataset_not_open、reference_not_in_dataset、run_not_found、
result_not_found、result_unavailable、result_untrusted、result_inconsistent、invalid_cursor、
unsupported_include、invalid_source_set、response_item_too_large、invalid_state、idempotency_conflict、
confirmation_required、confirmation_stale、already_running、host_operation_failed。
host 未预期异常仍保留 diagnostic_id、记录日志且不伪造 Run 业务状态。error.current_state /
allowed_actions / run_ref 仅在有事实时附带。不存在/外 Dataset 的子引用不得泄露其他 Dataset 内容。


### D2. 运行状态与控制

正常状态沿用 running/paused/blocked/completed/cancelled/failed。没有新的 queued/cancelling。
progress、issues、reason 读取现有持久事实；status 绝不推进、重启、认领任务。
reason 与允许动作由同一快照导出：响应且推进新鲜→无 reason；响应但安静→no_recent_progress；
旧 owner 心跳失效→保留原 running 并显式 suspected_stalled、resume/cancel。已知 owner 退出要执行
现有暂停恢复或失败转换，不能永久伪装 running。保留当前活性阈值配置，不新造心跳协议。

start 持久创建并启动 worker 后返回 run_ref；相同 request_id 重放不重启 worker。
同 Dataset 另一个未结束 Run → already_running 并带原 run_ref。pause/cancel 成功意味着控制已持久
接受，返回当时 state；resume 成功还要求 worker 已获执行权。目标已达成重复调用无新效果；
状态竞态按现有锁/事务拒绝 invalid_state。终态只能读，不能 resume。无新 request_id 型控制令牌。

完成时 result 取自通过完整性校验的不可变 Result，含 ref/coverage/readiness 和必要 qualifications。
去掉 integrity 常量不去掉 seal/hash/reference checks；Read 成功即证明完整性，Plan 接受受信
Read 的 plan_ready，不读取隐藏字段。coverage 是范围对账，与地点缺失率无关。


### D3. progress 与动态诊断

progress 固定五字段 phase/unit/processed/total/last_progress_at，数量与时间不可知用 null。
先沿用现有 coordinator 的报告阶段，不把并行各 producer 做伪总体合计。
phase 为现有公开阶段枚举；unit 默认 logical_operation（对应该阶段唯一 Work），Geo 用 location_query，
其中旧 external_evidence 在本次 PreCheck 契约中统一叫 geo，不保留第二个同义阶段。
仅能证明一文件一单位的发现阶段用 source_item。不得把多个 video-frame Work 标成视频数。
processed=成功计算+有效复用+不会再自动重试的终结失败；可重试失败仍在未处理部分，每 Work 计一次。
同阶段当前附属 work_id 集合定义计数域，换阶段重置。同阶段集合被库存重查或需求重建改变，
本次变更事务写入现有 Run 的 reason=progress_scope_changed 和 last_progress_at；持久到下次阶段
切换，提醒客户端重置比较。未知 total 不估算；不增加公共 progress ID/任务实体。
单一 reason 冲突时优先级为终态/阻塞/确认原因 > suspected_stalled > no_recent_progress > progress_scope_changed；
低优先的集合变化作为 issues 中 code=progress_scope_changed 说明（unit=phase，count=1），保留到阶段切换。
last_progress_at 由真实持久推进更新（含终结失败/复用/阶段切换），不能由 status 或心跳刷新。

默认 issues 按 phase/code/unit 分组最多5类，按单位去重；更多类标 issues_truncated=true。
status include=diagnostics 返回全部分类分页（50默认/200最大）和当前阶段 work 精确分项、效果摘要。
分页游标绑定 Run、所选字段、limit、排序及 canonical diagnostic content digest；心跳不改变摘要，
实际诊断变化返回 invalid_cursor 要求重读，无新 snapshot store。cursor 内携带 bound digest，
使用现有校验/编码工具且验证全部绑定，不暴露未校验调用参数。频繁变化时可读最新首页，终态可读全量；
这只影响审计一致性，不影响控制与主 progress。
status include=accounting 返回 discovered/accounted/scope_condition 及 selection/provenance。
status include 允许accounting与一个分页详情组合，diagnostics与confirmation不能同请求分页；
scope_path/scope_after只能用于源范围确认视图，不能与page或其他include混用。
这些统计可在 Run 终态读，不用伪 Result 或缓存路径作为交接。scope 子树分页保留 scope_path/scope_after。


### D8. 确认与字节边界

保持 scope default+exceptions、inventory_fingerprint、外部 content_identity+geo_request_fingerprint
和可信 elicitation 机制。既有大小桶、kind计数、代表路径与不完整发现保留；scope view简化为
immediate entries，每节点含递归文件统计及可展开目录数，固定有界63项，scope_after绑定指纹和路径。
范围变更重新确认，遗漏不当做排除；accepted selection按需 accounting读取。
外部 disclosure 复用共享 Geo的实际数据类 `coordinate/datum/locale`（含必要 lookup controls说明），
不能按早期 mock 的复数字符串制造不被 Tool接受的授权。

外部披露若超524288字节：status只返回confirmation summary/identities并提示详情分页，
status include=confirmation + page分页坐标（默认50/max200）；全部页绑定同一完整披露摘要。
可信客户端调用resume(proceed)时由 Host读取整份冻结披露，不以Agent已读几页作为授权凭证；
无法在客户端完整呈现则 confirmation_unavailable 零效果停止，不允许截断确认或按页分别授权。
非分页默认披露能装入则内联。取消窗口仍 paused；decline终止Run，未授权不能以地点失败旁路。


### D9. 规范校验与交换值边界

Tool outputSchema 是所有action返回的并集，用于MCP发现。运行时还必须按输入action选择
Tool Schema 中的 responseSchemas[action]校验：控制的简单state不能让status省掉progress、reason或Result。
responseSchemas是以outputSchema为根解析的schema片段，复用同一份$defs；不复制字段定义，
编译时组合outputSchema.$defs与片段即可；当前合约测试从稳定目录加载这些定义。
新Geo观测按name分支约束value形状，缺失/失败basis必须存在，观察完整度仍由语义校验负责。
公开error.code集合允许扩展但不得重用语义；所有新分支需明确code，不解析message。
合同内复用的access、basis、provenance等开放数据字段保留现有扩展语义，不把它们误当成任意行为指令。
该设计不把json_value的开放性用于掩盖尚未定义的必需字段。


## Geo 与结果交接

共享 Geo Tool 的[有限重试与授权规则](../geo-query/index.md)控制实际请求。
PreCheck 对每个 Source Item 投影地址与附近地点两个 Observation。
无坐标、已查询无结果、已终结的已知服务失败和按策略未请求，均不单独阻止 Plan。
正在确认、仍在执行或外部效果不确定，不得被这些合法缺地点结果冒充。

[Result Read 合约](../precheck-read/index.md)维护完整性、分页、精确成员、
组件状态、消费者校验和合法历史投影。覆盖是否完整与是否 plan_ready 保持独立。

## 本期准备深度与配置

### 普通 Run 与完整 Processing Profile

按已确认的[基础模型](../../../model/model-260913-1408-precheck-basics.md)，改要求创建新的普通 Run，恢复继续原 Run；Profile 是配置值。`start` 可附 `source_set` 和 `profile`，正反例见 [composition.mock.json](composition.mock.json)。本次实现与隔离验收单独记录在[验收包](../../../../openspec/changes/simplify-precheck-run-composition/acceptance.md)，不借用此前发布的验收。

`source_set` 必须带 `prior_result_ref`，并恰好选择该 Result 的全部 `accounts_for` 成员 S。辅助、排除和异常条目的角色保持；新发现文件不加入 S。省略它则普通发现和范围确认继续适用。`prior_result_ref` 仅为关联和引用上下文，不继承旧参数或范围。

省略 `profile` 固定当前 Dataset 默认值；提供时必须完整声明 `configuration_identity`、`compression`、`overrides`。每个非 null compression 必须提供 `target_entries`、`temporal_scale_seconds`、`spatial_scale_meters`、`content_distance_scale`；四者分别控制数量后备、时间尺度（秒）、空间尺度（米）、余弦距离尺度。距离尺度为正数，数量为正整数；较小内容距离使内容区分更严格。null 跳过该分区最终自适应压缩。不得给 override 补默认值或合并旧 Profile。

非空 overrides 必须有显式 S；每项 source_set 选择 S 中非空、可处理的 source_media，彼此不交叠，即便参数相同也不能交叠。数组位置用于回读，不是优先级。各 T 使用其完整参数，剩余 source_media 使用 base 参数，最终压缩不跨分区。旧代表跨界时先按真实成员展开；代表自身属性不能成为其他成员的事实。初始准备预算仍由冻结的基础准备配置决定，override 成员成为定向准备需求。准备缺失的必要输入、保留有效计算和未受影响的工作；范围外分组可随真实依赖改变，Read 保留实际成员和依据。内容比较关闭而 override 改变内容阈值时返回 `configuration_invalid`，不启用模型或假装生效。

`configuration_identity` 是固定非公开准备语义的 SHA-256 内容身份，不是实体、查找句柄、缓存键或授权。规范值为 `{"kind":"precheck-preparation","values":...}`；JSON 使用 UTF-8、对象键排序、数组原顺序、不转义非 ASCII、紧凑分隔符，拒绝非有限数字。values 恰含 metadata、gpx、image_renditions、video、bundles、visual_selection、embedding、sensitivity、geo、compression_recipe。分别绑定完整有效 MetadataProfile（含知识/上下文）、各启用策略和安装配方、视频帧数、基础初选配方/目标/显式定向输入、有效模型语义与不可变身份、排序的检测器及停用策略、现有 Geo 查询/路由/重试语义、压缩及代表选择配方和固定比较设置。影响输出的实现修订进入配方；模型身份缺失明确失败，读取有效缓存不加载模型。

公开压缩参数和 overrides 不进入此投影；基础初选 target 仍进入 visual_selection。Run 身份、Dataset 名称、产物和模型路径、存储提示、批量、线程、资源调度、凭证及旧确认不进入投影。运行选项若影响含义，必须进入其所属配方。新请求在任何 worker/producer 效果前比较当前投影，失配返回 `configuration_changed`，绝不回取旧配置合并执行。恢复保留原配置；先查幂等绑定，已接受的原请求在默认值变化后仍返回原 Run，内容不同为 `idempotency_conflict`。

紧凑 `{source_set, profile}` 请求部分最多 262144 UTF-8 字节，超限为 `invalid_request`。形状不完整为 `invalid_request`；空/交叠/非媒体 override 或不完整外部 S 为 `invalid_source_set`；Result 外引用为 `reference_not_in_result`。非法请求不创建新 Run。worker 对显式原输入校验源 attachment 和观测版本：检测到变化为终态 `source_snapshot_changed`，源不可用为有明确恢复前提的等待。匹配强度如实保留，未知历史不伪造。

Result 封存完整 Profile、配置投影、精确 override 成员和直接输入绑定；它们属于 Result 留存数据，不依赖可变 Run/Work 或可驱逐 producer 缓存。同次发布重试只有一个 Result；新 request_id 创建新的普通 Run/Result。旧 Result 字节、材料留存及引用保持，读取语义见 [Read](../precheck-read/index.md#准备回读与直接来源对应)。

厂商知识和 metadata 时区按[厂商知识契约](../manufacturer-knowledge/index.md)读取。新 Run 固定完整知识和上下文到现有 execution_config；恢复使用原快照，新 start 重读当前文件，幂等重放不重新解释。`configuration_invalid` 表示新工作采用的配置无效，不创建本次执行；它不同于条件不匹配、缺判断信息或某属性的规则冲突。控制请求沿用当前 schema，不把整份知识重复放进每次 Run 请求。

本节是第一里程碑确认的准备义务；第二里程碑已完成实现和安装入口验证，并通过用户验收，具体范围与仍未认证事项见既有迁移台账。start/status/pause/resume/cancel 的请求字段继续使用现有 schema；不增加任意 producer 参数或新的 stage。

| 能力 | 默认准备范围 | 必须保留的边界 |
| --- | --- | --- |
| 廉价 metadata | 所有纳入的可处理源媒体及有关侧车 | 按 [属性义务](../precheck-read/precheck-attributes.md)提取时间、相机、镜头、曝光、ISO、源尺寸、原坐标等；失败按项交代，不能退回全量高成本视觉处理 |
| 初步关联与压缩 | 本地时间、同名/侧车关系及可用比较证据 | 先后顺序是可替换方法；保留精确成员、方法依据、跨度与有损限制 |
| 普通/高清静态图 | 被选中进行视觉准备的源项 | 同时提供独立可复用的普通图和高清图，尽量共享解码；高清不再依赖 embedding 或检测开关；未选中成员不默认生成 |
| 视频 probe、帧和联系表 | 被选中进行视频准备的源项 | 有限准备包含可用的起始、中间和结尾材料；按实际帧去重，保留请求与已知实际位置、时长、尺寸和失败；不承诺全视频视觉覆盖或任意时刻即时补帧 |
| 本地 embedding | 显式配置启用；覆盖选中的输入材料 | 保留已验收的安装入口、有效模型身份与复用；不自动下载或回退远程 |
| 敏感性检测 | 默认关闭；显式启用后检查已准备静态高清图和所选视频帧 | 逐模型选择的本地能力分别保留检测器、真实输入、具名值、profile 和失败；不推断远程路由 |
| GPX/Geo | 复用已有采用策略及现有 Geo Tool | 默认无外部效果；有请求时按现有冻结批次与授权；每个 in-scope 源项都有两组件状态，未请求不是 no_result |

准备范围不同不等于结果属性可缺而不报。未选中高成本输入可标 `not_checked + evidence_not_prepared`；配置关闭可标 `capability_disabled`；依赖不可用、执行失败、未实现或未接通必须分别处理。用户选择启用而后端不可用时沿用可恢复的 backend-unavailable 状态，禁止静默跳过后宣称完成。

### 本地敏感性模型（2026-09-12 授权采用）

用户/Dataset `config.toml` 的 `[sensitivity]` 整表覆盖；不增加 Tool action。
总表仅允许 `enabled`（布尔，默认 false）与 `models`；models 仅允许 `freepik`、
`nudenet640`。每项仅允许 `enabled/profile/model_path/device/precision/batch_size`。
省略模型或 enabled=false 表示关闭。总开关关闭时所有模型关闭。所有键和类型均校验，
关闭不掩盖非法值；路径若提供须为绝对路径，启用项必须有路径。
已知配方的 profile/device/precision/batch_size 可省略，解析为以下固定值：

```toml
[sensitivity]
enabled = true
[sensitivity.models.freepik]
enabled = true
profile = "freepik-ordinal448-mps-fp32-v1"
model_path = "/absolute/local-models/freepik-snapshot"
device = "mps"
precision = "float32"
batch_size = 4
[sensitivity.models.nudenet640]
enabled = true
profile = "nudenet640-native-cpu-fp32-v1"
model_path = "/absolute/local-models/640m.onnx"
device = "cpu"
precision = "float32"
batch_size = 1
```

只发布这两套配方；不支持的值明确拒绝，不下载、不换设备、不回退。
旧 `device/nsfw_model_id/nsfw_revision` 配置须显式迁移，不自动替换模型。
配置错误阻止新 start，但不阻止历史 Read 或使用已冻结快照恢复。
新 Run 冻结全部有效选择、声明及本地资产位置；resume 使用原快照。
停用模型在新 Result 中为 `not_checked + capability_disabled`，包括已有缓存也不纳入；
旧 Result/Work 保留，后继重新启用可复用。没有输入时为 `evidence_not_prepared`，不造 Evidence。

适配器声明不加载推理库，说明图片条件、输出种类、taxonomy/分数含义、设备、批量及资源估计。
每次输入为唯一键、本地已定向单帧图片、内容身份和实际尺寸；每键恰有一个具名值结果或
已知局部失败，返回顺序可变。重复、缺失、错绑或非法输出是执行缺陷，提交前拒绝。
适配器不接触 Dataset 私有存储或 Plan 策略。

Freepik 固定 revision `15b85477e4fd2000db76ae9aae0f89a72f95e2e3`、
权重 SHA256 `024a9d4818fae2656403bf626c9f8c9e7789c2da274749fbebb1060d8fdaa7ab`，
官方 Timm 448px bicubic squash、原生 mean/std、MPS FP32，无 autocast，batch 4。
640m 权重 SHA256 `04fe3d77980780c1f8297dc6d7f942fd5b3abe6942a188f742a85241e4f634eb`，
NudeNet 3.4.2 native 预处理和 class-agnostic NMS（candidate .2 / score .25 / IoU .45），
CPU FP32、batch 1；保留镜像来源限制。逐模型批量独立于 embedding。

模型加载到释放始终受已有资源准入负责；需求不截小以适配预算，不足时明确拒绝准入。
声明估计和实际测量分开；未测为 null，批次时间不冒充逐图实测。
有效 Work 身份绑定输入、权重/处理器、语义配方、输出及影响结果的实现/运行时，
不绑定完整模型名单、本地路径或纯调度。有效缓存命中无需推理库/权重。
需要新执行但缺固定资产/后端时 `sensitivity_backend_unavailable` 阻塞，保留兄弟成果，
恢复确切前提后沿原快照继续；不发布本次完成 Result。已知单项失败为真实输入上的 failed，
未知异常和协议错误沿 Host/执行失败暴露，不能变成正常等待或坏源。

Read 只消费已准备材料。本期不新增通用“任意高清/任意视频帧”获取 Tool；需要超出已有准备的内容时，Plan 可以使用已存在的合法能力，或明确请求后继 PreCheck。普通候选不足不自动要求重跑整个阶段。

### 准备有效性、执行成本与发布证据

progress 的终结工作数、范围对账完整、准备义务满足、plan_ready 和发布的运行品质分别由各自证据支持；不能用终结失败或重复帧凑足有效准备。正常坏源按项保留；采样器制造的不可解码目标须作为实现问题修复。有限材料是否足够支持具体组织判断，仍由 Agent 和用户判断。

每项 Work 保留独立身份、依赖、输出和失败责任；执行可以共享批次、进程、解码上下文及数据库连接，不要求逐项启动或提交。有效配置和重要资源限制进入已有 Run 诊断；实际可执行的并发/线程上限与内存估算、观察值分别说明。仅改变不影响结果含义的调度分组或并发，不使有效成果失效；真实语义或有效性依赖变化只重做受影响工作，保留无关成功结果和旧 Result。

耗时不作为跨设备固定 API 常量。相关发布须在声明的输入、输出规格、版本、资源与缓存条件下，同时验证相同有效工作量、首次准备、后继复用、局部变化和实际安装入口。门槛与实测归入对应 OpenSpec 验收和既有评测/迁移台账，不能用少输出的总时长证明吞吐改善；真实 fixture 之外的未认证范围明确保留。

### Geo 服务前提与恢复

Geo 的地点级终结失败与适用服务不可达遵循 [Geo D6](../geo-query/index.md#d6-有限执行目标地域和公开恢复)。后者保留已取得证据并 blocked，不发布本次 Result。status 说明缺失条件；用户处理网络或配置后通过既有 resume 进入缺失组件恢复确认，明确 proceed 才能产生新效果。恢复披露原累计请求/费用和上限、保留组件及实际网络接收边界；旧确认不覆盖新的 Proxy。已持久化响应的本地投影重放不产生新地图请求，未知历史费用保持未知。

恢复调用顺序：blocked 时发送 `resume` 且省略 decision，准备恢复确认；进入 paused 并取得完整 confirmation 后，才发送 `resume + decision=proceed` 触发可信确认。前一步不授予新的外部效果，不能把尚无披露时的 proceed 当作授权。

### 本地模型执行诊断（敏感性验收补修）

`status include=["diagnostics"]` 增加 `diagnostics.local_execution` 汇总；
`status include=["local_execution"]` 返回相同汇总和 `batches/page`，复用既有 page，默认50/最大200。
local_execution、diagnostics、confirmation 三种分页详情一次只选一种，可同时读取 accounting。
游标绑定冻结 Run 配置及规范化执行事实摘要；事实变化时游标失效，不能因心跳失效。

local_execution 包含 status、resource_budget、models；resource_budget 是原 Run 的有效准入
capacity/max_workers/max_pending，不是实测内存。每模型保存请求的 device/precision/batch_limit、
memory_estimate_bytes、成功/失败/待完成 Work 数及 unreported_work_count。
recorded_current/recorded_reused 分别汇总有可证明记录的本次和复用批次；不是整个流程耗时。
批次保存 batch_id（仅去重依据，不可独立调用）、观察时间、请求 input_count、实际
inference_input_count、此范围 included_work_count、processing_wall_seconds、load_wall_seconds、
实际设备/精度及 measured_memory_bytes。不可测为 null。处理墙钟是 analyze 调用区间，不含独立加载，绝非逐图实测。加载耗时为null时，不能推断适配器内部加载与分析可分离。

一次适配器调用产生一个批次身份；多个 Work 保存相同记录时只计一次，内容不一致则拒绝。
复用批次保留原整个调用的输入数/耗时，并用 included_work_count 标明当前引用了多少项，
不能将原四张批次的成本改成其中一张的实测值。按批次汇总，不相加 Work 的重复时间。
旧 Work 没有可证明批次身份或分离计时，计入 unreported_work_count；不得按相同数值猜测分组。
尚无冻结配置时 status=not_recorded、预算null；旧 Result 缺此快照同样明确未记录。
唯一机器定义为本 Tool 的 local_* $defs；Read 携带受一致性检查约束的生成片段。
