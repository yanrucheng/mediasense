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


## 独立验收补修记录（2026-09-14，进行中）

本节记录独立验收指出缺口后的补修，前面的 r6 实施记录保留为历史。本轮仅授权开发与隔离验收，成本矩阵尚在执行，未宣布整体验收通过。

### 行为补修

- 冻结要求：r6 把 preparation 从进度行移入只写一次表，但读取时缺行返回 None；orchestrator 随后选择普通发现，Result 又被当作合法历史缺项。现在执行读取必需冻结记录，验证结构、原请求及新记录的载荷摘要；摘要位于已有 execution_config JSON，未增加表、实体或公共字段。缺配置不再从当前默认值重建。读取/解析放入 worker 的失败收尾边界，坏 JSON 也不会留下假运行。真正历史 Result 的 preparation=null 语义不变，Read 仍只依赖封存数据。
- 源修订：SourceChangedDuringRead 继承 OSError，原分支误判为临时不可读。现在先捕获确定的变化并映射为 failed/source_snapshot_changed；普通 PermissionError/OSError 继续可恢复等待。初始核验与封存前复核均有反例。
- 修复前新增用例为 **7 failed、1 passed**；首轮相关回归 **116 passed**，后续含规范编码与发布重试的回归 **86 passed**。原始日志保存在 `.local/acceptance-releases/260914-run-composition-repair/`。

### 隔离构建与检查

候选 `candidate-1` 从独立源码导出构建，完整逐文件身份、工作树差异、依赖约束和日志均保留。wheel SHA-256 为 `8c8d8730106f8998ab7d8e340e0c8114f48b700b35a997c99d5fccf8456be48e`。并行版本工作把源码版本更新为 0.11.0，本任务保留该改动，仅生成隔离的 `mediasense-0.11.0-py3-none-any.whl`，没有执行发布或日常切换。

实际安装使用 CPython 3.11.13 与 r6 相同的 33 项 core 安装组合（MediaSense 自身由候选替换），无模型 extras。artifact 内容校验通过；**78 次 MCP、6 次 CLI** 通过普通 Run→Read→新 Run→Read→Plan、重启重放、缺确认拒绝及新增三个故障。删除/损坏冻结记录均 failed/execution_failed，合成源修订变化为 failed/source_snapshot_changed，仍只有原两份 Result。删除全部测试 Run 冻结记录后，独立 CLI 进程继续完整读取 Result。源修订注入由验收脚本修改其自建媒体并恢复；正常链路与结束时源 SHA-256 相同，provider requests=0，模型关闭。

默认开发环境检查首轮 **1465 passed、8 failed、17 deselected**：4 项因沙盒禁止 loopback；3 项因并行版本更新后开发环境仍保留旧包元数据；1 项把旧版本线写死在测试中。该断言改为核对实际版本线，未改产品契约。使用隔离 wheel、清除 PYTHONPATH 并允许测试本地 loopback 后，失败文件及补修回归共 **74 passed**。没有切换日常或开发安装来消除版本差异。Ruff 与 OpenSpec strict 通过。

### 成本测量进展

旧 ru_maxrss 数据是同一进程的累计高水位，不能当成每个 Run 的独立峰值；r6 每规模一次也不是中位数。修正的测量器逐规模、逐重复启动新解释器，先复制固定暖工作区再测单次新 Run，所有旧 Result 保留。源、廉价准备开关、两个图像规格、target_entries=2、1 worker/2 pending、512 MiB executor 预算及变化检测 profile 保持；实际 Run RSS、预热前后的进程高水位、公开读取和后置留存检查分别记录。20 ms RSS 采样是近似区间峰值，ru_maxrss 单独保留；不刷新 OS 文件缓存，计时包括同样的 SQL 计数和状态轮询。

初次定位在 JSON 编码阶段观察到约 296 MiB RSS 增量。原实现先构造整份 Unicode JSON，再编码成 UTF-8；现在用标准 JSONEncoder 分块写入 BytesIO，避免同时保留整份宽 Unicode 文本。规范字节、非有限值拒绝、封存和读取核验以及故障重试承诺不变。正式比较还使用流式哈希检查历史 Result，避免测量器自身先读入整份文件抬高高水位；该调整不减少核验。

正式基线、r6 对照及候选重复矩阵和分阶段记录尚未完成；本节将在完成后补齐数值与明确通过/未通过项。
