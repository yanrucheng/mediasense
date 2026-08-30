# Agent integration

MediaSense exposes a local Model Context Protocol server over stdio:

```bash
mediasense mcp
```

The server is started on demand by an MCP client. It does not listen on a network
port or remain running as a daemon.

Outside MCP, inspect the installed Tool catalog and one exact contract with:

```bash
mediasense tools list
mediasense tools show mediasense.precheck.run --json
```

## Codex

Register the installed executable through Codex's native MCP command:

```bash
codex mcp add mediasense -- mediasense mcp
```

Codex owns this registration in its configuration. MediaSense does not edit
`~/.codex/config.toml` itself. Confirm the registration with the Codex MCP listing
command documented by the installed Codex version. See the
[official Codex MCP documentation](https://developers.openai.com/codex/mcp/).

Install the three packaged MediaSense Skills explicitly into a chosen Codex Skill
root:

```bash
mediasense skills install --target ~/.codex/skills
```

The command is idempotent when an installed Skill is byte-identical and refuses to
overwrite a different existing Skill. To inspect the packaged sources without
copying them, run:

```bash
mediasense skills path
```

After registration, the intended conversation can begin with only a source path:

```text
Prepare /Volumes/PhotoDisk/Photos with MediaSense. Keep the source read-only and
do not use network providers.
```

The Agent first calls `mediasense.dataset.open`, reports the selected portable or
local workspace, and hands the returned exact `dataset_ref` to PreCheck.

## Other MCP clients

The Tool Host uses standard local stdio MCP and is not intentionally coupled to
Codex. Claude Desktop, Claude Code, VS Code, Cursor, and other stdio MCP clients can
launch the same `mediasense mcp` command using their own configuration mechanisms.

The initial product certification covers the complete Skill-guided workflow on
Codex. Other clients are protocol-compatible, but their client-specific Skill,
approval, display, and recovery behavior is not claimed as certified until it has
its own acceptance run.

## Trust boundary

The initial Host is local and single-user. The operating-system account and the
client-launched stdio process form the transport trust boundary. Tool business
requests remain distinct from transport-only confirmation and authorization
context. A future network transport requires a separate authentication and threat
model; changing the transport must not change Tool meaning.
