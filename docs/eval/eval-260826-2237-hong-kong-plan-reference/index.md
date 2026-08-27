---
id: "eval-260826-2237-hong-kong-plan-reference"
title: "Hong Kong Bounded Plan Reference Instance"
type: eval
status: review
created: 2026-08-26
updated: 2026-08-26
timezone: "Asia/Shanghai"
parent: "index-eval"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
  - "spec-260826-1546-precheck-read"
  - "eval-260823-1918-ai-album-migration-baseline"
superseded-by: ""
tags: ["plan", "reference-instance", "hong-kong", "handoff"]
---

# Hong Kong Bounded Plan Reference Instance

This review module contains a manually authored example of a bounded Plan handoff. It is not a Plan contract, schema, Tool, Skill, runtime output, or execution authorization.

## Open this first

- [`plan-reference.yaml`](plan-reference.yaml) is the single authoritative candidate instance in this module. It is explicitly marked `human-authored reference instance`; its field names and YAML form are provisional.
- The upstream read surface is the [PreCheck Read Contract](../../spec/spec-260826-1546-precheck-read/) and its [Hong Kong development Mock](../../spec/spec-260826-1546-precheck-read/hong-kong.mock.json).
- Product boundaries come from the [MediaSense Foundation](../../design/design-260823-1918-mediasense-foundation.md) and [Information Architecture](../../design/design-260825-2235-mediasense-information-architecture/).
- Fixture facts and migration comparison are bounded by the [AI Album migration baseline](../eval-260823-1918-ai-album-migration-baseline/) and the tracked [fixture descriptor](../../../eval/fixtures/ai-album-hk-representative-v1.yaml).

The package's standard verifier passed before this instance was written: manifest hashes, declared counts, cache inventory, media-path existence, and normalized production/replay output all passed. No fresh replay, remote model, or paid API was used.

## How to read the claims

| Label | Authority in this module |
| --- | --- |
| `precheck_observation` | Returned by a listed legal `mediasense.precheck.read` Mock exchange bound to the exact Result. |
| `semantic_claim` | A challengeable Plan interpretation, never promoted to observed fact. |
| `agent_judgment` | The proposed organization decision and its stated boundary. |
| `illustrative_user_confirmation` | A fabricated, precisely scoped confirmation used only to test a frozen handoff. It is not actual authorization from the repository owner. |
| `fixture_fact` | Direct package evidence used to audit plausibility, not hidden Plan input. |
| `illustrative_assumption` | A review convenience that must not be treated as observed fact or runtime output. |

The candidate freezes only seven Source Items: `13`, `14`, `15`, `211`, `215`, `216`, and `217`. Every other item in the 224-path Result, the unpaged remainder of bundle 61, and the rest of the 2,136-item fixture source-media population are outside this Plan.

## Regenerable target view

This tree is derived from `plan-reference.yaml`; it is not a second authority.

```text
hong-kong-food-trip-bounded-review/
├── 01-restaurant-table-sequence/
│   ├── 001--source-13--{source_basename}
│   ├── 002--source-14--{source_basename}
│   └── 003--source-15--{source_basename}
├── 02-restaurant-people-moment/
│   └── 001--source-211--{source_basename}
└── 03-recovered-camera-clip-variants/
    ├── 001--source-216--{source_basename}
    └── 002--source-217--{source_basename}

no materialized output: source-item:215
```

## Review focus

The example deliberately tests three pressure points:

1. Bundle 61's food-only entry Evidence represents 201 items but hides a person visible at `source-item:211`; the illustrative decision splits only four exact Source Items and makes no claim about the other 197.
2. The invalid item, patched source, and readable missing-time remux remain three identities. The plan copies the two candidate variants, preserves the invalid source in place without output, and does not claim content identity or invent a timestamp.
3. Apply receives exact unit membership, names, order, copy rules, collision refusal, preconditions, and a no-op disposition. It has no semantic choice left, but execution remains unauthorized because all confirmations are illustrative.

The most material review questions are:

1. Is the exact split `13/14/15` versus `211`, including both names, an acceptable example of scoped confirmation without generalizing to all of bundle 61?
2. Should a frozen example retain both `216` and `217` as ordered recovery variants while giving `215` an explicit no-output disposition, or should one readable variant also be excluded?
3. Is source-reference resolution plus a frozen basename-preserving target rule sufficiently deterministic for Apply, given that this development Mock omits direct `inspect` examples for `14`, `15`, `211`, and `216`?

