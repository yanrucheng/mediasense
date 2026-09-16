---
title: "PreCheck 执行效率实施与成本验收"
service_version: "0.11.0 isolated candidate"
date: 2026-09-14
updated: 2026-09-15
environment: "macOS 26.4.1 arm64; local APFS; Python 3.11.13"
model_id: "disabled in cost matrix"
dataset_version: "synthetic-stills-same-address-v1"
purpose: "实现已复核设计的 S0–S5，保持完整准备、输出和安全语义并实测成本"
baseline_ref: "e10abe8ed78a10205f6e00e1d70906f786ae74b2"
---

# PreCheck 执行效率实施与成本验收

本记录对应[已复核工程设计](../../../docs/design/design-260914-1450-precheck-execution-efficiency.md)和[前期调查](../260914-1359-tool-execution-efficiency/report.md)。2026-09-15 已补修复核发现的 P1/P2，candidate-3 的隔离针对性回归 120 passed，CLI/MCP 与包内容核对通过。**整体验收仍待内存取舍；下列 S0–S5 全量回归和成本数据属于 candidate-2，不能作为 candidate-3 的全量回归或性能实测声明。** 补修记录见文末。未执行日常安装、发布、模型下载或远端 provider 调用。

## 初轮确切身份与证据位置（candidate-2）

原始日志、源码快照、wheel、数据库、媒体和逐样本公开读取轨迹位于 Git 忽略的 [`.local/precheck-efficiency/260914-1826`](../../../.local/precheck-efficiency/260914-1826/)。基线为 `e10abe8ed78a10205f6e00e1d70906f786ae74b2`；会话开始时的并行补修在 S0 固定前已纳入该提交，S0 状态为空。保存的逐文件清单和初始差异优先于仅凭版本号判断。未重置或清理其他工作树状态。

2026-09-14 测量 candidate-2 wheel SHA-256：`e83e5c3c504532900012704ff085a0083c5524aa937880a11edf1650b4ef7204`。本次修改 12 个产品模块；当轮全部 108 个产品 Python 文件在源码、导出快照、wheel 与隔离安装中逐文件一致，见[最终文件核对](../../../.local/precheck-efficiency/260914-1826/candidate-2/final-source-match.json)。59 项非产品依赖与 S0 相同；仓库 `.venv` 的 MediaSense 元数据为旧 `0.10.2`，隔离 wheel 安装为 `0.11.0`。2026-09-14 正式 A/B 均使用这个相同的隔离解释器和依赖，通过 `PYTHONPATH` 分别加载固定 baseline/candidate 导出源码，不使用日常安装。

baseline 源码清单 SHA-256 为 `3a311e1d7926406100905d96b9e0fdaf2ba2e8ce152707298437c8e9467924f1`，candidate-2 为 `69b2116156f46f47294978e39297056268b80c150592c4a31beb84999a5e58a8`。解释器为 Python 3.11.13，SQLite 3.47.1。

身份记录：[baseline](../../../.local/precheck-efficiency/260914-1826/baseline/identity.json)、[candidate](../../../.local/precheck-efficiency/260914-1826/candidate-2/identity.json)、[固定依赖](../../../.local/precheck-efficiency/260914-1826/dependencies.txt)。

## 初轮阶段记录（candidate-2）

| 阶段 | 当前证据 |
| --- | --- |
| S0 | 冻结恢复、源变化、Result 相关基线测试 [61 passed](../../../.local/precheck-efficiency/260914-1826/baseline-tests.log)；固定完整源码、依赖、diff 和状态。 |
| S1 | 连接复用、Run、编排定向 [44 passed](../../../.local/precheck-efficiency/260914-1826/s1-tests.log)；timeout 隔离、嵌套借用、线程隔离、回滚及 observe 快照释放。 |
| S2 | Source/Work/Artifact 批量与故障 [36 passed](../../../.local/precheck-efficiency/260914-1826/s2-batch-faults.log)；追加 Artifact 进度/失效传播后 [16 passed](../../../.local/precheck-efficiency/260914-1826/s2-artifact-progress.log)；来源证明进程退出检查集合 [11 passed](../../../.local/precheck-efficiency/260914-1826/s2-process-exit.log)。 |
| S3 | 组装及静态图执行边界 [51 passed](../../../.local/precheck-efficiency/260914-1826/s3-boundaries.log)；冷/暖、共享解码、逐项重新验源、协作停止、未知异常及小集合四 worker 资源检查。 |
| S4 | 验证器/相关集成 [221 passed](../../../.local/precheck-efficiency/260914-1826/s4-validator-targeted.log)；最终隔离 wheel 默认套件 1495 passed, 17 deselected；scale 2 passed；Ruff、artifact-only、distribution、CLI/MCP 均通过。 |
| S5 | 20 份正式成本样本及 2 份独立诊断完成，所有对照完整语义一致；8192 三对连续唤醒重测通过。时间/CPU 改善，4096 RSS 不退化未通过。 |

首次源码默认套件为 1483 passed / 8 failed / 17 deselected：4 项因沙箱禁止 `127.0.0.1` 监听，4 项因 `.venv` 旧版本元数据与当前资源不一致。没有修改产品/契约迁就这些失败；确切 wheel 的隔离环境和允许回环夹具的完整复验通过。首次定向回归发现跨 Dataset 错误被较泛的附属错误提前替代，已在原校验位置修正，最终完整回归覆盖。曾误用不存在的 `tests/test_rendition.py`，该命令未执行测试，后续使用实际入口完成验证。

## 实现责任

- `_sqlite_scope` 与 `_run_sqlite` 按线程、数据库和 timeout 复用空闲连接，借用结束回滚剩余事务；协调调用和 worker 各自持有 scope。
- `source_validity` 批读来源、逐 occurrence 观察并在短事务重新检查状态、修订和 stat，再记录证明。
- `_work_sqlite` 共用单项/批量身份、依赖、重试策略与附属规则，事务内复用有限查询结果；批读完整 Work 和依赖。
- `_artifact_sqlite` 保有文件核验、失效传播及核验后附属责任。一个调用内按 Artifact 去重，竞争项最多重验一次，未知错误回滚当前批。
- `rendition` / `_orchestrator` 接入最多 32 来源的正常调度批，按并行度和内存缩小；缺口回到原逐来源执行，普通/高清共享懒解码。
- `_result_assembly` / `_result_work_projection` 分块读取所选 rendition，释放读取后再核验写回；封存分块校验来源和材料，最终 pin 仍在原注册事务内完整核验。
- `runtime/resources` 与 `_result_sqlite` 按现有根验证器生命周期、每线程复用 Observation 子定义；不缓存数据有效结论。

首个候选在 4096 项三轮测量中出现明显 RSS 增长。小型生命周期反例证明：`_result_sqlite.py` 中的 lineage 与 `_sensitivity_values.py` 共享敏感性输入校验的递归闭包，在草稿返回后仍持有 Source/Observation 图，直至循环 GC。改为同模块私有递归函数，保留逐边、来源、维度和循环检查，并测试关闭循环 GC 时立即释放整个数据图。这属于原封存/验证责任内的生命周期修正，不通过强制 GC 改测量数字。修正后重建 candidate-2、重做 S4 和全部最终成本对照；[candidate-1 原值](metrics/candidate-1.json)及工作区全部保留。candidate-1 未继续跑 8192；其数值不混入最终结论。

没有新增表、schema、公共参数、缓存服务或持久批次，也没有修改 SQLite journal/synchronous。公共契约文件和既有 Result 字节未修改。

## 测量配方

[run.py](run.py) 通过 `RuntimeHost.call_tool` 的公共 Run/Read 接口执行；没有网络 API endpoint。`matrix.py` 管理测试器专用路径，先用 baseline 建立模板，每次在 Host/SQLite 进程退出后完整归档工作区，然后只恢复其有 ownership marker 的同址 workspace。源目录始终原位；不硬链接数据库、不改旧 Result locator。异址归档必须恢复到记录的专用原位置才能重新验证其绝对材料位置。

正式命令模板（仓库根目录）：

```sh
rtk proxy caffeinate -i .local/precheck-efficiency/260914-1826/candidate-2/venv/bin/python \
  eval/sessions/260914-1826-precheck-efficiency/matrix.py \
  --root .local/precheck-efficiency/260914-1826/final-cost \
  --output-root .local/precheck-efficiency/260914-1826/final-cost-awake-clean \
  --reuse-templates \
  --baseline .local/precheck-efficiency/260914-1826/baseline/source \
  --candidate .local/precheck-efficiency/260914-1826/candidate-2/source \
  --python .local/precheck-efficiency/260914-1826/candidate-2/venv/bin/python \
  --case warm-8192
```

case 依次为 `varied`、`local`、`diagnostic`、`warm-4096`、`warm-8192`，分别串行启动。最终轮使用 candidate-2 路径，并增加 `--output-root .local/precheck-efficiency/260914-1826/final-cost-candidate-2`；已有前四类模板增加 `--reuse-templates`，8192 首次建模板。它们继续恢复原有专用 slot 的同址 workspace，不改变封存 locator。所有已执行 runner 版本按内容摘要保存在 ignored `recipes/`；逐样本记录其实际摘要。不可在已有 case 目录直接重跑；脚本拒绝覆盖证据。8 项预演和失败配方记录在 `recipe-check*`，不计正式收益。局部样本首次后置审计错误地断言必须只有 4 次解码；冻结初选在 T 之外另增加 2 个必要输入，实际基线为 6 次。修正为逐路径核对 T 的 4 个真实缺口、禁止重复解码既有材料，并用 `--case local --resume-after-audit-fix` 在同一原位模板重做一次完整对照；首次样本工作区和日志保留。两版本修正样本均为同样 6 次解码、14 个新增 attempt（12 个图像 Work + 2 个压缩 Work）。预演修正了解释器 symlink 解析导致丢失 venv，以及冷启动首次生成 attachment/reuse_domain 身份的比较方式。

控制配方固定为 1 worker、max_pending=2、executor 内存预算 512 MiB、compression target=2，image_renditions 启用；metadata、GPX、video、bundles、embedding、sensitivity 和远端 provider 关闭。来源检查沿用 `candidate-sha256-full-or-3x4k-v1`。除局部准备外，既有定向准备配置列入全部来源；两版本配置完全相同。这些关闭项仅用于本次隔离成本配方，不是产品默认值变更。

正式 Run 计时包含 start、自动范围确认、执行、封存、worker 完整 Read 和 0.1 秒 status 首次观察 completed。prior Read、恢复/归档和后置全部材料/成员审计分开计时。RSS 每 20ms 采样，并报告 OS 累计高水位上下界；OS cache 未控制。模型和远端关闭，实际 producer 入口计数必须为零。独立诊断才启用逐 SQL trace 和子验证器构造计数。

全量比较保留所有 Source occurrence、Evidence、Observation、关系、Profile、直接对应和材料字节。仅对应新 Run/Result/Work 引用、冷启动确切源位置上的新 attachment/reuse_domain 引用，以及 `source_content_verification` 的真实观察时间和发布时刻。Work 由完整依赖描述对应，关系端点使用同一映射；相同内容的不同路径不合并。封存对象集合以规范顺序比较，另外保留 entry_evidence 顺序。旧 Result 原字节不作归一化，必须摘要完全不变。

## 正确性与安全证据

以下行为均有运行证据；测试属于上述已完成套件，不将相互重叠的定向集合累加为一个测试总数。

| 保证 | 实际验证及证据位置 |
| --- | --- |
| 历史成功 Work 不提前计入复用 | `test_reuse_attaches_only_after_verification_and_rechecks_work`、`test_public_progress_does_not_count_unverified_reuse` 在材料核验中观察公共进度，并在资格变化后检查返回状态；见 [Artifact 测试](../../../tests/test_artifact.py)。 |
| 单项/批量共用语义与碰撞规则 | [Work 测试](../../../tests/test_work.py)核对批内重复 semantic key、descriptor/retry policy 冲突、输入顺序及失败原子性；[Source 测试](../../../tests/test_source_validity.py)核对不同 occurrence 和提交前变更。 |
| 回滚当前未提交批，保留既有提交 | `test_process_exit_rolls_back_open_proof_batch_and_keeps_prior_commit` 实际终止子进程；Artifact 的异常失效/附属批回滚；`test_rendition_batch_checks_each_execution_and_retains_committed_prefix` 验证来源变更、协作停止与异常后的已提交前缀。 |
| 来源只读与逐项责任 | 每份正式样本前后比较所有源文件 SHA-256、inode、大小和 mtime；零模型/provider 调用。静态图批次执行前重新验源，普通/高清共享一次解码；已知单项失败保持局部责任。 |
| 资源与线程隔离 | [连接测试](../../../tests/test_precheck_sqlite_scope.py)覆盖 timeout、嵌套借用、心跳线程、事务回滚和观察快照释放；[编排测试](../../../tests/test_precheck_orchestration.py)覆盖小批四 worker 资源声明和实际 1/3 worker 交错输出一致。 |
| 完整输出、精确成员、直接对应 | 每份正式样本保存完整 `normalized.json`、`public-trace.jsonl` 和 `metrics.json`；解析全量 Source scope、逐源 expand、全部 Evidence review 分页、无重复游标、membership identity、Profile scope 与逐路径直接对应。成对全量语义摘要一致才生成 `verified.json`。 |
| 封存与发布重试 | [Result 测试](../../../tests/test_precheck_result.py)覆盖 bytes 发布后、注册前故障和最终 pin 的 Work/材料/来源复核；[编排测试](../../../tests/test_precheck_orchestration.py)覆盖注册后、Run 完成前中断并恢复到唯一 Result。不同语义重试、损坏及磁盘写入失败均不能伪报成功。 |
| 旧 Result 留存与公开入口 | 每份暖样本核对旧 Result 原字节摘要、再次公开 Read、独立新 Result 数量；[隔离 CLI/MCP 日志](../../../.local/precheck-efficiency/260914-1826/candidate-2/cli-mcp.log)包含旧 Result/Plan Work 读取、重启回放和缺失/损坏准备材料及来源变化的真实失败状态；[组合测试](../../../tests/test_run_composition.py)另覆盖维护后已发布材料及旧 Result 读取。 |

candidate-2 wheel 的日志：[完整回归](../../../.local/precheck-efficiency/260914-1826/candidate-2/full-tests.log)、[规模检查](../../../.local/precheck-efficiency/260914-1826/candidate-2/scale.log)、[分发检查](../../../.local/precheck-efficiency/260914-1826/candidate-2/distribution.log)、[两项最终边界检查](../../../.local/precheck-efficiency/260914-1826/candidate-2/final-boundary-tests.log)。完整回归 1495 passed / 17 deselected；规模 2 passed（[100000 成员精确分页](../../../tests/scale/test_preparation_scope.py)与 [500→3→200 多 Result](../../../tests/scale/test_multiple_results.py)），另两项定向检查 2 passed。未运行需要外部环境或真实模型的其余被筛除场景，不将其算作通过。

## 8192 重测与废弃尝试

首次 8192 模板和首个暖基线经历合盖/维护休眠。`pmset` 日志与公开进度 UTC 时间均保留；`perf_counter` 没有计入系统睡眠，不能仅从它的秒数推断这份样本没有中断。用户于 22:08 确认新的连续唤醒窗口并要求重测，因此此前 8192 尝试全部不进入最终对照，改在原位模板上重做三对样本，输出到 `final-cost-awake-clean`。512/4096 最终样本的时间区间无上述休眠事件，继续保留。

停止旧任务时，进程检查先被沙箱拦下，随后发生了一次错误的重启顺序，新的模板恢复与旧候选的后置审计短暂重叠。该次新启动已停止并废弃。旧 `candidate-warm-2` 尚未完成审计，未能在恢复前完整归档；其已有日志保留，workspace archive 标记不可信，绝不作为对应 Run 的完整证据。此前已完成样本和关闭保存的暖模板未改变。之后在获得进程检查权限后确认所有测量 driver/worker 退出，再校验模板 SQLite 完整性、1 份 Result、16384 份成功 rendition Work、2 个 Artifact 及封存摘要，才开始干净重测。

新的 `caffeinate -i` 只在测量进程存续期间避免空闲休眠，不修改全局电源配置，也不阻止用户主动合盖。最终汇总只使用干净重测的六份 8192 样本。两项补充边界复验在非性能样本的模板构造期间完成（1.89 秒）：真实 1/3 worker 交错执行保持像素、Work 语义和成员一致；退出子进程使用与父进程相同的隔离包。最终默认套件为 1495 passed，另外这两项定向复验通过；不把它们写成一次未实际运行的 1496 项全量命令。

最终干净重测区间为 2026-09-14 22:13:04–23:31:49（Asia/Shanghai，包含审计）。[最终电源日志](../../../.local/precheck-efficiency/260914-1826/power-events-final.log)显示该区间无 Sleep/DarkWake/Wake 转换；[逐样本核对](../../../.local/precheck-efficiency/260914-1826/final-sample-verification.json)还确认最终采用的全部 20 份成本样本和 2 份诊断均无休眠重叠、成功退出且有工作区归档。六份 8192 的 [verified.json](../../../.local/precheck-efficiency/260914-1826/final-cost-awake-clean/samples/warm-8192/verified.json)确认三对完整语义一致。

## candidate-2 成本、限制与初轮结论

candidate-2 的 S0–S5 分阶段检查、确切 wheel 验证和规定成本矩阵已执行完毕。当轮已执行的正确性检查通过，后续复核发现的 P1/P2 暴露了反例覆盖缺口，现已单独补修；**时间与 CPU 收益清晰，但 4096 项 RSS 显著上升，资源不退化未通过，不能将候选描述为无条件的优化成功。** 按设计停止本轮，不追加调优、安装或发布。

全部原值、中位数、范围、CPU user/system 分项、RSS 上下界、来源/旧 Result/完整输出摘要和样本路径见 [metrics/summary.json](metrics/summary.json)。共有 20 份正式成本样本及 2 份独立 SQL 诊断样本；诊断计时不进入下表。下表“减少”统一为 `(baseline-candidate)/baseline`，负值表示增加。512 场景每版本仅一轮，不据此证明稳定幅度；4096/8192 每版本三轮，表中为中位数。

### Run 与 CPU

| 场景 | 每版本轮数 | 基线 Run 秒 | 候选 Run 秒 | Run 减少 | CPU 秒：基线 → 候选 | CPU 减少 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 512 首次准备（内容有差异） | 1 | 19.965 | 13.661 | 31.6% | 10.411 → 7.145 | 31.4% |
| 512 显式暖复用（1024 产物） | 1 | 12.767 | 5.103 | 60.0% | 6.517 → 2.560 | 60.7% |
| 512 普通发现暖复用 | 1 | 13.255 | 5.464 | 58.8% | 6.548 → 2.551 | 61.0% |
| 512 局部准备混合命中 | 1 | 3.470 | 1.662 | 52.1% | 2.265 → 1.178 | 48.0% |
| 4096 暖复用 | 3 | 96.829 | 27.296 | 71.8% | 67.836 → 27.101 | 60.0% |
| 8192 暖复用（连续唤醒重测） | 3 | 288.308 | 84.503 | 70.7% | 218.119 → 90.635 | 58.4% |

三轮逐样本原值（对应各版本第 1、2、3 轮；交替运行顺序保存在 driver 记录中）：

| 规模/版本 | Run 秒 | CPU 秒 | RSS 峰值 MiB |
| --- | --- | --- | --- |
| 4096 / baseline | 101.331, 96.793, 96.829 | 69.581, 67.836, 67.064 | 341.422, 341.562, 337.406 |
| 4096 / candidate | 27.325, 27.296, 26.275 | 27.151, 27.101, 25.979 | 448.031, 352.844, 400.234 |
| 8192 / baseline | 276.048, 290.361, 288.308 | 211.693, 218.119, 223.597 | 609.391, 611.594, 609.766 |
| 8192 / candidate | 89.136, 84.503, 82.383 | 94.301, 90.635, 87.400 | 610.391, 610.312, 610.328 |

### RSS 与磁盘

| 场景 | 基线 RSS 中位 [范围] MiB | 候选 RSS 中位 [范围] MiB | RSS 减少 |
| --- | ---: | ---: | ---: |
| 512 首次准备（内容有差异） | 102.78 [102.78, 102.78] | 101.34 [101.34, 101.34] | 1.40% |
| 512 显式暖复用（1024 产物） | 114.00 [114.00, 114.00] | 110.58 [110.58, 110.58] | 3.00% |
| 512 普通发现暖复用 | 115.94 [115.94, 115.94] | 115.33 [115.33, 115.33] | 0.53% |
| 512 局部准备混合命中 | 91.16 [91.16, 91.16] | 93.55 [93.55, 93.55] | -2.62% |
| 4096 暖复用 | 341.42 [337.41, 341.56] | 400.23 [352.84, 448.03] | -17.23% |
| 8192 暖复用（连续唤醒重测） | 609.77 [609.39, 611.59] | 610.33 [610.31, 610.39] | -0.09% |

4096 项候选三轮 RSS 为 352.84–448.03 MiB，均高于基线 337.41–341.56 MiB；中位数增加 58.81 MiB（17.2%）。8192 项中位数仅增加 0.56 MiB（0.09%），范围重叠，不认为该规模证明了内存改善。局部准备单轮增加 2.39 MiB（2.6%）。生命周期闭包缺陷已修复且重新验证，剩余 RSS 增长的归因尚未证明；不能宣称已解决。固定的 512 MiB 是 executor 资源预算，不是整个 Python 进程 RSS 的硬上限。

所有正式样本 `memory.peak_exact=true`：根据 Run 区间采样和 OS 高水位推导的峰值上下界相同。仍保留开始 RSS、历史高水位、20ms 采样及增量；不是以进程退出后的总高水位替代 Run 峰值。OS 文件缓存、后台负载及 Python 分配器行为未严格控制。

磁盘表以实际字节计；大规模为三轮中位数。各场景的 Result 和 Artifact 大小 A/B 完全相同，二者减少率均为 0%。Workspace 大小包含当次保留的数据库与历史内容，不包含外置审计日志和归档副本。

| 场景 | Result 字节（两版相同） | Artifact 字节（两版相同） | Workspace 字节：基线 → 候选 | Workspace 减少 |
| --- | ---: | ---: | ---: | ---: |
| 512 首次准备（内容有差异） | 4,559,216 | 300,195 | 14,256,245 → 14,329,973 | -0.517% |
| 512 显式暖复用（1024 产物） | 4,816,421 | 300,195 | 21,124,762 → 21,071,514 | 0.252% |
| 512 普通发现暖复用 | 4,559,216 | 300,195 | 20,285,925 → 20,265,445 | 0.101% |
| 512 局部准备混合命中 | 2,563,437 | 576 | 8,891,543 → 8,879,255 | 0.138% |
| 4096 暖复用 | 38,493,219 | 576 | 151,710,774 → 151,710,774 | 0.000% |
| 8192 暖复用（连续唤醒重测） | 76,979,235 | 576 | 303,213,622 → 303,225,910 | -0.004% |

8192 项基线 Workspace 三轮为 303,152,182 / 303,213,622 / 303,213,622 字节，候选三轮均为 303,225,910 字节；其余各组三轮磁盘量无组内波动。数据库页布局和控制状态写入会使 Workspace 字节略有差异，不等同于输出内容差异。

### 完整输出与实际工作量

| 场景 | Source | Evidence | 关系 | 入口 | 物理 Artifact | 新 attempt / 复用 Work |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 512 首次准备（内容有差异） | 512 | 1024 | 5118 | 2 | 1024 | 1026 / 0 |
| 512 显式暖复用（1024 产物） | 512 | 1024 | 5118 | 2 | 1024 | 0 / 1026 |
| 512 普通发现暖复用 | 512 | 1024 | 5118 | 2 | 1024 | 0 / 1026 |
| 512 局部准备混合命中 | 512 | 268 | 1710 | 8 | 2 | 14 / 256 |
| 4096 暖复用 | 4096 | 8192 | 40958 | 2 | 2 | 0 / 8194 |
| 8192 暖复用（连续唤醒重测） | 8192 | 16384 | 81918 | 2 | 2 | 0 / 16386 |

这些计数在对应 A/B 中一致。非去重夹具为 512 张不同的 32×24 JPEG，实际产生 1024 个普通/高清 Artifact；首次准备解码 512 次。普通发现和显式暖复用均零解码、零新增 attempt。主矩阵为相同内容的 8×8 JPEG，保留全部路径 occurrence，虽然共享 2 个物理 Artifact，仍保留 8192/16384 份 Evidence 及逐源关系。局部模板原有 128 项准备，T 含 4 项未准备和 2 项已准备，既有初选再增加 2 项必要输入；两版均仅解码 6 个新的不同来源，未重复解码已有来源，产生 14 个新 attempt。

### 独立阶段和公开读取

以下为每份样本主路径的互斥区间中位数（秒），嵌套 span 只归入最内层区间，worker span 不与外层 wall 重复相加。各阶段分别取中位数，其和不能代替整体中位数。

| 阶段 | 4096 基线 | 4096 候选 | 8192 基线 | 8192 候选 |
| --- | ---: | ---: | ---: | ---: |
| 受理 | 0.165 | 0.162 | 0.278 | 0.291 |
| 来源快照 | 5.076 | 4.824 | 23.447 | 23.394 |
| 静态图准备 | 52.147 | 5.778 | 149.234 | 21.846 |
| 压缩 | 0.803 | 0.674 | 1.791 | 1.835 |
| 组装 | 10.326 | 1.816 | 34.160 | 6.309 |
| 封存 | 19.608 | 6.116 | 58.521 | 14.605 |
| worker 完整 Read 验证 | 4.632 | 4.627 | 9.289 | 9.773 |
| 其余等待/控制/收尾 | 4.173 | 3.113 | 12.560 | 5.914 |

收益主要落在准备、组装和封存。worker 完整 Read 已包含在 Run 计时中，4096 的该段约 4.63 秒，8192 约 9–10 秒，没有证明显著改善。完成后同进程再发一次公开 review：4096 中位 0.0939 → 0.0960 秒（增加 2.3%），8192 中位 0.1371 → 0.1444 秒（增加 5.3%），候选最后一轮为 0.2827 秒；这不是冷进程首次加载的认证。Run 加这次 review 的中位为 96.922 → 27.394 秒和 288.445 → 84.642 秒。

全量后置审计另计：4096 基线 63.86–67.22 秒、候选 63.67–64.53 秒；8192 基线 583.49–592.27 秒、候选 582.75–602.81 秒。8192 全量公开对应与读取仍很昂贵，本轮未宣称改善这一成本。模板恢复、归档耗时另存 `restores.jsonl` 和各样本 `invocation.json`，均不混入 Run。

### 工程机制接通诊断

内容有差异的 512 项暖样本启用独立 SQL/构造计数；其耗时不进入正式统计。

| 计数 | 基线 | 候选 | 减少 |
| --- | ---: | ---: | ---: |
| connect | 2384 | 152 | 93.6% |
| SELECT | 45030 | 14198 | 68.5% |
| COMMIT | 6186 | 114 | 98.2% |
| preparation_worker COMMIT | 3072 | 32 | 99.0% |
| assembly COMMIT | 1024 | 16 | 98.4% |
| seal COMMIT | 2049 | 25 | 98.8% |
| Observation 子验证器构造 | 3594 | 11 | 99.7% |

全局计数包括受 status 次数影响的控制读取；按 producer、组装、封存列出的提交数才用于确认各项优化接通。DELETE journal、synchronous=2 保持不变。

### 验收状态与停止边界

- 已完成：限定实现、当前公共契约下的正确性回归、完整输出/来源只读/恢复/发布重试/旧 Result 留存检查，以及全部规定成本矩阵。
- 未通过：4096 项 RSS 不退化。8192 项内存变化很小，不能抵消 4096 的实际增加；最终报告保留这项资源风险。
- 未认证：真实大媒体、视频、外置盘、其他文件系统、真实模型推理和远端 provider 吞吐。512 场景单轮，主矩阵仅本机固定控制配方，不能跨规模或设备外推。
- 建议：保留代码与证据作为待验收候选，不自动替换日常版本。若峰值内存必须不增加，当前候选不满足该条件，应保留基线；是否取舍时间收益与内存代价由后续验收决定。本轮停止，不启动新一轮优化或发布。

2026-09-14 轻量检查：Ruff（`src tests` 与本 session 脚本）、`git diff --check`、报告与索引相对链接、原始证据 Git ignore 检查均通过；[检查记录](../../../.local/precheck-efficiency/260914-1826/final-checks.json)。没有新增公共契约文件改动，未提交 Git commit。


## 2026-09-15 复核补修（candidate-3）

用户复核发现两项实现缺陷后，授权仅补修这两项并做针对性复验；不重跑大规模矩阵，不以消除 RSS 数字为由扩展调优。当前源码为 candidate-3；candidate-2 的 wheel、全部样本与原始测量保持原样。

### 变更与反例

| 问题 | 局部修正 | 实际验证 |
| --- | --- | --- |
| P1：较早来源处理触发共享 Artifact 失效后，后续来源仍消费批首的成功 Work 对象 | [rendition.py](../../../src/mediasense/precheck/rendition.py) 在消费候选前用现有 `get_work_many(..., run_id=...)` 读取当前附属 Work；只有当前仍成功才返回复用。失效则回到原逐来源证明、认领和准备路径，普通/高清继续共享懒解码。批首尚无成功材料的项仍走原准备路径。 | [跨文件失效反例](../../../tests/test_precheck_result.py)覆盖仅普通、仅高清、两者同时失效。A 尚未准备，B/C 已准备；A 的处理通过真实 ArtifactStore 触发 B 材料失效，随后 A 修复同内容材料。B 必须使用新的有效 Work，原 Work 历史仍为 invalidated；未受影响 Profile 和 C 继续复用。检查返回状态与库中状态一致、A/B 各一次解码、来源字节不变，并实际完成下游压缩及完整成员检查。 |
| P2：`status NOT IN` 无法使用现有部分索引 | [_work_sqlite.py](../../../src/mediasense/precheck/_work_sqlite.py) 恢复 `status <> ? AND status <> ?`，与已有 `work_records_current_semantic_key` 索引谓词一致；不新增索引或表。 | [查询计划反例](../../../tests/test_work.py)截获实际 Store SQL 和原绑定参数，在 SQLite 3.47.1 上执行 `EXPLAIN QUERY PLAN`。单项与 32 项调用都必须 `SEARCH work_records USING INDEX work_records_current_semantic_key`，不能 `SCAN work_records`，且返回相同 Work。 |

补修前运行新增反例：[5 failed](../../../.local/precheck-efficiency/260914-1826/review-fixes-260915/before.log)，分别复现三种 `succeeded`/`invalidated` 状态不一致与两种全表扫描；修正后 [5 passed](../../../.local/precheck-efficiency/260914-1826/review-fixes-260915/after.log)。这两项属于本范围内的实现缺陷，已修复；未将它们解释成契约例外。

### 新候选身份与复验范围

candidate-3 wheel SHA-256：`9c14ca0ab2a9c008f459d7440362a68594c7b4bdac92086d55d6a5e8280a4eac`。源码清单 SHA-256：`2aacd5503c3bff7315e76b0917e1c745aa4c801fe66a2df16240e6a0fce120c1`。保留 [identity.json](../../../.local/precheck-efficiency/260914-1826/candidate-3/identity.json)、源码快照、完整 diff 和 wheel；[相对 candidate-2 的产品差异](../../../.local/precheck-efficiency/260914-1826/review-fixes-260915/product.diff)仅涉及上述两个模块。

新建本地隔离 venv，安装确切 wheel，并只链接 candidate-2 的既有依赖，验证时关闭 bytecode 写入；Python 3.11.13、SQLite 3.47.1 及依赖版本全部一致。未修改旧安装或日常安装。默认 uv 构建先因用户缓存目录权限失败，随后读取本机已有 Hatchling 1.30.1 及构建依赖离线构建；两份构建日志均保留，没有下载或升级。

- 新 wheel [artifact-only 核对](../../../.local/precheck-efficiency/260914-1826/review-fixes-260915/artifact.log)通过；[108 个产品文件](../../../.local/precheck-efficiency/260914-1826/review-fixes-260915/content-check.json)在当前源码、快照、wheel、隔离安装中一致。
- 隔离安装的[针对性回归](../../../.local/precheck-efficiency/260914-1826/review-fixes-260915/installed-targeted.log)：**120 passed in 40.73s**。覆盖 Work、Artifact、Result、SQLite scope、SourceValidity、编排、压缩及 Run composition 八个测试文件，包括新增反例、来源变化、回滚与恢复、发布重试、旧 Result 留存和实际 1/3 worker 交错。
- 新 wheel 的[CLI/MCP 组合验证](../../../.local/precheck-efficiency/260914-1826/review-fixes-260915/cli-mcp.log)通过：普通/局部 Run、完整 Read/resolve、旧 Result/Plan Work、重启回放、准备材料缺失/损坏和来源变化故障；provider 请求为零。
- Ruff、差异空白检查和文档链接检查通过。紧凑记录见 [review-fixes.json](metrics/review-fixes.json)。

针对性回归命令（仓库根目录，`pythonpath=` 防止加载工作树产品包）：

```sh
rtk proxy env PYTHONPATH= PYTHONDONTWRITEBYTECODE=1 \
  .local/precheck-efficiency/260914-1826/candidate-3/venv/bin/python \
  -m pytest -o pythonpath= -q \
  tests/test_work.py tests/test_artifact.py tests/test_precheck_result.py \
  tests/test_precheck_sqlite_scope.py tests/test_source_validity.py \
  tests/test_precheck_orchestration.py tests/test_compression.py tests/test_run_composition.py
```

本次未重跑默认全量 1495 项、scale 或大规模性能矩阵，不声称它们已在 candidate-3 上通过。原 4096/8192 提速和 17.2% RSS 增加继续只归属 candidate-2。P1 增加当前资格读取，P2 恢复索引，净成本变化未测量，不估算其提速百分比。

P1/P2 补修完成；内存取舍未被接受，整体验收不自动转为通过。当前候选保留为待验收状态，本轮停止，无发布、日常安装或后续调优。
