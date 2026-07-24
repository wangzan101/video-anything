# 安装依赖

下载地基的 v1 宿主是 macOS 10.15+（x86_64/arm64）和 Linux glibc 2.17+（x86_64/aarch64，WSL 按实际 Linux 环境判断）。musl、Linux armv7l 和原生 Windows 明确不支持；bootstrap 会在发起二进制下载前以 `10/unsupported_host` 失败。

这个 skill 需要 yt-dlp、ffmpeg、ffprobe 和 Python，**不需要任何 API key**。YouTube 的完整 extractor 还需要 Deno `>=2.3`；默认 `VA_YTDLP_JS_RUNTIME=auto` 会在 `$VA_HOME/bin/deno` 缺失时从 Deno 官方 release 安装。Node 不会被项目自动安装，只有显式 `VA_YTDLP_JS_RUNTIME=node` 且版本 `>=22` 才使用。

## 一次性安装

**macOS (Homebrew):**
```bash
brew install yt-dlp ffmpeg
pip install faster-whisper        # 推荐的本地 ASR(快、无需 key)
# 或者:pip install openai-whisper # 备选 ASR 引擎(提供 whisper 命令)
```

**其他/通用:**
```bash
pipx install yt-dlp               # 或 pip install -U yt-dlp
# ffmpeg:见 https://ffmpeg.org/download.html（必须同时提供 ffprobe）
pip install faster-whisper
```

## 自检

```bash
bash scripts/check.sh
```

全部 ✅ 即可用。

## 说明

- **yt-dlp** 要保持更新(平台反爬频繁),失效先重新运行 bootstrap；fetch 不会隐式自更新。
- runtime 可显式选择：`VA_YTDLP_JS_RUNTIME=auto|deno|node|none`。`none` 只表示禁用 JS runtime，不代表 YouTube capability ready。
- **faster-whisper** 首次运行会自动下载模型(`small` 约 460MB),之后离线可用。
- **模型选择**:中文短视频 `small` 够用;长视频或要更准用 `--model medium`。GPU 环境可换更大模型。
- 总结/改写步骤由 agent 自己完成,**无需 OpenAI/Anthropic key**。
