## Why

PreCheck 的运行、结果读取与 MCP 包装各自增长字段，消费者又重复解释状态，造成接口冗余及跨层漂移。
本次 Geo missing+value 发布故障说明：合法的无地点业务结果被错误地升级成整批发布失败。

## What Changes

- **BREAKING**：仅 PreCheck 两个 Tool 的 MCP 参数展平，统一 `action`，保留一次 `dataset_ref`，无 `request` 包装、无 `operation` 别名、不拆九个 Tool。
- **BREAKING**：精简 Run / Read 返回，统一单层 progress、原因、局部问题、控制语义、Result 摘要和分页；保留对账、审计、确认和精确成员校验。
- 将 Geo 结果规范化为现有 Observation 模型的地址与附近地点两种观测；fresh、复用及可证明的旧记录走同一规范化路径。
- 缺坐标、no_result、有限重试后的业务失败可局部发布；即使全体无地点也不能仅因此阻塞 Plan。
- 有限重试归共享 Geo Tool，预先计入授权额度；预期业务失败与程序错误、效果不确定保持区别。
- 同步生产组合、Source Set 消费者、Plan/Apply 读取桥、打包规范和 Skills，以离线纵向测试证明没有功能退化。

## Capabilities

### New Capabilities

- `precheck-result-read`：为已存在的 review / expand / resolve / geo_summary 建立完整 OpenSpec 规范归属；没有新运行能力或 Tool。

### Modified Capabilities

- `tool-host`：方案 A 的 PreCheck 分派、严格 schema、可信确认和错误边界。
- `precheck-run-orchestration`：简化状态/控制/进度，按需对账诊断与完成交接。
- `precheck-confirmed-geocoding`：压缩、确认、规范化、重用与无地点非阻塞。
- `geo-capability`：单一有界重试所有者及授权预算。
- `plan-working-state`：通过受信任 Read 边界校验入场，不依赖 integrity 常量或 Geo 获取细节。
- `apply-stage-runtime`：同步精确 Source Set 消费的操作和分页校验，保留全部文件安全门槛。
- `precheck-agent-workflow`：使用精简接口、正确解读无地点与终态。

## Impact

- `runtime/mcp_host.py`、`host.py`、`composition.py`、CLI Tool 调用入口。
- `precheck/run.py`、状态与对账 store、orchestration、Geo producer、Result assembly/projection/read/seal。
- `capabilities/geo`、`geo.py` 的可重试分类和请求预算；不改变 Provider 选择或媒体压缩算法。
- `source_sets.py`、Plan/Apply 中所有 PreCheck Read 消费路径，所有正式与打包 schemas、Skill 快照。
- 沿用既有非生产零 API 兼容政策；不删除用户数据，不要求重跑旧任务，不发布新安装包。
- 不含 EXIF (0,0) 判定、视频编解码修复、MediaSense Apply 文件效果或 AI Album 移植比较。
