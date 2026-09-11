## 1. Decisions, profile and contract

- [x] 1.1 Record delegated implementation authority, baseline profiling, decoder prototype, selected methods and fixed acceptance budgets.
- [x] 1.2 Clarify requested versus observed frame position and operating-quality semantics in current Run/Read contracts; synchronize schemas and add boundary checks.

## 2. Metadata coordination and resource use

- [x] 2.1 Add scoped thread-local connection reuse without holding transactions across provider work; prove thread/transaction isolation.
- [x] 2.2 Batch lease renewal and bound renewal work while preserving expiry, cancellation, sibling success and immediate recovery semantics.
- [x] 2.3 Restore resource-bounded ExifTool concurrency with run-local reuse, version identity and deterministic shutdown.
- [x] 2.4 Verify full-profile observations and first/reuse budgets against the fixed local fixture.

## 3. Video preparation and evidence

- [x] 3.1 Add a replaceable local decoder port and PyAV adapter with real PTS, bounded threads/work, source-read-only access and cancellation.
- [x] 3.2 Batch per-video frame preparation, keep individual Work/Artifact outcomes, prepare middle targets for short videos and deduplicate actual frames.
- [x] 3.3 Project requested/observed positions and actual producer into frame/contact-sheet evidence; preserve historical values and selective reuse.
- [x] 3.4 Verify valid/invalid/short/sparse/VFR cases, recovered843-frame coverage and fixed performance/reuse budgets.

## 4. Integration and delivery

- [x] 4.1 Run focused semantic/resource/recovery checks and the full default suite; resolve introduced failures without weakening contracts.
- [x] 4.2 Build and verify an isolated wheel with real installed Run/Read video execution and synchronized resources/dependencies.
- [x] 4.3 Publish after-measurements, source-integrity verification and scope-limited migration judgments; close tasks only with their actual evidence.

## Completion evidence (2026-09-12)

- [联合验收报告](../../../eval/sessions/260911-2128-precheck-throughput-recovery/report.md)和[固定输入/实际指标](../../../eval/sessions/260911-2128-precheck-throughput-recovery/metrics/combined.json)：正式metadata首次15.708 s、复用3.992 s；同4通道EXIF中位3.450 s；843同目标帧中位28.217 s；默认视频含联系表22.478 s、复用6.928 s。
- 输出与边界：2,134项metadata观察相同，843不同PTS帧/0采样器失败/1真实坏probe；2,142源文件不变；选择范围仍281来源（99图像/182视频），其视频实际540帧。
- 测试：1,109个默认case经全量执行及5个失败case的环境/副本修复复核通过；16个默认排除的local_fixture/scale用例未冒称运行。[检查记录](../../../eval/sessions/260911-2128-precheck-throughput-recovery/metrics/checks.json)
- 真实隔离安装Host公开Run/Read生成5帧/2联系表，后继Run无新提取且旧Result不变；wheel与源码和全部schema副本一致，SHA-256 b4a16a8f10513896f8f24d3d39529f3fa5237a6a905f687859bbf632f9ed731f。
- 当前Run/Read为唯一产品合约；秒数、输入/版本和认证限制留在验收/评测。本次完成不代表全局Host已升级，也不认证长码流、RAW、外置盘、模型质量或厂商规则能力。
