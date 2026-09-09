---
id: "eval-260823-1918-ai-album-migration-baseline"
title: "AI Album Migration Baseline"
type: eval
status: active
created: 2026-08-23
updated: 2026-09-09
timezone: "Asia/Shanghai"
parent: "index-eval"
depends-on:
  - "design-260823-1918-mediasense-foundation"
superseded-by: ""
tags: ["ai-album", "migration", "hong-kong", "fixture"]
---

# AI Album Migration Baseline

## Question and conclusion

This evaluation asks what AI Album actually did on the `260501-HK美食之旅` production collection, which capabilities MediaSense should preserve, which behaviors it should intentionally change, and how future Agents can continue development without independently reconstructing the same evidence or requiring routine access to the approximately 1.09 TB source.

The central conclusion is:

> Preserve the cost-compression funnel—logical media bundling, local metadata and embeddings, reusable artifacts, and representative selection—but do not preserve the fixed pipeline's habit of turning uncertain per-item semantic guesses directly into globally propagated folder names.

The portable `ai-album-hk-representative-v1` package is a strong first-line migration fixture. It preserves the full legacy bundle topology and a replayable historical baseline while reducing source media payload from roughly 944 GB of valid media to roughly 983 MB. It is not proof of multi-terabyte throughput or failure resilience.

## Evidence boundary

The first-pass conclusions are based on:

- AI Album source at `/Users/chengyanru/repos/personal/photo/ai_album`, inspected at commit `c90aa8f04fd0d3348284e0ad19e18462987b1af2`.
- Production source `/Volumes/RC24D-2T/YR-230520-8/260501-HK美食之旅`, cache `/Volumes/RC24D-2T/YR-230520-8/.similarity_cache/260501-HK美食之旅`, and output `/Volumes/RC24D-2T/YR-230520-8/260501-HK美食之旅-clustered`, inspected read-only.
- Shell history, project configuration, production artifacts, source code, and the representative package manifest.
- A successful Docker replay using `chengyanru/ai-album:3.0.0`.

The historical VLM-call figures are reconstructed from successful cache artifacts because the production command did not enable a usage log. They are estimates and lower bounds, not exact billing records.

## Conclusion-bearing structure

The observed system has two distinct compression layers:

1. File-level compression combines related JPG, RAW, sidecar, video, and time-adjacent items into logical bundles. This produced a large and valuable reduction.
2. Semantic evidence compression should select a small, coverage-aware set of representatives, boundaries, and outliers for an Agent. AI Album did not complete this second reduction: it still performed remote visual interpretation for most bundle representatives.

This distinction explains both what should be migrated and why simply wrapping the legacy pipeline in an Agent would not solve the cost or quality problem.

## Modules

- [Legacy system and HK run](eval-260823-1918A-legacy-system.md) records the observed pipeline, quantitative funnel, inferred model use, and failure modes.
- [Migration capability ledger](eval-260823-1918B-capability-ledger.md) assigns legacy capabilities to MediaSense stages, records intended parity or change, and now separates the finalized evidence-delivery contract from the installed production/consumer gates.
- [Representative fixture coverage](eval-260823-1918C-fixture-coverage.md) explains what the 1.7 GB package can and cannot establish.
- [AI Album stored information inventory](eval-260823-1918D-ai-album-stored-information.md) inventories native persisted artifacts, package-added evidence, in-memory gaps, dependencies, consumers, invalidation, and uncertainty without assigning MediaSense stage ownership.

Read the modules in order: A establishes the historical run, B records migration intent, C bounds the portable fixture, and D provides the stage-neutral information inventory required before any MediaSense information-domain mapping.

The inventory boundary in module D was accepted by human review on 2026-08-25. Later design may map or reject its evidence, but should reopen the historical inventory only under module D's stated reopening conditions.

## Current confidence and remaining uncertainty

High-confidence findings include the final production command, bundle/output counts, cache inventory, representative types, metadata/GPS coverage, fixed clustering thresholds, and normalized cached replay. These are supported by multiple artifacts or machine-readable manifests.

The exact production token spend, retry count, provider-side image-token accounting, semantic correctness of the legacy folder tree, and full-dataset throughput remain unknown. They must not be inferred from the cached replay.

The current research is sufficient to establish the MediaSense product boundary and begin manual stage-artifact design. It is not sufficient to freeze stage schemas or select final algorithms.

## Continuation and stopping rules

Continue research when a proposed contract cannot account for a known fixture case, when a migrated capability produces an unexplained difference, or when a decision depends on scale properties absent from the representative package. Use the original 1.09 TB source only for milestone tests involving real throughput, full video decoding, cache capacity, long-duration interruption, or storage-device behavior.

Do not reopen settled product boundaries merely because a different library or model becomes available. Reopen them only if evidence shows that the three-stage handoff cannot preserve intent, safety, coverage, or independent lifecycle ownership.
