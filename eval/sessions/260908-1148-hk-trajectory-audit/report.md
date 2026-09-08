---
title: "香港数据运行轨迹审计"
service_version: "MediaSense 0.8.0"
date: 2026-09-08
environment: "local macOS; read-only retrospective audit"
model_id: "gpt-6-astra; high"
dataset_version: "ai-album-hk-representative-v1/test-260831"
purpose: "复核 PreCheck/Plan 压缩收益、额外调用和历史答案暴露"
baseline_ref: "eval-260823-1918-ai-album-migration-baseline"
---

# 会话复核入口

结论的唯一维护位置是[正式审计报告](../../../docs/eval/eval-260908-1148-hk-trajectory-audit.md)。本目录保存只读复核脚本和精简指标，不保存原始媒体、图像、会话正文或数据库副本。

- 运行：`rtk proxy python3 eval/sessions/260908-1148-hk-trajectory-audit/run.py`。
- 输出：stdout JSON；已保存的审计摘要见 [metrics/combined.json](metrics/combined.json)。脚本没有文件写入、模型推理或网络请求。
- 来源：`/Users/chengyanru/Downloads/ai-album-hk-representative-v1/test-260831`。
- Runtime workspace：`/Users/chengyanru/Library/Application Support/MediaSense/datasets/dataset-b9f71c8826d891a534c33b7e`。
- 原始轨迹：`/Users/chengyanru/.codex/sessions/2026/09/08`，四个精确文件及 SHA-256 见指标文件。
- API endpoint：被审计对象使用本地 MediaSense MCP；审计仅检查本地 provider journal，不调用 Google、高德或模型 gateway。没有可用的独立费用账单。
- 审计源码 HEAD：`a9ba4a0908510e8594b1d6afb04dad02f78830c8`；安装 wheel 未记录 build commit，正式报告说明源码一致性核对边界。
- 原始 artifacts 均为 local-only。缺少原始日志、封存 Result 或数据库时无法完整复算，不应改用另一运行的数据。
- 包 verifier 的全局大小检查失败，清单内 SHA-256 检查通过；实际来源的 2,134 个 manifest 媒体另行逐个完整 SHA-256 比对通过。详细适用范围见正式报告。

本目录处于 finalized 状态；它记录一次审计，不改变 MediaSense 的默认配置和执行行为。
