---
id: "eval-260908-1148-hk-trajectory-audit"
title: "香港数据运行轨迹审计：压缩、额外调用与历史答案暴露"
type: eval
status: active
created: 2026-09-08
updated: 2026-09-08
timezone: "Asia/Shanghai"
parent: "index-eval"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
  - "design-260825-2235D-precheck-compression-boundary"
  - "eval-260823-1918-ai-album-migration-baseline"
superseded-by: ""
service_version: "MediaSense 0.8.0"
date: 2026-09-08
environment: "local macOS; retrospective read-only audit"
model_id: "gpt-6-astra; high"
dataset_version: "ai-album-hk-representative-v1/test-260831; 2134 manifest media hashes matched"
purpose: "检验本次 PreCheck 与 Plan 是否节省实际工作，并追溯结论是否受到历史答案影响"
baseline_ref: "eval-260823-1918-ai-album-migration-baseline"
tags: [compression, trajectory, provenance, hong-kong, geo]
---

# 香港数据运行轨迹审计

本次**地理压缩确实生效；视觉压缩主要实现了素材到代表的缩减，尚未证明进一步的语义选择收益**。没有发现 Agent 在压缩之后又逐项发起数百次地图查询，或向另一个 VLM 服务提交数百个逐图请求。Plan 确实消费了数百份视觉证据：234 份不同派生图像，来自 232 个来源项，经拼图等方式形成 32 个图像附件。

没有发现主动读取旧 caption、历史分类文件内容、其他 Agent 测试报告或参考 Plan 的行为。不过，范围发现把一个旧分类目录的语义标签直接暴露给了模型，因此**不能把本次结果称为严格独立于历史答案的盲测**。这证明了暴露，不足以证明该标签导致了最终判断。

本报告评价执行过程与证据来源；不把最终 32 个场景全部认证为语义正确，也不代替真实费用账单。

## 审计对象与证据方法

用户给出的 cmux surface 为 `30C70563-82D8-4DE7-8835-C45F61109183`，所属 workspace 为 `00309E9E-42AF-4484-AF6A-01B06A8CDDBD`。surface 的恢复绑定指向 T2；最终预览出现在它的续接会话 T3。通过 `forked_from_id` 验证以下父子链，而非只依赖终端滚屏：

| 标识 | 会话 ID | 用途 |
| --- | --- | --- |
| T0 | `01a07d01-3958-73a3-aca5-19cc5cc8882c` | 初始授权、来源范围确认、本地 PreCheck、Geo 披露 |
| T1 | `01a07ec4-2697-7921-873e-07764288c7e6` | Geo 授权续接 |
| T2 | `01a07ec4-db61-72f2-af79-69c5405381a9` | Geo 授权续接；surface 恢复绑定 |
| T3 | `01a07ed0-86a0-7312-94ba-748e62747fe2` | Geo 完成、证据消费、Plan Candidate 与预览 |

以下 `T3:137` 等标记是原始 JSONL 的一基行号。各文件绝对路径及 SHA-256 保存在[审计指标](../../eval/sessions/260908-1148-hk-trajectory-audit/metrics/combined.json)的 `sessions` 字段。T0 起于北京时间 2026-09-08 01:53，T3 结束于 11:07。原始日志仅在本机保留，未复制进 Git。

计数优先使用去重后的 `item_completed` 事件及实际结果；另外检查外层 `custom_tool_call_output` / `function_call_output`，区分“工具取回的数据”和“实际传给模型的文本或图像”。循环中的多个调用分别计数，不把一段 `functions.exec` 当成一次底层调用。工具状态、封存 Result 和 Geo journal 交叉核对；没有重跑 PreCheck、VLM 或地图服务。本审计自己的图像抽查不计入被审计运行。

- Dataset：`dataset:6581e19d4fe94e26a10e2f5ca1b34c9b`。
- PreCheck Run：`precheck-run:7e94a7a8c2ac4a7185f5c69069196d22`。
- Result：`precheck-result:876d5056651a2f836364865796f07819ac9c329534819c8b13759127abb62204`。
- Plan Work：`plan-work:39524f7b-e23d-4b94-bd51-88ad244720a0`；Candidate identity：`sha256:207b854227a826188df9864c0b1704f350024a23ffc10ecf8db42c0fdb4cb7fe`。
- 运行终点：2,133 个媒体进入 32 个场景；另有 2 个可用但场景不明的视频保留原位置，以及 1 个无效媒体和其他排除/辅助项。Candidate 已通过校验，等待确认封存；不是已完成 Apply。

## 地理信息：压缩有效，没有第二轮 Agent 补查

| 层次 | 实测数量 | 含义 |
| --- | ---: | --- |
| 有本地坐标的来源项 | 1,838 | 102 个来自媒体元数据，1,736 个来自本地 GPX 匹配 |
| 这些来源项中的不同精确坐标 | 1,611 | 简单精确去重后的基数 |
| 实际查询坐标 / 逻辑查询 | 225 | 压缩后 acquisition 的查询集合 |
| Google 地址查询 | 225 | 224 success，1 no_result |
| Google 附近地点查询 | 225 | 221 success，4 no_result |
| 高德 resolve_place 补查 | 4 | 3 success，1 no_result |
| 服务请求总数 | **454** | `225 + 225 + 4`，与 Result 和 journal 逐条一致 |
| Plan 新增地理查询 | **0** | 无直接 Geo Tool 调用、地图 HTTP 命令或第二个 journal operation |

从来源项到逻辑查询约为 **8.17 倍缩减**；即使以精确去重后的 1,611 个坐标作为起点，仍有约 **7.16 倍缩减**。因此不是仅靠缓存命中或把相同坐标算多次制造出来的压缩率。账本中的 `historical_provider_requests=0`，这 454 次均归为当前运行。

221 个坐标各发生 2 次请求；另外 4 个坐标各发生 3 次请求。高德请求对应 Google 附近地点没有结果之后的 fallback，未出现同一 provider/operation 的重复重试。最后得到 224 个成功地址组件和 223 个成功附近地点组件，其余明确为 no_result。

Geo journal 只有一个 operation，操作名为 `resolve_place`，请求指纹为 `sha256:50e03e85c47857f33635d1303bf9dc119f2c8a6432fd907aef82730190ab7a40`。其 454 条 attempts 与封存 Result 中的 provider、operation、输入坐标、status 和 request count 顺序一致。T3:127 的完成状态与 T3:137 的公开读取结果也给出相同总数。

披露的 2,025 是授权上限，不能当成已发生调用或预计账单。`billable_units` / `billable_calls` 仍未知，因此本报告不把请求减少直接换算成金额。

还有一个输入质量问题：19 个来源项带有 `(0, 0)` 坐标，它们最终触发一个逻辑查询、3 个无结果请求。是否应排除该坐标需要专门的数据有效性规则；本次不据此否定已经证实的整体压缩。

## 视觉信息：完成了代表压缩，未启用 embedding

| 环节 | 实测 |
| --- | --- |
| 发现与媒体范围 | 6,373 个发现项；2,136 个 source_media，其中 2,135 usable、1 invalid |
| 本地 bundle candidate | 241 个 |
| 压缩入口 | 200 个，覆盖全部 2,135 个 usable 来源项，无 residual |
| embedding 配置与执行 | `embedding_profile=null`；没有 embedding work record |
| 代表选择 | 200 个组全部为 `extension-priority-v1`；embedding 比较数为 0 |
| 质量限制 | 200 个组全部带 `limited_similarity_evidence`；outlier paths 为 0 |
| 分布 | 83 个单项组；最大组 195 个成员 |

`PrecheckExecutionConfig` 的默认 `compression_target=200`、`embedding_profile=None`，与这次持久化配置一致，见 [配置实现](../../src/mediasense/precheck/_orchestrator.py)。[分组实现](../../src/mediasense/precheck/_compression_strategy.py)按时间排序并依据日期、时间、空间及可用内容距离选取边界；本次没有 embedding，内容相似度没有参与。200 是本次使用的默认目标，不是 Agent 根据内容反复收敛后发现的最优数量。

因此不能将这次成功归因于 embedding 驱动的语义聚类。它实际依赖本地关联、时间/位置线索、代表选择，以及后续 Agent 的图像解释。从 2,135 个来源项到 200 个入口约缩减 **10.68 倍**；从 241 个 bundle candidate 到 200 个入口则只有 **1.21 倍**。

### Plan 实际看了多少

| 视觉消费 | 数量 | 轨迹 |
| --- | ---: | --- |
| 全部入口图像 | 200 | 10 张拼图，每张 20 格；T3:365、377、387、403 |
| 边界图像 | 31 | 2 张拼图；T3:493、503 |
| 单独打开的图像 | 20 | 最初 14，最后 6；T3:175、195–219、559–571 |
| 单独图像与拼图重叠 | 17 | 属于放大/重复检查，不能重复算成新素材 |
| 不同派生图像 | **234** | `200 + 31 + 20 - 17` |
| 不同来源项 | **232** | 通过 Result 的 `derived_from` 关系去重 |
| 图像呈现次数，含重复 | **251** | `200 + 31 + 20`；视频联系表内部帧数不另算 |
| 图像附件 / ImageView | **32** | 12 张拼图 + 20 张单图，分 6 批返回给模型 |

所有被查看图像均能沿 Result 追溯到纳入范围的 source_media，没有旧分类缩略图或历史 caption 图像混入这一集合。这里的 234 是派生图像数量；有些本身是视频联系表，不能称为 234 张独立原照片，也不能等同于 234 次 VLM API 请求。

232 个不同来源项约占 2,135 个 usable 来源项的 **10.87%**。因此没有发生“把两千多个媒体全部逐张送回模型”的完全退化。但 **200 个入口全都被展开和看过**，不能据此声称已经验证“只看少量代表，再按需扩展”的第二层选择收益。

本次没有调用独立 caption/VLM provider；视觉解释发生在 `gpt-6-astra` Agent 自身。PreCheck Result 中 `remote_models=false` 只描述 PreCheck Tool 的执行边界，绝不意味着整个 Agent 会话没有使用模型或没有图像成本。

### 展开是否有理由，以及成本是否转移

57 次 `precheck.read` 由 3 次 review、35 次 expand、19 次 resolve 构成。review 中一次因游标参数不一致失败，随后修正。expand 包含全部 200 个入口的 anchor 和来源 observations，以及 4 个混合组的 150 个成员 observations；另有 31 个边界和 3 个额外视频 anchor。resolve 返回 2,336 行、2,266 个不同来源身份，其中覆盖全部 2,135 个 usable 来源项。**身份解析不是看图，也不是重新地理解析。**大量返回值留在执行单元内，仅把摘要交给模型，不能把原始工具日志大小直接当成模型上下文大小。

T3 的决策记录明确说明了有价值的补查：约 8 小时时间冲突导致视频混入另一餐的压缩组；Agent 拆分了 4 个混合组，将 5 段 Amber 视频和 1 段牛排餐厅视频重新归组。视频工作另有 244 次 frame decode failure 和 1 次 probe failure；这些是操作数量，不能直接解释成 245 个损坏媒体。准备画面的限制可以解释一部分补查需求。

这说明 Agent 并非无理由重复调用。然而，轨迹没有提供足够证据证明“全量 200 入口 + 全量成员身份解析”是本次最省成本的必要路径。也不能在没有对照运行的情况下，把全部展开都判为浪费。

从 T3:135 的第一次 review 调用到预览结束，去重后的 usage records 记录 **52 次 Agent 模型请求**：累计 input 7,742,513 tokens，其中 cached input 7,461,068，非缓存输入 281,445，output 31,325。它们包括推理、协议查找、编排和预览构建，且后续请求可能再次携带之前图像的上下文。不能把 52 全部称为新图像推理，也不能把缓存 tokens 按普通输入单价计算。记录未单列图像 tokens，无法据此给出视觉费用或与旧项目的精确金额差。

## 结论来源：未发现主动借用，但有历史目录名暴露

### 实际读取和检索的来源

完整会话链有 4 次 `ctx_search`。一次无结果，其余返回本次已索引的 Skill、范围确认协议和 Geo 请求披露契约。未发现返回其他 Agent 的测试结论。

实际文件读取集中于安装的 Skill、Tool schema、为排查请求错误而读取的 MediaSense 安装代码，以及本次自己生成的临时 manifest、Candidate 和预览。未发现读取 `baseline/production-cache`、旧 caption/title/location 文件正文、`docs/eval/...plan-reference`、其他运行报告或会话日志。没有 shell 发起地图/VLM HTTP 请求，也没有 Agent 直接打开 PreCheck 数据库。审计者本次只读检查数据库的行为不属于被审计运行。

视觉与事实仍利用了素材自带的信息：源路径包含 `100MSDCF-amber`、`CLIP-amber`、`100MSDCF-steak-house` 等名称，Agent 明确把这些路径与画面、时间一起用于归组。这是输入本身已有的语义线索，不能把结果描述成“只凭像素独立识别全部餐厅”。原始目录标签是否应在下一次评估中隐藏，应由所要检验的能力决定。

对两个具名结论的抽查支持它们具有当前素材依据：

- `DSC00960.JPG` 的派生图像能读出 `FULL AMBER EXPERIENCE`，T3:561 单独打开了该图。
- `DSC00514.JPG` 的派生图像能读出 `Sister Wah / 華姐清湯腩`，T3:203 单独打开了该图。

这两项无需依赖旧分类答案；抽查不能外推为全部 32 个场景均无误。

### 已证实的暴露

初始范围发现返回了旧输出目录的三个 representative paths，并在 T0:109、140 的外层工具文本中进入模型上下文。其中一个为：

```text
representative-run-clustered/260501/1-室内纸箱物品整理/
DJI_20260501183924_0002_D_highres_thumbnail_3926f8ae4045a352323dedbcec9fd5b0.jpg
```

这是已生成的语义标签。即使随后排除了该目录，模型已经见过它。最终存在“05-01 收拾物品”分组，但模型也实际看过对应素材；没有反事实对照，不能证明最终名称是抄来的，也不能证明该历史提示毫无影响。

此外，T3:383 一次 `resolve(accounts_for)` 返回的首 200 行中，有 123 条旧缓存路径和 8 条旧分类输出路径，后者包含餐厅与场景名称。外层 T3:385 只输出 keys、pagination 和第一个成员，第一项是 `.npy` 缓存路径；8 条语义分类路径没有被展开到可见模型文本。脚本只保存了 `resolve-all-page`，后续没有读取该变量使用这些旧分类。因此将其记为**工具取回了不必要的旧答案路径**，而不是已经证明模型消费或采用了它们。

这两个层次必须区分：范围发现的语义标签暴露已经证实；后一次取回的完整旧路径集合，对模型的实际影响没有证据支持。单纯检查有没有 `cat baseline/...` 会漏掉第一类问题。

## Fixture 与比较边界

实际来源为 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`。本次按要求运行包的 `scripts/verify.zsh`：**清单内所有文件 SHA-256 检查通过，但整体校验在包大小检查失败**，实际 3,188,633,792 bytes，超过 2,000,000,000 上限。这个工作副本包含新增测试目录、安装资料和预览等，不能声称整个目录仍是未经扩展的原始交付包。

进一步只读核对了实际 test 来源与媒体 manifest：2,134 个声明媒体全部存在，`derived_sha256` 全部匹配；checksum manifest 自身的 SHA-256 与仓库 fixture 注册值一致。额外纳入的两个 RAW 来自包内 fixture，解释 2,136 的媒体统计。该验证支持素材身份，不把历史目录名当作语义真值。

本次预览 HTML 被写到包根目录，但在实际 source root `test-260831` 之外。它不构成源媒体移动；后续评估输出仍应放到 fixture 包外，避免下一次扫描或校验再次混入运行产物。

与 AI Album 的差异按迁移纪律分类：

| 差异 | 分类 | 本次证据支持的判断 |
| --- | --- | --- |
| 本地关联、代表选择、派生图与批量地理采集的缩减 | `preserved` | 两条成本缩减链都实际存在 |
| 由 Agent 使用当前证据做解释，Geo 使用有明确预算与 journal 的共享 Tool | `intentionally_changed` | 无旧式逐代表 caption pipeline；可核实实际请求 |
| AI Album 168 代表与本次 241 bundle / 200 入口 / 232 被看来源项的数值差 | `not_comparable` | 边界、覆盖和补查语义不同；不能直接据此判回归或优于旧项目 |
| “当前默认运行已经验证 embedding 语义压缩及更低总费用” | `not_comparable` | 本次 embedding 未执行，缺少相同条件的费用对照，不能成立该比较结论 |

本报告没有把这些数量差异直接认定为历史功能回归。默认执行组合未覆盖期望中的语义压缩能力，是已证实的能力验证缺口；是否修改默认配置属于后续设计与实现工作。

## 后续改进的优先顺序

1. **先验证实际启用的压缩能力。** 为需要语义压缩的运行明确记录 embedding 是否启用、模型/profile、local cost 和代表选择方法。先取得相同素材上的完整对照，不以把固定 200 改成另一个固定数作为完成依据。
2. **把 Agent 消费账本补齐。** 分开记录不同来源项、派生图、视频帧、拼图附件、重复查看、展开理由、token/cache 和 provider cost。按重要差异覆盖和边际收益决定何时停止，保留必要的冲突与边界补查。
3. **建立真正隔离历史答案的评估来源。** 仅暴露目标媒体与声明允许的元数据/GPX；旧分类、caption、参考 Plan 和其他测试结果不与输入同根。范围确认可保留排除项的必要计数，但独立评估不应把旧语义目录名当作示例展示给模型。
4. **用同一运行范围做对照。** 分别比较默认配置、启用语义证据、Plan 选择性展开的质量与总工作量；地理侧保留本次已经证明有效的采集单元压缩。重跑需要另行执行，本审计未产生任何新增模型或地图服务实验。

## 复核入口与限制

- [可复核脚本](../../eval/sessions/260908-1148-hk-trajectory-audit/run.py)：读取精确会话链、封存 Result 和只读 SQLite，核对实际图像来源、请求、token 记录及媒体 hash。只向 stdout 输出摘要 JSON。
- [精简指标](../../eval/sessions/260908-1148-hk-trajectory-audit/metrics/combined.json)：包含输入证据指纹、全部计数、旧目录名暴露样本和最终决策摘要。
- [会话说明](../../eval/sessions/260908-1148-hk-trajectory-audit/report.md)：本机环境、命令与文件位置。
- 复核命令：`rtk proxy python3 eval/sessions/260908-1148-hk-trajectory-audit/run.py`。
- 审计时仓库 HEAD：`a9ba4a0908510e8594b1d6afb04dad02f78830c8`。安装来源记录为本机 `dist/mediasense-0.8.0-py3-none-any.whl`，没有嵌入可证明的 build commit；83 个同时存在的安装 Python 文件与仓库源码逐字节一致。因此 HEAD 是审计源码定位，不能冒充已记录的原始 build commit。
- 账本位于 `/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e`。封存 Result 文件 SHA-256 为 `dd014de51cf5d4de24bf7ad63e4b7fc318d7ae100dd061b8ab4b008b706fb7be`。
- API 证据来自本地 MediaSense MCP 和内部 provider journal；本审计没有请求地图 API。模型 gateway 与地图服务没有独立账单/网络抓包，无法证明进程外未记录活动的绝对不存在，也无法计算精确收费。
- 结论限定于该代理媒体 fixture、该配置、该 Agent 轨迹；不能外推到完整原片、另一配置或 TB 级吞吐量。没有进行去历史标签的重跑，所以不能估计标签暴露的因果影响。
