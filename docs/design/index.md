---
id: "index-design"
title: "Design Documents"
type: index
status: active
created: 2026-08-23
updated: 2026-09-17
timezone: "Asia/Shanghai"
parent: "index-docs"
depends-on: []
superseded-by: ""
---

# Design Documents

Read the applicable [basic concept model](../model/index.md) before proposing new designs. This directory owns design rationale and implementation choices; the model directory owns the accepted foundational concepts.

| ID | Title | Status | Created | Summary |
| --- | --- | --- | --- | --- |
| [design-260917-1150-apply-safety-efficiency](design-260917-1150-apply-safety-efficiency.md) | Apply 的目的、安全与效率：已选 B 方案及开发交接 | review | 2026-09-17 | 用户已选 B：轻量核验、逐项持久化，修复来源与授权缺口；明确相对现状的效率收益和完整字节检测取舍，保留正式业务接口；本地源码及隔离 wheel 已开发验证，证据见设计 §11；未发布或安装。 |
| [design-260915-1519-plan-view-lifecycle](design-260915-1519-plan-view-lifecycle.md) | Plan 预览生命周期：自动交付与资源回收 | active | 2026-09-15 | 设计已定稿并按授权实施：轻路由、重上下文回收、自动退出、版本隔离和诊断清理；源码／隔离构建及图片／慢读取补修证据见实施记录，未发布或切换日常安装。 |
| [design-260915-1244-plan-preview-simplification](design-260915-1244-plan-preview-simplification.md) | Plan 整理结果浏览：设计计划 | review | 2026-09-15 | 分组浏览已实现并获用户观感认可，源码、隔离构建及浏览器验证见文末，未发布；后续生命周期见专门设计。[生产记录](design-260915-1244-plan-preview-simplification.reasoning.md)归属于本计划。 |
| [design-260914-1450-precheck-execution-efficiency](design-260914-1450-precheck-execution-efficiency.md) | PreCheck工具执行效率工程设计 | review | 2026-09-14 | 限定连接复用、Store批量操作、准备/结果数据访问和验证器复用；按S0–S5验证正确性并最终实测，无强制提速门槛，尚未开发。 |
| [design-260911-1834-manufacturer-information-system](design-260911-1834-manufacturer-information-system.md) | 厂商信息维护体系：能力边界与演进设计 | active | 2026-09-11 | User-selected bundled YAML plus personal overlays; the file contract owns fields and application, with frozen knowledge, actual provenance and evidence in the existing ledger. |
| [design-260910-1726-geo-recovery](design-260910-1726-geo-recovery.md) | Geo 业务阻塞诊断与恢复方案 | implemented | 2026-09-10 | 0.10.0 regional routing, network pause/recovery and cumulative effects implemented; synthetic legacy accounting and isolated installed CLI/MCP verified. Live business recovery remains separate. |
| [design-260830-1626-geo-capability-evolution](design-260830-1626-geo-capability-evolution.md) | MediaSense Geo Capability Evolution | superseded | 2026-09-05 | Historical public-Geo/Plan-enrichment design, superseded when production evidence returned Geo acquisition to PreCheck. |
| [design-260830-1527-reusable-capability-architecture](design-260830-1527-reusable-capability-architecture.md) | MediaSense Reusable Capability Architecture | active | 2026-08-30 | Defines how stage- and business-agnostic capability families progress from reusable kernels through adapters, Tools, Skills, artifacts, and services without speculative entities or lost authority. |
| [design-260829-0038-apply-reference-handoff](design-260829-0038-apply-reference-handoff/) | MediaSense Apply Reference Handoff | review | 2026-08-29 | Preserves the Human-authored direct Plan-to-Apply handoff, lifecycle, trusted Source Set expansion, recovery, verification, and rewind examples. |
| [design-260828-2043-plan-local-artifacts](design-260828-2043-plan-local-artifacts/) | MediaSense Plan Local Artifact Design | active | 2026-08-28 | Defines revisioned Work with optional notes and candidate, immutable Frozen Plan JSON, and the seal response as the direct Apply handoff. |
| [design-260827-0022-precheck-implementation](design-260827-0022-precheck-implementation.md) | MediaSense PreCheck Implementation Design | active | 2026-08-27 | Defines the target local PreCheck runtime, fine-grained reuse and invalidation, Evidence compression, sealing, recovery, resource control, and staged delivery. |
| [design-260825-2235-mediasense-information-architecture](design-260825-2235-mediasense-information-architecture/) | MediaSense Information Architecture | active | 2026-08-25 | Defines objects, relationships, and extensible attributes; representative reading joins own information with compression claims, while contracts own exchange formats. |
| [design-260823-1918-mediasense-foundation](design-260823-1918-mediasense-foundation.md) | MediaSense Foundation | active | 2026-08-23 | Defines stage authority and safety, Plan information sufficiency with open investigation methods, local Agent integration, and contract-first development. |
