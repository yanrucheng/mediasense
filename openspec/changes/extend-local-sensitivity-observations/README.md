# 本地 Nude/NSFW：方案 B 开发计划

## 状态与开始点

**2026-09-12 后续指示已授权开发、当前合约落定及隔离验收；日常部署不在授权内。**

用户明确接受 B 方案、D5-disabled（停用排除新 Result 中的缓存输出）及本包 handoff 信息含义与失败边界。准确字段、类型和工程拆分由实施者落定；以下规划时状态作为历史背景保留，由本段后续授权取代。

上一轮仅规划的边界与 A0 检查记录保留在 [acceptance](acceptance.md)。本轮不重开模型选择、人工质量评价或留出集；准确交换值已采用到当前 Run/Read/Dataset Open 合约。

| 项目 | 当前状态 |
| --- | --- |
| 模型与方法 | 已选 Freepik 固定 revision、448px、MPS FP32、batch 4；NudeNet 640m 固定权重、native、CPU FP32、batch 1 |
| 接口及归属 | B 方案；具名值继续属于 Source Item 的 Observation，绑定真实 Evidence；复用 Work/Run/Result |
| 停用后的缓存 | 用户明确接受 D5-disabled：停用模型的输出不进入新 Result，旧 Result/缓存保留，重启用可复用 |
| 精确交换值与失败边界 | 用户接受 handoff 含义/失败边界并授权工程细节；当前合约与纯语义校验已落实 |
| 开发与隔离验收 | 正常接入证据保留；三项边界已补修并完成287项定向检查与隔离MCP验证，整体验收待用户独立复验，见 acceptance |
| 日常安装、业务 Dataset、真实 Apply | 未授权、未执行；完成隔离验收后停在日常部署前 |

## 要交付什么

~~~text
本地敏感性证据
+-- 输入：有身份的已准备图片/视频帧 + 固定配方 + 执行约束
+-- 适配器：各自完成预处理、推理、后处理
|   +-- Freepik -> 分类分布 + 累计概率
|   `-- NudeNet 640 -> 部位实例（含同类多个框）
+-- 保存：Source Item 的 content_sensitivity Observation
|   `-- 绑定真实 input_evidence_ref、模型/配方、状态、依据与限制
`-- 输出读取：现有 precheck.read -> Plan 判断；展示按属性含义组织
~~~

“属性”是具名信息的表达，不增加独立 Attribute、注册中心、模型管理网页或公共 Tool。模型可以提供不同信息；没有提供的信息不能解释为阴性。模型/配方和信息类型可以扩展，但新含义需要明确声明和校验。

### 同一张图的可读结果

以下是合成图片 E（已定向，1000×1500）的示意，未运行模型：

| 来源 | 属性 | 返回的信息 |
| --- | --- | --- |
| Freepik | 分类分布 | neutral=0.05、low=0.15、medium=0.70、high=0.10；四类互斥 |
| Freepik | 累计概率 | at_least_low=0.95、at_least_medium=0.80、high=0.10；保留求和依据 |
| 640 | 部位实例 | FEMALE_BREAST_EXPOSED：0.91、框[100,300,220,430]；同标签另一实例：0.86、框[260,305,380,435]；FACE_FEMALE：0.98、框[170,60,320,250] |

框使用 E 的像素 xyxy。完整拟议 Observation 片段、无框、单模型关闭、局部失败、缺后端、复用、视频帧、模型分歧及旧 V1 共 11 个合成情形见 [handoff.examples.json](handoff.examples.json)。这些是人工审阅材料，不是当前 Tool 完整响应或真实模型质量证据。

资源另在执行部分表达：调用方给预算，配方/适配器声明需要什么，运行记录实际使用什么。Freepik 使用 MPS FP32、batch 4；640 使用 CPU FP32、batch 1；模型常驻资源不因一个批次结束而失去计账。结果读取不加载模型。

## 阅读与实施顺序

| 文件 | 用途 |
| --- | --- |
| [proposal.md](proposal.md) | 为什么改、哪些现有能力受影响、破坏性变更范围 |
| [design.md](design.md) | 输入输出、属性含义、配方、配置/停用、状态、资源、复用和迁移决定 |
| [handoff.examples.json](handoff.examples.json) | 正常及相反情形的拟议片段；只含合成数据 |
| [Run delta](specs/precheck-run-orchestration/spec.md) | 逐模型选择、适配器边界、执行/资源/复用和故障义务 |
| [Read delta](specs/precheck-result-read/spec.md) | 属性值、真实输入/实例位置、状态及历史读取义务 |
| [Distribution delta](specs/mediasense-distribution/spec.md) | 固定依赖/权重、诊断、配置迁移和安装交付义务 |
| [tasks.md](tasks.md) | 按依赖排序的开发任务；按本轮明确授权推进，勾选表示已完成的工程证据 |
| [acceptance.md](acceptance.md) | 当前规划校验与未来 V01—V12 验收、五输入技术子集及隔离安装范围 |

真正工作量集中在“模型输出→Observation”“配置→独立执行”“封存→历史与公共读取”三个连接处，再通过实际安装入口证明。沿用已有 Source Item/Evidence、Work/Run/Result、资源调度、Read 与安装机制；不为统一外观建立平台。

## 评测证据入口

工作区：`/Users/chengyanru/Downloads/mediasense-nsfw-eval-260912-1205`。下表路径相对于它；这里保留追溯入口和小文件身份，不将批量输出、媒体或模型复制进 Git。生产实现与配置不得依赖此 Downloads 路径。

| 证据 | 路径 | 本次只读核对 SHA-256 |
| --- | --- | --- |
| 人工整体反馈 | human/feedback-260912-161503-model-review.md | 34dbe26c493c004d86ef91df497731d50c1ca8b0dc6aed8449b323b69deb9288 |
| 分类配方 | classification/config.json | 849c574b4cc6f88359a01049197d32767e4e5b506e5571398c5e2e730fc428a6 |
| 分类实现参考 | classification/models.py | 93c4b02690203c6e0739bbaa63144a2c400ea48042a1b1b6c9be674007c98481 |
| Freepik 配方/身份 | runs/classification/freepik-mps-fp32-b4-dev-001/run.json | f31545175cca38514b93b766e882b3ee95723a3ffc8f90692c0a90f3e1341b3b |
| Freepik 原结果 | runs/classification/freepik-mps-fp32-b4-dev-001/results.jsonl | 6ff7b65f0d01c6c2d95a1c9710f4e9e49f57541f818acaf5339a05f4d7232caa |
| 640 实现参考 | scripts/detection/run_detection.py | c1770c1da11e2642bf1e90e9b8ab147696b18c6062ba34c7547cbafd809562c2 |
| 640 配方/身份 | runs/detection/nudenet640-native-dev-001/run.json | 59a8f64edcb8baabf8577cb5c2471907cb68f0fd50456090aec4d98bd11e693d |
| 640 原结果 | runs/detection/nudenet640-native-dev-001/results.jsonl | 49c875748ca9baf8783c9cb0ad1c7d9bb82c6de0e648f094d7bf8b1fa7749341 |

Freepik 使用 revision `15b85477e4fd2000db76ae9aae0f89a72f95e2e3`。640 权重 SHA-256 为 `04fe3d77980780c1f8297dc6d7f942fd5b3abe6942a188f742a85241e4f634eb`；来源收据是 models/detection/640m.onnx.receipt.json，固定镜像 SimonJoz/nudenet revision `2b20805bd4ab2a9edbbb99fa862f68411c00286a`。原评测未独立取得官方字节，这一来源限制保持，不伪称官方重新验证。

分类报告 classification/report.md、检测报告 runs/detection/report.md 及成本补测 costs/260912-1801-resources/ 解释技术边界。已有热处理数据为 Freepik 35 输入约 2.68 秒/13.1 输入每秒/进程物理内存峰值约 6.01 GiB，640 约 4.88 秒/7.2 输入每秒/约 0.36 GiB；模型资产约 165/99 MiB。它们不是完整产品耗时，不把不同内存口径相加；本轮不重测成本。

共同输入共 104（94 照片＋10 帧），开发集 35；留出 69 未推理。素材集中于同一主体，缺少日常负例和跨人物覆盖；人工反馈为整体定性评价，没有逐图真值。原素材、source-copy、prepared、原运行和反馈均保持只读。评测预览证明不同信息可以共同展示，不证明已有生产接口接通。

## 当前实现与权威的核对入口

- [当前属性义务](../../../docs/spec/contract/precheck-read/precheck-attributes.md)、[Run 合约](../../../docs/spec/contract/precheck-run/index.md)、[Read 合约](../../../docs/spec/contract/precheck-read/index.md)：新配置与值形状要显式修改，不能把当前开放属性规则当成既有实现完成。
- [迁移台账](../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)：已有敏感性能力/固定路由分离及当前 DINOv3 的真实状态；本包不重做旧系统审计、不以新模型覆盖旧验收范围。
- [安装 runbook](../../../readme/installation.md)：唯一安装/升级/回滚方法；打包 Skill copy 仅为发布快照。
- [模型评测 runbook](../../../readme/model-evaluation.md)：身份、配方、输入、计时与人工证据口径；本包仅使用其工程交接原则。

## 完成声明的范围

实施与隔离安装证据见 [acceptance](acceptance.md)。它们不证明日常 Host 已切换、
所有平台已认证或全量业务媒体性能；旧模型评价、参考输出和人工反馈均不改写。
