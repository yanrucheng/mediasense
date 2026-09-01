---
id: "01-request-dotfiles"
title: "Apply the Canonical git lg cmux Ref Filter"
type: task-delegation
status: active
created: 2026-08-31
updated: 2026-08-31
timezone: "Asia/Shanghai"
parent: "td-260831-1739-git-lg-cmux-filter"
depends-on: []
superseded-by: ""
recipient: "team:dotfiles"
result-home: "/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260831-1739-git-lg-cmux-filter/01-result-dotfiles.md"
---

以下内容可直接交付给 DotFiles：

````text
你是 DotFiles，工作位置是：

/Users/chengyanru/repos/personal/dotfiles

请与用户交互式完成一个 Git alias 的权威配置修正。用户希望保留现有 `git lg` 的高信息密度、颜色、日期、作者、decorate 和 graph 布局，只让默认视图不再遍历 cmux 生成的 last-turn 恢复快照。

为什么需要你处理

`team:dotfiles` 是跨设备 HOME 环境基线、稳定非秘密配置和重建输入的权威 Team。当前会话位于 MediaSense，但不应直接把 `~/.gitconfig` 当作独立权威修改。你必须先完整遵守 DotFiles 仓库的 `AGENTS.md`、`docs/environment/index.md`、相关正式合同和标准事实，定位 Git alias 的 canonical source 以及当前设备的受支持收敛方式。

已经确认的当前行为

- 有效 `alias.lg` 为 `!git lg3`。
- 有效 `alias.lg3` 保留用户偏好的密集单行格式，并包含 `--all`。
- MediaSense 仓库存在大量 `refs/cmux/last-turn/*`；`--all` 会从这些自定义 refs 开始遍历，因此 `git lg` 出现大量 `On main: cmux last turn baseline` 和 `index on main: ...` 的 stash-shaped 双亲提交。
- 这些 refs 是恢复证据，不应删除；Git history 也不需要重写。

用户已选择的目标改动

在 DotFiles 的 authoritative `alias.lg3` 定义中，只把：

`--all`

替换为：

`--exclude='refs/cmux/last-turn/*' --all`

保持原有 format、颜色、日期、作者、decorate、graph、`alias.lg = !git lg3`、`lg1` 和 `lg2` 不变。不要改成另一套低密度展示，也不要把 project-facing ref allowlist 作为替代方案。

交互与执行边界

1. 先调查并向用户说明 canonical source、拟修改的精确文件、当前 HOME 是否只是 projection、受支持的收敛命令，以及所有可见和持久化影响。
2. 等待用户在这个交互工作线中明确确认后，才能编辑或运行会改变 DotFiles/HOME 状态的命令。父会话确认了目标和交互执行方式，但不替代此处对精确文件与效果的可见确认。
3. 只修改 DotFiles 自己授权的 canonical 文件，以及在其正式合同允许且用户确认后所需的当前设备 projection。保留所有无关和未提交工作。
4. 如果 DotFiles 合同不允许由你更新真实 HOME，只完成其授权的 canonical 改动，并明确给出剩余 handback；不要绕过边界直接编辑 `~/.gitconfig`。
5. 不得删除或改写任何 `refs/cmux/*`、stash、commit、branch 或 repository history，也不得修改 MediaSense 产品文件或其他 alias。

验收证据

- 展示修改前后的 authoritative alias 定义，并证明只有选定的 scope token 改变。
- 若当前 HOME 已按合同收敛，展示 `git config --global --get alias.lg3` 的有效结果。
- 在含 cmux last-turn refs 的仓库验证默认 `git lg` 不再显示 `cmux last turn baseline` 或 `index on main:` 快照提交。
- 验证显式 `git log --all` 仍能看到这些恢复提交，从而证明 refs 未被删除。
- 验证 `alias.lg`、`lg1`、`lg2` 和其他无关配置保持不变。
- 最终报告列出准确文件、实际命令、验证结果、未完成事项和恢复方法。

返回要求

这是 user-interactive 工作。完成调查后先让用户确认精确修改和效果；修改与验证完成后，在最终结果写回前再次请求用户确认。未经最终确认，不得声称完成或写入最终报告正文。

用户最终确认后，仅把未经发起方重新解释的完整原始报告写入：

/Users/chengyanru/repos/personal/mediasense/docs/delegation/td-260831-1739-git-lg-cmux-filter/01-result-dotfiles.md

保持该文件现有 frontmatter，只写完整报告正文。引用本地文件、目录和产物时使用绝对路径。完成后只返回简短写回回执。综合验收和 delegation 关闭仍由发起方负责。
````
