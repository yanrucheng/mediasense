# Verification

Verified on 2026-08-31 in the shared macOS workspace without committing,
merging, pushing, publishing, calling a live provider, moving real media, or
modifying the Hong Kong fixture.

## Product and regression evidence

- Focused version, Honeycomb, CLI, Skill, and MCP tests: `22 passed` in the
  review-blocker correction run; the earlier integration-only run passed 28.
- Full default non-live suite: `529 passed, 12 deselected`.
- Ruff lint: passed.
- OpenSpec pre-archive strict validation: `16 passed, 0 failed`.
- An isolated copy completed the real archive operation with five added and four
  modified requirements, then passed strict validation with 15 items. This
  replaced the prior reproduction in which archive aborted on duplicate ADDED
  requirements.
- The real repository archive then applied the same five additions and four
  modifications exactly once, moved the change to
  `2026-08-31-adopt-local-honeycomb-integration`, and passed post-archive strict
  validation with 15 items.
- Repository and packaged copies of all three Skills passed `quick_validate.py`.
- Repository/package Skill and contract parity test: passed.
- Documentation validation inspected 61 Markdown files with zero frontmatter,
  ID, folder-index, index-entry, or local-link errors under the repository's
  existing modular-document convention.
- Documentation regression search found no obsolete default command in active
  guidance. Exact legacy commands remain only in an explicitly superseded
  delegation section; the old MCP-add command also appears as a rejected design
  alternative and in regression-test data.
- `uv lock --check`, installer shell syntax, and `git diff --check`: passed.

## Package evidence

- `uv build --out-dir /private/tmp/mediasense-0.3.0-final.96ZANF` built
  `mediasense-0.3.0.tar.gz` and
  `mediasense-0.3.0-py3-none-any.whl`.
- The wheel passed the offline isolated Python 3.11 distribution smoke. The
  smoke proved that CLI installation creates no user-level Codex configuration
  or Skill directory, installed all Skills only below the explicit local target,
  kept that target independent of Dataset state, initialized the real stdio MCP
  child, discovered seven Tools, and completed
  `dataset.open -> precheck.run start`.
- Before replacement, the explicit installed-global-CLI probe rejected
  `/Users/chengyanru/.local/bin/mediasense` because it reported `0.2.0`; it did
  not resolve to the repository `.venv`.
- The verified local wheel then replaced the uv tool environment offline. The
  same absolute executable now reports `0.3.0`, its MCP server reports `0.3.0`,
  discovers seven Tools, and returns a `precheck-run:*` from the real
  `dataset.open -> precheck.run start` path.
- The installed environment contains
  `mediasense-0.3.0.dist-info`; uv reports only MediaSense `0.3.0`, so the prior
  global `0.2.0` installation is no longer present as the active tool.

## Machine-state migration

- The exact project registration is
  `/Users/chengyanru/repos/personal/mediasense/.codex/config.toml`.
- The original user configuration was copied without overwrite to
  `/Users/chengyanru/.codex/config.toml.mediasense-backup-20260831-125617` with
  mode `0600`.
- A semantic comparison and textual diff proved that only
  `[mcp_servers.mediasense]` was removed from the user configuration;
  `mcp_servers.cua_repl` and every other parsed value remain.
- Only the three exact user Skill directories `mediasense-precheck`,
  `mediasense-plan`, and `mediasense-apply` were removed. Repository-local Skills
  remain present and pass parity validation.

## Fresh-process scope evidence

- `codex mcp list --json` from
  `/Users/chengyanru/repos/personal/mediasense` returned an enabled `mediasense`
  entry with command `mediasense` and arguments `["mcp"]`.
- The same command from
  `/private/tmp/mediasense-no-project-config.RoCXdc` returned only the unrelated
  user-level servers and no MediaSense entry.
- A project-config-driven stdio subprocess completed initialize, exact seven-Tool
  discovery, and a non-destructive Dataset Open call. Closing stdin/session made
  the process exit successfully.
- The stdio subprocess created by the acceptance probe exited with its session.
  Older Codex sessions may still own their previously launched `mediasense mcp`
  children until those sessions close; those client-owned children are not a
  global daemon.

The Agent session performing this change began before the user-level registration
was removed and may retain its startup-time MCP view. A newly entered trusted
repository session is the authoritative post-change experience.

## Acceptance limits

- Codex is the only fully exercised Agent client. Other stdio MCP clients remain
  protocol-compatible but not certified for Skill discovery, project scope,
  approval, restart, display, or recovery behavior.
- No physical removable-volume run, network filesystem, live model or map
  provider, paid API, fresh Hong Kong replay, or real media move was used.
- The prior distribution delegation remains active and is not accepted or closed
  by this evidence.
