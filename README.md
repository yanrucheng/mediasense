# MediaSense

MediaSense is an agent-native system for organizing large personal media collections without requiring an agent to inspect every image or exposing source files to premature, opaque automation.

The product is organized around three user-facing skills:

- `mediasense.precheck` prepares a large media collection with source-read-only, local-first, resumable computation; external evidence calls are disabled by default and require a frozen-scope confirmation.
- `mediasense.plan` lets an agent and user iteratively turn static evidence into a complete, reviewable organization plan.
- `mediasense.apply` validates and safely applies a frozen plan without making new semantic decisions.

The three durable handoff roles are the precheck result, the frozen organization plan, and the apply receipt. PreCheck, Plan, and Apply now have active contracts for the first end-to-end `move_originals` path. Apply verifies every selected source through its exact PreCheck Result, binds trusted Human authorization to one prepared Run identity, refuses overwrite, journals and recovers effects, and publishes one immutable Receipt. Its Darwin cross-filesystem profile verifies content byte for byte and blocks source deletion until any exact user-relevant metadata loss receives new Human authorization.

## Start here

1. Read [MediaSense Foundation](docs/design/design-260823-1918-mediasense-foundation.md) for the product boundaries and non-negotiable invariants.
2. Read [AI Album Migration Baseline](docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md) before migrating or comparing legacy behavior.
3. Read [the fixture descriptor](eval/fixtures/ai-album-hk-representative-v1.yaml) before using the Hong Kong representative package.
4. For Plan development, read the [Plan Working State Tool Contract](docs/spec/spec-260827-1915B-plan-work/), [Frozen Organization Plan Contract](docs/spec/spec-260827-1138-frozen-plan/), [Default Organization Profile](docs/spec/spec-260828-2026-default-organization-profile/), and [Plan Local Artifact Design](docs/design/design-260828-2043-plan-local-artifacts/).
5. For Apply development, read the [Apply Contract](docs/spec/spec-260829-0050-apply/) and [Apply Activation Evidence](docs/eval/eval-260829-1350-apply-activation-evidence.md).

## Current phase

PreCheck, Plan, and the first Apply `move_originals` slice are implemented against active contracts. Apply supports durable preparation, exact authorization, same-filesystem moves, the evidence-bounded Darwin cross-filesystem route, pause/resume/cancel, restart reconciliation, immutable Receipts, bounded Receipt reads, and whole-Run rewind. Copy/link profiles, broader cross-filesystem platforms, ACL-bearing sources, and representative real-media throughput measurements remain deferred.

The former implementation remains in `/Users/chengyanru/repos/personal/photo/ai_album` as historical evidence. MediaSense is a new project and must not take a runtime dependency on that repository.
