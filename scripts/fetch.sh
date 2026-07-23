#!/usr/bin/env bash
# fetch.sh — download a video + all assets for one URL.
#
# Usage:   bash scripts/fetch.sh "<URL>" [OUTPUT_ROOT]
# Example: bash scripts/fetch.sh "https://v.douyin.com/xxx/" ./video-out
#
# Produces  <OUTPUT_ROOT>/<extractor>-<id>/ with:
#   video.mp4, audio.wav (16k mono), info.json, thumbnail.*, and *.vtt (if the
#   platform ships subtitles). Prints the produced directory as the LAST line.
#
# Notes:
#   - Douyin/Kuaishou generally return the no-watermark source via yt-dlp.
#   - For login/region-gated content, add cookies (see references/platforms.md):
#       export VA_COOKIES_FROM_BROWSER=chrome   # or a cookies.txt path in VA_COOKIES
set -uo pipefail

URL="${1:-}"
OUT_ROOT="${2:-./video-out}"
if [ -z "$URL" ]; then
  echo "usage: bash scripts/fetch.sh \"<URL>\" [OUTPUT_ROOT]" >&2
  exit 2
fi

if ! command -v yt-dlp >/dev/null 2>&1; then
  echo "ERROR: yt-dlp not installed. Run: pipx install yt-dlp   (or brew install yt-dlp)" >&2
  exit 1
fi

# Cookie handling (optional)
COOKIE_ARGS=()
if [ -n "${VA_COOKIES_FROM_BROWSER:-}" ]; then
  COOKIE_ARGS+=(--cookies-from-browser "$VA_COOKIES_FROM_BROWSER")
elif [ -n "${VA_COOKIES:-}" ]; then
  COOKIE_ARGS+=(--cookies "$VA_COOKIES")
fi

# Resolve extractor + id up front so we can name the output dir deterministically.
meta="$(yt-dlp "${COOKIE_ARGS[@]}" --no-warnings --print "%(extractor)s\t%(id)s" --playlist-items 1 "$URL" 2>/dev/null | head -1)"
extractor="$(printf '%s' "$meta" | cut -f1)"
vid="$(printf '%s' "$meta" | cut -f2)"
if [ -z "$extractor" ] || [ -z "$vid" ]; then
  echo "ERROR: could not resolve video metadata. Try 'yt-dlp -U' to update, or check the URL / cookies." >&2
  exit 1
fi

DIR="$OUT_ROOT/${extractor}-${vid}"
mkdir -p "$DIR"

echo ">> downloading [$extractor] $vid → $DIR"
yt-dlp "${COOKIE_ARGS[@]}" \
  --no-warnings --no-playlist \
  -f "bv*+ba/b" --merge-output-format mp4 \
  --write-info-json --write-thumbnail \
  --write-subs --write-auto-subs --sub-langs "zh-Hans,zh,en" --convert-subs vtt \
  -o "$DIR/video.%(ext)s" \
  -o "infojson:$DIR/info.%(ext)s" \
  -o "thumbnail:$DIR/thumbnail.%(ext)s" \
  -o "subtitle:$DIR/sub.%(ext)s" \
  "$URL"

# Normalize the merged video filename to video.mp4 when possible.
if [ ! -f "$DIR/video.mp4" ]; then
  first_vid="$(ls "$DIR"/video.* 2>/dev/null | grep -viE '\.(json|jpg|jpeg|png|webp|vtt)$' | head -1)"
  [ -n "$first_vid" ] && mv "$first_vid" "$DIR/video.mp4"
fi

# Extract 16k mono wav for ASR.
if [ -f "$DIR/video.mp4" ]; then
  echo ">> extracting audio → audio.wav"
  ffmpeg -y -loglevel error -i "$DIR/video.mp4" -vn -ac 1 -ar 16000 "$DIR/audio.wav" \
    || echo "WARN: audio extraction failed"
fi

echo
echo ">> done. contents:"
ls -1 "$DIR" | sed 's/^/   /'
echo
# LAST line = the produced directory (machine-readable for the next step).
echo "$DIR"
