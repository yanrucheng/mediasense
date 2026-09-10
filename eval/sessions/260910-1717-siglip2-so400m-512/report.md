---
title: "SigLIP 2 So400m-512：Apple Silicon 业务 Embedding 探索"
service_version: "MediaSense 0.9.0"
date: 2026-09-10
environment: "local macOS 26.4.1; Apple M5 Pro; 48 GiB unified memory"
model_id: "google/siglip2-so400m-patch16-512@ceea1cba8130d8271436da4828633198c176a775"
dataset_version: "ai-album-hk-representative-v1; frozen ChineseCLIP business inputs"
purpose: "固定业务输入和参数，实测 SigLIP 2 图像塔的 MPS 与 Core ML 路线，交付人工分类验收"
baseline_ref: "eval/sessions/260910-1330-chineseclip-business-baseline/metrics/baseline.json"
---

技术执行：**MPS 与 Core ML 单张路线均已完成真实业务评测**，含既有输入失败与下述数值限定。
Core ML 原生 batch 2／4 未通过正确性检查，固定 batch 4 的转换也未解决；这些尝试没有发布业务吞吐。
人工质量：**已验收，当前展示达到预期**；与 ChineseCLIP 的比较结论：**相当，用户未感到显著差异**。
验收日期：2026-09-10（Asia/Shanghai）。用户反馈：“我看了看这个结果都挺不错的，但是没有什么显著的差异吧，我感觉就是跟之前那效果也不错，这个能达到我的预期。”
验收覆盖用户查看的当前分类与代表展示；既有输入准备、关键帧和数值限定继续保留。
生成时的 HTML 与实测摘要保留“待人工验收”快照，最新人工结论以本报告为准。

可打开 [MPS 分类与代表预览](outputs/mps/preview/index.html)，与
[已验收 ChineseCLIP 基线](../260910-1330-chineseclip-business-baseline/outputs/baseline/preview/index.html)比较。
[Core ML 单张预览](outputs/coreml-batch1/preview/index.html)使用同一页面生成器。
三个成功运行都编码了 366 个输入，得到 107 个组，完整交代 2,134 个源媒体。
两条运行时的组成员、组代表和视频选中帧完全一致；用户对候选与 ChineseCLIP 的整体观感为相当。

## 固定条件与实现

Source: `/private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1`，完整 verifier 通过。
实际编码复用业务基线 `outputs/prepared/inputs.json`：99 张图片、267 个视频帧，
保持 184 次抽帧失败和 1 次坏视频探测失败。没有重新抽帧、换素材或调整分类参数。
输入指纹为 `2144fcd970052a44d20a378e3819b86b55345d0605b6d71ce073fc2dd5cd5ba0`。
算法仍为 `build_adaptive_groups` 和 `select_embedding_representative`，距离尺度仍为 0.311。

API endpoint: 仅从公开 PyPI／Hugging Face 下载依赖与指定权重；图像推理全在本地，
编码强制 Hugging Face 离线。没有上传素材、远程推理、训练、微调或 INT8／INT4 量化。
Code 起点：`6037952`，加本会话 eval 修改；每次编码摘要保存实际源码 SHA-256。
原基线及 HTML 运行信息修复分别已提交为 `77e37ab`、`6037952`，起始工作区干净。
原基线摘要和 HTML 的 SHA-256 在收尾仍一致。

实机为 Apple M5 Pro、18 个逻辑 CPU、48 GiB 统一内存、arm64、macOS 26.4.1（25E253）。
隔离环境位于 `/private/tmp/mediasense-siglip2-260910/venv`：Python 3.13.5、PyTorch 2.7.0、
Transformers 4.57.6、Core ML Tools 9.0、NumPy 2.2.6、Pillow 12.3.0。
PyTorch 2.7.0 是该 Core ML Tools 版本声明的最高已测试版本。
独立安装原 MediaSense 0.9.0 wheel，其 46 份 PreCheck 源码指纹与业务基线一致；日常环境未改动。
完整依赖锁定见 [requirements.txt](requirements.txt)，环境和文件身份见 [environment.json](metrics/environment.json)。

checkpoint 固定为 `ceea1cba8130d8271436da4828633198c176a775`；权重 SHA-256 为
`a621bd212e1b3329b428595f9693217e19587afe826adf3e5c241a16392e8973`。
下载文件包含双塔，共 1,136,555,698 个 FP32 参数；只实例化、执行 **428,772,800 参数的视觉塔**。
薄适配器位于 [model_evaluation_siglip2.py](../../shared/model_evaluation_siglip2.py)，复用原 runner、分类与 HTML。
共用 runner 仅新增首批计时字段。

使用官方 `SiglipImageProcessor`：Pillow RGB、双线性缩放到 512×512、除以 255、均值／标准差均为 0.5，
不额外转置 EXIF，不沿用 ChineseCLIP 参数。取官方 `pooler_output`，保留学习得到的注意力池化及残差 MLP；
这是 `SiglipModel.get_image_features` 的视觉路径，输出 1,152 维，再由 runner L2 归一化并保存 float32-le。

MPS 使用 FP16 参数／输入、官方 SDPA 实现、无 autocast，显式禁用 CPU fallback。
实际核对参数及输出设备为 MPS，并调用 `torch.mps.synchronize()`；沙箱隐藏 Metal 设备，因此实际运行在沙箱外进行。
Core ML 使用转换后的独立 ML Program／`.mlmodelc`，预测不加载或执行 PyTorch 模型；图内 FP16，输入输出 FP32。
最终配置明确限定 **每次原生预测 1 张**，没有补齐输入或隐藏的批量推理。

## 性能

每行都是新进程、新输出目录的全量真实编码，无向量缓存命中，无不计时预热。
MPS 两个批大小的向量逐字节相同；batch 1 是为匹配 Core ML 可用路径增加的一次对照。

| 模型／运行时 | 设备／计算单元 | 精度 | batch | 加载 s | 编码 s | 输入/s | 进程峰值 RSS GiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| ChineseCLIP Huge／PyTorch | CPU | FP32 | 4 | 26.50 | 155.29 | 2.357 | 2.864 |
| SigLIP 2／PyTorch | MPS GPU | FP16 | 4 | 8.70 | 26.74 | 13.686 | 2.715 |
| SigLIP 2／PyTorch | MPS GPU | FP16 | 1 | 28.59 | 29.07 | 12.589 | 2.715 |
| SigLIP 2／Core ML | ALL，实际调度未测 | FP16 图 | 1 | 9.19 | 21.76 | 16.816 | 1.968* |

摘要：[MPS batch 4](metrics/mps.json)、[MPS batch 1](metrics/mps-batch1.json)、[Core ML batch 1](metrics/coreml-batch1.json)。
与旧 CPU 基线相比，MPS batch 4 约快 5.81 倍，Core ML batch 1 约快 7.14 倍，表示模型、精度和设备共同变化的方案收益。
同一候选、相近精度、相同 batch 1 下，Core ML 本次吞吐高 **33.58%**，编码时间少 **25.14%**。
这是一次完整输入集测量的结论，未建立多轮方差或其他机器的效率结论。

加载包含适配器／框架导入、加载及设备准备；编码包含读取、解码、官方预处理、计算、结果取回及同步。
源校验、抽帧、L2 归一化、写盘、分类和预览在编码计时之外。首批分别为 0.391／0.418／0.501 s，已计入相应编码总时间。
系统文件和设备编译缓存未清空；首批时间包含读取和计算，不能作为纯编译时间。
MPS batch 1 的加载时间明显长于 batch 4，使用相同加载路径，原因未独立量测，不归因于批大小。
PyTorch 实际使用 2 个 CPU 线程、1 个 inter-op 线程，所有性能运行 nice 10；Core ML 内部线程由系统管理。

*RSS 是 `RUSAGE_SELF` 从编码进程启动到编码完成的高水位，含加载，排除子进程及 Core ML 独立系统服务。
全机统一内存峰值、Core ML 服务占用和 GPU 独立峰值均未知；**不能把 1.968 GiB 与 2.715 GiB 的差额解释为整个方案节省的内存**。

## 转换与正确性

[小样本 PyTorch 验证](metrics/correctness-torch.json)覆盖固定 4 张图片、4 个视频帧，
核对顺序、维度、有限数值、归一化、单张／批量／重排／末批 2 张。
CPU 适配器与直接调用官方 `get_image_features` 输出完全一致。
MPS FP32 相对 CPU FP32 最大余弦距离约 `2.20e-8`；MPS FP16 为 `1.45e-5`。
8 个样本的相似度排序均未变。

[Core ML 转换记录](metrics/conversion.json)：TorchScript 追踪及 batch 1／2／4 核对 30.98 s，
转换 8.35 s，保存 0.13 s，`compile_model` 包编译 0.14 s，另有源加载和框架导入。
追踪输出与原 FP32 参考完全一致。最低目标 macOS 15，659 个非恒定浮点输出为 FP16、1 个为 FP32。
设备特定准备仍可能发生在模型加载／首批内，未单独识别其耗时；这些成本没有从相应计时中扣除。
转换进程 RSS 峰值 4.520 GiB，与编码进程指标分开。
模型包和已编译目录每个文件的 SHA-256 在 [Core ML 配置](config-coreml-batch1.json)中固定。

`ComputeUnit.ALL` 的静态计算计划为 665 个可执行操作列出 GPU 优先，另有 938 个恒定操作未报告设备。
它同时列出可支持的 CPU／GPU／ANE；**静态计划不证明实际调度，也不证明 ANE 参与**。

原生批量缺陷被真实检查拦截：[可变批量失败](metrics/correctness-coreml-flexible-failed.json)、
[固定 batch 4 失败](metrics/correctness-coreml-fixed4-failed.json)、[定位摘要](metrics/coreml-batch-diagnosis.json)。
可变模型单张接近参考，但 batch 4 的前三个槽位可出现约 0.48–0.73 的对应余弦相似度，重排和重复同图仍能复现；
固定 batch 4 也未通过。具体错误算子／后端尚未定位，未通过替换池化、调整阈值或改权重消除差异。
最终只采用已验证的单张调用，转换脚本默认生成的运行配置也限制 batch 1。

[Core ML 单张小样本验证](metrics/correctness-coreml-batch1.json)通过：相对 CPU FP32 最大余弦距离 `1.18e-5`，
相对 MPS FP16 为 `8.34e-6`，8 个样本排序未变。
该记录中的多图调用检查由适配器逐张预测，不表示原生 batch 4 已修好。

[全量核对](metrics/result-validation.json)确认三次运行的 366 个向量均有限、单位范数误差小于 `2.6e-8`；
跨运行时 366 个最近邻、107 个组的成员／代表和视频选中帧一致。保存向量重新分类与各自原结果完全相同。
全量跨运行时最大对应余弦距离为 `9.39e-5`，最大两两相似度差为 **0.002560**。
共有 **13／66,795 对**超过小样本使用的 0.002 检查界限；没有改大这个界限，也不声称全量均满足它。
[最差一对的额外 FP32 核对](metrics/numerical-tail-check.json)发现 MPS／Core ML 分别偏差 0.001360／0.001200、方向相反，
两张图的对应余弦距离均小于 `4e-5`。这支持本轮带数值限定的业务使用，不构成任意输入下的严格数值等价证明。

三份 HTML 各有 2,134 张无重复源卡片、2,118 份可解码缩略图和 2,681 个存在的本地链接。
现有隔离 WebKit 检查器实际加载页面，验证 107 个组展开／收起、视频展开及各 16 张图片解码。
截图留在本地，没有把私人图像传入远程模型。18 项共用测试及 Ruff 检查通过。

## 人工验收与技术判断

ChineseCLIP 为 117 组，候选为 107 组。80 个候选组与某个基线组成员完全相同，其中 3 组更换了代表。
用户查看后确认达到预期，与原基线没有感到显著差异。本次人工结论为效果相当，不从分组减少或参数规模推导更好的质量。

**候选已达到用户本轮质量预期，主要已证实收益是编码速度。** 本机已有明显方案速度收益，Core ML 单张也给出了相同业务结果和较快的匹配运行时实测。
后续可据此评估集成价值，并决定是否研究 Core ML 批量缺陷和更广泛数值稳定性；总内存与功耗改善尚无完整测量证据。
本轮没有生产模型替换或阶段合约修改。

原输入限制继续有效：185 项准备失败；181 个可用视频仅有 1–2 帧，不能证明关键帧排序质量；
代理素材不代表原始全码流解码速度或画质；未逐一编码的初始组成员仍可能有隐藏差异。
固定 0.311 的结果只说明直接接入当前业务的表现，是否为新模型调整阈值留待后续独立实验。

## 工程参考资产与接入边界

本报告是本候选的工程参考入口。下表链接已实际使用的技术资产；参数、依赖和模型
文件身份仍以对应配置为准，验证结论和限制见上文及链接的原始摘要。

| 技术资产 | 工程可复用的内容 | 位置 |
| --- | --- | --- |
| 两条图像编码参考实现 | 官方处理器和池化、视觉塔加载、MPS 设备检查与同步、Core ML 单张预测 | [薄适配器](../../shared/model_evaluation_siglip2.py) |
| 已验证运行配置 | 固定 checkpoint、文件校验、设备／精度／批量条件、1152 维输出及归一化声明 | [MPS batch 4](config-mps.json)、[MPS batch 1 对照](config-mps-batch1.json)、[Core ML batch 1](config-coreml-batch1.json) |
| 环境复现依据 | 实测硬件、依赖锁、原 MediaSense wheel 身份；这里锁定的是完整评测环境 | [环境记录](metrics/environment.json)、[依赖锁](requirements.txt) |
| 转换方法 | 从相同视觉塔生成 FP16 ML Program、编译模型及记录计算计划／文件身份；默认运行配置限制为 batch 1 | [转换脚本](convert_coreml.py)、[转换记录](metrics/conversion.json) |
| 正确性验证方法 | 固定真实输入，检查官方输出、设备／精度差异、顺序与多图调用；可重跑对应小样本 | [验证脚本](validate.py)、[PyTorch 证据](metrics/correctness-torch.json)、[Core ML 单张证据](metrics/correctness-coreml-batch1.json) |
| 业务与失败证据 | 实测速度／RSS、相同业务输出、原生批量缺陷、全量数值偏差及适用范围 | [全量核对](metrics/result-validation.json)、[批量缺陷](metrics/coreml-batch-diagnosis.json)、[数值补查](metrics/numerical-tail-check.json)；性能表见上文 |

接入时需要保留完整的已验证编码链路：适配器 `encode_images()` 返回的是原生池化特征，
**L2 归一化、向量有效性检查和 float32-le 落盘由共用 runner 完成**。
只取适配器而漏掉后段，会偏离本次验证条件。生产已有
[`ImageEmbeddingEncoder` 与 `EmbeddingProfile`](../../../src/mediasense/precheck/embedding.py)：
当前端口是 `identity`、`encode_image(Path)`，评测适配约定另有 `load`、`encode_images` 和
`synchronize`，因此该参考实现尚不能直接宣称为生产端口的实现。

工程可把必要编码逻辑适配到现有生产边界，生产代码不依赖本仓库的 `eval/` 路径。
评测配置／identity 含本机路径、解释器和实验环境信息；生产模型身份、profile 与
缓存依赖需按现有机制接入，验证新旧向量隔离、失效和复用，不能直接把评测配置当成生产配置。

本轮尚未验证 SigLIP 2 的生产配置装配、依赖发布、模型获取与安装、Work／Artifact
复用、长任务中断恢复，以及安装版 PreCheck 入口的完整集成。这些由后续工程接入
完成并记录到既有迁移台账。本轮沿用的 0.9.0 业务源码指纹描述原实测；工程版本发生
变化后需在其实际安装环境复验，改变输入或分类配方时按 runbook 重新建立可比基线。

Core ML 当前通过的是 Python `coremltools.CompiledMLModel` 加官方 Transformers 图像
处理器的路线。虽然预测不执行 PyTorch 模型，完整评测环境仍包含 PyTorch 和转换工具；
**去掉这些依赖的最小运行环境、Swift／原生应用接入和其他机器均未验证**。
原生 batch 2／4 的失败及数值限定必须随本次参考一起交代；未来可由新证据更新支持范围。

源权重位于 `config-mps.json` 指定的 `/private/tmp/mediasense-siglip2-260910/hf/` 下，
可用 `.mlpackage` 和 `.mlmodelc` 位于 `/private/tmp/mediasense-siglip2-260910/coreml-fp16/`。
本次核对这些文件仍存在；它们是本地临时资产，生产分发与长期保存尚未建立。
固定来源、文件校验和下节重建命令随文本资产保留，不把临时路径当成长期交付地址。

本次工程资产核对时，新增会话文件与薄适配器已落盘，但尚未被 Git 跟踪／提交；
共用 runner 和 runbook 也有未提交改动。版本化保存仍待完成；其他线程正在修改的
Geo／产品文件不属于本会话交付。模型、向量和大量生成输出继续排除在 Git 外。

## 复现

唯一流程说明仍是 [本地模型评测 runbook](../../../readme/model-evaluation.md)。以下工作目录均为仓库根目录。
本地权重、转换模型、向量、HTML、缩略图、截图、日志均不进 Git；`outputs/` 被忽略。
`/private/tmp` 不是长期备份，丢失时按下列固定依赖和 revision 重建，准备输入丢失时遵循 runbook 并核对原指纹。

已有环境及权重时，重新执行完整 MPS／Core ML 编码；下面的 `repeat-01` 输出与摘要必须尚不存在：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-siglip2-260910/venv/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-1717-siglip2-so400m-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-1717-siglip2-so400m-512/outputs/repeat-mps-01 \
  --summary eval/sessions/260910-1717-siglip2-so400m-512/metrics/repeat-mps-01.json

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-siglip2-260910/venv/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-1717-siglip2-so400m-512/config-coreml-batch1.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-1717-siglip2-so400m-512/outputs/repeat-coreml-01 \
  --summary eval/sessions/260910-1717-siglip2-so400m-512/metrics/repeat-coreml-01.json

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-siglip2-260910/venv/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-1717-siglip2-so400m-512/config-mps-batch1.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-1717-siglip2-so400m-512/outputs/repeat-mps-batch1-01 \
  --summary eval/sessions/260910-1717-siglip2-so400m-512/metrics/repeat-mps-batch1-01.json
```

原次执行的输出名称为 `mps`、`coreml-batch1`、`mps-batch1`，相应摘要为同名 JSON；这些文件已存在，不覆盖。
MPS batch 4 执行后只扩充了适配器的 Core ML 部分，MPS 的四个定义经 AST 核对未变；
当时源码保留于 `outputs/mps/execution-source/`，与记录 SHA 一致，
[小补丁](metrics/mps-batch4-adapter-source.patch)可从最终代码恢复当时版本。两个 batch 1 使用相同的最终 eval 源码指纹。

仅在隔离环境丢失时重建。wheel SHA-256 必须为
`66745af1eed9fe4d2d0ae7f9dc31fa47c1a9a84a5826559d2ab8551c9371344a`：

```bash
rtk proxy uv venv --python /Users/chengyanru/.local/share/uv/python/cpython-3.13.5-macos-aarch64-none/bin/python3.13 /private/tmp/mediasense-siglip2-260910/venv
rtk proxy env UV_CACHE_DIR=/private/tmp/mediasense-siglip2-260910/uv-cache uv pip install \
  --python /private/tmp/mediasense-siglip2-260910/venv/bin/python \
  -r eval/sessions/260910-1717-siglip2-so400m-512/requirements.txt dist/mediasense-0.9.0-py3-none-any.whl
rtk proxy env HF_HOME=/private/tmp/mediasense-siglip2-260910/hf HF_HUB_OFFLINE=0 HF_HUB_DISABLE_TELEMETRY=1 HF_HUB_DISABLE_IMPLICIT_TOKEN=1 \
  /private/tmp/mediasense-siglip2-260910/venv/bin/python -c 'from huggingface_hub import snapshot_download; snapshot_download("google/siglip2-so400m-patch16-512", revision="ceea1cba8130d8271436da4828633198c176a775", cache_dir="/private/tmp/mediasense-siglip2-260910/hf/hub", allow_patterns=["config.json", "preprocessor_config.json", "model.safetensors", "README.md"], token=False)'
```

重新验证小样本及重建转换模型，仍使用新路径：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-siglip2-260910/venv/bin/python eval/sessions/260910-1717-siglip2-so400m-512/validate.py torch \
  --config eval/sessions/260910-1717-siglip2-so400m-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-1717-siglip2-so400m-512/outputs/correctness-torch-repeat-01

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-siglip2-260910/venv/bin/python eval/sessions/260910-1717-siglip2-so400m-512/convert_coreml.py \
  --config eval/sessions/260910-1717-siglip2-so400m-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260910-1717-siglip2-so400m-512/outputs/correctness-torch-repeat-01 \
  --output /private/tmp/mediasense-siglip2-260910/coreml-fp16-repeat-01 \
  --evidence eval/sessions/260910-1717-siglip2-so400m-512/outputs/conversion-repeat-01

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-siglip2-260910/venv/bin/python eval/sessions/260910-1717-siglip2-so400m-512/validate.py coreml \
  --config eval/sessions/260910-1717-siglip2-so400m-512/outputs/conversion-repeat-01/config-coreml.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260910-1717-siglip2-so400m-512/outputs/correctness-torch-repeat-01 \
  --output eval/sessions/260910-1717-siglip2-so400m-512/outputs/correctness-coreml-repeat-01
```

重建后用新 `conversion-repeat-01/config-coreml.json` 运行共用 `run`，因为生成文件的身份可能变化。
`--fixed-batch` 仅保留复现失败尝试的诊断用途。原次小样本证据位于 `correctness-torch-02`、
`correctness-coreml-batch1`；首次 PyTorch 诊断的进度文件写入冲突已修复并完整重跑，原失败日志继续保留。
