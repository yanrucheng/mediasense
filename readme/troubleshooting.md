# Troubleshooting and recovery

Start with:

```bash
mediasense doctor
```

The command does not install dependencies, contact providers, or alter a Dataset.
Warnings identify optional capabilities; errors identify prerequisites required by
the installed runtime.

## A Dataset does not open

Inspect the exact workspace reported by the failed command:

```bash
mediasense dataset inspect /path/to/workspace
```

Common outcomes:

- `manifest_invalid` or `manifest_missing`: the selected directory is not a
  trustworthy MediaSense Dataset. Keep it unchanged and restore its manifest from
  backup or choose a different explicit path.
- `manifest_newer` or `store_newer`: install a MediaSense release that supports the
  reported version. Do not retry with an older executable.
- `manifest_unsupported` or `store_unsupported`: no migration from that version is
  implemented. Keep the workspace and use a compatible release; do not edit SQLite
  metadata manually.
- `source_mismatch`: the workspace belongs to another source. Reconnect the expected
  device or perform a separately reviewed source-rebind workflow.
- `workspace_nested_in_source`: choose a workspace outside the declared source
  root. For a whole-volume source, use an explicit workspace or the local fallback.
- `workspace_unsafe`: the destination did not demonstrate required write, atomic
  replacement, or SQLite-locking behavior. Use a supported filesystem or an
  explicit local workspace.

MediaSense does not silently skip a broken higher-priority portable workspace and
create a new local Dataset, because that would make completed PreCheck work appear
to have disappeared.

## MCP client cannot start MediaSense

First verify the installed executable directly:

```bash
mediasense --version
mediasense doctor
mediasense tools list
```

Then run `mediasense mcp` from a terminal. It intentionally waits for MCP messages
and writes protocol frames only to stdout. Stop it with Ctrl-C after confirming it
starts without an immediate error.

For Codex, inspect the selected Honeycomb's exact `.codex/config.toml`. The
MediaSense registration must be:

```toml
[mcp_servers.mediasense]
command = "mediasense"
args = ["mcp"]
```

Check these cases distinctly:

- if `mediasense` is not in the Agent process's `PATH`, fix or reinstall the CLI
  only after identifying the trusted source and destination;
- if the project is untrusted, Codex skips its `.codex/` layer, so trust the
  intended project through the client's normal trust flow before retrying;
- if the same table exists with different values, treat it as a conflict and do
  not overwrite it;
- if the table was added during the current session, start a new Agent session
  from that Honeycomb;
- in the new session, verify all seven MediaSense Tools through discovery rather
  than treating file presence as success.

From a directory with no applicable local MediaSense configuration and no
explicit user-wide advanced setup, Codex should not list MediaSense. The stdio
server exits when the client connection closes; if a MediaSense MCP process
persists, capture its command and parent process because that is not the intended
lifecycle.

## Optional media capability is unavailable

Install missing system tools through a trusted package manager, then rerun
`mediasense doctor`. MediaSense never installs them automatically. Existing
Dataset state remains valid; resume the affected durable Run after the missing
prerequisite is available.

## Uninstall or rollback

Removing the executable does not remove Dataset workspaces. Preserve the complete
`.mediasense/datasets/` tree when moving or backing up an external Dataset. Before
deleting any workspace, use `mediasense dataset inspect` and retain any Result,
Frozen Plan, Receipt, or recovery record still needed.
