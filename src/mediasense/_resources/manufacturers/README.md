# 厂商知识维护指南

阅读或修改本目录的 YAML 前，从这里开始。本指南面向用户和后续 Agent，解释记录的含义，以及怎样新增、修订、验证和撤回记录。

本目录维护的是：**素材与附带元数据本身无法可靠说明、但处理媒体时需要知道的厂商行为。** 例如“某类设备漏写时间偏移”“某种 XML 中哪个字段才是设备型号”。照片中已经存在的型号、序列号、经纬度是素材的观察值；规则描述如何识别和解释它们，无需再登记一份素材台账。

## 从一条记录读懂 when、apply、basis

可以把一条规则读成一句话：**在什么输入上（when），采用什么处理（apply），为什么可以这样做、还不知道什么（basis）。**

| 字段 | 回答的问题 | 写法 |
| --- | --- | --- |
| `id` | 这条知识叫什么？ | 稳定 ID，例如 `dji.photo-time`；文件改名不需要改 ID |
| `operation` | 是新增、替换还是停用？ | `add`、`replace`、`disable`，见下面的修改方式 |
| `summary` | 这条知识解决什么问题？ | 一句人能读懂的说明 |
| `when` | 哪些输入适用？ | 标签与正则条件；所有条件成立才匹配 |
| `apply` | 匹配后怎样处理？ | 时间解释、字段来源选择，或坐标/尺寸配对 |
| `basis.sources` | 凭什么这样处理？ | 可定位的历史记录、厂商资料或用户观察 |
| `basis.limitations` | 依据还不能证明什么？ | 未确认的型号、固件、来源范围等；未知就写未知 |

例如 [dji.yaml](dji.yaml) 的 `dji.photo-time`：

- `when` 要求素材的 `EXIF:Make` 包含 DJI，且素材 MIME 类型以 `image/` 开头。这限定的是照片。
- `apply.capture_time.tags` 优先读取 `EXIF:DateTimeOriginal`，再读 `XMP:DateTimeOriginal`。`naive_time: source_local` 表示这些字段没有偏移时，按配置的设备时区解释。
- `basis.sources` 指向 AI Album 的历史配置和调查记录；`limitations` 如实说明历史没有完整固件范围，也不把照片经验推广到视频。

`when` 和 `apply` 会被程序执行。`basis` 会随规则依据交付给读者，但程序不会自动打开其引用，更不会验证它描述的事实。因此，**通过格式校验不等于依据已经成立**。

## 写到哪里，怎样选择修改方式

| 要做的事 | 修改位置与方式 |
| --- | --- |
| 改进所有安装用户共用的基础知识 | 在源码 `src/mediasense/_resources/manufacturers/` 编辑 YAML，随项目正常发布；内置记录使用 `add` |
| 增加个人规则 | 在用户 `config.toml` 旁的 `manufacturers/` 写 YAML，使用新 ID 和 `operation: add` |
| 调整一条内置规则 | 在用户目录写相同 ID、`operation: replace`，完整提供 summary、when、apply、basis |
| 暂停一条内置规则 | 在用户目录写相同 ID、`operation: disable` 和 `reason` |
| 撤回个人修改 | 删除对应用户操作；下一次新 Run 恢复内置规则，或不再使用个人新增规则 |

macOS 用户目录默认是 `~/Library/Application Support/MediaSense/manufacturers/`，已有 `MEDIASENSE_CONFIG_HOME` 可以改变其配置根。目录不必预先存在；只读取其中直接包含的 `.yaml`、`.yml` 文件。Dataset 没有另一份厂商 YAML 维护目录。

本目录的源码是内置知识的创作源，安装后的同名目录是发布副本。个人定制写到用户目录，避免被安装升级覆盖。文件名只用于组织；匹配条件必须写入 `when`。

`replace` 是整条替换，不是只补一个嵌套字段。同一用户 ID 只能出现一次；替换/停用必须指向存在的内置 ID。不要复制整套内置库到用户目录。

## 新增记录的起点

下面是合成示例，演示字段关系，不是可直接采用的真实厂商知识。先取得实际依据，再替换其中的条件、字段和说明。

```yaml
schema_version: 1
rules:
  - id: acme.photo-time
    operation: add
    summary: 合成 ACME 照片应优先读取 EXIF 拍摄时间。
    when:
      - tags: [EXIF:Make]
        pattern: '^ACME$'
      - tags: [File:MIMEType]
        pattern: '^image/'
    apply:
      capture_time:
        tags: [EXIF:DateTimeOriginal]
        naive_time: source_local
        fallback: true
    basis:
      sources: [合成教学示例，不代表真实厂商行为。]
      limitations: [仅用于解释配置结构，不认证任何设备。]
```

停用内置规则的结构更短，不附带 when/apply：

```yaml
schema_version: 1
rules:
  - id: dji.photo-time
    operation: disable
    reason: 合成停用示例，实际使用时填写具体原因。
```

## 选择条件和处理时要弄清的事

`when.tags` 是按顺序查找的备选标签，找到第一个非空值后用 `pattern` 匹配，不是“只要任意标签能匹配就算成立”。`pattern` 使用 Python 正则 search；`^`、`$` 分别限定开头和结尾，`(?i)` 表示忽略大小写。一个条件找不到字段是无法判断；字段存在但不匹配是不符合。

`scope` 默认 `source`，只查当前素材。确实需要已关联侧车时才用 `associated`，如 [sony.yaml](sony.yaml)。`File:*` 始终来自素材本身，不能把 XML 的文件类型当成视频类型。原始字段的分组名和大小写以实际 ExifTool 输出为准。

| 想调整什么 | 用哪个处理 | 要保留的含义 |
| --- | --- | --- |
| 时间标签优先级、无偏移时间解释 | `apply.capture_time` | `tags` 决定来源；`naive_time` 决定无偏移字段按本地时间还是 UTC 解释 |
| 已证实的设备时钟偏差 | `capture_time.shift_seconds` | 校正真实时刻；不能把显示时区换算误写成设备时钟偏差 |
| 型号、镜头等标准单值字段 | `apply.fields` 中的 `name` 与 `tags` | 保持标准属性的类型、单位和主体含义 |
| 纬度/经度、宽/高 | `fields` 中的 `tag_pairs` | 同一文件内成对选择；源尺寸只读当前素材；GPS 沿 WGS84 十进制度数语义 |
| 新的单值属性 | `manufacturer.<namespace>.<name>` | 声明 `value_type`、`description`，需要时声明 `unit`；整数保持精确值 |

`fallback` 默认 true，指定字段无法使用时允许通用来源参与选择；false 禁止这种回退。`priority` 默认0，大者优先。它表示选择优先级，不是可信度评分；同属性、同最高优先级但处理不同会报告冲突。不要为了消除冲突就随意加大数值，应先查条件和依据是否重叠。

设备无偏移时间所用的时区，在用户或 Dataset 的 `config.toml` 中配置 `metadata.assumed_timezone`；输出表示由 `metadata.output_timezone` 决定，两者默认 Asia/Shanghai。一次旅行的相机设置不应变成整个品牌的固有事实。已有显式偏移会参与解释。DJI 历史修正有其观察依据，不能凭通用格式印象删除，也不能在不知道范围时推广为所有 DJI 文件统一加八小时。

配置只能组合当前支持的处理。新私有格式、算法或转换需要先实现相应能力；不能在 YAML 中加入脚本或未支持字段。

## 从依据到验证

1. **确定差异。** 保留相关原始标签值，说明默认结果、预期结果及为什么不同。依据应让另一位维护者找得到：例如历史提交＋路径＋条目，或资料标题/链接＋章节，或有日期、样本引用的用户观察。没有的固件信息不要补造。
2. **写最小范围的变更。** 优先修改已有相关规则；新知识才增加 ID。把已经确认的范围放进 when，把尚未确认的范围写进 limitations。声明一个没有依据的更窄型号范围同样不可靠。
3. **检查配置能否生效。** 使用目标安装的 `mediasense doctor --json`，或 Dataset Open。检查 metadata 下的规则 ID、来源、替换/停用记录和错误。`execution: not_checked` 只表示尚未执行，不代表失败，也不证明命中了素材。
4. **用有限样本验证实际处理。** 通过已有 PreCheck Run/Read 比较变更前后。至少包含应命中的样本和相邻但不应命中的反例；涉及缺字段、显式时区或冲突时补相应案例。Read 中核对标准属性值、`provenance.manufacturer_knowledge` 的规则 ID、来源、匹配状态及保留的原始候选；不要只确认程序没有报错。
5. **说明验证范围。** 项目贡献者将相关回归案例加入现有测试，把迁移/安装证据记在既有台账。合成样本证明执行语义，实际设备结论需要对应原片或可信资料；两者分开说明。

从源码验证配置与规则行为，可在仓库根运行（使用已有开发环境）：

```sh
rtk proxy .venv/bin/python -m pytest -q tests/test_manufacturer_knowledge.py
```

该测试集验证已有机制与案例；新增规则仍需要自己的正反例。项目安装测试入口为 `tests/run_manufacturer_knowledge_smoke.py`，它使用生成媒体和隔离配置。构建、升级和正式安装按仓库 `readme/installation.md` 执行。

样本验证会创建 Run 和派生结果，输入范围要明确。metadata 规则本身不会调用模型或网络；Run 的其他已启用能力仍按其配置和授权执行。坐标进入 Geo 待处理集合也不等于取得了地图结果。

## 修改后何时生效，怎样撤回

新 Run 重读当前 YAML，并保存完整生效知识快照。恢复旧 Run 使用它原来的快照；修改文件不会在半次运行中替换规则，也不会重写旧 Result。对比效果要创建后继 Run，不要用幂等 start 的重放充当一次新执行。

用户文件写坏时，doctor 报错，新任务拒绝使用；Dataset 仍可打开并报告错误，有快照的旧任务仍可恢复。修好或撤回对应用户操作后重新检查。用户 replace 会持续覆盖内置同 ID 规则，软件升级后应查看 `overridden_rules`，确认个人修订是否仍有必要。

## 权威文件与继续阅读

本 README 是维护操作的唯一创作源，放在 YAML 旁并随包交付。它不另行定义文件格式；增加字段或改变承诺时先更新唯一契约，再同步实现、示例和本指南。

- **当前目录随包可读：** [机器 Schema](../contracts/manufacturer-knowledge.schema.json)、[DJI](dji.yaml)、[Canon](canon.yaml)、[Sony](sony.yaml)。安装后的 Schema 是该版本的发布副本。
- **有源码 checkout 时：** [完整字段与生效契约](../../../../docs/spec/contract/manufacturer-knowledge/index.md)、[新增示例](../../../../docs/spec/contract/manufacturer-knowledge/example-add.yaml)、[替换示例](../../../../docs/spec/contract/manufacturer-knowledge/example-replace.yaml)、[停用示例](../../../../docs/spec/contract/manufacturer-knowledge/example-disable.yaml)。这些源码链接在仅有安装包时不可用；不要把找不到 checkout 当作规则失效。
- **设计及证据：** 源码中的 [设计理由](../../../../docs/design/design-260911-1834-manufacturer-information-system.md) 与 [迁移台账](../../../../docs/eval/eval-260823-1918-ai-album-migration-baseline/eval-260823-1918B-capability-ledger.md)。历史调查引用不构成对 AI Album 仓库的运行依赖。
