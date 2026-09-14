# 第 6 包实施与验证

2026-09-13。用户独立复核确认主流程已接通，但指出当前页刷新、多级目录层级、说明成员读取异常分类三处缺口，因此此前记录不能作为整包验收通过的结论。用户本次没有重跑此前开发者记录的 280 项测试。三处已修正，补修复验结果记录在文末；独立 Human 页面可理解性验收仍未执行；后续开发者页面使用及同模型独立 Agent 记录见文末，弱模型比较已由用户明确跳过。

## 实现范围

- 一个 Work 保存 `organization_content`（无组织、draft、candidate）；复用 Result、Source Set、分组、其他处置和 decision_notes。未安排数量来自精确范围差集，完整草案不会自动变成候选。
- create/update/seal 的保存回执与本次 `view` 观察分离；默认 inspect 返回视图，可明确选择不经过 renderer 的状态读取。失败保存边界与幂等重放保留。
- 普通 CLI/MCP 自动交付当前和确切版本入口。本机只读进程由 Runtime 启动、按构建复用、检查和恢复；`views status/stop` 反映真实进程。页面不提供写入、确认或 Apply API。
- 页面展示说明、偏好、范围、目录、其他处置、待安排项、说明适用成员和实际 Evidence；每页 50 项、有真实续页。已加载旧页提示过期，过期续页拒绝混入新版本。图片失败有来源和占位。
- 严格确认绑定 Work/reviewed_revision/identity。新保存、同值写入、撤回后恢复相同内容均拒绝旧确认；展示和幂等重放不另造版本。Frozen Plan 格式保持不变。
- 公开合约、38 个静态交互例、Plan Skill、页面发布资源、安装 runbook 及其发布副本同步。私有存储升级为 v4，保留旧状态、回执、游标密钥、预留 Plan 引用和冻结 artifact；未完成旧 seal 拒绝迁移，先恢复原发布。

## 验证范围

| 层面 | 证据与状态 |
| --- | --- |
| 静态材料 | 本包 verify_spec.py：3 schemas、38 exchanges、23 requirements、54 scenarios 通过；只证明一致性 |
| 定向回归 | 最终 280 项通过：Plan 保存/校验/分页、严格确认、进程并发与取消、MCP、图片缺失、迁移、Dataset/Host、PreCheck→Plan→Apply 交接、发布资源与合约检查；Ruff 与 diff 检查通过 |
| 隔离 wheel / 实际页面 | 已通过：普通 CLI 19 次实际交换及回包 schema 检查、真实 Chromium 页面操作、MCP inspect/seal/replay、已冻结页面；1200 项以每页 50 项共 24 页完整浏览，无重复或漏项 |
| Human 可理解性审阅 | 未执行；自动化浏览器与截图检查不代替 Human 对页面的接受 |
| 独立 / 较弱 Agent 效果 | 未执行；没有较弱 Agent 成功率、token 节约或真实规划质量的结论 |
| 日常安装 | 未切换；仅在 /tmp 的隔离环境构建、安装和运行 |

## 使用与恢复

从普通 `mediasense.plan.work` 返回的 `view.current_uri` 继续讨论；完整候选整案审阅使用 `view.revision_uri`。页面失败后，先保留成功的保存回执；可选择 overview/working_notes/content 做状态读取，再通过 inspect 的 view 或原请求重放恢复入口。不要用新 request_id 重写一个已经提交的语义变化。

实际页显示冻结状态的依据是成功 seal 记录。测试中的 `human:synthetic-*` context 只模拟可信客户端事件以验证核对机制，不能作为真实 Human 接受记录。

原始素材、真实业务 Plan、版本化 fixture 均未修改。大集合测试仅生成新的合成媒体与 Result；原始日志、截图和 wheel 留在 /tmp，不写入 Git。已有共享工作区修改保留。

## 最终隔离执行证据

- wheel：`/tmp/mediasense-p6-wheel/mediasense-0.10.2-py3-none-any.whl`
- SHA-256：`1a500efb4be88b5759d85310ad5e27bfd2b25880e408f90a017f1e9916dfc509`
- 固定构建源快照：`/tmp/mediasense-p6-release-source`；隔离 Python：`/tmp/mediasense-p6-env/bin/python`（CPython 3.11.13，MCP 2.2.0）。版本号没有被当成构建身份。
- 运行目录：`/tmp/mediasense-p6-acceptance-8`。其中 `report.json`、`cli-trace.json`、`mcp-seal.json`、`partial.png`、`candidate.png`、`frozen.png` 保留实际回包与页面证据。Frozen 页面另经普通 inspect 重连后等待目录、说明及图片加载完成检查。
- 合成 Work：`plan-work:f1a0d30d-7bf6-4b2a-97d2-7557e8f83105`；冻结 revision：`work-revision:3d19377b-e392-4ed0-b262-6192ba4e715d`。1 次 create、9 次新 update、1 次 seal；重放不增加保存次数。

实际循环覆盖：无组织页面 → 工作说明 → 5/1200 部分草案 → 全部安排但仍为 draft → 完整 candidate → 24 页成员及说明成员展开 → 图片缺失、明确占位、宿主重启后仍保持核心规划 → 恢复图片 → 工作说明变更与同值写入后拒绝旧确认 → 清空/恢复相同候选仍拒绝旧确认 → 保存成功但入口目录不可用 → 同一请求恢复页面且回执不变 → 旧保存回执显示 superseded → 宿主停止后普通 inspect 恢复 → MCP 最终冻结/幂等重放 → 查看实际冻结记录。

同时检查旧页及旧成员游标拒绝混合版本，保存文本中的脚本作为文字呈现，跨 Origin 请求与未知句柄拒绝，任意路径不能充当图片引用。所有 1200 个合成原文件在完整循环前后逐一 SHA-256 相同。结束时测试页面宿主已停止，下一次普通 inspect 可以重新取得入口。

复现入口：

```sh
rtk proxy /tmp/mediasense-p6-env/bin/python tests/run_plan_preview_delivery_smoke.py \
  --host /tmp/mediasense-p6-env/bin/mediasense \
  --output /tmp/new-plan-preview-check \
  --browser "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --playwright "/Applications/Codex.app/Contents/Resources/cua_node/lib/node_modules/playwright-core"
```

浏览器程序与 Playwright 路径是本机验证条件，不是产品依赖。产品页面由标准浏览器打开即可。测试脚本创建自己的合成数据，不能将输出指向真实业务或版本化 fixture。

## 构建范围与限制

固定源快照与 wheel 完整一致；本包在共享工作区中的代码、Plan 合约、页面资源和 Skill 与 wheel 一致。构建后其他工作将共享区的 `precheck-read.tool.json`、`precheck-run.tool.json`（及各自发布副本）继续修改；本包保留这些改动，没有将它们的未完成接口混入此 wheel 或宣称已验证。构建身份核对保留在 `/tmp/ms-p6-release-identity.json`。

本次仅认证上述隔离构建和用例，未认证整个持续变化的共享工作区构建。未切换日常 CLI、Honeycomb Skill 或既有 Agent 会话。Human 对页面可理解性和导航的独立验收、较弱 Agent 按 Skill 自主规划的效果、大于 1200 项规模、其他操作系统均未验证。历史草案永久恢复和远程分享不在本版承诺中。

## 独立复核后的三处补修

用户指出的三个问题均为实现缺陷，未重新讨论或修改产品语义、公开 Tool 合约和冻结规则。本节是最新补修记录；前文 280 项及旧 wheel 记录保留为首次实现证据，不冒充本轮用户验收。

| 缺陷 | 修正 | 实际复验 |
| --- | --- | --- |
| 当前 URI 被改写为固定版本，刷新不能取得新版 | 保留进入页面时的 URI；当前文档的 API 请求仍固定其已加载 revision | 浏览器在当前入口连续保存说明、部分草案后直接 reload，URL 不变且取得新 revision；未刷新的旧文档不自动换内容；另一个固定版本页 reload 后明确过期，未显示新版目录 |
| 多级路径平铺 | 由已保存路径逐级派生并复用父节点，保留首次出现顺序；直属成员与包含子目录的汇总数量分开 | 普通 CLI 保存另一个含 54 个目录、三级结构的合成 Work；实际点击第二页加载余下 4 组，共享父节点不重复，同名叶节点不合并；父目录和根目录的直属成员、父子关系和顺序均核对，第二页叶节点可展开成员 |
| 说明成员读取中的程序异常被包装成资源错误 | 使用已有 Plan resolver 的异常传播规则；HTTP 输入错误显式验证，内部 RuntimeError/ValueError/KeyError 到达 operation_failed 边界 | 针对 decision_notes 和 note:0 的晚期读取注入三种异常：直接调用抛出原异常，HTTP Handler 返回 500/operation_failed；已知 Result 不可用仍为 503，错误输入仍为 400，移除故障后可继续读取且 Work 不变 |

目录汇总由同一完整快照计算，所以首批 50 组加载时，父节点已经显示包括后续页在内的真实数量；不把“当前已加载的子目录数量”伪装成总量。未新增 Agent 维护的展示数据或业务专用模块。

本轮验证分层：

- 新增边界及相关预览测试 **32 项通过**；其中 **9 项**异常分类/目录汇总测试又针对已安装 wheel 重跑通过。
- 扩大回归实际结果是 **288 passed、1 failed**。失败用例为 `tests/test_runtime_host.py::test_start_preparation_failure_pauses_the_unowned_accounting_run`，期望 PreCheck start 返回 error，但当前共享区实现返回 run_ref；单独重跑仍失败。用前一轮隔离安装运行同一用例为通过。它位于持续变动的 PreCheck 启动路径，本次未修改；不能宣称本轮扩大回归全绿。
- 新 wheel 经普通 CLI/MCP 和真实 Chromium 重跑完整循环通过：1200 项、24 页，21 次 CLI 交换及响应 schema 验证，图片/入口失败恢复、宿主重启、旧确认拒绝、MCP 冻结及已冻结页面。增加了当前入口刷新与 54 组跨页树结构验证。1200 个合成原文件逐一哈希不变。
- Ruff、JavaScript 语法、diff 检查与本包静态 38 条交互检查通过。静态检查不作为页面操作证明。

新构建与证据：

- 固定源快照 `/tmp/mediasense-p6-fix-source`；wheel `/tmp/mediasense-p6-fix-wheel/mediasense-0.10.2-py3-none-any.whl`。
- wheel SHA-256：`274c978be46144d1451c8998eeb6262f513869dd509f431001c5f38e2897b2ce`。
- 独立安装 `/tmp/mediasense-p6-fix-env`。140 个包文件与固定源快照及 wheel 逐字节相同；本次四个产品修正文件与共享区源码相同。共享区其他后续变动不借用此构建的认证。
- `/tmp/mediasense-p6-fix-acceptance-1/report.json`、`cli-trace.json`、`mcp-seal.json`、`hierarchy.png` 和 `frozen.png` 保留实际运行及页面证据。测试宿主已停止。
- `/tmp/ms-p6-fix-tests.log` 保留扩大回归结果；`/tmp/ms-p6-fix-baseline-test.log` 保留旧安装对照；`/tmp/ms-p6-fix-build.json` 保留构建核对。

本轮完成三处工程补修与上述开发者复验，仍待用户独立复核。独立/较弱 Agent 行为评测和 Human 页面可理解性审阅没有新增证据，继续标为未完成。未切换日常安装、修改真实业务 Plan、原始素材或版本化 fixture；共享工作区其他修改保留。

## 2026-09-14：实际页面使用与发布前收尾

用户要求继续实际使用、补独立 Agent 运行并查清 PreCheck 测试，随后明确跳过弱模型比较。本节和[完整评测报告](../../../eval/sessions/260913-2352-plan-delivery-use/report.md)是最新状态；前述“弱模型待验”和“1 项 PreCheck 失败”不再作为当前阻塞项。

- 开发者实际使用隔离页面完成“讨论 → 保存部分草案 → 展开成员查看 → 补充背景 → 修改完整候选 → 再修订说明 → 明确接受 → 冻结”。场景为 12 项合成活动图卡，包含看展、陶艺、两次散步、票根和保留原处的便条。查看了同一版本的成员、来源与准备图片，能够据此提出具体修改；这不冒充独立 Human 可理解性验收或真实照片识别评测。
- 一位无父上下文的 `gpt-6-astra / low` 独立使用 Agent 实际读取安装后的 Skill/Profile、打开 9 张证据、保存 3 个修订并冻结。没有编写 HTML、临时服务器或重复展示数据。首次请求重复包装失败及主持者对说明内容的纠正均保留，不报告零错误首次成功。它是独立同模型低预算运行，弱模型比较已按用户要求跳过。
- 实际使用修正了 `retain_current_organization` 的中文标签，增加同版本准备图片的新页入口，并明确零待安排时的文案；未变更 Plan 数据与确认规则。
- 剩余 PreCheck 失败来自测试注入点过时：配置已在 start 冻结，旧 `_resolved_execution_config` 注入不会触发。共享区已修正到实际 accounting 绑定步骤，本轮核对失败转换并重跑通过。另补正一份遗漏 kind 的 Candidate 测试和六份仍比较整个动态 view 回包的幂等测试，未放宽产品合约或原子性断言。
- 固定源码完整检查 **1453 passed, 17 deselected**；最终唯一生产增量是上述 app.js 显示修正，已在实际页面、图片新页、离线干净安装 smoke 及完整 1200 项／24 页、54 目录／三级结构的 CLI/MCP/Chromium 循环中验证。12 项使用样例和 1200 项回归样例的源字节均未变。

最终 wheel：`eval/sessions/260913-2352-plan-delivery-use/outputs/release-final/wheel/mediasense-0.10.2-py3-none-any.whl`，SHA-256 `be8dd255892856cc8f90caad25c330dce293b67b49dabaaaac33294e8c084e4c`。141 个安装包文件与固定源快照、wheel 完全一致。快照、调用轨迹、截图和指标的入口见上述评测报告；原始输出不进入 Git。

当前本机隔离样例入口：`http://127.0.0.1:50564/v/kJUvonVqb7-NDcWoBHQ1ATiOHs6MpQLJZlhIGsSuSBk`。保留只读宿主便于复核；地址失效时以普通 inspect 重取，不能将临时地址当永久身份。未切换日常安装或改动真实业务 Plan，等待独立验收 Agent 核对本轮结果后再考虑日常切换。
