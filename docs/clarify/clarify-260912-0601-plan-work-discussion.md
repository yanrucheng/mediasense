---
id: "clarify-260912-0601-plan-work-discussion"
title: "Plan Work 交互与落盘契约讨论"
type: clarify
status: active
created: 2026-09-12
updated: 2026-09-12
timezone: "Asia/Shanghai"
parent: "index-clarify"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "clarify-260827-0107-plan-frozen-contract"
  - "clarify-260827-1604-tool-operation-contracts"
  - "plan-work"
  - "frozen-plan"
  - "eval-260912-0224-plan-memory-risk-audit"
superseded-by: ""
tags: [plan, contract, interaction]
---

# Plan Work 交互与落盘契约讨论

本页记录本次设计讨论，沿用“短业务例子 → 请求与返回 → 选择及后果 → 用户回答”的本地讨论方式。**设计已定稿，用户已确认进入研发，当前合约已同步。** 本次沿用预览 HTML 后聊天确认，额外确认通道升级不在范围内。以下样例是合成契约案例，不是 Tool 实际返回；`working_notes` 是本次定稿的新字段，运行实现与交付验收仍待开发。当前规范见 [Plan Work 合约](../spec/contract/plan-work/index.md)，本页保留讨论和授权依据。

## 已有约定与本轮范围

历史讨论中已经确认：

- [Frozen Plan 澄清](clarify-260827-0107-plan-frozen-contract.md)：先证明业务价值，再决定实体和字段；未保存某种记录不自动意味着功能缺失。正常组织只保留最终决定，特殊决定保留最短理由，完整对话和调查过程不进入 Frozen Plan。
- [Tool 操作澄清 Q10—Q15](clarify-260827-1604-tool-operation-contracts.md)：偏好属于既有 Work；revision 为不透明 token；完整替换 Candidate，避免额外 group ID 和 patch 语言；最终确认绑定确切内容。
- 同记录 Q16：只有 plan-ready、可被可信 Read 读取的 Result 才进入 Plan。讨论中的未完成 Work 不等于放开 blocked Result 的入口。
- [当前合约入口](../spec/contract/index.md)：`index.md` 解释含义，JSON Schema 定义交换值，JSON/JSONC 为可检查的例子；合约定稿与实现完成是两个不同里程碑。历史协议示例不替代当前格式。

本次已经讨论一致的方向是：Agent 主动获取组织决策所需的信息，能够先和用户讨论，再调用 Tool 落盘。信息形式与调查方法开放。下面只讨论 Tool 是否额外保存“足以继续的工作说明”，不要求 Tool 管理每个问题、逐步调查或全部用户输入。

**目的锚：** Agent 需要保存时，能把有意义的工作成果交给下一次继续；不需要时仍可一次提交完整组织。

**归宿锚：** 未完成工作的已保存说明属于既有 Work；被确认的最终组织属于 Frozen Plan；原 Result 的事实和范围不被改写。

## 一个共同的合成场景

已经存在可信且 `plan_ready` 的 `precheck-result:demo`。本例范围只有两个源项：`source-item:a`、`source-item:b`；为方便阅读，使用显式 Source Set，大数据仍可复用 `represents` 等既有紧凑表达。

用户希望日后按活动找回素材，保留文件名。Agent 通过材料与用户讨论，已确认 a 属于展览参观；b 的活动身份尚不明确。用户可能直接说明 b，也可能给出补充资料或表示不记得。Agent 根据实际回答继续判断，不由 Tool 选择下一问。

两条都合理的路径：

- **A：继续讨论，明确全部组织后一次提交。** 当前 Tool 已支持，不需要保存每轮对话。
- **B：用户希望先停下，或 Agent 判断工作值得保存。** 用一个可选的工作说明快照保存当前理解与未决影响；以后读回。新增能力仅服务于这一需要。

本轮 B 先讨论更小的候选：`working_notes` 为自由文本，偏好沿用 `organization_preferences`；完整 Candidate 仍沿用现有格式。它不承诺机器可恢复、渲染或校验一棵未完成的目录树。若这样的说明不足以支持你需要的接续，下一轮才比较结构化草稿。

## 1. 创建同一个 Work：沿用现有形状

以下均展示 `mediasense.plan.work` 的业务请求；MCP 的 `dataset_ref`／传输包装本轮不改变。`tool/request/response` 仅是文档中的调用记录格式。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "create",
    "result_ref": "precheck-result:demo",
    "organization_preferences": {
      "retrieval_goal": "按活动查找",
      "preserve_source_basenames": true
    },
    "request_id": "request:demo-create"
  },
  "response": {
    "outcome": "ok",
    "action": "create",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:a",
    "state": "open",
    "organization_preferences": {
      "retrieval_goal": "按活动查找",
      "preserve_source_basenames": true
    }
  }
}
```

工具没有因创建 Work 就执行一轮调查。Agent 可以在创建前或创建后与用户交流；被保存的偏好只包含用户已表达的内容。

## 2. B 路径：只保存当前工作说明，尚无 Candidate

这是本轮要讨论的实际新增承诺。延用 `update` 和同一个 revision，不增加 Note ID、Question ID 或专用保存 Tool。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "update",
    "work_ref": "plan-work:demo",
    "base_revision": "work-revision:a",
    "working_notes": "用户已明确 source-item:a 属于展览参观，仅适用于 a。source-item:b 的活动身份尚不明确，会影响它与 a 合并还是独立命名。现有材料不足以判断；尚无完整候选。后续需要补充信息，或与用户明确采用较粗的归属。",
    "request_id": "request:demo-save-notes"
  },
  "response": {
    "outcome": "ok",
    "action": "update",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:b",
    "state": "open"
  }
}
```

这个 `ok` 只证明工作说明已保存。它不证明 Agent 判断正确、所有源项都有最终去向、补充文件已被解析，也不代表用户确认了最终方案。`update` 的返回继续作为写入回执，完成度由 `inspect` 查询；第三轮沿用这个边界，不另加摘要字段。

## 3. 换会话后读取：说明能恢复，完成度明确

下例增加 `working_notes` section。第三轮补齐默认 inspect：仍返回全部 section，无 Candidate 时正常读取并返回 `content: null`，见例 9。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "inspect",
    "work_ref": "plan-work:demo",
    "sections": ["preferences", "working_notes", "validation"]
  },
  "response": {
    "outcome": "ok",
    "action": "inspect",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:b",
    "state": "open",
    "returned_sections": ["preferences", "working_notes", "validation"],
    "sections": {
      "preferences": {
        "retrieval_goal": "按活动查找",
        "preserve_source_basenames": true
      },
      "working_notes": "用户已明确 source-item:a 属于展览参观，仅适用于 a。source-item:b 的活动身份尚不明确，会影响它与 a 合并还是独立命名。现有材料不足以判断；尚无完整候选。后续需要补充信息，或与用户明确采用较粗的归属。",
      "validation": {
        "seal_ready": false,
        "issues": [{
          "code": "candidate_missing",
          "severity": "error",
          "message": "当前没有完整组织候选；工作说明已保存。"
        }]
      }
    }
  }
}
```

没有可冻结的 `candidate_content_identity`。恢复的是 Agent 明确保存的说明，不是全部会话或模型上下文。说明是 Agent 的工作摘要，其中“用户已明确”的表述也不是 Tool 出具的可信最终认证。

## 4. 讨论完成后提交完整组织：保留一次提交路径

此时用户说明 b 属于另一场家庭聚会。Agent 已据此确定最终组织，再写入完整 Candidate。下面沿 B 路径使用 revision b，并更新工作说明，消除旧的未决描述。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "update",
    "work_ref": "plan-work:demo",
    "base_revision": "work-revision:b",
    "working_notes": "用户分别说明 a 为展览参观、b 为家庭聚会；Agent 已形成两个独立活动的组织候选。局部事实说明不构成最终版本确认，尚待审阅该候选。",
    "candidate_content": {
      "result_ref": "precheck-result:demo",
      "scope": {
        "kind": "explicit",
        "source_item_refs": ["source-item:a", "source-item:b"]
      },
      "logical_root": "周末活动",
      "groups": [
        {
          "relative_path": ["展览参观"],
          "members": {"kind": "explicit", "source_item_refs": ["source-item:a"]},
          "source_naming": {"default": "preserve_source_basename"}
        },
        {
          "relative_path": ["家庭聚会"],
          "members": {"kind": "explicit", "source_item_refs": ["source-item:b"]},
          "source_naming": {"default": "preserve_source_basename"}
        }
      ],
      "other_outcomes": [],
      "decision_notes": [{
        "applies_to": {"kind": "explicit", "source_item_refs": ["source-item:b"]},
        "summary": "依据用户补充，将 b 作为独立的家庭聚会组织，未沿用 a 的活动身份。"
      }]
    },
    "request_id": "request:demo-submit-candidate"
  },
  "response": {
    "outcome": "ok",
    "action": "update",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:c",
    "state": "open"
  }
}
```

**A 路径跳过第 2、3 个例子**，把上述 `base_revision` 改为创建返回的 a，省略 `working_notes`，直接提交同一份完整 Candidate。这就是当前 Tool 能支持的先讨论、后落盘；B 不应让它多出必经步骤。

完整候选经 inspect 取得确切内容和 identity 后才进入最终审阅。`seal` 仍绑定 Work、revision、完整内容 identity 和可信人类确认；工作说明不自动进入 Frozen Plan，也不构成 Apply 输入。完整候选之后只更新说明的情况由第二轮补齐，不能仅凭第一轮样例推定。

## 5. 一个失败例子：旧 revision 不能覆盖后来保存的工作

假设当前 revision 已为 b，另一个调用仍持有 a：

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "update",
    "work_ref": "plan-work:demo",
    "base_revision": "work-revision:a",
    "working_notes": "仍以旧工作内容为基础的修改。",
    "request_id": "request:demo-stale-write"
  },
  "response": {
    "outcome": "error",
    "action": "update",
    "work_ref": "plan-work:demo",
    "revision": "work-revision:b",
    "error": {
      "code": "revision_conflict",
      "current_revision": "work-revision:b",
      "message": "工作内容已经变化，请读取当前版本后再决定如何合并。"
    }
  }
}
```

没有保存该次修改；Tool 不把两份文字自行融合。相同 request_id 和相同有效请求重试仍返回原回执，改变请求则沿用 idempotency_conflict。超时本身不证明未保存，应按现有回执和执行控制语义恢复。

## 这几个字段为什么存在

| 内容 | 权威与用途 | 不能据此声称 |
| --- | --- | --- |
| `organization_preferences` | 用户实际表达的组织偏好，在 Work 中保存 | 不是客观来源事实，也不授权 Tool 自己推断分组 |
| 建议的 `working_notes` | Agent 选择保存的可继续工作说明；允许自然语言 | 不是全部对话、已验证事实、材料存储或可信确认 |
| `candidate_content` | 一份完整且可机械校验的组织决定 | 结构完整不证明名字正确，也不证明用户已确认 |
| `decision_notes` | 随最终组织保留的最短必要解释 | 不承担整个工作期信息仓库 |
| `revision` | 以上已保存 Work 内容的共同版本边界 | 不是语义正确度或调查进度 |

本轮推荐“可选工作说明”的理由是它复用现有 Work 和 revision，允许自由表达，不要求设计 Question、Claim、Attachment 或半成品 group 实体。它也有真实限制：Tool 无法机器校验工作说明里的语义引用，无法从中可靠渲染部分目录，不能保证每个重要事实已被 Agent 摘要。这些不能以 `ok` 隐去。

如接受这一方向，建议的简单写入含义为：`working_notes` 传入时完整替换，省略时保留，空字符串清空；已有偏好省略／替换／空对象清空的含义沿用。一次 update 至少提供一项实际内容。完整 Candidate 一旦提供，仍需通过现有校验；如果同时提交的 Candidate 不合法，整次原子写入不生效。它不是一种“有错的 Candidate 先落盘”的方案。

## 第一轮：可选工作说明（方向已认可）

需要决定的是：**除了完整 Candidate，MediaSense 是否要提供上述“可选保存工作说明”的承诺？**

推荐先考虑 B：保留当前完整 Candidate 结构，只给既有 Work 增加可选的文字工作说明。它足以演示“先保存，再换会话继续”，又不引入结构化草稿树和过程托管。A 仍是有效选择；如果恢复能力由会话承担已足够，则可以完全不改 Plan Work。若希望 Tool 在组织尚未完整时也能逐组渲染、核验和恢复，则属于比 B 更强的结构化草稿设计，需要另举例子说明收益。

用户回答：**“我觉得这符合我的预期。继续”**。

整合：可选工作说明属于已有 Work，Agent 可以先讨论后提交，也可以自主选择保存时机；不引入结构化半成品目录、问题实体或过程托管。这是第一轮方向与示例的认可，后续边界继续讨论，不能视为整个合约定稿或开发放行。

## 第二轮：完整候选已经存在后，怎样更新工作

本轮建议固定一个可观察关系：`revision` 对应整个已保存 Work；`candidate_content_identity` 对应完整组织内容。工作说明不进入 Frozen Plan，因此只改说明可以产生新 revision，同时保留相同的候选内容身份。Tool 不从说明文字推断是否应改组、重新调查或请求用户确认；Agent 用明确请求表达对候选的处置。

接续第 4 个例子：当前版本为 `work-revision:c`，已有“展览参观／家庭聚会”的完整候选。按现有编码规则，示例 `frozen-plan:demo` 的候选内容身份为 `sha256:5640cff1778c552adba0473feac26b85890ad86246a5243611d1a9d7786da470`。这是用合成内容计算的示例身份，不是一次真实发布。

### 6. 补充工作说明，保留当前候选

Agent 补记了判断来源，认为它不改变当前组织。省略 `candidate_content`，明确使用“保留当前内容”的字段语义。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "update",
    "work_ref": "plan-work:demo",
    "base_revision": "work-revision:c",
    "working_notes": "补记：a、b 的活动身份来自用户分别说明。Agent 保留现有的两个活动分组；尚待用户审阅最终候选。",
    "request_id": "request:demo-note-source"
  },
  "response": {
    "outcome": "ok",
    "action": "update",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:d",
    "state": "open"
  }
}
```

读取同一候选的校验与身份：

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "inspect",
    "work_ref": "plan-work:demo",
    "sections": ["validation"]
  },
  "response": {
    "outcome": "ok",
    "action": "inspect",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:d",
    "state": "open",
    "returned_sections": ["validation"],
    "sections": {
      "validation": {"seal_ready": true, "issues": []}
    },
    "candidate_content_identity": "sha256:5640cff1778c552adba0473feac26b85890ad86246a5243611d1a9d7786da470"
  }
}
```

组织内容没有改变，所以 digest 不改变，结构校验也不需要因一条工作说明重新变成失败。`seal_ready` 不证明文字说明正确、符合全部用户偏好或已经取得最终确认。说明若改变了重要解释，Agent 应把最终需审阅的解释放进完整候选的 `decision_notes`，或使用下面的撤下／替换操作，不能只在工作说明里写相反结论后继续声称组织已被修正。

### 7. 新信息使当前组织需要重审，撤下待冻结候选

用户补充的信息让 b 的归属出现实质冲突，Agent 尚未形成替代方案。建议允许 `candidate_content: null`，表示撤下当前候选；不是一个空目录，也不是排除所有来源项。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "update",
    "work_ref": "plan-work:demo",
    "base_revision": "work-revision:d",
    "working_notes": "新信息对 b 的活动归属提出冲突。上一候选需要重审；已撤下待冻结候选，尚未决定替代组织。",
    "candidate_content": null,
    "request_id": "request:demo-withdraw-candidate"
  },
  "response": {
    "outcome": "ok",
    "action": "update",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:e",
    "state": "open"
  }
}
```

读回完成度：

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "inspect",
    "work_ref": "plan-work:demo",
    "sections": ["working_notes", "validation"]
  },
  "response": {
    "outcome": "ok",
    "action": "inspect",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:e",
    "state": "open",
    "returned_sections": ["working_notes", "validation"],
    "sections": {
      "working_notes": "新信息对 b 的活动归属提出冲突。上一候选需要重审；已撤下待冻结候选，尚未决定替代组织。",
      "validation": {
        "seal_ready": false,
        "issues": [{
          "code": "candidate_missing",
          "severity": "error",
          "message": "当前没有组织候选；工作说明和已保存偏好仍可读取。"
        }]
      }
    }
  }
}
```

这里清除的是 Work 中的当前 Candidate 及其可冻结身份。工作说明和偏好保留，Work 仍为 open；不删除任何已经发布的 Frozen Plan，不触碰媒体，也不承诺自动恢复被撤下候选的历史版本。重新进入可冻结状态需要 Agent 提交完整候选。若 Agent 已确定新组织，可以直接在一次 update 中提交新的完整 `candidate_content`，无需先撤下再提交。

这项权衡是用显式清空实现最小控制，不增加“候选仍保留但已过期”的第二套状态与重新启用 action。若需要在 Tool 中同时保存旧候选供比较／修改，再禁用其冻结，则需要另行比较该产品收益；本轮未默认加入。

### 8. revision 更新与最终确认各检查什么

假设当前仅完成例 6，revision 为 d，候选内容与 c 完全相同。旧 seal 请求若仍写 c，将得到 revision_conflict；这是并发保护，不意味着组织内容身份已改变。下面假定调用已提供与示例内容匹配的可信确认上下文，排除“没有确认”这个更早的拒绝条件。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "seal",
    "work_ref": "plan-work:demo",
    "revision": "work-revision:c",
    "candidate_content_identity": "sha256:5640cff1778c552adba0473feac26b85890ad86246a5243611d1a9d7786da470",
    "request_id": "request:demo-stale-seal"
  },
  "response": {
    "outcome": "error",
    "action": "seal",
    "work_ref": "plan-work:demo",
    "revision": "work-revision:d",
    "error": {
      "code": "revision_conflict",
      "current_revision": "work-revision:d",
      "message": "工作版本已变化；请读取当前版本后再提交精确请求。"
    }
  }
}
```

Agent 读回当前 d 后，如果组织内容仍是用户已经确认的精确内容，且该确认仍然有效，可以使用当前 revision、同一候选 identity 和新的 request_id 请求 seal；不因单纯记录文字变化强制重复询问。Tool 不从工作说明里的“已确认”获得认证。用户撤回或修正了接受意思时，Agent／可信交互层不能仅因 digest 相同而把旧确认视为有效。

若例 7 已撤下 Candidate，当前 e 没有可冻结对象；即使调用带着旧内容身份，也不得发布。如果之后提交的是另一份内容，原确认不匹配新的 identity。完整候选未改、只修改用户偏好时同样由 Agent 决定保留、撤下还是直接替换；Tool 不自动解释任意偏好字段是否影响组织，也不把保留的结构校验当作偏好符合性认证。

### 本轮候选规则

| `candidate_content` 的输入 | 对当前候选的效果 | 保存后是否可冻结 |
| --- | --- | --- |
| 省略 | 保留当前候选；不存在则仍不存在 | 沿用实际候选的结构校验，仍须可信最终确认 |
| 完整对象 | 通过现有校验后原子替换 | 以新完整内容的 identity 和可信确认判断 |
| `null` | 撤下当前候选，清除其可冻结身份 | 不可冻结，需重新提交完整候选 |

`working_notes` 和偏好仍按各自省略／替换／清空规则处理。以上可以在同一次 update 原子组合；任何字段或候选非法，整次修改不保存。重复 request_id 仍按现有幂等规则返回原结果。closed Work 继续拒绝修改，不新增“重新打开旧 Frozen Plan”的路径。

本轮推荐：**保留这些明确操作，由 Agent 决定是否撤下或替换候选，Tool 不从说明文字推断。** 这使补充说明不强迫重做组织；实质冲突又有一种立即阻止当前候选冻结的明确操作。

用户回答：**“没问题，如果这个是工业上，社区普遍遵循的设计的话，我就同意。”**

### 行业与社区依据核对（2026-09-12）

核对结论：核心工程机制有成熟标准和社区项目的明确先例，可以按这一方向收敛；整套 MediaSense 产品规则并不是某一份行业标准。下面分别列出每份依据实际支持的部分，避免把相近概念说成协议兼容。

| 本轮机制 | 一手依据 | 能支持的结论与边界 |
| --- | --- | --- |
| 省略保留，`null` 显式清空 | [RFC 7396 §1–2：JSON Merge Patch](https://www.rfc-editor.org/rfc/rfc7396.html#section-2) | 标准已有未涉及成员保持不变、`null` 删除成员的语义。该 RFC 对对象递归合并；本页的完整 Candidate 替换不采用它的递归规则，不能把 `update` 称为 JSON Merge Patch。 |
| Work 可部分更新，Candidate 对象整体替换 | [Kubernetes Server-Side Apply：Merge strategy](https://kubernetes.io/docs/reference/using-api/server-side-apply/#merge-strategy) | 社区项目允许把 map／struct 声明为 `atomic`，只能整体替换；嵌套对象不必逐字段合并。本页仅借鉴这个更新粒度，仍沿用本地 Q12 的完整 Candidate；不引入 Kubernetes 的字段所有权或省略字段删除规则。 |
| 用当前 revision 拒绝陈旧写入／冻结 | [RFC 9110 §13.1.1：If-Match](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1)、[Google AIP-154](https://google.aip.dev/154) | 修改前核对客户端所见资源版本，以防并行写入相互覆盖，是成熟的乐观并发控制。本页使用现有 opaque revision 与 `revision_conflict`，不把业务 Tool 的传输声称为 HTTP If-Match。 |
| 确认对应具体审阅内容，失效条件由产品明确 | [GitHub：Require pull request reviews before merging](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-pull-request-reviews-before-merging) | GitHub 可记录获批时的 diff，并在 diff 改变后使批准失效；也提供其他审阅策略。这是内容绑定审阅的成熟先例，不是 MediaSense 确认有效期或撤回机制的规范。 |

“省略／提供／清空”并非所有 API 的统一语法；例如 [Google AIP-134](https://google.aip.dev/134#request-message) 使用 `update_mask` 明确更新范围。本页继续采用适合既有 Tool 的小型字段契约：三个字段各自的替换与清空含义必须写清楚，不能依赖 Agent 猜测某一种 PATCH 习惯。

本地产品选择仍需明示：`null` 使 Work 不再有待冻结 Candidate；不承诺被撤下候选的历史恢复。`revision` 和候选 identity 继续各守既有范围：前者保护整份已保存 Work，后者标识最终组织内容。只补记说明不机械要求用户重复确认；前提是组织内容未变、原确认仍有效。用户撤回接受或提出实质修正时，相同 digest 不会替代其当前意思。上述标准不能替 MediaSense 决定这些业务含义。

整合：**记录用户的有条件认可，核心工程机制的依据已核实，不再重复征询同一机制。** 第二轮的业务边界继续作为整份合约最终审阅的明示内容；不把“有成熟先例”扩大成所有细节的行业共识或正式开发放行。

## 第三轮：补齐可以交接开发的边界

用户要求：**“最终的目的是要把这个设计定好，然后让另外一个Agent可以开始开发。”**

下面收敛可从已确认方向与既有契约推导的工程细节。完整行为、改动归属、验收与精确拟议 patch 已放入[开发交接包](../../openspec/changes/refine-plan-interaction/README.md)，避免下一位 Agent 重新猜测本轮含义。

### 9. 默认读取刚创建的 Work

接续例 1，当前仍为 a，还没有 Candidate，也没有保存说明。省略 sections 仍表示读取全部；不再因为缺候选而使整次 inspect 失败。

```json
{
  "tool": "mediasense.plan.work",
  "request": {
    "action": "inspect",
    "work_ref": "plan-work:demo"
  },
  "response": {
    "outcome": "ok",
    "action": "inspect",
    "work_ref": "plan-work:demo",
    "result_ref": "precheck-result:demo",
    "revision": "work-revision:a",
    "state": "open",
    "returned_sections": ["overview", "preferences", "working_notes", "content", "validation"],
    "sections": {
      "overview": {"state": "open"},
      "preferences": {
        "retrieval_goal": "按活动查找",
        "preserve_source_basenames": true
      },
      "working_notes": "",
      "content": null,
      "validation": {
        "seal_ready": false,
        "issues": [{
          "code": "candidate_missing",
          "severity": "error",
          "message": "当前没有组织候选；已保存的工作说明和偏好仍可读取。"
        }]
      }
    }
  }
}
```

`null` 表示没有对象，`""` 表示空说明；没有新增“探索中”等状态。有候选时仍沿用现有 complete／paged content。说明按普通 JSON string 完整保存和读回，不另设未经规模证据支持的字段专属字符上限或分页；现有整体入口资源限制仍适用，不能静默截断。只改说明、偏好或撤下候选不触发 PreCheck Read、模型或 Geo。

### 10. 实际 MCP 调用与返回包装

这是例 2 的传输形状。`request` 是业务请求；MCP 的 `content` 不是 Plan 的 Candidate content。一次普通保存不需要确认信息。

```json
{
  "request": {
    "jsonrpc": "2.0",
    "id": 41,
    "method": "tools/call",
    "params": {
      "name": "mediasense.plan.work",
      "arguments": {
        "dataset_ref": "dataset:demo",
        "request": {
          "action": "update",
          "work_ref": "plan-work:demo",
          "base_revision": "work-revision:a",
          "working_notes": "a 为用户已说明的展览参观；b 的活动身份仍影响组织决定，需要补充信息。",
          "request_id": "request:demo-mcp-save"
        }
      }
    }
  },
  "response": {
    "jsonrpc": "2.0",
    "id": 41,
    "result": {
      "content": [],
      "structuredContent": {
        "outcome": "ok",
        "action": "update",
        "work_ref": "plan-work:demo",
        "result_ref": "precheck-result:demo",
        "revision": "work-revision:b",
        "state": "open"
      },
      "isError": false
    }
  }
}
```

业务完成以 structuredContent 中的 outcome 为准；不额外塞入自然语言副本、预览路径、确认状态或下一步指令。最终确认沿用下述既有客户端路径。

### 补充材料、最终展示与失败行为

| 边界 | 本轮收敛 |
| --- | --- |
| 换会话恢复什么 | 恢复 Agent 实际保存的说明、偏好与候选；不宣称恢复完整对话。 |
| 用户提供的原件 | 可通过适当授权能力读取和使用；本次不自动托管原件。需要后续复核时，依赖实际具备保留／读取保证的能力，仅有路径时明确限制。 |
| 最终依据 | 重要补充及其来源、范围进入既有 decision_notes；evidence_refs 仍只引用 Result 内 Evidence。 |
| 最终展示 | 必须交付影响接受的 decision_notes 及适用范围，修复内置渲染器丢失说明的问题；working_notes 不自动进入最终方案。 |
| 组合写入失败 | 任意提供值非法或 Candidate 校验失败，整次不保存；不发生“说明先保存、候选后来失败”。 |
| 重复、并发和取消 | 沿用现有回执、revision、提交及 seal recovery；同值新写入也产生新 revision，相同请求重试不产生。 |

其余错误例子和连续状态变化在交接包的 interaction.mock.json 中。该文件是合成契约案例，不要求 Agent 按它的调用顺序工作。

### 最终确认：保留预览 HTML 后聊天接受

当前 Plan Host 的模型是：信任本地客户端传入的 transport authority，并检查其中的内容身份与 Candidate 匹配。它没有像当前 PreCheck／Geo 一样，通过 MCP Human elicitation 收取这一次接受。这是现有[单用户本地信任边界](../../readme/agent-integration.md#trust-boundary)，不能把参数匹配宣称为 Host 独立验证了一次真实用户点击。

Agent 曾提议复用 MCP Human elicitation，并把它列成最后必选项。用户随后要求用浅显的前后例子解释，并说明：**“我会看一个它产生的一个预览HTML，然后我看了觉得预览HTML挺好，我就跟它说行。”**

澄清后收窄范围：这条既有流程满足本次目标，MCP 确认入口升级是额外产品选择，不应成为本次开发前置。Agent 撤回该前置项，本包继续沿用客户端传递实际聊天接受的方式；不将用户要求解释记成已经批准了新入口或整包开发。

| 情形 | 用户看到的过程 |
| --- | --- |
| 现有最终确认 | Agent 给出最终预览 HTML → 用户说“行” → Agent 传递对这份方案的接受 → Tool 冻结同一份内容。 |
| 曾提出的 MCP 备选 | Agent 给出最终预览 → 客户端通过确认卡片等界面收取接受 → Host 生成确认上下文 → Tool 冻结。它改变接受的入口，本次不采用。 |
| 本次设计的正常流程 | Agent 在重要信息不足时先讨论，得到足够支持后给出最终预览 HTML → 用户说“行” → 沿现有方式冻结。无需新增确认按钮。 |

例如，Agent 先询问两段素材是否属于同一场活动，用户补充“后半段是另一场聚会”，这只是补充信息；Agent 据此生成两个分组的最终 HTML，用户看后说“行”，才是对这份方案的最终接受。若依据已经充分，可直接展示最终预览，不为满足模板强行提问。

用户接受的是所看方案的确切内容。Agent 后来改动组织或重要解释，需要展示新候选；只补写内部工作说明、且原接受仍有效时，不要求用户重复接受。冻结仍不等于 Apply 授权。

### 定稿与研发放行

用户在上述流程澄清后确认：**“所以简单来说，我们后续的研发可以开始了，是吧？”**

结合此前逐轮认可及最新的进入研发确认，本包按已讨论范围定稿并放行开发；没有将用户表述扩大为新增确认入口、真实 Dataset 操作或发布安装授权。当前 Plan Work 合约、Foundation 与本地存储职责已同步，开发可从[交接入口](../../openspec/changes/refine-plan-interaction/README.md)开始，无需重新确认已收敛的字段或流程。

合约携带 22 组正向／业务失败交换、6 组非法输入，以及开发范围和验收要求。设计阶段已通过 schema 编译、交换值及反例、示例 digest 与版本关系检查；实现与安装验收单独完成，不能用合约通过代替。当前 Zero BC 政策继续适用。
