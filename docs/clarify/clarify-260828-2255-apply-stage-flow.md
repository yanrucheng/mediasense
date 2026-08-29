---
id: "clarify-260828-2255-apply-stage-flow"
title: "MediaSense Apply 阶段流程澄清"
type: clarify
status: active
created: 2026-08-28
updated: 2026-08-29
timezone: "Asia/Shanghai"
parent: "index-clarify"
depends-on:
  - "design-260823-1918-mediasense-foundation"
  - "design-260825-2235-mediasense-information-architecture"
  - "spec-260827-1138-frozen-plan"
  - "eval-260823-1918-ai-album-migration-baseline"
superseded-by: ""
---

# MediaSense Apply 阶段流程澄清

## 当前设计

本轮先确定 Apply 的完整业务流程、异常分支和完成条件，不提前定义 Schema、字段、Tool 数量、数据库或目录结构。能够由既有安全不变量、上游契约和成熟工程实践确定的行为采用专业默认值，不要求用户逐项确认；只把会改变产品体验或风险承担方式的决定留作问题。

Apply 从用户已经在 Plan 阶段看过组织效果并认可之后开始。Plan 如何生成或渲染预览不属于 Apply。Apply 只负责把一个精确、不可变、已经 Human-confirmed 的 Frozen Plan 安全落实为真实文件系统变化，不得重新解释分组、成员、名称或例外。

当前正常流程是：

```text
用户已认可 Plan 的组织效果
  -> 用户选择 original 式移动和实际目标位置
  -> Apply 在不修改媒体的前提下检查现实条件
  -> Apply 展示一页真实影响摘要
  -> 用户作一次最终确认
  -> Apply 执行并持续展示进展
  -> Apply 核对计划效果与实际结果
  -> 保留很短的安全恢复窗口
  -> 结束
```

执行前检查若发现明确阻塞项，一个文件都不移动。Apply 一次性报告已发现的全部阻塞项，等待用户处理后重新检查；非阻塞警告可以进入最终确认页。执行已经开始后发生的意外不能抹去已经完成的事实，也不能把部分完成报告成全部成功。

语义或组织问题返回 Plan；足以动摇原计划的源变化经 Plan 返回 PreCheck；权限、空间、目标状态、I/O、中断和恢复等执行问题留在 Apply。Apply 不得通过自动改名、替换目标或更换移动机制来绕过问题。

### 已采用的专业工程默认

1. 当前首要 Apply profile 是 AI Album `original` 对应的原媒体移动。历史 copy/link 能力进入迁移账本，后续按独立价值交付；暂缓不等于声称其不存在或无需覆盖。
2. 目标目录可以已有内容，但完整映射中只要出现目标冲突就阻塞。Apply 不覆盖、不自动改名，也不逐项打断用户临场命名。
3. 跨文件系统移动是显式高风险路径：先复制、逐项验证，再删除对应源。它必须在执行摘要中明确披露并单独确认，不能从同盘移动静默退化而来。
4. 大规模执行期间允许目标树逐步可见，但未验证完成前始终标为进行中或未完成，不能被呈现为可交付的最终结果。
5. 磁盘断开、目标身份变化、journal 无法可靠更新或其他全局风险出现时，立即停止发起新操作；允许已经开始的单项安全收尾，然后重新检查。
6. 暂停和取消都不自动反向移动已经完成的文件。暂停保留可恢复执行；取消结束本次执行并诚实保留部分结果及其记录。
7. 崩溃或机器重启后先观察源和目标的当前事实，再从未完成处向前恢复。不能确认的项停止，不从头盲重放，也不自动先回滚。
8. 执行期间发现外部改动时，停止受影响操作；若它可能影响整批安全，则暂停整批。Apply 不寻找替代源、不自动改名，也不把“目标存在”直接当作已完成。
9. `original` 只移动 Frozen Plan 覆盖的媒体，不顺便清理源目录。目录清理是额外破坏性能力，需要独立需求才能加入。
10. 事后验证强度随风险变化：同文件系统移动验证对象身份、最终位置和原位置消失；跨文件系统传输在删除每个源之前验证目标内容完整。
11. 用户可以明确结束一个无法补齐的部分结果，但它永久保持“未完整”，并列明缺失项和原因；用户接受不把事实改写为全部成功。
12. 单个文件发生局部失败时，记录该项并继续其他相互独立且仍然安全的操作；整次执行保持未完成，修复后只补齐遗漏项。可能影响其他项的错误仍按全局风险立即暂停。
13. 成功完成后提供一个很短的整次 rewind 窗口。rewind 前重新检查源、目标和碰撞；条件不再安全时拒绝。首版不支持任意挑选文件或分区恢复。

### 端到端参考实例

参考输入采用现有 `frozen-plan:local-artifact-example-002`。它把七个 Source Items 组织到 `Media/` 下六个逻辑分组，其中包括普通图片、一个依靠上下文归组的损坏视频、一个明确进入 `d-damaged-info/` 的无效 MP4、一个修复参考文件和一个可读但语义未解决的视频。

用户选择把这份 Plan 以 `original` 方式移动到实际目标父目录 `/Volumes/Archive`；Frozen Plan 的 `logical_root: Media` 因而解析为最终组织根 `/Volumes/Archive/Media`。目标父目录与计划内逻辑根不能混为同一个概念。Apply 的用户可见过程如下：

1. **准备。** Apply 验证 Frozen Plan 身份、seal、所绑定 PreCheck Result 和所有 Source Item 引用，解析七个当前源位置及七个最终绝对目标。这里不会修改媒体。
2. **预检。** Apply 检查源对象仍与计划兼容、目标根身份与写权限、同盘或跨盘条件、可用空间、完整路径碰撞和 journal 是否能够可靠落盘。无效媒体容器本身不是移动阻塞项：只要源字节仍可安全读取，`source-item:215` 仍应作为普通文件移动到已计划的异常目录。
3. **影响摘要。** 用户看到 Frozen Plan 身份、`original` 效果、实际目标、七项总数、数据量、同盘或跨盘执行方式、预计目录、警告和零阻塞结论。无需审阅七行 source-to-target 表；有需要时可以展开核查。
4. **最终确认。** 用户确认的是这一次精确执行内容，而不是授权 Apply “想办法完成”。确认后、首个文件变更前，Apply 再检查易变化的安全条件；发现漂移则回到阻塞状态，不消耗授权执行另一套内容。
5. **执行。** Apply 先留下足以恢复的 durable 记录，再逐项移动并持续报告已完成、剩余、失败和当前阶段。目标树可以逐步出现，但始终标明尚未完成。
6. **局部异常。** 假设第四项在预检后发生临时读取错误。Apply 记录该项失败，继续其余独立安全项，最终显示 `6/7 已完成，1 项待处理`，而不是报告成功。用户修复后，只重新检查并补齐这一项。
7. **验证。** 同盘移动核对七个对象均位于精确目标、原位置消失且没有额外覆盖；跨盘移动则在删除每个源前逐字节验证目标内容，并核对声明的用户相关属性。只有完整闭合，或精确属性损失已被重新授权并留痕后，才可删除源并报告该项完成。
8. **收据。** Apply 封存实际结果，绑定原 Frozen Plan、真实目标、执行方式、授权、逐项结果、验证证据和资源事实。Receipt 记录现实，不回写 Frozen Plan。
9. **短期 rewind。** 用户若在窗口内要求整次恢复，Apply 从原 Receipt 构造一次反向 Apply Run，重新预检和确认后执行。原 Receipt 保持不变，反向执行产生自己的 Receipt；历史不会被改写成“第一次从未发生”。

### 由流程推导的最小责任模型

现有 **Frozen Organization Plan** 是 Apply 的不可变语义输入，不是新的 Apply 实体。Apply 只需要两个新的顶层业务实体：

1. **Apply Run**：一次可变、可恢复的执行过程。它绑定一个 Frozen Plan、用户选择的实际效果和目标，拥有预检、影响摘要、精确授权、当前进度、局部失败、暂停、恢复、取消、验证和短期 rewind 执行的生命周期。没有它，就无法诚实表示十万项执行到一半的现实，也无法安全重试。
2. **Apply Receipt**：一次已经结束的执行事实。它是不可变的，证明哪份 Frozen Plan 在什么授权和现实条件下实际发生了什么、是否完整、如何验证，以及是否仍具备 rewind 条件。没有它，用户无法区分计划意图与真实结果，也无法可靠审计或发起整次恢复。

以下信息必要，但不获得独立顶层实体：

- **Apply Authorization** 是 Human 对 Apply Run 中精确内容的绑定，不需要独立 Confirm Tool 或单独权威文件。
- **resolved operations** 是 Run 从 Frozen Plan、源定位和实际目标确定性展开的内容，不是第二份 Plan。
- **preflight / impact summary** 是 Run 的可再生成视图，不是权威产物。
- **journal** 是 Run 履行持久化、幂等和恢复保证的内部机制，不跨阶段成为产品权威。
- **operation outcomes / verification evidence** 是 Receipt 的明细；百万项时可以分片保存或紧凑表达，但逻辑上仍属于一个 Receipt。
- **rewind** 是引用原 Receipt 的新 Apply Run，不引入 Rewind Plan，也不修改原 Run 或 Receipt。

### 生命周期与责任边界

```text
preparing
  -> blocked ---------------------> recheck
  -> ready_for_authorization
       -> executing <-------------> paused / needs_attention
            -> verifying
                 -> completed
                 -> closed_incomplete

completed receipt
  -> short rewind eligibility
       -> new reverse Apply Run
```

- **Human** 决定真实效果、目标位置、最终授权、主动暂停或取消、是否接受永久残余失败，以及是否在短窗口内请求整次 rewind。
- **Agent** 解释影响与阻塞原因、维持用户意图、调用确定性能力，并把组织问题退回 Plan、把源证据问题经 Plan 退回 PreCheck；Agent 不决定文件碰撞的替代名称，也不自行授权高风险效果。
- **Apply Skill** 保存可复用的引导、风险判断和升级标准；加载 Skill 本身不产生授权或文件效果。
- **Apply Tool** 强制执行计划解析、安全门、授权绑定、journal-before-mutation、文件操作、幂等恢复、暂停边界、事后验证和 Receipt 完整性。安全保证必须在这个可执行边界落实。

这一模型暂不固定 Tool action 名、状态枚举、SQLite、journal 格式、锁、批大小、并发度、临时目录或 Receipt 的物理分片方式。

### Run 与 Receipt 的最小稳定语义

Apply Run 至少必须让调用者和恢复逻辑知道：

- 它绑定的精确 Frozen Plan，以及从该 Plan 可追溯的 PreCheck Result；
- 用户选择的真实执行效果和实际目标，而不是一个模糊的“应用计划”意图；
- Frozen Plan 确定性展开后的完整操作覆盖，以及当前准备内容的稳定身份；
- 源兼容性、目标身份、文件系统关系、容量、权限、碰撞等预检结论和仍需处理的阻塞项；
- Human 授权究竟绑定了哪一版执行内容，以及授权后是否发生了需要重新确认的实质变化；
- 当前生命周期、业务进度、局部失败、全局暂停原因和可验证恢复条件；
- 已发生效果的 durable 事实，以及最终发布的 Receipt（如有）。

这些是 Run 必须维护的意义，不要求全部成为一个记录或一个文件。实现可以采用更合适的 journal、数据库、清单、检查点和批处理方法。

Apply Receipt 至少必须证明：

- 它对应的精确 Run、Frozen Plan、执行效果、实际目标和 Human 授权；
- 执行开始时通过了什么预检和源兼容性检查；
- Frozen Plan 展开的所有应处理项均有且只有一个最终结果，没有沉默遗漏；
- 每项实际完成、失败、拒绝或未尝试的事实，以及必要的重试和恢复事实；
- 观察到的最终位置、源位置状态和与风险相称的完整性验证；
- 计划与现实之间的所有差异、残余失败、整体完整性和关键资源事实；
- 短期 rewind 的资格、截止条件，以及由该 Receipt 发起的反向 Run / Receipt 关系（如发生）。

Receipt 不复制 Frozen Plan、PreCheck Result、完整运行日志或内部数据库。它引用这些权威来源，同时必须携带或绑定一份不可变、完整的实际操作账本，保存每个 Source Item 在该次执行中的原位置、预期目标、实际结果和验证结论。原因是移动完成后旧 locator 不再能独立说明现实，rewind 也不能依赖可能已过期的 mutable Run。百万项操作明细在逻辑上属于一个 Receipt，物理上可以分片；分片方式不成为业务实体。

### Apply Tool 边界候选

当前证据支持一条有副作用的 Tool 边界：`mediasense.apply.run`。它拥有同一个 Run 从准备、预检、授权、执行、暂停、恢复、取消、验证到 Receipt 发布的完整保证。

- 预检和执行不能拆成彼此无绑定的 Tool：否则可能检查旧源或旧目标，却执行变化后的现实。
- “preview”只是 Run 的影响摘要视图，不是独立 Tool，也不承担 Plan 的组织效果预览。
- Human 授权通过可信认证上下文绑定精确的准备内容；普通请求字段不能自行声称“用户已确认”，也不增加 Confirm Tool。
- 任何会改变 Frozen Plan、执行效果、目标身份、完整操作覆盖、碰撞结论或用户看到的重要风险的变化，都使原授权失效并回到准备/确认阶段。等价的安全复查不产生新语义版本。
- 暂停、恢复和取消是同一 Run 的控制，不建立新 Run。rewind 会造成一组新的文件效果，因此建立引用原 Receipt 的新反向 Run。
- Run 只有在 Receipt 已可靠发布后，才可以把“最终结果已封存”作为完成事实。Receipt 发布中断属于可恢复的 Run 状态，不能生成两个逻辑结果。

Receipt 是否需要独立 `mediasense.apply.read` 由下述规模压力测试决定。Frozen Plan 可以作为完整紧凑 JSON 直接消费，而百万项 Receipt 需要分页和选择性读取。

### 十万项 Receipt 参考形态

假设一个 Frozen Plan 覆盖 100,000 个 Source Items，用户执行同盘 `original` 移动。运行中经历一次进程重启和一个局部读取失败，恢复后该失败项仍无法处理，用户最终接受未完整结果。

用户首先看到的是可信摘要，而不是十万行日志：

```text
执行结果：未完整
Frozen Plan：frozen-plan:example
效果：同文件系统移动
目标：已验证的 /Volumes/Archive/Media

计划项          100,000
已完成并验证     99,999
失败                  1
拒绝                  0
未尝试                0

恢复次数              1
计划外覆盖            0
计划外改名            0
源对象无法确认        0
短期整次 rewind       可用（覆盖实际完成的 99,999 项）
```

这份摘要背后的逻辑 Receipt 不需要重复保存十万份相同的“成功”：

- Frozen Plan、实际目标和确定性展开规则定义应处理全集；
- `completed_and_verified` 可以表达“全集减去明确异常集合”；
- 一个失败项单独保留源、预期目标、失败阶段、实际观察、重试次数和残余状态；
- 一次重启保留影响结论和恢复依据，不复制完整过程日志；
- 若异常接近全集、压缩不再经济，物理表示可以转为分片明细，但仍是同一个 Receipt 的内容。

这个形态同时满足完整操作闭合、百万项可扩展性和异常可展开性。rewind 针对 Receipt 中“实际完成并验证”的整个效果集合：完整 Receipt 就恢复全部完成项；未完整或取消后的 Receipt 则恢复它实际完成的全部项。它仍然不是让用户任意挑选文件，而是完整反转该次执行已经造成的效果。

### Apply Read 边界结论

规模压力证明需要独立的只读 `mediasense.apply.read`：

- Run 的 `status` 应保持轻量，只报告当前状态、业务计数、阻塞/恢复条件和已发布的 `receipt_ref`；它不负责返回十万项执行事实。
- Receipt 是 Run 结束后仍需被用户、审计、评估和 rewind 消费的不可变权威，生命周期不同于可变 Run。
- 只读边界应能取得 Receipt 摘要，并按结果类别、Source Item 或异常集合逐步展开，且每次读取绑定同一个精确 `receipt_ref`。
- 读取 Tool 不创造新状态、不重新验证历史，也不把存储分片暴露为产品概念。

因此最小 Tool 组合为：

```text
mediasense.apply.run   # prepare / execute / status / pause / resume / cancel
mediasense.apply.read  # inspect / traverse immutable Receipt
```

这里固定的是操作责任。正式 review 契约已采用 `execute`：它把可信 Human 授权绑定到精确 prepared content，并开始或继续对应的文件效果，不能先产生一个可被其他执行内容复用的裸授权对象。若跨盘传输后来发现精确属性损失，Run 必须形成新的 prepared revision；同一 `execute` 动作可绑定这次额外授权，但旧授权不能复用。

### Apply Run 操作与生命周期候选

`mediasense.apply.run` 的最小公共行为可以收敛为：

| 行为 | 用户可见意义 | 关键边界 |
| --- | --- | --- |
| `prepare` | 以 Frozen Plan 准备正向执行，或以 Receipt 准备整次 rewind；创建新 Run 并开始无副作用检查 | 两种输入互斥；具有安全重试身份；不产生媒体变更 |
| `status` | 查看当前阶段、业务计数、影响摘要、阻塞/恢复条件和当前允许操作 | 不返回全量逐项记录 |
| `execute` | 以可信 Human 上下文确认精确准备内容并开始文件效果 | 授权内容漂移即拒绝；具有安全重试身份 |
| `pause` | 请求停止发起新操作，允许在途单项安全收尾 | 接受请求不等于已经暂停 |
| `resume` | 在重新验证恢复条件后继续同一 Run | 不能借 resume 更换目标、模式或计划 |
| `cancel` | 停止本次 Run，不自动反向移动 | 授权前零效果结束；执行已被接受后先停止、验证，再发布 `closure: human_cancelled` 的 Receipt，完整度由 `completion` 独立表达 |

生命周期稳定含义如下，正式枚举名仍可在契约阶段压缩：

```text
preparing
  ├─ blocked ──(恢复条件满足后 resume/recheck)──┐
  └─ ready_for_authorization                    │
          └─ execute ─> executing <─> paused ───┘
                           ├─ needs_attention ──> resume / cancel
                           └─ verifying
                                  └─ closed + immutable receipt
```

- `blocked` 在首次文件效果前保持零媒体变更；`needs_attention` 表示已经可能存在真实效果，二者不能混成一个模糊错误状态。
- `closed` 只说明事实已经通过 Receipt 封存；Receipt 自己区分完整、未完整、取消后部分完成或其他诚实结果。
- 成功路径和已经补齐全部失败项的恢复路径自动验证并封存，不要求用户再按一次“完成”。
- 用户在 `needs_attention` 中决定不再补齐时调用 `cancel`；只有没有操作仍在运行、当前事实已尽可能验证、残余项可完整列出后，Run 才发布 `closure: human_cancelled` 的 Receipt，并用 `completion` 如实区分完整或未完整。
- 在任何可能已有文件效果的路径上，终态都必须有 Receipt；只有尚未授权且保证零效果的准备 Run 才可被放弃而不产生 Apply Receipt。
- 一旦 `execute` 已被接受，Run 结束时就必须发布 Receipt，即使最终零项完成；它仍需说明哪些操作未尝试、拒绝、失败或无法确认。若因持久存储损坏等原因无法发布可信 Receipt，Run 不得冒充 closed，而应保持可观察的严重失败或待接管状态并披露可能已发生的效果。
- 外部进程崩溃不是新的产品状态。重启后从 durable Run 恢复为可观察的准备、执行、暂停、待处理或验证状态。
- 准备阶段本身可能需要检查十万项来源，因此同样可观察、可暂停、可取消和可恢复；只有 `execute` 之后才允许媒体变更。
- 预检通过不是永久通行证。Tool 在每个文件效果边界重新验证相关源和目标条件，并以不可覆盖的原子语义提交；若无法避免检查与变更之间的竞态，则该操作阻塞。
- 同盘移动以逐文件原子、不覆盖的 rename 效果为基础；跨盘移动先写入目标文件系统上的非最终位置，完整验证并以不覆盖方式发布最终目标后，才删除对应源。具体系统调用与刷新策略留给实现证明。
- Apply 创建的目录也是可观察效果。Receipt 记录哪些目录由本 Run 新建；rewind 只删除本 Run 新建且当时仍为空、未被外部改变的目录，永不删除执行前已存在的目录。
- Tool 在真实目标文件系统上检查大小写折叠、Unicode 规范化、路径长度、保留名称和别名后的冲突；不能只按 Frozen Plan 的字符串比较结果判断无碰撞。
- 两个活动 Run 不得同时改变同一个源对象或最终目标。并发冲突必须在产生效果的边界被强制阻止；锁或 reservation 的实现形式保持开放。
- 如果多个路径实际指向同一对象，或 symlink、hard link、mount 边界使“移动哪个对象”产生歧义，预检阻塞，不能猜测跟随或复制语义。
- 跨盘路径必须逐字节验证内容，并尽可能保留时间、权限、扩展属性、Finder 标签等用户相关文件系统属性。任何属性无法保留时，都必须在删除对应源文件前阻塞，精确披露受影响 Source Item、属性、预期值和实际值，把这组差异绑定到新的 prepared content，并重新取得 Human 授权；旧的执行授权不能延用。Receipt 永久记录实际未保留属性、接受它们的授权绑定和删除源后的验证事实；实现不得用“copy 成功”代替移动等价性证明。
- 首版拒绝源范围与最终组织根互相包含或重叠，避免执行过程改变尚待处理的输入命名空间；若未来支持原地重组，必须以独立用例重新设计顺序和恢复保证。
- durable Run 与 Receipt 发布状态不能只保存在源卷或目标卷上；其中任一卷断开后，系统仍需知道已经发生的效果和安全恢复条件。具体本地存储位置保持开放。
- 恢复时，只有目标对象与该项 verification basis 匹配且源已缺失，才可把“目标已存在”归类为此前已完成；其他目标存在一律视为碰撞或不确定状态。

### 七项 Run / Receipt 参考交互

以下实例用于审查责任和最小信息，不是 Schema，也不是实际执行声明。Plan 身份、seal、七项 scope 和逻辑路径来自现有 Frozen Plan；实际挂载位置、同盘条件、文件大小、源验证依据和故障时点是为了压力测试而明确添加的假设。

#### 1. `prepare` 后的用户视图

```text
Apply Run：apply-run:example-001
Frozen Plan：frozen-plan:local-artifact-example-002
确认内容：sha256:c21577e7565299a6a2f4c486bb8fe9764ad373ab266e61f4265085499633a114

执行效果：移动原媒体（original）
目标父目录：/Volumes/Archive
最终组织根：/Volumes/Archive/Media
文件系统：同一文件系统，可使用逐项原子移动

计划覆盖：7 项
源对象验证：7 项通过
最终目标：7 项唯一
既有目标碰撞：0
阻塞项：0
警告：1 项媒体内容不可解码，但源字节可读且 Plan 已明确安排到 d-damaged-info/

下一步：确认并开始执行；或取消且不产生任何媒体变化
```

Agent 默认只展示这份摘要。详细视图可展开 Source Item、原位置、最终目标和单项检查，但用户无需逐行批准。

#### 2. 授权绑定

Human 确认绑定的是：精确 Plan content identity、`original` 效果、解析后的目标根身份、七项完整操作账本、同盘执行路径和当前披露的风险。`execute` 在首个变更前复查这些条件。若目标盘被重新挂载、任一目标出现、源验证结果改变或操作覆盖变化，原授权失效，Run 回到准备或阻塞状态。

#### 3. 执行中一次局部失败

```text
状态：executing
已完成并验证：4 / 7
当前失败：1
尚未尝试：2

source-item:217
预期目标：.../0504-示例章节/Uncategorized/DJI_20260504202728_0029_D.remux-faststart.MP4
结果：临时读取失败；未创建最终目标，原文件仍在
处置：记录失败并继续另外 2 项独立操作
```

其他两项完成后，Run 进入 `needs_attention`，显示 `6/7 已完成，1 项待补齐`。用户修复读取问题并 `resume`；Tool 只重新验证和执行 `source-item:217`，不重复移动前六项。

#### 4. 最终 Receipt 用户视图

```text
Apply Receipt：apply-receipt:example-001
结果：全部完成并验证
Frozen Plan：frozen-plan:local-artifact-example-002
执行效果：同文件系统移动
目标父目录：/Volumes/Archive
最终组织根：/Volumes/Archive/Media

计划项：7
完成并验证：7
失败 / 拒绝 / 未尝试 / 无法确认：0 / 0 / 0 / 0
计划外覆盖：0
计划外改名：0
恢复次数：1
重试完成：source-item:217

短期整次 rewind：当前可用
```

Receipt 内的操作账本可以证明两个具体例子：

- `source-item:215` 从 PreCheck Result 中记录的原 locator 移动到 `Media/260501-示例复杂事件/d-damaged-info/DJI_20260504202728_0029_D.MP4`；虽然媒体容器无效，但字节对象已按 Plan 完成移动和位置验证。
- `source-item:217` 从原 locator 移动到 `Media/260501-示例复杂事件/0504-示例章节/Uncategorized/DJI_20260504202728_0029_D.remux-faststart.MP4`；首次尝试失败，恢复后完成并验证。

#### 5. 整次 rewind

用户在短窗口内提出 rewind。系统从 `apply-receipt:example-001` 的实际完成集合创建新的反向 Run，目标是七项各自的原位置。它重新检查原位置没有被新文件占用、当前目标仍是本次移动后的同一对象、两端文件系统与权限可用，然后再次显示影响摘要并取得 Human 确认。反向 Run 完成后产生新的 Receipt；原 Receipt 仍然证明第一次移动确实发生过。

#### 6. 说明性逻辑形态（不是 Schema）

下面只验证信息责任能否闭合；名称、嵌套、枚举和序列化均可在正式契约中调整。

```yaml
apply_run:
  ref: apply-run:example-001
  direction: forward
  frozen_plan:
    ref: frozen-plan:local-artifact-example-002
    content_identity: sha256:c21577...
  effect: move_originals
  destination:
    parent: /Volumes/Archive
    resolved_logical_root: /Volumes/Archive/Media
    observed_identity: <准备时验证的目标位置身份>
  prepared_content:
    revision: <opaque token>
    identity: <绑定完整操作覆盖与重要风险的内容身份>
    scope_items: 7
    file_operations: 7
    execution_route: same_filesystem_atomic_move
    blockers: 0
    warnings: 1
  authorization:
    state: confirmed
    confirmed_prepared_content: <同一 prepared content identity>
    authority: <由可信认证上下文取得>
  lifecycle:
    state: closed
    completed_and_verified: 7
    receipt_ref: apply-receipt:example-001

apply_receipt:
  ref: apply-receipt:example-001
  run_ref: apply-run:example-001
  frozen_plan_ref: frozen-plan:local-artifact-example-002
  authorized_effect: move_originals
  completion: complete
  closure: automatic
  accounting:
    planned_scope: 7
    completed_and_verified: 7
    exceptions: []
  verification:
    planned_targets_present: 7
    original_locations_absent: 7
    unplanned_overwrites: 0
    unplanned_renames: 0
  metadata_preservation:
    profile: same_filesystem_rename_v1
    content_verification:
      profile: filesystem_identity_and_location
      result: verified
    checked_attributes: [filesystem_identity_and_location]
    unpreserved_attributes: []
    accepted_discrepancy_refs: []
    discrepancy_authorizations: []
  recovery:
    resume_count: 1
    recovered_item_refs: [source-item:217]
    rewind_window_ends_at: <策略确定的截止时刻>
  operation_ledger:
    coverage: all planned items
    representation: <内嵌、紧凑或分片均可>
```

`rewind_window_ends_at` 只记录承诺窗口；“现在是否仍可安全 rewind”必须在新反向 Run 的 `prepare` 中重新观察，不能作为 Receipt 中永远为真的布尔值。

### AI Album Apply 相关能力迁移判断

| 历史能力或行为 | MediaSense 判断 | Apply 处置与理由 |
| --- | --- | --- |
| `original` 移动原媒体 | `preserved` | 作为首要 Apply profile，保持用户最终看到原件进入确认目录的效果 |
| 完整 bundle 展开，包括 sidecar 与不可解码成员 | `preserved` | Frozen Plan 对 Source Items 完整核算；不可解码不等于不可移动 |
| 按 cluster 层级生成目录树 | `preserved` | 由 Frozen Plan 的逻辑根、相对路径、成员和名称确定性物化 |
| 默认保留 basename | `preserved` | 无 Plan override 时保持源 basename |
| 同名时自动追加源父目录消歧 | `intentionally_changed` | 名称是 Plan 语义；Apply 预检发现碰撞即阻塞，不自行改变组织结果 |
| 默认生成唯一 `<input>-clustered` 路径 | `intentionally_changed` | Apply 可提供可解释的目标建议，但实际目标必须进入影响摘要并由用户授权 |
| 显式目标可以是已有目录 | `preserved` | 允许已有目录，但完整目标映射必须无碰撞且不会覆盖既有内容 |
| 预先计算完整 source-to-target 映射 | `preserved` | 升级为授权和完整性检查所依赖的确定性准备内容 |
| 预建目标目录 | `preserved`（方法开放） | 保留高效批处理能力；具体创建顺序服从 journal 与恢复设计 |
| 并发文件操作 | `preserved`（质量属性） | 保留大规模吞吐要求；并发度、调度和背压不进入稳定契约 |
| 同文件系统 rename | `preserved` | 作为普通 `original` 快速路径，并验证目标与源后置条件 |
| 跨文件系统静默 fallback 为 copy-delete | `intentionally_changed` | 改为明确披露、单独授权、复制后强验证再逐项删除源 |
| move/copy 可能覆盖既有目标 | `intentionally_changed` | 无条件拒绝计划外覆盖；安全门属于 Tool 保证 |
| 操作失败只打印或返回值未聚合 | `intentionally_changed` | 每项结果进入 Run 与 Receipt；局部失败继续但整批不冒充成功 |
| `thumbnail` 组织预览 | `preserved`，但不属于 Apply | 由 Plan 的可再生成预览承担；Apply 不重复实现 |
| `print` cluster | `intentionally_changed`，且不属于 Apply | 由 Plan/Frozen Plan 的可读视图替代，不继承 Python 内存结构输出 |
| relative symlink 输出 | `preserved` 目标、首版 Apply 暂缓 | 保留迁移项；其来源依赖、断链、rewind 与验证语义需独立 profile 设计 |
| copy 输出 | `preserved` 目标、首版 Apply 暂缓 | 保留迁移项；与 move 的来源保留、空间和完成语义不同，后续独立 profile 设计 |
| 一次组合多个 output types | `intentionally_changed` | 每次 Run 绑定一种明确效果，避免不同风险和结果混成一个不可恢复执行 |
| 终端进度 | `preserved` 并加强 | 以业务计数、阶段、失败、阻塞与恢复条件替代仅有进度条 |
| 无 journal、无完整 Receipt、无可靠重启 | `intentionally_changed` | 引入 Run durable state、幂等恢复、验证和不可变 Receipt |

首版不交付 copy/link 不是功能否认，也不能在最终迁移验收中标为已 preserved；在对应 profile 被设计、实现和比较前，它们保持明确 deferred。

### Agent 与 Human 可操作性约束

- `prepare` 和 `execute` 会创建身份或授权文件效果，必须带安全重试身份；同一身份加相同请求返回同一结果，同一身份加不同请求报告冲突。
- `pause`、`resume`、`cancel` 以目标状态保持幂等。控制请求被接受只证明系统开始收敛，后续 `status` 才证明已经停止发起操作、恢复执行或完成取消。
- `status` 在每个状态返回当前业务计数、重要阻塞或不确定性、可验证恢复条件，以及当前允许的新控制操作；人或 Agent 不需要从错误字符串猜下一步。需要重新授权的属性差异由 Run 拥有，必须完整、内容身份绑定、可由 Human 取得，并支持有界读取。内联、文件、分页或数据库投影都只是实现方法，不进入稳定契约。
- Human 摘要默认采用渐进披露：先展示效果、两端位置、规模、执行路径、阻塞和风险，再允许展开逐项映射。详细信息可隐藏，决策相关事实不可隐藏。
- `execute` 必须让 Human 看见授权后的中断、取消、rewind 能力和局限，不能用一个泛化的 `yes` 掩盖跨盘删除源或元数据损失。
- `apply.read` 的每次读取绑定精确 `receipt_ref`；分页或 cursor 同时绑定 section、筛选和顺序。摘要计数与完整 operation accounting 必须可以机械核对。
- 人类视图和 Agent 机器视图可以不同，但必须对 Run 状态、目标、授权范围、实际效果、未确认项和 Receipt 结论保持同义。

### 最小本地持久化边界

Apply 需要一个独立于源卷和目标卷的本地 store。候选最小形态是：一个承载可变 Run 与 journal 责任的事务性 `work.sqlite3`，以及一个承载不可变 Receipt 的 `receipts/` 区域。小 Receipt 可为单个 JSON；大 Receipt 可由一个权威 manifest 发现不可变操作分片。物理分片不产生新的业务实体。

journal 不单独成为文件契约或第三个权威对象。它是 Run 为兑现“先记录再变更、崩溃后可判定、重复执行幂等”所需的内部持久信息。Receipt 发布采用非覆盖、可恢复的协议；只有完整、可验证的 Receipt 与 Run 终态一致时，才报告封存成功。

不固定 SQLite 表、journal mode、分片编码、阈值、锁实现、`fsync` 策略或垃圾回收规则。稳定约束是：Run 状态不随媒体卷断开而丢失，Receipt 不依赖 mutable Run 才可解释，二者发布不一致时能够恢复且不会生成第二个逻辑 Receipt。

### 压力测试结论

端到端实例经过以下故障点检查：

| 故障点 | 流程结论 | 是否需要新实体 |
| --- | --- | --- |
| Frozen Plan 或引用集合无法完整解析 | Run 在准备阶段阻塞，不形成另一份 Plan | 否 |
| 当前 locator 指向的对象是否仍是原 Source Item 无法证明 | 危险移动不得开始；返回 PreCheck/Plan 补足可信源绑定 | 否，但暴露上游契约缺口 |
| 计划中的损坏媒体不可解码但字节可读 | 按既定目标正常移动；Apply 不重新判断媒体语义 | 否 |
| 预检后单项读取失败 | 记录失败并继续独立安全项，Run 保持未完成 | 否 |
| 目标盘掉线或挂载身份改变 | 停止发起新操作，Run 进入待处理并重新预检 | 否 |
| 进程在文件变化后、journal 完成标记前崩溃 | 恢复时观察两端事实再归类，不盲目重复 | 否 |
| Receipt 写入前崩溃 | Run 仍是权威工作状态；恢复并完成验证或封存 | 否 |
| 完成后整次 rewind | 以原 Receipt 为依据建立新的反向 Run；两个 Receipt 都保留 | 否 |

唯一实质性跨阶段缺口是 **可验证源绑定**：现行 PreCheck Read 最低契约要求 Source Item 提供 `locator`，但没有保证 Apply 能证明当前路径仍指向 Plan 所确认的同一个源对象。Apply 的稳定要求应是“高风险执行前必须得到足以验证源兼容性的依据”，而不是把某一种 hash、inode、mtime 或设备标识永久写死。具体依据应由上游契约补足或明确提供；若无法证明，Apply 必须阻塞，不能把路径相同当作对象相同。

专业判断是：不新增 Source Snapshot、Source Verify Tool 或 Apply 自有源身份实体。PreCheck Result 已逐项核算 Source Items，现有 Source Item 又允许携带开放式 Observation；最小修正应让危险 Apply 能从精确 Result 解析每个计划内 Source Item 的不可变验证依据，并按声明的验证 profile 检查当前对象。该依据应支持普通文件替换或内容变化的可靠检测，但不把 PreCheck 的缓存 key、内部依赖图或跨 Result 永久资产身份暴露给 Apply。

这样得到的是“精确 Result 中的每项来源都可验证”，不是会导致全局失效的 Dataset Snapshot。具体 digest 算法、文件系统身份组合和增量计算方法仍需后续性能设计；它们必须满足所声明的检测能力，不能把历史 AI Album 的 partial hash 直接当作强内容证明。

## 证据

- 用户确认正常主流程是：先在 Plan 查看组织效果；满意后在 Apply 大规模执行 `original` 式原媒体移动。
- 用户确认无副作用检查后展示一页影响摘要，只作一次最终确认，然后开始执行。
- 用户确认执行前发现明确阻塞项时，一个文件都不移动，解决问题后重新检查。
- 用户要求 AI Album 经真实大规模迁移使用的业务能力必须逐项覆盖；任何不保留的能力都要给出可审查理由。
- 用户要求 Apply 采用专业工程判断，只保留真正高风险或有业务分歧的问题。
- Foundation 要求 Apply 不作新语义决定，拒绝静默覆盖和未计划改名，区分同文件系统移动与显式授权的跨文件系统传输，先记录再变更，支持重启与幂等，并执行事后验证。
- AI Album 历史实现提供 `print`、`thumbnail`、`link`、`original`，并具有完整映射计算、目标目录预建、并发操作、basename 保留和同名消歧等行为，但缺少可靠的覆盖拒绝、journal、完整结果汇总和可验证恢复。

## 已确认决策

1. Plan 负责组织效果预览；Apply 不设计或实现 Plan 的预览流程。
2. Apply 的起点是用户已经认可一个 Frozen Plan，并明确提出真实文件变更意图。
3. 正常流程依次是：选择实际执行意图与目标、无副作用检查、影响摘要、一次最终确认、执行、验证、短期安全恢复窗口、结束。
4. 执行前只要存在明确阻塞项，就不修改任何媒体；Apply 集中报告问题，修复后重新检查。
5. 运行中已经完成的效果必须如实保留和报告；中断或局部失败不得伪装为未开始或全部成功。
6. Apply 不得作语义判断，也不得静默改名、换目标、降级执行方式或改写 Frozen Plan。
7. AI Album 的历史业务能力必须逐项分类为 `preserved`、`intentionally_changed`、`regression` 或 `not_comparable`。
8. MediaSense 尚未投产，采用 Zero Backward Compatibility。
9. 单项局部失败采用隔离后继续：不隐藏失败，不阻塞其余独立安全操作，后续精确补齐遗漏项。
10. 成功完成后支持短窗口内整次 rewind；不承诺任意粒度撤回，恢复条件不安全时拒绝。
11. Apply 流程采用“已采用的专业工程默认”继续收敛，当前流程层无剩余阻塞项。
12. Apply 的最小顶层业务实体为可变的 Apply Run 与不可变的 Apply Receipt；Frozen Plan 是既有输入，其余候选概念归入 Run、Receipt 或可再生成视图。
13. rewind 复用完整 Apply 流程并创建新的反向 Run 和 Receipt；原执行历史保持不可变。
14. Agent 负责引导和路由，Human 负责高风险授权，Tool 负责可执行安全保证；Skill 不拥有授权或运行时事实。
15. 可验证源绑定是危险 Apply 的硬入口条件；具体身份或指纹机制保持开放。仅有 locator 而无法证明当前对象兼容时，不得开始执行。
16. Apply Run 与 Apply Receipt 的最小稳定语义已经确定；物理 journal、数据库和分片方法保持开放。
17. 预检、影响摘要和执行属于同一 `mediasense.apply.run` 责任边界，以保持检查、授权和实际效果的精确绑定；不增加 Preview Tool 或 Confirm Tool。
18. 独立 `mediasense.apply.read` 的必要性必须由大规模 Receipt 读取证据证明；第 20 项记录压力测试后的结论。
19. 十万项压力测试证明 Apply Receipt 可以用“确定性全集减异常集合”紧凑表达，并在必要时物理分片；一个逻辑 Receipt 不拆成多个业务实体。
20. 增加独立只读 `mediasense.apply.read`，用于摘要和渐进展开不可变 Receipt；`apply.run status` 不承载大规模执行明细。
21. 任何带已完成文件效果的终态 Receipt 都可以在短窗口内整次反转其实际完成集合，包括用户接受的未完整结果；这不是任意粒度撤回。
22. Apply Run 候选公共行为收敛为 `prepare / status / execute / pause / resume / cancel`；`prepare` 可互斥接收 Frozen Plan 正向来源或 Receipt rewind 来源，`cancel` 同时覆盖主动停止和接受残余未完整结果，最终拼写可变，但每项责任不可隐去。
23. 首次文件效果前的阻塞与已有文件效果后的待处理必须可区分；所有可能已有文件效果的终态都发布 Receipt。
24. 源兼容性采用 Result 内逐 Source Item 的可验证依据，不新增 Dataset Snapshot 或 Source Verify 顶层实体；现行 PreCheck 最低契约需要为危险 Apply 补足这一能力。
25. AI Album Apply 相关能力已逐项给出迁移判断；copy/link 保持 deferred，不能被误报为首版已交付。
26. Apply 本地持久化只保留可变 Run store 与不可变 Receipt store 两种权威生命周期；journal 属于 Run 内部责任，不成为第三个产品实体。
27. 正式契约必须以可证伪场景覆盖零效果预检、目标竞态、跨盘失败窗口、并发 Run、取消、Receipt 发布恢复、整次 rewind 与十万项有界读取。
28. 跨盘移动必须逐字节验证内容并尽可能保留时间、权限、扩展属性、Finder 标签等用户相关属性；任何精确属性损失都在删源前阻塞，进入新的 prepared revision 并重新取得 Human 授权，Receipt 保留差异与授权绑定。

## 问题清单

### 第 1 轮：仅剩的高风险业务选择

原有 13 个问题已重新审查。11 项可由安全不变量和工程实践直接决定，已并入“当前设计”；这里只保留 2 个会实质改变用户风险体验的问题。请在“你的回答”后写选项字母，也可以直接改写。

#### Q1. 执行开始后只有一个独立文件失败，是否继续其余安全操作？

为什么问：两种选择都能做到安全，但体验不同。继续可以最大化长时间迁移的有效进展，却会扩大“部分已移动”的范围；立即停止更保守，却可能让十万项任务因一个坏文件反复中断。

简单例子：十万项移动到第 20,001 项时，一个文件发生临时读取错误，其他源、目标和 journal 都正常。

选项：

- A. 记录失败项，继续其他相互独立且仍然安全的操作；本次保持未完成，修复后只补齐遗漏项。
- B. 立即停止发起后续操作；已完成项保留，修复后再继续整批。
- C. 由每次执行前让用户选择 A 或 B。

推荐：A。原因：MediaSense 面向大规模集合，隔离单项失败并继续更符合长任务价值；journal、未完成状态和精确补齐保证它不会把失败隐藏掉。任何可能影响其他项的错误仍按全局风险立即暂停。

你的回答：A。按照推荐方案执行。

#### Q2. 完成后的短期 rewind，是否承诺用户主动恢复整次移动？

为什么问：此前 Plan 设计已经确认“很短的安全恢复窗口”，但用户主动 rewind 会再发动一次大规模文件变化。是否把它作为明确产品能力，会直接影响 Apply 的保留信息、目标占用规则和恢复责任。

简单例子：十万项全部移动并验证完成五分钟后，用户发现自己选错了目标硬盘，希望回到执行前的位置。

选项：

- A. 支持在短窗口内恢复整次已完成移动；恢复前重新检查两端状态和碰撞，条件不安全时拒绝。
- B. 短窗口只服务崩溃和执行失败恢复；成功完成后不提供用户主动 rewind。
- C. 支持用户任选分区或文件恢复。

推荐：A。原因：它兑现已经确认的短期安全网，同时把恢复限定在同一整次执行，避免 Apply 变成新的文件挑选和整理工具。C 会引入新的语义选择和长期复杂状态，不建议。

你的回答：A。按照推荐方案执行。

## 被拒绝选项

- 在 Apply 里重新讨论或实现 Plan 的组织效果预览。
- 在阶段流程尚未稳定前直接定义 Apply Schema、字段、Tool 数量或本地存储形态。
- 把 AI Album 没有正式记录某项信息直接解释为业务能力缺失，并据此增加永久实体。
- 已知执行前阻塞项时先移动其余文件。
- Apply 遇到现实冲突时自行改名、换目录或修改 Frozen Plan。
- 要求用户逐项确认能够由安全不变量和成熟工程实践决定的 Apply 行为。
- 自动清理源目录、盲目重放中断操作、取消即自动回滚、把用户接受部分结果记为全部成功。

## 未决问题

当前 Apply 流程、顶层责任模型、Run / Receipt 最小语义、Tool 责任边界、生命周期候选和历史能力处置均无用户决策阻塞项。人类可审阅的 Run/Receipt 参考实例与 `review` 契约候选已经形成；转为 active 前仍需把逐 Source Item 验证依据补入上游交付能力，并取得跨文件系统元数据保证的可执行证据。

## 质量门

- [x] 已完整读取 Foundation、信息架构、迁移基线及其模块。
- [x] 已读取相关上游契约、设计和 clarify 记录。
- [x] 已回看历史 PreCheck 与 Plan Codex session 的交互顺序和用户纠正。
- [x] 已确认正常 Apply 流程和执行前阻塞门槛。
- [x] 已用专业工程判断将原 13 个问题收敛为 11 项默认决定和 2 个高风险选择。
- [x] 第 1 轮只讨论流程、异常分支和完成条件。
- [x] 用户已回答第 1 轮剩余 2 个阻塞问题。
- [x] 已将回答整合进当前设计、已确认决策、被拒绝选项和未决问题。
- [x] 已确认流程层没有会迫使下游设计自行发明行为的剩余阻塞问题。
- [x] 已从现有 Frozen Plan 示例推导端到端 Apply 参考实例。
- [x] 已用独立责任与生命周期检验收敛为 Apply Run 和 Apply Receipt 两个顶层实体。
- [x] 已对入口解析、源漂移、损坏媒体、局部失败、全局风险、崩溃、Receipt 封存和 rewind 做流程压力测试。
- [x] 已识别可验证源绑定这一跨阶段契约缺口，并保持具体机制开放。
- [x] 已确定 Apply Run 与 Apply Receipt 的最小稳定语义，并排除 Preview、Authorization、Journal 等多余顶层实体。
- [x] 已确定预检、授权绑定与执行必须处于同一 Apply Run Tool 责任边界。
- [x] 已用十万项 Receipt 参考形态证明紧凑表达、异常展开和独立 Apply Read Tool 的必要性。
- [x] 已形成 Apply Run 最小操作与生命周期候选，并区分零效果阻塞与已有部分效果的待处理。
- [x] 已逐项分类 AI Album Apply 相关业务能力与质量属性。
- [x] 已形成可供 Human 审阅的 Run 与 Receipt 具体参考实例。
- [x] 已用参考实例证明 Run、Receipt 与读取接口的最小候选字段。
- [ ] 已在上游正式提供并验证跨阶段 Source Item 身份依据。
- [x] 已定义 Apply Run、Receipt 与 Read 的 `review` Schema/Tool 候选。
- [ ] 已用支持平台上的可执行证据验证跨文件系统逐字节校验与用户相关属性保留保证。
- [ ] 尚未激活 Apply Schema、Tool 或 Skill，也未实现运行时文件操作。
