## Context

MediaSense 0.2 already ships one `mediasense` executable, packaged Skills and contracts, and a conforming `mediasense mcp` stdio server. Its installed `0.2.0` Tool Host also predates the public/internal Dataset-reference normalization fix, so Tool discovery succeeds while the first real `dataset.open → precheck.run start` path fails. The remaining distribution defects are therefore both scope and release identity: user-level Codex registration makes every project appear MediaSense-aware, and the unchanged version cannot distinguish the corrected runtime.

The target is an ordinary local Honeycomb integration. A Honeycomb is the user-selected repository or working-directory root from which an Agent client discovers local instructions and configuration. It is not a MediaSense runtime entity and is never inferred from a Dataset path. Official OpenAI documentation confirms that Codex discovers repository Skills through `.agents/skills/`, accepts project-scoped MCP configuration in `.codex/config.toml`, gives project configuration precedence over user configuration, and loads project `.codex/` layers only for trusted projects:

- https://developers.openai.com/codex/skills/
- https://developers.openai.com/codex/mcp/
- https://developers.openai.com/codex/config-basic/

The archived `productize-mediasense-distribution` change is historical evidence for the executable, Dataset opener, Tool Host, and packaging work. This change replaces only its user-level client-integration guidance and does not edit the archive into a different historical decision.

## Goals / Non-Goals

### Goals

- Let a user install the CLI once while choosing exactly which Honeycombs load MediaSense Skills and MCP configuration.
- Make first use possible after a user performs the Agent client's standard local Skill installation action.
- Preserve explicit Human authority for executable installation and Honeycomb configuration changes.
- Keep Dataset state portable or machine-local according to Dataset policy, independently of Agent integration.
- Make absence, incompatibility, conflicts, trust rejection, write failure, restart requirements, discovery failure, and process termination observable.
- Prove Codex project-local visibility and ordinary stdio compatibility without claiming certification for untested clients.

### Non-Goals

- Add `mediasense agent`, an Agent-specific environment, launcher, daemon, network service, plugin platform, or hard-coded Agent directory.
- Derive a Honeycomb from a Dataset source or workspace, or store Agent configuration in a Dataset workspace.
- Add a Codex-specific configuration mutation command without evidence that safe standard-file editing is insufficient.
- Change the seven Tool business contracts, Dataset identity, or PreCheck/Plan/Apply authority.
- Preserve the obsolete default of user-wide Skill and MCP registration.

## Backward Compatibility Policy

| Attribute | Value |
|-----------|-------|
| Production status | Not in production; MediaSense 0.3 is a local pre-release |
| BC Level | None — Zero BC policy |

No production consumers require compatibility shims. The user-level installation guidance is replaced cleanly rather than retained behind aliases, dual configuration, or a new launcher. Existing user-owned files are migrated once through exact backup and targeted removal; Dataset state and public Tool contracts are unchanged.

## Decisions

### 1. Four independent homes carry four independent responsibilities

```text
machine executable path
└── mediasense CLI
    └── mediasense mcp (stdio entry point)

Human-selected Honeycomb
├── .agents/skills/mediasense-{precheck,plan,apply}/
└── .codex/config.toml
    └── [mcp_servers.mediasense]

independent Dataset workspace
└── Dataset-owned state and artifacts
```

The CLI owns installation diagnostics, Human control surfaces, and the executable entry point. Local Skills own reusable Agent guidance. The client configuration owns only how the current Honeycomb starts the Tool Host. The Dataset workspace owns domain state. None is an alias or discovery rule for another.

Alternative rejected: a MediaSense Agent home or launcher. It adds an entity without independent product authority and makes a normal MCP application responsible for starting the Agent client.

### 2. Responsibility and authority remain explicit

| Boundary | Responsibility and authority |
| --- | --- |
| Human | Selects the Honeycomb and trusted install source; authorizes global CLI installation, Honeycomb writes, external effects, and Apply effects. |
| Agent | Inspects current facts, explains exact targets/effects, requests missing authority, performs authorized setup, verifies discovery, and coordinates stage Tools. |
| Skill | Carries version-aware bootstrap and stage workflow knowledge; loading it grants no mutation or external authority. |
| CLI | Provides diagnostic and Human-oriented commands plus the `mcp` process entry point; it does not silently configure Agent clients. |
| MCP | Transports structured Tool discovery and calls between one client session and the CLI process; it owns no business semantics or Dataset state. |
| Tool | Owns each named business capability's validated inputs, effects, lifecycle, state transitions, failures, and evidence. |

The seven Tool names remain `mediasense.dataset.open`, `mediasense.precheck.run`, `mediasense.precheck.read`, `mediasense.plan.work`, `mediasense.geo.query`, `mediasense.apply.run`, and `mediasense.apply.read`.

### 3. First use begins with one already-loaded local Skill

The Agent client's ordinary Skill mechanism places at least `mediasense-precheck` under `<honeycomb>/.agents/skills/`; a Skill cannot load itself. Once loaded, PreCheck:

1. checks `command -v mediasense` and `mediasense --version` without mutation;
2. if the CLI is absent or incompatible, explains the exact source, executable destination, and possible network access, then waits for Human authorization before installation;
3. resolves an explicitly supplied Honeycomb, or presents the current directory as a candidate and obtains confirmation before any write;
4. inspects the exact `<honeycomb>/.agents/skills/` target and may use `mediasense skills install --target <exact-path>` after authorization to install the release-matched set without overwriting differences;
5. parses `<honeycomb>/.codex/config.toml`, reports the absolute target, and after authorization creates or safely merges the exact MediaSense table;
6. reports that a new Agent session is required; and
7. in that new session, proves success through discovery of all seven Tools before opening a Dataset.

Plan and Apply state only the compatible-current-Honeycomb prerequisite and route an unmet prerequisite back to PreCheck bootstrap instead of copying the whole procedure.

Alternative rejected: require users to memorize CLI installation and registration commands before the Skill can help. The only irreducible manual step is standard local Skill acquisition.

### 4. Local configuration edits fail closed

The target block is exactly:

```toml
[mcp_servers.mediasense]
command = "mediasense"
args = ["mcp"]
```

Before a write, the Agent reports the resolved Honeycomb root and full target path. Missing files may be created; parseable files are merged while retaining unrelated content. An identical MediaSense table is an idempotent success. A same-name table with different values, invalid TOML, untrusted project, non-writable target, or unclear Honeycomb root is a stop condition, not permission to overwrite, guess, or fall back to user configuration.

Alternative rejected: `codex mcp add mediasense -- mediasense mcp` as the default. In the currently certified Codex client it writes user-level configuration and therefore widens capability discovery beyond the selected Honeycomb.

### 5. The MCP Host is session-scoped transport

`mediasense mcp` remains part of the same installed CLI distribution. Codex launches it from project configuration as an stdio child process when a session needs it. Closing the client connection closes stdin and the server exits; installation creates no service definition, listener, scheduler, or background daemon. Durable work continuity belongs to Tool-owned Dataset state, not process lifetime.

Alternative rejected: a global daemon. It adds process management, network/authentication, and cross-project authority without a current requirement.

### 6. Configuration presence is not activation evidence

Project `.codex/config.toml` is ignored by Codex for untrusted projects, and a running session normally does not reload a newly written MCP entry. Success therefore requires a new process/session from the trusted Honeycomb and Tool discovery of the exact seven names. CLI presence, file presence, or process creation alone is insufficient.

The first complete certification target is Codex. Other clients may launch the standard stdio command and remain protocol-compatible, but their Skill discovery, configuration scope, approval UI, restart behavior, and full workflow are not certified without client-specific evidence.

### 7. The corrected runtime has a new release identity

This breaking integration ships as MediaSense `0.3.0`. The repository and
packaged Skills accept `0.3.x` and reject `0.2.x`, even when an older Host exposes
the same seven Tool names. Package metadata remains the single version source.
Installed-runtime acceptance resolves and invokes the exact global executable
path before entering any repository-managed environment, then proves
`dataset.open → precheck.run start` through that process.

Alternative rejected: reuse `0.2.0` or accept all `0.2.x`. That makes a known-bad
installed Host observationally indistinguishable from the corrected build and
invalidates version-based bootstrap checks.

### 8. Validation is layered by risk

This is a medium-to-high integration and configuration-safety change. Fast tests protect explicit target binding, idempotency, conflict refusal, repository/package parity, forbidden guidance, static project configuration, stdio handshake/call, and EOF exit. A separate local acceptance script uses fresh Codex processes to compare the selected Honeycomb with a temporary directory. Packaging acceptance builds both artifacts, installs the wheel into an isolated tool home, and proves installation does not create Agent configuration.

## Risks / Trade-offs

- [A user chooses the wrong Honeycomb] → show the absolute root and target paths and require confirmation before writing when the root was not explicit.
- [TOML merge damages unrelated configuration] → parse first, preserve all unrelated content, make an external backup for real user-state migration, and refuse a differing `mcp_servers.mediasense` table.
- [A current session retains stale user-level MCP state or an old child process] → disclose session caching, distinguish client-owned children from daemons, and use a fresh Codex process for acceptance.
- [A repository test shadows the installed executable with `.venv/bin`] → capture
  the absolute global executable before invoking repository test tooling and pass
  that path explicitly to the installed-runtime probe.
- [The CLI is outside PATH in the Agent environment] → distinguish command-not-found from server/protocol failures and report the expected command without guessing a path.
- [Project configuration exists but is ignored] → explain Codex trust gating and require Tool discovery as proof.
- [Other MCP clients differ] → claim protocol compatibility only; retain Codex as the sole certified client.

## Migration Plan

1. Keep the focused OpenSpec delta authoritative while main specs remain at their pre-change state; prove archive succeeds in an isolated copy.
2. Upgrade package and Skill compatibility identity to `0.3.0`, then update user guides, delegation follow-up, and conflict audit.
3. Add explicit installed-global-CLI, configuration-scope, Skill, stdio lifecycle, and documentation-regression tests; run the complete non-live and packaging gates.
4. Build and install the exact `0.3.0` wheel, replacing the old global `0.2.0` tool environment, then prove the real global `dataset.open → precheck.run start` path.
5. Archive the change so OpenSpec performs the one authoritative delta-to-main-spec synchronization; validate the resulting main specs and archive.
6. Preserve the repository-local `.codex/config.toml`, absent user-level MediaSense registration and Skills, and compare fresh Codex processes inside and outside the Honeycomb.

Rollback of the machine-state migration restores the timestamped user-config backup and, if desired, reinstalls the exact packaged Skills into an explicitly chosen target. The previous global `0.2.0` executable is not retained as a supported fallback because it fails the first-use path. No Dataset migration or media change occurs.

## Open Questions

None. Certification of additional MCP clients remains future evidence work rather than an unresolved design choice.
