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

- `mediasense-precheck` prepares a large media collection with source-read-only, local-first, resumable computation; every external evidence call requires authorization for its exact frozen effect scope.
- `mediasense-plan` lets an agent and user iteratively turn one immutable Result plus clearly attributed Human semantic decisions into a complete, reviewable organization plan.
- `mediasense-apply` validates and safely applies a frozen plan without making new semantic decisions.

The three durable handoff roles are the precheck result, the frozen organization plan, and the apply receipt. PreCheck, Plan, and Apply now have active contracts and packaged user-facing Skills for the first end-to-end `move_originals` path. The Skills guide Human/Agent interaction while Tools remain authoritative for PreCheck work and Results, Plan validation and freezing, and deterministic Apply effects and Receipts. PreCheck owns media-aware Geo acquisition: it compresses bundle, time, coordinate, and trajectory evidence into a bounded query set, invokes the shared `mediasense.geo.query` Tool under exact Run-scoped authorization, and publishes one outcome for every located Source Item. Plan interprets that immutable Result and may call the same Geo Tool for a small, separately authorized investigation when it challenges an over-broad prepared assignment; it cannot use that path to conceal missing PreCheck coverage or mutate the Result. Apply performs no geographic acquisition or interpretation. It verifies every selected source through its exact PreCheck Result, accepts the complete Frozen Plan object returned by Plan seal, binds trusted Human authorization to one prepared Run identity, refuses overwrite, journals and recovers effects, and publishes one immutable Receipt. Its Darwin cross-filesystem profile verifies content byte for byte and blocks source deletion until any exact user-relevant metadata loss receives new Human authorization.

## Start here

1. Read [MediaSense Foundation](docs/design/design-260823-1918-mediasense-foundation.md) for the product boundaries and non-negotiable invariants.
2. Read [AI Album Migration Baseline](docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md) before migrating or comparing legacy behavior.
3. Read [the fixture descriptor](eval/fixtures/ai-album-hk-representative-v1.yaml) before using the Hong Kong representative package.
4. For PreCheck development, first read the [object, relationship, and attribute model](docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md), then the [PreCheck Run Tool Contract](docs/spec/contract/precheck-run/) and [PreCheck Read Contract](docs/spec/contract/precheck-read/). The stable contract directory is the only development authority; its milestone status distinguishes the finalized contract from the currently installed release.
5. For Plan development, read the [Plan Working State Tool Contract](docs/spec/contract/plan-work/), [Frozen Organization Plan Contract](docs/spec/contract/frozen-plan/), [Default Organization Profile](docs/spec/contract/default-organization-profile/), and [Plan Local Artifact Design](docs/design/design-260828-2043-plan-local-artifacts/).
6. For Apply development, read the [Apply Contract](docs/spec/contract/apply/) and [Apply Activation Evidence](docs/eval/eval-260829-1350-apply-activation-evidence.md).

## Current phase

The [PreCheck evidence-delivery contract](docs/spec/contract/precheck-read/index.md) and its production implementation have passed milestone-one and milestone-two acceptance, including the metadata, historical-detection, and pagination corrections. The [capability ledger](docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md) retains the exact evidence and certification limits.

The `0.9.0` distribution provides the installed `mediasense` executable, portable-
first Dataset discovery, one local composition root, a packaged product entry
Skill and three stage Skills, Tool contracts, and an on-demand stdio MCP Host.
`mediasense mcp` is part of that same
CLI package and exits with its client session; it is not a daemon. The repository
contains the packaged Skill sources but is not itself an activated MediaSense
Honeycomb. Installing the executable does not install Skills, edit any Agent
client's configuration, or enable external providers by default.

This release changes the Read response protocol: `review.items` delivers each
Evidence's own attributes and actual Source Items separately from its `represents`
relationships. Prepared Evidence can be selected explicitly; unreadable or oversized
items remain local failures with continuation to later items. Photographic metadata,
ordinary/high-resolution renditions, video and Geo evidence, and optional local
sensitivity signals are delivered through the installed Host. MCP returns one
`structuredContent` result with empty `content`. Upgrade the CLI and all four Skills
together; 0.8 clients are incompatible. See the [0.9.0 release notes](CHANGELOG.md)
and [upgrade steps](readme/installation.md#upgrade-and-rollback), then start a
new Agent session.

Acceptance covers the recorded controlled delivery paths. Model and representative
quality, broad codec/HDR support, live Geo quality and terms, large-collection
throughput, and arbitrary Agent clients' large-page consumption remain uncertified.

PreCheck, Plan, and the first Apply `move_originals` slice are implemented against active contracts. Apply supports its user-facing Skill, durable preparation, exact authorization, same-filesystem moves, the evidence-bounded Darwin cross-filesystem route, pause/resume/cancel, restart reconciliation, immutable Receipts, bounded Receipt reads, and whole-Run rewind. Original-file copy is not a c90 runtime capability despite legacy README wording; persistent relative symbolic links are intentionally deferred because their preview purpose is now Plan-owned and their dangling/rebinding lifecycle is not accepted. Broader cross-filesystem platforms, ACL-bearing cross-filesystem sources, and representative user-storage throughput remain uncertified.

The former implementation remains in `/Users/chengyanru/repos/personal/photo/ai_album` as historical evidence. MediaSense is a new project and must not take a runtime dependency on that repository.
