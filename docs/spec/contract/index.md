---
id: "index-contract"
title: "MediaSense 当前合约"
type: index
status: active
created: 2026-09-09
updated: 2026-09-10
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260825-2235D-precheck-compression-boundary"
superseded-by: ""
---

# MediaSense 当前合约

**所有新开发从这里开始。** 本目录是 MediaSense 对外合约的唯一当前权威位置。目录名表示接口职责，不表示版本；不要根据历史文件夹的日期选择合约。稳定目录采用用户指定的命名方式，不再创建带日期的平行当前规范。

第一里程碑固定的是开发必须遵守的承诺。**2026-09-09 第一里程碑已完成：验收修订和用户要求的 Observation 校验收尾检查均已通过；第二里程碑暂未通过用户验收；metadata 与历史检测两项已通过复验，2026-09-10 的近上限中间页续读补修已完成验证，整体待复验，原验证证据保留。** 本目录中的 `active` 表示当前规范位置，不表示安装版已通过验收。

## 阅读入口

| 当前合约 | 用途 | 本轮变化 |
| --- | --- | --- |
| [PreCheck Read](precheck-read/index.md) | 分批读取材料路径、自身属性、压缩关系；调查明细和精确成员 | `review.items`、开放属性、选择已准备 Evidence、完整性和失败语义定稿 |
| [PreCheck Run](precheck-run/index.md) | 启动、控制和观察准备过程 | 控制接口沿用；补齐本期准备深度与生产接通要求 |
| [Geo Query](geo-query/index.md) | 有界、受授权的地理候选获取 | 输入和效果语义沿用；明确采集策略与证据投影的责任 |
| [Dataset Open](dataset-open/index.md) | 打开明确的 Dataset | 迁入稳定位置，语义沿用 |
| [Plan Work](plan-work/index.md) | 维护和冻结 Plan | 迁入稳定位置，语义沿用 |
| [Frozen Plan](frozen-plan/index.md) | 冻结后的组织意图 | 迁入稳定位置，Source Set 含义沿用 |
| [组织 Profile](default-organization-profile/index.md) | 默认组织和命名策略 | 迁入稳定位置；明确翻译属于 Plan 判断 |
| [Apply](apply/index.md) | 已冻结计划的执行合约 | 仅迁入稳定位置，本轮不作全量审计 |

## 一份权威，三个表达用途

- `index.md` 解释业务语义、权限、范围、失败及扩展规则。
- `*.tool.json / *.schema.json` 是交换值的唯一机器定义；调用时按 action 校验响应。
- JSONC 是带说明的人工阅读示例，JSON 示例和测试验证合约。示例不是独立规范，也不能用来缩减合约承诺。

[概念模型](../../design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)解释“对象＋关系＋属性”；本目录定义如何调用和读取；[迁移台账](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)记录能力处置及实际完成证据。三者各有职责，不互相复制完整定义。

## 开发与变更规则

1. 实现必须符合此处合约，不得为通过测试而自行删字段、改变归属或放宽承诺。发现矛盾应定位到具体条款，先解决矛盾。
2. 可替换算法、库、存储、并发和内部顺序。可以按已约定规则增加属性；不能用相同属性名改变单位、来源范围、状态或候选性质。
3. 改变公开含义、效果、必需能力或失败行为，需要明确的合约变更及用户授权。已授权的当前里程碑范围内，工程细节由实现者决定。
4. 不保留新旧公开路由、双写或兼容别名。零 API 兼容不表示开发者可以无审阅改变当前承诺。旧 Result 的封存字节保持不变。
5. 旧日期目录与 OpenSpec 旧变更包是历史材料，不是另一套当前规范。已有安装包内的 schema/Skill 副本是该版本发布快照，禁止独立创作。

## 两个里程碑

| 里程碑 | 完成定义 |
| --- | --- |
| 1：合约定稿 | 当前入口唯一；输入、输出、属性义务、准备深度、分页、错误、扩展和迁移处置明确；结构与语义正反例检查通过，并经用户验收 |
| 2：实现完成 | 代码、安装依赖/配置、生产装配、公开入口和返回全部符合当前合约；发布副本同步；相关实现和装配验证通过 |

第一里程碑只固定承诺；第二里程碑已同步生产者、消费者、Host、测试和发布副本，并通过隔离安装验证；整体仍待用户复验。现用环境没有自动升级。验证范围、构建身份和仍未认证事项记录在既有迁移台账；不会保留永久的两套公开协议。

第一里程碑的离线检查入口：`rtk proxy .venv/bin/python -m pytest -q tests/test_contract_authority.py tests/test_precheck_read_contract.py`。它检查合约和合成证据，不运行 PreCheck、模型、地图服务或真实数据端到端验收。
