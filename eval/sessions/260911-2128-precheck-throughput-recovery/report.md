---
title: "PreCheck 吞吐与有效帧修复验收"
service_version: "0.10.0 开发候选，基于 b3aa696；隔离 wheel 以 SHA-256 标识"
date: 2026-09-12
environment: "Apple M5 Pro / 18 logical CPUs / 48 GiB / macOS 26.4.1"
model_id: null
dataset_version: "ai-album-hk-representative-v1 / test-260831"
purpose: "联合验证 metadata 成本、有效视频帧、来源安全、复用和实际安装交付"
baseline_ref: "260911-1841-hk-preprocess-performance"
---

**实施前固定的本机门槛全部通过。** 2026-09-11开始实施，2026-09-12完成收尾复核。 最终候选的完整 metadata 阶段从 82.747 秒降至 15.708 秒，全量复用从 14.961 秒降至 3.992 秒；2,134 项正式 profile 的观测值逐对象不变。视频默认准备恢复为 843 个不同实际位置的帧，采样器制造的失败从 285 次降为零，唯一已知坏视频仍按 probe 失败保留。

用户先要求方案、逐步验收再开发，随后明确委托 Agent 自行判断并继续开发。[OpenSpec 决策](../../../openspec/changes/restore-precheck-throughput-and-coverage/design.md)、[冻结门槛](../../../openspec/changes/restore-precheck-throughput-and-coverage/acceptance.md)和[tasks](../../../openspec/changes/restore-precheck-throughput-and-coverage/tasks.md)记录该边界；不把委托判断说成用户逐条审阅了实现细节。

## 输入、版本和计时边界

- 指定路径：`/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`；主来源为其中 `260501-HK美食之旅`，共 1,851 JPG + 283 MP4。旧缓存和分类图不混作源媒体。
- 沿用原 package README、handoff 与 verifier 核验：原清单 SHA 全通过；用户加入副本后整个操作包超过原 2 GB 上限，verifier 总退出码仍为 1。未改包或放宽门槛。
- 最终逐项复核主目录全部 **2,142 个文件**：路径、大小、mtime、SHA-256 与修复前一致，2,134 个媒体仍匹配受保护 manifest。
- 基线代码：MediaSense `b3aa69625fdbdc7692cd1e6bdc935464406d962c`；AI Album `c90aa8f04fd0d3348284e0ad19e18462987b1af2`。原 session 的代码、21 次测量和输出保留；没有让旧 worker 的 FFmpeg 注入路径冒充新的 PyAV 路径。
- 新候选：ExifTool 13.30；ffprobe 8.1；PyAV 16.1.0（libavcodec 62.11.100 / libavformat 62.3.100）；Pillow 12.3.0。当前 Python 3.11.13，旧提取方法的 Python 3.10.18；版本差异保留，不把所有速度差解释为一个变量。
- 模型及 Geo 调用均为 **0**，API endpoint：无。性能路线依次执行，系统缓存未清空，机器未独占；首次指新工作区/未命中 Work，不能等同于操作系统冷缓存。

所有数字均为明确阶段的墙钟时间。扫描、分组单列；有 GPS 的香港素材没有绕过 Geo 契约强行完成公开 Run。真实完整 Run/Read 装配另用无 GPS 的受控来源验证。原始媒体、数据库、图像、日志、profiles 与 wheel 仅在 ignored `outputs/`。

## 性能与结果共同验收

| 范围 | 修复前 | 修复后 | 结论 |
| --- | ---: | ---: | --- |
| 2,133 项同 18 字段内核，原并发策略 | 旧 AI Album 11 并发 1.363 s；MediaSense 单通道 10.787 s | — | 原差距主要来自串行化；不把不同资源条件直接作新实现胜负结论 |
| 同 18 字段，双方最多 4 个 ExifTool | 本次新增旧方法参考：3.477 s | **3.450 s**，三轮中位 | ≤4 s，且为同资源旧参考的 0.992 倍；各轮返回值逐对象相同 |
| 正式 metadata profile，2,134 项首次 | 82.747 s | **15.708 s** | 全部成功、观测值相同；≤35 s |
| 同 profile，后继 Run 全复用 | 14.961 s | **3.992 s** | 2,134 项复用；仅版本查询，无字段重提取；≤8 s |
| 843 个相同有效目标帧，串行/同尺寸/JPEG 90 | AI Album OpenCV 31.800 s；原 MediaSense 50.593 s | **28.217 s**，三轮中位 | ≤35 s 且≤旧方法的 1.10 倍；所有目标、实际位置和图像对应通过 |
| 默认有限视频准备，283 视频 | 370 有效帧、285 抽帧失败、1 坏源 probe | **843 有效帧、0 抽帧失败、1 坏源 probe** | 282 个正常视频均交付；没有用少输出换速度 |
| 当前完整视频阶段首次，含 probe/帧/联系表 | 原 23.748 s 仅含 probe/帧，不能直接比全阶段 | **22.478 s**，含 282 张联系表 | ≤30 s；阶段内 probe 2.996 s、帧 12.657 s、联系表 6.595 s |
| 当前完整视频阶段全复用，含联系表 | 原 7.666 s 仅复用370帧及旧失败 | **6.928 s** | 843 帧复用；0 decoder open、0 frame request；≤10 s |

EXIF 当前三轮为 **6.443 / 3.323 / 3.450 s**，旧四并发参考为 **3.315 / 3.477 / 3.718 s**；偏高的首轮没有剔除或重写。视频内核三轮为 **28.217 / 30.177 / 27.720 s**。前一候选的 metadata 首次/复用还测得 14.410 / 4.384 s；收尾表使用最终代码复核的 15.708 / 3.992 s，完整正式字段比较均通过。

最终 metadata 两轮扫描另为 **2.910 / 8.469 s**；视频两轮扫描为 **11.292 / 3.185 s**，不混入 producer 时长也不隐藏。分组/选择首次另测 2.655 s（后续联合复核复用已有候选，0.601 s，单独记录而不覆盖首次值）；与基线仍为167个候选、99个图像和182个视频来源。该真实选择集合内，视频材料从 **267 有效帧 / 184 抽帧失败 / 1 坏 probe** 恢复到 **540 有效帧 / 0 抽帧失败 / 1 坏 probe**。

默认 JPEG 现在只缩小超出上限的帧，不放大低清代理；默认前后还改变了目标策略，并新增统计联系表，所以默认总时间不作为严格同工作量速度比。严格比较使用相同 843 帧、相同输出尺寸和编码预算。843张对应帧的尺寸全部相同，在原64×64检查配方下像素 MAE 中位 **0.000244/255**、最大 **0.367757/255**。默认产出的843张帧与该内核的同位置图像字节一致，另完整解码282张联系表。

## 修复机制与产品契约

根因证据来自调用粒度与结果验收的连接。独立的逐项责任曾带来重复连接/续租及逐帧进程；同时 duration 请求被直接视为帧位置，终结失败容易与“准备完成”混淆。修复保留每项 Work、依赖、失败与恢复，把物理执行改为可共享的短暂组织。

256项同一串行诊断配方中，SQLite实际连接从 **3,097 降至 27**，提交从 **2,305 降至 1,281**；快速批次的1,024次冗余逐项续租消失。每个操作仍独立提交，长批 heartbeat 使用自己的线程与连接。该 profile 说明热点机制，不用带 profiling 开销的时长替换正式成绩。[调用统计](metrics/coordination-profile.json)

| 稳定承诺及权威位置 | 本次落点 |
| --- | --- |
| [Run](../../../docs/spec/contract/precheck-run/index.md)：范围、准备义务、资源、恢复和执行事实 | 每项责任独立；允许有界批量/共享解码；完成计数、对账、准备满足、plan_ready 与发布认证各需自己的证据 |
| [Read 属性](../../../docs/spec/contract/precheck-read/precheck-attributes.md)：真实材料、位置、来源及限制 | `sample_time_seconds` 保留请求目标；`decoded_time_seconds` 记录实际 PTS；basis 给真实 producer、流起点、时间基准和选帧方法，联系表格子保持一致 |
| [本次验收](../../../openspec/changes/restore-precheck-throughput-and-coverage/acceptance.md)：输入和数字门槛 | 条件化的性能/覆盖/复用与安装证据；不把4通道、3帧、PyAV或本机秒数变成永久API常量 |

来源只有两帧的三个视频，各交付两个实际位置；其余279个正常视频各交付三个，共843。内部846个请求 Work 都成功，三个重复实际位置不增加 Evidence 数量。请求会按源时间基准的最近 tick 解析，选择该处或之前的实际帧；片尾解析到最后可用 PTS。历史没有实际位置时保持未知，旧 Result 字节不回写。语义变化由新 frame producer/decoder/profile 依赖隔离；纯线程数变化不使有效帧失效。

这解决的是经济地取得可追溯的有限证据。是否足够支持具体组织决定仍由 Agent 和用户判断；有限起/中/尾不等于全场景发现，也不替代厂商规则配置或模型质量的独立验收。

## 故障、恢复、资源与安装

- 完整默认套件：1,104项先通过；4项回环 HTTP 测试受沙箱监听限制，取得本机回环权限后4项通过；另1项指出遗漏的 Skill schema 副本，修复后相关10项通过。合计 **1,109项默认测试的验收已通过**，16项 `local_fixture/scale` 按默认标记未运行。本次真实fixture性能验证由独立配方承担。
- 覆盖批次坏项隔离、过期/失去租约、续租失败、取消后成功保留、线程/事务隔离、独立并发通道、死亡通道重启与旧管道关闭；视频覆盖一/两帧、稀疏时间线、VFR、非零流起点、解码工作上限、源变动、取消、变更后选择性复用、旧Result不变及公开位置投影。
- codec 实际配置2线程；视频阶段至多4路，按源尺寸估算内存准入。正式视频进程观测RSS峰值 **763,887,616 bytes**，串行内核峰值约579 MB；早期单视频原型946,503,680 bytes，均低于本次1.25 GiB原型门槛。内存估算不是硬RSS限制，120秒/20,000帧检查及取消是协作式，底层调用需先返回。
- 从锁定核心依赖构建隔离 wheel，运行时从其 `site-packages` 导入；未混用checkout或注入fake producer。真实 Host 经公开 start/status/resume/Read 生成并读取 **5帧、2联系表**，包含请求与实际PTS不同的稀疏尾帧。后继Run没有新的 metadata/video Work尝试，沿用有效范围确认；3个受控源文件及旧Result字节不变，网络尝试0。
- wheel 中全部 MediaSense 文件与当前源码逐字节相同；Read 权威schema、Host副本和Skill引用副本一致。SHA-256：`b4a16a8f10513896f8f24d3d39529f3fa5237a6a905f687859bbf632f9ed731f`。候选含当前共享工作区已有内容，其他Plan工作不作为本次修复的贡献或性能归因。

首次安装检查已正确完成首个Run和后继复用；脚本误把后继Run的有效范围复用当作必须再次暂停，已修正脚本并在独立目录重跑通过。原检查输出保留，不修改产品合约迎合测试假设。源码和隔离wheel已验收；**日常全局Host与业务Dataset没有切换**。

## 复核入口与适用范围

[完整小型指标](metrics/combined.json)、[检查记录](metrics/checks.json)、[固定配置](config.json)、[运行配方](run.py)、[联合验证](validate.py)、[实际安装检查](installed_smoke.py)。从仓库根目录运行；case目录拒绝覆盖已有测量，重跑请使用新的case名并明确比较范围。以下是本次具体调用形式：

```sh
rtk proxy .venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/run.py metadata --case metadata-final
rtk proxy .venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/run.py metadata --case metadata-final --reuse
rtk proxy .venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/run.py exif-current --case exif-current-3
rtk proxy /Users/chengyanru/repos/personal/photo/ai_album/.venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/run.py exif-legacy --case exif-legacy-3
rtk proxy .venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/run.py video-common --case video-common-3
rtk proxy .venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/run.py video --case video
rtk proxy .venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/run.py video --case video --reuse
rtk proxy env -u PYTHONPATH eval/sessions/260911-2128-precheck-throughput-recovery/outputs/install-venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/installed_smoke.py
rtk proxy .venv/bin/python eval/sessions/260911-2128-precheck-throughput-recovery/validate.py
```

内核分别使用1/2/3三次case。wheel按 `uv.lock` 导出的非dev核心约束安装；构建与依赖准备允许下载包，实际fixture及Host运行禁止网络。开发测试的完整命令和初次失败保留在 `outputs/pytest-full.log`、`outputs/pytest-packaged-contract.log` 及本报告中，4项回环复核使用 `rtk proxy .venv/bin/python -m pytest -q tests/test_geo_network.py`。

当前结论只覆盖本机、该受保护代理fixture及三个0.30–2.74秒原样4K/8K片段，不能外推到原始879 GiB视频、长GOP、全量RAW、外置/远程存储或所有机器。若这些范围影响下一步产品判断，应新增相应输入、资源、故障和耗时验收；若profile/decoder语义改变或实测资源超出估算，重开对应依赖与预算，不沿用本次通过标签。
