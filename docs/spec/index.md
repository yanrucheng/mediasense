---
id: "index-spec"
title: "Specifications"
type: index
status: active
created: 2026-08-26
updated: 2026-09-09
timezone: "Asia/Shanghai"
parent: "index-docs"
depends-on: []
superseded-by: ""
---

# Specifications

**唯一当前合约入口：[contract/](contract/index.md)。** 所有新开发从这里开始。日期目录是历史记录，日期不是接口版本，也不用于选择最新规范。

[概念模型](../design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)固定对象、关系与属性；稳定合约固定请求、返回与失败语义；[迁移台账](../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)记录实现和验收。第一里程碑已完成；第二里程碑于 2026-09-10 经用户验收通过，以 0.9.0 发布。

## 当前规范

| 目录 | 状态 | 用途 |
| --- | --- | --- |
| [contract/](contract/index.md) | active | 唯一当前合约，按接口职责组织；实现版本是否已符合另行标明 |

## 历史记录

以下目录保留曾经发布或审阅的内容，不与 contract 并列有效。历史 schema 供旧版本证据和测试复核，不能作为新开发依据。

| 历史文档 | 状态 | 当前入口 |
| --- | --- | --- |
| [260907 PreCheck 讨论草图](spec-260907-0247-precheck-plan-handoff/index.md) | superseded | [当前合约](contract/index.md) |
| [260831 Dataset Open](spec-260831-0009-dataset-open/index.md) | superseded | [Dataset Open](contract/dataset-open/index.md) |
| [260830 Geo Query](spec-260830-2034-geo-query/index.md) | superseded | [Geo Query](contract/geo-query/index.md) |
| [260829 Apply](spec-260829-0050-apply/index.md) | superseded | [Apply](contract/apply/index.md) |
| [260828 Organization Profile](spec-260828-2026-default-organization-profile/index.md) | superseded | [Organization Profile](contract/default-organization-profile/index.md) |
| [260827 PreCheck Run](spec-260827-1915A-precheck-run/index.md) | superseded | [PreCheck Run](contract/precheck-run/index.md) |
| [260827 Plan Work](spec-260827-1915B-plan-work/index.md) | superseded | [Plan Work](contract/plan-work/index.md) |
| [260827 Frozen Plan](spec-260827-1138-frozen-plan/index.md) | superseded | [Frozen Plan](contract/frozen-plan/index.md) |
| [260826 PreCheck Read](spec-260826-1546-precheck-read/index.md) | superseded | [PreCheck Read](contract/precheck-read/index.md) |
