---
id: "01-request-checker-sdk"
title: "Research Checker SDK's Fast Test Contract for MediaSense"
type: "task-delegation"
status: active
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-2334-mediasense-test-contract"
depends-on: []
superseded-by: ""
recipient: "team:checker-sdk"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260906-2334-mediasense-test-contract/01-result-checker-sdk.md"
---

以下内容可直接交付给 Checker SDK：

````text
你是 Checker SDK，工作位置是：

/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker

请对本项目当前的 `make test` 入口和测试工程准则做一次只读、证据化调研，并判断哪些原则可供 MediaSense 采用。不要修改 Checker SDK 或 MediaSense 的代码、配置、文档、依赖、Git 状态或测试合同。

为什么需要这份结果

MediaSense 目前没有自己的 `make test`。发起方希望先理解 Checker SDK 已经形成的做法，再决定 MediaSense 是否应建立类似的默认测试入口和质量准则。用户特别记得两点：单个文件最好控制在约 400 行以内，以及默认 `make test` 应在 10 秒以内、最好显著低于 10 秒。你的报告将作为 MediaSense 后续设计与实现的输入，不直接授权任何变更。

已经确认的事实

- 发起方是 `team:mediasense`，工作位置为 `/Users/chengyanru/repos/personal/mediasense`。
- MediaSense 当前没有仓库级 `Makefile`。
- MediaSense 已在 `pyproject.toml` 中使用 pytest 和 Ruff；pytest 的 `local_fixture` 与 `scale` marker 是 opt-in。
- 接收方规范身份是 `team:checker-sdk`，本请求通过其 local workspace route 交付，结果采用 direct-write。
- “400 行”和“显著低于 10 秒”目前只是用户对 Checker SDK 实践的记忆，必须以当前权威文件、实现和实测核验，不能直接当作已证实合同。

调查边界

1. 完整遵守 Checker SDK workspace 内的 `AGENTS.md` 及其指向的项目规则。
2. 检查当前权威文档、`Makefile`、测试配置、脚本、CI 配置和相关源码；历史材料只能作为历史证据。
3. 可以运行项目现有的无外部副作用测试或静态检查，以取得可复现的行为与耗时证据。不要发起网络、生产、付费或真实外部服务调用；若默认命令会触及这些边界，停止该部分并准确报告。
4. 先后记录工作树状态并保留所有既有修改。不得编辑任何文件；若工具自然产生可忽略缓存，只能识别并报告，不得误删既有文件。

请给出一个可独立复核的结果，至少回答：

1. 当前 `make test` 的精确入口、依赖链和实际执行内容是什么？哪些检查属于默认开发门禁，哪些被分到慢速、集成、benchmark、外部或手工层？
2. Checker SDK 的测试准则在哪里权威定义？请说明高信号、确定性、隔离、失败诊断、覆盖价值、fixture、mock、网络与时间依赖等约束及其实际执行机制。
3. 关于单文件约 400 行，准确规则是什么：适用哪些文件、是硬门禁还是 review heuristic、如何计算、在哪里执行、允许哪些有理由的例外、违规时如何失败？
4. 关于默认测试耗时，准确目标是什么：`make test` 是否要求低于 10 秒，还是采用更严格预算？请在当前机器上提供可复现的测量证据，包括命令、运行环境说明、成功/失败状态和足以判断稳定区间的多次运行摘要；无需为了满足目标而修改或清缓存。
5. 哪些设计让该入口保持快速？例如测试分层、慢测试隔离、并行策略、无真实 sleep/network、测试选择、lint/static check 组合、缓存依赖或退出策略。区分已验证事实与推断。
6. 哪些做法可直接成为跨项目原则，哪些依赖 Checker SDK 自己的语言、工具链、目录结构、运行时或风险模型？不要把本项目细节误写成通用规则。
7. 基于 MediaSense 已使用 pytest、Ruff、`local_fixture` 和 `scale` marker 的事实，提出一个最小候选合同供 MediaSense 后续评审：建议的 `make test` 范围、分层命令、耗时预算、文件大小规则的性质与例外治理，以及应先测量的基线。这里只提出候选，不修改 MediaSense。

证据与报告要求

- 引用本地材料时使用绝对路径，并尽量给出行号或精确目标名。
- 严格区分：当前合同、当前实现、当前实测、历史材料、你的推断与建议。
- 如果记忆中的“400 行”或“低于 10 秒”与现状不符，直接指出差异，不要为了迎合前提而重述。
- 报告应足以让 MediaSense 独立判断是否采纳，但调查方法、分析结构和执行顺序由你决定。

返回要求

只修改以下配对结果文件，保留其现有 frontmatter，并在 frontmatter 后写入完整原始报告正文：

/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260906-2334-mediasense-test-contract/01-result-checker-sdk.md

不要修改请求、package index、synthesis 或其他文件。写完后返回简短写回回执。验证、综合判断、接受与后续实现仍由 MediaSense 发起方负责。
````
