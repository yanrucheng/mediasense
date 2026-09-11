# 本地模型评测

这是本仓库唯一的本地模型评测 runbook。目的只有三个：人工查看 embedding 在业务
分组、组代表和视频关键帧选择中的效果，记录峰值进程内存，记录真实编码速度。
它不选生产模型，不修改阶段合约，不提供质量评分或综合排名。

共用入口是 `eval/shared/model_evaluation.py`；每次评测的配置、紧凑摘要和
人工结论位于 `eval/sessions/<时间-名称>/`。第一份工作的准确状态见
[ChineseCLIP 香港基线会话](../eval/sessions/260910-0048-chineseclip-hk-baseline/report.md)。
每次会话同时留下可供工程复用的技术依据，入口和收尾要求见
[工程参考资产与收尾](#工程参考资产与收尾)。

## 本轮调研收官：2 万张照片的质量与效率取舍

2026-09-11，用户认可下面的比较作为本轮模型调研的收官结论，并确认 **2 万张照片是常见业务规模**。
用户最终首选：**DINOv3 方案（本轮已验收的 ViT-B/16 384px），兼顾效率与实际效果，
在用户人工检验中具有一流的肉眼效果。** DINOv3 已取得大部分效率收益；用户更看重它的实际质量，
不以 MobileCLIP2-S2 额外节省的几分钟作为最终选择依据。
用户补充原话：“我最终还是最喜欢dino v3 的方案它综合了效率和实际效果，在人工检验上拥有一流的肉眼效果。”
这是本轮评测的取舍结论，不代表已替换生产模型或确定生产默认分组粒度。

各取目前实际测过且通过正确性检查的最快路线。以下“2 万张”指 **2 万张均需各编码一次**，
不是源媒体总数经业务代表采样后的输入数；估算公式为 `20,000 ÷ 实测输入/秒`，使用未取整的吞吐计算。
实测来自同一台 Apple M5 Pro／48 GiB、同一冻结的 366 个图片／帧输入。表中数据链接到保留的实测摘要。

| 模型与输入尺寸 | 运行条件 | 366 输入实测编码 | 实测吞吐 | 2 万张预计编码时间 |
| --- | --- | ---: | ---: | ---: |
| [ChineseCLIP Huge · 224（原始基线）](../eval/sessions/260910-1330-chineseclip-business-baseline/metrics/baseline.json) | CPU FP32，batch 4 | 155.29 s | 2.36 张/s | **2小时21分26秒** |
| [SigLIP 2 So400m · 512](../eval/sessions/260910-1717-siglip2-so400m-512/metrics/coreml-batch1.json) | Core ML FP16，batch 1 | 21.76 s | 16.82 张/s | **19分49秒** |
| [DINOv3 ViT-B/16 · 384](../eval/sessions/260911-0953-dinov3-resolution-384/metrics/384-coreml-batch1.json) | Core ML 混合精度，batch 1 | 9.34 s | 39.21 张/s | **8分30秒** |
| [MobileCLIP2-S2 · 256](../eval/sessions/260911-1027-mobileclip2-s2/metrics/mps-fp32.json) | MPS FP32，batch 4 | 5.42 s | 67.53 张/s | **4分56秒** |

按此规模，ChineseCLIP → SigLIP 2 约省 **2小时2分钟**，SigLIP 2 → DINOv3 384 再省 **11分19秒**，
DINOv3 384 → MobileCLIP2-S2 再省 **3分34秒**。最后一步吞吐约为 1.72 倍、编码时间约少 42%，
但用户比较约百组预览后认为 MobileCLIP2-S2 质量有所下降，以“DINOv3 95 分、MobileCLIP2 87–88 分”
表达主观差距；这些不是标准化 benchmark 分数。DINOv3 384 已明确获评“挺好的，达到我的要求”。
人工反馈与技术证据分别保留在 [DINOv3 384 报告](../eval/sessions/260911-0953-dinov3-resolution-384/report.md)
和 [MobileCLIP2-S2 报告](../eval/sessions/260911-1027-mobileclip2-s2/report.md)。

这里比较的是不同模型、输入分辨率、精度、运行时和批量的**整体方案**，不是控制这些变量后的模型速度排名，
也不说明 ChineseCLIP 的其他未测运行时只能达到该速度。DINOv3 混合图为 FP16 卷积／MLP、FP32 attention／归一化／残差／RoPE；
MobileCLIP2 的 FP16 全量检查未通过，因此只列有效 FP32 路线。

预计时间包含逐输入读取、RGB 解码、预处理、预测、结果取回和设备同步，加载另加约 **7–27 秒／次**；
不包含源遍历、校验、原视频抽帧、runner L2、向量写盘、分类和 HTML，不能当作完整整理流程耗时。
这是基于真实 366 输入实测的线性外推，**没有执行 2 万张评测或新增推理成绩**。
原素材是代理图片与稀疏视频帧；原图尺寸、存储介质、系统负载、缓存和持续运行状态都会影响实际耗时。
若业务只编码其中的代表图片，应代入实际编码输入数。旧基线、向量、两档粒度与人工验收全部保留。

## 已确认方向与实施状态

用户已确认主评测复用当前 MediaSense 的时序视觉压缩与代表选择逻辑。
`build_adaptive_groups(content_based_boundaries=True)` 负责业务分组，
`select_embedding_representative` 负责组代表及视频关键帧选择；可从现有
[compression 入口](../src/mediasense/precheck/compression.py)复用。
算法、参数和业务输入在一轮模型比较中固定，长期可替换。

首份[业务基线](../eval/sessions/260910-1330-chineseclip-business-baseline/report.md)已完成真实执行，
可打开[分类与代表预览](../eval/sessions/260910-1330-chineseclip-business-baseline/outputs/baseline/preview/index.html)。
2,134 个源媒体、167 个业务候选、117 个组；366 个图片／帧成功编码。
用户于 2026-09-10 确认当前展示效果可接受；抽帧与关键帧排序限制继续保留。
共用入口已接入业务 prepare／run／preview。旧会话保留为独立编码证据，其旧确认状态不影响业务配置。

HTML 与缩略图由共用 `render_business` 自动生成；每次评测复用同一展示逻辑，
不需要 Agent 逐次编写页面。Agent 负责配置、必要的模型适配及运行核对，用户负责质量判断。
生成时页面记录待验收状态，后续人工结论统一写入会话报告。

[SigLIP 2 So400m-512 候选会话](../eval/sessions/260910-1717-siglip2-so400m-512/report.md)
复用上述业务基线的完整输入和分类参数，包含 MPS FP16、Core ML FP16 的真实结果、
正确性验证和复现命令。Core ML 本次可用路径限定为单张预测；其原生 batch 2／4
未通过数值检查，固定 batch 4 的针对性转换也未解决。为比较运行时，另有相同
batch 1 的 MPS 对照。用户于 2026-09-10 确认当前展示达到预期，与 ChineseCLIP 基线
没有感到显著差异，比较结论为相当；最新人工验收以会话报告为准，生成时的页面与指标保留原快照。

该会话的公开模型下载和依赖安装已由用户明确授权，均在独立评测环境中进行。
日常环境未升级，编码继续强制离线。候选只添加 eval 薄适配器，不替换生产模型。

[DINOv3 ViT-B/16 512px 候选会话](../eval/sessions/260910-2212-dinov3-vitb16-512/report.md)
已完成同一冻结输入的 MPS batch 4／1 与 Core ML 固定单张评测，技术检查通过。
后继[103 组参数适配](../eval/sessions/260911-0031-dinov3-threshold-calibration/report.md)
已于 2026-09-11 获得人工认可，用户认为效果与效能相对此前方案“显著更好”；
用户同时认为原 157 组很可能更适合作为 Embedding 聚合结果，两种粒度均保留。
103 组复用原向量，仅将视觉距离尺度改为 0.85，没有新的推理性能实测，也未确定生产默认粒度。
最新人工原话与用途判断以该后继报告为准。官方 Hugging Face 权重受访问限制，本轮采用用户列出的 timm
同源发布并固定版本；取最终 LayerNorm 后的 768 维 CLS，采用官方示例的 512px
方形处理配方。原生 FP16 attention 溢出，FP16 残差也未通过数值检查；有效路线为
FP16 卷积／MLP、FP32 attention／归一化／残差／RoPE。Core ML 可变 batch 1／2／4
在设备编译阶段中止，其性能与正确性未获确认。三次有效运行均为 157 个组；
与 SigLIP 2 的差异、精度处理、转换限制和复现命令以会话报告及配置为准。

用户已接受 512px、尺度 0.85 下 MPS 103／Core ML 104 组的微小差异：仅一个
56 成员组拆为 1＋55，其余 102 组成员和代表相同；不再为一致组数调整实现或阈值。
此决定不豁免非有限值、输入错位等实质数值错误。

[DINOv3 512→384 会话](../eval/sessions/260911-0953-dinov3-resolution-384/report.md)
已完成 384 CPU／MPS／Core ML 正确性检查、两条运行时全量编码及同口径 512 对照。
只改输入尺寸，权重和 85,641,216 个参数不变。384 两条路线均得到 156／99 组
（尺度 0.311／0.85）。用户于 2026-09-11 确认“挺好的，达到我的要求”，384 已人工验收；
两档及 512 原结果和人工认可保留，未确定生产默认粒度。
该会话也保存 MobileCLIP2-S2 的有界资料核对，未接入或运行该模型。

后继 [MobileCLIP2-S2 会话](../eval/sessions/260911-1027-mobileclip2-s2/report.md)已完成实际接入：
官方固定权重、OpenCLIP/timm 实现、原生 256px 与 512 维学习投影；视觉融合后 35,702,992 参数。
MPS FP32 batch 4／Core ML FP32 固定单张通过完整 CPU 参考，编码分别为 5.42／6.14 s，
尺度 0.311／0.85 下均为 144／19 组，**待人工验收**。原 FP16 小样本通过，但全量超限，
失败证据和速度保留，不能作为有效路线推荐。不同家族的同一距离尺度不保证相同粒度，未为匹配组数调参。
用户随后认为 19 组过粗，授权复用向量调整粒度；尺度 0.55 的 [99 组预览](../eval/sessions/260911-1027-mobileclip2-s2/outputs/mps-fp32-granularity/preview/index.html)已生成供人工查看，
无新编码或性能实测，原 144／19 组保留。用户查看 99 组后认为质量略差于 DINOv3，
以 95 对 87–88 分作主观比较；此为人工反馈，非标准化得分，也未授权替换生产模型。
读取／预处理与加载开销已成为重要成本；Core ML 加载＋366 输入编码与 DINOv3-384 接近，
不只依据编码秒数宣布整体效率提升。生产默认模型和粒度仍未确定。

## 既有编码实验的素材与前置条件

先读[fixture 描述](../eval/fixtures/ai-album-hk-representative-v1.yaml)，再读实际包内
`README.md` 和 `docs/RESEARCH-AND-HANDOFF.zh-CN.md`，运行该包的 `scripts/verify.zsh`。
原媒体和包只读；新输出必须在包外。

本机候选包核实为 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1`。
描述文件中的 `Datasets/mediasense/fixtures/` 路径目前不存在。Downloads 包的
固定清单内文件完整，但被加入了后续测试副本等内容，导致总大小校验失败。
本次按原 SHA256SUMS 重建的干净副本是：

```text
/private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1
```

该副本已通过完整 verifier：10,608 个文件、1,759,421,497 bytes。它仍是原有
fixture 版本，不包含新增文件。不要清理原包来伪造其完整性，也不要修改 fixture
描述中的校验值。`/private/tmp` 不是长期备份；丢失时从原包按清单重建。

编码只读取 media-manifest 中的 `path`、`media_type`、`derived_sha256`，共
2,134 个媒体路径。旧代表、bundle、metadata 缓存、标题、分类目录、报告和向量
都不参与输入。源清单和每张实际输入的完整 SHA-256 在准备时及编码前后核对。
额外 GPX、RAW fixture 不在本次清单内。

既有编码实验使用实际解码帧中最接近 `duration × [0.1, 0.5, 0.9]` 的帧，距离相同时取较早帧。
固定帧序号后，由 FFmpeg 按序号抽取 RGB24 PNG，不旋转、不缩放。记录每一位置的
帧序号、PTS、PNG 校验值；短视频落在同一帧的多个位置保留为独立输入，并实际分别编码。
本次有 4 个重复位置。损坏视频保留三个失败位置，不能从总数中消失。

图片直接使用包内 JPEG，保持现有编码器的 Pillow RGB 转换，不额外转置 EXIF。
分类排序时间直接从图片 EXIF、视频 creation_time 与帧 PTS 读取；无可用字段时
明确退回文件 mtime。这些规则和 FFmpeg/ffprobe 版本都固定在配置中。
素材是缩小图片与稀疏视频代理，本次结果不代表原始全码流的解码速度或画质。

业务基线已对齐实际使用的 metadata、初始分组、rendition 和抽帧规则。上述全量 JPEG
及 10%／50%／90% PNG 不能直接称为产品输入。新配方及其指纹在后继评测会话中固定，
旧配置与旧实测保留供追溯。

本次复用已安装环境 `/Users/chengyanru/.local/share/uv/tools/mediasense/bin/python`，
不使用正在改动的源码版运行时。它对应 Python 3.13.5、PyTorch 2.13.0 和
Transformers 4.57.6。权重、处理器文件和底层编码器均固定 SHA-256，完整配置在
[config.json](../eval/sessions/260910-0048-chineseclip-hk-baseline/config.json)。
用户级 embedding 配置目前为空；本次沿用最近一次实际安装验证的 CPU / batch 4
配置，并把计算限制为 2 个 CPU 线程、nice 10。运行时会检查实际环境，差异直接报错。

不要自动下载权重、安装新依赖或升级日常环境。runner 强制 Hugging Face 离线模式，
现有适配器从本地固定 snapshot 加载。不存在可用依赖或权重时，记录缺口并停止。

## 既有编码实验的可执行命令

以下命令的工作目录都是 `/Users/chengyanru/repos/personal/mediasense`。
输出目录和摘要文件必须是新路径，存在时拒绝覆盖。

只在干净副本丢失时重建；它复用现有 `eval/shared/prepare_input.py` 的校验复制逻辑：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py stage-fixture \
  --config eval/sessions/260910-0048-chineseclip-hk-baseline/config.json \
  --output /private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1
rtk proxy /private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1/scripts/verify.zsh
```

首次准备图片清单和视频帧；已有 `outputs/prepared/inputs.json` 可复用，编码仍会重新执行：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py prepare \
  --config eval/sessions/260910-0048-chineseclip-hk-baseline/config.json \
  --output eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/prepared
```

本次输入指纹已写入配置。首次建立新素材配方时，核对 prepare 的清单、失败和指纹后，
把真实 `input_fingerprint` 写入该会话的 `expected_input_fingerprint`。
复用基线素材的候选必须保持同一指纹；不要通过改掉指纹掩盖输入变化。

原次实验实际运行了同一入口的 `encode` 动作，保存真实编码结果。
以下为原次命令；其输出已经存在，重新运行时需要换成新的输出目录：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py encode \
  --config eval/sessions/260910-0048-chineseclip-hk-baseline/config.json \
  --inputs eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/baseline
```

旧会话仅用于复现原次全量编码实验；业务评测使用下节的新配置。

`preview` 只读取已有结果，不测推理速度。调试业务分组时，只有模型、权重、预处理、
归一化和实际输入字节都一致的向量才可复用，并记录来源。新的性能基线必须重新执行
完整的业务编码输入集；不以缓存命中、旧全量实测或少量补算外推速度与峰值内存。
失败或中断保留当时的已完成行、未编码行和失败原因；新速度测量从新输出目录开始。

业务分组需要调参时，可用 `preview --encoding <原编码目录> --output <新目录> --summary <新摘要>`
复用已完成编码。入口核对编码身份、输入指纹及向量／行记录校验值，再调用相同业务函数和 HTML 生成器。
新摘要记录 `encoding_reuse.newly_encoded = 0`、`performance = null`；原编码性能单列于
`source_encoding_performance`，页面明确标注“原编码实测，非本次测量”。原向量和原预览不覆盖。
改变分类参数时仍按下文要求建立同参数比较参照，不绕过 `baseline_ref` 检查。
[DINOv3 103 组会话](../eval/sessions/260911-0031-dinov3-threshold-calibration/report.md#复现-103-组)
保留实际配置、复现命令和工程经验。分组粒度按用途评估；人工认可的一种粒度不会自动淘汰另一种聚合用途。

## 业务基线的复现与查看

所有命令在仓库根目录执行。当前使用已安装 MediaSense 0.9.0、Python 3.13.5，
ChineseCLIP 权重与编码器仍为原固定版本；业务源码与依赖指纹写在新配置中。
`prepare` 直接调用现有 Accounting、Metadata、Bundle、ImageRendition、VideoProbe／Frame
producers 和生产视觉需求选择函数。它只执行本地准备，不启动完整 PreCheck Run／Geo／Plan。
业务分组调用 `build_adaptive_groups`，视频关键帧调用 `select_embedding_representative`。

已有 `outputs/prepared/inputs.json` 可复用；需要从头准备时使用新目录：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py prepare \
  --config eval/sessions/260910-1330-chineseclip-business-baseline/config.json \
  --output eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared-repeat-01
```

新准备结果须与配置中的 `expected_input_fingerprint` 相符；不改指纹掩盖差异。
模型速度复现始终重新编码完整业务输入集：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-1330-chineseclip-business-baseline/config.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-1330-chineseclip-business-baseline/outputs/repeat-01 \
  --summary eval/sessions/260910-1330-chineseclip-business-baseline/metrics/repeat-01.json
```

打开新输出的 `preview/index.html` 即可。再次运行请换 `repeat-02` 等新路径。
`encode` 可只编码，随后对同一输出使用 `preview --config ... --output ... --summary ...`；
preview 要求其 `preview/` 与摘要路径尚不存在，引用已保留的编码性能，不产生新速度数据。
所有配置路径相对于仓库根目录；准备清单内保留本地路径，搬迁后重新 prepare 并验证指纹。

接入候选时，在新的 `eval/sessions/<时间-候选名>/` 配置中复用相同 `inputs`、
`expected_input_fingerprint` 和 `classification`，仅替换模型／推理运行时及其固定版本，
将 `baseline_ref` 设为 `eval/sessions/260910-1330-chineseclip-business-baseline/metrics/baseline.json`。
复用同一已准备输入运行上述 run；业务指纹不同会拒绝比较。同模型框架变更也记录为新候选。

本次有 184 次视频抽帧失败和 1 次坏视频探测失败，均在页面中保留；不可把失败帧算进吞吐。
现存 181 个可用视频各只有 1 或 2 帧（95／86 个视频），两帧时相似度对称打平，
因此这份素材不能证明关键帧排序质量。后续若修复产品抽帧、增加采样或换素材，应冻结
新输入配方并重跑原模型基线；本轮不在 eval 中偷偷修复或代换生产算法。
实际帧时间仅记录 producer 的请求 seek 时间；该 producer 未暴露解码 PTS。

## 业务算法与比较边界

主评测沿用[现有时序视觉分组](../src/mediasense/precheck/_compression_strategy.py)：
固定初始素材分组及来源关系，按时间排列其候选代表，结合日期、时间间隔、位置和
余弦距离切分；与组首候选的视觉比较用于限制连续相似造成的漂移。生成组代表、
边界、差异较大样本和相应限制，供人展开核对。视频先在该视频的固定候选帧内选代表帧，
再按业务路径参与素材分组；不能把三帧当作三个源媒体增加权重。

业务代码是算法实现的权威来源；评测只做最薄的输入、配置和展示适配。复用时固定
实际导入的代码版本与有效参数，不照抄一份会独立演化的业务算法。
分组阈值、时间与位置尺度、代表选择比例及比较预算是本轮配置，不是永久标准。
预览树展示“组 → 源素材／初始分组 → 视频候选帧”等实际关系，不冒称完整凝聚式层次聚类树。

AI Album c90 的 `LinearHierarchicalCluster` 是历史实现参考，其独立候选移植位于
[`model_evaluation_hierarchy.py`](../eval/shared/model_evaluation_hierarchy.py)。它不是本轮主算法，
不沿用“每张图片／帧权重 1，再以最小权重 20 合并”的评测方案；不以旧名称或
73 个历史终端组为正确答案，也不需要新增一条历史算法对照流水线。

候选与基线必须具有相同的源清单、业务候选图片／帧、非模型 metadata、初始分组、
下游算法及参数。选中的关键帧、组代表和最终分组是模型影响的结果，允许不同，
不能预先固定成基线答案。候选模型可有自己的处理器，其版本与预处理进入向量身份。

候选配置的 `baseline_ref` 指向可比业务基线的 `metrics/*.json`。
共用入口须核对输入与业务配方指纹，差异明确报错。改变采样、排序、分组参数或算法时，
先在新配方下生成现有模型基线，再比较候选。固定当前阈值的比较说明直接接入当前
业务的效果，不证明每个模型都已在各自最佳阈值下发挥能力。

## 最小模型适配约定

每个候选复用同一 runner，通过 `model.adapter = 模块:工厂类` 选择一个薄适配器，
不复制整套评测脚本，不引入注册中心、服务、Skill 或公共 Tool。
现有适配器包装已安装的 `ImageEmbeddingEncoder` / `ChineseCLIPEncoder`。

- `load()` 加载确切本地模型；`identity` 与 `description` 声明模型/权重、编码器版本、
  实际预处理、维度、精度、设备和归一化。适配器自身及底层编码器的代码版本必须可追溯。
- `encode_images(paths)` 严格按输入顺序返回已经取回的普通数值向量；可包装现有
  `encode_image`，也可使用其真批量能力。不要向 runner 返回 Tensor、MLX array 等框架对象。
- `synchronize()` 等待真实设备工作完成；CPU 为同步操作。GPU 适配器必须实现实际等待。
- 输出行数错误立即拒绝分配；维度错误、零向量、NaN、Infinity 明确失败。
  本配方将有效向量 L2 归一化，并以 little-endian float32 保存。

runner 的模型身份包含实际模型、权重/处理器文件、预处理、运行时及归一化。
相同维度不是相同向量空间。每次编码独立存储，不存在可命中的向量缓存；可复用的只有
经过指纹校验的固定输入与帧。增加新适配器时记录其实际版本和预处理，并验证单张与
批量的输入对应关系。不要为了接入评测去更改 PreCheck/Plan/Apply 合约。

## 工程参考资产与收尾

评测交付应让后续工程人员能够复现有效路线、找到可复用实现，并判断还缺哪些
生产接入证据。每个会话的 `report.md` 是该候选的工程参考入口，链接实际代码、
配置和证据；本 runbook 维护共同要求。模型身份与参数以配置为准，实测以保留的
运行记录为准，报告解释其结论和限制。原始记录保留执行时状态，后续人工结论记在报告。

会话收尾在现有报告中交代以下适用信息，已有内容可直接链接：

| 后续工程需要知道什么 | 应保留的依据 |
| --- | --- |
| 怎样正确编码 | 实际使用的适配实现或既有编码器入口；预处理、特征提取／池化、输出维度、归一化和存储精度，以及分别由谁执行 |
| 哪些运行条件已验证 | 权重／处理器身份、依赖版本、实际设备与精度、有效批量范围、同步和回退行为；转换过模型时保留转换方法及生成文件身份 |
| 结论能支持到哪里 | 正确性和业务结果、人工结论、性能及统计范围、已失败路线、未测项和适用限制；可复现的失败也供工程避坑 |
| 从哪里恢复和重跑 | 代码、配置、输入与二进制资产的位置／来源、校验方式和可执行命令；标明临时路径、保留状态及重建条件 |
| 接入生产还缺什么 | 可复用部分、评测专用部分，以及现有生产端口、配置、模型获取、依赖、缓存失效、运行失败语义或安装入口中尚未验证的相关环节 |

以上固定的是交付信息的责任，不要求每次新增适配器、转换脚本或独立交接文件。
沿用已有 `report.md`、配置、`metrics/` 和共用代码即可；只有实际需要的实验方法
才留下相应实现。新的框架、模型和验证方法可替换现有方法，实测版本和失败范围
描述该次证据，不自动成为永久的生产限制。

评测负责人交代可复用依据与证据边界；工程接入负责人负责把所选实现接到现有
生产边界，完成相关安装与集成验证，并按既有迁移台账记录接通状态。
人工质量验收和 eval 可运行，不等于生产模型已接通或获准替换。生产代码不反向
依赖 `eval/`；工程应提取必要实现并沿用已有生产配置、身份和工作状态机制。

收尾核对代码、配置、报告和紧凑证据的版本控制状态：明确哪些已提交、哪些仍为
工作区文件，未提交时如实交代尚未完成版本化保存。权重、编译模型和批量输出继续
遵守下节的 Git 排除规则；临时目录中的二进制不能代替可持久保存的来源与重建方法。
只处理本会话改动，保留其他线程的工作。

当前 [SigLIP 2 会话的工程参考入口](../eval/sessions/260910-1717-siglip2-so400m-512/report.md#工程参考资产与接入边界)
展示了已有资产、可用运行条件和生产接入缺口。

## 性能口径与人工验收

模型加载时间包含框架/适配器导入、模型与处理器加载、设备转移和同步。文件校验在
预检中进行，不混入加载时间。不清空系统文件缓存；校验会读取输入与权重，
因此加载和读取时间不是冷磁盘基准。

编码时间累加真实批次的墙钟时间，包含图片/已抽取帧读取、RGB 解码、模型预处理、
计算、结果取回 CPU 和设备同步；包含首批冷启动，不做不计时 warmup。
不含原视频抽帧、源校验、runner 的 L2 归一化、向量写盘、分类和预览。
吞吐为成功编码的图片/帧输入数除以该时间；失败运行不发布可比较吞吐。
新运行的 `first_batch_seconds` 单列首批时间，同时仍计入编码总时间；它包含首批
读取与计算，不能单独解释为编译耗时。Core ML 转换、包编译及缓存条件另记于会话。

峰值内存采用内核 `resource.getrusage(RUSAGE_SELF).ru_maxrss`，macOS 为 bytes，
汇总时换算 GiB。它是编码进程从启动到编码完成的 RSS 高水位，包含加载，
不包含子进程、独立抽帧进程或系统文件缓存，不是全机峰值。GPU 分配未另报；
未来若补充可靠的 GPU 指标，必须单列，不能与统一内存 RSS 相加。
Core ML 独立系统服务的内存也不在此 RSS 内；没有额外可靠测量时，不能据此声称
整个方案节省了相应内存，统一内存峰值应标为未知。

DINOv3 的 `runtime.stage_timing = true` 可在原编码总时间内单列读取／RGB 解码、
resize／归一化／组 batch，以及预测／结果取回／同步；适配器仅返回普通秒数，
runner 汇总并将剩余时间记为开销，拒绝阶段重叠或无效计时。MPS 在取回后额外同步一次，
Core ML predict 同步返回；这些成本均计入总时间。阶段数据是墙钟归因，不是纯 GPU kernel
时间。比较分辨率时用同配置开关和同步方式的新实测，不改写已有成绩。

打开业务输出的 `preview/index.html`，无需服务或网络。组中标出实际
选中的代表、边界和差异较大的样本，可展开源成员及视频全部候选帧，再打开图片或源视频。
源媒体数、编码输入数、分组数、失败和未处理原因分别展示。当前已有的 `input-preview`
仍只供核对旧编码输入。
技术完成与人工质量分别记录，成功编码不能自动写为分类验收通过。

在每个会话的 `report.md` 填写：人工验收日期、比较对象、
“更好／相当／更差／待定”和简短意见。初始结论为“待人工验收”，比较结论为“待定”。
无需新标注体系或自动分数。

Git 保存共用代码、配置、report 和必要的小型 `metrics/*.json`。
`outputs/` 中的图片、帧、向量、逐项记录、HTML、缓存和日志由现有 `.gitignore` 排除；
原始媒体与权重继续留在外部。不要把大量生成图片或旧模型输出加入 Git。

修改共用代码后，只运行相称的验证：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python -m unittest discover -s eval/shared -p 'test_model_evaluation*.py' -v
rtk proxy .venv/bin/ruff check eval/shared/model_evaluation*.py eval/shared/test_model_evaluation*.py
```
