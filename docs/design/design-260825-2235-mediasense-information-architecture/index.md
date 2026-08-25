---
id: "design-260825-2235-mediasense-information-architecture"
title: "MediaSense Information Architecture"
type: design
status: active
created: 2026-08-25
updated: 2026-08-25
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
| [Information domain map](design-260825-2235A-information-domain-map.md) | active | 2026-08-25 | Defines the governing relations, minimum business concepts, historical traceability, uncertainty boundary, and stopping rule. |
| [Stage ownership](design-260825-2235B-stage-ownership.md) | review | 2026-08-25 | Assigns authoritative homes, producers, consumers, validation, sealing, handoffs, and failure routing across PreCheck, Plan, and Apply. |

No storage-lifecycle, schema, or implementation module is part of this version. Stage ownership remains under human review and does not yet authorize downstream contract work.

## Authority and discovery path

- [MediaSense Foundation](../design-260823-1918-mediasense-foundation.md) remains authoritative for product purpose, stage invariants, and handoff roles.
- [AI Album Stored Information Inventory](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918D-ai-album-stored-information.md) remains authoritative for the accepted historical inventory and its evidence limits.
- This module is authoritative for the new stage-neutral MediaSense information vocabulary and necessary business relations.
- [Stage ownership](design-260825-2235B-stage-ownership.md) is the review candidate for which stage produces, consumes, validates, or seals each concept; it becomes authoritative only after human acceptance and lifecycle activation.

## Preserved projection input

The reviewed PreCheck projection candidate is retained as downstream design input:

```text
PreCheck Result
├── Result Manifest
├── Source Account
├── Evidence Base
└── Coverage Map
```

It also retains the reviewed separation between a mutable Working Run and a new immutable Sealed Result, the fully offline `plan-ready` boundary, and local content-sensitivity evidence separated from Plan's VLM policy. This is not yet a formal PreCheck contract or schema.

## Follow-on sequence

```text
Information Domain Map
  -> Stage Ownership (current review)
  -> reviewed stage handoff examples and projections
  -> Storage Lifecycle
  -> minimal formal contracts
  -> Tools and Skills
```

The primary Plan outcome remains an effective Frozen Organization Plan. A separate diagnostic responsibility has an independent secondary purpose, but its package shape, capture policy, privacy boundary, and retention contract remain deferred until a Plan reference handoff is reviewed.

## Stopping rule

This module stops once the accepted historical information and known gaps have a stage-neutral business disposition, every required new concept has an explicit origin, and no current method has been promoted into a permanent product entity. It does not advance into ownership or storage decisions merely to make the map look implementation-ready.
