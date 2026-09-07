# simplify-precheck-contract 实施验收

2026-09-07 完成首轮实施，原 25 项任务勾选。2026-09-08 用户复核发现三个遗漏，暂不通过验收；
原有 679 项离线测试通过不足以覆盖这些反例。修正与复验证据见本节，首轮记录保留在下方。
未 archive、commit 或 push。
起始状态为 OpenSpec Apply `ready`、0/25 任务完成；当时的 `status.isComplete=true`
仅说明准备文档齐全。本记录依据下面的实现与运行证据。

## 2026-09-08 复核修正

| 遗漏 | 修正与新增回归 |
| --- | --- |
| GPS/GPX 冲突输出 `conflicting` | 改为合约中的 `conflict`。以真实 GPX 匹配结果叠加合成 GPS Observation，封存后读取 `geo_summary`；验证重叠计数、GPX 优先、精确成员解析及源文件/封存字节不变。正常 GPX 仅补缺失坐标的策略未变。 |
| journal 恢复的未知费用变零，未知外发变空 | PreCheck 不再对未知请求的空 attempts 生成零费用；Run 诊断保留当前与历史未知请求的外发类别。Result review 同类分支也已修正。合成 Provider 在效果发生后、journal 完成前抛错，重开 stores 后只重放；Work、当前诊断和跨 Run 历史诊断保留 null，无新增 Provider execute。已知零请求/零费用仍是零，外发类别仍为空。 |
| 不存在 Run 的 MCP resume 错误 | 确认读取仅处理以所请求 run_ref 为键的预期 KeyError，返回正常分派；其他 KeyError 继续抛出。PreCheck 正常分派的业务错误保留 structuredContent 和 isError=true；真实 stdio 的 resume + proceed 与直接 RuntimeHost 调用得到同一个 run_not_found 对象。其他 Tool 及内部故障封装未改。 |

新增回归位于 `test_gpx.py`、`test_geocode.py`、`test_mcp_subprocess.py` 和 `test_runtime_host.py`。
修复前分别复现了冲突 Schema 拒绝、Work/当前诊断/历史诊断的 `0 != null`、复用旧 Work 的 Result
读取的外发类别丢失，以及真实 MCP 的 host_operation_failed；补充封装后确认结构化业务错误保留。
修复后新增 **14 项全部通过（9.88 秒）**。未删除或放宽原有断言。

不确定 journal 仍不能伪造 Provider 证据；新增测试保留其 `blocks_use` 限定与 seal 拒绝门槛。
复用旧 Work 的 Result 费用与外发读取另用完整 Provider/授权证据测试，覆盖未知、零和正请求数，
并验证旧 Work 内容与已封存 Result 字节、摘要不变。

| 本轮验证 | 结果 |
| --- | --- |
| 受影响 Run/Geo/Read/Host/CLI、真实 stdio 与生产组合 | **169 passed，56.72 秒**；包含九 action 和 PreCheck → Plan → Apply preparation。 |
| 默认离线 pytest | **693 passed，16 deselected，140.92 秒**；`rtk proxy .venv/bin/pytest -q --tb=short`，沿用默认 `not local_fixture and not scale`。 |
| Ruff、OpenSpec strict、verify_packet.py | 全部通过；包内仍为 2 contracts、9 actions、26 正向/13 拒绝向量、按 action 返回校验及精确成员摘要。 |
| 隔离 wheel/package smoke | 离线构建与临时安装通过，`distribution smoke: ok`；103 个包内源码/资源文件与当前工作树逐字节一致。 |
| 格式与差异 | 本轮触碰的 9 个 Python 文件通过 Ruff format --check；git diff --check 通过。 |
| README 的 OpenSpec 状态命令 | status.isComplete=true；instructions apply 为 all_done，29/29 任务完成。文档与任务状态不代替用户复验。 |

本轮 wheel：

```text
/private/tmp/mediasense-simplify-recheck-wheel.7MZYLM/mediasense-0.7.2-py3-none-any.whl
sha256:7e49fea585424d1daca4f66dbeaf44d1f09ca198fb7531ca2cef1490fbab7f90
```

```sh
rtk proxy uv build --offline --wheel --out-dir /private/tmp/mediasense-simplify-recheck-wheel.7MZYLM
rtk proxy .venv/bin/python tests/run_distribution_smoke.py /private/tmp/mediasense-simplify-recheck-wheel.7MZYLM/mediasense-0.7.2-py3-none-any.whl --offline
```

`tasks.md` 第 7 节的 4 项修正任务已完成；用户复验结论尚未给出，不能将工具检查通过称作用户验收通过。

## 完成范围

| 任务 | 实施与保留的能力 | 主要运行证据 |
| --- | --- | --- |
| 1.1–1.3 | 两个 PreCheck Tool、九 action；输入展平并显式绑定 Dataset；按 action 校验返回；其他 Tool 传输格式不变 | `test_precheck_run_contract.py`、`test_precheck_read_contract.py`、`test_runtime_host.py`、`test_runtime_cli.py`、`test_mcp_subprocess.py` |
| 2.1–2.4 | 单层进度、终结工作计数、未知 null、同阶段集合变化；一次读取事务内的状态事实；有界问题与诊断分页；幂等启动与真实控制状态 | `test_precheck_run.py`、`test_precheck_orchestration.py`、`test_precheck_simplification_edges.py` |
| 3.1–3.4 | 63 项范围 entries 与指纹分页；完整披露身份与可信确认；共享 Geo 独占有限重试；每次 HTTP 前检查 deadline | `test_precheck_scope_review.py`、`test_geo_tool.py`、`test_geo_capability_model.py`、`test_geocode.py`、专项边界测试 |
| 4.1–4.4 | v4 producer；地址/附近地点独立 Observation；fresh、复用、合法历史投影共用纯规范化；缺地点非阻塞；旧字节与摘要不改写 | 整批双 no_result、整批已知失败、v3 missing+value 转换、证据不足 not_checked、合法旧 Result 投影、非法 seal/read 拒绝 |
| 5.1–5.4 | review/expand/resolve/geo_summary 精简；独立费用分页与总字节边界；两种 prepared target；全部 Source Set 表达式和双摘要；Plan/Apply 消费者同步 | `test_precheck_result.py`、`test_source_sets.py`、Plan/Apply 测试、`test_stage_handoff_e2e.py` |
| 6.1–6.6 | active 规范、OpenSpec 规范、Skills、机读 mock、打包资源同步；离线回归与最终 wheel 验证 | 默认套件、Ruff、真实 stdio、生产组合、严格 OpenSpec 与 packet 检查 |

源码中的 `integrity` 仍服务于不可变封存及内部验证；删除的是公开成功响应中的常量。
Source Set 消费者仍验证真实数组长度、排序、重复成员、游标推进、终页总数以及完整成员摘要。
读取成功不替代 Apply 对当前源内容、路径、文件系统、冲突和冻结计划的独立检查。

## 首轮验证（2026-09-07）

| 验证 | 结果 |
| --- | --- |
| 默认离线 pytest 套件 | **679 passed，16 deselected，0 failed，132.88 秒**。通过 `pytest.main(['-q', '--tb=short'])` 运行，只增加结果汇总 hook；使用 pyproject 的默认 `not local_fixture and not scale` 选择。 |
| `rtk proxy .venv/bin/ruff check src/mediasense tests openspec/changes/simplify-precheck-contract/verify_packet.py` | All checks passed |
| `rtk proxy openspec validate simplify-precheck-contract --strict --no-interactive` | valid |
| `rtk proxy .venv/bin/python openspec/changes/simplify-precheck-contract/verify_packet.py` | 2 contracts、9 actions、26 正常/13 拒绝向量、按 action 返回校验及精确成员摘要全部通过 |
| `rtk proxy git diff --check` | 通过 |
| `rtk proxy openspec status --change simplify-precheck-contract --json` | `isComplete=true`，仅作为文档状态读取。 |
| `rtk proxy openspec instructions apply --change simplify-precheck-contract --json` | **all_done；total=25、complete=25、remaining=0**。 |
| 最终 wheel 内容核对 | 103 个包内源码/资源文件与当前工作树逐字节一致；修改的 Markdown 链接均存在。 |
| 真实 stdio MCP | 九 action 均经过实际 Host 分派，包含成功取消未完成 Run 及拒绝取消已完成 Run；成功观察 failed Run 保持 `isError=false`，调用错误使用 `isError=true`；旧 wrapper 拒绝。最终补充正向取消断言后，`test_simplify_precheck_contract.py` 再次 **2 passed（5.54 秒）**。 |
| 生产组合 PreCheck → Plan → Apply preparation | 合成媒体通过冻结计划与准备验证；无现场媒体整理效果。 |
| 隔离 wheel/package smoke | 离线构建及临时安装验证通过：`distribution smoke: ok`。CLI、包资源、MCP 发现、PreCheck 调用及 Plan 入口可用。 |

最后一份 wheel：

```text
/private/tmp/mediasense-simplify-final-wheel.zztfSn/mediasense-0.7.2-py3-none-any.whl
sha256:bb4979b2d12fa82f67121f97c14420481621d521d1800c90b4cdf5f5fe7d0d95
```

构建和 smoke 命令：

```sh
rtk proxy uv build --offline --wheel --out-dir /private/tmp/mediasense-simplify-final-wheel.zztfSn
rtk proxy .venv/bin/python tests/run_distribution_smoke.py /private/tmp/mediasense-simplify-final-wheel.zztfSn/mediasense-0.7.2-py3-none-any.whl --offline
```

验证中发现并修复过：精简时漏掉 Result 绑定的成员摘要、Apply 未注入 Dataset、seal 残留地点门槛、
完整 expand 残留旧字段、MCP Schema 缺少根 object 类型、已授权披露变化的重确认边界、
状态快照不一致，以及卡片和费用页共用总字节预算的问题。保留相应行为断言。
wheel smoke 最初无法在临时 HOME 中按版本名找到 Python；改为绑定运行 smoke 的确切解释器，
并显式复用原离线依赖缓存，安装与配置仍留在临时目录。

## 未完成项、限制与现场边界

首轮记录之后的补充修正以第 7 节任务及本轮复验证据为准。未运行真实 Provider、外部服务、
现场 fixture 或 scale 验证；离线测试通过不能作为现场升级、真实服务吞吐或计费实测的证明。

所有运行验证使用合成数据和临时 workspace。没有读取或修改现场运行数据库、操作用户媒体、
重跑现场 Dataset、产生真实 Provider 计费或升级本机安装版。Apply 执行/恢复的既有单元测试
只操作它们自己的临时合成文件；生产纵向验收止于 preparation。
原有讨论文档及工作树修改保留，没有重置或覆盖无关变更。

本次没有调整 (0,0) 元数据过滤、视频解码策略、Provider 选择或媒体压缩算法。
