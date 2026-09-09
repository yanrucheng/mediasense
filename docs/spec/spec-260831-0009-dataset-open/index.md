---
id: "spec-260831-0009-dataset-open"
title: "MediaSense Dataset Open Tool Contract"
type: spec
status: superseded
created: 2026-08-31
updated: 2026-09-09
timezone: "Asia/Shanghai"
parent: ""
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
superseded-by: "dataset-open"
---

# MediaSense Dataset Open Tool Contract

> **历史记录，已退出当前规范。** 唯一当前合约在 [contract/dataset-open](../contract/dataset-open/index.md)。本目录的文字、schema 和示例保留为旧版本证据，不用于新开发；包内旧副本也不能替代新合约。


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
