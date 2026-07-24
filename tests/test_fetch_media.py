from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.fetch import Failure, normalize, validate


FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


def require_media_tools() -> tuple[str, str]:
    if not FFMPEG or not FFPROBE:
        pytest.fail("Phase 4 local integration requires ffmpeg and ffprobe")
    return FFMPEG, FFPROBE


def make_media(root: Path, *, audio: bool = True, container: str = "mp4") -> Path:
    ffmpeg, _ = require_media_tools()
    output = root / f"input.{container}"
    argv = [ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=160x90:d=1"]
    if audio:
        argv += ["-f", "lavfi", "-i", "sine=frequency=1000:duration=1"]
    argv += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if audio:
        argv += ["-c:a", "aac", "-shortest"]
    argv.append(str(output))
    subprocess.run(argv, check=True, capture_output=True)
    return output


@pytest.mark.phase4_local
def test_real_h264_aac_mp4_passes_complete_validation(tmp_path: Path) -> None:
    ffmpeg, ffprobe = require_media_tools()
    source = make_media(tmp_path)
    stage = tmp_path / "stage"
    stage.mkdir()
    source.rename(stage / "video.mp4")
    (stage / "info.json").write_text(json.dumps({"id": "abc123", "extractor": "fake"}), encoding="utf-8")
    result = validate(stage, {"id": "abc123", "extractor": "fake"}, ffmpeg, ffprobe, os.environ.copy())
    assert result["video"]["container"] == "mp4"
    assert result["audio"]["sample_rate"] == 16000


@pytest.mark.phase4_local
def test_real_h264_aac_mkv_is_remuxed_to_mp4(tmp_path: Path) -> None:
    ffmpeg, ffprobe = require_media_tools()
    source = make_media(tmp_path, container="mkv")
    stage = tmp_path / "stage"
    stage.mkdir()
    source.rename(stage / "video.mkv")
    normalized = normalize(stage, ffmpeg, ffprobe, os.environ.copy())
    assert normalized.name == "video.mp4"
    assert "mp4" in subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=format_name", "-of", "default=nw=1:nk=1", str(normalized)], check=True, capture_output=True, text=True).stdout


@pytest.mark.phase4_local
def test_real_video_without_audio_is_media_error(tmp_path: Path) -> None:
    ffmpeg, ffprobe = require_media_tools()
    source = make_media(tmp_path, audio=False)
    stage = tmp_path / "stage"
    stage.mkdir()
    source.rename(stage / "video.mp4")
    (stage / "info.json").write_text(json.dumps({"id": "abc123", "extractor": "fake"}), encoding="utf-8")
    with pytest.raises(Failure, match="no_audio"):
        validate(stage, {"id": "abc123", "extractor": "fake"}, ffmpeg, ffprobe, os.environ.copy())
