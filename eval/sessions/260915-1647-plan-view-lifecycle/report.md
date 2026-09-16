---
title: "Plan 预览生命周期开发验证"
service_version: "0.11.0 development, unreleased"
date: 2026-09-15
environment: "macOS arm64 / Python 3.11.13 / Chrome / source and isolated wheel"
model_id: "none"
dataset_version: "generated 1200-item JPEG datasets"
purpose: "Verify L01–L20 automatic preview lifecycle without changing real Plans"
baseline_ref: "design-260915-1519-plan-view-lifecycle"
---

# 实施结论与范围

2026-09-15 安装补记：用户随后授权日常安装；现已把预览改动与已安装的 PreCheck 效率修复合并，完成日常 CLI、原项目四个 Skills 及新注册 MCP Host 验证。当前安装 wheel 为 `d9e3d11b…`，确切身份与范围见[安装台账](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md#2026-09-15plan-预览生命周期日常安装0110)。下文未发布／未安装是开发自验时点的事实，不代表当前日常安装状态；原用户 Agent 会话仍需新开。

2026-09-15 复核补修：用户指出瞬时图片失败和慢读取被错误分类两处缺口；现已针对这两项修复并完成源码、隔离 wheel 的浏览器验证。**当前候选为 build-4**，证据见文末“复核补修”。下方 build-3 的 243 项和生产周期记录保留为原始证据，不代表它们覆盖了这两条此前遗漏的分支。

生命周期实现保留普通 Plan 保存／默认 inspect 的自动 `view_delivery`。轻路由与整个重展示上下文分离；120 秒数据闲置回收、最多两份上下文、每 Work 单一重操作、最多 16 个等待者／5 秒等待、600 秒使用闲置退出均由 Runtime 执行。真实交互与数据读取分别计时，版本轮询和健康检查不续期。当前合约、Plan Skill、安装 runbook 和逐字发布副本已同步，公共 Tool schema、确认与冻结权限不变。

本轮使用独立生成的 JPEG 与 Dataset；没有读取或修改真实用户 Plan，没有运行真实媒体准备、远程模型或 Apply。浏览器／MCP smoke 不 seal；既有 pytest 仅在合成数据中回归确认、旧确认失效及冻结权限。标题、HTML 和 CSS 与工作区初始已确认界面逐字相同。

工程自验、用户体验确认、安装发布是三个状态：本页记录工程证据；原整理方案界面的观感已有用户确认，本次生命周期没有冒记新的用户验收；**没有发布或切换日常安装**。

## 实现与所有权

- `plan/_sqlite.py` 的最小只读绑定读取只取 Work／Result／revision／state／publication，不初始化、迁移或反序列化内容；展示专用 Store 与 cursor key 只读，连接明确关闭。
- `runtime/_view_lifecycle.py` 由现有 ViewServer 持有轻路由、缓存名额、Condition、pin 和两种时间。路由不持有 Reader；淘汰关闭整个 PlanView。失败构造的 traceback 死帧也清除局部强引用，保留异常类别和调用位置。图片响应字节在撤销 pin 前解除引用。
- `runtime/plan_views.py` 与 `_view_files.py` 管理父目录 lifecycle 锁、进程寿命锁、确切构建发现、60 秒总交付期限和 15 秒启动期限。只对明确 retiring／连接拒绝重接一次；超时、reset 等结果不明的传输失败不重复昂贵绑定。
- `_view_server.py` 持有 pin 至内容响应完成，退出与接入共用同步边界；stop 最多排空 5 秒，真实中断单独计数。状态读取不启动／续期，寿命锁仍持有时不会把 health 失败报成 stopped。
- 私有 activity POST 限同源、JSON、256 bytes 和精确 revision。前端过滤合成输入／鼠标移动，隐藏页暂停轮询；实际交互节流 30 秒并保留一次尾次发送。离线、忙、过期和实际图片失败分别反馈。
- 日志真实轮转为 1 MiB + 一个备份，不逐条记录 token／轮询／Plan 正文。旧构建清理只碰识别协议、当前 UID、已证明停止的已知普通文件；父锁忙、活动锁、旧协议、符号链接和未知文件安全跳过。每次最多检查 16 个目录，100 ms 检查预算；不扫描业务或 fixture 目录。

## 构建与可复核身份

基线 commit：`e10abe8ed78a10205f6e00e1d70906f786ae74b2`。先记录初始工作区摘要，再从 Git export 叠加明确清单构建，排除工作区原有 PreCheck 效率修改。没有回滚或覆盖无关文件。

初次实现 wheel（build-3，补修前）：[mediasense-0.11.0-py3-none-any.whl](../../../.local/plan-view-lifecycle/build-3/wheel/mediasense-0.11.0-py3-none-any.whl)。SHA-256：`4672ffffe38fff2d16c75bad167c6dd71bd893be95aef009731a51a6ae618e15`。

[纳入文件及逐文件摘要](../../../.local/plan-view-lifecycle/build-3/included-paths.json)、[固定依赖](../../../.local/plan-view-lifecycle/build-3/dependencies.txt)和隔离 source／venv 保留在同一 build-3 目录。最终包内源码与仓库对应 `src/` 文件无漂移；artifact-only 检查、合约副本及 runbook 逐字一致检查通过。原 HTML/CSS 摘要与初始工作区一致，无关改动摘要一致。

前两份隔离构建用于纵向验证。build-3 在 build-2 基础上仅进一步释放异常死帧引用和响应字节；页面、Plan 数据语义、锁／计时策略未变。验证脚本随后补充的案例按仓库版本运行，脚本摘要另见本轮最终清单。

## L01–L20 证据

| 场景 | 验证与结果 | 主要证据 |
| --- | --- | --- |
| L01 | 普通 create/update/default inspect 自动返回页面；没有 start/render 前置调用 | CLI trace、MCP inspect、原 delivery runner |
| L02 | state-only inspect 与 status 不创建 runtime 目录；非法 body／cursor／旧 activity 不载入上下文、不续期 | `test_plan_view_process`、`test_plan_view_lifecycle` |
| L03 | 四个真实 CLI 同时首次交付，同一 origin/token 和一个健康实例 | simultaneous-first-CLI 测试，源码与 wheel 均通过 |
| L04 | 不同 Dataset／Work 独立绑定；进程内同一 Work 复用地址；更新保留过期拒绝 | distinct-datasets 测试、20 Work／40 标签报告、原 delivery runner |
| L05 | 持续 current 轮询期间，120 秒回收，600 秒使用闲置后真实退出 | 生产参数运行日志、测量、寿命锁与 PID 检查 |
| L06 | 无图片读取的真实键盘交互节流／尾次通知通过；活动不延长重缓存 | UI activity 报告、生产 cache/use 两种时间、注入时钟测试 |
| L07 | 隐藏停轮询、可见恢复检查、静止可见页仍退出；独立 Chrome 被 SIGKILL 后无需 unload 仍自动退出 | UI activity、browser-crash/report.json；墙钟跳变／恢复调度使用注入时钟，未实际休眠用户机器 |
| L08 | 两个 pin 时第三份等待有界；等待池满立即拒绝；真实 HTTP 503 + Retry-After: 1；current 可用 | Condition 并发测试、HTTP busy 测试 |
| L09 | 20 个各含 1,200 成员的 Candidate，各开两个真实标签，共 40 标签；重上下文始终 ≤ 2 | multitab/report.json；Reader 弱引用、FD、RSS 记录 |
| L10 | 冷回收后沿原 token 读取，组页、50 成员后的旧游标和图片字节完全一致；新版仍拒绝旧请求 | cold-cache-final-wheel.json、cold-cache-source.json、原过期测试 |
| L11 | 长读跨闲置截止不退出；断连、投影、构造失败撤销 pin；保留异常也不能留住 Reader | inflight/factory/dead-frame/response-pin 测试 |
| L12 | 接入／退出只有一个胜者；真正排空进程返回 retiring 后内部仅重接一次，原 receipt 与 Work 不变 | barrier 竞争测试、real-retiring 测试、原期限／模糊失败测试 |
| L13 | 真实子进程卡住读取，约 5 秒停止排空并中断 1 个请求；PID 退出、寿命锁释放 | real-stop 测试；CLI stop 回执 |
| L14 | 旧 instance 不删 successor connection；health 不通且寿命锁持有时为 unknown/unreachable | lifetime-lock／successor 测试 |
| L15 | 退出后保留分组和已载图片；停止固定重试；新读取提示让 Agent 重开，无假图片丢失 | lifecycle-offline.png；浏览器断言 |
| L16 | 下一次普通 inspect 取得新 origin/token，revision 不变 | lifecycle trace／report、source CLI recovery |
| L17 | 256 路由满后保存回执仍在，新绑定 unavailable，旧路由不淘汰；路径故障恢复不重写业务 | production-route-capacity 测试、delivery-failure/replay 浏览器场景 |
| L18 | 活动构建、旧协议、symlink、未知文件不删除；一次目录检查有上限；日志实际轮转且合计 < 2 MiB | cleanup/rotation 测试及 process ownership 测试 |
| L19 | 120 组跨 3 页、1,200 成员跨 24 页；不重置展开；旧 cursor／asset 409；busy 与图片失败局部恢复 | 原 delivery browser-report、groups/narrow/stale/image-failure 截图 |
| L20 | 展示／回收／退出全量数据摘要相同；普通恢复仅已有 Dataset-open 更新时间改变，业务全量比较相同；确认权限回归通过 | authority-report、source recipe 校验、Plan 测试 |

独立测试 Chrome 已实际 SIGKILL，服务在最后读取后的短闲置期限自动退出：测试参数 cache 0.3 秒／service 5 秒，浏览器崩溃后约 4.63 秒核验服务 PID 退出、寿命锁释放及 idle_timeout。用户自己的浏览器未受影响。系统休眠只验证注入时钟的恢复调度、墙钟跳变与无续期行为，没有实际休眠用户机器。

## 实际测量与检查

最终源码和 wheel 定向测试各 **243 项通过**；另有新增真实 retiring 重接案例。源码使用匹配的隔离 0.11.0 解释器并显式指向 `src/`，子进程也使用该源码。原 `.venv` 留有 0.10.2 distribution metadata，导致过 3 项版本／Skill 环境检查失败；没有更改该环境，匹配环境已复验通过。[源码 JUnit](../../../.local/plan-view-lifecycle/final-source-tests.xml)、[wheel JUnit](../../../.local/plan-view-lifecycle/final-installed-tests.xml)、[真实重接 JUnit](../../../.local/plan-view-lifecycle/real-retiring-tests.xml)。

20 Candidate／40 标签运行：服务 RSS 为 **85,920–105,328 KiB**，上下文上限 2。较早 20 个空 Work／完整 Result 读取循环的 FD 始终为 21；RSS 为 93,872–101,808 KiB。以上只描述本次合成规模，不能推成物理内存硬上限。

1,200 成员冷重建：wheel 初读约 1.43 秒、重载约 1.33 秒；源码约 1.41／1.28 秒。Reader／PlanView 弱引用归零，成员游标、组页、图片字节相同，无 `gc.collect()`、malloc trim 或直接 shutdown 冒充自动回收。

build-2 生产参数运行在采样第 122.05 秒看到缓存归零，635.34 秒看到进程停止；计时起点为页面操作完成附近，最后一次节流尾次活动在约 30 秒，因此退出对应 **最后有效使用后 600 秒 + 检查／采样间隔**。整个静止期仍有超过 150 次 current 请求。缓存回收时 RSS 98,912 KiB，实际退出后 PID 不存在。最终 build-3 的完整 runner 以退出码 0 通过：第 **120.66 秒**观察到缓存归零，第 **634.85 秒**核验进程停止；共 **158 次 current 轮询、2 次活动通知**。缓存释放时 RSS 67,824 KiB、FD 21；PID 32054 与对应寿命锁实例退出，普通 inspect 返回新入口且 revision 不变；恢复后的显式 stop 也核验成功。此轮复用已生成 Work，不重跑媒体准备，40 标签容量证据仍见独立运行。

## 数据比对发现与处理

前两次长跑在最后“恢复后全目录必须逐字相同”的断言失败。逐表定位证明唯一差异是原有 `_accounting_sqlite.py` 的 Dataset-open 记账更新 `precheck.datasets.updated_at`，不是 Plan 或预览写入；展示、回收和退出期间连这个字段也未变。

没有修改 PreCheck 代码或放宽业务数据校验。修正验证器仅把这个既有打开时间单独记录；其余 schema、全部表／列／行、Work／Frozen／Result／准备图及文件仍严格相同。build-2 已由独立观察器在真实退出后、恢复前保存完整摘要，再于恢复后验证；[原始差异](../../../.local/plan-view-lifecycle/installed-1/recovery-authority-diff.json)、[最终逐表结论](../../../.local/plan-view-lifecycle/installed-2/authority-report.json)均保留。该轮的迟到断言失败没有被抹去，[finalize.py](finalize.py)核验其已记录的过程、实际交换和后验并形成报告。修正后的完整 runner 用于 build-3。

1,200 源文件再次与固定生成配方逐字节摘要核对。真实用户 Dataset 始终未被用作测试输入。

## 复核入口与复现

以下均为本机忽略目录中的生成产物，未进入 Git：

- [最终构建生产参数完整报告](../../../.local/plan-view-lifecycle/installed-3/lifecycle-report.json)、[最终测量序列](../../../.local/plan-view-lifecycle/installed-3/lifecycle-measurements.json)、[最终正常／离线截图](../../../.local/plan-view-lifecycle/installed-3/lifecycle-offline.png)、[最新合成入口回执](../../../.local/plan-view-lifecycle/installed-3/review-entry.json)。
- [CLI／MCP／浏览器汇总](../../../.local/plan-view-lifecycle/installed-2/report.json)、[生产运行明细](../../../.local/plan-view-lifecycle/installed-2/lifecycle-report.json)、[测量序列](../../../.local/plan-view-lifecycle/installed-2/lifecycle-measurements.json)。
- [最终 MCP 回执](../../../.local/plan-view-lifecycle/final-mcp/mcp-inspect.json)、[40 标签报告](../../../.local/plan-view-lifecycle/multitab/report.json)、[活动与隐藏页面报告](../../../.local/plan-view-lifecycle/ui-activity/report.json)、[实际浏览器崩溃报告](../../../.local/plan-view-lifecycle/browser-crash/report.json)。
- [正常页面](../../../.local/plan-view-lifecycle/installed-2/lifecycle-active.png)、[服务退出后仍保留内容](../../../.local/plan-view-lifecycle/installed-2/lifecycle-offline.png)、[自动恢复](../../../.local/plan-view-lifecycle/installed-2/lifecycle-recovered.png)、[窄屏](../../../.local/plan-view-lifecycle/installed-2/narrow.png)、[忙恢复](../../../.local/plan-view-lifecycle/installed-2/resource-busy-recovered.png)、[局部连接失败](../../../.local/plan-view-lifecycle/installed-2/image-failure.png)。
- [冷缓存 wheel 证据](../../../.local/plan-view-lifecycle/installed-1/cold-cache-final-wheel.json)、[源码冷缓存证据](../../../.local/plan-view-lifecycle/installed-1/cold-cache-source.json)。

最小完整复现使用已有本地 Chrome 和 playwright-core，无下载：

```sh
rtk proxy .local/plan-view-lifecycle/build-3/venv/bin/python   tests/run_plan_preview_delivery_smoke.py   --host .local/plan-view-lifecycle/build-3/venv/bin/mediasense   --output .local/plan-view-lifecycle/fresh-reproduction   --browser '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'   --playwright /private/tmp/foodie-p07-clean-7r0hr4km/node_modules/playwright-core   --skip-seal --lifecycle
```

输出目录必须不存在。此命令只准备新的合成媒体，完整生产参数阶段需等待约 11 分钟；常规产品使用不需要此测试命令。额外 activity／multitab／cache probe 的入口在 `tests/run_plan_view_*`，输入配置和路径在对应本机产物目录。没有留下必须由用户手工清理的产品历史 HTML。

剩余限制：RSS 不以字节硬封顶，超大 Result 的单个投影仍受其实际对象规模影响；静止超过 10 分钟后旧链接可能离线，需要普通 Plan 调用返回新入口。这些是已确认设计边界。真实系统休眠仅模拟时钟验证；未做发布、日常安装或真实用户 Plan 验收。


最终 build-3 的普通 CLI 入口验证、MCP 验证、异常引用释放测试和生产计时均已完成。旧 raw-hash 断言的修正没有改变产品代码或 PreCheck 行为；最后一轮完整 runner 已通过，不依赖前两轮的后验整理。所有截图中的媒体均为合成测试数据。


## 复核补修（2026-09-15）

用户只读复核确认主体证据，并指出两条此前未覆盖的前端分支。本次仅修复这两项；产品包相对 build-3 **只有 `_resources/plan-view/app.js` 改变**。后台生命周期、Plan 数据与权限、页面 HTML/CSS、合约及 Skill／安装副本均未改动，没有重新设计方案或切换日常安装。

图片首次失败后，同版本资源复查返回 HTTP 200 时，页面对原图片自动重试一次；仍失败则保留临时占位，重新展开只重试该位置。原图位置、文件名及其他已加载图片保留。明确资源拒绝仍显示图片失败，busy 仍可重试；不会将复查成功落入永久失败分支。

内容请求使用 60 秒浏览器等待期限；current／activity 保持 10 秒轻量期限。请求超时或单一资源连接失败后，先合并为一次轻量 current 检查并核对原 revision。服务仍可用时保留页面与已加载内容，显示读取较慢及手动重试；每次点击只有一次有界读取，未完成请求不会被后台定时器反复重发。初始 overview 失败也保留状态位置及重试按钮。轻量检查自身超时属于尚未确认，不能声称服务退出；只有实际连接失败或 retiring 才使用离线提示。发现新版仍拒绝续读，不拼接内容。浏览器期限不等于服务端 CPU 计算期限，后台 pin 和退出规则保持原样。

### 新增验证

[真实浏览器脚本](../../../tests/run_plan_view_recovery_smoke.cjs)通过普通 CLI 取得页面，使用原有 1,200 项合成 Dataset 内的专用测试 Work。测试在 HTTP 边界注入故障／延迟，页面 JS、图片解码、DOM 操作和 AbortSignal 均由真实 Chrome 执行。没有重新准备媒体或访问真实用户 Plan。

旧 build-3 在两条针对性浏览器负例中均失败：[复现记录](../../../.local/plan-view-lifecycle/review-fixes/baseline/report.json)。修正源码和 build-4 wheel 以下 **9 项各自全部通过**：

| 场景 | 验证结果 |
| --- | --- |
| 原图片失败、复查 200 | 自动恢复，恰好一次探测与一次图片重试，无永久占位 |
| 12 秒正常 overview | 实际等待约 12.6 秒后加载成功；仅一次请求，无离线提示 |
| 图片重试再次失败 | 自动重试有界，重新展开可恢复，其他图片 DOM 不重建 |
| 明确图片失败／资源繁忙 | 永久资源失败与可重试 busy 保持区分 |
| 首次 overview 到期 | current 确认、初始状态位置保留、一次点击重试成功；当前入口正确绑定 revision |
| 分页到期 | 保留 50 组、展开状态和已载图片；同一游标重试后为 100 组，无重复追加 |
| 到期后探测到新版 | 提示过期，拒绝续读与旧内容拼接 |
| current 自身到期 | 不误报离线，不固定重试；显式重试后恢复 |
| current 确认连接失败 | 使用离线提示并停止自动探测循环 |

到期边界用测试侧缩短的 AbortSignal 触发，并核对内容请求实际配置为 60,000 ms；12 秒正常读取使用真实墙钟，没有缩短或绕过等待。源码和 wheel 的浏览器阶段前后 Dataset 全部保留数据摘要一致；专用 Work 的 create/update 仅发生在测试准备阶段。

[源码 9 项报告](../../../.local/plan-view-lifecycle/review-fixes/source-2/report.json)、[wheel 9 项报告](../../../.local/plan-view-lifecycle/review-fixes/installed/report.json)、[图片恢复截图](../../../.local/plan-view-lifecycle/review-fixes/installed/image-recovered.png)、[初次超时保留与重试截图](../../../.local/plan-view-lifecycle/review-fixes/installed/timeout-retry.png)、[12 秒后正常加载截图](../../../.local/plan-view-lifecycle/review-fixes/installed/slow-overview-loaded.png)、[最新合成入口回执](../../../.local/plan-view-lifecycle/review-fixes/installed/review-entry.json)可直接复核。

另外，build-4 的 artifact-only 内容核验通过，资源／合约／Skill 定向检查 **21 项通过**，见 [JUnit](../../../.local/plan-view-lifecycle/review-fixes/package-tests.xml)。JS 语法和差异空白检查通过。原 243 项、120/600 秒、40 标签和后台进程证据仍对应此前记录，本轮未重跑这些未改动的后台检查，也不将旧记录改写成 build-4 的新运行结果。

### 当前构建

[build-4 wheel](../../../.local/plan-view-lifecycle/build-4/wheel/mediasense-0.11.0-py3-none-any.whl) SHA-256：`ca37575bbb61f7b3ff7852f78c861f3f8291ff6b28925ff8ba45aa5a5fe3bde6`。

仍以 `e10abe8ed78a10205f6e00e1d70906f786ae74b2` 为导出基线，叠加明确的[文件清单](../../../.local/plan-view-lifecycle/build-4/included-paths.json)，沿用固定运行依赖版本并排除无关 PreCheck 工作区改动。[包内差异清单](../../../.local/plan-view-lifecycle/build-4/package-delta.json)证明唯一产品文件变化是 app.js。补修后源码与包内脚本摘要一致。

复现本次有界浏览器检查（复用已生成合成数据，不重跑准备或生产闲置周期）：

```sh
rtk proxy node tests/run_plan_view_recovery_smoke.cjs .local/plan-view-lifecycle/review-fixes/installed-config.json
```

本次为工程补修与自验，等待用户复核；没有发布、日常安装升级或真实方案确认。


## 日常安装补记（2026-09-15）

安装时发现日常环境已有另一路已接受的 PreCheck 效率修复，因此没有直接覆盖为 Plan-only build-4。已从固定源码构建两者合并包，保留所有 PreCheck 文件和原 59 项依赖，仅合入这次已验证的 Plan 相关差异。合并 wheel SHA-256 为 `d9e3d11b2f5a4edeec8d09aab8990d537539c2029980c03f378b460633f322fe`，原 Python 3.13.5、embeddings、配置和凭据保持不变。

相同日常环境的隔离安装基线、隔离及实际日常入口的九项浏览器恢复场景、global CLI smoke、四 Skill 的内容／manager hash／无关 lock 保留、原注册包装启动的新 MCP Host 均已通过。日常安装与 wheel 的 143 个包文件一致；详情以安装台账与[收据](../../../.local/releases/0.11.0-plan-view-20260915-203644/installation-receipt.json)为准。没有迁移真实数据或重跑业务，旧已保存 Work 可以正常 inspect 取得新预览入口。尚未产生可用 Result 的 PreCheck 运行仍只能看进度，不是这次升级取消数据兼容。

用户需要在原操作项目新开 Agent 会话加载新的工具与 Skills；新的诊断 Host 已验证，不代表旧会话热更新。安装后平时由普通 Plan 操作自动启动／复用页面服务，不增加 Agent 手动启停流程。


## 闲置时限与安装调整（2026-09-16）

用户明确反馈 10 分钟过短，要求改为 6 小时并安装，且本次不测试。当前默认服务闲置时限已改为 21,600 秒，缓存仍为 120 秒；现有时钟断言、生产长跑预期和当前设计／runbook／发布副本同步。前文 120／600 秒及浏览器记录保持其原构建、原参数含义，本次没有重新执行或声称完成 6 小时观测。

本次从前次已安装合并源码隔离构建，只有两个包文件变化，wheel SHA-256 为 `1675cc0b079398b17583387c84396af95e32417179b9580041fcfc7bfe94b291`。原 uv 全局 CLI 及项目四个 Skills 已更新；安装内容 143 文件、59 项原依赖、项目配置和 manager hash 核对完成，原预览进程正常停止并核验退出。没有业务数据操作，没有重启 Agent／MCP，会话验证及功能测试按用户要求未运行。详见[安装收据](../../../.local/releases/0.11.0-plan-view-6h-20260916-015303/installation-receipt.json)和[安装台账](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。


## 闲置时限再次调整与单例核对（2026-09-16）

用户决定继续使用按需服务，把 6 小时延长至 72 小时，不采用静态快照。当前 Runtime 默认值为 259,200 秒，缓存仍为 120 秒，单服务最多两份上下文。多客户端复用的边界与锁机制未变：同一用户／data home／确切安装构建共用一个服务，测试环境和不同安装另行隔离。安装前日常 data home 无预览进程；系统还有 16 个分属临时目录的旧测试实例，本次没有清理。

基于前次安装快照生成仅两个包文件变化的 wheel，SHA-256 为 `6bdb7179e2776a02c9e75e42886bb90aab1cf24eebfa9de090992c1e201d2e68`，并已更新原全局 CLI 与项目四个 Skills。实际安装参数、143 文件、59 项依赖、配置摘要及 manager hash 核对完成；按前次参数更新无需测试的要求，本次没有运行测试或 72 小时等待，没有重启业务 Agent／MCP，也没有操作真实 Dataset。现有测试时钟、长跑预期与外层运行期限已同步但未执行。详见[安装收据](../../../.local/releases/0.11.0-plan-view-72h-20260916-110723/installation-receipt.json)；历史 6 小时、10 分钟证据保持原义。


## 重缓存 1 小时与实际安装（2026-09-16）

用户所指真实页面在旧 120 秒缓存策略下，overview 冷重建 27.628 秒，随后复用 0.056 秒，相关只读诊断位于前次发布目录 `checks/resource-busy-diagnosis.json`。用户明确要求将 cache_idle 延长为 3,600 秒且不测试；service_idle 保持 259,200 秒，其余容量／等待策略不变。

新 wheel SHA-256 `6e5f8529ca8fcaa2317178fe368bc1e2a963af9545893aa30ceebded5075acbd` 已离线安装，原项目四个 Skills 同步，143 文件／59 原依赖／配置摘要和管理器 hash 核对完成。旧预览实际停止，新版预览进程报告的策略确认为 3600／259200 秒。仅核验安装内容与启动配置，没有绑定或更改真实 Dataset／Plan，没有执行测试，也没有进行一小时观测。详见[安装收据](../../../.local/releases/0.11.0-plan-cache-1h-20260916-135952/installation-receipt.json)和[进程策略](../../../.local/releases/0.11.0-plan-cache-1h-20260916-135952/checks/actual-runtime-policy.json)。
