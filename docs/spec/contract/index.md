---
id: "index-contract"
title: "MediaSense 当前合约"
type: index
status: active
created: 2026-09-09
updated: 2026-09-14
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "design-260825-2235D-precheck-compression-boundary"
superseded-by: ""
---

# MediaSense 当前合约

**所有新开发从这里开始。** 本目录是 MediaSense 对外合约的唯一当前权威位置。目录名表示接口职责，不表示版本；不要根据历史文件夹的日期选择合约。稳定目录采用用户指定的命名方式，不再创建带日期的平行当前规范。

第一里程碑固定的是开发必须遵守的承诺。**2026-09-09 第一里程碑已完成；2026-09-10 第二里程碑及验收补修已通过用户验收，以 0.9.0 发布。** 本目录中的 `active` 表示当前规范位置；实际构建、安装验证与认证范围另见迁移台账。

2026-09-11 用户授权 Agent 收敛并开发的吞吐/有效帧修复，补充 Run 的联合运行品质承诺和 Read 的请求位置/实际 PTS 含义。其独立验收见[变更计划](../../../openspec/changes/restore-precheck-throughput-and-coverage/acceptance.md)及[修复评测](../../../eval/sessions/260911-2128-precheck-throughput-recovery/report.md)。源码与隔离 wheel 的认证不等于日常 Host 已升级；不借用 0.9.0 的验收记录扩大当前安装的能力声明。

2026-09-12 用户确认 Plan 信息收集与可选工作保存进入研发。本次 **Plan Work 合约变更已定稿，源码及隔离 wheel/MCP 实现验收已完成**：支持可选工作说明、独立偏好更新、候选保留／整体替换／撤下，以及无候选的正常读取。最终确认保留预览 HTML 后聊天接受的方式。开发从[交接包](../../../openspec/changes/refine-plan-interaction/README.md)开始；[实现验收](../../../openspec/changes/refine-plan-interaction/acceptance.md)记录实际入口证据；日常安装与原注册启动链路已按确切 wheel 升级验证；现有 Agent 会话不能由磁盘或相同版本号推断已重载。

2026-09-12 用户复核收窄首轮验收：正常保存路径证据成立，但发现身份字段注入、非法结构错误分类、Preview 图片交付三处缺口。上述三项已通过用户独立复验；后续发现的 Preview 选定 Evidence 分页缺口也已获用户独立复核通过。2026-09-12 按用户授权完成日常安装升级，保留原 Python、extras、依赖和配置。当前契约承诺不变，详细证据见上述实现验收链接。

2026-09-13 本地敏感性扩展已按用户授权落定：逐模型启停、Freepik 四类/累计概率、NudeNet 640 完整区域实例、实际输入归属、停用缓存排除与无模型历史读取。源码及最终 wheel 的隔离 CLI/MCP 验收通过，见[实施验收记录](../../../openspec/changes/extend-local-sensitivity-observations/acceptance.md#实施验收记录2026-09-13)。本次未切换日常安装；原 Result 字节和 V1 阈值含义不变。 后续用户独立复核发现Read输入关联、未知加载错误分类和公共执行信息三项缺口；现已补修并通过定向及隔离自检，**整体验收待用户独立复验**，不以先前正常路径证据冒充边界已被用户接受。

2026-09-14 发布补记：用户授权合并当前两条开发线并升级日常安装，**0.11.0 已完成本地发布、日常 CLI 升级、原项目四个 Skills 同步及新 MCP Host 入口检查**。确切快照、资源摘要、依赖/配置保留、检查与回退边界见[能力台账](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md#2026-09-140110-合并发布与日常安装)。下述各包自验时点的“未发布/未切换”不代表当前安装状态；发布不扩大用户数据或成本验收范围，已加载 Agent 会话需要重新开启。

2026-09-13 第 6 包按已定案设计进入实现：Plan Work 当前接口统一保存 draft/candidate，普通 Tool 自动交付持续页面，并严格绑定 Work/revision 的最终确认。现行机器定义、Skill 与发布资源同步；源码、隔离安装和浏览器验证见[本包实施记录](../../../openspec/changes/review-plan-preview-delivery/acceptance.md)。日常安装未切换，Human 页面审阅和较弱 Agent 效果不由自动化检查代替。

2026-09-14，用户授权的普通 Run 与局部准备改造已落实到 Run/Read 正式契约、实现及隔离 CLI/MCP：完整 Profile、固定全量输入、互斥局部参数、按依赖复用、不可变准备回读和直接来源对应。Profile 仍是配置值，改要求创建新 Run，恢复继续原 Run；Plan 创建新 Work 并重新确认。功能和隔离入口自验已通过，但规模成本门槛尚未关闭：8192 项 RSS 较接手基线增加约 25.1%，待讨论进一步定位。确切构建、规模成本及验收界限见[实施验收](../../../openspec/changes/simplify-precheck-run-composition/acceptance.md)。这里的实现自验不宣称用户独立验收、日常安装升级或发布。

## 阅读入口

| 当前合约 | 用途 | 本轮变化 |
| --- | --- | --- |
| [厂商知识](manufacturer-knowledge/index.md) | 随包知识、用户 YAML 增量及运行快照 | 用户授权 B 方案；固定文件字段、替换/停用、条件、处理和交付语义，实际验证另记台账 |
| [PreCheck Read](precheck-read/index.md) | 分批读取材料路径、自身属性、压缩关系；调查明细和精确成员 | `review.items`、开放属性、选择已准备 Evidence、完整性和失败语义定稿 |
| [PreCheck Run](precheck-run/index.md) | 启动、控制和观察准备过程 | 控制接口沿用；补齐本期准备深度与生产接通要求 |
| [Geo Query](geo-query/index.md) | 有界、受授权的地理候选获取 | 输入和效果语义沿用；明确采集策略与证据投影的责任 |
| [Dataset Open](dataset-open/index.md) | 打开明确的 Dataset | 迁入稳定位置，语义沿用 |
| [Plan Work](plan-work/index.md) | 保存草案/候选、交付持续页面、按版本确认并冻结 | 第 6 包当前接口已同步；验证范围见本包实施记录，未切换日常安装 |
| [Frozen Plan](frozen-plan/index.md) | 冻结后的组织意图 | 迁入稳定位置，Source Set 含义沿用 |
| [组织 Profile](default-organization-profile/index.md) | 默认组织和命名策略 | 迁入稳定位置；明确翻译属于 Plan 判断 |
| [Apply](apply/index.md) | 已冻结计划的执行合约 | 仅迁入稳定位置，本轮不作全量审计 |

## 一份权威，三个表达用途

- `index.md` 解释业务语义、权限、范围、失败及扩展规则。
- `*.tool.json / *.schema.json` 是交换值的唯一机器定义；调用时按 action 校验响应。
- JSONC 是带说明的人工阅读示例，JSON 示例和测试验证合约。示例不是独立规范，也不能用来缩减合约承诺。

[概念模型](../../design/design-260825-2235-mediasense-information-architecture/design-260825-2235D-precheck-compression-boundary.md)解释“对象＋关系＋属性”；本目录定义如何调用和读取；[迁移台账](../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)记录能力处置及实际完成证据。三者各有职责，不互相复制完整定义。

## 开发与变更规则

1. 实现必须符合此处合约，不得为通过测试而自行删字段、改变归属或放宽承诺。发现矛盾应定位到具体条款，先解决矛盾。
2. 可替换算法、库、存储、并发和内部顺序。可以按已约定规则增加属性；不能用相同属性名改变单位、来源范围、状态或候选性质。
3. 改变公开含义、效果、必需能力或失败行为，需要明确的合约变更及用户授权。已授权的当前里程碑范围内，工程细节由实现者决定。
4. 不保留新旧公开路由、双写或兼容别名。零 API 兼容不表示开发者可以无审阅改变当前承诺。旧 Result 的封存字节保持不变。
5. 旧日期目录与 OpenSpec 旧变更包是历史材料，不是另一套当前规范。已有安装包内的 schema/Skill 副本是该版本发布快照，禁止独立创作。

## 两个里程碑

| 里程碑 | 完成定义 |
| --- | --- |
| 1：合约定稿 | 当前入口唯一；输入、输出、属性义务、准备深度、分页、错误、扩展和迁移处置明确；结构与语义正反例检查通过，并经用户验收 |
| 2：实现完成 | 代码、安装依赖/配置、生产装配、公开入口和返回全部符合当前合约；发布副本同步；相关实现和装配验证通过 |

第一里程碑固定承诺；第二里程碑已同步生产者、消费者、Host、测试和发布副本，并通过隔离安装验证及用户验收。0.9.0 是该不兼容 Read 协议的发布版本，CLI、MCP Host 和四个 Skill 应同版升级。验证范围、构建身份和仍未认证事项记录在既有迁移台账；不会保留永久的两套公开协议。

第一里程碑的离线检查入口：`rtk proxy .venv/bin/python -m pytest -q tests/test_contract_authority.py tests/test_precheck_read_contract.py`。它检查合约和合成证据，不运行 PreCheck、模型、地图服务或真实数据端到端验收。
