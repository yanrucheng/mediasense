---
id: "01-result-dotfiles"
title: "DotFiles Result for the git lg cmux Ref Filter"
type: delegation
status: draft
created: 2026-08-31
updated: 2026-08-31
timezone: "Asia/Shanghai"
parent: "td-260831-1739-git-lg-cmux-filter"
depends-on:
  - "01-request-dotfiles"
superseded-by: ""
---

# DotFiles 原始执行报告

## 结果

DotFiles 已在其权威 Git 配置源中实现选定的 cmux last-turn ref 过滤，并以字段级方式收敛当前 HOME 投影。MediaSense 中的 cmux recovery refs、stash-shaped commits、branch、stash 和 repository history 均未删除或改写。

权威变更已经形成一个只包含 `/Users/chengyanru/repos/personal/dotfiles/dot_gitconfig` 的原子提交，提交主题为：

`fix(git): exclude cmux recovery refs from lg`

综合验收、delegation 状态更新与关闭仍由发起方负责。

## 权威与变更入口

- 设备无关标准：`/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml`
- 相关 Managed Unit：S08「Git 日常配置与 Work identity」
- 当前设备映射：`/Users/chengyanru/repos/personal/dotfiles/docs/environment/machines/work-mac-2026/mapping.yaml`
- canonical source：`/Users/chengyanru/repos/personal/dotfiles/dot_gitconfig`
- HOME projection：`/Users/chengyanru/.gitconfig`

S08 已确认通用 gitconfig 由 DotFiles 管理；本次只是在既有权威和行为合同内维护 alias，属于普通仓库维护，不需要新建 OpenSpec packet。当前 `/Users/chengyanru/repos/personal/dotfiles/openspec/changes/register-dotfiles-team/` packet 仅涉及 S15，未被本次工作修改。

## 权威 alias 的精确改动

修改前：

```gitconfig
lg3 = log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ad)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)' --all --date=human-local
```

修改后：

```gitconfig
lg3 = log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ad)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)' --exclude='refs/cmux/last-turn/*' --all --date=human-local
```

逐键比较 HEAD 与工作结果证明，canonical config 中只有 `alias.lg3` 改变；移除新增的 `--exclude='refs/cmux/last-turn/*'` token 后，新旧值完全相同。因此以下内容均保持：

- 原有密集单行 format
- 颜色
- `%ad` 日期与 `--date=human-local`
- `%an` 作者
- `--decorate`
- `--graph`
- `--abbrev-commit`
- `alias.lg = !git lg3`
- `lg1`、`lg2` 及所有其他 alias

`--exclude` 位于 `--all` 之前，这是 Git 使 exclusion pattern 作用于随后 `--all` 展开的必要顺序。可见行为上，`git lg` 和直接调用 `git lg3` 都使用过滤后的默认图；未修改的 `lg1`、`lg2` 与显式 `git log --all` 仍遍历全部 refs。

## 当前 HOME 的安全收敛

修改前，对 `/Users/chengyanru/.gitconfig` 运行仅路径状态检查得到：

```text
M /Users/chengyanru/.gitconfig
```

语义比较发现，当时 canonical 有 24 个配置项，HOME 有 25 个；所有 alias 完全相同，唯一额外项为：

```text
core.hooksPath=/Users/chengyanru/.bytesec/commit_hook/
```

该目录存在并包含活动 Git hooks。DotFiles 的 S38 已把 ByteSec 归为当前设备外部工具：不跨设备恢复、不并入 DotFiles，同时未授权删除当前文件。因此没有运行会覆盖整份 `/Users/chengyanru/.gitconfig` 的 chezmoi apply，而是只定点替换 `alias.lg3`。更新后：

- HOME 的所有 `alias.*` 与 canonical source 语义一致；
- HOME 相对 canonical 的唯一配置键差异仍是 `core.hooksPath`；
- ByteSec hooksPath 和其他 HOME 配置均被保留；
- chezmoi 仍把该目标标为 `M`，这是已知外部键导致的预期结果，而不是 alias 未收敛。

仓库一般支持的整目标命令是：

```sh
rtk chezmoi -S /Users/chengyanru/repos/personal/dotfiles apply --interactive /Users/chengyanru/.gitconfig
```

本次没有执行它，因为当前文件含需保留的 HOME-only ByteSec 配置。

## 实际修改命令

canonical source 通过 reviewable patch 修改。HOME 使用的定点命令为：

```sh
rtk git config --file /Users/chengyanru/.gitconfig --replace-all alias.lg3 "log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ad)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)' --exclude='refs/cmux/last-turn/*' --all --date=human-local"
```

原子提交命令为：

```sh
rtk git commit --only -m 'fix(git): exclude cmux recovery refs from lg' -- dot_gitconfig
```

该提交只包含：

```text
/Users/chengyanru/repos/personal/dotfiles/dot_gitconfig
```

预先存在的以下 DotFiles 工作树内容保持未提交、未修改：

- `/Users/chengyanru/repos/personal/dotfiles/docs/environment/machines/work-mac-2026/mapping.yaml`
- `/Users/chengyanru/repos/personal/dotfiles/docs/environment/standard/manifest.yaml`
- `/Users/chengyanru/repos/personal/dotfiles/dot_agents/custom/teams/dotfiles.md`
- `/Users/chengyanru/repos/personal/dotfiles/openspec/changes/register-dotfiles-team/`

## 行为验收

验收仓库为 `/Users/chengyanru/repos/personal/mediasense`。

关键只读命令包括：

```sh
rtk git for-each-ref --format='%(refname)' refs/cmux/last-turn
rtk proxy git --no-pager lg --no-color
rtk proxy git --no-pager log --all --format=%s
rtk git rev-list --count --exclude=refs/cmux/last-turn/* --all
rtk git rev-list --count --branches --remotes
```

验证结果：

- MediaSense 仍有 63 个 `refs/cmux/last-turn/*`，与修改前相同；
- 默认 `git lg` 不再出现 `cmux last turn baseline` 或 `index on main:` recovery subjects；
- 显式 `git log --all` 仍能看到这些 recovery subjects；
- 过滤后的 reachable commit 数为 35，与当前 branches/remotes 的 reachable commit 数 35 一致；
- 强制颜色执行时仍产生 ANSI color sequences；
- canonical 与 HOME 的全部 alias 集合相等；
- `alias.lg` 仍精确委托 `!git lg3`；
- `git diff --check -- dot_gitconfig` 无错误；
- 没有执行 ref 删除、stash 操作、history rewrite 或 MediaSense 产品文件修改。

## 扩展的当前设备漂移调查

用户最终确认前补充执行了全量、仅路径的：

```sh
rtk chezmoi -S /Users/chengyanru/repos/personal/dotfiles status --path-style=absolute
```

该审计纠正了早先只从 `.gitconfig` 推断全局状态的过窄结论。除 `.gitconfig` 外，下列差异的目标修改时间均早于本次 delegation；它们不是本次 alias 工作造成的。

| HOME 目标 | 当前差异 | 判断与处置 |
| --- | --- | --- |
| `/Users/chengyanru/.agents/.skill-lock.json` | JSON 语义相同；HOME 为 `0644`，canonical 期望 `0600` | 既有权限漂移；未修改 |
| `/Users/chengyanru/.agents/custom/teams/data-validation-production.md` | HOME 出现 `Historical identity`、`Historical operating context`、`Retirement and succession` 等较新的本地语义，canonical 内容不同 | 可能是尚未回收进 DotFiles 的 Team Fact 演进；不得覆盖，需单独权威对账 |
| `/Users/chengyanru/.config/dotfiles` | HOME 目录为 `0700`，canonical 期望 `0755` | 既有权限漂移；未放宽 |
| `/Users/chengyanru/.config/dotfiles/templates/pancode-config.json` | JSON 语义相同；HOME 为 `0600`，canonical 期望 `0644` | 既有权限漂移；未放宽 |
| `/Users/chengyanru/.config/openspec/config.json` | HOME 额外保留 `telemetry` | 属于旧 OpenSpec 全局配置和 stop-management 边界；未清理 |
| `/Users/chengyanru/.config/zsh/aliases.zsh` | HOME 仍有 `brew_python`、`go1.17`、`gr` 三个 legacy alias | canonical 已按确认决定排除显式 Homebrew Python/旧 Go；未覆盖或清理 HOME |
| `/Users/chengyanru/.config/zsh/toolchains.zsh` | HOME 仍有 Go、Java、pyenv、rbenv 相关 PATH、变量和入口 | canonical 已按 S11 决定排除这些旧 toolchains；未覆盖或清理 HOME |
| `/Users/chengyanru/.gitconfig` | HOME-only ByteSec `core.hooksPath` | S38 外部本机状态；保留 |

全量状态同时提示 chezmoi config template 已变化、需要重新 init。仓库合同禁止在未审查实际目标影响时仅为消除警告而提高 baseline 标记，因此本次没有执行 init 或全量 apply。

## Audio Recorder 新实现

仅检查 chezmoi 受管目标会漏掉外部项目投影。进一步调查确认，本机已经有新的独立 Audio Recorder 能力：

- 权威项目：`/Users/chengyanru/repos/personal/audio-recorder`
- 稳定命令：`/Users/chengyanru/.local/bin/audio_record_toggle`
- 版本安装根：`/Users/chengyanru/.local/share/audio-recorder/versions/`
- 当前版本指针：`/Users/chengyanru/.local/share/audio-recorder/current` → version `0.1.3`
- 上一版本指针：`/Users/chengyanru/.local/share/audio-recorder/previous` → version `0.1.2`
- Hammerspoon Spoon：`/Users/chengyanru/.hammerspoon/Spoons/AudioRecorder.spoon`
- Hammerspoon bootstrap：`/Users/chengyanru/.hammerspoon/init.lua`

上述投影创建于 2026-08-31 17:23（Asia/Shanghai），早于本 delegation 的 17:39。它们不是本次 Git alias 操作产生的。

`/Users/chengyanru/repos/personal/audio-recorder` 自己声明为 `audio_record_toggle` 和 Hammerspoon `option+R` 集成的权威 release project；仓库工作树干净。只读检查结果为：

```text
installed version: 0.1.3
doctor: 23 pass, 0 warning, 0 failure
```

`/Users/chengyanru/repos/personal/audio-recorder/openspec/changes/extract-audio-recorder-standalone/tasks.md` 中的 7.1–7.5（观察期、rollback/forward 演练、旧权威退休与 archive）仍未完成。因此：

- Audio Recorder 的实现、版本、安装包和运行恢复不应复制进 DotFiles；
- DotFiles 的 S12/S37 machine realization 已落后于当前本机事实：S12 仍写 `not-implemented`，S37 仍未反映由外部项目提供的 recorder-specific Hammerspoon 投影；
- 这需要 Audio Recorder 稳定后单独做跨权威 handoff 和 machine mapping 对账，不应夹带进本次 S08 alias 维护；
- 当前已 dirty 的 `/Users/chengyanru/repos/personal/dotfiles/docs/environment/machines/work-mac-2026/mapping.yaml` 属于另一项在途工作，本次未覆盖。

## 其他持久化影响

因为 HOME 保留了 `core.hooksPath=/Users/chengyanru/.bytesec/commit_hook/`，创建 DotFiles 提交时 ByteSec hook 正常运行，并更新了其运行结果文件：

`/Users/chengyanru/.bytesec/commit_hook/commit_result.json`

该文件的修改时间与提交时间一致。它是 ByteSec 外部运行记录，不是 DotFiles 配置；同一 hook 目录内没有发现其他在本 delegation 期间修改的文件。

除这一 hook 运行记录、`/Users/chengyanru/.gitconfig` 的定点 alias 更新、DotFiles canonical source 及其原子提交外，没有发现本次工作造成的其他相关 HOME 或仓库配置变化。

## 未完成事项

1. 发起方尚需综合验收本报告并决定 delegation 是否关闭。
2. S08 machine mapping 中“受管 Git 配置与真实 HOME 字节一致”的表述已不再准确；当前应描述为 canonical alias 已收敛、HOME 另有明确外部 ByteSec 键。由于 mapping 正被 S15 packet 修改，本次未重写。
3. Audio Recorder 的 S12/S37 current-machine realization 需要在其项目完成观察、rollback/forward 和权威退休后单独对账。
4. `/Users/chengyanru/.agents/custom/teams/data-validation-production.md` 的 HOME-local Team Fact 演进需要确认真正权威后再决定回收或保持外部；不得用全量 chezmoi apply 覆盖。
5. 其余权限、legacy alias/toolchain 和 OpenSpec config 漂移均需要各自授权与验收；本报告不把它们冒充为已收敛。

## 恢复方法

canonical 变更由单文件原子提交承载。若决定撤销：

1. 在 `/Users/chengyanru/repos/personal/dotfiles` 中定位主题为 `fix(git): exclude cmux recovery refs from lg` 的提交，并使用 `git revert` 创建反向提交；不要 reset、checkout 或覆盖其他 dirty 工作。
2. 仅定点恢复 HOME alias：

```sh
rtk git config --file /Users/chengyanru/.gitconfig --replace-all alias.lg3 "log --graph --abbrev-commit --decorate --format=format:'%C(bold blue)%h%C(reset) - %C(bold green)(%ad)%C(reset) %C(white)%s%C(reset) %C(dim white)- %an%C(reset)%C(bold yellow)%d%C(reset)' --all --date=human-local"
```

3. 复查：

```sh
rtk git config --file /Users/chengyanru/.gitconfig --get alias.lg3
rtk git config --file /Users/chengyanru/.gitconfig --get core.hooksPath
```

撤销 alias 不需要也不得删除任何 `refs/cmux/*`。不要用整文件 chezmoi apply 作为本次恢复手段，否则会同时影响本报告列出的本机差异。
