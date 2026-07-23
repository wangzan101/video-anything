# 安装依赖

这个 skill 只依赖三个本地工具,**不需要任何 API key**。

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
# ffmpeg:见 https://ffmpeg.org/download.html
pip install faster-whisper
```

## 自检

```bash
bash scripts/check.sh
```

全部 ✅ 即可用。

## 说明

- **yt-dlp** 要保持更新(平台反爬频繁),失效先 `yt-dlp -U`。
- **faster-whisper** 首次运行会自动下载模型(`small` 约 460MB),之后离线可用。
- **模型选择**:中文短视频 `small` 够用;长视频或要更准用 `--model medium`。GPU 环境可换更大模型。
- 总结/改写步骤由 agent 自己完成,**无需 OpenAI/Anthropic key**。
