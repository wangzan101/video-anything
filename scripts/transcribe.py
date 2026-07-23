#!/usr/bin/env python3
"""transcribe.py — speech-to-text for the video-anything skill.

Usage:
    python3 scripts/transcribe.py <AUDIO_OR_VIDEO> [--engine local|cloud]
                                   [--model small] [--lang auto] [--out DIR]

Writes, next to the input (or into --out):
    transcript.md   (with [mm:ss] timestamps)
    transcript.txt  (plain text)

Engine selection (--engine, default "local"):
    local  - runs fully on-device, no network/API key ever used.
             1) faster-whisper (pip install faster-whisper) — fast, no key
             2) openai-whisper CLI ("whisper"/"whisper-cli" on PATH) — fallback
    cloud  - NOT implemented in M1. This is an explicit-opt-in placeholder:
             selecting it prints a message and exits non-zero. It never runs
             just because GROQ_API_KEY happens to be set (R5: no silent
             upload of the user's media).
"""
import argparse
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # adds scripts/
from lib.asr_utils import parse_vtt, segments_to_markdown, segments_to_text  # noqa: E402


def write_outputs(out_dir: str, segments) -> None:
    """segments: list of (start_seconds, text)."""
    md_path = os.path.join(out_dir, "transcript.md")
    txt_path = os.path.join(out_dir, "transcript.txt")
    with open(md_path, "w", encoding="utf-8") as md:
        md.write(segments_to_markdown(segments))
    with open(txt_path, "w", encoding="utf-8") as txt:
        txt.write(segments_to_text(segments))
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
    write_outputs(out_dir, [(s.start, s.text) for s in seg_iter])
    return True


def run_whisper_cli(audio: str, out_dir: str, model: str, lang: str) -> bool:
    from shutil import which

    exe = next((cand for cand in ("whisper", "whisper-cli") if which(cand)), None)
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
        # openai-whisper names it after the input stem; fall back to any .vtt
        # it wrote into out_dir.
        cands = [f for f in os.listdir(out_dir) if f.endswith(".vtt")]
        vtt = os.path.join(out_dir, cands[0]) if cands else None
    if not vtt or not os.path.exists(vtt):
        print(f"ERROR: {exe} ran but produced no .vtt output in {out_dir}",
              file=sys.stderr)
        return False
    with open(vtt, encoding="utf-8") as f:
        segments = parse_vtt(f.read())
    write_outputs(out_dir, segments)
    return True


def run_local(audio: str, out_dir: str, model: str, lang: str) -> int:
    if run_faster_whisper(audio, out_dir, model, lang):
        return 0
    if run_whisper_cli(audio, out_dir, model, lang):
        return 0
    print(
        "ERROR: no local ASR engine found. Install one:\n"
        "  pip install faster-whisper      (recommended)\n"
        "  brew install whisper-cpp        (provides whisper-cli)\n"
        "  pip install openai-whisper      (provides whisper)\n"
        "See scripts/bootstrap.sh for other dependency setup.",
        file=sys.stderr,
    )
    return 1


def run_cloud() -> int:
    # M1 stub: cloud transcription is not implemented yet (see M3). This must
    # never run implicitly off the presence of GROQ_API_KEY — --engine cloud
    # is the only opt-in, and even then it is a no-op placeholder for now.
    print(
        "云引擎将在 M3 实装,当前请用默认 --engine local。\n"
        "(Cloud engine is not implemented in M1; use --engine local.)",
        file=sys.stderr,
    )
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="audio or video file")
    ap.add_argument("--engine", choices=("local", "cloud"), default="local",
                    help="transcription engine (default local; cloud is an "
                         "M1 stub, see --help notes)")
    ap.add_argument("--model", default="small",
                    help="whisper model: tiny/base/small/medium/large (default small)")
    ap.add_argument("--lang", default="auto",
                    help="language code (e.g. zh, en) or 'auto' (default auto)")
    ap.add_argument("--out", default=None, help="output dir (default: input's dir)")
    args = ap.parse_args()

    if args.engine == "cloud":
        return run_cloud()

    if not os.path.exists(args.input):
        print(f"ERROR: no such file: {args.input}", file=sys.stderr)
        return 2
    out_dir = args.out or os.path.dirname(os.path.abspath(args.input))
    os.makedirs(out_dir, exist_ok=True)

    return run_local(args.input, out_dir, args.model, args.lang)


if __name__ == "__main__":
    raise SystemExit(main())
