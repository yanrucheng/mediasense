# MediaSense

MediaSense is an agent-native system for organizing large personal media collections without requiring an agent to inspect every image or exposing source files to premature, opaque automation.

The product is organized around three user-facing skills:

- `mediasense.precheck` prepares a large media collection with source-read-only, offline-by-default, resumable local computation.
- `mediasense.plan` lets an agent and user iteratively turn static evidence into a complete, reviewable organization plan.
- `mediasense.apply` validates and safely applies a frozen plan without making new semantic decisions.

The three durable handoff roles are the precheck result, the frozen organization plan, and the apply receipt. The sealed PreCheck result is consumed through the formal [PreCheck Read Contract](docs/spec/spec-260826-1546-precheck-read/); the [Frozen Organization Plan Contract](docs/spec/spec-260827-1138-frozen-plan/) is under review; the Apply contract remains to be derived before its Tool and Skill are implemented.

## Start here

1. Read [MediaSense Foundation](docs/design/design-260823-1918-mediasense-foundation.md) for the product boundaries and non-negotiable invariants.
2. Read [AI Album Migration Baseline](docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md) before migrating or comparing legacy behavior.
3. Read [the fixture descriptor](eval/fixtures/ai-album-hk-representative-v1.yaml) before using the Hong Kong representative package.

## Current phase

This repository establishes the authoritative product direction, migration evidence, and formal stage contracts. PreCheck implementation has begun with Slice 1 source discovery and resumable accounting; the Plan and Apply contracts, the three Skill implementations, and production Tools remain under development.

The former implementation remains in `/Users/chengyanru/repos/personal/photo/ai_album` as historical evidence. MediaSense is a new project and must not take a runtime dependency on that repository.
