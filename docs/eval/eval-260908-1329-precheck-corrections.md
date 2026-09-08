---
id: "eval-260908-1329-precheck-corrections"
title: "香港审计后的 PreCheck 修复与验证"
type: eval
status: active
created: 2026-09-08
updated: 2026-09-08
timezone: "Asia/Shanghai"
parent: ""
depends-on:
  - "eval-260908-1148-hk-trajectory-audit"
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
superseded-by: ""
tags: ["precheck", "metadata", "embedding", "evaluation"]
---

# 结论与边界

**验收状态：部分通过。** 已知时间问题和 embedding 能力接通通过；真实 Plan
消费、质量和总费用改善尚待独立对照。原默认暴露路径已修复，验收指出的
operator manifest `..` / 符号链接绕过也已补上，不能据此声称整个盲测完成。

三个问题已分别定位到现有 metadata 解释、Host 的本地模型接入，以及评估输入边界。
修复没有增加产品 Tool、Skill、服务或 registry。时间事实仍由 metadata Work 产生，
运行配置仍由 Host 负责，实际执行由 Work/Result 记账，独立性由评估准备与评估上下文负责。
当前方法不是产品不变量；换模型、字段解释策略或压缩方法不需要改变这些归属。

本次是开发验证，不是独立盲测。开发上下文已经读过审计和历史材料。
没有执行 Apply、移动原媒体或提交代码。首轮只更新 `/tmp` 测试安装；
后续日常安装的验证状态单独记录，不将安装成功等同于完整验收。

## 时间：证实了字段解释回归，也识别了 remux 丢失时间

具体例子 `0504/DJI_001-action-sd-amber/DJI_20260504173346_0001_D.MP4`：

| 链路 | 观察 |
| --- | --- |
| 媒体原始字段 | `QuickTime:CreateDate=2026:05:04 09:33:46`，无显式偏移；Model/Encoder 为 DJI OsmoAction6 |
| 提取选项 | 旧、新实现原来都没有开启 ExifTool QuickTimeUTC 转换；输出保留无偏移字段 |
| AI Album 实际代码 | `_metadata_time._extract_standard_time` 调用 `jinnang.date_str_to_iso_date_str`；该安装函数将无偏移值先解释为 UTC，再转换到配置时区 |
| 旧包元数据记录 | `17:33:46+08:00`；它是历史观察，不是独立真值 |
| 修复前 MediaSense | `_normalize_datetime` 将所有无偏移值直接附加上海时区，得到 `09:33:46+08:00` |
| 修复后 | 同一原值按 QuickTime 整数时钟的 UTC 语义解释，得到 `17:33:46+08:00`；保留原值并标注假设 |

这是当前 fixture 上可复现的解释错误，不是对所有视频统一加八小时。
ExifTool 现在显式使用 `QuickTimeUTC=0` 保留原始观察，转换不依赖进程的本地时区。
带偏移时间按其偏移转换；EXIF 无偏移拍摄时间仍按配置的当地时区解释；
`OffsetTimeOriginal` 与带偏移的复合/相机拍摄字段参与选择。厂商名本身不是加减时差的依据。
不符合容器约定但拥有相机拍摄字段的输入，优先采用拍摄字段，并保留相互矛盾的候选。

`DJI_20260504202728_0029_D.remux-faststart.MP4` 的 QuickTime 创建时间全为零，
Encoder 为 Lavf62.12.100；修复前采用复制日期 `2026-08-31T06:12:38+08:00`。
现在在有效拍摄字段都缺失时，采用文件名候选 `2026-05-04T20:27:28+08:00`，
明确标注 `filename_time_fallback`，而不是把它写成媒体原始时间。
无可用文件名时仍可回退 mtime，但标注 `filesystem_time_fallback`。
有效但可疑的 2000 年时间不会被文件名悄悄覆盖；冲突显式保留。

与封存旧 Result 按路径对齐的 2,134 项对照：

- 1,851 项时间不变；281 个 QuickTime 视频的解释恢复了八小时差。
- 2 项从复制日期改用文件名回退；299 项标注时区假设，1 项保留时间冲突。
- 原值、拒绝的候选、来源、解释规则和资格限制进入封存观察，Plan 可以读到结构化 provenance。
- metadata producer 身份和 profile 语义进入 Work 缓存键；GPX、bundle 和 compression 通过上游依赖重新计算。
- 测试证明同一原值的错误/正确解释分别匹配不同 GPX 点、进入不同餐次组；旧封存 Result 字节不变。

时间修正还暴露了代表失效的问题：损坏原视频与两个修复副本归入同一 bundle 后，
原首选视频不可解码。压缩现可改用已经准备好的同组成员；bundle 身份与实际代表仍可区分，
并记录 `unavailable_bundle_representative_replaced`。损坏文件的失败事实不被改成解码成功。
最终全量运行中，原先未被压缩表示的三个成员重新获得表示。

限制：未读取 1.09 TB 原始素材来逐字段证明代理制作前后完全一致。
包内历史 cached_metadata 仅用于迁移比较，没有进入新运行的判断输入。
修复证实当前字段解释与回退链的问题，不声称恢复了所有厂商、格式、DST 歧义和编辑历史。

## Embedding：接通真实入口，证明执行与复用，不以入口数冒充质量

根因不是单个遗漏的开关。`EmbeddingProducer`、ChineseCLIP adapter、视频帧选择与
压缩消费已存在；但 RuntimeConfig 只接受地图配置，composition root 没有注入编码器，
默认 `embedding_profile=None`。机器原有模型缓存存在，仓库和已安装 Host 环境却没有
torch/transformers。仅改 profile 会遇到不可用后端。

现有配置新增 `[embedding]`，绑定模型 repository、不可变 revision、维度、设备和 batch。
安装脚本的 `--embeddings` 将依赖装入 Host 自己的环境；模型权重不会自动下载。
`dataset.open` 区分 disabled/configured，且明确 `execution=not_checked`。
Run 对缺模型/设备报告已知阻塞，对编码器身份变化要求恢复原配置或另开 Run。
意外实现异常会失败并传播，不会伪装成普通降级。
封存 Dataset context 记录实际 profile、执行、复用、失败和覆盖限制。

无配置仍禁用：这是明确、可发现的低证据运行，不是默认声称语义压缩生效。
适用性由本地成本和预期下游收益决定，未将一个特定大模型固化为默认目的。
CPU 可实际加载本机已有 pinned ChineseCLIP；本环境 MPS 不可用，未自动冒充 GPU 成功。

有 embedding 时，分组使用内容距离、时间、空间及相对于组首候选的距离判断边界。
相似候选不为了凑满 200 而被拆开；显著变化也不因数量目标被吞掉。
缺少视觉比较的部分保留原有限额回退及限制标记。代表比较、边界和远端成员候选仍可展开。
`bundle_members_not_visually_compared` 说明并未逐项比较所有原始媒体。

| 实验 | 不启用 embedding | 启用 embedding | 再次运行 |
| --- | --- | --- | --- |
| 9 个受控输入、三组重复真实画面、真实 MCP | 9 入口；编码 0 | 3 入口；实际编码 9；代表比较 18 | 3 入口；编码 0、复用 9 |
| 2,134 个 manifest 媒体的全量本地工作 | 167 bundle / 167 压缩候选 | 117 候选；实际编码 366；代表比较 160 | 编码 0、复用 366 |
| 全量最终代码复核 | 2,134 项均获压缩表示 | 2,134 项均获表示；117 候选 | 保持同样覆盖 |

全量编码的 366 份来自 99 个高分辨率图像和 267 个视频帧，不是 366 个原媒体。
181 个视频有成功探测；另有 1 个 probe failure、184 个 frame failure 工作记录。
这些是操作状态，不能算成 185 个坏文件。编码本身没有失败。
全量最终准备物为普通图 99、高分辨率图 99、视频帧 267、视频 contact sheet 181；
prepared media / Work / 派生图均不等于 Plan 实际看过的媒体或附件。

首次全量 embedding 对照约 222.7 秒；最终复核复用这 366 份输出，含其他本地工作约
61.8 秒，再次复用约 52.6 秒。受控源码 MCP 运行约 3.0 / 29.3 / 7.2 秒。
这些是该环境会话耗时，不是纯编码吞吐，也不是费用。幂等重放 status 的约一秒耗时
不算完整运行耗时；脚本另记录持久 Run 起止时间。

全量没有配置地图服务、没有远程授权：Geo journal 没有 admission，provider 请求为零。
因此全量 Run 在完成本地证据后诚实地终止于 `failed/provider_unavailable`，
**未封存完整 Result，未成为 Plan-ready 成功运行**。受控实验无坐标，完整封存成功。
本次未修改强制 Geo 获取契约来让评估看起来成功。

117 是局部视觉比较后得到的候选数，不是质量结论。最大组仍有 201 个来源成员；
其余未准备成员、视频抽帧局限和组内场景完整性仍需独立质量评估。
本次没有新的 Plan Agent：不同媒体查看数、派生图查看数、拼图附件、重复查看、
Plan 模型请求、Plan token/cache 均为 0，因为该阶段没有执行；端到端费用未测。
开发 Agent 会话自己的模型使用不属于这个零值，`remote_models=false` 也从不表示整个会话没用模型。

原审计的消费基线仍是：232 个不同来源、234 张不同派生图、251 次派生图呈现、
32 个图像附件，17 张派生图重复呈现；52 次 Plan 模型请求，输入 token 7,742,513、
cached input 7,461,068、未缓存输入 281,445、输出 31,325，费用未知。
成员 `resolve` 是身份解析，不计作 VLM 或地图调用。
时间纠错、复制日期辨认是本次消除的上游补救负担；确认具体餐厅、检查隐藏场景、
按用户检索目的命名仍是合理 Plan 调查。两者的后续实际节省量尚未测得。

## 旧答案：减少默认暴露，评估用允许输入而非排除后自称独立

原审计证明历史目录名曾通过范围样例进入模型上下文；另有 200 行 resolve 的
工具返回包含 123 条缓存路径与 8 条历史分类路径，后者未在外层摘要展开，也未证实被采纳。
这三层仍分开：工具取回、模型实际看到、最终采纳。没有新增证据证明结果整体抄袭。

scope inventory 现在只展示请求层级。目录不再提供后代样例；错误路径只投影到
当前层级，错误摘要不回显隐藏后代的诊断文本。显式展开仍可见精确路径。
正常排除项记账、`accounts_for` 和追溯没有删除或脱敏。
这不是访问控制：顶层名字本身仍可能有语义，显式展开和正常查账仍能取回排除项。

评估侧新增小型共享准备脚本，接受精确的路径→SHA-256 允许列表，复制到新的外部目录，
拒绝路径逃逸、符号链接、哈希不符和向 fixture 内写输出。它不会扫描并复制其他历史资料。
调用者必须先声明保留人工语义路径还是改为 opaque 名字；操作员映射放在评估输入之外。
本次全量对照允许原有人工目录和内嵌元数据；不允许旧分类、caption、参考 Plan、
报告、缓存或旧检索内容。受控实验使用 opaque 名字和合成时间，目标只限于重复画面选择。

测试用未列入允许输入的 `OLD_ANSWER` 验证目录样例、错误输出和副本内容不会暴露它，
也验证正常显式展开仍然可用。真正盲测还必须使用无继承上下文、无旧 memory/search 索引、
无历史目录访问能力的独立环境。准备副本本身不约束任意 shell 或远程检索权限。
本任务没有声称已运行这样的盲测。

## 复核与交付位置

- 源码基线 HEAD：`a9ba4a0908510e8594b1d6afb04dad02f78830c8`；本次改动未提交。
- [实验入口与输入边界](../../eval/sessions/260908-1329-precheck-corrections/report.md)、
  [MCP runner](../../eval/sessions/260908-1329-precheck-corrections/run.py)、
  [只读对照脚本](../../eval/sessions/260908-1329-precheck-corrections/analyze.py)、
  [精简指标](../../eval/sessions/260908-1329-precheck-corrections/metrics/combined.json)。
- 本地输出：`/tmp/mediasense-full-corrections`、`/tmp/mediasense-controlled-final`；
  仅精简指标进入仓库，媒体、模型输出、SQLite 和日志不进入 Git。
- 安装验证使用 `/tmp/mediasense-corrections-install`；现有全局安装没有替换。
  以上描述首轮验证。验收补修后，已用 `./scripts/install.sh --offline --embeddings --force`
  更新 `/Users/chengyanru/.local/bin/mediasense` 指向的日常安装。原 wheel 保存于
  `/tmp/mediasense-before-acceptance-update/mediasense-0.8.0-py3-none-any.whl`。
  版本仍为 0.8.0；关键源码/Skill/契约内容逐项 SHA-256 对齐。全局环境为 Python 3.13、
  torch 2.13.0、transformers 4.57.6，已独立用其解释器启动真实 MCP 验证：9 个来源、
  3 个入口、首次执行 9 份编码、随后全部复用；两次均 completed，Result 引用有效。
  耗时约 32.3 / 10.4 秒，输出在 `/tmp/mediasense-daily-installed-check`。
  用户级模型/地图配置没有被修改；新启动的 Host 使用新安装，既有进程不作热更新声明。
  安装脚本成功构建并装入 54 个依赖包；从该环境的 site-packages 启动真实 MCP，
  9→3 入口、实际编码 9、再次复用 9，三次均 completed。会话耗时约 6.4 / 42.4 / 12.2 秒。
  第一次沙箱内安装受 uv 缓存访问限制，隔离缓存又遇到 DNS 限制；经自动批准后使用
  现有离线缓存完成 `/tmp` 安装，没有把这些失败尝试记作安装成功。
- 验证：718 tests passed，16 deselected（默认不运行 local_fixture/scale）；ruff 和 diff 检查通过。
  验收补修后为 725 tests passed、16 deselected，涵盖 `..`、父/叶符号链接、
  写前路径改变、独占创建及历史指标引用修复。日志为 `/tmp/mediasense-acceptance-tests.log`。
  9 份 completed 摘要的空引用已通过既有 Run 和封存 SHA-256 补齐；
  6 份 failed 全量摘要仍为空，未改写其状态、耗时、工作计数或封存文件。
  当前完整 PreCheck → Plan 对照仍待地图凭据、外部调用授权、Plan 模型/服务和预算。
  它的明确输入边界、77 个坐标集合和验收标准已写入实验入口文档，尚未执行，
  不以受控编码案例替代独立 Plan 消费与质量比较。
- Fixture verifier：清单 SHA-256 通过，总大小 3,188,633,792 bytes 超过 2,000,000,000 上限。
  test 来源 2,134 个 manifest 媒体逐项 SHA-256 匹配；清单自身 SHA-256 为
  `f56caa6b1f1dd56e1b02850a5bfc17567d11f5617899db166eb8d670889d67fe`。
  没有把这些限定结果写成“整个扩展 fixture 完整校验通过”。

旧运行地理压缩结论保持：1,838 个带坐标来源、1,611 个不同精确坐标、225 个查询坐标，
Google 地址/附近各 225 次、高德 fallback 4 次，共 454 次；Plan 新增 0 次，费用未知。
新实验的媒体边界和 GPX 输入不同，不拿它的 pending Geo 批次与旧实际请求做优劣比较。
