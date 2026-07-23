<div align="center">

# 🎬 video-anything

### One link → *everything* about a video.

Download it, transcribe it, and let your AI rewrite it — in any agent, with **zero API keys and zero manual setup**.

**English** · [简体中文](README.md)

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-open%20standard-6b46c1)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![stars](https://img.shields.io/github/stars/wangzan101/video-anything?style=social)](https://github.com/wangzan101/video-anything)

</div>

<!-- TODO: drop a 15s demo GIF here — paste a link → no-watermark video + transcript + rewrite. Highest-converting asset. -->
<p align="center"><img src="docs/demo.gif" alt="demo" width="720"></p>

---

## Why this exists

`yt-dlp` **downloads** — but it can't transcribe, and it can't understand.
The paid "video-to-text" sites **can** — but they're closed, cost money, and only hand you text.

**`video-anything` closes the loop *as a skill*:** `download → local transcript → the agent itself rewrites/summarizes`.
No external LLM key — because the agent reading this skill **is** the LLM.

## Paste one link, get all of it

| | |
|---|---|
| 📹 **Video file** | no-watermark on Douyin / Kuaishou |
| 🎧 **Audio** | 16k mono, ASR-ready |
| 📝 **Transcript** | local Whisper, timestamped |
| 💬 **Subtitles** | platform subs when available (human subs only) |
| 🖼️ **Cover** + 🏷️ **Metadata** | title, description, tags, author, stats |
| ✨ **AI rewrite / summary** | done by *your* agent, no key |

## ✨ The part yt-dlp can't do

Feed the transcript into a built-in **playbook** and your agent produces publish-ready copy:

- **Key points** — one-line thesis + 3–7 timestamped highlights
- **Voiceover rewrite** — rewrite into distinct social styles (or your own), with a hard *no-fabrication* rule

<details>
<summary><b>See it (rewrite → social "种草" style)</b></summary>

> **In** (raw transcript): `[00:03] 我做自由职业三年了,前两年天天被拖延症折磨…`
> **Out** (小红书 style): `真的会哭死,自由职业三年,前两年天天被拖延症拿捏😭 后来才想明白,根本不是意志力不够,是"开始"这个动作太难了…`

Full 3-style example: [`references/examples/rewrite.md`](references/examples/rewrite.md)

</details>

## Works in *your* agent

Built on the [Agent Skills open standard](https://agentskills.io) — **write once, call anywhere**: Claude Code · Cursor · OpenAI Codex · GitHub Copilot · Gemini CLI · and 40+ more.

## Install

**1. Add the skill** (drop it where your agent looks for skills):

```bash
git clone https://github.com/wangzan101/video-anything ~/.claude/skills/video-anything
# Cursor / Codex / others also scan .claude/skills, .cursor/skills, .agents/skills
```

**2. That's it.** No `brew install`, no manual setup. On first use the skill **auto-provisions** its own tools (`yt-dlp` + `ffmpeg` + local Whisper) into `~/.video-anything/` — nothing pollutes your system.

> Want to check/pre-provision? `bash scripts/check.sh`. Details: [`references/install.md`](references/install.md).

## Use

Just talk to your agent — it picks the steps:

- *"Download this Douyin video, no watermark"*
- *"Turn this Bilibili video into a transcript"*
- *"Summarize this YouTube video, then rewrite it as a 小红书 script"*

<details>
<summary>What runs under the hood</summary>

```bash
bash scripts/fetch.sh "<URL>" ./video-out                 # download + assets
python3 scripts/transcribe.py ./video-out/<dir>/audio.wav  # local transcript
# → the agent reads the transcript and writes summary.md via a playbook
```
</details>

## How it works

```
URL ─► detect platform ─► yt-dlp (video + human subs + cover + metadata)
      └► ffmpeg → 16k audio ─► human subtitle? ── yes ─► use it (skip ASR)
                                              └─ no ──► local Whisper → transcript
      └► agent runs a playbook ─► summary.md  (no API key)
```

## Platforms

| Platform | Status |
|---|---|
| YouTube · Bilibili · Twitter/X | ✅ solid |
| Douyin | ✅ works — no-watermark |
| Kuaishou | ⚠️ works, occasional anti-bot breakage |
| WeChat Channels | ⛔ not yet (phase 2) |
| 1800+ others via yt-dlp | ➕ just try it |

## Boundaries

Public content only. **No** DRM, paywalls, or paid content. Built for creators, research, and personal archiving.

---

<div align="center">

**If it saved you time, a ⭐ Star means a lot to an indie project.**

MIT © [wangzan101](https://github.com/wangzan101)

</div>
