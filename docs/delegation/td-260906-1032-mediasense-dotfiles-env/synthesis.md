---
id: "synthesis"
title: "MediaSense and DotFiles Credential Delivery Synthesis"
type: delegation
status: active
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-1032-mediasense-dotfiles-env"
depends-on:
  - "01-result-dotfiles"
superseded-by: ""
---

# MediaSense and DotFiles Credential Delivery Synthesis

## Closing judgment

用户的纠正成立：Credential value、identity、consumer binding、env-file
projection 的安全生产与轮换都应留在 DotFiles；MediaSense 不应新增
Keychain item、Secret store、Credential registry、刷新命令、wrapper 或兼容层。

当前故障也不是 MediaSense 没有全局安装。CLI、Skills、MCP 注册与六个 Tool
均已工作；缺口是 DotFiles 已生成的 Secret projection 没有进入
`mediasense mcp` 的子进程环境。文件存在不会自动改变已经运行的 cmux、Codex
或 MCP child 的环境。

长期推荐选择 **方案 B：由现有 DotFiles producer 生成一个只含两个地图
Credential 的 `mediasense` narrow profile，并只在 stdio MCP child 启动边界
加载它。** 这保持一个 Secret value 权威、一个 identity catalog、一个 producer
和一个 refresh 生命周期；新增的 projection 只承担 MediaSense 这个独立消费者的
最小变量集合与独立会话生命周期，因此通过独立责任测试。

该选择现已实施并验收。DotFiles 的 `add-mediasense-narrow-profile` change 已完成
repository implementation、真实 Human refresh 与无值 machine acceptance；目标
Honeycomb 已只在 MediaSense stdio MCP child 启动边界加载该 profile。新启动的
Codex 0.153.4 会话发现精确六个 MediaSense Tool，且 `dataset.open` 报告 AMap 与
Google Maps 均为 `credential=configured`、`capability=available`。

## Purpose anchor 与 Home anchor

- **Purpose anchor**：让 MediaSense Geo acquisition 在需要它的 MCP 子进程中获得
  两个 Provider Credential，同时不扩大 Secret 的进程可见范围。
- **Secret value home**：Bitwarden Password Manager。
- **Credential identity home**：DotFiles
  `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/credentials.yaml`。
- **Consumer binding 与 delivery contract home**：DotFiles
  `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml`。
- **Machine realization home**：DotFiles
  `/Users/chengyanru/repos/personal/dotfiles/docs/environment/machines/work-mac-2026/mapping.yaml`。
- **Generated projection home**：
  `/Users/chengyanru/.config/dotfiles/secrets/`；它是可重建的本地投影，不是
  Secret value 或 binding 的权威。
- **MediaSense authority**：只固定自身接受的变量名、Provider availability 和
  fail-closed 行为；不读取 Vault、DotFiles catalog、`~/.env` 或 projection 路径。
- **Honeycomb/Codex authority**：只固定在哪个 stdio MCP child 启动边界消费投影。

## Evidence synthesis

### 已验证的 active contract 与实现

- DotFiles 已有 `cred:location/amap` 和 `cred:location/google-maps`，无需新增
  Credential identity 或 registry。
- `dotfiles-secrets-refresh ai-album` 已实现 exact Vault lookup、完整校验、
  `0700/0600` 权限、同目录临时文件、原子替换和失败保留旧文件。
- 当前正式投影
  `/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh` 已存在并为 `0600`，
  但只由 `drun` 在函数局部作用域加载。普通 Zsh、GUI cmux 与 Codex 没有
  获得这些变量的现有合同。
- `/Users/chengyanru/.env` 是 legacy 本地消费者文件，不是当前 producer 的
  生成目标，也未被 active Zsh 启动链加载；不应把它提升为新的权威或全局
  Secret profile。
- DotFiles 当前明确排除通用 Agent profile、全局 Shell Secret profile、任意
  Item adapter 和第二份 Secret cache。
- MediaSense 默认读取 `AMAP_API_KEY` 与 `GOOGLE_MAPS_API_KEY`，并已有只保存
  环境变量名的非秘密 mapping。DotFiles 的现有 AI Album profile 使用历史名
  `GOOGLEMAP_API_KEY`；AMap 名称一致。

### Codex 启动边界

当前 Codex 文档确认 stdio MCP 配置支持 `command`、`args`、`env` 和
`env_vars`。其中 `env_vars` 只会从 Codex 的父进程环境转发变量，不能读取
DotFiles 生成的 env file；把 Secret value 直接写入 `env` 也不符合本次安全
边界。因此，如果不让 cmux/Codex 父进程持有 Secret，实施时需要在 MCP child
的直接启动命令中加载 narrow profile 后 `exec mediasense mcp`。具体 TOML/shell
表达属于可替换方法，应以当前 Codex 客户端做最小验证，不提升为产品合同。

官方参考：<https://developers.openai.com/codex/mcp/>。

### 实施与真实客户端证据

- Human 已在交互终端完成一次正式 `dotfiles-secrets-refresh mediasense`。后续只做
  无值验收：projection 为 owner `chengyanru`、group `staff`、mode `0600` 的普通
  文件；目录为 `0700`；export 名称集合精确为 `AMAP_API_KEY` 与
  `GOOGLE_MAPS_API_KEY`；无 temp 或 lock 残留。
- DotFiles machine mapping 的 S26/S27 已据实从 `partial` 更新为 `accepted`；focused
  synthetic tests、ShellCheck、governance、strict OpenSpec、rollback isolation 和
  `git diff --check` 均通过。
- Honeycomb `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml`
  使用 `/bin/sh -c` 在直接 child 边界 source narrow profile，然后 `exec`
  `/Users/chengyanru/.local/bin/mediasense mcp`。配置本身不含 Secret value。原配置
  已保存在同目录的 `config.toml.bak-20260906-114244`。
- 当前 Codex 0.153.4 能解析该配置。一个真实、全新的临时 Codex 会话发现精确六个
  MediaSense Tool，并通过 `mediasense.dataset.open` 打开正确 source，返回 manifest
  version 2、PreCheck store 17、Plan store 3、Apply store 2，两个地图 Provider 均
  configured/available。
- 第一次真实 Codex 验收误用了不存在的 source path，Tool 诚实返回 error 且未创建
  Dataset；随后改用实际 source path成功。该路径错误不是凭据或 MCP 故障。
- 尚未执行真实 Provider request。Credential availability 不等于外部效果授权；任何
  坐标披露仍必须由一个新 PreCheck Run 给出精确 disclosure，并通过 MCP session
  elicitation 获得绑定该 disclosure identity 的 Human confirmation。

## Selectable options

| 方案 | 权威与实体 | Secret 暴露 | 生命周期与代价 | 判断 |
| --- | --- | --- | --- | --- |
| **A. 临时复用现有 `ai-album.zsh`** | 不新增 projection；MCP child 直接加载现有六变量 profile，Google Maps 使用 MediaSense 既有非秘密变量名 mapping | 启动 shell 会读到六项，最终 child 需主动移除四项无关 Secret | 改动最少，但 MediaSense 耦合 AI Album 的名称、变量集合和刷新生命周期 | 适合一次短期、可撤销的通路验证；不建议成为长期合同 |
| **B. DotFiles 生成 `mediasense` narrow profile** | 复用现有 Vault、两个 identity、catalog、producer、目录和测试框架；只增加两变量 consumer projection | 只向 MediaSense MCP child 暴露 `AMAP_API_KEY` 与 `GOOGLE_MAPS_API_KEY` | 需更新 DotFiles manifest、producer tests、machine acceptance，并新建 Codex session | **长期推荐；责任最清楚、最小权限、通过独立责任测试** |
| **C. 全局加载 `~/.env` 或 Secret profile** | 把 legacy 文件或 narrow profile提升为 shell/login-session 输入，并需新增 GUI 注入与撤销合同 | cmux、Codex 及大量无关后代进程都可见 Secret | 与现有 S26 安全边界冲突，重启、轮换和陈旧环境最复杂 | 不推荐 |

## Why option B is the professional default

方案 B 对应常见的最小权限实践：Secret value 只在专门的 Secret manager 中
维护；由一个受控 producer 生成权限收紧、可原子替换的 consumer-specific
projection；只在真正需要凭据的进程边界注入；配置文件只保存变量名和启动
方法，不保存 value；轮换后通过新进程获得新环境。

它不是建立第二套 Secret 管理。`mediasense.zsh` 与现有 `ai-album.zsh` 一样只是
DotFiles 管理的可重建投影。若删除它，MediaSense 独立的两项最小 key 集合、
标准变量接口和 stdio session 生命周期就失去诚实承载者；因此该实体有独立
目的。相反，MediaSense wrapper、Keychain item、通用 Agent profile、launchd
注入服务或第二个 registry 都没有新增独立责任，不能成立。

## Implemented option B

实施由两个既有权威分别完成，没有新设第三个协调层：

1. DotFiles 通过独立 OpenSpec change，把两个既有 Credential identity 绑定到
   `mediasense` profile，并由现有 `dotfiles-secrets-refresh` 安全生成投影。
2. 用户在授权终端执行了正式 refresh；验收只检查文件权限与变量名集合，没有输出
   value。
3. Honeycomb 的项目级 Codex MCP 配置只在 child 启动边界加载该投影并启动
   `mediasense mcp`；TOML 中没有 Secret value。
4. 新 Codex session/MCP child 已确认六个 Tool 可发现，两个 Provider 均为
   configured/available。
5. 没有自行启动新的 PreCheck Run。旧 Run 已终止，不能被凭据变更恢复；未来新的
   Geo acquisition 仍须按 PreCheck 的 exact scope 与 elicitation 合同获得 Human 决定。

这些步骤描述责任与验收，不固定 producer 的内部函数拆分或 Codex 启动命令的
具体写法。

## Acceptance state

本 package 的 closing judgment 已完成：用户选择的方案 B 已在 DotFiles 权威中
实现并通过 repository 与 machine acceptance；Honeycomb 的 child-only MCP 接入已
落盘并由真实新 Codex 会话验证。MediaSense runtime 未改动，Secret value 未进入
仓库、TOML、报告或普通父进程环境。

本次不声称 Geo acquisition 已执行。当前完成的是安全凭据投放和 Provider
availability；未来具体坐标外发必须由新 Run 的精确 disclosure 和 Human elicitation
单独授权。DotFiles OpenSpec packet 的归档与 Git commit 同样不在本次授权内。
