---
title: "DINOv3 粒度适配：103 组人工验收与 157 组聚合参考"
service_version: "MediaSense 0.9.0"
date: 2026-09-11
environment: "local macOS; retained verified embeddings; no new inference"
model_id: "timm/vit_base_patch16_dinov3.lvd1689m@c6a5fb7d12bbd3cf3b0079253141c3332aaed7da"
dataset_version: "frozen ChineseCLIP business inputs; 366 vectors"
purpose: "记录用户对 103 组效果的明确认可、157 组聚合用途判断，以及同一向量复用与粒度适配的实现经验"
baseline_ref: "260910-2212-dinov3-vitb16-512"
---

技术执行：**103 组预览已生成并检查通过，复用已验证向量，没有重新编码。**
人工质量：**已验收**。人工比较结论：**更好，用户评价为“显著更好”**。
验收日期：2026-09-11（Asia/Shanghai）。本轮主要对比此前已认可的 SigLIP 2 分组方案；ChineseCLIP 保留为原始参照。

## 人工反馈与两种粒度的用途

用户查看 103 组页面后明确反馈：

> “不错，我肯定了这个效果是比之前那个还要强，就是它效果比之前那个好，然后效能比之前那个好，这个显著更好。”

用户同时说明：

> “你这103版本和那个一五几的版本，我觉得这103这版本证明它能力是很强的，一五几的那个版本很可能更合适作为一个Embedding聚合的结果。”

据此记录：

| 结果 | 固定视觉距离尺度 | 人工结论与保留用途 |
| --- | ---: | --- |
| **103 组** | **0.85** | 用户明确认可效果优于此前方案，并认为这证明了 DINOv3 的能力；作为本轮已验收的效果参照。 |
| **157 组** | **0.311** | 用户认为其很可能更适合作为 Embedding 聚合结果，保留为较细粒度的聚合候选。此用途判断保留“很可能”的限定。 |

103 组的认可没有淘汰 157 组，也没有将组数越少定义为越好。
本轮得到的经验是：同一表示可以支持不同粒度的业务结果，适合哪一种粒度取决于后续阅读、聚合或解释的目的。
两份结果分别由现有业务算法生成；它们的严格嵌套关系未在本次验收中确立。
用户反馈没有指定生产默认阈值，也没有要求替换生产模型或阶段合约。

用户最初看到 157 组时认为组内确为同类，但切分更细碎，尚不能判断好坏；
随后澄清 80–110 只是便于比较的粒度，核心关切是较细子组之间是否仍保留合理的相似关系。
本页记录其查看 103 组后的最新明确认可；邻居关系分析与公开 benchmark 调研仍按用户要求暂停，不作为本次验收依据。

HTML 和运行摘要保留生成时的“待人工验收”快照，最新人工结论以本报告为准。
原 157 组页面、配置、向量、性能摘要和历史技术收尾记录均保留。

## 追加人工决定：接受 103／104 的运行时差异

2026-09-11 用户明确接受：同一距离尺度 0.85 下，MPS 为 103 组，Core ML 为 104 组；
差异仅为一个 56 成员组拆成 1＋55，其余 102 组成员和代表相同。
用户认为差异太微弱，可以接受，无需继续更改。本记录依据用户已完成的验收决定，
不新增数值调查、不修复或调整阈值以强求一致；非有限值、输入错位和其他实质数值错误仍必须拒绝。
两条路线作为 512 粗粒度参照保留，没有选择生产默认配置。

## 可查看与复用的资产

- [已验收 103 组预览](outputs/dinov3-085/preview/index.html) · [固定配置](config-dinov3-085.json) · [生成摘要](metrics/dinov3-085.json)
- [原 157 组预览](../260910-2212-dinov3-vitb16-512/outputs/mps/preview/index.html) · [原配置](../260910-2212-dinov3-vitb16-512/config-mps.json)
- [DINOv3 编码、精度、Core ML 与性能的工程参考报告](../260910-2212-dinov3-vitb16-512/report.md)
- [此前已验收 SigLIP 2 预览](../260910-1717-siglip2-so400m-512/outputs/mps/preview/index.html)

103 组 HTML 的绝对路径：

```text
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260911-0031-dinov3-threshold-calibration/outputs/dinov3-085/preview/index.html
```

157 组 HTML 的绝对路径：

```text
/Users/chengyanru/repos/personal/mediasense/eval/sessions/260910-2212-dinov3-vitb16-512/outputs/mps/preview/index.html
```

## 本次实际执行与性能依据

实际输入继续绑定 `eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json`。
源 fixture 为 `/private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1`，本轮使用前完整 verifier 通过。
2,134 个源媒体、167 个分组候选、366 个有效向量、185 项准备失败保持原样。
输入指纹为 `2144fcd970052a44d20a378e3819b86b55345d0605b6d71ce073fc2dd5cd5ba0`。

向量直接来自原 DINOv3 `outputs/mps` 完整实测，文件 SHA-256 为
`0a4093d752e5349180d11d845a06721f3b3bc25dbb17fc5c1dd4217445c637ee`。
只将 `classification.profile.content_distance_scale` 从 0.311 改为 0.85；
模型、权重、512px 预处理、CLS 提取、向量归一化、源范围、时空参数、初始素材组、分组算法和代表选择规则均保持不变。
103 组结果由既有业务函数和 HTML 生成器产生，没有通过手工拼组达到某个数量。

为了保留 runner 的同参数比较检查，新配置的 `baseline_ref` 指向
[同为 0.85 的 ChineseCLIP 重分组控制](metrics/chineseclip-085.json)。该控制也复用旧向量，未改写原基线，
不成为新的已人工认可质量基线。用户主要比较的是 DINOv3／0.85 与此前 SigLIP 2／0.311 的实际方案效果；
这一判断包含模型与粒度配置的共同变化。

生成摘要明确记录 `encoding_reuse.newly_encoded = 0`、`reused_vectors = 366`、`performance = null`。
原编码实测单列于 `source_encoding_performance`，页面将其折叠标为“原编码实测，非本次测量”。
用户所认可的效能优势，其已有量测依据仍是原 DINOv3 评测：
MPS batch 4 编码 20.36 s（SigLIP 2 为 26.74 s），Core ML batch 1 为 14.72 s（SigLIP 2 为 21.76 s）。
完整运行条件和内存口径见原报告；103 组没有产生新的推理速度或内存实测。

103 组页面已由本地 WebKit 实际打开，检查 103 个组展开／收起、视频展开以及 16 张图片解码；
页面交代 2,134 个源媒体且无遗漏。原 157 组预览与向量校验值保持一致。
18 项共用 eval 测试通过，其中增加了复用提示、原性能标注、来源转义和“本轮新编码 0”的检查；相关 Ruff 检查通过。

API endpoint: 103 组生成不需要远程服务或模型推理；此前公开文献获取仅为已暂停的研究。
私人素材和截图保持本地。代码起点为 `46228e9e74be7893a61ac206c664663004421489` 加既有评测改动，
本轮重分组的实际代码指纹保存在摘要的 `classification_code`，原编码代码仍保存在原记录中。

## 保留的技术实现经验

| 经验 | 已验证实现与使用范围 |
| --- | --- |
| 将向量能力与分组粒度分开判断 | 103／157 使用同一份向量。分组数同时受到表示、视觉距离尺度、时空边界和组首比较的影响，单独的组数不能代表模型能力。103 的人工认可与 157 的聚合用途判断分别保留。 |
| 用已完成编码做可追溯重分组 | 共用入口支持 `preview --encoding <原编码目录>`。读取时核对完整编码身份、输入指纹、向量与行记录校验值；新配置和页面写到新目录，复用原分类算法与生成器。 |
| 复用不能变成新性能成绩 | 重分组摘要的 `performance` 为 null；原性能及其来源另存，页面明确说明复用向量、新编码为 0。需要新性能结果时仍须执行完整 `run`。 |
| 参数属于可替换的实验配方 | 本例只改一个视觉距离尺度。0.85 是已获认可的效果样例，0.311 保留较细聚合输出；两者均未升级为永久阈值或生产默认。 |
| 保留原始特征与真实精度边界 | 继续沿用最终 LayerNorm 后的 768 维 CLS、runner L2 归一化和固定 DINOv3 预处理。有效 MPS 路线为 FP16 卷积／MLP、FP32 attention／归一化／残差／RoPE；纯 FP16 溢出和 FP16 残差偏差已有复现证据。 |
| 转换支持范围随证据交付 | Core ML 固定单张已通过；导出中的固定维度 `tensor_split → chunk` 等价处理及验证方法保留。可变 batch 1／2／4 的设备编译失败继续作为限制，不从单张结果外推批量可用。 |

模型权重、timm 与官方实现差异、转换脚本、依赖锁和数值验证的权威技术记录继续维护在
[原 DINOv3 会话报告](../260910-2212-dinov3-vitb16-512/report.md)，本页只补充重分组经验与人工结论。
实际薄适配器位于 [model_evaluation_dinov3.py](../../shared/model_evaluation_dinov3.py)；
复用入口和展示实现分别位于 [model_evaluation.py](../../shared/model_evaluation.py) 与
[model_evaluation_business_preview.py](../../shared/model_evaluation_business_preview.py)。

## 复现 103 组

在仓库根目录执行。原向量和冻结输入须存在；输出与摘要使用尚不存在的新路径。
这里仅复用向量，不需要加载模型权重，也不执行 GPU 推理：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /private/tmp/mediasense-dinov3-260910/venv/bin/python eval/shared/model_evaluation.py preview \
  --config eval/sessions/260911-0031-dinov3-threshold-calibration/config-dinov3-085.json \
  --encoding eval/sessions/260910-2212-dinov3-vitb16-512/outputs/mps \
  --output eval/sessions/260911-0031-dinov3-threshold-calibration/outputs/dinov3-085-repeat-01 \
  --summary eval/sessions/260911-0031-dinov3-threshold-calibration/metrics/dinov3-085-repeat-01.json
```

`baseline_ref` 所需的 0.85 ChineseCLIP 控制摘要已保存在本会话；它绑定同一业务输入和分类参数。
若向量或输入丢失，应按原评测 runbook 恢复并校验，而不是生成不同素材来冒充本次结果。
共同操作说明仍在[唯一 runbook](../../../readme/model-evaluation.md)。

## 未完成工作与保留边界

邻居关系分析与公开 benchmark 调研按用户指示暂停，本次没有恢复执行，也未用其草稿支持人工结论。
邻居草稿中“首次重合前外部混合”的统计条件尚需修正：当前可能包含首次重合之后再次拆分时的事件，
恢复研究前需要修正并复核。89 组版本只是暂停前的探索产物，没有本次人工验收结论。

185 项准备失败与视频仅有 1–2 帧的限制继续有效，不能据此认证视频关键帧排序质量。
用户认可的是当前可见业务效果与既有实测方案效能；生产端口、模型发布、缓存失效和安装入口的集成验证仍属于后续工作。

本次更新仅保存人工反馈与工程经验，没有重新编码、重写旧向量或更改生产配置。
配置、报告与紧凑证据保留在仓库工作区，尚未提交；生成图片、HTML、向量、文献原文与原始日志继续排除在 Git 外。
历史 HTML、运行摘要和技术 closeout 保留执行时状态及校验值，后续人工意见由报告追加记录。
