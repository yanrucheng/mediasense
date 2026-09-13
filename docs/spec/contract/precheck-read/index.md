---
id: "precheck-read"
title: "MediaSense PreCheck Read Contract"
type: spec
status: active
created: 2026-08-26
updated: 2026-09-13
timezone: "Asia/Shanghai"
parent: "index-contract"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235D-precheck-compression-boundary"
superseded-by: ""
tags: ["mediasense", "precheck", "contract", "evidence"]
---

# PreCheck Read：当前合约

**第一里程碑已完成；第二里程碑及 metadata、历史检测和近上限中间页续读补修于 2026-09-10 通过用户验收，以 0.9.0 发布。** 本目录是 `mediasense.precheck.read` 的唯一当前合约位置。验收修订已闭合阈值表达、故障项续页和语义检查；已确认的概念模型保持不变。旧日期目录及已安装版本的副本仅说明历史行为，不与本合约并列有效。

[Tool Schema](precheck-read.tool.json)定义唯一交换值形状；[属性与交付义务](precheck-attributes.md)定义本期属性含义与准备要求；[完整合成用例](examples.json)覆盖正常、异常和多来源读取。下方 JSONC 注释供人阅读，不进入返回，不是第二套协议。

2026-09-13 已采用本地敏感性具名值扩展，保持 Observation、Source Item/Evidence 归属及分页结构。准确值约束见[属性义务](precheck-attributes.md#敏感性具名值2026-09-12-授权采用)；工程与隔离安装证据见[实施验收](../../../../openspec/changes/extend-local-sensitivity-observations/acceptance.md)。历史 V1 只读保留，本轮不授权日常部署。

## 一次读取回答什么

```text
review 返回（读取视图，不是存储树）
├── result：哪一份不可变结果，是否可用于 Plan
├── accounting：整份结果有没有完整交代源条目
├── items：本页阅读记录，按原选择顺序逐项交代
│   ├── 正常项
│   │   ├── evidence_ref / access：材料 E 的身份与读取位置
│   │   ├── observations / qualifications：E 自身的属性和限制
│   │   ├── source_items：E 实际来源的属性，例如原照片 R
│   │   ├── represents：E 代表哪些素材、关系属性、依据和限制
│   │   └── available_expansions：进一步调查已有材料
│   └── 故障项：evidence_ref / error，明确该项未交付
└── page：此选择是否还有下一页
```

一个缩略图 E 来源于 R，却可以代表 20 张照片。R 的拍摄时刻和地址属于 R，成员时间范围和压缩依据属于 `represents`。`items` 是普通列表名，不是社区规定的 Card/Case 实体。Representative 是 Evidence 的角色，不增加 bundle、属性注册表或读取会话。

## review 输入

```jsonc
{
  "action": "review", // 必需：只读操作，不开始准备。
  "dataset_ref": "dataset:example", // 必需：已打开的 Dataset。
  "result_ref": "precheck-result:example", // 必需：确切不可变结果，不自动找最新。
  "page": { // 可省略：复用现有分页。
    "limit": 1 // 本次最多 1 个入口；是示例选择，不是永久批大小。
  }
}
```

省略 `evidence_refs` 时按 Result 固定入口顺序读取。提供非空、去重的 `evidence_refs` 时，读取所选已准备 Evidence，最多 16 个引用，按引用升序分页；不新增或生成证据。例如已取得高清图引用后：

```jsonc
{
  "action": "review", // 相同读取操作和返回结构。
  "dataset_ref": "dataset:example", // 绑定 Dataset。
  "result_ref": "precheck-result:example", // 绑定同一 Result。
  "evidence_refs": ["evidence:R-highres"], // 精确选读已有材料，空列表不表示默认入口。
  "page": { "limit": 1 } // 对这个明确选择分页。
}
```

显式选择的高清/边界 Evidence 返回它自身的真实 `represents`，不自动继承另一个入口的成员。`accounting` 始终是整份 Result；`page.total` 是本次选择的总 Evidence 数。

## review 返回示例

以下合成 Result 有 20 张照片、一个入口 E。小例子只记录所示自身属性，不定义完整生产属性清单，真实返回不得照示例丢弃其他已有公共属性。两个廉价关系摘要均在本例中显示。

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
  "items": [ // 保留列表、简化名称：每项是读取视图，不是新的业务实体。
    {
      "evidence_ref": "evidence:E", // 保留：这条记录对应哪份证据材料，供后续精确引用。
      "access": { // 保留读取方式：沿用现有结构；不强制下载或向模型发送图片。
        "kind": "local_artifact", // 沿用：这是本地派生材料，不是源媒体路径。
        "locator": { // 沿用：定位的编码层，本身没有业务身份。
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
          },
          {
            "name": "media_type_counts", // 必需的廉价关系摘要：成员是什么媒体类型。
            "status": "available", // 这些类型已知；未知成员仍需在状态数量中交代。
            "value": { // 类型组成属于成员集合，不是 E 自己的格式。
              "status_counts": { "available": 20 }, // 已取得类型的成员数；其他状态非零也返回。
              "values": [ // 只列已知类型，不猜未取得值。
                { "value": "image/jpeg", "count": 20 } // 本例 20 个成员均为 JPEG。
              ]
            },
            "basis": { "summary": "由精确成员已有的媒体类型计算。" } // 无新采集。
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
      "available_expansions": [ // 保留：仅列提供额外信息的调查选项及规模，不要求依次执行。
        {
          "include": "prepared_targets", // 保留调查能力：查已有高清图/边界等目标，不生成新材料。
          "estimated_items": 1 // 本例已准备 1 个目标；不是强制每个代表都必须有 1 个。
        },
        {
          "include": "provenance", // 保留调查能力：读实际派生关系；不会返回所有被代表成员的明细。
          "estimated_items": 1 // 本例有 1 项直接来源；多步来源保持各自关系。
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

## 字段与空值规则

| 位置 | 固定义务 |
| --- | --- |
| result/accounting/items/page | 每个成功 review 都有；无可选项时 items 为 []，total 为 0，next_cursor 为 null |
| 正常 item 的身份、access、observations、source_items、represents、available_expansions | 全部必需。已检查为空用 []，不以省略制造“未读取”歧义 |
| 故障 item 的 evidence_ref/error | 只用于已定位的材料不可读或单项超限；保留原位置，不带正常项字段。引用说明谁失败，error 说明原因 |
| qualifications | 有实质限定时出现；没有则省略。归属于材料、来源或关系，不混合主体 |
| observations | 保留该主体所有已记录的公共属性及必要缺口说明；不含私有 Work、向量、缓存或原始日志 |
| roles | 仅在存在其他已准备的 representative/boundary/outlier/conflict Evidence 时返回，引用不包含当前 E；无其他角色时省略 |
| unassigned_prepared_evidence | 已准备但没有这些角色的其他 Evidence 引用，非空才返回；避免角色列表导致材料隐藏 |
| available_expansions | 只提示能提供额外信息的 prepared_targets/provenance/coverage_basis/member_observations，estimated_items 未知用 null；不重复提示已返回的 anchor_evidence |

具名属性复用 Observation，不再保留固定 `facts` 分类或 `other_observations_available`。每个正常项的关系中必须各有一条时间和类型摘要，包括缺值时的状态与计数；普通属性在同一主体内不得重名，检测按 detector/input 区分，详见[属性义务](precheck-attributes.md)。这些摘要从现有成员信息推导；不为此获取全成员图像、地点或检测。Source Set、定位层复用现有格式，其重复引用用于独立调用，不再添加短写别名。

### 来源的确定

`source_items` 是材料实际表达的来源对象，不是被代表的全部成员：

- E 直接复用源条目时，取该源条目；E 派生自其他 Evidence 时沿 `derived_from` 追到实际内容来源，去重并按源引用排序。视觉材料通常来自照片或视频；GPX 的文字摘要等非视觉 Evidence 也可以实际来自辅助源项，不能因源项不是照片而丢掉来源。
- GPX、侧车和地图结果可能是某个属性的依据，但不会因此成为“照片的画面来源”；它们在该属性 provenance 中保持引用和作用。不得把 relation 覆盖成员当作 derivation 来源。
- 一张图由两个原照片产生时分别返回两个 Source Item 和各自属性；视频联系表来自多帧但同一视频只返回一个视频源项。完整中间链通过 `expand provenance` 读取。
- 没有可证明来源的合法 inline Evidence 返回空 source_items，并说明 `source_lineage_unavailable`。已有 `derived_from` 边断裂、循环或指到 Result 外则 result_inconsistent，不能用空数组降格。
- 源引用、属性、关联候选和限定都属于确切 Result。Source Items 不因本次查询被创建，源定位也不证明 Agent 已打开文件。

### 代表关系的确定

`represents.source_set` 复用 `precheck_relation/represents/outbound`。source_count 和 scope_condition 由其完整、去重成员计算，每条关系对应一个源项；其他入口可与它重叠，全局 memberships 与 unique 计数区分这种重叠。

同一已记录总体依据可直接返回；成员依据不同则 basis 说明 `member_specific`，通过精确成员及 `expand covering_evidence` 回溯具体依据。局部限定带真实 occurrences。不得挑一条依据当全组共同依据，或用自由文字猜出未记录的算法。历史依据缺失时明确 qualification，不新造事实。

## 其他操作及与 review 的衔接

| 操作 | 选择和 include | 保证 |
| --- | --- | --- |
| expand 源项 | source_item_refs，最多16；source_item/observations/covering_evidence | 返回请求的完整字段；[] 表示请求后确实为空 |
| expand Evidence | evidence_refs，最多16；anchor_evidence/prepared_targets/provenance/coverage_basis | 读取已有直接材料与关系；不递归获取新证据 |
| expand 成员观测 | 单个 evidence_ref；仅 member_observations | 复用 page，按源引用排序；只读已有成员观测 |
| resolve | 现有 Source Set 表达式 | 精确成员、稳定分页、可重算 source_set_identity 与 membership_identity |
| geo_summary | Result 与 page | 按坐标的组件状态诊断，不替代默认代表的地点属性 |

review 取得 prepared_targets 引用后，可用 review.evidence_refs 一次读取对应材料自身信息和关系。expand 的旧 selector 和 include 继续存在；源项和普通 Evidence expand 仍是原子有界批次，不接受 page，多项合计超限应缩小选择。单项超限仍明确失败，不能声称缩小批量可解决。只有 member_observations 的 expand 使用分页。

resolve 的 explicit、accounts_for、represents、union、difference、geo_coordinate 表达式及两种摘要算法保持。未知/外 Dataset 子引用统一返回不可见错误，不扫描其他 Dataset。成员身份读取不等于读取图片或通过源内容校验。

精确集合规则在此固定：

- explicit 选择列出的 Result-local Source Items；Result/accounts_for 选择全部已交代条目，包括辅助、排除和异常项；Evidence/represents 选择该 Evidence 的直接去重成员。
- union 是子集合去重并集；difference 是 base 减去 subtract；所有引用必须在同一绑定 Result 内。列表顺序不改变成员，但 Source Set 表达式自身的摘要保留其原有结构。
- geo_coordinate 的 `gpx_over_gps_exact_normalized_v1` 仅在 source_media 中选择：优先可用 GPX，否则可用 GPS；经纬度按归一后的数值及 datum 精确相等，不四舍五入或地理距离合并。改变这个选择规则必须使用新的明确身份，不能让旧表达式静默改变成员。
- resolve 成员按 source_item_ref 升序。`source_set_identity = SHA256(canonical(source_set))`；`membership_identity = SHA256(canonical({result_ref, source_set, members}))`，members 是完整排序去重引用。canonical 使用 UTF-8 JSON、对象键排序、不转义非 ASCII、无多余空格；同表达式与全量成员可重算，不能用当前页代替 members。
- 页面消费者验证不重复游标、有实际推进、最终数量及 membership_identity。不得只信 total、某个 complete 标志或样本页。

## 分页与失败

现有 page 机制继续使用，无读取会话：review 默认25/最大100；显式 Evidence 选择最多16；expand成员与geo默认50/最大200；resolve默认250/最大1000。limit 是请求上限，不保证恰好返回那么多，也不是 Agent 永久阅读预算。

- 游标绑定 Result digest、action、selector、include、limit、order 和位置。不能跨 Result、选项或排序复用；错配返回 invalid_cursor。
- 成功页必有精确 total 和 next_cursor。对 review，每个选中 Evidence 占一个位置，返回完整正常项或明确的故障项；两者都计入 limit 和 total，故障不改变顺序、Result、accounting 或总数。null 表示这些位置已全部交代，不表示所有证据读取成功或原素材都已看过。
- 结构化响应最大524288字节，按紧凑 UTF-8 JSON 计算。正常项和故障项均整体装入页面；图片未内联，不计算文件载荷。下一项单独可放入而当前页余量不足时，stop_reason=byte_limit，游标仍指向该项，下一页继续；不能把页余量不足报成单项超限。
- review 的完整正常项连同必需的单项页封套仍超过上限时，在该位置返回 `evidence_ref + error(response_item_too_large)`。不截断属性或候选列表，不冒充完整交付。故障项本身要简短，不携带导致超限的原始值；它可随正常项同页返回，也可单独成页，游标从其后继续。禁止没有记录的跳过。显式 evidence_refs 选读也遵守相同规则。
- 多来源记录仍作为一个完整项；超过上限按上条交代。调用方可调查更小的已有来源 Evidence。Read 不为适配响应临时生成新的拼图、summary 或 Result。非 review 的原子 expand 超限仍返回调用级错误；缩小批量只解决多项合计超限。
- 已封存派生文件缺失、损坏、越界或与封存身份不符时，review 在原位置返回 `evidence_ref + error(evidence_unavailable)`，不提供伪可读路径，不将未返回属性填成空数组。其他正常项继续可读。Reader 根据封存证明验证；路径随后因磁盘变化失效仍可能发生，不能承诺未来文件一直可用。
- 上述故障项只处理可定位的局部读取失败。Result 封存字节及引用完整性与派生文件当前可用性分别验证；已定位的派生文件损坏不能单独成为拒读整份 Result 的理由。Result 本身不可信、成员顺序无法确定、关系损坏、非法请求或未知实现异常仍是调用级错误，不得伪装成局部失败后继续。
- 一个已准备属性的 failed 是普通成功数据，不等于整个调用失败。未知实现异常不得伪装成 Run paused/blocked，应按 Host 既有失败诊断返回。

### 正常项 → 故障项 → 后续正常项

合成 Result 有 E1、E2、E3 三个入口，本例为便于阅读选择 limit=1：

| 请求 | items | page |
| --- | --- | --- |
| 首次读取 | E1 的完整正常项 | total=3，next_cursor 指向 E2 |
| 沿该游标读取 | E2 的故障项，如下 | total=3，next_cursor 指向 E3 |
| 沿下一游标读取 | E3 的完整正常项 | total=3，next_cursor=null |

```jsonc
{
  "evidence_ref": "evidence:E2", // 必需：交代原选择中的这一项，后续可精确重读。
  "error": { // 必需：本次未能交付这项证据；不是 Result 中的新 Observation。
    "code": "evidence_unavailable", // 必需：材料不可读；单项超大时用 response_item_too_large。
    "message": "派生图损坏；本项未交付，后续项仍可读取。" // 必需：简短解释，不重复材料内容或引用。
  }
}
```

[合成用例](examples.json)分别给出文件损坏和单项超限的完整三页请求/返回，包括整页只有故障项的情况。500 个入口中第26个损坏时同理：limit=25 的第二页可以返回第26项的错误和第27—50项的正常记录，再继续第51项；若先达到字节上限则按实际位置提前分页。最终交代了500个位置，其中一个未交付，不能宣称500项证据都已读到。

继续阅读无需新的跳过参数、恢复 Tool 或读取会话。调查失败项时可用现有 review.evidence_refs 精确重读，或通过其已有关系调查其他材料；后续文件恢复必须符合原封存身份，不能为消除错误修改 Result。

review 的 execution_boundary 仍按需通过 include 返回。execution_page 独立控制 attempts，绑定同一 Result，不能与 items 的 page 混用。效果未知为 null；一页样本不能外推全量费用。必需封套或附审计本身导致最小返回超限时，返回调用级 response_item_too_large，不归咎于某个 Evidence；调用方可移除可选审计或缩小 execution_page 再读取。不能挤掉证据字段，或将本可独立交付的项报为超大。

execution_page 默认50/最大200，按原 durable attempt 顺序。每条 attempt 保留 provider/operation/status、输入坐标、实际 provider_requests、可证明的 billable_units、原观察时间及 Result 内 source_set；current/historical 以这份 Result 的 Run 边界划分。同一复用历史事件不重复计费，未知累计仍为 null；已知明细可以返回但不能外推未知总数。无外部效果必须有可证明的零效果依据，不能把缺日志当零。

### 错误代码

调用级失败只返回单一 `error`，必需 code/message，MCP isError=true。review 的两种局部故障使用上述页内记录，MCP isError=false；这表示页面成功交代了各项结果，不表示故障项已交付。故障项的 error 只含 code/message 和可选 diagnostic_id，evidence_ref 在外层出现一次。其他操作的调用级错误仍可按事实携带 evidence_ref/source_item_ref。没有读取会话或隐式重试。

| code | 含义 |
| --- | --- |
| invalid_request / unsupported_include | 请求形状、选择器组合或所选 include 不合法 |
| dataset_not_open | 当前 Host 未打开给定 Dataset |
| result_not_found / result_unavailable | 指定 Result 不在当前可见 Dataset / 已知 Result 暂时不可读取 |
| result_untrusted / result_inconsistent | 封存身份或内容不可信 / 引用、关系或计数相互矛盾 |
| reference_not_in_result / reference_not_in_dataset | 子引用不在绑定 Result；或请求显式给出的 Dataset 互相矛盾。不存在和其他 Dataset 的隐蔽子引用不加区分 |
| invalid_source_set / invalid_cursor | 精确集合表达式非法 / 游标绑定或位置不匹配 |
| response_item_too_large | review 单项超限用页内故障记录；封套/审计自身超限或原子 expand 超限用调用级错误，并说明实际范围 |
| evidence_unavailable | 所选已封存材料当前不可读；review 用页内故障记录，其他读取用调用级错误，不假装有可用路径 |
| host_operation_failed | 未预期实现错误；保留 diagnostic_id，不转成正常 Run 状态 |

代码可按既有扩展规则增加，但不得重用现有含义。客户端不理解某种传输时不能据此编造成功；它是集成验收失败，不是媒体属性 missing。

## Geo 状态、历史和效果

地址和附近地点的属性语义见[属性义务](precheck-attributes.md)，获取权限和请求上限见[Geo 合约](../geo-query/index.md)。success→available；no_result→missing；有限终结失败→failed；未请求→not_checked；无坐标→not_applicable。indeterminate 保留效果不确定限定，不伪装成普通缺地点；有限再试与显式恢复资格遵循 Geo D6。后继成功不消除历史未知 attempt 或费用，未解决服务前提的 Run 不发布本次 Result。

缺坐标、no_result、已终结已知失败或策略未请求，均不单独阻止 Plan。尚在确认、执行或效果不确定不能假装终结。按坐标诊断仍保留逐组件 Source Item 数量和 candidate_evidence_refs，仅指真实候选。

geo_summary 按纬度、经度、datum 稳定排序，复用 page。gps/gpx/combined 的状态数量分别保留；同坐标出现多个历史组件结果时，address/nearby_places 各返回 outcome 数量，每一组件之和等于 member_count，不挑一个伪总体状态。对有坐标项，两组件均有已终结记录时 acquisition_status=complete；仍未请求或效果不确定为 incomplete；没有最终坐标为 not_applicable。该状态不替代 readiness，也不证明候选正确。candidate_evidence_refs 只含真实可读候选；无候选来源沿 source_set→resolve/expand 追溯。

现有 Geo 采集单元与逐项投影已在第二里程碑完成针对性实现核对，证据见迁移台账。该策略的价值或阈值不由本合约预先认证；必须输出真实查询点、源坐标依据及复用限制。Plan 新补查取得独立证据，不修改 Result。

旧 Result 先验证原封存字节，再只读投影。保留能证明的原值、时间和来源；缺失新字段以 historical_unrecorded 说明，不能捏造成功、逐组件无结果或新授权。旧版 Geo 规范化保留先前的证据约束：聚合缺失和请求数量不能证明两组件都执行过；升级器猜出的两组件 no_result 也不是原始证据，必须追溯真实 Tool 组件结果、attempts 或 provider 协议。无证据的组件明确 historical_geo_unrecorded，不循环迁移或自动网络补查。非法旧 Result 拒绝，不修数据。

## MCP 传输

业务数据只定义一份。当前 MCP 适配使用 structuredContent 传递本合约对象，content 为空；Host 不额外序列化整份 JSON 到 TextContent。客户端必须把这份结构化信息送入模型一次。不支持该路径的客户端不能通过集成验收；不得以空内容冒充成功，也不假定 Host 能知道模型实际看到了什么。其他适配可以选择能实现单份交付的载体，业务结构、属性和失败含义不变。

图片通过 access 的现有本地路径/源项/inline读取形式提供，默认不返回 ImageContent 或 base64。Agent 自主决定打开哪些图片。返回路径、接口已读、图像实际进入上下文和被合理使用是四种不同证据，Tool 不宣称模型已经看过或理解。按 action 校验 outputSchema；调用级错误 isError=true，成功页面中的局部故障或属性失败 isError=false，客户端必须保留这些局部失败，不能只看 MCP 成功标志。

## 完成与变更

对象身份、来源与表示归属、范围、属性状态和分页承诺是必须保持的契约。具体算法、模型、标签、并发和属性扩展按[模型](../../../design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)开放。更改已命名属性单位、作用域、必需能力、错误或调用形状须显式变更合约，不能修改测试掩盖实现偏差。

本目录的 schema、JSONC 和 examples 必须互相符合。[合约检查](../../../../tests/test_precheck_read_contract.py)同时验证结构、必需关系摘要、主体内属性唯一性、已有 V1 profile 的实际分类值和多页连续结果；删除摘要、重复属性、吞掉故障项或重复游标都必须被拒绝。纯分类函数比较不运行检测器、模型或 PreCheck，也不能证明生产装配已接通。

按用户确认的收尾条件，Observation 状态／值检查已限定在正式 observations 容器内，合法嵌套扩展正例与非法 Observation 反例均通过检查，第一里程碑完成；本次收尾未改变主体契约。第二里程碑从安装配置→生产装配→公开入口→结果交付验证后才可称能力 implemented。代码、发布快照的实际证据与仍未认证事项见[迁移台账](../../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。

### 本地模型执行读取（敏感性验收补修）

`review include=["local_execution"]` 返回封存的本地模型预算、汇总及批次明细，使用已有
execution_page（默认50/最大200）；本次不得同时请求 execution_boundary。
证据 page 与执行 execution_page 独立，仍遵守524288字节、完整项与显式超限规则。
字段含义沿 [Run 执行诊断](../precheck-run/index.md#本地模型执行诊断敏感性验收补修)。
Read 不加载模型、不查私有 Work；旧 Result 未封存执行数据时 status=not_recorded、预算null、
models/batches为空，绝不假造零成本或从可变数据库补写历史。

封存和 Read 共用敏感性输入关联校验：available/failed 观测必须属于真实 Source Item，
input_evidence_ref 在同一 Result 且沿实际 derived_from 链回到该源；区域尺寸与实际输入
Evidence 的尺寸证明一致。represents 不是来源证明，单条 Observation 合法不能代替此检查。
