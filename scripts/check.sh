#!/usr/bin/env bash
# Dependency + local-ASR self-check for the video-anything skill.
# Honors VA_HOME (private $VA_HOME/bin is searched first, then system PATH).
# Auto-runs bootstrap.sh when yt-dlp/ffmpeg are missing, then re-checks.
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
check "python3" "python3 --version" "install Python 3.9+"

# ---------------------------------------------------------------------------
# Local ASR — real probe, in priority order:
#   1. system whisper / whisper-cli CLI
#   2. faster-whisper inside $VA_HOME/venv
#   3. whisper.cpp binary ($VA_HOME/bin/whisper-cli or system) — covered by
#      step 1 since $VA_HOME/bin is already on PATH and whisper-cli is the
#      whisper.cpp CLI name.
#   4. none -> cloud engine required
# ---------------------------------------------------------------------------
asr_bin="$(command -v whisper-cli 2>/dev/null || command -v whisper 2>/dev/null || true)"
if [ -n "$asr_bin" ]; then
  echo "  ✅ ASR          本地 ASR: 系统 whisper ($asr_bin)"
elif [ -x "$VA_HOME/venv/bin/python" ] && "$VA_HOME/venv/bin/python" -c "import faster_whisper" >/dev/null 2>&1; then
  echo "  ✅ ASR          本地 ASR: faster-whisper ($VA_HOME/venv)"
else
  echo "  ❌ ASR          MISSING — 本地 ASR: 无(云引擎需 --engine cloud); pip install faster-whisper (or: brew install whisper-cpp)"
  ok=0
fi

echo
if [ "$ok" = 1 ]; then
  echo "就绪:所有依赖可用。"
else
  echo "存在缺失依赖 — 见上方提示及 references/install.md。"
  exit 1
fi
