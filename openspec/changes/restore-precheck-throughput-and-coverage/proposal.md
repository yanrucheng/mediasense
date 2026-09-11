## Status and authority

**实施及本次验收已完成。** 用户于2026-09-11明确授权Agent自行判断方案与验收并继续开发。Agent据实测和剖析收敛技术选择，先固定[实施验收](acceptance.md)与[tasks](tasks.md)，再修改产品代码；这些技术决定不冒称用户逐项审阅。完成证据见[修复报告](../../../eval/sessions/260911-2128-precheck-throughput-recovery/report.md)，认证到源码和隔离wheel/Host，未切换全局安装。

本 change 记录既有能力的变更及验收，不是当前公开规范。`docs/spec/contract/` 仍是唯一当前合约权威；本次收敛的语义已补入 Run/Read。此前 `scale-precheck-execution` 的已完成记录保留，本次单独记录新实测引出的修复与验收责任。

## Why

2026-09-11 本机对照显示，当前同字段 EXIF 提取耗时为旧版的7.92倍，同工作量抽帧为1.59倍；默认帧准备虽更短，却只交付370帧并发生285次可定位的采样失败。现有 Foundation 已要求经济性、吞吐和复用，但既有验收主要闭合机制/装配，尚未把有效准备结果、资源边界、全路径成本与发布判断结合起来。

证据：[本机性能对照](../../../eval/sessions/260911-1841-hk-preprocess-performance/report.md)、[迁移台账](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。这些是特定本机/代理素材上的事实，不是所有原始视频和机器的结论。

## What Changes

- 明确 PreCheck 的目标：在来源安全、可恢复和资源约束内，经济地完成约定的证据准备，使 Agent/用户能继续解释、质疑和组织素材。局部调用计数或缓存命中不替代这个结果。
- 保留现有 Source Item、Evidence、关系、Observation、Work、Artifact、Run、Result 的权威；使独立归属和失败粒度与批处理、并发、解码/事务共享的执行粒度可以分开演进。
- 在 Run/Read 既有承诺中区分准备需求、实际取得的材料、范围对账、缺口及限制。位置意图不得冒充实际帧观测；一般来源缺失、实现导致的采样错误和未知异常分别处理。
- 为已批准的工作负载和资源条件建立联合验收：字段/有效帧与覆盖要求、首次/复用成本、来源安全、恢复和安装入口均有通过条件。秒数与比较阈值放在本次计划和评测配置，不变成跨机器永久 API 常量。
- 先补充非 ExifTool 时间的剖析，再选择批间并发、协调/存储批处理和视频解码复用方法。保留逐项语义、局部失效与可验证提交，不用降低采样或删除摄影字段抵销成本。

交换值沿用 `sample_time_seconds` 的请求位置含义，新增可选 `decoded_time_seconds` 表达实际 PTS；联系表同步引用，历史缺值保持未知。没有新增公开 Tool、输入路由或状态；已封存 Result 不修改。

## Capabilities

### New Capabilities

无。不增加 Tool、Skill、服务、批次实体、质量注册表或平行结果存储。

### Modified Capabilities

- `precheck-run-orchestration`：把按约准备、资源约束内的高效执行、复用以及有条件的运行品质验收连接起来；保留既有状态和控制语义。
- `precheck-result-read`：使已取得的视频材料、可证明位置、准备范围和局限能经现有对象/属性/关系交付，不把结构可用等同于语义充分。

## Impact

- 公开规范归属：`docs/spec/contract/precheck-run/`、`docs/spec/contract/precheck-read/`；交换值只在现有 schema 定义一次，打包副本同步。
- 实现范围：PreCheck metadata、video、资源调度、Work/来源证明和 Result 投影中的已证实热点；具体原语与边界见 design 和 tasks。
- 评测复用现有 session 配方；迁移判断回填现有台账；发布需安装入口验证。不会通过修改历史数据或期望值让实现过关。
- 厂商规则维护、模型选择、Plan 命名与 Apply 行为不在此 change 内。并行 metadata 语义变更若进入发布，必须重新固定有效 profile 和整合验收范围。

## Approval sequence

1. 已取得继续开发及技术判断授权，沿用前述目的、权威边界和可读案例。
2. 256项metadata剖析已定位1,024次逐项租约续期、连接/查询/事务开销；PyAV原型在稀疏片尾及三个4K/8K原样短片上取得真实PTS。由此固定具体方法和实施前验收门槛。
3. 按tasks推进合约、实现、测试和隔离安装验收，结果回填既有台账。未授权的外部服务和当前业务Dataset不参与本次开发验证。
