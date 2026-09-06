---
id: "01-result-dotfiles"
title: "DotFiles Research Result for MediaSense Credential Delivery"
type: delegation
status: draft
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-1032-mediasense-dotfiles-env"
depends-on:
  - "01-request-dotfiles"
superseded-by: ""
---

# DotFiles 对 MediaSense Credential 投放的只读调研

## 结论先行

MediaSense 不应新建 Secret store、Keychain item、Credential registry、独立 env-file producer 或专属包装脚本。现有权威边界已经足够清楚：Bitwarden Password Manager 持有 Secret value，DotFiles 持有 repository-safe Credential identity、消费者 binding 和窄投放实现，具体机器 mapping 记录本机 realization，生成文件只是可重建 projection；MediaSense 应只消费启动进程环境中的标准变量名，并至多保留现有的非秘密变量名映射能力。

用户所说的 DotFiles “env file 的安全管理和生产”，按当前 active contract/code，最准确地对应 `/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh`，不是 `/Users/chengyanru/.env`。前者由 `/Users/chengyanru/.local/bin/dotfiles-secrets-refresh ai-album` 生成，具有已测试的精确 Vault lookup、严格校验、`0700` 目录、`0600` 文件、同目录临时文件、原子替换和失败保留旧文件语义；后者是保留原有变量名、赋值位置和加载方式的 legacy 本地文件，不是当前 refresh command 的输出，也不是 Secret value 的权威。

当前失败的直接原因不是 CLI、Skills、MCP 注册或 projection 不存在，而是进程投放链路缺失：active Zsh 启动不读取 `/Users/chengyanru/.env`，也明确不全局读取 `/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh`；现有 profile 只由 `drun` 在函数局部作用域读取。GUI 启动的 cmux、cmux 启动的 Codex 以及 Codex 启动的 `mediasense mcp` 因而没有合同保证会获得这些变量。当前 shell 与当前用户 launchd 环境中，`AMAP_API_KEY`、`GOOGLEMAP_API_KEY`、`GOOGLE_MAPS_API_KEY` 均观测为 absent。

此外存在一个真实但次级的接口差异：DotFiles 的既有 AI Album profile 生成 `GOOGLEMAP_API_KEY`，MediaSense 默认读取 `GOOGLE_MAPS_API_KEY`。AMap 名称双方一致。MediaSense 已有只保存变量名、不保存 value 的 `google_maps_api_key_env` 配置，因此复用旧 profile 时可用这个最小非秘密 mapping；若 DotFiles 增加 MediaSense narrow profile，则应直接生成 MediaSense 的标准名 `GOOGLE_MAPS_API_KEY`，MediaSense 保持默认值即可。

推荐的最小持久方案是：**由现有 `dotfiles-secrets-refresh` 增加一个只含 AMap 和 Google Maps 两项的 `mediasense` narrow profile，再由 Honeycomb 的 MCP 启动边界读取该 profile 并 `exec mediasense mcp`。** 这会增加一个有真实独立消费者和生命周期的 projection，但不增加 producer、store、identity registry 或 wrapper；它比直接复用六变量 AI Album profile 少暴露四个无关 Credential，也比全局 Shell/GUI 注入显著缩小进程可见范围。

## 调研边界与证据等级

本次只读检查没有读取、比较或推断任何 Secret value，也没有刷新 projection、解锁 Vault、改变 HOME、启动或重启进程、修改 MCP 配置或接触 Dataset。DotFiles 工作树原有的两处 tracked 修改和相关 untracked 工作均保持不动。唯一写入是本报告。

下文严格使用这些证据类别：

- **当前 active contract**：`/Users/chengyanru/repos/personal/dotfiles/AGENTS.md`、`/Users/chengyanru/repos/personal/dotfiles/docs/environment/index.md`、`/Users/chengyanru/repos/personal/dotfiles/docs/spec/`、`/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml`、`/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/credentials.yaml`。
- **当前代码/配置**：`/Users/chengyanru/repos/personal/dotfiles/dot_local/bin/executable_dotfiles-secrets-refresh`、`/Users/chengyanru/repos/personal/dotfiles/dot_config/zsh/`、`/Users/chengyanru/repos/personal/dotfiles/tests/test_bw_secret_delivery.sh`，以及 MediaSense 的 `/Users/chengyanru/repos/personal/mediasense/src/mediasense/runtime/config.py`、`/Users/chengyanru/repos/personal/mediasense/src/mediasense/runtime/mcp_host.py` 和目标 Honeycomb 的 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml`。
- **当前机器只读观测**：文件存在性和 mode、变量名是否声明或出现在进程环境中、部署文件是否与当前 DotFiles source 相同；没有读取 value。
- **历史/archived 材料**：`/Users/chengyanru/repos/personal/dotfiles/docs/design/design-260811-1119-bitwarden-password-manager.md` 是 active rationale 而非 live inventory；`/Users/chengyanru/repos/personal/dotfiles/docs/design/design-260811-0144-bitwarden-secrets-manager.md` 已明确 archived，仅用于确认 BWS 不是当前运行方案。
- **推断**：标准操作系统父子进程环境继承、进程启动后环境快照及方案取舍。凡是 DotFiles 没有明文承诺的地方，本文不把这种机制推断写成现有合同保证。

## 1. 四层权威与 `/Users/chengyanru/.env` 的地位

| 信息或资产 | 权威拥有者 | 当前权威位置或生命周期 | 结论 |
| --- | --- | --- | --- |
| Secret value | Bitwarden Password Manager | 外部 Vault；DotFiles 只通过正式 `bw` reader 在显式 refresh 中读取 | 不属于 Git、MediaSense config、Honeycomb config、生成文件或 machine mapping 的事实权威 |
| repository-safe Credential identity | DotFiles credential catalog | `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/credentials.yaml` | `cred:location/amap` 与 `cred:location/google-maps` 均已正式存在，value authority 都是 `bitwarden-password-manager` |
| 设备无关消费者 binding 与 delivery 名称 | DotFiles standard manifest | `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml` | S13 把两个 identity 绑定到 AI Album consumer/profile；消费者反查必须从这里进行，不能维护第二份列表 |
| 当前机器 realization、观察与验收 | DotFiles machine mapping | `/Users/chengyanru/repos/personal/dotfiles/docs/environment/machines/work-mac-2026/mapping.yaml` | S25/S26 记录本机 B2 identities、AI Album profile 和安全边界已验收；mapping 不反向定义 identity 或消费者合同 |
| 生成的 env/profile 文件 | DotFiles 窄投放生命周期产生的本地 projection | `/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh` | 可由 Vault 和 repo-safe contract 重建，不是 Secret value 或 binding 的权威 |
| MediaSense 读取接口 | MediaSense | 子进程环境变量；变量名 mapping 是非秘密配置 | MediaSense 不应知道 Bitwarden locator、Vault schema 或 projection 刷新生命周期 |

`/Users/chengyanru/.env` 不是当前 active `dotfiles-secrets-refresh` 的生成目标。当前设计只要求若干 legacy 变量继续保留原有变量名、赋值位置和加载方式，并明确说它们不构成新的 Password Manager 投放设计。当前机器只读观测只确认：该文件存在、mode 为 `0600`，并有 `AMAP_API_KEY` 与历史名 `GOOGLEMAP_API_KEY` 的 assignment-only 声明；没有读取 value。active Zsh 配置没有 source 该文件。因此不能把 `/Users/chengyanru/.env` 称为人工的 Secret value 权威，也不能把它称为当前生成 projection；它只是一个保留的 legacy 本地消费者文件，其值最终仍应服从 Bitwarden 的 value authority。

相比之下，`/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh` 是当前已实现、已测试、已在 machine mapping 验收的生成 projection。若用户口中的 “DotFiles 已负责 env file 的安全管理和生产” 指当前正式能力，应理解为这条 narrow-profile 能力，而非 legacy `/Users/chengyanru/.env`。

## 2. 正式 profile、命令、目标文件与变量名

### 当前 active contract

`/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml` 的 S13 已包含：

| Credential identity | Delivery | 生成的 consumer name |
| --- | --- | --- |
| `cred:location/amap` | `ai-album-profile` | `AMAP_API_KEY` |
| `cred:location/google-maps` | `ai-album-profile` | `GOOGLEMAP_API_KEY` |

同一个 profile 还包含 `SILICONFLOW_API_KEY`、`VOLCE_ARK_API_KEY`、`VOLCE_ARK_BYTEDANCE_API_KEY`、`VOLCE_ARK_GLOBALDATA_API_KEY`，共六项。

S26 把“窄 Credential 投放”定义为 DotFiles 与 Bitwarden 的共同边界，要求最小权限、严格校验、原子替换、失败保留旧文件；同时明确排除通用 Agent profile、全局 Shell Secret profile、任意 Item adapter、第二份 Secret cache，以及 `chezmoi apply`/日常请求中的隐式 Vault 访问。

### 当前 code 与 supported command

受支持命令为：

```text
/Users/chengyanru/.local/bin/dotfiles-secrets-refresh ai-album
```

其 repo source 是 `/Users/chengyanru/repos/personal/dotfiles/dot_local/bin/executable_dotfiles-secrets-refresh`。当前机器的 deployed command 与 repo source 相同。该命令生成：

```text
/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh
```

当前实现先精确解析 `Developer/Credentials/location` 与 `Developer/Credentials/ai-service` Folder，再以 exact item identity 和 ID 读取并验证唯一 Hidden Field。六项全部成功后才替换文件。目录 mode 为 `0700`，文件 mode 为 `0600`。当前机器只读观测确认目标文件存在且为 `0600`；本次没有刷新，也没有验证它与 Vault 当前版本是否新鲜。

另一个受支持 profile 是 `dotfiles-secrets-refresh pancode <aidp|globaldata>`，目标为 `/Users/chengyanru/.pancode/config.jsonc`；它与本问题的地图 Credential 无关，不能作为 MediaSense 投放入口。

### 命名差异

MediaSense `/Users/chengyanru/repos/personal/mediasense/src/mediasense/runtime/config.py` 的默认接口是：

- AMap：`AMAP_API_KEY`；
- Google Maps：`GOOGLE_MAPS_API_KEY`。

其 `[providers]` 配置可把 `amap_api_key_env`、`google_maps_api_key_env` 映射到其他**环境变量名**，配置不保存 Secret value。当前 macOS 默认用户配置 `/Users/chengyanru/Library/Application Support/MediaSense/config.toml` 不存在；目标 Honeycomb 中只观测到 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml`，未发现另一个 `config.toml`。因此当前运行使用默认变量名。

结论：AMap 不存在命名冲突；Google Maps 存在 `GOOGLEMAP_API_KEY` 与 `GOOGLE_MAPS_API_KEY` 的接口差异。该差异不能仅凭历史 `drun` 消费者决定改 DotFiles 还是改 MediaSense，应在选定 delivery boundary 后处理。

## 3. 从文件到普通 shell、cmux、Codex 和 MCP child 的实际链路

### 已由合同保证的链路

当前唯一完整且有测试的地图 Credential 消费链路是：

```text
Bitwarden Password Manager
  -> dotfiles-secrets-refresh ai-album
  -> /Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh
  -> drun 函数局部 source
  -> 本次 docker run 子进程
```

`/Users/chengyanru/.config/zsh/functions/drun` 先声明六个 Zsh local 变量，再 source profile，并通过 `docker run --env NAME` 传给单次容器。测试明确确认函数返回后六个变量不留在交互 shell。这个“局部、单消费者”的限制是安全设计，不是遗漏。

### 普通 shell

`/Users/chengyanru/.zshenv` 只设置 XDG 目录和 `ZDOTDIR`。`/Users/chengyanru/.config/zsh/.zshrc` 读取 `/Users/chengyanru/.config/zsh/env.zsh` 等模块；`env.zsh` 读取的是 uv 的 `/Users/chengyanru/.local/bin/env`，不是 `/Users/chengyanru/.env`，也不是 Secret profile。active rationale 还明确要求 Zsh 启动不得 source Secret 目录。

所以普通新 Zsh 并不会因文件存在而获得地图变量；当前交互 shell 对三个候选名称的只读检查也均为 absent。

### GUI cmux

active DotFiles code/contract 中没有 `launchctl setenv`、LaunchAgent 或其他把 Secret projection 导入 GUI login session 的机制。当前用户 launchd 环境对三个候选名称的只读检查也均为 absent。

因此，从 Finder/Dock 等 GUI 路径启动的 cmux 没有现有合同保证可见这些变量。仅“刷新文件”或“重新开一个 cmux 窗口”不等于完成投放；文件不会自动变成进程环境。

### cmux -> Codex -> `mediasense mcp`

父进程向新子进程继承已导出的环境是操作系统通常行为，但不是 DotFiles 当前针对该链路的 delivery contract。目标 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml` 目前仅包含：

```toml
[mcp_servers.mediasense]
command = "mediasense"
args = ["mcp"]
```

它没有 source env/profile 的启动边界，也没有 Secret value。MediaSense `/Users/chengyanru/repos/personal/mediasense/src/mediasense/runtime/mcp_host.py` 直接创建 stdio server；`/Users/chengyanru/repos/personal/mediasense/src/mediasense/runtime/config.py` 从自身进程环境检查 provider credential。由此，只有当 Codex 启动 MCP child 时其环境中已经有对应 exported value，MediaSense 才能看到。当前这条前置条件不成立。

### 启动与重启边界

进程环境在进程创建时确定。未来若选择父环境注入，需要完全退出并重新启动持有旧环境的上游进程，再创建新 Codex 会话与 MCP child。若选择在 MCP command 的直接启动边界 source narrow profile，则无需让 cmux 或 Codex 父进程持有 Secret，但仍须启动新的 Codex session/MCP child；现有 stdio child 不会动态重载。MediaSense 自己的 Skill 也要求 MCP 配置变化后新建 session，不能声称当前 session 动态加载了新配置。

## 4. 当前失败的原因分解

| 候选原因 | 当前判断 | 证据与限制 |
| --- | --- | --- |
| 未刷新 projection | **不是当前最直接原因；新鲜度未确认** | `/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh` 已存在且为 `0600`，machine mapping 记录已验收。但本次禁止访问 Vault，因此不能确认 projection 是否反映最新轮换。即使它是最新的，当前 MCP 仍不会自动读取它。 |
| 未加载 / 未 export | **AMap 的直接原因；Google Maps 也受影响** | active Zsh 不 source `/Users/chengyanru/.env` 或 AI Album profile；当前 shell 和 launchd 均无这些变量。`/Users/chengyanru/.env` 中相关声明还是 assignment-only，即便某处普通 source，也不会自然导出给后续子进程，除非加载边界显式 export 或启用等价语义。AI Album profile 自身使用 `export`，但只被 `drun` 局部 source。 |
| 变量命名不一致 | **Google Maps 的独立问题，不解释 AMap** | DotFiles profile 为 `GOOGLEMAP_API_KEY`，MediaSense 默认为 `GOOGLE_MAPS_API_KEY`；`AMAP_API_KEY` 两边一致。必须先建立投放链路，再通过 MediaSense 非秘密 mapping 或新 profile 的标准名解决。 |
| 会话未重启 | **可能是后续生效条件，但不是现状根因** | 当前根本没有为 cmux/Codex/MCP 建立注入。只重启现有链路仍会得到 absent。完成某个启动边界后，必须新建相应进程/session。 |
| 现有合同缺口 | **是根本原因** | S13/S26 只承诺 AI Album/`drun` narrow profile；S27 的 Codex 条目只涉及通过 Pancode 间接消费 ModelHub。没有 MediaSense consumer binding，没有 GUI cmux 投放，也没有 stdio MCP child 的 Secret loading contract。 |

因此，目标 PreCheck 在 required Geo acquisition fail-closed 与当前证据一致：MediaSense 进程按默认变量名检查自己的环境，AMap value 没有进入该环境，Google Maps 既没有进入环境又存在历史变量名差异。

## 5. 三个可选方案

### 方案 A：直接复用现有 AI Album profile

**复用实体**

- Bitwarden 中既有 `cred:location/amap`、`cred:location/google-maps`；
- `/Users/chengyanru/.local/bin/dotfiles-secrets-refresh ai-album`；
- `/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh`；
- MediaSense 已有的非秘密 `google_maps_api_key_env` mapping；
- Honeycomb 的 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml`。

**需要改变的权威文件或运行步骤**

- 不改变 Credential catalog 或 Secret store。
- 在 MediaSense user/Dataset config 中将 Google Maps 的变量名映射到 `GOOGLEMAP_API_KEY`，或在 MCP 直接启动边界将其规范化为 `GOOGLE_MAPS_API_KEY`；二选一，不维护两套事实。
- 让 MCP 启动 command 在 child 边界 source 已有 profile 后 `exec mediasense mcp`。可直接表达在项目 `.codex/config.toml` 的 command/args 中，不需要新增 wrapper 文件。若要把 MediaSense 认定为 AI Album profile 的正式消费者，还应更新 DotFiles manifest binding；否则这只能算临时、未入合同的复用。
- projection 新鲜度有疑问时，由用户在授权的交互终端显式运行已有 refresh；本报告不执行。

**是否涉及 Secret value**

配置变化本身不含 value。运行 refresh 会从 Vault 读取并原子更新现有 Secret-bearing projection；MCP 启动时会读取该文件。

**适用范围与启动边界**

可只作用于这个 Honeycomb 启动的 MediaSense MCP child，不必注入 cmux/Codex 父进程。修改 MCP config 或更新 profile 后需新建 Codex session/MCP child。

**安全属性**

沿用成熟的 `0600`、严格校验与失败保留旧文件。但 profile 包含六项 Credential；若直接 source 后 exec，MediaSense child 会获得四项无关 Secret。可在 exec 前显式 unset 无关变量，但启动 shell 仍短暂读取全部六项，且 MediaSense 与 AI Album 的投放生命周期被耦合。

**验证方法**

- 只按变量名确认新 MCP child 中 AMap 与映射后的 Google Maps 为 present，不输出 value；
- 调用 `mediasense.dataset.open`，确认 provider status 为 `configured`/`available` 且不回显 value；
- 用相同授权重新执行 required Geo PreCheck，确认不再因 credential absent fail-closed；
- 确认四个无关变量在最终 MCP child 中 absent（若采用过滤）。

**主要代价**

改动最少、可快速验证，但消费者边界不诚实、最小暴露较差，且继承了 `GOOGLEMAP_API_KEY` 历史拼写。适合作为经用户明确接受的短期验证，不是首选的长期合同。

### 方案 B：由现有 producer 增加 MediaSense narrow profile（推荐）

**复用实体**

- 同一 Bitwarden Password Manager、两个既有 B2 identities、同一个 repository-safe catalog；
- 同一个 `/Users/chengyanru/.local/bin/dotfiles-secrets-refresh` producer 及其 exact lookup、fail-closed、locking、atomic replace、安全输出和测试框架；
- 同一个 `/Users/chengyanru/.config/dotfiles/secrets/` 窄投放目录；
- 同一个 Honeycomb MCP 配置边界。

**需要改变的权威文件或运行步骤**

- 在 `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml` 增加 MediaSense 对两个既有 identity 的正式 delivery binding；不改 `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/credentials.yaml`，因为 identity 已存在。
- 扩展 `/Users/chengyanru/repos/personal/dotfiles/dot_local/bin/executable_dotfiles-secrets-refresh`，增加明确的 `mediasense` profile，生成 `/Users/chengyanru/.config/dotfiles/secrets/mediasense.zsh`，只包含 `AMAP_API_KEY` 和 `GOOGLE_MAPS_API_KEY`。
- 扩展 `/Users/chengyanru/repos/personal/dotfiles/tests/test_bw_secret_delivery.sh`，复用现有安全与失败语义；真实验收后再更新 `/Users/chengyanru/repos/personal/dotfiles/docs/environment/machines/work-mac-2026/mapping.yaml`。
- 因为这改变 Credential delivery/safety contract，按 DotFiles 治理应先走对应 OpenSpec packet，而不是把当前不相关的 active packet 或 dirty changes混入。
- Honeycomb MCP command 在直接 child 启动边界 source 这个 profile 后 `exec mediasense mcp`。这可内联到现有 `.codex/config.toml`，不需要创建专属 wrapper 实体。

**是否涉及 Secret value**

repo、manifest、测试和 MCP config 不含 value。用户显式运行 refresh 时才从 Vault 读取两个值并写入 `0600` projection；MediaSense 仍只从环境读取，不碰 Vault。

**适用范围与启动边界**

仅适用于 MediaSense MCP consumer，可被选定 Honeycomb 的 stdio child 使用。刷新 projection 后，新启动的 MCP child 读取新文件；不需要把 Secret 注入普通 shell、launchd、cmux 或 Codex 父进程。MCP config 改变后新建 Codex session。

**安全属性**

最小持久化集合和最小进程暴露；不向 MediaSense 暴露 AI Album 的另外四项 key；保持 Bitwarden value authority 和 DotFiles delivery lifecycle；不创建第二个 cache，因为这个文件就是面向独立消费者生命周期的唯一 projection。与现有 `0600` 文件一样，它不能对同一 macOS 用户建立真正文件访问隔离，不能宣称超出 Unix mode 的保证。

**验证方法**

- synthetic tests 验证 exact two-item set、标准变量名、`0700/0600`、幂等、原子替换、失败保留、锁与信号清理，以及 stdout/stderr/log 无 value；
- 经用户授权的真实 refresh 后只检查文件存在、mode 和变量名集合，不输出 value；
- 新建 Codex session，确认六个 MediaSense Tools 仍可发现；
- `mediasense.dataset.open` 报告两 provider 已配置，再执行 required Geo PreCheck；
- 确认 MCP child 不含 AI Album 的另外四个变量。

**主要代价**

比方案 A 多一个 projection 和一组正式合同/测试变更，也需要用户授权一次 Vault refresh。但 MediaSense 是新的独立 consumer，所需 key 集合、变量接口和 stdio session 生命周期都与 `drun`/Docker 不同，因此该实体通过独立责任与生命周期检验。它不新增 producer、store、registry 或 wrapper。

### 方案 C：全局 Shell / GUI session env

**复用实体**

可尝试复用 `/Users/chengyanru/.env` 或 AI Album profile，并在 Zsh 启动或 macOS login/launchd 层全局加载。

**需要改变的权威文件或运行步骤**

- 改变 `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml` 的 S26 明确排除项；
- 修改 Zsh env 模块，若还要覆盖 Finder/Dock 启动的 cmux，则必须再增加 GUI login-session 注入与清理/轮换合同；
- 完全退出并重启 cmux，再新建 Codex session/MCP child。仅修改 Zsh 对 GUI cmux 不充分；仅重启 cmux而不建立注入也不充分。

**是否涉及 Secret value**

会让 Secret value 进入更广泛的 shell、GUI 父进程与所有后代进程环境。若使用 `/Users/chengyanru/.env`，还会把非生成 legacy 文件提升为新投放输入，造成 lifecycle 与 authority 模糊。

**适用范围与启动边界**

用户 session 级，远大于 MediaSense 的需要。轮换和撤销需要处理所有长寿命进程及重启边界。

**安全属性**

与当前“无全局 Shell Secret profile”的合同相反；扩大无关进程的可见范围，容易产生陈旧环境，GUI 和 shell 两套入口也增加不可观察差异。

**验证方法**

必须分别验证新 shell、launchd、全新 cmux、全新 Codex 和 MCP child，且只能报告变量 presence，不能输出 value；还要验证退出/轮换后的旧进程不再持有旧环境。

**主要代价**

范围最大、重启最重、安全性最弱、合同变化最大。除非未来出现多个明确需要同一组 Credential 且确实要求 login-session 级共享的消费者，不应采用。

## 6. 最小推荐与 MediaSense 应固定的真实接口

### 推荐

推荐方案 B：**一个由既有 DotFiles producer 生成的 MediaSense narrow profile，直接在 stdio MCP child 的启动边界加载。**

这里“最小”按责任和暴露面衡量，不只按改动行数衡量：

- Secret value 仍只有 Bitwarden 一个权威；
- Credential identity 仍只有 DotFiles catalog 一个权威；
- consumer binding 仍只在 DotFiles manifest；
- env-file producer 仍只有 `dotfiles-secrets-refresh`；
- 不新增 Keychain item、Vault runtime、registry、cache、daemon 或 wrapper 文件；
- 新增的唯一实体是两变量 projection，而 MediaSense 作为独立 consumer 确有不同的变量接口、最小 key 集合和 stdio session 生命周期；
- Secret 不进入普通 shell、launchd、cmux 或 Codex 父进程，只进入需要它的 MCP child。

方案 A 的代码/操作步数更少，可用来做一次短期可撤销验证，但长期会让 MediaSense 依赖名为 `ai-album` 的六变量 projection，并扩大 Secret 暴露。方案 C 不符合现有安全合同。

### MediaSense 一侧应固定的接口

MediaSense 应继续固定以下真实接口：

1. 默认只要求进程环境中的标准名 `AMAP_API_KEY` 与 `GOOGLE_MAPS_API_KEY`。
2. 保留现有 `amap_api_key_env`、`google_maps_api_key_env` 非秘密变量名 mapping，作为旧消费者兼容接口；它只映射名称，不读取或保存 Secret。
3. Provider adapter 只在调用时读取自身进程环境，保持缺失即 unavailable/fail-closed，并且不把 value 放入 result、log、cache、provenance 或 Dataset artifact。
4. MediaSense 不读取 `/Users/chengyanru/.env`、`/Users/chengyanru/.config/dotfiles/secrets/` 或 Bitwarden，不管理 Vault login/unlock/session，不刷新 projection，不判断 Credential identity，也不接管 DotFiles 的轮换、投放和撤销生命周期。
5. MediaSense Skill 可以诊断“所需变量在 MCP child 中未配置”并指出需要重新建立外部 delivery 后新建 session，但不应自动改 HOME、MCP config 或 Secret store。

采用推荐方案 B 时，narrow profile 直接生成 MediaSense 标准名，因此无需新增 mapping 配置；mapping 继续作为已有能力保留。采用短期方案 A 时，仅将 Google Maps 映射到 DotFiles 历史名即可，AMap 保持默认；不得把 Secret value 写入 MediaSense config 或 Honeycomb TOML。

## 尚未确认且必须留给后续授权的事项

- 当前 `/Users/chengyanru/.config/dotfiles/secrets/ai-album.zsh` 是否与 Bitwarden 最新值一致：本次没有解锁或读取 Vault，不能确认。
- 用户最终选择临时复用 AI Album profile，还是建立 MediaSense narrow profile：本报告只给出边界和推荐，不代替用户授权。
- Codex 对内联 shell command/args 的最终可移植表达及退出/错误传播，应在实施时以当前 Codex 配置合同做最小验证；本报告只确认当前 table 直接启动 `mediasense mcp`，没有注入。
- 若选择方案 B，具体 OpenSpec packet 名称、实现函数拆分与 TOML 表达保持开放，不应把临时实现细节提升为永久产品合同。
