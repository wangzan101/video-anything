import re

def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

_TS = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.\d{3}\s*-->")

def parse_vtt(text: str) -> list[tuple[int, str]]:
    segs, start, buf = [], None, []
    for line in text.splitlines():
        m = _TS.match(line)
        if m:
            if start is not None and buf:
                segs.append((start, " ".join(buf))); buf = []
            h, mn, s = map(int, m.groups())
            start = h * 3600 + mn * 60 + s
        elif line and not line.startswith(("WEBVTT", "NOTE")) and "-->" not in line:
            buf.append(line.strip())
    if start is not None and buf:
        segs.append((start, " ".join(buf)))
    return segs
