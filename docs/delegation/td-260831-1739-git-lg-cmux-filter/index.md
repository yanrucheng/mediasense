---
id: "td-260831-1739-git-lg-cmux-filter"
title: "Filter cmux Recovery Refs from git lg"
type: delegation
status: active
created: 2026-08-31
updated: 2026-08-31
timezone: "Asia/Shanghai"
parent: "index-delegation"
depends-on: []
superseded-by: ""
---

# Filter cmux Recovery Refs from git lg

## Shared purpose and intended use

Preserve the user's existing dense `git lg` presentation while preventing cmux
last-turn recovery snapshots from dominating its default graph. The result
supports one closing judgment: whether DotFiles has changed the authoritative
Git alias source and safely converged the current HOME projection without
altering unrelated aliases, refs, or repository history.

## Scope

- Recipient: `team:dotfiles` through its local workspace route.
- Engagement: user-interactive in a dedicated workline.
- The recipient may inspect DotFiles authority and, after user confirmation,
  modify the canonical Git alias source and any current-HOME projection that
  DotFiles' own contract authorizes.
- MediaSense product files outside this package, Git refs, commit history,
  stash data, and unrelated aliases are outside the recipient's write scope.

## Confirmed starting facts

- `team:dotfiles` owns the stable, non-secret cross-device HOME configuration
  baseline; its workspace route is
  `/Users/chengyanru/repos/personal/dotfiles` with direct-write return.
- The effective `alias.lg` delegates to `git lg3`.
- The effective `alias.lg3` retains the user's desired dense formatting and
  currently includes `--all`.
- `--all` makes `git lg` traverse `refs/cmux/last-turn/*`, whose stash-shaped
  checkpoint commits appear as repeated merge-like graph branches.
- The user selected the surgical behavior: replace only `--all` in the
  authoritative `lg3` definition with
  `--exclude='refs/cmux/last-turn/*' --all` and preserve the rest.

## Unresolved questions

- Which DotFiles-owned file is the canonical source for the effective Git
  alias, and what supported convergence mechanism updates the current HOME?
- Does DotFiles authorize updating the current HOME projection in the same
  operation, or must that effect be handed back separately?

## Closing and acceptance criteria

- DotFiles identifies and changes the authoritative source rather than treating
  the current `~/.gitconfig` projection as independent authority.
- The accepted edit changes only the selected ref scope in `alias.lg3`; the
  dense format, color, date, author, decoration, graph, `alias.lg` delegation,
  `lg1`, and `lg2` remain unchanged.
- The current HOME is converged only through a DotFiles-authorized mechanism
  and only after the user confirms the visible plan and effects.
- Effective `git lg` omits cmux last-turn checkpoint commits, while an explicit
  `git log --all` can still traverse them.
- No cmux ref, stash, commit history, or unrelated HOME setting is deleted or
  rewritten.
- The raw result records exact files, commands, verification evidence, and any
  remaining handback; final writeback occurs only after user confirmation.

## Request and result inventory

| Request | Recipient | Result | Status |
| --- | --- | --- | --- |
| [01-request-dotfiles](01-request-dotfiles.md) | `team:dotfiles` | [01-result-dotfiles](01-result-dotfiles.md) | user-interactive workline ready |

## Material handoff evidence

- 2026-08-31 17:39 Asia/Shanghai — The user confirmed the surgical cmux-ref
  filtering outcome and corrected ownership from a direct HOME edit to
  `team:dotfiles`.
- 2026-08-31 17:39 Asia/Shanghai — The user explicitly required interactive
  execution before any DotFiles or HOME mutation.
- 2026-08-31 17:39 Asia/Shanghai — A dedicated non-focusing cmux workline was
  created in window `97981626-4292-4E2F-B064-6303ACB0A5CF` as workspace
  `F4253AEE-3FF3-4EFB-951F-5430F88972BC` (`workspace:41`), with terminal
  surface `6097A894-16A5-4723-B835-028F11EBEE2F` (`surface:146`).
- 2026-08-31 17:39 Asia/Shanghai — The complete payload was delivered as the
  initial task to a normal interactive Codex session in the DotFiles workspace;
  the recipient restated the authority and confirmation boundary.
- 2026-08-31 17:39 Asia/Shanghai — After one transient transport reconnect, a
  bounded readback confirmed the same session actively inspecting DotFiles'
  canonical `dot_gitconfig` while preserving unrelated in-progress work.
