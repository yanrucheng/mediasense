# 0.8.0 本机安装与旧 Dataset 清理

2026-09-08，用户选择安装新版本后由全新 Agent 从同一批源媒体重新使用服务，
并明确要求清理旧 Dataset 工作区，不恢复原 failed Run。

## 安装结果

- 本次为公开输入/输出合约不兼容变更，按项目 SemVer 惯例从 0.7.2 升至 **0.8.0**。
- 版本、锁文件、当前安装文档、Changelog、四个打包 Skills 的版本线及相应测试同步更新。
- 已离线构建并安装：`dist/mediasense-0.8.0-py3-none-any.whl`。
- wheel SHA-256：`2b6c223b28f52e750575e6221ad59949628ff5cb9b5678a7f0fd49f4633ed686`。
- 本机入口：`/Users/chengyanru/.local/bin/mediasense`，`--version` 返回 `0.8.0`。
- 103 个 wheel 源码/资源文件与仓库及本机安装副本逐字节一致。
- 已升级操作目录 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1/.agents/skills`
  内的四个 MediaSense Skills；再次执行幂等升级全部返回 unchanged。
- 该目录的既有 `.codex/config.toml` 保持不变。按其现有环境启动 doctor 时，Provider 配置可用；
  不读取或输出凭据内容、不发起 Provider 请求。

## 清理结果

清理前逐个核对了 manifest 的来源路径，三个目录均为该香港 fixture 的旧工作区；
未发现进程打开这些目录，且目录内没有符号链接。约 203 MB 旧状态已移到：

`/Users/chengyanru/.Trash/mediasense-old-datasets-20260908.q8RszO/`

| 旧 Dataset 工作区 | 已核对的 source |
| --- | --- |
| `dataset-b9f71c8826d891a534c33b7e` | `…/ai-album-hk-representative-v1/test-260831` |
| `dataset-5cdfb41eb139166f87573dcd` | `…/ai-album-hk-representative-v1/test-260831/260501-HK美食之旅` |
| `dataset-578f3580b10a479628317d8c` | `…/ai-album-hk-representative-v1/dataset/260501-HK美食之旅` |

原 `/Users/chengyanru/Library/Application Support/MediaSense/datasets/` 目录已核实为空，
所以上述旧记录不再参与默认 Dataset 发现或缓存复用。废纸篓尚未清空，可恢复。
源媒体、用户配置、凭据和共享模型保留；没有删除源目录中的历史输出或 fixture 内容。

## 本轮验证

- 版本、Honeycomb 集成与 CLI 针对性测试：**23 passed**。
- Ruff、OpenSpec strict、verify_packet.py、git diff --check：通过。
- 0.8.0 隔离离线安装：`distribution smoke: ok`。
- 本机真实 CLI/stdio MCP：`global CLI smoke: ok`，验证 7 Tool 发现和临时合成数据的启动。
- 当前安装 doctor：资源、ExifTool、FFmpeg、ffprobe 可用；可选本地模型依赖未安装，
  与此前基础安装范围一致。

前一轮 693 项全套验收仍是实现子工作线的证据，本轮版本递增没有重跑全套，未将 23 项重复累加。

## 新 Agent 的起点

从 `/Users/chengyanru/Downloads/ai-album-hk-representative-v1` 启动全新 Agent 会话，
使其加载该目录 0.8.x Skills 和新 MCP 进程；源路径仍用 `test-260831`。
第一次 Dataset open 将在原默认发现目录重新建立工作区；本轮没有预先创建 Dataset 或启动现场 PreCheck。
不继续使用旧 Agent 中已缓存的 0.7.x Tool 形状。用户仍需在新 Run 确认范围及具体外部效果。

旧 Run 没有被恢复，也没有生成新 Result；事故的实际通过结论待这次全新使用验收。
本轮未 commit、push、发布到远端包仓库或 archive OpenSpec change。
