<div align="center">

# 🎬 video-anything

### 粘一个链接 → 关于这条视频的*一切*

下载、转文案、AI 改写口播稿 —— 在任意 AI 工具里，**零 API key、零手动安装、本地搞定**。下载契约正在加固中，Phase4 门禁前不要只凭目录存在判断成功。

[English](README.en.md) · **简体中文**

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-开放标准-6b46c1)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![stars](https://img.shields.io/github/stars/wangzan101/video-anything?style=social)](https://github.com/wangzan101/video-anything)

</div>

<!-- TODO: 录一个 15s demo GIF 放这里 —— 粘抖音链接 → 出无水印视频 + 文案 + 小红书改写。这是转化率最高的一块。 -->
<p align="center"><img src="docs/demo.gif" alt="演示" width="720"></p>

---

## 为什么做这个

`yt-dlp` 只会**下载** —— 它不转文案，也不理解内容。
那些付费的「视频文案提取」站**能**做到 —— 但闭源、收费，而且只给你一段文字。

**`video-anything` 把整条链做成一个 skill：** `下载 → 本地转文案 → agent 自己改写/总结`。
不需要任何外部大模型 key —— 因为**读到这个 skill 的 agent 本身就是那个 LLM**。

## 粘一个链接，全都有

| | |
|---|---|
| 📹 **视频本体** | 抖音 / 快手 拿到的是无水印源 |
| 🎧 **音频** | 16k 单声道，可直接喂 ASR |
| 📝 **文案 / transcript** | 本地 Whisper，带时间戳 |
| 💬 **字幕** | 平台自带字幕(只信人工字幕) |
| 🖼️ **封面** + 🏷️ **元数据** | 标题、简介、标签、作者、数据 |
| ✨ **AI 改写 / 总结** | 由**你的 agent** 完成，免 key |

## ✨ yt-dlp 做不到的那半条

把文案丢进内置 **playbook**，agent 直接产出能发的稿子：

- **提炼要点** —— 一句话主旨 + 3–7 条带时间戳的要点
- **口播稿改写** —— 一键改写成 **小红书种草 / 知识拆解 / 播客口播**(或你自定义的风格)，并带**「不编造」硬约束**

<details>
<summary><b>看效果(口播改写 → 小红书种草)</b></summary>

> **输入**(原始文案)：`[00:03] 我做自由职业三年了,前两年天天被拖延症折磨…`
> **输出**(小红书风格)：`真的会哭死,自由职业三年,前两年天天被拖延症拿捏😭 后来才想明白,根本不是意志力不够,是"开始"这个动作太难了…`

完整 3 风格对照见 [`references/examples/rewrite.md`](references/examples/rewrite.md)

</details>

## 在你自己的 AI 工具里就能用

基于 [Agent Skills 开放标准](https://agentskills.io) —— **一次写好，处处调用**：Claude Code · Cursor · OpenAI Codex · GitHub Copilot · Gemini CLI · 以及 40+ 个 agent 工具。

## 安装

**1. 装上 skill**(放到你的 agent 找 skill 的目录):

```bash
git clone https://github.com/wangzan101/video-anything ~/.claude/skills/video-anything
# Cursor / Codex 等也会扫 .claude/skills、.cursor/skills、.agents/skills
```

**2. 没了。** 不用 `brew install`、不用手动配环境。首次使用时 skill 会**自动就位**自己需要的工具(`yt-dlp` + `ffmpeg` + 本地 Whisper)到 `~/.video-anything/`，**不污染你的系统**。

> 想先自检 / 预装? `bash scripts/check.sh`。详情见 [`references/install.md`](references/install.md)。

## 怎么用

直接跟你的 agent 说话，它会自己挑要执行的步骤；下载契约是目标 contract，见 [`docs/superpowers/specs/2026-07-24-video-download-contract.md`](docs/superpowers/specs/2026-07-24-video-download-contract.md)：

- *"下载这个抖音视频,要无水印"*
- *"把这个 B 站视频转成文案"*
- *"总结这个 YouTube 视频的要点,再改写成小红书口播稿"*

<details>
<summary>底层实际跑的命令</summary>

```bash
bash scripts/fetch.sh "<URL>" ./video-out                  # 下载 + 素材（目标 contract 后续会补齐 manifest）
python3 scripts/transcribe.py ./video-out/<extractor>-<id>/audio.wav   # 本地转文案
# → agent 读文案,按 playbook 写出 summary.md
```
</details>

`fetch.sh` 的目标 contract 是在 `video.mp4`、`audio.wav`、`info.json`、`manifest.json` 都验证通过后才会发布 final；Phase4 门禁前不要仅凭当前目录判断成功，失败时 stdout 仍应为空。

## 工作原理

```
链接 ─► 识别平台 ─► yt-dlp(视频 + 人工字幕 + 封面 + 元数据)
      └► ffmpeg → 16k 音频 ─► 有人工字幕? ── 有 ─► 直接用(跳过 ASR)
                                          └─ 无 ─► 本地 Whisper → 文案
      └► agent 跑 playbook ─► summary.md  (全程免 key)
```

## 平台支持

> 以下状态是 Phase 0 临时校准，等待新的 download foundation smoke 通过后再升级。

| 平台 | 状态 |
|---|---|
| YouTube · Bilibili · Twitter/X | provisional |
| 抖音 Douyin | provisional |
| 快手 Kuaishou | experimental |
| 视频号(微信) | unsupported |
| yt-dlp 支持的 1800+ 站点 | experimental |

## 边界

仅限**公开可访问**的内容。**不**绕过 DRM、付费墙、大会员等付费内容。定位:创作者、研究、个人存档。

---

<div align="center">

**如果它帮你省了时间,点个 ⭐ Star 支持一下 —— 这是对独立开发最大的鼓励。**

MIT © [wangzan101](https://github.com/wangzan101)

</div>
