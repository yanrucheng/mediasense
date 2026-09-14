## Status and evidence boundary

This file owns the implementation acceptance criteria and evidence. The design-only planning milestone on 2026-09-13 withdrew prematurely written code; the Human subsequently explicitly authorized formal development and isolated acceptance. Daily installation and publishing are outside that authorization. Planning evidence below remains historical and never substitutes for the implementation record.

## Development-ready gate (planning milestone history)

| Gate | Required evidence |
| --- | --- |
| Concepts and decisions | Accepted model linked once; local parameter semantics and complete explicit requests have no unresolved alternatives |
| Contract design | Proposed fields, required/optional/null meanings, scope binding and failure outcomes are explicit in design/specs; actual canonical schema edits are assigned to implementation |
| Consumer usability | The planned read→request→new Result→correspondence→Plan sequence does not require private state |
| Negative behavior | Incomplete Profiles, scope overlap/outside/empty, stale configuration, wrong Result/cursor and false correspondence have specified outcomes |
| Engineering design | Configuration projection, dependency boundary, partitioning, sealed input lineage, recovery and retention are assigned to existing owners |
| Execution plan | Every implementation task has concrete files, prerequisites and an exit gate; all implementation tasks remain unstarted |
| Handoff boundary | Provide this design package and stop; the user arranges the implementation Agent |

Only OpenSpec document validation belongs to this planning milestone:

```sh
rtk proxy env OPENSPEC_TELEMETRY=0 openspec validate simplify-precheck-run-composition --strict --no-interactive
```

The implementation Agent must first create and validate the canonical schemas, shared fragments and positive/negative examples, including configuration identity vectors. It then implements the matrix below with real components. No executable verifier or test has been retained from this planning task.

## Implementation acceptance matrix

| Case | Pass condition |
| --- | --- |
| Ordinary same-input Run | Different request_id creates a new Run/Result; valid expensive metadata/decoding/embedding/detector/provider work is not executed again |
| Exact replay and resume | Replaying an accepted request after Dataset defaults change still returns its Run; resume keeps the frozen settings; changed request content conflicts |
| Local threshold change | T uses its full new settings; S−T parameters are identical to their declaration; cached inputs are reused; every accounted item remains present |
| Existing group crosses T | Inputs are split through exact source members before final compression; one representative's attributes never become facts about the other members |
| Count fallback / actual dependency | Outside groups may change, with readable members/basis; unchanged dependencies do not cause gratuitous producer execution |
| Missing selected input | Only the selected/actually required boundary input is prepared; disabled content comparison rejects an ineffective content-threshold override; missing enabled backend follows a real recoverable prerequisite |
| Same bytes in different files | Two source occurrences map to two distinct target references; path/content equality without an explicit input binding gives unproven |
| Changed / unavailable source | Detected revision change fails the same-snapshot request; disconnection is a recoverable availability condition; neither is silently accepted as the old input |
| Different / historical Result | Read is usable; absent preparation is null with a qualification; absent direct lineage is unproven, without private Work lookup |
| Large scope readback | An override containing 100000 synthetic source references reads back as one profile_scope selector; resolve pages all exact members with stable identities and no configuration truncation |
| Source Set cursor | Changing source Result, target Result, expression, limit or position invalidates the cursor; full original membership digest remains independently recomputable |
| Disabled capability | Cached disabled detector/embedding output does not become newly requested evidence; independent valid caches remain reusable |
| Failure / publication retry | Inject failure before and after durable publication boundaries; retry neither duplicates Result publication nor loses valid sibling work |
| Retention | Old Result bytes/reads remain stable after new Runs and producer-cache cleanup; protected publication material is retained or loss is explicitly reported |
| Plan continuation | Public Tools can recover prior notes/preferences and map the intended source scope into a new Work; new Evidence is inspected where material; new Human confirmation is required |
| Host and installed artifact | The same path executes through real composed internals and isolated CLI/MCP; tool discovery and mock success alone do not count |

## Cost measurement and acceptance

Use controlled synthetic preparation inputs of 4096 and 8192 entries plus the small eight-entry boundary case. First measure the existing baseline under the same build, hardware, source-verification profile, resource limits and output obligation. Use warmed repeated runs and report median wall time separately for verification, reusable-work lookup, actual producer execution and sealing. Do not manufacture a universal seconds threshold.

Mechanistic requirements are fixed before measurement: zero expensive producer calls for fully valid warm inputs; threshold-only changes do not rerun metadata/decoding/embedding whose dependencies are unchanged; a newly demanded uncached source does not invalidate unrelated Work; input visits, persisted membership and Result assembly remain linear in the accounted sources plus relationships. Record query/write counts and peak memory so a nominal cache hit cannot hide quadratic coordination or per-Run duplication of large producer outputs.

A failure of these mechanisms blocks release. Unexpected dominating full-source I/O or materially increased resource cost requires an explicit optimization/acceptance decision, not a weaker output or an invented timing claim. Existing historical 62-test evidence is not this release's acceptance, and the old 500→3→200 scale test is not cited until its current contract calls run successfully.

## Verification record

2026-09-13: `openspec validate simplify-precheck-run-composition --strict --no-interactive` passed. This validates the OpenSpec document structure only. This task's schema/contract edits, executable validator and tests were withdrawn; targeted diff inspection confirmed no remaining changes in the Run/Read contracts, their packaged schemas or the existing Run contract test from this task. Concurrent Plan development was preserved. No schema/runtime test or production acceptance is claimed.

## 实施验收记录（2026-09-14）

功能实现与隔离入口自验已完成；**整体成本验收未通过**，按用户关于明显增加成本先讨论的指示暂停进一步改造。用户在 2026-09-13 明确授权接手；本记录不宣称用户独立复验、日常安装升级或发布。概念模型不变，公开承诺落在当前 Run/Read 契约；本包是实施与验收记录。

### 实际交付

| 范围 | 实现与证据 |
| --- | --- |
| 正式契约 | Run 的完整 Profile、固定输入与拒绝语义；Read 的 preparation、profile_scope、直接 correspondence；同一权威的 Schema、交换示例、固定身份向量、发布资源和 Skill 引用一致性检查 |
| 配置与范围 | 新请求先冻结当前有效设置、原始请求和精确成员；原请求重放先于可变默认值检查；恢复原 Run；改要求创建普通新 Run。大成员快照在原 Run 的只写一次表保存，进度行不反复携带它 |
| 局部准备与复用 | 初始预算使用冻结基础设置，T 成员成为定向需求；范围外继续基础准备。跨界 bundle 保留真实剩余成员和可用代表，必要时只补替换代表；100 项用例分别只新解码 1 项、2 项。阈值变化不重做有效输入，模型身份变化只重做相关 embedding |
| 发布与留存 | 逐来源核对 attachment、stat 与既有指纹；输入变化拒绝，附件断开或原路径变成其他目录时可恢复等待。发布前后故障重试只生成一个 Result。封存 Profile、成员和直接绑定；来源对应是读取视图，不另存重复交换对象。旧 Result 字节、材料与读取保持，删除测试 Run 的准备快照后仍可独立读取 Result |
| 公开读取 | profile_scope 在确切 Result 内解析；100000 合成成员保持紧凑回读、完整分页与可重算摘要。游标绑定源/目标 Result、表达式、limit 和位置；相同字节/同 inode 不同名称保持两个 occurrence；独立或缺历史数据的对应为 unproven，矛盾绑定拒绝 |
| Plan 接续 | 公开 inspect 旧 Work → resolve 对应 → 检查新 Evidence → create 新 Work → 保存说明、偏好及新组织 → review；旧 Work 不重绑，旧确认不转移，未确认 seal 被拒绝 |

### 代码与入口检查

- 最终默认检查：**1462 passed，17 deselected**，见[完整日志](../../../.local/acceptance-releases/260914-0034-run-composition/final-r6-tests.log)。Ruff 与 OpenSpec strict 检查通过。
- 专项规模检查：修正后的 500→3→200 当前调用和 100000 成员分页均通过；100 项跨界需求、附件替换/恢复、发布前后重试、历史缺项及矛盾绑定有独立正反例。相关测试定义位于 tests/test_run_composition*.py、tests/test_preparation_configuration.py 与 tests/scale/。
- 最终 wheel：`mediasense-0.10.2-py3-none-any.whl`，SHA-256 **`1835e3e904ee75b4e5f442ecd1b177edb1abb5e68d0de8e1eadb1e95d37f6b86`**。代码基点 `c5936ca8fc81f4a44839fad775509e09c5577e17` 加完整工作树快照；[逐文件身份](../../../.local/acceptance-releases/260914-0034-run-composition/r6/source-files.json)、[源码差异](../../../.local/acceptance-releases/260914-0034-run-composition/r6/source.diff)、[固定依赖](../../../.local/acceptance-releases/260914-0034-run-composition/r6/dependencies.txt)与 wheel/venv 都保留在 ignored 验收目录。
- Artifact 检查确认源码包文件、Schema、四个 Skill 及 installation snapshot 一致。隔离 CPython 3.11.13、相同 core 依赖、无模型 extras；实际 **47 次 MCP + 5 次 CLI** 调用通过，包含两个普通 Run、两份 Result、来源对应、新 Work、重启重放和缺确认拒绝。[完整报告](../../../.local/acceptance-releases/260914-0034-run-composition/r6/installed-smoke/report.json)及[调用轨迹](../../../.local/acceptance-releases/260914-0034-run-composition/r6/installed-smoke/trace.json)保留实际返回。
- CLI 的 start/resume 仍明确要求持久 Host；本次由真实 MCP Host 承担执行，CLI 完成读取和 Plan 调用，没有伪造一次性 CLI 的 worker 生命周期。
- 安装入口的后继 Run 复用全部 8 项 metadata，按实际缺口新增图像准备；[生产者记录](../../../.local/acceptance-releases/260914-0034-run-composition/r6/installed-smoke/producer-reuse.json)区分附属 Work 和真正执行。源文件 SHA-256 前后相同，provider requests=0，模型明确关闭。

### 成本实测

接手时的[基线源码及逐文件身份](../../../.local/acceptance-releases/260914-0034-run-composition/baseline-source-files.json)已另存于同级 `baseline-source/`，包含原始工作树差异；不会由后续候选覆盖。

全部为当前 Mac 上的受控合成 8×8 JPEG，所有输入先有普通/高清准备；固定一个 worker、两个 pending、512 MiB executor 资源预算（不是整个进程 RSS 上限）、target_entries=2。metadata/video/GPX/embedding/detector/provider 不参与本项规模测量。baseline 是接手时源码，r2 是初轮实现，各大小三次暖运行取中位数；最终 r6 各大小复测一次，使用新进程读取既有合成 fixture/cache。旧实现不支持显式同快照请求，baseline 走普通发现，r2/r6 走显式固定输入；比较保持来源校验 profile、输入和完整 accounting/入口数量义务，不能解读为同一算法或相同新增封存语义的纯微基准。单次复验不冒充三次中位数。r1 至 r6 的独立源码与 wheel 均保留。

| 输入数 | baseline 中位 s | r2 中位 s | r6 单次 s | baseline 峰值 RSS MiB | r2 峰值 RSS MiB | r6 峰值 RSS MiB |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4096 | 296.055 | 102.775 | 220.658 | 451.0 | 757.8 | 496.3 |
| 8192 | 830.250 | 299.033 | 538.285 | 841.9 | 1196.5 | 1052.8 |

| r6 输入数 | accounting/snapshot s | Work lookup s | 新解码 | assembly s | sealing s | SELECT / 写语句 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4096 | 6.917 | 9.204 | 0 | 9.382 | 141.385 | 358561 / 77897 |
| 8192 | 49.945 | 39.656 | 0 | 38.300 | 179.380 | 718767 / 155746 |

[baseline](../../../.local/acceptance-releases/260914-0034-run-composition/evidence/scale-baseline.json)、[r1 首次/局部调整](../../../.local/acceptance-releases/260914-0034-run-composition/evidence/scale-r1.json)、[r2 重复暖运行](../../../.local/acceptance-releases/260914-0034-run-composition/evidence/scale-r2.json)、[r4](../../../.local/acceptance-releases/260914-0034-run-composition/evidence/scale-r4.json)、[r5 缓存修正](../../../.local/acceptance-releases/260914-0034-run-composition/evidence/scale-r5.json)、[最终 r6](../../../.local/acceptance-releases/260914-0034-run-composition/evidence/scale-r6.json)保留每轮时间、查询/写计数、RSS、Result 引用和输出数。r1 的局部调整仍完整交代 4096/8192 项并输出 6 个入口，新增解码均为 0。r6 两个规模同样零新增解码、完整交代全部输入。

成本处置：初轮发现普通读取无条件保留两份 Result 图，明显增加峰值内存。r5 先将双图缓存限定为跨 Result resolve；r6 又在新 Run 接受并冻结输入后释放已消费的 prior 图，消除它在执行期的不必要驻留。普通读取在解析新 Result 前释放旧图；只有跨 Result resolve 可共用既有缓存预算保留两图，从而避免每页重新验证。弱引用测试证明旧图在新图验证前及新 Run 接受后已释放，随后重新读取旧 Result 仍返回完整相同内容；真实后继的逐页来源对应测试证明两图各只验证一次，原有字节/身份/注册/损坏检查继续通过。最终 RSS 与基线的差异照表保留；新 Result 额外封存配置、精确成员与直接来源绑定，按输入量线性增长，不复制大图或向量载荷；但这不能替代峰值分配归因。最终 8192 项 RSS 为 1052.8 MiB，比接手基线 841.9 MiB 高约 25.1%，尚未解释并消除该增量，**成本门槛未关闭**。建议下一轮追踪 Run 冻结、Result 组装和校验期间的峰值分配，再用既有样本复验；目前不建议直接接受该内存增量。executor 预算保持不变；本测量报告的是实际进程峰值。

这些时间是共享开发机上的观察值，不是跨设备阈值。r6 的 4096 项单轮 sealing 达 141.385 s（r5 为 18.500 s），本轮未单独归因该波动；它没有新增解码，也不能据此声称稳定的加速比例。分项是所列函数边界的包围时间，sealing 包含最终来源与 pin 验证；不能把它们当作完整、互斥的 I/O 归因相加。仍有 O(N) 来源验证、索引、状态观察和封存成本；真实大图/视频的 I/O、解码或模型吞吐不由这些小图证明。有效暖输入不再推理/解码，真实依赖以外的 Work 不失效，成员持久化与组装按源项和关系推进。

### 修复过程与限制

初轮默认检查有 7 个 Plan 测试差异，在接手前快照也复现；随后工作区的并行测试更新进入最终快照，未由本任务修改其产品实现。4 个 loopback 检查最初被沙盒端口限制阻止，隔离放行后通过；旧 schema 测试现显式区分支持的 17/18 与不支持版本。第一次安装检查器误把 Plan 的业务 error 当成 MCP isError，按现行传输边界修正检查器后完整重跑；失败日志与中间产物保留。

仅支持同一 Dataset、一份 prior Result 的完整输入快照和直接后继对应。没有自动合并多 Result、迁移文件、调和源修改或猜测缺失历史；`matched` 只具备声明的普通变化检测强度，不是完整字节相等或观测/分组等价。真实模型质量、远端服务、所有平台与文件系统、大媒体吞吐及 Human 的组织判断未认证。本次未改日常 CLI、用户配置、业务 Dataset、项目 Skill 安装或发布版本。


## 独立验收补修记录（2026-09-14）

**本轮规定的行为、回归、隔离入口及成本自验通过，等待独立验收。** 前面的 r6 记录保留为历史，不再作为本轮成本结论。未执行日常安装升级或发布。

### 接手身份与改动

接手时当前代码和测试与 r6 一致，只有 5 份文档在快照后变化；[初始差异](../../../.local/acceptance-releases/260914-run-composition-repair/initial-r6-differences.json)、[初始逐文件身份](../../../.local/acceptance-releases/260914-run-composition-repair/initial-source-files.json)和工作树补丁均保留。期间并行提交 `62be2fe`、`b79be81` 纳入前一轮补修及 0.11.0 版本工作，本任务未撤回或覆盖。最终运行代码与 `candidate-2/source-files.json` 一致；更新后的[完整交接导出身份](../../../.local/acceptance-releases/260914-run-composition-repair/final/source-files.json)及[最终 wheel 对应记录](../../../.local/acceptance-releases/260914-run-composition-repair/final/artifact-identity.json)独立保存。

| 问题 | 原因、修复与反例 |
| --- | --- |
| 冻结要求丢失后恢复降级 | r6 缺行时返回 preparation=None，执行转为普通发现，Result 再被误标为历史缺项。现在读取必须取得完整冻结记录，核对结构、原请求及新记录载荷摘要；摘要复用 execution_config JSON，不加表、实体或公共字段。缺配置不再从当前默认值重建，读取/解析在 worker 失败收尾内。删除、null、坏 JSON、改变 input/scopes/profile 均 failed/execution_failed，未访问快照源、未发布新 Result。完整旧冻结记录仍可恢复；历史 Result 的合法 null 投影和独立读取不变。 |
| 源变化误分类 | SourceChangedDuringRead 继承 OSError，曾被当作临时不可读。现在先捕获确定变化，返回 failed/source_snapshot_changed；普通 PermissionError/OSError 保留 blocked/source_verification_unavailable，恢复访问后继续同一 Run。初始核验和发布前复核均有正反例。 |
| 成本与内存 | 改为每规模、每重复独立进程，固定暖工作区副本；区分 Run 区间、预热和后置留存检查。增量 JSON 编码避免整份 Unicode 文本与 UTF-8 字节并存，保持规范字节和全部校验。封存后由原 worker 接收已有 SealedResult，释放准备/草稿/生产者临时对象，再完整读回校验并写 completed；不新增状态或实体，不删除 Work/Result。 |

行为反例修复前为 **7 failed、1 passed**，见 [reproduction.log](../../../.local/acceptance-releases/260914-run-composition-repair/reproduction.log)。后续 116 项定向、86 项结果/恢复回归通过；对象存活反例在第一候选上失败，补修后与相关回归共 **101 passed**。正常 8 项 / 2 入口 → 指定两项分别呈现 / 4 入口、历史读取、默认值变化后的恢复、发布重试和原 Result 留存均有真实 Host 覆盖。

### 最终测试与隔离入口

- 最终隔离 wheel 默认集：**1474 passed、17 deselected**，[日志](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/default-tests.log)。500→3→200 与 100000 成员分页在已安装 wheel 中 **2 passed**，[日志](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/scale-tests.log)。Ruff、OpenSpec strict、artifact/发布资源一致性检查通过。
- Wheel：`mediasense-0.11.0-py3-none-any.whl`，SHA-256 **`8b52d48704de8af6621c7b40689c9a830221b7fa03ef02b5bf5f5a2e6fc0deb2`**。来源为 `b79be81` 加保留差异；[逐文件身份](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/source-files.json)、[补丁](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/source.diff)、[固定依赖](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/dependencies.txt)均保留。0.11.0 来自并行版本工作，本任务只构建隔离 wheel。
- CPython 3.11.13，与 r6 相同的 core 依赖版本；无模型 extras，另在隔离 venv 安装固定 pytest。实际 **85 次 MCP、6 次 CLI** 通过 Run→Read→新 Run→Read→Plan、重启重放、缺确认拒绝；[报告](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/installed-smoke/report.json)和[完整交换](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/installed-smoke/trace.json)包含实际返回。
- 安装入口的删除/损坏冻结记录、合成源修订变化三个注入均得到预期 failed 状态，仍只有两份正常 Result。删除全部测试 Run 冻结记录后，独立 CLI 进程仍完整读取 Result。源修改仅由测试器在自建媒体中注入并恢复；正常链路及结束时源 SHA-256 相同，provider requests=0，模型关闭。
- 首轮开发环境默认检查有 8 项失败：4 项 loopback 沙盒限制、3 项并行版本更新后的旧包元数据、1 项写死旧版本线的测试。断言改为核对实际版本线，未改产品契约；隔离复核 74 项通过，最终上述完整默认集也全部通过。失败记录保留，未通过切换日常安装掩盖环境差异。

### 修正后的成本比较

同一 Mac（48 GiB、18 个逻辑 CPU）、CPython/core 依赖、合成 8×8 JPEG 内容、来源变化检测 profile、普通/高清准备、完整 accounting 与 2 个入口义务保持。固定 1 worker、2 pending、512 MiB executor 预算（不是进程 RSS 上限）。metadata/video/GPX/embedding/detector/provider 不参与规模计算。每个样本从固定工作区副本开始，显式读 prior Result 预热，随后只运行一次新 Run；复制与预热不计入 Run 墙钟。旧 Result 哈希使用流式读取，避免测量器先制造整份文件缓冲。OS 文件缓存不刷新，样本串行；测试未与测量重叠。

普通矩阵使用同一固定[测量脚本](../../../.local/acceptance-releases/260914-run-composition-repair/scale-measurement.py)，各报告含脚本 SHA、PID、时间、负载、预算、输入内容身份和阶段记录；最终仓库脚本另补了局部选择与峰值上下界报告。基线是接手前实现，走普通发现；候选走显式同快照输入并额外封存配置、accounting 和直接绑定。因此是相同覆盖与准备义务下的产品成本比较，不是相同接口/算法的微基准。旧状态数量也保留：基线各 4 份 Result，候选 4096/8192 模板分别 10/12 份。

| 输入 | 基线墙钟中位 s | 最终墙钟中位 s | 基线 Run 峰值 MiB | 最终 Run 峰值 MiB | RSS 变化 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4096 | 261.739 | 103.839 | 443.2 | 362.8 | -18.1% |
| 8192 | 964.744 | 306.563 | 818.2 | 667.5 | -18.4% |

每格来自 **3 个独立进程样本**。[全部样本/汇总](../../../.local/acceptance-releases/260914-run-composition-repair/cost-summary.json)保留原值。4096 墙钟范围为基线 242.669—317.845 s、候选 97.085—107.497 s；8192 为基线 926.699—986.142 s、候选 291.051—308.836 s。时间差也包含主体实现已有的协调优化，不能全部归因于本次内存补修。

| 最终输入 | accounting/snapshot s | Work lookup s | assembly s | sealing s | 完整读取校验 s | SELECT / 写语句中位 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4096 | 5.780 | 10.970 | 10.908 | 22.229 | 4.799 | 357381 / 77893 |
| 8192 | 26.247 | 29.455 | 36.741 | 59.948 | 9.217 | 716080 / 155739 |

分项是函数包围时间，部分嵌套；sealing 含最终来源与 pin 验证，不能相加当成互斥 I/O 分解。有效暖输入 **12/12 个正式样本零新解码**，Work lookup 次数分别 8194/16386；查询/写入及存储量随源项和关系近似成比例增长，不用两档耗时冒充通用复杂度证明。

RSS 记录采用 20 ms 当前 RSS 采样与独立的 ru_maxrss。原累计高水位无法重置，不能直接分摊给多个规模。本轮 12 个正式样本的高水位都在 Run 窗口内再次上升，因此可确定其 Run 峰值；若未上升只能报告采样下界和历史上界。短暂原生/GIL 峰值可能漏采，例如最终 8192 首轮采样约 653 MiB、区间高水位约 674 MiB，本表采用后者。该矩阵的进程峰值（含预热、公开读取和留存检查）恰与对应 Run 峰值相同；原始字段仍分别保存，未推断长驻多 Run 进程的未来峰值。

### 内存归因、输出与留存

同方法的 8192 单轮诊断（不冒充三次中位数）显示：r6 编码阶段约增加 297 MiB；增量编码后约增加 74 MiB，第一候选总峰值仍约 875 MiB。对象存活测试进一步证明已封存草稿和准备数据仍压在读回栈上；释放它们后，最终候选首轮读回从约 390 MiB 上升到 612 MiB，总峰值转移到接受/冻结输入阶段约 674 MiB。局部样本额外记录 run_acceptance/frozen_input_write，8192 接受阶段高水位约 672 MiB，支持这一定位。未放松来源核验、规范字节、注册/引用/pin 检查或保留策略。

[独立输出核验](../../../.local/acceptance-releases/260914-run-composition-repair/cost-output-audit.json)覆盖全部 16 个正式/诊断样本：4096 为 4096 Source、8192 Evidence、40958 条关系；8192 为 8192 Source、16384 Evidence、81918 条关系，各版本数量相同。相同合成图像按内容复用 2 个物理产物，其引用、大小与 SHA 均核对；物理去重不合并 Source occurrence。每样本保留全部原 Result，恰增加一份新 Result。候选 Result 约 38.78/77.55 MB，基线约 35.46/70.92 MB；新增封存数据没有为压低内存而删除，路径长度也影响少量字节数。

[局部参数样本](../../../.local/acceptance-releases/260914-run-composition-repair/local-candidate-2-r2/metrics.json)分别使用独立进程，完整交代 4096/8192 项并返回 **6 个入口、零新解码**；所选 T 通过公开关系 resolve 全量分页，核对去重、数量和 membership_identity。局部样本墙钟约 113.081/302.503 s，Run 峰值约 364.9/671.7 MiB，均为单轮功能/归因证据。

测量存在一项明确的夹具限制：旧 Result 封存绝对材料路径，克隆 workspace 后旧材料页会正确返回 evidence_unavailable，不能把相同故障页当成可用性证明。本轮未改写旧字节或放宽路径核验；[定位记录](../../../.local/acceptance-releases/260914-run-composition-repair/clone-path-diagnosis.json)证明材料在原处和副本的 SHA 相同。局部选择使用返回的 Evidence 引用和公开 represents 关系，不声称打开旧图片。[原位置只读复验](../../../.local/acceptance-releases/260914-run-composition-repair/original-result-reads.json)对两个规模、两套原夹具共 4 次均完整返回 2 个入口、零材料故障。正常同址新 Run、缓存清理和独立 CLI 的旧 Result 可读性另由功能/安装测试证明。普通成本数字只证明所述克隆、暖缓存和有限读取条件，不认证 workspace 迁移后的地址重绑定。

### 通过项与边界

- **通过**：冻结缺失/损坏拒绝、源变化/读取不可用区分、合法恢复与历史读取、必要回归、最终隔离入口、规定规模功能、独立重复成本、零重复昂贵计算、完整输出与旧 Result 留存。
- **本轮清单无未关闭的自验失败**；早期失败及修正过程保留。尚未执行用户独立验收。
- 未认证真实大图/视频与模型吞吐、其他平台/文件系统、长驻 Host 多轮内存或工作区迁移后的旧绝对地址恢复。未改变已确认 Run/Result/Profile 模型、公共契约、留存义务或外部效果范围；未执行日常安装升级与发布。完成后停止，等待独立验收。
