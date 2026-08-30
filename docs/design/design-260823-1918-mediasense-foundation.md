---
id: "design-260823-1918-mediasense-foundation"
title: "MediaSense Foundation"
type: design
status: active
created: 2026-08-23
updated: 2026-08-30
timezone: "Asia/Shanghai"
parent: "index-design"
depends-on: []
superseded-by: ""
tags: ["mediasense", "agent-native", "media-organization"]
---

# MediaSense Foundation

## Purpose

MediaSense helps an agent and a user organize media collections ranging from hundreds of files to multi-terabyte or hundred-thousand-item datasets. It must preserve the cost advantage of local precomputation and representative sampling while returning semantic interpretation, ambiguity handling, naming, and approval to the agent and user.

MediaSense is a new, independent project. It selectively preserves valuable logic from AI Album but does not depend on the AI Album repository at runtime. AI Album remains historical implementation evidence and a migration baseline.

## Governing relation

The system must reduce a large, uncompressed source into sufficient reviewable evidence before expensive semantic reasoning, then separate that reasoning from filesystem mutation:

```text
large source collection
  -> local, source-read-only preparation
  -> static evidence and reusable analysis
  -> agent/user planning and confirmation
  -> frozen, complete organization plan
  -> deterministic safety checks and execution
  -> verifiable receipt
```

This relation generates three product stages and three user-facing Skills. The stages are not required to map one-to-one to internal Tool calls.

## The three stages

| Skill | Stable purpose | Dominant owner | Stage completion |
| --- | --- | --- | --- |
| `mediasense.precheck` | Prepare the largest, still-uncompressed data safely and economically for later reasoning. | Tools, guided and interpreted by an Agent | A complete or explicitly partial, immutable precheck result is available. |
| `mediasense.plan` | Use the static result, bounded visual evidence, and user interaction to decide the complete organization. | Agent, guided by Skill and supported by query/validation Tools | A plan is complete, reviewed, versioned, and frozen. |
| `mediasense.apply` | Faithfully and safely apply one exact frozen plan to the filesystem. | Deterministic Tools, with Agent explanation and human authorization | Every planned item has a verified outcome and an execution receipt. |

### `mediasense.precheck`: heavy but entrustable

`precheck` is not designed to be slow. It faces the largest data volume, so it must optimize throughput and avoid repeated work. The system must nevertheless remain safe and useful if the work takes hours. Its stable guarantees are:

- Source media is read-only. Derived artifacts are written to a separate workspace.
- Remote calls, uploads, reverse-geocoding services, and billable model access are disabled by default and reported explicitly.
- After compression freezes a normalized, deduplicated representative-coordinate batch, a Run may perform coordinate-only reverse geocoding under one authorization bound to that exact batch and effective profile. This never authorizes media, rendition, embedding, path, filename, prompt, or general-metadata egress.
- Metadata extraction, decoding, thumbnailing, frame selection, fingerprinting, embedding, indexing, and grouping reuse completed work where valid.
- Work is observable, bounded in resource use, resumable after interruption, and incrementally invalidated.
- A disconnected volume is treated as unavailable, not as evidence that its files were deleted.
- One corrupt asset becomes a localized error and does not invalidate unrelated completed work.
- A partial working state is not presented as a complete precheck result.
- The result records provenance, confidence, failures, omissions, processing profiles, coverage, and externally observable cost.

Exact implementations—ExifTool, FFmpeg, embedding model, index, clustering algorithm, and cache layout—remain replaceable.

### `mediasense.plan`: interactive convergence

`plan` starts from one static precheck result. It may use a modern multimodal model or an authorization-bound stage-neutral capability, but it must not inspect every asset or acquire new evidence by default. It progressively selects representative, boundary, outlier, and conflict evidence under explicit visual, external-effect, cost, and user-attention budgets. If additional place evidence is material, Plan owns the exact query purpose, selected Result coordinates, authorization binding, retained observations, and stopping decision; it does not inherit PreCheck Run authority. Plan-local observations never rewrite the bound PreCheck Result.

It must keep these meanings separate:

- observed facts and their provenance;
- computed groups and scores;
- candidate semantic claims;
- Agent judgments;
- user-confirmed decisions;
- display names and target paths.

A map, tree, or mind-map UI is a view of the evolving organization plan, not a second source of truth. The Agent should ask about high-impact uncertainty rather than every uncertain item. A confirmation has an explicit scope; confirming one restaurant event must not silently label a day, neighborhood, or unrelated assets.

The stage ends only when every in-scope asset has an explicit disposition, conflicts have been resolved, remaining uncertainty is accepted or deferred explicitly, and the exact plan version is frozen. Planning never reorganizes source media.

## Evidence acquisition and downstream policy

`precheck` owns reusable source-derived evidence acquisition and its immutable Result projection; `plan` owns the policy for interpreting and using that evidence. Plan may additionally retain a bounded observation acquired for one planning question through an authorization-bound stage-neutral capability. That observation is Plan-owned, revision-bound candidate evidence and never edits or impersonates PreCheck evidence. A downstream policy's current choice not to consume an observation is not, by itself, a reason to remove an independently useful upstream evidence capability.

- `precheck` may produce local, source-derived candidate signals, including content-sensitivity observations. Such signals must retain their producer, effective profile, score or quality where available, completion or failure state, and other provenance needed to challenge or regenerate them. They are evidence, not semantic truth, user authorization, or a routing decision.
- The exact detector, model, labels, thresholds, and implementation remain replaceable. The stage boundary preserves the evidence capability and its traceability, not one historical classifier or taxonomy.
- `plan` may use or ignore sensitivity evidence according to an explicit policy. Valid policies may include all-local processing, all-remote processing, signal-informed routing, warnings before remote use, user confirmation, or future mechanisms. No one mechanism is part of the stage contract.
- VLM providers expose their locality and data-egress effects; `plan` selects and invokes them under the applicable user policy and authorization. A provider must not silently change locality or fall back from local to remote execution.
- `precheck` does not choose a local or remote VLM path from sensitivity signals. Local evidence acquisition does not relax its source-read-only, local-first, external-call-disabled-by-default, or explicit authorization and effect-reporting guarantees. Coordinate-only reverse geocoding may run after compression freezes the exact logical query set and the user confirms it; this does not authorize media, feature, or prompt egress.

This separation lets evidence collection improve independently from planning policy, while allowing stronger future Agents and providers to replace today's interpretation and routing methods without changing the precheck handoff boundary.

### `mediasense.apply`: safe and faithful

`apply` accepts only a frozen plan. It performs no captioning, geographic acquisition or interpretation, grouping, or naming. Unexpected conditions are returned to planning rather than resolved semantically by the executor.

Its safety guarantees belong in Tools, not merely in Skill instructions:

- Bind authorization to an exact plan digest, the selected Result-local Source
  Item references, and their safely rebound source roots; revalidate the selected
  source bytes from their declared, replaceable verification observations.
- Refuse silent overwrite and unplanned target-name changes.
- For same-filesystem moves, use filesystem rename semantics and preserve basenames when the plan requires it.
- Never silently fall back from a cross-filesystem move to copy-then-delete.
- Treat verified cross-filesystem transfer as a distinct, explicitly authorized mode.
- Write the operation journal before mutation, update it transactionally, support restart, and make repeated execution idempotent.
- Verify postconditions and issue a receipt that accounts for every planned asset.

No software can eliminate physical-media failure. MediaSense's guarantee is against detectable logical loss, silent overwrite, unplanned mutation, and unknowable partial execution; backup policy remains a separate concern.

## Handoff roles and authority

Three independent lifecycle boundaries require three handoff roles:

1. The precheck result is authoritative for what was observed and computed from a particular source snapshot. Mutable checkpoints remain internal working state.
2. The frozen organization plan is authoritative for user and Agent intent. It references one compatible precheck result and does not become valid merely because a Tool emitted it.
3. The apply receipt is authoritative for what execution actually attempted and verified. It must never rewrite history to match the intended plan.

These are conceptual roles, not approved schemas. Their exact filenames, storage formats, and field sets will be defined only after realistic human-reviewed examples exist.

## Agent, Skill, and Tool boundaries

- Tools perform typed I/O, batch computation, persistent state, resource limits, hard safety checks, and verifiable execution. They return facts, candidates, scores, errors, and receipts; they do not assert ambiguous semantic truth.
- Skills preserve reusable methods: how to scope a collection, interpret quality signals, allocate visual attention, select high-leverage questions, converge a plan, request authorization, and respond to failures. Skills do not perform I/O or guarantee filesystem safety.
- The Agent interprets user intent, chooses which criteria matter, reads selected evidence, reasons about ambiguity, proposes organization and names, asks the user, and decides whether evidence is sufficient.
- The human owns high-impact semantic confirmation and authorization of irreversible or materially risky effects. Tools enforce that required authorization exists.

A substantially stronger future Agent must be able to use better reasoning and visual understanding without replacing the stage contracts or dismantling local indexing and safety enforcement.

## Development method

Each stage follows the same contract-first sequence:

1. Manually construct a realistic example of the stage's final handoff.
2. Review whether it is understandable to a human and sufficient for the next stage without hidden state.
3. Define runtime, interruption, failure, and resumption semantics.
4. Extract only the stable minimum into a formal contract.
5. Implement deterministic Tools against fixtures.
6. Write the Skill that teaches an Agent how to use, interpret, and challenge those Tools.
7. Compare the resulting capability with AI Album and classify every material difference.

Human-reviewed fixtures allow the three implementation tracks to proceed in parallel without coupling downstream work to unstable upstream internals.

## Three managed budgets

MediaSense must expose and manage three different costs:

- Local compute and I/O during precheck.
- Model image/token usage during planning.
- User attention during confirmation.

Optimizing one by silently expanding another is not success. Coverage and residual uncertainty must remain visible.

## Out of scope for the current foundation

The following remain deliberately open:

- Exact schemas and filenames for stage handoffs.
- Programming language, Agent framework, database, vector index, and model provider.
- Exact clustering and representative-selection algorithm.
- Mind-map or other planning UI technology.
- Packaging and distribution of the three Skills.
- Cross-filesystem transfer support beyond the safety boundary described above.

These questions should be settled only when a reviewed handoff example, measured constraint, or implementation experiment can discriminate between alternatives.

## Reopen conditions

Revisit this foundation if evidence shows that:

- a stage cannot be consumed without hidden mutable state from another stage;
- one handoff cannot be independently versioned, reviewed, or reproduced;
- safe execution requires semantic decisions after plan freeze;
- the three-stage split forces material repeated computation or prevents stronger Agents from using better methods; or
- a stated guarantee cannot be enforced or honestly verified.
