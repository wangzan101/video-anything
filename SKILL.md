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
  homepage: https://github.com/wangzan101/video-anything
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

**首次使用这个 skill,先跑一次:**

```bash
bash scripts/check.sh
```

`check.sh` 会自检 `yt-dlp` / `ffmpeg` / 本地 ASR 是否就绪;**缺依赖会自动跑 `bootstrap.sh` 补装**,无需手动安装。装不上才需要手动看 [references/install.md](references/install.md)。之后再用不用重复跑。

## 主流程

首次使用请先完成上面的「前置检查」。给定一个链接 `<URL>`,按顺序执行下面几步。**只做用户要的那几步**——例如用户只说「下载」就停在第 1 步,说「要文案」才走到第 3 步。

### 1. 下载视频 + 素材

```bash
bash scripts/fetch.sh "<URL>" ./video-out
```

产出一个目录 `./video-out/<platform>-<id>/`,含:`video.mp4`、`audio.wav`(16k 单声道,供 ASR)、`info.json`(标题/简介/标签/时长/作者等)、`thumbnail.*`(封面)、以及平台自带字幕 `*.vtt`(若有)。脚本会把该目录路径打印在最后一行。

> **无水印**:抖音/快手经由 yt-dlp 的官方 extractor,拿到的通常已是无水印源。平台差异、cookie、反爬见 [references/platforms.md](references/platforms.md)。

### 2. 判断要不要转录

`fetch.sh` 只下载**人工字幕**(不下自动生成字幕,spec 从不信自动字幕),据此决定是否跳过 ASR:
- 若第 1 步已产出 `sub.*.vtt` (存在即人工字幕),且用户只要文案 → 直接读 `.vtt`,清洗成纯文本即可,**跳过 ASR**(更快更准)。
- 若没有 `sub.*.vtt`(该平台无字幕,或未命中 `--sub-langs` 里的语言;抖音/快手常见无字幕),或用户要精确逐字稿 → 走第 3 步本地 ASR。
- 防御性二次校验:`scripts/lib/asr_utils.py::is_manual_subtitle()` 可用于按文件名再次确认某个 `.vtt` 不是自动字幕(正常流程不应触发,仅作兜底)。

### 3. 本地转录(Whisper,无需 key)

```bash
python3 scripts/transcribe.py ./video-out/<platform>-<id>/audio.wav
```

产出同目录下 `transcript.md`(带 `[mm:ss]` 时间戳)和 `transcript.txt`(纯文本)。中文默认用 `small` 模型;长视频或要更准可加 `--model medium`。参数见脚本头部注释。

### 4. 总结 / 改写(你来做,免 key)

读取 `transcript.md` / `transcript.txt` 与 `info.json`,按用户意图产出,写入同目录 `summary.md`。这一步不调用任何外部模型 —— 你(读到本文件的 agent)就是那个 LLM,直接产出即可。

用户常见意图里,目前「提炼要点」「口播稿改写」有完整 playbook(下面展开);「拆分镜」「选题矩阵」留到之后的版本,这里先不展开写法,遇到了按你的判断直接产出即可。

#### 提炼要点(playbook)

当用户想要「总结 / 提炼要点 / 划重点」时,按这几步做:

1. 读 `transcript.md`(逐句 `` `[MM:SS]` `` 时间戳 + 原文)和 `info.json`(取 `title`/`description` 帮助判断主题、`duration` 帮助判断详略程度)。
2. 写**一句话主旨**:概括这条视频整体在讲什么/传达什么,不要罗列多个点,提炼出共同的核心。
3. 提炼 **3–7 条要点**,每条要求:
   - 是一个独立的信息点,由你归纳/合并原文,**不是逐句翻译或摘抄**;
   - 句尾尽量带该信息点在 transcript 中**最早出现**的 `[MM:SS]` 出处,方便用户回看原片核对;
   - 极少数确实找不到明确对应时间点的内容(比如纯开场寒暄)可以不带,但整体应以带时间戳为主。
4. 如果原文里有态度鲜明的总结句/金句,末尾加一节「一句话金句」,**原话直引**(可加时间戳),不要转述;没有明显金句就省略这一节。
5. 按下面的结构写入 `summary.md`:

   ```markdown
   # {info.json 里的 title}

   ## 主旨
   一句话。

   ## 要点
   - 要点一 [MM:SS]
   - 要点二 [MM:SS]

   ## 一句话金句(可选,没有就省略这节)
   > "原话" [MM:SS]
   ```

完整的输入/输出对照(真实感示例 transcript → 期望的 summary.md)见黄金样例 [references/examples/key-points.md](references/examples/key-points.md),下笔前先看一眼,校准颗粒度和风格。

#### 口播稿改写(playbook)

当用户想要把原视频「改写成另一种风格的口播稿」(而不是提炼要点)时,按这几步做:

1. **读素材**:`transcript.md`(逐句 `` `[MM:SS]` `` 时间戳 + 原文)和 `info.json`(取 `title`/`description` 辅助判断主题,`duration` 参考原片节奏)。
2. **先确认目标风格**——这是硬性前置步骤,不要跳过。如果用户已经指定风格(或给出自定义风格描述),直接按其要求写;如果没指定,向用户确认想要哪一种。内置 3 种预设风格:
   - **小红书种草**:第一人称、有钩子开头、口语化、emoji 适度、结尾引导互动/收藏;
   - **知识拆解**:结构化、分点、先给结论再展开,适合"3 分钟讲清 X";
   - **播客口播**:自然对话感、有过渡句、可以更长,像在跟听众聊天。
   用户也可以给一个自定义风格描述(比如"某博主的口吻"),按其描述改写。
3. **改写,不是照抄**:基于 transcript 提炼出的核心信息与观点,用目标风格的语言、结构、节奏**重新组织表达**——这是重写一份新口播稿,不是逐句翻译或摘抄原文的措辞。
4. **硬约束,不可违反**:**不编造原视频没有的事实/数据**;原文没提到的细节、数字、结论一律不补;不确定的地方宁可略去,也不要靠"合理推测"补全。
5. **按平台调整时长/节奏**:小红书种草通常更短更快(适合压缩到原视频信息量的核心部分),播客口播可以更长、更松弛,知识拆解视信息量而定,但都应完整覆盖原视频的核心信息和观点,不能因为改写而丢失原意。
6. **语言**:除非用户明确要求其它语言,默认输出中文。
7. 按下面的结构写入 `summary.md`:

   ```markdown
   # {info.json 里的 title}

   ## 风格:{小红书种草 / 知识拆解 / 播客口播 / 自定义风格名}

   {改写后的完整口播稿,可含分段/小标题}

   > 适用平台/时长建议:一句话(可选,没有明显建议就省略)
   ```

完整的输入/输出对照(同一段真实感示例 transcript → 3 种风格各一版改写)见黄金样例 [references/examples/rewrite.md](references/examples/rewrite.md),下笔前先看一眼,校准每种风格的差异度和忠于原素材的边界。

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
