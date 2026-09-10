# 本地模型评测

这是本仓库唯一的本地模型评测 runbook。目的只有三个：人工看 Hierarchical
分类效果、看峰值进程内存、看真实编码速度。它不选生产模型，不修改阶段合约，
不提供质量评分或综合排名。

共用入口是 `eval/shared/model_evaluation.py`；每次评测的配置、紧凑摘要和
人工结论位于 `eval/sessions/<时间-名称>/`。第一份工作的准确状态见
[ChineseCLIP 香港基线会话](../eval/sessions/260910-0048-chineseclip-hk-baseline/report.md)。

## 素材与前置条件

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

视频使用实际解码帧中最接近 `duration × [0.1, 0.5, 0.9]` 的帧，距离相同时取较早帧。
固定帧序号后，由 FFmpeg 按序号抽取 RGB24 PNG，不旋转、不缩放。记录每一位置的
帧序号、PTS、PNG 校验值；短视频落在同一帧的多个位置保留为独立输入，并实际分别编码。
本次有 4 个重复位置。损坏视频保留三个失败位置，不能从总数中消失。

图片直接使用包内 JPEG，保持现有编码器的 Pillow RGB 转换，不额外转置 EXIF。
分类排序时间直接从图片 EXIF、视频 creation_time 与帧 PTS 读取；无可用字段时
明确退回文件 mtime。这些规则和 FFmpeg/ffprobe 版本都固定在配置中。
素材是缩小图片与稀疏视频代理，本次结果不代表原始全码流的解码速度或画质。

本次复用已安装环境 `/Users/chengyanru/.local/share/uv/tools/mediasense/bin/python`，
不使用正在改动的源码版运行时。它对应 Python 3.13.5、PyTorch 2.13.0 和
Transformers 4.57.6。权重、处理器文件和底层编码器均固定 SHA-256，完整配置在
[config.json](../eval/sessions/260910-0048-chineseclip-hk-baseline/config.json)。
用户级 embedding 配置目前为空；本次沿用最近一次实际安装验证的 CPU / batch 4
配置，并把计算限制为 2 个 CPU 线程、nice 10。运行时会检查实际环境，差异直接报错。

不要自动下载权重、安装新依赖或升级日常环境。runner 强制 Hugging Face 离线模式，
现有适配器从本地固定 snapshot 加载。不存在可用依赖或权重时，记录缺口并停止。

## 可执行命令

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

日常复现使用一个 `run` 命令完成重新编码、固定分类和预览。它要求会话中的
Hierarchical 选择已经得到用户确认；本次尚未确认时会明确拒绝分类，不自动选算法：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-0048-chineseclip-hk-baseline/config.json \
  --inputs eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/repeat-01 \
  --summary eval/sessions/260910-0048-chineseclip-hk-baseline/metrics/repeat-01.json
```

本次等待算法确认时，实际先运行了同一入口的 `encode` 动作，保存真实编码结果：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py encode \
  --config eval/sessions/260910-0048-chineseclip-hk-baseline/config.json \
  --inputs eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/baseline
```

确认分类选择后，可以用 `preview` 完成本次流程，引用已经实际执行的编码指标：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py preview \
  --config eval/sessions/260910-0048-chineseclip-hk-baseline/config.json \
  --output eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/baseline \
  --summary eval/sessions/260910-0048-chineseclip-hk-baseline/metrics/baseline.json
```

`preview` 不测推理速度；它校验原始编码配置、向量字节和行映射，引用该编码进程的
`encoding.json`。更换模型必须重新 `run`，不能拿 preview 的缓存读取冒充新推理。
失败或中断保留当时的已完成行、未编码行和失败原因；新速度测量从新输出目录开始。

## Hierarchical 的确切含义与当前缺口

MediaSense 当前没有该算法入口。历史 AI Album 的唯一对应类是
`LinearHierarchicalCluster`，来源为 commit
`c90aa8f04fd0d3348284e0ad19e18462987b1af2` 的 `src/cluster/linear.py`。
其内容层调用参数来自 `src/content_analysis/clustering_engine.py` 与 CLI 默认值
`src/argparser.py`。独立候选移植在
[`model_evaluation_hierarchy.py`](../eval/shared/model_evaluation_hierarchy.py)，运行时不依赖旧仓库。

候选方法先按固定时间和路径排序，只比较相邻输入的 `1 - cosine_similarity`，
距离 `>= 0.311` 时切分；总权重 `<= 20` 则停止。相邻分区权重和严格 `< 20`
时合并，所以 20 不是最终组的最小大小。只得到一个分区时也提前停止，不再进入下一阈值。
这是线性层级切分，不是凝聚式聚类，没有 linkage 参数。

本次建议只移植视觉层，每张图片或帧权重为 1；不采用旧 bundle 权重、日期/GPS 分层
或语义命名。单个阈值只产生一层视觉分组，不能冒充完整的多级 dendrogram。
该选择仍待用户确认，配置保持 `classification.status = awaiting_human_confirmation`。
只有实际收到确认后，才把状态更新为 `confirmed` 并将 `algorithm` 设为
`legacy_linear_hierarchical_visual`；如用户指向其他实现，应先落实其来源和参数。
已确认的后续会话复用该选择，无需重复询问。

未来候选在自己的配置中将 `baseline_ref` 指向所比较基线的 `metrics/*.json`。
预览会核对素材指纹及分类代码、参数指纹，不一致时拒绝比较。若改变阈值、排序、
权重规则或分类代码，先用新配置重新运行现有模型，形成对应基线，再比较候选。
旧输出名称和 73 个历史终端组不是真值，也不是本次要追平的数值。

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

打开输出的 `preview/index.html`，无需服务或网络。层级组可以展开到每个成员，
点击缩略图打开对应图片或实际视频帧，也可打开源视频。计数和失败始终可见。
技术完成与人工质量分别记录，成功编码不能自动写为分类验收通过。

在每个会话的 `report.md` 填写：人工验收日期、比较对象、
“更好／相当／更差／待定”和简短意见。初始结论为“待人工验收”，比较结论为“待定”。
无需新标注体系或自动分数。

Git 保存共用代码、配置、report 和必要的小型 `metrics/*.json`。
`outputs/` 中的图片、帧、向量、逐项记录、HTML、缓存和日志由现有 `.gitignore` 排除；
原始媒体与权重继续留在外部。不要把大量生成图片或旧模型输出加入 Git。

修改共用代码后，只运行相称的验证：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python -m unittest discover -s eval/shared -p test_model_evaluation.py -v
rtk proxy .venv/bin/ruff check eval/shared/model_evaluation*.py eval/shared/test_model_evaluation.py
```
