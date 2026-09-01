---
id: "eval-260831-1237-local-honeycomb-doc-conflicts"
title: "Local Honeycomb Documentation Conflict Audit"
type: eval
status: active
created: 2026-08-31
updated: 2026-08-31
timezone: "Asia/Shanghai"
parent: "index-eval"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "td-260830-2227-mediasense-distribution"
superseded-by: ""
tags: ["distribution", "honeycomb", "documentation-audit"]
---

# Local Honeycomb Documentation Conflict Audit

## Scope and method

The audit searched `README.md`, `CHANGELOG.md`, `readme/`, all repository and
packaged MediaSense Skills, `docs/design/`, `docs/spec/`, `docs/eval/`,
`docs/delegation/`, `openspec/specs/`, `openspec/changes/`, `scripts/`, and
`tests/`. Search terms covered the former user-level Codex Skill target, the
native Codex MCP-add command, `mediasense skills install`, global scope,
Agent-workspace or Agent-home language, `mediasense agent`, `.codex/config.toml`,
and `mediasense mcp`.

The review distinguished operational guidance from negative requirements, tests,
ordinary uses of “global” in unrelated Apply risk semantics, and historical
records. This audit establishes documentation consistency only; it does not close
the distribution delegation or claim whole-product acceptance.

## Authoritative model

| Concern | Current authority |
| --- | --- |
| Executable | The `mediasense` CLI may be installed machine-wide and does not configure Agent clients. |
| Tool Host | `mediasense mcp` is the same package's session-scoped stdio child process, not a daemon or separate service. |
| Skills | The `mediasense` product entry plus three stage Skills install under the Human-selected Honeycomb's `.agents/skills/`; the target is explicit and independent of Dataset paths. |
| Codex MCP | The selected trusted Honeycomb owns `.codex/config.toml`; the exact table launches `mediasense mcp`. |
| Dataset | The Dataset workspace owns Dataset state and may live anywhere allowed by Dataset policy. |
| Acceptance | A new Agent session must discover all seven Tools; command or file presence alone is insufficient. |

## Conflict disposition

| Previous or risky statement | Disposition | Current location |
| --- | --- | --- |
| Default installation into the user Codex Skill directory | Removed from active setup guidance; retained only in the explicitly superseded delegation result and negative no-write requirements/tests. | `readme/agent-integration.md`; `docs/delegation/td-260830-2227-mediasense-distribution/01-result-mediasense.md` |
| Default native Codex MCP-add command | Removed from active setup guidance because the current command writes user configuration; retained only as a rejected alternative or clearly labeled history. | `readme/agent-integration.md`; `openspec/changes/archive/2026-08-31-adopt-local-honeycomb-integration/design.md` |
| CLI presence implies Agent capability | Replaced with local Skills plus local MCP registration and post-restart seven-Tool discovery. | `README.md`; the MediaSense entry and three stage Skills; active distribution and Tool Host specs |
| Dataset path implies Agent workspace | Rejected explicitly; Honeycomb and Dataset selection have independent authorities and lifecycles. | `readme/installation.md`; active Dataset workspace spec |
| MCP is a separately installed or persistent service | Replaced with the CLI-bundled, client-launched stdio lifecycle and EOF/session-close exit evidence. | `readme/agent-integration.md`; active Tool Host spec |
| A new user must know that PreCheck owns installation | Replaced with the `mediasense` product entry Skill; all three stage Skills now route unavailable-Host recovery to that entry. | `mediasense/SKILL.md`; the three stage Skills |
| Archived distribution change appears current | Its archive README now carries a prominent supersession notice without rewriting the historical proposal, design, tasks, or verification. | `openspec/changes/archive/2026-08-30-productize-mediasense-distribution/README.md` |
| Delegation result implies final acceptance | Existing Dataset-ID correction remains, and a second explicit Honeycomb follow-up marks old commands historical and renewed acceptance pending. | `docs/delegation/td-260830-2227-mediasense-distribution/` |

## Residual intentional matches

- The superseded delegation result retains the two old commands as historical
  evidence under a warning. Removing them would falsify the record.
- The new design names the old MCP-add command only as a rejected default.
- Active specs and tests name user-level paths only to assert that CLI
  installation must not write them.
- Apply runtime uses “global risk” as an execution-safety classification; it is
  unrelated to installation scope.
- `mediasense mcp`, `.codex/config.toml`, and explicit
  `mediasense skills install --target <absolute-honeycomb>/.agents/skills` remain
  valid current terms when their local scope and lifecycle are stated.

## Result

No active installation guide or MediaSense Skill recommends user-level Skill
installation or user-level MCP registration as the default. Current guidance
consistently requires an explicit Honeycomb, safe non-overwriting local writes,
Codex project trust, a new session after configuration changes, and Tool discovery
as the success criterion. Historical exceptions are visibly marked and overall
delegation acceptance remains open.
