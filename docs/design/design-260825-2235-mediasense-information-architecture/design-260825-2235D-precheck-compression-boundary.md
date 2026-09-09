---
id: "design-260825-2235D-precheck-compression-boundary"
title: "MediaSense PreCheck Compression Boundary"
type: design
status: active
created: 2026-08-26
updated: 2026-09-09
timezone: "Asia/Shanghai"
parent: "design-260825-2235-mediasense-information-architecture"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235A-information-domain-map"
  - "design-260825-2235B-stage-ownership"
  - "eval-260823-1918D-ai-album-stored-information"
  - "clarify-260826-1819-precheck-contract-concepts"
superseded-by: ""
tags: ["mediasense", "precheck", "compression", "handoff-boundary"]
---

# PreCheck：对象、关系与属性

## 状态与权威

本页是已经过用户确认的 PreCheck 概念模型。它固定对象、关系、属性的含义，以及为什么需要它们；具体请求、返回和错误由[正式 Read 合约](../../spec/contract/precheck-read/index.md)维护。概念模型的确认不代表下一版接口已经发布，也不代表相关能力已经实现。

2026-09-09 的确认收敛为两层：**模型采用“对象＋关系＋属性”，阅读采用“代表自身信息＋压缩关系”。** `attributes` 是概念用语，不要求重命名现有 `observations`，也不另建属性注册表、文件或服务。

本页不定义数据库结构或处理流水线。后文保留的历史压力测试说明模型的适用范围，不认证当前安装版、真实数据质量或某个具体算法。

## 为什么需要这个模型

PreCheck 要用可控的本地计算和有限获取，把大量素材变成较少、较便宜的阅读入口，同时保留返回源素材的路径。Plan 再解释内容、质疑证据、分组和命名。

由这个目的产生两个问题：

1. **正在读什么？** 代表材料、它的实际来源以及关于它们的信息。
2. **因此暂时少读了什么？** 被代表的素材，以及这项压缩的依据和限制。

这两个问题需要不同关系，但可以共享信息和计算。坐标可以参与压缩，也可以帮助 Plan 解释画面；metadata 或 embedding 可以先于某一轮压缩计算。它们不是互斥信息类别，也不规定所有信息必须在压缩之后获取。

## 模型骨架

```text
PreCheck Result — 绑定一个 Dataset 和一次固定的来源范围
├── 源条目 Source Items
│   ├── 身份、定位
│   └── attributes：关于该源条目的信息
├── 证据材料 Evidence
│   ├── 身份、读取入口
│   └── attributes：关于该材料的信息
└── 关系 Relationships
    ├── 连接谁、关系含义
    └── attributes：关于该关系的信息
```

这是一张含义图，不是要求把全量对象树返回给 Agent，也不是三份必须存在的文件。Result 本身也可保留属于它的限定和效果证据。身份、边界、关系端点及授权语义不能被降为任意属性。

### 哪些概念需要独立身份

| 概念 | 稳定目的与权威 | 删除后的损失 |
| --- | --- | --- |
| Dataset | 用户或产品定义的持续素材集合，例如“香港旅行素材”；路径变化不自动改变集合身份 | 无法理解多次预检是在处理同一个持续变化的集合 |
| Result | PreCheck 发布的一次不可变结果，固定该次范围、观测和关系；通过确切引用读取 | Plan 会依赖不断变化的最新状态，无法复核当时依据 |
| Source Item（源条目） | Result 直接交代的具体来源对象，保留身份与定位；可以是照片、视频、GPX、侧车、排除项或损坏项 | 观测和覆盖无法指向同一来源，未选中或损坏的素材可能消失 |
| Evidence（证据材料） | 可读取的表达，便于低成本查看素材；可以是缩略图、视频帧、联系表、文字、结构化内容或直接复用源条目 | 原文件与派生材料混淆，清晰度、采样和来源无法分别交代 |

Source Item 是来源对象的统称，不是在照片之上再制造一层业务对象。Evidence 不要求独立文件；后续方法仍可替换具体载体。更正观测或重新压缩若要成为 PreCheck 的新权威结果，产生后继 Result，原 Result 不变。

Representative 是被选为代表的**角色**，不是第五个实体。一个公开 bundle 实体也不是前提：现有 Evidence 和 `represents` 已能表达代表范围。只有出现无法由现有对象诚实承载的独立责任或生命周期时，才重新讨论新增实体。

### 五种关系分别回答什么

| 关系 | 连接 | 回答的问题 |
| --- | --- | --- |
| `accounts_for` | Result → Source Item | 本次交代了哪些源条目，它们的范围处置与处理条件是什么？ |
| `entry_evidence` | Result → Evidence | 可以从哪些低成本材料开始阅读？ |
| `derived_from` | Evidence → Source Item 或 Evidence | 这份材料实际从哪里产生？ |
| `represents` | Evidence → Source Item | 读它时，暂时少读了哪些源条目？ |
| `expands_to` | Evidence → Source Item 或 Evidence | 已经准备了哪些可以进一步读取的细节？ |

关系无需独立 ID。共有依据只需表达一次；个别成员的依据或限制保留在相应连接上，不能拿第一条成员依据冒充全组依据。成员数可以从精确关系推导，返回的计数不拥有另一份权威。源条目也必须能反向查到相关表示，异常项不因没有图像而消失。

### attributes：开放内容，保留含义

属性是关于一个明确对象或关系的陈述，不需要独立身份、生命周期或全局注册服务。今天的时间、镜头、坐标，未来的文字识别或其他检测，都可以作为属性，不成为框架的固定分支。

现有 Observation 已承载对象的具名值、状态和来源；现有关系的 basis、qualifications 已承载依据与限制。具体合约优先复用这些表达。概念上的统一不要求把所有载体改成一个 `attributes` 字段，也不允许双写同一信息。

属性需要使读者知道：

- 它描述谁、名称是什么意思，值的类型和单位是什么；
- 已取得、源字段缺失、未请求、不适用或执行失败的区别；
- 影响解释的来源、有效 profile、观察时间、候选性质及限制；
- 来源冲突或只覆盖部分对象时，实际适用范围是什么。

具体能力在现有合约中定义其属性语义，框架不穷举属性清单。无可靠分数时不制造 confidence。新属性不能改变旧名称含义，也不能替代必须明确的对象身份和关系端点。Read 不把候选转换为事实，Plan 的判断和用户确认不冒充原 Result 观测。

## 一个代表照片的例子

以下均为合成案例，用来检验含义，不是现场运行或最终 schema。

```text
原照片 R ──产生──→ 缩略图 E
                     │
                     └──代表──→ 20 张源照片
```

| 属性属于谁 | 示例 | 不能据此推出什么 |
| --- | --- | --- |
| R | 拍摄时间 12:05；镜头参数；坐标来源；地址候选 | 不能推出 20 张照片均在 12:05 或同一家餐厅 |
| E | 派生尺寸、清晰度限制 | 派生尺寸不是 R 的源尺寸，看不清细字不代表原片没有文字 |
| E 的 `represents` 关系 | 20 个成员；已知时间范围 12:00—12:18；选择依据；未逐张比较内容 | 时间范围不是 R 的时间，精确成员也不证明内容一致 |

Tool 的默认代表阅读把 E 的读取入口、E 自身属性、R 的关联属性和压缩关系放在一起。它沿实际来源取得 R，不沿 `represents` 把其他 19 张的全部属性混入“自身信息”。多步派生保留每一步来源；多个实际来源分别归属，不压成一个虚假的共同源对象。

阅读结构可以表达为：

```text
代表阅读入口（可重新生成的视图，没有独立身份）
├── 自身信息：材料、实际来源及各自属性
└── 压缩关系：精确成员入口、关系属性、依据与限制
```

“完整关联信息”是选中代表已有公共证据及必要缺口说明，不是私有 Work、向量、缓存或原始日志，也不要求先取得全部被代表成员的详细结果。必要的廉价信息可提前准备并复用；准备深度由能力目的与成本决定。

## 两种质疑与正常限制

| 质疑 | 被质疑的含义 | 可能的下一步 |
| --- | --- | --- |
| R 的画面像餐厅，但 POI 都不吻合 | R 的候选、坐标或获取范围是否足够 | 读取 R 的依据、已准备的高清图；必要时在授权范围内调用现有 Geo Tool |
| 代表关系的时间跨度异常长 | E 是否适合代表这些成员 | 读取精确成员、时间、边界或其他已准备材料；Plan 可调整组织判断 |

两种调查可相互影响，但普通信息不足不等于 PreCheck 缺陷。有限 POI 不证明当地没有其他地点；压缩可有损，可回溯不意味着预先知道所有隐藏差异。Plan 可以在自己的判断和合法补查中处理不确定性；只有需要修订 PreCheck 权威范围、观测或关系时才产生后继 Result。

现有 Geo 采集单元、查询点选择及逐项投影是待核对的设计现状，不由本模型重新认证或固定。实际查询坐标与源项坐标不同、复用范围或候选数量有限时，应交代其真实依据与限制。Geo 的授权和效果仍由现有 Run/Read/Geo 合约负责。Plan 补查证据保留新的来源，不能冒充原 Result 已有观测。

## 图片读取与传输

图片路径和对应属性可以在同一条阅读结果中交付。Agent 决定是否打开图片以及如何使用它。提供路径不证明图片已经进入模型上下文，Tool 不返回无法证明的“模型已看过”标志。

业务结果只有一份含义。MCP 的 content、structuredContent 或其他承载形式属于传输适配；不以兼容习惯为理由要求向模型重复注入完整内容，也不强制 Read 附带 base64 图像。客户端是否实际获得、打开、使用了证据要分别验证，不能从路径或工具内变量推断。

## 更换方法时模型如何继续使用

| 变化 | 保持的模型 | 改变的内容 |
| --- | --- | --- |
| 时间邻接改为视觉相似度压缩 | Evidence 通过 `represents` 表示源项 | 关系依据、结果成员与限制 |
| 一张照片改为视频的多帧阅读 | 一个视频源项可产生多个 Evidence；每帧有自己的来源和属性 | 帧位置、采样方式和清晰度等属性 |
| 多个帧组合成联系表 | 联系表来自多个 Evidence，继续追溯同一视频；不复制视频身份 | 材料形式、派生关系和采样限制 |
| 增加 OCR、改变时间解释或调整准备顺序 | 对象与关系不变；新观测若改变封存含义，产生后继 Result | 属性值、producer/profile、内部依赖和执行方法 |

一对一、多对一、一对多和交叠表示都可以成立。聚类不是永久实体；Evidence 也可以是文字、结构化摘要或其他将来形式。通用性来自稳定的归属、关系和责任，不来自一个无语义约束的任意 JSON 字典。

## 八项不变要求

1. **降低默认阅读成本。** Plan 无须默认查看全部素材。
2. **来源范围固定。** Result 的确切范围不随 Dataset 后续变化漂移。
3. **条目不静默消失。** 包括排除、辅助、损坏、未支持和未知项，范围与处理条件分别交代。
4. **来源和表示双向可追溯。** 产生材料的来源与被表示的成员不能混淆。
5. **已有细节可按需调查。** 可读取成员和已准备材料，不要求默认全量阅读。
6. **诚实保留损失与限制。** 未知差异仍未知，不假造全成员已验证。
7. **读取绑定不可变结果。** 不能依赖私有可变 Work 或静默切到最新结果。
8. **方法开放。** 算法、存储、模型、载体和执行顺序可改进，以上含义保持。

## 实现、合约和迁移的边界

长任务的进度、暂停、恢复、失效与复用属于可变 Working Run；状态仍遵守 Foundation 的 execution-state honesty。源只读和外部效果授权由 Tool 执行保证。必要来源与效果证据可以进入 Result，但完整日志、缓存和数据库表不是另一套 Plan 输入。

本页说明已确认的稳定概念；[Read 合约](../../spec/contract/precheck-read/index.md)说明当前调用格式和语义，其第一里程碑已完成；第二里程碑才同步实现、消费者与发布副本，不引入版本路由或双写。零公开 API 兼容政策不授权实现 Agent 自行改变已经确认的承诺，也不授权改写旧 Result。

每次新增字段、层级或实体，都应说明稳定目的、权威来源、删除损失，以及能否复用或推导。更强的 Agent 应能换用更好的调查方法，而不必先拆掉今天固定的流程。

同时对照 AI Album 的实际采集与消费，判断是否有遗漏。框架支持摄影属性，不证明镜头、光圈或曝光已经采集；存在检测器类，不证明安装版配置、生产装配与公开交付已接通。具体 `preserved / intentionally_changed / regression / not_comparable` 判断、实现和验收状态只维护在[既有迁移台账](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。

只有证据显示现有对象不能承载独立责任、关系无法保持追溯，或属性语义导致实质混淆时，才重开模型讨论。新增属性、改变算法或替换存储本身不要求重开骨架。

## Pressure-test results

The minimal Dataset, Result, Source Item, Evidence, and relationship model was tested against three materially different producers. The test asks whether each producer can expose its real compression semantics and limitations without imitating the current implementation or inventing guarantees it does not possess.

### Current MediaSense candidate and Hong Kong material

The current approach maps naturally:

- the continuing subject maps to Dataset, while the reviewed media population is expressed by each Result's direct `accounts_for` relation to Source Items;
- image renditions, video frames, RAW previews, structured summaries, and group entry material can all be Evidence;
- group coverage, production lineage, source lookup, and progressive detail map to the five accepted relationships;
- unreadable media, missing observations, uncertain repair-family identity, proxy fidelity, and possible hidden variation qualify the appropriate Result, Source Item, Evidence, or relationship.

SQLite, YAML, clustering, GPS, named frontier roles, and evidence filenames remain possible implementations or content. None is required by the model. The first sample's business information can therefore be retained without promoting its storage or field layout into the handoff.

### Historical AI Album

AI Album preserved substantial compression value: ordinary and high-resolution thumbnails, video sample frames, metadata, embeddings, bundles, representatives, and clustered output. These map to Evidence, observations, or relationships where the historical material actually preserves their derivation or membership.

The mapping also exposes rather than repairs historical gaps:

- the native output did not bind its Dataset, completely accounted Source Items, effective configuration, caches, and output into one immutable Result;
- it did not provide a complete handoff-level proof that every source item was represented or had an explicit exception path;
- some bundle membership and source traceability had to be reconstructed or added by the later fixture package rather than read from one native authoritative result;
- compression loss, hidden variation, omissions, and uncertainty were not systematically retained.

Captions, inferred locations, titles, privacy results, embeddings, and similar information are not lost by the model. They may be exposed as Evidence or observations when useful, but their presence does not turn those particular semantics into permanent PreCheck concepts. Historical semantic judgments that belong to planning remain comparison evidence rather than PreCheck truth.

The accepted eighteen-class historical inventory remains authoritative in [AI Album Stored Information Inventory](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918D-ai-album-stored-information.md); this module records only what its mapping demonstrates about the handoff model.

### Plausible implementation without clustering

A different producer may create low-fidelity renditions, divide a collection into inspectable ranges, sample each range, extract video excerpts, surface exceptions separately, and permit progressive expansion without computing clusters.

It still maps naturally:

```text
range entry
  -> sampled Evidence
  -> denser existing Evidence
  -> particular Source Items
```

Compression may reduce bytes, decode cost, attention cost, or the number of items read initially; it need not always reduce the number of stored objects. This producer satisfies the model if its entry cost is materially lower for the declared purpose and its coverage, traceability, expansion, loss, and exceptions remain inspectable.

### Pressure-test judgment

All three producers fit without making clustering, metadata categories, database layout, or artifact form permanent. The current producer retains its information, AI Album's missing guarantees remain honestly missing, and the non-clustering producer does not have to masquerade as today's design. No additional core concept is justified by these tests, and relationship records need no separate object identity.

## Boundary and follow-on contract

This document stops at the accepted conceptual model. The active [PreCheck Read Contract](../../spec/contract/precheck-read/index.md) owns the stable machine-facing access semantics derived from these concepts, five relationships, and eight invariants.

Internal storage and implementation remain outside this document's authority. The downstream Tool name, request and response contract, and development Mock are fixed by the formal specification.
