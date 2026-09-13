---
title: "Plan 信息充分性与例外处置行为验证"
service_version: "MediaSense 0.10.2"
date: 2026-09-13
environment: "isolated local macOS installation; synthetic datasets"
model_id: "gpt-6-astra, low; independent agents without parent history"
dataset_version: "config.json synthetic cases"
purpose: "Verify installed Profile delivery and independent Plan investigation and dispositions for acceptance packages 4 and 5"
baseline_ref: "260912-2333-hk-run-acceptance"
---

**源码修复、隔离 wheel 交付和代表性行为验证通过，待用户独立复验。** 默认组织规则已在实际安装的 Plan Skill 阅读入口交付；7 位独立 Agent 均实际读取了对应 Skill 和完整默认 Profile，并通过真实 MCP 完成规划。日常 CLI、原香港操作项目的 Skills 和业务 Plan 未切换或修订。

## 变更与权威

- [Plan Skill](../../../src/mediasense/_resources/skills/mediasense-plan/SKILL.md)明确按组织决定的影响选择调查、解释粗称仍可能缺失关键检索线索、处理未知与后续更正，并区分 condition、上下文、组织意图及执行可行性。
- 默认规则只维护在[现有 Profile](../../../docs/spec/contract/default-organization-profile/index.md)。Skill 引用其逐字随包副本 `references/default-organization-profile.md`，不再使用一个遗漏异常细则的独立摘要。同步方式是从权威文件复制；源码、显式安装目标和 wheel 都有字节一致性检查，引用可离线读取。
- 未修改任何 `docs/spec/contract/` 文档或 schema、Plan Tool、Apply、Result 或业务 Plan。无新的问题对象、评分机制、必问轮数或统一过滤策略。HTML 工程仍属第 6 包。

## 实际交付

基线 commit 为 `0794d3c9182793b7b25c1cac77793e3c97e42092`。从该 commit 的隔离导出加上明确选定的 Skill 和验证改动构建，没有夹带共享工作区第 1—3 包的在途修改。

最终产物保存在仓库忽略目录 `.local/acceptance-releases/260913-1214-plan-skill/candidate-02/`：

| 内容 | 身份或证据 |
| --- | --- |
| 最终 wheel | `wheel/mediasense-0.10.2-py3-none-any.whl`，SHA-256 `249398c2150fbf129a946c9822b174dab150bc57eff1efedc1386d8dfcd2b7ef` |
| Plan Skill | SHA-256 `16f15bb281460d05bdd61bb6b7ba1e3360757e1b1356c06a69d7a816d1842950` |
| 默认 Profile 副本 | SHA-256 `5f561a600a397e4ce96b3a57abf10ae3f2bc5c8c08b53f2bbc4bd50349523189`，与当前权威逐字一致 |
| 安装 | Python 3.11.13；core 依赖按导出的 lock 约束离线安装；不启用模型 extras、不改变日常配置 |
| 保留材料 | `source-identity.json`、不可变 source 导出、dependencies、wheel、venv、`behavior-recipe/`；最终评测配方与构建时配方分开保留，不改写旧构建身份 |

最初尝试 Python 3.13.5 隔离安装时，离线缓存缺少 `av==16.1.0`，安装失败。随后使用已有缓存的受支持 Python 3.11.13，未放开网络或下载依赖。这不认证日常 Python 3.13.5 加 embeddings 的升级组合。

## 行为结果

协调者使用 [review-guide.md](review-guide.md) 中预存的模拟用户事实，只回答被问到的范围。独立 Agent 从安装后的 Skill、用户原始请求和合成 Result 开始，不接收问题包、正确答案、预期提问或验收结论。它们自行选择 Read、图片打开、问题和候选；[metrics/combined.json](metrics/combined.json)保留实际资源读取行号、hash、会话身份、候选变化和调用摘要。

| 场景 | 实际行为与判定 |
| --- | --- |
| 旅行：用户知道餐厅，后来更正活动 | 首版和最终版各一位独立 Agent 都先主动问烧味店身份及酒与点心的活动背景；已有店名证据未逐店强制重问。用户最初说是晚餐前段时，Agent 识别品鉴卡、讲解者与时间所留下的竞争解释，保留可单独找回的粗入口。更正后通过真实 update 修改为酒店品酒班，相关两项范围明确，其余组不被扩散改名。 |
| 旅行：用户记不起、无补充资料 | 主动提问后接受信息边界，保留“烧肉饭晚餐（店名未定）”“酒与点心品鉴（场所未定）”，说明失去的检索线索；没有猜酒店或把品鉴混入晚餐，也没有宣称用户已接受粗称。 |
| 书展与散步：信息充分 | 无补问，直接形成两个浅层活动目录；遵守用户不细分展位的偏好，不为缺少城市、展馆或河流名阻挡候选。 |
| 混合目录：坏片、未决片、GPX 与控制标记 | 首版和最终版各一位独立 Agent 都读取三份独立可读样本，保留损坏原片与相关版本同组，同时注明代表来自另一相机且修复等价未认证。遮挡视频留在可信日期层，旅行坏片保留旅行上下文，无背景坏片和可读未决项分别兜底；GPX 入旅行辅助资料，`.albumignore` 留原处。12 项完整唯一对账。 |
| 非餐饮迁移：同一代表中的看展与体验课 | Agent 主动读取其他已准备图卡，发现四分钟跨度与共同代表不能证明同活动，并询问体验课身份。又主动询问 GPX 的来源；得知它是朋友另一次徒步后放入独立辅助资料位置，未强行归文化中心活动，未猜年份和日期。 |

7 位独立执行者共实际打开 **35 张合成图卡**；视频场景读取的是明确标注的 inline 合成样本。最终都有通过校验、尚未冻结的候选。共记录 **63 次业务调用**：27 次 PreCheck Read、36 次 Plan Work；另有 18 次 Host discovery，业务回执错误为 0。上述次数不含适配器连接时的 initialize/list/open；零次额外 Geo/provider、seal 或 Apply 调用。所有场景源字节和封存 Result hash 保持不变。

第一版行为审阅发现过宽的“无模型调用／费用”表述，部分进入 Candidate 说明。最终 Skill 补明“未额外调用 provider”与 Agent 自身模型使用不同；原 4 位 Agent 重读实际升级内容，分别修改报告或真实替换候选。随后两位新 Agent 重新执行旅行与异常场景，第三位执行非餐饮迁移。保留初版问题与修订过程，不把后续修正算成首版已经正确。当前 Agent 模型处理确实发生，未独立计量的传输、token 和费用为未知。

## 检查结果

| 检查 | 结果与范围 |
| --- | --- |
| Skill frontmatter／引用 | quick_validate 通过；本地引用可达；默认 Profile 源码、wheel、显式安装目标逐字相同 |
| 完整源码测试 | 第一版隔离 source：**1377 passed, 16 deselected**，243.55 秒；最终生产变动仅为同一 Skill 的效果报告说明，其余生产字节不变 |
| 最终安装版专项 | **169 passed**，11.14 秒；覆盖 Skill 安装／升级、Plan Work、Candidate、可选工作说明、Preview 和 Frozen Plan 原有语义 |
| 最终 wheel 分发 | `run_distribution_smoke.py` 的源码／wheel 比对、实际离线安装、Skill 安装、CLI、doctor 和真实 MCP 路径通过 |
| 行为与结果 | 7 次独立执行及后续修订的实际回执、图片打开和候选语义审阅通过；源／Result 不变检查通过 |

这里的 HTML 单元检查只证明已有路径没有因本次改动回归，不构成第 6 包自动交付修复。

## 复跑与本机证据

场景来自本目录 [config.json](config.json)，名称、图卡与用户回复均为合成材料，不使用真实香港媒体。MCP endpoint 是被选安装的 `mediasense mcp` stdio 子进程。runner 允许 Read 和未冻结 Plan Work，拒绝 Geo、Apply、seal 与调用方提供 authority；它不替 Agent 选择语义答案。

```sh
rtk proxy .local/acceptance-releases/260913-1214-plan-skill/candidate-02/venv/bin/python eval/sessions/260913-1214-plan-skill-behavior/run.py prepare --output /private/tmp/mediasense-plan-new-evaluation --host /Users/chengyanru/repos/personal/mediasense/.local/acceptance-releases/260913-1214-plan-skill/candidate-02/venv/bin/mediasense
rtk proxy .local/acceptance-releases/260913-1214-plan-skill/candidate-02/venv/bin/python eval/sessions/260913-1214-plan-skill-behavior/run.py verify --output /private/tmp/mediasense-plan-behavior-260913-final
rtk proxy .local/acceptance-releases/260913-1214-plan-skill/candidate-02/venv/bin/python .local/acceptance-releases/260913-1214-plan-skill/candidate-02/source/tests/run_distribution_smoke.py .local/acceptance-releases/260913-1214-plan-skill/candidate-02/wheel/mediasense-0.10.2-py3-none-any.whl --verify-only
```

复跑行为验证须另开无父上下文的 Agent，只给单个 `case.json`、`request.md`、安装后 Skill 和 public tool 调用入口；评测协调者单独持有 review-guide，不能将其作为提示发给执行者。`run.py verify` 只验证字节与汇总，不认证语义。

原始目录为 `/private/tmp/mediasense-plan-behavior-260913-1214`、`/private/tmp/mediasense-plan-behavior-260913-final` 和 `/private/tmp/mediasense-plan-behavior-260913-transfer`。已将完整快照保留在本 session 忽略的 `outputs/round1/`、`outputs/final/`、`outputs/transfer/`；session JSONL 的确切位置和读取前缀 hash 见 metrics。所有 raw reply、图片、数据库、日志和 wheel 均未加入 Git。

## 尚未认证

本次证明规则交付与代表性执行，不证明所有未来 Agent、真实照片或大型集合都同样成功；没有对照旧 Skill 做因果或统计收益实验。有限图卡全部读取不能证明大型集合的视觉预算效率。原香港业务 Plan 的新版本质量、真实人类最终接受、第 6 包页面交付、日常安装切换及当前原会话加载均不在本次通过声明内。
