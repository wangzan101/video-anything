# video-anything Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一个跨工具 Agent Skill:给一个视频链接,产出无水印视频/音频/文案/字幕/封面/元数据,并由 agent 做 4 种 AI 加工;零 key(默认)、可离线、装上即用。

**Architecture:** 方案 A —— SKILL.md 路由 + 独立脚本(bootstrap/fetch/transcribe/check),agent 负责编排与 AI playbook。纯逻辑抽到 `scripts/lib/asr_utils.py` 做 TDD 单测;网络/二进制部分靠 `tests/smoke.sh` 冒烟。

**Tech Stack:** bash、Python 3(标准库 + faster-whisper/whisper CLI 二选一)、yt-dlp、ffmpeg、pytest。

## Global Constraints

- 平台一等公民(v1):YouTube / Bilibili / Twitter-X / 抖音 / 快手;视频号 = 二期。
- 依赖**自动 bootstrap** 到 `~/.video-anything/`(bin + venv),不污染系统;用户不手动 install。
- 下载的二进制**必须校验 SHA256**,来源钉版本(yt-dlp 官方 release;ffmpeg 按 OS×arch 第三方源,失败回退系统 ffmpeg)。
- 本地 ASR **不假设 `pip install faster-whisper` 成功**(Py3.14/ctranslate2 可能无 wheel):就位顺序 = 系统 whisper → 兼容 Python(3.11/3.12)venv 装 faster-whisper → whisper.cpp → 报错。
- 云 ASR **仅显式 opt-in**(`--engine cloud`),不因 `GROQ_API_KEY` 存在隐式触发;云路径需大小检测 + 超限分片(~25MB)。
- 字幕优先**只信人工字幕**;自动字幕仍走 ASR。
- 输出目录 `video-out/<extractor>-<id>/`;同 URL 默认复用,`--force` 覆盖。
- 不承诺「秒级」;红线:不碰 DRM/付费墙/大会员。License MIT。
- DRY / YAGNI / TDD / 频繁提交。

---

## File Structure

| 文件 | 职责 |
|---|---|
| `scripts/lib/asr_utils.py` | 纯函数:时间戳、VTT 解析、路径推导、人工/自动字幕判别、分片判断(**单测核心**) |
| `scripts/transcribe.py` | ASR 编排:引擎选择 + 调 lib + 写 transcript |
| `scripts/fetch.sh` | yt-dlp 下载 + ffmpeg 抽音频 |
| `scripts/bootstrap.sh` | 依赖就位(yt-dlp/ffmpeg/ASR)+ 校验 + 回退 |
| `scripts/check.sh` | 依赖 + 本地 ASR 可用性自检 |
| `tests/test_asr_utils.py` | pytest 纯逻辑 |
| `tests/smoke.sh` | 各平台真链接冒烟 |
| `SKILL.md` | 路由 + 4 playbook |
| `references/examples/*.md` | 4 playbook 黄金样例 |

---

# 里程碑 M1 · 核心闭环(Tier-1 可发)

## Task 1: 建测试骨架 + `fmt_ts`(时间戳格式化)

**Files:**
- Create: `scripts/lib/__init__.py`(空)
- Create: `scripts/lib/asr_utils.py`
- Test: `tests/test_asr_utils.py`
- Create: `pytest.ini`

**Interfaces:**
- Produces: `fmt_ts(seconds: float) -> str` —— `<3600` 秒返回 `"MM:SS"`,`>=3600` 返回 `"H:MM:SS"`。

- [ ] **Step 1: 写失败测试**
```python
# tests/test_asr_utils.py
from scripts.lib.asr_utils import fmt_ts

def test_fmt_ts_under_hour():
    assert fmt_ts(0) == "00:00"
    assert fmt_ts(65) == "01:05"
    assert fmt_ts(599.9) == "09:59"

def test_fmt_ts_over_hour():
    assert fmt_ts(3661) == "1:01:01"
```
- [ ] **Step 2: 跑,确认 FAIL**
Run: `python3 -m pytest tests/test_asr_utils.py -v`
Expected: FAIL(ImportError/AttributeError)
- [ ] **Step 3: 最小实现**
```python
# scripts/lib/asr_utils.py
def fmt_ts(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"
```
- [ ] **Step 4: 跑,确认 PASS**
Run: `python3 -m pytest tests/test_asr_utils.py -v`
Expected: PASS
- [ ] **Step 5: 提交**
```bash
# pytest.ini 内容:[pytest]\npythonpath = .
git add scripts/lib/__init__.py scripts/lib/asr_utils.py tests/test_asr_utils.py pytest.ini
git commit -m "feat(asr_utils): fmt_ts timestamp formatter (TDD)"
```

## Task 2: `parse_vtt`(VTT → 分段)

**Files:** Modify `scripts/lib/asr_utils.py`; Modify `tests/test_asr_utils.py`
**Interfaces:** Produces `parse_vtt(text: str) -> list[tuple[int, str]]` —— 返回 `(起始秒, 文本)` 列表,合并 cue 内多行,跳过 `WEBVTT/NOTE`。

- [ ] **Step 1: 写失败测试**
```python
from scripts.lib.asr_utils import parse_vtt

def test_parse_vtt_basic():
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello\n\n00:01:05.000 --> 00:01:07.000\nworld\nagain\n"
    assert parse_vtt(vtt) == [(1, "Hello"), (65, "world again")]
```
- [ ] **Step 2: 跑,确认 FAIL** — `python3 -m pytest tests/test_asr_utils.py::test_parse_vtt_basic -v`
- [ ] **Step 3: 实现**
```python
import re
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
```
- [ ] **Step 4: 跑,确认 PASS**
- [ ] **Step 5: 提交** — `git commit -m "feat(asr_utils): parse_vtt (TDD)"`

## Task 3: `derive_output_dir`(路径推导 + 消毒)

**Files:** Modify lib + tests
**Interfaces:** Produces `derive_output_dir(extractor: str, video_id: str, root: str) -> str` —— 返回 `root/<sane_extractor>-<sane_id>`;非 `[A-Za-z0-9_-]` 字符替换为 `_`。

- [ ] **Step 1: 失败测试**
```python
from scripts.lib.asr_utils import derive_output_dir
def test_derive_output_dir_sanitizes():
    assert derive_output_dir("douyin", "abc123", "video-out") == "video-out/douyin-abc123"
    assert derive_output_dir("You/Tube", "a b*c", "out") == "out/You_Tube-a_b_c"
```
- [ ] **Step 2: FAIL** — `python3 -m pytest -k derive_output_dir -v`
- [ ] **Step 3: 实现**
```python
def _sane(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", s)

def derive_output_dir(extractor: str, video_id: str, root: str) -> str:
    return f"{root}/{_sane(extractor)}-{_sane(video_id)}"
```
- [ ] **Step 4: PASS**
- [ ] **Step 5: 提交** — `git commit -m "feat(asr_utils): derive_output_dir with sanitization (TDD)"`

## Task 4: `is_manual_subtitle`(人工/自动字幕判别,R7)

**Files:** Modify lib + tests
**Interfaces:** Produces `is_manual_subtitle(filename: str) -> bool` —— yt-dlp 自动字幕文件名含 `.auto`/`-auto`(如 `sub.en-auto.vtt`、`sub.en.auto.vtt`)判为自动→False;否则人工→True。

- [ ] **Step 1: 失败测试**
```python
from scripts.lib.asr_utils import is_manual_subtitle
def test_is_manual_subtitle():
    assert is_manual_subtitle("sub.zh-Hans.vtt") is True
    assert is_manual_subtitle("sub.en-auto.vtt") is False
    assert is_manual_subtitle("sub.en.auto.vtt") is False
```
- [ ] **Step 2: FAIL**
- [ ] **Step 3: 实现**
```python
def is_manual_subtitle(filename: str) -> bool:
    low = filename.lower()
    return not (".auto." in low or "-auto." in low)
```
- [ ] **Step 4: PASS**
- [ ] **Step 5: 提交** — `git commit -m "feat(asr_utils): manual-vs-auto subtitle discriminator (TDD)"`

## Task 5: `segments_to_markdown` / `segments_to_text`

**Files:** Modify lib + tests
**Interfaces:** Produces `segments_to_markdown(segs) -> str`(每段 `` `[MM:SS]` 文本 ``)、`segments_to_text(segs) -> str`(纯文本换行)。空文本段跳过。

- [ ] **Step 1: 失败测试**
```python
from scripts.lib.asr_utils import segments_to_markdown, segments_to_text
def test_segments_render():
    segs = [(1, "Hello"), (65, "  "), (66, "world")]
    assert segments_to_markdown(segs) == "# Transcript\n\n`[00:01]` Hello\n\n`[01:06]` world\n"
    assert segments_to_text(segs) == "Hello\nworld\n"
```
- [ ] **Step 2: FAIL**
- [ ] **Step 3: 实现**
```python
def segments_to_markdown(segs) -> str:
    out = ["# Transcript", ""]
    for start, text in segs:
        t = text.strip()
        if t:
            out.append(f"`[{fmt_ts(start)}]` {t}"); out.append("")
    return "\n".join(out[:-1]) + "\n" if len(out) > 2 else "# Transcript\n\n"

def segments_to_text(segs) -> str:
    return "".join(f"{t.strip()}\n" for _, t in segs if t.strip())
```
- [ ] **Step 4: PASS**
- [ ] **Step 5: 提交** — `git commit -m "feat(asr_utils): segment renderers (TDD)"`

## Task 6: `bootstrap.sh`(yt-dlp + ffmpeg 就位 + 校验 + 回退)

**Files:** Create `scripts/bootstrap.sh`
**Interfaces:** Produces `~/.video-anything/bin/{yt-dlp,ffmpeg}`;导出 `VA_HOME=~/.video-anything`。幂等(已就位则跳过)。
**验证方式:** 冒烟(网络+二进制,不单测)。

- [ ] **Step 1: 写脚本**(核心逻辑,含 OS×arch 探测、SHA256 校验、ffmpeg 回退系统)
```bash
#!/usr/bin/env bash
set -uo pipefail
VA_HOME="${VA_HOME:-$HOME/.video-anything}"; BIN="$VA_HOME/bin"; mkdir -p "$BIN"
os="$(uname -s)"; arch="$(uname -m)"
# --- yt-dlp (official release, pinned + checksum) ---
YTDLP_VER="2026.07.01"    # pin; update deliberately
case "$os" in
  Darwin) asset="yt-dlp_macos" ;;
  Linux)  asset="yt-dlp_linux" ;;
  *)      echo "unsupported OS: $os (Windows needs WSL/git-bash)"; exit 1 ;;
esac
if [ ! -x "$BIN/yt-dlp" ]; then
  url="https://github.com/yt-dlp/yt-dlp/releases/download/$YTDLP_VER/$asset"
  curl -fsSL "$url" -o "$BIN/yt-dlp"
  curl -fsSL "$url.sha256" -o "$BIN/yt-dlp.sha256" 2>/dev/null || \
    curl -fsSL "https://github.com/yt-dlp/yt-dlp/releases/download/$YTDLP_VER/SHA2-256SUMS" -o "$BIN/SUMS"
  # verify (accept either per-asset .sha256 or SUMS file)
  ( cd "$BIN" && (shasum -a 256 -c yt-dlp.sha256 2>/dev/null || grep " $asset\$" SUMS | sed "s/$asset/yt-dlp/" | shasum -a 256 -c -) ) \
    || { echo "yt-dlp checksum FAILED"; rm -f "$BIN/yt-dlp"; exit 1; }
  chmod +x "$BIN/yt-dlp"
fi
# --- ffmpeg: prefer system, else fetch static per OS×arch ---
if command -v ffmpeg >/dev/null 2>&1; then
  ln -sf "$(command -v ffmpeg)" "$BIN/ffmpeg" 2>/dev/null || true
elif [ ! -x "$BIN/ffmpeg" ]; then
  echo ">> system ffmpeg not found; fetching static build for $os/$arch"
  bash "$(dirname "$0")/bootstrap_ffmpeg.sh" "$BIN" "$os" "$arch" \
    || { echo "ffmpeg provisioning failed — install ffmpeg manually (see references/install.md)"; exit 1; }
fi
echo ">> bootstrap ok: $BIN"
```
> ffmpeg 静态源逻辑抽到 `bootstrap_ffmpeg.sh`(mac→evermeet、linux→johnvansickle,各钉版本+校验),作为本任务的一部分创建。
- [ ] **Step 2: 干净环境冒烟**
Run: `env VA_HOME=/tmp/va-test bash scripts/bootstrap.sh`
Expected: 打印 `bootstrap ok`,`/tmp/va-test/bin/yt-dlp -–version` 可运行
- [ ] **Step 3: 幂等验证** — 再跑一次,Expected: 跳过已就位项、无报错
- [ ] **Step 4: 提交** — `git commit -m "feat(bootstrap): provision yt-dlp+ffmpeg with checksum & system fallback"`

## Task 7: `check.sh`(依赖 + 本地 ASR 可用性自检)

**Files:** Modify `scripts/check.sh`(原型已有,升级为「缺则触发 bootstrap + 探测本地 ASR 真可用」)
**Interfaces:** Produces 退出码 0=全就绪;打印每项状态,含「本地 ASR 引擎:faster-whisper venv / 系统 whisper / 无」。

- [ ] **Step 1: 升级脚本** —— 在原型基础上:①缺 yt-dlp/ffmpeg 则调 `bootstrap.sh`;②ASR 探测按 Global Constraints 顺序,输出实际可用引擎名。
- [ ] **Step 2: 冒烟** — `bash scripts/check.sh`;Expected: 本机(Py3.14 无 faster-whisper)应报告「系统 whisper 可用」并整体 ✅
- [ ] **Step 3: 提交** — `git commit -m "feat(check): probe real local-ASR availability + auto-bootstrap"`

## Task 8: `fetch.sh`(下载 + 抽音频,收敛到 lib 的路径约定)

**Files:** Modify `scripts/fetch.sh`(原型已可用,改为:用私有 bin 的 yt-dlp/ffmpeg;目录名与 `derive_output_dir` 规则一致;cookie 逃生舱保留)
**Interfaces:** 最后一行打印产出目录。

- [ ] **Step 1: 调整** —— PATH 前置 `~/.video-anything/bin`;确认输出目录命名与 Task 3 规则一致(extractor-id,消毒)。
- [ ] **Step 2: 冒烟(Tier-1)** — 用一个短公开 YouTube 链接
Run: `bash scripts/fetch.sh "<short_youtube_url>" /tmp/vo`
Expected: 产出 `video.mp4 + audio.wav + info.json`,最后一行是目录路径
- [ ] **Step 3: 提交** — `git commit -m "feat(fetch): use private bin, align output dir naming"`

## Task 9: `transcribe.py`(引擎选择 + 调 lib + 写 transcript)

**Files:** Modify `scripts/transcribe.py`(原型重构:纯函数改为 import `lib.asr_utils`;引擎选择实现 Global Constraints;`--engine` 默认 local)
**Interfaces:** Consumes `lib.asr_utils.{fmt_ts,parse_vtt,segments_to_markdown,segments_to_text}`;CLI `transcribe.py <audio> [--engine local|cloud] [--model small] [--lang auto]`。

- [ ] **Step 1: 重构** —— 删掉内联的 fmt/parse,改 import lib;引擎级联:`--engine cloud`→云(暂留 stub,M3 实装)、否则 faster-whisper→系统 whisper CLI→报错。产物用 `segments_to_markdown/text` 写。
- [ ] **Step 2: 集成冒烟** — 拿 Task 8 产出的 `audio.wav`
Run: `python3 scripts/transcribe.py /tmp/vo/<dir>/audio.wav`
Expected: 生成 `transcript.md`(带 `[MM:SS]`)与 `transcript.txt`
- [ ] **Step 3: 单测仍绿** — `python3 -m pytest -v`
- [ ] **Step 4: 提交** — `git commit -m "feat(transcribe): engine cascade + lib-backed rendering"`

## Task 10: `SKILL.md` M1 + 提炼要点 playbook + 样例

**Files:** Modify `SKILL.md`;Create `references/examples/key-points.md`
**Interfaces:** SKILL.md 描述含触发词;主流程引用 check/fetch/transcribe;第 1 个 playbook「提炼要点」写死指令。

- [ ] **Step 1: 更新 SKILL.md** —— 加「首次运行 `bootstrap.sh`」;写「提炼要点」playbook(3–7 bullet + 一句话主旨),引用样例文件。
- [ ] **Step 2: 写黄金样例** `references/examples/key-points.md`(一段真实 transcript → 期望要点输出)。
- [ ] **Step 3: 端到端人工验收** — 在 Claude Code 里对一个真链接跑「下载→文案→提炼要点」,核对产出。
- [ ] **Step 4: 提交** — `git commit -m "feat(skill): M1 routing + key-points playbook + example"`

> **M1 完成 = 可发「下载+文案+提炼要点」最小可用版(Tier-1)。**

---

# 里程碑 M2 · 自媒体主盘(首发主力)

## Task 11: 抖音/快手 + 人工字幕优先

**Files:** Modify `scripts/fetch.sh`、`references/platforms.md`、`scripts/transcribe.py`
- [ ] **Step 1:** fetch.sh 对抖音短链自动跟随;抖音/快手 cookie 提示;platforms.md 补两平台无水印/反爬条目。
- [ ] **Step 2:** 接入「人工字幕优先」——fetch 产出字幕后,用 `is_manual_subtitle` 判定;仅人工字幕时 transcribe 可跳过 ASR(加 `--prefer-subs` 开关,默认开)。
- [ ] **Step 3: 冒烟** — 各拿一个公开抖音/快手链接跑通下载+文案。
- [ ] **Step 4: 提交** — `git commit -m "feat: douyin/kuaishou support + manual-subtitle-first"`

## Task 12: 口播改写 playbook + 样例

**Files:** Modify `SKILL.md`;Create `references/examples/rewrite.md`
- [ ] **Step 1:** 写「口播稿改写」playbook —— 输入 transcript + 目标风格(小红书种草/知识拆解/播客),输出重写稿;含风格清单与约束。
- [ ] **Step 2:** 黄金样例(一段 transcript → 三种风格各一版)。
- [ ] **Step 3: 人工验收 + 提交** — `git commit -m "feat(skill): voiceover-rewrite playbook + example"`

> **M2 完成 = 覆盖抖音/快手 + 两大 playbook,可作首发主力对外发布。**

---

# 里程碑 M3 · 差异化补全

## Task 13: 拆分镜 + 选题矩阵 playbook + 样例

**Files:** Modify `SKILL.md`;Create `references/examples/{storyboard,topics}.md`
- [ ] **Step 1:** 「拆分镜」playbook —— 按 transcript 时间戳输出 镜号/时间/画面/口播 表。
- [ ] **Step 2:** 「选题矩阵」playbook —— 基于主题输出 5–10 选题 + 标题。
- [ ] **Step 3:** 两份黄金样例。
- [ ] **Step 4: 人工验收 + 提交** — `git commit -m "feat(skill): storyboard + topic-matrix playbooks"`

## Task 14: 云 ASR(Groq)+ 大小检测 + 分片(R8)

**Files:** Modify `scripts/lib/asr_utils.py`、`tests/test_asr_utils.py`、`scripts/transcribe.py`
**Interfaces:** Produces `plan_chunks(size_bytes: int, limit: int = 25*1024*1024) -> int`(返回需切的块数,≥1)。

- [ ] **Step 1: 失败测试**
```python
from scripts.lib.asr_utils import plan_chunks
def test_plan_chunks():
    assert plan_chunks(10*1024*1024) == 1
    assert plan_chunks(30*1024*1024) == 2
    assert plan_chunks(0) == 1
```
- [ ] **Step 2: FAIL** — `python3 -m pytest -k plan_chunks -v`
- [ ] **Step 3: 实现**
```python
import math
def plan_chunks(size_bytes: int, limit: int = 25 * 1024 * 1024) -> int:
    return max(1, math.ceil(size_bytes / limit)) if size_bytes > 0 else 1
```
- [ ] **Step 4: PASS**;然后在 transcribe.py 实装云引擎:`--engine cloud` 时读 `GROQ_API_KEY`(不存在则报错),按 `plan_chunks` 用 ffmpeg 切音频、逐块调 Groq、拼接。
- [ ] **Step 5: 提交** — `git commit -m "feat(transcribe): cloud engine (Groq) with size-based chunking (TDD)"`

---

# 里程碑 M4 · 硬化 + 发布

## Task 15: 全平台冒烟 + bootstrap 干净环境验证

**Files:** Create `tests/smoke.sh`
- [ ] **Step 1:** 写 smoke.sh —— 遍历 5 平台各一条公开短链,跑 fetch(可选 transcribe),报告每平台 PASS/FAIL;顶部注明「失败先判链接是否失效」。
- [ ] **Step 2:** 在干净环境(容器或 UTM VM)从零跑 bootstrap→fetch→transcribe,确认零手动安装可用。
- [ ] **Step 3: 提交** — `git commit -m "test: cross-platform smoke + clean-env bootstrap verification"`

## Task 16: README/install 打磨 + 填占位 + 跨 agent 验证

**Files:** Modify `README.md`、`references/install.md`、`SKILL.md`
- [ ] **Step 1:** 填 `SKILL.md` 的 `homepage` 占位为真实 repo;README 平台表/钩子终稿。
- [ ] **Step 2:** 至少在 Claude Code + 另一个 agent(Cursor/Codex)各验证一次 skill 可被识别调用。
- [ ] **Step 3: 提交** — `git commit -m "docs: finalize README/install, fill repo homepage, cross-agent verified"`

> **M4 完成 = 全量 v1 可发布。**

---

## Self-Review

**1. Spec 覆盖检查**
- §2 达标线:①平台→Task 8/11/15;②transcribe→Task 9;③4 playbook+样例→Task 10/12/13;④零安装 bootstrap→Task 6/7;⑤README/跨agent→Task 16;⑥单测+冒烟+VM→Task 1-5/15;⑦不承诺秒级→README(Task 16)。✅
- §4 bootstrap(校验/回退/兼容Python)→Task 6/7;§5 数据流/字幕优先→Task 8/9/11;§7 playbooks→Task 10/12/13;§8 双引擎+分片→Task 9/14;§9 错误处理→Task 6-9 分散;§10 测试→Task 1-5/15;§12 平台→Task 8/11;§14 分阶段→M1-M4 结构。✅
- 未覆盖项:无。视频号/批量/Windows 原生按 §11 明确不做。

**2. 占位符扫描**:无 TBD/TODO;shell 脚本给了核心可运行逻辑(ffmpeg 静态源细节下放到 `bootstrap_ffmpeg.sh` 由 Task 6 一并创建,非占位)。✅

**3. 类型一致性**:`fmt_ts/parse_vtt/derive_output_dir/is_manual_subtitle/segments_to_*/plan_chunks` 在定义(Task 1-5/14)与消费(Task 9/11/14)处签名一致。✅
