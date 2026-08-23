# MediaSense

MediaSense is an agent-native system for organizing large personal media collections without requiring an agent to inspect every image or exposing source files to premature, opaque automation.

The product is organized around three user-facing skills:

- `mediasense.precheck` prepares a large media collection with source-read-only, offline-by-default, resumable local computation.
- `mediasense.plan` lets an agent and user iteratively turn static evidence into a complete, reviewable organization plan.
- `mediasense.apply` validates and safely applies a frozen plan without making new semantic decisions.

The three durable handoff roles are the precheck result, the frozen organization plan, and the apply receipt. Their exact file formats are intentionally not specified yet: each contract will be derived from a manually reviewed, realistic example before its Tool and Skill are implemented.

## Start here

1. Read [MediaSense Foundation](docs/design/design-260823-1918-mediasense-foundation.md) for the product boundaries and non-negotiable invariants.
2. Read [AI Album Migration Baseline](docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md) before migrating or comparing legacy behavior.
3. Read [the fixture descriptor](eval/fixtures/ai-album-hk-representative-v1.yaml) before using the Hong Kong representative package.

## Current phase

This repository currently establishes the authoritative product direction and migration evidence. It does not yet contain final stage schemas, the three Skill implementations, or production Tools. Those will be created only after the corresponding handoff examples and runtime/failure semantics are reviewed by a human.

The former implementation remains in `/Users/chengyanru/repos/personal/photo/ai_album` as historical evidence. MediaSense is a new project and must not take a runtime dependency on that repository.
