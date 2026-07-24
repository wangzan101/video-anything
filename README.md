<div align="center">

# 🎬 video-anything

### 面向 Agent 的视频下载、转录与内容处理 Skill

把公开可访问的视频 URL 交给支持 [Agent Skills](https://agentskills.io) 的工具，完成下载、音频抽取、转录和后续内容整理。

[English](README.en.md) · **简体中文** · [下载契约](docs/superpowers/specs/2026-07-24-video-download-contract.md)

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-开放标准-6b46c1)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

> 当前重点是把“URL → 可验证下载产物”做成可靠地基。平台状态仍以真实 smoke 证据为准；不能把目录存在、yt-dlp 支持站点列表或一次偶然成功当成稳定支持。

## 能做什么

- 使用 yt-dlp 下载单个公开视频，不处理播放列表、直播、DRM、付费墙或会员内容。
- 用 ffmpeg/ffprobe 验证媒体，而不是靠文件扩展名判断成功。
- 成功时发布 `video.mp4`、`audio.wav`、`info.json`、`manifest.json` 和 `fetch.log`。
- 默认复用经过重新验证的 final；`--force` 在新结果验证完成前保留旧结果。
- 通过本地 Whisper/其他已配置 ASR 方案进行转录，再由你的 Agent 做摘要、改写或选题整理。

AI 改写和总结由调用它的 Agent 完成，本项目不要求 OpenAI、Anthropic 或其他 LLM API key。

## 当前状态

下载核心已经完成离线契约、真实媒体本地集成和默认 CI；真实平台 smoke 仍是独立的 release/nightly 门禁。

| 平台 | 当前等级 | 说明 |
|---|---|---|
| YouTube、Bilibili、Twitter/X | provisional | 需要按记录的公开 fixture 复测；YouTube 还依赖 JS runtime |
| Douyin | provisional | 短链、登录和反爬条件需要单独 smoke |
| Kuaishou | experimental | 不承诺固定 extractor 或无水印结果 |
| WeChat Channels | unsupported | 不在当前 v1 支持范围 |
| 其他 yt-dlp 站点 | experimental | upstream 支持不等于本项目 READY 证据 |

## 安装

```bash
git clone https://github.com/wangzan101/video-anything ~/.claude/skills/video-anything
cd ~/.claude/skills/video-anything
```

运行时需要 Python 3、yt-dlp、ffmpeg 和 ffprobe。可以先检查：

```bash
bash scripts/check.sh
```

`scripts/bootstrap.sh` 可将 yt-dlp、ffmpeg/ffprobe 和 Deno（默认 runtime 策略）放入独立的 `VA_HOME`。支持矩阵为：

- macOS 10.15+：x86_64、arm64
- Linux glibc 2.17+：x86_64、aarch64；WSL 按实际 Linux 环境判断
- musl、Linux armv7l、原生 Windows：unsupported

YouTube JS runtime：

```bash
export VA_YTDLP_JS_RUNTIME=auto   # 默认，优先受控 Deno >=2.3
# deno：显式使用 Deno >=2.3
# node：仅显式选择 Node >=22，项目不会安装 Node
# none：禁用 JS runtime；不代表 YouTube capability ready
```

更多安装说明见 [`references/install.md`](references/install.md)。

## 直接使用下载器

```bash
bash scripts/fetch.sh "https://example.com/video" ./video-out
```

强制重新生成：

```bash
bash scripts/fetch.sh "https://example.com/video" ./video-out --force
```

成功时 stdout 只输出最终目录路径；失败时 stdout 为空，详细原因写入 stderr。固定退出码：

| 码 | 含义 |
|---:|---|
| 0 | READY |
| 2 | 参数或 URL 错误 |
| 10 | 依赖、宿主或 JS runtime 不可用 |
| 20 | URL 解析失败、播放列表或直播 |
| 30 | 下载失败 |
| 40 | 无法得到真实兼容 MP4 |
| 50 | 视频、JSON、音频或时长校验失败 |
| 60 | 锁、发布或恢复冲突 |

成功目录：

```text
video-out/<extractor>-<id>/
├── video.mp4       # 可解析 MP4；优先 H.264/AAC
├── audio.wav       # PCM WAV、16 kHz、单声道
├── info.json       # 与 extractor/id 一致的元数据
├── manifest.json   # status=ready、校验结果和 provenance
└── fetch.log       # 脱敏诊断日志
```

封面和人工字幕属于可选资产。失败 staging、journal、backup 位于输出根目录下的隐藏事务目录中，用于诊断和恢复，不应直接交给下游 Agent。

## 在 Agent 中使用

安装 Skill 后，可以直接提出类似请求：

- “下载这个公开视频并验证产物。”
- “把已经下载的音频转成带时间戳的中文文案。”
- “根据 transcript 提炼要点，再改写成小红书口播稿。”

Skill 的操作边界和下游流程见 [`SKILL.md`](SKILL.md)。

## 测试与 CI

本地离线测试不访问网络：

```bash
python -m pytest -q
bash -n scripts/*.sh tests/smoke.sh
git diff --check
```

真实媒体集成使用本机 ffmpeg/ffprobe。平台 smoke 是显式运行的 release/nightly 检查：

```bash
bash tests/smoke.sh --platform youtube --url "<public-fixture-url>"
```

仓库不内置 URL、cookie 或私密 fixture；smoke 报告只保存 URL hash 和脱敏诊断。每个平台达到“两条公开 fixture、各连续三次 READY”后，才可以把状态升级为 `supported`。

## 边界与许可

仅处理你有权访问的公开内容。不绕过 DRM、付费墙、登录限制或平台安全措施。项目采用 MIT License，见 [`LICENSE`](LICENSE)。
