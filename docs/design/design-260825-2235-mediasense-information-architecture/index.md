---
id: "design-260825-2235-mediasense-information-architecture"
title: "MediaSense Information Architecture"
type: design
status: active
created: 2026-08-25
updated: 2026-09-09
timezone: "Asia/Shanghai"
parent: "index-design"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "eval-260823-1918D-ai-album-stored-information"
superseded-by: ""
tags: ["mediasense", "information-architecture", "domain-model"]
---

# MediaSense Information Architecture

## Question and decision

This module answers one question:

> What stage-neutral business information must MediaSense understand in order to account for a large source collection, preserve coverage-constrained evidence, freeze an effective organization decision, and verify its execution?

The answer is a business information map, not a schema. It fixes the meanings and authority boundaries that later handoff designs must preserve while leaving storage, algorithms, models, Agent reasoning, and orchestration open.

AI Album contributes historical capability and failure evidence only. Its cache names, flags, file patterns, directory layout, and evaluation identifiers are not MediaSense product vocabulary.

## Modules

| Module | Status | Created | Summary |
| --- | --- | --- | --- |
| [PreCheck compression boundary](design-260825-2235D-precheck-compression-boundary.md) | active | 2026-08-26 | Defines objects, relationships, and extensible attributes; separates representative information from compression claims without creating new entities. |
| [PreCheck reference handoff](design-260825-2235C-precheck-reference-handoff.md) | review | 2026-08-26 | Preserves the blocked path-closed fixture reference and adds an assumption-labeled Plan-ready completion variant, without fixing storage or schema. |
| [Information domain map](design-260825-2235A-information-domain-map.md) | active | 2026-08-25 | Defines the governing relations, minimum business concepts, historical traceability, uncertainty boundary, and stopping rule. |
| [Stage ownership](design-260825-2235B-stage-ownership.md) | active | 2026-08-25 | Assigns authoritative homes, producers, consumers, validation, sealing, handoffs, and failure routing across PreCheck, Plan, and Apply. |

The conceptual model is active after Human review. The formal [PreCheck Read Contract](../../spec/contract/precheck-read/) owns the finalized exchange schema; implementation and release synchronization are tracked separately as milestone two. Model acceptance does not activate a new API or certify its implementation. The earlier reference handoff remains historical review evidence.

## Authority and discovery path

- [MediaSense Foundation](../design-260823-1918-mediasense-foundation.md) remains authoritative for product purpose, stage invariants, and handoff roles.
- [AI Album Stored Information Inventory](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918D-ai-album-stored-information.md) remains authoritative for the accepted historical inventory and its evidence limits.
- This module is authoritative for the new stage-neutral MediaSense information vocabulary and necessary business relations.
- [Stage ownership](design-260825-2235B-stage-ownership.md) is authoritative for which stage produces, consumes, validates, or seals each concept.
- [PreCheck compression boundary](design-260825-2235D-precheck-compression-boundary.md) is authoritative for PreCheck's accepted compression purpose, minimal handoff concepts and relationships, eight invariants, runtime/storage separation, and three-producer pressure-test judgment.
- [PreCheck Read Contract](../../spec/contract/precheck-read/) is authoritative for the Tool name, machine-readable request and response schemas, stable relationship vocabulary, access outcomes, and Plan development Mock.
- [Frozen Plan Contract](../../spec/contract/frozen-plan/) is authoritative for the immutable Human-confirmed organization handed to Apply.
- [Apply Contract](../../spec/contract/apply/) is authoritative for the Run, Receipt, authorization, execution, recovery, and verification boundary.
- [PreCheck reference handoff](design-260825-2235C-precheck-reference-handoff.md) preserves the concrete blocked and illustrative completion examples that exposed the abstraction problem. It remains review evidence, not an authoritative product shape.

## Accepted PreCheck handoff model

The stable structure is **objects + relationships + attributes**. Dataset and Result bind the subject and immutable observation boundary; Source Items and Evidence have their own identities and access. Attributes describe an identified object or relationship without fixing today's metadata categories:

```text
PreCheck Result — references one Dataset
├── Source Items: identity, locator, attributes
├── Evidence: identity, access, attributes
└── relationships: endpoints, meaning, attributes
```

The five relationship meanings remain `accounts_for`, `entry_evidence`, `represents`, `derived_from`, and `expands_to`. Representative is a role; attributes and relationships need no additional identity. A representative read brings together **its own information and its compression relationships**, without fetching all represented members' detail by default. Image access may be a path; the Agent decides whether to open it.

The [compression boundary](design-260825-2235D-precheck-compression-boundary.md) is the single authority for these meanings, extension rules, examples, and limits. It does not require a new `attributes` wire field or replace existing Observations. Mutable Work, caches, algorithms, storage, and processing order remain implementation choices.

## Follow-on sequence

```text
Information Domain Map
  -> Stage Ownership
  -> accepted PreCheck Compression Handoff Model
  -> active PreCheck Read Contract and development Mock
  -> active PreCheck, Plan, and Apply contracts and implementations
```

The primary Plan outcome remains an effective Frozen Organization Plan. A separate diagnostic responsibility has an independent secondary purpose, but its package shape, capture policy, privacy boundary, and retention contract remain deferred until a Plan reference handoff is reviewed.

## Stopping rule

This module stops once the accepted historical information and known gaps have a stage-neutral business disposition, every required new concept has an explicit origin, and no current method has been promoted into a permanent product entity. It does not advance into ownership or storage decisions merely to make the map look implementation-ready.
