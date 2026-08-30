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

For Codex, inspect its own MCP registration rather than asking MediaSense to edit
it. Re-register the server with the installed executable if the command path has
changed.

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
