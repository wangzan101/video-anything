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
  Darwin)
    case "$arch" in
      x86_64|amd64|arm64|aarch64) asset="yt-dlp_macos" ;;
      *) echo "ERROR: unsupported_host ($os/$arch)" >&2; exit 10 ;;
    esac
    ;;
  Linux)
    libc_probe="$(ldd --version 2>&1 | head -1 || true)"
    if printf '%s' "$libc_probe" | grep -qi musl || ! printf '%s' "$libc_probe" | grep -Eqi 'glibc|gnu libc|gnu c library'; then
      echo "ERROR: unsupported_host (Linux libc is not supported glibc)" >&2
      exit 10
    fi
    glibc_version="$(printf '%s' "$libc_probe" | grep -oE '[0-9]+\.[0-9]+' | head -1)"
    glibc_major="$(printf '%s' "$glibc_version" | cut -d. -f1)"
    glibc_minor="$(printf '%s' "$glibc_version" | cut -d. -f2)"
    if [ -z "$glibc_major" ] || [ "$glibc_major" -lt 2 ] || { [ "$glibc_major" -eq 2 ] && [ "${glibc_minor:-0}" -lt 17 ]; }; then
      echo "ERROR: unsupported_host (Linux glibc >=2.17 required)" >&2
      exit 10
    fi
    case "$arch" in
      x86_64|amd64) asset="yt-dlp_linux" ;;
      aarch64|arm64) asset="yt-dlp_linux_aarch64" ;;
      *) echo "ERROR: unsupported_host ($os/$arch)" >&2; exit 10 ;;
    esac
    ;;
  *)
    echo "ERROR: unsupported_host ($os/$arch). video-anything needs a supported POSIX host." >&2
    echo "       On Windows, run this inside WSL or Git Bash." >&2
    exit 10
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
  if command -v shasum >/dev/null 2>&1; then
    actual="$(shasum -a 256 "$tmp_bin" | awk '{print $1}')"
  elif command -v sha256sum >/dev/null 2>&1; then
    actual="$(sha256sum "$tmp_bin" | awk '{print $1}')"
  else
    echo "ERROR: neither shasum nor sha256sum is available to verify the yt-dlp download" >&2
    exit 1
  fi
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
# Deno runtime for yt-dlp EJS (Node is never bootstrapped)
# ---------------------------------------------------------------------------
runtime_choice="${VA_YTDLP_JS_RUNTIME:-auto}"
case "$runtime_choice" in
  auto|deno|node|none) ;;
  *) echo "ERROR: invalid VA_YTDLP_JS_RUNTIME='$runtime_choice'" >&2; exit 10 ;;
esac

runtime_version_ok() {
  runtime_bin="$1"; minimum_major="$2"; minimum_minor="$3"
  version_line="$($runtime_bin --version 2>/dev/null | head -1 || true)"
  version_numbers="$(printf '%s' "$version_line" | grep -oE '[0-9]+(\.[0-9]+)+' | head -1)"
  major="$(printf '%s' "$version_numbers" | cut -d. -f1)"
  minor="$(printf '%s' "$version_numbers" | cut -d. -f2)"
  [ -n "$major" ] && { [ "$major" -gt "$minimum_major" ] || { [ "$major" -eq "$minimum_major" ] && [ "${minor:-0}" -ge "$minimum_minor" ]; }; }
}

if [ "$runtime_choice" = node ]; then
  node_bin="$(command -v node 2>/dev/null || true)"
  if [ -z "$node_bin" ] || ! runtime_version_ok "$node_bin" 22 0; then
    echo "ERROR: VA_YTDLP_JS_RUNTIME=node requires Node >=22 (project does not bootstrap Node)" >&2
    exit 10
  fi
  echo ">> yt-dlp JS runtime: explicit Node ($node_bin)"
elif [ "$runtime_choice" = none ]; then
  echo ">> yt-dlp JS runtime: disabled by VA_YTDLP_JS_RUNTIME=none"
else
  deno_bin=""
  if [ -x "$BIN/deno" ] && runtime_version_ok "$BIN/deno" 2 3; then
    deno_bin="$BIN/deno"
  elif command -v deno >/dev/null 2>&1 && runtime_version_ok "$(command -v deno)" 2 3; then
    deno_bin="$(command -v deno)"
  fi
  if [ -z "$deno_bin" ]; then
    if [ "$runtime_choice" = deno ]; then
      echo "ERROR: VA_YTDLP_JS_RUNTIME=deno requires Deno >=2.3" >&2
      exit 10
    fi
    if ! command -v curl >/dev/null 2>&1 || ! command -v unzip >/dev/null 2>&1; then
      echo "ERROR: auto Deno bootstrap requires curl and unzip" >&2
      exit 10
    fi
    case "$os/$arch" in
      Darwin/x86_64|Darwin/amd64) deno_asset="deno-x86_64-apple-darwin.zip" ;;
      Darwin/arm64|Darwin/aarch64) deno_asset="deno-aarch64-apple-darwin.zip" ;;
      Linux/x86_64|Linux/amd64) deno_asset="deno-x86_64-unknown-linux-gnu.zip" ;;
      Linux/aarch64|Linux/arm64) deno_asset="deno-aarch64-unknown-linux-gnu.zip" ;;
      *) echo "ERROR: unsupported_host ($os/$arch)" >&2; exit 10 ;;
    esac
    deno_tag="$(curl -fsSL https://api.github.com/repos/denoland/deno/releases/latest 2>/dev/null | grep '"tag_name"' | head -1 | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/')"
    [ -n "$deno_tag" ] || { echo "ERROR: could not resolve latest Deno release" >&2; exit 10; }
    deno_base="https://github.com/denoland/deno/releases/download/$deno_tag"
    deno_work="$(mktemp -d "${TMPDIR:-/tmp}/va-deno.XXXXXX")" || { echo "ERROR: mktemp failed" >&2; exit 10; }
    cleanup_deno() { rm -rf "$deno_work"; }
    trap cleanup_deno EXIT
    curl -fsSL "$deno_base/$deno_asset" -o "$deno_work/deno.zip" || { echo "ERROR: Deno download failed" >&2; exit 10; }
    curl -fsSL "$deno_base/$deno_asset.sha256sum" -o "$deno_work/deno.sha256sum" || { echo "ERROR: Deno checksum download failed" >&2; exit 10; }
    expected_deno="$(awk '{print $1}' "$deno_work/deno.sha256sum" | head -1)"
    actual_deno="$(shasum -a 256 "$deno_work/deno.zip" 2>/dev/null | awk '{print $1}' || sha256sum "$deno_work/deno.zip" | awk '{print $1}')"
    [ -n "$expected_deno" ] && [ "$expected_deno" = "$actual_deno" ] || { echo "ERROR: Deno checksum mismatch" >&2; exit 10; }
    (cd "$deno_work" && unzip -q deno.zip) || { echo "ERROR: Deno archive extraction failed" >&2; exit 10; }
    chmod +x "$deno_work/deno"
    mv "$deno_work/deno" "$BIN/deno"
    trap - EXIT
    cleanup_deno
    deno_bin="$BIN/deno"
  fi
  echo ">> yt-dlp JS runtime: Deno ($deno_bin, $($deno_bin --version | head -1))"
fi

# ---------------------------------------------------------------------------
# ffmpeg + ffprobe — prefer a complete system pair, else fetch a static pair
# ---------------------------------------------------------------------------
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  sys_ffmpeg="$(command -v ffmpeg)"
  sys_ffprobe="$(command -v ffprobe)"
  if [ ! -e "$BIN/ffmpeg" ] || [ "$(readlink "$BIN/ffmpeg" 2>/dev/null)" != "$sys_ffmpeg" ]; then
    ln -sf "$sys_ffmpeg" "$BIN/ffmpeg"
  fi
  if [ ! -e "$BIN/ffprobe" ] || [ "$(readlink "$BIN/ffprobe" 2>/dev/null)" != "$sys_ffprobe" ]; then
    ln -sf "$sys_ffprobe" "$BIN/ffprobe"
  fi
  echo ">> ffmpeg/ffprobe: using system install ($sys_ffmpeg, $sys_ffprobe)"
elif [ -x "$BIN/ffmpeg" ] && [ -x "$BIN/ffprobe" ] && "$BIN/ffmpeg" -version >/dev/null 2>&1 && "$BIN/ffprobe" -version >/dev/null 2>&1; then
  echo ">> ffmpeg/ffprobe already provisioned: $("$BIN/ffmpeg" -version | head -1)"
else
  echo ">> complete ffmpeg/ffprobe pair not found; fetching static build for $os/$arch"
  rm -f "$BIN/ffmpeg" "$BIN/ffprobe"
  if ! bash "$SCRIPT_DIR/bootstrap_ffmpeg.sh" "$BIN" "$os" "$arch"; then
    echo "ERROR: ffmpeg/ffprobe provisioning failed — install both manually (see references/install.md)" >&2
    exit 10
  fi
fi

if [ ! -x "$BIN/ffmpeg" ] || [ ! -x "$BIN/ffprobe" ]; then
  echo "ERROR: bootstrap did not produce a runnable ffmpeg + ffprobe pair" >&2
  exit 10
fi

echo ">> bootstrap ok: $BIN"
