# MediaSense Agent Guidance

## Required reading

Before architecture, contract, Skill, Tool, or migration work:

1. Read `docs/design/design-260823-1918-mediasense-foundation.md`.
2. For legacy comparison, read `docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md` and its linked modules.
3. Before using the Hong Kong fixture, read `eval/fixtures/ai-album-hk-representative-v1.yaml`, then the package's own `README.md` and `docs/RESEARCH-AND-HANDOFF.zh-CN.md`. Run the package verifier before trusting its contents.

## Authority and boundaries

- This repository is authoritative for MediaSense product intent, contracts, Skills, Tools, and migration judgments.
- `/Users/chengyanru/repos/personal/photo/ai_album` is historical implementation evidence, not a MediaSense runtime dependency or design authority.
- External fixtures are evidence assets. They are not source code, product specifications, or ground truth for corrected MediaSense behavior.
- Original media is the factual source. Indexes, thumbnails, embeddings, clusters, plans, and output trees are derived artifacts with distinct lifecycles.
- Do not create a final stage schema or Skill merely from an implementation convenience. First establish a human-reviewed handoff example and runtime/failure semantics.

## Non-negotiable stage invariants

- `mediasense.precheck`: source media remains read-only; remote calls and billable model access are disabled by default; long work is observable, resumable, incrementally reusable, and honest about partial completion.
- `mediasense.plan`: the agent owns interpretation and interaction; facts, candidates, confidence, agent judgment, and user confirmation remain distinguishable; no source media is reorganized.
- `mediasense.apply`: only a frozen plan may be executed; no new semantic decision is allowed; safety gates, collision refusal, same-filesystem checks, journaling, idempotency, and post-verification belong to deterministic Tools.

## Migration discipline

For each migrated capability, compare MediaSense with AI Album and classify differences as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`. Compare functional coverage and relevant operating qualities such as local/remote cost, throughput, resumability, cache reuse, user effort, and file safety. A difference from the legacy output is not automatically a regression.

Do not mutate a versioned fixture and continue to claim its recorded checksum or baseline. Write all evaluation output outside the fixture. Do not place bulk media, generated caches, raw logs, or model output in Git.
