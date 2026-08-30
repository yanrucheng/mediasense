---
name: "skill-writing-bible"
description: "Use only when the user explicitly names `skill-writing-bible`."
version: "2.0.0"
activation: "explicit"
context-load: "light"
channels: [public]
---

# Skill Writing Bible

Create, review, or revise Skills for frontier and future Agents. Do not add instructions solely to support less capable models.

## Establish Shared Understanding

Before committing a new or materially changed Skill, establish shared understanding proportionate to its semantic scope, reuse, autonomy, cost, and reversibility. Consequential intent, situations, boundaries, trade-offs, authorities, and downstream results must not depend mainly on unexamined Agent assumptions.

Use any effective method to expose and resolve material ambiguity before it is amplified through the Skill. Agent proposals may extend beyond current consensus, and explicitly delegated choices belong within it; do not commit consequential proposals as settled semantics until they are calibrated with the human. Stop gathering input when remaining uncertainty would not materially change the Skill contract.

## Double Anchors, Open Methods

Apply the following semantics to every resulting Skill. Do not require it to reproduce this Bible's headings, abstraction, reasoning process, workflow, taxonomy, checklist, or document shape.

### Anchor Purpose

Identify the necessary, durable capability that would be lost without the Skill. Generic reasoning advice, familiar best practices, and prompt scaffolding do not establish such a purpose.

Place each fact, rule, decision, responsibility, and result in its proper authority or preserve a reliable discovery path to that authority. State what the Skill owns and what remains authoritative elsewhere.

Introduce no entity unless it has an independent responsibility, authority, loading condition, or lifecycle.

### Anchor the Downstream Product

Define what purpose using the Skill must achieve, what semantic properties and boundaries every acceptable downstream result must satisfy, and what evidence makes acceptance observable. Judge the Skill by those actual results, not by the apparent completeness of `SKILL.md`.

### Leave Methods Open

Fix only genuine constraints. Leave investigation, reasoning, organization, orchestration, tool choice, and execution open unless a particular method is itself an enduring invariant.

## Shape the Runtime Skill

### Keep the Runtime Product Pure

Keep content only when it changes runtime selection, judgment, action, boundaries, or result quality. Exclude design rationale, rejected alternatives, change history, and explanations used only to derive the final instructions. Preserve such reasoning in an OpenSpec packet or another artifact that owns a design-history lifecycle.

Typical failure:

```text
Wrong: Use only when the user explicitly names `skill-writing-bible`, because runtimes may use different invocation prefixes.
Right: Use only when the user explicitly names `skill-writing-bible`.
```

Do not make an Agent consume the reasoning that produced a rule when it only needs the rule.

### Spend Context Deliberately

Retain durable, non-obvious knowledge, consequential failure modes, real constraints, authority paths, and semantic result requirements. Remove generic explanations, duplicated rules, decorative examples, prompt workarounds, and content a frontier Agent can derive reliably.

Keep commonly required guidance in `SKILL.md`. Add companion content only for a distinct loading condition. Split a Skill only when the parts have independent purposes, authorities, loading conditions, or lifecycles. Do not use token counts, line counts, or stylistic categories as substitutes for these judgments.

### Define Selection and Load

Frontmatter is the pre-load selection surface. Its description must let an Agent decide whether to load the Skill without reading its body.

- `activation: "auto"`: describe the task meaning that makes the Skill eligible for selection.
- `activation: "explicit"`: set the description to exactly `Use only when the user explicitly names \`<skill-id>\`.` using the complete ID declared by `name`.
- `context-load: "light" | "standard" | "heavy"`: the relative context loaded after selection; it never changes selection eligibility.

Do not append a purpose, aliases, invocation prefixes, or other routing language to an explicit description. Do not add `entrypoints`. Runtime presentation and parsing are not Skill contracts.

## Accept the Skill

Reject or revise a Skill when:

- its purpose would disappear merely because the Agent became substantially stronger;
- its intended downstream leverage exceeds the shared understanding supporting its consequential semantics;
- its downstream product contract does not make purpose achievement, required result properties, boundaries, and acceptance evidence clear;
- its knowledge, responsibility, or result has no clear authority;
- it constrains a stronger Agent to a replaceable method;
- its runtime content includes the reasoning behind the product instead of the product contract;
- retained content lacks sufficient marginal behavioral value; or
- an introduced entity lacks an independent identity.
