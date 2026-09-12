# MediaSense Agent Guidance

## Required reading

Before architecture, contract, Skill, Tool, or migration work:

1. Read `docs/design/design-260823-1918-mediasense-foundation.md`.
2. Before creating or reviewing a shared module, provider adapter, stage-neutral Tool, capability Skill, artifact, registry, or service, read `docs/design/design-260830-1527-reusable-capability-architecture.md`.
3. Before PreCheck model, evidence, or handoff work, read `docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md`. Before changing a public Tool, read `docs/spec/contract/index.md` and the relevant active contract.
4. For legacy comparison, read `docs/eval/eval-260823-1918-ai-album-migration-baseline/index.md` and its linked modules.
5. Before using the Hong Kong fixture, read `eval/fixtures/ai-album-hk-representative-v1.yaml`, then the package's own `README.md` and `docs/RESEARCH-AND-HANDOFF.zh-CN.md`. Run the package verifier before trusting its contents.

For installation, local upgrades, readiness verification, rollback, or changes to
those paths, use the single [installation and upgrade runbook](readme/installation.md).
Its packaged Skill copy is a release snapshot, not a second authoring source;
maintain it and its consistency checks in the same change.

For local model evaluation, use the single [model evaluation runbook](readme/model-evaluation.md).

Before reading or maintaining manufacturer YAML, use the adjacent
[manufacturer knowledge runbook](src/mediasense/_resources/manufacturers/README.md).
It explains authoring and verification; the linked active contract owns field semantics.

## Authority and boundaries

- This repository is authoritative for MediaSense product intent, contracts, Skills, Tools, and migration judgments.
- `/Users/chengyanru/repos/personal/photo/ai_album` is historical implementation evidence, not a MediaSense runtime dependency or design authority.
- External fixtures are evidence assets. They are not source code, product specifications, or ground truth for corrected MediaSense behavior.
- Original media is the factual source. Indexes, thumbnails, embeddings, clusters, plans, and output trees are derived artifacts with distinct lifecycles.
- Do not create a final stage schema or Skill merely from an implementation convenience. First establish a human-reviewed handoff example and runtime/failure semantics.

## PreCheck model and contract development

- The [compression model](docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md) owns object, relationship, and attribute meanings. Attributes extend the information about an identified subject; they do not replace identity, relationship endpoints, accounting, or authority. Reuse existing Observation, basis, and qualification semantics before adding another structure.
- Representative is a role of Evidence. A representative read joins its own information with its compression relationships; it is a regenerable view, not a new entity. Derivation from one source never makes that source's attributes facts about every represented member.
- Implement the public contract under `docs/spec/contract/`; the two milestone statuses there separate a finalized contract from a conforming release. Historical dated specs and OpenSpec change packets are not current contracts. Use its declared extension rules; a change to promised semantics requires an explicitly reviewed contract change. Do not rewrite the contract or its examples merely to make an implementation pass.
- Keep declared capabilities distinct from execution and delivery. An extensible attribute model does not prove that a legacy capability was collected, wired into the installed entry point, or exposed to its consumer. Record those gates in the existing migration ledger.

## Execution-state honesty

- Follow [Execution-state honesty](docs/design/design-260823-1918-mediasense-foundation.md#execution-state-honesty) before designing or interpreting long-running lifecycle states. A state must be backed by a real mechanism: never use `queued`, `running`, `blocked`, or `paused` as a catch-all for a missing execution owner, unknown exception, or violated invariant. Preserve expected waits explicitly and let unexpected implementation failures surface immediately.

## Non-negotiable stage invariants

- `mediasense.precheck`: source media remains read-only; remote calls and billable model access are disabled by default; long work is observable, resumable, incrementally reusable, and honest about partial completion.
- `mediasense.plan`: the agent owns interpretation and interaction; facts, candidates, confidence, agent judgment, and user confirmation remain distinguishable; no source media is reorganized.
- `mediasense.apply`: only a frozen plan may be executed; no new semantic decision is allowed; safety gates, collision refusal, same-filesystem checks, journaling, idempotency, and post-verification belong to deterministic Tools.

## Migration discipline

For each migrated capability, compare MediaSense with AI Album and classify differences as `preserved`, `intentionally_changed`, `regression`, or `not_comparable`. Compare functional coverage and relevant operating qualities such as local/remote cost, throughput, resumability, cache reuse, user effort, and file safety. A difference from the legacy output is not automatically a regression.

Do not mutate a versioned fixture and continue to claim its recorded checksum or baseline. Write all evaluation output outside the fixture. Do not place bulk media, generated caches, raw logs, or model output in Git.
