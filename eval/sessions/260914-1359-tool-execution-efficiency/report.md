---
title: "MediaSense 工具执行效率调研：暖 Run、缓存复用与局部准备"
service_version: "0.11.0 candidate-2，b79be81 加验收补修快照"
date: 2026-09-14
environment: "本机 macOS / APFS，CPython 3.11.13，SQLite 3.47.1"
model_id: "none；全部模型与远端服务关闭"
dataset_version: "本轮隔离 512 项 8×8 JPEG；复用既有 4096/8192 成本证据"
purpose: "定位履行现有工具职责的内部成本，提出保持契约与安全保证的优化方案"
baseline_ref: ".local/acceptance-releases/260914-run-composition-repair/candidate-2"
status: review
timezone: "Asia/Shanghai"
---

# 调研结论

后续状态：用户已授权编写具体工程设计，由其他Agent后续实施。当前实施范围与S0–S5验证标准见[工程设计](../../../docs/design/design-260914-1450-precheck-execution-efficiency.md)。该设计采用限定手段完成后统一实测的方式，不要求逐阶段收益达标；本报告历史建议中的25%/40%目标不作为实施验收门槛。调查事实与原始样本保持不变。

优先优化 **小事务过多、逐项控制查询与连接建立、重复读取和校验写回**。暖缓存已经省去了解码，但每张图片仍大致触发 **12 次提交**：准备时 6 次、组装时 2 次、封存时 4 次。Work、来源和产物的检查义务需要保留；按这一粒度访问数据库并非契约要求。

不建议先加通用缓存层、服务或协调中心。现有 Run、Work、Artifact 和 Result 的责任足够承载优化。缓存有效性继续由 Tool 内部判断，Agent 不读取私有表、不推断命中、不参与失效决策。

本轮仅增加调查报告、紧凑指标和 ignored 临时脚本/数据，没有修改产品源码、公共契约、安装或用户状态。保留主线程全部并行改动。调查已停止，以下实施方案等待选择，不代表实施授权或性能验收。

## 证据范围与方法

权威依据为 [PreCheck 基础模型](../../../docs/model/model-260913-1408-precheck-basics.md)、[Foundation](../../../docs/design/design-260823-1918-mediasense-foundation.md)、[复用能力架构](../../../docs/design/design-260830-1527-reusable-capability-architecture.md)、[压缩模型](../../../docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)、当前 [Run](../../../docs/spec/contract/precheck-run/index.md) / [Read](../../../docs/spec/contract/precheck-read/index.md) 契约，以及任务包 [design](../../../openspec/changes/simplify-precheck-run-composition/design.md) / [acceptance](../../../openspec/changes/simplify-precheck-run-composition/acceptance.md)。尤其 Run 已明确允许共享批次、进程和连接，不要求逐 Work 提交。

兼容政策沿用本轮明确边界：现有公开形状、语义、准备义务和返回内容不变；旧 Result 字节、材料及引用留存。仓库零公开 API BC 政策不构成本轮改变契约的授权。内部索引、批量大小、连接和调度方式可替换；不增加版本路由或双写权威。

本轮采用已固定的 [candidate-2 源码身份](../../../.local/acceptance-releases/260914-run-composition-repair/candidate-2/source-files.json)，基点 `b79be81` 加保留差异，对应 wheel SHA-256 `8b52d48704de8af6621c7b40689c9a830221b7fa03ef02b5bf5f5a2e6fc0deb2`。使用其既有隔离解释器，没有安装新包。后文源码链接用于导航，精确证据以该快照为准。

- 既有大规模证据：修复目录 [cost-summary.json](../../../.local/acceptance-releases/260914-run-composition-repair/cost-summary.json)、[8192 单轮](../../../.local/acceptance-releases/260914-run-composition-repair/cost-candidate-2-8192-1/metrics.json)、[局部参数样本](../../../.local/acceptance-releases/260914-run-composition-repair/local-candidate-2-r2/metrics.json)。历史 r6 等仅用于解释测量边界，不重跑旧基线。
- 新数据全部位于 [隔离目录](../../../.local/tool-execution-efficiency/260914-1359/)。先做 128 项准备，随后主要使用 512 项固定暖模板；单个 worker、两个 pending、512 MiB executor 预算、完整普通/高清图义务、两个入口。新样本串行运行；没有重跑 4096/8192 Run，没有启动并行负载。
- 每个暖样本为独立进程、独立工作区克隆，先读 prior Result，随后走真实 `RuntimeHost.call_tool` → Run → worker → Result → Read。API 是进程内公共 Tool 入口，不是新增网络端点；本轮未重测 CLI/MCP 安装传输。
- 八个 512 项暖样本均完整交代 512 个来源、两个入口，零新增解码；源哈希不变，保留 prior Result 并新增一份。第一次 128 暖样本因执行环境下卷身份从 stable-volume 变为 session-local 被正确阻塞，失败日志保留，未修改身份检查或数据使它通过；它不进入性能样本。
- 计时分为轻量原阶段计时、原 SQL trace 计数、逐 SQL wall/thread CPU 诊断和 cProfile。逐 SQL/cProfile 结果用于归因，不冒充无插桩性能。原阶段计时的 20 ms RSS 采样仍保留；本轮没有完全零仪器的基线。
- 紧凑结果及脚本摘要见 [metrics/summary.json](metrics/summary.json)。原始 SQL、调用图、数据库、图片、日志及脚本均为 local-only、Git ignored。工作区克隆的旧绝对材料路径限制沿用原验收记录；新 Result 的材料读取成功，未宣称克隆实现了旧材料重定位。

## 一次真实暖 Run：时间在哪里

下表来自最后一次 512 项 SQL 分阶段诊断，总墙钟 **10.209 s**。取主执行路径上不重叠的区间，不把嵌套 Work 检查或并行线程时间重复相加。

| 主路径区间 | 秒 | 占墙钟 | 实际工作 |
| --- | ---: | ---: | --- |
| Run 接受、冻结（`_start`） | 0.050 | 0.5% | 当前请求和配置核对、冻结输入、持久创建 |
| 初始快照来源检查 | 0.275 | 2.7% | attachment、逐来源 stat/指纹、已有 accounting 批提交 |
| 图像准备阶段，全部缓存命中 | 5.295 | 51.9% | 逐文件调度、两侧状态查询、来源证明、Work 附属、产物核验及写回 |
| 最终压缩 | 0.095 | 0.9% | 获取已准备输入、依赖与分组 Work |
| Result 组装 | 0.983 | 9.6% | 读取来源/Work/关系，构造完整内容，再次检查产物 |
| SQLite Result 封存 | 2.271 | 22.2% | 结构/语义、来源和产物验证，编码、落盘、最终 pin 与注册 |
| 完整 Read 核验 | 0.582 | 5.7% | 新 Result 完整性与关系检查，之后才能 completed |
| 其余间隙 | 0.658 | 6.4% | Host 接受外层、阶段切换、收尾、发布前第二次 snapshot 检查、观察终态的延迟等 |

原先未覆盖的部分有了具体解释：`ensure_work` 只包住图像命中路径的一段。它不包含 `SourceValidityStore.prove`、`artifacts_for_work/verify`、调度前后 `_running`、连接建立、future 等待。发布前第二次 `snapshot_events` 也在原 `process_snapshot` 与 `SQLiteResultStore.seal` 两个计时器之外。主路径剩余 0.658 s 仍是联合余项，不为其中每个原因虚构精确秒数。

既有 8192 项单轮墙钟 291.051 s，原分项为 snapshot 26.247、Work lookup 25.620、assembly 37.402、sealing 56.540、Read 9.075 s。粗略相减约 136 s 是原仪器没有解释的残差，不能叫作“数据库时间”。新剖析证明缺少哪些大段，以及这些路径确实昂贵；**没有据此把 512 项占比直接套到 8192 项**。原 8192 时刻没有 CPU/锁等待轨迹，无法事后精确重建。

### CPU、文件 I/O、数据库与测量开销

最后一轮 wall 为 10.209 s，进程累计 CPU 为 **6.659 s**，其中 user/system 分别记录在指标中。CPU 是所有线程之和，因此 wall 减 CPU 不能严格作为整个进程的 I/O 等待时间。

| 证据 | 能判断什么 | 不能判断什么 |
| --- | --- | --- |
| SQL 调用合计线程 CPU 约 4.20 s；调用区间墙钟合计约 11.74 s | 数据库边界占据显著 CPU 与非 CPU 时间；跨线程调用有重叠 | 11.74 s 不能作为总 Run 占比，不能与主路径表相加 |
| 最后一轮约 6.2k 次提交；准备/组装/封存分别 3072/1024/2049 次 | 大量命中仍承担实际写事务；并非只读查询 | COMMIT 次数不等于 fsync 次数，也不等于锁等待次数 |
| 第一轮 SQL 诊断连接 2358 次，累计 wall 4.004 s、线程 CPU 0.243 s | 建立连接路径有明显停顿；控制读在 producer 复用连接范围之外 | 不能把全部差值归为打开文件，可能包含锁、调度及 GIL 重新获取 |
| 原生 cProfile 中 1024 次来源指纹累计约 0.168 s；3072 次产物 hash 约 0.113 s | 小图上直接内容读取/哈希不是数秒级主因；来源并非“零读取” | 不能外推大图、外置盘或冷 OS 缓存 |
| 新 Result 完整核验 0.582 s，执行线程 CPU 0.579 s | 该阶段在这个样本上主要是 CPU 工作 | 不能取消核验或用准备完成替代 Read 完整性 |
| SQLite 实库为 `journal_mode=delete`、`synchronous=FULL` | 正在使用 rollback journal；写提交和并发读存在可调查的竞争面 | attachment 的 WAL 探针成功不表示实库使用 WAL |

SQL 的 wall/thread CPU 是实际调用测量；非 CPU 部分没有系统级锁/磁盘追踪，无法进一步可靠拆成 fsync、文件锁、系统调度和 GIL 等待。macOS 本轮 `ru_inblock/ru_oublock` 为零，不把它解释成没有 I/O。Python 层观察到的 `fsync` 不涵盖 SQLite C 内部同步。数据库等待的精确分类是剩余未知，已不妨碍先减少重复事务与连接。

测量扰动对照保持相同模板、0.1 s status 周期，按 light→trace→trace→light 顺序串行：

| 模式 | 两次 wall s | 两次进程 CPU s |
| --- | --- | --- |
| 关闭逐 SQL trace；保留原阶段/RSS测量 | 10.085、9.906 | 6.074、5.866 |
| 原 trace 回调、SQL计数与锁 | 10.398、8.906 | 6.514、5.923 |

两组墙钟范围重叠，不能认证 trace 的固定增量或加速比例。trace 有额外 CPU 工作，尚不足以解释主耗时。单轮把轮询从 0.1 s 改为 1 s 得到 8.734 s / CPU 5.404 s，说明 status 负载值得单独评估；只有一次且终态观察延迟不同，不作为改善证明或产品默认调整建议。cProfile 样本为 13.021 s，开销明显，调用图用于定位而非绝对时间承诺。

## 一个文件的完整路径

取新夹具的 `00000.jpg`。它与其他 511 张内容相同，但仍是独立来源 occurrence。暖缓存已有 ordinary/high-resolution 两份 Work；全部 512 张合计只有两个物理 Artifact，这不合并 Source Item 或 Work 身份。

| 位置 | 实际读取 | 实际写入 | 必须保持的意义与当前可替换做法 |
| --- | --- | --- | --- |
| `start` | 可信 prior Result、完整 S/Profile、当前配置身份 | 新 Run、冻结输入和直接绑定 | 必须冻结原要求；不必在后续每次控制读重建完整配置 |
| `process_snapshot` | attachment、路径与源字节指纹 | `run_items` 等 accounting 事实；当前已按256项提交 | 必须发现确定源变化并区分不可用；这段已经有批量，不是逐文件提交的主要来源 |
| `_execute` | 提交任务前和任务开始前各读 Run state | 无逐文件状态变更 | 必须能响应控制；目前两次读取各自建立新连接，未复用 producer scope |
| ordinary 的 `prove` | working run + run item；源 stat；已有 proof | upsert `source_content_proofs` 与 observed_at，提交一次 | 必须校验当前版本和归属；无需每个 profile 单独实现整套查询/事务 |
| ordinary 的 `ensure_work` | Run readiness；版本/内容依赖；semantic key；Work/依赖 | `run_work_records` 附属、同事务写 progress_scope_changed；提交一次 | 必须附属到新 Run，保留碰撞/失效检查；同一源版本目前因两种依赖查询两遍 |
| ordinary 的 Artifact 命中 | 再读 Work 和全部依赖；读 Work→Artifact；读文件 hash/size | 写 integrity/last_verified_at，再读 Artifact；提交一次 | 必须验证产物可用；复用刚读取的 Work、批量写核验事实不改变责任 |
| high-resolution | 再经过上述三步 | 再三次提交 | 两种输出/语义依赖独立；来源元数据读取与事务不必完全重复 |
| 压缩输入 | 再读成功 Work、依赖、已有输出 | 两个分组 Work 的本次附属 | 必须按真实依赖计算/复用；已知 ID 不必反复构造完整 WorkRecord |
| 组装 | 读两份 Work、来源依赖与产物，建立完整 Evidence/关系 | 两次 Artifact 校验写回，各提交一次 | 保留所有自身属性、成员与派生来源；读取方式可以批量化 |
| 发布前快照复核 | 再核对 attachment、源 stat/指纹 | 本轮不重做 producer | 必须捕获准备期间变化；不能用起始证明越过该边界 |
| Result seal | 两轮来源 prove；两份 Evidence 产物核验；Work/依赖/关系检查 | 两次 proof + 两次 Artifact 写回；另有全 Result 注册事务 | 本文件约四次提交；最终 pin eligibility、材料身份与注册原子性必须保留 |
| Read 核验与完成 | 封存字节、摘要、引用、关系、准备绑定与材料证明 | 通过后写 Run completed | 不依赖私有 Work 补造 Result，不允许提前 completed；后续公开 Read 复用现有受信图仍校验适用身份 |

准备阶段这一个文件的 SQL 顺序已经实际记录在 [single_file_sql](../../../.local/tool-execution-efficiency/260914-1359/sql-phases-512/512-0/measurement/probe.json)：6 个 COMMIT、两次 proof、两次 Work 附属、两次 Artifact 校验。两种 profile 已共享一条 producer 连接，因此问题不是“完全没有连接复用”，而是复用范围没有覆盖高频 Run 控制读，且事务仍按单步提交。

全 Run 数量能交叉印证：512 项有 2048 次 `prove`、3072 次 Artifact `verify`、6150 次 `_get_work`。约 `12N` 次提交在 8192 上即 98304 次，加上阶段/控制等固定或轮询成本，与既有 98384 次记录相符。该吻合解释了事务结构，不把它当作时间复杂度证明。

## 瓶颈排序

| 优先级 | 判断 | 证据强度 |
| --- | --- | --- |
| 1 | 来源证明、命中附属及产物核验的细碎写事务 | **已确认。** 约12N提交，命中路径和封存都有显著耗时；保持 FULL 的独立事务对照支持批量收益 |
| 2 | 逐项调度伴随的控制查询、连接打开及与写入竞争 | **已确认路径和成本。** 图像准备占52%左右；两个线程各约1.84–1.85 s `_running` 包围时间，互相重叠。具体非CPU等待构成仍未分清 |
| 3 | 重复 Work/依赖/Artifact 读取与对象重建 | **已确认重复。** `_get_work`约12N，单文件 trace 显示刚读完又读取；批查询整体收益待实施验证 |
| 4 | Result/Observation 结构与语义验证 CPU | **已确认存在。** 完整Read约0.58 s，cProfile显示 jsonschema descend/evolve；精简验证器构造的收益仍待验证，不允许减少验证规则 |
| 5 | progress/status 的聚合扫描与观测干扰 | **已确认反复聚合，收益待验证。** 默认status执行当前Work分组、attempt存在性和效果统计；轮询对照仅一轮变化，不足以定量排序到前三 |
| 较低 | 索引缺失、压缩计算、图片解码、直接小文件 hash | 高频点查已命中索引；压缩约0.095 s；解码为零；hash累计很小。没有证据支持优先改这些 |

在原 8192 数据库上只读 `EXPLAIN QUERY PLAN`，Work ID、依赖、source revision、proof、Artifact 和 semantic key 均走已有索引，见 [查询计划](../../../.local/tool-execution-efficiency/260914-1359/query-plans-8192.json)。这不排除 status 聚合或长历史下需要覆盖索引，只说明不能把“71万 SELECT”直接等价为“缺索引”。

## 优化方案及正确性边界

下表工作量为单人粗估，包含定向测试，不含真实媒体和跨文件系统认证；收益互相重叠，不能相加。

| 顺序 | 方案与责任位置 | 收益依据与目标 | 风险 / 工作量 |
| --- | --- | --- | --- |
| P0-A | 在现有 SourceValidity/Work/Artifact Store 增加有界批量读写；先覆盖暖 rendition 的证明、附属及校验写回 | 准备阶段6N提交可降为按批的少数提交；初包争取全Run提交减少≥40%，保持每项事实和完整核验 | 中；3–5人日。真正难点是校验后并发失效、提交后进度和局部失败，而非 executemany 语法 |
| P0-B | 扩大现有线程内连接scope到协调循环、控制检查及批次；保持事务短、线程隔离 | 先保留逐项state检查，仅消除反复打开连接/解析schema；无需改变暂停行为 | 低至中；1–2人日。不得跨线程共用正在借出的连接、携带未结束事务或锁穿过外部执行 |
| P1-A | 按有界ID集合批读 Work、依赖、附属与Artifact；组装直接消费一次投影结果 | 消除N+1及重复对象；不取全Dataset历史，不为已知ID构造用不到的字段 | 中；2–4人日。批量读取仍须在一致快照里验证每个请求ID，缺项不能被JOIN悄悄过滤 |
| P1-B | 每次明确验证边界按唯一物理Artifact核验，再映射到全部Evidence；短寿命验证结果由现有Store内部持有 | 本夹具3072次hash对应2个文件；真实不去重媒体仍可消除同一产物跨引用重复。优先去重复写回，较后才复用hash结论 | 中至高；2–4人日。跨边界和并发改变的失效规则必须先落定；不是一个通用TTL缓存 |
| P2-A | 有界批次调度命中检查，保留每项身份/失败/控制检查；昂贵缺口继续走原资源准入 | 减少512个future及控制/结果封套；有效命中无需占用与真实解码相同生命周期的调度工作 | 中；2–3人日。不能凭未验证“可能命中”绕过资源限制，不能把批次伪装为一个公开Work |
| P2-B | 复用已编译Observation子验证器、优化确定性投影；减少status对无关能力的重复扫描 | 针对CPU与默认观察成本；现有schema编译已缓存，需处理的是子validator演化和重复遍历 | 中；2–3人日。检查规则、开放属性、错误与输出必须等价；暂不新增持久聚合表 |
| 条件项 | 评估 WAL、必要覆盖索引 | delete/FULL下并发读写停顿值得研究；当前点查索引齐全，先减少次数 | 中至高；独立存储验证。必须处理共享盘支持、checkpoint、sidecar备份/克隆及崩溃恢复；不改同步强度换速度 |

事务微对照使用相同 CPython/SQLite，在独立512行表上做完全相同的逐行读校验和更新，保持 delete/FULL：512次提交耗时0.316–0.466 s；32项一批、16次提交为0.0142–0.0146 s；128项一批、4次提交为0.0042–0.0046 s，最终行内容摘要相同。它支持“提交次数有直接成本”，**不是 MediaSense 的预计加速倍数，也未证明批量恢复正确**。

另在隔离实库只读512次同一Run state，新建连接为0.146–0.149 s，复用连接为0.0027–0.0032 s。它没有并发writer，远小于真实Run连接累计停顿，说明实际还有竞争/调度成分；不能用微基准比例推算整个Run。两项脚本与原值见 [micro.py](../../../.local/tool-execution-efficiency/260914-1359/micro.py) / [micro311.json](../../../.local/tool-execution-efficiency/260914-1359/micro311.json)。早先系统Python探索记录不用于以上数值。

### 每项优化必须怎样失效、恢复和重试

**批读/批写。** 保留每个Work的语义键、依赖、当前generation/lease、输出及失败。文件读取与模型执行在写事务外；提交时在短事务内重新核对Run状态、来源revision/reuse_domain、上游状态和产物资格，不能把较早SELECT当提交授权。写入附属关系与progress_scope_changed同事务提交，processed只统计已持久终结项。批内已知坏项逐项交代；未知异常回滚并显式失败。崩溃最多重验未提交批次，已提交Work保留；恢复仍使用原冻结要求，不能借当前默认配置补缺。同次发布沿用原确定Result身份，final pins与注册保持原子边界。

**连接与查询复用。** 有效期是同线程、同Database、当前operation/batch，作用仅为连接与语句复用；每次状态查询仍读取新持久事实，不把state值缓存。结束或异常清理未提交事务，恢复/新owner重新建立scope。长读事务不得阻塞暂停写入或持有旧快照跨越producer执行；Database替换、schema变化和连接失效必须重开，不沿用旧游标。

**内部验证结果复用。** 源证明绑定Dataset、attachment/reuse_domain、path occurrence、revision、verification profile；产物证明绑定Artifact ID、封存digest/size、路径及本次打开对象的文件身份。优先在一次验证调用内对唯一文件去重，提交/交付前仍检查对应的全部Work与引用。若进一步跨调用复用hash，至少要证明文件对象稳定、记录stat前后身份（含可用ctime）、防止symlink/替换，并在任何身份/依赖变化时重新hash；无法证明则继续完整校验。不能只设“有效五分钟”，不能从源的proof推导其他成员属性。暂停、恢复、owner更换、重开进程和发布重试均丢弃临时证明；发布前来源指纹及最终pin边界不沿用早期结论。能否跨阶段复用hash仍是设计验证项，首个实施包不需要它。

**调度。** 批次只是执行容器；内存、pending和每项输出责任保持。保留任务前控制检查及原资源准入，批处理结束前不报未提交工作完成。暂停/取消写入立即持久接受；正在执行的工作在既有安全边界停下。批大小须受数量、时间和内存共同限制，不能把整个S放进一个不可中断事务。恢复只处理尚未完成或已失效的逐项工作。

**验证CPU、status及索引/WAL。** 预编译验证器随契约/配方版本失效，数据内容仍逐项检查。status保持纯观察、真实心跳与进度含义；可在同次观察里共享一致查询结果，不能用心跳刷新进度或隐藏scope变化。若未来引入持久聚合，必须证明同事务更新、恢复重建和与原Work事实一致，当前证据不要求该实体。WAL或索引变更应独立验证暂停写入、崩溃、跨进程读、历史Result及发布重放，不能顺便改变保留规则。

## 工程优化与需要讨论的行为调整

上述 P0/P1 的批量访问、连接scope、去重复投影，及保持每项控制检查的调度修改，属于**可在既有契约下实施的工程方案**；本轮仅建议，不执行。批大小、语句方式、索引和同次调用内的临时映射由实现者决定，不形成新的公共配置或实体。

如果要改变默认status刷新周期、对外进度的新鲜度、暂停的可感知响应边界，或放宽来源/材料校验强度，必须先向用户解释并讨论；本轮没有证据要求这些行为改变。默认少准备、减少字段/关系、丢弃旧Result、使Read依赖可驱逐缓存、降低SQLite同步强度等均不在可选方案内。局部准备仍核对完整S、保留必要输入与全量对应，只减少实现层重复工作，不承诺局部参数修改变成纯O(|T|)。

## 成熟度、改动范围与结构代价：用户担忧复核

用户进一步明确：性能收益不能依赖全盘重构、代码范围失控、增加不必要实体，或把底层工具的有效性与安全判断搬到业务编排。此次目标应同时衡量执行成本、维护成本及责任是否集中。不能只证明“跑得快”，还要证明新增复杂度值得。

**这些是成熟工程手段的组合，不是一套需要引入的新架构，也不是可以不考虑现有语义直接照搬的标准套件。** [SQLite FAQ 的事务说明](https://www.sqlite.org/faq.html#q19)明确介绍用一个事务分摊多个写入的提交成本；[Python sqlite3 文档](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.connect)提供连接、语句缓存及线程使用边界。这里需要项目设计的是批次何时提交、哪些事实必须一起可见、失败如何恢复。

同样，不能机械套用数据库优化口号。[SQLite 官方的小查询说明](https://www.sqlite.org/np1queryprob.html)指出，进程内SQLite没有远程数据库逐查询的网络往返，小查询很多也可以高效。因此批查询的优先级仍依据本轮实测的重复解析、对象构造和事务成本，不设“所有查询必须批量化”的规范。

仓库已有足够的实现起点：[连接scope](../../../src/mediasense/precheck/_sqlite_scope.py)、[Work批量完成](../../../src/mediasense/precheck/_work_sqlite.py)、[metadata批量生产](../../../src/mediasense/precheck/metadata.py)，以及[连接事务/线程隔离测试](../../../tests/test_precheck_sqlite_scope.py)。它们说明该方向可以沿已有结构推进；不证明新的暖命中批量路径已经正确。

| 候选范围 | 改动大小判断 | 预计涉及的现有责任 | 耦合判断 |
| --- | --- | --- | --- |
| 只补Run控制读的连接复用 | 小；约1–2人日，预计2–4个产品模块及定向测试，尚非补丁承诺 | `_sqlite_scope`、Run SQLite适配、必要的执行scope入口；保持超时与线程行为 | 低语义耦合。逐项查询、验证、事务和状态含义都可原样保留；主要改变连接生命周期 |
| 在一个已有Store中批量化一项完整操作，并接一个真实调用路径 | 小至中；需先选具体热点，通常涉及Store、调用producer及测试 | 例如Artifact逐项完整核验后的短事务批量写回，或Work批量附属 | 中等。事务可见性和失败边界需要设计，但不必同时改变所有Store |
| 完整P0-A：来源证明、Work附属、Artifact核验贯通暖rendition | 局部中型；原估3–5人日，至少涉及三种Store、rendition及编排接入 | 多个既有模块共同完成一条执行路径 | 中等。不是独立拔插模块，也不应宣传为几十行小修；共享数据库状态和恢复路径必须联合验证 |
| 把P0/P1/P2和WAL全部实施 | 中大型、多包工作；本轮不建议作为一个项目包启动 | 准备、调度、组装、封存、Read与存储运行方式 | 变化传播较大。报告列的是可选候选，不能自动变成全量重构清单 |

文件数和天数只用于表达量级，不能替代实际补丁范围。尤其测试和并发恢复验证可能比核心性能代码更费时。仅连接复用能独立实施，但目前没有产品A/B补丁证明它单独足以达到“显著降低总成本”的目标。

**理想结构是现有模块各自更高效地完成原职责。** Run/producer传入明确需求；SourceValidity继续负责来源证明；Work继续负责身份、依赖、附属和状态转换；Artifact继续负责材料完整性及失效；Result继续负责封存、pin和独立读取。批大小、线程数、先后顺序属于可替换方法，不进入语义身份或公共产品概念。

这些模块有必要的数据联系：Artifact损坏必须使相关Work失效，Work附属必须与进度范围变化同事务记录。因此不能承诺“完全独立、互不影响”。但没有理由新增一个全知的“暖Run优化器”，让它直接跨表写状态、认定缓存有效，再让各Tool接受它的判断。那会分散原来集中的责任。

设计审查应使用以下范围约束，而不是以新文件、新类或统一框架的数量证明模块化：

- 单项与批量入口共用同一套验证、失效和状态转换规则；不能复制两条长期分叉的冷热实现。
- 编排层不接收“跳过验证”“强制认为命中”等权限，也不为批量提交直接操纵各Store私表。
- 底层不新增“普通Run/局部准备特例”，不理解Plan为什么选择某个子集；仍只处理自身已有输入、依赖和资格。
- 不把多个独立操作包进贯穿文件读取/模型执行的巨型事务，不增加全局服务、注册表、持久缓存或独立批次实体。
- 任何改动如果要求先重写所有producer、整体更换存储层或清理现有类继承，便已超出本次局部优化范围，应停下来单独评估其必要性。

连接复用可以暂时回退而不改变持久数据；后续批量实现也应尽量保持现有表与逐项事实，使各步可以单独审核和对照。必要的短寿命列表、字典或私有辅助函数不构成新的产品实体；判断依据是它是否新增独立权威或生命周期。

## 最小实施与验收建议

根据上述约束，**修订首包建议为先独立做 P0-B 连接复用**，保留原逐项校验和事务。随后用相同方法测量剩余耗时；若不足，再选P0-A中的一个完整操作批量化，不一次贯通所有Store。原P0-A + P0-B的4–7人日估计是合计候选范围，不再作为最小开工包。跨阶段hash复用、WAL、公共行为调整及新缓存实体继续留在首包之外。

1. **先建立有限观察。** 保留主路径时间、进程CPU、按阶段提交/连接数及资源峰值。默认性能样本关闭逐SQL回调；另设一次诊断样本。验收计时起止统一，prior预热与后置留存审计分开。不要把减少轮询本身算作产品加速。
2. **先验正确性。** 覆盖同址暖复用、真实局部缺口、配置语义变化与纯调度变化；独立来源/同inode多名称不合并；比较完整Source/Evidence/关系、属性、Profile、scope成员、直接对应、有效材料与旧Result字节。允许Run/Result ID及真实观察时间变化，不能只比较入口数。
3. **验证实际效果。** 在测试运行后检查新增decode/model/provider调用及Work attempt，而非仅凭缓存状态；暖样本应零重复昂贵计算，缺产物/改源/改真实依赖必须重做或明确失败，不能错误命中。
4. **故障与并发。** 在批事务前/中/后、产物校验后、发布落盘后注册前、注册后completed前注入中断；并发改变Work资格、替换/损坏Artifact、修改源、暂停和失去owner。恢复保留已提交项、原冻结要求、真实错误，发布重试仍一份Result。保留既有冻结损坏、来源变化/不可用分类及旧Result独立Read反例。
5. **分层复测。** 先用512项和普通/高清物理内容不同的小夹具；正确后才在主线程空闲时，对固定4096/8192暖模板各做3次独立进程，与同方法候选基线比较。增加一个有真实新增准备的局部样本；启用能力的功能覆盖不可由本报告的关闭能力规模样本替代。最后由原验收链路检查隔离构建的公开入口，本轮不提前安装或发布。
6. **建议门槛，不是已获承诺。** 连接复用小包核对连接数及其时间下降，提交数应保持原语义，不预先承诺25%总时长改善。若后续选择包含批量事务的组合包，再以总提交减少≥40%、墙钟中位数降低25%作为可讨论的目标。各包均须CPU/RSS不回退、全部等价与恢复反例通过。若只改善微基准而整Run无显著收益，诚实报告收益不足；扩大范围前重新评估复杂度代价，不为达标削减准备/输出或追加未经选择的大重构。进一步覆盖组装/封存批写后才讨论更高目标，不承诺8192项固定秒数。

调查停止于此：已确认重复事务、连接/控制路径与数据访问的成本，已排除当前样本的实际模型/解码计算作为主因；精确OS等待分解、长历史status扩展、真实大媒体和其他文件系统仍未认证。这些剩余问题不要求先建立新架构，也不需要在选择最小方案之前重跑完整旧基线。

## 复现入口

在仓库根目录使用以下命令；输出目录必须是新的，不能覆盖本轮证据。先由同一执行环境生成512项模板，再克隆模板测量，避免卷身份能力不同造成预期的attachment拒绝。

```sh
rtk proxy env PYTHONPATH=.local/acceptance-releases/260914-run-composition-repair/candidate-2/source/src PROBE_MODE=light .local/acceptance-releases/260914-run-composition-repair/candidate-2/venv/bin/python .local/tool-execution-efficiency/260914-1359/runner.py --worker --output /private/tmp/mediasense-efficiency-new-seed --sizes 512 --explicit
rtk proxy env PYTHONPATH=.local/acceptance-releases/260914-run-composition-repair/candidate-2/source/src PROBE_MODE=sql .local/acceptance-releases/260914-run-composition-repair/candidate-2/venv/bin/python .local/tool-execution-efficiency/260914-1359/runner.py --output /private/tmp/mediasense-efficiency-new-sample --sizes 512 --repeats 1 --explicit --reuse-fixtures /private/tmp/mediasense-efficiency-new-seed
```

`PROBE_MODE=legacy`保留原trace计数；`cprofile`保存线程调用图；`light`不设逐SQL回调。`PROBE_POLL`仅控制调查器status轮询，默认0.1秒。最末SQL样本增加了按阶段统计和`00000.jpg`路径记录，早期样本没有这两项；最终脚本摘要见紧凑指标。临时剖析器不改变产品判定，只观测真实调用。
