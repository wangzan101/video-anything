#!/usr/bin/env bash
# Dependency + local-ASR self-check for the video-anything skill.
# Honors VA_HOME (private $VA_HOME/bin is searched first, then system PATH).
# Auto-runs bootstrap.sh when yt-dlp/ffmpeg/ffprobe are missing, then re-checks.
# Prints ✅/❌ per item (with version/engine) and exits 0 iff everything is
# ready, 1 otherwise (pointing at references/install.md).
set -uo pipefail

VA_HOME="${VA_HOME:-$HOME/.video-anything}"
BIN="$VA_HOME/bin"
export PATH="$BIN:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

ok=1

check() {
  local name="$1" probe="$2" hint="$3"
  if eval "$probe" >/dev/null 2>&1; then
    printf '  ✅ %-12s %s\n' "$name" "$(eval "$probe" 2>/dev/null | head -1)"
  else
    printf '  ❌ %-12s MISSING — %s\n' "$name" "$hint"
    ok=0
  fi
}

echo "video-anything dependency check (VA_HOME=$VA_HOME):"

# ---------------------------------------------------------------------------
# yt-dlp / ffmpeg — auto-bootstrap into $VA_HOME/bin if either is missing
# ---------------------------------------------------------------------------
need_bootstrap=0
command -v yt-dlp >/dev/null 2>&1 || need_bootstrap=1
command -v ffmpeg >/dev/null 2>&1 || need_bootstrap=1
command -v ffprobe >/dev/null 2>&1 || need_bootstrap=1

if [ "$need_bootstrap" = 1 ]; then
  echo ">> yt-dlp/ffmpeg missing, running bootstrap..."
  if ! bash "$SCRIPT_DIR/bootstrap.sh"; then
    echo "ERROR: bootstrap 失败 — 见 references/install.md" >&2
    exit 1
  fi
  export PATH="$BIN:$PATH"
fi

check "yt-dlp"  "yt-dlp --version"  "pipx install yt-dlp   (or: brew install yt-dlp)"
check "ffmpeg"  "ffmpeg -version"   "brew install ffmpeg"
check "ffprobe"  "ffprobe -version"  "install the ffmpeg package that includes ffprobe"
check "python3" "python3 --version" "install Python 3.9+"

# ---------------------------------------------------------------------------
# yt-dlp JavaScript runtime is reported separately from generic download
# readiness.  The fetch layer will pass the selected absolute runtime path.
# ---------------------------------------------------------------------------
runtime_choice="${VA_YTDLP_JS_RUNTIME:-auto}"
case "$runtime_choice" in
  auto|deno|node|none) ;;
  *) echo "  ❌ YouTube JS  invalid VA_YTDLP_JS_RUNTIME='$runtime_choice'"; ok=0; runtime_choice=none ;;
esac

runtime_version_ok() {
  runtime_bin="$1"; minimum_major="$2"; minimum_minor="$3"
  version_line="$($runtime_bin --version 2>/dev/null | head -1 || true)"
  version_numbers="$(printf '%s' "$version_line" | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)"
  major="$(printf '%s' "$version_numbers" | cut -d. -f1)"
  minor="$(printf '%s' "$version_numbers" | cut -d. -f2)"
  [ -n "$major" ] && { [ "$major" -gt "$minimum_major" ] || { [ "$major" -eq "$minimum_major" ] && [ "${minor:-0}" -ge "$minimum_minor" ]; }; }
}

if [ "$runtime_choice" = none ]; then
  echo "  ⚠️  YouTube JS  disabled (VA_YTDLP_JS_RUNTIME=none); generic download may still work"
else
  runtime_bin=""
  if [ -x "$BIN/deno" ] && runtime_version_ok "$BIN/deno" 2 3; then runtime_bin="$BIN/deno"; fi
  if [ -z "$runtime_bin" ] && command -v deno >/dev/null 2>&1 && runtime_version_ok "$(command -v deno)" 2 3; then runtime_bin="$(command -v deno)"; fi
  if [ "$runtime_choice" = node ]; then
    runtime_bin="$(command -v node 2>/dev/null || true)"
    if [ -n "$runtime_bin" ] && runtime_version_ok "$runtime_bin" 22 0; then
      echo "  ✅ YouTube JS  explicit Node ($runtime_bin)"
    else
      echo "  ❌ YouTube JS  explicit Node >=22 required — project does not bootstrap Node"
      ok=0
    fi
  elif [ -n "$runtime_bin" ]; then
    echo "  ✅ YouTube JS  Deno ($runtime_bin)"
  else
    echo "  ❌ YouTube JS  Deno >=2.3 unavailable — run bootstrap with VA_YTDLP_JS_RUNTIME=auto"
    ok=0
  fi
fi

# ---------------------------------------------------------------------------
# Local ASR — real probe, in priority order (must match scripts/transcribe.py):
#   1. faster-whisper inside $VA_HOME/venv
#   2. system openai-whisper CLI ("whisper" on PATH)
#   3. none -> cloud engine required
# ---------------------------------------------------------------------------
asr_bin="$(command -v whisper 2>/dev/null || true)"
if [ -x "$VA_HOME/venv/bin/python" ] && "$VA_HOME/venv/bin/python" -c "import faster_whisper" >/dev/null 2>&1; then
  echo "  ✅ ASR          本地 ASR: faster-whisper ($VA_HOME/venv)"
elif [ -n "$asr_bin" ]; then
  echo "  ✅ ASR          本地 ASR: openai-whisper ($(basename "$asr_bin"))"
else
  echo "  ❌ ASR          MISSING — 本地 ASR: 无(云引擎需 --engine cloud); pip install faster-whisper (or: pip install openai-whisper)"
  ok=0
fi

echo
if [ "$ok" = 1 ]; then
  echo "就绪:所有依赖可用。"
else
  echo "存在缺失依赖 — 见上方提示及 references/install.md。"
  exit 1
fi
