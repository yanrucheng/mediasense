---
title: "Plan 持续页面使用与发布核查"
service_version: "MediaSense 0.10.2; be8dd255892856cc8f90caad25c330dce293b67b49dabaaaac33294e8c084e4c"
date: 2026-09-14
environment: "isolated macOS, Python 3.11.13, MCP 2.2.0, Chromium 153.0.8010.36"
model_id: "gpt-6-astra / low independent consumer; gpt-6-astra evaluator"
dataset_version: "review-loop synthetic 12-item case in config.json"
purpose: "Exercise actual page review and an independent Agent using the installed Skill, then verify the release"
baseline_ref: "review-plan-preview-delivery/acceptance.md"
---

**页面使用与发布前工程核查完成，待独立验收 Agent 复核。** 主持者实际打开规划页面、核对成员和证据、给出两轮修改意见，再接受并查看冻结版本。独立使用 Agent 全程通过真实 MCP 保存规划，没有编写 HTML 或临时展示服务器。用户随后明确跳过弱模型比较，因此不再把这一项列为发布阻塞，也不将同模型低推理预算运行冒充弱模型对比。

## 实际使用结论

这组材料包含两天的书展、散步、文化中心看展、陶艺课、票根及无关便条。数据均为人工编写的合成图卡，有真实文件、准备图片和封存 Result；它验证页面与交互，不认证真实照片识别。

主持者在真实 Chromium 中完成以下动作，操作文本与截图保留在 `outputs/page-review/`：

| 实际操作 | 看到的问题或判断 | 后续结果 |
| --- | --- | --- |
| 打开第一版并展开书展成员 | 首屏能分清已安排 5/12 与待安排 7，两个活动下可核对原文件名，未安排项没有被自动塞进兜底目录 | 以此页面为依据补充第二天活动、票根和便条背景 |
| 在同一当前入口刷新 | 新版显示“六月周末活动 → 两天 → 五个活动”，11 项归组、1 项保留原处；看展与近时间陶艺课已分开 | 可以按活动找到陶艺课，再逐项核对两张照片和票根 |
| 阅读最终决定说明 | Agent 将“尚未最终确认”写入了拟冻结说明，未来阅读会有歧义 | 主持者通过普通反馈要求只保留理由、来源和限制；Agent 另存一版，将过程状态留在 working_notes，没有偷偷沿用上一版 |
| 打开准备图片、展开陶艺课成员与证据 | 票根归属来自模拟用户背景，而不是模糊图像或时间推断；详细证据实际关联对应源条目 | 最终明确接受这一确切版本，再由 Agent 调用 seal |
| 刷新冻结页 | 已冻结、确认记录、五个活动、保留原处的便条仍可核对 | 冻结 revision 与接受 revision 完全相同，无确认后额外保存、无 Apply |

实际使用还发现并修正三处轻量显示问题：`retain_current_organization` 现在显示为“保留原处”；准备图片可点击在浏览器新页打开，链接仍固定同一 Work/revision；待安排为零时明确写“当前范围内的素材均已有明确处置”。这些没有改变组织数据、确认规则或增加展示业务实体。

在本场景，页面能够支持判断组织、核对范围并提出有效修订。证据展开仍包含较多技术字段，图卡也不是现实照片；本结论不是普通用户可理解性或所有数据规模的独立认证。

## 独立 Agent 运行

最初请求的 `gpt-5.6-luna`、`gpt-5.5`、`gpt-5.6-terra`、`gpt-5.6-sol` 均在启动时被网关以 403 拒绝，未执行任何业务动作。没有修改账户权限。用户随后说“弱模型比较跳过”，这一决定取代原先的弱模型待验项。

实际消费者是无父上下文的 `/root/plan_consumer_low`，模型 **gpt-6-astra，low**。它只拿到安装后 Skill、自然语言请求、case.json 和公开 MCP 转发入口；未读取实现、测试、评测配置或本 review-guide。原始会话标识为 `01a09b88-3764-7eb0-8933-221e0c0bece5`。

从实际执行事件核对：完整读取 Plan Skill（事件行 25）及默认 Profile（行 30），真正打开 **9 张**准备图卡；保存 **3 个新修订**（部分草案、完整候选、说明修订），最后冻结。Agent 文件只有请求 JSON，没有 HTML。详细小型指标见 [metrics/combined.json](metrics/combined.json)。

首次 create 把 MCP 的外层 request 又嵌套了一次，返回 host_operation_failed，Agent 自行查清转发器采用业务请求平铺输入后恢复；保留该错误，不称为零错误首轮成功。模拟用户还纠正了最终说明里的过程状态。因此本轮证明可通过讨论收敛，不证明 Agent 一次就能完美规划。

原始 MCP trace 同时含两次主持者为更新显示构建而进行的 inspect；不把这些计作 Agent 独立动作。保留的 `outputs/agent-tools.jsonl` 只含执行、图片查看和对外消息，排除内部推理文本。模型调用已发生，未独立计量 token/费用；无额外 Geo/provider、Apply 或真实媒体修改。

## 剩余 PreCheck 测试的原因

此前失败的 `test_start_preparation_failure_pauses_the_unowned_accounting_run` 把故障注入到 `_resolved_execution_config`。配置改为在 start 时冻结之后，正常准备路径已有 execution_config，该函数不再被调用，因此测试未制造失败、正常得到 run_ref。

本轮开始时共享工作区已将注入点改到真正执行的 `bind_accounting_run`，先执行实际绑定再抛出模拟错误。我们核对了调用链并重跑：返回 operation_failed，公开 Run 为 failed，已绑定 accounting Run 为 paused。该用例单独和在完整快照套件中均通过；没有为让测试绿而更改产品失败语义。

全量检查还发现两个第 6 包遗留测试形状：一份手写 Candidate 缺少 kind；六个并发重放用例仍比较包含新 view 时间观察的整个回包。修正测试为当前输入形状，并只比较不可变业务回执；原子性、精确 revision、关闭状态及只提交一次的断言保留。四个 loopback 网络测试最初被沙箱拒绝监听，改在允许本机监听的隔离运行中通过，未将权限失败算作产品回归。

## 最终构建和检查

基线 commit：`0794d3c9182793b7b25c1cac77793e3c97e42092`，外加本轮冻结的共享工作区快照。快照与检查不随随后其他 Agent 的工作区改动而改变。

| 项目 | 实际结果 |
| --- | --- |
| 完整源码套件 | **1453 passed, 17 deselected**，298.15 秒；含已修正的 PreCheck 准备失败、全部 Plan 和其他阶段测试；local_fixture/scale 按原 marker 默认排除 |
| 最终生产差异 | 全量检查后的唯一生产差异为 app.js 上述显示修正；通过 JS 语法、实际图片新页和以下完整浏览器复验 |
| 最终 wheel | `outputs/release-final/wheel/mediasense-0.10.2-py3-none-any.whl`，SHA-256 **be8dd255892856cc8f90caad25c330dce293b67b49dabaaaac33294e8c084e4c** |
| 安装字节核对 | 141 个包文件与固定源码、wheel、独立 venv 逐字节相同 |
| 离线干净安装 smoke | `distribution smoke: ok`，实际隔离 uv tool 安装、Skill、CLI、doctor、MCP；临时目标与日常目标分离 |
| 最终浏览器回归 | 再次通过 1200 项／24 页、54 个目录／两页三级结构、刷新与固定版本、图片/入口恢复、宿主重启、MCP 冻结；21 次 CLI 实际回包通过 schema 验证 |
| 真实使用样例 | 12 个源文件及封存 Result 的 SHA-256 前后不变；accepted revision 与 frozen revision 相同 |
| 静态工程检查 | Ruff、JavaScript 语法、diff 检查通过 |

固定源码、初版源身份、测试修订和最终源身份分别留在 `outputs/release/` 与 `outputs/release-final/`。最终安装保留在 `outputs/release-final/venv/`。原始媒体、数据库、图像、MCP 回复、执行日志和 wheel 全部是本地忽略输出，不进入 Git。

## 复现与复核

配置在 [config.json](config.json)，模拟反馈见 [review-guide.md](review-guide.md)，生产者复用上一轮的合成案例准备逻辑；本轮 [run.py](run.py) 只转发并记录安装版 MCP。MCP endpoint 是选择的 `mediasense mcp` stdio 子进程。浏览器驱动是 [browser.cjs](browser.cjs)，所有页面与业务数据都来自产品。

```sh
rtk proxy <isolated-python> eval/sessions/260913-2352-plan-delivery-use/run.py prepare --output /tmp/new-plan-use --host <isolated-mediasense>
rtk proxy <isolated-python> eval/sessions/260913-2352-plan-delivery-use/run.py tool /tmp/new-plan-use/review-loop mediasense.plan.work <request.json>
rtk proxy <isolated-python> <fixed-source>/tests/run_distribution_smoke.py <wheel> --offline
rtk proxy <isolated-python> <fixed-source>/tests/run_plan_preview_delivery_smoke.py --host <isolated-mediasense> --output /tmp/new-plan-smoke --browser <chromium> --playwright <playwright-core>
```

实际使用原始数据在 `/private/tmp/mediasense-p6-agent-use/review-loop`，完整副本保留于本会话 `outputs/case/`；浏览器操作和截图在 `outputs/page-review/`。最终大集合回归原始目录为 `/tmp/mediasense-p6-final-delivery-smoke`，结论与截图另保留到 `outputs/final-smoke/`。便于独立验收的当前本机页面为 `http://127.0.0.1:50564/v/kJUvonVqb7-NDcWoBHQ1ATiOHs6MpQLJZlhIGsSuSBk`；传输地址不是永久 Plan 身份，宿主退出后通过普通 inspect 重取。

完成状态：页面实际使用与发布工程核查完成；独立验收 Agent 尚未复核本轮。弱模型比较按用户决定跳过。未切换日常 CLI、项目 Skill 或既有会话；本轮冻结是合成评测 Plan，不是业务 Plan，也没有 Apply 授权。
