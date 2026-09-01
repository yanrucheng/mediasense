---
id: "td-260830-2227-mediasense-distribution"
title: "MediaSense Installation, Tool Hosting, and Versioning"
type: delegation
status: active
created: 2026-08-30
updated: 2026-08-31
timezone: "Asia/Shanghai"
parent: "index-delegation"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
superseded-by: ""
---

# MediaSense Installation, Tool Hosting, and Versioning

## Shared purpose and intended use

Turn the completed MediaSense stage engines, public Tool contracts, and Agent Skills into a professional local product that a user can install, diagnose, upgrade, and invoke without writing a bespoke Python host. The result supports one closing judgment: whether MediaSense has a coherent supported installation and release surface suitable for normal continued use.

## Scope

- Recipient: `team:mediasense` through its local workspace route.
- Engagement: user-interactive in a dedicated cmux workspace.
- The recipient owns product discussion, design, OpenSpec planning, implementation, clean-install verification, documentation, and a reviewable handoff.
- Required product areas are an installable executable Tool experience, a complete installation/bootstrap path, and an authoritative versioning/release system.
- The work may define the minimum local Tool Host needed to expose the existing public Tools, but must not redesign stage semantics merely for packaging convenience.

## Confirmed starting facts

- MediaSense is currently a Python 3.11+ source package at version `0.1.0` with `uv.lock`, but `pyproject.toml` has no executable entry point or explicit build-system declaration.
- The repository currently has no documented end-user installation flow, unified composition root, MCP/stdio or HTTP Tool Host, Docker packaging, or `mediasense` command.
- The six current public Tool identities are PreCheck Run/Read, Plan Work, Geo Query, and Apply Run/Read. Their business contracts remain authoritative and independent from the transport chosen for installation.
- Three repository-local Skills guide PreCheck, Plan, and Apply. Their installation and discovery need to be considered as part of the usable product experience.
- Other Agents are concurrently closing cross-stage contract findings. This work must preserve their changes and coordinate its implementation baseline instead of overwriting or silently redefining them.

## User-interactive decisions and checkpoints

- First explain the viable product shapes in plain language and recommend one: local CLI/library only, local MCP/stdio Tool Host, or another justified minimal host.
- Discuss what “installed and usable” means for the owner: supported platforms, invocation from an Agent client, initial workspace/configuration, dependency checks, upgrades, and uninstall/recovery.
- Discuss the version model: application/package version, public Tool-contract compatibility, persistent-store migrations, release tags/changelog, prerelease policy, and compatibility promises. Application version changes must not become broad computation invalidation keys.
- Use professional judgment for ordinary engineering choices. Stop only for decisions that materially change product usage, release/compatibility promises, installation trust, distribution channels, or external effects.
- Before implementation, agree with the user on the target experience and safe workspace/branch strategy, then create a focused OpenSpec change and delivery backlog.
- Before final writeback, present the complete implementation and clean-install evidence to the user and wait for explicit acceptance.

## Closing and acceptance criteria

- A new user has one documented, repeatable installation route and can invoke MediaSense as a real tool without custom Python assembly.
- The installed runtime exposes the existing Tool contracts through a clearly owned local host or equally usable boundary, with explicit configuration, storage, authorization, and failure behavior.
- Installation is safe, idempotent where appropriate, diagnoses required external components, and does not claim unsupported platforms.
- One authoritative version source drives package metadata and `--version`; release, compatibility, migration, upgrade, and rollback behavior are documented and tested.
- Versioning does not leak into PreCheck dependency validity or turn every application upgrade into a Dataset-wide rebuild.
- Skills and Tool Host discovery are usable from the intended Agent environment.
- A clean-environment smoke test covers install, init/configuration, version/doctor, Tool discovery, a non-destructive invocation, upgrade compatibility where applicable, and uninstall or cleanup guidance.
- Existing public stage contracts remain stable unless the user separately accepts an evidenced change.
- No real media mutation, online map request, remote model, paid API, release publication, push, or merge occurs without separate authority.

## Request and result inventory

| Request | Recipient | Result | Status |
| --- | --- | --- | --- |
| [01-request-mediasense](01-request-mediasense.md) | `team:mediasense` | [01-result-mediasense](01-result-mediasense.md) | interactive discussion and delivery opened |

## Material handoff evidence

- 2026-08-30 22:27 Asia/Shanghai — The user requested a dedicated MediaSense Agent to own productized installation, normal Tool invocation, and a complete versioning system, with direct interactive discussion before implementation decisions are frozen.
- 2026-08-30 22:31 Asia/Shanghai — A first transport attempt was rejected because shell interpretation altered the prompt before submission; its temporary workspace was stopped and closed rather than treated as a valid handoff.
- 2026-08-30 22:32 Asia/Shanghai — Created non-focusing workspace `D811C805-1A60-4412-887D-021BC0BF5EC0` with terminal surface `CBFDDBF0-213B-4686-9A03-05D88D57FF06` in the invoking window; direct entry: `cmux://workspace/D811C805-1A60-4412-887D-021BC0BF5EC0/surface/CBFDDBF0-213B-4686-9A03-05D88D57FF06`.
- 2026-08-30 22:32 Asia/Shanghai — Verified the MediaSense cwd, ordinary interactive Codex UI, unchanged original focus, complete initial task delivery, and the recipient's read-only opening before product discussion.
- 2026-08-31 12:37 Asia/Shanghai — A local Honeycomb follow-up found that the recorded user-level Skill and MCP examples had the wrong scope. `2026-08-31-adopt-local-honeycomb-integration` now records the replacement model; revalidation and explicit user acceptance remain pending, so this delegation stays active.
- 2026-08-31 14:59 Asia/Shanghai — Corrected the three review blockers: released and installed `0.3.0`, proved the exact global executable can complete Dataset Open → PreCheck Start, and archived the Honeycomb OpenSpec change through one successful delta-to-main-spec synchronization. This is new evidence for review, not delegation closure.
