---
title: "首次真实 Apply 使用验收"
service_version: "0.11.0；Apply 与 MCP Host 文件逐项比对安装包"
date: 2026-09-16
updated: 2026-09-17
environment: "本机 macOS / APFS；已安装 MediaSense Python 3.13"
model_id: "被验收会话为 gpt-6-astra max；核验脚本不调用模型"
dataset_version: "ai-album-hk-representative-v1 的 test-260831 工作副本"
purpose: "对照正式契约核对首次 Apply 操作、授权、文件结果和意外情况"
baseline_ref: "docs/spec/contract/apply/index.md"
status: review
timezone: "Asia/Shanghai"
---

**这次文件整理结果通过核对；Apply 整体验收暂不通过。** 冻结方案、准备、执行、回执的主流程与设计一致，实际文件没有发现丢失、错位或覆盖迹象。但是安装版存在两处安全边界缺口：冻结后源内容变化未被拦截，MCP 接受 Agent 自填的人类确认字段。两项均已用隔离探针复现。

本轮交付为验收报告、只读核验脚本和隔离复现脚本，没有实施产品修复。

## 验收对象与证据

- 用户指定的[实际 cmux 会话](cmux-nightly://workspace/00309E9E-42AF-4484-AF6A-01B06A8CDDBD/surface/1E22F6DB-7256-4C33-B752-4735C318D886?stable_workspace_id=520A8438-0F7A-424E-9912-BAA7A64B2BB2&stable_surface_id=07ECA30E-E297-4CE5-9C66-88E1D258C637)，核对了实时终端、原会话和继续会话的结构化记录。
- 源工作副本：`/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`。
- 备份：同级 `test-260831-original-backup-20260916`；目标：同级 `Media`。
- Dataset：`dataset:c9e8ae22f35d48b8860e07caf1381a93`；状态目录及全部精确定位见 [config.json](config.json)。
- Frozen Plan：`frozen-plan:615f97ba-9593-4349-b2d3-054c0bc6596d`；Run：`apply-run:fe55d2965a854783819567ce93c05ad5`；Receipt：`apply-receipt:fe55d2965a854783819567ce93c05ad5`。
- 原执行入口是本机 `mediasense mcp` 的 stdio Tool Host。验收使用安装包的 `PrecheckReadTool`、`ApplyReceiptReader` 做只读解析，并以 SQLite `mode=ro` 交叉检查既有 Run；没有新开真实 Dataset 的写入 Host。
- 仓库 HEAD：`e10abe8ed78a10205f6e00e1d70906f786ae74b2`，保留工作区既有未提交改动。安装版为 `0.11.0`；14 个相关实现、合约和 Skill 文件与工作区逐字节一致，精确摘要见 [code-identity.json](metrics/code-identity.json)。版本号本身不作为构建相同的证据。

设计依据为 [Foundation](../../../docs/design/design-260823-1918-mediasense-foundation.md)、[Apply 当前契约](../../../docs/spec/contract/apply/index.md)、[Frozen Plan 当前契约](../../../docs/spec/contract/frozen-plan/index.md)、[人工交接示例](../../../docs/design/design-260829-0038-apply-reference-handoff/index.md)以及随安装交付的 [Apply Skill](../../../src/mediasense/_resources/skills/mediasense-apply/SKILL.md)。判断遵循 `yanru-guidelines`：冻结意图、运行效果和回执事实各归其权威；核验和交接方法可以改善，无需新增业务实体。

## 实际结果

2026-09-16 23:08 的独立核验结果见 [verification.json](metrics/verification.json)。

| 核对对象 | 结果 |
| --- | --- |
| 冻结范围与组织 | 6,373 项、50 个逻辑组；经精确 Result 的公开 Source Set 解析，分组、成员及最终路径全部与 Receipt 相等 |
| 移动范围 | 2,138 文件，1,095,090,414 bytes；1,851 JPG、283 MP4、2 GPX、1 DNG、1 ARW |
| 未移动范围 | 4,233 排除项、2 个保留原位项，共 4,235；逐文件 SHA-256 与备份一致 |
| 已移动字节 | 2,138 个目标文件的完整 SHA-256 与备份及 Apply 准备记录一致；其原位置全部不存在 |
| 来源连续性观测 | 2,138 项均与原 Result 留存的有限指纹一致；目标 dev/inode/size/mtime 与准备时记录相同 |
| 备份覆盖 | 6,373 文件、1,424,933,315 bytes；移动集与留存集合并恰好覆盖备份，无遗漏 |
| Receipt | 完整性通过；3 个不可变操作分段经 3 页读完，共 2,138 条；每项 attempt=1 |
| 结束与异常 | `completion=complete`、`closure=automatic`；失败、拒绝、未验证及残余操作均为 0；59 个创建目录有记录 |
| 执行时间 | 21:45:35.394 至 21:46:04.027，约 28.63 秒；不是整段 Agent 交互耗时 |

权限、owner/group、mtime、BSD flags 和全部 xattr 与备份一致。创建时间与 `cp -R -p` 备份有差异，因此不把备份创建时间当成 Apply 前的完整元数据快照；独立临时文件实验也复现了单独 `cp -p` 造成创建时间差异、源文件未变且 mtime 相等。本次没有证据把该差异归因于 Apply。

当前目标树有 5 个额外 `.DS_Store`，创建于 22:50–22:51，晚于 21:46 的执行关闭；它们是后续 Finder 浏览元数据，不是多移了 5 个计划文件。Receipt 的执行时事实与后来的目录现状分别记账。

## 阻断整体验收的问题

### P1：冻结后源文件变化会被重新认作原计划对象

本次 2,138 项的 PreCheck 观测均为 `candidate-sha256-full-or-3x4k-v1`，明确只支持普通变化检测。安装版在 [SourceItemEvidence.from_precheck_view](../../../src/mediasense/apply/preparation.py:156) 仅保留 `sha256-full-v1`，其余情况令 `verification=None`；[_verify_source](../../../src/mediasense/apply/preparation.py:2246) 只有 basis 非空才比较旧证据。随后 [_prepare_item](../../../src/mediasense/apply/preparation.py:1720) 将当前文件的完整哈希写为新准备依据。

这使 Result 到 Apply 准备之间的来源核验断开。隔离实验先为蓝色 JPEG 生成真实 PreCheck Result 和冻结计划，再把文件改成尺寸不同的红色 JPEG：字节数从 689 变成 949，普通指纹和完整哈希均变化。`prepare` 仍返回 `ready_for_authorization`、0 blockers，并将改后字节写为预期值。探针没有调用 execute，目标目录为空，全部实验文件随后清理。详见 [source_drift 指标](metrics/boundary-probes.json)和 [复现脚本](probe_boundaries.py)。

**这次真实文件未发现该变化；复现证明的是保护机制缺失。** 将完整哈希延后到 Apply 是既有 [scale-precheck-execution 调整](../../../openspec/changes/scale-precheck-execution/design.md)记录的方法选择。应保留这一成本边界，同时先验证当前对象与 Result 已有普通变化证据一致，再建立准备阶段的完整哈希。改变的来源不能仅凭同一路径继承原冻结计划的归属。

另有契约同步问题：[当前 Apply Source compatibility gate](../../../docs/spec/contract/apply/index.md:102)仍要求 Result 提供 `sha256-full-v1`，与已实施的延后核验和本次实际输入不一致。需要显式审阅并收敛这个承诺；不能通过修改文档掩盖上述源变化缺口。

### P1：Host 将普通参数中的人类身份声明当作可信确认

本次移动有用户在 21:39 的明确确认。问题在于 Host 没有验证确认的来源：20:17 的首次执行因缺少上下文返回 `access_denied`；继续会话中的 Agent 阅读安装源码后，自行填写顶层 `authority.principal_ref`、`confirmed_content_identity`、`confirmed_at`，21:45 执行成功。

[MCP schema](../../../src/mediasense/runtime/mcp_host.py:242)向调用方公开自由填写的 `authority`；[dispatch](../../../src/mediasense/runtime/mcp_host.py:75)读取它；[composition](../../../src/mediasense/runtime/composition.py:676)直接构造 `ApplyConfirmationContext`。底层会核对内容 identity，但没有证据区分人类确认与 Agent 的自我声明。它与 Apply 契约及 Skill 中“trusted host context”“Never … place a principal assertion in ordinary Tool input”的承诺不一致。

隔离探针调用安装版真实 MCP handler，以 `context=None` 和虚构身份发送普通 arguments；该 authority 原样到达记录型 runtime，无任何人类确认通道参与。没有使用真实 Run，也没有文件效果。详见 [authority 指标](metrics/boundary-probes.json)。

修复责任属于现有 Host 的确认边界：使普通 Agent 参数不能自行取得可信身份，并从客户端可验证的人类确认建立上下文。现有 PreCheck/Geo 的 Host 确认机制可以作为实现参考；不需要新建确认 Tool、Skill 或授权服务。

## 使用过程中的其他差异

**冻结计划交接过大。** 已封存 JSON 为 465,692 bytes，其中 4,233 项排除清单被逐项展开，68 条 decision notes 也携带大量范围引用。首次 seal 输出被工具估算为 116,750 token 并截断；后续为取回完整对象重放 seal，又遇到一次 `confirmation_required`。这个值是工具输出估算，不是模型计费 token。尽管后来原样交接成功，它已经偏离“紧凑、可直接消费的冻结计划”的使用目标。优先复用现有 Source Set 的集合表达减少重复，可靠保留结构化 seal 结果；不应要求消费 Agent 读取 Plan 私有路径或拼接计划。

**撤回期限没有在最终答复中告知。** `apply.read inspect` 已返回 `rewind_window_ends_at=2026-09-16T14:46:04.026685Z`，即本地 22:46:04；最后回复只给出了成功数量、备份和 Receipt。这个 Run 的内置整批撤回窗口是一小时，在本次验收文件核对时已过期。备份仍在，但备份恢复与 Receipt 驱动的 rewind 是不同路径。结束说明应交代该期限与条件，不应让用户从回执 JSON 自行发现。

**“先 thumbnail apply”被拒绝符合当前设计。** 18:35 用户提出该请求后，Agent 检查接口并明确说明只支持 `move_originals`，预览属于 Plan；直到用户再次要求直接 Apply 才准备移动。这是对 AI Album 输出模式的既定 `intentionally_changed`，本次没有以缩略图请求替代原件移动授权。它同时说明用户仍带着旧产品的“先生成缩略图目录再移动”预期，产品说明需要提前讲清。

**长等待需要分别归因。** 从 19:05 的直接 Apply 请求到 20:18 的确认错误回复，包含重取计划、大载荷交接、Agent 调度与等待；留存轨迹不足以把整段时间分摊为引擎成本。已验证的实际移动与关闭约为 29 秒，不能写成移动文件用了数十分钟。

## 验证方式与范围

重跑实际数据只读核验：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 \
  /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python \
  eval/sessions/260916-2258-first-apply-acceptance/run.py \
  --output eval/sessions/260916-2258-first-apply-acceptance/outputs/verification.json
```

重跑隔离边界探针：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 \
  /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python \
  eval/sessions/260916-2258-first-apply-acceptance/probe_boundaries.py \
  --output eval/sessions/260916-2258-first-apply-acceptance/outputs/boundary-probes.json
```

另运行 8 项现有临时文件集成测试，**8 passed in 2.71s**：零效果准备、同卷成功回执、准备后碰撞拒绝、移动后崩溃恢复、重复执行返回同一回执、重启恢复、旧授权拒绝、回执游标与有界读取。精确命令见 [checks.json](metrics/checks.json)。它们支持已覆盖的执行边界，同时不能代替本报告新增的两个反例。

本次没有执行真实 rewind、跨卷迁移或物理断电/掉盘实验，不扩大已有认证范围。核验脚本早期曾遇到一批摄影属性展开超出 Read 字节上限、以及当前 macOS Python 缺少 `os.listxattr`；最终改用已有 resolve 的核验投影和只读 Darwin xattr API，完整核验通过。这些是核验方法修正，未修改产品、冻结内容或预期结果。

香港包按要求先读了 descriptor、README 和交接文档并运行 verifier。**所有清单内 SHA-256 通过，但完整 verifier 因当前目录总大小 4,613,783,445 bytes 超过 2 GB 而失败**：该目录已包含工作副本、备份、输出和预览，不能继续称为原始交付包整体校验通过。原清单覆盖的 fixture 字节与本次受移动的工作副本应分别看待。

原始会话、媒体、Result、Run 数据库、Receipt 与本轮 `outputs/` 均只在本地保留。Git 中仅增加报告、复验配方及紧凑指标；既有索引和迁移台账引用本报告，不复制一套新的产品定义。

原始轨迹定位：

- 原会话：`~/.codex/sessions/2026/09/16/rollout-2026-09-16T12-51-28-01a0a88e-3a94-74c1-abf2-e8a283910da3.jsonl`，关键记录为 433/444/451（确认与 seal）、470/486（备份与完整哈希核对）、514（thumbnail 说明）、525/528（seal 重取错误）、541/556/562/565（准备及首次执行拒绝）。
- 继续会话：`~/.codex/sessions/2026/09/16/rollout-2026-09-16T21-39-18-01a0aa71-78c0-7bb3-947c-bda11437e712.jsonl`，关键记录为 6（用户明确授权）、26/31（未变的准备身份）、44/47（Agent 提供 authority 后接受）、55/60（关闭与 Receipt）、72（最终说明）。

## 2026-09-17：安全与低 I/O 的取舍

后续设计已整理为[三套 Apply 方案及开发交接](../../../docs/design/design-260917-1150-apply-safety-efficiency.md)。方案选择、拟修改范围和合约判断以该设计为本轮入口；本报告保留首次验收事实及其讨论背景。

用户进一步明确：Apply 的目标同时包括效率、稳定和安全；希望尽量采用同卷 move/rename，避免大量媒体 I/O，并以 AI Album 的实际使用经验和成熟工具为参考。以下是基于该目标的讨论建议，尚未改变正式契约、产品代码或安装。上面的缺口复现与实际结果保留。

首次验收的全量 SHA-256 对照属于一次性结果证明。日常运行的校验应另按风险和成本设计，不能直接把验收脚本中的全部读取搬进正常执行流程。

### 当前成本与旧版机制

本轮检查时 HEAD 为 `cc3354db1f132be0d44e85ceb8272339c5f3f241`，三个 Apply 核心文件与首次验收时摘要一致。正常、无重试的同卷路径包含三次全文件读取：`_verify_source` 在准备时读取一次，`LocalFilesystem.move` 在 rename 前、后各调用一次全文件 `verify_file`。关闭 Run 的 `_close` 主要生成和发布回执，不再完整扫描媒体。

因此，本次选中的 1,095,090,414 bytes 对应约 **3,285,271,242 bytes 应用层媒体读取**；1 TB 媒体会对应约 3 TB 逻辑读取。它并未复制三份媒体，但也不是单纯目录项修改。这里是代码路径推导，物理读盘量和缓存命中未测，不能把它当成冷盘吞吐测试。大量小文件的路径查询、锁和同步提交还有另外的按文件数量增长的成本。

AI Album `c90aa8f` 的 `async_safe_move` 调用 `jinnang.io.system.safe_move`，lockfile 指向 `jinnang 0.2.2`。核对本机同版本、RECORD 摘要匹配的依赖后，正常分支为 `os.rename`，没有全量内容哈希；任何 rename `OSError` 都可能转入 `copy2` 再 `remove`。应保留它同卷改名的低 I/O 优点，同时移除不符合本次目标的自动复制回退。MediaSense 的不覆盖原子 rename 已经存在，不必重新设计文件搬移引擎。

### 推荐的默认边界

| 情况 | 建议行为 | 内容 I/O |
| --- | --- | --- |
| 同卷、来源和目标条件正常 | 复用旧来源证据，检查文件身份、大小、时间和路径边界，使用不覆盖目标的原子 rename；之后核对身份与位置 | 正常路径不以反复全文件哈希为前提 |
| 来源证据仅有现行有限指纹 | 比较 Result 的旧指纹，保留其普通变化检测限制 | 现有算法每项最多 12 KiB；本次 2,138 项上界约 26.27 MB，而不是 GB 级全量扫描 |
| 来源发生变化、目标已存在、卷或路径绑定失效 | 停止受影响的效果并报告；不重认来源、不临时改名 | 不以反复扫描或复制尝试消除阻塞 |
| 中断恢复 | 利用已持久化的意图、身份和结果，只复核尚不确定的操作 | 强校验按有根据的需要限定范围；新算一个哈希不能代替旧来源证据 |
| 跨文件系统 | 默认拒绝隐式转成复制删除；明确选择跨卷迁移后才执行相应验证路线 | 跨卷无法仅靠目录改名完成，必须单独披露数据搬运成本 |

当前 Result 的有限指纹并不包含完整的可直接比较的文件身份/stat 投影。若要把正常路线进一步收敛为纯元数据检查，应将 PreCheck 已取得的身份、大小和时间保留在现有 Observation 中，再由 Apply 复用；不能用 Apply 准备时刚读到的新 stat 冒充旧 Result 的证据。保持现有 Observation、Run 和 Receipt 即可，不需要新快照实体、验证服务或一组验证 Tool。

上次发现的来源问题可以通过比较已有旧证据来修复，不要求另加一次全量扫描；在保留现有准备读取的方案里，有限指纹甚至可以与同一遍读取一起计算。人类确认也应绑定整批准备结果一次，由可信 Host 承接，几乎不增加媒体 I/O，不需要逐文件向用户确认。

日志仍需要保证意图先于效果持久化，但可以研究小批提交和目录同步合并；批大小由实际测量决定。单个 rename 原子性不代表整批操作具有事务原子性，不能为提速直接删除恢复日志或停止同步后仍宣称同样的断电保证。

这种默认路线保护普通源变化、错卷、覆盖及可恢复执行，不宣称逐字节发现所有隐蔽内容修改或静默存储损坏。正式 Apply 契约目前承诺更强的完整字节证明；采用轻量默认路线时，需要显式审阅并同步保证强度和 Receipt 的核验含义，不能只删除 hash 调用却继续宣称完整字节验证通过。

### 成熟工具的参考

- [rename(2)](https://man7.org/linux/man-pages/man2/rename.2.html)：原地重命名保持文件对象；`RENAME_NOREPLACE` 在目标存在时拒绝；跨挂载点返回 `EXDEV`。这是廉价且有效的效果边界，不要求应用先扫描媒体内容。
- [GNU mv(1)](https://man7.org/linux/man-pages/man1/mv.1.html)：提供 `--no-copy`，明确要求改名失败时不复制。这是设计参考，不能假定 macOS 自带 mv 具有同一选项。
- [rsync 官方手册](https://download.samba.org/pub/rsync/rsync.1)：默认以大小和修改时间做 quick check；`--checksum` 是另一种判断依据；真正传输的文件另有随传输产生的完整校验。应借鉴按问题选择检查强度的思路，不把 rsync 的复制语义当成同卷 move。
- [fsync(2)](https://man7.org/linux/man-pages/man2/fsync.2.html)：文件同步不自动保证目录项已持久化，目录同步需要单独处理；轻量日志和正确持久化仍有价值，数据量小也可能存在延迟成本。

后续性能验收应分别比较正常同卷路径的媒体读取字节、媒体写入字节、元数据/同步操作量、文件吞吐与异常恢复工作量。不能仅凭这次暖缓存的小样本完成时间，声称大媒体或机械盘也具有相同性能。
