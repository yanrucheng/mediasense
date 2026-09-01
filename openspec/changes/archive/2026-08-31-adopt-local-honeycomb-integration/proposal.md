## Why

The released integration guidance currently turns one local MediaSense installation into user-wide Codex configuration and Skills. MediaSense instead needs a lightweight, ordinary stdio MCP integration whose executable may be machine-wide while capability discovery remains explicit and local to the Human-selected Honeycomb.

## What Changes

- **BREAKING**: replace the default user-level Codex MCP and Skill installation guidance with Honeycomb-local `.codex/config.toml` and `.agents/skills/` guidance.
- Release the breaking integration and the corrected installed
  `dataset.open → precheck.run start` path as MediaSense `0.3.0`; `0.2.x` is not
  compatible with this Skill set.
- Define the independent responsibilities and lifecycles of the global `mediasense` CLI, local Skill copies, local MCP registration, and Dataset workspace.
- Make `mediasense-precheck` the bootstrap entry after standard Skill acquisition: inspect first, explain exact effects, request Human authorization, then install a compatible CLI or merge local configuration when needed.
- Require conflict-safe TOML handling, explicit Honeycomb selection, trusted-project disclosure, session restart, and post-restart Tool discovery before claiming the integration works.
- Keep `mediasense mcp` inside the CLI distribution as an on-demand stdio subprocess; add no Agent launcher, daemon, network service, plugin platform, or MediaSense-owned Agent home.
- Certify Codex first while describing other stdio MCP clients only as protocol-compatible until separately accepted.
- Correct active documentation and the prior delegation record without rewriting the archived `productize-mediasense-distribution` history.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `mediasense-distribution`: separate global executable installation from Honeycomb-local Skill and MCP integration.
- `tool-host`: define the CLI-bundled, session-scoped stdio lifecycle and local registration boundary.
- `dataset-workspace`: make Dataset placement independent from Honeycomb and client configuration.
- `precheck-agent-workflow`: add the first-use bootstrap and post-restart Tool-discovery gate.
- `plan-agent-workflow`: require a compatible Tool Host already loaded in the current Honeycomb.
- `apply-skill-workflow`: require the same local Tool Host prerequisite without duplicating bootstrap instructions.

## Impact

- OpenSpec distribution, Tool Host, Dataset, and stage-workflow requirements.
- Repository and packaged PreCheck, Plan, and Apply Skills.
- Root and task-oriented documentation, historical-status notes, documentation indexes, and a conflict audit.
- Distribution, explicit-target Skill installation, stdio MCP, project-config, process-lifecycle, and documentation-regression tests.
- An explicit-path installed-global-CLI acceptance probe that cannot resolve to
  the repository `.venv` by accident.
- One exact user-config backup and cleanup after product verification; no Dataset, media, provider, or billing effect.
