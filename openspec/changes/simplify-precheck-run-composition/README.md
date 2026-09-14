# 普通 Run 与局部准备：开发与验收

## 当前状态

2026-09-13，用户确认基础模型、完整显式请求方案及“局部修改参数、其余参数不变，派生分组允许随真实依赖变化”，随后明确授权正式开发与隔离安装验收。2026-09-14 独立验收发现冻结要求缺失后的恢复降级、源变化误分类及成本测量缺口；用户已授权本轮补修。两个行为问题、最终隔离入口及独立三次成本比较已完成自验；4096/8192 的 RSS 中位峰值较修正后的基线分别降低约 18.1%/18.4%，等待用户独立验收。此前约 25.1% 的 RSS 差异来自累计高水位记录，不能作为本轮独立 Run 比较。准确完成项见 [tasks.md](tasks.md)，实际证据及限制见 [acceptance.md](acceptance.md)。

当前 Run/Read 契约、Schema、示例与发布副本已据此改造。此前撤回提前实现的记录属于设计阶段，不限制本次已授权开发。日常安装升级和发布不在授权范围内。

## 已确认的目的与模型

```text
PreCheck：按明确配置准备证据、压缩呈现
├── Run A → 不可变 Result A
└── Run B → 不可变 Result B
    ├── 调用方完整声明输入与 Profile
    ├── 所选 T 使用新参数，其余使用声明的原参数
    └── 有效计算按真实依赖复用

Plan：解释证据、决定哪里需要调整、保留有依据的判断
```

[基础模型](../../../docs/model/model-260913-1408-precheck-basics.md)是唯一概念权威；本包不再定义一套模型。Profile 是值，改要求创建普通新 Run，中断恢复原 Run。代码和设计保持业务无关，不引入 Subrun、Profile 管理实体或迁移实体。

“允许其他分组变化”不等于允许改其他参数，也不要求全局重排。现有阈值与数量后备方法保持可替换；纯阈值算法不是这次已确认的额外要求。

## 阅读顺序与权威

| 位置 | 用途 |
| --- | --- |
| [proposal.md](proposal.md) | 目的、范围及影响 |
| [现有 Run 契约](../../../docs/spec/contract/precheck-run/index.md) | 当前普通 Run、Profile、输入、效果与失败的正式承诺 |
| [现有 Read 契约](../../../docs/spec/contract/precheck-read/index.md) | 当前读取、准备回读、Source Set 和来源对应的正式承诺 |
| [design.md](design.md) | 配置投影、边界处理、来源依据、内部职责与工程选择 |
| [specs/](specs/) | 本次行为增量及场景；不取代当前契约 |
| [tasks.md](tasks.md) | 具体文件边界、依赖顺序、通过标准和开发门槛 |
| [acceptance.md](acceptance.md) | 后续 Agent 必须实现的正反例、证据和通过标准 |

## 已采用的最小接口改动及必要性

| 改动 | 删除它会缺什么 |
| --- | --- |
| start.source_set / profile | 无法明确表达同一固定输入和完整局部处理要求，只能依赖隐式旧状态 |
| Profile.configuration_identity | 无法发现其他准备默认值已变化；也不必因此公开整份私有执行配置 |
| review include=preparation | 调用方不能从公开、不可变结果构造下一次完整请求 |
| Source Set.profile_scope | 大范围配置回读可能需要一次展开成千上万个引用，无法保持有界 |
| resolve.target_result_ref / correspondence | Plan 无法可靠地核对新旧来源，只能猜路径或复制旧引用 |

上述是请求、配置值与读取视图扩展；机器契约的唯一当前权威在 docs/spec/contract。Source Set 的 scope index 只指向某个 Result 内配置值的位置，没有独立身份或生命周期。Plan Work 继续使用当前契约的 inspect/create/update 和确认流程。

## 实施与验收

按 tasks 的依赖顺序落实正式契约、配置与范围冻结、能力复用、Run 执行与 Result 封存、公开读取和 Plan 接续。验收包括真实 Host 的正反例、恢复和留存、100000 成员分页、4096/8192 输入成本及隔离 wheel/CLI/MCP。文档和 Schema 检查只证明相应层级，不代替运行与安装证据。

普通缺输入与 unproven 对应按已定方案处理；如必须削弱旧 Result 留存、清空有效工作、扩大外部效果或改变局部参数语义，则带具体证据与用户讨论。所有生成媒体、数据库、原始轨迹及 wheel 留在 Git 之外，保留其他并行工作。

## 调查依据与限制

设计调查时 start 只有 action/dataset_ref/request_id/prior_result_ref；当时 Read 缺少完整配置回读和可靠跨 Result 对应。源项引用含 accounting Run 身份，不能复制旧引用。已有 WorkStore/producer 复用和不可变发布继续作为实现基础。

现有 build_adaptive_groups 的纯合成数量后备反例见 design；它证明范围外分组可能变化，不证明所有阈值算法都会如此。此前62项定向测试通过是历史机制证据；设计时旧500→3→200测试使用过期调用格式；本次已按当前契约修正并重跑。开发验收使用合成媒体和真实 Host/安装入口，不调用外部地图或模型；详细界限见 acceptance。
