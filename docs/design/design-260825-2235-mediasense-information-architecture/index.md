---
id: "design-260825-2235-mediasense-information-architecture"
title: "MediaSense Information Architecture"
type: design
status: active
created: 2026-08-25
updated: 2026-08-26
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
| [PreCheck compression boundary](design-260825-2235D-precheck-compression-boundary.md) | active | 2026-08-26 | Defines the accepted Dataset, Result, Source Item, Evidence, and relationship model and records its three-producer pressure test. |
| [PreCheck reference handoff](design-260825-2235C-precheck-reference-handoff.md) | review | 2026-08-26 | Preserves the blocked path-closed fixture reference and adds an assumption-labeled Plan-ready completion variant, without fixing storage or schema. |
| [Information domain map](design-260825-2235A-information-domain-map.md) | active | 2026-08-25 | Defines the governing relations, minimum business concepts, historical traceability, uncertainty boundary, and stopping rule. |
| [Stage ownership](design-260825-2235B-stage-ownership.md) | active | 2026-08-25 | Assigns authoritative homes, producers, consumers, validation, sealing, handoffs, and failure routing across PreCheck, Plan, and Apply. |

No storage-lifecycle or PreCheck implementation module is part of this version. The PreCheck compression boundary is active after human review, and the machine-facing access interface is fixed by the formal [PreCheck Read Contract](../../spec/spec-260826-1546-precheck-read/). The earlier reference handoff remains a review artifact rather than the product contract.

## Authority and discovery path

- [MediaSense Foundation](../design-260823-1918-mediasense-foundation.md) remains authoritative for product purpose, stage invariants, and handoff roles.
- [AI Album Stored Information Inventory](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918D-ai-album-stored-information.md) remains authoritative for the accepted historical inventory and its evidence limits.
- This module is authoritative for the new stage-neutral MediaSense information vocabulary and necessary business relations.
- [Stage ownership](design-260825-2235B-stage-ownership.md) is authoritative for which stage produces, consumes, validates, or seals each concept.
- [PreCheck compression boundary](design-260825-2235D-precheck-compression-boundary.md) is authoritative for PreCheck's accepted compression purpose, minimal handoff concepts and relationships, eight invariants, runtime/storage separation, and three-producer pressure-test judgment.
- [PreCheck Read Contract](../../spec/spec-260826-1546-precheck-read/) is authoritative for the Tool name, machine-readable request and response schemas, stable relationship vocabulary, access outcomes, and Plan development Mock.
- [PreCheck reference handoff](design-260825-2235C-precheck-reference-handoff.md) preserves the concrete blocked and illustrative completion examples that exposed the abstraction problem. It remains review evidence, not an authoritative product shape.

## Accepted PreCheck handoff model

The stable structure is a logical compression model rather than a file or table package:

```text
Dataset
└── referenced by an immutable PreCheck Result
      ├── accounts for Source Items
      ├── exposes low-cost entry Evidence
      └── lets Evidence
            ├── represent Source Items
            ├── derive from Source Items or Evidence
            └── expand toward Source Items or Evidence
```

Mutable working state, reusable work units, SQLite, caches, clustering, thumbnails, metadata categories, and evidence filenames remain replaceable PreCheck implementation details. Only the immutable PreCheck Result crosses into Plan through stable semantics bound to an exact result identity.

## Follow-on sequence

```text
Information Domain Map
  -> Stage Ownership
  -> accepted PreCheck Compression Handoff Model
  -> active PreCheck Read Contract and development Mock
  -> independent PreCheck implementation and later Plan design
```

The primary Plan outcome remains an effective Frozen Organization Plan. A separate diagnostic responsibility has an independent secondary purpose, but its package shape, capture policy, privacy boundary, and retention contract remain deferred until a Plan reference handoff is reviewed.

## Stopping rule

This module stops once the accepted historical information and known gaps have a stage-neutral business disposition, every required new concept has an explicit origin, and no current method has been promoted into a permanent product entity. It does not advance into ownership or storage decisions merely to make the map look implementation-ready.
