# Agent integration

MediaSense uses the ordinary local integration points of an Agent client. It does
not create or launch a dedicated Agent environment.

```text
machine executable path
└── mediasense
    └── mediasense mcp

user-selected Honeycomb
├── .agents/skills/mediasense/
├── .agents/skills/mediasense-precheck/
├── .agents/skills/mediasense-plan/
├── .agents/skills/mediasense-apply/
└── .codex/config.toml

independent location
└── Dataset workspace
```

The CLI may be installed once for the machine. Skill discovery and MCP
registration are local to each Honeycomb that should expose MediaSense. Dataset
state follows the Dataset policy and may live beside an external volume or in the
platform application-data directory; it is never an Agent configuration root.

## What each surface owns

- A MediaSense **Tool** is a concrete business capability:
  `mediasense.dataset.open`, `mediasense.precheck.run`,
  `mediasense.precheck.read`, `mediasense.plan.work`, `mediasense.geo.query`,
  `mediasense.apply.run`, or `mediasense.apply.read`.
- The **CLI** is the installed local executable. It provides diagnostics, Human
  control surfaces, and runtime entry points.
- **`mediasense mcp`** is the CLI package's stdio server. MCP transports Tool
  discovery and calls; it does not own Tool meaning, authorization, or Dataset
  state.
- A **Skill** tells an Agent when and how to use Tools, when to ask the Human, and
  how to preserve stage boundaries. Loading a Skill grants no mutation authority.
- **`.codex/config.toml`** tells Codex in this Honeycomb how to start the stdio
  child process. The process exits with the client connection and is not a daemon.

A globally available `mediasense` command therefore does not give every Agent
MediaSense capability. Automatic discovery requires the local product entry and
stage Skills plus the MCP configuration that apply to that Agent session.

## New-user bootstrap

The first step uses the Agent client's standard mechanism to place the
`mediasense` product entry Skill under the selected Honeycomb:

```text
<honeycomb>/.agents/skills/
```

The MediaSense source checkout is not an implicit Honeycomb. Its packaged Skill
sources under `src/mediasense/_resources/skills/` are release assets, not an
activated local installation. Install into the separate WorkTree where the Agent
will actually operate MediaSense, unless the Human explicitly chooses the source
checkout itself for that operational role.

Start the Agent from the Honeycomb. Once `mediasense` is loaded, it owns the
remaining setup guidance and installs the complete release-matched Skill set:

1. Confirm the Honeycomb root. The current directory is only a candidate when the
   Human has not explicitly selected a root; no write occurs until its absolute
   path is shown and confirmed. Dataset paths are never used to infer it.
2. Check `command -v mediasense` and `mediasense --version`. The current Skill set
   requires `0.8.x`; an installed `0.3.x` through `0.7.x` host is incompatible and must not be
   accepted merely because it exposes the expected Tool names.
3. If the CLI is absent or incompatible, explain the exact trusted source,
   executable destination, and possible network access. Install only after Human
   authorization. Installation does not modify Agent configuration.
4. If the release-matched Skill set is incomplete, show the exact target and,
   after authorization, run:

   ```bash
   mediasense skills install --target <absolute-honeycomb>/.agents/skills
   ```

   Identical content is idempotent. Different existing content is a conflict and
   is not overwritten.
   To replace a known older release as one matched set, run:

   ```bash
   mediasense skills upgrade --target <absolute-honeycomb>/.agents/skills
   ```

   Upgrade changes only the four MediaSense Skill directories and preserves
   unrelated Skills.
5. Inspect and parse `<absolute-honeycomb>/.codex/config.toml`. Show that complete
   target path and request authorization before creating the file or minimally
   merging:

   ```toml
   [mcp_servers.mediasense]
   command = "mediasense"
   args = ["mcp"]
   ```

   Preserve every unrelated TOML value and other MCP server. If a MediaSense
   table already has different content, or the file is invalid or not writable,
   report the conflict and stop. Do not silently replace the file or fall back to
   user-level configuration.
6. Start a new Agent session from the trusted Honeycomb. Codex only loads project
   `.codex/` configuration for trusted projects, and an already-running session
   normally does not acquire a newly added MCP server.
7. Discover Tools in the new session and verify all seven exact names listed
   above. File presence or CLI availability alone is not acceptance evidence.
8. Only then route the request: begin PreCheck for a source that needs preparation,
   enter Plan for an exact Plan-ready `result_ref`, or enter Apply for an exact
   Frozen Plan.

The intended first request can remain simple:

```text
Prepare /Volumes/PhotoDisk/Photos with MediaSense. Keep the source read-only and
before any Provider request show me the exact pending-coordinate disclosure and
wait for my authorization.
```

## Codex scope and trust

Codex discovers local Skills from `.agents/skills/` along the working-directory
to repository-root chain. It accepts project-scoped MCP servers from
`.codex/config.toml`, gives project configuration precedence over user
configuration, and skips project `.codex/` layers for untrusted projects. See the
official documentation:

- [Codex Skills](https://developers.openai.com/codex/skills/)
- [Codex MCP](https://developers.openai.com/codex/mcp/)
- [Codex configuration](https://developers.openai.com/codex/config-basic/)

The native `codex mcp add` command currently targets user configuration, so it is
not the default MediaSense setup route. User-wide Skill installation is likewise
an explicit advanced choice, never the first-use default.

When `mediasense.precheck.run` pauses for an external effect, its MCP `resume`
request carries the intended decision but no caller-authored authority object.
The MediaSense MCP Host uses the connected session's elicitation channel to show
the exact pending disclosure and constructs the confirmation context only after
the Human accepts. A client without elicitation support leaves the Run paused and
causes no Provider request.

## Other MCP clients

The Tool Host uses standard local stdio MCP and is not intentionally coupled to
Codex. Other clients may launch `mediasense mcp` through their own local
configuration mechanisms.

Only Codex currently has complete MediaSense certification. Other clients are
protocol-compatible, but their Skill discovery, configuration scope, approval,
display, restart, and recovery behavior is not certified until exercised in a
client-specific acceptance matrix.

## Trust boundary

The initial Host is local and single-user. The operating-system account and the
client-launched stdio process form the transport trust boundary. Tool business
requests remain distinct from transport-only confirmation and authorization
context. A future network transport requires a separate authentication and threat
model; changing transport must not change Tool meaning.
