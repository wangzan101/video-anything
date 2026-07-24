from __future__ import annotations

import json
import os
import shlex
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


VIDEO_PROBE = {
    "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "10.0"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "duration": "10.0"},
        {"codec_type": "audio", "codec_name": "aac", "duration": "10.0"},
    ],
}
WEBM_PROBE = {
    "format": {"format_name": "matroska,webm", "duration": "10.0"},
    "streams": [
        {"codec_type": "video", "codec_name": "vp9", "duration": "10.0"},
        {"codec_type": "audio", "codec_name": "opus", "duration": "10.0"},
    ],
}
WAV_PROBE = {
    "format": {"format_name": "wav", "duration": "10.0"},
    "streams": [
        {
            "codec_type": "audio",
            "codec_name": "pcm_s16le",
            "sample_rate": "16000",
            "channels": 1,
            "duration": "10.0",
        }
    ],
}


DEFAULT_SCENARIO: dict[str, Any] = {
    "resolve_exit": 0,
    "resolve_stdout": "fake\tabc123\n",
    "resolve_stderr": "",
    "resolve_metadata": {
        "_type": "video",
        "extractor": "fake",
        "id": "abc123",
        "is_live": False,
        "webpage_url": "https://example.com/watch?v=abc123",
    },
    "download_exit": 0,
    "download_stdout": "",
    "download_stderr": "",
    "download_sleep": "0",
    "write_video": True,
    "video_ext": "mp4",
    "video_body": "fake video payload\n",
    "write_info": True,
    "info_ext": "json",
    "info_body": '{"id":"abc123","extractor":"fake"}\n',
    "write_thumbnail": False,
    "thumbnail_ext": "webp",
    "thumbnail_body": "thumb\n",
    "write_subtitle": False,
    "subtitle_ext": "vtt",
    "subtitle_body": "WEBVTT\n",
    "ffmpeg_exit": 0,
    "ffmpeg_stderr": "",
    "write_audio_on_success": True,
    "audio_body": "RIFFfake-wav\n",
    "remux_body": "fake remuxed mp4\n",
    "ffprobe_exit": 0,
    "ffprobe_stdout": json.dumps(VIDEO_PROBE) + "\n",
    "ffprobe_stderr": "",
    "ffprobe_responses": {
        ".mp4": {"exit": 0, "stdout": json.dumps(VIDEO_PROBE) + "\n", "stderr": ""},
        ".webm": {"exit": 0, "stdout": json.dumps(WEBM_PROBE) + "\n", "stderr": ""},
        ".wav": {"exit": 0, "stdout": json.dumps(WAV_PROBE) + "\n", "stderr": ""},
    },
}


YT_DLP_SCRIPT = r"""#!/usr/bin/env bash
set -u

state_dir=${FAKE_TOOL_STATE_DIR:?}
scenario_dir=${FAKE_TOOL_SCENARIO_DIR:?}
source "$scenario_dir/scenario.env"

log_call() {
  local mode=$1
  shift
  local call_dir
  call_dir=$(mktemp -d "$state_dir/calls/call.XXXXXX")
  printf '%s' 'yt-dlp' > "$call_dir/tool"
  printf '%s' "$mode" > "$call_dir/mode"
  printf '%s\0' "$@" > "$call_dir/argv"
  printf '%s\0' \
    HOME "${HOME-}" PATH "${PATH-}" VA_HOME "${VA_HOME-}" \
    VA_COOKIES "${VA_COOKIES-}" \
    VA_COOKIES_FROM_BROWSER "${VA_COOKIES_FROM_BROWSER-}" \
    YTDLP_NO_PLUGINS "${YTDLP_NO_PLUGINS-}" \
    XDG_CONFIG_HOME "${XDG_CONFIG_HOME-}" > "$call_dir/env"
}

has_output=0
wants_json=0
wants_version=0
previous=''
for argument in "$@"; do
  if [ "$previous" = '-o' ] || [ "$argument" = '-o' ]; then
    has_output=1
  fi
  case "$argument" in
    --dump-json|--dump-single-json|-J) wants_json=1 ;;
    --version) wants_version=1 ;;
  esac
  previous=$argument
done

if [ "$wants_version" -eq 1 ]; then
  log_call version "$@"
  printf '%s\n' '2026.07.24'
  exit 0
fi

if [ "$has_output" -eq 0 ]; then
  log_call resolve "$@"
  if [ "$wants_json" -eq 1 ]; then
    cat "$scenario_dir/resolve.metadata"
  else
    cat "$scenario_dir/resolve.stdout"
  fi
  cat "$scenario_dir/resolve.stderr" >&2
  exit "$RESOLVE_EXIT"
fi

log_call download "$@"
if [ "$DOWNLOAD_SLEEP" != '0' ]; then
  sleep "$DOWNLOAD_SLEEP"
fi

first_video=''
while [ "$#" -gt 0 ]; do
  if [ "$1" != '-o' ] || [ "$#" -lt 2 ]; then
    shift
    continue
  fi
  template=$2
  shift 2
  case "$template" in
    infojson:*)
      if [ "$WRITE_INFO" -eq 1 ]; then
        output=${template#infojson:}
        output=${output//'%(ext)s'/$INFO_EXT}
        mkdir -p "$(dirname "$output")"
        cp "$scenario_dir/info.body" "$output"
      fi
      ;;
    thumbnail:*)
      if [ "$WRITE_THUMBNAIL" -eq 1 ]; then
        output=${template#thumbnail:}
        output=${output//'%(ext)s'/$THUMBNAIL_EXT}
        mkdir -p "$(dirname "$output")"
        cp "$scenario_dir/thumbnail.body" "$output"
      fi
      ;;
    subtitle:*)
      if [ "$WRITE_SUBTITLE" -eq 1 ]; then
        output=${template#subtitle:}
        output=${output//'%(ext)s'/$SUBTITLE_EXT}
        mkdir -p "$(dirname "$output")"
        cp "$scenario_dir/subtitle.body" "$output"
      fi
      ;;
    *)
      if [ "$WRITE_VIDEO" -eq 1 ]; then
        output=${template//'%(ext)s'/$VIDEO_EXT}
        mkdir -p "$(dirname "$output")"
        cp "$scenario_dir/video.body" "$output"
        if [ -z "$first_video" ]; then
          first_video=$output
        fi
      fi
      ;;
  esac
done

if [ -n "$first_video" ]; then
  printf '%s\n' "$first_video" > "$scenario_dir/last-video-path"
fi
cat "$scenario_dir/download.stdout"
cat "$scenario_dir/download.stderr" >&2
exit "$DOWNLOAD_EXIT"
"""


FFMPEG_SCRIPT = r"""#!/usr/bin/env bash
set -u

state_dir=${FAKE_TOOL_STATE_DIR:?}
scenario_dir=${FAKE_TOOL_SCENARIO_DIR:?}
source "$scenario_dir/scenario.env"

call_dir=$(mktemp -d "$state_dir/calls/call.XXXXXX")
printf '%s' 'ffmpeg' > "$call_dir/tool"
printf '%s\0' "$@" > "$call_dir/argv"

for argument in "$@"; do
  if [ "$argument" = '-version' ] || [ "$argument" = '--version' ]; then
    printf '%s\n' 'ffmpeg version 7.1-fake'
    exit 0
  fi
done

output=''
for argument in "$@"; do
  output=$argument
done
if [ "$FFMPEG_EXIT" -eq 0 ] && [ -n "$output" ]; then
  mkdir -p "$(dirname "$output")"
  case "$output" in
    *.wav|*.wav.tmp)
      if [ "$WRITE_AUDIO_ON_SUCCESS" -eq 1 ]; then
        cp "$scenario_dir/audio.body" "$output"
      fi
      ;;
    *) cp "$scenario_dir/remux.body" "$output" ;;
  esac
fi
cat "$scenario_dir/ffmpeg.stderr" >&2
exit "$FFMPEG_EXIT"
"""


FFPROBE_SCRIPT = r"""#!/usr/bin/env bash
set -u

state_dir=${FAKE_TOOL_STATE_DIR:?}
scenario_dir=${FAKE_TOOL_SCENARIO_DIR:?}
source "$scenario_dir/scenario.env"

call_dir=$(mktemp -d "$state_dir/calls/call.XXXXXX")
printf '%s' 'ffprobe' > "$call_dir/tool"
printf '%s\0' "$@" > "$call_dir/argv"

for argument in "$@"; do
  if [ "$argument" = '-version' ] || [ "$argument" = '--version' ]; then
    printf '%s\n' 'ffprobe version 7.1-fake'
    exit 0
  fi
done

target=''
for argument in "$@"; do
  target=$argument
done
response_key=default
case "$target" in
  *.mp4) response_key=mp4 ;;
  *.webm) response_key=webm ;;
  *.wav) response_key=wav ;;
esac
if [ -f "$scenario_dir/ffprobe.$response_key.stdout" ]; then
  cat "$scenario_dir/ffprobe.$response_key.stdout"
  cat "$scenario_dir/ffprobe.$response_key.stderr" >&2
  response_exit=$(cat "$scenario_dir/ffprobe.$response_key.exit")
  exit "$response_exit"
fi
cat "$scenario_dir/ffprobe.stdout"
cat "$scenario_dir/ffprobe.stderr" >&2
exit "$FFPROBE_EXIT"
"""


PYTHON_WRAPPER_TEMPLATE = r"""#!/usr/bin/env bash
set -u
if [ "${1-}" = '-c' ] && [[ "${2-}" == *'derive_output_dir'* ]]; then
  extractor=${3-}
  video_id=${4-}
  output_root=${5-}
  printf '%s/%s-%s\n' "${output_root%/}" "$extractor" "$video_id"
  exit 0
fi
exec __REAL_PYTHON__ "$@"
"""


@dataclass
class FakeToolHarness:
    root: Path
    scenario: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.fake_home = self.root / "fake-home"
        self.bin_dir = self.fake_home / "bin"
        self.state_dir = self.root / "fake-tool-state"
        self.scenario_dir = self.state_dir / "scenario"
        self.calls_dir = self.state_dir / "calls"

    def install(self) -> None:
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.scenario_dir.mkdir(parents=True, exist_ok=True)
        self.calls_dir.mkdir(parents=True, exist_ok=True)
        merged = dict(DEFAULT_SCENARIO)
        merged.update(self.scenario)
        self._write_scenario(merged)
        self._write_executable(self.bin_dir / "yt-dlp", YT_DLP_SCRIPT)
        self._write_executable(self.bin_dir / "ffmpeg", FFMPEG_SCRIPT)
        self._write_executable(self.bin_dir / "ffprobe", FFPROBE_SCRIPT)
        python_wrapper = PYTHON_WRAPPER_TEMPLATE.replace(
            "__REAL_PYTHON__", shlex.quote(sys.executable)
        )
        self._write_executable(self.bin_dir / "python3", python_wrapper)

    def build_env(self, **extra: str) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self.root / "home")
        env["VA_HOME"] = str(self.fake_home)
        env["FAKE_TOOL_SCENARIO_DIR"] = str(self.scenario_dir)
        env["FAKE_TOOL_STATE_DIR"] = str(self.state_dir)
        env["XDG_CONFIG_HOME"] = str(self.root / "xdg")
        env.setdefault("VA_YTDLP_JS_RUNTIME", "none")
        env.update(extra)
        return env

    def calls(self, tool: str | None = None, mode: str | None = None) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for call_dir in sorted(self.calls_dir.iterdir(), key=lambda path: path.stat().st_mtime_ns):
            record: dict[str, Any] = {
                "tool": (call_dir / "tool").read_text(encoding="utf-8"),
                "argv": self._read_nul_fields(call_dir / "argv"),
            }
            mode_path = call_dir / "mode"
            if mode_path.exists():
                record["mode"] = mode_path.read_text(encoding="utf-8")
            env_path = call_dir / "env"
            if env_path.exists():
                fields = self._read_nul_fields(env_path)
                record["env"] = dict(zip(fields[::2], fields[1::2], strict=True))
            records.append(record)
        if tool is not None:
            records = [record for record in records if record.get("tool") == tool]
        if mode is not None:
            records = [record for record in records if record.get("mode") == mode]
        return records

    def _write_scenario(self, scenario: dict[str, Any]) -> None:
        variables = {
            "RESOLVE_EXIT": scenario["resolve_exit"],
            "DOWNLOAD_EXIT": scenario["download_exit"],
            "DOWNLOAD_SLEEP": scenario["download_sleep"],
            "WRITE_VIDEO": int(bool(scenario["write_video"])),
            "VIDEO_EXT": scenario["video_ext"],
            "WRITE_INFO": int(bool(scenario["write_info"])),
            "INFO_EXT": scenario["info_ext"],
            "WRITE_THUMBNAIL": int(bool(scenario["write_thumbnail"])),
            "THUMBNAIL_EXT": scenario["thumbnail_ext"],
            "WRITE_SUBTITLE": int(bool(scenario["write_subtitle"])),
            "SUBTITLE_EXT": scenario["subtitle_ext"],
            "FFMPEG_EXIT": scenario["ffmpeg_exit"],
            "WRITE_AUDIO_ON_SUCCESS": int(bool(scenario["write_audio_on_success"])),
            "FFPROBE_EXIT": scenario["ffprobe_exit"],
        }
        env_text = "\n".join(
            f"{key}={shlex.quote(str(value))}" for key, value in variables.items()
        ) + "\n"
        (self.scenario_dir / "scenario.env").write_text(env_text, encoding="utf-8")

        text_files = {
            "resolve.stdout": scenario["resolve_stdout"],
            "resolve.stderr": scenario["resolve_stderr"],
            "resolve.metadata": json.dumps(scenario["resolve_metadata"]) + "\n",
            "download.stdout": scenario["download_stdout"],
            "download.stderr": scenario["download_stderr"],
            "video.body": scenario["video_body"],
            "info.body": scenario["info_body"],
            "thumbnail.body": scenario["thumbnail_body"],
            "subtitle.body": scenario["subtitle_body"],
            "ffmpeg.stderr": scenario["ffmpeg_stderr"],
            "audio.body": scenario["audio_body"],
            "remux.body": scenario["remux_body"],
            "ffprobe.stdout": scenario["ffprobe_stdout"],
            "ffprobe.stderr": scenario["ffprobe_stderr"],
        }
        for name, content in text_files.items():
            (self.scenario_dir / name).write_text(str(content), encoding="utf-8")

        for suffix, response in scenario.get("ffprobe_responses", {}).items():
            key = suffix.removeprefix(".")
            (self.scenario_dir / f"ffprobe.{key}.stdout").write_text(
                str(response.get("stdout", "")), encoding="utf-8"
            )
            (self.scenario_dir / f"ffprobe.{key}.stderr").write_text(
                str(response.get("stderr", "")), encoding="utf-8"
            )
            (self.scenario_dir / f"ffprobe.{key}.exit").write_text(
                str(response.get("exit", 0)), encoding="utf-8"
            )

    @staticmethod
    def _read_nul_fields(path: Path) -> list[str]:
        fields = path.read_bytes().split(b"\0")
        if fields and fields[-1] == b"":
            fields.pop()
        return [field.decode("utf-8") for field in fields]

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
