## 1. 契约与生产入口

- [x] 1.1 阅读本包，原位更新 docs/spec 的 PreCheck Run/Read schemas 为 contracts 中的形状；同步机读mock，执行 verify_packet.py 与当前合约测试。
- [x] 1.2 修改两个 PreCheck MCP输入为扁平 action/dataset_ref；保留其他Tool包装，验证Host路由与请求Dataset一致，移除旧operation/request公开别名。
- [x] 1.3 同步 RuntimeHost、DatasetRuntime、CLI入口和所有precheck.read进程内callable；MCP错误isError与已失败Run正常返回分别验证。

## 2. Run 状态、控制与诊断

- [x] 2.1 用现有Run/Work事实实现单层progress、null未知值、terminal计数、phase/unit口径和progress_scope_changed；保留活性诊断与无隐式恢复。
- [x] 2.2 实现status按需accounting/diagnostics、5类默认issues截断标记及digest绑定诊断分页，验证变更后拒绝旧cursor。
- [x] 2.3 start仅返回run_ref并保持幂等/唯一活跃Run；pause/resume/cancel返回真实观察state，补充控制竞态与worker启动失败测试。
- [x] 2.4 完成结果摘要去integrity常量，保留读取/发布校验与qualifications；确认所有failure/blocked分支有真实机制。

## 3. 确认与效果边界

- [x] 3.1 实现scope entries视图、既有统计桶和scope分页，保留指纹校验、刷新后重新确认及selection provenance。
- [x] 3.2 实现完整披露内联/坐标分页、summary/content_identity和Host可信elicitation绑定；超限客户端无法完整呈现时零效果拒绝。
- [x] 3.3 按D6实现共享Geo内部RetryPolicy、瞬态分类、可取消退避/deadline、指纹与journal绑定、预先放大请求/费用上限；移除PreCheck终结失败外层重复重试。
- [x] 3.4 通过fake Provider/clock验证瞬态成功、永久失败、额度不足、超时、取消、indeterminate、重放及每次HTTP计费上界。

## 4. Geo 与 Result 发布

- [x] 4.1 实现唯一纯Geo规范化函数、v4 producer身份、address_candidate/nearby_place_candidates标准Observations；保留来源、组件差异和代表坐标basis。
- [x] 4.2 修改Result assembly/projection/seal/read对组件的使用；移除missing.value.component_outcomes依赖，保留通用value不变量。
- [x] 4.3 实现无坐标/no_result/终结failed/策略未请求的非阻塞readiness，区分未完成确认/执行和effect indeterminate；不动(0,0)类型策略。
- [x] 4.4 在合成旧Work/合法旧Result上验证有证据转换、无证据not_checked、原字节不改、历史费用不算新请求；非法sealed Result拒绝读取。

## 5. Read 与全部消费者

- [x] 5.1 实现review的result/accounting/cards和成本include，保留scope/condition、重叠覆盖、角色/缺失态/限定、可展开成本。
- [x] 5.2 实现compact expand及全部include、两种prepared_target、16-ref原子校验和单Evidence成员分页。
- [x] 5.3 实现统一page并修改source_sets.py、Plan验证/预览、Apply准备等所有消费者；保留两种identity、排序去重、全量最终核验和source_content_verification。
- [x] 5.4 实现geo_summary两组件outcome计数、无位置与混合历史结果、exact source_set；禁止再把available映射成完整业务成功。

## 6. 文档、打包与收敛

- [x] 6.1 同步foundation、相关active规格与PreCheck/Plan Skills的无地点非阻塞规则；原位保留唯一权威源，讨论稿指向落地规范。
- [x] 6.2 同步_resources/contracts、Skill参考快照、packaging与CLI说明；未改其他Tool公共接口，不新增版本路由/注册表。
- [x] 6.3 把contracts/examples.json转为真实组件可重算的合成回归向量，逐条证明rejection、分页、授权、无地点及legacy seal。
- [x] 6.4 运行受影响合约/Run/Geo/SourceSet/Plan/Apply/Host测试及默认非live pytest套件和ruff，保留失败证据，不改预期掩盖退化。
- [x] 6.5 用生产组合和真实stdio MCP完成九action与PreCheck→Plan→Apply准备的零外部效果纵向验证；构建临时wheel做隔离导入/发现测试，不升级本机安装。
- [x] 6.6 完成字段删减/功能保留检查、严格OpenSpec校验与git diff --check，报告所有测试和改动；不自动archive、commit或运行用户Dataset。

## 7. 2026-09-08 复核修正

- [x] 7.1 修正 GPS/GPX 冲突的 conflict 枚举，验证真实封存 Result 的 geo_summary、GPX 优先和精确成员选择。
- [x] 7.2 保留崩溃恢复的未知费用、请求数与外发类别，验证 journal 重放、Work 持久化、诊断及读取；已知未发送仍为零。
- [x] 7.3 修正 MCP resume + proceed 对不存在 Run 的错误语义，验证真实 stdio 与直接调用一致且保留结构化 run_not_found。
- [x] 7.4 重跑针对性测试、默认离线套件、Ruff、包内检查、生产组合及隔离 wheel smoke，更新复验依据。
