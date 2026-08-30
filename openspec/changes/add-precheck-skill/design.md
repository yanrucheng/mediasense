## Context

The PreCheck runtime, its immutable Result, and the `mediasense.precheck.run`
and `mediasense.precheck.read` contracts already exist. Plan and Apply have
repository-local user-facing Skills, while PreCheck does not. This change adds
the missing procedural knowledge after the deterministic boundaries are stable;
it does not redesign the stage or turn the Skill into another runtime authority.

The Skill must be useful for collections ranging from hundreds of files to
multi-terabyte or hundred-thousand-item Datasets. It therefore has to help an
Agent choose a compression purpose, explain long-running state, adapt evidence
budgets, and preserve uncertainty without fixing today's algorithms or storage
implementation as permanent workflow law.

## Goals / Non-Goals

**Goals:**

- Make PreCheck normally discoverable for preparation, observation, recovery,
  result interpretation, and Plan handoff.
- Preserve the Human, Agent, Skill, Tool, and Result authority boundaries.
- Keep source media read-only and external work disabled by default.
- Support goal-driven initial compression and later recompression or evidence
  expansion without hiding cost, coverage, or uncertainty.
- Verify the workflow with positive and negative activation cases plus
  independent realistic Agent scenarios.

**Non-Goals:**

- No new Tool action, schema, runtime state, storage format, producer, or I/O.
- No fixed clustering method, database, hash, extractor, decoder, model,
  threshold, directory layout, or execution profile in the Skill.
- No Plan grouping or naming decisions and no Apply filesystem effects.
- No fresh media replay, live provider call, remote model, online map, or paid
  API during validation.

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | Not in production |
| BC Level | None — Zero BC policy |

No production consumer exists for the missing Skill. Compatibility aliases,
version routers, duplicated contract representations, and adapters are
prohibited. Existing PreCheck Run/Read contracts remain unchanged because they
are already the authoritative boundary used by Plan and Apply.

## Decisions

### The Skill owns guidance, not execution or truth

The Human owns collection intent, consequential trade-offs, the bounded online
decision, and the choice after a blocked Result. The Agent interprets that
intent, recommends a compression purpose, explains observable status and
uncertainty, and chooses among Tool-supported next steps. The Skill supplies the
reusable criteria and workflow. `mediasense.precheck.run` owns discovery, long
work, control transitions, confirmation enforcement, recovery, and publication;
`mediasense.precheck.read` owns immutable Result views and evidence navigation.

This allocation prevents Skill prose from becoming a second schema, consent
record, or status store. Direct filesystem, cache, database, or producer access
is not an alternative path.

### One concise Skill is sufficient

Create only `SKILL.md` and `agents/openai.yaml`. The entrypoint links the formal
Run and Read contract documentation instead of copying their schemas. The
workflow is cohesive and short enough that another reference layer would not
reduce conditional context or establish an independent responsibility.

Automatic discovery remains enabled. The description names both the positive
scope and the nearby Plan/Apply exclusions so ordinary preparation requests can
activate it without attracting naming or filesystem-execution requests.

### Compression follows the decision purpose

The Skill asks what downstream decision the evidence must support and balances
coverage, variation, user review burden, local cost, and residual uncertainty.
It does not canonize a target or algorithm. A changed target or purpose creates
a new Run and immutable Result from the exact prior Result lineage through the
available Tool boundary; reusable valid work remains a runtime guarantee, not a
Skill implementation recipe.

When evidence is insufficient, the Agent can recommend targeted Result-local
expansion, a differently compressed Result, or directed upstream rebuild. It
must not manufacture confidence or require one visual rendition per Source
Item. Accounting remains closed through the normal frontier or explicit
auxiliary, excluded, unsupported, invalid, error, or unresolved paths.

### External scope remains narrow and exact

The normal path is local-only. The sole current online exception is reverse
geocoding of the normalized, deduplicated coordinate set frozen after
compression. Before any request, the Agent presents the Tool-reported exact
logical-query count and scope and asks for the matching Human decision. A skip
continues without that optional evidence. The Skill grants no authority to send
media, renditions, features, prompts, or ordinary metadata.

### Observable state drives recovery and completion

The Agent reports the Run state, business progress, structured reason, recovery
condition, and allowed actions from `status`; command acceptance is never
reported as completion. Interruptions preserve reusable work, disconnected
volumes remain unavailable rather than deleted, capacity failures retain
committed work, and corrupt items remain localized when the Tool reports those
facts.

Only an immutable Result read through `mediasense.precheck.read` can support
handoff. Coverage, readiness, and integrity are independent: a partial but
`plan_ready` Result may proceed with its qualifications, while `blocked`
requires an explicit Human choice to continue preparation, request directed
rebuild/other evidence, or stop. Plan receives only the exact `result_ref` and
uses Read; it never receives a PreCheck database or cache path.

### Validation separates structure from behavior

Repository tests validate the Skill package, automatic invocation policy,
contract links, prohibited authority claims, activation examples, and the
complete scenario matrix. Independent Agent passes receive realistic prompts
and Tool observations without the intended answer, then are reviewed for Tool
selection, confirmation, status explanation, recovery, and stage handoff.
Generated evaluation output stays outside Git.

## Risks / Trade-offs

- **Guidance can drift from Tool contracts** → Link the authoritative contract
  documents, add boundary assertions, and run strict OpenSpec validation.
- **A broad description can steal Plan or Apply requests** → Include explicit
  phase exclusions and exercise negative activation prompts independently.
- **A short Skill can omit rare recovery detail** → Teach interpretation of
  Tool-provided reasons and recovery conditions rather than enumerate internal
  exceptions or duplicate schemas.
- **Forward tests are model-dependent** → Pair independent Agent evaluation
  with deterministic package and scenario-contract tests; report both and keep
  the observed transcripts outside the repository.

## Migration Plan

1. Add and strictly validate the `precheck-agent-workflow` capability.
2. Initialize the repository-local Skill with normal automatic discovery.
3. Add deterministic activation/boundary/scenario checks and run independent
   Agent forward tests without media or network effects.
4. Run repository gates and present the uncommitted change for Human review.
5. After explicit acceptance, archive the OpenSpec change and write the original
   completion report to the paired delegation result; do not commit or push.

Rollback removes the new Skill, its focused tests, and this additive capability;
the existing PreCheck runtime and contracts are unchanged.

## Open Questions

None. Production-only providers, model quality, and hardware/filesystem matrices
remain later certification work and do not belong in this Skill change.
