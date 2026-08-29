# MediaSense

MediaSense is an agent-native system for organizing large personal media collections without requiring an agent to inspect every image or exposing source files to premature, opaque automation.

The product is organized around three user-facing skills:

- `mediasense.precheck` prepares a large media collection with source-read-only, local-first, resumable computation; external evidence calls are disabled by default and require a frozen-scope confirmation.
- `mediasense.plan` lets an agent and user iteratively turn static evidence into a complete, reviewable organization plan.
- `mediasense.apply` validates and safely applies a frozen plan without making new semantic decisions.

The three durable handoff roles are the precheck result, the frozen organization plan, and the apply receipt. PreCheck and Plan have active read, run, working-state, Frozen Plan, default organization, and local-artifact contracts or designs. Apply has a review-stage reference handoff and contract candidate. Its source-verification and declared Darwin APFS cross-filesystem activation gates now have executable evidence, including fail-closed public PreCheck Read integration. The contract still requires explicit Human activation before production mutation runtime begins.

## Start here

1. Read [MediaSense Foundation](docs/design/design-260823-1918-mediasense-foundation.md) for the product boundaries and non-negotiable invariants.
2. Read [AI Album Migration Baseline](docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md) before migrating or comparing legacy behavior.
3. Read [the fixture descriptor](eval/fixtures/ai-album-hk-representative-v1.yaml) before using the Hong Kong representative package.
4. For Plan development, read the [Plan Working State Tool Contract](docs/spec/spec-260827-1915B-plan-work/), [Frozen Organization Plan Contract](docs/spec/spec-260827-1138-frozen-plan/), [Default Organization Profile](docs/spec/spec-260828-2026-default-organization-profile/), and [Plan Local Artifact Design](docs/design/design-260828-2043-plan-local-artifacts/).

## Current phase

PreCheck and Plan have active contracts and implementations. Apply has a review-stage Run, Receipt, and Read contract plus a pre-activation, zero-media-effect preparation implementation; it has no active contract, Skill, or production mutation Tool yet.

The former implementation remains in `/Users/chengyanru/repos/personal/photo/ai_album` as historical evidence. MediaSense is a new project and must not take a runtime dependency on that repository.
