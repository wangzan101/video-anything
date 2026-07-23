#!/usr/bin/env bash
# scripts/bootstrap.sh — provision yt-dlp + ffmpeg into a private, isolated
# directory ($VA_HOME/bin) with zero manual install steps.
#
# Usage:   bash scripts/bootstrap.sh
# Env:     VA_HOME   override install root (default: ~/.video-anything)
#
# Idempotent: already-provisioned + working binaries are left alone. yt-dlp
# is downloaded from the official GitHub release for this platform and
# verified against the official SHA2-256SUMS. ffmpeg prefers the system
# install (symlinked in); if absent, scripts/bootstrap_ffmpeg.sh fetches a
# pinned static build.
#
# This is the most fragile piece of the project (network + third-party
# binaries) — every failure path below prints a specific, actionable reason
# and exits non-zero rather than limping along silently.
set -uo pipefail

VA_HOME="${VA_HOME:-$HOME/.video-anything}"
BIN="$VA_HOME/bin"
mkdir -p "$BIN" || { echo "ERROR: cannot create $BIN" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

os="$(uname -s)"
arch="$(uname -m)"

case "$os" in
  Darwin) asset="yt-dlp_macos" ;;
  Linux)  asset="yt-dlp_linux" ;;
  *)
    echo "ERROR: unsupported OS '$os'. video-anything needs a POSIX shell + coreutils." >&2
    echo "       On Windows, run this inside WSL or Git Bash." >&2
    exit 1
    ;;
esac

# ---------------------------------------------------------------------------
# yt-dlp
# ---------------------------------------------------------------------------
ytdlp_ok=0
if [ -x "$BIN/yt-dlp" ] && "$BIN/yt-dlp" --version >/dev/null 2>&1; then
  ytdlp_ok=1
fi

if [ "$ytdlp_ok" = 1 ]; then
  echo ">> yt-dlp already provisioned: $("$BIN/yt-dlp" --version)"
else
  echo ">> provisioning yt-dlp ($asset)..."

  # Resolve the latest stable release tag dynamically — never hardcode a tag
  # here, GitHub prunes old asset URLs are fine but a stale hand-picked
  # version number goes stale and 404s. Fall back to a tag we have verified
  # exists, only if the GitHub API itself is unreachable/rate-limited.
  tag="$(curl -fsSL https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest 2>/dev/null \
        | grep '"tag_name"' | head -1 | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/')"
  if [ -z "$tag" ]; then
    tag="2026.06.09"  # verified-existing fallback (checked at authoring time); see task-6-report.md
    echo "WARN: could not resolve latest yt-dlp release via GitHub API; falling back to $tag" >&2
  fi

  base="https://github.com/yt-dlp/yt-dlp/releases/download/$tag"
  tmp_bin="$BIN/.yt-dlp.$$.tmp"
  tmp_sums="$BIN/.SUMS.$$.tmp"
  cleanup_ytdlp() { rm -f "$tmp_bin" "$tmp_sums"; }
  trap cleanup_ytdlp EXIT

  if ! curl -fsSL "$base/$asset" -o "$tmp_bin"; then
    echo "ERROR: yt-dlp download failed for tag '$tag' ($base/$asset)" >&2
    echo "       check network access, or that release '$tag' still ships '$asset'." >&2
    exit 1
  fi
  if ! curl -fsSL "$base/SHA2-256SUMS" -o "$tmp_sums"; then
    echo "ERROR: could not fetch SHA2-256SUMS for tag '$tag' ($base/SHA2-256SUMS)" >&2
    exit 1
  fi

  expected="$(grep " \*\{0,1\}$asset\$" "$tmp_sums" | awk '{print $1}' | head -1)"
  if [ -z "$expected" ]; then
    echo "ERROR: no checksum entry for '$asset' in SHA2-256SUMS (tag $tag)" >&2
    exit 1
  fi
  actual="$(shasum -a 256 "$tmp_bin" | awk '{print $1}')"
  if [ "$expected" != "$actual" ]; then
    echo "ERROR: yt-dlp checksum mismatch for tag '$tag'" >&2
    echo "       expected: $expected" >&2
    echo "       got:      $actual" >&2
    exit 1
  fi

  chmod +x "$tmp_bin"
  mv "$tmp_bin" "$BIN/yt-dlp"
  trap - EXIT
  rm -f "$tmp_sums"

  if ! "$BIN/yt-dlp" --version >/dev/null 2>&1; then
    echo "ERROR: downloaded yt-dlp does not run on this system (arch/OS mismatch?)" >&2
    exit 1
  fi
  echo ">> yt-dlp $("$BIN/yt-dlp" --version) ready (tag $tag, checksum verified)"
fi

# ---------------------------------------------------------------------------
# ffmpeg — prefer system install, else fetch a static build
# ---------------------------------------------------------------------------
if command -v ffmpeg >/dev/null 2>&1; then
  sys_ffmpeg="$(command -v ffmpeg)"
  if [ ! -e "$BIN/ffmpeg" ] || [ "$(readlink "$BIN/ffmpeg" 2>/dev/null)" != "$sys_ffmpeg" ]; then
    ln -sf "$sys_ffmpeg" "$BIN/ffmpeg"
  fi
  echo ">> ffmpeg: using system install ($sys_ffmpeg)"
elif [ -x "$BIN/ffmpeg" ] && "$BIN/ffmpeg" -version >/dev/null 2>&1; then
  echo ">> ffmpeg already provisioned: $("$BIN/ffmpeg" -version | head -1)"
else
  echo ">> system ffmpeg not found; fetching static build for $os/$arch"
  rm -f "$BIN/ffmpeg"
  if ! bash "$SCRIPT_DIR/bootstrap_ffmpeg.sh" "$BIN" "$os" "$arch"; then
    echo "ERROR: ffmpeg provisioning failed — install ffmpeg manually (see references/install.md)" >&2
    exit 1
  fi
fi

echo ">> bootstrap ok: $BIN"
