---
id: "precheck-run"
title: "MediaSense PreCheck Run Tool Contract"
type: spec
status: active
created: 2026-08-27
updated: 2026-09-11
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

本节是第一里程碑确认的准备义务；第二里程碑已完成实现和安装入口验证，并通过用户验收，具体范围与仍未认证事项见既有迁移台账。start/status/pause/resume/cancel 的请求字段继续使用现有 schema；不增加任意 producer 参数或新的 stage。

| 能力 | 默认准备范围 | 必须保留的边界 |
| --- | --- | --- |
| 廉价 metadata | 所有纳入的可处理源媒体及有关侧车 | 按 [属性义务](../precheck-read/precheck-attributes.md)提取时间、相机、镜头、曝光、ISO、源尺寸、原坐标等；失败按项交代，不能退回全量高成本视觉处理 |
| 初步关联与压缩 | 本地时间、同名/侧车关系及可用比较证据 | 先后顺序是可替换方法；保留精确成员、方法依据、跨度与有损限制 |
| 普通/高清静态图 | 被选中进行视觉准备的源项 | 同时提供独立可复用的普通图和高清图，尽量共享解码；高清不再依赖 embedding 或检测开关；未选中成员不默认生成 |
| 视频 probe、帧和联系表 | 被选中进行视频准备的源项 | 有限准备包含可用的起始、中间和结尾材料；按实际帧去重，保留请求与已知实际位置、时长、尺寸和失败；不承诺全视频视觉覆盖或任意时刻即时补帧 |
| 本地 embedding | 显式配置启用；覆盖选中的输入材料 | 保留已验收的安装入口、有效模型身份与复用；不自动下载或回退远程 |
| 敏感性检测 | 默认关闭；显式启用后检查已准备静态高清图和所选视频帧 | 两类本地检测能力均需接通，分别保留检测器、输入、分数/标签、profile 和失败；不推断远程路由 |
| GPX/Geo | 复用已有采用策略及现有 Geo Tool | 默认无外部效果；有请求时按现有冻结批次与授权；每个 in-scope 源项都有两组件状态，未请求不是 no_result |

准备范围不同不等于结果属性可缺而不报。未选中高成本输入可标 `not_checked + evidence_not_prepared`；配置关闭可标 `capability_disabled`；依赖不可用、执行失败、未实现或未接通必须分别处理。用户选择启用而后端不可用时沿用可恢复的 backend-unavailable 状态，禁止静默跳过后宣称完成。

敏感性的安装配置复用现有用户/Dataset `config.toml` 及覆盖规则，只增加一个表：

```toml
[sensitivity]
enabled = true
device = "cpu"
nsfw_model_id = "Falconsai/nsfw_image_detection"
nsfw_revision = "<本地已有模型的40位不可变commit>"
```

表省略或 `enabled=false` 为关闭，enabled 省略也按 false，不因模型文件存在自动启用。enabled 必须为布尔值；表内仅允许上述四个键，未知键或非法类型按既有配置错误拒绝。启用时 `nsfw_revision` 必须是40位十六进制 commit；nsfw_model_id 默认上述仓库，device 默认 cpu，允许 cpu/mps/cuda，实际后端不支持则明确返回不可用。NudeNet 使用发布包声明的本地依赖和权重，记录真实 package/weights identity；安装必须校验所需本地权重已存在，不允许第三方懒加载暗中下载。标签和阈值沿已存在的 versioned profiles，有效 profile 入 Result；模型/profile 可在受控实现替换中更新，不冻结一种算法为产品边界。

沿用 profile 包括保留超出分数范围的有效阈值，例如 normal 的99及温和阈值33。[Read 属性义务](../precheck-read/precheck-attributes.md#敏感性分数与阈值)允许并解释该表达；实现不得删值、截断阈值或临时改判定来通过 schema。

该表不是新的能力注册系统。配置被解析为本次 Run 的有效快照，enabled、本地性及有效 profile 可在安装/Run 诊断中读到；凭据不进入公开返回。修改会使真实依赖失效，已经封存的 Result 不修改。

Read 只消费已准备材料。本期不新增通用“任意高清/任意视频帧”获取 Tool；需要超出已有准备的内容时，Plan 可以使用已存在的合法能力，或明确请求后继 PreCheck。普通候选不足不自动要求重跑整个阶段。

### 准备有效性、执行成本与发布证据

progress 的终结工作数、范围对账完整、准备义务满足、plan_ready 和发布的运行品质分别由各自证据支持；不能用终结失败或重复帧凑足有效准备。正常坏源按项保留；采样器制造的不可解码目标须作为实现问题修复。有限材料是否足够支持具体组织判断，仍由 Agent 和用户判断。

每项 Work 保留独立身份、依赖、输出和失败责任；执行可以共享批次、进程、解码上下文及数据库连接，不要求逐项启动或提交。有效配置和重要资源限制进入已有 Run 诊断；实际可执行的并发/线程上限与内存估算、观察值分别说明。仅改变不影响结果含义的调度分组或并发，不使有效成果失效；真实语义或有效性依赖变化只重做受影响工作，保留无关成功结果和旧 Result。

耗时不作为跨设备固定 API 常量。相关发布须在声明的输入、输出规格、版本、资源与缓存条件下，同时验证相同有效工作量、首次准备、后继复用、局部变化和实际安装入口。门槛与实测归入对应 OpenSpec 验收和既有评测/迁移台账，不能用少输出的总时长证明吞吐改善；真实 fixture 之外的未认证范围明确保留。

### Geo 服务前提与恢复

Geo 的地点级终结失败与适用服务不可达遵循 [Geo D6](../geo-query/index.md#d6-有限执行目标地域和公开恢复)。后者保留已取得证据并 blocked，不发布本次 Result。status 说明缺失条件；用户处理网络或配置后通过既有 resume 进入缺失组件恢复确认，明确 proceed 才能产生新效果。恢复披露原累计请求/费用和上限、保留组件及实际网络接收边界；旧确认不覆盖新的 Proxy。已持久化响应的本地投影重放不产生新地图请求，未知历史费用保持未知。

恢复调用顺序：blocked 时发送 `resume` 且省略 decision，准备恢复确认；进入 paused 并取得完整 confirmation 后，才发送 `resume + decision=proceed` 触发可信确认。前一步不授予新的外部效果，不能把尚无披露时的 proceed 当作授权。
