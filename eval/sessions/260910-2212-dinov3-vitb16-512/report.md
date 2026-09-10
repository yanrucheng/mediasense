---
title: "DINOv3 ViT-B/16 512px：业务 Embedding 接入与评测"
service_version: "MediaSense 0.9.0"
date: 2026-09-10
environment: "macOS 26.4.1; Apple M5 Pro; 48 GiB unified memory; isolated environment"
model_id: "timm/vit_base_patch16_dinov3.lvd1689m@c6a5fb7d12bbd3cf3b0079253141c3332aaed7da"
dataset_version: "ai-album-hk-representative-v1; frozen ChineseCLIP business inputs"
purpose: "比较较小纯视觉模型直接接入固定业务策略时的分类、代表选择、速度与内存"
baseline_ref: "eval/sessions/260910-1330-chineseclip-business-baseline/metrics/baseline.json"
---

技术验收：**MPS 混合精度 batch 4／1、Core ML 固定单张路线通过，均完成真实业务评测。**
人工质量更新（2026-09-11）：**后继 103 组版本已验收，用户认为效果与效能相对此前方案“显著更好”。**
本页保留的 157 组版本已由用户查看，用户认为其**很可能更适合作为 Embedding 聚合结果**。
主要比较对象仍为已验收的 SigLIP 2 So400m-512；103 组的认可与 157 组的聚合用途判断分别记录，
完整原话及范围见[后继会话的人工反馈](../260911-0031-dinov3-threshold-calibration/report.md#人工反馈与两种粒度的用途)。
原 HTML、运行摘要及技术 closeout 保留生成时状态，人工结论以报告后续记录为准。
185 项既有准备失败、视频采样限制、下述失败路线及数值范围随结果保留。
会话于 2026-09-10 建立；技术收尾于 2026-09-11（Asia/Shanghai）完成。
这次接入的实际发布来自 timm；官方 Hugging Face checkpoint 未取得，不声称已验证两者数值等价。

## 可直接查看的结果

- [已人工验收的后继 103 组预览（距离尺度 0.85，复用本会话向量）](../260911-0031-dinov3-threshold-calibration/outputs/dinov3-085/preview/index.html)
- [DINOv3 MPS 分类与代表预览](outputs/mps/preview/index.html)
- [DINOv3 Core ML 单张预览](outputs/coreml-batch1/preview/index.html)
- [DINOv3 MPS batch 1 对照](outputs/mps-batch1/preview/index.html)
- [已验收 SigLIP 2 预览](../260910-1717-siglip2-so400m-512/outputs/mps/preview/index.html) · [其报告与验收记录](../260910-1717-siglip2-so400m-512/report.md)
- [已验收 ChineseCLIP 预览](../260910-1330-chineseclip-business-baseline/outputs/baseline/preview/index.html) · [其报告与验收记录](../260910-1330-chineseclip-business-baseline/report.md)

三条有效 DINOv3 路线均得到 **157 个组**，组成员、组代表、视频选中帧、边界及差异样本一致。
三份 157 组页面展示等价的业务结果；103 组的后继验收不覆盖或淘汰这些较细聚合结果。
相对 SigLIP 2 的 107 个组，34 个原组被进一步拆分；
157 个新组均包含在某个原 SigLIP 2 组内，没有跨原组的新合并。73 个组成员完全相同，代表也未改变。
相对 ChineseCLIP 的 117 个组，28 个原组被拆分，89 个组成员完全相同。

建议优先比较 SigLIP 2 的 **055 → DINOv3 076–080**、**056 → 081–086**、**065 → 097–100**。
其中后一个原组覆盖 111 个源媒体。请判断这些拆分是否有用、是否增加了不必要的阅读负担，
并检查各组代表是否能概括内容。这些编号用于定位，不构成自动质量评分。

157 个组中有 148 个仅含一个初始业务候选；初始候选本身仍可能代表多张源素材。
DINOv3 的预处理、CLS 路径、输入对应和数值检查均已核对，跨运行时也复现了同样的拆分。
这支持把差异视为当前模型表示与固定业务策略的实际组合结果，而非本轮已发现的数值错误。
本会话的距离尺度仍为 **0.311**，原次实验没有调参。
后继会话只将尺度改为 **0.85**，复用相同向量生成 103 组并获得用户明确认可；
用户同时倾向保留 157 组作为较细的 Embedding 聚合结果。两种用途及重分组实现经验由[后继报告](../260911-0031-dinov3-threshold-calibration/report.md)维护。

## 冻结条件与模型来源

Source: `/private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1`。
本轮完整 verifier 通过，逻辑大小 1,759,421,497 bytes。源与原有结果保持只读。
实际输入固定为 `eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json`：
2,134 个源媒体、167 个初始业务候选、99 张图片和 267 个视频帧；另外保留 184 次抽帧失败和 1 次探测失败。
没有重新抽帧，也没有读取旧向量作为候选输入或推理缓存。
输入指纹为 `2144fcd970052a44d20a378e3819b86b55345d0605b6d71ce073fc2dd5cd5ba0`。

业务函数复用安装版 MediaSense 0.9.0 的 `build_adaptive_groups` 和 `select_embedding_representative`。
46 份 PreCheck 源码指纹为 `255977ab42bc780b9f59ce4ff519be872766f2ee4dfa4ae1cc1eace1dd8b2ff3`，
与业务基线一致。共用 runner、分类绑定、HTML 生成器沿用已有现场版本；本轮新增模型薄适配器和会话验证代码。
Code 起点：`60379526456f0f0653066ab906cd5cf42ca860da`，包含当时已有未提交的 SigLIP／eval 改动；
[起始状态](metrics/starting-state.json)与各次 `encoding.json` 保存实际源码 SHA-256，成功运行的源码副本保留在对应 `outputs/*/execution-source/`。

优先检查的官方仓库是 `facebook/dinov3-vitb16-pretrain-lvd1689m`，公开 API revision 为
`5931719e67bbdb9737e363e781fb0c67687896bc`；权重下载返回 **401 GatedRepo**，要求账户获批且登录。
本机没有 Hugging Face token 或该模型缓存。本轮已说明此缺口，使用用户列出的公开 timm 同源发布继续。
没有换为 DINOv2、其他规模或其他训练数据 checkpoint。

实际模型为 `timm/vit_base_patch16_dinov3.lvd1689m`，revision
`c6a5fb7d12bbd3cf3b0079253141c3332aaed7da`。
权重 SHA-256：`1f9ed8a2378d65e24bb710ba522ac9fa7be4e036d7aefb4384ce022833926332`。
**实际实例化 85,641,216 个参数**，严格加载全部权重，无缺失或额外键；没有训练、微调或添加分类头。
模型卡将其说明为从 DINOv3 ViT-7B 蒸馏的 LVD-1689M 视觉模型。

API endpoint: 仅公开 Hugging Face／PyPI 的模型与依赖下载；推理强制离线。
私人素材、缩略图和截图没有上传，也没有远程／付费推理。
独立环境为 `/private/tmp/mediasense-dinov3-260910/venv`：Python 3.13.5、PyTorch 2.7.0、
timm 1.0.20、Torchvision 0.22.0、Core ML Tools 9.0、NumPy 2.2.6、Pillow 12.3.0。
日常环境和生产模型配置未升级。完整身份见[环境记录](metrics/environment.json)、[依赖锁](requirements.txt)和[预检](metrics/preflight.json)。

## 简单性能对比

每行对应一次新进程、新输出目录的完整真实编码。SigLIP 2 和 ChineseCLIP 行来自核对后的历史保留记录。
各行都是 366 个成功输入，零向量缓存命中、零不计时预热；未建立多轮方差或其他机器上的保证。

| 模型 | 输入 px | 运行时／有效精度 | batch | 加载 s | 编码 s | 输入/s | 峰值进程 RSS GiB |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| ChineseCLIP Huge | 224 | CPU／FP32 | 4 | 26.50 | 155.29 | 2.357 | 2.864 |
| SigLIP 2 So400m | 512 | MPS／FP16 参数与计算 | 4 | 8.70 | 26.74 | 13.686 | 2.715 |
| SigLIP 2 So400m | 512 | MPS／FP16 参数与计算 | 1 | 28.59 | 29.07 | 12.589 | 2.715 |
| SigLIP 2 So400m | 512 | Core ML／FP16 图 | 1 | 9.19 | 21.76 | 16.816 | 1.968* |
| DINOv3 ViT-B/16 | 512 | MPS／混合 FP16＋FP32，参数 FP32 | 4 | 6.06 | **20.36** | **17.974** | **0.964** |
| DINOv3 ViT-B/16 | 512 | MPS／混合 FP16＋FP32，参数 FP32 | 1 | 5.82 | **21.04** | **17.399** | **0.964** |
| DINOv3 ViT-B/16 | 512 | Core ML／混合 FP16＋FP32 图 | 1 | 7.30 | **14.72** | **24.868** | **0.776*** |

DINOv3 相对 SigLIP 2，MPS batch 4 本次编码时间少 **23.85%**，吞吐高 **31.33%**；
Core ML batch 1 编码时间少 **32.38%**，吞吐高 **47.88%**。这些是模型、表示、精度策略和实现共同变化的方案收益。
同一 DINOv3、相同 batch 1 下，Core ML 本次编码时间少 **30.03%**，吞吐高 **42.92%**。
参数约为 SigLIP 2 实际图像塔的五分之一，并没有直接转化为五倍吞吐。

加载包含框架／适配器导入、模型与处理器加载、设备准备和同步。
编码包含读取、RGB 解码、预处理、推理、结果取回和同步；不含源校验、抽帧、runner L2 归一化、写盘、分组或 HTML。
DINOv3 三次首批分别为 0.521／0.242／0.121 s，均计入总编码时间。
PyTorch 使用 2 个 CPU 线程、1 个 inter-op 线程；性能运行均为 nice 10，Core ML 内部线程由系统管理。
文件与系统编译缓存未清空，验证也会读取权重／输入；这些数值不是冷磁盘基准。

*RSS 是编码进程 `RUSAGE_SELF` 从启动到编码完成的高水位，包含加载，排除子进程、Core ML 独立系统服务和未被该指标覆盖的 GPU 分配。
**全机统一内存峰值及 Core ML 服务／GPU 峰值未知；不能据 RSS 差额宣称整个方案节省了相同的总内存。**
MPS 进程 RSS 的下降是该统计范围内的实测。Core ML 使用 `ComputeUnit.ALL`，实际设备调度未跟踪，不宣称使用了 ANE。

## 接入与精度的技术 review

[薄适配器](../../shared/model_evaluation_dinov3.py)只负责加载、编码、同步和运行说明，返回普通数值向量。
runner 继续负责行数／有限数值检查、L2 归一化及 little-endian float32 落盘。
MPS 实际参数和输出设备均核对为 MPS，`PYTORCH_ENABLE_MPS_FALLBACK=0`；在可访问 Metal 的沙箱外执行。
timm 明确在 CPU 生成位置坐标再转移到模型设备，这属于可见实现步骤，不是算子静默回退。

| 检查项 | 实际处理与结论 |
| --- | --- |
| 512 配方 | 使用 Meta README `make_transform(resize_size=512)`：Pillow RGB、ToImage uint8、双线性方形 resize／antialias、转 FP32 并缩放、ImageNet mean/std。无 crop、无 EXIF transpose。原官方示例默认 256；本轮显式设置 512，动态尺寸模型实测产生 32×32 patch。未沿用 timm 默认 bicubic/center-crop 或 SigLIP 的处理器。 |
| CLS 含义 | `forward_features` 包含最终 LayerNorm；只取 `[:, 0, :]`。实测 token 形状为 N×1029×768，即 CLS＋4 register＋1024 patch。模型保留内部 register tokens；未把它们平均进输出。timm 默认池化是 avg，本轮明确使用 CLS，head 为 Identity。 |
| 参考一致性 | CPU 适配器、直接取最终 CLS、timm token-pool 路径完全一致；预处理与独立构造的 Meta 配方逐值一致。CPU FP32 是本轮选定 timm 实现的参考，不冒充原 Meta checkpoint 的实测。 |
| QKV bias 差异 | timm 模型卡说明原权重的 QKV bias 为零，发布时禁用并省略；本轮严格加载的 state 中确实没有 QKV bias。原官方权重不可访问，其值未独立复核。 |
| RoPE 差异 | timm 原生生成 FP32 periods，原 Meta 模型卡描述持久化 BF16 periods。本轮固定 timm 原生 FP32 值，没有截断成 BF16，也不宣称两者数值等价。 |
| 通过的 MPS 精度 | 保留 FP32 参数、attention、归一化、残差和 RoPE，显式 FP16 autocast 用于卷积／MLP；attention 内禁用 autocast。实际 hook 记录 Conv/MLP 输出为 FP16，QKV、LayerNorm、block 残差输出为 FP32，均在 MPS。 |

纯 FP16 路线和无保护的标准 autocast 在第一层 attention 产生非有限值。
同一 Q/K/V 的 FP32 QK 点积最大约 **1,096,297**，超出 FP16 有限范围；FP32 SDPA 正常，FP16 SDPA 与普通 FP16 attention 都失败。
只把 attention 保留 FP32、其余参数和残差改为 FP16，虽不再出现 NaN，但最大对应余弦距离 **0.02210**、两两相似度差 **0.02228**，没有通过原界限。
最终采用上表的有限混合精度。以上失败由[保存的诊断脚本](diagnose_precision.py)再次复现，见[精度复现](metrics/precision-reproduction.json)和[attention 定位](metrics/attention-diagnosis.json)。
这些失败路线没有全量业务吞吐，不把有效路线称为全模型 FP16。

[小样本验证](metrics/correctness-torch.json)覆盖固定 4 张图片与 4 个视频帧、单张／batch 4、重排、重复槽位及末批 2 张。
最大对应余弦距离界限 0.001、两两相似度差界限 0.002，参考间隔大于 0.005 的排序不得反转，保存范数误差不超过 1e-6。
这些界限在运行前固定，失败后没有放宽。
MPS FP32 相对 CPU FP32 的最大两两差约 5.33e-7；有效 MPS 混合精度最大对应距离 2.09e-6、两两差 0.000414，8 个样本排序未变。

## Core ML 转换与全量正确性

[转换脚本](convert_coreml.py)从同一 CPU FP32 CLS 路径导出固定 512 输入。
Core ML Tools 9.0 最初不支持 `tensor_split`；仅在导出进程中将 128 维 sin/cos 的二等分改为等价 `chunk(2,-1)`，未改位置值或池化。
追踪输出与 CPU 参考逐值相同。脚本保留 `--native-tensor-split` 以复现原失败。
精度选择只将卷积／MLP scope 转为 FP16；attention、归一化、残差和 RoPE 保留 FP32。
转换后有 51 个非恒定 FP16 输出、486 个 FP32 输出；核对的 36 个 attention 计算输出均为 FP32。

固定单张[转换记录](metrics/conversion-batch1.json)：源加载及样例准备 1.377 s、trace 与检查 5.365 s、
转换 2.066 s、保存 0.041 s、包编译 0.176 s。转换进程峰值 RSS 约 0.995 GiB，与编码进程分开。
设备特定准备仍可能发生于加载／首批中，没有从性能计时中扣除，也没有把首批当作纯编译时间。
生成的 `.mlpackage`／`.mlmodelc` 文件身份由配置固定；模型重建后使用转换脚本新生成的配置。
预测调用 `CompiledMLModel.predict`，不实例化或执行 PyTorch 模型；本轮预处理仍依赖 Torchvision/PyTorch，未验证最小运行依赖或 Swift 原生模型接入。

[Core ML 单张小样本](metrics/correctness-coreml-batch1.json)相对 CPU 最大对应距离 1.80e-6、两两差 0.000401；
相对 MPS 最大对应距离 2.20e-7、两两差 0.000069，样本排序未变。
单张配置在验证脚本的多图调用中逐张预测，未用这种调用证明原生 batch 4。

[全量验证](metrics/result-validation.json)确认三次各 366 个向量有限、最大单位范数误差 6.26e-9 以下；保存向量重新分类与各自原结果完全一致。
MPS batch 1 与 batch 4 的向量文件逐字节相同。
Core ML 相对 MPS 全量最大对应距离约 **3.98e-7**，66,795 对相似度最大差 **0.000318**，超过 0.002 的对数为 **0**；
366 个最近邻一致。更深排序有 6,825 个位置变化，但参考间隔大于 0.005 的反转为零；未声称全部排序完全相同。
业务组成员、代表、视频选中帧、边界和差异样本一致。

全量核对时 NumPy/Accelerate 对有限单位向量 matmul 发出了浮点告警；独立非 BLAS einsum 复核两条路径均有限，最大差小于 2.9e-15。
最终全量验证使用非 BLAS 计算并显式检查矩阵有限性，见[算术复核](metrics/similarity-arithmetic-check.json)。这没有改变推理、分组参数或数值界限。

另外实际转换并尝试了原生可变 batch 1／2／4。该模型在 Core ML 设备编译阶段产生
`layer_norm tensor<?x?x768xf32>` 与 `gamma tensor<1x1x0xf32>` 不兼容的 LLVM 错误，进程 SIGABRT／exit 134，未产出可验收向量。
[失败摘要](metrics/correctness-coreml-batch124-failed.json)保留准确范围；[转换记录](metrics/conversion-batch124.json)不等于推理通过。
它是本轮动态形状的后端编译失败，没有证据把它解释为上轮 SigLIP 2 的批量数值错误。
**本轮有效 Core ML 配置仅限固定 batch 1**。进一步研究可单独尝试固定 batch 2／4，并重新验证槽位与末批；本轮不扩展为后端修复工程。

## 交付检查与适用边界

三份 HTML 均有 2,134 张无重复源卡片，2,118 张缩略图全部通过本地解码，所有本地图片／链接目标存在。
[本地 WebKit 检查](metrics/browser-validation.json)由保存并重新编译的 [Swift 检查器](check_preview.swift)执行，
通过 157 组展开／收起、视频展开和每页 16 张图像加载。截图仅在 ignored outputs 内保留，没有传给远程模型。
18 项共用 eval 测试及本轮 Python 文件 Ruff 检查通过。

181 个可用视频仍只有 1–2 帧（95／86 个），两帧对称比较会打平，**无法证明视频关键帧排序质量**。
185 项准备失败原样保留；初始素材组中未逐一编码成员可能仍有隐藏差异。
素材是代理图片／稀疏视频，不代表原始全码流的解码速度或画质。
本轮 CPU FP32 完整参考仅覆盖固定小样本；全量验证覆盖已运行路线之间的差异与业务复现，不证明任意输入下的数值等价。

生产 `ImageEmbeddingEncoder` 的身份、单图端口、配置、依赖发布、模型获取、缓存失效、Work/Artifact 复用、长任务恢复与安装入口尚未接入验证。
生产代码不应依赖 eval 路径；后续工程可提取必要编码逻辑接到已有端口。
本轮没有生产模型替换、PreCheck/Plan/Apply 合约修改或迁移台账接通声明。

本轮代码、配置、报告和紧凑证据已落盘，**尚未提交 Git，版本化保存尚待完成**。
原基线、SigLIP 2 配置／结果、已有 runner 和业务绑定保留；其他线程的 Geo／产品工作未纳入本轮改动。
权重、转换模型、向量、HTML、图片、截图和原始日志排除于 Git；`/private/tmp` 是临时资产位置，不能作为长期备份。
固定来源与重建方法保存在本会话。收尾证据见 [closeout.json](metrics/closeout.json)。

## 复现命令

工作目录为 `/Users/chengyanru/repos/personal/mediasense`；共同规则见[唯一 runbook](../../../readme/model-evaluation.md)。
配置入口：[MPS batch 4](config-mps.json)、[MPS batch 1](config-mps-batch1.json)、[Core ML 固定单张](config-coreml-batch1.json)。
所有新输出和摘要路径必须不存在；原次运行名为 `mps`、`mps-batch1`、`coreml-batch1`，不要覆盖。

已有本地环境／权重／编译模型时，重新执行完整输入集：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-2212-dinov3-vitb16-512/outputs/repeat-mps-01 \
  --summary eval/sessions/260910-2212-dinov3-vitb16-512/metrics/repeat-mps-01.json

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/config-mps-batch1.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-2212-dinov3-vitb16-512/outputs/repeat-mps-batch1-01 \
  --summary eval/sessions/260910-2212-dinov3-vitb16-512/metrics/repeat-mps-batch1-01.json

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/config-coreml-batch1.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-2212-dinov3-vitb16-512/outputs/repeat-coreml-01 \
  --summary eval/sessions/260910-2212-dinov3-vitb16-512/metrics/repeat-coreml-01.json
```

临时环境丢失时独立重建。原 wheel SHA-256 为 `66745af1eed9fe4d2d0ae7f9dc31fa47c1a9a84a5826559d2ab8551c9371344a`。
仅在对应 snapshot 丢失时执行下载循环；runner 会核对全部文件身份。

```bash
rtk proxy uv venv --python /Users/chengyanru/.local/share/uv/python/cpython-3.13.5-macos-aarch64-none/bin/python3.13 /private/tmp/mediasense-dinov3-260910/venv
rtk proxy env UV_CACHE_DIR=/private/tmp/mediasense-dinov3-260910/uv-cache uv pip install \
  --python /private/tmp/mediasense-dinov3-260910/venv/bin/python \
  -r eval/sessions/260910-2212-dinov3-vitb16-512/requirements.txt dist/mediasense-0.9.0-py3-none-any.whl
rtk proxy mkdir -p /private/tmp/mediasense-dinov3-260910/checkpoint/c6a5fb7d12bbd3cf3b0079253141c3332aaed7da
for dino_file in config.json README.md LICENSE.md model.safetensors; do
  rtk proxy curl -fL --retry 2 --connect-timeout 20 --max-time 300 \
    -o "/private/tmp/mediasense-dinov3-260910/checkpoint/c6a5fb7d12bbd3cf3b0079253141c3332aaed7da/$dino_file" \
    "https://huggingface.co/timm/vit_base_patch16_dinov3.lvd1689m/resolve/c6a5fb7d12bbd3cf3b0079253141c3332aaed7da/$dino_file"
done
```

重跑小样本并重建 Core ML；仍使用全新路径：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/validate.py torch \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-2212-dinov3-vitb16-512/outputs/correctness-torch-repeat-01

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/convert_coreml.py \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260910-2212-dinov3-vitb16-512/outputs/correctness-torch-repeat-01 \
  --output /private/tmp/mediasense-dinov3-260910/coreml-repeat-01 \
  --evidence eval/sessions/260910-2212-dinov3-vitb16-512/outputs/conversion-repeat-01

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/validate.py coreml \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/outputs/conversion-repeat-01/config-coreml.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260910-2212-dinov3-vitb16-512/outputs/correctness-torch-repeat-01 \
  --output eval/sessions/260910-2212-dinov3-vitb16-512/outputs/correctness-coreml-repeat-01
```

重建后的 Core ML 完整 `run` 须使用新生成的 `outputs/conversion-repeat-01/config-coreml.json`，
不能继续使用指向旧编译文件的根目录配置。准备输入若丢失，按 runbook 恢复并验证原指纹，不在本轮改变抽帧。

独立复核本次全量结果与失败精度策略：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/validate_results.py \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --runs eval/sessions/260910-2212-dinov3-vitb16-512/outputs/mps eval/sessions/260910-2212-dinov3-vitb16-512/outputs/coreml-batch1 eval/sessions/260910-2212-dinov3-vitb16-512/outputs/mps-batch1 \
  --output eval/sessions/260910-2212-dinov3-vitb16-512/metrics/result-validation-repeat-01.json

rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/diagnose_precision.py \
  --config eval/sessions/260910-2212-dinov3-vitb16-512/config-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260910-2212-dinov3-vitb16-512/outputs/correctness-torch-autocast \
  --output eval/sessions/260910-2212-dinov3-vitb16-512/outputs/precision-repeat-01
```

失败的原生批量复现：给转换命令增加 `--batches 1 2 4` 并换新输出目录，
再对生成的配置执行 `validate.py coreml`。本次原始目录为 `outputs/conversion-batch124` 与 `outputs/correctness-coreml-batch124`，
后者因进程 SIGABRT 无 Python finally 摘要，以对应日志和紧凑失败记录为准。

页面检查器可用 `rtk proxy xcrun swiftc -module-cache-path /private/tmp/mediasense-dinov3-260910/swift-module-cache eval/sessions/260910-2212-dinov3-vitb16-512/check_preview.swift -o /private/tmp/mediasense-dinov3-260910/check-preview` 重建；
运行时传入 HTML 与本地 PNG 的绝对路径，截图不上传。

## 来源

- [DINOv3 官方仓库与所读 README revision](https://github.com/facebookresearch/dinov3/tree/6876159a11b4df116f30f667f8c9888617df0751)
- [DINOv3 论文](https://arxiv.org/abs/2508.10104)
- [优先检查的官方 HF 发布](https://huggingface.co/facebook/dinov3-vitb16-pretrain-lvd1689m)
- [实际采用的 timm 模型卡 revision](https://huggingface.co/timm/vit_base_patch16_dinov3.lvd1689m/blob/c6a5fb7d12bbd3cf3b0079253141c3332aaed7da/README.md)
