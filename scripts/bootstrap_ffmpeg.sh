#!/usr/bin/env bash
# scripts/bootstrap_ffmpeg.sh — fetch a static ffmpeg binary when no system
# ffmpeg is available. Called by scripts/bootstrap.sh; not normally exercised
# on machines that already have ffmpeg installed, but must be complete and
# correct on its own since it's the fallback path for users without it.
#
# Usage: bash scripts/bootstrap_ffmpeg.sh <BIN_DIR> <os> <arch>
#   <os>    uname -s output: Darwin | Linux
#   <arch>  uname -m output: x86_64 | arm64 | aarch64 | armv7l | i686 ...
#
# Sources (fixed, no user choice):
#   macOS -> evermeet.cx/ffmpeg        official "release" (stable) channel,
#            static universal binary. No published SHA256, so verification
#            is best-effort: expected download size (from their JSON info
#            API) + a smoke run of the extracted binary.
#   Linux -> johnvansickle.com/ffmpeg  official "release" static build,
#            per-arch. Verified against their published MD5 checksum.
#
# Exits non-zero on any failure so the caller can print an actionable
# fallback message and abort rather than leaving a half-provisioned BIN.
set -uo pipefail

BIN="${1:-}"; os="${2:-}"; arch="${3:-}"
if [ -z "$BIN" ] || [ -z "$os" ]; then
  echo "usage: bootstrap_ffmpeg.sh <BIN_DIR> <os> <arch>" >&2
  exit 2
fi
mkdir -p "$BIN" || { echo "ERROR: cannot create $BIN" >&2; exit 1; }

work="$(mktemp -d "${TMPDIR:-/tmp}/va-ffmpeg.XXXXXX")" || { echo "ERROR: mktemp failed" >&2; exit 1; }
cleanup() { rm -rf "$work"; }
trap cleanup EXIT

case "$os" in
  Darwin)
    if ! command -v unzip >/dev/null 2>&1; then
      echo "ERROR: 'unzip' is required to install the macOS static ffmpeg build" >&2
      exit 1
    fi

    info_url="https://evermeet.cx/ffmpeg/info/ffmpeg/release"
    info="$(curl -fsSL "$info_url")" || { echo "ERROR: cannot reach $info_url" >&2; exit 1; }

    version="$(printf '%s' "$info" | grep -o '"version":"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')"
    zip_block="$(printf '%s' "$info" | grep -o '"zip":{[^}]*}' | head -1)"
    zip_url="$(printf '%s' "$zip_block" | grep -o '"url":"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')"
    zip_size="$(printf '%s' "$zip_block" | grep -o '"size":[0-9]*' | head -1 | sed -E 's/.*:([0-9]*)/\1/')"
    if [ -z "$version" ] || [ -z "$zip_url" ]; then
      echo "ERROR: could not parse evermeet.cx release metadata from $info_url" >&2
      exit 1
    fi

    echo ">> fetching ffmpeg $version from evermeet.cx (official release channel)"
    if ! curl -fsSL "$zip_url" -o "$work/ffmpeg.zip"; then
      echo "ERROR: download failed: $zip_url" >&2
      exit 1
    fi

    if [ -n "$zip_size" ]; then
      actual_size="$(wc -c < "$work/ffmpeg.zip" | tr -d ' ')"
      if [ "$actual_size" != "$zip_size" ]; then
        echo "ERROR: downloaded size ($actual_size bytes) != expected ($zip_size bytes) for $zip_url" >&2
        exit 1
      fi
    fi

    if ! ( cd "$work" && unzip -q ffmpeg.zip ); then
      echo "ERROR: could not unzip downloaded archive from $zip_url" >&2
      exit 1
    fi
    if [ ! -f "$work/ffmpeg" ]; then
      echo "ERROR: expected 'ffmpeg' binary not found inside archive from $zip_url" >&2
      exit 1
    fi
    chmod +x "$work/ffmpeg"

    probe_info_url="https://evermeet.cx/ffmpeg/ffprobe/release"
    probe_info="$(curl -fsSL "$probe_info_url")" || { echo "ERROR: cannot reach $probe_info_url" >&2; exit 1; }
    probe_zip_block="$(printf '%s' "$probe_info" | grep -o '"zip":{[^}]*}' | head -1)"
    probe_zip_url="$(printf '%s' "$probe_zip_block" | grep -o '"url":"[^"]*"' | head -1 | sed -E 's/.*:"([^"]*)"/\1/')"
    if [ -z "$probe_zip_url" ]; then
      echo "ERROR: could not parse evermeet.cx ffprobe metadata from $probe_info_url" >&2
      exit 1
    fi
    if ! curl -fsSL "$probe_zip_url" -o "$work/ffprobe.zip"; then
      echo "ERROR: ffprobe download failed: $probe_zip_url" >&2
      exit 1
    fi
    if ! ( cd "$work" && unzip -q ffprobe.zip ); then
      echo "ERROR: could not unzip downloaded ffprobe archive from $probe_zip_url" >&2
      exit 1
    fi
    probe_extracted="$(find "$work" -maxdepth 2 -type f -name ffprobe | head -1)"
    if [ -z "$probe_extracted" ]; then
      echo "ERROR: expected 'ffprobe' binary not found inside archive from $probe_zip_url" >&2
      exit 1
    fi
    cp "$probe_extracted" "$work/ffprobe"
    chmod +x "$work/ffprobe"
    ;;

  Linux)
    case "$arch" in
      x86_64|amd64)  la=amd64 ;;
      aarch64|arm64) la=arm64 ;;
      armv7l|armhf)  la=armhf ;;
      i686|i386)     la=i686 ;;
      *)
        echo "ERROR: no johnvansickle.com static ffmpeg build for arch '$arch'" >&2
        exit 1
        ;;
    esac

    base="https://johnvansickle.com/ffmpeg/releases"
    tarball="ffmpeg-release-${la}-static.tar.xz"
    tar_url="$base/$tarball"
    md5_url="$base/$tarball.md5"

    echo ">> fetching ffmpeg (johnvansickle.com official release, $la)"
    if ! curl -fsSL "$tar_url" -o "$work/$tarball"; then
      echo "ERROR: download failed: $tar_url" >&2
      exit 1
    fi
    if ! curl -fsSL "$md5_url" -o "$work/$tarball.md5"; then
      echo "ERROR: could not fetch checksum: $md5_url" >&2
      exit 1
    fi

    expected_md5="$(awk '{print $1}' "$work/$tarball.md5")"
    if [ -z "$expected_md5" ]; then
      echo "ERROR: could not parse checksum file $md5_url" >&2
      exit 1
    fi
    if command -v md5sum >/dev/null 2>&1; then
      actual_md5="$(md5sum "$work/$tarball" | awk '{print $1}')"
    elif command -v md5 >/dev/null 2>&1; then
      actual_md5="$(md5 -q "$work/$tarball")"
    else
      echo "ERROR: neither md5sum nor md5 is available to verify the ffmpeg download" >&2
      exit 1
    fi
    if [ "$expected_md5" != "$actual_md5" ]; then
      echo "ERROR: ffmpeg tarball checksum mismatch for $tar_url" >&2
      echo "       expected: $expected_md5" >&2
      echo "       got:      $actual_md5" >&2
      exit 1
    fi

    if ! ( cd "$work" && tar -xf "$tarball" ); then
      echo "ERROR: could not extract $tarball" >&2
      exit 1
    fi
    extracted="$(find "$work" -maxdepth 2 -type f -name ffmpeg | head -1)"
    extracted_probe="$(find "$work" -maxdepth 2 -type f -name ffprobe | head -1)"
    if [ -z "$extracted" ] || [ -z "$extracted_probe" ]; then
      echo "ERROR: ffmpeg + ffprobe binaries not found inside $tarball" >&2
      exit 1
    fi
    cp "$extracted" "$work/ffmpeg"
    cp "$extracted_probe" "$work/ffprobe"
    chmod +x "$work/ffmpeg"
    chmod +x "$work/ffprobe"
    ;;

  *)
    echo "ERROR: no static ffmpeg source configured for OS '$os'" >&2
    exit 1
    ;;
esac

if ! "$work/ffmpeg" -version >/dev/null 2>&1 || ! "$work/ffprobe" -version >/dev/null 2>&1; then
  echo "ERROR: fetched ffmpeg/ffprobe pair does not run on this system (arch mismatch?)" >&2
  exit 1
fi

mv "$work/ffmpeg" "$BIN/ffmpeg"
mv "$work/ffprobe" "$BIN/ffprobe"
echo ">> ffmpeg + ffprobe provisioned: $("$BIN/ffmpeg" -version | head -1)"
