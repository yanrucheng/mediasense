---
id: "spec-260826-1546-precheck-read"
title: "MediaSense PreCheck Read Tool Contract"
type: spec
status: active
created: 2026-08-26
updated: 2026-09-07
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
superseded-by: ""
tags: ["mediasense", "precheck", "tool", "result", "review"]
---

# MediaSense PreCheck Read Tool Contract

`mediasense.precheck.read` 只读一份确切、受信任的不可变 Result。
[Tool Schema](precheck-read.tool.json) 是唯一交换值规范；
[合成示例](hong-kong.mock.json)展示 review、expand、resolve 和 geo_summary。
四操作均显式携带 action、dataset_ref、result_ref，不接受 request 包装或 operation 别名。
本合约采用零公开 API 兼容政策，不增加 Tool、版本路由或读取会话。

Read 不获取新证据，不作组织语义决定，不修改 Run、Plan 或源媒体。
验证封存字节与引用后才作只读投影；非法 Result 返回 result_untrusted 或 result_inconsistent。
成功读取失败 Observation 是普通数据，不是调用失败。

### D4. Read：取齐与取对

四 action 都只读 immutable Result。input/output 的具体字段以 [Tool Schema](precheck-read.tool.json) 为准；原有 include 全保留。
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


### D9. 规范校验与交换值边界

Tool outputSchema 是所有action返回的并集，用于MCP发现。运行时还必须按输入action选择
Tool Schema 中的responseSchemas[action]校验：控制的简单state不能让status省掉progress、reason或Result。
responseSchemas是以outputSchema为根解析的schema片段，复用同一份$defs；不复制字段定义，
编译时组合outputSchema.$defs与片段即可，verify_packet.py给出实际例子。
新Geo观测按name分支约束value形状，缺失/失败basis必须存在，观察完整度仍由语义校验负责。
公开error.code集合允许扩展但不得重用语义；所有新分支需明确code，不解析message。
合同内复用的access、basis、provenance等开放数据字段保留现有扩展语义，不把它们误当成任意行为指令。
该设计不把json_value的开放性用于掩盖尚未定义的必需字段。


## 消费者责任

Plan 通过受信任 Read 接受 complete 或有界 partial、且 readiness=plan_ready 的 Result，
不查找 integrity 常量或重建 Geo 获取状态。Apply 在准备阶段仍必须验证 Source Set 的
完整成员身份、冻结计划、源定位、源内容、冲突和文件系统安全条件。
消除返回冗余不取消任何这些检查。

分页游标只在同一 Result、action、选择器、include、排序与 limit 下有效。
独立的 execution_page 不能用作 cards 的 page。非末页必须有实际推进，终页必须对齐总数，
精确成员摘要必须以完整排序去重成员重算。禁止从一个样本页推断全量成员或历史费用。

## 错误

使用单一 error 对象的 code/message；相关代码包括 invalid_request、dataset_not_open、
result_not_found、result_unavailable、result_untrusted、result_inconsistent、
reference_not_in_dataset、reference_not_in_result、invalid_cursor、unsupported_include、
invalid_source_set 和 response_item_too_large。
不存在与其他 Dataset 中的子引用使用同一不可见结果，不能扫描其他 Dataset 来区分。
