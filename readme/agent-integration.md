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

## Setup and readiness

Follow the single [installation and upgrade runbook](installation.md) for first
use, upgrades, project Skill management, MCP registration, and readiness evidence.
The `mediasense` entry Skill carries the same procedure as an offline release
snapshot. This guide explains the integration model; it does not maintain another
installation sequence or compatible-version declaration.

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
