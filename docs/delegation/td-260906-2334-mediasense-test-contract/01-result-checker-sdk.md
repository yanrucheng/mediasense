---
id: "01-result-checker-sdk"
title: "Checker SDK Research Result for MediaSense Test Contract"
type: delegation
status: draft
created: 2026-09-06
updated: 2026-09-06
timezone: "Asia/Shanghai"
parent: "td-260906-2334-mediasense-test-contract"
depends-on:
  - "01-request-checker-sdk"
superseded-by: ""
---

# Checker SDK `make test` 与测试工程准则调研

## 结论摘要

本报告核验的是 Checker SDK 当前 checkout `434e91ab72cbea3b91fd6d9ad8f2204798aea4c5`，不是对历史印象的复述。

1. 当前 `make test` 是一个单层入口：直接运行 pytest 默认集合，并用 pytest-xdist 的 6 个 worker 按测试文件调度。它不依赖 `make check`，也不运行 Ruff、覆盖率、packaging、真实 tokenizer resource、真实 CSV 回归或 benchmark。
2. “默认测试要快”是当前书面目标，但仓库没有“必须低于 10 秒”或更严格数值预算。当前机器 5 次连续、未清缓存、强制离线运行的 wall time 为 `16.08 / 8.75 / 8.75 / 8.64 / 8.80s`：后 4 次稳定在 `8.64–8.80s`，第一轮超过 10 秒。因此“稳定显著低于 10 秒”与现状不符。
3. “400 行”不是“所有文件最好约 400 行”的软建议。它是主包 Python 生产源码的 `<= 400` physical-line 硬门禁，属于默认 pytest；测试、fixture 等不在扫描根内，并有两类受机器校验的例外及一个冻结的历史例外。
4. Checker SDK 没有一份统一的“测试工程圣经”。当前权威分散在 `AGENTS.md`、README、`pyproject.toml`、active OpenSpec 及可执行测试中。高信号、确定性、隔离、诊断和覆盖价值主要由具体合同测试、parity fixture 与治理测试实现；mock、时间依赖和网络并没有一条全仓统一禁令。
5. MediaSense 可采用“一个快速默认入口 + 明确 opt-in 层 + 可复现计时 + 可执行结构门禁”这一组合，但不应照搬固定 6 worker、Checker 专用 marker 或立即对全部源码施加 400 行零存量门禁。当前 MediaSense `src/mediasense` 下已有 32 个 Python 文件超过 400 physical lines，直接照搬会立即全红。

## 调研范围、方法与可复核环境

- Checker SDK 仓库：`/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker`
- Git revision：`434e91ab72cbea3b91fd6d9ad8f2204798aea4c5`
- 调研前后 `git status --short` 均为空；没有修改 Checker SDK 的 tracked 或 untracked 状态。
- 机器：Darwin `25.4.0`，Apple Silicon `Mac17,8`，18 logical CPUs。
- 测试运行时：Python `3.12.7`、uv `0.7.13`、pytest `9.1.1`、pytest-xdist `3.8.0`、GNU Make `3.81`。
- 仓库存在被 `.gitignore` 忽略的 `.env`；依据 [Makefile](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/Makefile:3)，Make 会读取它并只导出三个 `ATQC_OBM_*` 变量。为避免泄露或扩大调查范围，本次未读取其值。
- 所有 pytest 实测都额外设置 `UV_OFFLINE=1`，以保证依赖解析不联网；没有清除 uv、Python、pytest 或操作系统缓存，也没有调用真实外部服务。
- 仓库内没有发现 `.github` workflow、`.gitlab-ci.yml`、`.circleci`、`Jenkinsfile`、`tox.ini` 或 `.coveragerc`。因此本报告只能判断仓库内默认开发入口，不能把未见到的组织级 CI 行为当成当前合同。

## 1. 当前 `make test` 的精确入口与分层

### 默认入口

[Makefile](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/Makefile:1) 将 `test` 声明为 phony target；[Makefile](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/Makefile:20) 定义默认 `TEST_WORKERS ?= 6`；[Makefile](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/Makefile:22) 的完整 recipe 是：

```text
printf "==> project tests\n"
uv run --with pytest --with pytest-xdist python -m pytest -q -n "$(TEST_WORKERS)" --dist loadfile
```

依赖链为：

```text
make test
  -> uv project environment + pytest/pytest-xdist
  -> python -m pytest
  -> pyproject testpaths = ["tests"]
  -> pyproject addopts = -m "not packaging and not tokenizer_resource"
  -> 6 xdist workers, loadfile scheduling
```

`test:` 没有 Make prerequisite，所以不会先跑 `check`、Ruff、类型检查、coverage 或 build。`--dist loadfile` 将同一测试文件的测试放到同一 worker；README 也把它描述为 “six file-isolated workers”，见 [README.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/README.md:32)。worker 数可通过 `TEST_WORKERS` 覆盖。

[pyproject.toml](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/pyproject.toml:120) 是 pytest 默认选择的实现权威：只发现 `tests/`，并默认排除 `packaging` 与 `tokenizer_resource`。当前 collection 共 2,216 个参数化 test item；默认选中 2,186 个，排除 30 个。其中 `packaging` 28 个，`tokenizer_resource` 2 个。

### 默认门禁与显式层

| 层 | 当前入口 | 当前作用 | 是否属于 `make test` |
| --- | --- | --- | --- |
| 默认项目测试 | `make test` | 2,186 个选中 item；功能、合同、parity、布局/源码治理等均通过 pytest 表达 | 是 |
| Contributor authoring | `make check` | 运行 authoring checker，再运行 `test_contract.py`、`test_authoring.py`、`test_compute_metadata_checkers.py`；当前为 487 个生产 checker、2 个 keyword Rule Set、147 个 pytest item | 否；它是 checker contributor 的独立单入口 |
| Packaging | `python -m pytest -q -m packaging` | build/install、wheel/sdist、干净环境、包内资源及离线安装行为；28 个 item | 否；README 要求 release/handoff 前显式运行 |
| 真实 tokenizer resource | `make test-tokenizer-resource` | 真实 tokenizer archive/transformers smoke；2 个 item | 否 |
| DTM pinned upstream strict | `make test-dtm-strict` | 先核对上游 commit、submodule/inventory/provenance，再用 `ATQC_DTM_UPSTREAM_ROOT` 跑 6 个指定测试模块 | 否 |
| 真实本地样本 smoke/regression | `make local-test SAMPLE_CSV=...` | 对外部 QS CSV 跑本地诊断；README 明说是 local/CI smoke，不是 `make test` | 否 |
| Benchmark | `make bench SAMPLE_CSV=...` | 默认 10 warm-up rows、200 measured rows，输出耗时 Top 10 | 否 |
| Golden Standard extraction | `make golden-standard-extract SAMPLE_CSV=...` | 从明确提供的真实 CSV 提取命中 | 否 |

相关 recipe 见 [Makefile](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/Makefile:26)；README 对 packaging、local-test、bench 的定位分别见 [README.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/README.md:43)、[README.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/README.md:70)、[README.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/README.md:119)。

一个容易漏掉的事实是：默认套件当前有 16 个 skip，全部是未设置 `ATQC_DTM_UPSTREAM_ROOT` 时跳过 pinned upstream oracle，机制见 [tests/oracles/upstream_dtm.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/oracles/upstream_dtm.py:60)。所以 `make test` 的“complete default suite”不是 strict upstream parity；后者由 `make test-dtm-strict` 补齐。

## 2. 当前测试准则的权威位置与执行机制

### 权威是分层的，不是一份统一文档

- 默认入口、快速本地循环与显式 packaging 分层：[README.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/README.md:32)。
- 精确 pytest 选择与 marker 定义：[pyproject.toml](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/pyproject.toml:120)。
- contributor 的“加/改匹配测试并跑 `make check`”： [checkers/README.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/bytedance/agent_trajectory_quality_checker/checkers/README.md:7)；`make check` 的能力边界见 [docs/checker-authoring.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/docs/checker-authoring.md:370)。
- 生产源码 400 行治理：[AGENTS.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/AGENTS.md:126) 与 active [checker-authoring-experience spec](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/openspec/specs/checker-authoring-experience/spec.md:245)。
- 各能力应覆盖什么行为：各 active OpenSpec；例如布局迁移要求验证根入口、签名/default、checker 顺序、序列化 schema、action materialization、本地工具入口与包装行为，见 [sdk-layout-governance spec](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/openspec/specs/sdk-layout-governance/spec.md:120)。faithful port 的 parity 还明确要求 positive、negative、threshold、ordering、malformed-input，并比较 exact final JSON、terminal decision、ownership、event order 与 affected indices，见 [tob-volcanic-engine-faithful-checker spec](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/openspec/specs/tob-volcanic-engine-faithful-checker/spec.md:136)。
- 最终可执行机制是 `tests/`；若文档要求未由 target 或测试连接，不能冒充已执行门禁。

### 各项原则的核验结论

| 维度 | 当前合同/实现 | 证据化判断 |
| --- | --- | --- |
| 高信号 | 具体 spec 定义行为类别，测试大量使用精确输出、边界和 parity 断言 | 已形成实践，但没有名为“high-signal tests”的全仓通用条款。代表例是 DTM coverage matrix：要求 227 个 public checker、206 个 reason 的完整对应，并逐项指向真实测试函数，[tests/test_dtm_coverage_matrix.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_dtm_coverage_matrix.py:27)。 |
| 确定性 | 固定 revision/hash、提交的 synthetic/redacted fixture、精确 JSON/order 断言、无随机抽样的默认测试 | 多次运行 item 数和结果一致；但这不是“全仓绝不依赖时间/环境”的书面硬规则。 |
| 隔离 | xdist `loadfile` 文件级调度；广泛使用 `tmp_path` 和 `monkeypatch`；若干 autouse fixture 在每次测试前后清环境和模块缓存 | 例如 OBM 测试删除三个 `ATQC_OBM_*` 环境变量并清缓存，[tests/test_benchmark_contamination_checker.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_benchmark_contamination_checker.py:30)。但 Make 自身仍会读取本地 `.env`，所以入口并非天然完全 hermetic。 |
| 失败诊断 | 描述性 test ID、参数化 case ID、pytest assertion rewriting；子进程检查常把 `stderr` 作为断言消息；authoring checker 汇总具体 checker_id/错误并返回 1 | 例如 import side-effect guard 在失败时回传子进程 stderr，[tests/test_sdk_layout_contract_guards.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_contract_guards.py:763)。但默认 `-q` 没有 `-x`、Junit 报告或统一诊断 schema；失败不会 fail-fast。 |
| 覆盖价值 | 以合同、source inventory、parity matrix 与行为边界为准，而非只计行覆盖 | 当前没有 pytest-cov/coverage 配置或阈值。不能声称 line/branch coverage 是门禁；这里的“覆盖”是可追溯的语义覆盖。 |
| Fixture | active spec 要求 migration parity fixture 使用 synthetic 或 redacted data，禁止真实轨迹、生产记录、local QS 输出、凭据或用户内容，[sdk-layout-governance spec](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/openspec/specs/sdk-layout-governance/spec.md:137) | 80 个顶层测试模块使用 inline fixture、提交的 YAML/JSON fixture 和 pytest `tmp_path`；真实 CSV 流程被放到显式 `local-test`/benchmark 层。 |
| Mock/test double | 没有“必须 mock”或“不得 mock”的统一条款；实现广泛使用 pytest `monkeypatch`，主要替换外部边界、时钟、sleep、环境和缓存 | 例如 placebo timing 注入 `_MONOTONIC` 与 `_SLEEP`，直接断言应 sleep 的值，[tests/test_evaluation_modes.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_evaluation_modes.py:213)。这比等待真实时间稳定，但只是当前实现模式。 |
| 网络 | 多个合同要求默认运行时离线；测试会在隔离子进程中把 socket、URL open、subprocess 或外部依赖替换为立即失败，见 [tests/test_sdk_layout_contract_guards.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_contract_guards.py:706) 和 [tests/test_ark_faithful_source.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_ark_faithful_source.py:95) | 测试体具有很强的“不得意外外联”证据；但 `uv run --with ...` 在依赖未缓存的新机器上仍可能访问 `pyproject.toml` 指定的包索引。因此默认入口本身没有离线硬保证。本次用 `UV_OFFLINE=1` 运行。 |
| 时间 | 主要通过注入时钟/sleep 测试；源码扫描未发现测试直接调用 `time.time`、`monotonic`、`perf_counter`、`datetime.now` 或随机 API | 不是绝对“禁止 sleep”：默认套件有一个 `time.sleep(0.002)`，用于验证 1ms slow-warning 阈值，[tests/test_local_qs_format_regression.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_local_qs_format_regression.py:848)；另有两个 `asyncio.sleep(0)` 仅用于让出 event loop。 |

## 3. 400 physical-line 规则

### 准确规则

当前规则是：主包生产源码 `bytedance/agent_trajectory_quality_checker/**/*.py` 必须不超过 400 physical lines；`400` 合规，`401` 违规。文字权威见 [AGENTS.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/AGENTS.md:126)；active spec 使用 SHALL/THEN 规定超过前应按 source/domain responsibility 拆分，见 [checker-authoring-experience spec](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/openspec/specs/checker-authoring-experience/spec.md:263)。

这不是仅供 review 参考的 heuristic。默认 `make test` 会收集 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:55)，该测试要求 `_main_source_line_issues(...) == []`，因此违规会使默认 pytest 与 Make 以非零状态失败。

### 计算与作用域

- 常量：`MAX_MAIN_SOURCE_LINES = 400`，见 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:9)。
- 扫描：`PACKAGE_ROOT.rglob("*.py")`。
- 计数：`len(path.read_text(encoding="utf-8").splitlines())`，即 physical lines，不是 Ruff/Cloc 的逻辑代码行，见 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:103)。
- 文本规则明确排除 tests、fixtures、evals、benchmarks、generated/vendor、build/cache、venv 与 archived files，见 [AGENTS.md](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/AGENTS.md:128)。当前可执行扫描本身没有这些通用目录判断：它只是从主包根递归扫描 `.py`，再应用下述三类具体例外；当前这些排除对象通常位于主包外或由 provenance 机制覆盖。当前 `tests/` 下有 28 个 Python 文件超过 400 行，证明仓库测试文件不属于门禁对象；反过来，若把生成或 benchmark Python 文件放进主包，单凭目录名称并不会自动豁免。
- 实现按当前文件树扫描，不要求文件已被 Git tracked；放入主包的 untracked `.py` 也会被扫到。

### 受治理的例外

1. **Manifest-tracked faithful source**：只允许在 family 的 `faithful_source/` 下；package-local provenance 必须给出 upstream path/revision、upstream/local SHA-256、ported symbols、adaptations 与 scope。测试还校验文件存在、hash、符号和路径安全，见 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:130) 与 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:276)。同目录中未被 manifest 跟踪的 adapter 仍违规；测试明确证明 401 行 adapter 报 `401 (untracked faithful source)`，见 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:82)。
2. **Registered pure declarative keyword catalog**：只有固定登记的两个 `rules.py` 可以例外，且 AST 校验要求唯一 public `RULE_SET`、显式 include/exclude、无函数、类、循环、条件、comprehension、I/O 或其他执行行为，见 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:580)。当前唯一非-`faithful_source` 超限生产文件是 459 行的 `requirement_drift/rules.py`，符合此例外。
3. **历史冻结例外**：`merge_production_checker/faithful/source` 是 manifest 合同前的 legacy copied root；代码注释明确要求不要新增这种 root，见 [tests/test_sdk_layout_governance.py](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/tests/test_sdk_layout_governance.py:20)。

因此更准确的表述不是“单个文件最好约 400 行”，而是“普通手写主包 Python 生产源码 400 physical lines 是默认测试硬上限；测试等不适用，例外必须满足机器可验证的窄条件”。

## 4. 默认测试耗时实测

### 是否存在 10 秒合同

不存在。当前 README 只说默认排除 packaging smoke “so the local loop stays fast”，没有任何数值 SLO、timeout 或性能失败门禁；Makefile 也没有耗时判断。`SLOW_WARN_SECONDS ?= 1.0` 只属于 `local-test`/Golden Standard 的单 checker 诊断参数，不是 `make test` 总预算，见 [Makefile](/Users/chengyanru/repos/work-aids/06-agent/agent-trajectory-quality-checker/Makefile:10)。

### 可复现测量

命令（连续 5 次、同一 checkout、不清缓存）：

```text
rtk proxy env UV_OFFLINE=1 /usr/bin/time -p make test
```

| Run | pytest 汇报 | wall `real` | 结果 |
| ---: | ---: | ---: | --- |
| 1 | 15.59s | 16.08s | 2170 passed, 16 skipped |
| 2 | 8.38s | 8.75s | 同上 |
| 3 | 8.45s | 8.75s | 同上 |
| 4 | 8.29s | 8.64s | 同上 |
| 5 | 8.50s | 8.80s | 同上 |

- 5 次 wall median：`8.75s`；全区间 `8.64–16.08s`。
- 后 4 次暖态 wall 区间：`8.64–8.80s`，median `8.75s`。
- 额外一次带 `-rs --durations=20` 的诊断运行：`2170 passed, 16 skipped in 8.62s`；最慢单项约 `2.37s`。
- 串行对照 `UV_OFFLINE=1 make test TEST_WORKERS=0`：同样 `2170 passed, 16 skipped, 30 deselected`，pytest 汇报 `28.79s`。

结论：当前实现的暖态通常低于 10 秒，6 worker 在此机上相对串行约快 3.3 倍；但第一次被测运行为 16.08 秒，而且没有数值合同。因此不能把“低于 10 秒，更不能把显著低于 10 秒”写成 Checker SDK 当前保证。

## 5. 保持快速的设计：已验证事实与推断

### 已验证事实

- 默认选择只看 `tests/`，不会发现主包内上游 faithful-source 自带的测试。
- 30 个 packaging/tokenizer item 被 marker 排除；真实 CSV、benchmark、严格上游 oracle 是独立入口。
- 6 个 xdist worker + `loadfile` 带来实测加速：约 `28.79s -> 8.7s`。
- fixture 主要是提交的 synthetic/redacted 小样本、inline 数据和 `tmp_path`；真实数据工作流不进默认集合。
- 时间通常通过可注入边界测试；只有一个 2ms 实际 sleep 与两个 event-loop yield。
- 默认不做 wheel/sdist 构建、真实 tokenizer 加载、Ruff、类型检查或 coverage。
- 默认没有 `-x`；它追求一次给出完整失败面，不靠 fail-fast 缩短失败路径。
- 暖态明显快于第一轮，说明当前体验会受 import、文件系统和 uv/Python 缓存状态影响。未清缓存是本次测量条件，不应把暖态数字外推为冷启动保证。

### 有证据支持但仍属于推断

- `loadfile` 很可能兼顾速度和共享模块状态/fixture 的隔离；README 只明确说 file-isolated workers，没有记录更细的选型实验。
- 大量 exact parity、hash、inventory 和 schema 测试以小输入获得较高回归信号，是 2,000+ item 仍能在暖态约 9 秒完成的重要原因；仓库没有量化每种实践的独立贡献。
- 没有全局 network blocker plugin；只能确认有若干专门测试主动封锁外部副作用，不能把它提升成所有未来测试天然无法联网的机制。

## 6. 可迁移原则与 Checker SDK 专属实现

### 可直接作为跨项目原则

1. 一个稳定、易记、非交互的默认开发入口，成功/失败由进程退出码表达。
2. 默认层只包含本地、确定性、高反馈价值检查；真实数据、真实模型/网络、打包安装、规模与 benchmark 显式分层。
3. marker 的名字、语义、默认选择与显式运行命令必须同时写入配置和入口文档。
4. 用小型 synthetic/redacted fixture 覆盖正例、反例、阈值、顺序、 malformed input 与失败语义；真实数据用于独立 validation，不替代单元/合同测试。
5. mock/test double 用在时间、网络、环境、文件系统和重依赖边界，并断言调用与结果；不要让比生产 port 更宽松的 fake 掩盖组合错误。
6. 覆盖价值以需求、风险、状态转移和跨组件边为单位追踪；代码覆盖率可以补充，但不应替代语义矩阵。
7. 快速预算必须带参考机器、冷/暖状态、selected/deselected/skipped 数和多次分布；不能只记录一次最好成绩。
8. 结构规则若重要，应由默认测试机器执行，并让失败信息包含文件、当前值和允许值。

### 不应照搬为通用规则的项目细节

- Python/uv/pytest/pytest-xdist、固定 6 worker 和 `loadfile` 调度。
- `packaging`、`tokenizer_resource`、DTM strict、OBM、QS CSV 等 marker/target 与环境变量。
- Checker 的 400 精确数值、`faithful_source` provenance schema、两个特定 keyword catalog 和遗留 copied-root 例外。
- 487 checker 的 authoring probe、227/206 DTM coverage matrix、特定 revision/hash parity。
- “默认不含 Ruff/coverage”是当前实现事实，不是值得跨项目复制的原则。

## 7. MediaSense 最小候选合同（供后续评审，不是本次变更）

MediaSense 当前 [pyproject.toml](/Users/chengyanru/repos/personal/mediasense/pyproject.toml:28) 已有 pytest 与 Ruff；[pyproject.toml](/Users/chengyanru/repos/personal/mediasense/pyproject.toml:43) 已将 `local_fixture` 与 `scale` 默认排除。建议最小候选如下。

### 默认入口与分层

```text
make test
  -> uv run ruff check .
  -> uv run pytest -q
```

这里让 `pyproject.toml` 继续作为 marker 选择的单一权威，不在 Makefile 重复 `-m` 表达式。默认层应覆盖纯本地 unit、contract、schema、状态/失败语义、composition/Host 的零副作用或安全有界 vertical test；不得需要外部 fixture、网络、付费模型、真实媒体目录或长规模生成。

显式层建议保留最少三个入口：

- `make test-local-fixture`：只跑 `-m local_fixture`，由调用者提供 fixture 路径；不得成为默认成功的隐式前提。
- `make test-scale`：只跑 `-m scale`，单独记录规模、资源和耗时。
- packaging/installed-artifact smoke：若 MediaSense 后续建立发布门禁，再作为独立 release target；不要为了入口对称提前创建没有实际责任的 target。

pytest-xdist 不应因 Checker 使用 6 worker 就直接加入。先比较 serial 与 2/4/6 worker；MediaSense 当前存在 2,000 行级单个测试模块，`loadfile` 可能造成 worker 尾部不均衡。只有在实测提升且没有共享状态竞态后再固定策略。

### 候选耗时预算

- 将“参考开发机上连续 5 次暖态 wall median `<= 10s`”作为第一版明确 SLO；更理想目标为 `<= 5s`，但在基线未知前不应伪装成现有能力。
- 同时记录 warm max 与一次不清理用户缓存的首轮值；建议先以告警/趋势回归治理，不把跨机器 wall-clock 直接做脆弱的 pytest 硬失败。
- 若基线已超过 10 秒，先按 slowest test 与层级拆分，设置“不继续恶化”的 ratchet，再逐步收紧；不能通过隐藏必要测试或把普通回归随意标成 slow 来达标。
- 默认运行出现 skip 时必须在 `-ra` 摘要中可见；对本应满足的本地依赖，unexpected skip 应失败，而不是成为绿色门禁中的永久空洞。

### 候选文件大小规则

- 对普通手写 `src/mediasense/**/*.py` 采用 `<= 400 physical lines` 的硬上限是可讨论的目标；测试、fixture、生成物与第三方 vendored source 不自动共享这个数值。
- 不应立即对当前全树启用零例外门禁：只读扫描显示 83 个生产 Python 文件中已有 32 个超过 400 行，最大为 `src/mediasense/apply/preparation.py` 的 2,490 行。立即照搬只会制造常红门禁。
- 最小落地方式应是机器可验证的 baseline ratchet：禁止新增超限文件、禁止已登记超限文件继续增长，并在正常职责拆分时逐项消除存量。不要把“本次没空拆”作为永久例外。
- 真正例外只允许可审计类别，例如生成文件（有 generator/source/hash）或外部保真源码（有 revision/path/hash/scope）；MediaSense 自己的 adapter、orchestrator、state machine、filesystem safety 与 evidence formatting 不应因邻近外部代码而豁免。
- 违规输出至少包含文件路径、physical line count、阈值与未满足的例外条件；计数算法应固定并测试边界 `400 pass / 401 fail`。

### 在冻结合同前先测的 MediaSense 基线

1. 固定一个 commit 和参考机器，记录 Python、uv、pytest、Ruff 版本。
2. `pytest --collect-only` 记录默认、`local_fixture`、`scale` 的 selected/deselected/skipped 数，确认 marker 没有漏标。
3. 分别测 Ruff、默认 pytest 串行，以及候选并行度 2/4/6；每种做 1 次首轮 + 5 次连续暖态，不清缓存，不删除失败样本。
4. 用 `--durations` 查最长测试，审计真实 sleep、网络、模型、外部路径、全局环境和跨测试缓存；将它们改造成注入边界或移入显式层之前，不先写不真实的“离线/10 秒”保证。
5. 建立需求/风险到测试的最小矩阵，优先覆盖 foundation 要求的 material cross-stage edge、异常传播、source-read-only、authorization、journaling/idempotency 与 post-verification；不要用 line coverage 百分比代替这些证明。

## 最终判断

MediaSense 最值得采用的不是 Checker SDK 的具体命令，而是三件事：默认路径有清晰边界、慢/外部工作显式分层、重要结构规则由测试执行。Checker 的“400 行”当前确为硬门禁；“10 秒”则不是合同，且当前只在暖态勉强低于 10 秒。MediaSense 若采纳，应把耗时写成带测量条件的自身 SLO，并用存量 ratchet 处理现有 32 个超限生产文件，而不是宣称已满足一个未经基线验证的数字。
