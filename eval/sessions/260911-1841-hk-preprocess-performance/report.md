---
title: "香港本机素材 EXIF 与视频抽帧性能对照"
service_version: "MediaSense 0.10.0 / AI Album c90aa8f"
date: 2026-09-11
environment: "Apple M5 Pro, 18 logical CPUs, 48 GiB, macOS 26.4.1, local APFS"
model_id: null
dataset_version: "ai-album-hk-representative-v1 / test-260831; all 2134 media SHA-256 matched"
purpose: "比较同工作量的 EXIF/抽帧效率、默认采样覆盖与缓存复用，确定当前迁移表现"
baseline_ref: "AI Album c90aa8f04fd0d3348284e0ad19e18462987b1af2"
---

技术执行与复核已完成。**在这份本机素材上，当前 EXIF 提取的批间串行造成明显吞吐回退；同工作量抽帧也较慢。默认帧准备虽然耗时更短，但采样量、并发和输出规格不同，而且仍存在末帧位置处理缺陷，不能据此宣布性能与覆盖都已保留。**

本报告记录测量事实；迁移处置仍归[既有能力台账](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。没有修改产品实现。

## 数据、代码与测量边界

用户指定来源是 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`。该目录还包含 `.similarity_cache` 和 `representative-run-clustered`，总计 6,373 个文件、1,424,933,315 bytes；其中 4,009 个可识别媒体路径混有旧派生材料。本次主测试固定为 `260501-HK美食之旅` 的 **2,134 个 manifest 媒体：1,851 JPG、283 MP4，共 983,284,422 bytes**，不重复处理旧缓存和旧分类图。隔离的两个 RAW、GPX 和标记文件未纳入媒体吞吐对照。

先读包 README/交接文档，再运行原 `scripts/verify.zsh`：全部清单 SHA-256 通过；整个操作目录因增加测试副本而达到 3,188,684,007 bytes，超过原包 2 GB 限制，verifier 在大小检查返回 1。没有删文件或修改 verifier。随后逐一验证用户指定副本的 2,134 个媒体，全部与受保护 manifest 的 SHA-256 相同。主素材目录的全部 2,142 个文件在测试前后路径、大小、mtime 和 SHA-256 均不变。[输入证明](metrics/inventory.json) · [原 verifier 日志](outputs/package-verification.log)

API endpoint：无；未运行 embedding、Geo 或远程服务。Python worker 拒绝网络连接，所有测量的连接拒绝计数为 0；子进程只接收本地媒体和本 session 内的输出路径。

| 依赖／环境 | 本次实际使用 |
| --- | --- |
| MediaSense | 0.10.0 源码，`b3aa69625fdbdc7692cd1e6bdc935464406d962c` |
| AI Album | `c90aa8f04fd0d3348284e0ad19e18462987b1af2` 的源码快照 |
| 两条受控内核路线 | 同一个 Python 3.10.18；Pillow 10.1.0；旧 OpenCV 4.11.0；PyExifTool 0.5.6、orjson 3.10.15 |
| MediaSense 完整 producer | Python 3.11.13、Pillow 12.3.0、NumPy 2.4.6、jsonschema 4.26.0、gpxpy 1.6.2 |
| 本机命令行程序 | ExifTool 13.30、FFmpeg/ffprobe 8.1 |
| 机器 | Apple M5 Pro，18 个逻辑 CPU，48 GiB，本机 APFS，macOS 26.4.1 |

源码通过 `git archive` 固定，未混入同一工作区的其他开发。所有计时路线顺序执行、nice 10。系统文件缓存没有清空；前置哈希检查已读过素材，因此“首次”指空应用缓存，不是冷磁盘。未独占整台机器；三轮交替顺序为旧→新、新→旧、旧→新，保留各轮与当时 load average。

计时排除 Python/库导入、输入完整性检查和结果 JSON 汇总；保留外层进程总时间供复核。内核、持久化 producer 和默认采样分别计时。本次不是完整 CLI/MCP PreCheck、Plan 或 Apply 验收，也不是旧版带模型/地图的完整流水线对照。

## 同工作量比较：三轮结果

| 测量 | 旧实现三轮 s | 当前实现三轮 s | 旧／新中位数 s | 当前耗时 ÷ 旧耗时 |
| --- | --- | --- | --- | --- |
| EXIF：2,133 项、相同 18 个原始字段 | 1.701 / 1.318 / 1.363 | 11.145 / 10.787 / 10.045 | **1.363 / 10.787** | **7.92×** |
| 视频：282 个视频、相同 843 个有效目标帧 | 32.189 / 31.779 / 31.800 | 51.922 / 50.593 / 50.423 | **31.800 / 50.593** | **1.59×** |

[完整测量摘要](metrics/combined.json) · [可比性验证](metrics/validation.json)

### EXIF 的差距来自哪里

对照使用相同 18 个时间/GPS/摄影/格式字段、每批上限 200，先排除已知损坏视频，得到 11 批。旧路线执行 c90 的 `_get_exif_data` 原方法体，通过与旧 `asyncio.to_thread` 相同默认容量的线程池并发；本轮最多 11 批、11 个 ExifTool 进程。新路线直接加载当前 `StayOpenExifTool`，一个进程依次执行 11 批，包含一次版本查询和关闭。

六次运行的 **2,133 条原始字段返回逐对象相同**，不只是数量相同。另跑包含坏视频的旧路线，2,134 条 metadata 仍全部返回；可读取 metadata 不代表该视频可解码。这项值相等证明不涵盖归一化时间解释、厂商规则或字段选择政策。

将旧路线也限制为一批一批串行后，耗时 **11.548 s**，与当前的 10.787 s 接近。常驻进程确实减少启动开销，但这里丢掉批间并发的影响更大。“4,009 项变 21 批、只启动一个进程”的计数不能证明相对原版更快。

### 视频同工作量比较的具体含义

这是受控提取适配测试：旧路线保留 OpenCV 单句柄的 `CAP_PROP_POS_FRAMES` 定位、读取和 Pillow 转换；新路线使用当前 `VideoFrameProducer` 的 FFmpeg 命令参数形状，每帧独立进程。两边都串行遍历视频；OpenCV 的现有线程设置为 18，FFmpeg 使用当前 `-threads 2` 参数。它比较本机两条现有解码路线，不将库、线程或编码器差异伪装成纯算法变量。

共同目标由 ffprobe 帧数/帧率确定：首、中、末实际帧；不足三帧时去重，因此是 843 而非 846 帧。FFmpeg seek 提前四分之一帧周期，避免小数舍入跨过目标。两边最长边都限制到 `min(1920, 源最长边)`，保持同样尺寸，JPEG 保存预算为 90；Pillow quality 与 FFmpeg qscale 不是同一编码器。

三轮均 **843/843 成功**。第一轮 843 对输出尺寸全部相同，完整解码后统一缩到 64×64，RGB 平均绝对差的中位数 **1.248/255**、P95 **1.386/255**、最大 **1.511/255**。这支持帧对应关系，但不认证语义代表质量。新路线每轮启动 **843 个 FFmpeg 进程**；旧路线在进程内使用 OpenCV。启动、解码和编码各自占多少尚未进一步剖开。[逐帧核对](outputs/common-frame-comparison.json)

## 当前 metadata producer：提取之外的成本

直接运行真实 `AccountingStore`、`MetadataProducer`、依赖检查和工作状态持久化，处理全部 2,134 个主媒体，使用当前更广的字段 profile。后继 Run 复用同一数据库。以下两行均为单次实测，不与上面的 18 字段纯提取当作同一工作量比较。

| 指标 | 首次 | 后继 Run 复用 |
| --- | ---: | ---: |
| metadata producer 总时间 | **82.747 s** | **14.961 s** |
| 其中 ExifTool 命令等待 | 18.328 s | 0.061 s，仅版本查询 |
| 其余 producer 时间 | **64.420 s** | **14.899 s** |
| 成功 Work／其中复用 | 2,134／0 | 2,134／2,134 |
| 另计：来源枚举和账本准备 | 2.351 s | 2.720 s |
| 另计：分组和视觉材料选择 | 2.710 s | 1.124 s |

因此只优化 ExifTool 仍不足以消除主要的 producer 时间。剩余时间包含来源证明、Python 字段处理、Work/依赖查询及 SQLite 读写；这次没有做逐函数 profiling，不能把 64.420 s 全部叫作数据库写入时间。

本次重新计算得到 167 个主素材候选组、281 个视觉来源，其中 99 张照片、182 个视频，与此前业务输入形状一致。

## 默认采样与真实缓存：速度和产出必须一起看

两边都接收同样 283 个视频。旧路线直接执行 c90 `VideoProcessor.get_frames()` 和 `CacheManager`，默认约 10 秒间隔、最多 20 帧、串行；当前路线执行真实 `VideoProbeProducer`/`VideoFrameProducer`，默认最多 3 帧、四个工作线程、FFmpeg threads=2。当前调度是本机受控 producer 驱动，不冒充完整生产 Orchestrator 的计时。

| 指标 | AI Album | MediaSense |
| --- | ---: | ---: |
| 首次帧准备并落盘 | **49.551 s** | **23.748 s** |
| 新进程读取／复用既有缓存 | **6.979 s** | **7.666 s** |
| 得到至少一帧的视频 | 282 | 282 |
| 成功输出帧 | **1,736** | **370** |
| 本轮帧读取／请求数 | 1,736 次成功 OpenCV read | 655 个采样 Work |
| 抽帧失败 | 0 次 read failure；坏视频另计 | **285 次** |
| 已知坏视频 | 1 个；无帧 | 1 个；probe failure |

默认总时间降低，同时输出帧数下降 **78.7%**。当前另有更高并发；旧路线不放大帧且 JPEG 保存未显式指定 quality，新路线最长边 1920、质量 profile 90。这些工作量、并发、输出规格和持久化保障差异，使 23.748 s 不能被当成“同等能力下提速两倍”。

复用结果也真实但边界不同：旧缓存对 282 个有效视频不再解码，仍读取 1,736 张 JPEG；坏视频重新打开一次。新路线复用 370 个成功帧并保留 285 个终结失败，未再执行媒体探测或帧提取，仅启动 ffprobe/FFmpeg 各一次查询版本。它返回 Artifact/Work 并做完整性检查，不能与旧侧完整加载像素的 6.979 s 简化为同单位缓存胜负。

原始 worker 指标 `frame_attempts` 统计请求的采样 Work 数，包含复用，不能作为新的执行次数；本次首次为655个实际提取，复用为零次新提取。实际命令计数需从 `external_calls` 扣除明确记录的版本查询。`process_starts` 覆盖整个 worker，可能包含计时区间之外来源探测所用的 `diskutil`。

所有 1,736 张旧输出与 370 张新输出均已在计时外完整解码核对。原缓存没被拿来冒充本次新生成结果。

### 285 次失败的定位

- **282 次**请求时间等于容器 duration，即每个可读视频的结束边界。请求在这个位置提取一帧，已经没有可输出帧。
- **3 次**请求 10 秒，虽小于容器 duration，仍晚于最后一个实际帧 PTS。ffprobe 完整帧时间核对如下。

| 视频标识 | 容器时长 s | 请求 s | 最后一帧 PTS s |
| --- | ---: | ---: | ---: |
| DJI_20260503135449_0001_D | 10.143467 | 10 | 6.762311 |
| DJI_20260505113813_0004_D | 12.312300 | 10 | 8.208200 |
| DJI_20260505195258_0008_D | 10.520000 | 10 | 7.013333 |

[实际帧时间证据](outputs/interior-failure-diagnostics.json)

这 285 次是采样操作失败，**不是 285 个损坏视频，也不是 embedding 失败**。已知无 moov atom 的截断文件单独保留为一个 probe failure。当前 282 个有输出视频中，194 个只有 1 帧，88 个只有 2 帧；“都有一张图”不证明整段内容覆盖或关键帧选择质量。

把本次逐视频结果对应到真实选择集合：旧 97 个代表视频取得 1,366 帧；当前 182 个被选视频取得 **267 帧、184 次抽帧失败**，另有 1 个坏视频探测失败。这复现了此前业务评测的问题。集合不同，而且并发任务重叠，未从逐项时间相加伪造两套完整默认流水线耗时。

## 结论、限制与下一步

| 判断 | 本次证据支持的范围 |
| --- | --- |
| `preserved` | 同字段 EXIF 原始值、有效位置的帧提取能力和成功结果复用 |
| `regression` | 本机同字段批量 EXIF 吞吐，以及所测同工作量视频路线耗时；批间串行已有隔离对照 |
| `regression` | 默认采样落到最后可输出帧之后；旧方法可取得末帧，而当前产生可复现的失败 |
| `intentionally_changed` | 采样上限、输出规格、并发方式、逐项失败与依赖完整性；变化本身不证明质量/性能已保留 |
| `not_comparable` | 完整旧流水线与当前 PreCheck 的总耗时、不同缓存读取责任、模型/Geo 成本和原始长码流吞吐 |

优先处理实际可输出帧位置与默认覆盖，再恢复符合资源上限的 EXIF 批间并发，同时定位 metadata 的非 ExifTool 热点。抽帧提速应比较减少进程启动或复用解码状态的方法，而不是只减少采样量。后续沿用本配方复测，并把行为变化回填已有台账；无需新增产品合约、服务或缓存权威。

素材边界仍很窄：185 个视频是约 3 秒的三帧代理，94 个是稀疏时间线代理；仅 3 个 native copy，为约 0.30–2.74 秒的 4K/8K HEVC 短片。它们不能代表 879 GiB 原始视频、长 GOP、外置盘或完整 RAW 读取。两个默认帧链路与完整 metadata 仅各测一次首次/复用；稳态内核各三轮。没有多机、冷磁盘、长运行或模型质量认证。

原始测量保留了父进程和 `RUSAGE_CHILDREN` 的 RSS 指标，但不是整棵并发进程树的同步峰值。不能只看当前父进程 RSS 就宣布更省内存；4K/8K 解码的单进程高水位已达 GiB 量级，提高并发前需进一步校准资源预算。

## 配方与复核

- [config.json](config.json)：源路径、代码版本、运行时、批量及采样参数。
- [run.py](run.py)：输入校验、串行编排、交替顺序和汇总；拒绝覆盖已有成绩。
- [worker.py](worker.py)：旧原方法／受控内核／当前真实 producer；无模型调用。
- [validate.py](validate.py)：字段逐对象比对、帧对应、完整解码、失败 PTS 与源完整性。
- [metrics/combined.json](metrics/combined.json)：各次测量与原始记录路径。
- [metrics/validation.json](metrics/validation.json)：可比性与产出检查。

源码快照由以下方式准备；新一轮应使用新的 session 目录，保留原 `outputs/`：

```bash
rtk proxy git -C /Users/chengyanru/repos/personal/photo/ai_album archive c90aa8f04fd0d3348284e0ad19e18462987b1af2 src | rtk proxy tar -x -C <session>/outputs/legacy-source
rtk proxy git archive b3aa69625fdbdc7692cd1e6bdc935464406d962c src | rtk proxy tar -x -C <session>/outputs/mediasense-source
rtk proxy zsh /Users/chengyanru/Downloads/ai-album-hk-representative-v1/scripts/verify.zsh > <session>/outputs/package-verification.log 2>&1
```

本次精确执行入口（从仓库根目录；重复执行 `run` 会拒绝覆盖成绩）：

```bash
rtk proxy .venv/bin/python eval/sessions/260911-1841-hk-preprocess-performance/run.py inventory
rtk proxy .venv/bin/python eval/sessions/260911-1841-hk-preprocess-performance/run.py run
rtk proxy .venv/bin/python eval/sessions/260911-1841-hk-preprocess-performance/run.py summarize
rtk proxy .venv/bin/python eval/sessions/260911-1841-hk-preprocess-performance/validate.py
```

原有工具的 verifier 大小失败已单独解释，`inventory` 还会检查受保护 SHA 清单身份与指定副本逐媒体哈希。正式计时前有少量独立 `pilot-*` 校准，不计入汇总。所有正式测量保存了当时 `run.py`、`worker.py` 和 `config.json` 的 SHA-256；计时后未改变它们。`validate.py` 只做测量后的复核。

源码快照、媒体、数据库、原始逐项响应和日志均仅保留在 ignored `outputs/`；Git 只应跟踪配方、报告和小型汇总。本次 Ruff、全部度量一致性、843 对帧对应、2,106 张默认输出完整解码和来源不变检查通过。
