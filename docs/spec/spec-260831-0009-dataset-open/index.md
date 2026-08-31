---
id: "spec-260831-0009-dataset-open"
title: "MediaSense Dataset Open Tool Contract"
type: spec
status: active
created: 2026-08-31
updated: 2026-08-31
timezone: "Asia/Shanghai"
parent: ""
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
superseded-by: ""
---

# MediaSense Dataset Open Tool Contract

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

## Identity and safety

The Dataset manifest binds the source locator to observed source and volume
identity. A compatible mount-path change may reuse verified work; an identity
mismatch blocks automatic reuse, and an explicit rebind begins a separately
audited reuse domain. Workspace creation is atomic and reopening the same Dataset
is idempotent.

The Tool owns Dataset resolution only. PreCheck, Plan, Geo, and Apply retain their
existing stage contracts and effect boundaries.

## Files

- [`dataset-open.tool.json`](dataset-open.tool.json) — callable input and output
  contract.
- [`dataset-open.mock.json`](dataset-open.mock.json) — external-volume selection
  example.
