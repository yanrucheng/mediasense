---
id: "precheck-attributes"
title: "PreCheck 属性与交付义务"
type: spec
status: active
created: 2026-09-09
updated: 2026-09-12
timezone: "Asia/Shanghai"
parent: "precheck-read"
depends-on:
  - "design-260825-2235D-precheck-compression-boundary"
superseded-by: ""
---

# PreCheck 属性与交付义务

框架固定对象和关系，本页固定本期能力的属性含义。属性仍使用 `name / status / value / basis / provenance / qualifications`，不新增 Attribute 实体或注册服务。相应值形状只在 [Read schema](precheck-read.tool.json)中定义一次；Run 准备规则引用本页。

## 共同规则

| 字段 | 要求 |
| --- | --- |
| `name` | 必需。稳定含义；未知名称可以扩展，不能复用旧名改变单位或归属 |
| `status` | 必需。`available / missing / failed / not_checked / not_applicable` 含义与主合约一致 |
| `value` | 仅 `available` 时必需，不能用 null 冒充可用值；其他状态禁止携带 |
| `basis` | 失败、未检查、不适用时必需；Geo 两组件始终必需；说明原因、推导或适用范围 |
| `provenance` | 有值时保留所有已知、影响解释的公开来源。源标签、侧车来源、profile、观察时间等有则保留，缺则说明，不编造 |
| `qualifications` | 有实质限制或冲突时必需，归属于它实际影响的属性 |
| `confidence` | 仅当 producer 提供有明确含义的分数时返回，不自动补一个统一置信度 |

同一对象的普通属性每个名称最多一条。多个来源冲突保留被选值的来源、已知备选与限制，不能让调用者在多条同名观测中任选。敏感性检测是有明确输入的多次检测：以 `name + detector_identity + input_evidence_ref` 区分，不能覆盖或合并为一次全视频检测。关系摘要同名最多一条。

不完整也可以有 `available` 值，例如成员时间只有部分可知，但必须附实际覆盖和限制。`missing` 表示查过无值；源字段未采集、能力未启用和历史未记录都不能伪装成 missing。producer 未实现或生产未接通是开发缺口，不能成为发布版忽略能力的合法状态。

## Source Item：来源媒体自身

对本期范围内每个可处理源媒体尝试廉价批量 metadata。以下字段适用时应尝试采集；无值如实记录，不只为最后视觉代表保留。侧车参与取值时，provenance 指向实际侧车 Source Item 和标签。标签优先级是可替换方法，但有效 profile、冲突及选择依据必须可追溯。

| 属性 | 可用值及单位 | 迁移/归属要求 |
| --- | --- | --- |
| `capture_time` | 含时区的时间字符串 | 保留已验收时间语义、原候选和 fallback 限制；是该媒体时刻，不是组范围 |
| `camera_make / camera_model` | 非空字符串 | 保留 EXIF/XMP/QuickTime/XML 等已支持来源；不把 Encoder 随意当相机真名 |
| `camera_serial_number / camera_firmware` | 非空字符串 | 旧系统曾提取，继续本地采集和读取；不作为授权向外发送的一般 metadata |
| `lens_model / lens_serial_number` | 非空字符串 | 旧系统能力保留，不因少见而漏项 |
| `focal_length_mm` | 大于零的实际焦距，mm | 不与 35mm 等效焦距合并 |
| `focal_length_35mm_equivalent_mm` | 大于零的等效焦距，mm | 原始标签有值时保留；不能从实际焦距无依据推算 |
| `aperture_f_number` | 大于零的 f 值 | 例如 2.8，不提前写成“大光圈”语义结论 |
| `exposure_time_seconds` | 大于零的秒数 | 1/25 秒归一为 0.04；原值与转换依据可追溯 |
| `iso` | 大于零的感光度数值 | 缺值不能写成零 |
| `source_pixel_dimensions` | width、height，正整数像素 | 源文件实际尺寸；不能用派生图、历史原片缓存或代理前尺寸替代 |
| `orientation` | EXIF 含义的 1—8 整数 | 源观测；派生图已旋转不抹掉源值 |
| `media_type / source_file_format` | MIME / 源容器或格式字符串 | 两者是不同含义；旧格式值保留来源，不靠后缀伪造成功提取 |
| `gps_coordinates` | latitude、longitude、datum | 内嵌或侧车坐标；不被获取单元的查询坐标覆盖 |
| `gps_altitude_meters / gps_version` | 米数 / 非空字符串 | 保留旧系统可取得的信息与基准/来源；高度不改变水平坐标含义 |
| `gpx_coordinates` | latitude、longitude、datum | 已采用 GPX 的匹配候选；保留轨迹来源、匹配方法、时差和冲突，不覆盖原 GPS |
| `address_candidate` | formatted_address、components | provider 候选，非确认地点；获取状态服从 Geo 合约 |
| `nearby_place_candidates` | 非空候选列表 | 保留已取得的名称、地址、坐标、类别、距离等；有限结果不是穷尽声明 |
| `video_probe` | duration_seconds、源 width/height；已知 frame_count/frame_rate | 对被选中进行视频准备的源项执行；其他源项可为 evidence_not_prepared，不能假造时长 |
| `content_sensitivity` | detector_identity、profile、labels | 归属于源项，但必须携带实际 input_evidence_ref；只说明该次输入的检测，不推广到未检查帧或其他成员 |
| `source_content_verification` | 沿用 Observation 的外层 status；value 内为 profile/value/size_bytes/observed_at/producer | resolve 将它投影成既有 verification 格式；不在 value 重复 status，不升级核验强度 |

一个上游提取器整体失败时，可用 `source_metadata: failed` 说明受影响的已声明 metadata 能力，禁止用空数组暗示已完成。已取得的其他属性仍保留。旧 Result 不具备本期新属性时，读取投影可标记 `not_checked + historical_unrecorded`；新 producer 不得使用该理由省略义务。

### 敏感性分数与阈值

`score` 是 0—1 范围内的检测分数；`threshold` 和 `mild_threshold` 是有限、非负的比较阈值，可以大于 1。它们不是概率，不能限制在同一个数值范围。

本期沿用的两个 V1 profile 保留实际 label、score、threshold、mild_threshold、sensitive 和 mild_sensitive。其比较语义是 `score >= threshold` 和 `score >= mild_threshold`。例如 NSFW profile 的 normal 标签返回 score=0.999、threshold=99、mild_threshold=33，两种判定均为 false；NudeNet 中相应不触发敏感判定的标签也保留这些有效阈值。禁止将阈值截到 1、删除已记录值或改变分类算法来满足 schema。

这是对现有 profile 表达能力的保留，不新增一个“禁用标签”字段。以后更换 profile 必须使用相应身份并交代有效语义，不能重用 V1 名称改变已有判定。分类值的保留不证明检测器已在安装版接通。

## Geo 候选的 basis

两个组件各保留实际 `outcome`、`query_coordinate`、`observed_at`、有效 profile（已知才返回）。nearby 的已请求 radius/max_places 必须可读；有效范围若比请求更窄也要说明；未返回有效值时未知，不能把请求上限写成实际搜索完备范围。

候选距离相对于其查询点。实际查询点与源项坐标不同，basis 保留投影依据和适用范围，不能把复用候选说成源项独立查到。provider_ref 和请求尝试通过现有 execution audit 读取。默认观察值不灌入请求日志或私有 Work。

## Evidence：派生材料自身

| 属性 | 必需含义 |
| --- | --- |
| `pixel_dimensions` | 当前派生图 width/height；已有 profile 保留，和源尺寸分开 |
| `video_frame` | sample_time_seconds 为请求目标；decoded_time_seconds 为有证明时的实际解码位置；当前 width/height、已知有效 profile 保留 |
| `video_contact_sheet` | columns、width/height、有序 frames；每格给 Evidence 引用和采样位置，不给私有 frame_work_ids |
| `evidence_role` | 当前 Evidence 自身的 role；不输出内部 compression group/work ID。其他已准备角色的引用在 review.roles 中，二者不混用 |
| 其他已记录公共属性 | 包括角色或比较限制等，按其实际主体保留，不以默认展示清单为由静默丢弃 |

联系表中的 frames 按从左到右、从上到下的格子顺序。帧与视频时长、清晰度、部分解码失败均分别交代。对一个选中 Evidence，默认返回其已有直接属性和实际 Source Item 来源属性；完整派生链通过 provenance 调查，不把所有中间对象重复塞入默认返回。

视频位置以秒表示，相对于源视频流起点，必须为有限非负数。`sample_time_seconds` 是准备时请求的位置；片尾目标可以等于容器时长，但不证明该处存在一帧。`decoded_time_seconds` 只在实际呈现时间戳（PTS）可证明时返回，basis 保留真实生产者、时间依据及选择方法。历史材料缺少该字段时实际位置未知，不能把请求位置补写为实际位置，也不能回写已封存 Result。联系表每格沿用对应帧的请求与已知实际位置。

不同请求落在同一实际帧时，交付按可证明的帧位置去重；没有位置证明时可以按相同派生字节去重，但不能据此推断不同时间的视觉覆盖。只有一帧、两帧或稀疏时间线属于有限可用材料，不因不满足名义帧数而判源损坏。有限材料不承诺发现全部场景；相关限制由现有 qualifications 交代。

输入身份统一使用公开 Source Item/Evidence 引用。现有 producer 若把 frame_work_ids、input_work_id 或私有 group_ref 写进可见值，M2 必须在封存投影处替换为实际公开来源/格子关系，或删除仅用于执行的身份；不能把私有字段改名后原样暴露，也不能丢掉其承载的真实输入关联。

## represents：压缩关系

| 属性或关系内容 | 必需含义 |
| --- | --- |
| `source_set / source_count / scope_condition` | 现有精确选择器、去重成员数、范围及条件组成；计数由关系推导 |
| `capture_time_range` | 已有成员时间的 earliest/latest 和 status_counts；没有可用时间时 missing，计数放 basis，不伪造范围 |
| `media_type_counts` | 已知类型及数量、各状态数量；与时间相同，未知成员不能消失 |
| `basis` | 已记录的压缩方法/代表选择依据及 material limits；可为结构化数据，不要求自然语言固定句式 |
| `qualifications` | 代表性、比较覆盖、边界冲突或未知差异等限定；属于成员子集的限定保留 occurrences 和成员级追溯 |

时间、类型摘要只聚合已有廉价信息，不要求新采集所有成员的图像、检测和 POI。不存在可证明的共同关系依据时，basis 明确 member_specific，具体依据经 `expand source_item_refs + covering_evidence` 读取；不能选择一条成员依据冒充共同方法。

每个正常 review 项必须各有一条 `capture_time_range` 和 `media_type_counts`。无可用值时保留相应状态，并在 basis 中交代 status_counts；不能省略整条摘要。两者的状态计数都必须覆盖该关系的 source_count。普通属性唯一性适用于 Source Item、Evidence 和关系各自的 observations，也适用于 expand 返回；不同主体之间可使用同一属性名。页内故障记录明确未交付该项，不用空 observations 冒充正常项。

## 扩展与完成

[厂商知识契约](../manufacturer-knowledge/index.md)使用现有 provenance/basis/qualifications 交付规则选择和修正依据。`provenance.manufacturer_knowledge` 记录快照身份、来源与适用判断；其中素材依据必须引用对应 Source Item。`manufacturer.*` 扩展属性在 provenance.definition 中保留声明的类型、单位和含义，不能覆盖标准属性的语义。明确匹配且有依据的规则可从设备原生 Encoder 提取型号；未采用这种规则时，不把制作软件 Encoder 当作相机。

厂商规则可为 gps_coordinates 和 source_pixel_dimensions 选择成对标签，继续交付标准属性及既有主体、单位和下游意义。配对不得跨来源文件；尺寸只属于当前源素材。integer 扩展保留精确整数，包含超出二进制浮点精确范围的值。

新增属性沿现有 schema 的具名分支维护类型、单位、主体和状态，不新建注册服务。未知属性作为数据保留；如果其含义影响必须理解的限制，生产者必须通过既有 qualifications 交代，消费者不能将未知解释为已检查或不存在。

本页是能力义务，不是“字段越多越好”的要求。框架允许某属性不构成实现完成；[迁移台账](../../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)逐项记录旧用途、当前缺口、生产入口、交付和验证。模型、采样及标签可替换，业务信息不得未说明就省略。
