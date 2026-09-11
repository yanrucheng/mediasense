---
title: "DINOv3 ViT-B/16 512→384：有界效率探索"
service_version: "MediaSense 0.9.0"
date: 2026-09-11
environment: "macOS; Apple M5 Pro; 48 GiB; isolated existing environment"
model_id: "timm/vit_base_patch16_dinov3.lvd1689m@c6a5fb7d12bbd3cf3b0079253141c3332aaed7da"
dataset_version: "frozen business inputs; 366 encodable images/frames"
purpose: "只改变输入分辨率，检查正确性、分阶段效率与两档人工预览；简查 MobileCLIP 2-S2"
baseline_ref: "260910-2212-dinov3-vitb16-512; 260911-0031-dinov3-threshold-calibration"
---

技术验收：**384 MPS 混合精度 batch 4、Core ML 混合精度固定 batch 1 均通过，完整 366 输入实测及 8 份预览已交付。**
分类与代表质量：**已人工验收，达到用户要求**（2026-09-11）。
用户原话：“我验收了384的这个，我觉得挺好的，达到我的要求。你继续验下一轮，然后这轮的结果可以留档。”
比较结论：满足要求；用户未进一步断言质量严格优于或数值等同于 512。156／99 两档结果均保留，未选择生产默认粒度。
页面、指标和原 closeout 保留生成时状态；人工结论以本报告为准。
技术判断：**384 的正确性和效率检查通过，人工质量也已获认可，支持将这条输入配方作为后续接入依据。**
收官人工决定（2026-09-11）：**DINOv3 是用户最终首选方案**；本轮 384px 已通过人工验收。
用户补充：“我最终还是最喜欢dino v3 的方案它综合了效率和实际效果，在人工检验上拥有一流的肉眼效果。”
这是用户完成跨模型比较后的明确偏好；完整四模型实测与 2 万张推算表见
[调研收官结论](../../../readme/model-evaluation.md#本轮调研收官2-万张照片的质量与效率取舍)。
本轮没有替换生产模型或决定生产默认粒度。

同口径新实测中，Core ML 编码从 14.87 s 降至 **9.34 s（少 37.20%）**；
MPS 从 21.64 s 降至 **12.01 s（少 44.50%）**。进程峰值 RSS 基本不变，未测总统一内存。
这次缩小的是输入尺寸，**同一权重、同一 85,641,216 个参数**；不是更小参数模型，
也不表示跨模型家族没有更好的候选。MobileCLIP2-S2 的结论是**值得下一轮接入测试**，本轮只查资料。

## 人工查看入口

每条运行时每个尺寸只编码一次；0.85 页面复用该次向量，明确显示“新编码 0”，没有新增性能成绩。
下面的 512 页面是本轮同口径计时的新输出，原 512 页面、向量和人工认可仍保留。

| 运行时 | 尺度 | 384 候选 | 512 同口径参照 |
| --- | ---: | --- | --- |
| Core ML batch 1 | 0.311 | [156 组](outputs/384-coreml-batch1/preview/index.html) | [157 组](outputs/512-coreml-batch1/preview/index.html) |
| Core ML batch 1 | 0.85 | [99 组](outputs/384-coreml-batch1-085/preview/index.html) | [104 组](outputs/512-coreml-batch1-085/preview/index.html) |
| MPS batch 4 | 0.311 | [156 组](outputs/384-mps/preview/index.html) | [157 组](outputs/512-mps/preview/index.html) |
| MPS batch 4 | 0.85 | [99 组](outputs/384-mps-085/preview/index.html) | [103 组](outputs/512-mps-085/preview/index.html) |

优先查看 Core ML 候选的绝对路径：

```text
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260911-0953-dinov3-resolution-384/outputs/384-coreml-batch1/preview/index.html
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260911-0953-dinov3-resolution-384/outputs/384-coreml-batch1-085/preview/index.html
```

对应的 512 参照：

```text
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260911-0953-dinov3-resolution-384/outputs/512-coreml-batch1/preview/index.html
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260911-0953-dinov3-resolution-384/outputs/512-coreml-batch1-085/preview/index.html
```

原人工认可：[512 MPS 103 组](../260911-0031-dinov3-threshold-calibration/outputs/dinov3-085/preview/index.html)、
[512 MPS 157 组](../260910-2212-dinov3-vitb16-512/outputs/mps/preview/index.html)。

**新增用户决定已记录在[原人工反馈报告](../260911-0031-dinov3-threshold-calibration/report.md#追加人工决定接受-103104-的运行时差异)**：
用户接受 512、尺度 0.85 下 MPS 103／Core ML 104 的差异；仅一个 56 成员组拆为 1＋55，其余 102 组成员和代表相同。
本轮没有再调查或修改这一差异，也不调参强求一致；这个决定不豁免非有限值、输入错位等实质错误。

384 两条运行时在两档尺度下的组成员、代表、视频选中帧和边界结果相同。
相对 512，0.311 有 **153 组成员完全相同，代表也相同**；0.85 相对 MPS 103 组有 86 组成员相同，
相对 Core ML 104 组有 87 组相同，两种对照各有 1 个成员相同的组换了代表。
这些只是定位信息，不是自动质量评分，也不能从组数接近推定质量保持。
可优先展开 0.311 的 512 第 145 组与 384 第 143–144 组；0.85 的 512 Core ML 第 20、44、73–74 组
与 384 第 18–19、41–42、67–69 组。完整定位摘要见[结果核对](metrics/result-validation.json)。

## 冻结条件与实现

- 模型：`timm/vit_base_patch16_dinov3.lvd1689m`，revision `c6a5fb7d12bbd3cf3b0079253141c3332aaed7da`。
- 权重 SHA-256：`1f9ed8a2378d65e24bb710ba522ac9fa7be4e036d7aefb4384ce022833926332`；严格加载，同一 85,641,216 参数。
- 输出：`forward_features(pixel_values)[:, 0, :]`，最终 LayerNorm 后的 768 维 CLS；不混入 register 或 patch 平均，不训练头。
- 唯一模型配方变化：方形 512→384。Pillow RGB、无 EXIF 转置、ToImage uint8 → 双线性 antialias resize → FP32 rescale → ImageNet mean/std，无裁剪。
- CPU 参考和 MPS 均保留 timm 的 FP32 RoPE；MPS 仍为 FP32 参数／attention／归一化／残差，卷积／MLP FP16 autocast。Core ML 图遵循同一精度边界。
- patch：1024→576；CLS＋4 register 后 token：1029→581。参数量没有因此变化，不能按 token 比例承诺加速。

[适配器](../../shared/model_evaluation_dinov3.py)和原会话的[验证](../260910-2212-dinov3-vitb16-512/validate.py)、
[转换](../260910-2212-dinov3-vitb16-512/convert_coreml.py)读取配置尺寸，不复制 runner 或另开模型实现。
CPU 参考新增配方指纹，把权重、预处理、特征语义、timm 文件和 RoPE 策略绑定起来；
Core ML 转换与检查拒绝借用不同尺寸的参考。模型预处理和编码身份包含尺寸，384 未使用 512 向量。
新 512 对照向量与旧实测逐值相同，说明本轮参数化和计时没有改变已验证输出。

timm 与不可访问的 Meta checkpoint 的差异沿用[原技术 review](../260910-2212-dinov3-vitb16-512/report.md#接入与精度的技术-review)：
FP32 RoPE periods、省略原发布说明中的零 QKV bias；不声称已证明两种实现数值等价。
本轮不重试全 FP16、半精度残差或动态 batch。

Source: `/private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1`，完整 verifier 通过，1,759,421,497 bytes。
实际输入：`eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json`。
输入指纹：`2144fcd970052a44d20a378e3819b86b55345d0605b6d71ce073fc2dd5cd5ba0`。
2,134 个源媒体、167 个业务候选、99 张图片＋267 个视频帧，**185 项准备失败原样保留**。
没有重新抽帧、修改素材或读取其他模型向量。安装版 MediaSense 0.9.0 的业务算法和代表选择逻辑未改。
0.311 配置绑定原 ChineseCLIP baseline_ref；0.85 绑定原先已建立的同尺度 ChineseCLIP 控制，旧基线不改写。

环境沿用 `/private/tmp/mediasense-dinov3-260910/venv/bin/python`：Python 3.13.5、torch 2.7.0、
torchvision 0.22.0、timm 1.0.20、coremltools 9.0；完整依赖身份在配置中，重建用[原依赖锁](../260910-2212-dinov3-vitb16-512/requirements.txt)。
Apple M5 Pro／48 GiB／macOS 26.4.1；2 个 CPU 线程、1 个 inter-op 线程、nice 10。
MPS 可用并实际执行，fallback=0；Core ML `ComputeUnit.ALL`，实际 CPU／GPU／ANE 调度未跟踪。
API endpoint: 推理离线；只有 MobileCLIP2 公开文本／源码资料访问，没有私人素材上传、付费推理或环境升级。

## 速度、阶段耗时与内存

以下每行都是一个新进程、同一 366 输入的完整实测，没有向量缓存、没有不计时预热。
运行顺序为 384 Core ML → 512 Core ML → 384 MPS → 512 MPS，模型运行不并发。
只各测一次，没有控制其他系统活动或建立方差区间，百分比是本机本轮观察。

| 分辨率／运行时／精度 | batch | 加载 s | 总编码 s | 输入/s | 读取＋RGB s | resize＋归一化＋组 batch s | 预测＋取回＋同步 s | 其余开销 s | 峰值进程 RSS GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 512／Core ML 混合 | 1 | 7.161 | 14.866 | 24.620 | 1.771 | 3.628 | 9.292 | 0.175 | 0.7758 |
| **384／Core ML 混合** | **1** | **7.192** | **9.335** | **39.206** | **1.653** | **2.749** | **4.807** | **0.127** | **0.7758** |
| 512／MPS 混合、FP32 参数 | 4 | 5.909 | 21.644 | 16.910 | 1.944 | 3.531 | 16.117 | 0.052 | 0.9650 |
| **384／MPS 混合、FP32 参数** | **4** | **6.274** | **12.012** | **30.469** | **1.958** | **3.023** | **6.988** | **0.044** | **0.9646** |

原始指标：[384 Core ML](metrics/384-coreml-batch1.json)、[512 Core ML](metrics/512-coreml-batch1.json)、
[384 MPS](metrics/384-mps.json)、[512 MPS](metrics/512-mps.json)。
Core ML 吞吐增加 59.25%，MPS 吞吐增加 80.18%；比较的是同一运行时／批量／混合精度下的分辨率变化。
本轮 MPS batch 4 与 Core ML batch 1 不是同批量运行时比较，不把两者差额全部归因于框架。

核对保留文件后的历史参照：ChineseCLIP Huge 224 CPU FP32 batch 4 **155.29 s**；
SigLIP 2 So400m 512 Core ML FP16 batch 1 **21.76 s**；DINOv3 512 MPS 混合 batch 4 **20.36 s**；
DINOv3 512 Core ML 混合 batch 1 **14.72 s**。历史成绩未改写；103 组重分组没有新速度成绩。
本轮 512 的不同时间反映重测条件与计时插桩影响，不能用一次差额估计插桩的纯成本。

### 计时口径与瓶颈判断

总编码仍由 runner 在每批同步前后计墙钟，含读取、RGB 解码、模型预处理、预测、CPU 结果取回与设备等待。
不含权重／输入校验、原视频抽帧、runner L2、写盘、分类和 HTML。加载含框架／适配器导入、权重／处理器、设备准备和同步，单独列出。

适配器内部逐图记录读取／RGB、处理器变换，并把 stack 计入预处理。GPU 输入转移、预测和取回统一计入预测阶段。
MPS 在 CPU 取回后额外执行一次 `mps.synchronize()`，runner 原有的外层同步仍保留；
额外同步和读取计时器的成本都在总时间内。Core ML predict 同步返回物化数组，未增加 GPU 异步推断。
文件关闭、Python 向量整理、计时器与外层同步等剩余成本归入“其余开销”；三阶段与开销之和严格等于总编码时间。
这是阶段墙钟归因，不是独立 GPU kernel profiling；不把 `.to()`、执行与等待重复累计。

512 的预测／取回／同步占比为 Core ML 62.50%、MPS 74.47%，是本轮首要成本；
降低尺寸主要改善了这一部分。384 时占比仍为 51.49%／58.17%，而读取＋预处理已达约 47.15%／41.46%。
因此输入尺寸探索有效；若之后继续挖 384 Core ML 效率，建议先有界验证预处理及 PyTorch／Torchvision 依赖开销能否减少，
并保持像素处理数值一致。它并不是当前唯一瓶颈。跨家族的小模型也仍值得独立试验，不能只看参数量或手机延迟。
本轮没有重写预处理、试其他尺寸、量化或改批量。

首批（仍包含在总编码）分别为 384 Core ML 0.091 s、512 Core ML 0.119 s、384 MPS 0.442 s、512 MPS 0.691 s。
运行前已做正确性验证；系统文件缓存与 Core ML 设备缓存不清空，权重／输入校验也会读取文件。
因此不是冷磁盘／首次设备部署基准，首批不等于纯编译时间。

RSS 为 `RUSAGE_SELF` 从进程启动到编码完成的高水位，包含加载，**排除子进程、Core ML 独立服务和未覆盖的 GPU 分配**。
同一模型不同尺寸的 RSS 基本不变；不能把未知的服务／GPU 内存当作节省，也不能据此得到总统一内存峰值。

## 正确性与转换证据

原先预定的门槛保持：对应向量余弦距离 ≤0.001、两两相似度误差 ≤0.002、
参考间隔 >0.005 的排序不反转、存储单位范数误差 ≤1e-6。不对 384 与 512 强加转换等价门槛。

| 检查 | 结果 |
| --- | --- |
| 384 CPU FP32 配方与 CLS | 与独立构造的 Meta resize 配方逐值相同；实测 N×581×768；直接 CLS、token-pool 与适配器一致，非 patch 平均。 |
| 固定 4 图片＋4 视频帧 | 单张／batch 4、重排、重复槽位、末批 2，CPU FP32、MPS FP32／有效混合精度与 Core ML 均通过。Core ML 多图片调用内部逐张预测，不证明原生批量。 |
| MPS 混合 vs CPU | 最大对应余弦距离 1.64e-6，最大两两差 0.000225，参考排序未变；hook 核对 MPS、FP16 Conv／MLP 与 FP32 attention／残差。 |
| Core ML vs CPU | 最大对应余弦距离 1.59e-6，最大两两差 0.000238；vs MPS 最大两两差 0.0000732，参考排序未变。 |
| 384 全量 MPS vs Core ML | 366×768 有限、顺序／身份完整，66,795 对最大两两差 **0.000366**，超限 0，对应最大距离 5.52e-7；366 个最近邻一致，参考间隔 >0.005 的反转 0。较深排序有 6,597 个位置变化，不声称全排序相同。 |
| 两档业务重放 | 保存向量重新分类与页面 groups.json 一致；两条 384 运行时的成员、代表和边界结果相同；185 失败、2,134 源、366 编码均正确。 |
| 512 插桩对照 | 新旧 MPS 向量一致；新旧 Core ML 向量一致。384 向量与 512 不同，预处理和编码指纹反映分辨率变化。 |
| 页面 | 8 页均通过本地 WebKit 打开、组展开／收起、视频展开、各 16 张图解码；每页 2,134 张唯一源卡片，全部本地链接及 2,118 张唯一缩略图通过文件／解码检查。截图只保留在 ignored outputs。 |

小样本证据：[Torch](metrics/correctness-384-torch.json)、[Core ML](metrics/correctness-384-coreml.json)。
全量与网页证据：[result-validation.json](metrics/result-validation.json)、[browser-validation.json](metrics/browser-validation.json)。
没有放宽容差或以代表／组数一致替代数值检查。

[384 转换记录](metrics/conversion-384.json)：源加载与样例 1.395 s、trace＋核对 2.934 s、转换 2.280 s、保存 0.040 s、包编译 0.119 s。
转换进程峰值 RSS 0.994 GiB，与编码进程分开。沿用固定 128 维 RoPE 的 `tensor_split → chunk` 导出替换，CPU trace 原始输出误差为零。
混合图包含 51 个 FP16、486 个 FP32 非常量输出，36 个检查到的 attention 计算输出均为 FP32。
固定 batch 1 的输入形状为 1×3×384×384；trace 形状告警只在这个固定形状范围内解释。
Core ML 缓存文件身份由[配置](config-384-coreml-batch1.json)固定；转换记录中“numerical validation pending”是转换时快照，最终通过状态见独立正确性记录。

模型包位于 `/private/tmp/mediasense-dinov3-260911/coreml-384-batch1`，512 继续使用原已编译包。
临时目录不是持久备份；丢失后按下面命令重建，使用新生成的包哈希和配置，不伪造旧编译文件身份。

## MobileCLIP2-S2：值得下一轮接入测试

理由是有明确的官方 checkpoint／推理方法、主流 OpenCLIP 包的精确型号集成，以及可固定的不同视觉家族。
这些足以支持一个有界实验；**还不能宣称它比 DINOv3 更好、更快或在 Mac 上即插即用**。
没有必要为凑候选再扩充模型目录。

| 证据类别 | 本轮实际核对与边界 |
| --- | --- |
| 官方发布规格 | `apple/MobileCLIP2-S2@72424e7025436db18f15c3eff6ee8c7c15ad4481`；官方表为视觉 **35.7M**＋文本 63.4M，FastViT `fastvit_mci2`，**256px、512 维**图像表示。参数是作者规格，本轮未实例化计数。 |
| 作者评测 | 官方表中 S2 的 ImageNet-1k zero-shot Top-1 **77.2%**、38 数据集平均 **64.1%**；第一代 S2 是 74.4%／63.7%。这是作者评测，不是独立复测，也不是本业务无监督聚合。3.6 ms 图像延迟是手机路线证据，不能当 Mac 速度。 |
| 主流社区实际集成 | 静态核对 **OpenCLIP 3.2.0** 发布 wheel：存在 `MobileCLIP2-S2.json` 与 `dfndr2b` 预训练入口，指向 `timm/MobileCLIP2-S2-OpenCLIP@ac6b37c8fc40b62b623d09ed228a6f0c9bc29fe6`。属于可用集成，不是独立 benchmark。 |
| 其他采用线索 | `RuteNL/MobileCLIP2-S2-OpenCLIP-ONNX` 明确为精确 S2 的 ONNX 导出，并给出 Rust `open_clip_inference` 调用。没有从这一模型卡得到 Mac 成绩或独立质量比较；不以少量导出展示作为主要维护依据。 |
| Mac 部署条件 | 官方要求 eval 模式（有 BatchNorm）并在推理／导出前重参数化；社区可用 timm 的 `reparameterize_model`。下一轮应固定一条实现，先验证融合前后输出，再做 CPU→MPS；Core ML 仍要实测转换及单张输出。本轮未获得精确 S2 的现成 Core ML 包／Mac 吞吐／内存保证。 |
| 独立比较 | 有界检索没有取得可直接支持 S2 vs DINOv3-B／SigLIP 2 在图像聚合及 Mac 性能上的独立结果。模型卡反复转载作者表格不构成多份独立证据。 |

部署注意：OpenCLIP S2 配方为 mean=0／std=1、双线性、resize shortest，输入 256；
不能复用 DINO 的 ImageNet 归一化或 square-no-crop，也不能硬套 DINO 的 CLS 提取。
社区 S2 模型卡示例误写了 `MobileCLIP2-S0`，应以包内 S2 配置和固定发布为准。
官方卡的 Highlights 混有第一代 S2 与第二代 S4 的宣传，不能把它们移作第二代 S2 的竞品结论。
原官方 .pt 的 LFS 元数据 SHA-256 为 `37c2d839a856491f2fcc82c40dc28672dbd0907235b4cd4c38dfff6457f0c09f`，
398,071,149 bytes；仅获取元数据，**未下载权重、未安装 OpenCLIP、未接入或运行模型**。

来源：

- [Apple 研究页](https://machinelearning.apple.com/research/mobileclip2)与[论文 2508.20691](https://arxiv.org/abs/2508.20691)。研究页直接读取；本轮论文正文直连未成功，具体 S2 表使用固定官方模型卡。
- [官方固定发布](https://huggingface.co/apple/MobileCLIP2-S2/tree/72424e7025436db18f15c3eff6ee8c7c15ad4481)。
- [OpenCLIP 固定社区发布](https://huggingface.co/timm/MobileCLIP2-S2-OpenCLIP/tree/ac6b37c8fc40b62b623d09ed228a6f0c9bc29fe6)与[OpenCLIP 3.2.0](https://pypi.org/project/open_clip_torch/3.2.0/)。
- [第三方 ONNX 导出](https://huggingface.co/RuteNL/MobileCLIP2-S2-OpenCLIP-ONNX)。

GitHub／HF 直连超时后，公开模型卡及 API 从 `hf-mirror.com` 获取，OpenCLIP wheel 从清华 PyPI 镜像获取并核对 SHA-256。
wheel `e1f5b3ecbadb6d8ea64b1f887db23efee9739e7c0d0075a8a2a3cabae8fed8d1` 仅作静态阅读。
FiftyOne 页面为跳转目录，未确认精确 S2；Bing 返回无关结果，未采用。没有把这些访问缺口解释为模型不存在或维护薄弱。
[紧凑调研记录](metrics/mobileclip2-s2-research.json)保存版本、来源和本地文本哈希；原文留在 ignored `outputs/references/`。

## 复现与工程边界

工作目录：`/Users/chengyanru/repos/personal/mediasense`。所有输出和 summary 必须为新路径；下面用 `-repeat-01`，原结果不可覆盖。
已有环境、权重和编译包时，重新完整编码并生成两档预览：

```bash
for route in 384-coreml-batch1 512-coreml-batch1 384-mps 512-mps; do
  rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/shared/model_evaluation.py run \
    --config eval/sessions/260911-0953-dinov3-resolution-384/config-$route.json \
    --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
    --output eval/sessions/260911-0953-dinov3-resolution-384/outputs/$route-repeat-01 \
    --summary eval/sessions/260911-0953-dinov3-resolution-384/metrics/$route-repeat-01.json
done
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260911-0953-dinov3-resolution-384/preview_granularities.py --suffix=-repeat-01
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260911-0953-dinov3-resolution-384/audit_results.py --suffix=-repeat-01
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260911-0953-dinov3-resolution-384/check_pages.py --suffix=-repeat-01
```

本次实际运行没有 `-repeat-01` 后缀。`preview_granularities.py` 只编排共用 `preview --encoding`，
`audit_results.py` 复用原验证函数和分类器；没有第二份 runner。页面检查器的重建方法见[原报告](../260910-2212-dinov3-vitb16-512/report.md#复现命令)。

重跑 384 小样本并重建 Core ML 时：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/validate.py torch \
  --config eval/sessions/260911-0953-dinov3-resolution-384/config-384-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260911-0953-dinov3-resolution-384/outputs/validation-384-torch-repeat-01
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/convert_coreml.py \
  --config eval/sessions/260911-0953-dinov3-resolution-384/config-384-mps.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260911-0953-dinov3-resolution-384/outputs/validation-384-torch-repeat-01 \
  --output /private/tmp/mediasense-dinov3-260911/coreml-384-batch1-repeat-01 \
  --evidence eval/sessions/260911-0953-dinov3-resolution-384/outputs/conversion-384-repeat-01 --batches 1
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/sessions/260910-2212-dinov3-vitb16-512/validate.py coreml \
  --config eval/sessions/260911-0953-dinov3-resolution-384/outputs/conversion-384-repeat-01/config-coreml.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260911-0953-dinov3-resolution-384/outputs/validation-384-torch-repeat-01 \
  --output eval/sessions/260911-0953-dinov3-resolution-384/outputs/validation-384-coreml-repeat-01
```

重新编译后用新 `config-coreml.json` 执行 runner，另存其 0.85 配置；不要覆盖本次配置来伪造相同包身份。
Python 环境／权重丢失时按[原报告的固定来源与依赖重建步骤](../260910-2212-dinov3-vitb16-512/report.md#复现命令)，
不升级日常环境、不改 frozen inputs。源包 verifier 和 runner 的前后字节检查必须通过。

已完成：384 CPU／MPS／Core ML 正确性、两运行时各尺寸全量计时、两档预览、全量核对与页面检查、候选有界调研。
后续人工更新：384 已验收。原实验未开展：MobileCLIP2 接入、其他分辨率、量化、动态批量修复、预处理重写、生产模型替换。
旧邻居关系分析及旧跨模型 benchmark 大调研继续暂停。

保留限制：181 个可用视频只有 1–2 帧，**不能证明视频关键帧排序质量**；185 准备失败不修复。
素材为代理图片／稀疏帧，不代表原码流解码；小样本 CPU 参考不证明所有图像数值等价；单轮本机性能不是普遍速度保证。
生产模型端口、依赖发布、获取与缓存失效、长任务恢复、安装入口仍未接通；eval 成功和用户质量验收不等于生产替换获准。

代码起点 `97800edac4b15ea817d74326fe8d025ff6434a0f`，起始工作区干净；每次编码保存实际代码 SHA-256。
原始输出只在本地 `outputs/`，权重／编译包在 `/private/tmp`；Git 仅纳入代码、固定配置、报告和紧凑指标。
本轮代码、配置、报告和紧凑证据随本轮独立 Git 提交保存；生成 HTML、图片、向量和模型二进制不入库。
[收尾核对](metrics/closeout.json)保留提交前检查快照，最终提交号见交付说明。
