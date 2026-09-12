## Status and authority

**仅完成开发规划；尚未获准开始开发。** 2026-09-12 用户确认方案 B，并要求“open spec 把这个后续的开发计划定好。但是先别开始，到要开发的时候跟我讲”。本包不授权修改生产代码、当前公开合约、安装环境或运行模型。开发者必须先报告计划就绪，取得后续明确的开始指示。

当前协议唯一权威仍为 [docs/spec/contract](../../../docs/spec/contract/index.md)。本包的 delta specs 和样例是拟议变更，不是已经激活的合约。模型选择与 B 方向已确认；停用后的缓存交付语义采用规划默认，确认边界见 [README](README.md)。

## Why

用户已选定 Freepik/nsfw_image_detector 和 NudeNet 640m，希望通过同一接入与读取方式取得不同模型各自提供的信息。当前生产端口及通用后处理只交付标签分数，丢失位置和同类多个实例；共用设备、批量及固定装配也无法表达两份已选配方的独立执行要求。

## What Changes

- 采用已确认的 B 方案：输入是明确的本地图片或视频帧与执行要求；输出是有定义的具名属性值及执行事实。首期属性为分类分布、累计概率、区域实例，复用现有 content_sensitivity Observation，不创建 Attribute 实体或另一份结果存储。
- 接入两份确切本地配方：Freepik 指定 revision、官方 448px、MPS FP32、batch 4；NudeNet 640m 指定权重、native 预处理/NMS/坐标规则、CPU FP32、batch 1。保留全部四类概率、累计概率以及全部 native 实例，不重新选型或重做人工质量验收。
- **BREAKING**：把 sensitivity 的固定双检测器/共用设备配置改为逐模型启停与有效配方配置；改变“启用必定要求两类一起执行”的承诺。默认仍关闭，Dataset 覆盖及 Run 快照保持明确。
- **BREAKING**：为 content_sensitivity 定义带类型和约束的新值分支，保留实际输入、标签体系、分数含义和坐标基准；同步封存、Read、语义校验和消费路径。旧 V1 名称及阈值不重释，旧 Result 不改写。
- 复用现有逐项 Work、依赖失效、批量执行和资源准入；把逐模型要求、实际后端及可证明的执行成本接入现有诊断。停用、未准备、成功无框、缺依赖和执行故障分别交代。
- 使旧结果及有效缓存的读取不依赖推理库或模型仍安装；升级模型/配方只重做有真实依赖的工作。
- 沿唯一安装 runbook 准备依赖、正式权重路径、发布快照和隔离安装验收。日常环境切换另有授权边界。

## Capabilities

### New Capabilities

无。没有新增公共 Tool、Skill、模型管理网页、注册中心、插件平台、服务或独立数据实体。

### Modified Capabilities

- `precheck-run-orchestration`：逐模型配置与输入/输出接入、资源要求、诚实执行状态、有效缓存与后继复用。
- `precheck-result-read`：具名属性值、模型特有含义、实际输入与实例位置、完整交付和无模型环境下的历史读取。
- `mediasense-distribution`：选定依赖/权重、逐模型诊断、旧配置迁移提示及正式 CLI/MCP 交付验证。

## Impact

- 合约候选变更：PreCheck Run、PreCheck Read/schema/属性义务及其包内发布副本；只在后续获准开发并完成合约审阅后采用。
- 实现落点：SensitivityDetector/SensitivityProducer、PrecheckExecutionConfig/编排、Result assembly/SQLite/历史投影、runtime 配置/装配/诊断。范围与依赖顺序见 [design](design.md) 和 [tasks](tasks.md)。
- 依赖与资产：Freepik 所需 Timm/Transformers 处理路径及其已验证依赖组合；640m 的固定本地权重与来源收据。生产不得导入 Downloads 或 eval 代码，运行不得自动下载或远程回退。
- 消费边界：Plan 读取并解释证据；分数不构成自动处理决策或远程授权。展示复用属性值和实际输入，不新建模型管理产品。
- 历史与迁移：沿现有零公开 API 兼容政策统一交付，不保留双路由/双写；保留封存数据和原有 V1 含义。实际接通与差异分类回填既有迁移台账，不用本计划宣称 implemented。
- 验收：见 [acceptance](acceptance.md)。本轮只验证计划包、引用和合成样例；实现测试、模型验证、构建与安装均未执行。
