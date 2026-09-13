# Plan 信息收集与可选工作保存：实现验收

## 当前基线重新验收与输入校验补修

2026-09-12 本轮任务开始时工作区干净，HEAD 为 `615c3359941927515f0c0a8738a3f08122bcad46`。`6acf1f5` 已包含本包实现、Skill、SQLite 增量升级、Preview 与此前四项补修，因此没有重复应用 contract.patch 或重写已完成实现。以下是本次实际执行的新证据；后文历史日常安装记录不代表已安装本次新构建。

### 本次改动

- `plan/work.py`：create/update 的偏好按既有正式 schema 校验，拒绝空偏好键；嵌套 JSON 的开放范围不变。无效偏好在 Read、候选分析和写入之前拒绝，组合请求不改变说明、候选或 revision，失败不占用 request_id。
- `inspect`：显式 `page.limit:null` 返回 `invalid_request`，仅省略时使用默认 limit；新 Work、有候选和已撤下三种状态一致。没有修改当前 schema 或预期错误码。
- `test_plan_optional_work.py` 新增 5 项语义反例；原实现上 5 项全部失败，补修后通过。实际 MCP runner 增加相同反例及失败后状态检查。既有 SQLite、Skill、Preview、Host 包装和确认通道不需要再次修改。

### 实际验证

| 验收面 | 本轮结果与范围 |
| --- | --- |
| 三字段保存、读取、身份及恢复 | 源码专项 **234 passed，25.99 s**；含 52 组三字段组合、无候选、长文本精确读回、错误组合原子性、零 Read/候选分析、保存候选不解码、同值新 revision、幂等重放、旧 cursor/版本、闭合、seal reservation 恢复，以及线程/跨进程竞争、取消、提交中崩溃和响应丢失 |
| 默认全集 | 同一隔离源码快照首次 **1292 passed、4 failed、16 deselected，138.69 s**；4 项均在 `socket.bind` 被沙箱阻止。仅放行本机回环后重跑这 4 项，**4 passed，0.18 s**。因此选中的 **1296 项已全部通过**，不是宣称一次运行全绿；16 项为原有 local_fixture/scale 排除 |
| 安装包专项 | CPython **3.11.13**、core 依赖、pytest 9.1.1；从 checkout 外运行，删除 PYTHONPATH、`-o pythonpath=''`，**234 passed，24.82 s**。实际 import 来自本轮 `install/lib/python3.11/site-packages/mediasense` |
| 实际 MCP | 新临时合成 Dataset，**42 次 stdio MCP 调用通过**：create、notes-only、默认读取、重启、完整候选、非法候选/偏好拒绝、撤下、字段清空、预览、缺失/错误确认、纯说明更新后的旧版本拒绝、同内容当前版本冻结与重放。所有业务返回仅一份 structuredContent、content=[]，**elicitation=0**；成功冻结的三处 plan_ref 一致 |
| Preview | 原 Result、原两项 Evidence 选集及 limit=16 的字节分页续读通过，第二页准备 JPEG 完整解码 **80×40**；HTML 包含同一候选身份、决定说明、Source Set、引用和转义后的脚本文字。无候选拒绝最终 Preview。独立 Chrome DOM 观察到 complete=true、naturalWidth=80、naturalHeight=40；浏览器退出超时另记下文 |
| Agent 工作流 | 独立 Agent 只获得当前 Skill/合约及原始合成场景，未读取旧验收结论。六类场景（文件可读/不可读分支共七条路径）产生中文回复、来源/范围判断与请求；**24 条 Plan、5 条 Read 请求**通过 schema 检查。主 Agent 复核后，24 条 Plan 请求以实际返回的不透明引用绑定，在隔离安装 Tool＋合成 Read 上逐条执行成功；仅完整 HTML 后明确接受的合成分支 seal |
| 打包与一致性 | 离线 distribution smoke 的安装、CLI/doctor、七 Tool discovery/dispatch、12 个 Skill 文件、卸载通过；**128 个 package 文件**与隔离源码逐字节一致。Ruff、Skill quick_validate 和 diff whitespace 检查通过 |

行为验收中，单张照片左侧人物身份未传播到其他成员；补充文件区分路径、内容和解释；充分信息直接形成候选；未知/未答复不制造答案；实质冲突撤下旧候选；局部纠正不充当全案接受。没有固定调查顺序、必问节点或每轮保存要求。合成视觉与用户接受是明确测试前提，不声称认证了真实媒体语义或真实人类事件。

### 构建身份与复跑

本轮产物根目录：`/private/tmp/mediasense-plan-reaccept-6p3o8lhs/`。从上述 commit 的 `git archive` 导出，仅覆盖本次三个代码/测试文件；`implementation.patch` SHA-256 为 `998ff87ae3df3c697cb9420a0f4bfc51f06ed2dbfbdefd03d4eaf5d3eca89822`。没有纳入过程中其他任务新增的敏感性变更文档。

- wheel：`wheel/mediasense-0.10.2-py3-none-any.whl`；SHA-256 **`f6a8b56645b8f60cdc3734c3887406eb330f122c2585e3e0b40addf7f039db45`**。
- core 约束从该快照 uv.lock 以 `--locked --offline --no-dev --no-emit-project --no-hashes` 导出；`dependencies.txt` SHA-256 `2ce899b23c7c1d4896f7c0ae7c378de7078f4afc7459b9f9693650feb8b91b11`。未下载或运行模型，未调用地图服务。
- `build-verification.json`、`default-tests.xml`、`loopback-tests.xml`、`installed-tests.xml`、对应日志保存精确环境和结果。独立推演见 `agent-workflows.md`，原请求见 `agent-workflow-requests.json`，实际重放见 `agent-workflow-replay.json`。
- MCP 完整轨迹：`mcp-complete/report.json`，HTML：`mcp-complete/preview.html`；候选 identity `sha256:dbb3a7a21abc90b445cf654cf627cb3ec837da22279ce6c5d0d5d0eff4588989`。源 JPEG 前后 SHA-256 同为 `68e5efb8145b31e6ce2d4062a97e3cb23edf37940cf3ba5e3f6fefcd625a991a`。

复跑使用本轮安装的 Python，删除 PYTHONPATH、设置临时 MEDIASENSE_CONFIG_HOME/DATA_HOME，执行快照内 `tests/run_plan_interaction_smoke.py --host <本轮 install/bin/mediasense> --output <新的临时目录> --paged-preview`。安装包专项沿用上表十个 Plan/Frozen Plan 测试文件，并禁用 pytest 的源码 pythonpath。构建、依赖组合和受测入口均与历史 wheel 分开记录；同为 0.10.2 不意味着字节相同。

### 失败记录、限制与交付判断

首次 distribution runner 被沙箱禁止读取 uv 缓存的 `.git` 标记，放行相同离线临时安装后通过，未切换全局工具。可选 `--browser` 的首次 MCP 运行在 Chrome 启动时 SIGABRT，不能作为完整 MCP 成功证据；新目录不带该选项的完整 42 次调用通过。独立 Chrome 两次在 40 秒退出等待上超时，第二次保留的 stdout 已含完整 DOM 和成功图片加载结果。`browser-timeout.json`、`browser-dom.html`、`browser-observation.json` 分别保留超时诊断及可证实的加载；没有把超时改写为浏览器 runner 正常通过。检查时没有本次临时 profile 的残留 Chrome 主进程。

**本轮达到限定范围内的源码和隔离 wheel 可交付状态。** Chrome 自动化退出仍有环境限制，但实际 DOM 图片加载已取得证据。没有切换全局安装、写入业务 Plan/Result、操作真实媒体、执行真实 Apply 或增加外部服务调用；历史日常安装仍停留在它自己的构建。未来切换须按唯一安装 runbook 验证实际依赖与会话。本轮不认证所有未来 Agent 的语义质量、真实人类身份、多 TB/任意大文本吞吐、真实地图/模型质量或其他 OS。原有确认顺序仍为用户看确切 HTML、聊天明确接受、Agent 传递同内容接受、Tool 冻结。

## 历史交付记录

2026-09-12：用户确认此前四项问题均已独立复核闭合，并授权按唯一安装 runbook 执行日常升级。本次机器 CLI、操作项目四个 Skills/lock 和原 MCP 启动链路已完成切换与验证；现有 Agent 会话不声称已重载，需在操作项目中新开会话核对。各轮失败与证据继续保留。

首轮记录认证源码与实际隔离 wheel 的限定路径；不认证日常 Host 已升级，也不把合成聊天当作真实人类事件。当前承诺仍由 `docs/spec/contract/` 维护，`contract.patch` 未重复应用。

## 日常环境升级（2026-09-12）

采用用户指定 wheel，未从并行修改的工作区重建。稳定保留位置：`.local/releases/0.10.2-plan-work-20260912/wheel/mediasense-0.10.2-py3-none-any.whl`；SHA-256 **`1c454027d2f6b5217e3c3b4f0f6a0f86a7e523bdc4ea282565e0008ce2a4e5e7`**。本节路径中 `.local/` 均相对 MediaSense 仓库，目录已被 Git 忽略。

| 目标 | 实际切换与核对 |
| --- | --- |
| 日常 CLI | `/Users/chengyanru/.local/bin/mediasense` → `/Users/chengyanru/.local/share/uv/tools/mediasense/bin/mediasense`。原 uv 0.7.13 执行离线 force 安装，只替换 MediaSense 包；同为0.10.2，旧 wheel 哈希 `68e4ec3152091285513724b84f92cce9aad04968b5e2f46313dd234b1f03302c` 已保留 |
| Python／依赖 | 保留独立解释器 `/Users/chengyanru/.local/share/uv/python/cpython-3.13.5-macos-aarch64-none/bin/python3`、`embeddings` extra、全部 **59 项**依赖版本，新增/删除/版本变化均为0。继续使用保留的 DINO 依赖 wheel 目录作为 find-links，无下载或模型执行 |
| 操作项目 | `/Users/chengyanru/Downloads/ai-album-hk-representative-v1`，不把源码仓库当作 Honeycomb。原四个 Skill 无本地定制，无更高层同名副本；不读取此目录的真实媒体作为验收输入 |
| Skills／lock | 原 `npx --offline skills@1.5.25`、Codex目标、四名allowlist、关闭遥测。四个 Skill 共 **12 文件**与选定 wheel 一致，native localeCompare＋SHA256(path+content) 的 computedHash 全部匹配。lock 来源明确改为稳定 `wheel-export/mediasense/_resources/skills`；原锁没有无关条目，仍检查无额外条目与无关变更 |
| MCP／配置 | `.codex/config.toml` 中原 `/bin/sh -c '. /Users/chengyanru/.config/dotfiles/secrets/mediasense.zsh && exec /Users/chengyanru/.local/bin/mediasense mcp'` 保持原字节。凭据加载文件、用户 `config.toml`（包括已启用 DINO/0.311）SHA-256 均未变；凭据值未输出或复制到发布目录 |
| Host 生命周期 | 替换前再次核对进程，没有日常 MediaSense Host；实际 Dataset 无打开句柄。无需退休进程，没有中断任何 Agent。验收时新建的 stdio Host 随连接正常关闭 |

### 备份与依赖组合验证

稳定发布目录的 `before/` 保存旧 wheel、uv receipt、59项依赖、四个 Skills、原 lock、项目 MCP TOML、用户配置。凭据加载脚本只记录路径和哈希，原文件保留不改写。

唯一已定位业务 workspace 为 `/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e`，对应 `dataset:6581e19d4fe94e26a10e2f5ca1b34c9b`。只读 `dataset inspect` 确认格式；无 writer/句柄时用 SQLite backup API 备份 PreCheck、Plan、Geo、Apply 四个数据库，逐个 integrity_check=ok，同时备份 manifest 和两份 sealed Result。原 Artifact 和源媒体留在原处且不修改，不声称制作了全量媒体备份。保留状态中两个 PreCheck Run 已完成、两个 Plan Work 为 open；没有恢复任何业务任务。

在备份的独立 Plan DB 副本上验证 v3 加列：两个 Work、四份请求回执、cursor key 全部保留，工作说明初始为空；原数据库未打开为 Runtime、未迁移，安装前后所有已记录状态文件哈希相同。

先以完全相同的 Python3.13.5＋embeddings＋59依赖，在 `/private/tmp/mediasense-plan-daily-profile/` 离线安装目标包，确认依赖变化为0。该组合的完整 distribution smoke 和 **36次 Plan MCP** 验证通过后才切换。未把之前 Python3.11 core 验收冒充日常依赖组合验证，也没有移除 extras。

### 实际安装验证及会话边界

- 实际 **127 个包文件**与 wheel 逐字节一致；安装收据指向稳定 wheel；四个 Skill 的12文件及4个锁哈希一致。
- 原注册命令、原凭据包装、实际项目 cwd 启动的新 Host：初始化0.10.2、七 Tool 的 contract ID/digest 全部匹配 wheel。Plan Work digest 为 `sha256:63676aa36966bea23024ae2538ef4830cc2ce8e42b0af8554c28dbd5a37478e1`。同一包装下 doctor=ok，DINO prerequisites=prepared、execution=not_checked；不进行模型推理。
- 精确日常 CLI 的 `run_global_cli_smoke.py` 通过；只使用临时空 Dataset。通过从原注册内容生成的验证 harness，再运行 `run_plan_interaction_smoke.py --paged-preview`，**36次 MCP 调用通过**。此 harness 未替换项目注册，仅在项目 cwd 执行其原 command/args。
- 新合成 Dataset 验证说明保存、重启、非法候选原子拒绝、撤下、相同两条 Evidence 的字节分页、准备图片80×40完整解码、缺失／错误确认拒绝、正确冻结与重放。源图片字节不变、零新MCP弹窗，模型/Geo/真实媒体 Apply 调用均为0。测试用临时配置关闭模型，不改变日常用户配置。
- 完整实际轨迹 `/private/tmp/mediasense-plan-daily-upgrade-verified/report.json`，HTML 同目录 `preview.html`；报告已复制到稳定发布目录 `evidence/actual-plan-smoke.json`。冻结 identity 为 `sha256:5ed23afb14a3afda5e519dd59ab32ead126298243139b4c9efae0e27698f2039`。这仍是合成 trusted client context，不扩大为真实人类身份认证。
- 稳定 `installation-receipt.json`、`evidence/actual-installation-verification.json`、`doctor-actual-launcher.json`、`skill-lock-verification.json`、安装前后 uv receipt/lock、`isolated-profile.json` 和 SQLite 备份清单记录精确结果。没有将这些原始输出、wheel、数据库或媒体加入 Git。

**仍需用户在 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` 新开 Agent 会话**，确认加载四个项目 Skills、重新发现七个 MediaSense Tools，并核对上述 Plan Work 合约 digest／新 Host。机器安装与独立新连接已验证；本次当前 Agent 会话不在该操作项目，也没有声称旧会话热重载。该会话交接不授权恢复真实 Run、调用地图/模型或 Apply。

### 回滚与本次失败记录

回滚前按唯一 runbook 正常退出受影响 Host，确认没有会被覆盖的后续业务写入。使用保留的旧 wheel、同一个 Python／extras／依赖约束，并由原 Skill manager 恢复原保留来源；配置本次未改，不需覆盖。具体 CLI 回退命令为：

```sh
rtk proxy uv tool install --offline --force --no-python-downloads \
  --python /Users/chengyanru/.local/share/uv/python/cpython-3.13.5-macos-aarch64-none/bin/python3 \
  --constraints /Users/chengyanru/repos/personal/mediasense/.local/releases/0.10.2-plan-work-20260912/dependencies.txt \
  --find-links /Users/chengyanru/repos/personal/mediasense/.local/releases/0.10.1-dinov3-20260912/dependencies \
  '/Users/chengyanru/repos/personal/mediasense/.local/releases/0.10.2-plan-work-20260912/before/mediasense-0.10.2-py3-none-any.whl[embeddings]'
```

在上述操作项目中，用 `npx --offline skills@1.5.25 add /Users/chengyanru/repos/personal/mediasense/.local/releases/0.10.2-manufacturers-20260912/candidate-02/source --skill mediasense mediasense-precheck mediasense-plan mediasense-apply -a codex --full-depth -y` 恢复，仍设置 DISABLE_TELEMETRY/DO_NOT_TRACK；核对 `before/skills` 与原四个锁条目。原来源已再次与备份逐字节核对。不要手写锁记录。原业务数据库本次没有迁移，不应无故恢复备份；以后若有不兼容状态变化，应按 runbook 评估整套一致性恢复，不能只覆盖 Plan DB 或丢弃新工作。

本次检查器第一次误以为所有 `.tool.json` 都有 `$id`，在 PreCheck 合约处停止；现有 descriptor 本来会推导其 contract ID，修正检查器后通过，未修改产品。因该检查尚未生成 launcher harness，随后的第一次实际 Plan smoke 在启动前报文件不存在，没有 MCP 调用或真实 Dataset 写入；使用已核对的 harness 和新临时目录完整重跑通过。记录与失败版本脚本保留在 `evidence/verification-failures.json`、`verify_actual.first-attempt.py`。此前开发、浏览器超时和环境失败记录继续保留在下文。

## 最新补修：选定 Evidence 的字节分页

用户复现：已选两条 Evidence，元数据合计超过 512 KiB 响应上限；第一页是非图片，第二页有可解码图片。原渲染器只收第一页，错误显示 unavailable。未扩大扫描或修改设计。

- `preview.py` 现在续读直到 `next_cursor:null`。每页保持原 Result、原 Evidence 列表及 limit=16，仅更新 cursor；查询仍不超过原先选定的 16 条 Evidence。
- 全部页面读完才更新本次 build 的 Evidence 缓存。重复 cursor、空页却仍有 continuation、超过选集可支持的分页次数均明确失败；Read 续读错误不转换为“没有图片”。失败不覆盖已有完整 HTML。
- `test_preview_follows_byte_limited_review_to_image_on_second_page` 使用真实合成 Result、真实 Read 和两项各 300,000 字符的 Observation，不伪造成功分页。三条可用 Evidence 中只选两条，第一条改为合法 inline 材料，第二条保留准备图片。旧 wheel `31be3b85…` 上实际复现仅一次 Read；修复后两次请求的选集完全相同、第二页图片解码为 20×10 并进入 HTML。另两分支验证重复 cursor 与续读失败时不发布部分预览。
- 源码相关测试 **136 passed，9.43 s**；新隔离 wheel 专项 **229 passed，30.07 s**。本轮是局部分页补修，没有重复上轮 1288 项默认全集；其结果仍按上轮构建记录，不改写为本轮结果。Ruff、diff 检查、wheel 字节一致性及完整 distribution smoke 通过。

### 本轮实际入口

- wheel：`/private/tmp/mediasense-plan-pagination-wheel/mediasense-0.10.2-py3-none-any.whl`，SHA-256 **`1c454027d2f6b5217e3c3b4f0f6a0f86a7e523bdc4ea282565e0008ce2a4e5e7`**；源码包文件仍为 127 个。约束、core 依赖和 CPython 3.11.13 沿用；独立安装 `/private/tmp/mediasense-plan-pagination-install/`，未覆盖此前环境。
- `run_plan_interaction_smoke.py --paged-preview` 新增可复跑的合成大元数据场景，在实际安装包上完整执行 **36 次 MCP 调用**。创建、说明保存、重启、候选、非法输入、撤下、预览、可信上下文、seal 和重放均通过；零 elicitation、源文件字节不变。
- 完整业务轨迹及预览 Read 分页摘要：`/private/tmp/mediasense-plan-pagination-complete/report.json`。其中 `preview_pages` 明确记录第一页 inline、stop_reason=byte_limit，第二页 local_artifact、next_cursor=null；两次 request 只差 cursor，选择数量均为 2，limit 均为 16。
- 最终 HTML：`/private/tmp/mediasense-plan-pagination-complete/preview.html`；图片通过完整解码，80×40。Candidate identity：`sha256:b2a74700f7a6b8b2c2e0e925b5b3c9f290484cf659fb9da38a71342087a941b1`。
- 浏览器验证单独保留在 `/private/tmp/mediasense-plan-pagination-acceptance/browser-images.json` 和 `browser-dom.html`：该目录是同一 wheel、同一分页场景的前一次隔离运行，Chrome 观察到 complete=true、naturalWidth=80、naturalHeight=40。它不是上述最终冻结 Work 的另一份身份声明。
- 失败记录：首次带 `--browser` 的业务脚本在 Chrome 子进程等待退出时超过 40 秒，未将该次运行宣称为完整业务通过。随后不带可选浏览器参数重跑完整 MCP 流程成功，并独立启动测试 profile 读取已生成 HTML；取得 DOM 图片证据后，只清理本次启动的浏览器进程组。没有使用个人浏览器配置。

复跑业务命令：使用本轮隔离 Python，删除 PYTHONPATH、设置临时 MEDIASENSE_CONFIG_HOME/DATA_HOME，运行 `tests/run_plan_interaction_smoke.py --host /private/tmp/mediasense-plan-pagination-install/bin/mediasense --output <新的临时目录> --paged-preview`。契约、全局安装、真实 Dataset 及真实媒体 Apply 均未变更。

## 用户复核后的三处补修

本节是上一轮记录，用户独立复跑 63 项检查、8 组非法候选及实际图片显示后确认这三项通过。下面保留的首轮测试数量、旧 wheel 和 24 次轨迹只证明其原来覆盖的路径；不能据此抹去用户指出的缺口。没有重开设计或修改定稿 schema。

| 复核问题 | 补修与阻断位置 | 新增反例及运行证据 |
| --- | --- | --- |
| P1：Candidate 夹带 plan_ref 可覆盖 Tool 身份 | `_candidate.py` 在构造 sealedContent、遍历内容或读取 Result 前，按当前 Plan Work 的 Candidate schema 校验原始输入；本地 registry 解析 Frozen Plan 定义。materialize 另拒绝 contract/plan_ref/seal，不允许输入覆盖 Tool 字段 | 直接 Tool 和 MCP 分别提交 plan_ref、正确值的 contract、seal；全部 candidate_invalid，notes/preferences/Candidate/revision 均不变。之后成功 seal 的外层 plan_ref、sealed_content.plan_ref、预留 plan_ref 一致 |
| P2：存在准备图片却显示 unavailable | 默认 Preview 通过公共 Read 的 source expand covering_evidence，再以 review.evidence_refs 取得真实 access 与 source_items。图片 URI 来自经过 Read 验证的 local_artifact；实际来源用于标签，不能由 represents 推断。成功解码后才展示 | 真实 Accounting/Rendition/ResultStore 生成的合成 Dataset，来源 locator 相对而 Evidence 路径绝对，图片成功显示。缺失／损坏 artifact 保持 unavailable；实际来源在组外的图片不冒充组内样本 |
| P2：other_outcomes 的 null/数字变成内部故障 | 结构错误在字段遍历前返回校验问题，经 Work 转为 candidate_invalid；不广泛捕获未知异常冒充业务错误 | `other_outcomes:[null]`、`other_outcomes:1`、groups/decision_notes 中的 null、scope:null 在 Read 前拒绝；实际 MCP 返回候选错误而非 host_operation_failed |

预览仍是派生视图，未增加 Tool 或原件托管。默认按每组至多 16 个候选来源和至多 16 个 Evidence 进行一次有界选择、显示至多两张图片，并复用本次 build 的 Evidence 读取结果。未声称读取每个成员或能在所有未选材料里搜到图片；调用方仍可使用既有 asset_resolver 自定义展示。说明保存路径完全不执行这些 Preview 读取。

### 上轮隔离构建与证据

- wheel：`/private/tmp/mediasense-plan-review-fixes-final/mediasense-0.10.2-py3-none-any.whl`；SHA-256 **`31be3b85e6cd29f08c48f17dab15bfd06a55df5ab50fca07c302f1d9e790e438`**。仍使用原 core 锁定约束、CPython 3.11.13，无模型 extras；版本号不代表首轮与补修构建相同。
- 独立安装：`/private/tmp/mediasense-plan-review-install/`。未覆盖首轮安装或其验收目录，更未切换全局安装。实际 import 来自该目录的 `site-packages/mediasense`。
- 安装包专项 **226 passed，23.19 s**：`-o pythonpath=''`、删除 PYTHONPATH、checkout 外运行。源码相关契约／Plan／Host 回归 **239 passed，31.23 s**；有界图片读取的最后调整另跑 Preview **13 passed**。最终默认全集使用临时配置并允许本地回环测试：**1288 passed、16 deselected，238.93 s**。
- `run_distribution_smoke.py` 离线安装、CLI/doctor、Skill、MCP discovery/dispatch/卸载通过；最终 wheel 与当前 package 文件字节一致。Ruff 和 diff whitespace 检查通过。
- 更新后的 `run_plan_interaction_smoke.py` 完成 **35 次真实 stdio MCP 调用**，包括五组非法输入及每次失败后的相同 inspect；成功 seal 与重放核对 Plan 编号一致。所有业务返回仍在单一 structuredContent，零 MCP elicitation。
- 新轨迹：`/private/tmp/mediasense-plan-review-acceptance/report.json`；新 HTML：同目录 `preview.html`；浏览器检查：`browser-images.json`；实际页面截图 `preview.png` 已目视确认紫色样本、目录、决定说明和引用均呈现。Candidate identity：`sha256:22bd976f13739bb9643ec4d042c0bc2352bf4f77bc788a75d632f39945559ccb`。
- HTML 中实际 img.src 指向该临时 Dataset 的准备 JPEG；Pillow 完整解码 **80×40**，独立 headless Chrome 在全新测试 profile 中得到 **complete=true、naturalWidth=80、naturalHeight=40**。这次不再以 HTML 生成或存在路径代替图片可显示证据。Chrome 检查通过 runner 的 `--browser` 参数执行，可选浏览器不属于 wheel 依赖。
- 源 JPEG 字节仍为 `68e5efb8145b31e6ce2d4062a97e3cb23edf37940cf3ba5e3f6fefcd625a991a`，未调用模型、Geo 或真实媒体 Apply。输入反例和文件损坏测试只作用于新建的合成 Dataset。

新增测试改变了“缺少排除理由”的内部诊断：schema 已拒绝时直接返回 schema_violation；只有结构合法但理由为空白的情形才执行语义检查。公共返回仍为 candidate_invalid，没有改动契约错误语义。

复跑实际入口：使用新隔离 Python 执行 `tests/run_plan_interaction_smoke.py --host /private/tmp/mediasense-plan-review-install/bin/mediasense --output <新的临时目录> --browser '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'`，同时删除 PYTHONPATH 并设置临时 MEDIASENSE_CONFIG_HOME/DATA_HOME。Browser profile 归该测试输出目录，不使用个人会话。

## 实现及归属

- `plan/work.py`、`plan/_sqlite.py`：既有 Work 增加可选说明；三字段省略／替换／清空独立且原子。说明／偏好／撤下不分析 Candidate、不调用 Read、模型或 Geo；预检只取 Work 元数据，候选保留在 SQL 中，不反序列化或遍历媒体。新接受请求总有新 revision，原请求重放恢复原回执。
- 沿用同一 Work 的进程锁、取消检查、提交门、请求回执和 seal reservation。无候选默认 inspect 返回 null、candidate_missing、无 identity；分页仍校验形状、revision、cursor。闭合 Work 只读。
- v3 SQLite 增量加列，事务内串行检查与 ALTER；保留现有 Work、候选、revision、plan_ref、回执、cursor key、seal reservation。不是重建数据库或改写 Result/Frozen Plan。安装 runbook 及 packaged 副本同步说明这个增量边界。
- `mediasense-plan/SKILL.md`：信息充分性归 Agent；主动调查用户知识、背景和材料，按影响、支持、成本和注意力判断提问时机。完整候选检查只约束候选提交。工作说明可提前保存；实质冲突明确保留／替换／撤下。最终 HTML 后聊天接受建立第四项 Human confirmed，不循环要求先确认才能请求确认。
- `plan/preview.py`：派生文档保存精确 decision_notes；HTML 展示说明、完整适用 Source Set 和已有 Evidence 引用，文本经 HTML escape，不访问说明中的路径。说明和偏好不进入 Frozen Plan。
- 实际安装发现并修复两处入口缺陷：MCP 广告 schema 内嵌随包 Frozen Plan 资源，客户端不用联网解析其绝对 `$ref`；Frozen Plan 默认加载器读取随包资源，移除对历史源码文档路径的依赖。两项均保持当前契约含义。

基线是共享工作区 HEAD `20b86a987714e630344d10df9e3807141a8d8474` 加本次开始时已有的并行变更。未回滚厂商知识、模型或安装相关工作，未创建提交。wheel 包含构建时整个工作区源码；下述认证只覆盖这里列明的行为，不能借同为 0.10.2 宣称日常安装具备新功能。

## 确定性验收映射

| 承诺与失败边界 | 运行证据 |
| --- | --- |
| 三字段独立保留／替换／清空，已有及无 Candidate | `test_plan_optional_work.py` 的 26 种非空组合 × 两种起点；比较全部保存字段、revision、identity、plan_ref，重放并校验返回 schema |
| 错误字段、部分 Candidate、错误覆盖组合全部不保存 | 类型／额外字段反例及重复成员的合法形状 Candidate；失败前后完整 snapshot 相等 |
| 长说明完整保存、重启、同值新 revision | 含中文、CRLF、NUL、组合 Unicode 和 emoji 的重复长字符串精确比较；重启重放、同值不同请求、省略与 null 的幂等冲突 |
| 轻量更新零 Read／Candidate 分析，不遍历保存的媒体 | Read 与分析入口设为必失败；保存的 Candidate JSON 放置不可解码哨兵，说明／偏好仍成功保留 identity，撤下清空两者 |
| 并发、取消、崩溃和失联 | execution/process/MCP/replay 测试；完整候选 owner 与说明 waiter 跨进程竞争，存活 owner 提交后 waiter 冲突，owner 退出后 waiter 接管；说明提交前取消、事务内崩溃、提交后失联回执恢复 |
| 读取与闭合、预留恢复 | 缺候选合法分页为 null；旧 cursor、错误形状和旧 revision 被拒；notes 不绕过 pending seal，重启后可恢复；闭合 Work 可读说明但不能改写 |
| Preview 含义、转义与身份 | decision_notes 全文、Source Set、Evidence 引用与同一 identity；脚本字符仅为文本；无 Candidate 拒绝最终 Preview |
| 最终确认边界 | 缺失／不匹配上下文拒绝；说明更新使旧 revision 冲突；重新 inspect 后相同 identity 可沿用仍有效的上下文；冻结不携带 working_notes |
| 实际入口与打包 | 自包含 MCP schema 测试、下面的 24 次实际 stdio MCP 调用、默认资源加载和已安装 Python 的 209 项检查 |

这些测试验证保存和机制，不替 Agent 判断说明是否足够、候选语义是否正确或用户是否真正接受。

## Agent 代表性行为验收

依 skill-creator 的独立前向验证要求，另一 Agent 只接收修改后的 Skill、当前契约和六类合成场景，独立产生用户可见对话、采用／待定判断与 Tool 请求。主 Agent 复核了请求及确认范围；未通过词语搜索替代行为判断。完整临时推演位于 `/private/tmp/mediasense-plan-behavior.md`，不把原始模型输出加入 Git。以下保留影响验收结论的内容和边界。

| 场景输入 | 观察到的回复／动作 | 判断及仍未证明的部分 |
| --- | --- | --- |
| 聚会代表照片有三人；用户仅认出左边小林 | 回复“保留对这张照片左侧的辨认”，组名暂用室内聚餐；notes 指明只适用 a，不扩展至代表成员 b/c | 正确保留人物与范围；画面与边界读取是合成输入，不认证真实视觉辨认 |
| 用户提供活动安排文本 | 可读分支先读取，再将事前安排与照片时间／画面匹配；不可读分支明确“还没看到内容”，请求贴出有关文本并继续独立场景调查 | 区分收到、读到、解释；不将路径当托管或 Evidence 引用，不自动重开 PreCheck |
| 公园和咖啡馆证据充分 | 不强制提问或每轮保存，直接提交完整两组 Candidate，inspect 后展示 HTML | 候选有完整三项账目与必要说明，Human confirmed 仍待聊天接受 |
| 用户不记得／未回复聚会身份 | 不猜毕业或同事；前者可提出有依据的室内聚餐粗分类，后者先处理独立公园部分、保存未决后果 | 不把未回复当批准；粗分类是否满足实际找回目的仍由真实用户审阅 |
| 旧 Candidate 的同事聚会标签与用户新信息冲突 | 先原子提交 `candidate_content:null` 和 scoped notes，再独立 expand b 的观察；完整替代未成熟不冻结旧方案 | 撤下使旧候选不可封存；没有只写反对说明却保留为最终内容 |
| 用户只纠正餐厅为咖啡馆 | 整体替换 Candidate，decision_notes 记录局部来源；inspect 获取新 identity，展示完整 HTML，再询问是否接受整份计划 | 只有后续“看过这份 HTML，整份计划我接受”才建立完整接受；Tool transport 与实际人类事件分别认证 |

推演未发现当前 Skill 与契约的直接矛盾。方法、输入形式、调查顺序和轮数保持开放。该结果覆盖这些代表性职责路径，不承诺所有未来 Agent、输入和用户都能得到同等语义质量。

## 首轮隔离交付（保留证据，已被复核收窄）

最终 wheel：`/private/tmp/mediasense-plan-release-complete/mediasense-0.10.2-py3-none-any.whl`。

- SHA-256：`c6623dd6e96612a816d16ff2363d9d2e58c44439300430fe5478c8c0b7cc3a66`。
- 离线 `uv.lock` core 约束：`/private/tmp/mediasense-plan-dependencies.txt`，SHA-256 `88429af7616119a08cd84cbb2eff6937b3a9b8bd3b2d6b3ec21d55d40b2cf8a6`；无模型 extras。测试依赖另外离线安装已有缓存中的 pytest 9.1.1，不变更运行依赖。
- CPython 3.11.13；真实包位置 `/private/tmp/mediasense-plan-isolated/lib/python3.11/site-packages/mediasense/`，真实 Host `/private/tmp/mediasense-plan-isolated/bin/mediasense`。
- `run_distribution_smoke.py`：最终 wheel 与源码、所有发布 schema/Skill/runbook 字节一致；离线隔离工具安装、CLI/doctor、七 Tool MCP discovery、最小派发、Skill 安装和隔离卸载通过。
- `run_plan_interaction_smoke.py`：24 次真实 MCP 调用通过；单一 structuredContent、content=[]；跨三次 Plan 连接验证说明保留和候选撤下重启，之后完整候选恢复、HTML、缺失／错误确认、旧 revision、最新 revision 封存与重放。零 MCP elicitation。
- 结果与完整调用轨迹：`/private/tmp/mediasense-plan-acceptance-complete/report.json`；实际 HTML：同目录 `preview.html`。Candidate identity 为 `sha256:fe0620f5ee23564d5d8b81c1352f9a04047f52b792b6b890c804428cda582aa1`。
- 使用一张临时生成的紫色 JPEG，经已安装的真实 Accounting/Rendition/ResultStore 生成封存 Result，再由生产 composition/Read 消费。媒体原字节 SHA-256 前后相同：`68e5efb8145b31e6ce2d4062a97e3cb23edf37940cf3ba5e3f6fefcd625a991a`。没有真实媒体、Geo、模型或 Apply 调用。

复跑入口（使用新的输出目录；不设置 checkout PYTHONPATH）：

```sh
rtk proxy env -u PYTHONPATH \
  MEDIASENSE_CONFIG_HOME=/private/tmp/plan-check-config \
  MEDIASENSE_DATA_HOME=/private/tmp/plan-check-data \
  /private/tmp/mediasense-plan-isolated/bin/python \
  tests/run_plan_interaction_smoke.py \
  --host /private/tmp/mediasense-plan-isolated/bin/mediasense \
  --output /private/tmp/plan-check-new
```

## 首轮测试结果与失败记录

- 最终隔离 wheel：Plan Work/Frozen Plan 合约、Candidate、可选保存、execution/replay/process/MCP、Preview 共 **209 passed，18.70 s**；`-o pythonpath=''` 且删除 PYTHONPATH，从 checkout 外运行。
- 源码相关契约／Plan／Host／发布版本检查先通过 **238 项**；随后请求形状补测及默认 schema 路径修复分别通过 **107 项**、**26 项**。最终默认全集使用临时 MEDIASENSE_CONFIG_HOME／MEDIASENSE_DATA_HOME，并仅为本地回环测试解除 sandbox 限制：**1271 passed、16 deselected，228.83 s**。被排除的是仓库原有 local_fixture/scale 标记，不是失败用例。
- Ruff、Skill quick_validate、wheel 字节一致性及 distribution smoke 均通过。
- 默认全集首轮 **1261 passed、5 failed、16 deselected**：四项为 sandbox 禁止 127.0.0.1 监听，一项被机器已有 DINOv3 配置污染而阻塞（测试环境 NumPy 不匹配）。临时配置及所需回环权限重跑对应文件 **6 passed**；未改模型配置或弱化断言。
- 首轮实际完整 Candidate MCP inspect 失败于客户端获取外部 schema URI；修复广告 schema 后通过。安装包测试收集失败于默认 schema 指向历史 checkout 文档；修复随包资源路径后 209 项通过。保留这些失败原因，以免以后只运行 create 或源码测试就漏掉实际入口。

## 未认证范围与重开条件

开发验收阶段没有切换全局安装或日常 Honeycomb；本次日常升级的机器／会话边界另见上文。没有对外发布版本或执行真实媒体 Apply。没有香港原事件重跑、真实地图或模型质量／成本比较、多 TB 吞吐、任意大说明吞吐或所有 OS 的认证。临时验收文件可删除，Git 中保留的是可重跑入口与必要结论。

确认测试传入合成 trusted client context，证明传输与 exact-content/revision 核对；不独立证明真实人类身份、看图或点击。真实 Agent 仍须根据实际聊天保存接受对象、范围及有效性。外部原件不由文字路径自动托管。

如发现有效接受被错误扩展、重要说明未进预览、轻量更新调用 Read／模型／Geo、并发或取消导致部分写入、旧 cursor 被接受，或最终 wheel 不能走同一条入口，应重开对应验收。新的语义质量证据或真实媒体差异另行更新迁移台账，不改写旧 Result 冒充修复。
