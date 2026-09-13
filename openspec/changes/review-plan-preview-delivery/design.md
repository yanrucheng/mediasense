> 2026-09-13 实施状态：用户已授权按本定案设计开发。当前接口权威已对齐至 [Plan Work 合约](../../../docs/spec/contract/plan-work/index.md)，实际验证与未验范围见 [实施记录](acceptance.md)。下文“本轮仅 Spec”描述保留为设计阶段历史范围，不限制已授权实施。

> 本文件是工程支撑稿，主方案及具体例子见[README](README.md)。这些工程选择由Agent提出，不要求用户选择字段名、端口或框架，也不构成现行实现。

## Context

本设计落实[proposal](proposal.md)及本包三个[能力Spec](specs/plan-working-state/spec.md)。公开接口的当前权威仍为`docs/spec/contract/`；本包提供下一版的审阅材料，不覆盖现行承诺。用户已明确持续页面目的，并在具体例子后选定严格revision确认；无需再询问该规则。

现有Work保存自由文本、偏好和可选完整Candidate；`snapshot_for_preview`要求候选可seal；renderer没有普通Tool交付入口，页面没有真正的成员续读。现有SQLite事务、Source Set解析、Frozen Plan发布和准备证据读取可以复用。

## Goals / Non-Goals

目标是建立“讨论、保存、查看、反馈”的正常循环：无目录也有页面，部分目录如实显示，完整候选才请求整案接受，工具保证所审阅版本与冻结版本一致。所有可见组织数据能回到同一份已保存内容及绑定Result。

本轮交付Spec、接口样例、项目设计和验收依据。实现、安装切换、真实业务Plan重做、远程分享、全历史草案归档、多方案编辑器和Apply均不属于本轮。本包不量化尚未测量的token节约或较弱模型成功率。

## Decisions

### 1. Work只保存一份当前组织

更新输入使用`organization_content`：`null`清空；省略保留；对象整体替换。对象复用现有`result_ref/scope/logical_root/groups/other_outcomes/decision_notes`，增加`kind: draft | candidate`。不保留旧`candidate_content`别名，不同时保存一份草案和一份候选。

`draft`的字段结构完整，但允许范围尚未被完全安排。它仍须保证Result绑定、非空scope、已写Source Set完全可解析、无越界或重复去向、目录和命名安全、说明引用有效。空分组列表与空其他处置列表可表示尚未安排任何项；没有明确成员的目录构想留在工作说明，不进入树。草案不取得可冻结identity。

`candidate`必须通过现有完整分区和Frozen Plan校验。100%已安排的草案不会自动晋升；Agent显式提交完整候选才产生可冻结身份。这保留语义充分性由Agent判断、机械完整性由Tool证明的分工。

Work的`open/closed`生命周期不承担草案、候选、显示失败等含义。已保存组织种类、范围统计、页面交付状态分别表达。`scope_summary`由精确解析计算，包含scope、归组、其他处置和未安排数量；它是可再生统计，不增加逐项权威账本。Plan scope与Result覆盖边界同时可见，缩小scope不能成为隐式补齐。

`inspect.content`返回所存组织，而不把草案伪装为Frozen Plan。完整与分页响应使用同一对象/字段含义；分页的`mode: complete`仅表示本次完整返回该集合，组织是否为候选由`kind`说明。`inspect`同时返回既有预留Plan引用的明确字段`reserved_plan_ref`，便于核对候选物化；Work打开时它只是预留，关闭后同一引用应与已发布Plan一致，引用值本身不证明发布成功。

Candidate identity仍由现有编码产生：从组织内容去掉`kind`，加入固定`contract`和该Work预留`plan_ref`，得到原有`sealed_content`并计算摘要。工作说明、偏好、页面和草案标记不进入Frozen Plan。关闭Work的组织投影与已发布artifact一致，展示实际seal记录。

`validation`继续表示冻结条件，而非一次保存是否成功。无组织内容或草案的读取是成功读取，即使validation列出candidate_missing或draft_not_candidate；页面按正常讨论状态展示，不能把它们当作数据损坏。顶层结构/旧字段/必需参数错误为invalid_request；提供的组织对象不符合结构、引用或组织规则为organization_invalid。传输层可以在Tool分派前拒绝不符合输入schema的消息；多重错误不规定一个新的全局优先顺序。

选择这一方案是因为同一份规划应可逐步成形。仅显示自由文本不能交付准确成员；伪造其余项的处置会谎报完整；再存一份页面组织会分裂权威。局部方案比较仍可在说明中讨论，不为尚无明确需求的多树编辑增加持久对象。

### 2. 明确业务回执和本次页面观察

create/update/seal先完成其原有原子状态转换，形成可重放的业务回执，再进行页面入口交付。成功输出保留原有操作绑定字段，增加`view`；inspect将`view`作为可选section并默认返回。

业务回执与页面观察的时间不同。相同request_id/请求仍只能产生一次状态转换；回放时原业务字段及Frozen Plan逐字不变，`view`是本次尝试的交付观察，允许变化。这是对现行“整个结果相同”的明确收窄，须与新合约一起审阅；不影响幂等副作用、request_id冲突或revision保护。

`view`包含请求版本的Work/Result绑定、`revision`、`observed_at`、`current_revision`、`current_uri`、`revision_uri`、`status`及`problems`。状态仅有：

| status | 含义 |
| --- | --- |
| ready | 该版本的核心规划及浏览入口可交付 |
| degraded | 核心规划可交付，但有明确列出的局部证据限制 |
| unavailable | 正常运行条件下暂不能交付核心页面或宿主入口，保留具体原因 |
| superseded | 已知该请求版本不是当前版本；不能以新内容冒充它 |

`current_uri`指向该Work的当前入口，`revision_uri`固定所请求版本；无法交付时相应URI为null。重启后传输地址可以重取，Work引用和版本含义不变。`current_revision`是交付检查时实际观察值，不可用时为null；revision是opaque equality token，不能按字符串大小判断新旧。

例：r2保存成功后回复丢失，期间Work已到r3。重复r2的request_id仍返回原业务回执r2，附`view.status=superseded/current_revision=r3`；不会把r2重写到当前状态，也不会把r3页面冒充r2。

预期的宿主启动/读取/图片条件失败通过view报告，已保存规划不回滚。renderer内部的意外异常必须向外传播；最外层运行时报告`operation_failed`和已经确定的`committed_receipt`（若有），保留诊断，不将程序错误伪装为正常unavailable、queued或running。故障后的inspect可只选overview/notes/content而不选view，以读取权威保存结果；不得因坏renderer把Work读取全部堵死。

### 3. 首版工程建议：本机只读页面宿主

首版工程选择为现有Runtime的本机只读页面适配器：HTML框架和有界读取入口由产品提供；每次打开当前入口读取当前Work并固定显示版本，后台检测变化只提示新版，用户刷新后切换。最终接受使用工具返回的精确版本入口。页面没有写入规划、确认或Apply的HTTP接口。

宿主是实际提供跨Tool调用浏览的运行进程，不是新业务实体。优先一份安装/用户范围的宿主服务多个已显式绑定的Dataset，按需打开读取，避免每个Work生成一套服务。数据集路由是运行时句柄，可丢弃重建，不成为Dataset或Plan权威注册表。不扫描用户目录自动注册其他集合。

进程联络信息归属安装所使用的用户级运行时数据目录，只记录连接、实例和构建信息，不存规划内容；Dataset对应的视图与成员索引仍放在它自己的Plan管理范围。路由以明确Dataset绑定和Work共同定位，不能只按一个来自URL的Work字符串猜测存放目录。

Runtime负责启动、健康检查、复用、真实退出和重启后的重新绑定；正常CLI/MCP操作自动完成接入，不要求Agent启动手工服务器或用户管理端口。进程在单次CLI/Tool调用结束后继续提供入口，安装升级或显式停止后由下一次普通接入恢复。不得增加系统自动登录服务作为未声明的安装副作用。复用前核对用户、所用安装构建与实际宿主身份；不能仅凭相同版本号复用旧代码进程。

读取仅监听本机loopback，限定被交付的Dataset/Work及绑定Result，使用运行时访问句柄限制页面和资源。句柄只有读取权限，不是Human确认。宿主校验访问边界，拒绝任意本机路径、跨Dataset资源和跨站读取；不把整个Dataset目录作为静态文件根开放。文本转义、资源类型和来源核对属于确定性展示实现。

选择此首版机制是为了直接读到当前revision、支持真实分页并表达过期和失败，不依赖Agent重建全量HTML。静态页面/分片等方案未来只要兑现同样Spec即可替换；HTTP、端口及框架不成为Plan业务语义。静态导出不是本轮必需交付，也不能代替持续入口。

### 4. 归属与数据流

```text
Agent/Human讨论
    -> Plan Work保存（同一份当前组织、说明、偏好）
    -> Runtime交付Work页面入口
    -> 页面读取一个确定版本的Plan投影
         -> 既有Source Set解析与PreCheck Read
         -> 原有准备Evidence及限定
    -> Human聊天接受该版 -> Plan Work seal -> 原有Frozen Plan
```

Plan模块拥有视图投影和局部缓存；Runtime拥有入口、进程、连接和只读资源传输；PreCheck Read拥有Result完整性与Evidence读取；现有publisher拥有Frozen Plan。页面不读取PreCheck私有数据库，也不通过浏览器直接读取Plan SQLite。

派生缓存位于Dataset工作区的Plan管理范围，版本/查询/绑定均进入缓存身份。源媒体、fixture目录和最终组织输出树不作为页面写入位置。当前状态可由Work/Result重建，冻结内容由Frozen Plan重建。页面业务值全由投影生成，展示内部的JSON或索引不成为Agent另行维护的数据。

投影缓存必须覆盖`work_ref/revision/state`、冻结identity（关闭时）、Result身份、展示构建及Evidence依赖。seal关闭精确revision而不创建另一个组织revision，因此不能只以revision缓存open/closed显示。缺失图片的临时失败可重新核验，不永久缓存为不存在。

### 5. 读取、分页与发布竞争

先捕获一个确定Work快照，之后所有目录、计数、说明、成员和Evidence适用范围都从这个快照解释。浏览续页绑定Work/revision、集合或目录、查询条件和位置。当前版本改变时，过期读取明确拒绝并给出当前入口；不把新版条目拼到旧列表中。实现可复用现有游标及Source Set能力，不能仅在前端截取前100个引用。

初始读数和成员索引复用校验得到的精确集合，分批读取文件信息及准备Evidence；不为了页面解码全体原媒体。显示可辨认的源文件名、必要路径/类型、目标命名及条件，源引用放详情。`decision_notes`展示自然说明、适用数量和可展开成员、实际可读Evidence；全局说明不需在每个组复制成另一份记录。

页面读取有界并有真实结束标记。列表查询条件固定后，连续续读必须无漏项/重复；字节预算和单项Evidence错误不能伪装成分页结束。具体页大小、线程/任务预算及索引参数属于实现配置，在大集合验证中给出实际数字。

首版目录顺序采用已保存groups数组中的首次出现顺序，派生父层保持该顺序；不重新解释数字前缀或用字母排序改动组织意图。其他处置和决定说明保留保存顺序。同一目录的展开成员采用明确、稳定的显示排序并以source_item_ref消除重名歧义，排序条件进入查询绑定；这不改变Source Set的集合含义。

渲染或索引任务发布结果前再次核对绑定，较旧完成任务不能覆盖当前入口。宿主可以返回“本页rN、当前已为rM”的过期结果，不按opaque token排序推断。已加载页面保持所显示版本，不能静默变更用户正在接受的内容。

不承诺历史草案永久读取或撤回恢复。旧入口明确过期；如仍有派生快照只能标记为历史。缓存缺失时不得改用当前内容冒充旧版。已冻结Work及其artifact在现有保留边界内可读，后续修改另建Work，不把旧入口改指其他Work。

### 6. 确认与异常

可信客户端上下文要求`principal_ref/work_ref/reviewed_revision/confirmed_content_identity/confirmed_at`。普通Work请求不能声明这些权限。seal同时核对请求revision、当前revision、上下文reviewed_revision和identity；上下文绑定不符使用`confirmation_binding_mismatch`，请求revision不再当前仍用`revision_conflict`，内容身份不同仍用原有错误。

任何成功的新update都产生新revision，包括只写说明、偏好和同值写入；旧上下文不再有效。撤下后恢复同内容即使得到同identity，也不能恢复旧确认。幂等重放、翻页、重新渲染、修复缓存不生成revision。用户在聊天中撤回时，Agent停止seal并及时保存撤回/草案状态，不能指望Tool自动读懂聊天。确认记录由seal保存，不在接受后再写“已确认”备忘。

图片不可读只作明确占位并保留真正来源，不冒充其他源、不自动补采模型/地图、不改分组。Result整体不可信或成员不可解析则页面不能声称完整校验，seal依原边界拒绝。重要限制由Agent和Human判断是否需要改变最终说明或继续调查；不存在“所有图片都加载完才允许确认”的统一规则。

工作说明与偏好是当前讨论上下文，页面明确它们不进入Frozen Plan；需要随最终决定保留的理由由Agent写入decision_notes。种类、来源、限定和适用范围由已有数据表达，不引入具体应用类别字段。页面存在、100%安排、结构校验通过都不产生Human确认。

## Risks / Trade-offs

- 常驻读取进程增加实际生命周期 → 限一份安装/用户宿主，按需读取、限定资源、提供状态/停止/重接并在安装验证中检查真实进程，不增加后台采集。
- 保存成功而页面交付失败 → 原业务回执可重放，view单独报告；权威inspect可跳过view，意外错误保留committed_receipt。
- 严格revision确认可能增加一次重复接受 → 用户已选择此取舍；接受后直接seal，展示操作不造revision。
- 大集合页面可能重复解析大量集合 → 复用精确集合与版本缓存，查询有界；不把全量图像和HTML回传模型。
- 自由文本可能含敏感路径或可执行内容 → 原样作为文字显示，路径不自动读取，不执行记录中的HTML/脚本。

## Migration Plan

实施后先在隔离副本验证新格式，再考虑日常切换。公共接口按既定Zero BC替换，不提供旧字段别名。持久数据转换与公共兼容接口分开：旧非空Candidate可无损转换为`kind=candidate`，旧空Candidate为无组织内容；Work/Result/预留Plan引用、说明、偏好、已冻结artifact及历史回执不丢失。

升级前停止写入并按安装runbook做一致备份，先完成旧Host正在恢复的seal事务；不得在新Host中猜测未完成的旧发布。原数据库/格式保留可回退副本，新写入使用明确的新格式并拒绝旧Host写入。旧request_id不能被新语义重新利用；旧接口请求在新入口明确拒绝，历史回执保留用于核对，不以兼容路由重演。新合约只承诺新接口所接受请求的重放。

迁移不为旧确认补造reviewed_revision。打开的旧Work在新的严格边界下需审阅当前版后确认；已经冻结的历史artifact保持原记录，不冒称当时遵守了新规则。回退在确认没有新写入时恢复旧快照；已有新写入时先保留新状态，再采用经过验证的恢复方案，不能用旧备份覆盖它。

合约、发布资源、Skill、Runtime和读取宿主必须在同一交付中对齐；按原安装runbook检查具体构建、Python/依赖、项目Skill及实际新会话。这里只设计步骤，不执行迁移或安装。

## Open Questions

目前没有必须由用户再选择才能完成本版Spec的产品问题。用户已选择严格确认；部分草案、入口及失败边界按本稿收敛。接口文案、页面导航可理解性和实际规模表现仍需实现后按验收场景验证，不能把本轮静态Spec检查算作运行或视觉验收。具体实现细节可在不改变Spec承诺的范围内调整。
