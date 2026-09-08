---
id: "spec-260907-0247-precheck-plan-handoff"
title: "MediaSense PreCheck 最小接口草图"
type: spec
status: draft
created: 2026-09-07
updated: 2026-09-08
timezone: "Asia/Shanghai"
parent: "index-spec"
depends-on:
  - "spec-260826-1546-precheck-read"
  - "spec-260827-1915A-precheck-run"
superseded-by: ""
tags: ["mediasense", "precheck", "contract"]
---

# PreCheck 最小接口草图

本页保留早期讨论过程。当前交换值以[Run 正式合约](../spec-260827-1915A-precheck-run/index.md)和[Read 正式合约](../spec-260826-1546-precheck-read/index.md)为准；本页省略与临时格式不再是实施依据。

以下 command 表示已选定的操作，JSON 只列当时讨论的业务参数。
示例中的文件、引用、计数和校验值均为假数据，不是现场 Run 的返回。

## 1. Command 目录

```text
PreCheck
├── mediasense.precheck.run
│   ├── start
│   ├── status
│   ├── pause
│   ├── resume
│   └── cancel
│
└── mediasense.precheck.read
    ├── review
    ├── expand
    ├── resolve
    └── geo_summary
```

| Command | 用途 |
| --- | --- |
| `start` | 开始一次 PreCheck。 |
| `status` | 看执行状态、当前进度和可用控制。 |
| `pause` | 请求暂停，保留继续执行的可能。 |
| `resume` | 恢复同一次执行，必要时提交当前确认决定。 |
| `cancel` | 结束同一次执行，不发布 Result。 |
| `review` | 看已发布 Result 的全貌和代表性证据。 |
| `expand` | 展开指定证据或源条目的细节。 |
| `resolve` | 取出一个集合中的精确源条目，供 Plan / Apply 使用。 |
| `geo_summary` | 检查地点证据覆盖和坐标复用，不发起新查询。 |

## 2. 通用字段约定

以下约定适用于本页的 PreCheck commands：同义同名、同名同义。
每个 command 只返回有用的字段，不要求所有返回都套同一个完整对象。

### 2.1 返回字段各自回答什么

| 字段 | 回答的问题 | 使用边界 |
| --- | --- | --- |
| `state` | 这次 Run 处于什么状态？ | 描述执行生命周期，不表示查询成功，也不表示 Result 可以进入 Plan。 |
| `progress` | 当前在做什么，处理了多少？ | 只放当前报告阶段的进度，不混入 Dataset 对账或执行器健康。 |
| `reason` | 为什么暂停、阻塞、失败，或需要注意？ | 解释 Run 的状态或异常情况；正常运行时不必出现。 |
| `allowed_actions` | 此刻可以尝试哪些控制？ | 只列改变状态的动作；不是授权，也不保证稍后执行时条件仍成立。 |
| `issues` | 哪些局部工作有问题？ | 保留局部失败，不把整次 Run 自动判为失败。 |
| `result` | 发布了哪份结果，是否能用？ | 只在 Result 已发布时出现；摘要从 Result 投影，不另算或存一份结论。 |
| `error` | 这次 command 为什么没能完成？ | 例如查不到 Run；与成功查到一个 `state: failed` 的 Run 不同。 |
| `confirmation` | 具体需要用户确认什么？ | 需要范围选择或外部请求授权时出现；不能只用一句 reason 代替完整确认内容。 |
| `accounting` | 源条目有没有被完整交代？ | 记录范围、处理条件和覆盖路径，与阶段进度分开。 |
| `execution_boundary` | 实际发生了哪些外部效果和成本？ | 仅按需审计读取，不作为 Plan 入场门槛。 |

`state` 必须有真实执行机制支撑。`running` 要有执行器；疑似失联必须明确报告。
`paused`、`blocked` 要有具体原因和恢复条件，不能用来掩盖未知程序错误。

### 2.2 `progress`：任务、单位、数量、时间

| 字段 | 固定含义 |
| --- | --- |
| `phase` | 当前报告的工作阶段，如地点查询、视频处理、发布结果。 |
| `unit` | 数的是什么，如地点查询、视频；不暴露内部 Work 身份。 |
| `processed` | 当前阶段已取得最终处理结论的单位数，包含有效复用、正常无结果和已终结的局部失败；等待重试的不算。 |
| `total` | 同一阶段、同一工作集合、同一单位下的总量。 |
| `last_progress_at` | 最近一次实际处理推进或阶段切换的时间；轮询和心跳不能刷新它。 |

- 数量非负且按单位去重，重试次数不能充当处理数量。已知时满足 `processed <= total`。
- 未知数量用 `null`，不能用 `0` 代替；尚无可证明的推进时间也用 `null`。时间包含时区。
- 阶段切换后重新计数；工作集合改变要说明，不能让调用方跨集合误比较。
- 不同阶段、不同单位的数量不能相加，也不能换算成整次 Run 的完成百分比或 ETA。
- `phase` 不规定算法、固定顺序或并行方式；这里显示当前报告阶段，不声称覆盖所有后台工作。
- 进度长时间不变不能单独证明失联。活性判断由 Tool 作出，需要注意时通过 `reason` 返回。

### 2.3 原因、局部问题与调用错误

`reason`、`issues` 中的每项和 `error` 都用 `code` 表达稳定类别，用 `message`
向人解释具体情况。Agent 根据 `code` 判断，不解析 `message` 措辞；不同含义不能复用同一个 code。

| 结构 | 额外信息 |
| --- | --- |
| `reason` | 有条件可恢复时，用 `resume_when` 说明可验证的恢复条件；这不是自动重试指令。 |
| `issues` 中的每项 | 用 `phase`、`unit`、`count` 说明在哪个阶段、有多少个什么对象受影响。 |
| `error` | 不伪造执行状态或 Result；必要时可附已知引用，例如重复启动时的已有 `run_ref`。 |

`issues.count` 在该类别内按 `unit` 去重，不同类别可能涉及同一对象，不能直接相加。
跨阶段未解决的问题不能因为当前阶段切换而消失。摘要应有界，不能无提示截断后冒充完整清单。

### 2.4 Result 摘要

| 字段 | 固定含义 |
| --- | --- |
| `ref` | 一份已发布、不可变的 Result 的引用。 |
| `coverage` | 声明范围的覆盖是否完整：`complete` / `partial`。 |
| `readiness` | 是否满足进入 Plan 的条件：`plan_ready` / `blocked`。 |
| `qualifications` | 存在覆盖缺口、阻塞或其他实质限制时，返回 Result 中对应的说明。 |

`completed` 只表示 Result 已发布；不保证 `coverage: complete` 或 `readiness: plan_ready`。
地点缺失、查无结果或有限重试后的查询失败，本身都不构成 `readiness: blocked`。
成功摘要省略恒为 `valid` 的 `integrity`。发布校验失败则没有 Result；发布后发现损坏，
读取时报错。省略字段不削弱完整性校验。

### 2.5 引用、重试与字段省略

| 字段 | 指向什么 |
| --- | --- |
| `dataset_ref` | 已打开的数据集；Dataset 已绑定源目录与工作空间。 |
| `run_ref` | 一次可暂停、恢复或取消的 PreCheck 执行。 |
| `result_ref` / `result.ref` | 一份已发布 Result；`prior_result_ref` 是作为新执行起点的旧 Result。 |
| `request_id` | 一次需要防止重复执行的调用意图；相同编号、相同输入安全重试，不产生第二次启动。 |

引用作为不透明标识使用，不从字符串推断路径或内部存储。新建对象返回引用；已知输入不做无意义回显。
`request_id` 与 `run_ref` 责任不同；只读查询不需要额外的重试编号。

字段不存在表示该分支不需要它；`null` 表示该数值或时间目前未知；`0` 表示确定为零。
分页续读标记的 `null` 是明确的“已读完”，按 2.7 的专门约定解释。
正常情况下省略 `reason`、无问题时省略 `issues`；终态省略 `allowed_actions` 表示没有新控制动作。
该省略规则不允许隐藏尚未解决的问题，也不能用省略代替未知计数。

### 2.6 控制请求：接受与生效

`pause`、`resume`、`cancel` 成功时返回接受请求后观察到的 `state`。
成功意味着该请求已被可靠接受，不保证目标状态已经达成；之后以 `status` 为准。
不再重复返回 command 已说明的目标状态，也不添加恒为 `true` 的 `accepted`。

目标已达成时，重复相同控制不产生第二次效果，也不需要 `request_id`。
后续已有相反控制或状态发生变化时，不盲目重放旧请求；先看 `status`，不兼容时返回
`invalid_state` 和当前状态、可用动作。控制不得把一个已发布 Result 改回 Run。

### 2.7 只读返回与分页

所有 `precheck.read` 操作绑定输入的确切 `result_ref`，不默认选择“最新结果”。
它们只读、本地、可重复，不改变源文件、Run、Result 或 Plan，也不执行 Provider / 模型请求。
批量输入中有一个无效引用或 include，整个请求报错，不伪装成部分读取成功。

| 字段 | 固定含义 |
| --- | --- |
| `include` | 明确要展开哪些细节；省略可选细节不等于删除其读取能力。 |
| `page.limit`（输入） | 单页条目数上限；实际还受返回字节限制。 |
| `page.cursor`（输入） | 上一页给出的不透明续读标记，不能自行构造或换到另一个查询。 |
| `page.total`（输出） | 整个所选集合的精确条目数；不是当前页长度。 |
| `page.next_cursor`（输出） | 有下一页时返回标记；`null` 明确表示本集合已读完。 |

省去可由数组长度得到的 `returned`，以及可由 `next_cursor` 得到的 `complete`。
保留按需的 `page.stop_reason: byte_limit`，使调用方知道小页是受字节限制而非项目不足；
达到数量上限和读完的情况由 limit、数组长度和 next_cursor 判断。
读完一页或一个集合不代表 Result 的 `coverage: complete`。
游标绑定 Result 内容、command、选择条件、include、排序和 limit，支持进程重启后继续；
任一绑定变化报 `invalid_cursor`。所有页读完前不能把已取到的子集用于完整成员交付。

| 操作 | 默认 / 最大单页数量 |
| --- | --- |
| `review` | 25 / 100 张证据卡 |
| `expand member_observations`、`geo_summary` | 50 / 200 项 |
| `resolve` | 250 / 1000 项 |

保留当前 524,288 字节返回上限。到数量或字节上限都在完整条目之间分页，不截断 JSON；
单条超限报 `response_item_too_large`。不能仅为减少字段而静默丢掉已请求的内容。

### 2.8 源条目、证据与观测

| 名称 | 含义 |
| --- | --- |
| Source Item | 一份实际源文件或辅助输入；每项都有 Result 内的引用和源相对定位。 |
| Evidence | 可查看的源内容或派生内容，例如代表照片、视频帧；可以代表多个 Source Items。 |
| `source_set` | 一个已有 Result 内的成员选择表达式，不是新的可变分组实体。 |
| `observations` | 源条目或证据的事实、候选与处理结果；不等于 Agent 判断或用户确认。 |

Evidence 代表多个源条目，不代表它们必须被 Plan 分成一组。精确成员由 `resolve` 取得，
不能拿一张卡的计数或样例路径代替。

| Observation 字段 | 用途 |
| --- | --- |
| `name` | 说明是什么观测；名称可扩展，不能换名掩盖同义概念。 |
| `status` | `available` / `missing` / `failed` / `not_checked` / `not_applicable`。 |
| `value` | 只有 `available` 才携带，且必须携带；其他状态禁止。 |
| `basis` | 解释依据；`failed` 必须有，不能用失败当成“没有查到”。 |
| `provenance` | 必要的来源、处理方法及版本，可追溯，不复制执行日志。 |
| `confidence` | 只有含义明确时才提供的置信信息，不虚构分数。 |
| `qualifications` | 实质限制；`effect` 区分 `limits_interpretation` 和 `blocks_use`。 |

`missing`、`failed` 等是成功读取的数据，不自动变成顶层 `error`。
按需展开时，不得丢弃已经记录的来源、置信度、失败、限制或成员差异。

源条目的 `scope` 与 `condition` 分开：前者表示 `source_media` / `auxiliary` / `excluded`，
后者表示 `usable` / `unsupported` / `invalid` / `error` / `unresolved`。
被排除不表示文件损坏，文件损坏也不意味着可以从清单中消失。

### 2.9 证据卡和精确成员

`review` 的卡片只汇总所代表成员的拍摄时间、媒体类型和已有证据角色；其他观测通过
`expand` 读取。时间保留时区和假设，既有观测状态全部计数；零计数可省略，
缺少观测记录记为 `unreported`，不能当作 `missing`。

证据角色 `representative`、`boundary`、`outlier`、`conflict` 只表示查看用途。
没有角色的已准备证据仍可展开，不能因精简界面而丢掉。相同源条目可能被多张卡代表，
所以跨卡成员数不能直接相加当作源文件总数。

`resolve.resolution.source_set_identity` 校验选中了哪个表达式；
`membership_identity` 校验 Result、选择表达式和完整有序成员。二者保留，每页一致，
最终与完整成员重算核对。计数、取齐成员和源内容核验各有用途，不能彼此替代。

### 2.10 确认与读取细节

`confirmation.kind` 区分源范围选择和外部效果授权。`inventory_fingerprint` 绑定具体发现清单，
`content_identity` 绑定具体授权披露；两者不是可以互换的“通用确认编号”。
确认内容变了就重新确认，不因为同一 Run 或曾经同意过而扩大权限。

外部请求的 `resume decision: proceed` 只是要求进入可信客户端确认流程；
客户端必须绑定精确披露取得 Human 确认，调用者不能自填 `authority`、`confirmed_by` 等证明。
关闭确认窗口不代表同意。已有密钥、`allowed_actions` 或 `request_id` 都不授予外部权限。

运行中的对账和执行诊断通过 `status include` 按需读取；已发布后的权威内容通过
`review` / `expand` / `resolve` 读取。普通 Plan 只依赖逐条证据和 Result readiness，
不需要了解 Provider、缓存、请求数或 acquisition groups。

### 2.11 地点是可缺失的信息

PreCheck 不要求每张照片都获得地点，才允许进入 Plan。无 GPS、地点查无结果、服务不稳定导致
查询最终失败，都是可以局部记录的信息缺口；照片仍保留在 Result 中，不能因此删除、排除它，
或把原本可用的照片判为不可用。即使所有照片都没有地点，也不能仅因此阻塞 Plan。

| 情况 | 对 Plan 的含义 | 记录方式 |
| --- | --- | --- |
| 没有可用坐标 | 没有地点信息 | 坐标缺失；地点获取未执行及其原因如实保留，不冒充查询已完成。 |
| 查询完成，但没有候选 | 没有地点信息 | 记录 `no_result` 的事实，候选 Observation 为 `missing`。 |
| 工具有限尝试后最终失败 | 没有地点信息，且知道获取失败了 | 候选 Observation 为 `failed`，带失败依据；不改写成 `no_result`。 |
| 只有部分地点信息可用 | 使用已有部分，并保留限制 | 保留可用候选，缺失或失败组件分别记录，不能升级为全部成功。 |

可重试的服务错误由确定性 Tool 在次数、时间及请求额度的有限边界内处理，且不得超出已经授予
的外部效果范围。最终返回失败，表示本次策略和授权内没有可继续的重试；不要求 Agent 接手
循环重试，也不要求 Plan 修复 PreCheck 的缺口。失败并不意味着将来服务永远无法恢复。
重试中仍是未结束的工作；最终失败计入 `processed`，并保留局部问题和实际请求成本。

这类信息缺口使用 `limits_interpretation` 说明；不因缺地点设置 `blocks_use`，也不自动将
`coverage` 改成 `partial`。是否完整覆盖仍由源范围对账决定，是否可进入 Plan 仍需满足其他条件。
Plan 可以利用时间、图像和用户意图继续组织，没有地点不强制补查、不强制问用户，更不能编造地点。

已知的查询失败是合法业务结果，可以发布。数据自相矛盾、丢失源项、无法确定已执行的外部效果等
问题仍按各自合约处理，不能借“地点可缺失”隐藏。正在等待用户授权也不能假装查询失败后继续；
本条不改变用户取消、拒绝授权或 Run 尚未结束的含义。

## 3. Command 示例

### 3.1 `status`

`status` 只回答三件事：这次 Run 现在是什么状态、正在做什么、调用方现在能做什么。

Command：

```text
mediasense.precheck.run status
```

输入：

```json
{
  "run_ref": "precheck-run:example-001"
}
```

返回格式：JSON。`state` 决定其余字段是否出现。

#### 正在运行

```json
{
  "state": "running",
  "progress": {
    "phase": "geo",
    "unit": "location_query",
    "processed": 120,
    "total": 225,
    "last_progress_at": "2026-09-07T02:10:00+08:00"
  },
  "allowed_actions": ["pause", "cancel"]
}
```

即：**正在查询地点，已处理 120 / 225 个查询；最近推进时间为 02:10。**

有需要注意的信息时，按需出现：

| 情况 | 返回内容 |
| --- | --- |
| 执行器仍响应，但长时间没有推进 | `reason.code = no_recent_progress`，说明仍响应；不能据此认定失败。 |
| 原执行器疑似失联 | `reason.code = suspected_stalled`，说明活性证据过期，返回可验证的恢复条件及实际允许的 `resume` / `cancel`。不能只显示 `running`。 |
| 局部处理失败，其余继续 | `issues`，给出简短的错误类别、受影响阶段和数量。 |

例如，视频阶段发现两个损坏的视频，附加：

```json
{
  "issues": [
    {
      "phase": "video",
      "code": "invalid_media_container",
      "unit": "video",
      "count": 2,
      "message": "两个视频无法解析，其余项目继续处理。"
    }
  ]
}
```

#### 等待用户决定

```json
{
  "state": "paused",
  "reason": {
    "code": "confirmation_required",
    "message": "需要确认是否进行外部地点查询。"
  },
  "allowed_actions": ["resume", "cancel"]
}
```

需要范围选择或外部请求授权时，按需附带现有 `confirmation` 详情。

#### 被外部条件阻塞

```json
{
  "state": "blocked",
  "reason": {
    "code": "source_unavailable",
    "message": "源磁盘当前不可用。",
    "resume_when": "源磁盘重新连接后"
  },
  "allowed_actions": ["resume", "cancel"]
}
```

#### 完成

```json
{
  "state": "completed",
  "result": {
    "ref": "precheck-result:example-001",
    "coverage": "complete",
    "readiness": "plan_ready"
  }
}
```

#### 失败

```json
{
  "state": "failed",
  "reason": {
    "code": "result_validation_failed",
    "message": "non-available Observation cannot contain a value"
  }
}
```

#### 已取消

```json
{
  "state": "cancelled"
}
```

#### 查询本身失败

例如 `run_ref` 不存在，不能把它说成“这次 Run 执行失败”：

```json
{
  "error": {
    "code": "run_not_found",
    "message": "找不到这次 PreCheck 执行。"
  }
}
```

`status` 只读，重复查询不会启动或恢复执行。返回一个时刻的一致快照；
控制动作执行时仍会检查最新状态。

### 3.2 `start`

开始一次本地 PreCheck，立即返回这次执行的编号，后续用 `status` 查询。

Command：

```text
mediasense.precheck.run start
```

输入：

```json
{
  "dataset_ref": "dataset:example-001",
  "request_id": "request:start-001"
}
```

返回：

```json
{
  "run_ref": "precheck-run:example-001"
}
```

成功返回前，Tool 必须已持久化 Run 并启动执行器；仅登记一条任务不算启动成功。
返回不等于处理完成，也不承诺下一次查询时仍是 `running`。

同一 `request_id`、同一输入返回同一 `run_ref`，即使 Run 后来已暂停或完成；
同一编号配不同输入报 `idempotency_conflict`。有意新开一次使用新的请求编号；
同一 Dataset 已有未结束的 Run 时，拒绝重复启动并在错误中指明已有 `run_ref`，
不把已有执行冒充成本次新建，也不自动恢复它。

基于已有 Result 再做一次时，用 `prior_result_ref` 替代 `dataset_ref`：

```json
{
  "prior_result_ref": "precheck-result:example-001",
  "request_id": "request:start-002"
}
```

两者只能选一个；新 Run 的 Dataset 从旧 Result 确定，旧 Result 不被修改。
已确认范围只有在仍精确匹配时才能复用；否则先等范围确认，再做昂贵处理。
`start` 本身不授予外部请求或计费权限。

### 3.3 `pause`

Command：`mediasense.precheck.run pause`

输入：

```json
{ "run_ref": "precheck-run:example-001" }
```

暂停请求已被接受、正在等待已开始的工作收尾时，返回：

```json
{ "state": "running" }
```

这不是暂停失败，也不是已经暂停。随后 `status` 确认：

```json
{
  "state": "paused",
  "reason": { "code": "pause_requested", "message": "已按请求暂停，可继续。" },
  "allowed_actions": ["resume", "cancel"]
}
```

若返回前已经暂停，直接返回 `state: paused`。保留已完成工作；暂停过程中不再接纳新工作，
不抢先发布 Result。与完成发生竞态时报告真实状态，不把 completed 改写成 paused。

### 3.4 `resume`

Command：`mediasense.precheck.run resume`

普通暂停后继续，输入：

```json
{ "run_ref": "precheck-run:example-001" }
```

执行器已恢复，返回：

```json
{ "state": "running" }
```

沿用同一 Run、同一对账身份并复用仍有效的已完成工作；不创建新的执行或重用已失效授权。
恢复成功须有执行器，后续业务进展看 `status`。源盘仍不可用则报错并给出 blocked 原因，
不能把“收到请求”当作成功恢复。恢复失败与原 Run 已完成均需诚实返回。

<details>
<summary>需要选择源目录范围时</summary>

先由 `status` 返回清单。这个示例只有两个目录；“旅行”中包含两张照片、一段视频和一个 GPX。

```json
{
  "state": "paused",
  "reason": { "code": "scope_confirmation_required", "message": "请选择本次处理范围。" },
  "confirmation": {
    "kind": "source_scope",
    "inventory_fingerprint": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "inventory": {
      "complete": true,
      "view": {
        "root": ".",
        "entries": [
          { "path": "旅行", "node_type": "directory", "file_count": 4, "byte_count": 12500000,
            "unknown_size_count": 0, "kind_counts": { "image": 2, "video": 1, "gpx": 1 },
            "size_buckets": { "under_1_mib": 1, "1_to_10_mib": 3, "over_10_mib": 0 },
            "representative_paths": [], "child_count": 0 },
          { "path": "历史输出", "node_type": "directory", "file_count": 1, "byte_count": 2000000,
            "unknown_size_count": 0, "kind_counts": { "image": 1 },
            "size_buckets": { "under_1_mib": 0, "1_to_10_mib": 1, "over_10_mib": 0 },
            "representative_paths": [], "child_count": 0 }
        ],
        "next_after": null
      }
    }
  },
  "allowed_actions": ["resume", "cancel"]
}
```

`inventory.complete` 表示发现是否完整，不表示这一页展示了全部目录。
路径相对于源根；目录名不等于 Tool 已判断它应该包含或排除。
`byte_count` 是已知大小总和，`unknown_size_count` 保留未知大小，不能当作零字节。
大小桶只服务于判断范围，固定桶定义由当前发现能力披露，不固定成以上三档。
`child_count` 表示下一层可展开目录数量，文件统计是递归统计；示例目录里只有文件。
受限发现必须附 `issues` 说明遗漏，不能靠数量凑成完整清单。

选中“旅行”，调用 `resume`：

```json
{
  "run_ref": "precheck-run:example-001",
  "decision": {
    "kind": "source_scope",
    "inventory_fingerprint": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "default_disposition": "exclude",
    "exceptions": ["旅行"]
  }
}
```

返回使用普通 resume 的 `state` 格式。例外子树采用与默认相反的处理方式，不能彼此重叠。
生效前验证清单仍匹配；变化时返回新的确认内容，不悄悄应用旧选择。排除项仍被对账，不删除文件。

展开目录或继续读子目录仍用 `status`，不新增 command：

```json
{ "run_ref": "precheck-run:example-001", "scope_path": "旅行" }
```

后续页增加返回的 `scope_after` 标记；它绑定 Run、清单 fingerprint 和所选路径，
`next_after: null` 表示当前路径展示完毕。生效选择可通过 `status include: ["accounting"]` 核对。

</details>

<details>
<summary>需要授权外部地点查询时</summary>

`status` 返回下面这段 `confirmation`；其余 state、reason、allowed_actions 同上。
示例的请求集只有一个坐标，因此不是从大请求集抽样的确认。

```json
{
  "confirmation": {
    "kind": "external_effect",
    "content_identity": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "disclosure": {
      "geo_request_fingerprint": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
      "operation": "resolve_place",
      "coordinates": [{ "latitude": 22.2938, "longitude": 114.1697, "datum": "WGS84" }],
      "pending_logical_queries": 1,
      "source_item_outcomes": 2,
      "nearby_radius_meters": 100,
      "max_places": 5,
      "transmitted_data_classes": ["coordinates", "datum", "locale", "lookup_controls"],
      "providers": [{ "provider": "google_maps", "data_handling": "unknown" }],
      "max_provider_requests": 2,
      "max_billable_units": null,
      "billable_calls": "unknown",
      "result_retention": "immutable_precheck_result"
    }
  }
}
```

`content_identity` 绑定 Human 所见整份披露，`geo_request_fingerprint` 绑定实际 Geo 请求，
不能用任一个代替另一个。坐标会离开本地，可暴露访问地点；源媒体、文件名和普通元数据不在授权内。
允许的 Provider、回退范围、请求上限、未知费用和保留方式都要明示。以上坐标数不能代替请求费用。
大请求集仍必须完整可读并绑定同一披露身份，不能省略坐标后让用户确认一个未说明的范围。

请求客户端完成可信确认：

```json
{ "run_ref": "precheck-run:example-001", "decision": "proceed" }
```

只有客户端确认通过才恢复。明确拒绝用 `decision: decline`，终止该 Run 且不发布 Result；
关闭确认控件仅保持暂停。已完成工作可保留，但不承诺可以在原 Run 的终态后 resume。
不能添加 `skip_allowed: true` 绕过既有必需获取环节；也不回传恒为 false 的字段。

</details>

### 3.5 `cancel`

Command：`mediasense.precheck.run cancel`

输入：

```json
{ "run_ref": "precheck-run:example-001" }
```

已结束时返回：

```json
{ "state": "cancelled" }
```

尚在收尾时返回实际 `state`，用 `status` 等到 cancelled，不新增没有执行机制的中间状态。
取消阻止后续工作和 Result 发布；已开始的外部效果不能假称撤销，诊断记录仍保留。
取消不删除原媒体、不清空已完成工作，也不撤回已经发布的 Result。

### 3.6 `review`

Command：`mediasense.precheck.read review`

看 Result 是否可用、所有条目怎样被交代，以及从哪些代表证据开始看。
例子包含两张照片、一段损坏视频、一个辅助 GPX 和一个排除项，均已明确交代。

输入：

```json
{ "result_ref": "precheck-result:example-001", "page": { "limit": 25 } }
```

返回：

```json
{
  "result": {
    "ref": "precheck-result:example-001",
    "coverage": "complete",
    "readiness": "plan_ready",
    "qualifications": [
      { "code": "invalid_media_container", "effect": "limits_interpretation",
        "message": "一段视频无法读取，保留为异常源条目；其余证据可供规划。" }
    ]
  },
  "accounting": {
    "total": 5,
    "scope_condition": [
      { "scope": "source_media", "condition": "usable", "count": 2 },
      { "scope": "source_media", "condition": "invalid", "count": 1 },
      { "scope": "auxiliary", "condition": "usable", "count": 1 },
      { "scope": "excluded", "condition": "usable", "count": 1 }
    ],
    "routes": { "frontier_only": 2, "exception_only": 3, "frontier_and_exception": 0, "residual": 0 },
    "frontier": { "entry_evidence_count": 1, "coverage_memberships": 2, "represented_unique_source_items": 2 }
  },
  "cards": [
    {
      "evidence_ref": "evidence:entry-001",
      "access": { "kind": "source_item", "source_item_ref": "source-item:001" },
      "source_count": 2,
      "scope_condition": [{ "scope": "source_media", "condition": "usable", "count": 2 }],
      "facts": {
        "capture_time": { "status_counts": { "available": 2 },
          "earliest": "2026-05-01T12:00:00+08:00", "latest": "2026-05-01T12:01:00+08:00" },
        "media_type": { "status_counts": { "available": 2 }, "values": [{ "value": "image/jpeg", "count": 2 }] }
      },
      "roles": { "representative": ["evidence:entry-001"], "boundary": ["evidence:boundary-001"] },
      "other_observations_available": true,
      "available_expansions": ["anchor_evidence", "prepared_targets", "provenance", "coverage_basis", "member_observations"],
      "source_set": { "kind": "precheck_relation", "origin": "evidence:entry-001", "relation": "represents", "direction": "outbound" }
    }
  ],
  "page": { "total": 1, "next_cursor": null }
}
```

`accounting` 总是整份 Result 的对账，不是当前页卡片的统计。`routes` 四项互斥且总和等于
`total`；完整覆盖要求 `residual: 0`。`scope_condition` 明确辅助项和排除项，不能把 5 项叫作 5 张照片。
可推导的对账等式和 `closure_check: passed` 不回传，校验由 Tool 保证。
异常项可通过 `resolve` 的 Result `accounts_for` 集合完整取得。

`cards` 按 Result 已固定的入口顺序分页。卡片的 source_count 是去重成员数；
全局 coverage_memberships 与 represented_unique_source_items 保留跨卡重复覆盖信息，差值可直接算出。
有实质限定时卡片附 `qualifications`（含 `applies_to`、`occurrences`）；无角色的准备证据按需附
`unassigned_prepared_evidence`。空角色组和零计数省略，不把“未展示”解释成未知或未检查。

<details>
<summary>查看对账、费用与复用的完整信息</summary>

默认 review 不显示 Provider 和请求细节。需要审计时：

```json
{ "result_ref": "precheck-result:example-001", "include": ["execution_boundary"] }
```

在普通返回上附加：

```json
{
  "execution_boundary": {
    "source_read_only": true,
    "remote_models": false,
    "historical_provider_requests": 0,
    "current_provider_requests": 2,
    "billable_calls": null,
    "providers_attempted": ["google_maps"],
    "transmitted_data_classes": ["coordinates", "datum", "locale", "lookup_controls"]
  }
}
```

历史复用携带的请求不算作本次新请求；任一数值无证据就用 `null`，不能用“总请求数”推导账单。
执行审计保留既有实际 Provider、回退、重试、数据类别和费用证据，字段按实际发生情况返回；
示例仅表示无回退、无重试的小场景。

Run 尚未发布时，仍可读运行期对账或诊断，例如：

```json
{ "run_ref": "precheck-run:example-001", "include": ["accounting"] }
```

除普通 status 字段，附加：

```json
{
  "accounting": {
    "discovered": 5,
    "accounted": 5,
    "scope_condition": [
      { "scope": "source_media", "condition": "usable", "count": 2 },
      { "scope": "source_media", "condition": "unresolved", "count": 1 },
      { "scope": "auxiliary", "condition": "usable", "count": 1 },
      { "scope": "excluded", "condition": "usable", "count": 1 }
    ],
    "selection": {
      "inventory_fingerprint": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "default_disposition": "exclude",
      "exceptions": ["旅行"],
      "provenance": { "basis": "human_selection" }
    }
  }
}
```

运行期数值未知仍返回 `null`；对账不凭固定 fixture 数量推导。
当前阶段更细的工作数量、实际效果审计和完整问题类别按需读取：

```json
{
  "run_ref": "precheck-run:example-001",
  "include": ["diagnostics"],
  "page": { "limit": 50 }
}
```

在普通 status 上附加以下对象，示例此时停在视频阶段：

```json
{
  "diagnostics": {
    "work": { "phase": "video", "unit": "video_probe", "completed": 0, "reused": 0, "failed": 1, "remaining": 0, "total": 1 },
    "issues": [
      { "phase": "video", "code": "invalid_media_container", "unit": "video", "count": 1,
        "message": "一段视频无法解析，源文件仍保留。" }
    ],
    "page": { "total": 1, "next_cursor": null }
  }
}
```

这里保留 completed（本次成功计算）、reused（复用有效工作）、failed（当前失败）、remaining
（待处理）的精确分类；已知时总和等于 total。它们不是另一套运行状态，也不能用来推翻 progress
的既定计数口径；分类和 progress 的单位不同时不能直接对应。

问题较多时 `diagnostics.issues` 按公共 page 续读，默认 status 的摘要以 `issues_truncated: true`
明确说明省略。运行数据持续变化，游标绑定诊断数据版本；读下一页时若版本已变，
明确报 `invalid_cursor` 并重新从首页读取，不把不同时间的分类拼成一份精确快照。
敏感原始日志、私有数据库和 Work ID 不作为接口。执行审计按需包含在 diagnostics.execution_boundary，
使用与发布 Result 相同的效果/费用语义，不把未知结果写成零。

</details>

### 3.7 `expand`

Command：`mediasense.precheck.read expand`

只读取选中的内容。Source Item 与 Evidence 使用不同选择器，但每次只能选一种，最多 16 个引用。

输入：

```json
{
  "result_ref": "precheck-result:example-001",
  "source_item_refs": ["source-item:003"],
  "include": ["source_item", "observations", "covering_evidence"]
}
```

返回：

```json
{
  "items": [
    {
      "source_item_ref": "source-item:003",
      "included": {
        "source_item": {
          "locator": { "kind": "source_root_relative_path", "source_root_ref": "source-root:001", "value": "旅行/003.MP4" }
        },
        "observations": [
          { "name": "media_type", "status": "available", "value": "video/mp4" },
          { "name": "capture_time", "status": "missing" },
          { "name": "media_readability", "status": "failed", "basis": { "summary": "视频容器缺少必需索引。" } }
        ],
        "covering_evidence": []
      }
    }
  ],
  "page": { "total": 1, "next_cursor": null }
}
```

没有 covering Evidence 不等于源项不存在；本例仍保留损坏视频的身份和失败依据。
已请求的空列表返回 `[]`，不能省略后让调用者分不清“没请求”和“查过但为空”。

| 选择对象 | 可用 include |
| --- | --- |
| `source_item_refs` | `source_item`、`observations`、`covering_evidence` |
| `evidence_refs` | `anchor_evidence`、`prepared_targets`、`provenance`、`coverage_basis` |
| 单个 `evidence_ref`，通过 `evidence_refs` 传入 | `member_observations`，分页逐成员观测 |

<details>
<summary>照片没有地点：查无结果与最终失败</summary>

两张照片都可以继续交给 Plan。下面只展示地点相关观测，其余已记录观测实际仍需返回。

输入：

```json
{
  "result_ref": "precheck-result:place-gaps-001",
  "source_item_refs": ["source-item:photo-no-result", "source-item:photo-query-failed"],
  "include": ["observations"]
}
```

返回：

```json
{
  "items": [
    {
      "source_item_ref": "source-item:photo-no-result",
      "included": {
        "observations": [
          {
            "name": "reverse_geocode_candidate",
            "status": "missing",
            "basis": { "summary": "地点查询已完成，没有返回地址或附近地点候选。" }
          }
        ]
      }
    },
    {
      "source_item_ref": "source-item:photo-query-failed",
      "included": {
        "observations": [
          {
            "name": "reverse_geocode_candidate",
            "status": "failed",
            "basis": { "summary": "地点服务持续不可用，工具已结束本次有限重试，没有可用候选。" },
            "qualifications": [
              { "code": "location_query_failed", "effect": "limits_interpretation",
                "message": "此照片缺少地点信息，可使用其他证据继续规划。" }
            ]
          }
        ]
      }
    }
  ],
  "page": { "total": 2, "next_cursor": null }
}
```

两条非 available Observation 都不含 `value`。第一张是“查过但没找到”，第二张是“没能查到
可靠结果”；都不是整个 `expand` 调用失败。不增加强制的地点包装对象，也不让 Plan 接收重试细节。

如果这份 Result 其余条件均满足，`status` 完成时返回：

```json
{
  "state": "completed",
  "result": {
    "ref": "precheck-result:place-gaps-001",
    "coverage": "complete",
    "readiness": "plan_ready",
    "qualifications": [
      { "code": "location_query_failed", "effect": "limits_interpretation",
        "message": "一张照片的地点获取最终失败，已逐项记录，不妨碍继续规划。" }
    ]
  }
}
```

</details>

<details>
<summary>看代表证据及其展开依据</summary>

输入：

```json
{
  "result_ref": "precheck-result:example-001",
  "evidence_refs": ["evidence:entry-001"],
  "include": ["anchor_evidence", "prepared_targets", "coverage_basis"]
}
```

返回：

```json
{
  "items": [
    {
      "evidence_ref": "evidence:entry-001",
      "included": {
        "anchor_evidence": {
          "access": { "kind": "source_item", "source_item_ref": "source-item:001" },
          "observations": [{ "name": "media_type", "status": "available", "value": "image/jpeg" }],
          "roles": ["representative"]
        },
        "prepared_targets": [
          { "evidence_ref": "evidence:boundary-001", "roles": ["boundary"],
            "access_status": "available", "basis": { "summary": "已准备的边界照片。" } }
        ],
        "coverage_basis": {
          "member_count": 2,
          "qualified_member_count": 0,
          "member_specific_basis": true
        }
      }
    }
  ],
  "page": { "total": 1, "next_cursor": null }
}
```

`coverage_basis` 有限定时返回已有 `qualification_groups`，保留成员级差异；
`member_specific_basis` 提醒是否需要逐成员查看，不能由“共两项”推出同一依据适用于全部成员。
`provenance` 可读取所有既有可追溯信息；`prepared_targets` 包含有角色及无角色证据。

读取逐成员观测时：

```json
{
  "result_ref": "precheck-result:example-001",
  "evidence_refs": ["evidence:entry-001"],
  "include": ["member_observations"],
  "page": { "limit": 50 }
}
```

返回：

```json
{
  "items": [
    { "source_item_ref": "source-item:001",
      "observations": [{ "name": "capture_time", "status": "available", "value": "2026-05-01T12:00:00+08:00" }] },
    { "source_item_ref": "source-item:002",
      "observations": [{ "name": "capture_time", "status": "available", "value": "2026-05-01T12:01:00+08:00" }] }
  ],
  "page": { "total": 2, "next_cursor": null }
}
```

这里为便于展示只示意拍摄时间观测；实际返回所选成员全部已记录观测及必要 qualifications，
不得按示例删掉其他观测。用公共 page 完整续读。单次只选一个 Evidence，避免多组成员分页含混。

</details>

### 3.8 `resolve`

Command：`mediasense.precheck.read resolve`

取精确成员，用于完整组织、验证和 Apply；不判断该集合是否应该作为相册分组。
这里直接复用 review 返回的 source_set。

输入：

```json
{
  "result_ref": "precheck-result:example-001",
  "source_set": { "kind": "precheck_relation", "origin": "evidence:entry-001", "relation": "represents", "direction": "outbound" },
  "page": { "limit": 250 }
}
```

返回：

```json
{
  "resolution": {
    "source_set_identity": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "membership_identity": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
  },
  "members": [
    {
      "source_item_ref": "source-item:001",
      "locator": { "kind": "source_root_relative_path", "source_root_ref": "source-root:001", "value": "旅行/001.JPG" },
      "scope": "source_media", "condition": "usable",
      "source_content_verification": { "status": "not_checked" }
    },
    {
      "source_item_ref": "source-item:002",
      "locator": { "kind": "source_root_relative_path", "source_root_ref": "source-root:001", "value": "旅行/002.JPG" },
      "scope": "source_media", "condition": "usable",
      "source_content_verification": { "status": "not_checked" }
    }
  ],
  "page": { "total": 2, "next_cursor": null }
}
```

假校验值仅演示形状；实际必须由 Tool 对表达式和全量成员计算并可重算核对。
成员固定按 source_item_ref 升序；不再回显恒定 ordering，也不重复返回两份 total。
source_content_verification 保留真实核验状态；有核验时包含 profile、value、size_bytes、
observed_at、producer 和必要依据。精确取到成员不等于源内容已经核验，Apply 仍需执行自己的安全门槛。

| 集合 | 保留的表达能力 |
| --- | --- |
| `explicit` | 指定 Source Item 引用列表。 |
| `precheck_relation` + Result `accounts_for` | 全部已对账条目，包括辅助、排除和异常项。 |
| `precheck_relation` + Evidence `represents` | 该证据的精确成员。 |
| `geo_coordinate` | Geo 诊断返回的精确坐标成员集合，带适用选择规则。 |
| `union` / `difference` | 多个集合的去重并集或差集。 |

表达式只选择当前 Result 中的成员，不接受私有 bundle/cache ID。
组合集合仍须精确校验、稳定分页；不把“允许这些表达式”变成公开任意图遍历。

### 3.9 `geo_summary`

Command：`mediasense.precheck.read geo_summary`

这是 PreCheck 的地点诊断视图，Plan 不靠它重建逐 Source Item 地点结果。

输入：

```json
{ "result_ref": "precheck-result:example-001", "page": { "limit": 50 } }
```

一个坐标覆盖两张照片的示例：

```json
{
  "acquisition_status": "complete",
  "coordinate_evidence": {
    "gps": { "available": 2, "missing": 1 },
    "gpx": { "missing": 3 },
    "combined": { "available": 2, "missing": 1 }
  },
  "coordinate_groups": [
    {
      "coordinate": { "latitude": 22.2938, "longitude": 114.1697, "datum": "WGS84" },
      "member_count": 2,
      "source_set": {
        "kind": "geo_coordinate",
        "coordinate": { "latitude": 22.2938, "longitude": 114.1697, "datum": "WGS84" },
        "selection_rule": "gpx_over_gps_exact_normalized_v1"
      },
      "reverse_geocode": "success",
      "candidate_evidence_refs": ["evidence:geo-001", "evidence:geo-002"]
    }
  ],
  "page": { "total": 1, "next_cursor": null }
}
```

沿用既有 `reverse_geocode` 的 success / no_result / failure / not_requested 诊断口径，
不把它升级为新定义的“地址和附近地点都成功”。逐组件结果仍需来自真实记录，不能反推伪造。
`acquisition_status` 表示这项证据覆盖是否闭合；不证明地点正确，也不替代 Result readiness。
GPS、GPX、最终坐标分开统计；冲突及其他状态非零时必须返回，不能用最终选择覆盖历史证据。

精确规则由 `source_set.selection_rule` 定义；以上规则保留 GPX 优先、经纬度及 datum 精确匹配、
不做四舍五入。取消重复的 deduplication 说明和 unique_coordinate_count；后者等于 page.total。
规则变更必须换明确身份，不能让旧 source_set 静默改变成员。
分组按纬度、经度、datum 稳定排序，成员通过 resolve 分页取得，不把所有源引用塞进一项。
必要 provenance、冲突和 qualifications 按需随组保留；要核对请求/成本则通过 review 的 execution_boundary。

地点可缺失的统一规则见 2.11：终结的局部获取失败不阻塞 Plan。
`geo_summary` 的 failure 表示获取结果失败，不表示整份 Result 不可用；
获取仍在等待、结果记录缺漏和已终结的失败必须分别说明，不能只靠一个粗摘要反推 readiness。
