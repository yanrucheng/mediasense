---
title: "MobileCLIP2-S2：跨家族小视觉模型业务评测"
service_version: "MediaSense 0.9.0"
date: 2026-09-11
environment: "Apple M5 Pro; 48 GiB; isolated evaluation environment"
model_id: "apple/MobileCLIP2-S2@72424e7025436db18f15c3eff6ee8c7c15ad4481"
dataset_version: "frozen 366 business images/frames"
purpose: "在已认可 DINOv3-384 后实际测试更小跨家族视觉表示的效果、速度和内存"
baseline_ref: "260911-0953-dinov3-resolution-384; original ChineseCLIP runner controls"
---

技术验收：**MPS FP32 batch 4、Core ML FP32 固定 batch 1 通过完整 CPU 参考与业务核对**。
分类与代表选择：**已获得人工比较反馈：略差于 DINOv3**（2026-09-11，针对后继 99 组预览）。
用户描述差距可感知但不很显著，以 DINOv3 95 分、MobileCLIP2-S2 87–88 分作主观比喻；这不是标准化 benchmark。
尚未表达接受新模型替代 DINOv3 的决定。主要参照为已人工认可的 DINOv3-B/16 384px。
FP16 失败路线保留，不作为本次技术通过交付。


## 追加粒度预览：99 组（2026-09-11）

用户明确反馈 0.85／19 组“明显就太粗了”，希望看约百组，数量无需精确。
复用已通过全量检查的 MPS FP32 向量，仅调整视觉距离尺度：0.45→124 组，0.50→111 组，
0.55→**99 组**后停止。没有重编码、改池化、修改其他分类参数或生成新性能成绩。
原 144／19 组、编码向量和实测全部保留；99 组的后续人工反馈为**相对 DINOv3 略差**，见报告开头。
页面已通过本地 WebKit 的 99 组展开／收起、视频展开及 16 图加载；全部源卡片和图片链接另行核对，见
[重分组核对](metrics/granularity-validation.json)与[浏览器检查](metrics/browser-granularity.json)。

[99 组预览](outputs/mps-fp32-granularity/preview/index.html) · [固定配置](config-mps-fp32-granularity.json) ·
[参数试查](metrics/granularity-sweep.json) · [生成摘要](metrics/mps-fp32-granularity.json)。
为满足 runner 同参数参照检查，新增同为 0.55 的 ChineseCLIP 向量重分组控制，未修改原基线。
页面明确标注复用向量，新编码为 0；原编码性能单列为历史数据。

复现命令（工作目录为仓库根目录，新输出路径必须不存在）：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/shared/model_evaluation.py preview \
  --config eval/sessions/260911-1027-mobileclip2-s2/config-mps-fp32-granularity.json \
  --encoding eval/sessions/260911-1027-mobileclip2-s2/outputs/mps-fp32 \
  --output eval/sessions/260911-1027-mobileclip2-s2/outputs/mps-fp32-granularity-repeat-01 \
  --summary eval/sessions/260911-1027-mobileclip2-s2/metrics/mps-fp32-granularity-repeat-01.json
```

同尺度 ChineseCLIP 控制丢失时，可用以下命令重建到新路径，再将候选配置的 baseline_ref 绑定其新摘要：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/shared/model_evaluation.py preview \
  --config eval/sessions/260911-1027-mobileclip2-s2/config-chineseclip-granularity-control.json \
  --encoding eval/sessions/260910-1330-chineseclip-business-baseline/outputs/baseline \
  --output eval/sessions/260911-1027-mobileclip2-s2/outputs/chineseclip-granularity-control-repeat-01 \
  --summary eval/sessions/260911-1027-mobileclip2-s2/metrics/chineseclip-granularity-control-repeat-01.json
```

## 可人工验收的结果

建议优先查看 **0.311／144 组**，与已认可 DINOv3-384 的 156 组比较。0.85 的 **19 组**用于检查宽松尺度下是否合并过度。
同一尺度在不同模型上不保证同一粒度；本轮没有为了接近 99 组而调参。

| 路线 | 尺度 0.311 | 尺度 0.85 |
| --- | --- | --- |
| MobileCLIP2-S2 MPS FP32 batch 4 | [144 组](outputs/mps-fp32/preview/index.html) | [19 组](outputs/mps-fp32-085/preview/index.html) |
| MobileCLIP2-S2 Core ML FP32 batch 1 | [144 组](outputs/coreml-fp32/preview/index.html) | [19 组](outputs/coreml-fp32-085/preview/index.html) |
| 已验收 DINOv3-384 MPS | [156 组](../260911-0953-dinov3-resolution-384/outputs/384-mps/preview/index.html) | [99 组](../260911-0953-dinov3-resolution-384/outputs/384-mps-085/preview/index.html) |
| 已验收 DINOv3-384 Core ML | [156 组](../260911-0953-dinov3-resolution-384/outputs/384-coreml-batch1/preview/index.html) | [99 组](../260911-0953-dinov3-resolution-384/outputs/384-coreml-batch1-085/preview/index.html) |

候选 MPS 的绝对路径：

```text
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260911-1027-mobileclip2-s2/outputs/mps-fp32/preview/index.html
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260911-1027-mobileclip2-s2/outputs/mps-fp32-085/preview/index.html
```

两条有效路线的组成员、代表、视频选中帧与边界结果一致。0.311 下相对 DINO 有 132 组成员相同，
其中 1 组代表变化；其余主要是把 DINO 的较细组归并。0.85 下仅 7 组成员相同。
输入／预处理／特征路径与精度核对通过，这支持把 19 组视为表示与当前阈值策略的实际组合结果，
不证明模型“更好”或“更弱”，也不证明该尺度适合作为新模型默认值。
每条路线只真实编码一次有效 FP32 向量，0.85 用既有 preview 重分组，`performance=null`、新编码 0。

## 有效 FP32 路线与性能结论

完整 [CPU 参考核对](metrics/full-fp32.json)覆盖全部 366×512 向量与 66,795 对相似度。
MPS／Core ML 相对 CPU 最大两两差分别为 **8.45e-6／8.12e-6**；跨运行时 **6.72e-6**，超限对 0。
各路线最近邻 366/366 一致，参考间隔 >0.005 的排序反转 0。跨运行时仍有 24 个较深排序位置变化，未声称所有排序相同。
完整向量有限、单位范数误差 <1.6e-8、551 输入行顺序一致、366 编码槽位唯一；保存向量重放业务结果一致。
[业务核对](metrics/result-validation.json)及 [4 页本地 WebKit 检查](metrics/browser-validation.json)通过：
每页 2,134 张唯一源卡片、2,118 张唯一图片解码和本地链接检查，组展开／收起、视频展开、各 16 图实际浏览器加载通过。
图片和截图只留本地，没有上传。

| 模型／输入／有效精度 | batch | 加载 s | 编码 s | 输入/s | 读取＋RGB s | resize／crop／归一化 s | 预测＋取回＋同步 s | 其余开销 s | 峰值进程 RSS GiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DINOv3-B 384 MPS 混合 | 4 | 6.274 | 12.012 | 30.469 | 1.958 | 3.023 | 6.988 | 0.044 | 0.965 |
| MobileCLIP2-S2 256 MPS FP32 | 4 | 9.417 | **5.420** | **67.531** | 1.871 | 1.404 | 2.119 | 0.025 | **0.875** |
| DINOv3-B 384 Core ML 混合 | 1 | 7.192 | 9.335 | 39.206 | 1.653 | 2.749 | 4.807 | 0.127 | 0.776 |
| MobileCLIP2-S2 256 Core ML FP32 图 | 1 | 10.006 | **6.138** | **59.633** | 1.829 | 1.410 | 2.807 | 0.091 | **0.671** |

MobileCLIP2 的两条行来自本轮完整新编码；DINO 行为上一轮已核对保留实测，未在本轮重跑。
同运行时同批量下，MPS 编码少 **54.88%**，Core ML 少 **34.25%**。同时改变模型、256/384 输入、预处理、精度和依赖，
这是整体方案对比，不能把差额只归因于参数数量或运行时。未为 MPS batch 4 与 Core ML batch 1 做同批量因果比较。

**加载更慢，必须一起看**：加载＋编码为 MobileCLIP2 MPS 14.84 s、DINO MPS 18.29 s；
MobileCLIP2 Core ML 16.14 s、DINO Core ML 16.53 s。Core ML 单次启动后只处理这 366 张时，
整体收益约 0.38 s，而非编码阶段的 3.20 s；长驻复用加载更可能体现编码收益，但本轮没有测持久进程。
这里的合计仍不含校验、写盘、分类和 HTML，不是用户工作流总耗时。

MPS FP32 读取＋预处理占编码约 60.4%，Core ML FP32 约 52.8%，预测分别约 39.1%／45.7%。
如果用户认可质量，下一步效率工作优先有界研究读取、预处理及依赖／模型加载开销，不应只继续压缩模型计算。
本轮未重写预处理、量化或改批量。计时同 DINO 插桩方式，GPU 取回后真实同步，阶段与剩余开销之和等于总编码时间。
MPS FP32 首批 0.307 s，Core ML FP32 首批 0.097 s，包含在总时间里；无不计时 warmup。

失败／诊断实测另列，**不作为通过方案推荐**：MPS FP16 编码 4.924 s、Core ML FP16 6.033 s，
[全量门槛失败](metrics/full-fp16-failed.json)。完整 CPU FP32 参考编码 148.641 s，作为正确性参照，未生成质量结论。
所有路线都实际编码 366 项；没有缓存命中冒充吞吐。

Core ML FP32 [转换记录](metrics/conversion-coreml-fp32.json)：源加载／融合／样例 2.688 s，trace＋核对 3.436 s，
转换 1.737 s，保存 0.033 s，包编译 0.155 s；源为融合后的 FP32 图，输入输出固定 FP32、1×3×256×256。
[FP32 单张检查](metrics/correctness-coreml-fp32.json)与上面的全量参考均通过。编译包位于
`/private/tmp/mediasense-mobileclip2-260911/coreml-fp32-batch1`，配置固定包文件校验值。
初始 FP16 [转换记录](metrics/conversion-coreml.json)保留当时“验证待完成”的快照，不能用转换成功替代最终数值通过。

技术判断：**MobileCLIP2-S2 的 FP32 路线值得进行本轮人工质量验收**；若 144 组分类和代表达到要求，
它提供更低的编码成本。尚不能替代用户确认，也不能把 0.85 直接接成生产默认。384 已认可结果继续保留。

## 输入、实现与保留决定

用户已确认 DINOv3 384“挺好的，达到我的要求”；原 [384 报告](../260911-0953-dinov3-resolution-384/report.md)
已记录人工反馈，156／99 两档、全部实测、512 结果及此前认可均保留。没有替换生产模型或选择生产默认粒度。

本轮下载实际权重为 **apple/MobileCLIP2-S2**，官方 HF revision `72424e7025436db18f15c3eff6ee8c7c15ad4481`，
SHA-256 `37c2d839a856491f2fcc82c40dc28672dbd0907235b4cd4c38dfff6457f0c09f`，398,071,149 bytes。
原拟用社区重新打包的 safetensors，其 HF 文件端点持续超时；实际取得 ModelScope 镜像中的官方原始 .pt，
下载字节与上一轮固定的官方 HF LFS 校验值完全相同。没有换 checkpoint 或模型代次。
镜像提交为 `9b428c3d5b0eb80a1e83caf271d03314657c4f0f`；普通整文件传输停滞后，用现有 Range API
四路并发 8 MiB 分段下载成功；见[获取证据](metrics/model-acquisition.json)和[重建脚本](download_weights.py)。

实现仍只选择 **OpenCLIP 3.2.0 + timm 1.0.20**，通过 timm 自带 `checkpoint_filter_fn` 映射官方权重，
与 OpenCLIP `load_checkpoint` 使用同一映射，严格加载全部视觉键。`torch.load(weights_only=True)`，仅允许预期视觉／文本／logit 前缀。
性能适配器不实例化文本塔，加载时读入完整原始 state，提取视觉后释放。

原生输入 **256×256**，Pillow RGB（无 EXIF 转置），双线性 antialias 缩短边到 256 → CenterCrop 256 → ToTensor → mean=0/std=1。
调用 OpenCLIP 原处理器，独立 torchvision 配方逐值核对；不套用 DINO 方形无 crop 或 ImageNet 归一化。
输出是 FastViT 最终卷积 → 原生全局平均池化 → **原训练 1280→512 线性投影**，保留 bias；不是 CLS，也不是删除头后的 1280 维平均。
runner 负责 L2 归一化和 float32-le 保存。CPU 未融合视觉输出与完整 OpenCLIP `encode_image(normalize=False)` 逐值一致。

融合前视觉参数 **35,815,232**，CPU FP32 eval 模式 `timm.reparameterize_model` 后 **35,702,992**；
融合前后小样本最大相似度差 6.20e-7。融合去掉推理不再需要的分支／BN 参数，不是量化、训练或替换新头。
权重映射、特征路径、预处理、代码文件哈希和融合策略均进入[固定配置](config-mps.json)。

Source: `/private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1`；完整 verifier 通过，1,759,421,497 bytes。
冻结输入 `eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json`，指纹
`2144fcd970052a44d20a378e3819b86b55345d0605b6d71ce073fc2dd5cd5ba0`。
2,134 个源媒体、167 个业务候选、366 可编码图片／帧；185 既有准备失败保留，不重新抽帧。
沿用安装版 MediaSense 0.9.0 分组与代表选择，尺度固定为 0.311／0.85，不为匹配 DINO 组数调参。
0.311 baseline_ref 绑定原 ChineseCLIP；0.85 绑定既有同尺度 ChineseCLIP 重分组控制。

新环境 `/private/tmp/mediasense-mobileclip2-260911/venv/bin/python`，Python 3.13.5、torch 2.7.0、torchvision 0.22.0、
OpenCLIP 3.2.0、timm 1.0.20、coremltools 9.0，完整[依赖锁](requirements.txt)。
MediaSense 0.9.0 从原隔离环境复制已安装包，113 个文件逐字节核对，见[环境复制证据](metrics/installed-mediasense-copy.json)。
不用正在变化的产品源码，不升级 DINO 或日常环境。Apple M5 Pro／48 GiB、2 CPU 线程、1 inter-op、nice 10。
API endpoint: 只有公开模型／依赖下载；编码强制离线，私人素材不上传，没有远程／付费推理。

## 精度检查与工程经验

固定 4 图片＋4 帧，单张／batch4、重排、重复槽位和末批2；CPU FP32、MPS FP32／FP16 与 Core ML 固定单张小样本均通过。
门槛沿用原值：对应余弦距离 ≤0.001、两两差 ≤0.002、参考间隔 >0.005 不反转、单位范数误差 ≤1e-6。
MPS FP16 相对 CPU 小样本最大两两差 0.001290，Core ML FP16 为 0.001057。

**全量 FP16 未通过**：MPS／Core ML 66,795 对最大相似度差 0.004524，309 对超 0.002；最近邻 365/366 相同。
虽然二者尺度 0.311 都得到 144 组，不能据此覆盖数值失败。原 FP16 性能保留为失败路线实测，不作为技术通过结果推荐。
完整 CPU FP32 参考进一步确认：MPS FP16 相对 CPU 最大两两差 0.010208，695 对超限，21 次有明显间隔的反转；
Core ML FP16 最大两两差 0.008578，708 对超限，18 次反转。详见[全量 FP16 失败证据](metrics/full-fp16-failed.json)。
没有非有限值，但这并不足以通过门槛。随后限定只验证 FP32 GPU 路线，不放宽容差、不改阈值或展开多种混合精度。

有效路线和最终性能见下文收尾数据。Core ML 只固定 batch1，未测试动态批量。

## 复现与限制

共用入口仍为 `eval/shared/model_evaluation.py`，薄适配器为 [model_evaluation_mobileclip2.py](../../shared/model_evaluation_mobileclip2.py)。
[小样本验证](validate_mobileclip2.py)、[转换](convert_coreml.py)、[全量精度核对](validate_full_precision.py)、
[业务与页面资产核对](audit_results.py)复用原数值／分类检查函数；未复制整套 runner。
原数值比较器只把硬编码 768 改成输入维度，供 512 维复用，门槛和算法不变。

CPU 全量参考不做业务质量打分。视频仍只有 1–2 帧，不能证明关键帧排序质量；原准备失败保留。
单轮本机速度无方差区间；Core ML 允许 ALL，实际 CPU/GPU/ANE 调度未跟踪。
RSS 为编码进程从启动到编码完成的高水位，含加载，排除独立 Core ML 服务、子进程和未覆盖的 GPU 分配；总统一内存未知。
加载含导入／模型／融合／设备准备，编码含读取、预处理、预测、取回和同步；不含源校验、抽帧、L2、写盘、分类或 HTML。
无不计时预热，首批包含在总编码；系统文件和设备编译缓存未清空，非冷启动磁盘基准。

权重、编译包、图片、向量、HTML、原始日志在本地 ignored 目录；Git 保存代码、配置、报告和紧凑证据。
`/private/tmp` 不是长期备份；下载来源、哈希及重建步骤随会话保留。


### 可执行命令

工作目录 `/Users/chengyanru/repos/personal/mediasense`。已有固定环境、权重和编译包时，用新的 `-repeat-01` 路径运行：

```bash
for route in coreml-fp32 mps-fp32; do
  rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/shared/model_evaluation.py run \
    --config eval/sessions/260911-1027-mobileclip2-s2/config-$route.json \
    --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
    --output eval/sessions/260911-1027-mobileclip2-s2/outputs/$route-repeat-01 \
    --summary eval/sessions/260911-1027-mobileclip2-s2/metrics/$route-repeat-01.json
done
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/sessions/260911-1027-mobileclip2-s2/preview_granularities.py --suffix=-repeat-01
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/sessions/260911-1027-mobileclip2-s2/audit_results.py --suffix=-repeat-01
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/sessions/260911-1027-mobileclip2-s2/check_pages.py --suffix=-repeat-01
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/sessions/260911-1027-mobileclip2-s2/validate_full_precision.py \
  --runs mps-fp32-repeat-01 coreml-fp32-repeat-01 \
  --output eval/sessions/260911-1027-mobileclip2-s2/metrics/full-fp32-repeat-01.json
```

本次实际执行不带 `-repeat-01`。CPU 全量参考保留于 `outputs/cpu-fp32`；上面最后一步与它对照。
原始 FP16 配置为 `config-mps.json`／`config-coreml.json`，只供复现失败，不应误用为本轮推荐配置。
所有新 run、preview、summary 必须不存在；HTML 生成复用既有函数，不手工改分组。

重新验证及转换可用以下新路径：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/sessions/260911-1027-mobileclip2-s2/validate_mobileclip2.py torch \
  --config eval/sessions/260911-1027-mobileclip2-s2/config-mps-fp32.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260911-1027-mobileclip2-s2/outputs/validation-torch-repeat-01
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/sessions/260911-1027-mobileclip2-s2/convert_coreml.py \
  --config eval/sessions/260911-1027-mobileclip2-s2/config-mps-fp32.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260911-1027-mobileclip2-s2/outputs/validation-torch-repeat-01 \
  --output /private/tmp/mediasense-mobileclip2-260911/coreml-fp32-batch1-repeat-01 \
  --evidence eval/sessions/260911-1027-mobileclip2-s2/outputs/conversion-coreml-fp32-repeat-01 --precision float32
rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTORCH_ENABLE_MPS_FALLBACK=0 /private/tmp/mediasense-mobileclip2-260911/venv/bin/python eval/sessions/260911-1027-mobileclip2-s2/validate_mobileclip2.py coreml \
  --config eval/sessions/260911-1027-mobileclip2-s2/outputs/conversion-coreml-fp32-repeat-01/config-coreml.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --reference eval/sessions/260911-1027-mobileclip2-s2/outputs/validation-torch-repeat-01 \
  --output eval/sessions/260911-1027-mobileclip2-s2/outputs/validation-coreml-fp32-repeat-01
```

重建的编译模型使用转换器新生成的配置和文件哈希，另存两档参数，不覆盖旧配置。固定包丢失时不能用别的编译产物冒充原哈希。
CPU 全量参考若丢失，可用 `model_evaluation.py encode --config .../config-cpu-fp32.json --inputs <同一冻结清单> --output <新目录>` 重建，
同时让全量比较脚本引用重建的参考目录；不把 CPU 参考编码时间当作候选 GPU 成绩。

### 临时环境与模型资产恢复

新隔离环境建立命令：

```bash
rtk proxy uv venv --python /Users/chengyanru/.local/share/uv/python/cpython-3.13.5-macos-aarch64-none/bin/python3.13 /private/tmp/mediasense-mobileclip2-260911/venv
rtk proxy env UV_CACHE_DIR=/private/tmp/mediasense-mobileclip2-260911/uv-cache uv pip install \
  --python /private/tmp/mediasense-mobileclip2-260911/venv/bin/python \
  --index-url https://pypi.tuna.tsinghua.edu.cn/simple \
  -r eval/sessions/260911-1027-mobileclip2-s2/requirements.txt
```

环境已存在时不执行 venv 重建。依赖锁不含私有 MediaSense 0.9.0；本轮从原 DINO 隔离环境复制同版本
`site-packages/mediasense` 和 `mediasense-0.9.0.dist-info`（排除 pycache），保留目录结构，不通过源码导入。
可以复用这一经字节校验的安装包，或用原 0.9.0 wheel 恢复；必须通过配置中原业务代码 SHA-256 检查。
[复制记录](metrics/installed-mediasense-copy.json)给出确切源／目的路径与文件聚合指纹，原 DINO 环境的恢复说明见[原报告](../260910-2212-dinov3-vitb16-512/report.md#复现命令)。

权重按官方固定 SHA-256 恢复：

```bash
rtk proxy python3 eval/sessions/260911-1027-mobileclip2-s2/download_weights.py
```

该脚本不覆盖已有不匹配权重；存在匹配权重时只核验。分段临时文件、下载 header 均只留 `/private/tmp`。
checkpoint 中的其余四个固定文本文件可由前轮保留原文恢复：

```bash
rtk proxy python3 - <<'PYRESTORE'
from pathlib import Path
import hashlib, json
root = Path('/private/tmp/mediasense-mobileclip2-260911/checkpoint')
source = Path('eval/sessions/260911-0953-dinov3-resolution-384/outputs/references')
spec = json.loads(Path('eval/sessions/260911-1027-mobileclip2-s2/config-mps-fp32.json').read_text())['model']
for old, new in [('official-config.json','config.json'), ('official-card.md','official-README.md'), ('openclip-config.json','open_clip_config.json'), ('openclip-card.md','README.md')]:
    data = (source/old).read_bytes()
    assert hashlib.sha256(data).hexdigest() == spec['files_sha256'][new]
    target = root/new
    if target.exists():
        assert target.read_bytes() == data
    else:
        target.write_bytes(data)
PYRESTORE
```

原文也丢失时，从 `https://hf-mirror.com/apple/MobileCLIP2-S2/raw/72424e7025436db18f15c3eff6ee8c7c15ad4481/`
下载 `config.json`／`README.md`（后者保存为 `official-README.md`）；从
`https://hf-mirror.com/timm/MobileCLIP2-S2-OpenCLIP/raw/ac6b37c8fc40b62b623d09ed228a6f0c9bc29fe6/`
下载 `open_clip_config.json`／`README.md`。所有文件必须匹配配置哈希，下载元数据或缓存放 checkpoint 目录之外。
该目录实际采用官方 .pt，不应再添加另一个 safetensors 文件造成身份混淆。

### 收尾与保留范围

已完成：384 人工反馈留档；MobileCLIP2-S2 下载／固定身份、最薄适配、原图像投影与融合验证、
CPU FP32 全量参考、MPS／Core ML FP32 全量及两档预览、数值与页面检查。
未完成：新候选人工质量验收。没有生产模型替换、阈值校准、动态批量修复、量化或其他模型扩展。
旧邻居关系分析和广泛 benchmark 调研继续暂停。

共用 eval 的 18 项测试和本轮 Ruff 通过；最终版本提交仅包含本轮代码、配置、报告和紧凑证据，
原实验性能及页面不回写人工状态。原 384 closeout 的报告哈希是历史快照，不改写成新反馈后的哈希。
完整性与版本状态见本轮 [closeout.json](metrics/closeout.json) 和最终交付说明。

代码起点：`122af60f76aecd193c79bceaa843de46848809de`，初始工作区干净；每次编码保留实际源码 SHA-256。
本轮代码、配置、报告和紧凑证据随独立 Git 提交保存，提交号见最终交付；大文件不入库。


## 人工比较后的吞吐推算（2026-09-11）

用户反馈：“明显比之前的 Dino V3 差了一些。虽然不是很显著，但如果之前那个能打95分，这个可能就只有87、88分。”
这里按上下文将“W13的384像素”理解为 DINOv3 384。用户请求简单估算，不新增模型运行。

按既有同机 366 输入的实测吞吐线性外推：`20,000 / 输入每秒`。

| 路线 | DINOv3 384 | MobileCLIP2-S2 256 | 编码时间减少 |
| --- | ---: | ---: | ---: |
| MPS batch 4，DINO 混合／Mobile FP32 | 30.47 张/s；10分56秒 | 67.53 张/s；4分56秒 | 约 6 分钟，54.9% |
| Core ML batch 1，DINO 混合／Mobile FP32 | 39.21 张/s；8分30秒 | 59.63 张/s；5分35秒 | 约 2分55秒，34.3% |

若各取已有最快有效路线：DINO Core ML 约 8分30秒 → Mobile MPS 约 4分56秒，少约 3分34秒，
吞吐约 1.72 倍、编码时间少约 42%。这是两套方案整体比较，不能单独归因于模型或运行时。
模型加载另加约 6–10 秒／次。此推算包含每个输入的读取、RGB、预处理、预测与同步，
不含原视频抽帧、源遍历、校验、分类、HTML 等完整业务流程；原评测是代理图片与视频帧，
2 万张原图的大小、读取介质和持续运行状态不同会改变实际时间。它是量级估算，不是 2 万张实测。
99 组只重分组，不产生新吞吐。旧配置、向量、指标和页面不变。
