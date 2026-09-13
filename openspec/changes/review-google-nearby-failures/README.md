# Google 附近地点请求失败与 PreCheck 交付状态

## 交接状态

记录日期：2026-09-13。阶段：**已按后续授权完成源码修复与隔离安装验证；未升级日常环境、未重采真实地图、未改写业务 Result**。

创建时用户要求只整理问题；本次已另行授权在现有设计与合约内直接修复。下方“已确认事实”保留历史审计含义，最终实现与验证见本页交付记录。没有修改公开合约。

## 已确认事实

1. 本次冻结的 Geo 请求为 `max_places=30`。168 个逻辑查询点包含 164 个 Google 点和 4 个高德点。
2. Google 适配器的构造参数 `max_pois` 允许 1—20，默认 10。组合 `resolve_place` 路径会收窄数量；共享 Geo 服务因该适配器声明独立组件能力，将请求拆为 `reverse_geocode` 和 `nearby_places` 后，独立附近地点路径未执行同样的收窄。
3. 无网络捕获式复现中，同样以 30 请求，默认适配器的组合入口构造 `maxResultCount=10`，独立附近地点入口构造 `maxResultCount=30`。
4. 实际 journal 记录：Google 地址查询 163 次成功、1 次无结果；Google 附近地点 164 次全部失败，错误均为 `http_permanent / provider HTTP 400`；高德 4 次组合查询成功。
5. HTTP 400 在该实现中归为 `http_permanent`。本次继续处理后续坐标，Geo 最终为 `partial`，PreCheck 为 `completed` 并发布 `plan_ready`。
6. 实际服务请求为 332，未发生额外重试；996 是授权上限，费用未知。9 月 8 日同一来源为 225 个逻辑点、454 次服务请求，本次并非数量增加。

## 影响与证据边界

香港范围的附近地点候选没有按这次请求取得，影响后续餐厅调查；成功的地址组件与失败的附近地点组件需分别理解。请求数量下降不能证明获取质量达标。

已观察到参数越界路径和全批同类 HTTP 400。原始响应体没有保留，不能排除同时存在其他参数问题，也不能从 `http_permanent` 推出这些都是地点特定、不可恢复的失败。将失败观测保存在 succeeded Work 中，不单独证明该 Work 状态有误；问题涉及实际组件结果、失败分类和后续发布行为。

## 直接复核入口

- 指标：`geo`、`geo_selection`、`google_payload_probe`。
- [适配器与 HTTP 分类](../../../src/mediasense/geo.py)：`GoogleMapsReverseGeocoder.execute`、`_nearby`、`UrllibJsonTransport._open`。
- [共享 Geo 执行](../../../src/mediasense/capabilities/geo/service.py)：独立组件拆分、传递参数和停止条件。
- [PreCheck Geo 采集](../../../src/mediasense/precheck/geocode.py)：请求及结果投影。
- [Geo 当前合约](../../../docs/spec/contract/geo-query/index.md)：组件状态、效果与 D6 失败边界。
- 相关既有包：[Geo 采集整合](../consolidate-geo-acquisition-in-precheck/README.md)。该包已有的结论不等于本次运行通过。

## 创建时的复核问题

- 已观察失败中，请求构造、服务前提与地点级失败各自能由什么证据区分？
- 公开请求上限与 Provider 有效能力在各调用路径中应如何保持一致含义？
- 本次已发布 Result 和已取得的成功组件应如何处理，哪些后续效果需要另行界定？
- 哪些验收证据足以证明真实共享服务调用路径已闭合，而不只证明适配器的一个入口可用？

## 共用证据与适用范围

- [运行验收报告](../../../eval/sessions/260912-2333-hk-run-acceptance/report.md)
- [精简指标](../../../eval/sessions/260912-2333-hk-run-acceptance/metrics/combined.json)
- [精确对象与本机路径](../../../eval/sessions/260912-2333-hk-run-acceptance/config.json)
- [只读复核脚本](../../../eval/sessions/260912-2333-hk-run-acceptance/run.py)

被审计运行使用 MediaSense 0.10.2，源为 `ai-album-hk-representative-v1/test-260831`。审计代码基点为 `615c3359941927515f0c0a8738a3f08122bcad46`；共享工作区和原 Plan 会话随后继续变化，不能把当前磁盘状态当作当时状态。

PreCheck Run 为 `precheck-run:8b5ff902fda54e6292b14d4fa5f0de42`，Result 为 `precheck-result:cbd18bc79b56b2b9d257529f878b7151c399b4815acebe74d1ba328e80a7ae57`。初版 Plan 轨迹固定到配置中声明的原会话前 859 行；后续更正按报告中的时间与行号分别引用。原始媒体、数据库、完整轨迹和 HTML 快照在本机，不复制到本包。

公开语义以 [当前合约](../../../docs/spec/contract/index.md) 为准；本包不成为另一份规范，也不改变既有验收或迁移决定。

## 修复与验证交付（2026-09-13）

### 事实复核与原因

当前 checkout 的独立 `nearby_places` 入口仍直接传入 30，组合入口才收窄为 10。修复前，新增的生产装配测试真实执行 `_geo_tool → GeoQueryTool → GeoCapability → GoogleMapsReverseGeocoder → UrllibJsonTransport`，只替换最外层 opener：捕获到 30；模拟 HTTP 400 服务禁用得到 partial；请求参数拒绝和无法分类的 400 均未停止批次。这五个针对性断言修复前均失败。

这证明当前代码缺陷仍存在，不证明历史 164 次 400 全由数量参数引起。历史响应体缺失的证据边界不变。

### 最终改动及必要性

- Google adapter 的独立组件与最终请求构造边界共同执行有效上界；生产默认实际请求为最多 10 个、500 米，更小的调用者上限原样保留。成功和失败组件均可保留已知收窄限定，不声称穷尽搜索。
- transport 有界读取错误响应，仅交给 adapter 在内存中分类。adapter 从结构化 status / ErrorInfo 的已知值区分参数错误、API/账单配置、鉴权、配额等；原始 message、metadata、URL 和 key 不写入 journal。保留实际 HTTP 状态及脱敏分类，不解析自然语言消息猜原因。
- `INVALID_ARGUMENT` / reverse `INVALID_REQUEST` 是请求实现缺陷；未分类 HTTP 拒绝仍待诊断。Tool 先保存实际 attempt，再立即抛出执行异常，既不继续发送，也不包装成普通 blocked 或地点终局失败。checkpoint 重放及 PreCheck 对旧 `http_permanent` Work 的复用不会把未解决的拒绝变成新 Result 的可发布缺地点证据。
- 已证明的服务前提缺失走现有 blocked；停止同地点的未发送组件及后续地点，保留成功组件、not_requested 和累计费用。已授权且适用的替代 Provider 仍有自己的有限重试周期；明确地点级失败仍可局部终结。
- 复用原 model、adapter、service、journal 和 Work。新增的内部 HTTP 异常只承载有界响应分类；共享错误检查防止执行、重放和 PreCheck 复用各自解释同一拒绝。没有新 Tool、服务或持久实体。执行指纹的内部语义标记更新为 `component-recovery-v3`；旧已完成请求仍按现有合约精确重放，新执行不能套用旧确认。

### 验证证据

入口是 [生产路径回归](../../../tests/test_google_nearby_requests.py)、[PreCheck 投影回归](../../../tests/test_geocode.py) 和既有 Geo recovery/tool/process tests。关键实际结果：

| 情形 | 结果 |
| --- | --- |
| 三地点成功，公开上限 30 / 800 米 | 三次 GET + 三次 POST；POST 均为 10 / 500；实际请求 6，费用 unknown；重放零新增请求 |
| 地址成功后 nearby 参数错误或未分类 400 | 仅两次请求；地址与失败 attempt 均已落 journal；抛异常；本地重放仍不发布假 partial |
| 首组件服务禁用 / 地址后 nearby 服务禁用 | 分别 1 / 2 次请求后 blocked；后续组件/地点未发送 |
| 处理服务前提后显式恢复 | 只补缺失组件；累计请求 7，费用仍 unknown，原地址及 observed_at 不变 |
| 真正地点级失败 / 适用替代服务暂态失败 | 前者继续后续地点；后者保留自己的有限重试，不继承上一 Provider 的停止标志 |

旧“配额耗尽仍 completed”测试与 Geo D6 的明确条款冲突，已改为结构化 `RESOURCE_EXHAUSTED` 并断言 blocked；这项调整由现行合约决定，未改合约或通过文本猜测制造期望。无结果、局部失败和跨 Provider 成功来源仍分别验证。

最终执行命令、数量与构建身份见 [verification.json](verification.json)。共同回归覆盖 Geo、GPX、压缩、有效性、资源与生产编排；隔离 wheel 另通过包文件一致性及 CLI/MCP smoke。wheel 来自 `615c3359941927515f0c0a8738a3f08122bcad46` 加本次修复的隔离导出，排除了同时进行的敏感性、Plan 与安装文档改动。其 0.10.2 版本字符串只是验证载体标识，确切字节以 SHA-256 为准，不表示已正式发布。

### 剩余限制与决策

源码与隔离安装路径已验证；没有真实地图成功认证，也未修改历史 332 次请求及未知费用。历史业务 Result 保持完整性，日常 Host/Skill 未升级。新执行若遇到未知拒绝仍需诊断，不会凭 HTTP 400 推断地点失败。历史失败的重采、已发布 Result 的后继交付和日常升级属于另行处理范围。本次工程修复没有需要用户重新决定的公开语义或产品取舍。

最终共同验收：源码 **158 passed**；隔离 wheel **158 passed**，并通过离线 CLI/MCP 分发 smoke。最终 wheel SHA-256：`55db47084afc8c75b3204d358ff0f771f7d8b2a337695efc15573139bdf4c55b`。
