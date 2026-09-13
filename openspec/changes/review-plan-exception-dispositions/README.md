# Plan 对损坏、未决与辅助素材的处置依据

## 交接状态

记录日期：2026-09-13。阶段：**第一轮事实与现有设计复核完成，正在与用户讨论；方案尚未定案**。

用户已要求本轮讨论并收敛第 4、5 包，先复核事实和现有设计，再讨论必要调整。本包中的新建议尚未获用户确认，不构成代码、Skill、公开合约或业务 Plan 的实施放行。代码位置用于复核当时行为，不限定后续方法；审计报告中的建议不构成本包的设计决议。

## 已确认事实

1. 初版共将 3 个媒体与 4 个辅助项留在原位置。3 个媒体中，1 个被 PreCheck 判为 invalid，另 2 个视频是可读但时间或画面不足以确定更细语义。
2. 损坏文件 `DJI_20260504202728_0029_D.MP4` 与 `.patched-full.MP4`、`.remux-faststart.MP4` 属于同一个入口 Evidence 的代表关系：
   `evidence:2f3396b11699a55ad88fa8dcd0f4dcc61ba6b013272f6972c45ad02a2612a2a8`。
3. 两个可读版本进入 Amber／面包与主菜；损坏版本留原位，候选理由直接引用 PreCheck 的 invalid 条件。
4. 原轨迹第 808 行构造完整候选时，对拟归组成员统一筛选 `condition === "usable"`，剩余 source_media 被纳入留原位的处置。
5. 4 个辅助项为两份 GPX 和两个 `.albumignore` 标记。GPX 在 Result 中的 condition 为 unresolved，标记为 usable；原候选将四项均留原位，并以 GPX 尚未取得整体有效性认证解释其处置。
6. 当前 [默认组织 Profile](../../../docs/spec/contract/default-organization-profile/index.md) 区分损坏、可读未决和辅助素材；损坏本身不排除依据可靠上下文归组，辅助素材有既有默认组织含义。
7. 初版所有来源仍有唯一处置，没有因此丢项，也没有执行移动。该初版随后因用户对餐厅信息的反馈撤下。

## 影响与证据边界

损坏版本与可读相关版本在计划中的组织处置不同；辅助资料也没有随普通组织进入对应结果。已有编码或 condition 不独立证明这种处置符合用户的检索意图。

共同代表关系是可调查的依据，不等于已经证明文件间的字节同一性、修复历史或最终正确目录。不能据此认定所有 invalid、unresolved 或辅助项都应进入某一固定位置。本包记录初版依据不足以直接得出结论之处，不替用户预定这些项的去向。

## 直接复核入口

- 指标：`source.scope_condition`、`plan.other_outcome_counts`、`plan.full_partition_verified`。
- 原候选和构造过程：原轨迹第 808 行及其后的 Plan inspect 回执；初版身份见配置。
- 损坏项：`source-item:a632e25bd4a7b31ea05f815609247333a6dffd5d6d3d7d035b56e2f303b0af3b`。
- 修复版本：`source-item:bdf49ffdb450ea316d553ab4b505be33866039a6e5a44e215672dbf65d5a264d`。
- remux 版本：`source-item:818104e942baaa6b8face5515f23da4d243d0470eb141fc4156d945dd4aa81c0`。
- [Frozen Plan 当前合约](../../../docs/spec/contract/frozen-plan/index.md)、[Plan Skill](../../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md)。
- 相关包：[Plan 信息充分性](../review-plan-information-sufficiency/README.md)。本包聚焦例外处置，不规定整套问答顺序。

## 尚未定案的问题

- 这几个具体来源已有何种足够可靠的上下文，哪些关系仍需质疑？
- condition、可读性、组织语义及执行可行性分别支持什么结论？
- 初版的留原位属于充分解释的选择，还是由成员过滤方法直接形成的结果？
- 用户需要看到哪些例外理由和范围，才能评价这些处置？

## 第一轮复核记录

以下为现有规则对照、直接复核结果及 Agent 建议；本轮未替用户确认具体来源的最终去向，未修改业务 Plan。

### 现有规则已足以纠偏

默认 Profile 被选为当前组织策略后，以下规则已经适用，无需另立异常策略：

- [损坏素材](../../../docs/spec/contract/default-organization-profile/index.md#damaged-or-unreadable-media)：可靠同名族、时序、源目录等上下文可以支持坏片随相关素材进入正常组；只有活动／章节可信时保留在该层级；上下文不足才使用最近可信层级的 `d-damaged-info/`。
- [可读未决素材](../../../docs/spec/contract/default-organization-profile/index.md#valid-but-unresolved-media)：先保留已知活动／章节；必要时在最近可信层级使用 `Uncategorized/`，不能只因细分未知就丢失已有上下文。
- [辅助资料](../../../docs/spec/contract/default-organization-profile/index.md#auxiliary-material)：范围内、对该集合有用的轨迹等辅助资料默认放入 `a-files/`；`a-files/GPX/` 可提供进一步定位。预检缓存、派生 Evidence 不因此进入输出。
- [Frozen Plan](../../../docs/spec/contract/frozen-plan/index.md#other-outcomes-and-decision-notes)可以表达保留现状和有理由的排除；该表达能力不自动说明某次选择符合已选 Profile。重要偏离仍需依据和审阅。
- [Apply](../../../docs/spec/contract/apply/index.md#operation-and-recovery-invariants)已明确：媒体容器无效仍可能作为字节安全移动。Plan 决定逻辑归属；Apply 核对实际可执行性，不代为改组。

因此，第 808 行按 `condition === "usable"` 统一决定拟归组成员，再把其余 source_media 留原位，是本次执行纠偏对象。`invalid` 和 `unresolved` 既不是组织去向，也不是已经证明无法执行的结果。

### 具体来源与证据边界

| 对象 | 本轮核实到的依据 | 可以支持与不能支持的判断 |
| --- | --- | --- |
| `DJI_20260504202728_0029_D.MP4` 及两个可读版本 | 三者同在 `0504/DJI_001-action-sd-amber/`，共享文件名主干；第 758 行 resolve 显示 invalid／usable 条件；两个可读版本在初版同属 Amber／面包与主菜 | 支持调查并保留相关版本的上下文联系，不支持单凭 invalid 拆开；不能据此证明三者字节相同、修复完整或内容逐帧相同 |
| 共同入口 Evidence | 第 461 行显示它实际来自另一相机的 `0504/DJI_001-pocket4-amber/DJI_20260504202740_0029_D.MP4`；精确代表 4 项，时间范围为 20:27:28—20:27:41 | 不是直接由损坏源生成的画面，也不是只代表那三个修复相关文件。其成员未逐项视觉比较、相似证据有限、原代表不可用后替换的限定均须保留 |
| `DJI_20000114013849_0001_D.MP4` | 可读，位于 `0503/DJI_001-pocket4/`；Result 保留了 2000 年时间与时间冲突；初版认为画面不足 | 文件夹是待评估的上下文线索，不足以直接把拍摄日期改成 5 月 3 日。细组未知不自动要求留原位；活动可信时可保留在活动层 |
| `DJI_20260503135449_0001_D.MP4` | 可读，位于 `0503/DJI_001-action/`，Result 时间为 2026-05-03 13:54:50 +08:00；初版认为画面遮挡 | 可以调查与当天上下文的关系；遮挡不等于损坏，也不证明属于某家餐厅。本轮未重新看片认证它的具体活动 |
| 两份 GPX | 第 644、646 行定位于该旅行 `a-files/GPX/`，属于 auxiliary/unresolved，均有 available 的来源内容验证 Observation | 支持作为该集合的辅助资料考虑，不需要先认证每个轨迹点才能决定保留位置。既不能把参与匹配当作完整有效，也不能把 unresolved 当作必须留原位 |
| 两个 `.albumignore` | 位于旅行的 `a-files/` 和 `fixtures/`，为 auxiliary/usable；来源内容验证为 not_checked | 与 GPX 的用户用途不同：它们首先是原遍历范围的控制标记，不能仅凭同属 auxiliary 就要求搬入同一辅助目录；也不能凭 usable 宣称已满足 Apply 核验 |

Agent 的推荐是优先维持损坏源与相关版本的联系；若现有证据只支持 Amber 这一餐而不支持“面包与主菜”细组，就保留较粗层级。共同组织不要求先证明完全内容等价，也不授权合并或丢弃任何版本。两份 GPX 优先按既有 Profile 放在旅行的辅助资料位置，并保留有效性限制。这些是待审阅的组织理由示例，不是对原 Plan 的实际改写或冻结。

两个可读未决视频的具体可信层级、本次修复相关文件最合适的细组仍未重新认证。`.albumignore` 是否随输出承载忽略规则，要按其真实用途判断；不能为了对齐 GPX 而自动搬运。需要时可在既有 other outcome 中明确保留原位置及范围，不新增“控制素材”实体。

### 各类依据各自回答什么

| 依据 | 回答的问题 | 不替代的决定 |
| --- | --- | --- |
| scope 与 condition | 本次如何核算此项、已有处理条件是什么 | 用户希望在哪里找回它 |
| 容器／画面可读性 | 能取得什么内容证据、缺失或损失是什么 | 最终语义归属及文件能否安全搬移 |
| 上下文关联 | 最深能可靠归到哪个活动、章节或组 | 全成员内容一致、修复完全性或重复删除 |
| 组织意图与 Profile | 为何放在这里、为何需要偏离默认 | 当前文件系统安全条件 |
| Apply 核验 | 选定源能否按冻结组织安全执行 | 新的命名、分组或例外语义 |

### 可以验证的指导交付缺口

第 514 行保留的运行版 Plan Skill 与当前 packaged Skill 逐字一致。它已有“保持相关素材在一起”“异常可见”“解释 Profile 偏离”的原则，但未包含默认 Profile 对损坏、可读未决、辅助资料的具体处置规则，也没有指向这些默认细则的可用随包引用。现有 `references/organization-profiles.md` 仅面向默认不适用时的替代方向。

这是可以直接核对的指导交付缺口，不能据此宣称它是本次偏差的唯一原因。建议在既有 Plan Skill 的默认 Profile 说明中准确交付现有规则，并验证实际操作项目加载的发布内容；规则权威继续属于当前默认 Profile，不增加另一套策略、registry 或 Tool 语义。

### 建议的审阅与验收依据

- 以可核实上下文为条件检验归属，不以枚举值决定输出：同样 invalid 的两项可以因关联强弱不同而进入正常组或损坏资料目录；同样 usable 的两项也可以分别归组和保持未决。
- 正例覆盖坏片随可靠关联同行、只知道活动时停在较粗层级、可读未决项保留上下文、GPX 虽未完全认证仍作为辅助资料组织。反例覆盖全部 usable 自动归组、全部 invalid 留原位、所有代表成员共享一个菜名、所有 auxiliary 自动同去向。
- 最终审阅呈现具体处置、精确适用成员／数量、支持该层级的依据、仍不知道什么，以及保留原位或排除对日后找回的影响。坏片即使在正常组中，也不能因此隐藏损坏事实与解释限制。
- 不同理由不能被“7 项保留原位”一个合计替代：修复相关文件、两段可读未决视频、GPX 和控制标记分别可辨；源项仍只有一个明确处置。使用既有 Source Set、`other_outcomes`、`decision_notes` 和 Result 限定即可。
- 解释材料必须来自最终 Candidate 的说明与确切范围；页面怎样生成和展开由第 6 包负责。本包不开发 HTML，也不让 Apply 根据展示文字另行决定去向。
- 先证明 Agent 能在当前地点／GPX 证据有缺口时正确判断；不把第 1—3 包修复作为讨论或行为验收的前提。本轮没有执行 Apply，不能宣称这些源已经通过执行前核验。

### 本轮复核范围与未决状态

原轨迹前 859 行 SHA-256 与配置相符，具体对象来自其公开 Read／Plan inspect 回执，未以当前业务 Work 代替初版。已按要求读取 fixture 说明并运行 verifier：清单内所有文件 SHA-256 匹配；整个工作副本因额外内容达到 3,193,897,404 bytes，超过 2,000,000,000 bytes 门槛，校验以失败结束。不能声称整包通过或仍是未扩展的原始包。

另对本节涉及的 5 段视频和 2 份 GPX 完整计算 SHA-256，当前 `test-260831` 来源均与对应受清单保护的包内文件一致。这只支持这些具体文件的复核，不认证全部工作副本、完整原片质量、轨迹整体有效性或 Apply 可执行性。

已有默认去向原则不需要用户重新选择。待继续讨论的是具体上下文是否足够支持所提层级，以及有特殊找回目的时是否需要偏离默认；目前没有证据要求新增公开对象或修改合约。用户尚未确认本轮改进建议，两个包均未获实施放行。

## 共用证据与适用范围

- [运行验收报告](../../../eval/sessions/260912-2333-hk-run-acceptance/report.md)
- [精简指标](../../../eval/sessions/260912-2333-hk-run-acceptance/metrics/combined.json)
- [精确对象与本机路径](../../../eval/sessions/260912-2333-hk-run-acceptance/config.json)
- [只读复核脚本](../../../eval/sessions/260912-2333-hk-run-acceptance/run.py)

被审计运行使用 MediaSense 0.10.2，源为 `ai-album-hk-representative-v1/test-260831`。审计代码基点为 `615c3359941927515f0c0a8738a3f08122bcad46`；共享工作区和原 Plan 会话随后继续变化，不能把当前磁盘状态当作当时状态。

PreCheck Run 为 `precheck-run:8b5ff902fda54e6292b14d4fa5f0de42`，Result 为 `precheck-result:cbd18bc79b56b2b9d257529f878b7151c399b4815acebe74d1ba328e80a7ae57`。初版 Plan 轨迹固定到配置中声明的原会话前 859 行；后续更正按报告中的时间与行号分别引用。原始媒体、数据库、完整轨迹和 HTML 快照在本机，不复制到本包。

公开语义以 [当前合约](../../../docs/spec/contract/index.md) 为准；本包不成为另一份规范，也不改变既有验收或迁移决定。
