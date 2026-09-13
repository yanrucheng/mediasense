# Plan HTML 人工确认页面的正式交付与内容来源

## 交接状态

记录日期：2026-09-13。阶段：**事实已记录，待后续 Agent 与用户单独讨论**。

用户要求本轮只整理问题，后续逐包细化、讨论定案后再解决。本包不包含已确认的设计、公开合约变更或实施任务。代码位置用于复核当时行为，不限定后续方法；审计报告中的建议不构成本包的设计决议。

## 用户已明确的目标

2026-09-13，用户说明 HTML 是其最终确认 Plan 的直接人工手段，非常重要；希望较弱 Agent 使用时也有稳定结果，不要求 Agent 自己编写 HTML 并承担相应 token 成本。用户希望 Plan 登记后能够自动取得 HTML；本次临时菜品核对不需要固化成通用业务模块。

这些是用户已表达的目的，不是已选定的接口、文件布局、渲染技术、事务或失败处理方案。

## 已确认事实

1. [PlanPreviewRenderer](../../../src/mediasense/plan/preview.py) 已存在；被检查的安装副本与源码一致，SHA-256 为 `fa0d521eb2d4c062883660bd1293666c256ad154a9242784277987a9641cff0b`。它支持根据候选生成目录、图片、例外与 decision_notes 并写出 HTML。
2. 被检查的 Plan Work 公开合约只有 create/update/inspect/seal。安装版 update 响应只有 `outcome/action/work_ref/result_ref/revision/state`，没有预览位置或生成状态。CLI 没有对应预览生成入口，生产调用路径没有接入 renderer。
3. [现有 smoke 脚本](../../../tests/run_plan_interaction_smoke.py) 在 MCP 保存候选后，另建 Python RuntimeHost，通过内部 `local._datasets[dataset].plan_work` 调用 renderer；它没有经普通 Agent 的 Tool 调用取得生成好的 HTML。
4. [Plan Skill](../../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md) 要求生成与确切候选对应的最终预览，但没有给出已经接通的生成入口。本次整个 HTML 由 Agent 临时编写 `/tmp/render_mediasense_hk_preview.py` 生成，后来追加菜品板块；原会话 Agent 也向用户明确说明这一事实。
5. 内置 renderer 默认只在每目录列出前 100 个不透明 Source Item 引用；超出部分提示可以进一步读取，但生成的静态页面没有接入其 Python `directory_page` 的真实分页操作。
6. 被检查的临时预览数据中，10 条菜品名称及依据都有对应的 Candidate decision_notes。不能将整块内容说成完全没有写进 Plan。
7. 菜品专页实际读取独立 `dishAnnotations` 列表，其 `name/basis/path/source/url/ids` 由 Agent 另行维护；临时脚本不是从 Candidate 的 notes、适用范围和 Evidence 关系确定性生成这些图文定义。
8. 被检查页面 SHA-256 为 `2a3e98ec956b45d4efa6246512c8547ae0cb26155d017bd95b6faeff4e7b2581`，对应 Candidate 为 `sha256:691c36d0031b011cb97ea0216934dee4b08a6e00cdc5c9d0b6114f203a1221af`；它不是共用指标中 23:11 的初版候选。

## 影响与证据边界

从内部 Python 能力到用户实际使用入口之间缺少正式交付。当前现场页面的实现与维护依赖 Agent 的页面编程能力，不能由已有 renderer 或单独渲染测试推定已经提供了用户要求的自动体验。

临时页面还依赖 Candidate 之外人工维护的展示定义。核对“页面嵌入的 Candidate JSON 与 identity 一致”，不等于已验证每一块可见内容都从该 Candidate 派生。这里没有证据表明菜品文字必然错误，也没有证明 renderer 的所有其他能力不可用。

没有对不同模型完成同条件 token 或成功率实验，不能量化自动生成将节省多少 token。是否生成脚本、静态 HTML、何时生成、怎样读取、如何处理失败与历史页面，均未在本包定案。

## 直接复核入口

- [Plan Work 当前合约](../../../docs/spec/contract/plan-work/index.md)及[交换值定义](../../../docs/spec/contract/plan-work/plan-work.tool.json)。
- [PlanWorkTool](../../../src/mediasense/plan/work.py)：update 回执、内部 `snapshot_for_preview`。
- [renderer](../../../src/mediasense/plan/preview.py)：`build`、`render_html`、`write_html`、`directory_page`。
- [smoke 入口](../../../tests/run_plan_interaction_smoke.py)：MCP 保存之后的内部 Python 渲染路径。
- 本机临时脚本：`/tmp/render_mediasense_hk_preview.py`；数据：`/tmp/mediasense-plan-hk-preview-data.json`；它们可能随原会话继续变化。
- 相关既有包：[Plan 信息收集与可选保存](../refine-plan-interaction/README.md)。该包已有 Preview 验证与本次发现的实际入口缺口分别记录。

## 尚未定案的问题

- 用户所说的“登记后自动取得 HTML”，对应当前哪些候选/工作状态及交付结果？
- 正式确认页面需要包含哪些通用内容，其语义分别来自 Candidate、Result 或其他已有事实？
- 如何区分临时调查展示与最终确认内容，避免再维护一份组织意图？
- 在候选变化、撤回、生成失败、材料不可读或内容过大时，用户能够依赖什么？
- 怎样证明普通 Agent 经正式入口就能交付可用页面，而不是测试代码绕到内部对象才可生成？

## 共用证据与适用范围

- [运行验收报告](../../../eval/sessions/260912-2333-hk-run-acceptance/report.md)
- [精简指标](../../../eval/sessions/260912-2333-hk-run-acceptance/metrics/combined.json)
- [精确对象与本机路径](../../../eval/sessions/260912-2333-hk-run-acceptance/config.json)
- [只读复核脚本](../../../eval/sessions/260912-2333-hk-run-acceptance/run.py)

被审计运行使用 MediaSense 0.10.2，源为 `ai-album-hk-representative-v1/test-260831`。审计代码基点为 `615c3359941927515f0c0a8738a3f08122bcad46`；共享工作区和原 Plan 会话随后继续变化，不能把当前磁盘状态当作当时状态。

PreCheck Run 为 `precheck-run:8b5ff902fda54e6292b14d4fa5f0de42`，Result 为 `precheck-result:cbd18bc79b56b2b9d257529f878b7151c399b4815acebe74d1ba328e80a7ae57`。初版 Plan 轨迹固定到配置中声明的原会话前 859 行；后续更正按报告中的时间与行号分别引用。原始媒体、数据库、完整轨迹和 HTML 快照在本机，不复制到本包。

公开语义以 [当前合约](../../../docs/spec/contract/index.md) 为准；本包不成为另一份规范，也不改变既有验收或迁移决定。
