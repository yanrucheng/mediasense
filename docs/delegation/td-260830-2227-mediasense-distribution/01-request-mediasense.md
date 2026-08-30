---
id: "01-request-mediasense"
title: "Productize MediaSense Installation and Versioning"
type: task-delegation
status: active
created: 2026-08-30
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "td-260830-2227-mediasense-distribution"
depends-on: []
superseded-by: ""
recipient: "team:mediasense"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260830-2227-mediasense-distribution/01-result-mediasense.md"
---

以下内容可直接交付给 MediaSense：

````text
你位于 MediaSense 项目：

/Users/chengyanru/repos/personal/mediasense

你将从头到尾负责 MediaSense 的“产品化安装、Tool Host 与版本体系”，并在一个交互式 Workspace 中直接和用户讨论、澄清、设计、实现和验收。不要把问题返回给发起 Agent；用户希望由你亲自与他完成这项工作。

为什么需要这项工作

MediaSense 的 PreCheck、Plan、Apply 核心阶段、公共 Tool contracts 和用户侧 Skills 已基本形成，但目前仍主要是仓库内 Python 实现：缺少普通用户可以理解和重复执行的安装方式、统一运行入口、Tool Host/composition root、首次使用流程和完整版本策略。目标不是做一个演示脚本，而是让 MediaSense 以相对专业、可持续维护的本地产品形态出现，能够服务后续真实使用。

用户已经明确至少需要：

1. MediaSense 可以像正常工具一样被调用和使用，而不是要求使用者手写 Python 来装配内部类；
2. 有一套完整、清楚、安全的安装/bootstrap 方式和脚本；
3. 有一套相对完整、权威、可维护的版本号和兼容性系统；
4. 所有工程取舍最终服务于 MediaSense 的正常后续使用，而不是为了形式完整而增加平台、服务或抽象。

你首先要和用户讨论，而不是立即写代码。请用浅显语言说明当前缺口、可选产品形态和你的推荐方案，重点讨论：

- 用户最终怎样安装、启动、调用和升级 MediaSense；
- Agent 客户端怎样发现并调用六个现有公共 Tool；
- 是否采用本地 CLI、MCP/stdio Tool Host、本地 socket/HTTP 或其他最小边界；
- 第一次使用时怎样建立工作目录、配置 Dataset、检查外部依赖和安装 Skills；
- 首版明确支持哪些平台，哪些能力探测后再启用；
- 应用/package 版本、Tool contract 兼容、SQLite/持久状态迁移、release tag、changelog、prerelease、升级与回退分别怎样管理；
- 怎样避免把应用版本错误地变成 PreCheck 全局失效键；
- 什么叫 clean-machine 安装验收完成。

普通工程细节请自行作出专业判断。只有会改变产品使用方式、发布渠道、兼容承诺、安装信任边界、用户数据或外部效果的问题才需要停下来让用户决定。用户确认目标体验后，再建立一个聚焦的 OpenSpec change/backlog，然后分阶段实现；不要每个内部 Gate 都停下来询问。

必须先完整遵守仓库 AGENTS.md。架构、Tool、Skill 和 durable structure 判断必须使用：

- $yanru-guidelines
- $systematicity-lens
- $agent-skill-tool-boundary
- $agent-friendly-cli-design（若建立 Agent-facing CLI）
- $human-oriented-cli-design（若建立 Human-facing CLI）
- $local-doc-manager
- $test-optimization

当前已知事实，必须重新只读核实后再使用：

- Python package 名为 `mediasense`，当前版本声明为 `0.1.0`，要求 Python 3.11+，有 `uv.lock`；
- 当前 `pyproject.toml` 没有 CLI script entry point，也没有明确 build-system；
- 当前没有统一 `mediasense` 命令、公开 Tool Host/server、Dockerfile 或完整安装/首次使用说明；
- 当前公共 Tool 是 `mediasense.precheck.run`、`mediasense.precheck.read`、`mediasense.plan.work`、`mediasense.geo.query`、`mediasense.apply.run`、`mediasense.apply.read`；
- `.agents/skills/` 下有 PreCheck、Plan、Apply 三个用户侧 Skill；
- 其他 Agent 正在并行修复跨阶段 contract 问题。必须保留全部现有工作树修改，不得覆盖并行成果，也不得用安装便利重新定义业务契约。

产品和架构原则

- MediaSense 是 local-first 的媒体组织产品。安装层不能削弱 PreCheck 源只读、默认离线、长任务可恢复，Plan 负责解释和交互，Apply 只执行 Frozen Plan 的阶段边界。
- Tool 的业务 contract 与承载它的 CLI/MCP/stdio/HTTP transport 必须分开；transport 可替换，不得成为第二份产品语义。
- 建立唯一、明确的 composition root，集中构造配置、存储、schema、provider 和六个 Tool；不要让用户或每个客户端自行拼装依赖。
- 不要因为“专业化”就预设 daemon、云服务、动态插件系统、provider registry、安装器框架或多平台矩阵。每个持久实体必须有独立责任、权威或生命周期。
- 版本号必须有一个 authoritative source，并能驱动 package metadata、运行时 `--version` 和发布制品。明确 SemVer 或更合适规则、零版本策略、contract 兼容、数据库 migration、Skill/Tool compatibility 和 release notes。
- 应用版本、Git commit 或安装包版本不得成为 PreCheck 所有 Work 的粗粒度失效依据；只有真正影响某结果语义的生产者、参数、模型、输入或环境条件才参与有效性判断。
- 安装脚本必须可审阅、错误诚实、避免危险覆盖，明确对 Python、uv/pipx、ExifTool、FFmpeg/ffprobe、本地模型和平台能力的检查或安装责任。不要静默执行联网安装或写入不相关系统配置。
- 配置、credentials、工作状态和媒体源要分离；不得把密钥写入日志、版本标识、Result 或 Git。
- 不修改 AI Album 或香港 fixture，不运行 fresh replay、真实远程 provider、收费 API 或真实媒体移动。

交付至少应覆盖

- 专业的安装与卸载/清理路径；
- 一个正常可调用的 executable 入口和最小 Human-facing 控制面；
- 六个 Tool 的本地可发现/可调用 Host 或经论证的等价边界；
- `init`、配置、`doctor`、`version`、启动/连接和故障提示的完整用户旅程（具体命令名由你根据调查决定，不是预先冻结）；
- 外部依赖和首版平台能力探测；
- Tool/Skill 安装或发现；
- single-source version、兼容性政策、数据库迁移、发布和升级/回退策略；
- README/readme 中从空环境开始的实际步骤；
- isolated clean-environment smoke tests，证明安装、首次启动、Tool discovery、无破坏调用、版本显示和诊断可工作；
- 与现有三阶段 contract 的回归和端到端验证。

工作方式与 Git 边界

- 当前工作树可能包含其他 Agent 的未提交修改。先只读核查；不要 reset、checkout、清理或覆盖。
- 在任何实现前，先与用户确认目标体验和安全的 worktree/branch 方案。不要自行提交、merge、push、发布 package、创建 release 或删除 worktree/branch。
- 使用 OpenSpec 承载确认后的变更；人工验收前保持 change 可审阅，不要提前归档。
- 设计完整目标形态，同时拆成可早期验证的交付切片。优先尽快建立真实 clean-install vertical slice。

验收证据至少包括

- 全新临时环境中的可重复安装，不依赖仓库已有 `.venv`；
- CLI/Host 的 help、version、doctor、init 和 Tool discovery 行为；
- 配置/工作目录权限、重复初始化、缺失依赖、无效配置和升级失败的恢复；
- package metadata 与运行时版本一致；
- 支持/拒绝的 contract 与持久状态版本组合有测试；
- 普通测试不依赖 Downloads、在线地图、远程模型或收费 API；
- Ruff、全部非-live测试、OpenSpec strict、链接/frontmatter/index 和 `git diff --check`；
- 若实现 MCP 或其他协议，加入真实子进程级握手和至少一个无破坏 Tool 调用，而不只测试 Python 类。

最终返回要求

先向用户展示完整、可理解的完成报告和安装演示，等待用户明确确认。只有用户确认后，才把未经发起方解释加工的最终报告写入：

/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260830-2227-mediasense-distribution/01-result-mediasense.md

写回时保持该文件既有 frontmatter，只替换占位正文；引用本地文件必须使用绝对路径。完成后只给出简短写回回执。综合验收、合并、发布和关闭 delegation 仍由发起方或用户决定。
````

