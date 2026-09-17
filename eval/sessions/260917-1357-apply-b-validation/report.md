---
title: "Apply B：同卷有限核验与可信 Host 授权"
service_version: "0.11.0 working tree, unreleased"
date: 2026-09-17
environment: "macOS 26.4.1 arm64 / local APFS / isolated temporary files"
model_id: "not-applicable"
dataset_version: "synthetic-dense-apply-b-v1"
purpose: "验证已选 B 的来源连续性、可信确认、逐项持久化与内容读取成本"
baseline_ref: "260916-2258-first-apply-acceptance"
---

# Apply B 开发与隔离验证

已完成[已选 B](../../../docs/design/design-260917-1150-apply-safety-efficiency.md)的本地开发、隔离安全测试和三类负载测量。正式保证维护于 [Apply 合约](../../../docs/spec/contract/apply/index.md)。原始工作区的设计、Plan/PreCheck Skill、验收报告及索引改动保留；过程中另出现的 README 和 Intel Mac 交接文档不属于本次修改。

本次未发布、未升级日常安装，未执行真实媒体 Apply。所有源文件由测试生成，位于 `/private/tmp/mediasense-apply-b-*` 或 pytest 的独立临时目录。不存在真实媒体或香港 fixture 的读取/移动。

## 改了什么

1. **来源连续性。** 复用精确 Result 的公开 resolve 投影，比较原有 `candidate-sha256-full-or-3x4k-v1` 指纹及大小；缺失、失败、未知、畸形或不匹配的依据阻塞准备。保留原 producer、basis 和 qualifications，不再以当前新算的完整 hash 替换旧证据，也不修改旧 Result。缺少必要投影才调用对应 Source Item 的 expand。
2. **同卷效果与恢复。** 准备保存 dev/inode/size/mtime/ctime。效果前核对这份绑定及安全位置，复用不覆盖 rename，效果后核对同一对象、大小、mtime、目标位置和源位置消失；rename 可改变 ctime，后置值另行记录。执行、常规中断恢复和关闭不扫描媒体内容。恢复只协调 durable intent，不把同字节的另一个目标对象认作已完成。
3. **持久化。** 保留 SQLite `synchronous=FULL`、逐项意图和结果提交；补齐源、目标父目录同步。没有合并提交、批量窗口、同步降级或隐式复制删除。原有目录记账、幂等、分段回执、暂停/取消及 rewind 继续使用。
4. **授权适配器，独立于效率优化。** MCP schema 移除非正式业务参数 `authority`，收到它直接拒绝；CLI `--authority` 也被拒绝。Host 读取真实准备摘要，通过客户端 elicitation 取得一次整批确认，并绑定精确 Run/revision/digest、效果、根、路由及核验保证。相同 execute 请求重放使用已持久的授权，resume 不接收新的元数据损失。status 不启动媒体效果；确认无执行 owner 后呈现中断恢复条件，未知 worker 异常显式失败。
5. **接口与规范。** 三份正式 Apply JSON 定义逐字节不变。沿用 warnings、source_verification、filesystem_identity_and_location 等表达；既有 verification.basis 保存实际后置对象事实，供 rewind 使用。没有新增 Tool、action、公开状态、Batch、批大小参数、file_state、transfer_policy 或字段改名。Apply Skill 补充有限核验、一次客户端确认、幂等重放及完成时报告 rewind 期限。

私有 Apply store 为 **3**，包含准备 ctime 与独立的跨卷完整传输摘要。旧格式 2 不由新构建接管或自动迁移；旧 Result、Plan、Receipt 字节不变。部署过渡不在本次开发验证范围，已同步安装 runbook 及其包内副本，防止直接替换仍持有旧 Run 的 Host。

## 安全与生产装配证据

`tests/test_apply_b_safety.py` 加上原有 Apply 集成测试覆盖以下实际临时文件行为：

| 场景 | 实际结果 |
| --- | --- |
| 真实 PreCheck Result 封存后修改源大小/内容 | prepare 阻塞，未移动；原 Result 读取完全相同 |
| 缺失、失败、未知、畸形、大小或指纹不匹配的旧依据 | 拒绝；不建立一个新 hash 后就绪 |
| 旧证据仅为完整 SHA-256 | 同卷 B 在内容读取前阻塞；不从完整摘要推导有限指纹 |
| 0、1、12,287、12,288、12,289 字节和 8 MiB 文件 | 每项实际 read 返回量为 min(size, 12 KiB) |
| 小文件在读取时快速增长 | 只读原大小，检测变化后拒绝；不循环读到新 EOF |
| 准备后写入并恢复 mtime、同字节对象替换 | ctime 或对象绑定不匹配，拒绝效果 |
| 检查与 rename 之间替换源对象 | 后置发现错误对象，保留不确定 intent 并停止后续项 |
| 原有/竞态目标、错误目标、源目标均在或均不在 | 不覆盖，不自动改名/删除，不冒认完成 |
| intent 后、rename 后记录前、两端同步前后、结果提交后、回执发布后 | 恢复同一操作和同一逻辑 Receipt，无重复移动 |
| 真正子进程 `os._exit(42)`，以及结果记账写入失败 | durable intent/结果与实际文件协调；不把异常算完成 |
| 恢复、效果和关闭期间禁止打开媒体内容 | 测试通过；恢复未引入全量内容扫描 |
| rewind 时以同字节新对象替换已移动文件 | 被 Receipt 的后置身份/状态检查拦截 |
| 自填 authority、无客户端能力、decline、cancel、确认时准备身份改变 | 零未经授权的移动 |
| 相同 execute 重放、同一授权下恢复 | 不重复效果，不要求第二次确认 |

最终 wheel 的相关测试 **165 passed, 3 deselected**，22.25 秒。范围包括 Apply 准备/执行/恢复/契约/Skill、MCP 和版本一致性；这些测试使用自动化的合成确认，不冒称进行了人类可用性验收。

另以最终 wheel 在独立工作目录启动真正 `python -m mediasense mcp` stdio 子进程，通过 MCP ClientSession 完成 Dataset open、读取真实封存 Result、prepare、伪造拒绝、客户端 elicitation、execute、status、重复 execute、Receipt read。**7 个 Tool；整批确认恰好 1 次；结果字节正确；旧 Result 不变。** 见 [host_probe.py](host_probe.py) 与 [stdio-host.json](metrics/stdio-host.json)。

**冻结源码的最终全仓回归：1,568 passed，17 deselected，367.81 秒。** 前一轮为 1,567 passed / 1 failed；失败记录为 PreCheck `_artifact_sqlite._digest_file` 的 `Artifact changed while reading`，该发布代码未被本轮修改。随后整个 `test_run_composition_recovery.py` 的 21 项独立重跑通过，固定源码再次执行完整默认套件亦通过；本报告保留这次偶发失败，不宣称已经修复该发布路径的所有并发情况。此前还处理了现有 .venv 的 0.10.2 元数据、沙箱阻止 loopback 测试及开发期间构建身份变化带来的测试干扰；最终使用真实 0.11.0 wheel 元数据与固定源码，不改测试预期掩盖产品失败。

## 性能：读取量和耗时分别看

环境为 macOS 26.4.1 arm64、本机 APFS SSD（[卷信息](metrics/volume.json)）。使用实际写入的稠密合成字节文件，扩展名为媒体或 sidecar；不要求它们是可解码的视频/XML，因为 Apply 不解释内容。源分布于每目录最多 100 项的子目录，目标为同一冻结逻辑目录。两版使用完全相同的 Plan、公开读取配方和结果核对。

[run.py](run.py)分开统计源/目标媒体 read 返回字节、阶段耗时、CPU、进程峰值 RSS、显式 SQLite commit 数量及等待、目录 fsync 数量及等待。文件生成不计入阶段时间；RSS 是整个测试进程峰值。缓存未清空，测量期间本机还运行过仓库测试，属于暖缓存/非独占环境；数值不认证冷盘、HDD、真实 TB 媒体或长期吞吐。读取量是应用层数据量，不是物理读盘量；最终有限指纹使用无缓冲读取，避免 Python 额外预读，文件系统/设备自身预读仍未测量。

大媒体取各 3 次中位数；2 万小文件和混合负载使用第一组完整基线，最终 B 小文件另用最终 wheel 重测一次。没有选择最快结果。开发期测量仍保留，但主表的最终选择与各项统计见 [combined.json](metrics/combined.json)。

| 合成负载 | 源字节 | 旧实现内容读取 → B | 准备至核验完成耗时：旧 → B |
| --- | ---: | ---: | ---: |
| 8 × 128 MiB 大媒体 | 1 GiB | 3 GiB → 96 KiB | 1.407 s → 0.172 s |
| 20,000 × 512 B 小文件 | 10.24 MB | 30.72 MB → 10.24 MB | 343.861 s → 328.430 s |
| 1,000 × 256 KiB 媒体 + 9,000 × 512 B sidecar | 266.752 MB | 800.256 MB → 16.896 MB | 146.386 s → 137.320 s |

**B 三类负载的执行阶段内容读取均为 0，媒体内容写入均为 0；每项读取最大 12 KiB。** 小文件可能在准备时被完整读一次，但不会在执行前后再读两次。所有已完成负载的 Receipt 完整性、逐项结果数及最终映射一致。

大文件耗时在本机约为旧实现的 1/8.2，而读取量下降约 32,768 倍；小文件和混合负载仅观察到约 4.5% 与 6.2% 的总耗时下降，不能视为稳定的提速承诺。**没有把读取量下降写成同倍数加速。**

| B 的保留成本 | 大媒体 N=8 | 小文件 N=20,000 | 混合 N=10,000 |
| --- | ---: | ---: | ---: |
| 意图提交 / 结果提交 | 8 / 8 | 20,000 / 20,000 | 10,000 / 10,000 |
| 全部显式提交 | 34 | 60,010 | 30,010 |
| 全部 commit 累计等待 | 0.0048 s | 6.553 s | 3.293 s |
| 意图 + 结果 commit 等待 | 0.0022 s | 4.271 s | 2.046 s |
| 目录 fsync 次数 | 18 | 40,002 | 20,002 |
| 目录 fsync 累计等待 | 0.0011 s | 1.137 s | 0.535 s |
| 准备时间 | 0.073 s | 83.683 s | 42.448 s |
| 执行时间 | 0.096 s | 244.613 s | 94.816 s |
| CPU 时间 | 0.054 s | 162.703 s | 60.705 s |
| 峰值 RSS | 69.24 MB | 550.81 MB | 330.48 MB |

旧实现的提交数量完全相同；B 的目录同步增加到两端。小文件的每项意图+结果 commit 等待约 0.214 ms，混合约 0.205 ms；这只计 SQLite commit 调用，不含连接、SQL 执行、状态查询、路径检查、锁或回执构建。不能把其余数百秒全部归因于 fsync。本次未实现 C，也未优化全部随条目数增长的查询和记账成本。

作为机制成本参照，裸不覆盖 rename 三类样本为 0.0023 s、3.818 s、1.778 s；它没有来源检查、Human 授权、逐项日志、目录同步、恢复或 Receipt，不能据此建议绕过 Apply。

## 保证与剩余限制

- 相比旧实现，来源旧依据跳过和 Agent 自证 Human 两个已知缺口已经修复，效果后也实际核对目标文件对象。安全改善来自这些检查和授权边界，不能归因于删除 hash。
- 有限旧证据不能识别所有准备前变化。测试明确保留了“同大小、抽样之外改字节仍匹配”的例子；旧 Result 没有可比文件身份时，也不能辨认具有相同有限证据的替换对象。准备后的状态检查不保证发现无状态变化的静默损坏；这弱于完整字节对照。
- ctime 因 rename 可变。没有持久后置结果的中断恢复只能比较已准备身份、大小、mtime、类型和位置；不能补造丢失的后置 ctime。普通元数据变化也可能造成保守拒绝。外部程序恶意并发修改、inode 复用、跨未验证重挂载均不在已证明的连续性范围。
- 保留逐项持久化不等于证明突然断电安全。本轮验证进程退出和注入式同步/记账故障，未做系统崩溃、重启、突然掉电或物理介质损坏测试；未新增 Linux、HDD 或跨卷平台认证。
- MCP 依赖可信客户端的 elicitation 能力。取消、拒绝、不支持或无法完整展示超限披露时不授权；没有新授权服务。不能抵御同一 OS 账户下任意恶意代码。
- 大量小文件仍慢，并保留逐项提交成本；本轮没有完成所有按 N 增长的性能优化。峰值 RSS 和单次耗时不是通用资源保证。
- 新私有格式不能直接接管旧 Run。本轮不提供保留 Dataset 的发布迁移，也未安装；不得用相同 `0.11.0` 版本字符串推断已运行 Host 就是这份代码。

## 复验与构建身份

基线 HEAD：`cc3354db1f132be0d44e85ceb8272339c5f3f241`。开发前已把未改的 Apply 三个核心文件和源码复制到隔离目录，未覆盖用户已有改动。最终源码及基线核心摘要见 [code-identity.json](metrics/code-identity.json)。最终 wheel：`/private/tmp/mediasense-apply-b-final-build/mediasense-0.11.0-py3-none-any.whl`，SHA-256 为 `bf606b753520803bd8a16948c127cace2c2aadd43386858142f2af636ed45f8c`。安装 runbook 及包内副本一致，正式 Apply JSON 结构未改。

```bash
# 构建；只写临时输出，不安装
rtk proxy uv build --wheel --offline --out-dir /private/tmp/mediasense-apply-b-final-build

# 单个性能样本；基线将 PYTHONPATH 换为上述 HEAD 的 src
rtk proxy env PYTHONPATH=src .venv/bin/python \
  eval/sessions/260917-1357-apply-b-validation/run.py \
  --case mixed --label B --output /private/tmp/apply-b-mixed.json

# 完整 stdio Host 探针；PYTHONPATH 指向解包后的 wheel
rtk proxy env PYTHONPATH=/private/tmp/mediasense-apply-b-final-wheel .venv/bin/python \
  eval/sessions/260917-1357-apply-b-validation/host_probe.py \
  --output /private/tmp/apply-b-host.json

# 核心回归；全仓默认测试不传文件列表
rtk proxy env PYTHONPATH=src:/private/tmp/mediasense-apply-b-final-wheel \
  .venv/bin/python -m pytest -q tests/test_apply_b_safety.py \
  tests/test_apply_preparation.py tests/test_apply_execution.py \
  tests/test_apply_precheck_integration.py tests/test_mcp_subprocess.py
```

全仓 Geo/Plan 的 loopback HTTP 测试需要相应本机权限；权限问题不能改写为产品通过。测试与基准入口都是已有 Python Tool / MCP stdio，无线上 API。`outputs/` 保留原始日志并被 Git 忽略；媒体、工作数据库和模型输出不进入 Git。Git 仅保留报告、复验配方和紧凑指标。
