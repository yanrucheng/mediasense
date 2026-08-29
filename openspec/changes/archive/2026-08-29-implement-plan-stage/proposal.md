## Why

MediaSense has active contracts and reviewed examples for Plan working state and Frozen Plans, but no production Plan implementation. The stage must turn one exact PreCheck Result and evolving Human intent into an inspectable, revision-bound preview and then an immutable Frozen Plan, without moving source media or forcing Apply to make semantic decisions.

## What Changes

- Implement the four existing `mediasense.plan.work` actions: `create`, `update`, `inspect`, and `seal`.
- Persist mutable, revisioned Working State and request idempotency in the Plan-local SQLite store.
- Validate complete candidate content against the active Frozen Plan contract and one exact immutable PreCheck Result reached only through `mediasense.precheck.read`.
- Add a deterministic, read-only preview capability bound to one exact candidate revision and content identity. It exposes the proposed directory tree, per-directory counts, representative media, explicit other outcomes, and bounded drill-down without becoming authoritative state.
- Publish immutable Frozen Plan JSON through a recoverable, non-overwriting protocol after trusted Human confirmation of the exact reviewed content.
- Add the `mediasense.plan` Skill and Mock-driven interaction path for progressive evidence reading, proposal, preview, revision, confirmation, and sealing.
- Evaluate migrated Plan behavior against the AI Album baseline, including functional coverage, model cost, reuse, user attention, uncertainty visibility, and file safety.
- Keep reverse geocoding and other reusable geographic enrichment outside this change. Plan consumes such evidence when an exact PreCheck Result provides it; it performs no live reverse-geocoding request.
- Preserve the repository's Zero Backward Compatibility policy. No aliases, adapters, version routers, or deprecated draft representations are introduced.

## Capabilities

### New Capabilities

- `plan-working-state`: Durable creation, inspection, revision replacement, deterministic validation, and trusted sealing of one Plan Working State.
- `plan-review-preview`: Deterministic, revision-bound, regenerable review of the proposed logical organization before confirmation.
- `plan-agent-workflow`: Agent guidance for evidence-led organization, preview-driven revision, Human confirmation, and migration-aware completion.

### Modified Capabilities

None. The repository's active Plan, Frozen Plan, PreCheck Read, Default Organization Profile, and local-artifact documents remain authoritative; this change implements them and adds the newly accepted preview requirement without changing `mediasense.plan.work`'s four-action contract.

## Impact

- Adds `src/mediasense/plan/` with a small public Tool boundary and private persistence, candidate, preview, and publication modules.
- Adds Plan implementation, preview, failure-recovery, and Skill evaluation tests while retaining the existing contract tests.
- Adds one repository-local `mediasense-plan` Skill only after the deterministic Tool and preview behavior are established.
- Uses the existing PreCheck Read Mock so Plan development does not depend on PreCheck SQLite, caches, or incomplete runtime producers.
- Introduces no source-media mutations, Apply behavior, live model calls in tests, online map calls, new authoritative manifests, persistent previews, Profile copies, or PreCheck Result copies.
- Retains one Human checkpoint to review the first concrete preview before its presentation contract is finalized. All other slices may proceed continuously unless a contract contradiction, authority expansion, or failing baseline requires escalation.
