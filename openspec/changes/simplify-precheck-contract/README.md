> Historical change packet. Current development authority is [`docs/spec/contract/`](../../../docs/spec/contract/index.md). Its pinned schemas/examples describe the earlier installed release and are not the current contract.

# PreCheck 接口重构实施包

2026-09-08 子工作线完成设计、实施及独立代码复验。首次验收发现的三个遗漏已修正，
再次复验通过；结论限于仓库实现与离线验证，不表示现场故障已经恢复。
`tasks.md` 第 7 节记录修正任务，实施方证据见 [verification.md](verification.md)，最新独立复验事实见下方交接。
这里的 OpenSpec Apply 是代码实施，不是运行 MediaSense Apply 整理媒体。
子工作线交接后，主线程按用户授权完成 **0.8.0 本机安装和旧 Dataset 清理**，
见 [安装与清理记录](installation-20260908.md)。下方交接保留子工作线完成时点事实；
实际数据的全新使用验收尚未开始。

## 给主 Agent 的事实交接（可直接复制）

```text
这是 MediaSense 子工作线的完成交接，事实截至 2026-09-08。
我们已完成 PreCheck 接口与 PreCheck → Plan 交接合约的设计、仓库实施和独立代码复验。
你仍负责主线程的整体判断；以下只提供已完成事实和边界，不替你决定下一步，也不新增操作授权。

项目：
/Users/chengyanru/repos/personal/mediasense

一、已完成什么

- 已与用户确认最小接口设计，落地 OpenSpec change：simplify-precheck-contract。
  保留 PreCheck run/read 两个 Tool、九个 action，采用顶层 action/dataset_ref 的扁平输入。
  运行进度统一到 progress；范围对账、工作进度和执行活性仍各自表达，不混用口径。
- Result 面向每个 Source Item 提供地点证据。地址与附近地点使用两个标准 Observation，
  不要求 Plan 理解 bundle、Provider、缓存或请求次数。费用和执行细节通过按需审计保留。
- 用户确认：缺 GPS、查询 no_result、已知且终结的地点服务失败，不单独阻断 Result 发布或 Plan，
  即使所有照片都缺地点也如此。有限重试归 Tool；确认未完成、效果 indeterminate 和非法 Result
  仍有独立阻断边界，不能用“允许缺地点”吞掉这些问题。
- 已处理本次发布故障对应的跨层合约缺口：fresh、复用/legacy 规范化与 Result 投影不再依赖
  非 available Observation 携带 value.component_outcomes。获取压缩本来已工作，并非本次修复对象。
- 同步了真实 Host、编排、Result 读写、Plan/Apply 消费者、正式规范、Skills 与打包资源。
  删除公开的 integrity 常量等冗余表达，但保留封存、摘要、引用、分页、成员绑定及文件安全校验。
  包内 29 项任务（原 25 项实施 + 4 项复核修正）已勾选；代码验收并非仅凭勾选结果。

二、遵循的开发理念

每个字段和实体都要有必要职责；复用已有模型，保持唯一权威归属和清楚的责任边界。
简化表达不等于削弱能力；之前有合理考量的功能不能无理由回退，删除字段不删除其校验保障。
相关原则来自：
/Users/chengyanru/.agents/skills/yanru-guidelines/SKILL.md

三、已验收什么

首次独立验收未通过，发现三个现有测试遗漏：
1. GPS/GPX 冲突时返回 conflicting，与 Schema 的 conflict 不一致。
2. Geo journal 崩溃重放的未知费用被变为 0，外发类别被变为空列表。
3. MCP 对不存在 Run 的 resume + proceed，把 run_not_found 误报为内部故障。

实施方修正后，子工作线再次独立检查代码并运行验证，结论为代码验收通过：
- 上述问题对应的 14 项新增回归全部通过；覆盖 GPX 优先与精确成员、未知与已知零值、
  当前与历史请求、重放不新增效果、真实 stdio MCP 错误一致性及真实程序异常继续暴露。
- 默认离线全套：693 passed、16 deselected；上述 14 项包含在全套中，不是额外累加。
- Ruff、OpenSpec strict、verify_packet.py、git diff --check 全部通过。
- 新 wheel 的 103 个源码/资源文件与当前工作树逐字节一致；两轮 wheel 的产品代码差异
  仅涉及此次修正的 5 个源码文件，没有新增模型或放宽 Schema。
- 复验期间工作树文件内容未变化，未发现新增阻断问题。

四、尚未做什么

这不是现场恢复、安装发布或真实 Provider 的验收。没有升级本机安装版、重跑现场 Run、
读取或修改现场运行数据库、操作用户媒体，或发起真实 Provider/计费请求。
没有 commit、push 或 archive；交接的是当前工作树中的实现。
(0,0) 元数据策略、视频局部失败，以及现场 Run 如何恢复，均未在本子任务中处理。
原现场 failed 状态不能因为代码验收通过就被视为已恢复。

五、事实与合约入口

实施包及本交接：
/Users/chengyanru/repos/personal/mediasense/openspec/changes/simplify-precheck-contract/README.md
已确认工程决策：
/Users/chengyanru/repos/personal/mediasense/openspec/changes/simplify-precheck-contract/design.md
任务记录：
/Users/chengyanru/repos/personal/mediasense/openspec/changes/simplify-precheck-contract/tasks.md
实施方验证记录（其中“等待用户复验”描述的是实施方交付时点）：
/Users/chengyanru/repos/personal/mediasense/openspec/changes/simplify-precheck-contract/verification.md
用户讨论与设计理由：
/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260907-0247-precheck-plan-handoff/index.md
/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260907-0247-precheck-plan-handoff/reasoning.md

以上是子工作线的完成范围与证据。请结合你掌握的主线程目标、其他工作和用户授权，
自行判断下一步是否需要行动、如何行动或还需确认什么。
README 后面的原 Apply Agent 启动指令是历史材料，不是本次给你的待执行任务。
```

## 阅读顺序

1. [proposal.md](proposal.md)：变更目的和范围。
2. [design.md](design.md)：已收口的工程决策，包括 MCP 方案 A、进度、Geo 与旧数据。
3. [specs/](specs/)：需求与验收场景；每项对应现有能力，新增的 read 规范只补原来缺少的规范归属，不新增 Tool。
4. [contracts/](contracts/)：完整请求/返回 Schema 与合成 transcript，是本包的机器形状。
5. [tasks.md](tasks.md)：按依赖顺序实施，完成后才勾选。

中文讨论稿在 [接口草图](../../../docs/spec/spec-260907-0247-precheck-plan-handoff/index.md)，
早期示例是业务主干，不是完整 MCP 调用。用户已选方案 A；本包对 action、Dataset 路由、
Geo 组件及分页细节的精化优先于讨论稿中的省略或临时旧格式。active 合约及其打包副本已原位同步，
全部仓库消费者使用同一公开合约；本机安装版未升级。

本包机器形状另含 `responseSchemas[action]`，用于按请求操作校验对应返回；这是schema定义的
索引，不是新增Tool或运行期注册表。不能拿所有返回的并集放行不完整status。

## 原 Apply Agent 启动指令（历史）

以下保留最初交给实施 Agent 的启动提示词，用于追溯当时的范围与约束；本轮实施已完成，
不要把它当作新的待执行任务。具体合约仍以本包及已同步的正式规范为准。

```text
请在 /Users/chengyanru/repos/personal/mediasense 实施 OpenSpec change：
simplify-precheck-contract。

这里的 OpenSpec Apply 指按已确认设计修改仓库代码，不是执行 MediaSense Apply 整理媒体。
本包已完成设计准备，但这不等于代码已经实现。先核对当前任务状态，再完成剩余任务。

一、先读上下文

遵守 /Users/chengyanru/repos/personal/mediasense/AGENTS.md 及其引用的指引。
加载并遵守以下 Skill：
/Users/chengyanru/.agents/skills/yanru-guidelines/SKILL.md

阅读项目基础设计：
/Users/chengyanru/repos/personal/mediasense/docs/design/design-260823-1918-mediasense-foundation.md
/Users/chengyanru/repos/personal/mediasense/docs/design/design-260830-1527-reusable-capability-architecture.md

阅读用户讨论稿，理解简化的动机和取舍：
/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260907-0247-precheck-plan-handoff/index.md
/Users/chengyanru/repos/personal/mediasense/docs/spec/spec-260907-0247-precheck-plan-handoff/reasoning.md

实施包入口：
/Users/chengyanru/repos/personal/mediasense/openspec/changes/simplify-precheck-contract/README.md
以该目录为基准，依次完整阅读 proposal.md、design.md、specs/ 下全部规范、
contracts/ 下两个 Tool Schema 和 examples.json、tasks.md。
不要只读本提示词或示例就开工。包内已确认的工程精化优先于早期讨论稿的省略和临时格式；
仓库 active 规范尚待同步，不要把待替换的旧实现误认成新需求。

二、开发理念

1. 每个字段、包装层、实体都必须有独立且必要的职责。
   能删去的重复表达就删去，不为实现方便新增 Tool、服务、注册表或兼容框架。
2. 分类要有一致的逻辑。Source Item 的覆盖、Work 的处理进度、执行是否存活是不同问题；
   不混用计数，不把 Provider、bundle、缓存和请求数泄露成 Plan 必须理解的概念。
3. 简化表达不等于削弱能力。删除公开字段，不能连带删除完整性、授权、分页、引用和安全校验。
   之前有理由保留的功能不能悄悄回退；任何取舍都必须有具体依据和等价保障。
4. 产品语义已经确认，不需要重新向我逐项征求意见。
   普通工程判断自行推进；若发现关键机制冲突、新的业务选择或实质退化，给出证据后停下讨论。

三、不能误解的已确认决定

- MCP 已选方案 A：保留 run/read 两个 Tool，以顶层 action 区分九个操作；
  输入是扁平结构，显式携带 dataset_ref，删除这两个 Tool 的 request 包装和 operation 别名。
  不拆成九个 Tool，不推断 latest Dataset，不顺手改变其他 Tool 的传输格式。
  返回必须按请求 action 校验，不能只用所有返回的并集放行残缺 status。
- progress 收拢为平面结构；处理数表示已终结的逻辑工作，不是成功数或实际请求数。
  未知进度诚实表示未知；status 只观察，不接管执行。接受 pause/cancel 不代表已经完成暂停/取消。
- 删除公开的常量 integrity 表达，保留 Result seal、hash、引用与消费者校验。
  覆盖程度与能否进入 Plan 仍是两个独立问题；不能把两者一起删掉。
- 照片没有 GPS、Geo 双组件 no_result、已终结的已知服务失败，都不因缺少地点而阻断 Plan；
  即使所有照片没有地点也是如此。有限重试由 Tool 在已获授权内完成，不让 Agent 无限补查。
  no_result、failed、not_requested、indeterminate 必须保留区别；这不允许吞掉程序错误或非法 Result。
- Geo 使用既有 Observation 模型中的 address_candidate 与 nearby_place_candidates。
  available 才能有可用 value，非 available 不能带 value。fresh、复用及合法历史投影走统一规范化路径。
  历史证据不足不能编造 no_result，也不能自动发请求；不可变旧 Result 的原文、引用和 hash 不改写。
  重试上限、超时、未知发送结果、授权及计费上界严格按 design.md D6 实现，不另加外层重试。
- 读取的分页、Source Set 成员绑定、Source Item/Evidence 两种 prepared_targets，以及 Plan/Apply 安全检查
  都必须保留。去掉冗余输出不代表去掉这些机制；详情按包内规范和验收场景执行。

事故背景只需抓住这一点：Geo 获取压缩已工作，本次发布失败是旧缓存迁移形成 missing + value，
且 fresh 路径也存在同类缺陷。修复必须覆盖生产、复用、投影、seal 和消费者，不能只删非法 value。
(0,0) 的元数据过滤、视频解码问题是独立议题，不在本次范围。

四、实施范围与边界

按 tasks.md 的依赖顺序推进，完成并验证后才勾选；不要以包内 Schema 校验替代运行行为验证。
可修改本变更必需的仓库代码、测试、正式规范、打包资源和 Skill 文档。
同步真实 MCP/CLI Host、PreCheck 编排、共享 Geo 与日志、Result 读写/投影/封存、
source_sets 与 Plan/Apply 消费者，以及机读 Schema、mock 和 _resources 副本，避免两套公开合约。

先检查工作树，保留已有讨论文档和其他变更，不重置、不覆盖无关修改。
测试使用隔离的合成数据和临时 workspace；不调用真实 Provider、不产生真实计费，
不读取或修改现场运行数据库、不操作用户媒体、不重跑现场 Dataset、不升级本机安装版。
不要自行 commit、push 或 archive 本变更。

五、验收和汇报

按 tasks.md 完成针对性测试、默认离线测试、Ruff、真实 stdio MCP/生产组合测试、
合成数据的 PreCheck → Plan → Apply preparation 验证及隔离 wheel/package smoke。
最后一条只到准备阶段，不执行真实媒体整理；不启用真实 fixture/scale 或外部服务测试。
特别覆盖 fresh/legacy 无结果、最终服务失败、全批缺地点仍可进入 Plan、非法 Result 拒绝、
授权和重试上界、恢复与竞争、分页和成员摘要篡改等行为。

同时运行本包 README 中的检查命令。OpenSpec 准备文档齐全不等于实施或验收完成。
不要通过删除断言、放宽约束或只修改预期来掩盖回退。无法运行的验证明确列出原因。

现在开始实施。先用简短中文说明你理解的目标和首批任务，然后推进代码与测试。
最终用中文汇报：完成的任务、实际验证证据、未完成项或风险，以及未触碰的现场边界。
```

## 检查命令

```sh
rtk proxy openspec validate simplify-precheck-contract --strict --no-interactive
rtk proxy .venv/bin/python openspec/changes/simplify-precheck-contract/verify_packet.py
rtk proxy openspec status --change simplify-precheck-contract --json
rtk proxy openspec instructions apply --change simplify-precheck-contract --json
```

`status.isComplete` 只表示准备文档齐全。Apply 必须是 ready 且有未完成任务，不能因为文件齐全
就声称实现通过。包内校验只检查规范/形状/合成数据，不代替实施后的行为测试。

准备阶段已通过严格 OpenSpec 校验、2份schema的26个正常/13个拒绝用例及成员摘要重算、
校验脚本ruff和diff检查。当时 25 项实现任务均未勾选。该段仅记录准备阶段；后续实施与运行验收见 verification.md。
