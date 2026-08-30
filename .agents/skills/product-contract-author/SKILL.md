---
name: "product-contract-author"
description: "Use only when the user explicitly names `product-contract-author`."
version: "0.1.0"
activation: "explicit"
context-load: "light"
channels: [public]
---

# Product Contract Author

## Purpose

Write or review the current contract and contract changes of a product form so a
competent third-party human can understand, judge, use, or continue the product
without learning its internal production, implementation, design history, or
document-production process.

A product form is the externally meaningful shape of a result, artifact, capability,
service, interface, workflow, policy, or other delivered product. Its contract may
govern purpose achievement, required semantic properties, behavior, composition,
boundaries, responsibilities, and observable acceptance evidence. It is not limited
to APIs or software products. A third party is any intended reader who did not
participate in producing the product and should not need that internal context; they
need not be external to the organization.

## Authority

This Skill owns reusable criteria for producing third-party product contracts. It
does not own any product's purpose, facts, policy, compatibility promise, acceptance
standard, or documentation topology. Discover the authorities for the governed
product form and for the contract artifact before writing. Use intent sources,
implementation, schemas, tests, observed behavior, policy, and design history as
evidence according to their real authority; do not silently promote any one of them
into the product contract.

Keep one discoverable authority for the current contract. A change artifact may
describe a transition, but it must not become a competing current truth. When a
change takes effect, reconcile the authoritative current contract. Keep proposals,
history, rejected alternatives, and design rationale in artifacts that own those
lifecycles.

## Required Downstream Product

The downstream product of this Skill is a human-usable current contract or contract
change. It must anchor the governed product form: the purpose it must achieve, the
semantic properties and boundaries every acceptable instance must satisfy, and the
evidence by which intended third-party readers can recognize and rely on it. Judge
the contract by whether it makes the actual governed product entrustable, not by the
apparent completeness of the document.

Derive coverage from the material relationships between the product and those
readers and from the relations by which the product fulfills its purpose. Depending
on the product, these may include required contents or qualities, concepts and
states, accessible capabilities, inputs or preconditions, defaults and selection,
outputs, evidence, effects, ordering, failures, partial outcomes, limits,
responsibilities, decision rights, composition, and compatibility. Do not add a
section or concept merely because it appears in this list.

A relation is material when omitting it could change whether the product fulfills
its purpose or change a third party's recognition, use, interpretation, action,
trust, responsibility, compatibility judgment, or decision to stop. Expose the
product-native relations on which those judgments depend. For example:

```text
condition -> behavior -> result or effect -> permitted interpretation
source or evidence -> claim -> confidence or applicability boundary
role -> responsibility -> handoff -> remaining decision right
input or prior state -> transformation -> resulting product state
```

These are possible relations, not a universal model. Use whichever structure makes
the governed product's material semantics inspectable without requiring the reader
to reconstruct a missing link.

Fix the third-party-facing semantics and real invariants. Leave document shape,
investigation, reasoning, notation, examples, modularity, and authoring sequence
open.

## Write for the Third-Party Human

State the resulting product directly. A reader should not have to pass through how
the author gathered evidence, organized sources, chose the document shape, debated
alternatives, or arrived at a decision. Do not use production structure,
implementation structure, or internal vocabulary as the contract's organizing model
unless it is itself public and consequential.

Hide production and implementation mechanisms; do not hide their consequences.
Retain such information only when it changes what the third party may observe, rely
on, interpret, or do.
Retain reasons only when the causal fact is needed to understand an outcome, judge
applicability or trust, or choose an action. Separate that from internal rationale
for why the product was designed that way.

Prefer contract voice:

```text
Omitting selection fails. An empty selection also fails.
```

Do not replace it with production voice:

```text
After considering several options, this version chooses explicit selection because
the team found implicit defaults confusing.
```

Do not make the reader inspect source materials, source code, or design records to
discover the product's ordinary contract. Link outward for production detail,
implementation detail, evidence, history, or specialized reference material that is
not needed in the normal reading path.

## Make Semantics Interpretable

Define not only the visible shape of the product but its inference and use
boundaries. Make clear what a claim, field, state, result, absence, error, effect, or
other consequential element means; what it does not mean; and which combinations
change the reader's permitted interpretation or action. Do not let one public term
silently carry multiple independent meanings.

Distinguish materially different conditions even when their serialized or visible
forms appear similar. Cover defaults, no-ops, skipped work, invalid states, failures,
partial success, ordering, and residual effects when they can alter reliance. Do not
claim completeness merely because every field has been listed.

State decision boundaries without absorbing the third party's policy. Specify what
the product establishes, decides, or guarantees and what remains for the reader to
choose. Do not turn author preference, recommended usage, or a convenient
presentation into a mandatory product rule.

## Expose Material Contrast

When easily confused cases lead to different use, interpretation, effects, actions,
or responsibilities, make the contrast directly visible to a human reader. A good
contrast places the cases together, varies the decision-bearing condition clearly,
and shows the resulting behavioral or interpretive difference.

Contrast examples are semantic witnesses, not necessarily machine-readable samples,
schemas, or test fixtures. They may omit irrelevant fields or use explanatory values
when that makes the product behavior easier to see. Optimize them for immediate
human discrimination, not executability.

For example, if these are the product's actual semantics, show the relation rather
than giving one isolated payload:

| Case | Product meaning | Consequence |
| --- | --- | --- |
| Value omitted | No value was supplied | Default or missing-value behavior applies |
| Empty value supplied | A value was supplied and is empty | Empty-value behavior applies |
| Invalid value supplied | A supplied value violates the contract | Error behavior applies |

Do not require an example for every rule. Require visible contrast where a plausible
confusion could materially change reliance. If the reader must mentally combine
distant definitions to discover the difference, the contrast is not yet doing its
job.

## Current Contracts and Contract Changes

For a current contract, present the settled product form applicable under its stated
status and conditions. Keep future possibilities, migration history, and superseded
forms out of the normal path unless they remain necessary to recognize or use the
current product. Distinguish a proposed or approved future contract from a contract
that already governs current products.

For a contract change, make the transition itself usable by third parties. State:

- the affected purpose, semantic property, boundary, promise, or product form;
- the before and after semantics, using direct human-readable contrast when the
  difference is not immediately evident;
- the readers, uses, states, or artifacts to which the change applies;
- guarantees that remain unchanged and guarantees that no longer hold;
- the effective condition, compatibility boundary, and required third-party action
  when material; and
- where the reconciled current contract is or will become authoritative.

Describe downstream obligations and available choices, but do not prescribe the
reader's internal implementation unless the product contract legitimately owns that
method. Do not narrate the author's change process in place of the changed product.

## Boundaries

Do not turn the contract into:

- a PRD describing desired outcomes without establishing the governed product form
  and its applicability;
- a technical design explaining internal architecture and trade-offs;
- an API or content inventory that lists parts without their product, behavioral,
  and interpretive semantics;
- a runbook prescribing an operator's internal procedure;
- a changelog that names differences without defining their consequences; or
- a reasoning log containing research, drafting, review, or decision history.

The contract may link to or coexist with these artifacts. Add or split an artifact
only when it has an independent audience, authority, loading condition, or
lifecycle.

## Acceptance

Reject or revise the result when an intended third-party reader cannot determine,
to the extent material to the product:

- what product form and boundary the contract governs;
- what purpose the governed product must achieve and how acceptable products can be
  recognized;
- what the product currently establishes or promises and explicitly does not decide
  or guarantee;
- how relevant conditions and relations lead to contents, qualities, behavior,
  results, evidence, effects, or failures;
- how to interpret contracted information without inventing meaning from absence,
  internal detail, or author preference;
- what remains true after no-op, skip, error, or partial success;
- which consequential decisions and responsibilities remain with the reader;
- how materially confusable cases differ in actual product semantics or
  consequences; and
- for a change, what differs, who or what is affected, what remains stable, when it
  applies, and what action is required.

Also reject or revise when the reader must inspect production or implementation or
reconstruct material design reasoning to use the ordinary product contract, when
examples are decorative rather than contrastive, when internal rationale displaces
the governed product, or when document completeness is mistaken for product-form
completeness.
