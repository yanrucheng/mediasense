---
id: "clarify-260826-1819-precheck-contract-concepts"
title: "PreCheck 接口概念、命名与字段澄清"
type: clarify
status: active
created: 2026-08-26
updated: 2026-08-26
timezone: "Asia/Shanghai"
parent: "index-clarify"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "eval-260823-1918D-ai-album-stored-information"
superseded-by: ""
tags: ["mediasense", "precheck", "contract", "concept-model"]
---

# PreCheck 接口概念、命名与字段澄清

## 当前设计

下面的 JSON 用“一个视频 + 三张连拍”做具体例子，让人直接判断每个实体和字段是否合理。它不是正式 schema，也不是 runtime 输出；嵌套只是为了阅读方便，不代表最终存储或接口一定嵌套。问卷已经确认的名称现由正式 PreCheck Read Contract 固化。

```json
{
  "dataset": {
    "ref": "dataset:A",
    "name": "数据集 A",
    "context": [
      {
        "content": "家庭旅行媒体；整理时优先保留人物与事件差异",
        "provided_by": "user"
      }
    ],
    "qualifications": []
  },
  "precheck_result": {
    "ref": "precheck-result:A-003",
    "dataset_ref": "dataset:A",
    "coverage": "complete",
    "readiness": "plan_ready",
    "integrity": "valid",
    "source_items": [
      {
        "ref": "source-item:video-001",
        "locator": {
          "kind": "dataset_relative_path",
          "value": "旅行/video-001.mp4"
        },
        "accounting": {
          "scope": "source_media",
          "condition": "usable"
        },
        "observations": [
          {
            "name": "media_type",
            "status": "available",
            "value": "video/mp4",
            "basis": {
              "method": "local_media_probe"
            }
          }
        ],
        "qualifications": []
      },
      {
        "ref": "source-item:burst-001",
        "locator": {
          "kind": "dataset_relative_path",
          "value": "旅行/burst-001.jpg"
        },
        "accounting": {
          "scope": "source_media",
          "condition": "usable"
        },
        "observations": [],
        "qualifications": []
      },
      {
        "ref": "source-item:burst-002",
        "locator": {
          "kind": "dataset_relative_path",
          "value": "旅行/burst-002.jpg"
        },
        "accounting": {
          "scope": "source_media",
          "condition": "usable"
        },
        "observations": [],
        "qualifications": []
      },
      {
        "ref": "source-item:burst-003",
        "locator": {
          "kind": "dataset_relative_path",
          "value": "旅行/burst-003.jpg"
        },
        "accounting": {
          "scope": "source_media",
          "condition": "usable"
        },
        "observations": [],
        "qualifications": []
      }
    ],
    "entry_evidence": [
      {
        "ref": "evidence:video-frame-001",
        "access": {
          "kind": "local_artifact",
          "locator": "evidence/video-001/frame-001.jpg"
        },
        "derived_from": [
          "source-item:video-001"
        ],
        "represents": [
          "source-item:video-001"
        ],
        "expands_to": [
          "evidence:video-frame-002",
          "evidence:video-frame-003",
          "source-item:video-001"
        ],
        "observations": [],
        "qualifications": []
      },
      {
        "ref": "evidence:burst-representative",
        "access": {
          "kind": "source_item",
          "source_item_ref": "source-item:burst-002"
        },
        "derived_from": [
          "source-item:burst-002"
        ],
        "represents": [
          "source-item:burst-001",
          "source-item:burst-002",
          "source-item:burst-003"
        ],
        "expands_to": [
          "source-item:burst-001",
          "source-item:burst-002",
          "source-item:burst-003"
        ],
        "observations": [],
        "qualifications": [
          {
            "code": "representative_may_hide_variation",
            "effect": "limits_interpretation",
            "message": "默认只看 burst-002；另外两张仍可直接展开。",
            "basis": "三张照片相似，但并非完全相同。"
          }
        ]
      }
    ],
    "attention_items": {
      "authority": "derived_view",
      "derived_from": "source_items 中 condition 异常或带有重要 qualification 的项目",
      "items": []
    },
    "relationship_query_example": {
      "origin": "evidence:burst-representative",
      "relation": "represents",
      "direction": "outbound",
      "basis": "本次 PreCheck 的相似性与覆盖检查",
      "qualifications": [
        {
          "code": "representative_may_hide_variation",
          "effect": "review_more_if_material",
          "message": "这是一项可质疑的压缩主张，不是来源媒体真值。"
        }
      ],
      "items": [
        {
          "target": "source-item:burst-001"
        },
        {
          "target": "source-item:burst-002"
        },
        {
          "target": "source-item:burst-003"
        }
      ]
    },
    "qualifications": []
  },
  "precheck_internal_working_state": {
    "delivered_to_plan": false,
    "reusable_work_examples": [
      {
        "plain_example": "video-001 的视频截图已经算过；来源和截图方法均未改变时可以复用"
      },
      {
        "plain_example": "burst-002 的相似性计算已经算过；文件移动但内容未变时，本版实现希望继续复用"
      }
    ]
  }
}
```

这个例子里的边界是：

```text
压缩前的来源                         压缩后给 Plan 的证据

video-001.mp4（1 个 Source Item） ──→ frame-001 / 002 / 003（多份 Evidence）

burst-001.jpg（1 个 Source Item） ┐
burst-002.jpg（1 个 Source Item） ├─→ burst-002 作为默认 Evidence
burst-003.jpg（1 个 Source Item） ┘
```

- `Source Item` 是压缩前被发现并需要核算的单个来源对象。在这个例子里共有 4 个：1 个视频文件和 3 个图片文件。
- “三张连拍”是这 3 个 Source Items 之间的候选关系或压缩分组，不是一个 Source Item。
- 视频截图是从视频产生的 Evidence，不是 Source Item。
- `burst-002.jpg` 本身仍是一个 Source Item；当它被选作默认代表时，Evidence 可以直接引用它，不要求再复制一份图片。
- `ref` 像该 Result 内使用的“编号”，例如 `source-item:burst-002`。关系通过它精确指向对象，不把路径当身份。
- `locator`（仍是待审工作名）像“地址”，例如 `旅行/burst-002.jpg`，用于找到并打开实际来源。`ref` 回答“是哪一项”，`locator` 回答“当前到哪里访问它”。
- `precheck_internal_working_state` 刻意放在 Result 外，展示局部缓存与复用属于 PreCheck 内部工作状态，不直接交付给 Plan。
- 当前确认五种权威关系语义：Result 核算 Source Item、Result 指定默认 Evidence、Evidence 代表 Source Item、Evidence 来源于 Source Item/Evidence、Evidence 展开到 Source Item/Evidence。`dataset_ref` 是 Result 的必填字段，不重复表达为关系；`attention_items` 是从核算状态派生的快捷视图，不是第二份权威关系。
- `relationship_query_example` 展示关系查询的最小响应：查询外层只写一次 `origin/relation/direction`，成员只返回 `target`；共享依据和限制放在外层，个别成员仅在不同时覆盖。

当前模型保留长期 Dataset，但不再用整个 Dataset 的 `Source Snapshot` 作为主要复用和失效边界。Result 直接核算一组 Source Items；PreCheck 内部按更小的信息单元复用、局部失效和增量补全，这种内部单元不进入 Plan 接口。

## 证据

- 用户业务场景：同一 1.5T 数据集可反复得到约 500、3、200 张不同压缩结果；补入少量数据后应复用未受影响工作，而不是全量重算。
- AI Album 的历史实现以单媒体 partial hash 参与多类缓存寻址，并支持按缓存类别清理；这证明细粒度复用有业务价值，也暴露了依赖维度缺失和失效范围偏粗的问题。详见 [AI Album 持久化信息清单](../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918D-ai-album-stored-information.md)。
- [MediaSense Foundation](../design/design-260823-1918-mediasense-foundation.md) 已要求 PreCheck 可恢复、可增量复用、局部失败不污染无关完成工作，并保持具体算法可替换。
- [PreCheck Compression Boundary](../design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md) 已确认压缩、双向溯源、渐进展开和无静默消失是稳定责任；其中 `Source State` 及四概念结构现因本轮反馈重新打开审查。
- [PreCheck Read Contract](../spec/spec-260826-1546-precheck-read/index.md) 与 [香港 Mock](../spec/spec-260826-1546-precheck-read/hong-kong.mock.json) 最初是待修材料；现已依据本记录完成 Zero BC 重写，正式约束以 specification 为准。

## 已确认决策

1. Dataset 是长期存在的业务对象；源文件增删改后仍可保持同一个 Dataset 身份。
2. Dataset 的变化会使旧 PreCheck 交付不再代表当前状态，但不应使全部既有计算同时失效。
3. PreCheck 的核心业务价值是压缩，并为 Plan 建立低成本、快速、可渐进展开的本地信息基础。
4. 复用与失效必须能够落到比整个 Dataset 更小的粒度；新增少量来源通常只补算新增项及受其影响的下游关系。
5. 不采用整个 `Source Snapshot` 作为所有缓存的共同身份或全局失效开关。
6. Plan 通过稳定 Tool 读取 PreCheck 交付，不直接依赖 SQLite 或其他内部存储布局。
7. SQLite、hash 算法、缓存文件名、thumbnail、embedding、cluster 和具体压缩方法均不是永久产品实体。
8. 本记录已完成实体名、关系名和最小字段审查；正式取值与机器约束由 PreCheck Read Contract 负责。
9. 长期对象采用工作名 `Dataset`，由用户或上层产品维持身份；最小字段为 `ref`、可选 `name`、可选且可追溯的 `context`、必要时的 `qualifications`。
10. Dataset 可以有当前发现视图，但每份 Result 必须直接且不可变地核算自身覆盖的 Source Items；不以全局 Source Snapshot 作为缓存边界。
11. `Source Item` 的引用只承诺在一个 Result 内稳定；当前实现可以识别来源移动并复用缓存，但这不升级为跨 Result 永久身份契约。
12. Source Item 的最小字段为 `ref`、`locator`、开放式 `observations` 和必要时的 `qualifications`；范围角色与处理状况在核算关系上分别表达。
13. Plan 接口不公开 hash、缓存 key 等内部有效性依据；PreCheck 内部保留可独立复用和失效的工作单元，但当前接口阶段不冻结其字段。
14. Plan 可读的压缩入口采用工作名 `Evidence`；其最小字段为 `ref`、`access`、开放式 `observations` 和必要时的 `qualifications`，入口与展开角色由关系表达。
15. `PreCheck Result` 是不可变交付，不是可变缓存视图；最小字段为 `ref`、`dataset_ref`、`coverage`、`readiness`、`integrity` 和必要时的 `qualifications`。
16. 关系层保留五种独立权威语义：`accounts_for`、`entry_evidence`、`represents`、`derived_from`、`expands_to`。`dataset_ref` 作为 Result 字段；`attention_items` 作为由 `accounts_for` 派生的快捷视图。
17. 关系查询在外层声明 `origin`、`relation` 和 `direction`；返回成员只保留 `target` 及该成员特有的信息，不设置关系 ID，也不重复 `type/from/to`。
18. 不为所有关系强制统一 `epistemic_state`。每种关系由自身语义确定权威性质；`represents` 是可质疑的 PreCheck 压缩主张，不冒充来源真值。
19. 关系共享的 `basis` 与 `qualifications` 放在查询外层，个别成员仅在内容不同时覆盖。`represents` 必须能查到选择或覆盖依据，其他关系只在有重要限制时提供。
20. Observation 最小字段为 `name`、`status`、按需 `value` 和可追溯 `basis`；`status` 采用 `available`、`missing`、`failed`、`not_checked`、`not_applicable`。`confidence` 与 qualification 仅在确有意义时出现。
21. Qualification 最小字段为 `code`、`effect`、`message`；只有所属对象或关系没有表达依据时才增加 `basis`。

## 问题清单

### 第 1 轮：全部核心实体与字段问题包

本轮一次覆盖五组问题：Dataset、来源项、内部可复用信息、Plan 可读证据、PreCheck Result 与公共关系。可以只写选项字母，也可以直接改 JSON 中的工作名或字段；如果一个选项只对一半，请写组合答案。

#### Q1. 长期业务对象应叫什么，它的身份由谁确认？

为什么问：它需要跨来源增删改持续存在，但如果完全由路径或内容自动决定，同一个数据集移动或补充后就可能被误判为新对象。

简单例子：`数据集 A` 从磁盘 1 移到磁盘 2，并新增 20 张照片，业务上仍是同一个对象。

选项：

- A. `Dataset`：由用户或上层产品创建并维持身份；PreCheck 只引用。
- B. `Media Library`：强调这是持续维护的媒体库，也由用户或上层产品维持身份。
- C. `Collection`：沿用当前名字，由系统按来源范围自动识别。
- D. 不设长期实体；每次只识别当前输入。

推荐：A。原因：`Dataset` 最接近你反复使用的“数据集 A”，也不会暗示算法分组；身份应由业务层确认，而不是由易变路径或内容猜测。

你的回答：A

#### Q2. Dataset 自身最少应有哪些字段？

为什么问：Dataset 要给人和 Plan 提供稳定上下文，但不能变成所有信息都往里塞的杂物箱。

简单例子：Plan 需要知道“这是香港美食旅行资料”，但不应从 Dataset 字段里读取某张照片的 GPS。

选项：

- A. 只有 `ref`；名称和说明都由外部系统管理。
- B. `ref`、可选 `name`、可选且可追溯的 `context`、必要时的 `qualifications`。
- C. 再加入创建时间、所有者、当前路径、总文件数、默认语言等固定字段。
- D. 使用任意 JSON 属性，不定义稳定字段。

推荐：B。原因：它保留最小身份和 Plan 真正需要的长期背景，同时不把当前来源状态或产品管理字段提前固化。

你的回答：B

#### Q3. Dataset 的 `context` 应怎样区分事实、用户说明和偏好？

为什么问：Plan 可以利用数据集背景，但“用户说这是家庭旅行”和“系统观察到文件时间范围”不是同一种权威。

简单例子：用户写“重点整理饮食经历”；这是一条有效输入，但不是从媒体中观察出的事实。

选项：

- A. 一段自由文本；Plan 自行理解，不记录来源。
- B. 多条可归因内容，每条保留内容、来源/提供者和必要限制；具体内容结构保持开放。
- C. 预先定义旅行地点、人物、时间、目标等固定字段。
- D. Dataset 不保存任何 Plan 可读背景。

推荐：B。原因：它能诚实区分用户输入和系统事实，又不把旅行场景特有字段冻结进框架。

你的回答：B

#### Q4. Dataset 是否直接拥有一份“当前 Source Items 清单”？

为什么问：Dataset 会持续变化；把一个可变清单直接当成稳定字段，会让旧 Result 到底核算了哪些项目变得不清楚。

简单例子：Dataset 今天 10,000 项，明天新增 20 项；旧 Result 必须仍能说明它只核算了当时那 10,000 项。

选项：

- A. Dataset 固定保存唯一当前清单，所有 Result 都间接引用它。
- B. Dataset 可有当前发现视图，但每个 Result 必须直接、不可变地核算自己所覆盖的 Source Items；当前视图不属于跨阶段稳定契约。
- C. 每次变化创建一个完整 `Source Snapshot` 实体，所有计算都绑定它。
- D. 不保存清单，只保存总数。

推荐：B。原因：它同时保留 Dataset 的持续身份、旧 Result 的可审计边界和细粒度复用，不把全局 Snapshot 变成缓存失效边界。

你的回答：B

#### Q5. “某份 Result 核算到的一个具体来源对象”应叫什么、如何保持身份？

为什么问：它必须让 Plan 精确回到原始资产，但跨 Result 的永久文件身份会牵涉移动、替换、复制和重复内容，不能轻率承诺。

简单例子：相同照片从目录 A 移到目录 B；旧 Result 仍应能描述当时的来源，新 Result 是否沿用同一个项目身份需要明确。

选项：

- A. `Source Item`：引用只保证在一个 Result 内稳定；跨 Result 对应关系可另行推断或记录。
- B. `Media Asset`：在 Dataset 内永久稳定，路径移动不改变身份。
- C. `File`：身份就是某一条路径。
- D. `Input`：每次 PreCheck 运行都重新创建，不强调可回查对象。

推荐：A。原因：这是当前接口能诚实保证的最小语义；内部缓存仍可按内容依据复用，但不必把缓存识别规则升级成永久资产身份。

你的回答：A. 这地方很值得关注一点就是，确实是这条记录应该能记录那个原本的样子，但是它移动了之后，我们要不要通过缓存在新的地点仍然复用这结果，我觉得是可以要的，至少在我们这一版实现方案是可以要的。当然作为框架的话，就是要求是A，这个区别就是框架和实现方案上的一个区别，你能不能明白我的意思？

#### Q6. Source Item 自身最少应有哪些字段？

先明确对象：在顶部例子里，`video-001.mp4`、`burst-001.jpg`、`burst-002.jpg`、`burst-003.jpg` 各是一个 Source Item。视频截图是 Evidence；三张连拍形成的组也不是 Source Item。`burst-002.jpg` 被选为代表时，它仍是来源项，同时由一条 Evidence 记录把它作为 Plan 的默认入口。

为什么问：来源项需要同时解决“关系怎样稳定引用它”和“怎样找到实际文件”两个问题，但媒体类型、时间、GPS、可读性等可能缺失或由不同方法得到，不宜全部做固定顶层字段。

简单例子：`ref: source-item:burst-002` 是 Result 内部引用这张照片的编号；`locator: 旅行/burst-002.jpg` 是找到并打开它的地址。前者供关系引用，后者供实际访问。移动后是否跨 Result 复用旧计算，由 PreCheck 内部的来源识别与依赖判断完成，不要求两个 Result 共用同一个 `ref`。

选项：

- A. `ref`（Result 内的稳定编号）、`locator`（实际来源地址，字段名仍可改）、开放式 `observations`、必要时的 `qualifications`。
- B. 再固定加入 `path`、`media_type`、`size`、`mtime`、`checksum`、`capture_time`、`gps`。
- C. 只有 `path`，其余均由 Plan 现查。
- D. Source Item 不作为可检查实体，只存在于关系里。

推荐：A。原因：`ref` 与 `locator` 分别承担关系引用和实际访问，不能互相替代；`path`、时间、GPS 等具体内容则作为带 availability 与 provenance 的 observation 出现。若你认为“地址”比 `locator` 更自然，可以在回答中直接给它改名。

你的回答：A

#### Q7. included、auxiliary、excluded、unsupported、invalid、error、unresolved 应怎样表达？

为什么问：这些词混合了“是否纳入媒体范围”和“当前处理状况”。放进同一个枚举会出现 invalid 文件到底算 included 还是 invalid 的冲突。

简单例子：损坏 MP4 可以同时是 `source_media` 和 `invalid`；GPX 可以同时是 `auxiliary` 和 `usable`。

选项：

- A. 一个统一状态字段，七个值互斥。
- B. 在 Result→Source Item 的核算关系上分成 `scope` 与 `condition` 两个正交字段。
- C. 全部写成自然语言 qualification。
- D. 放在 Source Item 本身，所有 Result 永久沿用同一分类。

推荐：B。原因：分类是某次核算决定，不一定是来源对象的永久属性；两个维度可以诚实表示 invalid 仍属 source media。

你的回答：B

#### Q8. 单项内容变化和缓存复用依据是否应成为 Plan 接口字段？

为什么问：PreCheck 必须精确失效，但 Plan 通常只关心信息能否依赖，而不关心 fast hash 或缓存键。

简单例子：新增一张照片只补算相关项；算法版本改变时，某类旧 embedding 失效，但原 metadata 仍可复用。

选项：

- A. 把 hash、算法版本、缓存 key 全部公开在 Source Item。
- B. Plan 接口只暴露必要的当前有效性、provenance 和限制；具体依赖指纹属于 PreCheck 内部。
- C. Plan 完全看不到有效性，缓存命中即视为可信。
- D. 所有信息随 Dataset 任一变化一起失效。

推荐：B。原因：它保留跨阶段信任边界，同时允许内部实现替换 hash、索引和缓存布局。

你的回答：B

#### Q9. 是否需要独立的 `Prepared Information Unit`？它属于谁？

为什么问：它有独立的复用、失效和补算生命周期，因此内部可能是真实体；但把它直接交给 Plan 会泄漏缓存实现。

简单例子：一张照片的 metadata 已就绪、缩略图已就绪、embedding 因模型升级而 stale，这三项可分别处理。

选项：

- A. 是 PreCheck 内部实体，默认不进入 Plan 合同；只有被提升为可读 observation/evidence 后才跨阶段。
- B. 是公开实体，Plan 可以枚举全部缓存单元。
- C. 不需要实体，只保存散落文件并靠是否存在判断。
- D. 每个 Dataset 只有一个整体完成状态。

推荐：A。原因：它确实拥有独立生命周期，但其稳定责任是支撑 PreCheck 增量运行，不是让 Plan 依赖缓存结构。

你的回答：A

#### Q10. 如果保留内部 Prepared Information Unit，它最少需要哪些语义字段？（原题已撤回推荐）

为什么问：只以“缓存文件存在”判断有效会重复 AI Album 的已知问题；但固定 hash、模型或目录字段又会锁死方法。

简单例子：旧 caption 文件存在，但 prompt 已改变；系统必须判断它 stale，而不是误当命中。

选项：

- A. `subject_ref`、`information_kind`、`input_basis`、`method_basis`、`state`、`value_or_artifact`、`provenance`、必要 `qualifications`。
- B. 只有 `cache_path` 和 `exists`。
- C. 再固定加入 fast hash、模型名、prompt、embedding 维度和 SQLite row id。
- D. 暂不定义任何最小语义，等实现时自由决定。

原推荐：A。

整合说明：这一组字段不是工业界公认的固定标准，而是从构建缓存、内容寻址、任务产物、数据血缘和增量构建等常见机制中抽出的候选集合。它混合了“框架必须保证什么”和“当前实现怎样记录”，超出了当前先冻结 Plan 读取接口的范围，因此撤回原推荐。本题保留作为审查记录，不需要回答，请改答下面的 Q10A。

你的回答：N/A

#### Q10A. 当前接口阶段要不要规定内部可复用计算的具体字段？

为什么问：Q9 已确认 PreCheck 内部需要可独立复用和失效的工作单元，但这不意味着 Plan 接口现在必须知道它们怎样存储。

简单例子：工程实现可以用类似 `输入依据 + 计算方法依据 -> 缓存结果` 的机制判断视频截图能否复用；将来既可以用 SQLite，也可以用内容寻址文件或其他增量计算系统。

选项：

- A. 当前不规定内部字段；只把“能够按真实依赖精确判断复用或失效，不能仅凭缓存文件存在”记为 PreCheck 实现必须满足的要求。
- B. 现在就把原 Q10 的八个字段固定为内部数据模型。
- C. 完全不规定有效性要求；实现发现缓存就直接复用。

推荐：A。原因：业界有共同原则，但没有一套适用于所有系统的标准字段表。当前应冻结的是可观察能力和正确性要求；内部字段等第一阶段实现设计时再依据选定技术落地。

你的回答：A

#### Q11. Plan 可直接读取的压缩入口应叫什么？

为什么问：当前 `Representation` 太抽象，也容易被理解成某种图片文件；真正责任是“可依赖、可展开、可回溯的压缩证据”。

简单例子：一张组内代表图、一组边界对照图或一段视频帧摘要，都可以成为 Plan 的起点。

选项：

- A. `Evidence`：强调它是用于判断、可追溯但不是真值本身的证据。
- B. `Representation`：强调它代表一个或多个来源项。
- C. `Summary`：强调压缩后的摘要。
- D. `Artifact`：强调它是可打开的文件或数据产物。

推荐：A。原因：它能同时容纳视觉和结构化证据，并自然要求 provenance、限制与反向追溯；具体 artifact 只是访问形式。

你的回答：A

#### Q12. Evidence 最少应有哪些字段，默认角色放在哪里？

为什么问：此前在实体里用自然语言 `role` 指挥 Plan，会让行为不可稳定判断；但固定 representative/boundary/outlier/conflict 又可能把当前方法写死。

简单例子：同一张图片可以因一条关系成为 Result 的默认入口，也可以因另一条关系成为某证据的下一层展开。

选项：

- A. Evidence 只含 `ref`、`access`、开放式 `observations`、必要 `qualifications`；入口和展开角色由关系表达。
- B. Evidence 固定加入自然语言 `role`，Plan 根据文字判断。
- C. Evidence 固定加入 representative/boundary/outlier/conflict 枚举。
- D. Evidence 只给文件路径，不提供限制或结构信息。

推荐：A。原因：机器行为由 `entry_evidence`、`represents`、`expands_to` 等稳定关系决定；算法仍可用任意方式选择证据。

你的回答：A

#### Q13. `PreCheck Result` 应是不可变交付，还是始终指向正在增长的缓存？

为什么问：Plan 需要稳定输入；PreCheck 又需要持续补算和复用。把二者合成同一可变对象会让同一次 Plan 查询前后含义变化。

简单例子：Plan 已根据 200 份入口证据开始工作，此时 PreCheck 又补入 20 个新文件。

选项：

- A. Result 是不可变发布物；可变工作状态与缓存继续增长，准备好后产生新 Result，并复用旧工作。
- B. Result 永远是 Dataset 当前缓存的动态视图。
- C. Result 是一次运行目录，运行重启就产生新身份。
- D. 不设 Result；Plan 每次直接查询 Dataset。

推荐：A。原因：稳定交付和增量缓存属于两个不同生命周期；分开后既不会强迫全量重算，也不会让 Plan 的依据漂移。

你的回答：A

#### Q14. PreCheck Result 自身最少应有哪些字段？

为什么问：Result 需要让 Plan 判断“能否开始”和“能信到什么程度”，但不应复制完整来源清单、证据清单和运行日志到一个巨大对象里。

简单例子：一项损坏 MP4 已完整核算且有足够替代证据；Coverage 可以 complete，Readiness 可以 plan-ready，Integrity 仍可 valid，同时保留局部限制。

选项：

- A. `ref`、`coverage`、`readiness`、`integrity`、必要 `qualifications`；Dataset、核算项、入口证据和异常项通过关系读取。
- B. 再把全部 Source Items、Evidence、缓存状态和日志内嵃进 Result。
- C. 只有 `ref` 和 `complete` 一个布尔值。
- D. 不提供明确状态，全由 Plan 阅读后自行推断。

推荐：A。原因：三个轴回答不同问题，关系负责可分页的大集合；这样既最小，又不会用一个 `complete` 掩盖局部错误。

你的回答：A

#### Q15. 公共关系、observation 和 qualification 应保留到什么程度？

为什么问：这些公共记录决定所有实体怎样扩展。如果过薄，错误和依据只能写散文；如果过厚，每条边都会充满重复字段。

简单例子：“证据 E 代表来源 1–201”是候选关系；“来源 215 无法解码”是 observation；“代理视频不能证明完整时间线”是 qualification。

选项：

- A. 采用顶部 JSON 的候选：关系含 type/from/to/epistemic state/provenance/必要 qualifications；observation 含 name/availability/value/epistemic state/可选 confidence/provenance/必要 qualifications；qualification 含 code/effect/message/provenance 或 basis。关系无独立 ID。
- B. 所有公共记录只保留自由文本。
- C. 每种 metadata、错误和关系各自定义专用字段与实体。
- D. 关系只含 from/to，其他一律由 Plan 猜测。

推荐：A，但允许你逐项删字段。原因：这是目前能同时表达事实与候选、缺失与失败、来源与限制的最小通用外壳；具体 observation 名称和算法仍保持开放。

你的回答：很好。就按你这个。

整合说明：接受的是关系语义审计结论，不是原 A 中“每条关系统一携带所有字段”的设计。确认保留 `accounts_for`、`entry_evidence`、`represents`、`derived_from`、`expands_to` 五种权威关系语义；`dataset_ref` 改为 Result 字段；`attention_items` 是由核算状态派生的快捷视图。关系英文名暂作工作名。公共记录字段继续在第 2 轮最小化。

### 第 2 轮：关系与公共记录的最小字段

本轮只审接口记录怎样表达已经确认的关系、观察和限制，不重新打开实体、关系种类或内部缓存实现。重点是删除重复字段，并让缺失、失败和依据仍然可判断。

#### Q16. 一次关系查询返回的每一项，是否还要重复 `type`、`from` 和 `to`？

为什么问：如果查询外层已经写明“从 Evidence E 沿 `represents` 向外查”，每一项再重复相同的关系名和起点会制造大量冗余。

简单例子：查询外层是 `origin: evidence:E`、`relation: represents`、`direction: outbound`；返回项只写 `target: source-item:P1` 即可知道完整方向。

选项：

- A. 外层保留 `origin`、`relation`、`direction`；每个返回项只保留 `target` 和该关系特有的信息，不设关系 ID，也不重复 `type/from/to`。
- B. 每个返回项都完整重复 `type/from/to`，方便脱离查询上下文单独复制。
- C. 关系全部嵌入实体数组，不提供统一遍历响应。

推荐：A。原因：它不损失语义，同时显著减少百万项关系中的重复数据；独立复制某一条边不是当前接口的业务责任。

你的回答：A

#### Q17. 五种关系是否应共享同一套 `epistemic_state`？

为什么问：这五种关系的权威性质本来不同。强制都填写 `fact/candidate` 容易把产品决定、导航关系和语义推断混成一种东西。

简单例子：`entry_evidence` 是 PreCheck 对默认入口的交付决定；`derived_from` 是生成血缘；`represents` 则是“看这份证据可以暂缓看哪些来源”的压缩主张。

选项：

- A. 不设所有关系共有的 `epistemic_state`；每种关系直接定义自己的权威语义，其中 `represents` 永远是可质疑的 PreCheck 压缩主张，不冒充媒体真值。
- B. 所有关系强制填写 `fact` 或 `candidate`。
- C. 所有关系都当作事实，不表达可质疑性。

推荐：A。原因：关系类型本身已经承载不同责任；统一枚举会重复或歪曲这些责任。以后如果同一种关系确实需要多个状态，再为该关系增加专用字段。

你的回答：A

#### Q18. 哪些关系必须携带依据或限制？

为什么问：每条关系都复制 provenance 和 qualifications 太重；全部不记录又会让代表性压缩无法审查。

简单例子：201 个 `represents` 成员可能共享同一份分组与覆盖依据，没有必要在 201 条返回项里重复同一段文字。

选项：

- A. 关系查询外层可以保存这组关系共享的 `basis` 和 `qualifications`；个别成员只有不同时才覆盖。`represents` 必须能查到选择/覆盖依据；其他关系仅在有重要限制时提供。
- B. 每一个返回项都强制复制完整 provenance 和 qualifications。
- C. 任何关系都不记录依据或限制，全靠 Evidence 文本说明。

推荐：A。原因：它保留可审查性，又避免按成员重复相同信息；真正不同的个别成员仍可单独标记。

你的回答：A

#### Q19. 一条 observation 最少需要什么？

为什么问：需要区分“值为空”“没有观察”“观察失败”和“不适用”，也需要知道值来自直接读取还是推导；但不应把所有可能元数据固定成顶层字段。

简单例子：视频 `create_date` 可以是 `missing`，而不是错误地写成空字符串；媒体类型可以是本地探测得到的 `video/mp4`。

选项：

- A. 必填 `name` 与 `status`；有值时填写 `value`；有值或失败时记录可追溯的 `basis`。`status` 最小取值为 `available`、`missing`、`failed`、`not_checked`、`not_applicable`。只有确实有意义时才增加 `confidence` 或 qualification。
- B. 沿用原 A：每条都强制 `availability`、`epistemic_state`、`provenance`、qualifications，即使为空也保留。
- C. 只保留 `name/value`，缺失和失败均写 `null`。

推荐：A。原因：状态和依据是可信使用的最低要求；它把缺失与失败分开，又删除了每条记录上常为空或可由语义推断的包装字段。

你的回答：A

#### Q20. 一条 qualification 最少需要什么？

为什么问：qualification 既要让 Agent 快速判断影响，也要让人能读懂原因；但 `basis` 若已在 observation 或关系外层存在，不应重复。

简单例子：代表图片可能隐藏组内人物差异，这会限制直接下结论，但未必阻塞 Plan 开始工作。

选项：

- A. 必填机器可判断的 `code`、`effect` 和人可读的 `message`；只有依据没有在所属对象或关系上表达时，才补 `basis`。
- B. 只保留一段自然语言 `message`。
- C. 每条都强制 `code/effect/message/basis/provenance/confidence`。

推荐：A。原因：`code` 支持稳定筛选，`effect` 表明后果，`message` 方便人工审阅；依据只在缺失时补足，避免双写。

你的回答：A

## 被拒绝选项

1. 用整个 Dataset 的单一 `Source Snapshot` 或整体 hash 作为全部缓存的共同失效边界：它会把局部变化错误放大成全量失效。
2. 让 Plan 直接读取 SQLite：这会把第一阶段内部实现变成第二阶段依赖，妨碍独立替换。
3. 把 AI Album 的缓存类别、bitmap、partial MD5 或文件名直接提升成 MediaSense 永久契约：它们只能提供历史能力和失败证据。
4. 用自由自然语言 `role` 承担必须稳定判断的入口、覆盖或展开语义：机器行为需要由明确关系表达。
5. 因为某项 invalid、unsupported 或 auxiliary 就将其从核算边界静默移除：所有已发现项目都必须有明确归宿。

## 未决问题

无阻塞项。下一步可以依据本记录重写正式 PreCheck 读取接口和 Mock；实现层的 SQLite、缓存依赖字段与算法仍留待第一阶段实现设计。

## 质量门

- [x] 顶部候选 JSON 覆盖全部待审实体、字段、关系和明确排除项。
- [x] 已将稳定产品语义与 SQLite、hash、缓存文件名和具体算法分开。
- [x] 已把 Dataset 持续身份与 Result 的不可变核算边界分开。
- [x] 每个问题都有原因、例子、选项、推荐答案和回答位置。
- [x] 用户已回答第 1 轮全部阻塞问题。
- [x] 已将第 1 轮回答整合进“当前设计”“已确认决策”“被拒绝选项”和“未决问题”。
- [x] 用户已回答第 2 轮公共记录最小字段问题。
- [x] 当前设计足以让另一位 Agent 重写正式接口与 Mock，而无需自行发明实体或字段。
