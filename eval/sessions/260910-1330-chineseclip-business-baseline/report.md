---
title: "ChineseCLIP 业务分组与代表选择基线"
service_version: "MediaSense 0.9.0"
date: 2026-09-10
environment: "local macOS; CPU"
model_id: "OFA-Sys/chinese-clip-vit-huge-patch14@503e16b560aff94c1922f13a86a7693d36957a4f"
dataset_version: "ai-album-hk-representative-v1"
purpose: "固定业务输入和分组、代表及视频关键帧选择，实测 embedding 业务效果"
baseline_ref: null
---

技术执行：**已完成，含明确输入准备失败**。人工质量：**已验收，当前展示效果可接受**。
验收日期：2026-09-10（Asia/Shanghai）。用户原话：“我觉得挺好，没什么问题。”
比较结论：待定（首份基线，无其他模型比较对象）。本次作为后续模型比较的参照。
验收覆盖用户查看的当前展示效果；既有抽帧失败和关键帧排序质量未获证明的限制仍保留。
生成时的 HTML 保留“待人工质量验收”快照，最新人工结论以本报告为准。

Source: `/private/tmp/mediasense-model-evaluation/ai-album-hk-representative-v1`。
API endpoint: 无；本地 producer 与纯业务函数，不调用远程。
Code: `17373fa926549b671d293bfcc1635a7de664629d`，加本会话 eval 适配修改。
原始媒体、SQLite、向量、缩略图与预览仅保留在 ignored outputs 中。

操作入口：[runbook](../../../readme/model-evaluation.md)。
旧编码证据：[先前会话](../260910-0048-chineseclip-hk-baseline/report.md)；输入不同，不作为可比业务基线。

## 实测与交付

[分类预览](outputs/baseline/preview/index.html) · [性能摘要](metrics/baseline.json) · [验证记录](metrics/validation.json)。

| 指标 | 实测 |
| --- | ---: |
| 源媒体／初始素材组 | 2,134／167 |
| 请求视觉材料的源媒体 | 281 |
| 计划编码输入（含失败占位） | 551 |
| 实际编码成功 | 366：99 张图像、267 个帧 |
| 输入准备失败 | 185：184 次抽帧、1 次容器探测 |
| 业务分组／已归属源媒体 | 117／2,134 |
| 未交代遗漏 | 0 |
| 模型加载 | 26.502734 s |
| 编码时间／吞吐 | 155.289815 s／2.356883 输入/s |
| 编码进程 RSS 高水位 | 3,075,702,784 bytes = 2.864471 GiB，不含子进程 |

实测机器仍为 M5 Pro、48 GiB、macOS 26.4.1。CPU／float32／batch 4／2 个 CPU 线程，
nice 10。模型权重与编码器保持原版本；安装版已由另一个产品线程更新至 0.9.0，
此次核对后使用其与仓库一致的业务代码，没有为评测升级依赖或替换模型。
加载与编码分开，编码含图片读取、预处理、计算、CPU 取回和同步，不含视频准备、
归一化写盘、分组或预览。无向量缓存命中，无不计时预热；内存不与 GPU 分配相加。

原次精确命令（输出已存在；复现请换新目录）：

```bash
rtk proxy env PYTHONDONTWRITEBYTECODE=1 /Users/chengyanru/.local/share/uv/tools/mediasense/bin/python eval/shared/model_evaluation.py run \
  --config eval/sessions/260910-1330-chineseclip-business-baseline/config.json \
  --inputs eval/sessions/260910-1330-chineseclip-business-baseline/outputs/prepared/inputs.json \
  --output eval/sessions/260910-1330-chineseclip-business-baseline/outputs/baseline \
  --summary eval/sessions/260910-1330-chineseclip-business-baseline/metrics/baseline.json
```

## 人工核对重点与限制

请先看组摘要中的代表、边界与差异较大样本，展开较大的组检查有无明显不同内容被合并；
再看各视频的候选帧、选中帧及失败。所有源成员均可展开，未请求编码的照片缩略图只供
人工查看，不能称为模型已经看过。初始素材组内未逐一编码成员的隐藏差异仍待人工判断。

本次直接复现当前业务 producer 的失败：184 次抽帧失败包含端点请求的 FFmpeg MJPEG
错误，另一个原有坏视频缺少 moov atom。没有用旧帧、近似端点或不同抽帧实现顶替。
失败优先代表按现有业务回退到组内可用成员，共发生一次，具体映射在 groups.json。
这些失败属于输入准备限制，不能直接归咎于 embedding 质量；完整源归属不证明帧覆盖完整。

181 个有可用帧的视频中，95 个只有 1 帧，86 个只有 2 帧。两帧的对称相似度会打平，
当前规则按稳定顺序取先者，因此**此基线不证明视频关键帧排序质量**。修复产品抽帧或
增加采样后须另建输入配方、重跑当前模型；本轮保留准确故障与结果供产品线程处理。
此包是稀疏代理素材，不能代表原始视频解码吞吐、帧流或画质。

## 技术验证

17 项针对性测试通过，覆盖框架无关的第二适配器、业务函数对照、代表回退、视频
身份与选中帧变化、参数变化拒绝比较、坏输出拒绝。固定真实向量再次分组与保留结果完全一致。
2,134 张源卡片无重复遗漏，2,118 份缩略图全部可解码，2,681 个原件／输入链接均存在。
系统 WebKit 使用隔离的非持久数据环境实际加载 file 页面，117 个组的展开／收起和
视频候选展开通过，抽查 16 张图片全部解码；页面截图已检查。Chrome 沙箱启动失败及
隔离启动超时未当作通过，超时实例已结束，专用 profile 无遗留浏览器进程。

评测是直接复用本地 producer 和纯业务算法的适配，不是完整 PreCheck 公共 Run 发布、
Plan 或 Apply 验收；没有远程请求、没有产品合约或生产代码改动。

独立从源重建第二份业务输入，得到相同指纹、366 个可编码输入与185 个准备失败；复现未读取首轮向量或抽帧缓存。

首次人工核对可优先展开组 044（201 个源）、022（136）、070（134）和 073（111），检查初始素材组内被省略的照片是否仍适合由当前代表概括。组号只用于定位，不是好坏排名。

## 2026-09-10 收尾验证

业务评测代码、配置、摘要与报告已保存在提交 `77e37ab`；本次核对基线记录的全部
9 份评测代码 SHA-256，均与该提交一致。原执行指纹继续描述当时版本，不改写为修复后的代码。

HTML 运行信息已改为读取编码时保存的 `runtime`，设备和精度优先采用 `effective_encoder`
的实际报告，batch 使用该次编码记录。18 项针对性测试及 Ruff 检查通过；新增回归覆盖
CPU、MPS／float16、实际报告与配置不同、文本转义，不把 MPS 可用当作本次使用 MPS。

本次仅修复展示并核对版本留存，未重新编码或生成原基线预览；原性能摘要、向量、
分组和人工验收保持原记录。图片、向量、HTML、缓存与日志继续留在被 Git 忽略的
`outputs/` 中，已确认没有该目录下的文件被 Git 跟踪。收尾验证另记于
`metrics/validation.json` 的 `closeout`，不覆盖原次验收结果及限制。
