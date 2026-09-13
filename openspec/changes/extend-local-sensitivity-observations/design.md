## Context

**2026-09-12 用户后续授权本设计进入开发，接受 B、D5-disabled 与 handoff 含义/失败边界。** 准确交换值已落实到当前合约；本页保留设计理由，不成为第二份 schema。

用户已选择 Freepik/nsfw_image_detector 与 NudeNet 640m，并确认“图片和执行要求输入，具名属性与执行情况输出”的方向。模型内部方法由适配器负责；PreCheck 取得本地证据，Plan 判断如何使用。用户授权 Agent 自行确定有充分依据的工程细节，；上一轮暂缓开发的指示已被本轮明确授权取代。

本次只读基线为源码 commit `6acf1f56f5531bcfc425cb2c5ae6cf50eba3b168`，当时工作区干净，pyproject 版本为 0.10.2。当前装配仍是 Falconsai 与 NudeNet 320，端口只有 label/score，通用后处理取同名标签最大分，设备/模型批量未逐模型分开。这里不重新认证日常 Host 或用户配置；下一次开发应仅核对相关差异，不重做模型选型和全仓审计。

权威依据：[Foundation](../../../docs/design/design-260823-1918-mediasense-foundation.md)、[可复用能力架构](../../../docs/design/design-260830-1527-reusable-capability-architecture.md)、[对象/关系/属性模型](../../../docs/design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)、[当前合约](../../../docs/spec/contract/index.md)。评测是工程证据，不是产品合约；工程参考身份见 [README](README.md#评测证据入口)。

## Goals / Non-Goals

### Goals

- 相同的本地图片输入协议可接不同模型，返回值有具名含义、类型、来源和失败边界；模型可以只提供自己支持的信息。
- 完整交付 Freepik 四类互斥概率及累计概率，以及 640 native 的所有标签、分数和位置；多个同类实例保留。
- 每模型独立启停、配方、设备和批量；有效成果局部复用，历史结果无需对应模型或推理库仍安装。
- 使用现有 Observation、basis、provenance、qualifications、Work、Run 和 Result；用户能分清少取得了哪些信息以及原因。

### Non-Goals

- 重新比较候选、对留出集运行模型、重做逐图人工验收或生成准确率/召回率。
- 本轮正式接入 Marqo、MiniCPM、EraX；Falconsai 保留历史含义，不自动成为新组合的一部分。
- 全成员/全视频检测、跨模型合成真假值、统一敏感阈值、自动远程路由或模型管理网页。
- 插件平台、注册中心、独立 Attribute/检测实体、常驻服务、新 Tool、另一份属性存储或长期保存原始网络张量的义务。

## Backward Compatibility Policy

| Attribute | Value |
| --- | --- |
| Production status | 已有 MediaSense 本机安装、Dataset 和封存结果；新模型接入尚未实现 |
| BC Level | L0：沿当前合约的零公开 API 兼容政策；改变已确认含义仍需合约审阅 |
| Deprecation window / sunset | 不设双路由、双写或永久旧配置别名 |
| Migration ownership | 本 change 的生产者、读取者、配置、消费者及发布副本一起迁移 |
| Durable-data boundary | 旧 Result 字节不改；原有 V1 值、阈值及实际输入证据继续可读；零 API 兼容不授权删除历史 |

生产状态及 BC 级别由现有合约和用户上下文直接确定，无需重新问卷。这里沿用 backward-compat-questionnaire 的政策记录方式，不采用历史文档中“尚无生产消费者”的旧假设。

## System context

~~~text
稳定能力：取得可追溯、可组合的本地内容观察
+-- PreCheck：选中已有图片/视频帧，固定本次模型与配方
+-- 现有模型端口与逐模型适配器
|   +-- Freepik -> 分类分布、累计概率
|   `-- NudeNet 640 -> 区域实例
+-- SensitivityProducer / Work：资源准入、执行、复用、结果校验
`-- Result -> Source Item 的 content_sensitivity Observation
    +-- 实际 input_evidence_ref、来源及限制
    `-- precheck.read -> Plan 解释；展示层按属性类型展示
~~~

适配器不读写 Dataset 私有数据库，不决定选哪些素材或是否进入 Plan，不构造完整公开 Result。输入是已准备、可证明的单帧图片；图片可源于照片或视频。公共 Source Item/Evidence 引用由 PreCheck 投影，内部输入对应键不变成新公共身份。

## Decisions

### D1. 一个输入/输出端口，方法留给模型

沿 SensitivityDetector/SensitivityProducer 改造最小端口。下表定义责任，Python 方法名和拆文件方式由实现者确定。

| 边界 | 输入 | 输出及保证 |
| --- | --- | --- |
| 适配器/配方声明，准入前可读 | 明确的模型和配方绑定 | 支持的图片条件、会提供哪些属性、标签/分数定义、设备与批量限制、资源估计；不为读取声明加载模型 |
| 一次单张/批量分析 | 有唯一对应键的本地图片句柄、已验证输入身份和尺寸、冻结配方、允许的执行约束 | 每个输入恰有一项可对应的结果或已知局部失败；返回普通数值/结构，不返回 Tensor、库对象或私有 Work 身份 |
| 执行事实 | 实际加载、批次与设备事件 | 实际后端/精度、配方/代码/依赖身份、可证明的加载/批次耗时和资源观察；未测为未知 |
| PreCheck 投影 | 已提交 Work 及输入 Artifact 的真实关联 | 一次模型/输入的 Observation；封存时替换为 Result 内真实 Evidence 引用 |

请求既可是一张也可是一批；批次是执行安排，不是新持久实体。返回必须验证输入键的一一对应，拒绝缺行、重复、错绑和不可归属的结果。声明、缓存检查和 Read 不要求重载权重。

不强制所有适配器接收同一个 RGB Tensor：Freepik 的 Pillow/Timm 路径和 640 的 native OpenCV 路径分别遵守已选配方。共同边界是已定向、单帧、只读的准备图片及其身份。原始文件解码/采样仍由现有准备能力负责。

### D2. Attribute 复用 Observation，不再加一层实体

同一模型对同一输入的结果继续用 `name=content_sensitivity`。现有外层 status/value/basis/provenance/qualifications 继续承担状态、值、依据、来源和限制。拟议的新 value 保留 detector_identity/profile，并在其中放下列具名值；这不是另一个 attributes 存储或嵌套 Observation 生命周期。

| 拟议属性名 | 值与最小校验 | 模型特有内容 |
| --- | --- | --- |
| classification_distribution | taxonomy、score_semantics、完整 probabilities；有限 0—1 概率，类别不漏、不重，互斥分布和为 1（首期绝对容差 1e-6） | Freepik 的 neutral/low/medium/high，模型原生四档含义；不是通用裸露真值 |
| cumulative_probabilities | 具名事件的 0—1 概率；basis 保留所引用类别与求和公式，校验与原分布一致 | at_least_low=low+medium+high；at_least_medium=medium+high；high=high |
| region_detections | taxonomy、score_semantics、坐标基准、输入尺寸、instances；实例有 label/score/box_xyxy，允许同名多条 | NudeNet 18 类标签、native 检测分数与筛选方法；保留 FACE/covered 等全部原生标签 |

三者是首期的真实信息需要，不是框架永久穷举。每个 profile 明确必需输出：Freepik 要求前两项，640 要求区域项。只有已实际提供的属性出现在可用值中；Freepik 不输出空区域列表来冒充检查过部位。

标签与分数定义随有效 profile 的公开 provenance 保存必要快照，至少包含 taxonomy 身份、已声明类别、值含义/单位、适用范围及解释限制；读取不向模型、外部网页或私有缓存查定义。累计概率的依据放已有 basis，不创建新的派生实体。没有可校准的统一 confidence 就不生成。

以后新增标签体系不同的分类器：增加适配器、配置选择、固定配方与标签/分数声明，并通过现有分类值校验；Producer/Read 不按品牌写消费分支。若变成多标签独立分数、logit、问答或掩码等不同含义，应按当前扩展规则定义新具名值，不能冒充四类互斥概率或把必需信息塞入任意 JSON。

候选 A 的通用标签记录可承载当前模型，但分类分布关系和区域实例会依赖额外标签组约定。用户已选 B；不再重开 A/B 选型。

### D3. 输入、框和归属只说明实际检查的材料

Observation 归属于 Source Item，provenance.input_evidence_ref 指向该次真正检查的高清图或视频帧。框坐标使用该 Evidence 已定向图片的像素，原点左上，x 向右、y 向下，xyxy 边界，满足 `0 <= x1 < x2 <= width`、`0 <= y1 < y2 <= height`。输入尺寸与 Evidence 的已有尺寸证明一致，不用源文件尺寸代替。

640 原生整数 xywh 只作可逆的 `x2=x+w, y2=y+h` 转换；保留 native 已产生的裁框与整数化结果，不二次裁剪、修正颜色、改 NMS 或取同类最大分。无效坐标明确失败，不偷偷修正。展示可以缩放框，但必须使用可证明的输入到展示图转换。

首期每个模型在一个 Run 中只有一套有效配方。新 detector_identity 应包含模型内容与有效配方绑定，使现有 `name + detector_identity + input_evidence_ref` 唯一性足以区分新结果；不能用同一身份改后处理。实际 runtime 版本/设备另如实保留。历史身份原样读取，不重释旧 V1。

明确停用或未准备输入时，可从冻结配置记录所请求/停用的模型与配方身份，标明来源为 configuration；这不证明实际加载或执行，不编造 observed_at/actual_device。没有准备材料时不制造 Evidence 引用。可用/失败观测仍必须指向真实输入。角色为 Representative 不扩张检测覆盖范围。

### D4. 固定已选配方，避免生产移植改变行为

| 项目 | Freepik | NudeNet 640 |
| --- | --- | --- |
| 模型 | Freepik/nsfw_image_detector | notAI-tech/NudeNet/640m |
| revision | 15b85477e4fd2000db76ae9aae0f89a72f95e2e3 | nudenet-3.4.2/v3.4-weights；内容身份以 SHA-256 为准 |
| 权重 SHA-256 | 024a9d4818fae2656403bf626c9f8c9e7789c2da274749fbebb1060d8fdaa7ab | 04fe3d77980780c1f8297dc6d7f942fd5b3abe6942a188f742a85241e4f634eb |
| 执行 | MPS FP32，无 autocast，batch 4（尾批按实际输入数） | CPU FP32，batch 1 |
| 预处理 | 官方 448x448 bicubic squash、原生 mean/std；TimmWrapper/Timm transform | native OpenCV 解码/颜色处理，右侧/底部补黑方形，640px，1/255 |
| 后处理 | softmax，保留四类原始概率及已定义累计事件 | candidate=0.2，NMS score=0.25，IoU=0.45，class-agnostic，候选 argmax；无额外汇总 |

具体依赖、预处理参数、权重来源和证据哈希以 README 列出的 run.json 为工程依据。Freepik 不能直接套当前通用 AutoImageProcessor 路径；640 的库曾忽略 providers 参数，必须验证实际 CPU provider，并在必要时通过窄适配保证执行要求。保持已验收像素/后处理含义，不顺手修正 native 色彩行为或混入 320 classwise 诊断配方。

首期只发布以上经过选择的配方。配置中出现其他设备、精度、批量或处理方式时，明确校验其是否属于支持范围，不静默采用另一配方。尾批和必要的输入拆分不制造新模型身份；支持范围之外的优化另有一致性证据后再加入。

### D5. 逐模型配置及停用语义

沿用户与 Dataset config.toml 的层级，Dataset 的 sensitivity 表仍整体替换用户表；有效配置清单可读。拟议形状如下，路径只是未来安装配置示意，不是本轮写入请求：

~~~toml
[sensitivity]
enabled = true

[sensitivity.models.freepik]
enabled = true
profile = "freepik-ordinal448-mps-fp32-v1"
model_path = "/absolute/local-models/freepik-snapshot"
device = "mps"
precision = "float32"
batch_size = 4

[sensitivity.models.nudenet640]
enabled = true
profile = "nudenet640-native-cpu-fp32-v1"
model_path = "/absolute/local-models/640m.onnx"
device = "cpu"
precision = "float32"
batch_size = 1
~~~

总表省略/关闭为关闭；逐模型配置省略/关闭则该模型不参与。全部模型均关闭也是明确的空选择，不自动启用任何模型。启用项需有完整可解析的配方及本地资产位置；已知配方解析不加载推理库。未知模型、未知键、错误类型、与固定配方冲突的值是配置错误，不静默忽略。

**D5-disabled（本轮用户已明确确认）：** 停用后，新 Result 不纳入该模型的缓存输出；旧 Result 和缓存保留。重新启用时仍可复用有效 Work。不增加 cache-only 模式。未来改变此含义须同步当前合约、样例和验收。

新 Run 冻结有效选择；resume 用原快照，不把配置编辑混入原 Run。更换/停用已有模型或改变语义配方应创建后继 Run。旧四键配置不被默默改成 Freepik/640；执行前给明确迁移说明。旧配置错误不能连带阻止无执行需求的历史 Read，复用现有配置错误延迟到新执行边界的模式。

### D6. 成功、没有结果和故障不合并

| 情况 | Observation / Run 行为 |
| --- | --- |
| Freepik 返回完整四类；640 返回实例 | 各自 available；并列保留，不取跨模型最大值，不生成整体 sensitive/mild_sensitive |
| 640 成功执行后无框 | available，instances=[]；保留配方/输入及筛选限制，不用 missing 或 not_checked |
| 一个模型没有提供某类信息 | 不出现该类值；由 profile 声明能力范围，不推断为阴性 |
| 配置关闭 | not_checked + capability_disabled，指出对应模型/配方；不创建模型执行 attempt |
| 没有准备合适输入 | not_checked + evidence_not_prepared，保留实际准备缺口；不伪造输入 |
| 确定不适用 | not_applicable + 具体依据；不能用于吞掉未实现或缺依赖 |
| 有效已提交输出命中缓存 | 复用并标明原来源/时间；不加载模型，不伪造本次推理 |
| 需要新推理且固定本地权重/后端不可用 | Run 按既有 backend-unavailable 阻塞并说明恢复条件；保留已完成 Work，不发布本次“完成”Result |
| 可确定归属的一张图片读取/执行失败 | failed，保留真实输入和明确原因；其他成功成果保留，按已有局部失败规则交付限制 |
| 批量对应错误、协议/装配不变量违反、未知异常 | 直接暴露执行/Host 故障，保留有限诊断；不得伪装成坏源、无框、正常 paused/blocked |

模型预测分歧是证据，不等同于程序失败。Freepik 的原生等级与部位实例不一定回答同一命题；Plan 保留分歧并决定是否需要进一步调查。状态是执行事实，不增设一个虚假的 queued/partial 总状态。

### D7. 资源属于执行，不属于图片内容

调用方提供允许的设备/批量/并发和预算；适配器/配方在执行前声明支持范围、模型常驻与批次资源估计；现有资源调度器准入。实际设备、批量、耗时及已测资源进入已有执行诊断，不写成媒体内容属性。

采用已有成本证据作为初始估计：Freepik 进程物理内存峰值约 6.01 GiB，640 约 0.36 GiB。与 RSS、Metal allocation 的口径分别保留；这些数不能相加冒充全流程或全机峰值，也不是跨输入/跨机器硬上限。

分别配置 Freepik batch 4 和 640 batch 1，不再使用 embedding 的 model_batch_size。模型常驻内存在加载到释放期间必须有资源责任，不能只申请每批内存后让已加载模型长期失去计账。复用已有 scope/准入机制，首期以可证明的受限并发安排执行；不把当前执行顺序固定进公共合约。

可强制的线程/批量/并发上限与估计内存分开报告；不能用 min(需求, 容量) 截小申请来假装够用。容量不足是明确配置/准入条件，不能无限等待没有执行者的队列或自动换 CPU/模型。批次墙钟保留批次范围，不能除以批量后冒充逐图实测延迟。

### D8. 局部复用与历史读取

复用依赖包括实际输入内容/准备配方、模型权重和处理器身份、适配实现及影响结果的运行时、精度、预处理、后处理和输出语义。有效配置中的完整模型名单、纯展示规则、无语义影响的调度分组不成为所有模型的共同失效条件。

- 换 Freepik 只失效相关 Freepik 工作；640、metadata、图片/视频准备和 DINOv3 等无关有效成果继续复用。
- 同一输入的有效历史输出可直接复用，不以重新加载模型为前提；安装缺失只在需要新执行时成为后端缺口。
- 更改累计展示或 Plan 策略可利用已保存概率；更改 NMS 不能从已筛选框恢复被抑制候选。没有有效原始网络预测缓存时重跑该模型，不承诺后处理任意免推理修改。
- 封存数据包含解释值所需的公共来源、配方、定义和限制。Read/封存验证不导入或加载可选推理模型；删除模型包/权重不损坏旧结果读取。
- 旧 V1 labels/score/threshold/mild_threshold/sensitive/mild_sensitive 及 99/33 保留原义。缺框、缺实例数、缺实际输入或定义的历史记录以已有历史缺口语义说明，不补成空框或虚构成功，不把最大分摘要投影成完整实例。
- 新 Result 只投影本次范围内、有效且被选择的 Work，不混入旧 Result 的同名值作为新的默认事实。

### D9. 合约采用与工程落点

| 内容 | 已有扩展路径 / 必须改动 |
| --- | --- |
| 模型实现、算法和库替换 | 方法开放，但保留明确有效配方、来源、效果和失败 |
| basis/provenance/qualifications 的额外解释 | 沿已有扩展语义，不以开放 JSON 掩盖必需值 |
| 新的三个具名值、必需字段/单位/空值与唯一性 | 明确调整 Read prose/schema/属性义务和语义检查；当前 value 顶层是封闭的 detector/profile/labels |
| 独立模型选择、新配置键、缺口及完成条件 | 明确调整 Run 的四键配置和“两类均启用”义务；请求 action 不扩展为任意 producer 参数 |
| 新旧输出读取 | 单一 Read 路由，封存前结构/语义校验与纯历史投影一起验证；没有双写或第二份结果权威 |
| 安装配置与依赖 | 唯一 installation runbook 及其发布快照同改；doctor/有效配置/CLI/MCP 验证对应能力 |

代码优先落在现有 sensitivity.py、_orchestrator.py、_result_assembly.py、_result_sqlite.py、_read_projection.py 及 runtime/config.py、composition.py、doctor.py。模型实现可按真实职责拆成小模块，不预建通用 capability 平台。包内 schema/Skill references 仅从已采用的权威源同步。

## Risks / Trade-offs

| 风险 | 缓解与停止条件 |
| --- | --- |
| 预处理、native 颜色或 NMS 在移植时漂移 | 固定输入与配方做小规模数值/坐标对照；超出约定容差先定位，不改参考结果或重选模型 |
| 640 忽略请求 provider | 校验真实 ORT provider；不满足 CPU 要求即拒绝执行，不虚报后端 |
| Freepik 在开发环境可用但发布缺 Timm/兼容依赖 | 从已验证组合形成约束，在隔离 wheel/Host 路径证明，不仅测试模型类 |
| 已加载模型超出按批次计的资源 | 覆盖模型常驻寿命的资源责任及真实并发限制；估计与观察值不混同 |
| 只保留原生后处理结果，无法免推理重做任意 NMS | 明确边界；原始张量不是新公共产物或默认长期保留义务 |
| 属性变大、历史分支或未检查身份导致遗漏 | 检查逐模型/逐输入唯一性、完整页与现有单项超限语义；不截断实例或制造重复普通属性 |
| 停用含义与历史保留 | 本轮已接受停用排除新结果；以关闭/重启用和旧字节不变验证，不以清缓存实现停用 |

## Migration Plan

1. 规划阶段已完成文档和合成样例校验并等待后续指示；本轮已收到明确开发授权，实际结果见 acceptance 的实施记录。
2. 获准开始后，先完成 handoff/运行失败语义的具体审阅，采用准确的 Run/Read 合约变更并同步机器定义与例子，再按合约开发。B 方向批准不冒充精确交换值已验收。
3. 更新模型端口、固定配方、配置与诊断、独立执行及 Result/Read；同时保留旧 Result 的纯读取路径。源媒体只读，业务 Dataset 不作为开发输出位置。
4. 旧配置显式迁移，不覆盖原文件或静默换模型。日常升级前清点未终结 Run：由原版本完成/取消，或证明新版本可按其原快照继续；不把旧快照改成新模型来恢复。若存在无法安全继续的原 Run，保留原安装与状态并停止切换。
5. 若私有快照/存储格式确需变化，沿已有 versioning 机制执行受验证、可回滚的迁移，禁止重建或改写封存结果。旧写入者对新状态必须明确拒绝；不能由相同应用版本号猜测兼容。
6. 按 [安装 runbook](../../../readme/installation.md)固定源码/依赖/wheel，完成隔离安装检查及有界模型一致性/交付验证，记录门槛和证据。此步仍不代表获准切换日常 Host。
7. 回填既有迁移台账的真实实现、消费者、安装门槛及 preserved/intentionally_changed/regression/not_comparable 判断；日常切换与回滚只在相应授权下执行。

## Open Questions

B、D5-disabled、handoff 含义和失败边界已获本轮用户明确授权，没有等待开发许可的未决项。
工程选择已由当前合约、实现与隔离验收记录承载。只有证据要求改变既定模型配方、业务含义、
外部效果或历史数据保证时，才重新提出具体问题。日常部署仍属于另一次授权。
