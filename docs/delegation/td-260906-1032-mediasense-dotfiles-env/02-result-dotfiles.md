---
id: "02-result-dotfiles"
title: "DotFiles Implementation Result for the MediaSense Narrow Credential Profile"
type: delegation
status: draft
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-1032-mediasense-dotfiles-env"
depends-on:
  - "02-request-dotfiles"
superseded-by: ""
---

# 实施结论

方案 B 已在 DotFiles 仓库完成实现和仓库级验收。独立 OpenSpec change ID 为 `add-mediasense-narrow-profile`。既有 `dotfiles-secrets-refresh` producer 现在提供显式 `mediasense` profile，目标为：

```text
/Users/chengyanru/.config/dotfiles/secrets/mediasense.zsh
```

该 profile 只绑定两个既有 Bitwarden Credential identity：

- `cred:location/amap` / `api_key` → `AMAP_API_KEY`
- `cred:location/google-maps` / `api_key` → `GOOGLE_MAPS_API_KEY`

未新增 Secret authority、Credential identity、通用 registry、第二 producer、wrapper、daemon、cache 或全局 Shell/GUI profile。legacy `/Users/chengyanru/.env` 未读取、未修改，也未成为新合同的 fallback。

当前机器的 producer 定点部署、Human 交互式 Refresh 和无值机器验收均已完成。projection 已生成；S26/S27 已据实更新为 `accepted`。Honeycomb MCP child 接入和 MediaSense Geo 端到端验收仍归 MediaSense 发起方，不属于这次 DotFiles acceptance。

# 实际修改

## DotFiles 既有权威和实现

- `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml`
  - S26 增加 MediaSense 两变量 narrow profile 合同。
  - S27 增加两个正式 consumer bindings，并固定标准变量名。
  - 保留了本任务开始前用户已有的 Team Fact 24→25 修改。
- `/Users/chengyanru/repos/personal/dotfiles/docs/environment/machines/work-mac-2026/mapping.yaml`
  - S26/S27 如实记录 repo implementation、真实 projection 生成和无值验收已完成，并标记为 `accepted`。
  - 保留了本任务开始前用户已有的 Team Fact 24→25 修改。
- `/Users/chengyanru/repos/personal/dotfiles/dot_local/bin/executable_dotfiles-secrets-refresh`
  - 新增 `dotfiles-secrets-refresh mediasense`。
  - 复用既有 exact lookup、完整 Item/field schema 校验、同目录 Secret-bearing temp、原子替换、失败保留旧 target、owned-session relock 与无值 stdout/stderr 合同。
  - MediaSense 使用独立 target lock：`~/.config/dotfiles/secrets/.mediasense.zsh.lock`；锁在 Vault sync 之前取得。
  - AI Album 的六变量接口保持不变，仍使用其既有 `GOOGLEMAP_API_KEY`；MediaSense 独立输出标准名 `GOOGLE_MAPS_API_KEY`。
- `/Users/chengyanru/repos/personal/dotfiles/tests/fixtures/fake-bw`
  - 增加 synthetic-only 的 get-item block/ready seam，用于在 Secret-bearing temp 已存在时验证 SIGTERM cleanup。
- `/Users/chengyanru/repos/personal/dotfiles/tests/test_bw_secret_delivery.sh`
  - 增加 exact two-key、变量集合、权限、幂等、existing-session、lookup/schema/field/replace failure、second-item failure、并发锁和 SIGTERM cleanup 覆盖。
  - 共用既有 failure helper，没有复制第二套完整测试系统。

## 独立 OpenSpec packet

以下文件均位于 `/Users/chengyanru/repos/personal/dotfiles/openspec/changes/add-mediasense-narrow-profile/`：

- `.openspec.yaml`
- `README.md`
- `proposal.md`
- `design.md`
- `tasks.md`
- `specs/mediasense-credential-delivery/spec.md`
- `verification.md`
- `rollback.forward.patch`
- `rollback.reverse.patch`

本 change 未混入或修改用户已有的 `/Users/chengyanru/repos/personal/dotfiles/openspec/changes/register-dotfiles-team/` 与 `/Users/chengyanru/repos/personal/dotfiles/dot_agents/custom/teams/dotfiles.md`。

# 安全语义

实现保持以下 fail-closed 行为：

- 只按 formal identity 和已确认 folder 做 exact Bitwarden lookup；两个 Item 任一缺失、重复、错位、返回 identity/type 不符，都会失败。
- 每个 Item 必须只有一个名为 `api_key` 的非空、单行 Hidden Field；缺失、重复、额外 field、错误 type、空值或多行值都会失败。
- 目标目录为 0700，目标文件为 0600；Secret-bearing temp 与最终文件在同一目录，成功时原子替换。
- MediaSense target-specific lock 拒绝同 profile 并发 Refresh；失败或 signal 会保留旧 target、删除 temp/lock，并在本进程拥有临时 Vault session 时 relock。
- 输出只报告目标路径、profile 和 credential 数量；不输出 Secret value 或 Vault session。

本次实施和验证没有读取、打印、比较、hash、量长度或记录任何真实 Secret value、Bitwarden session 或 token。所有内容级测试值均为 synthetic fixture。

# 验证证据

以下命令均在 `/Users/chengyanru/repos/personal/dotfiles` 执行：

1. Shell syntax：

   ```sh
   rtk sh -n dot_local/bin/executable_dotfiles-secrets-refresh tests/fixtures/fake-bw tests/test_bw_secret_delivery.sh tests/test_recovery_governance.sh
   ```

   结果：exit 0，无输出。

2. ShellCheck：

   ```sh
   rtk shellcheck dot_local/bin/executable_dotfiles-secrets-refresh tests/fixtures/fake-bw tests/test_bw_secret_delivery.sh tests/test_recovery_governance.sh
   ```

   结果：exit 0，无 findings。

3. Focused synthetic delivery：

   ```sh
   rtk sh tests/test_bw_secret_delivery.sh
   ```

   结果：exit 0；输出 `PASS: exact B2 reads, AI Album and MediaSense profiles, and Pancode rendering are atomic, scoped, idempotent, and secret-safe under synthetic tests.`

   该 suite 证明 MediaSense exact two-key set、标准变量名、AI Album-only key 排除、0700/0600、幂等、两个 exact Item read、共享 validation failure matrix、第二 Item 失败保留、replace failure、target-specific concurrency，以及 Secret-bearing temp 已创建后的 SIGTERM cleanup。SIGTERM case 同时证明非零退出、旧 target 保留、temp/lock 清除和 owned-session relock。

4. Repository governance：

   ```sh
   rtk sh tests/test_recovery_governance.sh
   ```

   结果：exit 0；49 Managed Units、19 Credentials、20 bindings、2 active affected declarations 全部解析；18 个 bound identities 具有 inverse consumer lookup；Secret-bearing fields/values 未进入治理权威。

5. Strict OpenSpec 与 whitespace：

   ```sh
   rtk openspec validate add-mediasense-narrow-profile --strict --no-interactive
   rtk git diff --check
   ```

   结果：change valid；diff check exit 0。

6. Rollback isolation：

   - 两份 packet-owned patch 只包含五个已有 tracked implementation targets。
   - 隔离 baseline 先重放用户原有 Team Fact 24→25 增量；reverse patch 恢复到这个保留用户增量的 baseline，forward patch 再恢复当前五个文件。
   - 两个方向的 `git apply --check` 均通过；forward 后五个文件与当前 working tree 逐文件 byte-equal。
   - patch 不包含临时隔离路径或真实 Secret material。

# 当前 HOME 状态

只对以下 producer target 执行了定点 chezmoi apply：

```sh
rtk chezmoi -S /Users/chengyanru/repos/personal/dotfiles apply -- /Users/chengyanru/.local/bin/dotfiles-secrets-refresh
```

结果：

- `/Users/chengyanru/.local/bin/dotfiles-secrets-refresh` 与 repo source byte-equal。
- deployed file mode 为 0755。
- 对该单一 target 的 chezmoi status 已 clean；没有顺带 apply 其他 HOME drift。

随后只尝试了一次真实命令：

```sh
rtk /Users/chengyanru/.local/bin/dotfiles-secrets-refresh mediasense
```

Bitwarden 当时为 locked；非交互执行没有可用 `/dev/tty`，命令以 `bw unlock failed` 结束。按授权边界立即停止，没有在 Agent 侧重复尝试。该尝试确认失败路径没有留下 projection、temp 或 lock。

- `/Users/chengyanru/.config/dotfiles/secrets` 当时仍为 0700。
- `.mediasense.zsh.lock` 和 `.mediasense.zsh.*` temp 均无残留。

# 最终 Human Refresh 与机器验收

Human 随后在真实交互终端成功执行：

```sh
rtk /Users/chengyanru/.local/bin/dotfiles-secrets-refresh mediasense
```

命令输出只表明 `mediasense.zsh` 已更新两个 credentials。随后完成的无值验收确认：

- projection 是 Regular File，owner 为 `chengyanru`，group 为 `staff`，mode 为 0600。
- Secret directory 是 Directory，owner 为 `chengyanru`，group 为 `staff`，mode 为 0700。
- export 变量名集合严格等于 `AMAP_API_KEY` 与 `GOOGLE_MAPS_API_KEY`。
- MediaSense temporary artifacts absent；target lock absent。

验收没有记录任何 Secret value、hash 或长度。DotFiles machine mapping 的 S26/S27 已据此改为 `accepted`。

# MediaSense 发起方接入接口

DotFiles 交付的是一个 consumer-scoped sourceable profile：

- 路径：`/Users/chengyanru/.config/dotfiles/secrets/mediasense.zsh`
- 变量名：`AMAP_API_KEY`、`GOOGLE_MAPS_API_KEY`
- 生命周期：由 Human 显式 Refresh；不是全局 login shell 或 GUI environment。
- 消费边界：发起方在自己拥有的 stdio MCP child 启动边界加载该文件，使变量只进入该 child 的环境。

DotFiles 不修改 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml`，不修改 Honeycomb MCP 配置，不启动或重启 MCP child，也不负责 MediaSense Geo 的端到端验收。上述接入与运行验收仍由 MediaSense 发起方负责。

# 未完成事项与回滚

未完成事项：

1. MediaSense 发起方接入 stdio MCP child，并完成端到端 Geo 验收。
2. OpenSpec packet 归档；归档需要独立授权，本任务没有自行归档或提交。

回滚时只允许使用 `add-mediasense-narrow-profile/rollback.reverse.patch` 恢复五个既有 tracked targets；packet-created files 只能在 provenance 与无他人增量均已证明时移除。不得使用 reset、checkout、restore、整文件覆盖，也不得删除或修改用户的 `register-dotfiles-team` packet 与 `dot_agents/custom/teams/dotfiles.md`。当前没有 Git commit。
