---
id: "index-design"
title: "Design Documents"
type: index
status: active
created: 2026-08-23
updated: 2026-09-13
timezone: "Asia/Shanghai"
parent: "index-docs"
depends-on: []
superseded-by: ""
---

# Design Documents

Read the applicable [basic concept model](../model/index.md) before proposing new designs. This directory owns design rationale and implementation choices; the model directory owns the accepted foundational concepts.

| ID | Title | Status | Created | Summary |
| --- | --- | --- | --- | --- |
| [design-260911-1834-manufacturer-information-system](design-260911-1834-manufacturer-information-system.md) | 厂商信息维护体系：能力边界与演进设计 | active | 2026-09-11 | User-selected bundled YAML plus personal overlays; the file contract owns fields and application, with frozen knowledge, actual provenance and evidence in the existing ledger. |
| [design-260910-1726-geo-recovery](design-260910-1726-geo-recovery.md) | Geo 业务阻塞诊断与恢复方案 | implemented | 2026-09-10 | 0.10.0 regional routing, network pause/recovery and cumulative effects implemented; synthetic legacy accounting and isolated installed CLI/MCP verified. Live business recovery remains separate. |
| [design-260830-1626-geo-capability-evolution](design-260830-1626-geo-capability-evolution.md) | MediaSense Geo Capability Evolution | superseded | 2026-09-05 | Historical public-Geo/Plan-enrichment design, superseded when production evidence returned Geo acquisition to PreCheck. |
| [design-260830-1527-reusable-capability-architecture](design-260830-1527-reusable-capability-architecture.md) | MediaSense Reusable Capability Architecture | active | 2026-08-30 | Defines how stage- and business-agnostic capability families progress from reusable kernels through adapters, Tools, Skills, artifacts, and services without speculative entities or lost authority. |
| [design-260829-0038-apply-reference-handoff](design-260829-0038-apply-reference-handoff/) | MediaSense Apply Reference Handoff | review | 2026-08-29 | Preserves the Human-authored direct Plan-to-Apply handoff, lifecycle, trusted Source Set expansion, recovery, verification, and rewind examples. |
| [design-260828-2043-plan-local-artifacts](design-260828-2043-plan-local-artifacts/) | MediaSense Plan Local Artifact Design | active | 2026-08-28 | Defines revisioned Work with optional notes and candidate, immutable Frozen Plan JSON, and the seal response as the direct Apply handoff. |
| [design-260827-0022-precheck-implementation](design-260827-0022-precheck-implementation.md) | MediaSense PreCheck Implementation Design | active | 2026-08-27 | Defines the target local PreCheck runtime, fine-grained reuse and invalidation, Evidence compression, sealing, recovery, resource control, and staged delivery. |
| [design-260825-2235-mediasense-information-architecture](design-260825-2235-mediasense-information-architecture/) | MediaSense Information Architecture | active | 2026-08-25 | Defines objects, relationships, and extensible attributes; representative reading joins own information with compression claims, while contracts own exchange formats. |
| [design-260823-1918-mediasense-foundation](design-260823-1918-mediasense-foundation.md) | MediaSense Foundation | active | 2026-08-23 | Defines stage authority and safety, Plan information sufficiency with open investigation methods, local Agent integration, and contract-first development. |
