---
id: "eval-260912-0224-plan-memory-risk-audit"
title: "真实 Plan 运行取证：耗时、餐厅识别与记忆确认"
type: eval
status: review
created: 2026-09-12
updated: 2026-09-12
timezone: "Asia/Shanghai"
parent: "index-eval"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
  - "design-260825-2235D-precheck-compression-boundary"
  - "plan-work"
  - "default-organization-profile"
superseded-by: ""
tags: [plan, memory, interaction, provenance, performance]
---

# 真实 Plan 运行取证

这次运行暴露了三件不同的事：工具调用很慢，超时后的执行结果不透明；餐厅名称发生视觉误读；Agent 完成分组前没有与用户核对影响检索的用餐节点。工具层已有源码修复和验证，日常安装尚未包含这些修复。提高工具速度不会自动修复后两项。

用户在本次审计中明确更正店名为“鲁上鲁”。这是一项有来源的用户输入；本报告不把它改写成原 PreCheck 的地图观测，也不据此确认整天或全部成员的归属。以下事实与建议分开陈述；建议尚未改成产品合约或 Skill。

取证对象是用户指定的 cmux workspace `00309E9E-42AF-4484-AF6A-01B06A8CDDBD`、surface `1E22F6DB-7256-4C33-B752-4735C318D886`。当前树确认它是香港 fixture 的终端。恢复元数据仍指向旧的 9 月 6 日会话，因此没有以该记录代替实际运行：终端进程 `18263` 的打开文件、启动时间和最后答复共同绑定到下述 T 会话。

| 证据 | 精确定位 |
| --- | --- |
| T：原始会话 | `/Users/chengyanru/.codex/sessions/2026/09/11/rollout-2026-09-11T01-19-40-01a08c55-1097-7113-9fcf-d57cf2d50591.jsonl`；SHA-256 `7c3fc9d7894a4ee5d2269b38a8f3b328f7f8b0fd8cb6ddf2e521844ee3bb3ac4` |
| Dataset | `dataset:6581e19d4fe94e26a10e2f5ca1b34c9b`；工作区 `/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e` |
| 绑定 Result | `precheck-result:911f941ec5861716868dc5238596fe4bf903f6bd70a76ef3614a2fe931018e8f`；封存文件 SHA-256 `f287afc51c0c3e6785f97f400421ff560045b54190cd1f67cbd8472b06425928` |
| 原 Plan Work | `plan-work:5d657748-d779-42ca-9adc-addb36ee7c2d` |
| 会话结束时的本地草稿 | `/tmp/mediasense-plan-draft.json`；SHA-256 `27b792a3734ea3cec47dd3b061ac185c056fce74fd6a993fe8a3632b85614eeb` |
| 当时预览数据 | `/tmp/mediasense-plan-preview-data.json`；SHA-256 `49460bb9cae9a077383da758df61b19c06a7bbdfae93d19253236c939eda8dad` |
| 本次小型取证输出 | `/tmp/mediasense-risk-audit-20260912/`；含公开 Read 返回、候选摘要、原 Work 的只读账本摘录和两次临时 Plan 重放结果 |

`T:263` 等引用为 JSONL 一基行号。日志时间为 UTC，以下业务时间已换算为 Asia/Shanghai。只检查指定会话、已保存证据和相关实现；本次没有重新运行媒体准备、地图服务或外部模型，没有向原会话发输入，没有修改业务 Work 或冻结 Plan。两个验证用 Plan Store 写在上述 `/tmp` 目录。

包的 `scripts/verify.zsh` 已运行：原清单内 SHA-256 全部通过，整体校验因操作副本达到 `3,188,684,007` bytes、超过原 `2,000,000,000` 上限而退出 1。另逐项核对实际 `test-260831/260501-HK美食之旅`：2,134 个 manifest 媒体全部存在且 `derived_sha256` 相符；checksum manifest 自身也匹配仓库登记值。不能把扩展后的操作目录称为未改变的原始发布包，也不以历史分类名作为本次语义真值。

**工具修复可以确认到实现；本次业务会话尚未用上。**

| 现场事实或验证 | 结果与边界 |
| --- | --- |
| Plan 总历时 | 2026-09-11 01:36:33 进入 Plan，02:26:53 返回草稿，约 50 分 20 秒；包含 Agent 工作、证据读取、工具等待和预览生成，不能全算成模型推理或一次 Tool 耗时 |
| 两次 `update` | T:700、T:795 发起；T:765、T:843 均返回 `timed out awaiting tools/call after 300s` |
| 会话结束时的状态 | T:942 于 02:25:05 返回原 revision、`candidate_missing`、`seal_ready=false`；T:962 据此报告未保存、未冻结 |
| **后来实际发生的提交** | 原 SQLite `plan_requests` 中出现第一次请求 `request:plan-hk-20260911-candidate-01` 的成功回执，`created_at=2026-09-11 05:36:07` UTC，即当地 13:36:07，距离发起约 **11 小时 34 分钟** |
| 本次读取原 Work | `open`，已有 Candidate；revision `work-revision:9bd777ce-6650-40bb-9918-5fe3bc0726f8`，identity `sha256:e7f6e10fda9614dabddf6d24edfe88f8cf71defc61e29b7fbd4c05c482ffe93b`，未发布 Frozen Plan；“晋上馆”仍在其中 |
| 当前源码重放第一份候选 | 使用原 Work 保存的 40 条 decision notes 原始候选，分组、scope、其他结果与本地草稿相同；临时 `create` **8.352 s**，随后 `update` **15.228 s**，380 次 Read；`inspect` 返回 `seal_ready=true`、无结构错误 |
| 当前源码重放会话末尾草稿 | 使用 1 条合并 decision note 的草稿；临时 `create` **8.012 s**，随后 `update` **14.863 s**；没有用删分组、减成员来获得这一时间 |
| 相关回归 | `test_precheck_read_reuse.py`、`test_plan_update_execution.py`、`test_plan_update_mcp.py`、`test_plan_update_process.py`、`test_plan_update_replay.py`：**58 passed in 22.04 s** |
| 日常安装 | 全局包仍为 `0.10.0`，111 个 wheel 文件与旧 wheel 逐字节一致，wheel SHA-256 `f4e4ee4454ebb95c7eca7b87abc004eb7ac1fe6b78411c184b89ad9842c26f1e`；缺少新增的 `plan/_update_execution.py` 和 `runtime/_plan_update.py` |

迟到的回执证明“300 秒超时”和“随后尚无 Candidate”不能推出请求已终止。账本提供提交时间和请求身份，不单独证明提交瞬间的线程身份。与此相符的实现证据是：安装版 MCP 把同步 `update` 放进 `anyio.to_thread.run_sync`，没有 Plan 专用取消检查；旧版本在长计算开始前检查 revision，随后仍可能继续计算和提交。不能根据旧的 `candidate_missing` 直接用新 request ID 或另一份草稿推断先前执行已经结束。

当前源码 `f5a1763` 包含：`2bec2fb` 的 Read schema 验证优化，`fb168c3` 的已验证 Result 图复用和有界分页，`9ed7f8f` 的 Plan 执行归属、取消和进度，及 `f5a1763` 的并发提交后回执复查。实际落点见 [Read](../../src/mediasense/precheck/read.py)、[Plan update](../../src/mediasense/plan/work.py)、[执行上下文](../../src/mediasense/plan/_update_execution.py)与 [MCP 取消桥接](../../src/mediasense/runtime/_plan_update.py)。本次临时重放使用当前 checkout 的真实 Reader 和 Plan 组件，读取同一个封存 Result；没有把它称为日常 Host 已升级或整个 Agent 体验已重跑。`create` 首次加载结果，后续 `update` 复用同一 Reader，因此两个时段分别报告。

PreCheck 的重计算修复有独立的[验收报告](../../eval/sessions/260911-2128-precheck-throughput-recovery/report.md)：正式 metadata 首次从 82.747 s 降至 15.708 s，复用从 14.961 s 降至 3.992 s；本次选择范围的视频从 267 个有效帧、184 次抽帧失败恢复到 540 个有效帧、0 次抽帧失败，保留 1 个已知坏视频。该报告也明确日常 Host 未切换。旧 Result 不会因安装新代码而自动获得缺失帧；其改进需要对应的后继准备和结果，不能回写旧证据。

本次发现的 `invalid_cursor` 还应单独归因：T:188 的查询包含 `include:["execution_boundary"]`，T:213 延续其 cursor 时省略了该 include，T:228 因查询不一致拒绝；T:232 恢复参数后取得下一页。这里是调用者改变了 cursor 绑定的查询，不能与服务器慢、失去取消控制合并为一种工具缺陷。

**A：具名餐厅主要由视觉判断；地点证据既有限，消费也不完整。**

T:364 打开了入口 21，即 `0502/100MSDCF/DSC00227.JPG`；T:675 返回其高清 Evidence，T:679 再次打开。相同[高清图](</Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e/precheck/_artifacts/sha256/14/1451789d3cfa63069b8fcab0742957322601e5287716c496ed010cc3df984a5f.jpg>)显示人物背后的虚焦书法牌匾。T:691 却说“高清画面能读到……晋上馆”，T:692 随即生成相关章节。没有独立 OCR Tool 为这个词出具观测或可靠度；它是 Agent 的视觉解读。

该照片自身的 `address_candidate` 和 `nearby_place_candidates` 均为 `not_applicable`。整个 Result 的附近地点候选名称中也没有匹配“鲁上／魯上／晋上／晉上”的记录。所以这次“晋上馆”不是地图解析结果。用户的更正与图中的字形相符，但本审计不把经过用户提示后的图像复核说成独立盲测识别。

错误被用于 `05-02_晋上馆聚餐` 这个 314 项章节，其中“用餐与合影”组为 311 项、“车程与到店”为 3 项。确认店名、确认一次访问、确认这些素材均属于该访问，是三个不同范围的判断。即使一张代表照片读字正确，也不能仅沿 `represents` 就把其他来源的时间、地点和事件身份全部证明为相同。

用户追问“缺少地点还是解析不出来”后，对这 314 项做了完整的位置核对。通过公开 `resolve` 取得精确成员，再核对同一封存 Result 的逐项观测；统计和例子保存在 `/tmp/mediasense-risk-audit-20260912/lushanglu-location-summary.json`。这一步不认定该章节的全部成员均属于同一次餐厅访问。

| 位置来源 | 数量 | 实际含义 |
| --- | ---: | --- |
| 无内嵌 GPS，GPX 也未匹配 | 83 | 地址和附近地点为 `not_applicable / coordinate_unavailable`，没有可供这一来源发起地点查询的坐标 |
| 无内嵌 GPS，通过 GPX 最近点得到坐标 | 223 | 拍摄时间在 5 月 2 日 18:26:43—19:35:37；全部匹配到当日 **21:26:27** 的同一轨迹点，时间差 **6,649.92—10,783.907 秒**，即约 1 小时 51 分至 3 小时 |
| 文件中存在 GPS 字段 | 8 | 全部记录同一坐标，数值与上述 GPX 点相同；已抽查 MP4 的实际 ExifTool 输出，MediaSense 没有把该字段读成另一坐标。字段存在不证明它就是相机在用餐时直接测得的位置 |

该 GPX 文件的最早轨迹点就是 21:26:27。当前及本次 Result 记录的匹配上限为 `10,800` 秒；[匹配实现](../../src/mediasense/precheck/gpx.py)允许轨迹范围之外的最近点，只要时间差不超过上限。因此 17:57:03 的牌匾照片距离该点约 3 小时 29 分，未匹配；18:26:43 之后的 223 项则获得了这个更晚的坐标。这是时间容差与匹配方法的结果，不是 GPX 文件解析异常。

有坐标的 231 项，其地址与附近地点均记录为 `available`，没有该组的 Geo 接口失败。查询结果指向北京市海淀区人民大学南路，附近 10 项为打印店、商店、宿舍、厕所等，无“鲁上鲁”。这说明既有局部位置缺失，又有“位置值可用，但与拍摄时刻相隔很远”的证据质量问题。现有记录不足以确认该坐标就是用户到访门店的位置，也不能据此断言地图服务没有收录鲁上鲁。这里新确认的风险是长时间间隔匹配被下游当成普通可用位置消费；它与牌匾被误读为“晋上馆”是不同环节。

以下是本次通过公开 `PrecheckReadTool.read` 重新读取同一 Result 得到的候选摘要；没有发起新 Geo 查询：

| 草稿中的关键节点 | 已保存地点证据 | 可支持的判断 |
| --- | --- | --- |
| 5 月 2 日“晋上馆” | 入口 21 照片没有位置候选；相关视频的 10 个附近项为打印店、商店、宿舍、厕所等，无餐厅 | 有缺口，不能用该列表确认餐厅身份 |
| 5 月 3 日旺角晚餐，207 项 | 入口 60 的 10 个附近项含“泰之味东南亚美食坊”“一锅堂”，另有商铺和机构 | 存在可讨论的候选；既不能断定去过其中之一，也不能当作已穷尽餐厅名单 |
| 5 月 4 日太子烧味午餐，140 项 | 入口 67 返回 10 项，其中含 Bunmily；入口 70 的附近地点查询失败 | 餐食场景与店名之间仍有未解决的缺口 |
| Amber | 入口 90 的附近项是公交站、商铺、律师和咖啡店，没有 Amber；菜单图与源目录提供另一类线索 | 地图候选并非唯一依据；视觉识别有用，但来源须分别保留 |
| 5 月 5 日牛排晚餐，258 项 | 入口 139 的候选含 K11 ARTUS、Beef Ba 牛爸、商铺和厕所；入口 142 返回花园、商铺、福升小厨等 | 同一地址或附近候选不足以确认具体到访餐厅；泛称“牛排晚餐”保留了活动信息，却没有解决用户按店名回忆的需求 |

这不是一个只要改成“优先相信地图”就能解决的问题。当前及安装版 [Google adapter](../../src/mediasense/geo.py)相同，附近查询使用 `includedTypes: []`、`rankPreference: DISTANCE`，默认最多 10 项。通用附近地点不承诺识别实际到访场所，在密集商场和楼宇环境中尤其可能缺少需要的餐厅。有限候选、有效无结果和查询失败也有不同含义。

消费链还有一个具体缺口。T:447 确实尝试把 `address_candidate` 与 `nearby_place_candidates` 投影给模型，因此不能说它完全没读 Geo；但 T:449 的 19,835-token 输出被截断，可见尾部止于入口索引 36。后续 T:380 的分页只输出路径、成员数、时间范围，T:625 全量汇总只输出 `formatted_address`，没有展开后续的附近餐厅候选。数据在 Tool 返回值或脚本存储中存在，不等于已经进入模型的比较与判断。没有找到对上述香港候选逐项取舍、冲突处理或向用户展示候选的轨迹。

另一个不能忽略的限制是：本次 Result 明确记录 embedding 为 `disabled / no_local_profile_configured`。167 个入口和 2,136 项记账不等于所有潜在餐厅边界都经过内容检验。例如入口 60 单独代表 201 项。本审计没有逐个验证这些成员是否隐藏另一次访问，所以只将其列为压缩限制和需按后果调查的范围，不直接认定分组算法已错。

**B：中途语义确认缺失属实，最终冻结确认被绕过则没有证据。**

T 会话只有三个用户输入：处理数据、授权地理恢复的“行”、以及 T:263 的“直接进入 plan”。进入 Plan 后没有用户对餐厅身份、访问次数或顺序的确认。T:505 的“方向预览”只是说明将按日期和活动整理，没有给出具体用餐节点的候选或邀请用户补齐缺口；T:699 已宣布完整草稿并开始提交。最终没有请求冻结确认，是因为当时工具未能交付可冻结身份。这不能解释或补偿提交前已经缺失的语义互动，也不能被描述为已经越权冻结或 Apply。

Foundation 本来就要求 Agent 询问高影响不确定性、保留确认范围。[Plan Skill](../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md)也已有 conformance checkpoint、directional Preview 和高影响语义确认。问题不是“从未写过交互”，而是这些要求没有在这个结果中成立。

Skill 同时存在一处直接的准则冲突：第 90 行要求 `Ask the Human only when the unresolved branch is a value or retrieval preference they own.`，把提问收窄到价值或检索偏好；第 108 行却允许改变高影响语义边界的问题，第 128 行又承认用户提供地点含义的路径。T:270 保留的实际 Skill 读取输出也包含这一限制，因此不是审计后才出现的文本。用户能够澄清“去了哪家、去了几次、先后如何”，这些不是只能由地图供应商裁定的偏好问题。应当保持的是“用户陈述不能冒充 PreCheck/provider 观测”，并不需要禁止用户补充经历事实。这是有文本证据的责任边界冲突；没有反事实运行，不能断言它是本次模型行为的唯一原因。

Agent 还把“我已经核对”的语气当成了足够可靠的停止条件。虚焦字形被自信读错，说明仅加一个模型自报置信度阈值不能挡住本例。应结合证据质量、相互支持或冲突、候选缺失，以及错误会影响多少素材和什么检索入口来判断是否需要确认。

草稿自测的检索问题是“找牛排刀具”“找厨房合影”等已经出现在自己目录中的标签。它们证明了一部分可浏览性，却没有检验用户真正记得的餐厅名称和访问节奏。把未知餐厅改成泛活动名能避免无依据命名，但不能自动宣称记忆目标已满足。2,136 项各有去向、结构校验通过、与用户记忆对齐，需要各自的证据。

这次当前源码接受包含“晋上馆”的原候选并返回 `seal_ready=true`，恰好说明 [Plan Work 合约](../spec/contract/plan-work/index.md)的边界：它验证覆盖、引用、路径和版本；不识别餐厅，不证明名字真实。不能让一个确定性的结构校验结果替 Agent 和用户承担这项语义责任。

下面是按本次指定的两个 Skill 收敛后的责任分配。它复用当前实体；没有建议新增“记忆节点”Schema、Confirm Tool 或固定多 Agent 流程。

| 责任与决定权 | 权威归宿、状态和效果 | 必须能看见的依据与升级边界 |
| --- | --- | --- |
| PreCheck 准备来源信息 | PreCheck Result 固定观测、来源和压缩关系；Working Run 管运行；源只读，默认无外部效果 | 位置／视觉材料的实际状态、生产来源、采样损失、代表范围；Result 缺项或失真由其生产者修复，后继 Result 不改写旧结果 |
| Geo 有界获取 | 现有 Geo Tool 管候选、授权、请求记账和恢复；不拥有“到访了哪家”的决定权 | 精确查询点、半径／数量上限、provider、候选和失败；新增网络效果须获得相应授权，不能从已有候选继承无限补查权限 |
| 形成记忆结构、决定何时问 | Plan Agent 按用户目标和授权决定调查、合并、拆分、命名和提问；方法保持开放 | 显示支撑关键节点的证据、真实对立候选和缺口；重要名称、访问边界或先后关系仍不充分且用户可澄清时，请用户确认或明确延后 |
| 补充经历、偏好与接受不确定性 | 用户拥有未委托的语义确认和价值取舍；输入按所说的事件／成员范围进入 Plan | 区分经历陈述、组织偏好、接受残余不确定性和最终版本确认；确认一家店不能扩散成确认整天或全体成员 |
| 保存判断与确认的含义 | 既有 Plan candidate 的 `decision_notes` 配合现有 Source Set 保存实质依据和适用范围；`organization_preferences` 只放真实偏好；Preview 是视图 | 保留“视觉推断／Geo 候选／用户更正／未决”的区别；不把用户店名写成原 Result 观测，不把对话方向接受当作最终身份确认 |
| 持久化与执行安全 | Plan Work Tool 拥有 revision、幂等回执、结构验证和 seal；Apply 仅执行精确 Frozen Plan | 生命周期与请求取消必须真实；最终确认绑定确切 candidate identity；未确认不能 seal，未冻结不能 Apply，Apply 不补做语义决定 |
| 可复用判断知识 | 现有 Plan Skill 指向上述权威并提供充分性、提问和停止准则 | 修正互相冲突的准则；加载 Skill 不证明遵守、不构成授权，也不提供运行状态保证 |

**双锚一放在这里可以落到明确的验收条件。** 目的锚是“用户能凭自己记得的事件、餐厅和节奏找到素材，关键误判不会无声扩散”，归宿锚是“证据留在 Result，解释、用户补充与接受范围留在 Plan，准确版本确认由现有 seal 边界落实”。

确认可以是一次按时间排列的代表图预览、一个简短候选对照，也可以随着发现冲突分批发生。关键条件是：在批量固化关键命名和成员边界前，Agent 已把会改变用户记忆结构的实质缺口带到恰当的决定者，并保存其处理结果。证据充分且用户已委托的部分可直接采用；无法确认的部分可用明确的未知名称或延后处置，但需交代对检索的影响。更强模型若能自行消除这些不确定性，就不需要仪式性地多问一轮。不要固定“第几步必问”、每家店必问、问题数、图像数或统一置信度阈值。

就本例而言，用户已更正的“鲁上鲁”、未定名的旺角晚餐、太子午餐和牛排晚餐，适合作为少量关键节点的复核对象。复核应同时对照各自的时间、代表图、合理候选及成员范围，检查有没有漏掉或混合一次访问；没有可靠候选时可以直接承认缺少店名，不必把无关附近商铺包装成候选菜单。本段是交互样例的选题依据，不是对真实行程或全部成员的新增确认。

后续最小改动应先修正现有 Plan Skill 中对用户事实澄清的排斥，并用相同真实场景验证“候选被实际消费、关键不确定性得到处理、确认范围被准确保存”。针对虚焦高自信误读、附近候选缺少真店、多次访问可能混合，以及用户已明确委托且证据充分的情形分别观察行为；既检验该问时能问，也检验不需要时不会强加问卷。工具发布则按既有[安装与升级 runbook](../../readme/installation.md)完成源码、wheel、日常安装与新会话的逐层验证。当前审计没有替用户批准一份新的合约，也没有把修复安装、业务候选修改或后继 PreCheck 记为已经完成。
