---
id: "td-260906-2334-mediasense-test-contract"
title: "Research a Fast Test Contract for MediaSense"
type: delegation
status: draft
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "index-delegation"
depends-on:
  - "design-260823-1918-mediasense-foundation"
superseded-by: ""
---

# Research a Fast Test Contract for MediaSense

## Shared purpose and intended use

Determine which parts of Checker SDK's established `make test` entry point and
testing discipline should become a MediaSense development contract. The result
will support one closing judgment: what should MediaSense require in its default
local test gate so it remains comprehensive, maintainable, and comfortably
below a ten-second feedback budget.

## Scope

- Recipient: `team:checker-sdk` through its local workspace route.
- Initiator: `team:mediasense`.
- Engagement: autonomous, read-only research.
- Checker SDK owns the factual account of its current test entry point,
  enforcement, timing evidence, and rationale.
- MediaSense retains the decision about which practices fit its own risks and
  repository structure.
- No implementation or repository-policy change is authorized by this request.

## Confirmed starting facts

- MediaSense is registered as the active virtual Team `team:mediasense`, with
  canonical short name `MediaSense` and a local workspace route.
- Checker SDK is registered as the active virtual Team `team:checker-sdk`, with
  canonical short name `chk.SDK` and a direct-write local workspace route.
- MediaSense currently has no repository `Makefile`.
- MediaSense already uses pytest and Ruff through `pyproject.toml`; pytest has
  opt-in `local_fixture` and `scale` markers.
- The requester recalls that Checker SDK has both a `make test` entry point and
  a broader testing discipline, including a preference that files stay within
  roughly 400 lines and that the default suite finish well below 10 seconds.
  The exact source, wording, enforcement, exceptions, and current measured
  behavior remain to be verified.

## Unresolved questions

- What does Checker SDK's current `make test` actually execute, and which
  checks are part of its default developer gate?
- Where are its testing and source-size rules authoritative, and how are they
  enforced rather than merely described?
- Is the roughly 400-line rule a hard gate, a review heuristic, or a scoped
  exception policy?
- What is the current reproducible runtime of `make test`, and what keeps it
  below the intended feedback budget?
- Which parts are reusable principles, and which are specific to Checker SDK's
  language, architecture, fixtures, or risk profile?
- What is the smallest credible MediaSense contract to evaluate next, without
  prematurely implementing it?

## Closing and acceptance criteria

- The raw result cites current Checker SDK files and runnable evidence, not
  memory alone.
- It explains the `make test` dependency chain, test tiers, determinism rules,
  file-size policy, timing budget, enforcement, and exceptions.
- It includes current timing evidence or a precise reason measurement was not
  safe or possible.
- It distinguishes reusable principles from Checker SDK-specific mechanisms.
- It recommends a bounded MediaSense candidate contract while leaving final
  adoption and implementation to MediaSense.
- The research changes neither repository.

## Request and result inventory

| Request | Recipient | Result | Status |
| --- | --- | --- | --- |
| [01-request-checker-sdk](01-request-checker-sdk.md) | `team:checker-sdk` | [01-result-checker-sdk](01-result-checker-sdk.md) | prepared for autonomous delivery |

## Material handoff evidence

- 2026-09-06 23:34 Asia/Shanghai — The user asked MediaSense to confirm its
  registered identity and research Checker SDK's `make test`, source-file size
  discipline, and sub-ten-second feedback target before considering changes.

