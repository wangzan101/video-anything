#!/usr/bin/env bash
# Dependency self-check for the video-anything skill.
# Prints OK / MISSING for each tool and a one-line install hint if missing.
set -uo pipefail

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

echo "video-anything dependency check:"
check "yt-dlp"  "yt-dlp --version"        "pipx install yt-dlp   (or: brew install yt-dlp)"
check "ffmpeg"  "ffmpeg -version"         "brew install ffmpeg"
check "python3" "python3 --version"       "install Python 3.9+"

# ASR: prefer faster-whisper (python), fall back to a whisper CLI
if python3 -c "import faster_whisper" >/dev/null 2>&1; then
  echo "  ✅ ASR          faster-whisper (python)"
elif command -v whisper-cli >/dev/null 2>&1 || command -v whisper >/dev/null 2>&1; then
  echo "  ✅ ASR          whisper CLI ($(command -v whisper-cli || command -v whisper))"
else
  echo "  ❌ ASR          MISSING — pip install faster-whisper   (or: brew install whisper-cpp)"
  ok=0
fi

echo
if [ "$ok" = 1 ]; then
  echo "All dependencies present. You're good to go."
else
  echo "Some dependencies missing — see hints above and references/install.md."
  exit 1
fi
