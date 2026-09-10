---
title: "ChineseCLIP 香港素材本地模型基线"
service_version: "MediaSense 0.8.0 installed encoder"
date: 2026-09-10
environment: "local macOS; CPU; isolated evaluation process"
model_id: "OFA-Sys/chinese-clip-vit-huge-patch14@503e16b560aff94c1922f13a86a7693d36957a4f"
dataset_version: "ai-album-hk-representative-v1"
purpose: "固定素材和 Hierarchical 方法，记录真实编码速度、内存并交付人工分类预览"
baseline_ref: null
---

技术执行：**真实编码已完成；Hierarchical 分类尚未执行，等待算法选择确认。**
分类质量：**待人工验收**。本会话还不是完整的分类基线。

人工比较结论：待定（更好／相当／更差／待定）。

简短意见：待填写。

本会话的配置见 [config.json](config.json)，操作方法统一维护在
[模型评测 runbook](../../../readme/model-evaluation.md)。API endpoint：无，完全本地。
原始媒体、帧、向量、预览与日志均为 local-only，不进入 Git。

## 已取得的真实结果

[编码摘要](metrics/encoding.json)记录本次观察及代码哈希；
[验证记录](metrics/validation.json)记录输入对应和单张／批量复核。

| 指标 | 实测 |
| --- | ---: |
| 源媒体 | 2,134 |
| 计划图片／帧输入 | 2,700 |
| 成功编码 | 2,697：1,851 张图片、846 个帧输入 |
| 已记录抽帧失败 | 3，均来自同一个故意损坏视频 |
| 未交代／遗漏 | 0 |
| 模型加载 | 28.604990 s |
| 编码时间 | 1,147.785283 s |
| 编码速度 | 2.349743 输入/s |
| 峰值编码进程 RSS | 4,080,992,256 bytes = 3.800720 GiB，不含子进程 |

环境实测为 Apple M5 Pro、48 GiB 统一内存、macOS 26.4.1（25E253）。
沿用已安装的 CPU / float32 / batch 4 配置，2 个 CPU 线程、nice 10；
该进程观察到 MPS 不可用，未切换设备或模型。计时包含读取、预处理、计算、
结果取回和同步，不含抽帧、校验、向量写盘、分类与预览。没有向量缓存命中或不计时预热。

当前可打开[输入核对页](outputs/baseline/input-preview/index.html)。它有 2,697 张卡片，
明确标记“尚未分类”，不能当作 Hierarchical 结果。所有缩略图可解码，5,394 个源／输入
链接均指向存在的本地文件，无外部页面资源；已查看抽样联系表。部分图片保留未转置的
EXIF 方向，预览与本次编码输入一致。自动 headless Chrome 在此执行环境中以 -6 退出，
未取得浏览器截图，因此不声称完成浏览器交互验收。

11 项针对性测试、ruff 和改动范围的 diff 检查通过。重新编码三个不同输入的单张和
批量形式，对照基线的最大绝对分量差不超过 2.39e-7；这是对应关系验证，不是质量评分。
这 6 次额外验证编码在独立进程中完成，不混入上述性能指标。重复使用已存在的输出目录
会在模型加载前被拒绝。

本次实际执行命令（该输出已存在；重跑请用新目录）：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py encode \
  --config eval/sessions/260910-0048-chineseclip-hk-baseline/config.json \
  --inputs eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-0048-chineseclip-hk-baseline/outputs/baseline
```

## 待确认与后续完成条件

MediaSense 中没有现成的 Hierarchical。已定位的历史实现是
`LinearHierarchicalCluster`，其视觉层按时间只比较相邻项，CLI 距离阈值为 0.311，
最小权重参数为 20。候选移植和边界测试已准备；本次建议每张图片／帧权重为 1，
不采用旧 bundle 权重、日期/GPS 层或语义命名。

按照用户“仓库中没有对应实现时先确认”的要求，本次没有自行启用该选择。
确认后更新 config 的分类选择，运行 runbook 中的 `preview` 命令；该动作引用本次真实
编码指标，生成完整分类树并写入 `metrics/baseline.json`。若用户指的是另一种算法，
先落实该实现与参数再分类，同一份已编码向量仍可用于这次收尾。

原包位于 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1`。
2026-09-10 的原包 verifier 检查中，列出的 SHA-256 全部匹配，但总大小为
3,188,639,936 bytes，超过 2 GB 上限。额外的 6,395 个文件包含后续测试副本、
缓存和预览。按原有 SHA256SUMS 的 10,607 条记录加清单自身，使用现有
`eval/shared/prepare_input.py` 重建独立的 10,608 文件副本，不改写原包，
也不采用其额外内容。本次输入仅取 media-manifest 的路径、类型与派生文件 SHA-256；
不采用历史 bundle、代表、metadata 缓存、分类名或向量。

独立副本的原包 verifier 已完整通过，逻辑大小准确匹配 1,759,421,497 bytes。
本次准备同时实际解码所有图片并探测每个视频，仅原有损坏视频失败。

源码起点：`b52535a9fa1021ba29c4e8431cc9ca5125ae4f22`。工作区另有产品线程
未提交修改；运行摘要将记录实际评测代码和已安装 encoder 的哈希。

这些素材是包中的缩小图片和稀疏代理视频，不能证明原始全码流的解码吞吐或画质。
历史输出只是比较材料，不是本次分类的正确答案。
