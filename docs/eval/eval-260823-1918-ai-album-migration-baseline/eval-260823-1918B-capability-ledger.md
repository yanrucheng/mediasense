---
id: "eval-260823-1918B-capability-ledger"
title: "Migration Capability Ledger"
type: eval
status: active
created: 2026-08-23
updated: 2026-09-13
timezone: "Asia/Shanghai"
parent: "eval-260823-1918-ai-album-migration-baseline"
depends-on:
  - "eval-260823-1918A-legacy-system"
superseded-by: ""
tags: ["migration", "capability", "parity"]
---

# Migration Capability Ledger

## Purpose

This ledger is the authoritative place to decide whether each material AI Album capability is preserved, intentionally changed, regressed, or not comparable in MediaSense. It prevents both accidental feature loss and blind reproduction of known legacy defects.

The capability inventory records target intent. The implementation-status table below separately records what has actually been delivered and evaluated; intent must never be reported as implementation completion.

## Difference classes

- `preserved`: the useful capability and relevant operating qualities remain available.
- `intentionally_changed`: behavior differs for a stated product, correctness, cost, or safety reason.
- `regression`: a useful legacy capability is unexpectedly missing or materially worse.
- `not_comparable`: MediaSense changes the problem boundary, so equality is not meaningful; evaluation uses a different criterion.

Implementation status is independent of the difference class:

- `implemented`: the stated capability unit is reachable through the installed configuration, production composition and public entry point, delivers its promised result, and has evidence at every claimed boundary; a component or injection test alone is insufficient;
- `characterized_only`: legacy or desired behavior is captured, or components exist, but the claimed installed production path or result delivery is not yet closed; the evidence column must state exactly where the chain stops;
- `deferred`: the capability unit is intentionally not implemented and remains a gate for dependent work.

`pending implementation comparison` is not a fifth difference class; it means there is not yet enough MediaSense implementation evidence to assign one of the four migration judgments.

## Capability inventory

| Legacy capability | Legacy behavior | MediaSense stage | Intended disposition | Required comparison |
| --- | --- | --- | --- | --- |
| Recursive media inventory | Walked a root and recognized a fixed format set | `precheck` | Preserve and broaden behind a stable inventory contract | Coverage, errors, unsupported files, scan throughput |
| `.albumignore` scope control | Required directory-local marker knowledge | `precheck` | Intentionally change: automatic discovery plus Agent-assisted scope confirmation; retain advanced override | Included/excluded paths, user effort, reproducibility |
| Explicit GPX argument | User supplied paths even when files were discoverable | `precheck` | Intentionally change: discover candidates, compute overlap/benefit, record adopted sources | GPS coverage, false matches, provenance, user questions |
| Same-stem and sidecar grouping | Associated JPG/RAW/LRF and name variants | `precheck` | Preserve the capability; make membership and rationale inspectable | Bundle membership, attachment coverage, false association |
| 60-second adjacent chaining | Chained adjacent groups without limiting total span | `precheck` | Intentionally change or bound after evaluation; never hide span | Over-merge/under-merge review, span and boundary metrics |
| Representative selection | Chose one preferred file per bundle | `precheck` and `plan` | Preserve stable identity; improve semantic evidence selection separately | Representative stability and coverage |
| Batch metadata extraction | Used ExifTool and configured tags | `precheck` | Preserve and strengthen provenance/error semantics | Value equality, source tags, failures, throughput |
| Manufacturer information maintenance system | User YAML supplied conditional timestamp exceptions and configurable extraction fields; some photography-context mappings were disconnected | `precheck`, with bundled knowledge, user YAML and user/Dataset metadata context | Preserve scoped adaptation and configuration-based extension; the 2026-09-11 regression and 2026-09-12 isolated delivery are recorded separately below | User configuration → requested tags → conditional selection → installed execution → public observations → correct invalidation after edits |
| Coordinate reverse geocoding and nearby-place lookup | Reverse-geocoded each GPS-bearing bundle representative; AMap returned address/POI in one logical lookup, while Google called reverse and nearby endpoints and could switch provider/language across neighboring media | Shared Geo capability, consumed by `precheck` and available to `plan` for bounded investigation | Preserve datum conversion, address/POI normalization, fallback, and rate limiting; replace hidden continuity state, unstable per-file cache identity, failure ambiguity, and uncounted requests with a stage-neutral Tool, explicit authorization, stable observation identity, and enforced budgets. The accepted M2 evidence below covers acquisition-unit boundaries and per-Source-Item projection; real-place threshold quality and applicability remain uncertified | Located Source Item outcome coverage, query-point/source-coordinate differences and reuse limits, unique logical-query count, actual provider requests, switching hit rate, normalized values, reuse, privacy, user confirmation, and failure/partial semantics |
| Timestamp fallback | Batch and single-item paths behaved differently | `precheck` | Intentionally change: unified typed candidates and confidence | `000114`, `260428`, missing-time fixtures |
| Video frame sampling | Up to 20 frames, roughly 10-second interval | `precheck` | Preserve the capability, leave sampling strategy open | Decode coverage, representative quality, cost |
| Thumbnail generation | Cached ordinary and high-resolution thumbnails | `precheck` | Preserve with versioned profiles and exact invalidation | Visual fidelity, cache hits, regenerated work |
| Asset/frame embeddings | ChineseCLIP arrays cached per representative/frame | `precheck` | Preserve local embedding capability; model remains replaceable | Neighbor quality, storage, throughput, version invalidation |
| Local content-sensitivity evidence | Local NudeNet/NSFW results supplied scores and sensitivity signals | `precheck` | Preserve the local evidence capability with explicit detector provenance, profile, score or quality, and completion/error semantics; the historical classifier, labels, and thresholds remain replaceable | Signal quality, false positives/negatives, local cost, reproducibility, version invalidation |
| Sensitivity-informed VLM routing | Sensitivity results directly selected local or remote processing paths | `plan` | Intentionally change: planning owns whether to ignore or use the signals and may choose all-local, all-remote, automatic routing, warnings, user confirmation, or another explicit policy; provider locality and data-egress effects must be visible and must not change silently | Policy adherence, authorization scope, provider locality, actual data egress, user effort, remote cost |
| Date/location/content clustering | Fixed hierarchy and thresholds | `precheck` and `plan` | Not comparable as a final truth; preserve local candidate computation, move organization judgment to Agent | Coverage, heterogeneity, outliers, visual budget |
| Per-representative caption | Most representatives captioned, usually remotely | `plan` | Intentionally change: budgeted, progressive Agent vision over selected evidence | Images read, image tokens, semantic coverage |
| Visual location inference | Often separate remote call, output used as label | `plan` | Intentionally change: return scoped candidates/evidence and escalate high-impact uncertainty | Wrong-label propagation, candidate quality, confirmations |
| Per-item title and cluster mode | 158 of 159 titles unique; mode usually unhelpful | `plan` | Intentionally change: Agent names the whole organization coherently | Duplicate/similar names, hierarchy clarity, user acceptance |
| Direct output-tree construction | Semantic guesses became filesystem paths early | `plan` then `apply` | Intentionally change: produce and freeze a complete plan before effects | Coverage, conflicts, reviewability |
| Thumbnail/link/move output modes and generic copy helper | `original` moved files; `link` created relative symbolic links for preview; `thumbnail` used generic metadata-copy code, while no user-facing original-copy branch existed | `plan`, `precheck`, and `apply` | Preserve move; move preview to Plan; preserve rendition production in PreCheck; defer persistent links and any new original-copy profile until they have independent accepted lifecycle semantics | No overwrite/loss, source retention, dangling-link behavior, authorization, rewind, receipts |
| Per-stage cache | Many results were reusable by flags and hashes | `precheck` | Preserve and strengthen: checkpointing, atomic writes, provenance, dependency-aware invalidation | Resume work, cache hits, interrupted equivalence |
| Usage monitoring | Optional log, absent from final production run | all | Intentionally change: relevant cost/operation accounting is part of stage results | Zero external calls for local-only runs; confirmed logical work versus actual provider calls for enabled external producers; plan visual cost; apply operations |

<a id="manufacturer-information-repair"></a>

## 2026-09-13：本地 Freepik / NudeNet 640 源码与隔离交付

用户后续独立复核将本轮整体验收标为暂不通过：Read输入关系未校验、未知加载错误被转为正常阻塞、执行信息未公共交付。三项现已补修；287项定向检查与新核心隔离MCP自检通过，**待用户独立复验**。新wheel SHA-256为`89a44a95394b2cd0034620c33662123d731234a6f31c62a0fc54036f290aec64`；新环境132文件匹配，原两环境各131文件保持。本轮不重跑真实模型；详细反例、公共分页入口、去重与未知历史边界见同一验收记录末尾。

用户明确授权 B 方案开发、D5-disabled 和 handoff 信息/失败边界；当前合约先落实逐模型配置、
具名概率/累计/区域值及真实 Evidence 归属，再完成生产接入。详细逐项证据见
[本地敏感性实施验收](../../../openspec/changes/extend-local-sensitivity-observations/acceptance.md#实施验收记录2026-09-13)。

| 边界 | 处置与实际证据 |
| --- | --- |
| 本地证据、逐输入状态和溯源 | `preserved`；复用 Observation/Work/Run/Result，旧 V1/99/33 原义和封存字节可在无推理依赖的真实 Host 读取 |
| 分类器/部位模型及输出 | `intentionally_changed`；新执行采用固定 Freepik 448 MPS FP32 batch 4、640m native CPU FP32 batch 1；四类、累计事件及所有 native 实例完整保存，不生成旧二档判断或标签最大值 |
| 启停与复用 | `intentionally_changed`；逐模型选择，关闭排除新 Result 中的缓存输出，旧结果/缓存保留；重新启用和核心无模型环境复用无新增 attempt |
| 固定 VLM 路由 | `intentionally_changed` 保持；Plan 拥有解释/授权，不恢复由分数自动选择远程模型的流程 |
| 模型移植一致性 | `preserved` 于已选配方：仅5个 development 输入/模型；Freepik 最大概率差0；640共18实例位置/数量/标签相同，最大分数差4.172325134277344e-7。不是与旧模型分类质量相同的声明 |
| 旧系统质量与吞吐数字 | `not_comparable`；没有逐图真值、留出集运行、全量业务耗时或本轮成本补测；原历史报告和人工反馈不改写 |

安装交付门槛已在隔离环境通过：真实 CLI/MCP→Run→Result→review/expand→Plan create，
双模型/两种单模型/全关闭/重启用交付8/4/4/0/8条 available；缺固定权重阻塞，恢复原快照；
无 torch/Transformers/Timm/NudeNet/ORT/NumPy 的核心 Host 可读并复用。
最终默认检查1336 passed、16 deselected；原有 local_fixture/scale 边界保持。

最终隔离 wheel SHA-256：`6c35c4d05679311b08121e0278d5520a9d52465411214f67180f8e0807bdc373`，
版本字符串0.10.2；源码基线`615c3359941927515f0c0a8738a3f08122bcad46`及本任务差异见
`/private/tmp/mediasense-sensitivity-260912/candidate-4/`。构建排除其他线程未提交的 Plan 等改动。
PreCheck存储18/Run快照8保护新写入；隔离17→18与旧备份回滚验证通过，旧 Result 不转换。

**本任务没有切换日常安装、改实际用户/业务 Dataset 配置或执行真实媒体 Apply。** 后续日常部署
必须按唯一安装 runbook 核对原未终结 Run 与一致备份。MPS可用性、640镜像来源限制、其他平台、
全量性能和长稳态仍是明确边界，不由本轮隔离成功推断通过。

## 2026-09-12：Plan 当前基线重新验收与输入补修

本轮从干净的 `615c3359941927515f0c0a8738a3f08122bcad46` 核实本包实现已存在，保留其他任务的并行改动。补齐两处既定 schema 的实现遗漏：显式 `page.limit:null` 不再当作省略；create/update 拒绝空偏好键，非法组合不写入、不读取 PreCheck、不占用请求回执。没有修改合约、SQLite 存储语义、Skill 调查方法或最终确认方式。

| 能力与归属 | 本轮运行与交付证据 |
| --- | --- |
| Tool/SQLite：可选说明、偏好、候选生命周期 | 源码与隔离安装专项各 **234 项通过**，包括三字段 52 种组合、零 Read/分析、版本/身份、并发/取消/崩溃/重放及 seal recovery；新增 5 项反例在旧实现失败后修复。全默认 **1292 passed＋4 项沙箱回环失败**，相同代码放行后 **4 passed**，合计选中的1296项全部通过，16项原有 opt-in 排除 |
| Skill：主动收集、保留范围、完整接受 | 六类独立合成推演；24 条 Plan 和5条 Read请求校验通过，24条 Plan 请求进一步在安装 Tool＋合成 Read 中实际执行成功。只有新 HTML 后全案接受分支 seal；不以局部人物/地点纠正充当最终确认 |
| Preview/Host：含义与真实交付 | 新合成 Dataset 的 **42次真实 MCP调用**通过，structuredContent单一、content=[]、无elicitation；准备图片字节分页、80×40解码及Chrome DOM加载证据成立。Chrome正常退出未通过，40秒超时及DOM输出独立保留，不冒充完整浏览器runner通过 |
| 发行与实际安装边界 | 离线 distribution smoke通过，128个package文件匹配快照；新wheel SHA-256 **`f6a8b56645b8f60cdc3734c3887406eb330f122c2585e3e0b40addf7f039db45`**。本轮仅隔离Python3.11.13/core验证，**未切换全局安装**，不能借后文历史升级宣称已交付这两处新补修到日常Host |

迁移分类保持：主动调查与Agent/Human组织判断 `intentionally_changed`；只读媒体、已有Work并发/取消/幂等/恢复 `preserved`；新增说明的实际语义质量、用户注意力和大规模吞吐相较旧流水线仍 `not_comparable`。两处输入缺陷是当前合约符合性修复，不构成已审阅产品语义变更。没有新增AI Album实测或原事件回归，不改写旧Result。

本轮达到源码与隔离wheel的限定可交付状态；构建补丁、约束、失败恢复、实际轨迹及未认证范围统一见[本轮验收](../../../openspec/changes/refine-plan-interaction/acceptance.md#当前基线重新验收与输入校验补修)。所有原始轨迹、合成媒体和数据库位于 `/private/tmp/mediasense-plan-reaccept-6p3o8lhs/`，不入Git。

## 2026-09-12：Plan 日常环境升级完成

用户确认此前四项问题全部独立复核闭合，明确授权执行实际升级。严格使用已验收 wheel，未从共享工作区重建：SHA-256 **`1c454027d2f6b5217e3c3b4f0f6a0f86a7e523bdc4ea282565e0008ce2a4e5e7`**，稳定保留在 `.local/releases/0.10.2-plan-work-20260912/`。该目录的 `installation-receipt.json` 及[日常升级记录](../../../openspec/changes/refine-plan-interaction/acceptance.md#日常环境升级2026-09-12)保存精确目标、依赖、备份、实际入口、回滚命令和失败记录。

| 验收层 | 实际结果 |
| --- | --- |
| 安装及依赖 | 原 uv tool 管理的 `/Users/chengyanru/.local/bin/mediasense` 已切换。保留 Python3.13.5、embeddings extra、全部59依赖版本，新增/移除/版本变化均为0。实际127个包文件匹配选定wheel；旧0.10.2 wheel `68e4ec3152091285513724b84f92cce9aad04968b5e2f46313dd234b1f03302c`、收据及约束可回退 |
| 依赖组合先验 | 原组合在隔离 uv tool 根安装，完整 distribution smoke 和36次 Plan MCP检查先通过；没有把旧Python3.11 core验收直接用于日常extras组合，不下载或执行模型 |
| 操作项目 Skills | `~/Downloads/ai-album-hk-representative-v1`，原 npx skills@1.5.25、Codex目标、四名allowlist、离线且关闭遥测。12文件匹配wheel，四个原生computedHash正确；lock明确指向新稳定wheel导出的Skills，原无无关条目，检查无额外修改 |
| MCP启动与配置 | 原项目 `/bin/sh`＋`~/.config/dotfiles/secrets/mediasense.zsh` 包装不变；MCP TOML、凭据加载文件、用户DINO/0.311配置哈希不变。原启动方式的新Host初始化0.10.2、七Tool合约ID/digest匹配；doctor=ok，DINO prerequisites=prepared、execution=not_checked |
| 业务状态与安全 | 无旧Host进程或Dataset打开句柄，无需中断Agent。四库SQLite一致备份和完整性检查通过，manifest/两份sealed Result备份；两个Work在副本增量加列后原字段及回执/key保留。原业务Dataset未Runtime打开/迁移，状态文件哈希未变，无真实业务恢复/媒体重跑/Geo/模型/Apply |
| 日常实际入口 | 精确CLI smoke通过。经原注册launcher在新临时合成Dataset执行36次MCP调用，保存、重启、非法候选、撤下、两条Evidence字节分页、80×40图片解码、冻结和重放通过；源字节不变，零新增elicitation |

机器与操作项目资源已升级；独立启动链路已验证。**现有Agent会话未宣称热重载**：用户仍需在 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` 新开会话，核对四Skills、七Tools及Plan Work digest `sha256:63676aa36966bea23024ae2538ef4830cc2ce8e42b0af8554c28dbd5a37478e1`。这不授权后续真实业务动作。

实际完整报告 `/private/tmp/mediasense-plan-daily-upgrade-verified/report.json` 已复制到稳定 `evidence/actual-plan-smoke.json`。回退以原wheel＋相同依赖组合及原Skill manager来源成套恢复；原业务数据库本次未迁移，不应无故恢复或覆盖后续新工作。既有Artifact/媒体留原处，不声称全量媒体备份。首次实际检查器误要求所有合约含`$id`而失败，实际Plan检查因此在缺少harness时启动失败；按已有descriptor规则修正检查器、生成原注册harness后完整重跑通过，产品包未改。失败版本及记录保留，不抹去此前开发/浏览器失败。

## 2026-09-12：Plan 信息收集与可选工作保存实现验收及补修

[当前 Plan Work 合约](../../spec/contract/plan-work/index.md)及用户已放行的[开发交接](../../../openspec/changes/refine-plan-interaction/README.md)已实现；[实现验收](../../../openspec/changes/refine-plan-interaction/acceptance.md)记录测试、独立合成行为推演、实际 wheel/MCP 和精确构建身份。最终流程保留预览 HTML 后聊天接受，不新增确认弹窗。

| 能力 | 声明与设计 | 运行实现 | 入口与交付 |
| --- | --- | --- | --- |
| Agent 获取组织决定所需的信息 | 用户可提供知识、背景和材料；调查方法与提问时机开放 | packaged Plan Skill 已修正偏好限制和确认循环；六类独立合成对话覆盖口述范围、文件读取／能力缺失、信息充分、未回答、候选冲突及局部纠正 | Skill 随精确 wheel 交付；代表性职责路径通过，不认证真实媒体语义质量或所有未来 Agent |
| 可选说明、独立偏好、候选保留／替换／撤下 | 三字段省略／清空、原子写入、版本／幂等、无候选可读 | 52 组三字段组合及错误／长文本／零 Read／恢复反例通过；复用进程锁、取消提交门和 seal reservation；v3 存储无损增量加列 | 209 项已安装包检查通过；实际 stdio MCP 保存、重启、撤下、再提交和 seal 通过 |
| 最终预览中的必要决定说明 | 同一 Candidate 的说明、Source Set、Evidence 引用必须可审阅 | PreviewDocument／HTML 交付并转义 decision_notes；无候选拒绝最终 Preview | 真实 wheel HTML 和 identity 核对通过；24 次 MCP 调用均为单一 structuredContent、零新增 elicitation |
| 最终接受与冻结 | 精确 HTML → 聊天接受 → 同内容冻结；补充信息不等于批准 | 缺失／错误确认及旧 revision 拒绝；记事后刷新 revision 可复用仍有效的同内容接受 | 证明现有本地客户端上下文传递及内容核对，不证明独立真实人类认证；未切换日常 Host |

迁移判断：Agent 组织判断、主动获取信息和显式接受延续 `intentionally_changed`，替代历史固定流水线把局部推断传播为目录名的方式；媒体只读、已有 Work 并发／取消／重放和封存保护 `preserved`。新可选说明在旧实现无对等工作状态，其质量、用户注意力、吞吐及成本比较为 `not_comparable`；这里只证明轻量更新没有 Read／模型／Geo 调用，没有重跑 AI Album 或原事件，不从目录差异推断回归。

隔离 wheel 为 0.10.2，SHA-256 `c6623dd6e96612a816d16ff2363d9d2e58c44439300430fe5478c8c0b7cc3a66`。它包含当前共享工作区，不能仅凭相同版本号视为日常已安装包。本次同时修复实际安装暴露的 MCP schema 外部引用和 Frozen Plan 默认历史路径；未改写合约、封存 Result 或真实媒体。通用 distribution smoke、Skill/runbook 一致性已通过；全局安装切换与真实 Apply 不在本次授权内。最终默认测试 **1271 passed、16 deselected**；初轮环境失败、恢复及命令均见实现验收。

### 用户复核后的三项缺口与补修

用户明确暂不通过首轮整体验收。正常保存路径的 55 项合约检查、旧 wheel 字节和 24 次 MCP 轨迹成立，但不足以证明非法候选身份保护、所有结构错误及真实图片显示；此前的完成表述按此收窄。

| 缺口 | 处置与实际证据 | 状态／界限 |
| --- | --- | --- |
| 输入 plan_ref 覆盖 Tool 预留身份 | 按当前 Candidate schema 验证原输入后才 materialize；另外阻止 sealing-owned 字段注入。MCP 对 plan_ref/contract/seal 均返回 candidate_invalid，Work 不变，后续 seal 三处 Plan 编号相同 | 对既定契约的符合性缺陷已修复；不是允许修改 Plan 身份的合约变更 |
| other_outcomes null/数字成为内部故障 | schema 失败不遍历字段；直接 Tool 和 MCP 反例返回 candidate_invalid 且无 Read／写入 | 保留未知异常立即暴露，不靠宽泛异常捕获通过验收 |
| HTML 未显示已有准备图片 | 经 Read 获取 covering_evidence 和实际 Evidence access/source_items，核对组内实际来源、解码并呈现 | 新 wheel 的真实准备 JPEG 在 Chrome complete=true、naturalWidth=80、naturalHeight=40；不认证所有浏览器或未选样本 |

补修隔离 wheel SHA-256 `31be3b85e6cd29f08c48f17dab15bfd06a55df5ab50fca07c302f1d9e790e438`，与首轮 wheel 保持分离。新安装包 **226 项**通过、默认测试 **1288 passed／16 deselected**、实际 MCP **35 次**调用通过、通用 distribution smoke 通过；[最新验收记录](../../../openspec/changes/refine-plan-interaction/acceptance.md#用户复核后的三处补修)保留路径、反例、浏览器证据及最终默认测试结果。三项已获用户独立复验通过；无全局切换或真实媒体 Apply。历史 AI Album 比较未重跑，前述 intentionally_changed／not_comparable 边界不变，不能把本次缺陷修复描述为旧模型质量已改善。

### Preview 选定 Evidence 分页补修

用户随后指出新的 P2：选定两条 Evidence 的元数据超过响应上限，第一页无图、第二页有图，渲染器忽略 next_cursor。该问题属于已承诺的读取完整性缺陷，不能用上轮图片显示证据覆盖。现已固定原 Result、原选集和 limit=16 续读至结束，不扩大最多 16 条 Evidence；循环或续读失败明确报错，不发布部分预览。

真实 Result/Read 的字节分页反例在旧 wheel 上复现一次 Read，修复后同一选集两次 Read 并显示第二页图片；源码相关 **136 项**、新隔离 wheel **229 项**、实际 MCP **36 次**调用通过。新 wheel SHA-256 `1c454027d2f6b5217e3c3b4f0f6a0f86a7e523bdc4ea282565e0008ce2a4e5e7`，127 个 package 文件与源码一致，distribution smoke 通过。分页轨迹、独立浏览器 80×40 显示证据及首次可选浏览器超时均保留在[最新验收节](../../../openspec/changes/refine-plan-interaction/acceptance.md#最新补修选定-evidence-的字节分页)。本次未重跑 AI Album 比较或默认全集，不扩大旧测试认证范围；本轮自验完成，待用户复核，未全局切换或执行真实 Apply。

## 2026-09-12：厂商体系三项验收补修与 0.10.2 日常交付

用户复核通过 B 方案和核心结构，同时指出三项未覆盖的反例。本节承接该复核；之前的1,151项源码测试、244项安装测试和四次 Run 仅证明其当时范围，不证明这些反例已通过。三项补修已完成，并在隔离安装和日常 **0.10.2** 中验证。

| 原缺口 | 处置与当前证据 |
| --- | --- |
| 配置无法适配标准坐标与源尺寸 | 遗留 `regression` 已修复，配置能力 `preserved`、`implemented`。fields 以 tag_pairs 声明纬度/经度或宽/高；完整配对来自同一文件，尺寸只读当前源素材。安装 ExifTool→MCP→Read 返回配置选择的80×40尺寸；额外 GPS Run 将 EXIF:GPSDestLatitude/Longitude 中的合成测试值送入标准 gps_coordinates，再形成真实 Geo 待处理坐标22.3/114.2（WGS84）。无服务配置时诚实阻塞，测试随后取消该临时 Run；未发出地图请求。 |
| 重启 Host 后坏 YAML 阻止旧任务恢复 | `intentionally_changed`，`implemented`。Dataset Open 保持可访问并给出配置错误摘要，不伪造有效知识；有快照的恢复及旧 Result 读取独立于当前 YAML，新工作仍严格校验。实际关闭并重开 MCP Host，保持 YAML 损坏，恢复原快照并完成 Result；快照内容和源文件字节不变，新 start 仍返回 configuration_invalid。 |
| integer 经浮点转换发生精度损失 | `regression` 已修复，类型语义 `preserved`、`implemented`。以精确分数判断整数并返回整数，拒绝非整数；Read 实际返回9007199254740993。测试覆盖原生整数、正负字符串、十进制、可整除分数及大数附近非整数。metadata 解释版本进入 Work 身份，修正不会继续复用旧的错误整数输出，也不改写已封存 Result。 |

契约、机器 Schema、[新增示例](../../spec/contract/manufacturer-knowledge/example-add.yaml)、Dataset Open 诊断和安装说明已同步。文件格式仍为 schema_version 1，复用既有字段、Run 和 Observation；未增加公共 Tool 或独立服务。DJI 随包规则本轮没有修改。

### 精确构建与验证

- 基底为 `20b86a987714e630344d10df9e3807141a8d8474`。发布保留目录 `.local/releases/0.10.2-manufacturers-20260912/`；最终源码在 `candidate-02/source/`，`source-manifest.json`、`source.patch` 保存24个选入变更和完整文件摘要。未提交的其他评测修改未混入包；本节之外的用户文档修改保留。
- wheel：`candidate-02/wheel/mediasense-0.10.2-py3-none-any.whl`，SHA-256 **`68e4ec3152091285513724b84f92cce9aad04968b5e2f46313dd234b1f03302c`**。candidate-01/02 的包字节完全相同，第二次仅修正测试配置隔离与版本断言，因此125项安装测试及增强厂商 smoke 的证据适用于最终同一包。
- 最终默认源码套件 **1,179 passed，16 deselected，231.10 s**；安装代码专项 **125 passed，16.84 s**；真实隔离 uv tool 分发检查、Ruff、离线锁一致性和文档/发布副本检查通过。默认排除项未执行。
- 隔离与日常安装各执行增强 smoke：6张生成 JPEG、5个完成 Run，以及1个进入真实 Geo 待处理集合后取消的 GPS Run。覆盖新增/修订/停用/撤回、无变更复用、原 Result 不变、精确整数、标准尺寸，以及坏 YAML 下跨 Host 恢复。厂商 smoke 的模型和外部 Provider 调用均为0；没有把受阻 GPS Run 计作完成 Result。

### 日常安装与现有环境

日常 `/Users/chengyanru/.local/bin/mediasense` 已由原 uv tool 管理器更新到0.10.2。Python **3.13.5**、`embeddings` extra及**59项依赖版本**全部保留；实际安装的**127个包文件**与该 wheel 一致。`precheck/dinov3.py`、`runtime/embedding.py` 与固定配方文件保持原安装字节；用户启用的 DINO/0.311 配置文件、原 MCP 配置和凭据加载脚本的 SHA-256 均不变。本次未打开或重建业务 Dataset，也没有数据库 schema 迁移。

原操作项目 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` 的四个 MediaSense Skills 使用原 **npx skills@1.5.25** 离线更新，遥测关闭。12个文件匹配同一 wheel，四个 computedHash 经原生 localeCompare 排序及 SHA256(path+content) 复核；其他锁条目不变。升级前未发现日常 MCP Host。升级后 doctor=ok；使用原 `/bin/sh` 和凭据加载方式启动的新 Host 返回0.10.2、七个匹配的合约 ID/digest，临时 Dataset Open 成功。独立新连接的验证不声称原业务 Agent 已热重载 Skill。

`before/` 保留旧 wheel、收据、依赖、四个 Skill 及项目锁；`actual-installation-verification.json`、`skill-lock-verification.json`、`candidate-02/package-verification.json` 与日志记录结果。生成媒体和状态在 `/private/tmp/mediasense-manufacturer-repair-260912-dr649rbx/`，均不入 Git。回退仍须遵守安装 runbook：旧日常包的解析器不支持新建 Run 的 v7 执行配置，不能仅凭数据库 schema 版本未变就回退后续业务状态；本次没有改动这类业务状态。

保留的失败及范围：首轮相关检查99项通过、1项失败，该旧 Host 用例读入了用户 DINO 默认设置；按隔离配置连同配置/契约检查重跑后118项通过。首次完整套件有1177项通过、2项失败，分别是 MCP 子进程未隔离用户设置及写死0.10.1的断言，修正后的完整套件如上。沙箱下 doctor 将实际默认数据目录判为不可写，按正常系统权限核对后通过，未降低检查。操作项目内的 fixture 校验确认所有列出文件 SHA-256 一致，但整个目录3,188,720,647 bytes超出运输包2 GB上限，因此不宣称整包 verifier 通过；该目录本轮仅作为既有操作项目更新 Skill，厂商测试全部使用独立合成媒体。真实厂商型号/固件矩阵和地图服务质量不属于此次补修认证。

<a id="manufacturer-information-delivery"></a>

## 2026-09-12：厂商知识文件契约与隔离安装交付

用户选择 B 方案（随包基础知识＋个人 YAML 增量），授权先定文件结构和字段契约再开发。[当前契约](../../spec/contract/manufacturer-knowledge/index.md)已承接唯一字段定义、示例和失败语义；[设计](../../design/design-260911-1834-manufacturer-information-system.md)记录目的与权威边界。本次完成了源码、隔离安装、正常 Host/Run 与 Read 的接通；下方 2026-09-11 审计仍保留当时的回归事实。此记录不表示用户逐字段另行验收、日常安装已切换或完整发布完成。

### 能力处置与实际证据

| 能力单位 | 差异与状态 | 本次交付及边界 |
| --- | --- | --- |
| 按设备、媒体及来源条件适配 | `preserved`，`implemented` | DJI 照片和 Canon EOS DSLR 时间规则、Sony XML 字段映射、DJI 原生视频 Encoder 条件均进入随包 YAML。条件及目标标签参与真实提取；未知条件、明确不匹配、优先级和同属性冲突有独立语义。DJI 历史缺时区经验按已记录范围保留，不编造固件范围。真实 ExifTool/MCP 验证含竞争 EXIF/XMP 的 DJI 照片；其他规则及反例由安装代码测试覆盖。 |
| 用户配置新增规则及提取字段 | `preserved`，`implemented` | 在用户配置根的 `manufacturers/` 中新增 YAML，无需修改 Python。实际安装的 ACME 规则改变时间选择，并将 `EXIF:Artist` 作为 `manufacturer.acme.operator` 经 Read 交付，含 Source Item 引用和规则依据。 |
| 知识维护与明确覆盖 | `intentionally_changed`，`implemented` | 旧版整文件覆盖改为稳定 ID 的 add / 完整 replace / disable；重复操作、未知字段和非法正则明确拒绝。doctor / Dataset Open 报告来源、被覆盖来源、停用项及快照身份，执行仍为 not_checked。时区上下文留在现有 TOML，Dataset 只覆盖明确提供的 metadata 键。 |
| 规则修订、失效和恢复 | `intentionally_changed`，`implemented` | 完整知识及上下文进入已有 Run execution_config，metadata Work 依赖快照身份；新 Run 重读，幂等重放和恢复保留旧快照。四次安装 Run 证明无变更复用、修改/停用后重评、删除增量后恢复内置及旧 Result 不变。重开 RuntimeHost 后配置变化/删除的恢复测试通过；已有真实依赖测试继续验证 metadata → GPX/关联/压缩。历史 execution_config 5/6 恢复为无厂商规则语义，不套用当前文件。 |
| 时间解释及局部失败 | `preserved` / `intentionally_changed`，`implemented` | 分开无偏移时区、输出时区、字段 UTC/本地含义和设备时钟补偿。显式偏移仍参与解释；无法表示的补偿保留原候选和失败原因，遵守 fallback，其他属性继续处理。来源、规则竞争和被拒候选不因最终选择而抹去。 |

### 精确构建与环境

- 基础提交：`f5a17634be32afff998b31079c010e1b5c5050ef`。最终候选位于 `/private/tmp/mediasense-manufacturer-release-260912-5/`；`source-manifest.json` 记录选入的38个文件及全部735个源码文件的 SHA-256，清单自身 SHA-256 为 `b9f6495a32850d54f73655d9fb0161e6383d5bfe849287ee9fd8967aba98b56a`。
- wheel：`wheel/mediasense-0.10.1-py3-none-any.whl`，SHA-256 **`4faa4237cf6b62e453b2d60575c54477465c6ba27b1b65bb8c55cac400bb683f`**。版本沿用同期补丁元数据，不能凭 0.10.1 字符串识别此内容。
- 候选保留一致的厂商 runtime/config/composition/doctor 快照，排除同期 DINO 接入；明确选入当时的安装 runbook、Skill 副本与一致性检查。当前共享工作区的 DINO 及其他改动保留；额外运行工作区相关测试，不以此宣称完整 DINO 安装认证。
- 安装目标为 `/private/tmp/mediasense-manufacturer-install-260912-5/`，Python **3.11.13**、核心依赖、无模型 extra。基础依赖新增 **PyYAML 6.0.3**，其版本原已锁定；`dependencies.txt`、`test-dependencies.txt` 和 `package-verification.json` 保留确切版本。隔离准备时仅缺缓存的 av 16.1.0 wheel 曾经显式获取，后续构建与最终安装均离线，未下载模型。
- artifact-only 分发检查通过；全部124个包内文件与安装字节一致，源码清单和安装依赖约束逐项匹配。未替换真实用户配置、日常 CLI、项目 Skill 或业务 Dataset。

### 验证结果与保留的失败

| 检查 | 结果与范围 |
| --- | --- |
| 最终候选默认源码测试 | **1,151 passed，16 deselected，221.81 s**。以物理 `/private/tmp` 路径执行；既有本地回环测试获准运行。默认排除项仍未执行。 |
| 最终 wheel 安装代码测试 | **244 passed，15.46 s**。清除 PYTHONPATH、使用 `pytest -o pythonpath=''`；覆盖厂商、时间、元数据、历史特征、runtime 配置/Host/Dataset 与 Run/Read 契约。 |
| 当前共享工作区相关测试 | **253 passed，12.82 s**。包含最终时钟边界修复、厂商接入、公开契约及安装说明副本一致性；不覆盖所有同期功能。 |
| [真实安装 CLI/MCP 测试](../../../tests/run_manufacturer_knowledge_smoke.py) | 2张生成 JPEG、4个完成 Run；无变更无新增 Work attempt，修改补偿/停用规则改变后继结果，删除用户文件恢复基线；原媒体哈希不变，旧 Result 内容不变，快照可重建。无效 YAML 下幂等 start 重放仍成功，新 start 返回 configuration_invalid。 |
| 静态与资源检查 | 相关 Ruff、diff 空白检查、Schema 副本和文档检查通过；锁文件通过离线一致性检查。安装媒体验证无模型调用、无外部 provider 调用，未使用 HK fixture。 |

失败记录不以最终成功覆盖：初轮默认测试发现 Dataset Open 机器定义缺少新 metadata 摘要，已补齐严格字段及示例；本地回环受 sandbox 限制的测试经明确放行后通过；同期版本变更造成开发环境 editable 元数据过期，已刷新。候选1的 `/tmp` 别名触发既有 Reader 路径一致性检查，改用物理 `/private/tmp` 后通过，未放松 Reader。候选2误带共享 runtime 的 DINO 引用但未带其模块，后续改用一致隔离快照。候选3的测试脚本误将预期 MCP 错误响应断言为成功，修正后通过；其源码测试的同类路径别名问题亦已消除。候选4全套1,146项通过后，额外发现大数/日历边界补偿会溢出，候选5以局部失败和5个回归案例修复。曾尝试全套安装代码测试，其中旧 Plan 测试依赖 checkout 相对文档而无法收集；最终明确分开完整源码测试与适用的安装代码测试。

上述构建和失败材料各留在原候选目录，最终响应及摘要位于候选5的 `installed-smoke/`。此轮证明维护机制和受控输入执行；真实设备所有型号/固件、侧车/转封装矩阵、厂商规则规模与大数据吞吐仍未认证。原片、知识来源、配置、执行和交付的责任不因这些未认证范围而合并。

<a id="manufacturer-information-audit"></a>

## 2026-09-11：厂商信息维护体系专项核对

用户将“厂商定制适配＋用户通过简单配置扩展”命名为**厂商信息维护体系**，并确认其核心能力定位。本次结论是：**通用元数据解释和可追溯性有进步；按条件维护厂商规则、从用户配置扩展提取的能力发生回归。** 不能用字段交付完成证明这个体系已迁移，也不能将旧版没有实际接通的配置算作成功能力。

### 比较边界与实际路径

- 历史基线为 AI Album `c90aa8f04fd0d3348284e0ad19e18462987b1af2`，以 `git show` 读取。当前 AI Album HEAD `6eccb3711f4817242b0700dc370a070680edbaaf` 已拆分 metadata 模块，只作辅助定位；`src/conf/conf.yml` 与基线一致。
- MediaSense 源码为 `b3aa69625fdbdc7692cd1e6bdc935464406d962c`；实际安装 **0.10.0** 的 `runtime/config.py`、`precheck/metadata.py`、`precheck/_metadata_fields.py`、`precheck/_orchestrator.py` 与本次源码逐字节一致。
- 历史执行链：`config_loader.UserAwareConfig` 读取用户 `conf.yml` → `ProjectConfig` → `MetaDataLoader.get_all_config_tags/get_special_recognition_tags` 将条件与目标标签纳入提取 → `get_missing_timezone_config/extract_fields` 执行配置。`missing_timezone_cases` 支持标签、正则及目标时间标签；内置 DJI 规则限定图片，Canon 规则限定 EOS 型号匹配。通用 `exif.<section>.<field>.keys/type` 可增加提取字段。
- 当前执行链：[RuntimeConfig](../../../src/mediasense/runtime/config.py) 仅接受 providers/embedding/sensitivity/geo_network → [编排](../../../src/mediasense/precheck/_orchestrator.py) 调用 `produce_many` 时未传 metadata profile → [MetadataProfile](../../../src/mediasense/precheck/metadata.py) 使用默认时区及全局时间标签顺序 → [FIELD_TAGS](../../../src/mediasense/precheck/_metadata_fields.py) 使用代码中的摄影字段映射。内部 Python 参数可改不等于用户入口可配置。

### 分项判断

| 能力单位 | 判断与实现状态 | 支持结论的证据及限制 |
| --- | --- | --- |
| 通用字段、时间语义及来源交付 | `preserved` / `intentionally_changed`，已有对应 `implemented` 证据继续有效 | EXIF 本地时间、显式偏移、QuickTime UTC 假设分开；原值、候选和冲突保留；实际/等效焦距分开，Encoder 不冒充相机。并非直接复制旧厂商表，也非完整厂商矩阵认证 |
| 按设备/媒体条件覆盖默认解释 | `regression`；`characterized_only`，未形成可配置安装能力 | 旧版可按 Make/Model/MIME 等条件选择目标标签；当前只有全局标签优先级，无同等厂商规则选择与维护入口。单字段 DJI/Canon 成功不能覆盖竞争字段场景 |
| 用户配置新增规则、标签优先级和已支持类型的提取字段 | `regression`；`characterized_only` | 历史真实配置加载器和选择函数的合成探针执行新增 ACME 规则及字段成功；安装 0.10.0 拒绝 metadata/厂商配置表，正常入口连 metadata 时区也未开放 |
| 配置变更后的可追溯重算基础 | `intentionally_changed`，现有 metadata profile/Work 机制已实现；厂商规则修订尚未实现 | profile descriptor、提取器版本和源依赖参与 Work 身份；已有测试证明时间策略改变 GPX 结果、再次运行复用及旧 Result 不变。此基础不等于厂商规则的新增/撤回失效已经完成 |

旧版也有明确限制：用户配置是整文件优先，缺少完整生效快照和配置依赖失效；`get_time_tags/get_all_config_tags` 有进程内缓存。c90 的 `PhotoInfoExtractor._get_field_mappings` 引用不存在的 `src.conf.conf_manager`，会退回内置映射；品牌选择还写死 Canon/Sony/Nikon/DJI/Apple。向 `metadata_field_mappings` 新增品牌不足以接通该路径。这不否定已验证的时间规则和通用字段配置能力，也不能成为丢弃它们的理由。

### 本次验证与可复核反例

合成输入统一为 `EXIF:DateTimeOriginal=2026:05:04 17:33:46`、`XMP:DateTimeOriginal=2026:05:04 09:33:46`、`File:MIMEType=image/jpeg`，另分别使用 DJI/FC220、Canon/EOS 80D、ACME/C1。为 ACME 在用户 YAML 添加 Make 条件和 EXIF 目标；在 `exif.camera` 添加 `operator_label`，来源为 `XMP:Creator=operator-note`。

| 检查 | 实际结果 |
| --- | --- |
| c90 用户配置加载与选择 | 使用 `/tmp` 中的用户 override；新增目标标签进入提取清单；三个输入都匹配相应规则并得到 `17:33:46+08:00`；新增字段值均为 `operator-note` |
| 安装 0.10.0 的同一组字段 | 三者都选择全局优先的 XMP，得到 `09:33:46+08:00`；保留 `capture_timezone_assumed` 和 `capture_time_conflict`。用户无法从正常配置改变这一选择 |
| 安装 0.10.0 的配置入口 | 临时 TOML 的 `[metadata] timezone="America/New_York"` 与 `[manufacturers.acme]` 均得到 `ConfigurationError: Unknown configuration section`；默认 metadata 时区为 Asia/Shanghai |
| c90 摄影映射的新增品牌 | 向 `_get_field_value` 提供 ACME 专用值42和 default值24，实际选择24，证明品牌路由仍有限制 |
| 现有时间与迁移回归 | `rtk proxy .venv/bin/python -m pytest -q tests/test_capture_time.py tests/characterization/test_legacy_metadata.py`：**15 passed，2.32 s** |

历史探针使用 c90 的真实配置加载器、现有 AI Album Python 3.10 环境依赖，以及从 c90 AST 原样选出的时间/字段方法；省略未调用的 Geo/媒体 I/O 方法及全局产品初始化，避免读取真实用户配置。它证明配置→提取标签→选择的能力，不是完整历史 CLI 或真实设备提取认证。安装探针使用实际 uv tool 的 Python 3.13 环境，从 `/tmp` 直接调用配置读取及元数据选择函数；没有将此写成一次 MCP 媒体端到端运行。

这个双时间输入证明两种机制可以产生不同结果，**不证明真实照片中一定是 EXIF 正确、XMP 错误**。真实字段优劣需要有作用范围的设备/制作历史证据。审计未读取 HK fixture、运行模型、调用地图或改动原媒体；吞吐、所有型号/固件、DST 歧义与制作软件矩阵未认证。

### 后续完成门槛

[设计提案](../../design/design-260911-1834-manufacturer-information-system.md)定义规则维护、三种时间含义、生效快照与失效的边界，状态为 review。后续必须同时证明：用户/Dataset 配置新增规则和字段可从安装入口执行并经 Read 交付；同品牌不同范围及冲突场景有明确行为；规则新增/修改/停用正确重评此前未匹配项和真实依赖，旧 Result 不变。发布与验收通过前，本项回归保持开放，不改变此前窄范围字段/时间验收的事实。

## 2026-09-09：证据交付合约与本期迁移范围

当前开发以 [稳定合约](../../spec/contract/index.md)为准。第一里程碑固定对象、关系、属性及读取承诺；第二里程碑才验证代码和安装版接通。本次源码基线为 b52535a，历史比较为 AI Album c90aa8f04fd0d3348284e0ad19e18462987b1af2。时间、embedding 安装接通和旧答案目录名暴露已修复并验收，不重新列为待修项；旧运行审计不代表当前实现。

下面逐项覆盖历史 11 类缓存及其消费用途，并增加不能由缓存类别替代的 Geo、关系和交付边界。它是本台账的本期范围，不是另一套迁移清单。合约位置只指向字段定义，不复制完整 schema。

| 能力／旧用途 | 本期责任与迁移判断 | 当前证据达到哪一环 | M2 完成规则／独立认证 |
| --- | --- | --- | --- |
| metadata：时间、坐标、相机 | PreCheck 采集，Plan 解释；基础能力 `preserved`，来源/失败语义 `intentionally_changed` | `implemented`：保留已验收时间语义与 GPS/GPX；index-v2 的标签/选择策略进入 Work 身份，来源和已知候选经 Result 投影保留。安装 MCP 实际读取受控照片的相机、时间与来源；Geo 投影测试独立核对源坐标。 | 保持已有语义；从安装入口验证新增投影不丢失值、来源和失败 |
| metadata：镜头、焦距、光圈、曝光、ISO、源尺寸 | 修复 `regression`；实际/等效焦距分开属于 `intentionally_changed` | `implemented`：廉价批量采集实际/等效焦距、f 值、秒、ISO、源尺寸；侧车冲突和 raw 值可读。安装包真实提取 50 mm / 75 mm、0.04 s、f/2.8、ISO 400、1200×800 源尺寸，派生尺寸独立。 | 按 [属性义务](../../spec/contract/precheck-read/precheck-attributes.md)采集、归一、保留侧车/冲突、投影并默认交付；不能拿派生尺寸代替源尺寸 |
| metadata：相机序列号、固件、镜头序列号、GPS 高度/版本、源格式 | 保留旧可获取业务信息；当前未接入是 `regression` | `implemented`：对照 c90 conf.yml 接通 Firmware、Sony XML Device/Lens 标签、序列号、GPS 高度/版本及格式；合成字段验证含符号高度、缺值和冲突。安装图像实际交付两种序列号与格式；Encoder 仅保留候选，不能冒充相机。 | 廉价批量采集，缺值据实返回；未知基准不编造；不因很少进入旧 prompt 而静默删能力 |
| 普通 thumbnail | PreCheck 制作、Read 给路径；profile/变换 `intentionally_changed` | `implemented`：安装入口真实生成、解码、默认 review 返回路径及自身属性；source_items 与 represents 分离；源字节不变。 | 安装版真实生成与读取；源只读、变换限制、引用和属性对应 |
| 高清 thumbnail | 为已选中静态视觉来源准备，与 embedding/检测开关解耦；`intentionally_changed` | `implemented`：生产调度与模型开关解耦；两 profile 共享懒解码并独立 Work/Artifact 复用。无模型安装 Run 的显式 review.evidence_refs 取得高清与自身来源。 | 无模型启用也能为所选静态来源提供高清；普通/高清独立复用，不默认处理全成员 |
| 媒体 embedding | 保留本地能力，模型与方法 `intentionally_changed` | `implemented`（保持此前验收范围）：生产 encoder 装配未更换；现有安装、依赖、输入与复用测试继续通过；本轮不重复扩大真实模型邻域/吞吐认证。 | 不重开已修问题；保持有效 profile、输入及复用；更广邻域质量/吞吐另行认证 |
| privacy／敏感性检测 | 本地证据保留，安装入口缺失为 `regression`；默认关闭为确认的成本策略 | `implemented`：现有 config.toml 增加约定 sensitivity 表，local-models extra/安装脚本/doctor/生产双检测器/Run 已接通；安装 MCP 对高清照片和视频帧实际产生四条逐检测器/逐输入 Observation，后继 Run 无新增 producer attempt。缺后端阻塞可恢复；无自动模型下载或远程 fallback。 | 显式启用可运行两类检测，逐输入、逐检测器交代成功/失败；无自动下载或远程 fallback；模型质量另行认证 |
| 敏感性决定 VLM 路由 | 路由归 Plan 策略，`intentionally_changed` | `intentionally_changed` 已保持：交付可追溯本地信号；配置或分数不授权远程调用，生产入口未引入固定 VLM 路由。 | 接通检测时不得私自恢复固定本地/远程路由；信号不构成授权 |
| caption | Plan 对选中证据综合解释，`intentionally_changed` | `intentionally_changed` 已交付：默认图片路径、自身/源项属性与关系共同返回；安装验证实际解码，Agent 可按需打开。没有恢复逐代表 caption/付费流水线。 | 默认交付图片入口和关联属性，Agent 自主看图；不恢复逐代表 caption 缓存或付费流水线 |
| 推断 location | Plan 解释图像和地理候选，`intentionally_changed` | `intentionally_changed` 已保持：两组件候选保留原文本、query_coordinate、来源/投影限制；Plan 新调查与原 Result 分开。 | 候选、Agent 判断、Human 确认、新补查来源分开；不以更多具名餐厅验收 |
| title | Plan 面向整体组织命名，`intentionally_changed` | `intentionally_changed` 已交付：摄影信息、地点候选与阅读入口可由 Plan 消费；安装版 Plan create 接受新 Read，组织命名仍由 Agent/Human。 | 新交付不漏掉旧命名曾用的摄影/地点信息；不要求复制历史目录 |
| translation | 语言转换归 Plan 命名，`intentionally_changed` | `intentionally_changed` 已保持：原始地点文本不改写；Plan Skill 明确按 Human 语言生成展示名，无新翻译缓存或 Tool。 | 保留原始地点文本，按用户语言产生展示名；不新增强制翻译缓存/Tool，不声称已做真实质量比较 |
| 视频帧 | PreCheck 有限采样；方法 `intentionally_changed` | `implemented`：安装 FFmpeg/ffprobe 路径实际交付 1 秒视频的 probe、帧和联系表；格子绑定公开 Evidence 与采样时间，真实 derived_from 链可追溯，局部失败保留。 | 返回位置、尺寸、时长及部分失败，联系表按格子对应公开 Evidence；不得泄露 frame_work_ids |
| 视频帧 embedding／关键帧 | 保留比较能力，方法 `intentionally_changed` | `implemented`（保持此前 encoder 验收范围）：现有精确 frame→embedding Work 校验继续通过；关键帧角色 basis 交付方法、top_k、frame_count 与 compared_evidence_refs；私有 frame/work ID 不作为返回。 | 精确帧输入→编码→关键帧选择可验证，局部失败/复用可读；不以“有类”证明帧覆盖质量 |
| Geo 地址/附近地点 | 公共 Tool 保留；授权、幂等和投影责任 `intentionally_changed` | `implemented`（有界假 provider 认证）：生产获取→Source Item→默认 Read 链路保留两组件状态、查询点、实际源坐标、请求500 m/30项以及复用距离/限制。15 m/120 s 阈值边界、移动、跨 datum、同坐标去重和缺时间同资产范围已针对性核对；阈值地点质量未认证。 | 保留查询点/源坐标/半径/数量/结果状态和投影限制；已取得必须交付。当前采集单元阈值边界已在 M2 针对性核对，真实地点适用性仍未认证 |
| 初步关联、adaptive compression、代表关系 | 保留压缩目的，方法 `intentionally_changed`；最终目录与旧固定树 `not_comparable` | `implemented`：正常 review 项交付实际来源、独立 represents、精确集合、去重计数、时间/类型状态摘要、共同/逐成员依据及限定；多来源和显式非默认 Evidence 用例通过。 | 自身来源与 represented members 分开，范围/依据/角色/损失可追溯；不默认全成员详细汇总 |
| 逐阶段缓存与失效 | 保留复用，依赖完整性 `intentionally_changed` | `implemented`：新增 metadata 字段进入 index-v2 descriptor；普通/高清独立复用，检测绑定真实本地模型和输入；已封存旧 Result 先验原字节后只读投影。安装后继 Run 核对实际 producer attempts 不变。 | 新属性/profile 正确失效，未影响输入复用；旧 Result 不修改；不新增旧缓存 runtime 依赖 |
| 代表信息交付与模型阅读 | 共同返回路径/属性/关系为 `intentionally_changed`；已取得未交付是交付缺口 | `implemented`（受控 MCP 客户端）：单份 structuredContent、content=[]；正常项/故障项/后续页全部验证，损坏项与单项超大均原位交代。公开 payload 与图片路径经受控客户端读取；真实终端 Agent 集成及语义使用质量的认证范围见下方限制。 | 安装 Host 一份结构化业务结果，客户端确实送入一次；不强制 ImageContent。路径可读、图像被打开、Agent 使用分别验证；局部坏项必须有记录且不阻断后续正常项 |

### 0.9.0 发布收尾（2026-09-10）

用户已明确确认第二里程碑验收通过，包括 metadata、历史检测及近上限中间项续页补修。第一里程碑和第二里程碑均完成；本次仅完成发布与实际环境升级，不重开主体合约或质量认证。

本次起点 HEAD 为 `b52535a9fa1021ba29c4e8431cc9ca5125ae4f22`，完整 M1/M2 及验收修复提交为 `125b33f`。发布前确认源码的 105 个 package 文件与已验收候选 `121949a6…` 逐字节相同。独立模型评测工作及其 README/AGENTS 引用保留在工作区，不纳入此次发布提交或构建。

应用升为 **0.9.0**，同步项目锁版本和四个 Skill 的 `0.9.x` 声明；Read 是不兼容协议变化，不能继续作为 0.8.0 或兼容 patch 发布。机器合约和已验收运行时代码保持不变；Dataset manifest 3、PreCheck store 17、Plan store 3、Geo journal 1、Apply store 2 与 Result artifact 2 均不随应用机械升版。

下方三轮 wheel 都是**标记为 0.8.0 的 M2 验收候选**，不是最终 0.9.0 发布包；其哈希、原日志与产物保留。原 848 项默认测试、96 项合约专项、33 项安装回归和受控双模型执行沿用各自原验证范围。本次版本检查、隔离包验证及实际安装证据如下；未重跑模型或真实 Dataset，也未将旧日志冒充本次执行。

最终发布源码为 `8a3df9fa9a96b7057a706e13936f91b983c6b773` 的干净 Git 导出，构建不读取混有无关评测引用的工作区 README。最终 wheel：

- 路径：`/Users/chengyanru/repos/personal/mediasense/dist/mediasense-0.9.0-py3-none-any.whl`
- SHA-256：**`66745af1eed9fe4d2d0ae7f9dc31fa47c1a9a84a5826559d2ab8551c9371344a`**
- 源码／导出／wheel／隔离安装／实际安装的 **105 个 package 文件逐字节一致**。与已验收 `121949a6…` 候选相比，仅四个 Skill 的兼容版本声明改变；Python 实现、全部机器合约与 Skill schema 引用保持原字节。wheel 元数据为 0.9.0，README 来自干净提交，不含无关评测入口。后续证据文档提交不改变这个 wheel。

本次重新执行的检查：

| 检查 | 本次结果与范围 |
| --- | --- |
| `uv lock --check --offline`、`ruff check src tests`、`git diff --check` | 通过；锁文件只有 mediasense 项目版本变化，无新依赖下载 |
| 隔离 3.13 环境运行版本、CLI、Host/config、Honeycomb、Skill 与合约检查 | **155 passed，10.92 s**；使用已安装 wheel，`-o pythonpath=''` 禁用源码注入，包含原96项合约专项。发布快照一致性检查已取消 M1 时对 Read 的豁免，九份机器定义全部检查 |
| `run_distribution_smoke.py <0.9.0-wheel> --offline` | **distribution smoke: ok**；已有 Python 3.11、独立 uv tool/Honeycomb 环境，CLI/doctor、7 Tool、MCP dispatch、schema 和四个 Skill 通过 |
| `run_precheck_corrections_smoke.py --host <isolated-install>/bin/mediasense` | Python 3.13 安装 Host 通过；metadata 拒绝依据、合法524278/524288字节终页、真正超限局部故障、同一 limit=2 的两种中间项完整续读、历史3条缺口与1条可证明输入均保留；source/legacy 原字节不变 |
| 实际 CLI 和已有注册的 MCP 启动命令 | version/doctor 为 **0.9.0 / ok**；新建的验证 MCP 进程 initialize 报0.9.0，7个 Tool 可发现；临时合成 Dataset 的 **10份完整 Read 返回与隔离保存产物逐对象相同**，单份 structuredContent、content=[] |

实际安装收尾：

- CLI 仍是 `/Users/chengyanru/.local/bin/mediasense`，指向 `/Users/chengyanru/.local/share/uv/tools/mediasense/bin/mediasense`，由原 `uv tool` 管理。使用上述确切 wheel 离线替换，保留 Python **3.13.5**、`embeddings` extra 及全部 **53个依赖的原版本**（含 Torch 2.13.0、Transformers 4.57.6）；uv 安装日志确认只替换 mediasense。receipt 保留 wheel 路径、extra 和已展开的依赖版本约束，不依赖临时约束文件存活。
- 首轮识别并升级的用户级四个 Skill 在 `/Users/chengyanru/.agents/skills/{mediasense,mediasense-precheck,mediasense-plan,mediasense-apply}`；当时漏查了实际操作项目内的副本，因此这项证据不能证明所有实际加载的 Skill 已同版，补正见下节。升级前11个文件均精确匹配仓库历史版本，无本地定制；由 **0.9.0 自带的 `mediasense skills upgrade --target /Users/chengyanru/.agents/skills --json`** 整组升级。升级后11个文件与 wheel 完全一致。未迁移为 repo/Honeycomb 目录，未触碰其他 Skill。
- 实际 MCP 注册位于 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.codex/config.toml`，保留原 `/bin/sh -c` 加载既有密钥环境后 `exec /Users/chengyanru/.local/bin/mediasense mcp` 的命令。本次只读取并使用其启动配置，未修改或遍历该 fixture 的媒体和 Dataset。MCP 配置、密钥脚本、用户配置及已记录的无关 Skill 文件共 **32项原哈希/缺失状态不变**；未输出密钥值，也未调用地图服务。
- `doctor` 确认 embeddings 依赖可用；`local-models` 仍未安装，敏感性检测仍 disabled。未更改模型配置、既有授权或 Dataset/Result。全程使用离线缓存，无新网络下载、模型运行、地图/付费调用、真实 Dataset 从零验收或 Apply 全量审计。
- **首轮完成 CLI/Host 和用户级 Skill 磁盘升级，但遗漏操作项目内的 Skill，实际使用环境对齐当时并未完整完成。当前主 Agent 会话未重启、未宣称已重新加载。** 必须先完成下述项目副本补正，再在原操作位置新建 Agent 会话加载0.9.x Skill 与新 Host；这次独立 MCP 验证进程的成功不代替当前客户端会话切换。没有修改其他 MCP 服务，也没有推送或远程 release。

本次临时证据统一保留于 `/tmp/mediasense-0.9.0-release/`：`package-verification.json`、`release-checks-verified.log`、`distribution-smoke.log`、`isolated-mcp/{summary.json,responses.json}`、`actual-install.log`、`actual-verification-verified.log`、`actual-verification.json`、`actual-doctor.json`、`actual-tools.json`、`actual-mcp-responses.json` 与升级前后依赖/配置指纹。`verify_actual.py` 保留真实注册启动及合成结果重读的复核步骤；临时输出、wheel 和原日志均不入 Git。首次验证脚本误用了未存在的测试文件名，未运行测试；使用正确清单得到上表155项。实际 Host 初次对合成 workspace 的 `/tmp` 别名请求按原合约拒绝为 source_mismatch，使用封存的 `/private/tmp` 精确定位后通过；没有为此改实现或旧 Result。

仍未认证的质量／吞吐／客户端边界沿用下方记录，不由升版或安装成功扩展：模型与代表/关键帧质量、广泛 codec/RAW/HEIF/HDR 矩阵、Geo 15m/120s 的真实地点适用性及 live 服务条款/配额/费用、大数据吞吐与长故障 soak、全量真实 Dataset、具体 Agent 客户端大页完整交付与语义使用质量。

### 0.9.0 实际项目 Skill 安装遗漏补正（2026-09-10）

用户反馈操作会话已发现七个 Tool，CLI 为0.9.0，但 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.agents/skills/mediasense-precheck/SKILL.md` 要求0.8.x，因此没有开始处理数据源。只读核对确认该项目内四个 Skill 均仍是0.8.x。此前仅核对用户级 `~/.agents/skills` 并把它称为完整实际使用位置，遗漏了已找到 MCP 注册的同一项目内的 Skill 目录；这是发布安装收尾遗漏。使用者暂停 PreCheck 符合兼容性要求，七个 Tool 可发现不能代替 Skill 版本一致性验证。

本次起点为 `7fbdc77`，工作区干净；该提交中的独立模型评测工作保持不变。沿用用户原有实际安装升级授权，只处理明确反馈的项目 Skill 目录，不遍历其他项目、不改变安装拓扑。升级前四个目录无符号链接，全部11个文件能逐字节匹配仓库历史发布内容，文件集合与已验证 wheel 相同，无本地定制；备份与指纹保留于 `/tmp/mediasense-0.9.0-project-skills-correction/`。

使用现有0.9.0安装版执行 `mediasense skills upgrade --target /Users/chengyanru/Downloads/ai-album-hk-representative-v1/.agents/skills --json`，实际返回四个 Skill 全部 upgraded。升级后11个文件与最终0.9.0 wheel逐字节一致，兼容声明均为0.9.x；包 SHA-256仍为 `66745af1eed9fe4d2d0ae7f9dc31fa47c1a9a84a5826559d2ab8551c9371344a`，没有重建包或修改主体合约。该项目 MCP 配置原哈希不变。`verification.json` 记录结果；此次只写四个 Skill 目录及原台账，没有读取或处理 fixture 媒体、修改 Dataset/Result、调用模型或地图服务。

本次补正完成的是项目 Skill 的磁盘副本。使用者仍需在该操作项目新建 Agent 会话，确认加载0.9.x Skill；不把磁盘更新说成旧会话已生效，不终止当前主 Agent。上一节CLI、依赖、包及公开Read验证仍有效，但其原“实际使用环境完整升级”结论以此补正为准。

### 项目级 npx Skills 管理与全局清理（2026-09-10）

用户进一步明确：MediaSense Skill 应保留在实际操作项目，删除全局副本，并通过 `npx-skills-manager` / `npx skills` 管理安装和对应锁文件。此前使用 `mediasense skills upgrade` 只同步了文件，没有维护已有 npx 项目需求记录；因此上一节11个文件一致并不等于锁文件完整。以上用户级升级是历史步骤，最终安装范围以下述状态为准。

使用离线缓存中的 **skills CLI 1.5.25** 完成，只通过其正常 remove/add 管理入口写安装，不手改锁。全局 `ls -g --json` 显示四个 MediaSense 的 source 均为null，全局锁原本无对应key；实际还有四个 `~/.claude/skills/` symlink。执行明确四名的 `remove ... -g -y` 后，CLI不再列出、全局锁无对应key、canonical目录和agent链接均不存在；其余24个全局Skill和已记录的无关文件/链接不变。后续全局批量操作不应重新安装这四项。

操作项目 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` 原 `skills-lock.json` 仅有 mediasense，source为 `../../repos/personal/mediasense`、sourceType为local，另外三个文件副本无锁记录。沿用这一既有本地来源和实际Codex目标，用显式四名allowlist执行 `npx --offline skills@latest add /Users/chengyanru/repos/personal/mediasense --skill mediasense mediasense-precheck mediasense-plan mediasense-apply -a codex --full-depth -y`。CLI正常写锁为四项，仍使用相对本地source；逐项按该CLI算法验证computedHash与实际安装内容一致，11个文件仍与0.9.0 wheel完全相同。此版本对该local source记录source/sourceType/computedHash，未生成skillPath；未手工伪造它。项目已有Claude Code入口链接保留，MCP配置原哈希不变。

这是**已有本地来源的项目锁修复**，不声称远端发布托管或跨机器无条件恢复；恢复仍依赖相对路径处存在正确版本的源码。未使用尚未确认的远端内容、未推送、未下载。该操作目录不是Git仓库，项目锁只在其本地落盘，不在MediaSense源码仓库另建需求清单。此次没有改变0.9.0发布包或应用，CLI仍为0.9.0；该用户的后续Skill管理应走npx入口，避免仅用打包复制命令而使项目锁再次脱节。

备份、前后CLI列表、安装日志和 `verification.json` 位于 `/tmp/mediasense-npx-skills-cleanup/`；全局删除列表已收敛，项目四项锁与文件均验证。没有媒体/Result/Dataset处理，也没有模型或地图调用。当前Agent会话没有重启；操作项目的新会话加载项目级0.9.x副本。全局清理与项目锁变化不影响CLI/MCP服务本身。

### M2 中间页续读补修与已通过验收的历史候选（2026-09-10）

用户第二次复验仍判定 **暂不通过**；metadata 与历史检测两项已经通过。新增分页遗漏已修复并完成下述验证；此处保留当时的待复验阶段记录，后续用户已确认通过，见上方发布收尾。此前有效证据继续保留。

修复保持原合约及 cursor/limit 绑定：先按实际封套尝试完整页面和可交付前缀；后续项留到自己的页面判断。当首项连同实际必需的 `stop_reason=byte_limit` 仍无法交付时，原位生成 `response_item_too_large` 局部故障，再装入后续项。局部失败不改变 Result、accounting、选择顺序和总数，不要求调用方改变 limit 或放弃原游标。后续大项若在自己的终页可以合法交付，也不会在前一页被提前判为超限。生产改动仅为 `precheck/read.py`，已通过复验的 metadata 和历史检测实现未改。

[完整续页回归](../../../tests/test_precheck_delivery_regressions.py)新增9个用例：默认入口与显式 Evidence 选择各覆盖4个中间页阈值，另加一个“后续大项在终页可与短故障记录共同交付”的反向检查。指定的8个中间页用例在修复前 **4 failed / 4 passed**；最终该回归文件 **33 passed**。所有续页保持 `limit=2`，核对游标推进、逐项顺序、不重复不漏项、故障后的正常项、精确字节数，以及 Result 原字节和 accounting 不变。

最终 wheel 的[安装 MCP 复验](../../../tests/run_precheck_corrections_smoke.py)实际返回：

| 中间项单项页，不含 stop_reason | 所需完整中间页 | 同一 limit=2 下的结果 | 实际页面字节数 |
| --- | --- | --- | --- |
| 524261 | 524288 | 正常首项 → 完整中间项 → 正常后项 | 3746 / 524288 / 3393 |
| 524278 | 524305 | 正常首项 → 中间项局部超限＋正常后项 | 3746 / 3623 |

故障页面仍是 MCP `isError=false`，`content=[]`，一份完整 `structuredContent`；total 始终为3，最后游标为null。这些结果是本次真实安装入口调用，不是仅对大小函数或注入组件的测试。

本次验证记录：

- 完整默认套件重新执行：**848 passed，16 deselected，78.54 s**，包含原96项合约专项；排除的 local_fixture/scale 不计入本次认证。
- 新建 Python 3.13 隔离环境安装新 wheel 和 pytest，在 `/tmp` 运行回归、禁用源码 pythonpath 并断言加载位置为该安装的 site-packages：**33 passed，10.42 s**。
- 扩充的 MCP smoke 与原离线发行 smoke 均通过；metadata 拒绝依据、历史逐条检测及已证明输入同时继续验证。`ruff check` 和 `git diff --check` 通过。
- 源码、新 wheel 与新隔离安装的 **105个 package 文件逐字节相同**；对比上轮 `838dcd3…` wheel，package 中只有 `mediasense/precheck/read.py` 变化。机器合约及其发布副本未变，原正反例保留。

本轮历史验收候选（包内版本 0.8.0）：`/tmp/mediasense-m2-middle-dist/mediasense-0.8.0-py3-none-any.whl`，SHA-256 **`121949a6557a4a70f68bcf5278395ca45f78e769e85722bc05cc9218fa896660`**。隔离安装在 `/tmp/mediasense-m2-middle-install/`；实际 MCP `summary.json` 与含10份完整返回的 `responses.json`保留于 `/tmp/mediasense-m2-middle-verified-mcp/`。日志为 `/tmp/mediasense-m2-middle-verified-{suite,installed-tests,mcp,distribution}.log`，修复前复现日志为 `/tmp/mediasense-m2-middle-before.log`。旧 `838dcd3…` 和 `e565b1a…` 候选工件均保留，本次输出不入 Git。

本次没有运行模型、地图或付费服务，没有下载模型、启动真实数据验收或扩展 Apply 审计；现用环境不变。其余原认证限制仍有效。

### 首轮补修记录（2026-09-10；分页遗漏的后续修复见上节）

用户验收结论为 **暂不通过**。下列三项实现修复已经完成并验证，当时整体状态为 **待复验**（后续验收结论见上节）；本记录不将实现者的检查替代用户验收。主体模型、机器合约及原有正反例未变，使用原台账记录，不新建平行台账。

| 验收问题 | 实现修复 | 新增交付回归 |
| --- | --- | --- |
| metadata 的原 basis 被投影覆盖 | 优先保留 producer 的原依据，只在没有 basis 时生成来源描述；原依据中的路径转换为确切 Source Item 引用，原值、拒绝原因、其他来源和 producer 信息保留 | 实际 MetadataProducer → 封存 Result → review/expand 验证 Encoder 的原值/拒绝原因与非法焦距 -7；核对 producer 输出未被投影修改 |
| 合法大小页面误判超限 | 按实际返回封套、每项紧凑 UTF-8 字节及逗号计数；只在真正因字节停止的页面加入 stop_reason，终页和达到 limit 的页面不预留该字段 | 524278、524287、524288、524289 字节 × 五种选择/limit 组合，覆盖终页、非终页、整页及字节续页；合法项完整返回，真正超限仍局部报错 |
| 多次历史检测投影后身份碰撞 | 无法证明输入引用时，按已证明 detector 保留一个 not_checked 缺口；basis 中逐条保留原检测的状态、值、profile、观察时间、依据和限定；可还原输入的观测继续使用真实 Evidence 引用 | 跨 detector、同 detector 多帧、成功/失败和已知/未知输入混合均通过公开 Read；原封存字节不变，不生成伪输入引用；同一已证明输入上的重复检测仍拒绝 |

历史缺口的记录列表不合并分数、标签或样本含义，不宣称全视频被检测，也没有放宽 Observation 唯一性校验。已经封存且丢失 metadata basis 的旧 M2 Result 不会被就地改写或偷读 Work 来补字段；需要通过后继 Result 重新投影已有 producer 输出。

本次实际执行的验证：

- [新增回归](../../../tests/test_precheck_delivery_regressions.py)：修复前 **12 failed / 12 passed**；修复后 **24 passed**。反例保留真正超限和重复已证明输入的拒绝行为。
- `rtk proxy .venv/bin/python -m pytest -q --tb=short --maxfail=5`：**839 passed，16 deselected，80.21 s**，包含原96项合约专项。与上一轮815项记录区分，这是本次重新运行的完整默认套件。
- 在新建 Python 3.13 隔离环境安装新 wheel 和测试依赖，从 `/tmp` 执行新增24项，禁用仓库 pytest 的源码 pythonpath 并断言实际 package 位于隔离 site-packages：**24 passed，9.84 s**。
- [安装 MCP 复验脚本](../../../tests/run_precheck_corrections_smoke.py)在该环境通过真实 `mediasense mcp` 调用 Dataset Open / Read：metadata 原依据保留；**524278 和524288字节**的完整终页成功；524289字节项局部超限；三条未知输入历史记录与一条可还原输入记录全部可读；`content=[]`、单份 structuredContent、源字节与历史 fixture 封存字节不变。这里的 metadata 提取输入由受控 ExifTool 适配响应提供，实际 Producer、Result、Reader、Host 和安装资源均使用发布实现。
- 原 `run_distribution_smoke.py <new-wheel> --offline`：**distribution smoke: ok**。首次沙箱运行只因 uv 既有缓存读取权限失败；获准读取缓存后重跑通过，所有安装与 Honeycomb 副本仍在临时目录。`ruff check` 和 `git diff --check` 通过。
- 新 wheel、源码、隔离安装中的 **105 个 package 文件逐字节相同**；已验收 schema 发布副本保持同步。旧 wheel `e565b1a9ef62d7730637609a1d752b4ee2f61ce70b7c9bda505d1d1c3365fbff` 保留未覆盖。

上轮复验候选（保留）：`/tmp/mediasense-m2-corrections-dist/mediasense-0.8.0-py3-none-any.whl`，SHA-256 **`838dcd3c68e7a84efe6058387c01fa8b7400e4b6b9455525ff4e224baea76148`**。隔离安装在 `/tmp/mediasense-m2-corrections-install/`；MCP 的 `summary.json` 与完整 `responses.json` 在 `/tmp/mediasense-m2-corrections-mcp/`。本次日志为 `/tmp/mediasense-m2-corrections-{before,after,suite,installed-tests,mcp,distribution}.log`，临时输出不入 Git；可重跑 recipe 保留在上述测试和脚本中。

本次模型运行、地图及付费服务调用均为 **0**；没有下载模型、启动真实 Dataset 验收或进行 Apply 全量审计。上一轮双模型日志及产物继续保留，但不标成本次重新执行；原质量、吞吐与客户端认证限制仍有效。

### 保留的 M2 实施验证证据（2026-09-09，非验收结论）

源码起点为 `b52535a9fa1021ba29c4e8431cc9ca5125ae4f22` 加工作区中已验收的 M1 交付；本轮实现仍在同一工作区，未提交或替换在用安装。合约 JSON 和 M1 正反例没有为实现而改动。发布 schema 与 Skill reference 从稳定合约同步，旧 Result 原封存字节不改写。

- `rtk proxy .venv/bin/python -m pytest -q --tb=short`：**815 passed，16 deselected**。排除项仍是仓库声明的 local_fixture/scale，不构成那些边界的认证。M1 专用检查维持 **96 passed**。最终补全 metadata producer provenance 后，受影响回归另有 **63 passed**，并重新构建和验证安装包。
- [交付回归](../../../tests/test_precheck_delivery.py)覆盖来源/代表成员分离、多来源、已准备 Evidence 精确选读、缺失/损坏/超大单项三页连续交代、metadata 单位/侧车/源尺寸、独立 profile 共享解码与复用、配置拒绝、后端缺失阻塞恢复、真实输入引用封存拒绝和 Geo 距离/时间阈值边界。已有 Geo 测试新增 default Read 的源坐标、查询点、距离与附近请求范围断言。
- [安装交付脚本](../../../tests/run_precheck_delivery_smoke.py)：最终 wheel 安装于隔离 Python 3.13 环境，从真实 `mediasense mcp` 的 Dataset→Run→Read→Plan create 贯通。每个场景仅生成 **1 张带 EXIF 的受控照片和 1 秒合成视频**。关闭模型与显式开启两检测器的两个场景均得到 **4 个准备好的 Evidence**，核对普通/高清图、源属性、视频 probe/格子关系、逐输入检测、实际文件解码、后继 Result、损坏项续页与源 SHA-256 不变；两个场景各自后继 Run 所核对的 metadata、rendition、video、sensitivity/embedding producer attempt/output 记录完全不变。
- 双检测器场景实际交付 **4 条 available 检测 Observation**（高清照片、视频帧各两类）。NSFW 使用本地 revision `04367978d3474804ab1a00a9bd6548b741764069`，Transformers 4.57.6 / PyTorch 2.13.0 / CPU；NudeNet 3.4.2 / ONNX Runtime 1.29.0 / CPU，已存在权重 SHA-256 为 `c15d8273adad2d0a92f014cc69ab2d6c311a06777a55545f2c4eb46f51911f0f`。显式关闭 ONNX telemetry；没有模型下载或远程 fallback。
- [发行脚本](../../../tests/run_distribution_smoke.py)对 wheel 执行 `--offline`：**distribution smoke: ok**，覆盖独立 uv tool 安装、CLI/doctor、7 个 Tool、MCP dispatch、发布 schema、4 个 Skill 及隔离 Honeycomb 安装。Python 3.11 验证基础发行；本机 3.11 离线缓存缺 ONNX wheel，因此真实模型安装执行使用已有的 Python 3.13 完整缓存。`rtk proxy .venv/bin/ruff check src tests` 通过。
- 验证全程地图/付费模型请求为 **0**，没有读取 HK fixture 或启动真实 Dataset 从零验收，也没有开展 Apply 全量审计。合成 provider 的效果、拒绝、重试和部分失败走既有 Geo conformance/生产组件测试，不冒充 live 请求。

上一轮候选构建（保留）：`mediasense-0.8.0-py3-none-any.whl`，SHA-256 `e565b1a9ef62d7730637609a1d752b4ee2f61ce70b7c9bda505d1d1c3365fbff`。本次可复核临时工件在 `/tmp/mediasense-m2-dist/`、`/tmp/mediasense-m2-release-local/`、`/tmp/mediasense-m2-release-model/`；每个运行目录的 `summary.json` 和 `delivery.json` 保留完整结果，recipe 是上述已跟踪脚本，临时输出不入 Git。双模型首次 Result 为 `precheck-result:fe6d21908fb241912bb8f75bbb37926b10e2cc16b08660beee088722cb131ee1`；无模型首次 Result 为 `precheck-result:69980a0482c4e79b0713a659d866ec1356a25a4016e0ca047e54909c69fd8c28`。

受控 Agent 消费证据：安装 MCP 对一个显式视频帧的完整响应经紧凑序列化、响应大小检查及足够的桥接输出预算，**单份完整进入本次 Agent 上下文**；保留在 `agent-frame-delivery.json`（20956 bytes，SHA-256 `380e0b5084ea0897ea5cacd53b70436514f35300d15351e71233c1dbcee902e1`）。随后实际打开该路径，识别到 FFmpeg 合成色条与数字0，并将它限定为 1秒源视频中0秒处的一个样本；Source Item 同时公开保留了另一个采样失败，未据此声称整段视频全帧已读。Agent 还打开高清 JPEG，观察到800×1200纵向蓝底/黄色矩形/旋转文字，与源1200×800和EXIF orientation=6对应。上层 shell 工具的不足输出预算曾截断另一条长 JSON，因此这次受控、单项的成功不能外推到任意客户端或默认大页。

Geo 针对性判断：保留 `bundle-stationary-complete-link-v1`，没有把其阈值提升为合约保证。测试验证 **14.9/15.1 m、119.9/120.1 s** 的两侧行为、20 m 链式扩张拒绝、medoid 必须为实际成员坐标、跨 datum 分裂，以及既有移动/无时间同资产/精确坐标去重案例。默认返回披露这份有效策略、源坐标和真实查询点；不同点复用附查询点距离与候选范围限制。相同坐标的跨时刻请求复用也不证明同一事件；同资产缺时间时局限必须保留。此证据支持实现与有损范围可追溯，**不认证 15 m/120 s 对真实地点的准确性**。

仍未认证：模型敏感性质量和假阳/假阴、广泛编码器/RAW/HEIF/HDR/色彩矩阵、视觉代表与关键帧质量、真实地图响应/边界质量/配额/费用/条款、大数据吞吐和长故障 soak、全量真实 Dataset，以及其他具体 Agent 客户端的大页、截断处理与语义使用质量。受控 MCP 客户端已验证 `content=[]` 与一份 `structuredContent`，单项完整进入本次 Agent 上下文且图像实际打开；这不等于所有客户端或语义判断通过验收。Plan 命名、翻译与 caption 的质量也没有由这一工程验收推导。

### 完成门槛

对本期每项能力逐环检查：**旧能力及用途 → 明确处置 → 实现 → 安装依赖与配置 → 生产装配 → 公开入口 → Result/返回交付 → 对应验证**。

- schema/文档或 fake 注入只能证明对应层。只有正常安装包和公开入口可达且结果交付符合合约，才能将该能力标记 implemented。
- 对局部 detector/codec 的真实执行使用少量受控输入和已有本地模型即可，不要求重跑真实 Dataset。外部地图可使用 conformance/fake provider 验证效果约束；live provider 质量、账单和条款继续单独标为未认证。
- 必须区分源没有值、策略未启用、执行失败、未实现、未接入、已取得未交付。发布版不能把未实现或未接入包装成合法缺值。
- 安装依赖、配置和 schema/Skill 发布副本必须与实际 release 一起同步。M1 不修改正在使用的代码或宣称安装版已经符合新 schema。
- 未覆盖的真实质量、吞吐和全数据验收不从组件或合约测试推导。实际数据从零验收由用户另行安排；本期不开展 Apply 全量审计。
- 有意改变或暂缓必须在本台账说明业务原因，开发不得自行省略然后宣布完成。

当前状态：**M1、M2 及验收补修均已通过用户验收，以 0.9.0 发布；既有交付证据及独立认证边界保留。** 下表的历史单位能力证据继续保留原认证范围。

2026-09-09 验收修订：敏感性 profile 的分数范围和阈值范围不能混同。Read 现在允许并保留现有99/33阈值和对应 false 判定，此项为 `preserved`；不得以改算法或丢值规避 schema。review 局部不可读/单项超限改为页内明确故障记录，复用原分页继续读取其他项，完整项与故障项分别计数，不能把遍历完成说成证据全部交付。合约检查增加实际纯分类值、完整续页、必需摘要和属性唯一性的正反例。上述是契约和检查修订，不是检测器或 Reader 的生产接通证据；M2 仍须从正常入口验证同样行为。

同日按用户确认的收尾条件完成 M1：状态／值校验只检查正式 observations 容器，合法嵌套扩展按普通数据保留，非法 Observation 仍被拒绝。相关合约检查192项通过；本次未修改主体契约或运行时代码，未开展模型、地图或真实数据验收。

## 2026-09-10：实际 Geo indeterminate 阻塞诊断（未实施恢复）

本次是在M2验收后的业务实验中发现运行品质/恢复缺口，不改写原受控验收结果。源码HEAD `6037952`，相关Geo/PreCheck/runtime文件与实际0.9.0安装相同。对用户指定cmux业务surface及确切Dataset的两份SQLite只读核对：Run `precheck-run:ea216eded808430ead13f6afef40420d` 在 `dataset:6581e19d4fe94e26a10e2f5ca1b34c9b` 中仍blocked，无本次Result。

实际保留：114条历史Geo复用；获授权的54个逻辑查询中42个两组件成功、1个地址成功而附近结果不明、11个未请求。journal保留86条Google请求尝试（43地址成功、42附近成功、1附近indeterminate），billable_units=null。重建原request及授权envelope与持久化的两份指纹完全匹配，上限486、允许未知计费；400余量只是原授权范围下的算术，不能自动扩展为新的未知效果重试权。

当前transport只留下通用错误，无法确认timeout、proxy、TLS或其它原因。原业务Host进程无HTTP/HTTPS/ALL proxy与CA覆盖变量，父Agent的NO_PROXY未传入；当前系统proxy enable flags均0。此证据证明不能假定父shell/Agent网络设置已进Host，但不证明缺代理造成这次故障。未进行连接探测或地图请求。

用户已进一步确认目标：先根据素材中的目标地点选择适用服务，再考虑当前网络可达性。内地地点优先高德等适合内地地址/POI的服务，尽量不先调用Google；海外地点需要当地适用服务，如果网络不可达且没有能满足需求的替代，保存成果并暂停，让用户决定Proxy、网络或其它方式。AI Album的ConnectTimeout回退是有价值的机制证据，但只有替代服务对目标地点/组件适用时才能采用；不能因为高德已获授权或能够连接就将海外查询全部切过去。此前笼统“Google超时→高德→失败则记缺口继续”的推荐撤回，不作为迁移完成标准。

当前业务故障仍只能证明附近接口在42次成功后发生一次通用传输失败，不能断言内地无代理。根据已确认目标，下一阶段业务决策已足够明确，工程计划用“内地首选服务正确、海外服务不可用必暂停、局部有效失败可继续、恢复不丢成果/费用”作为评价条件；待实施的合约补充不等于已经改变当前有效合约。

方案及具体代码/测试证据见[Geo业务阻塞诊断与恢复方案](../../design/design-260910-1726-geo-recovery.md)。诊断及计划阶段该文档状态为review，收敛了7步实施顺序与安装入口验收场景，当时公共合约未改。用户随后授权开发，最新状态见下方开发进展；原诊断判断和证据保留：

| 能力／运行品质 | 本轮分类 | 证据与完成边界 |
| --- | --- | --- |
| Google/AMap请求、datum转换、3/15秒默认timeout、0.3秒限速、AMap暂态infocode | `preserved` | 相关适配能力存在；本批仅实际调用Google。不同网络、proxy/CA和服务商真实表现未由一次成功批次认证 |
| 10次固定间隔重试改为Tool内3次/1、3秒/120秒并受授权上界限制 | `intentionally_changed` | 现有合成检查验证预算、停止和幂等；原费用未知继续保留，不恢复旧的无累计计费上限重试 |
| ConnectTimeout分类及换Provider能力 | `regression`（本轮发现） | AI Album c90的GeoProcessor明确捕获ConnectTimeout换Provider；当前transport将一般连接timeout与响应未知合并，无法区分安全恢复与需保留未知的路径。安装版合成探针已证明分类差异；恢复旧回退能力须增加目标地域/组件适用约束，不能证明此次真实异常就是连接timeout |
| 可配置timeout/provider路线及真实Host网络环境可观测性 | `regression`／`not_comparable` | 旧geo_config能调整timeout/限速/endpoint，新正常配置只有key变量名；requests→urllib的proxy/CA语义不是完全等价，且MCP环境边界是新的部署条件。须补安装入口验证，不能仅凭存在HTTP库宣称网络适应能力保留 |
| 上一坐标推断provider/locale改为按坐标固定有效路由 | `intentionally_changed` | 生产OrderedGeoRoutingPolicy避免跨坐标隐藏状态；不能拿AdaptiveReverseGeocoder单独测试当作生产地域路由认证。用户已确认内地优先适用内地服务，海外必要服务不可达无替代则暂停；当前固定Google优先尚未满足，需要独立的地域/适用性和安装场景验证 |
| 已成功地址在后续整组重试后丢失 | `regression`（本轮发现） | 安装版合成“地址成功→附近503→重复地址未知”返回地址candidates为空，违背现有成功组件保留保证；当前实际第43项的地址仍保留，不能混为同一故障 |
| 原请求幂等、未知效果不自动重发、未知费用不记0 | `intentionally_changed` | journal和PreCheck符合现有合约；已有20项合成检查通过。相比旧系统吞错继续，效果诚实得到保持，但公开恢复出口缺失放大为全Run阻塞 |
| 单点失败局部结束、继续后续查询与Result交付 | `regression`（运行品质缺口）；修复需合约审阅 | 旧metadata层可在Geo异常后继续，但可能丢地址/缓存成缺字段；新实现应保留组件/效果并增加公开恢复。仅孤立且有明确依据的地点级终结结果可继续；适用服务持续不可达无替代必须暂停，不能复制吞错、自动降级或擅改当前indeterminate阻断语义 |
| HTTP级持久预算、跨恢复链防双发及旧批次恢复 | `not_comparable` | AI Album无相应授权/journal保证；当前仅整批admit/complete，无法证明崩溃中途的逐HTTP进度。拟扩展现有journal职责，尚未实施或认证 |

本轮运行已有相关合成检查 **20 passed，2.65s**，日志 `/tmp/mediasense-geo-diagnosis-existing-tests.log`；安装版纯合成传输和成功候选探针 `/tmp/mediasense-geo-diagnosis/synthetic-probes.json`；授权指纹核对 `/tmp/mediasense-geo-diagnosis/authority-verification.json`。没有重跑模型、读取fixture媒体、调用地图、恢复Run或修改业务数据库；真实网络根因、实际费用、尚未实现的恢复流程及跨平台网络能力均未认证。

### Geo 恢复开发进展（2026-09-10；尚未形成可安装交付）

用户已批准按既定业务目标直接开发。起点仍为 `6037952`；同工作区另有独立模型评测改动，未纳入本次 Geo 工作。本节不覆盖 M2 的既有验收或 0.9.0 wheel 哈希，也不将源码检查算作安装入口验收。

已实现的源码范围：

- Geo 成功/no_result 组件保留，Google 只补缺失组件；历史 attempt、未知费用和组件原观察时间在恢复后保留。新的确定暂态传输分类在可重复 Provider、有限周期和累计预算内重试；鉴权/配置、持续服务不可用和额度条件返回 blocked，明确地点级失败仍可继续。
- 同一 Geo Tool 增加显式关联 recovery，原请求重放不发 HTTP，恢复链唯一后继且累计额度不重置；同一已消费授权不能通过换 request_id 再取得一份额度。
- 原 Geo journal 演进至内部 v2：逐操作发送前预留、返回后保存、OS 执行所有权锁、已完成响应不可覆盖；已保存 checkpoint 可本地恢复，只有预留的部分保留未知及上界。新写入守卫同时阻止迁移前已打开的旧连接写入。无关 store 与 Result 格式未升版。
- PreCheck 利用现有 confirmation/resume 接通恢复，恢复响应先入 journal，再投影后继 Work；投影异常后只重放本地响应，旧 Work 输出保留。尝试的执行归属用于区分历史与本次费用。缺少 Provider 变为可解释 blocked，无完成 Result。
- 实际 transport 接入 HTTP(S) Proxy、ALL_PROXY 回补、NO_PROXY、CA bundle 和可调 timeout/限速；配置只展示脱敏接收位置与 `not_checked`，不声称可达。网络 profile 参与授权身份，文件设置可在暂停后的 resume 更新。当前合约、发布 schema 源、PreCheck Skill 说明和安装开发说明同步，尚未构建新发布包。

当前源码与受控证据：

- 最终 Geo/PreCheck 重点检查 **108 passed，26.97 s**：`/tmp/mediasense-geo-final-focused.log`。覆盖正常首项→中间地址保留/附近未知→后项未查→明确确认→恢复投影中断→零 HTTP 重放、未知费用、累计请求、原观察时间、授权复用拒绝、旧无 checkpoint 未知记录与旧写入拒绝。
- 4 项真实 loopback HTTP 检查 **4 passed，0.14 s**。测试仅使用自建 `127.0.0.1` 服务，验证 Proxy、NO_PROXY、429/Retry-After、实际超时及脱敏。默认沙箱中的组合执行因禁止 bind 报 4 个 PermissionError；随后仅对这 4 项申请本机监听权限并通过，不能把沙箱失败记成产品网络故障。
- 默认全套第一次记录为 **855 passed，5 failed，16 deselected**：4 个上述 bind 限制，1 个旧用例仍要求“未配置 Provider=failed”；按用户已批准的“配置前提可恢复阻塞”语义修正为 blocked 后，相关编排回归通过。随后重跑默认源码套件（仅将上述4项 loopback 独立运行）得到 **857 passed，16 deselected，89.52 s**，日志 `/tmp/mediasense-geo-final-suite.log`；另4项已在允许本机监听的受控运行中通过。原失败日志 `/tmp/mediasense-geo-full-tests.log` 保留。
- `ruff check` 与 `git diff --check` 通过。开发 `.venv` 原包元数据仍为0.8.0，已仅用离线缓存重新安装本仓库 editable 元数据为当前0.9.0；没有升级实际 uv tool CLI/MCP 环境。

**开放门槛没有关闭**：可靠离线地域资源尚缺，拟使用 Natural Earth 1:10m Admin-0 Countries 公共领域数据，网络下载授权仍待答复；没有下载，也没有用粗框替代。生产路由当前仍是旧顺序，尚不能认证“内地直接高德、海外不向不适用高德回退”。地域边界/港澳场景、完整114复用＋54查询形状、真实进程终止/并发压力、最终 wheel 的 CLI/MCP 与受控 TLS/Proxy 恢复、四个项目 Skill/lock 一致性均仍需完成。源码组件存在及本节检查不能替代这些门槛。

本次没有恢复业务 Run、访问地图、运行模型、下载模型或数据、读取真实媒体、改写旧 Result、安装全局 Skill、升级实际业务环境或推送提交。当前工作保留为开发改动；完成地域与安装门槛后才可交付新版本。

### 0.10.0 Geo 恢复交付（2026-09-10；隔离安装通过，真实业务未恢复）

本节是上述开发记录的后续完成证据。用户随后明确允许继续及下载地域资源；未增加平行台账。当前源码仍从 `6037952` 开始，保留无关模型评测改动。主体 Source Item/Evidence/Observation 模型与 Read 主体协议未重设计；当前 Geo/Run 披露扩展只在 `docs/spec/contract/` 定义并同步打包副本及 Skill 引用。0.9.0 和全部 M1/M2 历史证据、包哈希保留。

| 目标与迁移判断 | 最终实现和证据 | 保留的边界 |
| --- | --- | --- |
| 地域适用性 `intentionally_changed`；修复旧固定Google优先的运行品质缺口 | Natural Earth 5.1.1 WGS84几何随包分发，按坐标分别路由；内地高德，海外Google。安装版内地Google请求0；只有高德配置的香港输入在零请求下blocked；混合、乱序、GCJ02、香港、澳门、台湾及边界用例通过 | 不把服务路由标签作为法律归属；边界/海岸500米保守带返回uncertain，填海、岛屿、争议范围和资源实际精度未作业务认证 |
| 网络环境、超时和错误分类 `preserved` / `intentionally_changed` | 生产Host接入HTTP(S) Proxy、ALL_PROXY回补、NO_PROXY、CA和timeout/限速；实际本机HTTP验证代理、绕过、429/Retry-After和超时。未知HTTP/JSON响应不会作为地点无结果封存；服务故障在有限次数内阻塞 | 无SOCKS原生支持，不关闭TLS校验，不发线上探测；仍不能据新分类倒推本次历史故障的具体原因 |
| 已成功组件保留 `regression` 已在所述受控链路修复 | 地址及原观察时间保留，Google仅补未完成组件；旧Work和旧Result字节不变；未知效果与费用不变成0 | 实际地图内容、地点准确性和费用仍须独立核对 |
| 公开恢复与累计预算 `intentionally_changed` | Geo关联recovery只有一个后继，原请求重放零HTTP，换request_id不能重复使用同一已消费授权；PreCheck blocked时resume不带decision准备确认，paused时proceed才授权。网络profile变化重新绑定确认；逐HTTP预算预留及已完成响应不可覆盖 | 不自动扩大预算/Provider/数据范围；不可证明旧授权或成本上界时拒绝自动恢复 |
| 进程中断及投影 `not_comparable`（旧系统无此保证） | 5项真实测试子进程kill覆盖发送前、发送后、写execution前、complete前和Work投影中断；OS锁释放后重放已保存证据，原未知预留保留。v2投影owner可证明消失后回收其lease；legacy lease保留原TTL。旧已打开连接也不能写v2 Geo journal | 不声称跨平台网络/文件系统或长时间压力测试已通过 |
| 安装入口及结果交付 `implemented`（下述范围） | 最终wheel实际CLI doctor、7个Tool发现、MCP确认、阻塞、配置切换、恢复和Read均通过。114历史复用＋54新查询的合成旧版0.9账本：原86，新增23，累计109；Read分别报告历史228/本次109，费用null | 没有恢复真实Run、重跑模型/真实Dataset或扩展Apply审计 |

**最终包**：`dist/mediasense-0.10.0-py3-none-any.whl`，SHA-256 **`f4e4ee4454ebb95c7eca7b87abc004eb7ac1fe6b78411c184b89ad9842c26f1e`**。包元数据、uv.lock项目版本及四个Skill的兼容声明均为0.10版本线；仅Geo journal内部版本从1升2，Dataset manifest3、PreCheck17、Plan3、Apply2和Result格式未随应用升版。

验证记录：

- 最终源码默认套件：**879 passed，16 deselected，101.88 s**，仅将4项需监听的loopback测试单独放在安装回归运行；`/tmp/mediasense-0.10.0-final-verified-suite.log`。local_fixture/scale不计本次认证。
- Python **3.13.5** 隔离安装最终wheel，保留实际0.9.0环境全部 **53项依赖版本**，包括torch2.13.0/transformers4.57.6；没有加载模型或下载依赖/权重。安装路径 `/tmp/mediasense-0.10.0-production-profile/`，日志 `/tmp/mediasense-0.10.0-production-install.log`。
- 禁用源码pythonpath、用上述安装Python在/tmp运行Geo区域/恢复/硬进程kill、本机HTTP及M2 Read边界回归：**67 passed，41.91 s**。日志 `/tmp/mediasense-0.10.0-final-verified-installed.log`；显式关闭可选pytest缓存，安装回归没有warning。
- 最终真实安装MCP脚本 `tests/run_geo_recovery_smoke.py` 通过。10个HTTP请求全部在自建127.0.0.1 TLS Proxy内终止，外部地图请求0；内地1次高德，海外故障周期6次Google，换Proxy并明确确认后只新增3次，Read累计9并保留3次indeterminate和费用null。缺海外Provider场景0请求/无Result。完整返回、确认文本和summary在 `/tmp/mediasense-0.10.0-final-verified-mcp/`，日志同名`.log`。
- 现有离线发行脚本 `tests/run_distribution_smoke.py` 通过，日志 `/tmp/mediasense-0.10.0-final-verified-distribution.log`；`uv lock --check --offline`、ruff和diff空白检查通过。
- 源码、最终wheel、Python3.13隔离安装的 **111个包文件逐字节一致**。四个Skill **11个文件**与wheel一致。`npx skills` **1.5.25**通过正常add入口在 `/tmp/mediasense-0.10.0-skill-project` 写入4个项目锁entry；显式Codex目标、四名allowlist、离线并关闭遥测。用该CLI的native localeCompare和SHA256(path+content)核对全部computedHash。锁记录相对的本地wheel解包来源，仅用于隔离验收，不声称远端托管恢复。
- 汇总文件 `/tmp/mediasense-0.10.0-verification.json`；Skill锁核对 `/tmp/mediasense-0.10.0-skill-lock-verification.json`；原始安装日志 `/tmp/mediasense-0.10.0-skills-install.log`。

地域资源：获明确授权后下载 Natural Earth 1:10m Admin-0 Countries 5.1.1，原zip SHA-256 `ce1ac7036499a0edd641fbc093cd209a98f96a49d2eca8480aaacad35138a7f6`；核对官方public-domain条款。只提取CHN/HKG/MAC/TWN几何、不做简化，随包JSON342894字节、SHA-256 `25aca3d92c8b53faf03021601b344f58277577d71f6d63e3d55ea363ed6b257c`。可复现提取脚本 `scripts/build_geo_boundaries.py`，包内 `geo/NOTICE.md` 保存来源与精度限制。下载不含媒体、模型或坐标查询。

最后的checkpoint反例还证明：已经成功解决的旧暂态错误不能把另一地点的明确局部失败变成全局阻塞。已改为按各组件最后一次尝试判断，并保留修复前后日志 `/tmp/mediasense-geo-checkpoint-{before,after}.log`。此前候选wheel SHA-256 `97c31937405931f021eec0c1d1c8f541292eada694dd8215b688572023eff6bd` 保存在 `/tmp/mediasense-0.10.0-candidate-97c3193/`，不是最终交付；其878项源码、66项安装和MCP记录保留，最终证据以上述新包复验为准。

安装验收暴露并修复了两个源码单测未覆盖的接通缺口：Run确认schema未允许新增网络/路由字段、现代恢复链历史授权缺少原确认数量而被Result验证拒绝。现已在完整安装入口通过；历史失败日志 `/tmp/mediasense-geo-installed-smoke-{2,3,4}.log` 保留，其中第3次是测试客户端在尚无确认的blocked状态错误附带proceed，已按现有契约修正为先无decision恢复。另有默认沙箱禁止loopback bind和npm缓存访问的环境限制，经仅针对本机测试/离线安装的权限放行后通过；没有将它们当作实际地图根因。

实际 `~/.local/bin/mediasense` 本次只读复查仍是 **0.9.0**。现用CLI/MCP、操作项目Skills/lock、Proxy配置、业务Dataset/Run和旧Result未改变；没有全局Skill安装、远程推送或release。0.10.0交付停在隔离验证与本地源码提交，实际切换及真实业务恢复按已确定的网络条件另行执行，当前主Agent未终止。

### 0.10.0 实际安装切换与原 Run 恢复准备（2026-09-11）

本节续接上节的隔离交付。用户明确授权实际安装升级、操作项目四个 Skills/lock 同步和原 Run 的有界恢复。起点提交 **`46228e9e74be7893a61ac206c664663004421489`**；wheel 仍是上节最终包，重新计算 SHA-256 为 **`f4e4ee4454ebb95c7eca7b87abc004eb7ac1fe6b78411c184b89ad9842c26f1e`**。没有重新构建包。独立验收记录 `/private/tmp/mediasense-acceptance-260911.md` 的88项安装回归、完整CLI/MCP恢复及再次失败后继续恢复证据沿用，本次未重跑该套件、模型或真实数据从零验收。工作区中的独立模型评测改动保留，未纳入此次收尾。

**实际安装完成；原 Run 已准备恢复披露，尚未授权执行本次恢复，也没有新 Result。业务 Agent 会话切换仍需用户新建会话。**

| 检查边界 | 本次实际证据 |
| --- | --- |
| 升级前无在途执行 | 指定 Dataset 的两个 Run 分别为completed和blocked，worker均为空；Work无运行项，Geo journal两条记录均已关闭。操作项目的两个业务Agent均停在输入提示。核实PID/父进程/命令后，仅关闭旧MediaSense Host子进程57794、66792；父Agent84648、9090和当前主Agent41231保留。迁移前SQLite备份在临时证据目录。 |
| 实际CLI升级 | 原路径 `/Users/chengyanru/.local/bin/mediasense` → `/Users/chengyanru/.local/share/uv/tools/mediasense/bin/mediasense`，仍由uv tool管理。使用最终wheel、`--offline --force --no-python-downloads`、原Python3.13.5、`embeddings` extra和原53项依赖的精确约束；uv仅替换mediasense 0.9.0→0.10.0。全部53项依赖版本复核不变，111个包文件与源码/wheel逐字节一致。 |
| 操作项目Skills/lock | `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.agents/skills/` 的四个Skill升级前11个文件均匹配0.9.0包，无本地定制。通过缓存的`npx --offline skills@1.5.25 add ../../repos/personal/mediasense --skill mediasense mediasense-precheck mediasense-plan mediasense-apply -a codex --full-depth -y`同步；关闭遥测，不使用全局安装。升级后11个文件匹配0.10.0 wheel，四个lock key及既有相对local source不变，computedHash按CLI原生localeCompare算法逐项通过。该操作项目不是Git仓库；本地lock落在该项目，恢复仍依赖原相对源码位置。 |
| 实际配置与doctor | 项目`.codex/config.toml`哈希不变，沿用原`/bin/sh -c`加载既有密钥脚本并exec实际CLI的方式；没有输出凭据或新增Proxy。该启动环境下doctor为0.10.0 / ok，ExifTool、FFmpeg、ffprobe和embedding依赖可用；local-models未安装、敏感性仍disabled。第一次在沙箱且未加载凭据的doctor报目录权限error，不能代表实际环境；使用原启动方式并获实际目录访问权限后通过。 |
| 实际安装Host与合约 | 从操作项目原MCP配置启动的验证Host，initialize明确返回0.10.0；七个公开Tool及contract_id/digest均匹配实际CLI发布清单。该Host通过公开dataset.open打开原Dataset并准备原Run恢复；验证客户端没有elicitation callback，也未发送decision=proceed。取得paused披露后客户端正常退出。收尾无MediaSense在途进程，三个Agent父进程仍在。此证据证明安装Host实际可用，不等于现有Agent已重新加载。 |
| 原状态迁移与保留 | 新Host按支持的迁移将Geo journal升为2，manifest中的geo store声明随之更新；manifest仍为3，PreCheck17、Plan3、Apply2不变。原已封存Result行逐字节比较不变；各capability的producer attempt总数无新增。没有直接修改数据库或伪造状态，所有迁移/恢复写入均来自公开Host操作。 |
| 公开原Run恢复准备 | `resume`不带decision后，原Run经已存工作复用进入`paused / confirmation_required`。范围仍是default exclude、唯一include `260501-HK美食之旅`。保留114个历史复用、42个本批完成、1个附近地点未知、11个未请求。披露只补12个地点：12个nearby_places和11个reverse_geocode，共23个缺失组件；已取得的第43个地址不在补查集。 |
| 效果、预算和当前限制 | **本次安装/准备新增地图请求0**；公开status仍报本批86、历史229、billable_calls=null。原累计请求上限486，剩余400；历史229单列，不重置原批预算，也不把未知记零。原54个查询的地域路由均要求Google，原provider授权名单未扩大；网络profile无Proxy、系统CA、TLS校验开启、reachability=not_checked。未证明网络故障已消失。未执行proceed，因此不能将23个缺失组件写成实际新增23次请求。 |

当前公开披露的精确身份：

- `confirmation.content_identity`：`sha256:68f017fc1d1ed23037c954e996931d30b29c1a13a801bce25364c7051b3bfe2f`
- `geo_request_fingerprint`：`sha256:4eb6b8e4bb80b8ef60f7fa1535b89f16530c47f195893cd38d78a2eba481f44e`
- `execution_profile.identity`：`sha256:18d18732f636e45d2d0495169f65a143758a59209fd5c75a4e2da676ad398968`
- 原请求和恢复root：`request:precheck-geo:85c2e2486d1e1c397b6820528eb198eed7eff6747405691afe7738dd287f05e9`
- 当前`result_ref`：**无**。readiness、最终覆盖及异常须在完成后通过`precheck.read`取得，不能由旧Result或隔离测试替代。现有status还保留184个video_frame_decode_failed和1个video_probe_failed，未将其清零。

证据在 `/tmp/mediasense-0.10.0-live-switch-260911/`：`installation-verification.json`、`doctor-actual-launcher.json`、`mcp-initialize.json`、`mcp-tools.json`、`dataset-open-after.json`、`status-new-host-before-resume.json`、`resume-without-decision.json`、`status-prepared.json`、`status-final.json`、`recovery-preparation-summary.json`、`retired-hosts.json`，以及升级前依赖/Skill/lock和SQLite备份。包、原始响应及媒体不入Git。fixture verifier的清单SHA-256全部通过，但操作目录已有额外业务文件，总量3,188,676,923字节超过原2,000,000,000字节上限；不能宣称整个操作目录仍是原封不动的限量fixture，也未为通过校验删除这些文件。

#### 在操作项目新建 Agent 会话后的续接指令

当前主Agent没有MediaSense MCP工具，已运行的业务Agent仍加载旧会话资源；Codex当前公开命令面未提供可用的MCP会话内reload。不要终止当前主Agent或用一次独立Host检查冒充业务会话切换。请在 **`/Users/chengyanru/Downloads/ai-album-hk-representative-v1`** 新建正常Codex会话，加载本项目0.10.x四个Skill及原MCP配置，然后继续以下任务：

1. 遵守本项目Skill及MediaSense当前合约，确认新会话实际发现七个MediaSense工具、Host为0.10.0且合约匹配。安装、原数据范围和恢复已有授权，不另开安装或数据范围确认。
2. 使用`mediasense.dataset.open`打开精确 `source_root=/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831` 和 `workspace=/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e`，核对 `dataset_ref=dataset:6581e19d4fe94e26a10e2f5ca1b34c9b`。
3. 用公开status读取 **`run_ref=precheck-run:ea216eded808430ead13f6afef40420d`**，include diagnostics/accounting。不得start新Run。它当前已经完成不带decision的resume，停在paused恢复确认；核对上列披露身份、仅补12地点/23组件、本批86/历史229/未知费用、累计486/剩余400和唯一已选范围`260501-HK美食之旅`。若状态已变化，以新的公开事实为准，不重放陈旧确认。
4. 在范围、服务商和网络接收方仍匹配既有授权时，调用公开`mediasense.precheck.run`，平铺参数`action=resume`、上述dataset_ref/run_ref、`decision=proceed`，由MCP客户端显示完整披露并取得正常Human elicitation。不要传authority、自动接受回调、编辑数据库或伪造确认。此最终可信控件是公开契约的执行机制，不是再次征求已经授权的安装/业务范围。若必须新增代理、变更接收方或扩大预算，先准备具体方案并取得相应授权。
5. 沿原Run观察到真实终态；若网络仍不可达或再次blocked，保留成功组件、累计尝试和未知费用，明确具体原因及条件，不能无变化地循环resume。完成后用`mediasense.precheck.read`读取Tool给出的精确result_ref，核对readiness、覆盖、异常、历史/本次请求及未知费用。真实新增请求按完成后本批计数减86报告，合成+23不是承诺。将实际结果继续补在本台账；不扩大Apply或模型认证。

## Current MediaSense implementation status

This table is deliberately narrower than the inventory above. A row marked `implemented` proves only the stated unit, not the whole legacy capability family or a complete PreCheck stage.

| Capability unit | Implementation status | Migration judgment | Current evidence | Remaining gate |
| --- | --- | --- | --- | --- |
| Recursive path discovery and extension classification | `implemented` | `preserved` | `src/mediasense/precheck/discovery.py`; fast discovery tests; verified Hong Kong package with 2,140 signed paths plus two explicit local `.DS_Store` items; a generated 100,000-path stream completed in 6.389 s with 6,649,587 bytes peak Python-traced memory on the development host | Physical-directory and network-volume throughput remain environment-specific production measurements |
| Local discovery failure and symlink accounting | `implemented` | `intentionally_changed` | `tests/test_discovery.py` covers failed `scandir`, disappearing entries, loops, and boundary escape; accounting tests preserve both spellings and report both sides of an NFC collision without merging Source Items | Removable-volume and non-POSIX fault coverage remain platform-specific |
| `.albumignore` observation and path accounting | `implemented` | `intentionally_changed` | Marker and descendants remain visible with `albumignore_*_observed` basis; Hong Kong RAW/DNG and GPX paths remain accounted | Compression-scope effect is `deferred`; marker presence alone is not exclusion authorization |
| `.albumignore`-driven compression exclusion | `deferred` | `intentionally_changed` | c90 marker behavior is characterized, while the current MediaSense implementation deliberately treats markers as visible observations and does not parse them or alter producer/compression scope | Define an explicit Run policy, retained basis, and coverage behavior before enabling exclusion |
| PreCheck source-scope review and admission | `implemented` | `intentionally_changed` | `tests/test_precheck_scope_review.py` covers bounded factual trees, media-bearing `.similarity_cache`, legal hidden media, ordinary dotfiles, nested historical output, exact selection, stale-tree refusal, reuse, and unattended waiting | AI Album recursively scanned subject to `.albumignore`; MediaSense instead pauses before expensive Work, leaves semantic interpretation to the Agent/Human, and accounts excluded items without treating names or hiddenness as authority |
| RAW/DNG, GPX, sidecar, and AppleDouble discovery roles | `implemented` | `intentionally_changed` | Characterization tests and Hong Kong local-fixture assertions; metadata/sidecar interpretation and explicit GPX matching are implemented as dependency-complete Work | Wider RAW decoder/metadata coverage and automatic GPX adoption-benefit policy remain |
| Same-stem, temporal-chain, and bundle representative candidates | `implemented` | `intentionally_changed` | AI Album c90 unions same-directory stems, AppleDouble names and M01/M02 families, then transitively chains adjacent timestamps and selects JPG/JPEG, HEIC, PNG, MOV, MP4 in that order. `BundleCandidateProducer` preserves those candidate capabilities as dependency-complete Work, uses deterministic ordering, retains every member, reports total capture span and boundary paths, and marks a chain whose total span exceeds the per-edge gap. Missing time remains separate rather than becoming epoch zero. To prevent one transitive chain from creating unbounded Work, MediaSense splits it at a versioned member ceiling and records that limitation. Tests prove cross-run reuse and that a far source addition leaves an unchanged candidate reusable. | Compare representative stability, long-chain user-correction burden, and the bounded split on reviewed production collections |
| Resumable batched Working Run accounting and feedback | `implemented` | `intentionally_changed` | AI Album exposed transient terminal progress bars and logs but no durable per-item ledger or Run-level complete/partial state. MediaSense status now keeps Source Item accounting separate from a durable activity projection: coarse phase, computed/reused/failed/remaining/total Work, last effective progress, bounded error summaries, responsive-but-quiet versus suspected-stalled liveness, and resumable worker interruption. Synthetic SQLite/checkpoint, fake-clock, fault-injection, pause/resume, localized-failure, and publication tests cover the contract without replaying real media; generated discovery covers 100,000 paths. | Long-running real-media cancellation, hard process-kill, sleep/wake, and database/process crash soak tests remain. |
| Run-scoped source attachment and safe remount | `implemented` | `intentionally_changed` | AI Album c90 `argparser.py` expands input paths and `cache_manager.py` derives path/hash cache locations but has no durable run attachment or remount identity check. `source_attachment.py` and accounting tests bind locator plus observed root/volume identity to each Working Run; compatible relocation is audited, identity mismatch blocks, and operator-confirmed rebinding starts a new reuse domain. The installed macOS path now prefers a stable volume UUID and root inode, with an explicit session-local fallback. | Validate physical removable-volume reconnect and cross-machine behavior on the supported filesystem matrix; non-Darwin stable volume identity remains future work. |
| Filesystem capability observation | `implemented` | `not_comparable` | No equivalent source/workspace capability record was found in AI Album c90. Attachment tests persist observed mount writability, process writability, verified SQLite locking, workspace replace behavior, same/cross/unknown filesystem status, case behavior, and symlink policy without probing writes on the source. NFC-equivalent paths remain separate authoritative spellings and produce explicit non-blocking accounting issues. | Read-only mount enforcement plus removable-volume and non-POSIX certification remain platform-specific |
| Normal-path removal detection | `implemented` | `intentionally_changed` | Run-owned removal facts retain the previous revision before the current source view becomes absent; tests cover deletion, rename, non-repetition, deletion beside an unrelated unreadable subtree, and transitive invalidation of path-dependent Work. Bundle and compression group Work now declare exact member Source revisions plus direct upstream Work, so member change/removal invalidates only affected candidates. | Production-scale candidate membership and bridge-addition profiles remain |
| Fast source-change candidate fingerprint | `implemented` | `preserved` | AI Album commit `d10f42a` introduced a constant-I/O partial MD5 over the first, middle, and final 4 KiB and c90 retained it through `jinnang.MyPath.hash`. MediaSense preserves that bounded-read geometry for large files and full reads for files up to 12 KiB; characterization tests cover sampled and unsampled mutations. Internal hardening intentionally uses SHA-256 with size/offset domain separation, pre/post stat checks, and no path-only process cache. The fingerprint remains candidate-only. A generated sparse 1.5 TB candidate completed in 0.003 s on the development host. | Real-storage latency and exact Artifact validity cost remain separate measurements |
| PreCheck source-content validity | `implemented` | `intentionally_changed` | AI Album's bounded fingerprint is retained and hardened for ordinary-change detection. MediaSense Work binds source revision plus the versioned bounded fingerprint and verifies pre/post stat identity, avoiding repeated whole-file SHA-256 reads. This deliberately does not detect adversarial same-size, same-time changes outside sampled ranges. | Measure real-storage latency and observe false-reuse risk under the accepted non-adversarial threat model |
| Result-local source verification handoff | `implemented` | `intentionally_changed` | Eligible Source Items expose the actual replaceable verification profile, including its limitations, plus a locator-owned `source_root_ref` and root-relative path. Seal revalidates that profile without upgrading it to an exact-byte claim. Missing or limited PreCheck verification does not make an otherwise eligible item unselectable. | New verification profiles require profile-aware seal and consumer tests |
| Apply-side selected-source revalidation | `implemented` | `not_comparable` | Apply resolves every selected move through exact `result_ref + source_item_ref`, safely binds the current root, establishes a fresh full SHA-256 and size proof during preparation even when PreCheck supplied only limited or no verification, then rechecks root, destination, source object, bytes, and target absence at the effect boundary. Malformed exact evidence and exact mismatches fail closed. | Broader platform volume identity remains certification work |
| Authorized `move_originals`, recovery, and Receipt | `implemented` | `intentionally_changed` | The active Apply Run/Read Tools bind trusted Human confirmation to exact prepared content, use non-overwriting moves, durable intent and fact-based recovery, preserve partial truth, publish one immutable Receipt, and support whole-Run rewind. Same-filesystem Darwin APFS and cross-filesystem Darwin APFS-to-APFS have controlled evidence. | Real removable-media throughput, Linux filesystem certification, and broader filesystem pairs remain |
| User-facing Apply Skill | `implemented` | `not_comparable` | `mediasense-apply` explains prepared impact and Tool-owned states, obtains exact Human confirmation through trusted context, handles blockers/drift/partial recovery, reads Receipts, and guides newly authorized rewind without owning state or effects. Fixture workflows cover forward, blocker, drift, recovery, Receipt, and rewind paths. | End-user host/UI usability study remains |
| Original-file copy profile | `deferred` | `not_comparable` | c90 README said “Copy original,” but c90 code routes `original` to `safe_move`; `copy_with_meta` serves thumbnails/tests, may overwrite, and tolerates metadata failure. MediaSense does not invent duplicate-retention, authorization, or rewind semantics and does not place thumbnail output in Apply. | Requires a new Human-reviewed product purpose and lifecycle before implementation |
| Persistent relative symbolic-link profile | `deferred` | `intentionally_changed` | c90 creates relative symlinks as a preview before moving originals and reports failures only by printing. MediaSense preserves preview in Plan without filesystem effects and refuses to reinterpret link as a hard link. | Requires accepted dangling-link, source-volume rebinding, coexistence, authorization, and rewind policy |
| Semantic Work identity and direct dependency records | `implemented` | `intentionally_changed` | AI Album c90 `cache_manager.py` reuses path/hash-addressed files and eight cache flags, but has no dependency-complete Work identity. Work tests cover canonical descriptors, narrow producer identity, source revision and exact-content inputs, exact upstream Work references, cross-run reuse, source-driven transitive invalidation, and Artifact-integrity invalidation without an application-wide version key. Bundle and adaptive compression groups declare their exact Source membership and evidence Work rather than a Dataset-wide snapshot. | Measure descriptor/dependency-table cost for very large groups and introduce a semantically equivalent compact representation only if required |
| Durable Work attempts, leases, retry, and checkpoints | `implemented` | `intentionally_changed` | AI Album c90 `clustering_engine.py`, `cluster/linear.py`, and metadata batching use fixed semaphores/batches and eagerly materialized coroutine lists but retain no durable attempt or lease. Work tests cover atomic cross-run claiming, restart recovery, stale-token refusal, renewal, bounded retry/backoff, terminal blocking, retained attempt history, transitive invalidation, and cooperative cancellation before new external Work | Process/GPU crash soak tests and production media throughput remain |
| Durable Run control and confirmation breakpoint | `implemented` | `not_comparable` | AI Album c90 has no equivalent durable operator authority. `PrecheckRunTool` implements idempotent `start`, `status`, `pause`, `resume`, and `cancel`; exact frozen optional-work counts cause an automatic pause; matching decisions are fingerprint-bound; internal publication marks validation failure terminal, workspace-write failure resumable, and completion only after the sealed Result re-verifies. Public `seal` is rejected. | End-user host integration and long-duration restart/cancellation exercises remain |
| Internal configured Run orchestration | `implemented` | `intentionally_changed` | AI Album c90 groups before expensive media analysis but eagerly creates coroutine lists and controls each stage with fixed parallelism. MediaSense now preserves the useful cost funnel explicitly: all eligible media receive `index-v1` metadata, bundle candidates are built through a disk-backed ordering path, and a deterministic bounded representative/boundary frontier receives initial rendition/video/model Work. A generated production-path gate populates one million Source Items and index-metadata Work rows, then bounds planner RSS and pending-call cancellation; immutable Result payloads remain necessary `O(N)` authority. The internal directed-evidence seam is not exposed by the public Run contract. | Public directed-evidence authorization/Result/failure semantics, host worker lifecycle integration, long process/GPU fault soak, and real storage/codec/model throughput remain certification work |
| Selective manual rebuild and bounded resource admission | `implemented` | `intentionally_changed` | AI Album c90 exposes eight cache flags, clears related cache families procedurally, uses stage parallelism 4/1/1/4, frame-embedding batches of 8, configurable ExifTool batches, global model locks, and a coarse 12 GB startup gate. MediaSense rebuild selectors invalidate only matched Work and real dependents. Its Run-start resolver combines CPU, Darwin `vm_stat` available-memory evidence, verified physical-solid-state/remote/unknown source classification, enabled providers, and optional ceiling-only overrides; freezes the result; keeps unknown or remote source I/O at one lane; bounds pending work; and separates process, decoder, encoder, model, source-I/O, workspace-I/O, and network admission. Same-filesystem status remains a file-safety fact and does not imply fast storage. | Physical storage throughput and GPU-memory calibration remain production measurements |
| Immutable Artifact cache and publication | `implemented` | `intentionally_changed` | Artifact tests cover workspace-local unpublished files, copying producer output onto a publication-owned inode, complete-byte digest/size validation before transactional Work binding, atomic content-addressed publication, crash orphans, missing/corrupt detection, Work invalidation, restoration, cross-run reuse, and ENOSPC without partial success | Broader filesystem and concurrent-publication soak measurements remain |
| Workspace retention, quarantine, and repair | `implemented` | `intentionally_changed` | AI Album c90 repairs cache path collisions but has no Result-reachability retention authority. MediaSense derives reachability from existing sealed Result and active-Run references, pins their Work, removes only unreferenced invalidated Work/Artifact pairs, quarantines expired unpublished/orphan bytes, and restores a missing Artifact only from integrity-matching quarantined bytes. | Policy tuning for retention windows and concurrent maintenance remains operational follow-up |
| Ordinary and high-resolution still-image rendition | `implemented` | `intentionally_changed` | Pillow producer and c90 characterization tests preserve EXIF orientation, bounded aspect-preserving resize, no upscale, RGB JPEG output, source immutability, local terminal decode failure, exact source dependency, and immutable Artifact publication. Stable ordinary (640 px / legacy 360p role) and high-resolution (1920 px / legacy 1080p role) profiles create independently reusable Work; the ordinary rendition enters the default frontier and expands to the higher-resolution Evidence. Unlike c90's `keep_original_ratio=False` high-resolution path, both profiles preserve aspect ratio rather than risk stretching. The verified Hong Kong package now supplies a real representative JPEG test without modifying package bytes. | HEIF/RAW coverage, decoder matrix, color/HDR policy, throughput, and visual-fidelity comparison remain |
| Local video probe, sampled frames, key-frame candidate, and contact sheet | `implemented` | `intentionally_changed` | AI Album c90 samples at roughly ten-second intervals with a twenty-frame cap, batches frame embeddings by eight, and has no cross-stage process budget. MediaSense keeps each probe/frame/sheet as dependency-complete Work, initially runs video only for demanded bundle evidence, bounds concurrent FFmpeg processes through process/decoder/encoder lanes, and writes the resolved FFmpeg thread count into Work identity and command arguments. | Wider codec/container/orientation/HDR matrix, decode throughput, visual-quality/key-frame comparison, and production fixture coverage remain |
| Local image and video-frame embeddings | `implemented` | `intentionally_changed` | AI Album c90 lazily loads singleton ChineseCLIP under a global model lock and batches frame embeddings by eight. MediaSense keeps exact input Work, pinned model/runtime identity, dimensions, dtype, and normalization as semantic dependencies, and now gives compatible adapters a bounded true-batch interface while retaining one Work/Artifact/failure boundary per input. Large-group representative comparison uses an exact small-group path and a recorded bounded approximation beyond the configured comparison budget. | Run a pinned local ChineseCLIP model against representative media; compare vector shape, neighbor quality, CPU/GPU throughput, memory, and frame-key selection before claiming production parity |
| Pinned local model quality and throughput certification | `characterized_only` | `not_comparable` | c90 model identities and retained vectors provide a historical baseline; MediaSense adapters, semantic dependencies, fake-model orchestration, and failure behavior are implemented, but no reviewed MediaSense quality/throughput result from the pinned real models is recorded yet | Required before production-parity claims, not before three-stage contract integration |
| Local content-sensitivity installed capability | `implemented` | `regression` (fixed in M2); evidence/routing separation remains `intentionally_changed` | `SensitivityProducer`, NudeNet and NSFW adapters, per-input Work and Result projections exist. `tests/test_sensitivity.py` manually injects detectors and proves component/result behavior. That was the b52535a gap. M2 adds the accepted local configuration, production composition and installed MCP execution of both detectors; see the current scope and verification evidence above. | Installed configuration, both detectors, per-input public observations and reuse are verified; model quality, false positives/negatives and throughput remain separately uncertified |
| Minimal local metadata, time, and GPS observations | `implemented` | `intentionally_changed` | AI Album c90 uses ExifTool `-G -n -api largefilesupport=1`, batches timestamp extraction (configured 200), then opens an `ExifToolHelper` context for each later metadata call over representatives. MediaSense defines the versioned `index-v1` profile, sends bounded multi-item commands through one Run-local stay-open process, preserves one Work/result per source, subdivides unattributed failures, and keeps source/sidecar provenance. For 4,009 healthy candidates at batch 200 this is 21 execute batches and one process start rather than roughly 4,009 per-item extraction starts; retries after malformed batches are data-dependent. A short installed-ExifTool test verifies reuse/restart/shutdown without a large fixture. | This narrow row does not certify photographic-field completeness; missing lens/exposure/ISO/source-size/device fields are recorded below. Wider camera/RAW/video matrix and physical-storage throughput remain |
| GPX adoption and time-based coordinate candidates | `implemented` | `intentionally_changed` | AI Album c90 parses time-bearing track segments, sorts points, applies a maximum time difference, and intends nearest-point or linear interpolation; its history fixed path loading, fatal missing inputs, matching limits, and diagnostics. `GPXMatchProducer` preserves the useful behavior with exact dependencies on every explicitly adopted GPX Source Item and the upstream metadata Work, distinguishes embedded-GPS `not_applicable`, missing capture-time `not_checked`, no match, full failure, and partial input failure, and projects Result-local provenance for all adopted tracks. It intentionally fixes c90's right-index interpolation defect and localizes one malformed GPX instead of aborting all tracks. | Automatic adoption/benefit policy, production HK track comparison, clock-offset candidates, multi-media batching, and throughput remain |
| Minimal Evidence frontier and immutable Result read path | `implemented` | `intentionally_changed` | Result tests cover exact `accounts_for` for the enumerated boundary, partial coverage when discovery leaves an unenumerated region, entry Evidence, all five relationship meanings, many-to-one and one-to-many boundaries, normal/exception navigation closure, unresolved readiness blocking, atomic seal publication, exact `result_ref`, pagination, current-Run Artifact provenance and final pin revalidation, read-only integrity checks, and the earlier release Read schema conformance. Seal rechecks inline supporting Work as well as visible Artifact Work; Run-level tests cover automatic publication, validation refusal, ENOSPC blocking, retry adoption after a crash before registration, reuse after a crash before Run completion, and absence of a public seal action. Adaptive Results expose representative, boundary, outlier and conflict roles using existing observations and relations. | This earlier-path evidence alone does not prove the 2026-09-09 review.items/own-attributes delivery; the accepted M2 evidence above closes that implementation boundary. Large-page latency and additional filesystem-specific fault profiles remain |
| Adaptive local compression and multiple Results | `implemented` | `intentionally_changed` | AI Album c90 applies a fixed date → 3,000 m/500 m location → cosine-content hierarchy with distance `0.311`, minimum weights and opaque final naming. MediaSense preserves local temporal, WGS84 spatial, cosine-content and c90 top-half representative signals but treats them as replaceable candidate methods. A declared target ranks adjacent boundaries, retains limitations and axis conflicts, emits exact-member group Work, and projects challengeable `represents`/`expands_to` paths without naming or final organization judgment. Lower-level Work is reused across profiles. The public-Run generated acceptance seals three immutable Results with entry frontiers `500 → 3 → 200` in 62.00 s on the development host, reuses the same 500 low-level rendition Work records and Artifact references, and leaves source bytes unchanged. Result comparison reports source-boundary, entry-count, compression-ratio, shared-Artifact and identical-group metrics from sealed projections without exposing Work. | Compare compression quality, hidden variation, group balance, reopen/user-correction burden and Hong Kong legacy groups; complete production-scale profiling |
| Coordinate reverse geocoding and nearby-place lookup | `implemented` | `intentionally_changed` | AI Album c90 establishes WGS84/GCJ02 conversion, AMap/Google lookup, same-asset and temporal pre-compression, fallback, and rate limiting. MediaSense preserves those useful capabilities through the public stage-neutral `mediasense.geo.query` Tool and a PreCheck-owned media-aware acquisition policy. Bundle candidates seed conservative stationary units; moving, temporally conflicting, or datum-conflicting members split; exact coordinate deduplication follows. Every located Source Item receives a Result outcome even when many reuse one observation. Stable Work identity excludes batch position and membership, and an explicit compatibility path reuses matching 0.7.1 successes. On the paused Hong Kong Run, read-only evaluation yields 225 queries for 1,838 located Source Items instead of 1,611 exact-coordinate queries; 98 of those queries reuse compatible historical observations and 127 remain pending, with zero new Provider attempts. | A user-confirmed live-provider smoke, Provider policy/terms review, boundary-quality sampling around the current local thresholds, and real quota/error observations remain environment-specific |
| Live reverse-geocode deployment certification | `characterized_only` | `not_comparable` | c90 source/tests and the current fake-provider suite characterize routing, fallback, counts, authorization, and failure behavior without issuing a live request in this acceptance run | Confirm provider terms, quotas, retention, keys, regional coverage, route quality, and observed billing in an explicitly authorized production check |

### 2026-09-08 temporal, visual-entry and evaluation correction

Evidence and exact limitations: [HK audit corrections](../eval-260908-1329-precheck-corrections.md).

| Capability / difference | Classification | Delivered evidence and operating qualities |
| --- | --- | --- |
| Naive QuickTime integer timestamp interpreted as local time | `regression` (fixed) | Actual c90 standard conversion treated it as UTC; typed field interpretation restores that behavior. 281 fixture video timestamps change, 1,851 others do not. No extra remote cost; interpretation and rejected fields now remain inspectable. |
| Local camera times, offsets, sidecars, single-candidate DJI/Canon photo examples | `preserved` within the tested field cases | Local EXIF semantics and explicit offsets are retained without copying a mandatory vendor rule table. Tests distinguish camera fields from container fields. This does not establish conditional vendor override or user-configuration parity; the 2026-09-11 manufacturer-system audit above records those regressions. |
| Generic naive-time handling and timestamp provenance | `intentionally_changed` | Avoid c90's blanket UTC behavior for ordinary EXIF. Preserve raw candidates, uncertainty and filename/mtime fallback qualifications. Versioned metadata Work invalidates dependent GPX/bundle/compression work; old Results remain immutable. |
| Filename recovery after absent/invalid capture metadata | `regression` (fixed) | TimestampService had a basename fallback; migrated selection could instead select copied mtime. Generic timestamp patterns now precede filesystem fallback without overriding valid camera fields. |
| Local embedding reachable through installed Host | `regression` (fixed) | Internal adapter existed but runtime configuration/composition and optional dependencies prevented ordinary use. The real MCP path now executes and reuses a pinned local profile. No AI Album runtime dependency or automatic model download. |
| Optional models, content-driven frontier and unavailable representative fallback | `intentionally_changed` | Local cost remains explicit; no model is universally enabled. 167→117 candidates with 366 real encodings, and complete reuse later. Failed preferred representatives can use verified prepared members; failures remain visible. |
| Historical 168 representatives versus new frontier / total cost | `not_comparable` | Different boundaries and no new independent Plan quality/cost experiment. CPU work, hidden members and residual investigation are disclosed, not counted as proven savings. |
| Immutable accounting and independent evaluation boundary | `intentionally_changed` | Keep excluded source identity; remove automatic descendant samples and stage exact allowed inputs outside fixture. Clean judging context is separately required. No original media movement/deletion. |

### 2026-09-11 本机 EXIF 与抽帧性能对照

用户要求在 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`
实测。完整[配方、报告与小型统计](../../../eval/sessions/260911-1841-hk-preprocess-performance/report.md)
固定 MediaSense `b3aa696` 与 AI Album `c90aa8f`，使用同一 M5 Pro / 48 GiB 本机。
主范围是 2,134 个 manifest 媒体，不把同级旧缓存/分类图算作原媒体；指定副本逐项 SHA-256
相同，主素材目录全部 2,142 个文件测试前后字节、大小、mtime 与路径不变。包 verifier
的清单 SHA 全通过，但操作目录因额外副本超过原 2 GB 限制而整体返回 1；未篡改门槛。

这些实测补充并限制此前“批量、复用机制已接通”的结论，不将机制测试扩展为性能保留。

| 能力／运行品质 | 本次迁移判断 | 实测与边界 |
| --- | --- | --- |
| 同字段 EXIF 原始值 | `preserved`，仅所测字段 | 2,133 项、18 字段、六次返回逐对象相同；不认证归一化时间、厂商规则或所有摄影字段 |
| 批量 EXIF 吞吐 | `regression`，本机同工作量 | 三轮中位数旧 1.363 s、新 10.787 s，新耗时 7.92×。旧 11 批并发/11 进程，新单 stay-open 顺序执行。旧路线串行控制为 11.548 s，支持批间并发是主要差距；少启动进程不是吞吐保留证据 |
| 同目标帧提取路线 | `regression`，所测适配与依赖 | 282 个可读视频、843 个实际目标帧、相同输出尺寸上限，三轮中位数旧 31.800 s、新 50.593 s（1.59×）。全部成功、尺寸相同、像素核对支持帧对应。新每轮启动843个FFmpeg；旧OpenCV进程内定位。未把库/线程/编码差异当作单一算法变量 |
| 默认采样和帧覆盖 | 上限／规格 `intentionally_changed`；末帧位置处理为 `regression` | 同283视频，旧实际 get_frames/cache 首次49.551 s、1,736帧；当前真实producer四线程23.748 s、370帧，同时285次抽帧失败、另1个已知坏视频probe失败。282次请求duration终点，另3次虽在容器时长内但晚于最后一帧PTS。总时间短不能证明同等覆盖更快 |
| metadata 工作状态与来源证明成本 | 新保障与完整旧流水线 `not_comparable`；当前热点已量化 | 2,134项实际producer首次82.747 s，其中ExifTool18.328 s，其余64.420 s含Python/来源证明/Work/SQLite；后继Run全部复用仍14.961 s，仅一次版本查询。不能未经profiling把其余时间全归于数据库写入 |
| 成功缓存复用与失败保留 | 复用能力 `preserved`；读取责任 `intentionally_changed` | 旧282个有效视频复用1,736张JPEG需6.979 s；当前370帧复用并保留285个终结失败需7.666 s，仅ffprobe/FFmpeg版本查询，无新帧提取。旧返回已加载像素、新返回验证后的Artifact/Work，不作同单位缓存胜负结论 |

本次重新选择得到167个主素材候选、99个图像与182个视频来源。把全量逐视频结果对应到
该选择集合，准确复现此前 **267成功帧 / 184抽帧失败 / 1坏视频probe失败**。这些失败是
操作次数，不是185个坏视频，也不是模型失败；旧97个视频代表与当前182个视频来源不能
直接视为相同完整流水线。来源、全部默认输出完整解码和受控帧对应均通过复核。

测试没有模型/Geo调用，没有修改产品实现或业务Dataset/Result；原始日志、数据库和
生成媒体留在ignored outputs。内核三轮、默认链路与producer各一次首次/复用；系统缓存
未清空，也未独占机器。代理素材、仅3个0.30–2.74秒4K/8K原样短片，均不能认证原始
879 GiB视频、长GOP、外置盘或完整RAW吞吐。后续先修有效帧位置与覆盖，再恢复资源上限内
的EXIF批间并发并定位非ExifTool热点，沿同配方复测。更广质量/吞吐门槛仍开放。

用户随后要求先讨论基础方案、再固定具体计划及逐步验收，之后才开发；又明确委托
Agent自行判断并继续实施。[OpenSpec变更](../../../openspec/changes/restore-precheck-throughput-and-coverage/proposal.md)
已在产品改动前固定具体任务与门槛。上述数字保留为修复前证据，后续验收如下。

### 2026-09-11 吞吐与有效帧修复验收

状态：本次源码与隔离安装边界 `implemented`。证据见[修复报告和配方](../../../eval/sessions/260911-2128-precheck-throughput-recovery/report.md)、[固定验收](../../../openspec/changes/restore-precheck-throughput-and-coverage/acceptance.md)及[小型指标](../../../eval/sessions/260911-2128-precheck-throughput-recovery/metrics/combined.json)。当前 Run/Read 合约拥有产品含义；本段只认证声明的工作负载与交付边界。

| 能力／运行品质 | 本次处置 | 完成证据与限制 |
| --- | --- | --- |
| metadata 字段及吞吐 | 值 `preserved`；已测串行化回归修复，通道方法 `intentionally_changed` | 2,133项同18字段，新四通道中位3.450 s、旧同四并发参考3.477 s，逐对象相同；原11并发1.363 s保留，不混用资源口径 |
| 正式 metadata producer 与复用 | 保障 `not_comparable` 于旧缓存；MediaSense 内部开销修复 | 全2,134项观察值不变，最终首次82.747→15.708 s、复用14.961→3.992 s，复用零字段提取。256项诊断实际连接3,097→27、提交2,305→1,281；每项提交/错误仍保留，长批仍续租 |
| 同目标视频帧提取 | 已测回归修复；decoder 可替换 | 同843帧三轮中位28.217 s，相比旧OpenCV31.800 s、原MediaSense50.593 s；位置、尺寸和像素对应通过。CPU codec线程受控，按视频复用容器；未认证所有长码流 |
| 默认视频有效准备与位置交付 | 采样深度 `intentionally_changed`；285次错误采样修复 | 283视频取得843个不同PTS帧、0采样器失败，1已知坏probe保留；完整阶段含282联系表22.478 s，复用6.928 s且0decode。当前真实选择的182视频范围由267帧/184失败恢复到540帧/0失败，另1坏probe |
| 已封存结果、局部失效与安装 | 复用能力 `preserved`，强来源/不可变交付 `not_comparable` 于旧体系 | 请求时间保留；实际PTS可选且basis保留真实producer，联系表一致。旧Result字节不变，decoder变化不重做无关Work；实际wheel Host公开Run/Read取得5帧/2表，后继Run无新提取，Source与旧Result不变 |

1,109项默认测试经全量及失败项修复复核完成；4项回环HTTP测试使用本机监听权限，另修复一份遗漏的Skill schema副本。2,142个源文件的路径/字节/大小/mtime保持原样；模型/Geo调用0。wheel SHA-256 `b4a16a8f10513896f8f24d3d39529f3fa5237a6a905f687859bbf632f9ed731f`，包内源码与合同/Skill副本一致。

声明限于本机代理fixture、三个原样短片和隔离安装；日常全局Host未切换。默认新JPEG不放大低清代理，完整视频时长含联系表；其总时长不冒充与旧默认同规格的胜负。扫描/分组在报告中单列。内存准入为估算，时限/取消为协作式；长GOP、全量RAW、物理/远程存储、模型质量及厂商规则配置的独立缺口仍按各自台账判断。

### 2026-09 PreCheck scale correction

The following records the earlier `scale-precheck-execution` mechanism and its
then-certified scope. The single ExifTool lane and per-frame FFmpeg description
are superseded by the scoped 2026-09-11 implementation/acceptance above; prior
mechanism evidence is retained without extending its original performance claim.

- `preserved`: AI Album's useful funnel—batch enough metadata to group first,
  then create thumbnails, video evidence, embeddings, and sensitivity evidence
  for representatives—is restored. Per-item caching and local model reuse remain.
- `intentionally_changed`: MediaSense uses one Run-local stay-open ExifTool,
  dependency-complete Work, item-local failure subdivision, bounded model
  batches, exact Apply-time byte proof, and host-resolved resource lanes instead
  of AI Album's cache flags, per-call helper lifetime, global model locks, and
  fixed 12 GB admission gate.
- `regression`: the earlier MediaSense orchestrator ran rendition, video,
  embedding, and sensitivity stages for all media before bundling, launched
  metadata extraction per item, repeatedly required full source hashes, and
  defaulted to two workers with one process/codec lane. Those behaviors explain
  why it could be much slower than AI Album despite the smaller candidate count;
  they are removed by `scale-precheck-execution`.
- `not_comparable`: durable Run/Work leases, dependency-scoped invalidation,
  immutable Result/Artifact validation, exact Apply revalidation, and explicit
  source/workspace safety have no equivalent guarantee in AI Album.

For 4,009 healthy metadata subjects and the default batch ceiling of 200, the
new path issues 21 ExifTool execute requests through one stay-open child
process. Recursive subdivision adds calls only for failing batches. Exact
decode/encode and video subprocess counts cannot be inferred without the media
kind and bundle distribution: each demanded still creates one ordinary
rendition, plus one high-resolution rendition when a local model is enabled;
each demanded video creates one ffprobe process and at most three ffmpeg frame
processes under the current default. Undemanded bundle members remain present
in Result accounting but create none of those visual calls.

Increasing `max_workers` from two to eight alone would not have fixed the old
shape: it would retain per-item process startup, all-item decode/model demand,
repeated source reads, eager task construction, and quadratic representative
comparison. The current design reduces and batches work first, then uses
resolved concurrency only within explicit CPU, memory, process, codec, model,
and I/O ceilings.

### 2026-09 Geo coverage and compression correction

- `preserved`: AI Album's same-stem/RAW/JPG/sidecar associations, temporal
  shooting-chain evidence, representative selection, Provider adapters, datum
  conversion, rate limiting, and the ability to reuse one lookup are retained.
- `intentionally_changed`: a legacy bundle is only a candidate Geo scope. Local
  coordinate/time consistency can split movement or conflict; one deterministic
  member coordinate is queried; the observation is then projected to every
  covered Source Item. The shared Geo Tool, exact authorization, durable effect
  journal, and hard request ceiling have no legacy equivalent.
- `regression`: the representative-only MediaSense correction omitted per-item
  outcomes, while the subsequent all-coordinate correction bypassed bundle
  compression and made Work identity depend on prior batch position. Both are
  repaired by separating coverage, acquisition units, and projection.
- `regression`: the first shared-Tool integration requested only
  `reverse_geocode`, so AMap used `extensions=base`, Google never called its
  nearby endpoint, and PreCheck projected empty POI evidence. Bounded
  `resolve_place` repairs this while retaining the Tool's progressive default for
  Plan; AMap again supplies address and POI in one request and Google accounts for
  its two requests separately.
- `not_comparable`: adaptive visual compression groups are not classified as a
  Geo-equivalence mechanism because their purpose is bounded visual review. Plan's
  separately authorized, targeted Geo investigation also has no AI Album stage
  equivalent.

## Acceptance dimensions

Every migrated capability must be evaluated on the dimensions that can change the product judgment:

- Functional coverage and correctness.
- Local compute, I/O, memory, cache growth, and wall time.
- Remote requests, image inputs, provider-reported tokens, and monetary cost.
- Reuse after restart and after a localized input/profile change.
- User knowledge and confirmation burden.
- Visibility of uncertainty, omissions, and failure.
- Source integrity, collision behavior, recoverability, and auditability.

An implementation is not accepted merely because it reproduces one legacy directory tree. Conversely, a changed directory tree is not a regression when the change follows an approved plan and fixes an evidenced legacy failure.

## Stage development gate

Before implementing a stage's production Tool or Skill, preserve these links:

```text
human-reviewed handoff example
  + runtime/interruption/failure semantics
  -> minimal formal contract
  -> Tool implementation and tests
  -> Skill guidance and Agent evaluation
  -> ledger comparison and acceptance judgment
```

The three stage tracks may develop concurrently using manually approved fixtures. Downstream work must not depend on unversioned upstream internal databases or caches.

## Open work that can change priorities

- Quantify bundle purity and missed grouping on high-weight bundles.
- Compare representative strategies at 32, 64, 128, and 256-image planning budgets.
- Measure whether contact sheets reduce API turns, visual tokens, user effort, or only request overhead.
- Measure dependency-descriptor and invalidation cost for very large population-wide candidate groups.
- Define plan completeness, freeze, amendment, and approval semantics through a manual example.
- Define apply transaction, recovery, same-filesystem move, and cross-filesystem refusal through a manual example and generated fault fixtures.

These are decision-bearing unknowns. Do not select final schemas or frameworks until the relevant experiment or example distinguishes the alternatives.

## Existing components to evaluate before building

These are implementation candidates and capability baselines, not permanent architecture commitments:

- ExifTool already provides mature batch image/video metadata extraction. MediaSense's distinctive responsibility is the provenance, confidence, error, and incremental-state contract around it.
- FFmpeg and ffprobe already provide video decoding, probing, sampling, and scene signals. MediaSense should not build a general video decoder.
- ImageMagick montage can produce labeled contact sheets. Its effect on actual provider-reported visual tokens must be measured rather than assumed from the reduction in request count.
- CLIP/SigLIP-family embeddings, FAISS, scikit-learn, and HDBSCAN are replaceable candidates for local similarity, indexing, and grouping. Their names should not enter stage contracts.
- FiftyOne provides similarity, duplicate, uniqueness, representativeness, and clustering capabilities and is useful as a research benchmark or prototype. It should not become a required heavy runtime dependency without an explicit comparison.
- Immich, PhotoPrism, and digiKam demonstrate that persistent media indexes, thumbnails, embeddings, and similarity search form a stable problem domain. They are full applications, not direct MediaSense Tool contracts.

The currently inspected machine already has ImageMagick 7.1.1-47, ExifTool 13.25, FFmpeg 7.1.1, ffprobe, Quick Look, and `mdls`. Availability on one development host is not a portability guarantee.

## Planning-budget baseline from the legacy tree

The historical tree provides useful upper-bound scenarios even though its groups are not semantic ground truth:

| Sampling policy | Images presented to the Agent |
| --- | ---: |
| One image from each of 28 date/location macro groups | 28 |
| Up to two per macro group | 46 |
| Up to three per macro group | 61 |
| One image from each of 73 leaf groups | 73 |
| Up to two per leaf group | 116 |
| Up to three per leaf group | 140 |

This suggests that a first semantic pass on the Hong Kong fixture can plausibly start at 32-64 images and expand only heterogeneous or uncertain regions. It does not establish that every dataset, especially a hundred-thousand-item collection with many independent events, can be understood with the same fixed count.

The stopping rule should combine budget, mass/quality-weighted coverage, residual uncertainty, and marginal information gain. A fixed `N images per cluster` rule is not sufficient.


### 0.10.1 实际安装与统一 runbook 交付（2026-09-12）

用户先确认统一安装/升级 runbook，再明确授权执行实际升级。本次按
`readme/installation.md` 执行，发布输入固定为提交
`f5a17634be32afff998b31079c010e1b5c5050ef`、已确认的 runbook 及其发布检查改动、
0.10.1 补丁版本元数据。同期尚在开发的厂商知识和独立审计不混入本包；工作区保留。
准确文件范围和内容哈希在下述保留目录的 `scope.json`、`source-hashes.json`。

- 发布目录：`dist/releases/0.10.1-20260912/`；确切 wheel 为
  `wheel/mediasense-0.10.1-py3-none-any.whl`，SHA-256
  `227f20a968359a0e4301b2ccc7636af8e0e8cac09086f77800a703af0a0961c3`。
  119 个包文件与隔离发布源码、实际安装逐字节一致；合约、Skill schema 和离线
  runbook 副本一致。源码导出和 wheel 保留在此目录，不能当成可覆盖临时文件。
- 源码默认套件：1115 passed、16 deselected；唯一失败为旧开发环境发行元数据仍是
  0.10.0，目标版本断言为0.10.1。用已安装0.10.1环境单项复核通过；不将首次执行
  写成整套一次通过。安装包禁用源码注入后的 Plan 并发、取消、重试、Read复用及
  版本专项 **62 passed**。Python3.13.5、原 embeddings 依赖约束下的独立 uv tool
  distribution smoke 通过，涵盖实际CLI/MCP及四个Skill安装。
- 真实隔离安装和日常安装分别实跑合成图像/视频：公开Run/Read均交付5帧/2表，
  实际PTS正确，后继Run没有新增metadata/抽帧，源和旧Result字节不变，网络尝试0。
  本次不重新认证模型质量、完整业务媒体或真实地图服务。
- 日常入口仍为 `/Users/chengyanru/.local/bin/mediasense`，原uv tool管理；
  0.10.0→0.10.1，Python3.13.5、`embeddings` extra和原53项依赖版本保留。
  仅新增PyAV16.1.0；cp313 macOS arm64 wheel按锁文件地址下载并校验
  `408dbe6a2573ca58a855eb8cd854112b33ea598651902c36709f5f84c991ed8e`。
  依赖安装与正式切换离线完成，未下载模型、启用敏感性或更改embedding配置。
- 操作项目 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` 的四个Skills
  由原 `npx skills@1.5.25` 离线整组同步，关闭遥测。原11个文件匹配旧wheel，无本地
  定制；新12个文件匹配本次wheel，每个项目lock的computedHash经原生localeCompare
  排序及SHA256(path+content)核对。为保留确切版本，local source明确改为上述发布目录
  的 `source/`，不再依赖持续变动的checkout；其他Skill目标没有变化。
- 原MCP配置及凭据加载脚本保留。按项目原 `/bin/sh` 启动方式运行的doctor为ok，
  实际Host initialize为0.10.1，7个Tool的contract ID/digest与安装清单一致，临时
  Dataset Open→PreCheck Start通过。业务Dataset没有打开、迁移或恢复；只读inspect
  确认其manifest3、PreCheck17、Plan3、Geo2、Apply2，与本包格式一致。
- 已确认的旧Host PID18354（idle，父18263）通过TERM退休，Agent父进程保留。
  原Agent会话并未重新加载；独立Host验证不冒充业务会话验收。

回退材料保存在同一发布目录的 `before/`（旧wheel、uv receipt、依赖清单、四个
Skills和项目lock）。本次不迁移业务store；回退仍必须按runbook判断当前格式并用
各自manager恢复匹配集合。汇总 `installation-verification.json`、实际包/Skill/
launcher核对及视频配方输出都在保留目录内，不入Git。

**剩余会话交接：** 在上述操作项目中新开Agent会话，确认读取本项目新Skill与其
runbook、Host0.10.1及7个匹配合约后再继续业务。当前开发会话没有MediaSense MCP；
本次没有向旧业务Agent发送输入、恢复业务Run、修改Plan语义或冻结/执行Plan。


### DINOv3 384 正式入口与本机更新（2026-09-12）

用户明确选择已人工认可的 **DINOv3 ViT-B/16、384px**，授权正式接入、必要依赖／
固定权重准备和本机更新。依据 `readme/installation.md` 执行；公开 Tool 合约未因本次
实现改变。开始时的已有改动备份于 `/tmp/mediasense-dinov3-start-20260912-030026`。
厂商知识和独立审计改动保留，任务期间还观察到厂商分支文件更新；未将其混入本次安装。

| 能力／运行品质 | 迁移分类 | 本次结论与交付门 |
| --- | --- | --- |
| 本地高分辨率材料／视频帧 embedding、代表选择、源只读 | `preserved` | 沿现有 Encoder port、Work／Artifact、压缩与代表选择消费；正式 DatasetRuntime 已按配置装配，实际 CLI/MCP 推理通过。不是仅存在一个 eval adapter。 |
| ChineseCLIP Huge 224／1024 维 → DINOv3 ViT-B/16 384／768 维推荐 | `intentionally_changed` | 新配置显式启用且未指定模型时推荐 DINOv3；旧显式 ChineseCLIP 表（包括省略 enabled 的完整表）继续选择 ChineseCLIP。表缺省／空表／false 保持关闭，不改已有 Dataset 配置。 |
| 权重／预处理／后端与缓存身份 | `intentionally_changed` | 固定 revision、编译图文件 SHA-256、384 uint8 resize 配方、CLS、L2／float32、混合精度、ALL、线程、库版本和 OS／架构；输入与归一化进入既有 Work 依赖。与 ChineseCLIP、512 配方隔离。相同模型副本换位置不失效；有效上游准备独立复用。 |
| 下载、费用、失败与恢复 | `preserved` | Run/doctor 不下载、不转换模型、不回退远程或其他后端。已知依赖／模型条件阻塞并可恢复；未预期预测异常直接失败。真实测试网络尝试 0、Provider／收费调用 0。 |
| 运行成本与吞吐 | `intentionally_changed` | 复用已验收 366 输入证据：384 Core ML 9.335 s，ChineseCLIP CPU 155.29 s；是整体运行方案比较，不是纯架构速度或完整 PreCheck 耗时。本次 8 输入仅证明安装执行，不制造新的吞吐成绩。 |
| Intel macOS／Windows | `not_comparable` | 本次 DINOv3 均未发布／未验证，运行时明确拒绝。PyPI 核对：Torch 2.7／Torchvision 0.22 无 Intel macOS wheel，Windows x64 有 wheel；Core ML tools 9 有 Intel wheel、无 Windows prediction runtime。Intel Torch 2.2.2 CPU 或 Windows Torch CPU/CUDA 是待验证路线，不自动采用。 |

模型为 `timm/vit_base_patch16_dinov3.lvd1689m@c6a5fb7d12bbd3cf3b0079253141c3332aaed7da`，
原 checkpoint SHA-256 `1f9ed8a2378d65e24bb710ba522ac9fa7be4e036d7aefb4384ce022833926332`。
使用最终 LayerNorm 后 CLS；图中 FP16 卷积／MLP、FP32 attention／归一化／残差／RoPE／I/O。
生产 `_resources/dinov3-384.json` 固定配方和已验收编译文件；实际后端为 **Core ML ALL**，
不声称测得 CPU／GPU／ANE 的具体调度。要求 Apple Silicon、macOS 15+，本机 M5 Pro／
macOS 26.4.1 实测；其他满足前置条件的 Mac 仍须做本机推理检查。

**分组与人工决定边界：** 复用 `260911-0953-dinov3-resolution-384/report.md`：
384 模型／代表质量已获人工认可，两档 0.311／0.85 分别为 156／99 组，Core ML／MPS
成员、代表及选帧一致。现有 `compression.py`、`_compression_producer.py`、
`_compression_strategy.py` 与评测环境副本逐字节相同；时间 86400 s、空间 3000 m、
代表 top-half、exact limit 256、比较预算 65536 不变。历史稀疏视频帧不足以认证复杂
关键帧排序；本次不把模型认可扩大为该保证。**未改变当前算法的 0.311 默认值，也未将其
标成人工确认的生产粒度；已向用户提出 0.311／0.85 的默认粒度确认，答复仍待接收。**
这项未决选择不改变旧 Result，也不触发已有 Dataset 重算。

发布保留目录为 `.local/releases/0.10.1-dinov3-20260912/`。以上一次已安装 0.10.1
源快照为基底，仅合入本次 delta；不额外提交用户工作。此次仍为 0.10.1 的独立本地内容
构建，确切 `wheel-02/mediasense-0.10.1-py3-none-any.whl` SHA-256：
`eb851b9491eb112d0d146adc8c6cb05f5735460b214464c90b5745a7ecaa487b`。
`scope.json`、`release-diff.patch`、`source-hashes.json`、`dependencies.txt` 和安装收据
共同识别本次构建，不能只凭版本号确认。早期候选 wheel 保留，不覆盖已有校验值。

- 隔离发布默认套件 **1132 passed、16 deselected**；包含工作区既有改动的整体检查
  **1162 passed、16 deselected**。DINOv3／配置／Embedding／CLI 专项 45 项通过；
  静态检查通过。artifact-only 与真实隔离 uv tool distribution smoke 均通过。
- 完整 HK verifier 通过，10,608 文件、1,759,421,497 bytes。复用 8 个校验过的既有
  输入对比接受的 Core ML 向量，归一化最大元素误差 `6.76545e-9`、余弦距离 `1.60946e-9`。
  未重跑模型质量评测、未改历史输入或阈值以追平组数。
- 隔离 wheel 和实际 `/Users/chengyanru/.local/bin/mediasense` 分别经 MCP 执行 8 输入，
  输出均为 768 维有限单位向量，Run 记录 DINOv3 384 encoder identity。后继 Run 的
  metadata／rendition／embedding attempt 数和输出摘要不变。测试模型 locator 移除后
  `embedding_backend_unavailable`，恢复相同模型、新 Host resume 后完成且继续复用。
  源副本字节不变，真实模型未移除，既有业务 Dataset 未打开／迁移／批量重建。
- Python 3.13.5、embeddings extra 保留。Torch 2.13.0→2.7.0、NumPy 2.5.2→2.2.6；
  新增 Torchvision 0.22.0、Core ML tools 9.0、cattrs 26.2.0、pyaml 26.7.0、protobuf 7.36.1。
  Pillow 12.3.0 与其他原依赖版本保留；新增依赖复用评测版本，wheel 经固定 SHA-256 校验
  留存后离线安装。ChineseCLIP 原固定权重在更新后的实际环境单张离线推理通过（1024 维）。
- 已校验 384 编译模型持久存放于
  `~/Library/Caches/MediaSense/models/dinov3-vitb16-384-c6a5fb7d12bbd3cf3b0079253141c3332aaed7da`。
  `scripts/prepare_dinov3.py` 从可信固定导出原子复制、校验并幂等复用；本次未重新下载权重。
  它不提供从任意 checkpoint 自动转换的承诺，缺少该固定导出时按安装文档明确处理。
- 实际安装 **122 个包文件**与 wheel 一致；原操作项目
  `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` 的四个 Skills 由原
  `npx skills@1.5.25` 离线同步，**12 个文件**匹配 wheel，四个锁的 computedHash 复核通过。
  非 MediaSense 锁条目及原 MCP 配置逐字节不变。权威安装文档与发布 Skill 快照同步。
- 替换前未发现运行的 MediaSense Host。实际 CLI／七 Tool discovery 与最小分发通过，
  原凭据加载启动方式下 doctor=ok、DINOv3 prerequisites=prepared、embedding=disabled。
  安装版真实推理证明执行；doctor 自身仍正确报告 execution=not_checked。

详细证据保存在同一发布目录的 `actual-content-verification.json`、
`actual-dinov3-evidence.json`、`isolated-dinov3-evidence.json`、`numerical-verification.json`、
`chineseclip-installed-check.json`。完整临时输出位于 `/private/tmp/mediasense-dinov3-installed-*`，
均不进入 Git。初期脚本的 Dataset 初始化顺序和 Work 输出包裹层断言曾失败，修正测试后
完整重跑通过；沙箱 Core ML 访问系统缓存曾被拒绝，按授权获得系统执行权限后通过，
不把这些初次执行写成一次全绿。

`before/` 保留旧 wheel、uv receipt、四个 Skills／项目锁／MCP 配置用于回退；本次没有
业务 store 迁移。回退依赖和 Skills 仍须按 runbook 成套恢复，不以同为 0.10.1 推定相同内容。
**剩余事项：** 默认分组粒度的人工作答；在原操作项目中新开 Agent 会话以加载更新后的
Skills／Host。独立 MCP 验证已完成，但没有把磁盘更新冒充原业务 Agent 已热重载。

补充核对：原项目 MCP 注册在切换后新启动的独立 Host，其初始化版本、7 个 Tool 的
传输 schema 与 contract ID/digest 均匹配已验证安装；`actual-launcher-verification.json`
记录此证据。检查器最初按原始合约而非既有 MCP 包装比较，修正检查器后通过，未修改合约。
最后安装文档／Skill 同步与 CLI 专项 19 项通过。汇总见同目录 `installation-verification.json`。


### DINOv3 默认开启与 0.311 确认（2026-09-12）

用户明确回复“我要开启0.311 和 默认embedding。怎么弄 你直接弄”，据此确认
**0.311 为当前 DINOv3 384 的生产默认分组尺度**，并授权开启本机用户默认 embedding。
前一节关于默认粒度“答复待接收”的状态到此结束；原 0.85 评测与人工质量认可保留。

本机原先不存在用户 config.toml，本次在
`~/Library/Application Support/MediaSense/config.toml` 写入 owner-only 的完整 `[embedding]`
配置：enabled=true、固定 DINOv3 revision、384px、768 维、Core ML、batch 1。
0.311 已是安装版实际压缩默认值，无需添加未支持的 TOML 字段或修改算法。
配置在写入前已由安装版解析并通过固定依赖／模型校验；原启动环境 doctor=ok，
local_embedding=configured、DINOv3 prerequisites=prepared。

范围是本机用户默认：未单独覆盖 embedding 的 Dataset 在新 Host 打开时采用它；
Dataset 显式 embedding 表仍有更高优先级，已有 Run 快照和已封存 Result 不修改。
未打开或批量重建既有业务 Dataset；产品内建默认仍关闭，此次是用户明确选择。
本次配置前状态、精确配置和验证证据保存在
`.local/releases/0.10.1-dinov3-20260912/default-enablement/`，不改写前次关闭状态的安装历史。

正式安装 CLI/MCP 的独立单图验证通过：Dataset 没有自身 config.toml，Open 报告仅从
上述用户配置继承 DINOv3 384；Run 实际生成 768 维单位 embedding 并完成 Result，
压缩 Work 的 content_distance_scale 依赖实录为 `0.311`。源副本未变，网络尝试为 0。
具体证据为该目录 `verification.json`；无需重装软件或重建任何既有 Dataset。
