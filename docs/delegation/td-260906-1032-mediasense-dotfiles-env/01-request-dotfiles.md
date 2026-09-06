---
id: "01-request-dotfiles"
title: "Research MediaSense Credential Delivery through DotFiles"
type: task-delegation
status: active
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-1032-mediasense-dotfiles-env"
depends-on: []
superseded-by: ""
recipient: "team:dotfiles"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260906-1032-mediasense-dotfiles-env/01-result-dotfiles.md"
---

以下内容可直接交付给 DotFiles：

````text
你是 DotFiles，工作位置是：

/Users/chengyanru/repos/personal/dotfiles

请进行一次只读、证据化调研，说明 MediaSense 应如何复用 DotFiles 已有的 Secret 与 env-file 投放能力。不要修改任何仓库、HOME、Vault、Keychain、进程、MCP 配置或 Dataset。

为什么需要这份结果

MediaSense 已全局安装并在一个 Honeycomb 中完成 Skills 与项目级 MCP 接入。Codex 已成功发现和调用六个 MediaSense Tools，但 PreCheck 到 required Geo acquisition 时 fail-closed，因为启动 `mediasense mcp` 的进程没有可用地图 Provider credential。发起方曾建议新建 MediaSense 专属 Keychain item 和包装器；用户指出 DotFiles 已负责 env file 的安全管理和生产，不应另造一套责任。你的结果将用于让用户从少量方案中选择，不用于直接执行变更。

已经确认的现场事实

- 全局 CLI：`/Users/chengyanru/.local/bin/mediasense`，版本 `0.7.1`。
- 目标 Honeycomb：`/Users/chengyanru/Downloads/ai-album-hk-representative-v1`。
- 其 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml` 使用 `command = "mediasense"`、`args = ["mcp"]`。
- Codex 已实际调用 MediaSense Tool，故 CLI、Skills 和项目 MCP 注册不是当前失败点。
- MediaSense 默认识别 `AMAP_API_KEY` 和 `GOOGLE_MAPS_API_KEY`；其用户配置只允许把 Provider 映射到环境变量名，不保存 Secret value。
- `/Users/chengyanru/.env` 当前为 `0600`，其中存在 `AMAP_API_KEY` 赋值；当前交互 shell 中该变量 absent。禁止读取、返回或比较任何 Secret value。
- `/Users/chengyanru/.config/zsh/functions/drun` 还提到 `GOOGLEMAP_API_KEY`，这与 MediaSense 的 `GOOGLE_MAPS_API_KEY` 拼写不同，但不能仅凭这一处历史消费者推断应修改哪一方。
- DotFiles 已有 credential catalog、machine mapping、`dotfiles-secrets-refresh`、Bitwarden Password Manager 方案与相关测试。用户明确说 DotFiles 负责 env file 的安全管理和生产。

必须先遵循的权威路径

1. 完整遵守 `/Users/chengyanru/repos/personal/dotfiles/AGENTS.md`。
2. 按其 mandatory route 阅读 `docs/environment/index.md`、相关 `docs/spec/`、`docs/environment/standard/` 和当前机器 mapping。
3. 检查当前 active contract/code，而不是把 archived Bitwarden Secrets Manager 候选设计当成现行事实。
4. 保留 DotFiles 当前脏工作树；本请求禁止写入、收敛、刷新、解锁 Vault、打印 Secret 或运行有外部效果的命令。

请回答的独立问题

1. 当前 Secret value、repository-safe Credential identity、机器绑定、生成的 env file 分别由谁权威拥有？`/Users/chengyanru/.env` 是人工权威还是生成 projection？
2. 当前正式 consumer/profile 是否已经包含 `cred:location/amap` 与 `cred:location/google-maps`？哪条受支持命令生产/刷新哪些目标文件，使用哪些环境变量名？
3. 当前设计如何让 env-file 中的变量进入普通 shell、GUI 启动的 cmux、cmux 启动的 Codex，以及 Codex 启动的 stdio MCP child？哪些链路已由合同保证，哪些没有？
4. 结合当前机器的只读状态，为什么目标 Codex/MediaSense MCP 没有拿到 AMap credential？请区分未刷新 projection、未加载/未 export、变量命名不一致、会话未重启和现有合同缺口。
5. 给出 2–3 个可选方案。每个方案需列明：复用的现有实体、需要改变的权威文件或运行步骤、是否涉及 Secret value、适用范围、启动/重启边界、安全属性、验证方法、主要代价。
6. 推荐一个最小方案。必须优先复用 DotFiles 已有责任，不得建议 MediaSense 新建第二个 Secret store、Keychain item、credential registry、env-file producer 或专属 wrapper，除非你能证明存在真实且无人拥有的独立责任。
7. 明确 MediaSense 一侧应固定什么真实接口。重点判断它应继续只要求标准环境变量名，还是需要最小的非秘密变量名映射；不得让 MediaSense读取 Bitwarden、管理 Vault 或接管 DotFiles 的投放生命周期。

证据与报告要求

- 严格区分：当前 active contract、当前代码/配置、当前机器只读观测、历史/archived 材料、你的推断。
- 引用本地文件、目录或制品时使用绝对路径。
- 不输出 Secret value、片段、hash、长度、Vault session、Token、敏感原始内容或可用于推断 value 的信息。
- 报告需要足够具体，让发起方可以把方案直接交给用户选择；但保持执行方法开放，不把临时实现细节提升为永久合同。

返回要求

只修改以下配对结果文件，保留其现有 frontmatter，并在 frontmatter 后写入完整原始报告正文：

/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260906-1032-mediasense-dotfiles-env/01-result-dotfiles.md

不要修改请求、package index、synthesis 或其他文件。写完后返回简短写回回执。综合判断、用户方案选择和任何后续变更仍由 MediaSense 发起方负责。
````
