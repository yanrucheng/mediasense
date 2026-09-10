# 本地模型评测

这是本仓库唯一的本地模型评测 runbook。目的只有三个：人工查看 embedding 在业务
分组、组代表和视频关键帧选择中的效果，记录峰值进程内存，记录真实编码速度。
它不选生产模型，不修改阶段合约，不提供质量评分或综合排名。

共用入口是 `eval/shared/model_evaluation.py`；每次评测的配置、紧凑摘要和
人工结论位于 `eval/sessions/<时间-名称>/`。第一份工作的准确状态见
[ChineseCLIP 香港基线会话](../eval/sessions/260910-0048-chineseclip-hk-baseline/report.md)。

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

## 性能口径与人工验收

模型加载时间包含框架/适配器导入、模型与处理器加载、设备转移和同步。文件校验在
预检中进行，不混入加载时间。不清空系统文件缓存；校验会读取输入与权重，
因此加载和读取时间不是冷磁盘基准。

编码时间累加真实批次的墙钟时间，包含图片/已抽取帧读取、RGB 解码、模型预处理、
计算、结果取回 CPU 和设备同步；包含首批冷启动，不做不计时 warmup。
不含原视频抽帧、源校验、runner 的 L2 归一化、向量写盘、分类和预览。
吞吐为成功编码的图片/帧输入数除以该时间；失败运行不发布可比较吞吐。

峰值内存采用内核 `resource.getrusage(RUSAGE_SELF).ru_maxrss`，macOS 为 bytes，
汇总时换算 GiB。它是编码进程从启动到编码完成的 RSS 高水位，包含加载，
不包含子进程、独立抽帧进程或系统文件缓存，不是全机峰值。GPU 分配未另报；
未来若补充可靠的 GPU 指标，必须单列，不能与统一内存 RSS 相加。

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
