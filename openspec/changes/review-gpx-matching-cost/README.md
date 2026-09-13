# GPX 匹配重复工作与本地处理耗时

## 交接状态

记录日期：2026-09-13。阶段：**重复解析优化已获用户确认；资源不足的公开反馈补修及确切持久 wheel 已通过独立 Agent 复验。未升级日常环境；首轮全量计时未重测**。

独立复验结论与范围见[运行验收报告末尾的第 1—3 包再次独立验收](../../../eval/sessions/260912-2333-hk-run-acceptance/report.md)。该结论绑定新 wheel `9e813bda30fa4b7cc33517d582aefd7547f48e7836a8a78ed7a0f9df31df9f9f`，不扩大为日常安装、真实 Provider 成功或历史业务恢复。

当前证据见本页末尾的二次交付。原全量计时保留为历史记录；旧临时 wheel 已不存在，本轮重新构建并记录新身份。

创建时用户要求只整理问题；本次已另行授权在现有设计与合约内直接修复。历史事实保持原义，以下交付记录补充实际实现和测量，没有修改匹配语义或公开合约。

## 已确认事实

1. 本次共完成 2,136 个 `gpx-location-candidate` Work，其中 2,034 个带有被采用的 GPX 轨迹依赖。
2. 使用的两份轨迹文件大小分别为 2,131,984 和 1,840,392 bytes，来源分别为 `2026-05-03T05-33-10+0800.gpx` 与 `2026-05-05T21-47-16+0800.gpx`。
3. GPX Work 首次开始至末次完成为 22:22:15.720—22:32:03.164，跨度 **587.44 秒**。本次 Embedding Work 对应跨度为 **44.10 秒**。
4. `GPXMatchProducer.produce` 在逐源项执行时调用 `parse_gpx_sources(proofs)`；后者读取并解析传入的轨迹。匹配时还从 segment 的点构造时间列表。
5. 按 2,034 个带轨迹依赖的成功 Work 和这条代码路径，可推得 4,068 次轨迹解析入口；该数字不是独立 profiler 的调用计数。
6. 本次没有 GPX Work 失败。可用坐标中，102 个来自内嵌 metadata，1,787 个来自 GPX；“完成匹配检查”不等于每个源项都取得坐标。

## 影响与证据边界

GPX Work 占据这次本地准备中的主要时间段，不能把本地阶段的长等待直接归因于新增 Embedding。

587.44 秒包含相关读取、匹配、校验和持久化，不是纯 XML 解析 CPU 时间。尚未得到各项开销的独立分解，没有本包对应修复后的性能测量。本次代理媒体、两个轨迹的结果不能外推为任意规模数据的耗时。

## 直接复核入口

- 指标：`work.phases.gpx-location-candidate`、`work.phases.image-embedding`、`work.gpx_work_with_track_dependencies`。
- [GPX producer](../../../src/mediasense/precheck/gpx.py)：`produce`、`parse_gpx_sources`、`match_gpx_segments`。
- [PreCheck Run 当前合约](../../../docs/spec/contract/precheck-run/index.md)：复用、有效性、执行成本与发布证据。
- 相关既有包：[吞吐与有效帧修复](../restore-precheck-throughput-and-coverage/proposal.md)。该包已有 EXIF/视频指标不能替代此次 GPX 证据。
- 另一项独立问题：[压缩消费 GPX 坐标](../review-compression-gpx-evidence/README.md)。本包不将两个问题合并成一个原因。

## 创建时的复核问题

- 这段时间中读取、解析、匹配、有效性校验和持久化各占多少？
- 哪些重复工作确实是有效性或恢复语义所必需，哪些缺少复用？
- 如何在保持相同输入、匹配结果和失败责任的条件下比较运行品质？
- 需要什么证据区分首次处理、同 Run 恢复与后继复用？

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

本次保留的修复前 `gpx.py` 与提交 `615c3359941927515f0c0a8738a3f08122bcad46` 的文件字节相同，SHA-256 为 `e6689fc891e4a763349a6f0e1001500154ba6b8fb5a8b1ed63107208e2bdf11f`。没有把审计时安装版本推断为整个当前工作区。

新并发测试中，8 个不同源项匹配同一轨迹，修复前实际调用 XML parser 8 次。全量隔离测量进一步实测到 4,068 次读取与解析，证实此前由代码推算的数量。这些数字不是把历史 587.44 秒当作纯解析耗时。

### 最终改动及必要性

- 在现有 `GPXMatchProducer` 内保留一个有界、不可变的已解析轨迹集合；锁合并并发首次解析。键绑定 Dataset、reuse domain、相对/实际路径、revision、算法、digest 与大小；它没有跨进程权威或独立生命周期，不新增持久 Work、Artifact、缓存服务或 schema。
- 每次二分搜索直接访问已排序点的 timestamp，不再逐匹配构造时间列表。插值、最近点、时差阈值、同分选择、采用轨迹集合及逐项 provenance 保持原义。
- 缓存默认以 64 MiB 的保留对象估算为界；超限照常计算但不保留，不裁剪轨迹。部分解析/读取失败不记入准备缓存，避免恢复访问后仍沿用失败。生产装配复用现有 ResourceAdmission，仅对真正需要执行的匹配申请内存；Work 复用、内嵌 GPS 和时间不可用的短路均不申请解析预算。估算是 `64 MiB + 8 MiB + 64 × 输入字节`，不是实测 RSS 保证；原 source I/O 和 CPU 约束保留。
- 每源项仍独立生成 Work、依赖和 Observation；预检查、匹配后验证、失效和 Work 恢复不减少。第一次缓存装入另作一次前后有效性确认，因此全量 prove 调用从 8,136 增为 8,138，不能把提速归因于跳过验证。GPX producer 身份不变，纯方法优化不让既有有效输出失效。

### 相同输入、相同有效输出的测量

[run_gpx_cost_check.py](../../../tests/run_gpx_cost_check.py) 以原数据库的只读 SQLite backup 建立独立副本，仅重置副本中的 GPX Work 来测首次执行；两侧都使用相同 2,136 个 metadata Work、相同两份轨迹、相同完整采用集合和默认匹配 profile。计时包括逐项验证、matching、Work 读写/提交，排除复制与其他 PreCheck 阶段。每项输出和 Work 身份必须逐项与原记录相等，否则脚本失败。没有模型或 Provider 调用。

| 指标 | 修复前 | 修复后（已安装 wheel） |
| --- | ---: | ---: |
| 首次输出 Work / 实际 matching | 2,136 / 2,034 | 2,136 / 2,034 |
| 轨迹读取 / XML parse 次数 | 4,068 / 4,068 | 2 / 2 |
| 逻辑读取字节 | 8,079,812,784 | 3,972,376 |
| 首次 wall seconds | 586.77 | 54.42 |
| XML parse wall seconds | 477.30 | 0.235 |
| matching wall seconds | 0.749 | 0.023 |
| prove 次数 | 8,136 | 8,138 |
| 新 producer 复用成功 Work | 2,136 | 2,136 |
| 复用时读取 / parse / matching 次数 | 0 / 0 / 0 | 0 / 0 / 0 |
| 复用时 prove 次数 | 4,068 | 4,068 |

所有全量执行的输出摘要均为 `cdf145dc78dc6723ef7c174578b941b18d4dcdec0de42b0f408185a7fc64bd4a`。源码两次首次观察为 48.98 / 56.32 秒，首版 wheel 为 53.84 秒，最终 wheel 为 54.42 秒；复用观察在 15.40—19.92 秒波动，未证明复用时延改善。读取字节是程序逻辑读取量，不是设备 I/O；OS 缓存未清空，基线期间有其他离线验证活动，机器并非专用。调用数与等输出证据比单次时延更强，不外推到任意设备/数据规模。

prove 计时包含已有有效性存储写入；未单独测 SQLite commit 或底层磁盘读取时间。扣除已测子过程后的剩余耗时也包含 metadata/Work 查询、协调与序列化，不冒称全部是持久化时间。

### 回归与素材完整性

[test_gpx_preparation.py](../../../tests/test_gpx_preparation.py) 覆盖并发首次解析、关闭缓存、读取失败后后续源项恢复、源删除/变化、缓存命中期间变化拒绝提交、插值/最近点/阈值，以及预算不足不得伪造失败源项、已有 Work 仍可复用。既有 GPX 测试继续验证后继 Run 复用、轨迹变化后的局部失效与 Read 来源依据。共同的源码和安装包回归包含真实生产编排。

本机 Downloads 包的清单内 SHA 全部匹配，但额外测试目录使整包大小超限，因此没有宣称该目录整包 verifier 通过。仅按原清单复制到隔离目录后，原 verifier 完整通过（10,608 文件、1,759,421,497 bytes）；本次使用的两份轨迹另逐字节摘要匹配该已验证副本。源、fixture 和业务 Result 未改写。

精简测量、构建与回归范围见 [verification.json](verification.json)。输出全部位于 `/tmp/mediasense-run-acceptance-repairs/`；原日志、数据库与媒体不进入 Git。

### 剩余限制与决策

没有重跑完整业务 PreCheck，原 587.44 秒也不是新一轮端到端对照的分母。当前改善来自首次解析及匹配准备，逐项有效性和持久化仍有成本。未认证超大轨迹的峰值内存、恶劣磁盘/卸载或任意设备吞吐。日常安装未切换；本次没有需要用户重新决定的匹配语义或产品取舍。

首轮共同自验的历史记录：源码 **158 passed**；隔离 wheel **158 passed**，并通过离线 CLI/MCP 分发 smoke。旧 wheel SHA-256：`55db47084afc8c75b3204d358ff0f771f7d8b2a337695efc15573139bdf4c55b`；其临时产物已丢失。

## 独立复核后的二次交付（2026-09-13）

用户确认等输出优化证据成立，同时发现 ResourceLimitExceeded 从 GPX 内存准入穿过 stage adapter，最终落入 Run 的通用 execution_failed，缺少资源原因与恢复方式。新增[公开交付测试](../../../tests/test_gpx_resource_delivery.py)使用真实 producer、ResourceAdmission、executor、orchestrator 和 Run 状态流，只替换资源估算以生成已知超预算条件；补修前公开 state 为 failed，所需 blocked 断言失败。

补修仅在 `_gpx` 消费执行结果时捕获现有 ResourceLimitExceeded，沿视频/敏感性阶段既有模式抛出 `_BlockedExecution`。公开 status 现在为 `blocked + gpx_resource_budget_insufficient`，说明 GPX 超出已冻结预算，并给出“取消本 Run、以足够资源启动后继 Run，已完成 Work 可复用”的恢复路径。没有修改通用 run.py 异常处理、资源估算、GPX 匹配/缓存或公开 schema；未知实现异常仍抛出并记录 execution_worker_crashed。

测试实际验证：

- 128 MiB 的冻结预算拒绝替身估算的 256 MiB 需求；metadata Work 保持 succeeded，GPX Work 为 ready 且 attempt_count=0，不伪造源项失败或 Result。
- 只读 status 不执行工作；原 Run resume 后仍以原预算阻塞，没有暗中提高资源。
- 取消后以 512 MiB 预算建立后继 Run，复用已有 metadata 并成功完成 GPX；随后如实报告尚未提供的 Geo 服务前提，未制造完成 Result。
- 未知 RuntimeError 不被重标为资源等待。

源码与隔离 wheel 共同回归各 **166 passed**，包文件一致性与离线 CLI/MCP smoke 通过。使用 CPython 3.11.13、core 依赖及 pytest；未安装模型 extras、调用真实 Provider 或升级日常环境。**本轮没有重测 2,136 项全量耗时**，不把原 586.77→54.42 秒写成新 wheel 的实测。

新 wheel SHA-256：`9e813bda30fa4b7cc33517d582aefd7547f48e7836a8a78ed7a0f9df31df9f9f`。持久目录为 `.local/acceptance-releases/260913-1107-google-gpx-r2/`；完整源码、归档、差异、约束、venv、日志均留存，详见[复核说明](../../../.local/acceptance-releases/260913-1107-google-gpx-r2/REVIEW.md)、[校验清单](../../../.local/acceptance-releases/260913-1107-google-gpx-r2/SHA256SUMS)和 [verification.json](verification.json) 的 current_delivery。旧数据归 previous_delivery，旧临时路径不再作为当前产物入口。

此项补修没有新的产品取舍待决；用户独立验收状态未由工程自验代替。
