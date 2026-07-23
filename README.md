# 🎬 video-anything

**One link → everything about a video.**
Paste a video URL and get the video, no-watermark file, audio, transcript (文案), subtitles, cover, and metadata — then let your AI agent summarize, rewrite, or storyboard it. **Zero config, zero API key, fully local.**

Works across any agent that supports the [Agent Skills open standard](https://agentskills.io) — Claude Code, Cursor, OpenAI Codex, GitHub Copilot, Gemini CLI, and more. Write once, call anywhere.

---

## Why

`yt-dlp` downloads. It doesn't transcribe, and it doesn't understand. The paid "视频文案提取" sites do — but they're closed, cost money, and only give you text.

`video-anything` closes the loop **as a skill**: download → local ASR → the agent itself does the summary/rewrite/storyboard. No external LLM key, because the agent reading the skill *is* the LLM.

## What you get from one link

- 📹 Video file (no-watermark on Douyin/Kuaishou)
- 🎧 Audio (16k mono, ready for ASR)
- 📝 Transcript / 文案 — local Whisper, with timestamps
- 💬 Platform subtitles (when available)
- 🖼️ Cover / thumbnail
- 🏷️ Metadata (title, description, tags, author, stats)
- ✨ AI summary / rewrite / storyboard / 选题 — done by your agent

## Platforms

| Platform | Status |
|----------|--------|
| YouTube | ✅ solid |
| Bilibili 哔哩哔哩 | ✅ solid |
| Twitter / X | ✅ solid |
| 抖音 Douyin | ✅ works (no-watermark) |
| 快手 Kuaishou | ⚠️ works, occasional breakage |
| 视频号 WeChat Channels | ⛔ not yet (phase 2) |
| 1800+ others via yt-dlp | ➕ try it |

## Install

```bash
brew install yt-dlp ffmpeg
pip install faster-whisper
```
Then verify: `bash scripts/check.sh`. Full notes: [references/install.md](references/install.md).

## Use

Just tell your agent, e.g.:
- *"下载这个抖音视频,要无水印"*
- *"把这个 B站 视频转成文案"*
- *"总结这个 YouTube 视频的要点,再改写成小红书口播稿"*

Under the hood the skill runs:
```bash
bash scripts/fetch.sh "<URL>" ./video-out          # download + assets
python3 scripts/transcribe.py ./video-out/<dir>/audio.wav   # local transcript
# then the agent reads the transcript and writes summary.md
```

## Boundaries

Public content only. No DRM, no paywalls, no 大会员/付费内容. Built for creators, research, and personal archiving.

## License

MIT
