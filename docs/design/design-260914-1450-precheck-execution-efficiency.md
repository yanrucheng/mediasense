---
id: "design-260914-1450-precheck-execution-efficiency"
title: "PreCheck 工具执行效率：有限工程优化与分阶段验证设计"
type: design
status: review
created: 2026-09-14
updated: 2026-09-14
timezone: "Asia/Shanghai"
parent: "design-260823-1918-mediasense-foundation"
depends-on:
  - "model-260913-1408-precheck-basics"
  - "design-260823-1918-mediasense-foundation"
  - "design-260830-1527-reusable-capability-architecture"
  - "precheck-run"
  - "precheck-read"
superseded-by: ""
---

# 目的与设计状态

在相同来源、准备义务、输出内容和安全保证下，降低普通 Run、有效暖复用和局部准备的内部执行成本。缓存归工具所有，由工具判断有效性；本设计不改变这个职责。

2026-09-14 用户授权本轮只做具体工程设计，后续由其他 Agent 实施。用户不要求预先保证提速比例：完成这里限定的成熟工程优化后，统一实测收益；若不理想，如实报告并停止，不为性能数字追加过度设计。本页是实施交接设计，`review` 不表示已获实现验收。没有产品代码或新测试由本设计任务编写。

[专项调查](../../eval/sessions/260914-1359-tool-execution-efficiency/report.md)保存实测和归因边界。本页拥有后续工程范围、内部责任和验证顺序；[Run](../spec/contract/precheck-run/index.md)、[Read](../spec/contract/precheck-read/index.md)继续拥有公开承诺。调查报告此前的25%收益、40%提交减少建议不再作为验收门槛。

## 开始设计及实施的前提

**没有需要用户进一步决定的设计阻塞点。** 现有证据已足够选取工程方法；精确OS等待分解、真实大媒体收益和跨设备吞吐不是设计前置条件。

实施阶段必须先固定源码基线：当前普通Run补修有并行未提交改动，不得覆盖、重置或误计为本次性能成果。优先使用后续确定的补修完成快照；若尚无合并提交，记录commit加逐文件摘要与diff即可，不要求为本任务清理工作树。针对基线差异重新定位函数即可，不改变现行契约。大规模测量等待独占测量窗口，不影响设计或小型功能验证。

唯一需要重新讨论范围的情形：实施发现某个方法必须改变公开行为、降低验证强度、新增持久权威/服务，或先重写所有producer才能成立。届时记录具体不相容点并停止该方法，不能自行扩大架构。正常实现细节、批大小和私有函数命名不需要重新决策。

## 固定范围与不做事项

本期按顺序实施以下四类优化，并完成一次最终验收阶段：

1. 补齐现有线程内连接复用，保留逐项控制读取与事务语义。
2. 在现有SourceValidity、Work、Artifact Store内提供有界批量操作，共用单项校验和状态转换规则。
3. 接入静态图准备、Result组装和封存，减少重复读取/对象构造及逐条提交；保留真实来源和最终发布核验边界。
4. 复用Observation子验证器，消除已确认的不必要构造；保持完整数据逐项验证。

不把调查中的所有候选都列入实施：本期不改SQLite journal/synchronous，不做跨阶段hash缓存，不新增持久进度聚合，不改默认status频率，不替换调度器、数据库、ORM或依赖库，不建立通用批处理框架、缓存服务、注册表、消息队列或新的批次实体。不对metadata/video/model/Geo各生产流程作全面批量重写；共享底层变更需回归这些调用者。

新私有方法、局部列表和映射可按需要使用，它们没有独立身份或生命周期。依赖身份不包含连接、批量大小、线程等纯执行选择；这些方法改变不使有效Work失效。Profile参数、源修订、实际成员及输入等影响结果的依赖仍须绑定，不能把局部准备要求也当作无语义的“Run策略”排除。

## Backward Compatibility Policy

保持当前公开API、返回内容、错误含义、准备义务与旧Result留存。仓库零公开API BC政策不授权本次改变已确认语义。本期预期无需schema迁移、新表、新公共字段或配置项；如实现提出这些变化，须先证明现有结构无法承载，不把它当作性能开发的自然附带工作。

原Result封存字节不改写，新Result仍独立可读；Work历史、attempt和材料pin不删除。源只读、关闭能力不交付旧缓存、默认无远端效果、幂等发布和状态真实性保持。

## 工程依据与模块责任

批量事务、连接和预编译语句复用是成熟做法，参见[SQLite事务说明](https://www.sqlite.org/faq.html#q19)、[Python sqlite3连接](https://docs.python.org/3.11/library/sqlite3.html#sqlite3.connect)。[SQLite的小查询说明](https://www.sqlite.org/np1queryprob.html)也提醒不能仅按查询数量认定性能问题；本设计针对已观测的重复写事务、连接打开和对象构造。

调查中512项暖Run零解码，但有约12N提交；图像准备、组装、封存分别存在来源证明和产物核验写回。项目已有 `_sqlite_scope.connection_scope`、`succeed_work_many`、多个`produce_many`和独立事务测试。本期沿这些已有方法扩展，不建立另一套执行基础设施。

| 现有责任位置 | 继续拥有的判断 | 本期内部变化 |
| --- | --- | --- |
| `_sqlite_scope.py`、`_run_sqlite.py` | 连接使用、线程隔离、事务清理、Run持久状态 | 统一使用已有连接scope，保持超时等原选项 |
| `source_validity.py` | 来源revision、reuse_domain、证明及失效 | 批量获取行、逐项证明、短事务记录 |
| `_work_sqlite.py` | Work语义身份、依赖、附属、状态、碰撞 | 批量ensure/get；单项和批量共用规则 |
| `_artifact_sqlite.py` | 产物完整性、Work关联与失效传播 | 批读关联、批量核验写回；在核验及资格复核后附属可复用的产物Work，不接收调用方宣称有效 |
| `rendition.py`、`_orchestrator.py` | 准备需求、producer组合、资源与控制 | 有界批量准备命中检查，缺口沿原执行和发布路径 |
| `result.py`、`_result_assembly.py`、`_result_evidence_projection.py`、`_result_sqlite.py` | 完整Result构造、引用/资格校验、pin与发布 | 分块取数、复用同次投影、批量核验写回 |
| `_result_sqlite.py`、既有contract validator入口 | Observation规则验证 | 复用不可变子验证器定义，不缓存数据验证结论 |

这是现有多个模块上的局部中型工程工作，不是单个独立插件，也不要求全盘重构。Artifact损坏到Work失效、Work附属到进度范围变更的联系是必要耦合。ArtifactStore已有“材料发布与Work完成”的短事务，本期的“核验后复用附属”沿用这个所属边界，调用Work的共用私有事务内规则；不新建全流程事务管理器。编排层不直接写各Store私表，不持有跨Store全流程事务，不给底层增加“局部Run免检”等分支。无需借本期整理现有类继承或文件布局。

## 1. 连接复用设计

让Run SQLite适配使用现有`connect/connection_scope`机制，scope安置在有明确结束点的协调调用及worker批次外围。连接只在同线程同数据库内复用；心跳、控制调用和worker各自使用连接，不设置跨线程共享来绕过限制。

当前Run Store有独立`sqlite_timeout`，通用connect固定timeout。接入必须保留原配置：可给已有helper增加必要的私有连接参数，scope不得混用不同连接语义。不要顺手新增连接池服务或改变等待策略。

scope只复用空闲连接，不代表事务。已有事务仍由Store开启、提交或回滚；借出的连接不能被嵌套调用借走并提交。scope异常退出清理未提交事务并关闭连接。不能在整个Run期间持有读快照或写锁。每次`current_state`仍查持久状态，复用连接不缓存state值；原任务前控制检查继续执行。

尤其`SQLiteRunStore.observe`现在通过`BEGIN`读一致状态，原先靠连接关闭结束读事务。改为复用后必须在该次观察结束时显式结束事务，保留同次status的一致快照，也让下次status看到新提交。SQL游标/未消费生成器不得逃逸连接借用范围；先在受限大小内取完并关闭游标，再等待future、调用可能写库的Store或处理文件，避免同线程读锁阻塞自己的嵌套写入。

## 2. Store内批量操作设计

### 共用规则与输入边界

下列方法名是内部设计意图，实施者可以按现有风格命名：`prove_many`、`ensure_work_many`、`get_work_many`、`artifacts_for_works`、`verify_many`，以及ArtifactStore内部“确保产物Work并完成复用附属”的组合操作。只有接入的真实消费者需要时才添加方法，不先生成全部通用CRUD API。

- 单项入口委托同一规则实现，或两种入口共用少量私有校验/转换函数。禁止复制一套永远独立的“快速验证”。原单项错误、输出和提交完成语义保留。
- 批量返回保留输入关联和确定顺序，不依赖SQL返回顺序；未知ID、缺行、重复ID按方法语义明确处理，不让JOIN静默吞项。`ensure_work_many`对语义等价请求沿用同一Work，仍检查descriptor碰撞和retry policy。
- 按实际SQLite参数上限分块；不全量加载Dataset历史。初始内部批量建议32个来源，限制在128个来源以内；这是可调整实现默认值，不进入公共配置/身份。按字节预算继续收缩含大载荷批次，未处理输入保持惰性。
- 新增批写事务不包含文件读取、hash、解码和模型执行；读取形成的观察只在明确校验后提交，事务内重新读取可能变化的资格和版本。既有最终pin事务仍执行原材料核验，不受这条新增批写规则影响；不能把它移出事务后直接注册。
- 每个已返回成功/复用项必须有已提交依据。未提交项不可提前计入processed或向上返回成功。Source证明、Artifact/Work复用附属和Result注册保留各自短事务，不把整个准备过程变成一个原子操作。
- 多语句批读同一组Work、依赖和关联时使用短的一致读快照，取完本块即释放。分块间不承诺全Dataset长期快照，真正执行和提交仍重新验证资格；不能一边持有整次组装的读事务，一边调用Artifact核验写回。

### 来源证明

批量读取对应run_items和working run字段，仍逐来源核对允许状态、revision、attachment/reuse_domain及现有stat检查。不能把一份内容相同的文件证明推广到另一path occurrence。

写事务内重新检查每个观察所绑定的Run/来源revision/reuse_domain及条件；批量等待拉长了观察到提交的间隔，还须按现有profile重新比对该路径的stat，防止源在批内较早检查后已变而仅数据库未变。发生变化沿现有错误/失效规则处理。upsert证明及由证明改变触发的依赖失效保持同事务。保留每项真实observed_at，不制造整批完成时间作为每项观察时间。

`prove`目前使用accounting保存的指纹加当前stat，不应把函数名误当成完整重新hash。本期既不降低也不扩大其保证；初始和发布前snapshot的字节指纹检查仍在原边界执行。

### Work确保与读取

预先构造逐项spec和semantic key；批量获取Run item、source proof、上游Work及现有semantic key记录。事务内重新验证依赖、descriptor、retry policy和状态，创建缺失Work并附属到Run。不同spec中同一路径/Work行可共享该事务内读取结果；不得复用到后续事务。批内同semantic key只创建一次，按输入映射结果；重复spec仍逐个核对descriptor与retry policy，不能以去重掩盖冲突。缓存的新建/更新行须同步反映本事务内写入，不能第二次重复INSERT。

**产物Work有一个必须区分的步骤：只读候选查找不等于附属。** 当前status会直接把已附属且`succeeded`的Work计为复用，因此新暖路径不能先调用通用`ensure_work_many`把整批历史成功Work附属，再慢慢核验Artifact。Source证明完成后，由ArtifactStore的上述组合操作查找候选、在事务外核验材料，最后在短事务内复核当前Work/依赖/产物资格并附属；附属与范围变化同次提交。WorkStore继续拥有语义与附属规则，ArtifactStore继续拥有材料判断，调用方不能传入`validated=true`或免检名单。

没有成功产物的READY/PENDING等需求可附属为未处理项；损坏引发失效后按原semantic规则取得可执行的当前Work。一个Artifact失效可能传递影响同批其他Work：必须先应用失效，再读取最终状态及返回值，不能返回前面预取的`succeeded`对象。对已在本Run附属的历史Work，按当前契约处理状态及失效；不伪造新attempt、不重写其真实历史来“刷新进度”。

同事务更新进度集合变化。`record_work_scope_change`可按实际受影响capability合并调用，但不得漏掉变化提示，last_progress_at只来自真实持久推进。已附属的重复请求不产生新的推进事实。批量完整读取Work时，用分块Work行和依赖行组装结果；只需要少数字段的原调用不要先构造完整WorkRecord再丢弃。

### Artifact核验及写回

批量查Work存在性、Work→Artifact关联及产物元数据。保留角色/位置和全部请求Work映射；一个物理Artifact可映射多个Work，但不合并来源、Evidence或生产依赖。

每个有界核验调用按唯一Artifact ID读取当前文件并完整核对hash和size，再映射到所有请求Work；这只是同次调用去重，不创建验证缓存。每个引用的Work资格、角色、顺序与来源依赖仍分别校验。组装、封存及最终pin等不同核验边界各自取得新观察，不跨调用缓存hash结论。提交损坏状态与Work失效后，不得用同批较早的available对象撤销失效或返回成功。

观察前保存所读Artifact行的内容身份和本次文件身份；文件读取继续使用原有非符号链接、普通文件和读取前后检查。提交时重新核对digest、size、路径、当前integrity以及Work状态/output身份，并确认路径仍指向本次读取的文件对象。字段中的验证时间仅更新、而身份/状态/文件均相同，不单独使整批重做；它不是新的失效版本。不能用墙钟时间排序来证明并发先后。

只对实际发生竞争的项重新做一次逐项完整核验，不反复重跑整批。如果仍无法稳定读取，沿现有文件不可用/Artifact完整性失败路径处理；未知数据库异常和矛盾记录向原执行错误边界传播，不伪装成坏图、有效命中或普通blocked。此处不新增无界重试循环、等待状态或持久“验证票据”。检测到被替换/变化必须拒绝旧结论；这仍是有时点的观察，不承诺提交以后文件不能变化。

损坏/缺失的integrity更新与相关Work失效在一个事务内完成；不能先发布“available”，后执行失效。好的兄弟成果不删除；已返回的成功项不可因后续批失败回滚。单批未知异常回滚未提交批，已提交批保留；已有尝试/冻结要求不丢失。

### 批内失败与边界

批事务的正常输出和异常输出必须分清，不采用“捕获异常后顺便提交有效前缀”的方式：

- 已知、可定位的材料缺失/损坏是Artifact核验的逐项结果；更新对应integrity并传播失效，正常兄弟项可在同一成功事务内提交。已知解码失败继续走原单来源producer处理，不升级为整批坏源。
- 非法输入、身份/依赖冲突、确定的固定输入变化等无法继续的错误，以及未知异常，回滚当前尚未提交的批并向原调用边界传播。先前已提交批保持；不在异常收尾追加写入，不把未处理项填成终结失败。
- 单项API仍提供原有逐项返回/抛错语义；新批API的回滚单位是此次有界提交。批内未提交的廉价检查可以在恢复后重验；此前任何已持久成功的昂贵Work不能因此重做。若异常所属Run按现有规则已failed，则不增加隐式resume能力。

批量代码要区分“尚未持久化的检查”与“已经完成的生产效果”。本期不批量改变昂贵producer的最终publish/lease规则，因此不会为了批量数据库提交而积攒一批未登记的解码或远端效果。

## 3. 接入准备、组装和封存

### 静态图准备

在现有rendition producer增加有界批量准备入口，编排只传路径、profile及原资源/控制上下文。每一来源的ordinary/high-resolution继续拥有独立spec、Work和结果。

批次内先批量取得来源证明，再调用ArtifactStore核验并确保产物Work/复用附属。命中在材料核验、当前资格及事务完成后返回完整RenditionOutcome；不是先附属所有成功Work再验证。READY/PENDING/RETRYABLE_FAILURE、已有有效lease、terminal failure、缺Artifact绑定和损坏等情况分别沿原状态规则处理，不统一当作可立即执行的miss。仍缺执行资格时返回当前实际状态；不能无限ensure/claim循环。

复核时如果当前semantic key已指向另一Work，不能把旧候选的核验结论套给新Work；必须核对当前ID、descriptor、依赖、output身份及材料映射后才附属。材料文件缺失/损坏可触发原失效与重算；声明成功却缺少该能力必须具有的Artifact绑定属于结构矛盾，走原错误边界，不默认当作普通缓存miss自动“修数据”。

发现缺口、失效或需重试时，沿现有claim→draft→render→source verify→publish路径执行。**在真正处理该来源之前重新执行原逐项来源检查，并重新核对/认领该Work；不得直接消费批首预取后等待过多个文件的proof或Work状态。** 可共用私有执行步骤，不能复制冷热两套语义或新增`skip_validation`开关。

同一来源两种profile都缺时，继续在一个来源生命周期里共享一次懒解码、按原文件身份变化规则重新解码；一项失败不抹掉另一项已发布成果。不能因改用`produce`逐profile循环而把一次解码变成两次。各来源的解码对象在处理完该来源时释放，不能在整批中常驻32份。

批次沿既有BoundedWorkExecutor调度，不更换scheduler。初始准备批量为32个来源、最大128，是可调整内部默认值；当来源少、已有可执行并发大于批数时，先将批拆小保留原来的可并行工作数，不能把全部小集合压成一个串行任务。每个批次仍按可能发生的缺口预留原单来源decode/encode资源，额外计入本批元数据和结果内存；若批量额外内存不够，先缩小批，不能截小单项真实资源估算。`max_pending`是批次数，待处理元数据总量须证明受`max_pending × batch_size`及字节预算约束，禁止全部S预取。

控制沿既有协作停止语义：检查至少发生在批开始、每个来源预检查/真正执行前以及准备提交的安全边界。观察到非running后停止开始后续来源；已进入执行的项可按原安全边界结束并保存结果。pause/cancel响应说明控制已持久接受，不承诺已开始的操作在该瞬间消失。对一个大文件hash不能即时中断的既有限制不扩大到整批；不得为实现“零竞态”把控制锁或写事务持有到解码结束。未知异常仍立即向原worker失败边界传播，不被批处理包装成部分成功。

协作停止发生在批中时，只交回已有实际结果，未开始项保留未处理；由原Run paused/cancelled状态阻止阶段发布，不填造失败项使返回数量等于批大小。整批方法抛错导致临时结果列表未返回时，之前已提交的Work仍保留并可由合法恢复重读，不能以列表丢失为由重做成功生产。

### 组装

在`_result_assembly`分块读取已选Work、依赖、Artifact与来源，复用本次组装的映射；后续Evidence投影消费同一批已经由所属Store核验的记录，不再为了判断存在性重复构造完整WorkRecord。映射只活在该次组装，不写缓存、不被后继Run当权威。读取本块元数据后先结束游标和读事务，再执行Artifact核验写回；核验导致Work失效后只消费新的最终状态，不能将早先行对象用于输出成功Evidence。

保留全部来源、Evidence、Observation、关系、精确成员、profile scope与直接输入绑定。查询只针对原来选中的Work，不按成功状态过滤后悄悄省掉失败/缺口。Result最终完整图本来需要O(输出量)内存，但不再常驻一份额外全量缓存；使用流式/分块中间处理，保持补修中封存草稿在完整Read前释放的行为。

批次完成顺序、SQL的IN返回顺序和字典插入顺序不得成为新的语义排序。保持原来源/代表选择和封存输出的确定顺序；为有依赖的下游恢复输入顺序或使用既有显式排序。用交错完成和不同批大小验证代表、成员、输出像素与语义身份不变，不能因调度修改就提升recipe版本来掩盖输出变化。

### 封存

保留以下原顺序和职责边界：

1. 原发布前snapshot重验；固定输入变化和不可用仍按原分类处理。
2. Result结构、关系、来源证明及材料资格校验；内部调用批量Store减少提交，不省规则。
3. 规范JSON编码、临时文件写入及同步、确定Result引用的文件发布；已有文件按原幂等恢复语义核对。
4. 原封存末尾来源重验；最终pin eligibility、所有Work资格/引用检查与Result注册在原事务边界完成。批量查询可以替换逐项查询，但必须核对每个请求成员且提交前无资格窗口。
5. 同一worker释放草稿/准备临时对象，完整Read校验后写completed。Read不能从可变Work补造封存内容。

最终pin处已有按唯一Artifact进行hash的逻辑继续保留；不把早期Artifact检查结果带过去取代它。发布前/后两种崩溃的重试仍只产生一份Result。任何批处理失败不能修改旧Result字节或解除原pin。

## 4. Observation验证器复用

在现有contract validator缓存/构造位置，复用绑定同一schema的Observation子验证器，避免每组Observation重新evolve根定义。不要引入另一个schema注册表、验证服务或手写较弱规则。

只缓存验证器定义，不缓存“这个Observation已经有效”的结论；每项仍执行schema、非有限数字、敏感性语义、属性去重及主体/来源关联规则。必须沿用当前`ReadValidator`类型、format checker、`$defs`及引用解析方式，不能直接换成通用jsonschema validator丢掉自定义校验。按Host已加载资源的生命周期复用，不在每项验证时重新读取文件/计算schema哈希；新进程、新资源装载或测试明确清空根缓存时同步重建子验证器。无需为此增加运行中热更新资源能力。不同线程不能共享可变错误迭代器或校验中间状态。若现有validator没有适合的安全复用途径，保留局部构造并说明原因，不引入新框架强行完成该项。

## 分阶段执行与验收

各阶段按依赖顺序实施，允许单独提交/回退。中间阶段不要求达到总时长目标，也不循环做8192项大测量。验证使用真实SQLite/临时文件系统，时间与并发竞态用受控时钟、事件或故障注入，不用脆弱sleep断言。

| 阶段 | 交付范围 | 必须通过的验证 | 停止/转入条件 |
| --- | --- | --- | --- |
| S0 基线固定 | 确切源码与依赖、原配置、测试命令、测量配方；保留并行diff | 主体补修的冻结恢复、源变化、旧Result留存相关测试通过；确认baseline与candidate使用同一公开路径/语义 | 相关基线失败不能豁免；无关既存失败可单独记录而不冒充本期修复。不覆盖他人代码 |
| S1 连接复用 | 连接helper、Run适配、scope接入 | 同线程复用、不同线程隔离；嵌套借用不提交外层事务；异常关闭/回滚；超时保持；observe结束释放快照；未结束游标不阻塞写入；pause/heartbeat仍可写 | 每次状态读是真实新查询；连接减少可以结构计数证明，不要求此时总时长下降 |
| S2 Store批量规则 | 三类Store的实际所需批量API与共用校验 | 单项/批量语义等价；空/重复/未知输入；descriptor及policy冲突；批内多次同键；revision和上游变化；Artifact失效影响同批兄弟；无异常后提交；已提交批保留 | 与S3真实消费者成对交付，不将死API作为完成；至少一个集成入口证明核验先于成功复用附属 |
| S3 接入与结果 | rendition批准备、组装分块、seal数据访问；原缺口执行保持 | 冷/暖/混合及局部新增；每项执行前重新验源；同源双profile一次解码；小集合不强制串行；进度不预报复用；交错完成不变输出；完整恢复/pin/发布/旧Read反例 | 正确性和资源边界先通过；分别验证1个及多个worker。不能仅以单worker全暖样本证明并发正确 |
| S4 验证器及回归 | 安全的子验证器复用，完成默认测试、必需scale及隔离公开入口 | 自定义ReadValidator/format规则保持；完整默认套件、Ruff、scope与多Result规模检查；最终确切wheel的CLI/MCP小链路 | 源码测试和安装包测试分别记证据；相关失败/未执行仍未完成，不改契约例子迁就实现 |
| S5 最终实际测量 | 固定baseline与最终candidate的功能、资源和成本对照报告 | 下面定义的矩阵、全部输出与留存核验；报告绝对值及变化，区分实测与未测 | 报告完成后停止。效果不理想仍可完成测量任务，但不得宣称达到性能目标或自动追加设计 |

### 对应现有测试与命令

以接手时`pyproject.toml`为准；当前pytest默认排除`local_fixture`和`scale`。没有仓库`.github`工作流可直接当CI模板。开发时先运行下列相关集合，不在每次微调后重跑全部规模。

```sh
rtk proxy .venv/bin/python -m pytest -q tests/test_precheck_sqlite_scope.py tests/test_work.py tests/test_source_validity.py tests/test_artifact.py
rtk proxy .venv/bin/python -m pytest -q tests/test_run_composition.py tests/test_run_composition_recovery.py tests/test_precheck_orchestration.py tests/test_precheck_result.py tests/test_read_validation.py tests/test_preparation_configuration.py
rtk proxy .venv/bin/python -m pytest -q tests/test_contract_authority.py tests/test_precheck_run_contract.py tests/test_precheck_read_contract.py tests/test_run_composition_contract.py
rtk proxy .venv/bin/python -m pytest -q
rtk proxy .venv/bin/python -m pytest -q -m scale tests/scale/test_multiple_results.py tests/scale/test_preparation_scope.py
rtk proxy .venv/bin/python -m ruff check src tests
```

实施者将新批量/竞态反例放在现有责任相邻测试中；不为每个helper写镜像测试。共享Store变化另运行metadata、video、embedding、sensitivity及Geo原测试，最终默认套件覆盖它们。默认套件通过不表示scale或真实模型已经测过。

真实Host小型链路须走公共start/status/控制/Read/resolve，保留完整Profile、直接对应和Plan创建新Work的边界。完成最终代码后必须对确切wheel做隔离CLI/MCP与artifact检查，可复用`tests/run_precheck_composition_smoke.py`、`tests/run_distribution_smoke.py`等已有入口，按其实际参数选择场景；CLI start/resume需要持久Host的现有边界不变，由MCP Host执行长任务。遵循[安装runbook的隔离验证规则](../../readme/installation.md)：清除`PYTHONPATH`和pytest的`src`注入，核对实际import来自隔离安装、记录wheel摘要。缺依赖或无法完成隔离验证必须明确未完成，不能用源码检查替代。日常安装、发布、远端调用和模型下载均不属于本设计授权。

两项scale功能检查属于S4的一次性回归，验证旧Result与大成员分页；它们不是S5性能样本。不要把其他为构造数据而修改同步参数的scale脚本当成本期性能配方。批处理资源有界性可用小输入加受控阻塞证明，不必为了该断言重跑百万来源生成器。

### 必须明确覆盖的故障点

| 注入位置 | 预期事实 |
| --- | --- |
| 批量观察后、提交前修改source revision/Work资格 | 旧观察不得用于成功附属/发布；按原规则重验或失败 |
| 控制线程在历史成功Work核验前读取status | 候选尚未因批量预取被附属为本Run复用；核验、资格复核和附属提交后才计数 |
| 产物hash后换文件/改Artifact记录，或另线程先写损坏 | 旧available结果不得覆盖新的矛盾事实；只对竞争项有界重验；同批受失效传播影响的Work不返回旧成功状态 |
| 批事务内部异常/进程终止 | 未提交批无部分持久成功；已提交批和所有旧Result保留 |
| 一项坏源与正常项混合 | 已知失败只归属于真实项，正常已提交成果不丢；未知错误不被吞掉 |
| pause/cancel与批准备竞争 | 控制接受真实持久化；下一来源必须重新读控制；已启动项按原边界结束，批剩余项不被伪报完成 |
| 批首proof完成后、实际轮到该来源前修改文件 | 真正执行前重新验源并按原分类拒绝变化，不解码旧证明对应的新文件 |
| 同源两个profile都缺、批次交错完成 | 成功路径每源只需一次共享解码；代表/成员/像素及语义键不因调度改变 |
| 批读游标未结束时进入Artifact写回 | 先释放本块读取；不会由复用连接制造同线程等锁或持有跨阶段快照 |
| 恢复时默认配置改变/冻结数据缺失 | 继续原冻结要求；缺失/损坏不降级到当前默认发现 |
| 文件已发布、DB未注册时崩溃 | 重试按原确定Result身份恢复，字节/语义冲突拒绝 |
| 注册后、completed前崩溃 | 恢复完整核验并完成原Run，不造第二Result、不提前completed |
| 驱逐producer缓存后读旧Result | 留存材料/pin和封存数据仍支持独立Read |

## S5：最终测量配方与判断

### 一致比较

S0固定优化前的可复现baseline，S4结束再固定最终candidate，两者均保留确切代码/依赖身份。baseline和candidate必须走同一种普通发现或显式同快照调用；旧调查中“baseline普通发现、candidate显式输入”的数字只能作背景，不能用于本期精确提速声明。除本期优化外，其他代码必须相同；若并行补修进入candidate，也将同一修复纳入对照baseline或重新标记不可比，不能把它计入本期收益。

同一数据、准备规格、配置、资源预算、解释器/core依赖、存储设备与status观察周期。使用独立进程，固定暖模板，串行运行，不与主线程测量或模型作业竞争。记录OS缓存未控制、系统负载、文件系统、历史Run/Result数量及实际代码位置。不能删除历史状态改善candidate。

当前Read不仅要求旧材料存在，还要求它的绝对路径等于当前workspace内的封存位置；因此**“异址克隆但原路径仍存在”不足以成为正常暖样本**。本期统一采用测试器独占的固定工作区路径：用同一baseline在该位置预热得到模板，在全部Host/SQLite连接关闭后完整保存模板；每个样本开始前在同一路径恢复一份独立可写副本，再由对应版本的新进程运行。源目录在全部样本间保持原位和身份；不改旧Result字节/locator，不硬链接可变数据库，不动主线程或用户工作区。

每样本结束后先核验并保留完整工作区副本、旧Result字节和公开读取轨迹，再在这个专用测试位置恢复模板供下一样本使用；不覆盖已归档证据。这是明确限定的测试夹具重置，不能扩展为删除产品历史。异址归档的旧绝对材料不能直接复验，需恢复到该专用原位置；在报告中说明该限制。若当前环境不能满足此方法，则正常暖矩阵未完成，不用故障页面样本代替。

先保存原状态/来源摘要并在计时外读prior Result预热；不得直接预热candidate本次Run。主Run计时从公共start调用前开始，包含请求冻结、执行、发布和worker完整Read核验，到固定周期status首次观察completed为止；普通发现场景的自动合成范围确认计入同一窗口，不能含人工等候。prior预热、模板复制/恢复、后置完整语义与旧字节核验分别报告、不混入Run墙钟。两版本status周期固定0.1秒，说明终态观察有最多一个周期加调用耗时的延迟；另报告后置公开Read耗时及Run+Read总成本。

每个规模的三个对照对交替baseline→candidate、candidate→baseline顺序运行，始终串行；记录每样本负载，避免把机器随时间变化全部归于某一版本。样本失败或外部负载明显异常时保留记录并解释，不只挑最快的三次。任何必须复测的理由均写入报告，不默认启动更多轮调优。

### 固定最小矩阵

| 场景 | 输入与重复 | 核验重点 |
| --- | --- | --- |
| 首次准备 | 512项有内容差异的合成静态图，各版本1次，普通发现入口，512项均显式列入既有定向准备配置 | 普通/高清输出、真实decode次数和失败责任；不据单轮宣称稳定加速 |
| 暖Run主矩阵 | 8×8 JPEG、4096/8192项、全部已有ordinary/high-resolution，1 worker/2 pending/512 MiB executor、target=2；同一显式快照请求，每版本每规模3个独立进程 | 相同准备、全量accounting及2入口；零重复decode；模板内部历史量相同；中位、范围、逐样本 |
| 局部准备混合命中 | 独立512项固定S模板，base target=2且无全量定向列表，初次仅部分准备；从已封存accounting选择4个未准备项和2个已准备项组成T，完整override设compression=null，每版本1次 | S/配置身份不变，完整S和T的新增准备、已有Work复用、scope成员及对应；实际缺口须由首次Result核实 |
| 非去重产物 | 内容差异512夹具，保证像素内容差异在生成产物中保留；同一baseline模板，每版本再暖跑一次 | 实际Artifact数大于2，完整ordinary/high-resolution材料及来源；不能仅文件名不同或源JPEG差异但产物仍相同 |
| 普通发现暖复用 | 内容差异512暖模板，省略source_set/profile，保持相同默认配置，每版本1次 | 普通发现/范围确认路径与显式快照均覆盖；单轮独立报告，不与主矩阵合并 |

控制成本配方明确固定为：image_renditions启用，metadata、GPX、video、bundles、embedding、sensitivity和远端provider关闭，compression target=2，采用现有`candidate-sha256-full-or-3x4k-v1`来源检查；除局部场景外在既有定向准备配置中列入全部来源。baseline与candidate使用完全相同的投影和能力开关。512场景沿用同一1 worker/2 pending预算以利对照；多worker、正常metadata/模型adapter行为在S3/S4功能回归中另验，不与这组成本数混合。

模型/远端不参与该隔离规模基准，这是固定测量场景，不是产品默认改为关闭。启用能力的功能与混合复用通过现有离线adapter/集成测试证明；没有本地现成模型就如实列真实推理吞吐未测，不下载、不远端调用。真实视频/外置盘不在本期自动扩大矩阵。

### 输出与成本记录

每个样本至少记录：代码/脚本/配置身份、输入及旧Result摘要、wall、进程user/system CPU、Run区间RSS峰值及采样/累计高水位边界、独立阶段时间、输出数量/字节、有效Work复用与新增attempt、decode/model/provider实际调用、历史Result留存及读取结果。

正常性能测量不启用逐SQL trace或cProfile。另用512项单次诊断记录连接/查询/提交与主路径阶段，证明工程机制接通；若需要大规模计数，放单独诊断样本，不能混入正式中位数。阶段只报告互斥区间；嵌套函数和多线程wall单列，不能相加。

用对照相同的方法记录S1连接打开次数、S2/S3实际提交批次以及S4验证器构造次数；这只证明设计手段实际接通，不要求某个固定百分比。SQL诊断须按producer、组装、封存区分，不能以其他阶段减少的次数冒充某项实现完成。最终代码与S4隔离验证wheel逐文件对应；S5若直接加载源码，必须核对其与该wheel中产品代码相同并明确报告，不能无意测到另一个工作树。

比较完整语义内容，建立明确的非语义差异白名单（新Run/Result ID、真实观察/发布时刻及必要路径重绑定），不能泛化删除所有provenance字段。核对每个Source occurrence、Evidence、Observation、关系/成员、Profile和直接对应、可用材料hash/size及旧Result原字节。入口数相同并不足够。

新Result比较按声明的来源occurrence及材料角色建立引用对应，不按相同内容摘要合并两个来源；本期原位模板不应产生旧路径重绑定例外。忽略新引用字符串时仍须验证所有关系端点都按同一映射对应。完整内容审计使用封存字节和公开Read/resolve的全部必要分页，核对无重复游标、最终成员数及membership_identity；既有100000成员scope与500→3→200等价功能测试不能由S5的2入口样本替代。

报告`baseline/candidate`原始秒数、中位和范围，以及`(baseline-candidate)/baseline`，CPU/RSS和磁盘量同样报告。单轮写明单轮，不跨规模或设备外推，不将微基准倍数当整Run收益。

### 验收分类与停止规则

- **正确性不通过：** 实施未完成，修复本期改动造成的缺陷；不进入性能成功结论。
- **正确性通过、收益清晰：** 报告优化幅度及适用范围，等待用户验收；不自动发布。
- **正确性通过、收益小/波动重叠：** 明确写“收益有限/未证明稳定改善”，列出已完成的工程手段及剩余成本，停止。低收益不是继续造实体或扩架构的授权。
- **性能或资源显著变差：** 不把候选描述为优化成功。排除明显测量错误并核对是否本期实现缺陷；如方法本身无益，报告保留/回退建议，停止，不能自动追加本期之外的架构。
- **环境无法测量：** 报告具体缺失条件，区分设计、功能验证和成本实测状态，不能用估算补齐实测。

不设强制提速百分比或跨设备秒数。可以修复本范围内的实现缺陷；不因为最终收益不理想启动新一轮无界调优。无需穷尽所有潜在性能点才能交付。

## 开发Agent交接清单

实施者先读本页引用的模型/当前契约和原Run补修验收；固定S0基线，再按S1–S4分别实现与验证。阶段间交接记录完成文件、守住的责任、测试结果和剩余失败；严禁把设计状态写成已实现。

最终交付代码差异、逐阶段验证、S5成本报告及明确留存/外部效果证明。沿既有评测session记录原始证据（ignored）和紧凑结果，不为执行引入新服务或任务实体。本设计任务到文档和链接检查结束；代码、测试实现及实测由后续开发执行。

## 开发前设计复核记录（2026-09-14）

本轮按当前实现和Run/Read承诺静态复核，并在上文原位置修正以下设计缺口；不是已经通过运行测试的声明。

| 发现的问题 | 已落定的处理 |
| --- | --- |
| 先批量附属成功Work、后验Artifact会扩大进度虚报窗口 | 只读候选与复用附属分开；ArtifactStore核验后与Work资格复核/附属同次提交，不增加进度实体 |
| 批预取证明被延后用于缺口执行，可能错用过期来源；逐profile改写可能重复解码 | 当项执行前重新验源/认领，继续同源双规格共享解码；补交错完成及资源/并发反例 |
| 异常后提交有效前缀、重复Artifact时最后观察获胜、竞争重试没有边界 | 未提交批回滚；同次核验按唯一Artifact映射；先传播失效再形成结果，只对竞争项有界重验 |
| 连接复用可能留下observe快照或游标，与后续写入互相等锁 | 同次status快照结束即释放；本块读取取完再进入写回，不持有长读事务 |
| 异址克隆保留原路径仍不符合Read材料位置要求；源码通过可能掩盖安装包未验证 | 固定同址模板、保留全部样本归档；最终wheel隔离CLI/MCP必验，补普通发现暖路径及scope规模检查 |
| 纯调度依赖与局部语义混在同一句排除规则中 | 仅排除纯执行选择，真实Profile/成员/来源依赖继续进入所属Work语义 |

静态复核后未发现仍需用户决定才能开始开发的设计阻塞点。S0确切基线、S1–S4实现正确性与S5最终收益仍须后续Agent实际验证；本结论不承诺具体提速幅度，也不授权本设计之外的重构。
