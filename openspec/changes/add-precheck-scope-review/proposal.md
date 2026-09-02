## Why

Selecting a source directory currently lets every discovered media-shaped object enter PreCheck's expensive producer pipeline without first exposing the effective processing scope. Dot entries, caches, thumbnails, indexes, historical outputs, backups, and other derived trees can therefore multiply local work even when they are not part of the user's intended collection.

PreCheck needs a bounded factual inventory before expensive work so an Agent can interpret the tree and help the Human choose the intended scope. The Tool must report and enforce that choice without embedding semantic guesses about which directory names are legitimate media.

## What Changes

- **BREAKING**: make a newly started PreCheck Run finish source inventory and wait for an exact scope selection before admitting metadata extraction, full-content verification, decoding, rendition, video, embedding, sensitivity, compression, or online work, unless an unchanged prior selection is safely reusable.
- Add a compact, deterministic, expandable source tree to Run status. Each reported node contains factual counts, byte totals, file-kind and size distributions, representative relative paths, omitted-child counts, and discovery limitations; it contains no cache/output/backup verdict or confidence score.
- Accept an exact include/exclude selection bound to the inventory revision. Preserve excluded discoveries in Source Item accounting and refuse a stale selection when the relevant source tree changes.
- Keep interpretation in the Agent workflow: the Skill guides the Agent to explain structures such as media-bearing cache trees or legal hidden media, distinguish Tool facts from Agent judgment, and obtain Human direction where authority is not already delegated.
- Define deterministic unattended behavior: without a valid reusable or caller-supplied selection, the Run waits without admitting expensive work and exposes a machine-readable reason.
- Update public Tool contracts, reviewable mocks, packaged Skill copies, and focused synthetic tests. Do not add a Dataset Open responsibility, a Preflight Tool, or directory-name exclusion lists.

## Capabilities

### New Capabilities

- `precheck-scope-review`: Factual bounded source inventory, exact scope selection, admission gating, auditability, reuse, and honest invalidation inside one PreCheck Working Run.

### Modified Capabilities

- `precheck-run-orchestration`: Require scope selection before the existing producer chain can admit expensive work and expose the scope-review wait through the existing Run lifecycle.
- `precheck-agent-workflow`: Require the Agent to interpret Tool-supplied statistics and tree structure without presenting its judgments as Tool facts or silently inventing scope authority.

## Impact

- `mediasense.precheck.run` request/response schema, lifecycle mock, runtime coordinator, Working Run persistence, Result accounting basis, and contract tests.
- Discovery aggregation and a bounded inventory-tree projection; no new public Tool, stage, service, registry, provider adapter, or source-side marker.
- Canonical and packaged `mediasense-precheck` Skill copies and their workflow tests.
- Small synthetic acceptance fixtures for dotfiles, hidden media, media-bearing cache trees, nested historical output, stale selection, and unattended operation.
- MediaSense is not in production, so Zero Backward Compatibility applies: the current contract changes directly without a version router, dual write, deprecation shim, or compatibility adapter.
- No Hong Kong fixture mutation or replay, remote call, billable work, or source-media write.
