---
id: "eval-260823-1918B-capability-ledger"
title: "Migration Capability Ledger"
type: eval
status: active
created: 2026-08-23
updated: 2026-09-10
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
| Local camera times, offsets, sidecars, DJI/Canon photo cases | `preserved` | Local EXIF semantics and explicit offsets are retained without copying a mandatory vendor rule table. Tests distinguish camera fields from container fields. |
| Generic naive-time handling and timestamp provenance | `intentionally_changed` | Avoid c90's blanket UTC behavior for ordinary EXIF. Preserve raw candidates, uncertainty and filename/mtime fallback qualifications. Versioned metadata Work invalidates dependent GPX/bundle/compression work; old Results remain immutable. |
| Filename recovery after absent/invalid capture metadata | `regression` (fixed) | TimestampService had a basename fallback; migrated selection could instead select copied mtime. Generic timestamp patterns now precede filesystem fallback without overriding valid camera fields. |
| Local embedding reachable through installed Host | `regression` (fixed) | Internal adapter existed but runtime configuration/composition and optional dependencies prevented ordinary use. The real MCP path now executes and reuses a pinned local profile. No AI Album runtime dependency or automatic model download. |
| Optional models, content-driven frontier and unavailable representative fallback | `intentionally_changed` | Local cost remains explicit; no model is universally enabled. 167→117 candidates with 366 real encodings, and complete reuse later. Failed preferred representatives can use verified prepared members; failures remain visible. |
| Historical 168 representatives versus new frontier / total cost | `not_comparable` | Different boundaries and no new independent Plan quality/cost experiment. CPU work, hidden members and residual investigation are disclosed, not counted as proven savings. |
| Immutable accounting and independent evaluation boundary | `intentionally_changed` | Keep excluded source identity; remove automatic descendant samples and stage exact allowed inputs outside fixture. Clean judging context is separately required. No original media movement/deletion. |

### 2026-09 PreCheck scale correction

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
