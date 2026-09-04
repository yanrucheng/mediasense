# MediaSense

MediaSense is an agent-native system for organizing large personal media collections without requiring an agent to inspect every image or exposing source files to premature, opaque automation.

The normal Agent journey starts by placing the `mediasense` product entry Skill
in a chosen local Honeycomb's `.agents/skills/` directory. That entry checks and,
with explicit Human authorization, helps install the machine-wide `mediasense`
CLI, the complete release-matched Skill set, and that Honeycomb's project-level
`.codex/config.toml` MCP connection. Installing the CLI alone changes no Agent
configuration. MediaSense
keeps expensive Dataset work beside media on an eligible external volume by
default and falls back to the platform-local application-data directory when no
portable workspace exists. The Honeycomb and Dataset workspace are independent.
See
[Installation and first use](readme/installation.md) and
[Agent integration](readme/agent-integration.md) for the complete flow; see
[Troubleshooting and recovery](readme/troubleshooting.md) when opening or
connecting fails.

The product exposes one user-facing entry Skill, `mediasense`, which owns setup,
readiness verification, and routing. It delegates business work to three stage
Skills:

- `mediasense-precheck` prepares a large media collection with source-read-only, local-first, resumable computation; external evidence calls are disabled by default and require a frozen-scope confirmation.
- `mediasense-plan` lets an agent and user iteratively turn one immutable Result plus explicitly authorized Plan-local observations into a complete, reviewable organization plan.
- `mediasense-apply` validates and safely applies a frozen plan without making new semantic decisions.

The three durable handoff roles are the precheck result, the frozen organization plan, and the apply receipt. PreCheck, Plan, and Apply now have active contracts and packaged user-facing Skills for the first end-to-end `move_originals` path. The Skills guide Human/Agent interaction while Tools remain authoritative for PreCheck work and Results, Plan validation and freezing, and deterministic Apply effects and Receipts. PreCheck may perform optional coordinate-only reverse geocoding over one frozen post-compression batch under Run-scoped authorization; Plan may separately use the stage-neutral `mediasense.geo.query` Tool for additional authorization-bound place candidates. Their selection, authorization, state, reuse, and evidence lifecycles remain separate, and Apply performs no geographic acquisition or interpretation. Apply verifies every selected source through its exact PreCheck Result, accepts the complete Frozen Plan object returned by Plan seal, binds trusted Human authorization to one prepared Run identity, refuses overwrite, journals and recovers effects, and publishes one immutable Receipt. Its Darwin cross-filesystem profile verifies content byte for byte and blocks source deletion until any exact user-relevant metadata loss receives new Human authorization.

## Start here

1. Read [MediaSense Foundation](docs/design/design-260823-1918-mediasense-foundation.md) for the product boundaries and non-negotiable invariants.
2. Read [AI Album Migration Baseline](docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md) before migrating or comparing legacy behavior.
3. Read [the fixture descriptor](eval/fixtures/ai-album-hk-representative-v1.yaml) before using the Hong Kong representative package.
4. For PreCheck development, read the [PreCheck Run Tool Contract](docs/spec/spec-260827-1915A-precheck-run/) and [PreCheck Read Contract](docs/spec/spec-260826-1546-precheck-read/).
5. For Plan development, read the [Plan Working State Tool Contract](docs/spec/spec-260827-1915B-plan-work/), [Geo Query Tool Contract](docs/spec/spec-260830-2034-geo-query/), [Frozen Organization Plan Contract](docs/spec/spec-260827-1138-frozen-plan/), [Default Organization Profile](docs/spec/spec-260828-2026-default-organization-profile/), and [Plan Local Artifact Design](docs/design/design-260828-2043-plan-local-artifacts/).
6. For Apply development, read the [Apply Contract](docs/spec/spec-260829-0050-apply/) and [Apply Activation Evidence](docs/eval/eval-260829-1350-apply-activation-evidence.md).

## Current phase

The `0.6.0` distribution provides the installed `mediasense` executable, portable-
first Dataset discovery, one local composition root, a packaged product entry
Skill and three stage Skills, Tool contracts, and an on-demand stdio MCP Host.
`mediasense mcp` is part of that same
CLI package and exits with its client session; it is not a daemon. The repository
contains the packaged Skill sources but is not itself an activated MediaSense
Honeycomb. Installing the executable does not install Skills, edit any Agent
client's configuration, or enable external providers by default.

PreCheck, Plan, and the first Apply `move_originals` slice are implemented against active contracts. Apply supports its user-facing Skill, durable preparation, exact authorization, same-filesystem moves, the evidence-bounded Darwin cross-filesystem route, pause/resume/cancel, restart reconciliation, immutable Receipts, bounded Receipt reads, and whole-Run rewind. Original-file copy is not a c90 runtime capability despite legacy README wording; persistent relative symbolic links are intentionally deferred because their preview purpose is now Plan-owned and their dangling/rebinding lifecycle is not accepted. Broader cross-filesystem platforms, ACL-bearing cross-filesystem sources, and representative user-storage throughput remain uncertified.

The former implementation remains in `/Users/chengyanru/repos/personal/photo/ai_album` as historical evidence. MediaSense is a new project and must not take a runtime dependency on that repository.
