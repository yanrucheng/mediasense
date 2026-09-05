---
name: mediasense
description: "Sets up, verifies, and enters MediaSense, then routes work to PreCheck, Plan, or Apply from the user's intent and exact retained state. Use when a user is installing or configuring MediaSense, starting without knowing a stage, continuing prior MediaSense work, or diagnosing why MediaSense is unavailable; not for replacing stage-specific judgment or Tool guarantees."
---

# MediaSense

Bring one Human-selected Honeycomb from unknown readiness to a verified
MediaSense integration, then route the user's work to the stage that owns it.
Keep product setup and cross-stage orientation here; keep PreCheck, Plan, and
Apply semantics in their independently loadable Skills.

## Establish readiness

This Skill set targets the MediaSense `0.7.x` CLI and its bundled Tool contracts.
If the compatible CLI and complete release-matched Skill set are present and all
seven exact Tool names below are already discoverable in the current session, do
not repeat setup. A `mediasense` command in `PATH`, installed Skill files, or a
configuration file on disk is not proof that the current Agent session has loaded
the Tool Host.

1. Establish the Honeycomb root independently of the Dataset. Prefer a path the
   Human or Agent client supplied explicitly. The current working directory may
   be proposed as a candidate, but before any write show its resolved absolute
   path and ask the Human to confirm it. Never derive it from a source-media or
   Dataset-workspace path. A MediaSense source checkout is not an implicit
   Honeycomb: packaged Skill sources inside it are release assets, not an
   installed copy. Do not install back into that checkout unless the Human
   explicitly selects it for operational MediaSense work.
2. Inspect the CLI without changing state: run `command -v mediasense`, then
   `mediasense --version` when present. If it is absent or not `0.7.x`, identify
   the exact trusted wheel or source checkout and executable destination,
   explain whether `uv tool install <trusted-source-or-wheel>` may use the
   network, and obtain Human authorization before installing or replacing the
   machine-wide CLI. If no trusted source is known, ask rather than choosing one.
3. Inspect the confirmed `<honeycomb>/.agents/skills/` directory. The complete
   release-matched set is `mediasense`, `mediasense-precheck`,
   `mediasense-plan`, and `mediasense-apply`. If it is incomplete, show the exact
   absolute target and ask before running
   `mediasense skills install --target <absolute-target>`. The command is
   idempotent for identical content and refuses a different existing Skill. If
   a complete older MediaSense release is present and the Human authorizes
   replacement, use
   `mediasense skills upgrade --target <absolute-target>`; it transactionally
   replaces only the four MediaSense Skills and preserves unrelated Skills.
   Never default to a user-wide Skill directory.
4. Inspect and parse `<honeycomb>/.codex/config.toml`. Explain that this is a
   project-local Codex connection only, and that Codex loads it only for a
   trusted project. Show the exact absolute file before requesting authorization
   to create it or minimally merge this table:

   ```toml
   [mcp_servers.mediasense]
   command = "mediasense"
   args = ["mcp"]
   ```

   Preserve all unrelated TOML content and other MCP servers. An identical table
   is already configured. If the same table has different content, the TOML is
   invalid, the root is unclear, the project is untrusted, or the target cannot
   be written, stop and report the exact condition; do not overwrite it or fall
   back to `~/.codex/config.toml`.
5. After any MCP configuration change, explain that the current Agent session
   normally cannot load it dynamically. Ask the Human to start a new session from
   the trusted Honeycomb. In that new session, verify discovery of exactly
   `mediasense.dataset.open`, `mediasense.precheck.run`,
   `mediasense.precheck.read`, `mediasense.plan.work`,
   `mediasense.apply.run`, and `mediasense.apply.read` before claiming setup is
   complete.

`mediasense mcp` is the CLI package's on-demand stdio server. The Agent client
starts it for the session and it exits with that connection; it is not a daemon
and owns no Dataset state or Tool meaning. Codex is the first fully certified
client. Other stdio clients are protocol-compatible only until their Skill,
configuration, approval, restart, and recovery behavior is separately accepted.

## Route to the owning stage

Route from the user's goal and exact public references. Do not infer progress
from private databases, caches, directory names, or the mere presence of files.

- Use `mediasense-precheck` when the user has a source path to prepare, needs to
  open a Dataset, has no Plan-ready Result, or must revise upstream evidence.
- Use `mediasense-plan` when the user has one exact Plan-ready `result_ref` and
  needs grouping, naming, inspection, revision, confirmation, or a Frozen Plan.
- Use `mediasense-apply` when the user has one exact Frozen Plan and wants to
  prepare, authorize, execute, recover, inspect, or rewind filesystem effects.
- If the requested continuation lacks the required exact reference, explain
  what is missing and use the owning stage's public read or status operation
  when available. Do not silently restart from PreCheck or reconstruct state.

Once routed, follow the selected stage Skill rather than reproducing its method
here. A stage handoff changes the active method, not the authority of its Result,
Frozen Plan, Receipt, Human confirmation, or Tool response.

## Boundaries

- Loading this Skill grants no authority to install software, edit Agent
  configuration, enable network providers, spend money, or change media.
- Keep executable installation, Honeycomb-local Skill installation, client MCP
  configuration, and Dataset state as independent locations and effects.
- Do not perform PreCheck interpretation, Plan decisions, or Apply filesystem
  execution in this entry Skill.
- Do not claim installation success until the current session exposes the exact
  Tool set. Do not claim stage completion without its authoritative artifact.
