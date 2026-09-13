# 本地敏感性接入：验收计划

## 状态与适用边界

**2026-09-13 用户独立复核：整体验收暂不通过，Read 输入关联、加载故障分类、公共执行信息三项需补修。日常部署未执行。** 本轮用户明确授权实现、当前合约落定、隔离构建安装及有界验证，并接受 B、D5-disabled 与 handoff 含义/失败边界。下文 A0 和原检查记录保留规划时事实；本次真实执行证据见末尾“实施验收记录”。业务 Dataset 与真实媒体 Apply 始终不在本轮授权内。

验收对象是已选 Freepik 与 NudeNet 640 配方经过生产接入后，输入输出、状态、复用及读取是否成立。整体人工认可继续成立；这里不要求重新评价模型、扩大全部候选、运行 69 个留出输入，或计算没有逐图真值支持的准确率。

## A0：当前允许的计划包检查

| 检查 | 通过条件 |
| --- | --- |
| OpenSpec 文档 | proposal/design/specs/tasks 齐备；三个 modified capabilities 与 delta 目录一致；strict validate 通过 |
| 引用与发现 | README 能找到设计、样例、delta 和任务；包内与仓库相对链接存在；不另建当前合约 |
| 合成样例 | JSON 合法；案例 ID 唯一；Observation 的 status/value/basis 与输入绑定成立；分布/累计/框和旧阈值关系自洽 |
| 执行边界 | tasks 的开发/验收任务全部未完成；包内明确仅规划；本任务的写入只在本 change，未修改当前公开合约、生产代码、安装、原素材或评测结果；并行工作另行识别 |

本组检查通过不证明任何适配器、生产链路、模型质量或安装结果。检查证据在实际运行后写入本页末尾，不能预先填入 passed。

## A1：语义与边界矩阵

下表是开发后的通过条件。已有测试入口见后文；新测试只围绕独立语义/故障边界，不机械复刻实现。

| ID | 要证明什么 | 正例与反例 / 必须观察到的结果 |
| --- | --- | --- |
| V01 | 单张/批量输入对应 | 正序、反序、尾批、混合可读/失败输入均回到实际输入；重复键、缺行、错绑和不明确输出在提交前失败 |
| V02 | Freepik 信息完整 | 四类均保留、有限 0—1、和为 1（容差 1e-6）；累计事件与 basis 求和一致；不出现 Falconsai 的旧阈值判定；缺类/非法概率拒绝 |
| V03 | 640 实例完整 | 同标签两个框、不同标签及非敏感原生标签全部保留；非正方形输入的 xywh→xyxy 与 native 坐标一致；越界、零面积和错误输入尺寸拒绝，不二次修框 |
| V04 | 未提供/无检出/停用 | Freepik 不输出伪空 regions；640 成功无框是 available+[]；任一模型或全部关闭均无该模型新执行；D5 默认下有效缓存也不进入新 Result |
| V05 | 失败与恢复 | 单输入已知失败保持兄弟成功；需要新工作但缺本地后端时按既有阻塞恢复；恢复沿原快照；未知异常/对应关系错误不变成正常等待或坏源 |
| V06 | Work 复用与局部失效 | 全复用无新增模型 attempt；只改 Freepik 配方仅重做 Freepik；不重做有效 metadata/图像/视频/embedding/640；纯调度变化不制造全失效 |
| V07 | 后端与资源诚实 | 4/1 独立批量不受 embedding batch 控制；实际 MPS/CPU 与声明一致；模型驻留仍有资源责任；预算不足不截小需求、不悄悄换设备；未知指标不写零 |
| V08 | 历史及无模型读取 | 在不安装推理库、不提供模型权重的隔离读环境中，真实 Host 能读保留的 Result；99/33 与旧判断原义保留；无框/无输入证明不被补造 |
| V09 | Source/Evidence/关系边界 | 高清照片及视频帧分别可追溯；同模型不同帧不冲突；Representative 的其他成员不继承观测；源尺寸与输入尺寸不可互换 |
| V10 | 公共完整交付 | review/expand 保留已声明属性、来源及限制；实例变多时使用现有分页/单项超限行为，禁止截断；单份 structuredContent 交付 |
| V11 | 增长与替换 | 一个不同标签的合成分类适配器通过同一端口/值类型/消费路径；未知新信息形式必须显式声明/扩展，不能放宽成任意 JSON 或伪概率 |
| V12 | 安装与配置迁移 | 包内依赖/权重/资源副本正确；新配置按模型启停；旧四键配置明确迁移，不自动换模型；配置/缺模型不阻止历史读取 |

与 [handoff.examples.json](handoff.examples.json) 的主要对应：both_models_available→V02/V03；successful_empty_regions→V04；两种 disabled→V04；known_input_failure/required_backend_missing→V05；valid_cache_without_model→V06/V08；unprepared_input/video_frame_scope→V09；model_disagreement→V10；legacy_v1_read→V08。JSON 是拟议片段，不冒充当前 Tool 完整响应或已通过当前 schema 的新值。

## A2：模型配方的一致性验证

**仅在获准开发及对应有界验证后执行。** 默认技术子集为现有 development 的 sample-0001、sample-0002、sample-0011、sample-0013、sample-0104，最多五个输入/模型；先核对 prepared 清单中其身份与 split。Freepik 用完整 batch 4 加尾批，640 用 batch 1；包含已选照片、实际视频帧及非正方形输入。

| 比较 | 基准及门槛 |
| --- | --- |
| 输入 | prepared 清单及各结果的 input_sha256；字节、定向、尺寸必须一致。输入变了就不是模型移植一致性比较 |
| Freepik | 对相同输入核对四类和累计事件；绝对概率差不超过 1e-5，类别顺序/语义、公式和声明设备相同；不以 argmax 相同替代数值检查 |
| NudeNet 640 | 与所选 native 运行比较实例数量、标签和整数框位置完全一致；score 绝对差不超过 1e-6；实例保留顺序可规范展示，但比较必须能证明全部实例未丢失 |
| 外部效果 | 输入不上传、无网络模型回退、无运行时下载；源、source-copy、prepared 校验不变 |

参考运行来自 [README 的证据入口](README.md#评测证据入口)。如超过门槛，先定位输入、库版本、预处理、设备或 native 后处理差异；不能调宽容差、改参考输出或改模型来让测试通过。仅针对失败边界增加必要技术检查，不扩大成新一轮选型或留出集推理。

原始网络张量不进入公共 Result，也不要求作为长期产物；诊断需要时保存在新的测试输出目录，不能写回原评测运行。已有成本数据只作预算依据，本计划不重跑成本补测。

## A3：实际安装链路

遵循唯一 [installation runbook](../../../readme/installation.md)：固定源码/包含的 diff、Python、extras、依赖约束和 wheel SHA，再验证包内契约与 Skill/runbook 快照。选择与记录当前安装依赖的兼容增量，不能仅按宽版本范围重装全部依赖。

使用现有 distribution/precheck delivery runner 的隔离配置和临时 Dataset，至少覆盖：

1. 核心读环境没有可选推理库和权重，仍能经真实 Host 读保存的结果；新执行的不可用状态另报。
2. Freepik 单独、640 单独、两者一起、全部关闭四种配置；使用一张受控图片和一个短合成视频/已准备帧验证 Source→Run→Result→Read，读取结果可供现有 Plan 入口使用。
3. 相同配方的后继 Run 无新模型 attempt；一个模型配方变化只影响相关工作；当前 Result 引用固定且旧字节不变。
4. 删除/损坏受控权重时需要新工作明确阻塞；恢复确切权重后按原快照继续。未知异常应暴露，不能靠空结果完成。
5. 真实可选依赖齐备的隔离安装运行 A2 技术子集，保留实际加载来源、设备、图片身份与模型/配方；不能用 checkout 的 src 路径污染安装验证。

测试 Dataset 显式关闭不属于场景的模型和所有外部能力，避免继承本机已经启用的 DINOv3 或其他用户配置。模型资产使用测试/正式资产位置的已验证副本，不让生产依赖 Downloads 或 eval Python 模块；所有输出在新临时/验收目录，原证据保持只读。

这里区分包内一致性、隔离安装真实执行、日常安装/会话实际加载三种证据。前两种通过不授权日常切换，也不代表完整产品流程性能或所有平台已认证。

## A4：检查入口与范围

| 已有入口 | 本次应覆盖的边界 |
| --- | --- |
| tests/test_sensitivity.py | 值校验、实例保留、模型端口、批量对应、成功/失败/复用 |
| tests/test_precheck_orchestration.py、tests/test_resources.py | 逐模型需求、资源寿命、控制、缺后端和未知异常 |
| tests/test_runtime_config.py、tests/test_runtime_host.py、tests/test_runtime_cli.py | 配置层级、装配、延迟加载、诊断及入口 |
| tests/test_precheck_read_contract.py、tests/test_precheck_run_contract.py、tests/test_contract_authority.py | 经审阅后的交换值/状态/完整性和发布定义一致 |
| tests/test_precheck_result.py、tests/test_precheck_delivery.py、tests/test_precheck_read_reuse.py | 封存、实际输入归属、历史读取、局部复用和分页 |
| tests/run_distribution_smoke.py、tests/run_precheck_delivery_smoke.py | wheel 与实际 CLI/MCP 的完整路径 |
| tests/test_honeycomb_integration.py、tests/test_runtime_versioning.py | runbook/Skill 快照、既有持久状态与版本保护 |

实施时先读现有检查并扩充有意义的正反例；必要的模型专项测试按实际模块职责新增。不运行未授权的 local_fixture/scale、全量业务素材或其他候选模型。变更相关检查通过后完成默认仓库检查；仅在新修改、失败或未解决疑虑出现时扩大/重复。

## A5：收尾与迁移证据

验收报告记录精确 source/wheel/config/模型输入身份、执行设备、已通过的 V01—V12、实际模型调用范围、失败/重试、旧 Result 哈希、复用/局部失效和未认证边界。不得用“字段可扩展”替代生产装配或消费交付证据。

差异分类仍维护在既有 [迁移台账](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)：本地证据与历史值保留、模型/配方替换及路由归 Plan 的意图分别归类；当前计划不提前写 implemented，不把新的定性人工评价换成旧基线统计准确率。

## 当前检查记录

2026-09-12 22:46（Asia/Shanghai；工具时间 14:46:54 UTC）完成 A0 检查：

| 项目 | 实际结果与范围 |
| --- | --- |
| OpenSpec 1.2.0 strict validate | passed；1 个 change，issues=[]，3 个 delta capability 与 proposal 一致 |
| OpenSpec artifact status | proposal/design/specs/tasks 均 done，isComplete=true；这是文档完成状态，不是开发放行或执行完成 |
| 合成 JSON 与语义 | passed；11 个情形、16 条 Observation；3 份分类分布/累计、6 份区域列表、2 条 V1 历史观测；状态/值、输入、重复标签实例、概率公式、坐标、99/33 关系均自洽 |
| 引用、空白及任务 | 41 个 Markdown 相对链接目标存在；无尾随空白；30 个开发/交付任务全部未勾选；本包 git diff --check 通过 |
| 写入与并行范围 | 本任务只写本 change 的计划文件。核对期间其他工作推进了 Git HEAD，并包含本包较早草稿提交；同时存在 Plan 功能/测试及相关验收台账改动。本任务未调用 git commit，也未修改这些生产文件，不将并行工作算作本能力开发 |
| 未执行 | V01—V12 产品测试、真实模型推理、成本补测、wheel 构建、安装/升级、业务 Dataset 及原媒体操作均为本任务未执行 |

实际 OpenSpec 检查命令：

~~~sh
rtk proxy env OPENSPEC_TELEMETRY=0 openspec validate extend-local-sensitivity-observations --type change --strict --no-interactive --json
rtk proxy env OPENSPEC_TELEMETRY=0 openspec status --change extend-local-sensitivity-observations --json
~~~

合成资料以 Python 标准库 JSON/数学/路径检查验证，没有导入产品代码或推理框架；它不替代未来正式合约 schema 与安装链路验收。以上记录不把 D5-disabled 或精确 handoff 草案标为用户已确认。

V01—V12、A2—A5 仍全部是未来实施验收，当前没有执行结果。下一步是向用户报告计划就绪并等待开始指示。


## 实施验收记录（2026-09-13）

**结论：tasks 1—6 完成；源码、最终 wheel 与实际隔离 CLI/MCP 路径通过。停在日常部署前。**
本次从用户明确的后续授权开始，不把上一轮 A0 当作开发许可。当前 Run/Read/Dataset Open 合约
先落实信息与状态含义，再接入生产。属性仍归属于 Source Item，绑定实际 Evidence；未新增 Tool、
注册服务或第二份 Result。旧 V1 只读保留，新生产不再执行 Falconsai/320 或写 V1 标签摘要。

### 精确身份与环境

| 项目 | 实际记录 |
| --- | --- |
| 实施基线 | `615c3359941927515f0c0a8738a3f08122bcad46`；开始时 diff/status 留在 `/private/tmp/mediasense-sensitivity-260912/baseline.patch` 与 `baseline.json` |
| 最终隔离源码 | `/private/tmp/mediasense-sensitivity-260912/candidate-4/source`；`source-identity.json` 记录包含文件 SHA-256，`included.patch` 保存差异；其他线程的 Plan/测试/台账改动及新 HK eval 会话不混入构建 |
| 最终 wheel | `/private/tmp/mediasense-sensitivity-260912/candidate-4/wheel/mediasense-0.10.2-py3-none-any.whl` |
| wheel SHA-256 | `6c35c4d05679311b08121e0278d5520a9d52465411214f67180f8e0807bdc373`；版本字符串仍为 0.10.2，必须按此内容身份识别本次隔离候选 |
| Python / 本机 | 3.13.5 / Apple M5 Pro / macOS 26.4.1；实际模型 MPS FP32 与 CPU FP32 |
| 模型安装 | `/private/tmp/mediasense-sensitivity-260912/model-env`；保留日常安装已有兼容依赖，新增固定 Timm/NudeNet/ORT/OpenCV 及其依赖，详见 `daily-dependencies.json`、`constraints.txt` |
| 核心读安装 | `/private/tmp/mediasense-sensitivity-260912/core-env`；无 torch / transformers / timm / nudenet / onnxruntime / numpy，见 `core-environment.json` |
| 模型资产 | 从已校验资产复制到 `/private/tmp/mediasense-sensitivity-260912/models`；运行不引用 eval Python 或 Downloads 权重路径；没有下载选定权重 |
| 依赖准备 | 曾遇离线缓存缺失；在已授权的隔离环境安装固定 Python 依赖，随后最终 wheel 构建/安装离线完成。NudeNet 依赖包自带的 320 权重未被选用 |
| 持久格式 | PreCheck 18、Run 快照 8；17→18 只升级格式标记，不变换 Work 输出或旧 Result；旧写入者拒绝 18 |

`candidate-4/source` 是最终实现快照；之后的验收文档与任务勾选只记录结果，不改变 wheel 代码。
最终两个安装环境中所有包内代码/资源逐字节等于 wheel；没有通过 PYTHONPATH 注入 checkout。
`final-integrity.json` 核对本任务生产改动与最终 wheel 一致；被排除的其他线程 `plan/work.py`
按记录的源码基线进入构建，未覆盖工作区中的并行修改。
发布的 schema 和 Skill 内 Run/Read、installation 快照与当前权威文件一致。

### A1：V01—V12 的实际证据

| ID | 结果与证据范围 |
| --- | --- |
| V01 | passed；`test_sensitivity_named.py` 验证正/反序、缺行、重复键、错 SHA、已知局部失败与未知异常；无法对应/非法输出在成功提交前拒绝，并清除失去执行者的 lease |
| V02 | passed；`test_sensitivity_contract.py` 的合成正反例与最终纯校验保留四类/累计关系、概率域和和；A2 五输入绝对差 0 |
| V03 | passed；三个合成 native 区域含两个同名 FACE 和 covered 标签，经 Work→seal→expand 完整相等；错误源绑定/输入尺寸/框/零面积拒绝；A2 18 个实际实例数量、标签、整数框完全一致 |
| V04 | passed；五个实际后继选择依次双模型、Freepik、640、全关闭、重启用，available 数为 8/4/4/0/8；关闭模型明确 not_checked，不纳入缓存。合成空框为 available+[]，分类没有伪 regions |
| V05 | passed；单输入已知失败保留兄弟成功、完整失败 provenance；缺固定后端阻塞且不发布；恢复确切资产后沿原快照完成，期间把配置改为全关闭也不改变原 Run。未知实现错误不转为正常等待/坏源 |
| V06 | passed；五个后继选择及核心无模型缓存 Run 的模型 Work/attempt/output 保持；synthetic recipe 改变仅创建该模型新 Work，兄弟模型复用；纯 batch/资源估计变化不改变语义身份 |
| V07 | passed；实际双模型为 Freepik batch 4 / 640 batch 1，后端 MPS / CPUExecutionProvider；单元检查 reservation 从首次新工作到 close 持有，缓存不准入模型资源，超预算不截小需求。内存观测未知保持 null，批次墙钟不称逐图延迟 |
| V08 | passed；核心真实 Host 在没有可选推理包且模型资产路径暂时不可用时读新 Result 并完成缓存后继 Run；旧安装生成的真实格式-17 合成 V1 Result 经新 Host 读取，99/33/false 原义与封存 SHA 保持。历史无输入记录原样保留在 gap 中，不补框 |
| V09 | passed；实际一张带 EXIF 受控照片及一秒合成视频形成四个模型输入（高清图＋3 帧）；每模型4条，全部真实 Evidence 绑定；错误 Source/derived_from 和尺寸反例拒绝，代表关系不扩张检测覆盖 |
| V10 | passed；真实 MCP review/expand 完整返回8条检测，content=[]、单份 structuredContent；Result 被 Plan create 接受。原有整项分页、单项超限和历史缺口回归通过，未增加截断或叠框转换 |
| V11 | passed；不同 dry/wet 标签的合成分类适配器经同一端口、Work、封存和公共 Read；未知具名种类及嵌套未声明信息拒绝，无品牌消费分支 |
| V12 | passed；逐模型配置/整表覆盖、旧配置明确迁移、配置解析与历史读取分离；doctor 区分 prepared/unavailable/invalid 和 not_checked；包内一致性、核心环境、实际格式升级和旧写入者拒绝已验证 |

相关测试位于本仓库 `tests/test_sensitivity*.py`、现有 orchestration/resources/runtime/
contract/result/read 回归。最终仓库工作区默认测试（Python 3.11.13）**1336 passed，16 deselected**，用时 241.82 秒；
local_fixture 与 scale 保持既有排除，没有香港业务素材或留出集运行。
Ruff 与 git diff --check 通过；OpenSpec strict validate 为 1 passed、issues=[]。
日志：`/private/tmp/mediasense-sensitivity-260912/pytest-final-unrestricted.log`。

### A2：模型一致性

只运行 development：sample-0001、0002、0011、0013、0104；3照片＋2实际视频帧，包含非正方形。
每模型5输入，没有留出集或新候选。Freepik 使用4＋1，640使用五个batch 1。
输入字节、参考结果和权重在前后核对；原素材/source-copy/prepared/参考结果未写入。

| 模型 | 结果 |
| --- | --- |
| Freepik | 四类及累计概率最大绝对差 **0**，门槛1e-5 |
| NudeNet 640 | **18实例**，数量/标签/整数框完全一致；最大score差 **4.172325134277344e-7**，门槛1e-6 |
| 外部效果 | A2 socket guard 无网络尝试，模型加载固定本地文件；A3当前/历史provider请求均0 |

原始记录：`/private/tmp/mediasense-sensitivity-260912/model-check-1/report.json`。
最终一致性复用证明：`/private/tmp/mediasense-sensitivity-260912/accepted-model-evidence.json`。最终 wheel 的适配器和配方
与该实测版本逐字节相同，保存输出也通过最终值校验，因此没有重复五输入推理。
模型代码 SHA-256：`d94e47a4afa8d1d46cfe4ffada6cd0894573e8ba4eabdd6fdf61c9b72313b1e9`；
配方文件 SHA-256：`4dc6f697e83c77776e97e071e1db9a81cc8d9a04f7e7319e3dfee399cdf8575e`。
线程限制为2 intra-op/1 inter-op；640保留 native 颜色/NMS，分数微差没有放宽门槛。

### A3：安装、历史与恢复

最终证据：`/private/tmp/mediasense-sensitivity-260912/delivery-accepted/report.json`、`delivery-summary.json`、
`distribution-accepted.log`。实际使用 candidate-4 的 CLI/MCP 可执行文件。
主临时 Dataset 每模型4条成功 Work、4次逐项 attempt；Freepik 一批4，640四批1。
之后单模型/全关闭/重启用与核心缓存 Run 没有新增模型 attempt。恢复 Dataset 在缺权重时
阻塞，确切权重恢复后同 Run 交付8条观察。Plan 仅 create，没有真实媒体 Apply。

首份新 Result SHA-256：`65ae4049975bc5adc4e32365ab99e7500f9500b16b89406b0b58935b7fd3e1d1`。
旧格式 V1 Result SHA-256：`75f70ce38dee784b5b0179d5f722c69aaefcaeba6b0cf988d95a57a23f3fa6eb`。
二者在后继/读取后保持。`rollback-evidence.json` 证明旧写入者拒绝新格式且旧备份可打开；
`migration-final.json` 证明最终核心 CLI 真实升级17→18。`model-env-doctor.json`、
`core-env-doctor.json`、`legacy-config-doctor.json` 分别保留依赖就绪、缺依赖和旧配置诊断。

### 保留的失败与修复

- 首轮默认检查发现格式迁移测试仍把17视为不支持、历史 gap 内的原记录被新增限定影响，
  及一个测试继承本机 DINO 配置；分别调整受支持版本反例、把新增限定留在读取视图而保留
  原记录、隔离测试配置。没有改写旧封存字节或模型参考输出。
- 首次 A3 脚本先向空 Dataset 写配置触发 manifest_missing；改为按正式入口初始化后写
  受控配置。此轮尚未推理。
- 后续沙箱复验无法发现 MPS，生产按要求 blocked；四个默认测试的 loopback bind 被拒绝。
  在本轮已授权范围内放行本机 MPS/回环端口后通过。没有 CPU/远程回退；失败日志保留在
  `delivery-final.log` 和 `pytest-final.log`，不把环境失败改成模型通过。
- 最终边界补修包括：失败 Work 保存完整已知来源/后端、无执行者 lease 失效、原子格式标记
  升级和未声明嵌套信息拒绝。对应定向检查与最终完整默认检查均通过。

### 结束边界

日常 executable/Skills/MCP 注册启动链路未切换，实际用户/业务 Dataset 配置未改，未执行真实媒体 Apply。
Freepik的MPS依赖、640固定镜像来源限制、未认证平台、全量性能/长稳态和更广质量覆盖仍保留。
本次不重做人工质量验收、不报告新准确率、不运行69个留出输入。格式18会排除旧写入者；
将来的日常升级需按安装 runbook 先处理旧未终结 Run，并保存一致备份。
所有验证输出在 `/private/tmp/mediasense-sensitivity-260912`；这是临时保留位置，Git仅保存实现、紧凑证据和可复现检查入口。


## 用户独立复核与三项补修（自检完成，待独立复验）

用户保留已核实的正常模型/安装证据，指出 Read 未复用封存的输入关联检查、加载错误笼统转为
backend-unavailable、批量/耗时/有效预算仍只在私有 Work。原1336项测试与五输入数值结果是历史
执行证据，不能覆盖这些反例。补修只沿这三个边界推进，不重跑人工质量验收或留出集。


### 三项补修结果

本次只修复用户指出的三个边界；**补修自检完成，不把它写成用户已通过整体验收**。
原1336项默认测试、五输入模型一致性、原wheel与两套131文件安装仍保留其原来的证据范围。
本轮没有重新运行真实模型，没有日常部署、业务 Dataset 配置修改或真实 Apply。

| 用户反例 | 修复 | 本轮独立检查 |
| --- | --- | --- |
| Read接受Result外输入、错绑照片、错误尺寸 | `validate_input_links` 成为封存/Read共用的纯校验，验证同Result、实际Source、derived_from及输入尺寸；不以represents代替来源 | 三种内存副本反例在封存及`_validate_package`均拒绝；正常原封存字节可读且不变 |
| 未知加载RuntimeError被包装为正常阻塞 | 模型/ORT构造不再笼统转换RuntimeError、ValueError、OSError或ImportError。仅明确缺包/文件、权限与设备/provider前提走backend-unavailable；前提探针的未知异常也直接暴露 | 两加载器×四种未知异常原样传播；三种未知探针异常拒绝伪装缺前提；已知缺固定资产仍为backend-unavailable；未知异常沿真实Run成为failed |
| 实际批量/耗时/有效预算未公共交付 | 现有Work保存每次调用的批次身份、实际输入数和分离计时；现有Run/Result负责投影，既有status/review与分页交付，不新增Tool或存储服务 | 同批两个Work只计一次；跨批计数/耗时与Work覆盖校验；重复批次/矛盾总量拒绝；真实安装MCP两次Run及Read分页一致，后继复用无新适配调用 |

### 公共读取入口与含义

- Run：`status include=["diagnostics"]` 的 `diagnostics.local_execution` 返回有效资源预算及每模型汇总。
- Run：`status include=["local_execution"]` 返回汇总与 `batches/page`，使用既有`page`。
- Read：`review include=["local_execution"]` 从不可变Result读取同一快照，使用既有`execution_page`。
- 分页均默认50、最大200。Run的local_execution/diagnostics/confirmation详情互斥；Read一次选local_execution或execution_boundary。证据分页与执行分页保持独立，原整项字节上限不变。

预算是冻结Run的准入capacity/max_workers/max_pending，不冒充实测内存；模型另有memory_estimate_bytes。
每批的input_count是调用输入数，inference_input_count是实际送入模型的数量；未知为null。
processing_wall_seconds计analyze区间，不含已分离的load_wall_seconds；后者null时不推断能分离加载。
每批都有可去重的batch_id，多个Work保存同一事实只计一次。复用保留整个原批次成本，
included_work_count说明本次只引用了多少Work；不把四图批次摊成一张图的“实测”。
模型的recorded_current/recorded_reused只汇总有证明的批次，unreported_work_count明确未记录的部分。

旧Result缺少执行快照时返回not_recorded、预算null和空明细；**不回查私有Work补造封存历史**。
旧Work缺批次身份/分离计时时不按重复数值猜批次，不聚合成虚假的已知成本。
Run/Read公共机器定义已同步；local_*定义唯一在Run合约编写，Read的生成片段有明确来源和一致性测试。

### 检查与构建身份

- `tests/test_sensitivity_repairs.py`：20项反例/边界检查通过。
- 本轮最终工作区定向回归：**287 passed，37.31秒**，含敏感性、编排、历史读取、分页、Run/Read合约及发布副本；未重跑整套默认审计。日志：`/private/tmp/mediasense-sensitivity-repairs-260913/focused-tests.log`。
- Ruff、git diff --check、OpenSpec strict validate通过；机器定义和安装runbook发布副本一致。
- 最终源码：`/private/tmp/mediasense-sensitivity-repairs-260913/candidate-2/source`；以原candidate-4为基线，仅加入本次修复。`source-identity.json`、`repair.patch`记录确切文件与差异，排除其他线程的GPX/compression/Plan改动；工作区中的这些改动保留。
- 新wheel：`/private/tmp/mediasense-sensitivity-repairs-260913/candidate-2/wheel/mediasense-0.10.2-py3-none-any.whl`。
- 新wheel SHA-256：`89a44a95394b2cd0034620c33662123d731234a6f31c62a0fc54036f290aec64`。
- 新核心隔离环境Python3.13.5，没有Torch/Transformers/Timm/NudeNet/ORT/NumPy；**132个包内文件**逐字节等于新wheel。
- 原两套隔离环境的**各131个包内文件**仍逐字节等于原candidate-4，未覆盖用户已核实的安装证据。

安装验证使用`tests/run_sensitivity_repairs_smoke.py`的具名合成适配器，经安装版Producer/Orchestrator封存，
再由真实安装的CLI/MCP读取Run诊断及Result。这是执行输出与恢复/读取验证，不是新的模型质量证据。
4张受控图片产生4个Work、2个实际适配器批次；首Run计2批/4输入，后继Run记为复用，适配器总调用仍为2。
两页批次ID去重、耗时求和、有效预算在Run与Read一致；MCP只有一份structuredContent。
旧V1 Result在独立Dataset副本读取，明确未记录执行快照，封存SHA不变。

主证据：`/private/tmp/mediasense-sensitivity-repairs-260913/installed-smoke-2/report.json`，SHA-256 `b7b674f19fbc7b4cf220de196d375f39d15f6aebedc90e24726e3fa2834f7f9f`。
安装/包完整性汇总：`/private/tmp/mediasense-sensitivity-repairs-260913/verification.json`。首次smoke因测试脚本未给后继Run建立源对账而正确得到
execution_not_prepared；修正测试准备后通过，原日志保留，未把该失败改成成功记录。

固定配方文件字节不变；分析函数去掉新增测量赋值后的AST与原candidate-4一致，
证明未改图片预处理、模型调用、概率计算或native检测处理。见`/private/tmp/mediasense-sensitivity-repairs-260913/numerical-path.json`。
本轮真实模型推理调用数为**0**，原五输入一致性仍是已有证据，没有伪称在新wheel重新实测。

当前停止点：三个修复及对应自检/隔离交付已完成，供用户独立复验；日常部署仍未授权。
