# 视觉压缩未消费已有 GPX 坐标

## 交接状态

记录日期：2026-09-13。阶段：**代码修复已通过用户独立验收；重建的确切持久 wheel 又通过独立 Agent 回归及 CLI/MCP 复验。日常环境未升级、业务 Result 未改写；首轮全量压缩未重跑**。

独立复验结论与范围见[运行验收报告末尾的第 1—3 包再次独立验收](../../../eval/sessions/260912-2333-hk-run-acceptance/report.md)。该结论绑定新 wheel `9e813bda30fa4b7cc33517d582aefd7547f48e7836a8a78ed7a0f9df31df9f9f`，不扩大为日常安装、真实 Provider 成功或历史业务恢复。

本轮未修改此项实现。当前安装包证据见本页末尾的二次交付，首轮全量回放数据保留为历史记录。

创建时用户要求只整理问题；本次已另行授权在现有设计与合约内直接修复。历史审计事实保持原义，最终实现与验证记录如下；没有改变公开坐标语义或默认尺度。

## 已确认事实

1. GPX producer 的可用坐标 Observation 名称为 `gpx_coordinates`，metadata 中的内嵌坐标名称为 `gps_coordinates`。
2. 视觉压缩的 `_prepare_input` 对 metadata 和 GPX 调用同一个 `_gps_value`；被审计实现的该函数只查 `gps_coordinates`。
3. 本次 167 个压缩输入点均有 Embedding，其中 89 个已有内嵌坐标，另有 **55 个有 GPX 坐标但未被该消费者采用**。
4. 实际输出为 156 组，71 组标有 `limited_similarity_evidence`。
5. 在同一批已准备输入、同一向量和同一参数上，仅使对照计算读取实际 `gpx_coordinates` 后，仍是 **156 组，成员身份完全相同**；该限定变为 21 组。这个对照没有改写原 Result 或执行新模型。
6. Geo 采集路径读取的是 GPX 的实际 Observation 名称；本次取得 168 个地图查询点。视觉压缩缺口不等于 Geo 路径也没有采用这些坐标。

## 影响与证据边界

已准备的信息没有进入声明可使用该信息的压缩比较路径，实际采用的空间证据和限定受到影响。

对本次输入，不能声称该缺口造成了更多组或更多地图请求；已有局部对照恰好显示成员与组数不变。该对照也没有认证全部空间比较、场景正确性或其他数据集表现。0.311 是用户已确认的本次默认尺度，本包没有变更这一决定。

## 直接复核入口

- 指标：`compression.gpx_available_but_ignored_points`、`native_gps_points`、`correct_gpx_observation_groups`、`correct_gpx_changed_group_ids`、`correct_gpx_qualifications`。
- [GPX producer](../../../src/mediasense/precheck/gpx.py)：实际 Observation。
- [压缩 producer](../../../src/mediasense/precheck/_compression_producer.py)：`_prepare_input` 与 `_gps_value`。
- [Geo 输入读取](../../../src/mediasense/precheck/geocode.py)：与视觉压缩消费者的区别。
- [压缩概念模型](../../../docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)。
- 相关独立包：[GPX 匹配成本](../review-gpx-matching-cost/README.md)。

## 创建时的复核问题

- 当前消费者对内嵌坐标与 GPX 候选分别采用什么语义，是否与有效生产输出一致？
- 什么验证能证明已有空间信息被实际消费，而非仅存在字段或 producer？
- 限定、工作有效性和历史结果分别有哪些影响需要交代？

## 共用证据与适用范围

- [运行验收报告](../../../eval/sessions/260912-2333-hk-run-acceptance/report.md)
- [精简指标](../../../eval/sessions/260912-2333-hk-run-acceptance/metrics/combined.json)
- [精确对象与本机路径](../../../eval/sessions/260912-2333-hk-run-acceptance/config.json)
- [只读复核脚本](../../../eval/sessions/260912-2333-hk-run-acceptance/run.py)

被审计运行使用 MediaSense 0.10.2，源为 `ai-album-hk-representative-v1/test-260831`。审计代码基点为 `615c3359941927515f0c0a8738a3f08122bcad46`；共享工作区和原 Plan 会话随后继续变化，不能把当前磁盘状态当作当时状态。

PreCheck Run 为 `precheck-run:8b5ff902fda54e6292b14d4fa5f0de42`，Result 为 `precheck-result:cbd18bc79b56b2b9d257529f878b7151c399b4815acebe74d1ba328e80a7ae57`。初版 Plan 轨迹固定到配置中声明的原会话前 859 行；后续更正按报告中的时间与行号分别引用。原始媒体、数据库、完整轨迹和 HTML 快照在本机，不复制到本包。

公开语义以 [当前合约](../../../docs/spec/contract/index.md) 为准；本包不成为另一份规范，也不改变既有验收或迁移决定。

## 修复与验证交付（2026-09-13）

### 原因与修复

首轮修复前源码在 GPX Work 上查询 `gps_coordinates`。新增测试用真实 MetadataProducer、GPXMatchProducer、rendition 和 embedding Work 构造消费链，修复前 `_prepare_input` 得到的坐标为 None，直接揭示了丢失；没有用手写同名字段假装生产者已接通。

现有压缩 producer 分别读取 metadata 的 `gps_coordinates` 和 GPX 的 `gpx_coordinates`，保留 metadata 优先、GPX 补缺及只有 available 值可用的规则。GPX 仍是带来源/匹配依据的候选；没有覆盖源 GPS、改变 Geo 采集坐标策略或将代表坐标推广成所有成员的事实。

对实际采用 GPX 的组，沿现有 WorkDependency 增加内部 `coordinate_evidence_policy=gps-then-gpx-v1`。必要性是组成员即使没变，旧 Work 中的限定仍可能已失真，不能返回旧输出同时只在内存里声称修正。实际边界 basis 变化继续参与既有依赖；上游 metadata、GPX、向量、材料及无关有效 Work 保留。没有新增实体、公开字段或 schema，原 Result 不改写。

### 真实 producer 回放结果

[run_compression_gpx_check.py](../../../tests/run_compression_gpx_check.py) 从原数据库做只读 backup 到隔离目录，复制所需已保留向量后按正常 Artifact 验证，再执行真实 `_prepare_input` 和 `AdaptiveCompressionProducer.produce`。它没有改写审计脚本来模拟新字段，没有换向量或重新执行模型；源码和隔离 wheel 均得到相同结果：

| 指标 | 修复前保留结果 | 修复后真实 producer |
| --- | ---: | ---: |
| 输入点 | 167 | 167 |
| 实际坐标点 | 89 | 144 |
| 额外消费的 GPX 点 | 0 | 55 |
| 组数 | 156 | 156 |
| limited_similarity_evidence | 71 | 21 |
| bundle_members_not_visually_compared | 82 | 82 |
| unavailable_bundle_representative_replaced | 1 | 1 |
| content_distance_scale | 0.311 | 0.311 |

组身份及成员一致；50 组的限定发生变化。组边界依据/消费策略也参与 Work 身份，因此这次复用了 15 个旧组 Work；再次执行修正后的输入时 156 个全部复用。每个返回 group 的限定与实际持久化 Work 输出一致。仅组数相等不是通过标准。

[test_compression_gpx.py](../../../tests/test_compression_gpx.py) 还证明 GPX 点确实进入空间距离计算：足够远的已知坐标产生大于 1 的归一空间距离；同一对照缺坐标时该证据项为 0。缺坐标输入保留 limited 限定，有完整时间/坐标/向量的输入才去除该限定。既有压缩/Read 回归验证精确成员与不可变旧 Result。

全量素材与原 Result 的完整性边界同 [GPX 成本包](../review-gpx-matching-cost/README.md#回归与素材完整性)。精简结果、脚本及 wheel 身份见 [verification.json](verification.json)；隔离输出在 `/tmp/mediasense-run-acceptance-repairs/`。

### 剩余限制与决策

这证明本次已有 GPX 信息被实际消费并正确影响限定，不证明全部场景的语义分组正确，也不证明组数、地图查询数应减少。0.311 用户决定保持不变。没有封存新业务 Result、修改原 Result 或切换日常 Host；这些是独立后续交付。本次没有需要用户重新决定的具体事项。

首轮共同自验的历史记录：源码 **158 passed**；隔离 wheel **158 passed**，并通过离线 CLI/MCP 分发 smoke。旧 wheel SHA-256：`55db47084afc8c75b3204d358ff0f771f7d8b2a337695efc15573139bdf4c55b`；其临时产物已丢失。

## 产物缺失后的二次交付（2026-09-13）

用户已独立确认字段消费、metadata 优先、受影响 Work 失效及空间比较路径，接受本项代码。本轮只修复相邻 Google/GPX 问题并恢复可复核安装包，不改变压缩实现、坐标语义或 0.311 默认尺度。

原 `/tmp/mediasense-run-acceptance-repairs/` 已不存在，无法重验旧 wheel。新构建基于 `0794d3c9182793b7b25c1cac77793e3c97e42092` 加本轮两个补修，源码和隔离 wheel 共同回归各 **166 passed**，包含真实 GPX producer 到压缩消费者的测试；包文件一致性及离线 CLI/MCP 分发 smoke 通过。没有重跑香港全量压缩，原 **55 个坐标、71→21 个限定、156 组**继续作为首轮历史证据，不是本轮新测量。

新 wheel SHA-256：`9e813bda30fa4b7cc33517d582aefd7547f48e7836a8a78ed7a0f9df31df9f9f`。持久产物在仓库内 `.local/acceptance-releases/260913-1107-google-gpx-r2/`，由现有 Packet 指向，不新增发布注册表。保留源码、归档、差异、约束、venv 和日志：[复核说明](../../../.local/acceptance-releases/260913-1107-google-gpx-r2/REVIEW.md)、[校验清单](../../../.local/acceptance-releases/260913-1107-google-gpx-r2/SHA256SUMS)。[verification.json](verification.json) 的 current_delivery 是当前证据，previous_delivery 是不可冒充新包验收的旧记录。

本次未进行日常安装升级或业务 Result 改写；本项代码通过与共同安装包独立复验的状态分开记录。
