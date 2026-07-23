#!/usr/bin/env python3
"""transcribe.py — local speech-to-text for the video-anything skill.

Usage:
    python3 scripts/transcribe.py <AUDIO_OR_VIDEO> [--model small] [--lang auto] [--out DIR]

Writes, next to the input (or into --out):
    transcript.md   (with [mm:ss] timestamps)
    transcript.txt  (plain text)

Engine preference:
    1) faster-whisper (pip install faster-whisper)  — fast, no API key
    2) openai-whisper CLI ("whisper" on PATH)        — fallback

No external API / key is ever used. Everything runs locally.
"""
import argparse
import os
import subprocess
import sys


def fmt_ts(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def write_outputs(out_dir: str, segments) -> None:
    """segments: iterable of (start_seconds, text)."""
    md_path = os.path.join(out_dir, "transcript.md")
    txt_path = os.path.join(out_dir, "transcript.txt")
    with open(md_path, "w", encoding="utf-8") as md, \
         open(txt_path, "w", encoding="utf-8") as txt:
        md.write("# Transcript\n\n")
        for start, text in segments:
            text = text.strip()
            if not text:
                continue
            md.write(f"`[{fmt_ts(start)}]` {text}\n\n")
            txt.write(text + "\n")
    print(f">> wrote {md_path}")
    print(f">> wrote {txt_path}")


def run_faster_whisper(audio: str, out_dir: str, model: str, lang: str) -> bool:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return False
    print(f">> transcribing with faster-whisper (model={model}) ...")
    m = WhisperModel(model, device="auto", compute_type="int8")
    seg_iter, info = m.transcribe(
        audio, language=None if lang == "auto" else lang, vad_filter=True
    )
    print(f">> detected language: {info.language} (p={info.language_probability:.2f})")
    write_outputs(out_dir, ((s.start, s.text) for s in seg_iter))
    return True


def run_whisper_cli(audio: str, out_dir: str, model: str, lang: str) -> bool:
    exe = None
    for cand in ("whisper", "whisper-cli"):
        from shutil import which
        if which(cand):
            exe = cand
            break
    if not exe:
        return False
    print(f">> transcribing with {exe} CLI (model={model}) ...")
    cmd = [exe, audio, "--model", model, "--output_dir", out_dir,
           "--output_format", "vtt"]
    if lang != "auto":
        cmd += ["--language", lang]
    subprocess.run(cmd, check=True)
    # Parse the produced .vtt into our md/txt format.
    vtt = os.path.join(out_dir, os.path.splitext(os.path.basename(audio))[0] + ".vtt")
    if not os.path.exists(vtt):
        # openai-whisper names it after the input stem
        cands = [f for f in os.listdir(out_dir) if f.endswith(".vtt")]
        vtt = os.path.join(out_dir, cands[0]) if cands else None
    if vtt and os.path.exists(vtt):
        write_outputs(out_dir, _parse_vtt(vtt))
    return True


def _parse_vtt(path: str):
    import re
    segs = []
    start = None
    buf = []
    ts_re = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.\d{3}\s*-->")
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            m = ts_re.match(line)
            if m:
                if start is not None and buf:
                    segs.append((start, " ".join(buf)))
                    buf = []
                h, mnt, s = int(m.group(1)), int(m.group(2)), int(m.group(3))
                start = h * 3600 + mnt * 60 + s
            elif line and not line.startswith(("WEBVTT", "NOTE")) and "-->" not in line:
                buf.append(line)
    if start is not None and buf:
        segs.append((start, " ".join(buf)))
    return segs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="audio or video file")
    ap.add_argument("--model", default="small",
                    help="whisper model: tiny/base/small/medium/large (default small)")
    ap.add_argument("--lang", default="auto",
                    help="language code (e.g. zh, en) or 'auto' (default auto)")
    ap.add_argument("--out", default=None, help="output dir (default: input's dir)")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: no such file: {args.input}", file=sys.stderr)
        return 2
    out_dir = args.out or os.path.dirname(os.path.abspath(args.input))
    os.makedirs(out_dir, exist_ok=True)

    if run_faster_whisper(args.input, out_dir, args.model, args.lang):
        return 0
    if run_whisper_cli(args.input, out_dir, args.model, args.lang):
        return 0
    print("ERROR: no ASR engine found. Install one:\n"
          "  pip install faster-whisper      (recommended)\n"
          "  brew install whisper-cpp        (or)\n", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
