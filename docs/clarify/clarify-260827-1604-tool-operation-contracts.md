---
id: "clarify-260827-1604-tool-operation-contracts"
title: "MediaSense Tool 最小操作契约澄清"
type: clarify
status: active
created: 2026-08-27
updated: 2026-08-27
timezone: "Asia/Shanghai"
parent: "index-clarify"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "spec-260826-1546-precheck-read"
  - "spec-260827-1138-frozen-plan"
superseded-by: ""
---

# MediaSense Tool 最小操作契约澄清

## 当前设计

### 先看一个小型端到端候选示例

下面只是帮助审阅字段的候选调用形状，不是已经确定的正式 Schema。示例中的 ID 和组织内容都是说明性数据。

启动一个新的 PreCheck Run：

```json
{
  "tool": "mediasense.precheck.run",
  "request": {
    "action": "start",
    "dataset_ref": "dataset:hong-kong-food-trip",
    "request_id": "request:precheck-001"
  },
  "response": {
    "outcome": "ok",
    "run_ref": "precheck-run:hk-001",
    "dataset_ref": "dataset:hong-kong-food-trip",
    "state": "running"
  }
}
```

同一个 `status` 操作先可观察运行，随后观察 Result 已发布。这里只展示完成后的候选返回：

```json
{
  "tool": "mediasense.precheck.run",
  "request": {
    "action": "status",
    "run_ref": "precheck-run:hk-001"
  },
  "response": {
    "outcome": "ok",
    "run_ref": "precheck-run:hk-001",
    "dataset_ref": "dataset:hong-kong-food-trip",
    "state": "completed",
    "allowed_actions": [],
    "published_result": {
      "result_ref": "precheck-result:hk-001",
      "coverage": "partial",
      "readiness": "plan_ready",
      "integrity": "valid"
    }
  }
}
```

Plan 通过既有只读契约取得 Evidence：

```json
{
  "tool": "mediasense.precheck.read",
  "request": {
    "result_ref": "precheck-result:hk-001",
    "action": "traverse",
    "relation": "entry_evidence",
    "direction": "outbound",
    "page": {
      "limit": 20
    }
  },
  "response": {
    "outcome": "ok",
    "result_ref": "precheck-result:hk-001",
    "action": "traverse",
    "origin": "precheck-result:hk-001",
    "relation": "entry_evidence",
    "direction": "outbound",
    "items": [
      {
        "target": "evidence:entry-01"
      }
    ],
    "page": {
      "returned": 1,
      "complete": true
    }
  }
}
```

创建 Plan Working State。`organization_preferences` 作为该 Working State 的 revision 化快照持久化，但不形成独立 Profile 实体：

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "create",
    "result_ref": "precheck-result:hk-001",
    "organization_preferences": {
      "default_hierarchy": "time_place_event",
      "maximum_depth": 3
    },
    "request_id": "request:plan-001"
  },
  "response": {
    "outcome": "ok",
    "work_ref": "plan-work:hk-001",
    "result_ref": "precheck-result:hk-001",
    "revision": "work-revision:1"
  }
}
```

下面用已经确认的“完整替换当前候选内容”语义演示 `update`：

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "update",
    "work_ref": "plan-work:hk-001",
    "base_revision": "work-revision:1",
    "candidate_content": {
      "result_ref": "precheck-result:hk-001",
      "scope": {
        "kind": "precheck_relation",
        "origin": "precheck-result:hk-001",
        "relation": "accounts_for",
        "direction": "outbound"
      },
      "logical_root": "香港美食之旅",
      "groups": [
        {
          "relative_path": ["2026", "2026-05-01_香港"],
          "members": {
            "kind": "precheck_relation",
            "origin": "precheck-result:hk-001",
            "relation": "accounts_for",
            "direction": "outbound"
          },
          "source_naming": {
            "default": "preserve_source_basename"
          }
        }
      ],
      "other_outcomes": []
    },
    "request_id": "request:plan-update-001"
  },
  "response": {
    "outcome": "ok",
    "work_ref": "plan-work:hk-001",
    "revision": "work-revision:2"
  }
}
```

`inspect` 绑定一个精确 revision，同时返回内容、验证结论和候选内容身份。CLI 可以把同一 `content` 渲染成树：

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "inspect",
    "work_ref": "plan-work:hk-001",
    "revision": "work-revision:2",
    "sections": ["content", "validation"],
    "page": {
      "section": "groups",
      "limit": 50
    }
  },
  "response": {
    "outcome": "ok",
    "work_ref": "plan-work:hk-001",
    "revision": "work-revision:2",
    "content": {
      "logical_root": "香港美食之旅",
      "groups": [
        {
          "relative_path": ["2026", "2026-05-01_香港"],
          "member_count": 2134
        }
      ]
    },
    "validation": {
      "seal_ready": true,
      "issues": []
    },
    "candidate_content_identity": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "page": {
      "section": "groups",
      "returned": 1,
      "complete": true
    }
  }
}
```

最后由可信的人类认证上下文调用 `seal`。请求不接受调用者自报的 `confirmed_by`：

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "seal",
    "work_ref": "plan-work:hk-001",
    "revision": "work-revision:2",
    "candidate_content_identity": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "request_id": "request:plan-seal-001"
  },
  "response": {
    "outcome": "ok",
    "work_ref": "plan-work:hk-001",
    "plan_ref": "frozen-plan:hk-001",
    "result_ref": "precheck-result:hk-001",
    "content_identity": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "frozen_plan": {
      "sealed_content": {
        "contract": "mediasense.frozen-plan",
        "plan_ref": "frozen-plan:hk-001",
        "result_ref": "precheck-result:hk-001",
        "scope": {
          "kind": "precheck_relation",
          "origin": "precheck-result:hk-001",
          "relation": "accounts_for",
          "direction": "outbound"
        },
        "logical_root": "香港美食之旅",
        "groups": [
          {
            "relative_path": ["2026", "2026-05-01_香港"],
            "members": {
              "kind": "precheck_relation",
              "origin": "precheck-result:hk-001",
              "relation": "accounts_for",
              "direction": "outbound"
            },
            "source_naming": {
              "default": "preserve_source_basename"
            }
          }
        ],
        "other_outcomes": []
      },
      "seal": {
        "encoding_profile": "mediasense-json-strings-sha256-v1",
        "content_identity": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        "final_confirmation": {
          "confirmed_content_identity": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "confirmed_at": "2026-08-27T16:04:00+08:00",
          "confirmed_by": "human:authenticated-owner"
        }
      }
    }
  }
}
```

基于旧 Result 重新开始仍使用 `start`，并且不重复提供第二个 Dataset 权威：

```json
{
  "action": "start",
  "prior_result_ref": "precheck-result:hk-001",
  "request_id": "request:precheck-002"
}
```

### 已固定的操作边界

```text
mediasense.precheck.run
├── start
├── status
├── pause
├── resume
└── cancel

mediasense.precheck.read
├── inspect
└── traverse

mediasense.plan.work
├── create
├── update
├── inspect
└── seal
```

`mediasense.precheck.run` 拥有可变、耗时、可恢复的 Working Run；`mediasense.precheck.read` 只读取已发布、不可变的 Result；`mediasense.plan.work` 拥有可变 Plan Working State，并在可信人类确认后产生 Frozen Plan。三者不合并。

PreCheck 公共状态已经固定为 `running`、`paused`、`blocked`、`completed`、`cancelled`、`failed`。`paused.reason` 可以区分人工暂停和进程中断。内部阶段、checkpoint、SQLite、缓存和算法均不是公共语义。

### 第 1 轮整合后的工程默认

用户已直接回答 Q1-Q7，并授权其余纯工程问题按推荐方案收敛。因此当前候选固定为：

- `start` 在 `dataset_ref` 与 `prior_result_ref` 中二选一；后者唯一决定 Dataset 和谱系。
- `start / create / update / seal` 使用 `request_id` 保证安全重试；控制操作按目标状态幂等。
- `status` 返回 `allowed_actions`、业务进度、结构化暂停/阻塞/失败原因和恢复条件。
- `pause / resume / cancel` 先确认请求已接受，实际状态转换仍以之后的 `status` 为准。
- 普通暂停、中断、阻塞和取消不会冒充 partial Result；只有通过 Result 契约验证的有界终态才会自动发布。
- `completed` 返回 `result_ref` 及其三轴摘要；不可变 Result 仍是三轴的唯一权威。
- Plan 组织偏好保存在已有 Working State 内，不形成 Profile 实体；它随 revision 精确返回和修改。
- Plan revision 是只用于精确绑定和并发检查的 opaque token；`update` 使用 `base_revision`，以完整 `candidate_content` 原子替换当前候选。
- `inspect` 可省略 revision 以原子解析当前版本，但响应和后续 cursor 必须绑定精确 revision；分页不改变全局候选内容身份。
- `seal` 精确绑定 `work_ref + revision + candidate_content_identity + request_id` 和可信 Human confirmation，成功返回完整 Frozen Plan，并可安全重试。

Plan 阶段采用严格入口：只有 `readiness=plan_ready` 且 `integrity=valid` 的 Result 才能创建 Working State；`coverage` 可以是 complete 或有界 partial。`readiness=blocked` 的 Result 继续通过 `precheck.read` 调查，必要时以 `start(prior_result_ref)` 开始新的 PreCheck Run，不创建探索性 Plan 草稿。

## 证据

- 本轮用户已经固定三条 Tool 边界、十一项公共操作、六种 PreCheck 公共状态、自动 Result 发布、Plan seal 后关闭 Working State、人类确认边界、`inspect` 的 revision 与分页要求，以及 Organization Profile 暂不实体化。
- 用户在第 1 轮直接回答 Q1-Q7，并进一步授权：除真正容易产生业务分歧的选择外，其余问题按工程推荐方案确认；不再要求 Human 审查常规幂等、revision、分页、错误外壳和安全重试设计。
- 用户在第 2 轮选择 Q16=A，并明确希望保持简单：`readiness` 作为严格 Plan 入口，不增加 blocked Result 的探索性 Working State 生命周期。
- [`design-260823-1918-mediasense-foundation`](../design/design-260823-1918-mediasense-foundation.md) 规定 PreCheck 的源媒体只读、默认无远程与收费调用、长任务可观察和可恢复；Plan 负责 Agent 与 Human 收敛，不修改源媒体。
- [`spec-260826-1546-precheck-read`](../spec/spec-260826-1546-precheck-read/index.md) 已正式固定 `mediasense.precheck.read` 的 `inspect / traverse`、精确 `result_ref`、分页、关系方向、三轴状态和错误外壳。本记录不重新询问这些已定语义。
- [`spec-260827-1138-frozen-plan`](../spec/spec-260827-1138-frozen-plan/index.md) 已固定 Frozen Plan 的完整逻辑组织、精确 `result_ref`、内容身份和最终人类确认。本记录只澄清 Working State 怎样安全地产生该 artifact。
- [`design-260827-0022-precheck-implementation`](../design/design-260827-0022-precheck-implementation.md) 证明 Working Run、恢复、自动验证和原子发布需要持久生命周期，但其中的内部阶段和存储方法不提升为公共契约。
- `docs/clarify/` 中没有同主题的 active Tool 操作契约记录；现有两份 active 记录分别负责 PreCheck Result 概念和 Frozen Plan artifact。

## 已确认决策

1. 保留 `mediasense.precheck.run`、`mediasense.precheck.read`、`mediasense.plan.work` 三条 Tool 边界，不合并。
2. `precheck.run` 只有 `start / status / pause / resume / cancel`；`start` 可选接受 `prior_result_ref`，不增加 `reopen`。
3. `precheck.read` 继续使用已有正式 `inspect / traverse` 契约，本轮不修改。
4. PreCheck 不设公共 `seal`。Run 只有在能形成诚实、稳定的 complete 或有界 partial Result 时才自动原子发布。
5. `completed` 只表示 Result 已发布；Plan 是否可用由 Result 的 `coverage / readiness / integrity` 三轴判断。
6. 暂停或中断中的 Working State 不是 Result；单个媒体失败不等于 Run `failed`。
7. `plan.work` 只有 `create / update / inspect / seal`；preview 是适配器渲染，验证结论由 `inspect` 返回。
8. Plan seal 后原 Working State 关闭，新的 `plan_ref` 成为权威对象；后续修改必须创建新 Working State。
9. `seal` 依赖可信人类认证上下文并绑定精确内容身份；普通请求字段不能自报 `confirmed_by`；不增加 Confirm Tool。
10. `plan.work inspect` 绑定精确 revision，可按 section/page 分批读取，但完整内容必须最终可取得。
11. Organization Profile 暂不成为独立实体、Tool 或 `profile_ref`；组织偏好目前只是 Plan 输入。
12. CLI 和 Agent Tool 是同一操作契约的不同适配器，本轮不冻结 CLI 或认证实现。
13. `start` 的 `dataset_ref / prior_result_ref` 二选一；使用旧 Result 时 Dataset 从 Result 推导，响应保留 lineage。
14. `start / create / update / seal` 使用 `request_id`；同一 ID 和相同请求返回同一结果，不同请求返回 `idempotency_conflict`。
15. `status` 返回当前 `allowed_actions`；控制调用的“已接受”不等于状态已经转换完成。
16. 只有通过 Result 契约验证的有界终态才自动发布 partial；暂停、中断、阻塞和取消不触发发布。
17. `status` 使用业务计数表达进度，并为暂停、阻塞和失败提供结构化原因及可验证恢复条件。
18. `completed` 返回 `result_ref` 和从不可变 Result 精确复制的 `coverage / readiness / integrity` 摘要。
19. 组织偏好作为 Plan Working State 的 revision 化快照保存，不形成独立 Profile 实体。
20. Plan revision 是 opaque token；`update` 必须传 `base_revision`，并以完整 `candidate_content` 原子替换当前候选。
21. `inspect` 可省略 revision，但响应必须回显原子解析到的精确 revision；section/page cursor 与该 revision 和查询形状绑定。
22. 可 seal 的完整候选具有全局 `candidate_content_identity`；分页只是取得内容的方式，不产生 page identity。
23. `seal` 绑定精确 Work、revision、内容身份、幂等请求和可信 Human confirmation；成功返回完整 Frozen Plan，错误沿用统一结构化外壳。
24. `plan.work create` 只接受 `readiness=plan_ready` 且 `integrity=valid` 的 Result；`coverage` 可以是 complete 或有界 partial。blocked 或 invalid Result 不创建 Working State。

## 问题清单

### 第 1 轮：最小稳定操作契约问题包

本轮一次覆盖五组阻塞选择：创建与谱系、安全重试、PreCheck 状态与发布、Plan revision 与更新、inspect/seal/error。请在每题“你的回答”后填写选项字母，也可以直接改写推荐答案。

#### Q1. `start` 应怎样在新 Dataset 与旧 Result 之间选择唯一上游？

为什么问：如果 `dataset_ref` 和 `prior_result_ref` 可以同时出现并且不一致，后续 Run 不知道哪个才是权威来源。

简单例子：旧 Result 属于 Dataset A，但请求同时传入 Dataset B。Tool 必须拒绝，而不能猜测。

选项：

- A. 请求必须二选一：首次运行传 `dataset_ref`；基于旧 Result 重启时只传 `prior_result_ref`，Dataset 从旧 Result 推导。响应总是返回 `dataset_ref`，有谱系时再返回 `prior_result_ref`。
- B. `dataset_ref` 永远必填，`prior_result_ref` 只是可选提示；两者冲突时以 Dataset 为准。
- C. 有旧 Result 时两个字段都必填，Tool 只负责核对是否一致。
- D. 合并成通用 `source_ref`，由实现自行识别它指向 Dataset 还是 Result。

推荐：A。原因：它只保留一个上游权威，同时让谱系和首次运行都能直接发现；不会增加通用引用包装。

你的回答：A

#### Q2. 哪些有副作用的操作必须携带安全重试身份？

为什么问：Agent 在超时后可能不知道调用是否成功。如果盲目重试 `start`、`create`、`update` 或 `seal`，可能产生两个 Run、两个 Working State、两个 revision 或两个 Frozen Plan。

简单例子：`seal` 已经成功，但响应在网络中丢失；同一请求重试时应返回同一 `plan_ref`，而不是再生成一份。

选项：

- A. 所有非查询操作都必须带 `request_id`，包括 `pause / resume / cancel`。
- B. `start / create / update / seal` 必须带 `request_id`；`pause / resume / cancel` 依靠目标状态保持幂等。同一 ID 加同一请求返回同一结果，同一 ID 加不同请求返回 `idempotency_conflict`。
- C. 只有会创建顶层身份的 `start / create / seal` 需要；`update` 只靠 revision。
- D. Tool 不提供幂等保证，调用者自行检查结果后重试。

推荐：B。原因：这些操作会产生新的持久身份、revision 或 artifact；控制操作本身可以自然表达“已经暂停/已经取消”，不必再增加请求身份。

你的回答：B

#### Q3. `status` 是否应直接返回当前允许的后续控制操作？

为什么问：状态名本身未必足以让 Agent 安全推导下一步，尤其是 `blocked`、终态和并发控制场景。

简单例子：Run 已 `completed` 后再调用 `resume`，Tool 应明确拒绝；调用者不应靠猜测状态机。

选项：

- A. `status` 必须返回 `allowed_actions`；`status` 在所有状态可用，控制操作只允许：`running → pause/cancel`，`paused → resume/cancel`，`blocked → resume/cancel`，三个终态不再允许控制。
- B. 状态转换只写在文档里，`status` 不重复返回 `allowed_actions`。
- C. Tool 尽量执行任何控制请求，不冻结转换矩阵。
- D. 调用者直接提交期望的新状态，不保留 `pause / resume / cancel` 的独立动作。

推荐：A。原因：允许的下一动作会直接影响安全恢复，属于当前权威状态的一部分，而不是 UI 提示。

你的回答：A

#### Q4. `pause / resume / cancel` 应在何时报告成功？

为什么问：长任务可能要等到安全点才能真正暂停或取消。仅仅接受请求不能冒充状态已经改变。

简单例子：`pause` 已被接受，但一个不可中断的本地解码步骤仍在结束；此时报告 `paused` 会误导操作者拔盘或关机。

选项：

- A. 调用一直等待，直到 Run 已稳定进入目标状态才返回。
- B. 控制调用先返回 `outcome: accepted` 和当时观察到的状态；只有后续 `status` 返回 `paused` 或 `cancelled` 才证明转换完成。
- C. 快时同步、慢时异步，由实现自行选择，响应不作区分。
- D. 控制调用无返回语义，调用者固定等待后再查询。

推荐：B。原因：它不要求长连接，也不会把请求接受误报成完成；重复调用仍可安全收敛到同一目标。

你的回答：B

#### Q5. 一个 Run 在什么情况下可以自动发布 partial Result，而不是保持 blocked、cancelled 或 failed？

为什么问：已经确认 partial 可以发布，但仍需防止“进程刚好中断”被包装成一份看似正式的结果。

简单例子：发现 2,134 项后只处理了前 500 项就崩溃，这不是有界 partial；如果 Result 明确声明一个封闭子集、遗漏范围和限制，并通过完整性验证，才可能是诚实 partial。

选项：

- A. 只有 Run 达成了一个可明确描述、可完整核算的终止边界，并且 Result 契约验证成功时才自动发布；普通暂停、中断、阻塞和取消从不触发发布。
- B. 任何不能继续的 Run 都尽量把已有内容发布成 partial，避免浪费工作。
- C. 只自动发布 complete；partial 虽被 Artifact Contract 支持，但本 Tool 暂不产生。
- D. partial 必须重新增加公共 `seal` 或 `publish-partial` 操作。

推荐：A。原因：它同时保留 partial 的产品价值和 Result 的可信边界，而且不增加新操作。

你的回答：A

#### Q6. `status` 的最小稳定进度应该表达什么？

为什么问：百分比和内部阶段容易失真，但只有一句“正在运行”又不足以判断规模、异常和是否值得继续。

简单例子：已发现 10 万项但只核算 2 万项，与已核算 10 万项但存在 3 个异常，下一步判断完全不同。

选项：

- A. 固定业务进度字段：`discovered / accounted / usable / exceptional / unresolved` 计数；未知值显式标记未知。允许附加非权威 ETA，但不要求百分比、内部阶段或 checkpoint。
- B. 只要求 `completed_units / total_units / percent`，具体单位由实现决定。
- C. 只返回状态和一段自然语言进度。
- D. 返回完整内部生产者、缓存和任务队列统计，便于精确诊断。

推荐：A。原因：这些计数直接支持用户判断，并与 PreCheck Result 的核算语义一致；实现仍可自由改变内部任务分解。

你的回答：A

#### Q7. `paused / blocked / failed` 的原因和恢复条件应怎样返回？

为什么问：三个状态都表示当前不再正常推进，但恢复方式完全不同；自由文本不足以让 Agent决定是否重试。

简单例子：磁盘空间不足需要清理空间，源卷断开需要重新挂载，永久配置错误则可能无法恢复。

选项：

- A. 非正常推进状态必须返回结构化 `reason.code`、人类可读 `reason.message`；可恢复时再返回 `resume_when` 或等价的可验证条件，同时由 `allowed_actions` 表明能否调用 `resume`。
- B. 只返回错误代码，解释由调用者查文档。
- C. 只返回自然语言消息，避免冻结原因分类。
- D. `paused / blocked / failed` 都不解释原因，统一让调用者尝试 `resume`。

推荐：A。原因：原因代码支持稳定控制流，消息支持 Human；恢复条件只描述外部可观察事实，不暴露 checkpoint 或实现阶段。

你的回答：A

#### Q8. `completed` 状态应返回多少已发布 Result 信息？

为什么问：操作者需要立刻知道 Result 是否可用于 Plan，但 Result 本身仍必须是三轴状态的唯一权威。

简单例子：Run 已完成并发布 `partial + blocked + valid` Result；仅看到 `completed` 会被误解成“可以开始 Plan”。

选项：

- A. 返回 `published_result`，包含 `result_ref` 和从该不可变 Result 精确复制的 `coverage / readiness / integrity`；其他内容通过 `mediasense.precheck.read` 读取。
- B. 只返回 `result_ref`，调用者必须再读取 Result 才能知道质量。
- C. 在 `status` 中返回完整 Result，省去后续 Tool 调用。
- D. 返回三轴状态但不返回 `result_ref`。

推荐：A。原因：它防止把 `completed` 等同于 plan-ready，同时不在 Working Run 中建立第二份可变质量权威。

你的回答：A（依据用户授权，按工程推荐确认）

#### Q9. `plan.work create` 应接受哪些 PreCheck Result？

为什么问：PreCheck `completed` 不保证 plan-ready。如果对 blocked 或 untrusted Result 创建 Working State，下游必须猜测何时允许 seal。

简单例子：`coverage=partial, readiness=plan_ready, integrity=valid` 可以在声明范围内规划；`readiness=blocked` 表示 Evidence 尚不足。

选项：

- A. 只接受 `readiness=plan_ready` 且 `integrity=valid` 的 Result；`coverage` 可为 complete 或 partial。成功返回 `work_ref / result_ref / revision`。
- B. 接受所有 `integrity=valid` Result；blocked Result 也可创建 Working State，但在问题解决前禁止 seal。
- C. 接受任何已发布 Result，包括 `integrity=invalid`，由 Agent 自行判断。
- D. `create` 不检查 Result；只在 `seal` 时检查。

推荐：A。原因：blocked Result 已经明确表示不满足 Plan 入口；Agent 仍可通过 `precheck.read` 调查并用 `precheck.run start(prior_result_ref)` 继续准备，无需制造不可封存草稿。

你的回答：A（由第 2 轮 Q16=A 最终确认）

#### Q10. Plan 的组织偏好是否需要进入 Tool 拥有的 Working State？

为什么问：组织偏好已确定暂不成为 Profile 实体，但仍需决定它是可恢复的项目状态，还是只存在于 Agent 上下文。

简单例子：用户要求最多三层。Agent 会话重启后，如果 Tool 没有保存这个约束，新的 Agent 可能生成四层目录。

选项：

- A. `create` 可接收 `organization_preferences`；Tool 保存并随 revision 返回精确快照，后续修改也必须通过 `update`。它不是独立实体，也没有 `profile_ref`。
- B. 偏好只属于 Agent 任务上下文；Tool 只保存已经形成的候选组织内容。
- C. Tool 只保存会被机械验证的硬约束，命名风格等软偏好留给 Agent。
- D. 把偏好写进 Frozen Plan 的 `decision_notes`，不在 Working State 单独保存。

推荐：A。原因：Plan Working State 的价值之一是跨调用保持 Human 已表达的组织意图；把快照放在现有 Work 中不需要新实体。偏好的具体字段仍应只包含用户可见策略，不能混入算法参数。

你的回答：A（依据用户授权，按工程推荐确认）

#### Q11. Plan revision 应是可排序序号，还是只用于等值绑定的 opaque token？

为什么问：revision 的稳定意义决定并发保护方式；如果承诺连续整数，就会把无关的存储和分支方法冻结进接口。

简单例子：两个 Agent 都从 revision R1 开始更新。第一个成功后，第二个必须得到冲突，而不是覆盖 R2。

选项：

- A. 使用单调递增整数；调用者可以比较大小和推算前后顺序。
- B. 使用 opaque revision token；只承诺同一 `work_ref` 内可用于精确读取和等值并发检查，不承诺格式或连续性。`update` 必须传 `base_revision`。
- C. 直接用候选内容 digest 作为 revision，不再区分两者。
- D. 不公开 revision，以最后写入为准。

推荐：B。原因：调用者真正需要的是精确绑定和检测陈旧写入，不需要依赖内部版本编号方法。

你的回答：B（依据用户授权，按工程推荐确认）

#### Q12. `plan.work update` 的最小变更语义应是什么？

为什么问：局部 patch 需要冻结工作态字段路径或额外 group ID；自然语言又会让 Tool 自己做主观决定。

简单例子：Agent 把两个集合放进同一逻辑目录。Tool 应保存确定结果，而不是再次解释“把晚餐照片整理好”。

选项：

- A. 定义一套业务 patch：`set_root / put_group / remove_group / set_other_outcome` 等；所有 change 原子应用。
- B. 每次提交一份完整 `candidate_content`，原子替换当前候选；内容使用 Frozen Plan 已有组织语义，但不包含最终 `plan_ref`、seal 或 Human confirmation。
- C. 使用通用 JSON Patch，路径直接指向 Working State 的序列化结构。
- D. 接收自然语言修改要求，由 Tool 解释并改写状态。

推荐：B。原因：Frozen Plan 被设计为紧凑结果；完整替换不需要新增工作态 group ID 或 patch 语言，也不会限制更强 Agent 的编辑方法。若未来真实规模证明替换成本不可接受，再用证据增加局部更新。

你的回答：B（依据用户授权，按工程推荐确认）

#### Q13. `plan.work inspect` 在未指定 revision 时应怎样工作？

为什么问：交互式查看通常希望看到当前内容，但确认和分页又必须绑定精确 revision。

简单例子：调用者未指定 revision 发起 inspect；在响应期间另一个 Agent 更新了 Work。响应必须明确自己读的是哪一版。

选项：

- A. `revision` 永远必填；不知道当前 revision 时无法 inspect。
- B. `revision` 可选；省略时原子解析为当时的当前 revision，响应必须返回精确 token。后续 page cursor 和 seal 都绑定该 token。
- C. 允许字面值 `latest`，响应不需要回显解析后的 revision。
- D. inspect 始终跟随最新内容，分页过程中也可以跨 revision。

推荐：B。原因：首次进入和恢复操作足够简单，同时每份实际返回仍有不可歧义的 revision 锚点。

你的回答：B（依据用户授权，按工程推荐确认）

#### Q14. `inspect` 的 section、分页、完整性和候选内容身份应怎样组合？

为什么问：大 Working State 不能保证单次返回全部内容，但 Human 最终确认的 identity 必须对应完整候选，而不是某一页。

简单例子：groups 有 500 页。第 3 页的 digest 不能被误当成整个 Frozen Plan 候选的 digest。

选项：

- A. 请求可选择 `content / validation / preferences` 等 section；每个 cursor 绑定 `work_ref + revision + section + 查询形状`。页面返回 `complete / next_cursor`。若整个 revision 已形成可 seal 的完整候选，每一页都可返回同一个全局 `candidate_content_identity`；否则不返回该字段。
- B. 每页各有一个 page identity，调用者自行合并成最终 identity。
- C. 只有取完所有页的最后一次响应才返回候选 identity，Tool 不允许直接跳页。
- D. inspect 只返回摘要，完整内容通过未来的新 Tool 获取。

推荐：A。原因：它延续现有 PreCheck read 的精确 cursor 绑定，并保证分页只是传输方式，不改变候选内容的全局身份。

你的回答：A（依据用户授权，按工程推荐确认）

#### Q15. `seal` 的最小输入、成功输出、重复调用和错误外壳应怎样固定？

为什么问：这是 Human authority、并发、Frozen Plan 可取得性和跨 Tool 一致性汇合的最后边界；若只返回 `plan_ref`，当前又没有 Frozen Plan read Tool，artifact 将无法取得。

简单例子：Human 确认 revision R7 后，Agent 又写入 R8；或者 seal 已成功但响应丢失。Tool 必须拒绝陈旧确认，并能安全返回同一个结果。

选项：

- A. 请求必须含 `work_ref + revision + candidate_content_identity + request_id`；可信认证上下文另行提供 Human confirmation。Tool 原子核对 revision、identity、确认，关闭 Work 并返回完整 `frozen_plan`、`plan_ref / result_ref / content_identity`。同一请求安全重试返回同一 artifact。错误沿用 `precheck.read` 的 `outcome: error` 外壳，并增加最小代码：`work_not_found / work_closed / revision_conflict / idempotency_conflict / content_identity_mismatch / confirmation_required / invalid_state`；既有 Result 引用错误继续使用既有代码。
- B. 请求只含 `work_ref`；Tool 自动选择当前 revision 和 identity，成功只返回 `plan_ref`。
- C. 请求提交完整 Frozen Plan；Tool 只负责验证和存储，不读取 Working State。
- D. seal 允许在没有 Human confirmation 时先生成 provisional plan，稍后再补确认。

推荐：A。原因：所有必要锚点都来自已经存在的 Work、revision、内容身份和认证上下文；没有新增 Confirm 或 Frozen Plan Read Tool，也不会把陈旧确认用于新内容。

你的回答：A（依据用户授权，按工程推荐确认）

### 第 1 轮整合说明

- Q1-Q7：用户已在文档中直接回答，答案分别为 A、B、A、B、A、A、A。
- Q8、Q10-Q15：用户授权按工程推荐确认，已写入对应答案。
- Q9：其中的引用校验、三轴读取和 seal 保护属于工程规则；真正需要 Human 判断的阶段入口选择改写为 Q16。

### 第 2 轮：唯一业务分歧

工程可靠性问题已全部按推荐收敛。本轮只保留一个会改变真实产品流程的问题：Evidence 明确不够时，是否仍允许提前建立 Plan Working State。

#### Q16. `readiness=blocked` 的 PreCheck Result 是否允许提前创建 Plan Working State？

为什么问：这决定 `readiness` 是严格的阶段入口，还是只限制最后 seal。两种选择都会显著改变用户和 Agent 的工作方式。

简单例子：Result 已经可靠核算来源，但明确缺少足够 Evidence，状态为 `partial + blocked + valid`。Agent 可以先讨论目录偏好，也可以先回到 PreCheck 补证据再开始 Plan。

选项：

- A. 严格阶段入口：`plan.work create` 只接受 `plan_ready + valid`；coverage 可以是 complete 或有界 partial。blocked Result 只能经 `precheck.read` 调查，并通过新的 PreCheck Run 补足后再创建 Plan。
- B. 允许探索性 Plan：任何 `integrity=valid` Result 都可创建 Working State；blocked Result 可以保存偏好和候选判断，但禁止 seal，且绑定新 Result 时必须创建另一份 Working State。
- C. 只接受 `complete + plan_ready + valid`；即使 partial 已被判定 plan-ready，也不允许进入 Plan。
- D. 只要 Result 已发布就允许 create 和 seal；三轴仅供提示，不作为硬门。

推荐：A。原因：`readiness` 的稳定目的就是回答“能否进入 Plan”。允许 blocked Result 创建不可封存草稿会产生一个容易成为死胡同的生命周期；而 partial + plan-ready 已经保留了在明确子范围内工作的能力。

你的回答：A

## 被拒绝选项

- 合并三条 Tool 边界：可变 Run、不可变 Result 读取、可变 Plan Working State 的权威对象、权限和生命周期不同。
- 独立 `reopen`：`start(prior_result_ref)` 已完整承载谱系，不损失能力。
- 公共 PreCheck `seal`：完整或有界 partial Result 的验证与原子发布属于 Run 完成语义。
- 独立 Plan `preview / validate`：它们只是在同一 revision 上读取和渲染，没有独立效果或生命周期。
- Organization Profile 实体或 `profile_ref`：尚无跨 Dataset 复用、独立版本和独立维护生命周期的证据。
- 公共内部阶段、checkpoint、SQLite 或缓存接口：它们是可替换方法，不是产品权威。
- 独立 Confirm Tool：Human confirmation 可以由 `seal` 的可信认证上下文承载。
- 两套 CLI 与 Agent Tool 契约：适配器可以不同，操作语义只能有一份权威。

## 未决问题

无阻塞项。

## 质量门

- [x] 问题包开头提供小型端到端 JSON 候选示例，并明确不是正式 Schema。
- [x] 没有重复询问用户已接受的 Tool 边界、动作集合、状态名、自动发布、Human confirmation 或 Profile 非实体化决定。
- [x] 每个问题都会改变稳定输入、输出、状态转换、并发、重试、分页、seal 或错误语义。
- [x] 没有询问 SQLite、目录布局、缓存、checkpoint、CLI 参数、UI、认证实现或 Skill 内部流程。
- [x] 与既有 PreCheck Read Contract 和 Frozen Plan Contract 的权威边界保持一致。
- [x] 没有增加缺乏独立责任、权限或生命周期的 Tool、实体或操作。
- [x] 用户完成第 1 轮回答；Q1-Q7 为直接答案，其余工程问题按用户授权采用推荐答案。
- [x] 第 2 轮只保留真正改变产品阶段入口的业务分歧。
- [x] 用户回答 Q16=A；`readiness` 成为严格 Plan 入口。
- [x] 所有回答已整合，当前无阻塞项。
