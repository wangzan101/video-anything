#!/usr/bin/env python3
"""Validated single-video download pipeline (Phase 2 initial publish path)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from scripts.lib.capabilities import CapabilityError, choose_js_runtime

USAGE, DEPENDENCY, RESOLVE, DOWNLOAD, NORMALIZE, MEDIA, PUBLISH = 2, 10, 20, 30, 40, 50, 60


class Failure(Exception):
    def __init__(self, code: int, reason: str, detail: str = "") -> None:
        self.code, self.reason, self.detail = code, reason, detail


def redact(url: str) -> str:
    parts = urlsplit(url)
    query = [(key, "<redacted>") for key, _ in parse_qsl(parts.query, keep_blank_values=True)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise Failure(DEPENDENCY, f"missing_{name}")
    return path


def runtime() -> dict[str, str | None]:
    choice = os.environ.get("VA_YTDLP_JS_RUNTIME", "auto")
    deno, node = shutil.which("deno"), shutil.which("node")
    def version(path: str | None) -> str | None:
        if not path:
            return None
        try:
            return subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5, check=False).stdout
        except (OSError, subprocess.TimeoutExpired):
            return None
    try:
        return choose_js_runtime(choice, deno_path=deno, deno_version=version(deno), node_path=node, node_version=version(node))
    except CapabilityError as exc:
        raise Failure(DEPENDENCY, str(exc)) from exc


def cookie_args() -> list[str]:
    if os.environ.get("VA_COOKIES_FROM_BROWSER"):
        return ["--cookies-from-browser", os.environ["VA_COOKIES_FROM_BROWSER"]]
    if os.environ.get("VA_COOKIES"):
        return ["--cookies", os.environ["VA_COOKIES"]]
    return []


def js_args(selected: dict[str, str | None]) -> list[str]:
    if selected["runtime"] == "none":
        return ["--no-js-runtimes"]
    return ["--no-js-runtimes", "--js-runtimes", f"{selected['runtime']}:{selected['path']}"]


def invoke(argv: list[str], *, timeout: int, env: dict[str, str], timeout_code: int = DOWNLOAD) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise Failure(timeout_code, "timeout", str(exc)) from exc
    except OSError as exc:
        raise Failure(DEPENDENCY, "exec_failed", str(exc)) from exc


def resolve(url: str, ytdlp: str, js: dict[str, str | None], env: dict[str, str]) -> dict[str, object]:
    argv = [ytdlp, "--ignore-config", *js_args(js), *cookie_args(), "--no-warnings", "--no-playlist", "--match-filters", "!is_live", "--dump-single-json", "--skip-download", url]
    result = invoke(argv, timeout=120, env=env, timeout_code=RESOLVE)
    if result.returncode:
        raise Failure(RESOLVE, "resolve_failed", result.stderr[-1000:])
    try:
        metadata = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Failure(RESOLVE, "invalid_metadata", str(exc)) from exc
    if metadata.get("_type") == "playlist" or metadata.get("entries") or metadata.get("is_live") is True:
        raise Failure(RESOLVE, "not_single_video")
    if metadata.get("_type") not in {None, "video"} or not metadata.get("extractor") or not metadata.get("id"):
        raise Failure(RESOLVE, "not_single_video")
    return metadata


def download(url: str, stage: Path, ytdlp: str, js: dict[str, str | None], env: dict[str, str]) -> None:
    argv = [ytdlp, "--ignore-config", *js_args(js), *cookie_args(), "--no-warnings", "--no-playlist", "--match-filters", "!is_live", "--retries", "10", "--fragment-retries", "10", "--extractor-retries", "3", "--file-access-retries", "3", "--socket-timeout", "30", "-f", "bv*[vcodec^=avc1]+ba[acodec^=mp4a]/b[ext=mp4]", "--merge-output-format", "mp4", "--write-info-json", "--write-thumbnail", "--write-subs", "--sub-langs", "zh-Hans,zh,en", "--convert-subs", "vtt", "-o", str(stage / "video.%(ext)s"), "-o", f"infojson:{stage / 'info.%(ext)s'}", "-o", f"thumbnail:{stage / 'thumbnail.%(ext)s'}", "-o", f"subtitle:{stage / 'sub.%(ext)s'}", url]
    result = invoke(argv, timeout=14400, env=env)
    if result.returncode:
        raise Failure(DOWNLOAD, "download_failed", result.stderr[-1000:])
    if not list(stage.glob("video.*")):
        raise Failure(DOWNLOAD, "media_missing")


def probe(path: Path, ffprobe: str, env: dict[str, str]) -> dict[str, object]:
    argv = [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise Failure(MEDIA, "ffprobe_timeout", str(exc)) from exc
    if result.returncode:
        raise Failure(MEDIA, "unparseable_video", result.stderr[-1000:])
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise Failure(MEDIA, "unparseable_video", str(exc)) from exc


def stream_list(data: dict[str, object], kind: str) -> list[dict[str, object]]:
    return [item for item in data.get("streams", []) if isinstance(item, dict) and item.get("codec_type") == kind]


def media_duration(data: dict[str, object]) -> float:
    value = data.get("format", {}).get("duration") if isinstance(data.get("format"), dict) else None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise Failure(MEDIA, "missing_duration") from exc


def normalize(stage: Path, ffmpeg: str, ffprobe: str, env: dict[str, str]) -> Path:
    candidates = [p for p in stage.glob("video.*") if p.suffix.lower() not in {".json", ".jpg", ".jpeg", ".png", ".webp", ".vtt"}]
    if not candidates:
        raise Failure(NORMALIZE, "media_missing")
    source = candidates[0]
    data = probe(source, ffprobe, env)
    videos, audios = stream_list(data, "video"), stream_list(data, "audio")
    if not videos:
        raise Failure(MEDIA, "no_video_stream")
    fmt = str(data.get("format", {}).get("format_name", ""))
    vc = str(videos[0].get("codec_name", ""))
    ac = str(audios[0].get("codec_name", "")) if audios else ""
    compatible = "mp4" in fmt and vc in {"h264", "avc1"} and (not audios or ac in {"aac", "mp4a"})
    if compatible:
        target = stage / "video.mp4"
        if source != target:
            source.replace(target)
        return target
    can_remux = vc in {"h264", "avc1"} and (not audios or ac in {"aac", "mp4a"})
    if not can_remux:
        raise Failure(NORMALIZE, "incompatible_container_or_codec")
    target = stage / "video.mp4"
    try:
        result = subprocess.run([ffmpeg, "-y", "-i", str(source), "-c", "copy", str(target)], capture_output=True, text=True, timeout=14400, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise Failure(NORMALIZE, "timeout", str(exc)) from exc
    if result.returncode:
        raise Failure(NORMALIZE, "remux_failed", result.stderr[-1000:])
    checked = probe(target, ffprobe, env)
    if "mp4" not in str(checked.get("format", {}).get("format_name", "")):
        raise Failure(NORMALIZE, "remux_not_mp4")
    return target


def validate(stage: Path, metadata: dict[str, object], ffmpeg: str, ffprobe: str, env: dict[str, str]) -> dict[str, object]:
    video, info = stage / "video.mp4", stage / "info.json"
    video_data = probe(video, ffprobe, env)
    videos, audios = stream_list(video_data, "video"), stream_list(video_data, "audio")
    if not videos:
        raise Failure(MEDIA, "no_video_stream")
    if not audios:
        raise Failure(MEDIA, "no_audio")
    if not info.exists():
        raise Failure(MEDIA, "info_missing")
    try:
        info_data = json.loads(info.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Failure(MEDIA, "info_invalid", str(exc)) from exc
    if info_data.get("id") != metadata.get("id") or info_data.get("extractor") != metadata.get("extractor"):
        raise Failure(MEDIA, "info_identity_mismatch")
    audio = stage / "audio.wav"
    try:
        result = subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(audio)], capture_output=True, text=True, timeout=14400, env=env, check=False)
    except subprocess.TimeoutExpired as exc:
        raise Failure(MEDIA, "timeout", str(exc)) from exc
    if result.returncode or not audio.exists():
        raise Failure(MEDIA, "audio_extract_failed", result.stderr[-1000:])
    audio_data = probe(audio, ffprobe, env)
    wav_streams = stream_list(audio_data, "audio")
    if not wav_streams or str(audio_data.get("format", {}).get("format_name", "")).lower() != "wav":
        raise Failure(MEDIA, "audio_invalid")
    wav = wav_streams[0]
    if wav.get("codec_name") not in {"pcm_s16le", "pcm_s24le", "pcm_s32le"} or str(wav.get("sample_rate")) != "16000" or int(wav.get("channels", 0)) != 1:
        raise Failure(MEDIA, "audio_invalid")
    vd, ad = media_duration(video_data), media_duration(audio_data)
    if abs(ad - vd) > min(5.0, max(1.0, vd * 0.01)):
        raise Failure(MEDIA, "audio_duration_mismatch")
    return {"video": {"path": "video.mp4", "bytes": video.stat().st_size, "duration": vd, "container": "mp4", "vcodec": videos[0].get("codec_name"), "acodec": audios[0].get("codec_name")}, "audio": {"path": "audio.wav", "bytes": audio.stat().st_size, "duration": ad, "codec": wav.get("codec_name"), "sample_rate": 16000, "channels": 1}, "info": {"path": "info.json", "bytes": info.stat().st_size}}


def write_manifest(stage: Path, metadata: dict[str, object], url: str, generation: str, tools: tuple[str, str, str, dict[str, str | None]], artifacts: dict[str, object]) -> None:
    ytdlp, ffmpeg, ffprobe, js = tools
    manifest = {"schema_version": 1, "status": "ready", "error": None, "source": {"url_redacted": redact(url), "url_sha256": sha256(url)}, "extractor": metadata["extractor"], "id": metadata["id"], "generation": generation, "publish_mode": "initial", "tools": {"yt_dlp": ytdlp, "ffmpeg": ffmpeg, "ffprobe": ffprobe, "js_runtime": js}, "artifacts": artifacts, "warnings": []}
    tmp = stage / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    with tmp.open("rb") as handle:
        os.fsync(handle.fileno())
    tmp.replace(stage / "manifest.json")
    (stage / "fetch.log").write_text(f"status=ready\nurl_sha256={sha256(url)}\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("url")
        parser.add_argument("output_root", nargs="?", default="./video-out")
        parser.add_argument("--force", action="store_true")
        args = parser.parse_args(argv)
        parsed = urlsplit(args.url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise Failure(USAGE, "invalid_url")
        ytdlp, ffmpeg, ffprobe, js = require_tool("yt-dlp"), require_tool("ffmpeg"), require_tool("ffprobe"), runtime()
        env = os.environ.copy(); env["YTDLP_NO_PLUGINS"] = "1"
        metadata = resolve(args.url, ytdlp, js, env)
        root = Path(args.output_root).expanduser().resolve(); final = root / f"{metadata['extractor']}-{metadata['id']}"
        if final.exists():
            raise Failure(PUBLISH, "existing_final_requires_phase3")
        root.mkdir(parents=True, exist_ok=True)
        generation = str(uuid.uuid4()); stage = root / ".staging" / f"{metadata['extractor']}-{metadata['id']}.{generation}"; stage.mkdir(parents=True, exist_ok=False)
        download(args.url, stage, ytdlp, js, env)
        normalize(stage, ffmpeg, ffprobe, env)
        artifacts = validate(stage, metadata, ffmpeg, ffprobe, env)
        write_manifest(stage, metadata, args.url, generation, (ytdlp, ffmpeg, ffprobe, js), artifacts)
        stage.replace(final)
        print(final)
        return 0
    except Failure as failure:
        print(f"ERROR: {failure.reason}{(': ' + failure.detail) if failure.detail else ''}", file=sys.stderr)
        return failure.code
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: internal_failure: {exc}", file=sys.stderr)
        return PUBLISH


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
