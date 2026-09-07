## Context

用户已确认两条原则：每字段/实体有独立责任；已有能力若退回必须给出理由及等价保障。
已确认进度单层化、九 command 覆盖、无地点不阻塞 Plan，并选择 MCP 方案 A。
本包将约一千行讨论稿中的示意收口为可实施的契约；不实施生产代码。

## Goals / Non-Goals

Goals：两个 Tool、九 action，语义和 JSON 形状唯一；长任务可恢复、结果可质疑、精确成员可验证；
正常业务失败局部化；Apply Agent 不再承担产品设计。

Non-Goals：新的 CLI 子命令树、改变其他 Tool 的包装、新注册表/服务、生产数据迁移、安装升级、
重跑故障 Run、(0,0) 特殊过滤、视频修复。命令示意通过现有 CLI 的 Tool 入口调用，不为其新增九个命令实现。

## Decisions

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
代码共享校验，不给 UI/CLI 再维护另一套字段。MCP 成功用 structuredContent，业务/host error
用相同 error 对象且 isError=true；查询到 failed Run 则 isError=false。

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

### D4. Read：取齐与取对

四 action 都只读 immutable Result。input/output 的具体字段以 contracts 为准；原有 include 全保留。
review 默认提供 result/accounting/cards/page，不默认输出效果细节；include=execution_boundary 获取审计。
审计include返回累计费用摘要及attempts/page，每条attempt保留Provider/operation/结果、坐标、费用、
原观察时间和Result内source_set关联。historical/current按该Result的Run边界分类，同历史事件只计一次。
明细按原durable attempt顺序分页，输入execution_page（50默认/200最大）只控制审计；普通page只管cards，
两游标均绑定相同Result且彼此不能混用。该额外selector防止卡片分页与费用明细分页共用一个cursor。
公开累计数量若老资料无法证明为null，仍返回已知明细；不能从可见明细样本外推全量费用。
运行中的diagnostics只显示效果累计与分类；需要逐来源审计时，published Result使用此Read通路，
未封存Run保留既有journal证据但不把私有存储交给Agent。
每张卡 source_count 是 direct represents 去重 Source Items；关系记录保留一个源项一个 membership，
不允许重复边改变成员数。全局 memberships/unique count 保留跨卡重叠。空角色、省零状态是已知零；
未知计数不能省略成零。时间/类型/角色以外的事实不进入固定摘要，其原貌仍由 expand 完整读取。
保留 available_expansions 的 include+estimated_items，不删有用的读取成本估计；无法估算用 null。

page={total,next_cursor,stop_reason?}，next_cursor 必须存在，null 表示完整终页；total 精确。
按需 stop_reason=byte_limit。最大输出524288字节，完整项之间分页；单项超限明确错误。
review默认25/max100；expand成员/geo50/max200；resolve250/max1000。
页顺序：review入口既定顺序、成员源引用升序、geo纬度经度datum；绑定 digest/action/selector/include/limit/order。
page.returned、complete、重复 ordering/total 删除后，消费者仍验证实际数组长度、递增未重复游标、
非末页有推进、最终全量 count 与 membership identity。page cursor 不构成一个新的读取会话实体。

source_set 保留原表达式 explicit、precheck_relation(accounts_for/represents/outbound)、union、difference、
geo_coordinate(gpx_over_gps_exact_normalized_v1)。source_set_identity=SHA256(canonical selection)；
membership_identity=SHA256(canonical {result_ref,source_set,members})，members为排序去重引用。
不改变 Frozen Plan 的 source_set 表达式。两种 digest 都有当前消费者校验用途，保留。
prepared_targets 保留 target:{kind,ref} 的 Evidence/Source Item 两种目标；不能只剩 evidence_ref。
原 source_content_verification 格式与强弱核验含义保持，Apply 仍重新验证源内容。

### D5. Geo Observation 的唯一权威形状

每个 in-scope Source Item 均可通过 expand observations 得到 `address_candidate` 与
`nearby_place_candidates` 两个标准 Observation；使用现有 Result.observations，不新增模型、
注册表或 location/overall_status 包装。地址 value 保留 formatted_address/components；
nearby value 为非空候选列表，候选的 name/address/coordinate/category/distance 等可用证据保留。
当前name/address分类等候选字段随既有GeoCandidate.value原样保留，公开schema对已知结构类型检查，
扩展候选字段只作为数据，不改变通用Observation状态含义。近邻候选附provider_ref应移入可追溯审计，
普通Plan返回去除provider_ref而不去掉候选主体。每个Source Item每种组件最多一个权威Observation，
冲突来源通过qualifications/basis显式表示，不能多条同名观测让消费者任选。
查询坐标仍是独立 gps/gpx 观测；获取时代表坐标与源最终坐标不同时，在 basis 中保留投影依据，
不得把代表坐标强写成媒体 GPS。具体坐标 basis、所用 Profile 和 observation time 可追溯，
provider/request/cache/Work 的明细通过执行审计保留，不成为普通 Plan 的必填语义。

| 组件结果 | Observation | value |
| --- | --- | --- |
| success | available | 必须非空候选 |
| no_result | missing | 禁止；basis 说明已查询无候选 |
| failed（有限尝试终结） | failed | 禁止；basis/qualification 说明原因 |
| not_requested（策略关闭/没有调用） | not_checked | 禁止；basis 区分未启用、历史未记录等 |
| 没有可用坐标 | not_applicable | 禁止；basis 指向坐标缺失 |
| indeterminate | failed + geo_effect_indeterminate qualification | 禁止；Run 不因此获得普通完成资格 |

缺坐标/no_result/failed/按策略未请求地点均不单独阻塞 Plan；所有项无地点亦如此。
真正选定的获取尚在进行、确认尚未解决，不可当 completed；schema矛盾和丢成员失败仍阻止发布。
效果 indeterminate 继续遵守 Geo journal：停止新外部效果，不自动重试，不把它降格成普通 no_result。
Result readiness 仅保留既有非Geo前提（有可用入口、源条目处理闭合等）；缺 Geo 记录时按明确
not_checked+historical_geo_unrecorded 归一化，不能推断曾尝试；来源证据自相矛盾则 result_untrusted。

Geo 诊断改成每坐标 components:{address,nearby_places}，每项返回 outcome 的计数字典
（success/no_result/failed/not_requested/not_applicable/indeterminate），计数单位固定 Source Item，
因此可表示同坐标多份历史结果冲突而不选一个伪总体状态；计数各等于 member_count。
acquisition_status 对有最终坐标的两组件均有终结记录则 complete，仍未请求则 incomplete，
没有坐标则 not_applicable；这不是 plan_ready 判据。candidate_evidence_refs 只含真实候选，
无结果来源通过 source_set→expand 追溯，不能把空候选伪造 Evidence。

### D6. 有限重试归 Tool，费用预先受限

共享 GeoCapability 接受内部不可变 RetryPolicy（配置值，不是新公开字段/Tool）。
本轮实现策略：每坐标、每候选 Provider 最多3次 execute，瞬态失败后等待1秒、3秒；
每坐标单调时钟120秒墙钟预算，每个实际 HTTP timeout 不超过剩余时间及原 Provider timeout。
成功组件保留，no_result 不在同 Provider 重试；只有 transient(限流/服务5xx/安全可重试网络错误)重试。
permanent 不重试；indeterminate 立即停止。回退按现有已授权 Provider 路由，不新增 Provider。
“安全可重试网络错误”只包括证明请求未发送的连接失败；发送后的timeout/未知完成仍按现有
Geo契约归indeterminate，不能把计费未知当作可盲重试失败。HTTP已响应的429/5xx可重试，
其请求数照实记录；认证/参数等永久错误立即终结。GeoProvider.execute增加内部deadline及cancelled
参数，所有真实adapter与fake遵守同一端口；每个HTTP admission前重新校验剩余deadline。
扩展操作一次可有两次 HTTP，全部受 Provider 声明 ceiling；重试会重复读已成功组件时照实计费，
不丢失已得候选。Sleep 可取消，deadline或额度耗尽时终结带具体 qualification 的失败。

预检请求 ceiling = coordinates × sum(provider.execute ceiling × max_attempts)，已知 billable
ceiling同样上界；配置策略描述加入有效请求 fingerprint 与 journal admission identity并随披露返回。
纯 request 数据保持现有 Geo公共输入，Host/Tool 以 request+effective profile 的 canonical值计算最终
fingerprint，不让客户端自行猜摘要。变更策略使旧授权不匹配；较小的既有授权不能被扩大，
不足以再发一次时直接终结。效果最终失败后的相同 request_id 重放只读 journal，不重做外部调用。
失败证明与安全重试资格由adapter返回的attempt/error类别决定；缺分类默认不可重试，不能靠自由message猜测。
PreCheck 外层 Work 不重复重试已经终结的 Geo失败，只有未发送且可安全恢复的工作走本地恢复。

### D7. 旧证据与零 API 兼容

使用现有零公开 API 兼容政策：不保留旧 request/operation/响应字段路由。新 schema 一次替换，
同包更新所有 runtime 与测试消费者。旧不可变 Result 字节、摘要、引用不改，mutable store 不批量清理。
在 Result Read 和 Geo reuse 的现有 stage adapter 中调用同一个纯规范化函数，读取旧证据时
只映射能证明的含义，不为旧版本增加服务/版本路由。新 producer identity 使用
`builtin-geo-component-observations-v4`，新 Work 与旧身份区分，旧数据不被覆盖。

旧 v3 output.result.component_outcomes 在枚举/候选一致且来自真实逐组件Tool返回时足以规范化；
若producer.reused_from指向legacy升级器，则必须追溯原始证据，不能把升级器猜出的两项no_result
当作独立证明。该value即使曾误放missing candidate中，也只在工作输出归一化时提取，
绝不放行非法公开Observation。
更旧聚合结果：从 attempts/provider协议及已有记录能分别证明两个组件时转换；仅有 requests数量
或 aggregate missing 不足以证明两操作已执行。缺证据组件写 not_checked+basis（historical_geo_unrecorded），
不假造 no_result，不自动网络补查、不循环迁移。保留原作者、观察时间和历史授权用于审计，
不是当前 Run 的新授权。旧 published Result 本身不合法/摘要损坏则拒绝读取，不能偷偷修数据。

ordinary Read 对原本合法旧 Result 以新投影返回，derived readiness使用新非阻塞规则；
content digest始终验证旧封存字节，投影不是替换内容。有 active Run 的现场升级/恢复是另一项运维任务，
本包只在合成旧数据上证明规范化，不在本机数据库执行。

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
contracts中的responseSchemas[action]校验：控制的简单state不能让status省掉progress、reason或Result。
responseSchemas是以outputSchema为根解析的schema片段，复用同一份$defs；不复制字段定义，
编译时组合outputSchema.$defs与片段即可，verify_packet.py给出实际例子。
新Geo观测按name分支约束value形状，缺失/失败basis必须存在，观察完整度仍由语义校验负责。
公开error.code集合允许扩展但不得重用语义；所有新分支需明确code，不解析message。
合同内复用的access、basis、provenance等开放数据字段保留现有扩展语义，不把它们误当成任意行为指令。
该设计不把json_value的开放性用于掩盖尚未定义的必需字段。

## Risks / Trade-offs

- [两组 schemas 与旧消费者漂移] → 先原位替换正式规范/资源，真实MCP及Plan→SourceSet→Apply准备纵向测试；不只运行新示例。
- [精简隐藏观察范围或成本] → 保留include与全量通路，未知显式null，issues限长且可分页，费用分历史与本次。
- [旧数据解读过度] → 不证明就not_checked，非法封存Result拒绝；新Work身份隔离，无现场写入。
- [诊断频繁变化导致分页失效] → 优先最新状态，精确分类在稳定快照或终态读；无隐式快照生命周期。
- [重试放大费用] → upfront ceiling × max_attempts，效果边界每次发请求前执行；HTTP失败也计已发生请求。

## Migration Plan

Apply 原位更新 active docs/spec 与打包副本，将本包 schema promoted 到原有Tool文件位置。
删除的是公开冗余字段与旧别名，不删除检查、原始证据、Fixture或数据库。同步 foundation、Skill、
Plan入口、SourceSet消费者、Geo profile和错误映射。现有其他changes已落地内容作为当前代码基线，
不修改/归档它们；本包delta覆盖与本次冲突的旧语义，不能回滚到旧representative-only Geo。
回滚为仅回滚本次仓库实现补丁；没有安装/生产数据迁移。无版本号发布、无自动archive。

## Open Questions

无阻碍 Apply 的产品或字段决策。实现若发现实际机制不能满足这里的保证，必须报告证据，
不得自行放宽授权、完整性或制造新生命周期。用户若改变产品选择则显式修订本包。
