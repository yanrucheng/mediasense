---
id: "reasoning"
title: "PreCheck 最小接口草图编写说明"
type: spec
status: draft
created: 2026-09-07
updated: 2026-09-07
timezone: "Asia/Shanghai"
parent: "spec-260907-0247-precheck-plan-handoff"
depends-on: []
superseded-by: ""
---

# 编写与复核记录

用户已接受单层 `progress` 和 `start` 的简化方向。正文按三个章节组织：Command
目录、通用字段约定、Command 示例。第二章集中维护字段语义，第三章保留具体输入输出，
不在不同 command 下重复定义同名字段。根据用户授权，本轮覆盖目录内全部九个 command，
维持文档提案，不改动运行代码或任何实际 Run。

通用约定只约束本页 PreCheck 接口，不创建一个强制所有 Tool 套用的返回模型、注册表或新实体。
新 command 按需要使用既有字段，不能把同名字段用于新含义；没有独立用途的字段不加入。

## `status` 字段审查

| 项目 | 判断 |
| --- | --- |
| `run_ref` 输入 | 保留，绑定一次独立执行；输出不回显。 |
| `action`、`outcome`、`dataset_ref` 回显 | 简化示意中省略。操作已由 command 选定，查询错误走 `error`。这不是宣称已安装 MCP 支持省略 `action`。 |
| `source_items` / `accounted` | 从默认进度移出。实现按 run_items 计数，含 excluded 等，不等于源媒体处理完成。对账能力仍须保留。 |
| `activity` / `current_work` | 删除包装层；当前阶段、单位、数量、推进时间直接放 `progress`。 |
| `processed` | 包含有效复用和已终结的局部失败，不能表示成功率，也不统计每次重试。 |
| `unit` | 保留。不同阶段的数量不一定表示文件，单靠数字不足以解释进度。 |
| `last_progress_at` | 保留。推进证据与健康心跳不同；不能仅凭时间推断失联。 |
| `liveness` | 不再作为常驻字段；长时间无进度、疑似失联仍通过 `reason` 和可用动作显式区分。 |
| `issues` | 按需保留现有局部失败摘要能力，避免 processed 将错误藏掉；无需复制 Work 或增加独立实体。 |
| `result` | 采用对话中后续建议：完成时直接展示 ref、coverage、readiness 的 Result 投影。摘要不独立持久化或重算。 |
| `integrity` | 省略成功响应中的常量；发布校验、读取校验和 Plan 入口拒绝不可信内容的保证仍在。 |

## 发现并补充的边界

- `null` 表示未知，不能按零处理；不同阶段不能拼出总体完成百分比。
- 一个阶段的不同计数单位不能合并；当前显示阶段不限制执行器未来并行处理能力。
- 进度冻结不等于执行失败；疑似失联不能被省略成无解释的 running。
- 局部失败仍需简短、带单位的摘要，跨阶段可见；不能一有局部失败就把整个 Run 标成 failed。
- `allowed_actions` 是能力提示，不是授权；确认暂停仍需附带真实的 confirmation 范围。
- `completed` 可以对应 blocked Result；必要限定从 Result 的 qualifications 投影。
- 查询失败与 Run 执行失败分开；status 不能自行启动、恢复或接管 worker。

## `start` 字段审查

- `dataset_ref` 指定对象；Dataset 已承载源目录与工作空间，不再重复这些路径。
- `request_id` 标识启动意图。相同 Dataset 的两次主动运行和一次超时重试必须可区分，
  所以不能只靠 dataset_ref 去重。该字段的责任和 run_ref 不同。
- 成功返回只需要 run_ref；不带瞬间就可能变化的 state，不复制 Dataset 或 Result。
- 成功仍要求持久化及执行器启动。相同请求的回放只保证同一 Run 身份，不重新启动它。
- 保留 prior_result_ref 替代 dataset_ref 的既有后继 Run 能力，不新增 successor command。
- 尚未讨论的启动高级配置不预先加入。维持当前规范的非生产、零 BC 口径，文档不新建兼容层。

## 其余 commands：功能保留与删减依据

| 边界 | 保留 | 简化及理由 |
| --- | --- | --- |
| pause / resume / cancel | 请求被接受与目标生效不同；真实 observed state、同 Run 恢复、竞态拒绝和取消不撤销外部效果 | 用通用 state 表达观察值，省 command / target_state / run_ref 回显，不以空响应掩盖尚未暂停。 |
| 源范围选择 | fingerprint、完整发现限制、大小/类型/样例证据、子目录展开与分页、精确选择、排除项对账 | 展平到一层 entries，每个目录可继续展开；name 从 path 得到，fingerprint 只出现一次，scan_generation 不再用作第二种身份。 |
| 外部授权 | 披露身份与 Geo 请求身份、完整坐标范围、Provider 与数据处理政策、请求上限、费用未知、保留方式、可信确认 | 不回显 skip_allowed=false 和重复 quantity/summary；原 disclosure 内未知字符串暂保留，避免无审查重写共享 Geo 合约。 |
| review | 全局互斥对账、辅助/排除/损坏条目、跨卡重复、代表/边界/异常/冲突 Evidence、逐卡观测状态、限定和下一步菜单 | 删除 closure_check=passed 及可计算等式；cards 简化命名；省零计数、空角色、恒定 represents 与重复 member count。 |
| expand | 源条目与 Evidence 两类选择、全部 include、16 ref 上限、原子拒绝、成员差异、provenance 与准备证据 | 外层已经绑定主体，内部不重复 kind/ref；保留选择器区分，不把所有内容强塞一个 JSON 字典。 |
| resolve | 精确集合表达式、稳定排序、两种校验身份、全量成员与核验事实、分页安全 | ordering 固定在合约；total 只保留 page 中一份，删除数组长度回显；未省核验或身份摘要。 |
| geo_summary | 坐标来源区别、冲突、精确选择规则、源集合、可追溯候选、诊断而非 Plan 门槛 | 用 page.total 代替重复 unique count，source_set 规则承载 dedup 解释；不擅自把旧粗 outcome 升级成双组件成功。 |
| 分页 | 相同 Result 与查询绑定、字节上限、完整项边界、全量续读和最终核对 | page 保留 total / next_cursor；删 returned 与 complete，byte_limit 停止原因按需保留。 |
| 运行诊断与费用 | Source Item 对账、已生效选择、Work 分类、错误类别、Provider 效果、历史复用与本次请求分离 | 用现有 status/read 操作的 include 按需展开，不新增诊断 Tool 或持久化实体。 |

复核 source_sets.py 后保留 source_set_identity 与 membership_identity：前者用于请求选择核对，
后者将 Result、规范化选择、完整成员绑定，当前消费者会重算，不是恒真字段。原 ordering、total、
page.complete 等消费者校验点必须在未来实现时随新字段映射保留检查，而非直接删校验代码。

源 Source Set 的 union/difference 和 geo_coordinate 虽未在主要示例重复展开，依然是保留能力。
若 compact view 返回不足以判断的内容，用精确 include/分页补齐，不省去来源、限定或异常说明。

## Human 已确认的 Geo 边界

用户明确决定：地点不是 PreCheck 到 Plan 的必备信息。服务不稳定时由 Tool 内部有限重试；
最终失败表示本次重试策略内无可继续尝试，逐照片保留缺口，Plan 按已有信息继续。
无坐标、双 no_result、最终失败或整批照片均无地点，不得仅因此使 Result readiness blocked。

该决定撤销前面对失败地点一律阻塞的建议。保留失败与查无结果的区别，二者都不能破坏合法
Result 的发布。它不授权 Agent 再尝试外部请求，也不改变取消、拒绝授权或效果不确定的处理。
正文复用既有 reverse_geocode_candidate 和统一 Observation 展示最小结果，不重新引入被清空
草案的 location 包装或未经确认的整体 available 语义。

正式实现需同步核对 foundation、PreCheck Run / Read、Skill 的地点前置门槛及旧 Result 检查：
需要的是逐项诚实记录，不是每项地点必须成功。已有明确失败记录不得被旧门槛重新阻塞。
本轮仍仅更新审核草案，不宣称 active 规范或安装版已经修改。

工程修复仍要同时规范化 fresh 与 legacy，解除投影器对 missing.value.component_outcomes 的依赖；
不能只删 value 后让投影失败。地址与附近地点的分别结果、来源和部分失败必须保留在已有
Result 证据结构中；聚合候选示例不许可丢弃组件记录，更不从旧聚合 missing 猜造未执行结果。
单独的 (0,0) 元数据归一化策略依然不是本决定的内容。

## 后续完成实现合约时的检查点

- 本页是审核用形状，不是完整的已发布传输 schema；需在实现前明确操作如何分派，不能让
  MCP 在没有 action 的情况下猜测操作，也不把 command 示意当作已实现 CLI。
- 运行期对账 / diagnostics include、范围选择 view、外部披露原子绑定已列入样例与约定。
  正式 schema 需将这些 extension 和 compact read 字段同步到安装资源与消费者，不保留隐式双语义。
- `issues` 摘要超过容量必须声明 issues_truncated，完整分类通过 status diagnostics 分页读取；
  具体容量上限和按需细节 schema 属于下一步实现合约工作，不用生产日志或路径当公共接口。
- 若一个阶段的工作集合在同一 Run 内被重新生成，不能跨集合误比较计数；届时应明确集合
  切换的公开解释，无需现在预先增加一套进度实体或 ID。
- 除疑似失联的明示例外，running 必须有执行器；确认其已经退出时应用真实的暂停恢复或失败机制，
  不能靠 reason 将 ownerless running 永久保留。
- 示例 JSON 的解析检查只证明语法和本页约定，不等于已运行端到端合约测试。
- 地点用例需覆盖无 GPS、双 no_result、重试后双失败、成功与失败混合，以及所有照片都无地点；
  在其他条件满足时均可 plan_ready。另测缺记录或非法 Observation 仍不能冒充完整可信 Result。
- 本文档达到九 command 的可审阅结构覆盖，不宣称穷举所有响应或字段枚举。
  示例里的 sha256 是占位值，正式 conformance 必须替换成可重算值。
