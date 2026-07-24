<div align="center">

# 🎬 video-anything

### A video download, transcription, and content-processing Skill for Agents

Give an Agent Skills-compatible tool a public video URL and get a validated download, extracted audio, transcription inputs, and downstream content work.

**English** · [简体中文](README.md) · [Download contract](docs/superpowers/specs/2026-07-24-video-download-contract.md)

[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-open%20standard-6b46c1)](https://agentskills.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

> The current focus is making “URL → verifiable artifact” dependable. Platform status is evidence-based: directory existence, yt-dlp site-list entries, or one lucky download are not support proof.

## What it does

- Downloads one public video with yt-dlp; playlists, live streams, DRM, paywalls, and membership-only content are out of scope.
- Uses ffmpeg/ffprobe to validate media instead of trusting file extensions.
- Publishes `video.mp4`, `audio.wav`, `info.json`, `manifest.json`, and `fetch.log` only after validation.
- Reuses a revalidated final by default; `--force` keeps the previous final intact until the replacement is ready.
- Feeds the audio into your configured local ASR workflow, then lets your Agent summarize or rewrite the transcript.

Your Agent performs the LLM work; this project does not require an OpenAI, Anthropic, or other LLM API key.

## Current status

The download core has offline contract coverage, real local media integration, and default CI. Real platform smoke remains a separate release/nightly gate.

| Platform | Level | Notes |
|---|---|---|
| YouTube, Bilibili, Twitter/X | provisional | Requires recorded public fixtures; YouTube also needs a JS runtime |
| Douyin | provisional | Short links, login, and anti-bot conditions need separate smoke coverage |
| Kuaishou | experimental | No fixed extractor or no-watermark guarantee |
| WeChat Channels | unsupported | Outside the current v1 support scope |
| Other yt-dlp sites | experimental | Upstream availability is not READY evidence |

## Install

```bash
git clone https://github.com/wangzan101/video-anything ~/.claude/skills/video-anything
cd ~/.claude/skills/video-anything
```

Runtime requirements are Python 3, yt-dlp, ffmpeg, and ffprobe. Check the environment with:

```bash
bash scripts/check.sh
```

`scripts/bootstrap.sh` can provision yt-dlp, an ffmpeg/ffprobe pair, and Deno (the default runtime policy) under an isolated `VA_HOME`. v1 supports:

- macOS 10.15+: x86_64 and arm64
- Linux glibc 2.17+: x86_64 and aarch64; WSL follows its actual Linux host
- musl, Linux armv7l, and native Windows: unsupported

YouTube JS runtime selection:

```bash
export VA_YTDLP_JS_RUNTIME=auto   # default; controlled Deno >=2.3
# deno: explicitly use Deno >=2.3
# node: explicitly use Node >=22; the project never installs Node
# none: disable JS runtime; this does not mean YouTube is ready
```

See [`references/install.md`](references/install.md) for details.

## Run the downloader directly

```bash
bash scripts/fetch.sh "https://example.com/video" ./video-out
```

Force a new artifact:

```bash
bash scripts/fetch.sh "https://example.com/video" ./video-out --force
```

On success, stdout contains only the final directory path. On failure, stdout is empty and diagnostics go to stderr. Exit codes:

| Code | Meaning |
|---:|---|
| 0 | READY |
| 2 | Invalid arguments or URL |
| 10 | Dependency, host, or JS runtime unavailable |
| 20 | Resolve failure, playlist, or live stream |
| 30 | Download failure |
| 40 | No real compatible MP4 could be produced |
| 50 | Video, JSON, audio, or duration validation failure |
| 60 | Lock, publish, or recovery conflict |

Successful output:

```text
video-out/<extractor>-<id>/
├── video.mp4       # parseable MP4; H.264/AAC preferred
├── audio.wav       # PCM WAV, 16 kHz, mono
├── info.json       # metadata matching extractor/id
├── manifest.json   # status=ready, validation, and provenance
└── fetch.log       # redacted diagnostics
```

Thumbnails and human subtitles are optional. Failed staging, journals, and backups live in hidden transaction directories under the output root for diagnosis/recovery and should not be passed to downstream Agents.

## Use it from an Agent

After installing the Skill, ask for example:

- “Download this public video and validate the artifact.”
- “Transcribe the downloaded audio with timestamps.”
- “Extract key points from the transcript and rewrite it as a social-video script.”

See [`SKILL.md`](SKILL.md) for the Skill’s operational boundaries and downstream workflow.

## Tests and CI

Offline tests do not access the network:

```bash
python -m pytest -q
bash -n scripts/*.sh tests/smoke.sh
git diff --check
```

Local integration uses real ffmpeg/ffprobe. Platform smoke is explicit and belongs in release/nightly checks:

```bash
bash tests/smoke.sh --platform youtube --url "<public-fixture-url>"
```

The repository contains no fixture URLs, cookies, or private credentials. Smoke reports store a URL hash and redacted diagnostics. A platform may be upgraded to `supported` only after two public fixtures each produce READY three consecutive times.

## Boundaries and license

Use only public content you are authorized to access. Do not bypass DRM, paywalls, login restrictions, or platform security controls. MIT License: [`LICENSE`](LICENSE).
