---
name: video-anything
description: >-
  One link → everything about a video. Downloads a video from Douyin, Bilibili,
  YouTube, Kuaishou, Twitter/X (and more via yt-dlp), then extracts audio,
  transcribes speech to text locally (Whisper, no API key), and lets the agent
  summarize / rewrite / outline the content. Zero-config and offline: the only
  local tools are yt-dlp + ffmpeg + Whisper; summarization is done by the agent
  itself, so no external LLM key is needed.

  Use this when the user gives a video URL (or share link) and wants to:
  download the video / no-watermark video / audio, get the transcript / 文案 /
  subtitles / 字幕, transcribe / 转文字 / 转录, or summarize / 总结 / 改写 /
  拆分镜 / 提炼要点 / 做笔记 based on a video. Triggers: 视频下载, 无水印, 抖音,
  快手, B站, 视频号, youtube 下载, 视频转文字, 视频文案, 提取字幕, 视频总结,
  video download, download tiktok/douyin, video to text, transcribe video,
  summarize youtube video, get subtitles.
metadata:
  version: 0.1.0
  homepage: https://github.com/CHANGE_ME/video-anything
---

# Video Anything — 基于视频的一切

给一个视频链接,拿到关于这条视频的**一切**:无水印视频、音频、文案(本地 ASR)、字幕、封面、元数据,并由 agent 直接**总结 / 改写 / 拆分镜 / 做笔记**。

**核心设计:零配置、零 key、可离线。** 只用三个本地工具(`yt-dlp` + `ffmpeg` + `whisper`),不需要任何外部 LLM API —— 总结这一步由**你(agent)自己**完成。

## 什么时候用

用户给出一个视频 URL / 分享链接,并想要下列任意一项:
- 下载视频 / 无水印视频 / 只要音频
- 视频转文字(文案 / 口播稿 / transcript)
- 提取平台字幕
- 基于视频内容做总结 / 改写 / 拆分镜 / 提炼要点 / 生成笔记

## 前置检查(第一次使用)

运行一次依赖自检;缺什么按提示装(见 [references/install.md](references/install.md)):

```bash
bash scripts/check.sh
```

## 主流程

给定一个链接 `<URL>`,按顺序执行。**只做用户要的那几步**——例如用户只说「下载」就停在第 1 步,说「要文案」才走到第 3 步。

### 1. 下载视频 + 素材

```bash
bash scripts/fetch.sh "<URL>" ./video-out
```

产出一个目录 `./video-out/<platform>-<id>/`,含:`video.mp4`、`audio.wav`(16k 单声道,供 ASR)、`info.json`(标题/简介/标签/时长/作者等)、`thumbnail.*`(封面)、以及平台自带字幕 `*.vtt`(若有)。脚本会把该目录路径打印在最后一行。

> **无水印**:抖音/快手经由 yt-dlp 的官方 extractor,拿到的通常已是无水印源。平台差异、cookie、反爬见 [references/platforms.md](references/platforms.md)。

### 2. 判断要不要转录

- 若第 1 步已产出平台字幕 `*.vtt`,且用户只要文案 → 直接读 `.vtt`,清洗成纯文本即可,**跳过 ASR**(更快更准)。
- 若无字幕(抖音/快手常见),或用户要精确逐字稿 → 走第 3 步本地 ASR。

### 3. 本地转录(Whisper,无需 key)

```bash
python3 scripts/transcribe.py ./video-out/<platform>-<id>/audio.wav
```

产出同目录下 `transcript.md`(带 `[mm:ss]` 时间戳)和 `transcript.txt`(纯文本)。中文默认用 `small` 模型;长视频或要更准可加 `--model medium`。参数见脚本头部注释。

### 4. 总结 / 改写(你来做,免 key)

读取 `transcript.md` / `transcript.txt` 与 `info.json`,按用户意图产出,并写入同目录 `summary.md`。常见意图:

- **提炼要点**:3–7 条 bullet + 一句话主旨
- **口播稿改写**:改写成用户指定风格的新文案(小红书种草 / 知识拆解 / 播客口播)
- **拆分镜**:按时间戳切成 分镜脚本(镜号 / 时间 / 画面 / 口播)
- **选题矩阵**:基于该视频主题,生成 5–10 个衍生选题 + 标题

> 这一步不调用任何外部模型 —— 你(读到本文件的 agent)就是那个 LLM,直接产出即可。

## 输出目录约定

```
video-out/<platform>-<id>/
├── video.mp4          # 视频本体
├── audio.wav          # 16k 单声道,供 ASR
├── info.json          # 元数据(标题/简介/标签/作者/时长/统计)
├── thumbnail.*        # 封面
├── *.vtt              # 平台自带字幕(若有)
├── transcript.md      # ASR 文案(带时间戳)
├── transcript.txt     # ASR 文案(纯文本)
└── summary.md         # 你产出的总结/改写(按需)
```

## 平台支持

| 平台 | 状态 | 备注 |
|------|------|------|
| YouTube | ✅ 稳 | yt-dlp 原生 |
| Bilibili B站 | ✅ 稳 | 海外 IP 可能需 cookie(412),见 platforms.md |
| Twitter / X | ✅ 稳 | yt-dlp 原生 |
| 抖音 Douyin | ✅ 可用 | 通常无水印;短链先展开 |
| 快手 Kuaishou | ⚠️ 可用 | 偶发失效,反爬 |
| 视频号(微信) | ⛔ 二期 | 封闭生态,yt-dlp 不支持,需客户端抓包,尽力而为 |
| 其他 1800+ 站点 | ➕ | yt-dlp 支持即支持,直接试 |

平台专属处理(短链展开、cookie、无水印、反爬)一律见 [references/platforms.md](references/platforms.md)。

## 注意

- **只下载可公开访问的内容**。不绕过 DRM、付费墙、大会员等版权保护内容。
- 反爬导致的偶发失效是这类工具的通病;失败时先 `yt-dlp -U` 升级再试,再查 platforms.md。
