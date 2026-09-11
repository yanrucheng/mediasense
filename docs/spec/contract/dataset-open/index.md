---
id: "dataset-open"
title: "MediaSense Dataset Open Tool Contract"
type: spec
status: active
created: 2026-08-31
updated: 2026-09-12
timezone: "Asia/Shanghai"
parent: "index-contract"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
superseded-by: ""
---

# MediaSense Dataset Open Tool Contract

本页位于稳定合约目录。当前规范以此处为准；迁移到此目录本身不构成新的实现或真实数据验收。


## Purpose and status

`mediasense.dataset.open` resolves or creates one exact Dataset workspace for a
media source without reading or modifying the source media. It is the installed
product entry point that lets long-running derived work remain associated with
the Dataset while keeping application configuration and credentials separate.

This directory is the active authority for the Dataset Open Tool contract and
its reviewable example.

## Workspace selection

The Tool uses one deterministic precedence order:

1. a workspace path explicitly supplied by the user;
2. `<external-volume>/.mediasense/datasets/` when the source belongs to an
   eligible external volume; or
3. the platform-appropriate local application-data directory.

The response always reports the selected workspace, selection tier, effective
non-secret configuration provenance, manifest version, and component store
versions. A corrupt or incompatible higher-priority workspace is reported rather
than silently bypassed.

`configuration.local_embedding` reports disabled/configured state, reason and the
effective pinned local profile. `execution=not_checked` explicitly avoids claiming
that configuration proves model execution or semantic compression. Local model
downloads are disabled. The existing PreCheck Work records and sealed Dataset
context own execution, reuse and failure facts; this Tool owns configuration
discovery only. No new model registry or model-facing Tool is introduced.

## Identity and safety

`configuration.metadata` reports `assumed_timezone`, `output_timezone`, and a
manufacturer-knowledge summary: canonical identity, source document identities,
active rule IDs, `overridden_rules` linking user replacements to their bundled
origins, and explicit disabled rules with their original and user sources.
Its `execution=not_checked` means files validated, not that a rule has processed
media. The [manufacturer file contract](../manufacturer-knowledge/index.md) owns
authoring and overlay semantics. A new PreCheck Run freezes full knowledge in its
existing store; this discovery response does not duplicate the full catalog.


The Dataset manifest binds the source locator to observed source and volume
identity. A compatible mount-path change may reuse verified work; an identity
mismatch blocks automatic reuse, and an explicit rebind begins a separately
audited reuse domain. Workspace creation is atomic and reopening the same Dataset
is idempotent.

The Tool owns Dataset resolution only. PreCheck, Plan, and Apply retain their
existing stage contracts and effect boundaries. The stage-neutral Geo Tool owns a
separately versioned Dataset journal for effect idempotency; PreCheck Result and
Plan Working State remain authoritative for their own projected facts and
decisions.

## Files

- [`dataset-open.tool.json`](dataset-open.tool.json) — callable input and output
  contract.
- [`dataset-open.mock.json`](dataset-open.mock.json) — external-volume selection
  example.
