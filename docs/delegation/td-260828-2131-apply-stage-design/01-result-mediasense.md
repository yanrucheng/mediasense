---
id: "01-result-mediasense"
title: "MediaSense Apply Stage Design Result"
type: delegation
status: draft
created: 2026-08-28
updated: 2026-08-28
timezone: "Asia/Shanghai"
parent: "td-260828-2131-apply-stage-design"
depends-on:
  - "01-request-mediasense"
superseded-by: ""
---

# MediaSense Apply 阶段产品设计结果

## 结论

Apply 的职责不是预览或重新解释组织方案，而是把一个已经由 Human 确认并冻结的 Plan，安全、可恢复、可核验地变成真实文件效果。

本轮设计收敛为两个顶层业务实体和两个 Tool 责任边界：

```text
mediasense.apply.run   <-> 可变 Apply Run
mediasense.apply.read   -> 不可变 Apply Receipt
```

- Apply Run 管理准备、授权、执行、暂停、恢复、取消、验证和 Receipt 发布。
- Apply Receipt 永久记录实际发生的效果及其证据。
- Frozen Plan 是既有输入，不是 Apply 新实体。
- journal、锁、临时路径、数据库表、分片和差异披露的物理形态都是实现方法，不成为新的产品实体。
- Apply spec 与 reference handoff 保持 `review`，不转为 `active`；本轮不实现 Tool、Skill 或真实文件操作。

## 阶段边界

Plan 负责让用户查看组织后的实际效果，包括分区、成员、目录和名称。Apply 不重复提供组织预览，也不重新分组、改名、换目标或补做语义判断。

Apply 只接受一个完整、不可变、已经确认的 Frozen Plan。开始执行前，还必须绑定：

- Frozen Plan 及其内容身份；
- Frozen Plan 所引用的每个 `source_root_ref` 到当前本地根的映射；
- 实际目标父目录；
- 单一执行 profile，首版为 `move_originals`；
- 完整、确定性的逐项源到目标映射；
- 当前预检结果和 prepared-content identity；
- 对这份精确 prepared content 的可信 Human 授权。

Apply 不因现实冲突而修改 Frozen Plan。任何需要改变分组、文件名、目标语义或成员范围的情况都必须返回 Plan，而不是在 Apply 内临场修正。

## 标准流程

1. `prepare` 创建持久 Run，解析完整计划范围和多来源根绑定，全程不修改媒体。
2. Tool 验证 Frozen Plan、来源身份、目标身份、执行路径、容量、权限、碰撞、命名空间重叠、并发冲突、保真能力和 journal 可用性。
3. 若存在执行前阻塞项，保持零媒体变更，并一次性报告阻塞与恢复条件。
4. 无阻塞时，`status` 给出有界影响摘要以及精确 prepared revision 和 content identity。
5. Human 对这份精确准备内容授权；`execute` 绑定授权并开始文件效果。授权内容一旦变化，旧授权失效。
6. Tool 在每个文件效果边界重新检查易变条件，先持久记录意图，再以不可覆盖语义执行并记录观察结果。
7. 单项局部失败被隔离，其他相互独立且仍安全的操作继续；影响全局安全的错误立即停止发起新操作。
8. Run 对来源和目标后置条件进行验证，闭合计划全集、实际物化操作和 retain/exclude 无操作项。
9. 一旦 `execute` 已被接受，普通终态都发布不可变 Receipt。只有授权前取消且能够证明零媒体效果时可以没有 Receipt。
10. 在短期安全窗口内，用户可以对该次实际完成集合发起整次 rewind。rewind 创建新的反向 Run 和 Receipt，不改写原历史。

## Run 控制面

`mediasense.apply.run` 的公共动作固定为：

- `prepare`
- `status`
- `execute`
- `pause`
- `resume`
- `cancel`

`prepare` 互斥接受正向 Frozen Plan 或用于整次 rewind 的 Receipt。`prepare` 和 `execute` 具有请求幂等身份；相同身份配相同内容返回同一逻辑结果，相同身份配不同内容报告冲突。

`pause`、`resume` 和 `cancel` 是目标状态控制。接受控制请求不等于目标状态已经到达，权威状态由后续 `status` 给出。

Run 生命周期区分：

- `preparing`：无副作用检查进行中；
- `ready_for_authorization`：精确准备内容可供授权；
- `blocked`：首次文件效果前存在阻塞，保证零媒体变更；
- `executing`：已授权效果正在进行；
- `paused`：停止发起新效果，可继续；
- `needs_attention`：已经可能存在效果，自动推进因可恢复问题或新的 Human 决策而停止；
- `verifying`：不再发起正向效果，正在核对和封存事实；
- `closed`：Receipt 已发布并绑定；
- `cancelled`：授权前取消且已证明零效果；
- `failed`：无法恢复可信核算或 Receipt 发布，必须显式披露可能效果和接管限制。

## 跨文件系统保真与再次授权

同文件系统优先使用不覆盖的原子 rename 语义。跨文件系统不是静默 fallback，而是一条单独披露的执行路线：

1. 写入目标文件系统上的非最终位置；
2. 对内容进行逐字节验证；
3. 尽可能保留并核对时间、权限、扩展属性、Finder 标签，以及平台 profile 声明的其他用户相关属性；
4. 以不覆盖方式发布最终目标；
5. 只有前述条件满足后才删除对应源文件。

内容不一致永远不能作为可授权例外。如果任何用户相关属性无法保留：

- 对应源文件的删除立即阻塞；
- Run 记录受影响 Source Item、属性、预期值和实际值；
- 差异集合进入新的 prepared revision 和 content identity，旧执行授权不能复用；
- Human 必须先取得完整差异，再通过同一个 `execute` 边界重新授权；普通 `resume` 无权接受该风险；
- 获得授权后，Receipt 永久记录被接受的差异集合、差异集合身份和授权绑定；
- 未获得授权时，源文件保持存在，该项不得标记为 `completed_and_verified`。

稳定契约只要求差异披露由 Run 拥有、内容完整、读取有界、绑定内容身份且可由 Human 取得。内联、文件、分页或数据库投影都是可替换实现方法。

## 失败、恢复和并发

- 目标存在时拒绝覆盖，不自动追加父目录、改名或换目标。
- 实际文件系统的大小写、Unicode、路径限制、symlink、hard link、mount 和别名语义都属于安全检查。
- 两个活动 Run 不得同时改变重叠的源对象或最终目标。
- 写入 effect intent 后发生崩溃时，恢复必须观察源和目标事实再归类，不可盲目重放。
- 只有目标与精确 verification basis 匹配且源已不存在时，才能把已有目标认作此前完成。
- 目标盘断开、挂载身份改变、全局权限失效、journal 不可靠等全局风险停止新操作并进入可诊断状态。
- `cancel` 不自动反向移动已完成效果；它先让在途操作到达安全边界，再核算事实。
- Apply 创建的目录属于可观察效果。rewind 只删除由原 Run 创建、仍为空且未被外部改变的目录。

## Apply Receipt

Receipt 是执行事实的不可变权威，至少闭合：

- Run、Frozen Plan、prepared content、执行 profile 和授权绑定；
- 多来源根与实际目标绑定；
- Plan 全部 Source Item 的范围；
- 需要物化的全部操作及其唯一结果；
- retain/exclude 等无需物化的计划项；
- 每项执行前来源验证与执行后验证；
- 完成、失败、拒绝、未尝试和不确定计数；
- 创建目录、重试、恢复和资源事实；
- 内容与元数据保真 profile；
- 无法保留的具体属性、被接受的差异及其 Human 再授权；
- Receipt 自身的内容身份和 seal。

结果使用两条分离的事实轴：

- `completion: complete | incomplete` 表示计划操作是否全部完成并验证；
- `closure: automatic | human_cancelled` 表示本次封存如何结束。

`complete` 必须意味着每一项来源验证和后置验证都成功。存在失败、拒绝、未尝试或不确定项时不得报告完整。

大规模 Receipt 可以用确定性全集减异常集合或不可变物理分片压缩表示，但必须保持一个逻辑 Receipt、完整核算和可验证内容身份。物理分片不是新的业务实体。

## Apply Read

`mediasense.apply.read` 提供：

- `inspect`：读取一个精确 Receipt 的有界摘要；
- `traverse`：有界读取 `operations`、`exceptions`、`metadata_discrepancies` 或 `created_directories`。

读取操作必须绑定精确 `receipt_ref`。cursor 同时绑定 Receipt、section、筛选、顺序和位置，不能在后续页静默切换查询。Read 不改变历史，也不重新验证已经封存的事实。

## 本地持久化边界

Apply 只有两个权威生命周期：

```text
<apply-store>/
├── work.sqlite3
└── receipts/
    └── <receipt-artifact>/
        ├── receipt.json
        └── <optional immutable operation segments>
```

- Run store 保存可变生命周期、授权、幂等、journal、恢复和 Receipt 发布状态。
- Receipt store 保存独立可读、不可变的最终事实。
- store 必须独立于源卷和目标卷，以便任一媒体卷断开后仍可判断已发生效果和安全恢复方式。

上述路径是当前参考形态，不是跨实现格式承诺。SQLite 表、journal mode、临时文件、flush、锁、调度、并发度、分片阈值和差异披露载体均保持开放。

## AI Album 迁移判断

| 能力 | 判断 | MediaSense 处理 |
| --- | --- | --- |
| `original` 原媒体移动 | `preserved` | 首版 `move_originals` |
| 完整 bundle 展开 | `preserved` | Frozen Plan 全范围确定性展开 |
| cluster 层级目录树 | `preserved` | 按逻辑根和相对路径物化 |
| 默认保留 basename | `preserved` | 无 Plan override 时保持 |
| 已有目标父目录 | `preserved` | 允许，但最终目标必须无碰撞 |
| 完整 source-to-target 预计算 | `preserved` | 升级为 prepared content 与授权依据 |
| 并发操作和进度 | `preserved`，并加强 | 保留吞吐要求，提供可恢复业务进度 |
| 同文件系统 rename | `preserved` | 不覆盖、验证后置条件 |
| 同名自动追加父目录 | `intentionally_changed` | Apply 阻塞，不修改 Plan 名称 |
| 默认隐式唯一输出路径 | `intentionally_changed` | 实际目标进入 Human 授权 |
| 跨盘静默 copy-delete | `intentionally_changed` | 显式路线、逐字节验证、属性保真及损失再授权 |
| 可能覆盖既有目标 | `intentionally_changed` | 无条件拒绝计划外覆盖 |
| 失败仅打印或未聚合 | `intentionally_changed` | Run 与 Receipt 完整核算 |
| `thumbnail` / summary 预览 | `preserved`，但属于 Plan | Apply 不重复实现 |
| `print` cluster | `intentionally_changed`，且属于 Plan | 由 Frozen Plan 可读视图替代 |
| copy / relative link | deferred，尚不能宣称 preserved | 后续独立 profile 设计 |

迁移验收还必须比较吞吐、内存、用户操作量、中断成本、恢复复用和元数据保真；与历史输出不同不自动构成 regression。

## 交付物

- 流程澄清：[clarify-260828-2255-apply-stage-flow.md](/Users/chengyanru/repos/personal/mediasense/docs/clarify/clarify-260828-2255-apply-stage-flow.md)
- 参考交付：[design-260829-0038-apply-reference-handoff/index.md](/Users/chengyanru/repos/personal/mediasense/docs/design/design-260829-0038-apply-reference-handoff/index.md)
- Review 契约：[spec-260829-0050-apply/index.md](/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260829-0050-apply/index.md)
- Run Tool 候选：[apply-run.tool.json](/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260829-0050-apply/apply-run.tool.json)
- Receipt Schema 候选：[apply-receipt.schema.json](/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260829-0050-apply/apply-receipt.schema.json)
- Read Tool 候选：[apply-read.tool.json](/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260829-0050-apply/apply-read.tool.json)
- 生命周期示例：[lifecycle.mock.json](/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260829-0050-apply/lifecycle.mock.json)
- Receipt 示例：[receipt.mock.json](/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260829-0050-apply/receipt.mock.json)
- Read 示例：[read.mock.json](/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260829-0050-apply/read.mock.json)
- 契约测试：[test_apply_contract.py](/Users/chengyanru/repos/personal/mediasense/tests/test_apply_contract.py)

## Activation blockers

Apply 保持 `review`，仅保留以下两项 activation blocker：

1. PreCheck 正式提供可由 Apply 使用的逐 Source Item 验证依据及访问路径。
2. 跨文件系统的内容逐字节验证和声明元数据保真策略取得支持平台上的真实执行证据，包括属性损失阻塞与重新授权路径。

在这两项关闭前，不激活 Apply 契约，也不开始生产运行时实现。
