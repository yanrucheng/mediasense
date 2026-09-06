---
id: "02-request-dotfiles"
title: "Implement the DotFiles MediaSense Narrow Credential Profile"
type: task-delegation
status: active
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-1032-mediasense-dotfiles-env"
depends-on:
  - "01-result-dotfiles"
superseded-by: ""
recipient: "team:dotfiles"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260906-1032-mediasense-dotfiles-env/02-result-dotfiles.md"
---

以下内容可直接交付给 DotFiles：

````text
你是 DotFiles，工作位置是：

/Users/chengyanru/repos/personal/dotfiles

用户已选择方案 B。请在 DotFiles 的既有 Secret delivery 架构内实现并验收一个
MediaSense narrow profile；不要建立第二套 Secret authority、producer、registry、
wrapper、daemon、cache 或全局 Shell/GUI Secret profile。

共享目的与 closing judgment

让指定 Honeycomb 启动的 MediaSense stdio MCP child 只获得 Geo acquisition 所需的
两个 Credential，同时保持 Bitwarden Password Manager 为唯一 Secret value 权威、
DotFiles 为 Credential identity / consumer binding / projection production 权威、
MediaSense 只消费进程环境。实现结果必须足够完整，使发起方可以继续完成
Honeycomb MCP child 接入和端到端验收。

已接受的只读调研结论

- 原始调研报告：
  /Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260906-1032-mediasense-dotfiles-env/01-result-dotfiles.md
- DotFiles 已有 `cred:location/amap` 与 `cred:location/google-maps`；不要新增或复制
  Credential identity。
- 复用现有 `/Users/chengyanru/repos/personal/dotfiles/dot_local/bin/executable_dotfiles-secrets-refresh`、
  `/Users/chengyanru/.config/dotfiles/secrets/`、Bitwarden Password Manager 和现有
  synthetic test framework。
- 新 projection 应只暴露 `AMAP_API_KEY` 与 `GOOGLE_MAPS_API_KEY`。不要沿用
  AI Album 的历史变量名 `GOOGLEMAP_API_KEY`。
- `/Users/chengyanru/.env` 是 legacy 文件，不是本次修改目标；不得 source、改写或
  提升为权威。
- Honeycomb MCP 配置和 MediaSense runtime 由发起方负责；DotFiles 不修改
  `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml` 或
  MediaSense 仓库。

必须遵循

1. 完整遵守 `/Users/chengyanru/repos/personal/dotfiles/AGENTS.md` 的 mandatory route。
2. 按 `$yanru-guidelines` 固定目的与权威归属，只固定真实责任和安全不变量，保持
   producer 内部拆分与后续消费方法开放。
3. 先建立一个独立、聚焦的 DotFiles OpenSpec change，再实现和 strict validate。
   不要把本变更混入现有 `register-dotfiles-team` packet。
4. 当前工作树已有用户修改：
   - `docs/environment/standard/manifest.yaml` 的 Team Fact 24 -> 25；
   - `docs/environment/machines/work-mac-2026/mapping.yaml` 的 Team Fact 24 -> 25；
   - `dot_agents/custom/teams/dotfiles.md` 与
     `openspec/changes/register-dotfiles-team/` untracked。
   必须保留并合并，禁止 reset/checkout/覆盖，禁止提交。
5. 不得输出、记录、比较或写入 Git 任何 Secret value、片段、hash、长度、
   BW session、Token 或可用于推断 value 的信息。测试只能使用 synthetic value。
6. 所有 shell 命令使用 `rtk` 前缀。

实施责任

1. 在 DotFiles standard manifest 中为 MediaSense 建立正式 consumer binding，复用
   两个既有 Credential identity。不得把 generated projection 写成事实权威。
2. 扩展现有 `dotfiles-secrets-refresh`，支持：

   `dotfiles-secrets-refresh mediasense`

   它应生成：

   `/Users/chengyanru/.config/dotfiles/secrets/mediasense.zsh`

   且精确输出两个 export：`AMAP_API_KEY`、`GOOGLE_MAPS_API_KEY`。
3. 复用并保持现有安全语义：exact Vault lookup、完整 schema/field 校验、
   `0700` 目录、`0600` 文件、同目录 Secret-bearing temp file、原子替换、并发锁、
   signal cleanup、失败保留旧 target、owned session 自动 relock、stdout/stderr 不泄密。
4. 扩展 synthetic tests，至少证明 exact two-key set、标准变量名、权限、幂等、
   原子替换、并发/信号清理、每类 lookup/validation/replace failure 均 fail-closed、
   保留旧文件且不残留临时 Secret 文件。避免为 profile 复制一整套不可维护测试；
   可在不模糊责任的前提下抽取现有 test helpers。
5. 仅在真实机器安全收敛和验收确已完成时，更新 machine mapping 为 accepted；
   未完成就诚实记录 pending，不得把 synthetic test 当作 machine acceptance。
6. 运行与本变更成比例的 tests、lint/shellcheck（若仓库已有正式命令）、
   `openspec validate <change-id> --strict` 和 `git diff --check`。

当前机器收敛授权

- 用户已授权实施方案 B，包括把 repo source 安全收敛到当前 HOME，并由既有
  producer 生成 `mediasense.zsh`。
- 可以使用现有正式 chezmoi apply/verify 流程，但必须限制到本变更实际管理的目标，
  不得顺带收敛无关 HOME 漂移。
- 可以运行 `dotfiles-secrets-refresh mediasense`。若 Bitwarden 已有可用授权状态，
  完成 refresh；若需要 Human 输入 unlock/password/MFA，立即停在该边界，保留
  repo implementation 与 synthetic tests，清楚报告需要用户执行的精确命令。
- 不读取或打印生成文件内容。验收只允许检查存在性、owner/mode、变量名集合和
  非敏感命令结果。

返回要求

只在 DotFiles 工作区实现上述职责，并把完整原始实施报告写入以下已存在文件，
保留 frontmatter：

/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260906-1032-mediasense-dotfiles-env/02-result-dotfiles.md

报告必须列出：实际修改文件、OpenSpec change ID、测试与精确结果、当前机器
projection 是否已生成和安全验收、尚未完成事项、发起方接入 MCP child 所需的
非秘密接口。不得修改本 package 的 request、index、synthesis 或其他 MediaSense
文件。不要提交。
````
