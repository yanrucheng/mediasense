---
id: "index-manufacturer-knowledge"
title: "厂商知识文件与生效契约"
type: index
status: active
created: 2026-09-12
updated: 2026-09-12
timezone: "Asia/Shanghai"
parent: "index-contract"
depends-on:
  - "design-260911-1834-manufacturer-information-system"
superseded-by: ""
---

# 厂商知识文件与生效契约

用户已确认目的、行为承诺与 B 方案，并授权先定文件契约再开发。本页是该文件接口的当前权威；它不增加公共 Tool、stage 或服务。实现和安装验证另记[迁移台账](../../../eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。

## 文件位置与权威

```text
src/mediasense/_resources/manufacturers/     随包基础知识的唯一创作源
  dji.yaml
  canon.yaml
  sony.yaml
<用户配置根>/manufacturers/                 用户新增、完整替换或停用
  dji.yaml                                 名称只用于组织，不隐含匹配条件
<Dataset workspace>/precheck/work.sqlite3   本次生效知识快照和已有 Work
```

用户配置根复用现有 `config.toml` 的父目录。macOS 默认为 `~/Library/Application Support/MediaSense`；已有 `MEDIASENSE_CONFIG_HOME` 可指定其他位置。只读取目录直接包含的 `.yaml`、`.yml` 文件，按文件名稳定读取。目录不存在表示无用户增量，不自动写入整套默认模板。普通配置文件支持指向常规文件的符号链接；目录、不可读文件或读取到的无效 YAML 必须明确报错。

Dataset 不另外发现厂商知识目录。它的普通 metadata 设置可以不同，但厂商知识的个人维护入口始终只有上述用户目录。安装资源是发布副本，用户不需要修改 site-packages。

文件采用 UTF-8、单文档 YAML，解析后的值须为 JSON 可表示的数据；禁止重复键、自定义标签、锚点/别名、非有限数及未知字段。机器定义是 [manufacturer-knowledge.schema.json](manufacturer-knowledge.schema.json)，随包副本只能从此同步。规则 ID 在文件之间唯一；文件改名不改变规则含义，但来源变化会进入新快照。

## 字段

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 必须为整数1，描述文件格式，不是软件版本或固件版本 |
| `rules` | 规则操作列表；空列表合法，未知键拒绝 |
| `id` | 稳定规则身份，小写字母起始，后续可含数字、点、下划线、连字符 |
| `operation` | 必填 `add / replace / disable` |
| `summary` | add/replace 必填，说明要补充的厂商知识 |
| `priority` | 默认0；按被影响的属性分别比较，大者优先；数值不表示知识正确率 |
| `when` | 至少一项条件，全部成立才匹配 |
| `apply` | 至少一个已支持处理：`capture_time` 或 `fields` |
| `basis.sources` | 至少一个非空来源说明；可以是历史提交/记录、厂商资料或明确的用户观察，不自动联网解析 |
| `basis.limitations` | 必填列表，可以为空；未记录的型号/固件范围应在这里如实说明 |
| `reason` | disable 唯一的说明字段，必填；不附带被忽略的 when/apply |

每个 `when` 条件包含有序 `tags`、Python 正则 `pattern`、可选 `scope`。scope 默认 source，只查当前素材；associated 可查已关联且实际读取的侧车及当前素材，沿既有侧车优先级。按标签顺序、再按来源顺序取第一个非空值做正则 search。`File:*` 始终只查素材本身，不把侧车文件类型当成媒体类型。字段缺失为无法判断；值存在且正则不匹配为不符合；有一项明确不符合即可排除整条规则。非法正则在配置检查时报错。所有条件和目标标签必须纳入实际批量提取。

## 覆盖与竞争

内置文件只使用 add。用户 add 不得重用已有 ID；replace/disable 必须指向存在的内置 ID。每个用户 ID 最多出现一次；用户文件之间不靠加载顺序覆盖。replace 是完整规则替换，必须重新提供 summary/when/apply/basis，不能发生隐式深合并；disable 只保留停用记录。对某个内置 ID 的明确替换会跨软件升级继续有效，诊断同时保留被替换的内置来源；恢复内置规则只需删除用户操作。

不同规则可以影响不同属性。同一属性的最高优先级匹配规则若效果相同，则共同作为依据；若效果不同，该属性为 failed，basis 说明 `manufacturer_rule_conflict`。其他独立属性继续准备。未能判断是否适用的规则不冒充不符合：沿用已声明的通用解释时附 `manufacturer_rule_applicability_unknown` 限制。明确匹配、未匹配、信息不足、低优先级和冲突的区别进入该属性 provenance。

## 支持的处理

`apply.capture_time`：

| 字段 | 含义 |
| --- | --- |
| `tags` | 优先采用的时间标签，至少一个 |
| `fallback` | 默认true；目标字段均不可用时继续采用默认字段及文件名/mtime 回退。false 时这些回退不参与选择，但已有候选原值仍保留 |
| `naive_time` | 可省略以沿用字段语义；source_local 表示以配置的 assumed_timezone 解释无偏移值；utc 表示以UTC解释。只影响 tags 指定的字段，已有显式偏移或 EXIF OffsetTimeOriginal 仍参与解释 |
| `shift_seconds` | 默认0，已选中目标字段解析后的真实时刻校正，可正可负；这是明确的设备时钟补偿，不能当成显示时区转换。不会修正默认回退来源 |

补偿后超出可表示的日历范围时，该时间候选保留原值和 `manufacturer_clock_correction_out_of_range` 原因；按已声明的 fallback 决定是否继续选择其他来源。没有可用候选时，该时间观察失败，其他属性继续处理。

旧 DJI 照片及 Canon EOS DSLR 经验优先采用 EXIF/XMP 拍摄字段并按源时区解释无偏移值；不将其改写为对所有视频或所有带偏移时间机械移动八小时。历史未记录的版本保持未记录。其他明确有依据的时钟偏差可通过 shift_seconds 表达。

`apply.fields` 为非空列表，每项含 name、tags、可选 fallback（默认true）。内置摄影属性沿 [Read 属性定义](../precheck-read/precheck-attributes.md)固定类型、单位和实际来源；这里只改变标签选择，不能重定义属性含义。默认追加通用候选；fallback=false 时只允许指定标签参与选择。相机型号的显式字段规则可以在有条件和依据时采用设备的 Encoder 值，未采用该规则时继续保留通用的 Encoder 拒绝规则。

扩展字段必须使用 `manufacturer.<namespace>.<name>`，额外提供 `value_type: string / number / integer / boolean` 和 description，可提供 unit（字符串或null）。同名扩展在整份有效知识里必须有一致的类型、单位和含义；冲突在配置检查时拒绝。number/integer 支持数值和分数字符串；boolean 只接受布尔值、0/1或明确的 true/false 字符串。扩展值仍属于来源 Source Item，使用既有 Observation，未知属性不成为新的主体。

## 时区上下文

运行设置留在现有用户/Dataset `config.toml`：

```toml
[metadata]
assumed_timezone = "Asia/Shanghai"
output_timezone = "Asia/Shanghai"
```

两项均为 IANA 时区，缺省均为 Asia/Shanghai，分别回答无偏移设备时间怎样解释、同一时刻用哪个时区表示。Dataset 在已有配置优先级下覆盖明确提供的 metadata 键。规则不把用户这次拍摄设置写成全体同品牌设备的事实。

## 快照、失败与交付

Dataset Open 和 doctor 校验知识，报告 `identity`、`sources`、`active_rules`、`overridden_rules` 和 `disabled_rules`，execution 保持 not_checked。`overridden_rules` 同时给出替换规则的用户来源与被替换的内置来源，便于升级后核对仍被个人规则覆盖的知识。新 Run 在接受新工作前重新读取当前文件；幂等 start 重放不读取新知识。Run 把完整解析内容（含已覆盖的内置来源）、时区上下文和规范化 JSON 摘要保存进已有 execution_config，不只存文件路径或版本号。恢复使用快照，即使文件随后变化或删除，也不混用新规则。旧配置没有知识快照的历史 Run 沿已知的无厂商规则语义恢复，不自动套入新版知识。

无效配置拒绝本次生效，并定位文件、规则或字段；不悄悄退回内置知识。未知处理类型明确拒绝，不接受任意脚本/import/命令。运行中的实现异常按 Foundation 直接暴露。字段缺失、规则不适用和规则冲突按前述观察语义分别交代。

对应 Observation 的 `provenance.manufacturer_knowledge` 保留快照身份、规则 ID/来源/basis、匹配依据及使用结果；匹配依据中的媒体路径投影为公开 Source Item 引用。规则选择与修正不会抹掉未选择候选。Read 原样交付这些已知依据；不把配置存在说成规则已执行。扩展字段的类型、单位和说明进入其 provenance。

有效知识和时区语义进入 metadata Work 身份，包括此前未命中的规则变化。第一版保守重评 metadata，传播到真实的 GPX/关联/压缩依赖；可证明无关的图像和模型工作复用。不会修改原媒体、旧 Result 或冻结 Plan，不自动扩大 Geo 授权。

## 示例与验收

- [新增知识和字段](example-add.yaml)：不改 Python，即可按新厂商条件交付时间与扩展字段。
- [完整替换内置规则](example-replace.yaml)：同一 ID 明确改变作用范围及处理。
- [停用内置规则](example-disable.yaml)：不删除随包文件，诊断保留停用原因。

验收覆盖 DJI 照片/视频、Canon 型号正反例、Sony 来源映射、新增字段、同优先级冲突、缺条件、非法文件/重复ID、修订和撤回、快照恢复、真实安装的配置→提取→Run→Read。只用合成和受控媒体认证接通与语义；未声称所有型号/固件准确率或大数据吞吐通过。
