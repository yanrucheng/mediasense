---
id: "spec-260826-1546-precheck-read"
title: "MediaSense PreCheck Read Tool Contract"
type: spec
status: superseded
created: 2026-08-26
updated: 2026-09-09
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
superseded-by: "precheck-read"
tags: ["mediasense", "precheck", "tool", "result", "review"]
---

# MediaSense PreCheck Read Tool Contract

> **历史记录，已退出当前规范。** 唯一当前合约在 [contract/precheck-read](../contract/precheck-read/index.md)。本目录的文字、schema 和示例保留为旧版本证据，不用于新开发；包内旧副本也不能替代新合约。


`mediasense.precheck.read` 只读一份确切、受信任的不可变 Result。
[Tool Schema](precheck-read.tool.json) 是当前唯一交换值规范；
[合成示例](hong-kong.mock.json)展示 review、expand、resolve 和 geo_summary。
四操作均显式携带 action、dataset_ref、result_ref，不接受 request 包装或 operation 别名。
本合约采用零公开 API 兼容政策，不增加 Tool、版本路由或读取会话。

Read 不获取新证据，不作组织语义决定，不修改 Run、Plan 或源媒体。
验证封存字节与引用后才作只读投影；非法 Result 返回 result_untrusted 或 result_inconsistent。
成功读取失败 Observation 是普通数据，不是调用失败。

## 历史审阅过程：代表阅读的最小改动

**状态：本节待用户验收，尚未激活。** 已确认的[概念模型](../../design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)采用“对象＋关系＋属性”；本节只提出它到 `review` 的最小映射。下方 D4—D9、Tool Schema、发布副本和运行代码仍是当前接口，不能把本节样例宣称为现有返回。

原 D4 让默认 review 只提供固定摘要，其他信息通过 expand 拼接。本提案改为：**一条阅读记录共同提供代表的图片路径、自身关联属性和压缩关系。** Agent 决定是否打开图片。`attributes` 不新增为另一个字段：具名属性复用 `observations`，关系依据和限制复用 `basis / qualifications`。

**这还不是最终字段设计。** 已确认的是概念及归属；下方命名和层级仍待审阅。原稿的 `cards` 是现有接口对阅读列表的叫法，不是 `case`，也不是 MCP 标准或独立业务实体。本待审稿改称 `items`（本页阅读条目），当前生效 schema 仍使用 `cards`，尚未迁移。

### 先看返回树

```text
一次 review 的返回（读取视图，不是 Result 的存储结构）
├── result：读的是哪份结果，是否可以用于 Plan
├── accounting：整份结果有没有把源条目交代清楚
├── items：本页的阅读条目，不新增实体
│   └── 一条阅读记录
│       ├── evidence_ref / access：当前材料 E 是谁、在哪里读取
│       ├── observations / qualifications：E 自己的属性和限制
│       ├── source_items：E 实际来自 R；这里放 R 的属性
│       ├── represents：E 代表那 20 张照片；这里放关系属性
│       └── roles / available_expansions：已有调查导航，可继续精简
└── page：本次选择还有没有下一页
```

先读 `items` 就能理解一个代表。`result / accounting / page` 分别处理结果绑定、全局完整性和分页，不是另外三种素材对象。

下方用 JSONC 给人审阅，`//` 注释不进入真实返回。注释中的“保留”表示该含义必要；“按需”表示有相应证据或请求时返回；“待精简”表示当前编码仍需判断，不能仅凭旧 schema 已有就固定。具体 `required` 集合将在本节验收后写入机器 schema。

### 输入

继续使用现有 Tool 和分页请求，不增加读取会话或 bundle ID：

```jsonc
{
  "action": "review", // 保留：选择读取操作，不开始新的 PreCheck。
  "dataset_ref": "dataset:example", // 保留：在已打开的 Dataset 内定位，不扫描其他集合。
  "result_ref": "precheck-result:example", // 保留：固定这一次结果，不自动读取“最新”。
  "page": { // 按需：复用现有分页控制；省略时使用 Tool 默认值。
    "limit": 1 // 按需：本次最多读取 1 个入口；是示例值，不是永久批大小。
  }
}
```

### 返回

以下是业务返回对象，不重复展示 MCP 的传输包装。全部为合成数据：Result 交代 20 张照片，只有一个入口 E；E 实际来自 R，并代表那 20 张照片。这个小样例只记录下列属性，**不定义生产属性清单，也不允许真实返回照此省略已经取得的其他关联属性**。

```jsonc
{
  "result": { // 保留：说明读取依据，不是新创建一个 Result。
    "ref": "precheck-result:example", // 保留：与请求对应，读者能核对确切结果。
    "coverage": "complete", // 保留：声明范围覆盖完整；不保证每种属性都有值。
    "readiness": "plan_ready" // 保留：可进入 Plan；不保证所有语义判断正确。
  },
  "accounting": { // 保留：整份 Result 的对账；不能用本页代表数代替。
    "total": 20, // 保留：本次总共交代 20 个源条目，不是 20 个阅读入口。
    "scope_condition": [ // 保留：按范围用途和处理条件交代条目，避免把辅助文件算成照片。
      {
        "scope": "source_media", // 保留：这些是来源媒体；其他条目可能是辅助或排除项。
        "condition": "usable", // 保留：能使用；与是否纳入范围是两回事。
        "count": 20 // 保留：这个范围与条件组合下的数量。
      }
    ],
    "routes": { // 沿用：核对每个源条目是否能经代表入口或异常说明找到。
      "frontier_only": 20, // 保留：仅由正常代表入口交代的源条目。
      "exception_only": 0, // 保留：仅经异常说明交代，如无法生成图像的损坏视频。
      "frontier_and_exception": 0, // 保留：同时在两条路径出现的源条目，单独计数以免重复相加。
      "residual": 0 // 保留：两条路径都未交代的源条目；这里必须诚实暴露缺口。
    },
    "frontier": { // 沿用：整份 Result 的入口和覆盖统计；这个名称不是新实体。
      "entry_evidence_count": 1, // 保留：共有 1 个默认入口，不是当前页返回数量。
      "coverage_memberships": 20, // 保留：各入口代表数量之和；交叠成员可能被多次计算。
      "represented_unique_source_items": 20 // 保留：被代表的源条目去重数，用于看出交叠覆盖。
    }
  },
  "items": [ // 保留列表、简化名称：原称 cards；每项是读取视图，不是 Card/Case 模型。
    {
      "evidence_ref": "evidence:E", // 保留：这条记录对应哪份证据材料，供后续精确引用。
      "access": { // 保留读取方式：沿用现有结构；不强制下载或向模型发送图片。
        "kind": "local_artifact", // 沿用：这是本地派生材料，不是源媒体路径。
        "locator": { // 沿用、可评估简化：定位的编码层，本身没有业务身份。
          "kind": "local_file_path", // 沿用：说明 value 是本地文件路径，不是 URL 或另一个引用。
          "value": "/example/renditions/R.jpg" // 保留：Agent 可选择打开的图片；路径出现不等于已看图。
        }
      },
      "observations": [ // 保留属性容器：此处只描述 E；具体属性清单不固定为本例这几项。
        {
          "name": "pixel_dimensions", // 保留属性名；本例为派生图尺寸，不是源照片尺寸。
          "status": "available", // 保留：有实际值；与缺失、失败、未检查分别表达。
          "value": { // 有值时保留：属性值形状由该属性语义定义，不复制一套图像实体。
            "width": 640, // 本例属性的必要分量：宽度，单位像素。
            "height": 457 // 本例属性的必要分量：高度，单位像素。
          }
        }
      ],
      "qualifications": [ // 按需：对 E 的解释有限制时必须交代；没有限制不用编一条。
        {
          "code": "lower_fidelity_rendition", // 保留稳定类别：程序识别原因，不解析措辞。
          "effect": "limits_interpretation", // 保留影响：可以继续判断，但要考虑清晰度限制。
          "message": "这是缩小后的派生图，细小文字可能无法辨认。" // 保留具体解释：供人和 Agent 理解。
        }
      ],
      "source_items": [ // 保留归属：E 实际来源的条目及属性；本例只有 R，不放那 20 张成员明细。
        {
          "source_item_ref": "source-item:R", // 保留：这些属性描述的确切源对象。
          "locator": { // 保留源定位：来源路径和派生图路径不同，不能相互替代。
            "kind": "source_root_relative_path", // 沿用：路径相对于已绑定来源根目录。
            "source_root_ref": "source-root:example", // 保留：确定相对路径以哪个根目录为准。
            "value": "trip/R.jpg" // 保留：该源条目在根目录下的位置。
          },
          "observations": [ // 保留：R 已有的公共属性共同返回，不让调用方按摄影/地理类别拼接。
            {
              "name": "capture_time", // 示例属性：R 自己的拍摄时间，不是成员范围。
              "status": "available", // 保留：确实取得了这个时间。
              "value": "2026-05-03T12:05:00+08:00", // 有值时保留：本例明确带时区。
              "provenance": { // 有来源证据时保留：使时间可以质疑和复核。
                "tag": "EXIF:DateTimeOriginal", // 本例来源：取值的 metadata 标签。
                "offset_tag": "EXIF:OffsetTimeOriginal" // 本例来源：时区偏移依据；未记录时不能编造。
              }
            },
            {
              "name": "focal_length_mm", // 示例属性：实际焦距，单位 mm；与 35mm 等效焦距分开。
              "status": "available", // 保留：有值；不是仅仅支持这种属性。
              "value": 100, // 有值时保留：不要求未来所有照片都能取得焦距。
              "provenance": { // 有来源证据时保留：旧系统已有这项能力，迁移不能只保留字段名。
                "tag": "EXIF:FocalLength" // 本例来源：说明实际采集的标签。
              }
            },
            {
              "name": "content_sensitivity", // 示例属性：敏感性检测的执行/结果说明。
              "status": "not_checked", // 保留：未检查，不等于没有敏感内容。
              "basis": { // 此处必要：未检查的原因会影响后续判断。
                "code": "capability_disabled" // 保留：本例未启用；不能拿它掩盖尚未实现或未接入。
              }
            }
          ]
        }
      ],
      "represents": { // 保留含义分层：这里描述 E 代表的范围，避免和 R 自己的属性混用。
        "source_set": { // 保留可复用选择器：可直接交给现有 resolve；不是新增成员集合实体。
          "kind": "precheck_relation", // 沿用：按当前 Result 中的一种关系取成员。
          "origin": "evidence:E", // 沿用：从 E 出发；虽与上方引用相同，但选择器可独立传给 resolve。
          "relation": "represents", // 沿用：取“代表哪些素材”，而不是“实际从哪里产生”。
          "direction": "outbound" // 沿用：选择器的既有方向字段；不新增另一套短写协议。
        },
        "source_count": 20, // 保留便宜摘要：由关系去重计算，无须先读取全部成员才能知道规模。
        "scope_condition": [ // 保留成员组成：只统计 E 的成员；本例恰好与全局统计相同。
          {
            "scope": "source_media", // 保留：成员中这些条目的范围用途。
            "condition": "usable", // 保留：成员中这些条目的处理条件。
            "count": 20 // 保留：对应组合的成员数，不额外保存一份权威计数。
          }
        ],
        "observations": [ // 保留开放属性：描述代表关系；可以扩展，不固定时间/GPS等分类层。
          {
            "name": "capture_time_range", // 示例关系属性：成员已知时间范围，不是 R 的拍摄时刻。
            "status": "available", // 保留：可提供范围；完整程度仍需看下面的状态数量。
            "value": { // 有值时保留：范围与覆盖程度一起说明。
              "earliest": "2026-05-03T12:00:00+08:00", // 本例必要分量：已知成员时间的最早值。
              "latest": "2026-05-03T12:18:00+08:00", // 本例必要分量：已知成员时间的最晚值。
              "status_counts": { // 本例必要：避免把部分已知时间冒充所有成员的精确范围。
                "available": 20 // 本例有时间的成员数；若有 missing/failed/not_checked 等也要据实交代。
              }
            },
            "basis": { // 此处必要：说明这是推导值，不是对未知成员作了新调查。
              "summary": "由精确成员已有的拍摄时间计算。" // 保留可理解依据；不要求照抄这句文案。
            }
          }
        ],
        "basis": { // 保留压缩依据：关系为什么成立，与时间范围如何计算是不同问题。
          "summary": "本例按时间邻接形成候选，按格式优先选择 R。" // 示例实际方法；换算法可换内容，不改骨架。
        },
        "qualifications": [ // 按需：关系有实质限制时必须呈现，不能混到 E 的清晰度限制里。
          {
            "code": "bundle_members_not_visually_compared", // 保留稳定原因：本例没有全成员视觉比较。
            "effect": "limits_interpretation", // 保留后果：可作为压缩入口，但不能保证成员内容一致。
            "message": "未逐张比较成员内容；R 的观测不自动成为全部成员的共同事实。" // 保留具体限制。
          }
        ]
      },
      "roles": { // 沿用、待精简：可定位已准备的代表/边界/离群材料；不增加角色实体。
        "representative": ["evidence:E"] // 本例只是重复 E 的入口角色；单独看并非不可删除，其他角色导航需另行保留。
      },
      "available_expansions": [ // 沿用、待精简：告诉调用方已有的调查选项及规模，不是要求依次执行。
        {
          "include": "anchor_evidence", // 旧选项：只取 E 自身；本次已共同交付，默认是否还需提示待精简。
          "estimated_items": 1 // 保留成本估计的含义：该选项预计读取 1 项；未知用 null。
        },
        {
          "include": "prepared_targets", // 保留调查能力：查已有高清图/边界等目标，不生成新材料。
          "estimated_items": 1 // 本例已准备 1 个目标；不是强制每个代表都必须有 1 个。
        },
        {
          "include": "provenance", // 保留调查能力：读实际派生关系；不会返回所有被代表成员的明细。
          "estimated_items": 1 // 本例有 1 项直接来源；多步来源保持各自关系。
        },
        {
          "include": "coverage_basis", // 旧选项：覆盖依据；本次增加默认依据后，需检查提示是否仍提供额外价值。
          "estimated_items": 20 // 沿用现有关系规模估计，不是新 POI/图像调查数量。
        },
        {
          "include": "member_observations", // 保留调查能力：主动选择后才分页读取成员已有观测。
          "estimated_items": 20 // 本例有 20 个成员；默认返回不包含它们全部的明细。
        }
      ]
    }
  ],
  "page": { // 保留：复用现有分页，无新会话或批次实体。
    "total": 1, // 保留：本次入口选择共有 1 项；与 accounting.total 的 20 个源条目不同。
    "next_cursor": null // 保留：没有下一页；只表示此选择读完，不表示所有原图都被看过。
  }
}
```

### 每层只回答一个问题

| 位置 | 固定含义 | 与现有接口的关系 |
| --- | --- | --- |
| `result / accounting / page` | 本次绑定、全局对账、本页进度 | 复用现有字段；不把全局 accounting 改成选中代表的统计 |
| `items` | 本页阅读记录列表 | 待审稿替代原名 `cards`；没有 Card、Case 或 Item 的新业务实体 |
| `evidence_ref / access / observations / qualifications` | 正在读取哪份材料，以及该材料自身的属性和限制 | 复用已有 Evidence detail 的含义和图片定位；不新增图片实体 |
| `source_items` | 材料实际来源及其各自属性 | 从既有来源关系组装的视图；本例只有 R，不是那 20 个被代表成员 |
| `represents` | 代表范围及关于这项压缩的属性、依据和限制 | 复用现有关系；将原 card 的成员计数、集合和成员限定归到这一层，不重复保留两份 |
| `represents.observations` | 既有关系信息或可据实推导的具名摘要 | 替代固定 `facts` 分类；属性名、值和单位可演进，不要求新存储或预先收集所有成员明细 |
| `roles / available_expansions` | 已准备的角色与调查入口、读取成本估计 | 导航能力需保留，但仅重复当前 E 或已交付内容的提示待精简；不是已冻结层级 |

图片 E 来自 R、代表 20 张，这两项含义不能用同一列表承载。`source_items` 不是新的持久对象，也不改变 Result 中的 `derived_from`。多来源各自保持属性归属；多步派生的真实关系继续通过既有 provenance 读取，不能将“可覆盖的所有成员”当作“产生图片的所有来源”。若某个 Evidence 没有可证明的 Source Item 来源，明确返回空列表和必要限制，不猜一个代表来源。

属性状态和来源继续服从现有 Observation 规则。`capture_time_range` 是本提案中的关系摘要示例：只用已有成员时间，保留各状态数量；未知或未记录成员不能算成已验证，缺少可用时间时不得伪造范围。该属性的加入不授权新增地址、检测或视觉的全成员汇总。

默认阅读记录不再需要 `other_observations_available`：自身已有公共属性应共同交付。原卡片的成员类型等有用摘要可作为关系属性保留，不能以改用开放属性为由删去旧能力。`qualifications` 的归属明确到材料、源项或代表关系；其他未显示的准备目标之限制仍按原有作用域保留，不混写成当前 R 的限制。

### 必要含义与可继续简化的编码

| 项目 | 本轮判断 |
| --- | --- |
| `result / accounting / page` 里看起来相同的数量 | 本例只有一个代表才恰好相等；全局源条目、入口选择、单个代表的成员是三个不同计数范围，不可互相替代 |
| `access.locator` 和 Source Set 内重复的引用、关系名 | 目前复用已存在且有消费者的定位/选择器；它们不是新模型实体，日后简化要同步消费者，不能宣称属于社区强制标准 |
| `roles.representative` 重复当前 E | 本例冗余，推荐后续去除这种重复；需要保留边界、离群等已有材料的发现能力 |
| `available_expansions` 提示已默认返回的明细 | 推荐仅保留提供额外信息或控制的提示；本轮先逐项注明，避免未解释就删掉能力 |
| 把属性改成开放列表 | 框架可以通用，但属性名称、单位、状态与来源仍要明确；不能把 AI Album 曾采集的信息漏掉后归因于“框架只定义属性” |

这一轮只把必要性和疑点写清楚，供用户判断结构；没有把所有“沿用”字段认定为最终设计。

### 本次不改变的读取边界

- `expand` 的既有 include、`resolve` 的 Source Set 和精确成员摘要、`geo_summary` 的诊断作用继续保留。查更多已准备材料属于调查，不要求调用方为 R 的已有自身证据按类别反复拼接。
- 沿用 `page.limit / cursor` 和 `page.total / next_cursor / stop_reason`，以及 Result、action、selector、include、limit、排序绑定。按完整阅读记录的 JSON 字节分页；单项超限报错，不截断属性列表或伪装终页。图片未内联，字节预算不计算未打开的图片文件。JSONC 注释仅供文档审阅，不进入响应字节预算。
- `access` 只指向已经存在且绑定到该 Result 的可读取材料，不偷偷生成高清图、视频帧或重跑 PreCheck。路径返回、实际打开图片、Agent 使用证据是不同事实。
- 同一业务 JSON 不因 MCP 兼容习惯被要求向模型重复注入。传输层具体承载方式待实现验证；本提案不要求 Base64 或强制看图。
- Geo 采集策略仍是待核对现状；本接口只保留已有候选、实际查询依据及投影限制。Plan 新补查保持单独来源，不写回 Result。

### 验收与后续激活

本节只请求确认：**这条结构化返回是否准确表达“自身信息＋压缩关系”，并保持属性开放。** 最小样例不等于全部能力验收；摄影、地理、检测、视频和压缩差异仍由既有迁移台账逐项核对。

当前先在本目录原地收敛。内容验收后，再将已确认合约集中到稳定的 `docs/spec/contract/` 入口，并同步 schema、示例、引用和发布副本；本轮不创建或搬迁该目录。最终每个公开接口只保留一份当前权威定义，旧目录不再与它并列有效。D4 的固定摘要、`cards` 到 `items` 的命名及 MCP 返回需一起核对，不能只改文档后宣称代码已经交付。

开发不得为迁就实现自行改变已确认语义。属性扩展必须保持声明的类型、单位、归属和状态；改变这些含义须显式评审。最终能力完成要求同时验证正式合约、安装配置、生产装配、公开入口和结果交付；仅有组件或注入测试不算接通。真实数据从零验收另行安排。

## 当时生效条款（已被稳定合约替代）

### D4. Read：取齐与取对

四 action 都只读 immutable Result。input/output 的具体字段以 [Tool Schema](precheck-read.tool.json) 为准；原有 include 全保留。
review 默认提供 result/accounting/cards/page，不默认输出效果细节；include=execution_boundary 获取审计。
审计include返回累计费用摘要及attempts/page，每条attempt保留Provider/operation/结果、坐标、费用、
原观察时间和Result内source_set关联。historical/current按该Result的Run边界分类，同历史事件只计一次。
明细按原durable attempt顺序分页，输入execution_page（50默认/200最大）只控制审计；普通page只管cards，
两游标均绑定相同Result且彼此不能混用。该额外selector防止卡片分页与费用明细分页共用一个cursor。
公开累计数量若老资料无法证明为null，仍返回已知明细；不能从可见明细样本外推全量费用。
运行中的diagnostics只显示效果累计与分类；需要逐来源审计时，published Result使用此Read通路，
未封存Run保留既有journal证据但不把私有存储交给Agent。
每张卡 source_count 是 direct represents 去重 Source Items；关系记录保留一个源项一个 membership，
不允许重复边改变成员数。全局 memberships/unique count 保留跨卡重叠。空角色、省零状态是已知零；
未知计数不能省略成零。时间/类型/角色以外的事实不进入固定摘要，其原貌仍由 expand 完整读取。
保留 available_expansions 的 include+estimated_items，不删有用的读取成本估计；无法估算用 null。

page={total,next_cursor,stop_reason?}，next_cursor 必须存在，null 表示完整终页；total 精确。
按需 stop_reason=byte_limit。最大输出524288字节，完整项之间分页；单项超限明确错误。
review默认25/max100；expand成员/geo50/max200；resolve250/max1000。
页顺序：review入口既定顺序、成员源引用升序、geo纬度经度datum；绑定 digest/action/selector/include/limit/order。
page.returned、complete、重复 ordering/total 删除后，消费者仍验证实际数组长度、递增未重复游标、
非末页有推进、最终全量 count 与 membership identity。page cursor 不构成一个新的读取会话实体。

source_set 保留原表达式 explicit、precheck_relation(accounts_for/represents/outbound)、union、difference、
geo_coordinate(gpx_over_gps_exact_normalized_v1)。source_set_identity=SHA256(canonical selection)；
membership_identity=SHA256(canonical {result_ref,source_set,members})，members为排序去重引用。
不改变 Frozen Plan 的 source_set 表达式。两种 digest 都有当前消费者校验用途，保留。
prepared_targets 保留 target:{kind,ref} 的 Evidence/Source Item 两种目标；不能只剩 evidence_ref。
原 source_content_verification 格式与强弱核验含义保持，Apply 仍重新验证源内容。


### D5. Geo Observation 的唯一权威形状

每个 in-scope Source Item 均可通过 expand observations 得到 `address_candidate` 与
`nearby_place_candidates` 两个标准 Observation；使用现有 Result.observations，不新增模型、
注册表或 location/overall_status 包装。地址 value 保留 formatted_address/components；
nearby value 为非空候选列表，候选的 name/address/coordinate/category/distance 等可用证据保留。
当前name/address分类等候选字段随既有GeoCandidate.value原样保留，公开schema对已知结构类型检查，
扩展候选字段只作为数据，不改变通用Observation状态含义。近邻候选附provider_ref应移入可追溯审计，
普通Plan返回去除provider_ref而不去掉候选主体。每个Source Item每种组件最多一个权威Observation，
冲突来源通过qualifications/basis显式表示，不能多条同名观测让消费者任选。
查询坐标仍是独立 gps/gpx 观测；获取时代表坐标与源最终坐标不同时，在 basis 中保留投影依据，
不得把代表坐标强写成媒体 GPS。具体坐标 basis、所用 Profile 和 observation time 可追溯，
provider/request/cache/Work 的明细通过执行审计保留，不成为普通 Plan 的必填语义。

| 组件结果 | Observation | value |
| --- | --- | --- |
| success | available | 必须非空候选 |
| no_result | missing | 禁止；basis 说明已查询无候选 |
| failed（有限尝试终结） | failed | 禁止；basis/qualification 说明原因 |
| not_requested（策略关闭/没有调用） | not_checked | 禁止；basis 区分未启用、历史未记录等 |
| 没有可用坐标 | not_applicable | 禁止；basis 指向坐标缺失 |
| indeterminate | failed + geo_effect_indeterminate qualification | 禁止；Run 不因此获得普通完成资格 |

缺坐标/no_result/failed/按策略未请求地点均不单独阻塞 Plan；所有项无地点亦如此。
真正选定的获取尚在进行、确认尚未解决，不可当 completed；schema矛盾和丢成员失败仍阻止发布。
效果 indeterminate 继续遵守 Geo journal：停止新外部效果，不自动重试，不把它降格成普通 no_result。
Result readiness 仅保留既有非Geo前提（有可用入口、源条目处理闭合等）；缺 Geo 记录时按明确
not_checked+historical_geo_unrecorded 归一化，不能推断曾尝试；来源证据自相矛盾则 result_untrusted。

Geo 诊断改成每坐标 components:{address,nearby_places}，每项返回 outcome 的计数字典
（success/no_result/failed/not_requested/not_applicable/indeterminate），计数单位固定 Source Item，
因此可表示同坐标多份历史结果冲突而不选一个伪总体状态；计数各等于 member_count。
acquisition_status 对有最终坐标的两组件均有终结记录则 complete，仍未请求则 incomplete，
没有坐标则 not_applicable；这不是 plan_ready 判据。candidate_evidence_refs 只含真实候选，
无结果来源通过 source_set→expand 追溯，不能把空候选伪造 Evidence。


### D7. 旧证据与零 API 兼容

使用现有零公开 API 兼容政策：不保留旧 request/operation/响应字段路由。新 schema 一次替换，
同包更新所有 runtime 与测试消费者。旧不可变 Result 字节、摘要、引用不改，mutable store 不批量清理。
在 Result Read 和 Geo reuse 的现有 stage adapter 中调用同一个纯规范化函数，读取旧证据时
只映射能证明的含义，不为旧版本增加服务/版本路由。新 producer identity 使用
`builtin-geo-component-observations-v4`，新 Work 与旧身份区分，旧数据不被覆盖。

旧 v3 output.result.component_outcomes 在枚举/候选一致且来自真实逐组件Tool返回时足以规范化；
若producer.reused_from指向legacy升级器，则必须追溯原始证据，不能把升级器猜出的两项no_result
当作独立证明。该value即使曾误放missing candidate中，也只在工作输出归一化时提取，
绝不放行非法公开Observation。
更旧聚合结果：从 attempts/provider协议及已有记录能分别证明两个组件时转换；仅有 requests数量
或 aggregate missing 不足以证明两操作已执行。缺证据组件写 not_checked+basis（historical_geo_unrecorded），
不假造 no_result，不自动网络补查、不循环迁移。保留原作者、观察时间和历史授权用于审计，
不是当前 Run 的新授权。旧 published Result 本身不合法/摘要损坏则拒绝读取，不能偷偷修数据。

ordinary Read 对原本合法旧 Result 以新投影返回，derived readiness使用新非阻塞规则；
content digest始终验证旧封存字节，投影不是替换内容。有 active Run 的现场升级/恢复是另一项运维任务，
本包只在合成旧数据上证明规范化，不在本机数据库执行。


### D9. 规范校验与交换值边界

Tool outputSchema 是所有action返回的并集，用于MCP发现。运行时还必须按输入action选择
Tool Schema 中的responseSchemas[action]校验：控制的简单state不能让status省掉progress、reason或Result。
responseSchemas是以outputSchema为根解析的schema片段，复用同一份$defs；不复制字段定义，
编译时组合outputSchema.$defs与片段即可，verify_packet.py给出实际例子。
新Geo观测按name分支约束value形状，缺失/失败basis必须存在，观察完整度仍由语义校验负责。
公开error.code集合允许扩展但不得重用语义；所有新分支需明确code，不解析message。
合同内复用的access、basis、provenance等开放数据字段保留现有扩展语义，不把它们误当成任意行为指令。
该设计不把json_value的开放性用于掩盖尚未定义的必需字段。


## 消费者责任

Plan 通过受信任 Read 接受 complete 或有界 partial、且 readiness=plan_ready 的 Result，
不查找 integrity 常量或重建 Geo 获取状态。Apply 在准备阶段仍必须验证 Source Set 的
完整成员身份、冻结计划、源定位、源内容、冲突和文件系统安全条件。
消除返回冗余不取消任何这些检查。

分页游标只在同一 Result、action、选择器、include、排序与 limit 下有效。
独立的 execution_page 不能用作 cards 的 page。非末页必须有实际推进，终页必须对齐总数，
精确成员摘要必须以完整排序去重成员重算。禁止从一个样本页推断全量成员或历史费用。

## 错误

使用单一 error 对象的 code/message；相关代码包括 invalid_request、dataset_not_open、
result_not_found、result_unavailable、result_untrusted、result_inconsistent、
reference_not_in_dataset、reference_not_in_result、invalid_cursor、unsupported_include、
invalid_source_set 和 response_item_too_large。
不存在与其他 Dataset 中的子引用使用同一不可见结果，不能扫描其他 Dataset 来区分。
